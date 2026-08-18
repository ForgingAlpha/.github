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
SOURCE_ACTION = ROOT / "actions" / "security-patch-source" / "action.yml"
DEPENDABOT_WORKFLOW = ROOT / ".github" / "workflows" / "dependabot-automerge.yml"
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
        self.patches = []

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

    def patch(self, path, payload):
        self.patches.append((path, payload))
        raise AssertionError(f"unexpected PATCH {path}")


class ProjectionCreateApi(FakeApi):
    def __init__(self):
        super().__init__()
        self.refs = {}
        self.checks = []
        self.pull_requests = {}
        self.lose_response = None
        self.duplicate_check_after_write = False
        self.competing_lock_after_pr_write = False
        self.main_ref_reads = 0
        self.move_main_at_read = None
        self.production_base = sha("a")
        self.projection_tree = sha("c")
        self.projection_head = sha("d")

    def get(self, path, fresh=False):
        repository = "ForgingAlpha/alphaapps-site"
        if path == f"repos/{repository}/git/ref/heads/main":
            self.main_ref_reads += 1
            if self.move_main_at_read is not None and self.main_ref_reads >= self.move_main_at_read:
                return {"object": {"sha": sha("9")}}
            return {"object": {"sha": self.production_base}}
        matching_prefix = f"repos/{repository}/git/matching-refs/heads/"
        if path.startswith(matching_prefix):
            branch = path[len(matching_prefix):]
            value = self.refs.get(branch)
            return [] if value is None else [{"ref": f"refs/heads/{branch}", "object": {"sha": value}}]
        pull_prefix = f"repos/{repository}/pulls/"
        if path.startswith(pull_prefix) and path[len(pull_prefix):].isdigit():
            number = int(path[len(pull_prefix):])
            if number not in self.pull_requests:
                raise AssertionError(f"unexpected GET {path}")
            return self.pull_requests[number]
        return super().get(path, fresh=fresh)

    def pages(self, path, fresh=False):
        if path == "repos/ForgingAlpha/alphaapps-site/pulls?state=open&base=main&per_page=100":
            return [[
                pull
                for pull in self.pull_requests.values()
                if pull.get("state") == "open" and pull.get("base", {}).get("ref") == "main"
            ]]
        if path.startswith("repos/ForgingAlpha/alphaapps-site/pulls?state=all&head="):
            return [[pull for pull in self.pull_requests.values()]]
        if path.startswith("repos/ForgingAlpha/alphaapps-site/commits/") and path.endswith(
            "/check-runs?filter=all&per_page=100"
        ):
            return [{"check_runs": self.checks}]
        return super().pages(path, fresh=fresh)

    def post(self, path, payload):
        self.posts.append((path, payload))
        if path.endswith("/git/trees"):
            return {"sha": self.projection_tree}
        if path.endswith("/git/commits"):
            return {"sha": self.projection_head}
        if path.endswith("/git/refs"):
            branch = payload["ref"].removeprefix("refs/heads/")
            if branch in self.refs:
                raise security_patch.PolicyError("simulated existing projection ref")
            self.refs[branch] = payload["sha"]
            result = {"ref": payload["ref"], "object": {"sha": payload["sha"]}}
            if self.lose_response == "ref":
                raise security_patch.PolicyError("simulated lost ref response")
            return result
        if path.endswith("/check-runs"):
            result = {
                "id": 701 + len(self.checks),
                **payload,
                "app": {
                    "id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID,
                    "slug": "forgingalpha-security-projector",
                },
            }
            self.checks.append(result)
            if self.duplicate_check_after_write:
                duplicate = dict(result)
                duplicate["id"] = result["id"] + 1
                self.checks.append(duplicate)
            if self.lose_response == "check":
                raise security_patch.PolicyError("simulated lost check response")
            return result
        if path.endswith("/pulls"):
            result = {
                "number": 44,
                "state": "open",
                "draft": payload["draft"],
                "maintainer_can_modify": payload["maintainer_can_modify"],
                "changed_files": 1,
                "base": {"ref": "main", "sha": self.production_base},
                "head": {
                    "ref": payload["head"],
                    "sha": self.projection_head,
                    "repo": {"full_name": "ForgingAlpha/alphaapps-site"},
                },
                "user": {"login": "forgingalpha-security-projector[bot]"},
            }
            self.pull_requests[44] = result
            if self.competing_lock_after_pr_write:
                self.pull_requests[45] = {
                    "number": 45,
                    "state": "open",
                    "changed_files": 1,
                    "base": {"ref": "main", "sha": sha("a")},
                    "head": {
                        "ref": "other",
                        "sha": sha("7"),
                        "repo": {"full_name": "ForgingAlpha/alphaapps-site"},
                    },
                }
                self.page_values[
                    "repos/ForgingAlpha/alphaapps-site/pulls/45/files?per_page=100"
                ] = [[{"filename": "package-lock.json", "status": "modified"}]]
            if self.lose_response == "pr":
                raise security_patch.PolicyError("simulated lost pull-request response")
            return result
        raise AssertionError(f"unexpected POST {path}")


