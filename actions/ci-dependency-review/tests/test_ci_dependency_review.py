import json
import os
import subprocess
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-dependency-review" / "action.yml"
SCRIPT = ROOT / "actions" / "ci-dependency-review" / "scripts" / "validate_license_evidence.py"
OFFICIAL_ACTION = "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294"


class CiDependencyReviewTest(unittest.TestCase):
    def load_action(self):
        return yaml.safe_load(ACTION.read_text(encoding="utf-8"))

    def run_validator(self, changes):
        value = changes if isinstance(changes, str) else json.dumps(changes)
        return subprocess.run(
            ["python3", str(SCRIPT)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "DEPENDENCY_CHANGES": value},
        )

    def test_contract_has_no_caller_bypass_or_license_override(self):
        action = self.load_action()
        self.assertNotIn("inputs", action)
        text = ACTION.read_text(encoding="utf-8")
        for obsolete in ("enabled", "deny-licenses", "allow-dependencies-licenses"):
            self.assertNotIn(obsolete, text)

    def test_official_review_uses_strict_central_policy(self):
        action = self.load_action()
        review = next(step for step in action["runs"]["steps"] if step.get("uses") == OFFICIAL_ACTION)

        self.assertEqual(review["id"], "review")
        self.assertEqual(review["if"], "${{ github.event_name == 'pull_request' }}")
        self.assertEqual(review["with"]["fail-on-severity"], "low")
        self.assertEqual(review["with"]["fail-on-scopes"], "runtime,development,unknown")
        allowlist = review["with"]["allow-licenses"]
        for expected in ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC"):
            self.assertIn(expected, allowlist.split(","))

    def test_non_pull_request_skip_is_explanatory(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("not applicable outside pull_request", text)
        self.assertIn("WHAT:", text)
        self.assertIn("WHY:", text)
        self.assertIn("HOW:", text)

    def test_missing_license_guard_runs_even_if_official_review_fails(self):
        action = self.load_action()
        guard = next(
            step for step in action["runs"]["steps"] if step.get("name") == "Reject missing license evidence"
        )
        self.assertIn("always()", guard["if"])
        self.assertEqual(
            guard["env"]["DEPENDENCY_CHANGES"],
            "${{ steps.review.outputs.dependency-changes }}",
        )

    def test_validator_accepts_known_license_and_ignores_removals(self):
        result = self.run_validator(
            [
                {"change_type": "added", "package_url": "pkg:npm/good@1", "license": "MIT"},
                {"change_type": "removed", "package_url": "pkg:npm/old@1", "license": None},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validator_rejects_unknown_license_with_remediation(self):
        result = self.run_validator(
            [{"change_type": "added", "package_url": "pkg:npm/unknown@1", "license": None}]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pkg:npm/unknown@1", result.stderr)
        self.assertIn("WHAT:", result.stderr)
        self.assertIn("WHY:", result.stderr)
        self.assertIn("HOW:", result.stderr)

    def test_validator_rejects_missing_or_malformed_output(self):
        for value in ("", "not-json", "{}", "[null]"):
            with self.subTest(value=value):
                result = self.run_validator(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("WHAT:", result.stderr)

    def test_validator_rejects_malformed_license_or_change_type(self):
        invalid_records = (
            {"change_type": "added", "package_url": "pkg:npm/object@1", "license": {}},
            {"change_type": "added", "package_url": "pkg:npm/list@1", "license": []},
            {"change_type": "modified", "package_url": "pkg:npm/future@1", "license": "MIT"},
        )
        for record in invalid_records:
            with self.subTest(record=record):
                result = self.run_validator([record])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("WHAT:", result.stderr)


if __name__ == "__main__":
    unittest.main()
