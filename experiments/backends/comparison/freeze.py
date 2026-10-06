"""Freeze exactly eight existing development conditions and 32 base configurations."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from records import ROOT, BACKENDS, identity, sha

SELECTED = ('v1-main', 'v2-main', 'v3-main', 'v4-c0', 'v5-main', 'v6-standard', 'v7-linear-main', 'c1-main')
sys.path[:0] = [str(ROOT / 'experiments/backends/dvs2-spectre-validation'),
               str(ROOT / 'experiments/backends/dvs2-four-backend-validation')]
from run_suite import conditions, PROFILES, T, netlist
from build_inputs import netlists


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def runtime_identity():
    paths = sorted(p for base in ('evas/src', 'evas/rust_core') for p in (ROOT / base).rglob('*')
                   if p.is_file() and (p.suffix in ('.py', '.rs', '.toml') or p.name == 'Cargo.lock')
                   and 'target' not in p.parts and '__pycache__' not in p.parts)
    return identity({str(p.relative_to(ROOT)): sha(p) for p in paths})


def checker_identity():
    return identity({str(p.relative_to(ROOT)): sha(p) for directory in
        ('experiments/backends/dvs2-spectre-validation', 'experiments/archive/dvs2-history-validation',
         'experiments/archive/dvs2-starter-pilot') for p in sorted((ROOT / directory).glob('*.py'))})


def selected_cases():
    lookup = {c['id']: c for c in conditions()}
    return [lookup[c] for c in SELECTED]


def case_inputs(c):
    source = '\n'.join((ROOT / 'evas/validation/cases' / card / 'dut.va').read_text() for card in c['source_cards'])
    settings = {**PROFILES['base'], 'stop': c['stop_x'] * T, 'maxstep': PROFILES['base']['step'],
                'method': 'traponly', 'forced_strobe': False}
    return source, settings


def input_identity(c):
    source, settings = case_inputs(c)
    return identity({'condition': c, 'source': source, 'requested_settings': settings})


def freeze(output):
    cases = selected_cases()
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'conditions.json', cases)
    plan = []
    for c in cases:
        source, settings = case_inputs(c)
        for backend in BACKENDS:
            work = output / 'runs' / backend / c['id'] / 'base'
            work.mkdir(parents=True)
            (work / 'dut.va').write_text(source)
            save(work / 'condition.json', c)
            save(work / 'requested_settings.json', settings)
            (work / 'tb.scs').write_text(netlist(c, 'base'))
            for filename, body in netlists(c, settings).items():
                (work / filename).write_text(body)
            plan.append({'backend': backend, 'condition': c['id'], 'profile': 'base',
                         'source_sha256': sha(work / 'dut.va'), 'input_identity': input_identity(c),
                         'work': str(work.relative_to(output))})
    save(output / 'RUN_PLAN.json', plan)
    save(output / 'provenance.json', {'dataset': 'cmp8-base', 'configurations': 32,
         'simulations_per_backend': 8, 'stage_timeout_s': 90, 'license_timeout_s': 30,
         'evas_runtime_identity': runtime_identity(),
         'checker_identity': checker_identity()})
    save(output / 'INPUT_MANIFEST.json', {str(p.relative_to(output)): {'sha256': sha(p), 'bytes': p.stat().st_size}
                                         for p in sorted(output.rglob('*')) if p.is_file()})
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(f'Frozen {len(freeze(args.output))} configurations; no simulation launched')
