"""Exercise the remote policy CLI used by ci-rust against protected Git revisions."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_standalone_readme_intent as fixture


def sha(data):
    return hashlib.sha256(data).hexdigest()


def document(values, body):
    return ("---\n" + "".join(f"{k}: {v}\n" for k, v in values.items()) + "---\n" + body).encode()


class ProductReadmeScopeTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.StandaloneIntentTest()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.declaration = "{main: ['.', 'engine']}"
        self.write_scope(".")
        self.write_scope("engine")
        self.adopt()

    def write_scope(self, scope, *, status="approved", identity=None):
        prefix = "" if scope == "." else scope + "/"
        ids = {kind: "urn:example:" + (identity or scope) + ":" + kind for kind in ("intent", "requirements", "architecture")}
        values = {"status": status, "id": ids["intent"]}
        readme = document(values, "# Definition\n\n## Intent\n\nProvide stable observations.\n\n## Operations\n\nRead the manual.\n")
        self.f.write(prefix + "README.md", readme)
        intent = fixture.policy.readme_intent(readme).sha256
        values = {"status": status, "id": ids["requirements"], "intent": ids["intent"]}
        if scope == ".":
            values.update(readme_intent_scopes=self.declaration, intent_sha256=intent)
            body = "# Requirements\n\nProvide stable reads.\n"
        else:
            body = f"# Requirements\n\nFollow the [product intent](../README.md#intent) at SHA-256\n`{intent}`.\n"
        req = document(values, body)
        self.f.write(prefix + "docs/requirements.md", req)
        values = {"status": status, "id": ids["architecture"], "intent": ids["intent"], "requirements": ids["requirements"]}
        if scope == ".":
            values.update(intent_sha256=intent, requirements_sha256=sha(req))
            body = "# Architecture\n\nKeep an isolated service.\n"
        else:
            body = ("# Architecture\n\n| Source | SHA-256 |\n| --- | --- |\n"
                    f"| [Intent](../README.md#intent) | `{intent}` |\n| [Requirements](requirements.md) | `{sha(req)}` |\n")
        self.f.write(prefix + "docs/architecture.md", document(values, body))

    def adopt(self):
        self.f.head = self.f.commit()
        self.f.adopt_migration()
        self.f.refresh_event()

    def candidate(self, *, code=True):
        if code:
            self.f.write("src/lib.rs", b"pub fn measure() -> u32 { 1 }\n")
        self.f.head = self.f.commit()
        self.f.refresh_event()

    def cli(self, valid, message=None):
        result = subprocess.run([sys.executable, "-I", "-B", str(fixture.SCRIPTS / "validate_product_lifecycle_baseline.py")],
                                cwd=self.f.repo, env=os.environ | self.f.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, valid, result.stderr + result.stdout)
        if message:
            self.assertIn(message, result.stdout if valid else result.stderr)

    def test_approved_product_pr_exact_merge_and_protected_push(self):
        self.declaration = "{dev: ['.', 'engine']}"
        self.write_scope(".")
        self.adopt()
        self.f.git("update-ref", "refs/remotes/origin/dev", self.f.base)
        self.f.write("examples/README.md", b"# Syntax\n\n```md\n## Intent\n\nA sample.\n```\n")
        self.candidate()
        self.f.event["pull_request"]["base"]["ref"] = "dev"
        self.f.env["GITHUB_BASE_REF"] = "dev"
        self.f.save_event()
        self.cli(True, "approved-structure")
        merged = self.f.git("commit-tree", self.f.git("rev-parse", "HEAD^{tree}"), "-p", self.f.base, "-p", self.f.head, "-m", "merge")
        self.f.git("checkout", "--detach", merged)
        self.f.env["GITHUB_SHA"] = merged
        self.cli(True, "approved-structure")
        self.f.event = {"repository": self.f.event["repository"], "ref": "refs/heads/dev", "before": self.f.base,
                        "after": merged, "created": False, "deleted": False, "forced": False}
        self.f.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/dev")
        self.f.save_event()
        self.cli(True, "approved-structure")

    def test_missing_undeclared_competing_duplicate_and_detached_scopes(self):
        for name in ("missing", "undeclared", "competing", "duplicated", "detached", "extra-readme"):
            with self.subTest(name=name):
                self.f.git("reset", "--hard", self.f.base)
                if name == "missing":
                    self.f.git("rm", "engine/docs/requirements.md")
                elif name == "undeclared":
                    self.write_scope("another")
                elif name == "competing":
                    self.f.write("engine/docs/intent.md", b"# Alternative\n")
                elif name == "duplicated":
                    self.write_scope("engine", identity=".")
                elif name == "detached":
                    self.write_scope("engine", identity="other")
                else:
                    self.f.write("other/README.md", b"# Other\n\n## Intent\n\nAnother owner.\n")
                self.candidate()
                self.cli(False)

    def test_explicit_digest_and_id_binding_for_each_scope_and_format(self):
        for name, before, after in (
            ("engine/docs/architecture.md", b"| [Requirements](requirements.md) | `", b"| [Requirements](requirements.md) | `f"),
            ("engine/docs/requirements.md", b"at SHA-256\n`", b"at SHA-256\n`f"),
            ("engine/docs/requirements.md", b"../README.md#intent", b"../../README.md#intent"),
            ("engine/docs/architecture.md", b"requirements: urn:example:engine:requirements", b"requirements: urn:example:.:requirements"),
            ("docs/architecture.md", b"requirements_sha256: ", b"requirements_sha256: f"),
            ("engine/docs/architecture.md", b"id: urn:example:engine:architecture", b"description: architecture"),
        ):
            with self.subTest(name=name, before=before):
                self.f.git("reset", "--hard", self.f.base)
                target = self.f.repo / name
                raw = target.read_bytes()
                self.assertIn(before, raw)
                target.write_bytes(raw.replace(before, after))
                self.candidate()
                self.cli(False)

    def test_provisional_on_either_revision_refuses_mixed_code(self):
        self.write_scope("engine", status="provisional")
        self.candidate()
        self.cli(False, "provisional repair")
        self.f.git("reset", "--hard", self.f.base)
        self.write_scope("engine", status="provisional")
        self.adopt()
        self.write_scope("engine")
        self.candidate()
        self.cli(False, "provisional repair")
        self.f.git("reset", "--hard", self.f.base)
        self.write_scope("engine")
        self.candidate(code=False)
        self.cli(True, "definition-only")

    def test_changed_or_malformed_protected_selection_cannot_admit_code(self):
        for declaration in ("{main: ['.']}", "{main: ['.', '../other']}", "{main: ['.', 'engine'], dev: ['.']}",
                            "{main: ['.', 'engine', 'another']}", "false"):
            with self.subTest(declaration=declaration):
                self.f.git("reset", "--hard", self.f.base)
                self.declaration = declaration
                self.write_scope(".")
                self.candidate()
                self.cli(False)

    def test_first_candidate_declaration_with_code_refused_even_beside_legacy_sources(self):
        self.f.write("docs/intent.md", self.f.old_intent)
        self.f.write_trio(self.f.old_intent, selected=False)
        self.adopt()
        self.f.write_trio(self.f.old_intent)
        self.candidate()
        self.cli(False, "documentation-only")
        Path(self.f.env["GITHUB_EVENT_PATH"]).write_bytes(b"{}")
        self.cli(False, "provider evidence")

    def test_wrong_provider_or_damaged_checked_merge_refused(self):
        self.candidate()
        self.f.env["GITHUB_SERVER_URL"] = "https://wrong.invalid"
        self.cli(False, "provider")
        self.f.env["GITHUB_SERVER_URL"] = "https://github.com"
        self.f.git("rm", "engine/docs/architecture.md")
        self.f.git("add", "-A")
        tree = self.f.git("write-tree")
        merged = self.f.git("commit-tree", tree, "-p", self.f.base, "-p", self.f.head, "-m", "merge")
        self.f.git("checkout", "--detach", merged)
        self.f.env["GITHUB_SHA"] = merged
        self.cli(False, "missing registered governing source")

    def test_existing_root_only_optional_metadata_contract_remains_eligible(self):
        self.f.git("rm", "-r", "engine")
        self.f.write("README.md", document({"status": "approved"}, "# Example\n\n## Intent\n\nPreserve observed results.\n"))
        self.f.write("docs/requirements.md", document({"status": "approved", "id": "urn:example:requirements",
                     "readme_intent_scopes": "{main: ['.']}"}, "# Requirements\n\nKeep history.\n"))
        self.f.write("docs/architecture.md", document({"status": "approved", "requirements": "urn:example:requirements"},
                     "# Architecture\n\nKeep the source distinct.\n"))
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")


if __name__ == "__main__":
    unittest.main()
