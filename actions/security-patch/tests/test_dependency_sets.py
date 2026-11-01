"""Real Git objects; synthetic GitHub metadata, signatures, checks and writes.

These exercise the producer/reader state machine, not hosted/App qualification.
"""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
from urllib.parse import unquote

from test_security_patch import security_patch as sp, source_candidate_fixture, encoded_blob


DECLARATION = json.loads((Path(sp.__file__).parents[1] / "profiles.json").read_text())
SET_ROWS = [r for r in DECLARATION["repositories"] if "/" in r["pairs"][0]["lock_path"]]


class GitProvider:
    """Bounded local Git store with explicit synthetic provider state/effects."""
    def __init__(self, directory, row, pairs=None, manifests=False, branch="dev"):
        self.root = Path(directory)
        self.root.mkdir()
        self.repo, self.identity = row["repository"], row["repository_id"]
        self.pairs = copy.deepcopy(pairs or row["pairs"])
        self.branch = branch
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                    "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                    "GIT_AUTHOR_DATE": "2026-08-16T12:00:00Z", "GIT_COMMITTER_DATE": "2026-08-16T12:00:00Z"}
        self.git("init", "--quiet")
        self.gets, self.page_values, self.posts, self.refs, self.checks, self.pulls = {}, {}, [], {}, {}, {}
        self.lose_response = None
        self.ghsas = ("GHSA-abcd-efgh-ijkl", "GHSA-mnop-qrst-uvwx")
        leaves = {"README.md": self.blob("production-independent sibling\n"),
                  "PROJECT.md": self.blob("# Owner\n\nApplication.\n\n## End\n")}
        for pair in self.pairs:
            leaves[pair["manifest_path"]] = self.blob("manifest before\n")
            leaves[pair["lock_path"]] = self.blob("lock before\n")
            prefix = pair["lock_path"].rpartition("/")[0]
            leaves[(prefix + "/" if prefix else "") + "sibling.txt"] = self.blob("nested untouched\n")
        self.base = self.commit(self.tree(leaves), [])
        after = dict(leaves)
        for pair in self.pairs:
            after[pair["lock_path"]] = self.blob("lock after " + pair["lock_path"] + "\n")
            if manifests:
                after[pair["manifest_path"]] = self.blob("manifest after\n")
        self.changed = sorted(p for p in after if leaves[p] != after[p])
        self.head = self.commit(self.tree(after), [self.base])
        self.merge = self.commit(self.gets[self.endpoint("git/commits/" + self.head)]["tree"]["sha"], [self.base, self.head])
        production = {**leaves, "production-only.txt": self.blob("main only\n")}
        self.main = self.commit(self.tree(production), [self.base])
        self.refs.update({branch: self.base, "main": self.base if branch == "main" else self.main})
        self.original_main_leaves = production
        self.gets[self.endpoint("")] = {"full_name": self.repo, "id": self.identity, "default_branch": branch}
        self.pulls[17] = {"number": 17, "state": "open", "draft": False, "auto_merge": None, "labels": [],
            "changed_files": len(self.changed), "commits": 1, "user": {"login": "dependabot[bot]"},
            "base": {"ref": branch, "sha": self.base, "repo": {"full_name": self.repo, "id": self.identity}},
            "head": {"ref": "dependabot/security", "sha": self.head, "repo": {"full_name": self.repo, "id": self.identity}},
            "merge_commit_sha": self.merge}
        self.page_values[self.endpoint("pulls/17/files?per_page=100")] = [[{"filename": p, "status": "modified"} for p in self.changed]]
        signed = copy.deepcopy(source_candidate_fixture().page_values["repos/ForgingAlpha/alphaapps-site/pulls/17/commits?per_page=100"])
        signed[0][0]["sha"] = self.head
        self.page_values[self.endpoint("pulls/17/commits?per_page=100")] = signed
        self.gets[self.endpoint("actions/runs/901")] = {"id": 901, "name": "CI", "path": ".github/workflows/ci.yml",
            "event": "pull_request", "status": "completed", "conclusion": "success", "head_sha": self.head,
            "repository": {"full_name": self.repo}, "head_repository": {"full_name": self.repo},
            "actor": {"login": "dependabot[bot]"}, "pull_requests": [{"number": 17,
                "base": {"ref": branch, "sha": self.base}, "head": {"sha": self.head}}]}
        self.page_values[self.endpoint(f"commits/{self.head}/check-runs?filter=latest&per_page=100")] = [{"check_runs": [
            {"name": name, "head_sha": self.head, "status": "completed", "conclusion": "success", "app": {"id": app}}
            for name, app in (("CI", sp.TRUSTED_CI_APP_ID), ("CodeQL", sp.TRUSTED_CODEQL_APP_ID))]}]

    def endpoint(self, suffix):
        return "repos/" + self.repo + ("/" + suffix if suffix else "")

    def git(self, *args, data=None):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=self.root, env=self.env, input=data).decode().strip()

    def blob(self, text):
        raw = text.encode()
        oid = self.git("hash-object", "-w", "--stdin", data=raw)
        self.gets[self.endpoint("git/blobs/" + oid)] = encoded_blob(raw)
        return oid

    def tree(self, leaves):
        def build(group):
            direct, children = {}, {}
            for name, oid in group.items():
                if "/" in name:
                    first, rest = name.split("/", 1)
                    children.setdefault(first, {})[rest] = oid
                else:
                    direct[name] = ("100644", "blob", oid)
            for name, nested in children.items():
                direct[name] = ("040000", "tree", build(nested))
            entries = [{"path": n, "mode": m, "type": k, "sha": o} for n, (m, k, o) in sorted(direct.items())]
            raw = b"".join(f"{e['mode']} {e['type']} {e['sha']}\t{e['path']}\0".encode() for e in entries)
            oid = self.git("mktree", "-z", data=raw)
            self.gets[self.endpoint("git/trees/" + oid)] = {"truncated": False, "tree": entries}
            return oid
        return build(leaves)

    def leaves(self, tree):
        result = {}
        for line in self.git("ls-tree", "-r", tree).splitlines():
            meta, path = line.split("\t")
            result[path] = meta.split()[2]
        return result

    def commit(self, tree, parents, message="fixture"):
        args = ["commit-tree", tree]
        for parent in parents:
            args += ["-p", parent]
        oid = self.git(*args, data=message.encode())
        self.gets[self.endpoint("git/commits/" + oid)] = {"tree": {"sha": tree}, "parents": [{"sha": p} for p in parents],
            "committer": {"date": "2026-08-16T12:00:00Z"}}
        return oid

    def get(self, path, fresh=False):
        if path.startswith(self.endpoint("git/ref/heads/")):
            return {"object": {"sha": self.refs[path.split("heads/", 1)[1]]}}
        if path.startswith(self.endpoint("git/matching-refs/heads/")):
            branch = path.split("heads/", 1)[1]
            return [] if branch not in self.refs else [{"ref": "refs/heads/" + branch, "object": {"sha": self.refs[branch]}}]
        if path.startswith(self.endpoint("pulls/")) and path.rsplit("/", 1)[1].isdigit():
            return self.pulls[int(path.rsplit("/", 1)[1])]
        if path not in self.gets:
            raise AssertionError("unexpected synthetic GET " + path)
        return self.gets[path]

    def pages(self, path, fresh=False):
        if path.endswith("/check-runs?filter=all&per_page=100"):
            head = path.split("/commits/")[1].split("/")[0]
            return [{"check_runs": self.checks.get(head, [])}]
        if "pulls?state=all&head=" in path:
            branch = unquote(path.split("head=", 1)[1].split("&")[0]).split(":", 1)[1]
            return [[p for p in self.pulls.values() if p["head"]["ref"] == branch]]
        if "pulls?state=open&base=" in path:
            return [[p for p in self.pulls.values() if p["state"] == "open" and p["base"]["ref"] == "main"]]
        if path.endswith("/pulls?per_page=100") and "/commits/" in path:
            return [[self.pulls[17]]]
        if path not in self.page_values:
            raise AssertionError("unexpected synthetic pagination " + path)
        return self.page_values[path]

    def security_ghsas(self, *args):
        return self.ghsas

    def security_ghsa_evidence(self, *args):
        return self.ghsas, self.ghsas

    def post(self, path, payload):
        self.posts.append((path, copy.deepcopy(payload)))
        if path.endswith("/git/trees"):
            leaves = self.leaves(payload["base_tree"])
            leaves.update({e["path"]: e["sha"] for e in payload["tree"]})
            return {"sha": self.tree(leaves)}
        if path.endswith("/git/commits"):
            return {"sha": self.commit(payload["tree"], payload["parents"], payload["message"])}
        if path.endswith("/git/refs"):
            branch = payload["ref"].removeprefix("refs/heads/")
            assert branch not in self.refs
            self.refs[branch] = payload["sha"]
            result = {"ref": payload["ref"], "object": {"sha": payload["sha"]}}
            boundary = "ref"
        elif path.endswith("/check-runs"):
            classified = payload["name"] == sp.SOURCE_CHECK
            result = {**payload, "id": 601 + len(self.posts), "completed_at": "2026-08-16T11:59:59Z" if classified else "2026-08-16T12:01:00Z",
                      "app": {"id": sp.TRUSTED_SECURITY_AUTOMATION_APP_ID, "slug": "security-fixture"}}
            self.checks.setdefault(payload["head_sha"], []).append(result)
            boundary = "check"
        elif path.endswith("/pulls"):
            number = 44
            head = self.refs[payload["head"]]
            result = {"number": number, "state": "open", "draft": True, "auto_merge": None, "maintainer_can_modify": False,
                      "created_at": "2026-08-16T12:01:01Z", "changed_files": len(self.changed),
                      "base": {"ref": "main", "sha": self.refs["main"]},
                      "head": {"ref": payload["head"], "sha": head, "repo": {"full_name": self.repo, "id": self.identity}},
                      "user": {"login": "security-fixture[bot]"}}
            self.pulls[number] = result
            self.page_values[self.endpoint("pulls/44/files?per_page=100")] = copy.deepcopy(self.page_values[self.endpoint("pulls/17/files?per_page=100")])
            self.page_values[self.endpoint("pulls/44/commits?per_page=100")] = [[{"sha": head}]]
            boundary = "pr"
        else:
            raise AssertionError("unexpected synthetic write " + path)
        if self.lose_response == boundary:
            self.lose_response = None
            raise sp.PolicyError("synthetic accepted write with lost response")
        return result

    def classified_source(self):
        sp.classify_source_candidate(self, self.repo, 901, self.branch, None, None, 17, self.head, self.base)
        self.pulls[17].update(state="closed", merged_at="2026-08-16T12:00:00Z", merged_by={"login": "maintainer", "type": "User"})
        self.refs[self.branch] = self.merge
        return sp.build_source_evidence(self, self.repo, self.merge, self.branch, None, None, alert_wait_seconds=0)

    def ready(self, evidence):
        pr = self.pulls[44]
        pr["draft"] = False
        pr["merge_commit_sha"] = self.commit(evidence.projection_tree, [evidence.production_base, evidence.projection_head])
        pointer = {"number": 44, "base": {"ref": "main", "sha": evidence.production_base}, "head": {"sha": evidence.projection_head}}
        self.page_values[self.endpoint(f"commits/{evidence.projection_head}/check-runs?filter=latest&per_page=100")] = [{"check_runs": [
            {"name": name, "head_sha": evidence.projection_head, "status": "completed", "conclusion": "success",
             "app": {"id": app}, "check_suite": {"id": 801}, "pull_requests": [pointer]}
            for name, app in (("CI", sp.TRUSTED_CI_APP_ID), ("CodeQL", sp.TRUSTED_CODEQL_APP_ID))]}]
        self.page_values[self.endpoint(f"actions/runs?event=pull_request&head_sha={evidence.projection_head}&per_page=100")] = [{"workflow_runs": [
            {"path": ".github/workflows/ci.yml", "event": "pull_request", "head_sha": evidence.projection_head,
             "status": "completed", "conclusion": "success", "created_at": "2026-08-16T12:02:00Z", "check_suite_id": 801,
             "repository": {"full_name": self.repo}, "pull_requests": [pointer]}]}]


class DependencySetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.serial = 0

    def fixture(self, row=None, **kwargs):
        self.serial += 1
        return GitProvider(Path(self.temp.name) / str(self.serial), row or SET_ROWS[-1], **kwargs)

    def test_every_single_and_grouped_shape_source_projection_and_immutable_retry(self):
        for row in SET_ROWS:
            for pairs in ([p] for p in row["pairs"]) if len(row["pairs"]) == 1 else ([row["pairs"][0]], [row["pairs"][1]], row["pairs"]):
                for manifests in (False, True):
                    with self.subTest(repository=row["repository"], pairs=pairs, manifests=manifests):
                        api = self.fixture(row, pairs=pairs, manifests=manifests)
                        structural = sp.verify_ci_admission(api, api.repo, 17, "dev")
                        self.assertEqual(structural.dependency_pairs, tuple(pairs))
                        source = api.classified_source()
                        original_check = copy.deepcopy(api.checks[api.head])
                        number, evidence = sp.create_projection(api, source, "main", None, None)
                        self.assertEqual(evidence.profile, sp.SET_PROFILE)
                        self.assertEqual(evidence.attestation()["schema"], sp.SET_PROJECTION_SCHEMA)
                        self.assertEqual(sp.parse_projection_attestation(evidence.attestation()), evidence)
                        self.assertEqual(sp.verify_projection(api, api.repo, number, "dev", "main", False)[0], evidence)
                        self.assertEqual(sp.verify_ci_admission(api, api.repo, number, "main"), evidence)
                        expected = dict(api.original_main_leaves)
                        expected.update({p: source.post[p].sha for p in source.changed_paths})
                        self.assertEqual(api.leaves(evidence.projection_tree), expected)
                        count = sum(p.endswith(("/git/refs", "/check-runs", "/pulls")) for p, _ in api.posts)
                        self.assertEqual(sp.create_projection(api, source, "main", None, None), (number, evidence))
                        self.assertEqual(sum(p.endswith(("/git/refs", "/check-runs", "/pulls")) for p, _ in api.posts), count)
                        self.assertEqual(api.checks[api.head], original_check)

    def test_direct_main_nested_source_observation(self):
        api = self.fixture(SET_ROWS[0], branch="main")
        source = api.classified_source()
        event = {"repository": {"full_name": api.repo}, "ref": "refs/heads/main", "before": api.base,
                 "after": api.merge, "deleted": False, "forced": False}
        self.assertEqual(sp.verify_source_post_merge(api, api.repo, event, "push", "refs/heads/main", api.merge), source)
        self.assertEqual(len(api.posts), 1)

    def test_set_post_merge_reconstructs_production_tree_and_cli_assertion(self):
        api = self.fixture()
        _, evidence = sp.create_projection(api, api.classified_source(), "main", None, None)
        api.ready(evidence)
        pr = api.pulls[44]
        pr.update(state="closed", merged_at="2026-08-16T12:03:00Z", merged_by={"login": "maintainer", "type": "User"})
        api.refs["main"] = pr["merge_commit_sha"]
        self.assertEqual(sp.verify_post_merge(api, api.repo, "main", pr["merge_commit_sha"], 44), evidence)
        for argument in ([], ["--manifest-path", "package.json"], ["--lock-path", ""]):
            output = io.StringIO()
            # This fixture owns stdout, not the enclosing Actions job's output file.
            with patch.dict(os.environ, {"GITHUB_OUTPUT": ""}), patch.object(sp, "GhApi", return_value=api), redirect_stdout(output), redirect_stderr(io.StringIO()):
                status=sp.cli(["verify-post-merge", "--repository", api.repo, "--pull-request", "44", "--merge-sha", pr["merge_commit_sha"], *argument])
            self.assertEqual(status, 1 if argument else 0)
            self.assertEqual(output.getvalue(), "" if argument else "verified=true\n")
        tree = api.gets[api.endpoint("git/trees/" + evidence.projection_tree)]
        next(e for e in tree["tree"] if e["path"] == "README.md")["sha"] = api.blob("tampered sibling\n")
        with self.assertRaisesRegex(sp.PolicyError, "mismatched"):
            sp.verify_post_merge(api, api.repo, "main", pr["merge_commit_sha"], 44)

    def test_every_pair_preimage_including_unchanged_manifest_is_required(self):
        for key in ("manifest_path", "lock_path"):
            for index in (0, 1):
                api = self.fixture()
                source = api.classified_source()
                leaves = dict(api.original_main_leaves)
                leaves[api.pairs[index][key]] = api.blob("divergent production\n")
                api.refs["main"] = api.commit(api.tree(leaves), [api.main])
                before = len(api.posts)
                with self.assertRaisesRegex(sp.PolicyError, "preimage"):
                    sp.create_projection(api, source, "main", None, None)
                self.assertEqual(len(api.posts), before)

    def test_single_lock_collision_refuses_whole_set_before_writes(self):
        for pair in SET_ROWS[-1]["pairs"]:
            api = self.fixture()
            source = api.classified_source()
            api.pulls[45] = {"number": 45, "state": "open", "changed_files": 1, "base": {"ref": "main"},
                             "head": {"ref": "other", "repo": {"full_name": api.repo}}}
            api.page_values[api.endpoint("pulls/45/files?per_page=100")] = [[{"filename": pair["lock_path"], "status": "modified"}]]
            before = len(api.posts)
            with self.assertRaisesRegex(sp.PolicyError, "already touch"):
                sp.create_projection(api, source, "main", None, None)
            self.assertEqual(len(api.posts), before)

    def test_lost_response_whole_set_adoption(self):
        for boundary in ("ref", "check", "pr"):
            api = self.fixture()
            source = api.classified_source()
            api.lose_response = boundary
            result = sp.create_projection(api, source, "main", None, None)
            self.assertEqual(sp.create_projection(api, source, "main", None, None), result)
            for suffix in ("/git/refs", "/pulls"):
                self.assertEqual(sum(p.endswith(suffix) for p, _ in api.posts), 1)
            self.assertEqual(len(api.checks[result[1].projection_head]), 1)

    def test_source_adverse_complete_delta_identity_and_tree(self):
        for defect in ("wrong-id", "extra-file", "missing-lock", "duplicate-file", "truncated-files", "sibling", "symlink", "ancestor", "signature", "neutral"):
            with self.subTest(defect=defect):
                api = self.fixture()
                files = api.page_values[api.endpoint("pulls/17/files?per_page=100")][0]
                if defect == "wrong-id": api.gets[api.endpoint("")]["id"] += 1
                elif defect == "extra-file": files.append({"filename": "README.md", "status": "modified"})
                elif defect == "missing-lock": files.pop()
                elif defect == "duplicate-file": files.append(copy.deepcopy(files[0]))
                elif defect == "truncated-files": api.pulls[17]["changed_files"] += 1
                elif defect == "signature": api.page_values[api.endpoint("pulls/17/commits?per_page=100")][0][0]["commit"]["verification"]["verified"] = False
                elif defect == "neutral":
                    api.page_values[api.endpoint(f"commits/{api.head}/check-runs?filter=latest&per_page=100")][0]["check_runs"][1]["conclusion"] = "neutral"
                else:
                    tree = api.gets[api.endpoint("git/commits/" + api.head)]["tree"]["sha"]
                    entries = api.gets[api.endpoint("git/trees/" + tree)]["tree"]
                    if defect == "sibling": next(e for e in entries if e["path"] == "README.md")["sha"] = api.blob("unreported drift\n")
                    elif defect == "ancestor": next(e for e in entries if e["type"] == "tree")["mode"] = "100644"
                    else:
                        for value in api.gets.values():
                            if isinstance(value.get("tree"), list):
                                for entry in value["tree"]:
                                    if entry["path"] == "package-lock.json": entry["mode"] = "120000"
                with self.assertRaises(sp.PolicyError):
                    sp.wait_for_source_candidate(api, api.repo, 901, "dev", None, None, 0)
                self.assertFalse(api.posts)

    def test_root_assertions_never_select_set_and_empty_cli_refuses(self):
        api = self.fixture()
        for manifest, lock in (("package.json", None), (None, "package-lock.json"), ("package.json", "package-lock.json"), ("", None), ("assets/admin/package.json", None)):
            with self.assertRaises(sp.PolicyError):
                sp.build_source_candidate(api, api.repo, 901, "dev", manifest, lock)
        for value in ("", "$(touch injected)", "x\npackage.json", "../package.json"):
            output = io.StringIO()
            with patch.object(sp, "GhApi", return_value=api), redirect_stderr(output):
                self.assertEqual(sp.cli(["preflight-source", "--repository", api.repo, "--workflow-run-id", "901", "--manifest-path", value, "--wait-seconds", "0"]), 1)
        self.assertFalse(api.posts)

    def test_version_pair_and_unknown_field_tampering_refuses(self):
        api = self.fixture()
        _, evidence = sp.create_projection(api, api.classified_source(), "main", None, None)
        for field, value in (("schema", sp.PROJECTION_SCHEMA), ("profile", sp.PROFILE), ("repository_id", api.identity + 1),
                             ("dependency_pairs", list(reversed(api.pairs))), ("extra", True)):
            raw = evidence.attestation()
            raw[field] = value
            with self.assertRaises(sp.PolicyError): sp.parse_projection_attestation(raw)

    def test_closed_source_declaration_and_universal_legacy_root(self):
        self.assertEqual(len(DECLARATION['repositories']),5)
        self.assertEqual(sum(len(r['pairs']) for r in DECLARATION['repositories']),7)
        for defect in ('extra','bool-id','duplicate-repo','duplicate-pair','unsafe-path','mixed-family','missing'):
            data=copy.deepcopy(DECLARATION)
            row=data['repositories'][-1]
            if defect=='extra':data['override']=True
            elif defect=='bool-id':row['repository_id']=True
            elif defect=='duplicate-repo':data['repositories'].append(copy.deepcopy(row))
            elif defect=='duplicate-pair':row['pairs'].append(copy.deepcopy(row['pairs'][0]))
            elif defect=='unsafe-path':row['pairs'][0]['manifest_path']='assets/../package.json'
            elif defect=='mixed-family':row['pairs'][0]['ecosystem']='cargo'
            with self.subTest(defect=defect),patch.object(sp.Path,'read_text',side_effect=OSError('missing') if defect=='missing' else None,return_value=json.dumps(data)):
                with self.assertRaises(sp.PolicyError):sp.declared_pairs('ForgingAlpha/turnkeyleads-app',1017445965)
                # Missing/malformed new declarations cannot revoke universal v2 capability.
                profile,identity,pairs=sp.select_dependencies(object(),'OtherOwner/legacy',[{'filename':'package-lock.json','status':'modified'}])
                self.assertEqual((profile,identity,pairs),(sp.PROFILE,None,sp.ROOT_PAIRS))
        with patch.object(sp.Path,'read_text',return_value='{"schema_version":1,"schema_version":1,"repositories":[]}'):
            with self.assertRaisesRegex(sp.PolicyError,'duplicate'):sp.declared_pairs('ForgingAlpha/turnkeyleads-app',1017445965)

    def test_classification_retries_preserve_body_time_and_cross_version_uniqueness(self):
        api = self.fixture()
        candidate = sp.build_source_candidate(api, api.repo, 901, "dev", None, None)
        sp.ensure_source_classification(api, candidate)
        original = copy.deepcopy(api.checks[api.head])
        sp.ensure_source_classification(api, candidate)
        self.assertEqual(api.checks[api.head], original)
        self.assertEqual(len(api.posts), 1)
        self.assertTrue(original[0]["external_id"].startswith("source-v3:dev:17:"))
        api.checks[api.head][0]["external_id"] = "alphaapps-security-source-v2:dev:17:" + api.head
        with self.assertRaises(sp.PolicyError): sp.ensure_source_classification(api, candidate)
        self.assertEqual(len(api.posts), 1)
        api.checks[api.head].append(original[0])
        with self.assertRaisesRegex(sp.PolicyError, "multiple"): sp.ensure_source_classification(api, candidate)

    def test_projection_tombstone_conflicting_ref_and_check_never_rewrite(self):
        for defect in ("closed", "ref", "check", "duplicate"):
            api = self.fixture()
            source = api.classified_source()
            _, evidence = sp.create_projection(api, source, "main", None, None)
            if defect == "closed": api.pulls[44]["state"] = "closed"
            elif defect == "ref": api.refs[api.pulls[44]["head"]["ref"]] = api.base
            elif defect == "check": api.checks[evidence.projection_head][0]["output"]["summary"] = "{}"
            else: api.checks[evidence.projection_head].append(copy.deepcopy(api.checks[evidence.projection_head][0]))
            before = sum(p.endswith(("/git/refs", "/check-runs", "/pulls")) for p, _ in api.posts)
            with self.assertRaises(sp.PolicyError): sp.create_projection(api, source, "main", None, None)
            self.assertEqual(sum(p.endswith(("/git/refs", "/check-runs", "/pulls")) for p, _ in api.posts), before)

    def test_actual_projection_verification_wrappers_quoted_omission_and_root_assertions(self):
        import yaml
        root = Path(sp.__file__).parents[3]
        rows = [DECLARATION["repositories"][1], *SET_ROWS]
        for row in rows:
            is_root = row["pairs"][0]["manifest_path"] == "package.json"
            shapes = [("", "")] + ([("package.json", ""), ("", "package-lock.json"), ("package.json", "package-lock.json")] if is_root else [])
            for action_name, step_id in (("security-patch-projection", "project"), ("security-patch-verification", "verify")):
                action = yaml.safe_load((root / "actions" / action_name / "action.yml").read_text())
                step = next(s for s in action["runs"]["steps"] if s.get("id") == step_id)
                self.assertNotIn("${{", step["run"])
                self.assertNotIn("default", action["inputs"]["manifest-path"])
                for manifest, lock in shapes + [("$(touch injected)", ""), ("x\npackage.json", "")]:
                    with self.subTest(repository=row["repository"], action=action_name, manifest=manifest, lock=lock):
                        case = Path(self.temp.name) / ("wrapper" + str(self.serial))
                        self.serial += 1
                        case.mkdir()
                        expected = self.fixture(row)
                        runner = case / "driver.py"
                        runner.write_text("import sys,os,json\n"
                            "sys.path.insert(0, " + repr(str(Path(__file__).parent)) + ")\n"
                            "from test_dependency_sets import GitProvider,sp\n"
                            "api=GitProvider(os.environ['FIXTURE_GIT'],json.loads(os.environ['FIXTURE_ROW']))\n"
                            "source=api.classified_source()\n"
                            "if sys.argv[2]=='verify-projection':\n"
                            " _,e=sp.create_projection(api,source,'main',None,None);api.ready(e)\n"
                            "sp.GhApi=lambda:api\n"
                            "raise SystemExit(sp.cli(sys.argv[2:]))\n")
                        shim = case / "python3"
                        shim.write_text("#!/bin/sh\nexec " + sys.executable + " " + str(runner) + ' "$@"\n')
                        shim.chmod(0o700)
                        env = {"PATH": str(case) + ":/usr/bin:/bin", "GITHUB_ACTION_PATH": str(root / "actions" / action_name),
                            "GITHUB_REPOSITORY": row["repository"], "FIXTURE_GIT": str(case / "git"), "FIXTURE_ROW": json.dumps(row),
                            "SECURITY_SOURCE_MERGE_SHA": expected.merge, "SECURITY_SOURCE_BRANCH": "dev", "SECURITY_TARGET_BRANCH": "main",
                            "SECURITY_MANIFEST_PATH": manifest, "SECURITY_LOCK_PATH": lock, "SECURITY_PULL_REQUEST_NUMBER": "44",
                            "SECURITY_CI_APP_ID": "15368", "SECURITY_CODEQL_APP_ID": "57789", "SECURITY_CODEQL_CHECK_NAME": "CodeQL"}
                        result = subprocess.run(["/usr/bin/bash", "-e", "-c", step["run"]], cwd=case, env=env, capture_output=True, text=True, timeout=30)
                        valid = (manifest, lock) in shapes
                        self.assertEqual(result.returncode, 0 if valid else 1, result.stderr)
                        self.assertFalse((case / "injected").exists())
                        self.assertIn("eligible=true" if step_id == "project" else "verified=true", result.stdout) if valid else self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
