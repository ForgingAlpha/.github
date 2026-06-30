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

    def test_first_party_sha_policy_is_data_driven(self):
        self.write_yaml(
            ".github/alphaapps-github-actions-allowlist.yml",
            {"first_party_action_refs": "sha"},
        )
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
            "check_workflows must support data-driven SHA-only first-party policy. "
            "WHY: stricter pinning should not require checker rewrites. "
            f"HOW: inspect first_party_action_refs handling; stderr={stderr.getvalue()!r}",
        )
        self.assertIn(
            "first-party action reference",
            stderr.getvalue(),
            "SHA-only first-party policy failure must name the first-party action. "
            f"WHY: agents need a concrete ref to pin. stderr={stderr.getvalue()!r}",
        )


if __name__ == "__main__":
    unittest.main()
