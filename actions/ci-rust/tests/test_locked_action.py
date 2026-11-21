"""Exercise the public Rust steps with local, network-free Cargo workspaces."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ACTION = Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ACTION / "action.yml").read_text())
STEPS = {step["name"]: step for step in CONFIG["runs"]["steps"]}
VERIFY = "Verify Cargo lock policy"
FORMAT = "Check formatting"
CLIPPY = "Clippy (deny warnings)"
CHECK = "Compile (deny dead code)"
TEST = "Run tests"
AUDIT = "Audit dependencies"


class LockedActionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        self.tools = self.root / "bin"
        self.tools.mkdir()
        self.env = dict(os.environ, GITHUB_ACTION_PATH=str(ACTION),
                        PATH=str(self.tools) + os.pathsep + os.environ["PATH"],
                        CARGO_HOME=str(self.root / "cargo"), CARGO_NET_OFFLINE="true",
                        CARGO_TARGET_DIR=str(self.root / "target"),
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.command(["git", "init", "--quiet"], self.repo)

    def command(self, argv, cwd):
        return subprocess.run(argv, cwd=cwd, env=self.env, text=True,
                              capture_output=True, check=True)

    def public_step(self, name, cwd, locked=None, success=True):
        step = STEPS[name]
        self.assertEqual(step["shell"], "bash")
        self.assertEqual(step["working-directory"], "${{ inputs.working-directory }}")
        self.assertNotIn("if", step)
        self.assertNotIn("continue-on-error", step)
        env = dict(self.env)
        for key, value in step.get("env", {}).items():
            self.assertEqual(value, "${{ inputs.locked }}")
            env[key] = CONFIG["inputs"]["locked"]["default"] if locked is None else locked
        result = subprocess.run(["bash", "-eo", "pipefail", "-c", step["run"]],
                                cwd=cwd, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def commit(self):
        self.command(["git", "add", "-A"], self.repo)
        self.command(["git", "-c", "user.name=Rust fixture", "-c", "user.email=ci@example.org",
                      "commit", "-qm", "fixture"], self.repo)

    def workspace(self, path):
        workspace = self.repo / path
        files = {
            "Cargo.toml": ('[workspace]\nmembers=["app","other"]\ndefault-members=["app"]\n'
                           'exclude=["vendor/upstream"]\nresolver="2"\n'),
            "app/Cargo.toml": ('[package]\nname="app"\nversion="1.0.0"\nedition="2021"\n'
                               '[dependencies]\nupstream={path="../vendor/upstream"}\n'),
            "app/src/lib.rs": "#[test]\nfn app_test() {}\n",
            "other/Cargo.toml": '[package]\nname="other"\nversion="1.0.0"\nedition="2021"\n',
            "other/src/lib.rs": "#[test]\nfn other_test() {}\n",
            "vendor/upstream/Cargo.toml": ('[package]\nname="upstream"\nversion="1.0.0"\n'
                                           'edition="2021"\n[workspace]\n'),
            "vendor/upstream/src/lib.rs": '#[test]\nfn vendor_test() {\n    panic!("vendor only");\n}\n',
        }
        for name, content in files.items():
            dest = workspace / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
        self.command(["cargo", "generate-lockfile", "--offline"], workspace)
        self.commit()
        return workspace

    def test_valid_workspace_and_member_keep_package_selection(self):
        # Delegate only the external auditor to a local probe. Cargo, Clippy,
        # rustfmt and the compiled tests run on the real workspace.
        auditor = self.tools / "cargo-audit"
        auditor.write_text('#!/bin/sh\nset -eu\ntest "$1" = audit && test "$2" = --file && '
                           'test "$#" = 3 && test -f "$3" && printf "%s\\n" "$3"\n')
        auditor.chmod(0o755)
        for path in (".", "nested api"):
            workspace = self.workspace(path)
            lock = workspace / "Cargo.lock"
            before = lock.read_bytes()
            for directory, included, excluded in ((workspace, "app_test", "other_test"),
                                                  (workspace / "other", "other_test", "app_test")):
                with self.subTest(directory=directory):
                    for step in (VERIFY, FORMAT, CLIPPY, CHECK):
                        self.public_step(step, directory, "true")
                    tests = self.public_step(TEST, directory, "true").stdout
                    self.assertIn(included, tests)
                    self.assertNotIn(excluded, tests)
                    self.assertNotIn("vendor_test", tests)
                    self.assertEqual(self.public_step(AUDIT, directory, "true").stdout.strip(), str(lock))
                    self.assertEqual(lock.read_bytes(), before)
                    if directory != workspace:
                        self.assertFalse((directory / "Cargo.lock").exists())
                    self.assertFalse((workspace / "vendor/upstream/Cargo.lock").exists())

    def test_root_and_nested_missing_generated_dirty_and_stale_locks(self):
        for path in (".", "api"):
            workspace = self.workspace(path)
            lock = workspace / "Cargo.lock"
            original = lock.read_bytes()
            self.command(["git", "rm", "--quiet", "Cargo.lock"], workspace)
            self.commit()
            for state in ("missing", "generated", "staged", "dirty", "stale"):
                with self.subTest(workspace=path, state=state):
                    if state == "generated":
                        self.command(["cargo", "generate-lockfile", "--offline"], workspace)
                    if state == "staged":
                        self.command(["git", "add", "Cargo.lock"], workspace)
                    if state == "dirty":
                        self.commit()
                        lock.write_bytes(original + b"\n# uncommitted\n")
                    if state == "stale":
                        lock.write_bytes(original)
                        member = workspace / "app/Cargo.toml"
                        member.write_text(member.read_text().replace("1.0.0", "2.0.0"))
                        self.commit()
                    before = lock.read_bytes() if lock.exists() else None
                    status = self.command(["git", "status", "--porcelain"], workspace).stdout
                    self.public_step(VERIFY, workspace, "true", success=False)
                    if state != "stale":
                        failure = self.public_step(AUDIT, workspace / "app", "true", success=False)
                        self.assertIn("committed workspace lockfile", failure.stderr)
                    if state == "stale":
                        for step in (CLIPPY, CHECK, TEST):
                            failure = self.public_step(step, workspace, "true", success=False)
                            self.assertIn("--locked", failure.stderr)
                    self.assertEqual(lock.read_bytes() if lock.exists() else None, before)
                    self.assertEqual(self.command(["git", "status", "--porcelain"], workspace).stdout, status)

    def test_two_valid_locked_graphs_preserve_the_repository_selection(self):
        workspace = self.workspace(".")
        app = workspace / "app/Cargo.toml"
        with app.open("a") as manifest:
            manifest.write('local-demo = "1"\n')
        # Use a local directory source with two compatible releases. Generate
        # each lock while that release is the newest, then keep both in Git.
        config = workspace / ".cargo/config.toml"
        config.parent.mkdir()
        vendored = ('[source.crates-io]\nreplace-with = "fixture"\n'
                    '[source.fixture]\ndirectory = "crates"\n')
        config.write_text(vendored)
        root_lock = workspace / "Cargo.lock"
        locks = {}
        for minor, version in enumerate(("1.0.0", "1.1.0")):
            package = workspace / "crates" / f"local-demo-{version}"
            (package / "src").mkdir(parents=True)
            (package / "Cargo.toml").write_text(
                f'[package]\nname = "local-demo"\nversion = "{version}"\nedition = "2021"\n')
            (package / "src/lib.rs").write_text(f"pub const MINOR: u8 = {minor};\n")
            files = {name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                     for name in ("Cargo.toml", "src/lib.rs")}
            (package / ".cargo-checksum.json").write_text(json.dumps({"files": files, "package": None}))
            root_lock.unlink()
            self.command(["cargo", "generate-lockfile"], workspace)
            locks[version] = root_lock.read_bytes()
        alternate = workspace / "alternate/Cargo.lock"
        alternate.parent.mkdir()
        alternate.write_bytes(locks["1.1.0"])
        root_lock.write_bytes(locks["1.0.0"])

        def selected_version():
            result = self.command(["cargo", "metadata", "--locked", "--format-version", "1"], workspace)
            return next(p["version"] for p in json.loads(result.stdout)["packages"] if p["name"] == "local-demo")

        self.assertEqual(selected_version(), "1.0.0")
        config.write_text(vendored + '[resolver]\nlockfile-path = "alternate/Cargo.lock"\n')
        self.commit()
        self.assertEqual(selected_version(), "1.1.0", "this two-lockfile fixture requires Cargo 1.97+")
        for step in (VERIFY, FORMAT, CLIPPY, CHECK, TEST, AUDIT):
            refused = self.public_step(step, workspace, "true", success=False)
            self.assertIn("cannot verify a configured lockfile path", refused.stderr)
        self.public_step(VERIFY, workspace)
        # Compilation succeeds only with the repository-selected release.
        (workspace / "app/src/lib.rs").write_text("const _: () = assert!(local_demo::MINOR == 1);\n")
        self.public_step(CHECK, workspace, "false")
        self.assertEqual(selected_version(), "1.1.0")
        self.assertEqual(root_lock.read_bytes(), locks["1.0.0"])
        self.assertEqual(alternate.read_bytes(), locks["1.1.0"])

    def test_config_sources_and_ordinary_settings(self):
        workspace = self.workspace("api")
        member = workspace / "app"
        ancestor = self.repo / ".cargo"
        ancestor.mkdir()
        config = ancestor / "config.toml"
        config.write_text('include = ["group.toml", { path = "missing.toml", optional = true }]\n')
        (ancestor / "group.toml").write_text('include = ["shared.toml"]\n')
        included = ancestor / "shared.toml"
        included.write_text('[build]\njobs = 1\n')
        self.public_step(VERIFY, member, "true")

        included.write_text('resolver."lockfile-path" = "elsewhere/Cargo.lock"\n')
        self.assertIn("configured lockfile path", self.public_step(VERIFY, member, "true", False).stderr)
        # Cargo chooses the extensionless file when both names exist.
        (ancestor / "config").write_text('[build]\njobs = 1\n')
        self.public_step(VERIFY, member, "true")
        home_config = Path(self.env["CARGO_HOME"]) / "config.toml"
        home_config.write_text('[env]\nCARGO_RESOLVER_LOCKFILE_PATH = "elsewhere/Cargo.lock"\n')
        self.assertIn("configured lockfile path", self.public_step(VERIFY, member, "true", False).stderr)
        home_config.unlink()
        self.env["CARGO_RESOLVER_LOCKFILE_PATH"] = "elsewhere/Cargo.lock"
        self.assertIn("configured lockfile path", self.public_step(VERIFY, member, "true", False).stderr)

    def test_root_workspace_with_conventional_build_config(self):
        workspace = self.workspace(".")
        config = workspace / ".cargo/config.toml"
        config.parent.mkdir()
        config.write_text("[build]\njobs = 8\n")
        self.commit()
        self.public_step(VERIFY, workspace, "true")
        self.public_step(CHECK, workspace, "true")

    def test_multiline_config_uses_the_python_selected_on_path(self):
        workspace = self.workspace(".")
        config = workspace / ".cargo/config.toml"
        config.parent.mkdir()
        config.write_text('[env]\nEXAMPLE = {\n  value = "local",\n  force = false,\n}\n')
        self.command(["cargo", "metadata", "--locked", "--format-version", "1"], workspace)
        version = self.command(["python3", "-I", "-c",
                                "import sys; print(sys.version_info >= (3, 15))"], workspace)
        supports_toml_11 = version.stdout.strip() == "True"
        result = self.public_step(VERIFY, workspace, "true", success=supports_toml_11)
        if not supports_toml_11:
            self.assertIn("select Python 3.15+ as python3 on PATH", result.stderr)
        config.write_text(config.read_text().replace("EXAMPLE", "CARGO_RESOLVER_LOCKFILE_PATH"))
        refused = self.public_step(VERIFY, workspace, "true", success=False)
        diagnostic = "configured lockfile path" if supports_toml_11 else "select Python 3.15+"
        self.assertIn(diagnostic, refused.stderr)

    def test_input_validation_and_no_parent_manifest_fallback(self):
        self.assertEqual(CONFIG["inputs"]["working-directory"]["default"], ".")
        self.assertEqual(CONFIG["inputs"]["locked"]["default"], "false")
        self.assertLess(list(STEPS).index(VERIFY), list(STEPS).index("Cache Rust"))
        workspace = self.workspace(".")
        directory = workspace / "app/src"
        for value in ("", "yes", "central", "TRUE"):
            self.public_step(VERIFY, workspace, value, success=False)
        self.public_step(VERIFY, directory, "true", success=False)
        for value in (None, "false"):
            self.public_step(VERIFY, directory, value)

    def test_default_and_false_forward_the_legacy_command_and_failure(self):
        cargo = self.tools / "cargo"
        cargo.write_text('#!/bin/sh\nprintf "%s\\n" "$*"\nexit 8\n')
        cargo.chmod(0o755)
        expected = {FORMAT: "fmt --all -- --check",
                    CLIPPY: "clippy --all-targets --all-features -- -D warnings",
                    CHECK: "check --all-targets", TEST: "test --all-targets --all-features", AUDIT: "audit"}
        for value in (None, "false"):
            for name, args in expected.items():
                with self.subTest(value=value, name=name):
                    result = self.public_step(name, self.repo, value, success=False)
                    self.assertEqual(result.stdout.strip(), args)
                    self.assertEqual(result.returncode, 8)
