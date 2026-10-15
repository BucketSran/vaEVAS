"""Five frozen next-sync conditions: finite native-row assessment, no fitting."""
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path
import argparse, importlib.util, json, math, hashlib, re
HERE=Path(__file__).resolve().parent
DESIGN=HERE.parents[1]/'design'
ROOT=next(p for p in HERE.parents if (p/'evas/validation/paper').is_dir())
TIERS={'Q1':F('0.0000101'),'Q2':F('0.00000101'),'Q3':F('0.000000101')}
T=F(1,2**20);TT=F('1e-12');CASES={'ramp':('ramp',False,1),'ramp-g1000':('ramp',False,1000),'history':('history',False,1),'filter':('filter',False,1),'filter-interrupt':('filter',True,1)}
def rat(v):
    if isinstance(v,float):
        if not math.isfinite(v):raise ValueError('nonfinite numeric value')
        return F(v)
    return F(str(v))
def add(a,b):return(a[0]+b[0],a[1]+b[1])
def scale(a,k):return(min(a[0]*k,a[1]*k),max(a[0]*k,a[1]*k))
@lru_cache(maxsize=4096)
def expneg(r):
    """Exact alternating series; after 60 terms, next term bounds remainder.
    For 0<=r<=4, terms decrease after k>=4. Partial sum to k=60
    is an upper bound; subtract magnitude of k=61 for lower bound.
    """
    if not 0<=r<=4:raise ValueError('exponential argument outside frozen scope')
    term=F(1);s=term
    for k in range(1,61):term*= -r/k;s+=term
    remainder=abs(term*r/61)
    return (s-remainder,s)
def polynomial(p,x):return sum(v*x**i for i,v in enumerate(p))
def particular(p,x):
    return polynomial(p,x)-sum(i*p[i]*x**(i-1) for i in range(1,len(p)))+sum(i*(i-1)*p[i]*x**(i-2) for i in range(2,len(p)))
def segment(p,start,end,seed):
    at=particular(p,end);c=add(seed,(-particular(p,start),)*2);e=expneg(end-start)
    prod=(min(v*w for v in c for w in e),max(v*w for v in c for w in e))
    return add((at,at),prod)
def reference(case,t,a,b=None):
    kind,interrupt,G=CASES[case];x=t/T;alpha=a/T;beta=b/T if b is not None else None
    h0=F(1,4) if kind=='history' else F(2);h=h0+x
    e=max(F(0),min(F(1),x-alpha))
    if interrupt and x>=beta:e=max(F(0),2*beta-alpha-x)
    out={'h':(h,h),'edge':(e,e),'y':(G*h*e,)*2}
    if kind=='history':out['other']=(-F(1,8)-x/2,)*2
    if kind=='filter':
        f=(F(0),F(0));rise_end=beta if interrupt else alpha+1
        if x>alpha:f=segment([-G*h0*alpha,G*(h0-alpha),F(G)],alpha,min(x,rise_end),f)
        if x>rise_end:
            if interrupt:
                c=2*beta-alpha
                f=segment([G*h0*c,G*(c-h0),F(-G)],beta,min(x,c),f)
                if x>c:f=segment([F(0)],c,x,f)
            else:f=segment([G*h0,F(G)],alpha+1,x,f)
        out['f']=f
    return out

def callbacks_from_log(text):
    # Representation only. Printed times are NOT qualified execution boxes.
    return [{'index':int(i),'time_s':t,'target':int(q),'bounds_s':[t,t]} for i,t,q in re.findall(r'PRODUCT_CALLBACK\s+(\d+)\s+(\S+)\s+(\d+)',text)]

