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
