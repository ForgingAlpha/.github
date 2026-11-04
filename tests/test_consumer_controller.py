"""Credential-free controller contracts using synthetic identities and commands."""

import copy
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("consumer_controller", ROOT / "scripts/consumer_compatibility.py")
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)
NOW = dt.datetime(2026, 11, 3, 12, tzinfo=dt.timezone.utc)
HEAD, TREE = "a" * 40, "b" * 40


def grant():
    return {
        "schema": 1, "grant_id": "synthetic-grant", "enrollment_id": "synthetic-resource",
        "principal": "synthetic-principal", "trust_domain": "synthetic-domain",
        "decision_evidence": "synthetic-human-decision", "grant_sha256": "c" * 64,
        "enrollment_sha256": "d" * 64, "reporting_app_id": 123, "fixture_app_id": 124, "fixture_bot_id": 456,
        "shared_repository_id": 1137664016, "consumer_repository_id": 1428636846,
        "environment": "consumer-compatibility", "caller_ref": "refs/heads/dev",
        "purpose": "shared-ci-foundation-qualification",
        "actions": ["read-approved-shared-candidate", "execute-private-fixture", "publish-public-result", "close-owned-fixture"],
        "conditions": ["exact-head-human-review", "foundation-read-entitlement", "no-controller-secret-in-fixture", "human-only-merge"],
        "not_before": "2026-11-03T00:00:00Z", "expires_at": "2026-11-04T00:00:00Z",
    }


def public_pr():
    return {"number": 7, "state": "open", "draft": False,
            "head": {"sha": HEAD, "repo": {"id": 1137664016}},
            "base": {"ref": "main", "repo": {"id": 1137664016}}}


def approval():
    return {"id": 17, "state": "APPROVED", "commit_id": HEAD,
            "user": {"id": 19, "login": "synthetic-reviewer", "type": "User"}}


def permission(login):
    return {"permission": "read", "user": {"id": 19, "type": "User"}}


def native():
    branch = "test/shared-ci-" + "e" * 48
    pr = {"number": 8, "head": {"sha": HEAD, "ref": branch, "repo": {"id": 1428636846}},
          "base": {"ref": "dev", "repo": {"id": 1428636846}}}
    run = {"id": 71, "run_attempt": 1, "check_suite_id": 72, "event": "pull_request",
           "path": ".github/workflows/shared-candidate.yml", "head_sha": HEAD,
           "head_branch": branch, "repository": {"id": 1428636846},
           "head_repository": {"id": 1428636846}, "pull_requests": [],
           "status": "completed", "conclusion": "success"}
    steps = [{"name": name, "status": "completed", "conclusion": "success", "number": i}
             for i, name in enumerate(["Set up job", "Synthetic product check", "Synthetic evaluator",
                                       "Post Synthetic checkout", "Complete job"], 1)]
    job = {"id": 73, "run_id": 71, "run_attempt": 1, "head_sha": HEAD, "name": "Synthetic compatibility",
           "status": "completed", "conclusion": "success", "steps": steps,
           "check_run_url": "https://api.github.com/repos/ForgingAlpha/container-foundation/check-runs/73"}
    check = {"id": 73, "app": {"id": 15368}, "head_sha": HEAD, "check_suite": {"id": 72},
             "name": job["name"], "status": "completed", "conclusion": "success"}
    return [run, [job], [check], pr, run["path"], branch,
            ["Synthetic product check", "Synthetic evaluator"], job["name"]]


class AuthorityTests(unittest.TestCase):
    def test_exact_closed_current_projection(self):
        expected = grant()
        self.assertEqual(controller.authorization(json.dumps(expected), NOW), expected)
        for permission_name in ("merge", "update-main", "administration"):
            value = grant()
            value["actions"].append(permission_name)
            with self.subTest(permission=permission_name), self.assertRaises(controller.Refusal):
                controller.authorization(json.dumps(value), NOW)

    def test_missing_extra_wrong_and_expired_records_refuse(self):
        mutations = [
            lambda g: g.pop("grant_id"), lambda g: g.update(active=True),
            lambda g: g.update(schema=True), lambda g: g.update(reporting_app_id=True),
            lambda g: g.update(fixture_bot_id=0), lambda g: g.update(caller_ref="refs/heads/main"),
            lambda g: g.update(fixture_app_id=123), lambda g: g.update(fixture_app_id=True),
            lambda g: g.update(consumer_repository_id=99), lambda g: g.update(shared_repository_id=99),
            lambda g: g.update(not_before="2026-11-03T13:00:00Z"),
            lambda g: g.update(expires_at="2026-11-03T12:00:00Z"),
            lambda g: g.update(expires_at="2026-99-99T00:00:00Z"),
            lambda g: g.update(grant_sha256="unverified"), lambda g: g.update(conditions=[]),
            lambda g: g.update(environment="unguarded"),
        ]
        for i, change in enumerate(mutations):
            value = grant(); change(value)
            with self.subTest(case=i), self.assertRaises(controller.Refusal):
                controller.authorization(json.dumps(value), NOW)

    def test_duplicate_authority_field_refuses(self):
        with self.assertRaises(controller.Refusal):
            controller.authorization('{"app_id":123,"app_id":999}', NOW)

    def test_caller_and_defining_source_cannot_be_substituted(self):
        env = {"GITHUB_REPOSITORY": "ForgingAlpha/container-foundation", "GITHUB_REPOSITORY_ID": "1428636846",
               "GITHUB_REF": "refs/heads/dev", "GITHUB_EVENT_NAME": "schedule",
               "CC_WORKFLOW_REPOSITORY": "ForgingAlpha/.github", "CC_WORKFLOW_SHA": HEAD,
               "CC_WORKFLOW_REF": "ForgingAlpha/.github/.github/workflows/consumer-compatibility-controller.yml@refs/heads/main"}
        self.assertEqual(controller.runtime_context(env), HEAD)
        for key, value in [("GITHUB_REF", "refs/heads/test/pilot"), ("GITHUB_EVENT_NAME", "pull_request_target"),
                           ("GITHUB_REPOSITORY_ID", "99"), ("CC_WORKFLOW_REPOSITORY", "ForgingAlpha/container-foundation"),
                           ("CC_WORKFLOW_REF", env["CC_WORKFLOW_REF"].replace("main", "candidate")),
                           ("CC_WORKFLOW_SHA", "main")]:
            with self.subTest(field=key), self.assertRaises(controller.Refusal):
                controller.runtime_context({**env, key: value})


