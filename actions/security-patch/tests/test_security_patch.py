from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "actions" / "security-patch" / "scripts" / "security_patch.py"
PROJECTION_ACTION = ROOT / "actions" / "security-patch-projection" / "action.yml"
ACTIVATION_ACTION = ROOT / "actions" / "security-patch-activation" / "action.yml"
DEPENDABOT_ACTION = ROOT / "actions" / "dependabot-automerge" / "action.yml"
MERGE_FLOW_ACTION = ROOT / "actions" / "ci-merge-flow" / "action.yml"

spec = importlib.util.spec_from_file_location("security_patch", SCRIPT)
security_patch = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = security_patch
spec.loader.exec_module(security_patch)


def sha(character: str) -> str:
    return character * 40


def blob(path: str, value: str) -> security_patch.BlobEntry:
    return security_patch.BlobEntry(path=path, mode="100644", kind="blob", sha=sha(value))


def encoded_blob(value: bytes) -> dict:
    return {
        "encoding": "base64",
        "size": len(value),
        "content": base64.b64encode(value).decode(),
    }


class FakeApi:
    def __init__(self):
        self.gets = {}
        self.page_values = {}
        self.ghsas = ("GHSA-abcd-efgh-ijkl",)
        self.posts = []
        self.puts = []

    def get(self, path, fresh=False):
        if path not in self.gets:
            raise AssertionError(f"unexpected GET {path}")
        return self.gets[path]

    def pages(self, path, fresh=False):
        if path not in self.page_values:
            raise AssertionError(f"unexpected pagination {path}")
        return self.page_values[path]

    def security_ghsas(self, repository, pull_request):
        self.last_security_query = (repository, pull_request)
        return self.ghsas

    def post(self, path, payload):
        self.posts.append((path, payload))
        raise AssertionError(f"unexpected POST {path}")

    def put(self, path, payload):
        self.puts.append((path, payload))
        raise AssertionError(f"unexpected PUT {path}")


class ProjectionCreateApi(FakeApi):
    def __init__(self):
        super().__init__()
        self.open_queries = 0

    def pages(self, path, fresh=False):
        if path == "repos/ForgingAlpha/alphaapps-site/pulls?state=open&base=main&per_page=100":
            self.open_queries += 1
            if self.open_queries == 1:
                return [[]]
            return [[{"number": 44}]]
        return super().pages(path, fresh=fresh)

    def post(self, path, payload):
        self.posts.append((path, payload))
        if path.endswith("/git/trees"):
            return {"sha": sha("c")}
        if path.endswith("/git/commits"):
            return {"sha": sha("d")}
        if path.endswith("/git/refs"):
            return {"ref": payload["ref"], "object": {"sha": payload["sha"]}}
        if path.endswith("/check-runs"):
            return {
                "head_sha": sha("d"),
                "app": {"id": 2468, "slug": "forgingalpha-security-projector"},
            }
        if path.endswith("/pulls"):
            return {
                "number": 44,
                "state": "open",
                "base": {"ref": "main"},
                "head": {"sha": sha("d")},
                "user": {"login": "forgingalpha-security-projector[bot]"},
            }
        raise AssertionError(f"unexpected POST {path}")


