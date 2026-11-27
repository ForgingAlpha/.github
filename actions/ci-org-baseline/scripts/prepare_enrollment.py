"""Preview an organization CI enrollment from committed data and reviewed owner inputs."""

import argparse
from contextlib import redirect_stdout
import difflib
import importlib.util
import json
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath


# Load only the validator from the selected, trusted shared-CI checkout.
spec = importlib.util.spec_from_file_location("enrollment_baseline", Path(__file__).with_name("baseline.py"))
ci = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ci
spec.loader.exec_module(ci)

CATALOG_PATH = "actions/ci-org-baseline/enrollment.json"
OWNER_FIELDS = {"branches", "producer", "qualification_subject", "release_route", "review_policy"}


def blob(root, inventory, name, limit=1024 * 1024):
    ci.require(name in inventory and inventory[name][0] in ("100644", "100755"),
               "missing tracked regular input: " + name)
    return ci.git(root, "cat-file", "blob", inventory[name][1], limit=limit)


def discover(root, inventory):
    """Discover unambiguous component roots. Cargo workspace membership needs native qualification."""
    result = {}
    unsupported = sorted(name for name in inventory if PurePosixPath(name).name in ci.UNSUPPORTED_MANIFESTS)
    ci.require(not unsupported, "shared CI owner must qualify unsupported ecosystem inputs: " + repr(unsupported))
    manifests = sorted(name for name in inventory if PurePosixPath(name).name in ("package.json", "Cargo.toml"))
    ci.require(len(manifests) <= 256, "manifest inventory exceeds limit")
    size = 0
    for name in manifests:
        path = PurePosixPath(name)
        directory = str(path.parent)
        data = blob(root, inventory, name)
        size += len(data)
        ci.require(size <= 8 * 1024 * 1024, "manifest bytes exceed limit")
        if path.name == "package.json":
            package = ci.decode(data)
            ci.require(isinstance(package, dict), f"invalid npm manifest at {name}")
            groups = [package.get(k, {}) for k in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")]
            ci.require(all(isinstance(group, dict) for group in groups), f"invalid npm dependencies at {name}")
            ci.require(any("astro" in group for group in groups), f"unsupported npm component at {name}; shared CI owner must qualify its profile")
            kind = "astro"
        else:
            manifest = tomllib.loads(data.decode())
            ci.require("workspace" not in manifest and isinstance(manifest.get("package"), dict) and
                       "workspace" not in manifest["package"],
                       f"Rust workspace at {name} needs reviewed roots and native workspace qualification")
            kind = "rust"
        ci.require(directory not in result, f"conflicting component types at {directory}")
        result[directory] = kind
    return result


def owner_fields(entry):
    astro_checks = {
        component["root"]: {key: value for key, value in component.items() if key not in ("kind", "root")}
        for component in entry["components"] if component["kind"] == "astro"
    }
    return {k: entry[k] for k in OWNER_FIELDS | {"repository", "repository_id"}} | {
        "astro_checks": astro_checks
    }


def make_entry(repository, repository_id, roots, fields):
    ci.require(isinstance(fields, dict), "product and protection owners must supply owner fields for a new enrollment")
    required = OWNER_FIELDS | {"astro_checks", "repository", "repository_id"}
    missing = sorted(required - fields.keys())
    ci.require(not missing, "product and protection owners must supply: " + ", ".join(missing))
    ci.require(set(fields) == required, "unexpected owner fields")
    ci.require(ci.positive(fields["repository_id"]) and
               (fields["repository"], fields["repository_id"]) == (repository, repository_id),
               "owner fields must identify the same repository by its positive integer ID and name")
    checks = fields["astro_checks"]
    ci.require(isinstance(checks, dict), "product owner must supply an astro_checks object keyed by component root")
    astro = {k for k, v in roots.items() if v == "astro"}
    ci.require(set(checks) == astro, "product owner must reconcile Astro check roots: " + repr(sorted(astro ^ set(checks))))
    components = []
    for path, kind in sorted(roots.items()):
        obligations = {"tests": ["cargo-all"]}
        if kind == "astro":
            obligations = checks[path]
            ci.require(isinstance(obligations, dict) and
                       set(obligations) - {"website_browser"} == {"static_scripts", "tests"},
                       "invalid product-owner Astro checks at " + path)
        components.append({"kind": kind, "root": path, **obligations})
    kinds = set(roots.values())
    profile = "mixed" if len(kinds) > 1 else next(iter(kinds), "documentation-bootstrap")
    return {"repository": repository, "repository_id": repository_id, "branches": fields["branches"],
            "profile": profile, "producer": fields["producer"], "qualification_subject": fields["qualification_subject"],
            "release_route": fields["release_route"], "review_policy": fields["review_policy"], "components": components}


def checked_governing_layout(root, branch, base, head, inventory, entry):
    event = {"pull_request": {"base": {"ref": branch, "sha": base}, "head": {"sha": head}}}
    pointer = ci.approved_readme_pointer(root, event, entry)
    if pointer is None:
        # The legacy policy reads files. Give it only the three committed sources
        # so it sees the same bytes in a bare repo or a modified consumer checkout.
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            for name in ci.policy.BASELINE_SOURCE_TRUTH_FILES:
                target = snapshot / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob(root, inventory, name))
            ci.require(not ci.policy.incomplete_baseline(ci.policy.baseline_statuses(snapshot)),
                       "complete approved structural governing metadata required")
    return pointer


