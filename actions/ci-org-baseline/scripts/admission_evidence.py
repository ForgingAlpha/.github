"""Closed consumer projection for unified admission; no operational owner reader.

These types preserve existing decisions, not a lifecycle registry or authentication
mechanism. Only trusted executing code supplies a reader. JSON cannot select one.
"""
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Protocol

LIMIT = 65536
PURPOSES = frozenset(('feature', 'consolidation', 'promotion', 'repair', 'reconciliation', 'staging-main'))
PERSISTENT = frozenset(('dev', 'staging', 'main'))
STATES = frozenset(('satisfied', 'refuted', 'unknown', 'not-applicable', 'unavailable'))
COMMON = {
    'task': ('authorized', 'fact_accepted', 'preparation_reviewed', 'ordinary_eligible', 'drift_reviewed'),
    'workspace': ('creation_verified',),
    'migration': ('qualified',),
    'scheduling': ('coherent',),
}
RELEASE_REQUIRED = {
    'consolidation': ('complete_scope', 'prior_reconciled', 'batch_reviewed', 'corrections_reviewed'),
    'promotion': ('complete_scope', 'prior_reconciled', 'batch_reviewed', 'corrections_reviewed', 'snapshot_verified', 'intended_integration_reviewed'),
    'repair': ('staged_correspondence', 'repair_bounded'),
    'reconciliation': ('staged_correspondence', 'later_dev_preserved', 'reconciliation_reviewed'),
    'staging-main': ('complete_scope', 'snapshot_verified', 'staged_correspondence', 'prior_qualification', 'main_integration_reviewed'),
}
SCHEDULING_PREDICATES = ('coherent', 'hold_communicated', 'hold_release_verified', 'withdrawal_verified', 'effects_resolved', 'safe_baseline', 'effects_reconciled')
RELEASE_PREDICATES = tuple(sorted({p for values in RELEASE_REQUIRED.values() for p in values} | {'no_change_reviewed'}))


class Refused(ValueError):
    """Sanitized contract refusal, never containing source payloads."""


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def shape(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), 'invalid admission fields')


def identity(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}', value), 'invalid logical identity')
    return value


def revision(value):
    require(type(value) is int and 0 < value < 2**53, 'invalid owner revision')


def sha(value, length=40):
    require(type(value) is str and re.fullmatch('[a-f0-9]{%d}' % length, value), 'invalid exact content identity')
    return value


def encoded(value):
    try:
        result = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Refused('invalid admission encoding') from None
    require(len(result) <= LIMIT, 'admission exceeds bounded complete input')
    return result


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def decode(raw):
    require(type(raw) in (bytes, str), 'invalid admission encoding')
    require(len(raw.encode() if isinstance(raw, str) else raw) <= LIMIT, 'admission exceeds bounded complete input')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate admission JSON key')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False, 'invalid JSON number'))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, Refused):
            raise
        raise Refused('invalid admission JSON') from None


@dataclass(frozen=True)
class Subject:
    wire: bytes

    @classmethod
    def parse(cls, raw):
        value = decode(raw) if type(raw) in (bytes, str) else decode(encoded(raw))
        shape(value, 'repository repository_id task task_revision purpose source_ref head creation_base target_ref target checking_repository checking_sha profile outcome pr')
        require(type(value['repository']) is str and re.fullmatch(r'ForgingAlpha/[A-Za-z0-9_.-]+', value['repository']) and value['repository'] != 'ForgingAlpha/.github', 'invalid unified repository')
        revision(value['repository_id']); revision(value['task_revision']); identity(value['task'])
        require(type(value['purpose']) is str and value['purpose'] in PURPOSES, 'unsupported purpose')
        require(value['profile'] in ('astro', 'rust', 'mixed'), 'unsupported unified profile')
        require(value['checking_repository'] == 'ForgingAlpha/.github', 'wrong checking repository')
        for name in ('head', 'target', 'checking_sha'):
            sha(value[name])
        if value['creation_base'] is not None:
            sha(value['creation_base'])
        identity(value['source_ref'])
        require(not value['source_ref'].startswith(('refs/', '-')) and not any(part in value['source_ref'] for part in ('..', '//', '@{', '\\')) and not value['source_ref'].endswith(('/', '.', '.lock')), 'invalid source branch')
        require(value['target_ref'] in PERSISTENT, 'unsupported target')
        require(value['outcome'] in ('proposal', 'no-change'), 'unsupported proposal outcome')
        if value['outcome'] == 'proposal':
            revision(value['pr'])
        else:
            require(value['pr'] is None and value['purpose'] in ('consolidation', 'reconciliation'), 'invalid no-change subject')
        return cls(encoded(value))

    def value(self):
        return decode(self.wire)


