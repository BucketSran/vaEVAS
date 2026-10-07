"""Prepare VA07 calibration sources using the existing historical generator.

No simulator, SSH, model API, or shared lifecycle is invoked. Frozen original
case bytes remain available for EVAS; the coordinator supplies runtime metadata.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
GENERATOR=ROOT/'experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py'
TASK=ROOT/'benchmark/tasks/va07-triangle-repair'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output):
    spec=importlib.util.spec_from_file_location('va07_historical_generator',GENERATOR)
    generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
    original=json.loads((TASK/'tests/cases.json').read_text())
    if generator.bench_cases()!=original:
        raise ValueError('historical generator no longer matches original eight mathematical cases')
    rows=[r for r in generator.experiments() if r['kind'] in ['benchmark','calibration']]
    variants={};groups={}
    for row in rows:
        variant=row['family']
        source=row['source'];case_name=row['name'] if row['kind']=='benchmark' else row['name'][len(variant)+1:]
        if variant in variants and variants[variant]!=source:
            raise ValueError('one variant unexpectedly has multiple source identities')
        variants[variant]=source;groups.setdefault(variant,[]).append(case_name)
    output.mkdir(parents=True,exist_ok=False);plan=[]
    for variant,source in variants.items():
        directory=output/variant;directory.mkdir();candidate=directory/'dut.va';candidate.write_text(source)
        plan.append(dict(variant=variant,candidate=str(candidate.resolve()),candidate_sha256=digest(candidate),
            cases=groups[variant],expected_score=0 if variant not in ['reference','equivalent'] else 1))
    result=dict(status='prepared_only',simulator_executed=False,task='va07-triangle-repair',
        generator_sha256=digest(GENERATOR),canonical_oracle_sha256=digest(ROOT/'benchmark/checkers/triangle_oscillator.py'),
        original_cases_sha256=digest(TASK/'tests/cases.json'),reference_sha256=digest(TASK/'solution/dut.va'),
        signal_mapping=dict(ctl='positive velocity input relative to grounded r',z='triangle output relative to grounded r',count='integer reversal count voltage relative to grounded r'),
        candidates=plan,planned_condition_count=sum(len(r['cases']) for r in plan),
        equivalent_scope='One equivalent product-guard source, evaluated on two historical stimuli; not two distinct implementation sources.')
    (output/'plan.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'runs/legacy-va07-candidates')
    args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
