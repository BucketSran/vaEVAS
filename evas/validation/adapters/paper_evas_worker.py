"""Current paper EVAS worker: compile, transient response, and raw record.

The caller supplies a prepared work directory and an explicit kernel path.
Plan selection, launch budgets, and non-EVAS backends stay in the experiment runner.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RELATIVE_PATH = 'evas/validation/adapters/paper_evas_worker.py'


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def save_raw_response(path, response):
    """Only the potentially large response uses compact JSON; preserve all values."""
    with path.open('x') as stream:
        json.dump(response, stream, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def evas_effective_record(request, response):
    """The transient public API has already validated the actual response."""
    evidence = response.get('observation_evidence')
    record = {'request_echo': {'reltol': request['reltol'], 'vabstol': request['vabstol'],
                              'stop': request['stop'], 'maxstep': request['max_step']},
              'observed_response': {'engine': response['engine'], 'accepted_steps': response['transient'].get('accepted_steps')},
              'unsupported_controls': ['iabstol', 'integration_method']}
    if evidence is None:
        record.update(sample_origin='unknown; legacy response has no observation evidence',
                      settings_readback='unknown; legacy response does not report actual controls')
    else:
        record['runtime_controls'] = dict(evidence['effective_controls'])
        origins = evidence['sample_origins']
        record['sample_origin_summary'] = {origin: origins.count(origin) for origin in sorted(set(origins))}
        record['sample_origin'] = 'actual response origins; these do not independently establish paper native qualification'
        record['settings_readback'] = 'validated public response observation_evidence.effective_controls'
    return record


def worker(work, kernel):
    """Normal compiler/top hierarchy, current transient API, no source rewriting."""
    sys.path.insert(0, str(ROOT / 'evas/src'))
    from evas import CompileError, KernelError, Instance, compile_sources, transient
    request = load(work / 'request.json')
    result = {'status': 'execution_failed', 'reason': 'worker did not complete'}
    try:
        instances = [Instance(i['name'], i['module'], i['ports'], i['parameters']) for i in request['instances']]
        program = compile_sources({'dut.va': (work / 'dut.va').read_text()}, instances)
        save(work / 'program.json', program.to_dict())
        times = load(work / request['requested_times'])
        response = transient(program, request['inputs'], times, stop=request['stop'], max_step=request['max_step'],
                             kernel=kernel, vabstol=request['vabstol'], reltol=request['reltol'], timeout=None)
        save_raw_response(work / 'raw-response.json', response)
        # Owned outer stage kills the complete worker/kernel group at its limit.
        with (work / 'waveform.csv').open('x') as handle:
            writer = csv.writer(handle)
            writer.writerow(['time', *response['nodes']])
            writer.writerows([t, *row['voltages']] for t, row in zip(times, response['solutions'], strict=True))
        save(work / 'effective.json', evas_effective_record(request, response))
        result = {'status': 'waveform_available', 'waveform': 'waveform.csv'}
    except CompileError as exc:
        result = {'status': 'compile_failed', 'failure_stage': 'compile', 'reason': str(exc)}
    except KernelError as exc:
        result = {'status': 'execution_failed', 'failure_stage': 'kernel', 'reason': str(exc), 'detail': exc.detail}
    except Exception as exc:
        result = {'status': 'execution_failed', 'failure_stage': 'worker', 'exception_type': type(exc).__name__, 'reason': str(exc)}
    save(work / 'worker-result.json', result)
