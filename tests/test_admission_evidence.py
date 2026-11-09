"""Unified source contract acceptance; every owner record here is synthetic."""
import copy
import json
import unittest

from test_org_baseline import baseline

ae = baseline.admission
D0, D1, S0, M0 = ('a' * 40, 'b' * 40, 'c' * 40, 'e' * 40)


def subject(purpose='feature', **changes):
    target_ref = {'feature': 'dev', 'consolidation': 'dev', 'promotion': 'staging', 'repair': 'staging', 'reconciliation': 'dev', 'staging-main': 'main'}[purpose]
    value = dict(repository='ForgingAlpha/layas-learning-lab-site', repository_id=1420939261,
                 task='task/fixture', task_revision=1, purpose=purpose, source_ref='feature/fixture', head=D1,
                 creation_base=S0 if purpose in ('repair', 'staging-main') else D0,
                 target_ref=target_ref, target={'dev': D0, 'staging': S0, 'main': M0}[target_ref],
                 checking_repository='ForgingAlpha/.github', checking_sha='d' * 40, profile='astro', outcome='proposal', pr=1)
    if purpose == 'staging-main':
        value.update(source_ref='staging', head=S0)
    value.update(changes)
    return ae.Subject.parse(value)


class Reader:
    """Fixture acquisition boundary, deliberately not an operational adapter."""
    def __init__(self, records):
        self.records = records
        self.outcome = None
        self.requests = []

    def acquire(self, request):
        self.requests.append(request)
        return self.outcome if self.outcome is not None else ae.Available(ae.encoded(self.records))


def resign(records, role):
    records[role]['ref']['payload_sha256'] = ae.digest(records[role]['body'])


def context(s):
    value = s.value(); purpose = value['purpose']
    observation = {'dev': D1 if purpose == 'promotion' else value['creation_base'], 'staging': S0, 'main': M0}
    observation[value['target_ref']] = value['target']
    observation = {name: observation[name] for name in ae.required_branches(s)}
    members = [{'task': 'task/a', 'revision': 1, 'integrated': D0}, {'task': 'task/b', 'revision': 1, 'integrated': D1}]
    data = {
        'task': {'task': value['task'], 'revision': value['task_revision'], 'subject_sha256': ae.digest(value)},
        'workspace': {'task': value['task'], 'creation_ref': 'staging' if purpose in ('repair', 'staging-main') else 'dev', 'creation_base': value['creation_base']},
        'migration': {'profile': value['profile']},
        'scheduling': {'hold': 'held' if purpose in ('consolidation', 'promotion') else 'clear', 'claim': None if purpose == 'feature' else 'release/1', 'lifecycle': 'none' if purpose == 'feature' else 'continuing', 'effects': 'staging' if purpose in ('repair','reconciliation','staging-main') else 'none', 'resolved_dev': None, 'resolved_staging': None, 'resolved_main': None},
        'release': {'claim': 'release/1', 'frozen_dev': value['creation_base'], 'snapshot': D1, 'staging': S0, 'main': M0,
                    'intended_target': value['target'], 'intended_integration': {'head':value['head'],'target':value['target'],'result':{'kind':'tree','sha':'f'*40},'evidence_sha256':'f'*64} if purpose in ('promotion','staging-main') else None, 'staged_repairs': [], 'reconciled_repairs': [], 'prior_qualification': {'head': S0, 'results_sha256': 'f'*64, 'state': 'completed-success'} if purpose == 'staging-main' else None, 'expected_members': members, 'accepted_members': copy.deepcopy(members)},
    }
    records = {}
    bindings = tuple((role, 'owner/' + role) for role in ae.required_roles(s))
    for role, record in bindings:
        names = ae.SCHEDULING_PREDICATES if role == 'scheduling' else ae.RELEASE_PREDICATES if role == 'release' else ae.COMMON[role]
        body = {'repository': value['repository'], 'repository_id': value['repository_id'], 'decision': 'accepted', 'validity': 'current',
                'predicates': {name: {'state': 'satisfied', 'evidence_sha256': 'f' * 64} for name in names}, 'data': data[role]}
        records[role] = {'ref': {'role': role, 'record': record, 'decision_revision': 1, 'state_revision': 1, 'payload_sha256': ae.digest(body),
                                'predecessor': None, 'coordinator': 'coordinator/assigned', 'succession_sha256': 'f' * 64}, 'body': body}
    reader = Reader(records)
    return ae.UnifiedContext(s, bindings, reader), observation


