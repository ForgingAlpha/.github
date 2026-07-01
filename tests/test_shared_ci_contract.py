import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_ACTIONS = [
    ROOT / "actions" / "ci-rust" / "action.yml",
    ROOT / "actions" / "ci-elixir" / "action.yml",
    ROOT / "actions" / "ci-astro" / "action.yml",
    ROOT / "actions" / "ci-typescript" / "action.yml",
    ROOT / "actions" / "ci-shell" / "action.yml",
]
CODE_ACTIONS = [
    ROOT / "actions" / "ci-rust" / "action.yml",
    ROOT / "actions" / "ci-elixir" / "action.yml",
    ROOT / "actions" / "ci-astro" / "action.yml",
    ROOT / "actions" / "ci-typescript" / "action.yml",
]
CROSS_CUTTING_ORDER = [
    "ForgingAlpha/.github/actions/ci-merge-flow@v1",
    "ForgingAlpha/.github/actions/ci-alphaapps-policy@v1",
    "ForgingAlpha/.github/actions/ci-markdown@v1",
    "ForgingAlpha/.github/actions/ci-github-actions@v1",
    "ForgingAlpha/.github/actions/ci-dependabot-coverage@v1",
]
CROSS_CUTTING_HELPER_STEP_NAMES = {
    "Plan GitHub Actions safety gate",
}


