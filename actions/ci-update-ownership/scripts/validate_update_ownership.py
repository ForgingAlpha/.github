#!/usr/bin/env python3
"""Validate a consumer's sole normal-update owner during the Renovate cutover."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

CENTRAL_PRESET = "local>ForgingAlpha/.github:renovate-config"
ALLOWED_POLICY_KEYS = {"schema_version", "normal_update_owner", "base_branch", "runtime_profile"}
ALLOWED_RENOVATE_KEYS = {"$schema", "extends", "baseBranchPatterns"}
ALTERNATE_RENOVATE_CONFIGS = (
    "renovate.jsonc",
    "renovate.json5",
    ".github/renovate.json",
    ".github/renovate.jsonc",
    ".github/renovate.json5",
    ".gitlab/renovate.json",
    ".gitlab/renovate.jsonc",
    ".gitlab/renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".renovaterc.jsonc",
    ".renovaterc.json5",
)


class OwnershipError(ValueError):
    """Raised when update ownership is missing, overlapping, or unsafe."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OwnershipError(f"could not read valid JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise OwnershipError(f"{path} must contain a JSON object")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise OwnershipError(f"could not read valid YAML from {path}: {error}") from error
    if not isinstance(value, dict):
        raise OwnershipError(f"{path} must contain a YAML object")
    return value


def validate_policy(policy: dict[str, Any]) -> tuple[str, str, str]:
    if set(policy) != ALLOWED_POLICY_KEYS:
        raise OwnershipError("update policy must contain exactly schema_version, normal_update_owner, base_branch, and runtime_profile")
    if policy["schema_version"] != 1:
        raise OwnershipError("update policy schema_version must be 1")
    owner = policy["normal_update_owner"]
    if owner not in {"dependabot", "renovate"}:
        raise OwnershipError("normal_update_owner must be dependabot or renovate")
    base = policy["base_branch"]
    if not isinstance(base, str) or not base or base.startswith("refs/") or "/" in base:
        raise OwnershipError("base_branch must be a simple branch name")
    profile = policy["runtime_profile"]
    if not isinstance(profile, str) or not profile:
        raise OwnershipError("runtime_profile must name the centrally assigned profile")
    return owner, base, profile


def validate_renovate(config: dict[str, Any], base: str) -> None:
    unexpected = set(config) - ALLOWED_RENOVATE_KEYS
    if unexpected:
        raise OwnershipError(f"repository Renovate config contains forbidden policy overrides: {', '.join(sorted(unexpected))}")
    if config.get("extends") != [CENTRAL_PRESET]:
        raise OwnershipError(f"repository Renovate config must extend only {CENTRAL_PRESET}")
    if config.get("baseBranchPatterns") != [base]:
        raise OwnershipError(f"repository Renovate baseBranchPatterns must be exactly [{base!r}]")


def validate_config_files(repository_root: Path, canonical_path: Path) -> None:
    root = repository_root.resolve()
    canonical = canonical_path if canonical_path.is_absolute() else root / canonical_path
    if not os.path.lexists(canonical) or not canonical.is_file() or canonical.is_symlink():
        raise OwnershipError("canonical renovate.json must be one regular file at the repository root")
    alternates = [relative for relative in ALTERNATE_RENOVATE_CONFIGS if os.path.lexists(root / relative)]
    if alternates:
        raise OwnershipError(
            "alternate Renovate config files are forbidden because Renovate uses only the first match: "
            + ", ".join(alternates)
        )
    package_json = root / "package.json"
    if os.path.lexists(package_json):
        package = load_json(package_json)
        if "renovate" in package:
            raise OwnershipError("deprecated package.json renovate configuration is forbidden")


