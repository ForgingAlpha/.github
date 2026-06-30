import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_product_evidence.py"
ACTION_YML = Path(__file__).resolve().parents[1] / "action.yml"


class ProductEvidenceValidatorTest(unittest.TestCase):
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

    def valid_manifest(self):
        return {
            "schema_version": 1,
            "promises": [
                {
                    "id": "REQ-001",
                    "source_ref": "docs/requirements.md#REQ-001",
                    "title": "Example promise",
                    "type": "technical/architecture",
                    "status": "covered",
                    "evidence": [
                        {
                            "ref": "path:tests/example_test.py",
                            "kind": "auto",
                            "summary": "Exercises the example promise.",
                        }
                    ],
                }
            ],
        }

    def write_manifest(self, manifest):
        self.write("tests/example_test.py", "def test_example():\n    assert True\n")
        self.write(
            "docs/evidence/product-evidence.json",
            json.dumps(manifest, indent=2) + "\n",
        )

    def start_feature_with_product_evidence(self):
        self.git("switch", "main")
        self.write_manifest(self.valid_manifest())
        self.commit_all("required product evidence")
        self.git("branch", "-D", "feature")
        self.git("switch", "-c", "feature")

    def test_missing_manifest_blocks_ordinary_change(self):
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("ordinary change")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "missing Product Evidence must block ordinary implementation changes. "
            f"WHY: active ForgingAlpha repos require product-evidence.json by default. "
            f"HOW: inspect validate_required_presence. STDOUT={result.stdout!r} "
            f"STDERR={result.stderr!r}",
        )
        for expected in ("WHAT:", "WHY:", "HOW:", "Missing Product Evidence manifest"):
            self.assertIn(
                expected,
                result.stderr,
                f"missing-manifest failure must include {expected!r}. STDERR={result.stderr!r}",
            )

    def test_missing_manifest_allows_source_truth_backfill(self):
        self.write(
            "docs/intent.md",
            textwrap.dedent(
                """\
                ---
                status: approved
                ---

                # Intent
                """
            ),
        )
        self.commit_all("source truth backfill")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "missing Product Evidence must allow source-truth backfill only. "
            f"WHY: agents need a repair path to create required baselines. "
            f"HOW: inspect is_backfill_only_path. STDOUT={result.stdout!r} "
            f"STDERR={result.stderr!r}",
        )

    def test_missing_manifest_allows_evidence_backfill_creation(self):
        self.write_manifest(self.valid_manifest())
        self.commit_all("evidence backfill")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "missing Product Evidence must allow creating or repairing Product Evidence "
            "artifacts. WHY: evidence backfill is the required repair lane when the "
            f"manifest is absent. HOW: inspect is_backfill_only_path. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_valid_manifest_allows_ordinary_change(self):
        self.start_feature_with_product_evidence()
        self.write("lib/example.py", "VALUE = 1\n")
        self.commit_all("ordinary change")

        result = self.run_validator()

        self.assertEqual(
            result.returncode,
            0,
            "valid Product Evidence manifest must allow ordinary work. "
            f"WHY: required evidence is present and valid before the implementation diff. "
            f"HOW: inspect validate_manifest and required presence handling. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )

    def test_malformed_manifest_fails(self):
        self.write("docs/evidence/product-evidence.json", "{not json\n")
        self.commit_all("malformed evidence")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "malformed Product Evidence manifest must fail. "
            f"WHY: evidence status cannot be trusted if JSON parsing fails. "
            f"HOW: inspect load_manifest. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "not valid JSON",
            result.stderr,
            f"malformed manifest failure must name JSON parsing. STDERR={result.stderr!r}",
        )

    def test_orphaned_view_without_manifest_fails(self):
        self.write("docs/evidence/product-evidence-view.md", "# Product Evidence View\n")
        self.commit_all("orphan view")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "orphaned Product Evidence view must fail without a manifest. "
            f"WHY: generated views need the manifest source rows. "
            f"HOW: inspect orphan view handling. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "orphaned Product Evidence view",
            result.stderr,
            f"orphaned view failure must name the missing manifest condition. STDERR={result.stderr!r}",
        )

    def test_deleting_required_manifest_fails_even_when_diff_is_evidence_only(self):
        self.start_feature_with_product_evidence()
        (self.repo / "docs" / "evidence" / "product-evidence.json").unlink()
        self.commit_all("remove product evidence")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "deleting the required Product Evidence manifest must fail even when the diff "
            "is limited to docs/evidence. WHY: evidence backfill is a repair lane, not an "
            f"opt-out path. HOW: inspect deleted_required_evidence_files. "
            f"STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "Required Product Evidence artifact removed",
            result.stderr,
            f"manifest deletion failure must name the removed required artifact. STDERR={result.stderr!r}",
        )

    def test_valid_manifest_with_stale_view_fails(self):
        self.write_manifest(self.valid_manifest())
        self.write("docs/evidence/product-evidence-view.md", "# Product Evidence View\n\nstale\n")
        self.commit_all("stale view")

        result = self.run_validator()

        self.assertNotEqual(
            result.returncode,
            0,
            "stale generated Product Evidence view must fail when present. "
            f"WHY: reviewers read the view as generated evidence. "
            f"HOW: inspect render comparison. STDOUT={result.stdout!r} STDERR={result.stderr!r}",
        )
        self.assertIn(
            "view is stale",
            result.stderr,
            f"stale-view failure must name the generated view. STDERR={result.stderr!r}",
        )

    def test_policy_action_has_no_private_checkout_or_product_evidence_opt_out(self):
        action = yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))
        inputs = action.get("inputs", {})
        rendered = ACTION_YML.read_text(encoding="utf-8")

        self.assertNotIn(
            "product-evidence",
            inputs,
            "ci-alphaapps-policy must not expose a normal Product Evidence opt-out input. "
            f"WHY: Product Evidence is required for active ForgingAlpha repositories. "
            f"HOW: remove product-evidence from action.yml inputs. inputs={sorted(inputs)}",
        )
        self.assertNotIn(
            "alphaapps-docs",
            rendered.lower(),
            "ci-alphaapps-policy must not require consumers to checkout private alphaapps-docs. "
            "WHY: the public action has to run in consumer CI without private repository tokens. "
            "HOW: keep validators self-contained under actions/ci-alphaapps-policy/scripts.",
        )
        self.assertIn(
            "$GITHUB_ACTION_PATH/scripts",
            rendered,
            "ci-alphaapps-policy must run bundled scripts through GITHUB_ACTION_PATH. "
            "WHY: public consumers need the action implementation from the released tag. "
            "HOW: call python scripts from $GITHUB_ACTION_PATH/scripts.",
        )

    def test_policy_action_invalid_inputs_emit_what_why_how(self):
        rendered = ACTION_YML.read_text(encoding="utf-8")

        for input_name in (
            "product-lifecycle",
            "durable-evidence-references",
            "repo-kind",
            "base-ref",
        ):
            self.assertIn(
                "WHAT:",
                rendered,
                f"ci-alphaapps-policy invalid {input_name} failures must include WHAT. "
                "WHY: action failures need agent-readable WHAT/WHY/HOW diagnostics. "
                "HOW: add an explicit WHAT line to the invalid input branch.",
            )
        for diagnostic in ("WHAT:", "WHY:", "HOW:"):
            self.assertGreaterEqual(
                rendered.count(diagnostic),
                4,
                f"ci-alphaapps-policy invalid input branches must include {diagnostic}. "
                "WHY: every invalid-input branch needs complete WHAT/WHY/HOW output. "
                f"HOW: inspect action.yml input validation. rendered_count={rendered.count(diagnostic)}",
            )


if __name__ == "__main__":
    unittest.main()
