"""REQ-024–026: preserve valid bootstrap and refuse trust-boundary violations."""
import copy
import hashlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from route_fixture_support import git_context, git_data

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tested_org_baseline", ROOT / "actions/ci-org-baseline/scripts/baseline.py")
baseline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = baseline
spec.loader.exec_module(baseline)
# Synthetic bootstrap fixture; production accepts schema3 only.
ENTRY = {
    "repository": "ForgingAlpha/layas-learning-lab-site", "repository_id": 1420939261,
    "branches": ["dev", "main"], "profile": "documentation-bootstrap", "team_id": 20299307,
    "minimum_approvals": 1, "producer": "bootstrap", "qualification_subject": {"kind": "none"},
    "review_policy": {"kind": "qualified-team", "team_id": 20299307, "minimum_approvals": 1},
    "foundation": "not-applicable", "components": [],
}


def row(entry):
    part = {"mode": "central", "selected_targets": entry["branches"], **{k: entry[k] for k in
        ("profile", "producer", "qualification_subject", "review_policy", "foundation", "components")}}
    entry["participation"] = part
    return {k: entry[k] for k in ("repository", "repository_id", "proposal", "participation")}


def bind_fixture(fixture, entry, name="PROJECT.md"):
    data = fixture.git('show', fixture.base + ':' + name).encode()
    lines = data.decode().splitlines(keepends=True)
    start, end = ("<!-- route -->", "<!-- end-route -->") if name == 'docs/route.md' else ('# Project', 'Documentation.')
    i, j = [n for n, x in enumerate(lines) if x.rstrip('\n') == start][0], [n for n, x in enumerate(lines) if x.rstrip('\n') == end][0]
    entry['proposal'] = {'task_target': 'dev', 'promotions': [{'source': 'dev', 'target': 'main', 'same_repository': True}],
      'evidence': {'adoption_branch': 'dev', 'adopted_commit': fixture.base,
        'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}],
        'regions': [{'path': name, 'start': start, 'end': end, 'sha256': hashlib.sha256(''.join(lines[i+1:j]).encode()).hexdigest()}],
        'reconciliation_sha256': 'c'*64, 'governing_sha256': 'f'*64, 'rule': 'application', 'persistent_sources': ['dev','main']}}
    row(entry)
    entry['proposal']['evidence'].update(context=git_context(fixture.root,fixture.base),transition={'kind':'none'})
    return entry


def admission_record(fixture, entry, source='d'*40):
    projected = row(entry)
    subject = baseline.route.subject(fixture.event(), projected)
    kind, proof = baseline.route.ordinary(projected, subject, False)
    return {'schema_version': 2, 'kind': kind, **subject,
            'head_tree_sha': fixture.git('rev-parse', fixture.head+'^{tree}').strip(),
            'policy_evidence_sha256': baseline.route.digest(entry['proposal']['evidence']),
            'checking_source_sha': source, 'checking_fingerprints': baseline.route.fingerprint(),
            'enrollment_sha256': baseline.route.digest(projected), 'source_correspondence':{'authority':0,'subjects':baseline.route.local_correspondence(fixture.root,projected,[fixture.base,fixture.head])}, 'proof': proof}


def successful_needs(plan, **receipts):
    """GitHub fan-in with admission and each executed job's defining source."""
    return {
        "baseline": {"result": "success", "outputs": {"plan": json.dumps(plan), "source_sha": plan["source_sha"]}},
        **{phase: {"result": "success", "outputs": {"receipt": raw, "source_sha": plan["source_sha"]}}
           if (raw := receipts.get(phase)) is not None else {"result": "skipped", "outputs": {}}
           for phase in ("static", "tests")},
    }


class CatalogTests(unittest.TestCase):
    def test_actual_enrollment_validates_independently(self):
        entries = baseline.catalog(baseline.decode(
            (ROOT / "actions/ci-org-baseline/enrollment.json").read_bytes()))
        self.assertTrue(entries)
        for entry in entries:
            for branch in entry["branches"]:
                if entry['participation']['mode'] == 'central':
                    self.assertEqual(baseline.select(entries, entry["repository"], entry["repository_id"], branch), entry)
                else:
                    with self.assertRaisesRegex(ValueError, 'metadata-only'):
                        baseline.select(entries, entry["repository"], entry["repository_id"], branch)


def rules():
    return [{"type": "pull_request", "parameters": {
        "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
        "required_reviewers": [{"reviewer": {"type": "Team", "id": ENTRY["team_id"]},
                                "minimum_approvals": 1, "file_patterns": ["*"]}]}}]


class Fixture:
    def __init__(self, root, branch="dev"):
        self.root = root
        self.branch = branch
        root.mkdir()
        self.git("init", "-q", "-b", branch)
        self.git("remote", "add", "origin", "https://github.com/" + ENTRY["repository"])
        self.git("commit", "-q", "--allow-empty", "-m", "empty base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", f"refs/remotes/origin/{branch}", self.base)
        for name in baseline.REQUIRED - baseline.ALIASES:
            text = "# Project\n\nDocumentation.\n" if name == "PROJECT.md" else "---\nstatus: approved\n---\n\n# Document\n\nDocumentation.\n"
            self.write(name, text)
        for name in baseline.ALIASES:
            (root / name).symlink_to("PROJECT.md")
        for name in baseline.DATA_PATHS:
            self.write(name, '{"schema_version": 1}\n')
        self.commit()
        self.base = self.head
        self.git("update-ref", f"refs/remotes/origin/{branch}", self.base)
        self.write('docs/change.md', '# Change\n')
        self.commit()
        self.entry = bind_fixture(self, copy.deepcopy(ENTRY))

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
        return subprocess.check_output(["git", "-c", "user.name=CI Fixture", "-c", "user.email=fixture@example.invalid", *args], cwd=self.root, env=env, text=True, stderr=subprocess.PIPE)

    def write(self, name, data):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.encode() if isinstance(data, str) else data)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-q", "--allow-empty", "-m", "documentation candidate")
        self.head = self.git("rev-parse", "HEAD").strip()

    def event(self):
        repo = {"id": ENTRY["repository_id"], "full_name": ENTRY["repository"]}
        return {"repository": repo, "number": 1, "pull_request": {
            "base": {"repo": repo, "ref": self.branch, "sha": self.base},
            "head": {"repo": repo, "ref": "dev" if self.branch == "main" else "feature/docs", "sha": self.head}}}