class ContractTests(unittest.TestCase):
    def test_all_purposes_and_every_migration_gate(self):
        for purpose in sorted(ae.PURPOSES):
            with self.subTest(purpose=purpose):
                ctx, observations = context(subject(purpose))
                self.assertEqual(ae.acquire(ctx, observations)['outcome'], 'ProposalEligible')
                ctx.reader.records['migration']['body']['predicates']['qualified']['state'] = 'unknown'
                resign(ctx.reader.records, 'migration')
                with self.assertRaisesRegex(ValueError, 'not satisfied'):
                    ae.acquire(ctx, observations)

    def test_strict_subject_domains_and_duplicate_json(self):
        for key, value in [('repository_id', True), ('task_revision', 0), ('purpose', 'security'), ('head', 'main'),
                           ('checking_sha', 'A' * 40), ('profile', 'bootstrap'), ('pr', True), ('trusted', True)]:
            raw = subject().value(); raw[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): ae.Subject.parse(raw)
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'[' * 2000, b' ' * 65537):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError): ae.decode(raw)
        ctx, obs = context(subject(creation_base=None))
        with self.assertRaisesRegex(ValueError, 'creation baseline'): ae.acquire(ctx, obs)

    def test_all_states_and_owner_currentness_are_explicit(self):
        for state in (True, False, 'unknown', 'unavailable', 'refuted', 'not-applicable', None):
            ctx, obs = context(subject());ctx.reader.records['task']['body']['predicates']['fact_accepted']['state'] = state;resign(ctx.reader.records, 'task')
            with self.subTest(state=state), self.assertRaises(ValueError): ae.acquire(ctx, obs)
        for kind, values in [('decision', ('rejected', 'indeterminate')), ('validity', ('revoked', 'superseded', 'expired', 'unknown'))]:
            for value in values:
                ctx, obs = context(subject());ctx.reader.records['task']['body'][kind] = value;resign(ctx.reader.records, 'task')
                with self.subTest(kind=kind,value=value), self.assertRaises(ValueError): ae.acquire(ctx, obs)
        for outcome, message in [(ae.Unavailable(), 'unavailable'), (ae.Invalid(), 'invalid'), (ae.Conflicting(), 'conflicting')]:
            ctx, obs = context(subject());ctx.reader.outcome = outcome
            with self.assertRaisesRegex(ValueError, message): ae.acquire(ctx, obs)

    def test_owner_provenance_totality_and_sanitized_failures(self):
        ctx, obs = context(subject())
        ctx.reader.records['task']['body']['data']['revision'] = True
        # Integrity is valid, so the nested type check must reject the alias.
        resign(ctx.reader.records, 'task')
        with self.assertRaisesRegex(ValueError, 'invalid owner revision'):
            ae.acquire(ctx, obs)
        for mutate in (
            lambda r:r['task']['ref'].update(record='owner/other'),
            lambda r:r['task']['ref'].update(decision_revision=True),
            lambda r:r['task']['ref'].update(state_revision=0),
            lambda r:r['task']['ref'].update(payload_sha256='0'*64),
            lambda r:r['task']['body'].update(raw_api='secret-fixture-sentinel'),
            lambda r:r['task']['body'].update(repository_id=True),
            lambda r:r.update(unrelated={'trusted':True}),
        ):
            ctx,obs=context(subject());mutate(ctx.reader.records)
            with self.assertRaises(ValueError) as caught:ae.acquire(ctx,obs)
            self.assertNotIn('secret-fixture-sentinel',str(caught.exception))
        ctx,obs=context(subject())
        def broken(request):raise ValueError('secret-fixture-sentinel')
        ctx.reader.acquire=broken
        with self.assertRaisesRegex(ValueError,'owner acquisition unavailable') as caught:ae.acquire(ctx,obs)
        self.assertNotIn('secret-fixture-sentinel',str(caught.exception))

    def test_independent_refs_exact_requests_and_same_repo_hold(self):
        ctx, obs = context(subject());before = ae.acquire(ctx, obs)
        unrelated = {'release': 1};unrelated['release'] += 1
        self.assertEqual(before, ae.acquire(ctx, obs))
        self.assertEqual(tuple(role for role, _ in ctx.reader.requests[-1].bindings), ('migration','scheduling','task','workspace'))
        self.assertNotIn('release', before['records'])
        ctx.reader.records['scheduling']['ref']['state_revision'] += 1
        self.assertNotEqual(before, ae.acquire(ctx, obs))
        ctx.reader.records['scheduling']['body']['data'].update(hold='held', claim='release/1', lifecycle='continuing');resign(ctx.reader.records,'scheduling')
        with self.assertRaisesRegex(ValueError, 'held'): ae.acquire(ctx,obs)
        ctx.reader.records['scheduling']['body']['data'].update(hold='released',effects='staging');resign(ctx.reader.records,'scheduling')
        self.assertEqual(ae.acquire(ctx,obs)['outcome'],'ProposalEligible')

    def test_distinct_promotion_baselines_and_complete_unique_scope(self):
        ctx, obs = context(subject('promotion'))
        self.assertEqual((ctx.subject.value()['creation_base'],ctx.subject.value()['head'],ctx.subject.value()['target']), (D0,D1,S0))
        ae.acquire(ctx,obs)
        for key,value in [('snapshot', D0), ('intended_target', D1), ('claim','release/other')]:
            bad=copy.deepcopy(ctx.reader.records);bad['release']['body']['data'][key]=value;resign(bad,'release')
            with self.subTest(key=key),self.assertRaises(ValueError):ae.evaluate(ctx.request(),ae.Available(ae.encoded(bad)),obs)
        for mode in ('duplicate','omit','different'):
            bad=copy.deepcopy(ctx.reader.records);data=bad['release']['body']['data']
            if mode=='duplicate':
                a,b=data['expected_members'];data['expected_members']=[a,a,b];data['accepted_members']=[a,b,b]
            elif mode=='omit':data['accepted_members']=data['accepted_members'][:1]
            else:data['accepted_members'][0]['revision']=2
            resign(bad,'release')
            with self.subTest(mode=mode),self.assertRaises(ValueError):ae.evaluate(ctx.request(),ae.Available(ae.encoded(bad)),obs)
        integration=ae.acquire(ctx,obs)['records']['release']['body']['data']['intended_integration']
        self.assertNotEqual(integration['result']['sha'],ctx.subject.value()['head'])
        for mutation in ('missing','none','missing-result','unknown-result','result-alias'):
            bad=copy.deepcopy(ctx.reader.records);data=bad['release']['body']['data']
            if mutation=='missing':del data['intended_integration']
            elif mutation=='none':data['intended_integration']=None
            elif mutation=='missing-result':del data['intended_integration']['result']
            elif mutation=='unknown-result':data['intended_integration']['result']={'kind':'tree','sha':None}
            else:data['intended_integration']['result']={'kind':'source','sha':D1}
            resign(bad,'release')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):ae.evaluate(ctx.request(),ae.Available(ae.encoded(bad)),obs)
        for key in ('head','target'):
            bad=copy.deepcopy(ctx.reader.records);bad['release']['body']['data']['intended_integration'][key]=M0;resign(bad,'release')
            with self.assertRaisesRegex(ValueError,'integration subject'):ae.evaluate(ctx.request(),ae.Available(ae.encoded(bad)),obs)
        for predicate in ('complete_scope','corrections_reviewed','batch_reviewed','intended_integration_reviewed'):
            bad=copy.deepcopy(ctx.reader.records);bad['release']['body']['predicates'][predicate]['state']='unknown';resign(bad,'release')
            with self.assertRaises(ValueError):ae.evaluate(ctx.request(),ae.Available(ae.encoded(bad)),obs)
        with self.assertRaises(ValueError):ae.acquire(ctx,{**obs,'dev':D0})

    def test_no_change_has_no_fabricated_pr_and_rechecks_actual_baselines(self):
        for purpose in ('consolidation','reconciliation'):
            ctx,obs=context(subject(purpose,outcome='no-change',pr=None,head=D0))
            self.assertEqual(ae.acquire(ctx,obs)['outcome'],'NoProposalRequired')
            with self.assertRaises(ValueError):ae.acquire(ctx,{**obs,'dev':D1})
            ctx.reader.records['release']['body']['predicates']['no_change_reviewed']['state']='unknown';resign(ctx.reader.records,'release')
            with self.assertRaises(ValueError):ae.acquire(ctx,obs)
        with self.assertRaises(ValueError):subject('reconciliation',outcome='no-change',pr=1)

    def test_cancel_suspend_and_actual_effect_obligations(self):
        for state in ('cancelled','suspended'):
            ctx,obs=context(subject('promotion'));ctx.reader.records['scheduling']['body']['data']['lifecycle']=state;resign(ctx.reader.records,'scheduling')
            with self.assertRaisesRegex(ValueError,'not continuing'):ae.acquire(ctx,obs)
        ctx,obs=context(subject());schedule=ctx.reader.records['scheduling']['body'];schedule['data'].update(hold='released',claim='release/1',lifecycle='cancelled',resolved_dev=D0,resolved_staging=S0,resolved_main=M0);obs.update(staging=S0,main=M0)
        for name in ('withdrawal_verified','effects_resolved','safe_baseline'):
            schedule['predicates'][name]['state']='not-applicable';resign(ctx.reader.records,'scheduling')
            with self.assertRaises(ValueError):ae.acquire(ctx,obs)
            schedule['predicates'][name]['state']='satisfied'
        schedule['data']['effects']='staging';schedule['predicates']['effects_reconciled']['state']='not-applicable';resign(ctx.reader.records,'scheduling')
        with self.assertRaises(ValueError):ae.acquire(ctx,obs)
        schedule['predicates']['effects_reconciled']['state']='satisfied';resign(ctx.reader.records,'scheduling');ae.acquire(ctx,obs)

    def test_nonheld_cancellation_cannot_skip_recovery_by_using_clear(self):
        for hold in ('clear', 'released'):
            for effects in ('none', 'staging', 'main'):
                ctx, obs = context(subject())
                schedule = ctx.reader.records['scheduling']['body']
                schedule['data'].update(hold=hold, claim='release/1', lifecycle='cancelled', effects=effects,
                                        resolved_dev=D0, resolved_staging=S0, resolved_main=M0)
                obs.update(staging=S0, main=M0)
                resign(ctx.reader.records, 'scheduling')
                with self.subTest(hold=hold, effects=effects):
                    self.assertEqual(ae.acquire(ctx, obs)['outcome'], 'ProposalEligible')
                    required = ['withdrawal_verified', 'effects_resolved', 'safe_baseline']
                    if effects != 'none':
                        required.append('effects_reconciled')
                    for predicate in required:
                        schedule['predicates'][predicate]['state'] = 'not-applicable'
                        resign(ctx.reader.records, 'scheduling')
                        with self.subTest(predicate=predicate), self.assertRaisesRegex(ValueError, 'not satisfied'):
                            ae.acquire(ctx, obs)
                        schedule['predicates'][predicate]['state'] = 'satisfied'
                    resign(ctx.reader.records, 'scheduling')
                    with self.assertRaisesRegex(ValueError, 'incomplete branch observations'):
                        ae.acquire(ctx, {'dev': D0})
                    with self.assertRaisesRegex(ValueError, 'resolved baseline'):
                        ae.acquire(ctx, {**obs, 'main': D1})

    def test_continuing_staged_effects_need_verified_hold_release_when_clear(self):
        ctx, obs = context(subject())
        schedule = ctx.reader.records['scheduling']['body']
        schedule['data'].update(hold='clear', claim='release/1', lifecycle='continuing')
        schedule['predicates']['hold_release_verified']['state'] = 'not-applicable'
        resign(ctx.reader.records, 'scheduling')
        # A claim before any staged effects need not fabricate a completed release.
        self.assertEqual(ae.acquire(ctx, obs)['outcome'], 'ProposalEligible')
        for effects in ('staging', 'main'):
            schedule['data']['effects'] = effects
            schedule['predicates']['hold_release_verified']['state'] = 'not-applicable'
            resign(ctx.reader.records, 'scheduling')
            with self.subTest(effects=effects), self.assertRaisesRegex(ValueError, 'not satisfied'):
                ae.acquire(ctx, obs)
            schedule['predicates']['hold_release_verified']['state'] = 'satisfied'
            resign(ctx.reader.records, 'scheduling')
            self.assertEqual(ae.acquire(ctx, obs)['outcome'], 'ProposalEligible')

    def test_prior_phase_completion_and_wrong_route_or_observations(self):
        for state in ('pending', 'failure', 'unavailable'):
            ctx,obs=context(subject('staging-main'))
            ctx.reader.records['release']['body']['data']['prior_qualification']['state']=state;resign(ctx.reader.records,'release')
            with self.subTest(state=state),self.assertRaisesRegex(ValueError,'prior staged qualification'):ae.acquire(ctx,obs)
        for purpose in sorted(ae.PURPOSES):
            for key,value in [('source_ref','main'),('target_ref','main' if purpose!='staging-main' else 'dev')]:
                ctx,obs=context(subject(purpose,**{key:value}))
                with self.subTest(purpose=purpose,key=key),self.assertRaises(ValueError):ae.acquire(ctx,obs)
        for ref in ('refs/heads/dev','feature/../main','feature//task'):
            with self.assertRaises(ValueError):subject(source_ref=ref)
        ctx,obs=context(subject('repair'))
        with self.assertRaises(ValueError):ae.acquire(ctx,{k:v for k,v in obs.items() if k!='staging'})
        ctx,obs=context(subject('reconciliation'))
        ctx.reader.records['release']['body']['data']['staged_repairs']=[{'task':'repair/1','revision':1,'integrated':S0}];resign(ctx.reader.records,'release')
        with self.assertRaisesRegex(ValueError,'repair identities'):ae.acquire(ctx,obs)
        ctx,obs=context(subject('reconciliation'));ctx.reader.records['release']['body']['predicates']['later_dev_preserved']['state']='unknown';resign(ctx.reader.records,'release')
        with self.assertRaises(ValueError):ae.acquire(ctx,obs)

    def test_frozen_roundtrip_and_no_trust_flags_or_completion_alias(self):
        ctx,obs=context(subject());projection=ae.acquire(ctx,obs)
        self.assertEqual(ae.frozen(ae.encoded(projection),ctx),projection)
        for key in ('trusted','stage','current_result','prior_ready','pending_complete'):
            bad=copy.deepcopy(projection);bad[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):ae.frozen(bad,ctx)
        ctx.reader.records['task']['body']['predicates']['preparation_reviewed']['state']='unknown';resign(ctx.reader.records,'task')
        with self.assertRaises(ValueError):ae.acquire(ctx,obs)
        ctx,obs=context(subject('staging-main'));ctx.reader.records['release']['body']['predicates']['prior_qualification']['state']='unknown';resign(ctx.reader.records,'release')
        with self.assertRaises(ValueError):ae.acquire(ctx,obs)
        with self.assertRaisesRegex(ValueError,'unavailable'):ae.acquire(ae.UnifiedContext(ctx.subject,ctx.bindings),obs)
