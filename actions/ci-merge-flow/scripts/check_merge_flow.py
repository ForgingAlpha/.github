"""Admit a PR to technical CI using the reviewed source's release route."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

ACTION = Path(__file__).resolve().parents[1]
PERSISTENT = {"dev", "staging", "main"}
ROUTES = {"direct", "development", "staged", "main-only"}
SOURCE_REPOSITORY = "ForgingAlpha/.github"
SOURCE_ID = 1137664016


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def assigned_route(repository_id):
    catalog = json.loads((ACTION / "routes.json").read_bytes())
    require(isinstance(catalog, dict) and set(catalog) == ROUTES, "invalid release-route catalog")
    assignments = {}
    for route, identities in catalog.items():
        require(isinstance(identities, list), "invalid route assignments")
        for identity in identities:
            require(type(identity) is int and identity > 0 and identity not in assignments,
                    "invalid or duplicate repository assignment")
            assignments[identity] = route
    require(repository_id in assignments, "repository has no reviewed release-route assignment")
    return assignments[repository_id]


def operation(route, base, head, same_repository):
    require(route in ROUTES and base in PERSISTENT, "unknown release route or target")
    if route == "main-only":
        require(base == "main" and head not in PERSISTENT, "shared tooling requires a task PR to main")
        return "task"
    if base == "dev":
        require(head not in PERSISTENT, "development requires a nonpersistent task branch")
        return "task"
    require(route != "development", "production route has not been activated for this repository")
    if route == "staged" and base == "staging":
        require(same_repository and head not in PERSISTENT, "staging requires a release-owner promotion task")
        return "snapshot"
    pair = (head, base)
    if same_repository and ((route == "direct" and pair == ("dev", "main")) or
                            (route == "staged" and pair == ("staging", "main"))):
        return "promotion"
    require(base == "main" and head not in PERSISTENT and same_repository,
            "source and target branches do not follow the assigned release route")
    return "verify-projection"


def verify_tip(branch, ref, sha):
    require(isinstance(branch, dict) and branch.get("name") == ref and branch.get("protected") is True
            and isinstance(branch.get("commit"), dict) and branch["commit"].get("sha") == sha,
            f"protected {ref} tip is missing or differs from the PR")


def require_release_claim():
    # An equal SHA identifies content. It cannot identify the owner of a live release
    # or authorize a staging repair. No deployed evidence reader supplies that claim yet.
    raise ValueError("staging admission requires qualified release-owner evidence")


def github(endpoint):
    return json.loads(subprocess.check_output(["gh", "api", endpoint], timeout=30))


def numeric(value):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value), "missing positive GitHub identity")
    return int(value)


def main():
    env = os.environ
    repo, repo_id = env["GITHUB_REPOSITORY"], numeric(env["GITHUB_REPOSITORY_ID"])
    base_repo, base_id = env["BASE_REPOSITORY"], numeric(env["BASE_REPOSITORY_ID"])
    head_repo, head_id = env["HEAD_REPOSITORY"], numeric(env["HEAD_REPOSITORY_ID"])
    head, base = env["HEAD_REF"], env["BASE_REF"]
    number = numeric(env["PR_NUMBER"])
    require(repo == base_repo and repo_id == base_id and repo.startswith("ForgingAlpha/"),
            "PR base and runtime repository identities disagree")
    for name, identity in ((repo, repo_id), (head_repo, head_id)):
        require(re.fullmatch(r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*/[a-zA-Z0-9_.-]+", name)
                and name.split("/")[1] not in {".", ".."}, "malformed repository name")
        if name.casefold() == SOURCE_REPOSITORY.casefold() or identity == SOURCE_ID:
            require((name, identity) == (SOURCE_REPOSITORY, SOURCE_ID), "conflicting source repository identity")
    require((head_id == repo_id) == (head_repo.casefold() == repo.casefold()),
            "head repository name and ID disagree")
    require(subprocess.run(["git", "check-ref-format", "refs/heads/" + head], check=False).returncode == 0,
            "invalid PR head ref")
    route = assigned_route(repo_id)
    action = operation(route, base, head, (head_repo, head_id) == (repo, repo_id))
    if action != "task":
        subjects = (("head", head_repo, head_id, head, env["HEAD_SHA"]),
                    ("base", base_repo, base_id, base, env["BASE_SHA"]))
        live = github(f"repos/{repo}/pulls/{number}")
        require(live.get("state") == "open" and live.get("number") == number, "current open PR required")
        for side, name, identity, ref, sha in subjects:
            data = live.get(side, {})
            require(re.fullmatch(r"[0-9a-f]{40}", sha) and data.get("sha") == sha and data.get("ref") == ref
                    and data.get("repo", {}).get("full_name") == name and data["repo"].get("id") == identity,
                    "PR source or target changed since the event")
        if action in {"promotion", "snapshot"}:
            source_branch = "dev" if action == "snapshot" else head
            verify_tip(github(f"repos/{repo}/branches/{source_branch}"), source_branch, env["HEAD_SHA"])
            verify_tip(github(f"repos/{repo}/branches/{base}"), base, env["BASE_SHA"])
        if route == "staged" and action in {"promotion", "snapshot"}:
            require_release_claim()
    if action == "verify-projection":
        verifier = ACTION.parent / "security-patch/scripts/security_patch.py"
        subprocess.run([sys.executable, "-I", str(verifier), "verify-ci-admission", "--repository", repo,
                        "--pull-request", str(number), "--target-branch", base], check=True)
        print("Trusted exact security projection admitted to required CI")
    print(f"PR admitted to CI under the {route} release route")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(f"Release-route check failed: {exc}")
