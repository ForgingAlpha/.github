"""F2 typed stage composition. Provider and product commands are synthetic.

Real Git, admission, plan serialization and finalization run here. This is not
full product/A11 or hosted caller qualification.
"""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_org_baseline import ApplicationFixture, FakeApi, baseline, bind_fixture, row, successful_needs, ROOT
from test_proposal_route import Api
from route_fixture_support import git_data

sys.path.insert(0, str(ROOT/'actions/security-patch/tests'))
from test_security_patch import source_candidate_fixture, sha
from test_dependency_sets import GitProvider, sp


class SetCompositionTests(unittest.TestCase):
    def test_nested_npm_cargo_single_multi_admission_plan_lanes_finalizer(self):
        declaration=json.loads((ROOT/'actions/security-patch/profiles.json').read_text())
        rows=[r for r in declaration['repositories'] if r['repository'] in ('ForgingAlpha/turnkeyleads-app','ForgingAlpha/container-foundation')]
        with tempfile.TemporaryDirectory() as directory:
            serial=0
            for source_row in rows:
                for pairs in ([source_row['pairs'][0]], [source_row['pairs'][1]], source_row['pairs']):
                    serial+=1
                    with self.subTest(repository=source_row['repository'],pairs=pairs):
                        kinds=tuple(('astro' if p['ecosystem']=='npm' else 'rust',p['manifest_path'].rsplit('/',1)[0]) for p in pairs)
                        f=ApplicationFixture(Path(directory)/str(serial),kinds=kinds)
                        old_repo=f.entry['repository'];repo=source_row['repository']
                        f.entry.update(repository=repo,repository_id=source_row['repository_id'])
                        f.runtime['assignments'][repo]=f.runtime['assignments'].pop(old_repo)
                        f.git('remote','set-url','origin','https://github.com/'+repo)
                        f.base=f.head
                        f.git('update-ref','refs/remotes/origin/dev',f.base)
                        for pair in pairs:
                            value='{"lockfileVersion":3,"packages":{},"version":"2"}' if pair['ecosystem']=='npm' else 'version = 4\n# security fixture delta\n'
                            f.write(pair['lock_path'],value)
                        f.commit();bind_fixture(f,f.entry,'docs/route.md')
                        tree=f.git('rev-parse',f.head+'^{tree}').strip()
                        base_tree=f.git('rev-parse',f.base+'^{tree}').strip()
                        merge=f.git('commit-tree',tree,'-p',f.base,'-p',f.head,'-m','synthetic provider merge').strip()
                        original=source_candidate_fixture()
                        replacements={'ForgingAlpha/alphaapps-site':repo,sha('a'):f.base,sha('b'):f.head,sha('c'):merge,sha('d'):base_tree,sha('e'):tree}
                        def translate(value):
                            encoded=json.dumps(value)
                            for before,after in replacements.items():encoded=encoded.replace(before,after)
                            return json.loads(encoded)
                        api=Api(translate(original.gets),translate(original.page_values))
                        api.gets.update(git_data(f.root,repo,[f.base,f.head,merge]))
                        api.gets[f'repos/{repo}'].update(id=source_row['repository_id'])
                        api.gets[f'repos/{repo}/git/ref/heads/dev']={'object':{'sha':f.base}}
                        pr=api.gets[f'repos/{repo}/pulls/17']
                        pr.update(changed_files=len(pairs),commits=1)
                        pr['head']['ref']='dependabot/security'
                        for side in ('head','base'):pr[side]['repo']={'full_name':repo,'id':source_row['repository_id']}
                        api.page_values[f'repos/{repo}/pulls/17/files?per_page=100']=[[{'filename':p['lock_path'],'status':'modified'} for p in pairs]]
                        api.gets[f'repos/{repo}/branches/dev']={'commit':{'sha':f.base},'protected':True}
                        api.gets[f'repos/{repo}/branches/dependabot%2Fsecurity']={'commit':{'sha':f.head},'protected':False}
                        api.gets[f'repos/{repo}/compare/{f.base}...{f.base}']={'status':'identical','merge_base_commit':{'sha':f.base}}
                        event={'repository':{'full_name':repo,'id':source_row['repository_id']},'number':17,'pull_request':copy.deepcopy(pr)}
                        f.event=lambda:copy.deepcopy(event)
                        record=baseline.route.admission(api,event,row(f.entry),'d'*40)
                        self.assertEqual(record['schema_version'],2)
                        self.assertEqual(record['proof']['dependency_pairs'],pairs)
                        plan=baseline.app_plan(f.root,event,f.entry,'d'*40,f.runtime,admission_record=record)
                        self.assertEqual(plan['schema_version'],4)
                        self.assertEqual(plan['required_jobs'],['baseline','static','tests'])
                        original_integrity=baseline.application_integrity
                        def integrity(root, inventory, entry, *args):return original_integrity(root,inventory,entry,f.runtime)
                        calls=[]
                        def command(argv,cwd,env=None,**kwargs):
                            calls.append(argv)
                            if '--version' in argv:return b'rustc 1.90.0 (fixture)\n' if 'rustc' in argv else b'v24.18.0\n'
                            if 'metadata' in argv:
                                manifest=str(cwd/'member/Cargo.toml')
                                return json.dumps({'version':1,'workspace_root':str(cwd),'workspace_members':[manifest],
                                    'packages':[{'id':manifest,'manifest_path':manifest,'dependencies':[]}]}).encode()
                        output=Path(directory)/f'output-{serial}';output.write_text('outer=untouched\n')
                        environment={'GITHUB_REPOSITORY':repo,'GITHUB_REPOSITORY_ID':str(source_row['repository_id']),
                                     'GITHUB_TOKEN':'synthetic-read-only','GITHUB_OUTPUT':str(output)}
                        class CurrentApi:
                            def get(self,path):return api.get(path.lstrip('/'))
                        with patch.dict(os.environ,environment),patch.object(baseline.route.security,'GhApi',return_value=api), \
                             patch.object(baseline,'Api',return_value=CurrentApi()),patch.object(baseline,'application_integrity',side_effect=integrity), \
                             patch.object(baseline,'application_common'),patch.object(baseline,'checked',side_effect=command):
                            baseline.staged_main(SimpleNamespace(stage='admit'),f.root,event,[f.entry],'d'*40)
                            fields=dict(l.split('=',1) for l in output.read_text().splitlines())
                            self.assertEqual(json.loads(fields['plan']),plan)
                            os.environ['BASELINE_PLAN']=fields['plan']
                            for stage in ('preflight','install'):baseline.staged_main(SimpleNamespace(stage=stage),f.root,event,[f.entry],'d'*40)
                            receipts={}
                            for stage in ('static','tests'):
                                output.write_text('')
                                baseline.staged_main(SimpleNamespace(stage=stage),f.root,event,[f.entry],'d'*40)
                                receipts[stage]=dict(l.split('=',1) for l in output.read_text().splitlines())['receipt']
                            os.environ['BASELINE_NEEDS']=json.dumps(successful_needs(plan,**receipts))
                            captured=io.StringIO()
                            with redirect_stdout(captured):baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                            self.assertEqual(json.loads(captured.getvalue())['admission_sha256'],plan['admission_sha256'])
                            for defect in ('schema','pair','profile','digest'):
                                wrong=copy.deepcopy(plan)
                                if defect=='schema':wrong['schema_version']=3
                                elif defect=='pair':wrong['admission']['proof']['dependency_pairs']=[]
                                elif defect=='profile':wrong['admission']['proof']['profile']='root-npm-v1'
                                else:wrong['admission_sha256']='0'*64
                                os.environ['BASELINE_PLAN']=json.dumps(wrong)
                                with self.assertRaises((ValueError,baseline.route.security.PolicyError)):
                                    baseline.staged_main(SimpleNamespace(stage='preflight'),f.root,event,[f.entry],'d'*40)
                            for status in ('failure','skipped','cancelled'):
                                needs=successful_needs(plan,**receipts);needs['tests']['result']=status
                                with self.assertRaises(ValueError):baseline.aggregate(plan,needs)
                            # Live proof cannot be replaced by a green frozen plan.
                            api.page_values[f'repos/{repo}/pulls/17/commits?per_page=100'][0][0]['commit']['verification']['verified']=False
                            with self.assertRaises(baseline.route.security.PolicyError):
                                baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                        self.assertTrue(any('central' in c for c in calls))


    def test_set_projection_full_stages_conserve_proof_and_reprove_live_evidence(self):
        """Real set producer/stage engine; provider, runtime and subprocess results are fixtures."""
        rows=json.loads((ROOT/'actions/security-patch/profiles.json').read_text())['repositories']
        rows=[r for r in rows if r['repository'] in ('ForgingAlpha/turnkeyleads-app','ForgingAlpha/container-foundation')]
        with tempfile.TemporaryDirectory() as directory:
            serial=0
            for declaration in rows:
                for pairs in ([declaration['pairs'][0]],[declaration['pairs'][1]],declaration['pairs']):
                    serial+=1
                    with self.subTest(repository=declaration['repository'],pairs=pairs):
                        kinds=tuple(('astro' if p['ecosystem']=='npm' else 'rust',p['manifest_path'].rsplit('/',1)[0]) for p in pairs)
                        f=ApplicationFixture(Path(directory)/str(serial),kinds=kinds)
                        repo=declaration['repository'];old_repo=f.entry['repository']
                        f.entry.update(repository=repo,repository_id=declaration['repository_id'])
                        f.runtime['assignments'][repo]=f.runtime['assignments'].pop(old_repo)
                        f.git('remote','set-url','origin','https://github.com/'+repo)
                        f.base=f.head;production=f.base
                        f.git('update-ref','refs/remotes/origin/main',production)
                        for pair in pairs:
                            f.write(pair['lock_path'],'{"lockfileVersion":3,"packages":{},"version":"2"}' if pair['ecosystem']=='npm' else 'version = 4\n# security delta\n')
                        f.commit();source_head=f.head
                        bind_fixture(f,f.entry,'docs/route.md')
                        tree=f.git('rev-parse',f.head+'^{tree}').strip()
                        merge=f.git('commit-tree',tree,'-p',f.base,'-p',f.head,'-m','synthetic source merge').strip()
                        original=source_candidate_fixture()
                        replacements={'ForgingAlpha/alphaapps-site':repo,sha('a'):f.base,sha('b'):f.head,sha('c'):merge,
                                      sha('d'):f.git('rev-parse',f.base+'^{tree}').strip(),sha('e'):tree}
                        def translate(value):
                            encoded=json.dumps(value)
                            for before,after in replacements.items():encoded=encoded.replace(before,after)
                            return json.loads(encoded)
                        # Use the existing actual-Git writer/provider fixture on this complete
                        # application tree, so the real security producer creates the proof.
                        provider=GitProvider.__new__(GitProvider)
                        provider.root=f.root;provider.repo=repo;provider.identity=declaration['repository_id']
                        provider.pairs=copy.deepcopy(pairs);provider.branch='dev';provider.base=f.base
                        provider.head=f.head;provider.merge=merge;provider.main=production
                        provider.env={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null',
                            'GIT_AUTHOR_NAME':'fixture','GIT_AUTHOR_EMAIL':'fixture@example.invalid',
                            'GIT_COMMITTER_NAME':'fixture','GIT_COMMITTER_EMAIL':'fixture@example.invalid',
                            'GIT_AUTHOR_DATE':'2026-08-16T12:00:00Z','GIT_COMMITTER_DATE':'2026-08-16T12:00:00Z'}
                        provider.gets=translate(original.gets);provider.page_values=translate(original.page_values)
                        provider.gets.update(git_data(f.root,repo,[f.base,f.head,merge]))
                        provider.gets[provider.endpoint('git/commits/'+merge)]['committer']={'date':f.git('show','-s','--format=%cI',merge).strip()}
                        provider.gets[provider.endpoint('')].update(id=provider.identity)
                        provider.posts=[];provider.checks={};provider.lose_response=None
                        # The product fixture has symlink instruction aliases. Preserve every
                        # original mode when the synthetic provider creates a Git tree.
                        modes={line.split('\t')[1]:line.split()[0] for line in f.git('ls-tree','-r',production).splitlines()}
                        def projection_tree(leaves):
                            def build(group,prefix=''):
                                direct={};children={}
                                for name,oid in group.items():
                                    if '/' in name:
                                        first,rest=name.split('/',1);children.setdefault(first,{})[rest]=oid
                                    else:direct[name]=(modes.get(prefix+name,'100644'),'blob',oid)
                                for name,nested in children.items():direct[name]=('040000','tree',build(nested,prefix+name+'/'))
                                entries=[{'path':n,'mode':m,'type':k,'sha':o} for n,(m,k,o) in sorted(direct.items())]
                                raw=b''.join(f"{e['mode']} {e['type']} {e['sha']}\t{e['path']}\0".encode() for e in entries)
                                oid=provider.git('mktree','-z',data=raw)
                                provider.gets[provider.endpoint('git/trees/'+oid)]={'truncated':False,'tree':entries}
                                return oid
                            return build(leaves)
                        provider.tree=projection_tree
                        provider.ghsas=('GHSA-abcd-efgh-ijkl',);provider.refs={'dev':f.base,'main':production}
                        provider.changed=sorted(p['lock_path'] for p in pairs)
                        source_pr=provider.gets[provider.endpoint('pulls/17')]
                        source_pr.update(changed_files=len(pairs),commits=1)
                        source_pr['head']['ref']='dependabot/security'
                        identity={'full_name':repo,'id':provider.identity}
                        for side in ('head','base'):source_pr[side]['repo']=copy.deepcopy(identity)
                        provider.pulls={17:source_pr}
                        provider.page_values[provider.endpoint('pulls/17/files?per_page=100')]=[[{'filename':p,'status':'modified'} for p in provider.changed]]
                        source=provider.classified_source()
                        _,projection=sp.create_projection(provider,source,'main',None,None)
                        pr=provider.pulls[44]
                        for side in ('head','base'):pr[side]['repo']=copy.deepcopy(identity)
                        f.head=projection.projection_head;f.base=projection.production_base;f.branch='main'
                        f.git('checkout','--detach',f.head)
                        f.git('update-ref','refs/remotes/origin/dev',merge)
                        gets=copy.deepcopy(provider.gets);pages=copy.deepcopy(provider.page_values)
                        gets.update({provider.endpoint('pulls/'+str(n)):copy.deepcopy(p) for n,p in provider.pulls.items()})
                        for branch,revision in provider.refs.items():
                            gets[provider.endpoint('git/ref/heads/'+branch)]={'object':{'sha':revision}}
                            gets[provider.endpoint('branches/'+baseline.route.quote(branch,safe=''))]={'commit':{'sha':revision},'protected':branch in ('dev','main')}
                        gets[provider.endpoint('compare/'+production+'...'+merge)]={'status':'ahead','merge_base_commit':{'sha':production}}
                        for head,checks in provider.checks.items():pages[provider.endpoint('commits/'+head+'/check-runs?filter=all&per_page=100')]=[{'check_runs':copy.deepcopy(checks)}]
                        pages[provider.endpoint('pulls?state=open&base=main&per_page=100')]=[[copy.deepcopy(pr)]]
                        api=Api(gets,pages)
                        event={'repository':identity,'number':44,'pull_request':copy.deepcopy(pr)}
                        f.event=lambda:copy.deepcopy(event)
                        record=baseline.route.admission(api,event,row(f.entry),'d'*40)
                        self.assertEqual(record['schema_version'],2)
                        self.assertEqual(record['kind'],'security-projection')
                        self.assertEqual(record['proof'],projection.attestation())
                        self.assertEqual(record['proof']['dependency_pairs'],pairs)
                        plan=baseline.app_plan(f.root,event,f.entry,'d'*40,f.runtime,admission_record=record)
                        self.assertEqual(plan['schema_version'],4)
                        self.assertEqual(plan['admission'],record)
                        self.assertEqual(plan['admission_sha256'],baseline.route.digest(record))
                        original_integrity=baseline.application_integrity
                        def integrity(root,inventory,entry,*args):return original_integrity(root,inventory,entry,f.runtime)
                        calls=[]
                        def command(argv,cwd,env=None,**kwargs):
                            calls.append(argv)
                            if 'validate_update_ownership.py' in ' '.join(argv):self.assertNotIn('GITHUB_OUTPUT',env)
                            if '--version' in argv:return b'rustc 1.90.0 (fixture)\n' if 'rustc' in argv else b'v24.18.0\n'
                            if 'metadata' in argv:
                                manifest=str(cwd/'member/Cargo.toml')
                                return json.dumps({'version':1,'workspace_root':str(cwd),'workspace_members':[manifest],
                                    'packages':[{'id':manifest,'manifest_path':manifest,'dependencies':[]}]}).encode()
                        output=Path(directory)/f'projection-output-{serial}';output.write_text('outer=untouched\n')
                        env={'GITHUB_REPOSITORY':repo,'GITHUB_REPOSITORY_ID':str(provider.identity),'GITHUB_TOKEN':'synthetic-read-only','GITHUB_OUTPUT':str(output)}
                        class CurrentApi:
                            def get(self,path):return api.get(path.lstrip('/'))
                        with patch.dict(os.environ,env),patch.object(baseline.route.security,'GhApi',return_value=api), \
                             patch.object(baseline,'Api',return_value=CurrentApi()),patch.object(baseline,'application_integrity',side_effect=integrity), \
                             patch.object(baseline,'checked',side_effect=command),patch.object(baseline.route,'admission',wraps=baseline.route.admission) as live:
                            # Actual application_common executes; all its external commands are
                            # intercepted above, including installers, so this test installs nothing.
                            baseline.staged_main(SimpleNamespace(stage='admit'),f.root,event,[f.entry],'d'*40)
                            self.assertEqual(live.call_count,2)
                            fields=dict(line.split('=',1) for line in output.read_text().splitlines())
                            self.assertEqual(set(fields),{'outer','plan','profile','producer','result_name','mise_version'})
                            self.assertEqual(fields['outer'],'untouched')
                            self.assertEqual(json.loads(fields['plan']),plan)
                            os.environ['BASELINE_PLAN']=fields['plan']
                            for stage in ('preflight','install'):baseline.staged_main(SimpleNamespace(stage=stage),f.root,event,[f.entry],'d'*40)
                            receipts={}
                            for stage in ('static','tests'):
                                output.write_text('outer=untouched\n')
                                baseline.staged_main(SimpleNamespace(stage=stage),f.root,event,[f.entry],'d'*40)
                                fields_out=dict(line.split('=',1) for line in output.read_text().splitlines())
                                self.assertEqual(set(fields_out),{'outer','receipt'})
                                self.assertEqual(fields_out['outer'],'untouched')
                                receipts[stage]=fields_out['receipt']
                                self.assertEqual(json.loads(receipts[stage])['plan_sha256'],baseline.plan_digest(plan))
                            self.assertEqual(live.call_count,2,'token-free stages unexpectedly requested live provider proof')
                            needs=successful_needs(plan,**receipts);os.environ['BASELINE_NEEDS']=json.dumps(needs)
                            final=io.StringIO()
                            with redirect_stdout(final):baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                            self.assertEqual(live.call_count,4,'finalizer must reprove both before and after aggregation')
                            receipt=json.loads(final.getvalue())
                            self.assertEqual(receipt['schema_version'],4)
                            self.assertEqual(receipt['admission_kind'],'security-projection')
                            self.assertEqual(receipt['admission_sha256'],baseline.route.digest(record))
                            self.assertEqual(receipt['plan_sha256'],baseline.plan_digest(plan))
                            self.assertEqual(receipt['head_tree_sha'],projection.projection_tree)
                            self.assertEqual(receipt['required_results'],{'baseline':'success','static':'success','tests':'success'})
                            # Missing and mixed proofs/receipts cannot inherit a prior success.
                            for defect in ('missing-proof','mixed-pair','old-schema','mixed-source'):
                                wrong=copy.deepcopy(plan)
                                if defect=='missing-proof':wrong['admission']['proof']={}
                                elif defect=='mixed-pair':wrong['admission']['proof']['dependency_pairs']=[]
                                elif defect=='old-schema':wrong['schema_version']=3
                                else:wrong['checking_fingerprints']['actions/security-patch/profiles.json']='0'*64
                                os.environ['BASELINE_PLAN']=json.dumps(wrong)
                                with self.assertRaises((ValueError,baseline.route.security.PolicyError)):
                                    baseline.staged_main(SimpleNamespace(stage='preflight'),f.root,event,[f.entry],'d'*40)
                            os.environ['BASELINE_PLAN']=json.dumps(plan)
                            for defect in ('missing','mixed','stale'):
                                wrong=copy.deepcopy(needs)
                                if defect=='missing':wrong['tests']['outputs'].pop('receipt')
                                elif defect=='mixed':wrong['static']['outputs']['source_sha']='0'*40
                                else:
                                    stale=json.loads(wrong['tests']['outputs']['receipt']);stale['plan_sha256']='0'*64
                                    wrong['tests']['outputs']['receipt']=json.dumps(stale)
                                os.environ['BASELINE_NEEDS']=json.dumps(wrong)
                                with self.assertRaises(ValueError):baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                            os.environ['BASELINE_NEEDS']=json.dumps(needs)
                            check_path=provider.endpoint('commits/'+f.head+'/check-runs?filter=all&per_page=100')
                            saved=copy.deepcopy(api.page_values[check_path])
                            original_aggregate=baseline.aggregate
                            def withdraw_after_aggregate(current_plan,current_needs):
                                original_aggregate(current_plan,current_needs)
                                api.page_values[check_path]=[{'check_runs':[]}]
                            before=live.call_count;refused_output=io.StringIO()
                            with patch.object(baseline,'aggregate',side_effect=withdraw_after_aggregate),redirect_stdout(refused_output):
                                with self.assertRaises(baseline.route.security.PolicyError):
                                    baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                            self.assertEqual(live.call_count,before+2)
                            self.assertEqual(refused_output.getvalue(),'','failed final reproof emitted success')
                            api.page_values[check_path]=[{'check_runs':[]}]
                            with self.assertRaises(baseline.route.security.PolicyError):baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                            api.page_values[check_path]=saved
                            api.gets[provider.endpoint('git/ref/heads/main')]={'object':{'sha':source_head}}
                            with self.assertRaises((ValueError,baseline.route.security.PolicyError)):
                                baseline.staged_main(SimpleNamespace(stage='finalize'),f.root,event,[f.entry],'d'*40)
                        self.assertIn(['mise','install','--locked'],calls)
                        self.assertTrue(any('validate_update_ownership.py' in ' '.join(c) for c in calls))
                        self.assertTrue(any('central' in c for c in calls))


if __name__=='__main__':unittest.main()