class AdmissionTests(unittest.TestCase):
    def test_existing_effective_human_approval_with_private_access(self):
        self.assertEqual(controller.eligible(public_pr(), [approval()], permission, "APPROVED"), 19)

    def test_fork_draft_closed_wrong_route_and_missing_approval_refuse(self):
        mutations = [lambda p: p.update(draft=True), lambda p: p.update(state="closed"),
                     lambda p: p["head"]["repo"].update(id=99), lambda p: p["base"]["repo"].update(id=99),
                     lambda p: p["base"].update(ref="dev")]
        for i, change in enumerate(mutations):
            pr = public_pr(); change(pr)
            access = Mock(side_effect=permission)
            with self.subTest(case=i), self.assertRaises(controller.Refusal):
                controller.eligible(pr, [approval()], access, "APPROVED")
            access.assert_not_called()
        for decision in (None, "REVIEW_REQUIRED", "CHANGES_REQUESTED"):
            with self.subTest(decision=decision), self.assertRaises(controller.Refusal):
                controller.eligible(public_pr(), [approval()], permission, decision)

    def test_dismissed_stale_bot_and_changed_effective_review_refuse(self):
        for state in ("DISMISSED", "CHANGES_REQUESTED", "PENDING"):
            changed = {**approval(), "id": 18, "state": state}
            with self.subTest(state=state), self.assertRaises(controller.Refusal):
                controller.eligible(public_pr(), [approval(), changed], permission, "APPROVED")
        for change in (lambda r: r.update(commit_id=TREE), lambda r: r["user"].update(type="Bot")):
            review = approval(); change(review)
            with self.assertRaises(controller.Refusal):
                controller.eligible(public_pr(), [review], permission, "APPROVED")

    def test_comment_does_not_erase_an_effective_approval(self):
        comment = {**approval(), "id": 18, "state": "COMMENTED"}
        self.assertEqual(controller.eligible(public_pr(), [approval(), comment], permission, "APPROVED"), 19)

    def test_entitlement_must_bind_same_human(self):
        for access in ({"permission": "none", "user": {"id": 19, "type": "User"}},
                       {"permission": "admin", "user": {"id": 20, "type": "User"}},
                       {"permission": "admin", "user": {"id": 19, "type": "Bot"}}, {}):
            with self.subTest(access=access), self.assertRaises(controller.Refusal):
                controller.eligible(public_pr(), [approval()], lambda _: access, "APPROVED")


