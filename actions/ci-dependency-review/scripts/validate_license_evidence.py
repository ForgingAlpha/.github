#!/usr/bin/env python3
"""Fail when introduced dependency records do not contain license evidence."""

from __future__ import annotations

import json
import os
import sys


def fail(what: str, why: str, how: str) -> int:
    print("✗ Dependency license evidence validation failed.", file=sys.stderr)
    print(f"  WHAT: {what}", file=sys.stderr)
    print(f"  WHY: {why}", file=sys.stderr)
    print(f"  HOW: {how}", file=sys.stderr)
    return 1


def main() -> int:
    raw = os.environ.get("DEPENDENCY_CHANGES", "")
    if not raw.strip():
        return fail(
            "The official dependency-review action returned no dependency-changes JSON.",
            "Unknown license data cannot be distinguished from missing review evidence.",
            "Inspect the preceding Dependency Review step and restore a valid dependency-review output.",
        )

    try:
        changes = json.loads(raw)
    except json.JSONDecodeError as error:
        return fail(
            f"dependency-changes was not valid JSON ({error}).",
            "The commercial-license gate must evaluate machine-readable evidence.",
            "Inspect the official action output and rerun the pull-request CI job.",
        )

    if not isinstance(changes, list):
        return fail(
            "dependency-changes was not a JSON array.",
            "The commercial-license gate expects the official dependency change schema.",
            "Inspect the official action output and update the pinned integration if its schema changed.",
        )

    missing = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            return fail(
                f"dependency-changes entry {index} was not a JSON object.",
                "Malformed records cannot provide trustworthy license evidence.",
                "Inspect the pinned official action output and update this validator for any reviewed schema change.",
            )
        change_type = change.get("change_type")
        if change_type not in {"added", "removed"}:
            return fail(
                f"dependency-changes entry {index} had unsupported change_type {change_type!r}.",
                "The pinned dependency-review schema must not change silently.",
                "Inspect the official action output and update the pin, schema validation, and tests together.",
            )
        if change_type == "removed":
            continue
        license_value = change.get("license")
        if not isinstance(license_value, str) or not license_value.strip():
            missing.append(change.get("package_url") or change.get("name") or "<unknown package>")

    if missing:
        packages = ", ".join(sorted(set(str(package) for package in missing)))
        return fail(
            f"Introduced or updated dependencies lack license evidence: {packages}.",
            "Packages without recognized license evidence cannot be approved for commercial SaaS use.",
            "Choose a dependency with approved SPDX evidence or add centrally reviewed license evidence before merge.",
        )

    print("✓ Every introduced or updated dependency has recognized license evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
