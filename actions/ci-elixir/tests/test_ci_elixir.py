import os
import subprocess
import tempfile
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

    def run_phoenix_step(self, name, dependencies, deps_status=0, sobelow_status=0, grep_status=None):
        step = next(step for step in self.steps if step.get("name") == name)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = root / "calls"
            mix = root / "mix"
            mix.write_text(
                "#!/usr/bin/env python3\n"
                "import os, signal, sys\n"
                "from pathlib import Path\n"
                "signal.signal(signal.SIGPIPE, signal.SIG_DFL)\n"
                "args = sys.argv[1:]\n"
                "if args == ['deps']:\n"
                "    for line in os.environ['MOCK_DEPENDENCIES'].splitlines(keepends=True):\n"
                "        sys.stdout.write(line)\n"
                "        sys.stdout.flush()\n"
                "    sys.exit(int(os.environ['MOCK_DEPS_STATUS']))\n"
                "if args in (['help', 'sobelow'], ['sobelow', '--exit']):\n"
                "    with Path(os.environ['MOCK_CALLS']).open('a') as output:\n"
                "        output.write(' '.join(args) + '\\n')\n"
                "    sys.exit(int(os.environ['MOCK_SOBELOW_STATUS']))\n"
                "if args in (['help', 'credo'], ['help', 'deps.audit'], ['help', 'dialyzer']):\n"
                "    sys.exit(0)\n"
                "sys.exit(99)\n",
                encoding="utf-8",
            )
            mix.chmod(0o700)
            if grep_status is not None:
                grep = root / "grep"
                grep.write_text(f"#!/bin/sh\nexit {grep_status}\n", encoding="utf-8")
                grep.chmod(0o700)
            result = subprocess.run(
                ["bash", "-c", step["run"]],
                cwd=root,
                env={
                    **os.environ,
                    "PATH": f"{root}{os.pathsep}{os.environ['PATH']}",
                    "MOCK_DEPENDENCIES": dependencies,
                    "MOCK_DEPS_STATUS": str(deps_status),
                    "MOCK_SOBELOW_STATUS": str(sobelow_status),
                    "MOCK_CALLS": str(calls),
                },
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            observed = calls.read_text().splitlines() if calls.exists() else []
            return result, observed

    def test_phoenix_discovery_preserves_success_failure_and_scan_outcomes(self):
        steps = {
            "Require static-analysis tools": "help sobelow",
            "Analyze Phoenix security": "sobelow --exit",
        }
        # Exceeds a pipe buffer: an early successful grep must not kill Mix
        # and turn a Phoenix project into a silently skipped analysis.
        large_dependencies = "* phoenix (Hex package)\n" + "* another_dependency\n" * 5000
        cases = [
            ("present", "* phoenix (Hex package)\n", 0, 0, True),
            ("large present", large_dependencies, 0, 0, True),
            ("absent", "* ecto (Hex package)\n", 0, 0, False),
            ("failed with Phoenix", "* phoenix (Hex package)\n", 17, 17, False),
            ("failed without Phoenix", "* ecto (Hex package)\n", 17, 17, False),
        ]
        for name, expected_call in steps.items():
            for label, dependencies, deps_status, expected_status, invokes in cases:
                with self.subTest(step=name, case=label):
                    result, calls = self.run_phoenix_step(name, dependencies, deps_status)
                    self.assertEqual(result.returncode, expected_status, result.stderr)
                    self.assertEqual(calls, [expected_call] if invokes else [])

            for grep_status in (2, 127):
                with self.subTest(step=name, case="matcher error", status=grep_status):
                    result, calls = self.run_phoenix_step(
                        name, "* phoenix (Hex package)\n", grep_status=grep_status
                    )
                    self.assertEqual(result.returncode, grep_status, result.stderr)
                    self.assertEqual(calls, [])
                    self.assertIn("dependency detection failed", result.stderr)

            with self.subTest(step=name, case="Sobelow failure"):
                result, calls = self.run_phoenix_step(
                    name, "* phoenix (Hex package)\n", sobelow_status=23
                )
                expected_status = 1 if name == "Require static-analysis tools" else 23
                self.assertEqual(result.returncode, expected_status, result.stderr)
                self.assertEqual(calls, [expected_call])


if __name__ == "__main__":
    unittest.main()
