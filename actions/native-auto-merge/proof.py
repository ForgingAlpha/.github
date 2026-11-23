"""Publish and read the independent exact-review check for a qualified route."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import re
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from enrollment import CONTEXT, SHA, approved_request, load_policy, positive, require


SCHEMA = "native-merge-review-v1"
TEAM_PATH = "orgs/ForgingAlpha/teams/human-approvers"
REVIEW = """
  reviewDecision baseRefOid headRefOid isDraft state
  potentialMergeCommit { oid tree { oid } parents(first: 3) { nodes { oid } } }
  latestOpinionatedReviews(first: 100, writersOnly: true) {
    pageInfo { hasNextPage }
    nodes { fullDatabaseId state submittedAt commit { oid } author { __typename login ... on User { databaseId } } }
  }
"""
TRANSITIONS = """
  transitions: timelineItems(last: 1, itemTypes: [HEAD_REF_FORCE_PUSHED_EVENT,
    BASE_REF_FORCE_PUSHED_EVENT, BASE_REF_CHANGED_EVENT, HEAD_REF_RESTORED_EVENT, REOPENED_EVENT,
    CONVERT_TO_DRAFT_EVENT, READY_FOR_REVIEW_EVENT]) {
    nodes { ... on HeadRefForcePushedEvent { createdAt } ... on BaseRefForcePushedEvent { createdAt }
      ... on BaseRefChangedEvent { createdAt } ... on HeadRefRestoredEvent { createdAt }
      ... on ReopenedEvent { createdAt } ... on ConvertToDraftEvent { createdAt } ... on ReadyForReviewEvent { createdAt } }
  }
"""
ARM_HISTORY = """
  arm: timelineItems(last: 1, itemTypes: [AUTO_MERGE_ENABLED_EVENT, AUTO_MERGE_DISABLED_EVENT,
       AUTO_REBASE_ENABLED_EVENT, AUTO_SQUASH_ENABLED_EVENT]) {
    nodes { __typename ... on AutoMergeEnabledEvent { id createdAt actor { __typename ... on Bot { id databaseId } } }
      ... on AutoMergeDisabledEvent { createdAt } }
  }
