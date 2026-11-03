"""Public synthetic contracts; no private consumer commands or workflow copy."""

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = load("qualify_foundation")
custody = load("consumer_source")
IDS = ("merge_flow", "checkout", "evidence", "policy", "actions", "markdown", "dependencies", "updates", "coverage", "unit", "preflight", "preload", "qualification", "layout", "outcomes", "upload")
SHARED = dict(zip(("merge_flow", "policy", "actions", "markdown", "dependencies", "updates", "coverage"), ("ci-merge-flow", "ci-alphaapps-policy", "ci-github-actions", "ci-markdown", "ci-dependency-review", "ci-update-ownership", "ci-dependabot-coverage")))
PIN = "1" * 40


def synthetic():
    """Independently authored opaque commands, not Foundation product logic."""
    depends = {
        "merge_flow": (), "checkout": ("merge_flow",), "evidence": ("checkout",),
        **{k: ("checkout",) for k in SHARED if k != "merge_flow"},
        "unit": ("evidence",), "preflight": ("evidence", "unit"), "preload": ("preflight",),
        "qualification": ("preload",), "layout": ("qualification",),
        "outcomes": ("evidence",), "upload": ("evidence",),
    }
    steps = []
    for key in IDS:
        status = "always()" if key in ("outcomes", "upload") else "!cancelled()"
        expression = " && ".join([status, *(f"steps.{d}.outcome == 'success'" for d in depends[key])])
        step = {"name": key, "id": key, "if": "${{ " + expression + " }}"}
        if key in SHARED:
            step["uses"] = "ForgingAlpha/.github/actions/" + SHARED[key] + "@main"
            if key == "policy":
                step["with"] = {"repo-kind": "code"}
        elif key == "checkout":
            step.update(uses="actions/checkout@" + PIN, **{"with": {"ref": "${{ github.event.pull_request.head.sha }}", "fetch-depth": 0, "persist-credentials": False}})
        elif key == "upload":
            step.update(uses="actions/upload-artifact@" + PIN, **{"with": {"name": "synthetic", "path": "${{ runner.temp }}/synthetic", "if-no-files-found": "error", "retention-days": 14}})
        else:
            step.update(shell="bash", run="printf '%s\\n' 'opaque " + key + "'\n")
            if key == "evidence":
                step["env"] = {"SYNTHETIC": "source-owned input"}
            elif key == "outcomes":
                step["env"] = {"STEP_RESULTS": "${{ toJSON(steps) }}"}
        steps.append(step)
    steps.append({"name": "opaque original evaluator", "if": "${{ always() }}", "shell": "bash", "env": {"STEP_RESULTS": "${{ toJSON(steps) }}"}, "run": "printf '%s\\n' 'opaque final command'\n"})
    return {"name": "CI", "on": {"pull_request": {"branches": ["dev", "main"]}}, "permissions": {"contents": "read", "checks": "read", "pull-requests": "read"}, "jobs": {"CI": {"name": "CI", "runs-on": "ubuntu-24.04", "timeout-minutes": 60, "steps": steps}}}


def serialize(value):
    source = adapter.yaml.dump(value, Dumper=adapter.Dumper, sort_keys=False)
    for action in ("checkout", "upload-artifact"):
        source = source.replace("uses: actions/" + action + "@" + PIN + "\n", "uses: actions/" + action + "@" + PIN + " # synthetic immutable fixture\n")
    return source


def generate(value=None):
    return adapter.generate(serialize(synthetic() if value is None else value), "a" * 40, "b" * 40, "c" * 40, "d" * 40, "test/synthetic")


