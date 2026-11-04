"""Foundation-only reconciliation. Candidate files are data, never controller code.

This does not install credentials or rules. See docs/consumer-compatibility.md.
"""

import base64
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request


SHARED = "ForgingAlpha/.github"
CONSUMER = "ForgingAlpha/container-foundation"
SHARED_ID = 1137664016
CONSUMER_ID = 1428636846
CHECK = "Consumer compatibility"
WORKFLOW = ".github/workflows/shared-candidate.yml"
CONTROLLER = ".github/workflows/consumer-compatibility-controller.yml"
HEX40 = r"[0-9a-f]{40}"
HEX64 = r"[0-9a-f]{64}"
BRANCH = r"test/shared-ci-[0-9a-f]{48}"
ACTIONS = ["read-approved-shared-candidate", "execute-private-fixture",
           "publish-public-result", "close-owned-fixture"]
CONDITIONS = ["exact-head-human-review", "foundation-read-entitlement",
              "no-controller-secret-in-fixture", "human-only-merge"]
REVIEW_QUERY = "query($number:Int!){repository(owner:\"ForgingAlpha\",name:\".github\"){pullRequest(number:$number){headRefOid reviewDecision}}}"
INSPECTED_ACTIONS = ("ci-merge-flow", "ci-alphaapps-policy", "ci-github-actions", "ci-markdown",
                     "ci-dependency-review", "ci-update-ownership", "ci-dependabot-coverage",
                     "ci-foundation", "ci-org-baseline", "security-patch")


class Refusal(Exception):
    """Bounded, nonsecret diagnostic; never includes provider bodies or stderr."""


class IncompleteInventory(Refusal):
    """Validated observations may be used to block, never to admit new work."""

    def __init__(self, items):
        super().__init__("provider inventory is incomplete")
        self.items = tuple(items)


class Pending(Refusal):
    """An ordinary prerequisite is not ready; this is not a controller error."""


class NativeFailure(Refusal):
    """The selected native execution completed without success."""


def need(value, reason):
    if not value:
        raise Refusal(reason)


def integer(value):
    return type(value) is int and value > 0


def sha(value):
    need(isinstance(value, str) and re.fullmatch(HEX40, value), "invalid source identity")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def decode(raw, maximum=8 * 1024 * 1024):
    need(isinstance(raw, (bytes, str)) and len(raw.encode() if isinstance(raw, str) else raw) <= maximum, "response exceeds bound")

    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, "duplicate JSON field")
            out[key] = value
        return out

    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: need(False, "nonfinite JSON number"))
    except (ValueError, RecursionError) as exc:
        raise Refusal("invalid JSON") from exc


def timestamp(value):
    need(isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value), "invalid authority time")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise Refusal("invalid authority time") from exc


def source_family(tree):
    return digest(canonical({"schema": "foundation-source-family/v1",
                             "repository_id": CONSUMER_ID, "tree": sha(tree)}))


def impact_catalog(raw):
    value = decode(raw, 131072)
    need(type(value) is dict and set(value) == {"schema", "records"} and
         type(value["schema"]) is int and value["schema"] == 1 and
         type(value["records"]) is list and 0 < len(value["records"]) <= 32, "invalid impact catalog")
    required = {"source_fingerprint_sha256", "evidence_revision", "consumer_repository_id",
                "consumer_source_family", "entrypoints", "inspected_paths", "unaffected_paths", "reachability_basis"}
    inspected = {"actions/" + a + "/" for a in INSPECTED_ACTIONS} | {".github/workflows/org-baseline.yml"}
    entrypoints = {"actions/" + a + "/action.yml" for a in INSPECTED_ACTIONS[:7]}
    maximum_exempt = {"actions/ci-" + a + "/" for a in ("astro", "elixir", "rust", "shell", "typescript")} | {"README.md"}
    seen = set()
    for record in value["records"]:
        need(type(record) is dict and set(record) == required, "unbound impact record")
        for field in ("source_fingerprint_sha256", "consumer_source_family"):
            need(isinstance(record[field], str) and re.fullmatch(HEX64, record[field]), "invalid impact identity")
        sha(record["evidence_revision"])
        need(type(record["consumer_repository_id"]) is int and record["consumer_repository_id"] == CONSUMER_ID,
             "impact consumer mismatch")
        for field, allowed, exact in (("inspected_paths", inspected, True), ("entrypoints", entrypoints, True),
                                      ("unaffected_paths", maximum_exempt, False)):
            values = record[field]
            need(type(values) is list and values and all(isinstance(p, str) for p in values) and
                 len(values) == len(set(values)) and set(values) <= allowed and
                 (not exact or set(values) == allowed), "invalid or unbound impact paths")
        need(isinstance(record["reachability_basis"], str) and 1 <= len(record["reachability_basis"]) <= 4096,
             "impact evidence basis unavailable")
        key = (record["source_fingerprint_sha256"], record["consumer_source_family"])
        need(key not in seen, "ambiguous impact records")
        seen.add(key)
    return value["records"]


def path_member(path, classes):
    return any(path.startswith(item) if item.endswith("/") else path == item for item in classes)


def no_impact(before, after, consumer_tree, records):
    """A positive derivation for recorded complete source shapes, never a guess."""
    for files in (before, after):
        if not isinstance(files, dict) or not files:
            return False
        for path, entry in files.items():
            if (not isinstance(path, str) or path.startswith("/") or
                    any(p in ("", ".", "..") for p in path.split("/")) or
                    any(ord(c) < 32 for c in path) or
                    not isinstance(entry, (tuple, list)) or len(entry) != 3 or
                    entry[0] not in ("100644", "100755") or entry[1] != "blob" or
                    not isinstance(entry[2], str) or not re.fullmatch(HEX40, entry[2])):
                return False
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    if not changed:
        return False
    directories = {""}
    for path in before:
        pieces = path.split("/")
        directories.update("/".join(pieces[:i]) for i in range(1, len(pieces)))
    if any(p in after and p.rpartition("/")[0] not in directories for p in changed):
        return False
    family = source_family(consumer_tree)
    for record in records:
        if family != record["consumer_source_family"]:
            continue
        def fingerprint(files):
            entries = [[p, *files[p]] for p in sorted(files) if path_member(p, record["inspected_paths"])]
            return digest(canonical(entries))
        if (fingerprint(before) == fingerprint(after) == record["source_fingerprint_sha256"] and
                all(path_member(p, record["unaffected_paths"]) for p in changed)):
            return True
    return False