def source_fixture() -> FakeApi:
    api = FakeApi()
    repository = "ForgingAlpha/alphaapps-site"
    source_base = sha("a")
    source_head = sha("b")
    source_merge = sha("c")
    base_tree = sha("d")
    head_tree = sha("e")
    manifest_blob = sha("f")
    old_lock_blob = sha("1")
    new_lock_blob = sha("2")
    app_id = 1234
    pr_number = 17

    api.page_values[f"repos/{repository}/commits/{source_merge}/pulls?per_page=100"] = [[{
        "number": pr_number,
        "merged_at": "2026-08-16T12:00:00Z",
        "merge_commit_sha": source_merge,
        "base": {"ref": "dev"},
        "head": {"sha": source_head},
        "user": {"login": "dependabot[bot]"},
        "merged_by": {"login": "forgingalpha-agent-credential[bot]"},
    }]]
    attestation = {
        "schema": security_patch.SOURCE_SCHEMA,
        "repository": repository,
        "pull_request": pr_number,
        "source_base_sha": source_base,
        "source_head_sha": source_head,
        "ghsa_set": ["GHSA-abcd-efgh-ijkl"],
        "profile": security_patch.PROFILE,
    }
    api.page_values[f"repos/{repository}/commits/{source_head}/check-runs?per_page=100"] = [{
        "check_runs": [{
            "name": security_patch.SOURCE_CHECK,
            "head_sha": source_head,
            "status": "completed",
            "conclusion": "success",
            "app": {"id": app_id, "slug": "forgingalpha-agent-credential"},
            "output": {"summary": json.dumps(attestation)},
        }]
    }]
    api.gets[f"repos/{repository}/git/commits/{source_merge}"] = {
        "tree": {"sha": head_tree},
        "parents": [{"sha": source_base}],
        "committer": {"date": "2026-08-16T12:00:00Z"},
    }
    api.gets[f"repos/{repository}/git/commits/{source_head}"] = {
        "tree": {"sha": head_tree},
        "parents": [{"sha": sha("9")}],
    }
    api.gets[f"repos/{repository}/git/commits/{source_base}"] = {
        "tree": {"sha": base_tree},
        "parents": [{"sha": sha("8")}],
    }
    api.gets[f"repos/{repository}/git/trees/{base_tree}"] = {
        "truncated": False,
        "tree": [
            {"path": "package.json", "mode": "100644", "type": "blob", "sha": manifest_blob},
            {"path": "package-lock.json", "mode": "100644", "type": "blob", "sha": old_lock_blob},
            {"path": "src", "mode": "040000", "type": "tree", "sha": sha("3")},
        ],
    }
    api.gets[f"repos/{repository}/git/trees/{head_tree}"] = {
        "truncated": False,
        "tree": [
            {"path": "package.json", "mode": "100644", "type": "blob", "sha": manifest_blob},
            {"path": "package-lock.json", "mode": "100644", "type": "blob", "sha": new_lock_blob},
            {"path": "src", "mode": "040000", "type": "tree", "sha": sha("3")},
        ],
    }
    api.gets[f"repos/{repository}/git/blobs/{manifest_blob}"] = encoded_blob(b'{"name":"site"}\n')
    api.gets[f"repos/{repository}/git/blobs/{old_lock_blob}"] = encoded_blob(b'{"lockfileVersion":3,"version":"1"}\n')
    api.gets[f"repos/{repository}/git/blobs/{new_lock_blob}"] = encoded_blob(b'{"lockfileVersion":3,"version":"2"}\n')
    api.page_values[f"repos/{repository}/pulls/{pr_number}/files?per_page=100"] = [[{
        "filename": "package-lock.json",
        "status": "modified",
    }]]
    return api


