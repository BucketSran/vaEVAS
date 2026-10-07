"""Losslessly compress preserved actual PSFs locally; not a solver measurement."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('actual_psf_storage',ROOT/'benchmark/checkers/first_batch_optimization.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def sha(data):return hashlib.sha256(data).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--analysis',type=Path,required=True);parser.add_argument('--scratch',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.analysis.read_bytes();analysis=json.loads(raw);args.scratch.mkdir(parents=True,exist_ok=True)
    records=[]
    for attempt,actual in zip(analysis['attempts'],analysis['records'],strict=True):
        if attempt['task_id'] not in ('optimize-vco-step','optimize-uart-calendar') or attempt['phase']!='warmup':continue
        archive=Path(actual['archive']);archive_data=archive.read_bytes()
        if sha(archive_data)!=actual['archive_sha256']:raise ValueError('archive identity mismatch')
        with tarfile.open(archive) as tar:data=tar.extractfile('run/work/verifier/'+actual['condition_id']+'/psf/tran.tran.tran').read()
        if sha(data)!=actual['waveform_sha256']:raise ValueError('waveform identity mismatch')
        directory=args.scratch/(attempt['task_id']+'-'+attempt['side']);directory.mkdir(exist_ok=False)
        path=directory/'tran.tran.tran';path.write_bytes(data);storage=M.lossless_compress_waveform(path)
        records.append(dict(task_id=actual['task_id'],role=attempt['side'],archive_sha256=actual['archive_sha256'],storage=storage))
    if len(records)!=4:raise ValueError('four actual original waveforms required')
    args.output.write_text(json.dumps(dict(kind='local_lossless_storage_check_of_actual_archived_psf',new_simulations=False,
        performance_measurement=False,solver_process_timer_unchanged=True,compression_host='local workstation, not solver host',
        python_version=sys.version.split()[0],input_analysis_sha256=sha(raw),records=records),indent=2)+'\n')