def publication_capacity(prs, refs, bot_id, branch, now):
    """Include unresolved refs as conservative reservations for unknown PR writes."""
    cutoff = now - dt.timedelta(hours=24)
    published, recent = set(), 0
    for pr in prs:
        name = pr.get("head", {}).get("ref", "")
        if not re.fullmatch(BRANCH, name):
            continue
        need(pr.get("user", {}).get("id") == bot_id and pr["user"].get("type") == "Bot" and
             pr["head"]["repo"]["id"] == CONSUMER_ID and pr["base"]["repo"]["id"] == CONSUMER_ID and
             pr["base"]["ref"] == "dev" and name not in published, "ambiguous fixture publication ledger")
        created = timestamp(pr.get("created_at"))
        need(created <= now, "future fixture publication time")
        recent += created >= cutoff
        published.add(name)
    pending = set(refs) - published
    # The selected existing ref will become a PR, replacing its reservation.
    return recent + len(pending - {branch}) < 2


def authorization(raw, now=None):
    value = decode(raw, 16384)
    strings = {"grant_id", "enrollment_id", "principal", "trust_domain", "decision_evidence"}
    hashes = {"grant_sha256", "enrollment_sha256"}
    fixed = {"schema": 1, "shared_repository_id": SHARED_ID,
             "consumer_repository_id": CONSUMER_ID, "environment": "consumer-compatibility",
             "caller_ref": "refs/heads/dev", "purpose": "shared-ci-foundation-qualification",
             "actions": ACTIONS, "conditions": CONDITIONS}
    need(type(value) is dict and set(value) == strings | hashes | set(fixed) |
         {"reporting_app_id", "fixture_app_id", "fixture_bot_id", "not_before", "expires_at"}, "invalid authorization fields")
    for key, expected in fixed.items():
        need(type(value[key]) is type(expected) and value[key] == expected, "authorization flow mismatch")
    for key in strings:
        need(isinstance(value[key], str) and 1 <= len(value[key]) <= 1024 and
             all(ord(c) >= 32 for c in value[key]), "invalid authority reference")
    for key in hashes:
        need(isinstance(value[key], str) and re.fullmatch(HEX64, value[key]), "invalid authority digest")
    need(all(integer(value[key]) for key in ("reporting_app_id", "fixture_app_id", "fixture_bot_id")) and
         value["reporting_app_id"] != value["fixture_app_id"], "invalid or combined principal identity")
    now = now or dt.datetime.now(dt.timezone.utc)
    need(timestamp(value["not_before"]) <= now < timestamp(value["expires_at"]), "authority is not current")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal("provider redirect refused")


