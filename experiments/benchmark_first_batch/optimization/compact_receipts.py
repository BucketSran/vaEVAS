"""Retain compact actual evidence; no solver launch and no remote artifact URL."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tarfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
sys.path.insert(0,str(REPO/'benchmark/checkers'))
from adc_linearity import read_psf
from first_batch_optimization import validate_solver_evidence

TASKS=('optimize-vco-step','optimize-power-monitor','optimize-sar-calendar','optimize-uart-calendar')


def sha(data):return hashlib.sha256(data).hexdigest()


def native_clock_times(log):
    match=re.search(r'Simulation started at: (.*?), ended at: (.*?), with elapsed time',log)
    if not match:raise ValueError('native start/end timestamps missing')
    # Header timestamps have one-second precision. The log gives no timezone;
    # do not invent UTC or infer actual duration from the misleading audit total.
    return [datetime.datetime.strptime(text.replace('Thur ','Thu '),'%I:%M:%S %p, %a %b %d, %Y').isoformat()
            for text in match.groups()]


def compact_pairs(path):
    data=path.read_bytes();document=json.loads(data)
    if document['kind']!='offline_analysis_of_actual_spectre_jobs':raise ValueError('actual offline evidence required')
    rows=[]
    for attempt,record in zip(document['attempts'],document['records'],strict=True):
        if record['task_id'] not in TASKS:continue
        archive=Path(record['archive'])
        if sha(archive.read_bytes())!=record['archive_sha256']:raise ValueError('archive hash changed')
        with tarfile.open(archive) as tar:
            native=tar.extractfile('run/work/verifier/'+record['condition_id']+'/spectre.log').read()
        if sha(native)!=record['native_statistics']['native_log_sha256']:raise ValueError('native hash changed')
        start,end=native_clock_times(native.decode())
        rows.append({**{key:record[key] for key in ('task_id','condition_id','job_id','archive_sha256',
                     'candidate_bundle_sha256','source_sha256','criteria_sha256','netlist_sha256',
                     'native_host_identity_sha256','report_sha256','waveform_sha256','solver_process_elapsed_s')},
                     'phase':attempt['phase'],'pair':attempt['pair'],'role':attempt['side'],
                     'source_identity':record['source_identity'],
                     'native_log_sha256':sha(native),'native_start_clock':start,'native_end_clock':end,
                     'native_statistics':{key:record['native_statistics'][key] for key in
                       ('spectre_version','native_cpu_type','accepted_steps','rejected_steps','intrinsic_tran','total_tran','native_errors','stream_layout','stream_identities')},
                     'functional_result':record['functional_result'],'solver_argv':record['solver_argv']})
    if len(rows)!=48:raise ValueError('one warmup pair plus five measured pairs for four tasks required')
    return dict(kind='compact_subset_of_verified_actual_quiet_pairs',new_simulations=False,
                input_analysis_sha256=sha(data),input_manifest_sha256=document['manifest_sha256'],
                source_analysis='runs/benchmark-first-batch-20261008/performance-all-analysis-v1.json',
                raw_artifact_availability='local-only; hashes identify retained archives, not downloadable URLs',
                native_clock_timezone=None,native_clock_precision_s=1,
                native_clock_window=dict(first_start=min(r['native_start_clock'] for r in rows),last_end=max(r['native_end_clock'] for r in rows)),
                records=rows,paired_summaries={task:document['paired_summaries'][task] for task in TASKS},
                scope='four original candidate quiet pairs; not formal same-job verifier execution',
                current_functional_replay_sha256=sha((HERE/'raw_point_waveform_replay.json').read_bytes()))


def flash_function(run_root,scratch):
    spec=importlib.util.spec_from_file_location('compact_current_flash',HERE/'flash_thresholds/evaluate.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    cases={c['name']:c for c in json.loads((HERE/'flash_thresholds/cases.json').read_text())}
    rows=[]
    for label,filename in [('event-only','sampled_linear_scan.va'),('analytic','analytic_inverse.va')]:
        source=(HERE/'flash_thresholds/profile'/filename).read_bytes()
        directory=run_root/('flash-'+label+'-function-v1')
        for archive in sorted((directory/'remote').glob('*/archive/job.tar.gz')):
            with tarfile.open(archive) as tar:
                report_data=tar.extractfile('run/work/verifier/report.json').read();report=json.loads(report_data)
                if report['status']!='completed' or report['reward']!=1 or len(report['cases'])!=1:raise ValueError('actual functional run incomplete')
                actual=report['cases'][0];name=actual['name'];prefix='run/work/verifier/'+name
                if tar.extractfile(prefix+'/original/dut.va').read()!=source or tar.extractfile(prefix+'/dut.va').read()!=source:raise ValueError('candidate source mismatch')
                netlist=tar.extractfile(prefix+'/tb.scs').read()
                if netlist!=cases[name]['netlist'].encode():raise ValueError('functional workload mismatch')
                native=tar.extractfile(prefix+'/spectre.log').read();merged=tar.extractfile(prefix+'/stdout.log').read()
                stats=validate_solver_evidence(source,actual['returncode'],native,merged,None,stream_layout='merged')
                waveform=tar.extractfile(prefix+'/psf/tran.tran.tran').read()
                if sha(waveform)!=actual['waveform_sha256']:raise ValueError('waveform identity changed')
                temp=scratch/'wave.psf';temp.write_bytes(waveform)
                replay=oracle.evaluate(read_psf(temp),cases[name])
                if replay['passed'] is not True:raise ValueError('current raw-point oracle failed')
                start,end=native_clock_times(native.decode())
                compile_matches=re.findall(rb'Finished compilation in ([\d.e+-]+) (ms|s) \(elapsed\) for offset_flash\.',native)
                if len(compile_matches)!=1:raise ValueError('missing/ambiguous cold compilation')
                duration,unit=compile_matches[0]
                rows.append(dict(candidate=label,case=name,archive_sha256=sha(archive.read_bytes()),
                                 raw_artifact_availability='local-only',report_sha256=sha(report_data),
                                 source_sha256=sha(source),executed_source_sha256=sha(source),
                                 waveform_sha256=sha(waveform),netlist_sha256=sha(netlist),
                                 executed_cases_sha256=report['cases_sha256'],executed_verify_sha256=report['checker_sha256'],
                                 executed_runtime_sha256=report['runtime_sha256'],executed_contract_sha256=report['contract_sha256'],
                                 replay_checker_sha256=sha((HERE/'flash_thresholds/evaluate.py').read_bytes()),
                                 replay_cases_sha256=sha((HERE/'flash_thresholds/cases.json').read_bytes()),
                                 functional_result=replay,native_statistics=stats,solver_argv=actual['argv'],
                                 native_start_clock=start,native_end_clock=end,
                                 solver_process_elapsed_s=actual['elapsed_s'],
                                 cold_compile_elapsed_s=float(duration)*(1e-3 if unit==b'ms' else 1)))
    if len(rows)!=6 or any({r['case'] for r in rows if r['candidate']==c}!=set(cases) for c in ('event-only','analytic')):
        raise ValueError('all three conditions required for both candidates')
    return dict(kind='compact_actual_flash_candidate_function_receipts',new_simulations=False,
                performance_verdict='unmeasured repeatability; six functional calibrations only',
                old_binary_reference_unchanged=True,native_clock_timezone=None,native_clock_precision_s=1,records=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-root',type=Path,required=True);parser.add_argument('--scratch',type=Path,required=True)
    args=parser.parse_args();args.scratch.mkdir(parents=True,exist_ok=True)
    (HERE/'quiet_four_tasks_receipt.json').write_text(json.dumps(compact_pairs(args.run_root/'performance-all-analysis-v1.json'),indent=2)+'\n')
    (HERE/'flash_thresholds/profile/new_candidate_function_receipts.json').write_text(json.dumps(flash_function(args.run_root,args.scratch),indent=2)+'\n')
