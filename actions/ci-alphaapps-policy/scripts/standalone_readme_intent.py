"""Protected-base README Intent selection for the existing remote policy action.

This module reads committed Git objects only. Authored status remains structural
metadata; neither this check nor a successful migration supplies human approval.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


SELECTION = "readme_intent_scopes"
LIMIT = 512 * 1024
SHA = re.compile(r"[0-9a-f]{40}")
BRANCHES = {"main", "dev"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
               GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "--no-replace-objects", "-c", "core.fsmonitor=false", "-c",
         "core.hooksPath=/dev/null", "-C", str(root), *args],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False,
    )
    require(result.returncode == 0, "required committed Git evidence unavailable")
    require(len(result.stdout) <= LIMIT, "committed Git evidence exceeds its bound")
    return result.stdout


def blob(root, revision, path, *, optional=False, discovery=False):
    record = git(root, "ls-tree", "-z", revision, "--", path)
    if optional and not record:
        return None
    regular = (record.startswith(b"100644 blob ") and record.endswith(b"\t" + path.encode() + b"\0")
               and record.count(b"\0") == 1)
    if discovery and not regular:
        return None
    require(regular, "missing or nonregular governing source: " + path)
    oid = record.split(b" ", 2)[2].split(b"\t", 1)[0].decode("ascii")
    size = git(root, "cat-file", "-s", oid).strip()
    bounded = size.isdigit() and 0 < int(size) <= LIMIT
    if discovery and not bounded:
        return None
    require(bounded, "invalid governing source size: " + path)
    return git(root, "cat-file", "blob", oid)


def metadata(policy, data):
    text = data.decode("utf-8")
    require(not any(mark in text for mark in ("\r", "\0", "\ufeff")), "invalid governing text encoding")
    values, end = policy.leading_metadata(text.split("\n"))
    require(end > 0, "missing governing YAML frontmatter")
    return values, end


def selection(value):
    require(isinstance(value, dict) and value, "invalid protected README selection")
    for branch, scopes in value.items():
        require(branch in BRANCHES and isinstance(scopes, list) and "." in scopes and len(scopes) <= 64
                and all(isinstance(scope, str) and (scope == "." or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", scope))
                        for scope in scopes) and len(set(scopes)) == len(scopes), "invalid protected README selection")
    return value


@lru_cache(maxsize=1)
def checking_baseline():
    # The complete remote action checkout owns this module. Isolated Python
    # must never resolve a checking dependency through the consumer directory.
    path = Path(__file__).resolve().parents[2] / "ci-org-baseline/scripts/baseline.py"
    spec = importlib.util.spec_from_file_location("product_governing_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def four_reader():
    path = Path(__file__).resolve().with_name("four_section.py")
    spec = importlib.util.spec_from_file_location("alphaapps_four_section", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate provider event field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Subject:
    repository: str
    repository_id: int
    branch: str
    base: str
    head: str


def provider_event(env):
    event_path = Path(env.get("GITHUB_EVENT_PATH", ""))
    require(event_path.is_file() and not event_path.is_symlink()
            and event_path.stat().st_size <= 1024 * 1024, "provider event unavailable or oversized")
    with event_path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024, "provider event exceeds its bound")
    event = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    require(isinstance(event, dict), "invalid provider event shape")
    return event


def mapping(value):
    require(isinstance(value, dict), "invalid provider event object")
    return value


def event_subject(root, env, event):
    require(env.get("GITHUB_SERVER_URL") == "https://github.com"
            and env.get("GITHUB_API_URL") == "https://api.github.com", "unsupported GitHub provider")
    repository = mapping(event.get("repository"))
    name, identity = repository.get("full_name"), repository.get("id")
    require(isinstance(name, str) and re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", name)
            and type(identity) is int and identity > 0, "invalid provider repository identity")
    require(env.get("GITHUB_REPOSITORY") == name and env.get("GITHUB_REPOSITORY_ID") == str(identity)
            and repository.get("html_url") == "https://github.com/" + name,
            "provider repository identity disagrees with runner")
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    require(origin in {"https://github.com/" + name, "https://github.com/" + name + ".git",
                       "git@github.com:" + name + ".git", "ssh://git@github.com/" + name + ".git"},
            "checkout origin differs from provider repository")
    current = git(root, "rev-parse", "HEAD").decode().strip()
    event_name = env.get("GITHUB_EVENT_NAME")
    if event_name == "pull_request":
        pr = mapping(event.get("pull_request"))
        base, head = mapping(pr.get("base")), mapping(pr.get("head"))
        number = event.get("number")
        require(type(number) is int and number > 0 and type(pr.get("number")) is int and pr["number"] == number,
                "invalid provider pull request identity")
        base_repo, head_repo = mapping(base.get("repo")), mapping(head.get("repo"))
        require(type(base_repo.get("id")) is int and base_repo.get("id") == identity
                and base_repo.get("full_name") == name, "pull request base repository identity disagrees")
        head_name, head_identity = head_repo.get("full_name"), head_repo.get("id")
        require(isinstance(head_name, str) and re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", head_name)
                and type(head_identity) is int and head_identity > 0
                and head_repo.get("html_url") == "https://github.com/" + head_name
                and (head_name == name) == (head_identity == identity),
                "invalid or contradictory pull request head repository identity")
        branch, prior, after = base.get("ref"), base.get("sha"), head.get("sha")
        require(branch in BRANCHES and env.get("GITHUB_BASE_REF") == branch
                and isinstance(head.get("ref"), str) and head.get("ref")
                and env.get("GITHUB_HEAD_REF") == head.get("ref")
                and env.get("GITHUB_REF") == f"refs/pull/{number}/merge",
                "pull request ref disagrees with provider event")
        require(isinstance(prior, str) and SHA.fullmatch(prior)
                and isinstance(after, str) and SHA.fullmatch(after), "invalid immutable PR revisions")
        require(git(root, "rev-parse", "refs/remotes/origin/" + branch).decode().strip() == prior,
                "checked-out protected base differs from event")
        runner_sha = env.get("GITHUB_SHA", "")
        require(SHA.fullmatch(runner_sha), "invalid runner revision")
        if current == after and runner_sha == after:
            pass
        else:
            parents = git(root, "show", "-s", "--format=%P", runner_sha).decode().strip().split()
            require(parents == [prior, after] and current in {after, runner_sha},
                    "checkout is neither exact PR head nor its exact base/head merge")
    elif event_name == "push":
        ref = event.get("ref", "")
        require(isinstance(ref, str) and ref.startswith("refs/heads/"), "unsupported push ref")
        branch, prior, after = ref[len("refs/heads/"):], event.get("before"), event.get("after")
        require(branch in BRANCHES and env.get("GITHUB_REF") == ref
                and event.get("created") is False and event.get("deleted") is False
                and event.get("forced") is False, "unsupported initial, deleted or forced push")
        require(isinstance(prior, str) and SHA.fullmatch(prior) and prior != "0" * 40
                and isinstance(after, str) and SHA.fullmatch(after)
                and current == after == env.get("GITHUB_SHA"), "push revisions disagree with checkout")
        git(root, "merge-base", "--is-ancestor", prior, after)
    else:
        raise ValueError("standalone selection supports only pull_request and protected-branch push")
    return Subject(name, identity, branch, prior, after)


def read_document(root, revision, kind, policy, *, readme=False):
    path = "README.md" if readme else "docs/" + kind + ".md"
    data = blob(root, revision, path)
    if readme:
        parsed = policy.readme_intent(data)
        values, data = parsed.metadata, parsed.canonical
    else:
        values, _ = metadata(policy, data)
    require(values.get("status") in {"approved", "provisional"}, "missing or unsupported authored status: " + path)
    return data, values


def upstream_bindings(data, values, kind, *, readme=False, prior_data=None):
    """Root migration retains optional identities/digests and checks every authored binding."""
    if kind == "intent":
        return {}
    reader = checking_baseline().first_definition
    bindings = {name: [values[name + "_sha256"]] if name + "_sha256" in values else []
                for name in ("intent", "requirements")}
    targets = reader.README_TARGETS if readme else {"intent.md": "intent", "requirements.md": "requirements"}
    opening = data.decode().split("\n## ", 1)[0]
    if prior_data is None:
        # Only the original reader's claims and metadata were protected.
        for _, label, _, digest in reader.historical_links(opening):
            bindings["requirements" if label == "Requirements" else "intent"].append(digest)
        return bindings

    prior_opening = prior_data.decode().split("\n## ", 1)[0]
    prior_claims = Counter(reader.opening_links(prior_opening, product=True))
    protected_targets = {(label, target) for label, target, _, historical in prior_claims if historical}
    for claim in reader.opening_links(opening, product=True):
        label, target, digest, historical = claim
        if digest is None:
            continue
        if not historical and prior_claims[claim]:
            # Carry a previously ignored occurrence. Extra copies and changed
            # labels, targets or digests are new claims and must be checked.
            prior_claims[claim] -= 1
            continue
        if historical and (label, target) in protected_targets:
            name = "requirements" if label == "Requirements" else "intent"
        else:
            name = reader.governing_link_name(label, target, targets, product=True, legacy=not readme)
        if name:
            require(digest, "invalid upstream governing digest")
            bindings[name].append(digest)
    return bindings


def documents(root, revision, policy, readme, *, prior=None):
    docs = {}
    for kind in ("intent", "requirements", "architecture"):
        data, values = read_document(root, revision, kind, policy, readme=readme and kind == "intent")
        bindings = upstream_bindings(data, values, kind, readme=readme, prior_data=prior[kind][0] if prior else None)
        for name, (upstream, upstream_values, _) in docs.items():
            if name in values:
                require(isinstance(upstream_values.get("id"), str)
                        and values[name] == upstream_values["id"], "wrong upstream governing identity")
            require(all(value == hashlib.sha256(upstream).hexdigest() for value in bindings.get(name, [])),
                    "wrong upstream governing digest")
        docs[kind] = data, values, bindings
    return docs


def transferred_intent(policy, old):
    _, end = metadata(policy, old)
    lines = old.decode().split("\n")
    body = lines[end:]
    while body and not body[0].strip():
        body.pop(0)
    require(body and re.fullmatch(r"# [^\n]+", body[0]), "legacy Intent must begin with its source title")
    body.pop(0)
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    for index, heading in policy._readme_lines(body, 0):
        if heading is not None:
            require(2 <= len(heading[1]) <= 5, "unsupported legacy Intent heading level")
            # The migration changes heading level only, preserving its exact text.
            start = heading.start(1)
            body[index] = body[index][:start] + "#" + body[index][start:]
    return ("## Intent\n\n" + "\n".join(body) + "\n").encode()


def reject_competing(root, revision, policy):
    readme = blob(root, revision, "README.md", optional=True)
    if readme is None:
        return
    try:
        policy.readme_intent(readme)
    except ValueError:
        require(not re.search(rb"(?m)^ {0,3}##[ \t]+Intent(?:[ \t]|$)", readme),
                "competing or invalid README Intent beside the legacy source")
    else:
        raise ValueError("both governing Intent sources are present")


def governing_texts(root, revision, scopes, policy):
    # Ignore implementation blobs. Inspect the paths capable of owning a
    # governing source at any depth, including unselected README Intent claims.
    bounded_git = checking_baseline().git
    raw = bounded_git(root, "ls-tree", "-rlz", "--full-tree", revision, limit=16 * 1024 * 1024)
    require(raw.endswith(b"\0"), "missing complete governing inventory")
    texts, seen, total = {}, set(), 0
    allowed = definition_paths(scopes)
    intent_heading = checking_baseline().first_definition.INTENT_HEADING
    for row in raw[:-1].split(b"\0"):
        header, path = row.split(b"\t", 1)
        if not (b"/" + path.lower()).endswith((b"/readme.md", b"/docs/intent.md", b"/docs/requirements.md",
                                              b"/docs/architecture.md")):
            continue
        mode, kind, oid, size = header.split()
        require(mode == b"100644" and kind == b"blob" and re.fullmatch(rb"[a-f0-9]{40}", oid),
                "nonregular governing or README source")
        require(size.isdigit() and int(size) <= LIMIT, "governing source exceeds supported bound")
        total += int(size)
        require(path not in seen and len(seen) < 512 and total <= 8 * 1024 * 1024,
                "duplicate governing source or inventory exceeds supported bounds")
        seen.add(path)
        data = bounded_git(root, "cat-file", "blob", oid.decode("ascii"), limit=LIMIT)
        name, text = path.decode(), data.decode()
        if name not in allowed and name.casefold().endswith("readme.md") and intent_heading.search(text):
            # Examples inside fenced code or HTML cannot own a governing section.
            lines = text.split("\n")
            _, start = policy.leading_metadata(lines)
            if not any(heading and intent_heading.fullmatch(lines[index])
                       for index, heading in policy._readme_lines(lines, start)):
                continue
        texts[name] = text
    return texts


def changed_paths(root, base, head):
    return set(git(root, "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", base, head, "--")
               .decode().split("\0")[:-1])


def require_document_change(root, subject, *, manifests=()):
    # A selector may be prepared for a later protected base. Never combine
    # adoption with implementation, executable files, workflows or config.
    raw = git(root, "diff", "--raw", "--no-ext-diff", "--no-renames", "-z", subject.base, subject.head, "--")
    records = raw.split(b"\0")
    require(raw and records[-1] == b"" and len(records) % 2 == 1, "invalid selection preparation diff")
    for header, path in zip(records[0:-1:2], records[1:-1:2]):
        modes = header.removeprefix(b":").split()[:2]
        if manifests and path in {b"AGENTS.md", b"CLAUDE.md"}:
            name = path.decode()
            if modes[0] == b"120000":
                require(git(root, "cat-file", "blob", subject.base + ":" + name) == b"PROJECT.md"
                        and blob(root, subject.base, "PROJECT.md") is not None
                        and blob(root, subject.head, "PROJECT.md", optional=True) is None,
                        "unsupported prior native instruction link or target retirement")
            else:
                require(modes[0] in {b"000000", b"100644"}, "unsupported prior native instruction mode")
            if modes[1] == b"120000":
                require(name == "CLAUDE.md" and git(root, "cat-file", "blob", subject.head + ":" + name) == b"AGENTS.md"
                        and blob(root, subject.head, "AGENTS.md") == four_reader().NATIVE_POINTER,
                        "unsupported native instruction alias or target")
            else:
                require(modes[1] == b"100644" and blob(root, subject.head, name) == four_reader().NATIVE_POINTER,
                        "native instruction entry must point to the four README sections")
        else:
            require(len(modes) == 2 and all(mode in (b"000000", b"100644") for mode in modes)
                    and (path.endswith((b".md", b".markdown")) or path in manifests),
                    "README selection or migration requires documentation-only changes")


def require_four_document_change(root, subject, scopes):
    manifests = { (("" if scope == "." else scope + "/") + four_reader().MANIFEST).encode() for scope in scopes}
    require_document_change(root, subject, manifests=manifests)


def definition_paths(scopes):
    return {("" if scope == "." else scope + "/") + name for scope in scopes
            for name in ("README.md", "docs/requirements.md", "docs/architecture.md")}


def validate_scopes(root, subject, policy, protected_scopes, proposed_scopes):
    reader = checking_baseline().first_definition
    current = governing_texts(root, subject.head, proposed_scopes, policy)
    if protected_scopes == ["."]:
        # The existing root contract allowed absent IDs/digests. Preserve each
        # authored binding, while requiring the complete new contract at head.
        require(blob(root, subject.base, "docs/intent.md", optional=True) is None,
                "component selection requires a protected README Intent")
        prior = {"README.md": blob(root, subject.base, "README.md").decode()}
        old_root = documents(root, subject.base, policy, readme=True)
        prior_docs = {kind: (values, {name: len(items) for name, items in bindings.items()})
                      for kind, (_, values, bindings) in old_root.items()}
    else:
        prior = governing_texts(root, subject.base, protected_scopes, policy)
        prior_docs = reader.check_documents(prior, protected_scopes, policy, allow_approved=True, allow_supporting_evidence=True)
    current_docs = reader.check_documents(current, proposed_scopes, policy, allow_approved=True, allow_supporting_evidence=True)
    provisional = any(values["status"] == "provisional"
                      for docs in (prior_docs, current_docs) for values, _ in docs.values())
    for path, (old, old_bindings) in prior_docs.items():
        new, new_bindings = current_docs[path]
        require(all(new.get(key) == old[key] for key in ("id", "intent", "requirements") if key in old),
                "protected governing identity changed")
        require(all(key in new for key in ("intent_sha256", "requirements_sha256") if key in old)
                and all(new_bindings.get(key, 0) >= count for key, count in old_bindings.items()),
                "protected governing binding removed")
    if provisional:
        diff = changed_paths(root, subject.base, subject.head)
        require(diff and diff <= definition_paths(proposed_scopes), "provisional repair requires only selected definition-file changes")
        for name in diff & definition_paths(protected_scopes):
            if name.endswith("README.md"):
                require(policy.readme_intent(prior[name].encode()).outside == policy.readme_intent(current[name].encode()).outside,
                        "provisional repair changed README outside Intent")
    return "definition-only" if provisional else "approved-structure"


def validate_pair(root, subject, policy, selected):
    head_root = blob(root, subject.head, "docs/requirements.md")
    current_metadata, _ = metadata(policy, head_root)
    current_selection = selection(current_metadata.get(SELECTION))
    require(all(set(scopes) <= set(current_selection.get(branch, [])) for branch, scopes in selected.items()),
            "candidate removed protected README selection")
    if subject.branch not in selected:
        return False
    scopes = selected[subject.branch]
    proposed_scopes = current_selection[subject.branch]
    if len(proposed_scopes) > 1:
        return validate_scopes(root, subject, policy, scopes, proposed_scopes)
    old_legacy = blob(root, subject.base, "docs/intent.md", optional=True)
    new_legacy = blob(root, subject.head, "docs/intent.md", optional=True)
    if old_legacy is not None:
        reject_competing(root, subject.base, policy)
    if new_legacy is not None:
        require(old_legacy is not None, "candidate restored a competing legacy Intent")
        reject_competing(root, subject.head, policy)
        return False
    prior = documents(root, subject.base, policy, readme=old_legacy is None)
    current = documents(root, subject.head, policy, readme=True, prior=prior)
    provisional = any(values["status"] == "provisional" for docs in (prior, current)
                      for _, values, _ in docs.values())
    if old_legacy is not None:
        require(not provisional, "first README migration requires approved authored trios")
        require_document_change(root, subject)
    elif provisional:
        before = policy.readme_intent(blob(root, subject.base, "README.md"))
        after = policy.readme_intent(blob(root, subject.head, "README.md"))
        require(before.outside == after.outside, "provisional repair changed README outside Intent")
        changed = git(root, "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z",
                      subject.base, subject.head, "--").rstrip(b"\0").split(b"\0")
        require(changed != [b""] and all(path in {b"README.md", b"docs/requirements.md", b"docs/architecture.md"}
                                        for path in changed), "provisional repair requires only definition-file changes")
    for kind, (_, values, bindings) in prior.items():
        new_values, new_bindings = current[kind][1:]
        for key, value in values.items():
            if key in {"intent_sha256", "requirements_sha256"}:
                require(key in new_values, "candidate removed governing digest binding")
            elif (old_legacy is not None and key != SELECTION) or key in {"id", "intent", "requirements"}:
                require(new_values.get(key) == value, "candidate changed or removed authored governing metadata")
        require(all(len(new_bindings.get(name, [])) >= len(digests) for name, digests in bindings.items()),
                "candidate removed authored upstream binding")
    if old_legacy is not None:
        require(prior["intent"][1] == current["intent"][1], "transferred Intent metadata differs")
        _, end = metadata(policy, current["intent"][0])
        body = "\n".join(current["intent"][0].decode().split("\n")[end:]).encode()
        require(body == transferred_intent(policy, old_legacy), "transferred Intent body differs from approved legacy source")
    return "definition-only" if provisional else "approved-structure"


def declared_selection(policy, data):
    if data is None:
        return {}
    try:
        values, _ = metadata(policy, data)
    except ValueError:
        if SELECTION.encode() in data:
            raise
        return {}
    return selection(values[SELECTION]) if SELECTION in values else {}


def layouts(root, revision, policy):
    four = four_reader()
    data = blob(root, revision, "docs/requirements.md", optional=True)
    old = declared_selection(policy, data)
    prepared = {}
    if data and four.ENROLLMENT.encode() in data:
        values, _ = metadata(policy, data)
        if four.ENROLLMENT in values:
            prepared = selection(values[four.ENROLLMENT])
    # A legacy consumer may use this name for an unrelated object. Only a
    # bounded, regular manifest can declare a successor. A previously selected
    # manifest is mandatory in check_four_enrollment, including after deletion.
    manifest = blob(root, revision, four.MANIFEST, optional=True, discovery=not prepared)
    if manifest and four.ENROLLMENT.encode() in manifest:
        record = four.decode(manifest)
        if isinstance(record, dict) and four.ENROLLMENT in record:
            require(record.get("schema_version") == 3, "unsupported selected source manifest version")
            successor = selection(record[four.ENROLLMENT])
            require(not prepared or prepared == successor, "conflicting protected source selections")
            return old, successor, True
    return old, prepared, False


def check_four_enrollment(root, subject, protected, proposed):
    _, selected, converted = protected
    _, pending, converting = proposed
    require(all(set(scopes) <= set(pending.get(target, [])) for target, scopes in selected.items()),
            "candidate removed protected four-section scope")
    if selected != pending:
        require(not converted and not converting, "candidate cannot enroll its own conversion")
        require_document_change(root, subject)
    require(not converted or converting, "candidate removed protected four-section manifest")
    if converting and not converted:
        require(subject.branch in selected and pending == selected,
                "candidate cannot select its own four-section conversion")


def require_prepared_layout(root, subject, policy, scopes):
    """The protected opt-in permits a later complete migration. Keep legacy CI live."""
    four = four_reader()
    changes = changed_paths(root, subject.base, subject.head)
    for scope in scopes:
        prefix = "" if scope == "." else scope + "/"
        manifest = prefix + four.MANIFEST
        if manifest in changes:
            data = blob(root, subject.head, manifest, optional=True)
            require(data is not None, "incomplete prepared source manifest")
            record = four.decode(data)
            require(isinstance(record, dict) and record.get("schema_version") in (1, 2),
                    "incomplete four-section conversion manifest")
        readme = prefix + "README.md"
        if readme in changes:
            def titles(revision):
                data = blob(root, revision, readme)
                lines = data.decode().split("\n")
                _, first = policy.leading_metadata(lines)
                return {heading[2].strip().casefold() for _, heading in policy._readme_lines(lines, first)
                        if heading and heading[1] == "##" and heading[2]}
            selected = {name.casefold() for name in policy.SECTION_NAMES[1:]}
            current = titles(subject.head)
            added = (current - titles(subject.base)) & selected
            require(not {name.casefold() for name in policy.SECTION_NAMES} <= current and len(added) < 2,
                    "incomplete four-section conversion without a manifest")


def selection_hints(root, env, branch, layout):
    """Runner revision/target hints may require refusal, never authorize a route."""
    hints = []
    if branch in BRANCHES:
        try:
            hints.append(git(root, "rev-parse", "refs/remotes/origin/" + branch).decode().strip())
        except ValueError:
            pass
    runner_sha = env.get("GITHUB_SHA", "")
    if SHA.fullmatch(runner_sha):
        try:
            parents = git(root, "show", "-s", "--format=%P", runner_sha).decode().split()
            if parents:
                hints.append(parents[0])
        except ValueError:
            pass
    inspected = False
    for revision in set(hints):
        try:
            old, four, _ = layout(revision)
        except ValueError:
            continue
        inspected = True
        selected = old | four
        if selected and (branch is None or branch in selected):
            return True, inspected
    return False, inspected


def require_trusted_action(root, policy, env):
    require(env.get("POLICY_ACTION_REPOSITORY") == "ForgingAlpha/.github"
            and env.get("POLICY_ACTION_REF") == "main", "selected route requires the protected remote policy action")
    source = Path(policy.__file__).resolve()
    require(source.parent == Path(__file__).resolve().parent and not source.is_relative_to(root.resolve()),
            "selected route cannot execute checking code from the consumer checkout")


def maybe_validate(root, policy, env=None):
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS") != "true":
        return False
    name = env.get("GITHUB_EVENT_NAME")
    branch = (env.get("GITHUB_BASE_REF") if name == "pull_request" else
              env.get("GITHUB_REF", "").removeprefix("refs/heads/")) or None
    @lru_cache(maxsize=8)
    def layout(revision):
        return layouts(root, revision, policy)

    def selected_at(revision):
        old, four, _ = layout(revision)
        return old | four

    hinted, inspected = selection_hints(root, env, branch, layout)
    if name not in {"pull_request", "push"}:
        if hinted or branch is None or branch in BRANCHES:
            local = selected_at("HEAD")
            require(not hinted and not local, "selected standalone route requires native pull_request or push evidence")
        return False
    # The base is only a lookup until the complete provider/checkout binding below
    # succeeds. It can never select or approve a candidate by itself.
    try:
        event = provider_event(env)
        if name == "push":
            ref = event.get("ref")
            require(isinstance(ref, str) and ref.startswith("refs/heads/"), "invalid provider push ref")
            event_branch, prior = ref[len("refs/heads/"):], event.get("before")
        else:
            base = mapping(mapping(event.get("pull_request")).get("base"))
            event_branch, prior = base.get("ref"), base.get("sha")
        require(isinstance(event_branch, str), "provider event has no target branch")
        if event_branch != branch:
            provider_hint, _ = selection_hints(root, env, event_branch, layout)
            hinted = hinted or provider_hint
        require(isinstance(prior, str) and SHA.fullmatch(prior) and prior != "0" * 40,
                "provider event has no immutable predecessor")
        git(root, "cat-file", "-e", prior + "^{commit}")
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError):
        if branch is not None and branch not in BRANCHES and not hinted:
            return False
        local = selected_at("HEAD")
        require(not hinted and inspected and not local, "protected selection cannot be checked without exact provider evidence")
        return False
    # A candidate declaration cannot authorize this event, even if the legacy
    # trio is still present. A change to any branch's selection is preparation
    # for a later protected base and must be kept separate from implementation.
    protected = layout(prior)
    selected, four, converted = protected
    if branch in BRANCHES or event_branch in BRANCHES:
        # The checkout is only a refusal hint if exact provider data is missing.
        try:
            head = event["after"] if name == "push" else event["pull_request"]["head"]["sha"]
            require(isinstance(head, str) and SHA.fullmatch(head), "provider event lacks exact candidate revision")
            pending = layout(head)
        except (KeyError, TypeError, ValueError):
            local = selected_at("HEAD")
            require(not hinted and not selected and not four and not local, "README selection requires exact provider evidence")
            return False
        proposed, new_four, converting = pending
        if four or new_four or converted or converting:
            subject = event_subject(root, env, event)
            check_four_enrollment(root, subject, protected, pending)
            if subject.branch in four and not converting:
                require_prepared_layout(root, subject, policy, four[subject.branch])
            if converting and subject.branch in four:
                require_trusted_action(root, policy, env)
                result = four_reader().check_pair(sys.modules[__name__], policy, root, subject, protected, pending)
                checkout = git(root, "rev-parse", "HEAD").decode().strip()
                if checkout != head:
                    merged = Subject(subject.repository, subject.repository_id, subject.branch, subject.base, checkout)
                    merge_layout = layout(checkout)
                    require(merge_layout == pending, "merge checkout differs from PR governing selection")
                    four_reader().check_pair(sys.modules[__name__], policy, root, merged, protected, merge_layout)
                print("Protected-base four-section README " + result + " passed")
                return True
        if proposed != selected:
            subject = event_subject(root, env, event)
            require(all(set(scopes) <= set(proposed.get(target, [])) for target, scopes in selected.items()),
                    "candidate removed protected README selection")
            require_document_change(root, subject)
            # New selections for other branches, or the first declaration on
            # this branch, cannot authorize this run. Check their complete
            # future multi-scope input before falling back to the existing route.
            reader = checking_baseline().first_definition
            for target, scopes in proposed.items():
                if (target != subject.branch or target not in selected) and len(scopes) > 1 and scopes != selected.get(target):
                    texts = governing_texts(root, head, scopes, policy)
                    reader.check_documents(texts, scopes, policy, allow_approved=True, allow_supporting_evidence=True)
    if not selected:
        if hinted:
            event_subject(root, env, event)
        return False
    # Either selected target requires the full comparison; a disagreeing runner
    # target must not turn a selected provider event into a legacy fallback.
    if event_branch not in selected and branch not in selected and not hinted:
        return False
    subject = event_subject(root, env, event)
    if subject.branch not in selected:
        return False
    require_trusted_action(root, policy, env)
    handled = validate_pair(root, subject, policy, selected)
    checked_head = git(root, "rev-parse", "HEAD").decode().strip()
    if len(proposed[subject.branch]) > 1 and checked_head != subject.head:
        # ci-rust can build GitHub's exact synthetic merge. Check the governing
        # sources in that checkout too, using only the original protected base.
        merged = Subject(subject.repository, subject.repository_id, subject.branch, subject.base, checked_head)
        merged_selection = declared_selection(policy, blob(root, checked_head, "docs/requirements.md"))
        require(merged_selection == proposed, "merge checkout differs from PR governing selection")
        if proposed != selected:
            require_document_change(root, merged)
        validate_pair(root, merged, policy, selected)
    if handled:
        print("✓ Protected-base README Intent " + handled + " passed; human approval and Currentness are separate")
    return bool(handled)
