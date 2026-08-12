#!/usr/bin/env python3
"""Validate the approved Alpha Apps source-truth baseline."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NoReturn


BASELINE_SOURCE_TRUTH_FILES = ("docs/intent.md", "docs/requirements.md", "docs/architecture.md")
CONTROL_PLANE_REPOS = {".github", "alphaapps-docs"}
DEFINITION_ONLY_FILES = {"PROJECT.md", "AGENTS.md", "docs/glossary.md"} | set(
    BASELINE_SOURCE_TRUTH_FILES
)
GIT_ENV_OVERRIDES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")
MAX_LEADING_COMMENT_LINES = 20
MAX_FRONTMATTER_LINES = 200
MAX_DIAGNOSTIC_STATUS_LENGTH = 40
SENSITIVE_STATUS_PATTERN = re.compile(
    r"(access[-_]?token|api[-_]?key|key|password|refresh[-_]?token|secret|session|token|"
    r"AA_CANARY_SECRET|FORGINGALPHA_CANARY|DO_NOT_PERSIST|"
    r"sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|xox[baprs]-|"
    r"BE" r"GIN [A-Z ]*PRI" r"VATE KEY|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|"
    r"\b\d{3}-\d{2}-\d{4}\b|"
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b)",
    re.IGNORECASE,
)
ROOT_MARKERS = (
    Path.home() / "src/github.com/forgingalpha",
    Path.home() / "Development/work/forgingalpha",
    Path.home() / "wt",
)


@dataclass(frozen=True)
class BaselineStatus:
    path: str
    status: str | None
    problem: str | None


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV_OVERRIDES:
        env.pop(key, None)
    return env


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=git_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fail(what: str, why: str, how: str, details: str | None = None) -> NoReturn:
    print(f"✗ {what}", file=sys.stderr)
    print(f"  WHAT: {what}", file=sys.stderr)
    print(f"  WHY: {why}", file=sys.stderr)
    print(f"  HOW: {how}", file=sys.stderr)
    if details:
        print(details, file=sys.stderr)
    raise SystemExit(1)


def git_stdout(repo: Path, *args: str) -> str:
    result = run_git(repo, *args)
    if result.returncode != 0:
        fail(
            f"git {' '.join(args)} failed",
            "source-truth policy needs git history to compare the branch with its base ref.",
            "run from a valid checkout with the configured base ref fetched.",
            result.stderr.strip() or result.stdout.strip(),
        )
    return result.stdout.strip()


def repo_root() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        fail(
            "not inside a git repository",
            "source-truth policy is defined relative to a repository worktree.",
            "run this action after actions/checkout.",
            result.stderr.strip(),
        )
    return Path(result.stdout.strip())


def origin_url(repo: Path) -> str | None:
    result = run_git(repo, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def repo_from_remote(url: str) -> str | None:
    match = re.search(r"github\.com[:/]forgingalpha/([^/\s]+?)(?:\.git)?$", url, re.IGNORECASE)
    return match.group(1) if match else None


def repo_from_path(repo: Path) -> str | None:
    resolved = repo.resolve()
    for root in ROOT_MARKERS:
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        if relative.parts:
            return relative.parts[0]
    marker = "/src/github.com/forgingalpha/"
    normalized = resolved.as_posix().lower()
    if marker in normalized:
        return normalized.split(marker, 1)[1].split("/", 1)[0]
    return None


def alphaapps_repo_name(repo: Path) -> str | None:
    remote = origin_url(repo)
    if remote:
        detected = repo_from_remote(remote)
        if detected:
            return detected
    return repo_from_path(repo)


def repo_kind(repo_name: str) -> str:
    configured = os.environ.get("ALPHAAPPS_POLICY_REPO_KIND", "auto")
    if configured in {"code", "control-plane"}:
        return configured
    return "control-plane" if repo_name in CONTROL_PLANE_REPOS else "code"


def default_base_ref(repo_name: str) -> str:
    configured = os.environ.get("ALPHAAPPS_POLICY_BASE_REF", "auto")
    if configured and configured != "auto":
        return configured
    return "main" if repo_kind(repo_name) == "control-plane" else "dev"


def resolve_ref(repo: Path, ref: str) -> str:
    candidates = [ref] if ref.startswith("origin/") else [f"origin/{ref}", ref]
    for candidate in candidates:
        result = run_git(repo, "rev-parse", "--verify", f"{candidate}^{{commit}}")
        if result.returncode == 0:
            return candidate
    fail(
        f"base ref not found: {ref}",
        "changed-file lifecycle policy must compare this branch with the configured base branch.",
        "fetch the base branch or pass base-ref with an available ref.",
    )


def review_head(repo: Path) -> str:
    current_head = git_stdout(repo, "rev-parse", "HEAD")
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        pr_head = run_git(repo, "rev-parse", "--verify", "HEAD^2^{commit}")
        if pr_head.returncode == 0:
            return pr_head.stdout.strip()
    return current_head


def changed_file_statuses(repo: Path, old: str, new: str) -> list[tuple[str, str, str | None]]:
    output = git_stdout(repo, "diff", "--name-status", "--diff-filter=ACMRD", f"{old}..{new}")
    statuses: list[tuple[str, str, str | None]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        old_path = parts[1].strip()
        new_path = parts[2].strip() if status.startswith(("R", "C")) and len(parts) > 2 else None
        statuses.append((status, new_path or old_path, old_path if new_path else None))
    return statuses


def paths_from_statuses(statuses: list[tuple[str, str, str | None]]) -> list[str]:
    return [path for _, path, _ in statuses]


def read_frontmatter(path: Path) -> tuple[list[str], str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            if first.startswith("<!--"):
                for _ in range(MAX_LEADING_COMMENT_LINES):
                    if not first or "-->" in first:
                        break
                    first = handle.readline()
                if "-->" not in first:
                    return [], "malformed leading HTML comment before YAML frontmatter"
                first = handle.readline()
                for _ in range(MAX_LEADING_COMMENT_LINES):
                    if not first or first.strip():
                        break
                    first = handle.readline()
                if first and not first.strip():
                    return [], "missing YAML frontmatter with status"
            if first.strip() != "---":
                return [], "missing YAML frontmatter with status"
            lines: list[str] = []
            for line in handle:
                if line.strip() == "---":
                    return lines, None
                lines.append(line.rstrip("\n"))
                if len(lines) > MAX_FRONTMATTER_LINES:
                    return [], "malformed YAML frontmatter: missing closing ---"
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], f"could not read file: {exc}"
    return [], "malformed YAML frontmatter: missing closing ---"


def frontmatter_values(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or line.startswith((" ", "\t")):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def diagnostic_status_value(status: str | None) -> str:
    if status is None:
        return "missing"
    if len(status) > MAX_DIAGNOSTIC_STATUS_LENGTH or SENSITIVE_STATUS_PATTERN.search(status):
        return "[redacted-sensitive-status]"
    return repr(status)


def baseline_status(repo: Path, relative_path: str) -> BaselineStatus:
    path = repo / relative_path
    if not path.is_file():
        return BaselineStatus(relative_path, None, "missing file")
    lines, problem = read_frontmatter(path)
    if problem:
        return BaselineStatus(relative_path, None, problem)
    status = frontmatter_values(lines).get("status")
    if not status:
        return BaselineStatus(relative_path, None, "missing status")
    if status not in {"approved", "provisional"}:
        return BaselineStatus(relative_path, status, f"unsupported status {diagnostic_status_value(status)}")
    return BaselineStatus(relative_path, status, None)


def baseline_statuses(repo: Path) -> list[BaselineStatus]:
    return [baseline_status(repo, path) for path in BASELINE_SOURCE_TRUTH_FILES]


def incomplete_baseline(statuses: list[BaselineStatus]) -> list[BaselineStatus]:
    return [item for item in statuses if item.problem is not None or item.status != "approved"]


def baseline_status_details(statuses: list[BaselineStatus]) -> str:
    lines: list[str] = []
    for item in statuses:
        if item.problem:
            lines.append(f"- {item.path}: {item.problem}")
        elif item.status == "provisional":
            lines.append(f"- {item.path}: status is provisional")
    return "\n".join(lines)


def definition_only_work_allowed(incomplete: list[BaselineStatus]) -> bool:
    return all(item.problem in (None, "missing file") for item in incomplete)


def definition_only_path(path: str) -> bool:
    if path in DEFINITION_ONLY_FILES:
        return True
    parts = PurePosixPath(path).parts
    return len(parts) >= 3 and parts[0] == "docs" and parts[1] == "architecture"


def deleted_baseline_from_statuses(statuses: list[tuple[str, str, str | None]]) -> list[str]:
    return sorted(
        old_path or path
        for status, path, old_path in statuses
        if (status.startswith("D") and path in BASELINE_SOURCE_TRUTH_FILES)
        or (status.startswith("R") and old_path in BASELINE_SOURCE_TRUTH_FILES)
    )


def validate(repo: Path) -> int:
    repo_name = alphaapps_repo_name(repo)
    if repo_name is None:
        print("✓ Approved source-truth validation skipped: non-ForgingAlpha repo")
        return 0

    base_ref = default_base_ref(repo_name)
    resolved_base = resolve_ref(repo, base_ref)
    current_head = review_head(repo)
    base_sha = git_stdout(repo, "merge-base", resolved_base, current_head)
    statuses = changed_file_statuses(repo, base_sha, current_head)
    changed = paths_from_statuses(statuses)
    deleted_baseline = deleted_baseline_from_statuses(statuses)

    baseline = baseline_statuses(repo)
    incomplete = incomplete_baseline(baseline)
    if incomplete:
        blocked = sorted(path for path in changed if not definition_only_path(path))
        if (
            changed
            and not blocked
            and not deleted_baseline
            and definition_only_work_allowed(incomplete)
        ):
            print(
                "✓ Approved source-truth validation passed for "
                f"definition/backfill-only work (BASE_REF={base_ref})"
            )
            return 0
        title = "Deleted baseline source truth" if deleted_baseline else "Incomplete baseline source truth"
        details = baseline_status_details(baseline)
        if deleted_baseline:
            details = f"{details}\ndeleted baseline files:\n" + "\n".join(
                f"- {path}" for path in deleted_baseline
            )
        if blocked:
            details = f"{details}\nblocked paths:\n" + "\n".join(f"- {path}" for path in blocked)
        fail(
            title,
            "every active ForgingAlpha repo requires docs/intent.md, docs/requirements.md, "
            "and docs/architecture.md with status: approved before ordinary planning, "
            "implementation, maintenance, release, dependency, runtime, broad refactor, or test work.",
            "complete or approve the baseline source-truth docs first; while the baseline is "
            "missing, malformed, or provisional, keep the diff limited to definition/backfill paths.",
            details,
        )

    print(f"✓ Approved source-truth validation passed (BASE_REF={base_ref})")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate(repo_root()))
