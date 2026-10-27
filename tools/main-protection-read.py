#!/usr/bin/env python3
"""Human-run, fixed-scope GitHub protection observations; never applies settings."""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


REPOSITORIES = {
    ".github": 1137664016,
    "control-plane": 739528598,
    "container-foundation": 1428636846,
}
OWNER = "ForgingAlpha"
HUMAN = "leosmigel"
# Response projections exclude credentials, content bodies, API messages and URLs.
FIELDS = frozenset("""
id login slug name type source source_type target enforcement conditions rules
full_name default_branch allow_auto_merge allow_merge_commit allow_squash_merge allow_rebase_merge
ruleset_id ruleset_source_type ruleset_source
ref_name include exclude repository_name repository_id repository_ids protected
parameters bypass_actors actor_id actor_type bypass_mode current_user_can_bypass
required_pull_request_reviews required_approving_review_count dismiss_stale_reviews
require_code_owner_reviews require_last_push_approval dismissal_restrictions
bypass_pull_request_allowances users teams apps enforce_admins enabled
required_status_checks strict contexts checks context app_id integration_id
restrictions allow_force_pushes allow_deletions block_creations required_signatures
required_linear_history required_conversation_resolution allow_fork_syncing lock_branch
required_deployments environments required_code_scanning_tools code_scanning_tools
tool security_alerts_threshold alerts_threshold required_workflows workflows
repository_id path ref sha do_not_enforce_on_create update_allows_fetch_and_merge
required_status_checks_enforcement_level allowed_merge_methods merge_queue
grouping_strategy max_entries_to_build min_entries_to_merge max_entries_to_merge
min_entries_to_merge_wait_minutes check_response_timeout_minutes
default_workflow_permissions can_approve_pull_request_reviews
dismiss_stale_reviews_on_push require_code_owner_review required_review_thread_resolution
strict_required_status_checks_policy required_reviewers dismissal_restriction allowed_actors
require_extra_approval_for_unattributed_changes file_patterns minimum_approvals reviewer
operator pattern negate
review_on_push review_draft_pull_requests permissions admin maintain push pull triage
allow_update_branch archived delete_branch_on_merge disabled private visibility web_commit_signoff_required
""".split())
METADATA_ONLY = frozenset("""
url html_url _links node_id created_at updated_at avatar_url gravatar_id events_url
followers_url following_url gists_url organizations_url received_events_url repos_url
starred_url subscriptions_url download_url git_url content encoding size links
""".split())
BOOL_FIELDS = frozenset("""
protected enabled strict dismiss_stale_reviews require_code_owner_reviews require_last_push_approval
dismiss_stale_reviews_on_push require_code_owner_review required_review_thread_resolution
strict_required_status_checks_policy require_extra_approval_for_unattributed_changes
do_not_enforce_on_create update_allows_fetch_and_merge can_approve_pull_request_reviews
allow_auto_merge allow_merge_commit allow_squash_merge allow_rebase_merge negate
review_on_push review_draft_pull_requests admin maintain push pull triage
allow_update_branch archived delete_branch_on_merge disabled private web_commit_signoff_required
""".split())
INT_FIELDS = frozenset("""
id actor_id ruleset_id app_id integration_id repository_id required_approving_review_count
minimum_approvals max_entries_to_build min_entries_to_merge max_entries_to_merge
min_entries_to_merge_wait_minutes check_response_timeout_minutes
""".split())
STRING_FIELDS = frozenset("""
login slug name type source source_type target enforcement actor_type bypass_mode
current_user_can_bypass ruleset_source_type ruleset_source full_name default_branch
context path ref sha tool security_alerts_threshold alerts_threshold
default_workflow_permissions grouping_strategy operator pattern
visibility
""".split())
STRING_LISTS = frozenset("contexts include exclude environments allowed_merge_methods file_patterns".split())
OBJECT_LISTS = frozenset("rules bypass_actors required_reviewers allowed_actors users teams apps checks workflows code_scanning_tools".split())
OBJECT_FIELDS = frozenset("""
parameters conditions ref_name repository_name repository_id required_pull_request_reviews
dismissal_restrictions bypass_pull_request_allowances enforce_admins restrictions
required_signatures required_linear_history required_conversation_resolution allow_fork_syncing
lock_branch allow_force_pushes allow_deletions block_creations required_deployments
dismissal_restriction reviewer
permissions
""".split()) - {"repository_id"}
ACTOR_TYPES = {"Integration", "OrganizationAdmin", "RepositoryRole", "Team", "DeployKey",
               "User", "EnterpriseOwner", "EnterpriseRole"}


