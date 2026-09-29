import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
ACTION_ROOT = ROOT / "actions" / "ci-markdown"
ACTION = ACTION_ROOT / "action.yml"
VALID = "# Heading\n"
INVALID = "# Heading\n\n### Skipped level\n"


class CiMarkdownTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = tempfile.TemporaryDirectory(prefix="markdown-tests-")
        cls.addClassCleanup(cls.state.cleanup)
        cls.state_root = Path(cls.state.name)
        cls.cache = Path(os.environ.get("MARKDOWN_TEST_CACHE", cls.state_root / "cache"))
        cls.install = cls.state_root / "warm"
        cls.install.mkdir()
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(ACTION_ROOT / name, cls.install / name)
        cls.base_env = dict(os.environ, npm_config_cache=str(cls.cache))
        result = subprocess.run(
            ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=cls.install, env=cls.base_env, capture_output=True, text=True, timeout=90,
        )
        if result.returncode:
            raise AssertionError(f"Required locked test tool installation failed: {result.stderr}")
        cls.base_env["npm_config_offline"] = "true"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="markdown-case-", dir=self.state_root)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.config = ".markdownlint-cli2.jsonc"
        self.configure()
        self.runner = self.root / "runner"
        self.runner.mkdir()

    def git(self, *args):
        return subprocess.run(["git", "--literal-pathspecs", *args], cwd=self.repo, check=True, capture_output=True)

    def configure(self, **options):
        (self.repo / self.config).write_text(
            json.dumps({"config": {"default": False, "MD001": True}, **options}), encoding="utf-8"
        )

    def file(self, name, content=VALID, tracked=True):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if tracked:
            self.git("add", "--", name)
        return path

    def fake_command(self, name, script):
        directory = self.root / "bin"
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text("#!/usr/bin/env python3\n" + script, encoding="utf-8")
        path.chmod(0o755)
        return directory

    def run_action(self, cwd=None, **overrides):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        code = "\n".join(step["run"] for step in action["runs"]["steps"] if "run" in step)
        env = dict(self.base_env, GITHUB_ACTION_PATH=str(ACTION_ROOT),
                   MARKDOWN_CONFIG_PATH=self.config, RUNNER_TEMP=str(self.runner))
        env.update(overrides)
        result = subprocess.run(["bash", "-c", code], cwd=cwd or self.repo, env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertFalse(list(self.runner.glob("ci-markdown-*")), "Action must clean its own installation")
        return result

    def assert_failure(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        for label in ("WHAT:", "WHY:", "HOW:"):
            self.assertIn(label, result.stderr + result.stdout)

    def test_action_contract_and_single_version_owner(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        self.assertEqual(set(action["inputs"]), {"config-path", "node-version"})
        self.assertRegex(action["runs"]["steps"][0]["uses"], r"^actions/setup-node@[0-9a-f]{40}$")
        run = action["runs"]["steps"][1]["run"]
        self.assertIn("scripts/lint_markdown.mjs", run)
        self.assertNotIn("npx", run)
        manifest = json.loads((ACTION_ROOT / "package.json").read_text())
        lock = json.loads((ACTION_ROOT / "package-lock.json").read_text())
        self.assertEqual(lock["packages"][""]["dependencies"], manifest["dependencies"])
        installed = json.loads((self.install / "node_modules/markdownlint-cli2/package.json").read_text())
        self.assertEqual(installed["version"], manifest["dependencies"]["markdownlint-cli2"])
        for name, package in lock["packages"].items():
            if name:
                self.assertRegex(package["integrity"], r"^sha512-[A-Za-z0-9+/]+={0,2}$", name)
                self.assertTrue(package["resolved"].startswith("https://registry.npmjs.org/"), name)

    def test_valid_tracked_inputs_exclude_untracked_invalid_file(self):
        self.file("README.md")
        self.file("untracked.md", INVALID, tracked=False)
        self.assertEqual(self.run_action().returncode, 0)

    def test_central_policy_has_no_incremental_exclusions(self):
        config = yaml.safe_load((ROOT / ".markdownlint-cli2.yaml").read_text())
        self.assertFalse(config.get("ignores"))

    def test_git_pathspec_environment_cannot_change_discovery(self):
        self.file("docs/bad.md", INVALID)
        self.file("docs/guide.markdown", INVALID)
        self.file("not-markdown.MD", INVALID)
        variables = ["GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
                     "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS"]
        for variable in variables:
            with self.subTest(variable=variable):
                result = self.run_action(**{variable: "1"})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                output = result.stdout + result.stderr
                for name in ("docs/bad.md", "docs/guide.markdown"):
                    self.assertRegex(output, rf"(?m)^{re.escape(name)}:3 error MD001/heading-increment\b")
                self.assertNotIn("not-markdown.MD:3 error", output)

    def test_invalid_tracked_input_fails(self):
        self.file("bad.md", INVALID)
        result = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad.md", result.stderr + result.stdout)
        self.assert_failure(result)

    def test_outside_git_is_not_successful_emptiness(self):
        outside = self.root / "outside"
        outside.mkdir()
        shutil.copyfile(self.repo / self.config, outside / self.config)
        self.assert_failure(self.run_action(cwd=outside))

    def test_git_failure_with_partial_output_fails(self):
        self.file("README.md")
        script = (
            "import os, sys\n"
            "if sys.argv[1] == 'ls-files':\n"
            "    sys.stdout.buffer.write(b'README.md\\0')\n"
            "    sys.exit(73)\n"
            f"os.execv({shutil.which('git')!r}, ['git', *sys.argv[1:]])\n"
        )
        directory = self.fake_command("git", script)
        self.assert_failure(self.run_action(PATH=f"{directory}:{self.base_env['PATH']}"))

    def test_empty_inventory_does_not_acquire_tool(self):
        script = "from pathlib import Path\nimport sys\nPath(" + repr(str(self.root / "called")) + ").touch()\nsys.exit(99)\n"
        directory = self.fake_command("npm", script)
        self.fake_command("npx", script)
        result = self.run_action(PATH=f"{directory}:{self.base_env['PATH']}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "called").exists())

    def test_missing_and_empty_config_fail(self):
        self.file("README.md")
        for value in ("", "absent.json"):
            with self.subTest(value=value):
                self.assert_failure(self.run_action(MARKDOWN_CONFIG_PATH=value))

    def test_invalid_config_fails_with_context(self):
        self.file("README.md")
        (self.repo / self.config).write_text("{ invalid JSON")
        self.assert_failure(self.run_action())

    def test_missing_indexed_file_fails_even_when_ignored(self):
        path = self.file("missing.md")
        path.unlink()
        self.configure(ignores=["missing.md"])
        self.assert_failure(self.run_action())

    def test_non_file_indexed_path_fails(self):
        path = self.file("directory.md")
        path.unlink()
        path.mkdir()
        self.assert_failure(self.run_action())

    @unittest.skipIf(os.geteuid() == 0, "root bypasses file permission checks")
    def test_unreadable_indexed_file_fails(self):
        path = self.file("unreadable.md")
        path.chmod(0)
        try:
            self.assert_failure(self.run_action())
        finally:
            path.chmod(0o600)

    def test_supported_literal_names_and_nested_segments_are_linted(self):
        names = ["(draft).md", "[ab].md", "!note.md", ":note.md", "#note.md", "-note.md",
                 "space name.md", "a*b.md", "a?b.md", "a+(b).md", "a$b.md", "a^b.md", "例.md",
                 "docs/(a)/b.md", "docs/[ab]/b.md", "docs/a*b/b.md", "docs/a?b/b.md",
                 "docs/space name/b.md", "docs/a?(b)/c.md", "docs/a*(b)/c.md",
                 "docs/guide.markdown", ".github/guide.md"]
        for name in names:
            self.file(name, INVALID)
        result = self.run_action()
        self.assertEqual(result.returncode, 1)
        output = result.stdout + result.stderr
        for name in names:
            self.assertRegex(output, rf"(?m)^{re.escape(name)}:3 error MD001/heading-increment\b",
                             f"Missing rule diagnostic for tracked input: {name}")

    def test_unsupported_names_fail_explicitly(self):
        names = ["a|b.md", "a{b}.md", "a!(b).md", "a@(b).md", "line\nname.md",
                 "line\rname.md", "a\\b.md", "docs/a+(b)/c.md"]
        for name in names:
            with self.subTest(name=name):
                path = self.file(name, INVALID)
                result = self.run_action()
                self.assert_failure(result)
                self.assertIn("Unsupported tracked Markdown path", result.stderr)
                self.git("rm", "--cached", "--", name)
                path.unlink()

    def test_utf8_bom_filename_is_not_replaced_by_untracked_collision(self):
        tracked = "\ufeffbad.md"
        self.file(tracked, INVALID)
        self.file("bad.md", VALID, tracked=False)
        result = self.run_action()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stderr, rf"(?m)^{re.escape(tracked)}:3 error MD001/heading-increment\b")

    def test_non_utf8_indexed_path_fails(self):
        name = b"invalid-\xff.md"
        full = os.fsencode(self.repo) + b"/" + name
        with open(full, "wb") as stream:
            stream.write(INVALID.encode())
        self.git("add", "--", name)
        self.assert_failure(self.run_action())

    def test_lint_ignores_are_preserved(self):
        self.file("ignored.md", INVALID)
        self.configure(ignores=["ignored.md"])
        self.assertEqual(self.run_action().returncode, 0)

    def test_gitignore_policy_is_preserved_for_tracked_files(self):
        self.file("ignored.md", INVALID)
        self.file(".gitignore", "ignored.md\n")
        self.configure(gitignore=True)
        self.assertEqual(self.run_action().returncode, 0)

    def test_ignore_files_policy_is_preserved(self):
        self.file("ignored.md", INVALID)
        self.file(".lintignore", "ignored.md\n")
        self.configure(gitignore=".lintignore")
        self.assertEqual(self.run_action().returncode, 0)

    def test_config_can_add_untracked_inputs(self):
        self.file("README.md")
        self.file("untracked.md", INVALID, tracked=False)
        self.configure(globs=["untracked.md"])
        self.assertEqual(self.run_action().returncode, 1)

    def test_nested_configuration_is_preserved(self):
        self.file("docs/bad.md", INVALID)
        self.file("docs/.markdownlint-cli2.jsonc", json.dumps({"config": {"MD001": False}}))
        self.assertEqual(self.run_action().returncode, 0)

    def test_consumer_local_package_and_binary_do_not_select_tool(self):
        self.file("bad.md", INVALID)
        self.file("node_modules/markdownlint-cli2/package.json", json.dumps({
            "name": "markdownlint-cli2", "version": "99.0.0", "main": "index.js"}), tracked=False)
        self.file("node_modules/markdownlint-cli2/index.js", "throw new Error('consumer shadow');", tracked=False)
        directory = self.fake_command("npx", "import sys\nsys.exit(0)\n")
        result = self.run_action(PATH=f"{directory}:{self.base_env['PATH']}")
        self.assertEqual(result.returncode, 1)
        self.assertIn("MD001", result.stderr + result.stdout)
        self.assertNotIn("consumer shadow", result.stderr + result.stdout)

    def test_one_formatter_invocation(self):
        self.file("one.md")
        self.file("two.md")
        self.file("formatter.cjs", "module.exports = () => require('node:fs').appendFileSync('formatter-count', 'x');\n")
        self.configure(outputFormatters=[["./formatter.cjs"]])
        self.assertEqual(self.run_action().returncode, 0)
        self.assertEqual((self.repo / "formatter-count").read_text(), "x")

    def test_large_inventory_and_last_file_failure(self):
        names = []
        for number in range(1000):
            name = f"docs/{number:04d}-" + "long-name-" * 15 + ".md"
            self.file(name, tracked=False)
            names.append(name)
        self.git("add", "--", "docs")
        self.assertGreater(len(" ".join(names).encode()), 131072)
        self.assertEqual(self.run_action().returncode, 0)
        self.file(names[-1], INVALID)
        result = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertIn(names[-1], result.stderr + result.stdout)

    def test_non_numeric_linter_result_fails_closed(self):
        self.file("README.md")
        script = (
            "import sys, shutil\nfrom pathlib import Path\n"
            "prefix = Path(sys.argv[sys.argv.index('--prefix') + 1])\n"
            f"shutil.copytree({str(self.install / 'node_modules')!r}, prefix / 'node_modules')\n"
            "(prefix / 'node_modules/markdownlint-cli2/markdownlint-cli2.mjs').write_text('export async function main() { return undefined; }')\n"
        )
        directory = self.fake_command("npm", script)
        result = self.run_action(PATH=f"{directory}:{self.base_env['PATH']}")
        self.assert_failure(result)
        self.assertIn("invalid exit status", result.stderr)

    def test_failed_install_cannot_become_lint_success(self):
        self.file("README.md")
        directory = self.fake_command("npm", "import sys\nsys.exit(17)\n")
        self.assert_failure(self.run_action(PATH=f"{directory}:{self.base_env['PATH']}"))


if __name__ == "__main__":
    unittest.main()
