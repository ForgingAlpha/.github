"""Exercise the isolated site enrollment and the protected-dev first-release reader."""
import json
import os
from pathlib import Path
from subprocess import run
import sys
import unittest
from unittest.mock import patch

from four_section_fixture import KEY, MANIFEST, README, TRIO, details, documents

SCRIPTS = Path(__file__).resolve().parents[1] / "actions/ci-alphaapps-policy/scripts"
sys.path.insert(0, str(SCRIPTS.parent / "tests"))
import test_standalone_readme_intent as legacy


class SiteFirstPromotion(unittest.TestCase):
    def setUp(self):
        self.f = legacy.StandaloneIntentTest()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.site = {"id": 1151414035, "full_name": "ForgingAlpha/analyzingalpha-site",
                     "html_url": "https://github.com/ForgingAlpha/analyzingalpha-site"}
        self.f.env.update(GITHUB_REPOSITORY=self.site["full_name"], GITHUB_REPOSITORY_ID=str(self.site["id"]))
        self.f.git("remote", "set-url", "origin", self.site["html_url"])
        self.f.git("rm", "-r", "docs")
        self.f.write("README.md", b"# Legacy site\n")
        self.main = self.f.commit()
        self.f.write("README.md", README)
        self.f.write("docs/release-notes.md", b"# Release notes\n\nProject news.\n")
        for path, data in details().items():
            self.f.write(path, data)
        _, manifest = documents("dev")
        self.manifest = json.loads(json.dumps(manifest))
        self.write_manifest()
        self.dev = self.f.commit()
        for selection in [self.manifest[KEY], self.manifest["source_metadata"][TRIO[1]][KEY]]:
            selection["main"] = ["."]
        self.write_manifest()
        self.enrolled = self.f.commit()

    def write_manifest(self):
        self.f.write(MANIFEST, (json.dumps(self.manifest, indent=2) + "\n").encode())

    def merge(self, base, head, tree=None):
        return self.f.git("commit-tree", tree or head + "^{tree}", "-p", base, "-p", head, "-m", "merge")

    def pr(self, branch, base, source, head, *, tree=None):
        merge = self.merge(base, head, tree)
        self.f.git("checkout", "--detach", merge)
        self.f.git("update-ref", "refs/remotes/origin/" + branch, base)
        self.f.env.update(GITHUB_EVENT_NAME="pull_request", GITHUB_BASE_REF=branch, GITHUB_HEAD_REF=source,
                          GITHUB_SHA=merge, GITHUB_REF="refs/pull/7/merge")
        self.f.event = {"number": 7, "repository": self.site,
                        "pull_request": {"number": 7, "base": {"repo": self.site, "ref": branch, "sha": base},
                                         "head": {"repo": self.site, "ref": source, "sha": head}}}
        self.f.save_event()
        return merge

    def cli(self, success, reason):
        result = run([sys.executable, "-I", "-B", str(SCRIPTS / "validate_product_lifecycle_baseline.py")],
                     cwd=self.f.repo, env=os.environ | self.f.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        self.assertIn(reason, result.stdout + result.stderr)

    def push(self, branch, before, after):
        ref = "refs/heads/" + branch
        self.f.git("update-ref", "refs/remotes/origin/" + branch, after)
        self.f.git("checkout", "--detach", after)
        self.f.event = {"repository": self.site, "ref": ref, "before": before, "after": after,
                        "created": False, "deleted": False, "forced": False}
        self.f.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF=ref, GITHUB_SHA=after)
        self.f.save_event()

    def test_enrollment_pr_push_and_later_ordinary_main(self):
        adopted = self.pr("dev", self.dev, "task", self.enrolled)
        self.cli(True, "dev enrollment passed")
        self.push("dev", self.dev, adopted)
        self.cli(True, "dev enrollment passed")
        self.push("dev", self.dev, self.enrolled)
        self.cli(False, "must be the exact reviewed source tree")
        self.f.git("checkout", "--detach", adopted)
        self.pr("main", adopted, "dev", self.f.commit())
        self.cli(True, "approved-structure passed")

    def test_enrollment_rejects_other_bytes_or_missing_mirror(self):
        candidate = self.f.repo / MANIFEST
        candidate.write_bytes(candidate.read_bytes() + b"\n")
        self.pr("dev", self.dev, "task", self.f.commit())
        self.cli(False, "two identical main scopes")
        del self.manifest["source_metadata"][TRIO[1]][KEY]["main"]
        self.write_manifest()
        self.pr("dev", self.dev, "task", self.f.commit())
        self.cli(False, "two identical main scopes")
        self.write_manifest()
        self.f.write("product.js", b"// product\n")
        self.pr("dev", self.dev, "task", self.f.commit())
        self.cli(False, "only the root source manifest")

    def test_enrollment_uses_site_identity_same_repo_and_trusted_action(self):
        self.pr("dev", self.dev, "task", self.enrolled)
        self.f.env["POLICY_ACTION_REF"] = "task"
        self.cli(False, "protected remote policy action")
        self.f.env["POLICY_ACTION_REF"] = "main"
        self.f.event["pull_request"]["head"]["repo"] = {"id": 101, "full_name": "other/site",
                                                        "html_url": "https://github.com/other/site"}
        self.f.save_event()
        self.cli(False, "same-repository pull request")
        self.site["id"] = 123
        self.f.env["GITHUB_REPOSITORY_ID"] = "123"
        self.pr("dev", self.dev, "task", self.enrolled)
        self.cli(False, "cannot enroll its own conversion")

    def test_release_requires_exact_legacy_base_protected_source_and_test_merge(self):
        self.f.git("update-ref", "refs/remotes/origin/dev", self.enrolled)
        self.pr("main", self.main, "dev", self.enrolled)
        self.cli(False, "inspected legacy main")
        # Only the inspected legacy commit is site-specific. Substitute this
        # fixture's seed for positive coverage without adding a runtime override.
        with patch.object(legacy.route, "LEGACY_SITE_MAIN", self.main):
            self.assertTrue(self.f.check())
            self.pr("main", self.main, "feature", self.enrolled)
            with self.assertRaisesRegex(ValueError, "current protected dev head"):
                self.f.check()
            self.pr("main", self.main, "dev", self.enrolled)
            self.f.git("update-ref", "refs/remotes/origin/dev", self.dev)
            with self.assertRaisesRegex(ValueError, "current protected dev head"):
                self.f.check()
            self.f.git("update-ref", "refs/remotes/origin/dev", self.enrolled)
            self.pr("main", self.main, "dev", self.enrolled, tree=self.dev + "^{tree}")
            with self.assertRaisesRegex(ValueError, "test merge differs"):
                self.f.check()
            self.f.git("checkout", "--detach", self.enrolled)
            self.f.env["GITHUB_SHA"] = self.enrolled
            with self.assertRaisesRegex(ValueError, "checked provider test merge"):
                self.f.check()
            self.push("main", self.main, self.merge(self.main, self.enrolled))
            with self.assertRaisesRegex(ValueError, "on push"):
                self.f.check()

    def test_release_requires_ancestry_and_complete_approved_snapshot(self):
        orphan = self.f.git("commit-tree", self.enrolled + "^{tree}", "-m", "unrelated history")
        with patch.object(legacy.route, "LEGACY_SITE_MAIN", self.main):
            self.f.git("update-ref", "refs/remotes/origin/dev", orphan)
            self.pr("main", self.main, "dev", orphan)
            with self.assertRaisesRegex(ValueError, "Git evidence unavailable"):
                self.f.check()
            for path, data, message in [
                ("component/docs/governing-source-bindings.json", b'{}', "unexpected governing manifest"),
                ("component/README.md", README, "unregistered governing scope"),
                ("component/docs/requirements.md", b'# Requirements', "unregistered governing source"),
                ("README.md", README.replace(b"original observations", b"changed observations"), "digest"),
            ]:
                with self.subTest(path=path):
                    self.f.git("checkout", "--detach", self.enrolled)
                    self.f.write(path, data)
                    head = self.f.commit()
                    self.f.git("update-ref", "refs/remotes/origin/dev", head)
                    self.pr("main", self.main, "dev", head)
                    with self.assertRaisesRegex(ValueError, message):
                        self.f.check()
            self.f.git("checkout", "--detach", self.enrolled)
            self.manifest["source_metadata"][TRIO[1]]["status"] = "provisional"
            self.write_manifest()
            head = self.f.commit()
            self.f.git("update-ref", "refs/remotes/origin/dev", head)
            self.pr("main", self.main, "dev", head)
            with self.assertRaisesRegex(ValueError, "requires approved"):
                self.f.check()
