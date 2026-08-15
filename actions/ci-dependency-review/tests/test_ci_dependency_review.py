import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
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

    def run_validator(self, changes, token=None):
        value = changes if isinstance(changes, str) else json.dumps(changes)
        env = {**os.environ, "DEPENDENCY_CHANGES": value}
        env.pop("GITHUB_LICENSE_TOKEN", None)
        if token is not None:
            env["GITHUB_LICENSE_TOKEN"] = token
        return subprocess.run(
            ["python3", str(SCRIPT)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def run_main(self, changes, token="test-token"):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {"DEPENDENCY_CHANGES": json.dumps(changes), "GITHUB_LICENSE_TOKEN": token},
            clear=True,
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                return validator.main(), stdout.getvalue(), stderr.getvalue()

    def first_party_change(self, action="approved-automerge", source=...):
        change = {
            "change_type": "added",
            "ecosystem": "actions",
            "name": f"ForgingAlpha/.github/actions/{action}",
            "version": "1.*.*",
            "package_url": (
                f"pkg:githubactions/ForgingAlpha/.github/actions/{action}@1.%2A.%2A"
            ),
            "license": None,
        }
        if source is not ...:
            change["source_repository_url"] = source
        return change

    def first_party_api_responses(self, paths=("actions/approved-automerge/action.yml",)):
        ref = {
            "ref": "refs/tags/v1",
            "object": {"type": "commit", "sha": FIRST_PARTY_COMMIT},
        }
        tree = {
            "truncated": False,
            "tree": [
                {"path": path, "type": "blob", "sha": FIRST_PARTY_BLOB, "size": 123}
                for path in paths
            ],
        }
        return [
            io.BytesIO(json.dumps(ref).encode()),
            io.BytesIO(json.dumps(tree).encode()),
        ]

    def test_contract_has_no_caller_bypass_or_license_override(self):
        action = self.load_action()
        self.assertNotIn("inputs", action)
        text = ACTION.read_text(encoding="utf-8")
        for obsolete in ("enabled", "deny-licenses", "allow-dependencies-licenses"):
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
        )
        allowlist = policy_result.stdout.strip().removeprefix("allow_licenses=").split(",")
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
            step for step in action["runs"]["steps"] if step.get("name") == "Reject missing license evidence"
        )
        self.assertIn("always()", guard["if"])
        self.assertEqual(
            guard["env"]["DEPENDENCY_CHANGES"],
            "${{ steps.review.outputs.dependency-changes }}",
        )
        self.assertEqual(guard["env"]["GITHUB_LICENSE_TOKEN"], "${{ github.token }}")

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
            validator, "fetch_first_party_release_tree"
        ) as first_party_fetch:
            validator.validate_changes(changes)
        fetch.assert_not_called()
        first_party_fetch.assert_not_called()

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

    def test_first_party_action_uses_fixed_v1_commit_and_tree(self):
        changes = [
            self.first_party_change(source=None),
            self.first_party_change("ci-dependency-review"),
        ]
        paths = (
            "actions/approved-automerge/action.yml",
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
            "pkg:githubactions/ForgingAlpha/.github/actions/nested/path@1.%2A.%2A",
            "pkg:githubactions/ForgingAlpha/.github/actions/approved_automerge@1.%2A.%2A",
            "pkg:githubactions/ForgingAlpha/.github/actions/approved-automerge@2.%2A.%2A",
            "pkg:githubactions/ForgingAlpha/.github/actions/approved-automerge@1.*.*",
            "pkg:githubactions/forgingalpha/.github/actions/approved-automerge@1.%2A.%2A",
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
            {"ref": "refs/tags/v1", "object": {"type": "tag", "sha": FIRST_PARTY_COMMIT}},
            {"ref": "refs/tags/v1", "object": {"type": "commit", "sha": "ABC"}},
        )
        for payload in bad_ref_payloads:
            with self.subTest(payload=payload), mock.patch.object(
                validator.urllib.request,
                "urlopen",
                return_value=io.BytesIO(json.dumps(payload).encode()),
            ):
                with self.assertRaises(validator.EvidenceError):
                    validator.fetch_first_party_release_tree("read-token")

        valid_ref = self.first_party_api_responses()[0]
        bad_tree_payloads = (
            {},
            {"truncated": True, "tree": []},
            {"truncated": False, "tree": None},
            {"truncated": False, "tree": [None]},
            {
                "truncated": False,
                "tree": [{"path": "actions/x/action.yml", "type": "blob", "sha": "bad"}],
            },
        )
        for payload in bad_tree_payloads:
            with self.subTest(payload=payload), mock.patch.object(
                validator.urllib.request,
                "urlopen",
                side_effect=[
                    io.BytesIO(valid_ref.getvalue()),
                    io.BytesIO(json.dumps(payload).encode()),
                ],
            ):
                with self.assertRaises(validator.EvidenceError):
                    validator.fetch_first_party_release_tree("read-token")

    def test_first_party_action_path_must_be_one_exact_blob(self):
        identity = validator.FirstPartyActionIdentity(
            "approved-automerge",
            "pkg:githubactions/ForgingAlpha/.github/actions/approved-automerge@1.%2A.%2A",
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
                "fetch_first_party_release_tree",
                return_value=(FIRST_PARTY_COMMIT, entries),
            ):
                with self.assertRaises(validator.EvidenceError):
                    validator.verify_first_party_actions(
                        {identity.action_directory: identity}, "read-token"
                    )

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
            commit_sha, entries = validator.fetch_first_party_release_tree("read-token")

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
