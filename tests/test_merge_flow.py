import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class MergeFlowBehaviorTest(unittest.TestCase):
    def run_guard(self, head_repository, base="main", dev_exists=True):
        action = yaml.safe_load((ROOT / "actions/ci-merge-flow/action.yml").read_text())
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            gh = tmp / "gh"
            gh.write_text("#!/bin/sh\n" + ("echo '{}'\n" if dev_exists else "echo 'HTTP 404: Not Found' >&2\nexit 1\n"))
            gh.chmod(0o755)
            verifier = tmp / "python3"
            verifier.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$VERIFIER_LOG"\nexit 1\n')
            verifier.chmod(0o755)
            log = tmp / "verifier.log"
            env = {
                **os.environ, "PATH": f"{tmp}:{os.environ['PATH']}",
                "HEAD_REF": "dev", "HEAD_REPOSITORY": head_repository,
                "BASE_REF": base, "GITHUB_REPOSITORY": "ForgingAlpha/example",
                "GITHUB_ACTION_PATH": str(ROOT / "actions/ci-merge-flow"),
                "PR_NUMBER": "42", "VERIFIER_LOG": str(log),
            }
            result = subprocess.run(["bash", "-c", action["runs"]["steps"][0]["run"]], env=env, text=True, capture_output=True)
            return result, log.read_text() if log.exists() else ""

    def test_same_repository_dev_can_target_main_or_staging(self):
        for base in ("main", "staging"):
            with self.subTest(base=base):
                result, verification = self.run_guard("ForgingAlpha/example", base)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(verification, "")

    def test_fork_dev_has_no_ordinary_dev_exemption(self):
        for base in ("main", "staging"):
            with self.subTest(base=base):
                result, verification = self.run_guard("contributor/example", base)
                self.assertNotEqual(result.returncode, 0)
                if base == "main":
                    self.assertIn("verify-ci-admission", verification)
                else:
                    self.assertEqual(verification, "")

    def test_main_only_repository_keeps_ordinary_feature_admission(self):
        result, _ = self.run_guard("contributor/example", dev_exists=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_declared_direct_staged_pairs_and_dev_preservation(self):
        helper = ROOT / "actions/ci-merge-flow/scripts/check_merge_flow.sh"
        for route, head, base, expected in [("direct","dev","main",0),("staged","dev","staging",0),("staged","staging","main",0),("staged","dev","main",1),("direct","main","dev",0),("staged","staging","dev",0),("unknown","dev","main",1),("direct","feature","staging",1)]:
            env = {**os.environ,"DECLARED_ROUTE":route,"HEAD_REF":head,"BASE_REF":base,"HEAD_REPOSITORY":"ForgingAlpha/example","GITHUB_REPOSITORY":"ForgingAlpha/example","PR_NUMBER":"42","GITHUB_ACTION_PATH":str(ROOT/"actions/ci-merge-flow")}
            result=subprocess.run(["bash",str(helper),"declared-route"],env=env,capture_output=True)
            with self.subTest(route=route,head=head,base=base):self.assertEqual(result.returncode==0,expected==0,result.stderr)