"""


def timestamp(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def query_pull(api, repository, number, fields):
    owner, name = repository.split("/")
    result = api.graphql("query($owner:String!,$name:String!,$number:Int!){"
                         "repository(owner:$owner,name:$name){pullRequest(number:$number){id "
                         + fields + "}}}", {"owner": owner, "name": name, "number": number})
    require(not result.get("errors"), "incomplete GitHub pull request response")
    return result["data"]["repository"]["pullRequest"]


def review_evidence(snapshot, pull, members, minimum, last_push, different_pusher):
    head, base = pull["head"]["sha"], pull["base"]["sha"]
    require(snapshot["id"] == pull["node_id"] and snapshot["headRefOid"] == head
            and snapshot["baseRefOid"] == base and snapshot["state"] == "OPEN"
            and snapshot["isDraft"] is False and snapshot["reviewDecision"] == "APPROVED",
            "current native approval on the open, ready PR is missing")
    merge = snapshot["potentialMergeCommit"]
    require(merge["oid"] == pull["merge_commit_sha"] and SHA.fullmatch(merge["oid"])
            and SHA.fullmatch(merge["tree"]["oid"])
            and [p["oid"] for p in merge["parents"]["nodes"]] == [base, head],
            "test merge does not identify the current integration")
    transition = max(timestamp(pull["created_at"]), timestamp(last_push["timestamp"]))
    for event in snapshot["transitions"]["nodes"]:
        transition = max(transition, timestamp(event["createdAt"]))
    latest = snapshot["latestOpinionatedReviews"]
    require(latest["pageInfo"]["hasNextPage"] is False, "latest review set is incomplete")
    require(positive(minimum), "invalid required team approval count")
    approvals = {}
    for review in latest["nodes"]:
        actor = review["author"] or {}
        user = actor.get("databaseId")
        review_id = review.get("fullDatabaseId")
        if (review["state"] == "APPROVED" and review["commit"] and review["commit"]["oid"] == head
                and actor.get("__typename") == "User" and positive(user) and user in members
                and actor["login"] == members[user] and user != pull["user"]["id"]
                and (not different_pusher or user != last_push["actor"]["id"])
                and isinstance(review_id, str) and re.fullmatch(r"[1-9][0-9]*", review_id) and timestamp(review["submittedAt"]) > transition):
            require(user not in approvals, "ambiguous current review for a team member")
            approvals[user] = {"user_id": user, "review_id": int(review_id), "commit": head,
                               "submitted_at": review["submittedAt"]}
    require(len(approvals) >= minimum, "missing current exact-head human team approval")
    return [approvals[k] for k in sorted(approvals)]


def same_bot(graph, rest):
    return (graph["__typename"] == "Bot" and rest["type"] == "Bot" and positive(rest["id"])
            and graph["databaseId"] == rest["id"] and graph["id"] == rest["node_id"] and bool(graph["id"]))


def request_evidence(snapshot, pull, policy):
    arm = pull.get("auto_merge")
    events = snapshot["arm"]["nodes"]
    if arm is None:
        require(not events or (len(events) == 1 and events[0]["__typename"] == "AutoMergeDisabledEvent"),
                "native request record and timeline disagree")
        return None
    require(approved_request(arm, policy) and len(events) == 1,
            "unqualified native request on the pull request")
    event, actor = events[0], arm["enabled_by"]
    require(event["__typename"] == "AutoMergeEnabledEvent" and same_bot(event["actor"], actor)
            and event["id"] and timestamp(event["createdAt"]) >= timestamp(pull["created_at"]),
            "native request timeline does not match the enrolled principal")
    return {"actor_id": actor["id"], "actor_node": actor["node_id"], "event": event["id"],
            "enabled_at": event["createdAt"], "method": "MERGE"}


def collect(api, repository, pull, policy):
    from eligibility import verify_eligible
    team_checker = str(HERE.parent / "ci-org-baseline/scripts")
    if team_checker not in sys.path:
        sys.path.insert(0, team_checker)
    import verify_team_review
    team_id = verify_team_review.baseline.ORGANIZATION_HUMAN_REVIEW["team_id"]
    pr = pull["number"]
    head, base = pull["head"]["sha"], pull["base"]["sha"]
    branch = policy["branch"]
    require(positive(pr) and bool(SHA.fullmatch(head)) and bool(SHA.fullmatch(base))
            and pull["state"] == "open" and pull["draft"] is False
            and pull["base"]["ref"] == branch and pull["base"]["repo"]["id"] == policy["repository_id"]
            and pull["base"]["repo"]["full_name"] == repository and positive(pull["user"]["id"]),
            "PR does not match its protected enrollment")
    # A green SHA check is not portable between PRs or integration targets.
    associations = [row for page in api.pages(f"repos/{repository}/commits/{head}/pulls?per_page=100",
                                               fresh=True) for row in page]
    require(len(associations) == 1 and associations[0]["node_id"] == pull["node_id"],
            "head is reused or its PR association cannot be proved")
    rules = [row for page in api.pages(f"repos/{repository}/rules/branches/{branch}?per_page=100",
                                       fresh=True) for row in page]
    verify_team_review.verify_rule(rules)
    designated = next(rule["parameters"] for rule in rules
                      if rule.get("ruleset_id") == verify_team_review.HUMAN_REVIEW_RULE and rule["type"] == "pull_request")
    minimum = next(row["minimum_approvals"] for row in designated["required_reviewers"]
                   if row["reviewer"]["type"] == "Team" and row["reviewer"]["id"] == team_id)
    team = api.get(TEAM_PATH, fresh=True)
    require(team["id"] == team_id and team["organization"]["login"] == "ForgingAlpha", "team identity changed")
    members = {row["id"]: row["login"] for page in api.pages(TEAM_PATH + "/members?per_page=100", fresh=True)
               for row in page if row["type"] == "User"}
    snapshot = query_pull(api, repository, pr, REVIEW + TRANSITIONS + ARM_HISTORY)
    head_repo = pull["head"]["repo"]["full_name"]
    require(head_repo == repository and pull["head"]["repo"]["id"] == policy["repository_id"],
            "head-ref history is unavailable for this repository")
    ref = "refs/heads/" + pull["head"]["ref"]
    history = api.get(f"repos/{repository}/activity?ref={quote(ref, safe='')}&direction=desc&per_page=2", fresh=True)
    require(isinstance(history, list) and len(history) in (1, 2) and history[0]["ref"] == ref
            and history[0]["after"] == head and positive(history[0]["id"]) and positive(history[0]["actor"]["id"]),
            "most recent head update does not identify this revision")
    require(len(history) == 1 or timestamp(history[0]["timestamp"]) > timestamp(history[1]["timestamp"]),
            "ambiguous head update order")
    different_pusher = any(row.get("parameters", {}).get("require_last_push_approval") is True
                           for row in rules if row["type"] == "pull_request")
    approvals = review_evidence(snapshot, pull, members, minimum, history[0], different_pusher)
    arm = request_evidence(snapshot, pull, policy)
    if arm:
        from protection import verify_qualification
        verify_eligible(api, repository, pull, policy)
        verify_qualification(api, repository, policy, rules)
    tip = api.get(f"repos/{repository}/branches/{branch}", fresh=True)
    compare = api.get(f"repos/{repository}/compare/{base}...{head}", fresh=True)
    require(tip["name"] == branch and tip["protected"] is True and tip["commit"]["sha"] == base
            and compare["merge_base_commit"]["sha"] == base and compare["status"] == "ahead",
            "head does not contain the current protected base")
    merge = snapshot["potentialMergeCommit"]
    return {"schema": SCHEMA, "repository_id": policy["repository_id"], "pr": pr, "pr_node": pull["node_id"],
            "branch": branch, "head": head, "base": base, "integration": merge["oid"],
            "tree": merge["tree"]["oid"], "head_ref": ref, "head_update_id": history[0]["id"], "reviews": approvals, "request": arm}


def external_id(pull):
    return f"{SCHEMA}:{pull['number']}:{pull['base']['sha']}:{pull['head']['sha']}"


def publish(api, repository, pr, event_head, publisher_id, publisher_user_id, *, ambiguous=False):
    endpoint = f"repos/{repository}/pulls/{pr}"
    pull = api.get(endpoint, fresh=True)
    require(pull["number"] == pr and pull["head"]["sha"] == event_head and SHA.fullmatch(event_head)
            and pull["state"] == "open", "wake does not identify the live pull request")
    policy = load_policy(api, repository, pull["base"]["sha"])
    if not policy:
        return "No enrollment on protected base"
    require(policy["branch"] == pull["base"]["ref"] and policy["repository_id"] == pull["base"]["repo"]["id"]
            and policy["proof_app_id"] == publisher_id and positive(publisher_user_id)
            and publisher_user_id != policy["requester_id"], "wrong proof producer or target")
    # A failed or withdrawn review must supersede a previous success. A crash
    # after creation leaves this check outstanding. The caller serializes wakes.
    check = api.post(f"repos/{repository}/check-runs",
                     {"name": CONTEXT, "head_sha": event_head, "external_id": external_id(pull), "status": "in_progress"})
    require(positive(check["id"]) and check["app"]["id"] == publisher_id and check["head_sha"] == event_head
            and check["external_id"] == external_id(pull), "independent check identity is unavailable")
    check_path = f"repos/{repository}/check-runs/{check['id']}"
    try:
        require(not ambiguous, "wake identifies an ambiguous pull-request subject")
        evidence = collect(api, repository, pull, policy)
        require(evidence == collect(api, repository, api.get(endpoint, fresh=True), policy),
                "approval or subject moved during verification")
    except Exception:
        api.patch(check_path, {"status": "completed", "conclusion": "failure",
                               "output": {"title": CONTEXT, "summary": "Exact current approval could not be proved."}})
        raise
    api.patch(check_path, {"status": "completed", "conclusion": "success",
                           "output": {"title": CONTEXT, "summary": json.dumps(evidence, sort_keys=True)}})
    return f"Recorded {CONTEXT} for PR {pr} at {event_head}"


COMPLETION = """
  history: timelineItems(last: 100, itemTypes: [AUTO_MERGE_ENABLED_EVENT, AUTO_MERGE_DISABLED_EVENT,
    AUTO_REBASE_ENABLED_EVENT, AUTO_SQUASH_ENABLED_EVENT, MERGED_EVENT, HEAD_REF_DELETED_EVENT,
    HEAD_REF_FORCE_PUSHED_EVENT, BASE_REF_FORCE_PUSHED_EVENT, BASE_REF_CHANGED_EVENT, HEAD_REF_RESTORED_EVENT,
    REOPENED_EVENT, CONVERT_TO_DRAFT_EVENT, READY_FOR_REVIEW_EVENT]) {
    pageInfo { hasPreviousPage }
    nodes { __typename
      ... on AutoMergeEnabledEvent { id createdAt actor { __typename ... on Bot { id databaseId } } }
      ... on AutoMergeDisabledEvent { createdAt }
      ... on AutoRebaseEnabledEvent { createdAt } ... on AutoSquashEnabledEvent { createdAt }
      ... on MergedEvent { createdAt commit { oid } }
      ... on HeadRefDeletedEvent { createdAt headRefName }
      ... on HeadRefRestoredEvent { createdAt } ... on HeadRefForcePushedEvent { createdAt }
      ... on BaseRefForcePushedEvent { createdAt } ... on BaseRefChangedEvent { createdAt }
      ... on ReopenedEvent { createdAt } ... on ConvertToDraftEvent { createdAt }
      ... on ReadyForReviewEvent { createdAt } }
  }