def admission_fixture() -> FakeApi:
    api = FakeApi()
    repository = "ForgingAlpha/alphaapps-site"
    production_base = sha("a")
    projection_head = sha("b")
    production_tree = sha("c")
    projection_tree = sha("d")
    manifest_blob = sha("e")
    old_lock_blob = sha("f")
    new_lock_blob = sha("1")
    pull_request = 44
    app_id = 2468
    attestation = {
        "schema": security_patch.PROJECTION_SCHEMA,
        "repository": repository,
        "source_pull_request": 17,
        "source_base_sha": sha("2"),
        "source_head_sha": sha("3"),
        "source_merge_sha": sha("4"),
        "ghsa_set": ["GHSA-abcd-efgh-ijkl"],
        "production_base_sha": production_base,
        "projection_head_sha": projection_head,
        "projection_tree_sha": projection_tree,
        "changed_paths": ["package-lock.json"],
        "manifest_path": "package.json",
        "lock_path": "package-lock.json",
        "profile": security_patch.PROFILE,
    }
    api.gets[f"repos/{repository}/pulls/{pull_request}"] = {
        "number": pull_request,
        "state": "open",
        "base": {"ref": "main", "sha": production_base},
        "head": {"sha": projection_head, "repo": {"full_name": repository}},
        "user": {"login": "forgingalpha-security-projector[bot]"},
    }
    api.page_values[f"repos/{repository}/commits/{projection_head}/check-runs?per_page=100"] = [{
        "check_runs": [{
            "name": security_patch.PROJECTION_CHECK,
            "head_sha": projection_head,
            "status": "completed",
            "conclusion": "success",
            "app": {"id": app_id, "slug": "forgingalpha-security-projector"},
            "output": {"summary": json.dumps(attestation)},
        }]
    }]
    api.gets[f"repos/{repository}/git/ref/heads/main"] = {"object": {"sha": production_base}}
    api.gets[f"repos/{repository}/git/commits/{production_base}"] = {
        "tree": {"sha": production_tree},
        "parents": [{"sha": sha("5")}],
    }
    api.gets[f"repos/{repository}/git/commits/{projection_head}"] = {
        "tree": {"sha": projection_tree},
        "parents": [{"sha": production_base}],
    }
    api.gets[f"repos/{repository}/git/trees/{production_tree}"] = {
        "truncated": False,
        "tree": [
            {"path": "package.json", "mode": "100644", "type": "blob", "sha": manifest_blob},
            {"path": "package-lock.json", "mode": "100644", "type": "blob", "sha": old_lock_blob},
        ],
    }
    api.gets[f"repos/{repository}/git/trees/{projection_tree}"] = {
        "truncated": False,
        "tree": [
            {"path": "package.json", "mode": "100644", "type": "blob", "sha": manifest_blob},
            {"path": "package-lock.json", "mode": "100644", "type": "blob", "sha": new_lock_blob},
        ],
    }
    api.gets[f"repos/{repository}/git/blobs/{new_lock_blob}"] = encoded_blob(b'{"lockfileVersion":3}\n')
    api.page_values[f"repos/{repository}/pulls/{pull_request}/files?per_page=100"] = [[{
        "filename": "package-lock.json",
        "status": "modified",
    }]]
    api.page_values[f"repos/{repository}/pulls/{pull_request}/commits?per_page=100"] = [[{
        "sha": projection_head,
    }]]
    api.page_values[f"repos/{repository}/pulls?state=open&base=main&per_page=100"] = [[{
        "number": pull_request,
    }]]
    return api


def full_projection_fixture() -> FakeApi:
    api = source_fixture()
    repository = "ForgingAlpha/alphaapps-site"
    production_base = sha("a")
    projection_head = sha("6")
    projection_tree = sha("e")
    pull_request = 44
    attestation = {
        "schema": security_patch.PROJECTION_SCHEMA,
        "repository": repository,
        "source_pull_request": 17,
        "source_base_sha": sha("a"),
        "source_head_sha": sha("b"),
        "source_merge_sha": sha("c"),
        "ghsa_set": ["GHSA-abcd-efgh-ijkl"],
        "production_base_sha": production_base,
        "projection_head_sha": projection_head,
        "projection_tree_sha": projection_tree,
        "changed_paths": ["package-lock.json"],
        "manifest_path": "package.json",
        "lock_path": "package-lock.json",
        "profile": security_patch.PROFILE,
    }
    api.gets[f"repos/{repository}/pulls/{pull_request}"] = {
        "number": pull_request,
        "state": "open",
        "draft": False,
        "base": {"ref": "main", "sha": production_base},
        "head": {"sha": projection_head, "repo": {"full_name": repository}},
        "user": {"login": "forgingalpha-security-projector[bot]"},
    }
    api.page_values[f"repos/{repository}/commits/{projection_head}/check-runs?per_page=100"] = [{
        "check_runs": [{
            "name": security_patch.PROJECTION_CHECK,
            "head_sha": projection_head,
            "status": "completed",
            "conclusion": "success",
            "app": {"id": 2468, "slug": "forgingalpha-security-projector"},
            "output": {"summary": json.dumps(attestation)},
        }]
    }]
    api.gets[f"repos/{repository}/git/ref/heads/main"] = {"object": {"sha": production_base}}
    api.gets[f"repos/{repository}/git/commits/{projection_head}"] = {
        "tree": {"sha": projection_tree},
        "parents": [{"sha": production_base}],
    }
    api.page_values[f"repos/{repository}/pulls?state=open&base=main&per_page=100"] = [[{
        "number": pull_request,
    }]]
    api.page_values[f"repos/{repository}/pulls/{pull_request}/files?per_page=100"] = [[{
        "filename": "package-lock.json", "status": "modified",
    }]]
    api.page_values[f"repos/{repository}/pulls/{pull_request}/commits?per_page=100"] = [[{
        "sha": projection_head,
    }]]
    return api