class EvidenceTests(unittest.TestCase):
    def test_plan_binds_every_selected_input_and_bounded_branch(self):
        args = [7, "a" * 40, "b" * 40, "c" * 40, "d" * 40, "e" * 40, "f" * 40]
        original = controller.plan(*args)
        self.assertEqual(original, controller.plan(*args))
        self.assertRegex(original[2], r"^test/shared-ci-[0-9a-f]{48}$")
        for i in range(len(args)):
            changed = args.copy(); changed[i] = 8 if i == 0 else "1" * 40
            self.assertNotEqual(original[1], controller.plan(*changed)[1])

    def test_public_output_never_uses_private_plan_details(self):
        result = controller.check_payload(HEAD, "e" * 64, "completed", "success", 8)
        self.assertEqual(set(result), {"name", "head_sha", "external_id", "status", "conclusion", "details_url", "output"})
        self.assertEqual(result["details_url"], "https://github.com/ForgingAlpha/container-foundation/pull/8")
        self.assertNotIn("consumer_commit", json.dumps(result))
        for conclusion in ("neutral", "skipped", "stale", None):
            with self.subTest(conclusion=conclusion), self.assertRaises(controller.Refusal):
                controller.check_payload(HEAD, "e" * 64, "completed", conclusion)
        for conclusion in ("failure", "action_required", "cancelled", "timed_out"):
            self.assertEqual(controller.check_payload(HEAD, "e" * 64, "completed", conclusion)["conclusion"], conclusion)

    def test_empty_native_pr_array_requires_independent_full_binding(self):
        self.assertTrue(controller.native_success(*native()))
        value = native()
        value[0]["pull_requests"] = [{"number": 8, "head": value[3]["head"], "base": value[3]["base"]}]
        self.assertTrue(controller.native_success(*value))
        value[0]["pull_requests"][0]["number"] = 9
        with self.assertRaises(controller.Refusal):
            controller.native_success(*value)

    def test_wrong_run_head_branch_event_repo_or_attempt_refuses(self):
        mutations = [lambda x: x[0].update(head_sha=TREE), lambda x: x[0].update(head_branch="test/unrelated"),
                     lambda x: x[0].update(event="workflow_dispatch"), lambda x: x[0]["repository"].update(id=99),
                     lambda x: x[0]["head_repository"].update(id=99), lambda x: x[0].update(path=".github/workflows/other.yml"),
                     lambda x: x[1][0].update(run_attempt=2), lambda x: x[1][0].update(run_id=99),
                     lambda x: x[3]["base"]["repo"].update(id=99), lambda x: x[3]["base"].update(ref="main")]
        for i, change in enumerate(mutations):
            value = native(); change(value)
            with self.subTest(case=i), self.assertRaises(controller.Refusal):
                controller.native_success(*value)

    def test_wrong_issuer_suite_missing_job_and_failed_post_hook_refuse(self):
        mutations = [lambda x: x[2][0]["app"].update(id=99), lambda x: x[2][0]["check_suite"].update(id=99),
                     lambda x: x[1].clear(), lambda x: x[1].append(copy.deepcopy(x[1][0])),
                     lambda x: x[1][0]["steps"][-2].update(conclusion="failure"),
                     lambda x: x[1][0]["steps"].pop(2), lambda x: x[1][0]["steps"][1].update(conclusion="skipped"),
                     lambda x: x[0].update(conclusion="failure")]
        for i, change in enumerate(mutations):
            value = native(); change(value)
            with self.subTest(case=i), self.assertRaises(controller.Refusal):
                controller.native_success(*value)

    def test_pending_run_is_not_success(self):
        value = native(); value[0].update(status="in_progress", conclusion=None)
        self.assertFalse(controller.native_success(*value))

    def test_duplicate_associations_steps_and_unexplained_reruns_refuse(self):
        value = native()
        item = {"number": 8, "head": value[3]["head"], "base": value[3]["base"]}
        value[0]["pull_requests"] = [item, copy.deepcopy(item)]
        with self.assertRaises(controller.Refusal):
            controller.native_success(*value)
        value = native()
        value[1][0]["steps"][1]["number"] = value[1][0]["steps"][0]["number"]
        with self.assertRaises(controller.Refusal):
            controller.native_success(*value)
        value = native()
        value[0]["run_attempt"] = value[1][0]["run_attempt"] = 2
        with self.assertRaises(controller.Refusal):
            controller.native_success(*value)


class TransportTests(unittest.TestCase):
    def fake_api(self, repository):
        api = controller.API(repository, "synthetic-not-a-credential")
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"id":1}'
        api.opener = Mock()
        api.opener.open.return_value = response
        return api

    def test_reporter_can_create_and_update_only_checks(self):
        api = self.fake_api(controller.SHARED)
        self.assertEqual(api.request("/check-runs", "POST", {"name": "synthetic"}), {"id": 1})
        self.assertEqual(api.request("/check-runs/1", "PATCH", {"status": "in_progress"}), {"id": 1})
        for method, path, body in [("POST", "/pulls", {}), ("POST", "/git/refs", {}),
                                   ("PUT", "/pulls/1/merge", {}), ("POST", "/actions/runs/1/rerun", {})]:
            api.opener.reset_mock()
            with self.subTest(path=path), self.assertRaises(controller.Refusal):
                api.request(path, method, body)
            api.opener.open.assert_not_called()

    def test_fixture_ref_is_exact_disposable_family_and_never_updated(self):
        api = self.fake_api(controller.CONSUMER)
        self.assertEqual(api.request("/git/refs", "POST", {"ref": "refs/heads/test/shared-ci-" + "e" * 48, "sha": HEAD}), {"id": 1})
        for ref in ("refs/heads/main", "refs/heads/dev", "refs/heads/test/shared-ci-pr91-20261103", "refs/heads/test/shared-ci-abc"):
            api.opener.reset_mock()
            with self.subTest(ref=ref), self.assertRaises(controller.Refusal):
                api.request("/git/refs", "POST", {"ref": ref, "sha": HEAD})
            api.opener.open.assert_not_called()
        with self.assertRaises(controller.Refusal):
            api.request("/git/refs/heads/test/shared-ci-" + "e" * 48, "PATCH", {"sha": HEAD, "force": True})

    def test_redirects_never_receive_credentials(self):
        with self.assertRaises(controller.Refusal):
            controller.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.invalid")

    def test_paginated_inventory_is_complete_or_refuses(self):
        api = controller.API(controller.SHARED, "synthetic")
        api.request = Mock(side_effect=[[{"id": n} for n in range(1, 101)], [{"id": 101}]])
        self.assertEqual(len(api.listing("/pulls", limit=101)), 101)
        api.request = Mock(side_effect=[[{}] * 100, [{}]])
        with self.assertRaises(controller.Refusal):
            api.listing("/pulls", limit=100)
        api.request = Mock(return_value={"workflow_runs": [], "total_count": 1})
        with self.assertRaises(controller.Refusal):
            api.listing("/actions/runs", "workflow_runs")

    def test_duplicate_pages_and_nonfinite_json_refuse(self):
        api = controller.API(controller.SHARED, "synthetic")
        api.request = Mock(side_effect=[[{"id": n} for n in range(1, 101)], [{"id": 1}]])
        with self.assertRaises(controller.Refusal):
            api.listing("/pulls")
        for raw in ('{"value":NaN}', '{"value":Infinity}', '{"id":1,"id":2}'):
            with self.subTest(raw=raw), self.assertRaises(controller.Refusal):
                controller.decode(raw)


