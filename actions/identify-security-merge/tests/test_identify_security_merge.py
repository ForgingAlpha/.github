from pathlib import Path
import unittest


ACTION = Path(__file__).parents[1] / "action.yml"


class IdentifySecurityMergeContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = ACTION.read_text()

    def test_rechecks_exact_merge_identity_and_current_base(self):
        for fragment in (
            'current_base="$(gh api',
            '.merge_commit_sha == $sha',
            '.base.ref == $base',
            '.user.login == "dependabot[bot]"',
            'any(.labels[]?; .name == $label)',
            'pr_head_sha=',
            'external_id="security-pr-${pr_number}-${pr_head_sha}"',
            '.app.id == $app_id',
            '"${merged_by_login}" = "${app_slug}[bot]"',
        ):
            self.assertIn(fragment, self.text)

    def test_label_is_not_security_authority(self):
        self.assertIn("vulnerabilityAlerts", self.text)
        self.assertIn("dependabotUpdate{pullRequest{number}}", self.text)
        self.assertIn('.state == "OPEN" or .state == "FIXED"', self.text)
        self.assertIn("no official open or fixed GitHub security-alert association", self.text)


if __name__ == "__main__":
    unittest.main()