class SecurityPatchSourceTest(unittest.TestCase):
    def build(self, api=None):
        return security_patch.build_source_evidence(
            api or source_fixture(),
            "ForgingAlpha/alphaapps-site",
            sha("c"),
            "dev",
            1234,
            "package.json",
            "package-lock.json",
        )

    def test_accepts_exact_transitive_only_squash_source(self):
        evidence = self.build()
        self.assertEqual(evidence.source_base, sha("a"))
        self.assertEqual(evidence.source_head, sha("b"))
        self.assertEqual(evidence.changed_paths, ("package-lock.json",))
        self.assertEqual(evidence.ghsa_set, ("GHSA-abcd-efgh-ijkl",))

    def test_rejects_multi_parent_source_merge(self):
        api = source_fixture()
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/commits/{sha('c')}"]["parents"].append({"sha": sha("7")})
        with self.assertRaisesRegex(security_patch.PolicyError, "one-parent squash"):
            self.build(api)

    def test_rejects_merge_tree_that_differs_from_source_head(self):
        api = source_fixture()
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/commits/{sha('c')}"]["tree"]["sha"] = sha("4")
        with self.assertRaisesRegex(security_patch.PolicyError, "source head tree"):
            self.build(api)

    def test_rejects_changed_live_advisory_set(self):
        api = source_fixture()
        api.ghsas = ("GHSA-zzzz-yyyy-xxxx",)
        with self.assertRaisesRegex(security_patch.PolicyError, "GHSA set"):
            self.build(api)

    def test_rejects_rename_or_extra_path(self):
        api = source_fixture()
        api.page_values["repos/ForgingAlpha/alphaapps-site/pulls/17/files?per_page=100"][0][0]["previous_filename"] = "old-lock.json"
        with self.assertRaisesRegex(security_patch.PolicyError, "must not be renamed"):
            self.build(api)

    def test_rejects_binary_lock_blob(self):
        api = source_fixture()
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/blobs/{sha('2')}"] = encoded_blob(b"abc\x00def")
        with self.assertRaisesRegex(security_patch.PolicyError, "binary"):
            self.build(api)

    def test_rejects_duplicate_trusted_classification_checks(self):
        api = source_fixture()
        page = api.page_values[f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?per_page=100"][0]
        page["check_runs"].append(dict(page["check_runs"][0]))
        with self.assertRaisesRegex(security_patch.PolicyError, "exactly one trusted"):
            self.build(api)


class ProjectionInvariantTest(unittest.TestCase):
    def test_pair_preimage_requires_unchanged_manifest_even_for_lock_only_fix(self):
        source = {
            "package.json": blob("package.json", "a"),
            "package-lock.json": blob("package-lock.json", "b"),
        }
        production = dict(source)
        production["package.json"] = blob("package.json", "c")
        with self.assertRaisesRegex(security_patch.PolicyError, "package.json differs"):
            security_patch.assert_pair_preimage(
                production,
                source,
                "package.json",
                "package-lock.json",
            )

    def test_projection_tree_rejects_any_extra_root_change(self):
        main = {
            "package.json": blob("package.json", "a"),
            "package-lock.json": blob("package-lock.json", "b"),
            "src": security_patch.BlobEntry("src", "040000", "tree", sha("c")),
        }
        post = {
            "package.json": main["package.json"],
            "package-lock.json": blob("package-lock.json", "d"),
        }
        result = dict(main)
        result["package-lock.json"] = post["package-lock.json"]
        result["src"] = security_patch.BlobEntry("src", "040000", "tree", sha("e"))
        with self.assertRaisesRegex(security_patch.PolicyError, "extra or mismatched"):
            security_patch.assert_root_tree_projection(
                main,
                result,
                ("package-lock.json",),
                post,
            )

    def test_open_lock_proposal_serialization_fails_closed(self):
        api = FakeApi()
        api.page_values["repos/ForgingAlpha/alphaapps-site/pulls?state=open&base=main&per_page=100"] = [[{"number": 9}]]
        api.page_values["repos/ForgingAlpha/alphaapps-site/pulls/9/files?per_page=100"] = [[{
            "filename": "package-lock.json",
            "status": "modified",
        }]]
        self.assertEqual(
            security_patch.open_lock_proposals(
                api,
                "ForgingAlpha/alphaapps-site",
                "main",
                "package-lock.json",
            ),
            [9],
        )

    def test_post_merge_requires_exact_parent_order_and_tree(self):
        api = FakeApi()
        repository = "ForgingAlpha/alphaapps-site"
        merge_sha = sha("a")
        base = sha("b")
        head = sha("c")
        tree = sha("d")
        api.gets[f"repos/{repository}/git/ref/heads/main"] = {"object": {"sha": merge_sha}}
        api.gets[f"repos/{repository}/git/commits/{merge_sha}"] = {
            "tree": {"sha": tree},
            "parents": [{"sha": base}, {"sha": head}],
        }
        security_patch.verify_post_merge(api, repository, "main", merge_sha, base, head, tree)
        api.gets[f"repos/{repository}/git/commits/{merge_sha}"]["parents"].reverse()
        with self.assertRaisesRegex(security_patch.PolicyError, "parents"):
            security_patch.verify_post_merge(api, repository, "main", merge_sha, base, head, tree)

    def test_created_projection_requires_one_consistent_app_identity(self):
        head = sha("a")
        pr = {
            "number": 44,
            "state": "open",
            "base": {"ref": "main"},
            "head": {"sha": head},
            "user": {"login": "forgingalpha-security-projector[bot]"},
        }
        check = {
            "head_sha": head,
            "app": {"id": 2468, "slug": "forgingalpha-security-projector"},
        }
        security_patch.verify_created_projection_identity(pr, check, 44, "main", head, 2468)
        check["app"]["id"] = 9999
        with self.assertRaisesRegex(security_patch.PolicyError, "configured App"):
            security_patch.verify_created_projection_identity(pr, check, 44, "main", head, 2468)

    def test_create_projection_uses_exact_git_data_and_attests_before_pr(self):
        api = ProjectionCreateApi()
        repository = "ForgingAlpha/alphaapps-site"
        production_base = sha("a")
        production_tree = sha("b")
        manifest = blob("package.json", "e")
        old_lock = blob("package-lock.json", "f")
        new_lock = blob("package-lock.json", "1")
        source = security_patch.SourceEvidence(
            repository=repository,
            pull_request=17,
            source_base=sha("2"),
            source_head=sha("3"),
            source_merge=sha("4"),
            source_tree=sha("5"),
            ghsa_set=("GHSA-abcd-efgh-ijkl",),
            changed_paths=("package-lock.json",),
            pre={"package.json": manifest, "package-lock.json": old_lock},
            post={"package.json": manifest, "package-lock.json": new_lock},
            classification_app_slug="forgingalpha-agent-credential",
        )
        api.gets[f"repos/{repository}/git/ref/heads/main"] = {"object": {"sha": production_base}}
        api.gets[f"repos/{repository}/git/commits/{production_base}"] = {
            "tree": {"sha": production_tree}, "parents": [{"sha": sha("6")}],
        }
        api.gets[f"repos/{repository}/git/commits/{source.source_merge}"] = {
            "tree": {"sha": source.source_tree},
            "parents": [{"sha": source.source_base}],
            "committer": {"date": "2026-08-16T12:00:00Z"},
        }
        api.gets[f"repos/{repository}/git/trees/{production_tree}"] = {
            "truncated": False,
            "tree": [manifest.as_dict(), old_lock.as_dict()],
        }
        api.gets[f"repos/{repository}/git/trees/{sha('c')}"] = {
            "truncated": False,
            "tree": [manifest.as_dict(), new_lock.as_dict()],
        }
        api.gets[f"repos/{repository}/git/blobs/{manifest.sha}"] = encoded_blob(b'{"name":"site"}\n')
        api.gets[f"repos/{repository}/git/blobs/{old_lock.sha}"] = encoded_blob(b'{"version":"1"}\n')
        api.page_values[f"repos/{repository}/pulls/44/files?per_page=100"] = [[{
            "filename": "package-lock.json", "status": "modified",
        }]]

        pull_request, evidence = security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json", 2468, True
        )
        self.assertEqual(pull_request, 44)
        self.assertEqual(evidence.production_base, production_base)
        paths = [path for path, _ in api.posts]
        self.assertLess(paths.index(f"repos/{repository}/check-runs"), paths.index(f"repos/{repository}/pulls"))
        commit_payload = next(payload for path, payload in api.posts if path.endswith("/git/commits"))
        self.assertEqual(commit_payload["parents"], [production_base])
        tree_payload = next(payload for path, payload in api.posts if path.endswith("/git/trees"))
        self.assertEqual(tree_payload["tree"], [new_lock.as_dict()])


