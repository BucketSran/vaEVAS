"""Frozen 65-I hand stages; exact decimal anchors and no interpolation."""
from decimal import Decimal, InvalidOperation
from fractions import Fraction as Q

ABSOLUTE=1e-7
RELATIVE=1e-5
TIMES=tuple(Q(i,8) for i in range(9))
WINDOWS=((Q(1,4),Q(1,4)+Q(1,10**9)),(Q(1,2)-Q(1,10**9),Q(1,2)+Q(1,10**9)))
GROUPS={'first':('y1','q01','q11','qlast1'), 'second':('y2','q02','q12','qlast2')}
# Restore and pollution values are independently derived from the frozen VA.
VALUES={'first':((1,0,1,1),(81,40,41,41)), 'second':((33,10,11,12),(213,70,71,72))}
NODES=('u',*GROUPS['first'],*GROUPS['second'])


def rational(token):
    try: value=Decimal(str(token))
    except InvalidOperation as error: raise ValueError('invalid decimal token') from error
    if not value.is_finite(): raise ValueError('nonfinite waveform token')
    return Q(value)


def validate(rows):
    if not rows: raise ValueError('empty waveform')
    times=[]
    for row in rows:
        if 'time' not in row or not isinstance(row.get('voltages'),dict) or set(NODES)-set(row['voltages']):
            raise ValueError('missing time or saved node')
        times.append(rational(row['time']))
        for node in NODES: rational(row['voltages'][node])
    if any(b<a for a,b in zip(times,times[1:])): raise ValueError('waveform time order decreases')
    return times


def error(token,exact):
    difference=abs(float(rational(token)-exact))
    limit=ABSOLUTE+RELATIVE*abs(float(exact))
    return difference,limit,difference/limit


def stage(row,instance):
    nodes=GROUPS[instance]
    candidates=[s for s in (0,1) if all(error(row['voltages'][node],Q(value))[2]<=1
                for node,value in zip(nodes[1:],VALUES[instance][s][1:]))]
    return candidates[0] if len(candidates)==1 else None


def inside_window(time):
    return any(lo<=time<=hi for lo,hi in WINDOWS)


def assess(rows):
    times=validate(rows)
    stages={name:[stage(row,name) for row in rows] for name in GROUPS}
    failures=[]; maximum={'ratio':0.,'absolute':0.,'row':None,'node':None}
    for i,(row,time) in enumerate(zip(rows,times)):
        exact={'u':min(time,Q(1))}
        for name,nodes in GROUPS.items():
            s=stages[name][i]
            if s is None:
                failures.append(dict(row=i,instance=name,reason='observers do not share a permitted stage'))
                continue
            if not inside_window(time) and s!=int(Q(1,4)<=time<Q(1,2)):
                failures.append(dict(row=i,instance=name,reason='stage outside frozen event windows'))
            exact.update(zip(nodes,map(Q,VALUES[name][s])))
        for node,value in exact.items():
            difference,limit,ratio=error(row['voltages'][node],value)
            if ratio>maximum['ratio']: maximum=dict(ratio=ratio,absolute=difference,row=i,node=node)
            if ratio>1: failures.append(dict(row=i,node=node,reason='independent formula mismatch',error=difference,limit=limit))
    brackets={}
    for name,ss in stages.items():
        changes=[i for i in range(1,len(ss)) if ss[i]!=ss[i-1]]
        brackets[name]=[]
        if len(changes)!=2 or ss[0]!=0 or ss[-1]!=0 or any(s not in (0,1) for s in ss):
            failures.append(dict(instance=name,reason='missing or repeated pollution/restoration transition'))
            continue
        for index,window in zip(changes,WINDOWS):
            compatible=max(times[index-1],window[0])<=min(times[index],window[1])
            brackets[name].append(dict(before_row=index-1,after_row=index,before_token=rows[index-1]['time'],
                                       after_token=rows[index]['time'],intersects_frozen_window=compatible,
                                       limit='Native change bracket, not a callback-time certificate.'))
            if not compatible: failures.append(dict(instance=name,reason='event bracket outside frozen window'))
    points=[]
    for wanted in TIMES:
        found=[i for i,t in enumerate(times) if t==wanted]
        nearest=min(range(len(times)),key=lambda i:abs(times[i]-wanted))
        points.append(dict(requested=str(float(wanted)),exact_decimal_rows=found,nearest_row=nearest,
                           nearest_time_token=rows[nearest]['time'],decimal_offset=str(Decimal(rows[nearest]['time'])-Decimal(str(float(wanted)))),interpolated=False))
    initial=times[0]==0 and all(ss[0]==0 for ss in stages.values())
    stop=any(t==1 for t in times)
    anchors=all(p['exact_decimal_rows'] for p in points)
    return dict(rows=len(rows),checked_values=len(rows)*len(NODES),formula_and_stage_status='P' if not failures else 'F',
                failures=failures,max_error=maximum,stage_counts={name:{str(s):ss.count(s) for s in (0,1,None)} for name,ss in stages.items()},
                event_brackets=brackets,required_points=points,initial_status='P' if initial else 'I',exact_stop_status='P' if stop else 'I',
                exact_required_point_count=sum(bool(p['exact_decimal_rows']) for p in points),required_point_status='P' if anchors else 'I',
                strict_observation_status='P' if initial and stop and anchors else 'I')


