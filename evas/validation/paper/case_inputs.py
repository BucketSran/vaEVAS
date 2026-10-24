"""Read paper case sources and construct inputs without a simulator or backend.

The cards own models and scientific conditions. Callers retain their own query
grids, acceptance checks and independent answers. Every read returns fresh data.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import re


CORE = Path(__file__).with_name('core-v1.json')


def load_core():
    return json.loads(CORE.read_text())


def case_source(case_id):
    for card in load_core()['cards']:
        if card['id'] == case_id:
            return card['source']
    raise KeyError(case_id)


def binding(card):
    """Select the last declared module, preserving the card's actual hierarchy."""
    modules = re.findall(r'\bmodule\s+(\w+)\s*\(([^)]*)\)\s*;', card['source'])
    if not modules:
        raise ValueError('no explicit module ports')
    module, ports = modules[-1]
    ports = [p.strip() for p in ports.split(',')]
    if set(ports) != set(card['observables']):
        raise ValueError('top module ports differ from observables')
    return {'top_module': module, 'instance': 'dut', 'ports': ports,
            'parameters': deepcopy(card['parameters']), 'hierarchy': 'preserve exact VA source',
            'source_legality': 'pending actual source and backend qualification'}


def stimulus(card, T):
    """Convert card stimulus units to seconds, preserving arithmetic order."""
    stop = card['stop_T'] * T
    sources = {}
    for port, source in card['stimulus'].items():
        if source['kind'] == 'dc':
            sources[port] = [[0, source['value_V']], [stop, source['value_V']]]
        elif source['kind'] == 'pwl':
            sources[port] = [[t * T, v] for t, v in source['points_T_V']]
        else:
            raise ValueError('unknown stimulus kind: ' + source['kind'])
    return sources


def requested_times(card, contract, T):
    """Requested output times, never a certificate of accepted-step accuracy."""
    stop = card['stop_T'] * T
    count = math.ceil(stop / contract['sample_gap_s'])
    times = {i * stop / count for i in range(count + 1)}
    for window in card['observation_windows']:
        start, end = window['start_T'] * T, window['end_T'] * T
        count = math.ceil((end-start) / window['max_gap_s'])
        times.update(start + i*(end-start)/count for i in range(count+1))
        times.add(window['center_T'] * T)
    times.update(a['t_T'] * T for a in card['anchors'])
    return sorted(times)
