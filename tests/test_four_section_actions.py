"""Run shared vectors through the exact action-owned entry on real Git revisions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from four_section_fixture import CASES, KEY, LOCAL, MANIFEST, README, TRIO, details, documents, sha

SCRIPTS = Path(__file__).resolve().parents[1] / "actions/ci-alphaapps-policy/scripts"
sys.path.insert(0, str(SCRIPTS.parent / "tests"))
import test_standalone_readme_intent as legacy


def encoded(record):
    return (json.dumps(record, indent=2) + "\n").encode()


class FourSectionActions(unittest.TestCase):
    def setUp(self):
        self.f = legacy.StandaloneIntentTest()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        meta, self.manifest = documents()
        self.meta = meta
        self.f.write("README.md", README.split(b"## Requirements")[0] + b"## Navigation\n\nFind the service.\n")
        # Preserve existing metadata, including current authored upstream assertions.
        self.write_old("requirements", "# Requirements\n\nEvery correction retains the original value.\n")
        self.write_old("architecture", "# Architecture\n\nThe recorder owns the history.\n")
        self.f.head = self.f.commit()
        self.f.adopt_migration()
        self.convert()

    def write_old(self, kind, body):
        meta = self.meta["README.md#" + kind]
        self.f.write(f"docs/{kind}.md", ("---\n" + "\n".join(k + ": " + json.dumps(v) for k, v in meta.items())
                     + "\n---\n" + body).encode())

    def convert(self):
        self.f.write("README.md", README)
        for old in ("docs/requirements.md", "docs/architecture.md"):
            (self.f.repo / old).unlink()
        for path, data in details().items():
            self.f.write(path, data)
        self.save()

    def save(self):
        self.f.write(MANIFEST, encoded(self.manifest))
        self.f.head = self.f.commit()
        self.f.refresh_event()

    def run_policy(self, expect=0):
        result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPTS / "validate_product_lifecycle_baseline.py")],
                                cwd=self.f.repo, env=os.environ | self.f.env, capture_output=True, text=True)
        self.assertEqual(expect == 0, result.returncode == 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_common_fixture_policy_and_classification(self):
        out = self.run_policy()
        for value in CASES["digests"].values():
            self.assertIn(value, out)
        self.f.adopt_migration()
        for case in CASES["edits"]:
            with self.subTest(case=case["id"]):
                changed = README.replace(case["before"].encode(), case["after"].encode())
                self.assertNotEqual(README, changed)
                self.f.write("README.md", changed)
                self.manifest["local_instructions"]["sha256"] = CASES["digests"]["local-instructions"]
                if case["decision"] == "instructions":
                    start = changed.index(b"## Local Instructions")
                    end = changed.index(b"\n## Navigation", start)
                    self.manifest["local_instructions"]["sha256"] = sha(changed[start:end].rstrip(b"\n") + b"\n")
                self.save()
                out = self.run_policy(1 if case["decision"] == "reject" else 0)
                if case["decision"] != "reject":
                    self.assertEqual(case["decision"] == "instructions", "Local Instructions changed" in out)
                    for key in ("intent", "requirements", "architecture"):
                        self.assertIn(CASES["digests"][key], out)

    def test_older_standalone_intent_can_transfer_exactly(self):
        self.f.git("reset", "--hard", self.f.base)
        head = README.index(b"## Intent")
        body = README[head:].split(b"## Requirements")[0].replace(
            b"## Intent", b"# Example Intent", 1).replace(b"### Boundaries", b"## Boundaries")
        front = README.split(b"---\n", 2)[1]
        self.f.write("docs/intent.md", b"---\n" + front + b"---\n" + body)
        self.f.write("README.md", b"# Example service\n")
        self.f.head = self.f.commit()
        self.f.adopt_migration()
        (self.f.repo / "docs/intent.md").unlink()
        self.convert()
        self.assertIn("four-section README", self.run_policy())

    def test_unqualified_native_alias_cannot_enter_with_source_migration(self):
        self.f.git("reset", "--hard", self.f.base)
        self.f.write("PROJECT.md", b"# Working instructions\n")
        (self.f.repo / "AGENTS.md").symlink_to("PROJECT.md")
        self.f.head = self.f.commit()
        self.f.adopt_migration()
        (self.f.repo / "PROJECT.md").unlink()
        (self.f.repo / "AGENTS.md").unlink()
        (self.f.repo / "AGENTS.md").symlink_to("docs/observations.md")
        self.convert()
        self.assertIn("unsupported native instruction alias", self.run_policy(1))
        (self.f.repo / "AGENTS.md").unlink()
        self.f.write("AGENTS.md", b"# Read a different source\n")
        self.save()
        self.assertIn("native instruction entry must point", self.run_policy(1))

    def test_missing_damaged_or_unlinked_normative_detail(self):
        self.f.adopt_migration()
        for data in (b"# Wrong source\n", None):
            with self.subTest(data=data):
                file = self.f.repo / "docs/observations.md"
                if data is None:
                    file.unlink()
                else:
                    file.write_bytes(data)
                self.save()
                self.run_policy(1)
        self.f.write("docs/observations.md", details()["docs/observations.md"])
        self.manifest["sources"] = self.manifest["sources"][:-2] + self.manifest["sources"][-1:]
        del self.manifest["sources"][2]["upstream"][1]["detail_sha256"]
        self.save()
        self.assertIn("removed or reassigned governing source", self.run_policy(1))

    def test_stale_child_even_after_parent_hash_refresh(self):
        self.f.adopt_migration()
        detail = b"# New observation contract\n\nRetain the full audit trail.\n"
        self.f.write("docs/observations.md", detail)
        self.manifest["sources"][3]["sha256"] = sha(detail)
        self.save()
        self.assertIn("wrong upstream selector or digest", self.run_policy(1))
        self.manifest["sources"][2]["upstream"][1]["detail_sha256"] = sha(detail)
        self.save()
        self.run_policy()
        data = README.replace(b"original observations", b"source observations")
        changed = legacy.policy.readme_intent(data).sha256
        self.f.write("README.md", data)
        self.manifest["sources"][0]["sha256"] = changed
        self.save()
        self.assertIn("wrong upstream selector or digest", self.run_policy(1))

    def test_inline_example_escaped_and_comment_links_cannot_bind_detail(self):
        self.f.adopt_migration()
        src = b"[observation contract](docs/observations.md)"
        for example in (b"`" + src + b"`", b"\\" + src, b"!" + src, b"<!--\n" + src + b"\n-->",
                        b"``a code span\n" + src + b"``", b"[other](file.md '" + src + b"')",
                        b"[&nbsp;](docs/observations.md)", b"[observations](docs/observations.md#missing)",
                        b"[obligations](./docs/observations.md)", b"[observations](docs/Observations.md)"):
            with self.subTest(example=example):
                readme = README.replace(src, example)
                selected = legacy.policy.readme_sections(readme)
                digest = sha(selected.sections["Requirements"])
                self.manifest["sources"][1]["sha256"] = digest
                self.manifest["sources"][2]["upstream"][1]["sha256"] = digest
                self.manifest["sources"][3]["upstream"][0]["sha256"] = digest
                self.f.write("README.md", readme)
                self.save()
                self.assertIn("missing link to normative detail", self.run_policy(1))

    def test_ordinary_link_adjacent_to_bracketed_text(self):
        reader = legacy.route.four_reader()
        for title in (b"", b' "Observation details"', b" 'Observation details'", b" (Observation details)",
                      b'\n"Observation details"'):
            with self.subTest(title=title):
                section = b"## Requirements\n\n[Optional] See [obligations](docs/observations.md" + title + b").\n"
                self.assertEqual({"docs/observations.md"}, reader.detail_links(section, legacy.policy))

    def test_prepared_layout_cannot_be_completed_one_heading_at_a_time(self):
        self.f.git("reset", "--hard", self.f.base)
        path = self.f.repo / "README.md"
        for name in ("Requirements", "Architecture", "Local Instructions"):
            path.write_bytes(path.read_bytes() + f"\n## {name}\n\nSome prose.\n".encode())
            self.f.head = self.f.commit()
            self.f.refresh_event()
            if name == "Local Instructions":
                self.assertIn("incomplete four-section conversion", self.run_policy(1))
            else:
                self.run_policy()
                self.f.adopt_migration()

    def test_prepared_legacy_pr_and_push_continue_until_cutover(self):
        self.f.git("reset", "--hard", self.f.base)
        self.f.write("product.py", b"active = True\n")
        self.f.head = self.f.commit()
        self.f.refresh_event()
        self.assertIn("Protected-base README Intent", self.run_policy())
        self.f.event = {"repository": self.f.event["repository"], "before": self.f.base, "after": self.f.head,
                        "ref": "refs/heads/main", "created": False, "deleted": False, "forced": False}
        self.f.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main")
        self.f.save_event()
        self.assertIn("Protected-base README Intent", self.run_policy())
        self.f.env.update(GITHUB_EVENT_NAME="pull_request", GITHUB_REF="refs/pull/7/merge")
        self.f.write(MANIFEST, b'{"schema_version": 3}\n')
        self.f.head = self.f.commit()
        self.f.refresh_event()
        self.assertIn("incomplete four-section conversion", self.run_policy(1))

    def test_exact_protected_push_and_synthetic_merge(self):
        self.f.event = {"repository": self.f.event["repository"], "before": self.f.base, "after": self.f.head,
                        "ref": "refs/heads/main", "created": False, "deleted": False, "forced": False}
        self.f.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main")
        self.f.save_event()
        self.assertIn("four-section README", self.run_policy())
        self.f.env.update(GITHUB_EVENT_NAME="pull_request", GITHUB_REF="refs/pull/7/merge")
        self.f.git("checkout", "--detach", self.f.base)
        self.f.git("merge", "--no-ff", self.f.head, "-m", "provider test merge")
        self.f.refresh_event()
        self.f.env["GITHUB_SHA"] = self.f.git("rev-parse", "HEAD")
        self.assertIn("four-section README", self.run_policy())

    def test_provisional_mixed_and_definition_only(self):
        self.f.adopt_migration()
        self.manifest["source_metadata"][TRIO[1]]["status"] = "provisional"
        self.save()
        self.assertIn("definition-only", self.run_policy())
        self.f.adopt_migration()
        self.f.write("service.py", b"print('running')\n")
        self.save()
        self.assertIn("provisional repair", self.run_policy(1))
        (self.f.repo / "service.py").unlink()
        self.f.write("README.md", README.replace(b"Read the service directory.", b"Read the directory."))
        self.save()
        self.assertIn("provisional repair", self.run_policy(1))

    def test_never_enrolled_legacy_manifest_name_does_not_change_validation(self):
        self.f.git("reset", "--hard", self.f.base)
        del self.meta[TRIO[1]][KEY]
        self.write_old("requirements", "# Requirements\n\nPreserve observations.\n")
        self.f.head = self.f.commit()
        self.f.adopt_migration()
        path = self.f.repo / MANIFEST
        path.symlink_to("unrelated-data.json")
        self.f.head = self.f.commit()
        self.f.refresh_event()
        self.assertIn("Protected-base README Intent", self.run_policy())
        path.unlink()
        self.f.write(MANIFEST, b"{}" * 300000)
        self.f.head = self.f.commit()
        self.f.refresh_event()
        self.assertIn("Protected-base README Intent", self.run_policy())

    def test_foreign_provider_and_selected_checkout_cannot_fall_back(self):
        self.f.env["GITHUB_REPOSITORY_ID"] = "999"
        self.run_policy(1)
        self.f.env["GITHUB_REPOSITORY_ID"] = "123"
        self.f.adopt_migration()
        (self.f.repo / MANIFEST).unlink()
        self.write_old("requirements", "# Requirements\n\nUse this copy.\n")
        self.write_old("architecture", "# Architecture\n\nUse this copy.\n")
        self.f.head = self.f.commit()
        self.f.refresh_event()
        self.assertIn("removed protected four-section manifest", self.run_policy(1))

    def test_candidate_enrollment_and_mixed_migration(self):
        self.f.write("service.py", b"new = True\n")
        self.save()
        self.assertIn("documentation-only", self.run_policy(1))
        self.f.base = self.f.git("rev-parse", self.f.base + "^")
        self.f.git("update-ref", "refs/remotes/origin/main", self.f.base)
        self.f.refresh_event()
        self.assertIn("enroll its own conversion", self.run_policy(1))