def valid_structure(value, depth=0):
    if depth > 12:
        return False
    if isinstance(value, list):
        return all(valid_structure(item, depth + 1) for item in value)
    if not isinstance(value, dict):
        return True
    for key, item in value.items():
        if item is None and key in {"restrictions", "required_status_checks",
                                    "required_pull_request_reviews", "required_deployments"}:
            continue
        if key in BOOL_FIELDS and type(item) is not bool:
            return False
        if key in INT_FIELDS and not (type(item) is int and item >= 0 or
                                      key == "repository_id" and isinstance(item, dict) or
                                      item is None and key in {"actor_id", "app_id", "integration_id"}):
            return False
        if key in STRING_FIELDS and not isinstance(item, str):
            return False
        if key in STRING_LISTS and not (isinstance(item, list) and all(isinstance(x, str) for x in item)):
            return False
        if key in OBJECT_LISTS and not (isinstance(item, list) and all(isinstance(x, dict) for x in item)):
            return False
        if key in OBJECT_FIELDS and not isinstance(item, dict):
            return False
        if key == "required_status_checks" and not isinstance(item, (dict, list)):
            return False
        if key == "required_status_checks" and isinstance(item, list):
            if not all(isinstance(row, dict) and isinstance(row.get("context"), str) for row in item):
                return False
        if key == "bypass_actors":
            for actor in item:
                if (not isinstance(actor.get("actor_type"), str)
                        or not isinstance(actor.get("bypass_mode"), str)
                        or actor["actor_type"] not in ACTOR_TYPES
                        or actor["bypass_mode"] not in {"always", "pull_request", "exempt"}
                        or "actor_id" not in actor):
                    return False
                if actor["actor_type"] not in {"OrganizationAdmin", "EnterpriseOwner", "DeployKey"}:
                    if not positive_id(actor["actor_id"]):
                        return False
        if key in FIELDS and not valid_structure(item, depth + 1):
            return False
    return True


def valid_payload(endpoint, payload):
    if not valid_structure(payload):
        return False
    if endpoint.endswith("/rules/branches/main"):
        return all(isinstance(row, dict) and isinstance(row.get("type"), str)
                   and positive_id(row.get("ruleset_id"))
                   and isinstance(row.get("ruleset_source_type"), str)
                   and row["ruleset_source_type"] in {"Repository", "Organization", "Enterprise"}
                   and isinstance(row.get("ruleset_source"), str) for row in payload)
    if "/rulesets?" in endpoint:
        return all(isinstance(row, dict) and positive_id(row.get("id"))
                   and isinstance(row.get("source_type"), str)
                   and row["source_type"] in {"Repository", "Organization", "Enterprise"}
                   and isinstance(row.get("source"), str) for row in payload)
    if re.search(r"/rulesets/[1-9][0-9]*$", endpoint):
        return type(payload.get("id")) is int and payload["id"] == int(endpoint.rsplit("/", 1)[1])
    return True


