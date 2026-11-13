"""Exercise the source admission guard and the credential boundary proposal."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("foundation_generator", ROOT / "scripts/qualify_foundation.py")
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        controller_path = ".github/workflows/consumer-compatibility-controller.yml"
        try:
            source = (ROOT / controller_path).read_text()
        except FileNotFoundError as error:
            raise AssertionError(
                f"Missing expected shared controller source at {controller_path}. "
                "Coordinate the shared-CI policy/controller owners and the Foundation caller owner "
                "to restore conforming source or review and adopt a coordinated successor or "
                "withdrawal, including required consumer qualification. This is a source "
                "reconciliation tripwire: Foundation retains source review rights, and central "
                "dependency eligibility is optional and separate from enrollment and grants."
            ) from error
        cls.workflow = generator.parse(source)
        cls.job = cls.workflow["jobs"]["reconcile"]
        cls.steps = cls.job["steps"]

    def guard(self, changes=None, context_changes=None):
        context = {"workflow_repository": "ForgingAlpha/.github", "workflow_sha": "a" * 40,
                   "workflow_ref": "ForgingAlpha/.github/.github/workflows/consumer-compatibility-controller.yml@refs/heads/main"}
        context.update(context_changes or {})
        env = {"PATH": os.defpath, "GITHUB_REPOSITORY": "ForgingAlpha/container-foundation",
               "GITHUB_REPOSITORY_ID": "1428636846", "GITHUB_REF": "refs/heads/dev",
               "GITHUB_EVENT_NAME": "schedule", "JOB_CONTEXT": json.dumps(context)}
        env.update(changes or {})
        # Execute the actual guard script, not a duplicate implementation.
        script = self.steps[0]["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        with tempfile.TemporaryDirectory(prefix="synthetic-controller-guard-") as temporary:
            output = Path(temporary) / "output"
            env["GITHUB_OUTPUT"] = str(output)
            result = subprocess.run([sys.executable, "-I", "-B", "-"], input=script, text=True,
                                    capture_output=True, env=env, timeout=10)
            return result, output.read_text() if output.exists() else ""

    def test_adopted_main_and_private_dev_are_permitted(self):
        for event in ("schedule", "push", "workflow_run", "workflow_dispatch"):
            result, output = self.guard({"GITHUB_EVENT_NAME": event})
            with self.subTest(event=event):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("sha=" + "a" * 40 + "\n", output)

    def test_pr_fork_wrong_repository_and_candidate_definitions_refuse_before_checkout(self):
        cases = [({"GITHUB_EVENT_NAME": "pull_request"}, {}),
                 ({"GITHUB_EVENT_NAME": "pull_request_target"}, {}),
                 ({"GITHUB_REF": "refs/heads/test/candidate"}, {}),
                 ({"GITHUB_REPOSITORY": "Other/container-foundation"}, {}),
                 ({"GITHUB_REPOSITORY_ID": "99"}, {}),
                 ({}, {"workflow_repository": "Other/.github"}),
                 ({}, {"workflow_sha": "main"}),
                 ({}, {"workflow_ref": "ForgingAlpha/.github/.github/workflows/consumer-compatibility-controller.yml@" + "a" * 40}),
                 ({"JOB_CONTEXT": '{"workflow_sha":"a","workflow_sha":"b"}'}, {})]
        for changes, context in cases:
            result, output = self.guard(changes, context)
            with self.subTest(changes=changes, context=context):
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")

    def test_uninvoked_reusable_source_has_one_serialized_protected_read_token_job(self):
        self.assertEqual(set(self.workflow["on"]), {"workflow_call"})
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.workflow["concurrency"], {"group": "consumer-compatibility-foundation", "cancel-in-progress": False})
        self.assertEqual(self.job["environment"], "consumer-compatibility")
        self.assertEqual(self.job["runs-on"], "ubuntu-24.04")
        self.assertEqual(self.job["timeout-minutes"], 15)
        self.assertNotIn("secrets.", json.dumps(self.job["env"]))

    def test_only_bound_shared_source_is_checked_out(self):
        checkouts = [s for s in self.steps if s.get("uses", "").startswith("actions/checkout@")]
        self.assertEqual(len(checkouts), 1)
        self.assertEqual(checkouts[0]["with"]["repository"], "${{ steps.source.outputs.repository }}")
        self.assertEqual(checkouts[0]["with"]["ref"], "${{ steps.source.outputs.sha }}")
        self.assertIs(checkouts[0]["with"]["persist-credentials"], False)
        self.assertNotIn("pull_request.head", json.dumps(self.workflow))

    def test_two_app_keys_and_tokens_are_separate_and_narrowed(self):
        tokens = [(i, s) for i, s in enumerate(self.steps) if s.get("uses", "").startswith("actions/create-github-app-token@")]
        self.assertEqual(len(tokens), 2)
        validate = next(i for i, s in enumerate(self.steps) if s.get("env", {}).get("CC_MODE") == "validate")
        public, private = (s["with"] for _, s in tokens)
        self.assertTrue(all(i > validate for i, _ in tokens))
        self.assertEqual(public["repositories"], ".github")
        self.assertEqual(private["repositories"], "container-foundation")
        self.assertNotEqual(public["app-id"], private["app-id"])
        self.assertNotEqual(public["private-key"], private["private-key"])
        self.assertEqual({k: v for k, v in public.items() if k.startswith("permission-")},
                         {"permission-contents": "read", "permission-pull-requests": "read", "permission-checks": "write"})
        self.assertEqual({k: v for k, v in private.items() if k.startswith("permission-")},
                         {"permission-contents": "write", "permission-pull-requests": "write", "permission-workflows": "write",
                          "permission-actions": "read", "permission-checks": "read"})
        self.assertNotIn("skip-token-revoke", public)
        self.assertNotIn("skip-token-revoke", private)
        for step in self.steps[:-1]:
            self.assertNotIn("outputs.token", json.dumps(step))
        self.assertEqual(self.steps[-1]["env"]["CC_MODE"], "reconcile")

    def test_dependency_install_is_exact_and_precedes_keys(self):
        install = next(i for i, s in enumerate(self.steps) if "pip --isolated install" in s.get("run", ""))
        first_key = next(i for i, s in enumerate(self.steps) if "private-key" in s.get("with", {}))
        self.assertLess(install, first_key)
        command = self.steps[install]["run"]
        for required in ("--require-hashes", "--no-deps", "--only-binary=:all:", "--no-cache-dir"):
            self.assertIn(required, command)
        requirements = (ROOT / "scripts/requirements.txt").read_text()
        self.assertIn("PyYAML==6.0.3 --hash=sha256:ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc", requirements)

    def test_completion_filter_precedes_environment_and_has_no_write_credentials(self):
        jobs = self.workflow["jobs"]
        wake = jobs["wake"]
        self.assertNotIn("environment", wake)
        self.assertTrue(all(value == "read" for value in wake["permissions"].values()))
        self.assertNotIn("secrets.", json.dumps(wake))
        self.assertEqual(jobs["reconcile"]["needs"], "wake")
        self.assertIn("needs.wake.outputs.admitted == 'true'", jobs["reconcile"]["if"])


if __name__ == "__main__":
    unittest.main()
