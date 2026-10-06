"""Freeze the original VA07 eight-case EVAS checker package for Harness replay."""
import argparse
import ast
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
    def behavior(path):
        tree=ast.parse(path.read_text())
        classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BehavioralRejection']
        if classes and (len(classes)!=1 or len(classes[0].bases)!=1
            or not isinstance(classes[0].bases[0],ast.Name) or classes[0].bases[0].id!='ValueError'
            or any(not isinstance(n,ast.Expr) or not isinstance(n.value,ast.Constant) or not isinstance(n.value.value,str) for n in classes[0].body)):
            raise ValueError('BehavioralRejection must remain a report-only ValueError subclass')
        messages={'noninteger count','missing, grouped or reversed count','incorrect count outside event windows','incorrect event count'}
        class ReportingExceptions(ast.NodeTransformer):
            def visit_Raise(self,node):
                call=node.exc
                if (classes and isinstance(call,ast.Call) and isinstance(call.func,ast.Name)
                    and call.func.id=='BehavioralRejection' and len(call.args)==1
                    and isinstance(call.args[0],ast.Constant) and call.args[0].value in messages):
                    call.func.id='ValueError'
                return node
        tree=ReportingExceptions().visit(tree)
        return [ast.dump(n,include_attributes=False) for n in tree.body
                if isinstance(n,ast.FunctionDef) and n.name in {'area','reference','roots','evaluate'}]
    if behavior(selected)!=behavior(adapter.ORACLE_PATH):
        raise ValueError('selected canonical oracle changes the original behavior criteria')
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
