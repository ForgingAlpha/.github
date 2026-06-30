#!/usr/bin/env python3
"""Validate this repo's workflow and composite-action contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_REFS = {"main", "master", "dev", "staging", "HEAD"}
FORBIDDEN_CHECK_DISABLE_INPUTS = {
    "run-build",
    "run-format-check",
    "run-lint",
    "run-tests",
}
FIRST_PARTY_ACTION_OWNERS = {"actions", "github"}
ACTION_REF_ALLOWLIST: dict[str, str] = {}
PULL_REQUEST_TARGET_ALLOWLIST: dict[str, str] = {}
ROOT_PERMISSION_ALLOWLIST: dict[str, str] = {}


def load_yaml(path: Path, errors: list[str]) -> dict[str, Any]:
    read_path = path if path.is_absolute() else ROOT / path
    try:
        loaded = yaml.safe_load(read_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(
            f"{path}: invalid YAML: {exc}. "
            "WHY: shared automation must be parseable before release. "
            "HOW: fix the YAML syntax in this file."
        )
        return {}

    if not isinstance(loaded, dict):
        errors.append(
            f"{path}: YAML root must be a mapping. "
            "WHY: GitHub Actions metadata is object-shaped. "
            "HOW: define top-level keys such as name, on, jobs, or runs."
        )
        return {}

    return loaded


def ref_is_versioned(ref: str) -> bool:
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return True
    if re.fullmatch(r"v?\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?", ref):
        return True
    return False


def is_sha_ref(ref: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", ref))


def action_owner(target: str) -> str:
    return target.split("/", 1)[0]


def allowlist_reason(allowlist: dict[str, str], key: str) -> str | None:
    reason = allowlist.get(key)
    if reason and reason.strip():
        return reason
    return None


def validate_uses_ref(path: Path, uses: str, errors: list[str]) -> None:
    if uses.startswith("./") or uses.startswith("../"):
        return

    if "@" not in uses:
        errors.append(
            f"{path}: action reference '{uses}' has no explicit ref. "
            "WHY: floating action references make CI non-reproducible. "
            "HOW: use a released tag such as @v1 or a full commit SHA."
        )
        return

    target, ref = uses.rsplit("@", 1)
    if ref in FORBIDDEN_REFS or ref.startswith("refs/heads/"):
        errors.append(
            f"{path}: action reference '{uses}' uses branch ref '{ref}'. "
            "WHY: branch refs can change without a reviewed release boundary. "
            "HOW: use a released tag such as @v1 or a full commit SHA."
        )
        return

    if target.startswith("ForgingAlpha/.github/actions/"):
        if not re.fullmatch(r"v\d+", ref):
            errors.append(
                f"{path}: internal shared action '{uses}' must use a major tag. "
                "WHY: vN is the consumer rollout boundary for shared actions. "
                "HOW: replace the ref with @v1 unless a newer major is intended."
            )
        return

    if action_owner(target) in FIRST_PARTY_ACTION_OWNERS:
        if not ref_is_versioned(ref):
            errors.append(
                f"{path}: first-party action reference '{uses}' is not a version "
                "tag or SHA. WHY: GitHub-owned action dependencies still need a "
                "stable release boundary. HOW: use a semver tag such as @v6 or "
                "a full 40-character SHA."
            )
        return

    if is_sha_ref(ref):
        return

    reason = allowlist_reason(ACTION_REF_ALLOWLIST, uses)
    if reason:
        return

    errors.append(
        f"{path}: third-party action reference '{uses}' is not pinned to a full "
        "SHA and is not allowlisted. WHY: third-party moving tags can change "
        "without this repo's review. HOW: pin to a 40-character SHA or add a "
        "non-empty ACTION_REF_ALLOWLIST reason."
    )


def validate_permissions(path: Path, workflow: dict[str, Any], errors: list[str]) -> None:
    permissions = workflow.get("permissions")
    if permissions is None:
        errors.append(
            f"{path}: workflow has no top-level permissions block. "
            "WHY: GitHub workflows should use explicit least privilege. "
            "HOW: add top-level permissions, usually 'contents: read'."
        )
        return

    if isinstance(permissions, str):
        reason = allowlist_reason(ROOT_PERMISSION_ALLOWLIST, str(path))
        if reason:
            return
        errors.append(
            f"{path}: top-level permissions use '{permissions}'. "
            "WHY: broad workflow permissions should not be the root default. "
            "HOW: set explicit read-only permissions at the top level and move "
            "write permissions to the job that needs them, or add an allowlist "
            "reason."
        )
        return

    if not isinstance(permissions, dict):
        errors.append(
            f"{path}: permissions must be a mapping or read-all. "
            "WHY: least-privilege validation needs explicit permission scopes. "
            "HOW: use a mapping such as 'contents: read'."
        )
        return

    broad_scopes = [
        f"{scope}: {value}"
        for scope, value in permissions.items()
        if str(value) not in {"read", "none"}
    ]
    if broad_scopes and not allowlist_reason(ROOT_PERMISSION_ALLOWLIST, str(path)):
        errors.append(
            f"{path}: top-level permissions include broad scopes "
            f"{', '.join(broad_scopes)}. WHY: root workflow permissions apply "
            "too widely for shared control-plane automation. HOW: keep top-level "
            "permissions read-only and put write scopes on the specific job, or "
            "add a non-empty ROOT_PERMISSION_ALLOWLIST reason."
        )


def validate_run_block(path: Path, run: str, errors: list[str]) -> None:
    dangerous_patterns = [
        r"bash\s+<\s*\(\s*curl\b",
        r"\bcurl\b[^\n|]*\|\s*(?:bash|sh)\b",
        r"\bwget\b[^\n|]*\|\s*(?:bash|sh)\b",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, run):
            errors.append(
                f"{path}: run block downloads and executes a script directly. "
                "WHY: remote install scripts bypass reviewed action metadata. "
                "HOW: pin a released version and download an artifact or use a "
                "pinned action ref."
            )
            return


def iter_workflow_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return []

    steps: list[dict[str, Any]] = []
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        job_steps = job.get("steps", [])
        if isinstance(job_steps, list):
            steps.extend(step for step in job_steps if isinstance(step, dict))
    return steps


def iter_workflow_job_uses(workflow: dict[str, Any]) -> list[str]:
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return []

    uses_refs: list[str] = []
    for job in jobs.values():
        if isinstance(job, dict) and isinstance(job.get("uses"), str):
            uses_refs.append(job["uses"])
    return uses_refs


def workflow_triggers(workflow: dict[str, Any]) -> Any:
    # PyYAML YAML 1.1 treats unquoted "on" as True. Support both shapes.
    return workflow.get("on", workflow.get(True, {}))


def has_trigger(triggers: Any, name: str) -> bool:
    if isinstance(triggers, str):
        return triggers == name
    if isinstance(triggers, list):
        return name in triggers
    if isinstance(triggers, dict):
        return name in triggers
    return False


def validate_workflow(path: Path, errors: list[str]) -> None:
    workflow = load_yaml(path, errors)
    if not workflow:
        return

    validate_permissions(path, workflow, errors)

    if has_trigger(workflow_triggers(workflow), "pull_request_target"):
        if not allowlist_reason(PULL_REQUEST_TARGET_ALLOWLIST, str(path)):
            errors.append(
                f"{path}: workflow uses pull_request_target without an allowlist "
                "reason. WHY: privileged PR triggers can expose secrets to "
                "untrusted code. HOW: use pull_request or add a non-empty "
                "PULL_REQUEST_TARGET_ALLOWLIST reason after security review."
            )

    for uses in iter_workflow_job_uses(workflow):
        validate_uses_ref(path, uses, errors)

    for step in iter_workflow_steps(workflow):
        if isinstance(step.get("uses"), str):
            validate_uses_ref(path, step["uses"], errors)
        if isinstance(step.get("run"), str):
            validate_run_block(path, step["run"], errors)


def validate_action(path: Path, errors: list[str]) -> None:
    action = load_yaml(path, errors)
    if not action:
        return

    for field in ("name", "description", "runs"):
        if field not in action:
            errors.append(
                f"{path}: missing required action field '{field}'. "
                "WHY: composite actions need complete metadata for consumers. "
                "HOW: add the missing top-level field."
            )

    runs = action.get("runs", {})
    if isinstance(runs, dict) and runs.get("using") != "composite":
        errors.append(
            f"{path}: runs.using must be 'composite'. "
            "WHY: shared CI checks must preserve the caller job name. "
            "HOW: implement this surface as a composite action."
        )

    inputs = action.get("inputs", {})
    if isinstance(inputs, dict):
        for input_name in sorted(FORBIDDEN_CHECK_DISABLE_INPUTS & set(inputs)):
            errors.append(
                f"{path}: input '{input_name}' can disable a standard check. "
                "WHY: shared CI actions are strict by default for AI-agent work. "
                "HOW: remove the opt-out input or move repo-specific behavior into "
                "a separate explicit action."
            )

    steps = runs.get("steps", []) if isinstance(runs, dict) else []
    if not isinstance(steps, list):
        errors.append(
            f"{path}: runs.steps must be a list. "
            "WHY: composite action execution steps must be ordered. "
            "HOW: define runs.steps as a YAML sequence."
        )
        return

    for step in steps:
        if not isinstance(step, dict):
            continue
        if isinstance(step.get("uses"), str):
            validate_uses_ref(path, step["uses"], errors)
        if isinstance(step.get("run"), str):
            validate_run_block(path, step["run"], errors)


def main() -> int:
    errors: list[str] = []

    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        validate_workflow(path.relative_to(ROOT), errors)

    for path in sorted((ROOT / "actions").rglob("action.yml")):
        validate_action(path.relative_to(ROOT), errors)

    if errors:
        print("✗ GitHub Actions contract validation failed", file=sys.stderr)
        print(
            "WHY: this repository is the shared CI control plane; invalid "
            "metadata or floating refs break consumer repos.",
            file=sys.stderr,
        )
        print(
            "HOW: fix each finding below, then rerun "
            "`python3 scripts/validate-github-actions.py`.",
            file=sys.stderr,
        )
        for error in errors:
            print(f"\n- {error}", file=sys.stderr)
        return 1

    print("✓ GitHub Actions contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
