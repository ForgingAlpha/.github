"""Generate a disposable Foundation PR workflow from its exact owned CI source.

Requires the existing shared CI dependency PyYAML. Does not publish or execute code.
Unsupported consumer workflow changes require a reviewed adapter update.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml


SHARED = {
    "merge_flow": "ci-merge-flow", "policy": "ci-alphaapps-policy",
    "actions": "ci-github-actions", "markdown": "ci-markdown",
    "dependencies": "ci-dependency-review", "updates": "ci-update-ownership",
    "coverage": "ci-dependabot-coverage",
}
ORIGINAL = (
    "merge_flow", "checkout", "evidence", "policy", "actions", "markdown",
    "dependencies", "updates", "coverage", "unit", "preflight", "preload",
    "qualification", "layout", "outcomes", "upload",
)
CUSTODY = (
    "bootstrap_path", "bootstrap_checkout", "bootstrap_verify", "candidate_path",
    "candidate_checkout", "candidate_verify", "candidate_cleanup",
    "post_path", "post_checkout", "post_verify",
)
CANDIDATE_PATH = "shared-ci-candidate"
TITLE = "Shared candidate compatibility"
SUCCESS = lambda step: f"steps.{step}.outcome == 'success'"


def require(condition, message):
    if not condition:
        raise ValueError(message + "; unsupported input requires a reviewed adapter update")


class Loader(yaml.SafeLoader):
    yaml_implicit_resolvers = {
        key: [(tag, pattern) for tag, pattern in rules if tag != "tag:yaml.org,2002:bool"]
        for key, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.I), list("tTfF"))


def mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        require(isinstance(key, str) and key not in result and key != "<<", "duplicate or non-string YAML key")
        result[key] = loader.construct_object(value_node)
    return result


Loader.add_constructor("tag:yaml.org,2002:map", mapping)


def parse(source):
    require(isinstance(source, str) and len(source.encode()) <= 131072, "YAML exceeds input limit")
    try:
        for token in yaml.scan(source):
            require(not isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken, yaml.tokens.TagToken)), "YAML anchors, aliases or tags are unsupported")
        value = yaml.load(source, Loader=Loader)
        count = 0

        def bounded(node, depth=0):
            nonlocal count
            count += 1
            require(depth < 20 and count <= 5000, "YAML nesting or node limit exceeded")
            require(type(node) in (dict, list, str, bool, int, type(None)), "unsupported YAML scalar")
            for child in (node.values() if isinstance(node, dict) else node if isinstance(node, list) else []):
                bounded(child, depth + 1)

        bounded(value)
        return value
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError("invalid or excessively nested YAML") from exc


def condition(*dependencies, always=False):
    return "${{ " + " && ".join(["always()" if always else "!cancelled()", *(SUCCESS(d) for d in dependencies)]) + " }}"


def conjoin(expression, dependency):
    return expression[:-3] + " && " + SUCCESS(dependency) + " }}"


def workflow(source):
    value = parse(source)
    require(isinstance(value, dict) and set(value) == {"name", "on", "permissions", "jobs"}, "unsupported root fields")
    require(value["name"] == "CI" and value["on"] == {"pull_request": {"branches": ["dev", "main"]}}, "unsupported workflow identity or trigger")
    require(value["permissions"] == {"contents": "read", "checks": "read", "pull-requests": "read"}, "unsupported workflow permissions")
    require(isinstance(value["jobs"], dict) and set(value["jobs"]) == {"CI"}, "expected one CI job")
    job = value["jobs"]["CI"]
    require(isinstance(job, dict) and set(job) == {"name", "runs-on", "timeout-minutes", "steps"}, "unsupported job settings")
    require(job["name"] == "CI" and job["runs-on"] == "ubuntu-24.04" and type(job["timeout-minutes"]) is int and job["timeout-minutes"] == 60, "unsupported job execution contract")
    steps = job["steps"]
    require(isinstance(steps, list) and len(steps) == 17 and all(isinstance(s, dict) for s in steps), "expected original 17 steps")
    require([s.get("id") for s in steps] == [*ORIGINAL, None], "changed step order, missing or extra outcome")
    dependencies = {
        "merge_flow": (), "checkout": ("merge_flow",), "evidence": ("checkout",),
        **{key: ("checkout",) for key in SHARED if key != "merge_flow"},
        "unit": ("evidence",), "preflight": ("evidence", "unit"), "preload": ("preflight",),
        "qualification": ("preload",), "layout": ("qualification",),
        "outcomes": ("evidence",), "upload": ("evidence",),
    }
    for step in steps:
        key = step.get("id")
        require(isinstance(step.get("name"), str) and bool(step["name"]), "step has no name")
        require(step.get("if") == condition(*dependencies.get(key, ()), always=key in (None, "outcomes", "upload")), "changed original condition")
        fields = {"name", "if"} | ({"id"} if key else set())
        if key in SHARED:
            fields.add("uses")
            require(step.get("uses") == f"ForgingAlpha/.github/actions/{SHARED[key]}@main", "mixed or unexpected shared source")
            if key == "policy":
                fields.add("with")
                require(step.get("with") == {"repo-kind": "code"}, "changed policy inputs")
        elif key in ("checkout", "upload"):
            fields |= {"uses", "with"}
            action = "checkout" if key == "checkout" else "upload-artifact"
            require(isinstance(step.get("uses"), str) and re.fullmatch(rf"actions/{action}@[0-9a-f]{{40}}", step["uses"]), "external action must retain an immutable pin")
            require(re.search(r"uses: " + re.escape(step["uses"]) + r"\s+# [^\n]+", source), "missing reviewed external release comment")
            inputs = step.get("with")
            if key == "checkout":
                require(inputs == {"ref": "${{ github.event.pull_request.head.sha }}", "fetch-depth": 0, "persist-credentials": False}, "changed exact consumer checkout")
            else:
                require(isinstance(inputs, dict) and set(inputs) == {"name", "path", "if-no-files-found", "retention-days"}, "changed upload inputs")
                require(inputs["if-no-files-found"] == "error" and type(inputs["retention-days"]) is int and inputs["retention-days"] == 14, "changed evidence retention")
                require(all(isinstance(inputs[k], str) and inputs[k] for k in ("name", "path")), "invalid artifact locator")
        else:
            fields |= {"shell", "run"}
            require(step.get("shell") == "bash" and isinstance(step.get("run"), str) and bool(step["run"]), "unsupported run step")
            if key in (None, "evidence", "outcomes"):
                fields.add("env")
                require(isinstance(step.get("env"), dict) and all(isinstance(v, str) for v in step["env"].values()), "unsupported run environment")
                if key in (None, "outcomes"):
                    require(step["env"] == {"STEP_RESULTS": "${{ toJSON(steps) }}"}, "changed outcome input")
        require(set(step) == fields, "unsupported step fields")
    return value


def git(repository, *args):
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(repository), *args], stderr=subprocess.PIPE)


def revision(repository, commit, tree):
    require(all(re.fullmatch(r"[0-9a-f]{40}", v) for v in (commit, tree)), "exact commit and tree required")
    require(git(repository, "cat-file", "-t", commit).strip() == b"commit", "source is not a commit")
    require(git(repository, "rev-parse", commit + "^{tree}").decode().strip() == tree, "source tree mismatch")


def candidate(repository, commit, tree):
    revision(repository, commit, tree)
    for item in git(repository, "ls-tree", "-rz", commit).split(b"\0"):
        if not item:
            continue
        metadata, path = item.split(b"\t", 1)
        mode, kind, _ = metadata.split()
        require(mode in (b"100644", b"100755") and kind == b"blob" and b"__pycache__" not in path.split(b"/"), "unsupported candidate tree entry")
    for action in SHARED.values():
        manifest = parse(git(repository, "show", f"{commit}:actions/{action}/action.yml").decode())
        require(isinstance(manifest, dict) and isinstance(manifest.get("runs"), dict), "missing action execution contract")
        runs = manifest["runs"]
        require(runs.get("using") == "composite" and isinstance(runs.get("steps"), list) and bool(runs["steps"]), "expected composite action")
        for step in runs["steps"]:
            require(isinstance(step, dict), "invalid composite step")
            if "uses" in step:
                uses = step["uses"]
                require(isinstance(uses, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}", uses) and not uses.lower().startswith("forgingalpha/"), "nested local or first-party action is unsupported")


class Dumper(yaml.SafeDumper):
    pass


def string(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


Dumper.add_representer(str, string)


def generate(source, commit, tree, consumer_commit, consumer_tree, branch):
    require(all(re.fullmatch(r"[0-9a-f]{40}", v) for v in (commit, tree, consumer_commit, consumer_tree)), "exact source identities required")
    require(re.fullmatch(r"test/[a-z0-9][a-z0-9/_-]{0,99}", branch) and "//" not in branch and not branch.endswith("/"), "fixture branch must be a bounded test branch")
    result = workflow(source)
    original = result["jobs"]["CI"]["steps"]
    checkout = original[1]["uses"]
    runtime = Path(__file__).with_name("consumer_source.py").read_text()

    def run_step(key, body, guard):
        return {"name": key.replace("_", " ").capitalize(), "id": key, "if": guard, "shell": "bash", "run": body}

    def acquire(prefix, predecessor=None, *, always=False):
        free = prefix + "_path"
        fetch = prefix + "_checkout"
        checked = prefix + "_verify"
        return [
            run_step(free, f"set -euo pipefail\ntest ! -e '{CANDIDATE_PATH}' && test ! -L '{CANDIDATE_PATH}'\n", condition(*([predecessor] if predecessor else []), always=always)),
            {"name": "Acquire exact shared candidate", "id": fetch, "if": condition(free, always=always), "uses": checkout,
             "with": {"repository": "ForgingAlpha/.github", "ref": commit, "path": CANDIDATE_PATH, "fetch-depth": 1, "persist-credentials": False}},
            run_step(checked, source_command("prepare"), condition(fetch, always=always)),
        ]

    def source_command(operation):
        return f"set -euo pipefail\npython3 -I -B - {operation} {commit} {tree} <<'PY'\n{runtime}\nPY\n"

    emitted = acquire("bootstrap")
    for initial in original:
        step = copy.deepcopy(initial)
        key = step.get("id")
        if key in SHARED:
            step["uses"] = f"./{CANDIDATE_PATH}/actions/{SHARED[key]}"
            step["if"] = conjoin(step["if"], "bootstrap_verify" if key == "merge_flow" else "candidate_verify")
        if key == "unit":
            emitted.append(run_step("candidate_cleanup", source_command("cleanup"), condition("candidate_verify")))
            step["if"] = conjoin(step["if"], "candidate_cleanup")
        if key == "outcomes":
            # The runner reloads local composite manifests for nested Action post
            # hooks. Restore them after clean-tree product checks, even on failure.
            emitted.extend(acquire("post", "candidate_cleanup", always=True))
        emitted.append(step)
        if key == "checkout":
            emitted.extend(acquire("candidate", "checkout"))
    evaluator = (
        "set -euo pipefail\npython3 -I -B - <<'PY'\nimport json, os\n"
        "steps = json.loads(os.environ['STEP_RESULTS'])\n"
        f"required = {(*ORIGINAL, *CUSTODY)!r}\n"
        "failed = {key: steps.get(key, {}).get('outcome', 'missing') for key in required "
        "if steps.get(key, {}).get('outcome') != 'success'}\n"
        "if failed:\n    raise SystemExit('Compatibility work did not succeed: ' + json.dumps(failed, sort_keys=True))\n"
        "print('All consumer and source custody outcomes succeeded.')\nPY\n"
    )
    emitted.append({"name": "Require complete consumer compatibility", "if": condition(always=True), "shell": "bash", "env": {"STEP_RESULTS": "${{ toJSON(steps) }}"}, "run": evaluator})
    result["name"] = TITLE
    result["on"] = {"pull_request": {"branches": ["dev"]}}
    job = result["jobs"].pop("CI")
    job["name"] = TITLE
    job["if"] = "${{ github.repository == 'ForgingAlpha/container-foundation' && github.event.pull_request.head.repo.full_name == github.repository && github.head_ref == '" + branch + "' }}"
    job["steps"] = emitted
    result["jobs"]["compatibility"] = job
    identity = {"shared_commit": commit, "shared_tree": tree, "consumer_commit": consumer_commit, "consumer_tree": consumer_tree, "workflow_sha256": hashlib.sha256(source.encode()).hexdigest()}
    output = "# Generated disposable fixture; never merge.\n# Inputs: " + json.dumps(identity, sort_keys=True) + "\n"
    output += yaml.dump(result, Dumper=Dumper, sort_keys=False, width=100000)
    # Preserve the consumer's reviewed release annotations, including added checkouts.
    for ref, comment in re.findall(r"uses: (actions/(?:checkout|upload-artifact)@[0-9a-f]{40})\s+# ([^\n]+)", source):
        output = output.replace("uses: " + ref + "\n", "uses: " + ref + " # " + comment + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("consumer-repo", "consumer-commit", "consumer-tree", "candidate-repo", "candidate-commit", "candidate-tree", "branch", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    revision(args.consumer_repo, args.consumer_commit, args.consumer_tree)
    candidate(args.candidate_repo, args.candidate_commit, args.candidate_tree)
    source = git(args.consumer_repo, "show", args.consumer_commit + ":.github/workflows/ci.yml").decode()
    output = generate(source, args.candidate_commit, args.candidate_tree, args.consumer_commit, args.consumer_tree, args.branch)
    with Path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(output)


if __name__ == "__main__":
    main()
