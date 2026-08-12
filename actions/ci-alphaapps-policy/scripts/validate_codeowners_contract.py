#!/usr/bin/env python3
"""Validate Alpha Apps' fail-closed repository CODEOWNERS contract."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


CODEOWNERS_PATH = Path(".github/CODEOWNERS")
MAX_CODEOWNERS_BYTES = 3_000_000
AUTHORIZED_HUMAN_OWNERS = frozenset({"@leosmigel"})
CONTROL_PLANE_REPOS = frozenset({".github", "alphaapps-docs", "control-plane"})
PRODUCTION_CONTROL_FILES = (
    "Dockerfile",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
    "firebase.json",
    "fly.toml",
    "netlify.toml",
    "render.yaml",
    "render.yml",
    "vercel.json",
    "wrangler.json",
    "wrangler.jsonc",
    "wrangler.toml",
)
PRODUCTION_CONTROL_DIRECTORIES = (
    "deploy",
    "helm",
    "infra",
    "infrastructure",
    "k8s",
    "terraform",
)


@dataclass(frozen=True)
class CodeownerEntry:
    line_number: int
    pattern: str
    owners: tuple[str, ...]


def fail(what: str, why: str, how: str, details: str | None = None) -> NoReturn:
    print(f"✗ {what}", file=sys.stderr)
    print(f"  WHAT: {what}", file=sys.stderr)
    print(f"  WHY: {why}", file=sys.stderr)
    print(f"  HOW: {how}", file=sys.stderr)
    if details:
        print(details, file=sys.stderr)
    raise SystemExit(1)


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        fail(
            "CODEOWNERS validation is not running in a Git repository",
            "the contract is defined relative to the candidate repository tree.",
            "run the validator after actions/checkout or from a repository worktree.",
            result.stderr.strip() or result.stdout.strip(),
        )
    return Path(result.stdout.strip())


def repo_name(repo: Path) -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        match = re.search(
            r"github\.com[:/]forgingalpha/([^/\s]+?)(?:\.git)?$",
            result.stdout.strip(),
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return repo.name


def read_entries(path: Path) -> list[CodeownerEntry]:
    if path.is_symlink():
        fail(
            f"{CODEOWNERS_PATH.as_posix()} is a symbolic link",
            "the protected ownership contract must be a reviewable file in the candidate tree.",
            f"replace {CODEOWNERS_PATH.as_posix()} with a regular UTF-8 file.",
        )
    if not path.is_file():
        fail(
            f"{CODEOWNERS_PATH.as_posix()} is missing",
            "a missing ownership contract silently disables required code-owner review.",
            f"add {CODEOWNERS_PATH.as_posix()} with the required authorized human ownership block.",
        )
    if path.stat().st_size >= MAX_CODEOWNERS_BYTES:
        fail(
            f"{CODEOWNERS_PATH.as_posix()} is not smaller than 3 MB",
            "GitHub does not load a CODEOWNERS file at or above its size limit, so review enforcement would fail open.",
            "reduce the file below 3 MB and keep the required ownership block last.",
        )
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        fail(
            f"{CODEOWNERS_PATH.as_posix()} is not valid UTF-8",
            "GitHub and the deterministic validator need one unambiguous text representation.",
            "encode CODEOWNERS as UTF-8 and rerun validation.",
        )

    entries: list[CodeownerEntry] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        if len(tokens) < 2:
            fail(
                f"CODEOWNERS line {line_number} has no owner",
                "an active CODEOWNERS pattern without an owner cannot establish review authority.",
                f"add at least one @owner to line {line_number} or remove the line.",
            )
        pattern, *owners = tokens
        invalid_owners = [owner for owner in owners if not owner.startswith("@") or len(owner) == 1]
        if invalid_owners:
            fail(
                f"CODEOWNERS line {line_number} contains an invalid owner",
                "every owner must be a GitHub user or team written as @name.",
                f"correct the owner tokens on line {line_number}.",
                "invalid owners: " + ", ".join(invalid_owners),
            )
        entries.append(CodeownerEntry(line_number, pattern, tuple(owners)))
    return entries


def required_patterns(repo: Path, name: str) -> list[str]:
    if name.lower() in CONTROL_PLANE_REPOS:
        return ["*"]

    patterns = ["/.github/"]
    for relative_path in PRODUCTION_CONTROL_FILES:
        if (repo / relative_path).exists():
            patterns.append(f"/{relative_path}")
    for relative_path in PRODUCTION_CONTROL_DIRECTORIES:
        if (repo / relative_path).exists():
            patterns.append(f"/{relative_path}/")
    return [patterns[0], *sorted(patterns[1:])]


def validate_required_block(entries: list[CodeownerEntry], patterns: list[str]) -> None:
    found_patterns = {entry.pattern for entry in entries}
    missing = [pattern for pattern in patterns if pattern not in found_patterns]
    if missing:
        classification = "production-control " if missing != ["/.github/"] else ""
        fail(
            f"CODEOWNERS is missing required {classification}ownership",
            "trust-plane and detected production-control paths need an authorized human code owner.",
            "add the required canonical entries as the final active CODEOWNERS block.",
            "missing patterns: " + ", ".join(missing),
        )

    suffix = entries[-len(patterns) :] if patterns else []
    suffix_patterns = [entry.pattern for entry in suffix]
    if suffix_patterns != patterns:
        fail(
            "CODEOWNERS required entries are not the final active block",
            "a later matching pattern could replace the intended human owners under GitHub's last-match rule.",
            "move the canonical required ownership entries to the end of CODEOWNERS in the reported order.",
            "required final active block: " + ", ".join(patterns),
        )

    authorized = {owner.lower() for owner in AUTHORIZED_HUMAN_OWNERS}
    for entry in suffix:
        entry_owners = {owner.lower() for owner in entry.owners}
        unauthorized_owners = entry_owners - authorized
        if unauthorized_owners:
            fail(
                f"CODEOWNERS pattern {entry.pattern} includes a non-authorized owner",
                "GitHub permits any owner on a matching line to satisfy required code-owner review, so mixing an agent, bot, or unknown identity with a human would weaken the boundary.",
                "assign only centrally authorized human owners to the required pattern.",
                "unauthorized owners: " + ", ".join(sorted(unauthorized_owners)),
            )


def validate(repo: Path) -> int:
    name = repo_name(repo)
    entries = read_entries(repo / CODEOWNERS_PATH)
    patterns = required_patterns(repo, name)
    validate_required_block(entries, patterns)
    print(
        "✓ CODEOWNERS contract validation passed "
        f"(repository={name}, required_patterns={len(patterns)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(validate(repo_root()))