def assess(case,rows,callbacks=None,tier='Q3',proof=None):
    B=TIERS[tier];kind,interrupt,G=CASES[case];proof=proof or {};issues=[];errors=[]
    result={'case':case,'tier':tier,'budget_V':float(B),'scope':'finite native observations only','numerical':{'status':'not_assessed'},'evidence':{'status':'insufficient','issues':issues},'behavior':{'status':'not_assessed','errors':errors},'Q_status':'not_qualified'}
    try:
        required={'h','edge','y','qout','count'}|({'other'} if kind=='history' else set())|({'f'} if kind=='filter' else set())
        if not rows:raise ValueError('empty waveform')
        times=[rat(r['time']) for r in rows]
        values=[{n:rat(r[n]) for n in required} for r in rows]
        if any(t<0 or t>3*T for t in times):raise ValueError('native time outside frozen interval')
        if any(v<=u for u,v in zip(times,times[1:])):raise ValueError('duplicate or unordered native times; phase adapter required')
        if times[0]!=0 or times[-1]!=3*T:issues.append('missing exact start/stop')
        if max((v-u for u,v in zip(times,times[1:])),default=3*T)>T/16:issues.append('incomplete native coverage')
        expected=[(T,1),(F(3,2)*T,0)] if interrupt else [(T,1)]
        if callbacks is None:
            issues.append('missing independent callback execution evidence; nominal history is diagnostic only')
            callbacks=[{'index':i+1,'time_s':float(t),'target':q,'bounds_s':[float(t),float(t)]} for i,(t,q) in enumerate(expected)]
        if len(callbacks)!=len(expected):raise ValueError('missing or duplicate callback inventory')
        centers=[];deltas=[];boxes=[]
        for i,(cb,(nominal,target)) in enumerate(zip(callbacks,expected)):
            if cb['index']!=i+1 or cb['target']!=target:errors.append('callback count/order/target mismatch')
            center=rat(cb['time_s']);lo,hi=map(rat,cb['bounds_s'])
            if not lo<=center<=hi:raise ValueError('callback center outside box')
            if lo<nominal-TT or hi>nominal+TT:errors.append('callback box violates fixed TT')
            centers.append(center);deltas.append(max(center-lo,hi-center));boxes.append((lo,hi))
        if len(boxes)>1 and boxes[0][1]>=boxes[1][0]:errors.append('callback order not proved')
        a=centers[0];b=centers[1] if interrupt else None
        critical=[a,(2*b-a) if interrupt else a+T]+([b] if interrupt else [])
        center_tol=rat(proof.get('native_time_bound_s',0))
        if center_tol<0:raise ValueError('negative native time observation bound')
        for c in critical:
            # Adjacent +/-2ps points are sides, never center evidence.
            # Without qualified native-time rounding proof, require the exact token.
            if min(abs(t-c) for t in times)>center_tol:issues.append('missing actual boundary center: '+str(float(c)))
            if not any(0<c-t<=F('2.1e-12') for t in times) or not any(0<t-c<=F('2.1e-12') for t in times):issues.append('missing actual boundary left/right: '+str(float(c)))
        callback_uncertainty=5*G*(deltas[0]+(2*deltas[1] if interrupt else 0))/T
        time_uncertainty=rat(proof.get('native_time_bound_s',0))*10*G/T
        export_uncertainty=rat(proof.get('native_voltage_bound_V',0))
        if time_uncertainty<0 or export_uncertainty<0:raise ValueError('negative observation uncertainty')
        uncertainty=callback_uncertainty+time_uncertainty+export_uncertainty
        if uncertainty>B/10:issues.append('callback/time/export uncertainty exceeds B/10')
        if not proof.get('callback_execution_qualified'):issues.append('callback producer not externally qualified')
        if not proof.get('native_export_qualified'):issues.append('native export/time representation not externally qualified')
        if proof.get('native_export_qualified') and not all(k in proof for k in ['native_time_bound_s','native_voltage_bound_V']):issues.append('qualified export lacks explicit uncertainty bounds')
        if not proof.get('synthetic_calibration') and (not proof.get('qualification_receipt_sha256') or not proof.get('executed_source_sha256')):issues.append('missing external qualification/source identity receipt')
        maxhi=F(0);maxlo=F(0);worst=None;reference_width=F(0);input_hi=F(0);input_lo=F(0)
        for t,row in zip(times,values):
            ref=reference(case,t,a,b)
            for name,(lo,hi) in ref.items():
                reference_width=max(reference_width,hi-lo)
                actual=row[name];upper=max(abs(actual-lo),abs(actual-hi))+uncertainty
                lower=max(F(0),lo-actual,actual-hi)-uncertainty;lower=max(F(0),lower)
                if upper>maxhi:maxhi=upper;worst={'time_s':float(t),'node':name,'actual_V':float(actual),'reference_bounds_V':[float(lo),float(hi)]}
                maxlo=max(maxlo,lower)
            # Independent factors are inputs to the product. Their output contribution
            # has B/100 budget, including gain; do not hide cancellation in y.
            for name,gain in [('h',G),('edge',5*G)]:
                lo,hi=ref[name];actual=row[name]
                factor_observation=export_uncertainty+rat(proof.get('native_time_bound_s',0))/T
                input_hi=max(input_hi,gain*(max(abs(actual-lo),abs(actual-hi))+factor_observation))
                input_lo=max(input_lo,gain*max(F(0),lo-actual-factor_observation,actual-hi-factor_observation))
            before=sum(hi<t for lo,hi in boxes);after=sum(lo<=t for lo,hi in boxes)
            if not any(abs(row['count']-n)<=F('1e-6') for n in range(before,after+1)):errors.append('native count incompatible with single callback history')
            targets={0}
            if before:targets={expected[before-1][1]}
            if after>before:targets|={expected[k-1][1] for k in range(before+1,after+1)}
            if not any(abs(row['qout']-q)<=F('1e-6') for q in targets):errors.append('native target incompatible with callback phase')
        counts=[round(v['count']) for v in values]
        if any(v-u not in (0,1) for u,v in zip(counts,counts[1:])):errors.append('nonmonotone or skipped native counter')
        for row,n in zip(values,counts):
            state=0 if n==0 else expected[n-1][1] if 0<n<=len(expected) else None
            if state is None or abs(row['qout']-state)>F('1e-6'):errors.append('count and target do not describe one event phase')
        if values[0]['count']!=0 or abs(values[-1]['count']-len(expected))>F('1e-6'):errors.append('initial/final count wrong')
        if reference_width>B/100:issues.append('reference enclosure exceeds B/100')
        num='numerical_error' if maxlo>B or input_lo>B/100 else 'pass' if maxhi<=B and input_hi<=B/100 else 'indeterminate'
        result['numerical']={'status':num,'error_upper_V':float(maxhi),'error_lower_V':float(maxlo),'input_contribution_upper_V':float(input_hi),'input_contribution_lower_V':float(input_lo),'input_contribution_budget_V':float(B/100),'reference_width_V':float(reference_width),'observation_uncertainty_V':float(uncertainty),'worst':worst,'history_basis':'supplied independent callback boxes or explicit nominal hypothesis'}
        result['behavior']['status']='error' if errors else 'pass'
        result['evidence']['status']='complete' if not issues else 'insufficient'
        result['Q_status']='calibration_only' if proof.get('synthetic_calibration') else 'qualified' if not issues and not errors and num=='pass' else 'not_qualified'
        result['status']='behavior_error' if errors else 'numerical_error' if num=='numerical_error' else 'evidence_insufficient' if issues else num
    except (ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError) as e:
        issues.append(str(e));result['status']='invalid_or_incomplete';result['behavior']['status']='not_assessed'
    return result

