"""Create a new binding receipt from immutable v2 runs and a separate supplement."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'evas/validation/paper'))
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from precision_v2 import assess, load_contract
from precision_v2_report import report as v2_report, load, verify_case_inputs
from precision_binding_evidence import callback_trace, axes, complete_boundary_search, qualify_ngspice_step
from precision_binding_run import recipe
from precision_run import source_files
from inputs import BACKENDS, sha, save
from observations import read_native


def normalized_tool(tool):
    value = {k: tool[k] for k in ('version', 'binary_sha256', 'compiler_sha256', 'kernel_sha256') if k in tool}
    if 'images' in tool:
        value['images'] = {k: v['config_id'] for k, v in tool['images'].items()}
    if 'interpreter' in tool:
        value['interpreter_version'] = tool['interpreter']['version']
    if 'reported' in tool:
        value['reported'] = tool['reported']
    return value


def dependency_hashes():
    paths = source_files() + list((ROOT / 'experiments/backends/support').glob('precision*.py'))
    paths += [ROOT / 'evas/validation/paper/precision-v2.json']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))
            if not p.name.startswith('test_')}


def requirements(card, tier, contract):
    q = next(x for x in contract['tiers'] if x['id'] == tier)
    budget = (contract['budgets']['absolute_V'] + contract['budgets']['relative'] * card['scale_V']) * q['factor']
    return {'tier': tier, 'voltage_budget_V': budget, 'hold_drift_budget_V': budget,
            'reference_uncertainty_max_V': .01 * budget, 'observation_uncertainty_max_V': .1 * budget,
            'input_budget_rule': '0.01 times tier voltage budget at each input scale',
            'expected_events': card.get('expected_events'),
            'event_early_s': card.get('event_early_s'), 'event_late_s': card.get('event_late_s'),
            'cross_expression_tolerance_V': card.get('cross_expression_tolerance_V'),
            'observation': contract['observation']['id'],
            'checker': 'precision-engineering-v2 unchanged; full callback interval inside legal window',
            'boundary_and_behavior': 'all named boundaries, initial state, event count/order, holding stages; no exclusions'}


def build(old, supplement, analysis_dir, step_evidence):
    dependencies = dependency_hashes()
    analysis_dir.mkdir(parents=True, exist_ok=False)
    # Reanalysis verifies full archive, input and execution hashes in both lanes.
    batches = [('v2-original', old, v2_report(old, step_evidence)),
               ('binding-supplement', supplement, v2_report(supplement, step_evidence))]
    contract = load_contract()
    results = []; configs = {}
    for origin, base, report in batches:
        for row in report['results']:
            r = copy.deepcopy(row); r['origin'] = origin
            r['id'] = '/'.join((origin, r['condition'], r['backend'], r['profile']))
            lane = r['family'] + '-' + r['backend']
            out = base / 'collected' / lane / 'outputs' / lane
            work = out / 'runs' / r['label']
            if r['execution_status'] != 'waveform_available':
                r['axes'] = {q['id']: {'numerical': 'unavailable', 'behavior': 'unknown',
                             'evidence': 'unavailable', 'status': r['execution_status']} for q in contract['tiers']}
                results.append(r); continue
            card = load(work / 'condition.json'); tool = load(out / 'TOOL_IDENTITY.json')
            canonical_card = next(c for c in contract['cards'] if c['id'] == r['condition'])
            if card != canonical_card: raise ValueError('case differs from calibrated mathematical fixture')
            is_trace = origin == 'binding-supplement' and r['backend'] == 'spectre' and r['family'] == 'sample_hold'
            generated = recipe(card, load(work / 'requested_settings.json'), r['backend'], callback_trace=is_trace)
            for name, value in generated.items():
                actual = (work / name).read_text() if isinstance(value, str) else load(work / name)
                if value != actual: raise ValueError('executed recipe differs from registered generator: ' + name)
            if origin == 'binding-supplement' and r['backend'] == 'spectre' and r['family'] == 'sample_hold':
                if (tool.get('binary_sha256') != '72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f' or
                        tool.get('version') != 'sub-version  21.1.0.509.isr12'):
                    raise ValueError('callback adapter has not been reviewed for this Spectre version')
                rows = read_native(work / load(work / 'RESULT.json')['waveform'], 'spectre')
                e = callback_trace(card, (work / 'dut.va').read_text(), (work / 'spectre.log').read_text(), rows)
                evidence_dir = analysis_dir / r['label']; evidence_dir.mkdir()
                shutil.copy2(work / 'spectre.log', evidence_dir / 'spectre.log')
                e.update(artifact='spectre.log', artifact_sha256=sha(evidence_dir / 'spectre.log'))
                save(evidence_dir / 'callback.json', e)
                a = assess(card, rows, contract, event_evidence_path=evidence_dir / 'callback.json')
                r['assessment'] = a
                r['callback_evidence'] = {k: e[k] for k in ('method', 'artifact_sha256', 'waveform_rows_sha256', 'events', 'scope', 'representation', 'type_basis', 'standard_url')}
            rows = read_native(work / load(work / 'RESULT.json')['waveform'], r['backend'])
            r['assessment'], boundary_witnesses = complete_boundary_search(card, rows, r['assessment'], contract)
            if boundary_witnesses: r['supplementary_boundary_witnesses'] = boundary_witnesses
            if r['backend'] == 'openvaf_r_ngspice':
                r['qualification'] = qualify_ngspice_step(r['qualification'], load(work / 'requested_settings.json'),
                                                       tool, step_evidence.get('openvaf_r_ngspice', {}))
            r['baseline_tiers'] = r.pop('tiers')
            r['axes'] = axes(r['assessment'], r['qualification'])
            files = ('dut.va', load(work / 'RESULT.json')['deck'], 'condition.json', 'requested_settings.json',
                     'requested_times.json', 'observation_plan.json')
            configs[r['id']] = {'settings': load(work / 'requested_settings.json'),
                               'actual': r['qualification']['actual'],
                               'mapped_controls': r['qualification'].get('mapped_controls', r['qualification'].get('source_mapped_controls')),
                               'tool_identity': normalized_tool(tool),
                               'recipe_hashes': {n: sha(work / n) for n in files},
                               'callback_trace': 'callback_evidence' in r,
                               'evidence': {'origin': origin, 'result': r['id'],
                                            'waveform_sha256': r['waveform_sha256'], 'receipt_sha256': r['receipt_sha256'],
                                            'archive_sha256': report['lanes'][lane]['archive_sha256'],
                                            'raw_availability': 'local-only; exact recipes reproducible, raw archive not public'}}
            results.append(r)
    bindings = {}
    # Fixed order: original base/tol/step/both/deep, then supplementary base
    # and deep_bound. Never drop a failed attempt or silently weaken the tier.
    for card in contract['cards']:
        for backend in BACKENDS:
            candidates = [r for r in results if r['condition'] == card['id'] and r['backend'] == backend]
            for q in contract['tiers']:
                tier = q['id']; selected = next((r for r in candidates if r['axes'][tier]['status'] == 'pass'), None)
                key = '/'.join((card['id'], backend, tier))
                binding = {'status': 'qualified' if selected else 'unavailable',
                           'requirements': requirements(card, tier, contract),
                           'attempts': [{'result': r['id'], **r['axes'][tier]} for r in candidates]}
                if selected: binding['configuration'] = selected['id']
                else:
                    binding['reasons'] = list(dict.fromkeys(reason for r in candidates for reason in
                        r.get('assessment', {}).get('tiers', {}).get(tier, {}).get('reasons', [r['execution_status']]) + r.get('qualification', {}).get('issues', [])))
                bindings[key] = binding
    selected_ids = {b['configuration'] for b in bindings.values() if b['status'] == 'qualified'}
    registry = {'schema_version': 1, 'id': 'precision-bindings-v1',
                'scope': 'eight exact frozen fixtures, tool hashes and observation plan; no generic model guarantee',
                'conditions': [c['id'] for c in contract['cards']], 'backends': list(BACKENDS),
                'configurations': {k: v for k, v in configs.items() if k in selected_ids}, 'bindings': bindings,
                'dependencies': dependencies}
    receipt = {'schema_version': 1, 'id': 'precision-binding-evidence-v1', 'results': results,
               'previous_scores': 'v1/v2 immutable; all supplements and reanalysis separate',
               'lanes': {origin: report['lanes'] for origin, base, report in batches},
               'manifests': {origin: sha(base / 'inputs/MANIFEST.json') for origin, base, report in batches},
               'analysis_dependencies': dependencies}
    if dependency_hashes() != dependencies:
        raise ValueError('analysis code changed during the run; repeat in a new analysis directory')
    return receipt, registry


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('old', type=Path); p.add_argument('supplement', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--step-evidence', type=Path, required=True)
    a = p.parse_args()
    receipt, registry = build(a.old.resolve(), a.supplement.resolve(), a.output.resolve(), load(a.step_evidence))
    save(a.output / 'receipt.json', receipt); save(a.output / 'registry-draft.json', registry)
    for backend in BACKENDS:
        print(backend, {q: sum(b['status'] == 'qualified' for k, b in registry['bindings'].items()
                              if k.split('/')[1:] == [backend, q]) for q in ('Q1', 'Q2', 'Q3')})
