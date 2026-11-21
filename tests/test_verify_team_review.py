"""Exercise the reusable metadata job with its CLI, source checkout and bounded HTTP fixtures."""

from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/verify-team-review.yml"
NAME, ID = "ForgingAlpha/example", 7123
REPO = {"full_name": NAME, "id": ID}
BASE, HEAD, MERGE = ("a" * 40, "b" * 40, "c" * 40)
TOKEN = "fixture-local-read-only"
RULE = {"type": "pull_request", "ruleset_id": 25795345, "ruleset_source_type": "Organization",
        "ruleset_source": "ForgingAlpha", "parameters": {
            "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
            "required_reviewers": [{"reviewer": {"type": "Team", "id": 20299307}, "minimum_approvals": 1,
                                    "file_patterns": ["*"]}]}}


class TeamReviewTests(unittest.TestCase):
    def setUp(self):
        self.job = yaml.safe_load((ROOT / WORKFLOW).read_text())
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.bind, self.checkout, self.check = self.job["jobs"]["verify"]["steps"]
        self.source = self.workspace / self.checkout["with"]["path"]
        command = shlex.split(self.check["run"])
        self.assertEqual(command[:3], ["python3", "-I", "-B"])
        self.entry = self.workspace / command[3]
        scripts = "actions/ci-org-baseline/scripts/"
        files = [self.entry.relative_to(self.source), scripts + "baseline.py", scripts + "first_definition.py",
                 "actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py"]
        for relative in files:
            dest = self.source / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, dest)
        for args in (["init", "-q"], ["add", "."], ["-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
                                                   "commit", "-qm", "fixture checking source"]):
            subprocess.run(["git", *args], cwd=self.source, check=True, capture_output=True)
        self.sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.source, text=True).strip()
        self.pr = {"number": 42, "state": "open", "merge_commit_sha": MERGE,
                   "base": {"repo": REPO.copy(), "ref": "dev", "sha": BASE},
                   "head": {"repo": REPO.copy(), "ref": "task/example", "sha": HEAD}}
        self.event = {"repository": REPO.copy(), "number": 42, "pull_request": self.pr}
        self.env = {"GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
                    "GITHUB_REPOSITORY": NAME, "GITHUB_REPOSITORY_ID": str(ID), "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_EVENT_PATH": str(self.workspace / "event.json"), "GITHUB_REF": "refs/pull/42/merge",
                    "GITHUB_SHA": MERGE, "GITHUB_BASE_REF": "dev", "GITHUB_HEAD_REF": "task/example",
                    "DEFINING_SHA": self.sha, "GITHUB_TOKEN": TOKEN}
        self.prefix = "/repos/" + NAME
        self.rules_path = self.prefix + "/rules/branches/dev?per_page=100&page=1"
        self.merge_path = self.prefix + "/git/commits/" + MERGE
        self.merge = {"sha": MERGE, "parents": [{"sha": BASE}, {"sha": HEAD}]}
        self.rule = copy.deepcopy(RULE)
        self.live_pr = copy.deepcopy(self.pr)
        self.branch = {"name": "dev", "protected": True, "commit": {"sha": BASE}}
        self.responses = {self.prefix: REPO.copy(), self.prefix + "/pulls/42": self.live_pr,
                          self.prefix + "/branches/dev": self.branch, self.merge_path: self.merge, self.rules_path: [self.rule]}
        self.links = {}
        self.calls = []

    def open_response(self, request, timeout):
        url = urlsplit(request.full_url)
        self.assertEqual((url.scheme, url.netloc, request.get_method()), ("https", "api.github.com", "GET"))
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        path = url.path + ("?" + url.query if url.query else "")
        self.calls.append(path)
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        response = io.BytesIO(json.dumps(value).encode())
        response.headers = {"Link": self.links.get(path, "")}
        return response

    def run_entry(self):
        # Patch only the HTTP transport. Execute the workflow entry as __main__,
        # including its isolated source checks, JSON parsing, pagination and exit handling.
        Path(self.env["GITHUB_EVENT_PATH"]).write_text(json.dumps(self.event))
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.OpenerDirector.open", self.open_response), \
                patch.object(sys, "path", sys.path.copy()), patch.dict(sys.modules), redirect_stdout(io.StringIO()) as output:
            sys.modules.pop("baseline", None)
            runpy.run_path(str(self.entry), run_name="__main__")
        result = output.getvalue()
        self.assertNotIn(TOKEN, result)
        return json.loads(result)

    def refused(self):
        with self.assertRaises(SystemExit) as error:
            self.run_entry()
        diagnostic = str(error.exception)
        self.assertRegex(diagnostic, r"^WHAT: [^\n]+\nWHY: [^\n]+\nHOW: [^\n]+$")
        self.assertIn("existing read access", diagnostic)
        self.assertNotIn(TOKEN, diagnostic)

    def test_workflow_binding_and_isolation(self):
        self.assertEqual(self.job["on"], {"workflow_call": None})
        self.assertEqual(self.job["permissions"], {"contents": "read", "pull-requests": "read"})
        self.assertEqual(list(self.job["jobs"]), ["verify"])
        job = self.job["jobs"]["verify"]
        self.assertEqual(job["runs-on"], "ubuntu-latest")
        self.assertNotIn("if", job)
        self.assertNotIn("continue-on-error", job)
        self.assertEqual(self.bind["env"], {"JOB_CONTEXT": "${{ toJSON(job) }}"})
        self.assertEqual(self.checkout["with"], {"repository": "ForgingAlpha/.github", "ref": "${{ steps.source.outputs.sha }}",
                                                "path": "team-rule-source", "persist-credentials": False})
        self.assertEqual(self.check["env"], {"DEFINING_SHA": "${{ steps.source.outputs.sha }}", "GITHUB_TOKEN": "${{ github.token }}"})
        out = self.workspace / "output"
        context = {"workflow_sha": self.sha, "workflow_repository": "ForgingAlpha/.github",
                   "workflow_ref": "ForgingAlpha/.github/" + WORKFLOW + "@refs/heads/main"}
        for change, ok in (({}, True), ({"workflow_repository": NAME}, False),
                           ({"workflow_ref": context["workflow_ref"].replace("main", "task")}, False),
                           ({"workflow_ref": context["workflow_ref"].replace("verify-team-review", "other")}, False),
                           ({"workflow_sha": "main"}, False)):
            out.write_text("")
            result = subprocess.run(["bash", "-e", "-c", self.bind["run"]], cwd=self.workspace, capture_output=True,
                                    env={"JOB_CONTEXT": json.dumps({**context, **change}), "GITHUB_OUTPUT": str(out)})
            self.assertEqual(result.returncode == 0, ok)
            if not ok:
                self.assertRegex(result.stderr.decode(), r"^WHAT: [^\n]+\nWHY: [^\n]+\nHOW: [^\n]+$")
                self.assertIn(b"verify-team-review.yml@main", result.stderr)
            self.assertEqual(out.read_text(), f"sha={self.sha}\n" if ok else "")
        malformed = subprocess.run(["bash", "-e", "-c", self.bind["run"]], capture_output=True,
                                   env={"JOB_CONTEXT": TOKEN, "GITHUB_OUTPUT": str(out)})
        self.assertNotEqual(malformed.returncode, 0)
        self.assertIn(b"HOW: Call ForgingAlpha/.github/", malformed.stderr)
        self.assertNotIn(TOKEN.encode(), malformed.stderr)

    def test_pr_and_fork_metadata_only_with_additive_paginated_rules(self):
        self.responses[self.rules_path] = [{"type": "deletion", "ruleset_id": 7}]
        second = self.rules_path[:-1] + "2"
        self.links[self.rules_path] = f'<https://api.github.com{second}>; rel="next"'
        self.responses[second] = [self.rule]
        for source in (REPO, {"full_name": "contributor/example", "id": 111}):
            with self.subTest(source=source):
                self.pr["head"]["repo"] = self.live_pr["head"]["repo"] = source
                self.calls.clear()
                result = self.run_entry()
                self.assertEqual(result["pull_request"], {"number": 42, "event_base": BASE, "base": BASE, "head": HEAD, "merge": MERGE,
                                 "head_repository": source["full_name"], "head_repository_id": source["id"]})
                self.assertEqual(result["source_sha"], self.sha)
                self.assertEqual(self.calls, [self.prefix, self.prefix + "/pulls/42", self.merge_path, self.prefix + "/branches/dev",
                                              self.rules_path, second])

    def test_current_run_merge_with_older_event_snapshot(self):
        old_base = "d" * 40
        self.pr["base"]["sha"] = old_base
        for old_merge in (None, "e" * 40):
            with self.subTest(old_merge=old_merge), patch.dict(self.pr, merge_commit_sha=old_merge):
                receipt = self.run_entry()["pull_request"]
                self.assertEqual((receipt["event_base"], receipt["base"], receipt["head"], receipt["merge"]),
                                 (old_base, BASE, HEAD, MERGE))

    def test_run_merge_must_have_current_base_and_submitted_head_as_ordered_parents(self):
        old = "d" * 40
        for parents in ([old, HEAD], [BASE, old], [HEAD, BASE], [BASE], [BASE, HEAD, old]):
            with self.subTest(parents=parents), patch.dict(self.merge, parents=[{"sha": sha} for sha in parents]):
                self.refused()
        with patch.dict(self.merge, sha=old):
            self.refused()

    def test_push_records_exact_before_and_after_and_rejects_moved_or_deleted_branch(self):
        self.event = {"repository": REPO, "ref": "refs/heads/dev", "after": BASE, "before": HEAD, "deleted": False}
        self.env.update(GITHUB_EVENT_NAME="push", GITHUB_SHA=BASE, GITHUB_REF="refs/heads/dev")
        self.assertEqual(self.run_entry()["push"], {"before": HEAD, "after": BASE})
        self.assertNotIn(self.prefix + "/pulls/42", self.calls)
        for obj, key, value in ((self.event, "deleted", True), (self.event, "after", MERGE),
                                (self.event, "ref", "refs/tags/dev"), (self.branch, "protected", False),
                                (self.branch, "commit", {"sha": MERGE})):
            with self.subTest(key=key), patch.dict(obj, {key: value}):
                self.refused()

    def test_visibility_only_reviewer_can_accompany_the_required_team(self):
        reviewers = self.rule["parameters"]["required_reviewers"]
        reviewers.append({"reviewer": {"type": "Team", "id": 721}, "minimum_approvals": 0,
                          "file_patterns": ["docs/**"]})
        self.assertEqual(self.run_entry()["team_id"], 20299307)
        reviewers[0]["minimum_approvals"] = 0
        self.refused()

    def test_unreadable_partial_wrong_source_or_weak_policy(self):
        params = self.rule["parameters"]
        reviewer = params["required_reviewers"][0]
        for obj, key, value in ((self.responses, self.rules_path, []), (self.responses, self.rules_path, [{}, self.rule]),
                                (self.responses, self.rules_path, HTTPError("https://api.github.com", 403, TOKEN, {}, None)),
                                (self.links, self.rules_path, '<https://outside.invalid/data>; rel="next"'),
                                (self.links, self.rules_path, f'<https://api.github.com{self.rules_path[:-1]}2>; rel="last"'),
                                (self.rule, "ruleset_source_type", "Repository"), (self.rule, "ruleset_source", "Other"),
                                (self.rule, "ruleset_id", 42), (params, "dismiss_stale_reviews_on_push", False),
                                (params, "required_approving_review_count", 0), (params, "required_reviewers", []),
                                (reviewer, "reviewer", {"id": 20299307, "type": "User"}),
                                (reviewer, "reviewer", {"id": 1000, "type": "Team"}),
                                (reviewer, "minimum_approvals", 0), (reviewer, "file_patterns", ["docs/**"]),
                                (reviewer, "file_patterns", ["*", "!private/**"])):
            with self.subTest(key=key, value=value), patch.dict(obj, {key: value}):
                self.refused()

    def test_wrong_subject_untrusted_source_and_unsupported_events_fail(self):
        for obj, key, value in ((self.env, "GITHUB_EVENT_NAME", "pull_request_target"), (self.env, "GITHUB_REF", "refs/pull/4/merge"),
                                (self.env, "GITHUB_API_URL", "https://other.invalid"), (self.env, "GITHUB_SHA", HEAD),
                                (self.env, "GITHUB_BASE_REF", "main"), (self.env, "GITHUB_TOKEN", ""),
                                (self.env, "DEFINING_SHA", MERGE), (self.env, "GITHUB_REPOSITORY_ID", "321"),
                                (self.responses[self.prefix], "id", ID + 1), (self.live_pr, "state", "closed"),
                                (self.live_pr["head"], "sha", BASE), (self.live_pr["head"], "repo", {"full_name": NAME, "id": ID + 1}),
                                (self.live_pr["base"], "sha", HEAD), (self.branch, "name", "main")):
            with self.subTest(key=key), patch.dict(obj, {key: value}):
                self.refused()
        (self.source / "unexpected.txt").touch()
        self.refused()
