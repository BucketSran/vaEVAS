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
    'missing_compile_artifact', 'missing_waveform', 'observation_invalid',
    'condition_directory_limit_exceeded', 'deck_parse_error'))
# A reviewed checker correction is admitted by fixed artifact hashes, never by
# whichever checker happens to be installed at report time.
CHECKER_ANALYSIS_METHODS = {'native_si_time_order_v1': {
    'criteria.py': 'ecdabb0c187d968400e8ee8c23f6f99a7552b3533962917539557436b8a95c1c',
    'oracle.py': '96ece5a943113a6e6e79b441145a2f2238da43938914605d884b5fd0414e72dc',
    'core-v1.json': CARDS_SHA}}


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


def final_execution(record, execution, manifest=None):
    ref = record['identity']['execution_manifest']
    if manifest is None:
        manifest = read_artifact(ref)
    root = Path(ref['path']).parent.resolve()
    try:
        selected_path = str(Path(record['execution']['path']).resolve().relative_to(root))
    except ValueError:
        raise ValueError('Selected execution outside its final lane') from None
    if manifest.get(selected_path, {}).get('sha256') != record['execution']['sha256']:
        raise ValueError('Final execution artifact missing from FILE_MANIFEST')
    final_ref = {'path': str(root / 'EXECUTION.json'),
                 'sha256': manifest.get('EXECUTION.json', {}).get('sha256')}
    rows = read_artifact(final_ref)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Final EXECUTION row must come from a valid lane array')
    matches = [row for row in rows if row.get('condition') == record['condition_id'] and row.get('backend') == record['backend']]
    if len(matches) != 1 or matches[0] != execution:
        raise ValueError('Final EXECUTION row must be unique and identical to selected execution')


def deck_parse_evidence(record, execution, work):
    """Bind the calibrated caret diagnostics and retained raw to real artifacts."""
    if record['backend']!='gnucap_modelgen' or execution.get('failure_stage')!='deck_parse':
        raise ValueError('Deck parse failure must belong to Gnucap deck_parse stage')
    stages=[stage for stage in execution.get('stages',[]) if stage.get('stage')=='simulate']
    if (len(stages)!=1 or stages[0].get('log')!='simulate.log'
            or type(stages[0].get('returncode')) is not int or stages[0]['returncode']!=0
            or stages[0].get('log_sha256')!=execution.get('diagnostic_log_sha256')):
        raise ValueError('Deck parse diagnostic must bind actual simulate stage/log')
    log_path=(work/'simulate.log').resolve()
    if not log_path.is_relative_to(work.resolve()):
        raise ValueError('Deck parse diagnostic log outside its condition directory')
    log_ref={'path':str(log_path),'sha256':execution.get('diagnostic_log_sha256')}
    lines=artifact_bytes(log_ref).decode(errors='replace').splitlines()
    expected=[{'line_number':i,'text':line} for i,line in enumerate(lines,1)
              if re.match(r'^\s*\^\s*\?\s*',line)]
    diagnostics=execution.get('diagnostics')
    if (not expected or not isinstance(diagnostics,list)
            or any(not isinstance(item,dict) or type(item.get('line_number')) is not int
                   or not isinstance(item.get('text'),str) for item in diagnostics)
            or diagnostics!=expected):
        raise ValueError('Deck parse diagnostics must match actual log lines')
    refs=[log_ref]
    rejected=execution.get('rejected_waveform')
    if rejected is not None:
        if (not isinstance(rejected,dict) or not isinstance(rejected.get('path'),str)
                or not rejected['path'] or Path(rejected['path']).is_absolute()
                or '..' in Path(rejected['path']).parts):
            raise ValueError('Rejected waveform must stay within its condition directory')
        path=(work/rejected['path']).resolve()
        if not path.is_relative_to(work.resolve()):
            raise ValueError('Rejected waveform outside its condition directory')
        ref={'path':str(path),'sha256':rejected.get('sha256')}
        artifact_bytes(ref)
        refs.append(ref)
    return refs

