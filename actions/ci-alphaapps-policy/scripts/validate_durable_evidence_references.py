#!/usr/bin/env python3
"""Reject execution-artifact citations in durable code/test comments."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


SOURCE_SUFFIXES = {
    ".bash",
    ".c",
    ".cc",
    ".cs",
    ".ex",
    ".exs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".mts",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".ts",
    ".tsx",
}
IGNORED_PATH_SEQUENCES = (
    ("docs", "plans"),
    ("docs", "handoffs"),
    ("docs", "audits"),
    ("docs", "research"),
)
SKIP_DIRS = {
    ".git",
    ".claude",
    ".obsidian",
    ".venv",
    "__pycache__",
    "_build",
    "build",
    "deps",
    "dist",
    "node_modules",
    "target",
}
IGNORED_DIRS = {"execution-evidence", "sources"}
SELF_FIXTURE_FILES = {"test_validate_durable_evidence_references.py"}

PLAN_REF = re.compile(r"docs/plans/(?:_archive/)?[^`'\"\n]*?\.md")
HANDOFF_REF = re.compile(r"docs/handoffs/[^`'\"\n]*?\.md")
AUDIT_REF = re.compile(r"docs/audits/[^`'\"\n]*?\.md")
PR_REF = re.compile(r"\bPR\s+#\d+\b", re.IGNORECASE)
AUTHORITY_CONTEXT = re.compile(
    r"\b(?:according to|because|cite|cited|cites|derived from|for|from|guard|guards|"
    r"handoff|implements|per|phase|receipt|refer|reference|source|truth|used by|"
    r"validated|validates|verified|verifies)\b",
    re.IGNORECASE,
)
DURABLE_TEXT_CONTEXT = re.compile(
    r"^\s*(?:@(?:doc|moduledoc|tag|typedoc)\b|assert\b|refute\b|flunk\b|expect\b|"
    r"test\b|describe\b)",
    re.IGNORECASE,
)
ASSERTION_START = re.compile(r"^\s*(?:assert|refute|flunk|expect)\b", re.IGNORECASE)
DOC_BLOCK_START = re.compile(r"^\s*@(?:doc|moduledoc|typedoc)\b.*(?:\"\"\"|''')")
DOC_BLOCK_END = re.compile(r"(?:\"\"\"|''')")
PY_TRIPLE_QUOTE = re.compile(r"^\s*(?:[rRuUbBfF]{0,2})?(?:\"\"\"|''')")
PLAN_PHASE_AUTHORITY = re.compile(
    r"\b(?:according to|because|cite|cited|cites|derived from|for|from|guard|guards|"
    r"handoff|implements|per|receipt|refer|reference|source|truth|used by|validated|validates|verified|verifies)\b"
    r".{0,80}\bPhase\s+\d+\b"
    r"|\bPhase\s+\d+\b"
    r".{0,80}\b(?:approved\s+plan|implementation\s+plan|plan|handoff|receipt|PR)\b",
    re.IGNORECASE,
)
PHASE_AUTHORITY = re.compile(
    r"\b(?:delete|deletion|cleanup|remove|removal|retire|retired|retirement|handoff|receipt|PR)\b"
    r".{0,80}\bPhase\s+\d+\b"
    r"|\bPhase\s+\d+\b"
    r".{0,80}\b(?:delete|deletion|cleanup|remove|removal|retire|retired|retirement|handoff|PR)\b",
    re.IGNORECASE,
)
PHASE_REQUIREMENT_AUTHORITY = re.compile(
    r"\bPhase\s+\d+\b"
    r".{0,120}\b(?:accepts?|allows?|blocks?|cites?|classifies?|creates?|distinguishes?|"
    r"documents?|explains?|fails?|guards?|indexes?|lists?|makes?|must|names?|passes?|"
    r"points?|preserves?|prints?|protects?|rejects?|reports?|requires?|returns?|routes?|"
    r"runs?|shall|should|validates?|verifies?)\b",
    re.IGNORECASE,
)


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def repo_root() -> Path:
    result = run_git("rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return Path.cwd()
    return Path(result.stdout.strip())


def has_path_sequence(parts: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    if len(sequence) > len(parts):
        return False
    return any(tuple(parts[index : index + len(sequence)]) == sequence for index in range(len(parts)))


def is_ignored(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if any(part in IGNORED_DIRS for part in path.parts):
        return True
    return any(has_path_sequence(path.parts, sequence) for sequence in IGNORED_PATH_SEQUENCES)


def should_scan(path: Path) -> bool:
    return path.is_file() and path.suffix in SOURCE_SUFFIXES and not is_ignored(path)


def iter_tracked_paths(root: Path) -> list[Path] | None:
    result = run_git("ls-files", "-z", cwd=root)
    if result.returncode != 0:
        return None
    paths: list[Path] = []
    for raw_path in result.stdout.split("\0"):
        if not raw_path:
            continue
        path = root / raw_path
        if should_scan(path):
            paths.append(path)
    return paths


def iter_default_paths(root: Path) -> list[Path]:
    tracked = iter_tracked_paths(root)
    if tracked is not None:
        return tracked

    paths: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIP_DIRS and dirname not in IGNORED_DIRS
        ]
        current_path = Path(current_root)
        for filename in filenames:
            path = current_path / filename
            if should_scan(path):
                paths.append(path)
    return paths


def is_comment_or_doc_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("#", "//", "/*", "*", "--", "<!--", "@doc", "@moduledoc", "@typedoc"))


def is_durable_text_line(line: str, *, in_doc_block: bool, in_assertion_context: bool) -> bool:
    return (
        in_doc_block
        or in_assertion_context
        or is_comment_or_doc_line(line)
        or bool(DURABLE_TEXT_CONTEXT.search(line))
    )


def is_python_docstring_start(path: Path, line: str, previous_significant: str | None) -> bool:
    return path.suffix == ".py" and bool(PY_TRIPLE_QUOTE.search(line)) and (
        previous_significant is None or previous_significant.endswith(":")
    )


def is_significant_python_line(path: Path, line: str) -> bool:
    if path.suffix != ".py":
        return False
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return not (stripped.startswith(("\"", "'")) and stripped.endswith(("\"", "'")))


def starts_assertion_context(line: str) -> bool:
    return bool(ASSERTION_START.search(line))


def assertion_context_should_continue(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped and stripped not in {"end", "}", ")", "]", "};", ")," })


def forbidden_refs(line: str) -> list[str]:
    refs: list[str] = []
    if AUTHORITY_CONTEXT.search(line):
        for pattern in (PLAN_REF, HANDOFF_REF, AUDIT_REF, PR_REF):
            refs.extend(match.group(0) for match in pattern.finditer(line))
    refs.extend(match.group(0) for match in PLAN_PHASE_AUTHORITY.finditer(line))
    refs.extend(match.group(0) for match in PHASE_AUTHORITY.finditer(line))
    refs.extend(match.group(0) for match in PHASE_REQUIREMENT_AUTHORITY.finditer(line))
    return refs


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    if path.name in SELF_FIXTURE_FILES:
        return findings
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings

    in_doc_block = False
    assertion_context_remaining = 0
    previous_significant: str | None = None
    for line_no, line in enumerate(lines, start=1):
        started_doc_block = False
        if starts_assertion_context(line):
            assertion_context_remaining = 6
        if not in_doc_block and (
            DOC_BLOCK_START.search(line) or is_python_docstring_start(path, line, previous_significant)
        ):
            in_doc_block = True
            started_doc_block = True

        if is_durable_text_line(
            line,
            in_doc_block=in_doc_block,
            in_assertion_context=assertion_context_remaining > 0,
        ):
            for ref in forbidden_refs(line):
                findings.append((line_no, ref, line.strip()))

        if in_doc_block and DOC_BLOCK_END.search(line) and not started_doc_block:
            in_doc_block = False
        elif started_doc_block and line.count('"""') + line.count("'''") >= 2:
            in_doc_block = False
        if not in_doc_block and is_significant_python_line(path, line):
            previous_significant = line.strip()
        if assertion_context_remaining > 0:
            if assertion_context_should_continue(line):
                assertion_context_remaining -= 1
            else:
                assertion_context_remaining = 0
    return findings