class SharedCiContractTest(unittest.TestCase):
    def load_action(self, path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def uses_sequence(self, path):
        action = self.load_action(path)
        return [
            step.get("uses")
            for step in action["runs"]["steps"]
            if isinstance(step, dict) and step.get("uses")
        ]

    def language_step_index(self, path):
        action = self.load_action(path)
        for index, step in enumerate(action["runs"]["steps"]):
            if not isinstance(step, dict):
                continue
            if step.get("uses", "").startswith("ForgingAlpha/.github/actions/"):
                continue
            if step.get("name") in CROSS_CUTTING_HELPER_STEP_NAMES:
                continue
            return index
        self.fail(
            f"{path} must include at least one language-specific step. "
            "WHY: dependency-review ordering needs a concrete boundary before language work. "
            "HOW: inspect the composite action steps.",
        )

    def action_steps(self, path):
        action = self.load_action(path)
        return [
            step
            for step in action["runs"]["steps"]
            if isinstance(step, dict)
        ]

    def require_step_by_id(self, path, step_id):
        for step in self.action_steps(path):
            if step.get("id") == step_id:
                return step
        self.fail(
            f"{path} must include a step with id {step_id}. "
            "WHY: shared CI contract tests need an explicit step to inspect. "
            "HOW: restore the required step id or update the contract test with the new durable step name.",
        )

    def require_uses_step(self, path, uses):
        action = self.load_action(path)
        for index, step in enumerate(action["runs"]["steps"]):
            if isinstance(step, dict) and step.get("uses") == uses:
                return index, step
        self.fail(
            f"{path} must include a step using {uses}. "
            "WHY: shared CI contract tests need the published action step to verify ordering and guards. "
            "HOW: restore the uses step or update the contract test with the approved replacement.",
        )

    def test_language_composites_run_cross_cutting_policy_before_language_checks(self):
        for path in LANGUAGE_ACTIONS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                uses = self.uses_sequence(path)

                indexes = []
                for expected in CROSS_CUTTING_ORDER:
                    self.assertIn(
                        expected,
                        uses,
                        f"{path} must run {expected}. "
                        "WHY: published language composites carry the shared CI baseline before language-specific checks. "
                        "HOW: add the missing cross-cutting action after ci-merge-flow.",
                    )
                    indexes.append(uses.index(expected))

                self.assertEqual(
                    indexes,
                    sorted(indexes),
                    f"{path} must run shared CI checks in the canonical order. "
                    "WHY: source-truth and evidence checks should fail before lower-level language work. "
                    f"HOW: reorder composite uses steps; uses={uses!r}",
                )

    def test_remote_cross_cutting_steps_skip_central_repo_self_ci(self):
        direct_guarded_refs = set(CROSS_CUTTING_ORDER) - {
            "ForgingAlpha/.github/actions/ci-github-actions@v1"
        }
        direct_guarded_refs |= {
            "ForgingAlpha/.github/actions/ci-dependency-review@v1"
        }

        for path in LANGUAGE_ACTIONS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                for step in self.action_steps(path):
                    if step.get("uses") not in direct_guarded_refs:
                        continue
                    self.assertIn(
                        "github.repository != 'ForgingAlpha/.github'",
                        step.get("if", ""),
                        f"{path} must skip unreleased remote shared-action refs during central repo self-CI. "
                        "WHY: this repo dogfoods in-branch actions through direct local workflow steps before v1 moves. "
                        f"HOW: add the central-repo guard to the {step.get('uses')} step.",
                    )

                helper_step = self.require_step_by_id(path, "github_actions_safety")
                self.assertIn(
                    'REPOSITORY}" = "ForgingAlpha/.github"',
                    helper_step.get("run", ""),
                    f"{path} must skip ci-github-actions remote resolution during central repo self-CI. "
                    "WHY: branch-local self validation must not depend on unreleased remote shared-action refs. "
                    "HOW: keep the central-repo short-circuit in the GitHub Actions safety planner.",
                )

    def test_github_actions_safety_runs_only_when_changed_or_explicitly_enabled(self):
        for path in LANGUAGE_ACTIONS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                action = self.load_action(path)
                github_actions_mode = action["inputs"].get("github-actions-mode")
                self.assertEqual(
                    github_actions_mode,
                    {
                        "description": "GitHub Actions safety mode (changed|all)",
                        "required": False,
                        "default": "changed",
                    },
                    f"{path} must expose the GitHub Actions safety rollout mode. "
                    "WHY: consumers should run workflow/action safety only when files changed unless explicitly enabled. "
                    "HOW: add github-actions-mode with default changed.",
                )

                helper_step = self.require_step_by_id(path, "github_actions_safety")
                helper_script = helper_step.get("run", "")
                for expected in (
                    "changed|all",
                    ".github/workflows/*.yml",
                    ".github/workflows/*.yaml",
                    "actions/*/action.yml",
                    ".github/actions/*/action.yml",
                    "actions/checkout fetch-depth: 0",
                    "workflow_action_paths=(",
                    '"action.yml"',
                    'changed_paths="$(git diff --name-only --diff-filter=ACMR "${range}" -- "${workflow_action_paths[@]}")"',
                    "Failed to compute changed workflow/action files",
                    'done <<<"${changed_paths}"',
                ):
                    self.assertIn(
                        expected,
                        helper_script,
                        f"{path} must compute the ci-github-actions condition from changed workflow/action files. "
                        "WHY: the shared action should not be remotely resolved on every consumer CI run. "
                        f"HOW: keep {expected!r} in the github_actions_safety planner.",
                    )
                failure_start = helper_script.find('if ! changed_paths="$(git diff')
                failure_end = helper_script.find("\nfi\n\nchanged=false", failure_start)
                self.assertGreaterEqual(
                    failure_start,
                    0,
                    f"{path} must branch around failed git diff before assigning changed=false. "
                    "WHY: failed changed-file detection must not continue to a skip decision. "
                    "HOW: keep the git diff failure branch before changed=false.",
                )
                self.assertGreater(
                    failure_end,
                    failure_start,
                    f"{path} must close the git diff failure branch before assigning changed=false. "
                    "WHY: fail-closed detection should exit before any skip decision can run. "
                    "HOW: keep the failure branch immediately before changed=false.",
                )
                failure_body = helper_script[failure_start:failure_end]
                self.assertIn(
                    "exit 1",
                    failure_body,
                    f"{path} must exit nonzero when git diff fails in changed mode. "
                    "WHY: GitHub Actions safety changed-mode detection must fail closed before deciding run=false. "
                    "HOW: keep exit 1 inside the git diff failure branch.",
                )

                _, safety_step = self.require_uses_step(
                    path,
                    "ForgingAlpha/.github/actions/ci-github-actions@v1",
                )
                self.assertEqual(
                    safety_step.get("if"),
                    "${{ steps.github_actions_safety.outputs.run == 'true' }}",
                    f"{path} must resolve ci-github-actions only when the local planner enables it. "
                    "WHY: changed-file gating should happen before remote action resolution. "
                    "HOW: gate ci-github-actions on steps.github_actions_safety.outputs.run.",
                )

    def test_code_repo_composites_run_dependency_review_before_language_checks(self):
        for path in CODE_ACTIONS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                uses = self.uses_sequence(path)

                self.assertIn(
                    "ForgingAlpha/.github/actions/ci-dependency-review@v1",
                    uses,
                    f"{path} must run ci-dependency-review for code/package repos. "
                    "WHY: PR dependency review is part of the shared code-repo safety baseline. "
                    "HOW: add ci-dependency-review before language-specific checks.",
                )
                self.assertGreater(
                    uses.index("ForgingAlpha/.github/actions/ci-dependency-review@v1"),
                    uses.index("ForgingAlpha/.github/actions/ci-dependabot-coverage@v1"),
                    f"{path} must run dependency review after Dependabot coverage. "
                    "WHY: dependency-surface coverage should validate the repo update model before PR dependency diff review. "
                    f"HOW: reorder shared checks; uses={uses!r}",
                )

                dependency_review_step_index, dependency_review_step = self.require_uses_step(
                    path,
                    "ForgingAlpha/.github/actions/ci-dependency-review@v1",
                )
                self.assertEqual(
                    dependency_review_step.get("if"),
                    "${{ github.repository != 'ForgingAlpha/.github' && github.event_name == 'pull_request' }}",
                    f"{path} must resolve dependency review only on consumer pull requests. "
                    "WHY: dependency-review is a PR diff gate and should not add remote action startup to pushes. "
                    "HOW: gate ci-dependency-review on non-central pull_request events.",
                )
                self.assertLess(
                    dependency_review_step_index,
                    self.language_step_index(path),
                    f"{path} must run dependency review before language-specific setup/check/test steps. "
                    "WHY: the shared code-repo safety baseline runs cross-cutting checks before language-specific work. "
                    "HOW: move ci-dependency-review above language tool setup.",
                )

    def test_parent_ci_dogfoods_local_shared_policy_actions(self):
        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["CI"]["steps"]
        uses = [step.get("uses") for step in steps if isinstance(step, dict) and step.get("uses")]
        run_blocks = "\n".join(step.get("run", "") for step in steps if isinstance(step, dict))
        validate_shell_step = next(
            (step for step in steps if isinstance(step, dict) and step.get("name") == "Validate Shell"),
            None,
        )
        self.assertIsNotNone(
            validate_shell_step,
            "Parent CI must keep a Validate Shell step. "
            "WHY: the parent repo still needs shell validation while avoiding local ./actions/ci-shell bootstrap resolution. "
            "HOW: restore a Validate Shell run step in .github/workflows/ci.yml.",
        )
        validate_shell_run = validate_shell_step.get("run", "")

        for expected in (
            "./actions/ci-merge-flow",
            "./actions/ci-alphaapps-policy",
            "./actions/ci-markdown",
            "./actions/ci-github-actions",
            "./actions/ci-dependabot-coverage",
        ):
            self.assertIn(
                expected,
                uses,
                f"Parent CI must dogfood {expected}. "
                "WHY: this repo should validate the in-branch shared actions before release tags move. "
                f"HOW: add a local uses step for {expected} in .github/workflows/ci.yml.",
            )
        self.assertNotIn(
            "./actions/ci-shell",
            uses,
            "Parent CI must not call local ./actions/ci-shell before v1 moves. "
            "WHY: GitHub resolves composite uses steps before step-level if guards, so ci-shell would try to download unreleased @v1 shared actions during self-CI. "
            "HOW: run shellcheck and bash -n directly in .github/workflows/ci.yml until ci-shell's remote dependencies exist at v1.",
        )
        self.assertIn(
            "shellcheck -S style",
            validate_shell_run,
            "Parent CI must still run ShellCheck directly. "
            "WHY: skipping ./actions/ci-shell is only a bootstrap guard, not a relaxation of shell validation. "
            "HOW: keep shellcheck -S style in the direct Validate Shell step.",
        )
        self.assertIn(
            'if ! bash -n "$file"; then',
            validate_shell_run,
            "Parent CI must still run Bash syntax validation directly. "
            "WHY: skipping ./actions/ci-shell is only a bootstrap guard, not a relaxation of shell validation. "
            "HOW: keep the executable bash -n \"$file\" branch in the direct Validate Shell step.",
        )
        self.assertIn(
            "python3 -m unittest discover -s actions/ci-remote-probe-guard/tests",
            run_blocks,
            "Parent CI must run the remote probe guard test suite. "
            "WHY: REQ-015 requires shared action contracts to self-validate before release tags move. "
            "HOW: keep the Test Remote Probe Guard action step in .github/workflows/ci.yml.",
        )

    def test_readme_yaml_workflow_examples_parse(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        yaml_blocks = re.findall(r"```yaml\n(.*?)\n```", readme, flags=re.DOTALL)
        workflow_blocks = [
            block
            for block in yaml_blocks
            if "jobs:" in block and ("runs-on:" in block or "uses:" in block)
        ]

        self.assertTrue(
            workflow_blocks,
            "README must include parseable YAML workflow examples. "
            "WHY: consumers copy the public CI contract from README. "
            "HOW: add canonical code and control-plane workflow examples.",
        )

        for index, block in enumerate(workflow_blocks):
            with self.subTest(block=index):
                parsed = yaml.safe_load(block)
                self.assertIsInstance(
                    parsed,
                    dict,
                    "README workflow YAML block must parse to a mapping. "
                    f"WHY: examples should be directly copyable; block={block!r}. "
                    "HOW: fix the YAML snippet syntax.",
                )

                jobs = parsed.get("jobs")
                if jobs is None or parsed.get("name") != "CI":
                    continue
                self.assertEqual(
                    set(jobs),
                    {"CI"},
                    "README workflow examples must expose exactly one CI job. "
                    "WHY: org rulesets require one stable uppercase CI status. "
                    f"HOW: keep examples to jobs.CI only; jobs={jobs!r}",
                )
                self.assertEqual(
                    jobs["CI"].get("name"),
                    "CI",
                    "README workflow examples must name the required job CI. "
                    "WHY: the required status check is the job name, not only the YAML key. "
                    f"HOW: set jobs.CI.name to CI; job={jobs['CI']!r}",
                )


if __name__ == "__main__":
    unittest.main()
