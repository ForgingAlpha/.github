#!/usr/bin/env python3
"""Require recognized commercial-license evidence for dependency changes."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from license_policy import APPROVED_SPDX


GITHUB_ACTION_PURL = re.compile(
    r"^pkg:githubactions/([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9_.-]+)@([0-9a-f]{40})$"
)
FIRST_PARTY_ACTION_PURL = re.compile(
    r"^pkg:githubactions/ForgingAlpha/\.github/actions/"
    r"([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)@1\.%2A\.%2A$"
)
FIRST_PARTY_REPOSITORY = "ForgingAlpha/.github"
FIRST_PARTY_SOURCE_URL = "https://github.com/ForgingAlpha/.github"
FIRST_PARTY_VERSION = "1.*.*"
FIRST_PARTY_REF_ENDPOINT = "https://api.github.com/repos/ForgingAlpha/.github/git/ref/tags/v1"
GITHUB_API_VERSION = "2026-03-10"
LICENSE_LOOKUP_LIMIT = 20
LICENSE_LOOKUP_TIMEOUT_SECONDS = 10
GITHUB_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class GitHubActionIdentity:
    owner: str
    repository: str
    sha: str
    package_url: str

    @property
    def cache_key(self) -> tuple[str, str, str]:
        return (self.owner.lower(), self.repository.lower(), self.sha)


@dataclass(frozen=True)
class FirstPartyActionIdentity:
    action_directory: str
    package_url: str

    @property
    def action_path(self) -> str:
        return f"actions/{self.action_directory}/action.yml"


class EvidenceError(ValueError):
    """Raised when dependency evidence cannot satisfy the governed contract."""


def fail(what: str, why: str, how: str) -> int:
    print("✗ Dependency license evidence validation failed.", file=sys.stderr)
    print(f"  WHAT: {what}", file=sys.stderr)
    print(f"  WHY: {why}", file=sys.stderr)
    print(f"  HOW: {how}", file=sys.stderr)
    return 1


def parse_github_action_identity(change: dict[str, Any]) -> GitHubActionIdentity | None:
    package_url = change.get("package_url")
    if not isinstance(package_url, str) or not package_url.startswith("pkg:githubactions/"):
        return None

    match = GITHUB_ACTION_PURL.fullmatch(package_url)
    if not match:
        raise EvidenceError(
            f"GitHub Action package URL is not an exact immutable reference: {package_url!r}."
        )

    owner, repository, sha = match.groups()
    source_url = change.get("source_repository_url")
    if not isinstance(source_url, str) or not source_url:
        raise EvidenceError(f"GitHub Action {package_url} has no source repository URL.")

    try:
        parsed = urllib.parse.urlsplit(source_url)
        port = parsed.port
    except ValueError as error:
        raise EvidenceError(f"GitHub Action {package_url} has an invalid source URL ({error}).") from error

    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise EvidenceError(
            f"GitHub Action {package_url} source must be an unqualified HTTPS github.com repository URL."
        )

    if urllib.parse.unquote(parsed.path) != parsed.path:
        raise EvidenceError(f"GitHub Action {package_url} source URL must not contain encoded path data.")

    source_parts = parsed.path.split("/")
    if len(source_parts) != 3 or source_parts[0] or not all(source_parts[1:]):
        raise EvidenceError(
            f"GitHub Action {package_url} source URL must contain exactly /owner/repository."
        )

    source_owner, source_repository = source_parts[1:]
    if (source_owner.lower(), source_repository.lower()) != (owner.lower(), repository.lower()):
        raise EvidenceError(
            f"GitHub Action {package_url} does not match source repository {source_url!r}."
        )

    return GitHubActionIdentity(owner, repository, sha, package_url)


def parse_first_party_action_identity(
    change: dict[str, Any],
) -> FirstPartyActionIdentity | None:
    package_url = change.get("package_url")
    prefix = "pkg:githubactions/ForgingAlpha/.github/actions/"
    if not isinstance(package_url, str) or not package_url.startswith(prefix):
        return None

    match = FIRST_PARTY_ACTION_PURL.fullmatch(package_url)
    if not match:
        raise EvidenceError(
            f"First-party GitHub Action package URL is outside the governed v1 family: {package_url!r}."
        )

    action_directory = match.group(1)
    expected_name = f"{FIRST_PARTY_REPOSITORY}/actions/{action_directory}"
    if change.get("ecosystem") != "actions":
        raise EvidenceError(f"First-party GitHub Action {package_url} has an invalid ecosystem.")
    if change.get("name") != expected_name:
        raise EvidenceError(f"First-party GitHub Action {package_url} has an inconsistent name.")
    if change.get("version") != FIRST_PARTY_VERSION:
        raise EvidenceError(f"First-party GitHub Action {package_url} has an inconsistent version.")

    source_url = change.get("source_repository_url")
    if source_url is not None and source_url != FIRST_PARTY_SOURCE_URL:
        raise EvidenceError(f"First-party GitHub Action {package_url} has an invalid source repository URL.")

    return FirstPartyActionIdentity(action_directory, package_url)


def fetch_github_json(endpoint: str, token: str, subject: str) -> Any:
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "ForgingAlpha-license-evidence",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=LICENSE_LOOKUP_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise EvidenceError(
            f"GitHub evidence lookup failed for {subject} ({type(error).__name__})."
        ) from error


def fetch_first_party_release_tree(token: str) -> tuple[str, tuple[dict[str, Any], ...]]:
    ref_payload = fetch_github_json(FIRST_PARTY_REF_ENDPOINT, token, "the first-party v1 channel")
    if not isinstance(ref_payload, dict) or ref_payload.get("ref") != "refs/tags/v1":
        raise EvidenceError("First-party v1 lookup returned an invalid reference.")
    ref_object = ref_payload.get("object")
    if not isinstance(ref_object, dict) or ref_object.get("type") != "commit":
        raise EvidenceError("First-party v1 must be a lightweight tag pointing directly to a commit.")
    commit_sha = ref_object.get("sha")
    if not isinstance(commit_sha, str) or not GITHUB_SHA.fullmatch(commit_sha):
        raise EvidenceError("First-party v1 returned an invalid commit SHA.")

    tree_endpoint = (
        f"https://api.github.com/repos/ForgingAlpha/.github/git/trees/{commit_sha}?recursive=1"
    )
    tree_payload = fetch_github_json(tree_endpoint, token, f"first-party v1 commit {commit_sha}")
    if not isinstance(tree_payload, dict) or tree_payload.get("truncated") is not False:
        raise EvidenceError("First-party v1 tree is invalid or truncated.")
    raw_entries = tree_payload.get("tree")
    if not isinstance(raw_entries, list):
        raise EvidenceError("First-party v1 tree returned no entry list.")

    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise EvidenceError("First-party v1 tree contains a malformed entry.")
        path = entry.get("path")
        entry_type = entry.get("type")
        entry_sha = entry.get("sha")
        size = entry.get("size")
        if (
            not isinstance(path, str)
            or not path
            or entry_type not in {"blob", "tree", "commit"}
            or not isinstance(entry_sha, str)
            or not GITHUB_SHA.fullmatch(entry_sha)
            or (size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0))
        ):
            raise EvidenceError("First-party v1 tree contains a malformed entry.")
        entries.append(entry)

    return commit_sha, tuple(entries)


def verify_first_party_actions(
    identities: dict[str, FirstPartyActionIdentity], token: str
) -> str:
    commit_sha, entries = fetch_first_party_release_tree(token)
    for identity in identities.values():
        matches = [entry for entry in entries if entry["path"] == identity.action_path]
        if (
            len(matches) != 1
            or matches[0]["type"] != "blob"
            or matches[0].get("size") == 0
        ):
            raise EvidenceError(
                f"First-party v1 commit does not contain exactly one released {identity.action_path} blob."
            )
        print(
            f"✓ Verified first-party provenance for {identity.package_url} at v1 commit {commit_sha}."
        )
    return commit_sha


def fetch_github_license(identity: GitHubActionIdentity, token: str) -> str:
    owner = urllib.parse.quote(identity.owner, safe="")
    repository = urllib.parse.quote(identity.repository, safe="")
    sha = urllib.parse.quote(identity.sha, safe="")
    endpoint = f"https://api.github.com/repos/{owner}/{repository}/license?ref={sha}"
    payload = fetch_github_json(endpoint, token, identity.package_url)

    if not isinstance(payload, dict):
        raise EvidenceError(f"GitHub license lookup returned an invalid response for {identity.package_url}.")
    license_data = payload.get("license")
    if not isinstance(license_data, dict):
        raise EvidenceError(f"GitHub license lookup returned no license object for {identity.package_url}.")
    spdx_id = license_data.get("spdx_id")
    if not isinstance(spdx_id, str) or not spdx_id.strip():
        raise EvidenceError(f"GitHub license lookup returned no SPDX identifier for {identity.package_url}.")
    if spdx_id not in APPROVED_SPDX:
        raise EvidenceError(
            f"GitHub Action {identity.package_url} resolved to non-approved SPDX license {spdx_id!r}."
        )
    return spdx_id


def load_changes() -> list[dict[str, Any]]:
    raw = os.environ.get("DEPENDENCY_CHANGES", "")
    if not raw.strip():
        raise EvidenceError("The official dependency-review action returned no dependency-changes JSON.")
    try:
        changes = json.loads(raw)
    except json.JSONDecodeError as error:
        raise EvidenceError(f"dependency-changes was not valid JSON ({error}).") from error
    if not isinstance(changes, list):
        raise EvidenceError("dependency-changes was not a JSON array.")
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise EvidenceError(f"dependency-changes entry {index} was not a JSON object.")
        if change.get("change_type") not in {"added", "removed"}:
            raise EvidenceError(
                f"dependency-changes entry {index} had unsupported change_type {change.get('change_type')!r}."
            )
    return changes


def validate_changes(changes: list[dict[str, Any]]) -> None:
    missing: list[str] = []
    identities: dict[tuple[str, str, str], GitHubActionIdentity] = {}
    first_party_identities: dict[str, FirstPartyActionIdentity] = {}

    for change in changes:
        if change["change_type"] == "removed":
            continue
        license_value = change.get("license")
        if isinstance(license_value, str) and license_value.strip():
            continue
        if license_value is not None and not isinstance(license_value, str):
            raise EvidenceError(
                f"Dependency {change.get('package_url') or change.get('name') or '<unknown package>'} "
                "has malformed license evidence."
            )

        first_party_identity = parse_first_party_action_identity(change)
        if first_party_identity is not None:
            first_party_identities[first_party_identity.action_directory] = first_party_identity
            continue

        identity = parse_github_action_identity(change)
        if identity is None:
            missing.append(str(change.get("package_url") or change.get("name") or "<unknown package>"))
            continue
        identities[identity.cache_key] = identity

    if missing:
        packages = ", ".join(sorted(set(missing)))
        raise EvidenceError(f"Introduced or updated dependencies lack license evidence: {packages}.")
    if len(identities) > LICENSE_LOOKUP_LIMIT:
        raise EvidenceError(
            f"GitHub Action license lookup count {len(identities)} exceeds limit {LICENSE_LOOKUP_LIMIT}."
        )
    if not identities and not first_party_identities:
        return

    token = os.environ.get("GITHUB_LICENSE_TOKEN", "")
    if not token:
        raise EvidenceError("GitHub Action license resolution requires the read-only GitHub token.")

    for identity in identities.values():
        spdx_id = fetch_github_license(identity, token)
        print(f"✓ Resolved {spdx_id} license evidence for {identity.package_url}.")
    if first_party_identities:
        verify_first_party_actions(first_party_identities, token)


def main() -> int:
    try:
        validate_changes(load_changes())
    except EvidenceError as error:
        return fail(
            str(error),
            "Dependencies require approved third-party license evidence or governed "
            "first-party release provenance.",
            "Choose a dependency with approved SPDX evidence or correct its governed "
            "first-party release evidence.",
        )

    print("✓ Every introduced or updated dependency has approved dependency evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
