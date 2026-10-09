"""Bind actual EVAS response evidence to paper roles without creating missing proofs."""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
from observations import normalize_observation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def upper(value):
    """Round a nonnegative rational upper bound outward to binary64."""
    result=float(value)
    return math.nextafter(result,math.inf) if F(result)<value else result


def bind(path):
    p=Path(path).resolve()
    return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}


def input_curve_bound(card,request):
    """Exact sup of two continuous affine PWLs on the original card domain."""
    domain=F(str(card['stop_T']))/10**6
    maxima={}
    def value(points,t):
        for (a,u),(b,v) in zip(points,points[1:]):
            if a<=t<=b:return u+(v-u)*(t-a)/(b-a)
        raise ValueError('input curve coverage insufficient')
    for name,stimulus in card['stimulus'].items():
        if stimulus.get('kind')!='pwl':return None,{'reason':'unsupported non-PWL stimulus','input':name}
        ideal=[(F(str(t))/10**6,F(str(v))) for t,v in stimulus['points_T_V']]
        actual=[(F(t),F(v)) for t,v in request['inputs'][name]]
        if any(len(p)<2 or any(a[0]>=b[0] for a,b in zip(p,p[1:])) or p[0][0]>0 or p[-1][0]<domain for p in (ideal,actual)):
            return None,{'reason':'noncontinuous/nonmonotone or insufficient original-domain coverage','input':name}
        knots=sorted({F(0),domain,*[t for t,_ in ideal if 0<=t<=domain],*[t for t,_ in actual if 0<=t<=domain]})
        bound=max(abs(value(ideal,t)-value(actual,t)) for t in knots)
        maxima[name]={'bound_V':upper(bound),'exact_numerator':bound.numerator,'exact_denominator':bound.denominator,'union_knots':len(knots)}
    return max((b['bound_V'] for b in maxima.values()),default=0),{'inputs':maxima,'domain_s':[0,upper(domain)]}


