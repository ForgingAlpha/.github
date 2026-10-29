#!/usr/bin/env python3
"""Read-only, centrally enrolled documentation admission. Never import consumer code."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import time
import stat
import subprocess
import sys
import tempfile
import tomllib

import yaml
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[3]
SOURCE_REPOSITORY = "ForgingAlpha/.github"
SHA = re.compile(r"[a-f0-9]{40}\Z")
REQUIRED = {"PROJECT.md", "AGENTS.md", "CLAUDE.md", "docs/intent.md", "docs/requirements.md", "docs/architecture.md"}
DATA_PATHS = {
    "docs/governing-source-bindings.json",
    "docs/changes/site-foundation/production-preparation/governing-source.json",
    "docs/changes/site-foundation/production-preparation/retained-inputs.json",
}
ALIASES = {"AGENTS.md", "CLAUDE.md"}
COMPILER_SELECTORS = {"RUSTC", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTUP_TOOLCHAIN",
                      "CARGO_BUILD_RUSTC", "CARGO_BUILD_RUSTC_WRAPPER", "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER"}


def load_checking_module(name, path):
    """Import public checking code from this workflow's source checkout."""
    spec = importlib.util.spec_from_file_location(name, SOURCE / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Existing bounded Git transport and strict JSON decoder; exact same source checkout.
foundation = load_checking_module("org_baseline_git", "actions/ci-foundation/scripts/foundation_source.py")
policy = load_checking_module("org_baseline_policy", "actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py")
require = foundation.require
git = foundation.git


def decode(data):
    try:
        return foundation.decode(data)
    except RecursionError:
        raise foundation.Refused("JSON nesting exceeds the supported limit") from None


def positive(value):
    return type(value) is int and value > 0


def catalog(data):
    if isinstance(data, dict) and type(data.get("schema_version")) is int and data["schema_version"] == 2:
        return application_catalog(data)
    require(isinstance(data, dict) and set(data) == {"schema_version", "repositories"}, "invalid central enrollment fields")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "unsupported enrollment schema")
    entries = data["repositories"]
    require(isinstance(entries, list) and 0 < len(entries) <= 32, "invalid enrollment inventory")
    names, ids = set(), set()
    keys = {"repository", "repository_id", "branches", "profile", "team_id", "minimum_approvals"}
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == keys, "invalid enrollment record fields")
        name = entry["repository"]
        require(isinstance(name, str) and re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", name) and name != SOURCE_REPOSITORY,
                "invalid consumer identity or source self-enrollment")
        require(positive(entry["repository_id"]) and name not in names and entry["repository_id"] not in ids,
                "ambiguous consumer enrollment")
        require(entry["profile"] == "documentation-bootstrap", "unsupported profile; no bootstrap fallback")
        require(entry["branches"] in (["dev"], ["dev", "main"]), "unsupported bootstrap branch selection")
        require(positive(entry["team_id"]) and positive(entry["minimum_approvals"]), "invalid trusted team policy")
        names.add(name)
        ids.add(entry["repository_id"])
    return entries


def select(entries, name, repository_id, branch):
    require(positive(repository_id), "invalid consumer repository ID")
    matches = [e for e in entries if e["repository"] == name and e["repository_id"] == repository_id and branch in e["branches"]]
    require(len(matches) == 1, "unknown or changed consumer identity/profile/base branch")
    return matches[0]


def admit_tree(root, expected_head):
    require(root == root.resolve() and git(root, "rev-parse", "--show-toplevel").decode().strip() == str(root), "explicit physical consumer root required")
    require(SHA.fullmatch(expected_head or "") and git(root, "rev-parse", "HEAD").decode().strip() == expected_head, "consumer checkout is not the exact PR head")
    require(git(root, "rev-parse", "--show-object-format").strip() == b"sha1", "unsupported Git object format")
    require(not git(root, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "HEAD", "--"), "modified consumer worktree/index")
    require(not git(root, "diff", "--cached", "--name-only", "HEAD", "--"), "modified consumer index")
    require(not git(root, "ls-files", "--others", "-z"), "untracked consumer inputs (including ignored files)")
    raw = git(root, "ls-tree", "-rz", "--full-tree", expected_head)
    require(raw.endswith(b"\0"), "empty or incomplete tracked inventory")
    records = raw[:-1].split(b"\0")
    require(len(records) <= 512, "bootstrap exceeds 512 tracked inputs")
    texts, seen, total = {}, set(), 0
    for record in records:
        meta, name_bytes = record.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split(" ")
        name = name_bytes.decode("utf-8")
        parts = PurePosixPath(name).parts
        require(name and str(PurePosixPath(name)) == name and not name.startswith("/") and
                all(p not in {".", ".."} for p in parts) and not any(ord(c) < 32 or ord(c) == 127 or c == "\\" for c in name), "unsafe tracked path")
        require(name not in seen, "duplicate tracked path")
        seen.add(name)
        require(name == ".gitignore" or (not any(p.startswith(".") for p in parts) and
                (name.endswith((".md", ".markdown")) or name in DATA_PATHS)), "undeclared executable/config/application input: " + repr(name))
        path = root / name
        for parent in path.parents:
            if parent == root:
                break
            require(stat.S_ISDIR(parent.lstat().st_mode), "linked or non-directory input ancestor")
        info = path.lstat()
        if mode == "120000":
            require(name in ALIASES and stat.S_ISLNK(info.st_mode) and os.readlink(path) == "PROJECT.md", "unsupported instruction projection link")
            data = b"PROJECT.md"
        else:
            require(mode == "100644" and kind == "blob" and stat.S_ISREG(info.st_mode) and not info.st_mode & 0o111,
                    "bootstrap requires non-executable regular inputs")
            require(info.st_size <= 512 * 1024, "bootstrap input exceeds 512 KiB")
            with path.open("rb") as stream:
                data = stream.read(512 * 1024 + 1)
            require(len(data) <= 512 * 1024, "bootstrap input exceeds 512 KiB")
        total += len(data)
        require(total <= 8 * 1024 * 1024, "bootstrap exceeds 8 MiB")
        require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == oid,
                "working input differs from selected Git blob")
        text = data.decode("utf-8")
        require("\0" not in text, "binary bootstrap input")
        if name in DATA_PATHS:
            require(isinstance(decode(data), dict), "declared JSON input must be an object")
        if mode == "100644" and name.endswith((".md", ".markdown")):
            texts[name] = text
    require(REQUIRED <= seen, "missing required project/governing inputs")
    target = root / "PROJECT.md"
    require(stat.S_ISREG(target.lstat().st_mode) and "PROJECT.md" in texts, "instruction projection target must be tracked regular Markdown")
    return texts


