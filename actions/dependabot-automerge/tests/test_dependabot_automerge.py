import unittest
from pathlib import Path

import yaml


ACTION_PATH = Path(__file__).resolve().parents[1] / "action.yml"
WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "dependabot-automerge.yml"


class DependabotAutomergeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
        cls.text = ACTION_PATH.read_text(encoding="utf-8")

    def test_normal_policy_is_patch_only(self):
        self.assertEqual(self.action["inputs"]["allow_patch"]["default"], "true")
        self.assertEqual(self.action["inputs"]["allow_minor"]["default"], "false")
        self.assertEqual(self.action["inputs"]["allow_major"]["default"], "false")

    def test_security_uses_official_alert_lookup_and_graphql_association(self):
        self.assertIn("alert-lookup: true", self.text)
        self.assertIn("vulnerabilityAlerts", self.text)
        self.assertIn("dependabotUpdate", self.text)
        self.assertIn("GHSA_ID", self.text)

    def test_merge_is_bound_to_validated_head(self):
        self.assertIn('--match-head-commit "${HEAD_SHA}"', self.text)
        self.assertIn("github.event.pull_request.head.sha", self.text)
        self.assertIn("github.actor", self.text)
        self.assertIn('gh pr review "${PR_URL}" --approve', self.text)

    def test_security_classification_is_app_owned_and_head_bound(self):
        for fragment in (
            "AlphaApps Security Classification",
            'external_id="security-pr-${PR_NUMBER}-${HEAD_SHA}"',
            'head_sha: $head_sha',
            'conclusion: "success"',
            '"repos/${GITHUB_REPOSITORY}/check-runs"',
        ):
            self.assertIn(fragment, self.text)

    def test_synchronize_clears_stale_auto_merge_and_label_before_reclassification(self):
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn('gh pr merge --disable-auto "${PR_URL}"', workflow_text)
        self.assertIn("--remove-label security-autopromote", workflow_text)
        self.assertIn("autoMergeRequest,labels", workflow_text)
        self.assertIn("Stale Dependabot merge or security-classification state remains", workflow_text)
        self.assertNotIn("--disable-auto \"${PR_URL}\" >/dev/null 2>&1 || true", workflow_text)
        self.assertIn("permission-checks: write", workflow_text)
        self.assertIn("if: ${{ github.actor == 'dependabot[bot]' }}", workflow_text)
        job_condition = yaml.safe_load(workflow_text)["jobs"]["dependabot-automerge"]["if"]
        self.assertNotIn("github.actor", job_condition)

    def test_file_scope_fetch_fails_closed(self):
        self.assertIn("gh api --paginate --slurp", self.text)
        self.assertIn("Pull-request file list is empty", self.text)

    def test_turnkey_asset_manifests_are_allowed(self):
        for path in (
            "assets/admin/package.json",
            "assets/admin/package-lock.json",
            "assets/customer/package.json",
            "assets/customer/package-lock.json",
        ):
            self.assertIn(path, self.text)

    def test_privileged_action_never_checks_out_pr_code(self):
        uses = [step.get("uses", "") for step in self.action["runs"]["steps"]]
        self.assertFalse(any(use.startswith("actions/checkout@") for use in uses))


if __name__ == "__main__":
    unittest.main()
