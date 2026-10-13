"""Read-only recipe checks for a frozen precision lane, without simulator access.

This validates requested controls and bindings. It never establishes effective
settings, compiler support, observation provenance or numerical acceptance.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import re
from time import perf_counter


def load(path):
    return json.loads(path.read_text())


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def safe_file(root, name):
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('unsafe frozen input: ' + str(name))
    return path


def pilot_plan(plan):
    """First frozen condition per capability group and actual configuration.

    A distinct target tier is retained even if two targets use one profile.
    The caller preserves all omitted slots; a pilot is not full qualification.
    """
    selected = []
    seen = set()
    for row in plan:
        key = (row['backend'], row['family'], row.get('group_id', row['condition']),
               row.get('tier'), row['profile'])
        if key not in seen:
            selected.append(row)
            seen.add(key)
    return selected


def check_deck(work, row, card, settings, times):
    """Inspect generated physical port order and requested controls independently."""
    backend = row['backend']
    text = (work / row['deck']).read_text()
    if backend == 'evas':
        return
    if backend == 'spectre':
        matches = re.findall(r'^dut\s+\(([^)]*)\)\s+(\S+)', text, re.M)
        if matches != [(' '.join(card['ports']), card['top'])]:
            raise ValueError('Spectre instance binding: ' + row['label'])
        for name, points in card['inputs'].items():
            matches = re.findall(r'^V' + re.escape(name) + r'\s+\(([^)]*)\)\s+vsource type=pwl wave=\[([^]]*)\]', text, re.M)
            if (len(matches) != 1 or matches[0][0] != name + ' 0' or
                    list(map(float, matches[0][1].split())) != [v for point in points for v in point]):
                raise ValueError('Spectre stimulus binding: ' + row['label'])
        controls = re.findall(r'^simulatorOptions options\s+([^\n]+)', text, re.M)
        tran = re.findall(r'^tran tran\s+([^\n]+)', text, re.M)
        if len(controls) != 1 or len(tran) != 1:
            raise ValueError('Spectre control scope: ' + row['label'])
        for field, control, line in [('reltol', 'reltol', controls[0]), ('vabstol_V', 'vabstol', controls[0]),
                                     ('iabstol_A', 'iabstol', controls[0]), ('stop_s', 'stop', tran[0]),
                                     ('maxstep_s', 'maxstep', tran[0])]:
            values = re.findall(r'(?<!\w)' + control + r'=([^\s]+)', line)
            if len(values) != 1 or float(values[0]) != settings[field]:
                raise ValueError('Spectre requested control binding: ' + row['label'])
        strobes = re.findall(r'\bstrobetimes=\[([^]]*)\]', tran[0])
        if len(strobes) != 1 or list(map(float, strobes[0].split())) != times:
            raise ValueError('Spectre observation times binding: ' + row['label'])
    elif backend == 'openvaf_r_ngspice':
        ports = re.findall(r'^N0\s+([^\n]+)', text, re.M)
        models = re.findall(r'^\.model model0\s+(\S+)', text, re.M)
        if ports != [' '.join(card['ports']) + ' model0'] or models != [card['top']]:
            raise ValueError('ngspice instance binding: ' + row['label'])
    elif backend == 'gnucap_modelgen':
        modules = re.findall(r'^\\([^\s#]+)(?:\s+#\([^\n]*\))?\s+dut\(([^)]*)\);', text, re.M)
        if modules != [(card['top'], ','.join(card['ports']))]:
            raise ValueError('Gnucap instance binding: ' + row['label'])
    else:
        raise ValueError('unknown backend: ' + backend)


def inspect_plan(inputs, plan):
    """Check every selected recipe before the first backend invocation."""
    inputs = inputs.resolve()
    data = load(safe_file(inputs, 'cards.json'))
    bindings = load(inputs / 'PROFILE_BINDINGS.json') if (inputs / 'PROFILE_BINDINGS.json').is_file() else None
    profiles = {p['id']: p for p in data['profiles']}
    cards = {c['id']: c for c in data['cards']}
    if len(cards) != len(data['cards']) or len(profiles) != len(data['profiles']):
        raise ValueError('duplicate card or profile identity')
    if not plan or len({(r['backend'], r['label']) for r in plan}) != len(plan):
        raise ValueError('empty or duplicate frozen slots')
    manifest = load(safe_file(inputs, 'MANIFEST.json'))
    for row in plan:
        work = inputs / row['work']
        if work.is_symlink() or not work.resolve().is_relative_to(inputs):
            raise ValueError('unsafe frozen work: ' + row['work'])
        names = ('dut.va', 'condition.json', 'requested_settings.json', 'requested_times.json', row['deck'])
        for name in names:
            path = safe_file(work, name)
            rel = str(path.relative_to(inputs))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != manifest.get(rel):
                raise ValueError('recipe not bound to frozen manifest: ' + rel)
        card = load(work / 'condition.json')
        expected = cards.get(row['condition'])
        # The row's family can name an execution batch (root-window-v3), while
        # the unchanged physical card keeps its own reference family.
        if expected is None or card != expected:
            raise ValueError('condition binding: ' + row['label'])
        if hashlib.sha256((work / 'dut.va').read_bytes()).hexdigest() != row['source_sha256']:
            raise ValueError('source binding: ' + row['label'])
        settings = load(work / 'requested_settings.json')
        profile = profiles.get(row['profile'])
        if profile is None or any(settings.get(k) != v for k, v in profile.items()):
            raise ValueError('profile binding: ' + row['label'])
        if bindings is not None:
            mapped = bindings['backend_tier_profiles'].get(row['backend'], {}).get(row.get('tier'))
            breadth = str(bindings.get('schema_version', '')).startswith('breadth-')
            if (mapped != row['profile'] or
                    ((breadth or 'target_tier' in settings) and settings.get('target_tier') != row.get('tier'))):
                raise ValueError('profile binding: ' + row['label'])
        for name in ('stop_s', 'maxstep_s', 'spice_maxstep_s', 'reltol', 'vabstol_V', 'iabstol_A'):
            if not positive(settings.get(name)):
                raise ValueError('invalid requested control ' + name + ': ' + row['label'])
        if (settings['stop_s'] != card['stop_s'] or not positive(card['unit_s']) or
                settings['maxstep_s'] != card['unit_s'] * profile['step_units'] or
                settings['spice_maxstep_s'] != settings['maxstep_s']):
            raise ValueError('time control binding: ' + row['label'])
        times = load(work / 'requested_times.json')
        if (not isinstance(times, list) or len(times) < 2 or
                any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or
                times[0] != 0 or times[-1] != card['stop_s'] or
                any(a >= b for a, b in zip(times, times[1:]))):
            raise ValueError('invalid observation times: ' + row['label'])
        ports = card['ports']
        if (not ports or len(set(ports)) != len(ports) or
                not set(card['inputs']).issubset(ports) or not set(card['outputs']).issubset(ports)):
            raise ValueError('port binding: ' + row['label'])
        if not (work / row['deck']).read_text().strip():
            raise ValueError('empty backend deck: ' + row['label'])
        check_deck(work, row, card, settings, times)
        if row['backend'] == 'evas':
            request = load(work / row['deck'])
            instance = {'name': 'dut', 'module': card['top'],
                        'ports': {p: p for p in ports}, 'parameters': card['parameters']}
            if request.get('instances') != [instance] or request.get('inputs') != card['inputs']:
                raise ValueError('EVAS instance binding: ' + row['label'])
            wanted = {'source': 'dut.va', 'requested_times': 'requested_times.json',
                      'stop': settings['stop_s'], 'max_step': settings['maxstep_s'],
                      'reltol': settings['reltol'], 'vabstol': settings['vabstol_V']}
            if any(request.get(k) != v for k, v in wanted.items()):
                raise ValueError('EVAS request binding: ' + row['label'])
    return {'status': 'ready', 'slots': len(plan),
            'backends': sorted({r['backend'] for r in plan}),
            'claim': 'requested recipe consistency only; actual tools, controls and scientific acceptance remain unverified'}


@contextmanager
def measure(timings, phase):
    """Retain elapsed time even when a stage raises."""
    started = perf_counter()
    try:
        yield
    finally:
        timings[phase] = timings.get(phase, 0) + perf_counter() - started
