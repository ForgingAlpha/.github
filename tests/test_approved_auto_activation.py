import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REUSABLE = ROOT / ".github" / "workflows" / "approved-automerge.yml"
CALLER = ROOT / ".github" / "workflows" / "approved-auto-activation.yml"


class ApprovedAutoActivationContractTest(unittest.TestCase):
    def load(self, path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_reusable_workflow_requires_protected_release_identity(self):
        workflow = self.load(REUSABLE)
        triggers = workflow.get("on", workflow.get(True))
        call = triggers["workflow_call"]
        self.assertTrue(call["inputs"]["release_app_id"]["required"])
        self.assertTrue(call["secrets"]["release_app_private_key"]["required"])

        text = REUSABLE.read_text(encoding="utf-8")
        self.assertIn("actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1", text)
        self.assertIn("permission-contents: write", text)
        self.assertIn("permission-pull-requests: write", text)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            workflow["jobs"]["activation"]["if"],
        )
        self.assertNotIn("--admin", text)

    def test_approval_is_bound_to_human_head_base_and_review(self):
        text = REUSABLE.read_text(encoding="utf-8")
        for required in (
            "github.event.review.user.login",
            "github.event.review.commit_id",
            "github.event.pull_request.base.sha",
            "github.event.review.id",
            ".head.repo.full_name",
            ".draft",
            "reviews/${EVENT_REVIEW_ID}",
            '.state == "APPROVED"',
            ".commit_id == $head",
            "git/ref/heads/${base_branch}",
            "--match-head-commit",
        ):
            self.assertIn(required, text)

    def test_only_declared_persistent_branches_are_eligible(self):
        workflow = self.load(REUSABLE)
        triggers = workflow.get("on", workflow.get(True))
        branch_input = triggers["workflow_call"]["inputs"]["persistent_branches"]
        self.assertTrue(branch_input["required"])
        text = REUSABLE.read_text(encoding="utf-8")
        self.assertIn('branch_allowed=false', text)
        self.assertIn('Target branch \'${base_branch}\' is not eligible', text)

    def test_exception_labels_and_changed_authority_disarm(self):
        workflow = self.load(REUSABLE)
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(
            triggers["workflow_call"]["inputs"]["hold_labels"]["default"],
            "hold-activation,no-merge",
        )
        text = REUSABLE.read_text(encoding="utf-8")
        for required in (
            "synchronize|converted_to_draft",
            "activation hold label was applied",
            "--disable-auto",
            "submit a fresh exact-revision approval",
        ):
            self.assertIn(required, text)

    def test_control_plane_caller_covers_approval_and_revocation_events(self):
        workflow = self.load(CALLER)
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(triggers["pull_request_review"]["types"], ["submitted", "dismissed"])
        self.assertEqual(
            triggers["pull_request_target"]["types"],
            ["synchronize", "converted_to_draft", "labeled"],
        )
        job = workflow["jobs"]["activate"]
        self.assertEqual(job["uses"], "./.github/workflows/approved-automerge.yml")
        self.assertEqual(job["with"]["persistent_branches"], "main")
        self.assertEqual(job["with"]["authorized_approver"], "leosmigel")