class ReconciliationTests(unittest.TestCase):
    """State transitions; these fakes establish no hosted API behavior."""

    def state(self):
        c = controller.Controller.__new__(controller.Controller)
        c.shared, c.consumer = Mock(), Mock()
        c.grant = grant()
        c.grant_raw = json.dumps({**grant(), "not_before": "1970-01-01T00:00:00Z", "expires_at": "2999-01-01T00:00:00Z"})
        value, identity, branch = controller.plan(7, HEAD, TREE, "c" * 40, "d" * 40, "e" * 40, "f" * 40)
        pr = {"number": 8, "state": "open", "head": {"sha": "1" * 40}}
        c.current = Mock(return_value=value["consumer_commit"])
        c.admit = Mock(return_value=public_pr())
        c.material = Mock(return_value=(value, identity, branch, "synthetic workflow", {}, {}, False))
        c.fixture = Mock(return_value=pr)
        c.verify_pr = Mock()
        c.observe = Mock(return_value=True)
        c.consumer.request.return_value = pr
        c.consumer.branch.return_value = pr["head"]["sha"]
        c.owned_check = Mock(return_value={"external_id": identity, "status": "completed", "conclusion": "success"})
        c.report = Mock()
        return c, identity

    def test_unchanged_success_does_not_become_pending_during_sweep(self):
        c, identity = self.state()
        c.reconcile(public_pr())
        c.report.assert_called_once_with(HEAD, identity, "completed", "success", 8)
        self.assertEqual(c.observe.call_count, 4)
        self.assertEqual(c.admit.call_count, 3)

    def test_changed_plan_invalidates_before_any_publication(self):
        c, identity = self.state()
        c.owned_check.return_value["external_id"] = "0" * 64
        order = []
        c.report.side_effect = lambda *args, **kwargs: order.append(("report", args[2]))
        pr = c.fixture.return_value
        c.fixture.side_effect = lambda *args: order.append(("fixture", None)) or pr
        c.reconcile(public_pr())
        self.assertEqual(order, [("report", "in_progress"), ("fixture", None), ("report", "completed")])

    def test_revoked_review_is_queued_without_execution_or_operational_failure(self):
        c, _ = self.state()
        c.admit.side_effect = controller.Pending("review revoked")
        c.reconcile(public_pr())
        c.fixture.assert_not_called()
        self.assertEqual(c.report.call_args.args[2:], ("queued",))

    def test_missing_native_evidence_clears_existing_green(self):
        c, identity = self.state()
        c.observe.return_value = False
        c.reconcile(public_pr())
        c.report.assert_called_once_with(HEAD, identity, "in_progress", number=8)

    def test_native_failure_clears_green_without_rerun(self):
        c, identity = self.state()
        c.observe.side_effect = controller.NativeFailure("failed")
        c.reconcile(public_pr())
        c.report.assert_called_once_with(HEAD, identity, "completed", "failure")

    def test_selection_movement_and_unknown_create_cannot_publish_success(self):
        for failure in ("base moved", "unknown create"):
            c, identity = self.state()
            if failure == "base moved":
                c.current.side_effect = ["c" * 40, "9" * 40]
            else:
                c.fixture.side_effect = controller.Refusal("unknown write")
            with self.subTest(failure=failure), self.assertRaises(controller.Refusal):
                c.reconcile(public_pr())
            c.report.assert_called_once_with(HEAD, identity, "completed", "action_required")

    def test_exact_current_report_is_reused_without_a_write(self):
        c, identity = self.state()
        del c.report
        payload = controller.check_payload(HEAD, identity, "completed", "success", 8)
        payload["output"].update(text=None, annotations_count=0, annotations_url="https://api.github.com/synthetic-annotations")
        c.owned_check.return_value = {**payload, "id": 90, "app": {"id": 123}}
        self.assertEqual(c.report(HEAD, identity, "completed", "success", 8)["id"], 90)
        c.shared.request.assert_not_called()

    def test_public_write_requires_exact_readback(self):
        c, identity = self.state()
        del c.report
        c.owned_check.return_value = None
        good = {**controller.check_payload(HEAD, identity, "completed", "success", 8), "id": 90, "app": {"id": 123}}
        for field, bad in (("head_sha", TREE), ("external_id", "0" * 64), ("app", {"id": 99}),
                           ("status", "queued"), ("conclusion", "failure")):
            c.shared.request.side_effect = [{"id": 90}, {**good, field: bad}]
            with self.subTest(field=field), self.assertRaises(controller.Refusal):
                c.report(HEAD, identity, "completed", "success", 8)

    def test_recreated_repository_name_does_not_reuse_old_resource_authority(self):
        c, _ = self.state()
        del c.current
        c.harness = "e" * 40
        c.shared.repo, c.consumer.repo = controller.SHARED, controller.CONSUMER
        c.shared.request.return_value = {"id": 1137664016, "full_name": controller.SHARED}
        c.consumer.request.return_value = {"id": 1428636846, "full_name": controller.CONSUMER}
        c.shared.branch.return_value = c.harness
        c.consumer.branch.return_value = "c" * 40
        self.assertEqual(c.current(), "c" * 40)
        for api in (c.shared, c.consumer):
            original = copy.deepcopy(api.request.return_value)
            api.request.return_value["id"] = 99
            with self.assertRaises(controller.Refusal):
                c.current()
            with self.assertRaises(controller.Refusal):
                c.mutation_authorized(api, 1137664016 if api is c.shared else 1428636846)
            api.request.return_value = original


