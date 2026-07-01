import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-markdown" / "action.yml"
SCRIPT = ROOT / "actions" / "ci-markdown" / "scripts" / "changed_markdown.sh"


class CiMarkdownTest(unittest.TestCase):
    def run_git(self, *args, cwd):
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def make_repo(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name)
        self.run_git("init", "-b", "main", cwd=path)
        self.run_git("config", "user.email", "test@example.invalid", cwd=path)
        self.run_git("config", "user.name", "Test", cwd=path)
        (path / "README.md").write_text("# Readme\n", encoding="utf-8")
        (path / "notes.txt").write_text("plain\n", encoding="utf-8")
        self.run_git("add", ".", cwd=path)
        self.run_git("commit", "-m", "initial", cwd=path)
        self.run_git("checkout", "-b", "feature", cwd=path)
        return tmp, path

    def test_action_pins_markdownlint_cli2(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        run_blocks = "\n".join(
            step.get("run", "")
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        )

        self.assertIn(
            "npx --yes markdownlint-cli2@0.22.1",
            run_blocks,
            "ci-markdown must run the pinned markdownlint-cli2 version. "
            "WHY: org-wide Markdown linting needs reproducible tool behavior. "
            "HOW: update the action run block and paired tests together.",
        )

    def test_action_sets_up_node_before_npx(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        steps = action["runs"]["steps"]

        self.assertEqual(
            action["inputs"]["node-version"]["default"],
            "24",
            "ci-markdown must declare the shared Node version input default. "
            "WHY: Node-based shared actions should not depend on ambient runner Node state. "
            "HOW: restore the node-version input default in action.yml.",
        )
        self.assertEqual(
            steps[0]["uses"],
            "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",
            "ci-markdown must set up Node with the existing pinned setup-node action. "
            "WHY: local Node-based CI actions establish Node before running npx/npm tools. "
            "HOW: restore the Setup Node.js step before Markdown linting.",
        )
        self.assertIn(
            "npx --yes markdownlint-cli2@0.22.1",
            steps[1]["run"],
            "ci-markdown must run npx only after the setup-node step. "
            "WHY: reproducible Markdown linting should use the declared Node runtime. "
            "HOW: keep the Run Markdown lint step after Setup Node.js.",
        )

    def test_action_defaults_to_changed_mode(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))

        self.assertEqual(
            action["inputs"]["mode"]["default"],
            "changed",
            "ci-markdown mode must default to changed. "
            "WHY: legacy repos may need incremental cleanup before all-file linting. "
            "HOW: update action.yml inputs if the rollout policy changes.",
        )

    def test_action_all_mode_uses_tracked_file_helper(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        run_blocks = "\n".join(
            step.get("run", "")
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        )

        self.assertIn(
            'changed_markdown.sh" --all',
            run_blocks,
            "ci-markdown all mode must enumerate tracked Markdown files through the helper. "
            "WHY: all-mode linting should avoid generated and dependency directories. "
            "HOW: restore the --all helper call before invoking markdownlint-cli2.",
        )

    def test_action_missing_config_fails_closed(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        run_blocks = "\n".join(
            step.get("run", "")
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        )

        self.assertIn(
            '[ ! -f "${MARKDOWN_CONFIG_PATH}" ]',
            run_blocks,
            "ci-markdown must fail when the configured Markdown policy file is missing. "
            "WHY: shared linting should not silently run without repo-owned policy. "
            "HOW: restore the config-path existence check in action.yml.",
        )
        self.assertIn(
            "Markdown config",
            run_blocks,
            "ci-markdown missing-config failure must identify the missing config. "
            "WHY: operators need a concrete file path to repair. HOW: keep the WHAT/WHY/HOW diagnostic block.",
        )

    def test_changed_markdown_lists_only_changed_markdown(self):
        tmp, repo = self.make_repo()
        self.addCleanup(tmp.cleanup)
        (repo / "README.md").write_text("# Readme\n\nChanged\n", encoding="utf-8")
        (repo / "script.py").write_text("print('ignored')\n", encoding="utf-8")
        self.run_git("add", ".", cwd=repo)
        self.run_git("commit", "-m", "change docs", cwd=repo)

        result = subprocess.run(
            [str(SCRIPT)],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "MARKDOWN_BASE_REF": "main"},
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["README.md"],
            "changed_markdown.sh must emit only changed Markdown paths. "
            "WHY: changed mode should avoid linting unrelated legacy files. "
            f"HOW: inspect git diff filtering; stdout={result.stdout!r}, stderr={result.stderr!r}",
        )

    def test_changed_markdown_honors_ignore_prefixes(self):
        tmp, repo = self.make_repo()
        self.addCleanup(tmp.cleanup)
        docs_dir = repo / "docs" / "drafts"
        docs_dir.mkdir(parents=True)
        (docs_dir / "note.md").write_text("# Draft\n", encoding="utf-8")
        (repo / "README.md").write_text("# Readme\n\nChanged\n", encoding="utf-8")
        self.run_git("add", ".", cwd=repo)
        self.run_git("commit", "-m", "change docs", cwd=repo)

        result = subprocess.run(
            [str(SCRIPT)],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "MARKDOWN_BASE_REF": "main",
                "MARKDOWN_IGNORE": "docs/drafts/\n",
            },
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["README.md"],
            "changed_markdown.sh must skip ignored prefixes. "
            "WHY: repos need explicit transitional ignores without hiding the lint action. "
            f"HOW: inspect MARKDOWN_IGNORE prefix handling; stdout={result.stdout!r}",
        )

    def test_changed_markdown_outputs_nothing_for_clean_branch(self):
        tmp, repo = self.make_repo()
        self.addCleanup(tmp.cleanup)

        result = subprocess.run(
            [str(SCRIPT)],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "MARKDOWN_BASE_REF": "main"},
        )

        self.assertEqual(
            result.stdout,
            "",
            "changed_markdown.sh must emit no files when HEAD has no Markdown changes from base. "
            "WHY: changed mode should skip clean legacy repos without false lint failures. "
            f"HOW: inspect git diff handling; stdout={result.stdout!r}, stderr={result.stderr!r}",
        )

    def test_all_markdown_lists_only_tracked_markdown(self):
        tmp, repo = self.make_repo()
        self.addCleanup(tmp.cleanup)
        (repo / "docs").mkdir()
        (repo / "docs" / "guide.markdown").write_text("# Guide\n", encoding="utf-8")
        (repo / "node_modules").mkdir()
        (repo / "node_modules" / "generated.md").write_text("# Generated\n", encoding="utf-8")
        self.run_git("add", "docs/guide.markdown", cwd=repo)
        self.run_git("commit", "-m", "add guide", cwd=repo)

        result = subprocess.run(
            [str(SCRIPT), "--all"],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "MARKDOWN_IGNORE": ""},
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["README.md", "docs/guide.markdown"],
            "changed_markdown.sh --all must emit only tracked Markdown files. "
            "WHY: all-mode linting should not traverse generated dependency trees. "
            f"HOW: inspect git ls-files handling; stdout={result.stdout!r}, stderr={result.stderr!r}",
        )

    def test_changed_markdown_missing_base_fails_with_how(self):
        tmp, repo = self.make_repo()
        self.addCleanup(tmp.cleanup)

        result = subprocess.run(
            [str(SCRIPT)],
            cwd=repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "MARKDOWN_BASE_REF": "missing"},
        )

        self.assertNotEqual(
            result.returncode,
            0,
            "changed_markdown.sh must fail when the requested base ref is missing. "
            "WHY: changed mode without a base silently under-checks files. "
            "HOW: inspect base-ref validation.",
        )
        self.assertIn(
            "HOW:",
            result.stderr,
            "changed_markdown.sh missing-base diagnostics must include HOW. "
            f"WHY: agents need direct remediation guidance. stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