def project(value, omitted, depth=0):
    """Keep only explicitly selected settings, preserving absent versus empty."""
    if depth > 12:
        return {"observation": "depth_limit"}
    if isinstance(value, dict):
        omitted.update(key for key in value if key not in FIELDS and key not in METADATA_ONLY)
        return {key: project(item, omitted, depth + 1)
                for key, item in value.items() if key in FIELDS}
    if isinstance(value, list):
        return [project(item, omitted, depth + 1) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return None


def positive_id(value):
    return type(value) is int and value > 0


def allowed_endpoint(endpoint):
    if endpoint == "user":
        return True
    for name in REPOSITORIES:
        root = f"repos/{OWNER}/{name}"
        if endpoint == root or endpoint in {
            f"{root}/branches/main", f"{root}/branches/main/protection",
            f"{root}/rules/branches/main",
            f"{root}/rulesets?includes_parents=true&per_page=100",
            f"{root}/actions/permissions/workflow",
            f"{root}/contents/.github/CODEOWNERS?ref=main",
        }:
            return True
        if re.fullmatch(re.escape(root) + r"/rulesets/[1-9][0-9]*", endpoint):
            return True
    return bool(re.fullmatch(
        r"(?:orgs/ForgingAlpha|enterprises/alphaapps)/rulesets/[1-9][0-9]*", endpoint))


class Reader:
    def __init__(self, gh):
        self.gh = gh

    def get(self, endpoint, expected=dict, limit=None):
        if not allowed_endpoint(endpoint):
            raise ValueError("endpoint outside fixed diagnostic scope")
        command = [self.gh, "api", "--hostname", "github.com", "--method", "GET",
                   "--include", "--header", "Accept: application/vnd.github+json", endpoint]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30,
                                    check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "unavailable"}, None
        # gh --include emits HTTP status + headers, then the JSON body.
        header, separator, body = result.stdout.replace("\r\n", "\n").partition("\n\n")
        match = re.match(r"HTTP/\S+ (\d{3})(?: |\n|$)", header)
        if not separator or not match:
            return {"status": "unavailable"}, None
        status = int(match.group(1))
        observation = {"http_status": status}
        if not 200 <= status < 300 or result.returncode != 0:
            observation["status"] = "http_error" if not 200 <= status < 300 else "unavailable"
            return observation, None
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            observation["status"] = "invalid_json"
            return observation, None
        if not isinstance(payload, expected) or not valid_payload(endpoint, payload):
            observation["status"] = "invalid_schema"
            if expected is list:
                observation["inventory_complete"] = False
            return observation, None
        omitted = set()
        observation.update(status="observed", value=project(payload, omitted))
        required = set()
        if endpoint == "user":
            required = {"id", "login", "type"}
        elif endpoint in {f"repos/{OWNER}/{name}" for name in REPOSITORIES}:
            required = {"id", "full_name", "default_branch", "allow_auto_merge"}
        elif endpoint.endswith("/branches/main/protection"):
            required = {"enforce_admins"}
        elif endpoint.endswith("/actions/permissions/workflow"):
            required = {"default_workflow_permissions", "can_approve_pull_request_reviews"}
        elif re.search(r"/rulesets/[1-9][0-9]*$", endpoint):
            required = {"id", "enforcement", "rules", "conditions", "bypass_actors"}
        observation["missing_fields"] = sorted(required - payload.keys()) if isinstance(payload, dict) else []
        observation["unreported_fields"] = sorted(omitted)
        observation["projection_complete"] = not omitted and not observation["missing_fields"]
        if isinstance(payload, list):
            next_page = bool(re.search(r'^link:.*rel="next"', header,
                                       flags=re.IGNORECASE | re.MULTILINE))
            observation["inventory_complete"] = not omitted and not next_page and not (
                limit is not None and len(payload) >= limit)
        return observation, payload


def ruleset_references(inventory, effective):
    found = set()
    for rows, id_key, type_key, source_key in (
        (inventory or [], "id", "source_type", "source"),
        (effective or [], "ruleset_id", "ruleset_source_type", "ruleset_source"),
    ):
        for row in rows:
            if not isinstance(row, dict) or not positive_id(row.get(id_key)):
                continue
            found.add((row[id_key], str(row.get(type_key, "")),
                       str(row.get(source_key, ""))))
    return sorted(found)


