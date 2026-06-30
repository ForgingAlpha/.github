#!/usr/bin/env python3
"""Validate this repo's workflow and composite-action contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "actions" / "ci-github-actions" / "scripts" / "check_workflows.py"
SPEC = importlib.util.spec_from_file_location("check_workflows", CHECKER_PATH)
checker = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError(
        f"WHAT: could not load GitHub Actions checker from {CHECKER_PATH}. "
        "WHY: parent validation delegates to the reusable ci-github-actions checker. "
        "HOW: restore actions/ci-github-actions/scripts/check_workflows.py."
    )
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


Allowlists = checker.Allowlists
load_yaml = checker.load_yaml
ref_is_versioned = checker.ref_is_versioned
is_sha_ref = checker.is_sha_ref
action_owner = checker.action_owner
allowlist_reason = checker.allowlist_reason
validate_run_block = checker.validate_run_block
iter_workflow_steps = checker.iter_workflow_steps
iter_workflow_job_uses = checker.iter_workflow_job_uses
workflow_triggers = checker.workflow_triggers
has_trigger = checker.has_trigger


def validate_uses_ref(path: Path, uses: str, errors: list[str]) -> None:
    checker.validate_uses_ref(path, uses, errors, Allowlists.empty())


def validate_permissions(path: Path, workflow: dict, errors: list[str]) -> None:
    checker.validate_permissions(path, workflow, errors, Allowlists.empty())


def validate_workflow(path: Path, errors: list[str]) -> None:
    checker.validate_workflow(path, errors, root=ROOT, allowlists=Allowlists.empty())


def validate_action(path: Path, errors: list[str]) -> None:
    checker.validate_action(path, errors, root=ROOT, allowlists=Allowlists.empty())


def main() -> int:
    return checker.run(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
