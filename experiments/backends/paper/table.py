"""Render fixed core-v1 tables from hash-bound assessments, without executing tools."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from inputs import identity as frozen_identity
import re

HERE = Path(__file__).resolve().parent
CARDS_PATH = HERE.parents[2] / 'evas/validation/paper/core-v1.json'
BATCH = json.loads(CARDS_PATH.read_text())
CARDS_SHA = hashlib.sha256(CARDS_PATH.read_bytes()).hexdigest()
# Presentation order, independent of runner scheduling order.
BACKENDS = ('evas', 'spectre', 'openvaf_r_ngspice', 'gnucap_modelgen')
STATUSES = 'PFUXIT'
# Runner's explicit failure states. This is a report consistency check, not scoring.
EXECUTION_FAILURES = frozenset(('compile_failed', 'compile_timeout', 'runtime_timeout',
    'execution_failed', 'execution_error', 'cancelled', 'cleanup_incomplete',
    'missing_compile_artifact', 'missing_waveform', 'observation_invalid'))


def artifact_bytes(ref):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError('Artifact identity requires path and sha256')
    path = Path(ref['path'])
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref.get('sha256'):
        raise ValueError('Artifact hash mismatch: ' + str(path))
    return data


def read_artifact(ref):
    return json.loads(artifact_bytes(ref))


def relative_ref(ref, containing):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError('Missing unsupported evidence artifact identity')
    return {**ref, 'path': str((Path(containing['path']).parent / ref['path']).resolve())}


def text(value):
    """Keep evidence strings within a Markdown cell."""
    return str(value).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')


def link(ref):
    return '[' + text(Path(ref['path']).name) + '](<' + ref['path'] + '>)'


def stable_tool(tool):
    """Project runner-produced scientific identity; retain full receipts separately."""
    keys = ('profile_identity', 'kernel_sha256', 'reported', 'interpreter',
            'binary_sha256', 'setup_sha256', 'version', 'environment_sha256',
            'environment_manifest_sha256', 'compiler_flags', 'compiler_sha256')
    stable = {key: tool[key] for key in keys if key in tool}
    if 'images' in tool:
        stable['images'] = {name: image['config_id'] for name, image in tool['images'].items()}
    if 'versions' in tool:
        stable['versions'] = {name: version['self_report'] for name, version in tool['versions'].items()}
    return stable


def execution_files(record, execution, started):
    identity = record['identity']
    lane = read_artifact(identity['lane_started'])
    inputs = read_artifact(identity['input_manifest'])
    manifest = read_artifact(identity['execution_manifest'])
    if lane.get('backend') != record['backend'] or lane.get('input_manifest_sha256') != identity['input_manifest']['sha256'] or lane.get('fixed_conditions') != [c['id'] for c in BATCH['cards']] or inputs.get('core.json', {}).get('sha256') != CARDS_SHA:
        raise ValueError('Frozen input/lane identity mismatch')
    lane_root = Path(identity['lane_started']['path']).parent
    refs = [record['execution'], *[identity[k] for k in ('tool', 'condition_started', 'lane_started')]]
    if identity.get('observation'):
        refs.append(identity['observation'])
    work = Path(identity['condition_started']['path']).parent
    card = next(c for c in BATCH['cards'] if c['id'] == record['condition_id'])
    source_sha = hashlib.sha256(card['source'].encode()).hexdigest()
    expected_work = 'runs/' + record['backend'] + '/' + record['condition_id']
    deck = execution.get('deck')
    if execution.get('work') != expected_work or not isinstance(deck, str) or Path(deck).name != deck or execution.get('condition_identity') != frozen_identity(card) or execution.get('source_sha256') != source_sha or started.get('source_sha256') != source_sha:
        raise ValueError('Executed/STARTED/card source/deck identity mismatch')
    for name, digest in [('dut.va', source_sha), (deck, started.get('deck_sha256'))]:
        ref = {'path': str(work / name), 'sha256': digest}
        if inputs.get(expected_work + '/' + name, {}).get('sha256') != digest:
            raise ValueError('Frozen source/deck identity mismatch')
        artifact_bytes(ref)
        refs.append(ref)
    for ref in refs:
        try:
            relative = str(Path(ref['path']).resolve().relative_to(lane_root.resolve()))
        except ValueError:
            raise ValueError('Artifact outside its execution lane') from None
        if manifest.get(relative, {}).get('sha256') != ref['sha256']:
            raise ValueError('Execution FILE_MANIFEST artifact identity mismatch: ' + relative)


def prior_attempts(record):
    refs = record.get('prior_attempts', [])
    if not isinstance(refs, list) or (refs and (not isinstance(record.get('selection_reason'), str) or not record['selection_reason'].strip() or not record.get('execution'))):
        raise ValueError('Declared prior_attempts require selection_reason')
    seen = {record.get('execution', {}).get('sha256')}
    for ref in refs:
        attempt = read_artifact(ref)
        if attempt.get('condition') != record['condition_id'] or attempt.get('backend') != record['backend'] or attempt.get('status') not in EXECUTION_FAILURES | {'waveform_available', 'not_run'}:
            raise ValueError('Invalid prior attempt condition/backend/status')
        if ref['sha256'] in seen:
            raise ValueError('Duplicate prior attempt artifact')
        seen.add(ref['sha256'])
    return refs


def validate(record):
    prior_attempts(record)
    if record.get('status') == 'T' and 'assessment' not in record:
        if 'execution' in record:
            execution = read_artifact(record['execution'])
            if execution.get('condition') != record['condition_id'] or execution.get('backend') != record['backend'] or execution.get('status') != 'not_run':
                raise ValueError('T execution status must be not_run for this condition/backend')
        return 'T', None, None
    identity = record.get('identity', {})
    if not all(identity.get(k) for k in ('source_revision', 'tool', 'condition_started', 'lane_started', 'input_manifest', 'execution_manifest', 'method', 'availability')):
        raise ValueError('Execution identity requires source_revision/tool/condition_started/lane_started/input_manifest/execution_manifest/method/availability')
    if identity['availability'] not in ('local-only', 'restricted', 'public'):
        raise ValueError('Unknown availability')
    if identity['availability'] == 'public' and not identity.get('public_url', '').startswith('https://'):
        raise ValueError('Public availability requires public_url')
    assessment = read_artifact(record.get('assessment'))
    execution = read_artifact(record.get('execution'))
    tool = read_artifact(identity['tool'])
    started = read_artifact(identity['condition_started'])
    if started.get('condition') != record['condition_id'] or started.get('tool_identity_sha256') != identity['tool']['sha256'] or any(not re.fullmatch('[0-9a-f]{64}', str(started.get(k, ''))) for k in ('source_sha256', 'deck_sha256')):
        raise ValueError('Condition source/deck/tool execution identity mismatch')
    if assessment.get('condition_id') != record['condition_id'] or execution.get('condition') != record['condition_id'] or execution.get('backend') != record['backend']:
        raise ValueError('Assessment/execution condition or backend mismatch')
    if assessment.get('execution_sha256') != record['execution']['sha256']:
        raise ValueError('Assessment execution hash mismatch')
    checker = assessment.get('checker_identity', {})
    if checker.get('files', {}).get('core-v1.json') != CARDS_SHA:
        raise ValueError('Assessment card identity mismatch')
    if not re.fullmatch('[0-9a-f]{64}', str(checker.get('sha256', ''))):
        raise ValueError('Missing checker identity')
    status = assessment.get('status')
    if not isinstance(status, str) or len(status) != 1 or status not in STATUSES:
        raise ValueError('Unknown assessment status')
    state = assessment.get('execution_state')
    if status in 'UXT':
        if state != status:
            raise ValueError('Assessment execution state mismatch')
        execution_status = execution.get('status')
        allowed = {'U': {'compile_failed'}, 'X': EXECUTION_FAILURES, 'T': {'not_run'}}
        if execution_status not in allowed[status]:
            raise ValueError(status + ' execution status is incompatible with assessment')
        if status == 'U':
            evidence_ref = relative_ref(assessment.get('unsupported_evidence'), record['assessment'])
            evidence = read_artifact(evidence_ref)
            if execution.get('failure_stage') != 'compile' or evidence.get('status') != 'confirmed_unsupported' or evidence.get('failure_stage') != 'compile' or not evidence.get('reason') or evidence.get('execution_sha256') != record['execution']['sha256']:
                raise ValueError('Invalid compiler unsupported evidence')
            diagnostic = relative_ref(evidence.get('diagnostic'), evidence_ref)
            if not artifact_bytes(diagnostic):
                raise ValueError('Empty compiler unsupported evidence diagnostic')
            if not any(stage.get('stage') == 'compile' and type(stage.get('returncode')) is int and stage['returncode'] != 0 and stage.get('log_sha256') == diagnostic['sha256'] for stage in execution.get('stages', [])):
                raise ValueError('Compiler unsupported evidence must bind actual failed compile log')
    else:
        if state != 'completed' or execution.get('status') != 'waveform_available':
            raise ValueError('Completed assessment requires waveform execution')
        observation = identity.get('observation')
        read_artifact(observation)
        if execution.get('observation', {}).get('sha256') != observation['sha256']:
            raise ValueError('Execution/assessment observation hash mismatch')
        if assessment.get('input_observation_sha256') != observation['sha256']:
            raise ValueError('Assessment input observation hash mismatch')
        properties = assessment.get('properties', [])
        states = {p.get('status') for p in properties}
        if not states or not states <= set('PFI'):
            raise ValueError('Completed assessment requires P/F/I properties')
        expected = 'F' if 'F' in states else 'I' if 'I' in states else 'P'
        if status != expected:
            raise ValueError('Assessment/property status mismatch')
    execution_files(record, execution, started)
    return status, assessment, tool


def render(records, allow_pending=False):
    cards = {card['id']: card for card in BATCH['cards']}
    if len(BATCH['cards']) != 12 or len(cards) != 12 or BATCH['counting']['declared_N'] != 12:
        raise ValueError('Expected fixed N=12 design')
    if any(c['primary_group'] not in BATCH['primary_groups'] for c in cards.values()):
        raise ValueError('Unknown card primary group')
    results = {}
    backend_identities = {}
    checker_identity = None
    for record in records:
        key = record.get('condition_id'), record.get('backend')
        if key[0] not in cards or key[1] not in BACKENDS:
            raise ValueError('Unknown condition/backend: ' + str(key))
        if key in results:
            raise ValueError('Duplicate condition/backend: ' + str(key))
        outcome, assessment, tool = validate(record)
        if assessment is not None:
            identity = record['identity']
            shared = (identity['source_revision'], frozen_identity(stable_tool(tool)),
                      frozen_identity(assessment['checker_identity']), identity['input_manifest']['sha256'])
            if key[1] in backend_identities and backend_identities[key[1]] != shared:
                raise ValueError('Mixed backend execution identity: ' + key[1])
            backend_identities[key[1]] = shared
            if checker_identity is not None and checker_identity != shared[2]:
                raise ValueError('Mixed checker identity across backends')
            checker_identity = shared[2]
        results[key] = (outcome, assessment, tool, record)
    missing = [(c, b) for c in cards for b in BACKENDS if (c, b) not in results]
    if missing and not allow_pending:
        raise ValueError('Missing condition/backend slots: ' + str(missing))
    for key in missing:
        results[key] = ('T', None, None, None)
    lines = [
        '# core-v1 results', '',
        f'N=12 conditions; 4 backends; 48 slots. Cards SHA256 `{CARDS_SHA}`.',
        'Immutable card design status: ' + text(BATCH['design_status']) + '.',
        'Actual outcomes below are separate from card design status and status_by_backend.',
        'Counts are P/F/U/X/I/T: pass/fail/confirmed unsupported/execution failure/indeterminate/not run.',
        'Missing slots are T only when --allow-pending is explicit. Properties and old31 add no conditions.',
        '', '| Primary group | N | ' + ' | '.join(BACKENDS) + ' |',
        '| --- | ---: | ' + ' | '.join(['---'] * 4) + ' |',
    ]
    def counts(selected, backend):
        counter = Counter(results[c, backend][0] for c in selected)
        return '/'.join(str(counter[s]) for s in STATUSES)
    for group in BATCH['primary_groups']:
        selected = [c for c in cards if cards[c]['primary_group'] == group]
        lines.append('| ' + group + ' | ' + str(len(selected)) + ' | ' + ' | '.join(counts(selected, b) for b in BACKENDS) + ' |')
    lines.extend(['| Total | 12 | ' + ' | '.join(counts(cards, b) for b in BACKENDS) + ' |', '',
                  '| Condition | Primary group | Scenario | Features/operators | ' + ' | '.join(BACKENDS) + ' |',
                  '| --- | --- | --- | --- | ' + ' | '.join(['---'] * 4) + ' |'])
    for c, card in cards.items():
        cells = []
        for backend in BACKENDS:
            status, assessment, _, record = results[c, backend]
            cells.append('[' + status + '](<' + record['assessment']['path'] + '>)' if assessment else status)
        lines.append('| ' + ' | '.join([c, card['primary_group'], text(card['scenario']), text(', '.join(card['features'])), *cells]) + ' |')
    lines.extend(['', '## Execution identities and limits', '',
                  'Assessment links retain per-property errors, uncertainty, units and claim limits. No combined error ratio or timing is computed.',
                  'Identity files and methods are evidence references, not an independent certification of their scientific bounds.',
                  'Local raw files do not establish public reproducibility; public availability is a declared publication link, not a reproducibility verdict.', '',
                  '| Condition/backend | Source revision | Tool version/identity | Method | Availability | Execution/checker/frozen inputs |',
                  '| --- | --- | --- | --- | --- | --- |'])
    for (c, backend), (_, assessment, tool, record) in results.items():
        if assessment is None:
            continue
        identity = record['identity']
        version = tool.get('reported', tool.get('version', 'unknown'))
        if 'versions' in tool:
            version = {name: value.get('self_report', 'unknown') for name, value in tool['versions'].items()}
        if tool.get('unknowns'):
            version = {'reported': version, 'unknowns': tool['unknowns']}
        availability = identity['availability']
        if availability == 'public':
            availability += ' ' + identity['public_url']
        lines.append('| ' + ' | '.join([c + '/' + backend, text(identity['source_revision']) + ' ' + link(identity['condition_started']),
            text(json.dumps(version, sort_keys=True)) + ' ' + link(identity['tool']) + ' SHA256 `' + identity['tool']['sha256'] + '`',
            text(identity['method']), text(availability), link(record['execution']) + ' / `' + assessment['checker_identity']['sha256'] + '` / ' + link(identity['input_manifest']) + ' SHA256 `' + identity['input_manifest']['sha256'] + '`']) + ' |')
    histories = [(key, value[3]) for key, value in results.items() if value[3] and value[3].get('prior_attempts')]
    if histories:
        lines.extend(['', '## Declared prior attempts', '',
                      'Prior attempts do not increase N. Selection is explicit; no best-result rule is applied. The collector must preserve all attempts; this view does not certify completeness.', '',
                      '| Condition/backend | Selected execution | Prior execution artifacts | Selection reason |',
                      '| --- | --- | --- | --- |'])
        for (c, backend), record in histories:
            lines.append('| ' + ' | '.join([c + '/' + backend, link(record['execution']),
                ', '.join(link(ref) for ref in record['prior_attempts']), text(record['selection_reason'])]) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records', type=Path, help='JSON array; artifact paths relative to this file')
    parser.add_argument('--allow-pending', action='store_true', help='explicitly fill absent fixed slots as T')
    args = parser.parse_args()
    records = json.loads(args.records.read_text())
    for record in records:
        for ref in [record.get('assessment'), record.get('execution'), *record.get('prior_attempts', []), *[record.get('identity', {}).get(k) for k in ('tool', 'condition_started', 'lane_started', 'input_manifest', 'execution_manifest', 'observation')]]:
            if isinstance(ref, dict) and isinstance(ref.get('path'), str):
                ref['path'] = str((args.records.resolve().parent / ref['path']).resolve())
    print(render(records, args.allow_pending), end='')
