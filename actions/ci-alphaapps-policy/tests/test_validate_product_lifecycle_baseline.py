import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_product_lifecycle_baseline.py"
)


class ProductLifecycleBaselineValidatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "tests@example.com")
        self.git("config", "user.name", "Tests")
        self.git("remote", "add", "origin", "git@github.com:ForgingAlpha/example.git")
        self.write("README.md", "base\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "base")
        self.git("switch", "-c", "feature")

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

    def approved_doc(self, title):
        return textwrap.dedent(
            f"""\
            ---
            status: approved
            ---

            # {title}
            """
        )

    def approved_doc_with_leading_comment(self, title):
        return textwrap.dedent(
            f"""\
            <!-- public metadata comment -->

            ---
            status: approved
            ---

            # {title}
            """
        )

    def provisional_doc(self, title):
        return textwrap.dedent(
            f"""\
            ---
            status: provisional
            ---

            # {title}
            """
        )

    def write_approved_baseline(self):
        self.write("docs/intent.md", self.approved_doc("Intent"))
        self.write("docs/requirements.md", self.approved_doc("Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Architecture"))

    def start_feature_with_approved_baseline(self):
        self.git("switch", "main")
        self.write_approved_baseline()
        self.commit_all("approved baseline")
        self.git("branch", "-D", "feature")
        self.git("switch", "-c", "feature")

    def commit_all(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)

    def run_validator(self):
        env = os.environ.copy()
        env["ALPHAAPPS_POLICY_BASE_REF"] = "main"
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_approved_baseline_allows_ordinary_change(self):
        self.start_feature_with_approved_baseline()
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("ordinary change")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "approved source-truth baseline must allow ordinary implementation work. "
            f"WHY: the policy gate is satisfied once intent, requirements, and architecture "
            f"are approved. HOW: inspect validator baseline status handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_approved_baseline_allows_leading_html_comment_before_frontmatter(self):
        self.git("switch", "main")
        self.write("docs/intent.md", self.approved_doc_with_leading_comment("Intent"))
        self.write("docs/requirements.md", self.approved_doc("Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Architecture"))
        self.commit_all("approved baseline with comment")
        self.git("branch", "-D", "feature")
        self.git("switch", "-c", "feature")
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("ordinary change")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "baseline frontmatter parsing must allow the canonical leading HTML "
            "comment pattern before YAML frontmatter. WHY: the public validator must "
            "mirror the approved alphaapps-docs helper contract. HOW: inspect "
            f"read_frontmatter. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_missing_baseline_blocks_ordinary_change(self):
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("ordinary change")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "missing source-truth baseline must block ordinary code changes. "
            f"WHY: active ForgingAlpha repos require approved baseline docs before "
            f"implementation. HOW: inspect incomplete baseline handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        for expected in ("WHAT:", "WHY:", "HOW:", "blocked paths"):
            self.assertIn(
                expected,
                result.stderr,
                f"baseline failure output must include {expected!r}. STDERR={result.stderr!r}",
            )

    def test_missing_baseline_allows_definition_only_change(self):
        self.write("docs/intent.md", self.approved_doc("Intent"))
        self.commit_all("definition only")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "missing baseline must allow source-truth backfill changes only. "
            f"WHY: agents need a path to create missing definition docs. "
            f"HOW: inspect definition_only_path handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_provisional_baseline_blocks_ordinary_change(self):
        self.write("docs/intent.md", self.provisional_doc("Intent"))
        self.write("docs/requirements.md", self.approved_doc("Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Architecture"))
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("provisional baseline")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "provisional baseline must block ordinary implementation changes. "
            f"WHY: provisional source truth still needs operator approval. "
            f"HOW: inspect incomplete baseline status handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "provisional",
            result.stderr,
            f"provisional baseline failure must name the provisional status. STDERR={result.stderr!r}",
        )

    def test_malformed_baseline_blocks_ordinary_change(self):
        self.write("docs/intent.md", "# Intent without frontmatter\n")
        self.write("docs/requirements.md", self.approved_doc("Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Architecture"))
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("malformed baseline")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "malformed baseline source truth must block ordinary implementation changes. "
            f"WHY: missing or malformed status frontmatter means the baseline is not approved. "
            f"HOW: inspect read_frontmatter and incomplete baseline handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        for expected in ("WHAT:", "WHY:", "HOW:", "missing YAML frontmatter"):
            self.assertIn(
                expected,
                result.stderr,
                f"malformed baseline failure must include {expected!r}. STDERR={result.stderr!r}",
            )

    def test_unsupported_sensitive_status_is_redacted(self):
        self.write(
            "docs/intent.md",
            textwrap.dedent(
                """\
                ---
                status: sk-secret-token-example
                ---

                # Intent
                """
            ),
        )
        self.write("docs/requirements.md", self.approved_doc("Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Architecture"))
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("sensitive unsupported status")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "unsupported sensitive baseline status must fail without echoing the "
            "sensitive-looking value. WHY: diagnostics should not leak token-shaped "
            f"frontmatter. HOW: inspect diagnostic_status_value. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "[redacted-sensitive-status]",
            result.stderr,
            f"sensitive unsupported status must be redacted. STDERR={result.stderr!r}",
        )
        self.assertNotIn(
            "sk-secret-token-example",
            result.stderr,
            f"sensitive unsupported status must not be printed. STDERR={result.stderr!r}",
        )

    def test_invalid_baseline_status_blocks_definition_only_change(self):
        self.write(
            "docs/intent.md",
            textwrap.dedent(
                """\
                ---
                status: draft
                ---

                # Intent
                """
            ),
        )
        self.write("docs/requirements.md", self.approved_doc("Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Architecture"))
        self.write("docs/glossary.md", "# Glossary\n")
        self.commit_all("invalid baseline with definition change")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "invalid baseline status must fail closed even for definition-only changes. "
            f"WHY: the repair lane allows missing files, not malformed or unsupported "
            f"baseline status values. HOW: inspect definition_only_work_allowed. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "unsupported status",
            result.stderr,
            f"invalid status failure must report unsupported status. STDERR={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
