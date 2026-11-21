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

    def test_docs_enroll_first_and_subsequent_scopes_before_code(self):
        self.f.git("rm", "-r", "engine")
        self.declaration = "{main: ['.']}"
        self.write_scope(".")
        # An old root may retain only a subset of the source identity chain.
        self.f.write("docs/requirements.md", document(
            {"status": "approved", "id": "urn:example:.:requirements", "readme_intent_scopes": self.declaration},
            "# Requirements\n\nStable observations.\n"))
        self.f.write("docs/architecture.md", document(
            {"status": "approved", "requirements": "urn:example:.:requirements"},
            "# Architecture\n\nAn independent service.\n"))
        self.adopt()
        self.declaration = "{main: ['.', 'engine']}"
        self.write_scope(".")
        self.write_scope("engine")
        self.candidate(code=False)
        self.cli(True, "approved-structure")
        self.adopt()
        self.declaration = "{main: ['.', 'engine', 'source']}"
        self.write_scope(".")
        self.write_scope("source", status="provisional")
        self.candidate(code=False)
        self.cli(True, "definition-only")
        self.adopt()
        self.write_scope("source")
        self.candidate()
        self.cli(False, "provisional repair")
        self.f.git("reset", "--hard", self.f.base)
        self.write_scope("source")
        self.candidate(code=False)
        self.cli(True, "definition-only")
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")

    def test_scope_enrollment_needs_complete_definitions_and_protected_identities(self):
        for defect in ("missing", "incomplete", "stale", "replaced", "code", "inactive"):
            with self.subTest(defect=defect):
                self.f.git("reset", "--hard", self.f.base)
                self.declaration = ("{main: ['.', 'engine'], dev: ['.', 'engine', 'source']}" if defect == "inactive" else
                                    "{main: ['.', 'engine', 'source']}")
                self.write_scope(".")
                if defect not in {"missing", "inactive"}:
                    self.write_scope("source")
                if defect == "incomplete":
                    (self.f.repo / "source/docs/architecture.md").unlink()
                if defect == "stale":
                    req = self.f.repo / "source/docs/requirements.md"
                    req.write_bytes(req.read_bytes() + b"Changed.\n")
                if defect == "replaced":
                    self.write_scope("engine", identity="detached")
                self.candidate(code=defect == "code")
                self.cli(False)

    def test_root_only_unrelated_digest_evidence_and_wrong_governing_target(self):
        self.f.git("rm", "-r", "engine")
        self.declaration = "{main: ['.']}"
        self.write_scope(".")
        self.adopt()
        req = self.f.repo / "docs/requirements.md"
        arch = self.f.repo / "docs/architecture.md"
        for label, valid in (("sample evidence", True), ("product intent", False)):
            with self.subTest(label=label):
                self.f.git("reset", "--hard", self.f.base)
                old = sha(req.read_bytes()).encode()
                req.write_bytes(req.read_bytes() + f"\n[{label}](sample.md) at SHA-256 `{'f' * 64}`.\n".encode())
                arch.write_bytes(arch.read_bytes().replace(old, sha(req.read_bytes()).encode()))
                self.candidate()
                self.cli(valid, "approved-structure" if valid else "wrong upstream governing link")

    def test_enrollment_and_product_with_checksummed_external_schema(self):
        url = "https://example.invalid/schema.json"

        def add_schema(scope, label="published schema", target=url):
            prefix = self.f.repo if scope == "." else self.f.repo / scope
            req, arch = prefix / "docs/requirements.md", prefix / "docs/architecture.md"
            before = sha(req.read_bytes()).encode()
            link = f"[{label}]({target})"
            evidence = (f"{link} at SHA-256 `{'a' * 64}`." if scope == "." else
                        f"| Source | SHA-256 |\n| --- | --- |\n| {link} | `{'a' * 64}` |")
            req.write_bytes(req.read_bytes() + f"\n{evidence}\n".encode())
            arch.write_bytes(arch.read_bytes().replace(before, sha(req.read_bytes()).encode()))

        self.f.git("rm", "-r", "engine")
        self.declaration = "{main: ['.']}"
        self.write_scope(".")
        add_schema(".", label="Organization Requirements")
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")
        self.f.git("reset", "--hard", self.f.base)
        self.declaration = "{main: ['.', 'engine']}"
        self.write_scope(".")
        self.write_scope("engine")
        add_schema(".", label="Organization Requirements")
        add_schema("engine")
        self.candidate(code=False)
        self.cli(True, "approved-structure")
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")
        reader = fixture.route.checking_baseline().first_definition
        texts = fixture.route.governing_texts(self.f.repo, self.f.head, [".", "engine"], fixture.policy)
        with self.assertRaisesRegex(ValueError, "digest link has wrong governing target"):
            reader.check_documents(texts, [".", "engine"], fixture.policy, allow_approved=True)
        for label, target in (("product intent", url), ("local requirements", url), ("published schema", "../README.md#intent")):
            with self.subTest(label=label, target=target):
                self.f.git("reset", "--hard", self.f.base)
                add_schema("engine", label=label, target=target)
                self.candidate()
                self.cli(False)

    def test_root_only_keeps_unrelated_nested_documentation_outside_its_scope(self):
        self.f.git("rm", "-r", "engine")
        self.declaration = "{main: ['.']}"
        self.write_scope(".")
        self.f.write("archive/docs/intent.md", b"# Historical intent\n")
        self.f.write("examples/README.md", b"# Example\n\n## Intent\n\nDescribe the sample.\n")
        (self.f.repo / "archive/README.md").symlink_to("../README.md")
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")
        self.f.git("reset", "--hard", self.f.base)
        self.declaration = "{main: ['.', 'engine']}"
        self.write_scope(".")
        self.write_scope("engine")
        self.candidate(code=False)
        self.cli(False)
        self.f.git("reset", "--hard", self.f.base)
        self.f.git("rm", "-r", "archive", "examples")
        self.adopt()
        self.write_scope(".")
        self.write_scope("engine")
        self.candidate(code=False)
        self.cli(True, "approved-structure")

    def test_protected_historical_checksums_are_validated_and_carried_into_multiscope(self):
        self.f.git("rm", "-r", "engine")
        self.declaration = "{main: ['.']}"
        self.write_scope(".")
        req = self.f.repo / "docs/requirements.md"
        arch = self.f.repo / "docs/architecture.md"
        readme = self.f.repo / "README.md"
        intent = fixture.policy.readme_intent(readme.read_bytes()).sha256

        def add_bindings(target, digest):
            previous = sha(req.read_bytes()).encode()
            req.write_bytes(req.read_bytes() + (f"\n[Intent]({target}) at SHA-256`{digest}`.\n\n"
                            f"| Source | Digest |\n| --- | --- |\n| [Product Intent]({target}) | `{digest}` |\n").encode())
            arch.write_bytes(arch.read_bytes().replace(previous, sha(req.read_bytes()).encode()))

        historical_target = "legacy source with spaces.md"
        add_bindings(historical_target, intent)
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")
        self.f.git("reset", "--hard", self.f.base)
        previous = sha(req.read_bytes()).encode()
        req.write_bytes(req.read_bytes().replace(f"SHA-256`{intent}`".encode(), f"SHA-256`{'0' * 64}`".encode()))
        # Rebind Architecture to the exact edit so only the historical checksum is wrong.
        arch.write_bytes(arch.read_bytes().replace(previous, sha(req.read_bytes()).encode()))
        self.candidate()
        self.cli(False, "wrong upstream governing digest")
        self.f.git("reset", "--hard", self.f.base)
        self.declaration = "{main: ['.', 'engine']}"
        self.write_scope(".")
        self.write_scope("engine")
        self.candidate(code=False)
        self.cli(False, "protected governing binding removed")
        add_bindings("../README.md#intent", intent)
        self.candidate(code=False)
        self.cli(True, "approved-structure")

    def test_root_only_can_keep_or_repair_previously_unrecognized_claims(self):
        self.f.git("rm", "-r", "engine")
        self.declaration = "{main: ['.']}"
        self.write_scope(".")
        req = self.f.repo / "docs/requirements.md"
        arch = self.f.repo / "docs/architecture.md"
        intent = fixture.policy.readme_intent((self.f.repo / "README.md").read_bytes()).sha256
        stale = "f" * 64
        intent_claim = f"[product intent](../README.md#intent) at SHA-256 `{stale}`".encode()
        req_claim = f"| [Product Requirements](./requirements.md) | `{stale}` |".encode()
        previous = sha(req.read_bytes()).encode()
        req.write_bytes(req.read_bytes() + b"\n" + intent_claim + b"\n")
        arch.write_bytes(arch.read_bytes().replace(previous, sha(req.read_bytes()).encode())
                         + b"\n| Source | Digest |\n| --- | --- |\n" + req_claim + b"\n")
        self.adopt()
        self.candidate()
        self.cli(True, "approved-structure")
        for source in ("intent", "requirements"):
            with self.subTest(repair=source):
                self.f.git("reset", "--hard", self.f.base)
                if source == "intent":
                    previous = sha(req.read_bytes()).encode()
                    req.write_bytes(req.read_bytes().replace(intent_claim, intent_claim.replace(stale.encode(), intent.encode())))
                    arch.write_bytes(arch.read_bytes().replace(previous, sha(req.read_bytes()).encode(), 1))
                else:
                    repair = req_claim.replace(b"./requirements.md", b"requirements.md").replace(stale.encode(), sha(req.read_bytes()).encode())
                    arch.write_bytes(arch.read_bytes().replace(req_claim, repair))
                self.candidate(code=False)
                self.cli(True, "approved-structure")
        for claim in (req_claim, req_claim.replace(b"./requirements.md", b"other.md")):
            with self.subTest(new_claim=claim):
                self.f.git("reset", "--hard", self.f.base)
                arch.write_bytes(arch.read_bytes() + claim + b"\n")
                self.candidate(code=False)
                self.cli(False, "wrong upstream governing link")

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
