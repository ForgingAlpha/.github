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
SIGNAL = ROOT / ".github" / "workflows" / "approval-signal.yml"


class ApprovedAutoActivationContractTest(unittest.TestCase):
    def load(self, path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_privilege_is_separated_from_pull_request_code(self):
        signal = self.load(SIGNAL)
        signal_triggers = signal.get("on", signal.get(True))
        self.assertEqual(signal_triggers["pull_request_review"]["types"], ["submitted"])
        self.assertEqual(signal["permissions"], {})

        caller = self.load(CALLER)
        caller_triggers = caller.get("on", caller.get(True))
        self.assertEqual(caller_triggers["workflow_run"]["workflows"], ["Approval Signal"])
        self.assertEqual(caller_triggers["workflow_run"]["types"], ["completed"])

        combined = SIGNAL.read_text(encoding="utf-8") + CALLER.read_text(encoding="utf-8")
        self.assertNotIn("pull_request_target", combined)
        self.assertNotIn("actions/checkout", combined)
        self.assertNotIn("release_app_private_key", SIGNAL.read_text(encoding="utf-8"))

    def test_reusable_requires_protected_release_identity(self):
        workflow = self.load(REUSABLE)
        triggers = workflow.get("on", workflow.get(True))
        call = triggers["workflow_call"]
        self.assertNotIn("release_app_client_id", call["inputs"])
        self.assertTrue(call["inputs"]["pull_request_number"]["required"])
        self.assertEqual(
            call["inputs"]["release_environment"]["default"],
            "release-automation",
        )
        self.assertNotIn("secrets", call)
        environment = workflow["jobs"]["activation"]["environment"]
        self.assertEqual(environment["name"], "${{ inputs.release_environment }}")
        self.assertFalse(environment["deployment"])

        text = REUSABLE.read_text(encoding="utf-8")
        self.assertIn("actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1", text)
        self.assertIn(
            "client-id: ${{ vars.FORGINGALPHA_RELEASE_APP_CLIENT_ID }}",
            text,
        )
        self.assertIn(
            "private-key: ${{ secrets.FORGINGALPHA_RELEASE_APP_PRIVATE_KEY }}",
            text,
        )
        self.assertNotIn("app-id:", text)
        self.assertIn("permission-contents: write", text)
        self.assertIn("permission-pull-requests: write", text)
        self.assertNotIn("owner:", text)
        self.assertNotIn("repositories:", text)
        self.assertNotIn("--admin", text)
        self.assertNotIn("actions/checkout", text)

    def test_privileged_run_revalidates_event_and_current_exact_approval(self):
        workflow = self.load(REUSABLE)
        job_if = workflow["jobs"]["activation"]["if"]
        for required in (
            "github.event_name == 'workflow_run'",
            "workflow_run.event == 'pull_request_review'",
            "workflow_run.conclusion == 'success'",
            "workflow_run.head_repository.full_name == github.repository",
        ):
            self.assertIn(required, job_if)

        text = REUSABLE.read_text(encoding="utf-8")
        for required in (
            ".head.repo.full_name",
            ".draft",
            "reviews?per_page=100",
            "max_by(.id)",
            '.state == "APPROVED"',
            ".commit_id == $head",
            "--match-head-commit",
        ):
            self.assertIn(required, text)

    def test_only_declared_persistent_branches_are_eligible(self):
        workflow = self.load(REUSABLE)
        triggers = workflow.get("on", workflow.get(True))
        branch_input = triggers["workflow_call"]["inputs"]["persistent_branches"]
        self.assertTrue(branch_input["required"])
        text = REUSABLE.read_text(encoding="utf-8")
        self.assertIn("branch_allowed=false", text)
        self.assertIn("Target branch '${base_branch}' is not eligible", text)

    def test_caller_passes_passive_pr_number_and_control_plane_branch(self):
        workflow = self.load(CALLER)
        job = workflow["jobs"]["activate"]
        self.assertEqual(job["uses"], "./.github/workflows/approved-automerge.yml")
        self.assertEqual(job["with"]["persistent_branches"], "main")
        self.assertEqual(job["with"]["authorized_approver"], "leosmigel")
        self.assertIn(
            "github.event.workflow_run.pull_requests[0].number",
            job["with"]["pull_request_number"],
        )


class ApprovedAutoActivationBehaviorTest(unittest.TestCase):
    HEAD = "a" * 40

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
        current_head=None,
        approved_head=None,
        latest_state="APPROVED",
        head_repo="ForgingAlpha/example",
        draft=False,
        base_branch="dev",
    ):
        current_head = current_head or self.HEAD
        approved_head = approved_head or self.HEAD

        pr = {
            "state": "open",
            "draft": draft,
            "head": {"sha": current_head, "repo": {"full_name": head_repo}},
            "base": {"ref": base_branch, "sha": "b" * 40},
        }
        reviews = [[
            {
                "id": 40,
                "user": {"login": "leosmigel"},
                "state": "COMMENTED",
                "commit_id": approved_head,
            },
            {
                "id": 44,
                "user": {"login": "leosmigel"},
                "state": latest_state,
                "commit_id": approved_head,
            },
        ]]

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
with open(os.environ["FAKE_GH_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\\n")

if args[:1] == ["api"]:
    endpoint = args[-1]
    if "/pulls/7/reviews?per_page=100" in endpoint:
        print(os.environ["FAKE_REVIEWS_JSON"])
    elif "/pulls/7" in endpoint:
        print(os.environ["FAKE_PR_JSON"])
    else:
        raise SystemExit(f"unexpected api call: {args}")
elif args[:2] == ["pr", "view"]:
    joined = " ".join(args)
    if "--json headRefOid" in joined:
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
                    "FAKE_CURRENT_HEAD": current_head,
                    "FAKE_GH_CALLS": str(calls),
                    "FAKE_PR_JSON": json.dumps(pr),
                    "FAKE_REVIEWS_JSON": json.dumps(reviews),
                    "GH_TOKEN": "test-token",
                    "GITHUB_REPOSITORY": "ForgingAlpha/example",
                    "GITHUB_STEP_SUMMARY": str(summary),
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

    def test_valid_exact_approval_arms_native_auto_merge_without_bypass(self):
        result, calls = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pr merge 7", calls)
        self.assertIn("--auto", calls)
        self.assertIn(f"--match-head-commit {self.HEAD}", calls)
        self.assertNotIn("--admin", calls)

    def test_changed_head_fails_before_merge(self):
        result, calls = self.run_activation(current_head="c" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact-head human approval is absent", result.stderr)
        self.assertNotIn("pr merge", calls)

    def test_latest_change_request_fails_before_merge(self):
        result, calls = self.run_activation(latest_state="CHANGES_REQUESTED")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact-head human approval is absent", result.stderr)
        self.assertNotIn("pr merge", calls)

    def test_draft_fails_before_merge(self):
        result, calls = self.run_activation(draft=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Pull request is a draft", result.stderr)
        self.assertNotIn("pr merge", calls)

    def test_undeclared_branch_fails_before_merge(self):
        result, calls = self.run_activation(base_branch="staging")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not eligible", result.stderr)
        self.assertNotIn("pr merge", calls)


if __name__ == "__main__":
    unittest.main()
