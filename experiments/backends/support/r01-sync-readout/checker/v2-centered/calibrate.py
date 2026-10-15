"""Reproducible synthetic controls using separate Decimal ODE construction."""
from pathlib import Path
from decimal import Decimal as D, localcontext
from copy import deepcopy
import json,hashlib,math
import check
HERE=Path(__file__).resolve().parent
PROOF={'synthetic_calibration':True,'callback_execution_qualified':True,'native_export_qualified':True,'native_time_bound_s':'0','native_voltage_bound_V':'0'}
T=D(1)/D(2**20)
def make(case,offset=D(0)):
    kind,interrupt,G=check.CASES[case];a=T+offset;b=D('1.5')*T+offset if interrupt else None
    cb=[{'index':1,'time_s':str(a),'bounds_s':[str(a),str(a)],'target':1}]
    if interrupt:cb.append({'index':2,'time_s':str(b),'bounds_s':[str(b),str(b)],'target':0})
    times={D(i)*T/64 for i in range(193)}
    for center in [a,(2*b-a) if interrupt else a+T]+([b] if interrupt else []):times.update([center-D('2e-12'),center,center+D('2e-12')])
    rows=[]
    with localcontext() as ctx:
        ctx.prec=90
        alpha=a/T;beta=b/T if b is not None else None
        # Independent ODE power series; no checker polynomial or exp imports.
        # For polynomial p, c0=seed and (k+1)c[k+1]=p[k]-c[k].
        def ode(p,start,end,seed):
            dt=end-start;c=seed;v=c
            # translate p to coefficients at start
            p0=p[0]+(p[1]*start if len(p)>1 else 0)+(p[2]*start*start if len(p)>2 else 0)
            p1=(p[1] if len(p)>1 else D(0))+((2*p[2]*start) if len(p)>2 else 0)
            pp=[p0,p1,p[2] if len(p)>2 else D(0)];power=D(1)
            for k in range(160):
                c=((pp[k] if k<len(pp) else D(0))-c)/D(k+1);power*=dt;v+=c*power
            return v
        for t in sorted(times):
            x=t/T;h=D('.25')+x if kind=='history' else 2+x
            e=max(D(0),min(D(1),x-alpha))
            if interrupt and x>=beta:e=max(D(0),2*beta-alpha-x)
            n=int(t>=a)+(int(t>=b) if interrupt else 0);q=int(t>=a) if not interrupt else int(a<=t<b)
            row={'time':str(t),'h':str(h),'edge':str(e),'y':str(G*h*e),'count':str(n),'qout':str(q)}
            if kind=='history':row['other']=str(-D('.125')-x/2)
            if kind=='filter':
                f=D(0);end=beta if interrupt else alpha+1
                if x>alpha:f=ode([-2*alpha,2-alpha,D(1)],alpha,min(x,end),f)
                if x>end:
                    if interrupt:
                        c=2*beta-alpha;f=ode([2*c,c-2,D(-1)],beta,min(x,c),f)
                        if x>c:f=ode([D(0)],c,x,f)
                    else:f=ode([D(2),D(1)],alpha+1,x,f)
                row['f']=str(f)
            rows.append(row)
    return rows,cb