class ProjectionTests(unittest.TestCase):
    def test_deterministic_projection_preserves_owned_commands_and_original_evaluator(self):
        source = synthetic()
        before = copy.deepcopy(source)
        text = generate(source)
        self.assertEqual(text, generate(source))
        self.assertEqual(source, before)
        result = adapter.parse(text)
        job = result["jobs"]["compatibility"]
        self.assertEqual(result["name"], "Shared candidate compatibility")
        self.assertEqual(job["name"], "Shared candidate compatibility")
        self.assertEqual(result["permissions"], source["permissions"])
        self.assertEqual(job["runs-on"], "ubuntu-24.04")
        self.assertEqual(job["timeout-minutes"], 60)
        originals = [s for s in job["steps"] if s.get("id") in IDS]
        self.assertEqual([s["id"] for s in originals], list(IDS))
        self.assertEqual(job["steps"][-2], source["jobs"]["CI"]["steps"][-1])
        for expected, actual in zip(source["jobs"]["CI"]["steps"], originals):
            with self.subTest(step=expected["id"]):
                for key, value in expected.items():
                    if key not in ("if", "uses"):
                        self.assertEqual(actual[key], value)
                self.assertIn(expected["if"][4:-3], actual["if"])
        self.assertEqual(text.count("# synthetic immutable fixture"), 5)
        shared = [s for s in originals if s["id"] in SHARED]
        self.assertEqual(len(shared), 7)
        self.assertTrue(all(s["uses"].startswith("./shared-ci-candidate/actions/") for s in shared))
        for step in job["steps"]:
            if "run" in step:
                subprocess.run(["bash", "-n"], input=step["run"], text=True, check=True, capture_output=True)

    def test_additional_evaluator_refuses_every_non_success_outcome(self):
        steps = adapter.parse(generate())["jobs"]["compatibility"]["steps"]
        evaluator = steps[-1]["run"]
        required = [s["id"] for s in steps if "id" in s]
        self.assertEqual(len(required), 26)
        good = {key: {"outcome": "success", "conclusion": "success"} for key in required}
        def execute(value):
            return subprocess.run(["bash", "-c", evaluator], env={**os.environ, "STEP_RESULTS": json.dumps(value)}, text=True, capture_output=True)
        self.assertEqual(execute(good).returncode, 0)
        for key in required:
            for outcome in ("failure", "skipped", "cancelled", None):
                with self.subTest(key=key, outcome=outcome):
                    value = copy.deepcopy(good)
                    if outcome is None:
                        del value[key]
                    else:
                        value[key]["outcome"] = outcome
                    result = execute(value)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(key, result.stderr)

    def test_source_lifecycle_order_and_gates(self):
        steps = adapter.parse(generate())["jobs"]["compatibility"]["steps"]
        ids = [s.get("id") for s in steps]
        self.assertLess(ids.index("bootstrap_verify"), ids.index("merge_flow"))
        self.assertLess(ids.index("merge_flow"), ids.index("checkout"))
        self.assertLess(ids.index("checkout"), ids.index("candidate_verify"))
        self.assertLess(ids.index("candidate_verify"), ids.index("policy"))
        self.assertLess(ids.index("coverage"), ids.index("candidate_cleanup"))
        self.assertLess(ids.index("candidate_cleanup"), ids.index("unit"))
        self.assertLess(ids.index("layout"), ids.index("post_path"))
        self.assertLess(ids.index("post_verify"), ids.index("outcomes"))
        by_id = {s.get("id"): s for s in steps}
        self.assertIn("bootstrap_verify.outcome == 'success'", by_id["merge_flow"]["if"])
        self.assertIn("candidate_cleanup.outcome == 'success'", by_id["unit"]["if"])
        self.assertEqual(by_id["post_path"]["if"], "${{ always() && steps.candidate_cleanup.outcome == 'success' }}")
        self.assertEqual(by_id["post_checkout"]["if"], "${{ always() && steps.post_path.outcome == 'success' }}")
        self.assertEqual(by_id["post_verify"]["if"], "${{ always() && steps.post_checkout.outcome == 'success' }}")
        for key in ("bootstrap_checkout", "candidate_checkout", "post_checkout"):
            self.assertEqual(by_id[key]["with"]["ref"], "a" * 40)
            self.assertFalse(by_id[key]["with"]["persist-credentials"])

    def test_unsupported_workflow_changes_refuse(self):
        mutations = [
            lambda w: w.update(env={"EXTRA": "inherited"}),
            lambda w: w["jobs"].update(other={}),
            lambda w: w["permissions"].update(contents="write"),
            lambda w: w["jobs"]["CI"].update(strategy={}),
            lambda w: w["jobs"]["CI"]["steps"].pop(5),
            lambda w: w["jobs"]["CI"]["steps"].append({"run": "true"}),
            lambda w: w["jobs"]["CI"]["steps"][1].update(**{"continue-on-error": True}),
            lambda w: w["jobs"]["CI"]["steps"][1].update(**{"if": "${{ always() }}"}),
            lambda w: w["jobs"]["CI"]["steps"][3].update(uses="ForgingAlpha/.github/actions/ci-alphaapps-policy@" + PIN),
            lambda w: w["jobs"]["CI"]["steps"][1]["with"].update(ref="main"),
            lambda w: w["jobs"]["CI"]["steps"][-1].update(id="replacement"),
        ]
        for mutate in mutations:
            value = synthetic()
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                generate(value)

    def test_ambiguous_yaml_and_identity_injection_refuse(self):
        for text in ("x: 1\nx: 2\n", "x: &shared [1]\ny: *shared\n", "x: !!python/object {}", "x: 2026-01-01", "---\nx: 1\n---\ny: 2\n", "[" * 40 + "]" * 40, "x" * 131073):
            with self.subTest(text=text[:30]), self.assertRaises(ValueError):
                adapter.parse(text)
        for branch in ("main", "dev", "test/x' }}", "test/x\nrun: evil", "test//x"):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                adapter.generate(serialize(synthetic()), "a" * 40, "b" * 40, "c" * 40, "d" * 40, branch)