def validate_candidate(root, branch, base, head, inventory, entry, runtime):
    ci.require(branch in entry["branches"], "selected branch is outside the approved enrollment")
    pointer = checked_governing_layout(root, branch, base, head, inventory, entry)
    if entry["profile"] == "documentation-bootstrap":
        ci.document_inputs(root, head, native_pointer=pointer)
        return
    ci.require((ci.README_REQUIRED if pointer else ci.REQUIRED) <= inventory.keys(), "missing required governing/project inputs")
    ci.require(not pointer or "PROJECT.md" not in inventory, "competing native project instructions")
    aliases = {"CLAUDE.md": b"AGENTS.md"} if pointer else dict.fromkeys(ci.ALIASES, b"PROJECT.md")
    for path, (mode, oid) in inventory.items():
        if mode == "120000":
            ci.require(path in aliases and ci.git(root, "cat-file", "blob", oid, limit=256) == aliases[path],
                       "unsupported linked application input: " + path)
        elif pointer and path in ci.ALIASES:
            ci.require(mode == "100644" and blob(root, inventory, path) == pointer, "invalid native README instruction pointer")
    ci.producer_check(root, inventory, entry, branch, read=blob)
    ci.classify(root, inventory, entry, read=blob)
    route = ci.declared_route(root, entry, base, head)
    assigned = ci.merge_flow().assigned_route(entry["repository_id"])
    ci.require(entry["branches"] == ["dev"] if assigned == "development" else assigned == route,
               "product release owner must reconcile the registered route and target branches")
    ci.application_integrity(root, inventory, entry, runtime, read=blob)


