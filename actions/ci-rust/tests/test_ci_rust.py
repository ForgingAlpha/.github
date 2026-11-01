"""Legacy command conservation and complete locked central workspace coverage."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / 'actions/ci-rust/scripts/check_rust.sh'


class RustCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'log'
        cargo = self.root / 'cargo'
        cargo.write_text('#!/bin/sh\nprintf "%s|%s|%s\\n" "$*" "${RUSTFLAGS:-}" "$PWD" >> "$COMMAND_LOG"\nexit "${STUB_EXIT:-0}"\n')
        cargo.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + ':' + os.environ['PATH'], COMMAND_LOG=str(self.log), CARGO_AUDIT_VERSION='0.22.2')
        self.env.pop('RUSTFLAGS', None)

    def invoke(self, mode, step, fail=False):
        return subprocess.run(['bash', str(HELPER), mode, step], cwd=self.root,
                              env=dict(self.env, STUB_EXIT='4' if fail else '0'), capture_output=True)

    def test_legacy_argv_cwd_failure_and_deadcode_flag(self):
        cases = {'fmt': 'fmt --all -- --check', 'clippy': 'clippy --all-targets --all-features -- -D warnings',
                 'check': 'check --all-targets', 'test': 'test --all-targets --all-features',
                 'install-audit': 'install cargo-audit --locked --version 0.22.2', 'audit': 'audit'}
        for step, expected in cases.items():
            self.assertEqual(self.invoke('legacy', step).returncode, 0)
            self.assertEqual(self.log.read_text().splitlines()[-1], expected + '|' + ('-D dead_code' if step == 'check' else '') + '|' + str(self.root))
            self.assertNotEqual(self.invoke('legacy', step, True).returncode, 0)

    def test_central_all_workspace_and_locked_resolution(self):
        for step in ('clippy', 'check', 'test'):
            self.assertEqual(self.invoke('central', step).returncode, 0)
            self.assertIn('--locked --workspace --all-targets', self.log.read_text().splitlines()[-1])
        self.assertNotEqual(self.invoke('central', 'skip').returncode, 0)

    def test_wrapper_setup_defaults_and_literal_preserved(self):
        action = yaml.safe_load((ROOT / 'actions/ci-rust/action.yml').read_text())
        steps = action['runs']['steps']
        self.assertEqual(action['inputs']['toolchain']['default'], 'stable')
        self.assertEqual(action['inputs']['github-actions-mode']['default'], 'changed')
        uses = [s['uses'] for s in steps if 'uses' in s]
        self.assertTrue(any(x.startswith('dtolnay/rust-toolchain@') for x in uses))
        self.assertTrue(any(x.startswith('Swatinem/rust-cache@') for x in uses))
        install = next(s for s in steps if s['name'] == 'Install cargo-audit')
        self.assertEqual(install['env'], {'CARGO_AUDIT_VERSION': '0.22.2'})
        self.assertIn('legacy install-audit', install['run'])
