"""Independent public-port checks for extension/integration tasks.

Expected samples and windows are frozen in cases.json, never extracted from
reference source. All required cases must pass the fixed backend separately.
"""
import bisect
import math
import statistics


def at(rows, name, t):
    times=[r['time'] for r in rows]
    if not times or t<times[0] or t>times[-1]:
        raise ValueError(f'waveform does not cover {t:g}')
    j=bisect.bisect_left(times,t)
    if j<len(times) and times[j]==t:return float(rows[j][name])
    i=j-1
    a=float(rows[i][name]);b=float(rows[j][name])
    return a+(b-a)*(t-times[i])/(times[j]-times[i])


def edges(rows,name,lo,hi,vth=.45):
    out=[]
    for a,b in zip(rows,rows[1:]):
        va=float(a[name]);vb=float(b[name])
        if va<vth<=vb:
            t=a['time']+(b['time']-a['time'])*(vth-va)/(vb-va)
            if lo<=t<=hi:out.append(t)
    return out


def divider_metrics(rows, window):
    lo,hi=window['window'];n=window['divider_n']
    d=edges(rows,'dco',lo,hi);f=edges(rows,'fb',lo,hi);r=edges(rows,'ref',lo,hi)
    frequency=1/statistics.mean([b-a for a,b in zip(f,f[1:])])
    ref_frequency=1/statistics.mean([b-a for a,b in zip(r,r[1:])])
    period=statistics.mean([b-a for a,b in zip(d,d[1:])])
    tolerance=window.get('divider_edge_tolerance',500e-12)
    indices=[min(range(len(d)),key=lambda i:abs(d[i]-t)) for t in f[1:-1]]
    delays=[abs(d[i]-t) for i,t in zip(indices,f[1:-1])]
    spacing=[b-a for a,b in zip(indices,indices[1:])]
    ok=bool(spacing) and all(x==n for x in spacing) and max(delays)<=tolerance
    ok=ok and abs(frequency-ref_frequency)<=window.get('feedback_frequency_tolerance',100e3)
    return {'divider_n':n,'feedback_frequency':frequency,'reference_frequency':ref_frequency,
            'dco_edge_spacing':sorted(set(spacing)),'maximum_edge_delay':max(delays),'passed':ok}


def lock_metrics(rows, contract):
    """Reconstruct eligibility from clocks and public coarse-count contract.

    Candidate code, valid and lock do not determine eligibility. Pairing uses
    actual ref/fb edges, quantized by the public TDC specification. The immutable
    coarse readiness is rederived from actual DCO counts in 16-reference windows.
    """
    import heapq
    first=rows[0]['time'];last=rows[-1]['time'];events=[];serial=0
    times=[row['time'] for row in rows]
    def sample(name,t):
        j=bisect.bisect_left(times,t)
        if j<len(times) and times[j]==t:return float(rows[j][name])
        i=j-1;a=float(rows[i][name]);b=float(rows[j][name])
        return a+(b-a)*(t-times[i])/(times[j]-times[i])
    def push(t,kind,data=None):
        nonlocal serial
        serial+=1;heapq.heappush(events,(t,serial,kind,data))
    for kind in ['dco','ref','fb','rst']:
        for t in edges(rows,kind,first,last):push(t,kind)
    for name,threshold in [('fine_enable',.45),('target',3.5)]:
        for a,b in zip(rows,rows[1:]):
            va=a[name];vb=b[name]
            if (va<threshold<=vb) or (va>threshold>=vb):
                push(a['time']+(b['time']-a['time'])*(threshold-va)/(vb-va),'invalidate')
    cycles=0;refs=0;good=0;ready=False;previous_n=3;qualified=0;pending={};last_pair=None
    checks=[];positive=0;negative=0
    lsb=contract['pair_lsb'];timeout=contract['timeout'];settle=contract['settle']
    def check(t,expected,reason):
        nonlocal positive,negative
        observe=t+settle+contract.get('observation_margin',0)
        if observe<=last:
            observed=sample('lock',observe);ok=abs(observed-(.9 if expected else 0))<=.01
            positive+=int(expected);negative+=int(not expected)
            checks.append({'time':observe,'expected':.9 if expected else 0,'observed':observed,'reason':reason,'passed':ok})
    while events:
        t,_,kind,data=heapq.heappop(events)
        if kind=='dco':cycles+=1;continue
        if kind=='rst':
            cycles=0;refs=0;good=0;ready=False;qualified=0;pending={};last_pair=None;check(t,False,'reset');continue
        if kind=='invalidate':
            qualified=0;pending={};last_pair=None;check(t,False,'mode or retune');continue
        if kind=='timeout':
            name,stamp=data
            if pending.get(name)==stamp:
                pending={};qualified=0;check(t,False,'missing counterpart')
            continue
        if kind=='watchdog':
            if last_pair==data:
                qualified=0;check(t,False,'no fresh pair')
            continue
        n=int(sample('target',t)+.5)
        reset=sample('rst',t)>.45
        enabled=sample('fine_enable',t)>.45
        if kind=='ref':
            if reset or n!=previous_n:
                cycles=0;refs=0;good=0;ready=False;previous_n=n
            else:
                refs+=1
                if refs==16:
                    good=good+1 if abs(16*n-cycles)<=1 else 0
                    ready=ready or good>=3;refs=0;cycles=0
        if reset:pending={};qualified=0;continue
        other='fb' if kind=='ref' else 'ref'
        if kind in pending:
            qualified=0;check(t,False,'repeated same edge')
        pending[kind]=t
        if other in pending:
            delta=pending['fb']-pending['ref']
            q=math.copysign(math.floor(abs(delta)/lsb+.500001),delta)
            q=max(-31,min(31,q));phase=abs(q*lsb)
            qualified=qualified+1 if enabled and ready and phase<=contract['phase_limit'] else 0
            pending={};last_pair=t;push(t+contract.get('fresh_pair_timeout',150e-9),'watchdog',t)
            check(t,qualified>=contract['consecutive'],'real completed pair')
        else:push(t+timeout,'timeout',(kind,t))
    ok=bool(checks) and all(c['passed'] for c in checks)
    if contract.get('require_positive',True):ok=ok and positive>0
    recovery=[any(c['expected']>.45 and lo<=c['time']<=hi for c in checks)
              for lo,hi in contract.get('positive_windows',[])]
    ok=ok and all(recovery)
    return {'lock_qualification':checks,'positive_checks':positive,'negative_checks':negative,
            'positive_windows':recovery,'passed':ok}


