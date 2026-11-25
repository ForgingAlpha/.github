"""Select the legacy ownership check or verify an enrolled branch's live review policy."""

import json
import os
from pathlib import Path
import re
import sys

ACTION = Path(__file__).resolve().parents[1]
REGISTRY = ACTION / "team-review-repositories.json"
WORKFLOW = ".github/workflows/required-team-review.yml"
SHARED_REPOSITORY_ID = 1137664016


def enrolled(name, identity, branch):
    records = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("invalid team-review registry")
    seen_names, seen_ids = set(), set()
    selected = False
    for row in records:
        repo, repo_id, branches = row["repository"], row["repository_id"], row["branches"]
        if (set(row) != {"repository", "repository_id", "branches"} or not isinstance(repo, str)
                or not re.fullmatch(r"ForgingAlpha/(?!\.{1,2}$)[A-Za-z0-9_.-]{1,100}", repo)
                or type(repo_id) is not int or repo_id <= 0
                or repo.lower() in seen_names or repo_id in seen_ids
                or not isinstance(branches, list) or not branches
                or not set(branches) <= {"main", "dev", "staging"} or len(set(branches)) != len(branches)):
            raise ValueError("invalid or duplicate team-review enrollment")
        seen_names.add(repo.lower())
        seen_ids.add(repo_id)
        if name.lower() == repo.lower() or identity == str(repo_id):
            if name != repo or identity != str(repo_id):
                raise ValueError("enrolled repository name or ID changed")
            selected = branch in branches
    return selected


def required_workflow(rules):
    for rule in rules:
        if (rule["type"] != "workflows" or rule.get("ruleset_source_type") != "Organization"
                or rule.get("ruleset_source") != "ForgingAlpha"):
            continue
        for workflow in rule["parameters"]["workflows"]:
            if (type(workflow.get("repository_id")) is int and workflow["repository_id"] == SHARED_REPOSITORY_ID
                    and workflow.get("path") == WORKFLOW and workflow.get("ref") == "refs/heads/main" and workflow.get("sha") is None):
                return rule["ruleset_id"]
    raise ValueError("the organization does not verifiably require the protected-main team-review workflow")


def verify():
    if (os.environ["POLICY_ACTION_REPOSITORY"], os.environ["POLICY_ACTION_REF"]) != ("ForgingAlpha/.github", "main"):
        raise ValueError("expected the shared policy action from protected main")
    # Isolated Python imports only the shared action archive's verifier here. Legacy callers stay offline.
    sys.path.insert(0, str(ACTION.parent / "ci-org-baseline/scripts"))
    import verify_team_review

    receipt, rules = verify_team_review.current_review()
    if not enrolled(receipt["repository"], str(receipt["repository_id"]), receipt["branch"]):
        raise ValueError("the live review subject is outside central enrollment")
    receipt["required_workflow_ruleset_id"] = required_workflow(rules)
    print(json.dumps(receipt))


def main():
    if sys.argv[1:] == ["select"]:
        selected = enrolled(os.environ["POLICY_REPOSITORY"], os.environ["POLICY_REPOSITORY_ID"],
                            os.environ["POLICY_BRANCH"])
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            print("mode=" + ("team" if selected else "codeowners"), file=output)
    elif sys.argv[1:] == ["verify"]:
        verify()
    else:
        raise ValueError("expected select or verify")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, TypeError, AttributeError, OSError, ImportError) as error:
        reason = str(error) if isinstance(error, ValueError) else "required evidence unavailable or malformed"
        sys.exit(f"WHAT: Repository ownership check refused: {reason}.\n"
                 "WHY: The protected enrollment and current organization rules must identify the same subject.\n"
                 "HOW: Check the shared enrollment, workflow selector and existing read access, then rerun current CI.")