class ProjectionAdmissionTest(unittest.TestCase):
    def verify(self, api=None):
        return security_patch.verify_projection_admission(
            api or admission_fixture(),
            "ForgingAlpha/alphaapps-site",
            44,
            "main",
            2468,
        )

    def test_accepts_only_exact_app_attested_projection(self):
        evidence = self.verify()
        self.assertEqual(evidence.projection_head, sha("b"))
        self.assertEqual(evidence.changed_paths, ("package-lock.json",))

    def test_rejects_duplicate_projection_checks(self):
        api = admission_fixture()
        checks = api.page_values[f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?per_page=100"][0]["check_runs"]
        checks.append(dict(checks[0]))
        with self.assertRaisesRegex(security_patch.PolicyError, "exactly one trusted"):
            self.verify(api)

    def test_rejects_unattested_tree_delta(self):
        api = admission_fixture()
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/trees/{sha('d')}"]["tree"].append({
            "path": "src", "mode": "040000", "type": "tree", "sha": sha("6"),
        })
        with self.assertRaisesRegex(security_patch.PolicyError, "root-tree delta"):
            self.verify(api)

    def test_rejects_pr_not_opened_by_projection_app(self):
        api = admission_fixture()
        api.gets["repos/ForgingAlpha/alphaapps-site/pulls/44"]["user"]["login"] = "attacker[bot]"
        with self.assertRaisesRegex(security_patch.PolicyError, "not opened by the projection App"):
            self.verify(api)

    def test_rejects_competing_open_lock_proposal(self):
        api = admission_fixture()
        path = "repos/ForgingAlpha/alphaapps-site/pulls?state=open&base=main&per_page=100"
        api.page_values[path][0].append({"number": 45})
        api.page_values["repos/ForgingAlpha/alphaapps-site/pulls/45/files?per_page=100"] = [[{
            "filename": "package-lock.json",
            "status": "modified",
        }]]
        with self.assertRaisesRegex(security_patch.PolicyError, "ambiguous"):
            self.verify(api)

    def test_full_projection_proof_reconstructs_source_and_result(self):
        evidence, pr = security_patch.verify_projection(
            full_projection_fixture(),
            "ForgingAlpha/alphaapps-site",
            44,
            "dev",
            "main",
            1234,
            2468,
            True,
        )
        self.assertEqual(evidence.source_pull_request, 17)
        self.assertEqual(evidence.projection_head, sha("6"))
        self.assertEqual(pr["base"]["sha"], sha("a"))