def execution_files(record, execution, started, checker):
    identity = record['identity']
    lane = read_artifact(identity['lane_started'])
    inputs = read_artifact(identity['input_manifest'])
    manifest = read_artifact(identity['execution_manifest'])
    if lane.get('backend') != record['backend'] or lane.get('input_manifest_sha256') != identity['input_manifest']['sha256'] or lane.get('fixed_conditions') != [c['id'] for c in BATCH['cards']] or inputs.get('core.json', {}).get('sha256') != CARDS_SHA:
        raise ValueError('Frozen input/lane identity mismatch')
    input_root = Path(identity['input_manifest']['path']).parent
    frozen = {}
    for name in ('ADAPTER_IDENTITY.json', 'CHECKER_IDENTITY.json'):
        frozen[name] = read_artifact({'path': str(input_root / name),
                                     'sha256': inputs.get(name, {}).get('sha256')})
        if not isinstance(frozen[name], dict):
            raise ValueError('Frozen identity must be an object: ' + name)
    runner_sha = frozen['ADAPTER_IDENTITY.json'].get('experiments/backends/paper/runner.py')
    if not re.fullmatch('[0-9a-f]{64}', str(runner_sha or '')) or lane.get('runner_sha256') != runner_sha:
        raise ValueError('Lane runner identity differs from frozen adapter')
    for name in ('criteria.py', 'oracle.py'):
        digest = frozen['CHECKER_IDENTITY.json'].get('evas/validation/paper/' + name)
        if not re.fullmatch('[0-9a-f]{64}', str(digest or '')) or checker['files'].get(name) != digest:
            raise ValueError('Assessment checker differs from frozen checker: ' + name)
    lane_root = Path(identity['lane_started']['path']).parent
    if Path(identity['execution_manifest']['path']).parent.resolve() != lane_root.resolve():
        raise ValueError('Execution FILE_MANIFEST must belong to its lane')
    final_execution(record, execution, manifest)
    refs = [record['execution'], *[identity[k] for k in ('tool', 'condition_started', 'lane_started')]]
    if identity.get('observation'):
        refs.append(identity['observation'])
    work = Path(identity['condition_started']['path']).parent
    if execution.get('status')=='deck_parse_error':
        refs.extend(deck_parse_evidence(record,execution,work))
    if execution.get('waveform') or execution.get('status') == 'waveform_available':
        waveform = execution.get('waveform')
        if not isinstance(waveform, str) or not waveform or Path(waveform).is_absolute() or '..' in Path(waveform).parts:
            raise ValueError('Waveform must be a relative path within its condition directory')
        waveform_path = (work / waveform).resolve()
        try:
            waveform_path.relative_to(work.resolve())
        except ValueError:
            raise ValueError('Waveform outside its condition directory') from None
        waveform_ref = {'path': str(waveform_path), 'sha256': execution.get('waveform_sha256')}
        artifact_bytes(waveform_ref)
        refs.append(waveform_ref)
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


