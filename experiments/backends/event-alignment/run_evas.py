"""Preserve one public-compiler/kernel execution per frozen engineering case."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as file:
        json.dump(value, file, indent=2, allow_nan=False)
        file.write('\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('assets', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--kernel', type=Path)
    p.add_argument('--case', action='append')
    a = p.parse_args()
    a.source, a.assets, a.output = (v.resolve() for v in (a.source, a.assets, a.output))
    kernel = (a.kernel or a.source/'evas/rust_core/target/debug/evas-kernel').resolve()
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.source/'evas/src'))
    from evas import compile_sources, Instance
    from evas.protocol import validate_response
    spec = importlib.util.spec_from_file_location('frozen_checker', a.assets/'checker.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    save(a.output/'IDENTITY.json', dict(
        source=str(a.source),
        revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=a.source, text=True).strip(),
        tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git','diff','HEAD','--','evas/src','evas/rust_core'],cwd=a.source)).hexdigest(),
        kernel=str(kernel), kernel_sha256=sha(kernel), runner_sha256=sha(Path(__file__)),
        checker_sha256=sha(a.assets/'checker.py'),
        limits='Finite engineering run, debug kernel. Timings are diagnostic and are not performance evidence.'))
    reports = []
    for name in a.case or ['T1','T2','C1','C2','M1','H1','N1']:
        c = json.loads((a.assets/name/'case.json').read_text())
        source = (a.assets/name/'dut.va').read_text()
        work = a.output/name
        work.mkdir()
        record = dict(case=name, source_sha256=sha(a.assets/name/'dut.va'), case_sha256=sha(a.assets/name/'case.json'))
        try:
            program = compile_sources({'dut.va':source}, [Instance('dut', c['module'], {n: '0' if n==c['ground_port'] else n for n in c['ports']})])
            settings = c['settings']['evas']
            request = dict(program=program.to_dict(), driven=list(c['inputs']), samples=[],
                transient=dict(pwl=list(c['inputs'].values()), output_times=c['times'],stop=c['stop'],max_step=settings['max_step']),
                tolerances=dict(absolute=settings['vabstol'],relative=settings['reltol']))
            save(work/'request.json', request)
            start = time.perf_counter()
            result = subprocess.run([str(kernel)], input=json.dumps(request,allow_nan=False).encode(), capture_output=True, timeout=90)
            record.update(returncode=result.returncode, diagnostic_wall_s=time.perf_counter()-start)
            (work/'stdout.json').write_bytes(result.stdout)
            (work/'stderr.json').write_bytes(result.stderr)
            if result.returncode:
                record.update(status='F', stage='kernel', detail=json.loads(result.stderr))
            else:
                response = json.loads(result.stdout)
                validate_response(response, program, len(c['times']), c['times'])
                normalized = dict(rows=[dict(time=t,voltages=dict(zip(response['nodes'],s['voltages']))) for t,s in zip(response['transient']['times'],response['solutions'])])
                save(work/'normalized.json', normalized)
                report = checker.inspect(c, normalized['rows'])
                save(work/'check.json', report)
                record.update(status=report['status'], stage='checker', failures=report['failures'], actual_event_records=len(response['transient']['events']))
        except Exception as error:
            record.update(status='F', stage='exception', detail=dict(type=type(error).__name__,message=str(error)))
        save(work/'RESULT.json', record)
        reports.append(record)
        print(json.dumps(record), flush=True)
    save(a.output/'SUMMARY.json', reports)
    save(a.output/'MANIFEST.json', {str(p.relative_to(a.output)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(a.output.rglob('*')) if p.is_file()})


if __name__ == '__main__':
    main()