class API:
    """Fixed host, scoped repository, bounded requests; no arbitrary endpoint writes."""

    def __init__(self, repo, token):
        need(repo in (SHARED, CONSUMER), "unknown repository")
        self.repo, self.token, self.requests = repo, token, 0
        self.opener = urllib.request.build_opener(NoRedirect)
        self.before_write = None

    def request(self, path, method="GET", body=None, absent=False):
        need((path == "" or path.startswith("/")) and not path.startswith("//") and "#" not in path,
             "invalid API path")
        graphql = path == "/graphql"
        if graphql:
            need(self.repo == SHARED and method == "POST" and body.get("query") == REVIEW_QUERY and
                 integer(body.get("variables", {}).get("number")), "unsupported GraphQL operation")
        elif method != "GET":
            allowed = bool(self.repo == SHARED and
                       ((method == "POST" and path == "/check-runs") or
                        (method == "PATCH" and re.fullmatch(r"/check-runs/[0-9]+", path))))
            allowed |= bool(self.repo == CONSUMER and (
                (method == "POST" and path in ("/git/blobs", "/git/trees", "/git/commits", "/git/refs", "/pulls")) or
                (method == "PATCH" and re.fullmatch(r"/pulls/[0-9]+", path) and body == {"state": "closed"})))
            need(allowed, "mutation outside controller surface")
            if path == "/git/refs":
                need(re.fullmatch("refs/heads/" + BRANCH, body.get("ref", "")), "persistent ref refused")
            if self.before_write is not None:
                self.before_write()
        # Leave capacity for invalidating known results after normal work fails.
        need(self.requests < (1600 if getattr(self, "blocking", False) else 1400), "API operation bound exhausted")
        self.requests += 1
        headers = {"Accept": "application/vnd.github+json", "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "forgingalpha-consumer-compatibility"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        url = "https://api.github.com/graphql" if graphql else "https://api.github.com/repos/" + self.repo + path
        request = urllib.request.Request(url,
                                         data=canonical(body).encode() if body is not None else None,
                                         headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                return decode(response.read(8 * 1024 * 1024 + 1))
        except urllib.error.HTTPError as exc:
            if absent and exc.code == 404:
                return None
            raise Refusal("provider operation failed; reconcile before retry") from None
        except (OSError, urllib.error.URLError) as exc:
            raise Refusal("provider operation unavailable; reconcile before retry") from exc

    def listing(self, path, key=None, limit=1000):
        result = []
        seen = set()
        try:
            for page in range(1, 12):
                response = self.request(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
                need(not key or type(response) is dict, "invalid provider list envelope")
                items = response.get(key) if key else response
                need(type(items) is list, "incomplete provider list")
                for item in items:
                    need(type(item) is dict and integer(item.get("id")) and item["id"] not in seen, "ambiguous provider inventory")
                    seen.add(item["id"])
                    result.append(item)
                    need(len(result) <= limit, "provider inventory exceeds supported bound")
                if len(items) < 100:
                    if key:
                        need(type(response.get("total_count")) is int and response["total_count"] == len(result), "partial provider inventory")
                    return result
            raise Refusal("pagination bound exhausted")
        except (Refusal, KeyError, TypeError, ValueError, OSError):
            raise IncompleteInventory(result) from None

    def commit(self, revision):
        value = self.request("/git/commits/" + sha(revision))
        need(value.get("sha") == revision, "commit identity mismatch")
        sha(value["tree"]["sha"])
        return value

    def branch(self, name):
        need(name in ("main", "dev") or re.fullmatch(BRANCH, name), "unsupported branch")
        value = self.request("/git/ref/heads/" + name, absent=True)
        if value is None:
            return None
        need(value.get("ref") == "refs/heads/" + name and value["object"]["type"] == "commit", "ref identity mismatch")
        return sha(value["object"]["sha"])

    def tree(self, tree):
        value = self.request("/git/trees/" + sha(tree) + "?recursive=1")
        need(value.get("sha") == tree and value.get("truncated") is False and
             type(value.get("tree")) is list and len(value["tree"]) <= 5000, "incomplete or oversized source tree")
        files, total = {}, 0
        for item in value["tree"]:
            path = item.get("path")
            need(isinstance(path, str) and 0 < len(path) <= 1024 and not path.startswith("/") and
                 not any(p in ("", ".", "..") for p in path.split("/")) and
                 all(ord(c) >= 32 for c in path), "invalid source path")
            if item.get("type") == "tree":
                continue
            need(path not in files and item.get("type") == "blob" and
                 item.get("mode") in ("100644", "100755", "120000") and
                 type(item.get("size")) is int and 0 <= item["size"] <= 2 * 1024 * 1024, "unsupported source entry")
            total += item["size"]
            need(total <= 16 * 1024 * 1024, "source exceeds supported byte bound")
            files[path] = (item["mode"], item["type"], sha(item.get("sha")))
        return files

    def fixture_refs(self):
        value = self.request("/git/matching-refs/heads/test/shared-ci-")
        need(type(value) is list and len(value) <= 1000, "incomplete fixture ref inventory")
        result = {}
        for item in value:
            ref = item.get("ref", "")
            need(isinstance(ref, str) and ref.startswith("refs/heads/test/shared-ci-"), "unexpected fixture ref")
            branch = ref.removeprefix("refs/heads/")
            if not re.fullmatch(BRANCH, branch):
                continue
            need(branch not in result and item.get("object", {}).get("type") == "commit", "ambiguous fixture refs")
            result[branch] = sha(item["object"].get("sha"))
        return result


def run_git(root, *args, data=None, extra=None):
    # No ambient Git config, hooks, credential helpers, or candidate working tree.
    env = {"PATH": os.defpath, "HOME": str(root), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
           "GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "core.hooksPath",
           "GIT_CONFIG_VALUE_0": "/dev/null", "GIT_CONFIG_KEY_1": "http.followRedirects",
           "GIT_CONFIG_VALUE_1": "false", "GIT_CONFIG_KEY_2": "credential.helper",
           "GIT_CONFIG_VALUE_2": ""}
    env.update(extra or {})
    try:
        return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                              input=data, capture_output=True, timeout=60, check=True, env=env).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refusal("bounded Git operation failed") from exc


def fetch(root, api, revision):
    root.mkdir()
    run_git(root, "init", "--bare", "--quiet")
    auth = base64.b64encode(("x-access-token:" + api.token).encode()).decode()
    run_git(root, "fetch", "--quiet", "--no-tags", "--depth=1",
            "https://github.com/" + api.repo + ".git", sha(revision), extra={
                "GIT_CONFIG_COUNT": "4", "GIT_CONFIG_KEY_3": "http.extraHeader",
                "GIT_CONFIG_VALUE_3": "Authorization: Basic " + auth})
    need(run_git(root, "cat-file", "-t", revision).strip() == b"commit", "fetched object is not a commit")


def adapter():
    spec = importlib.util.spec_from_file_location("qualified_adapter", Path(__file__).with_name("qualify_foundation.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(number, shared_head, shared_tree, consumer_head, consumer_tree, harness_head, harness_tree):
    need(integer(number), "invalid shared PR")
    value = {"schema": 1, "shared_repository_id": SHARED_ID, "consumer_repository_id": CONSUMER_ID,
             "pull_request": number, "shared_commit": sha(shared_head), "shared_tree": sha(shared_tree),
             "consumer_commit": sha(consumer_head), "consumer_tree": sha(consumer_tree),
             "harness_commit": sha(harness_head), "harness_tree": sha(harness_tree)}
    identity = digest(canonical(value))
    return value, identity, "test/shared-ci-" + identity[:48]


def private_body(value, identity, workflow):
    return "Disposable consumer qualification. Never merge.\n\n" + canonical({
        "plan": value, "plan_sha256": identity, "workflow_sha256": digest(workflow)}) + "\n"


def retained_plan(body):
    prefix = "Disposable consumer qualification. Never merge.\n\n"
    need(isinstance(body, str) and body.startswith(prefix), "fixture plan is unavailable")
    record = decode(body[len(prefix):], 8192)
    need(type(record) is dict and set(record) == {"plan", "plan_sha256", "workflow_sha256"},
         "invalid retained plan fields")
    p = record["plan"]
    need(type(p) is dict, "invalid retained plan")
    value, identity, branch = plan(p["pull_request"], p["shared_commit"], p["shared_tree"],
                                  p["consumer_commit"], p["consumer_tree"],
                                  p["harness_commit"], p["harness_tree"])
    need(canonical(p) == canonical(value) and record["plan_sha256"] == identity and
         isinstance(record["workflow_sha256"], str) and re.fullmatch(HEX64, record["workflow_sha256"]) and
         body == prefix + canonical(record) + "\n", "retained plan binding mismatch")
    return value, identity, branch, record["workflow_sha256"]


def check_payload(head, identity, status, conclusion=None, number=None, exempt=False):
    need(status in ("queued", "in_progress", "completed"), "invalid public state")
    need((status != "completed" and conclusion is None) or
         (status == "completed" and conclusion in ("success", "failure", "action_required", "cancelled", "timed_out")), "invalid public conclusion")
    need(re.fullmatch(HEX64, identity), "invalid public plan identity")
    value = {"name": CHECK, "head_sha": sha(head), "external_id": identity, "status": status,
             "output": {"title": CHECK, "summary": "Shared candidate " + head + "; plan " + identity +
                        "; " + (conclusion or status) + "."}}
    if conclusion is not None:
        value["conclusion"] = conclusion
    if exempt:
        need(status == "completed" and conclusion == "success" and number is None, "invalid impact result")
        value["output"]["summary"] += " No Foundation runtime dependency changed for this plan; product tests were not run."
    if number is not None:
        need(integer(number), "invalid private detail identity")
        value["details_url"] = "https://github.com/" + CONSUMER + "/pull/" + str(number)
    return value


def eligible(pr, reviews, entitlement, review_decision):
    need(pr["base"]["ref"] == "main" and pr["base"]["repo"]["id"] == SHARED_ID and
         pr["head"]["repo"]["id"] == SHARED_ID, "candidate is not an eligible same-repository PR")
    head = sha(pr["head"]["sha"])
    if pr.get("state") != "open" or pr.get("draft") is not False or review_decision != "APPROVED":
        raise Pending("awaiting eligible existing human review")
    latest = {}
    for review in sorted(reviews, key=lambda x: x["id"]):
        need(integer(review.get("id")) and integer(review["user"].get("id")), "invalid review identity")
        if review.get("state") != "COMMENTED":
            latest[review["user"]["id"]] = review
    for review in latest.values():
        user = review["user"]
        if review.get("state") == "APPROVED" and review.get("commit_id") == head and user.get("type") == "User":
            login = user.get("login")
            need(isinstance(login, str) and re.fullmatch(r"[A-Za-z0-9-]{1,39}", login), "invalid reviewer locator")
            access = entitlement(login)
            if (access.get("permission") in ("read", "write", "admin") and
                    access.get("user", {}).get("id") == user["id"] and access["user"].get("type") == "User"):
                return user["id"]
    raise Pending("eligible exact-head human review is unavailable")


def native_success(run, jobs, checks, pr, path, branch, expected_steps, job_name):
    """Provider observations only. Does not verify artifact payload content."""
    need(run.get("event") == "pull_request" and run.get("path") == path and
         run.get("head_branch") == branch and run.get("head_sha") == pr["head"]["sha"] and
         run.get("head_repository", {}).get("id") == CONSUMER_ID and
         run.get("repository", {}).get("id") == CONSUMER_ID and
         integer(run.get("id")) and integer(run.get("run_attempt")) and integer(run.get("check_suite_id")), "native run binding mismatch")
    associations = run.get("pull_requests")
    need(type(associations) is list and len(associations) <= 1 and all(
        item.get("number") == pr["number"] and item["head"]["sha"] == pr["head"]["sha"] and
        item["head"]["repo"]["id"] == CONSUMER_ID and item["base"]["repo"]["id"] == CONSUMER_ID
        for item in associations), "conflicting native PR association")
    need(pr["head"]["repo"]["id"] == CONSUMER_ID and pr["base"]["repo"]["id"] == CONSUMER_ID and
         pr["head"]["ref"] == branch and pr["base"]["ref"] == "dev", "private PR binding mismatch")
    # A later successful attempt cannot erase a failed attempt merely by
    # existing. No diagnostic-rerun authorization input is qualified yet.
    need(run["run_attempt"] == 1, "diagnostic rerun authorization is not qualified")
    if run.get("status") != "completed":
        return False
    if run.get("conclusion") != "success":
        raise NativeFailure("native workflow did not succeed")
    need(len(jobs) == 1 and len(checks) == 1, "ambiguous native jobs")
    job, check = jobs[0], checks[0]
    need(job.get("name") == job_name and job.get("run_id") == run["id"] and
         job.get("run_attempt") == run["run_attempt"] and job.get("head_sha") == run["head_sha"] and
         job.get("status") == "completed" and job.get("conclusion") == "success", "native job did not succeed")
    need(integer(check.get("id")) and job.get("check_run_url") ==
         "https://api.github.com/repos/" + CONSUMER + "/check-runs/" + str(check["id"]) and
         check.get("app", {}).get("id") == 15368 and check.get("head_sha") == run["head_sha"] and
         check.get("check_suite", {}).get("id") == run["check_suite_id"] and
         check.get("name") == job_name and check.get("status") == "completed" and
         check.get("conclusion") == "success", "native check issuer or subject mismatch")
    steps = job.get("steps")
    need(type(steps) is list and len(steps) >= len(expected_steps) + 2 and
         all(s.get("status") == "completed" and s.get("conclusion") == "success" for s in steps), "native step or post hook did not succeed")
    numbers = [s.get("number") for s in steps]
    need(all(integer(n) for n in numbers) and numbers == sorted(set(numbers)), "ambiguous native step identities")
    need([s.get("name") for s in steps[:len(expected_steps) + 1]] == ["Set up job", *expected_steps] and
         steps[-1].get("name") == "Complete job" and
         all(s.get("name", "").startswith("Post ") for s in steps[len(expected_steps) + 1:-1]), "native required step sequence mismatch")
    return True


class Controller:
    def __init__(self, shared, consumer, grant_raw, harness, temporary):
        self.shared, self.consumer = shared, consumer
        self.grant_raw, self.harness, self.temporary = grant_raw, sha(harness), Path(temporary)
        self.grant = authorization(grant_raw)
        shared.before_write = lambda: self.mutation_authorized(shared, SHARED_ID)
        consumer.before_write = lambda: self.mutation_authorized(consumer, CONSUMER_ID)
        self.generated = 0
        self.adapter = adapter()
        self.adapter.git = run_git
        try:
            self.impact = impact_catalog(Path(__file__).with_name("consumer-compatibility-impact.json").read_bytes())
        except (OSError, Refusal, KeyError, TypeError, ValueError):
            self.impact = []
            print("Impact catalog unavailable; full qualification is required.")

    def resource(self, api, identifier):
        repository = api.request("")
        need(type(repository.get("id")) is int and repository["id"] == identifier and
             repository.get("full_name") == api.repo, "repository identity changed")

    def mutation_authorized(self, api, identifier):
        authorization(self.grant_raw)
        self.resource(api, identifier)

    def current(self):
        authorization(self.grant_raw)
        self.resource(self.shared, SHARED_ID)
        self.resource(self.consumer, CONSUMER_ID)
        need(self.shared.branch("main") == self.harness, "checking source is no longer current")
        base = self.consumer.branch("dev")
        need(base is not None, "consumer branch is unavailable")
        return base

    def admit(self, number, expected_head):
        pr = self.shared.request("/pulls/" + str(number))
        need(pr["head"]["sha"] == expected_head, "shared candidate moved")
        reviews = self.shared.listing(f"/pulls/{number}/reviews")
        response = self.shared.request("/graphql", "POST", {"query": REVIEW_QUERY, "variables": {"number": number}})
        need(not response.get("errors"), "review decision unavailable")
        decision = response["data"]["repository"]["pullRequest"]
        need(decision["headRefOid"] == expected_head, "review subject moved")
        eligible(pr, reviews, lambda login: self.consumer.request("/collaborators/" + login + "/permission"),
                 decision["reviewDecision"])
        return pr

    def owned_check(self, head):
        try:
            checks = self.shared.listing("/commits/" + sha(head) + "/check-runs?filter=all&check_name=" +
                                         urllib.parse.quote(CHECK), "check_runs")
        except IncompleteInventory as error:
            self.invalidate_checks(head, error.items)
            raise
        owned = [c for c in checks if c.get("name") == CHECK and c.get("app", {}).get("id") == self.grant["reporting_app_id"]]
        need(all(integer(c.get("id")) and c.get("head_sha") == head for c in owned), "public check subject mismatch")
        if len(owned) > 1:
            # Ambiguity must not leave this App's previous successes intact.
            self.invalidate_checks(head, owned)
        need(len(owned) <= 1, "ambiguous public check ownership")
        if owned:
            need(integer(owned[0].get("id")) and owned[0].get("head_sha") == head, "public check subject mismatch")
            return owned[0]
        return None

    def invalidate_checks(self, head, checks):
        """PATCH only positively bound owned IDs; preserve failures and continue."""
        sha(head)
        prior = getattr(self.shared, "blocking", False)
        self.shared.blocking = True
        verified = True
        try:
            for check in checks:
                if type(check) is not dict or type(check.get("app")) is not dict:
                    verified = False
                    continue
                if check.get("name") != CHECK or check["app"].get("id") != self.grant["reporting_app_id"]:
                    continue
                try:
                    need(integer(check.get("id")) and check.get("head_sha") == head, "blocker subject mismatch")
                    payload = check_payload(head, digest("inventory-refused:" + head), "completed", "action_required")
                    payload.pop("head_sha")
                    payload["details_url"] = None
                    if (all(check.get(k) == v for k, v in payload.items() if k != "output") and
                            type(check.get("output")) is dict and
                            all(check["output"].get(k) == v for k, v in payload["output"].items())):
                        continue
                    path = "/check-runs/" + str(check["id"])
                    self.shared.request(path, "PATCH", payload)
                    observed = self.shared.request(path)
                    need(type(observed) is dict and type(observed.get("app")) is dict and
                         type(observed.get("output")) is dict, "invalid blocker readback")
                    need(observed.get("head_sha") == head and observed.get("app", {}).get("id") == self.grant["reporting_app_id"] and
                         all(observed.get(k) == v for k, v in payload.items() if k != "output") and
                         all((observed.get("output") or {}).get(k) == v for k, v in payload["output"].items()),
                         "blocker readback unconfirmed")
                except (Refusal, KeyError, TypeError, ValueError, OSError):
                    verified = False
            return verified
        finally:
            self.shared.blocking = prior

    def block_known(self, head):
        prior = getattr(self.shared, "blocking", False)
        self.shared.blocking = True
        complete = True
        try:
            try:
                checks = self.shared.listing("/commits/" + sha(head) + "/check-runs?filter=all&check_name=" +
                                             urllib.parse.quote(CHECK), "check_runs")
            except IncompleteInventory as error:
                checks, complete = error.items, False
            return self.invalidate_checks(head, checks) and complete
        finally:
            self.shared.blocking = prior

    def block_inventory(self, prs):
        heads = set()
        for pr in prs:
            head = pr.get("head") if type(pr) is dict else None
            if (type(head) is dict and type(head.get("repo")) is dict and
                    head["repo"].get("id") == SHARED_ID and isinstance(head.get("sha"), str) and re.fullmatch(HEX40, head["sha"])):
                heads.add(head["sha"])
        unverified = 0
        for head in heads:
            try:
                unverified += not self.block_known(head)
            except (Refusal, KeyError, TypeError, ValueError, OSError):
                unverified += 1
        print(f"Inventory refused; observed heads: {len(heads)}; unverified blocking: {unverified}. Unseen heads remain unverified.")

    def report(self, head, identity, status, conclusion=None, number=None, exempt=False):
        authorization(self.grant_raw)
        owned = self.owned_check(head)
        payload = check_payload(head, identity, status, conclusion, number, exempt)
        def same_output(observed):
            output = observed.get("output") or {}
            return (all(output.get(k) == v for k, v in payload["output"].items()) and
                    output.get("text") in (None, "") and output.get("annotations_count", 0) == 0)
        if owned:
            if (owned.get("external_id") == identity and owned.get("status") == status and
                    owned.get("conclusion") == conclusion and same_output(owned) and
                    owned.get("details_url") == payload.get("details_url")):
                return owned
            path = "/check-runs/" + str(owned["id"])
            payload.pop("head_sha")
            payload.setdefault("details_url", None)
            if status != "completed":
                payload.update(conclusion=None, completed_at=None)
            result = self.shared.request(path, "PATCH", payload)
        else:
            attempted = self.__dict__.setdefault("check_create_attempted", set())
            need(head not in attempted, "public check creation outcome remains unknown")
            attempted.add(head)
            result = self.shared.request("/check-runs", "POST", payload)
        need(integer(result.get("id")), "public write acknowledgement missing")
        observed = self.shared.request("/check-runs/" + str(result["id"]))
        need(observed.get("name") == CHECK and observed.get("app", {}).get("id") == self.grant["reporting_app_id"] and
             observed.get("head_sha") == head and observed.get("external_id") == identity and
             observed.get("status") == status and observed.get("conclusion") == conclusion and
             same_output(observed) and (number is None or observed.get("details_url") == payload["details_url"]),
             "public result readback mismatch")
        return observed

    def material(self, number, head, base):
        shared_commit = self.shared.commit(head)
        consumer_commit = self.consumer.commit(base)
        harness_commit = self.shared.commit(self.harness)
        candidate_files = self.shared.tree(shared_commit["tree"]["sha"])
        harness_files = self.shared.tree(harness_commit["tree"]["sha"])
        need(all(mode in ("100644", "100755") for mode, _, _ in candidate_files.values()), "unsupported candidate source mode")
        self.consumer.tree(consumer_commit["tree"]["sha"])
        value, identity, branch = plan(number, head, shared_commit["tree"]["sha"], base,
                                       consumer_commit["tree"]["sha"], self.harness, harness_commit["tree"]["sha"])
        directory = self.temporary / identity
        directory.mkdir(exist_ok=True)
        candidate_repo, consumer_repo = directory / "candidate.git", directory / "consumer.git"
        if not candidate_repo.exists():
            fetch(candidate_repo, self.shared, head)
        if not consumer_repo.exists():
            fetch(consumer_repo, self.consumer, base)
        self.adapter.candidate(candidate_repo, head, value["shared_tree"])
        self.adapter.revision(consumer_repo, base, value["consumer_tree"])
        source = run_git(consumer_repo, "show", base + ":.github/workflows/ci.yml").decode()
        generated = self.adapter.generate(source, head, value["shared_tree"], base, value["consumer_tree"], branch)
        original = self.adapter.workflow(source)["jobs"]["CI"]
        projected = self.adapter.parse(generated)["jobs"]["compatibility"]
        return value, identity, branch, generated, original, projected, no_impact(
            harness_files, candidate_files, value["consumer_tree"], self.impact)

    def capacity(self, branch):
        if self.generated >= 2:
            return False
        prs = self.consumer.listing("/pulls?state=all")
        return publication_capacity(prs, self.consumer.fixture_refs(), self.grant["fixture_bot_id"],
                                    branch, dt.datetime.now(dt.timezone.utc))

    def fixture(self, value, identity, branch, generated):
        """Publish at most one new immutable fixture. Read native state first."""
        ref = self.consumer.branch(branch)
        prs = self.consumer.listing("/pulls?state=all&head=" + urllib.parse.quote("ForgingAlpha:" + branch))
        need(len(prs) <= 1, "ambiguous fixture PR")
        body = private_body(value, identity, generated)
        if not prs and not self.capacity(branch):
            return None
        if ref is None:
            need(not prs, "fixture PR exists without its ref")
            authorization(self.grant_raw)
            blob = self.consumer.request("/git/blobs", "POST", {"content": generated, "encoding": "utf-8"})
            expected_blob = hashlib.sha1(b"blob " + str(len(generated.encode())).encode() + b"\0" + generated.encode()).hexdigest()
            need(blob.get("sha") == expected_blob, "published workflow blob mismatch")
            tree = self.consumer.request("/git/trees", "POST", {"base_tree": value["consumer_tree"], "tree": [
                {"path": WORKFLOW, "mode": "100644", "type": "blob", "sha": expected_blob}]})
            sha(tree.get("sha"))
            parent = self.consumer.commit(value["consumer_commit"])
            date = parent["committer"]["date"]
            # Fixed content/time makes an interrupted pre-ref create reproducible.
            author = {"name": "consumer-compatibility[bot]", "email": "consumer-compatibility@users.noreply.github.com", "date": date}
            commit = self.consumer.request("/git/commits", "POST", {
                "message": "Disposable consumer compatibility " + identity, "tree": tree["sha"],
                "parents": [value["consumer_commit"]], "author": author, "committer": author})
            ref = sha(commit.get("sha"))
            # Admission and all selections must still hold before native execution.
            need(self.current() == value["consumer_commit"], "consumer moved before publication")
            self.admit(value["pull_request"], value["shared_commit"])
            self.consumer.request("/git/refs", "POST", {"ref": "refs/heads/" + branch, "sha": ref})
            need(self.consumer.branch(branch) == ref, "fixture ref readback mismatch")
        self.verify_commit(ref, value, generated)
        if not prs:
            need(self.current() == value["consumer_commit"], "consumer moved before PR creation")
            self.admit(value["pull_request"], value["shared_commit"])
            if not self.capacity(branch):
                return None
            # Count a recovered ref's PR too. An outcome-unknown publication
            # consumes this invocation's allowance until the next readback.
            self.generated += 1
            self.consumer.request("/pulls", "POST", {"title": "Disposable consumer compatibility " + identity[:12],
                                  "head": branch, "base": "dev", "body": body, "draft": True})
            prs = self.consumer.listing("/pulls?state=all&head=" + urllib.parse.quote("ForgingAlpha:" + branch))
        need(len(prs) == 1, "fixture PR acknowledgement ambiguous")
        pr = prs[0]
        self.verify_pr(pr, ref, branch, value, body)
        need(pr["state"] == "open", "closed fixture is not reopened")
        return pr

    def workflow_bytes(self, ref):
        blob = self.consumer.request("/contents/" + WORKFLOW + "?ref=" + sha(ref))
        need(blob.get("type") == "file" and blob.get("encoding") == "base64", "fixture workflow unavailable")
        try:
            raw = base64.b64decode(blob["content"].replace("\n", ""), validate=True)
            need(len(raw) <= 131072, "fixture workflow exceeds supported bound")
            return raw.decode("utf-8")
        except (ValueError, UnicodeError) as exc:
            raise Refusal("invalid fixture encoding") from exc

    def verify_commit(self, ref, value, generated):
        commit = self.consumer.commit(ref)
        need([p.get("sha") for p in commit.get("parents", [])] == [value["consumer_commit"]], "fixture parent mismatch")
        before = self.consumer.tree(value["consumer_tree"])
        after = self.consumer.tree(commit["tree"]["sha"])
        blob_hash = hashlib.sha1(b"blob " + str(len(generated.encode())).encode() + b"\0" + generated.encode()).hexdigest()
        need(WORKFLOW not in before and after == {**before, WORKFLOW: ("100644", "blob", blob_hash)},
             "fixture tree or workflow mode mismatch")
        comparison = self.consumer.request("/compare/" + value["consumer_commit"] + "..." + ref)
        need(comparison.get("total_commits") == 1 and comparison.get("ahead_by") == 1 and
             comparison.get("behind_by") == 0, "fixture history mismatch")
        files = comparison.get("files")
        need(type(files) is list and len(files) == 1 and files[0].get("filename") == WORKFLOW and
             files[0].get("status") == "added", "fixture must only add its generated workflow")
        need(self.workflow_bytes(ref) == generated, "fixture workflow changed")

    def verify_pr(self, pr, ref, branch, value, body, historical=False):
        need(integer(pr.get("number")) and pr.get("body") == body and
             pr.get("draft") is True and
             pr.get("user", {}).get("id") == self.grant["fixture_bot_id"] and pr["user"].get("type") == "Bot" and
             pr["head"]["sha"] == ref and pr["head"]["ref"] == branch and
             pr["head"]["repo"]["id"] == CONSUMER_ID and pr["base"]["repo"]["id"] == CONSUMER_ID and
             pr["base"]["ref"] == "dev" and (historical or pr["base"]["sha"] == value["consumer_commit"]),
             "fixture PR custody mismatch")

    def retire(self):
        """Close only obsolete owned fixtures; preserve their refs and evidence."""
        for listed in self.consumer.listing("/pulls?state=open&base=dev"):
            if (listed.get("user", {}).get("id") != self.grant["fixture_bot_id"] or
                    not re.fullmatch(BRANCH, listed.get("head", {}).get("ref", ""))):
                continue
            need(integer(listed.get("number")), "invalid fixture identity")
            pr = self.consumer.request("/pulls/" + str(listed["number"]))
            need(pr.get("state") == "open" and pr.get("merged") is False, "fixture state changed")
            value, identity, branch, workflow_hash = retained_plan(pr.get("body"))
            head = sha(pr["head"]["sha"])
            self.verify_pr(pr, head, branch, value, pr["body"], historical=True)
            need(self.consumer.branch(branch) == head, "fixture ref changed")
            generated = self.workflow_bytes(head)
            need(digest(generated) == workflow_hash, "retained fixture bytes changed")
            self.verify_commit(head, value, generated)
            public = self.shared.request("/pulls/" + str(value["pull_request"]))
            need(public["base"]["repo"]["id"] == SHARED_ID and public["base"]["ref"] == "main" and
                 public["head"]["repo"]["id"] == SHARED_ID and public.get("state") in ("open", "closed"),
                 "retired fixture public subject mismatch")
            base = self.current()
            obsolete = (public.get("state") == "closed" or public["head"]["sha"] != value["shared_commit"] or
                        base != value["consumer_commit"] or self.harness != value["harness_commit"])
            if not obsolete:
                continue
            # A changed consumer/harness can stale the same public head. Revoke
            # its successful assertion before removing its live fixture.
            if public.get("state") == "open" and public["head"]["sha"] == value["shared_commit"]:
                check = self.owned_check(value["shared_commit"])
                if check and check.get("external_id") == identity:
                    self.report(value["shared_commit"], identity, "queued")
            observed = self.consumer.request("/pulls/" + str(pr["number"]))
            need(observed.get("state") == "open" and observed.get("merged") is False and
                 self.consumer.branch(branch) == head, "fixture moved before retirement")
            self.verify_pr(observed, head, branch, value, pr["body"], historical=True)
            self.consumer.request("/pulls/" + str(pr["number"]), "PATCH", {"state": "closed"})
            observed = self.consumer.request("/pulls/" + str(pr["number"]))
            self.verify_pr(observed, head, branch, value, pr["body"], historical=True)
            need(observed.get("state") == "closed" and observed.get("merged") is False and
                 self.consumer.branch(branch) == head, "fixture closure readback mismatch")

    def observe(self, pr, branch, path, job):
        runs = self.consumer.listing("/actions/workflows/" + urllib.parse.quote(path.rsplit("/", 1)[1], safe="") +
                                     "/runs?event=pull_request&head_sha=" + pr["head"]["sha"] +
                                     "&branch=" + urllib.parse.quote(branch, safe=""), "workflow_runs", limit=100)
        if not runs:
            return False
        need(len(runs) == 1, "additional workflow execution lacks diagnostic authorization")
        need(all(integer(r.get("id")) for r in runs), "invalid run inventory")
        run = runs[0]
        run = self.consumer.request("/actions/runs/" + str(run["id"]))
        # Re-read exact latest attempt; callbacks never supply authority or results.
        jobs = self.consumer.listing(f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs", limit=100)
        checks = []
        for item in jobs:
            url = item.get("check_run_url", "")
            match = re.fullmatch(r"https://api\.github\.com/repos/ForgingAlpha/container-foundation/check-runs/([0-9]+)", url)
            need(match is not None, "native check locator mismatch")
            checks.append(self.consumer.request("/check-runs/" + match[1]))
        return native_success(run, jobs, checks, pr, path, branch, [s["name"] for s in job["steps"]], job["name"])

    def reconcile(self, pr):
        number, head = pr["number"], sha(pr["head"]["sha"])
        identity = digest(canonical({"pull_request": number, "head": head, "state": "awaiting-admission"}))
        try:
            existing = self.owned_check(head)
            base = self.current()
            self.admit(number, head)
            value, identity, branch, generated, original, projected, exempt = self.material(number, head, base)
            # Preserve an unchanged success while re-observing it. A known changed
            # plan is invalidated before any replacement fixture is published.
            if not (existing and existing.get("external_id") == identity and
                    existing.get("status") == "completed" and existing.get("conclusion") == "success"):
                self.report(head, identity, "in_progress")
            if exempt:
                need(self.current() == base, "consumer moved before impact result")
                self.admit(number, head)
                self.report(head, identity, "completed", "success", exempt=True)
                return
            pr = self.fixture(value, identity, branch, generated)
            if pr is None:
                self.report(head, identity, "queued")
                return
            outcomes = [self.observe(pr, branch, WORKFLOW, projected),
                        self.observe(pr, branch, ".github/workflows/ci.yml", original)]
            if not all(outcomes):
                self.report(head, identity, "in_progress", number=pr["number"])
                return
            need(self.current() == base, "consumer moved during qualification")
            self.admit(number, head)
            # Re-observe the latest attempts before publication; previous attempts do not carry.
            fresh = self.consumer.request("/pulls/" + str(pr["number"]))
            self.verify_pr(fresh, pr["head"]["sha"], branch, value, private_body(value, identity, generated))
            need(fresh["state"] == "open" and self.consumer.branch(branch) == fresh["head"]["sha"], "fixture changed during reporting")
            need(self.observe(fresh, branch, WORKFLOW, projected) and
                 self.observe(fresh, branch, ".github/workflows/ci.yml", original), "latest native attempt is not complete")
            need(self.current() == base, "selected inputs moved before success")
            self.admit(number, head)
            self.report(head, identity, "completed", "success", pr["number"])
        except Pending:
            self.report(head, identity, "queued")
        except NativeFailure:
            self.report(head, identity, "completed", "failure")
        except (Refusal, KeyError, TypeError, ValueError, OSError):
            self.report(head, identity, "completed", "action_required")
            raise

    def sweep(self):
        # Complete inventory first: never silently qualify a truncated selection.
        try:
            prs = self.shared.listing("/pulls?state=open&base=main", limit=1000)
        except IncompleteInventory as error:
            self.block_inventory(error.items)
            raise
        same_repo = [p for p in prs if p.get("head", {}).get("repo", {}).get("id") == SHARED_ID]
        heads = [sha(p["head"]["sha"]) for p in same_repo]
        if len(prs) > 20 or len(heads) != len(set(heads)):
            self.block_inventory(prs)
            raise Refusal("unsupported PR inventory; no successful assertion")
        failed = False
        for pr in same_repo:
            try:
                self.reconcile(pr)
            except (Refusal, KeyError, TypeError, ValueError, OSError):
                failed = True
                # Public/provider text and private evidence are never printed.
                print("Qualification remains blocked for an observed shared candidate.")
        self.retire()
        need(not failed, "one or more candidates remain blocked")


def runtime_context(env):
    need(env.get("GITHUB_REPOSITORY") == CONSUMER and env.get("GITHUB_REPOSITORY_ID") == str(CONSUMER_ID) and
         env.get("GITHUB_REF") == "refs/heads/dev" and
         env.get("GITHUB_EVENT_NAME") in ("schedule", "push", "workflow_run", "workflow_dispatch"), "untrusted caller context")
    need(env.get("CC_WORKFLOW_REPOSITORY") == SHARED and
         env.get("CC_WORKFLOW_REF") == SHARED + "/" + CONTROLLER + "@refs/heads/main", "untrusted defining workflow")
    return sha(env.get("CC_WORKFLOW_SHA"))


def main():
    try:
        harness = runtime_context(os.environ)
        grant = authorization(os.environ.get("CC_AUTHORIZATION", ""))
        need(str(grant["reporting_app_id"]) == os.environ.get("CC_REPORTING_APP_ID") and
             str(grant["fixture_app_id"]) == os.environ.get("CC_FIXTURE_APP_ID") and
             str(grant["fixture_bot_id"]) == os.environ.get("CC_FIXTURE_BOT_ID"), "configured App identity mismatch")
        source = Path(__file__).resolve().parents[1]
        need(run_git(source, "rev-parse", "HEAD").decode().strip() == harness, "checking source checkout mismatch")
        if os.environ.get("CC_MODE") == "validate":
            need(API(SHARED, "").branch("main") == harness, "defining source is not current")
            print("Trusted source and protected authorization projection validated.")
            return
        need(os.environ.get("CC_MODE") == "reconcile", "unsupported controller mode")
        shared_token, private_token = os.environ.get("CC_SHARED_TOKEN"), os.environ.get("CC_PRIVATE_TOKEN")
        need(shared_token and private_token, "scoped connection unavailable")
        with tempfile.TemporaryDirectory(prefix="consumer-compatibility-", dir=os.environ["RUNNER_TEMP"]) as temporary:
            controller = Controller(API(SHARED, shared_token), API(CONSUMER, private_token),
                                    os.environ["CC_AUTHORIZATION"], harness, temporary)
            controller.sweep()
    except (Refusal, KeyError, TypeError, ValueError, OSError):
        raise SystemExit("Consumer compatibility is incomplete. Inspect the private controller configuration and exact native evidence; no success is inferred.") from None


if __name__ == "__main__":
    main()
