#!/usr/bin/env python3
"""Check a private repository's protected-dev documentation PR from the remote action."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys


ACTION = Path(__file__).resolve().parent
SOURCE = ACTION.parents[1]
CALLER = ".github/workflows/ci.yml"
sys.dont_write_bytecode = True


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_baseline():
    path = SOURCE / "actions/ci-org-baseline/scripts/baseline.py"
    spec = importlib.util.spec_from_file_location("repo_docs_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def consumer_root():
    root = Path(os.environ["GITHUB_WORKSPACE"])
    require(os.environ.get("GOV_ACTION_REPOSITORY") == "ForgingAlpha/.github" and
            os.environ.get("GOV_ACTION_REF") == "main" and Path(os.environ["GITHUB_ACTION_PATH"]) == ACTION and
            ACTION == SOURCE / "actions/ci-governing-docs", "expected the protected remote governing-docs action")
    require(root.is_absolute() and root == root.resolve() and not SOURCE.is_relative_to(root)
            and not root.is_relative_to(SOURCE), "checking source and consumer must be separate physical directories")
    return root


def scope_line(scopes):
    return b"          scopes: '" + ",".join(scopes).encode("ascii") + b"'\n"


def canonical_caller(baseline, scopes):
    template, _ = baseline.read_regular(ACTION / "caller.yml", 65536)
    selection = scope_line(["."])
    require(template.count(selection) == 1, "invalid action-owned caller template")
    return template.replace(selection, scope_line(scopes))


def caller_contract(baseline, data):
    workflow = baseline.yaml_data(data)
    try:
        checkout = workflow["jobs"]["CI"]["steps"][0]
        owner, separator, revision = checkout["uses"].partition("@")
    except (KeyError, IndexError, AttributeError, TypeError):
        raise ValueError("missing canonical caller checkout step") from None
    require(owner == "actions/checkout" and separator and baseline.SHA.fullmatch(revision),
            "canonical caller requires an immutable actions/checkout revision")
    checkout["uses"] = owner
    return workflow


def preserve_sources(prior, current):
    for path, (old, old_bindings) in prior.items():
        new, new_bindings = current[path]
        for field in ("id", "intent", "requirements"):
            if field in old:
                require(new.get(field) == old[field], "protected governing identity changed")
        for field in ("intent_sha256", "requirements_sha256"):
            if field in old:
                require(field in new, "protected governing digest field removed")
        require(all(new_bindings.get(key, 0) >= count for key, count in old_bindings.items()),
                "protected upstream binding removed")


def current_protection(baseline, api, event, entry):
    branch, _, _ = baseline.prove_pr(api, event, entry)
    rules = api.rules(entry["repository"], branch)
    baseline.team_configuration(rules, baseline.ORGANIZATION_HUMAN_REVIEW)
    baseline.first_definition.required_ci(rules)


def check(baseline, root, event, scopes, api):
    entries = baseline.catalog(baseline.decode((SOURCE / "actions/ci-org-baseline/enrollment.json").read_bytes()))
    entry = baseline.event_subject(root, event, entries, repo_docs=True)
    expected_workflow = entry["repository"] + "/" + CALLER + f'@refs/pull/{event["number"]}/merge'
    require(os.environ.get("GITHUB_WORKFLOW_REF") == expected_workflow, "unexpected native PR workflow source")
    current_protection(baseline, api, event, entry)
    base, head = (event["pull_request"][side]["sha"] for side in ("base", "head"))
    require(base != head and baseline.git(root, "rev-parse", "--is-shallow-repository").strip() == b"false",
            "complete PR ancestry required")
    baseline.git(root, "merge-base", "--is-ancestor", base, head)
    baseline.clean_document_checkout(root, head)
    caller = canonical_caller(baseline, scopes)
    prior = None
    if baseline.git(root, "ls-tree", "-z", base, "--", CALLER):
        adopted = baseline.git(root, "cat-file", "blob", base + ":" + CALLER, limit=65536)
        require(caller_contract(baseline, adopted) == caller_contract(baseline, caller),
                "protected workflow differs from the canonical caller contract or scopes")
        prior_text = baseline.document_inputs(root, base, definition_scopes=scopes, caller=adopted)
        prior = baseline.first_definition.check_documents(prior_text, scopes, baseline.policy, allow_approved=True)
        changed = baseline.git(root, "diff", "--no-renames", "--name-only", "-z", base, head)
        if changed != CALLER.encode() + b"\0":
            caller = adopted
    else:
        baseline.verify_seed(root, base, head)
    texts = baseline.document_inputs(root, head, definition_scopes=scopes, caller=caller, working=True)
    current = baseline.first_definition.check_documents(texts, scopes, baseline.policy, allow_approved=prior is not None)
    if prior is not None:
        preserve_sources(prior, current)
    baseline.lint_documents(root, texts)
    baseline.clean_document_checkout(root, head)
    baseline.document_inputs(root, head, definition_scopes=scopes, caller=caller, working=True)
    current_protection(baseline, api, event, entry)
    return "protected documentation update" if prior is not None else "initial provisional definitions"


def main():
    root = consumer_root()
    baseline = load_baseline()
    scopes = baseline.first_definition.parse_scopes(os.environ.get("GOV_SCOPES"))
    raw, _ = baseline.read_regular(Path(os.environ["GITHUB_EVENT_PATH"]), 2 * 1024 * 1024)
    event = baseline.decode(raw)
    require(isinstance(event, dict), "invalid provider event")
    result = check(baseline, root, event, scopes, baseline.Api(os.environ.get("GITHUB_TOKEN")))
    print("Validated " + result + " on the exact PR head. Human review is separate.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        print(f"Governing documentation CI refused: {error}", file=sys.stderr)
        raise SystemExit(1)
