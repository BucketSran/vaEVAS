"""Freeze the original VA07 eight-case EVAS checker package for Harness replay."""
import argparse
import json
from pathlib import Path
import shutil

import triangle_evas_replay as adapter

ROOT=Path(__file__).resolve().parents[2]


def build_package(output, oracle_path=None):
    """Keep original behavior identity; capture backend scripts as package files."""
    cases_path=ROOT/'benchmark/tasks/va07-triangle-repair/tests/cases.json'
    if adapter.digest(cases_path)!=adapter.CASES_SHA256:
        raise ValueError('original VA07 cases changed')
    cases=json.loads(cases_path.read_text())
    selected=Path(oracle_path or adapter.ORACLE_PATH)
    if adapter.digest(selected) not in adapter.SUPPORTED_ORACLES:
        raise ValueError('selected canonical oracle is not an explicitly calibrated full source file')
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(cases_path,output/'cases.json')
    shutil.copyfile(selected,output/'triangle_oscillator.py')
    shutil.copyfile(Path(adapter.__file__),output/'triangle_evas_replay.py')
    (output/'test.sh').write_text('#!/bin/sh\nset -eu\nexec python3 -B "$(dirname "$0")/triangle_evas_replay.py" --candidate "$CANDIDATE" --output "$VERIFY_OUTPUT"\n')
    adapter.dump(output/'mapping.json',dict(schema_version=1,solver_options=adapter.SOLVER_OPTIONS,
        cases=[dict(name=c['name'],requests=adapter.prepare_requests(c)[0],mapping=adapter.prepare_requests(c)[1]) for c in cases],
        limitations='Independent sampled evidence only; iabstol and traponly have no EVAS equivalent; both Spectre tolerance levels map to the same fixed EVAS options.'))
    manifest=dict(schema_version=1,task_id='va07-triangle-repair',task_version='dev-df643eaf9fd82a56',
        criteria_sha256='df643eaf9fd82a569e276640d3a673fa0a632c50b7b56dcf009a83ab3ab77f10',
        condition_id='va07-original-eight-cases-df84f3123a91',task_set='extension',purpose='final',
        entrypoint='test.sh',candidate_file='dut.va',report_path='verifier/report.json',feedback_fields=[],
        files={p.name:dict(sha256=adapter.digest(p),bytes=p.stat().st_size) for p in sorted(output.iterdir())})
    adapter.dump(output/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--oracle',type=Path,help='Explicit canonical checker from the coordinated report-only fix')
    args=parser.parse_args()
    build_package(args.output,args.oracle)
