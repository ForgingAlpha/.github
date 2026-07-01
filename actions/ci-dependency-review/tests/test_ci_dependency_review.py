import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-dependency-review" / "action.yml"


class CiDependencyReviewTest(unittest.TestCase):
    def load_action(self):
        return yaml.safe_load(ACTION.read_text(encoding="utf-8"))

    def run_blocks(self):
        action = self.load_action()
        return "\n".join(
            step.get("run", "")
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        )

    def test_defaults_match_security_baseline(self):
        inputs = self.load_action()["inputs"]

        self.assertEqual(
            inputs["enabled"]["default"],
            "true",
            "ci-dependency-review must default to enabled. "
            "WHY: dependency review is a security baseline PR check. "
            "HOW: restore enabled default true in action.yml.",
        )
        self.assertEqual(
            inputs["fail-on-severity"]["default"],
            "low",
            "ci-dependency-review must fail on low or higher vulnerabilities by default. "
            "WHY: the shared security baseline treats PR dependency vulnerabilities as merge-blocking evidence. "
            "HOW: restore fail-on-severity default low.",
        )
        self.assertEqual(
            inputs["fail-on-scopes"]["default"],
            "runtime,development,unknown",
            "ci-dependency-review must include runtime, development, and unknown scopes. "
            "WHY: dependency scope gaps should not bypass PR review. "
            "HOW: restore the fail-on-scopes default.",
        )

    def test_wraps_official_dependency_review_action_on_pull_requests(self):
        action = self.load_action()
        dependency_review_steps = [
            step
            for step in action["runs"]["steps"]
            if step.get("uses") == "actions/dependency-review-action@v5"
        ]

        self.assertEqual(
            len(dependency_review_steps),
            1,
            "ci-dependency-review must wrap the official actions/dependency-review-action@v5. "
            "WHY: the shared action should centralize GitHub's dependency diff review. "
            f"HOW: restore the dependency review uses step; steps={action['runs']['steps']!r}",
        )
        self.assertIn(
            "github.event_name == 'pull_request'",
            dependency_review_steps[0]["if"],
            "ci-dependency-review must run upstream dependency review only on pull_request. "
            "WHY: non-PR events do not provide the intended dependency diff enforcement surface. "
            "HOW: restore the pull_request condition on the Dependency Review step.",
        )

    def test_non_pull_request_skip_is_explanatory(self):
        run_blocks = self.run_blocks()

        self.assertIn(
            "Dependency review skipped outside pull_request",
            run_blocks,
            "ci-dependency-review must skip cleanly outside pull_request events. "
            "WHY: push and manual runs should explain why dependency review did not run. "
            "HOW: restore the non-pull_request skip step.",
        )
        self.assertIn(
            "WHAT:",
            run_blocks,
            "ci-dependency-review skip and failure output must include WHAT. "
            "WHY: agents need actionable diagnostics from shared CI. HOW: keep WHAT/WHY/HOW output.",
        )

    def test_license_policy_is_fail_closed_for_conflicting_inputs(self):
        run_blocks = self.run_blocks()

        self.assertIn(
            "Both allow-licenses and deny-licenses were set",
            run_blocks,
            "ci-dependency-review must reject simultaneous allow and deny license policies. "
            "WHY: GitHub dependency-review supports only one license policy direction. "
            "HOW: keep the input validation guard.",
        )
        self.assertEqual(
            self.load_action()["inputs"]["deny-licenses"]["default"],
            "",
            "ci-dependency-review must not set deprecated deny-licenses by default. "
            "WHY: upstream marks deny-licenses deprecated for possible removal. "
            "HOW: keep deny-licenses optional and empty by default.",
        )


if __name__ == "__main__":
    unittest.main()
