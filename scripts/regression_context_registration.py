"""Validate an exact, preauthorized criteria/collector context append.

The trusted loader supplies authority from one event-selected base. This module
checks untrusted evidence and preserves ordinary comparison and old contexts.
"""
import copy
import hashlib
import json
import re

BASELINE = 'evas/validation/baselines/regression-v1.json'
REVIEW = 'evas/validation/baselines/regression-v1.review.json'
CODE = 'scripts/regression_gate.py'
GOVERNANCE = 'context_registration_authorizations'
COLLECTOR_PATHS = {'runner': 'scripts/run_regression.py',
                   'environment_policy': 'scripts/ci_evidence.py',
                   'assertion_capture': 'scripts/regression_reason_identity.py',
                   'assertion_policy': 'scripts/regression_observation_policy.json'}
def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def raw_digest(value):
    return hashlib.sha256(value).hexdigest()


def exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('unknown or incomplete ' + label + ' schema')


def sha(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid ' + label + ' SHA256')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('missing ' + label)


def equal(left, right, label):
    if encoded(left) != encoded(right):
        raise ValueError(label + ' differs')


def version(value, label):
    if type(value) is not int or value != 1:
        raise ValueError('unknown ' + label + ' schema version')


def observations(gate, report):
    return {(row['id'], condition['id']): condition
            for row in report['tests'] for condition in row['conditions']} | {
                ('fixture:' + condition['scope'], condition['id']): condition
                for condition in report['fixtures']}


def checked_manifest(manifest, label):
    if not isinstance(manifest, list) or not manifest:
        raise ValueError(label + ' is empty')
    paths = []
    for row in manifest:
        if (not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str)
                or row[0].startswith('/') or '..' in row[0].split('/')):
            raise ValueError('invalid ' + label + ' row')
        sha(row[1], label)
        paths.append(row[0])
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate ' + label + ' row')


def authorization(auth):
    exact(auth, ['schema_version', 'id', 'action', 'old_baseline_canonical_sha256',
                 'previous_context_sha256', 'new_entry_canonical_sha256',
                 'current_dut', 'e1', 'artifacts', 'independent_review',
                 'obligation_mapping'], 'authorization')
    version(auth['schema_version'], 'authorization')
    text(auth['id'], 'authorization ID')
    if auth['action'] != 'append-one-criteria-collector-context':
        raise ValueError('unknown authorization action')
    for key in ('old_baseline_canonical_sha256', 'previous_context_sha256', 'new_entry_canonical_sha256'):
        sha(auth[key], key)
    exact(auth['current_dut'], ['manifest_sha256', 'kernel_sha256'], 'D0')
    for key, value in auth['current_dut'].items():
        sha(value, key)
    exact(auth['e1'], ['raw_sha256', 'canonical_report_sha256', 'execution_subject',
                      'raw_source_sha256', 'entry_source_sha256', 'entry_review_sha256'], 'E1 binding')
    for key, value in auth['e1'].items():
        if key != 'execution_subject':
            sha(value, key)
    expected = {'composition_recipe', 'snapshot_manifest', 'dut_build',
                'kernel_binary', 'collector_manifest', 'artifact_manifest',
                'stdout', 'stderr', 'shard_reports'}
    exact(auth['artifacts'], expected, 'artifact roles')
    for role, reference in auth['artifacts'].items():
        exact(reference, ['sha256', 'locator'], 'artifact reference')
        sha(reference['sha256'], role)
        text(reference['locator'], role + ' retrievable locator')
    review = auth['independent_review']
    exact(review, ['decision', 'reviewer', 'reference', 'entry_sha256',
                   'evidence_sha256', 'mapping_sha256', 'semantic_boundary'], 'independent review')
    if review['decision'] != 'approved-exact-context-registration':
        raise ValueError('registration review not approved')
    for key in ('reviewer', 'reference'):
        text(review[key], key)
    if review['semantic_boundary'] != 'human-exact-review-not-JSON-authentication':
        raise ValueError('review boundary must be explicit')
    for key in ('entry_sha256', 'evidence_sha256', 'mapping_sha256'):
        sha(review[key], key)


# The kernel hash in a run's environment is the DUT kernel (ci_evidence.environment()). E1 may run
# on another DUT than D0; every other environment field still has to match the registration run.
DUT_ENVIRONMENT = ('kernel_sha256',)


def dut_pair(subject):
    return {'manifest_sha256': subject['dut_files_sha256'], 'kernel_sha256': subject['kernel_sha256']}