def derive(card, request, requested_times, response, previous, review, *, core_sha, source_sha):
    """Return role facts; containment validates transport, not the solver proof.

    Source review is independent and explicit. Native query evaluation is reported
    separately from the legacy paper contract's accepted-step identity.
    """
    expected_inputs={n:[[t*1e-6,v] for t,v in stimulus['points_T_V']] for n,stimulus in card['stimulus'].items()}
    if request['inputs']!=expected_inputs or request['stop']!=card['stop_T']*1e-6:
        raise ValueError('actual stimulus/stop differs from frozen card')
    nodes=response['nodes']; times=response['transient']['times']; solutions=response['solutions']
    if times!=requested_times or len(times)!=len(solutions):
        raise ValueError('response does not preserve actual request times')
    if any(isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) for t in times):
        raise ValueError('invalid actual timestamps')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for solution in solutions for v in solution['voltages']):
        raise ValueError('invalid actual voltages')
    if len(set(nodes))!=len(nodes) or not set(card['observables'])<=set(nodes):
        raise ValueError('missing or duplicate actual nodes')
    rows=[dict(time=t,**dict(zip(nodes,s['voltages'],strict=True))) for t,s in zip(times,solutions,strict=True)]
    if previous['rows']!=rows or previous.get('condition')!=card['id'] or previous.get('backend')!='evas':
        raise ValueError('raw/normalized identity mismatch')
    roles={r:{'status':'unknown','basis':'missing actual evidence'} for r in
           ('source','time','voltage','inputs','native_initial','native_counters','native_phase')}
    matches=[r for r in review.get('records',[]) if r.get('condition')==card['id']]
    if review.get('schema_version')!=1 or review.get('cards_sha256',review.get('core-v1.json_file_sha'))!=core_sha:
        raise ValueError('source review core identity mismatch')
    if len(matches)!=1:
        raise ValueError('source review must contain exactly one condition record')
    record=matches[0]
    if record.get('source_sha256')!=source_sha or record.get('card_sha256')!=canonical_sha(card):
        raise ValueError('source review card/source identity mismatch')
    if record.get('status')=='reviewed' and ((isinstance(record.get('basis'),str) and record['basis'].strip()) or (isinstance(record.get('basis'),list) and record['basis'] and all(isinstance(x,str) and x.strip() for x in record['basis']))):
        roles['source']={'status':'established','basis':record['basis'],'limits':record.get('limits')}
    else:
        roles['source']={'status':record.get('status','unknown'),'basis':'external source review is not reviewed with a nonempty basis'}
    nominal=[F(str(t)) for t in requested_times]
    errors=[abs(F(t)-n) for t,n in zip(times,nominal,strict=True)]
    # Include independent decimal card obligations, rather than just comparing
    # a request echo with itself. Every named anchor/center must have a real row.
    named=[a['t_T'] for a in card.get('anchors',[])]+[w['center_T'] for w in card['observation_windows']]
    for value in named:
        requested=float(value)*1e-6
        if requested not in times:
            raise ValueError('missing named nominal request row')
        errors.append(abs(F(requested)-F(str(value))/10**6))
    time_error=upper(max(errors,default=F(0)))
    roles['time']={'status':'established','basis':'every raw timestamp equals its binary64 request; exact rational decimal-to-binary64 bounds include card anchors and centers','bound_s':time_error}
    evidence=response.get('observation_evidence')
    voltage_error=None; origins=['unknown']*len(rows)
    if evidence is not None:
        if evidence.get('schema_version')!=1 or evidence.get('nodes')!=nodes:
            raise ValueError('invalid observation evidence schema/node identity')
        controls=evidence['effective_controls']
        for key in ('absolute_V','relative','stop_s','max_step_s'):
            value=controls.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (key!='relative' and value==0):
                raise ValueError('invalid actual effective controls')
        if type(controls.get('max_step_applied')) is not bool:
            raise ValueError('invalid actual max_step application flag')
        bounds=evidence['voltage_bounds_V']; actual_origins=evidence['sample_origins']
        if len(bounds)!=len(rows) or len(actual_origins)!=len(rows):
            raise ValueError('evidence row count mismatch')
        radii=[]; missing=[]
        for i,(intervals,solution) in enumerate(zip(bounds,solutions,strict=True)):
            if intervals is None:
                missing.append(i);continue
            if len(intervals)!=len(nodes):
                raise ValueError('bound node count mismatch')
            for node,interval,value in zip(nodes,intervals,solution['voltages'],strict=True):
                if len(interval)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in interval):
                    raise ValueError('nonfinite or invalid interval')
                lo,hi=interval
                if not lo<=value<=hi:
                    raise ValueError('interval order/representative containment mismatch')
                if node in card['observables']:
                    radii.extend((F(value)-F(lo),F(hi)-F(value)))
        if not missing:
            voltage_error=upper(max(radii,default=F(0)))
            roles['voltage']={'status':'established','basis':'existing solver certificates exported as outward binary64 interval hulls; maximum radius around unchanged returned representative','bound_V':voltage_error,'limits':'certificate is for actual binary64 IR and PWL inputs; transport containment is not independent certificate verification'}
        else:
            roles['voltage']={'status':'unknown','basis':'solver did not export a certificate for all rows','missing_rows':missing}
        known={'accepted_controller_frame','certified_causal_frame','implicit_history_evaluation','stateless_working_point','unknown'}
        if any(o not in known for o in actual_origins):
            raise ValueError('invalid actual sample origin')
        # Only this provenance is already an accepted controller frame. Other
        # paths compute directly at requested times, but the legacy accepted
        # identity must not be enlarged by this adapter.
        origins=['accepted' if o=='accepted_controller_frame' else 'unknown' for o in actual_origins]
        native=bool(origins) and all(o=='accepted' for o in origins)
        if native:
            for role in ('native_counters','native_phase'):
                roles[role]={'status':'established','basis':'unmodified public output voltages from accepted controller frames; no interpolation, rounding or modulo repair'}
        initial=evidence.get('initial_settled') is True and times and times[0]==0 and origins[0]=='accepted'
        # initial_settled alone is after initialization, but a t=0 callback may
        # already have occurred. The original contract requires before callback.
        events=response['transient'].get('events',[])
        def positive_event(e):
            return (isinstance(e,dict) and isinstance(e.get('time'),(int,float)) and e['time']>0
                    and e.get('observation_time_bounds',[e['time'],e['time']])[0]>0
                    and all(t.get('time_bounds',[e['time'],e['time']])[0]>0 for t in e.get('fired_triggers',[])))
        if initial and all(positive_event(e) for e in events):
            roles['native_initial']={'status':'established','basis':'actual initial_settled at raw t=0 accepted frame and every exported callback time strictly positive'}
        else:
            roles['native_initial']={'status':'unknown','basis':'initial_settled does not by itself prove a row before the first sample/cross callback'}
    input_error,input_details=input_curve_bound(card,request)
    roles['inputs']={'status':'established' if input_error is not None else 'unknown',
        'basis':'Fraction exact maximum on union of decimal-card and binary64-request knots and original-domain endpoints; absolute affine difference reaches its maximum at an endpoint',
        'bound_V':input_error,'details':input_details,
        'limits':'continuous mathematical PWL curves, matching original-knot exact_source semantics; representative floating interpolation error is handled separately by output certificate; this is not an ideal-input output-error proof'}
    required=['source','time','voltage','inputs','native_initial']
    if any(n in ('count','na','nb') for n in card['observables']):required.append('native_counters')
    if card['id'] in ('CP-02','CO-VCO-01'):required.append('native_phase')
    return rows,origins,{'roles':roles,'required_roles':required,'missing_roles':[r for r in required if roles[r]['status']!='established'],
                        'time_error_s':time_error,'voltage_error_V':voltage_error,'input_error_V':input_error,
                        'effective_controls':evidence.get('effective_controls') if evidence else None,
                        'actual_sample_origins':evidence.get('sample_origins') if evidence else None}


