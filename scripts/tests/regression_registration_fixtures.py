"""Entirely synthetic plumbing fixtures. No fixture is a real E1 execution."""
import copy
import json
from pathlib import Path
import types
import importlib.util

API_PATH = Path(__file__).resolve().parents[1] / 'regression_context_registration.py'
_spec = importlib.util.spec_from_file_location('registration_fixture_api', API_PATH)
api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api)

BASE = 'a' * 40
EVENT = {'event_name': 'pull_request', 'pull_request': {'base': {'sha': BASE}}}
CODE = (Path(__file__).resolve().parents[1] / 'regression_gate.py').read_bytes()
gate = types.ModuleType('fixture_gate')
exec(compile(CODE, 'maintained-gate-synthetic-fixture', 'exec'), gate.__dict__)


def h(text):
    return api.raw_digest(text.encode())


def raw(value):
    return json.dumps(value, indent=2, sort_keys=True).encode() + b'\n'


def condition(identity, outcome, opaque=False, criteria='C0'):
    site = {'module': 'synthetic_fixture', 'line': 10, 'source_sha256': h(criteria)}
    value = dict(id=identity, phase='test', kind='assertion', site=site,
                 identity_complete=not opaque, outcome=outcome)
    if outcome != 'passed':
        value['reason'] = dict(kind='assertion', exception_type='builtins.AssertionError',
                               message='synthetic A differs', site=site,
                               context_complete=True, attribution='unreviewed-observation')
    return value


def report(criteria='C0', collector='I0', correction=False, opaque_count=58):
    criteria_files = [['evas/tests/test_demo.py', h(criteria)]]
    dut_files = [['evas/src/evas/core.py', h('D0 implementation fixture')]]
    collector_manifest = {role: h(collector + ':' + role) for role in api.COLLECTOR_PATHS}
    kernel = b'SYNTHETIC NONEXECUTABLE D0 BINARY FIXTURE'
    environment = {'python': 'synthetic-python', 'machine': 'synthetic-host',
                   'kernel_sha256': api.raw_digest(kernel), 'shard': '0-of-1'}
    entries = [['evas/tests/test_demo.py', '100644', 0o644, h(criteria)],
               ['evas/src/evas/core.py', '100644', 0o644, dut_files[0][1]],
               ['evas/capabilities/data/language-profile.json', '100644', 0o644, h('fixed-language')],
               *[[path, '100644', 0o644, collector_manifest[role]] for role, path in api.COLLECTOR_PATHS.items()],
               [api.BASELINE, '100644', 0o644, h('historical baseline bytes before authorization')],
               [api.REVIEW, '100644', 0o644, h('historical review bytes before authorization')]]
    entries.sort()
    comparison = dict(schema_version=1, report_schema_version=3, evidence_schema_version=3,
                      files_sha256=api.digest([row for row in entries if row[0] not in (api.BASELINE, api.REVIEW)]),
                      input_count=len(entries) - 2,
                      environment={k: v for k, v in environment.items() if k != 'shard'},
                      excluded_baseline_paths=[api.BASELINE, api.REVIEW])
    identity = dict(key=api.digest(dict(version=3, report_schema_version=3,
                                       files=entries, environment=environment)),
                    input_count=len(entries), environment=environment,
                    comparison_subject=comparison, report_schema_version=3, evidence_schema_version=3)
    conditions = [condition(criteria + ':A', 'failed', criteria=criteria),
                  condition(criteria + ':P', 'failed' if correction else 'passed', criteria=criteria)]
    conditions += [condition(criteria + ':opaque:' + str(i), 'passed', opaque=True, criteria=criteria)
                   for i in range(opaque_count)]
    name = 'synthetic.Case.test_one'
    value = dict(schema_version=3, complete=True, collection_complete=True, successful=False,
                 tests_run=1, failures=2 if correction else 1, errors=0, skipped=0,
                 expected_failures=0, unexpected_successes=0,
                 discovered_test_ids=[name], selected_test_ids=[name], setup_skipped_test_ids=[],
                 assignment=[[name]], shard_count=1, shard_index=0, fixtures=[],
                 tests=[dict(id=name, outcome='failed', seconds=0.1, conditions=conditions)],
                 metadata=dict(criteria_id=api.digest(criteria_files), language_profile=h('fixed-language'),
                               collector_sha256=api.digest(collector_manifest),
                               runtime_profile={'profile': 'synthetic-fixed-runtime'},
                               invocation={'pattern': 'test_*.py', 'modules': []}),
                 source_identity=dict(criteria_files=criteria_files, dut_files=dut_files,
                                      kernel_sha256=api.raw_digest(kernel), execution_identity=identity))
    return value, entries, collector_manifest, kernel


