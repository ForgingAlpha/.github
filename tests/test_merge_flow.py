import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class MergeFlowBehaviorTest(unittest.TestCase):
    def run_case(self, changes=None, api="present", verifier_status=1, mode=None):
        action_path = ROOT / "actions/ci-merge-flow"
        step = yaml.safe_load((action_path / "action.yml").read_text())["runs"]["steps"][0]
        context = {
            "github.token": "fixture-token",
            "github.event.pull_request.head.ref": "dev",
            "github.event.pull_request.head.repo.full_name": "ForgingAlpha/example",
            "github.event.pull_request.head.repo.id": "99",
            "github.event.pull_request.base.ref": "main",
            "github.event.pull_request.base.repo.full_name": "ForgingAlpha/example",
            "github.event.pull_request.base.repo.id": "99",
            "github.event.pull_request.number": "42",
        }
        # Resolve the actual wrapper environment mappings from fixture context.
        mapped = {key: context[value.removeprefix("${{ ").removesuffix(" }}")]
                  for key, value in step["env"].items()}
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            gh = tmp / "gh"
            gh.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$@" >> "$GH_LOG"\n'
                'case "$API_STATE" in\n'
                'present) echo "{}" ;;\n'
                'absent) echo "HTTP 404: Not Found" >&2; exit 1 ;;\n'
                'auth) echo "HTTP 401: Bad credentials" >&2; exit 1 ;;\n'
                'rate) echo "HTTP 429: Rate limit exceeded" >&2; exit 1 ;;\n'
                'outage) echo "HTTP 500: unavailable" >&2; exit 1 ;;\n'
                'esac\n'
            )
            gh.chmod(0o755)
            verifier = tmp / "python3"
            verifier.write_text(
                '#!/bin/sh\n[ -f "$1" ] || exit 97\n'
                'printf "%s\\n" "$@" >> "$VERIFIER_LOG"\nexit "$VERIFY_STATUS"\n'
            )
            verifier.chmod(0o755)
            env = {
                "PATH": f"{tmp}:{os.environ['PATH']}",
                "GITHUB_ACTION_PATH": str(action_path),
                "GITHUB_REPOSITORY": "ForgingAlpha/example", "GITHUB_REPOSITORY_ID": "99",
                "GH_LOG": str(tmp / "gh.log"), "VERIFIER_LOG": str(tmp / "verifier.log"),
                "API_STATE": api, "VERIFY_STATUS": str(verifier_status), **mapped,
                **(changes or {}),
            }
            env = {key: value for key, value in env.items() if value is not None}
            command = (["bash", "-c", step["run"]] if mode is None else
                       ["bash", str(action_path / "scripts/check_merge_flow.sh"), mode])
            result = subprocess.run(command, cwd=tmp, env=env, text=True,
                                    capture_output=True, timeout=10)
            calls = lambda name: (tmp / name).read_text().splitlines() if (tmp / name).exists() else []
            return result, calls("gh.log"), calls("verifier.log"), (tmp / "SENTINEL").exists()

    def run_guard(self, head_repository, base="main", dev_exists=True):
        result, _, verification, _ = self.run_case(
            {"HEAD_REPOSITORY": head_repository, "BASE_REF": base},
            api="present" if dev_exists else "absent",
        )
        return result, " ".join(verification)

    def test_same_repository_dev_can_target_main_or_staging(self):
        for base in ("main", "staging"):
            with self.subTest(base=base):
                result, verification = self.run_guard("ForgingAlpha/example", base)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(verification, "")

    def test_fork_dev_has_no_ordinary_dev_exemption(self):
        for base in ("main", "staging"):
            with self.subTest(base=base):
                result, verification = self.run_guard("contributor/example", base)
                self.assertNotEqual(result.returncode, 0)
                if base == "main":
                    self.assertIn("verify-ci-admission", verification)
                else:
                    self.assertEqual(verification, "")

    def test_main_only_repository_keeps_ordinary_feature_admission(self):
        result, _ = self.run_guard("contributor/example", dev_exists=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_declared_direct_staged_pairs_and_dev_preservation(self):
        helper = ROOT / "actions/ci-merge-flow/scripts/check_merge_flow.sh"
        for route, head, base, expected in [("direct","dev","main",0),("staged","dev","staging",0),("staged","staging","main",0),("staged","dev","main",1),("direct","main","dev",0),("staged","staging","dev",0),("unknown","dev","main",1),("direct","feature","staging",1)]:
            env = {**os.environ,"DECLARED_ROUTE":route,"HEAD_REF":head,"BASE_REF":base,"HEAD_REPOSITORY":"ForgingAlpha/example","GITHUB_REPOSITORY":"ForgingAlpha/example","PR_NUMBER":"42","GITHUB_ACTION_PATH":str(ROOT/"actions/ci-merge-flow")}
            result=subprocess.run(["bash",str(helper),"declared-route"],env=env,capture_output=True)
            with self.subTest(route=route,head=head,base=base):self.assertEqual(result.returncode==0,expected==0,result.stderr)

    def source_context(self, **changes):
        return {
            "GITHUB_REPOSITORY": "ForgingAlpha/.github", "GITHUB_REPOSITORY_ID": "1137664016",
            "BASE_REPOSITORY": "ForgingAlpha/.github", "BASE_REPOSITORY_ID": "1137664016",
            "HEAD_REPOSITORY": "ForgingAlpha/.github", "HEAD_REPOSITORY_ID": "1137664016",
            "HEAD_REF": "task/bridge", **changes,
        }

    def assert_source_result(self, changes, allowed, api="absent"):
        result, api_calls, verifier_calls, sentinel = self.run_case(changes, api=api)
        self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
        self.assertEqual(api_calls, [], "Source claims must not fall through to branch lookup")
        self.assertEqual(verifier_calls, [], "Ordinary source admission is not security classification")
        self.assertFalse(sentinel, "A ref was executed as shell source")

    def test_source_tasks_ignore_branch_topology_and_detection_errors(self):
        for api in ("present", "absent", "auth", "rate", "outage"):
            for repository, repo_id in (("ForgingAlpha/.github", "1137664016"),
                                        ("contributor-name/.github", "22")):
                with self.subTest(api=api, repository=repository):
                    self.assert_source_result(self.source_context(
                        HEAD_REPOSITORY=repository, HEAD_REPOSITORY_ID=repo_id), True, api)

    def test_source_refuses_persistent_heads_and_unsupported_targets(self):
        for repository, repo_id in (("ForgingAlpha/.github", "1137664016"), ("contributor/.github", "22")):
            for head in ("main", "dev", "staging"):
                with self.subTest(repository=repository, head=head):
                    self.assert_source_result(self.source_context(
                        HEAD_REPOSITORY=repository, HEAD_REPOSITORY_ID=repo_id, HEAD_REF=head), False)
        for target in ("dev", "staging", "unknown", "", None):
            with self.subTest(target=target):
                self.assert_source_result(self.source_context(BASE_REF=target), False)

    def test_each_runtime_or_base_claim_selects_strict_validation(self):
        # C2: a source base must not escape through another runtime's 404 exemption.
        fields = {
            "GITHUB_REPOSITORY": "ForgingAlpha/.github", "GITHUB_REPOSITORY_ID": "1137664016",
            "BASE_REPOSITORY": "ForgingAlpha/.github", "BASE_REPOSITORY_ID": "1137664016",
        }
        for field, value in fields.items():
            for target in ("main", "dev"):
                with self.subTest(field=field, target=target):
                    self.assert_source_result({field: value, "BASE_REF": target}, False)
        for field in ("GITHUB_REPOSITORY", "BASE_REPOSITORY"):
            with self.subTest(case_variant=field):
                self.assert_source_result({field: "forgingalpha/.github"}, False)
        for field in fields:
            for value in (None, "", "bad", "99", "Other/repository"):
                with self.subTest(field=field, value=value):
                    self.assert_source_result(self.source_context(**{field: value}), False)

    def test_source_requires_complete_consistent_head_and_pr_identity(self):
        for name in (None, "", "./..", "./repository", "owner/..", "owner/.",
                     "/repository", "owner/", "owner/repo/extra", "owner", "owner /repo",
                     "-owner/repo", "owner-/repo", "owner_underscore/repo"):
            with self.subTest(head_repository=name):
                self.assert_source_result(self.source_context(
                    HEAD_REPOSITORY=name, HEAD_REPOSITORY_ID="22"), False)
        for field in ("HEAD_REPOSITORY_ID", "PR_NUMBER"):
            for value in (None, "", "0", "-1", "1.0", "bad", "$(touch${IFS}SENTINEL)"):
                with self.subTest(field=field, value=value):
                    self.assert_source_result(self.source_context(**{field: value}), False)
        for name, repo_id in (("ForgingAlpha/.github", "22"), ("contributor/.github", "1137664016"),
                             ("forgingalpha/.github", "22")):
            with self.subTest(name=name, repo_id=repo_id):
                self.assert_source_result(self.source_context(
                    HEAD_REPOSITORY=name, HEAD_REPOSITORY_ID=repo_id), False)

    def test_source_refs_are_validated_as_data(self):
        for ref in (None, "", "bad ref", "../task", "task..bad", "@{-1}", "task.lock", "task\nnew"):
            with self.subTest(ref=ref):
                self.assert_source_result(self.source_context(HEAD_REF=ref), False)
        for ref in ("task/$(touch${IFS}SENTINEL)", "task/`touch${IFS}SENTINEL`",
                    "task/';touch${IFS}SENTINEL;#"):
            with self.subTest(ref=ref):
                self.assert_source_result(self.source_context(HEAD_REF=ref), True)

    def test_legacy_absence_errors_and_security_calls_are_distinct(self):
        for api, expected in (("absent", True), ("auth", False), ("rate", False), ("outage", False)):
            with self.subTest(api=api):
                result, api_calls, verifier_calls, _ = self.run_case({"HEAD_REF": "task/ordinary"}, api=api)
                self.assertEqual(result.returncode == 0, expected)
                self.assertEqual(api_calls, ["api", "repos/ForgingAlpha/example/branches/dev"])
                self.assertEqual(verifier_calls, [])
        for mode in (None, "declared-route"):
            for status in (0, 1):
                with self.subTest(mode=mode, status=status):
                    result, api_calls, verifier_calls, _ = self.run_case(
                        {"HEAD_REF": "task/ordinary", "DECLARED_ROUTE": "direct"},
                        verifier_status=status, mode=mode)
                    self.assertEqual(result.returncode == 0, status == 0)
                    self.assertEqual(bool(api_calls), mode is None)
                    self.assertEqual(verifier_calls, [
                        str(ROOT / "actions/ci-merge-flow/../security-patch/scripts/security_patch.py"),
                        "verify-ci-admission", "--repository", "ForgingAlpha/example",
                        "--pull-request", "42", "--target-branch", "main",
                    ])

    def test_declared_route_precedes_source_bridge_and_refuses_shortcuts(self):
        for route, head, target, allowed in (("direct", "dev", "main", True),
                                            ("staged", "dev", "main", False),
                                            ("staged", "staging", "main", True)):
            with self.subTest(route=route, head=head):
                result, api_calls, verifier_calls, _ = self.run_case(
                    self.source_context(DECLARED_ROUTE=route, HEAD_REF=head, BASE_REF=target),
                    mode="declared-route", verifier_status=0)
                self.assertEqual(result.returncode == 0, allowed)
                self.assertEqual(api_calls, [])
                self.assertEqual(verifier_calls, [])
        for mode in ("", "unknown", "source-bridge"):
            with self.subTest(mode=mode):
                result, api_calls, verifier_calls, _ = self.run_case(self.source_context(), mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(api_calls + verifier_calls, [])

    def test_wrapper_binds_context_and_schedules_all_source_claims(self):
        action = yaml.safe_load((ROOT / "actions/ci-merge-flow/action.yml").read_text())
        self.assertNotIn("inputs", action, "No caller-selected source exception")
        step = action["runs"]["steps"][0]
        expected_env = {
            "GH_TOKEN": "github.token", "HEAD_REF": "github.event.pull_request.head.ref",
            "HEAD_REPOSITORY": "github.event.pull_request.head.repo.full_name",
            "HEAD_REPOSITORY_ID": "github.event.pull_request.head.repo.id",
            "BASE_REPOSITORY": "github.event.pull_request.base.repo.full_name",
            "BASE_REPOSITORY_ID": "github.event.pull_request.base.repo.id",
            "BASE_REF": "github.event.pull_request.base.ref", "PR_NUMBER": "github.event.pull_request.number",
        }
        self.assertEqual(step["env"], {key: "${{ " + value + " }}" for key, value in expected_env.items()})
        self.assertEqual(step["run"], 'bash "$GITHUB_ACTION_PATH/scripts/check_merge_flow.sh" legacy-observed')
        self.assertEqual(" ".join(step["if"].split()), " ".join("""
            ${{ github.event_name == 'pull_request' &&
                (github.event.pull_request.base.ref == 'main' ||
                 github.event.pull_request.base.ref == 'staging' ||
                 github.repository == 'ForgingAlpha/.github' ||
                 github.repository_id == '1137664016' ||
                 github.event.pull_request.base.repo.full_name == 'ForgingAlpha/.github' ||
                 github.event.pull_request.base.repo.id == 1137664016) }}
        """.split()))
