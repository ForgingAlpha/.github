"""Validate a protected scope's four README selectors and their exact Git blobs."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import json
import posixpath
import re


MANIFEST = "docs/governing-source-bindings.json"
ENROLLMENT = "readme_four_section_scopes"
TRIO = tuple("README.md#" + kind for kind in ("intent", "requirements", "architecture"))
LOCAL = "README.md#local-instructions"
DETAIL = re.compile(r"(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+(?:[.][A-Za-z0-9_-]+)*[.]md")
NATIVE_POINTER = (
    "# Repository instructions\n\n[Intent](README.md#intent)\n\n"
    "[Requirements](README.md#requirements)\n\n[Architecture](README.md#architecture)\n\n"
    "[Local Instructions](README.md#local-instructions)\n"
).encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate source manifest field")
        result[key] = value
    return result


def decode(data):
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid source manifest") from None


def same_metadata(left, right):
    # Python equates 1, 1.0 and True. Authored JSON/YAML fields must retain their types.
    return left == right and json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass
class Snapshot:
    selection: object
    metadata: dict
    details: set
    digests: dict
    identities: dict
    detail_owners: dict


# Normative bindings name a whole file. An ordinary quoted or parenthesized
# Markdown title does not alter the destination. A fragment remains navigation.
DESTINATION = re.compile(
    r"""([^()\s\\<>`]+)(?:[ \t\n]+(?:"[^"]*"|'[^']*'|\([^()]*\)))?\)"""
)


def direct_links(line):
    """Skip each complete Markdown label/destination, including links with titles."""
    offset = 0
    while (start := line.find("[", offset)) >= 0:
        end = start + 1
        depth = 1
        while end < len(line) and depth:
            depth += (line[end] == "[") - (line[end] == "]")
            end += 1
        if depth:
            return
        label = line[start + 1:end - 1]
        offset = end
        if line[end:end + 1] != "(":
            continue
        destination = DESTINATION.match(line, end + 1)
        if destination:
            if (start == 0 or line[start - 1] not in "!]") and "[" not in label and html.unescape(label).strip():
                yield destination[1]
            offset = destination.end()
            continue
        end += 1
        depth = 1
        while end < len(line) and depth:
            depth += (line[end] == "(") - (line[end] == ")")
            end += 1
        if depth:
            return
        offset = end


def detail_links(data, policy):
    """Accept ordinary Markdown links in visible prose, excluding ambiguous markup."""
    source = data.decode()
    # HTML comments can begin after normal prose and span multiple lines.
    visible_source = re.sub(r"<!--.*?(?:--!?>|\Z)", lambda m: re.sub(r"[^\n]", " ", m[0]), source, flags=re.S)
    lines = source.split("\n")
    visible_lines = visible_source.split("\n")
    _, first = policy.leading_metadata(lines)
    result = set()
    in_code = 0
    previous = -2
    paragraph = []
    for index, heading in policy._readme_lines(lines, first):
        if heading is not None:
            continue
        if index != previous + 1:
            result.update(direct_links("\n".join(paragraph)))
            paragraph.clear()
            in_code = 0
        line = visible_lines[index]
        previous = index
        # Mask code spans, including spans across a paragraph's soft line breaks.
        # An escaped opener and an image never introduce an ordinary detail link.
        visible = []
        offset = 0
        while offset < len(line):
            char = line[offset]
            if char == "\\" and not in_code and offset + 1 < len(line):
                visible.append("  ")
                offset += 2
                continue
            if char == "`":
                stop = offset + 1
                while stop < len(line) and line[stop] == "`":
                    stop += 1
                width = stop - offset
                if not in_code:
                    in_code = width
                elif in_code == width:
                    in_code = 0
                visible.append(" " * width)
                offset = stop
                continue
            visible.append(" " if in_code else char)
            offset += 1
        text = "".join(visible)
        if "<" not in text and ">" not in text:
            paragraph.append(text)
        else:
            result.update(direct_links("\n".join(paragraph)))
            paragraph.clear()
    result.update(direct_links("\n".join(paragraph)))
    return result


def snapshot(policy, read, prefix, *, canonical=False):
    """read() accepts only a regular blob at the already selected revision."""
    manifest = decode(read(prefix + MANIFEST))
    required = {"schema_version", "sources", "local_instructions", "source_metadata"}
    allowed = required | ({ENROLLMENT} if not prefix else set())
    require(isinstance(manifest, dict) and required <= manifest.keys() <= allowed
            and type(manifest["schema_version"]) is int and manifest["schema_version"] == 3,
            "invalid four-section manifest fields")
    selection = policy.readme_sections(read(prefix + "README.md"))
    selectors = (*TRIO, LOCAL)
    content = dict(zip(selectors, selection.sections.values(), strict=True))
    hashes = {path: digest(data) for path, data in content.items()}
    require(manifest["local_instructions"] == {"path": LOCAL, "sha256": hashes[LOCAL]},
            "wrong Local Instructions binding")
    metadata = manifest["source_metadata"]
    require(isinstance(metadata, dict) and metadata.keys() == set(TRIO[1:])
            and all(isinstance(values, dict) for values in metadata.values()), "invalid source metadata")
    metadata = {TRIO[0]: selection.metadata, **metadata}
    rows = manifest["sources"]
    require(isinstance(rows, list) and 3 <= len(rows) <= 128, "invalid four-section sources")
    entries, identities, details = {}, {}, set()
    total_bytes = 0
    for row in rows:
        require(isinstance(row, dict) and row.keys() == {"id", "path", "sha256", "upstream"},
                "invalid four-section source entry")
        path, identity, expected = row["path"], row["id"], row["sha256"]
        require(isinstance(path, str) and path not in entries
                and isinstance(identity, str) and re.fullmatch(r"[^\s\x00-\x1f\x7f]{1,512}", identity)
                and identity not in identities.values(), "invalid or duplicate source identity or path")
        if path not in TRIO:
            require(DETAIL.fullmatch(path) and path not in {"README.md", "docs/intent.md"} and len(path) <= 512,
                    "unsupported normative detail path")
            data = read(prefix + path)
            total_bytes += len(data)
            require(total_bytes <= 8 * 1024 * 1024, "normative details exceed the scope size limit")
            require(data.decode("utf-8").strip() and b"\0" not in data, "empty or binary normative detail")
            hashes[path] = digest(data)
            details.add(path)
        require(hashes[path] == expected, "wrong governing source digest: " + path)
        entries[path], identities[path] = row, identity
    require(set(TRIO) <= entries.keys(), "incomplete governing source trio")

    def edge(path):
        return {"path": path, "sha256": hashes[path]}

    owner_details = {owner: {} for owner in TRIO}
    for path in sorted(details):
        owners = entries[path]["upstream"]
        require(isinstance(owners, list), "invalid normative detail owners")
        for selector in TRIO:
            if edge(selector) in owners:
                owner_details[selector][path] = hashes[path]

    def parent_edge(path):
        binding = edge(path)
        detail = owner_details[path]
        if detail:
            binding["detail_sha256"] = next(iter(detail.values())) if len(detail) == 1 else detail
        return binding

    for index, selector in enumerate(TRIO):
        values = metadata[selector]
        require(entries[selector]["upstream"] == [parent_edge(path) for path in TRIO[:index]],
                "wrong upstream selector or digest: " + selector)
        require((canonical and "status" not in values) or values.get("status") in ("approved", "provisional"),
                "missing or unsupported authored status: " + selector)
        require(values.get("id", prefix + selector) == identities[selector], "wrong source identity: " + selector)
        for path in TRIO[:index]:
            kind = path.split("#")[1]
            require(values.get(kind, identities[path]) == identities[path]
                    and values.get(kind + "_sha256", hashes[path]) == hashes[path],
                    "wrong authored upstream identity or digest: " + selector)
    links = {owner: detail_links(content[owner], policy) for owner in TRIO}
    for path in details:
        edges = entries[path]["upstream"]
        require(isinstance(edges, list) and edges, "missing normative detail owner")
        owners = [selector for selector in TRIO if edge(selector) in edges]
        require(edges == [edge(owner) for owner in owners], "wrong normative detail owner or digest")
        for owner in owners:
            require(path in links[owner], "missing link to normative detail: " + path)
    return Snapshot(selection, metadata, details, hashes, identities, owner_details)


def relocated_destination(target, directory):
    public_docs = "https://github.com/ForgingAlpha/.github/blob/main/docs/"
    path, mark, fragment = target.partition("#")
    if target.startswith(public_docs):
        name = path.removeprefix(public_docs)
        if name in {"requirements.md", "architecture.md"}:
            return public_docs.removesuffix("docs/") + "README.md#" + (fragment or name[:-3])
        return target
    if not path or path.startswith("/") or re.match(r"[a-z][a-z0-9+.-]*:", path, re.I):
        return target
    path = posixpath.normpath(posixpath.join(directory, path))
    for name in ("intent", "requirements", "architecture"):
        if path == f"docs/{name}.md":
            return "#" + (fragment or name)
    if path == "README.md" and mark:
        return "#" + fragment
    return path + mark + fragment


def transferred_detail(policy, data, *, upstream, directory="docs"):
    """Project an adopted docs source under its owner's H2, without editing its prose."""
    lines = data.decode("utf-8").split("\n")
    metadata, end = policy.leading_metadata(lines)
    require(directory or not metadata, "unsupported project instruction frontmatter")
    body = lines[end:]
    while body and not body[0].strip():
        body.pop(0)
    require(body and re.fullmatch(r"# [^\n]+", body[0]), "detail must begin with its document title")
    body = body[1:]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    require(body, "empty transferred governing source")
    for i, heading in policy._readme_lines(body, 0):
        if heading is not None:
            require(2 <= len(heading[1]) <= 5, "unsupported transferred detail heading")
            start = heading.start(1)
            body[i] = body[i][:start] + "#" + body[i][start:]
    # Only simple destinations need moving in these sources. Leave external URLs
    # and literal examples alone. An upstream hash changes only to its bound successor.
    fence = None
    for i, line in enumerate(body):
        marker = policy._FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        body[i] = re.sub(r"(\]\()([^()\s<>]+)(\))",
                         lambda m: m[1] + relocated_destination(m[2], directory) + m[3], line)
        body[i] = re.sub(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])",
                         lambda m: upstream.get(m[0], m[0]), body[i])
    return ("\n".join(body) + "\n").encode()