class ReviewRecoveryTests(unittest.TestCase):
    def test_second_run_id_cannot_erase_earlier_failed_execution(self):
        c, _ = ReconciliationTests().state()
        del c.observe
        c.consumer.listing.return_value = [{"id": 1, "conclusion": "failure"},
                                           {"id": 2, "run_attempt": 1, "conclusion": "success"}]
        with self.assertRaises(controller.Refusal):
            c.observe(c.fixture.return_value, "test/shared-ci-" + "a" * 48, controller.WORKFLOW, {})
        c.consumer.request.assert_not_called()

    def test_local_io_failure_after_input_movement_writes_blocker(self):
        c, _ = ReconciliationTests().state()
        c.current.return_value = "9" * 40
        c.material.side_effect = OSError(28, "synthetic disk full")
        with self.assertRaises(OSError):
            c.reconcile(public_pr())
        self.assertEqual(c.report.call_args.args[2:], ("completed", "action_required"))
        c.fixture.assert_not_called()

    def test_duplicate_owned_successes_are_both_invalidated(self):
        c, identity = ReconciliationTests().state()
        del c.owned_check
        checks = [{**controller.check_payload(HEAD, identity, "completed", "success"),
                   "id": i, "app": {"id": 123}} for i in (71, 72)]
        c.shared.listing.side_effect = lambda *a: copy.deepcopy(checks)
        def request(path, method="GET", payload=None):
            check = next(x for x in checks if path.endswith("/" + str(x["id"])))
            if method == "PATCH": check.update(payload)
            return copy.deepcopy(check)
        c.shared.request.side_effect = request
        with self.assertRaises(controller.Refusal): c.owned_check(HEAD)
        self.assertEqual([x["conclusion"] for x in checks], ["action_required"] * 2)
        count = c.shared.request.call_count
        with self.assertRaises(controller.Refusal): c.owned_check(HEAD)
        self.assertEqual(c.shared.request.call_count, count)

    def test_unknown_check_create_is_not_retried_within_invocation(self):
        c, identity = ReconciliationTests().state()
        del c.report
        c.owned_check.return_value = None
        c.shared.request.side_effect = controller.Refusal("synthetic lost acknowledgement")
        with self.assertRaises(controller.Refusal): c.report(HEAD, identity, "in_progress")
        with self.assertRaises(controller.Refusal): c.report(HEAD, identity, "completed", "action_required")
        self.assertEqual(c.shared.request.call_count, 1)


class WakeFilterTests(unittest.TestCase):
    def test_only_native_owned_fixture_completion_wakes_privileged_job(self):
        spec = importlib.util.spec_from_file_location("consumer_wake", ROOT / "scripts/consumer_wake.py")
        wake = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"consumer_compatibility": controller}):
            spec.loader.exec_module(wake)
        run, _, _, pr, *_ = native()
        run["actor"] = {"id": 456, "type": "Bot"}
        pr.update(state="open", user={"id": 456, "type": "Bot"})
        self.assertTrue(wake.owned(run, [pr], 456))
        mutations = [lambda r, p: r.update(head_branch="test/shared-ci-pr91-20261103"),
                     lambda r, p: r.update(path=".github/workflows/consumer-compatibility.yml"),
                     lambda r, p: r.update(event="push"),
                     lambda r, p: r["actor"].update(id=999),
                     lambda r, p: p["user"].update(id=999),
                     lambda r, p: p["head"].update(sha=TREE),
                     lambda r, p: p["head"]["repo"].update(id=999),
                     lambda r, p: p.update(state="closed")]
        for change in mutations:
            r, p = copy.deepcopy(run), copy.deepcopy(pr)
            change(r, p)
            self.assertFalse(wake.owned(r, [p], 456))
        self.assertFalse(wake.owned(run, [], 456))
        self.assertFalse(wake.owned(run, [pr, pr], 456))


