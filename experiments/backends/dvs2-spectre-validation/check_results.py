"""Independent finite-observation checks for the fixed Spectre batch.

Raw accepted points are never interpolated or removed. P/F/I refer to the
stated finite numeric assumptions; formal observation qualification remains I.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import sys

from run_suite import ROOT, T, v1
from analyze import analyze as analyze_v1, read_waveform
sys.path.insert(0,str(ROOT/'experiments/archive/dvs2-history-validation'))
from history import Event, check_history
from recheck import event_contract


def lowpass(x):
    def ramp(a): return 0 if a <= 0 else a + .5*math.expm1(-2*a)
    return .6*(ramp(x-1)-ramp(x-2))


def lowpass_slope(x):
    def rate(a): return 0 if a <= 0 else -math.expm1(-2*a)
    return .6*(rate(x-1)-rate(x-2))


def histories(c):
    """Declarative normalized contracts, independent of the Verilog-A source."""
    kind=c['kind']; name=c['id']
    if kind=='v1' and name in ('v3-main','v4-c0','v4-c1','v5-main'):
        return {'vout':(.1,event_contract(name))}
    if kind=='e1':
        d=Q(str(c['delta'])); w=Q('0.0001' if name=='e1-slow' else '0.00005')
        return {'up':(0,[Event(r+d,target,'.01',0,w) for r,target in [(Q('.5'),'.1'),(Q('2.5'),'.2')]]),
                'down':(0,[Event(Q('1.5')+d,'.1','.01',0,w)])}
    if kind in ('e2','c1'):
        seq=[]
        if name != 'c1-no-reset-a': seq.append(Event('2.15','.1','.025',0,'.00002'))
        for x in map(Q,['.5','1.5','2.5','3.5']):
            if (x==Q('.5') and name=='e2-reset-high') or (x==Q('2.5') and name!='c1-no-reset-a'):
                continue
            seq.append(Event(x,Q('.8')-Q('.1')*x,'.025',0,'.00004','-.1'))
        result={'vout' if kind=='e2' else 'outa':(.1,sorted(seq,key=lambda e:e.start))}
        if kind=='c1':
            result['outb']=(.3,[Event(x,Q('.2')+Q('.1')*x,'.04',0,'.00004','.1')
                               for x in map(Q,['.75','1.75','2.75','3.75'])])
        return result
    if kind=='c2':
        # |z''| <= 1.2 V/x^2. Linearized sample target has remainder
        # <= .5*1.2*(.00004)^2 = 9.6e-10 V, reserved from epsilon below.
        return {'vout':(.1,[Event(x,lowpass(x),'.025',0,'.00004',lowpass_slope(x)) for x in [1.5,2.5,3.5]])}
    return {}


def nominal_history(x, initial, events):
    previous=float(initial)
    for event in events:
        start=float(event.start); target=float(event.target); duration=float(event.duration)
        if x < start: return previous
        if x < start+duration: return previous+(target-previous)*(x-start)/duration
        previous=target
    return previous


def reference(c,x):
    """Used for synthetic calibration and non-event analytic checks only."""
    if c['kind']=='v1': return v1.reference(c,x*T)
    result={name:nominal_history(x,initial,events) for name,(initial,events) in histories(c).items()}
    kind=c['kind']
    if kind=='c2': result['z']=lowpass(x)
    if kind=='d1':
        area=lambda z:.2*z-.05*z*z
        flag=c['id']=='d1-reset' and 1.5<=x<2.5
        result={'vout':.25 if flag else .25+area(x)-(area(2.5) if c['id']=='d1-reset' and x>=2.5 else 0), 'flag':float(flag)}
    if kind=='d2':
        total=.125+.5*x+.5*c['alpha']*x*x
        phase=total-math.floor(total)
        result={'accumulated':total,'wrapped':phase,'vout':.8*math.sin(2*math.pi*phase)}
    if kind=='s1':
        g1,g2,b=(1.5,-.5,.125) if c['id']=='s1-default' else (-.5,2,-.25)
        result={'vout':g1*v1.pwl(c['inputs']['u'],x*T)+g2*v1.pwl(c['inputs']['v'],x*T)+b}
    return result


def quality(rows,c):
    required={'time',*c['inputs'],*c['outputs']}
    if len(rows)<2 or any(not required.issubset(r) for r in rows): raise ValueError('missing waveform or required signal')
    if any(not math.isfinite(r[n]) for r in rows for n in required): raise ValueError('nonfinite observation')
    if abs(rows[0]['time'])>1e-15 or abs(rows[-1]['time']-c['stop_x']*T)>1e-12:
        raise ValueError('incomplete extent')
    gaps=[b['time']-a['time'] for a,b in zip(rows,rows[1:])]
    if min(gaps)<=0: raise ValueError('nonincreasing or ambiguous duplicate time')
    if max(gaps)>1.001e-9: raise ValueError('export gap exceeds predeclared 1 ns')
    errors={n:max(abs(r[n]-v1.pwl(points,r['time'])) for r in rows) for n,points in c['inputs'].items()}
    if any(e>1e-7 for e in errors.values()): raise ValueError('input mismatch')
    return dict(sample_count=len(rows),max_gap_s=max(gaps),input_max_error_v=errors)


def integrator_check(rows,c,budget):
    """A single reset/release history constrained by every exported flag and value.

