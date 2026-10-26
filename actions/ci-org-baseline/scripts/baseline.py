#!/usr/bin/env python3
"""Read-only, centrally enrolled documentation admission. Never import consumer code."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
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


def load_trusted(name, path):
    spec = importlib.util.spec_from_file_location(name, SOURCE / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Existing bounded Git transport and strict JSON decoder; exact same source checkout.
foundation = load_trusted("org_baseline_git", "actions/ci-foundation/scripts/foundation_source.py")
policy = load_trusted("org_baseline_policy", "actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py")
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
        require(entry["branches"] == ["dev"], "unsupported bootstrap branch selection")
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
    return {"consumer": entry["repository"], "repository_id": entry["repository_id"], "profile": entry["profile"],
            "base": base, "head": head, "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
            "source": SOURCE_REPOSITORY, "source_sha": os.environ.get("BASELINE_SOURCE_SHA"),
            "team_configuration": "matched; membership, bypass and complete-path coverage require hosted qualification",
            "scope": "structural checks only; approval, Currentness and deployment are separate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer-root", required=True, type=Path)
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
    print(json.dumps(run(args.consumer_root.absolute(), event, entries, Api(os.environ.get("GITHUB_TOKEN")))))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        print(f"WHAT: Organization baseline refused: {error}\nWHY: Only the explicitly enrolled, complete, non-executable documentation profile may supply bootstrap CI.\nHOW: Repair the input/evidence or request an explicit reviewed application-profile transition; do not bypass this check.", file=sys.stderr)
        raise SystemExit(1)