class FakeApi:
    def __init__(self, fixture):
        self.fixture = fixture
        self.base = fixture.base
        self.live = {**fixture.event()["pull_request"], "number": 1, "state": "open"}
        self.evidence = rules()
        self.reads = []

    def get(self, path):
        self.reads.append(path)
        if path.endswith("/pulls/1"):
            return copy.deepcopy(self.live)
        if path.endswith(f"/branches/{self.fixture.branch}"):
            return {"commit": {"sha": self.base}}
        raise AssertionError("unexpected or non-read evidence operation " + path)

    def rules(self, repository, branch):
        assert repository == ENTRY["repository"] and branch == self.fixture.branch
        return copy.deepcopy(self.evidence)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(Path(self.temp.name) / "consumer")
        patcher = patch.object(baseline.route, 'admission', side_effect=lambda api, event, entry, source: admission_record(self.fixture, self.fixture.entry, source))
        patcher.start(); self.addCleanup(patcher.stop)

    def test_real_git_docs_and_verified_projection_aliases(self):
        texts = baseline.admit_tree(self.fixture.root, self.fixture.head)
        self.assertIn("PROJECT.md", texts)
        self.assertNotIn("AGENTS.md", texts)  # Canonical text is checked once.
        self.assertNotIn("CLAUDE.md", texts)
        self.assertFalse(baseline.policy.incomplete_baseline(baseline.policy.baseline_statuses(self.fixture.root)))

    def test_declared_json_is_data_not_an_additional_required_input(self):
        for name in baseline.DATA_PATHS:
            (self.fixture.root / name).unlink()
        self.fixture.commit()
        baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_application_executable_and_config_inputs_fail_before_lint(self):
        cases = {"package.json": "{}", "Cargo.toml": "[package]\n", "script.py": "raise Exception()\n",
                 ".markdownlint.cjs": "throw Error('must not execute')", "nested/.markdownlint-cli2.jsonc": "{}",
                 "docs/extra.json": "{}", "docs/bad.md": b"\xff", "docs/control\nname.md": "# Unsafe\n",
                 "docs/delete\x7f.md": "# Unsafe\n"}
        for number, (name, data) in enumerate(cases.items()):
            with self.subTest(path=name):
                f = Fixture(Path(self.temp.name) / str(number))
                f.write(name, data)
                f.commit()
                with self.assertRaises((ValueError, UnicodeError)):
                    baseline.admit_tree(f.root, f.head)

    def test_changed_untracked_and_ignored_inputs_do_not_pass(self):
        self.fixture.write("PROJECT.md", "# Altered after checkout\n")
        with self.assertRaisesRegex(ValueError, "modified"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)
        self.fixture.git("checkout", "--", "PROJECT.md")
        self.fixture.write(".gitignore", "hidden.md\n")
        self.fixture.commit()
        self.fixture.write("hidden.md", "# Not tracked\n")
        with self.assertRaisesRegex(ValueError, "untracked"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_link_escape_and_executable_markdown_refused(self):
        alias = self.fixture.root / "AGENTS.md"
        alias.unlink()
        alias.symlink_to("../PROJECT.md")
        self.fixture.commit()
        with self.assertRaisesRegex(ValueError, "projection"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)
        alias.unlink()
        alias.symlink_to("PROJECT.md")
        (self.fixture.root / "PROJECT.md").chmod(0o755)
        self.fixture.commit()
        with self.assertRaisesRegex(ValueError, "non-executable"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_required_document_deletion_and_malformed_data_refused(self):
        self.fixture.write(next(iter(baseline.DATA_PATHS)), '{"a":1,"a":2}')
        self.fixture.commit()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)
        self.fixture.write(next(iter(baseline.DATA_PATHS)), "{}")
        (self.fixture.root / "docs/intent.md").unlink()
        self.fixture.commit()
        with self.assertRaisesRegex(ValueError, "missing required"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_nonempty_docs_do_not_hide_limits(self):
        self.fixture.write("docs/large.md", "x" * (512 * 1024 + 1))
        self.fixture.commit()
        with self.assertRaisesRegex(ValueError, "512 KiB"):
            baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_same_input_requires_live_head_base_and_repo_identity(self):
        api = FakeApi(self.fixture)
        baseline.prove_pr(api, self.fixture.event(), ENTRY)
        api.live["head"]["sha"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "moved"):
            baseline.prove_pr(api, self.fixture.event(), ENTRY)
        api = FakeApi(self.fixture)
        api.live["head"]["repo"] = {"id": 3, "full_name": "outside/fork"}
        with self.assertRaisesRegex(ValueError, "fork"):
            baseline.prove_pr(api, self.fixture.event(), ENTRY)

    def test_complete_path_real_policy_and_locked_lint_then_repair(self):
        env = {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"]),
               "BASELINE_SOURCE_SHA": "a" * 40}
        with patch.dict(os.environ, env):
            result = baseline.run(self.fixture.root, self.fixture.event(), [self.fixture.entry], FakeApi(self.fixture))
            self.assertEqual(result["head"], self.fixture.head)
            self.assertEqual(result["source"], "ForgingAlpha/.github")
            self.fixture.write("PROJECT.md", "<!-- markdownlint-disable MD001 -->\n# Title\n\n### Skipped heading\n")
            self.fixture.commit()
            with self.assertRaisesRegex(ValueError, "Markdown"):
                baseline.run(self.fixture.root, self.fixture.event(), [self.fixture.entry], FakeApi(self.fixture))
            self.fixture.write("PROJECT.md", "# Title\n\n## Repaired heading\n")
            self.fixture.commit()
            baseline.run(self.fixture.root, self.fixture.event(), [self.fixture.entry], FakeApi(self.fixture))

    def test_provisional_metadata_never_uses_definition_only_exception(self):
        self.fixture.write("docs/intent.md", "---\nstatus: provisional\n---\n\n# Intent\n")
        self.fixture.commit()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
            with self.assertRaisesRegex(ValueError, "approved structural"):
                baseline.run(self.fixture.root, self.fixture.event(), [self.fixture.entry], FakeApi(self.fixture))

    def test_main_runs_complete_profile_with_fresh_main_evidence(self):
        fixture = Fixture(Path(self.temp.name) / "main", branch="main")
        api = FakeApi(fixture)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"],
                                     "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"]),
                                     "BASELINE_SOURCE_SHA": "b" * 40}):
            result = baseline.run(fixture.root, fixture.event(), [self.fixture.entry], api)
        self.assertEqual((result["base"], result["head"]), (fixture.base, fixture.head))
        self.assertEqual(result["source_sha"], "b" * 40)
        self.assertEqual(api.reads, [f'/repos/{ENTRY["repository"]}/pulls/1',
                                    f'/repos/{ENTRY["repository"]}/branches/main'] * 2)

    def test_main_refuses_stale_or_weaker_evidence_and_application_input(self):
        cases = [("head", "moved"), ("base", "base branch moved"),
                 ("team", "trusted team review"), ("application", r"src/app\.astro")]
        for case, diagnostic in cases:
            with self.subTest(case=case):
                fixture = Fixture(Path(self.temp.name) / ("main-" + case), branch="main")
                if case == "application":
                    fixture.write("src/app.astro", "<p>Application input</p>\n")
                    fixture.commit()
                api = FakeApi(fixture)
                if case == "head":
                    api.live["head"]["sha"] = "a" * 40
                elif case == "base":
                    api.base = "a" * 40
                elif case == "team":
                    api.evidence[0]["parameters"]["required_approving_review_count"] = 0
                with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"],
                                             "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        baseline.run(fixture.root, fixture.event(), [self.fixture.entry], api)

    def test_complete_path_refuses_executable_formatter_without_side_effect(self):
        marker = Path(self.temp.name) / "must-not-exist"
        self.fixture.write(".markdownlint-cli2.cjs", "require('fs').writeFileSync(" + json.dumps(str(marker)) + ", 'executed'); module.exports={};\n")
        self.fixture.commit()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
            with self.assertRaisesRegex(ValueError, "undeclared"):
                baseline.run(self.fixture.root, self.fixture.event(), [self.fixture.entry], FakeApi(self.fixture))
        self.assertFalse(marker.exists())

    def test_admitted_unicode_boundary_reaches_real_locked_lint(self):
        for number in range(12):
            self.fixture.write(f"docs/unicode-{number}.md", "# Unicode document\n\n" + "\U0001f331" * 125000 + "\n")
        self.fixture.commit()
        strings = baseline.admit_tree(self.fixture.root, self.fixture.head)
        self.assertLess(sum(len(text.encode("utf-8")) for text in strings.values()), 8 * 1024 * 1024)
        self.assertGreater(len(json.dumps(strings).encode()), 16 * 1024 * 1024)  # Discriminates the original transport defect.
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
            result = baseline.run(self.fixture.root, self.fixture.event(), [self.fixture.entry], FakeApi(self.fixture))
        self.assertEqual(result["head"], self.fixture.head)

    def test_gitlink_is_not_a_document(self):
        (self.fixture.root / "docs/submodule.md").mkdir()
        self.fixture.git("update-index", "--add", "--cacheinfo", "160000," + self.fixture.head + ",docs/submodule.md")
        self.fixture.git("commit", "-q", "-m", "unsupported gitlink")
        self.fixture.head = self.fixture.git("rev-parse", "HEAD").strip()
        with self.assertRaises(ValueError):
            baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_cli_requires_current_staged_contract_without_logging_authenticated_result(self):
        event_path = Path(self.temp.name) / 'event.json'
        event_path.write_text(json.dumps(self.fixture.event()))
        original_git = baseline.git
        def source_git(root, *args, **kwargs):
            if root == baseline.SOURCE and args == ('rev-parse','HEAD'): return b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n'
            if root == baseline.SOURCE and args == ('status','--porcelain','--untracked-files=all'): return b''
            return original_git(root,*args,**kwargs)
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME':'pull_request','BASELINE_SOURCE_SHA':'a'*40,'GITHUB_EVENT_PATH':str(event_path)}), \
             patch.object(sys,'argv',['baseline.py','--consumer-root',str(self.fixture.root)]), \
             patch.object(baseline,'git',side_effect=source_git), patch.object(baseline,'Api') as api, \
             patch.object(sys,'stdout',io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError,'explicit schema-3 stage'): baseline.main()
            api.assert_not_called(); self.assertEqual(output.getvalue(),'')

    def test_staged_bootstrap_freezes_before_auth_and_discards_authenticated_returns(self):
        from types import SimpleNamespace
        output = Path(self.temp.name) / 'stage-output'
        event = self.fixture.event()
        source = 'd' * 40
        canary = 'AUTHENTICATED_RETURN_MUST_NOT_BE_PUBLIC'
        frozen = baseline.public_receipt(self.fixture.root, event, [self.fixture.entry], source)
        actual_plan = baseline.make_plan
        order = []
        def plan(*args):
            order.append('plan')
            return actual_plan(*args)
        def authenticate(*args):
            self.assertEqual(order[0], 'plan')
            order.append('auth')
            return FakeApi(self.fixture)
        env = {'GITHUB_REPOSITORY': ENTRY['repository'], 'GITHUB_REPOSITORY_ID': str(ENTRY['repository_id']),
               'GITHUB_TOKEN': 'fixture-credential', 'GITHUB_OUTPUT': str(output),
               'BASELINE_NEEDS': json.dumps(successful_needs(baseline.make_plan(self.fixture.root, event, self.fixture.entry, source, admission_record(self.fixture, self.fixture.entry, source))))}
        with patch.dict(os.environ, env), patch.object(baseline, 'make_plan', side_effect=plan), \
                patch.object(baseline, 'Api', side_effect=authenticate), patch.object(baseline, 'run', return_value={'credential': canary}):
            baseline.staged_main(SimpleNamespace(stage='admit'), self.fixture.root, event, [self.fixture.entry], source)
            self.assertNotIn(canary, output.read_text())
            with patch.object(sys, 'stdout', io.StringIO()) as logged:
                baseline.staged_main(SimpleNamespace(stage='finalize'), self.fixture.root, event, [self.fixture.entry], source)
            final = json.loads(logged.getvalue())
            for key in ('head','base','consumer','source_sha'): self.assertEqual(final[key],frozen[key])
            self.assertEqual(final['schema_version'],4)
            self.assertEqual(final['admission_kind'],'ordinary-task')
            self.assertEqual(final['required_results'],{'baseline':'success'})
            self.assertNotIn(canary, logged.getvalue())
            with patch.object(sys, 'stdout', io.StringIO()) as logged, self.assertRaises(ValueError):
                baseline.staged_main(SimpleNamespace(stage='finalize'), self.fixture.root, event, [self.fixture.entry], 'e' * 40)
            self.assertEqual(logged.getvalue(), '')
            admitted = baseline.make_plan(self.fixture.root, event, self.fixture.entry, source, admission_record(self.fixture, self.fixture.entry, source))
            for change in ({'source_sha': 'e' * 40}, {'head': 'e' * 40}, {'base': 'e' * 40}, {'components': [{'kind': 'astro'}]}):
                bad = successful_needs({**admitted, **change})
                os.environ['BASELINE_NEEDS'] = json.dumps(bad)
                with self.subTest(change=change), patch.object(sys, 'stdout', io.StringIO()) as logged, self.assertRaises(ValueError):
                    baseline.staged_main(SimpleNamespace(stage='finalize'), self.fixture.root, event, [self.fixture.entry], source)
                self.assertEqual(logged.getvalue(), '')
            output.unlink()
            def mutate(*args): event['pull_request']['base']['sha'] = 'e' * 40
            with patch.object(baseline, 'run', side_effect=mutate), self.assertRaises(ValueError):
                baseline.staged_main(SimpleNamespace(stage='admit'), self.fixture.root, event, [self.fixture.entry], source)
            self.assertFalse(output.exists())