def backed_e1_dut(auth, blobs, payload, gate, e1):
    """E1's own DUT when it differs from D0 and E1's evidence backs it, else None.

    Backed means: E1's actual execution subject is the authorized one, the kernel_binary role is
    that subject's kernel, and E1's DUT manifest is the snapshot's DUT scope. With None, every D0
    binding in evidence() applies exactly as it did before E1 could run on another DUT. Expected
    data or shape errors return None too; any other exception stops the registration.
    """
    try:
        declared = auth['e1']['execution_subject']
        dut = dut_pair(declared)
        if dut == auth['current_dut'] or any(
                not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value) for value in dut.values()):
            return None
        files = {row[0]: row[3] for row in payload['snapshot_manifest']['entries']}
        scope = {path: checksum for path, checksum in files.items()
                 if path.startswith(('evas/src/', 'evas/rust_core/'))
                 and not {'__pycache__', 'target', 'baselines', '.git', 'runs'}.intersection(path.split('/'))}
        if (raw_digest(blobs['kernel_binary']) != dut['kernel_sha256']
                or encoded(gate.execution_subject(e1)) != encoded(declared)
                or dict(e1['source_identity']['dut_files']) != scope):
            return None
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        return None
    return dut


def evidence(auth, blobs, gate, e1, entry, current_subject):
    """Verify bound bytes/projections, not that a human or machine truly ran them.

    Returns E1's own DUT (D1) when E1 ran on another DUT than the registration run's D0, else None.
    """
    payload = {}
    for role, reference in auth['artifacts'].items():
        raw = blobs.get(role)
        if not isinstance(raw, bytes) or raw_digest(raw) != reference['sha256']:
            raise ValueError('missing or changed artifact bytes: ' + role)
        if role not in ('kernel_binary', 'stdout', 'stderr'):
            payload[role] = json.loads(raw)
    e1_dut = backed_e1_dut(auth, blobs, payload, gate, e1)
    if e1_dut is None and raw_digest(blobs['kernel_binary']) != auth['current_dut']['kernel_sha256']:
        raise ValueError('retrievable binary differs from D0')
    provenance = entry['source_identity']
    exact(provenance, ['schema_version', 'snapshot_revision', 'snapshot_reference',
                       'raw_reference', 'recipe_sha256', 'artifact_manifest_sha256'], 'entry provenance')
    version(provenance['schema_version'], 'entry provenance')
    if not isinstance(provenance['snapshot_revision'], str) or not re.fullmatch('[0-9a-f]{40}', provenance['snapshot_revision']):
        raise ValueError('entry composition snapshot revision missing')
    for key in ('snapshot_reference', 'raw_reference'):
        text(provenance[key], key)
    equal(provenance['recipe_sha256'], auth['artifacts']['composition_recipe']['sha256'], 'provenance recipe')
    equal(provenance['artifact_manifest_sha256'], auth['artifacts']['artifact_manifest']['sha256'], 'provenance capture')
    subject = gate.execution_subject(e1)
    equal(subject, auth['e1']['execution_subject'], 'E1 actual execution subject')
    if e1_dut is None:
        for actual in (current_subject, subject):
            equal({'manifest_sha256': actual['dut_files_sha256'], 'kernel_sha256': actual['kernel_sha256']},
                  auth['current_dut'], 'actual DUT/kernel against authorized D0')
        equal(current_subject['comparison_subject']['environment'],
              subject['comparison_subject']['environment'], 'actual environment profile')
    else:
        # D0 binds only the registration run; E1 is bound to its own backed subject (D1).
        equal(dut_pair(current_subject), auth['current_dut'], 'actual DUT/kernel against authorized D0')
        before = current_subject['comparison_subject']['environment']
        after = subject['comparison_subject']['environment']
        equal({k: v for k, v in before.items() if k not in DUT_ENVIRONMENT},
              {k: v for k, v in after.items() if k not in DUT_ENVIRONMENT}, 'actual environment profile')
        equal(before.get('kernel_sha256'), auth['current_dut']['kernel_sha256'],
              'registration run environment kernel against D0')
        equal(after.get('kernel_sha256'), e1_dut['kernel_sha256'], 'E1 environment kernel against its own DUT')
    source = e1['source_identity']
    checked_manifest(source['criteria_files'], 'criteria manifest')
    if digest(source['criteria_files']) != e1['metadata']['criteria_id']:
        raise ValueError('criteria ID does not bind producer criteria manifest')
    collector = payload['collector_manifest']
    exact(collector, COLLECTOR_PATHS, 'collector manifest')
    for value in collector.values():
        sha(value, 'collector source')
    if digest(collector) != e1['metadata']['collector_sha256']:
        raise ValueError('collector ID differs from source manifest')
    snapshot = payload['snapshot_manifest']
    exact(snapshot, ['schema_version', 'entries'], 'snapshot')
    version(snapshot['schema_version'], 'snapshot')
    entries = snapshot['entries']
    if not isinstance(entries, list) or not entries:
        raise ValueError('empty snapshot entries')
    paths = []
    for row in entries:
        if (not isinstance(row, list) or len(row) != 4 or not isinstance(row[0], str)
                or row[0].startswith('/') or '..' in row[0].split('/')
                or row[1] not in ('100644', '100755') or type(row[2]) is not int
                or not 0 <= row[2] <= 0o777):
            raise ValueError('snapshot must retain regular mode/path/hash rows')
        sha(row[3], 'snapshot input')
        paths.append(row[0])
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate snapshot path')
    files = {row[0]: row[3] for row in entries}
    ignored_parts = {'__pycache__', 'target', 'baselines', '.git', 'runs'}
    def selected(prefixes):
        return {path: checksum for path, checksum in files.items()
                if path.startswith(prefixes) and not ignored_parts.intersection(path.split('/'))}
    equal(dict(source['criteria_files']), selected(('evas/tests/', 'evas/validation/',
                                                   'evas/examples/', 'experiments/')),
          'complete producer criteria scope from snapshot')
    equal(dict(source['dut_files']), selected(('evas/src/', 'evas/rust_core/')),
          'complete producer DUT scope from snapshot')
    for path, checksum in source['criteria_files'] + source['dut_files']:
        if files.get(path) != checksum:
            raise ValueError('source manifest differs from snapshot: ' + path)
    for role, path in COLLECTOR_PATHS.items():
        if files.get(path) != collector[role]:
            raise ValueError('collector source differs from snapshot')
    if files.get('evas/capabilities/data/language-profile.json') != e1['metadata']['language_profile']:
        raise ValueError('language profile differs from snapshot bytes')
    retained = [row for row in entries if row[0] not in gate.COMPARISON_BASELINE_PATHS]
    comparison = subject['comparison_subject']
    if digest(retained) != comparison['files_sha256'] or len(retained) != comparison['input_count']:
        raise ValueError('all-input subject differs from fixed snapshot')
    # Single/merged full producer identities must reconstruct from the actual
    # same entries and each shard's own environment, never from a filled-in old raw.
    sources = [part['source_identity'] for part in e1['parts']] if e1.get('merged') else [source]
    for part in sources:
        identity = part['execution_identity']
        full = {'version': 3, 'report_schema_version': 3,
                'files': entries, 'environment': identity['environment']}
        if digest(full) != identity['key'] or identity['input_count'] != len(entries):
            raise ValueError('full fingerprint differs from frozen snapshot')
    recipe = payload['composition_recipe']
    exact(recipe, ['schema_version', 'dut_revision', 'snapshot_sha256', 'dut_manifest_sha256',
                   'kernel_sha256', 'criteria_id', 'collector_sha256', 'profile_sha256'], 'recipe')
    version(recipe['schema_version'], 'recipe')
    if not re.fullmatch('[0-9a-f]{40}', recipe['dut_revision']):
        raise ValueError('recipe DUT revision missing')
    profile = {key: e1['metadata'][key] for key in ('language_profile', 'runtime_profile', 'invocation')}
    expected = dict(schema_version=1, dut_revision=recipe['dut_revision'],
                    snapshot_sha256=auth['artifacts']['snapshot_manifest']['sha256'],
                    dut_manifest_sha256=subject['dut_files_sha256'], kernel_sha256=subject['kernel_sha256'],
                    criteria_id=e1['metadata']['criteria_id'], collector_sha256=e1['metadata']['collector_sha256'],
                    profile_sha256=digest(profile))
    equal(recipe, expected, 'composition recipe')
    build = payload['dut_build']
    exact(build, ['schema_version', 'dut_revision', 'dut_manifest_sha256', 'kernel_sha256',
                  'toolchain_reference', 'build_reference'], 'DUT build receipt')
    version(build['schema_version'], 'DUT build')
    for key in ('dut_revision', 'dut_manifest_sha256', 'kernel_sha256'):
        equal(build[key], recipe[key], 'build ' + key)
    for key in ('toolchain_reference', 'build_reference'):
        text(build[key], key)
    manifest = payload['artifact_manifest']
    exact(manifest, ['schema_version', 'raw_report_sha256', 'capture_reference',
                     'stdout_sha256', 'stderr_sha256', 'shard_report_sha256'], 'capture manifest')
    version(manifest['schema_version'], 'capture')
    equal(manifest['raw_report_sha256'], auth['e1']['raw_sha256'], 'capture raw bytes')
    text(manifest['capture_reference'], 'capture source reference')
    for key in ('stdout_sha256', 'stderr_sha256'):
        sha(manifest[key], key)
    if not isinstance(manifest['shard_report_sha256'], list) or len(manifest['shard_report_sha256']) != e1['shard_count']:
        raise ValueError('capture missing actual shard report identities')
    for checksum in manifest['shard_report_sha256']:
        sha(checksum, 'shard raw')
    for role in ('stdout', 'stderr'):
        equal(raw_digest(blobs[role]), manifest[role + '_sha256'], 'captured ' + role)
    raw_shards = payload['shard_reports']
    if not isinstance(raw_shards, list) or len(raw_shards) != e1['shard_count'] or any(not isinstance(x, str) for x in raw_shards):
        raise ValueError('retrievable shard raw bytes missing')
    if [raw_digest(x.encode()) for x in raw_shards] != manifest['shard_report_sha256']:
        raise ValueError('shard raw bytes differ from capture manifest')
    shards = [json.loads(x) for x in raw_shards]
    if any(not gate.validate_report(x)['valid'] or x.get('merged') for x in shards):
        raise ValueError('captured shard is invalid or already merged')
    if sorted(x['shard_index'] for x in shards) != list(range(e1['shard_count'])):
        raise ValueError('captured shards missing or duplicated')
    shards.sort(key=lambda x: x['shard_index'])
    for shard in shards:
        for key in ('metadata', 'discovered_test_ids', 'assignment', 'shard_count'):
            equal(shard[key], e1[key], 'shard ' + key)
        public = lambda source: {k: v for k, v in source.items() if k != 'execution_identity'}
        equal(public(shard['source_identity']), public(e1['source_identity']), 'shard public scientific source')
        expected_input = digest({key: shard[key] for key in
                                 ('metadata', 'source_identity', 'selected_test_ids')})
        equal(shard.get('input_identity'), expected_input, 'shard input_identity')
        environment = shard['source_identity']['execution_identity']['environment']
        expected_shard = str(shard['shard_index']) + '-of-' + str(shard['shard_count'])
        equal(environment.get('shard'), expected_shard, 'shard environment label')
    if e1.get('merged'):
        for key in ('tests', 'fixtures', 'setup_skipped_test_ids'):
            equal([item for shard in shards for item in shard[key]], e1[key], 'merged raw ' + key)
        for key in gate.COUNTERS:
            equal(sum(shard[key] for shard in shards), e1[key], 'merged raw ' + key)
        keys = ('shard_index', 'complete', 'collection_complete', 'selected_test_ids',
                'metadata', 'input_identity', 'source_identity')
        equal([{key: shard[key] for key in keys} for shard in shards], e1['parts'], 'merged original parts')
    else:
        equal(shards[0], e1, 'whole single-shard raw')
    return e1_dut


