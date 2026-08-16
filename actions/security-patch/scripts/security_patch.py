#!/usr/bin/env python3
"""Exact Dependabot security-patch projection and activation verifier."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
APP_ID_RE = re.compile(r"^[1-9][0-9]*$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ROOT_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SOURCE_SCHEMA = "alphaapps-security-source-v1"
PROJECTION_SCHEMA = "alphaapps-security-projection-v1"
SOURCE_CHECK = "AlphaApps Security Classification"
PROJECTION_CHECK = "AlphaApps Security Projection"
PROFILE = "root-npm-v1"
MAX_BLOB_BYTES = 20 * 1024 * 1024
# Public GitHub App identity owned by the released control-plane policy. This
# is a trust anchor, not a credential. Consumers cannot select or override it.
TRUSTED_SECURITY_AUTOMATION_APP_ID = 4249954
TRUSTED_CI_APP_ID = 15368
TRUSTED_CODEQL_APP_ID = 57789
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
CI_CHECK = "CI"
CODEQL_CHECK = "CodeQL"


class PolicyError(RuntimeError):
    """A fail-closed policy rejection."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyError(message)


def require_sha(value: str, label: str) -> str:
    require(bool(SHA_RE.fullmatch(value)), f"{label} must be a lowercase 40-character SHA")
    return value


def require_app_id(value: str | int, label: str) -> int:
    rendered = str(value)
    require(bool(APP_ID_RE.fullmatch(rendered)), f"{label} must be a positive GitHub App ID")
    return int(rendered)


def require_repository(value: str) -> str:
    require(bool(REPOSITORY_RE.fullmatch(value)), "repository must be owner/name")
    return value


def require_root_file(value: str, label: str) -> str:
    require(bool(ROOT_FILE_RE.fullmatch(value)), f"{label} must be one root regular-file path")
    return value


def require_pr_number(value: str | int, label: str = "pull request") -> int:
    rendered = str(value)
    require(bool(APP_ID_RE.fullmatch(rendered)), f"{label} number must be a positive integer")
    return int(rendered)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def flatten_pages(pages: Any, label: str) -> list[Any]:
    require(isinstance(pages, list), f"{label} pagination response must be a list")
    flattened: list[Any] = []
    for page in pages:
        require(isinstance(page, list), f"{label} page must be a list")
        flattened.extend(page)
    return flattened


