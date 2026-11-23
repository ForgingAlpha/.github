"""Exercise the native request against an offline recording of GitHub REST and GraphQL."""

import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("request_native_merge", ROOT / "actions/native-auto-merge/request.py")
armer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(armer)

REPO = "ForgingAlpha/fixture-site"
RID = 960093720  # A direct development route in the released route catalog.
BASE, HEAD, OTHER, ROOT_TREE, DOT_GITHUB_TREE = (digit * 40 for digit in "12345")
NODE = "PR_fixture9"
NUMBER = 9
PROOF_APP, REQUESTER = 762157, 90871243
SLUG = "fixture-merge-requester"
PREFIX = f"repos/{REPO}"
PULL = f"{PREFIX}/pulls/{NUMBER}"
FILES = f"{PULL}/files?per_page=100"
RULES = f"{PREFIX}/rules/branches/dev?per_page=100"
TEAM_RULE, PROOF_RULE, CI_RULE = 25795345, 432, 433


def rule(kind, identity, parameters):
    return {"type": kind, "ruleset_id": identity, "ruleset_source_type": "Organization",
            "ruleset_source": "ForgingAlpha", "parameters": parameters}


def checks(identity, context, app):
    return rule("required_status_checks", identity, {
        "strict_required_status_checks_policy": True,
        "required_status_checks": [{"context": context, "integration_id": app}]})


def native_request():
    return {"enabled_by": {"id": REQUESTER, "type": "Bot", "login": f"{SLUG}[bot]"},
            "merge_method": "merge"}