class SourceMergeApi(FakeApi):
    def __init__(self):
        super().__init__()
        self.did_merge = False
        self.source_ref_reads = 0
        self.advance_at_ref_read = None
        self.duplicate_after_write = False
        self.lose_merge_response = False

    def get(self, path, fresh=False):
        repository = "ForgingAlpha/alphaapps-site"
        if path == f"repos/{repository}/git/ref/heads/dev":
            self.source_ref_reads += 1
            advanced = self.did_merge or (
                self.advance_at_ref_read is not None
                and self.source_ref_reads >= self.advance_at_ref_read
            )
            return {"object": {"sha": sha("7") if advanced else sha("a")}}
        if path == f"repos/{repository}/pulls/17" and self.did_merge:
            value = dict(self.gets[path])
            value.update({
                "state": "closed",
                "merged_at": "2026-08-16T12:30:00Z",
                "merge_commit_sha": sha("c"),
                "merged_by": {"login": "forgingalpha-security-automation[bot]"},
            })
            return value
        return super().get(path, fresh=fresh)

    def post(self, path, payload):
        self.posts.append((path, payload))
        if path.endswith("/check-runs"):
            result = {
                "id": 601,
                **payload,
                "head_sha": sha("b"),
                "app": {
                    "id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID,
                    "slug": "forgingalpha-security-automation",
                },
            }
            checks_path = (
                f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}"
                "/check-runs?filter=all&per_page=100"
            )
            self.page_values[checks_path][0]["check_runs"].append(result)
            if self.duplicate_after_write:
                duplicate = dict(result)
                duplicate["id"] = 602
                self.page_values[checks_path][0]["check_runs"].append(duplicate)
            return result
        raise AssertionError(f"unexpected POST {path}")

    def put(self, path, payload):
        self.puts.append((path, payload))
        if path.endswith("/pulls/17/merge"):
            self.did_merge = True
            if self.lose_merge_response:
                raise security_patch.PolicyError("simulated lost merge response")
            return {"merged": True, "sha": sha("c")}
        raise AssertionError(f"unexpected PUT {path}")

    def patch(self, path, payload):
        self.patches.append((path, payload))
        if path.endswith("/check-runs/601"):
            result = {
                "id": 601,
                **payload,
                "head_sha": sha("b"),
                "app": {
                    "id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID,
                    "slug": "forgingalpha-security-automation",
                },
            }
            checks_path = (
                f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}"
                "/check-runs?filter=all&per_page=100"
            )
            self.page_values[checks_path][0]["check_runs"] = [result]
            return result
        raise AssertionError(f"unexpected PATCH {path}")


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
    app_id = security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID
    pr_number = 17

    api.page_values[f"repos/{repository}/commits/{source_merge}/pulls?per_page=100"] = [[{
        "number": pr_number,
        "merged_at": "2026-08-16T12:00:00Z",
        "merge_commit_sha": source_merge,
        "base": {"ref": "dev"},
        "head": {"sha": source_head},
        "user": {"login": "dependabot[bot]"},
        "merged_by": {"login": "forgingalpha-security-automation[bot]"},
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
            "app": {"id": app_id, "slug": "forgingalpha-security-automation"},
            "output": {"summary": json.dumps(attestation)},
        }]
    }]
    api.gets[f"repos/{repository}/git/commits/{source_merge}"] = {
        "tree": {"sha": head_tree},
        "parents": [{"sha": source_base}, {"sha": source_head}],
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


def source_candidate_fixture() -> SourceMergeApi:
    base = source_fixture()
    api = SourceMergeApi()
    api.gets.update(base.gets)
    api.page_values.update(base.page_values)
    api.ghsas = base.ghsas
    repository = "ForgingAlpha/alphaapps-site"
    run_id = 901
    api.gets[f"repos/{repository}/actions/runs/{run_id}"] = {
        "id": run_id,
        "name": "CI",
        "path": ".github/workflows/ci.yml",
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": repository},
        "head_repository": {"full_name": repository},
        "actor": {"login": "dependabot[bot]"},
        "head_sha": sha("b"),
        "pull_requests": [],
    }
    api.page_values[f"repos/{repository}/commits/{sha('b')}/pulls?per_page=100"] = [[{
        "number": 17,
        "state": "open",
        "user": {"login": "dependabot[bot]"},
        "base": {"ref": "dev"},
        "head": {"repo": {"full_name": repository}},
    }]]
    api.gets[f"repos/{repository}/pulls/17"] = {
        "number": 17,
        "state": "open",
        "draft": False,
        "user": {"login": "dependabot[bot]"},
        "base": {"ref": "dev", "sha": sha("a")},
        "head": {"sha": sha("b"), "repo": {"full_name": repository}},
        "merge_commit_sha": sha("c"),
        "auto_merge": None,
        "labels": [],
    }
    api.page_values[f"repos/{repository}/pulls/17/commits?per_page=100"] = [[{
        "sha": sha("b"),
        "author": {"login": "dependabot[bot]"},
        "committer": {"login": "web-flow"},
        "commit": {
            "author": {
                "name": "dependabot[bot]",
                "email": "49699333+dependabot[bot]@users.noreply.github.com",
            },
            "committer": {"name": "GitHub", "email": "noreply@github.com"},
            "verification": {"verified": True, "reason": "valid"},
        },
    }]]
    api.page_values[f"repos/{repository}/commits/{sha('b')}/check-runs?filter=latest&per_page=100"] = [{
        "check_runs": [
            {
                "name": "CI",
                "head_sha": sha("b"),
                "status": "completed",
                "conclusion": "success",
                "app": {"id": security_patch.TRUSTED_CI_APP_ID},
            },
            {
                "name": "CodeQL",
                "head_sha": sha("b"),
                "status": "completed",
                "conclusion": "success",
                "app": {"id": security_patch.TRUSTED_CODEQL_APP_ID},
            },
        ]
    }]
    api.page_values[f"repos/{repository}/commits/{sha('b')}/check-runs?filter=all&per_page=100"] = [{
        "check_runs": []
    }]
    return api


def live_codeql_neutral_output(
    repository: str = "ForgingAlpha/alphaapps-site",
    pull_request: int = 17,
    source_branch: str = "dev",
) -> dict:
    return {
        "annotations_count": 0,
        "text": None,
        "title": "2 configurations not found",
        "summary": (
            "**Warning**: Code scanning cannot determine the alerts introduced by this pull request, because "
            f"2 configurations present on `refs/heads/{source_branch}` were not found:\n\n"
            "### Default setup\n\n"
            "* :question:&nbsp;&nbsp;`/language:actions`\n"
            "* :question:&nbsp;&nbsp;`/language:javascript-typescript`\n\n\n"
            f"[View all branch alerts](/{repository}/security/code-scanning?"
            f"query=pr%3A{pull_request}+tool%3ACodeQL+is%3Aopen)."
        ),
    }


def live_codeql_pointer(
    repository: str = "ForgingAlpha/alphaapps-site",
    pull_request: int = 17,
    source_branch: str = "dev",
    source_base: str = sha("a"),
    source_head: str = sha("b"),
) -> dict:
    repository_name = repository.split("/", 1)[1]
    repository_pointer = {
        "id": 1234,
        "name": repository_name,
        "url": f"https://api.github.com/repos/{repository}",
    }
    return {
        "number": pull_request,
        "url": f"https://api.github.com/repos/{repository}/pulls/{pull_request}",
        "base": {
            "ref": source_branch,
            "sha": source_base,
            "repo": dict(repository_pointer),
        },
        "head": {
            "ref": "dependabot/npm_and_yarn/security-test",
            "sha": source_head,
            "repo": dict(repository_pointer),
        },
    }


def set_codeql_neutral(
    api: SourceMergeApi,
    output: dict | None = None,
    pointers: list | None = None,
) -> dict:
    check = api.page_values[
        f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=latest&per_page=100"
    ][0]["check_runs"][1]
    check.update({
        "status": "completed",
        "conclusion": "neutral",
        "output": live_codeql_neutral_output() if output is None else output,
        "pull_requests": [live_codeql_pointer()] if pointers is None else pointers,
    })
    return check


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
    app_id = security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID
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
        "changed_files": 1,
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
        "changed_files": 1,
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
            "app": {
                "id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID,
                "slug": "forgingalpha-security-projector",
            },
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


def projection_create_fixture() -> tuple[ProjectionCreateApi, security_patch.SourceEvidence]:
    api = ProjectionCreateApi()
    repository = "ForgingAlpha/alphaapps-site"
    production_base = sha("a")
    production_tree = sha("b")
    projection_tree = sha("c")
    projection_head = sha("d")
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
        classification_app_slug="forgingalpha-security-automation",
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
    api.gets[f"repos/{repository}/git/commits/{projection_head}"] = {
        "tree": {"sha": projection_tree}, "parents": [{"sha": production_base}],
    }
    api.gets[f"repos/{repository}/git/trees/{production_tree}"] = {
        "truncated": False,
        "tree": [manifest.as_dict(), old_lock.as_dict()],
    }
    api.gets[f"repos/{repository}/git/trees/{projection_tree}"] = {
        "truncated": False,
        "tree": [manifest.as_dict(), new_lock.as_dict()],
    }
    api.gets[f"repos/{repository}/git/blobs/{manifest.sha}"] = encoded_blob(b'{"name":"site"}\n')
    api.gets[f"repos/{repository}/git/blobs/{old_lock.sha}"] = encoded_blob(b'{"version":"1"}\n')
    api.page_values[f"repos/{repository}/pulls/44/files?per_page=100"] = [[{
        "filename": "package-lock.json", "status": "modified",
    }]]
    api.page_values[f"repos/{repository}/pulls/44/commits?per_page=100"] = [[{
        "sha": projection_head,
    }]]
    return api, source


class SecurityAlertGraphqlApi(security_patch.GhApi):
    def __init__(self, pages):
        super().__init__()
        self.response_pages = pages
        self.calls = []

    def _run(self, args, payload=None):
        self.calls.append((args, payload))
        return self.response_pages


def vulnerability_alert_pages(*node_pages):
    return [
        {
            "data": {
                "repository": {
                    "vulnerabilityAlerts": {
                        "nodes": nodes,
                    },
                },
            },
        }
        for nodes in node_pages
    ]


def vulnerability_alert_node(number, state="OPEN", ghsa="GHSA-abcd-efgh-ijkl"):
    return {
        "state": state,
        "securityAdvisory": {"ghsaId": ghsa},
        "dependabotUpdate": {"pullRequest": {"number": number}},
    }


class SecurityAlertAssociationTest(unittest.TestCase):
    def test_skips_schema_legitimate_nulls_and_other_prs_while_collecting_exact_associations(self):
        legitimate_unrelated = [
            {"dependabotUpdate": None},
            {"dependabotUpdate": {"pullRequest": None}},
            {
                "state": None,
                "securityAdvisory": None,
                "dependabotUpdate": {"pullRequest": {"number": 99}},
            },
        ]
        api = SecurityAlertGraphqlApi(vulnerability_alert_pages(
            [*legitimate_unrelated, vulnerability_alert_node(40, "FIXED", "GHSA-zzzz-yyyy-xxxx")],
            [
                vulnerability_alert_node(40, "OPEN", "GHSA-abcd-efgh-ijkl"),
                vulnerability_alert_node(40, "FIXED", "GHSA-abcd-efgh-ijkl"),
            ],
        ))

        self.assertEqual(
            api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40),
            ("GHSA-abcd-efgh-ijkl", "GHSA-zzzz-yyyy-xxxx"),
        )
        self.assertEqual(len(api.calls), 1)
        args, payload = api.calls[0]
        self.assertEqual(args[:3], ["graphql", "--paginate", "--slurp"])
        self.assertIsNone(payload)

    def test_schema_legitimate_unrelated_entries_do_not_create_an_association(self):
        api = SecurityAlertGraphqlApi(vulnerability_alert_pages([
            {"dependabotUpdate": None},
            {"dependabotUpdate": {"pullRequest": None}},
            vulnerability_alert_node(41),
        ]))

        with self.assertRaisesRegex(security_patch.PolicyError, "no official OPEN or FIXED"):
            api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40)

    def test_structurally_malformed_entries_fail_closed_even_with_a_valid_association(self):
        malformed_entries = (
            (None, "node must be an object"),
            ([], "node must be an object"),
            ("invalid", "node must be an object"),
            ({}, "no dependabotUpdate field"),
            ({"dependabotUpdate": "invalid"}, "dependabotUpdate must be an object or null"),
            ({"dependabotUpdate": []}, "dependabotUpdate must be an object or null"),
            ({"dependabotUpdate": {}}, "dependabotUpdate has no pullRequest field"),
            ({"dependabotUpdate": {"pullRequest": "invalid"}}, "pullRequest must be an object or null"),
            ({"dependabotUpdate": {"pullRequest": []}}, "pullRequest must be an object or null"),
            ({"dependabotUpdate": {"pullRequest": {}}}, "number must be a positive integer"),
            ({"dependabotUpdate": {"pullRequest": {"number": None}}}, "number must be a positive integer"),
            ({"dependabotUpdate": {"pullRequest": {"number": "40"}}}, "number must be a positive integer"),
            ({"dependabotUpdate": {"pullRequest": {"number": True}}}, "number must be a positive integer"),
            ({"dependabotUpdate": {"pullRequest": {"number": 0}}}, "number must be a positive integer"),
            ({"dependabotUpdate": {"pullRequest": {"number": -1}}}, "number must be a positive integer"),
            ({"dependabotUpdate": {"pullRequest": {"number": 40.0}}}, "number must be a positive integer"),
        )
        for node, error in malformed_entries:
            with self.subTest(node=node):
                api = SecurityAlertGraphqlApi(vulnerability_alert_pages([
                    vulnerability_alert_node(40),
                    node,
                ]))
                with self.assertRaisesRegex(security_patch.PolicyError, error):
                    api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40)

    def test_matching_association_requires_an_eligible_state(self):
        for state in (None, "DISMISSED", "open", 1):
            with self.subTest(state=state):
                api = SecurityAlertGraphqlApi(vulnerability_alert_pages([
                    vulnerability_alert_node(40, state=state),
                ]))
                with self.assertRaisesRegex(security_patch.PolicyError, "associated alert state is not eligible"):
                    api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40)

    def test_matching_association_requires_a_valid_security_advisory(self):
        malformed_advisories = (None, [], "invalid", {}, {"ghsaId": None}, {"ghsaId": 1}, {"ghsaId": "CVE-1"})
        for security_advisory in malformed_advisories:
            with self.subTest(security_advisory=security_advisory):
                node = vulnerability_alert_node(40)
                node["securityAdvisory"] = security_advisory
                api = SecurityAlertGraphqlApi(vulnerability_alert_pages([node]))
                with self.assertRaisesRegex(security_patch.PolicyError, "associated GHSA is invalid"):
                    api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40)

    def test_one_valid_association_does_not_mask_a_malformed_matching_entry(self):
        malformed_state = vulnerability_alert_node(40, state=None)
        malformed_advisory = vulnerability_alert_node(40)
        malformed_advisory["securityAdvisory"] = None
        for node, error in (
            (malformed_state, "associated alert state is not eligible"),
            (malformed_advisory, "associated GHSA is invalid"),
        ):
            with self.subTest(error=error):
                api = SecurityAlertGraphqlApi(vulnerability_alert_pages([
                    vulnerability_alert_node(40),
                    node,
                ]))
                with self.assertRaisesRegex(security_patch.PolicyError, error):
                    api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40)

    def test_malformed_pagination_schema_still_fails_closed(self):
        responses = (
            None,
            {},
            [None],
            [{}],
            [{"data": {"repository": None}}],
            [{"data": {"repository": {"vulnerabilityAlerts": {"nodes": None}}}}],
        )
        for response in responses:
            with self.subTest(response=response):
                api = SecurityAlertGraphqlApi(response)
                with self.assertRaisesRegex(security_patch.PolicyError, "vulnerability-alert"):
                    api.security_ghsas("ForgingAlpha/analyzingalpha-site", 40)


