import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_durable_evidence_references.py"
)


class DurableEvidenceReferenceValidatorTest(unittest.TestCase):
    def run_validator(self, *paths):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(path) for path in paths)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def git(self, repo, *args):
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
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

    def test_rejects_plan_citation_in_source_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lib" / "quota.ex"
            path.parent.mkdir(parents=True)
            path.write_text(
                textwrap.dedent(
                    """\
                    defmodule Quota do
                      # Guard used by docs/plans/quota-policy.md Phase 3.
                      def check, do: :ok
                    end
                    """
                ),
                encoding="utf-8",
            )

            result = self.run_validator(path)

        self.assertEqual(
            result.returncode,
            1,
            "durable source comments must reject plan and phase citations. "
            f"WHY: execution artifacts are not lasting source truth. "
            f"HOW: inspect forbidden_refs. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        for expected in ("WHAT:", "WHY:", "HOW:", "docs/plans/quota-policy.md", "Phase 3"):
            self.assertIn(
                expected,
                result.stderr,
                f"durable-reference failure must include {expected!r}. STDERR={result.stderr!r}",
            )

    def test_rejects_forbidden_artifact_families_in_docstrings_and_assertions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test" / "policy_test.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                textwrap.dedent(
                    '''\
                    def subject():
                        """Implements docs/handoffs/resume.md as durable authority."""
                        return True

                    def test_policy():
                        # Guard derived from docs/audits/2026-review.md.
                        assert subject(), "verified by PR #123"
                    '''
                ),
                encoding="utf-8",
            )

            result = self.run_validator(path)

        self.assertEqual(
            result.returncode,
            1,
            "durable docstrings, comments, and assertion messages must reject "
            "handoff, audit, and PR citations. WHY: execution artifacts cannot be "
            f"durable source truth. HOW: inspect scan_file context handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        for expected in ("docs/handoffs/resume.md", "docs/audits/2026-review.md", "PR #123"):
            self.assertIn(
                expected,
                result.stderr,
                f"durable-reference failure must report {expected!r}. STDERR={result.stderr!r}",
            )

    def test_ignores_execution_artifact_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [
                root / "docs" / "plans" / "example.py",
                root / "docs" / "handoffs" / "handoff.py",
                root / "docs" / "audits" / "audit.py",
                root / "docs" / "research" / "research.py",
            ]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# docs/plans/example.md Phase 4 PR #123\n", encoding="utf-8")

            result = self.run_validator(root)

        self.assertEqual(
            result.returncode,
            0,
            "execution-artifact directories may discuss plans, phases, audits, and PRs. "
            f"WHY: those docs are evidence artifacts, not durable code comments. "
            f"HOW: inspect IGNORED_PATH_SEQUENCES. STDOUT={result.stdout!r} "
            f"STDERR={result.stderr!r}",
        )

    def test_allows_domain_phase_language_without_plan_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lib" / "moon_phase.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                "def angle():\n    # Phase angle is a domain concept here.\n    return 0\n",
                encoding="utf-8",
            )

            result = self.run_validator(path)

        self.assertEqual(
            result.returncode,
            0,
            "ordinary domain phase wording must not fail without execution-artifact authority. "
            f"WHY: the validator targets plan authority, not the word phase alone. "
            f"HOW: inspect phase regex context. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_default_scan_uses_tracked_files_not_generated_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self.git(repo, "init", "-b", "main")
            self.git(repo, "config", "user.email", "tests@example.com")
            self.git(repo, "config", "user.name", "Tests")
            tracked = repo / "lib" / "safe.py"
            tracked.parent.mkdir(parents=True)
            tracked.write_text("def ok():\n    return True\n", encoding="utf-8")
            generated = repo / "node_modules" / "bad.py"
            generated.parent.mkdir(parents=True)
            generated.write_text("# Guard used by docs/plans/bad.md Phase 2.\n", encoding="utf-8")
            self.git(repo, "add", "lib/safe.py")
            self.git(repo, "commit", "-m", "tracked source")

            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(
            result.returncode,
            0,
            "default durable-reference scans must use tracked source files and avoid "
            "untracked generated/dependency directories. WHY: consumer repos can have "
            f"large generated trees. HOW: inspect iter_tracked_paths. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
