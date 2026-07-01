#!/usr/bin/env python3
"""Validate Dependabot update coverage for obvious dependency surfaces."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "_build",
    "build",
    "deps",
    "dist",
    "node_modules",
    "target",
}
UNMANAGED_RE = re.compile(
    r"^\s*#\s*alphaapps-dependabot-unmanaged:\s+"
    r"(?P<ecosystem>[a-z0-9_-]+)\s+"
    r"(?P<directory>/\S*)\s+-\s+"
    r"(?P<reason>.+?)\s*$"
)


@dataclass(frozen=True)
class Surface:
    ecosystem: str
    directory: str
    kind: str
    path: str


@dataclass(frozen=True)
class UpdateBlock:
    ecosystem: str
    directories: tuple[str, ...]


@dataclass(frozen=True)
class UnmanagedSurface:
    ecosystem: str
    directory: str
    reason: str


def normalize_directory(directory: str) -> str:
    if not directory:
        return "/"
    normalized = directory.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized


def manifest_directory(path: str) -> str:
    parent = Path(path).parent.as_posix()
    if parent == ".":
        return "/"
    return normalize_directory(parent)


def tracked_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        files: list[str] = []
        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                dirname
                for dirname in dirnames
                if dirname not in IGNORED_DIRS
            )
            for filename in sorted(filenames):
                path = Path(current_root) / filename
                if not path.is_file():
                    continue
                files.append(path.relative_to(root).as_posix())
        return sorted(files)

    return sorted(
        path.decode("utf-8")
        for path in result.stdout.split(b"\0")
        if path
    )


def detect_surfaces(root: Path) -> list[Surface]:
    surfaces: dict[tuple[str, str, str], Surface] = {}
    for path in tracked_files(root):
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
            surfaces[("github-actions", "/", "workflow")] = Surface(
                "github-actions",
                "/",
                "workflow files",
                path,
            )
            continue

        if path.endswith("/action.yml") and (
            path.startswith("actions/") or path.startswith(".github/actions/")
        ):
            directory = manifest_directory(path)
            surfaces[("github-actions", directory, "action")] = Surface(
                "github-actions",
                directory,
                "composite action manifest",
                path,
            )
            continue

        filename = Path(path).name
        if filename == "Cargo.toml":
            directory = manifest_directory(path)
            surfaces[("cargo", directory, "cargo")] = Surface(
                "cargo",
                directory,
                "Cargo manifest",
                path,
            )
        elif filename == "package.json":
            directory = manifest_directory(path)
            surfaces[("npm", directory, "npm")] = Surface(
                "npm",
                directory,
                "npm manifest",
                path,
            )
        elif filename == "mix.exs":
            directory = manifest_directory(path)
            surfaces[("mix", directory, "mix")] = Surface(
                "mix",
                directory,
                "Mix project",
                path,
            )
        elif filename in {"requirements.txt", "pyproject.toml", "Pipfile"}:
            directory = manifest_directory(path)
            surfaces[("pip", directory, "python")] = Surface(
                "pip",
                directory,
                "Python dependency manifest",
                path,
            )

    return sorted(surfaces.values(), key=lambda surface: (surface.ecosystem, surface.directory, surface.path))


def read_yaml_mapping(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(
            f"{path}: Dependabot config was not found. "
            "WHAT: .github/dependabot.yml is missing while dependency surfaces exist. "
            "WHY: detected dependencies need update coverage or documented unmanaged status. "
            "HOW: add .github/dependabot.yml from templates/dependabot/ or remove the dependency surface."
        )
        return {}
    except yaml.YAMLError as exc:
        errors.append(
            f"{path}: invalid YAML: {exc}. "
            "WHAT: Dependabot config could not be parsed. "
            "WHY: update coverage cannot be validated from invalid YAML. "
            "HOW: fix .github/dependabot.yml syntax."
        )
        return {}

    if not isinstance(loaded, dict):
        errors.append(
            f"{path}: YAML root must be a mapping. "
            "WHAT: Dependabot config root was not an object. "
            "WHY: Dependabot v2 config requires top-level version and updates keys. "
            "HOW: use a version: 2 config with an updates list."
        )
        return {}
    return loaded


def load_update_blocks(config: dict[str, Any], config_path: Path, errors: list[str]) -> list[UpdateBlock]:
    if config.get("version") != 2:
        errors.append(
            f"{config_path}: version must be 2. "
            f"WHAT: Dependabot version was {config.get('version')!r}. "
            "WHY: this validator supports the current Dependabot v2 configuration shape. "
            "HOW: set version: 2."
        )

    updates = config.get("updates")
    if not isinstance(updates, list):
        errors.append(
            f"{config_path}: updates must be a list. "
            "WHAT: Dependabot updates was missing or not a list. "
            "WHY: coverage validation needs declared update blocks. "
            "HOW: add updates entries with package-ecosystem and directory or directories."
        )
        return []

    blocks: list[UpdateBlock] = []
    for index, item in enumerate(updates):
        if not isinstance(item, dict):
            errors.append(
                f"{config_path}: updates[{index}] must be a mapping. "
                "WHAT: an update block was not an object. "
                "WHY: Dependabot update blocks must declare an ecosystem and directories. "
                "HOW: rewrite the update block as a YAML mapping."
            )
            continue

        ecosystem = item.get("package-ecosystem")
        if not isinstance(ecosystem, str) or not ecosystem:
            errors.append(
                f"{config_path}: updates[{index}] missing package-ecosystem. "
                "WHAT: an update block has no package-ecosystem. "
                "WHY: coverage validation must match surfaces to ecosystems. "
                "HOW: add package-ecosystem such as github-actions, npm, cargo, mix, or pip."
            )
            continue

        raw_directories = item.get("directories")
        raw_directory = item.get("directory")
        directories: list[str] = []
        if isinstance(raw_directories, list):
            for directory in raw_directories:
                if isinstance(directory, str):
                    directories.append(normalize_directory(directory))
        elif isinstance(raw_directory, str):
            directories.append(normalize_directory(raw_directory))

        if not directories:
            errors.append(
                f"{config_path}: updates[{index}] has no directory/directories. "
                "WHAT: an update block did not declare any directories. "
                "WHY: Dependabot needs a manifest directory for each ecosystem. "
                "HOW: add directory: '/' or directories: ['/', '/path/*']."
            )
            continue

        blocks.append(UpdateBlock(ecosystem=ecosystem, directories=tuple(directories)))

    return blocks


def parse_unmanaged_comments(config_path: Path, errors: list[str]) -> list[UnmanagedSurface]:
    if not config_path.exists():
        return []

    unmanaged: list[UnmanagedSurface] = []
    for lineno, line in enumerate(config_path.read_text(encoding="utf-8").splitlines(), start=1):
        if "alphaapps-dependabot-unmanaged:" not in line:
            continue
        match = UNMANAGED_RE.match(line)
        if not match:
            errors.append(
                f"{config_path}:{lineno}: malformed unmanaged dependency-surface comment. "
                "WHAT: alphaapps-dependabot-unmanaged comment did not include ecosystem, directory, and reason. "
                "WHY: intentionally unmanaged dependency surfaces require explicit review evidence. "
                "HOW: use '# alphaapps-dependabot-unmanaged: <ecosystem> <directory> - <reason>'."
            )
            continue
        reason = match.group("reason").strip()
        if not reason:
            errors.append(
                f"{config_path}:{lineno}: unmanaged dependency-surface comment has no reason. "
                "WHAT: alphaapps-dependabot-unmanaged reason was empty after trimming whitespace. "
                "WHY: intentionally unmanaged dependency surfaces require explicit review evidence. "
                "HOW: add a concrete reason after the dash."
            )
            continue
        unmanaged.append(
            UnmanagedSurface(
                ecosystem=match.group("ecosystem"),
                directory=normalize_directory(match.group("directory")),
                reason=reason,
            )
        )
    return unmanaged


def directory_matches(pattern: str, directory: str) -> bool:
    if pattern == directory:
        return True
    return fnmatch.fnmatchcase(directory, pattern)


def surface_is_covered(surface: Surface, blocks: list[UpdateBlock]) -> bool:
    for block in blocks:
        if block.ecosystem != surface.ecosystem:
            continue
        if any(directory_matches(pattern, surface.directory) for pattern in block.directories):
            return True
    return False


def surface_is_unmanaged(surface: Surface, unmanaged: list[UnmanagedSurface]) -> bool:
    return any(
        item.ecosystem == surface.ecosystem and directory_matches(item.directory, surface.directory)
        for item in unmanaged
    )


def validate(root: Path, config_path: Path) -> list[str]:
    errors: list[str] = []
    surfaces = detect_surfaces(root)
    if not surfaces:
        return errors

    if not config_path.exists():
        for surface in surfaces:
            errors.append(
                f"{surface.path}: missing Dependabot coverage for {surface.ecosystem} at {surface.directory}. "
                "WHAT: .github/dependabot.yml is missing while this dependency surface exists. "
                "WHY: detected dependencies need update coverage or documented unmanaged status. "
                "HOW: add .github/dependabot.yml from templates/dependabot/ or remove the dependency surface."
            )
        return errors

    config = read_yaml_mapping(config_path, errors)
    if not config:
        return errors

    blocks = load_update_blocks(config, config_path, errors)
    unmanaged = parse_unmanaged_comments(config_path, errors)

    for surface in surfaces:
        if surface_is_covered(surface, blocks):
            continue
        if surface_is_unmanaged(surface, unmanaged):
            continue
        errors.append(
            f"{surface.path}: missing Dependabot coverage for {surface.ecosystem} at {surface.directory}. "
            f"WHAT: detected {surface.kind} is not covered by .github/dependabot.yml. "
            "WHY: dependency surfaces need update coverage or explicit unmanaged documentation. "
            "HOW: add a matching Dependabot update block or document the unmanaged surface with "
            f"'# alphaapps-dependabot-unmanaged: {surface.ecosystem} {surface.directory} - <reason>'."
        )

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to validate.")
    parser.add_argument(
        "--config",
        default=".github/dependabot.yml",
        help="Dependabot config path relative to root.",
    )
    parser.add_argument(
        "--mode",
        choices=("fail", "report"),
        default="fail",
        help="fail exits non-zero on findings; report prints findings and exits zero.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path

    errors = validate(root, config_path)
    if errors:
        print("✗ Dependabot coverage validation failed", file=sys.stderr)
        print(
            "WHAT: one or more detected dependency surfaces lack Dependabot update coverage.",
            file=sys.stderr,
        )
        print(
            "WHY: dependency update coverage keeps vulnerable or stale dependency manifests visible.",
            file=sys.stderr,
        )
        print(
            "HOW: add a matching .github/dependabot.yml update block or a documented unmanaged-surface comment.",
            file=sys.stderr,
        )
        for error in errors:
            print(f"\n- {error}", file=sys.stderr)
        return 0 if args.mode == "report" else 1

    print("✓ Dependabot coverage validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
