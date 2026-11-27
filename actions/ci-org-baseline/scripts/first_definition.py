"""Data-only checks for an explicitly registered first definition."""

import argparse
import base64
import hashlib
import json
import re

import yaml


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main_registration(repository_id, base, head, number, team_id):
    """Encode the operator's complete subject in one bounded repository property."""
    require(all(type(value) is int and value > 0 for value in (repository_id, number, team_id)),
            "positive repository, PR and team identities required")
    require(all(isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{40}", sha) for sha in (base, head))
            and base != head, "distinct base and head commit identities required")
    subject = ["v2", repository_id, "main", base, head, number, ".", team_id]
    data = json.dumps(subject, separators=(",", ":")).encode("ascii")
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    value = f"v2:{team_id}:{digest}"
    require(len(value) <= 75, "registration exceeds the repository property limit")
    return value


def registration(properties, number, head, *, branch="dev", repository_id=None, base=None):
    require(isinstance(properties, list) and all(isinstance(row, dict) for row in properties),
            "repository property evidence unavailable")
    values = [row.get("value") for row in properties if row.get("property_name") == "first_definition"]
    require(len(values) == 1 and isinstance(values[0], str) and len(values[0]) <= 75 and values[0].isascii(),
            "missing, ambiguous or invalid first-definition registration")
    if branch == "main":
        match = re.fullmatch(r"v2:([1-9][0-9]*):[A-Za-z0-9_-]{43}", values[0])
        require(match, "missing main-only first-definition registration")
        team_id = int(match[1])
        require(values[0] == main_registration(repository_id, base, head, number, team_id),
                "main-only registration differs from the exact subject")
        scopes = ["."]
    else:
        require(branch == "dev", "unsupported first-definition target")
        match = re.fullmatch(r"v1:([1-9][0-9]*):([a-f0-9]{40}):([1-9][0-9]*):([a-zA-Z0-9.,_-]+)", values[0])
        require(match and int(match[1]) == number and match[2] == head, "registration differs from the exact PR/head")
        scopes, team_id = parse_scopes(match[4]), int(match[3])
    return {"scopes": scopes, "team_id": team_id,
            "registration_sha256": hashlib.sha256(values[0].encode("ascii")).hexdigest()}


def parse_scopes(raw):
    require(isinstance(raw, str) and 0 < len(raw) <= 1024, "missing or oversized governing scopes")
    scopes = raw.split(",")
    require("." in scopes, "first definition must include the repository root")
    require(len(set(scopes)) == len(scopes) and all(scope == "." or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", scope)
                                                    for scope in scopes), "invalid registered governing scopes")
    return scopes


def json_config(name):
    name = name.casefold()
    return ("config" in name or name.endswith("rc.json") or name in {
        "package.json", "package-lock.json", "npm-shrinkwrap.json", "composer.json", "deno.json",
        "jsr.json", "renovate.json", "biome.json", "turbo.json", "nx.json", "angular.json",
        "project.json", "global.json", "tslint.json", "lerna.json", "vercel.json", "firebase.json",
    })


def required_ci(rules, *, strict=False):
    matched = False
    for rule in rules:
        if rule["type"] != "required_status_checks":
            continue
        parameters = rule.get("parameters")
        checks = parameters.get("required_status_checks") if isinstance(parameters, dict) else None
        require(isinstance(checks, list) and all(isinstance(check, dict) for check in checks),
                "malformed required status checks")
        for check in checks:
            if check.get("context") == "CI":
                app = check.get("integration_id")
                require(app is None or (type(app) is int and app == 15368), "required CI specifies a different app")
                if not strict or parameters.get("strict_required_status_checks_policy") is True:
                    matched = True
    require(matched, "effective branch rules lack required CI")


def required_codeql(rules):
    matched = False
    for rule in rules:
        if rule["type"] != "code_scanning":
            continue
        parameters = rule.get("parameters")
        tools = parameters.get("code_scanning_tools") if isinstance(parameters, dict) else None
        require(isinstance(tools, list) and all(isinstance(tool, dict) for tool in tools),
                "malformed code scanning rules")
        for tool in tools:
            if (tool.get("tool") == "CodeQL" and tool.get("alerts_threshold") in ("errors", "errors_and_warnings", "all")
                    and tool.get("security_alerts_threshold") in ("high_or_higher", "medium_or_higher", "all")):
                matched = True
    require(matched, "effective branch rules lack required CodeQL protection")


LINK = re.compile(r"\[([^\]\n]{1,256})\]\(([^\s)]{1,1024})\)")
PROSE_DIGEST = re.compile(r",?\s+(?:at\s+)?SHA-256\s+")
DIGEST_LITERAL = re.compile(r"`([a-f0-9]{64})`")
TABLE_DIGEST = re.compile(r"[ \t]*\|[ \t]*`([a-f0-9]{64})`")
README_TARGETS = {"../README.md#intent": "intent", "requirements.md": "requirements"}
INTENT_HEADING = re.compile(r"(?im)^ {0,3}#{1,6}[ \t]+intent[ \t#]*$")


# Original per-source label and suffix grammar. Search once per closing
# parenthesis so even long historic target spellings stay bounded by the input.
_HISTORICAL_LABELS = (r"(?:Product )?Intent", r"Requirements")
_HISTORICAL_PROSE = re.compile(r",? (?:at )?SHA-256\s*`([a-f0-9]{64})`")
_HISTORICAL_TABLE = re.compile(r" \| `([a-f0-9]{64})` \|")
_HISTORICAL_OPENERS = {
    table: tuple(re.compile((r"\| " if table else "") + r"\[(" + label + r")\]\(") for label in _HISTORICAL_LABELS)
    for table in (True, False)
}
_PRODUCT_PROSE_DIGEST = re.compile(r",?\s+(?:at\s+)?SHA-256\s*")


def historical_links(text):
    start = 0
    for close in re.finditer(r"\)", text):
        end = close.start()
        prose = _HISTORICAL_PROSE.match(text, end + 1)
        table = _HISTORICAL_TABLE.match(text, end + 1)
        if prose or table:
            left = max(start, text.rfind("\n", start, end) + 1)
            for opener in _HISTORICAL_OPENERS[table is not None]:
                label = opener.search(text, left, end)
                if label and label.end() < end:
                    yield label.start(1) - 1, label[1], text[label.end():end], (prose or table)[1]
        start = end + 1


def opening_links(text, *, product=False):
    historical = {}
    if product:
        for position, label, target, digest in historical_links(text):
            historical[position] = label, target, digest
    prose_form = _PRODUCT_PROSE_DIGEST if product else PROSE_DIGEST
    for link in LINK.finditer(text):
        if link.start() in historical:
            continue
        prose = prose_form.match(text, link.end())
        table = TABLE_DIGEST.match(text, link.end())
        digest = None
        if prose or table:
            value = DIGEST_LITERAL.match(text, prose.end()) if prose else table
            digest = value[1] if value else ""
        yield link[1], link[2], digest, False
    for label, target, digest in historical.values():
        yield label, target, digest, True


def governing_link_name(label, target, targets, *, product=False, legacy=False):
    """Recognize a governing target or a label claiming one."""
    name = targets.get(target)
    qualifiers = r"(?:[\w -]+ )?"
    if product and name is None:
        # Qualified external sources such as an organization's requirements
        # can carry checksums. A label claiming the selected source cannot
        # redirect its binding to such evidence.
        qualifiers = r"(?:(?:product|platform|component|scoped|local(?: development)?|development) )?"
    named = next((source for source in targets.values()
                  if re.fullmatch(qualifiers + source, label, re.IGNORECASE)), None)
    if legacy:
        return name or named
    require(not named or named == name, "wrong upstream governing link")
    return name


def check_bindings(kind, text, values, upstream, *, allow_supporting_evidence=False):
    # Both documentary forms bind the ID in metadata. The digest is either a
    # metadata field or explicitly attached to the upstream link in the opening.
    targets = {target: name for target, name in README_TARGETS.items() if name in upstream}
    counts = dict.fromkeys(upstream, 0)
    for name, (identity, digest) in upstream.items():
        require(values.get(name) == identity, "wrong or missing governing identity in " + kind)
        if name + "_sha256" in values:
            require(values[name + "_sha256"] == digest, "wrong governing digest in " + kind)
            counts[name] += 1
    opening = text.split("\n## ", 1)[0]
    for label, target, digest, _ in opening_links(opening, product=allow_supporting_evidence):
        # Bind the label and local link independently of the digest form.
        if digest is None and target.startswith(("https://", "http://")):
            continue
        evidence_link = allow_supporting_evidence and digest is not None
        name = governing_link_name(label, target, README_TARGETS if evidence_link else targets,
                                   product=allow_supporting_evidence)
        if digest is not None:
            if evidence_link and name is None:
                continue
            require(name in upstream, "digest link has wrong governing target in " + kind)
            require(digest == upstream[name][1], "wrong governing link digest in " + kind)
            counts[name] += 1
    require(all(counts.values()), "missing upstream governing digest in " + kind)
    return counts


def governing_lines(text, policy):
    # Refuse YAML graph expansion before using the shared frontmatter reader.
    lines = text.split("\n")
    require(lines[0] == "---", "governing frontmatter required")
    try:
        end = lines.index("---", 1, policy.MAX_FRONTMATTER_LINES + 2)
        tokens = yaml.scan("\n".join(lines[1:end]))
        require(not any(isinstance(t, (yaml.AliasToken, yaml.AnchorToken, yaml.TagToken)) for t in tokens),
                "unsupported governing frontmatter reference or tag")
    except (ValueError, yaml.YAMLError, RecursionError):
        raise ValueError("invalid first-definition frontmatter") from None
    return lines


def check_scope_inventory(texts, scopes):
    prefixes = [("" if scope == "." else scope + "/") for scope in scopes]
    selected = {prefix + name for prefix in prefixes
                for name in ("README.md", "docs/requirements.md", "docs/architecture.md")}
    require(selected <= texts.keys(), "missing registered governing source")
    for path, text in texts.items():
        lower = "/" + path.casefold()
        require(not lower.endswith("/docs/intent.md"), "competing legacy Intent")
        if lower.endswith(("/docs/requirements.md", "/docs/architecture.md")) or (
                lower.endswith("/readme.md") and INTENT_HEADING.search(text)):
            require(path in selected, "unregistered governing scope or source")
    return prefixes


def check_documents(texts, scopes, policy, *, allow_approved=False, allow_supporting_evidence=False):
    prefixes = check_scope_inventory(texts, scopes)
    identities, documents = set(), {}
    statuses = {"approved", "provisional"} if allow_approved else {"provisional"}
    for prefix in prefixes:
        readme = texts[prefix + "README.md"]
        governing_lines(readme, policy)
        intent = policy.readme_intent(readme.encode())
        upstream = {}
        for kind in ("intent", "requirements", "architecture"):
            if kind == "intent":
                values, data, bindings = intent.metadata, intent.canonical, {}
            else:
                text = texts[prefix + "docs/" + kind + ".md"]
                lines = governing_lines(text, policy)
                values, end = policy.leading_metadata(lines)
                require(any(line.startswith("# ") for line in lines[end:]), "missing governing document title")
                bindings = check_bindings(kind, "\n".join(lines[end:]), values, upstream,
                                          allow_supporting_evidence=allow_supporting_evidence)
                data = text.encode()
            identity = values.get("id")
            require(isinstance(values.get("status"), str) and values["status"] in statuses and isinstance(identity, str) and
                    re.fullmatch(r"[^\s\x00-\x1f\x7f]{1,512}", identity) and identity not in identities,
                    "invalid authored status or governing identity")
            identities.add(identity)
            upstream[kind] = identity, hashlib.sha256(data).hexdigest()
            documents[prefix + kind] = values, bindings
    return documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True).add_parser(
        "main-registration", help="print the property value for one main-only root definition")
    command.add_argument("--repository-id", type=int, required=True)
    command.add_argument("--base", required=True)
    command.add_argument("--head", required=True)
    command.add_argument("--pr", type=int, required=True)
    command.add_argument("--team-id", type=int, required=True)
    args = parser.parse_args()
    try:
        print(main_registration(args.repository_id, args.base, args.head, args.pr, args.team_id))
    except ValueError as error:
        parser.error(str(error))
