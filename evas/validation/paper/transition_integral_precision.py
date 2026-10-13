"""EC05-Q-v2: interrupted edge area with one observed callback history.

The old EC05-v1 support probe and its results are left unchanged.  Here the
actual callback times a,b select a reference, not the DUT voltage values.
"""
from decimal import Decimal as D, localcontext
import math
import re
import precision_breadth_composition as old

TIERS={'Q1':10.1e-6,'Q2':1.01e-6,'Q3':101e-9}
PROFILES={'Q1':'base','Q2':'both','Q3':'deep'}


def dec(x): return D.from_float(x) if isinstance(x,float) else D(x)


def card():
    original=next(c for c in old.cards() if c['id']=='EC05-v1')
    return {**original,'id':'EC05-Q-v2','ancestor':'EC05-v1','support_probe_only':False,
            'criterion':'independent interrupted-ramp area; original source retained',
            'times':[float(i)*original['unit_s']/64 for i in range(193)]}


def trace_source(source):
    marker='n0=n0+1; end'
    if source.count(marker)!=2: raise ValueError('unexpected original event bodies')
    return source.replace(marker,'n0=n0+1; $strobe("EDGE_AREA %0d %.17g %.17g",n0,$abstime,q); end')


def callbacks(raw, backend):
    if backend=='spectre':
        return [dict(index=int(i),time_s=float(t),target=float(v),
                     bounds=[math.nextafter(float(t),-math.inf),math.nextafter(float(t),math.inf)])
                for i,t,v in re.findall(r'EDGE_AREA\s+(\d+)\s+(\S+)\s+(\S+)',raw)]
    names=raw['transient']['state_names']; qi=names.index('dut:q');ni=names.index('dut:n0')
    result=[]
    for e in raw['transient']['events']:
        if e['before'][ni]==e['after'][ni]:continue
        t=e['time'];bounds=e.get('observation_time_bounds')
        if bounds is None and e['kind'] in ('timer','held_timer'):
            # IR19 transient.rs serializes this field only for nonpoint
            # accepted observation windows. Missing timer field means [t,t];
            # nextafter adds conservative serialization slack. This rule does
            # not apply to cross and requires a qualified source/kernel chain.
            bounds=[math.nextafter(t,-math.inf),math.nextafter(t,math.inf)]
        result.append(dict(index=e['after'][ni],time_s=t,target=e['after'][qi],bounds=bounds))
    return result


def reference(time, a, b, unit):
    """Two triangle areas. Reversal uses old destination: slope -1/T."""
    t,a,b,T=map(dec,(time,a,b,unit));d=b-a;end=b+2*d;ic=dec(.1)
    if t<=a:return {'edge_v':D(0),'y':ic,'n':D(0)}
    if t<b:return {'edge_v':2*(t-a)/T,'y':ic+((t-a)/T)**2,'n':D(1)}
    if t<end:
        h=t-b
        return {'edge_v':(2*d-h)/T,'y':ic+(d*d+2*d*h-h*h/2)/(T*T),'n':D(2)}
    return {'edge_v':D(0),'y':ic+3*(d/T)**2,'n':D(2)}


def assess(c, rows, events, tier):
    B=TIERS[tier];result=dict(status='evidence_insufficient',budget_V=B,tier=tier,
        criterion='EC05-Q-v2',claim='finite native observations and mandatory boundaries, not full-time proof')
    T=c['unit_s'];stop=c['stop_s'];u=16*math.ulp(stop)
    if not rows or any(any(type(r.get(k)) not in (float,int) or not math.isfinite(r[k]) for k in ['time','edge_v','y','n']) for r in rows):
        return {**result,'reason':'missing/nonfinite waveform'}
    ts=[r['time'] for r in rows]
    if abs(ts[0])>u or abs(ts[-1]-stop)>u or any(b<=a for a,b in zip(ts,ts[1:])) or max(b-a for a,b in zip(ts,ts[1:]))>T/16+u:
        return {**result,'reason':'incomplete or duplicate/unordered native coverage'}
    if [e.get('index') for e in events]!=[1,2]:return {**result,'reason':'missing/extra callback inventory'}
    for e,nominal,target in zip(events,[T,1.25*T],[1,0]):
        t=e.get('time_s');box=e.get('bounds')
        if not isinstance(t,(int,float)) or not math.isfinite(t) or not box or len(box)!=2 or not all(math.isfinite(v) for v in box) or not box[0]<=t<=box[1]:
            return {**result,'reason':'missing actual callback time enclosure'}
        if box[0]<nominal-1e-10-u or box[1]>nominal+1e-10+u or e['target']!=target:
            return {**result,'status':'behavior_error','reason':'callback violates original timer or target rule'}
    a,b=[e['time_s'] for e in events]
    if not 0<b-a<T/2:return {**result,'status':'behavior_error','reason':'not the specified interrupted rising edge'}
    with localcontext() as ctx:
        ctx.prec=80
        # |de/da|<=2/T, |de/db|<=3/T. Over d<T/2 the integral
        # derivatives are <=3/T; 6/T safely bounds each, including branches.
        delta=sum(max(abs(dec(e['bounds'][0])-dec(e['time_s'])),abs(dec(e['bounds'][1])-dec(e['time_s']))) for e in events)
        uncertain=6*delta/dec(T)
        if uncertain>dec(B/10):return {**result,'reason':'unresolved callback influence','uncertainty_V':float(uncertain)}
        end=3*b-2*a;boundaries=[a,b,end]
        for t in boundaries:
            if min(abs(s-t) for s in ts)>2.1e-12+u or not any(0<t-s<=2.1e-12+u for s in ts) or not any(0<s-t<=2.1e-12+u for s in ts):
                return {**result,'reason':'missing center/left/right critical observation','boundary_s':t}
        upper=lower=D(0);maxima={};worst=None
        for r in rows:
            ref=reference(r['time'],a,b,T)
            near=[e for e in events if e['bounds'][0]-u<=r['time']<=e['bounds'][1]+u]
            if near:
                # A native event row may be the pre or post phase within the
                # serialized callback box; continuous channels keep one history.
                allowed={dec(e['index']) for e in near}|{dec(e['index']-1) for e in near}
                ref['n']=min(allowed,key=lambda n:abs(n-dec(r['n'])))
            for n,v in ref.items():
                conversion=abs(dec(float(v))-v)+dec(8*math.ulp(max(1.,abs(float(v)))))
                residual=abs(dec(r[n])-v);hi=residual+uncertain+conversion;lo=max(D(0),residual-uncertain-conversion)
                maxima[n]=max(maxima.get(n,D(0)),hi);lower=max(lower,lo)
                if hi>upper:upper=hi;worst=dict(time_s=r['time'],node=n,actual_V=r[n],reference_V=float(v))
        return {**result,'status':'pass' if upper<=dec(B) else 'numerical_error' if lower>dec(B) else 'evidence_insufficient',
                'error_upper_V':float(upper),'error_lower_V':float(lower),'maximum_errors_V':{n:float(v) for n,v in maxima.items()},
                'callback_history_uncertainty_V':float(uncertain),'callbacks':events,'worst':worst}
