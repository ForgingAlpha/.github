"""The enrollment preview prepares catalog changes without executing a consumer."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import four_section_fixture
from test_org_baseline import ApplicationFixture, Fixture, ROOT


spec = importlib.util.spec_from_file_location("preview", ROOT / "actions/ci-org-baseline/scripts/prepare_enrollment.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

# A second consumer keeps the real schema's nonempty-inventory invariant.
EXISTING = {"repository": "ForgingAlpha/example-docs", "repository_id": 71, "branches": ["dev"],
            "profile": "documentation-bootstrap", "producer": "bootstrap", "qualification_subject": {"kind": "none"},
            "release_route": {"kind": "not-applicable"}, "review_policy": {"kind": "qualified-team", "team_id": 23, "minimum_approvals": 1},
            "components": []}


class PreviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.f = ApplicationFixture(self.directory / "consumer")
        self.fields = preview.owner_fields(self.f.entry)
        self.catalog = {"schema_version": 2, "repositories": [copy.deepcopy(EXISTING)]}

    def result(self, fields=None):
        f = self.f
        return preview.preview(f.root, f.base, f.head, f.entry["repository"], f.entry["repository_id"],
                               self.catalog, fields, f.runtime, branch="dev")

    def test_new_astro_entry_is_exact_deterministic_and_preserves_existing_record(self):
        original = copy.deepcopy(self.catalog)
        expected = {"schema_version": 2, "repositories": [EXISTING, self.f.entry]}
        self.assertEqual(expected, self.result(self.fields))
        self.assertEqual(json.dumps(self.result(self.fields)), json.dumps(self.result(self.fields)))
        self.assertEqual(original, self.catalog)
        self.catalog = expected
        self.assertEqual(expected, self.result())

    def test_reads_commit_not_working_tree_and_never_executes_scripts(self):
        f = self.f
        marker = self.directory / "executed"
        package = json.loads((f.root / "package.json").read_text())
        package["scripts"]["test"] = "touch " + str(marker)
        f.write("package.json", json.dumps(package))
        f.commit()
        f.write("package.json", "invalid working copy")
        (f.root / "untracked").write_text("preserve")
        self.assertEqual(self.result(self.fields)["repositories"][-1], f.entry)
        self.assertFalse(marker.exists())
        self.assertEqual((f.root / "package.json").read_text(), "invalid working copy")
        self.assertEqual((f.root / "untracked").read_text(), "preserve")

    def test_missing_ownership_runtime_and_script_refuse(self):
        with self.assertRaisesRegex(ValueError, "owners must supply"):
            self.result()
        with self.assertRaisesRegex(ValueError, "review_policy"):
            self.result({k: v for k, v in self.fields.items() if k != "review_policy"})
        with self.assertRaisesRegex(ValueError, "Astro check roots"):
            self.result(dict(self.fields, astro_checks={}))
        field = copy.deepcopy(self.fields)
        field["astro_checks"]["."]["tests"]["scripts"].append("missing")
        with self.assertRaisesRegex(ValueError, "missing required npm script"):
            self.result(field)
        with self.assertRaisesRegex(ValueError, "positive integer ID"):
            self.result(dict(self.fields, repository_id=float(self.f.entry["repository_id"])))
        self.f.runtime["assignments"] = {}
        with self.assertRaises(ValueError):
            self.result(self.fields)

    def test_rejects_duplicate_identity_and_coverage_reduction(self):
        self.catalog["repositories"].append(self.f.entry)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            preview.preview(self.f.root, self.f.base, self.f.head, "ForgingAlpha/different-name",
                            self.f.entry["repository_id"], self.catalog, self.fields, self.f.runtime, branch="dev")
        field = copy.deepcopy(self.fields)
        field["astro_checks"]["."]["static_scripts"] = []
        with self.assertRaisesRegex(ValueError, "changed obligations"):
            self.result(field)
        (self.f.root / "package.json").unlink()
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "removed or moved"):
            self.result()

    def test_refuses_unsupported_package_and_missing_lock(self):
        self.f.write("other/package.json", '{"scripts":{}}')
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "unsupported npm component at other/package.json"):
            self.result(self.fields)
        (self.f.root / "other/package.json").unlink()
        (self.f.root / "package-lock.json").unlink()
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "missing tracked regular input: package-lock.json"):
            self.result(self.fields)

    def test_refuses_links_and_workspaces(self):
        (self.f.root / "unsafe").symlink_to("/missing/outside-consumer")
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "linked application input"):
            self.result(self.fields)
        (self.f.root / "unsafe").unlink()
        self.f.write("Cargo.toml", '[workspace]\nmembers=["crates/*"]')
        self.f.commit()
        with self.assertRaisesRegex(ValueError, "workspace.*native"):
            self.result(self.fields)

    def test_docs_requires_positive_complete_document_tree(self):
        f = Fixture(self.directory / "docs")
        fields = preview.owner_fields(EXISTING)
        repo, rid = self.f.entry["repository"], self.f.entry["repository_id"]
        fields.update(repository=repo, repository_id=rid)
        args = [f.root, f.base, f.head, repo, rid, self.catalog, fields, None]
        self.assertEqual(preview.preview(*args, branch="dev")["repositories"][-1]["profile"], "documentation-bootstrap")
        f.write("src/app.js", "export default 1")
        f.commit()
        args[2] = f.head
        with self.assertRaisesRegex(ValueError, "undeclared executable/config/application input"):
            preview.preview(*args, branch="dev")


    def test_supported_standalone_rust_and_mixed_shapes(self):
        for components in ((("rust", "."),), (("astro", "site"), ("rust", "service"))):
            with self.subTest(components=components):
                f = ApplicationFixture(self.directory / str(len(components)), kinds=components)
                crate = f.root / components[-1][1]
                (crate / "member/Cargo.toml").unlink()
                (crate / "Cargo.toml").write_text('[package]\nname="fixture"\nversion="1.0.0"\n')
                f.commit()
                # The fixture runtime is explicit. Both selected commits describe
                # standalone crates; workspace transition is outside the preview.
                outcome = preview.preview(f.root, f.head, f.head, f.entry["repository"], f.entry["repository_id"],
                                          self.catalog, preview.owner_fields(f.entry), f.runtime, branch="dev")
                self.assertEqual(outcome["repositories"][-1], f.entry)

    def test_cli_outputs_an_applicable_diff_then_an_explicit_noop(self):
        # A converted consumer emits governance diagnostics during validation.
        # Those receipts must never become part of a patch (including a no-op).
        f = self.f
        for path in preview.ci.REQUIRED:
            (f.root / path).unlink()
        f.write("README.md", four_section_fixture.README)
        f.write("AGENTS.md", preview.ci.readme_route().four_reader().NATIVE_POINTER)
        (f.root / "CLAUDE.md").symlink_to("AGENTS.md")
        f.write(four_section_fixture.MANIFEST, json.dumps(four_section_fixture.documents("dev")[1]))
        for path, data in four_section_fixture.details().items():
            f.write(path, data)
        f.commit()
        f.base = f.head
        checker = self.directory / "checking-source"
        checker.mkdir()
        for component in ("ci-org-baseline", "ci-alphaapps-policy", "ci-merge-flow", "ci-runtime-profile"):
            src = ROOT / "actions" / component
            shutil.copytree(src / "scripts", checker / "actions" / component / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "actions/ci-merge-flow/routes.json", checker / "actions/ci-merge-flow")
        catalog = checker / preview.CATALOG_PATH
        catalog.write_text(json.dumps(self.catalog, indent=2) + "\n")
        (checker / "runtime-profiles").mkdir()
        (checker / "runtime-profiles/catalog.json").write_text(json.dumps(self.f.runtime))
        git = ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Fixture", "-c", "commit.gpgsign=false",
               "-c", "core.hooksPath=/dev/null", "-C", str(checker)]
        for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "fixture"]):
            subprocess.run(git + args, check=True)
        fields = self.directory / "owner.json"
        fields.write_text(json.dumps(self.fields))
        command = [sys.executable, "-I", "-B", str(checker / "actions/ci-org-baseline/scripts/prepare_enrollment.py"),
                   "--consumer", str(self.f.root), "--repository", self.f.entry["repository"],
                   "--repository-id", str(self.f.entry["repository_id"]), "--branch", "dev",
                   "--base", self.f.base, "--head", self.f.head]
        first = subprocess.run(command + ["--owner-fields", str(fields)], capture_output=True, check=True)
        second = subprocess.run(command + ["--owner-fields", str(fields)], capture_output=True, check=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertTrue(first.stdout.startswith(b"--- a/"))
        self.assertIn(b"proposed", first.stderr)
        self.assertIn(b"Four-section digests", first.stderr)
        subprocess.run(git + ["apply", "-"], input=first.stdout, check=True)
        self.assertEqual(json.loads(catalog.read_text())["repositories"], [EXISTING, self.f.entry])
        subprocess.run(git + ["commit", "-qam", "accept fixture"], check=True)
        noop = subprocess.run(command, capture_output=True, check=True)
        self.assertEqual(noop.stdout, b"")
        self.assertIn(b"unchanged", noop.stderr)
