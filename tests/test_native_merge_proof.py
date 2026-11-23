"""Independently exercise exact approvals, publisher failure and security source attribution."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "actions/native-auto-merge"))
import proof

REPO = "ForgingAlpha/example"
TARGET = {"id": 200, "full_name": REPO}
BASE, HEAD, MERGE, TREE = (letter * 40 for letter in "abce")
BOT = {"id": 77, "type": "Bot", "login": "request[bot]", "node_id": "BOT-node"}
DATE = "2026-10-31T10:10:"
POLICY = {"proof_app_id": 88, "requester_id": 77, "repository_id": 200, "branch": "dev"}
RULE = {"type": "pull_request", "ruleset_id": 25795345, "ruleset_source_type": "Organization",
        "ruleset_source": "ForgingAlpha", "parameters": {"required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": True, "required_reviewers": [{"reviewer": {"type": "Team",
        "id": 20299307}, "minimum_approvals": 1, "file_patterns": ["*"]}]}}


class API:
    def __init__(self):
        self.pull = {"node_id": "PR-node", "number": 12, "state": "open", "draft": False,
                     "created_at": DATE + "01Z", "merge_commit_sha": MERGE, "user": {"id": 51},
                     "head": {"sha": HEAD, "ref": "feature/task", "repo": TARGET}, "base": {"sha": BASE, "ref": "dev", "repo": TARGET}}
        self.review = {"databaseId": 93, "submittedAt": DATE + "18Z", "state": "APPROVED",
                       "commit": {"oid": HEAD}, "author": {"databaseId": 52, "__typename": "User", "login": "reviewer"}}
        self.graph = {"id": "PR-node", "headRefOid": HEAD, "baseRefOid": BASE, "state": "OPEN", "isDraft": False,
                      "reviewDecision": "APPROVED", "potentialMergeCommit": {"oid": MERGE, "tree": {"oid": TREE},
                      "parents": {"nodes": [{"oid": BASE}, {"oid": HEAD}]}},
                      "latestOpinionatedReviews": {"pageInfo": {"hasNextPage": False}, "nodes": [self.review]},
                      "transitions": {"nodes": []}, "arm": {"nodes": []}}
        self.members = [{"type": "User", "id": 52, "login": "reviewer"}]
        self.associations = [{"node_id": "PR-node"}]
        self.last_push = {"ref": "refs/heads/feature/task", "after": HEAD, "id": 81,
                          "pushed_at": DATE + "09Z", "pusher": {"id": 51}}
        self.rules = [deepcopy(RULE)]
        self.writes = []
        self.checks = []
        self.later_reviews = []

    def pages(self, path, fresh=False):
        if path == f"repos/{REPO}/pulls/12/reviews?per_page=100":
            return [self.later_reviews]
        if path == proof.TEAM_PATH + "/members?per_page=100":
            return [self.members]
        if path == f"repos/{REPO}/rules/branches/dev?per_page=100":
            return [self.rules]
        if path == f"repos/{REPO}/commits/{HEAD}/pulls?per_page=100":
            return [self.associations]
        if path == f"repos/{REPO}/commits/{HEAD}/check-runs?filter=latest&per_page=100":
            return [{"check_runs": self.checks}]
        raise AssertionError(path)

    def get(self, path, fresh=False):
        if path == f"repos/{REPO}/pulls/12":
            return deepcopy(self.pull)
        if path == proof.TEAM_PATH:
            return {"id": 20299307, "organization": {"login": "ForgingAlpha"}}
        if path in (f"repos/{REPO}/activity?ref=refs%2Fheads%2Ffeature%2Ftask&direction=desc&per_page=2",
                    f"repos/{REPO}/activity?ref=refs%2Fheads%2Ffeature%2Ftask&direction=desc&per_page=100"):
            return [self.last_push]
        if path == f"repos/{REPO}/branches/dev":
            return {"name": "dev", "protected": True, "commit": {"sha": BASE}}
        if path == f"repos/{REPO}/compare/{BASE}...{HEAD}":
            return {"status": "ahead", "merge_base_commit": {"sha": BASE}}
        if path == f"repos/{REPO}/pulls/12/reviews/93":
            return {"id": 93, "state": self.review["state"], "commit_id": HEAD,
                    "submitted_at": DATE + "18Z", "user": {"id": 52, "type": "User"}}
        raise AssertionError(path)

    def graphql(self, query, variables):
        assert variables == {"owner": "ForgingAlpha", "name": "example", "number": 12}
        return {"data": {"repository": {"pullRequest": deepcopy(self.graph)}}}

    def post(self, path, record):
        assert path == f"repos/{REPO}/check-runs"
        self.writes.append(record["status"])
        self.checks = [dict(record, id=101, app={"id": 88})]
        return self.checks[0]

    def patch(self, path, record):
        assert path == f"repos/{REPO}/check-runs/101"
        self.writes.append(record["conclusion"])
        self.checks[0].update(record, completed_at=DATE + "19Z")
        return self.checks[0]

    def arm(self):
        self.pull["auto_merge"] = {"enabled_by": BOT, "merge_method": "merge"}
        self.graph["arm"] = {"nodes": [{"__typename": "AutoMergeEnabledEvent", "id": "EVENT-node",
                              "createdAt": DATE + "08Z", "actor": {"id": BOT["node_id"], "login": BOT["login"]}}]}

    def run_check(self):
        with patch.object(proof, "load_policy", return_value=POLICY):
            return proof.publish(self, REPO, 12, HEAD, 88)


class ProofTests(unittest.TestCase):
    def test_manual_path_checks_review_without_requiring_arm(self):
        api = API()
        api.run_check()
        receipt = json.loads(api.checks[0]["output"]["summary"])
        self.assertIsNone(receipt["request"])
        self.assertEqual(receipt["reviews"][0]["user_id"], 52)
        self.assertEqual(api.writes, ["in_progress", "success"])

    def test_new_sha_with_same_diff_and_withdrawn_or_ineligible_review_never_pass(self):
        for mutate in (lambda a: a.review["commit"].update(oid="9" * 40),
                       lambda a: a.review.update(state="DISMISSED"),
                       lambda a: a.graph.update(reviewDecision="CHANGES_REQUESTED"),
                       lambda a: a.review["author"].update(__typename="Bot"),
                       lambda a: a.pull["user"].update(id=52), lambda a: a.members.clear(),
                       lambda a: a.graph["latestOpinionatedReviews"]["pageInfo"].update(hasNextPage=True),
                       lambda a: a.graph["transitions"]["nodes"].append({"createdAt": DATE + "18Z"}),
                       lambda a: a.last_push.update(pushed_at=DATE + "19Z"),
                       lambda a: (a.rules[0]["parameters"].update(require_last_push_approval=True),
                                  a.last_push.update(pusher={"id": 52})),
                       lambda a: a.associations.append({"node_id": "other PR"}),
                       lambda a: a.graph["potentialMergeCommit"]["parents"]["nodes"].reverse(),
                       lambda a: a.rules[0]["parameters"]["required_reviewers"][0].update(minimum_approvals=2)):
            api = API()
            mutate(api)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                api.run_check()
            self.assertEqual(api.writes, ["in_progress", "failure"])

    def test_wrong_actor_cannot_publish_or_start_a_check(self):
        api = API()
        with patch.object(proof, "load_policy", return_value=POLICY), self.assertRaisesRegex(ValueError, "producer"):
            proof.publish(api, REPO, 12, HEAD, 15)
        self.assertEqual(api.writes, [])

    def test_reconciliation_on_failed_recheck(self):
        api = API()
        first = proof.collect(api, REPO, api.pull, POLICY)
        with patch.object(proof, "collect", side_effect=[first, dict(first, base="f" * 40)]):
            with self.assertRaisesRegex(ValueError, "moved"):
                api.run_check()
        self.assertEqual(api.writes, ["in_progress", "failure"])

    def test_source_readback_binds_request_producer_review_time_and_tree(self):
        for reason in ("valid", "actor", "context", "time", "tree", "disabled", "different-event", "dismissed", "superseded", "changed-subject"):
            api = API()
            api.arm()
            with patch("eligibility.verify_eligible", return_value="security-source"):
                api.run_check()
            api.pull.update(state="closed", merged_at=DATE + "20Z", merged_by=dict(BOT), auto_merge=None)
            if reason == "actor":
                api.pull["merged_by"]["id"] += 1
            if reason == "context":
                api.checks[0]["app"]["id"] += 1
            if reason == "time":
                api.checks[0]["completed_at"] = api.pull["merged_at"]
            if reason == "disabled":
                api.graph["arm"]["nodes"][0].update(__typename="AutoMergeDisabledEvent", createdAt=DATE + "21Z")
            if reason == "different-event":
                api.graph["arm"]["nodes"][0].update(id="other")
            if reason == "changed-subject":
                api.last_push.update(id=84, pushed_at=DATE + "19Z")
            if reason == "superseded":
                api.later_reviews.append({"state": "CHANGES_REQUESTED", "submitted_at": DATE + "20Z"})
            if reason == "dismissed":
                api.review["state"] = "DISMISSED"
            with self.subTest(reason=reason):
                if reason == "valid":
                    self.assertEqual(proof.observe_completion(api, REPO, api.pull, POLICY, TREE), BOT["login"])
                else:
                    with self.assertRaises(ValueError):
                        proof.observe_completion(api, REPO, api.pull, POLICY, BASE if reason == "tree" else TREE)

    def test_late_security_request_needs_unchanged_head_incarnation_and_strict_timeline(self):
        for mode in ("valid", "reused-head", "equal-time", "retargeted"):
            api = API()
            api.run_check()
            api.arm()
            api.graph["arm"]["nodes"][0]["createdAt"] = DATE + ("19Z" if mode == "equal-time" else "20Z")
            api.pull.update(state="closed", merged_at=DATE + "22Z", merged_by=dict(BOT), auto_merge=None)
            if mode == "retargeted":
                api.graph["transitions"]["nodes"].append({"createdAt": DATE + "20Z"})
            if mode == "reused-head":
                api.last_push.update(id=82, after=HEAD, pushed_at=DATE + "20Z")
            with self.subTest(mode=mode):
                if mode == "valid":
                    self.assertEqual(proof.observe_completion(api, REPO, api.pull, POLICY, TREE), BOT["login"])
                else:
                    with self.assertRaises(ValueError):
                        proof.observe_completion(api, REPO, api.pull, POLICY, TREE)

    def test_foreign_arm_and_manual_only_proposal_cannot_get_positive_proof(self):
        for foreign in (True, False):
            api = API()
            api.arm()
            if foreign:
                api.pull["auto_merge"]["enabled_by"] = dict(BOT, id=79)
            with patch("eligibility.verify_eligible", side_effect=ValueError("manual route")):
                with self.assertRaises(ValueError):
                    api.run_check()
            self.assertEqual(api.writes, ["in_progress", "failure"])