def analysis_observation(record, execution):
    """Bind a new analysis to immutable actual observations, not a new run."""
    original_ref = record['identity'].get('observation')
    original = read_artifact(original_ref)
    derived_ref = record.get('analysis_observation')
    if derived_ref is None:
        if any(key in record for key in ('derivation', 'analysis_method', 'prior_analyses')):
            raise ValueError('Analysis fields require analysis_observation')
        return original_ref
    if record['backend'] != 'evas' or not isinstance(record.get('analysis_method'), str) or not record['analysis_method'].strip():
        raise ValueError('Derived analysis requires EVAS and explicit analysis_method')
    packet = read_artifact(record.get('derivation'))
    if packet.get('schema_version') != 1:
        raise ValueError('Invalid analysis derivation schema')
    expected = {'execution': record['execution'], 'original_observation': original_ref,
                'derived_observation': derived_ref}
    for key, ref in expected.items():
        bound = packet.get(key)
        if not isinstance(bound, dict) or bound.get('sha256') != ref.get('sha256') or Path(bound.get('path', '')).resolve() != Path(ref['path']).resolve():
            raise ValueError('Analysis derivation identity mismatch: ' + key)
        artifact_bytes(bound)
    work = Path(record['identity']['condition_started']['path']).parent.resolve()
    manifest = read_artifact(record['identity']['execution_manifest'])
    lane = Path(record['identity']['execution_manifest']['path']).parent.resolve()
    for key, name in (('raw', 'raw-response.json'), ('source', 'dut.va')):
        ref = packet.get(key)
        if not isinstance(ref, dict) or Path(ref.get('path', '')).resolve() != work / name:
            raise ValueError('Analysis actual artifact path mismatch: ' + key)
        artifact_bytes(ref)
        relative = str((work / name).relative_to(lane))
        if manifest.get(relative, {}).get('sha256') != ref['sha256']:
            raise ValueError('Analysis actual artifact outside frozen manifest: ' + key)
    if packet['source']['sha256'] != execution.get('source_sha256'):
        raise ValueError('Analysis source differs from execution')
    adapter = packet.get('adapter')
    artifact_bytes(adapter)
    evidence_ref = packet.get('evidence')
    evidence = read_artifact(evidence_ref)
    bound_adapter = evidence.get('analysis_adapter')
    if not isinstance(bound_adapter, dict) or bound_adapter.get('sha256') != adapter['sha256'] or Path(bound_adapter.get('path', '')).resolve() != Path(adapter['path']).resolve():
        raise ValueError('Analysis evidence adapter identity mismatch')
    artifact_bytes(bound_adapter)
    for ref in (record['derivation'], evidence_ref, derived_ref, adapter):
        if Path(ref['path']).resolve().is_relative_to(work):
            raise ValueError('Analysis artifacts must stay outside actual run directory')
    if evidence.get('schema_version') != 1 or evidence.get('condition') != record['condition_id'] or evidence.get('backend') != record['backend']:
        raise ValueError('Analysis evidence condition/backend mismatch')
    identities = evidence.get('identities', {})
    for key, ref in (('normalized', original_ref), ('raw', packet['raw']), ('source', packet['source'])):
        bound = identities.get(key)
        if not isinstance(bound, dict) or bound.get('sha256') != ref['sha256'] or Path(bound.get('path', '')).resolve() != Path(ref['path']).resolve():
            raise ValueError('Analysis evidence actual identity mismatch: ' + key)
    for ref in identities.values():
        artifact_bytes(ref)
    chain = evidence.get('execution_identity', {})
    final_ref = chain.get('artifacts', {}).get('final_record')
    if not isinstance(final_ref, dict) or final_ref.get('sha256') != record['execution']['sha256'] or Path(final_ref.get('path', '')).resolve() != Path(record['execution']['path']).resolve():
        raise ValueError('Analysis evidence final execution mismatch')
    for key, ref in (('lane_manifest', record['identity']['execution_manifest']), ('tool', record['identity']['tool'])):
        bound = chain.get('artifacts', {}).get(key)
        if not isinstance(bound, dict) or bound.get('sha256') != ref['sha256'] or Path(bound.get('path', '')).resolve() != Path(ref['path']).resolve():
            raise ValueError('Analysis execution chain identity mismatch: ' + key)
    for ref in chain.get('artifacts', {}).values():
        artifact_bytes(ref)
    derived = read_artifact(derived_ref)
    for key in ('schema_version', 'condition', 'backend', 'status', 'units', 'rows'):
        if key not in original or derived.get(key) != original[key]:
            raise ValueError('Derived observation changed actual ' + key)
    if original.get('condition') != record['condition_id'] or original.get('backend') != record['backend']:
        raise ValueError('Original observation condition/backend mismatch')
    raw = read_artifact(packet['raw'])
    try:
        rows = [dict(time=t, **dict(zip(raw['nodes'], solution['voltages'], strict=True)))
                for t, solution in zip(raw['transient']['times'], raw['solutions'], strict=True)]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Invalid actual raw response') from error
    if rows != original['rows']:
        raise ValueError('Analysis raw/normalized rows mismatch')
    def geometry(observation):
        metadata = dict(observation.get('metadata', {}))
        for key in ('sample_origins', 'unmatched_boundary_records', 'boundary_cohort_rejection'):
            metadata.pop(key, None)
        if 'local_windows' in metadata:
            metadata['local_windows'] = [{k: v for k, v in window.items() if k != 'proved_center_rows'}
                                         for window in metadata['local_windows']]
        return metadata
    if geometry(original) != geometry(derived):
        raise ValueError('Derived observation changed actual observation geometry')
    for role, ref in derived.get('qualification', {}).get('qualification_evidence', {}).items():
        if not isinstance(ref, dict) or ref.get('sha256') != evidence_ref['sha256'] or Path(ref.get('artifact_path', '')).resolve() != Path(evidence_ref['path']).resolve() or evidence.get('roles', {}).get(role, {}).get('status') != 'established':
            raise ValueError('Derived qualification does not bind an established evidence role')
    priors = record.get('prior_analyses')
    if not isinstance(priors, list) or not priors:
        raise ValueError('Derived analysis must retain prior_analyses')
    seen = {record['assessment']['sha256']}
    for ref in priors:
        prior = read_artifact(ref)
        if ref['sha256'] in seen or prior.get('condition_id') != record['condition_id'] or prior.get('execution_sha256') != record['execution']['sha256'] or prior.get('status') not in ('P', 'F', 'I') or prior.get('execution_state') != 'completed':
            raise ValueError('Invalid prior analysis for this actual execution')
        seen.add(ref['sha256'])
        if prior.get('input_observation_sha256') != original_ref['sha256']:
            raise ValueError('Prior analysis must assess the original observation')
        prior_record = {k: v for k, v in record.items() if k not in ('analysis_observation', 'derivation', 'analysis_method', 'prior_analyses', 'checker_reanalysis')}
        prior_record['assessment'] = ref
        validate(prior_record)
    return derived_ref


