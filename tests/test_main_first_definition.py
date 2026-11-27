"""Protected main first-definition admission from the operator's property to the final CI receipt."""

import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import four_section_fixture as four
from test_first_definition import FirstDefinition, PropertyApi
from test_org_baseline import baseline, successful_needs


class MainDefinition(FirstDefinition):
    branch = "main"

    def write_candidate(self):
        front = "---\nid: urn:example:intent\nstatus: approved\n---\n"
        sections = [
            "## Intent\n\nPreserve observations.\n",
            "## Requirements\n\nRetain every correction.\n",
            "## Architecture\n\nThe log owns the history.\n",
            "## Local Instructions\n\nReview the changes.\n",
        ]
        self.write("README.md", front + "# Example\n\n" + "\n".join(sections))
        _, self.manifest = four.documents()
        rows = self.manifest["sources"] = self.manifest["sources"][:3]
        hashes = [four.sha(data.encode()) for data in (front + sections[0], *sections[1:])]
        for index, row in enumerate(rows):
            row.update(sha256=hashes[index], upstream=[
                {"path": four.TRIO[i], "sha256": hashes[i]} for i in range(index)])
        self.manifest["local_instructions"]["sha256"] = hashes[3]
        self.write(four.MANIFEST, json.dumps(self.manifest))
        for path in ("AGENTS.md", "CLAUDE.md"):
            self.write(path, baseline.readme_route().four_reader().NATIVE_POINTER)


def property_value(repo, base, head, pr=7, team=41, branch="main", scope="."):
    # The operator and verifier must interoperate with this language-independent format.
    subject = ["v2", repo, branch, base, head, pr, scope, team]
    data = json.dumps(subject, separators=(",", ":")).encode("ascii")
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")
    return f"v2:{team}:{digest}"


class MainFirstDefinitionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        self.f = MainDefinition(directory / "consumer")
        self.api = PropertyApi(self.f)
        self.api.effective[1]["parameters"]["strict_required_status_checks_policy"] = True
        self.api.effective.append({"type": "code_scanning", "parameters": {"code_scanning_tools": [
            {"tool": "CodeQL", "security_alerts_threshold": "high_or_higher", "alerts_threshold": "errors"}]}})
        # Independent branch protections can add an ordinary review rule alongside the qualified team.
        self.api.effective.append({"type": "pull_request", "parameters": {
            "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True, "required_reviewers": []}})
        self.refresh_subject()
        self.output = directory / "github-output"
        self.source = "a" * 40
        env = {"GITHUB_REPOSITORY": self.f.repo["full_name"], "GITHUB_REPOSITORY_ID": "123",
               "GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/7/merge",
               "GITHUB_BASE_REF": "main", "GITHUB_HEAD_REF": "feature/definition",
               "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
               "GITHUB_TOKEN": "synthetic", "GITHUB_OUTPUT": str(self.output)}
        self.enterContext(patch.dict(os.environ, env))
        self.enterContext(patch.object(baseline, "Api", return_value=self.api))
        self.command = self.enterContext(patch.object(baseline, "checked"))

    def refresh_subject(self):
        self.api.value = property_value(self.f.repo["id"], self.f.base, self.f.head)
        self.api.live = self.f.event()["pull_request"]
        self.api.branch["commit"]["sha"] = self.f.base

    def stage(self, stage="admit", *, event=None, entries=()):
        baseline.staged_main(SimpleNamespace(stage=stage), self.f.root, event or self.f.event(), entries, self.source)

    def admission(self):
        self.stage()
        job = dict(line.split("=", 1) for line in self.output.read_text().splitlines())
        self.assertEqual((job["result_name"], job["producer"], job["profile"]),
                         ("CI", "first-definition", "documentation-bootstrap"))
        return json.loads(job["plan"])

    def commit_and_expect_refusal(self):
        self.f.commit()
        self.refresh_subject()
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.output.exists())

    def test_operator_known_answer(self):
        command = [sys.executable, str(baseline.SOURCE / "actions/ci-org-baseline/scripts/first_definition.py"),
                   "main-registration", "--repository-id", "123", "--base", "1" * 40, "--head", "2" * 40,
                   "--pr", "7", "--team-id", "41"]
        self.assertEqual(subprocess.check_output(command, text=True),
                         "v2:41:lhlk1egaABdSztDIIYK93CU-LeA8a3bc5NbjlaaqOVw\n")

    def test_result_binds_git_subject_and_lints_each_markdown_blob(self):
        plan = self.admission()
        self.assertEqual((plan["base"], plan["head"], plan["source_sha"], plan["repository_id"], plan["pr"],
                          plan["branch"], plan["tree"]), (self.f.base, self.f.head, self.source, 123, 7, "main",
                                                          self.f.git("rev-parse", "HEAD^{tree}").strip()))
        self.assertEqual(plan["registration"], {"scopes": ["."], "team_id": 41,
                                               "registration_sha256": four.sha(self.api.value.encode("ascii"))})
        self.assertEqual((plan["components"], plan["required_jobs"]), ([], ["baseline"]))
        self.command.assert_called_once()
        args, kwargs = self.command.call_args
        self.assertEqual(args, (["node", str(baseline.SOURCE / "actions/ci-markdown/scripts/lint_bootstrap.mjs")],
                                baseline.SOURCE))
        self.assertEqual(json.loads(kwargs["data"]), {path: self.f.git("show", self.f.head + ":" + path)
                                                     for path in ("README.md", "AGENTS.md", "CLAUDE.md")})
        with patch.dict(os.environ, {"BASELINE_NEEDS": json.dumps(successful_needs(plan))}), patch(
                "sys.stdout", new_callable=io.StringIO) as out:
            self.stage("finalize")
        self.assertEqual(json.loads(out.getvalue()), {"producer": "first-definition", "result": "success",
                         "head": self.f.head, "base": self.f.base, "source_sha": self.source,
                         "plan_sha256": baseline.plan_digest(plan)})
        for stage in ("preflight", "install", "static", "tests"):
            with self.subTest(stage=stage), patch.dict(os.environ, {"BASELINE_PLAN": json.dumps(plan)}), self.assertRaises(ValueError):
                self.stage(stage)
        self.assertEqual(self.command.call_count, 1)

    def test_property_is_required_unique_and_bound_to_full_subject(self):
        subject = dict(repo=123, base=self.f.base, head=self.f.head, pr=7, team=41, branch="main", scope=".")
        for key, stale in dict(repo=124, base="3" * 40, head="4" * 40, pr=8, team=42, scope="docs", branch="dev").items():
            value = property_value(**(subject | {key: stale}))
            with self.subTest(key=key), patch.object(self.api, "value", value), self.assertRaises(ValueError):
                self.stage()
        for values in ([], [None], [self.api.value] * 2, [f"v1:7:{self.f.head}:41:."], [self.api.value + "="]):
            rows = [{"property_name": "first_definition", "value": v} for v in values]
            get = self.api.get
            with self.subTest(properties=values), patch.object(
                    self.api, "get", side_effect=lambda path: rows if path.endswith("/properties/values") else get(path)
            ), self.assertRaises(ValueError):
                self.stage()
        self.command.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_main_registration_cannot_enroll_dev(self):
        dev = FirstDefinition(self.f.root.parent / "dev-consumer")
        api = PropertyApi(dev)
        api.value = property_value(dev.repo["id"], dev.base, dev.head)
        with patch.dict(os.environ, {"GITHUB_BASE_REF": "dev"}), patch.object(
                baseline, "Api", return_value=api), self.assertRaises(ValueError):
            baseline.staged_main(SimpleNamespace(stage="admit"), dev.root, dev.event(), [], self.source)
        self.command.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_event_and_existing_enrollment_cannot_claim_first_definition(self):
        for head_ref in ("dev", "staging", "main"):
            event = self.f.event()
            event["pull_request"]["head"]["ref"] = head_ref
            with self.subTest(head=head_ref), patch.dict(os.environ, {"GITHUB_HEAD_REF": head_ref}), patch.dict(
                    self.api.live["head"], {"ref": head_ref}), self.assertRaises(ValueError):
                self.stage(event=event)
        for field, value in (("id", 124), ("full_name", "ForgingAlpha/another-example"), ("private", False)):
            event = self.f.event()
            event["pull_request"]["head"]["repo"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.stage(event=event)
        entry = {"repository": self.f.repo["full_name"], "repository_id": 123, "branches": ["dev"]}
        for entries in ([entry], [entry | {"repository_id": 124}],
                        [entry | {"repository": "ForgingAlpha/another-example"}],
                        [entry | {"branches": ["main"]}] * 2):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.stage(entries=entries)
        self.command.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_only_four_regular_files_and_exact_pointer_bytes(self):
        original = self.f.head
        for path in ("extra.md", "docs/intent.md", "app.py"):
            with self.subTest(extra=path):
                self.f.write(path, "# Extra\n")
                self.commit_and_expect_refusal()
                self.f.git("reset", "--hard", original)
        for name in ("README.md", four.MANIFEST, "AGENTS.md", "CLAUDE.md"):
            path = self.f.root / name
            for mode in ("absent", "executable", "symlink"):
                with self.subTest(path=name, mode=mode):
                    if mode == "executable":
                        path.chmod(0o755)
                    else:
                        path.unlink()
                        if mode == "symlink":
                            path.symlink_to("CLAUDE.md" if name == "AGENTS.md" else "AGENTS.md")
                    self.commit_and_expect_refusal()
                    self.f.git("reset", "--hard", original)
        for path in ("AGENTS.md", "CLAUDE.md"):
            self.f.write(path, "# Use other instructions\n")
            with self.subTest(pointer=path):
                self.commit_and_expect_refusal()
            self.f.git("reset", "--hard", original)

    def test_selected_metadata_sources_digests_and_upstream_edges(self):
        req = ("source_metadata", four.TRIO[1])
        for path, value in (
            ((four.KEY,), {"main": ["."], "dev": ["."]}),
            ((*req, four.KEY), {"main": [".", "service"]}),
            ((*req, "readme_intent_scopes"), {"dev": ["."]}),
            (("sources", 1, "id"), "urn:example:other"),
            (("sources", 2, "upstream", 1, "sha256"), "0" * 64),
            (("sources", 2, "upstream", 0, "path"), four.TRIO[1]),
            (("source_metadata", four.TRIO[2], "requirements"), "urn:example:wrong"),
            (("local_instructions", "sha256"), "0" * 64),
        ):
            with self.subTest(path=path):
                manifest = copy.deepcopy(self.f.manifest)
                obj = manifest
                for key in path[:-1]:
                    obj = obj[key]
                obj[path[-1]] = value
                self.f.write(four.MANIFEST, json.dumps(manifest))
                self.commit_and_expect_refusal()
        self.f.write(four.MANIFEST, json.dumps(self.f.manifest))
        readme = (self.f.root / "README.md").read_text()
        for term in ("Preserve", "Retain", "The log", "Review"):
            with self.subTest(section=term):
                self.f.write("README.md", readme.replace(term, "Change", 1))
                self.commit_and_expect_refusal()

    def test_seed_must_be_sole_readme_only_parentless_root_with_complete_history(self):
        f = self.f
        (f.root / ".git/shallow").write_text(f.head + "\n")
        with self.assertRaises(ValueError):
            self.stage()
        (f.root / ".git/shallow").unlink()
        seed_tree = f.git("rev-parse", f.base + "^{tree}").strip()
        head_tree = f.git("rev-parse", f.head + "^{tree}").strip()
        second_root = f.git("commit-tree", seed_tree, "-m", "other root").strip()
        child_seed = f.git("commit-tree", seed_tree, "-p", f.base, "-m", "later README").strip()
        extra_files = f.git("commit-tree", head_tree, "-m", "seed with extra files").strip()
        for base, parents in [(f.base, [f.head, second_root]), (child_seed, [child_seed]), (extra_files, [extra_files])]:
            with self.subTest(base=base, parents=parents):
                head = f.git("commit-tree", head_tree, *(arg for p in parents for arg in ("-p", p)),
                             "-m", "amended candidate").strip()
                f.git("checkout", "--detach", head)
                f.git("update-ref", "refs/remotes/origin/main", base)
                f.base, f.head = base, head
                self.refresh_subject()
                with self.assertRaises(ValueError):
                    self.stage()
        self.command.assert_not_called()

    def test_finalization_requires_current_subject_team_registration_and_native_rules(self):
        plan = self.admission()
        review, checks, scanning, _ = [rule["parameters"] for rule in self.api.effective]
        team = review["required_reviewers"][0]
        tool = scanning["code_scanning_tools"][0]
        # A different registered team could independently qualify a new plan.
        alternate = dict(team, reviewer={"id": 42, "type": "Team"})
        review["required_reviewers"].append(alternate)
        with patch.dict(os.environ, {"BASELINE_NEEDS": json.dumps(successful_needs(plan))}):
            for change in (
                patch.object(self.api, "value", None),
                patch.object(self.api, "value", property_value(123, self.f.base, self.f.head, team=42)),
                patch.dict(self.api.live, {"state": "closed"}),
                patch.dict(self.api.live["head"], {"sha": self.f.base}),
                patch.dict(self.api.branch, {"protected": False}),
                patch.dict(self.api.branch["commit"], {"sha": self.f.head}),
                patch.dict(review, {"required_reviewers": []}),
                patch.dict(team, {"minimum_approvals": 0}),
                patch.dict(team, {"file_patterns": ["*", "!docs/**"]}),
                patch.dict(checks, {"required_status_checks": []}),
                patch.dict(checks, {"strict_required_status_checks_policy": False}),
                patch.dict(checks["required_status_checks"][0], {"integration_id": 99}),
                patch.dict(scanning, {"code_scanning_tools": []}),
                patch.dict(tool, {"tool": "Other"}),
                patch.dict(tool, {"security_alerts_threshold": "critical"}),
                patch.dict(tool, {"alerts_threshold": "none"}),
            ):
                with self.subTest(change=change), change, patch("sys.stdout", new_callable=io.StringIO) as out:
                    with self.assertRaises(ValueError):
                        self.stage("finalize")
                    self.assertEqual(out.getvalue(), "")

    def test_rule_readback_after_aggregation_can_withdraw_final_success(self):
        plan = self.admission()
        later_rules = copy.deepcopy(self.api.effective)
        for rule in later_rules:
            if rule["type"] == "pull_request":
                rule["parameters"]["dismiss_stale_reviews_on_push"] = False
        with patch.dict(os.environ, {"BASELINE_NEEDS": json.dumps(successful_needs(plan))}), patch.object(
                self.api, "rules", side_effect=[self.api.effective, later_rules]), patch(
                "sys.stdout", new_callable=io.StringIO) as out:
            with self.assertRaises(ValueError):
                self.stage("finalize")
        self.assertEqual(out.getvalue(), "")

    def test_lint_failure_or_registration_withdrawal_during_lint_prevents_admission_output(self):
        with self.assertRaisesRegex(ValueError, "Markdown rejected"):
            self.command.side_effect = ValueError("Markdown rejected")
            self.stage()
        self.command.side_effect = lambda *args, **kw: setattr(self.api, "value", None)
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
