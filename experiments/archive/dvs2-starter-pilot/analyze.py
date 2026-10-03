"""Independent finite-observation checks. No claim of continuous-time qualification."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
from suite import STOP, T, events, pwl, reference


def number(s):
    try:
        return float(s)
    except ValueError:
        match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z]+)',s)
        factors={'T':1e12,'G':1e9,'Meg':1e6,'K':1e3,'k':1e3,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15,'a':1e-18}
        if not match or match[2] not in factors:
            raise ValueError('unrecognized numeric token: '+s)
        return float(match[1])*factors[match[2]]


def read_waveform(path, backend):
    if backend=='evas':
        with path.open() as stream:
            reader=csv.DictReader(stream)
            if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):
                raise ValueError('missing or duplicate CSV columns')
            return [{k:float(v) for k,v in row.items()} for row in reader]
    if backend=='spectre':
        lines=[line.strip() for line in path.read_text().splitlines()]
        start=lines.index('VALUE')+1
        if lines[-1]!='END':
            raise ValueError('truncated PSF')
        rows=[];row=None
        for line in lines[start:-1]:
            m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line)
            if not m:
                raise ValueError('unexpected PSF value: '+line)
            if m[1]=='time':
                if row is not None: rows.append(row)
                row={'time':float(m[2])}
            elif row is None or m[1] in row:
                raise ValueError('PSF time missing or repeated signal')
            else:
                row[m[1]]=float(m[2])
        if row is not None: rows.append(row)
        return rows
    lines=[line.split() for line in path.read_text().splitlines() if line.strip()]
    header=lines.pop(0)
    if header[0].lower() not in ['#time','time']:
        raise ValueError('unexpected text waveform header')
    names=['time']+[re.sub(r'^v\((.*)\)$',r'\1',name) for name in header[1:]]
    if len(names)!=len(set(names)) or any(len(row)!=len(names) for row in lines):
        raise ValueError('duplicate or ragged waveform columns')
    return [dict(zip(names,map(number,row))) for row in lines]


def edge_observations(rows, case):
    result=[];old=.1
    for start,target,duration,lo,hi,sample_slope in events(case):
        delta=target-old
        limits=[];measured=[];brackets=[]
        # The 1 mV voltage target is not a proven observation-error bound.
        # Use only brackets here; do not certify an internal event time.
        for fraction in [.1,.5,.9]:
            level=old+fraction*delta
            hits=[]
            for a,b in zip(rows,rows[1:]):
                if a['time']<start-duration or b['time']>start+2*duration:
                    continue
                ya,yb=a['vout'],b['vout']
                if (ya-level)*delta<0 and (yb-level)*delta>=0 and yb!=ya:
                    estimate=a['time']+(b['time']-a['time'])*(level-ya)/(yb-ya)
                    hits.append((a['time'],b['time'],estimate))
            if len(hits)!=1:
                result.append(dict(nominal_start_s=start,status='missing_or_multiple_crossings',fraction=fraction,count=len(hits)))
                break
            left,right,estimate=hits[0]
            limits.append((left-fraction*duration,right-fraction*duration))
            measured.append(estimate);brackets.append(right-left)
        else:
            lower=max(v[0] for v in limits);upper=min(v[1] for v in limits)
            overlap=max(lower,start+lo)<=min(upper,start+hi)+1e-18
            result.append(dict(nominal_start_s=start,status='joint_brackets_overlap' if overlap else 'joint_brackets_disjoint',
                output_50_time_s=measured[1],inferred_start_error_s=measured[1]-.5*duration-start,
                full_edge_estimate_s=(measured[2]-measured[0])/.8,
                nominal_full_edge_s=duration,max_crossing_bracket_s=max(brackets),
                joint_start_interval_s=[lower,upper],allowed_start_interval_s=[start+lo,start+hi],
                internal_event_observed=False))
        old=target
    return result


def analyze(rows,case):
    required={'time',*case['inputs'],*case['outputs']}
    if not rows or any(not required.issubset(row) for row in rows):
        raise ValueError('missing waveform or required signal')
    if any(not math.isfinite(row[name]) for row in rows for name in required):
        raise ValueError('nonfinite waveform')
    if abs(rows[0]['time'])>1e-15 or abs(rows[-1]['time']-STOP)>1e-12:
        raise ValueError('incomplete time extent')
    gaps=[b['time']-a['time'] for a,b in zip(rows,rows[1:])]
    if not gaps or min(gaps)<=0:
        raise ValueError('nonincreasing time')
    maxgap=max(gaps)
    if maxgap>1.001e-9:
        raise ValueError('observation gap exceeds predeclared 1 ns')
    input_errors={n:max(abs(row[n]-pwl(points,row['time'])) for row in rows) for n,points in case['inputs'].items()}
    if any(value>1e-7 for value in input_errors.values()):
        return dict(status='input_mismatch',input_max_error_v=input_errors,sample_count=len(rows),max_gap_s=maxgap)
    card=case['card'];seq=events(case)
    maximum={n:{'error_v':0.,'time_s':0.} for n in case['outputs']}
    failures=0;plateau_error=0.;shape_excess=0.;differential=0.;common=0.;residual=0.
    for row in rows:
        t=row['time'];expected=reference(case,t)
        errors={n:abs(row[n]-expected[n]) for n in expected}
        for n,error in errors.items():
            if error>maximum[n]['error_v']:
                maximum[n]={'error_v':error,'time_s':t}
        if card=='d2_v2_01':
            differential=max(differential,abs((row['op']-row['on'])-(expected['op']-expected['on'])))
            common=max(common,abs((row['op']+row['on'])/2-(expected['op']+expected['on'])/2))
        elif seq:
            # Nominal-waveform envelope is necessary, not sufficient for a common event history.
            allowance=6e-6 if card=='d2_v4_01' else 0.
            plateau=True;old=.1
            for start,target,duration,lo,hi,slope in seq:
                if start+lo-1e-15<=t<=start+duration+hi+1e-15:
                    plateau=False
                    allowance+=abs(target-old)/duration*max(abs(lo),abs(hi))
                old=target
            error=errors['vout']
            shape_excess=max(shape_excess,error-allowance)
            if plateau: plateau_error=max(plateau_error,max(0,error-allowance))
            failures+=error>0.001+allowance+1e-12
        else:
            epsilon=.0006 if card=='d2_v6_01' else .001
            failures+=any(error>epsilon+1e-12 for error in errors.values())
        if card=='d2_v7_01':
            residual=max(residual,abs(.5*row['outa']-row['vina']),abs(1.5*row['outb']-row['vinb']))
        elif card=='d2_v7_02':
            y=row['vout'];residual=max(residual,abs(y+case['cubic']*y**3-row['vin']))
    if card=='d2_v2_01':
        failures=int(differential>.002+1e-12 or common>.001+1e-12)
    edge=edge_observations(rows,case) if seq else []
    # Bracket disjointness alone is diagnostic: voltage/export uncertainty is not yet bounded.
    missing=any(e['status']=='missing_or_multiple_crossings' for e in edge)
    return dict(status='observed_violation' if failures or missing else 'observations_within_targets',
        formal_dvs_qualification='I',sample_count=len(rows),max_gap_s=maxgap,input_max_error_v=input_errors,
        max_observed_error=maximum,violating_sample_count=failures,plateau_error_v=plateau_error if seq else None,
        waveform_excess_over_nominal_event_allowance_v=shape_excess if seq else None,
        differential_error_v=differential if card=='d2_v2_01' else None,
        common_mode_error_v=common if card=='d2_v2_01' else None,
        max_relationship_residual_v=residual if card.startswith('d2_v7') else None,
        edges=edge,interpretation='finite exported observations; internal event and unsampled behavior remain unqualified')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    args=parser.parse_args();results=[]
    for path in sorted((args.root/'runs').glob('*/*/*/result.json')):
        result=json.loads(path.read_text());work=path.parent
        if result['status']=='waveform_available':
            case=json.loads((work/'condition.json').read_text())
            try:
                rows=read_waveform(work/result['waveform'],result['backend'])
                result['analysis']=analyze(rows,case)
            except (ValueError,KeyError,TypeError,IndexError) as exc:
                result['analysis']={'status':'observation_invalid','reason':str(exc),'formal_dvs_qualification':'I'}
            (work/'analysis.json').write_text(json.dumps(result['analysis'],indent=2)+'\n')
        results.append(result)
    (args.root/'ANALYSIS.json').write_text(json.dumps(results,indent=2)+'\n')
    for r in results:
        a=r.get('analysis',{})
        print(r['backend'],r['condition'],r['profile'],a.get('status',r['status']),
              max((v['error_v'] for v in a.get('max_observed_error',{}).values()),default=0),a.get('reason',''))


if __name__=='__main__':
    main()
