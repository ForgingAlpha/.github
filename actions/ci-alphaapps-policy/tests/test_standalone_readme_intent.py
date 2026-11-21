import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load("standalone_test_policy", SCRIPTS / "validate_product_lifecycle_baseline.py")
route = load("standalone_test_route", SCRIPTS / "standalone_readme_intent.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class StandaloneIntentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "consumer"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/ForgingAlpha/example.git")
        self.old_intent = (b"---\nstatus: approved\nid: control://example/intent\ntags: [example]\n---\n"
                           b"# Example Intent\n\n## Purpose\n\nPreserve exact meaning.\n\n"
                           b"```md\n## Example heading\n```\n\n##### Details\nKeep these.\n")
        self.write("docs/intent.md", self.old_intent)
        self.write("README.md", b"# Example\n\nNavigation.\n")
        self.write_trio(self.old_intent)
        self.base = self.commit()
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.git("switch", "-c", "feature")
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
                    "GITHUB_REPOSITORY": "ForgingAlpha/example", "GITHUB_REPOSITORY_ID": "123",
                    "GITHUB_REF": "refs/pull/7/merge", "GITHUB_BASE_REF": "main", "GITHUB_HEAD_REF": "feature",
                    "GITHUB_EVENT_PATH": str(self.root / "event.json"),
                    "POLICY_ACTION_REPOSITORY": "ForgingAlpha/.github", "POLICY_ACTION_REF": "main"}
        self.migrate()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout.decode().strip()

    def write(self, path, data):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def write_trio(self, intent, selected=True):
        select = "readme_intent_scopes: {main: ['.']}\n" if selected else ""
        req = ("---\nstatus: approved\nid: control://example/requirements\n"
               "intent: control://example/intent\nintent_sha256: " + digest(intent) + "\n" + select
               + "---\n# Requirements\n\nPreserve records.\n").encode()
        self.write("docs/requirements.md", req)
        self.write("docs/architecture.md", ("---\nstatus: approved\nid: control://example/architecture\n"
                   "intent: control://example/intent\nintent_sha256: " + digest(intent)
                   + "\nrequirements: control://example/requirements\nrequirements_sha256: " + digest(req)
                   + "\n---\n# Architecture\n\nOwned responsibilities.\n").encode())

    def migrate(self):
        _, end = policy.leading_metadata(self.old_intent.decode().split("\n"))
        front = "\n".join(self.old_intent.decode().split("\n")[:end]).encode() + b"\n"
        canonical = front + route.transferred_intent(policy, self.old_intent)
        self.write("README.md", front + b"# Example\n\n" + route.transferred_intent(policy, self.old_intent)
                   + b"\n## Operations\n\nRead the manual.\n")
        (self.repo / "docs/intent.md").unlink(missing_ok=True)
        self.write_trio(canonical)
        self.head = self.commit()
        self.refresh_event()

    def refresh_event(self):
        repository = {"id": 123, "full_name": "ForgingAlpha/example",
                      "html_url": "https://github.com/ForgingAlpha/example"}
        self.event = {"number": 7, "repository": repository,
                      "pull_request": {"number": 7,
                                       "base": {"repo": repository, "ref": "main", "sha": self.base},
                                       "head": {"repo": repository, "ref": "feature", "sha": self.head}}}
        self.env["GITHUB_SHA"] = self.head
        self.save_event()

    def save_event(self):
        Path(self.env["GITHUB_EVENT_PATH"]).write_text(json.dumps(self.event))

    def check(self):
        return route.maybe_validate(self.repo, policy, self.env)

    def revise(self, path, before, after):
        target = self.repo / path
        target.write_bytes(target.read_bytes().replace(before, after))
        self.head = self.commit()
        self.refresh_event()

    def adopt_migration(self):
        self.base = self.head
        self.git("update-ref", "refs/remotes/origin/main", self.base)

    def rebind_current_intent(self):
        self.write_trio(policy.readme_intent((self.repo / "README.md").read_bytes()).canonical)
        self.head = self.commit()
        self.refresh_event()

    def test_first_migration_preserves_fenced_examples_and_exact_prose(self):
        self.assertTrue(self.check())
        self.assertIn(b"```md\n## Example heading\n```", route.transferred_intent(policy, self.old_intent))

    def test_dispatch_executes_the_same_route_under_isolated_python(self):
        self.write("yaml.py", b"raise RuntimeError('consumer module must never execute')\n")
        env = os.environ | self.env | {"ALPHAAPPS_POLICY_BASE_REF": "wrong-and-ignored",
                                      "PYTHONPATH": str(self.repo)}
        result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPTS / "validate_product_lifecycle_baseline.py")],
                                cwd=self.repo, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Protected-base README", result.stdout)

    def test_opening_prose_and_table_digests(self):
        intent_digest, requirement_digest = "a" * 64, "b" * 64
        requirement = ("---\nstatus: approved\n---\n# Example — Product Requirements\n\n"
                       "Derived from the [Product Intent](../README.md#intent), SHA-256\n`"
                       + intent_digest + "`.\n\n## Terms\n").encode()
        architecture = ("---\nstatus: approved\n---\n# Example — Architecture\n\n"
                        "| Source | SHA-256 |\n| --- | --- |\n| [Intent](../README.md#intent) | `"
                        + intent_digest + "` |\n| [Requirements](requirements.md) | `"
                        + requirement_digest + "` |\n\n## Responsibilities\n").encode()
        self.assertEqual(route.upstream_bindings(requirement, {}, "requirements"),
                         {"intent": [intent_digest], "requirements": []})
        self.assertEqual(route.upstream_bindings(architecture, {}, "architecture"),
                         {"intent": [intent_digest], "requirements": [requirement_digest]})

    def test_later_migrated_read_allows_authored_body_update_with_exact_bindings(self):
        self.adopt_migration()
        target = self.repo / "README.md"
        target.write_bytes(target.read_bytes().replace(b"Preserve exact meaning.", b"Preserve revised meaning."))
        self.write_trio(policy.readme_intent(target.read_bytes()).canonical)
        self.head = self.commit()
        self.refresh_event()
        self.assertTrue(self.check())

    def test_later_unrelated_metadata_can_change(self):
        self.adopt_migration()
        readme = self.repo / "README.md"
        readme.write_bytes(readme.read_bytes().replace(b"tags: [example]", b"tags: [revised]"))
        self.write_trio(policy.readme_intent(readme.read_bytes()).canonical)
        requirements = self.repo / "docs/requirements.md"
        before = requirements.read_bytes()
        requirements.write_bytes(before.replace(b"status: approved", b"status: approved\ntags: [new]"))
        architecture = self.repo / "docs/architecture.md"
        architecture.write_bytes(architecture.read_bytes().replace(digest(before).encode(), digest(requirements.read_bytes()).encode())
                                 .replace(b"status: approved", b"status: approved\ntags: [new]"))
        self.head = self.commit()
        self.refresh_event()
        self.assertTrue(self.check())

    def test_later_provisional_definition_repair_and_repair_to_approved(self):
        self.adopt_migration()
        readme = self.repo / "README.md"
        readme.write_bytes(readme.read_bytes().replace(b"status: approved", b"status: provisional")
                          .replace(b"exact meaning", b"proposed meaning"))
        self.rebind_current_intent()
        with patch("builtins.print") as output:
            self.assertTrue(self.check())
        self.assertIn("definition-only", output.call_args.args[0])
        self.adopt_migration()
        readme.write_bytes(readme.read_bytes().replace(b"status: provisional", b"status: approved"))
        self.rebind_current_intent()
        with patch("builtins.print") as output:
            self.assertTrue(self.check())
        self.assertIn("definition-only", output.call_args.args[0])

    def test_provisional_repair_cannot_cover_code_or_readme_navigation(self):
        self.adopt_migration()
        readme = self.repo / "README.md"
        readme.write_bytes(readme.read_bytes().replace(b"status: approved", b"status: provisional"))
        self.rebind_current_intent()
        proposed = self.head
        for path, text in (("lib/example.py", b"implementation = True\n"),
                           ("README.md", readme.read_bytes().replace(b"Read the manual.", b"Changed navigation."))):
            with self.subTest(path=path):
                self.git("reset", "--hard", proposed)
                self.write(path, text)
                self.head = self.commit()
                self.refresh_event()
                with self.assertRaisesRegex(ValueError, "provisional repair"):
                    self.check()

    def test_migrated_identity_and_upstream_bindings_remain_required(self):
        self.adopt_migration()
        for before, after in ((b"id: control://example/architecture", b"id: control://other/architecture"),
                              (b"requirements_sha256: " + digest((self.repo / "docs/requirements.md").read_bytes()).encode() + b"\n", b"")):
            with self.subTest(after=after):
                self.git("reset", "--hard", self.base)
                self.revise("docs/architecture.md", before, after)
                with self.assertRaises(ValueError):
                    self.check()

    def test_wrong_first_migration_body_is_refused(self):
        self.revise("README.md", b"exact meaning", b"less meaning")
        self.write_trio(policy.readme_intent((self.repo / "README.md").read_bytes()).canonical)
        self.head = self.commit()
        self.refresh_event()
        with self.assertRaisesRegex(ValueError, "body differs"):
            self.check()

    def test_missing_provisional_or_changed_identity_is_refused(self):
        for before, after in [(b"status: approved", b"status: provisional"),
                              (b"status: approved\n", b""),
                              (b"id: control://example/intent", b"id: control://other/intent")]:
            with self.subTest(after=after):
                self.git("reset", "--hard", self.head)
                target = self.repo / "README.md"
                target.write_bytes(target.read_bytes().replace(before, after))
                changed = self.commit()
                self.event["pull_request"]["head"]["sha"] = changed
                self.env["GITHUB_SHA"] = changed
                self.save_event()
                with self.assertRaises(ValueError):
                    self.check()

    def test_selection_removal_cannot_fall_back_to_legacy(self):
        self.revise("docs/requirements.md", b"readme_intent_scopes: {main: ['.']}\n", b"")
        with self.assertRaisesRegex(ValueError, "selection"):
            self.check()

    def test_selection_cannot_enable_components_or_unknown_branches(self):
        for value in ({"main": ["data"]}, {"main": [".", "data"]}, {"feature": ["."]}, {}, None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "selection"):
                route.selection(value)

    def test_protected_base_with_competing_sources_is_refused(self):
        self.write("docs/intent.md", self.old_intent)
        self.write_trio(self.old_intent)
        self.base = self.commit()
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.migrate()
        with self.assertRaisesRegex(ValueError, "both governing"):
            self.check()

    def test_bad_upstream_digest_is_refused(self):
        self.revise("docs/architecture.md", b"requirements_sha256: ", b"requirements_sha256: bad")
        with self.assertRaisesRegex(ValueError, "digest"):
            self.check()

    def test_competing_sources_and_symlinks_are_refused(self):
        self.write("docs/intent.md", self.old_intent)
        self.head = self.commit()
        self.refresh_event()
        with self.assertRaisesRegex(ValueError, "both governing"):
            self.check()
        (self.repo / "docs/intent.md").unlink()
        (self.repo / "docs/intent.md").symlink_to("requirements.md")
        self.head = self.commit()
        self.refresh_event()
        with self.assertRaisesRegex(ValueError, "nonregular"):
            self.check()

    def test_selected_legacy_preparation_uses_existing_validator(self):
        self.git("reset", "--hard", self.base)
        self.head = self.commit()
        self.refresh_event()
        self.assertFalse(self.check())

    def test_candidate_selection_cannot_enroll_its_own_migration(self):
        self.git("reset", "--hard", self.base)
        self.write_trio(self.old_intent, selected=False)
        self.base = self.commit()
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.migrate()
        self.env["POLICY_ACTION_REPOSITORY"] = "not-used-for-unselected"
        self.assertFalse(self.check())
        env = os.environ | self.env | {"ALPHAAPPS_POLICY_BASE_REF": "main"}
        result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPTS / "validate_product_lifecycle_baseline.py")],
                                cwd=self.repo, env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Deleted baseline", result.stderr)

    def test_provider_action_identity_ref_and_base_drift_refuse(self):
        for key, value in [("GITHUB_SERVER_URL", "https://other.invalid"),
                           ("GITHUB_REPOSITORY_ID", "124"), ("GITHUB_BASE_REF", "dev"),
                           ("GITHUB_REF", "refs/pull/8/merge"), ("GITHUB_SHA", self.base),
                           ("POLICY_ACTION_REF", "feature"), ("POLICY_ACTION_REPOSITORY", "ForgingAlpha/example")]:
            with self.subTest(key=key):
                env = self.env | {key: value}
                with self.assertRaises(ValueError):
                    route.maybe_validate(self.repo, policy, env)
        self.git("update-ref", "refs/remotes/origin/main", self.head)
        with self.assertRaisesRegex(ValueError, "protected base"):
            self.check()

    def test_selected_provider_or_runner_branch_cannot_disagree_into_fallback(self):
        for runner, provider in (("dev", "main"), ("feature-target", "main"), ("main", "dev")):
            with self.subTest(runner=runner, provider=provider):
                self.event["pull_request"]["base"]["ref"] = provider
                self.save_event()
                with self.assertRaisesRegex(ValueError, "ref disagrees"):
                    route.maybe_validate(self.repo, policy, self.env | {"GITHUB_BASE_REF": runner})

    def test_undeclared_target_branches_keep_existing_checks(self):
        for branch in ("dev", "feature-target"):
            with self.subTest(branch=branch):
                self.event["pull_request"]["base"]["ref"] = branch
                self.save_event()
                env = self.env | {"GITHUB_BASE_REF": branch, "POLICY_ACTION_REF": "not-used"}
                self.assertFalse(route.maybe_validate(self.repo, policy, env))

    def test_missing_provider_evidence_cannot_restore_legacy_after_migration(self):
        self.adopt_migration()
        self.write("README.md", b"# Example\n\nNavigation.\n")
        self.write("docs/intent.md", self.old_intent)
        self.write_trio(self.old_intent)
        self.head = self.commit()
        self.refresh_event()
        for missing in ("GITHUB_EVENT_PATH", "GITHUB_SHA", "GITHUB_BASE_REF", "GITHUB_REPOSITORY_ID",
                        "POLICY_ACTION_REPOSITORY", "POLICY_ACTION_REF"):
            with self.subTest(missing=missing):
                env = self.env.copy()
                del env[missing]
                with self.assertRaises(ValueError):
                    route.maybe_validate(self.repo, policy, env)
        Path(self.env["GITHUB_EVENT_PATH"]).write_text("not JSON")
        with self.assertRaisesRegex(ValueError, "provider evidence"):
            self.check()

    def test_unselected_event_base_cannot_override_selected_runner_base(self):
        migrated = self.head
        self.git("reset", "--hard", self.base)
        self.write_trio(self.old_intent, selected=False)
        unselected = self.commit()
        self.git("reset", "--hard", migrated)
        self.head = migrated
        self.adopt_migration()
        self.write("README.md", b"# Example\n\nNavigation.\n")
        self.write("docs/intent.md", self.old_intent)
        self.write_trio(self.old_intent)
        self.head = self.commit()
        self.refresh_event()
        self.event["pull_request"]["base"]["sha"] = unselected
        self.save_event()
        with self.assertRaisesRegex(ValueError, "protected base"):
            self.check()
        for branch in ("dev", "feature-target"):
            with self.subTest(branch=branch), self.assertRaisesRegex(ValueError, "ref disagrees"):
                route.maybe_validate(self.repo, policy, self.env | {"GITHUB_BASE_REF": branch})

    def test_consumer_checker_is_not_trusted(self):
        with patch.object(policy, "__file__", str(self.repo / "checker.py")), self.assertRaisesRegex(ValueError, "consumer"):
            self.check()

    def test_provider_bound_fork_head_is_supported_without_selecting_sources(self):
        self.event["pull_request"]["head"]["repo"] = {
            "id": 456, "full_name": "contributor/example", "html_url": "https://github.com/contributor/example"}
        self.save_event()
        self.assertTrue(self.check())
        tree = self.git("rev-parse", "HEAD^{tree}")
        merged = self.git("commit-tree", tree, "-p", self.base, "-p", self.head, "-m", "fork merge")
        self.git("checkout", "--detach", merged)
        self.env["GITHUB_SHA"] = merged
        self.assertTrue(self.check())
        wrong = self.git("commit-tree", tree, "-p", self.head, "-p", self.base, "-m", "wrong parents")
        self.git("checkout", "--detach", wrong)
        self.env["GITHUB_SHA"] = wrong
        with self.assertRaisesRegex(ValueError, "exact base/head merge"):
            self.check()

    def test_head_repository_identity_collisions_are_refused(self):
        for name, identity in (("contributor/example", 123), ("ForgingAlpha/example", 456),
                               ("contributor/example", True), ("invalid-name", 456)):
            with self.subTest(name=name, identity=identity):
                self.event["pull_request"]["head"]["repo"] = {
                    "id": identity, "full_name": name, "html_url": "https://github.com/" + name}
                self.save_event()
                with self.assertRaisesRegex(ValueError, "head repository identity"):
                    self.check()

    def test_invalid_event_shapes_and_boolean_repository_identity_refuse(self):
        original = json.dumps(self.event)
        for repository in ([], None, {"id": True, "full_name": "ForgingAlpha/example"}):
            self.event = json.loads(original)
            self.event["repository"] = repository
            self.save_event()
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                self.check()

    def test_exact_synthetic_merge_checkout(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        merged = self.git("commit-tree", tree, "-p", self.base, "-p", self.head, "-m", "test merge")
        self.git("checkout", "--detach", merged)
        self.env["GITHUB_SHA"] = merged
        self.assertTrue(self.check())
        self.git("checkout", "--detach", self.head)
        self.assertTrue(self.check())

    def test_protected_push_and_forced_push(self):
        self.event = {"repository": self.event["repository"], "ref": "refs/heads/main",
                      "before": self.base, "after": self.head, "created": False, "deleted": False, "forced": False}
        self.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main")
        self.save_event()
        self.assertTrue(self.check())
        self.event["forced"] = True
        self.save_event()
        with self.assertRaisesRegex(ValueError, "forced"):
            self.check()


if __name__ == "__main__":
    unittest.main()