def print_findings(findings: list[tuple[Path, int, str, str]]) -> None:
    for path, line_no, ref, line in findings:
        print("✗ durable evidence reference uses execution artifact", file=sys.stderr)
        print(
            f"  WHAT: {path}:{line_no} cites {ref!r} in a durable comment/doc/assertion line: {line}",
            file=sys.stderr,
        )
        print(
            "  WHY: plans, phases, handoffs, PRs, audits, and receipts are execution evidence, "
            "not durable product source truth or orthogonal constraints.",
            file=sys.stderr,
        )
        print(
            "  HOW: cite product source truth, an orthogonal constraint, a stable ADR, approved "
            "design/story behavior, a local invariant, or a retired concept plus deletion condition.",
            file=sys.stderr,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject plan/handoff/audit/PR/phase citations in durable code/test comments."
    )
    parser.add_argument("paths", nargs="*", help="Optional files or directories to scan.")
    args = parser.parse_args()

    root = repo_root()
    candidates: list[Path] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if path.is_dir():
            candidates.extend(iter_default_paths(path))
        elif should_scan(path):
            candidates.append(path)
    if not args.paths:
        candidates = iter_default_paths(root)

    findings: list[tuple[Path, int, str, str]] = []
    for path in candidates:
        for line_no, ref, line in scan_file(path):
            display = path
            try:
                display = path.resolve().relative_to(root.resolve())
            except ValueError:
                pass
            findings.append((display, line_no, ref, line))

    if findings:
        print_findings(findings)
        return 1
    print("✓ durable evidence references valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