class GhApi:
    """Minimal GitHub API adapter using the runner-provided gh CLI."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def _run(self, args: list[str], payload: Any | None = None) -> Any:
        command = ["gh", "api", *args]
        completed = subprocess.run(
            command,
            input=None if payload is None else canonical_json(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown GitHub API error"
            raise PolicyError(f"GitHub API request failed: {detail}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise PolicyError("GitHub API returned malformed JSON") from error

    def get(self, path: str, fresh: bool = False) -> Any:
        if fresh or path not in self._cache:
            self._cache[path] = self._run([path])
        return self._cache[path]

    def pages(self, path: str, fresh: bool = False) -> Any:
        cache_key = f"pages:{path}"
        if fresh or cache_key not in self._cache:
            self._cache[cache_key] = self._run(["--paginate", "--slurp", path])
        return self._cache[cache_key]

    def post(self, path: str, payload: Any) -> Any:
        return self._run(["--method", "POST", path, "--input", "-"], payload)

    def put(self, path: str, payload: Any) -> Any:
        return self._run(["--method", "PUT", path, "--input", "-"], payload)

    def patch(self, path: str, payload: Any) -> Any:
        return self._run(["--method", "PATCH", path, "--input", "-"], payload)

    def security_ghsas(self, repository: str, pull_request: int) -> tuple[str, ...]:
        owner, name = repository.split("/", 1)
        query = (
            "query($owner:String!,$name:String!,$endCursor:String){"
            "repository(owner:$owner,name:$name){"
            "vulnerabilityAlerts(first:100,after:$endCursor,states:[OPEN,FIXED]){"
            "nodes{state securityAdvisory{ghsaId}dependabotUpdate{pullRequest{number}}}"
            "pageInfo{hasNextPage endCursor}}}}"
        )
        pages = self._run(
            [
                "graphql",
                "--paginate",
                "--slurp",
                "-f",
                f"query={query}",
                "-f",
                f"owner={owner}",
                "-f",
                f"name={name}",
            ]
        )
        require(isinstance(pages, list), "vulnerability-alert pagination must be a list")
        ghsas: set[str] = set()
        for page in pages:
            try:
                nodes = page["data"]["repository"]["vulnerabilityAlerts"]["nodes"]
            except (KeyError, TypeError) as error:
                raise PolicyError("vulnerability-alert response schema is invalid") from error
            require(isinstance(nodes, list), "vulnerability-alert nodes must be a list")
            for node in nodes:
                if node.get("dependabotUpdate", {}).get("pullRequest", {}).get("number") != pull_request:
                    continue
                require(node.get("state") in {"OPEN", "FIXED"}, "associated alert state is not eligible")
                ghsa = node.get("securityAdvisory", {}).get("ghsaId")
                require(isinstance(ghsa, str) and ghsa.startswith("GHSA-"), "associated GHSA is invalid")
                ghsas.add(ghsa)
        require(bool(ghsas), "source pull request has no official OPEN or FIXED GitHub alert")
        return tuple(sorted(ghsas))


@dataclass(frozen=True)
class BlobEntry:
    path: str
    mode: str
    kind: str
    sha: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "mode": self.mode, "type": self.kind, "sha": self.sha}


@dataclass(frozen=True)
class SourceEvidence:
    repository: str
    pull_request: int
    source_base: str
    source_head: str
    source_merge: str
    source_tree: str
    ghsa_set: tuple[str, ...]
    changed_paths: tuple[str, ...]
    pre: dict[str, BlobEntry]
    post: dict[str, BlobEntry]
    classification_app_slug: str


@dataclass(frozen=True)
class SourceCandidate:
    repository: str
    workflow_run: int
    pull_request: int
    source_base: str
    source_head: str
    source_tree: str
    ghsa_set: tuple[str, ...]
    changed_paths: tuple[str, ...]

    def attestation(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_SCHEMA,
            "repository": self.repository,
            "pull_request": self.pull_request,
            "source_base_sha": self.source_base,
            "source_head_sha": self.source_head,
            "ghsa_set": list(self.ghsa_set),
            "profile": PROFILE,
        }


@dataclass(frozen=True)
class ProjectionEvidence:
    repository: str
    source_pull_request: int
    source_base: str
    source_head: str
    source_merge: str
    ghsa_set: tuple[str, ...]
    production_base: str
    projection_head: str
    projection_tree: str
    changed_paths: tuple[str, ...]
    manifest_path: str
    lock_path: str

    def attestation(self) -> dict[str, Any]:
        return {
            "schema": PROJECTION_SCHEMA,
            "repository": self.repository,
            "source_pull_request": self.source_pull_request,
            "source_base_sha": self.source_base,
            "source_head_sha": self.source_head,
            "source_merge_sha": self.source_merge,
            "ghsa_set": list(self.ghsa_set),
            "production_base_sha": self.production_base,
            "projection_head_sha": self.projection_head,
            "projection_tree_sha": self.projection_tree,
            "changed_paths": list(self.changed_paths),
            "manifest_path": self.manifest_path,
            "lock_path": self.lock_path,
            "profile": PROFILE,
        }


def check_runs(api: GhApi, repository: str, sha: str, fresh: bool = False) -> list[dict[str, Any]]:
    suffix = "?filter=latest&per_page=100" if fresh else "?per_page=100"
    pages = api.pages(
        f"repos/{repository}/commits/{sha}/check-runs{suffix}",
        fresh=fresh,
    )
    require(isinstance(pages, list), "check-run pagination must be a list")
    result: list[dict[str, Any]] = []
    for page in pages:
        require(isinstance(page, dict), "check-run page must be an object")
        runs = page.get("check_runs")
        require(isinstance(runs, list), "check-run page has no check_runs list")
        result.extend(runs)
    return result


def parse_attestation_check(
    api: GhApi,
    repository: str,
    sha: str,
    name: str,
    app_id: int,
    schema: str,
) -> tuple[dict[str, Any], str]:
    candidates: list[tuple[dict[str, Any], str]] = []
    for run in check_runs(api, repository, sha):
        if not (
            run.get("name") == name
            and run.get("head_sha") == sha
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and run.get("app", {}).get("id") == app_id
        ):
            continue
        summary = run.get("output", {}).get("summary")
        require(isinstance(summary, str), f"{name} check has no machine-readable summary")
        try:
            attestation = json.loads(summary)
        except json.JSONDecodeError as error:
            raise PolicyError(f"{name} check summary is not JSON") from error
        require(isinstance(attestation, dict), f"{name} attestation must be an object")
        require(attestation.get("schema") == schema, f"{name} attestation schema is invalid")
        slug = run.get("app", {}).get("slug")
        require(isinstance(slug, str) and slug, f"{name} check App slug is missing")
        candidates.append((attestation, slug))
    require(len(candidates) == 1, f"expected exactly one trusted {name} check, found {len(candidates)}")
    return candidates[0]


def git_commit(api: GhApi, repository: str, sha: str) -> dict[str, Any]:
    value = api.get(f"repos/{repository}/git/commits/{require_sha(sha, 'commit')}")
    require(isinstance(value, dict), "git commit response must be an object")
    tree = value.get("tree", {}).get("sha")
    require_sha(str(tree), "commit tree")
    parents = value.get("parents")
    require(isinstance(parents, list), "git commit parents must be a list")
    for parent in parents:
        require_sha(str(parent.get("sha")), "commit parent")
    return value


def root_tree(api: GhApi, repository: str, commit_sha: str) -> tuple[str, dict[str, BlobEntry]]:
    commit = git_commit(api, repository, commit_sha)
    tree_sha = commit["tree"]["sha"]
    tree = api.get(f"repos/{repository}/git/trees/{tree_sha}")
    require(isinstance(tree, dict), "git tree response must be an object")
    require(tree.get("truncated") is not True, "git tree response is truncated")
    entries = tree.get("tree")
    require(isinstance(entries, list), "git tree entries must be a list")
    result: dict[str, BlobEntry] = {}
    for raw in entries:
        require(isinstance(raw, dict), "git tree entry must be an object")
        path = raw.get("path")
        require(isinstance(path, str) and path, "git tree path is invalid")
        require(path not in result, f"git tree contains duplicate path {path}")
        result[path] = BlobEntry(
            path=path,
            mode=str(raw.get("mode")),
            kind=str(raw.get("type")),
            sha=require_sha(str(raw.get("sha")), f"blob SHA for {path}"),
        )
    return tree_sha, result


def require_safe_blob(api: GhApi, repository: str, entry: BlobEntry) -> None:
    require(entry.mode == "100644", f"{entry.path} must be a non-executable regular file")
    require(entry.kind == "blob", f"{entry.path} must be a blob")
    blob = api.get(f"repos/{repository}/git/blobs/{entry.sha}")
    require(isinstance(blob, dict), f"blob response for {entry.path} is invalid")
    require(blob.get("encoding") == "base64", f"blob encoding for {entry.path} must be base64")
    declared_size = blob.get("size")
    require(isinstance(declared_size, int) and 0 < declared_size <= MAX_BLOB_BYTES, f"blob size for {entry.path} is invalid")
    content = blob.get("content")
    require(isinstance(content, str), f"blob content for {entry.path} is missing")
    try:
        decoded = base64.b64decode(content, validate=False)
    except (ValueError, TypeError) as error:
        raise PolicyError(f"blob content for {entry.path} is malformed") from error
    require(len(decoded) == declared_size, f"blob size for {entry.path} does not match content")
    require(b"\x00" not in decoded, f"blob {entry.path} is binary")


def load_pair(
    api: GhApi,
    repository: str,
    commit_sha: str,
    manifest_path: str,
    lock_path: str,
) -> tuple[str, dict[str, BlobEntry]]:
    tree_sha, entries = root_tree(api, repository, commit_sha)
    pair: dict[str, BlobEntry] = {}
    for path in (manifest_path, lock_path):
        require(path in entries, f"{path} is missing at {commit_sha}")
        entry = entries[path]
        require_safe_blob(api, repository, entry)
        pair[path] = entry
    return tree_sha, pair


def pull_files(api: GhApi, repository: str, pull_request: int) -> list[dict[str, Any]]:
    pages = api.pages(f"repos/{repository}/pulls/{pull_request}/files?per_page=100")
    files = flatten_pages(pages, "pull-request files")
    for item in files:
        require(isinstance(item, dict), "pull-request file entry must be an object")
    require(bool(files), "pull request has no changed files")
    return files


def require_dependabot_commit(commit: dict[str, Any]) -> None:
    require(commit.get("author", {}).get("login") == "dependabot[bot]", "source contains a non-Dependabot author")
    require(commit.get("committer", {}).get("login") == "web-flow", "source commit was not committed by GitHub")
    raw = commit.get("commit")
    require(isinstance(raw, dict), "source commit payload is invalid")
    require(
        raw.get("author", {}).get("name") == "dependabot[bot]"
        and raw.get("author", {}).get("email") == "49699333+dependabot[bot]@users.noreply.github.com",
        "source commit Git author is not the canonical Dependabot identity",
    )
    require(
        raw.get("committer", {}).get("name") == "GitHub"
        and raw.get("committer", {}).get("email") == "noreply@github.com",
        "source commit Git committer is not GitHub",
    )
    verification = raw.get("verification")
    require(
        isinstance(verification, dict)
        and verification.get("verified") is True
        and verification.get("reason") == "valid",
        "source contains a commit without a valid GitHub verification",
    )


def resolve_source_pointer(
    api: GhApi,
    repository: str,
    workflow_run: int,
    source_branch: str,
    expected_pull_request: int | None = None,
    expected_head: str | None = None,
    expected_base: str | None = None,
) -> tuple[dict[str, Any], int, str, str]:
    repository = require_repository(repository)
    workflow_run = require_pr_number(workflow_run, "workflow run")
    run = api.get(f"repos/{repository}/actions/runs/{workflow_run}", fresh=True)
    require(isinstance(run, dict), "CI workflow-run response must be an object")
    require(run.get("id") == workflow_run, "CI workflow-run ID mismatch")
    require(run.get("name") == CI_CHECK, "workflow-run name is not CI")
    require(run.get("path") == CI_WORKFLOW_PATH, "workflow-run path is not the governed CI caller")
    require(run.get("event") == "pull_request", "CI workflow run was not triggered by pull_request")
    require(run.get("status") == "completed", "CI workflow run is not complete")
    require(run.get("conclusion") == "success", "CI workflow run did not succeed")
    require(run.get("repository", {}).get("full_name") == repository, "CI workflow-run repository mismatch")
    require(run.get("head_repository", {}).get("full_name") == repository, "CI workflow-run head is not same-repository")
    require(run.get("actor", {}).get("login") == "dependabot[bot]", "CI workflow run was not initiated by Dependabot")
    run_head = require_sha(str(run.get("head_sha")), "CI workflow-run head")

    pointers = run.get("pull_requests")
    require(isinstance(pointers, list), "CI workflow-run pull-request pointers must be a list")
    require(len(pointers) <= 1, "CI workflow run identifies multiple pull requests")
    if pointers:
        pull_request = require_pr_number(pointers[0].get("number"), "CI workflow-run pull request")
    else:
        associated = flatten_pages(
            api.pages(f"repos/{repository}/commits/{run_head}/pulls?per_page=100", fresh=True),
            "CI head associations",
        )
        candidates = [
            item
            for item in associated
            if isinstance(item, dict)
            and item.get("state") == "open"
            and item.get("user", {}).get("login") == "dependabot[bot]"
            and item.get("base", {}).get("ref") == source_branch
            and item.get("head", {}).get("repo", {}).get("full_name") == repository
        ]
        require(len(candidates) == 1, f"CI head identifies {len(candidates)} eligible Dependabot pull requests")
        pull_request = require_pr_number(candidates[0].get("number"), "associated pull request")

    if expected_pull_request is not None:
        require(pull_request == expected_pull_request, "source pull-request number moved after preflight")
    pr = api.get(f"repos/{repository}/pulls/{pull_request}", fresh=True)
    require(isinstance(pr, dict), "source pull-request response must be an object")
    require(pr.get("number") == pull_request, "source pull-request number mismatch")
    require(pr.get("state") == "open", "source pull request is not open")
    require(pr.get("draft") is False, "source pull request is draft")
    require(pr.get("user", {}).get("login") == "dependabot[bot]", "source pull request is not Dependabot-authored")
    require(pr.get("base", {}).get("ref") == source_branch, "source pull-request base branch mismatch")
    require(pr.get("head", {}).get("repo", {}).get("full_name") == repository, "source pull-request head is not same-repository")
    require(pr.get("auto_merge") is None, "source pull request retains stale native auto-merge state")
    labels = pr.get("labels")
    require(isinstance(labels, list), "source pull-request labels must be a list")
    require(
        not any(isinstance(label, dict) and label.get("name") == "security-autopromote" for label in labels),
        "source pull request retains the retired security-autopromote label",
    )
    source_head = require_sha(str(pr.get("head", {}).get("sha")), "source head")
    source_base = require_sha(str(pr.get("base", {}).get("sha")), "source base")
    if expected_head is not None:
        require(source_head == expected_head, "source pull-request head moved after preflight")
    if expected_base is not None:
        require(source_base == expected_base, "source pull-request base moved after preflight")
    merge_candidate = pr.get("merge_commit_sha")
    allowed_run_heads = {source_head}
    if isinstance(merge_candidate, str) and SHA_RE.fullmatch(merge_candidate):
        allowed_run_heads.add(merge_candidate)
    require(run_head in allowed_run_heads, "CI workflow run is not bound to the live source head")
    require(ref_sha(api, repository, source_branch, fresh=True) == source_base, "source branch moved after CI")
    return pr, pull_request, source_head, source_base


def latest_check_state(
    api: GhApi,
    repository: str,
    head: str,
    name: str,
    app_id: int,
) -> str:
    named = [run for run in check_runs(api, repository, head, fresh=True) if run.get("name") == name]
    trusted = [run for run in named if run.get("app", {}).get("id") == app_id]
    if not trusted:
        require(not named, f"required check {name!r} is reported only by an untrusted App")
        return "pending"
    require(len(trusted) == 1, f"expected one latest trusted {name!r} check, found {len(trusted)}")
    run = trusted[0]
    require(run.get("head_sha") == head, f"required check {name!r} head mismatch")
    status = run.get("status")
    if status != "completed":
        require(status in {"queued", "in_progress", "pending", "waiting", "requested"}, f"required check {name!r} has invalid status")
        return "pending"
    require(run.get("conclusion") == "success", f"required check {name!r} completed without success")
    return "success"


def build_source_candidate(
    api: GhApi,
    repository: str,
    workflow_run: int,
    source_branch: str,
    manifest_path: str,
    lock_path: str,
    expected_pull_request: int | None = None,
    expected_head: str | None = None,
    expected_base: str | None = None,
    verify_alerts: bool = True,
) -> SourceCandidate:
    pr, pull_request, source_head, source_base = resolve_source_pointer(
        api,
        repository,
        workflow_run,
        source_branch,
        expected_pull_request,
        expected_head,
        expected_base,
    )
    commits = flatten_pages(
        api.pages(f"repos/{repository}/pulls/{pull_request}/commits?per_page=100", fresh=True),
        "source commits",
    )
    require(bool(commits), "source pull request has no commits")
    for commit in commits:
        require(isinstance(commit, dict), "source commit entry must be an object")
        require_dependabot_commit(commit)
    _, pre = load_pair(api, repository, source_base, manifest_path, lock_path)
    source_tree, post = load_pair(api, repository, source_head, manifest_path, lock_path)
    changed_paths = validate_pair_diff(
        pull_files(api, repository, pull_request),
        pre,
        post,
        manifest_path,
        lock_path,
    )
    merge_candidate = require_sha(str(pr.get("merge_commit_sha")), "source test merge")
    candidate = git_commit(api, repository, merge_candidate)
    require(
        [parent["sha"] for parent in candidate["parents"]] == [source_base, source_head],
        "source test merge parents do not equal current dev and source head",
    )
    require(candidate["tree"]["sha"] == source_tree, "source test merge tree does not equal source head tree")
    return SourceCandidate(
        repository=repository,
        workflow_run=workflow_run,
        pull_request=pull_request,
        source_base=source_base,
        source_head=source_head,
        source_tree=source_tree,
        ghsa_set=api.security_ghsas(repository, pull_request) if verify_alerts else (),
        changed_paths=changed_paths,
    )


def wait_for_source_candidate(
    api: GhApi,
    repository: str,
    workflow_run: int,
    source_branch: str,
    manifest_path: str,
    lock_path: str,
    wait_seconds: int,
    poll_seconds: int = 10,
    expected_pull_request: int | None = None,
    expected_head: str | None = None,
    expected_base: str | None = None,
    verify_alerts: bool = True,
) -> SourceCandidate:
    require(0 <= wait_seconds <= 300, "check wait must be between zero and 300 seconds")
    deadline = time.monotonic() + wait_seconds
    while True:
        _, pull_request, source_head, _ = resolve_source_pointer(
            api,
            repository,
            workflow_run,
            source_branch,
            expected_pull_request,
            expected_head,
            expected_base,
        )
        ci_state = latest_check_state(api, repository, source_head, CI_CHECK, TRUSTED_CI_APP_ID)
        codeql_state = latest_check_state(api, repository, source_head, CODEQL_CHECK, TRUSTED_CODEQL_APP_ID)
        if ci_state == codeql_state == "success":
            return build_source_candidate(
                api,
                repository,
                workflow_run,
                source_branch,
                manifest_path,
                lock_path,
                expected_pull_request or pull_request,
                expected_head or source_head,
                expected_base,
                verify_alerts,
            )
        if time.monotonic() >= deadline:
            raise PolicyError("trusted CI and CodeQL did not both succeed before the bounded deadline")
        time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))


def upsert_source_classification(api: GhApi, candidate: SourceCandidate) -> str:
    require(bool(candidate.ghsa_set), "source classification requires an official vulnerability-alert association")
    external_id = f"{SOURCE_SCHEMA}:{candidate.pull_request}:{candidate.source_head}"
    summary = canonical_json(candidate.attestation())
    create_payload = {
        "name": SOURCE_CHECK,
        "head_sha": candidate.source_head,
        "status": "completed",
        "conclusion": "success",
        "external_id": external_id,
        "output": {
            "title": "Official security association verified",
            "summary": summary,
        },
    }
    checks_path = f"repos/{candidate.repository}/commits/{candidate.source_head}/check-runs?filter=all&per_page=100"
    pages = api.pages(checks_path, fresh=True)
    existing: list[dict[str, Any]] = []
    for page in pages:
        require(isinstance(page, dict), "classification check-run page must be an object")
        runs = page.get("check_runs")
        require(isinstance(runs, list), "classification check-run page has no check_runs list")
        existing.extend(
            run
            for run in runs
            if run.get("name") == SOURCE_CHECK
            and run.get("head_sha") == candidate.source_head
            and run.get("app", {}).get("id") == TRUSTED_SECURITY_AUTOMATION_APP_ID
        )
    require(len(existing) <= 1, "multiple trusted source-classification checks already exist")
    if existing:
        require(existing[0].get("external_id") == external_id, "existing classification external identity conflicts")
        check_id = require_pr_number(existing[0].get("id"), "source-classification check")
        payload = dict(create_payload)
        payload.pop("head_sha")
        result = api.patch(f"repos/{candidate.repository}/check-runs/{check_id}", payload)
    else:
        result = api.post(f"repos/{candidate.repository}/check-runs", create_payload)
    require(isinstance(result, dict), "source-classification check response must be an object")
    require(result.get("head_sha") == candidate.source_head, "source-classification check head mismatch")
    require(result.get("app", {}).get("id") == TRUSTED_SECURITY_AUTOMATION_APP_ID, "source classification was not written by the trusted App")
    slug = result.get("app", {}).get("slug")
    require(isinstance(slug, str) and slug, "source-classification App slug is missing")
    result_id = require_pr_number(result.get("id"), "source-classification check")
    post_write: list[dict[str, Any]] = []
    for page in api.pages(checks_path, fresh=True):
        require(isinstance(page, dict), "post-write classification page must be an object")
        runs = page.get("check_runs")
        require(isinstance(runs, list), "post-write classification page has no check_runs list")
        post_write.extend(
            run
            for run in runs
            if run.get("name") == SOURCE_CHECK
            and run.get("head_sha") == candidate.source_head
            and run.get("app", {}).get("id") == TRUSTED_SECURITY_AUTOMATION_APP_ID
        )
    require(len(post_write) == 1, "trusted source-classification check is not unique after write")
    require(post_write[0].get("id") == result_id, "post-write source-classification check identity mismatch")
    require(post_write[0].get("external_id") == external_id, "post-write classification external identity mismatch")
    return slug


def merge_source_candidate(
    api: GhApi,
    repository: str,
    workflow_run: int,
    source_branch: str,
    manifest_path: str,
    lock_path: str,
    expected_pull_request: int,
    expected_head: str,
    expected_base: str,
) -> str:
    candidate = wait_for_source_candidate(
        api,
        repository,
        workflow_run,
        source_branch,
        manifest_path,
        lock_path,
        0,
        expected_pull_request=expected_pull_request,
        expected_head=expected_head,
        expected_base=expected_base,
    )
    app_slug = upsert_source_classification(api, candidate)
    final = wait_for_source_candidate(
        api,
        repository,
        workflow_run,
        source_branch,
        manifest_path,
        lock_path,
        0,
        expected_pull_request=candidate.pull_request,
        expected_head=candidate.source_head,
        expected_base=candidate.source_base,
    )
    require(final == candidate, "source evidence changed after classification")
    result = api.put(
        f"repos/{repository}/pulls/{candidate.pull_request}/merge",
        {"sha": candidate.source_head, "merge_method": "merge"},
    )
    require(isinstance(result, dict) and result.get("merged") is True, "GitHub did not merge the exact security source")
    merge_sha = require_sha(str(result.get("sha")), "source merge result")
    commit = git_commit(api, repository, merge_sha)
    require(
        [parent["sha"] for parent in commit["parents"]] == [candidate.source_base, candidate.source_head],
        "source merge parents do not equal attested dev and source head",
    )
    require(commit["tree"]["sha"] == candidate.source_tree, "source merge tree does not equal source head tree")
    merged_pr = api.get(f"repos/{repository}/pulls/{candidate.pull_request}", fresh=True)
    require(merged_pr.get("merged_at") is not None, "source pull request is not recorded as merged")
    require(merged_pr.get("merge_commit_sha") == merge_sha, "source pull-request merge SHA mismatch")
    require(merged_pr.get("merged_by", {}).get("login") == f"{app_slug}[bot]", "source merge actor is not the classification App")
    return merge_sha


def validate_pair_diff(
    files: Iterable[dict[str, Any]],
    pre: dict[str, BlobEntry],
    post: dict[str, BlobEntry],
    manifest_path: str,
    lock_path: str,
) -> tuple[str, ...]:
    allowed = {manifest_path, lock_path}
    file_paths: list[str] = []
    for item in files:
        path = item.get("filename")
        require(path in allowed, f"security patch changed disallowed path {path!r}")
        require(item.get("status") == "modified", f"security patch path {path} must be modified")
        require(not item.get("previous_filename"), f"security patch path {path} must not be renamed")
        file_paths.append(str(path))
    require(len(file_paths) == len(set(file_paths)), "security patch file list contains duplicates")
    changed = tuple(
        path
        for path in (manifest_path, lock_path)
        if pre[path].sha != post[path].sha or pre[path].mode != post[path].mode
    )
    require(lock_path in changed, f"security patch must change {lock_path}")
    require(set(file_paths) == set(changed), "pull-request files do not equal the exact blob delta")
    return changed


def source_pull_request(api: GhApi, repository: str, source_merge: str, source_branch: str) -> dict[str, Any]:
    pulls = flatten_pages(
        api.pages(f"repos/{repository}/commits/{source_merge}/pulls?per_page=100"),
        "commit-associated pull requests",
    )
    matches = [
        pull
        for pull in pulls
        if isinstance(pull, dict)
        and pull.get("merged_at") is not None
        and pull.get("merge_commit_sha") == source_merge
        and pull.get("base", {}).get("ref") == source_branch
        and pull.get("user", {}).get("login") == "dependabot[bot]"
    ]
    require(len(matches) == 1, f"expected one merged Dependabot source PR, found {len(matches)}")
    return matches[0]


def build_source_evidence(
    api: GhApi,
    repository: str,
    source_merge: str,
    source_branch: str,
    manifest_path: str,
    lock_path: str,
) -> SourceEvidence:
    repository = require_repository(repository)
    source_merge = require_sha(source_merge, "source merge")
    pull = source_pull_request(api, repository, source_merge, source_branch)
    pull_number = require_pr_number(pull.get("number"), "source pull request")
    source_head = require_sha(str(pull.get("head", {}).get("sha")), "source head")

    attestation, app_slug = parse_attestation_check(
        api,
        repository,
        source_head,
        SOURCE_CHECK,
        TRUSTED_SECURITY_AUTOMATION_APP_ID,
        SOURCE_SCHEMA,
    )
    require(attestation.get("repository") == repository, "source attestation repository mismatch")
    require(attestation.get("pull_request") == pull_number, "source attestation PR mismatch")
    require(attestation.get("source_head_sha") == source_head, "source attestation head mismatch")
    require(attestation.get("profile") == PROFILE, "source attestation is not production-profile eligible")
    attested_base = require_sha(str(attestation.get("source_base_sha")), "attested source base")
    attested_ghsas = attestation.get("ghsa_set")
    require(
        isinstance(attested_ghsas, list)
        and attested_ghsas == sorted(set(attested_ghsas))
        and all(isinstance(value, str) and value.startswith("GHSA-") for value in attested_ghsas),
        "source attestation GHSA set is invalid",
    )

    merge_commit = git_commit(api, repository, source_merge)
    parents = merge_commit["parents"]
    require(len(parents) == 2, "initial site profile requires a two-parent merge commit")
    source_base = parents[0]["sha"]
    require(source_base == attested_base, "source merge first parent does not match attested base")
    require(parents[1]["sha"] == source_head, "source merge second parent does not match classified head")
    head_commit = git_commit(api, repository, source_head)
    source_tree = merge_commit["tree"]["sha"]
    require(source_tree == head_commit["tree"]["sha"], "source merge tree does not equal source head tree")
    require(pull.get("merged_by", {}).get("login") == f"{app_slug}[bot]", "source PR was not merged by the classification App")

    live_ghsas = api.security_ghsas(repository, pull_number)
    require(tuple(attested_ghsas) == live_ghsas, "live GHSA set does not equal source attestation")

    _, pre = load_pair(api, repository, source_base, manifest_path, lock_path)
    _, post = load_pair(api, repository, source_head, manifest_path, lock_path)
    changed_paths = validate_pair_diff(
        pull_files(api, repository, pull_number),
        pre,
        post,
        manifest_path,
        lock_path,
    )
    return SourceEvidence(
        repository=repository,
        pull_request=pull_number,
        source_base=source_base,
        source_head=source_head,
        source_merge=source_merge,
        source_tree=source_tree,
        ghsa_set=live_ghsas,
        changed_paths=changed_paths,
        pre=pre,
        post=post,
        classification_app_slug=app_slug,
    )


def ref_sha(api: GhApi, repository: str, branch: str, *, fresh: bool = False) -> str:
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch)), "branch name is invalid")
    ref = api.get(f"repos/{repository}/git/ref/heads/{quote(branch, safe='/')}", fresh=fresh)
    return require_sha(str(ref.get("object", {}).get("sha")), f"{branch} ref")


def assert_pair_preimage(
    current: dict[str, BlobEntry],
    source: dict[str, BlobEntry],
    manifest_path: str,
    lock_path: str,
) -> None:
    for path in (manifest_path, lock_path):
        require(current[path] == source[path], f"current production preimage for {path} differs from source base")


def open_lock_proposals(
    api: GhApi,
    repository: str,
    target_branch: str,
    lock_path: str,
    *,
    fresh: bool = False,
) -> list[int]:
    pulls = flatten_pages(
        api.pages(
            f"repos/{repository}/pulls?state=open&base={quote(target_branch, safe='')}&per_page=100",
            fresh=fresh,
        ),
        "open production pull requests",
    )
    collisions: list[int] = []
    for pull in pulls:
        require(isinstance(pull, dict), "open pull-request entry must be an object")
        number = require_pr_number(pull.get("number"), "open pull request")
        if any(item.get("filename") == lock_path for item in pull_files(api, repository, number)):
            collisions.append(number)
    return collisions


def assert_only_lock_proposal(
    api: GhApi,
    repository: str,
    target_branch: str,
    lock_path: str,
    pull_request: int,
) -> None:
    collisions = open_lock_proposals(api, repository, target_branch, lock_path, fresh=True)
    require(collisions == [pull_request], f"open production lock proposals are ambiguous: {collisions}")


def assert_root_tree_projection(
    main_entries: dict[str, BlobEntry],
    result_entries: dict[str, BlobEntry],
    changed_paths: tuple[str, ...],
    post: dict[str, BlobEntry],
) -> None:
    expected = dict(main_entries)
    for path in changed_paths:
        expected[path] = post[path]
    require(result_entries == expected, "projection result tree contains an extra or mismatched entry")


def verify_created_projection_identity(
    pr_result: dict[str, Any],
    check_result: dict[str, Any],
    projection_pr: int,
    target_branch: str,
    projection_head: str,
) -> None:
    require(pr_result.get("number") == projection_pr and pr_result.get("state") == "open", "created projection PR is not open")
    require(pr_result.get("base", {}).get("ref") == target_branch, "created projection PR base mismatch")
    require(pr_result.get("head", {}).get("sha") == projection_head, "created projection PR head mismatch")
    projection_login = pr_result.get("user", {}).get("login")
    require(isinstance(projection_login, str) and projection_login.endswith("[bot]"), "created projection PR has no App author")
    require(check_result.get("head_sha") == projection_head, "created projection check head mismatch")
    require(
        check_result.get("app", {}).get("id") == TRUSTED_SECURITY_AUTOMATION_APP_ID,
        "projection token does not belong to the centrally trusted App",
    )
    projection_slug = check_result.get("app", {}).get("slug")
    require(
        isinstance(projection_slug, str)
        and projection_slug
        and projection_login == f"{projection_slug}[bot]",
        "projection PR and attestation check have different App owners",
    )


def create_projection(
    api: GhApi,
    source: SourceEvidence,
    target_branch: str,
    manifest_path: str,
    lock_path: str,
    draft: bool,
) -> tuple[int, ProjectionEvidence]:
    repository = source.repository
    collisions = open_lock_proposals(api, repository, target_branch, lock_path, fresh=True)
    require(not collisions, f"open production PRs already touch {lock_path}: {collisions}")

    production_base = ref_sha(api, repository, target_branch)
    production_tree, production_entries = root_tree(api, repository, production_base)
    _, production_pair = load_pair(api, repository, production_base, manifest_path, lock_path)
    assert_pair_preimage(production_pair, source.pre, manifest_path, lock_path)

    tree_payload = {
        "base_tree": production_tree,
        "tree": [source.post[path].as_dict() for path in source.changed_paths],
    }
    tree_result = api.post(f"repos/{repository}/git/trees", tree_payload)
    projection_tree = require_sha(str(tree_result.get("sha")), "projection tree")
    _, projected_entries = root_tree_from_tree(api, repository, projection_tree)
    assert_root_tree_projection(production_entries, projected_entries, source.changed_paths, source.post)

    message_data = {
        "schema": PROJECTION_SCHEMA,
        "source_pull_request": source.pull_request,
        "source_base_sha": source.source_base,
        "source_head_sha": source.source_head,
        "source_merge_sha": source.source_merge,
        "production_base_sha": production_base,
        "ghsa_set": list(source.ghsa_set),
    }
    source_commit = git_commit(api, repository, source.source_merge)
    timestamp = source_commit.get("committer", {}).get("date")
    require(isinstance(timestamp, str) and timestamp, "source merge committer date is missing")
    identity = {
        "name": "forgingalpha-security-projector[bot]",
        "email": "forgingalpha-security-projector[bot]@users.noreply.github.com",
        "date": timestamp,
    }
    commit_result = api.post(
        f"repos/{repository}/git/commits",
        {
            "message": "fix(security): project verified Dependabot patch\n\n" + canonical_json(message_data),
            "tree": projection_tree,
            "parents": [production_base],
            "author": identity,
            "committer": identity,
        },
    )
    projection_head = require_sha(str(commit_result.get("sha")), "projection head")
    branch = f"security/dependabot-{source.pull_request}-{source.source_head[:12]}"
    api.post(
        f"repos/{repository}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": projection_head},
    )

    evidence = ProjectionEvidence(
        repository=repository,
        source_pull_request=source.pull_request,
        source_base=source.source_base,
        source_head=source.source_head,
        source_merge=source.source_merge,
        ghsa_set=source.ghsa_set,
        production_base=production_base,
        projection_head=projection_head,
        projection_tree=projection_tree,
        changed_paths=source.changed_paths,
        manifest_path=manifest_path,
        lock_path=lock_path,
    )
    attestation = evidence.attestation()
    digest = hashlib.sha256(canonical_json(attestation).encode()).hexdigest()
    check_result = api.post(
        f"repos/{repository}/check-runs",
        {
            "name": PROJECTION_CHECK,
            "head_sha": projection_head,
            "status": "completed",
            "conclusion": "success",
            "external_id": f"{PROJECTION_SCHEMA}:{digest}",
            "output": {
                "title": "Exact security projection verified",
                "summary": canonical_json(attestation),
            },
        },
    )

    ghsa_text = ", ".join(source.ghsa_set)
    body = (
        "## Exact security projection\n\n"
        f"- source Dependabot PR: #{source.pull_request}\n"
        f"- source head: `{source.source_head}`\n"
        f"- source merge: `{source.source_merge}`\n"
        f"- production base: `{production_base}`\n"
        f"- advisories: {ghsa_text}\n\n"
        "This body is routing information only. Protected activation independently reconstructs every value."
    )
    pr_result = api.post(
        f"repos/{repository}/pulls",
        {
            "title": f"fix(security): project Dependabot #{source.pull_request}",
            "head": branch,
            "base": target_branch,
            "body": body,
            "draft": draft,
            "maintainer_can_modify": False,
        },
    )
    projection_pr = require_pr_number(pr_result.get("number"), "projection pull request")
    assert_only_lock_proposal(api, repository, target_branch, lock_path, projection_pr)
    verify_created_projection_identity(
        pr_result,
        check_result,
        projection_pr,
        target_branch,
        projection_head,
    )
    return projection_pr, evidence


def root_tree_from_tree(api: GhApi, repository: str, tree_sha: str) -> tuple[str, dict[str, BlobEntry]]:
    tree_sha = require_sha(tree_sha, "tree")
    tree = api.get(f"repos/{repository}/git/trees/{tree_sha}")
    require(isinstance(tree, dict), "git tree response must be an object")
    require(tree.get("truncated") is not True, "git tree response is truncated")
    entries = tree.get("tree")
    require(isinstance(entries, list), "git tree entries must be a list")
    result: dict[str, BlobEntry] = {}
    for raw in entries:
        path = raw.get("path") if isinstance(raw, dict) else None
        require(isinstance(path, str) and path and path not in result, "git tree path is invalid or duplicate")
        result[path] = BlobEntry(
            path=path,
            mode=str(raw.get("mode")),
            kind=str(raw.get("type")),
            sha=require_sha(str(raw.get("sha")), f"tree entry SHA for {path}"),
        )
    return tree_sha, result


def parse_projection_attestation(raw: dict[str, Any]) -> ProjectionEvidence:
    require(raw.get("schema") == PROJECTION_SCHEMA, "projection attestation schema mismatch")
    repository = require_repository(str(raw.get("repository")))
    source_pr = require_pr_number(raw.get("source_pull_request"), "source pull request")
    ghsa_set = raw.get("ghsa_set")
    require(
        isinstance(ghsa_set, list)
        and ghsa_set == sorted(set(ghsa_set))
        and all(isinstance(value, str) and value.startswith("GHSA-") for value in ghsa_set),
        "projection GHSA set is invalid",
    )
    changed = raw.get("changed_paths")
    require(isinstance(changed, list) and changed, "projection changed_paths is invalid")
    manifest = require_root_file(str(raw.get("manifest_path")), "manifest path")
    lock = require_root_file(str(raw.get("lock_path")), "lock path")
    require(raw.get("profile") == PROFILE, "projection profile is invalid")
    return ProjectionEvidence(
        repository=repository,
        source_pull_request=source_pr,
        source_base=require_sha(str(raw.get("source_base_sha")), "projection source base"),
        source_head=require_sha(str(raw.get("source_head_sha")), "projection source head"),
        source_merge=require_sha(str(raw.get("source_merge_sha")), "projection source merge"),
        ghsa_set=tuple(ghsa_set),
        production_base=require_sha(str(raw.get("production_base_sha")), "projection production base"),
        projection_head=require_sha(str(raw.get("projection_head_sha")), "projection head"),
        projection_tree=require_sha(str(raw.get("projection_tree_sha")), "projection tree"),
        changed_paths=tuple(changed),
        manifest_path=manifest,
        lock_path=lock,
    )


def verify_projection_admission(
    api: GhApi,
    repository: str,
    pull_request: int,
    target_branch: str,
) -> ProjectionEvidence:
    """Admit a trusted exact projection to CI without granting merge authority."""

    repository = require_repository(repository)
    pull_request = require_pr_number(pull_request)
    pr = api.get(f"repos/{repository}/pulls/{pull_request}")
    require(pr.get("number") == pull_request and pr.get("state") == "open", "projection PR must be open")
    require(pr.get("base", {}).get("ref") == target_branch, "projection PR targets the wrong branch")
    require(pr.get("head", {}).get("repo", {}).get("full_name") == repository, "projection PR head must be same-repository")
    projection_head = require_sha(str(pr.get("head", {}).get("sha")), "live projection head")

    raw_attestation, projection_slug = parse_attestation_check(
        api,
        repository,
        projection_head,
        PROJECTION_CHECK,
        TRUSTED_SECURITY_AUTOMATION_APP_ID,
        PROJECTION_SCHEMA,
    )
    evidence = parse_projection_attestation(raw_attestation)
    require(evidence.repository == repository, "projection repository mismatch")
    require(evidence.projection_head == projection_head, "projection attestation head mismatch")
    require(pr.get("user", {}).get("login") == f"{projection_slug}[bot]", "projection PR was not opened by the projection App")
    assert_only_lock_proposal(api, repository, target_branch, evidence.lock_path, pull_request)

    current_production = ref_sha(api, repository, target_branch)
    require(current_production == evidence.production_base, "production base moved after projection")
    require(pr.get("base", {}).get("sha") == evidence.production_base, "projection PR base SHA mismatch")

    commit = git_commit(api, repository, projection_head)
    require(
        [parent["sha"] for parent in commit["parents"]] == [evidence.production_base],
        "projection commit must have exactly the attested production parent",
    )
    require(commit["tree"]["sha"] == evidence.projection_tree, "projection tree mismatch")
    _, production_entries = root_tree(api, repository, evidence.production_base)
    _, projected_entries = root_tree(api, repository, projection_head)
    actual_changed = tuple(
        sorted(
            path
            for path in set(production_entries) | set(projected_entries)
            if production_entries.get(path) != projected_entries.get(path)
        )
    )
    require(actual_changed == tuple(sorted(evidence.changed_paths)), "projection root-tree delta does not match attestation")
    require(evidence.lock_path in evidence.changed_paths, "projection must change the attested lockfile")
    require(set(evidence.changed_paths) <= {evidence.manifest_path, evidence.lock_path}, "projection changes a disallowed path")
    for path in evidence.changed_paths:
        require(path in projected_entries, f"projection path {path} is missing")
        require_safe_blob(api, repository, projected_entries[path])

    files = pull_files(api, repository, pull_request)
    file_paths: list[str] = []
    for item in files:
        path = item.get("filename")
        require(path in evidence.changed_paths, f"projection PR changed unattested path {path!r}")
        require(item.get("status") == "modified", f"projection path {path} must be modified")
        require(not item.get("previous_filename"), f"projection path {path} must not be renamed")
        file_paths.append(str(path))
    require(len(file_paths) == len(set(file_paths)), "projection PR file list contains duplicates")
    require(set(file_paths) == set(evidence.changed_paths), "projection PR files do not match attestation")

    commits = flatten_pages(
        api.pages(f"repos/{repository}/pulls/{pull_request}/commits?per_page=100"),
        "projection commits",
    )
    require(len(commits) == 1 and commits[0].get("sha") == projection_head, "projection PR must contain one exact commit")
    return evidence


def verify_projection(
    api: GhApi,
    repository: str,
    pull_request: int,
    source_branch: str,
    target_branch: str,
    require_ready: bool,
) -> tuple[ProjectionEvidence, dict[str, Any]]:
    repository = require_repository(repository)
    pull_request = require_pr_number(pull_request)
    pr = api.get(f"repos/{repository}/pulls/{pull_request}")
    require(pr.get("number") == pull_request and pr.get("state") == "open", "projection PR must be open")
    if require_ready:
        require(pr.get("draft") is False, "projection PR must be ready")
    require(pr.get("base", {}).get("ref") == target_branch, "projection PR targets the wrong branch")
    require(pr.get("head", {}).get("repo", {}).get("full_name") == repository, "projection PR head must be same-repository")
    projection_head = require_sha(str(pr.get("head", {}).get("sha")), "live projection head")

    raw_attestation, projection_slug = parse_attestation_check(
        api,
        repository,
        projection_head,
        PROJECTION_CHECK,
        TRUSTED_SECURITY_AUTOMATION_APP_ID,
        PROJECTION_SCHEMA,
    )
    evidence = parse_projection_attestation(raw_attestation)
    require(evidence.repository == repository, "projection repository mismatch")
    require(evidence.projection_head == projection_head, "projection attestation head mismatch")
    require(pr.get("user", {}).get("login") == f"{projection_slug}[bot]", "projection PR was not opened by the projection App")
    assert_only_lock_proposal(api, repository, target_branch, evidence.lock_path, pull_request)

    source = build_source_evidence(
        api,
        repository,
        evidence.source_merge,
        source_branch,
        evidence.manifest_path,
        evidence.lock_path,
    )
    require(source.pull_request == evidence.source_pull_request, "projection source PR mismatch")
    require(source.source_base == evidence.source_base, "projection source base mismatch")
    require(source.source_head == evidence.source_head, "projection source head mismatch")
    require(source.ghsa_set == evidence.ghsa_set, "projection GHSA set changed")
    require(source.changed_paths == evidence.changed_paths, "projection changed path set changed")

    current_production = ref_sha(api, repository, target_branch)
    require(current_production == evidence.production_base, "production base moved after projection")
    _, production_pair = load_pair(
        api,
        repository,
        evidence.production_base,
        evidence.manifest_path,
        evidence.lock_path,
    )
    assert_pair_preimage(production_pair, source.pre, evidence.manifest_path, evidence.lock_path)

    projection_commit = git_commit(api, repository, projection_head)
    require(
        [parent["sha"] for parent in projection_commit["parents"]] == [evidence.production_base],
        "projection commit must have exactly the attested production parent",
    )
    require(projection_commit["tree"]["sha"] == evidence.projection_tree, "projection tree mismatch")
    _, production_entries = root_tree(api, repository, evidence.production_base)
    _, projected_entries = root_tree(api, repository, projection_head)
    assert_root_tree_projection(production_entries, projected_entries, source.changed_paths, source.post)
    validate_pair_diff(
        pull_files(api, repository, pull_request),
        source.pre,
        source.post,
        evidence.manifest_path,
        evidence.lock_path,
    )
    commits = flatten_pages(
        api.pages(f"repos/{repository}/pulls/{pull_request}/commits?per_page=100"),
        "projection commits",
    )
    require(len(commits) == 1 and commits[0].get("sha") == projection_head, "projection PR must contain one exact commit")
    return evidence, pr


def verify_successful_check(
    api: GhApi,
    repository: str,
    candidate_shas: tuple[str, ...],
    name: str,
    app_id: int,
) -> None:
    matches: list[dict[str, Any]] = []
    for sha in candidate_shas:
        matches.extend(
            run
            for run in check_runs(api, repository, sha)
            if run.get("name") == name
            and run.get("head_sha") == sha
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and run.get("app", {}).get("id") == app_id
        )
    require(bool(matches), f"required trusted check {name!r} is not successful")


def verify_ci_workflow(
    api: GhApi,
    repository: str,
    pull_request: int,
    merge_candidate: str,
    workflow_path: str,
) -> None:
    pages = api.pages(
        f"repos/{repository}/actions/runs?event=pull_request&status=success&head_sha={merge_candidate}&per_page=100"
    )
    require(isinstance(pages, list), "workflow-run pagination must be a list")
    runs: list[dict[str, Any]] = []
    for page in pages:
        require(isinstance(page, dict), "workflow-run page must be an object")
        page_runs = page.get("workflow_runs")
        require(isinstance(page_runs, list), "workflow-run page has no workflow_runs list")
        runs.extend(page_runs)
    matches = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("path") == workflow_path
        and run.get("event") == "pull_request"
        and run.get("head_sha") == merge_candidate
        and run.get("conclusion") == "success"
        and run.get("repository", {}).get("full_name") == repository
        and any(pointer.get("number") == pull_request for pointer in run.get("pull_requests", []))
    ]
    require(bool(matches), "exact trusted CI workflow run is not successful")


def verify_checks(
    api: GhApi,
    repository: str,
    pull_request: int,
    pr: dict[str, Any],
    evidence: ProjectionEvidence,
    ci_workflow_path: str,
    ci_check_name: str,
    ci_app_id: int,
    codeql_check_name: str,
    codeql_app_id: int,
) -> None:
    head = require_sha(str(pr.get("head", {}).get("sha")), "projection head")
    merge_candidate = require_sha(str(pr.get("merge_commit_sha")), "projection merge candidate")
    candidate = git_commit(api, repository, merge_candidate)
    require(
        [parent["sha"] for parent in candidate["parents"]]
        == [evidence.production_base, evidence.projection_head],
        "live test merge parents do not equal production base and projection head",
    )
    require(candidate["tree"]["sha"] == evidence.projection_tree, "live test merge tree does not equal projection tree")
    verify_ci_workflow(api, repository, pull_request, head, ci_workflow_path)
    verify_successful_check(api, repository, (head,), ci_check_name, ci_app_id)
    verify_successful_check(api, repository, (head,), codeql_check_name, codeql_app_id)


def verify_post_merge(
    api: GhApi,
    repository: str,
    target_branch: str,
    merge_sha: str,
    production_base: str,
    projection_head: str,
    projection_tree: str,
) -> None:
    merge_sha = require_sha(merge_sha, "merge result")
    require(ref_sha(api, repository, target_branch) == merge_sha, "target branch does not equal merge result")
    commit = git_commit(api, repository, merge_sha)
    require(
        [parent["sha"] for parent in commit["parents"]] == [production_base, projection_head],
        "merge result parents do not equal production base and projection head",
    )
    require(commit["tree"]["sha"] == projection_tree, "merge result tree does not equal projection tree")


def emit_output(name: str, value: str | int | bool) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    rendered = str(value).lower() if isinstance(value, bool) else str(value)
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={rendered}\n")
    else:
        print(f"{name}={rendered}")


def add_common_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-branch", default="dev")
    parser.add_argument("--target-branch", default="main")
    parser.add_argument("--manifest-path", default="package.json")
    parser.add_argument("--lock-path", default="package-lock.json")


def add_source_run_args(parser: argparse.ArgumentParser) -> None:
    add_common_source_args(parser)
    parser.add_argument("--workflow-run-id", required=True)


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_parser = subparsers.add_parser("verify-source")
    add_common_source_args(source_parser)
    source_parser.add_argument("--source-merge-sha", required=True)

    preflight_parser = subparsers.add_parser("preflight-source")
    add_source_run_args(preflight_parser)
    preflight_parser.add_argument("--wait-seconds", type=int, default=300)

    merge_source_parser = subparsers.add_parser("merge-source")
    add_source_run_args(merge_source_parser)
    merge_source_parser.add_argument("--pull-request", required=True)
    merge_source_parser.add_argument("--expected-head-sha", required=True)
    merge_source_parser.add_argument("--expected-base-sha", required=True)

    project_parser = subparsers.add_parser("project")
    add_common_source_args(project_parser)
    project_parser.add_argument("--source-merge-sha", required=True)
    project_parser.add_argument("--draft", choices=("true", "false"), default="true")

    verify_parser = subparsers.add_parser("verify-projection")
    add_common_source_args(verify_parser)
    verify_parser.add_argument("--pull-request", required=True)
    verify_parser.add_argument("--require-ready", choices=("true", "false"), default="true")
    verify_parser.add_argument("--verify-checks", choices=("true", "false"), default="false")
    verify_parser.add_argument("--ci-workflow-path", default=".github/workflows/ci.yml")
    verify_parser.add_argument("--ci-check-name", default="CI")
    verify_parser.add_argument("--ci-app-id")
    verify_parser.add_argument("--codeql-check-name", default="CodeQL")
    verify_parser.add_argument("--codeql-app-id")

    admission_parser = subparsers.add_parser("verify-ci-admission")
    admission_parser.add_argument("--repository", required=True)
    admission_parser.add_argument("--pull-request", required=True)
    admission_parser.add_argument("--target-branch", default="main")

    post_parser = subparsers.add_parser("verify-post-merge")
    post_parser.add_argument("--repository", required=True)
    post_parser.add_argument("--target-branch", default="main")
    post_parser.add_argument("--merge-sha", required=True)
    post_parser.add_argument("--production-base", required=True)
    post_parser.add_argument("--projection-head", required=True)
    post_parser.add_argument("--projection-tree", required=True)

    args = parser.parse_args(argv)
    api = GhApi()
    try:
        if args.command in {
            "verify-source",
            "preflight-source",
            "merge-source",
            "project",
            "verify-projection",
        }:
            manifest_path = require_root_file(args.manifest_path, "manifest path")
            lock_path = require_root_file(args.lock_path, "lock path")
            require(manifest_path != lock_path, "manifest and lock paths must differ")

        if args.command == "preflight-source":
            candidate = wait_for_source_candidate(
                api,
                args.repository,
                require_pr_number(args.workflow_run_id, "workflow run"),
                args.source_branch,
                manifest_path,
                lock_path,
                args.wait_seconds,
                verify_alerts=False,
            )
            emit_output("verified", True)
            emit_output("pull_request_number", candidate.pull_request)
            emit_output("source_base_sha", candidate.source_base)
            emit_output("source_head_sha", candidate.source_head)
            emit_output("source_tree_sha", candidate.source_tree)
        elif args.command == "merge-source":
            merge_sha = merge_source_candidate(
                api,
                args.repository,
                require_pr_number(args.workflow_run_id, "workflow run"),
                args.source_branch,
                manifest_path,
                lock_path,
                require_pr_number(args.pull_request),
                require_sha(args.expected_head_sha, "expected source head"),
                require_sha(args.expected_base_sha, "expected source base"),
            )
            emit_output("merged", True)
            emit_output("source_merge_sha", merge_sha)
        elif args.command == "verify-source":
            evidence = build_source_evidence(
                api,
                args.repository,
                args.source_merge_sha,
                args.source_branch,
                manifest_path,
                lock_path,
            )
            emit_output("eligible", True)
            emit_output("pull_request_number", evidence.pull_request)
            emit_output("source_head_sha", evidence.source_head)
            emit_output("ghsa_set", ",".join(evidence.ghsa_set))
        elif args.command == "project":
            source = build_source_evidence(
                api,
                args.repository,
                args.source_merge_sha,
                args.source_branch,
                manifest_path,
                lock_path,
            )
            pull_request, evidence = create_projection(
                api,
                source,
                args.target_branch,
                manifest_path,
                lock_path,
                args.draft == "true",
            )
            emit_output("eligible", True)
            emit_output("pull_request_number", pull_request)
            emit_output("projection_head_sha", evidence.projection_head)
            emit_output("production_base_sha", evidence.production_base)
        elif args.command == "verify-projection":
            pull_request = require_pr_number(args.pull_request)
            evidence, pr = verify_projection(
                api,
                args.repository,
                pull_request,
                args.source_branch,
                args.target_branch,
                args.require_ready == "true",
            )
            if args.verify_checks == "true":
                verify_checks(
                    api,
                    evidence.repository,
                    pull_request,
                    pr,
                    evidence,
                    args.ci_workflow_path,
                    args.ci_check_name,
                    require_app_id(args.ci_app_id, "CI App"),
                    args.codeql_check_name,
                    require_app_id(args.codeql_app_id, "CodeQL App"),
                )
            emit_output("verified", True)
            emit_output("projection_head_sha", evidence.projection_head)
            emit_output("production_base_sha", evidence.production_base)
            emit_output("projection_tree_sha", evidence.projection_tree)
        elif args.command == "verify-ci-admission":
            evidence = verify_projection_admission(
                api,
                args.repository,
                require_pr_number(args.pull_request),
                args.target_branch,
            )
            emit_output("verified", True)
            emit_output("projection_head_sha", evidence.projection_head)
        elif args.command == "verify-post-merge":
            verify_post_merge(
                api,
                require_repository(args.repository),
                args.target_branch,
                args.merge_sha,
                require_sha(args.production_base, "production base"),
                require_sha(args.projection_head, "projection head"),
                require_sha(args.projection_tree, "projection tree"),
            )
            emit_output("verified", True)
        return 0
    except PolicyError as error:
        print(f"✗ {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
