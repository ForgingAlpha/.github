"""REQ-027 replaces staging and branch-presence exemptions with owner evidence."""
import os
import subprocess
import unittest
from test_proposal_route import ROOT, route, fixture


class MergeFlowBehaviorTest(unittest.TestCase):
    def test_same_repository_dev_promotes_only_to_main(self):
        entry,event,api=fixture('main','dev')
        self.assertEqual(route.admission(api,event,entry,'d'*40)['kind'],'ordinary-promotion')
        entry,event,api=fixture('staging','dev')
        with self.assertRaises(ValueError):route.admission(api,event,entry,'d'*40)

    def test_fork_dev_has_no_ordinary_dev_exemption(self):
        entry,event,api=fixture('main','dev')
        event['pull_request']['head']['repo']={'full_name':'contributor/example','id':99}
        with self.assertRaisesRegex(ValueError,'fork'):route.admission(api,event,entry,'d'*40)

    def test_missing_dev_is_not_main_only_authority(self):
        entry,event,api=fixture('main','feature')
        api.gets.pop('repos/ForgingAlpha/alphaapps-site/branches/dev')
        with self.assertRaises(ValueError):route.admission(api,event,entry,'d'*40)
        entry,event,api=fixture('main','feature','ForgingAlpha/.github')
        self.assertEqual(route.admission(api,event,entry,'d'*40)['kind'],'ordinary-task')

    def test_obsolete_cli_modes_cannot_select_routes(self):
        helper=ROOT/'actions/ci-merge-flow/scripts/check_merge_flow.sh'
        for mode in ('legacy-observed','declared-route','', 'direct','staged'):
            result=subprocess.run(['bash',str(helper),mode],env={**os.environ,'DECLARED_ROUTE':'direct'},capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Unsupported admission interface',result.stderr)
