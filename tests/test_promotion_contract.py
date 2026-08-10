import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "promote-branch.yml"


class PromotionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_accepts_and_validates_exact_source_sha(self):
        self.assertIn("source_sha:", self.text)
        self.assertIn("REQUESTED_SOURCE_SHA", self.text)
        self.assertIn("only the exact tested source head may be promoted", self.text)

    def test_promotion_uses_expected_old_sha_lease(self):
        self.assertIn('--force-with-lease="refs/heads/${TARGET_BRANCH}:${target_sha_before}"', self.text)
        self.assertIn("git push --atomic", self.text)
        self.assertIn('"refs/tags/${tag}"', self.text)

    def test_requires_approved_ci_workflow_run_on_source_sha(self):
        for fragment in (
            'actions/runs?head_sha=${source_sha}&branch=${SOURCE_BRANCH}&event=push&status=success',
            '.path == ".github/workflows/ci.yml"',
            '.event == "push"',
            '.head_branch == $branch',
            '.head_sha == $sha',
            '.repository.full_name == $repo',
            '"${normalized_checks}" == "CI"',
        ):
            self.assertIn(fragment, self.text)

    def test_rechecks_source_and_target_immediately_before_lease_push(self):
        for fragment in (
            'source_sha_now="$(git rev-parse "origin/${SOURCE_BRANCH}")"',
            'target_sha_now="$(git rev-parse "origin/${TARGET_BRANCH}")"',
            '"${source_sha_now}" == "${source_sha}"',
            '"${target_sha_now}" == "${target_sha_before}"',
        ):
            self.assertIn(fragment, self.text)

    def test_reusable_workflow_does_not_break_staging_route(self):
        self.assertNotIn("Unsupported promotion route", self.text)


if __name__ == "__main__":
    unittest.main()