class ImpactAndBudgetTests(unittest.TestCase):
    def impact(self):
        records = controller.impact_catalog((ROOT / "scripts/consumer-compatibility-impact.json").read_text())
        before = {"README.md": ("100644", "blob", HEAD),
                  "actions/ci-rust/action.yml": ("100644", "blob", HEAD),
                  "actions/ci-markdown/action.yml": ("100644", "blob", HEAD)}
        record = copy.deepcopy(records[0])
        record["consumer_source_family"] = controller.source_family(TREE)
        record["source_fingerprint_sha256"] = controller.digest(controller.canonical([
            ["actions/ci-markdown/action.yml", "100644", "blob", HEAD]]))
        after = {**before, "README.md": ("100644", "blob", TREE)}
        return before, after, [record]

    def test_reviewed_unaffected_path_skips_only_on_exact_private_family(self):
        before, after, records = self.impact()
        self.assertTrue(controller.no_impact(before, after, TREE, records))
        self.assertFalse(controller.no_impact(before, after, HEAD, records))
        # Private config, modules, symlinks and callers all change the Git tree.
        self.assertNotEqual(controller.source_family(TREE), controller.source_family(HEAD))

    def test_unknown_changed_reachable_rename_and_new_directory_require_tests(self):
        before, after, records = self.impact()
        for path in (".markdownlint-cli2.yaml", "actions/ci-markdown/action.yml",
                     "actions/ci-rust/new-directory/file.py", "unknown.py"):
            changed = {**after, path: ("100644", "blob", TREE)}
            with self.subTest(path=path):
                self.assertFalse(controller.no_impact(before, changed, TREE, records))
        moved = dict(after)
        moved.pop("actions/ci-markdown/action.yml")
        moved["actions/ci-rust/moved.py"] = ("100644", "blob", HEAD)
        self.assertFalse(controller.no_impact(before, moved, TREE, records))
        after["actions/ci-rust/existing-directory-file.py"] = ("100644", "blob", HEAD)
        self.assertTrue(controller.no_impact(before, after, TREE, records))

    def test_unknown_modes_and_unreviewed_catalog_fail_closed(self):
        before, after, records = self.impact()
        after["README.md"] = ("120000", "blob", TREE)
        self.assertFalse(controller.no_impact(before, after, TREE, records))
        records[0]["unaffected_paths"].append("scripts/")
        with self.assertRaises(controller.Refusal):
            controller.impact_catalog(json.dumps({"schema": 1, "records": records}))
        self.assertFalse(controller.no_impact(before, before, TREE, []))

    def publication(self, suffix, age=0):
        return {"head": {"ref": "test/shared-ci-" + suffix * 48, "repo": {"id": controller.CONSUMER_ID}},
                "base": {"ref": "dev", "repo": {"id": controller.CONSUMER_ID}},
                "user": {"id": 456, "type": "Bot"},
                "created_at": (NOW - dt.timedelta(hours=age)).strftime("%Y-%m-%dT%H:%M:%SZ")}

    def test_rolling_cap_counts_closed_recent_prs_and_unknown_ref_reservations(self):
        branch = "test/shared-ci-" + "c" * 48
        recent = [self.publication("a"), self.publication("b", 23)]
        self.assertFalse(controller.publication_capacity(recent, {}, 456, branch, NOW))
        recent[1] = self.publication("b", 25)
        self.assertTrue(controller.publication_capacity(recent, {}, 456, branch, NOW))
        pending = {"test/shared-ci-" + "d" * 48: HEAD}
        self.assertFalse(controller.publication_capacity(recent, pending, 456, branch, NOW))
        # Converting this selected reservation into its PR spends only one slot.
        self.assertTrue(controller.publication_capacity(recent, {branch: HEAD}, 456, branch, NOW))
        recent[0]["user"]["id"] = 999
        with self.assertRaises(controller.Refusal):
            controller.publication_capacity(recent, {}, 456, branch, NOW)

    def test_exemption_rechecks_admission_and_does_not_publish_fixture(self):
        c, identity = ReconciliationTests().state()
        c.material.return_value = (*c.material.return_value[:-1], True)
        c.reconcile(public_pr())
        c.fixture.assert_not_called()
        c.observe.assert_not_called()
        self.assertEqual(c.admit.call_count, 2)
        c.report.assert_called_once_with(HEAD, identity, "completed", "success", exempt=True)
        payload = controller.check_payload(HEAD, identity, "completed", "success", exempt=True)
        self.assertIn("product tests were not run", payload["output"]["summary"])