class SecurityPatchSourceWorkflowTest(unittest.TestCase):
    def preflight(self, api=None, wait_seconds=0):
        return security_patch.wait_for_source_candidate(
            api or source_candidate_fixture(),
            "ForgingAlpha/alphaapps-site",
            901,
            "dev",
            "package.json",
            "package-lock.json",
            wait_seconds,
        )

    def test_preflight_resolves_empty_pointer_by_unique_commit_association(self):
        candidate = self.preflight()
        self.assertEqual(candidate.pull_request, 17)
        self.assertEqual(candidate.source_base, sha("a"))
        self.assertEqual(candidate.source_head, sha("b"))
        self.assertEqual(candidate.changed_paths, ("package-lock.json",))

    def test_read_only_preflight_does_not_query_vulnerability_alerts(self):
        api = source_candidate_fixture()
        candidate = security_patch.wait_for_source_candidate(
            api,
            "ForgingAlpha/alphaapps-site",
            901,
            "dev",
            "package.json",
            "package-lock.json",
            0,
            verify_alerts=False,
        )
        self.assertEqual(candidate.ghsa_set, ())
        self.assertFalse(hasattr(api, "last_security_query"))

    def test_preflight_accepts_one_live_workflow_pointer(self):
        api = source_candidate_fixture()
        api.gets["repos/ForgingAlpha/alphaapps-site/actions/runs/901"]["pull_requests"] = [{"number": 17}]
        candidate = self.preflight(api)
        self.assertEqual(candidate.pull_request, 17)

    def test_preflight_rejects_wrong_workflow_or_actor(self):
        api = source_candidate_fixture()
        run = api.gets["repos/ForgingAlpha/alphaapps-site/actions/runs/901"]
        run["path"] = ".github/workflows/spoof.yml"
        with self.assertRaisesRegex(security_patch.PolicyError, "governed CI caller"):
            self.preflight(api)
        run["path"] = ".github/workflows/ci.yml"
        run["actor"]["login"] = "attacker"
        with self.assertRaisesRegex(security_patch.PolicyError, "Dependabot"):
            self.preflight(api)

    def test_preflight_rejects_moved_source_branch(self):
        api = source_candidate_fixture()
        api.gets["repos/ForgingAlpha/alphaapps-site/pulls/17"]["base"]["sha"] = sha("9")
        with self.assertRaisesRegex(security_patch.PolicyError, "source branch moved"):
            self.preflight(api)

    def test_preflight_rejects_stale_native_or_legacy_merge_state(self):
        api = source_candidate_fixture()
        pr = api.gets["repos/ForgingAlpha/alphaapps-site/pulls/17"]
        pr["auto_merge"] = {"enabled_by": {"login": "forgingalpha-agent-credential[bot]"}}
        with self.assertRaisesRegex(security_patch.PolicyError, "native auto-merge"):
            self.preflight(api)
        pr["auto_merge"] = None
        pr["labels"] = [{"name": "security-autopromote"}]
        with self.assertRaisesRegex(security_patch.PolicyError, "retired security-autopromote"):
            self.preflight(api)

    def test_preflight_rejects_wrong_or_failed_required_check(self):
        api = source_candidate_fixture()
        checks = api.page_values[
            f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=latest&per_page=100"
        ][0]["check_runs"]
        checks[0]["app"]["id"] = 9999
        with self.assertRaisesRegex(security_patch.PolicyError, "untrusted App"):
            self.preflight(api)
        checks[0]["app"]["id"] = security_patch.TRUSTED_CI_APP_ID
        checks[1]["conclusion"] = "failure"
        with self.assertRaisesRegex(security_patch.PolicyError, "without success"):
            self.preflight(api)

    def test_preflight_accepts_full_live_codeql_neutral_after_exact_lock_classification(self):
        api = source_candidate_fixture()
        set_codeql_neutral(api)
        candidate = self.preflight(api)
        self.assertEqual(candidate.changed_paths, ("package-lock.json",))
        self.assertEqual(api.posts, [])
        self.assertEqual(api.puts, [])
        self.assertEqual(api.patches, [])

    def test_preflight_rejects_any_codeql_neutral_output_drift(self):
        def wrong_title(output):
            output["title"] = "3 configurations not found"

        def missing_title(output):
            output.pop("title")

        def wrong_count(output):
            output["summary"] = output["summary"].replace("because 2 configurations", "because 3 configurations")

        def wrong_branch(output):
            output["summary"] = output["summary"].replace("refs/heads/dev", "refs/heads/main")

        def missing_bullet(output):
            output["summary"] = output["summary"].replace(
                "* :question:&nbsp;&nbsp;`/language:javascript-typescript`\n",
                "",
            )

        def wrong_bullet(output):
            output["summary"] = output["summary"].replace("/language:actions", "/language:python")

        def extra_bullet(output):
            output["summary"] = output["summary"].replace(
                "* :question:&nbsp;&nbsp;`/language:javascript-typescript`\n",
                "* :question:&nbsp;&nbsp;`/language:javascript-typescript`\n"
                "* :question:&nbsp;&nbsp;`/language:python`\n",
            )

        def trailing_content(output):
            output["summary"] += "\nUnexpected trailing content"

        def nonempty_text(output):
            output["text"] = "Unexpected detail"

        def annotations(output):
            output["annotations_count"] = 1

        mutations = {
            "wrong title count": wrong_title,
            "missing title": missing_title,
            "wrong summary count": wrong_count,
            "wrong branch": wrong_branch,
            "missing bullet": missing_bullet,
            "wrong bullet": wrong_bullet,
            "extra bullet": extra_bullet,
            "trailing content": trailing_content,
            "nonempty text": nonempty_text,
            "annotations": annotations,
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                api = source_candidate_fixture()
                output = live_codeql_neutral_output()
                mutate(output)
                set_codeql_neutral(api, output=output)
                with self.assertRaisesRegex(security_patch.PolicyError, "exact lockfile-only no-configurations"):
                    self.preflight(api)

    def test_preflight_rejects_any_codeql_neutral_pull_request_pointer_drift(self):
        mutations = {
            "wrong number": lambda pointer: pointer.update({"number": 18}),
            "wrong pull request URL": lambda pointer: pointer.update({"url": "https://api.github.com/wrong"}),
            "wrong base ref": lambda pointer: pointer["base"].update({"ref": "main"}),
            "wrong base SHA": lambda pointer: pointer["base"].update({"sha": sha("9")}),
            "wrong head SHA": lambda pointer: pointer["head"].update({"sha": sha("9")}),
            "empty head ref": lambda pointer: pointer["head"].update({"ref": ""}),
            "wrong base repo name": lambda pointer: pointer["base"]["repo"].update({"name": "wrong"}),
            "wrong head repo URL": lambda pointer: pointer["head"]["repo"].update({"url": "https://api.github.com/wrong"}),
            "different repo IDs": lambda pointer: pointer["head"]["repo"].update({"id": 5678}),
            "invalid repo ID": lambda pointer: pointer["head"]["repo"].update({"id": True}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                api = source_candidate_fixture()
                pointer = live_codeql_pointer()
                mutate(pointer)
                set_codeql_neutral(api, pointers=[pointer])
                with self.assertRaisesRegex(security_patch.PolicyError, "exact lockfile-only no-configurations"):
                    self.preflight(api)

        for name, pointers in {
            "missing pointers": [],
            "multiple pointers": [live_codeql_pointer(), live_codeql_pointer()],
            "non-object pointer": ["wrong"],
        }.items():
            with self.subTest(name=name):
                api = source_candidate_fixture()
                set_codeql_neutral(api, pointers=pointers)
                with self.assertRaisesRegex(security_patch.PolicyError, "exact lockfile-only no-configurations"):
                    self.preflight(api)

    def test_preflight_rejects_duplicate_or_untrusted_codeql_checks(self):
        for name, app_id in {
            "duplicate trusted": security_patch.TRUSTED_CODEQL_APP_ID,
            "duplicate untrusted": 9999,
        }.items():
            with self.subTest(name=name):
                api = source_candidate_fixture()
                checks = api.page_values[
                    f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=latest&per_page=100"
                ][0]["check_runs"]
                duplicate = dict(checks[1])
                duplicate["app"] = {"id": app_id}
                checks.append(duplicate)
                with self.assertRaisesRegex(security_patch.PolicyError, "expected one latest"):
                    self.preflight(api)

        api = source_candidate_fixture()
        checks = api.page_values[
            f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=latest&per_page=100"
        ][0]["check_runs"]
        checks[1]["app"]["id"] = 9999
        with self.assertRaisesRegex(security_patch.PolicyError, "untrusted App"):
            self.preflight(api)

    def test_preflight_rejects_every_other_terminal_codeql_conclusion(self):
        conclusions = (
            "action_required",
            "cancelled",
            "failure",
            "skipped",
            "stale",
            "startup_failure",
            "timed_out",
            None,
        )
        for conclusion in conclusions:
            with self.subTest(conclusion=conclusion):
                api = source_candidate_fixture()
                checks = api.page_values[
                    f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=latest&per_page=100"
                ][0]["check_runs"]
                checks[1].update({"status": "completed", "conclusion": conclusion})
                with self.assertRaisesRegex(security_patch.PolicyError, "without success"):
                    self.preflight(api)

    def test_preflight_rejects_manifest_and_lock_with_exact_codeql_neutral(self):
        api = source_candidate_fixture()
        set_codeql_neutral(api)
        head_tree = api.gets[f"repos/ForgingAlpha/alphaapps-site/git/trees/{sha('e')}"]["tree"]
        manifest = next(entry for entry in head_tree if entry["path"] == "package.json")
        manifest["sha"] = sha("4")
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/blobs/{sha('4')}"] = encoded_blob(
            b'{"name":"site","version":"2"}\n'
        )
        api.page_values["repos/ForgingAlpha/alphaapps-site/pulls/17/files?per_page=100"][0].append({
            "filename": "package.json",
            "status": "modified",
        })
        with self.assertRaisesRegex(security_patch.PolicyError, "lockfile-only source classification"):
            self.preflight(api)

    def test_preflight_rejects_disallowed_diff_before_accepting_known_codeql_neutral(self):
        api = source_candidate_fixture()
        set_codeql_neutral(api)
        api.page_values["repos/ForgingAlpha/alphaapps-site/pulls/17/files?per_page=100"][0].append({
            "filename": "README.md",
            "status": "modified",
        })
        with self.assertRaisesRegex(security_patch.PolicyError, "disallowed path"):
            self.preflight(api)

    def test_preflight_rejects_cosmetic_or_unverified_dependabot_commit(self):
        api = source_candidate_fixture()
        commit = api.page_values["repos/ForgingAlpha/alphaapps-site/pulls/17/commits?per_page=100"][0][0]
        commit["committer"]["login"] = "maintainer"
        with self.assertRaisesRegex(security_patch.PolicyError, "not committed by GitHub"):
            self.preflight(api)
        commit["committer"]["login"] = "web-flow"
        commit["commit"]["author"]["email"] = "dependabot[bot]@example.com"
        with self.assertRaisesRegex(security_patch.PolicyError, "canonical Dependabot identity"):
            self.preflight(api)
        commit["commit"]["author"]["email"] = "49699333+dependabot[bot]@users.noreply.github.com"
        commit["commit"]["verification"]["reason"] = "unsigned"
        with self.assertRaisesRegex(security_patch.PolicyError, "valid GitHub verification"):
            self.preflight(api)

    def test_preflight_times_out_when_latest_check_is_pending(self):
        api = source_candidate_fixture()
        checks = api.page_values[
            f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=latest&per_page=100"
        ][0]["check_runs"]
        checks[1].update({"status": "in_progress", "conclusion": None})
        with self.assertRaisesRegex(security_patch.PolicyError, "bounded deadline"):
            self.preflight(api)

    def test_merge_reproves_and_accepts_recorded_result_after_later_dev_movement(self):
        api = source_candidate_fixture()
        merge_sha = security_patch.merge_source_candidate(
            api,
            "ForgingAlpha/alphaapps-site",
            901,
            "dev",
            "package.json",
            "package-lock.json",
            17,
            sha("b"),
            sha("a"),
        )
        self.assertEqual(merge_sha, sha("c"))
        self.assertEqual(
            api.puts,
            [("repos/ForgingAlpha/alphaapps-site/pulls/17/merge", {"sha": sha("b"), "merge_method": "merge"})],
        )
        check_payload = next(payload for path, payload in api.posts if path.endswith("/check-runs"))
        self.assertEqual(check_payload["head_sha"], sha("b"))
        self.assertEqual(json.loads(check_payload["output"]["summary"])["source_base_sha"], sha("a"))
        self.assertEqual(api.source_ref_reads, 4)

    def test_merge_adopts_exact_recorded_result_after_response_loss(self):
        api = source_candidate_fixture()
        api.lose_merge_response = True
        merge_sha = security_patch.merge_source_candidate(
            api,
            "ForgingAlpha/alphaapps-site",
            901,
            "dev",
            "package.json",
            "package-lock.json",
            17,
            sha("b"),
            sha("a"),
        )
        self.assertEqual(merge_sha, sha("c"))
        self.assertEqual(len(api.puts), 1)

    def test_merge_rerun_adopts_exact_already_completed_result_without_writing(self):
        api = source_candidate_fixture()
        api.did_merge = True
        merge_sha = security_patch.merge_source_candidate(
            api,
            "ForgingAlpha/alphaapps-site",
            901,
            "dev",
            "package.json",
            "package-lock.json",
            17,
            sha("b"),
            sha("a"),
        )
        self.assertEqual(merge_sha, sha("c"))
        self.assertFalse(api.puts)
        self.assertFalse(api.posts)

    def test_merge_rerun_rejects_completed_result_from_wrong_actor(self):
        api = source_candidate_fixture()
        api.did_merge = True
        source_association = api.page_values[
            f"repos/ForgingAlpha/alphaapps-site/commits/{sha('c')}/pulls?per_page=100"
        ][0][0]
        source_association["merged_by"] = {"login": "unexpected[bot]"}
        with self.assertRaisesRegex(security_patch.PolicyError, "merged by the classification App"):
            security_patch.merge_source_candidate(
                api,
                "ForgingAlpha/alphaapps-site",
                901,
                "dev",
                "package.json",
                "package-lock.json",
                17,
                sha("b"),
                sha("a"),
            )
        self.assertFalse(api.puts)

    def test_merge_rejects_dev_movement_during_final_reproof(self):
        api = source_candidate_fixture()
        api.advance_at_ref_read = 3
        with self.assertRaisesRegex(security_patch.PolicyError, "source branch moved"):
            security_patch.merge_source_candidate(
                api,
                "ForgingAlpha/alphaapps-site",
                901,
                "dev",
                "package.json",
                "package-lock.json",
                17,
                sha("b"),
                sha("a"),
            )
        self.assertFalse(api.puts)

    def test_merge_rerun_updates_the_unique_exact_head_classification(self):
        api = source_candidate_fixture()
        path = f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=all&per_page=100"
        api.page_values[path][0]["check_runs"] = [{
            "id": 601,
            "name": security_patch.SOURCE_CHECK,
            "head_sha": sha("b"),
            "external_id": f"{security_patch.SOURCE_SCHEMA}:17:{sha('b')}",
            "app": {"id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID},
        }]
        security_patch.merge_source_candidate(
            api,
            "ForgingAlpha/alphaapps-site",
            901,
            "dev",
            "package.json",
            "package-lock.json",
            17,
            sha("b"),
            sha("a"),
        )
        self.assertEqual(len(api.patches), 1)
        self.assertFalse(any(request_path.endswith("/check-runs") for request_path, _ in api.posts))

    def test_merge_rejects_conflicting_or_duplicate_trusted_classification(self):
        api = source_candidate_fixture()
        path = f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?filter=all&per_page=100"
        run = {
            "id": 601,
            "name": security_patch.SOURCE_CHECK,
            "head_sha": sha("b"),
            "external_id": "conflicting-identity",
            "app": {"id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID},
        }
        api.page_values[path][0]["check_runs"] = [run]
        with self.assertRaisesRegex(security_patch.PolicyError, "external identity conflicts"):
            security_patch.merge_source_candidate(
                api,
                "ForgingAlpha/alphaapps-site",
                901,
                "dev",
                "package.json",
                "package-lock.json",
                17,
                sha("b"),
                sha("a"),
            )
        api.page_values[path][0]["check_runs"] = [run, dict(run)]
        with self.assertRaisesRegex(security_patch.PolicyError, "multiple trusted"):
            security_patch.merge_source_candidate(
                api,
                "ForgingAlpha/alphaapps-site",
                901,
                "dev",
                "package.json",
                "package-lock.json",
                17,
                sha("b"),
                sha("a"),
            )

    def test_merge_rejects_a_concurrent_duplicate_created_after_write(self):
        api = source_candidate_fixture()
        api.duplicate_after_write = True
        with self.assertRaisesRegex(security_patch.PolicyError, "not unique after write"):
            security_patch.merge_source_candidate(
                api,
                "ForgingAlpha/alphaapps-site",
                901,
                "dev",
                "package.json",
                "package-lock.json",
                17,
                sha("b"),
                sha("a"),
            )
        self.assertFalse(api.puts)


class SecurityPatchSourceTest(unittest.TestCase):
    def build(self, api=None):
        return security_patch.build_source_evidence(
            api or source_fixture(),
            "ForgingAlpha/alphaapps-site",
            sha("c"),
            "dev",
            "package.json",
            "package-lock.json",
        )

    def test_accepts_exact_transitive_only_merge_source(self):
        evidence = self.build()
        self.assertEqual(evidence.source_base, sha("a"))
        self.assertEqual(evidence.source_head, sha("b"))
        self.assertEqual(evidence.changed_paths, ("package-lock.json",))
        self.assertEqual(evidence.ghsa_set, ("GHSA-abcd-efgh-ijkl",))

    def test_rejects_wrong_source_merge_parent_shape(self):
        api = source_fixture()
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/commits/{sha('c')}"]["parents"].append({"sha": sha("7")})
        with self.assertRaisesRegex(security_patch.PolicyError, "two-parent merge"):
            self.build(api)

    def test_rejects_source_merge_with_wrong_second_parent(self):
        api = source_fixture()
        api.gets[f"repos/ForgingAlpha/alphaapps-site/git/commits/{sha('c')}"]["parents"][1]["sha"] = sha("7")
        with self.assertRaisesRegex(security_patch.PolicyError, "second parent"):
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

    def test_rejects_classification_from_any_other_app(self):
        api = source_fixture()
        page = api.page_values[f"repos/ForgingAlpha/alphaapps-site/commits/{sha('b')}/check-runs?per_page=100"][0]
        page["check_runs"][0]["app"]["id"] = 9999
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
        api.gets["repos/ForgingAlpha/alphaapps-site/pulls/9"] = {
            "number": 9,
            "state": "open",
            "changed_files": 1,
            "base": {"ref": "main"},
        }
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

    def test_open_lock_proposal_rejects_incomplete_capped_file_enumeration(self):
        api = FakeApi()
        repository = "ForgingAlpha/alphaapps-site"
        api.page_values[f"repos/{repository}/pulls?state=open&base=main&per_page=100"] = [[{
            "number": 9,
        }]]
        api.gets[f"repos/{repository}/pulls/9"] = {
            "number": 9,
            "state": "open",
            "changed_files": security_patch.PULL_FILES_API_LIMIT + 1,
            "base": {"ref": "main"},
        }
        api.page_values[f"repos/{repository}/pulls/9/files?per_page=100"] = [[
            {"filename": f"generated/{index:04d}.txt", "status": "modified"}
            for index in range(security_patch.PULL_FILES_API_LIMIT)
        ]]
        with self.assertRaisesRegex(security_patch.PolicyError, "enumeration is incomplete"):
            security_patch.open_lock_proposals(api, repository, "main", "package-lock.json")

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
            "app": {
                "id": security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID,
                "slug": "forgingalpha-security-projector",
            },
        }
        security_patch.verify_created_projection_identity(pr, check, 44, "main", head)
        check["app"]["id"] = 9999
        with self.assertRaisesRegex(security_patch.PolicyError, "centrally trusted App"):
            security_patch.verify_created_projection_identity(pr, check, 44, "main", head)

    def test_create_projection_uses_exact_git_data_and_attests_before_pr(self):
        api, source = projection_create_fixture()
        repository = "ForgingAlpha/alphaapps-site"
        production_base = sha("a")

        pull_request, evidence = security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        self.assertEqual(pull_request, 44)
        self.assertEqual(evidence.production_base, production_base)
        paths = [path for path, _ in api.posts]
        self.assertLess(paths.index(f"repos/{repository}/check-runs"), paths.index(f"repos/{repository}/pulls"))
        commit_payload = next(payload for path, payload in api.posts if path.endswith("/git/commits"))
        self.assertEqual(commit_payload["parents"], [production_base])
        tree_payload = next(payload for path, payload in api.posts if path.endswith("/git/trees"))
        self.assertEqual(tree_payload["tree"], [source.post["package-lock.json"].as_dict()])
        branch = f"security/dependabot-17-{sha('3')}-{sha('a')}"
        self.assertEqual(api.pull_requests[44]["head"]["ref"], branch)

    def test_projection_adopts_each_accepted_write_after_response_loss(self):
        for stage in ("ref", "check", "pr"):
            with self.subTest(stage=stage):
                api, source = projection_create_fixture()
                api.lose_response = stage
                pull_request, evidence = security_patch.create_projection(
                    api, source, "main", "package.json", "package-lock.json"
                )
                self.assertEqual(pull_request, 44)
                self.assertEqual(evidence.projection_head, sha("d"))
                mutable_paths = ("/git/refs", "/check-runs", "/pulls")
                writes_after_loss = [
                    path for path, _ in api.posts if path.endswith(mutable_paths)
                ]
                api.lose_response = None
                rerun = security_patch.create_projection(
                    api, source, "main", "package.json", "package-lock.json"
                )
                writes_after_rerun = [
                    path for path, _ in api.posts if path.endswith(mutable_paths)
                ]
                self.assertEqual(rerun, (pull_request, evidence))
                self.assertEqual(writes_after_rerun, writes_after_loss)

    def test_projection_rerun_performs_no_second_ref_check_or_pr_write(self):
        api, source = projection_create_fixture()
        expected = security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        mutable_paths = (
            "repos/ForgingAlpha/alphaapps-site/git/refs",
            "repos/ForgingAlpha/alphaapps-site/check-runs",
            "repos/ForgingAlpha/alphaapps-site/pulls",
        )
        first_counts = {path: sum(item[0] == path for item in api.posts) for path in mutable_paths}
        actual = security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        second_counts = {path: sum(item[0] == path for item in api.posts) for path in mutable_paths}
        self.assertEqual(actual, expected)
        self.assertEqual(first_counts, {path: 1 for path in mutable_paths})
        self.assertEqual(second_counts, first_counts)

    def test_projection_allows_exact_ref_without_check_to_resume(self):
        api, source = projection_create_fixture()
        api.move_main_at_read = 3
        with self.assertRaisesRegex(security_patch.PolicyError, "before projection pull request"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        self.assertEqual(len(api.refs), 1)
        api.checks.clear()
        api.move_main_at_read = None
        api.main_ref_reads = 0
        ref_writes = sum(path.endswith("/git/refs") for path, _ in api.posts)
        pull_request, _ = security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        self.assertEqual(pull_request, 44)
        self.assertEqual(sum(path.endswith("/git/refs") for path, _ in api.posts), ref_writes)
        self.assertEqual(sum(path.endswith("/check-runs") for path, _ in api.posts), 2)

    def test_projection_rejects_check_without_ref_before_mutation(self):
        api, source = projection_create_fixture()
        api.move_main_at_read = 3
        with self.assertRaises(security_patch.PolicyError):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        api.refs.clear()
        api.move_main_at_read = None
        api.main_ref_reads = 0
        mutable_before = [
            path for path, _ in api.posts if path.endswith(("/git/refs", "/check-runs", "/pulls"))
        ]
        with self.assertRaisesRegex(security_patch.PolicyError, "check exists without"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        mutable_after = [
            path for path, _ in api.posts if path.endswith(("/git/refs", "/check-runs", "/pulls"))
        ]
        self.assertEqual(mutable_after, mutable_before)

    def test_projection_rejects_prior_closed_wrong_base_or_duplicate_branch_record(self):
        cases = (
            ("closed", [{"state": "closed", "base": "main", "merged_at": None}], "closed or merged"),
            ("merged", [{"state": "closed", "base": "main", "merged_at": "2026-08-17T12:00:00Z"}], "closed or merged"),
            ("wrong-base", [{"state": "open", "base": "release", "merged_at": None}], "base mismatch"),
            (
                "multiple",
                [
                    {"state": "open", "base": "main", "merged_at": None},
                    {"state": "closed", "base": "main", "merged_at": None},
                ],
                "multiple pull-request records",
            ),
        )
        for label, records, message in cases:
            with self.subTest(label=label):
                api, source = projection_create_fixture()
                branch = security_patch.projection_branch(source, sha("a"))
                for offset, record in enumerate(records):
                    number = 44 + offset
                    api.pull_requests[number] = {
                        "number": number,
                        "state": record["state"],
                        "merged_at": record["merged_at"],
                        "base": {"ref": record["base"], "sha": sha("a")},
                        "head": {
                            "ref": branch,
                            "sha": sha("d"),
                            "repo": {"full_name": source.repository},
                        },
                    }
                with self.assertRaisesRegex(security_patch.PolicyError, message):
                    security_patch.create_projection(
                        api, source, "main", "package.json", "package-lock.json"
                    )
                self.assertFalse(any(
                    path.endswith(("/git/refs", "/check-runs", "/pulls"))
                    for path, _ in api.posts
                ))

    def test_new_production_base_uses_new_branch_and_preserves_old_partial_records(self):
        api, source = projection_create_fixture()
        api.move_main_at_read = 3
        with self.assertRaisesRegex(security_patch.PolicyError, "before projection pull request"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        old_refs = dict(api.refs)
        old_check = json.loads(json.dumps(api.checks[0]))

        repository = source.repository
        new_base = sha("9")
        new_production_tree = sha("7")
        new_projection_tree = sha("8")
        new_projection_head = sha("6")
        api.move_main_at_read = None
        api.main_ref_reads = 0
        api.production_base = new_base
        api.projection_tree = new_projection_tree
        api.projection_head = new_projection_head
        api.gets[f"repos/{repository}/git/commits/{new_base}"] = {
            "tree": {"sha": new_production_tree}, "parents": [{"sha": sha("0")}],
        }
        api.gets[f"repos/{repository}/git/commits/{new_projection_head}"] = {
            "tree": {"sha": new_projection_tree}, "parents": [{"sha": new_base}],
        }
        api.gets[f"repos/{repository}/git/trees/{new_production_tree}"] = {
            "truncated": False,
            "tree": [source.pre["package.json"].as_dict(), source.pre["package-lock.json"].as_dict()],
        }
        api.gets[f"repos/{repository}/git/trees/{new_projection_tree}"] = {
            "truncated": False,
            "tree": [source.post["package.json"].as_dict(), source.post["package-lock.json"].as_dict()],
        }
        api.page_values[f"repos/{repository}/pulls/44/commits?per_page=100"] = [[{
            "sha": new_projection_head,
        }]]

        pull_request, evidence = security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        self.assertEqual(pull_request, 44)
        self.assertEqual(evidence.production_base, new_base)
        self.assertEqual(evidence.projection_head, new_projection_head)
        self.assertEqual(api.checks[0], old_check)
        for branch, head in old_refs.items():
            self.assertEqual(api.refs[branch], head)
        self.assertEqual(len(api.refs), 2)
        self.assertEqual(len(api.checks), 2)

    def test_existing_projection_pr_cannot_backfill_a_missing_ref_or_check(self):
        for missing in ("ref", "check"):
            with self.subTest(missing=missing):
                api, source = projection_create_fixture()
                security_patch.create_projection(
                    api, source, "main", "package.json", "package-lock.json"
                )
                if missing == "ref":
                    api.refs.clear()
                    message = "check exists without its deterministic branch"
                else:
                    api.checks.clear()
                    message = "pre-existing trusted check"
                mutable_before = len([
                    path
                    for path, _ in api.posts
                    if path.endswith(("/git/refs", "/check-runs", "/pulls"))
                ])
                with self.assertRaisesRegex(security_patch.PolicyError, message):
                    security_patch.create_projection(
                        api, source, "main", "package.json", "package-lock.json"
                    )
                mutable_after = len([
                    path
                    for path, _ in api.posts
                    if path.endswith(("/git/refs", "/check-runs", "/pulls"))
                ])
                self.assertEqual(mutable_after, mutable_before)

    def test_projection_rejects_existing_branch_at_a_different_head_without_update(self):
        api, source = projection_create_fixture()
        branch = security_patch.projection_branch(source, sha("a"))
        api.refs[branch] = sha("8")
        with self.assertRaisesRegex(security_patch.PolicyError, "different head"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        self.assertFalse(any(path.endswith("/git/refs") for path, _ in api.posts))

    def test_projection_rejects_duplicate_or_conflicting_trusted_check(self):
        api, source = projection_create_fixture()
        security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        duplicate = dict(api.checks[0])
        duplicate["id"] = 999
        api.checks.append(duplicate)
        with self.assertRaisesRegex(security_patch.PolicyError, "multiple trusted"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )

        api, source = projection_create_fixture()
        security_patch.create_projection(
            api, source, "main", "package.json", "package-lock.json"
        )
        api.checks[0]["external_id"] = "security-projection-v1:wrong"
        with self.assertRaisesRegex(security_patch.PolicyError, "external_id mismatch"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )

    def test_projection_rejects_duplicate_check_created_during_write(self):
        api, source = projection_create_fixture()
        api.duplicate_check_after_write = True
        with self.assertRaisesRegex(security_patch.PolicyError, "recorded uniquely"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )

    def test_projection_rejects_wrong_recorded_pr_identity(self):
        mutations = (
            ("user", lambda pull: pull.update({"user": {"login": "attacker[bot]"}}), "different App owners"),
            ("draft", lambda pull: pull.update({"draft": False}), "remain draft"),
            ("maintainer", lambda pull: pull.update({"maintainer_can_modify": True}), "maintainer modification"),
        )
        for label, mutate, message in mutations:
            with self.subTest(label=label):
                api, source = projection_create_fixture()
                security_patch.create_projection(
                    api, source, "main", "package.json", "package-lock.json"
                )
                mutate(api.pull_requests[44])
                with self.assertRaisesRegex(security_patch.PolicyError, message):
                    security_patch.create_projection(
                        api, source, "main", "package.json", "package-lock.json"
                    )

    def test_projection_rejects_wrong_recorded_pr_revision_or_tree(self):
        cases = (
            (
                "head",
                lambda api: api.pull_requests[44]["head"].update({"sha": sha("8")}),
                "head mismatch",
            ),
            (
                "base",
                lambda api: api.pull_requests[44]["base"].update({"sha": sha("8")}),
                "base SHA mismatch",
            ),
            (
                "tree",
                lambda api: api.gets[
                    "repos/ForgingAlpha/alphaapps-site/git/commits/" + sha("d")
                ]["tree"].update({"sha": sha("8")}),
                "commit tree mismatch",
            ),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                api, source = projection_create_fixture()
                security_patch.create_projection(
                    api, source, "main", "package.json", "package-lock.json"
                )
                mutate(api)
                with self.assertRaisesRegex(security_patch.PolicyError, message):
                    security_patch.create_projection(
                        api, source, "main", "package.json", "package-lock.json"
                    )

    def test_projection_rejects_competing_lock_before_mutable_writes(self):
        api, source = projection_create_fixture()
        api.pull_requests[45] = {
            "number": 45,
            "state": "open",
            "changed_files": 1,
            "base": {"ref": "main", "sha": sha("a")},
            "head": {"ref": "other", "sha": sha("7"), "repo": {"full_name": source.repository}},
        }
        api.page_values[f"repos/{source.repository}/pulls/45/files?per_page=100"] = [[{
            "filename": "package-lock.json", "status": "modified",
        }]]
        with self.assertRaisesRegex(security_patch.PolicyError, "already touch"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        mutable = ("/git/refs", "/check-runs", "/pulls")
        self.assertFalse(any(path.endswith(mutable) for path, _ in api.posts))

    def test_projection_rejects_main_movement_before_pr_creation(self):
        api, source = projection_create_fixture()
        api.move_main_at_read = 3
        with self.assertRaisesRegex(security_patch.PolicyError, "before projection pull request"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        self.assertFalse(any(path.endswith("/pulls") for path, _ in api.posts))

    def test_projection_rejects_main_movement_after_pr_acceptance(self):
        api, source = projection_create_fixture()
        api.move_main_at_read = 4
        with self.assertRaisesRegex(security_patch.PolicyError, "while recording projection"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )
        self.assertEqual(sum(path.endswith("/pulls") for path, _ in api.posts), 1)
        self.assertIn(44, api.pull_requests)

    def test_projection_rejects_competing_lock_created_with_projection_pr(self):
        api, source = projection_create_fixture()
        api.competing_lock_after_pr_write = True
        with self.assertRaisesRegex(security_patch.PolicyError, "ambiguous"):
            security_patch.create_projection(
                api, source, "main", "package.json", "package-lock.json"
            )


class ProjectionAdmissionTest(unittest.TestCase):
    def verify(self, api=None):
        return security_patch.verify_projection_admission(
            api or admission_fixture(),
            "ForgingAlpha/alphaapps-site",
            44,
            "main",
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
        api.gets["repos/ForgingAlpha/alphaapps-site/pulls/45"] = {
            "number": 45,
            "state": "open",
            "changed_files": 1,
            "base": {"ref": "main"},
        }
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

    def test_source_action_has_read_only_preflight_and_exact_merge_modes(self):
        text = SOURCE_ACTION.read_text()
        for fragment in (
            "preflight-source",
            "merge-source",
            "--workflow-run-id",
            "--expected-head-sha",
            "--expected-base-sha",
            "operation == 'preflight'",
            "operation == 'merge'",
        ):
            self.assertIn(fragment, text)
        self.assertNotIn("actions/checkout", text)
        self.assertNotIn("private-key", text)
        self.assertNotIn("app-id", text)
        self.assertNotIn("pull_request_target", text)

    def test_merge_flow_admits_only_app_attested_projection_to_ci(self):
        text = MERGE_FLOW_ACTION.read_text()
        for fragment in (
            "verify-ci-admission",
            "github.event.pull_request.number",
            "Trusted exact security projection admitted to required CI",
        ):
            self.assertIn(fragment, text)
        self.assertNotIn("vars.", text)
        self.assertNotIn("projection-app-id", text)
        self.assertNotIn("security/", text)
        self.assertNotIn("security-autopromote", text)

    def test_projection_identity_is_one_central_non_overridable_trust_anchor(self):
        self.assertEqual(security_patch.TRUSTED_SECURITY_AUTOMATION_APP_ID, 4618077)
        for path in (SOURCE_ACTION, PROJECTION_ACTION, ACTIVATION_ACTION, MERGE_FLOW_ACTION):
            text = path.read_text()
            self.assertNotIn("projection-app-id", text)
            self.assertNotIn("automation-app-id", text)
            self.assertNotIn("PROJECTION_APP_ID", text)
            self.assertNotIn("AUTOMATION_APP_ID", text)

    def test_legacy_classifier_keeps_its_quarantined_identity_until_callers_migrate(self):
        workflow = DEPENDABOT_WORKFLOW.read_text()
        self.assertIn("app-id: 4249954", workflow)
        self.assertNotIn("app-id: 4618077", workflow)
        self.assertNotIn("ALPHAAPPS_AUTOMATION_APP_ID", workflow)

    def test_projection_attestation_exists_before_pr_event_can_start_ci(self):
        text = SCRIPT.read_text()
        create = text.index("def create_projection")
        check = text.index("ensure_projection_check(api, evidence)", create)
        pull = text.index('f"repos/{repository}/pulls"', create)
        self.assertLess(check, pull)


if __name__ == "__main__":
    unittest.main()