class CheckProvenanceTest(unittest.TestCase):
    def test_ci_requires_exact_workflow_path_pr_sha_repo_and_conclusion(self):
        api = FakeApi()
        repository = "ForgingAlpha/alphaapps-site"
        merge_candidate = sha("a")
        path = f"repos/{repository}/actions/runs?event=pull_request&status=success&head_sha={merge_candidate}&per_page=100"
        api.page_values[path] = [{
            "workflow_runs": [{
                "path": ".github/workflows/ci.yml",
                "event": "pull_request",
                "head_sha": merge_candidate,
                "conclusion": "success",
                "repository": {"full_name": repository},
                "pull_requests": [{"number": 35}],
            }]
        }]
        security_patch.verify_ci_workflow(
            api,
            repository,
            35,
            merge_candidate,
            ".github/workflows/ci.yml",
        )
        api.page_values[path][0]["workflow_runs"][0]["path"] = ".github/workflows/spoof.yml"
        with self.assertRaisesRegex(security_patch.PolicyError, "workflow run"):
            security_patch.verify_ci_workflow(
                api,
                repository,
                35,
                merge_candidate,
                ".github/workflows/ci.yml",
            )

    def test_checks_require_exact_head_and_current_base_test_merge(self):
        api = FakeApi()
        repository = "ForgingAlpha/alphaapps-site"
        head = sha("a")
        base = sha("b")
        merge_candidate = sha("c")
        tree = sha("d")
        evidence = security_patch.ProjectionEvidence(
            repository=repository,
            source_pull_request=17,
            source_base=sha("e"),
            source_head=sha("f"),
            source_merge=sha("1"),
            ghsa_set=("GHSA-abcd-efgh-ijkl",),
            production_base=base,
            projection_head=head,
            projection_tree=tree,
            changed_paths=("package-lock.json",),
            manifest_path="package.json",
            lock_path="package-lock.json",
        )
        pr = {"head": {"sha": head}, "merge_commit_sha": merge_candidate}
        api.gets[f"repos/{repository}/git/commits/{merge_candidate}"] = {
            "tree": {"sha": tree},
            "parents": [{"sha": base}, {"sha": head}],
        }
        api.page_values[f"repos/{repository}/actions/runs?event=pull_request&status=success&head_sha={head}&per_page=100"] = [{
            "workflow_runs": [{
                "path": ".github/workflows/ci.yml",
                "event": "pull_request",
                "head_sha": head,
                "conclusion": "success",
                "repository": {"full_name": repository},
                "pull_requests": [{"number": 44}],
            }]
        }]
        api.page_values[f"repos/{repository}/commits/{head}/check-runs?per_page=100"] = [{
            "check_runs": [
                {"name": "CI", "head_sha": head, "status": "completed", "conclusion": "success", "app": {"id": 15368}},
                {"name": "CodeQL", "head_sha": head, "status": "completed", "conclusion": "success", "app": {"id": 57789}},
            ]
        }]
        security_patch.verify_checks(
            api, repository, 44, pr, evidence, ".github/workflows/ci.yml", "CI", 15368, "CodeQL", 57789
        )
        api.gets[f"repos/{repository}/git/commits/{merge_candidate}"]["parents"].reverse()
        with self.assertRaisesRegex(security_patch.PolicyError, "test merge parents"):
            security_patch.verify_checks(
                api, repository, 44, pr, evidence, ".github/workflows/ci.yml", "CI", 15368, "CodeQL", 57789
            )

    def test_checks_reject_wrong_reporting_app(self):
        api = FakeApi()
        repository = "ForgingAlpha/alphaapps-site"
        head = sha("a")
        api.page_values[f"repos/{repository}/commits/{head}/check-runs?per_page=100"] = [{
            "check_runs": [{
                "name": "CI", "head_sha": head, "status": "completed",
                "conclusion": "success", "app": {"id": 9999},
            }]
        }]
        with self.assertRaisesRegex(security_patch.PolicyError, "not successful"):
            security_patch.verify_successful_check(api, repository, (head,), "CI", 15368)