def checker_analysis(record, assessment, checker):
    """Validate a reviewed checker correction while retaining the old verdict."""
    ref = record.get('checker_reanalysis')
    if ref is None:
        return checker
    packet = read_artifact(ref)
    admitted = CHECKER_ANALYSIS_METHODS.get(packet.get('method'))
    if packet.get('schema_version') != 1 or admitted is None or any(not isinstance(digest, str) for digest in admitted.values()):
        raise ValueError('Unadmitted checker reanalysis method')
    selected = packet.get('assessment')
    if not isinstance(selected, dict) or selected.get('sha256') != record['assessment']['sha256'] or Path(selected.get('path', '')).resolve() != Path(record['assessment']['path']).resolve():
        raise ValueError('Checker reanalysis assessment identity mismatch')
    artifact_bytes(selected)
    snapshot = packet.get('checker', {})
    files = snapshot.get('files', {})
    if snapshot.get('identity') != checker or checker['files'] != admitted or set(files) != set(admitted):
        raise ValueError('Checker reanalysis fixed identity mismatch')
    for name, digest in admitted.items():
        artifact = files[name]
        if not isinstance(artifact, dict) or artifact.get('sha256') != digest:
            raise ValueError('Checker reanalysis snapshot identity mismatch: ' + name)
        artifact_bytes(artifact)
    for name in ('calibration', 'review'):
        if not artifact_bytes(packet.get(name)):
            raise ValueError('Empty checker reanalysis evidence: ' + name)
    original = read_artifact(packet.get('original_record'))
    if not isinstance(original, dict):
        raise ValueError('Checker reanalysis requires original record')
    for key in set(original) | set(record):
        if key not in ('assessment', 'checker_reanalysis') and original.get(key) != record.get(key):
            raise ValueError('Checker reanalysis changed original record: ' + key)
    if original.get('assessment') == record.get('assessment'):
        raise ValueError('Checker reanalysis must preserve a separate original assessment')
    validate(original)
    return read_artifact(original['assessment'])['checker_identity']


def validate(record):
    prior_attempts(record)
    if record.get('status') == 'T' and 'assessment' not in record:
        if any(key in record for key in ('analysis_observation', 'derivation', 'analysis_method', 'prior_analyses', 'checker_reanalysis')):
            raise ValueError('Derived analysis requires completed waveform execution')
        if 'execution' in record:
            execution = read_artifact(record['execution'])
            if execution.get('condition') != record['condition_id'] or execution.get('backend') != record['backend'] or execution.get('status') != 'not_run':
                raise ValueError('T execution status must be not_run for this condition/backend')
            if record.get('identity', {}).get('execution_manifest'):
                final_execution(record, execution)
        return 'T', None, None
    identity = record.get('identity', {})
    if not all(identity.get(k) for k in ('source_revision', 'tool', 'condition_started', 'lane_started', 'input_manifest', 'execution_manifest', 'method', 'availability')):
        raise ValueError('Execution identity requires source_revision/tool/condition_started/lane_started/input_manifest/execution_manifest/method/availability')
    if identity['availability'] not in ('local-only', 'restricted', 'public'):
        raise ValueError('Unknown availability')
    if identity['availability'] == 'public' and (not isinstance(identity.get('public_url'), str) or not identity['public_url'].startswith('https://')):
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
    if not isinstance(checker, dict) or not isinstance(checker.get('files'), dict) or not isinstance(checker.get('runtime'), dict):
        raise ValueError('Missing checker files/runtime identity')
    if checker['files'].get('core-v1.json') != CARDS_SHA:
        raise ValueError('Assessment card identity mismatch')
    if not re.fullmatch('[0-9a-f]{64}', str(checker.get('sha256', ''))):
        raise ValueError('Missing checker identity')
    dependency = {key: checker[key] for key in ('files', 'runtime')}
    if hashlib.sha256(json.dumps(dependency, sort_keys=True).encode()).hexdigest() != checker['sha256']:
        raise ValueError('Checker dependency digest mismatch')
    execution_checker = checker_analysis(record, assessment, checker)
    status = assessment.get('status')
    if not isinstance(status, str) or len(status) != 1 or status not in STATUSES:
        raise ValueError('Unknown assessment status')
    state = assessment.get('execution_state')
    if state != 'completed' and any(key in record for key in ('analysis_observation', 'derivation', 'analysis_method', 'prior_analyses')):
        raise ValueError('Derived analysis requires completed waveform execution')
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
        if not isinstance(execution.get('observation'), dict) or execution['observation'].get('sha256') != observation['sha256']:
            raise ValueError('Execution/assessment observation hash mismatch')
        analysis_input = analysis_observation(record, execution)
        if assessment.get('input_observation_sha256') != analysis_input['sha256']:
            raise ValueError('Assessment input observation hash mismatch')
        properties = assessment.get('properties', [])
        states = {p.get('status') for p in properties}
        if not states or not states <= set('PFI'):
            raise ValueError('Completed assessment requires P/F/I properties')
        expected = 'F' if 'F' in states else 'I' if 'I' in states else 'P'
        if status != expected:
            raise ValueError('Assessment/property status mismatch')
    execution_files(record, execution, started, execution_checker)
    return status, assessment, tool