def mapped_obligations(auth, gate, old, e1, dut_changed=False):
    """Check the explicit old-to-new mapping. With E1 on another DUT than D0 (dut_changed), only
    preserved old obligations and new passing obligations register: a changed outcome can no
    longer be attributed to the criteria alone."""
    before, after = observations(gate, old), observations(gate, e1)
    mapping = auth['obligation_mapping']
    if not isinstance(mapping, list):
        raise ValueError('obligation mapping is not an array')
    seen_old, seen_new = set(), set()
    for item in mapping:
        exact(item, ['old_owner', 'old_condition', 'old_signature_sha256',
                     'new_owner', 'new_condition', 'new_signature_sha256',
                     'classification', 'review_reference', 'attribution'], 'obligation mapping')
        a = (item['old_owner'], item['old_condition'])
        b = (item['new_owner'], item['new_condition'])
        if a not in before or b not in after or a in seen_old or b in seen_new:
            raise ValueError('lost, unknown or duplicate obligation mapping')
        seen_old.add(a)
        seen_new.add(b)
        equal(item['old_signature_sha256'], digest(gate._retention_condition(before[a])), 'old obligation signature')
        equal(item['new_signature_sha256'], digest(gate._retention_condition(after[b])), 'new obligation signature')
        text(item['review_reference'], 'mapping manual review reference')
        if item['classification'] == 'preserved':
            if before[a]['outcome'] != after[b]['outcome'] or item['attribution'] is not None:
                raise ValueError('preserved obligation changed outcome')
        elif item['classification'] == 'criterion-correction-reveals-old-dut-defect':
            if dut_changed:
                raise ValueError('false-pass attribution needs E1 on the authorized D0')
            if before[a]['outcome'] != 'passed' or after[b]['outcome'] not in ('failed', 'error'):
                raise ValueError('false-pass attribution has wrong outcomes')
            exact(item['attribution'], ['finding_id', 'counterexample', 'manual_reason'], 'false-pass attribution')
            for key, value in item['attribution'].items():
                text(value, key)
        else:
            raise ValueError('unknown scientific obligation attribution')
        if after[b]['outcome'] in ('skipped', 'expected_failure', 'unexpected_success') and before[a]['outcome'] != after[b]['outcome']:
            raise ValueError('new skip/xfail/unexpected-success is not authorized')
    if seen_old != set(before):
        raise ValueError('old obligations omitted from explicit manual mapping')
    for key, condition in after.items():
        if condition['outcome'] in ('skipped', 'expected_failure', 'unexpected_success') and key not in seen_new:
            raise ValueError('new skip/xfail/unexpected-success observation')
        if dut_changed and condition['outcome'] != 'passed' and key not in seen_new:
            raise ValueError('new obligation on another DUT must pass: ' + key[0] + ':' + key[1])


