"""Recipe and receipt adapters for the preserved legacy Q experiments."""
import json
import hashlib
import math
import os
import tempfile
import re
import shutil
from pathlib import Path
from time import perf_counter

from inputs import sha
from precision_precheck import measure, pilot_plan, positive, safe_file, check_deck


def save(path, value):
    """Atomically checkpoint receipts in this newly created execution lane."""
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
        temporary = stream.name
    os.replace(temporary, path)


def select_plan(plan, backend, cases=(), tiers=(), variant=None):
    if backend not in ('evas', 'spectre'):
        raise ValueError('unknown backend: ' + str(backend))
    for values, field in ((cases, 'condition'), (tiers, 'tier')):
        if values and (len(values) != len(set(values)) or set(values) - {r[field] for r in plan}):
            raise ValueError('unknown or duplicate selector: ' + field)
    if variant is not None and variant not in {r['variant'] for r in plan}:
        raise ValueError('unknown variant selector')
    selected = [r for r in plan if r['backend'] == backend and
                (not cases or r['condition'] in cases) and
                (not tiers or r['tier'] in tiers) and
                (variant is None or r['variant'] == variant)]
    if not selected:
        raise ValueError('empty selection')
    return selected


def paired_pilot(plan, cards):
    # Retain original/trace for every chosen condition and tier. Grouping is
    # based on the legacy physical kind, without introducing breadth families.
    tagged = [{**r, 'family': r['variant'],
               'group_id': cards[r['condition']].get('kind', r['condition'])} for r in plan]
    chosen_conditions = {(r['condition'], r['tier'], r['profile']) for r in pilot_plan(tagged)}
    return [r for r in plan if (r['condition'], r['tier'], r['profile']) in chosen_conditions]


def inspect_plan(inputs, plan, cards, profiles, tier_profiles, trace_source, validate_controls):
    manifest = json.loads(safe_file(inputs, 'MANIFEST.json').read_text())
    if not plan or len({(r['backend'], r['label']) for r in plan}) != len(plan):
        raise ValueError('empty or duplicate frozen slots')
    for row in plan:
        expected_label=row['condition'].replace(':','_')+'--'+row['tier']+'--'+row['variant']
        if row['label']!=expected_label or row['work']!='runs/'+row['backend']+'/'+expected_label:
            raise ValueError('frozen label/work binding')
        work = inputs / row['work']
        if work.is_symlink() or not work.resolve().is_relative_to(inputs.resolve()):
            raise ValueError('unsafe frozen work')
        for name in ('dut.va', 'original.va', 'condition.json', 'requested_settings.json',
                     'requested_times.json', 'SOURCE_BINDING.json', row['deck']):
            path = safe_file(work, name)
            if sha(path) != manifest.get(str(path.relative_to(inputs))):
                raise ValueError('recipe manifest mismatch: ' + str(path))
        card = json.loads((work / 'condition.json').read_text())
        expected = cards.get(row['condition'])
        if expected is not None:expected = json.loads(json.dumps(expected))
        if expected is None or row['tier'] not in tier_profiles or row['variant'] not in ('original', 'trace'):
            raise ValueError('unknown frozen condition/tier/variant')
        if row['backend'] == 'evas' and row['variant'] != 'original':
            raise ValueError('EVAS trace slot unsupported')
        for key, value in expected.items():
            if key != 'times' and card.get(key) != value:
                raise ValueError('condition contract binding: ' + key)
        if card.get('variant', row['variant']) != row['variant'] or card['id'] != row['condition']:
            raise ValueError('condition/variant binding')
        original = (work / 'original.va').read_text()
        wanted_source = trace_source(card) if row['variant'] == 'trace' else expected['source']
        if original != expected['source'] or (work / 'dut.va').read_text() != wanted_source:
            raise ValueError('original/trace source binding')
        for filename, field in (('original.va', 'original_source_sha256'), ('dut.va', 'executed_source_sha256'),
                                (row['deck'], 'deck_sha256'), ('SOURCE_BINDING.json', 'source_binding_sha256')):
            if sha(work / filename) != row.get(field):
                raise ValueError('plan hash binding: ' + field)
        binding = json.loads((work / 'SOURCE_BINDING.json').read_text())
        if binding['source_identity'] != json.loads((inputs / 'SOURCE_IDENTITY.json').read_text()):
            raise ValueError('source identity binding')
        settings = json.loads((work / 'requested_settings.json').read_text())
        pid = tier_profiles[row['tier']]
        profile = profiles[pid]
        if row['profile'] != pid or any(settings.get(k) != v for k, v in profile.items()):
            raise ValueError('profile binding')
        for name in ('stop_s', 'maxstep_s', 'spice_maxstep_s', 'reltol', 'vabstol_V', 'iabstol_A'):
            if not positive(settings.get(name)):
                raise ValueError('invalid requested control: ' + name)
        if (settings['stop_s'] != card['stop_s'] or not positive(card['unit_s']) or
                settings['maxstep_s'] != card['unit_s'] * profile['step_units'] or
                settings['spice_maxstep_s'] != settings['maxstep_s']):
            raise ValueError('time control binding')
        times = json.loads((work / 'requested_times.json').read_text())
        if (times != card.get('times', times) or len(times) < 2 or times[0] != 0 or times[-1] != card['stop_s'] or
                any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or
                any(a >= b for a, b in zip(times, times[1:])) or not set(expected['times']).issubset(times)):
            raise ValueError('observation time binding')
        physical = card.get('binding', {'top_module': card.get('top'), 'ports': card.get('ports'),
                                         'parameters': card.get('parameters')})
        ports = physical['ports']
        if not ports or len(ports) != len(set(ports)):
            raise ValueError('port binding')
        actual_ports = ['0' if p == 'r' and card.get('kind') == 'nt' else p for p in ports]
        adapted = dict(top=physical['top_module'], ports=actual_ports, inputs=card['inputs'])
        if row['backend'] == 'spectre':
            check_deck(work, row, adapted, settings, times)
            validate_controls((work / row['deck']).read_text())
        else:
            request = json.loads((work / row['deck']).read_text())
            instance = dict(name='dut', module=physical['top_module'],
                            ports=dict(zip(ports, actual_ports)), parameters=physical['parameters'])
            controls = dict(source='dut.va', requested_times='requested_times.json', stop=settings['stop_s'],
                            max_step=settings['maxstep_s'], reltol=settings['reltol'], vabstol=settings['vabstol_V'])
            if (request.get('instances') != [instance] or request.get('inputs') != card['inputs'] or
                    any(request.get(k) != v for k, v in controls.items())):
                raise ValueError('EVAS request binding')
    return dict(status='ready', slots=len(plan), claim='requested recipe consistency only; actual tool and scientific acceptance unverified')


