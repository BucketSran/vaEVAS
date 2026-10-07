"""Read existing actual-run archives; never submit a simulator job."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

UNITS={'s':1.,'ms':1e-3,'us':1e-6,'ns':1e-9}


def seconds(number,unit):
    return float(number)*UNITS[unit]


def phase_times(log,label):
    pattern=re.escape(label)+r"\s*CPU\s*=\s*([\d.eE+-]+)\s*(s|ms|us|ns),\s*elapsed\s*=\s*([\d.eE+-]+)\s*(s|ms|us|ns)"
    match=re.search(pattern,log)
    if not match:return None
    a,au,b,bu=match.groups()
    return dict(cpu_s=seconds(a,au),elapsed_s=seconds(b,bu))


def summarize(archive):
    with tarfile.open(archive) as tar:
        report=json.loads(tar.extractfile('run/work/verifier/report.json').read())
        result=dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    candidate_sha256=report.get('candidate_sha256'),cases_sha256=report.get('cases_sha256'),
                    checker_sha256=report.get('checker_sha256'),runtime_sha256=report.get('runtime_sha256'),
                    status=report.get('status'),reason=report.get('reason'),reward=report.get('reward'),cases=[])
        for case in report.get('cases',[]):
            name=case['name'];member=f'run/work/verifier/{name}/spectre.log'
            log=tar.extractfile(member).read().decode(errors='replace')
            version=re.search(r'^Version (.+)$',log,re.M)
            accepted=re.search(r'Number of accepted tran steps\s*=\s*(\d+)',log)
            rejected=re.search(r'Number of rejected tran steps\s*=\s*(\d+)',log)
            compile_match=re.search(r'Finished compilation in ([\d.eE+-]+)\s*(s|ms|us|ns)',log)
            licensing=re.search(r'Time spent in licensing: elapsed = ([\d.eE+-]+)\s*(s|ms|us|ns)',log)
            loads=re.search(r'System load averages[^\n]*',log)
            item=dict(name=name,passed=case.get('passed'),failures=case.get('failures'),
                      process_elapsed_s=case.get('elapsed_s'),spectre_version=version.group(1) if version else None,
                      accepted_steps=int(accepted.group(1)) if accepted else None,
                      rejected_steps=int(rejected.group(1)) if rejected else None,
                      intrinsic_tran=phase_times(log,'Intrinsic tran analysis time:'),
                      total_tran=phase_times(log,"Total time required for tran analysis `tran':"),
                      compilation_elapsed_s=seconds(*compile_match.groups()) if compile_match else None,
                      licensing_elapsed_s=seconds(*licensing.groups()) if licensing else None,
                      load_average_log=loads.group(0) if loads else None,
                      waveform_sha256=case.get('waveform_sha256'),waveform_rows=case.get('waveform_rows'))
            for key in ('max_code_voltage_error','max_point_error_v','max_interpolated_error_v',
                        'expected_samples','observed_clock_edges','expected_cycles','max_output_error_v'):
                if key in case:item[key]=case[key]
            result['cases'].append(item)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--calibration-root',type=Path,required=True)
    parser.add_argument('--names',nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    records=[]
    for name in args.names:
        for archive in sorted((args.calibration_root/name/'remote').glob('*/archive/job.tar.gz')):
            item=summarize(archive)
            item['run_name']=name
            item['archive_relative_path']=str(archive.relative_to(args.calibration_root))
            records.append(item)
    result=dict(kind='observed_actual_calibration',performance_verdict='inconclusive',
                limitations=['Single concurrent calibration round; not five alternating pairs.',
                             'No hot-path profile has been captured.',
                             'Rejected step counts absent from default logs remain null.',
                             'Compilation/queue/network/cache effects are not warmed or separated.',
                             'Aggregate audit elapsed duplicates CPU in observed Spectre logs; use intrinsic phase and independent process elapsed.'],
                records=records)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'Summarized {len(records)} actual archives to {args.output}')


if __name__=='__main__':
    main()