The flag constrains a possible history but is not treated as event ground truth.
F requires one point outside every legal value; failed witness search yields I.
"""
    eps=.001; area=lambda x:.2*x-.05*x*x
    if c['id']=='d1-free':
        worst=max(abs(r['vout']-(.25+area(r['time']/T))) for r in rows)
        flag_error=max(abs(r['flag']) for r in rows)
        e=max(worst,flag_error)
        return dict(status='P' if e<=eps-budget else 'F' if e>eps+budget else 'I', max_error_v=e)
    lo_a,hi_a=1.5,1.50004; lo_b,hi_b=2.5,2.50004
    for r in rows:
        x=r['time']/T; f=r['flag']
        allowed=[1] if 1.50004<x<2.5 else [0] if x<1.5 or x>2.50004 else [0,1]
        if min(abs(f-q) for q in allowed)>eps+budget:
            return dict(status='F',reason='flag outside every legal history',time_x=x)
        if abs(f-1)<=eps-budget:
            hi_a=min(hi_a,x); lo_b=max(lo_b,x)
        elif abs(f)<=eps-budget:
            if x<2: lo_a=max(lo_a,x)
            else: hi_b=min(hi_b,x)
        else: return dict(status='I',reason='flag in uncertainty band')
        vals=[]
        if x<=1.50004: vals.append(.25+area(x))
        if 1.5<=x<=2.50004: vals.append(.25)
        if x>=2.5: vals += [.25+area(x)-area(b) for b in [2.5,min(x,2.50004)]]
        # One conservative interval union enclosure; it can fail to reject, never spuriously reject a legal branch.
        if r['vout']<min(vals)-eps-budget or r['vout']>max(vals)+eps+budget:
            return dict(status='F',reason='voltage outside every legal history',time_x=x)
    if lo_a>hi_a or lo_b>hi_b:
        return dict(status='I',reason='no numeric flag witness; boundary ordering unqualified')
    a=(lo_a+hi_a)/2; b=(lo_b+hi_b)/2
    worst=0
    for r in rows:
        x=r['time']/T
        y=.25+area(x) if x<a else .25 if x<b else .25+area(x)-area(b)
        flag=float(a<=x<b)
        worst=max(worst,abs(r['vout']-y),abs(r['flag']-flag))
    return dict(status='P' if worst<=eps-budget else 'I',witness_reset_x=a,witness_release_x=b,
                max_error_v=worst,reason='numeric common witness' if worst<=eps-budget else 'witness not established')


def check(rows,c):
    result=dict(formal_dvs_qualification='I',continuous_time_qualified=False,
                scope='finite accepted exports; candidate uncertainty bounds are not qualified')
    try: result['observation']=quality(rows,c)
    except (ValueError,KeyError,TypeError) as exc:
        return dict(result,status='observation_invalid',reason=str(exc))
    kind=c['kind']; constraints=histories(c); states=[]
    if kind=='v1':
        result['v1_screen']=analyze_v1(rows,c)
        states.append('P' if result['v1_screen']['status']=='observations_within_targets' else 'F')
    if constraints:
        result['history']={}
        for name,(initial,events) in constraints.items():
            pairs=[(Q(str(r['time']))/Q('0.000001'),Q(str(r[name]))) for r in rows]
            reserve=Q('0.000000001') if kind=='c2' else Q(0)
            scenarios={label:check_history(pairs,events,initial=initial,epsilon=Q('.001')-reserve,uncertainty=budget)
                for label,budget in [('exact_export_assumption',0),('candidate_budget_sensitivity',Q('.00025'))]}
            result['history'][name]=scenarios
            states.append(scenarios['exact_export_assumption']['status'])
    if kind in ('c2','s1','d2'):
        limits={'z':.0006} if kind=='c2' else {'vout':.001} if kind=='s1' else {'accumulated':.0001,'wrapped':.0001,'vout':.001}
        worst={name:0 for name in limits}
        for r in rows:
            expected=reference(c,r['time']/T)
            for name in limits:
                error=abs(r[name]-expected[name])
                if name=='wrapped': error=abs((r[name]-expected[name]+.5)%1-.5)
                worst[name]=max(worst[name],error)
        result['analytic_max_error']=worst
        result['analytic_targets']=limits
        states.append('P' if all(worst[n]<=limits[n] for n in limits) else 'F')
        if kind=='d2':
            wraps=sum(a['wrapped']-b['wrapped']>.5 for a,b in zip(rows,rows[1:]))
            expected_wraps=2 if c['id']=='d2-constant' else 4
            range_ok=all(-1e-12<=r['wrapped']<1+1e-12 for r in rows)
            result['phase_checks']=dict(observed_wrap_count=wraps,expected_wrap_count=expected_wraps,range_with_roundoff_ok=range_ok)
            states.append('P' if range_ok and wraps==expected_wraps else 'F')
    if kind=='d1':
        result['reset_history']={label:integrator_check(rows,c,budget) for label,budget in
            [('exact_export_assumption',0),('candidate_budget_sensitivity',.00025)]}
        states.append(result['reset_history']['exact_export_assumption']['status'])
    if not states: raise ValueError('unimplemented condition')
    result['status']='observed_violation' if 'F' in states else 'unresolved' if 'I' in states else 'observations_within_targets'
    return result


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args(); root=args.root.resolve()
    if args.output.resolve().is_relative_to(root) or args.output.exists(): raise ValueError('output must be new and outside raw evidence')
    manifest=json.loads((root/'FILE_MANIFEST.json').read_text())
    # Verify all archived files, not just successful waveforms.
    for rel,d in manifest.items():
        p=root/rel
        if not p.resolve().is_relative_to(root) or sha(p)!=d['sha256'] or p.stat().st_size!=d['bytes']:
            raise ValueError('evidence drift: '+rel)
    source=json.loads((root/'source_identity.json').read_text())
    for rel,digest in source.items():
        if rel.endswith('.py') and sha(ROOT/rel)!=digest: raise ValueError('analysis source differs from pre-run freeze: '+rel)
    records=[]
    for case in json.loads((root/'conditions.json').read_text()):
        for profile in ['base','fine']:
            work=root/'runs'/case['id']/profile
            result=json.loads((work/'result.json').read_text())
            if (result['condition'],result['profile'])!=(case['id'],profile): raise ValueError('result identity mismatch')
            if result['status']=='waveform_available':
                try: analysis=check(read_waveform(work/result['waveform'],'spectre'),case)
                except (ValueError,KeyError,TypeError,IndexError) as exc: analysis=dict(status='observation_invalid',reason=str(exc),formal_dvs_qualification='I')
            else: analysis=dict(status=result['status'],formal_dvs_qualification='I')
            records.append(dict(condition=case['id'],card=case['card'],kind=case['kind'],profile=profile,
                                execution_status=result['status'],elapsed_s=result['elapsed_s'],analysis=analysis))
            print(case['id'],profile,analysis['status'],flush=True)
    summary=dict(configurations=len(records),conditions=len({r['condition'] for r in records}),
                 execution=dict(Counter(r['execution_status'] for r in records)),
                 observation=dict(Counter(r['analysis']['status'] for r in records)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(run_id=root.name,file_manifest_sha256=sha(root/'FILE_MANIFEST.json'),
        input_manifest_sha256=sha(root/'INPUT_MANIFEST.json'),source_identity=source,summary=summary,records=records),indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__': main()