class GitHub:
    """Only named GETs and the native enable mutation are routable in this fixture."""

    def __init__(self):
        self.repo = {"id": RID, "full_name": REPO, "default_branch": "dev", "archived": False,
                     "allow_auto_merge": True, "allow_merge_commit": True}
        self.pull = {"number": NUMBER, "node_id": NODE, "state": "open", "draft": False, "auto_merge": None,
                     "base": {"sha": BASE, "ref": "dev", "repo": self.repo},
                     "head": {"sha": HEAD, "ref": "feature/ordinary", "repo": self.repo},
                     "user": {"id": 101, "login": "author", "type": "User"}, "changed_files": 1}
        self.event = {"action": "ready_for_review", "number": NUMBER, "repository": deepcopy(self.repo),
                      "pull_request": deepcopy(self.pull)}
        self.env = {"GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
                    "GITHUB_REPOSITORY": REPO, "GITHUB_REPOSITORY_ID": str(RID),
                    "GITHUB_WORKFLOW_REF": f"{REPO}/.github/workflows/native-merge.yml@refs/heads/dev",
                    "GITHUB_EVENT_NAME": "pull_request_target", "GITHUB_RUN_ATTEMPT": "1", "REQUESTER_SLUG": SLUG}
        self.state = {"id": NODE, "headRefOid": HEAD, "baseRefName": "dev", "baseRefOid": BASE,
                      "state": "OPEN", "isDraft": False, "reviewDecision": "REVIEW_REQUIRED",
                      "viewerCanEnableAutoMerge": True, "timelineItems": {"nodes": []}}
        self.rows = {
            PREFIX: self.repo, PULL: self.pull,
            f"{PREFIX}/branches/dev": {"name": "dev", "protected": True, "commit": {"sha": BASE}},
            f"apps/{SLUG}": {"id": 846234, "slug": SLUG},
            f"users/{SLUG}%5Bbot%5D": {"id": REQUESTER, "type": "Bot", "login": f"{SLUG}[bot]"},
            FILES: [[{"filename": "src/parser.py", "status": "modified"}]],
            RULES: [[rule("pull_request", TEAM_RULE, {
                "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                "required_reviewers": [{"reviewer": {"type": "Team", "id": 20299307}, "minimum_approvals": 1,
                                        "file_patterns": ["*"]}]})],
                    [checks(PROOF_RULE, "Exact human approval", PROOF_APP), checks(CI_RULE, "CI", 15368)]],
        }
        update = rule("update", 434, {"update_allows_fetch_and_merge": False})
        safety = {**rule("non_fast_forward", 435, {}), "ruleset_source_type": "Enterprise",
                  "ruleset_source": "fixture-enterprise"}
        self.rows[RULES].append([update, safety])
        self.reads = []
        for row in [row for page in self.rows[RULES] for row in page]:
            ident = row["ruleset_id"]
            self.rows[f"{PREFIX}/rulesets/{ident}?includes_parents=true"] = {
                "id": ident, "node_id": f"ruleset-{ident}", "enforcement": "active", "source": row["ruleset_source"],
                "source_type": row["ruleset_source_type"], "target": "branch", "conditions": {"ref_name": {"include": ["dev"]}},
                "updated_at": "2026-08-01T10:00:00.350Z", "rules": [{"type": row["type"], "parameters": row["parameters"]}]}
        fingerprint, _ = armer.snapshot(self, REPO, "dev", armer.effective_rules(self, REPO, "dev"))
        self.policy = {"repository_id": RID, "branch": "dev", "requester_id": REQUESTER, "proof_app_id": PROOF_APP,
                       "proof_context": "Exact human approval", "ordinary_paths": ["src/**", "package.json"],
                       "security_sources": True,
                       "ruleset_qualification": {"sha256": fingerprint, "observed_at": "2026-08-01T11:00:00Z"}}
        self.set_blob(json.dumps(self.policy).encode())
        self.reads = []
        self.mutations = []
        self.after_mutation = None

    def set_blob(self, data):
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        self.blob_path = f"{PREFIX}/git/blobs/{blob}"
        self.rows[self.blob_path] = {"sha": blob, "encoding": "base64", "size": len(data),
                                     "content": base64.b64encode(data).decode()}
        self.rows[f"{PREFIX}/git/commits/{BASE}"] = {"sha": BASE, "tree": {"sha": ROOT_TREE}}
        for oid, entry in ((ROOT_TREE, {"path": ".github", "type": "tree", "mode": "040000", "sha": DOT_GITHUB_TREE}),
                           (DOT_GITHUB_TREE, {"path": "native-auto-merge.json", "type": "blob",
                                              "mode": "100644", "sha": blob})):
            self.rows[f"{PREFIX}/git/trees/{oid}"] = {"sha": oid, "truncated": False, "tree": [entry]}

    def get(self, path, fresh=False):
        self.reads.append(path)
        return deepcopy(self.rows[path])

    def pages(self, path, fresh=False):
        return self.get(path, fresh)

    def post(self, path, payload):
        if path != "graphql":
            raise AssertionError(f"Unexpected write surface {path}")
        query = payload["query"]
        if query.lstrip().startswith("query"):
            self.reads.append("graphql")
            return {"data": {"node": deepcopy(self.state)}}
        self.mutations.append(deepcopy(payload))
        if "enablePullRequestAutoMerge(" not in query:
            raise AssertionError(f"Unexpected mutation {query}")
        self.pull["auto_merge"] = native_request()
        self.state["timelineItems"]["nodes"] = [{"__typename": "AutoMergeEnabledEvent"}]
        if self.after_mutation:
            self.after_mutation(self)
        return {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"id": NODE}}}}

    def run(self, mutate=True):
        return armer.request(self, self.event, self.env, mutate=mutate)

    def classify(self):
        self.pull["user"] = {"id": 49699333, "type": "Bot", "login": "dependabot[bot]"}
        self.pull["head"]["ref"] = "dependabot/npm_and_yarn/security-fixture"
        self.event["pull_request"] = deepcopy(self.pull)
        s = armer.security
        summary = {"schema": s.SOURCE_SCHEMA, "repository": REPO, "pull_request": NUMBER, "source_head_sha": HEAD,
                   "source_base_sha": BASE, "profile": s.PROFILE, "ghsa_set": ["GHSA-2345-6789-cfgh"]}
        check = {"id": 8080, "name": s.SOURCE_CHECK, "app": {"id": s.TRUSTED_SECURITY_AUTOMATION_APP_ID, "slug": "trusted-security"},
                 "status": "completed", "head_sha": HEAD, "conclusion": "success",
                 "external_id": f"{s.SOURCE_SCHEMA}:{NUMBER}:{HEAD}", "output": {"summary": json.dumps(summary)}}
        self.rows[f"{PREFIX}/commits/{HEAD}/check-runs?filter=all&per_page=100"] = [{"check_runs": [check]}]
        return check, summary


