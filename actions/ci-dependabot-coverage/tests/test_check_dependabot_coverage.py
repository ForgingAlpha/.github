import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_dependabot_coverage.py"
ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-dependabot-coverage" / "action.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
TEMPLATES = ROOT / "templates" / "dependabot"
SPEC = importlib.util.spec_from_file_location("check_dependabot_coverage", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError(
        f"WHAT: could not load Dependabot coverage checker from {SCRIPT}. "
        "WHY: these tests import the reusable coverage checker directly. "
        "HOW: restore actions/ci-dependabot-coverage/scripts/check_dependabot_coverage.py."
    )
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class CheckDependabotCoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.root = self.make_repo()

    def tearDown(self):
        self.tmp.cleanup()

    def make_repo(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for key, value in (
            ("user.email", "test@example.invalid"),
            ("user.name", "Test"),
        ):
            subprocess.run(
                ["git", "config", key, value],
                cwd=root,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        return tmp, root

    def run_git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write_text(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.run_git("add", relative_path)
        return path

    def write_dependabot(self, updates, extra_comments=""):
        path = self.root / ".github" / "dependabot.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = extra_comments
        text += yaml.safe_dump({"version": 2, "updates": updates}, sort_keys=False)
        path.write_text(text, encoding="utf-8")
        self.run_git("add", ".github/dependabot.yml")
        return path

    def validate(self):
        return checker.validate(self.root, self.root / ".github" / "dependabot.yml")

    def test_missing_config_fails_for_each_detected_surface(self):
        fixtures = [
            (".github/workflows/ci.yml", "name: CI\n", "github-actions"),
            ("actions/example/action.yml", "name: Example\nruns:\n  using: composite\n  steps: []\n", "github-actions"),
            ("Cargo.toml", "[package]\nname = \"app\"\nversion = \"0.1.0\"\n", "cargo"),
            ("package.json", "{\"private\": true}\n", "npm"),
            ("mix.exs", "defmodule Example.MixProject do\nend\n", "mix"),
            ("requirements.txt", "requests==2.0.0\n", "pip"),
        ]

        for relative_path, content, ecosystem in fixtures:
            with self.subTest(relative_path=relative_path):
                tmp, root = self.make_repo()
                self.addCleanup(tmp.cleanup)
                old_root = self.root
                try:
                    self.root = root
                    self.write_text(relative_path, content)
                    errors = self.validate()
                finally:
                    self.root = old_root

                self.assertTrue(
                    any(ecosystem in error for error in errors),
                    "Dependabot coverage must fail when a detected surface has no config. "
                    f"WHY: every dependency surface needs update coverage or documented unmanaged status. "
                    f"HOW: inspect missing-config handling; errors={errors!r}",
                )

    def test_nested_action_manifest_requires_matching_github_actions_directory(self):
        self.write_text(".github/workflows/ci.yml", "name: CI\n")
        self.write_text("actions/example/action.yml", "name: Example\nruns:\n  using: composite\n  steps: []\n")
        self.write_dependabot(
            [
                {
                    "package-ecosystem": "github-actions",
                    "directory": "/",
                    "schedule": {"interval": "weekly"},
                }
            ]
        )

        errors = self.validate()

        self.assertTrue(
            any("/actions/example" in error for error in errors),
            "Dependabot coverage must require nested action manifest directories. "
            "WHY: composite action dependencies are updateable surfaces separate from workflows. "
            f"HOW: add /actions/* coverage; errors={errors!r}",
        )

        self.write_dependabot(
            [
                {
                    "package-ecosystem": "github-actions",
                    "directories": ["/", "/actions/*"],
                    "schedule": {"interval": "weekly"},
                }
            ]
        )

        self.assertEqual(
            self.validate(),
            [],
            "Dependabot coverage must accept directories entries that cover workflows and nested actions. "
            "WHY: shared repos use one github-actions update block with directories. "
            "HOW: inspect directory glob matching.",
        )

    def test_unmanaged_surfaces_require_documented_reason(self):
        self.write_text("requirements.txt", "requests==2.0.0\n")
        self.write_dependabot(
            [],
            extra_comments="# alphaapps-dependabot-unmanaged: pip /\n",
        )

        errors = self.validate()

        self.assertTrue(
            any("malformed unmanaged" in error for error in errors),
            "Dependabot coverage must reject unmanaged comments without a reason. "
            "WHY: intentionally unmanaged dependency surfaces need explicit review evidence. "
            f"HOW: add ' - <reason>' to the comment; errors={errors!r}",
        )

        self.write_dependabot(
            [],
            extra_comments="# alphaapps-dependabot-unmanaged: pip / -    \n",
        )

        errors = self.validate()

        self.assertTrue(
            any("has no reason" in error for error in errors),
            "Dependabot coverage must reject whitespace-only unmanaged reasons. "
            "WHY: exceptions need actual review evidence, not blank text after a dash. "
            f"HOW: inspect unmanaged reason trimming; errors={errors!r}",
        )

        self.write_dependabot(
            [],
            extra_comments="# alphaapps-dependabot-unmanaged: pip / - vendored runtime image owns Python updates\n",
        )

        self.assertEqual(
            self.validate(),
            [],
            "Dependabot coverage must accept an unmanaged surface only with a documented reason. "
            "WHY: exceptions are allowed only when review evidence is explicit. "
            "HOW: inspect unmanaged comment parsing.",
        )

    def test_directories_globs_cover_multiple_manifest_directories(self):
        self.write_text("apps/web/package.json", "{\"private\": true}\n")
        self.write_text("apps/admin/package.json", "{\"private\": true}\n")
        self.write_dependabot(
            [
                {
                    "package-ecosystem": "npm",
                    "directories": ["/apps/*"],
                    "schedule": {"interval": "weekly"},
                }
            ]
        )

        self.assertEqual(
            self.validate(),
            [],
            "Dependabot coverage must support directories globs for repeated manifest directories. "
            "WHY: mixed app repos should avoid duplicate update blocks for the same ecosystem. "
            "HOW: inspect directory glob matching.",
        )

    def test_report_mode_prints_findings_without_failure(self):
        self.write_text("package.json", "{\"private\": true}\n")
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            result = checker.main(["--root", str(self.root), "--mode", "report"])

        self.assertEqual(
            result,
            0,
            "Dependabot coverage report mode must exit successfully with findings. "
            "WHY: some repos may stage coverage rollout as a report before failing. "
            f"HOW: inspect mode handling; stderr={stderr.getvalue()!r}",
        )
        self.assertIn(
            "missing Dependabot coverage",
            stderr.getvalue(),
            "Dependabot coverage report mode must still print actionable findings. "
            f"WHY: report mode should not hide missing coverage. stderr={stderr.getvalue()!r}",
        )

    def test_filesystem_fallback_prunes_generated_directories(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "node_modules" / "pkg").mkdir(parents=True)
        (root / "node_modules" / "pkg" / "package.json").write_text(
            "{\"private\": true}\n",
            encoding="utf-8",
        )
        (root / "package.json").write_text("{\"private\": true}\n", encoding="utf-8")

        files = checker.tracked_files(root)

        self.assertEqual(
            files,
            ["package.json"],
            "Dependabot coverage fallback discovery must prune generated dependency directories. "
            "WHY: validation latency should not scale with node_modules or other build output. "
            f"HOW: inspect os.walk directory pruning; files={files!r}",
        )

    def test_action_validates_inputs_before_python_checker(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        run_blocks = "\n".join(
            step.get("run", "")
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        )

        for expected in (
            "Invalid mode input",
            "Invalid config-path input",
            ".github/dependabot.yml|.github/dependabot.yaml",
            "not an arbitrary file",
            "scripts/check_dependabot_coverage.py",
        ):
            with self.subTest(expected=expected):
                self.assertIn(
                    expected,
                    run_blocks,
                    "ci-dependabot-coverage must fail closed before invoking the checker with bad inputs. "
                    "WHY: shared action diagnostics should be WHAT/WHY/HOW and consistent with other composites. "
                    f"HOW: restore shell input validation in {ACTION}.",
                )

    def test_parent_ci_dogfoods_dependabot_coverage_action(self):
        workflow_text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "uses: ./actions/ci-dependabot-coverage",
            workflow_text,
            "Parent CI must dogfood ci-dependabot-coverage before relying on unit tests. "
            "WHY: shared composite actions should validate their in-branch action.yml wiring in CI. "
            f"HOW: add a local uses step to {WORKFLOW}.",
        )

    def test_dependabot_templates_are_v2_configs_with_github_actions_coverage(self):
        template_paths = sorted(TEMPLATES.glob("*.yml"))

        self.assertTrue(
            template_paths,
            "Dependabot templates must include at least one public template. "
            "WHY: consuming repos need copyable starting points for known repo classes. "
            "HOW: restore templates/dependabot/*.yml.",
        )
        for path in template_paths:
            with self.subTest(path=path.name):
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
                ecosystems = [
                    update.get("package-ecosystem")
                    for update in loaded.get("updates", [])
                    if isinstance(update, dict)
                ]

                self.assertEqual(
                    loaded.get("version"),
                    2,
                    f"{path.name} must be a Dependabot v2 config. "
                    "WHY: all public templates should be directly copyable. "
                    f"HOW: set version: 2 in {path}.",
                )
                self.assertIn(
                    "github-actions",
                    ecosystems,
                    f"{path.name} must include GitHub Actions coverage. "
                    "WHY: every known repo class has workflow or action dependency surfaces. "
                    f"HOW: add a github-actions update block to {path}.",
                )


if __name__ == "__main__":
    unittest.main()
