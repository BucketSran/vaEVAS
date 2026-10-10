"""Conditional callback replay on an already observed accepted time grid.

This is a falsifiable diagnostic hypothesis, NOT an EVAS scheduling policy or a
way to infer Spectre's adaptive grid. Counter values never enter prediction.
"""
from fractions import Fraction
import argparse
import json
import math
from pathlib import Path
import re
from callback_probe import read_native, sha, stage_failure


def covers_windows(rows, start, period, tolerance, stop):
    """Coverage of the declared timer windows, not initial/DC qualification."""
    if not rows or start > stop:
        return False
    first, end, tol = Fraction(start), Fraction(stop), Fraction(tolerance)
    last = first + ((end-first)//Fraction(period))*Fraction(period) if period>0 else first
    return (Fraction(rows[0]['time']) <= max(Fraction(0),first-tol)
            and Fraction(rows[-1]['time']) >= min(end,last+tol))


def predict(times, start, period, tolerance):
    if not all(math.isfinite(v) for v in (start, period, tolerance)) or tolerance <= 0:
        raise ValueError('policy requires finite schedule and positive explicit tolerance')
    if period > 0 and 2*tolerance >= period:
        raise ValueError('overlapping periodic windows are outside this hypothesis')
    n = 0
    counters, callbacks = [], []
    previous = -math.inf
    for t in times:
        if not math.isfinite(t) or t <= previous:
            raise ValueError('accepted times must be finite and strictly increasing')
        previous = t
        if period > 0 or n == 0:
            target = Fraction(start) + n*Fraction(period)
            distance = Fraction(t)-target
            if distance > Fraction(tolerance):
                raise ValueError('accepted grid skipped an entire callback window')
            if distance >= -Fraction(tolerance):
                n += 1
                callbacks.append(t)
        counters.append(n)
    return counters, callbacks


def audit_case(directory, counter_columns):
    source=(directory/'dut.va').read_text()
    schedules=[list(map(float, args.split(','))) for args in
               re.findall(r'@\(timer\(([^)]*)', source)]
    rows=json.loads((directory/'rows.json').read_text())
    stop=json.loads((directory/'requested_settings.json').read_text())['stop_s']
    raw=directory/'psf/tran.tran.tran'
    receipt=json.loads((directory/'RESULT.json').read_text())
    if not rows or not all(covers_windows(rows,*p,stop) for p in schedules):
        raise ValueError('policy audit requires native coverage of every declared timer window')
    if not all(math.isfinite(v) for row in rows for v in row.values()) or read_native(raw,'spectre')!=rows:
        raise ValueError('policy audit requires finite rows matching original native output')
    if receipt.get('raw_sha256')!=sha(raw):
        raise ValueError('native identity mismatch')
    # Both the original chain runner and callback probe preserve this field.
    if stage_failure(receipt['execution']) or receipt.get('analysis_failure'):
        raise ValueError('failed execution is not a policy observation')
    if len(schedules)!=len(counter_columns):
        raise ValueError('timer/counter ownership must be explicit')
    result=[]
    for parameters,column in zip(schedules,counter_columns):
        if len(parameters)!=3 or parameters[2]<=0:
            result.append(dict(column=column,status='outside_policy',reason='requires three arguments and positive tolerance'))
            continue
        predicted,callbacks=predict([r['time'] for r in rows],*parameters)
        mismatches=[dict(row=i,time_s=r['time'],predicted=n,observed=r[column])
                    for i,(r,n) in enumerate(zip(rows,predicted)) if n!=r[column]]
        result.append(dict(column=column,status='MATCH' if not mismatches else 'MISMATCH',
                           rows=len(rows),callbacks=callbacks,mismatches=mismatches))
    return result


def audit(root, output, kind):
    manifest_path=root/('FILE_MANIFEST.json' if kind=='chain' else 'MANIFEST.json')
    manifest=json.loads(manifest_path.read_text())
    for name,digest in manifest.items():
        if sha(root/name)!=digest:
            raise ValueError('changed execution artifact: '+name)
    paths=([(root/case/setting,['an','bn'] if case=='SEF-ISOLATION' else ['an'])
            for case in ['SEF-TIMER','SEF-INTERRUPT','SEF-ISOLATION']
            for setting in ['base','tight','fine']] if kind=='chain' else
           [(root/name,['an']) for name in sorted({str(Path(p).parent) for p in manifest if p.endswith('/probe.json')})])
    records=[]
    for directory,columns in paths:
        try:
            result=audit_case(directory,columns)
            record=dict(case=str(directory.relative_to(root)),result=result)
        except (ValueError,FileNotFoundError,KeyError) as error:
            record=dict(case=str(directory.relative_to(root)),failure=str(error))
        records.append(record)
    with output.open('x') as stream:
        json.dump(dict(scope='Conditional replay on supplied accepted grid; not EVAS alignment',
                       execution_manifest_sha256=sha(manifest_path),records=records),stream,indent=2)
    for record in records:
        print(record['case'],record.get('failure') or [(r['status'],len(r.get('mismatches',[]))) for r in record['result']])
    if not records or any(r.get('failure') or any(v['status']!='MATCH' for v in r.get('result',[])) for r in records):
        raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--kind',choices=['chain','probes'],required=True)
    args=parser.parse_args()
    audit(args.root,args.output,args.kind)
