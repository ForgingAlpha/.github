import unittest
from pathlib import Path

import yaml


ACTION_PATH = Path(__file__).resolve().parents[1] / "action.yml"


class CiElixirTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
        cls.steps = cls.action["runs"]["steps"]
        cls.text = ACTION_PATH.read_text(encoding="utf-8")

    def test_profiles_are_explicit_and_locked(self):
        self.assertEqual(self.action["inputs"]["profile"]["default"], "full")
        self.assertIn("full|static|test", self.text)
        self.assertNotIn("elixir-version:", self.text)
        self.assertNotIn("otp-version:", self.text)
        self.assertIn("install_args: --locked", self.text)
        self.assertIn('artifact.get("url") and not artifact.get("checksum")', self.text)
        self.assertIn("downloaded artifacts without checksums", self.text)

    def test_test_profile_skips_cross_cutting_and_static_steps(self):
        static_names = {
            "Enforce merge flow",
            "Validate Alpha Apps policy",
            "Validate Markdown",
            "Validate GitHub Actions safety",
            "Validate Dependabot coverage",
            "Review dependency changes",
            "Require static-analysis tools",
            "Check formatting",
            "Compile with warnings as errors",
            "Credo strict",
            "Reject unused dependencies",
            "Audit Hex packages",
            "Audit retired dependencies",
            "Analyze Phoenix security",
            "Run Dialyzer",
        }
        for step in self.steps:
            if step.get("name") in static_names:
                self.assertIn("inputs.profile != 'test'", step.get("if", ""), step.get("name"))

    def test_static_profile_skips_test_setup_and_tests(self):
        for name in ("Run pre-test setup", "Run tests"):
            step = next(step for step in self.steps if step.get("name") == name)
            self.assertIn("inputs.profile != 'static'", step["if"])

    def test_required_analysis_is_fail_closed(self):
        for command in ("mix credo --strict", "mix deps.unlock --check-unused", "mix hex.audit", "mix deps.audit", "mix sobelow --exit", "mix dialyzer"):
            self.assertIn(command, self.text)


if __name__ == "__main__":
    unittest.main()
