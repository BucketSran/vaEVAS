"""Finite engineering checks from one retained event-stamp vector per run.

No frontend/kernel imports. This is not a continuous-time error certificate.
"""
from fractions import Fraction as F
import argparse
import json
import math
from pathlib import Path


def number(value, token=None):
    return F(str(token)) if token is not None else F(float(value))


def reference(case_id, time, stamps, unit, phase=None):
    """Hand-derived TR equations and held event states, using fixed stamps."""
    t = time / unit
    h1, h2, h3 = [stamps.get(k, F(-1)) for k in ('h1', 'h2', 'h3')]
    phase = phase or {}
    occurred = lambda s: phase.get(s, s >= 0 and t >= s)
    result = dict(y=F(0), z=F(0), q=F(0), n=F(0), m=F(0), s=F(0),
                  h1=h1 if occurred(h1) else F(-1),
                  h2=h2 if occurred(h2) else F(-1),
                  h3=h3 if occurred(h3) else F(-1))
    clip = lambda x: min(F(1), max(F(0), x))
    if case_id in ('T1', 'M1'):
        result['n'], result['m'] = F(occurred(h1)), F(occurred(h2))
        result['q'] = F(occurred(h1) and not occurred(h2))
        # First edge is complete before the second edge in the frozen slice.
        result['y'] = clip(t-h1-F(1,4)) - clip((t-h2-F(1,4))/2)
        if case_id == 'M1':
            result['z'] = number(1e6)*unit*(max(F(0),t-h1)-max(F(0),t-h2))
    elif case_id == 'T2':
        result['n'], result['m'] = F(occurred(h1)), F(occurred(h2))
        result['q'] = F(occurred(h1) and not occurred(h2))
        if t < h2+2:
            result['y'] = clip(t-h1-2)
        else:
            # At reversal: value=h2-h1; old target 1 is the new origin.
            result['y'] = max(F(0),h2-h1-(t-h2-2))
    elif case_id == 'C1':
        result['n'] = F(occurred(h1))
        result['s'] = result['q'] = h1/2 if occurred(h1) else F(0)
        result['y'] = (h1/2)*clip(t-h1-F(1,4))
    elif case_id == 'C2':
        result['n'], result['m'] = F(occurred(h1)), F(occurred(h2))
        result['q'] = F(occurred(h1) and not occurred(h2))
        interruption = (h2-h1)/10
        result['s'] = interruption if occurred(h2) else F(0)
        result['y'] = max(F(0),(t-h1)/10) if t < h2 else max(F(0),interruption-(t-h2)/20)
    elif case_id == 'H1':
        result['n'] = F(occurred(h2))
        result['q'] = F(not occurred(h3))
        result['s'] = F(4) if occurred(h1) else F(6)
        result['y'] = result['n']
    elif case_id == 'N1':
        result['n'], result['m'] = F(occurred(h1)), F(occurred(h2))
        result['q'] = F(occurred(h3))
        result['s'] = h2 if occurred(h2) else F(0)
        result['y'] = result['n']+10*result['m']+100*result['q']
    else:
        raise ValueError('unknown frozen case '+case_id)
    return result