def team_configuration(rules, entry):
    require(isinstance(rules, list) and rules, "effective branch-rule evidence unavailable")
    matched = False
    for rule in rules:
        require(isinstance(rule, dict) and isinstance(rule.get("type"), str), "malformed effective rule")
        if rule["type"] != "pull_request":
            continue
        parameters = rule.get("parameters")
        require(isinstance(parameters, dict), "missing PR rule parameters")
        count, stale, reviewers = (parameters.get(k) for k in ("required_approving_review_count", "dismiss_stale_reviews_on_push", "required_reviewers"))
        require(type(count) is int and count >= 0 and type(stale) is bool and isinstance(reviewers, list), "malformed PR review evidence")
        for reviewer in reviewers:
            require(isinstance(reviewer, dict) and isinstance(reviewer.get("reviewer"), dict), "malformed required reviewer")
            identity, minimum, patterns = reviewer["reviewer"], reviewer.get("minimum_approvals"), reviewer.get("file_patterns")
            require(positive(minimum) and isinstance(patterns, list) and all(isinstance(p, str) for p in patterns), "malformed reviewer policy")
            if (identity.get("type") == "Team" and type(identity.get("id")) is int and identity["id"] == entry["team_id"] and
                    minimum >= entry["minimum_approvals"] and count >= entry["minimum_approvals"] and stale and "*" in patterns):
                matched = True
    require(matched, "trusted team review configuration absent or weaker than enrollment")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Api:
    def __init__(self, token):
        require(isinstance(token, str) and bool(token), "read-only workflow token unavailable")
        self.token = token
        self.opener = build_opener(NoRedirect())

    def page(self, path):
        require(path.startswith("/repos/ForgingAlpha/") and not any(c in path for c in "\r\n#"), "invalid API subject")
        request = Request("https://api.github.com" + path, headers={"Authorization": "Bearer " + self.token,
                          "Accept": "application/vnd.github+json", "Cache-Control": "no-cache"}, method="GET")
        try:
            with self.opener.open(request, timeout=20) as response:
                data = response.read(2 * 1024 * 1024 + 1)
                require(len(data) <= 2 * 1024 * 1024, "GitHub evidence exceeds response limit")
                return decode(data), response.headers.get("Link", "")
        except Exception as error:
            if isinstance(error, foundation.Refused):
                raise
            raise foundation.Refused("required GitHub evidence read failed; no cached or credential fallback") from None

    def get(self, path):
        data, link = self.page(path)
        require(not link, "unexpected pagination on exact-object evidence")
        return data

    def rules(self, repository, branch):
        path = f"/repos/{repository}/rules/branches/{quote(branch, safe='')}"
        results, seen, terminal_page = [], set(), None
        for page in range(1, 11):
            data, link = self.page(path + f"?per_page=100&page={page}")
            require(isinstance(data, list) and len(data) <= 100, "malformed branch-rule page")
            for rule in data:
                encoded = json.dumps(rule, sort_keys=True)
                require(encoded not in seen, "duplicate rule or repeated pagination page")
                seen.add(encoded)
                results.append(rule)
            pages = {}
            for part in link.split(",") if link else []:
                item = re.fullmatch(r'\s*<([^>]+)>;\s*rel="(next|prev|first|last)"\s*', part)
                require(item is not None, "malformed rule pagination")
                url, relation = urlsplit(item[1]), item[2]
                query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
                require(url.scheme == "https" and url.netloc == "api.github.com" and url.path == path and not url.fragment and
                        set(query) == {"per_page", "page"} and query["per_page"] == ["100"] and
                        len(query["page"]) == 1 and re.fullmatch(r"[1-9][0-9]*", query["page"][0]), "untrusted rule pagination")
                require(relation not in pages, "ambiguous rule pagination")
                pages[relation] = int(query["page"][0])
                require(pages[relation] <= 10, "rule pagination exceeds bounded complete evidence")
            require("first" not in pages or pages["first"] == 1, "inconsistent first rule page")
            require("prev" not in pages or pages["prev"] == page - 1, "inconsistent previous rule page")
            require("last" not in pages or pages["last"] >= page, "inconsistent last rule page")
            if "last" in pages:
                require(terminal_page is None or terminal_page == pages["last"], "rule pagination terminal page changed")
                terminal_page = pages["last"]
            require(terminal_page is None or page <= terminal_page, "rule pagination passed its terminal page")
            require(terminal_page is None or terminal_page == page or "next" in pages, "incomplete rule pagination: next page omitted")
            if "next" not in pages:
                return results
            require(pages["next"] == page + 1 and bool(data) and (terminal_page is None or pages["next"] <= terminal_page),
                    "untrusted or incomplete rule pagination")
        raise foundation.Refused("rule pagination exceeds bounded complete evidence")


def prove_pr(api, event, entry):
    number = event.get("number")
    require(positive(number), "invalid PR event number")
    pr = event.get("pull_request")
    require(isinstance(pr, dict), "pull_request event required")
    live = api.get(f'/repos/{entry["repository"]}/pulls/{number}')
    require(isinstance(live, dict) and live.get("state") == "open" and positive(live.get("number")) and live.get("number") == number, "current open PR evidence unavailable")
    for value in (pr, live):
        for side in ("base", "head"):
            ref = value.get(side, {})
            require(isinstance(ref, dict) and isinstance(ref.get("repo"), dict), "missing PR repository")
            require(positive(ref["repo"].get("id")) and ref["repo"].get("id") == entry["repository_id"] and ref["repo"].get("full_name") == entry["repository"], "unsupported fork or changed PR repository")
            require(isinstance(ref.get("sha"), str) and SHA.fullmatch(ref["sha"]), "invalid PR commit identity")
        require(value["base"].get("ref") in entry["branches"], "unqualified PR base branch")
    require(pr["base"]["ref"] == live["base"]["ref"] and all(pr[s]["sha"] == live[s]["sha"] for s in ("base", "head")), "PR base/head moved since event")
    branch = api.get(f'/repos/{entry["repository"]}/branches/{quote(pr["base"]["ref"], safe="")}')
    require(isinstance(branch, dict) and branch.get("commit", {}).get("sha") == pr["base"]["sha"], "base branch moved since event")
    return pr["base"]["ref"], pr["base"]["sha"], pr["head"]["sha"]