class ApprovedAutoActivationBehaviorTest(unittest.TestCase):
    HEAD = "a" * 40
    BASE = "b" * 40

    def setUp(self):
        workflow = yaml.safe_load(REUSABLE.read_text(encoding="utf-8"))
        self.script = next(
            step["run"]
            for step in workflow["jobs"]["activation"]["steps"]
            if step["name"] == "Revalidate exact approval and activate"
        )

    def run_activation(
        self,
        *,
        event_head=None,
        event_base=None,
        current_head=None,
        current_base=None,
        review_state="APPROVED",
        labels=None,
        head_repo="ForgingAlpha/example",
        draft=False,
    ):
        event_head = event_head or self.HEAD
        event_base = event_base or self.BASE
        current_head = current_head or self.HEAD
        current_base = current_base or self.BASE
        labels = labels or []

        pr = {
            "state": "open",
            "draft": draft,
            "head": {"sha": current_head, "repo": {"full_name": head_repo}},
            "base": {"ref": "dev", "sha": current_base},
            "labels": [{"name": label} for label in labels],
        }
        review = {
            "user": {"login": "leosmigel"},
            "state": review_state,
            "commit_id": current_head,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_gh = Path(temp_dir) / "gh"
            calls = Path(temp_dir) / "calls"
            summary = Path(temp_dir) / "summary"
            fake_gh.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
calls = os.environ["FAKE_GH_CALLS"]
with open(calls, "a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\\n")

if args[:1] == ["api"]:
    endpoint = args[1]
    if "/pulls/7/reviews/44" in endpoint:
        print(os.environ["FAKE_REVIEW_JSON"])
    elif "/pulls/7" in endpoint:
        print(os.environ["FAKE_PR_JSON"])
    elif "/git/ref/heads/dev" in endpoint:
        print(os.environ["FAKE_CURRENT_BASE"])
    else:
        raise SystemExit(f"unexpected api call: {args}")
elif args[:2] == ["pr", "view"]:
    joined = " ".join(args)
    if "--json autoMergeRequest" in joined:
        print("false")
    elif "--json headRefOid" in joined:
        print(os.environ["FAKE_CURRENT_HEAD"])
    elif "--json state,headRefOid,autoMergeRequest" in joined:
        print(json.dumps({
            "state": "OPEN",
            "headRefOid": os.environ["FAKE_CURRENT_HEAD"],
            "autoMergeRequest": {"mergeMethod": "MERGE"},
        }))
    else:
        raise SystemExit(f"unexpected pr view: {args}")
elif args[:2] == ["pr", "merge"]:
    if "--admin" in args:
        raise SystemExit("admin bypass forbidden")
else:
    raise SystemExit(f"unexpected gh call: {args}")
""",
                encoding="utf-8",
            )
            fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env.update(
                {
                    "AUTHORIZED_APPROVER": "leosmigel",
                    "EVENT_BASE_SHA": event_base,
                    "EVENT_HEAD_SHA": event_head,
                    "EVENT_REVIEW_ID": "44",
                    "FAKE_CURRENT_BASE": current_base,
                    "FAKE_CURRENT_HEAD": current_head,
                    "FAKE_GH_CALLS": str(calls),
                    "FAKE_PR_JSON": json.dumps(pr),
                    "FAKE_REVIEW_JSON": json.dumps(review),
                    "GH_TOKEN": "test-token",
                    "GITHUB_REPOSITORY": "ForgingAlpha/example",
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "HOLD_LABELS": "hold-activation,no-merge",
                    "MERGE_METHOD": "merge",
                    "PATH": f"{temp_dir}:{env['PATH']}",
                    "PERSISTENT_BRANCHES": "dev,main",
                    "PR_NUMBER": "7",
                }
            )
            result = subprocess.run(
                ["bash", "-c", self.script],
                check=False,
                capture_output=True,
                env=env,
                text=True,
            )
            call_text = calls.read_text(encoding="utf-8") if calls.exists() else ""
            return result, call_text

    def test_valid_exact_approval_arms_without_admin_bypass(self):
        result, calls = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pr merge 7", calls)
        self.assertIn("--auto", calls)
        self.assertIn(f"--match-head-commit {self.HEAD}", calls)
        self.assertNotIn("--admin", calls)

    def test_changed_head_fails_before_merge(self):
        result, calls = self.run_activation(current_head="c" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("head moved after approval", result.stderr)
        self.assertNotIn("pr merge", calls)

    def test_changed_target_fails_before_merge(self):
        result, calls = self.run_activation(current_base="d" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Target branch moved after approval", result.stderr)
        self.assertNotIn("pr merge", calls)

    def test_hold_requires_fresh_approval(self):
        result, calls = self.run_activation(labels=["hold-activation"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Activation is suspended", result.stderr)
        self.assertIn("fresh exact-revision approval", result.stderr)
        self.assertNotIn("pr merge", calls)

    def test_dismissed_review_fails_before_merge(self):
        result, calls = self.run_activation(review_state="DISMISSED")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approval is no longer valid", result.stderr)
        self.assertNotIn("pr merge", calls)


if __name__ == "__main__":
    unittest.main()