def git(path, *args):
    return subprocess.check_output(["git", "-c", "protocol.allow=never", "-C", str(path), *args], stderr=subprocess.PIPE).decode().strip()


def commit(path):
    git(path, "add", "--", ".gitignore", "module.py")
    git(path, "-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "synthetic fixture")
    return git(path, "rev-parse", "HEAD"), git(path, "rev-parse", "HEAD^{tree}")


class SourceCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name) / "consumer"
        self.workspace.mkdir()
        git(self.workspace, "init", "-q")
        (self.workspace / ".gitignore").write_text("__pycache__/\n")
        (self.workspace / "module.py").write_text("VALUE = 'consumer'\n")
        commit(self.workspace)
        self.root = self.workspace / "shared-ci-candidate"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "remote", "add", "origin", "https://github.com/ForgingAlpha/.github")
        (self.root / ".gitignore").write_text("__pycache__/\nignored\n")
        (self.root / "module.py").write_text("VALUE = 42\n")
        self.commit, self.tree = commit(self.root)

    def operation(self, operation):
        with contextlib.redirect_stdout(io.StringIO()):
            custody.operate(self.workspace, operation, self.commit, self.tree)

    def test_python_isolated_import_and_clean_owned_cleanup(self):
        code = "import importlib.util; s=importlib.util.spec_from_file_location('example','module.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.VALUE)"
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run(["python3", "-I", "-c", code], cwd=self.root, env=env, check=True, capture_output=True)
        self.assertTrue(list((self.root / "__pycache__").iterdir()))
        shutil.rmtree(self.root / "__pycache__")
        self.operation("prepare")
        result = subprocess.run(["python3", "-I", "-c", code], cwd=self.root, env=env, check=True, text=True, capture_output=True)
        self.assertEqual(result.stdout, "42\n")
        self.assertEqual(list((self.root / "__pycache__").iterdir()), [])
        self.assertEqual(git(self.root, "status", "--porcelain", "--ignored"), "")
        marker = Path(self.temporary.name) / "retained-evidence"
        marker.write_text("keep")
        self.operation("cleanup")
        self.assertFalse(self.root.exists())
        self.assertEqual(marker.read_text(), "keep")
        self.assertEqual((self.workspace / "module.py").read_text(), "VALUE = 'consumer'\n")

    def test_wrong_identity_and_modified_ignored_source_refuse(self):
        with self.assertRaisesRegex(ValueError, "commit"):
            custody.verify(self.root, "0" * 40, self.tree, prepared=False)
        with self.assertRaisesRegex(ValueError, "tree"):
            custody.verify(self.root, self.commit, "0" * 40, prepared=False)
        (self.root / "ignored").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "ignored"):
            self.operation("prepare")
        (self.root / "ignored").unlink()
        git(self.root, "update-index", "--assume-unchanged", "module.py")
        (self.root / "module.py").write_text("VALUE = 'substituted'\n")
        self.assertEqual(git(self.root, "status", "--porcelain"), "")
        with self.assertRaisesRegex(ValueError, "content differs"):
            self.operation("prepare")

    def test_source_returns_for_post_hooks_after_clean_product_checks(self):
        manifest = self.root / "actions/ci-markdown/action.yml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("name: synthetic local composite\n")
        git(self.root, "add", "--", "actions/ci-markdown/action.yml")
        git(self.root, "-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "synthetic post-hook manifest")
        self.commit, self.tree = git(self.root, "rev-parse", "HEAD"), git(self.root, "rev-parse", "HEAD^{tree}")
        snapshot = Path(self.temporary.name) / "candidate-source"
        shutil.copytree(self.root, snapshot)
        self.operation("prepare")
        self.operation("cleanup")
        # This is the observed native post-hook failure, before restoration.
        with self.assertRaises(FileNotFoundError):
            manifest.read_text()
        self.assertEqual(git(self.workspace, "status", "--porcelain", "--ignored"), "")
        shutil.copytree(snapshot, self.root)
        self.operation("prepare")
        self.assertEqual(manifest.read_text(), "name: synthetic local composite\n")
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.commit)

    def test_cache_collision_and_replacement_refuse_without_cleanup(self):
        cache = self.root / "__pycache__"
        cache.mkdir()
        with self.assertRaises(ValueError):
            self.operation("prepare")
        cache.rmdir()
        self.operation("prepare")
        cache.rmdir()
        cache.symlink_to(Path(self.temporary.name), target_is_directory=True)
        with self.assertRaises(ValueError):
            self.operation("cleanup")
        self.assertTrue(self.root.is_dir())
        cache.unlink()

    def test_candidate_path_symlink_and_origin_refuse(self):
        git(self.root, "remote", "set-url", "origin", "https://example.invalid/other")
        with self.assertRaisesRegex(ValueError, "repository"):
            self.operation("prepare")
        moved = self.root.with_name("unowned")
        self.root.rename(moved)
        self.root.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "owned directory"):
            self.operation("prepare")
        self.assertTrue((moved / "module.py").exists())

    def test_candidate_manifests_reject_nested_mixed_or_incomplete_sources(self):
        paths = []
        for name in SHARED.values():
            path = self.root / "actions" / name / "action.yml"
            path.parent.mkdir(parents=True)
            path.write_text("name: synthetic\nruns:\n  using: composite\n  steps:\n    - shell: bash\n      run: 'true'\n")
            paths.append(path.relative_to(self.root).as_posix())

        def checkpoint():
            git(self.root, "add", "--", *paths)
            git(self.root, "-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "synthetic manifests")
            return git(self.root, "rev-parse", "HEAD"), git(self.root, "rev-parse", "HEAD^{tree}")

        head, tree = checkpoint()
        adapter.candidate(self.root, head, tree)
        with self.assertRaisesRegex(ValueError, "tree mismatch"):
            adapter.candidate(self.root, head, "0" * 40)
        target = self.root / paths[0]
        for uses in ("./actions/helper", "ForgingAlpha/.github/actions/helper@main", "ForgingAlpha/.github/actions/helper@" + PIN, "${{ inputs.action }}"):
            target.write_text("name: synthetic\nruns:\n  using: composite\n  steps:\n    - uses: '" + uses + "'\n")
            head, tree = checkpoint()
            with self.subTest(uses=uses), self.assertRaisesRegex(ValueError, "nested"):
                adapter.candidate(self.root, head, tree)
        target.unlink()
        head, tree = checkpoint()
        with self.assertRaises(subprocess.CalledProcessError):
            adapter.candidate(self.root, head, tree)


if __name__ == "__main__":
    unittest.main()
