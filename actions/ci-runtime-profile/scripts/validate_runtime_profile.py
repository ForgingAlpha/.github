#!/usr/bin/env python3
"""Validate a consumer mise projection against the central runtime catalog."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
PROFILE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9.]+)*")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
ALLOWED_ASSIGNMENT_STATUSES = {"active", "planned"}
ALLOWED_TUPLE_STATES = {"current", "rollout"}


class ProfileError(ValueError):
    """Raised when a catalog or consumer projection violates the contract."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError(f"could not read valid JSON from {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ProfileError(f"{path} must contain a JSON object")
    return payload


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ProfileError(f"could not read valid TOML from {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ProfileError(f"{path} must contain a TOML table")
    return payload


def require_object(value: Any, subject: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError(f"{subject} must be an object")
    return value


def require_nonempty_string(value: Any, subject: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{subject} must be a nonempty string")
    return value


def validate_catalog(catalog: dict[str, Any]) -> None:
    if set(catalog) != {"schema_version", "profiles", "assignments"}:
        raise ProfileError("catalog must contain exactly schema_version, profiles, and assignments")
    if catalog["schema_version"] != 1:
        raise ProfileError("catalog schema_version must be 1")

    profiles = require_object(catalog["profiles"], "profiles")
    assignments = require_object(catalog["assignments"], "assignments")
    if not profiles:
        raise ProfileError("catalog must define at least one profile")
    if not assignments:
        raise ProfileError("catalog must define at least one repository assignment")

    for profile_id, raw_profile in profiles.items():
        if not isinstance(profile_id, str) or not PROFILE_ID_RE.fullmatch(profile_id):
            raise ProfileError(f"invalid profile id {profile_id!r}")
        profile = require_object(raw_profile, f"profile {profile_id}")
        if set(profile) != {"description", "approved_tuples"}:
            raise ProfileError(f"profile {profile_id} must contain exactly description and approved_tuples")
        require_nonempty_string(profile["description"], f"profile {profile_id} description")
        tuples = profile["approved_tuples"]
        if not isinstance(tuples, list) or not tuples:
            raise ProfileError(f"profile {profile_id} must contain approved tuples")
        current_count = 0
        tuple_ids: set[str] = set()
        for index, raw_tuple in enumerate(tuples):
            runtime_tuple = require_object(raw_tuple, f"profile {profile_id} tuple {index}")
            if set(runtime_tuple) != {"id", "state", "tools"}:
                raise ProfileError(
                    f"profile {profile_id} tuple {index} must contain exactly id, state, and tools"
                )
            tuple_id = require_nonempty_string(runtime_tuple["id"], f"profile {profile_id} tuple id")
            if tuple_id in tuple_ids:
                raise ProfileError(f"profile {profile_id} repeats tuple id {tuple_id}")
            tuple_ids.add(tuple_id)
            state = runtime_tuple["state"]
            if state not in ALLOWED_TUPLE_STATES:
                raise ProfileError(f"profile {profile_id} tuple {tuple_id} has invalid state {state!r}")
            current_count += state == "current"
            tools = require_object(runtime_tuple["tools"], f"profile {profile_id} tuple {tuple_id} tools")
            if not tools:
                raise ProfileError(f"profile {profile_id} tuple {tuple_id} must define tools")
            for tool, raw_tool in tools.items():
                require_nonempty_string(tool, f"profile {profile_id} tool name")
                tool_spec = require_object(raw_tool, f"profile {profile_id} tool {tool}")
                if set(tool_spec) != {"version", "required_platforms"}:
                    raise ProfileError(
                        f"profile {profile_id} tool {tool} must contain exactly version and required_platforms"
                    )
                require_nonempty_string(tool_spec["version"], f"profile {profile_id} tool {tool} version")
                platforms = tool_spec["required_platforms"]
                if not isinstance(platforms, list):
                    raise ProfileError(f"profile {profile_id} tool {tool} required_platforms must be a list")
                if len(platforms) != len(set(platforms)):
                    raise ProfileError(f"profile {profile_id} tool {tool} repeats a required platform")
                for platform in platforms:
                    require_nonempty_string(platform, f"profile {profile_id} tool {tool} required platform")
        if current_count != 1:
            raise ProfileError(f"profile {profile_id} must have exactly one current tuple")

    active_profiles: set[str] = set()
    for repository, raw_assignment in assignments.items():
        if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
            raise ProfileError(f"invalid repository assignment {repository!r}")
        assignment = require_object(raw_assignment, f"assignment {repository}")
        if set(assignment) != {"profile", "status"}:
            raise ProfileError(f"assignment {repository} must contain exactly profile and status")
        profile_id = require_nonempty_string(assignment["profile"], f"assignment {repository} profile")
        if profile_id not in profiles:
            raise ProfileError(f"assignment {repository} references unknown profile {profile_id}")
        status = assignment["status"]
        if status not in ALLOWED_ASSIGNMENT_STATUSES:
            raise ProfileError(f"assignment {repository} has invalid status {status!r}")
        if status == "active":
            active_profiles.add(profile_id)
    unused = set(profiles) - active_profiles
    if unused:
        raise ProfileError(f"profiles without an active assignment are not authoritative: {', '.join(sorted(unused))}")


def current_tuple(catalog: dict[str, Any], repository: str) -> dict[str, Any]:
    assignments = catalog["assignments"]
    assignment = assignments.get(repository)
    if not isinstance(assignment, dict):
        raise ProfileError(f"repository {repository} has no runtime profile assignment")
    if assignment["status"] != "active":
        raise ProfileError(f"repository {repository} runtime profile assignment is not active")
    profile = catalog["profiles"][assignment["profile"]]
    return next(item for item in profile["approved_tuples"] if item["state"] == "current")


def validate_policy_assignment(catalog: dict[str, Any], repository: str, policy: dict[str, Any]) -> None:
    assignment = catalog["assignments"].get(repository)
    if not isinstance(assignment, dict) or assignment.get("status") != "active":
        raise ProfileError(f"repository {repository} has no active runtime profile assignment")
    if policy.get("schema_version") != 1:
        raise ProfileError("update policy schema_version must be 1")
    if policy.get("runtime_profile") != assignment["profile"]:
        raise ProfileError(
            f"update policy runtime_profile {policy.get('runtime_profile')!r} does not equal assigned profile {assignment['profile']!r}"
        )


def validate_projection(
    catalog: dict[str, Any], repository: str, mise_toml: dict[str, Any], mise_lock: dict[str, Any]
) -> str:
    runtime_tuple = current_tuple(catalog, repository)
    tool_specs = runtime_tuple["tools"]
    expected_tools = {tool: spec["version"] for tool, spec in tool_specs.items()}
    actual_tools = mise_toml.get("tools")
    if actual_tools != expected_tools:
        raise ProfileError(
            f"{repository} mise.toml tools {actual_tools!r} do not equal assigned tuple {expected_tools!r}"
        )

    locked_tools = mise_lock.get("tools")
    if not isinstance(locked_tools, dict):
        raise ProfileError("mise.lock must contain a tools table")
    if set(locked_tools) != set(expected_tools):
        raise ProfileError("mise.lock tool set must exactly match the assigned runtime tuple")

    for tool, version in expected_tools.items():
        entries = locked_tools[tool]
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list) or not entries or not all(isinstance(entry, dict) for entry in entries):
            raise ProfileError(f"mise.lock must contain one or more valid entries for {tool}")
        platforms: dict[str, Any] = {}
        for entry in entries:
            if entry.get("version") != version:
                raise ProfileError(f"mise.lock {tool} version does not equal assigned version {version}")
            nested_platforms = entry.get("platforms")
            if isinstance(nested_platforms, dict):
                for platform, artifact in nested_platforms.items():
                    if platform in platforms:
                        raise ProfileError(f"mise.lock {tool}@{version} repeats platform {platform}")
                    platforms[platform] = artifact
            for key, value in entry.items():
                if isinstance(key, str) and key.startswith("platforms."):
                    platform = key.removeprefix("platforms.")
                    if not platform or platform in platforms:
                        raise ProfileError(f"mise.lock {tool}@{version} has an ambiguous platform table {key}")
                    platforms[platform] = value
        required_platforms = set(tool_specs[tool]["required_platforms"])
        missing = required_platforms - set(platforms)
        if missing:
            raise ProfileError(f"mise.lock {tool}@{version} is missing platforms: {', '.join(sorted(missing))}")
        for platform, raw_artifact in platforms.items():
            artifact = require_object(raw_artifact, f"mise.lock {tool}@{version} {platform}")
            url = require_nonempty_string(artifact.get("url"), f"mise.lock {tool}@{version} {platform} URL")
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ProfileError(f"mise.lock {tool}@{version} {platform} must use a credential-free HTTPS URL")
            checksum = artifact.get("checksum")
            if not isinstance(checksum, str) or not SHA256_RE.fullmatch(checksum):
                raise ProfileError(f"mise.lock {tool}@{version} {platform} lacks an exact SHA-256 checksum")
    return runtime_tuple["id"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--repository")
    parser.add_argument("--mise-toml", type=Path)
    parser.add_argument("--mise-lock", type=Path)
    parser.add_argument("--update-policy", type=Path)
    parser.add_argument("--catalog-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = load_json(args.catalog)
        validate_catalog(catalog)
        if args.catalog_only:
            print("✓ Runtime profile catalog validation passed")
            return 0
        if not args.repository or not args.mise_toml or not args.mise_lock or not args.update_policy:
            raise ProfileError("repository, update-policy, mise-toml, and mise-lock are required for projection validation")
        validate_policy_assignment(catalog, args.repository, load_json(args.update_policy))
        tuple_id = validate_projection(
            catalog,
            args.repository,
            load_toml(args.mise_toml),
            load_toml(args.mise_lock),
        )
        print(f"✓ Runtime profile projection validation passed ({args.repository}: {tuple_id})")
        return 0
    except ProfileError as error:
        print("✗ Runtime profile validation failed", file=sys.stderr)
        print(f"  WHAT: {error}", file=sys.stderr)
        print("  WHY: consumer runtime files must be an exact integrity-bearing projection of central policy.", file=sys.stderr)
        print("  HOW: regenerate mise.toml and mise.lock from the assigned current runtime tuple.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
