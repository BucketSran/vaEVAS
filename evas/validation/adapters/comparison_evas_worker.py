"""EVAS execution for the condition/requested_settings comparison contract.

This adapter does not implement the paper request/raw-response contract.
"""
import csv
import json
from pathlib import Path
import sys


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def worker(work, kernel, root):
    """Current Python compiler + current transient API, explicitly selected kernel."""
    sys.path.insert(0, str(root / 'evas/src'))
    from evas import CompileError, KernelError, Instance, compile_sources, transient
    from evas.syntax import Parser
    c = load(work / 'condition.json')
    settings = load(work / 'requested_settings.json')
    sources = {card: (root / 'evas/validation/cases' / card / 'dut.va').read_text() for card in c['source_cards']}
    if '\n'.join(sources.values()) != (work / 'dut.va').read_text():
        raise ValueError('current module bytes differ from frozen DUT')
    result = {'status': 'not_run'}
    try:
        ports = {m.name: m.ports for card, text in sources.items() for m in [Parser(text, card).parse()]}
        instances = [Instance(i['name'], i.get('module', c.get('module')),
                     dict(zip(ports[i.get('module', c.get('module'))], i['ports'], strict=True)), i['params'])
                     for i in c['instances']]
        program = compile_sources(sources, instances)
        save(work / 'program.json', program.to_dict())
        count = round(settings['stop'] / settings['step'])
        times = [i * (settings['stop'] / count) for i in range(count + 1)]
        inputs = {n: [[t * 1e-6, v] for t, v in points] for n, points in c['inputs'].items()}
        response = transient(program, inputs, times, stop=settings['stop'], max_step=settings['maxstep'],
                             kernel=kernel, vabstol=settings['vabstol'], reltol=settings['reltol'])
        save(work / 'effective.json', {'vabstol': settings['vabstol'], 'reltol': settings['reltol'],
             'max_step': settings['maxstep'], 'stop': settings['stop'], 'output_points': len(times),
             'engine': response['engine'], 'transient_summary': {
                 'accepted_steps': response['transient'].get('accepted_steps'),
                 'discarded_trials': response['transient'].get('discarded_trials'),
                 'state_names': response['transient'].get('state_names'),
                 'event_count': len(response['transient'].get('events', []))},
             'unsupported_spice_controls': ['iabstol', 'integration method']})
        with (work / 'waveform.csv').open('x') as stream:
            writer = csv.writer(stream)
            writer.writerow(['time', *response['nodes']])
            writer.writerows([t, *s['voltages']] for t, s in zip(times, response['solutions'], strict=True))
        result = {'status': 'waveform_available', 'waveform': 'waveform.csv'}
    except CompileError as exc:
        result = {'status': 'compile_failed', 'failure_stage': 'compile', 'reason': str(exc)}
    except KernelError as exc:
        result = {'status': 'execution_failed', 'failure_stage': 'kernel', 'reason': str(exc), 'detail': exc.detail}
    save(work / 'worker-result.json', result)