"""
ARM_TYPES = {"AutoMergeEnabledEvent", "AutoMergeDisabledEvent", "AutoRebaseEnabledEvent", "AutoSquashEnabledEvent"}


def verify_merge_check_evaluation(api, repository, pull, policy, check):
    """A passing rule evaluation can order a same-second check before merge."""
    root = f"repos/{repository}/rulesets/rule-suites"
    ref = "refs/heads/" + policy["branch"]
    target = {"before_sha": pull["base"]["sha"], "after_sha": pull["merge_commit_sha"], "ref": ref,
              "repository_id": policy["repository_id"], "actor_id": pull["merged_by"]["id"], "result": "pass"}
    pages = api.pages(f"{root}?ref={quote(ref, safe='')}&time_period=month&per_page=100", fresh=True)
    matches = [s for page in pages for s in page if all(s.get(k) == v for k, v in target.items())]
    require(len(matches) == 1 and positive(matches[0]["id"]), "ambiguous or unavailable merge rule evaluation")
    suite = api.get(f"{root}/{matches[0]['id']}?include_metadata=true", fresh=True)
    require(suite["id"] == matches[0]["id"] and all(suite.get(k) == v for k, v in target.items()),
            "merge rule evaluation does not match delivery")
    evaluated = []
    for rule in suite["rule_evaluations"]:
        if rule["rule_type"] == "required_status_checks" and rule["enforcement"] == "active" and rule["result"] == "pass":
            checks = rule["metadata"]["checks"]
            require(len(checks) < 50, "rule evaluation metadata may be truncated")
            evaluated.extend(c for c in checks if c["context"] == CONTEXT)
    require(len(evaluated) == 1 and evaluated[0]["id"] == check["id"] and evaluated[0]["app"]["id"] == policy["proof_app_id"]
            and evaluated[0]["type"].lower() in {"check_run", "checkrun"} and evaluated[0]["state"].lower() == "success",
            "merge evaluation does not include this exact successful check run")


def completion_evidence(api, repository, pull, policy, tree):
    """Reconcile the successful pre-merge observation with original PR events."""
    snapshot = query_pull(api, repository, pull["number"], COMPLETION)
    timeline = snapshot["history"]
    require(snapshot["id"] == pull["node_id"] and timeline["pageInfo"]["hasPreviousPage"] is False,
            "incomplete merged PR timeline")
    nodes = timeline["nodes"]
    merges = [i for i, row in enumerate(nodes) if row["__typename"] == "MergedEvent"]
    require(len(merges) == 1, "ambiguous merge event")
    index = merges[0]
    merged = nodes[index]
    require(merged["commit"]["oid"] == pull["merge_commit_sha"] and merged["createdAt"] == pull["merged_at"],
            "timeline merge differs from actual PR merge")
    merged_at = timestamp(pull["merged_at"])
    before, after = nodes[:index], nodes[index+1:]
    require(all(timestamp(e["createdAt"]) <= merged_at for e in before)
            and all(timestamp(e["createdAt"]) >= merged_at for e in after), "inconsistent PR timeline ordering")
    arms = [row for row in before if row["__typename"] in ARM_TYPES]
    if not arms or arms[-1]["__typename"] == "AutoMergeDisabledEvent":
        require(pull.get("auto_merge") is None and pull["merged_by"]["type"] == "User",
                "no matching native request for the recorded merger")
        return None
    event, actor = arms[-1], pull["merged_by"]
    require(len(arms) == 1 and event["__typename"] == "AutoMergeEnabledEvent" and same_bot(event["actor"], actor)
            and actor["id"] == policy["requester_id"], "ambiguous or unqualified native completion actor")
    if pull.get("auto_merge") is not None:
        require(approved_request(pull["auto_merge"], policy), "conflicting native merge method or principal")
    head = pull["head"]["sha"]
    pages = api.pages(f"repos/{repository}/commits/{head}/check-runs?filter=latest&per_page=100", fresh=True)
    checks = [run for page in pages for run in page["check_runs"]
              if run["name"] == CONTEXT and run["app"]["id"] == policy["proof_app_id"]]
    require(len(checks) == 1, "ambiguous or missing independent review check")
    check = checks[0]
    require(positive(check["id"]) and check["head_sha"] == head and check["external_id"] == external_id(pull)
            and check["conclusion"] == "success" and check["status"] == "completed",
            "independent check did not succeed on the exact subject")
    observed = json.loads(check["output"]["summary"])
    require(observed["schema"] == SCHEMA and observed["pr"] == pull["number"]
            and observed["pr_node"] == pull["node_id"] and observed["repository_id"] == policy["repository_id"]
            and observed["head"] == head and observed["base"] == pull["base"]["sha"]
            and observed["branch"] == pull["base"]["ref"] and observed["tree"] == tree
            and SHA.fullmatch(observed["integration"]), "proof and merged source do not correspond")
    expected_arm = {"actor_id": actor["id"], "actor_node": actor["node_id"], "event": event["id"],
                    "enabled_at": event["createdAt"], "method": "MERGE"}
    proof_at = timestamp(check["completed_at"])
    arm_at = timestamp(event["createdAt"])
    if observed["request"] is None:
        # Approval and request can race. Join the two historical observations
        # only if the same head incarnation stayed current until actual merge.
        require(proof_at < arm_at <= merged_at, "request and existing approval have ambiguous ordering")
    else:
        require(observed["request"] == expected_arm and arm_at <= proof_at <= merged_at,
                "native request and pre-merge check do not correspond")
    if proof_at == merged_at:
        verify_merge_check_evaluation(api, repository, pull, policy, check)
    require(all(timestamp(change["createdAt"]) < proof_at for change in before if change["__typename"] not in ARM_TYPES),
            "PR scope changed since the independent review proof")
    ref = "refs/heads/" + pull["head"]["ref"]
    require(ref == observed["head_ref"] and positive(observed["head_update_id"]), "head ref was replaced")
    history = api.get(f"repos/{repository}/activity?ref={quote(ref, safe='')}&direction=desc&per_page=100",
                      fresh=True)
    # GitHub can delete the head in the same second as merge. The ordered PR
    # timeline must place the matching deletion after this exact merge.
    require(isinstance(history, list) and all(h["ref"] == ref for h in history), "incorrect head activity")
    through_merge = [item for item in history if timestamp(item["timestamp"]) <= merged_at]
    same_second = [item for item in through_merge if timestamp(item["timestamp"]) == merged_at]
    if same_second:
        deletions = [e for e in after if e["__typename"] == "HeadRefDeletedEvent"
                     and e["headRefName"] == pull["head"]["ref"]]
        require(len(same_second) == len(deletions) == 1 and same_second[0]["activity_type"] == "branch_deletion"
                and same_second[0]["before"] == head and same_second[0]["after"] == "0" * 40
                and not any(merged_at < timestamp(h["timestamp"]) <= timestamp(deletions[0]["createdAt"])
                            for h in history),
                "head activity at the merge time is ambiguous")
    prior = [item for item in through_merge if timestamp(item["timestamp"]) < merged_at]
    require(prior and prior[0]["id"] == observed["head_update_id"] and prior[0]["after"] == head
            and timestamp(prior[0]["timestamp"]) < proof_at
            and all(timestamp(x["timestamp"]) < timestamp(prior[0]["timestamp"]) for x in prior[1:]),
            "continuous source head history is unavailable")
    eligible = observed["reviews"]
    require(isinstance(eligible, list) and eligible
            and all(positive(r["user_id"]) and positive(r["review_id"]) and r["commit"] == head
                    and timestamp(r["submitted_at"]) <= proof_at for r in eligible),
            "exact pre-merge human approval evidence is missing")
    # An approved review record can coexist with a later disapproving review.
    # No new opinion between the proof and merge may have superseded it.
    review_pages = api.pages(f"repos/{repository}/pulls/{pull['number']}/reviews?per_page=100", fresh=True)
    proved_reviews = {item["review_id"] for item in eligible}
    require(not any(row["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
                    and not (row["state"] == "APPROVED" and row["id"] in proved_reviews)
                    and proof_at <= timestamp(row["submitted_at"]) <= merged_at
                    for page in review_pages for row in page), "a later review requires fresh approval evidence")
    # The producer attested historical roster/permissions. The provider review
    # must still identify the signed human decision; later actions never create it.
    for review in eligible:
        original = api.get(f"repos/{repository}/pulls/{pull['number']}/reviews/{review['review_id']}", fresh=True)
        require(original["id"] == review["review_id"] and original["state"] == "APPROVED"
                and original["user"]["type"] == "User" and original["user"]["id"] == review["user_id"]
                and original["user"]["id"] != pull["user"]["id"] and original["commit_id"] == head
                and original["submitted_at"] == review["submitted_at"], "original exact human review is unavailable")
    return {**observed, "request": expected_arm, "merged_by": actor["login"], "merged_by_id": actor["id"],
            "merged_at": pull["merged_at"], "merge_commit_sha": pull["merge_commit_sha"],
            "check_id": check["id"], "proof_completed_at": check["completed_at"]}


def observe_completion(api, repository, pull, policy, tree):
    evidence = completion_evidence(api, repository, pull, policy, tree)
    return evidence["merged_by"] if evidence else None


def publish_wake(api, repository, repo_id, pointers, run_head, publisher_id, publisher_user_id):
    require(isinstance(pointers, list) and SHA.fullmatch(run_head), "missing notification subject")
    if not pointers:
        pages = api.pages(f"repos/{repository}/commits/{run_head}/pulls?per_page=100", fresh=True)
        pointers = [p for page in pages for p in page if p["state"] == "open" and p["head"]["sha"] == run_head]
    require(pointers, "wake has no current pull request")
    failures, subjects = [], set()
    for pointer in pointers:
        try:
            require(positive(pointer["number"]) and pointer["base"]["repo"]["id"] == repo_id
                    and SHA.fullmatch(pointer["head"]["sha"]), "invalid wake pointer")
            subjects.add((pointer["number"], pointer["head"]["sha"]))
        except (ValueError, TypeError, KeyError) as error:
            failures.append(str(error))
    ambiguous = len(subjects) != 1 or bool(failures)
    for number, head in sorted(subjects):
        try:
            print(publish(api, repository, number, head, publisher_id, publisher_user_id, ambiguous=ambiguous))
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            failures.append(f"PR {number}: {error}")
    require(not failures, " / ".join(failures))


def main():
    sys.path.insert(0, str(HERE.parent / "security-patch/scripts"))
    import security_patch
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    repo, run = event["repository"], event["workflow_run"]
    expected_repo = os.environ["GITHUB_REPOSITORY"]
    require(os.environ["GITHUB_EVENT_NAME"] == "workflow_run" and event["action"] == "completed"
            and os.environ["GITHUB_REF"] == f"refs/heads/{repo['default_branch']}"
            and repo["full_name"] == expected_repo and str(repo["id"]) == os.environ["GITHUB_REPOSITORY_ID"]
            and run["repository"]["id"] == repo["id"] and run["head_repository"]["id"] == repo["id"]
            and run["event"] in {"pull_request", "pull_request_review"}, "unsupported proof notification")
    # The signal is a locator only. No suggested approval, subject files,
    # workflow artifacts or status values are read from its producer.
    pointers = run["pull_requests"]
    api = security_patch.GhApi()
    from enrollment import dedicated_app_slug
    app_slug = os.environ["PROOF_APP_SLUG"]
    require(dedicated_app_slug(app_slug), "proof producer is not a dedicated installation")
    identity = api.get(f"apps/{app_slug}", fresh=True)
    require(identity["slug"] == app_slug and identity["client_id"] == os.environ["PROOF_APP_CLIENT_ID"]
            and positive(identity["id"]), "publisher application identity is unavailable")
    user = api.get(f"users/{app_slug}%5Bbot%5D", fresh=True)
    require(user["type"] == "Bot" and positive(user["id"]), "missing proof producer bot identity")
    publish_wake(api, expected_repo, repo["id"], pointers, run["head_sha"], identity["id"], user["id"])


if __name__ == "__main__":
    try:
        main()
    except (KeyError, IndexError, TypeError, AttributeError, ValueError, RuntimeError, OSError) as error:
        sys.exit(f"Exact human approval unavailable: {error}")