def collect(reader):
    identity, user = reader.get("user")
    if not user or user.get("type") != "User" or user.get("login") != HUMAN:
        raise ValueError("expected the human GitHub account leosmigel; no repository reads made")
    report = {
        "format": 1,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": "GET-only observations; no settings changed",
        "qualification": "unqualified: this report cannot certify agent exclusion or grants",
        "limitations": "Missing, forbidden, malformed and omitted fields remain unknown. "
                       "Ruleset bypass actors require write access to that ruleset. "
                       "No protected write probe, installation or outage test performed.",
        "identity": identity,
        "repositories": {},
    }
    identity["value"] = {key: identity["value"][key] for key in ("id", "login", "type")
                         if key in identity["value"]}
    for name, repository_id in REPOSITORIES.items():
        root = f"repos/{OWNER}/{name}"
        observations = report["repositories"][f"{OWNER}/{name}"] = {}
        metadata, repository = reader.get(root)
        if repository:
            metadata["value"] = {key: metadata["value"][key] for key in
                                 ("id", "full_name", "default_branch", "allow_auto_merge",
                                  "allow_merge_commit", "allow_squash_merge", "allow_rebase_merge")
                                 if key in metadata["value"]}
        observations["repository"] = metadata
        if (not repository or type(repository.get("id")) is not int
                or repository["id"] != repository_id
                or repository.get("full_name") != f"{OWNER}/{name}"):
            observations["identity"] = "unavailable_or_mismatched; dependent reads refused"
            continue
        observations["identity"] = "matched numeric repository ID"
        for label, endpoint in (
            ("main", "branches/main"), ("classic_protection", "branches/main/protection"),
            ("workflow_permissions", "actions/permissions/workflow"),
            ("codeowners_metadata", "contents/.github/CODEOWNERS?ref=main"),
        ):
            observation, payload = reader.get(f"{root}/{endpoint}")
            if label == "main" and payload:
                commit = payload.get("commit")
                sha = commit.get("sha") if isinstance(commit, dict) else None
                observation["value"] = {"name": observation["value"].get("name"),
                                        "protected": observation["value"].get("protected"),
                                        "sha": sha if isinstance(sha, str) else None}
                if not isinstance(sha, str):
                    observation["status"] = "invalid_schema"
            observations[label] = observation
        observations["effective_rules"], effective = reader.get(
            f"{root}/rules/branches/main", list, limit=30)
        observations["ruleset_inventory"], inventory = reader.get(
            f"{root}/rulesets?includes_parents=true&per_page=100", list, limit=100)
        references = ruleset_references(inventory, effective)
        observations["ruleset_detail_limit_reached"] = len(references) > 100
        observations["ruleset_details"] = []
        for ruleset_id, source_type, source in references[:100]:
            endpoints = [f"{root}/rulesets/{ruleset_id}"]
            if source_type == "Organization" and source == OWNER:
                endpoints.append(f"orgs/{OWNER}/rulesets/{ruleset_id}")
            elif source_type == "Enterprise" and source == "alphaapps":
                endpoints.append(f"enterprises/alphaapps/rulesets/{ruleset_id}")
            for endpoint in endpoints:
                detail, payload = reader.get(endpoint)
                detail["endpoint"] = endpoint
                detail["bypass_actors_visibility"] = (
                    "observed" if payload is not None and isinstance(payload.get("bypass_actors"), list)
                    else "unknown")
                observations["ruleset_details"].append(detail)
    return report


def write_report(report):
    directory = Path(tempfile.mkdtemp(prefix="alphaapps-shared-main-read-"))
    os.chmod(directory, 0o700)
    path = directory / "REPORT.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return path


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    gh = shutil.which("gh")
    if gh is None:
        print("STOP: existing GitHub CLI is unavailable; nothing installed or changed.")
        return 2
    try:
        report = collect(Reader(gh))
        path = write_report(report)
    except ValueError as error:
        print(f"STOP: {error}")
        return 2
    except OSError:
        print("STOP: private report could not be written; no settings changed.")
        return 2
    print("GET-only observations complete; no settings changed. Protection remains unqualified.")
    print(f"Private report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
