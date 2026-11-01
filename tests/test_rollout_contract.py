"""Main-source delivery and recovery contract, replacing retired tag writers."""

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class MainSourceContractTest(unittest.TestCase):
    def workflow(self, name):
        return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())

    def test_source_candidate_and_postmerge_ci_are_read_only(self):
        workflow = self.workflow('ci.yml')
        triggers = workflow.get('on', workflow.get(True))
        self.assertEqual(triggers['pull_request']['branches'], ['main'])
        self.assertEqual(triggers['push']['branches'], ['main'])
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(workflow['jobs']['CI']['name'], 'CI')
        for job in workflow['jobs'].values():
            self.assertNotIn('write', (job.get('permissions') or {}).values())
        steps = workflow['jobs']['CI']['steps']
        local = {step['uses'] for step in steps if step.get('uses', '').startswith('./')}
        self.assertTrue({'./actions/ci-alphaapps-policy', './actions/ci-dependency-review',
                         './actions/ci-github-actions', './actions/ci-markdown',
                         './actions/ci-update-ownership'} <= local)
        # A local candidate parent may not acquire remote-main siblings for self-CI.
        self.assertNotIn('./actions/ci-shell', local)
        scripts = '\n'.join(step.get('run', '') for step in steps)
        self.assertIn('shellcheck -S style', scripts)
        self.assertIn('python3 -m unittest discover -s tests', scripts)

    def test_no_active_tag_promotion_or_rollback_writer(self):
        for name in ('release.yml', 'rollback-v1.yml'):
            self.assertFalse((ROOT / '.github/workflows' / name).exists(), name)
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            text = path.read_text()
            self.assertNotIn('V1_ROLLOUT_ENABLED', text, path)
            self.assertNotRegex(text, r'refs/tags/v1(?:[\s:"$]|-rollout|-rollback)', path)
            self.assertNotRegex(text, r'git push[^\n]*(?:--force|refs/heads/main)', path)

    def test_all_executable_first_party_callers_select_literal_main(self):
        paths = [*(ROOT / '.github/workflows').glob('*.yml'),
                 *(ROOT / 'workflow-templates').glob('*.yml'),
                 *(ROOT / 'actions').glob('*/action.yml')]
        count = 0
        for path in paths:
            for line in path.read_text().splitlines():
                if line.lstrip().startswith('#'):
                    continue
                match = re.search(r'uses:\s*(ForgingAlpha/\.github/[^\s]+)', line)
                if match:
                    count += 1
                    self.assertTrue(match[1].endswith('@main'), (path, line))
        self.assertGreater(count, 20)

    def test_human_reviewed_recovery_preserves_evidence_and_withdrawals(self):
        procedure = (ROOT / 'docs/operator-checklist.md').read_text()
        for obligation in ('exact-head human', 'human merge into main',
                           'before/after commits', 'withdrawn catalog approvals',
                           'forward fix', 'complete current rule',
                           'outcome-unknown', 'effective dev/main rules'):
            self.assertIn(obligation, procedure)
        self.assertNotIn('Keep `V1_ROLLOUT_ENABLED`', procedure)
        self.assertNotIn('protected `v1` release', procedure)


if __name__ == '__main__':
    unittest.main()
