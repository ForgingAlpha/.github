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

    def run_validator(self, *, auto_base=False, python_flags=(), **overrides):
        env = os.environ.copy()
        env["ALPHAAPPS_POLICY_BASE_REF"] = "auto" if auto_base else "main"
        env.update(overrides)
        return subprocess.run(
            [sys.executable, *python_flags, str(SCRIPT)],
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

    def test_approved_baseline_allows_source_truth_and_plan_changes(self):
        self.start_feature_with_approved_baseline()
        self.write("docs/intent.md", self.approved_doc("Updated Intent"))
        self.write("docs/requirements.md", self.approved_doc("Updated Requirements"))
        self.write("docs/architecture.md", self.approved_doc("Updated Architecture"))
        self.write("docs/plans/refactor.md", "# Refactor plan\n")
        self.commit_all("update approved source truth")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "approved source-truth and plan changes must pass without a separate "
            "review receipt. WHY: PR review and required CI govern source-truth "
            "changes; this validator owns only the approved baseline contract. "
            "HOW: remove per-change receipt enforcement from the source-truth "
            f"validator. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
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
            "mirror the canonical leading-comment contract. HOW: inspect "
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

    def test_incomplete_baseline_classifies_both_rename_endpoints(self):
        for source, allowed in (("lib/example.py", False), ("docs/architecture/original.md", True)):
            with self.subTest(source=source):
                self.git("switch", "main")
                self.write(source, "unchanged source body\n")
                self.commit_all("seed rename source")
                self.git("branch", "-D", "feature")
                self.git("switch", "-c", "feature")
                target = self.repo / "docs/architecture/example.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                self.git("mv", source, str(target))
                self.commit_all("rename with incomplete baseline")
                self.assertIn(f"R100\t{source}\tdocs/architecture/example.md", self.git("diff", "--name-status", "main..HEAD").stdout)
                result = self.run_validator()
                self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)

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


    def test_yaml_comments_and_quoted_status_are_valid(self):
        self.start_feature_with_approved_baseline()
        for value in ('approved # reviewed', '"approved" # reviewed', "'approved'"):
            with self.subTest(value=value):
                self.write("docs/intent.md", f"---\nstatus: {value}\ntags: [org/alpha-apps]\n---\n# Intent\n")
                result = self.run_validator()
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_duplicate_and_non_scalar_yaml_fail_closed(self):
        self.start_feature_with_approved_baseline()
        for metadata in (
            'status: "approved', 'status: approved\nstatus: approved',
            'status: [approved]', 'status: null', 'status: true',
            'status: approved\ntags: [unterminated', '- status: approved',
            'status: approved\nnested: {one: 1, one: 2}',
        ):
            with self.subTest(metadata=metadata):
                self.write("docs/intent.md", f"---\n{metadata}\n---\n# Intent\n")
                result = self.run_validator()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("WHAT:", result.stderr)

    def test_indented_yaml_scalar_delimiter_does_not_end_frontmatter(self):
        self.start_feature_with_approved_baseline()
        for metadata, allowed in (
            ("note: |\n  ---\nstatus: approved", True),
            ("status: approved\nnote: |\n  ---\nstatus: provisional", False),
        ):
            with self.subTest(metadata=metadata):
                self.write("docs/intent.md", f"---\n{metadata}\n---\n# Intent\n")
                result = self.run_validator()
                self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)

    def test_missing_yaml_runtime_fails_with_prerequisite(self):
        self.start_feature_with_approved_baseline()
        result = self.run_validator(python_flags=("-S",))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PyYAML is unavailable", result.stderr)
        self.assertIn("provision Python 3 with PyYAML", result.stderr)

    def write_marker_free_baseline(self):
        for name in ("intent", "requirements", "architecture"):
            self.write(f"docs/{name}.md", f"---\nid: control://alphaapps/governance/{name}\ntags: [org/alpha-apps]\n---\n# {name}\n")

    def test_canonical_origin_uses_main_without_status_promotion(self):
        self.git("remote", "set-url", "origin", "git@github.com:ForgingAlpha/control-plane.git")
        self.write_marker_free_baseline()
        self.write("system/current.txt", "ordinary work\n")
        self.commit_all("canonical candidate")
        result = self.run_validator(auto_base=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BASE_REF=main", result.stdout)
        self.assertIn("approval and Currentness are separate", result.stdout)

    def test_status_exception_cannot_be_selected_by_repo_kind_or_misleading_origin(self):
        self.write_marker_free_baseline()
        self.write("lib/example.py", "ordinary work\n")
        self.commit_all("ordinary marker-free candidate")
        for remote in (
            "git@github.com:ForgingAlpha/example.git",
            "git@github.com:ForgingAlpha/.github.git",
            "https://evil.example/github.com/ForgingAlpha/control-plane",
        ):
            with self.subTest(remote=remote):
                self.git("remote", "set-url", "origin", remote)
                result = self.run_validator(ALPHAAPPS_POLICY_REPO_KIND="control-plane")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing status", result.stderr)

    def test_canonical_exception_preserves_yaml_and_optional_status_validation(self):
        self.git("remote", "set-url", "origin", "https://github.com/ForgingAlpha/control-plane.git")
        self.write_marker_free_baseline()
        self.write("system/current.txt", "ordinary work\n")
        self.commit_all("canonical candidate")
        for metadata in ('id: x\nid: x', 'status: invented', 'status: null', 'status: "approved', 'status: provisional'):
            with self.subTest(metadata=metadata):
                self.write("docs/intent.md", f"---\n{metadata}\n---\n# Intent\n")
                self.assertNotEqual(self.run_validator().returncode, 0)

    def test_type_change_is_not_definition_only_work(self):
        self.git("switch", "main")
        (self.repo / "lib").mkdir()
        (self.repo / "lib/current.py").symlink_to("../README.md")
        self.commit_all("base symlink")
        self.git("branch", "-D", "feature")
        self.git("switch", "-c", "feature")
        (self.repo / "lib/current.py").unlink()
        self.write("lib/current.py", "base\n")
        self.write("docs/intent.md", self.approved_doc("Intent"))
        self.commit_all("definition plus ordinary type change")
        self.assertIn("T\tlib/current.py", self.git("diff", "--name-status", "main..HEAD").stdout)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lib/current.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
