import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_workflows.py"
ACTION = Path(__file__).resolve().parents[1] / "action.yml"
SPEC = importlib.util.spec_from_file_location("check_workflows", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError(
        f"WHAT: could not load checker test module from {SCRIPT}. "
        "WHY: these tests import the reusable ci-github-actions checker directly. "
        "HOW: restore actions/ci-github-actions/scripts/check_workflows.py."
    )
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class CheckWorkflowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_yaml(self, relative_path, payload):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    def run_git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_action_wrapper_pins_actionlint_and_runs_checker(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        run_blocks = "\n".join(
            step.get("run", "")
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        )

        self.assertIn(
            'ACTIONLINT_VERSION: "1.7.12"',
            ACTION.read_text(encoding="utf-8"),
            "ci-github-actions must pin actionlint v1.7.12 in action.yml. "
            "WHY: workflow validation behavior must remain reproducible across repos. "
            "HOW: restore the pinned ACTIONLINT_VERSION env value.",
        )
        self.assertIn(
            "sha256sum -c -",
            run_blocks,
            "ci-github-actions must verify the downloaded actionlint archive checksum. "
            "WHY: downloaded binaries must be integrity-checked before execution. "
            "HOW: restore the checksum verification step before tar extraction.",
        )
        self.assertIn(
            "scripts/check_workflows.py",
            run_blocks,
            "ci-github-actions must run the reusable Python safety checker. "
            "WHY: actionlint alone does not enforce Alpha Apps ref, permission, and allowlist policy. "
            "HOW: restore the final checker invocation in action.yml.",
        )

    def test_composite_action_uses_references_are_scanned(self):
        self.run_git("init", "-b", "main")
        self.write_yaml(
            "actions/example/action.yml",
            {
                "name": "Example",
                "description": "Example action",
                "runs": {
                    "using": "composite",
                    "steps": [{"uses": "some-owner/some-action@main"}],
                },
            },
        )
        self.run_git("add", ".")

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = checker.run(self.root, allowlist_path=None)

        self.assertEqual(
            result,
            1,
            "check_workflows must scan uses refs inside composite action.yml files. "
            "WHY: composite-action dependencies can drift like workflow step dependencies. "
            f"HOW: inspect iter_action_paths and validate_action; result={result!r}",
        )

    def test_action_discovery_uses_tracked_files(self):
        self.run_git("init", "-b", "main")
        self.run_git("config", "user.email", "test@example.invalid")
        self.run_git("config", "user.name", "Test")
        self.write_yaml(
            "actions/tracked/action.yml",
            {
                "name": "Tracked",
                "description": "Tracked action",
                "runs": {"using": "composite", "steps": []},
            },
        )
        self.write_yaml(
            "actions/generated/action.yml",
            {
                "name": "Generated",
                "description": "Generated action",
                "runs": {
                    "using": "composite",
                    "steps": [{"uses": "some-owner/some-action@main"}],
                },
            },
        )
        self.run_git("add", "actions/tracked/action.yml")
        self.run_git("commit", "-m", "track action")

        paths = [
            path.relative_to(self.root).as_posix()
            for path in checker.iter_action_paths(self.root)
        ]

        self.assertEqual(
            paths,
            ["actions/tracked/action.yml"],
            "iter_action_paths must use tracked action manifests when git metadata is available. "
            "WHY: workflow safety scans should not traverse generated or dependency trees under actions/. "
            f"HOW: inspect git ls-files action discovery; paths={paths!r}",
        )

    def test_local_action_references_pass_for_self_ci(self):
        self.write_yaml(
            ".github/workflows/ci.yml",
            {
                "name": "CI",
                "on": "pull_request",
                "permissions": {"contents": "read"},
                "jobs": {
                    "CI": {
                        "runs-on": "ubuntu-latest",
                        "steps": [{"uses": "./actions/ci-merge-flow"}],
                    }
                },
            },
        )

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = checker.run(self.root, allowlist_path=None)

        self.assertEqual(
            result,
            0,
            "check_workflows must allow local ./actions/... references. "
            "WHY: this repo dogfoods in-branch composite actions before release tags move. "
            f"HOW: inspect local-reference handling in validate_uses_ref; result={result!r}",
        )

    def test_allowlist_entries_require_reasons(self):
        self.write_yaml(
            ".github/alphaapps-github-actions-allowlist.yml",
            {"action_refs": {"some-owner/some-action@v1": ""}},
        )
        self.write_yaml(
            "actions/example/action.yml",
            {
                "name": "Example",
                "description": "Example action",
                "runs": {
                    "using": "composite",
                    "steps": [{"uses": "some-owner/some-action@v1"}],
                },
            },
        )

        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            result = checker.run(self.root)

        self.assertEqual(
            result,
            1,
            "check_workflows must reject allowlist exceptions without reasons. "
            "WHY: exceptions need explicit review evidence. HOW: inspect require_reason_map.",
        )
        self.assertIn(
            "has no reason",
            stderr.getvalue(),
            "check_workflows diagnostics must identify the empty allowlist reason. "
            f"WHY: operators need to fix the exact exception entry. stderr={stderr.getvalue()!r}",
        )

    def test_allowlisted_third_party_tag_passes_with_reason(self):
        self.write_yaml(
            ".github/alphaapps-github-actions-allowlist.yml",
            {
                "action_refs": {
                    "some-owner/some-action@v1": "temporary upstream has no stable SHA in this fixture"
                }
            },
        )
        self.write_yaml(
            "actions/example/action.yml",
            {
                "name": "Example",
                "description": "Example action",
                "runs": {
                    "using": "composite",
                    "steps": [{"uses": "some-owner/some-action@v1"}],
                },
            },
        )

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = checker.run(self.root)

        self.assertEqual(
            result,
            0,
            "check_workflows must allow reviewed third-party tag exceptions with reasons. "
            "WHY: rollout exceptions are acceptable only when explicit and data-driven. "
            f"HOW: inspect action_refs allowlist handling; result={result!r}",
        )

    def test_pull_request_target_requires_allowlist_reason(self):
        self.write_yaml(
            ".github/workflows/unsafe.yml",
            {
                "name": "Unsafe",
                "on": {"pull_request_target": None},
                "permissions": {"contents": "read"},
                "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}},
            },
        )

        errors = []
        checker.validate_workflow(
            Path(".github/workflows/unsafe.yml"),
            errors,
            root=self.root,
            allowlists=checker.Allowlists.empty(),
        )

        self.assertTrue(
            any("pull_request_target without an allowlist reason" in error for error in errors),
            "validate_workflow must reject pull_request_target without allowlist evidence. "
            f"WHY: privileged PR triggers can expose secrets. HOW: inspect trigger handling; errors={errors!r}",
        )

    def test_root_write_permissions_require_allowlist_reason(self):
        self.write_yaml(
            ".github/workflows/write.yml",
            {
                "name": "Write",
                "on": "pull_request",
                "permissions": {"contents": "write"},
                "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}},
            },
        )

        errors = []
        checker.validate_workflow(
            Path(".github/workflows/write.yml"),
            errors,
            root=self.root,
            allowlists=checker.Allowlists.empty(),
        )

        self.assertTrue(
            any("top-level permissions include broad scopes" in error for error in errors),
            "validate_workflow must reject broad root workflow permissions without allowlist evidence. "
            f"WHY: workflow root permissions apply to every job by default. HOW: inspect validate_permissions; errors={errors!r}",
        )

    def test_read_all_permissions_require_allowlist_reason(self):
        path = self.write_yaml(
            ".github/workflows/read-all.yml",
            {
                "name": "Read all",
                "on": "pull_request",
                "permissions": "read-all",
                "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}},
            },
        )
        errors = []

        checker.validate_workflow(
            path.relative_to(self.root),
            errors,
            root=self.root,
            allowlists=checker.Allowlists.empty(),
        )

        self.assertTrue(any("top-level permissions use 'read-all'" in error for error in errors))

    def test_job_level_reusable_workflow_ref_is_validated(self):
        path = self.write_yaml(
            ".github/workflows/reusable.yml",
            {
                "name": "Reusable",
                "on": "pull_request",
                "permissions": {"contents": "read"},
                "jobs": {
                    "call": {"uses": "some-owner/some-repo/.github/workflows/ci.yml@main"}
                },
            },
        )
        errors = []

        checker.validate_workflow(
            path.relative_to(self.root),
            errors,
            root=self.root,
            allowlists=checker.Allowlists.empty(),
        )

        self.assertTrue(any("uses branch ref 'main'" in error for error in errors))

    def test_standard_check_opt_out_input_is_rejected(self):
        path = self.write_yaml(
            "actions/bad/action.yml",
            {
                "name": "Bad",
                "description": "Bad action",
                "inputs": {"run-tests": {"required": False, "default": "true"}},
                "runs": {"using": "composite", "steps": []},
            },
        )
        errors = []

        checker.validate_action(
            path.relative_to(self.root),
            errors,
            root=self.root,
            allowlists=checker.Allowlists.empty(),
        )

        self.assertTrue(any("input 'run-tests' can disable a standard check" in error for error in errors))

    def test_remote_download_to_shell_forms_are_rejected(self):
        run_blocks = (
            "curl -fsSL https://example.test/install.sh | bash",
            "wget -qO- https://example.test/install.sh | sh",
            "bash <(curl -fsSL https://example.test/install.sh)",
        )

        for run_block in run_blocks:
            with self.subTest(run_block=run_block):
                errors = []
                checker.validate_run_block(Path(".github/workflows/bad.yml"), run_block, errors)
                self.assertTrue(
                    any("downloads and executes a script directly" in error for error in errors)
                )

    def test_recursive_action_discovery_validates_deeply_nested_actions(self):
        self.run_git("init", "-b", "main")
        self.write_yaml(
            "actions/group/deep/nested/action.yml",
            {
                "name": "Nested",
                "description": "Nested action",
                "runs": {
                    "using": "composite",
                    "steps": [{"uses": "some-owner/some-action@main"}],
                },
            },
        )
        self.run_git("add", ".")

        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            result = checker.run(self.root, allowlist_path=None)

        self.assertEqual(result, 1)
        self.assertIn("some-owner/some-action@main", stderr.getvalue())

    def test_first_party_sha_policy_is_mandatory(self):
        self.write_yaml(
            "actions/example/action.yml",
            {
                "name": "Example",
                "description": "Example action",
                "runs": {
                    "using": "composite",
                    "steps": [{"uses": "actions/checkout@v7"}],
                },
            },
        )

        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            result = checker.run(self.root)

        self.assertEqual(
            result,
            1,
            "check_workflows must require SHA-only first-party policy. "
            "WHY: every external Action must resolve to immutable reviewed code. "
            f"HOW: inspect first_party_action_refs handling; stderr={stderr.getvalue()!r}",
        )
        self.assertIn(
            "external action reference",
            stderr.getvalue(),
            "SHA-only policy failure must name the external action. "
            f"WHY: agents need a concrete ref to pin. stderr={stderr.getvalue()!r}",
        )

    def test_probe_guard_v1_ref_is_allowed(self):
        errors = []

        checker.validate_uses_ref(
            Path(".github/workflows/probe.yml"),
            "ForgingAlpha/.github/actions/ci-remote-probe-guard@v1",
            errors,
            checker.Allowlists.empty(),
        )

        self.assertEqual(
            errors,
            [],
            "validate_uses_ref must allow the ForgingAlpha probe guard on @v1. "
            "WHY: diagnostics follow the latest-green internal platform model. "
            f"HOW: inspect is_forgingalpha_probe_automation handling; errors={errors!r}",
        )

    def test_probe_reusable_workflow_v1_ref_is_allowed(self):
        errors = []

        checker.validate_uses_ref(
            Path(".github/workflows/probe.yml"),
            "ForgingAlpha/.github/.github/workflows/ci-probe-elixir-postgres.yml@v1",
            errors,
            checker.Allowlists.empty(),
        )

        self.assertEqual(
            errors,
            [],
            "validate_uses_ref must allow ForgingAlpha reusable probe workflows on @v1. "
            "WHY: consumer repos should call the current centralized diagnostic workflow. "
            f"HOW: inspect internal reusable workflow ref handling; errors={errors!r}",
        )

    def test_probe_automation_rejects_non_v1_ref(self):
        errors = []

        checker.validate_uses_ref(
            Path(".github/workflows/probe.yml"),
            "ForgingAlpha/.github/actions/ci-remote-probe-guard@latest",
            errors,
            checker.Allowlists.empty(),
        )

        self.assertTrue(
            any("must use a vN major tag" in error for error in errors),
            "validate_uses_ref must reject probe automation refs outside @v1. "
            "WHY: diagnostics and required CI share one approved current channel. "
            f"HOW: inspect internal shared automation ref validation; errors={errors!r}",
        )

    def test_non_probe_internal_shared_action_main_ref_is_rejected(self):
        errors = []

        checker.validate_uses_ref(
            Path(".github/workflows/ci.yml"),
            "ForgingAlpha/.github/actions/ci-github-actions@main",
            errors,
            checker.Allowlists.empty(),
        )

        self.assertTrue(
            any("must use a vN major tag" in error for error in errors),
            "validate_uses_ref must reject @main for non-probe shared CI actions. "
            "WHY: all shared automation uses the latest-green v1 release channel. "
            f"HOW: inspect ForgingAlpha shared automation ref validation; errors={errors!r}",
        )


if __name__ == "__main__":
    unittest.main()