def check_source_transfer(route, policy, root, subject, prefix, before, after):
    """Only retire same-owner canonical documents proven present in the selected README."""
    if not before and not after.details:
        project = route.blob(root, subject.base, prefix + "PROJECT.md", optional=True)
        if project is not None:
            require(route.blob(root, subject.head, prefix + "PROJECT.md", optional=True) is None,
                    "competing native project instructions")
            body = transferred_detail(policy, project, upstream={}, directory="")
            expected = b"## Local Instructions\n\n" + body
            section = after.selection.sections["Local Instructions"]
            require(section == expected or section.startswith(expected + b"\n"),
                    "incomplete transfer into README Local Instructions")
    retired = before.details - after.details if before else set()
    if before:
        for path, identity in before.identities.items():
            if path not in retired:
                require(after.identities.get(path) == identity, "removed or reassigned governing source")
                continue
            require(path in {"docs/requirements.md", "docs/architecture.md"} and identity == path
                    and identity not in after.identities.values(), "removed or reassigned governing source")
        if not retired:
            return
    prior_hashes = {}
    for i, selector in enumerate(TRIO):
        kind = selector.split("#")[1]
        path = f"docs/{kind}.md"
        old = route.blob(root, subject.base, prefix + path, optional=True)
        if path in retired:
            require([owner for owner, paths in before.detail_owners.items() if path in paths] == [selector],
                    "cannot retire a reassigned or shared governing source")
        if path in retired or (not before and i and old is not None and not after.detail_owners[selector]):
            require(route.blob(root, subject.head, prefix + path, optional=True) is None,
                    "retired governing detail remains present: " + path)
            old_meta, _ = route.metadata(policy, old)
            parents = {p.split("#")[1] + "_sha256": after.digests[p] for p in TRIO[:i]}
            for source in (old_meta, before.metadata[selector] if before else {}):
                for field, value in source.items():
                    require(field in after.metadata[selector]
                            and same_metadata(after.metadata[selector][field], parents.get(field, value)),
                            "changed or removed transferred source metadata: " + field)
            body = transferred_detail(policy, old, upstream=prior_hashes)
            title = kind.title()
            expected = ("## " + title + "\n\n").encode() + body
            section = after.selection.sections[title]
            require(section == expected or section.startswith(expected + b"\n"),
                    "incomplete transfer into README " + title)
        if before:
            prior_hashes[before.digests[selector]] = after.digests[selector]
        if old is not None:
            prior_hashes[digest(old)] = after.digests[selector]


