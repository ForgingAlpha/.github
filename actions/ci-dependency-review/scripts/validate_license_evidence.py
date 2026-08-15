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
GITHUB_API_VERSION = "2026-03-10"
LICENSE_LOOKUP_LIMIT = 20
LICENSE_LOOKUP_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class GitHubActionIdentity:
    owner: str
    repository: str
    sha: str
    package_url: str

    @property
    def cache_key(self) -> tuple[str, str, str]:
        return (self.owner.lower(), self.repository.lower(), self.sha)


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


def fetch_github_license(identity: GitHubActionIdentity, token: str) -> str:
    owner = urllib.parse.quote(identity.owner, safe="")
    repository = urllib.parse.quote(identity.repository, safe="")
    sha = urllib.parse.quote(identity.sha, safe="")
    endpoint = f"https://api.github.com/repos/{owner}/{repository}/license?ref={sha}"
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
            payload = json.load(response)
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise EvidenceError(
            f"GitHub license lookup failed for {identity.package_url} ({type(error).__name__})."
        ) from error

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
    if not identities:
        return

    token = os.environ.get("GITHUB_LICENSE_TOKEN", "")
    if not token:
        raise EvidenceError("GitHub Action license resolution requires the read-only GitHub token.")

    for identity in identities.values():
        spdx_id = fetch_github_license(identity, token)
        print(f"✓ Resolved {spdx_id} license evidence for {identity.package_url}.")


def main() -> int:
    try:
        validate_changes(load_changes())
    except EvidenceError as error:
        return fail(
            str(error),
            "Packages without approved, revision-bound license evidence cannot be used for commercial SaaS.",
            "Choose a dependency with approved SPDX evidence or correct its immutable upstream license evidence.",
        )

    print("✓ Every introduced or updated dependency has approved license evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
