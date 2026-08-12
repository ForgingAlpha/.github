import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-markdown" / "action.yml"
CONFIG = ROOT / ".markdownlint-cli2.yaml"
SCRIPT = ROOT / "actions" / "ci-markdown" / "scripts" / "tracked_markdown.sh"


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
        return tmp, path

    def load_action(self):
        return yaml.safe_load(ACTION.read_text(encoding="utf-8"))

    def run_blocks(self):
        return "\n".join(
            step.get("run", "")
            for step in self.load_action()["runs"]["steps"]
            if isinstance(step, dict)
        )

    def test_action_has_one_full_repository_contract(self):
        action = self.load_action()
        run_blocks = self.run_blocks()
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

        self.assertNotIn("mode", action["inputs"])
        self.assertNotIn("base-ref", action["inputs"])
        self.assertNotIn("ignore", action["inputs"])
        self.assertIn('scripts/tracked_markdown.sh"', run_blocks)
        self.assertNotIn("changed_markdown", run_blocks)
        self.assertNotIn("MARKDOWN_BASE_REF", run_blocks)
        self.assertNotIn("ignores", config)

    def test_action_pins_node_and_markdownlint_cli2(self):
        action = self.load_action()
        steps = action["runs"]["steps"]

        self.assertEqual(action["inputs"]["node-version"]["default"], "24")
        self.assertEqual(
            steps[0]["uses"],
            "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
        )
        self.assertIn("npx --yes markdownlint-cli2@0.22.1", steps[1]["run"])

    def test_action_missing_config_fails_closed(self):
        run_blocks = self.run_blocks()

        self.assertIn('[ ! -f "${MARKDOWN_CONFIG_PATH}" ]', run_blocks)
        self.assertIn("Markdown config", run_blocks)
        self.assertIn("WHAT:", run_blocks)
        self.assertIn("WHY:", run_blocks)
        self.assertIn("HOW:", run_blocks)

    def test_helper_lists_only_tracked_markdown(self):
        tmp, repo = self.make_repo()
        self.addCleanup(tmp.cleanup)
        (repo / "docs").mkdir()
        (repo / "docs" / "guide.markdown").write_text("# Guide\n", encoding="utf-8")
        (repo / "node_modules").mkdir()
        (repo / "node_modules" / "generated.md").write_text("# Generated\n", encoding="utf-8")
        self.run_git("add", "docs/guide.markdown", cwd=repo)
        self.run_git("commit", "-m", "add guide", cwd=repo)

        result = subprocess.run(
            [str(SCRIPT)],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )

        self.assertEqual(result.stdout.splitlines(), ["README.md", "docs/guide.markdown"])

    def test_helper_fails_outside_git_with_actionable_output(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        result = subprocess.run(
            [str(SCRIPT)],
            cwd=tmp.name,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("WHAT:", result.stderr)
        self.assertIn("WHY:", result.stderr)
        self.assertIn("HOW:", result.stderr)


if __name__ == "__main__":
    unittest.main()