class FixtureRecoveryTests(unittest.TestCase):
    """Controller decisions after unknown provider outcomes, not provider proof."""

    def fixture_state(self):
        c = controller.Controller.__new__(controller.Controller)
        c.grant = grant()
        c.grant_raw = json.dumps({**grant(), "not_before": "1970-01-01T00:00:00Z", "expires_at": "2999-01-01T00:00:00Z"})
        c.generated = 0
        c.capacity = Mock(side_effect=lambda _: c.generated < 2)
        value, identity, branch = controller.plan(7, HEAD, TREE, "c" * 40, "d" * 40, "e" * 40, "f" * 40)
        generated, ref = "synthetic generated workflow\n", "1" * 40
        private = {"id": 80, "number": 8, "state": "open", "draft": True,
                   "body": controller.private_body(value, identity, generated), "user": {"id": 456, "type": "Bot"},
                   "head": {"sha": ref, "ref": branch, "repo": {"id": 1428636846}},
                   "base": {"sha": value["consumer_commit"], "ref": "dev", "repo": {"id": 1428636846}}}
        c.consumer = Mock()
        c.consumer.branch.return_value = ref
        c.verify_commit = Mock()
        c.current = Mock(return_value=value["consumer_commit"])
        c.admit = Mock()
        return c, (value, identity, branch, generated), private

    def test_recovered_ref_without_pr_still_consumes_publication_allowance(self):
        c, args, private = self.fixture_state()
        c.consumer.listing.side_effect = [[], [private]]
        self.assertEqual(c.fixture(*args), private)
        self.assertEqual(c.generated, 1)
        self.assertEqual(c.consumer.request.call_args.args[:2], ("/pulls", "POST"))

    def test_allowance_prevents_new_pr_even_when_ref_already_exists(self):
        c, args, _ = self.fixture_state()
        c.generated = 2
        c.consumer.listing.return_value = []
        self.assertIsNone(c.fixture(*args))
        c.consumer.request.assert_not_called()

    def test_unknown_create_recovers_existing_pr_without_a_second_write(self):
        c, args, private = self.fixture_state()
        created = []
        c.consumer.listing.side_effect = lambda _: list(created)

        def unknown_create(path, method, body):
            self.assertEqual((path, method), ("/pulls", "POST"))
            created.append(private)
            raise controller.Refusal("acknowledgement lost")

        c.consumer.request.side_effect = unknown_create
        with self.assertRaises(controller.Refusal):
            c.fixture(*args)
        self.assertEqual(c.generated, 1)
        self.assertEqual(c.fixture(*args), private)
        self.assertEqual(c.consumer.request.call_count, 1)
        self.assertEqual(c.generated, 1)

    def test_existing_owned_pr_reuses_without_spending_allowance(self):
        c, args, private = self.fixture_state()
        c.generated = 2
        c.consumer.listing.return_value = [private]
        self.assertEqual(c.fixture(*args), private)
        self.assertEqual(c.generated, 2)
        c.consumer.request.assert_not_called()

    def test_closed_or_foreign_pr_is_not_reopened_or_adopted(self):
        for change in (lambda p: p.update(state="closed"), lambda p: p["user"].update(id=99),
                       lambda p: p.update(body="foreign plan"), lambda p: p["base"].update(sha="0" * 40)):
            c, args, private = self.fixture_state()
            change(private)
            c.consumer.listing.return_value = [private]
            with self.assertRaises(controller.Refusal):
                c.fixture(*args)
            c.consumer.request.assert_not_called()