class EvidenceTests(unittest.TestCase):
    def test_unknown_identity_profile_and_policy_fields_are_refused(self):
        for name, identifier, branch in [("ForgingAlpha/renamed", ENTRY["repository_id"], "dev"),
                                         (ENTRY["repository"], 2, "dev"), (ENTRY["repository"], ENTRY["repository_id"], "staging")]:
            with self.assertRaises(ValueError):
                baseline.select([ENTRY], name, identifier, branch)
        for change in ({"profile": "rust"}, {"extra": True}, {"repository": "ForgingAlpha/.github"}, {"team_id": True}):
            with self.assertRaises(ValueError):
                baseline.catalog({"schema_version": 1, "repositories": [{**ENTRY, **change}]})

    def test_branch_enrollment_permits_main_only_when_centrally_declared(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory) / 'consumer')
            e = row(f.entry)
            for branch in ('dev', 'main'):
                entries = baseline.catalog({'schema_version': 3, 'repositories': [e]})
                baseline.select(entries, e['repository'], e['repository_id'], branch)
            for branches in (None, [], 'main', ['dev','dev'], ['dev','*'], ['dev','main','staging'], ['dev',True]):
                bad = copy.deepcopy(e); bad['participation']['selected_targets'] = branches
                with self.subTest(branches=branches), self.assertRaises((ValueError, TypeError)):
                    baseline.catalog({'schema_version': 3, 'repositories': [bad]})
            for version in (1,2):
                with self.assertRaisesRegex(ValueError, 'unsupported enrollment schema'):
                    baseline.catalog({'schema_version': version, 'repositories': [e]})

    def test_weakened_team_evidence_fails_additive_rules_preserve_stronger(self):
        baseline.team_configuration(rules(), ENTRY)
        changes = [("required_approving_review_count", 0), ("required_approving_review_count", True),
                   ("dismiss_stale_reviews_on_push", False), ("required_reviewers", [])]
        for key, value in changes:
            weak = rules()
            weak[0]["parameters"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                baseline.team_configuration(weak, ENTRY)
        for key, value in [("minimum_approvals", 0), ("file_patterns", ["docs/*"]), ("reviewer", {"type": "User", "id": ENTRY["team_id"]})]:
            weak = rules()
            weak[0]["parameters"]["required_reviewers"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                baseline.team_configuration(weak, ENTRY)
        weak = rules()
        weak[0]["parameters"].update(required_approving_review_count=0, dismiss_stale_reviews_on_push=False, required_reviewers=[])
        baseline.team_configuration(weak + rules(), ENTRY)
        for absent in ([], None, [{}]):
            with self.assertRaises(ValueError):
                baseline.team_configuration(absent, ENTRY)

    def test_complete_bounded_pagination_refuses_cross_host(self):
        api = baseline.Api("not-a-real-token")
        path = f'/repos/{ENTRY["repository"]}/rules/branches/dev'
        with patch.object(api, "page", side_effect=[(rules(), f'<https://api.github.com{path}?page=2&per_page=100>; rel="next"'), ([], "")]):
            self.assertEqual(api.rules(ENTRY["repository"], "dev"), rules())
        for header in ('<https://outside.invalid/steal>; rel="next"', 'malformed',
                       f'<https://api.github.com{path}?page=3&per_page=100>; rel="next"',
                       f'<https://api.github.com{path}?page=2&per_page=100>; rel="last"',
                       f'<https://outside.invalid{path}?page=1&per_page=100>; rel="last"'):
            with patch.object(api, "page", return_value=([], header)), self.assertRaises(ValueError):
                api.rules(ENTRY["repository"], "dev")
        with patch.object(api, "page", side_effect=[(rules(), f'<https://api.github.com{path}?page=2&per_page=100>; rel="next"'), (rules(), "")]), self.assertRaisesRegex(ValueError, "duplicate"):
            api.rules(ENTRY["repository"], "dev")

    def test_json_duplicates_and_nonstandard_constants_refused(self):
        for value in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":' + b'[' * 2000):
            with self.assertRaises(ValueError):
                baseline.decode(value)

    def test_advertised_terminal_page_survives_every_partial_chain(self):
        api = baseline.Api("not-a-real-token")
        path = f'https://api.github.com/repos/{ENTRY["repository"]}/rules/branches/dev'
        for last in range(2, 6):
            complete = []
            for number in range(1, last + 1):
                header = (f'<{path}?page={number + 1}&per_page=100>; rel="next", '
                          f'<{path}?page={last}&per_page=100>; rel="last"') if number < last else ""
                complete.append(([{"type": "deletion", "ruleset_id": number}], header))
            with patch.object(api, "page", side_effect=complete):
                self.assertEqual(len(api.rules(ENTRY["repository"], "dev")), last)
            for stop in range(1, last):
                partial = copy.deepcopy(complete[:stop])
                partial[-1] = (partial[-1][0], f'<{path}?page={last}&per_page=100>; rel="last"' if stop == 1 else "")
                with self.subTest(last=last, stop=stop), patch.object(api, "page", side_effect=partial), self.assertRaisesRegex(ValueError, "incomplete"):
                    api.rules(ENTRY["repository"], "dev")
        inconsistent = [complete[0], ([{"type": "deletion", "ruleset_id": 7}], f'<{path}?page=6&per_page=100>; rel="last"')]
        with patch.object(api, "page", side_effect=inconsistent), self.assertRaisesRegex(ValueError, "terminal page changed"):
            api.rules(ENTRY["repository"], "dev")


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import yaml
        cls.workflow = yaml.load((ROOT / ".github/workflows/org-baseline.yml").read_text(), Loader=yaml.BaseLoader)

    def test_source_enrolled_unknown_outcomes_and_dangerous_skip_mutations(self):
        jobs = self.workflow["jobs"]
        self.assertEqual(jobs["baseline"]["name"], "Organization Baseline")
        self.assertEqual(jobs["baseline"]["if"], "github.repository != 'ForgingAlpha/.github'")
        result = jobs["result"]
        self.assertEqual(set(result["needs"]), {"baseline", "static", "tests"})
        self.assertIn("always()", result["if"])
        self.assertIn("github.repository != 'ForgingAlpha/.github'", result["name"])
        self.assertIn("needs.baseline.outputs.result_name", result["name"])
        self.assertIn("|| 'Organization Profile Result'", result["name"])
        for name in ("static", "tests"):
            self.assertIn("needs.baseline.outputs.profile != 'documentation-bootstrap'", jobs[name]["if"])
            self.assertNotEqual(jobs[name]["name"], "CI")
        self.assertIn("static", jobs["tests"]["needs"])

    def test_real_inline_identity_parser_refuses_fallback_and_injection(self):
        valid = {"workflow_repository": "ForgingAlpha/.github", "workflow_sha": "b" * 40,
                 "workflow_ref": "ForgingAlpha/.github/.github/workflows/org-baseline.yml@refs/heads/main"}
        cases = [(json.dumps({**valid, **change}), expected) for change, expected in
                 [({}, 0), ({"workflow_repository": "outside/repo"}, 1), ({"workflow_sha": "main"}, 1),
                  ({"workflow_ref": "wrong/path@main"}, 1), ({"workflow_sha": "b" * 40 + "\noutput=bad"}, 1),
                  ({"workflow_ref": "ForgingAlpha/.github/.github/workflows/org-baseline.yml@v1"}, 1),
                  ({"workflow_ref": "ForgingAlpha/.github/.github/workflows/org-baseline.yml@" + "b" * 40}, 0)]]
        cases += [(json.dumps({k: v for k, v in valid.items() if k != field}), 1) for field in valid]
        cases += [(json.dumps(valid)[:-1] + ',"workflow_sha":"' + 'e' * 40 + '"}', 1)]
        for job, definition in self.workflow['jobs'].items():
            script = definition['steps'][0]['run']
            for raw, expected in cases:
                with self.subTest(job=job, context=raw), tempfile.TemporaryDirectory() as d:
                    output = Path(d) / "output"
                    # Consumer/current-main context may advance; the resolved job
                    # source remains b, with no live-main lookup or fallback.
                    value = subprocess.run(["bash", "-e", "-c", script], env={**os.environ, "JOB_CONTEXT": raw,
                        "GITHUB_SHA": "e" * 40, "GITHUB_REF": "refs/heads/main", "GITHUB_OUTPUT": str(output)}, capture_output=True)
                    self.assertEqual(value.returncode, expected, value.stderr.decode())
                    if expected:
                        self.assertFalse(output.exists())
                    else:
                        self.assertEqual(output.read_text(), "repository=ForgingAlpha/.github\nsha=" + "b" * 40 + "\n")

    def test_read_only_coherent_source_no_language_optout(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read", "pull-requests": "read"})
        self.assertEqual(self.workflow['jobs']['baseline']['permissions'], {'contents': 'read', 'pull-requests': 'read', 'checks': 'read'})
        self.assertEqual(set(self.workflow["on"]), {"pull_request"})
        steps = self.workflow["jobs"]["baseline"]["steps"]
        self.assertEqual(steps[1]["with"]["ref"], "${{ steps.source.outputs.sha }}")
        self.assertEqual(steps[2]["with"]["ref"], "${{ github.event.pull_request.head.sha }}")
        self.assertTrue(all(step["with"]["persist-credentials"] == "false" for step in steps if step.get("uses", "").startswith("actions/checkout@")))
        self.assertFalse(any("@v1" in str(step) for step in steps))
        for name, job in self.workflow["jobs"].items():
            self.assertEqual(job["steps"][0]["run"], steps[0]["run"])
            checkouts = [s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@")]
            self.assertEqual(len(checkouts), 2)
            self.assertEqual(checkouts[0]["with"]["ref"], "${{ steps.source.outputs.sha }}")
            self.assertEqual(checkouts[1]["with"]["ref"], "${{ github.event.pull_request.head.sha }}")
            self.assertTrue(all(s["with"]["persist-credentials"] == "false" for s in checkouts))
            self.assertNotIn("@v1", str(job))
            self.assertNotIn("upload-artifact", str(job))
            self.assertNotIn("download-artifact", str(job))
            if name in ('baseline', 'static', 'tests'):
                self.assertEqual(job['outputs']['source_sha'], '${{ steps.source.outputs.sha }}')
            if name == 'baseline':
                self.assertEqual(job['outputs']['plan'], '${{ steps.plan.outputs.plan }}')
            if name == 'result':
                self.assertEqual(job['steps'][-1]['env']['BASELINE_NEEDS'], '${{ toJSON(needs) }}')
            if name in ("static", "tests"):
                self.assertNotIn('checks', job.get('permissions', self.workflow['permissions']))
                self.assertNotIn("github.token", str(job))
                self.assertIn("--stage preflight", str(job["steps"][3]))
        self.assertEqual(self.workflow["jobs"]["baseline"]["steps"][-1]["with"]["workspace"], "${{ github.workspace }}/consumer")



class ApplicationFixture(Fixture):
    def __init__(self, root, kinds=(('astro', '.'),), producer='central-product', no_tests=False):
        super().__init__(root)
        self.write('docs/route.md', '# Release\n\n<!-- route -->\nDirect release through dev.\n<!-- end-route -->\n')
        self.write('mise.toml', '[tools]\nnode = "24.18.0"\n' + ('rust = "1.90.0"\n' if any(k == 'rust' for k, _ in kinds) else ''))
        tools = {'node': {'version': '24.18.0', 'required_platforms': ['linux-x64']}}
        lock = '[tools.node]\nversion="24.18.0"\n[tools.node.platforms.linux-x64]\nurl="https://example.invalid/node"\nchecksum="sha256:' + 'a' * 64 + '"\n'
        if any(k == 'rust' for k, _ in kinds):
            tools['rust'] = {'version': '1.90.0', 'required_platforms': ['linux-x64']}
            lock += '[tools.rust]\nversion="1.90.0"\n[tools.rust.platforms.linux-x64]\nurl="https://example.invalid/rust"\nchecksum="sha256:' + 'b' * 64 + '"\n'
        self.write('mise.lock', lock)
        self.write('.github/update-policy.json', json.dumps({'schema_version': 1, 'normal_update_owner': 'renovate', 'base_branch': 'dev', 'runtime_profile': 'fixture'}))
        components = []
        for kind, directory in kinds:
            prefix = '' if directory == '.' else directory + '/'
            if kind == 'astro':
                component = {'kind': kind, 'root': directory, 'static_scripts': ['extra'], 'tests': {'kind': 'owner-declared-none', 'evidence_sha256': 'f' * 64} if no_tests else {'kind': 'required', 'scripts': ['test']}}
                self.write(prefix + 'package.json', json.dumps({'name': 'fixture', 'version': '1.0.0', 'devDependencies': {'astro': '1.0.0', 'eslint': '1.0.0', 'prettier': '1.0.0'}, 'scripts': {'build': 'echo build', 'extra': 'echo extra', 'test': 'echo test'}}))
                self.write(prefix + 'package-lock.json', '{"lockfileVersion":3,"packages":{}}')
            else:
                component = {'kind': kind, 'root': directory, 'tests': ['cargo-all']}
                self.write(prefix + 'Cargo.toml', '[workspace]\nmembers=["member"]\ndefault-members=[]\n')
                self.write(prefix + 'member/Cargo.toml', '[package]\nname="fixture"\nversion="0.1.0"\n')
                self.write(prefix + 'Cargo.lock', 'version = 4\n')
            components.append(component)
        if producer == 'qualification':
            self.write('.github/workflows/ci.yml', 'name: CI\non: [pull_request, push]\njobs:\n  legacy:\n    name: CI\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo legacy\n')
        self.commit()
        self.base = self.head
        self.git('update-ref', 'refs/remotes/origin/dev', self.base)
        self.write('docs/change.md', '# Change\n')
        self.commit()
        self.entry = {'repository': ENTRY['repository'], 'repository_id': ENTRY['repository_id'], 'branches': ['dev', 'main'], 'profile': 'mixed' if len({k for k, _ in kinds}) > 1 else kinds[0][0], 'producer': producer,
                      'qualification_subject': {'kind': 'none'}, 'release_route': {'declarations': [{'kind': 'direct', 'path': 'docs/route.md', 'start': '<!-- route -->', 'end': '<!-- end-route -->', 'text': 'Direct release through dev.\n'}], 'transition': 'none', 'reconciliation_sha256': 'c' * 64},
                      'review_policy': {'kind': 'codeowners'}, 'foundation': 'not-applicable', 'components': sorted(components, key=lambda c: c['root'])}
        if producer == 'qualification':
            self.entry['qualification_subject'] = {'kind': 'legacy-ci', 'branch': 'dev', 'legacy_workflow': {'path': '.github/workflows/ci.yml', 'blob': self.git('rev-parse', self.head + ':.github/workflows/ci.yml').strip(), 'job_id': 'legacy'}}
        self.entry.pop('release_route')
        bind_fixture(self, self.entry, 'docs/route.md')
        self.runtime = {'schema_version': 1, 'profiles': {'fixture': {'description': 'NONAUTHORITATIVE SOURCE FIXTURE', 'approved_tuples': [{'id': 'fixture-1', 'state': 'current', 'tools': tools}]}}, 'assignments': {ENTRY['repository']: {'profile': 'fixture', 'status': 'active'}}}

    def plan(self):
        baseline.catalog({'schema_version': 3, 'repositories': [row(self.entry)]})
        return baseline.app_plan(self.root, self.event(), self.entry, 'd' * 40, self.runtime, admission_record=admission_record(self, self.entry))


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.f = ApplicationFixture(self.directory / 'consumer')

    def test_markdown_only_product_failure_then_repair_entire_profile(self):
        """P2/P5/P20: same profile on docs-only edits, actual helper failures reach fan-in."""
        plan = self.f.plan()
        journal = []
        def command(argv, cwd, env=None, **kwargs):
            journal.append((argv, cwd, env))
            if argv[-3:] == ['central', 'script', 'test'] and (self.f.root / 'fail-test').exists():
                raise ValueError('required test failed')
            return b'v24.18.0\n' if '--version' in argv else None
        with patch.object(baseline, 'checked', side_effect=command):
            static = baseline.execute_products(self.f.root, plan, 'static')
            self.f.write('fail-test', 'fail')
            with self.assertRaisesRegex(ValueError, 'required test failed'):
                baseline.execute_products(self.f.root, plan, 'tests')
            (self.f.root / 'fail-test').unlink()
            tests = baseline.execute_products(self.f.root, plan, 'tests')
        phases = [row[0][-1] for row in journal if 'central' in row[0]]
        for check in ('format', 'lint', 'types', 'build', 'extra'):
            self.assertEqual(phases.count(check), 1)
        needs = successful_needs(plan, static=json.dumps(static), tests=json.dumps(tests))
        baseline.aggregate(plan, needs)
        needs['tests']['result'] = 'failure'
        with self.assertRaises(ValueError):
            baseline.aggregate(plan, needs)
        # New documentation revision keeps the exact required logical component set.
        self.f.write('docs/change.md', '# Repaired change\n')
        self.f.commit()
        self.assertEqual(self.f.plan()['components'], plan['components'])

    def test_missing_and_undeclared_inputs_never_select_docs(self):
        cases = [('package.json', None), ('package-lock.json', None), ('mise.lock', None),
                 ('extra/package.json', '{}'), ('vendored/Cargo.toml', '[package]\n'),
                 ('yarn.lock', 'unsupported'), ('nested/mise.toml', '[tools]\n'), ('rust-toolchain.toml', '[toolchain]\nchannel="stable"')]
        for index, (name, data) in enumerate(cases):
            with self.subTest(name=name):
                f = ApplicationFixture(self.directory / str(index))
                if data is None:
                    (f.root / name).unlink()
                else:
                    f.write(name, data)
                f.commit()
                with self.assertRaises((ValueError, OSError)):
                    f.plan()

    def test_schema_totality_and_explicit_no_tests(self):
        for change in ({'producer': None}, {'extra': True}, {'foundation': 'unknown'}, {'repository_id': True}):
            entry = {**self.f.entry, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                baseline.catalog({'schema_version': 3, 'repositories': [{**row(entry), **({'extra':True} if 'extra' in change else {})}]})
        for tests in (None, [], {'kind': 'required', 'scripts': []}, {'kind': 'owner-declared-none', 'evidence_sha256': ''}):
            entry = copy.deepcopy(self.f.entry)
            entry['components'][0]['tests'] = tests
            with self.assertRaises(ValueError):
                baseline.catalog({'schema_version': 3, 'repositories': [row(entry)]})
        f = ApplicationFixture(self.directory / 'none', no_tests=True)
        plan = f.plan()
        with patch.object(baseline, 'checked', return_value=b'v24.18.0\n') as command:
            receipt = baseline.execute_products(f.root, plan, 'tests')
        self.assertEqual(command.call_count, 1)  # Runtime observation; no npm setup/test invented.
        self.assertEqual(receipt['components'][0]['result'], 'no-tests')
        self.assertEqual(plan['required_jobs'], ['baseline', 'static', 'tests'])
        static = copy.deepcopy(receipt)
        static['phase'] = 'static'
        static['components'][0]['result'] = 'success'
        needs = successful_needs(plan, static=json.dumps(static), tests=json.dumps(receipt))
        baseline.aggregate(plan, needs)
        needs['static']['result'] = 'failure'
        with self.assertRaises(ValueError): baseline.aggregate(plan, needs)

    def test_missing_selected_script_and_local_workspace_refused(self):
        path = self.f.root / 'package.json'
        original = json.loads(path.read_text())
        for mutation in ('script', 'workspaces', 'file'):
            value = copy.deepcopy(original)
            if mutation == 'script':
                del value['scripts']['test']
            elif mutation == 'workspaces':
                value['workspaces'] = ['other']
            else:
                value['dependencies'] = {'other': 'file:../other'}
            self.f.write('package.json', json.dumps(value)); self.f.commit()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.f.plan()
        self.f.write('package.json', json.dumps(original)); self.f.commit()
        self.f.plan()

    def test_runtime_missing_planned_mismatch_and_foundation_deleted_pair(self):
        valid = copy.deepcopy(self.f.runtime)
        self.f.runtime['assignments'] = {}
        with self.assertRaises(ValueError): self.f.plan()
        self.f.runtime = copy.deepcopy(valid)
        self.f.runtime['assignments'][ENTRY['repository']]['status'] = 'planned'
        with self.assertRaises(ValueError): self.f.plan()
        self.f.runtime = valid
        self.f.entry['foundation'] = 'required'
        with self.assertRaises(ValueError): self.f.plan()
        self.f.entry['foundation'] = 'not-applicable'
        self.f.write('foundation.lock', '{}'); self.f.commit()
        with self.assertRaisesRegex(ValueError, 'foundation pair'): self.f.plan()

    def test_only_alternative_cargo_compiler_selectors_are_refused(self):
        self.f.write('.cargo/config.toml', '[build]\njobs=2\n[net]\noffline=true\n')
        self.f.commit(); self.f.plan()
        for key in ('rustc', 'rustc-wrapper', 'rustc-workspace-wrapper'):
            self.f.write('.cargo/config.toml', '[build]\n'+key+'="other-compiler"\n')
            self.f.commit()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'compiler selector'): self.f.plan()
        for key in ('RUSTC', 'RUSTC_WRAPPER', 'RUSTC_WORKSPACE_WRAPPER', 'RUSTUP_TOOLCHAIN',
                    'CARGO_BUILD_RUSTC', 'CARGO_BUILD_RUSTC_WRAPPER', 'CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER'):
            self.f.write('.cargo/config.toml', '[env]\n'+key+'="other-compiler"\n')
            self.f.commit()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'compiler environment'): self.f.plan()
        self.f.write('.cargo/config.toml', '[build]\njobs=2\n')
        self.f.commit(); self.f.plan()
        original = (self.f.root/'mise.toml').read_text()
        self.f.write('mise.toml', original+'\n[env]\nCUSTOM_BUILD_LABEL="fixture"\n')
        self.f.commit(); self.f.plan()
        self.f.write('mise.toml', original+'\n[env]\nRUSTC="other-compiler"\n')
        self.f.commit()
        with self.assertRaisesRegex(ValueError, 'compiler environment'): self.f.plan()

    def test_route_unrelated_edit_and_controlling_change(self):
        self.f.write('docs/unrelated.md', '# Unrelated prose\n'); self.f.commit()
        self.assertEqual(self.f.plan()['admission']['kind'], 'ordinary-task')
        self.f.write('docs/route.md', '# New precedence\n\n<!-- route -->\nDirect release through dev.\n<!-- end-route -->\n')
        self.f.commit()
        with self.assertRaisesRegex(ValueError, 'controlling source changed'):
            self.f.plan()
        # An unchanged selected region cannot conceal changed controlling bytes.
        for version in (1,2):
            with self.assertRaisesRegex(ValueError, 'unsupported enrollment schema'):
                baseline.catalog({'schema_version':version, 'repositories':[row(self.f.entry)]})

    def test_qualification_valid_invalid_repair_on_moving_base_without_repin(self):
        f = ApplicationFixture(self.directory / 'qualification', producer='qualification')
        source = json.dumps(f.entry, sort_keys=True)
        first = f.plan()
        f.write('nested/package.json', '{}'); f.commit()
        with self.assertRaises(ValueError): f.plan()
        (f.root / 'nested/package.json').unlink(); f.commit()
        f.base = f.head
        f.git('update-ref', 'refs/remotes/origin/dev', f.base)
        f.write('docs/change.md', '# Already-open repaired head\n'); f.commit()
        repaired = f.plan()
        self.assertNotEqual(first['head'], repaired['head'])
        self.assertNotEqual(first['base'], repaired['base'])
        self.assertEqual(source, json.dumps(f.entry, sort_keys=True))
        f.write('.github/workflows/ci.yml', (f.root / '.github/workflows/ci.yml').read_text() + '# changed producer\n'); f.commit()
        with self.assertRaisesRegex(ValueError, 'CI producer'): f.plan()

    def test_dual_dynamic_reusable_and_ambiguous_workflow_refused(self):
        cases = ['on: push\njobs:\n  CI:\n    runs-on: ubuntu-latest\n',
                 'on: pull_request\njobs:\n  x:\n    name: "${{ matrix.name }}"\n',
                 'on: pull_request\njobs:\n  x:\n    uses: owner/repo/.github/workflows/test.yml@main\n',
                 'on: push\non: pull_request\njobs: {}\n']
        for i, content in enumerate(cases):
            f = ApplicationFixture(self.directory / ('workflow' + str(i)))
            f.write('.github/workflows/local.yml', content); f.commit()
            with self.assertRaises(ValueError): f.plan()
        for data in (b'x: &v [1]\ny: *v', b'x: !!python/object:bad {}'):
            with self.assertRaises(ValueError): baseline.yaml_data(data)

    def test_every_required_result_and_deny_only_output(self):
        plan = self.f.plan()
        def receipt(phase):
            return json.dumps({'schema_version': 1, 'phase': phase, 'plan_sha256': baseline.plan_digest(plan), 'components': [{'index': 0, 'kind': 'astro', 'root': '.', 'result': 'success'}]})
        needs = successful_needs(plan, **{phase: receipt(phase) for phase in ('static', 'tests')})
        baseline.aggregate(plan, needs)
        states = ('success', 'failure', 'cancelled', 'skipped', None, 'unknown', 'missing')
        for combination in itertools.product(states, repeat=3):
            candidate = copy.deepcopy(needs)
            for job, state in zip(('baseline', 'static', 'tests'), combination):
                if state == 'missing':
                    del candidate[job]
                else:
                    candidate[job]['result'] = state
            if combination == ('success',) * 3:
                baseline.aggregate(plan, candidate)
            else:
                with self.subTest(combination=combination), self.assertRaises(ValueError):
                    baseline.aggregate(plan, candidate)
        for job in needs:
            for state in ('failure', 'cancelled', 'skipped', None, 'unknown', ''):
                bad = copy.deepcopy(needs); bad[job]['result'] = state
                with self.subTest(job=job, state=state), self.assertRaises(ValueError): baseline.aggregate(plan, bad)
        for raw in ('', '{}', 'x' * 65537, receipt('tests').replace('success', 'failure'), receipt('tests').replace('astro', 'rust')):
            bad = copy.deepcopy(needs); bad['tests']['outputs']['receipt'] = raw
            with self.assertRaises(ValueError): baseline.aggregate(plan, bad)
        bad = copy.deepcopy(needs); del bad['static']
        with self.assertRaises(ValueError): baseline.aggregate(plan, bad)
        bad = copy.deepcopy(needs); r = json.loads(receipt('tests'));r['components'] *= 2;bad['tests']['outputs']['receipt'] = json.dumps(r)
        with self.assertRaises(ValueError): baseline.aggregate(plan, bad)

    def test_admission_and_every_executed_source_must_match_final_plan(self):
        app = self.f.plan()
        docs = Fixture(self.directory / 'documents')
        bootstrap = baseline.make_plan(docs.root, docs.event(), docs.entry, 'd' * 40, admission_record(docs, docs.entry))
        for plan in (bootstrap, app):
            receipts = {phase: json.dumps({'schema_version': 1, 'phase': phase,
                        'plan_sha256': baseline.plan_digest(plan), 'components': [
                            {'index': i, 'kind': c['kind'], 'root': c['root'], 'result': 'success'}
                            for i, c in enumerate(plan['components'])]}) for phase in ('static', 'tests')}
            needs = successful_needs(plan, **(receipts if plan is app else {}))
            baseline.aggregate(plan, needs)
            for raw in (None, '', '{}', '[]', 'x' * 65537, '{"source_sha":"one","source_sha":"two"}'):
                bad = copy.deepcopy(needs)
                if raw is None:
                    del bad['baseline']['outputs']['plan']
                else:
                    bad['baseline']['outputs']['plan'] = raw
                with self.subTest(profile=plan['profile'], raw=raw and raw[:30]), self.assertRaises(ValueError):
                    baseline.aggregate(plan, bad)
            for field, value in (('source_sha', 'e' * 40), ('head', 'e' * 40), ('base', 'e' * 40),
                                 ('components', [] if plan is app else [{'kind': 'astro'}]),
                                 ('proposal', {**plan['proposal'], 'task_target': 'staging'}),
                                 ('admission_sha256', '0' * 64),
                                 ('checking_fingerprints', {}), ('required_jobs', []),
                                 ('profile', 'wrong-profile'), ('producer', 'qualification'),
                                 ('repository_id', True)):
                bad = copy.deepcopy(needs)
                bad['baseline']['outputs']['plan'] = json.dumps({**plan, field: value})
                with self.subTest(profile=plan['profile'], field=field), self.assertRaises(ValueError):
                    baseline.aggregate(plan, bad)
            for job in plan['required_jobs']:
                for source in (None, '', 'main', 'e' * 40):
                    bad = copy.deepcopy(needs)
                    if source is None:
                        del bad[job]['outputs']['source_sha']
                    else:
                        bad[job]['outputs']['source_sha'] = source
                    with self.subTest(profile=plan['profile'], job=job, source=source), self.assertRaises(ValueError):
                        baseline.aggregate(plan, bad)
            for outputs in (None, [], 'invalid'):
                bad = copy.deepcopy(needs); bad['baseline']['outputs'] = outputs
                with self.subTest(outputs=outputs), self.assertRaises(ValueError):
                    baseline.aggregate(plan, bad)

    def test_mixed_complete_workspace_and_second_component_failure(self):
        f = ApplicationFixture(self.directory / 'mixed', kinds=(('astro', 'a'), ('rust', 'z')))
        plan = f.plan()
        calls = []
        def command(argv, cwd, env=None, **kwargs):
            calls.append(argv)
            if '--version' in argv: return b'rustc 1.90.0 (fixture)\n' if 'rustc' in argv else b'v24.18.0\n'
            if 'metadata' in argv:
                manifest = str(f.root / 'z/member/Cargo.toml')
                return json.dumps({'version': 1, 'workspace_root': str(f.root / 'z'), 'workspace_members': ['opaque-member'], 'packages': [{'id': 'opaque-member', 'manifest_path': manifest, 'dependencies': []}]}).encode()
            if argv[-1] == 'test': raise ValueError('second component fails')
        with patch.object(baseline, 'checked', side_effect=command):
            result = baseline.execute_products(f.root, plan, 'static')
            self.assertEqual(len(result['components']), 2)
            with self.assertRaisesRegex(ValueError, 'second component'):
                baseline.execute_products(f.root, plan, 'tests')
        self.assertTrue(any('--no-deps' in x and '--locked' in x for x in calls))
        self.assertLess(next(i for i, x in enumerate(calls) if 'metadata' in x), next(i for i, x in enumerate(calls) if 'central' in x))
        f.write('vendor/Cargo.toml', '[package]\nname="ignored"'); f.commit()
        changed = f.plan()
        calls.clear()
        with patch.object(baseline, 'checked', side_effect=command), self.assertRaisesRegex(ValueError, 'uncovered'):
            baseline.execute_products(f.root, changed, 'static')
        self.assertFalse(any('central' in x for x in calls))

    def test_all_workspace_coverage_precedes_any_product_helper(self):
        f = ApplicationFixture(self.directory / 'workspaces', kinds=(('astro', 'a'), ('rust', 'b'), ('rust', 'c')))
        plan = f.plan()
        for failure in (None, 'missing', 'overlap'):
            calls = []
            def command(argv, cwd, env=None, **kwargs):
                calls.append(argv)
                if '--version' in argv: return b'rustc 1.90.0 (fixture)\n' if 'rustc' in argv else b'v24.18.0\n'
                if 'metadata' in argv:
                    members = [str(cwd / 'member/Cargo.toml')]
                    if cwd.name == 'c' and failure == 'missing': members = [str(cwd / 'Cargo.toml')]
                    if cwd.name == 'c' and failure == 'overlap': members.append(str(f.root / 'b/member/Cargo.toml'))
                    return json.dumps({'version': 1, 'workspace_root': str(cwd), 'workspace_members': members,
                                       'packages': [{'id': m, 'manifest_path': m, 'dependencies': []} for m in members]}).encode()
            with self.subTest(failure=failure), patch.object(baseline, 'checked', side_effect=command):
                if failure:
                    with self.assertRaisesRegex(ValueError, 'uncovered|overlapping'):
                        baseline.execute_products(f.root, plan, 'static')
                    self.assertFalse(any('central' in x for x in calls))
                else:
                    self.assertEqual(len(baseline.execute_products(f.root, plan, 'static')['components']), 3)
                    self.assertLess(max(i for i,x in enumerate(calls) if 'metadata' in x), min(i for i,x in enumerate(calls) if 'central' in x))

    def test_regular_instruction_markdown_is_bounded_linted_and_repaired(self):
        original = baseline.checked
        payloads = []
        def command(argv, cwd, env=None, **kwargs):
            if any(str(arg).endswith('lint_bootstrap.mjs') for arg in argv):
                payloads.append(json.loads(kwargs['data']))
                return original(argv, cwd, env, **kwargs)
        def common():
            event = self.f.event(); event['repository']['default_branch'] = 'dev'
            # This formatting test explicitly qualifies each exact successor
            # instruction closure; the route suite separately refuses unknowns.
            e=self.f.entry['proposal']['evidence']
            successor={k:copy.deepcopy(e[k]) for k in ('files','regions','context')}
            successor['context']=git_context(self.f.root,self.f.head)
            e['transition']={'kind':'none'} if successor['context']==e['context'] else {'kind':'forward','predecessor':{k:copy.deepcopy(e[k]) for k in ('files','regions','context')},'successor':successor,'reconciliation_sha256':'9'*64}
            with patch.object(baseline, 'checked', side_effect=command), patch.object(baseline.policy, 'incomplete_baseline', return_value=[]):
                baseline.application_common(self.f.root, event, self.f.entry, FakeApi(self.f), self.f.plan())
        common()
        self.assertNotIn('AGENTS.md', payloads[-1]); self.assertNotIn('CLAUDE.md', payloads[-1])
        for name in ('AGENTS.md', 'CLAUDE.md'):
            (self.f.root/name).unlink()
            self.f.write(name, '# Instructions\n\n### Invalid skipped heading\n')
        self.f.commit()
        with self.assertRaisesRegex(ValueError, 'required command failed'): common()
        self.assertTrue({'AGENTS.md', 'CLAUDE.md'} <= set(payloads[-1]))
        for name in ('AGENTS.md', 'CLAUDE.md'): self.f.write(name, '# Instructions\n\n## Valid next heading\n')
        self.f.commit(); common()
        count = len(payloads)
        self.f.write('AGENTS.md', 'a' * (512 * 1024 + 1)); self.f.commit()
        with self.assertRaises(ValueError): common()
        self.assertEqual(len(payloads), count)

    def test_common_composition_uses_full_owned_validators_and_safe_cwd(self):
        plan = self.f.plan(); calls = []
        self.f.write('.github/workflows/safe.yml', 'on: pull_request\njobs:\n  docs:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo safe\n'); self.f.commit(); plan = self.f.plan()
        with patch.object(baseline, 'checked', side_effect=lambda *a, **k: calls.append((a, k))), patch.object(baseline.policy, 'incomplete_baseline', return_value=[]):
            event = self.f.event(); event['repository']['default_branch'] = 'dev'
            baseline.application_common(self.f.root, event, self.f.entry, FakeApi(self.f), plan)
        joined = [' '.join(map(str, a[0])) for a, _ in calls]
        for owner in ('validate_product_lifecycle_baseline.py', 'validate_codeowners_contract.py', 'lint_bootstrap.mjs', 'check_workflows.py', 'check_dependabot_coverage.py', 'validate_update_ownership.py', 'foundation_source.py'):
            self.assertEqual(sum(owner in command for command in joined), 1, owner)
        self.assertFalse(any('lint_markdown.mjs' in command for command in joined))
        self.assertFalse(any('check_merge_flow.sh' in command for command in joined))
        self.assertFalse(any('--default-branch' in command for command in joined))
        for (argv, cwd, *rest), _ in calls:
            self.assertIn(cwd, (self.f.root, baseline.SOURCE))

    def test_common_each_owned_failure_stops_and_unusual_action_is_checked(self):
        event = self.f.event(); event['repository']['default_branch'] = 'dev'
        plan = self.f.plan()
        owners = ('validate_product_lifecycle_baseline.py', 'validate_codeowners_contract.py',
                  'lint_bootstrap.mjs', 'install_actionlint.sh',
                  'check_workflows.py', 'check_dependabot_coverage.py',
                  'validate_update_ownership.py', 'foundation_source.py')
        for owner in owners:
            calls = []
            def command(argv, *args, **kwargs):
                calls.append(argv)
                if any(Path(str(part)).name == owner for part in argv):
                    raise ValueError('owner refusal: ' + owner)
            with self.subTest(owner=owner), patch.object(baseline, 'checked', side_effect=command), patch.object(
                baseline.policy, 'incomplete_baseline', return_value=[]
            ), self.assertRaisesRegex(ValueError, 'owner refusal'):
                baseline.application_common(self.f.root, event, self.f.entry, FakeApi(self.f), plan)
            self.assertTrue(any(Path(str(part)).name == owner for part in calls[-1]))
        with patch.object(baseline.route, 'validate_admission', side_effect=ValueError('owner refusal: admission')), patch.object(baseline, 'checked'), patch.object(baseline.policy, 'incomplete_baseline', return_value=[]), self.assertRaisesRegex(ValueError, 'owner refusal: admission'):
            baseline.application_common(self.f.root, event, self.f.entry, FakeApi(self.f), plan)
        self.f.write('custom/action.yaml', 'name: unsafe\ndescription: test\nruns:\n  using: composite\n  steps:\n    - uses: actions/checkout@main\n')
        self.f.commit(); plan = self.f.plan()
        with patch.object(baseline, 'checked'), patch.object(baseline.policy, 'incomplete_baseline', return_value=[]), self.assertRaisesRegex(ValueError, 'Action safety'):
            baseline.application_common(self.f.root, self.f.event(), self.f.entry, FakeApi(self.f), plan)

    def test_product_environment_strips_tokens_and_runtime_overrides(self):
        names = ('GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_LICENSE_TOKEN', 'MISE_GITHUB_TOKEN', 'INPUT_GITHUB_TOKEN',
                 'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'RUSTC', 'RUSTC_WRAPPER',
                 'RUSTC_WORKSPACE_WRAPPER', 'RUSTUP_TOOLCHAIN', 'CARGO_BUILD_RUSTC',
                 'CARGO_BUILD_RUSTC_WRAPPER', 'CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER')
        with patch.dict(os.environ, {**dict.fromkeys(names, 'secret-canary'), 'NODE_OPTIONS': '--require evil'}):
            safe = baseline.clean_env()
            self.assertNotIn('secret-canary', safe.values())
            for key in ('RUSTUP_TOOLCHAIN', 'NODE_OPTIONS'): self.assertNotIn(key, safe)
            output = baseline.checked([sys.executable, '-c', 'import os,json; print(json.dumps(dict(os.environ)))'], self.directory, capture=True)
            self.assertNotIn(b'secret-canary', output)
        plan = self.f.plan()
        with patch.object(baseline, 'checked', return_value=b'v99.0.0\n'), self.assertRaisesRegex(ValueError, 'selected runtime'):
            baseline.verify_runtime(self.f.root, plan)
        with patch.object(baseline, 'checked', return_value=b'v24.18.0\n'):
            baseline.verify_runtime(self.f.root, plan)

    def test_plan_tampering_and_identity_changes_refused(self):
        plan = self.f.plan()
        self.f.write('ignored.txt', 'untracked')
        with self.assertRaisesRegex(ValueError, 'untracked'): self.f.plan()
        (self.f.root / 'ignored.txt').unlink()
        path = self.f.root / 'package.json'; content = path.read_text();path.unlink();path.symlink_to('../outside')
        with self.assertRaises(ValueError): self.f.plan()
        path.unlink();path.write_text(content)
        self.assertEqual(self.f.plan(), plan)

    def test_composed_cli_stages_failure_repair_and_final_currentness(self):
        from types import SimpleNamespace
        output = self.directory / "outputs"
        event = self.f.event()
        original_integrity = baseline.application_integrity
        def fixture_integrity(root, inventory, entry, *args):
            return original_integrity(root, inventory, entry, self.f.runtime)
        def read_outputs():
            return dict(line.split("=", 1) for line in output.read_text().splitlines())
        calls = []
        failing = [True]
        def command(argv, cwd, env=None, **kwargs):
            calls.append(argv)
            if argv == ['mise', 'install', '--locked']:
                self.assertEqual(cwd, self.f.root)
                self.assertNotIn('fixture-api-only', env.values())
            if '--version' in argv:
                return b'v24.18.0\n'
            if argv[-3:] == ['central', 'script', 'test'] and failing[0]:
                raise ValueError('product test failed')
        api = FakeApi(self.f)
        env = {'GITHUB_REPOSITORY': ENTRY['repository'], 'GITHUB_REPOSITORY_ID': str(ENTRY['repository_id']),
               'GITHUB_OUTPUT': str(output), 'GITHUB_TOKEN': 'fixture-api-only'}
        with patch.dict(os.environ, env), patch.object(baseline.route, 'admission', side_effect=lambda api, event, entry, source: admission_record(self.f, self.f.entry, source)), patch.object(baseline, 'Api', return_value=api), \
                patch.object(baseline, 'application_integrity', side_effect=fixture_integrity), \
                patch.object(baseline, 'application_common') as common, patch.object(baseline, 'checked', side_effect=command):
            baseline.staged_main(SimpleNamespace(stage='admit'), self.f.root, event, [self.f.entry], 'd' * 40)
            common.assert_called_once()
            admitted = read_outputs()
            self.assertEqual(admitted['result_name'], 'CI')
            os.environ['BASELINE_PLAN'] = admitted['plan']
            for stage in ('preflight', 'install', 'static', 'tests'):
                before = len(calls)
                with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'admission subject/source mismatch'):
                    baseline.staged_main(SimpleNamespace(stage=stage), self.f.root, event, [self.f.entry], 'e' * 40)
                self.assertEqual(len(calls), before)
            baseline.staged_main(SimpleNamespace(stage='preflight'), self.f.root, event, [self.f.entry], 'd' * 40)
            baseline.staged_main(SimpleNamespace(stage='install'), self.f.root, event, [self.f.entry], 'd' * 40)
            baseline.staged_main(SimpleNamespace(stage='static'), self.f.root, event, [self.f.entry], 'd' * 40)
            static = read_outputs()['receipt']
            with self.assertRaisesRegex(ValueError, 'product test failed'):
                baseline.staged_main(SimpleNamespace(stage='tests'), self.f.root, event, [self.f.entry], 'd' * 40)
            failing[0] = False
            baseline.staged_main(SimpleNamespace(stage='tests'), self.f.root, event, [self.f.entry], 'd' * 40)
            tests = read_outputs()['receipt']
            needs = successful_needs(json.loads(admitted['plan']), static=static, tests=tests)
            os.environ['BASELINE_NEEDS'] = json.dumps(needs)
            with patch.object(sys, 'stdout', io.StringIO()) as logged, self.assertRaises(ValueError):
                baseline.staged_main(SimpleNamespace(stage='finalize'), self.f.root, event, [self.f.entry], 'e' * 40)
            self.assertEqual(logged.getvalue(), '')
            with patch.object(sys, 'stdout', io.StringIO()) as logged:
                baseline.staged_main(SimpleNamespace(stage='finalize'), self.f.root, event, [self.f.entry], 'd' * 40)
            self.assertEqual(json.loads(logged.getvalue())['head'], self.f.head)
            self.assertEqual(json.loads(logged.getvalue())['required_results'], {'baseline': 'success', 'static': 'success', 'tests': 'success'})
            self.assertNotIn('fixture-api-only', logged.getvalue())
            api.live['head']['sha'] = 'e' * 40
            with self.assertRaisesRegex(ValueError, 'head.*moved'):
                baseline.staged_main(SimpleNamespace(stage='finalize'), self.f.root, event, [self.f.entry], 'd' * 40)
            api.live['head']['sha'] = self.f.head
            api.base = 'e' * 40
            with self.assertRaisesRegex(ValueError, 'base branch moved'):
                baseline.staged_main(SimpleNamespace(stage='finalize'), self.f.root, event, [self.f.entry], 'd' * 40)
        self.assertEqual(sum(x[-1] == 'format' for x in calls), 1)

    def test_real_security_proofs_conserve_complete_central_plan_and_outputs(self):
        """Real Git trees + S1 verifier; provider attestations/product tools are fixtures."""
        import base64
        from types import SimpleNamespace
        from test_proposal_route import security_fixture, Api as RouteApi
        for projected in (False, True):
            with self.subTest(projected=projected):
                f = ApplicationFixture(self.directory / ('projection' if projected else 'source'))
                f.base = f.head; f.branch = 'main'
                f.git('update-ref', 'refs/remotes/origin/main', f.base)
                f.write('package-lock.json', '{"lockfileVersion":3,"packages":{},"version":"2"}')
                f.commit()
                bind_fixture(f, f.entry, 'docs/route.md')
                _, original_event, raw, module = security_fixture(projected)
                repo = f.entry['repository']
                base_tree = f.git('rev-parse', f.base+'^{tree}').strip()
                head_tree = f.git('rev-parse', f.head+'^{tree}').strip()
                replacements = {'ForgingAlpha/alphaapps-site':repo, 'a'*40:f.base, 'b'*40:f.head,
                                ('c' if projected else 'd')*40:base_tree,
                                ('d' if projected else 'e')*40:head_tree}
                def translate(value):
                    text=json.dumps(value)
                    for before, after in replacements.items(): text=text.replace(before,after)
                    return json.loads(text)
                api = RouteApi(translate(raw.gets), translate(raw.page_values))
                actual_objects=git_data(f.root,repo,[f.base,f.head])
                # Preserve provider-only synthetic test-merge metadata while
                # taking every real base/head tree/blob from the fixture Git store.
                api.gets.update(actual_objects)
                event = translate(original_event)
                event['repository']['id'] = f.entry['repository_id']
                for side in ('head','base'):event['pull_request'][side]['repo']['id']=f.entry['repository_id']
                f.event = lambda: copy.deepcopy(event)
                api.gets[f'repos/{repo}']['id']=f.entry['repository_id']
                api.gets[f'repos/{repo}/pulls/{event["number"]}']=copy.deepcopy(event['pull_request'])
                for revision, tree in ((f.base,base_tree),(f.head,head_tree)):
                    entries=[]
                    for line in f.git('ls-tree', revision).splitlines():
                        meta,name=line.split('\t');mode,kind,oid=meta.split()
                        entries.append({'path':name,'mode':mode,'type':kind,'sha':oid})
                        if kind=='blob':
                            data=baseline.git(f.root,'show',revision+':'+name)
                            api.gets[f'repos/{repo}/git/blobs/{oid}']=module.encoded_blob(data)
                    api.gets[f'repos/{repo}/git/trees/{tree}']={'truncated':False,'tree':entries}
                    for source in f.entry['proposal']['evidence']['files']:
                        data=baseline.git(f.root,'show',revision+':'+source['path'])
                        api.gets[f'repos/{repo}/contents/{source["path"]}?ref={revision}']={
                            'type':'file','encoding':'base64','size':len(data),'content':base64.b64encode(data).decode(),
                            'sha':f.git('rev-parse',revision+':'+source['path']).strip()}
                api.gets[f'repos/{repo}/compare/{f.base}...{f.base}']={'status':'identical','merge_base_commit':{'sha':f.base}}
                api.gets[f'repos/{repo}/branches/dev']={'commit':{'sha':f.base},'protected':True}
                if projected:
                    check=api.page_values[f'repos/{repo}/commits/{f.head}/check-runs?filter=all&per_page=100'][0]['check_runs'][0]
                    proof=module.security_patch.parse_projection_attestation(json.loads(check['output']['summary']))
                    check.update(module.security_patch.projection_check_payload(proof))
                record=baseline.route.admission(api,event,row(f.entry),'d'*40)
                self.assertEqual(record['kind'],'security-projection' if projected else 'dependabot-source')
                self.assertIsNone(baseline.route.ordinary(row(f.entry),record,False))
                original_integrity=baseline.application_integrity
                def integrity(root, inventory, entry, *args):
                    return original_integrity(root,inventory,entry,f.runtime)
                class CurrentApi:
                    def get(self, path):
                        return api.get(path.lstrip('/'))
                    def rules(self, *args):
                        return rules()
                calls=[];fail=[False]
                output=self.directory/('projection-output' if projected else 'source-output')
                output.write_text('outer=unchanged\n')
                def command(argv,cwd,env=None,**kwargs):
                    calls.append(argv)
                    if 'validate_update_ownership.py' in ' '.join(argv):
                        self.assertNotIn('GITHUB_OUTPUT',env)
                    if '--version' in argv:return b'v24.18.0\n'
                    if argv[-3:]==['central','script','test'] and fail[0]:raise ValueError('required product test failed')
                env={'GITHUB_OUTPUT':str(output),'GITHUB_TOKEN':'fixture-read-only','GITHUB_REPOSITORY':repo,
                     'GITHUB_REPOSITORY_ID':str(f.entry['repository_id'])}
                with patch.dict(os.environ,env),patch.object(baseline.route.security,'GhApi',return_value=api), \
                     patch.object(baseline,'Api',return_value=CurrentApi()),patch.object(baseline,'application_integrity',side_effect=integrity), \
                     patch.object(baseline,'checked',side_effect=command):
                    # Execute actual common composition: no child proof field may reach outer output.
                    plan=baseline.app_plan(f.root,event,f.entry,'d'*40,f.runtime,admission_record=record)
                    baseline.application_common(f.root,event,f.entry,CurrentApi(),plan)
                    self.assertEqual(output.read_text(),'outer=unchanged\n')
                    baseline.staged_main(SimpleNamespace(stage='admit'),f.root,event,[f.entry],'d'*40)
                    fields=dict(line.split('=',1) for line in output.read_text().splitlines())
                    self.assertEqual(set(fields),{'outer','plan','profile','producer','result_name','mise_version'})
                    plan=json.loads(fields['plan']);self.assertEqual(plan['admission'],record)
                    os.environ['BASELINE_PLAN']=fields['plan']
                    for stage in ('preflight','install','static'):
                        baseline.staged_main(SimpleNamespace(stage=stage),f.root,event,[f.entry],'d'*40)
                    static=dict(line.split('=',1) for line in output.read_text().splitlines())['receipt']
                    fail[0]=True
                    with self.assertRaisesRegex(ValueError,'required product test'):
                        baseline.staged_main(SimpleNamespace(stage='tests'),f.root,event,[f.entry],'d'*40)
                    fail[0]=False
                    baseline.staged_main(SimpleNamespace(stage='tests'),f.root,event,[f.entry],'d'*40)
                    tests=dict(line.split('=',1) for line in output.read_text().splitlines())['receipt']
                    os.environ['BASELINE_NEEDS']=json.dumps(successful_needs(plan,static=static,tests=tests))
                    with patch.object(sys,'stdout',io.StringIO()) as final:
                        baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                    self.assertEqual(json.loads(final.getvalue())['admission_kind'],record['kind'])
                    bad=copy.deepcopy(plan);bad['admission']['kind']='ordinary-task'
                    os.environ['BASELINE_NEEDS']=json.dumps(successful_needs(bad,static=static,tests=tests))
                    with self.assertRaises(ValueError):
                        baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                self.assertTrue(any('validate_update_ownership.py' in ' '.join(c) for c in calls))
                self.assertTrue(any(c[-1:] == ['format'] for c in calls))

    def test_actual_central_pr_updater_subprocess_and_event_transport(self):
        import shutil
        f=self.f
        f.write('renovate.json',json.dumps({'extends':['local>ForgingAlpha/.github:renovate-config'],'baseBranchPatterns':['dev']}))
        f.write('.github/dependabot.yml','version: 2\nupdates:\n  - package-ecosystem: npm\n    directory: /\n    open-pull-requests-limit: 0\n')
        f.commit();f.base=f.head;f.write('docs/pr.md','# Candidate\n');f.commit()
        f.git('update-ref','refs/remotes/origin/dev',f.base);bind_fixture(f,f.entry,'docs/route.md')
        event=f.event();event['repository']['default_branch']='main';repo=f.entry['repository']
        gets=git_data(f.root,repo,[f.base,f.head])
        gets.update({f'repos/{repo}':event['repository'],f'repos/{repo}/pulls/1':{**event['pull_request'],'number':1,'state':'open'},
             f'repos/{repo}/branches/dev':{'commit':{'sha':f.base},'protected':True},
             f'repos/{repo}/branches/feature%2Fdocs':{'commit':{'sha':f.head},'protected':False},
             f'repos/{repo}/compare/{f.base}...{f.base}':{'status':'identical','merge_base_commit':{'sha':f.base}}})
        bundle=self.directory/'checking-bundle';shutil.copytree(ROOT,bundle,ignore=shutil.ignore_patterns('.git','__pycache__'))
        (bundle/'actions/ci-org-baseline/enrollment.json').write_text(json.dumps({'schema_version':3,'repositories':[row(f.entry)]}))
        spec=importlib.util.spec_from_file_location('central_pr_fixture',bundle/'actions/ci-org-baseline/scripts/baseline.py')
        central=importlib.util.module_from_spec(spec);spec.loader.exec_module(central)
        event_file=self.directory/'pr-event';event_file.write_text(json.dumps(event))
        api_file=self.directory/'api';api_file.write_text(json.dumps(gets))
        gh=self.directory/'gh';gh.write_text('#!/usr/bin/env python3\nimport os,json,sys\nassert sys.argv[1]=="api" and "--method" not in sys.argv\nif os.environ.get("GH_TOKEN",os.environ.get("GITHUB_TOKEN"))!="fixture-read-only":sys.exit("fixture token unavailable")\nprint(json.dumps(json.load(open(os.environ["FIXTURE_API"]))[sys.argv[-1]]))\n');gh.chmod(0o700)
        output=self.directory/'outer-output';output.write_text('outer=unchanged\n')
        env={'PATH':str(self.directory)+os.pathsep+os.environ['PATH'],'FIXTURE_API':str(api_file),'GITHUB_EVENT_PATH':str(event_file),
             'GITHUB_EVENT_NAME':'pull_request','GITHUB_TOKEN':'fixture-read-only','GITHUB_REPOSITORY':repo,
             'GITHUB_REPOSITORY_ID':str(f.entry['repository_id']),'GITHUB_OUTPUT':str(output)}
        executed=[];original_checked=central.checked
        def command(argv,cwd,environment=None,**kwargs):
            if any(str(x).endswith('/validate_update_ownership.py') for x in argv):
                self.assertNotIn('GITHUB_OUTPUT',environment)
                executed.append((argv,cwd))
                return original_checked(argv,cwd,environment,**kwargs)
            # Other complete common owners retain their separate suites; no
            # installation/tool/product execution is claimed by this boundary test.
        with patch.dict(os.environ,env):
            record=central.route.admission(central.route.security.GhApi(),event,row(f.entry),'d'*40)
            plan=central.app_plan(f.root,event,f.entry,'d'*40,f.runtime,admission_record=record)
            with patch.object(central,'checked',side_effect=command):
                central.application_common(f.root,event,f.entry,FakeApi(f),plan)
                self.assertEqual(output.read_text(),'outer=unchanged\n')
                event_file.write_text(json.dumps({**event,'repository':{'full_name':'ForgingAlpha/wrong','id':1}}))
                with self.assertRaisesRegex(ValueError,'required command failed'):
                    central.application_common(f.root,event,f.entry,FakeApi(f),plan)
                self.assertEqual(output.read_text(),'outer=unchanged\n')
        self.assertEqual(len(executed),2)

    def test_capture_enforces_limits_while_process_is_running(self):
        self.assertEqual(baseline.checked([sys.executable, '-c', 'print("ok")'], self.directory, capture=True, capture_limit=3), b'ok\n')
        for stream, limit in [('stdout', 1024), ('stderr', 65536)]:
            program = 'import os,time; os.write(%d, b"x" * %d); time.sleep(30)' % (1 if stream == 'stdout' else 2, limit + 1)
            started = __import__('time').monotonic()
            with self.assertRaisesRegex(ValueError, 'bounded capture'):
                baseline.checked([sys.executable, '-c', program], self.directory, capture=True, capture_limit=1024, timeout=5)
            self.assertLess(__import__('time').monotonic() - started, 5)

    def test_recursive_central_actions_resolve_without_moving_first_party_refs(self):
        workflow = baseline.yaml_data((ROOT / '.github/workflows/org-baseline.yml').read_bytes())
        visited = set()
        def visit_steps(steps):
            for step in steps:
                target = step.get('uses', '')
                self.assertFalse(target.startswith('ForgingAlpha/.github/') and '@v1' in target)
                if target.startswith('./baseline-source/'):
                    path = ROOT / target.removeprefix('./baseline-source/') / 'action.yml'
                    if path in visited:
                        continue
                    visited.add(path)
                    visit_steps(baseline.yaml_data(path.read_bytes())['runs']['steps'])
        for job in workflow['jobs'].values():
            visit_steps(job['steps'])
        self.assertIn(ROOT / 'actions/ci-dependency-review/action.yml', visited)

    def test_consumer_runtime_setup_explicitly_disables_default_token(self):
        workflow = baseline.yaml_data((ROOT / '.github/workflows/org-baseline.yml').read_bytes())
        for job_id in ('static', 'tests'):
            steps = workflow['jobs'][job_id]['steps']
            setups = [s for s in steps if s.get('uses', '').startswith('jdx/mise-action@')]
            self.assertEqual(len(setups), 1)
            self.assertEqual(setups[0]['with']['github_token'], '')
            self.assertEqual(setups[0]['with']['working_directory'], 'baseline-source')
            for flag in ('install', 'env', 'export_path', 'cache', 'reshim', 'add_shims_to_path'):
                self.assertEqual(setups[0]['with'][flag], 'false')
            for token in ('GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_LICENSE_TOKEN', 'MISE_GITHUB_TOKEN', 'INPUT_GITHUB_TOKEN'):
                self.assertEqual(setups[0]['env'][token], '')
            self.assertTrue(any('--stage preflight' in s.get('run', '') for s in steps[:steps.index(setups[0])]))
            self.assertTrue(any('--stage install' in s.get('run', '') for s in steps[steps.index(setups[0])+1:]))

    def test_owned_tool_literals_are_fixed_data(self):
        values = baseline.literal_values()
        self.assertEqual(values, {'actionlint_version': '1.7.12', 'actionlint_sha256': '8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8', 'mise_version': '2026.8.3', 'audit_version': '0.22.2'})
        preset = json.loads((ROOT / 'renovate-config.json').read_text())
        self.assertNotIn('customManagers', preset)


if __name__ == "__main__":
    unittest.main()
