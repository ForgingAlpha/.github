"""Exercise the published action, its provider bindings and the shared route decisions."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "actions/ci-merge-flow"
STEP = yaml.safe_load((ACTION / "action.yml").read_text())["runs"]["steps"][0]
SPEC = importlib.util.spec_from_file_location("merge_flow", ACTION / "scripts/check_merge_flow.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
SITE = "ForgingAlpha/site"
SOURCE_ID = "1137664016"
CONSUMER_ID = "960093720"
HEAD = "1" * 40
BASE = "2" * 40


class MergeFlowBehaviorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.action = self.root / "actions/ci-merge-flow"
        shutil.copytree(ACTION, self.action)
        verifier = self.root / "actions/security-patch/scripts/security_patch.py"
        verifier.parent.mkdir(parents=True)
        verifier.write_text("""import json, os, sys
from pathlib import Path
Path('verifier.json').write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ['VERIFIER_STATUS']))
""")
        gh = self.root / "gh"
        gh.write_text("""#!/usr/bin/env python3
import json, sys
from pathlib import Path
assert sys.argv[1] == 'api'
path = sys.argv[2]
with Path('queries').open('a') as handle: print(path, file=handle)
result = json.loads(Path('api.json').read_text()).get(path)
if not result: sys.exit(1)
print(json.dumps(result))
""")
        gh.chmod(0o755)

    def run_action(self, route="direct", target="main", head="dev", repo=SITE, repo_id=CONSUMER_ID,
                   source=None, source_id=None, changes=(), mutate=None, verifier=1):
        source = source if source is not None else repo
        source_id = source_id if source_id is not None else repo_id
        context = {"github.token": "fixture-token", "github.event.pull_request.number": "7"}
        for side, ref, name, rid, sha in (("base", target, repo, repo_id, BASE),
                                           ("head", head, source, source_id, HEAD)):
            for key, value in (("ref", ref), ("repo.full_name", name), ("repo.id", rid), ("sha", sha)):
                context[f"github.event.pull_request.{side}.{key}"] = value
        env = {k: context[v.removeprefix("${{ ").removesuffix(" }}")] for k, v in STEP["env"].items()}
        env.update(GITHUB_ACTION_PATH=str(self.action), GITHUB_REPOSITORY=repo, GITHUB_REPOSITORY_ID=repo_id,
                   PATH=f"{self.root}:{os.environ['PATH']}", VERIFIER_STATUS=str(verifier))
        env.update(changes)
        assignments = {k: [] for k in GUARD.ROUTES}
        if route:
            assignments[route] = [int(repo_id)]
        (self.action / "routes.json").write_text(json.dumps(assignments))
        live = {side: {"repo": {"full_name": name, "id": int(rid)}, "ref": ref, "sha": sha}
                for side, name, rid, ref, sha in (("base", repo, repo_id, target, BASE),
                                                   ("head", source, source_id, head, HEAD))}
        live.update(state="open", number=7)
        prefix = "repos/" + repo
        rows = {f"{prefix}/pulls/7": live}
        for ref, sha in ((target, BASE), (head, HEAD), ("dev", HEAD)):
            rows[f"{prefix}/branches/{ref}"] = {"name": ref, "protected": True, "commit": {"sha": sha}}
        if mutate:
            mutate(rows)
        (self.root / "api.json").write_text(json.dumps(rows))
        for name in ("queries", "verifier.json"):
            (self.root / name).unlink(missing_ok=True)
        result = subprocess.run(["bash", "-c", STEP["run"]], env=env, cwd=self.root, capture_output=True,
                                text=True, timeout=6)
        proof = self.root / "verifier.json"
        return result, json.loads(proof.read_text()) if proof.exists() else []

    def expect(self, allowed, **case):
        result, proof = self.run_action(**case)
        self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
        return proof

    def test_tasks_and_ordinary_releases(self):
        self.expect(True)
        self.expect(False, route="staged", head="staging")
        for route in ("direct", "staged", "development"):
            self.expect(True, route=route, target="dev", head="feature/go", source="contributor/site", source_id="45")
            for head in GUARD.PERSISTENT:
                with self.subTest(route=route, head=head):
                    self.expect(False, route=route, target="dev", head=head)
        self.expect(False, route="development", target="main")
        self.expect(False, route="development", target="staging")
        self.expect(False, route="direct", target="staging")
        self.expect(False, route="staged", head="dev", target="main", verifier=0)
        self.expect(False, route="staged", head="dev", target="staging", verifier=0)
        # Source equality alone does not authorize occupancy or repair of staging.
        self.expect(False, route="staged", head="release/verified-snapshot", target="staging")
        self.expect(False, route=None)
        self.expect(False, route="direct", target="anything", head="task")

    def test_promotion_binds_live_repository_refs_and_protected_tips(self):
        pr = f"repos/{SITE}/pulls/7"
        for change in (lambda r: r[pr]["head"].update(ref="other"),
                       lambda r: r[pr]["head"]["repo"].update(id=41),
                       lambda r: r[pr]["base"].update(sha=HEAD),
                       lambda r: r[pr].update(state="closed"),
                       lambda r: r[f"repos/{SITE}/branches/dev"].update(protected=False),
                       lambda r: r[f"repos/{SITE}/branches/main"]["commit"].update(sha=HEAD)):
            with self.subTest(change=change):
                self.expect(False, mutate=change)
        self.expect(False, source="contributor/site", source_id="22")
        self.expect(False, source="contributor/site", source_id=CONSUMER_ID)
        self.expect(False, source=SITE, source_id="22")

    def test_security_projection_uses_exact_existing_verifier(self):
        expected = ["verify-ci-admission", "--repository", SITE, "--pull-request", "7", "--target-branch", "main"]
        for route in ("direct", "staged"):
            self.assertEqual(self.expect(True, route=route, head="task", verifier=0), expected)
            self.assertEqual(self.expect(False, route=route, head="task", verifier=1), expected)
        self.assertFalse(self.expect(False, target="staging", head="task", verifier=0))

    def test_main_only_source_identity_and_branch(self):
        subject = dict(route="main-only", repo="ForgingAlpha/.github", repo_id=SOURCE_ID)
        self.expect(True, **subject, head="feature/change")
        self.expect(True, **subject, head="feature/change", source="contributor/.github", source_id="22")
        for ref in ("main", "dev", "staging", "bad..ref", "bad ref"):
            self.expect(False, **subject, head=ref)
        for target in ("dev", "staging"):
            self.expect(False, **subject, target=target, head="feature")
        for key in ("BASE_REPOSITORY", "BASE_REPOSITORY_ID", "GITHUB_REPOSITORY", "GITHUB_REPOSITORY_ID"):
            self.expect(False, **subject, head="task", changes={key: "wrong"})
        for name, rid in (("ForgingAlpha/.github", "99"), ("contributor/x", SOURCE_ID), ("owner/..", "22")):
            self.expect(False, **subject, head="task", source=name, source_id=rid)
        for ref in ("task/$(touch${IFS}SENTINEL)", "task/`touch${IFS}SENTINEL`"):
            self.expect(True, **subject, head=ref)
            self.assertFalse((self.root / "SENTINEL").exists())

    def test_published_assignments_and_dispatch(self):
        self.assertEqual(GUARD.assigned_route(1137664016), "main-only")
        self.assertEqual(GUARD.assigned_route(960093720), "direct")
        for identity in (1459389966, 1459393022):
            self.assertEqual(GUARD.assigned_route(identity), "development")
        with self.assertRaises(ValueError):
            GUARD.assigned_route(99)
        self.assertEqual(STEP["if"], "${{ github.event_name == 'pull_request' }}")
        self.assertNotIn("inputs", yaml.safe_load((ACTION / "action.yml").read_bytes()))