def preview(root, base, head, repository, repository_id, catalog, fields, runtime, *, branch):
    ci.catalog(catalog)
    ci.require(catalog["schema_version"] == 2, "the current schema-2 catalog is required")
    for revision in (base, head):
        ci.require(ci.SHA.fullmatch(revision) and ci.git(root, "cat-file", "-t", revision).strip() == b"commit",
                   "supply exact base and candidate commit IDs available in the consumer object store")
    entries = catalog["repositories"]
    old = next((row for row in entries if row["repository_id"] == repository_id or row["repository"] == repository), None)
    if old:
        ci.require((old["repository"], old["repository_id"]) == (repository, repository_id), "repository identity changed")
        if fields is None:
            fields = owner_fields(old)
    inventory = ci.tree_inventory(root, head)
    roots = discover(root, inventory)
    previous = {}
    # A newly enrolled consumer also has a past: deleting a manifest must not
    # weaken its first proposal simply because the central catalog has no row yet.
    if ci.git(root, "ls-tree", "--name-only", base, limit=32 * 1024 * 1024):
        previous = ci.tree_inventory(root, base)
        lost = discover(root, previous).items() - roots.items()
        ci.require(not lost, "product owner must reconcile removed or moved components: " + repr(sorted(lost)))
    entry = make_entry(repository, repository_id, roots, fields)
    updated = dict(catalog, repositories=[entry if item is old else item for item in entries] + ([] if old else [entry]))
    ci.catalog(updated)
    if previous and not roots and set(previous) != {"README.md"}:
        pointer = checked_governing_layout(root, branch, base, base, previous, entry)
        ci.document_inputs(root, base, native_pointer=pointer)
    if old:
        ci.require(entry["branches"] == old["branches"] and entry["review_policy"] == old["review_policy"],
                   "protection owner must reconcile changed branches or review policy separately")
        if old["components"] or not entry["components"]:
            ci.require(all(old[k] == entry[k] for k in OWNER_FIELDS) and all(c in entry["components"] for c in old["components"]),
                       "product and protection owners must reconcile changed obligations, roots or producer separately")
    validate_candidate(root, branch, base, head, inventory, entry, runtime)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer", type=Path, required=True, help="trusted local clone or bare object store for the identified consumer")
    parser.add_argument("--branch", choices=("dev", "staging", "main"), required=True, help="intended protected target branch")
    parser.add_argument("--base", required=True, help="verified protected base commit")
    parser.add_argument("--head", required=True, help="candidate commit")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--repository-id", required=True, type=int)
    parser.add_argument("--owner-fields", type=Path, help="reviewed owner inputs held outside the consumer")
    args = parser.parse_args()
    try:
        root = args.consumer.resolve(strict=True)
        bare = ci.git(root, "rev-parse", "--is-bare-repository").strip() == b"true"
        located = ci.git(root, "rev-parse", "--absolute-git-dir" if bare else "--show-toplevel").decode().strip()
        ci.require(root == Path(located).resolve(), "supply the consumer repository root")
        fields = None
        if args.owner_fields:
            ci.require(not args.owner_fields.resolve().is_relative_to(root), "owner inputs must be supplied outside the consumer")
            fields = ci.decode(ci.read_regular(args.owner_fields, 1024 * 1024)[0])
        source_sha = ci.git(ci.SOURCE, "rev-parse", "HEAD").decode().strip()
        ci.require(not ci.git(ci.SOURCE, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "HEAD", "--") and
                   not ci.git(ci.SOURCE, "ls-files", "--others", "--exclude-standard", "-z"),
                   "use a clean, reviewed shared-CI checkout to bind the preview to its source revision")
        before = (ci.SOURCE / CATALOG_PATH).read_text(encoding="utf-8")
        catalog = ci.decode(before.encode())
        # The governance validator emits additional receipts on converted consumers.
        with redirect_stdout(sys.stderr):
            updated = preview(root, args.base, args.head, args.repository, args.repository_id,
                              catalog, fields, None, branch=args.branch)
        after = before if updated == catalog else json.dumps(updated, indent=2, ensure_ascii=False) + "\n"
        action = "unchanged" if updated == catalog else "proposed"
        print(f"Offline enrollment {action} for {args.repository} ({args.repository_id}); target {args.branch}@{args.base}, candidate {args.head}; shared source {source_sha}.", file=sys.stderr)
        sys.stdout.writelines(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                   "a/" + CATALOG_PATH, "b/" + CATALOG_PATH))
        return 0
    except (ValueError, OSError, TypeError, RecursionError, KeyError) as error:
        print("Enrollment preview refused: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
