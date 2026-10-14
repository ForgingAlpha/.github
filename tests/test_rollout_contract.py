import json
import os
import subprocess
import sys
import tempfile
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


class RolloutBehaviorTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)
        workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        self.steps = {step["name"]: step for step in workflow["jobs"]["rollout"]["steps"]}
        self.repository = "ForgingAlpha/.github"
        self.sha = "a" * 40
        self.old = "b" * 40
        self.tag = "c" * 40
        self.responses = {
            f"repos/{self.repository}/git/ref/heads/main": [[0, self.sha], [0, self.sha]],
            f"repos/{self.repository}/actions/runs/901": [[0, json.dumps({
                "path": ".github/workflows/ci.yml", "event": "push", "head_branch": "main",
                "head_sha": self.sha, "conclusion": "success", "repository": {"full_name": self.repository},
                "html_url": "https://github.com/ForgingAlpha/.github/actions/runs/901",
            })]],
            f"repos/{self.repository}/git/matching-refs/tags/v1": [[0, json.dumps([[{
                "ref": "refs/tags/v1", "object": {"type": "commit", "sha": self.old},
            }]])]],
            f"repos/{self.repository}/git/matching-refs/tags/v1-rollout-": [[0, "[[]]"]],
        }
        self.log = self.tmp / "calls.jsonl"
        self.state = self.tmp / "responses.json"
        gh = self.tmp / "gh"
        gh.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(json.dumps(["gh", *args]) + "\\n")
path = next(arg for arg in args if arg.startswith("repos/"))
state = Path(os.environ["API_RESPONSES"])
responses = json.loads(state.read_text())
if path not in responses or not responses[path]:
    sys.exit("unexpected API read: " + path)
