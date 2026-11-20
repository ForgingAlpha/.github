"""First definitions use an exact private registration and the staged document job."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_org_baseline import Fixture, baseline, successful_needs


def document(values, body):
    return "---\n" + "".join(f"{key}: {value}\n" for key, value in values.items()) + "---\n\n" + body


class FirstDefinition(Fixture):
    def __init__(self, root):
        self.root = root
        root.mkdir()
        self.repo = {"id": 123, "full_name": "ForgingAlpha/example-definition", "private": True,
                     "html_url": "https://github.com/ForgingAlpha/example-definition"}
        self.git("init", "-q", "-b", "dev")
        self.git("remote", "add", "origin", self.repo["html_url"])
        self.write("README.md", "# Example\n")
        self.commit()
        self.base = self.head
        self.git("update-ref", "refs/remotes/origin/dev", self.base)
        self.write_scope(".", prose=True)
        self.write_scope("engine", prose=False)
        self.write("engine/docs/facts/units.json", '{"units":["seconds"]}\n')
        self.write("PROJECT.md", "# Project\n")
        (root / "AGENTS.md").symlink_to("PROJECT.md")
        self.commit()

    def write_scope(self, scope, *, prose):
        prefix = "" if scope == "." else scope + "/"
        ids = {kind: f"example/{scope}/{kind}" for kind in ("intent", "requirements", "architecture")}
        metadata = {"status": "provisional", "id": ids["intent"]}
        readme = document(metadata, "# Example\n\n## Intent\n\nProvide a measured result.\n\n## Navigation\n\nRead the sources.\n")
        self.write(prefix + "README.md", readme)
        intent = baseline.policy.readme_intent(readme.encode()).sha256
        values = {"status": "provisional", "id": ids["requirements"], "intent": ids["intent"]}
        body = "# Requirements\n\nFollow the [scoped intent](../README.md#intent)"
        if prose:
            body += f" at SHA-256\n`{intent}`"
        else:
            values["intent_sha256"] = intent
        requirements = document(values, body + ".\n")
        self.write(prefix + "docs/requirements.md", requirements)
        req = hashlib.sha256(requirements.encode()).hexdigest()
        values = {**values, "id": ids["architecture"], "requirements": ids["requirements"]}
        body = "# Architecture\n\n"
        if prose:
            body += (f"Follow the [scoped intent](../README.md#intent) at SHA-256\n`{intent}` "
                     f"and [local requirements](requirements.md)\nat SHA-256 `{req}`.\n")
        else:
            values["requirements_sha256"] = req
            body += "Use an independent service.\n"
        self.write(prefix + "docs/architecture.md", document(values, body))

    def event(self):
        return {"number": 7, "repository": self.repo.copy(), "pull_request": {
            "number": 7, "state": "open",
            "head": {"ref": "feature/definition", "repo": self.repo.copy(), "sha": self.head},
            "base": {"ref": "dev", "repo": self.repo.copy(), "sha": self.base}}}


class PropertyApi:
    def __init__(self, fixture):
        self.fixture = fixture
        self.value = f"v1:7:{fixture.head}:41:.,engine"
        self.branch = {"name": "dev", "protected": True, "commit": {"sha": fixture.base}}
        self.live = fixture.event()["pull_request"]
        self.effective = [{"type": "pull_request", "parameters": {
            "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
            "required_reviewers": [{"reviewer": {"type": "Team", "id": 41}, "minimum_approvals": 1, "file_patterns": ["*"]}]}},
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "CI"}]}}]

    def get(self, path):
        base = "/repos/" + self.fixture.repo["full_name"]
        if path == base + "/properties/values":
            return [{"property_name": "first_definition", "value": self.value}]
        if path == base + "/pulls/7":
            return copy.deepcopy(self.live)
        if path == base + "/branches/dev":
            return copy.deepcopy(self.branch)
        raise AssertionError("unexpected API target")

    def rules(self, repository, branch):
        assert (repository, branch) == (self.fixture.repo["full_name"], "dev")
        return copy.deepcopy(self.effective)


class FirstDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = FirstDefinition(Path(self.temp.name) / "consumer")
        self.api = PropertyApi(self.f)
        env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/7/merge", "GITHUB_BASE_REF": "dev",
               "GITHUB_HEAD_REF": "feature/definition", "GITHUB_REPOSITORY": self.f.repo["full_name"],
               "GITHUB_REPOSITORY_ID": "123", "GITHUB_API_URL": "https://api.github.com",
               "GITHUB_SERVER_URL": "https://github.com", "GITHUB_TOKEN": "synthetic"}
        self.enterContext(patch.dict(os.environ, env))
        self.authenticate = self.enterContext(patch.object(baseline, "Api", return_value=self.api))
        self.lint = self.enterContext(patch.object(baseline, "checked"))
        self.outputs = self.enterContext(patch.object(baseline, "emit_outputs"))
        self.entries = baseline.catalog(baseline.decode((baseline.SOURCE / "actions/ci-org-baseline/enrollment.json").read_bytes()))

    def stage(self, stage="admit", event=None):
        baseline.staged_main(SimpleNamespace(stage=stage), self.f.root, event or self.f.event(), self.entries, "a" * 40)

    def test_staged_success_and_complete_data_only_lint(self):
        self.stage()
        job = self.outputs.call_args.args[0]
        plan = job["plan"]
        self.assertEqual((job["result_name"], job["profile"], plan["producer"]), ("CI", "documentation-bootstrap", "first-definition"))
        self.assertEqual(plan["registration"]["scopes"], [".", "engine"])
        self.assertEqual(plan["registration"]["team_id"], 41)
        self.assertEqual(plan["tree"], self.f.git("rev-parse", "HEAD^{tree}").strip())
        command, cwd = self.lint.call_args.args
        self.assertEqual((command, cwd), (["node", str(baseline.SOURCE / "actions/ci-markdown/scripts/lint_bootstrap.mjs")], baseline.SOURCE))
        self.assertEqual(set(json.loads(self.lint.call_args.kwargs["data"])),
                         {p.relative_to(self.f.root).as_posix() for p in self.f.root.rglob("*.md") if not p.is_symlink()})
        with patch.dict(os.environ, {"BASELINE_NEEDS": json.dumps(successful_needs(plan))}), patch("sys.stdout", io.StringIO()) as logged:
            self.stage("finalize")
        self.assertEqual(json.loads(logged.getvalue())["plan_sha256"], baseline.plan_digest(plan))
        for stage in ("static", "tests", "install", "preflight"):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                self.stage(stage)
        self.assertEqual(self.lint.call_count, 1)

    def test_finalize_requires_unchanged_registration_live_subject_and_review_rules(self):
        self.stage()
        plan = self.outputs.call_args.args[0]["plan"]
        os.environ["BASELINE_NEEDS"] = json.dumps(successful_needs(plan))
        # Both authorizations could independently succeed, but are not the same admission.
        reviewer = self.api.effective[0]["parameters"]["required_reviewers"][0]
        self.api.effective[0]["parameters"]["required_reviewers"].append(dict(reviewer, reviewer={"type": "Team", "id": 42}))
        for value in (None, self.api.value.replace(":41:", ":42:"), self.api.value.replace(".,engine", "engine,.")):
            with self.subTest(property=value), patch.object(self.api, "value", value), self.assertRaises(ValueError):
                self.stage("finalize")
        for patcher in (
            patch.object(self.api, "effective", self.api.effective[:1]),
            patch.object(self.api, "effective", self.api.effective[1:]),
            patch.dict(self.api.branch, {"protected": False}),
            patch.dict(self.api.branch, {"commit": {"sha": self.f.head}}),
            patch.dict(self.api.live, {"state": "closed"}),
            patch.dict(self.api.live["head"], {"sha": self.f.base}),
            patch.dict(self.api.live["base"]["repo"], {"private": False}),
        ):
            with patcher, self.assertRaises(ValueError):
                self.stage("finalize")

    def test_revalidation_after_lint_and_lint_failure_prevent_output(self):
        self.lint.side_effect = lambda *a, **kw: setattr(self.api, "value", None)
        with self.assertRaises(ValueError):
            self.stage()
        self.api.value = f"v1:7:{self.f.head}:41:.,engine"
        self.lint.side_effect = ValueError("Markdown lint failed")
        with self.assertRaisesRegex(ValueError, "Markdown lint failed"):
            self.stage()
        self.outputs.assert_not_called()

    def test_malformed_or_enrolled_identity_never_reads_property(self):
        for path, value in [
            (("repository", "full_name"), "ForgingAlpha/.."),
            (("repository", "full_name"), "ForgingAlpha/x?y"),
            (("repository", "full_name"), "ForgingAlpha/x/y"),
            (("repository", "full_name"), self.entries[0]["repository"].swapcase()),
            (("repository", "id"), self.entries[0]["repository_id"]),
            (("repository", "private"), 1), (("repository", "id"), True),
            (("pull_request", "head", "repo", "id"), True), (("pull_request", "head", "repo", "full_name"), "Other/fork"),
            (("pull_request", "base", "ref"), "main"), (("pull_request", "number"), True),
            (("pull_request", "head", "sha"), self.f.base), (("number",), True),
        ]:
            with self.subTest(path=path, value=value):
                event = self.f.event()
                obj = event
                for key in path[:-1]:
                    obj = obj[key]
                obj[path[-1]] = value
                with self.assertRaises(ValueError):
                    self.stage(event=event)
        self.authenticate.assert_not_called()

    def test_only_exact_registration_and_matching_ci_app(self):
        def read(*values):
            rows = [{"property_name": "first_definition", "value": value} for value in values]
            return baseline.first_definition.registration(rows, 7, self.f.head)
        value = self.api.value
        for values in ([], [value, value], [value.replace(":7:", ":6:")], [value.replace(self.f.head, self.f.base)],
                       [value.replace(":41:", ":0:")], [value.replace("engine", "..")], [value.replace("engine", ".")],
                       [value.replace("engine", "some/dir")], [value + "a" * 75], [value + "é"], [[value]]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                read(*values)
        check = self.api.effective[1]["parameters"]["required_status_checks"][0]
        for app in (True, 99, "15368"):
            with self.subTest(app=app), patch.dict(check, {"integration_id": app}), self.assertRaises(ValueError):
                self.stage()
        with patch.dict(check, {"integration_id": 15368}):
            self.stage()

    def test_new_seed_must_be_single_readme_and_only_root_of_the_head(self):
        tree = self.f.git("rev-parse", self.f.base + "^{tree}").strip()
        alternate = self.f.git("commit-tree", tree, "-m", "independent root").strip()
        joined = self.f.git("commit-tree", tree, "-p", self.f.head, "-p", alternate, "-m", "join").strip()
        with self.assertRaises(ValueError):
            baseline.verify_seed(self.f.root, self.f.base, joined)
        with self.assertRaises(ValueError):
            baseline.verify_seed(self.f.root, self.f.head, joined)
        nonseed = self.f.git("commit-tree", self.f.git("rev-parse", "HEAD^{tree}").strip(), "-m", "many files").strip()
        descendant = self.f.git("commit-tree", tree, "-p", nonseed, "-m", "definition").strip()
        with self.assertRaisesRegex(ValueError, "only regular README"):
            baseline.verify_seed(self.f.root, nonseed, descendant)

    def test_entire_tree_is_bounded_to_documents_and_inert_scoped_objects(self):
        original = self.f.head
        for name, data in ((".gitignore", "*.tmp\n"), ("engine/.hidden/info.md", "# Hidden\n"),
                           ("engine/docs/package.json", "{}"), ("engine/docs/tsconfig.json", "{}"),
                           ("other/docs/info.json", "{}"), ("register.json", "{}"), ("docs/data.json", "[1]"),
                           ("docs/data.json", '{"x":1,"x":2}'), ("docs/data.json", '{"x":NaN}'),
                           ("docs/run.sh", "exit 1\n"), ("legacy/docs/intent.md", "# Alternate\n"),
                           ("extra/docs/architecture.md", "# Another\n"), ("extra/README.md", "# Extra\n\n## Intent\n\nExtra.\n")):
            with self.subTest(path=name, data=data):
                self.f.write(name, data)
                self.f.commit()
                with self.assertRaises(ValueError):
                    baseline.admit_tree(self.f.root, self.f.head, definition_scopes=[".", "engine"])
                self.f.git("reset", "--hard", original)
        (self.f.root / "docs/requirements.md").chmod(0o755)
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "non-executable"):
            baseline.admit_tree(self.f.root, self.f.head, definition_scopes=[".", "engine"])
        self.f.git("reset", "--hard", original)
        (self.f.root / "PROJECT.md").unlink()
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "projection target"):
            baseline.admit_tree(self.f.root, self.f.head, definition_scopes=[".", "engine"])

    def test_all_scopes_status_ids_links_and_both_digest_forms_are_required(self):
        texts = baseline.admit_tree(self.f.root, self.f.head, definition_scopes=[".", "engine"])
        for scopes in (["."], [".", "engine", "extra"]):
            with self.subTest(scopes=scopes), self.assertRaises(ValueError):
                baseline.first_definition.check_documents(texts, scopes, baseline.policy)
        self.assertNotIn("AGENTS.md", texts)
        for path, old, new in (
            ("README.md", "status: provisional", "status: approved"),
            ("engine/README.md", "Provide a measured result", "Provide a different result"),
            ("docs/requirements.md", "../README.md#intent", "../other.md#intent"),
            ("docs/architecture.md", "](requirements.md)", "](other.md)"),
            ("docs/architecture.md", "requirements: example/./requirements", "requirements: other"),
            ("engine/docs/architecture.md", "requirements_sha256:", "old_binding:"),
            ("engine/docs/architecture.md", "id: example/engine/architecture", "id: example/./intent"),
            ("engine/docs/requirements.md", "../README.md#intent", "../README.md#other"),
            ("engine/docs/requirements.md", "status: provisional", "status: current"),
        ):
            with self.subTest(path=path, old=old):
                current = texts[path].replace(old, new)
                self.assertNotEqual(current, texts[path])
                with self.assertRaises(ValueError):
                    baseline.first_definition.check_documents(texts | {path: current}, [".", "engine"], baseline.policy)


if __name__ == "__main__":
    unittest.main()
