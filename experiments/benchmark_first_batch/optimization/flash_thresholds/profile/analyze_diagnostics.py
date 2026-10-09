"""Recheck four declared actual flash diagnostics, never launch a solver."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tarfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
sys.path.insert(0,str(REPO/'benchmark/checkers'))
from adc_linearity import read_psf
from first_batch_optimization import read_native_statistics,validate_solver_evidence
from read_counters import read as read_counters


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_root',type=Path);parser.add_argument('output',type=Path);parser.add_argument('scratch',type=Path)
    args=parser.parse_args();args.scratch.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('current_flash_oracle',HERE.parent/'evaluate.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    cases={c['name']:c for c in json.loads((HERE.parent/'cases.json').read_text())}
    records=[]
    for request in json.loads((HERE/'REQUEST.json').read_text())['requests']:
        label=request['label'];source=(REPO/request['source']).read_bytes()
        archives=list((args.run_root/label/'remote').glob('*/archive/job.tar.gz'))
        if len(archives)!=1:raise ValueError('need exactly one actual diagnostic archive')
        archive=archives[0]
        with tarfile.open(archive) as tar:
            report=json.loads(tar.extractfile('run/work/verifier/report.json').read())
            if report['status']!='completed' or report['reward']!=1:raise ValueError('actual functional run failed')
            if len(report['cases'])!=1:raise ValueError('unexpected diagnostic workload')
            actual=report['cases'][0];prefix='run/work/verifier/'+actual['name']
            if tar.extractfile(prefix+'/dut.va').read()!=source or tar.extractfile(prefix+'/original/dut.va').read()!=source:raise ValueError('diagnostic source identity mismatch')
            native=tar.extractfile(prefix+'/spectre.log').read();merged=tar.extractfile(prefix+'/stdout.log').read()
            if actual['returncode']!=0:raise ValueError('solver process failed')
            if request['instrumented']:
                # Declared profiling-only strobe is trusted by exact source bytes.
                # It is NOT a performance-guard eligible submission.
                stats=read_native_statistics(native)
                if re.search(rb'(?:ERROR|FATAL)\s*\([A-Z][A-Z0-9_-]*-\d+\)|Error found by spectre|Segmentation fault',merged):raise ValueError('fatal diagnostic')
                counters=read_counters(archive,'baseline' if label=='count-continuous-linear-scan' else 'reference')
            else:
                stats=validate_solver_evidence(source,0,native,merged,None,stream_layout='merged');counters=None
            wave=tar.extractfile(prefix+'/psf/tran.tran.tran').read()
            if sha(wave)!=actual['waveform_sha256']:raise ValueError('waveform hash mismatch')
            temp=args.scratch/'wave.psf';temp.write_bytes(wave)
            replay=oracle.evaluate(read_psf(temp),cases[actual['name']])
            compile_matches=re.findall(rb'Finished compilation in ([\d.e+-]+) (ms|s) \(elapsed\) for offset_flash\.',native)
            if len(compile_matches)!=1:raise ValueError('compile timing ambiguity')
            value,unit=compile_matches[0]
            records.append(dict(label=label,instrumented=request['instrumented'],archive_sha256=sha(archive.read_bytes()),
                                source_sha256=sha(source),waveform_sha256=sha(wave),native_statistics=stats,
                                process_elapsed_s=actual['elapsed_s'],cold_compile_elapsed_s=float(value)*(1e-3 if unit==b'ms' else 1),
                                counters=counters,replay=replay,replay_checker_sha256=sha((HERE.parent/'evaluate.py').read_bytes()),
                                replay_cases_sha256=sha((HERE.parent/'cases.json').read_bytes())))
    args.output.write_text(json.dumps(dict(kind='actual_flash_limiter_diagnostics_not_repeated_timing',new_simulations=False,records=records),indent=2)+'\n')
    for r in records:print(r['label'],'raw_pass',r['replay']['passed'],'compile',r['cold_compile_elapsed_s'],'CPU',r['native_statistics']['intrinsic_tran']['cpu_s'],'process',r['process_elapsed_s'],'counters',r['counters']['records'] if r['counters'] else None)


if __name__=='__main__':main()
