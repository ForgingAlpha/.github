"""A1-A3/A7-A10: actual resolver, frozen security proof and published shell."""
import base64
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
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from route_fixture_support import context, seed_file
spec = importlib.util.spec_from_file_location('route_under_test', ROOT/'actions/ci-org-baseline/scripts/proposal_route.py')
route = importlib.util.module_from_spec(spec); sys.modules[spec.name] = route; spec.loader.exec_module(route)


class Api:
    def __init__(self, gets, pages=None):
        self.gets = gets; self.page_values = pages or {}; self.reads = []

    def get(self, path, fresh=False):
        self.reads.append(path)
        if path not in self.gets: raise ValueError('required metadata unavailable: '+path)
        return copy.deepcopy(self.gets[path])

    def pages(self, path, fresh=False):
        self.reads.append(path)
        if path not in self.page_values: raise ValueError('required pages unavailable')
        return copy.deepcopy(self.page_values[path])


def fixture(base='dev', head='task/example', repository='ForgingAlpha/alphaapps-site', number=17):
    data = b'# Owner\n\nApplication.\n\n## End\n'
    repo = {'full_name': repository, 'id': {'ForgingAlpha/.github':1137664016,'ForgingAlpha/control-plane':739528598}.get(repository,1151008489)}
    task = 'main' if repository in ('ForgingAlpha/.github','ForgingAlpha/control-plane') else 'dev'
    evidence = {'adoption_branch':task,'adopted_commit':'a'*40,
                'files':[{'path':'PROJECT.md','sha256':hashlib.sha256(data).hexdigest()}],
                'regions':[{'path':'PROJECT.md','start':'# Owner','end':'## End','sha256':hashlib.sha256(b'\nApplication.\n\n').hexdigest()}],
                'reconciliation_sha256':'c'*64,'governing_sha256':'f'*64,
                'rule':'named-control' if task=='main' else 'application','persistent_sources':['main'] if task=='main' else ['dev','main']}
    evidence.update(context=context({'PROJECT.md':('100644',data)}),transition={'kind':'none'})
    entry = {'repository':repository,'repository_id':repo['id'], 'proposal':{'task_target':task,
             'promotions':[] if task=='main' else [{'source':'dev','target':'main','same_repository':True}], 'evidence':evidence},
             'participation':{'mode':'metadata-only'}}
    pr = {'number':number,'state':'open','user':{'login':'human'},
          'base':{'repo':repo,'ref':base,'sha':'a'*40},'head':{'repo':repo,'ref':head,'sha':'b'*40}}
    event = {'repository':repo,'number':number,'pull_request':copy.deepcopy(pr)}
    gets = {f'repos/{repository}/pulls/{number}':pr,
            f'repos/{repository}/compare/{"a"*40}...{"a"*40}':{'status':'identical','merge_base_commit':{'sha':'a'*40}},
            f'repos/{repository}/contents/PROJECT.md?ref={"a"*40}':{'type':'file','encoding':'base64','size':len(data),
              'content':base64.b64encode(data).decode(),'sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()},
            f'repos/{repository}/git/commits/{"b"*40}':{'tree':{'sha':'e'*40}}}
    for name in {task,base}:gets[f'repos/{repository}/branches/{route.quote(name,safe="")}']={'commit':{'sha':'a'*40},'protected':True}
    gets[f'repos/{repository}/branches/{route.quote(head,safe="")}']={'commit':{'sha':'b'*40},'protected':head in ('main','dev','staging')}
    gets[f'repos/{repository}']=copy.deepcopy(repo)
    gets[f'repos/{repository}/contents/PROJECT.md?ref={"b"*40}']=copy.deepcopy(gets[f'repos/{repository}/contents/PROJECT.md?ref={"a"*40}'])
    if head==task:
        evidence['adopted_commit']='b'*40
        gets[f'repos/{repository}/compare/{"b"*40}...{"b"*40}']={'status':'identical','merge_base_commit':{'sha':'b'*40}}
        gets[f'repos/{repository}/contents/PROJECT.md?ref={"b"*40}']=gets[f'repos/{repository}/contents/PROJECT.md?ref={"a"*40}']
    api=Api(gets)
    for revision in ('a'*40,'b'*40):seed_file(api,repository,revision,'PROJECT.md',data)
    return entry,event,api


def security_fixture(projection=False, branch='main'):
    spec = importlib.util.spec_from_file_location('source_fixtures',ROOT/'actions/security-patch/tests/test_security_patch.py')
    module = importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    api = module.admission_fixture() if projection else module.DefaultSourceAcceptanceTest().source_api(branch)
    number = 44 if projection else 17
    pr = api.gets[f'repos/ForgingAlpha/alphaapps-site/pulls/{number}']
    pr['head'].setdefault('ref','security/exact')
    for side in ('base','head'):pr[side]['repo']={'full_name':'ForgingAlpha/alphaapps-site','id':1151008489}
    entry,event,extra = fixture(base=branch,head=pr['head']['ref'],number=number)
    event['pull_request']=copy.deepcopy(pr)
    # Add only ordinary adapter observations; keep actual S1 commit/tree/PR proof intact.
    for key,value in extra.gets.items():api.gets.setdefault(key,value)
    api.gets['repos/ForgingAlpha/alphaapps-site'].update({'full_name':'ForgingAlpha/alphaapps-site','id':1151008489})
    for revision in ('a'*40,'b'*40):seed_file(api,'ForgingAlpha/alphaapps-site',revision,'PROJECT.md',b'# Owner\n\nApplication.\n\n## End\n')
    return entry,event,Api(api.gets,api.page_values),module


def dependency_set_fixture(directory, row, projection=False, pairs=None):
    """Synthetic provider/owner metadata over actual complete Git objects."""
    sys.path.insert(0, str(ROOT/'actions/security-patch/tests'))
    from test_dependency_sets import GitProvider
    branch = 'main' if row['repository']=='ForgingAlpha/.github' else 'dev'
    api = GitProvider(directory, row, pairs=pairs, branch=branch)
    if projection:
        source=api.classified_source()
        api_evidence=__import__('test_dependency_sets').sp.create_projection(api,source,'main',None,None)[1]
        number=44
    else:
        number=17
    pr=api.pulls[number]
    repo={'full_name':api.repo,'id':api.identity,'default_branch':branch}
    for side in ('head','base'):pr[side]['repo']=copy.deepcopy(repo)
    entry,_,_=fixture(pr['base']['ref'],pr['head']['ref'],api.repo,number)
    entry['repository_id']=api.identity
    entry['proposal']['evidence']['adopted_commit']=api.base
    authority=api.refs[entry['proposal']['evidence']['adoption_branch']]
    gets=copy.deepcopy(api.gets)
    gets[api.endpoint('')]=repo
    gets.update({api.endpoint('pulls/'+str(n)):copy.deepcopy(p) for n,p in api.pulls.items()})
    for name,revision in api.refs.items():
        gets[api.endpoint('git/ref/heads/'+name)]={'object':{'sha':revision}}
        gets[api.endpoint('branches/'+route.quote(name,safe=''))]={'commit':{'sha':revision},'protected':name in ('main','dev')}
    gets[api.endpoint('branches/'+route.quote(pr['head']['ref'],safe=''))]={'commit':{'sha':pr['head']['sha']},'protected':False}
    gets[api.endpoint('compare/'+api.base+'...'+authority)]={'status':'identical' if authority==api.base else 'ahead','merge_base_commit':{'sha':api.base}}
    data=b'# Owner\n\nApplication.\n\n## End\n'
    for revision in {authority,api.base,pr['base']['sha'],pr['head']['sha']}:
        gets[api.endpoint('contents/PROJECT.md?ref='+revision)]={'type':'file','encoding':'base64','size':len(data),
            'content':base64.b64encode(data).decode(),'sha':api.git('rev-parse',revision+':PROJECT.md')}
    pages=copy.deepcopy(api.page_values)
    for head,checks in api.checks.items():pages[api.endpoint('commits/'+head+'/check-runs?filter=all&per_page=100')]=[{'check_runs':checks}]
    pages[api.endpoint('pulls?state=open&base=main&per_page=100')]=[[p for p in api.pulls.values() if p['state']=='open' and p['base']['ref']=='main']]
    event={'repository':repo,'number':number,'pull_request':copy.deepcopy(pr)}
    return entry,event,Api(gets,pages)


class ProposalTests(unittest.TestCase):
    def test_actual_set_guard_full_typed_output_and_missing_proof_refusal(self):
        import yaml
        rows=json.loads((ROOT/'actions/security-patch/profiles.json').read_text())['repositories']
        rows=[r for r in rows if '/' in r['pairs'][0]['lock_path']]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for index,row in enumerate(rows):
                for projected in (False,True):
                    if projected and row['repository']=='ForgingAlpha/.github':continue
                    entry,event,api=dependency_set_fixture(root/f'git-{index}-{projected}',row,projected)
                    expected=route.admission(api,event,entry,'d'*40)
                    self.assertEqual(expected['schema_version'],2)
                    self.assertEqual(expected['proof']['profile'],'manifest-lock-set-v1')
                    self.assertEqual(expected['proof']['dependency_pairs'],row['pairs'])
                    bundle=root/f'bundle-{index}-{projected}';bundle.mkdir()
                    for name in set(route.CHECKING_FILES)|{'actions/ci-foundation/scripts/foundation_source.py'}:
                        target=bundle/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
                    (bundle/'actions/ci-org-baseline/enrollment.json').write_text(json.dumps({'schema_version':3,'repositories':[entry]}))
                    (bundle/'event').write_text(json.dumps(event));(bundle/'gets').write_text(json.dumps(api.gets));(bundle/'pages').write_text(json.dumps(api.page_values))
                    gh=bundle/'gh';gh.write_text('#!/usr/bin/env python3\nimport json,os,sys\na=sys.argv[1:]\nassert a[0]=="api" and "--method" not in a\nv=json.load(open(os.environ["FIXTURE_ROOT"]+("/pages" if "--paginate" in a else "/gets")))\nif a[-1] not in v:sys.exit("missing fixture proof")\nprint(json.dumps(v[a[-1]]))\n');gh.chmod(0o700)
                    output=bundle/'output';output.write_text('outer=untouched\n')
                    env={**os.environ,'PATH':str(bundle)+':'+os.environ['PATH'],'FIXTURE_ROOT':str(bundle),
                        'GITHUB_ACTION_PATH':str(bundle/'actions/ci-merge-flow'),'GITHUB_EVENT_PATH':str(bundle/'event'),
                        'GITHUB_EVENT_NAME':'pull_request','GITHUB_REPOSITORY':row['repository'],'GITHUB_REPOSITORY_ID':str(row['repository_id']),
                        'GITHUB_OUTPUT':str(output)}
                    script=yaml.safe_load((bundle/'actions/ci-merge-flow/action.yml').read_text())['runs']['steps'][0]['run']
                    result=subprocess.run(['bash','-e','-c',script],env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr)
                    actual=json.loads(result.stdout)
                    self.assertEqual(actual['proof'],expected['proof'])
                    self.assertEqual(actual['schema_version'],2)
                    self.assertEqual(output.read_text(),'outer=untouched\n')
                    if projected:
                        key=f"repos/{row['repository']}/commits/{event['pull_request']['head']['sha']}/check-runs?filter=all&per_page=100"
                        api.page_values[key]=[{'check_runs':[]}]
                    else:
                        key=f"repos/{row['repository']}/pulls/17/commits?per_page=100"
                        api.page_values[key][0][0]['commit']['verification']['verified']=False
                    (bundle/'pages').write_text(json.dumps(api.page_values))
                    result=subprocess.run(['bash','-e','-c',script],env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,1,result.stderr);self.assertEqual(result.stdout,'')
                    self.assertEqual(output.read_text(),'outer=untouched\n')

    def test_named_control_and_metadata_object_boundaries(self):
        entry,event,api=fixture('main','task/change','ForgingAlpha/.github')
        entry['proposal']['evidence']['rule']='owner-declared'
        with self.assertRaisesRegex(ValueError,'named control'):route.validate_entry(entry)
        for malformed in ([],None,True):
            with self.subTest(value=malformed),self.assertRaisesRegex(ValueError,'object'):
                route.get(Api({'repos/example':malformed}),'repos/example')

    def test_public_self_row_matches_controlling_repository_files(self):
        rows=route.catalog(json.loads((ROOT/'actions/ci-org-baseline/enrollment.json').read_text()))
        entry=next(r for r in rows if r['repository']=='ForgingAlpha/.github')
        for item in entry['proposal']['evidence']['files']:
            self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['sha256'])

    def test_exact_routes_and_default_independence(self):
        for repo,base,head,kind in [('ForgingAlpha/.github','main','task/fix','ordinary-task'),
                ('ForgingAlpha/control-plane','main','task/fix','ordinary-task'),
                ('ForgingAlpha/alphaapps-site','dev','task/fix','ordinary-task'),
                ('ForgingAlpha/alphaapps-site','main','dev','ordinary-promotion')]:
            with self.subTest(repo=repo,base=base,head=head):
                entry,event,api=fixture(base,head,repo);event['repository']['default_branch']='unrelated'
                result=route.admission(api,event,entry,'d'*40)
                self.assertEqual(result['kind'],kind);self.assertEqual(result['head_sha'],'b'*40)
                self.assertNotIn('eligible',result)

    def test_missing_dev_cannot_exempt_task_main(self):
        entry,event,api=fixture('main')
        self.assertIsNone(route.ordinary(entry,route.subject(event,entry),False))
        with patch.object(route.security,'verify_ci_admission',side_effect=route.security.PolicyError('no security proof')) as verifier:
            with self.assertRaisesRegex(route.security.PolicyError,'no security proof'):
                route.admission(api,event,entry,'d'*40)
            verifier.assert_called_once()
        api.gets.pop('repos/ForgingAlpha/alphaapps-site/branches/dev')
        with self.assertRaisesRegex(ValueError,'unavailable'):route.admission(api,event,entry,'d'*40)

    def test_source_identity_protection_and_staging_refuse(self):
        for base,head in [('main','task/x'),('dev','main'),('dev','staging'),('staging','dev')]:
            with self.subTest(base=base,head=head):
                entry,event,api=fixture(base,head)
                with self.assertRaises((ValueError,route.security.PolicyError)):
                    route.admission(api,event,entry,'d'*40)
        entry,event,api=fixture();event['pull_request']['head']['repo']={'full_name':'fork/site','id':2}
        with self.assertRaisesRegex(ValueError,'fork'):route.admission(api,event,entry,'d'*40)
        entry,event,api=fixture();api.gets['repos/ForgingAlpha/alphaapps-site/branches/task%2Fexample']['protected']=True
        with self.assertRaises(ValueError):route.admission(api,event,entry,'d'*40)

    def test_source_closure_and_ancestry_are_not_region_only(self):
        for mutation in ('body','ancestry','region','identity'):
            entry,event,api=fixture()
            if mutation=='body':entry['proposal']['evidence']['files'][0]['sha256']='0'*64
            if mutation=='ancestry':api.gets[f'repos/{entry["repository"]}/compare/{"a"*40}...{"a"*40}']['status']='diverged'
            if mutation=='region':entry['proposal']['evidence']['regions'][0]['start']='absent'
            if mutation=='identity':event['repository']['id']=42
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):route.admission(api,event,entry,'d'*40)

    def test_schema_retires_old_routes_and_metadata_is_not_enrollment(self):
        entry,_,_=fixture()
        for version in (1,2):
            with self.assertRaisesRegex(ValueError,'unsupported enrollment schema'):route.catalog({'schema_version':version,'repositories':[entry]})
        rows=route.catalog({'schema_version':3,'repositories':[entry]})
        with self.assertRaisesRegex(ValueError,'metadata-only'):route.select(rows,entry['repository'],entry['repository_id'],central=True)
        for key,value in [('release_route',{'kind':'direct'}),('class','application')]:
            bad=copy.deepcopy(entry);bad[key]=value
            with self.assertRaisesRegex(ValueError,'fields'):route.catalog({'schema_version':3,'repositories':[bad]})

    def test_actual_source_and_projection_proofs_conserve_distinctions(self):
        for projection in (False,True):
            with self.subTest(projection=projection):
                entry,event,api,_=security_fixture(projection)
                result=route.admission(api,event,entry,'d'*40)
                self.assertEqual(result['kind'],'security-projection' if projection else 'dependabot-source')
                route.validate_admission(result,event,entry,'d'*40,result['head_tree_sha'])
                self.assertNotIn('eligible',result)
                if not projection:self.assertNotIn('ghsa_set',result['proof'])
                bad=copy.deepcopy(result);bad['kind']='ordinary-task'
                with self.assertRaises(ValueError):route.validate_admission(bad,event,entry,'d'*40,result['head_tree_sha'])
                bad=copy.deepcopy(result);bad['proof']['source_head']='f'*40
                with self.assertRaises((ValueError,route.security.PolicyError)):route.validate_admission(bad,event,entry,'d'*40,result['head_tree_sha'])

    def test_drift_after_first_subject_cannot_emit_admission(self):
        entry,event,api=fixture();original=api.get;reads=[0]
        def read(name,fresh=False):
            value=original(name,fresh)
            if '/pulls/' in name:
                reads[0]+=1
                if reads[0]>1:value['head']['sha']='f'*40
            return value
        api.get=read
        with self.assertRaisesRegex(ValueError,'moved'):route.admission(api,event,entry,'d'*40)

    def test_original_security_child_pollutes_inherited_output_negative_control(self):
        # Actual unchanged producer, not an imitation echo: demonstrates N10.
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output';output.write_text('plan=original\n')
            code='import importlib.util,sys; s=importlib.util.spec_from_file_location("fixture",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.security_patch.GhApi=lambda:m.DefaultSourceAcceptanceTest().source_api(); raise SystemExit(m.security_patch.cli(["verify-ci-admission","--repository","ForgingAlpha/alphaapps-site","--pull-request","17"]))'
            result=subprocess.run([sys.executable,'-c',code,str(ROOT/'actions/security-patch/tests/test_security_patch.py')],env={**os.environ,'GITHUB_OUTPUT':str(output)},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('plan=original\nverified=true\nadmission_kind=dependabot-source\n',output.read_text())
            self.assertEqual(result.stdout,'')

    def test_base_head_and_forward_owner_closure(self):
        entry,event,api=fixture();repo=entry['repository']
        key=f'repos/{repo}/contents/PROJECT.md?ref={"b"*40}'
        seed_file(api,repo,'b'*40,'PROJECT.md',b'changed controlling prose')
        with self.assertRaises(ValueError):route.admission(api,event,entry,'d'*40)
        entry,event,api=fixture();repo=entry['repository']
        api.gets[f'repos/{repo}/branches/dev']['commit']['sha']='c'*40
        event['pull_request']['base']['sha']='c'*40
        api.gets[f'repos/{repo}/pulls/17']['base']['sha']='c'*40
        api.gets[f'repos/{repo}/compare/{"a"*40}...{"c"*40}']={'status':'ahead','merge_base_commit':{'sha':'a'*40}}
        api.gets[f'repos/{repo}/contents/PROJECT.md?ref={"c"*40}']=copy.deepcopy(api.gets[f'repos/{repo}/contents/PROJECT.md?ref={"a"*40}'])
        seed_file(api,repo,'c'*40,'PROJECT.md',b'# Owner\n\nApplication.\n\n## End\n')
        self.assertEqual(route.admission(api,event,entry,'d'*40)['kind'],'ordinary-task')

    def test_actual_wrapper_source_projection_and_output_isolation(self):
        import yaml
        for variant in ('source-main','source-dev','projection','ordinary','ordinary-control','ordinary-cp','ordinary-promotion','bad-source','bad-projection'):
            projection = 'projection' in variant
            entry,event,api,_=security_fixture(projection, 'dev' if variant=='source-dev' else 'main')
            if variant=='ordinary':entry,event,api=fixture()
            if variant=='ordinary-control':entry,event,api=fixture('main','task/example','ForgingAlpha/.github')
            if variant=='ordinary-cp':entry,event,api=fixture('main','task/example','ForgingAlpha/control-plane')
            if variant=='ordinary-promotion':entry,event,api=fixture('main','dev')
            bad=variant.startswith('bad-')
            if variant=='bad-source':api.gets[f"repos/{entry['repository']}/pulls/{event['number']}"]['draft']=True
            if variant=='bad-projection':api.gets[f"repos/{entry['repository']}/git/commits/{event['pull_request']['head']['sha']}"]['tree']['sha']='f'*40
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);bundle=root/'bundle';bundle.mkdir()
                files=set(route.CHECKING_FILES)|{'actions/ci-foundation/scripts/foundation_source.py'}
                for name in files:
                    dest=bundle/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
                (bundle/'actions/ci-org-baseline/enrollment.json').write_text(json.dumps({'schema_version':3,'repositories':[entry]}))
                (root/'event').write_text(json.dumps(event));(root/'gets').write_text(json.dumps(api.gets));(root/'pages').write_text(json.dumps(api.page_values))
                gh=root/'gh';gh.write_text('#!/usr/bin/env python3\nimport json,os,sys\nargs=sys.argv[1:]\nassert args[0]=="api" and "--method" not in args\nname=args[-1]\nfile="pages" if "--paginate" in args else "gets"\nvalues=json.load(open(os.environ["FIXTURE_ROOT"]+"/"+file))\nif name not in values: sys.exit("required metadata unavailable")\nprint(json.dumps(values[name]))\n');gh.chmod(0o700)
                output=root/'output';output.write_text('outer=unchanged\n')
                env={**os.environ,'PATH':str(root)+':'+os.environ['PATH'],'FIXTURE_ROOT':str(root),
                     'GITHUB_EVENT_PATH':str(root/'event'),'GITHUB_EVENT_NAME':'pull_request','GITHUB_REPOSITORY':entry['repository'],
                     'GITHUB_REPOSITORY_ID':str(entry['repository_id']),'GITHUB_ACTION_PATH':str(bundle/'actions/ci-merge-flow'),'GITHUB_OUTPUT':str(output)}
                action=yaml.safe_load((bundle/'actions/ci-merge-flow/action.yml').read_text())
                self.assertEqual(action['runs']['steps'][0]['if'],"${{ github.event_name == 'pull_request' }}")
                result=subprocess.run(['bash','-e','-c',action['runs']['steps'][0]['run']],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,1 if bad else 0,result.stderr)
                if bad:
                    self.assertEqual(result.stdout,'');self.assertIn('refused',result.stderr)
                else:
                    self.assertEqual(json.loads(result.stdout)['kind'],'ordinary-promotion' if variant=='ordinary-promotion' else 'ordinary-task' if variant.startswith('ordinary') else 'security-projection' if projection else 'dependabot-source')
                    self.assertNotIn('eligible',json.loads(result.stdout))
                stdout_result=subprocess.run(['bash','-e','-c',action['runs']['steps'][0]['run']],env={**env,'GITHUB_OUTPUT':''},capture_output=True,text=True)
                self.assertEqual((stdout_result.returncode,stdout_result.stdout,stdout_result.stderr),(result.returncode,result.stdout,result.stderr))
                self.assertEqual(output.read_text(),'outer=unchanged\n')

    def test_directed_changed_closure_and_promotion_without_future_authority(self):
        for promotion in (False,True):
            entry,event,api=fixture('main' if promotion else 'dev','dev' if promotion else 'task/change')
            evidence=entry['proposal']['evidence'];repo=entry['repository']
            # Reconciliation explicitly preaccepts these exact successor bytes;
            # the synthetic provider is not evidence of a real owner adoption.
            old=b'# Owner\n\nApplication.\n\n## End\n';new=b'# Owner\n\nApplication revised.\n\n## End\n'
            successor={k:copy.deepcopy(evidence[k]) for k in ('files','regions','context')}
            successor['files'][0]['sha256']=hashlib.sha256(new).hexdigest()
            successor['regions'][0]['sha256']=hashlib.sha256(b'\nApplication revised.\n\n').hexdigest()
            successor['context']=context({'PROJECT.md':('100644',new)})
            evidence['adopted_commit']='a'*40
            evidence['transition']={'kind':'forward','predecessor':{k:copy.deepcopy(evidence[k]) for k in ('files','regions','context')},'successor':successor,'reconciliation_sha256':'9'*64}
            if promotion:
                api.gets[f'repos/{repo}/compare/{"a"*40}...{"b"*40}']={'status':'ahead','merge_base_commit':{'sha':'a'*40}}
            seed_file(api,repo,'b'*40,'PROJECT.md',new)
            route.catalog({'schema_version':3,'repositories':[entry]})
            result=route.admission(api,event,entry,'d'*40)
            self.assertEqual(result['source_correspondence'],{'authority':1 if promotion else 0,'subjects':[0,1]})
            self.assertEqual(result['kind'],'ordinary-promotion' if promotion else 'ordinary-task')
            seed_file(api,repo,'a'*40,'PROJECT.md',new);seed_file(api,repo,'b'*40,'PROJECT.md',old)
            with self.assertRaisesRegex(ValueError,'transition'):route.admission(api,event,entry,'d'*40)
            seed_file(api,repo,'b'*40,'PROJECT.md',new+b'unknown\n')
            with self.assertRaisesRegex(ValueError,'closure'):route.admission(api,event,entry,'d'*40)

    def test_new_project_and_entrypoint_redirect_invalidate_complete_context(self):
        entry,event,api=fixture();repo=entry['repository'];e=entry['proposal']['evidence']
        data=b'# Owner\n\nApplication.\n\n## End\n'
        e['files'][0]['path']='docs/architecture.md';e['regions'][0]['path']='docs/architecture.md'
        e['context']=context({})
        for revision in ('a'*40,'b'*40):
            seed_file(api,repo,revision,'PROJECT.md',None)
            seed_file(api,repo,revision,'docs/architecture.md',data)
        self.assertEqual(route.admission(api,event,entry,'d'*40)['kind'],'ordinary-task')
        for name,mode,value in [('PROJECT.md','100644',b'new conflicting context'),('AGENTS.md','120000',b'other.md'),('CLAUDE.md','100644',b'redirected instructions')]:
            seed_file(api,repo,'b'*40,name,value,mode)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'closure'):route.admission(api,event,entry,'d'*40)
            seed_file(api,repo,'b'*40,name,None)
        tree=api.gets[f'repos/{repo}/git/commits/{"a"*40}']['tree']['sha']
        api.gets[f'repos/{repo}/git/trees/{tree}']['truncated']=True
        with self.assertRaises(ValueError):route.admission(api,event,entry,'d'*40)

    def test_result_job_declares_full_fresh_projection_read_set(self):
        import yaml
        workflow=yaml.safe_load((ROOT/'.github/workflows/org-baseline.yml').read_text())
        permissions=workflow['jobs']['result'].get('permissions',workflow['permissions'])
        self.assertEqual(permissions,{'contents':'read','pull-requests':'read','checks':'read'})
        for missing in (None,'checks','pull-requests','contents'):
            entry,event,api,_=security_fixture(True);reads=[]
            scopes=dict(permissions)
            if missing:scopes.pop(missing)
            original_get,original_pages=api.get,api.pages
            def check(path):
                needed='checks' if 'check-runs' in path else 'pull-requests' if '/pulls' in path else 'contents'
                reads.append((path,needed))
                if scopes.get(needed)!='read':raise ValueError('fixture capability refusal: '+needed)
            def get(path,fresh=False):check(path);return original_get(path,fresh)
            def pages(path,fresh=False):check(path);return original_pages(path,fresh)
            api.get,api.pages=get,pages
            if missing:
                with self.subTest(missing=missing),self.assertRaisesRegex(ValueError,'capability refusal'):route.admission(api,event,entry,'d'*40)
            else:
                self.assertEqual(route.admission(api,event,entry,'d'*40)['kind'],'security-projection')
                self.assertEqual({scope for _,scope in reads},{'contents','pull-requests','checks'})


if __name__=='__main__':unittest.main()
