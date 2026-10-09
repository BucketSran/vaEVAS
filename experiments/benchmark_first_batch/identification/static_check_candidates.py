"""Validate all prepared identification candidates with the shared I/O boundary.

This does not compile Verilog-A, run Spectre, or claim semantic acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from prepare_candidates import VARIANTS, ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(runtime, candidates):
    spec=importlib.util.spec_from_file_location('circuit_task_static_boundary',runtime)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    results=[]
    for task,variants in VARIANTS.items():
        contract_path=ROOT/'benchmark/tasks'/task/'tests/contract.json'
        contract=json.loads(contract_path.read_text())
        for variant in ['reference']+variants:
            path=candidates/task/variant/'dut.va'
            source=path.read_bytes()
            record=dict(task=task,variant=variant,source_sha256=sha(path),contract_sha256=sha(contract_path))
            try:
                executed,receipt=module.prepare_source(source,contract['candidate_files'],contract['output_files'],path.parent/'static-output')
                if executed!=source or receipt['edits'] or not receipt['inverse_verified']:
                    raise ValueError('unexpected mutation of voltage-only source')
                record.update(status='passed',receipt=receipt)
            except Exception as exc:
                record.update(status='rejected',error=f'{type(exc).__name__}: {exc}')
            results.append(record)
    return dict(kind='shared_prepare_source_static_check',runtime_sha256=sha(runtime),
        lexer_sha256=sha(runtime.with_name('adc_linearity.py')),
        scope='Static submission boundary only; not VA compilation or Spectre acceptance.',
        count=len(results),passed_count=sum(r['status']=='passed' for r in results),candidates=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,default=ROOT/'runs/identification-candidates')
    args=parser.parse_args();result=check(args.runtime,args.candidates)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed_count']==result['count'] else 1)
