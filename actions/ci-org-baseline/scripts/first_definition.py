"""Data-only checks for an explicitly registered first definition."""

import hashlib
import re

import yaml


def require(condition, message):
    if not condition:
        raise ValueError(message)


def registration(properties, number, head):
    require(isinstance(properties, list) and all(isinstance(row, dict) for row in properties),
            "repository property evidence unavailable")
    values = [row.get("value") for row in properties if row.get("property_name") == "first_definition"]
    require(len(values) == 1 and isinstance(values[0], str) and len(values[0]) <= 75 and values[0].isascii(),
            "missing, ambiguous or invalid first-definition registration")
    match = re.fullmatch(r"v1:([1-9][0-9]*):([a-f0-9]{40}):([1-9][0-9]*):([a-zA-Z0-9.,_-]+)", values[0])
    require(match and int(match[1]) == number and match[2] == head, "registration differs from the exact PR/head")
    scopes = match[4].split(",")
    require("." in scopes, "first definition must include the repository root")
    require(len(set(scopes)) == len(scopes) and all(scope == "." or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", scope)
                                                    for scope in scopes), "invalid registered governing scopes")
    return {"scopes": scopes, "team_id": int(match[3]),
            "registration_sha256": hashlib.sha256(values[0].encode("ascii")).hexdigest()}


def json_config(name):
    name = name.casefold()
    return ("config" in name or name.endswith("rc.json") or name in {
        "package.json", "package-lock.json", "npm-shrinkwrap.json", "composer.json", "deno.json",
        "jsr.json", "renovate.json", "biome.json", "turbo.json", "nx.json", "angular.json",
        "project.json", "global.json", "tslint.json", "lerna.json", "vercel.json", "firebase.json",
    })


def required_ci(rules):
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
                matched = True
    require(matched, "effective branch rules lack required CI")


LINK = re.compile(r"\[([^\]\n]{1,256})\]\(([^\s)]{1,1024})\)")
PROSE_DIGEST = re.compile(r",?\s+(?:at\s+)?SHA-256\s+")
DIGEST_LITERAL = re.compile(r"`([a-f0-9]{64})`")
TABLE_DIGEST = re.compile(r"[ \t]*\|[ \t]*`([a-f0-9]{64})`")
INTENT_HEADING = re.compile(r"(?im)^ {0,3}#{1,6}[ \t]+intent[ \t#]*$")


def check_bindings(kind, text, values, upstream):
    # Both documentary forms bind the ID in metadata. The digest is either a
    # metadata field or explicitly attached to the upstream link in the opening.
    targets = {"intent": "../README.md#intent", "requirements": "requirements.md"}
    found = set()
    for name, (identity, digest) in upstream.items():
        require(values.get(name) == identity, "wrong or missing governing identity in " + kind)
        if name + "_sha256" in values:
            require(values[name + "_sha256"] == digest, "wrong governing digest in " + kind)
            found.add(name)
    opening = text.split("\n## ", 1)[0]
    for link in LINK.finditer(opening):
        label, target = link.groups()
        name = next((key for key in upstream if target == targets[key]), None)
        prose = PROSE_DIGEST.match(opening, link.end())
        table = TABLE_DIGEST.match(opening, link.end())
        # Bind the label and local link independently of the digest form.
        if prose or table or not target.startswith(("https://", "http://")):
            for key in upstream:
                if re.fullmatch(r"(?:[\w -]+ )?" + key, label, flags=re.IGNORECASE):
                    require(target == targets[key], "wrong local governing link in " + kind)
        if prose or table:
            require(name is not None, "digest link has wrong governing target in " + kind)
            value = DIGEST_LITERAL.match(opening, prose.end()) if prose else table
            require(value and value[1] == upstream[name][1], "wrong governing link digest in " + kind)
            found.add(name)
    require(found == set(upstream), "missing upstream governing digest in " + kind)


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


def check_documents(texts, scopes, policy):
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
    identities = set()
    for prefix in prefixes:
        readme = texts[prefix + "README.md"]
        governing_lines(readme, policy)
        intent = policy.readme_intent(readme.encode())
        upstream = {}
        for kind in ("intent", "requirements", "architecture"):
            if kind == "intent":
                values, data = intent.metadata, intent.canonical
            else:
                text = texts[prefix + "docs/" + kind + ".md"]
                lines = governing_lines(text, policy)
                values, end = policy.leading_metadata(lines)
                require(any(line.startswith("# ") for line in lines[end:]), "missing governing document title")
                check_bindings(kind, "\n".join(lines[end:]), values, upstream)
                data = text.encode()
            identity = values.get("id")
            require(values.get("status") == "provisional" and isinstance(identity, str) and
                    re.fullmatch(r"[^\s\x00-\x1f\x7f]{1,512}", identity) and identity not in identities,
                    "provisional governing sources require distinct authored IDs")
            identities.add(identity)
            upstream[kind] = identity, hashlib.sha256(data).hexdigest()