def precheck(inputs, backend, verify, recipe, cards, *, cases=(), tiers=(), variant=None, pilot=False):
    verify(inputs)
    full = select_plan(json.loads((inputs / 'PLAN.json').read_text()), backend, cases, tiers, variant)
    report = recipe(inputs, full)
    chosen = paired_pilot(full, cards) if pilot else full
    return {**report, 'scope': 'pilot' if pilot else 'full-selection', 'selected_slots': len(chosen),
            'selected_labels': [r['label'] for r in chosen], 'omitted_slots': len(full) - len(chosen)}


def run(inputs, output, backend, profile_path, execution, verify, recipe, cards, analyze_work,
        execute_one, *, cases=(), tiers=(), variant=None, pilot=False, defer_analysis=False, finalize=None):
    full = select_plan(execution.load(inputs / 'PLAN.json'), backend, cases, tiers, variant)
    plan = paired_pilot(full, cards) if pilot else full
    output.mkdir(parents=True, exist_ok=False)
    results = []
    attempts = []
    started = perf_counter()
    timings = dict(status='interrupted', precheck_s=0, tool_preflight_s=0)
    save(output / 'STARTED.json', dict(selected=plan, full_selection=full, limits=execution.LIMITS,
         automatic_retries=0, input_manifest_sha256=sha(inputs / 'MANIFEST.json'),
         profile_sha256=sha(profile_path), defer_analysis=defer_analysis, scope='pilot' if pilot else 'full-selection'))
    try:
        with measure(timings, 'precheck_s'):
            verify(inputs)
            save(output / 'RECIPE_CHECK.json', recipe(inputs, full))
            profile = execution.load(profile_path)
            for name in ('MANIFEST.json', 'PLAN.json', 'SOURCE_IDENTITY.json', 'CONTRACT.json'):
                shutil.copyfile(inputs / name, output / ('FROZEN_' + name))
        with measure(timings, 'tool_preflight_s'):
            tool, env = execution.preflight(backend, profile, output, execution.LIMITS)
            save(output / 'TOOL_IDENTITY.json', tool)
        for row in plan:
            phases = dict(input_preparation=0, backend_execution=0, inline_analysis=0)
            with measure(phases, 'input_preparation'):
                verify(inputs)
                execution.verify_tool(tool, profile, env)
                work = output / 'runs' / row['label']
                shutil.copytree(inputs / row['work'], work)
            attempt = dict(label=row['label'], status='invoked', stages=[], stage_receipts_complete=False)
            attempts.append(attempt)
            save(output / 'ATTEMPTS.json', attempts)
            try:
                with measure(phases, 'backend_execution'):
                    record = {**row, **execute_one(backend, tool, env, work)}
                attempt.update(status=record['status'], stages=record.get('stages', []), stage_receipts_complete=True)
            except Exception as exc:
                record = {**row, 'status': 'execution_failed', 'reason': repr(exc), 'abort_batch': True}
                attempt.update(status='adapter_error', reason=repr(exc), stages=[execution.load(work / (n + '.json'))
                    for n in ('compile', 'simulate') if (work / (n + '.json')).is_file()])
            record['phase_timings_s'] = phases
            if defer_analysis:
                record.update(analysis_status='pending' if record['status'] == 'waveform_available' else 'not_available',
                              engineering_verdict='unknown', Q_qualification=dict(status='unknown', reason='analysis deferred'))
            elif record['status'] == 'waveform_available':
                try:
                    with measure(phases, 'inline_analysis'):
                        record.update(analyze_work(work, record, tool))
                except Exception as exc:
                    record.update(analysis_error=repr(exc), engineering_verdict='evidence_insufficient')
            record['directory_budget'] = execution.directory_budget(work)
            save(work / 'RESULT.json', record)
            results.append(record)
            save(output / 'EXECUTION.json', results)
            save(output / 'ATTEMPTS.json', attempts)
            if record.get('abort_batch') or record['directory_budget']['status'] != 'within_limit':
                break
        timings['status'] = 'complete' if len(results) == len(plan) else 'aborted'
    finally:
        done = {r['label'] for r in results}
        chosen = {r['label'] for r in plan}
        results.extend({**r, 'status': 'not_run', 'reason': 'batch did not reach this case' if r['label'] in chosen
                        else 'pilot did not select this frozen slot'} for r in full if r['label'] not in done)
        save(output / 'EXECUTION.json', results)
        save(output / 'ATTEMPTS.json', attempts)
        if finalize is not None:
            try:finalize(output,results,defer_analysis)
            except Exception as exc:save(output/'FINALIZATION_ERROR.json',dict(reason=repr(exc)))
        timings['cases'] = {r['label']: r['phase_timings_s'] for r in results if 'phase_timings_s' in r}
        timings['claim'] = 'named wall phases; backend includes compile/export; total excludes final receipt writes; no speed ranking'
        with measure(timings, 'artifact_sealing_s'):
            manifest = file_manifest(output)
        timings['total_s'] = perf_counter() - started
        save(output / 'TIMINGS.json', timings)
        manifest['TIMINGS.json'] = dict(sha256=sha(output / 'TIMINGS.json'), bytes=(output / 'TIMINGS.json').stat().st_size)
        save(output / 'FILE_MANIFEST.json', manifest)
    return results


