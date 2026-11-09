"""Local composition with public synthetic consumers and provider observations.

The wrapper and generated evaluator execute. GitHub's exit-to-step and
evaluator-to-run mappings, grants and API responses are synthetic; reports are
captured. These tests establish no native execution or protected permission.
"""

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

import test_consumer_compatibility as fixtures
import test_consumer_controller as providers


ROOT = Path(__file__).resolve().parents[1]
adapter = fixtures.adapter
controller = providers.controller
CONFIG = '{"config":{"default":false,"MD001":true}}\n'


class ComposedStandardsTests(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.TemporaryDirectory(prefix="consumer-standards-")
        self.addCleanup(self.state.cleanup)
        self.root = Path(self.state.name)
        self.consumer = self.root / "consumer"
        self.consumer.mkdir()
        self.git("init", "-q")
        (self.consumer / ".markdownlint-cli2.jsonc").write_text(CONFIG)
        workflow = self.consumer / ".github/workflows/ci.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(fixtures.serialize(fixtures.synthetic()))
        self.runner = self.root / "runner"
        self.runner.mkdir()
        self.observations = []

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "protocol.allow=never", "-C", str(self.consumer), *args],
            stderr=subprocess.PIPE, text=True,
        ).strip()

    def revision(self, markdown):
        (self.consumer / "README.md").write_text(markdown)
        self.git("add", "--", "README.md", ".markdownlint-cli2.jsonc", ".github/workflows/ci.yml")
        self.git("-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "synthetic consumer revision")
        return self.git("rev-parse", "HEAD"), self.git("rev-parse", "HEAD^{tree}")

    def execute(self, revision):
        head, tree = revision
        value, identity, branch = controller.plan(
            7, providers.HEAD, providers.TREE, head, tree, "e" * 40, "f" * 40,
        )
        source = self.git("show", head + ":.github/workflows/ci.yml") + "\n"
        generated = adapter.generate(source, providers.HEAD, providers.TREE, head, tree, branch)
        projected = adapter.parse(generated)["jobs"]["compatibility"]
        original = adapter.workflow(source)["jobs"]["CI"]
        action_root = ROOT / "actions/ci-markdown"
        action = adapter.yaml.safe_load((action_root / "action.yml").read_text())
        code = "\n".join(step["run"] for step in action["runs"]["steps"] if "run" in step)
        markdown = subprocess.run(
            ["bash", "-c", code], cwd=self.consumer, capture_output=True, text=True, timeout=90,
            env={**os.environ, "GITHUB_ACTION_PATH": str(action_root),
                 "MARKDOWN_CONFIG_PATH": ".markdownlint-cli2.jsonc", "RUNNER_TEMP": str(self.runner)},
        )
        outcomes = {s["id"]: {"outcome": "success", "conclusion": "success"}
                    for s in projected["steps"] if "id" in s}
        outcomes["markdown"] = {"outcome": "success" if markdown.returncode == 0 else "failure",
                                "conclusion": "success" if markdown.returncode == 0 else "failure"}
        evaluator = subprocess.run(
            ["bash", "-c", projected["steps"][-1]["run"]], capture_output=True, text=True, timeout=30,
            env={**os.environ, "STEP_RESULTS": json.dumps(outcomes)},
        )
        self.observations.append({"consumer_commit": head, "consumer_tree": tree, "plan": identity,
                                  "markdown_exit": markdown.returncode,
                                  "markdown_output": markdown.stdout + markdown.stderr,
                                  "evaluator_exit": evaluator.returncode,
                                  "evaluator_output": evaluator.stdout + evaluator.stderr,
                                  "consumer_config": CONFIG})
        return (value, identity, branch, generated, original, projected, False), markdown, evaluator

    def native(self, material, markdown, evaluator, fixture):
        """Explicit synthetic provider mapping, including unrelated successful work."""
        result = {}
        for index, (path, job) in enumerate(((controller.WORKFLOW, material[5]),
                                           (".github/workflows/ci.yml", material[4])), 1):
            conclusion = "success" if evaluator.returncode == 0 else "failure"
            run_id, check_id, suite_id = 100 + index, 200 + index, 300 + index
            run = {"id": run_id, "run_attempt": 1, "check_suite_id": suite_id,
                   "event": "pull_request", "path": path, "head_sha": fixture["head"]["sha"],
                   "head_branch": material[2], "repository": {"id": controller.CONSUMER_ID},
                   "head_repository": {"id": controller.CONSUMER_ID}, "pull_requests": [],
                   "status": "completed", "conclusion": conclusion}
            names = [s["name"] for s in job["steps"]]
            steps = [{"name": name, "number": i, "status": "completed", "conclusion": "success"}
                     for i, name in enumerate(["Set up job", *names, "Post Synthetic checkout", "Complete job"], 1)]
            if markdown.returncode:
                next(s for s in steps if s["name"] == "markdown")["conclusion"] = "failure"
            if evaluator.returncode:
                next(s for s in steps if s["name"] == names[-1])["conclusion"] = "failure"
            native_job = {"id": check_id, "run_id": run_id, "run_attempt": 1,
                          "head_sha": run["head_sha"], "name": job["name"], "steps": steps,
                          "status": "completed", "conclusion": conclusion,
                          "check_run_url": "https://api.github.com/repos/" + controller.CONSUMER + "/check-runs/" + str(check_id)}
            check = {"id": check_id, "app": {"id": 15368}, "head_sha": run["head_sha"],
                     "check_suite": {"id": suite_id}, "name": job["name"],
                     "status": "completed", "conclusion": conclusion}
            result[path] = (run, [native_job], [check], fixture, path, material[2], names, job["name"])
        return result

    def fixture(self, material):
        value, identity, branch, generated, *_ = material
        # A real local commit includes only the generated workflow over this consumer.
        self.git("checkout", "--detach", "-q", value["consumer_commit"])
        workflow = self.consumer / controller.WORKFLOW
        workflow.write_text(generated)
        self.git("add", "--", controller.WORKFLOW)
        self.git("-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "synthetic generated fixture")
        ref = self.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", "-q", value["consumer_commit"])
        return {"number": 8, "state": "open", "draft": True,
                "body": controller.private_body(value, identity, generated),
                "user": {"id": 456, "type": "Bot"},
                "head": {"sha": ref, "ref": branch, "repo": {"id": controller.CONSUMER_ID}},
                "base": {"sha": value["consumer_commit"], "ref": "dev", "repo": {"id": controller.CONSUMER_ID}}}

    def reconcile(self, material, fixture, records, previous=None):
        c = controller.Controller.__new__(controller.Controller)
        c.grant = providers.grant()
        c.current = Mock(return_value=material[0]["consumer_commit"])
        c.admit = Mock(return_value=providers.public_pr())
        c.material = Mock(return_value=material)
        c.owned_check = Mock(return_value=previous)
        events = []
        reports = []

        def report(*args, **kwargs):
            events.append(("report", args[2]))
            reports.append(controller.check_payload(*args, **kwargs))

        c.report = report
        c.fixture = Mock(side_effect=lambda *args: events.append(("fixture", None)) or fixture)
        c.consumer = Mock()
        c.consumer.branch.return_value = fixture["head"]["sha"]
        by_id = {r[0]["id"]: r for r in records.values()}
        by_check = {r[2][0]["id"]: r[2][0] for r in records.values()}

        def listing(path, key=None, limit=None):
            if key == "workflow_runs":
                name = path.split("/workflows/", 1)[1].split("/runs", 1)[0]
                return [r[0] for p, r in records.items() if p.rsplit("/", 1)[1] == name]
            return by_id[int(path.split("/")[3])][1]

        def request(path):
            if path.startswith("/pulls/"):
                return fixture
            if path.startswith("/check-runs/"):
                return by_check[int(path.rsplit("/", 1)[1])]
            return by_id[int(path.rsplit("/", 1)[1])][0]

        c.consumer.listing.side_effect = listing
        c.consumer.request.side_effect = request
        try:
            c.reconcile(providers.public_pr())
        except controller.Refusal:
            # Actual refusal is preserved in the captured final report.
            self.assertEqual(reports[-1]["conclusion"], "action_required")
        self.observations.append({"reports": reports, "events": events})
        return reports, events

    def test_rule_rejection_remediation_and_fresh_plan(self):
        bad_revision = self.revision("# Heading\n\n### Skipped level\n")
        bad, markdown, evaluator = self.execute(bad_revision)
        self.assertEqual(markdown.returncode, 1, markdown.stdout + markdown.stderr)
        self.assertIn("MD001", markdown.stdout + markdown.stderr)
        self.assertNotEqual(evaluator.returncode, 0, evaluator.stdout + evaluator.stderr)
        self.assertIn('"markdown": "failure"', evaluator.stderr)
        bad_fixture = self.fixture(bad)
        bad_records = self.native(bad, markdown, evaluator, bad_fixture)
        with self.assertRaises(controller.NativeFailure):
            controller.native_success(*bad_records[controller.WORKFLOW])
        failed, _ = self.reconcile(bad, bad_fixture, bad_records)
        self.assertEqual(failed[-1]["conclusion"], "failure")
        retained_failure = copy.deepcopy(failed[-1])

        good_revision = self.revision("# Heading\n\n## Consecutive level\n")
        good, markdown, evaluator = self.execute(good_revision)
        self.assertNotEqual(bad_revision, good_revision)
        self.assertNotEqual(bad[1], good[1])
        self.assertNotEqual(bad[2], good[2])
        self.assertEqual(markdown.returncode, 0, markdown.stdout + markdown.stderr)
        self.assertEqual(evaluator.returncode, 0, evaluator.stdout + evaluator.stderr)
        good_fixture = self.fixture(good)
        good_records = self.native(good, markdown, evaluator, good_fixture)

        stale, events = self.reconcile(good, bad_fixture, bad_records, retained_failure)
        self.assertEqual(stale[-1]["conclusion"], "action_required")
        self.assertEqual(events[:2], [("report", "in_progress"), ("fixture", None)])
        wrong, _ = self.reconcile(good, good_fixture, bad_records, retained_failure)
        self.assertEqual(wrong[-1]["conclusion"], "action_required")
        self.assertTrue(controller.native_success(*good_records[controller.WORKFLOW]))
        fresh, _ = self.reconcile(good, good_fixture, good_records, retained_failure)
        self.assertEqual(fresh[-1]["conclusion"], "success")
        self.assertEqual(fresh[-1]["external_id"], good[1])
        self.assertEqual(retained_failure, failed[-1])
        self.assertEqual(retained_failure["external_id"], bad[1])


if __name__ == "__main__":
    unittest.main()
