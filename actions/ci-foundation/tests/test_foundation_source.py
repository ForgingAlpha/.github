"""Requirement-grounded counterexamples; all public payloads are synthetic."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import yaml


ACTION = Path(__file__).resolve().parents[1]
ROOT = ACTION.parents[1]
SCRIPT = ACTION / "scripts/foundation_source.py"
spec = importlib.util.spec_from_file_location("trusted_foundation_source", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class FoundationAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.consumer = self.area / "consumer"
        self.consumer.mkdir()
        # A test-owned trusted action tree, separate from the candidate checkout.
        self.trusted = self.area / "shared/actions/ci-foundation"
        (self.trusted / "scripts").mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.trusted / "scripts/foundation_source.py")
        self.script = self.trusted / "scripts/foundation_source.py"
        self.payload = self.consumer / ".foundation"
        self.payload.mkdir()
        self.sentinel = self.area / "EXECUTED"
        body = ("from pathlib import Path\nPath(" + repr(str(self.sentinel)) + ").touch()\n").encode()
        (self.payload / "helper.py").write_bytes(body)
        (self.payload / "nested").mkdir()
        (self.payload / "nested/run").write_bytes(b"synthetic executable\n")
        (self.payload / "nested/run").chmod(0o755)
        # Build the oracle directly from the fixture bytes, not inventory().
        self.value = {"format": "foundation-source-v1",
                      "repository": "https://github.com/ForgingAlpha/container-foundation",
                      "repository_id": 1428636846, "commit": "a" * 40, "tree": "b" * 40,
                      "files": [{"path": "helper.py", "size": len(body), "mode": "100644",
                                 "sha256": hashlib.sha256(body).hexdigest()},
                                {"path": "nested/run", "size": 21, "mode": "100755",
                                 "sha256": hashlib.sha256(b"synthetic executable\n").hexdigest()}]}
        self.raw = (json.dumps(self.value, sort_keys=True, indent=2) + "\n").encode()
        (self.consumer / "foundation.lock").write_bytes(self.raw)
        self.record = {key: self.value[key] for key in
                       ("format", "repository", "repository_id", "commit", "tree")}
        self.record["lock_sha256"] = hashlib.sha256(self.raw).hexdigest()
        self.write_catalog([self.record])

    def write_catalog(self, records):
        (self.trusted / "approved.json").write_text(json.dumps({"schema_version": 1, "records": records}))

    def run_gate(self, operation="verify", extra=(), env_extra=None):
        env = dict(os.environ)
        env.update(env_extra or {})
        return subprocess.run([sys.executable, "-I", str(self.script), operation,
                               "--root", str(self.consumer), *extra],
                              cwd=self.consumer, env=env, capture_output=True, text=True, timeout=10)

    def refused(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.sentinel.exists(), "candidate helper executed during authentication")

    def test_valid_working_pair_and_identity_evidence(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["result"], "working_pair_matches_approved_export")
        self.assertEqual(receipt["source_commit"], "a" * 40)
        self.assertEqual(receipt["policy_catalog_sha256"],
                         hashlib.sha256((self.trusted / "approved.json").read_bytes()).hexdigest())
        self.assertFalse(self.sentinel.exists())

    def test_joint_payload_and_self_consistent_lock_rewrite_is_refused(self):
        body = b"changed but self-consistent\n"
        (self.payload / "helper.py").write_bytes(body)
        self.value["files"][0].update(size=len(body), sha256=hashlib.sha256(body).hexdigest())
        (self.consumer / "foundation.lock").write_bytes(checker.encode(self.value))
        self.assertEqual(self.value["files"][0]["sha256"],
                         hashlib.sha256((self.payload / "helper.py").read_bytes()).hexdigest())
        self.refused(self.run_gate())

    def test_lock_bytes_and_matched_record_identity_are_both_required(self):
        (self.consumer / "foundation.lock").write_bytes(self.raw + b" ")
        self.refused(self.run_gate())
        (self.consumer / "foundation.lock").write_bytes(self.raw)
        for key, wrong in (("commit", "c" * 40), ("tree", "c" * 40)):
            with self.subTest(field=key):
                row = dict(self.record, **{key: wrong})
                self.write_catalog([row])
                self.refused(self.run_gate())

    def test_unknown_and_wrong_source_fields_are_refused(self):
        for key, value in (("repository", "https://github.com/another/source"),
                           ("repository_id", True), ("repository_id", 1),
                           ("format", "future-format"), ("commit", "short")):
            with self.subTest(field=key, value=value):
                row = dict(self.record, **{key: value})
                self.write_catalog([row])
                self.refused(self.run_gate())
        self.write_catalog([])
        self.refused(self.run_gate())

    def test_missing_and_partial_pair_are_not_admitted(self):
        lock = self.consumer / "foundation.lock"
        lock.unlink()
        self.refused(self.run_gate())
        self.refused(self.run_gate("update-owner"))
        shutil.rmtree(self.payload)
        result = self.run_gate("update-owner")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "foundation_not_applicable")
        self.refused(self.run_gate())
        lock.write_bytes(self.raw)
        self.refused(self.run_gate("update-owner"))

    def test_working_file_changes_extras_modes_and_empty_directories(self):
        target = self.payload / "nested/run"
        target.chmod(0o644)
        self.refused(self.run_gate())
        target.chmod(0o744)
        self.refused(self.run_gate())
        target.chmod(0o755)
        (self.payload / "extra").write_text("extra")
        self.refused(self.run_gate())
        (self.payload / "extra").unlink()
        (self.payload / "empty").mkdir()
        self.refused(self.run_gate())
        (self.payload / "empty").rmdir()
        target.write_bytes(b"wrong")
        self.refused(self.run_gate())

    def test_links_special_files_and_incomplete_source_transaction(self):
        outside = self.area / "outside"
        outside.write_text("must remain unchanged")
        target = self.payload / "helper.py"
        original = target.read_bytes()
        target.unlink()
        target.symlink_to(outside)
        self.refused(self.run_gate())
        target.unlink()
        os.mkfifo(target)
        self.refused(self.run_gate())
        target.unlink()
        target.write_bytes(original)
        self.assertEqual(self.run_gate().returncode, 0)
        (self.payload / "linked-dir").symlink_to(self.area, target_is_directory=True)
        self.refused(self.run_gate())
        (self.payload / "linked-dir").unlink()
        self.assertEqual(self.run_gate().returncode, 0)
        state = self.consumer / ".foundation-state"
        state.mkdir()
        (state / "transaction.json").write_text("{}")
        self.refused(self.run_gate())
        self.assertEqual(outside.read_text(), "must remain unchanged")

    def test_catalog_is_strict_and_candidate_cannot_replace_it(self):
        (self.consumer / "json.py").write_text("raise SystemExit('candidate import executed')\n")
        self.assertEqual(self.run_gate(env_extra={"PYTHONPATH": str(self.consumer)}).returncode, 0)
        self.write_catalog([])
        (self.consumer / "approved.json").write_text(json.dumps({"schema_version": 1, "records": [self.record]}))
        self.refused(self.run_gate(env_extra={"FOUNDATION_CATALOG": str(self.consumer / "approved.json"),
                                             "PYTHONPATH": str(self.consumer)}))
        self.refused(self.run_gate(extra=("--catalog", str(self.consumer / "approved.json"))))
        for records in ([self.record, self.record], [dict(self.record, inventory=[])],
                        [dict(self.record, lock_sha256="invalid")]):
            self.write_catalog(records)
            self.refused(self.run_gate())
        (self.trusted / "approved.json").write_text('{"schema_version":1,"schema_version":1,"records":[]}')
        self.refused(self.run_gate())
        (self.trusted / "approved.json").unlink()
        (self.trusted / "approved.json").symlink_to(self.consumer / "approved.json")
        result = self.run_gate()
        self.refused(result)
        receipt = json.loads(result.stdout)
        self.assertIsNone(receipt["policy_catalog_sha256"])
        self.assertEqual(receipt["verifier_sha256"], hashlib.sha256(self.script.read_bytes()).hexdigest())

    def test_lock_root_and_state_links_and_metadata_limit(self):
        lock = self.consumer / "foundation.lock"
        outside_lock = self.area / "outside.lock"
        outside_lock.write_bytes(self.raw)
        lock.unlink()
        lock.symlink_to(outside_lock)
        self.refused(self.run_gate())
        lock.unlink()
        lock.write_bytes(self.raw)
        state = self.consumer / ".foundation-state"
        state.symlink_to(self.area, target_is_directory=True)
        self.refused(self.run_gate())
        state.unlink()
        stored_payload = self.consumer / "stored"
        self.payload.rename(stored_payload)
        self.payload.symlink_to(stored_payload, target_is_directory=True)
        self.refused(self.run_gate())
        self.payload.unlink()
        stored_payload.rename(self.payload)
        lock.write_bytes(b" " * (checker.METADATA_LIMIT + 1))
        self.refused(self.run_gate())
        self.assertEqual(outside_lock.read_bytes(), self.raw)

    def test_policy_withdrawal_and_explicit_old_policy_restoration(self):
        self.assertEqual(self.run_gate().returncode, 0)
        self.write_catalog([])
        result = self.run_gate(env_extra={"FOUNDATION_ACTION_REF": "v1"})
        self.refused(result)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["result"], "refused")
        self.assertEqual(receipt["action_ref"], "v1")
        self.assertEqual(receipt["lock_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(receipt["policy_catalog_sha256"],
                         hashlib.sha256((self.trusted / "approved.json").read_bytes()).hexdigest())
        self.assertEqual(receipt["verifier_sha256"], hashlib.sha256(self.script.read_bytes()).hexdigest())
        self.write_catalog([self.record])
        self.assertEqual(self.run_gate().returncode, 0)
        second = copy.deepcopy(self.value)
        second["commit"] = "c" * 40
        second_raw = checker.encode(second)
        second_record = {key: second[key] for key in checker.IDENTITY_KEYS}
        second_record["lock_sha256"] = hashlib.sha256(second_raw).hexdigest()
        self.write_catalog([self.record, second_record])
        (self.consumer / "foundation.lock").write_bytes(second_raw)
        self.assertEqual(self.run_gate().returncode, 0)
        (self.consumer / "foundation.lock").write_bytes(self.raw)
        self.assertEqual(self.run_gate().returncode, 0)

    def test_manifest_schema_and_path_counterexamples(self):
        for mutation in (lambda v: v["files"][0].update(path="../escape"),
                         lambda v: v["files"][0].update(path="."),
                         lambda v: v["files"][0].update(size=True),
                         lambda v: v["files"].append(v["files"][0]),
                         lambda v: v.update(repository_id=True),
                         lambda v: v.update(extra="unknown")):
            value = copy.deepcopy(self.value)
            mutation(value)
            with self.assertRaises(checker.Refused):
                checker.manifest(checker.encode(value))

    def test_owned_update_step_reuses_verifier_and_preserves_other_owner_checks(self):
        owner = ROOT / "actions/ci-update-ownership"
        trusted_owner = self.trusted.parent / "ci-update-ownership"
        shutil.copytree(owner, trusted_owner)
        (self.consumer / ".github").mkdir()
        (self.consumer / ".github/update-policy.json").write_text(json.dumps({
            "schema_version": 1, "normal_update_owner": "renovate", "base_branch": "main"}))
        (self.consumer / "renovate.json").write_text(json.dumps({
            "extends": ["local>ForgingAlpha/.github:renovate-config"], "baseBranchPatterns": ["main"]}))
        (self.consumer / ".github/dependabot.yml").write_text(
            "version: 2\nupdates:\n  - package-ecosystem: github-actions\n    directory: /\n    schedule: {interval: daily}\n    open-pull-requests-limit: 0\n")
        action = yaml.safe_load((trusted_owner / "action.yml").read_text())
        self.assertEqual(action["runs"]["steps"][0]["env"]["FOUNDATION_ACTION_REF"],
                         "${{ github.action_ref }}")
        command = action["runs"]["steps"][0]["run"]
        startup = self.area / "startup"
        startup.mkdir()
        (startup / "sitecustomize.py").write_text(
            "from pathlib import Path\nPath(" + repr(str(self.sentinel)) + ").touch()\n")
        env = dict(os.environ, GITHUB_ACTION_PATH=str(trusted_owner), UPDATE_POLICY_DEFAULT_BRANCH="main",
                   FOUNDATION_ACTION_REF="v1", PYTHONPATH=str(startup))
        def run():
            return subprocess.run(["bash", "-c", command], cwd=self.consumer,
                                  env=env, capture_output=True, text=True, timeout=15)
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.sentinel.exists(), "checkout Python startup executed before admission")
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])["action_ref"], "v1")
        saved_payload = self.area / "saved-payload"
        self.payload.rename(saved_payload)
        lock = self.consumer / "foundation.lock"
        lock.unlink()
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])["result"], "foundation_not_applicable")
        lock.write_bytes(self.raw)
        self.refused(run())
        lock.unlink()
        saved_payload.rename(self.payload)
        self.refused(run())
        lock.write_bytes(self.raw)
        self.assertEqual(run().returncode, 0)
        self.write_catalog([])
        self.refused(run())
        self.write_catalog([self.record])
        (self.consumer / ".github/update-policy.json").unlink()
        self.refused(run())

    def test_directory_limit_stops_iteration_before_collecting_the_directory(self):
        wide = self.area / "wide"
        wide.mkdir()
        for index in range(4):
            (wide / str(index)).mkdir()
        original_scan, seen = os.scandir, []
        class TrackedEntries:
            def __init__(self, path):
                self.entries = original_scan(path)
            def __enter__(self):
                return self
            def __exit__(self, *_):
                self.entries.close()
            def __iter__(self):
                return self
            def __next__(self):
                entry = next(self.entries)
                seen.append(entry.name)
                return entry
        with mock.patch.object(checker, "ENTRY_LIMIT", 1), mock.patch.object(checker.os, "scandir", TrackedEntries):
            with self.assertRaises(checker.Refused):
                checker.inventory(wide)
        self.assertEqual(len(seen), 3, "enumeration continued after the first over-limit entry")

    def test_git_stream_caps_and_owned_process_cleanup(self):
        tools = self.area / "tools"
        tools.mkdir()
        fake_git = tools / "git"
        actual_popen = subprocess.Popen
        for stream in (1, 2):
            with self.subTest(stream=stream):
                fake_git.write_text("#!" + sys.executable + "\nimport os\nwhile True: os.write(" +
                                    str(stream) + ", b'x' * 64)\n")
                fake_git.chmod(0o755)
                children = []
                def launch(*args, **kwargs):
                    process = actual_popen(*args, **kwargs)
                    children.append(process)
                    return process
                with mock.patch.dict(os.environ, {"PATH": str(tools)}), \
                        mock.patch.object(checker, "METADATA_LIMIT", 32), \
                        mock.patch.object(checker.subprocess, "Popen", launch):
                    with self.assertRaisesRegex(checker.Refused, "output size exceeded"):
                        checker.git(self.area, "synthetic", limit=32)
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll(), "owned Git process survived refusal")

    def test_derivation_checks_total_before_reading_the_excess_blob(self):
        source = self.area / "small-source"
        (source / "payload").mkdir(parents=True)
        for name in ("a", "b"):
            (source / "payload" / name).write_bytes(b"x")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(source), *args], stderr=subprocess.DEVNULL)
        git("init", "-q")
        git("remote", "add", "origin", checker.REPOSITORY)
        git("add", "payload")
        git("-c", "user.name=Synthetic fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "synthetic")
        revision = git("rev-parse", "HEAD").decode().strip()
        original_git, bodies = checker.git, []
        def observed_git(*args, **kwargs):
            if args[1:3] == ("cat-file", "blob"):
                bodies.append(args[3])
            return original_git(*args, **kwargs)
        with mock.patch.object(checker, "TOTAL_LIMIT", 1), mock.patch.object(checker, "git", observed_git):
            with self.assertRaisesRegex(checker.Refused, "payload size exceeded"):
                checker.derive(source, revision)
        self.assertEqual(len(bodies), 1, "excess blob was read before aggregate refusal")

    def test_git_timeout_stops_child_holding_pipes_after_parent_exit(self):
        tools = self.area / "timeout-tools"
        tools.mkdir()
        pid_file = self.area / "owned-child.pid"
        fake_git = tools / "git"
        fake_git.write_text("#!" + sys.executable + "\nimport os,time\nfrom pathlib import Path\n"
                            "child = os.fork()\nif child == 0:\n    time.sleep(30)\n    os._exit(0)\n"
                            "Path(" + repr(str(pid_file)) + ").write_text(str(child))\nos._exit(0)\n")
        fake_git.chmod(0o755)
        try:
            with mock.patch.dict(os.environ, {"PATH": str(tools)}), mock.patch.object(checker, "GIT_TIMEOUT", 2):
                with self.assertRaisesRegex(checker.Refused, "timed out"):
                    checker.git(self.area, "synthetic")
            child = int(pid_file.read_text())
            status = Path("/proc") / str(child) / "stat"
            # Sending SIGKILL does not synchronously finish the child's exit.
            deadline = time.monotonic() + 5
            while True:
                try:
                    state = status.read_text().split(") ", 1)[1].split()[0]
                except FileNotFoundError:
                    break
                if state == "Z":
                    break
                if time.monotonic() >= deadline:
                    self.fail("owned child survived bounded cleanup observation: " + state)
                time.sleep(0.01)
        finally:
            # A failing negative control must not leave its own test child alive.
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text()), 9)
                except ProcessLookupError:
                    pass

    def test_independent_derivation_uses_git_objects_not_working_files(self):
        source = self.area / "source"
        source.mkdir()
        def git(*args):
            return subprocess.check_output(["git", "-C", str(source), *args], stderr=subprocess.DEVNULL)
        git("init", "-q")
        git("remote", "add", "origin", checker.REPOSITORY + ".git")
        shutil.copytree(self.payload, source / "payload")
        git("add", "payload")
        git("-c", "user.name=Synthetic fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "synthetic")
        revision = git("rev-parse", "HEAD").decode().strip()
        (source / "payload/helper.py").write_text("uncommitted changes")
        raw, record = checker.derive(source, revision)
        derived = json.loads(raw)
        self.assertEqual(derived["files"], self.value["files"])
        self.assertEqual(record["lock_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record["commit"], revision)
        self.assertEqual(derived["tree"], git("rev-parse", revision + ":payload").decode().strip())
        self.assertFalse(self.sentinel.exists())

    def test_shared_action_has_no_policy_override(self):
        action = yaml.safe_load((ACTION / "action.yml").read_text())
        self.assertNotIn("inputs", action)
        command = action["runs"]["steps"][0]["run"]
        self.assertIn('python3 -I "$GITHUB_ACTION_PATH/scripts/foundation_source.py"', command)
        self.assertNotIn("continue-on-error", action["runs"]["steps"][0])


if __name__ == "__main__":
    unittest.main()