def main():
    outcomes=[]
    def test(name,case,rows,cb,expected,proof=PROOF,tier='Q3'):
        actual=check.assess(case,rows,cb,tier,proof);passed=actual['status']==expected
        outcomes.append({'id':name,'case':case,'expected':expected,'actual':actual['status'],'calibration_passed':passed,'assessment':actual})
        if not passed:print(name,actual)
    for case in check.CASES:
        rows,cb=make(case);test('correct-'+case,case,rows,cb,'pass')
        shifted,scb=make(case,D('2e-13'));test('legal-offset-'+case,case,shifted,scb,'pass')
        for magnitude,status in [(D('.5'),'pass'),(D(2),'numerical_error')]:
            changed=deepcopy(rows);i=next(i for i,r in enumerate(changed) if D(r['time'])>D('1.4')*T);changed[i]['y']=str(D(changed[i]['y'])+magnitude*D('101e-9'));test('perturb-'+str(magnitude)+'B-'+case,case,changed,cb,status)
        for label,center in [('a',T),('c',D(2)*T)]:
            center_removed=[r for r in deepcopy(rows) if D(r['time'])!=center]
            # Retain both +/-2ps sides. This previously false-passed as center coverage.
            assert any(D(r['time'])==center-D('2e-12') for r in center_removed)
            assert any(D(r['time'])==center+D('2e-12') for r in center_removed)
            test('remove-only-'+label+'-center-'+case,case,center_removed,cb,'evidence_insufficient')
        if check.CASES[case][1]:
            center=D('1.5')*T
            center_removed=[r for r in deepcopy(rows) if D(r['time'])!=center]
            test('remove-only-b-center-'+case,case,center_removed,cb,'evidence_insufficient')
        missing=deepcopy(rows);critical=T
        missing=[r for r in missing if not abs(D(r['time'])-critical)<=D('2.1e-12')];test('missing-boundary-'+case,case,missing,cb,'evidence_insufficient')
        bad=deepcopy(rows);bad[30]['y']='NaN';test('nan-'+case,case,bad,cb,'invalid_or_incomplete')
        test('duplicate-callback-'+case,case,rows,cb+cb[:1],'invalid_or_incomplete')
        test('no-callback-'+case,case,rows,None,'evidence_insufficient',{})
    rows,cb=make('ramp');bad=deepcopy(rows)
    for r in bad:r['y']=str(D(3)*D(r['edge']))
    test('locked-held','ramp',bad,cb,'numerical_error')
    rows,cb=make('history');bad=deepcopy(rows)
    for r in bad:
        if D(r['time'])>T:r['h']=str(D('.25')+(D(r['time'])-T)/T);r['y']=str(D(r['h'])*D(r['edge']))
    test('history-restart','history',bad,cb,'numerical_error')
    rows,cb=make('filter-interrupt');bad=deepcopy(rows)
    for r in bad:
        x=D(r['time'])/T
        if x>D('1.5'):r['edge']=str(max(D(0),D('.5')-D('.5')*(x-D('1.5'))));r['y']=str(D(r['h'])*D(r['edge']))
    test('wrong-interruption','filter-interrupt',bad,cb,'numerical_error')
    bad=deepcopy(rows)
    for r in bad:
        if D(r['time'])>2*T:r['f']='0'
    test('wrong-filter-tail','filter-interrupt',bad,cb,'numerical_error')
    rows,cb=make('ramp');other,ocb=make('ramp',D('2e-13'));bad=deepcopy(rows)
    # A single exact independent a remains in cb; a point from another legal a cannot be fitted individually.
    i=next(i for i,r in enumerate(bad) if D(r['time'])==D('1.5')*T)
    with localcontext() as ctx:
        ctx.prec=70;x=D(bad[i]['time'])/T;bad[i]['y']=str((2+x)*(x-D(ocb[0]['time_s'])/T))
    test('incompatible-pointwise-a','ramp',bad,cb,'numerical_error')
    wide=deepcopy(cb);wide[0]['bounds_s']=[str(T-D('1e-13')),str(T+D('1e-13'))]
    test('wide-callback-box','ramp',rows,wide,'evidence_insufficient')
    tiny=deepcopy(cb);tiny[0]['bounds_s']=[str(T-D('1e-22')),str(T+D('1e-22'))]
    test('nonpoint-small-callback-box','ramp',rows,tiny,'pass')
    bad=deepcopy(rows);bad[100]['qout']='0'
    test('incoherent-count-target','ramp',bad,cb,'behavior_error')
    observed=deepcopy(PROOF);observed['native_voltage_bound_V']='1e-9'
    test('input-export-budget-preserved','ramp',rows,cb,'indeterminate',observed)
    # Small native ASCII fixture exercises existing lossless PSF adapter, no simulator.
    data='HEADER\nVALUE\n'+''.join('"time" '+r['time']+'\n'+''.join('"'+n+'" '+v+'\n' for n,v in r.items() if n!='time') for r in rows)+'END\n'
    psf=HERE/'synthetic-ramp.psfascii';psf.write_text(data)
    parsed,sha=check.read_psf(psf,'ramp');test('reused-psf-adapter','ramp',parsed,cb,'pass')
    result={'status':'pass' if all(o['calibration_passed'] for o in outcomes) else 'fail','controls':len(outcomes),'passed':sum(o['calibration_passed'] for o in outcomes),'not_simulator_results':True,'oracle':'independent 90-digit Decimal ODE Taylor recursion, 160 terms; checker uses exact rational exp enclosure','outcomes':outcomes}
    (HERE/'CALIBRATION.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    sources=[HERE/'check.py',HERE/'calibrate.py',psf,check.ROOT/'experiments/backends/event-alignment/normalize_psf.py',check.DESIGN/'manifest.json']
    (HERE/'IDENTITY.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2)+'\n')
    print(json.dumps({'status':result['status'],'controls':result['controls'],'passed':result['passed']}))
    return 0 if result['status']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
