import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-github-actions.py"
SPEC = importlib.util.spec_from_file_location("validate_github_actions", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


class ValidateGitHubActionsTest(unittest.TestCase):
    def write_yaml(self, relative_path, payload):
        path = self.tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_third_party_tag_requires_sha_or_allowlist(self):
        errors = []

        validator.validate_uses_ref(
            Path("actions/example/action.yml"),
            "some-owner/some-action@v1",
            errors,
        )

        self.assertTrue(
            any("third-party action reference" in error for error in errors),
            "validate_uses_ref must reject unallowlisted third-party moving tags. "
            f"WHY: moving tags can change without review. HOW: inspect validate_uses_ref; errors={errors!r}",
        )

    def test_sha_pinned_third_party_ref_passes(self):
        errors = []

        validator.validate_uses_ref(
            Path("actions/dependabot-automerge/action.yml"),
            "dependabot/fetch-metadata@25dd0e34f4fe68f24cc83900b1fe3fe149efef98",
            errors,
        )

        self.assertEqual(
            errors,
            [],
            "validate_uses_ref must allow SHA-pinned third-party actions. "
            f"WHY: full commit SHAs provide a reviewed stable dependency boundary. "
            f"HOW: inspect third-party SHA handling in validate_uses_ref; errors={errors!r}",
        )

    def test_root_write_permissions_fail(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": "pull_request",
            "permissions": {"contents": "write"},
            "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}},
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("top-level permissions include broad scopes" in error for error in errors),
            "validate_workflow must reject broad root workflow permissions. "
            f"WHY: root workflow permissions apply too widely. HOW: inspect validate_permissions; errors={errors!r}",
        )

    def test_read_all_permissions_require_allowlist(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": "pull_request",
            "permissions": "read-all",
            "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}},
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("top-level permissions use 'read-all'" in error for error in errors),
            "validate_workflow must reject root read-all permissions without allowlist evidence. "
            f"WHY: broad workflow permissions need explicit review. HOW: inspect validate_permissions; errors={errors!r}",
        )

    def test_job_level_reusable_workflow_ref_is_validated(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": "pull_request",
            "permissions": {"contents": "read"},
            "jobs": {
                "call": {
                    "uses": "some-owner/some-repo/.github/workflows/ci.yml@main",
                }
            },
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("uses branch ref 'main'" in error for error in errors),
            "validate_workflow must apply action ref policy to job-level reusable workflows. "
            f"WHY: reusable workflow refs can drift like action refs. HOW: inspect iter_workflow_job_uses; errors={errors!r}",
        )

    def test_pull_request_target_requires_allowlist_reason(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": {"pull_request_target": None},
            "permissions": {"contents": "read"},
            "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}},
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("pull_request_target without an allowlist reason" in error for error in errors),
            "validate_workflow must reject pull_request_target without allowlist evidence. "
            f"WHY: privileged PR triggers can expose secrets. HOW: inspect validate_workflow trigger handling; errors={errors!r}",
        )

    def test_action_opt_out_inputs_fail(self):
        errors = []
        action = {
            "name": "Bad",
            "description": "Bad action",
            "inputs": {"run-tests": {"required": False, "default": "true"}},
            "runs": {"using": "composite", "steps": []},
        }
        path = self.write_yaml("actions/bad/action.yml", action)

        validator.validate_action(path, errors)

        self.assertTrue(
            any("input 'run-tests' can disable a standard check" in error for error in errors),
            "validate_action must reject standard-check opt-out inputs. "
            f"WHY: shared standard checks must not be casually disabled. HOW: inspect validate_action inputs; errors={errors!r}",
        )

    def test_workflow_rejects_curl_to_shell_run_blocks(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": "pull_request",
            "permissions": {"contents": "read"},
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "curl -fsSL https://example.test/install.sh | bash"}],
                }
            },
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("downloads and executes a script directly" in error for error in errors),
            "validate_workflow must reject curl-to-shell run blocks. "
            f"WHY: remote install scripts bypass reviewed action metadata. HOW: inspect validate_run_block; errors={errors!r}",
        )

    def test_workflow_rejects_wget_to_shell_run_blocks(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": "pull_request",
            "permissions": {"contents": "read"},
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "wget -qO- https://example.test/install.sh | sh"}],
                }
            },
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("downloads and executes a script directly" in error for error in errors),
            "validate_workflow must reject wget-to-shell run blocks. "
            f"WHY: remote install scripts bypass reviewed action metadata. HOW: inspect validate_run_block; errors={errors!r}",
        )

    def test_workflow_rejects_process_substitution_curl_to_bash(self):
        errors = []
        workflow = {
            "name": "Bad",
            "on": "pull_request",
            "permissions": {"contents": "read"},
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"run": "bash <(curl -fsSL https://example.test/install.sh)"}],
                }
            },
        }
        path = self.write_yaml(".github/workflows/bad.yml", workflow)

        validator.validate_workflow(path, errors)

        self.assertTrue(
            any("downloads and executes a script directly" in error for error in errors),
            "validate_workflow must reject process-substitution curl-to-bash blocks. "
            f"WHY: remote install scripts bypass reviewed action metadata. HOW: inspect validate_run_block; errors={errors!r}",
        )

    def test_recursive_action_discovery_catches_nested_actions(self):
        action = {
            "name": "Nested",
            "description": "Nested action",
            "runs": {
                "using": "composite",
                "steps": [{"uses": "some-owner/some-action@v1"}],
            },
        }
        self.write_yaml("actions/group/nested/action.yml", action)

        old_root = validator.ROOT
        try:
            validator.ROOT = self.tmp_path
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = validator.main()
            self.assertEqual(
                result,
                1,
                "main must recursively validate nested action.yml files under actions/. "
                f"WHY: composite action dependencies need the same ref policy as workflows. "
                f"HOW: inspect main action discovery; result={result!r}",
            )
        finally:
            validator.ROOT = old_root


if __name__ == "__main__":
    unittest.main()
