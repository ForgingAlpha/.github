import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "actions" / "ci-remote-probe-guard" / "action.yml"
SCRIPT = ROOT / "actions" / "ci-remote-probe-guard" / "scripts" / "validate_probe_inputs.py"
TEMPLATE = ROOT / "workflow-templates" / "ci-probe.yml"
SPEC = importlib.util.spec_from_file_location("validate_probe_inputs", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError(
        f"WHAT: could not load remote probe input validator from {SCRIPT}. "
        "WHY: REQ-012 requires a deterministic probe guard before diagnostic command construction. "
        "HOW: add actions/ci-remote-probe-guard/scripts/validate_probe_inputs.py."
    )
sys.modules[SPEC.name] = guard
SPEC.loader.exec_module(guard)


BASE_INPUTS = {
    "probe_mode": "exact",
    "lane": "unit",
    "allowed_lanes": "unit,integration",
    "file": "test/sample/example_test.exs",
    "line": "42",
    "out_label": "probe-unit",
    "checkout_ref": "feature/probe-target",
    "file_root": "test",
    "file_suffixes": ".exs",
}


class RemoteProbeGuardTest(unittest.TestCase):
    def validate(self, **overrides):
        inputs = {**BASE_INPUTS, **overrides}
        return guard.validate_inputs(inputs)

    def assert_invalid(self, expected_text, **overrides):
        with self.assertRaises(guard.ValidationError) as context:
            self.validate(**overrides)
        message = guard.render_error(context.exception)
        self.assertIn(
            expected_text,
            message,
            f"Invalid probe input must produce an actionable diagnostic. "
            f"WHY: REQ-012 requires constrained diagnostic execution before command construction. "
            f"HOW: include {expected_text!r} in the WHAT/WHY/HOW error; message={message!r}",
        )
        for required in ("WHAT:", "WHY:", "HOW:"):
            self.assertIn(
                required,
                message,
                f"Probe guard errors must use WHAT/WHY/HOW output. "
                f"WHY: REQ-014 requires actionable failure output. "
                f"HOW: update render_error; message={message!r}",
            )

    def test_valid_modes_return_normalized_fields_without_commands(self):
        cases = [
            (
                "exact",
                {"file": "test/sample/example_test.exs", "line": "42"},
                {"file": "test/sample/example_test.exs", "line": "42"},
            ),
            (
                "file",
                {"file": "test/sample/example_test.exs", "line": ""},
                {"file": "test/sample/example_test.exs", "line": ""},
            ),
            (
                "lane",
                {"file": "", "line": ""},
                {"file": "", "line": ""},
            ),
        ]

        for mode, overrides, expected in cases:
            with self.subTest(mode=mode):
                outputs = self.validate(probe_mode=mode, **overrides)

                self.assertEqual(
                    outputs["probe_mode"],
                    mode,
                    f"Probe guard must preserve the normalized mode {mode!r}. "
                    "WHY: consumer workflows assemble repo-owned command arrays from typed selector fields. "
                    f"HOW: inspect validate_inputs; outputs={outputs!r}",
                )
                self.assertEqual(
                    outputs["lane"],
                    "unit",
                    f"Probe guard must preserve the allowlisted lane. "
                    "WHY: lane selection is constrained input, not a shell command. "
                    f"HOW: inspect lane normalization; outputs={outputs!r}",
                )
                for key, value in expected.items():
                    self.assertEqual(
                        outputs[key],
                        value,
                        f"Probe guard must normalize {key} for {mode} mode. "
                        "WHY: the workflow needs deterministic fields for shell-array assembly. "
                        f"HOW: inspect mode-specific normalization; outputs={outputs!r}",
                    )
                self.assertEqual(
                    outputs["checkout_ref"],
                    "feature/probe-target",
                    f"Probe guard must preserve the normalized checkout ref. "
                    "WHY: the trusted workflow definition and target code checkout use separate refs. "
                    f"HOW: inspect checkout_ref normalization; outputs={outputs!r}",
                )
                self.assertEqual(
                    outputs["out_label"],
                    "probe-unit",
                    f"Probe guard must preserve safe artifact labels. "
                    "WHY: artifacts must be addressable without path traversal. "
                    f"HOW: inspect out_label normalization; outputs={outputs!r}",
                )
                self.assertEqual(
                    outputs["artifact_path"],
                    "probe-output/probe-unit",
                    f"Probe guard must derive a stable artifact path. "
                    "WHY: GITHUB_STEP_SUMMARY and upload-artifact need the same diagnostic packet path. "
                    f"HOW: inspect artifact_path output; outputs={outputs!r}",
                )
                forbidden = {"command", "cmd", "script", "shell", "run"}
                self.assertTrue(
                    forbidden.isdisjoint(outputs),
                    f"Probe guard must not emit arbitrary command fields. "
                    "WHY: REQ-012 forbids remote shell execution as a diagnostic input. "
                    f"HOW: remove command-like output keys; outputs={outputs!r}",
                )

    def test_invalid_modes_lanes_paths_lines_and_labels_fail(self):
        invalid_cases = [
            ("probe_mode", "shell", "probe_mode"),
            ("lane", "admin", "lane"),
            ("lane", "unit;rm -rf .", "lane"),
            ("file", "../mix.exs", "file"),
            ("file", "/tmp/example_test.exs", "file"),
            ("file", "test/./sample/example_test.exs", "file"),
            ("file", "test/sample/example_test.sh", "file"),
            ("file", "test/sample/example_test.exs;id", "file"),
            ("line", "0", "line"),
            ("line", "1;id", "line"),
            ("out_label", "../probe", "out_label"),
            ("out_label", "probe;id", "out_label"),
            ("file_root", "/test", "file_root"),
            ("file_root", "../test", "file_root"),
            ("file_root", "test/.", "file_root"),
            ("checkout_ref", "", "checkout_ref"),
            ("checkout_ref", "feature/ref;id", "checkout_ref"),
            ("checkout_ref", "../main", "checkout_ref"),
            ("checkout_ref", "refs/heads/bad..ref", "checkout_ref"),
            ("checkout_ref", "-dangerous", "checkout_ref"),
        ]

        for key, value, expected_text in invalid_cases:
            with self.subTest(key=key, value=value):
                self.assert_invalid(expected_text, **{key: value})

    def test_mode_specific_required_fields_fail_before_command_construction(self):
        self.assert_invalid("line", probe_mode="exact", line="")
        self.assert_invalid("file", probe_mode="exact", file="")
        self.assert_invalid("file", probe_mode="file", file="")
        self.assert_invalid("line", probe_mode="file", line="12")
        self.assert_invalid("file", probe_mode="lane", file="test/sample/example_test.exs")
        self.assert_invalid("line", probe_mode="lane", file="", line="12")

    def test_action_metadata_has_no_command_input_or_output(self):
        action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
        forbidden = {"command", "cmd", "script", "shell", "run"}
        input_names = set(action.get("inputs", {}))
        output_names = set(action.get("outputs", {}))

        self.assertTrue(
            forbidden.isdisjoint(input_names),
            f"Remote probe guard action must not accept command-like inputs. "
            "WHY: consumer repos own command mapping through reviewed workflow code. "
            f"HOW: remove command-like inputs from action.yml; inputs={input_names!r}",
        )
        self.assertTrue(
            forbidden.isdisjoint(output_names),
            f"Remote probe guard action must not emit command-like outputs. "
            "WHY: the guard emits selectors only, not remote shell commands. "
            f"HOW: remove command-like outputs from action.yml; outputs={output_names!r}",
        )

    def test_probe_template_is_thin_manual_wrapper(self):
        workflow = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
        triggers = workflow.get("on", workflow.get(True, {}))
        jobs = workflow.get("jobs", {})
        probe = jobs["probe"]

        self.assertIn(
            "workflow_dispatch",
            triggers,
            f"Probe template must be manually dispatched only. "
            "WHY: diagnostic probes are operator-run evidence, not merge authority. "
            f"HOW: define on.workflow_dispatch; triggers={triggers!r}",
        )
        self.assertEqual(
            set(triggers),
            {"workflow_dispatch"},
            f"Probe template must use workflow_dispatch as its only trigger. "
            "WHY: REQ-011 keeps diagnostic probes out of automatic merge authority. "
            f"HOW: remove automatic or privileged triggers; triggers={triggers!r}",
        )
        self.assertEqual(
            workflow.get("permissions"),
            {"contents": "read"},
            f"Probe template must use read-only root permissions. "
            "WHY: diagnostics should not need write permissions. "
            f"HOW: set permissions.contents to read; permissions={workflow.get('permissions')!r}",
        )
        for expected in ("inputs.probe_mode", "inputs.lane", "inputs.checkout_ref"):
            self.assertIn(
                expected,
                workflow.get("run-name", ""),
                f"Probe template run-name must include {expected}. "
                "WHY: manual diagnostic runs need visible mode/lane/ref context. "
                f"HOW: update run-name; run_name={workflow.get('run-name')!r}",
            )
        self.assertEqual(
            probe.get("uses"),
            "ForgingAlpha/.github/.github/workflows/ci-probe-elixir-postgres.yml@main",
            f"Probe template must call the centralized reusable probe workflow on @main. "
            "WHY: manual probes intentionally use the latest green internal platform. "
            f"HOW: keep the template as a thin reusable-workflow caller; probe={probe!r}",
        )
        self.assertNotIn(
            "steps",
            probe,
            f"Probe template must not copy command execution steps. "
            "WHY: reusable workflows own shared scaffolding and consumer repos own bin/ci-probe adapters. "
            f"HOW: remove copied steps from workflow-templates/ci-probe.yml; probe={probe!r}",
        )

    def test_reusable_probe_workflows_are_diagnostic_only(self):
        workflow_paths = sorted((ROOT / ".github" / "workflows").glob("ci-probe-*.yml"))
        self.assertTrue(
            workflow_paths,
            "Remote probe platform must define reusable probe workflows. "
            "WHY: consumers should call centralized @main workflows instead of copying command YAML. "
            "HOW: add .github/workflows/ci-probe-*.yml.",
        )

        for path in workflow_paths:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
                triggers = workflow.get("on", workflow.get(True, {}))
                jobs = workflow.get("jobs", {})
                steps = jobs["probe"]["steps"]
                run_blocks = "\n".join(
                    step.get("run", "") for step in steps if isinstance(step, dict)
                )
                step_names = [step.get("name", "") for step in steps if isinstance(step, dict)]

                self.assertEqual(
                    set(triggers),
                    {"workflow_call"},
                    f"Reusable probe workflow must be called by repo wrappers only. "
                    "WHY: consumer default-branch wrappers own manual workflow_dispatch entrypoints. "
                    f"HOW: keep on.workflow_call only; triggers={triggers!r}",
                )
                self.assertEqual(
                    workflow.get("permissions"),
                    {"contents": "read"},
                    f"Reusable probe workflow must use read-only root permissions. "
                    "WHY: diagnostics should not need write permissions. "
                    f"HOW: set permissions.contents to read; permissions={workflow.get('permissions')!r}",
                )
                self.assertLess(
                    step_names.index("Validate probe selector"),
                    step_names.index("Checkout target ref"),
                    f"Reusable probe workflow must validate selectors before target checkout. "
                    "WHY: invalid refs and selectors must fail before checkout-dependent execution. "
                    f"HOW: move the guard step before actions/checkout; step_names={step_names!r}",
                )
                source = next(step for step in steps if step.get("name") == "Checkout coherent trusted source")
                guard_step = next(step for step in steps if step.get("id") == "guard")
                self.assertEqual(source["with"]["ref"], "${{ steps.source.outputs.sha }}")
                self.assertEqual(source["with"]["path"], "probe-source")
                self.assertEqual(source["with"]["persist-credentials"], "false")
                self.assertNotIn("uses", guard_step)
                self.assertIn('${PROBE_SOURCE}/actions/ci-remote-probe-guard/scripts/validate_probe_inputs.py',
                              guard_step["run"])
                self.assertIn(
                    "./bin/ci-probe",
                    run_blocks,
                    f"Reusable probe workflow must delegate command mapping to the consumer adapter. "
                    "WHY: this public repo must not own private repo-specific probe commands. "
                    "HOW: invoke ./bin/ci-probe with normalized selector arguments.",
                )
                self.assertNotIn(
                    "eval ",
                    run_blocks,
                    f"Reusable probe workflow must not use eval. "
                    "WHY: probe inputs are selectors, not shell code. "
                    "HOW: keep command execution in repo-owned adapters without eval.",
                )
                self.assertIn(
                    "GITHUB_STEP_SUMMARY",
                    run_blocks,
                    f"Reusable probe workflow must write normalized inputs to the step summary. "
                    "WHY: diagnostic evidence needs exact selector and artifact context. "
                    "HOW: append a summary after guard validation.",
                )

                upload_steps = [
                    step
                    for step in steps
                    if isinstance(step, dict)
                    and str(step.get("uses", "")).startswith("actions/upload-artifact@")
                ]
                self.assertEqual(
                    len(upload_steps),
                    1,
                    f"Reusable probe workflow must upload one diagnostic artifact packet. "
                    "WHY: failed probes are evidence and must be retained briefly. "
                    f"HOW: add one upload-artifact step; upload_steps={upload_steps!r}",
                )
                upload = upload_steps[0]
                self.assertEqual(
                    upload.get("if"),
                    "${{ always() }}",
                    f"Probe artifacts must upload on success and failure. "
                    "WHY: failing probes carry the useful CI-only evidence. "
                    f"HOW: set if: ${{{{ always() }}}}; upload={upload!r}",
                )


class ProbeSourceBindingTest(unittest.TestCase):
    def workflows(self):
        for path in sorted((ROOT / ".github/workflows").glob("ci-probe-*.yml")):
            yield path, yaml.safe_load(path.read_text())["jobs"]["probe"]

    def context(self, path):
        return {"workflow_repository": "ForgingAlpha/.github", "workflow_sha": "a" * 40,
                "workflow_ref": "ForgingAlpha/.github/.github/workflows/" + path.name + "@refs/heads/main"}

    def run_identity(self, step, raw, directory):
        output = Path(directory) / "identity-output"
        output.unlink(missing_ok=True)
        environment = {**os.environ, "GITHUB_OUTPUT": str(output)}
        if len(raw) > 65536:
            # Linux rejects an individual environment string above its own limit.
            # Feed the same parser in-process via stdin to exercise our higher bound.
            parser = "\n".join(step["run"].splitlines()[1:-1])
            code = "import os,sys; os.environ['JOB_CONTEXT']=sys.stdin.read(); exec(" + repr(parser) + ")"
            result = subprocess.run([sys.executable, "-I", "-B", "-c", code], input=raw,
                                    cwd=directory, env=environment, capture_output=True, text=True)
        else:
            result = subprocess.run(["bash", "-c", step["run"]], cwd=directory,
                                    env={**environment, "JOB_CONTEXT": raw},
                                    capture_output=True, text=True)
        return result, output.read_text() if output.exists() else ""

    def test_native_identity_is_exact_bounded_and_duplicate_free(self):
        for path, job in self.workflows():
            step = next(s for s in job["steps"] if s.get("id") == "source")
            self.assertEqual(step["env"], {"JOB_CONTEXT": "${{ toJSON(job) }}"})
            self.assertEqual(step["working-directory"], "${{ github.workspace }}")
            context = self.context(path)
            with tempfile.TemporaryDirectory() as directory:
                for suffix in ("refs/heads/main", "a" * 40):
                    value = {**context, "workflow_ref": context["workflow_ref"].rsplit("@", 1)[0] + "@" + suffix}
                    result, output = self.run_identity(step, json.dumps(value), directory)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("sha=" + "a" * 40, output)
                invalid = ["", "{", "[]", "null", " " * 262145,
                           json.dumps(context)[:-1] + ', "workflow_sha": "' + 'b' * 40 + '"}']
                for key, value in (("workflow_repository", "other/.github"),
                                   ("workflow_sha", "main"), ("workflow_sha", "A" * 40),
                                   ("workflow_ref", context["workflow_ref"].replace(path.name, "other.yml")),
                                   ("workflow_ref", context["workflow_ref"].replace("refs/heads/main", "b" * 40))):
                    invalid.append(json.dumps({**context, key: value}))
                for key in context:
                    invalid.append(json.dumps({k: v for k, v in context.items() if k != key}))
                for raw in invalid:
                    with self.subTest(path=path.name, raw=raw[:160]):
                        result, output = self.run_identity(step, raw, directory)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("WHAT:", result.stderr)
                        self.assertEqual(output, "")

    def test_source_checkout_guard_arguments_and_consumer_paths_are_bound(self):
        original = yaml.safe_load(ACTION.read_text())["runs"]["steps"][0]
        for path, job in self.workflows():
            steps = job["steps"]
            source = next(s for s in steps if s.get("name") == "Checkout coherent trusted source")
            consumer = next(s for s in steps if s.get("name") == "Checkout target ref")
            step = next(s for s in steps if s.get("id") == "guard")
            self.assertEqual(source["with"]["repository"], "${{ steps.source.outputs.repository }}")
            self.assertEqual(source["with"]["ref"], "${{ steps.source.outputs.sha }}")
            self.assertEqual(consumer["with"]["ref"], "${{ steps.guard.outputs.checkout_ref }}")
            self.assertLess(steps.index(source), steps.index(step))
            self.assertLess(steps.index(step), steps.index(consumer))
            self.assertEqual(job["defaults"]["run"]["working-directory"], "consumer")
            for key, value in original["env"].items():
                self.assertEqual(step["env"][key], value.replace("-", "_"))
            for argument in ("--probe-mode", "--lane", "--allowed-lanes", "--file", "--line",
                             "--out-label", "--checkout-ref", "--file-root", "--file-suffixes"):
                self.assertIn(argument, step["run"])
            self.assertFalse(any(s.get("uses", "").startswith("ForgingAlpha/.github/") for s in steps))
            upload = next(s for s in steps if s.get("name") == "Upload diagnostic packet")
            self.assertEqual(upload["with"]["path"], "consumer/${{ steps.guard.outputs.artifact_path }}")
            for checkout in (source, consumer):
                self.assertEqual(checkout["with"]["persist-credentials"], "false")
            self.assertNotIn("token", step["env"])
            if path.name == "ci-probe-rust.yml":
                cache = next(s for s in steps if s.get("name") == "Cache Rust")
                self.assertEqual(cache["with"]["workspaces"], "consumer -> target")
            if path.name == "ci-probe-elixir-postgres.yml":
                setup = next(s for s in steps if s.get("name") == "Install exact locked runtime")
                self.assertEqual(setup["with"]["working_directory"], "consumer")
                self.assertEqual(setup["with"]["install_args"], "--locked")
                cache = next(s for s in steps if s.get("name") == "Cache deps and build")
                self.assertEqual(cache["with"]["path"].splitlines(), ["consumer/deps", "consumer/_build"])
                self.assertIn("hashFiles('consumer/mise.lock', 'consumer/mix.lock')", cache["with"]["key"])


    def test_workflow_a_never_executes_later_main_b_or_consumer_helper(self):
        for path, job in self.workflows():
            step = next(s for s in job["steps"] if s.get("id") == "guard")
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                helper = root / "probe-source/actions/ci-remote-probe-guard/scripts/validate_probe_inputs.py"
                helper.parent.mkdir(parents=True)
                shutil.copyfile(SCRIPT, helper)
                decoy = root / "consumer/actions/ci-remote-probe-guard/scripts/validate_probe_inputs.py"
                decoy.parent.mkdir(parents=True)
                decoy.write_text("raise RuntimeError('consumer or later main B must not execute')")
                fake_git = root / "git"
                fake_git.write_text('#!/bin/sh\nprintf "%s\\n" "$OBSERVED_SOURCE_SHA"\n')
                fake_git.chmod(0o755)
                output = root / "guard-output"
                environment = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                               "PROBE_SOURCE": str(root / "probe-source"), "PROBE_SOURCE_SHA": "a" * 40,
                               "OBSERVED_SOURCE_SHA": "a" * 40, "GITHUB_OUTPUT": str(output),
                               "PROBE_MODE": "exact", "PROBE_LANE": "unit", "PROBE_ALLOWED_LANES": "unit,integration",
                               "PROBE_FILE": "test/example.exs", "PROBE_LINE": "42", "PROBE_OUT_LABEL": "safe",
                               "PROBE_CHECKOUT_REF": "feature/target", "PROBE_FILE_ROOT": "test", "PROBE_FILE_SUFFIXES": ".exs"}
                result = subprocess.run(["bash", "-c", step["run"]], cwd=root, env=environment,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("checkout_ref=feature/target", output.read_text())
                output.unlink()
                # Simulate workflow A's checkout incorrectly replaced by later main B.
                marker = root / "ran-wrong-helper"
                helper.write_text("from pathlib import Path; Path(" + repr(str(marker)) + ").touch()")
                result = subprocess.run(["bash", "-c", step["run"]], cwd=root,
                                        env={**environment, "OBSERVED_SOURCE_SHA": "b" * 40},
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("differs from defining workflow", result.stderr)
                self.assertFalse(marker.exists())
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
