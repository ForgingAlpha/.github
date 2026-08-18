from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "actions" / "ci-runtime-profile" / "scripts" / "validate_runtime_profile.py"
CATALOG = ROOT / "runtime-profiles" / "catalog.json"
ACTION = ROOT / "actions" / "ci-runtime-profile" / "action.yml"

spec = importlib.util.spec_from_file_location("runtime_profile", SCRIPT)
assert spec and spec.loader
runtime_profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime_profile)


class RuntimeProfileTest(unittest.TestCase):
    def setUp(self):
        self.catalog = runtime_profile.load_json(CATALOG)
        self.mise_toml = {"tools": {"node": "24.18.0"}}
        self.policy = {"schema_version": 1, "runtime_profile": "node-24-site"}
        self.mise_lock = {
            "tools": {
                "node": [
                    {
                        "version": "24.18.0",
                        "backend": "core:node",
                        **{
                            f"platforms.{platform}": {
                                "url": f"https://nodejs.org/dist/v24.18.0/node-{platform}.tar.gz",
                                "checksum": "sha256:" + "a" * 64,
                            }
                            for platform in ["linux-x64", "macos-arm64", "macos-x64"]
                        },
                    }
                ]
            }
        }
        self.analyzingalpha_mise_lock = {
            "tools": {
                "node": [
                    {
                        "version": "24.18.0",
                        "backend": "core:node",
                        "platforms.linux-arm64": {
                            "checksum": "sha256:6b4484c2190274175df9aa8f28e2d758a819cb1c1fe6ab481e2f95b463ab8508",
                            "url": "https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-arm64.tar.gz",
                        },
                        "platforms.linux-x64": {
                            "checksum": "sha256:783130984963db7ba9cbd01089eaf2c2efb055c7c1693c943174b967b3050cb8",
                            "url": "https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-x64.tar.gz",
                        },
                        "platforms.macos-arm64": {
                            "checksum": "sha256:e1a97e14c99c803e96c7339403282ea05a499c32f8d83defe9ef5ec66f979ed1",
                            "url": "https://nodejs.org/dist/v24.18.0/node-v24.18.0-darwin-arm64.tar.gz",
                        },
                        "platforms.macos-x64": {
                            "checksum": "sha256:dfd0dbd3e721503434df7b7205e719f61b3a3a31b2bcf9729b8b91fea240f080",
                            "url": "https://nodejs.org/dist/v24.18.0/node-v24.18.0-darwin-x64.tar.gz",
                        },
                        "platforms.windows-x64": {
                            "checksum": "sha256:0ae68406b42d7725661da979b1403ec9926da205c6770827f33aac9d8f26e821",
                            "url": "https://nodejs.org/dist/v24.18.0/node-v24.18.0-win-x64.zip",
                        },
                    }
                ]
            }
        }

    def assert_invalid_projection(self, fragment: str, mise_toml=None, mise_lock=None):
        with self.assertRaisesRegex(runtime_profile.ProfileError, fragment):
            runtime_profile.validate_projection(
                self.catalog,
                "ForgingAlpha/alphaapps-site",
                self.mise_toml if mise_toml is None else mise_toml,
                self.mise_lock if mise_lock is None else mise_lock,
            )

    def test_published_catalog_and_action_contract(self):
        runtime_profile.validate_catalog(self.catalog)
        action = ACTION.read_text(encoding="utf-8")
        self.assertIn("RUNTIME_PROFILE_REPOSITORY: ${{ github.repository }}", action)
        self.assertIn("../../runtime-profiles/catalog.json", action)
        self.assertIn("--update-policy .github/update-policy.json", action)
        self.assertNotIn("github.token", action)
        self.assertNotIn("secrets.", action)

    def test_exact_projection_passes(self):
        runtime_profile.validate_policy_assignment(
            self.catalog, "ForgingAlpha/alphaapps-site", self.policy
        )
        tuple_id = runtime_profile.validate_projection(
            self.catalog, "ForgingAlpha/alphaapps-site", self.mise_toml, self.mise_lock
        )
        self.assertEqual(tuple_id, "node-24.18.0")

    def test_analyzingalpha_site_exact_existing_projection_passes(self):
        tuple_id = runtime_profile.validate_projection(
            self.catalog,
            "ForgingAlpha/analyzingalpha-site",
            self.mise_toml,
            self.analyzingalpha_mise_lock,
        )
        self.assertEqual(tuple_id, "node-24.18.0")

    def test_analyzingalpha_site_mismatched_projection_fails(self):
        mise_toml = copy.deepcopy(self.mise_toml)
        mise_toml["tools"]["node"] = "24.18.1"
        with self.assertRaisesRegex(runtime_profile.ProfileError, "do not equal assigned tuple"):
            runtime_profile.validate_projection(
                self.catalog,
                "ForgingAlpha/analyzingalpha-site",
                mise_toml,
                self.analyzingalpha_mise_lock,
            )

    def test_analyzingalpha_site_unassigned_projection_fails(self):
        catalog = copy.deepcopy(self.catalog)
        del catalog["assignments"]["ForgingAlpha/analyzingalpha-site"]
        with self.assertRaisesRegex(runtime_profile.ProfileError, "no runtime profile assignment"):
            runtime_profile.validate_projection(
                catalog,
                "ForgingAlpha/analyzingalpha-site",
                self.mise_toml,
                self.analyzingalpha_mise_lock,
            )

    def test_local_policy_must_select_central_assignment(self):
        policy = copy.deepcopy(self.policy)
        policy["runtime_profile"] = "another-profile"
        with self.assertRaisesRegex(runtime_profile.ProfileError, "does not equal assigned profile"):
            runtime_profile.validate_policy_assignment(
                self.catalog, "ForgingAlpha/alphaapps-site", policy
            )

    def test_unassigned_or_inactive_repository_fails(self):
        with self.assertRaisesRegex(runtime_profile.ProfileError, "no runtime profile assignment"):
            runtime_profile.validate_projection(
                self.catalog, "ForgingAlpha/unassigned", self.mise_toml, self.mise_lock
            )
        catalog = copy.deepcopy(self.catalog)
        catalog["assignments"]["ForgingAlpha/alphaapps-site"]["status"] = "planned"
        with self.assertRaisesRegex(runtime_profile.ProfileError, "not active"):
            runtime_profile.validate_projection(
                catalog, "ForgingAlpha/alphaapps-site", self.mise_toml, self.mise_lock
            )

    def test_mise_declaration_must_equal_entire_tuple(self):
        self.assert_invalid_projection("do not equal assigned tuple", {"tools": {"node": "24"}})
        self.assert_invalid_projection(
            "do not equal assigned tuple", {"tools": {"node": "24.18.0", "python": "3.14.1"}}
        )

    def test_lock_requires_exact_tool_version_platforms_and_checksum(self):
        lock = copy.deepcopy(self.mise_lock)
        lock["tools"]["node"][0]["version"] = "24.18.1"
        self.assert_invalid_projection("version does not equal", mise_lock=lock)

        lock = copy.deepcopy(self.mise_lock)
        del lock["tools"]["node"][0]["platforms.linux-x64"]
        self.assert_invalid_projection("missing platforms", mise_lock=lock)

        lock = copy.deepcopy(self.mise_lock)
        lock["tools"]["node"][0]["platforms.linux-x64"]["checksum"] = "sha256:short"
        self.assert_invalid_projection("lacks an exact SHA-256", mise_lock=lock)

    def test_lock_supports_multiple_entries_and_tools_without_direct_artifacts(self):
        catalog = copy.deepcopy(self.catalog)
        current = catalog["profiles"]["node-24-site"]["approved_tuples"][0]
        current["tools"] = {
            "erlang": {
                "version": "28.5.0.5",
                "required_platforms": ["linux-x64", "macos-arm64"],
            },
            "npm:npm": {"version": "11.13.0", "required_platforms": []},
        }
        mise_toml = {"tools": {"erlang": "28.5.0.5", "npm:npm": "11.13.0"}}
        mise_lock = {
            "tools": {
                "erlang": [
                    {
                        "version": "28.5.0.5",
                        "platforms.macos-arm64": {
                            "url": "https://example.test/otp-macos.tar.gz",
                            "checksum": "sha256:" + "a" * 64,
                        },
                    },
                    {
                        "version": "28.5.0.5",
                        "options": {"precompiled_os": "ubuntu-24.04"},
                        "platforms.linux-x64": {
                            "url": "https://example.test/otp-linux.tar.gz",
                            "checksum": "sha256:" + "b" * 64,
                        },
                    },
                ],
                "npm:npm": [{"version": "11.13.0", "backend": "npm:npm"}],
            }
        }
        self.assertEqual(
            runtime_profile.validate_projection(
                catalog, "ForgingAlpha/alphaapps-site", mise_toml, mise_lock
            ),
            "node-24.18.0",
        )

    def test_lock_rejects_untrusted_url_shape(self):
        for url in ["http://nodejs.org/node.tar.gz", "https://user:secret@nodejs.org/node.tar.gz"]:
            with self.subTest(url=url):
                lock = copy.deepcopy(self.mise_lock)
                lock["tools"]["node"][0]["platforms.linux-x64"]["url"] = url
                self.assert_invalid_projection("credential-free HTTPS", mise_lock=lock)

    def test_catalog_rejects_ambiguous_current_tuple_and_unused_profile(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"]["node-24-site"]["approved_tuples"].append(
            copy.deepcopy(catalog["profiles"]["node-24-site"]["approved_tuples"][0])
        )
        catalog["profiles"]["node-24-site"]["approved_tuples"][1]["id"] = "second-current"
        with self.assertRaisesRegex(runtime_profile.ProfileError, "exactly one current"):
            runtime_profile.validate_catalog(catalog)

        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"]["unused"] = copy.deepcopy(catalog["profiles"]["node-24-site"])
        with self.assertRaisesRegex(runtime_profile.ProfileError, "without an active assignment"):
            runtime_profile.validate_catalog(catalog)


if __name__ == "__main__":
    unittest.main()