code, output = responses[path].pop(0)
state.write_text(json.dumps(responses))
print(output)
sys.exit(code)
''')
        gh.chmod(0o755)
        git = self.tmp / "git"
        git.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(json.dumps(["git", *sys.argv[1:]]) + "\\n")
''')
        git.chmod(0o755)
        self.env = {
            **os.environ, "PATH": f"{self.tmp}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": self.repository, "GITHUB_OUTPUT": str(self.tmp / "outputs"),
            "VERIFIED_SHA": self.sha, "VERIFIED_RUN_ID": "901", "VERIFIED_RUN_URL": "",
            "CALL_LOG": str(self.log), "API_RESPONSES": str(self.state),
        }

    def run_step(self, name):
        script = self.steps[name]["run"].replace("/tmp/", f"{self.tmp}/")
        return subprocess.run(["bash", "-c", script], cwd=self.tmp, env=self.env, text=True, capture_output=True)

    def verify(self):
        self.state.write_text(json.dumps(self.responses))
        return self.run_step("Verify exact current main SHA")

    def publish(self):
        for line in (self.tmp / "outputs").read_text().splitlines():
            key, value = line.split("=", 1)
            self.env[key.upper()] = value
        return self.run_step("Advance v1 and record atomically")

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def pushes(self):
        return [call for call in self.calls() if call[:2] == ["git", "push"]]

    def test_current_main_rollout_records_previous_commit_and_atomic_lease(self):
        self.assertEqual(self.verify().returncode, 0)
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.pushes()), 1)
        self.assertIn("--atomic", self.pushes()[0])
        self.assertIn(f"--force-with-lease=refs/tags/v1:{self.old}", self.pushes()[0])
        self.assertEqual(self.env["PREVIOUS_V1_COMMIT"], self.old)
        # The final API observation immediately precedes the only publication.
        self.assertEqual(self.calls()[-2], ["gh", "api", f"repos/{self.repository}/git/ref/heads/main", "--jq", ".object.sha"])

    def test_main_moving_after_verification_prevents_publication(self):
        self.responses[f"repos/{self.repository}/git/ref/heads/main"][1] = [0, "d" * 40]
        self.assertEqual(self.verify().returncode, 0)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Main moved", result.stdout)
        self.assertEqual(self.pushes(), [])

    def test_failed_final_main_read_prevents_publication(self):
        self.responses[f"repos/{self.repository}/git/ref/heads/main"][1] = [1, "provider unavailable"]
        self.assertEqual(self.verify().returncode, 0)
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.pushes(), [])

    def test_confirmed_absence_uses_absent_ref_lease(self):
        self.responses[f"repos/{self.repository}/git/matching-refs/tags/v1"] = [[0, "[[]]"]]
        self.assertEqual(self.verify().returncode, 0)
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.env["PREVIOUS_V1_COMMIT"], "")
        self.assertIn("--force-with-lease=refs/tags/v1:", self.pushes()[0])

    def test_failed_ref_enumeration_is_not_absence(self):
        self.responses[f"repos/{self.repository}/git/matching-refs/tags/v1"] = [[1, "provider unavailable"]]
        self.assertNotEqual(self.verify().returncode, 0)
        self.assertEqual(self.pushes(), [])
        self.assertFalse((self.tmp / "outputs").exists())

    def test_prior_rollout_enumeration_errors_prevent_release_outputs(self):
        endpoint = f"repos/{self.repository}/git/matching-refs/tags/v1-rollout-"
        for payload in ("not-json", "", "null", "{}", "[{}]", "[[null]]", '[[{"ref": 17}]]',
                        '[[{"ref": "refs/heads/main"}]]'):
            with self.subTest(payload=payload):
                self.responses[endpoint] = [[0, payload]]
                (self.tmp / "outputs").unlink(missing_ok=True)
                result = self.verify()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((self.tmp / "outputs").exists())
                self.assertEqual(self.pushes(), [])

    def test_prior_rollout_history_preserves_rollback_and_completed_retry(self):
        prior_tag = f"v1-rollout-20261013T120000Z-{self.sha[:12]}"
        self.responses[f"repos/{self.repository}/git/matching-refs/tags/v1-rollout-"] = [[0, json.dumps([
            [], [{"ref": f"refs/tags/{prior_tag}"}],
        ])]]
        self.responses[f"repos/{self.repository}/git/ref/tags/{prior_tag}"] = [[0, json.dumps({
            "type": "commit", "sha": self.sha,
        })]]
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.tmp / "outputs").exists())
        self.assertEqual(self.pushes(), [])

        self.responses[f"repos/{self.repository}/git/matching-refs/tags/v1"] = [[0, json.dumps([[{
            "ref": "refs/tags/v1", "object": {"type": "commit", "sha": self.sha},
        }]])]]
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        outputs = dict(line.split("=", 1) for line in (self.tmp / "outputs").read_text().splitlines())
        self.assertEqual(outputs["already_complete"], "true")
        self.assertEqual(outputs["rollout_tag"], prior_tag)
        self.assertEqual(self.pushes(), [])

    def annotated_ref(self, peel_code=0):
        self.responses[f"repos/{self.repository}/git/matching-refs/tags/v1"] = [[0, json.dumps([[{
            "ref": "refs/tags/v1", "object": {"type": "tag", "sha": self.tag},
        }]])]]
        self.responses[f"repos/{self.repository}/git/tags/{self.tag}"] = [[peel_code, json.dumps({"type": "commit", "sha": self.old})]]

    def test_annotated_ref_is_peeled_from_captured_object(self):
        self.annotated_ref()
        self.assertEqual(self.verify().returncode, 0)
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.env["PREVIOUS_V1_COMMIT"], self.old)
        self.assertIn(f"--force-with-lease=refs/tags/v1:{self.tag}", self.pushes()[0])

    def test_successful_raw_read_with_failed_peel_is_not_recorded_as_none(self):
        self.annotated_ref(peel_code=1)
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not be resolved", result.stdout)
        self.assertEqual(self.pushes(), [])
        self.assertFalse((self.tmp / "outputs").exists())

    def test_rollback_requires_rollout_suffix_bound_to_resolved_commit(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/rollback-v1.yml").read_text())
        self.steps = {step["name"]: step for step in workflow["jobs"]["rollback"]["steps"]}
        for suffix, target, allowed in (("c" * 12, self.old, False), (self.old[:12], self.old + "0", False), (self.old[:12], self.old, True)):
            with self.subTest(suffix=suffix, target=target):
                rollout_tag = f"v1-rollout-20261013T120000Z-{suffix}"
                self.env["ROLLOUT_TAG"] = rollout_tag
                (self.tmp / "outputs").unlink(missing_ok=True)
                self.log.unlink(missing_ok=True)
                responses = {
                    f"repos/{self.repository}/git/ref/tags/{rollout_tag}": [[0, json.dumps({"type": "tag", "sha": self.tag})]],
                    f"repos/{self.repository}/git/tags/{self.tag}": [[0, json.dumps({"type": "commit", "sha": target})]],
                    f"repos/{self.repository}/git/ref/heads/main": [[0, self.sha]],
                    f"repos/{self.repository}/compare/{target}...{self.sha}": [[0, "ahead"]],
                    f"repos/{self.repository}/actions/runs?head_sha={target}&branch=main&event=push&status=success&per_page=100": [[0, json.dumps([{
                        "workflow_runs": [{"path": ".github/workflows/ci.yml", "event": "push", "head_branch": "main",
                                           "head_sha": target, "conclusion": "success", "repository": {"full_name": self.repository}}],
                    }])]],
                    f"repos/{self.repository}/git/ref/tags/v1": [[0, self.sha], [0, json.dumps({"type": "commit", "sha": self.sha})]],
                }
                self.state.write_text(json.dumps(responses))
                result = self.run_step("Validate immutable target and historical CI")
                self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
                if allowed:
                    for line in (self.tmp / "outputs").read_text().splitlines():
                        key, value = line.split("=", 1)
                        self.env[key.upper()] = value
                    result = self.run_step("Restore v1 and record atomically")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(len(self.pushes()), 1)
                    self.assertIn(f"{target}:refs/tags/v1", self.pushes()[0])
                else:
                    self.assertFalse((self.tmp / "outputs").exists())
                    self.assertEqual(len(self.calls()), 2)
                    self.assertEqual(self.pushes(), [])


if __name__ == "__main__":
    unittest.main()