def run(root, event, entries, api):
    repository = event.get("repository", {})
    pr = event.get("pull_request", {})
    require(isinstance(repository, dict) and isinstance(pr, dict), "malformed consumer event")
    entry = select(entries, repository.get("full_name"), repository.get("id"), pr.get("base", {}).get("ref"))
    require(os.environ.get("GITHUB_REPOSITORY") == entry["repository"] and os.environ.get("GITHUB_REPOSITORY_ID") == str(entry["repository_id"]), "event/runtime repository identity mismatch")
    branch, base, head = prove_pr(api, event, entry)
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    require(origin in (f'https://github.com/{entry["repository"]}', f'https://github.com/{entry["repository"]}.git'), "consumer origin mismatch")
    require(git(root, "rev-parse", f"refs/remotes/origin/{branch}").decode().strip() == base, "checkout base does not match current PR base")
    strings = admit_tree(root, head)
    statuses = policy.baseline_statuses(root)
    require(not policy.incomplete_baseline(statuses), "complete approved structural governing metadata required; definition-only fallback is unsupported")
    # Exact head checkout, not a synthetic merge; disable the legacy HEAD^2 heuristic.
    safe = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    safe.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
                GIT_TERMINAL_PROMPT="0", GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.fsmonitor", GIT_CONFIG_VALUE_0="false",
                GIT_CONFIG_KEY_1="core.hooksPath", GIT_CONFIG_VALUE_1="/dev/null", ALPHAAPPS_POLICY_BASE_REF=base,
                ALPHAAPPS_POLICY_REPO_KIND="code", GITHUB_EVENT_NAME="org_baseline_exact_head")
    result = subprocess.run([sys.executable, "-I", "-B", str(SOURCE / "actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py")], cwd=root, env=safe, timeout=45, check=False)
    require(result.returncode == 0, "structural lifecycle validation failed")
    team_configuration(api.rules(entry["repository"], branch), entry)
    temporary = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
    require(all(temporary != location and location not in temporary.parents for location in (root, SOURCE)),
            "Markdown installation must be outside consumer and trusted checkouts")
    lint_env = {k: v for k, v in safe.items() if k not in {"GITHUB_TOKEN", "GH_TOKEN", "NODE_OPTIONS", "NODE_PATH"}}
    lint = subprocess.run(["node", str(SOURCE / "actions/ci-markdown/scripts/lint_bootstrap.mjs")],
                          input=json.dumps(strings, ensure_ascii=False).encode("utf-8"), cwd=SOURCE, env=lint_env, timeout=180, check=False)
    require(lint.returncode == 0, "central data-only Markdown validation failed")
    prove_pr(api, event, entry)
    team_configuration(api.rules(entry["repository"], branch), entry)
    admit_tree(root, head)
    return public_receipt(root, event, entries, os.environ.get("BASELINE_SOURCE_SHA"))


def public_receipt(root, event, entries, source_sha):
    """Only validated public subject metadata; never serialize an API/auth result."""
    repository, pr = event["repository"], event["pull_request"]
    entry = select(entries, repository["full_name"], repository["id"], pr["base"]["ref"])
    return {"consumer": entry["repository"], "repository_id": entry["repository_id"], "profile": entry["profile"],
            "base": pr["base"]["sha"], "head": git(root, "rev-parse", "HEAD").decode().strip(),
            "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
            "source": SOURCE_REPOSITORY, "source_sha": source_sha,
            "team_configuration": "matched; membership, bypass and complete-path coverage require hosted qualification",
            "scope": "structural checks only; approval, Currentness and deployment are separate"}



# Schema 2 is a source capability. The live schema-1 catalog is deliberately unchanged.
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
SCRIPT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{0,63}\Z")


def shape(value, keys, subject):
    require(isinstance(value, dict) and set(value) == set(keys.split()), "invalid " + subject + " fields")


def safe_path(value, allow_root=False):
    require(isinstance(value, str) and value and not value.startswith(("/", "-")) and
            not any(ord(c) < 32 or ord(c) == 127 or c == "\\" for c in value), "unsafe path")
    if allow_root and value == ".":
        return value
    require(str(PurePosixPath(value)) == value and all(x not in ("", ".", "..") for x in value.split("/")), "unsafe path")
    return value


def script_ids(value, empty=False):
    require(isinstance(value, list) and (empty or value) and len(value) <= 16 and
            all(isinstance(x, str) and SCRIPT_ID.fullmatch(x) for x in value) and len(set(value)) == len(value), "invalid required script IDs")


def route_schema(value):
    shape(value, "declarations transition reconciliation_sha256", "release route")
    require(isinstance(value["reconciliation_sha256"], str) and DIGEST.fullmatch(value["reconciliation_sha256"]), "missing owner reconciliation")
    declarations = value["declarations"]
    require(isinstance(declarations, list) and len(declarations) in (1, 2) and
            value["transition"] == ("none" if len(declarations) == 1 else "owner-authorized"), "unsupported route transition")
    seen = set()
    for row in declarations:
        shape(row, "kind path start end text", "route declaration")
        require(row["kind"] in ("direct", "staged"), "unknown declared route")
        safe_path(row["path"])
        require(row["path"].endswith((".md", ".markdown")), "route declaration must select existing Markdown")
        for key in ("start", "end"):
            require(isinstance(row[key], str) and row[key] and "\n" not in row[key] and "\r" not in row[key] and len(row[key].encode()) <= 256, "invalid route delimiter")
        require(row["start"] != row["end"] and isinstance(row["text"], str) and 0 < len(row["text"].encode()) <= 8192, "invalid route declaration region")
        encoded = json.dumps(row, sort_keys=True)
        require(encoded not in seen, "duplicate route declaration")
        seen.add(encoded)