def adapt(core, condition, work, source_review, output):
    core=Path(core);work=Path(work);source_review=Path(source_review);output=Path(output)
    if output.exists():raise ValueError('output directory must be new')
    if output.resolve().is_relative_to(work.resolve()):raise ValueError('output must be outside actual run directory')
    data=json.loads(core.read_text());card=next(c for c in data['cards'] if c['id']==condition)
    request=json.loads((work/'request.json').read_text())
    paths={'core':core,'condition':work/'condition.json','source_review':source_review,'source':work/'dut.va','request':work/'request.json',
           'times':work/request['requested_times'],'raw':work/'raw-response.json','normalized':work/'observation.json'}
    # Identity is the actual consumed bytes. This creates no execution receipt.
    identities={name:bind(path) for name,path in paths.items()}
    loaded={name:json.loads(path.read_text()) for name,path in paths.items() if name not in ('core','source')}
    if loaded['condition']!=card:
        raise ValueError('actual condition does not equal frozen card')
    if (work/'dut.va').read_text()!=card['source']:
        raise ValueError('actual source does not equal frozen card source')
    rows,origins,report=derive(card,request,loaded['times'],loaded['raw'],loaded['normalized'],loaded['source_review'],
                             core_sha=sha(core),source_sha=sha(work/'dut.va'))
    report.update(schema_version=1,condition=condition,backend='evas',identities=identities,
                  claim='new actual-evidence derivation; preserves previous raw/normalized rows and leaves missing qualifications unknown')
    output.mkdir(parents=True)
    report_path=output/'evidence.json';report_path.write_text(json.dumps(report,separators=(',',':'),allow_nan=False)+'\n')
    certificates={role:{'method':fact['basis'],'artifact_path':str(report_path.resolve()),'sha256':sha(report_path)}
                  for role,fact in report['roles'].items() if fact['status']=='established'}
    q={key:report[key] for key in ('time_error_s','voltage_error_V','input_error_V')}
    q.update(qualified=not report['missing_roles'],source_validated=report['roles']['source']['status']=='established',
             native_initial=report['roles']['native_initial']['status']=='established',input_bounds_qualified=report['roles']['inputs']['status']=='established',
             exact_time_qualified=all(o=='accepted' for o in origins),qualification_evidence=certificates)
    normalized=normalize_observation(card,'evas',rows,origins,q,contract=data['shared_contract'])
    (output/'observation.json').write_text(json.dumps(normalized,separators=(',',':'),allow_nan=False)+'\n')
    return report,normalized


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('core',type=Path);parser.add_argument('condition');parser.add_argument('work',type=Path)
    parser.add_argument('source_review',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();adapt(args.core,args.condition,args.work,args.source_review,args.output)
