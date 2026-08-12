import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_codeowners_contract.py"
)
ACTION = Path(__file__).resolve().parents[1] / "action.yml"


class CodeownersContractValidatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "tests@example.com")
        self.git("config", "user.name", "Tests")
        self.git("remote", "add", "origin", "git@github.com:ForgingAlpha/example.git")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"fixture git command must pass: git {' '.join(args)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        return result

    def write(self, relative_path, content):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_validator(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def assert_contract_failure(self, result, *fragments):
        self.assertNotEqual(
            result.returncode,
            0,
            "invalid CODEOWNERS contract must fail. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        for fragment in ("WHAT:", "WHY:", "HOW:", *fragments):
            self.assertIn(
                fragment,
                result.stderr,
                f"CODEOWNERS failure must include {fragment!r}. "
                f"STDERR={result.stderr!r}",
            )

    def test_missing_codeowners_fails_closed(self):
        result = self.run_validator()

        self.assert_contract_failure(result, ".github/CODEOWNERS", "missing")

    def test_valid_minimum_contract_passes(self):
        self.write(
            ".github/CODEOWNERS",
            textwrap.dedent(
                """\
                # Alpha Apps required human ownership. Keep this block last.
                /.github/ @leosmigel
                """
            ),
        )

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "a valid self-owning CODEOWNERS contract must pass. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "CODEOWNERS contract validation passed",
            result.stdout,
            f"success output must name the passed contract. STDOUT={result.stdout!r}",
        )

    def test_required_owner_must_be_authorized_human(self):
        self.write(".github/CODEOWNERS", "/.github/ @forgingalpha-bot\n")

        result = self.run_validator()

        self.assert_contract_failure(result, "authorized human", "/.github/")

    def test_required_entry_rejects_mixed_human_and_bot_owners(self):
        self.write(
            ".github/CODEOWNERS",
            "/.github/ @leosmigel @forgingalpha-bot\n",
        )

        result = self.run_validator()

        self.assert_contract_failure(
            result,
            "non-authorized owner",
            "@forgingalpha-bot",
        )

    def test_required_entry_must_be_in_final_active_block(self):
        self.write(
            ".github/CODEOWNERS",
            "/.github/ @leosmigel\n* @forgingalpha-bot\n",
        )

        result = self.run_validator()

        self.assert_contract_failure(result, "final active block", "/.github/")

    def test_malformed_active_line_fails(self):
        self.write(".github/CODEOWNERS", "/.github/\n")

        result = self.run_validator()

        self.assert_contract_failure(result, "line 1", "owner")

    def test_detected_production_control_file_requires_ownership(self):
        self.write("wrangler.jsonc", "{}\n")
        self.write(".github/CODEOWNERS", "/.github/ @leosmigel\n")

        result = self.run_validator()

        self.assert_contract_failure(result, "/wrangler.jsonc", "production-control")

    def test_detected_production_control_file_passes_in_required_block(self):
        self.write("wrangler.jsonc", "{}\n")
        self.write(
            ".github/CODEOWNERS",
            "/.github/ @leosmigel\n/wrangler.jsonc @leosmigel\n",
        )

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "a detected production-control file with authorized ownership must pass. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_wrangler_toml_is_a_production_control_file(self):
        self.write("wrangler.toml", "name = 'example'\n")
        self.write(".github/CODEOWNERS", "/.github/ @leosmigel\n")

        result = self.run_validator()

        self.assert_contract_failure(result, "/wrangler.toml", "production-control")

    def test_codeowners_at_github_size_limit_fails_closed(self):
        prefix = "/.github/ @leosmigel\n"
        padding = "#" * (3_000_000 - len(prefix.encode("utf-8")))
        self.write(".github/CODEOWNERS", prefix + padding)

        result = self.run_validator()

        self.assert_contract_failure(result, "not smaller than 3 MB")

    def test_control_plane_repo_requires_complete_tree_ownership(self):
        self.git("remote", "set-url", "origin", "git@github.com:ForgingAlpha/.github.git")
        for path in (
            "actions/example/action.yml",
            "workflow-templates/example.yml",
            "templates/example.txt",
            "docs/intent.md",
            "docs/requirements.md",
            "docs/architecture.md",
        ):
            self.write(path, "fixture\n")
        self.write(
            ".github/CODEOWNERS",
            "* @leosmigel\n",
        )

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "the central .github repository's complete required ownership block must pass. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_control_plane_repo_rejects_partial_ownership(self):
        self.git("remote", "set-url", "origin", "git@github.com:ForgingAlpha/.github.git")
        self.write(
            ".github/CODEOWNERS",
            "/.github/ @leosmigel\n/actions/ @leosmigel\n",
        )

        result = self.run_validator()

        self.assert_contract_failure(result, "missing", "*")

    def test_shared_policy_action_invokes_validator(self):
        action = ACTION.read_text(encoding="utf-8")

        self.assertIn(
            'python3 "$GITHUB_ACTION_PATH/scripts/validate_codeowners_contract.py"',
            action,
            "the published policy action must invoke the CODEOWNERS validator",
        )


if __name__ == "__main__":
    unittest.main()
