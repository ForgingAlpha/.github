"""Read native merge enrollment from the protected base, never from the proposed tree."""

import base64
import hashlib
import json
import re

from pathlib import PurePosixPath


CONTEXT = "Exact human approval"
SHA = re.compile(r"[0-9a-f]{40}")
BOT_IDS = {49699333, 29139614, 41898282}  # Dependabot, Renovate, generic Actions
SHARED_APP_SLUGS = {"github-actions", "dependabot", "renovate", "forgingalpha-agent-credential",
                    "forgingalpha-security-automation"}
FIELDS = {"repository_id", "branch", "requester_id", "proof_app_id", "proof_context",
          "ordinary_paths", "security_sources", "ruleset_qualification"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def positive(value):
    return type(value) is int and value > 0


def dedicated_app_slug(slug):
    return isinstance(slug, str) and bool(re.fullmatch(r"[a-z0-9-]+", slug)) and slug not in SHARED_APP_SLUGS


def valid_path(path):
    return (isinstance(path, str) and bool(path) and all(ch.isprintable() for ch in path)
            and not set(path).intersection("*?[]\\") and not path.startswith("/")
            and all(part not in ("", ".", "..") for part in path.split("/")))


def matches_ordinary_path(policy, path):
    if not valid_path(path):
        return False
    parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
    if (any(part.startswith(".") for part in parts)
            or parts[0] in ("actions", "system", "workflow-templates")
            or parts[-1] in ("global.md", "agents.md", "claude.md", "project.md", "codeowners",
                             "readme.md", "renovate.json", "renovate-config.json", "renovate-weekly.json",
                             "governing-source-bindings.json")):
        return False
    return any(path == item or item.endswith("/**") and path.startswith(item[:-2])
               for item in policy["ordinary_paths"])


def approved_request(arm, policy):
    if not isinstance(arm, dict) or not policy:
        return False
    actor = arm.get("enabled_by")
    return (isinstance(actor, dict) and actor.get("type") == "Bot"
            and positive(actor.get("id")) and actor["id"] == policy["requester_id"]
            and arm.get("merge_method") == "merge")


def validate(value):
    require(isinstance(value, dict) and set(value) == FIELDS, "unexpected native merge enrollment fields")
    require(positive(value["repository_id"]) and positive(value["requester_id"])
            and value["requester_id"] not in BOT_IDS and positive(value["proof_app_id"])
            and value["proof_app_id"] not in {15368, 4618077}, "invalid or shared native merge identity")
    require(value["branch"] in ("dev", "main") and value["proof_context"] == CONTEXT
            and type(value["security_sources"]) is bool, "invalid native merge target or proof")
    anchor = value["ruleset_qualification"]
    require(isinstance(anchor, dict) and set(anchor) == {"sha256", "observed_at"}
            and isinstance(anchor["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", anchor["sha256"])
            and isinstance(anchor["observed_at"], str), "missing owner ruleset qualification")
    paths = value["ordinary_paths"]
    require(isinstance(paths, list) and all(isinstance(item, str) and valid_path(item.removesuffix("/**"))
            for item in paths) and len(paths) == len(set(paths)), "invalid ordinary-path selection")
    require(paths or value["security_sources"], "enrollment selects no proposals")
    return value


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate enrollment key")
        result[key] = value
    return result


def load_policy(api, repository, base_sha):
    require(re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", repository)
            and SHA.fullmatch(base_sha), "invalid enrollment repository or base")
    root = f"repos/{repository}/git"
    commit = api.get(f"{root}/commits/{base_sha}", fresh=True)
    require(commit["sha"] == base_sha, "enrollment commit mismatch")
    oid = commit["tree"]["sha"]
    for name, kind, mode in ((".github", "tree", "040000"), ("native-auto-merge.json", "blob", "100644")):
        require(SHA.fullmatch(oid), "invalid enrollment tree identity")
        response = api.get(f"{root}/trees/{oid}", fresh=True)
        require(response.get("sha") == oid and response.get("truncated") is False
                and isinstance(response.get("tree"), list), "incomplete enrollment tree")
        entries = [entry for entry in response["tree"] if entry["path"] == name]
        if not entries:
            return None
        require(len(entries) == 1 and entries[0]["type"] == kind and entries[0]["mode"] == mode,
                "invalid enrollment file or directory")
        oid = entries[0]["sha"]
    require(SHA.fullmatch(oid), "invalid enrollment blob identity")
    blob = api.get(f"{root}/blobs/{oid}", fresh=True)
    require(blob["sha"] == oid and blob["encoding"] == "base64" and type(blob["size"]) is int
            and 0 < blob["size"] <= 16384, "invalid enrollment blob")
    data = base64.b64decode("".join(blob["content"].split()), validate=True)
    require(len(data) == blob["size"] and hashlib.sha1(
        f"blob {len(data)}\0".encode() + data).hexdigest() == oid, "enrollment bytes differ from base")
    return validate(json.loads(data, object_pairs_hook=unique))
