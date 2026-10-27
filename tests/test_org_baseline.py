"""REQ-024–026: preserve valid bootstrap and refuse trust-boundary violations."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tested_org_baseline", ROOT / "actions/ci-org-baseline/scripts/baseline.py")
baseline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = baseline
spec.loader.exec_module(baseline)
ENTRY = baseline.catalog(baseline.decode((ROOT / "actions/ci-org-baseline/enrollment.json").read_bytes()))[0]


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
            "head": {"repo": repo, "ref": "feature/docs", "sha": self.head}}}


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
            result = baseline.run(self.fixture.root, self.fixture.event(), [ENTRY], FakeApi(self.fixture))
            self.assertEqual(result["head"], self.fixture.head)
            self.assertEqual(result["source"], "ForgingAlpha/.github")
            self.fixture.write("PROJECT.md", "<!-- markdownlint-disable MD001 -->\n# Title\n\n### Skipped heading\n")
            self.fixture.commit()
            with self.assertRaisesRegex(ValueError, "Markdown"):
                baseline.run(self.fixture.root, self.fixture.event(), [ENTRY], FakeApi(self.fixture))
            self.fixture.write("PROJECT.md", "# Title\n\n## Repaired heading\n")
            self.fixture.commit()
            baseline.run(self.fixture.root, self.fixture.event(), [ENTRY], FakeApi(self.fixture))

    def test_provisional_metadata_never_uses_definition_only_exception(self):
        self.fixture.write("docs/intent.md", "---\nstatus: provisional\n---\n\n# Intent\n")
        self.fixture.commit()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
            with self.assertRaisesRegex(ValueError, "approved structural"):
                baseline.run(self.fixture.root, self.fixture.event(), [ENTRY], FakeApi(self.fixture))

    def test_main_runs_complete_profile_with_fresh_main_evidence(self):
        fixture = Fixture(Path(self.temp.name) / "main", branch="main")
        api = FakeApi(fixture)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"],
                                     "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"]),
                                     "BASELINE_SOURCE_SHA": "b" * 40}):
            result = baseline.run(fixture.root, fixture.event(), [ENTRY], api)
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
                        baseline.run(fixture.root, fixture.event(), [ENTRY], api)

    def test_complete_path_refuses_executable_formatter_without_side_effect(self):
        marker = Path(self.temp.name) / "must-not-exist"
        self.fixture.write(".markdownlint-cli2.cjs", "require('fs').writeFileSync(" + json.dumps(str(marker)) + ", 'executed'); module.exports={};\n")
        self.fixture.commit()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
            with self.assertRaisesRegex(ValueError, "undeclared"):
                baseline.run(self.fixture.root, self.fixture.event(), [ENTRY], FakeApi(self.fixture))
        self.assertFalse(marker.exists())

    def test_admitted_unicode_boundary_reaches_real_locked_lint(self):
        for number in range(12):
            self.fixture.write(f"docs/unicode-{number}.md", "# Unicode document\n\n" + "\U0001f331" * 125000 + "\n")
        self.fixture.commit()
        strings = baseline.admit_tree(self.fixture.root, self.fixture.head)
        self.assertLess(sum(len(text.encode("utf-8")) for text in strings.values()), 8 * 1024 * 1024)
        self.assertGreater(len(json.dumps(strings).encode()), 16 * 1024 * 1024)  # Discriminates the original transport defect.
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ENTRY["repository"], "GITHUB_REPOSITORY_ID": str(ENTRY["repository_id"])}):
            result = baseline.run(self.fixture.root, self.fixture.event(), [ENTRY], FakeApi(self.fixture))
        self.assertEqual(result["head"], self.fixture.head)

    def test_gitlink_is_not_a_document(self):
        (self.fixture.root / "docs/submodule.md").mkdir()
        self.fixture.git("update-index", "--add", "--cacheinfo", "160000," + self.fixture.head + ",docs/submodule.md")
        self.fixture.git("commit", "-q", "-m", "unsupported gitlink")
        self.fixture.head = self.fixture.git("rev-parse", "HEAD").strip()
        with self.assertRaises(ValueError):
            baseline.admit_tree(self.fixture.root, self.fixture.head)

    def test_cli_logs_only_public_subject_not_authenticated_result(self):
        event_path = Path(self.temp.name) / "event.json"
        event_path.write_text(json.dumps(self.fixture.event()))
        source_sha = "a" * 40
        canary = "TEST_ONLY_AUTH_RESULT_MUST_NOT_BE_LOGGED"
        original_git = baseline.git

        def fixture_source_git(root, *args, **kwargs):
            if root == baseline.SOURCE and args == ("rev-parse", "HEAD"):
                return (source_sha + "\n").encode()
            if root == baseline.SOURCE and args == ("status", "--porcelain", "--untracked-files=all"):
                return b""
            return original_git(root, *args, **kwargs)

        output = io.StringIO()

        def authenticated_side_effect(root, event, entries, api):
            event["pull_request"]["base"]["sha"] = canary
            return {"credential": canary}

        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request", "BASELINE_SOURCE_SHA": source_sha,
                                     "GITHUB_EVENT_PATH": str(event_path), "GITHUB_TOKEN": "fixture-credential"}), \
                patch.object(sys, "argv", ["baseline.py", "--consumer-root", str(self.fixture.root)]), \
                patch.object(baseline, "git", side_effect=fixture_source_git), \
                patch.object(baseline, "Api", return_value=object()), \
                patch.object(baseline, "run", side_effect=authenticated_side_effect) as authenticated, \
                patch.object(sys, "stdout", output):
            baseline.main()
        authenticated.assert_called_once()
        self.assertNotIn(canary, output.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["head"], self.fixture.head)
        self.assertEqual(result["source_sha"], source_sha)
        self.assertEqual(result["consumer"], ENTRY["repository"])


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
        for branch in ("dev", "main"):
            self.assertIs(baseline.select([ENTRY], ENTRY["repository"], ENTRY["repository_id"], branch), ENTRY)
        legacy = baseline.catalog({"schema_version": 1, "repositories": [{**ENTRY, "branches": ["dev"]}]})
        baseline.select(legacy, ENTRY["repository"], ENTRY["repository_id"], "dev")
        with self.assertRaisesRegex(ValueError, "unknown or changed"):
            baseline.select(legacy, ENTRY["repository"], ENTRY["repository_id"], "main")
        for branches in (None, [], "main", ["main"], ["dev", "dev"], ["dev", "*"],
                         ["dev", "main", "staging"], ["dev", True]):
            with self.subTest(branches=branches), self.assertRaisesRegex(ValueError, "branch selection"):
                baseline.catalog({"schema_version": 1, "repositories": [{**ENTRY, "branches": branches}]})
        missing = {key: value for key, value in ENTRY.items() if key != "branches"}
        with self.assertRaisesRegex(ValueError, "record fields"):
            baseline.catalog({"schema_version": 1, "repositories": [missing]})

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

    def topology(self, job):
        guard = re.fullmatch(r"github.repository != '([^']+)'", job["if"])
        naming = re.fullmatch(r"\$\{\{ github.repository == '([^']+)' && '([^']+)' \|\| '([^']+)' \}\}", job["name"])
        self.assertIsNotNone(guard)
        self.assertIsNotNone(naming)
        for repo, expected_run, expected_name in [("ForgingAlpha/.github", False, "Organization Baseline"),
                                                   (ENTRY["repository"], True, "CI"), ("ForgingAlpha/unknown", True, "Organization Baseline")]:
            self.assertEqual(repo != guard[1], expected_run)
            self.assertEqual(naming[2] if repo == naming[1] else naming[3], expected_name)

    def test_source_enrolled_unknown_outcomes_and_dangerous_skip_mutations(self):
        job = self.workflow["jobs"]["baseline"]
        self.topology(job)
        for mutation in ({"if": f"github.repository != '{ENTRY['repository']}'"},
                         {"name": "${{ github.repository == 'ForgingAlpha/.github' && 'CI' || 'Organization Baseline' }}"}):
            with self.assertRaises(AssertionError):
                self.topology({**job, **mutation})

    def test_real_inline_identity_parser_refuses_fallback_and_injection(self):
        script = self.workflow["jobs"]["baseline"]["steps"][0]["run"]
        valid = {"workflow_repository": "ForgingAlpha/.github", "workflow_sha": "b" * 40,
                 "workflow_ref": "ForgingAlpha/.github/.github/workflows/org-baseline.yml@refs/heads/main"}
        for change, expected in [({}, 0), ({"workflow_repository": "outside/repo"}, 1),
                                 ({"workflow_sha": "main"}, 1), ({"workflow_ref": "wrong/path@main"}, 1),
                                 ({"workflow_sha": "b" * 40 + "\noutput=bad"}, 1)]:
            with tempfile.TemporaryDirectory() as d:
                output = Path(d) / "output"
                value = subprocess.run(["bash", "-e", "-c", script], env={**os.environ, "JOB_CONTEXT": json.dumps({**valid, **change}), "GITHUB_OUTPUT": str(output)}, capture_output=True)
                self.assertEqual(value.returncode, expected, value.stderr.decode())
                if expected:
                    self.assertFalse(output.exists())
                else:
                    self.assertEqual(output.read_text(), "repository=ForgingAlpha/.github\nsha=" + "b" * 40 + "\n")

    def test_read_only_coherent_source_no_language_optout(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read", "pull-requests": "read"})
        self.assertEqual(set(self.workflow["on"]), {"pull_request"})
        steps = self.workflow["jobs"]["baseline"]["steps"]
        self.assertEqual(steps[1]["with"]["ref"], "${{ steps.source.outputs.sha }}")
        self.assertEqual(steps[2]["with"]["ref"], "${{ github.event.pull_request.head.sha }}")
        self.assertTrue(all(step["with"]["persist-credentials"] == "false" for step in steps if step.get("uses", "").startswith("actions/checkout@")))
        self.assertFalse(any("@v1" in str(step) for step in steps))


if __name__ == "__main__":
    unittest.main()
