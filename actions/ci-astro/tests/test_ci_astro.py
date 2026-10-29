"""Legacy command behavior and central missing-tool refusal."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / 'actions/ci-astro/scripts/check_astro.sh'


class AstroCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'commands'
        self.stub = '#!/bin/sh\nprintf "%s|%s|%s\\n" "${0##*/}" "$*" "$PWD" >> "$COMMAND_LOG"\nexit "${STUB_EXIT:-0}"\n'
        for name in ('npm', 'npx'):
            file = self.bin / name
            file.write_text(self.stub)
            file.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'], COMMAND_LOG=str(self.log))

    def invoke(self, mode, step, *args, failure=False):
        return subprocess.run(['bash', str(HELPER), mode, step, *args], cwd=self.root,
                              env=dict(self.env, STUB_EXIT='9' if failure else '0'), capture_output=True)

    def test_legacy_exact_argv_cwd_and_failure(self):
        for step, expected in [('install', 'npm|ci'), ('format', 'npx|prettier --check .'),
                               ('lint', 'npx|eslint --max-warnings 0 .'), ('types', 'npx|astro check'), ('build', 'npm|run build')]:
            self.assertEqual(self.invoke('legacy', step).returncode, 0)
            self.assertEqual(self.log.read_text().splitlines()[-1], expected + '|' + str(self.root))
            self.assertNotEqual(self.invoke('legacy', step, failure=True).returncode, 0)

    def test_central_tools_never_download_and_missing_tool_refuses(self):
        for step in ('format', 'lint', 'types'):
            self.assertNotEqual(self.invoke('central', step).returncode, 0)
        self.assertFalse(self.log.exists())
        tools = self.root / 'node_modules/.bin'
        tools.mkdir(parents=True)
        for tool in ('prettier', 'eslint', 'astro'):
            file = tools / tool
            file.write_text(self.stub)
            file.chmod(0o755)
        for step in ('format', 'lint', 'types'):
            self.assertEqual(self.invoke('central', step).returncode, 0)
        self.assertNotIn('npx|', self.log.read_text())

    def test_only_selected_script_identifier_is_forwarded(self):
        self.assertEqual(self.invoke('central', 'script', 'test:unit').returncode, 0)
        self.assertIn('npm|run test:unit|', self.log.read_text())
        before = self.log.read_text()
        for name in ('--if-present', 'test;touch marker', '', '../../evil'):
            self.assertNotEqual(self.invoke('central', 'script', name).returncode, 0)
        self.assertEqual(before, self.log.read_text())
        self.assertNotEqual(self.invoke('legacy', 'script', 'test').returncode, 0)

    def test_wrapper_preserves_defaults_setup_and_every_language_step(self):
        action = yaml.safe_load((ROOT / 'actions/ci-astro/action.yml').read_text())
        steps = action['runs']['steps']
        self.assertEqual(action['inputs']['github-actions-mode']['default'], 'changed')
        self.assertNotIn('omit-common', action['inputs'])
        self.assertEqual(next(s for s in steps if s['name'] == 'Install exact locked runtime')['with']['version'], '2026.8.3')
        cores = [s for s in steps if 'check_astro.sh' in s.get('run', '')]
        self.assertEqual(len(cores), 5)
        self.assertTrue(all('legacy' in s['run'] and s['working-directory'] == '${{ inputs.working-directory }}' for s in cores))