@dataclass(frozen=True)
class AcquisitionRequest:
    subject: Subject
    bindings: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Available:
    records: bytes


@dataclass(frozen=True)
class Unavailable:
    pass


@dataclass(frozen=True)
class Invalid:
    pass


@dataclass(frozen=True)
class Conflicting:
    pass


class OwnerReader(Protocol):
    def acquire(self, request: AcquisitionRequest) -> Available | Unavailable | Invalid | Conflicting: ...


class UnavailableReader:
    def acquire(self, request):
        return Unavailable()


@dataclass(frozen=True)
class UnifiedContext:
    subject: Subject
    bindings: tuple[tuple[str, str], ...]
    reader: OwnerReader = field(default_factory=UnavailableReader)

    def request(self):
        subject = Subject.parse(self.subject.wire)
        roles = required_roles(subject)
        require(type(self.bindings) is tuple and all(type(row) is tuple and len(row) == 2 for row in self.bindings), 'invalid configured owner bindings')
        require(tuple(role for role, _ in self.bindings) == roles, 'missing/irrelevant owner binding')
        for _, record in self.bindings:
            identity(record)
        return AcquisitionRequest(subject, self.bindings)


def required_roles(subject):
    return tuple(sorted(COMMON)) + (() if subject.value()['purpose'] == 'feature' else ('release',))


def required_branches(subject, records=None):
    if records is not None:
        require(type(records) is dict and type(records.get('scheduling')) is dict, 'missing scheduling observation scope')
        body = records['scheduling'].get('body')
        require(type(body) is dict and type(body.get('data')) is dict, 'invalid scheduling observation scope')
        data = body['data']
        if data.get('lifecycle') == 'cancelled' and data.get('hold') in ('clear', 'released'):
            return ('dev', 'staging', 'main')
    purpose = subject.value()['purpose']
    return ('dev',) if purpose in ('feature', 'consolidation') else ('dev', 'staging', 'main')


def _propositions(values, names, required):
    require(type(values) is dict and set(values) == set(names), 'missing/unsupported proposition')
    for name, value in values.items():
        shape(value, 'state evidence_sha256')
        require(type(value['state']) is str and value['state'] in STATES, 'invalid proposition state')
        sha(value['evidence_sha256'], 64)
        require(value['state'] == 'satisfied' if name in required else value['state'] in ('satisfied', 'not-applicable'), 'required proposition not satisfied')


def _members(rows, *, allow_empty=False):
    require(type(rows) is list and (0 if allow_empty else 1) <= len(rows) <= 128, 'invalid whole batch')
    result = []
    for row in rows:
        shape(row, 'task revision integrated')
        identity(row['task']); revision(row['revision']); sha(row['integrated'])
        result.append(row['task'])
    require(len(set(result)) == len(result), 'duplicate batch member')
    require(result == sorted(result), 'noncanonical batch member order')
    return rows


def _record(raw, role, record_id, subject):
    shape(raw, 'ref body')
    ref, body = raw['ref'], raw['body']
    shape(ref, 'role record decision_revision state_revision payload_sha256 predecessor coordinator succession_sha256')
    require(ref['role'] == role and ref['record'] == record_id, 'wrong accountable owner binding')
    revision(ref['decision_revision']); revision(ref['state_revision']); identity(ref['coordinator'])
    if ref['predecessor'] is not None:
        identity(ref['predecessor'])
    sha(ref['succession_sha256'], 64); sha(ref['payload_sha256'], 64)
    require(ref['payload_sha256'] == digest(body), 'owner payload integrity mismatch')
    shape(body, 'repository repository_id decision validity predicates data')
    require(body['repository'] == subject['repository'] and type(body['repository_id']) is int and body['repository_id'] == subject['repository_id'], 'owner scope mismatch')
    require(body['decision'] in ('accepted', 'rejected', 'indeterminate'), 'invalid decision domain')
    require(body['validity'] in ('current', 'revoked', 'superseded', 'expired', 'unknown'), 'invalid validity domain')
    require(body['decision'] == 'accepted', 'owner decision not accepted')
    require(body['validity'] == 'current', 'owner decision not current')
    return body