def read_psf(path,case):
    # Reuse repository's lossless adapter, preserve decimal tokens, no interpolation.
    spec=importlib.util.spec_from_file_location('native_psf',ROOT/'experiments/backends/event-alignment/normalize_psf.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    nodes=['h','edge','y','qout','count']+(['other'] if case=='history' else [])+(['f'] if case.startswith('filter') else [])
    raw=mod.normalize(path,{'voltage_nodes':nodes})
    rows=[{'time':r['time'],**r['voltages']} for r in raw['decimal_tokens']]
    return rows,raw['psf_sha256']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES,required=True);p.add_argument('--psf',type=Path,required=True);p.add_argument('--callbacks',type=Path);p.add_argument('--log',type=Path);p.add_argument('--proof',type=Path);p.add_argument('--tier',choices=TIERS,default='Q3');args=p.parse_args()
    if args.callbacks and args.log:p.error('choose callbacks JSON or log')
    rows,sha=read_psf(args.psf,args.case)
    cb=json.loads(args.callbacks.read_text()) if args.callbacks else callbacks_from_log(args.log.read_text()) if args.log else None
    proof=json.loads(args.proof.read_text()) if args.proof else {}
    if proof.get('synthetic_calibration'):p.error('synthetic qualification is available only in calibration, not PSF CLI')
    if proof.get('native_export_qualified') and proof.get('psf_sha256')!=sha:proof['native_export_qualified']=False
    allowed={hashlib.sha256((DESIGN/args.case/name).read_bytes()).hexdigest() for name in ['dut.va','dut-callback.va']}
    if proof.get('callback_execution_qualified') and proof.get('executed_source_sha256') not in allowed:proof['callback_execution_qualified']=False
    report=assess(args.case,rows,cb,args.tier,proof);report['psf_sha256']=sha;report['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps(report,indent=2,allow_nan=False))