def file_manifest(lane):
    return {str(p.relative_to(lane)): dict(sha256=sha(p), bytes=p.stat().st_size)
            for p in sorted(lane.rglob('*')) if p.is_file() and p != lane / 'FILE_MANIFEST.json'}


def verify_lane(lane, producer_repo):
    """Verify actual file set, sealed frozen recipes and original producer bytes."""
    manifest = json.loads(safe_file(lane, 'FILE_MANIFEST.json').read_text())
    if file_manifest(lane) != manifest:
        raise ValueError('original execution artifact file set/hash/size drift')
    for name in manifest:safe_file(lane,name)
    records = json.loads(safe_file(lane, 'EXECUTION.json').read_text())
    keys=[(r['backend'],r['label']) for r in records]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate execution slot')
    for record in records:
        expected_label=record['condition'].replace(':','_')+'--'+record['tier']+'--'+record['variant']
        if record['label']!=expected_label:raise ValueError('execution label binding drift')
        if record['status']=='not_run':continue
        work=lane/'runs'/record['label']
        if work.is_symlink() or not work.resolve().is_relative_to(lane.resolve()):raise ValueError('execution work escapes sealed lane')
        if record['status']=='waveform_available':safe_file(work,record['waveform'])
    started_path=lane/'STARTED.json'
    if started_path.is_file():
        started=json.loads(safe_file(lane,'STARTED.json').read_text())
        denominator=started.get('full_selection',started.get('selected',started.get('plan')))
        if isinstance(denominator,list):
            planned=[(r['backend'],r['label']) for r in denominator]
            if len(planned)!=len(set(planned)) or set(keys)!=set(planned):raise ValueError('started execution denominator drift')
    frozen_path = lane / 'FROZEN_MANIFEST.json'
    if frozen_path.exists():
        frozen = json.loads(frozen_path.read_text())
        started = json.loads((lane / 'STARTED.json').read_text())
        if sha(frozen_path) != started['input_manifest_sha256']:
            raise ValueError('frozen input manifest binding drift')
        frozen_plan = json.loads((lane / 'FROZEN_PLAN.json').read_text())
        full=started['full_selection'];selected=started['selected']
        full_keys=[(r['backend'],r['label']) for r in full]
        if len(full_keys)!=len(set(full_keys)) or set(keys)!=set(full_keys):raise ValueError('execution denominator drift')
        if any(r not in frozen_plan for r in full) or any(r not in full for r in selected):raise ValueError('started selection/frozen plan drift')
        selected_keys=[(r['backend'],r['label']) for r in selected]
        if len(selected_keys)!=len(set(selected_keys)):raise ValueError('duplicate selected slot')
        if any(r['status']!='not_run' and (r['backend'],r['label']) not in selected_keys for r in records):raise ValueError('execution outside selection')
        for name in ('PLAN.json', 'SOURCE_IDENTITY.json', 'CONTRACT.json'):
            if sha(lane / ('FROZEN_' + name)) != frozen.get(name):
                raise ValueError('frozen metadata drift: ' + name)
        for record in records:
            row = next((r for r in frozen_plan if r['backend'] == record['backend'] and r['label'] == record['label']), None)
            if row is None or any(record.get(k) != v for k, v in row.items()):
                raise ValueError('execution/frozen plan drift')
            if record['status'] == 'not_run':
                continue
            work = lane / 'runs' / record['label']
            prefix = row['work'] + '/'
            for name, digest in frozen.items():
                if name.startswith(prefix) and sha(safe_file(work, name[len(prefix):])) != digest:
                    raise ValueError('executed frozen recipe drift: ' + name)
    for record in records:
        if record['status'] == 'not_run':
            continue
        work = lane / 'runs' / record['label']
        for filename,field in (('dut.va','executed_source_sha256'),('original.va','original_source_sha256'),(record['deck'],'deck_sha256')):
            if filename=='original.va' and not (work/filename).exists() and not frozen_path.exists():
                card=json.loads(safe_file(work,'condition.json').read_text())
                digest=hashlib.sha256(card['source'].encode()).hexdigest()
            else:digest=sha(safe_file(work,filename))
            if digest!=record.get(field):raise ValueError('executed source/deck binding drift: '+filename)
        binding_path = safe_file(work, 'SOURCE_BINDING.json')
        if sha(binding_path) != record.get('source_binding_sha256'):
            raise ValueError('original producer binding drift')
        binding = json.loads(binding_path.read_text())
        for name, digest in binding['source_identity'].items():
            if sha(safe_file(producer_repo, name)) != digest:
                raise ValueError('original producer source drift: ' + name)
    return dict(execution_sha256=sha(lane / 'EXECUTION.json'), manifest_sha256=sha(lane / 'FILE_MANIFEST.json'),
                recipe_binding='sealed frozen inputs' if frozen_path.exists() else 'limited legacy replay; no preserved frozen precheck receipt')


def save_exclusive(output, value, lanes):
    output = output.resolve()
    if any(output.is_relative_to(lane.resolve()) for lane in lanes):
        raise ValueError('analysis output must be outside original execution lanes')
    with output.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
