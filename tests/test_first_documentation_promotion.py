"""Exercise first-promotion admission on real Git trees with simulated provider evidence."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import four_section_fixture as four
import test_org_baseline as org


baseline = org.baseline
DUAL = {"dev": ["."], "main": ["."]}


class FirstDocumentationPromotion(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        legacy = org.ENTRY | {"repository": "ForgingAlpha/example-docs-site", "repository_id": 73611}
        self.enterContext(patch.object(org, "ENTRY", legacy))
        modern = {k: legacy[k] for k in ("repository", "repository_id", "branches", "profile")}
        modern.update(producer="bootstrap", qualification_subject={"kind": "none"},
                      release_route={"kind": "not-applicable"}, components=[],
                      review_policy={"kind": "qualified-team", "team_id": legacy["team_id"],
                                     "minimum_approvals": 1})
        [self.entry] = baseline.catalog({"schema_version": 2, "repositories": [modern]})
        self.route_file = self.root / "routes.json"
        self.routes = {route: [] for route in baseline.merge_flow().ROUTES}
        self.routes["direct"] = [legacy["repository_id"]]
        self.route_file.write_text(json.dumps(self.routes))
        self.enterContext(patch.object(baseline.merge_flow(), "ACTION", self.root))
        self.f = org.Fixture(self.root / "consumer", branch="main", empty_main=True)
        self.legacy = self.f.head
        for name in baseline.REQUIRED:
            (self.f.root / name).unlink()
        self.f.write("AGENTS.md", baseline.readme_route().four_reader().NATIVE_POINTER)
        (self.f.root / "CLAUDE.md").symlink_to("AGENTS.md")
        self.f.write("README.md", four.README)
        for path, data in four.details().items():
            self.f.write(path, data)
        _, self.manifest = four.documents("dev")
        self.manifest[four.KEY] = DUAL
        self.manifest["source_metadata"][four.TRIO[1]][four.KEY] = DUAL
        self.write_manifest(self.manifest)
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_REPOSITORY": legacy["repository"], "GITHUB_REPOSITORY_ID": str(legacy["repository_id"]),
            "GITHUB_TOKEN": "fixture-only", "GITHUB_OUTPUT": str(self.root / "output")
        }))
        self.source = "a" * 40

    def write_manifest(self, value):
        self.f.write(four.MANIFEST, json.dumps(value))
        self.f.commit()

    def plan(self, entry=None):
        return baseline.make_plan(self.f.root, self.f.event(), entry or self.entry, self.source)

    def stage(self, stage, api):
        with patch.object(baseline, "Api", return_value=api):
            return baseline.staged_main(SimpleNamespace(stage=stage), self.f.root, self.f.event(), [self.entry], self.source)

    def test_first_release_and_following_ordinary_release(self):
        f = self.f
        plan = self.plan()
        self.assertEqual(plan["tree"], f.git("rev-parse", "HEAD^{tree}").strip())
        self.assertEqual(plan["required_jobs"], ["baseline"])
        api = org.FakeApi(f)
        with patch.object(baseline, "lint_documents") as lint:
            self.stage("admit", api)
            self.assertIn("README.md", lint.call_args.args[1])
            receipt = baseline.run(f.root, f.event(), [self.entry], api)
            self.assertEqual(receipt["tree"], plan["tree"])
        needs = json.dumps(org.successful_needs(plan))
        with patch.dict(os.environ, {"BASELINE_NEEDS": needs}), patch.object(sys, "stdout", io.StringIO()) as out:
            self.stage("finalize", api)
            self.assertEqual(json.loads(out.getvalue())["tree"], plan["tree"])
        # The merging human chooses and qualifies the hosted method. Model a
        # two-parent merge so ordinary dev changes have their real merge base.
        released_dev = f.head
        merged = f.git("commit-tree", plan["tree"], "-p", f.base, "-p", released_dev, "-m", "first release").strip()
        self.assertEqual(f.git("rev-parse", merged + "^2").strip(), released_dev)
        f.base = merged
        f.git("update-ref", "refs/remotes/origin/main", merged)
        f.write("docs/next.md", "# Next release\n")
        f.commit()
        self.assertEqual(f.git("merge-base", merged, f.head).strip(), released_dev)
        with patch.object(baseline, "lint_documents"), patch.object(
                baseline.readme_route(), "check_site_snapshot", side_effect=AssertionError("first release reused")):
            self.stage("admit", org.FakeApi(f))
        self.assertEqual(f.git("merge-tree", "--write-tree", merged, f.head).strip(), self.plan()["tree"])

    def test_empty_main_refuses_legacy_layout_schema_and_absent_enrollment(self):
        with self.assertRaisesRegex(ValueError, "schema-2"):
            self.plan(org.ENTRY)
        denied = self.entry | {"branches": ["dev"]}
        with self.assertRaisesRegex(ValueError, "enroll|unknown"):
            baseline.event_subject(self.f.root, self.f.event(), [denied])
        self.f.git("checkout", "-q", "--detach", self.legacy)
        self.f.head = self.legacy
        with self.assertRaisesRegex(ValueError, "root README selection"):
            self.plan()

    def test_other_route_and_extra_history_roots_refused(self):
        self.routes["staged"] = self.routes.pop("direct")
        self.routes["direct"] = []
        self.route_file.write_text(json.dumps(self.routes))
        with self.assertRaisesRegex(ValueError, "direct"):
            self.plan()
        self.routes["direct"] = self.routes["staged"]
        self.routes["staged"] = []
        self.route_file.write_text(json.dumps(self.routes))
        f = self.f
        tree = f.git("rev-parse", "HEAD^{tree}").strip()
        other_root = f.git("commit-tree", tree, "-m", "other root").strip()
        first = f.head
        for label, parents in (("unrelated", [other_root]), ("multiple", [first, other_root])):
            commit = f.git("commit-tree", tree, *(arg for parent in parents for arg in ("-p", parent)), "-m", label).strip()
            f.git("checkout", "-q", "--detach", commit)
            f.head = commit
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "sole parentless root"):
                self.plan()
        empty = f.git("rev-parse", f.base + "^{tree}").strip()
        f.base = f.git("commit-tree", empty, "-p", first, "-m", "main emptied again").strip()
        with self.assertRaisesRegex(ValueError, "sole parentless root"):
            self.plan()

    def test_incomplete_history_and_wrong_instruction_pointer_refused(self):
        f = self.f
        # Git treats the listed revision as a history boundary even with its objects present.
        shallow = f.root / ".git/shallow"
        shallow.write_text(f.head + "\n")
        with self.assertRaisesRegex(ValueError, "complete dev history"):
            self.plan()
        shallow.unlink()
        f.write("AGENTS.md", "# Other instructions\n")
        f.commit()
        with self.assertRaisesRegex(ValueError, "native README instruction pointer"):
            self.plan()

    def test_both_scope_records_and_approved_bindings_required(self):
        for label in ("manifest", "metadata", "digest", "status", "upstream"):
            candidate = copy.deepcopy(self.manifest)
            if label == "manifest":
                candidate[four.KEY] = {"dev": ["."]}
            elif label == "metadata":
                candidate["source_metadata"][four.TRIO[1]][four.KEY] = {"dev": ["."]}
            elif label == "digest":
                candidate["sources"][1]["sha256"] = "e" * 64
            elif label == "status":
                candidate["source_metadata"][four.TRIO[1]]["status"] = "provisional"
            else:
                candidate["sources"][1]["upstream"] = []
            self.write_manifest(candidate)
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.plan()

    def test_whole_tree_and_computed_integration(self):
        for path in ("docs/other/governing-source-bindings.json", "docs/intent.md", "site/package.json"):
            self.f.write(path, "{}\n")
            self.f.commit()
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.plan()
            (self.f.root / path).unlink()
        self.f.commit()
        real_git = baseline.git

        def mismatched_tree(root, *args, **kwargs):
            if args[:2] == ("merge-tree", "--write-tree"):
                return b"f" * 40 + b"\n"
            return real_git(root, *args, **kwargs)

        with patch.object(baseline, "git", side_effect=mismatched_tree), self.assertRaisesRegex(ValueError, "integration"):
            self.plan()

    def test_finalization_requires_fresh_pr_protected_tips_and_main_team(self):
        f = self.f
        with patch.object(baseline, "lint_documents"):
            self.stage("admit", org.FakeApi(f))
        needs = json.dumps(org.successful_needs(self.plan()))
        for change in ("pr", "dev", "main", "team", "unavailable"):
            api = org.FakeApi(f)
            if change == "pr":
                api.live["head"]["sha"] = "d" * 40
            elif change == "team":
                api.evidence = []
            elif change == "unavailable":
                def unavailable(repository, target):
                    self.assertEqual(target, "main")
                    raise ValueError("missing rule evidence")
                api.rules = unavailable
            else:
                actual_get = api.get

                def moved(path):
                    record = actual_get(path)
                    if path.endswith("/branches/" + change):
                        record["commit"]["sha"] = "d" * 40
                    return record

                api.get = moved
            with self.subTest(change=change), patch.dict(os.environ, {"BASELINE_NEEDS": needs}), self.assertRaises(ValueError):
                self.stage("finalize", api)
