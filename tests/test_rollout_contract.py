import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class RolloutContractTest(unittest.TestCase):
    def load(self, relative_path):
        return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))

    def test_rollout_is_successful_main_workflow_run_only(self):
        workflow = self.load(".github/workflows/release.yml")
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(triggers["workflow_run"]["workflows"], ["CI"])
        job = workflow["jobs"]["rollout"]
        condition = job["if"]
        for required in (
            "V1_ROLLOUT_ENABLED == 'true'",
            "conclusion == 'success'",
            "event == 'push'",
            "head_branch == 'main'",
        ):
            self.assertIn(required, condition)
        self.assertIn("workflow_dispatch", triggers)

    def test_rollout_is_serialized_and_write_is_job_scoped(self):
        workflow = self.load(".github/workflows/release.yml")
        self.assertEqual(workflow["concurrency"]["group"], "v1-rollout")
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        self.assertEqual(workflow["permissions"]["contents"], "read")
        self.assertEqual(workflow["permissions"]["actions"], "read")
        self.assertEqual(workflow["jobs"]["rollout"]["permissions"]["contents"], "write")

    def test_rollout_checks_current_main_and_current_v1(self):
        workflow_text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        for required in (
            "git/ref/heads/main",
            "workflow_run.head_sha",
            "resolve_tag_commit v1",
            "git/matching-refs/tags/v1-rollout-",
            "gh api --paginate --slurp",
            'actions/runs?head_sha=${VERIFIED_SHA}&branch=main&event=push&status=success',
            '.path == ".github/workflows/ci.yml"',
            "must not silently undo an operator rollback",
            "v1-rollout-${timestamp}-${short_sha}",
            'previous_v1_object=',
            "git push --atomic",
            '--force-with-lease="refs/tags/v1:${PREVIOUS_V1_OBJECT}"',
            '"${VERIFIED_SHA}:refs/tags/v1"',
            '"refs/tags/${ROLLOUT_TAG}"',
            'already_complete=',
        ):
            self.assertIn(required, workflow_text)

    def test_rollback_uses_environment_and_immutable_tag(self):
        workflow = self.load(".github/workflows/rollback-v1.yml")
        self.assertEqual(workflow["jobs"]["rollback"]["environment"], "v1-rollback")
        self.assertEqual(workflow["concurrency"]["group"], "v1-rollout")
        workflow_text = (ROOT / ".github/workflows/rollback-v1.yml").read_text(encoding="utf-8")
        self.assertIn("v1-rollout-", workflow_text)
        self.assertIn("actions/runs?head_sha=${target_sha}&branch=main&event=push&status=success", workflow_text)
        self.assertIn("gh api --paginate --slurp", workflow_text)
        self.assertIn('.path == ".github/workflows/ci.yml"', workflow_text)
        self.assertIn("^v1-rollout-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$", workflow_text)
        self.assertNotIn("v1-bootstrap", workflow_text)
        self.assertNotIn("V1_BOOTSTRAP_SHA", workflow_text)
        self.assertIn("compare/${target_sha}...${current_main}", workflow_text)
        self.assertIn('--force-with-lease="refs/tags/v1:${CURRENT_V1_OBJECT}"', workflow_text)
        self.assertIn("v1-rollback-${timestamp}-${short_sha}", workflow_text)
        self.assertIn("git push --atomic", workflow_text)
        self.assertIn('"refs/tags/${rollback_record}"', workflow_text)
        self.assertIn("ROLLBACK_RECORD: ${{ steps.restore.outputs.rollback_record }}", workflow_text)


if __name__ == "__main__":
    unittest.main()