class RequestTests(unittest.TestCase):
    def assert_refused(self, api):
        with self.assertRaises((ValueError, armer.security.PolicyError)):
            api.run()
        self.assertEqual(api.mutations, [])

    def test_unapproved_ready_pr_only_requests_native_merge_on_selected_head(self):
        api = GitHub()
        self.assertTrue(api.run(mutate=False))
        self.assertEqual(api.mutations, [])
        self.assertTrue(api.run())
        self.assertEqual(len(api.mutations), 1)
        call = api.mutations[0]
        self.assertEqual(call["variables"], {"id": NODE, "head": HEAD})
        self.assertIn("expectedHeadOid:$head", call["query"].replace(" ", ""))
        self.assertIn("mergeMethod:MERGE", call["query"].replace(" ", ""))
        self.assertNotRegex(call["query"], r"\b(mergePullRequest|enqueuePullRequest|updateRef|createPullRequestReview)\b")
        self.assertEqual(api.pull["state"], "open")
        self.assertFalse(api.run())
        self.assertEqual(len(api.mutations), 1)

    def test_missing_enrollment_is_inert_and_blob_resolves_from_base(self):
        api = GitHub()
        api.rows[f"{PREFIX}/git/trees/{DOT_GITHUB_TREE}"]["tree"] = []
        self.assertFalse(api.run())
        self.assertEqual(api.mutations, [])
        self.assertIn(f"{PREFIX}/git/commits/{BASE}", api.reads)
        self.assertNotIn(f"{PREFIX}/git/commits/{HEAD}", api.reads)

    def test_rejects_changed_or_symlinked_enrollment(self):
        for variant in ("symlink", "truncated", "changed_bytes", "duplicate_field", "generic_proof_producer"):
            with self.subTest(variant=variant):
                api = GitHub()
                tree = api.rows[f"{PREFIX}/git/trees/{DOT_GITHUB_TREE}"]
                if variant == "symlink":
                    tree["tree"][0]["mode"] = "120000"
                elif variant == "truncated":
                    tree["truncated"] = True
                elif variant == "changed_bytes":
                    api.rows[api.blob_path]["content"] = "YQ=="
                elif variant == "duplicate_field":
                    api.set_blob(b'{"branch":"dev",' + json.dumps(api.policy).encode()[1:])
                else:
                    api.set_blob(json.dumps({**api.policy, "proof_app_id": 15368}).encode())
                self.assert_refused(api)

    def test_effective_nonbypassable_team_proof_and_ci_required(self):
        for variant in ("missing-proof", "wrong-producer", "non-strict", "shadow", "team-bypass", "proof-bypass",
                        "ci-app-bypass", "visible-invalid-bypass", "missing-ci", "queue"):
            with self.subTest(variant=variant):
                api = GitHub()
                rules = api.rows[RULES][1]
                proof = rules[0]["parameters"]
                if variant == "missing-proof":
                    rules.pop(0)
                elif variant == "wrong-producer":
                    proof["required_status_checks"][0]["integration_id"] = 15368
                elif variant == "non-strict":
                    proof["strict_required_status_checks_policy"] = False
                elif variant == "shadow":
                    rules.append(deepcopy(rules[0]))
                elif variant in ("team-bypass", "proof-bypass", "ci-app-bypass"):
                    rule_id = {"team-bypass": TEAM_RULE, "proof-bypass": PROOF_RULE, "ci-app-bypass": CI_RULE}[variant]
                    api.rows[f"{PREFIX}/rulesets/{rule_id}?includes_parents=true"]["bypass_actors"] = [
                        {"actor_type": "Integration", "actor_id": 91756, "bypass_mode": "always"}]
                elif variant == "visible-invalid-bypass":
                    api.rows[f"{PREFIX}/rulesets/{PROOF_RULE}?includes_parents=true"]["bypass_actors"] = None
                elif variant == "missing-ci":
                    rules.pop(1)
                else:
                    rules.append(rule("merge_queue", 999, {}))
                self.assert_refused(api)

    def test_owner_qualification_is_required_for_redacted_active_rulesets(self):
        for variant in ("mutated-actor-revision", "lost-update-rule", "enterprise-revision", "case-drift",
                        "changed-selector", "replaced-object", "missing-page", "same-tick", "future", "no-anchor"):
            with self.subTest(variant=variant):
                api = GitHub()
                metadata = api.rows[f"{PREFIX}/rulesets/{PROOF_RULE}?includes_parents=true"]
                if variant == "mutated-actor-revision":
                    metadata["updated_at"] = "2026-08-02T10:00:00Z"
                elif variant == "lost-update-rule":
                    api.rows[RULES][2].pop(0)
                elif variant == "enterprise-revision":
                    api.rows[f"{PREFIX}/rulesets/435?includes_parents=true"]["updated_at"] = "2026-08-01T10:00:01Z"
                elif variant == "case-drift":
                    metadata["source"] = "forgingalpha"
                elif variant == "changed-selector":
                    metadata["conditions"]["ref_name"]["include"].append("main")
                elif variant == "replaced-object":
                    metadata["node_id"] = "replacement"
                elif variant == "missing-page":
                    metadata["rules"].append({"type": "deletion"})
                else:
                    if variant == "no-anchor":
                        del api.policy["ruleset_qualification"]
                    else:
                        api.policy["ruleset_qualification"]["observed_at"] = (
                            "2026-08-01T10:00:00.900Z" if variant == "same-tick" else "2099-01-01T00:00:00Z")
                    api.set_blob(json.dumps(api.policy).encode())
                self.assert_refused(api)

    def test_explicit_human_exemptions_are_confined_to_the_owner_qualified_rule(self):
        for ident, mode, allowed in ((434, "exempt", True), (CI_RULE, "pull_request", True),
                                     (CI_RULE, "always", False), (PROOF_RULE, "pull_request", False)):
            with self.subTest(ident=ident, mode=mode):
                api = GitHub()
                api.rows[f"{PREFIX}/rulesets/{ident}?includes_parents=true"]["bypass_actors"] = [
                    {"actor_type": "OrganizationAdmin", "bypass_mode": mode}]
                if allowed:
                    self.assertTrue(api.run())
                else:
                    self.assert_refused(api)

    def test_snapshot_is_stable_across_provider_page_order(self):
        api = GitHub()
        api.rows[RULES].reverse()
        api.rows[RULES][0].reverse()
        self.assertTrue(api.run())
        self.assertFalse(any(p.startswith("orgs/") for p in api.reads))

    def test_refuses_stale_wrong_credential_or_replayed_wakes(self):
        for variant in ("stale-head", "stale-base", "foreign-caller", "rerun", "unknown-actor",
                        "wrong-requester", "generic-requester", "proof-as-requester", "retarget", "disarmed"):
            with self.subTest(variant=variant):
                api = GitHub()
                if variant == "stale-head":
                    api.event["pull_request"]["head"]["sha"] = OTHER
                elif variant == "stale-base":
                    api.rows[f"{PREFIX}/branches/dev"]["commit"]["sha"] = OTHER
                elif variant == "foreign-caller":
                    api.env["GITHUB_WORKFLOW_REF"] = f"{REPO}/.github/workflows/native-merge.yml@refs/heads/feature"
                elif variant == "rerun":
                    api.env["GITHUB_RUN_ATTEMPT"] = "2"
                elif variant == "unknown-actor":
                    api.pull["user"] = {"id": 156, "type": "Bot", "login": "unknown[bot]"}
                elif variant == "wrong-requester":
                    api.rows[f"users/{SLUG}%5Bbot%5D"]["id"] += 1
                elif variant == "proof-as-requester":
                    api.rows[f"apps/{SLUG}"]["id"] = PROOF_APP
                elif variant == "retarget":
                    api.event["pull_request"]["base"]["ref"] = "main"
                elif variant == "generic-requester":
                    api.env["REQUESTER_SLUG"] = "github-actions"
                else:
                    api.state["timelineItems"]["nodes"] = [{"__typename": "AutoMergeDisabledEvent"}]
                self.assert_refused(api)

    def test_manual_routes_draft_policy_and_files_refused(self):
        for variant in ("draft", "fork", "promotion", "projection", "foreign-request", "unlisted",
                        "protected-rename", "incomplete", "global", "nested-config"):
            with self.subTest(variant=variant):
                api = GitHub()
                if variant == "draft":
                    api.pull["draft"] = True
                elif variant == "fork":
                    api.pull["head"]["repo"] = dict(api.repo, id=1222, full_name="contributor/fork")
                elif variant == "promotion":
                    api.pull["head"]["ref"] = "staging"
                elif variant == "projection":
                    api.pull["head"]["ref"] = "security-projection/example"
                elif variant == "foreign-request":
                    api.pull["auto_merge"] = native_request()
                    api.pull["auto_merge"]["enabled_by"]["id"] += 1
                elif variant == "incomplete":
                    api.pull["changed_files"] = 2
                else:
                    row = {"filename": "config/outside.json", "status": "modified"}
                    if variant == "protected-rename":
                        row.update(filename="src/new-name.yml", status="renamed",
                                   previous_filename=".github/workflows/required.yml")
                    elif variant == "global":
                        row.update(filename="src/GLOBAL.md")
                    elif variant == "nested-config":
                        row.update(filename="src/.github/merge.yml")
                    api.rows[FILES] = [[row]]
                self.assert_refused(api)

    def test_reserved_paths_are_case_insensitive_but_enrollment_is_exact(self):
        from enrollment import matches_ordinary_path
        policy = {"ordinary_paths": ["src/**", "AcTions/**", "SyStEm/**", "Workflow-Templates/**"]}
        self.assertTrue(matches_ordinary_path(policy, "src/component/module.py"))
        for path in ("Src/component/module.py", "src/ReAdMe.Md", "src/component/aGeNtS.mD",
                     "src/CoDeOwNeRs", "src/Renovate.JsOn", "src/GOVERNING-SOURCE-BINDINGS.JSON",
                     "AcTions/script.py", "SyStEm/policy.json", "Workflow-Templates/ci.yml"):
            with self.subTest(path=path):
                self.assertFalse(matches_ordinary_path(policy, path))

    def test_classified_dependabot_source_is_eligible_without_ordinary_path_admission(self):
        api = GitHub()
        api.classify()
        api.rows[FILES] = [[{"filename": "package-lock.json", "status": "modified"}]]
        self.assertTrue(api.run())
        self.assertEqual(len(api.mutations), 1)

    def test_security_completion_wake_binds_classifier_event_to_its_live_loaded_check(self):
        for variant in ("valid", "foreign-producer", "wrong-subject", "bad-external-id", "wrong-check",
                        "stale-head", "failed", "other-action"):
            with self.subTest(variant=variant):
                api = GitHub()
                check, _ = api.classify()
                delivered = deepcopy(check)
                api.env["GITHUB_EVENT_NAME"] = "check_run"
                api.event = {"action": "completed", "repository": deepcopy(api.repo), "check_run": delivered}
                if variant == "valid":
                    self.assertTrue(api.run())
                    self.assertEqual(len(api.mutations), 1)
                    continue
                if variant == "foreign-producer":
                    delivered["app"]["id"] = PROOF_APP
                elif variant == "wrong-subject":
                    delivered["external_id"] = f"{armer.security.SOURCE_SCHEMA}:{NUMBER + 1}:{HEAD}"
                    # The other PR exists but the classifier's attestation names this PR.
                    api.rows[PULL.replace(f"/{NUMBER}", f"/{NUMBER + 1}")] = dict(api.pull, number=NUMBER + 1)
                elif variant == "bad-external-id":
                    delivered["external_id"] = "ordinary-ci"
                elif variant == "wrong-check":
                    delivered["id"] += 1
                elif variant == "stale-head":
                    delivered["head_sha"] = OTHER
                elif variant == "failed":
                    delivered["conclusion"] = "failure"
                else:
                    api.event["action"] = "requested_action"
                self.assert_refused(api)

    def test_approved_security_source_requests_only_native_completion(self):
        api = GitHub()
        api.classify()
        api.state["reviewDecision"] = "APPROVED"
        self.assertTrue(api.run())
        self.assertEqual(len(api.mutations), 1)
        self.assertEqual(api.mutations[0]["query"], armer.REQUEST)
        self.assertEqual(api.pull["state"], "open")

    def test_unqualified_security_source_cannot_fall_back_to_ordinary(self):
        for variant in ("missing", "wrong-app", "wrong-base", "wrong-pr", "no-advisory", "wrong-head"):
            with self.subTest(variant=variant):
                api = GitHub()
                check, summary = api.classify()
                if variant == "missing":
                    api.rows[f"{PREFIX}/commits/{HEAD}/check-runs?filter=all&per_page=100"] = [{"check_runs": []}]
                elif variant == "wrong-app":
                    check["app"]["id"] = PROOF_APP
                elif variant == "wrong-head":
                    check["head_sha"] = OTHER
                else:
                    summary.update({"wrong-base": {"source_base_sha": OTHER}, "wrong-pr": {"pull_request": NUMBER + 1},
                                    "no-advisory": {"ghsa_set": []}}[variant])
                    check["output"]["summary"] = json.dumps(summary)
                self.assert_refused(api)

    def test_lost_response_reconciled_only_on_same_subject_and_never_retried(self):
        for variant in ("recorded", "unknown", "other-head", "retarget", "foreign", "closed"):
            with self.subTest(variant=variant):
                api = GitHub()

                def lose_response(target):
                    if variant == "unknown":
                        target.pull["auto_merge"] = None
                    elif variant == "other-head":
                        target.pull["head"]["sha"] = OTHER
                    elif variant == "retarget":
                        target.pull["base"]["ref"] = "main"  # Same base SHA is possible.
                    elif variant == "foreign":
                        target.pull["auto_merge"]["enabled_by"]["id"] += 1
                    elif variant == "closed":
                        target.pull["state"] = "closed"
                    raise armer.security.PolicyError("response lost")

                api.after_mutation = lose_response
                if variant == "recorded":
                    self.assertTrue(api.run())
                else:
                    with self.assertRaises((ValueError, armer.security.PolicyError)):
                        api.run()
                self.assertEqual(len(api.mutations), 1)

    def test_shared_workflow_is_passive_and_privilege_is_bound_to_protected_source(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/request-auto-merge.yml").read_text())
        self.assertEqual(set(workflow["on"]), {"workflow_call"})
        self.assertEqual(workflow.get("permissions"), {})
        self.assertFalse(workflow["on"]["workflow_call"])
        preflight, writer = workflow["jobs"]["assess"], workflow["jobs"]["request"]
        self.assertNotIn("environment", preflight)
        self.assertTrue(all(access == "read" for access in preflight["permissions"].values()))
        self.assertEqual(writer["needs"], "assess")
        self.assertIn("needs.assess.outputs.eligible == 'true'", writer["if"])
        self.assertEqual(writer["environment"], "native-merge-request")
        self.assertTrue(all(access == "read" for access in writer["permissions"].values()))
        source = next(step for step in preflight["steps"] if step.get("id") == "source")
        self.assertEqual(source["env"]["JOB_CONTEXT"], "${{ toJSON(job) }}")
        self.assertIn(".workflow_sha", source["run"])
        self.assertIn("request-auto-merge.yml@refs/heads/main", source["run"])
        self.assertIn("native-merge.yml@refs/heads/$DEFAULT_BRANCH", source["run"])
        for job, immutable_ref in ((preflight, "${{ steps.source.outputs.sha }}"),
                                   (writer, "${{ needs.assess.outputs.source }}")):
            checkouts = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
            self.assertEqual(len(checkouts), 1)
            checkout = checkouts[0]
            self.assertRegex(checkout["uses"], r"^actions/checkout@[a-f0-9]{40}$")
            self.assertEqual(checkout["with"]["repository"], "ForgingAlpha/.github")
            self.assertEqual(checkout["with"]["ref"], immutable_ref)
            self.assertIs(checkout["with"]["persist-credentials"], False)
            for step in job["steps"]:
                self.assertNotIn("${{", step.get("run", ""))
            self.assertNotIn("github.event.pull_request.head", json.dumps(job))
        mint = next(step for step in writer["steps"] if step.get("id") == "requester")
        self.assertRegex(mint["uses"], r"^actions/create-github-app-token@[a-f0-9]{40}$")
        self.assertEqual(mint["with"]["private-key"], "${{ secrets.NATIVE_MERGE_REQUEST_PRIVATE_KEY }}")
        writable = {key for key, value in mint["with"].items() if value == "write"}
        self.assertEqual(writable, {"permission-contents", "permission-pull-requests"})
        self.assertFalse(any("administration" in key for key in mint["with"]))
        effect = writer["steps"][-1]
        self.assertEqual(effect["env"]["GH_TOKEN"], "${{ steps.requester.outputs.token }}")
        self.assertEqual(effect["env"]["REQUESTER_SLUG"], "${{ steps.requester.outputs.app-slug }}")
        self.assertEqual(effect["run"], "python3 -I -B actions/native-auto-merge/request.py request")
