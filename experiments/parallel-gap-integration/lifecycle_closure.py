"""Replay frozen lifecycle requests; distinguish new EVAS from reused Spectre.

The previous raw manifest binds the exact IR requests and checker snapshot.
No compilation, stimulus change or new remote execution occurs in this replay.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

from lifecycle_contract import digest, dump


def verify_manifest(root, name):
    for rel, identity in json.loads((root/name).read_text()).items():
        path=(root/rel).resolve()
        expected=identity['sha256'] if isinstance(identity,dict) else identity
        if not path.is_relative_to(root.resolve()) or digest(path)!=expected:
            raise ValueError('artifact drift: '+rel)


def replay(prior, root, kernel):
    verify_manifest(prior,'RAW_MANIFEST.json')
    root.mkdir(parents=True,exist_ok=False)
    # The prior final verdict used a separately frozen corrected analyzer;
    # the original execution snapshot predates that log-display correction.
    frozen=prior/'analysis-source/experiments/parallel-gap-integration/lifecycle_contract.py'
    if digest(frozen)!=json.loads((prior/'analysis-final.json').read_text())['analysis_source_sha256']:
        raise ValueError('previous final checker identity differs')
    spec=importlib.util.spec_from_file_location('frozen_lifecycle_checker',frozen)
    checker=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    verify_manifest(prior,'INPUT_MANIFEST.json')
    verify_manifest(prior/'spectre-remote','INPUT_MANIFEST.json')
    verify_manifest(prior/'spectre-remote','FILE_MANIFEST.json')
    if digest(prior/'INPUT_MANIFEST.json')!=digest(prior/'spectre-remote/INPUT_MANIFEST.json'):
        raise ValueError('previous backend inputs differ')
    shutil.copyfile(prior/'conditions.json',root/'conditions.json')
    shutil.copy2(kernel,root/'evas-kernel')
    kernel=root/'evas-kernel'
    dump(root/'STARTED.json',dict(kernel_sha256=digest(kernel),timeout_s=30,
        previous_run=prior.name,previous_raw_manifest_sha256=digest(prior/'RAW_MANIFEST.json'),
        previous_input_manifest_sha256=digest(prior/'INPUT_MANIFEST.json'),
        frozen_checker_sha256=digest(frozen),runner_sha256=digest(Path(__file__)),
        evidence_use='20 new EVAS requests with identical IR; 20 reused Spectre raw executions'))
    cases=json.loads((root/'conditions.json').read_text()); records=[]
    for c in cases:
        work=root/c['id']; work.mkdir()
        old=prior/c['id']
        for name in ['probe.va','evas-request.json']:
            shutil.copyfile(old/name,work/name)
        request=json.loads((work/'evas-request.json').read_text())
        start=time.monotonic(); process_started=False
        try:
            result=subprocess.run([str(kernel)],input=(work/'evas-request.json').read_text(),
                text=True,capture_output=True,timeout=30)
            process_started=True
            (work/'evas-stdout.json').write_text(result.stdout)
            (work/'evas-stderr.json').write_text(result.stderr)
            execution=dict(returncode=result.returncode,elapsed_s=time.monotonic()-start,
                request_sha256=digest(work/'evas-request.json'))
            if result.returncode:
                execution.update(status='kernel_refusal',error=json.loads(result.stderr))
            else:
                response=json.loads(result.stdout)
                if (response['nodes']!=request['program']['nodes'] or
                    response['schema_version']!=request['program']['schema_version'] or
                    response['transient']['times']!=c['output_times'] or
                    len(response['solutions'])!=len(c['output_times'])):
                    raise ValueError('response identity mismatch')
                rows=[dict(time=t,**dict(zip(response['nodes'],s['voltages'])))
                      for t,s in zip(c['output_times'],response['solutions'],strict=True)]
                dump(work/'evas-rows.json',rows)
                execution.update(status='waveform_available')
        except subprocess.TimeoutExpired:
            execution=dict(status='timeout',timeout_s=30,process_started=True)
        except Exception as error:
            execution=dict(status='execution_failure',reason=str(error),process_started=process_started)
        dump(work/'evas-execution.json',execution)
        old_execution=json.loads((old/'evas-execution.json').read_text())
        record=dict(backend='evas',case=c['id'],family=c['family'],profile=c['profile'],
            execution=execution,status=execution['status'],
            previous_execution_status=old_execution['status'],
            request_identical=digest(work/'evas-request.json')==digest(old/'evas-request.json'))
        if execution['status']=='waveform_available':
            record.update(checker.inspect(rows,c),waveform_sha256=digest(work/'evas-rows.json'))
        records.append(record)
        spec_work=prior/'spectre-remote'/c['id']
        spec_execution=json.loads((spec_work/'spectre-execution.json').read_text())
        reused=dict(backend='spectre',case=c['id'],family=c['family'],profile=c['profile'],
                    evidence_use='reused previous raw; rechecked by identical frozen checker',
                    execution=spec_execution)
        try:
            if spec_execution['returncode'] or spec_execution['timeout']:
                reused.update(status='execution_failure')
            else:
                wave=spec_work/'psf/tran.tran.tran'
                spec_rows=checker.read_waveform(wave,'spectre')
                actual,audit=checker.audit_displayed_settings((spec_work/'spectre.log').read_text(),c,spec_rows)
                if any(b['time']-a['time']>c['maxstep']*1.01 for a,b in zip(spec_rows,spec_rows[1:])):
                    raise ValueError('accepted export gap exceeds requested maxstep')
                reused.update(checker.inspect(spec_rows,c),waveform_sha256=digest(wave),
                              displayed_settings=actual,settings_audit=audit)
        except Exception as error:
            reused.update(status='analysis_failure',reason=str(error))
        records.append(reused)
        print(c['id'],record['status'],flush=True)
    analysis=dict(records=records,configurations_per_backend=len(cases),
        counts={b:dict(Counter(r['status'] for r in records if r['backend']==b)) for b in ['evas','spectre']},
        new_evas_execution=True,new_spectre_execution=False,
        frozen_checker_sha256=digest(frozen),previous_raw_manifest_sha256=digest(prior/'RAW_MANIFEST.json'),
        spectre_identity=json.loads((prior/'spectre-remote/SPECTRE_STARTED.json').read_text()),
        qualification='I',raw_availability='local-only',
        limits=['development cases; original31 denominator unchanged',
                'assumed finite observation allowance; no continuous-time qualification or accuracy ranking',
                'retained root observation policy can differ from Spectre late-trigger policy'])
    dump(root/'analysis.json',analysis)
    dump(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):digest(p)
        for p in sorted(root.rglob('*')) if p.is_file()})
    print(json.dumps(analysis['counts']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--kernel',type=Path,required=True)
    args=parser.parse_args()
    replay(args.prior.resolve(),args.root.resolve(),args.kernel.resolve())
