"""Run the repo-owned document action on exact Git objects and native-shaped PR evidence."""

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_first_definition import FirstDefinition, PropertyApi
from test_org_baseline import ROOT


spec = importlib.util.spec_from_file_location("repo_governing_docs", ROOT / "actions/ci-governing-docs/check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
baseline = check.load_baseline()


class DocsApi(PropertyApi):
    def __init__(self, fixture, event):
        super().__init__(fixture)
        self.number = event["number"]
        self.live = copy.deepcopy(event["pull_request"])
        self.effective[0]["parameters"]["required_reviewers"][0]["reviewer"]["id"] = check.HUMAN_TEAM_ID
        self.reads = []

    def get(self, path):
        self.reads.append(path)
        prefix = "/repos/" + self.fixture.repo["full_name"]
        if path == f"{prefix}/pulls/{self.number}":
            return copy.deepcopy(self.live)
        if path == prefix + "/branches/dev":
            return copy.deepcopy(self.branch)
        raise AssertionError("unexpected provider read")


class RepoGoverningDocsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = FirstDefinition(Path(self.temp.name) / "consumer")
        self.saved_seed = self.f.base
        self.scope_csv = ".,engine"
        self.template = (check.ACTION / "caller.yml").read_bytes()
        self.write_caller(self.scope_csv)
        self.f.commit()
        self.number = 7
        self.enterContext(patch.object(check, "load_baseline", return_value=baseline))
        self.checked = self.enterContext(patch.object(baseline, "checked"))

    def write_caller(self, csv):
        self.f.write(check.CALLER, self.template.replace(b"scopes: '.'", f"scopes: '{csv}'".encode()))

    def followup(self):
        self.f.base = self.f.head
        self.f.git("update-ref", "refs/remotes/origin/dev", self.f.base)
        self.number = 8

    def promote(self, scope):
        prefix = "" if scope == "." else scope + "/"
        readme, req, arch = [self.f.root / (prefix + path) for path in ("README.md", "docs/requirements.md", "docs/architecture.md")]
        old_intent = baseline.policy.readme_intent(readme.read_bytes()).sha256
        readme.write_text(readme.read_text().replace("status: provisional", "status: approved"))
        intent = baseline.policy.readme_intent(readme.read_bytes()).sha256
        old_req = hashlib.sha256(req.read_bytes()).hexdigest()
        req.write_text(req.read_text().replace(old_intent, intent).replace("status: provisional", "status: approved"))
        arch.write_text(arch.read_text().replace("status: provisional", "status: approved").replace(old_intent, intent)
                        .replace(old_req, hashlib.sha256(req.read_bytes()).hexdigest()))

    def invoke(self, *, env_changes=None, edit_event=None, edit_api=None):
        event = self.f.event()
        event["number"] = event["pull_request"]["number"] = self.number
        if edit_event:
            edit_event(event)
        api = DocsApi(self.f, event)
        if edit_api:
            edit_api(api)
        event_path = Path(self.temp.name) / "event.json"
        event_path.write_text(json.dumps(event))
        root = self.f.root
        env = {"GITHUB_WORKSPACE": str(root), "GITHUB_ACTION_PATH": str(check.ACTION), "GITHUB_EVENT_PATH": str(event_path),
               "GOV_ACTION_REPOSITORY": "ForgingAlpha/.github", "GOV_ACTION_REF": "main", "GOV_SCOPES": self.scope_csv,
               "GITHUB_TOKEN": "fixture", "GITHUB_EVENT_NAME": "pull_request", "GITHUB_SERVER_URL": "https://github.com",
               "GITHUB_API_URL": "https://api.github.com", "GITHUB_REPOSITORY": self.f.repo["full_name"], "GITHUB_REPOSITORY_ID": "123",
               "GITHUB_BASE_REF": "dev", "GITHUB_HEAD_REF": "feature/definition", "GITHUB_REF": f"refs/pull/{self.number}/merge",
               "GITHUB_WORKFLOW_REF": f'{self.f.repo["full_name"]}/{check.CALLER}@refs/pull/{self.number}/merge'}
        with patch.dict(os.environ, env | (env_changes or {})), patch.object(baseline, "Api", return_value=api), \
                patch("sys.stdout", io.StringIO()) as out:
            check.main()
        return out.getvalue(), api

    def test_seed_then_second_docs_pr_then_approved_update_use_one_caller(self):
        first, api = self.invoke()
        self.assertIn("initial provisional definitions", first)
        self.assertEqual(len(api.reads), 4)
        command, cwd = self.checked.call_args.args
        self.assertEqual(command, ["node", str(ROOT / "actions/ci-markdown/scripts/lint_bootstrap.mjs")])
        self.assertEqual(cwd, ROOT)
        linted = json.loads(self.checked.call_args.kwargs["data"])
        self.assertIn("engine/docs/requirements.md", linted)
        self.assertNotIn(check.CALLER, linted)
        self.followup()
        self.f.write("engine/docs/notes.md", "# Supporting documents\n")
        self.f.write("engine/docs/facts/units.json", '{"units":["milliseconds"]}\n')
        self.f.commit()
        second, _ = self.invoke()
        self.assertIn("protected documentation update", second)
        self.assertIn("engine/docs/notes.md", json.loads(self.checked.call_args.kwargs["data"]))
        self.followup()
        self.promote(".")
        self.promote("engine")
        self.f.commit()
        third, _ = self.invoke()
        self.assertIn("protected documentation update", third)

    def test_first_status_must_be_provisional_and_scope_must_cover_entire_tree(self):
        self.write_caller(".")
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "unregistered governing scope|undeclared executable"):
            self.invoke(env_changes={"GOV_SCOPES": "."})
        self.write_caller(self.scope_csv)
        self.promote(".")
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "status"):
            self.invoke()
        self.checked.assert_not_called()

    def test_single_scope_seed_has_the_same_caller(self):
        self.f.git("rm", "-qr", "engine")
        self.write_caller(".")
        self.f.commit()
        self.assertIn("initial provisional definitions", self.invoke(env_changes={"GOV_SCOPES": "."})[0])

    def test_ordinary_requires_exact_base_and_head_callers_and_document_trees(self):
        self.followup()
        original = self.f.base
        for path, content in ((check.CALLER, self.template + b"# changed\n"), (".github/workflows/other.yml", "name: other\n"),
                              ("engine/src/service.rs", "fn main() {}\n"), ("docs/package.json", "{}\n"),
                              ("engine/docs/run.md", "# Executable\n")):
            with self.subTest(path=path):
                self.f.write(path, content)
                if path == "engine/docs/run.md":
                    (self.f.root / path).chmod(0o755)
                self.f.commit()
                with self.assertRaises(ValueError):
                    self.invoke()
                self.f.git("reset", "--hard", original)
        # Dropping a component, even with self-consistent head inputs, cannot
        # remove a protected scope from the base caller.
        self.f.git("rm", "-qr", "engine")
        self.write_caller(".")
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "canonical caller"):
            self.invoke(env_changes={"GOV_SCOPES": "."})
        self.f.git("reset", "--hard", original)
        self.f.write("service.py", "pass\n")
        self.f.commit()
        self.followup()
        self.f.git("rm", "-q", "service.py")
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "undeclared executable"):
            self.invoke()
        self.checked.assert_not_called()

    def test_ordinary_rejects_rewritten_identity_and_bad_upstream_digest(self):
        self.followup()
        original = self.f.base
        path = self.f.root / "engine/docs/architecture.md"
        before = path.read_text()
        path.write_text(before.replace("id: example/engine/architecture", "id: example/changed/architecture"))
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "protected governing identity"):
            self.invoke()
        self.f.git("reset", "--hard", original)
        path.write_text(before.replace("requirements_sha256: ", "requirements_sha256: 0"))
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "wrong governing digest"):
            self.invoke()
        self.checked.assert_not_called()

    def test_ineligible_or_stale_base_cannot_select_first_or_followup(self):
        self.f.git("rm", "-q", check.CALLER)
        self.f.commit()
        self.followup()
        self.write_caller(self.scope_csv)
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "sole ancestor root"):
            self.invoke()
        self.f.git("update-ref", "refs/remotes/origin/dev", self.saved_seed)
        with self.assertRaisesRegex(ValueError, "base checkout mismatch"):
            self.invoke()
        self.checked.assert_not_called()

    def test_fork_source_identity_action_scope_and_native_protection(self):
        for changes in ({"GOV_ACTION_REPOSITORY": "Other/.github"}, {"GOV_ACTION_REF": "feature/changes"},
                        {"GITHUB_ACTION_PATH": str(self.f.root)}, {"GITHUB_WORKSPACE": str(ROOT)},
                        {"GITHUB_WORKFLOW_REF": "ForgingAlpha/example/.github/workflows/another.yml@refs/heads/dev"},
                        {"GITHUB_BASE_REF": "main"}, {"GOV_SCOPES": "engine"}, {"GOV_SCOPES": ".,../other"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.invoke(env_changes=changes)
        for edit in (lambda e: e["pull_request"]["head"]["repo"].update(full_name="Other/fork"),
                     lambda e: e["pull_request"]["head"]["repo"].update(private=False),
                     lambda e: e["repository"].update(id=True)):
            with self.assertRaises(ValueError):
                self.invoke(edit_event=edit)
        for edit in (lambda a: a.live["head"].update(ref="some/other-branch"),
                     lambda a: a.branch.update(protected=False),
                     lambda a: a.effective[0]["parameters"].update(dismiss_stale_reviews_on_push=False),
                     lambda a: a.effective.pop(),
                     lambda a: a.effective[0]["parameters"]["required_reviewers"][0]["reviewer"].update(id=1)):
            with self.assertRaises(ValueError):
                self.invoke(edit_api=edit)
        self.checked.assert_not_called()

    def test_requires_current_protection_after_lint(self):
        def change_after_lint(api):
            self.checked.side_effect = lambda *args, **kwargs: api.branch.update(commit={"sha": self.f.head})
        with self.assertRaisesRegex(ValueError, "branch moved"):
            self.invoke(edit_api=change_after_lint)
        self.checked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
