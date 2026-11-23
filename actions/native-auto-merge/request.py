"""Request GitHub's deferred merge. A direct merge is never a recovery operation."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ci-org-baseline/scripts"))
from eligibility import security, verify_eligible
from enrollment import SHA, approved_request, load_policy, positive, require
from protection import effective_rules, snapshot, verify_qualification
from verify_team_review import verify_rule

REQUEST = """mutation($id:ID!, $head:GitObjectID!){
  enablePullRequestAutoMerge(input:{pullRequestId:$id,expectedHeadOid:$head,mergeMethod:MERGE}){
    pullRequest { id }
  }
}"""
STATE = """query($id:ID!) { node(id:$id) { ... on PullRequest {
  id headRefOid baseRefName baseRefOid state isDraft reviewDecision
  timelineItems(last:1,itemTypes:[AUTO_MERGE_ENABLED_EVENT,AUTO_MERGE_DISABLED_EVENT,AUTO_REBASE_ENABLED_EVENT,AUTO_SQUASH_ENABLED_EVENT]){
    nodes { __typename }
  }
} } }"""


def live_rules(api, repo, policy):
    branch = policy["branch"]
    rows = effective_rules(api, repo, branch)
    verify_rule(rows)
    require(not any(r["type"] == "merge_queue" for r in rows), "merge queues require a different route")
    matches = []
    required_ci = False
    for row in rows:
        if row["type"] != "required_status_checks":
            continue
        parameters = row["parameters"]
        for check in parameters["required_status_checks"]:
            if check["context"] == "CI" and check.get("integration_id") == security.TRUSTED_CI_APP_ID:
                required_ci |= parameters.get("strict_required_status_checks_policy") is True
            if check["context"] == policy["proof_context"]:
                require(check.get("integration_id") == policy["proof_app_id"]
                        and parameters["strict_required_status_checks_policy"] is True,
                        "exact approval must be strict and bound to the independent producer")
                matches.append(row)
    require(len(matches) == 1 and required_ci, "required CI or independent exact approval rule missing")
    verify_qualification(api, repo, policy, rows)


def locate(event, env):
    meta = event["repository"]
    repo = meta["full_name"]
    require(re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", repo) and repo == env["GITHUB_REPOSITORY"]
            and positive(meta["id"]) and str(meta["id"]) == env["GITHUB_REPOSITORY_ID"], "event repository mismatch")
    require(env["GITHUB_SERVER_URL"] == "https://github.com" and env["GITHUB_API_URL"] == "https://api.github.com"
            and env["GITHUB_WORKFLOW_REF"] == f"{repo}/.github/workflows/native-merge.yml@refs/heads/{meta['default_branch']}",
            "caller must be the enrolled protected default-branch workflow")
    require(env["GITHUB_RUN_ATTEMPT"] == "1", "replayed run cannot request or restore auto-merge")
    if env["GITHUB_EVENT_NAME"] == "pull_request_target":
        require(event["action"] in ("opened", "ready_for_review") and event["number"] == event["pull_request"]["number"],
                "unsupported PR wake")
        n, sha = event["number"], event["pull_request"]["head"]["sha"]
    else:
        check = event["check_run"]
        require(env["GITHUB_EVENT_NAME"] == "check_run" and event["action"] == "completed"
                and check["name"] == security.SOURCE_CHECK and check["app"]["id"] == security.TRUSTED_SECURITY_AUTOMATION_APP_ID
                and positive(check["id"]) and check["status"] == "completed" and check["conclusion"] == "success",
                "untrusted classification wake")
        match = re.fullmatch(re.escape(security.SOURCE_SCHEMA) + r":([1-9][0-9]*):([a-f0-9]{40})", check["external_id"])
        require(match is not None and match[2] == check["head_sha"], "classification wake lacks exact subject")
        n, sha = int(match[1]), match[2]
    require(positive(n) and SHA.fullmatch(sha), "invalid PR locator")
    return repo, n, sha


def assess(api, event, env, verify_protection=True):
    repo, number, head = locate(event, env)
    meta = api.get(f"repos/{repo}", fresh=True)
    require(meta["id"] == event["repository"]["id"] and meta["default_branch"] == event["repository"]["default_branch"]
            and not meta["archived"], "repository changed or archived")
    pr = api.get(f"repos/{repo}/pulls/{number}", fresh=True)
    require(pr["number"] == number and pr["head"]["sha"] == head, "PR head changed since the wake")
    base = pr["base"]
    if env["GITHUB_EVENT_NAME"] == "pull_request_target":
        source = event["pull_request"]
        require(source["node_id"] == pr["node_id"] and source["base"]["ref"] == base["ref"]
                and source["base"]["sha"] == base["sha"] and source["head"]["ref"] == pr["head"]["ref"],
                "PR source or target changed since the wake")
    require(base["repo"]["id"] == meta["id"] and base["ref"] in ("main", "dev"), "ineligible base")
    tip = api.get(f"repos/{repo}/branches/{base['ref']}", fresh=True)
    require(tip["protected"] is True and tip["commit"]["sha"] == base["sha"], "protected target moved")
    policy = load_policy(api, repo, base["sha"])
    if policy is None:
        return None
    if verify_protection:
        require(meta.get("allow_auto_merge") is True and meta["allow_merge_commit"] is True, "repository auto-merge unavailable")
    require(policy["repository_id"] == meta["id"], "enrollment belongs to another repository")
    lane = verify_eligible(api, repo, pr, policy)
    if env["GITHUB_EVENT_NAME"] == "check_run":
        require(lane == "security-source", "completion wake only applies to a classified Dependabot source")
        _, _, classification = security.parse_attestation_check(
            api, repo, head, security.SOURCE_CHECK, security.TRUSTED_SECURITY_AUTOMATION_APP_ID, security.SOURCE_SCHEMA)
        require(classification["id"] == event["check_run"]["id"], "classification wake differs from live record")
    if verify_protection:
        live_rules(api, repo, policy)
    state = api.post("graphql", {"query": STATE, "variables": {"id": pr["node_id"]}})["data"]["node"]
    require(state["id"] == pr["node_id"] and state["headRefOid"] == head and state["baseRefName"] == base["ref"]
            and state["baseRefOid"] == base["sha"] and state["state"] == "OPEN" and state["isDraft"] is False, "native PR subject moved")
    history = state["timelineItems"]["nodes"]
    require(pr.get("auto_merge") is None or approved_request(pr["auto_merge"], policy), "foreign native request")
    if pr.get("auto_merge") is not None:
        return None
    require(history == [], "an earlier native request or cancellation requires human reconciliation")
    return repo, pr, policy


def request(api, event, env, mutate=False):
    subject = assess(api, event, env, verify_protection=mutate)
    if not subject:
        return False
    if not mutate:
        return True
    repo, pr, policy = subject
    slug = env["REQUESTER_SLUG"]
    require(re.fullmatch(r"[a-z0-9-]+", slug) and slug not in
            {"github-actions", "dependabot", "renovate", "forgingalpha-agent-credential", "forgingalpha-security-automation"},
            "requester is not a dedicated installation")
    app = api.get(f"apps/{slug}", fresh=True)
    require(positive(app["id"]) and app["slug"] == slug and app["id"] not in
            (policy["proof_app_id"], security.TRUSTED_SECURITY_AUTOMATION_APP_ID, security.TRUSTED_CI_APP_ID),
            "requester and review/security proof producers must be distinct")
    actor = api.get(f"users/{slug}%5Bbot%5D", fresh=True)
    require(actor["type"] == "Bot" and actor["id"] == policy["requester_id"], "wrong native requester")
    node, head = pr["node_id"], pr["head"]["sha"]
    # Never retry a write after a timeout. Its effect might already have occurred.
    try:
        result = api.post("graphql", {"query": REQUEST, "variables": {"id": node, "head": head}})
        require(result["data"]["enablePullRequestAutoMerge"]["pullRequest"]["id"] == node, "wrong request receipt")
    except (security.PolicyError, ValueError, KeyError, TypeError) as exc:
        # The response may be lost after GitHub accepts the mutation.
        print(f"Native request returned no conclusive receipt: {exc}", file=sys.stderr)
    observed = api.get(f"repos/{repo}/pulls/{pr['number']}", fresh=True)
    require(observed["node_id"] == node and observed["head"]["sha"] == head
            and observed["head"]["ref"] == pr["head"]["ref"] and observed["base"]["sha"] == pr["base"]["sha"]
            and observed["base"]["ref"] == pr["base"]["ref"] and observed["state"] == "open"
            and approved_request(observed.get("auto_merge"), policy),
            "native request outcome unresolved; inspect the original PR and merge record before any retry")
    print(f"Native request recorded for {repo}#{pr['number']} at {head}. Verify merge separately.")
    return True


def main():
    parser = argparse.ArgumentParser()
    operations = parser.add_subparsers(dest="operation", required=True)
    operations.add_parser("assess")
    operations.add_parser("request")
    inspect = operations.add_parser("ruleset-snapshot", help="read the visible ruleset fingerprint for owner qualification")
    inspect.add_argument("repository")
    inspect.add_argument("branch", choices=("main", "dev"))
    args = parser.parse_args()
    mode = args.operation
    if mode == "ruleset-snapshot":
        require(re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", args.repository), "unexpected repository")
        api = security.GhApi()
        rows = effective_rules(api, args.repository, args.branch)
        digest, newest = snapshot(api, args.repository, args.branch, rows)
        print(json.dumps({"sha256": digest, "latest_ruleset_update": newest.isoformat(),
                          "ruleset_ids": sorted({r["ruleset_id"] for r in rows})}))
        return
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    eligible = request(security.GhApi(), event, os.environ, mutate=(mode == "request"))
    if mode == "assess":
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            print(f"eligible={'true' if eligible else 'false'}", file=out)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        sys.exit(f"Native auto-merge request stopped: {exc}")