class RetirementTests(unittest.TestCase):
    fixture_state = FixtureRecoveryTests.fixture_state
    def retirement(self):
        c, args, private = self.fixture_state()
        value, identity, branch, generated = args
        c.harness = value["harness_commit"]
        c.workflow_bytes = Mock(return_value=generated)
        c.shared = Mock()
        c.shared.request.return_value = public_pr()
        c.report = Mock()
        c.owned_check = Mock(return_value={"external_id": identity, "conclusion": "success"})
        private["merged"] = False
        c.consumer.listing.side_effect = lambda _: [copy.deepcopy(private)] if private["state"] == "open" else []

        def request(path, method="GET", body=None):
            self.assertEqual(path, "/pulls/8")
            if method == "PATCH":
                self.assertEqual(body, {"state": "closed"})
                private["state"] = "closed"
            else:
                self.assertEqual(method, "GET")
            return copy.deepcopy(private)

        c.consumer.request.side_effect = request
        return c, args, private

    def test_current_fixture_stays_open(self):
        c, _, private = self.retirement()
        c.retire()
        self.assertEqual(private["state"], "open")
        c.report.assert_not_called()
        self.assertTrue(all(len(call.args) == 1 for call in c.consumer.request.call_args_list))

    def test_obsolete_fixture_closes_after_invalidating_its_old_result(self):
        c, args, private = self.retirement()
        c.current.return_value = "9" * 40
        c.retire()
        c.report.assert_called_once_with(HEAD, args[1], "queued")
        self.assertEqual(private["state"], "closed")
        self.assertEqual([call.args[1:] for call in c.consumer.request.call_args_list if len(call.args) > 1],
                         [("PATCH", {"state": "closed"})])

    def test_cleanup_does_not_clear_a_newer_success_for_same_head(self):
        c, _, private = self.retirement()
        c.current.return_value = "9" * 40
        c.owned_check.return_value["external_id"] = "0" * 64
        c.retire()
        self.assertEqual(private["state"], "closed")
        c.report.assert_not_called()

    def test_legacy_or_foreign_fixture_is_not_touched(self):
        for change in (lambda p: p["head"].update(ref="test/shared-ci-pr91-20261103"),
                       lambda p: p["user"].update(id=999)):
            c, _, private = self.retirement()
            change(private)
            c.retire()
            c.consumer.request.assert_not_called()

    def test_bad_plan_changed_bytes_ref_or_extra_delta_prevents_closure(self):
        for case in ("body", "bytes", "ref", "tree"):
            c, _, private = self.retirement()
            c.current.return_value = "9" * 40
            if case == "body":
                private["body"] += "\n"
            elif case == "bytes":
                c.workflow_bytes.return_value = "changed workflow"
            elif case == "ref":
                c.consumer.branch.return_value = "8" * 40
            else:
                c.verify_commit.side_effect = controller.Refusal("extra delta")
            with self.subTest(case=case), self.assertRaises(controller.Refusal):
                c.retire()
            self.assertEqual(private["state"], "open")
            self.assertTrue(all(len(call.args) == 1 for call in c.consumer.request.call_args_list))

    def test_unknown_close_recovers_observed_closed_state_without_repeating(self):
        c, _, private = self.retirement()
        c.current.return_value = "9" * 40
        request = c.consumer.request.side_effect

        def lose_ack(*args, **kwargs):
            result = request(*args, **kwargs)
            if len(args) > 1 and args[1] == "PATCH":
                raise controller.Refusal("closure acknowledgement lost")
            return result

        c.consumer.request.side_effect = lose_ack
        with self.assertRaises(controller.Refusal):
            c.retire()
        self.assertEqual(private["state"], "closed")
        count = c.consumer.request.call_count
        c.retire()
        self.assertEqual(c.consumer.request.call_count, count)


class GitCustodyTests(unittest.TestCase):
    def test_real_git_fixture_has_only_one_workflow_delta_and_one_parent(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-consumer-objects-") as temporary:
            root = Path(temporary)
            git = lambda *args, **kwargs: controller.run_git(root, *args, **kwargs)
            git("init", "--bare", "--quiet")
            parent_blob = git("hash-object", "-w", "--stdin", data=b"synthetic product source\n").decode().strip()
            workflow = "synthetic generated workflow\n"
            workflow_blob = git("hash-object", "-w", "--stdin", data=workflow.encode()).decode().strip()
            def tree(entries):
                return git("mktree", data="".join(f"{mode} {kind} {oid}\t{name}\n" for mode, kind, oid, name in entries).encode()).decode().strip()
            before = tree([("100644", "blob", parent_blob, "product.txt")])
            workflows = tree([("100644", "blob", workflow_blob, "shared-candidate.yml")])
            metadata = tree([("040000", "tree", workflows, "workflows")])
            after = tree([("040000", "tree", metadata, ".github"), ("100644", "blob", parent_blob, "product.txt")])
            author = {"GIT_AUTHOR_NAME": "Synthetic fixture", "GIT_COMMITTER_NAME": "Synthetic fixture",
                      "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
            base = git("commit-tree", before, data=b"synthetic base\n", extra=author).decode().strip()
            ref = git("commit-tree", after, "-p", base, data=b"synthetic fixture\n", extra=author).decode().strip()
            value, _, _ = controller.plan(7, HEAD, TREE, base, before, "e" * 40, "f" * 40)
            c = controller.Controller.__new__(controller.Controller)
            c.consumer = Mock()
            c.consumer.commit.return_value = {"parents": [{"sha": base}], "tree": {"sha": after}}
            def files(oid):
                result = {}
                for item in git("ls-tree", "-rz", oid).split(b"\0"):
                    if item:
                        info, path = item.split(b"\t", 1)
                        result[path.decode()] = tuple(info.decode().split())
                return result
            c.consumer.tree.side_effect = files
            c.consumer.request.return_value = {"total_commits": 1, "ahead_by": 1, "behind_by": 0,
                                               "files": [{"filename": controller.WORKFLOW, "status": "added"}]}
            c.workflow_bytes = Mock(return_value=workflow)
            c.verify_commit(ref, value, workflow)
            # A preserved-looking workflow is insufficient if any product file changes.
            changed = tree([("040000", "tree", metadata, ".github"), ("100644", "blob", workflow_blob, "product.txt")])
            c.consumer.commit.return_value["tree"]["sha"] = changed
            with self.assertRaises(controller.Refusal):
                c.verify_commit(ref, value, workflow)
            c.consumer.commit.return_value["tree"]["sha"] = after
            c.consumer.commit.return_value["parents"].append({"sha": HEAD})
            with self.assertRaises(controller.Refusal):
                c.verify_commit(ref, value, workflow)


if __name__ == "__main__":
    unittest.main()
