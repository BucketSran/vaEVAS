"""Add separately frozen calibration inputs; never edit a previous scan."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'evas/validation/paper'))
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from precision_v2 import load_contract, observation_plan
from precision_v2_run import run
from precision_run import source_files
from inputs import decks, save, sha

DEEP_BOUND = {'id': 'deep_bound', 'reltol': 1e-10, 'vabstol_V': 1e-14,
              'iabstol_A': 1e-17, 'step_units': 0.0004}
TRACE = '$strobe("EVAS_CALLBACK %d %.17g",n,$abstime);'


def recipe(card, profile, backend, *, callback_trace=False):
    """Same mathematics/observations as v2; instrumentation has its own identity."""
    contract = load_contract()
    observation = observation_plan(card, contract)
    times = observation['times_s']
    settings = {**profile, 'stop_s': card['stop_s'],
                'maxstep_s': card['unit_s'] * profile['step_units'],
                'spice_maxstep_s': card['unit_s'] * profile['step_units']}
    physical = {**card, 'stimulus': {n: {'points_s_V': v} for n, v in card['inputs'].items()}}
    bind = {'top_module': card['top'], 'ports': card['ports'], 'parameters': card['parameters']}
    filename, text = decks(physical, settings, bind, times,
                           {'records': [{'time_s': t} for t in times]})[backend]
    if backend == 'spectre':
        text = '\n'.join(line + ' precision="%.17g"' if line.startswith('simulatorOptions ') else
                         line + ' skipcount=1 compression=no annotate=steps annotatedigits=16'
                         if line.startswith('tran tran ') else line for line in text.splitlines()) + '\n'
    elif backend == 'openvaf_r_ngspice':
        text = text.replace(' method=trap\n', ' method=trap trtol=7 chgtol=1e-14 itl4=10\n')
    elif backend == 'gnucap_modelgen':
        text = text.replace('.options numdgt=17 dtmin=1e-15',
                            '.options numdgt=17 method=trap dtmin=1e-16 trtol=7 dtratio=1e9')
    source = card['source']
    if callback_trace:
        if backend != 'spectre' or card['family'] != 'sample_hold' or source.count('n=n+1; end') != 1:
            raise ValueError('unreviewed callback instrumentation shape')
        source = source.replace('n=n+1; end', 'n=n+1; ' + TRACE + ' end')
    return {filename: text, 'dut.va': source, 'condition.json': card,
            'requested_settings.json': settings, 'requested_times.json': times,
            'observation_plan.json': observation}


def write_recipe(work, files):
    work.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        if isinstance(value, str): (work / name).write_text(value)
        else: save(work / name, value)


def freeze(output):
    data = load_contract()
    data['profiles'] += [DEEP_BOUND]
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'cards.json', data)
    plan = []
    for card in data['cards']:
        choices = [('spectre', data['profiles'][0], True)] if card['family'] == 'sample_hold' else [
            (b, DEEP_BOUND, False) for b in ('spectre', 'openvaf_r_ngspice', 'gnucap_modelgen')]
        for backend, profile, trace in choices:
            label = card['id'] + '--' + profile['id']
            work = output / 'runs' / backend / label
            files = recipe(card, profile, backend, callback_trace=trace)
            write_recipe(work, files)
            deck = next(n for n in files if n in ('tb.scs', 'tb.cir', 'tb.gc', 'request.json'))
            plan.append({'condition': card['id'], 'profile': profile['id'], 'family': card['family'],
                         'backend': backend, 'label': label, 'work': str(work.relative_to(output)),
                         'deck': deck, 'source_sha256': sha(work / 'dut.va'), 'callback_trace': trace})
    save(output / 'PLAN.json', plan)
    paths = source_files() + [Path(__file__), ROOT / 'evas/validation/paper/precision-v2.json',
                             ROOT / 'experiments/backends/support/precision_v2_run.py',
                             ROOT / 'experiments/backends/support/precision_v2_report.py']
    save(output / 'SOURCE_IDENTITY.json', {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))})
    save(output / 'MANIFEST.json', {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    print('Frozen', len(plan), 'supplementary attempts; original 160 attempts unchanged')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('freeze'); s.add_argument('output', type=Path)
    s = sub.add_parser('run'); s.add_argument('inputs', type=Path); s.add_argument('output', type=Path)
    s.add_argument('--backend', required=True); s.add_argument('--profile', type=Path, required=True)
    s.add_argument('--family', required=True)
    a = p.parse_args()
    if a.mode == 'freeze': freeze(a.output.resolve())
    else: run(a.inputs.resolve(), a.output.resolve(), a.backend, a.profile.resolve(), a.family)