def inspect(case, rows, decimal_tokens=None):
    """Accept normalized time/voltages rows; optional same-shaped token rows.

    decimal_tokens[i] may contain {'time': str, 'voltages': {node: str}}.
    Tokens retain export precision; they do not establish hidden callbacks.
    """
    report = dict(id=case['id'], status='F', failures=[], events=[], max_errors_v={},
                  points=len(rows), scope='finite named outputs and one retained event-stamp vector')
    fail = report['failures'].append
    if not rows:
        fail('no complete successful waveform')
        return report
    try:
        if decimal_tokens is not None and len(decimal_tokens) != len(rows):
            raise ValueError('decimal token row count differs')
        converted=[]
        for i,row in enumerate(rows):
            tokens=decimal_tokens[i] if decimal_tokens is not None else {}
            if not math.isfinite(float(row['time'])):
                raise ValueError('nonfinite time')
            values={}
            for node in case['voltage_nodes']:
                value=row['voltages'][node]
                if not math.isfinite(float(value)):
                    raise ValueError('nonfinite '+node)
                values[node]=number(value,tokens.get('voltages',{}).get(node))
            converted.append((number(row['time'],tokens.get('time')),values))
    except (KeyError,ValueError,TypeError,OverflowError) as error:
        fail('invalid or missing normalized observation: '+str(error))
        return report
    if any(b[0]<a[0] for a,b in zip(converted,converted[1:])):
        fail('unordered observation times')
        return report
    criteria=case['criteria']; unit=number(criteria['unit_s']); stop=number(case['stop'])
    # Physical coverage tolerates decimal export/last-bit representation.
    # This engineering allowance is not the exact boundary diagnostic.
    export_epsilon=number(max(1e-15,64*math.ulp(case['stop'])))
    if abs(converted[0][0])>export_epsilon or converted[-1][0]<stop-export_epsilon:
        fail('trace does not cover zero through requested stop')
    if any(t < -export_epsilon or t > stop+export_epsilon for t,_ in converted):
        fail('trace outside requested time domain')
    if criteria.get('required_grid',True):
        missing=[]; cursor=0
        for requested in case['times']:
            target=number(requested)
            while cursor+1<len(converted) and converted[cursor][0]<target-export_epsilon:
                cursor+=1
            if abs(converted[cursor][0]-target)>export_epsilon:
                missing.append(requested)
        if missing:
            report['missing_grid_times']=missing
            fail('missing '+str(len(missing))+' requested common observations')
    voltage_budget=number(criteria['voltage_budget_v'])
    sample_budget=number(criteria['sample_budget_v'])
    stamp_budget=number(criteria['clock_stamp_budget_v'])
    final=converted[-1][1]
    stamps={event['stamp_node']:final[event['stamp_node']] for event in criteria['events']}
    previous=None
    for event in criteria['events']:
        node=event['stamp_node']; stamp=stamps[node]; actual=stamp*unit
        nominal=number(event['nominal_time_s']); budget=number(event['time_budget_s'])
        # Stamp is itself a finite exported voltage, hence a bounded observation.
        displacement=abs(actual-nominal)
        ok=stamp>=0 and displacement<=budget+stamp_budget*unit
        report['events'].append(dict(stamp_node=node,stamp_v=float(stamp),
            observed_time_s=float(actual),nominal_time_s=float(nominal),
            nominal_displacement_s=float(actual-nominal),declared_time_budget_s=float(budget),
            stamp_time_uncertainty_s=float(stamp_budget*unit),within_nominal_window=ok))
        if not ok:fail('event stamp outside nominal window: '+node)
        if previous is not None and actual<=previous:
            fail('retained event stamps do not preserve required strict order')
        previous=actual
    for node,count in criteria['expected_final_counts'].items():
        if abs(final[node]-count)>voltage_budget:
            fail('wrong final source count: '+node)
    if report['failures']:
        # Bad stamps cannot define a valid downstream oracle.
        return report
    maxima={node:F(0) for node in case['voltage_nodes']}
    feasible={stamps[e['stamp_node']]:[
        max(stamps[e['stamp_node']]*unit-stamp_budget*unit,number(e['nominal_time_s'])-number(e['time_budget_s'])),
        min(stamps[e['stamp_node']]*unit+stamp_budget*unit,number(e['nominal_time_s'])+number(e['time_budget_s']))]
        for e in criteria['events']}
    discrete={'q','n','m','s','h1','h2','h3'}
    if case['id'] in ('H1','N1'):discrete.add('y')
    for t,values in converted:
        # Each frozen model exposes a persistent stamp with sentinel -1.
        # The pre/post values are disjoint by much more than its budget, so
        # stamp observations determine ONE phase, without a greedy branch.
        phase={}; valid=True
        for event in criteria['events']:
            node=event['stamp_node'];source=stamps[node];observed=values[node]
            pre=abs(observed-F(-1))<=stamp_budget
            post=abs(observed-source)<=stamp_budget
            if pre==post:
                fail('stamp does not identify a unique held event phase: '+node)
                valid=False
                continue
            phase[source]=post
            if post:feasible[source][1]=min(feasible[source][1],t+export_epsilon)
            else:feasible[source][0]=max(feasible[source][0],t-export_epsilon)
        if not valid:continue
        if any(lo>hi for lo,hi in feasible.values()):
            fail('no single event time explains boundary observations at '+str(float(t)))
        answer=reference(case['id'],t,stamps,unit,phase)
        for node in case['voltage_nodes']:
            error=abs(values[node]-answer[node])
            maxima[node]=max(maxima[node],error)
    report['shared_event_time_intervals_s']={e['stamp_node']:[float(x) for x in feasible[stamps[e['stamp_node']]]] for e in criteria['events']}
    report['max_errors_v']={node:float(error) for node,error in maxima.items()}
    for node,error in maxima.items():
        budget=stamp_budget if node.startswith('h') else sample_budget if node=='s' else voltage_budget
        if error>budget:
            fail('output '+node+' exceeds frozen budget')
            if node in discrete:fail('inconsistent shared event phase for '+node)
    report['status']='P' if not report['failures'] else 'F'
    report['limits']='Finite engineering observations. Stamps constrain one shared event history; they do not certify continuous-time error or hidden callback order.'
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('case',type=Path);parser.add_argument('rows',type=Path)
    args=parser.parse_args()
    card=json.loads(args.case.read_text());data=json.loads(args.rows.read_text())
    result=inspect(card,data['rows'] if isinstance(data,dict) else data,
                   data.get('decimal_tokens') if isinstance(data,dict) else None)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='P' else 1)