def render(records, allow_pending=False):
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValueError('Records must be an array of objects')
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
    analyses = [(key, value[3]) for key, value in results.items() if value[3] and value[3].get('analysis_observation')]
    if analyses:
        lines.extend(['', '## Derived analyses of unchanged executions', '',
                      'Original observations and prior analyses remain immutable. Reanalysis adds no run or condition.', '',
                      '| Condition/backend | Method | Derived observation / derivation / adapter | Prior analyses |',
                      '| --- | --- | --- | --- |'])
        for (c, backend), record in analyses:
            packet = read_artifact(record['derivation'])
            lines.append('| ' + ' | '.join([c + '/' + backend, text(record['analysis_method']),
                link(record['analysis_observation']) + ' / ' + link(record['derivation']) + ' / ' + link(packet['adapter']) + ' SHA256 `' + packet['adapter']['sha256'] + '`',
                ', '.join(read_artifact(ref)['status'] + ' ' + link(ref) for ref in record['prior_analyses'])]) + ' |')
    reanalyses = [(key, value[3]) for key, value in results.items() if value[3] and value[3].get('checker_reanalysis')]
    if reanalyses:
        lines.extend(['', '## Reviewed checker reanalyses', '',
                      'Original verdicts and frozen execution identities remain preserved. No new execution is counted.', '',
                      '| Condition/backend | Method / evidence | Original verdict | Current checker identity |',
                      '| --- | --- | --- | --- |'])
        for (c, backend), record in reanalyses:
            packet = read_artifact(record['checker_reanalysis'])
            original = read_artifact(packet['original_record'])
            previous = read_artifact(original['assessment'])
            lines.append('| ' + ' | '.join([c + '/' + backend,
                text(packet['method']) + ' ' + link(record['checker_reanalysis']) + ' / ' + link(packet['calibration']) + ' / ' + link(packet['review']),
                previous['status'] + ' ' + link(original['assessment']) + ' / ' + link(packet['original_record']),
                '`' + packet['checker']['identity']['sha256'] + '`']) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records', type=Path, help='JSON array; artifact paths relative to this file')
    parser.add_argument('--allow-pending', action='store_true', help='explicitly fill absent fixed slots as T')
    args = parser.parse_args()
    records = json.loads(args.records.read_text())
    for record in records:
        for ref in [record.get('assessment'), record.get('execution'), record.get('analysis_observation'), record.get('derivation'), record.get('checker_reanalysis'), *record.get('prior_analyses', []), *record.get('prior_attempts', []), *[record.get('identity', {}).get(k) for k in ('tool', 'condition_started', 'lane_started', 'input_manifest', 'execution_manifest', 'observation')]]:
            if isinstance(ref, dict) and isinstance(ref.get('path'), str):
                ref['path'] = str((args.records.resolve().parent / ref['path']).resolve())
    print(render(records, args.allow_pending), end='')
