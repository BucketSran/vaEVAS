"""Fresh 31-condition rerun. Existing DUTs, profiles and checker stay unchanged."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'evas/src'), str(ROOT/'experiments/backends/dvs2-spectre-validation'),
               str(ROOT/'experiments/backends/dvs2-four-backend-validation')]
from run_suite import conditions, PROFILES, T
from build_inputs import netlists, ENV_SHA
from check_results import check, read_waveform
from remote import execute


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    with p.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write('\n')


def manifest(root):
    return {str(p.relative_to(root)): dict(sha256=sha(p), bytes=p.stat().st_size)
            for p in sorted(root.rglob('*')) if p.is_file()}


def verify(root, name='INPUT_MANIFEST.json'):
    for rel, identity in json.loads((root/name).read_text()).items():
        p = root/rel
        if not p.resolve().is_relative_to(root.resolve()) or sha(p) != identity['sha256']:
            raise ValueError('artifact drift: '+rel)


def build(source, root):
    verify(source)
    root.mkdir(parents=True, exist_ok=False)
    cases = json.loads((source/'conditions.json').read_text())
    save(root/'conditions.json', cases)
    save(root/'expected_images.json', json.loads((ROOT/'experiments/archive/dvs2-starter-pilot/results/TOOL_IDENTITIES.json').read_text())['images'])
    save(root/'provenance.json', dict(environment_sha256=ENV_SHA, max_configurations=124,
         max_simulation_launches=124, max_compiler_launches=93, stage_timeout_s=90,
         source_input_manifest_sha256=sha(source/'INPUT_MANIFEST.json')))
    plan = []
    for backend in ['openvaf_ngspice', 'gnucap']:
        for c in cases:
            for profile in PROFILES:
                old = source/'runs'/c['id']/profile
                work = root/'runs'/backend/c['id']/profile
                work.mkdir(parents=True)
                for name in ['dut.va', 'condition.json', 'requested_settings.json', 'tb.scs']:
                    shutil.copyfile(old/name, work/name)
                settings = json.loads((work/'requested_settings.json').read_text())
                for name, body in netlists(c, settings).items(): (work/name).write_text(body)
                plan.append(dict(backend=backend, condition=c['id'], profile=profile, source_sha256=sha(work/'dut.va')))
    save(root/'RUN_PLAN.json', plan)
    # Retain the existing bounded container runner; change only this run's plan
    # size/budget and omit the unrelated legacy EVAS version probe.
    runner = (ROOT/'experiments/backends/dvs2-four-backend-validation/remote.py').read_text()
    runner = runner.replace('130', '124').replace('35', '93')
    runner = runner.replace("checks=[('evas','/usr/local/bin/evas',['--version']),\n            ", 'checks=[')
    (root/'remote.py').write_text(runner)
    save(root/'ADAPTER_IDENTITY.json', {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),
         ROOT/'experiments/backends/dvs2-four-backend-validation/remote.py',
         ROOT/'experiments/backends/dvs2-four-backend-validation/build_inputs.py']})
    save(root/'INPUT_MANIFEST.json', manifest(root))


def worker(work, kernel):
    from evas import CompileError, KernelError, Instance, compile_sources, transient
    from evas.syntax import Parser
    c = json.loads((work/'condition.json').read_text())
    settings = json.loads((work/'requested_settings.json').read_text())
    result = dict(condition=c['id'], backend='evas', source_sha256=sha(work/'dut.va'))
    try:
        source = (work/'dut.va').read_text()
        # Parse individual common modules to preserve original port order.
        sources = {card: (ROOT/'evas/validation/cases'/card/'dut.va').read_text() for card in c['source_cards']}
        if '\n'.join(sources.values()) != source:
            raise ValueError('module source differs from frozen common DUT')
        ports = {m.name: m.ports for card, text in sources.items() for m in [Parser(text, card).parse()]}
        instances = [Instance(i['name'], i.get('module', c.get('module')),
                     dict(zip(ports[i.get('module', c.get('module'))], i['ports'], strict=True)), i['params'])
                     for i in c['instances']]
        program = compile_sources(sources, instances)
        save(work/'program.json', program.to_dict())
        count = round(settings['stop']/settings['step'])
        times = [i*(settings['stop']/count) for i in range(count+1)]
        inputs = {n: [[t*T, v] for t, v in points] for n, points in c['inputs'].items()}
        # All conditions use the transient API, including event-bearing models.
        response = transient(program, inputs, times, stop=settings['stop'], max_step=settings['maxstep'],
                             kernel=kernel, vabstol=settings['vabstol'], reltol=settings['reltol'])
        save(work/'effective.json', dict(vabstol=settings['vabstol'], reltol=settings['reltol'],
             max_step=settings['maxstep'], output_points=len(times), stop=settings['stop'],
             engine=response['engine'], transient=response['transient'],
             unsupported_spice_controls=['iabstol', 'integration method']))
        with (work/'waveform.csv').open('x') as f:
            writer = csv.writer(f)
            writer.writerow(['time', *response['nodes']])
            writer.writerows([t, *s['voltages']] for t, s in zip(times, response['solutions'], strict=True))
        result.update(status='waveform_available', waveform='waveform.csv', waveform_sha256=sha(work/'waveform.csv'))
    except CompileError as e:
        result.update(status='compile_rejected', reason=str(e))
    except KernelError as e:
        result.update(status='kernel_rejected', reason=str(e), detail=e.detail)
    save(work/'result.json', result)


def evas(source, root, kernel):
    verify(source)
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source/'conditions.json', root/'conditions.json')
    save(root/'STARTED.json', dict(kernel_sha256=sha(kernel), source_input_manifest_sha256=sha(source/'INPUT_MANIFEST.json'),
         python=sys.version, max_attempts=62, timeout_s=90,
         source_sha256={str(p.relative_to(ROOT)): sha(p) for pattern in ['evas/src/**/*.py', 'evas/rust_core/src/**/*.rs'] for p in ROOT.glob(pattern)}))
    records = []
    for c in json.loads((source/'conditions.json').read_text()):
        for profile in PROFILES:
            work = root/'runs'/c['id']/profile
            work.mkdir(parents=True)
            for name in ['dut.va', 'condition.json', 'requested_settings.json']:
                shutil.copyfile(source/'runs'/c['id']/profile/name, work/name)
            execution = execute([sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--root', str(work.resolve()),
                                 '--kernel', str(kernel.resolve())], work, 'worker.log', 90)
            save(work/'execution.json', execution)
            if not (work/'result.json').exists():
                save(work/'result.json', dict(status='runtime_timeout' if execution['timeout'] else 'adapter_failure',
                     condition=c['id'], backend='evas', reason=(work/'worker.log').read_text()[-2000:]))
            result = json.loads((work/'result.json').read_text())
            result['profile'] = profile
            records.append(result)
            print(c['id'], profile, result['status'], flush=True)
    save(root/'EXECUTION.json', records)
    save(root/'FILE_MANIFEST.json', manifest(root))


def analyze(parent, output):
    roots = {b: parent/name for b, name in [('spectre','matrix-spectre'),('evas','matrix-evas'),
              ('openvaf_ngspice','matrix-open'),('gnucap','matrix-open')]}
    for root in set(roots.values()): verify(root, 'FILE_MANIFEST.json')
    records = []
    for c in json.loads((roots['spectre']/'conditions.json').read_text()):
        for b, root in roots.items():
            for profile in PROFILES:
                work = root/'runs'
                if b in ['gnucap','openvaf_ngspice']: work /= b
                work = work/c['id']/profile
                r = json.loads((work/'result.json').read_text())
                if sha(work/'dut.va') != sha(roots['spectre']/'runs'/c['id']/profile/'dut.va'):
                    raise ValueError('common DUT mismatch')
                a = dict(status=r['status'], reason=r.get('reason'), formal_dvs_qualification='I')
                if r['status'] == 'waveform_available':
                    if b == 'evas':
                        with (work/r['waveform']).open() as f: rows = [{k: float(v) for k,v in row.items()} for row in csv.DictReader(f)]
                    else: rows = read_waveform(work/r['waveform'], b)
                    if b == 'gnucap' and any(abs(row.get('bench_ref', float('inf')))>1e-7 for row in rows):
                        a = dict(status='observation_invalid', reason='ground alias invalid')
                    else: a = check(rows, c)
                records.append(dict(backend=b, condition=c['id'], profile=profile, execution_status=r['status'], analysis=a))
                print(b, c['id'], profile, a['status'], flush=True)
    save(output, dict(records=records, configurations=len(records), evidence_use='all new executions/compilation attempts',
         summary={b:{p:dict(Counter(r['analysis']['status'] for r in records if r['backend']==b and r['profile']==p))
                     for p in PROFILES} for b in roots}, formal_dvs_qualification='I'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['build','evas','worker','analyze'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--source', type=Path)
    p.add_argument('--kernel', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.action == 'build': build(a.source, a.root)
    elif a.action == 'evas': evas(a.source, a.root, a.kernel)
    elif a.action == 'worker': worker(a.root, a.kernel)
    else: analyze(a.root, a.output)