def check_inventory(route, root, revision, scopes, policy):
    texts = route.governing_texts(root, revision, scopes, policy)
    allowed = route.definition_paths(scopes)
    for path, text in texts.items():
        if path in allowed:
            continue
        lower = "/" + path.casefold()
        require(not lower.endswith(("/docs/intent.md", "/docs/requirements.md", "/docs/architecture.md")),
                "unregistered governing source")
        if lower.endswith("/readme.md"):
            require(not route.checking_baseline().first_definition.INTENT_HEADING.search(text),
                    "unregistered governing scope")


def check_pair(route, policy, root, subject, protected, proposed, *, caller_scopes=None):
    old, scopes, converted = protected
    _, new_scopes, new_converted = proposed
    branch = subject.branch
    require(branch in scopes and new_converted and scopes == new_scopes,
            "conversion requires unchanged protected scope enrollment and complete v3 bindings")
    enrolled = scopes[branch]
    require(set(old.get(branch, [])) <= set(enrolled)
            and (caller_scopes is None or set(enrolled) == set(caller_scopes)),
            "four-section scope coverage differs from protected definitions or caller")
    if len(enrolled) > 1 or caller_scopes is not None:
        for revision in ([subject.base, subject.head] if converted else [subject.head]):
            check_inventory(route, root, revision, enrolled, policy)
    if not converted:
        route.require_four_document_change(root, subject, enrolled)
    # The prior adopted layout determines which protected inputs must survive.
    previous = {}
    if not converted:
        if len(enrolled) > 1 or caller_scopes is not None:
            reader = route.checking_baseline().first_definition
            texts = route.governing_texts(root, subject.base, enrolled, policy)
            previous = {k: v for k, (v, _) in reader.check_documents(
                texts, enrolled, policy, allow_approved=True, allow_supporting_evidence=True).items()}
        else:
            prior = route.documents(root, subject.base, policy,
                                    readme=route.blob(root, subject.base, "docs/intent.md", optional=True) is None)
            previous = {k: v for k, (_, v, _) in prior.items()}
    provisional = False
    classified, allowed, all_ids = [], set(), set()
    for scope in enrolled:
        prefix = "" if scope == "." else scope + "/"
        def load(rev):
            return snapshot(policy, lambda name: route.blob(root, rev, name), prefix,
                            canonical=subject.repository == "ForgingAlpha/control-plane")
        before = load(subject.base) if converted else None
        after = load(subject.head)
        ids = {after.identities[selector] for selector in TRIO}
        require(all_ids.isdisjoint(ids), "duplicate governing identity across scopes")
        all_ids.update(ids)
        require(route.blob(root, subject.head, prefix + "docs/intent.md", optional=True) is None,
                "competing legacy Intent")
        for selector in TRIO[1:]:
            name = "docs/" + selector.split("#")[1] + ".md"
            require(name in after.details or route.blob(root, subject.head, prefix + name, optional=True) is None,
                    "unbound competing legacy document: " + name)
        metadata = before.metadata if before else {
            selector: previous[prefix + selector.split("#")[1]] for selector in TRIO}
        for selector in TRIO:
            old_meta, new_meta = metadata[selector], after.metadata[selector]
            provisional |= "provisional" in (old_meta.get("status"), new_meta.get("status"))
            for key, value in old_meta.items():
                if key.endswith("_sha256"):
                    require(key in new_meta, "removed authored governing digest")
                elif not before or key in {"id", "intent", "requirements", route.SELECTION, ENROLLMENT}:
                    require(new_meta.get(key) == value, "changed or removed protected source metadata: " + key)
        check_source_transfer(route, policy, root, subject, prefix, before, after)
        if before:
            if before.selection.instructions != after.selection.instructions:
                classified.append("instructions")
            if before.selection.outside != after.selection.outside:
                classified.append("outside")
        else:
            # The previously approved Intent has an exact transfer contract.
            old_intent = route.blob(root, subject.base, prefix + "docs/intent.md", optional=True)
            if old_intent is None:
                original = policy.readme_intent(route.blob(root, subject.base, prefix + "README.md")).canonical
            else:
                _, end = route.metadata(policy, old_intent)
                original = b"\n".join(old_intent.split(b"\n")[:end]) + b"\n" + route.transferred_intent(policy, old_intent)
            require(digest(original) == after.digests[TRIO[0]], "conversion changed protected Intent")
        if converted:
            allowed.update(prefix + path for path in ("README.md", MANIFEST, *after.details))
        print("Four-section digests " + json.dumps({"scope": scope, "digests": after.digests}, sort_keys=True))
    if provisional:
        require(converted and not classified and route.changed_paths(root, subject.base, subject.head) <= allowed,
                "provisional repair requires only governing definition changes")
    if "instructions" in classified:
        print("Local Instructions changed")
    return "definition-only" if provisional else "approved-structure"
