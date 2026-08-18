#!/usr/bin/env python3
"""Require recognized commercial-license evidence for dependency changes."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
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
NPM_REGISTRY_ORIGIN = "https://registry.npmjs.org"
NPM_REGISTRY_RESPONSE_LIMIT = 2 * 1024 * 1024
GITHUB_SHA = re.compile(r"^[0-9a-f]{40}$")
NPM_NAME = r"(?:@[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*|[a-z0-9][a-z0-9._-]*)"
NPM_PRERELEASE_IDENTIFIER = (
    r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
)
NPM_VERSION = (
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    rf"(?:-{NPM_PRERELEASE_IDENTIFIER}(?:\.{NPM_PRERELEASE_IDENTIFIER})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
NPM_ALIAS_SPEC = re.compile(rf"^npm:({NPM_NAME})@({NPM_VERSION})$")
NPM_PACKAGE_NAME = re.compile(rf"^{NPM_NAME}$")
MAX_NPM_JSON_BYTES = 20 * 1024 * 1024
NPM_DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


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


@dataclass(frozen=True)
class NpmAliasIdentity:
    alias: str
    target: str
    version: str
    spec: str
    package_url: str


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


def npm_purl(name: str, version: str | None = None) -> str:
    encoded = f"%40{name[1:]}" if name.startswith("@") else name
    return f"pkg:npm/{encoded}" + (f"@{version}" if version is not None else "")


def parse_npm_alias_identity(change: dict[str, Any]) -> NpmAliasIdentity | None:
    if change.get("ecosystem") != "npm" or change.get("manifest") != "package.json":
        return None
    spec = change.get("version")
    if not isinstance(spec, str) or not spec.startswith("npm:"):
        return None

    required_fields = {
        "change_type",
        "ecosystem",
        "manifest",
        "name",
        "version",
        "package_url",
        "license",
        "source_repository_url",
        "scope",
        "vulnerabilities",
    }
    missing_fields = sorted(required_fields - change.keys())
    if missing_fields:
        raise EvidenceError(
            "npm alias dependency record is missing fields: " + ", ".join(missing_fields) + "."
        )
    if change.get("change_type") != "added" or change.get("license") is not None:
        raise EvidenceError("npm alias fallback requires one added null-license record.")
    if change.get("scope") not in {"development", "runtime", "unknown"}:
        raise EvidenceError("npm alias dependency record has an invalid scope.")
    if not isinstance(change.get("vulnerabilities"), list):
        raise EvidenceError("npm alias dependency record has invalid vulnerability evidence.")

    match = NPM_ALIAS_SPEC.fullmatch(spec)
    if match is None:
        raise EvidenceError(f"npm alias spec is not an exact registry version: {spec!r}.")
    alias = change.get("name")
    if not isinstance(alias, str) or NPM_PACKAGE_NAME.fullmatch(alias) is None:
        raise EvidenceError(f"npm alias has an invalid package name: {alias!r}.")
    package_url = change.get("package_url")
    if package_url != npm_purl(alias):
        raise EvidenceError(
            f"npm alias {alias!r} has inconsistent package URL {package_url!r}."
        )
    if change.get("source_repository_url") is not None:
        raise EvidenceError(f"npm alias {package_url} unexpectedly reports a source repository.")
    target, version = match.groups()
    if target == alias:
        raise EvidenceError(f"npm alias {package_url} does not name a different target package.")
    return NpmAliasIdentity(alias, target, version, spec, package_url)


def load_json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise EvidenceError(f"{label} is unavailable ({type(error).__name__}).") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_NPM_JSON_BYTES:
        raise EvidenceError(f"{label} must be one bounded regular file.")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_json_keys
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{label} is not valid UTF-8 JSON ({type(error).__name__}).") from error
    if not isinstance(payload, dict):
        raise EvidenceError(f"{label} must contain one JSON object.")
    return payload


def dependency_section(payload: dict[str, Any], alias: str, spec: str, label: str) -> str:
    matches = [
        section
        for section in NPM_DEPENDENCY_SECTIONS
        if isinstance(payload.get(section), dict) and payload[section].get(alias) == spec
    ]
    if len(matches) != 1:
        raise EvidenceError(f"{label} does not bind npm alias {alias!r} to {spec!r} exactly once.")
    return matches[0]


def npm_registry_tarball(name: str, version: str) -> str:
    basename = name.split("/", 1)[-1]
    return f"https://registry.npmjs.org/{name}/-/{basename}-{version}.tgz"


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"JSON evidence contains duplicate key {key!r}.")
        result[key] = value
    return result


def is_sha512_integrity(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("sha512-"):
        return False
    try:
        digest = base64.b64decode(value.removeprefix("sha512-"), validate=True)
    except (binascii.Error, ValueError):
        return False
    return len(digest) == 64


def npm_lock_packages(payload: dict[str, Any], label: str) -> dict[str, Any]:
    if payload.get("lockfileVersion") != 3:
        raise EvidenceError(f"{label} must use npm lockfileVersion 3.")
    packages = payload.get("packages")
    if not isinstance(packages, dict) or not isinstance(packages.get(""), dict):
        raise EvidenceError(f"{label} has no npm packages/root descriptor.")
    return packages


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Keep npm evidence requests on their internally constructed endpoints."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def npm_registry_endpoint(name: str, version: str) -> str:
    encoded_name = urllib.parse.quote(name, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    return f"{NPM_REGISTRY_ORIGIN}/{encoded_name}/{encoded_version}"


def fetch_npm_registry_release(identity: NpmAliasIdentity) -> dict[str, Any]:
    endpoint = npm_registry_endpoint(identity.target, identity.version)
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "User-Agent": "ForgingAlpha-license-evidence",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirects())
    try:
        with opener.open(request, timeout=LICENSE_LOOKUP_TIMEOUT_SECONDS) as response:
            if response.geturl() != endpoint:
                raise EvidenceError(
                    f"npm registry evidence redirected for {identity.package_url}."
                )
            if response.getcode() != 200:
                raise EvidenceError(
                    f"npm registry evidence returned non-200 status for {identity.package_url}."
                )
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    parsed_length = int(content_length)
                except ValueError as error:
                    raise EvidenceError(
                        f"npm registry evidence has invalid length for {identity.package_url}."
                    ) from error
                if parsed_length < 0 or parsed_length > NPM_REGISTRY_RESPONSE_LIMIT:
                    raise EvidenceError(
                        f"npm registry evidence is oversized for {identity.package_url}."
                    )
            raw = response.read(NPM_REGISTRY_RESPONSE_LIMIT + 1)
    except EvidenceError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError) as error:
        raise EvidenceError(
            f"npm registry evidence lookup failed for {identity.package_url} "
            f"({type(error).__name__})."
        ) from error

    if len(raw) > NPM_REGISTRY_RESPONSE_LIMIT:
        raise EvidenceError(f"npm registry evidence is oversized for {identity.package_url}.")
    try:
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_json_keys
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(
            f"npm registry evidence is not valid UTF-8 JSON for {identity.package_url}."
        ) from error
    if not isinstance(payload, dict):
        raise EvidenceError(f"npm registry evidence is not an object for {identity.package_url}.")
    return payload


def concrete_npm_licenses(
    changes: list[dict[str, Any]], expected_purls: set[str]
) -> dict[str, str]:
    records: dict[str, list[str]] = {}
    for change in changes:
        package_url = change.get("package_url")
        if package_url not in expected_purls:
            continue
        if change.get("change_type") != "added" or change.get("ecosystem") != "npm":
            raise EvidenceError(f"Concrete npm evidence is malformed for {package_url}.")
        license_value = change.get("license")
        if not isinstance(license_value, str) or not license_value.strip():
            raise EvidenceError(f"Concrete npm evidence has no license for {package_url}.")
        name = change.get("name")
        version = change.get("version")
        if (
            isinstance(name, str)
            and NPM_PACKAGE_NAME.fullmatch(name) is not None
            and isinstance(version, str)
            and re.fullmatch(NPM_VERSION, version) is not None
            and package_url == npm_purl(name, version)
            and package_url in expected_purls
        ):
            records.setdefault(package_url, []).append(license_value)
        else:
            raise EvidenceError(f"Concrete npm evidence has inconsistent identity for {package_url}.")
    duplicates = sorted(package_url for package_url, values in records.items() if len(values) != 1)
    if duplicates:
        raise EvidenceError(
            "Concrete npm license evidence is ambiguous: " + ", ".join(duplicates) + "."
        )
    return {package_url: values[0] for package_url, values in records.items()}


def verify_npm_aliases(
    identities: dict[str, NpmAliasIdentity], changes: list[dict[str, Any]]
) -> None:
    workspace_value = os.environ.get("DEPENDENCY_WORKSPACE", "")
    if not workspace_value:
        raise EvidenceError("npm alias resolution requires the checked-out dependency workspace.")
    workspace = Path(workspace_value)
    if not workspace.is_absolute():
        raise EvidenceError("dependency workspace must be an absolute path.")

    manifest = load_json_file(workspace / "package.json", "package.json")
    lock = load_json_file(workspace / "package-lock.json", "package-lock.json")
    lock_packages = npm_lock_packages(lock, "package-lock.json")
    lock_root = lock_packages[""]
    target_purls = {
        npm_purl(identity.target, identity.version)
        for identity in identities.values()
    }
    concrete_licenses = concrete_npm_licenses(changes, target_purls)
    registry_targets = target_purls - concrete_licenses.keys()
    if len(registry_targets) > LICENSE_LOOKUP_LIMIT:
        raise EvidenceError(
            f"npm alias license lookup count {len(registry_targets)} exceeds limit "
            f"{LICENSE_LOOKUP_LIMIT}."
        )
    registry_payloads: dict[str, dict[str, Any]] = {}

    for identity in identities.values():
        manifest_section = dependency_section(
            manifest, identity.alias, identity.spec, "package.json"
        )
        lock_section = dependency_section(
            lock_root, identity.alias, identity.spec, "package-lock.json root"
        )
        if lock_section != manifest_section:
            raise EvidenceError(
                f"npm alias {identity.package_url} changes dependency section in the lockfile."
            )

        location = f"node_modules/{identity.alias}"
        descriptor = lock_packages.get(location)
        if not isinstance(descriptor, dict) or descriptor.get("link") not in {None, False}:
            raise EvidenceError(
                f"npm alias {identity.package_url} lacks one non-link locked target."
            )
        expected = {
            "name": identity.target,
            "version": identity.version,
            "resolved": npm_registry_tarball(identity.target, identity.version),
        }
        for field, value in expected.items():
            if descriptor.get(field) != value:
                raise EvidenceError(
                    f"npm alias {identity.package_url} locked target has inconsistent {field}."
                )
        integrity = descriptor.get("integrity")
        if not is_sha512_integrity(integrity):
            raise EvidenceError(
                f"npm alias {identity.package_url} locked target lacks exact sha512 integrity."
            )
        license_value = descriptor.get("license")
        if license_value not in APPROVED_SPDX:
            raise EvidenceError(
                f"npm alias {identity.package_url} locked target has non-approved license "
                f"{license_value!r}."
            )
        target_purl = npm_purl(identity.target, identity.version)
        concrete_license = concrete_licenses.get(target_purl)
        if concrete_license is not None:
            if concrete_license != license_value or concrete_license not in APPROVED_SPDX:
                raise EvidenceError(
                    f"npm alias {identity.package_url} concrete license evidence does not "
                    "match its locked approved license."
                )
            print(
                f"✓ Resolved {license_value} license evidence for {identity.package_url} "
                f"from concrete dependency evidence {target_purl}."
            )
            continue

        payload = registry_payloads.get(target_purl)
        if payload is None:
            payload = fetch_npm_registry_release(identity)
            registry_payloads[target_purl] = payload
        dist = payload.get("dist")
        if not isinstance(dist, dict):
            raise EvidenceError(
                f"npm registry evidence has no distribution for {identity.package_url}."
            )
        expected_registry = {
            "name": identity.target,
            "version": identity.version,
            "license": license_value,
        }
        for field, value in expected_registry.items():
            if payload.get(field) != value:
                raise EvidenceError(
                    f"npm registry evidence has inconsistent {field} for "
                    f"{identity.package_url}."
                )
        if dist.get("tarball") != descriptor["resolved"]:
            raise EvidenceError(
                f"npm registry tarball does not match the lock for {identity.package_url}."
            )
        if dist.get("integrity") != integrity:
            raise EvidenceError(
                f"npm registry integrity does not match the lock for {identity.package_url}."
            )
        print(
            f"✓ Resolved {license_value} license evidence for {identity.package_url} "
            f"from exact npm registry release {target_purl}."
        )


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
        changes = json.loads(raw, object_pairs_hook=reject_duplicate_json_keys)
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
    npm_aliases: dict[str, NpmAliasIdentity] = {}

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

        npm_alias = parse_npm_alias_identity(change)
        if npm_alias is not None:
            if npm_alias.alias in npm_aliases:
                raise EvidenceError(
                    f"npm alias {npm_alias.package_url} appears more than once in dependency changes."
                )
            npm_aliases[npm_alias.alias] = npm_alias
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
        if npm_aliases:
            verify_npm_aliases(npm_aliases, changes)
        return

    token = os.environ.get("GITHUB_LICENSE_TOKEN", "")
    if not token:
        raise EvidenceError("GitHub Action license resolution requires the read-only GitHub token.")

    for identity in identities.values():
        spdx_id = fetch_github_license(identity, token)
        print(f"✓ Resolved {spdx_id} license evidence for {identity.package_url}.")
    if first_party_identities:
        verify_first_party_actions(first_party_identities, token)
    if npm_aliases:
        verify_npm_aliases(npm_aliases, changes)


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
