"""A native request is delivered only when its PR, merge and reviewed tree agree."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "actions/native-auto-merge"))
import observe


class OrdinaryCompletionTests(unittest.TestCase):
    def setUp(self):
        self.repo = "ForgingAlpha/example"
        self.base, self.head, self.merge, self.tree = (x * 40 for x in "abcf")
        self.target = {"id": 960093720, "full_name": self.repo}
        self.pull = {"number": 5, "state": "closed", "merged": True, "merged_at": "2026-10-01T12:30:00Z",
                     "merge_commit_sha": self.merge, "user": {"id": 10, "type": "User"}, "changed_files": 1,
                     "head": {"ref": "feature/example", "sha": self.head, "repo": self.target},
                     "base": {"ref": "dev", "sha": self.base, "repo": self.target}}
        self.commit = {"sha": self.merge, "parents": [{"sha": self.base}, {"sha": self.head}], "tree": {"sha": self.tree}}
        self.api = Mock(spec_set=["get", "pages"])
        resources = {
            f"repos/{self.repo}/pulls/5": self.pull,
            f"repos/{self.repo}/git/commits/{self.merge}": self.commit,
        }
        self.api.get.side_effect = lambda path, fresh=False: resources[path]
        self.files = [{"filename": "docs/guides/development.md", "status": "modified"}]
        pages = {f"repos/{self.repo}/pulls/5/files?per_page=100": [self.files]}
        self.api.pages.side_effect = lambda path, fresh=False: pages[path]
        self.policy = {"repository_id": self.target["id"], "branch": "dev", "ordinary_paths": ["docs/guides/**"]}

    def run_observer(self):
        return observe.observe(self.api, self.repo, 5, self.merge)

    def test_reconstructs_actual_commit_and_reads_policy_from_first_parent(self):
        receipt = {"reviews": [{"user_id": 12}], "request": {"actor_id": 31}, "merge_commit_sha": self.merge}
        with patch.object(observe, "load_policy", return_value=self.policy) as policy, \
             patch.object(observe.proof, "completion_evidence", return_value=receipt) as evidence:
            self.assertEqual(self.run_observer(), receipt)
        policy.assert_called_once_with(self.api, self.repo, self.base)
        evidence.assert_called_once_with(self.api, self.repo, self.pull, self.policy, self.tree)

    def test_personal_path_is_not_reported_as_native(self):
        with patch.object(observe, "load_policy", return_value=self.policy), \
             patch.object(observe.proof, "completion_evidence", return_value=None), self.assertRaisesRegex(ValueError, "personal"):
            self.run_observer()

    def test_refuses_unmerged_wrong_parents_and_manual_only_files(self):
        for case in ("unmerged", "parents", "excluded"):
            with self.subTest(case=case):
                self.pull["merged"] = case != "unmerged"
                self.commit["parents"][0]["sha"] = self.head if case == "parents" else self.base
                self.files[0]["filename"] = "README.md" if case == "excluded" else "docs/guides/example.md"
                with patch.object(observe, "load_policy", return_value=self.policy), \
                     patch.object(observe.proof, "completion_evidence") as evidence, self.assertRaises(ValueError):
                    self.run_observer()
                evidence.assert_not_called()


if __name__ == "__main__":
    unittest.main()
