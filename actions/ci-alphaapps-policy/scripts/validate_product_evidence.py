#!/usr/bin/env python3
"""Validate required Alpha Apps Product Evidence manifests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn


MANIFEST_PATH = Path("docs/evidence/product-evidence.json")
VIEW_PATH = Path("docs/evidence/product-evidence-view.md")
REQUIRED_EVIDENCE_FILES = {MANIFEST_PATH.as_posix(), VIEW_PATH.as_posix()}
BASELINE_SOURCE_TRUTH_FILES = {"docs/intent.md", "docs/requirements.md", "docs/architecture.md"}
SOURCE_TRUTH_BACKFILL_FILES = BASELINE_SOURCE_TRUTH_FILES | {"PROJECT.md", "AGENTS.md", "docs/glossary.md"}
CONTROL_PLANE_REPOS = {".github", "alphaapps-docs"}
ROOT_MARKERS = (
    Path.home() / "src/github.com/forgingalpha",
    Path.home() / "Development/work/forgingalpha",
    Path.home() / "wt",
)
GIT_ENV_OVERRIDES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")

ALLOWED_TYPES = {
    "business/product",
    "technical/architecture",
    "integration/contract",
    "security/safety",
    "operational/quality",
    "change/retirement",
}
ALLOWED_STATUSES = {"covered", "manual-only", "none", "stale"}
ALLOWED_KINDS = {"auto", "manual", "operational", "reviewer"}
STATUS_ORDER = ("stale", "none", "manual-only", "covered")
STATUS_LABELS = {
    "stale": "Stale",
    "none": "None",
    "manual-only": "Manual-only",
    "covered": "Covered",
}
ALLOWED_REF_PREFIXES = ("path:", "command:", "url:", "manual:", "reviewer:", "artifact:")
RAW_PAYLOAD_FIELDS = {
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "body",
    "content",
    "full_tool_input",
    "full_tool_output",
    "full_output",
    "input",
    "key",
    "log",
    "logs",
    "manual_body",
    "model",
    "model_output",
    "modeloutput",
    "output",
    "password",
    "payload",
    "prompt",
    "provider",
    "provider_payload",
    "provider_response",
    "providerresponse",
    "raw",
    "raw_body",
    "raw_output",
    "refresh_token",
    "refreshtoken",
    "secret",
    "session",
    "session_id",
    "sessionid",
    "stderr",
    "stdout",
    "system_prompt",
    "systemprompt",
    "token",
    "tool",
    "tool_input",
    "tool_output",
    "toolinput",
    "tooloutput",
    "transcript",
}
SENSITIVE_REF_PATTERN = re.compile(
    r"(access[-_]?token|api[-_]?key|key|password|refresh[-_]?token|secret|session|token)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(AA_CANARY_SECRET|FORGINGALPHA_CANARY|DO_NOT_PERSIST|"
    r"super[-_]?secret[-_]?token|sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|"
    r"xox[baprs]-|BE" r"GIN [A-Z ]*PRI" r"VATE KEY)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    what: str
    why: str
    how: str


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
            "Product Evidence policy needs git history to distinguish ordinary work from source-truth backfill.",
            "run from a valid checkout with the configured base ref fetched.",
            result.stderr.strip() or result.stdout.strip(),
        )
    return result.stdout.strip()


def repo_root() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        fail(
            "not inside a git repository",
            "Product Evidence policy is repository-local and needs a git worktree.",
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
        "Product Evidence policy must compare this branch with the configured base branch.",
        "fetch the base branch or pass base-ref with an available ref.",
    )


def review_head(repo: Path) -> str:
    current_head = git_stdout(repo, "rev-parse", "HEAD")
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        pr_head = run_git(repo, "rev-parse", "--verify", "HEAD^2^{commit}")
        if pr_head.returncode == 0:
            return pr_head.stdout.strip()
    return current_head


def changed_files(repo: Path, old: str, new: str) -> list[str]:
    output = git_stdout(repo, "diff", "--name-only", "--diff-filter=ACMRD", f"{old}..{new}")
    return [line.strip() for line in output.splitlines() if line.strip()]


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


def is_backfill_only_path(path: str) -> bool:
    if path in SOURCE_TRUTH_BACKFILL_FILES:
        return True
    if path in {MANIFEST_PATH.as_posix(), VIEW_PATH.as_posix()}:
        return True
    if path.startswith("docs/evidence/"):
        return True
    return path.startswith("docs/architecture/")


def changed_paths(repo: Path, repo_name: str) -> tuple[str, list[tuple[str, str, str | None]]]:
    base_ref = default_base_ref(repo_name)
    resolved_base = resolve_ref(repo, base_ref)
    current_head = review_head(repo)
    base_sha = git_stdout(repo, "merge-base", resolved_base, current_head)
    return base_ref, changed_file_statuses(repo, base_sha, current_head)


def deleted_required_evidence_files(statuses: list[tuple[str, str, str | None]]) -> list[str]:
    deleted: list[str] = []
    for status, path, old_path in statuses:
        if status.startswith("D") and path in REQUIRED_EVIDENCE_FILES:
            deleted.append(path)
        if status.startswith("R") and old_path in REQUIRED_EVIDENCE_FILES:
            deleted.append(old_path)
    return sorted(set(deleted))


def load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[Finding]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [
            Finding(
                f"Product Evidence manifest does not exist: {path}",
                "Active ForgingAlpha repositories require Product Evidence before ordinary work can pass shared policy.",
                "create docs/evidence/product-evidence.json or keep this diff limited to source-truth/evidence backfill.",
            )
        ]
    except json.JSONDecodeError as exc:
        return None, [
            Finding(
                f"Product Evidence manifest is not valid JSON: {path}:{exc.lineno}:{exc.colno}",
                "CI needs deterministic JSON parsing before evidence status can be trusted.",
                "fix the JSON syntax and rerun ci-alphaapps-policy.",
            )
        ]
    if not isinstance(raw, dict):
        return None, [
            Finding(
                "Product Evidence manifest root is not an object.",
                "the schema starts with schema_version and promises so generated views have one stable shape.",
                "replace the manifest root with an object containing schema_version and promises.",
            )
        ]
    return raw, []


def diagnostic_ref_value(value: str) -> str:
    return "[redacted-sensitive-path]" if SENSITIVE_REF_PATTERN.search(value) else value


def find_sensitive_string_values(value: Any, location: str, findings: list[Finding]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            find_sensitive_string_values(child, f"{location}.{key}" if location else key, findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            find_sensitive_string_values(child, f"{location}[{index}]", findings)
    elif isinstance(value, str) and SENSITIVE_VALUE_PATTERN.search(value):
        findings.append(
            Finding(
                f"{location} contains a sensitive or canary-looking value.",
                "Product Evidence generated views are durable artifacts and must not render secrets or raw payloads.",
                "replace the value with a stable reference, digest, classification, or short non-sensitive summary.",
            )
        )


def find_raw_payload_fields(value: Any, location: str, findings: list[Finding]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}" if location else key
            normalized = key.lower().replace("-", "_")
            compact = normalized.replace("_", "")
            if normalized in RAW_PAYLOAD_FIELDS or compact in RAW_PAYLOAD_FIELDS:
                findings.append(
                    Finding(
                        f"{child_location} uses raw evidence payload field {key!r}.",
                        "Product Evidence stores references, summaries, classifications, and recency metadata only.",
                        "replace copied output/body data with a stable ref plus a short summary.",
                    )
                )
            find_raw_payload_fields(child, child_location, findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            find_raw_payload_fields(child, f"{location}[{index}]", findings)


def require_string(record: dict[str, Any], field: str, location: str, findings: list[Finding]) -> str | None:
    value = record.get(field)
    if isinstance(value, str) and value.strip():
        return value
    findings.append(
        Finding(
            f"{location}.{field} is missing or not a non-empty string.",
            "Product Evidence rows need stable operator-readable fields.",
            f"set {location}.{field} to a non-empty string.",
        )
    )
    return None


def validate_ref(ref: str, location: str, root: Path, findings: list[Finding]) -> None:
    prefix = next((candidate for candidate in ALLOWED_REF_PREFIXES if ref.startswith(candidate)), None)
    if prefix is None:
        findings.append(
            Finding(
                f"{location}.ref has unsupported reference form.",
                "Product Evidence v1 accepts only path, command, url, manual, reviewer, or artifact references.",
                "use path:, command:, url:, manual:, reviewer:, or artifact:.",
            )
        )
        return
    value = ref[len(prefix) :].strip()
    if not value:
        findings.append(
            Finding(
                f"{location}.ref has an empty {prefix[:-1]} reference.",
                "empty references cannot be resolved by agents or reviewers.",
                "add the stable path, command, URL, manual id, reviewer id, or artifact id after the prefix.",
            )
        )
        return
    if prefix == "path:":
        evidence_path = (root / value).resolve()
        try:
            evidence_path.relative_to(root.resolve())
        except ValueError:
            findings.append(
                Finding(
                    f"{location}.ref points outside the repository.",
                    "local path refs must be repo-relative so reviews are branch-local.",
                    "use a repo-relative path inside this checkout.",
                )
            )
            return
        if not evidence_path.is_file():
            safe_value = diagnostic_ref_value(value)
            findings.append(
                Finding(
                    f"{location}.ref points to missing local evidence path: {safe_value}",
                    "covered/manual/stale evidence cannot be trusted when its local file reference is broken.",
                    f"create {safe_value}, update the ref, or remove the evidence item.",
                )
            )
    elif prefix == "url:" and not value.startswith("https://"):
        findings.append(
            Finding(
                f"{location}.ref uses a non-HTTPS URL.",
                "external Product Evidence links should be stable HTTPS references.",
                "use url:https://... or move local evidence to a path:/artifact:/manual:/reviewer: reference.",
            )
        )


def validate_evidence(
    evidence: Any,
    promise_id: str,
    root: Path,
    findings: list[Finding],
) -> list[dict[str, str]]:
    if not isinstance(evidence, list):
        findings.append(
            Finding(
                f"promise {promise_id} evidence is not a list.",
                "each Product Promise maps to zero or more evidence references.",
                "set evidence to [] or a list of Evidence Item objects.",
            )
        )
        return []

    parsed: list[dict[str, str]] = []
    for index, item in enumerate(evidence):
        location = f"promise {promise_id}.evidence[{index}]"
        if not isinstance(item, dict):
            findings.append(
                Finding(
                    f"{location} is not an object.",
                    "Evidence Items need ref, kind, and summary fields.",
                    "replace the item with an object containing ref, kind, and summary.",
                )
            )
            continue
        ref = require_string(item, "ref", location, findings)
        kind = require_string(item, "kind", location, findings)
        summary = require_string(item, "summary", location, findings)
        last_verified = item.get("last_verified")
        if kind is not None and kind not in ALLOWED_KINDS:
            findings.append(
                Finding(
                    f"{location}.kind has unsupported value {kind!r}.",
                    "Product Evidence v1 uses a small evidence-kind taxonomy.",
                    f"use one of: {', '.join(sorted(ALLOWED_KINDS))}.",
                )
            )
        if ref is not None:
            validate_ref(ref, location, root, findings)
        if last_verified is not None and not isinstance(last_verified, str):
            findings.append(
                Finding(
                    f"{location}.last_verified is not a string.",
                    "freshness metadata must be printable and stable in generated Markdown.",
                    "use an ISO-like date/string value or omit last_verified.",
                )
            )
        if ref is not None and kind is not None and summary is not None and kind in ALLOWED_KINDS:
            parsed.append(
                {
                    "ref": ref,
                    "kind": kind,
                    "summary": summary,
                    "last_verified": last_verified if isinstance(last_verified, str) else "",
                }
            )
    return parsed


def validate_manifest(manifest: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], list[Finding]]:
    findings: list[Finding] = []
    find_raw_payload_fields(manifest, "manifest", findings)
    find_sensitive_string_values(manifest, "manifest", findings)
    if manifest.get("schema_version") != 1:
        findings.append(
            Finding(
                f"schema_version must be 1, got {manifest.get('schema_version')!r}.",
                "Product Evidence View v1 has one supported schema.",
                "set schema_version to 1.",
            )
        )
    promises = manifest.get("promises")
    if not isinstance(promises, list):
        findings.append(
            Finding(
                "promises is missing or not a list.",
                "the generated view is grouped from Product Promise records.",
                "set promises to a list of Product Promise objects.",
            )
        )
        return [], findings

    parsed: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, promise in enumerate(promises):
        location = f"promises[{index}]"
        if not isinstance(promise, dict):
            findings.append(
                Finding(
                    f"{location} is not an object.",
                    "every Product Promise needs id, source_ref, title, type, status, and evidence fields.",
                    "replace the entry with a Product Promise object.",
                )
            )
            continue
        promise_id = require_string(promise, "id", location, findings)
        source_ref = require_string(promise, "source_ref", location, findings)
        title = require_string(promise, "title", location, findings)
        promise_type = require_string(promise, "type", location, findings)
        status = require_string(promise, "status", location, findings)
        evidence_items = validate_evidence(promise.get("evidence"), promise_id or f"#{index}", root, findings)

        if promise_id is not None:
            if promise_id in seen_ids:
                findings.append(
                    Finding(
                        f"Duplicate Product Promise id {promise_id!r}.",
                        "agents need a stable one-row mapping for each Product Promise.",
                        "merge duplicate entries or give each distinct promise its own stable id.",
                    )
                )
            seen_ids.add(promise_id)
        if promise_type is not None and promise_type not in ALLOWED_TYPES:
            findings.append(
                Finding(
                    f"promise {promise_id or index} type has unsupported value {promise_type!r}.",
                    "Product Evidence v1 uses the approved Promise Type taxonomy.",
                    f"use one of: {', '.join(sorted(ALLOWED_TYPES))}.",
                )
            )
        if status is not None and status not in ALLOWED_STATUSES:
            findings.append(
                Finding(
                    f"promise {promise_id or index} status has unsupported value {status!r}.",
                    "Product Evidence v1 status is covered, manual-only, none, or stale.",
                    f"use one of: {', '.join(sorted(ALLOWED_STATUSES))}; put planned work in planned_ref.",
                )
            )
        if promise.get("planned_ref") is not None and not isinstance(promise.get("planned_ref"), str):
            findings.append(
                Finding(
                    f"promise {promise_id or index}.planned_ref is not a string.",
                    "planned_ref is optional planning context only, not evidence status.",
                    "use a string reference or omit planned_ref.",
                )
            )

        stale_reason = promise.get("stale_reason")
        if status == "covered" and not any(item["kind"] == "auto" for item in evidence_items):
            findings.append(
                Finding(
                    f"promise {promise_id or index} is covered without auto evidence.",
                    "covered means current automated evidence exists.",
                    "add an auto Evidence Item or change status to manual-only, none, or stale.",
                )
            )
        if status == "manual-only":
            if not evidence_items:
                findings.append(
                    Finding(
                        f"promise {promise_id or index} is manual-only without evidence.",
                        "manual-only means manual, operational, or reviewer evidence currently exists.",
                        "add a non-auto Evidence Item or change status to none.",
                    )
                )
            if any(item["kind"] == "auto" for item in evidence_items):
                findings.append(
                    Finding(
                        f"promise {promise_id or index} is manual-only but includes auto evidence.",
                        "manual-only must not confuse automated coverage.",
                        "change status to covered or remove the auto Evidence Item.",
                    )
                )
        if status == "none" and evidence_items:
            findings.append(
                Finding(
                    f"promise {promise_id or index} is none but includes evidence.",
                    "none means no mapped evidence exists, so evidence items would overclaim support.",
                    "remove evidence items or choose covered, manual-only, or stale.",
                )
            )
        if status == "stale" and not (isinstance(stale_reason, str) and stale_reason.strip()):
            findings.append(
                Finding(
                    f"promise {promise_id or index} is stale without stale_reason.",
                    "agents need the stale reason to know what evidence must be refreshed.",
                    "add stale_reason explaining the mismatch.",
                )
            )
        if promise_type == "change/retirement" and not (
            isinstance(promise.get("deletion_criterion"), str) and promise["deletion_criterion"].strip()
        ):
            findings.append(
                Finding(
                    f"promise {promise_id or index} is change/retirement without deletion_criterion.",
                    "temporary guardrails need an explicit removal condition.",
                    "add deletion_criterion naming the removal condition.",
                )
            )

        if all(value is not None for value in (promise_id, source_ref, title, promise_type, status)):
            parsed.append(
                {
                    "id": promise_id,
                    "source_ref": source_ref,
                    "title": title,
                    "type": promise_type,
                    "status": status,
                    "planned_ref": promise.get("planned_ref"),
                    "stale_reason": stale_reason,
                    "deletion_criterion": promise.get("deletion_criterion"),
                    "evidence": evidence_items,
                }
            )
    return parsed, findings


def render_view(promises: list[dict[str, Any]]) -> str:
    lines = [
        "# Product Evidence View",
        "",
        "Generated from `docs/evidence/product-evidence.json`.",
        "",
        "This view is derived evidence. It does not create or change product source truth.",
        "",
    ]
    for status in STATUS_ORDER:
        group = sorted([promise for promise in promises if promise["status"] == status], key=lambda item: item["id"])
        lines.extend([f"## {STATUS_LABELS[status]}", ""])
        if not group:
            lines.extend(["No promises in this status.", ""])
            continue
        for promise in group:
            lines.append(f"### {promise['id']} - {promise['title']}")
            lines.append("")
            lines.append(f"- Source: `{promise['source_ref']}`")
            lines.append(f"- Type: `{promise['type']}`")
            lines.append(f"- Status: `{promise['status']}`")
            if promise.get("planned_ref"):
                lines.append(f"- Planned context: `{promise['planned_ref']}`")
            if promise.get("stale_reason"):
                lines.append(f"- Stale reason: {promise['stale_reason']}")
            if promise.get("deletion_criterion"):
                lines.append(f"- Deletion criterion: {promise['deletion_criterion']}")
            evidence_items = promise["evidence"]
            if evidence_items:
                lines.append("- Evidence:")
                for item in evidence_items:
                    line = f"  - `{item['kind']}` `{item['ref']}` - {item['summary']}"
                    if item.get("last_verified"):
                        line = f"{line} (last verified: {item['last_verified']})"
                    lines.append(line)
            else:
                lines.append("- Evidence: none")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print("✗ invalid Product Evidence manifest", file=sys.stderr)
        print(f"  WHAT: {finding.what}", file=sys.stderr)
        print(f"  WHY: {finding.why}", file=sys.stderr)
        print(f"  HOW: {finding.how}", file=sys.stderr)


def validate_required_presence(repo: Path, repo_name: str, manifest_path: Path, view_path: Path) -> bool:
    base_ref, statuses = changed_paths(repo, repo_name)
    deleted_evidence = deleted_required_evidence_files(statuses)
    if deleted_evidence:
        fail(
            "Required Product Evidence artifact removed",
            "required Product Evidence may be created or repaired during evidence backfill, but deleting or renaming it away is an opt-out.",
            "restore the required evidence artifact or record an explicit operator-approved source-truth exception before removing it.",
            "removed paths:\n" + "\n".join(f"- {path}" for path in deleted_evidence),
        )

    if manifest_path.is_file():
        return True
    if view_path.exists():
        fail(
            "orphaned Product Evidence view without manifest",
            "generated Product Evidence views require the manifest that defines their promise-to-evidence rows.",
            "restore docs/evidence/product-evidence.json or remove the orphaned generated view.",
            f"{view_path.as_posix()} exists but {manifest_path.as_posix()} is missing.",
        )
    changed = [path for _, path, _ in statuses]
    if changed and all(is_backfill_only_path(path) for path in changed):
        print(
            "✓ Product Evidence validation passed for source-truth/evidence-backfill-only "
            f"work (BASE_REF={base_ref})"
        )
        return False
    blocked = "\n".join(f"- {path}" for path in changed) if changed else "- no changed paths detected"
    fail(
        "Missing Product Evidence manifest",
        "active ForgingAlpha repositories require docs/evidence/product-evidence.json for ordinary code, "
        "test, dependency, runtime, maintenance, release, broad planning, or implementation changes.",
        "create docs/evidence/product-evidence.json and rerun ci-alphaapps-policy; only source-truth "
        "and evidence-backfill-only changes may proceed while the manifest is missing.",
        f"BASE_REF={base_ref}\nblocked paths:\n{blocked}",
    )


def validate(repo: Path) -> int:
    manifest_path = repo / MANIFEST_PATH
    view_path = repo / VIEW_PATH
    repo_name = alphaapps_repo_name(repo)
    if repo_name is None and not manifest_path.exists() and not view_path.exists():
        print("✓ Product Evidence validation skipped: non-ForgingAlpha repo")
        return 0
    if repo_name is None and view_path.exists() and not manifest_path.exists():
        fail(
            "orphaned Product Evidence view without manifest",
            "generated Product Evidence views require the manifest that defines their rows.",
            "restore docs/evidence/product-evidence.json or remove the orphaned generated view.",
        )
    if repo_name is not None and not validate_required_presence(repo, repo_name, manifest_path, view_path):
        return 0

    manifest, findings = load_manifest(manifest_path)
    if manifest is None:
        print_findings(findings)
        return 1
    promises, validation_findings = validate_manifest(manifest, repo)
    findings.extend(validation_findings)
    if findings:
        print_findings(findings)
        return 1

    if view_path.exists():
        rendered = render_view(promises)
        current = view_path.read_text(encoding="utf-8")
        if current != rendered:
            fail(
                "Product Evidence view is stale",
                "agents and reviewers read docs/evidence/product-evidence-view.md as the generated view of the manifest.",
                "regenerate the view from docs/evidence/product-evidence.json and commit the result.",
            )
    print("✓ Product Evidence validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate(repo_root()))