class ActionContractTest(unittest.TestCase):
    def test_projection_action_has_no_checkout_or_merge_authority(self):
        text = PROJECTION_ACTION.read_text()
        self.assertIn("security_patch.py\" project", text)
        self.assertNotIn("actions/checkout", text)
        self.assertNotIn("security-app-private-key", text)
        self.assertNotIn("pulls/${PR_NUMBER}/merge", text)

    def test_activation_proves_before_mint_and_reproves_before_merge(self):
        text = ACTIVATION_ACTION.read_text()
        proof = text.index("name: Re-prove source, projection, and trusted checks")
        mint = text.index("name: Mint protected security activation token")
        final_proof = text.index("name: Re-prove immediately before protected merge")
        merge = text.index("name: Merge exact projection through GitHub")
        post = text.index("name: Verify resulting main revision and tree")
        self.assertLess(proof, mint)
        self.assertLess(mint, final_proof)
        self.assertLess(final_proof, merge)
        self.assertLess(merge, post)
        self.assertIn("merge-enabled == 'true'", text)
        self.assertIn("{sha: $sha, merge_method: \"merge\"}", text)
        self.assertNotIn("actions/checkout", text)
        self.assertNotIn("--admin", text)

    def test_observation_mode_has_no_required_merge_credential(self):
        import yaml

        action = yaml.safe_load(ACTIVATION_ACTION.read_text())
        self.assertFalse(action["inputs"]["security-app-client-id"]["required"])
        self.assertFalse(action["inputs"]["security-app-private-key"]["required"])
        text = ACTIVATION_ACTION.read_text()
        self.assertIn("Validate protected merge credential inputs", text)
        self.assertIn("Merge-enabled activation requires", text)

    def test_source_classification_binds_base_head_ghsa_profile_and_squash(self):
        text = DEPENDABOT_ACTION.read_text()
        for fragment in (
            "github.event.pull_request.base.sha",
            "alphaapps-security-source-v1",
            "source_base_sha",
            "source_head_sha",
            "ghsa_set:",
            "root-npm-v1",
            'if [ "${MERGE_METHOD}" = "squash" ]',
        ):
            self.assertIn(fragment, text)

    def test_merge_flow_admits_only_app_attested_projection_to_ci(self):
        text = MERGE_FLOW_ACTION.read_text()
        for fragment in (
            "verify-ci-admission",
            "github.event.pull_request.number",
            "vars.ALPHAAPPS_AUTOMATION_APP_ID",
            "Trusted exact security projection admitted to required CI",
        ):
            self.assertIn(fragment, text)
        self.assertNotIn("security/", text)
        self.assertNotIn("security-autopromote", text)

    def test_projection_attestation_exists_before_pr_event_can_start_ci(self):
        text = SCRIPT.read_text()
        check = text.index('f"repos/{repository}/check-runs"', text.index("def create_projection"))
        pull = text.index('f"repos/{repository}/pulls"', text.index("def create_projection"))
        self.assertLess(check, pull)


if __name__ == "__main__":
    unittest.main()