def validate_context_registration(gate, report, trusted_baseline, head_proposal,
                                  trusted_review, head_review, changed_paths,
                                  e1_raw, artifact_blobs):
    """Check an append using authority already selected by the trusted loader.

    E1 and artifact bytes are untrusted observations. Only the loader may supply
    the comparator, baseline and review from the same event-selected base.
    JSON review fields record the main approval; they do not authenticate people.
    """
    result = {'valid': False, 'raw_successful': report.get('successful'),
              'merge_allowed': False, 'semantic_qualification': False,
              'transition': {'accepted': False},
              'authorization_evaluated': False, 'head_evaluated': False, 'differences': []}
    try:
        current = report
        compared = gate.compare_report(current, trusted_baseline)
        result['trusted_comparison'] = compared
        result['valid'] = compared['valid']
        # Do not inspect head/new evidence/authorization if ordinary comparison rejects.
        if not compared['merge_allowed']:
            result['differences'] = list(compared['differences'])
            return result
        if changed_paths != [BASELINE]:
            raise ValueError('registration transaction must change only fixed baseline path')
        if (not isinstance(trusted_review, dict) or type(trusted_review.get('schema_version')) is not int
                or trusted_review['schema_version'] != 1
                or not isinstance(trusted_review.get(GOVERNANCE), list)):
            raise ValueError('trusted review lacks governance array')
        head = head_proposal
        equal(head_review, trusted_review,
              'head review/receipt/governance fields')
        result['head_evaluated'] = True
        exact(trusted_baseline, ['schema_version', 'contexts'], 'trusted baseline')
        version(trusted_baseline['schema_version'], 'trusted baseline')
        exact(head, ['schema_version', 'contexts'], 'head baseline')
        version(head['schema_version'], 'baseline')
        old_entries = trusted_baseline['contexts']
        if not isinstance(head['contexts'], list) or len(head['contexts']) != len(old_entries) + 1:
            raise ValueError('exactly one context append is required')
        equal(head['contexts'][:-1], old_entries, 'all existing contexts/order')
        stripped = dict(schema_version=1, contexts=copy.deepcopy(head['contexts'][:-1]))
        transition = gate.validate_baseline_transition(current, trusted_baseline, stripped)
        result['current_transition'] = transition
        if not transition['merge_allowed']:
            raise ValueError('ordinary current-context transition rejected')
        entry = head['contexts'][-1]
        entry_hash = digest(entry)
        matches = [a for a in trusted_review[GOVERNANCE]
                   if isinstance(a, dict) and a.get('new_entry_canonical_sha256') == entry_hash]
        if len(matches) != 1:
            raise ValueError('expected one exact authorization in trusted-base review')
        auth = matches[0]
        authorization(auth)
        result['authorization_evaluated'] = True
        if len({a.get('id') for a in trusted_review[GOVERNANCE] if isinstance(a, dict)}) != len(trusted_review[GOVERNANCE]):
            raise ValueError('duplicate governance authorization ID')
        equal(auth['old_baseline_canonical_sha256'], digest(trusted_baseline), 'authorized old baseline')
        equal(auth['previous_context_sha256'], digest(gate._context(current)), 'authorized current context')
        exact(entry, ['context', 'source_identity', 'review', 'semantic_qualification',
                      'observation_format', 'observation_encoding', 'value_pool',
                      'canonical_report_sha256', 'observations', 'execution_subject'], 'new context entry')
        if entry['semantic_qualification'] is not False or entry['observation_encoding'] != 'pooled-context-v1':
            raise ValueError('new entry must preserve explicit unqualified observation format')
        if any(encoded(entry['context']) == encoded(e['context']) for e in old_entries):
            raise ValueError('new context duplicates an existing context')
        e1 = json.loads(e1_raw)
        exact(e1['metadata'], gate.CONTEXT_KEYS, 'E1 metadata')
        if not gate.validate_report(e1)['valid'] or not gate._whole(e1):
            raise ValueError('E1 needs a complete current-schema whole report')
        equal(raw_digest(e1_raw), auth['e1']['raw_sha256'], 'E1 raw bytes')
        equal(digest(e1), auth['e1']['canonical_report_sha256'], 'E1 canonical report')
        equal(entry['canonical_report_sha256'], digest(e1), 'new entry raw projection source')
        equal(digest(e1['source_identity']), auth['e1']['raw_source_sha256'], 'E1 producer source')
        equal(digest(entry['source_identity']), auth['e1']['entry_source_sha256'], 'entry provenance source')
        equal(digest(entry['review']), auth['e1']['entry_review_sha256'], 'entry exact review')
        equal(entry['context'], gate._context(e1), 'new context metadata')
        before_context = gate._context(current)
        for key in ('language_profile', 'runtime_profile', 'invocation'):
            equal(entry['context'][key], before_context[key], 'fixed ' + key)
        if all(entry['context'][key] == before_context[key] for key in ('criteria_id', 'collector_sha256')):
            raise ValueError('registration requires criteria/collector change')
        # The current run matched one trusted context, possibly across a runner-host change.
        matched, _ = gate._matching_contexts(old_entries, before_context)
        if len(matched) != 1:
            raise ValueError('current context lacks one matching trusted entry')
        old = gate._expand_baseline_observations(matched[0])
        if not set(old['discovered_test_ids']).issubset(e1['discovered_test_ids']):
            raise ValueError('old method ID obligation lost; registration does not support renames')
        if e1['setup_skipped_test_ids'] or any(f['outcome'] != 'passed' for f in e1['fixtures']):
            raise ValueError('collection/fixture/skip gap cannot be registered')
        if any(c['outcome'] != 'passed' and not gate._matchable(c) for c in observations(gate, e1).values()):
            raise ValueError('new nonpassing identity not fully matchable')
        projected = gate._expand_baseline_observations(entry)
        equal(projected, gate._baseline_observations(e1), 'complete projected E1 observations')
        if not gate.compare_report(e1, dict(schema_version=1, contexts=[entry]))['merge_allowed']:
            raise ValueError('new entry structure or review invalid')
        equal(entry['execution_subject'], gate.execution_subject(e1), 'entry actual execution subject')
        current_subject = gate.execution_subject(current)
        e1_dut = evidence(auth, artifact_blobs, gate, e1, entry, current_subject)
        # D0 is the registration run's DUT, D1 the DUT that E1 actually ran on.
        result['registration_dut'] = dict(current=copy.deepcopy(auth['current_dut']),
                                          e1=copy.deepcopy(e1_dut or auth['current_dut']),
                                          changed=e1_dut is not None)
        mapped_obligations(auth, gate, old, e1, dut_changed=e1_dut is not None)
        review = auth['independent_review']
        equal(review['entry_sha256'], entry_hash, 'manual review exact entry')
        equal(review['evidence_sha256'], digest(auth['e1']), 'manual review exact evidence')
        equal(review['mapping_sha256'], digest(auth['obligation_mapping']), 'manual review exact mapping')
        result['transition'].update(accepted=True, registration=True)
        result.update(merge_allowed=True, authorization_id=auth['id'],
                      added_entry_sha256=entry_hash,
                      human_review_status='trusted-main record only; JSON does not authenticate a human',
                      opaque_passes=sum(c['outcome'] == 'passed' and not gate._matchable(c)
                                        for c in observations(gate, e1).values()))
    except (KeyError, TypeError, ValueError, StopIteration, IndexError, OverflowError) as error:
        result['differences'].append(str(error))
    return result
