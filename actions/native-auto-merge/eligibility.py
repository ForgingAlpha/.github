"""Positive admission for a single qualified PR, independently of who woke the job."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ci-merge-flow/scripts"))
sys.path.insert(0, str(HERE.parent / "security-patch/scripts"))
import check_merge_flow as routes
import security_patch as security
from enrollment import SHA, matches_ordinary_path, positive, require


def verify_eligible(api, repository, pull, policy):
    require(pull["state"] == "open" and pull["draft"] is False, "PR is not open and ready")
    return classify_change(api, repository, pull, policy)


def classify_change(api, repository, pull, policy):
    """Classify the same change for open admission and after a confirmed merge."""
    base, head = pull["base"], pull["head"]
    for side in (base, head):
        require(side["repo"]["full_name"] == repository and side["repo"]["id"] == policy["repository_id"]
                and SHA.fullmatch(side["sha"]), "PR is not bound to this enrolled repository and revision")
    require(positive(pull["number"]) and base["ref"] == policy["branch"] and head["ref"] not in routes.PERSISTENT,
            "PR is not a task on the enrolled target")
    require(not head["ref"].startswith(("security/dependabot-", "security-projection/")), "security projections require personal human merge")
    actor = pull["user"]
    require(positive(actor["id"]), "unknown PR author")
    if actor["id"] == 49699333:
        require(policy["security_sources"] and actor["type"] == "Bot" and actor["login"] == "dependabot[bot]",
                "Dependabot source route is not qualified")
        require(api.get(f"repos/{repository}", fresh=True)["default_branch"] == base["ref"],
                "security sources must target the protected default")
        attestation, _, check = security.parse_attestation_check(
            api, repository, head["sha"], security.SOURCE_CHECK, security.TRUSTED_SECURITY_AUTOMATION_APP_ID,
            security.SOURCE_SCHEMA)
        expected = {"repository": repository, "pull_request": pull["number"], "source_head_sha": head["sha"],
                    "source_base_sha": base["sha"], "profile": security.PROFILE}
        require(all(attestation.get(k) == v for k, v in expected.items())
                and check.get("external_id") == f"{security.SOURCE_SCHEMA}:{pull['number']}:{head['sha']}",
                "security classification belongs to another source")
        advisories = attestation.get("ghsa_set")
        require(isinstance(advisories, list) and advisories and advisories == sorted(set(advisories))
                and all(isinstance(a, str) and a.startswith("GHSA-") for a in advisories),
                "security classification lacks an advisory")
        return "security-source"

    require(actor["type"] == "User" or (actor["type"] == "Bot" and actor["login"] in
            ("renovate[bot]", "forgingalpha-agent-credential[bot]")),
            "unqualified proposal author or security projection actor")
    require(routes.operation(routes.assigned_route(policy["repository_id"]), base["ref"], head["ref"], True) == "task",
            "only ordinary task routes may request native auto-merge")
    files = security.pull_files(api, repository, pull["number"], fresh=True)
    require(0 < len(files) == pull["changed_files"] < security.PULL_FILES_API_LIMIT
            and len({item["filename"] for item in files}) == len(files), "incomplete or ambiguous pull request files")
    for item in files:
        require(matches_ordinary_path(policy, item["filename"]), "path outside qualified ordinary changes")
        require(item.get("status") in {"added", "modified", "removed", "renamed"}, "unknown change type")
        if item["status"] == "renamed" or "previous_filename" in item:
            require(matches_ordinary_path(policy, item.get("previous_filename")), "rename crosses the qualified paths")
    return "ordinary"
