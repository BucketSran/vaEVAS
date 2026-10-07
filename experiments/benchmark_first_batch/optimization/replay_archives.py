"""Replay newly strengthened public oracles on immutable actual waveforms."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[2]/'benchmark/checkers'))
from adc_linearity import read_psf
from first_batch_optimization import read_native_statistics

FAMILIES={'optimize-vco-step':'vco_boundstep','optimize-flash-thresholds':'flash_thresholds',
          'optimize-power-monitor':'power_monitor','optimize-sampled-dac':'sampled_dac',
          'optimize-sc-coefficients':'sc_coefficients'}


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--calibration-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scratch',type=Path,required=True)
    args=parser.parse_args()
    args.scratch.mkdir(parents=True,exist_ok=True)
    records=[]
    for probe,family in FAMILIES.items():
        checker=ROOT/family/'evaluate.py';cases_file=ROOT/family/'cases.json'
        spec=importlib.util.spec_from_file_location(family,checker)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cases={case['name']:case for case in json.loads(cases_file.read_text())}
        for side in ('baseline','reference'):
            run=f'{probe}-{side}-v2'
            for archive in sorted((args.calibration_root/run/'remote').glob('*/archive/job.tar.gz')):
                with tarfile.open(archive) as tar:
                    report=json.loads(tar.extractfile('run/work/verifier/report.json').read())
                    for actual in report['cases']:
                        name=actual['name'];prefix=f'run/work/verifier/{name}'
                        waveform=tar.extractfile(f'{prefix}/psf/tran.tran.tran').read()
                        local=args.scratch/'wave.psf';local.write_bytes(waveform)
                        result=module.evaluate(read_psf(local),cases[name])
                        stats=read_native_statistics(tar.extractfile(f'{prefix}/spectre.log').read().decode())
                        records.append(dict(run_name=run,case=name,archive_sha256=sha(archive.read_bytes()),
                                            waveform_sha256=sha(waveform),candidate_sha256=report['candidate_sha256'],
                                            executed_checker_sha256=report['checker_sha256'],
                                            replay_checker_sha256=sha(checker.read_bytes()),
                                            replay_cases_sha256=sha(cases_file.read_bytes()),
                                            executed_passed=actual['passed'],replay=result,native_statistics=stats))
    args.output.write_text(json.dumps(dict(kind='actual_waveform_replay_not_new_va_execution',records=records),indent=2)+'\n')
    print(f'{sum(r["replay"]["passed"] for r in records)}/{len(records)} replay cases passed')
    for r in records:
        if not r['replay']['passed']:print(r['run_name'],r['case'],r['replay'])

if __name__=='__main__':main()
