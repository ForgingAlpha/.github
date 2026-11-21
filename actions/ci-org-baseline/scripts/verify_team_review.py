"""Check the designated organization review rule using target-repository metadata only."""

import json
import os
from pathlib import Path
import re
import sys

# Isolated Python excludes the script directory. Load only the defining checkout's helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import baseline

ORGANIZATION = "ForgingAlpha"
HUMAN_REVIEW_RULE = 25795345
REVIEW = {"team_id": 20299307, "minimum_approvals": 1}
BRANCHES = {"dev", "staging", "main"}


def commit(value):
    baseline.require(isinstance(value, str) and baseline.SHA.fullmatch(value) and value != "0" * 40,
                     "missing or invalid commit identity")
    return value


def repository(value):
    baseline.require(isinstance(value, dict) and baseline.positive(value.get("id"))
                     and isinstance(value.get("full_name"), str)
                     and re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]{1,100}", value["full_name"])
                     and value["full_name"].split("/")[1] not in (".", ".."), "invalid repository metadata")
    return value["full_name"], value["id"]


def revision(side):
    baseline.require(isinstance(side, dict) and isinstance(side.get("ref"), str) and side["ref"],
                     "missing pull request ref")
    return repository(side.get("repo")), side["ref"], commit(side.get("sha"))


def pr_subject(api, event, target):
    number, pr = event.get("number"), event.get("pull_request")
    baseline.require(baseline.positive(number) and isinstance(pr, dict)
                     and os.environ["GITHUB_REF"] == f"refs/pull/{number}/merge", "invalid pull request event")
    base_repo, branch, base = revision(pr.get("base"))
    head_repo, head_ref, head = revision(pr.get("head"))
    baseline.require(base_repo == target and branch in BRANCHES and branch == os.environ["GITHUB_BASE_REF"]
                     and head_ref == os.environ["GITHUB_HEAD_REF"], "event base or head differs from runner")
    live = api.get(f"/repos/{target[0]}/pulls/{number}")
    for record in (pr, live):
        baseline.require(isinstance(record, dict) and record.get("state") == "open"
                         and baseline.positive(record.get("number")) and record["number"] == number,
                         "current open pull request evidence unavailable")
    baseline.require(revision(live.get("base")) == (target, branch, base)
                     and revision(live.get("head")) == (head_repo, head_ref, head), "pull request subject moved")
    # GitHub's pull_request run SHA names the test merge, distinct from the submitted head.
    merge = commit(os.environ["GITHUB_SHA"])
    baseline.require(live.get("merge_commit_sha") == merge and pr.get("merge_commit_sha") in (None, merge),
                     "pull request merge commit differs from runner")
    return branch, base, {"number": number, "base": base, "head": head, "head_repository": head_repo[0],
                          "head_repository_id": head_repo[1], "merge": merge}


def push_subject(event):
    ref, after, before = event.get("ref"), commit(event.get("after")), event.get("before")
    baseline.require(isinstance(ref, str) and ref == os.environ["GITHUB_REF"] and ref.startswith("refs/heads/")
                     and ref.removeprefix("refs/heads/") in BRANCHES and after == os.environ["GITHUB_SHA"]
                     and event.get("deleted") is False and isinstance(before, str) and baseline.SHA.fullmatch(before),
                     "invalid or deleted protected-branch push")
    return ref.removeprefix("refs/heads/"), after, {"before": before, "after": after}


def verify_rule(rules):
    baseline.require(all(isinstance(row, dict) and isinstance(row.get("type"), str)
                         and baseline.positive(row.get("ruleset_id")) for row in rules),
                     "effective rule identity is incomplete")
    matches = [row for row in rules if row["type"] == "pull_request" and row["ruleset_id"] == HUMAN_REVIEW_RULE]
    baseline.require(len(matches) == 1, "designated organization pull request rule is missing or ambiguous")
    rule = matches[0]
    baseline.require(rule.get("ruleset_source_type") == "Organization" and rule.get("ruleset_source") == ORGANIZATION,
                     "designated rule has the wrong source")
    # Validate the full rule, then bind its designated team to the canonical all-file list.
    # A later negative pattern can undo an earlier '*'.
    baseline.team_configuration([rule], REVIEW)
    team_rows = [row for row in rule["parameters"]["required_reviewers"]
                 if row["reviewer"].get("type") == "Team" and row["reviewer"].get("id") == REVIEW["team_id"]]
    baseline.require(len(team_rows) == 1 and team_rows[0]["file_patterns"] == ["*"],
                     "designated team lacks an unambiguous canonical all-files requirement")


def main():
    source_sha = os.environ["DEFINING_SHA"]
    baseline.source_identity(source_sha)
    kind = os.environ.get("GITHUB_EVENT_NAME")
    baseline.require(kind in ("pull_request", "push") and os.environ["GITHUB_SERVER_URL"] == "https://github.com"
                     and os.environ["GITHUB_API_URL"] == "https://api.github.com", "unsupported event or GitHub host")
    event = baseline.decode(baseline.read_regular(Path(os.environ["GITHUB_EVENT_PATH"]), 2 * 1024 * 1024)[0])
    target = repository(event.get("repository"))
    name, identity = target
    baseline.require(name.startswith(ORGANIZATION + "/") and os.environ["GITHUB_REPOSITORY"] == name
                     and os.environ["GITHUB_REPOSITORY_ID"] == str(identity), "event repository differs from runner")

    api = baseline.Api(os.environ.get("GITHUB_TOKEN"))
    baseline.require(repository(api.get(f"/repos/{name}")) == target, "live repository identity changed")
    branch, tip, receipt = pr_subject(api, event, target) if kind == "pull_request" else push_subject(event)
    live = api.get(f"/repos/{name}/branches/{branch}")
    baseline.require(live.get("name") == branch and live.get("protected") is True
                     and live.get("commit", {}).get("sha") == tip, "protected branch identity or tip changed")
    verify_rule(api.rules(name, branch))
    print(json.dumps({"source_sha": source_sha, "repository": name, "repository_id": identity,
                      "branch": branch, kind: receipt, "ruleset_id": HUMAN_REVIEW_RULE, **REVIEW}))


def diagnostic(reason):
    return (f"WHAT: Team review verification refused: {reason}.\n"
            "WHY: The shared source, current revision and complete active review rule must be verifiable together.\n"
            "HOW: Use the protected-main verifier on the current PR or branch push. Ask the protection operator "
            "to confirm the job's existing read access and the effective team rule before retrying.")


if __name__ == "__main__":
    try:
        main()
    except baseline.Refused as error:
        sys.exit(diagnostic(error))
    except (KeyError, ValueError, TypeError, AttributeError, OSError):
        sys.exit(diagnostic("required evidence unavailable or malformed"))
