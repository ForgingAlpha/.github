import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-dependency-review" / "action.yml"
SCRIPT = ROOT / "actions" / "ci-dependency-review" / "scripts" / "validate_license_evidence.py"
POLICY = ROOT / "actions" / "ci-dependency-review" / "scripts" / "license_policy.py"
OFFICIAL_ACTION = "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294"
CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
FIRST_PARTY_COMMIT = "a" * 40
FIRST_PARTY_TREE = "d" * 40
FIRST_PARTY_BLOB = "b" * 40

sys.path.insert(0, str(SCRIPT.parent))
validator_spec = importlib.util.spec_from_file_location("license_evidence_validator", SCRIPT)
assert validator_spec and validator_spec.loader
validator = importlib.util.module_from_spec(validator_spec)
sys.modules[validator_spec.name] = validator
validator_spec.loader.exec_module(validator)


class CiDependencyReviewTest(unittest.TestCase):
    def load_action(self):
        return yaml.safe_load(ACTION.read_text(encoding="utf-8"))

    def test_explicit_workspace_interface_preserves_legacy_default(self):
        action=self.load_action()
        self.assertEqual(action["inputs"]["workspace"]["default"],"${{ github.workspace }}")
        step=next(s for s in action["runs"]["steps"] if s.get("name")=="Validate dependency license evidence")
        self.assertEqual(step["env"]["DEPENDENCY_WORKSPACE"],"${{ inputs.workspace }}")
        self.assertEqual(step["env"]["GITHUB_LICENSE_TOKEN"],"${{ github.token }}")
        self.assertTrue(any(s.get("uses")==OFFICIAL_ACTION for s in action["runs"]["steps"]))

    def test_explicit_secondary_workspace_wins_over_decoy_default(self):
        aliases = (("tool-alias", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        concrete = {
            "change_type": "added", "ecosystem": "npm", "manifest": "package-lock.json",
            "name": "real-tool", "version": "1.2.3", "package_url": "pkg:npm/real-tool@1.2.3",
            "license": "Apache-2.0",
        }
        with self.npm_alias_workspace(aliases) as consumer, tempfile.TemporaryDirectory() as decoy, mock.patch.object(
            validator, "fetch_npm_registry_release"
        ) as fetch:
            Path(decoy, "package.json").write_text('{}')
            Path(decoy, "package-lock.json").write_text('{}')
            environment = {"GITHUB_WORKSPACE": decoy, "DEPENDENCY_WORKSPACE": str(consumer)}
            code, _, error = self.run_main([change, concrete], extra_env=environment)
            self.assertEqual(code, 0, error)
            lock = consumer / "package-lock.json"
            value = json.loads(lock.read_text())
            value["packages"]["node_modules/tool-alias"]["version"] = "9.9.9"
            lock.write_text(json.dumps(value))
            code, _, _ = self.run_main([change, concrete], extra_env=environment)
            self.assertNotEqual(code, 0)
            fetch.assert_not_called()

    def run_validator(self, changes, token=None, extra_env=None):
        value = changes if isinstance(changes, str) else json.dumps(changes)
        env = {**os.environ, "DEPENDENCY_CHANGES": value, "DEPENDENCY_REPOSITORY": "ForgingAlpha/test-repo"}
        env.pop("GITHUB_LICENSE_TOKEN", None)
        if token is not None:
            env["GITHUB_LICENSE_TOKEN"] = token
        if extra_env is not None:
            env.update(extra_env)
        return subprocess.run(
            ["python3", str(SCRIPT)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def run_main(self, changes, token="test-token", extra_env=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        env = {"DEPENDENCY_CHANGES": json.dumps(changes), "GITHUB_LICENSE_TOKEN": token, "DEPENDENCY_REPOSITORY": "ForgingAlpha/test-repo"}
        if extra_env is not None:
            env.update(extra_env)
        with mock.patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                return validator.main(), stdout.getvalue(), stderr.getvalue()

    def first_party_change(self, action="ci-merge-flow", source=...):
        change = {
            "change_type": "added",
            "ecosystem": "actions",
            "name": f"ForgingAlpha/.github/actions/{action}",
            "version": "main",
            "package_url": (
                f"pkg:githubactions/ForgingAlpha/.github/actions/{action}@main"
            ),
            "license": None,
        }
        if source is not ...:
            change["source_repository_url"] = source
        return change

    def first_party_api_responses(self, paths=("actions/ci-merge-flow/action.yml",)):
        ref = {
            "ref": "refs/heads/main",
            "object": {"type": "commit", "sha": FIRST_PARTY_COMMIT},
        }
        tree = {
            "sha": FIRST_PARTY_TREE,
            "truncated": False,
            "tree": [
                {"path": path, "type": "blob", "mode": "100644", "sha": FIRST_PARTY_BLOB, "size": 123}
                for path in paths
            ],
        }
        return [
            io.BytesIO(json.dumps(ref).encode()),
            io.BytesIO(json.dumps(tree).encode()),
        ]

    def npm_alias_change(self, alias, target, version):
        encoded_alias = f"%40{alias[1:]}" if alias.startswith("@") else alias
        return {
            "change_type": "added",
            "ecosystem": "npm",
            "manifest": "package.json",
            "name": alias,
            "version": f"npm:{target}@{version}",
            "package_url": f"pkg:npm/{encoded_alias}",
            "license": None,
            "source_repository_url": None,
            "scope": "development",
            "vulnerabilities": [],
        }

    @contextlib.contextmanager
    def npm_alias_workspace(self, aliases):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            exact_specs = {
                alias: f"npm:{target}@{version}" for alias, target, version in aliases
            }
            descriptors = {}
            for alias, target, version in aliases:
                basename = target.split("/", 1)[-1]
                descriptors[f"node_modules/{alias}"] = {
                    "name": target,
                    "version": version,
                    "resolved": (
                        f"https://registry.npmjs.org/{target}/-/"
                        f"{basename}-{version}.tgz"
                    ),
                    "integrity": "sha512-" + "A" * 86 + "==",
                    "dev": True,
                    "license": "Apache-2.0",
                }
            manifest = {
                "name": "alias-test",
                "version": "1.0.0",
                "devDependencies": exact_specs,
            }
            lock = {
                "name": "alias-test",
                "version": "1.0.0",
                "lockfileVersion": 3,
                "requires": True,
                "packages": {
                    "": {
                        "name": "alias-test",
                        "version": "1.0.0",
                        "devDependencies": exact_specs,
                    },
                    **descriptors,
                },
            }
            (workspace / "package.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (workspace / "package-lock.json").write_text(
                json.dumps(lock), encoding="utf-8"
            )
            yield workspace

    def npm_registry_payload(self, target, version, license_value="Apache-2.0"):
        basename = target.split("/", 1)[-1]
        return {
            "name": target,
            "version": version,
            "license": license_value,
            "dist": {
                "tarball": (
                    f"https://registry.npmjs.org/{target}/-/"
                    f"{basename}-{version}.tgz"
                ),
                "integrity": "sha512-" + "A" * 86 + "==",
            },
        }

    def artifact_change(self):
        # Actual dependency-review identity; independent constants avoid deriving
        # all positive evidence from the policy under test.
        return {
            "change_type": "added", "ecosystem": "npm", "name": "mapbox-gl",
            "version": "3.31.0", "manifest": "assets/customer/package-lock.json",
            "package_url": "pkg:npm/mapbox-gl@3.31.0",
            "source_repository_url": "https://github.com/mapbox/mapbox-gl-js",
            "license": "LicenseRef-bad-see-license-in-license.txt",
            "scope": "runtime", "vulnerabilities": [],
        }

    @contextlib.contextmanager
    def artifact_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            customer = workspace / "assets/customer"
            customer.mkdir(parents=True)
            manifest = {"dependencies": {"mapbox-gl": "^3.31.0"}}
            lock = {
                "lockfileVersion": 3,
                "packages": {
                    "": copy.deepcopy(manifest),
                    "node_modules/mapbox-gl": {
                        "version": "3.31.0",
                        "resolved": "https://registry.npmjs.org/mapbox-gl/-/mapbox-gl-3.31.0.tgz",
                        "integrity": "sha512-7i25NyCPW5jnqsqJq3irgBBEoVTJgfZqTJJS446Q3ZuxyAb5Om75UIcxYIo38oz9eDswnBXr0riz+M/C8V7g3Q==",
                        "license": "SEE LICENSE IN LICENSE.txt",
                    },
                },
            }
            (customer / "package.json").write_text(json.dumps(manifest))
            (customer / "package-lock.json").write_text(json.dumps(lock))
            yield workspace

    def run_artifact(self, workspace, changes=None):
        return self.run_main(
            [self.artifact_change()] if changes is None else changes,
            extra_env={"DEPENDENCY_WORKSPACE": str(workspace),
                       "DEPENDENCY_REPOSITORY": "ForgingAlpha/turnkeyleads-app"},
        )

    def test_artifact_exclusion_is_emitted_only_for_exact_central_repository(self):
        for repository, expected in [
            ("ForgingAlpha/turnkeyleads-app", "pkg:npm/mapbox-gl"),
            ("ForgingAlpha/test-repo", ""),
            ("someone/turnkeyleads-app", ""),
            ("forgingalpha/turnkeyleads-app", ""),
        ]:
            with self.subTest(repository=repository):
                result = subprocess.run(
                    ["python3", str(POLICY)], capture_output=True, text=True,
                    env={**os.environ, "DEPENDENCY_REPOSITORY": repository}, check=True,
                )
                outputs = dict(line.split("=", 1) for line in result.stdout.splitlines())
                self.assertEqual(outputs["allow_dependencies_licenses"], expected)
                self.assertNotIn("LicenseRef", outputs["allow_licenses"])

    def test_both_policy_stages_reject_missing_or_malformed_repository(self):
        for repository in ("", "owner", "owner/repo/extra", "owner/repo\n"):
            with self.subTest(repository=repository):
                result = subprocess.run(
                    ["python3", str(POLICY)], capture_output=True, text=True,
                    env={**os.environ, "DEPENDENCY_REPOSITORY": repository},
                )
                self.assertNotEqual(result.returncode, 0)
                code, _, stderr = self.run_main([], extra_env={"DEPENDENCY_REPOSITORY": repository})
                self.assertEqual(code, 1)
                self.assertIn("repository identity", stderr)

    def test_exact_artifact_passes_without_network_and_ignores_removed_old_version(self):
        with self.artifact_workspace() as workspace:
            removed = {**self.artifact_change(), "change_type": "removed", "version": "3.22.0"}
            with mock.patch.object(
                validator.urllib.request, "urlopen", side_effect=AssertionError("network lookup")
            ) as lookup, mock.patch.object(
                validator.urllib.request, "build_opener", side_effect=AssertionError("network opener")
            ) as opener:
                code, stdout, stderr = self.run_artifact(workspace, [removed, self.artifact_change()])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Verified reviewed artifact pkg:npm/mapbox-gl@3.31.0", stdout)
            lookup.assert_not_called()
            opener.assert_not_called()

    def test_artifact_policy_agrees_with_retained_preparation_receipt(self):
        policy = validator.artifact_exception("ForgingAlpha/turnkeyleads-app")
        receipt = json.loads(
            (ROOT / "docs/audits/2026-09-26-mapbox-3.31.0-artifact.json").read_text()
        )
        for policy_field, receipt_field in (
            ("resolved", "source_url"), ("version", "version"),
            ("integrity", "expected_sri"), ("integrity", "actual_sri"),
            ("archive_sha256", "archive_sha256"), ("license_member", "member"),
            ("license_sha256", "license_sha256"),
        ):
            self.assertEqual(policy[policy_field], receipt[receipt_field])
        self.assertTrue(validator.is_sha512_integrity(policy["integrity"]))
        for field in ("archive_sha256", "license_sha256"):
            self.assertRegex(policy[field], r"^[0-9a-f]{64}$")
        self.assertEqual(policy["resolved"], validator.npm_registry_tarball(policy["name"], policy["version"]))
        self.assertEqual(policy["package_url"], f"{validator.npm_purl(policy['name'])}@{policy['version']}")
        self.assertEqual(policy["package_path"], f"node_modules/{policy['name']}")
        self.assertIs(receipt["sri_verified"], True)
        self.assertIs(receipt["license_hash_verified"], True)
        self.assertIs(receipt["unique_member"], True)
        self.assertEqual(receipt["member_type"], "regular")
        for measured, limit in (
            ("archive_bytes", "compressed_bytes"), ("expanded_bytes_read", "expanded_bytes"),
            ("archive_members_scanned", "member_count"), ("license_bytes", "license_bytes"),
        ):
            self.assertGreater(receipt[measured], 0)
            self.assertLessEqual(receipt[measured], receipt["bounds"][limit])

    def test_other_repository_does_not_claim_artifact_approval(self):
        # Neither stage may admit this custom license outside its exact exception.
        code, stdout, stderr = self.run_main([self.artifact_change()], token="")
        self.assertEqual(code, 1, stderr)
        self.assertIn("unapproved or malformed license expression", stderr)
        self.assertNotIn("Verified reviewed artifact", stdout)

    def test_artifact_guard_rejects_mismatched_or_missing_change_evidence(self):
        mutations = {
            "version": "3.32.0", "manifest": "other/package-lock.json", "name": "other",
            "package_url": "pkg:npm/mapbox-gl@3.32.0", "ecosystem": "pypi",
            "source_repository_url": "https://github.com/someone/mapbox-gl-js",
            "license": "GPL-3.0-only", "scope": "development", "vulnerabilities": None,
        }
        with self.artifact_workspace() as workspace:
            for field, value in mutations.items():
                for missing in (False, True):
                    with self.subTest(field=field, missing=missing):
                        change = self.artifact_change()
                        if missing:
                            change.pop(field)
                        else:
                            change[field] = value
                        code, _, stderr = self.run_artifact(workspace, [change])
                        self.assertEqual(code, 1, stderr)

    def test_version_blind_encoded_and_case_exclusions_cannot_skip_artifact_guard(self):
        # Pinned official purlsMatch compares decoded, case-insensitive names and
        # ignores version. The independent guard must run before nonempty license.
        purls = [
            "pkg:npm/mapbox-gl@3.32.0", "pkg:NPM/MAPBOX-GL@3.22.0",
            "pkg:npm/%6dapbox-gl@3.32.0", "pkg:npm/mapbox%2Dgl@3.32.0",
            "pkg:npm/@mapbox-gl", "pkg:npm/mapbox-gl?x=1",
            "pkg:npm/mapbox-gl/#", "pkg:npm/mapbox-gl@3.31.0#subpath",
        ]
        with self.artifact_workspace() as workspace:
            for purl in purls:
                with self.subTest(purl=purl):
                    change = {**self.artifact_change(), "name": "contradictory-name",
                              "package_url": purl, "license": "GPL-3.0-only"}
                    self.assertTrue(validator.matches_exception_family(change, "mapbox-gl"))
                    self.assertEqual(self.run_artifact(workspace, [change])[0], 1)

    def test_valid_artifact_cannot_cover_duplicate_or_additional_package_evidence(self):
        with self.artifact_workspace() as workspace:
            for extra in [self.artifact_change(), {**self.artifact_change(), "version": "3.32.0"},
                          {**self.artifact_change(), "manifest": "another/package-lock.json"}]:
                code, _, stderr = self.run_artifact(workspace, [self.artifact_change(), extra])
                self.assertEqual(code, 1, stderr)
                self.assertIn("duplicate", stderr)

    def test_artifact_lock_rejects_changed_bytes_location_or_additional_install(self):
        descriptor_mutations = [
            {"version": "3.32.0"}, {"resolved": "https://example.com/mapbox.tgz"},
            {"integrity": "sha512-" + "A" * 86 + "=="}, {"license": "MIT"},
            {"name": "other"},
            *({"link": value} for value in (True, [], {}, "", 0, None)),
        ]
        for mutation in descriptor_mutations + ["missing", "nested", "alias", "old-format"]:
            with self.subTest(mutation=mutation), self.artifact_workspace() as workspace:
                path = workspace / "assets/customer/package-lock.json"
                lock = json.loads(path.read_text())
                descriptor = lock["packages"]["node_modules/mapbox-gl"]
                if isinstance(mutation, dict):
                    descriptor.update(mutation)
                elif mutation == "missing":
                    del lock["packages"]["node_modules/mapbox-gl"]
                elif mutation == "nested":
                    lock["packages"]["node_modules/other/node_modules/mapbox-gl"] = descriptor.copy()
                elif mutation == "alias":
                    lock["packages"]["node_modules/alias"] = {**descriptor, "name": "mapbox-gl"}
                else:
                    lock["lockfileVersion"] = 2
                path.write_text(json.dumps(lock))
                self.assertEqual(self.run_artifact(workspace)[0], 1)

    def test_artifact_manifest_and_root_lock_must_agree_with_reviewed_version(self):
        for spec, root_spec, extra, expected in [
            ("3.31.0", "3.31.0", False, 0), ("^3.31.0", "^3.31.0", False, 0),
            ("^3.31.0", "3.31.0", False, 1), ("^3.32.0", "^3.32.0", False, 1),
            ("^3.31.0", "^3.31.0", True, 1),
        ]:
            with self.subTest(spec=spec, root_spec=root_spec, extra=extra), self.artifact_workspace() as workspace:
                manifest_path = workspace / "assets/customer/package.json"
                lock_path = workspace / "assets/customer/package-lock.json"
                manifest = json.loads(manifest_path.read_text())
                lock = json.loads(lock_path.read_text())
                manifest["dependencies"]["mapbox-gl"] = spec
                lock["packages"][""]["dependencies"]["mapbox-gl"] = root_spec
                if extra:
                    manifest["devDependencies"] = {"mapbox-gl": spec}
                manifest_path.write_text(json.dumps(manifest))
                lock_path.write_text(json.dumps(lock))
                code, _, stderr = self.run_artifact(workspace)
                self.assertEqual(code, expected, stderr)

    def test_artifact_evidence_rejects_missing_duplicate_oversized_and_symlink_files(self):
        for invalid in ("missing", "duplicate", "oversized", "file-link", "directory-link"):
            with self.subTest(invalid=invalid), self.artifact_workspace() as workspace:
                path = workspace / "assets/customer/package-lock.json"
                if invalid == "missing":
                    path.unlink()
                elif invalid == "duplicate":
                    path.write_text('{"lockfileVersion":3,"lockfileVersion":3}')
                elif invalid == "oversized":
                    with path.open("wb") as handle:
                        handle.truncate(validator.MAX_NPM_JSON_BYTES + 1)
                elif invalid == "file-link":
                    real = workspace / "real-lock.json"
                    path.rename(real)
                    path.symlink_to(real)
                else:
                    real = workspace / "real-customer"
                    path.parent.rename(real)
                    path.parent.symlink_to(real, target_is_directory=True)
                self.assertEqual(self.run_artifact(workspace)[0], 1)

    def test_contract_has_no_caller_bypass_or_license_override(self):
        action = self.load_action()
        self.assertEqual(set(action["inputs"]), {"workspace"})
        text = ACTION.read_text(encoding="utf-8")
        for obsolete in ("enabled", "deny-licenses", "warn-only"):
            self.assertNotIn(obsolete, text)

    def test_official_review_uses_strict_central_policy(self):
        action = self.load_action()
        policy = next(step for step in action["runs"]["steps"] if step.get("id") == "license-policy")
        review = next(step for step in action["runs"]["steps"] if step.get("uses") == OFFICIAL_ACTION)

        self.assertEqual(policy["if"], "${{ github.event_name == 'pull_request' }}")
        self.assertEqual(
            policy["run"],
            'python3 "$GITHUB_ACTION_PATH/scripts/license_policy.py" >> "$GITHUB_OUTPUT"',
        )
        self.assertEqual(policy["env"]["DEPENDENCY_REPOSITORY"], "${{ github.repository }}")
        self.assertEqual(
            review["with"]["allow-dependencies-licenses"],
            "${{ steps.license-policy.outputs.allow_dependencies_licenses }}",
        )
        self.assertEqual(review["id"], "review")
        self.assertEqual(review["if"], "${{ github.event_name == 'pull_request' }}")
        self.assertEqual(review["with"]["fail-on-severity"], "low")
        self.assertEqual(review["with"]["fail-on-scopes"], "runtime,development,unknown")
        self.assertEqual(
            review["with"]["allow-licenses"],
            "${{ steps.license-policy.outputs.allow_licenses }}",
        )

        policy_result = subprocess.run(
            ["python3", str(POLICY)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            env={**os.environ, "DEPENDENCY_REPOSITORY": "ForgingAlpha/test-repo"},
        )
        outputs = dict(line.split("=", 1) for line in policy_result.stdout.splitlines())
        self.assertEqual(outputs["allow_dependencies_licenses"], "")
        allowlist = outputs["allow_licenses"].split(",")
        for expected in ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC"):
            self.assertIn(expected, allowlist)

    def test_non_pull_request_skip_is_explanatory(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("not applicable outside pull_request", text)
        self.assertIn("WHAT:", text)
        self.assertIn("WHY:", text)
        self.assertIn("HOW:", text)

    def test_missing_license_guard_runs_even_if_official_review_fails(self):
        action = self.load_action()
        guard = next(
            step for step in action["runs"]["steps"] if step.get("name") == "Validate dependency license evidence"
        )
        self.assertIn("always()", guard["if"])
        self.assertEqual(guard["env"]["DEPENDENCY_REPOSITORY"], "${{ github.repository }}")
        self.assertEqual(
            guard["env"]["DEPENDENCY_CHANGES"],
            "${{ steps.review.outputs.dependency-changes }}",
        )
        self.assertEqual(guard["env"]["GITHUB_LICENSE_TOKEN"], "${{ github.token }}")
        self.assertNotIn("DEPENDENCY_BASE_SHA", guard["env"])
        self.assertEqual(
            guard["env"]["DEPENDENCY_WORKSPACE"],
            "${{ inputs.workspace }}",
        )

    def test_validator_accepts_known_license_and_ignores_removals(self):
        result = self.run_validator(
            [
                {"change_type": "added", "package_url": "pkg:npm/good@1", "license": "MIT"},
                {"change_type": "removed", "package_url": "pkg:npm/old@1", "license": None},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_recognized_license_does_not_use_fallback_or_require_token(self):
        changes = [{"change_type": "added", "package_url": "pkg:npm/good@1", "license": "MIT"}]
        with mock.patch.object(validator, "fetch_github_license") as fetch, mock.patch.object(
            validator, "fetch_first_party_main_tree"
        ) as first_party_fetch:
            code, _, stderr = self.run_main(changes, token="")
            self.assertEqual(code, 0, stderr)
        fetch.assert_not_called()
        first_party_fetch.assert_not_called()

    def test_real_astro_licenses_and_complete_approved_alternatives_pass(self):
        expressions = (
            "LGPL-3.0-or-later",
            "Apache-2.0 AND LGPL-3.0-or-later",
            "Apache-2.0 AND LGPL-3.0-or-later AND MIT",
            "0BSD", "BSD-3-Clause", "ISC",
            "MIT OR GPL-3.0-only",
            "MIT AND (Apache-2.0 OR GPL-3.0-only)",
            "(MIT OR LGPL-2.1-or-later) AND Apache-2.0",
            "(Apache-2.0 WITH LLVM-exception) OR MIT",
            "MIT OR LicenseRef-unknown",
            "MIT OR LicenseRef-X.OTHER",
            "MIT OR DocumentRef-X.OTHER:LicenseRef-unknown",
        )
        changes = [
            {"change_type": "added", "package_url": f"pkg:npm/example-{index}@1", "license": expression}
            for index, expression in enumerate(expressions)
        ]
        with mock.patch.object(validator, "fetch_github_license") as github_lookup, mock.patch.object(
            validator, "fetch_npm_registry_release"
        ) as npm_lookup:
            code, _, stderr = self.run_main(changes, token="")
        self.assertEqual(code, 0, stderr)
        github_lookup.assert_not_called()
        npm_lookup.assert_not_called()

    def test_guard_rejects_unapproved_ranges_and_malformed_raw_license_evidence(self):
        expressions = (
            "LGPL-3.0-only", "LGPL-2.1-or-later", "LGPL-2.1-only",
            "GPL-3.0-only", "AGPL-3.0-only", "MPL-2.0",
            "MIT AND GPL-3.0-only", "Apache-2.0 WITH LLVM-exception",
            "MIT WITH LLVM-exception AND Apache-2.0",
            "NOASSERTION", "LicenseRef-unknown",
            "OTHER", "MIT OR OTHER", "OTHER OR MIT", "MIT OR OTHER.0",
            "MIT AND (Apache-2.0 OR OTHER)", "MIT OR OTHER:LicenseRef-X",
            "MIT OR", "MIT AND", "MIT Apache-2.0",
            "MIT || Apache-2.0", "MIT && Apache-2.0", "MIT;True",
            "__import__(os)", "not MIT", "MIT == MIT", "MIT(MIT)",
            "()", "(MIT", "MIT)", "MIT WITH", "WITH MIT",
            "MIT WITH LLVM-exception WITH Autoconf-exception-3.0",
            "MIT OR (Apache-2.0 AND)",
            "MIT and Apache-2.0", "MIT oR LGPL-3.0-only",
        )
        for expression in expressions:
            with self.subTest(expression=expression):
                change = {"change_type": "added", "package_url": "pkg:npm/example@1", "license": expression}
                code, _, stderr = self.run_main([change], token="")
                self.assertEqual(code, 1, stderr)
                self.assertIn("unapproved or malformed license expression", stderr)
                self.assertIn("WHAT:", stderr)
                self.assertIn("WHY:", stderr)
                self.assertIn("HOW:", stderr)

    def test_expression_bounds_refuse_adversarial_input_before_ast_parsing(self):
        expressions = (
            "(" * 1024 + "MIT" + ")" * 1024,
            " OR ".join(["MIT"] * 10000),
            " OR ".join(["MIT"] * 300),
        )
        for expression in expressions:
            with self.subTest(bytes=len(expression)), mock.patch(
                "license_policy.ast.parse", side_effect=AssertionError("Unbounded input reached AST parser")
            ):
                self.assertFalse(validator.approved_license_expression(expression))

    def test_complete_with_expression_requires_its_own_central_approval(self):
        expression = "Apache-2.0 WITH LLVM-exception"
        self.assertFalse(validator.approved_license_expression(expression))
        with mock.patch("license_policy.APPROVED_SPDX", (*validator.APPROVED_SPDX, expression)):
            self.assertTrue(validator.approved_license_expression(expression))
            self.assertFalse(validator.approved_license_expression("MIT WITH LLVM-exception"))

    def test_revision_bound_license_lookup_keeps_exact_lgpl_identifiers(self):
        identity = validator.parse_github_action_identity({
            "package_url": f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}",
            "source_repository_url": "https://github.com/actions/checkout",
        })
        assert identity is not None
        for identifier, allowed in (
            ("LGPL-3.0-or-later", True), ("LGPL-3.0-only", False), ("LGPL-2.1-or-later", False)
        ):
            with self.subTest(identifier=identifier):
                response = io.BytesIO(json.dumps({"license": {"spdx_id": identifier}}).encode())
                with mock.patch.object(validator.urllib.request, "urlopen", return_value=response):
                    if allowed:
                        self.assertEqual(validator.fetch_github_license(identity, "read-token"), identifier)
                    else:
                        with self.assertRaises(validator.EvidenceError):
                            validator.fetch_github_license(identity, "read-token")

    def test_exact_github_action_uses_revision_bound_approved_license(self):
        changes = [
            {
                "change_type": "added",
                "package_url": f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}",
                "source_repository_url": "https://github.com/actions/checkout",
                "license": None,
            }
        ]
        with mock.patch.object(validator, "fetch_github_license", return_value="MIT") as fetch:
            returncode, stdout, stderr = self.run_main(changes)

        self.assertEqual(returncode, 0, stderr)
        self.assertIn("Resolved MIT license evidence", stdout)
        identity, token = fetch.call_args.args
        self.assertEqual(identity.owner, "actions")
        self.assertEqual(identity.repository, "checkout")
        self.assertEqual(identity.sha, CHECKOUT_SHA)
        self.assertEqual(token, "test-token")

    def test_first_party_action_uses_fixed_main_commit_and_tree(self):
        changes = [
            self.first_party_change(source=None),
            self.first_party_change("ci-dependency-review"),
        ]
        paths = (
            "actions/ci-merge-flow/action.yml",
            "actions/ci-dependency-review/action.yml",
        )
        with mock.patch.object(
            validator.urllib.request,
            "urlopen",
            side_effect=self.first_party_api_responses(paths),
        ) as urlopen:
            returncode, stdout, stderr = self.run_main(changes)

        self.assertEqual(returncode, 0, stderr)
        self.assertEqual(urlopen.call_count, 2)
        ref_request = urlopen.call_args_list[0].args[0]
        tree_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(ref_request.full_url, validator.FIRST_PARTY_REF_ENDPOINT)
        self.assertEqual(
            tree_request.full_url,
            "https://api.github.com/repos/ForgingAlpha/.github/git/trees/"
            f"{FIRST_PARTY_COMMIT}?recursive=1",
        )
        for call in urlopen.call_args_list:
            request = call.args[0]
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
            self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
            self.assertEqual(
                request.get_header("X-github-api-version"),
                validator.GITHUB_API_VERSION,
            )
            self.assertEqual(
                call.kwargs["timeout"],
                validator.LICENSE_LOOKUP_TIMEOUT_SECONDS,
            )
        self.assertEqual(stdout.count("Verified first-party provenance"), 2)

    def test_first_party_identity_requires_exact_record_and_fixed_family(self):
        valid_missing_source = self.first_party_change()
        valid_null_source = self.first_party_change(source=None)
        valid_canonical_source = self.first_party_change(source=validator.FIRST_PARTY_SOURCE_URL)
        self.assertIsNotNone(validator.parse_first_party_action_identity(valid_missing_source))
        self.assertIsNotNone(validator.parse_first_party_action_identity(valid_null_source))
        self.assertIsNotNone(validator.parse_first_party_action_identity(valid_canonical_source))

        invalid = []
        for field, value in (
            ("ecosystem", "github-actions"),
            ("name", "ForgingAlpha/.github/actions/other"),
            ("version", "v1"),
            ("source_repository_url", "https://github.com/ForgingAlpha/other"),
        ):
            change = self.first_party_change()
            change[field] = value
            invalid.append(change)
        for package_url in (
            "pkg:githubactions/ForgingAlpha/.github/actions/nested/path@main",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci_merge_flow@main",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci-merge-flow@2.%2A.%2A",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci-merge-flow@1.*.*",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci-merge-flow@v1",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci-merge-flow@refs/heads/main",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci-merge-flow@MAIN",
            "pkg:githubactions/forgingalpha/.github/actions/ci-merge-flow@main",
        ):
            change = self.first_party_change()
            change["package_url"] = package_url
            invalid.append(change)

        for change in invalid:
            with self.subTest(change=change), mock.patch.object(
                validator.urllib.request, "urlopen"
            ) as urlopen:
                returncode, _, stderr = self.run_main([change])
            self.assertNotEqual(returncode, 0)
            self.assertIn("WHAT:", stderr)
            urlopen.assert_not_called()

    def test_first_party_ref_and_tree_fail_closed(self):
        bad_ref_payloads = (
            {},
            {"ref": "refs/tags/v2", "object": {"type": "commit", "sha": FIRST_PARTY_COMMIT}},
            {"ref": "refs/heads/main", "object": {"type": "tag", "sha": FIRST_PARTY_COMMIT}},
            {"ref": "refs/heads/main", "object": {"type": "commit", "sha": "ABC"}},
        )
        for payload in bad_ref_payloads:
            with self.subTest(payload=payload), mock.patch.object(
                validator.urllib.request,
                "urlopen",
                return_value=io.BytesIO(json.dumps(payload).encode()),
            ):
                with self.assertRaises(validator.EvidenceError):
                    validator.fetch_first_party_main_tree("read-token")

        valid_ref, _ = self.first_party_api_responses()
        bad_tree_payloads = (
            ({"sha": FIRST_PARTY_TREE, "truncated": True, "tree": []}, "invalid or truncated"),
            ({"sha": FIRST_PARTY_TREE, "truncated": False, "tree": None}, "no entry list"),
            ({"sha": FIRST_PARTY_TREE, "truncated": False, "tree": [None]}, "malformed entry"),
            ({"sha": FIRST_PARTY_TREE, "truncated": False,
              "tree": [{"path": "actions/x/action.yml", "type": "blob", "sha": "bad"}]},
             "malformed entry"),
        )
        for payload, expected in bad_tree_payloads:
            with self.subTest(payload=payload), mock.patch.object(
                validator.urllib.request,
                "urlopen",
                side_effect=[
                    io.BytesIO(valid_ref.getvalue()),
                    io.BytesIO(json.dumps(payload).encode()),
                ],
            ):
                with self.assertRaisesRegex(validator.EvidenceError, expected):
                    validator.fetch_first_party_main_tree("read-token")

    def test_main_snapshot_is_resolved_once_and_keeps_exact_commit_tree(self):
        # A later main value is deliberately queued. This decision must not read it.
        responses = self.first_party_api_responses()
        later = {"ref": "refs/heads/main", "object": {"type": "commit", "sha": "e" * 40}}
        responses.append(io.BytesIO(json.dumps(later).encode()))
        with mock.patch.object(validator.urllib.request, "urlopen", side_effect=responses) as request:
            code, output, error = self.run_main([self.first_party_change()])
        self.assertEqual(code, 0, error)
        self.assertEqual(request.call_count, 2)
        self.assertIn(FIRST_PARTY_COMMIT, output)
        self.assertIn(FIRST_PARTY_BLOB, output)
        self.assertIn("not an execution receipt", output)
        self.assertNotIn("e" * 40, output)

    def test_main_tree_requires_immutable_tree_identity(self):
        for sha in (None, "", "bad", "A" * 40, 42):
            with self.subTest(sha=sha):
                ref, tree = self.first_party_api_responses()
                payload = json.loads(tree.getvalue())
                payload["sha"] = sha
                with mock.patch.object(validator.urllib.request, "urlopen", side_effect=[
                    ref, io.BytesIO(json.dumps(payload).encode()),
                ]) as request:
                    code, _, error = self.run_main([self.first_party_change()])
                self.assertNotEqual(code, 0)
                self.assertIn("WHAT:", error)
                self.assertEqual(request.call_count, 2)

    def test_main_provenance_api_failure_has_no_tag_fallback(self):
        for index in range(2):
            with self.subTest(stage=index):
                responses = self.first_party_api_responses()[:index] + [TimeoutError("unavailable")]
                with mock.patch.object(validator.urllib.request, "urlopen", side_effect=responses) as request:
                    code, _, error = self.run_main([self.first_party_change()])
                self.assertNotEqual(code, 0)
                self.assertIn("WHAT:", error)
                self.assertEqual(request.call_count, index + 1)
                self.assertTrue(all('/tags/' not in c.args[0].full_url for c in request.call_args_list))

    def test_first_party_action_path_must_be_one_exact_blob(self):
        identity = validator.FirstPartyActionIdentity(
            "ci-merge-flow",
            "pkg:githubactions/ForgingAlpha/.github/actions/ci-merge-flow@main",
        )
        wrong_entries = (
            (),
            (
                {"path": identity.action_path, "type": "tree", "sha": FIRST_PARTY_BLOB},
            ),
            (
                {
                    "path": identity.action_path,
                    "type": "blob",
                    "sha": FIRST_PARTY_BLOB,
                    "size": 0,
                },
            ),
            (
                {"path": identity.action_path, "type": "blob", "sha": FIRST_PARTY_BLOB},
                {"path": identity.action_path, "type": "blob", "sha": "c" * 40},
            ),
        )
        for entries in wrong_entries:
            with self.subTest(entries=entries), mock.patch.object(
                validator,
                "fetch_first_party_main_tree",
                return_value=(FIRST_PARTY_COMMIT, entries),
            ):
                with self.assertRaises(validator.EvidenceError):
                    validator.verify_first_party_actions(
                        {identity.action_directory: identity}, "read-token"
                    )

    def test_main_action_blob_requires_regular_file_and_positive_size(self):
        for changes in ({"mode": "120000"}, {"mode": "160000"}, {"mode": None},
                        {"size": None}, {"size": 0}, {"size": True}):
            with self.subTest(changes=changes):
                ref, tree = self.first_party_api_responses()
                payload = json.loads(tree.getvalue())
                payload["tree"][0].update(changes)
                with mock.patch.object(validator.urllib.request, "urlopen", side_effect=[
                    ref, io.BytesIO(json.dumps(payload).encode()),
                ]):
                    code, _, error = self.run_main([self.first_party_change()])
                self.assertNotEqual(code, 0)
                self.assertIn("WHAT:", error)

    def test_first_party_tree_allows_unrelated_zero_byte_blob(self):
        ref, tree = self.first_party_api_responses()
        tree_payload = json.loads(tree.getvalue())
        tree_payload["tree"].append(
            {"path": "empty-marker", "type": "blob", "sha": "c" * 40, "size": 0}
        )
        with mock.patch.object(
            validator.urllib.request,
            "urlopen",
            side_effect=[ref, io.BytesIO(json.dumps(tree_payload).encode())],
        ):
            commit_sha, entries = validator.fetch_first_party_main_tree("read-token")

        self.assertEqual(commit_sha, FIRST_PARTY_COMMIT)
        self.assertEqual(len(entries), 2)

    def test_license_lookup_uses_only_constructed_exact_ref_endpoint(self):
        identity = validator.GitHubActionIdentity(
            "actions",
            "checkout",
            CHECKOUT_SHA,
            f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}",
        )
        response = io.BytesIO(json.dumps({"license": {"spdx_id": "MIT"}}).encode())
        with mock.patch.object(validator.urllib.request, "urlopen", return_value=response) as urlopen:
            self.assertEqual(validator.fetch_github_license(identity, "read-token"), "MIT")

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            f"https://api.github.com/repos/actions/checkout/license?ref={CHECKOUT_SHA}",
        )
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer read-token")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(
            request.get_header("X-github-api-version"),
            validator.GITHUB_API_VERSION,
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], validator.LICENSE_LOOKUP_TIMEOUT_SECONDS)

    def test_github_action_identity_must_be_exact_and_match_source(self):
        malformed = (
            ("pkg:githubactions/actions/checkout@v6", "https://github.com/actions/checkout"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}?x=1", "https://github.com/actions/checkout"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}", "https://github.com/other/checkout"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}", "https://evil.example/actions/checkout"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}", "https://user@github.com/actions/checkout"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}", "https://github.com/actions/checkout.git"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}", "https://github.com/actions/checkout/"),
            (f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}", "https://github.com/actions/checkout?q=1"),
        )
        for package_url, source_url in malformed:
            with self.subTest(package_url=package_url, source_url=source_url):
                changes = [
                    {
                        "change_type": "added",
                        "package_url": package_url,
                        "source_repository_url": source_url,
                        "license": None,
                    }
                ]
                with mock.patch.object(validator, "fetch_github_license") as fetch:
                    returncode, _, stderr = self.run_main(changes)
                self.assertNotEqual(returncode, 0)
                self.assertIn("WHAT:", stderr)
                fetch.assert_not_called()

    def test_non_github_action_null_license_fails_without_network(self):
        changes = [{"change_type": "added", "package_url": "pkg:npm/unknown@1", "license": None}]
        with mock.patch.object(validator, "fetch_github_license") as fetch:
            returncode, _, stderr = self.run_main(changes)
        self.assertNotEqual(returncode, 0)
        self.assertIn("pkg:npm/unknown@1", stderr)
        fetch.assert_not_called()

    def test_exact_pinned_npm_aliases_use_registry_bound_lock_evidence(self):
        aliases = (
            ("@typescript/native", "typescript", "7.0.2"),
            ("typescript", "@typescript/typescript6", "6.0.2"),
        )
        changes = [self.npm_alias_change(*alias) for alias in aliases]
        payloads = {
            (target, version): self.npm_registry_payload(target, version)
            for _, target, version in aliases
        }
        with self.npm_alias_workspace(aliases) as workspace, mock.patch.object(
            validator,
            "fetch_npm_registry_release",
            side_effect=lambda identity: payloads[(identity.target, identity.version)],
        ) as fetch:
            returncode, stdout, stderr = self.run_main(
                changes, extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )

        self.assertEqual(returncode, 0, stderr)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(stdout.count("exact npm registry release"), 2)
        self.assertIn("pkg:npm/typescript@7.0.2", stdout)
        self.assertIn("pkg:npm/%40typescript/typescript6@6.0.2", stdout)

    def test_npm_alias_reuses_exact_concrete_record_without_network(self):
        aliases = (("tool-alias", "real-tool", "1.2.3"),)
        alias_change = self.npm_alias_change(*aliases[0])
        concrete = {
            "change_type": "added",
            "ecosystem": "npm",
            "manifest": "package-lock.json",
            "name": "real-tool",
            "version": "1.2.3",
            "package_url": "pkg:npm/real-tool@1.2.3",
            "license": "Apache-2.0",
        }
        with self.npm_alias_workspace(aliases) as workspace, mock.patch.object(
            validator, "fetch_npm_registry_release"
        ) as fetch:
            returncode, stdout, stderr = self.run_main(
                [alias_change, concrete],
                extra_env={"DEPENDENCY_WORKSPACE": str(workspace)},
            )

        self.assertEqual(returncode, 0, stderr)
        self.assertIn("concrete dependency evidence", stdout)
        fetch.assert_not_called()

    def test_direct_dependency_replaced_by_alias_uses_current_evidence(self):
        aliases = (("tool-alias", "real-tool", "1.2.3"),)
        removed = {
            "change_type": "removed", "ecosystem": "npm", "manifest": "package.json",
            "name": "real-tool", "version": "1.2.3", "package_url": "pkg:npm/real-tool@1.2.3",
            "license": "MIT",
        }
        current = {**removed, "change_type": "added", "manifest": "package-lock.json", "license": "Apache-2.0"}
        for concrete in (None, current):
            with self.subTest(concrete=concrete), self.npm_alias_workspace(aliases) as workspace:
                changes = [removed, self.npm_alias_change(*aliases[0])]
                if concrete is not None:
                    changes.append(concrete)
                with mock.patch.object(validator, "fetch_npm_registry_release", return_value=self.npm_registry_payload("real-tool", "1.2.3")) as fetch:
                    code, _, stderr = self.run_main(changes, extra_env={"DEPENDENCY_WORKSPACE": str(workspace)})
                self.assertEqual(code, 0, stderr)
                self.assertEqual(fetch.call_count, 1 if concrete is None else 0)

        with self.npm_alias_workspace(aliases) as workspace, mock.patch.object(
            validator, "fetch_npm_registry_release", side_effect=validator.EvidenceError("registry unavailable")
        ) as fetch:
            code, _, _ = self.run_main([removed, self.npm_alias_change(*aliases[0])], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)})
        self.assertEqual(code, 1)
        fetch.assert_called_once()

    def test_npm_alias_conflicting_declaration_is_rejected_in_manifest_or_root_lock(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        for filename in ("package.json", "package-lock.json"):
            for extra_spec in ("npm:other-tool@1.2.3", "npm:real-tool@1.2.4", None):
                with self.subTest(filename=filename, extra_spec=extra_spec), self.npm_alias_workspace(aliases) as workspace:
                    path = workspace / filename
                    payload = json.loads(path.read_text())
                    root = payload if filename == "package.json" else payload["packages"][""]
                    root["dependencies"] = {"tool": extra_spec}
                    path.write_text(json.dumps(payload))
                    with mock.patch.object(validator, "fetch_npm_registry_release", return_value=self.npm_registry_payload("real-tool", "1.2.3")) as fetch:
                        code, _, _ = self.run_main([change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)})
                    self.assertEqual(code, 1)
                    fetch.assert_not_called()

    def test_npm_alias_registry_lookups_are_deduplicated_and_capped(self):
        aliases = (
            ("tool-one", "real-tool", "1.2.3"),
            ("tool-two", "real-tool", "1.2.3"),
        )
        changes = [self.npm_alias_change(*alias) for alias in aliases]
        with self.npm_alias_workspace(aliases) as workspace, mock.patch.object(
            validator,
            "fetch_npm_registry_release",
            return_value=self.npm_registry_payload("real-tool", "1.2.3"),
        ) as fetch:
            returncode, _, stderr = self.run_main(
                changes, extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )
        self.assertEqual(returncode, 0, stderr)
        fetch.assert_called_once()

        many = tuple(
            (f"alias-{index}", f"target-{index}", "1.2.3")
            for index in range(validator.LICENSE_LOOKUP_LIMIT + 1)
        )
        with self.npm_alias_workspace(many) as workspace, mock.patch.object(
            validator, "fetch_npm_registry_release"
        ) as fetch:
            returncode, _, stderr = self.run_main(
                [self.npm_alias_change(*alias) for alias in many],
                extra_env={"DEPENDENCY_WORKSPACE": str(workspace)},
            )
        self.assertNotEqual(returncode, 0)
        self.assertIn("exceeds limit", stderr)
        fetch.assert_not_called()

    def test_npm_alias_rejects_ambiguous_concrete_evidence(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        concrete = {
            "change_type": "added",
            "ecosystem": "npm",
            "name": "real-tool",
            "version": "1.2.3",
            "package_url": "pkg:npm/real-tool@1.2.3",
            "license": "Apache-2.0",
        }
        with self.npm_alias_workspace(aliases) as workspace, mock.patch.object(
            validator, "fetch_npm_registry_release"
        ) as fetch:
            returncode, _, stderr = self.run_main(
                [self.npm_alias_change(*aliases[0]), concrete, dict(concrete)],
                extra_env={"DEPENDENCY_WORKSPACE": str(workspace)},
            )
        self.assertNotEqual(returncode, 0)
        self.assertIn("ambiguous", stderr)
        fetch.assert_not_called()

    def test_npm_registry_lookup_is_anonymous_fixed_and_bounded(self):
        identity = validator.NpmAliasIdentity(
            "typescript",
            "@typescript/typescript6",
            "6.0.2",
            "npm:@typescript/typescript6@6.0.2",
            "pkg:npm/typescript",
        )

        class Response(io.BytesIO):
            headers = {"Content-Length": "256"}

            def geturl(self):
                return validator.npm_registry_endpoint(identity.target, identity.version)

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        response = Response(json.dumps(self.npm_registry_payload(
            identity.target, identity.version
        )).encode())
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(validator.urllib.request, "build_opener", return_value=opener) as build:
            payload = validator.fetch_npm_registry_release(identity)

        self.assertEqual(payload["name"], identity.target)
        request = opener.open.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://registry.npmjs.org/%40typescript%2Ftypescript6/6.0.2",
        )
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertIsNone(request.get_header("Cookie"))
        self.assertEqual(
            opener.open.call_args.kwargs["timeout"],
            validator.LICENSE_LOOKUP_TIMEOUT_SECONDS,
        )
        proxy_handler, redirect_handler = build.call_args.args
        self.assertIsInstance(proxy_handler, validator.urllib.request.ProxyHandler)
        self.assertEqual(proxy_handler.proxies, {})
        self.assertIsInstance(redirect_handler, validator.RejectRedirects)

    def test_npm_registry_lookup_rejects_redirect_size_and_invalid_json(self):
        identity = validator.NpmAliasIdentity(
            "tool", "real-tool", "1.2.3", "npm:real-tool@1.2.3", "pkg:npm/tool"
        )
        endpoint = validator.npm_registry_endpoint(identity.target, identity.version)

        class Response(io.BytesIO):
            def __init__(self, body, url=endpoint, headers=None):
                super().__init__(body)
                self._url = url
                self.headers = headers or {}

            def geturl(self):
                return self._url

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        cases = (
            Response(b"{}", url="https://example.test/redirect"),
            Response(b"{}", headers={"Content-Length": str(validator.NPM_REGISTRY_RESPONSE_LIMIT + 1)}),
            Response(b"x" * (validator.NPM_REGISTRY_RESPONSE_LIMIT + 1)),
            Response(b"not-json"),
        )
        for response in cases:
            with self.subTest(response=response), mock.patch.object(
                validator.urllib.request, "build_opener"
            ) as build:
                build.return_value.open.return_value = response
                with self.assertRaises(validator.EvidenceError):
                    validator.fetch_npm_registry_release(identity)

    def test_npm_alias_rejects_registry_identity_artifact_integrity_and_license_mismatch(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        mutations = {
            "name": lambda item: item.update(name="other-tool"),
            "version": lambda item: item.update(version="1.2.4"),
            "tarball": lambda item: item["dist"].update(tarball="https://registry.npmjs.org/other.tgz"),
            "integrity": lambda item: item["dist"].update(integrity="sha512-wrong=="),
            "license": lambda item: item.update(license="MIT"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.npm_alias_workspace(aliases) as workspace:
                payload = self.npm_registry_payload("real-tool", "1.2.3")
                mutate(payload)
                with mock.patch.object(
                    validator, "fetch_npm_registry_release", return_value=payload
                ):
                    returncode, _, stderr = self.run_main(
                        [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
                    )
            self.assertNotEqual(returncode, 0)
            self.assertIn("WHAT:", stderr)

    def test_npm_alias_rejects_changed_or_incomplete_lock_evidence(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        mutations = {
            "target": lambda item: item.update(name="other-tool"),
            "version": lambda item: item.update(version="1.2.4"),
            "registry": lambda item: item.update(resolved="https://example.test/tool.tgz"),
            "integrity": lambda item: item.update(integrity="sha256-forged"),
            "license": lambda item: item.update(license="GPL-3.0-only"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.npm_alias_workspace(aliases) as workspace:
                lock_path = workspace / "package-lock.json"
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                mutate(lock["packages"]["node_modules/tool"])
                lock_path.write_text(json.dumps(lock), encoding="utf-8")
                with mock.patch.object(validator, "fetch_npm_registry_release") as fetch:
                    returncode, _, stderr = self.run_main(
                        [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
                    )
            self.assertNotEqual(returncode, 0)
            self.assertIn("WHAT:", stderr)
            fetch.assert_not_called()

    def test_npm_alias_rejects_manifest_lock_and_base_ambiguity(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        with self.npm_alias_workspace(aliases) as workspace:
            manifest = json.loads((workspace / "package.json").read_text(encoding="utf-8"))
            manifest["dependencies"] = {"tool": "npm:real-tool@1.2.3"}
            (workspace / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
            duplicate = self.run_validator(
                [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )
        self.assertNotEqual(duplicate.returncode, 0)

    def test_npm_alias_requires_regular_bounded_root_files_and_lock_v3(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        with self.npm_alias_workspace(aliases) as workspace:
            lock_path = workspace / "package-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["lockfileVersion"] = 2
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            result = self.run_validator(
                [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lockfileVersion 3", result.stderr)

        with self.npm_alias_workspace(aliases) as workspace:
            manifest_path = workspace / "package.json"
            real_manifest = workspace / "real-package.json"
            manifest_path.rename(real_manifest)
            manifest_path.symlink_to(real_manifest)
            result = self.run_validator(
                [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bounded regular file", result.stderr)

    def test_npm_alias_rejects_duplicate_manifest_and_lock_keys(self):
        aliases = (("tool", "real-tool", "1.2.3"),)
        change = self.npm_alias_change(*aliases[0])
        duplicate_manifest = (
            '{"devDependencies":{"tool":"npm:real-tool@1.2.3",'
            '"tool":"npm:real-tool@1.2.3"}}'
        )
        with self.npm_alias_workspace(aliases) as workspace:
            (workspace / "package.json").write_text(duplicate_manifest, encoding="utf-8")
            result = self.run_validator(
                [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate key", result.stderr)

        with self.npm_alias_workspace(aliases) as workspace:
            lock_path = workspace / "package-lock.json"
            descriptor = json.loads(lock_path.read_text(encoding="utf-8"))["packages"][
                "node_modules/tool"
            ]
            duplicate_lock = (
                '{"lockfileVersion":3,"packages":{"":'
                '{"devDependencies":{"tool":"npm:real-tool@1.2.3"}},'
                '"node_modules/tool":'
                + json.dumps(descriptor)
                + ',"node_modules/tool":'
                + json.dumps(descriptor)
                + "}}"
            )
            lock_path.write_text(duplicate_lock, encoding="utf-8")
            result = self.run_validator(
                [change], extra_env={"DEPENDENCY_WORKSPACE": str(workspace)}
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate key", result.stderr)

    def test_npm_alias_requires_exact_schema_purl_and_version(self):
        valid = self.npm_alias_change("tool", "real-tool", "1.2.3")
        invalid = []
        for field, value in (
            ("manifest", "packages/app/package.json"),
            ("ecosystem", "npm-lock"),
            ("package_url", "pkg:npm/real-tool"),
            ("name", "Tool"),
            ("version", "npm:real-tool@^1.2.3"),
            ("version", "npm:real-tool@latest"),
            ("version", "npm:real-tool@1.2.3-01"),
            ("source_repository_url", "https://github.com/example/real-tool"),
            ("license", ""),
            ("scope", "build"),
            ("vulnerabilities", None),
        ):
            record = dict(valid)
            record[field] = value
            invalid.append(record)
        invalid.append(valid)
        invalid.append(valid)

        for record in invalid[:-2]:
            with self.subTest(record=record):
                result = self.run_validator([record])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("WHAT:", result.stderr)

        duplicate = self.run_validator(invalid[-2:])
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("appears more than once", duplicate.stderr)

        missing_source = dict(valid)
        del missing_source["source_repository_url"]
        missing = self.run_validator([missing_source])
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing fields", missing.stderr)

    def test_fallback_deduplicates_and_caps_exact_revision_lookups(self):
        change = {
            "change_type": "added",
            "package_url": f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}",
            "source_repository_url": "https://github.com/actions/checkout",
            "license": None,
        }
        with mock.patch.object(validator, "fetch_github_license", return_value="MIT") as fetch:
            returncode, _, stderr = self.run_main([change, change])
        self.assertEqual(returncode, 0, stderr)
        fetch.assert_called_once()

        too_many = []
        for index in range(validator.LICENSE_LOOKUP_LIMIT + 1):
            sha = f"{index:040x}"
            too_many.append(
                {
                    "change_type": "added",
                    "package_url": f"pkg:githubactions/actions/action-{index}@{sha}",
                    "source_repository_url": f"https://github.com/actions/action-{index}",
                    "license": None,
                }
            )
        with mock.patch.object(validator, "fetch_github_license") as fetch:
            returncode, _, stderr = self.run_main(too_many)
        self.assertNotEqual(returncode, 0)
        self.assertIn("exceeds limit", stderr)
        fetch.assert_not_called()

    def test_fallback_fails_closed_for_missing_token_api_and_license_schema(self):
        change = {
            "change_type": "added",
            "package_url": f"pkg:githubactions/actions/checkout@{CHECKOUT_SHA}",
            "source_repository_url": "https://github.com/actions/checkout",
            "license": None,
        }
        result = self.run_validator([change])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires the read-only GitHub token", result.stderr)

        identity = validator.parse_github_action_identity(change)
        assert identity is not None
        for payload in ({}, {"license": None}, {"license": {}}, {"license": {"spdx_id": "NOASSERTION"}}):
            with self.subTest(payload=payload):
                response = io.BytesIO(json.dumps(payload).encode())
                with mock.patch.object(validator.urllib.request, "urlopen", return_value=response):
                    with self.assertRaises(validator.EvidenceError):
                        validator.fetch_github_license(identity, "read-token")

        with mock.patch.object(
            validator.urllib.request,
            "urlopen",
            side_effect=validator.urllib.error.HTTPError(
                "https://api.github.com", 403, "Forbidden", {}, None
            ),
        ):
            with self.assertRaises(validator.EvidenceError):
                validator.fetch_github_license(identity, "read-token")

    def test_validator_rejects_unknown_license_with_remediation(self):
        result = self.run_validator(
            [{"change_type": "added", "package_url": "pkg:npm/unknown@1", "license": None}]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pkg:npm/unknown@1", result.stderr)
        self.assertIn("WHAT:", result.stderr)
        self.assertIn("WHY:", result.stderr)
        self.assertIn("HOW:", result.stderr)

    def test_validator_rejects_missing_or_malformed_output(self):
        for value in ("", "not-json", "{}", "[null]"):
            with self.subTest(value=value):
                result = self.run_validator(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("WHAT:", result.stderr)

    def test_validator_rejects_malformed_license_or_change_type(self):
        invalid_records = (
            {"change_type": "added", "package_url": "pkg:npm/object@1", "license": {}},
            {"change_type": "added", "package_url": "pkg:npm/list@1", "license": []},
            {"change_type": "modified", "package_url": "pkg:npm/future@1", "license": "MIT"},
        )
        for record in invalid_records:
            with self.subTest(record=record):
                result = self.run_validator([record])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("WHAT:", result.stderr)


if __name__ == "__main__":
    unittest.main()