def validate_security_only_dependabot(config: dict[str, Any], base: str) -> None:
    if config.get("version") != 2:
        raise OwnershipError("Dependabot config version must be 2")
    updates = config.get("updates")
    if not isinstance(updates, list) or not updates:
        raise OwnershipError("security-only Dependabot config must retain update blocks for alert remediation")
    identities: set[tuple[str, tuple[str, ...]]] = set()
    for index, raw_update in enumerate(updates):
        if not isinstance(raw_update, dict):
            raise OwnershipError(f"Dependabot update block {index} must be an object")
        ecosystem = raw_update.get("package-ecosystem")
        if not isinstance(ecosystem, str) or not ecosystem:
            raise OwnershipError(f"Dependabot update block {index} has no package ecosystem")
        directories = raw_update.get("directories")
        directory = raw_update.get("directory")
        if directories is None and isinstance(directory, str):
            directories = [directory]
        if not isinstance(directories, list) or not directories or not all(isinstance(item, str) and item for item in directories):
            raise OwnershipError(f"Dependabot update block {ecosystem} must name one or more directories")
        identity = (ecosystem, tuple(directories))
        if identity in identities:
            raise OwnershipError(f"Dependabot repeats update block {ecosystem} {directories}")
        identities.add(identity)
        if raw_update.get("open-pull-requests-limit") != 0:
            raise OwnershipError(f"Dependabot {ecosystem} normal version updates must have open-pull-requests-limit: 0")
        if raw_update.get("target-branch") != base:
            raise OwnershipError(f"Dependabot {ecosystem} target branch must be {base}")


def validate_central_preset(config: dict[str, Any]) -> None:
    if config.get("internalChecksFilter") != "strict":
        raise OwnershipError("central Renovate preset must use strict internal checks")
    if config.get("vulnerabilityAlerts") != {"enabled": False} or config.get("osvVulnerabilityAlerts") is not False:
        raise OwnershipError("central Renovate preset must disable vulnerability remediation")
    if config.get("lockFileMaintenance") != {"enabled": False}:
        raise OwnershipError("central Renovate preset must disable generic lock maintenance")
    rules = config.get("packageRules")
    if not isinstance(rules, list):
        raise OwnershipError("central Renovate preset must define package rules")
    mise_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("matchManagers") == ["mise"]]
    if len(mise_rules) != 1 or mise_rules[0].get("enabled") is not False:
        raise OwnershipError("central Renovate preset must disable direct mise projection updates")
    expected = {"patch": "3 days", "minor": "7 days", "major": "30 days"}
    observed: dict[str, str] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        update_types = rule.get("matchUpdateTypes")
        if not isinstance(update_types, list) or len(update_types) != 1 or update_types[0] not in expected:
            continue
        update_type = update_types[0]
        observed[update_type] = rule.get("minimumReleaseAge")
        if rule.get("automerge") is not True or rule.get("automergeType") != "pr" or rule.get("platformAutomerge") is not True:
            raise OwnershipError(f"central {update_type} rule must use protected pull-request automerge")
    if observed != expected:
        raise OwnershipError(f"central cooldown rules must be exactly {expected}, found {observed}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--renovate", type=Path)
    parser.add_argument("--dependabot", type=Path)
    parser.add_argument("--central-preset", type=Path)
    parser.add_argument("--repository-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.central_preset:
            validate_central_preset(load_json(args.central_preset))
            print("✓ Central Renovate preset validation passed")
            return 0
        if not args.policy or not args.renovate or not args.dependabot or not args.repository_root:
            raise OwnershipError("repository-root, policy, renovate, and dependabot paths are required for consumer validation")
        owner, base, _profile = validate_policy(load_json(args.policy))
        if owner != "renovate":
            raise OwnershipError("ci-update-ownership is the destination Renovate-mode gate")
        validate_config_files(args.repository_root, args.renovate)
        validate_renovate(load_json(args.renovate), base)
        validate_security_only_dependabot(load_yaml(args.dependabot), base)
        print(f"✓ Update ownership validation passed (Renovate normal updates; Dependabot security only; base {base})")
        return 0
    except OwnershipError as error:
        print("✗ Update ownership validation failed", file=sys.stderr)
        print(f"  WHAT: {error}", file=sys.stderr)
        print("  WHY: every dependency surface must have one normal-update owner and a separate security lane.", file=sys.stderr)
        print("  HOW: use the central Renovate preset and retain Dependabot blocks with normal PR capacity zero.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