def application_catalog(data):
    shape(data, "schema_version repositories", "enrollment")
    entries = data["repositories"]
    require(isinstance(entries, list) and 0 < len(entries) <= 32, "invalid enrollment inventory")
    names, ids = set(), set()
    for entry in entries:
        shape(entry, "repository repository_id branches profile producer qualification_subject release_route review_policy foundation components", "schema-2 enrollment")
        name = entry["repository"]
        require(isinstance(name, str) and re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", name) and name != SOURCE_REPOSITORY, "invalid consumer identity")
        require(positive(entry["repository_id"]) and name not in names and entry["repository_id"] not in ids, "ambiguous enrollment")
        names.add(name)
        ids.add(entry["repository_id"])
        review = entry["review_policy"]
        require(isinstance(review, dict), "missing review policy")
        if review.get("kind") == "codeowners":
            shape(review, "kind", "CODEOWNERS policy")
        else:
            shape(review, "kind team_id minimum_approvals", "team policy")
            require(review["kind"] == "qualified-team" and positive(review["team_id"]) and positive(review["minimum_approvals"]), "invalid team policy")
        if entry["profile"] == "documentation-bootstrap":
            require(entry["producer"] == "bootstrap" and entry["components"] == [] and entry["foundation"] == "not-applicable" and
                    entry["release_route"] == {"kind": "not-applicable"} and entry["qualification_subject"] == {"kind": "none"} and
                    review["kind"] == "qualified-team" and entry["branches"] in (["dev"], ["dev", "main"]), "invalid schema-2 bootstrap")
            continue
        require(entry["profile"] in ("astro", "rust", "mixed") and entry["producer"] in ("central-product", "qualification"), "unsupported profile/producer")
        require(entry["foundation"] in ("required", "not-applicable"), "unknown foundation applicability")
        route_schema(entry["release_route"])
        staged = any(x["kind"] == "staged" for x in entry["release_route"]["declarations"])
        require(entry["branches"] == ["dev", "staging", "main"] if staged else entry["branches"] in (["dev"], ["dev", "main"]), "invalid declared branch selection")
        qualification = entry["qualification_subject"]
        if entry["producer"] == "central-product":
            require(qualification == {"kind": "none"}, "unexpected qualification subject")
        else:
            shape(qualification, "kind branch legacy_workflow", "qualification subject")
            require(qualification["kind"] == "legacy-ci" and qualification["branch"] in entry["branches"], "invalid qualification branch")
            legacy = qualification["legacy_workflow"]
            shape(legacy, "path blob job_id", "legacy workflow")
            safe_path(legacy["path"])
            require(re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", legacy["path"]) and
                    isinstance(legacy["blob"], str) and SHA.fullmatch(legacy["blob"]) and
                    isinstance(legacy["job_id"], str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", legacy["job_id"]), "invalid legacy workflow identity")
        components = entry["components"]
        require(isinstance(components, list) and 0 < len(components) <= 16, "missing complete component inventory")
        roots, kinds = [], set()
        for component in components:
            require(isinstance(component, dict), "invalid component")
            kind = component.get("kind")
            shape(component, "kind root tests" + (" static_scripts" if kind == "astro" else ""), "component")
            require(kind in ("rust", "astro"), "unsupported component kind")
            roots.append(safe_path(component["root"], True))
            kinds.add(kind)
            if kind == "rust":
                require(component["tests"] == ["cargo-all"], "unsupported Rust test obligation")
            else:
                script_ids(component["static_scripts"], True)
                tests = component["tests"]
                require(isinstance(tests, dict), "missing explicit test selection")
                if tests.get("kind") == "required":
                    shape(tests, "kind scripts", "required tests")
                    script_ids(tests["scripts"])
                else:
                    shape(tests, "kind evidence_sha256", "no-tests decision")
                    require(tests["kind"] == "owner-declared-none" and isinstance(tests["evidence_sha256"], str) and DIGEST.fullmatch(tests["evidence_sha256"]), "missing no-tests owner decision")
        require(len(set(roots)) == len(roots) and roots == sorted(roots), "duplicate or unsorted component roots")
        require(kinds == ({"rust", "astro"} if entry["profile"] == "mixed" else {entry["profile"]}), "profile/component mismatch")
    return entries


def bootstrap_entry(entry):
    if "review_policy" not in entry:
        return entry
    return {key: entry[key] for key in ("repository", "repository_id", "branches", "profile")} | {
        key: entry["review_policy"][key] for key in ("team_id", "minimum_approvals")}


class StrictYaml(yaml.BaseLoader):
    """Data only; retain YAML event 'on', reject duplicate keys and aliases."""
    def compose_node(self, parent, index):
        require(not self.check_event(yaml.AliasEvent), "YAML aliases are unsupported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            require(key_node.tag == "tag:yaml.org,2002:str", "invalid YAML mapping key")
            key = self.construct_object(key_node, deep=deep)
            require(isinstance(key, str) and key not in result, "duplicate YAML key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def yaml_data(data):
    require(len(data) <= 1024 * 1024, "YAML input exceeds limit")
    # BaseLoader does not execute tags; reject explicit tags rather than silently treating them as data.
    try:
        require(not any(isinstance(token, yaml.TagToken) for token in yaml.scan(data)), "explicit YAML tags unsupported")
        value = yaml.load(data, Loader=StrictYaml)
    except (yaml.YAMLError, RecursionError):
        raise foundation.Refused("malformed or excessive YAML") from None
    require(isinstance(value, dict), "YAML mapping required")
    return value


def clean_inventory(root, head):
    require(root == root.resolve() and git(root, "rev-parse", "--show-toplevel").decode().strip() == str(root), "explicit physical consumer root required")
    require(isinstance(head, str) and SHA.fullmatch(head) and git(root, "rev-parse", "HEAD").decode().strip() == head, "consumer checkout differs from PR head")
    require(git(root, "rev-parse", "--show-object-format").strip() == b"sha1", "unsupported Git object format")
    require(not git(root, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "HEAD", "--") and
            not git(root, "ls-files", "--others", "-z", limit=16 * 1024 * 1024), "modified or untracked consumer inputs")
    raw = git(root, "ls-tree", "-rz", "--full-tree", head, limit=32 * 1024 * 1024)
    require(raw.endswith(b"\0"), "empty/incomplete tree")
    records = raw[:-1].split(b"\0")
    require(len(records) <= 100000, "tracked tree exceeds limit")
    inventory = {}
    for record in records:
        meta, name = record.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        name = safe_path(name.decode("utf-8"))
        require(name not in inventory and kind == "blob" and mode in ("100644", "100755", "120000"), "duplicate/unsupported tracked entry")
        target = root / name
        for parent in target.parents:
            if parent == root:
                break
            require(stat.S_ISDIR(parent.lstat().st_mode), "linked input ancestor")
        if mode == "120000":
            require(name in ALIASES and target.is_symlink() and os.readlink(target) == "PROJECT.md", "unsupported linked application input")
        else:
            require(stat.S_ISREG(target.lstat().st_mode), "nonregular application input")
        inventory[name] = (mode, oid)
    require(REQUIRED <= set(inventory), "missing required governing/project input")
    return inventory


def tracked_bytes(root, inventory, name, limit=1024 * 1024):
    require(name in inventory and inventory[name][0] in ("100644", "100755"), "missing tracked regular input: " + name)
    data, info = foundation.read_regular(root / name, limit)
    require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == inventory[name][1], "changed tracked bytes: " + name)
    require(bool(info.st_mode & 0o111) == (inventory[name][0] == "100755"), "changed tracked executable mode")
    return data


def root_file(component, name):
    return name if component["root"] == "." else component["root"] + "/" + name


def refuse_compiler_selectors(config, cargo=False):
    environment = config.get("env", {})
    require(isinstance(environment, dict) and not COMPILER_SELECTORS.intersection(environment), "alternative compiler environment selector")
    if cargo:
        build = config.get("build", {})
        require(isinstance(build, dict) and not {"rustc", "rustc-wrapper", "rustc-workspace-wrapper"}.intersection(build), "alternative Cargo compiler selector")


def classify(root, inventory, entry):
    manifests = {name for name in inventory if PurePosixPath(name).name in ("Cargo.toml", "package.json")}
    require(len(manifests) <= 256, "manifest inventory exceeds limit")
    parsed, size = {}, 0
    for name in sorted(manifests):
        data = tracked_bytes(root, inventory, name)
        size += len(data)
        require(size <= 8 * 1024 * 1024, "manifest bytes exceed limit")
        parsed[name] = decode(data) if name.endswith(".json") else tomllib.loads(data.decode())
        require(isinstance(parsed[name], dict), "manifest must be an object")
    astro = {root_file(c, "package.json") for c in entry["components"] if c["kind"] == "astro"}
    require(astro == {n for n in manifests if n.endswith("package.json")}, "undeclared or missing Astro component")
    rust_roots = {root_file(c, "Cargo.toml") for c in entry["components"] if c["kind"] == "rust"}
    require(rust_roots <= manifests, "missing Rust root manifest")
    require(bool(rust_roots) == any(n.endswith("Cargo.toml") for n in manifests), "undeclared Rust component")
    expected_locks = set()
    for c in entry["components"]:
        lock = root_file(c, "Cargo.lock" if c["kind"] == "rust" else "package-lock.json")
        expected_locks.add(lock)
        data = tracked_bytes(root, inventory, lock, 64 * 1024 * 1024)
        if c["kind"] == "astro":
            package = parsed[root_file(c, "package.json")]
            require("workspaces" not in package, "npm workspaces unsupported")
            dependencies = {}
            for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                value = package.get(key, {})
                require(isinstance(value, dict), "invalid npm dependencies")
                dependencies.update(value)
            require(all(tool in dependencies for tool in ("astro", "eslint", "prettier")), "missing locked Astro tools")
            require(all(isinstance(v, str) and not v.startswith(("file:", "link:", "workspace:")) for v in dependencies.values()), "unsupported local npm dependency")
            scripts = package.get("scripts")
            required_ids = ["build"] + c["static_scripts"] + (c["tests"]["scripts"] if c["tests"]["kind"] == "required" else [])
            require(isinstance(scripts, dict) and all(isinstance(scripts.get(n), str) and scripts[n].strip() for n in required_ids), "missing required npm script")
            require(isinstance(decode(data), dict), "invalid npm lock")
        else:
            require(bool(data.strip()), "empty Cargo lock")
    actual_locks = {n for n in inventory if PurePosixPath(n).name in ("Cargo.lock", "package-lock.json")}
    require(actual_locks == expected_locks, "undeclared/orphan lock")
    unsupported = {"yarn.lock", "pnpm-lock.yaml", "mix.exs", "pyproject.toml", "requirements.txt", "go.mod", "Gemfile", "composer.json", "Pipfile"}
    require(not any(PurePosixPath(n).name in unsupported for n in inventory), "unsupported ecosystem/workspace input")
    for name in inventory:
        leaf = PurePosixPath(name).name
        if PurePosixPath(name).parent.name == ".cargo" and leaf in ("config", "config.toml"):
            refuse_compiler_selectors(tomllib.loads(tracked_bytes(root, inventory, name).decode()), cargo=True)
        require(leaf not in ("rust-toolchain", "rust-toolchain.toml", ".tool-versions", ".node-version", ".nvmrc") and
                (not ((leaf.startswith(("mise.", ".mise.")) and leaf.endswith(".toml")) or leaf == "mise.lock" or "/mise/" in name or name.startswith(".mise/")) or name in ("mise.toml", "mise.lock")), "unsupported runtime override")
    return sorted(manifests)


def producer_check(root, inventory, entry, branch):
    qualification = entry["qualification_subject"]
    legacy = qualification.get("legacy_workflow") if entry["producer"] == "qualification" else None
    if legacy:
        require(branch == qualification["branch"], "qualification branch mismatch")
    found = False
    for name in sorted(inventory):
        if not re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", name):
            continue
        workflow = yaml_data(tracked_bytes(root, inventory, name))
        triggers = workflow.get("on")
        require(isinstance(triggers, (str, list, dict)), "unknown workflow triggers")
        events = [triggers] if isinstance(triggers, str) else list(triggers)
        require(all(isinstance(event, str) for event in events), "invalid workflow event")
        jobs = workflow.get("jobs")
        require(isinstance(jobs, dict) and jobs, "missing workflow jobs")
        for job_id, job in jobs.items():
            require(isinstance(job, dict) and "uses" not in job, "unresolved reusable workflow producer")
            label = job.get("name", job_id)
            require(isinstance(label, str) and "${{" not in label, "unresolved dynamic producer")
            if label != "CI":
                continue
            require(legacy and name == legacy["path"] and job_id == legacy["job_id"] and inventory[name][1] == legacy["blob"] and
                    "matrix" not in job.get("strategy", {}), "independent CI producer remains")
            require(not found, "duplicate CI producer")
            found = True
    require(found if legacy else not found, "qualified legacy producer missing")


def declared_route(root, entry, base, head):
    declarations = entry["release_route"]["declarations"]
    matches = []
    for revision in (base, head):
        matching = []
        for i, row in enumerate(declarations):
            # Git reads committed data, not consumer-supplied executable/config code.
            mode = git(root, "ls-tree", revision, "--", row["path"]).decode().split()
            if not mode or mode[0] != "100644":
                continue
            text = git(root, "show", revision + ":" + row["path"], limit=512 * 1024).decode("utf-8")
            lines = text.splitlines(keepends=True)
            starts = [n for n, line in enumerate(lines) if line.rstrip("\r\n") == row["start"]]
            ends = [n for n, line in enumerate(lines) if line.rstrip("\r\n") == row["end"]]
            require(len(starts) <= 1 and len(ends) <= 1, "ambiguous route delimiters")
            if not starts or not ends:
                continue
            require(starts[0] < ends[0], "invalid route delimiter order")
            if "".join(lines[starts[0] + 1:ends[0]]) == row["text"]:
                matching.append(i)
        require(len(matching) == 1, "route declaration differs from owner reconciliation")
        matches.append(matching[0])
    require(matches[0] == matches[1] or (entry["release_route"]["transition"] == "owner-authorized" and matches == [0, 1]), "unsupported route declaration transition")
    return "staged" if any(declarations[i]["kind"] == "staged" for i in matches) else "direct"


def application_integrity(root, inventory, entry, runtime_data=None, foundation_data=None):
    pair = any(os.path.lexists(root / name) for name in ("foundation.lock", ".foundation", "tools/container-foundation"))
    if entry["foundation"] == "required":
        records = foundation.catalog(foundation_data if foundation_data is not None else (SOURCE / "actions/ci-foundation/approved.json").read_bytes())
        foundation.verify(root, records, {})
    else:
        require(not pair, "foundation pair conflicts with explicit not-applicable scope")
    runtime = load_checking_module("org_runtime", "actions/ci-runtime-profile/scripts/validate_runtime_profile.py")
    data = runtime_data if runtime_data is not None else decode((SOURCE / "runtime-profiles/catalog.json").read_bytes())
    runtime.validate_catalog(data)
    policy_data = decode(tracked_bytes(root, inventory, ".github/update-policy.json"))
    runtime.validate_policy_assignment(data, entry["repository"], policy_data)
    config = tomllib.loads(tracked_bytes(root, inventory, "mise.toml").decode())
    refuse_compiler_selectors(config)
    lock = tomllib.loads(tracked_bytes(root, inventory, "mise.lock").decode())
    tuple_id = runtime.validate_projection(data, entry["repository"], config, lock)
    tools = runtime.current_tuple(data, entry["repository"])["tools"]
    required_tools = {"node" if c["kind"] == "astro" else "rust" for c in entry["components"]}
    require(required_tools <= set(tools), "assigned runtime lacks component tools")
    return {"tuple": tuple_id, "tools": {key: value["version"] for key, value in tools.items()}}


def app_plan(root, event, entry, source_sha, runtime_data=None, foundation_data=None):
    pr = event["pull_request"]
    base, head, branch = pr["base"]["sha"], pr["head"]["sha"], pr["base"]["ref"]
    inventory = clean_inventory(root, head)
    manifests = classify(root, inventory, entry)
    producer_check(root, inventory, entry, branch)
    route = declared_route(root, entry, base, head)
    runtime = application_integrity(root, inventory, entry, runtime_data, foundation_data)
    return {"schema_version": 2, "consumer": entry["repository"], "repository_id": entry["repository_id"], "pr": event["number"],
            "branch": branch, "base": base, "head": head, "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
            "source_sha": source_sha, "enrollment_sha256": hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "profile": entry["profile"], "producer": entry["producer"], "route": route, "runtime": runtime,
            "components": entry["components"], "manifests": manifests,
            "review_policy": entry["review_policy"], "foundation": entry["foundation"],
            "checking_fingerprints": {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in
                                      ("actions/ci-org-baseline/enrollment.json", "runtime-profiles/catalog.json",
                                       "actions/ci-foundation/approved.json", "actions/ci-foundation/scripts/foundation_source.py")},
            "required_jobs": ["baseline", "static", "tests"]}


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k not in COMPILER_SELECTORS and k not in
           {"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_LICENSE_TOKEN", "MISE_GITHUB_TOKEN", "INPUT_GITHUB_TOKEN",
            "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "NODE_OPTIONS", "NODE_PATH"}}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.fsmonitor", GIT_CONFIG_VALUE_0="false", GIT_CONFIG_KEY_1="core.hooksPath", GIT_CONFIG_VALUE_1="/dev/null")
    return env


def checked(command, root, env=None, capture=False, timeout=300, data=None, capture_limit=1024 * 1024):
    environment = clean_env() if env is None else env
    if not capture:
        result = subprocess.run(command, cwd=root, env=environment, input=data, timeout=timeout, check=False)
        require(result.returncode == 0, "required command failed: " + Path(command[0]).name)
        return None
    # Runtime/version and Cargo metadata reads have no stdin and bounded complete
    # stdout/stderr. Kill the entire subprocess group on overflow or timeout.
    require(data is None and type(capture_limit) is int and 0 < capture_limit <= 8 * 1024 * 1024, "unsupported bounded capture")
    output, counts = bytearray(), {"stdout": 0, "stderr": 0}
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, ("stdout", capture_limit))
                selector.register(process.stderr, selectors.EVENT_READ, ("stderr", 65536))
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, "required command timed out")
                    events = selector.select(remaining)
                    require(events, "required command timed out")
                    for key, _ in events:
                        name, cap = key.data
                        chunk = os.read(key.fd, min(65536, cap - counts[name] + 1))
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        counts[name] += len(chunk)
                        require(counts[name] <= cap, "required command output exceeds bounded capture")
                        if name == "stdout":
                            output.extend(chunk)
            remaining = deadline - time.monotonic()
            require(remaining > 0 and process.wait(timeout=remaining) == 0, "required captured command failed")
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
    return bytes(output)


def source_script(path, *args):
    return [sys.executable, "-I", "-B", str(SOURCE / path), *map(str, args)]


def literal_values():
    def step(action, name):
        value = yaml_data((SOURCE / "actions" / action / "action.yml").read_bytes())
        rows = [s for s in value["runs"]["steps"] if s.get("name") == name]
        require(len(rows) == 1, "missing/duplicate trusted tool step")
        return rows[0]
    lint = step("ci-github-actions", "Install actionlint")["env"]
    mise = step("ci-astro", "Install exact locked runtime")["with"]["version"]
    audit = step("ci-rust", "Install cargo-audit")["env"]["CARGO_AUDIT_VERSION"]
    result = {"actionlint_version": lint["ACTIONLINT_VERSION"], "actionlint_sha256": lint["ACTIONLINT_SHA256"], "mise_version": mise, "audit_version": audit}
    require(all(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", result[k]) for k in ("actionlint_version", "mise_version", "audit_version")) and
            DIGEST.fullmatch(result["actionlint_sha256"]), "invalid owned tool literal")
    return result


def application_common(root, event, entry, api, plan):
    safe = clean_env()
    safe.update(ALPHAAPPS_POLICY_BASE_REF=plan["base"], ALPHAAPPS_POLICY_REPO_KIND="code", GITHUB_EVENT_NAME="org_baseline_exact_head")
    require(not policy.incomplete_baseline(policy.baseline_statuses(root)), "complete approved structural governing metadata required")
    checked(source_script("actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py"), root, safe)
    if entry["review_policy"]["kind"] == "codeowners":
        checked(source_script("actions/ci-alphaapps-policy/scripts/validate_codeowners_contract.py"), root, safe)
    else:
        team_configuration(api.rules(entry["repository"], plan["branch"]), entry["review_policy"])
    # This is a trusted metadata subprocess, not consumer execution. Token is scoped to this guard alone.
    guard_env = clean_env()
    guard_env.update(GH_TOKEN=os.environ.get("GITHUB_TOKEN", ""), GITHUB_ACTION_PATH=str(SOURCE / "actions/ci-merge-flow"),
                     DECLARED_ROUTE=plan["route"], HEAD_REF=event["pull_request"]["head"]["ref"], HEAD_REPOSITORY=entry["repository"],
                     BASE_REF=plan["branch"], GITHUB_REPOSITORY=entry["repository"], PR_NUMBER=str(event["number"]))
    checked(["bash", str(SOURCE / "actions/ci-merge-flow/scripts/check_merge_flow.sh"), "declared-route"], root, guard_env)
    inventory = clean_inventory(root, plan["head"])
    texts, total = {}, 0
    for name in sorted(inventory):
        if name.endswith((".md", ".markdown")) and inventory[name][0] != "120000":
            data = tracked_bytes(root, inventory, name, 512 * 1024)
            total += len(data)
            require(total <= 8 * 1024 * 1024 and b"\0" not in data, "Markdown text exceeds supported boundary")
            texts[name] = data.decode("utf-8")
    checked(["node", str(SOURCE / "actions/ci-markdown/scripts/lint_bootstrap.mjs")], SOURCE, timeout=180, data=json.dumps(texts, ensure_ascii=False).encode())
    temporary = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
    require(all(temporary != location and location not in temporary.parents for location in (root, SOURCE)), "checking tools must install outside consumer/trusted checkouts")
    values = literal_values()
    lint_env = clean_env() | {"ACTIONLINT_VERSION": values["actionlint_version"], "ACTIONLINT_SHA256": values["actionlint_sha256"]}
    # Isolated output file avoids exposing intermediate outputs as plan authority.
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as directory:
        output = Path(directory) / "output"
        lint_env["GITHUB_OUTPUT"] = str(output)
        checked(["bash", str(SOURCE / "actions/ci-github-actions/scripts/install_actionlint.sh")], SOURCE, lint_env)
        executable = str(Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / ("actionlint-" + values["actionlint_version"]) / "actionlint")
        workflows = sorted(str(root / n) for n in inventory if re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", n))
        if workflows:
            checked([executable, "-color", *workflows], root)
    checked(source_script("actions/ci-github-actions/scripts/check_workflows.py", "--root", root), root)
    # Canonical CLI covers actions/**/action.yml. Account for other tracked Action
    # locations/extensions without duplicating its covered validation.
    remaining = [name for name in inventory if PurePosixPath(name).name in ("action.yml", "action.yaml") and
                 not (name.startswith("actions/") and name.endswith("/action.yml"))]
    if remaining:
        checker = load_checking_module("org_workflow_safety", "actions/ci-github-actions/scripts/check_workflows.py")
        errors = []
        allowlists = checker.load_allowlists(root, checker.DEFAULT_ALLOWLIST_PATH, errors)
        for name in sorted(remaining):
            yaml_data(tracked_bytes(root, inventory, name))
            checker.validate_action(Path(name), errors, root=root, allowlists=allowlists)
        require(not errors, "additional tracked Action safety validation failed")
    checked(source_script("actions/ci-dependabot-coverage/scripts/check_dependabot_coverage.py", "--root", root), root)
    checked(source_script("actions/ci-update-ownership/scripts/validate_update_ownership.py", "--repository-root", root,
                          "--default-branch", event["repository"]["default_branch"], "--policy", ".github/update-policy.json",
                          "--renovate", "renovate.json", "--dependabot", ".github/dependabot.yml"), root)
    checked(source_script("actions/ci-foundation/scripts/foundation_source.py", "update-owner", "--root", root), root)


def verify_runtime(root, plan):
    for tool, version in plan["runtime"]["tools"].items():
        if tool not in ("node", "rust"):
            continue
        command = "node" if tool == "node" else "rustc"
        output = checked(["mise", "exec", "--", command, "--version"], root, capture=True, capture_limit=4096).decode().strip()
        require(output == "v" + version if tool == "node" else output.startswith("rustc " + version + " "), "selected runtime differs from approved tuple")


def rust_workspace(root, component, manifests):
    cwd = root / component["root"]
    output = checked(["mise", "exec", "--", "cargo", "metadata", "--locked", "--format-version", "1", "--no-deps"], cwd, capture=True, capture_limit=8 * 1024 * 1024)
    value = decode(output)
    require(isinstance(value, dict) and value.get("version") == 1 and value.get("workspace_root") == str(cwd.resolve()), "Cargo workspace root mismatch")
    members, packages = value.get("workspace_members"), value.get("packages")
    require(isinstance(members, list) and members and len(set(members)) == len(members) and isinstance(packages, list), "invalid workspace members")
    package_map = {p["id"]: p for p in packages if isinstance(p, dict) and isinstance(p.get("id"), str)}
    require(len(package_map) == len(packages) and set(package_map) == set(members), "unexpected metadata package membership")
    covered = {root_file(component, "Cargo.toml")}
    for member in members:
        package = package_map[member]
        path = Path(package.get("manifest_path", ""))
        require(path.is_absolute() and path == path.resolve() and root in path.parents, "external/linked Cargo member")
        relative = path.relative_to(root).as_posix()
        require(relative in manifests, "untracked Cargo member")
        covered.add(relative)
        dependencies = package.get("dependencies", [])
        require(isinstance(dependencies, list), "invalid Cargo dependencies")
        for dep in dependencies:
            if dep.get("path") is not None:
                dependency_manifest = str(Path(dep["path"]).resolve() / "Cargo.toml")
                require(dependency_manifest in {p["manifest_path"] for p in packages}, "unsupported external/nonmember path dependency")
    return covered


def execute_products(root, plan, phase):
    require(phase in ("static", "tests"), "unsupported product phase")
    verify_runtime(root, plan)
    results, covered = [], set()
    # Prove complete Rust coverage before any component's product helpers,
    # including an earlier Astro component in the same ordered profile.
    if phase == "static":
        for component in plan["components"]:
            if component["kind"] == "rust":
                actual = rust_workspace(root, component, plan["manifests"])
                require(not covered & actual, "overlapping Cargo workspaces")
                covered.update(actual)
        require(covered == {n for n in plan["manifests"] if n.endswith("Cargo.toml")}, "undeclared/uncovered Cargo manifest")
    values = literal_values()
    for index, c in enumerate(plan["components"]):
        cwd = root / c["root"]
        helper = SOURCE / ("actions/ci-" + c["kind"] + "/scripts/check_" + c["kind"] + ".sh")
        env = clean_env() | {"CARGO_AUDIT_VERSION": values["audit_version"]}
        def run_step(step, *args):
            checked(["mise", "exec", "--", "bash", str(helper), "central", step, *args], cwd, env, timeout=1200)
        if phase == "static":
            if c["kind"] == "rust":
                for step in ("fmt", "clippy", "check", "install-audit", "audit"):
                    run_step(step)
            else:
                for step in ("install", "format", "lint", "types", "build"):
                    run_step(step)
                for script in c["static_scripts"]:
                    run_step("script", script)
        elif c["kind"] == "rust":
            run_step("test")
        elif c["tests"]["kind"] == "required":
            run_step("install")
            for script in c["tests"]["scripts"]:
                run_step("script", script)
        results.append({"index": index, "kind": c["kind"], "root": c["root"], "result": "no-tests" if phase == "tests" and c["kind"] == "astro" and c["tests"]["kind"] == "owner-declared-none" else "success"})
    return {"schema_version": 1, "phase": phase, "plan_sha256": plan_digest(plan), "components": results}


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def aggregate(plan, needs):
    require(isinstance(needs, dict), "missing job results")
    required = plan["required_jobs"]
    require(set(needs) == {"baseline", "static", "tests"}, "missing/unknown job result")
    for job in required:
        require(isinstance(needs[job], dict) and needs[job].get("result") == "success", "required job did not succeed: " + job)
    if plan["profile"] == "documentation-bootstrap":
        require(all(needs[j].get("result") == "skipped" for j in ("static", "tests")), "unexpected bootstrap product execution")
        return
    for phase in ("static", "tests"):
        raw = needs[phase].get("outputs", {}).get("receipt")
        require(isinstance(raw, str) and len(raw.encode()) <= 65536, "missing/oversized component receipt")
        receipt = decode(raw.encode())
        shape(receipt, "schema_version phase plan_sha256 components", "component receipt")
        require(type(receipt["schema_version"]) is int and receipt["schema_version"] == 1 and receipt["phase"] == phase and receipt["plan_sha256"] == plan_digest(plan), "component receipt identity mismatch")
        expected = [{"index": i, "kind": c["kind"], "root": c["root"], "result": "no-tests" if phase == "tests" and c["kind"] == "astro" and c["tests"]["kind"] == "owner-declared-none" else "success"} for i, c in enumerate(plan["components"])]
        require(isinstance(receipt["components"], list) and all(isinstance(row, dict) and type(row.get("index")) is int for row in receipt["components"]), "invalid typed component result")
        require(receipt["components"] == expected, "missing/mismatched/failed component result")


def emit_outputs(values):
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as stream:
        for key, value in values.items():
            require(re.fullmatch(r"[a-z_]+", key), "invalid output key")
            encoded = json.dumps(value, separators=(",", ":")) if not isinstance(value, str) else value
            require("\n" not in encoded and "\r" not in encoded and len(encoded.encode()) <= 65536, "unsafe/oversized output")
            stream.write(key + "=" + encoded + "\n")


def source_identity(source_sha):
    require(isinstance(source_sha, str) and SHA.fullmatch(source_sha) and git(SOURCE, "rev-parse", "HEAD").decode().strip() == source_sha, "trusted checkout differs from defining workflow SHA")
    require(not git(SOURCE, "status", "--porcelain", "--untracked-files=all"), "trusted checking source is modified")


def event_subject(root, event, entries):
    repo, pr = event.get("repository", {}), event.get("pull_request", {})
    entry = select(entries, repo.get("full_name"), repo.get("id"), pr.get("base", {}).get("ref"))
    require(os.environ.get("GITHUB_REPOSITORY") == entry["repository"] and os.environ.get("GITHUB_REPOSITORY_ID") == str(entry["repository_id"]), "event/runtime identity mismatch")
    for side in ("head", "base"):
        value = pr.get(side, {})
        require(value.get("repo", {}).get("full_name") == entry["repository"] and type(value.get("repo", {}).get("id")) is int and value["repo"]["id"] == entry["repository_id"] and
                isinstance(value.get("sha"), str) and SHA.fullmatch(value["sha"]), "fork or malformed PR subject")
    require(positive(event.get("number")) and git(root, "remote", "get-url", "origin").decode().strip() in
            ("https://github.com/" + entry["repository"], "https://github.com/" + entry["repository"] + ".git"), "invalid PR/origin")
    require(git(root, "rev-parse", "refs/remotes/origin/" + pr["base"]["ref"]).decode().strip() == pr["base"]["sha"], "consumer base checkout mismatch")
    return entry


def current_checks(api, event, entry):
    branch, _, _ = prove_pr(api, event, entry)
    review = entry.get("review_policy", {"kind": "qualified-team", **entry})
    if review["kind"] == "qualified-team":
        team_configuration(api.rules(entry["repository"], branch), review)


def make_plan(root, event, entry, source_sha):
    if entry["profile"] != "documentation-bootstrap":
        return app_plan(root, event, entry, source_sha)
    admit_tree(root, event["pull_request"]["head"]["sha"])
    return {**public_receipt(root, event, [bootstrap_entry(entry)], source_sha), "producer": "bootstrap", "components": [], "required_jobs": ["baseline"]}


def staged_main(args, root, event, entries, source_sha):
    entry = event_subject(root, event, entries)
    plan = make_plan(root, event, entry, source_sha)
    if args.stage in ("admit", "finalize"):
        api = Api(os.environ.get("GITHUB_TOKEN"))
        current_checks(api, event, entry)
    if args.stage == "admit":
        if entry["profile"] == "documentation-bootstrap":
            run(root, event, [bootstrap_entry(entry)], api)
        else:
            application_common(root, event, entry, api, plan)
        current_checks(api, event, entry)
        require(make_plan(root, event, entry, source_sha) == plan, "admission inputs changed")
        emit_outputs({"plan": plan, "profile": entry["profile"], "producer": plan["producer"],
                      "result_name": "Organization Profile Qualification" if plan["producer"] == "qualification" else "CI",
                      "mise_version": literal_values()["mise_version"]})
    elif args.stage == "finalize":
        aggregate(plan, decode(os.environ.get("BASELINE_NEEDS", "").encode()))
        current_checks(api, event, entry)
        require(make_plan(root, event, entry, source_sha) == plan, "final inputs changed")
        print(json.dumps(public_receipt(root, event, [bootstrap_entry(entry)], source_sha) if entry["profile"] == "documentation-bootstrap" else
                         {"schema_version": 2, "plan_sha256": plan_digest(plan), "consumer": plan["consumer"], "head": plan["head"], "base": plan["base"], "source_sha": source_sha, "producer": plan["producer"], "checking_fingerprints": plan["checking_fingerprints"],
                          "required_results": {job: "success" for job in plan["required_jobs"]}, "result": "success"}))
    else:
        expected = decode(os.environ.get("BASELINE_PLAN", "").encode())
        require(plan == expected, "job plan differs from rederived trusted source")
        require(entry["profile"] != "documentation-bootstrap", "product job cannot run bootstrap")
        if args.stage == "install":
            checked(["mise", "install", "--locked"], root, clean_env(), timeout=1200)
        if args.stage in ("static", "tests"):
            emit_outputs({"receipt": execute_products(root, plan, args.stage)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer-root", required=True, type=Path)
    parser.add_argument("--stage", choices=("admit", "preflight", "install", "static", "tests", "finalize"))
    args = parser.parse_args()
    require(os.environ.get("GITHUB_EVENT_NAME") == "pull_request", "read-only pull_request context required")
    source_sha = os.environ.get("BASELINE_SOURCE_SHA", "")
    require(SHA.fullmatch(source_sha) and git(SOURCE, "rev-parse", "HEAD").decode().strip() == source_sha, "trusted checkout differs from defining workflow SHA")
    require(not git(SOURCE, "status", "--porcelain", "--untracked-files=all"), "trusted checking source is modified")
    entries = catalog(decode((SOURCE / "actions/ci-org-baseline/enrollment.json").read_bytes()))
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    require(event_path.stat().st_size <= 2 * 1024 * 1024, "event evidence exceeds limit")
    event = decode(event_path.read_bytes())
    require(isinstance(event, dict), "invalid event evidence")
    root = args.consumer_root.absolute()
    if args.stage:
        staged_main(args, root, event, entries, source_sha)
        return
    public_output = json.dumps(public_receipt(root, event, entries, source_sha))
    api = Api(os.environ.get("GITHUB_TOKEN"))
    run(root, event, entries, api)
    # Discard the credential-bearing operation's return value. The logged receipt
    # was frozen before authentication, and is emitted only after validation.
    print(public_output)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        print(f"WHAT: Organization baseline refused: {error}\nWHY: Required profile, identity and complete-input obligations must hold; no lighter fallback is permitted.\nHOW: Repair the input/evidence or request an explicit reviewed application-profile transition; do not bypass this check.", file=sys.stderr)
        raise SystemExit(1)
