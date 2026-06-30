#!/usr/bin/env python3
"""Validate GitHub Actions workflow and composite-action safety policy."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


FORBIDDEN_REFS = {"main", "master", "dev", "staging", "HEAD"}
FORBIDDEN_CHECK_DISABLE_INPUTS = {
    "run-build",
    "run-format-check",
    "run-lint",
    "run-tests",
}
FIRST_PARTY_ACTION_OWNERS = {"actions", "github"}
DEFAULT_ALLOWLIST_PATH = ".github/alphaapps-github-actions-allowlist.yml"


@dataclass(frozen=True)
class Allowlists:
    action_refs: dict[str, str]
    pull_request_target: dict[str, str]
    root_permissions: dict[str, str]
    first_party_action_refs: str = "version-or-sha"

    @classmethod
    def empty(cls) -> "Allowlists":
        return cls(action_refs={}, pull_request_target={}, root_permissions={})


def load_yaml(path: Path, errors: list[str], root: Path | None = None) -> dict[str, Any]:
    read_path = path if path.is_absolute() else (root or Path.cwd()) / path
    try:
        loaded = yaml.safe_load(read_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(
            f"{path}: file was not found. "
            "WHAT: GitHub Actions validation could not read this file. "
            "WHY: shared automation policy can only validate checked-out files. "
            "HOW: verify the path exists in the checkout."
        )
        return {}
    except yaml.YAMLError as exc:
        errors.append(
            f"{path}: invalid YAML: {exc}. "
            "WHAT: YAML parsing failed for this workflow or action metadata file. "
            "WHY: shared automation must be parseable before release. "
            "HOW: fix the YAML syntax in this file."
        )
        return {}

    if not isinstance(loaded, dict):
        errors.append(
            f"{path}: YAML root must be a mapping. "
            "WHAT: the parsed YAML root was not an object. "
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


def require_reason_map(
    allowlist_path: Path,
    key: str,
    value: Any,
    errors: list[str],
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(
            f"{allowlist_path}: allowlist key '{key}' must be a mapping. "
            "WHAT: allowlist data had the wrong shape. "
            "WHY: exception policy must bind each exception to a reason. "
            "HOW: use entries like '<path-or-ref>': '<review reason>'."
        )
        return {}

    reasons: dict[str, str] = {}
    for exception, reason in sorted(value.items()):
        if not isinstance(exception, str) or not exception.strip():
            errors.append(
                f"{allowlist_path}: allowlist key '{key}' has an empty exception key. "
                "WHAT: an exception entry was not a non-empty string. "
                "WHY: policy exceptions must target one concrete workflow or action ref. "
                "HOW: replace the key with the exact path or uses reference."
            )
            continue
        if not isinstance(reason, str) or not reason.strip():
            errors.append(
                f"{allowlist_path}: allowlist entry '{key}.{exception}' has no reason. "
                "WHAT: the exception reason was empty. "
                "WHY: broad permissions, privileged triggers, and moving refs require explicit review evidence. "
                "HOW: add a short reason or remove the exception."
            )
            continue
        reasons[exception] = reason.strip()
    return reasons


def load_allowlists(root: Path, allowlist_path: str | None, errors: list[str]) -> Allowlists:
    if allowlist_path is None:
        return Allowlists.empty()

    path = Path(allowlist_path)
    read_path = path if path.is_absolute() else root / path
    if not read_path.exists():
        return Allowlists.empty()

    loaded = load_yaml(path, errors, root=root)
    if not loaded:
        return Allowlists.empty()

    first_party_policy = loaded.get("first_party_action_refs", "version-or-sha")
    if first_party_policy not in {"version-or-sha", "sha"}:
        errors.append(
            f"{path}: first_party_action_refs must be version-or-sha or sha. "
            f"WHAT: first_party_action_refs was {first_party_policy!r}. "
            "WHY: the checker supports only the current version/SHA policy or a stricter SHA-only rollout. "
            "HOW: set first_party_action_refs to version-or-sha or sha."
        )
        first_party_policy = "version-or-sha"

    return Allowlists(
        action_refs=require_reason_map(path, "action_refs", loaded.get("action_refs"), errors),
        pull_request_target=require_reason_map(
            path,
            "pull_request_target",
            loaded.get("pull_request_target"),
            errors,
        ),
        root_permissions=require_reason_map(
            path,
            "root_permissions",
            loaded.get("root_permissions"),
            errors,
        ),
        first_party_action_refs=first_party_policy,
    )


def allowlist_reason(allowlist: dict[str, str], key: str) -> str | None:
    reason = allowlist.get(key)
    if reason and reason.strip():
        return reason
    return None


def validate_uses_ref(
    path: Path,
    uses: str,
    errors: list[str],
    allowlists: Allowlists | None = None,
) -> None:
    allowlists = allowlists or Allowlists.empty()
    if uses.startswith("./") or uses.startswith("../"):
        return

    if "@" not in uses:
        errors.append(
            f"{path}: action reference '{uses}' has no explicit ref. "
            "WHAT: the uses reference omitted an @ref suffix. "
            "WHY: floating action references make CI non-reproducible. "
            "HOW: use a released tag such as @v1 or a full commit SHA."
        )
        return

    target, ref = uses.rsplit("@", 1)
    if ref in FORBIDDEN_REFS or ref.startswith("refs/heads/"):
        errors.append(
            f"{path}: action reference '{uses}' uses branch ref '{ref}'. "
            "WHAT: the uses reference points at a mutable branch ref. "
            "WHY: branch refs can change without a reviewed release boundary. "
            "HOW: use a released tag such as @v1 or a full commit SHA."
        )
        return

    if target.startswith("ForgingAlpha/.github/actions/"):
        if not re.fullmatch(r"v\d+", ref):
            errors.append(
                f"{path}: internal shared action '{uses}' must use a major tag. "
                "WHAT: the internal shared action ref is not a vN major tag. "
                "WHY: vN is the consumer rollout boundary for shared actions. "
                "HOW: replace the ref with @v1 unless a newer major is intended."
            )
        return

    if action_owner(target) in FIRST_PARTY_ACTION_OWNERS:
        if allowlists.first_party_action_refs == "sha" and not is_sha_ref(ref):
            reason = allowlist_reason(allowlists.action_refs, uses)
            if reason:
                return
            errors.append(
                f"{path}: first-party action reference '{uses}' is not pinned to a full SHA. "
                "WHAT: SHA-only first-party policy is enabled and this ref is not a 40-character SHA. "
                "WHY: first_party_action_refs is set to sha for stricter dependency control. "
                "HOW: pin to a 40-character SHA or add a non-empty action_refs allowlist reason."
            )
            return
        if not ref_is_versioned(ref):
            errors.append(
                f"{path}: first-party action reference '{uses}' is not a version "
                "tag or SHA. WHAT: the ref is neither semver-shaped nor a full SHA. "
                "WHY: GitHub-owned action dependencies still need a "
                "stable release boundary. HOW: use a semver tag such as @v6 or "
                "a full 40-character SHA."
            )
        return

    if is_sha_ref(ref):
        return

    reason = allowlist_reason(allowlists.action_refs, uses)
    if reason:
        return

    errors.append(
        f"{path}: third-party action reference '{uses}' is not pinned to a full "
        "SHA and is not allowlisted. WHAT: the ref is a moving third-party tag. "
        "WHY: third-party moving tags can change "
        "without this repo's review. HOW: pin to a 40-character SHA or add a "
        "non-empty action_refs allowlist reason."
    )


def validate_permissions(
    path: Path,
    workflow: dict[str, Any],
    errors: list[str],
    allowlists: Allowlists | None = None,
) -> None:
    allowlists = allowlists or Allowlists.empty()
    permissions = workflow.get("permissions")
    if permissions is None:
        errors.append(
            f"{path}: workflow has no top-level permissions block. "
            "WHAT: the workflow omitted explicit root permissions. "
            "WHY: GitHub workflows should use explicit least privilege. "
            "HOW: add top-level permissions, usually 'contents: read'."
        )
        return

    if isinstance(permissions, str):
        reason = allowlist_reason(allowlists.root_permissions, str(path))
        if reason:
            return
        errors.append(
            f"{path}: top-level permissions use '{permissions}'. "
            "WHAT: root permissions use a broad string value. "
            "WHY: broad workflow permissions should not be the root default. "
            "HOW: set explicit read-only permissions at the top level and move "
            "write permissions to the job that needs them, or add an allowlist "
            "reason."
        )
        return

    if not isinstance(permissions, dict):
        errors.append(
            f"{path}: permissions must be a mapping or read-all. "
            "WHAT: the permissions block is not a valid GitHub Actions permissions shape. "
            "WHY: least-privilege validation needs explicit permission scopes. "
            "HOW: use a mapping such as 'contents: read'."
        )
        return

    broad_scopes = [
        f"{scope}: {value}"
        for scope, value in permissions.items()
        if str(value) not in {"read", "none"}
    ]
    if broad_scopes and not allowlist_reason(allowlists.root_permissions, str(path)):
        errors.append(
            f"{path}: top-level permissions include broad scopes "
            f"{', '.join(broad_scopes)}. WHAT: root permissions include write or elevated scopes. "
            "WHY: root workflow permissions apply "
            "too widely for shared control-plane automation. HOW: keep top-level "
            "permissions read-only and put write scopes on the specific job, or "
            "add a non-empty root_permissions allowlist reason."
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
                "WHAT: a run step pipes or process-substitutes a remote download into a shell. "
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


def validate_workflow(
    path: Path,
    errors: list[str],
    root: Path | None = None,
    allowlists: Allowlists | None = None,
) -> None:
    allowlists = allowlists or Allowlists.empty()
    workflow = load_yaml(path, errors, root=root)
    if not workflow:
        return

    validate_permissions(path, workflow, errors, allowlists)

    if has_trigger(workflow_triggers(workflow), "pull_request_target"):
        if not allowlist_reason(allowlists.pull_request_target, str(path)):
            errors.append(
                f"{path}: workflow uses pull_request_target without an allowlist "
                "reason. WHAT: pull_request_target is enabled without reviewed exception data. "
                "WHY: privileged PR triggers can expose secrets to "
                "untrusted code. HOW: use pull_request or add a non-empty "
                "pull_request_target allowlist reason after security review."
            )

    for uses in iter_workflow_job_uses(workflow):
        validate_uses_ref(path, uses, errors, allowlists)

    for step in iter_workflow_steps(workflow):
        if isinstance(step.get("uses"), str):
            validate_uses_ref(path, step["uses"], errors, allowlists)
        if isinstance(step.get("run"), str):
            validate_run_block(path, step["run"], errors)


def validate_action(
    path: Path,
    errors: list[str],
    root: Path | None = None,
    allowlists: Allowlists | None = None,
) -> None:
    allowlists = allowlists or Allowlists.empty()
    action = load_yaml(path, errors, root=root)
    if not action:
        return

    for field in ("name", "description", "runs"):
        if field not in action:
            errors.append(
                f"{path}: missing required action field '{field}'. "
                "WHAT: composite action metadata is missing a required top-level field. "
                "WHY: composite actions need complete metadata for consumers. "
                "HOW: add the missing top-level field."
            )

    runs = action.get("runs", {})
    if isinstance(runs, dict) and runs.get("using") != "composite":
        errors.append(
            f"{path}: runs.using must be 'composite'. "
            "WHAT: the shared action is not declared as a composite action. "
            "WHY: shared CI checks must preserve the caller job name. "
            "HOW: implement this surface as a composite action."
        )

    inputs = action.get("inputs", {})
    if isinstance(inputs, dict):
        for input_name in sorted(FORBIDDEN_CHECK_DISABLE_INPUTS & set(inputs)):
            errors.append(
                f"{path}: input '{input_name}' can disable a standard check. "
                "WHAT: this action exposes a standard-check opt-out input. "
                "WHY: shared CI actions are strict by default for AI-agent work. "
                "HOW: remove the opt-out input or move repo-specific behavior into "
                "a separate explicit action."
            )

    steps = runs.get("steps", []) if isinstance(runs, dict) else []
    if not isinstance(steps, list):
        errors.append(
            f"{path}: runs.steps must be a list. "
            "WHAT: composite action steps are not a YAML sequence. "
            "WHY: composite action execution steps must be ordered. "
            "HOW: define runs.steps as a YAML sequence."
        )
        return

    for step in steps:
        if not isinstance(step, dict):
            continue
        if isinstance(step.get("uses"), str):
            validate_uses_ref(path, step["uses"], errors, allowlists)
        if isinstance(step.get("run"), str):
            validate_run_block(path, step["run"], errors)


def iter_workflow_paths(root: Path) -> list[Path]:
    workflow_dir = root / ".github" / "workflows"
    return sorted(
        [
            *workflow_dir.glob("*.yml"),
            *workflow_dir.glob("*.yaml"),
        ]
    )


def iter_action_paths(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", "actions/**/action.yml"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return sorted((root / "actions").rglob("action.yml"))

    return [
        root / relative_path
        for relative_path in sorted(result.stdout.splitlines())
        if relative_path
    ]


def run(root: Path, allowlist_path: str | None = DEFAULT_ALLOWLIST_PATH) -> int:
    root = root.resolve()
    errors: list[str] = []
    allowlists = load_allowlists(root, allowlist_path, errors)

    for path in iter_workflow_paths(root):
        validate_workflow(path.relative_to(root), errors, root=root, allowlists=allowlists)

    for path in iter_action_paths(root):
        validate_action(path.relative_to(root), errors, root=root, allowlists=allowlists)

    if errors:
        print("✗ GitHub Actions safety validation failed", file=sys.stderr)
        print(
            "WHAT: one or more workflow or composite-action policy checks failed.",
            file=sys.stderr,
        )
        print(
            "WHY: shared automation must be reproducible, least-privileged, and safe for public CI consumers.",
            file=sys.stderr,
        )
        print(
            "HOW: fix each finding below, then rerun the ci-github-actions checker.",
            file=sys.stderr,
        )
        for error in errors:
            print(f"\n- {error}", file=sys.stderr)
        return 1

    print("✓ GitHub Actions safety validation passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to validate.",
    )
    parser.add_argument(
        "--allowlist-path",
        default=DEFAULT_ALLOWLIST_PATH,
        help="Optional allowlist YAML path relative to root. Missing file means no exceptions.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(Path(args.root), allowlist_path=args.allowlist_path)


if __name__ == "__main__":
    raise SystemExit(main())