REVIEW = {'status': 'approved', 'reviewer': 'SYNTHETIC reviewer fixture',
          'reference': 'fixture:review-not-a-real-person', 'semantic_status': 'pending'}


class Store:
    """Fixture implementation of read-only Git object API; no Git writes."""
    def __init__(self, baseline, review, head):
        self.files = {(BASE, api.CODE): CODE,
                      (BASE, api.BASELINE): raw(baseline), (BASE, api.REVIEW): raw(review),
                      ('HEAD', api.BASELINE): raw(head), ('HEAD', api.REVIEW): raw(review)}
        self.changed = [api.BASELINE]
        self.nonregular = set()
        self.reads = []

    def commit(self, revision):
        if revision != BASE:
            raise ValueError('fixture unavailable event base')

    def regular_blob(self, revision, path):
        self.reads.append((revision, path))
        if (revision, path) in self.nonregular:
            raise ValueError('fixture fixed path is not regular Git blob')
        return self.files[(revision, path)]

    def changed_paths(self, base):
        assert base == BASE
        return self.changed


def make_fixture(correction=False, opaque_count=58, alter_e1=None, alter_entry=None,
                 alter_auth=None, alter_baseline=None, new_criteria='C1', new_collector='I1',
                 merged=False, alter_blobs=None):
    current, _, _, _ = report(opaque_count=opaque_count)
    e1, entries, collector, kernel = report(new_criteria, new_collector, correction, opaque_count)
    shards = [e1]
    if merged:
        names = e1['discovered_test_ids'] + ['synthetic.Case.test_added']
        shards = []
        for index in range(2):
            shard = copy.deepcopy(e1)
            shard.update(discovered_test_ids=names, selected_test_ids=[names[index]],
                         assignment=[[name] for name in names], shard_count=2, shard_index=index,
                         input_identity=h('synthetic part ' + str(index)))
            if index == 1:
                shard.update(failures=0, successful=True,
                             tests=[dict(id=names[1], outcome='passed', seconds=0.1,
                                         conditions=[condition('new obligation', 'passed', criteria=new_criteria)])])
            identity = shard['source_identity']['execution_identity']
            identity['environment']['shard'] = str(index) + '-of-2'
            identity['key'] = api.digest(dict(version=3, report_schema_version=3,
                                               files=entries, environment=identity['environment']))
            shards.append(shard)
        e1 = copy.deepcopy(shards[0])
        e1.update(merged=True, shard_index=None, selected_test_ids=names, tests_run=2,
                  tests=[row for shard in shards for row in shard['tests']],
                  parts=[{key: shard[key] for key in ('shard_index', 'complete', 'collection_complete',
                          'selected_test_ids', 'metadata', 'input_identity', 'source_identity')} for shard in shards])
        e1['source_identity'] = {k: v for k, v in e1['source_identity'].items() if k != 'execution_identity'}
        e1.pop('input_identity')
    if alter_e1:
        alter_e1(e1)
    baseline = gate.propose_baseline(current, {'fixture': 'C0:D0 observed provenance'}, REVIEW)
    unrelated = copy.deepcopy(current)
    unrelated['metadata']['invocation'] = {'profile': 'unrelated trusted fixture'}
    baseline['contexts'] += gate.propose_baseline(unrelated, {'fixture': 'other context'}, REVIEW)['contexts']
    if alter_baseline:
        alter_baseline(baseline)
    entry = gate.propose_baseline(e1, {'fixture': 'E1 composition snapshot; not real execution'}, REVIEW)['contexts'][0]
    current_subject, subject = gate.execution_subject(current), gate.execution_subject(e1)
    snapshot = dict(schema_version=1, entries=entries)
    profile = {key: e1['metadata'][key] for key in ('language_profile', 'runtime_profile', 'invocation')}
    snapshot_bytes = raw(snapshot)
    recipe = dict(schema_version=1, dut_revision='0' * 40,
                  snapshot_sha256=api.raw_digest(snapshot_bytes),
                  dut_manifest_sha256=subject['dut_files_sha256'], kernel_sha256=subject['kernel_sha256'],
                  criteria_id=e1['metadata']['criteria_id'], collector_sha256=e1['metadata']['collector_sha256'],
                  profile_sha256=api.digest(profile))
    build = dict(schema_version=1, dut_revision=recipe['dut_revision'],
                 dut_manifest_sha256=subject['dut_files_sha256'], kernel_sha256=subject['kernel_sha256'],
                 toolchain_reference='fixture:synthetic toolchain, never built',
                 build_reference='fixture:nonexecutable binary, not an actual build')
    e1_bytes = raw(e1)
    stdout, stderr = b'SYNTHETIC capture fixture; not actual execution\n', b''
    capture = dict(schema_version=1, raw_report_sha256=api.raw_digest(e1_bytes),
                   capture_reference='fixture:synthetic E1, not a real run',
                   stdout_sha256=api.raw_digest(stdout), stderr_sha256=api.raw_digest(stderr),
                   shard_report_sha256=[api.raw_digest(raw(shard)) for shard in shards])
    blobs = dict(composition_recipe=raw(recipe), snapshot_manifest=snapshot_bytes,
                 dut_build=raw(build), kernel_binary=kernel, collector_manifest=raw(collector),
                 artifact_manifest=raw(capture), stdout=stdout, stderr=stderr,
                 shard_reports=raw([raw(shard).decode() for shard in shards]))
    if alter_blobs:
        alter_blobs(blobs)
    entry['source_identity'] = dict(schema_version=1, snapshot_revision='f' * 40,
                                  snapshot_reference='fixture:synthetic composition, not actual execution',
                                  raw_reference='fixture:synthetic raw, not real E1',
                                  recipe_sha256=api.raw_digest(blobs['composition_recipe']),
                                  artifact_manifest_sha256=api.raw_digest(blobs['artifact_manifest']))
    if alter_entry:
        alter_entry(entry)
    old_conditions = list(api.observations(gate, current).items())
    new_conditions = list(api.observations(gate, e1).items())
    mappings = []
    for (a, old), (b, new) in zip(old_conditions, new_conditions):
        revealed = old['outcome'] == 'passed' and new['outcome'] in ('failed', 'error')
        mappings.append(dict(old_owner=a[0], old_condition=a[1],
                             old_signature_sha256=api.digest(gate._retention_condition(old)),
                             new_owner=b[0], new_condition=b[1],
                             new_signature_sha256=api.digest(gate._retention_condition(new)),
                             classification='criterion-correction-reveals-old-dut-defect' if revealed else 'preserved',
                             review_reference='fixture:manual exact cross-criteria review boundary',
                             attribution=dict(finding_id='SYNTHETIC-FALSE-PASS',
                                              counterexample='fixture:synthetic counterexample',
                                              manual_reason='fixture:human explanation required in real governance') if revealed else None))
    auth = dict(schema_version=1, id='fixture:append C1,I1 on unchanged D0',
                action='append-one-criteria-collector-context',
                old_baseline_canonical_sha256=api.digest(baseline),
                previous_context_sha256=api.digest(current['metadata']),
                new_entry_canonical_sha256=api.digest(entry),
                current_dut=dict(manifest_sha256=current_subject['dut_files_sha256'],
                                 kernel_sha256=current_subject['kernel_sha256']),
                e1=dict(raw_sha256=api.raw_digest(e1_bytes), canonical_report_sha256=api.digest(e1),
                        execution_subject=subject, raw_source_sha256=api.digest(e1['source_identity']),
                        entry_source_sha256=api.digest(entry['source_identity']),
                        entry_review_sha256=api.digest(entry['review'])),
                artifacts={role: dict(sha256=api.raw_digest(value), locator='fixture:' + role)
                           for role, value in blobs.items()},
                independent_review=dict(decision='approved-exact-context-registration',
                                        reviewer='SYNTHETIC reviewer, not authenticated',
                                        reference='fixture:exact review, not real E1 approval',
                                        entry_sha256=api.digest(entry), evidence_sha256=None,
                                        mapping_sha256=api.digest(mappings),
                                        semantic_boundary='human-exact-review-not-JSON-authentication'),
                obligation_mapping=mappings)
    auth['independent_review']['evidence_sha256'] = api.digest(auth['e1'])
    if alter_auth:
        alter_auth(auth)
    review = dict(schema_version=1, original_receipt={'decision': 'SYNTHETIC existing receipt retained'},
                  context_registration_authorizations=[auth])
    head = copy.deepcopy(baseline)
    head['contexts'].append(entry)
    store = Store(baseline, review, head)
    return dict(store=store, event=copy.deepcopy(EVENT), current=current, e1=e1,
                current_bytes=raw(current), e1_bytes=e1_bytes, blobs=blobs,
                baseline=baseline, entry=entry, auth=auth, review=review, head=head)


def evaluate(fixture):
    store = fixture['store']
    def head_data(path):
        raw = store.regular_blob('HEAD', path)
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return api.validate_context_registration(gate, json.loads(fixture['current_bytes']),
        json.loads(store.regular_blob(BASE, api.BASELINE)),
        head_data(api.BASELINE),
        json.loads(store.regular_blob(BASE, api.REVIEW)),
        head_data(api.REVIEW), store.changed_paths(BASE),
        fixture['e1_bytes'], fixture['blobs'])