def evaluate(rows,case,work):
    try:
        if not rows or any(not math.isfinite(float(v)) for r in rows for v in r.values()):
            raise ValueError('missing/non-finite waveform')
        if any(b['time']<=a['time'] for a,b in zip(rows,rows[1:])):
            raise ValueError('nonmonotone time')
        metrics=[]
        if case['kind'] in ('tdc','multichannel','actuator'):
            for check in case['checks']:
                t=check['time']
                for name,expected in check.items():
                    if name=='time':continue
                    observed=at(rows,name,t)
                    tol=case.get('tolerances',{}).get(name,case.get('code_tol',.01))
                    ok=abs(observed-expected)<=tol
                    metrics.append({'signal':name,'time':t,'observed':observed,'expected':expected,'tolerance':tol,'passed':ok})
            for interval in case.get('hold_windows',[]):
                name=interval['signal'];lo,hi=interval['window'];expected=interval['value']
                values=[float(r[name]) for r in rows if lo<=r['time']<=hi]
                ok=bool(values) and max(abs(v-expected) for v in values)<=interval.get('tolerance',.01)
                metrics.append({'signal':name,'window':[lo,hi],'passed':ok})
        elif case['kind']=='pll':
            for window in case['windows']:
                lo,hi=window['window']
                d=edges(rows,'dco',lo,hi);f=edges(rows,'fb',lo,hi);r=edges(rows,'ref',lo,hi)
                if len(d)<3 or len(f)<3 or len(r)<3:raise ValueError('insufficient real clock edges')
                df=1/statistics.mean([b-a for a,b in zip(d,d[1:])])
                target=window['frequency'];tol=window['frequency_tolerance']
                phase=[min(abs(te-re) for re in r) for te in f[1:-1]]
                max_phase=max(phase)
                ok=abs(df-target)<=tol and max_phase<=window['phase_tolerance']
                metrics.append({'window':[lo,hi],'frequency':df,'target':target,'max_phase':max_phase,'passed':ok})
                if 'divider_n' in window:metrics.append(divider_metrics(rows,window))
            if 'lock_contract' in case:metrics.append(lock_metrics(rows,case['lock_contract']))
            for check in case.get('checks',[]):
                for name,expected in check.items():
                    if name=='time':continue
                    observed=at(rows,name,check['time'])
                    metrics.append({'signal':name,'observed':observed,'expected':expected,'passed':abs(observed-expected)<=.01})
            for effect in case.get('effects',[]):
                lo,hi=effect['window'];vals=[r[effect['signal']] for r in rows if lo<=r['time']<=hi]
                ok=bool(vals) and max(vals)-min(vals)>=effect['minimum_span']
                metrics.append({'effect':effect['signal'],'passed':ok})
        else:raise ValueError('unknown integration case kind')
        return {'passed':bool(metrics) and all(m['passed'] for m in metrics),'metrics':metrics}
    except (KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError) as e:
        return {'passed':False,'evidence_error':str(e)}
