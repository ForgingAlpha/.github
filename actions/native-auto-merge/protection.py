"""Read the visible branch rules independently of the owner's bypass inspection."""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import quote

from eligibility import security
from enrollment import positive, require


def utc_time(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value),
            "invalid ruleset timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def snapshot(api, repo, branch, effective):
    """Hash the entire effective set plus every owning ruleset's visible revision."""
    require(re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", repo) and branch in ("main", "dev") and effective,
            "invalid or empty branch rules")
    grouped = {}
    for row in effective:
        ident = row["ruleset_id"]
        require(positive(ident) and isinstance(row["type"], str) and row["type"], "invalid effective rule")
        group = grouped.setdefault(ident, {})
        require(row["type"] not in group, "ambiguous effective rule type within ruleset")
        group[row["type"]] = row

    definitions = []
    newest = None
    for ident, rules in sorted(grouped.items()):
        detail = api.get(f"repos/{repo}/rulesets/{ident}?includes_parents=true", fresh=True)
        owner, kind = detail["source"], detail["source_type"]
        require(detail["id"] == ident and detail["enforcement"] == "active" and detail["target"] in ("branch", "push")
                and all(row["ruleset_source_type"] == kind and row["ruleset_source"] == owner for row in rules.values())
                and ((kind == "Repository" and owner == repo) or (kind == "Organization" and owner == "ForgingAlpha")
                     or (kind == "Enterprise" and isinstance(owner, str) and owner)), "rule owner or enforcement changed")
        require(isinstance(detail["node_id"], str) and detail["node_id"] and isinstance(detail["conditions"], dict)
                and isinstance(detail["rules"], list), "incomplete ruleset definition")
        # A restricted reader may not see actors. An explicit contradictory list is evidence.
        if "bypass_actors" in detail:
            actors = detail["bypass_actors"]
            require(isinstance(actors, list), "invalid bypass actors")
            mode = None
            if set(rules) <= {"update", "creation"}:
                mode = "exempt"
            elif set(rules) == {"required_status_checks"}:
                checks = rules["required_status_checks"]["parameters"]["required_status_checks"]
                if checks == [{"context": "CI", "integration_id": security.TRUSTED_CI_APP_ID}]:
                    mode = "pull_request"  # Owner must independently qualify this human-only quality override.
            require(not actors or mode and all(a["actor_type"] == "OrganizationAdmin" and a["bypass_mode"] == mode
                                               for a in actors), "visible bypass on an enrolled protection rule")

        updated = utc_time(detail["updated_at"])
        newest = max(newest, updated) if newest else updated
        # The branch endpoint reports the effective parameters. Compare those to
        # the defining endpoint so a partial page or changing policy cannot qualify.
        actual = {name: {k: v for k, v in row.items() if k not in {"ruleset_id", "ruleset_source", "ruleset_source_type"}}
                  for name, row in rules.items()}
        declared = {rule["type"]: rule for rule in detail["rules"]}
        require(len(declared) == len(detail["rules"]) and actual == declared, "incomplete or changed effective rules")
        definitions.append({**{k: detail[k] for k in ("id", "node_id", "source_type", "source", "target",
                                                       "enforcement", "conditions", "updated_at")},
                            "rules": [declared[name] for name in sorted(declared)]})
    document = {"repository": repo, "branch": branch, "rulesets": definitions}
    digest = hashlib.sha256(security.canonical_json(document).encode()).hexdigest()
    return digest, newest


def effective_rules(api, repo, branch):
    path = f"repos/{repo}/rules/branches/{quote(branch, safe='')}?per_page=100"
    return security.flatten_pages(api.pages(path, fresh=True), "effective branch rules")


def verify_qualification(api, repo, policy, rows):
    digest, newest = snapshot(api, repo, policy["branch"], rows)
    anchor = policy["ruleset_qualification"]
    inspected = utc_time(anchor["observed_at"])
    # The owner observed the full actor state after the update timestamp's
    # resolution window. Their observation cannot share a tick with a later edit.
    require(newest.replace(microsecond=0) < inspected.replace(microsecond=0) and inspected <= datetime.now(timezone.utc)
            and digest == anchor["sha256"], "rules differ from the protected owner qualification")