def evaluate(request, available, observations):
    """Validate source-faithful acquisition or frozen projection; never establish trust."""
    if type(available) is Unavailable:
        raise Refused('owner acquisition unavailable')
    if type(available) is Invalid:
        raise Refused('owner acquisition invalid')
    if type(available) is Conflicting:
        raise Refused('owner acquisition conflicting')
    require(type(available) is Available, 'unsupported owner acquisition outcome')
    subject = Subject.parse(request.subject.wire).value()
    configured = UnifiedContext(request.subject, request.bindings).request()
    records = decode(available.records)
    require(type(records) is dict and set(records) == {r for r, _ in configured.bindings}, 'missing/irrelevant owner record')
    require(type(observations) is dict and set(observations) == set(required_branches(request.subject, records)), 'incomplete branch observations')
    for value in observations.values():
        sha(value)
    require(observations.get(subject['target_ref']) == subject['target'], 'observed target moved')
    bodies = {role: _record(records[role], role, record, subject) for role, record in configured.bindings}
    for role, names in COMMON.items():
        if role != 'scheduling':
            _propositions(bodies[role]['predicates'], names, names)
    task = bodies['task']['data']
    shape(task, 'task revision subject_sha256')
    revision(task['revision'])
    require(task == {'task': subject['task'], 'revision': subject['task_revision'], 'subject_sha256': digest(subject)}, 'task eligibility subject mismatch')
    workspace = bodies['workspace']['data']
    shape(workspace, 'task creation_ref creation_base')
    require(subject['creation_base'] is not None and workspace['task'] == subject['task'] and workspace['creation_base'] == subject['creation_base'], 'original creation baseline unavailable/mismatched')
    expected_creation = 'staging' if subject['purpose'] in ('repair', 'staging-main') else 'dev'
    require(workspace['creation_ref'] == expected_creation, 'wrong original creation route')
    shape(bodies['migration']['data'], 'profile')
    require(bodies['migration']['data']['profile'] == subject['profile'], 'unqualified application profile')
    schedule = bodies['scheduling']['data']
    shape(schedule, 'hold claim lifecycle effects resolved_dev resolved_staging resolved_main')
    for branch in ('dev', 'staging', 'main'):
        if schedule['resolved_' + branch] is not None:
            sha(schedule['resolved_' + branch])
    require(schedule['hold'] in ('clear', 'held', 'released') and schedule['lifecycle'] in ('none', 'continuing', 'cancelled', 'suspended') and schedule['effects'] in ('none', 'staging', 'main'), 'invalid scheduling state')
    if schedule['claim'] is not None:
        identity(schedule['claim'])
    require((schedule['claim'] is None) == (schedule['lifecycle'] == 'none'), 'incoherent release claim')
    required = ['coherent']
    if schedule['hold'] == 'held':
        require(schedule['claim'] is not None, 'held repository lacks accountable claim')
        required.append('hold_communicated')
    if schedule['hold'] == 'released' and schedule['lifecycle'] == 'continuing':
        require(schedule['effects'] in ('staging', 'main'), 'continuing hold release lacks staged effects')
    if schedule['hold'] != 'held' and schedule['lifecycle'] == 'continuing' and schedule['effects'] in ('staging', 'main'):
        required.append('hold_release_verified')
    if schedule['lifecycle'] == 'cancelled' and schedule['hold'] != 'held':
        require(all(schedule['resolved_' + branch] == observations.get(branch) for branch in ('dev', 'staging', 'main')), 'cancellation resolved baseline moved/unavailable')
        required += ['withdrawal_verified', 'effects_resolved', 'safe_baseline']
        if schedule['effects'] != 'none':
            required.append('effects_reconciled')
    _propositions(bodies['scheduling']['predicates'], SCHEDULING_PREDICATES, required)
    purpose = subject['purpose']
    targets = {'feature': 'dev', 'consolidation': 'dev', 'promotion': 'staging', 'repair': 'staging', 'reconciliation': 'dev', 'staging-main': 'main'}
    require(subject['target_ref'] == targets[purpose], 'wrong purpose target')
    require(subject['source_ref'] == 'staging' if purpose == 'staging-main' else subject['source_ref'] not in PERSISTENT, 'persistent authored source or wrong staging source')
    if purpose == 'feature':
        require(schedule['hold'] != 'held', 'ordinary dev admission held')
    else:
        require(schedule['lifecycle'] == 'continuing' and schedule['claim'] is not None, 'release not continuing')
        release = bodies['release']['data']
        shape(release, 'claim frozen_dev snapshot staging main intended_target expected_members accepted_members staged_repairs reconciled_repairs prior_qualification intended_integration')
        integration = release['intended_integration']
        if integration is not None:
            shape(integration, 'head target result evidence_sha256')
            sha(integration['head']); sha(integration['target']); sha(integration['evidence_sha256'], 64)
            shape(integration['result'], 'kind sha')
            require(integration['result']['kind'] in ('commit', 'tree'), 'unsupported intended result kind')
            sha(integration['result']['sha'])
        if purpose in ('promotion', 'staging-main'):
            require(integration is not None and integration['head'] == subject['head'] and integration['target'] == subject['target'], 'intended integration subject mismatch')
        qualification = release['prior_qualification']
        if qualification is not None:
            shape(qualification, 'head results_sha256 state')
            sha(qualification['head']); sha(qualification['results_sha256'], 64)
            require(qualification['state'] in ('completed-success', 'failure', 'pending', 'unavailable'), 'invalid prior qualification state')
        require(release['claim'] == schedule['claim'], 'conflicting active claim')
        for name in ('frozen_dev', 'snapshot', 'staging', 'main', 'intended_target'):
            sha(release[name])
        staged_repairs = _members(release['staged_repairs'], allow_empty=True)
        reconciled_repairs = _members(release['reconciled_repairs'], allow_empty=True)
        require(_members(release['expected_members']) == _members(release['accepted_members']), 'incomplete accepted batch mapping')
        require(release['intended_target'] == subject['target'], 'intended target mismatch')
        needed = list(RELEASE_REQUIRED[purpose])
        if subject['outcome'] == 'no-change':
            needed.append('no_change_reviewed')
        _propositions(bodies['release']['predicates'], RELEASE_PREDICATES, needed)
        if purpose == 'consolidation':
            require(schedule['hold'] == 'held' and subject['creation_base'] == release['frozen_dev'] == observations['dev'], 'frozen dev or hold moved')
        if purpose == 'promotion':
            require(schedule['hold'] == 'held' and subject['head'] == release['snapshot'] == observations['dev'], 'fixed snapshot or dev hold moved')
        if purpose == 'repair':
            require(subject['creation_base'] == observations['staging'], 'repair creation not current staging')
        if purpose == 'reconciliation':
            require(staged_repairs == reconciled_repairs, 'unreconciled or stale repair identities')
            require(subject['creation_base'] == observations['dev'], 'reconciliation creation not current dev')
        if purpose in ('repair', 'reconciliation', 'staging-main'):
            require(schedule['effects'] in ('staging', 'main'), 'staged release effects unavailable')
            require(release['staging'] == observations['staging'] and release['main'] == observations['main'], 'actual staging/main moved')
        if purpose == 'staging-main':
            require(qualification is not None and qualification['head'] == release['staging'] and qualification['state'] == 'completed-success', 'completed prior staged qualification unavailable')
            require(subject['head'] == release['staging'], 'staging proposal is not actual staged snapshot')
        if subject['outcome'] == 'no-change':
            require(subject['head'] == subject['target'] == observations['dev'], 'no-change baseline moved')
    projection = {'version': 1, 'subject': subject, 'bindings': [list(row) for row in configured.bindings], 'records': records,
            'observations': observations, 'outcome': 'NoProposalRequired' if subject['outcome'] == 'no-change' else 'ProposalEligible'}
    encoded(projection)
    return projection


def read(context):
    request = context.request()
    try:
        result = context.reader.acquire(request)
    except Exception:
        raise Refused('owner acquisition unavailable') from None
    for kind, message in ((Unavailable, 'unavailable'), (Invalid, 'invalid'), (Conflicting, 'conflicting')):
        if type(result) is kind:
            raise Refused('owner acquisition ' + message)
    require(type(result) is Available, 'unsupported owner acquisition outcome')
    return result


def acquire(context, observations):
    return evaluate(context.request(), read(context), observations)


def frozen(raw, context):
    value = decode(raw) if type(raw) in (bytes, str) else decode(encoded(raw))
    shape(value, 'version subject bindings records observations outcome')
    require(type(value['version']) is int and value['version'] == 1, 'unsupported admission projection')
    request = context.request()
    require(value['subject'] == request.subject.value() and value['bindings'] == [list(row) for row in request.bindings], 'frozen subject/owner selection mismatch')
    expected = evaluate(request, Available(encoded(value['records'])), value['observations'])
    require(value == expected, 'frozen admission differs from evaluated evidence')
    return expected
