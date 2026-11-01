#!/usr/bin/env python3
"""Checked proposal-target projection. Never execute or trust consumer policy code.

Source adoption/reconciliation belongs to the owners. Runtime checks correspondence
and current repository metadata; it does not attest worktree origin or merge rights.
"""
import argparse
import base64
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import quote

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[3]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, SOURCE / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


security = load("proposal_security", "actions/security-patch/scripts/security_patch.py")
foundation = load("proposal_git", "actions/ci-foundation/scripts/foundation_source.py")
require = foundation.require
decode = foundation.decode
git = foundation.git
SHA = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
NAME = re.compile(r"ForgingAlpha/[A-Za-z0-9_.-]+\Z")
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,199}\Z")
CHECKING_FILES = (
    ".github/workflows/org-baseline.yml",
    "actions/ci-org-baseline/enrollment.json",
    "actions/ci-org-baseline/scripts/proposal_route.py",
    "actions/ci-org-baseline/scripts/baseline.py",
    "actions/ci-merge-flow/action.yml",
    "actions/ci-merge-flow/scripts/check_merge_flow.sh",
    "actions/ci-update-ownership/action.yml",
    "actions/ci-update-ownership/scripts/validate_update_ownership.py",
    "actions/security-patch/scripts/security_patch.py",
    "actions/security-patch/profiles.json",
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def shape(value, keys, subject):
    require(isinstance(value, dict) and set(value) == set(keys.split()), "invalid " + subject + " fields")


def positive(value):
    return type(value) is int and value > 0


def branch(value):
    require(isinstance(value, str) and BRANCH.fullmatch(value) and ".." not in value and
            not value.endswith(("/", ".", ".lock")) and "//" not in value, "invalid exact branch")
    return value


def path(value):
    require(isinstance(value, str) and value and not value.startswith("/") and
            str(PurePosixPath(value)) == value and ".." not in PurePosixPath(value).parts and
            "\\" not in value and not any(ord(c) < 32 for c in value), "invalid owner path")
    return value


def targets(entry):
    proposal = entry["proposal"]
    return sorted({proposal["task_target"], *(e["source"] for e in proposal["promotions"]),
                   *(e["target"] for e in proposal["promotions"])})


def validate_entry(entry):
    shape(entry, "repository repository_id proposal participation", "proposal row")
    require(isinstance(entry["repository"], str) and NAME.fullmatch(entry["repository"]) and
            positive(entry["repository_id"]), "invalid repository identity")
    p = entry["proposal"]
    shape(p, "task_target promotions evidence", "proposal")
    branch(p["task_target"])
    require(isinstance(p["promotions"], list) and len(p["promotions"]) <= 4, "invalid promotion edges")
    for edge in p["promotions"]:
        shape(edge, "source target same_repository", "promotion")
        branch(edge["source"]); branch(edge["target"])
        require(edge["same_repository"] is True and edge["source"] != edge["target"], "invalid promotion identity")
    require(len({digest(e) for e in p["promotions"]}) == len(p["promotions"]), "duplicate promotion")
    e = p["evidence"]
    shape(e, "adoption_branch adopted_commit files regions context transition reconciliation_sha256 governing_sha256 rule persistent_sources", "owner evidence")
    branch(e["adoption_branch"])
    require(isinstance(e["adopted_commit"], str) and SHA.fullmatch(e["adopted_commit"]), "invalid adopted commit")
    for key in ("reconciliation_sha256", "governing_sha256"):
        require(isinstance(e[key], str) and DIGEST.fullmatch(e[key]), "invalid owner reconciliation digest")
    require(e["rule"] in ("named-control", "application", "owner-declared"), "unknown reconciled rule")
    if entry["repository"] in ("ForgingAlpha/.github", "ForgingAlpha/control-plane"):
        require(e["rule"] == "named-control", "named control cannot use an owner-declared override")
    if e["rule"] == "named-control":
        require(entry["repository"] in ("ForgingAlpha/.github", "ForgingAlpha/control-plane") and
                p["task_target"] == "main" and p["promotions"] == [], "invalid named control route")
    elif e["rule"] == "application":
        require(p["task_target"] == "dev" and p["promotions"] == [
            {"source": "dev", "target": "main", "same_repository": True}], "invalid application route")
    require(isinstance(e["persistent_sources"], list) and set(targets(entry)) <= set(e["persistent_sources"]) and
            len(set(e["persistent_sources"])) == len(e["persistent_sources"]), "missing persistent source declarations")
    for name in e["persistent_sources"]: branch(name)
    validate_closure({k: e[k] for k in ("files", "regions", "context")})
    transition = e["transition"]
    require(isinstance(transition, dict), "missing source transition")
    if transition.get("kind") == "none":
        shape(transition, "kind", "source transition")
    else:
        shape(transition, "kind predecessor successor reconciliation_sha256", "source transition")
        require(transition["kind"] == "forward" and isinstance(transition["reconciliation_sha256"], str)
                and DIGEST.fullmatch(transition["reconciliation_sha256"]), "unqualified source transition")
        validate_closure(transition["predecessor"], allow_empty=True)
        validate_closure(transition["successor"])
        primary={k:e[k] for k in ("files","regions","context")}
        require(digest(primary) in {digest(c) for c in closures(entry)}, "authority closure not bound to transition")
        require(digest(transition["predecessor"]) != digest(transition["successor"]), "duplicate transition closure")
        covered = [{item["path"] for key in ("files", "context") for item in c[key]} for c in closures(entry)]
        require(covered[0] == covered[1], "transition omits controlling presence/absence")
    part = entry["participation"]
    require(isinstance(part, dict), "missing participation")
    if part.get("mode") == "metadata-only":
        shape(part, "mode", "metadata-only participation")
    else:
        shape(part, "mode selected_targets profile producer qualification_subject review_policy foundation components", "central participation")
        require(part["mode"] == "central" and entry["repository"] != "ForgingAlpha/.github", "unsupported central participation")
        require(isinstance(part["selected_targets"], list) and part["selected_targets"] and
                len(set(part["selected_targets"])) == len(part["selected_targets"]) and
                set(part["selected_targets"]) <= set(targets(entry)), "invalid central target selection")
    return entry


def validate_closure(e, allow_empty=False):
    shape(e, "files regions context", "controlling closure")
    require(isinstance(e["files"], list) and (0 if allow_empty else 1) <= len(e["files"]) <= 16, "missing controlling closure")
    names = set()
    for f in e["files"]:
        shape(f, "path sha256", "controlling source")
        path(f["path"])
        require(f["path"] not in names and isinstance(f["sha256"], str) and DIGEST.fullmatch(f["sha256"]), "duplicate/invalid controlling source")
        names.add(f["path"])
    require(isinstance(e["regions"], list) and (0 if allow_empty and not e["files"] else 1) <= len(e["regions"]) <= 16, "missing owner regions")
    for region in e["regions"]:
        shape(region, "path start end sha256", "owner region")
        require(region["path"] in names and all(isinstance(region[k], str) and region[k] and
                "\n" not in region[k] for k in ("start", "end")) and region["start"] != region["end"] and
                isinstance(region["sha256"], str) and DIGEST.fullmatch(region["sha256"]), "invalid owner region")
    require(isinstance(e["context"], list) and 3 <= len(e["context"]) <= 16, "missing entrypoint presence/absence closure")
    paths = set()
    for c in e["context"]:
        require(isinstance(c, dict) and c.get("kind") in ("absent", "file", "symlink"), "invalid context kind")
        shape(c, "path kind" + (" sha256" if c["kind"] == "file" else " target" if c["kind"] == "symlink" else ""), "context source")
        path(c["path"])
        require(c["path"] not in paths, "duplicate context source")
        paths.add(c["path"])
        if c["kind"] == "file":
            require(isinstance(c["sha256"], str) and DIGEST.fullmatch(c["sha256"]), "invalid context digest")
            require(all(f["sha256"] == c["sha256"] for f in e["files"] if f["path"] == c["path"]), "conflicting closure digest")
        elif c["kind"] == "symlink":
            require(isinstance(c["target"], str) and 0 < len(c["target"].encode()) <= 4096 and "\0" not in c["target"], "invalid exact entrypoint target")
        else:
            require(c["path"] not in names, "absent controlling file")
    require({"PROJECT.md", "AGENTS.md", "CLAUDE.md"} <= paths, "incomplete entrypoint precedence closure")
    require(e["files"] or all(c["kind"] == "absent" for c in e["context"]), "empty predecessor must have exact absent context")


def closures(entry):
    e = entry["proposal"]["evidence"]
    if e["transition"]["kind"] == "forward":
        return [e["transition"]["predecessor"],e["transition"]["successor"]]
    return [{k: e[k] for k in ("files", "regions", "context")}]


def catalog(value):
    shape(value, "schema_version repositories", "enrollment")
    require(type(value["schema_version"]) is int and value["schema_version"] == 3, "unsupported enrollment schema")
    rows = value["repositories"]
    require(isinstance(rows, list) and 0 < len(rows) <= 32, "invalid enrollment inventory")
    names, ids = set(), set()
    for row in rows:
        validate_entry(row)
        require(row["repository"] not in names and row["repository_id"] not in ids, "ambiguous repository identity")
        names.add(row["repository"]); ids.add(row["repository_id"])
    return rows


def select(rows, repository, repository_id, central=False):
    require(positive(repository_id), "invalid runtime repository ID")
    matches = [r for r in rows if r["repository"] == repository and r["repository_id"] == repository_id]
    require(len(matches) == 1, "unknown or conflicting owner identity")
    entry = matches[0]
    require(not central or entry["participation"]["mode"] == "central", "metadata-only is not central enrollment")
    return entry


def fingerprint():
    return {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() for p in CHECKING_FILES}


def get(api, endpoint):
    value = api.get(endpoint.lstrip("/"), fresh=True)
    require(isinstance(value, dict), "owner metadata must be an object")
    require(len(json.dumps(value).encode()) <= 2 * 1024 * 1024, "owner metadata exceeds bound")
    return value


def ref(api, repository, name):
    value = get(api, f"repos/{repository}/branches/{quote(branch(name), safe='')}")
    require(isinstance(value, dict) and isinstance(value.get("commit"), dict) and
            isinstance(value["commit"].get("sha"), str) and SHA.fullmatch(value["commit"]["sha"]), "current branch unavailable")
    return value


def match_closure(entry, read):
    # Read immutable entries once, including expected absences. A missing listed
    # path is evidence only from a complete exact Git tree, never a swallowed 404.
    observed = {}
    def observe(name):
        if name not in observed: observed[name] = read(name)
        return observed[name]
    matches = []
    refusals = []
    for index, evidence in enumerate(closures(entry)):
        try:
            texts = {}
            for f in evidence["files"]:
                item = observe(f["path"])
                require(item["kind"] == "file" and hashlib.sha256(item["data"]).hexdigest() == f["sha256"], "controlling source changed: " + f["path"])
                texts[f["path"]] = item["data"].decode("utf-8").splitlines(keepends=True)
            for c in evidence["context"]:
                item = observe(c["path"])
                require(item["kind"] == c["kind"], "controlling context presence/type changed")
                if c["kind"] == "file":
                    require(hashlib.sha256(item["data"]).hexdigest() == c["sha256"], "controlling entrypoint changed")
                elif c["kind"] == "symlink":
                    require(item["data"].decode("utf-8") == c["target"], "controlling entrypoint redirect changed")
            for r in evidence["regions"]:
                lines = texts[r["path"]]
                starts = [i for i, s in enumerate(lines) if s.rstrip("\r\n") == r["start"]]
                ends = [i for i, s in enumerate(lines) if s.rstrip("\r\n") == r["end"]]
                require(len(starts) == len(ends) == 1 and starts[0] < ends[0], "ambiguous owner region")
                require(hashlib.sha256("".join(lines[starts[0]+1:ends[0]]).encode()).hexdigest() == r["sha256"], "owner region changed")
            matches.append(index)
        except foundation.Refused as error:
            refusals.append(str(error))
    require(len(matches) == 1, "unknown or ambiguous controlling closure" +
            (": " + "; ".join(dict.fromkeys(refusals)) if refusals else ""))
    return matches[0]


def transition_correspondence(entry, authority, states):
    require(type(authority) is int and 0 <= authority < len(closures(entry)), "unknown authority closure")
    require(bool(closures(entry)[authority]["files"]), "subject-only empty predecessor is not authority")
    require(len(states) in (1, 2) and all(type(s) is int and 0 <= s < len(closures(entry)) for s in states), "unknown subject closure")
    if len(states) == 1:
        require(states[0] == authority, "push closure differs from current authority")
    else:
        base, head = states
        require((base == head == authority) or (base == 0 and head == 1 and len(closures(entry)) == 2),
                "reversed or unqualified controlling transition")
    return {"authority": authority, "subjects": states}


def local_correspondence(root, entry, revisions, correspondence=None):
    states = []
    for revision in revisions:
        require(isinstance(revision, str) and SHA.fullmatch(revision), "invalid source revision")
        def read(name):
            info = git(root, "ls-tree", revision, "--", name).decode().split()
            if not info: return {"kind": "absent"}
            require(info[0] in ("100644", "120000"), "unsupported controlling source mode")
            return {"kind": "symlink" if info[0] == "120000" else "file",
                    "data": git(root, "show", revision + ":" + name, limit=512 * 1024)}
        states.append(match_closure(entry, read))
    if correspondence is not None:
        require(correspondence["subjects"] == states, "local closure differs from admitted subject")
        transition_correspondence(entry, correspondence["authority"], states)
    return states


def remote_correspondence(api, entry, revision):
    repo = entry["repository"]
    commit = get(api, f"repos/{repo}/git/commits/{revision}")
    root = commit.get("tree", {}).get("sha")
    require(isinstance(root, str) and SHA.fullmatch(root), "owner tree unavailable")
    trees = {}
    def tree(oid):
        if oid not in trees:
            value = get(api, f"repos/{repo}/git/trees/{oid}")
            require(value.get("truncated") is False and isinstance(value.get("tree"), list), "incomplete controlling tree")
            entries = {}
            for item in value["tree"]:
                name = item.get("path")
                require(isinstance(name, str) and name and "/" not in name and name not in entries and
                        isinstance(item.get("sha"), str) and SHA.fullmatch(item["sha"]), "invalid controlling tree entry")
                entries[name] = item
            trees[oid] = entries
        return trees[oid]
    def read(name):
        oid = root
        parts = name.split("/")
        for i, part in enumerate(parts):
            item = tree(oid).get(part)
            if item is None: return {"kind": "absent"}
            if i < len(parts) - 1:
                require(item.get("type") == "tree" and item.get("mode") == "040000", "redirected controlling ancestor")
                oid = item["sha"]
        require(item.get("type") == "blob" and item.get("mode") in ("100644", "120000"), "unsupported controlling source mode")
        value = get(api, f"repos/{repo}/git/blobs/{item['sha']}")
        require(value.get("encoding") == "base64" and type(value.get("size")) is int and 0 <= value["size"] <= 512 * 1024, "owner source bytes unavailable")
        data = base64.b64decode(value.get("content", ""), validate=False)
        require(len(data) == value["size"] and hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == item["sha"], "owner blob mismatch")
        return {"kind": "symlink" if item["mode"] == "120000" else "file", "data": data}
    return match_closure(entry, read)


def owner_correspondence(api, entry):
    e, repo = entry["proposal"]["evidence"], entry["repository"]
    identity = get(api, f"repos/{repo}")
    require(identity.get("full_name") == repo and identity.get("id") == entry["repository_id"], "current repository identity changed")
    current = ref(api, repo, e["adoption_branch"])["commit"]["sha"]
    comparison = get(api, f"repos/{repo}/compare/{e['adopted_commit']}...{current}")
    require(comparison.get("status") in ("identical", "ahead") and
            comparison.get("merge_base_commit", {}).get("sha") == e["adopted_commit"], "owner source ancestry changed")
    state = remote_correspondence(api, entry, current)
    require(bool(closures(entry)[state]["files"]), "subject-only predecessor is not current authority")
    require(ref(api, repo, e["adoption_branch"])["commit"]["sha"] == current, "owner source moved during correspondence")
    return state


def subject(event, entry):
    repo = event.get("repository", {})
    require(repo.get("full_name") == entry["repository"] and repo.get("id") == entry["repository_id"], "event repository mismatch")
    pr = event.get("pull_request", {})
    require(positive(event.get("number")), "invalid PR number")
    for side in ("base", "head"):
        value = pr.get(side, {})
        require(value.get("repo", {}).get("full_name") == entry["repository"] and value.get("repo", {}).get("id") == entry["repository_id"], "fork or changed PR identity")
        branch(value.get("ref"))
        require(isinstance(value.get("sha"), str) and SHA.fullmatch(value["sha"]), "invalid PR SHA")
    require(pr["base"]["ref"] in targets(entry), "unsupported governed target")
    return {"repository": entry["repository"], "repository_id": entry["repository_id"], "pull_request_number": event["number"],
            "base_ref": pr["base"]["ref"], "head_ref": pr["head"]["ref"], "base_sha": pr["base"]["sha"], "head_sha": pr["head"]["sha"]}


def live_subject(api, event, entry):
    s = subject(event, entry)
    live = get(api, f"repos/{s['repository']}/pulls/{s['pull_request_number']}")
    require(live.get("state") == "open" and live.get("number") == s["pull_request_number"], "current open PR unavailable")
    require(subject({"repository": event["repository"], "number": event["number"], "pull_request": live}, entry) == s, "PR subject moved")
    for side in ("base", "head"):
        value = ref(api, s["repository"], s[side + "_ref"])
        require(value["commit"]["sha"] == s[side + "_sha"], "current PR ref moved")
        require(type(value.get("protected")) is bool, "source protection metadata unavailable")
        if side == "head": protected = value["protected"]
    return s, live, protected


def ordinary(entry, s, protected):
    p = entry["proposal"]
    for edge in p["promotions"]:
        if (s["head_ref"], s["base_ref"]) == (edge["source"], edge["target"]):
            return "ordinary-promotion", dict(edge)
    if s["base_ref"] == p["task_target"] and not protected and s["head_ref"] not in set(p["evidence"]["persistent_sources"]) | {"main", "dev", "staging"}:
        return "ordinary-task", {"task_target": p["task_target"], "source_protected": False}
    return None


def policy_record(entry, source_sha):
    return {"schema_version": 1, "repository": entry["repository"], "repository_id": entry["repository_id"],
            "task_target": entry["proposal"]["task_target"], "promotions": entry["proposal"]["promotions"],
            "selected_targets": entry["participation"].get("selected_targets", []),
            "policy_evidence_sha256": digest(entry["proposal"]["evidence"]),
            "checking_source": source_sha, "enrollment_sha256": digest(entry)}


def resolve_governed_route(api, entry, source_sha):
    state = owner_correspondence(api, entry)
    return {**policy_record(entry, source_sha), "authority_state": state}


def admission(api, event, entry, source_sha):
    resolved = resolve_governed_route(api, entry, source_sha)
    evidence_sha = resolved["policy_evidence_sha256"]
    s, live, protected = live_subject(api, event, entry)
    states = [remote_correspondence(api, entry, revision) for revision in (s["base_sha"], s["head_sha"])]
    correspondence = transition_correspondence(entry, resolved["authority_state"], states)
    selected = None if live.get("user", {}).get("login") == "dependabot[bot]" else ordinary(entry, s, protected)
    tree = get(api, f"repos/{s['repository']}/git/commits/{s['head_sha']}").get("tree", {}).get("sha")
    require(isinstance(tree, str) and SHA.fullmatch(tree), "head tree unavailable")
    if selected:
        kind, proof = selected
    else:
        require(live.get("user", {}).get("login") == "dependabot[bot]" or s["base_ref"] == "main", "ordinary source is outside governed route")
        verified = security.verify_ci_admission(api, s["repository"], s["pull_request_number"], s["base_ref"])
        if isinstance(verified, security.SourceAdmission):
            kind, proof = "dependabot-source", asdict(verified)
            proof["changed_paths"] = list(proof["changed_paths"])
            proof["dependency_pairs"] = list(proof["dependency_pairs"])
        else:
            require(isinstance(verified, security.ProjectionEvidence), "unknown security proof")
            kind, proof = "security-projection", verified.attestation()
    result = {"schema_version": 2, "kind": kind, **s, "head_tree_sha": tree,
              "policy_evidence_sha256": evidence_sha, "checking_source_sha": source_sha,
              "enrollment_sha256": digest(entry), "checking_fingerprints": fingerprint(), "source_correspondence": correspondence, "proof": proof}
    validate_admission(result, event, entry, source_sha, tree)
    final, final_live, final_protected = live_subject(api, event, entry)
    require(final == s and final_live.get("user") == live.get("user") and final_protected == protected and
            owner_correspondence(api, entry) == resolved["authority_state"], "admission inputs moved")
    return result


def validate_admission(record, event, entry, source_sha, tree):
    shape(record, "schema_version kind repository repository_id pull_request_number base_ref head_ref base_sha head_sha head_tree_sha policy_evidence_sha256 checking_source_sha enrollment_sha256 checking_fingerprints source_correspondence proof", "admission")
    require(record["schema_version"] == 2 and type(record["schema_version"]) is int and
            {k: record[k] for k in subject(event, entry)} == subject(event, entry) and record["head_tree_sha"] == tree and
            record["checking_source_sha"] == source_sha and record["checking_fingerprints"] == fingerprint() and
            record["enrollment_sha256"] == digest(entry) and record["policy_evidence_sha256"] == digest(entry["proposal"]["evidence"]), "admission subject/source mismatch")
    shape(record["source_correspondence"], "authority subjects", "source correspondence")
    require(len(record["source_correspondence"]["subjects"]) == 2, "missing PR closure pair")
    transition_correspondence(entry, record["source_correspondence"]["authority"], record["source_correspondence"]["subjects"])
    kind, proof = record["kind"], record["proof"]
    if kind in ("ordinary-task", "ordinary-promotion"):
        require(ordinary(entry, record, False) == (kind, proof), "ordinary proof mismatch")
    elif kind == "dependabot-source":
        shape(proof, "repository pull_request source_branch source_base source_head source_tree changed_paths profile dependency_pairs", "source proof")
        require((proof["repository"], proof["pull_request"], proof["source_branch"], proof["source_base"], proof["source_head"], proof["source_tree"]) ==
                (record["repository"], record["pull_request_number"], record["base_ref"], record["base_sha"], record["head_sha"], tree), "source proof subject mismatch")
        pairs = security.validate_profile(proof["profile"], proof["dependency_pairs"], record["repository"], record["repository_id"])
        security.validate_changed_paths(proof["changed_paths"], pairs)
        if proof["profile"] == security.SET_PROFILE:
            require(proof["changed_paths"] == sorted(proof["changed_paths"]), "structural set paths are not sorted")
    elif kind == "security-projection":
        parsed = security.parse_projection_attestation(proof)
        require(parsed.attestation() == proof and (parsed.repository, parsed.production_base, parsed.projection_head, parsed.projection_tree) ==
                (record["repository"], record["base_sha"], record["head_sha"], tree), "projection proof subject mismatch")
        require(parsed.profile == security.PROFILE or parsed.repository_id == record["repository_id"], "projection proof repository ID mismatch")
    else:
        raise foundation.Refused("unknown admission kind")
    return record


def read_event():
    f = Path(os.environ["GITHUB_EVENT_PATH"])
    require(f.stat().st_size <= 2 * 1024 * 1024, "event exceeds bound")
    event = decode(f.read_bytes())
    repo = event.get("repository", {})
    require(repo.get("full_name") == os.environ.get("GITHUB_REPOSITORY") and
            str(repo.get("id")) == os.environ.get("GITHUB_REPOSITORY_ID"), "event/runtime identity mismatch")
    return event


def source_identity():
    # All imports and catalog reads come from the same resolved action bundle;
    # no action_ref/main download or sibling checkout is allowed.
    return git(SOURCE, "rev-parse", "HEAD").decode().strip() if (SOURCE / ".git").exists() else digest(fingerprint())


def normal_target(api, event, entry, root):
    authority = owner_correspondence(api, entry)
    kind = os.environ.get("GITHUB_EVENT_NAME")
    if kind == "pull_request":
        s, _, _ = live_subject(api, event, entry)
        revision = s["head_sha"]
        revisions = [s["base_sha"], revision]
    else:
        require(kind == "push" and event.get("deleted") is False and event.get("forced") is False, "unsupported update-owner event")
        require(isinstance(event.get("before"), str) and SHA.fullmatch(event["before"]), "push before unavailable")
        name = event.get("ref", "")
        require(name.startswith("refs/heads/"), "invalid push ref")
        revision = event.get("after")
        require(revision == os.environ.get("GITHUB_SHA") and ref(api, entry["repository"], name[11:])["commit"]["sha"] == revision, "push ref moved")
        revisions = [revision]
    require(git(root, "rev-parse", "HEAD").decode().strip() == revision, "update input checkout mismatch")
    require(not git(root, "status", "--porcelain", "--untracked-files=no").strip(), "update input checkout is modified")
    states = local_correspondence(root, entry, revisions)
    transition_correspondence(entry, authority, states)
    require(owner_correspondence(api, entry) == authority, "authority closure moved")
    return entry["proposal"]["task_target"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("admit",))
    args = parser.parse_args()
    require(os.environ.get("GITHUB_EVENT_NAME") == "pull_request", "PR context required")
    event = read_event()
    rows = catalog(decode((SOURCE / "actions/ci-org-baseline/enrollment.json").read_bytes()))
    entry = select(rows, event["repository"]["full_name"], event["repository"]["id"])
    record = admission(security.GhApi(), event, entry, source_identity())
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError, security.PolicyError) as error:
        print("WHAT: Proposal admission refused: " + str(error) + "\nWHY: Current owner/source and exact subject must agree.\nHOW: Reconcile the owning source or caller; do not bypass admission.", file=sys.stderr)
        raise SystemExit(1)