def pair(native,candidate):
    times=validate(native); validate(candidate)
    by_time={float(rational(row['time'])):row for row in candidate}
    failures=[]; phases=[]; compared=0; maximum=0.
    for i,(row,time) in enumerate(zip(native,times)):
        other=by_time.get(float(time))
        if other is None:
            failures.append(dict(row=i,reason='missing candidate native-time query')); continue
        nodes=['u']; exact={'u':min(time,Q(1))}
        for name,group in GROUPS.items():
            left,right=stage(row,name),stage(other,name)
            if left is None or right is None:
                failures.append(dict(row=i,instance=name,reason='unqualified observer stage in pair')); continue
            if left!=right:
                phases.append(dict(row=i,instance=name,native_stage=left,candidate_stage=right,raw_time=row['time'],inside_frozen_window=inside_window(time)))
                if not inside_window(time): failures.append(dict(row=i,instance=name,reason='phase difference outside frozen window'))
                continue
            nodes.extend(group); exact.update(zip(group,map(Q,VALUES[name][left])))
        for node in nodes:
            difference=abs(float(rational(row['voltages'][node])-rational(other['voltages'][node])))
            ratio=difference/(ABSOLUTE+RELATIVE*abs(float(exact[node])))
            maximum=max(maximum,ratio); compared+=1
            if ratio>1: failures.append(dict(row=i,node=node,reason='same-stage pair mismatch',ratio=ratio))
    return dict(queried_native_rows=len(native),same_stage_values_compared=compared,maximum_pair_ratio=maximum,
                phase_differences=phases,failures=failures,voltage_status='P' if not failures else 'F',phase_status='P' if not phases else 'I',
                strict_phase_status='F' if phases else ('I' if any(f['reason'] in ('missing candidate native-time query','unqualified observer stage in pair') for f in failures) else 'P'))


if __name__=='__main__':
    import argparse
    import json
    import sys
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--candidate',type=Path)
    args=parser.parse_args()
    try:
        native=json.loads(args.native.read_text())
        result=pair(native,json.loads(args.candidate.read_text())) if args.candidate else assess(native)
        print(json.dumps(result,indent=2,allow_nan=False))
        raise SystemExit(0 if result.get('voltage_status',result.get('formula_and_stage_status'))=='P' and result.get('strict_phase_status')!='F' else 1)
    except ValueError as error:
        print(json.dumps(dict(status='ERROR',reason=str(error))),file=sys.stderr)
        raise SystemExit(2)
