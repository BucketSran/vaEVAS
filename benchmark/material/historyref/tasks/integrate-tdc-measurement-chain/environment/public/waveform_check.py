"""Contract-only temporal checker for original integration tasks.

Targets are independently authored event ledgers or algebraic contract values.
This module never reads a reference solution. Time is seconds and voltage volts.
"""
import bisect
import math


def interpolate(rows,t,node):
    times=[row['time'] for row in rows]
    i=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
    a,b=rows[i:i+2]
    if b['time']==a['time']:return b[node]
    return a[node]+(b[node]-a[node])*(t-a['time'])/(b['time']-a['time'])


def pll_expected(time_s, protocol):
    """Closed-form first-order frequency and phase from input events only."""
    t=time_s/1e-9;origin=0.;base=1.;target=1.;phase=0.;high=False;tau=protocol['tau_ns']
    events=sorted([(at,'hop',value) for at,value in protocol['hops']]+[(at,'reset',value) for at,value in protocol['resets']])
    for at,kind,value in events:
        if at>t:break
        dt=at-origin
        current=target+(base-target)*math.exp(-dt/tau)
        integrated=phase+target*dt+(base-target)*tau*(1-math.exp(-dt/tau))
        if kind=='reset':
            high=bool(value);origin=at;base=1.;target=1.;phase=0.
        elif not high:origin=at;base=current;target=value;phase=integrated
    if high:return 1.,0.
    dt=t-origin
    frequency=target+(base-target)*math.exp(-dt/tau)
    phase+=target*dt+(base-target)*tau*(1-math.exp(-dt/tau))
    return frequency,.5+.5*math.sin(2*math.pi*phase)


def evaluate(rows,case,work=None):
    required=set(case['signals'])
    failures=[]
    if len(rows)<2 or any(not required.issubset(row) for row in rows):
        return dict(passed=False,failures=['missing waveform or required signals'])
    if any(not math.isfinite(v) for row in rows for v in row.values()):
        return dict(passed=False,failures=['nonfinite waveform'])
    times=[row['time'] for row in rows]
    if any(a>b for a,b in zip(times,times[1:])) or abs(times[0])>1e-15 or abs(times[-1]-case['stop'])>max(1e-15,case['stop']*1e-8):
        return dict(passed=False,failures=['unordered or incomplete transient'])
    checked=0;worst=0.;bad_windows=0
    for spec in case.get('windows',[]):
        start,end=spec['start'],spec['end'];node=spec['node'];tol=spec['atol']
        # Check every accepted point plus endpoints; a late or transient error
        # inside a required stable interval cannot hide behind a global RMSE.
        values=[interpolate(rows,start,node),interpolate(rows,end,node)]
        values.extend(row[node] for row in rows if start<row['time']<end)
        error=max(abs(v-spec['value']) for v in values);checked+=len(values);worst=max(worst,error/tol)
        if error>tol:
            bad_windows+=1
            if len(failures)<30:failures.append(dict(kind='stable_window',node=node,start=start,end=end,expected=spec['value'],atol=tol,max_error=error))
    edge_counts={}
    for spec in case.get('edges',[]):
        node=spec['node'];level=spec['threshold'];observed=[]
        for a,b in zip(rows,rows[1:]):
            if (a[node]<level<=b[node]) or (a[node]>level>=b[node]):
                t=a['time']+(b['time']-a['time'])*(level-a[node])/(b[node]-a[node])
                if t>=spec.get('start',0):observed.append(t)
        expected=spec['times'];edge_counts[node]={'expected':len(expected),'observed':len(observed)}
        if len(observed)!=len(expected):failures.append(dict(kind='edge_count',node=node,**edge_counts[node]))
        elif any(abs(a-b)>spec['atol'] for a,b in zip(observed,expected)):
            failures.append(dict(kind='edge_time',node=node,expected=expected,observed=observed,atol=spec['atol']))
    for spec in case.get('samples',[]):
        observed=interpolate(rows,spec['t'],spec['node']);error=abs(observed-spec['value']);checked+=1;worst=max(worst,error/spec['atol'])
        if error>spec['atol'] and len(failures)<30:failures.append(dict(kind='sample',**spec,observed=observed))
    if 'pll_protocol' in case:
        protocol=case['pll_protocol'];bad_dynamic=0
        for row in rows:
            if any(abs(row['time']-at*1e-9)<.06e-9 for at,value in protocol['resets']):continue
            frequency,wave=pll_expected(row['time'],protocol)
            for node,value,tol in [('frequency',frequency,.001),('wave',wave,.01)]:
                error=abs(row[node]-value);checked+=1;worst=max(worst,error/tol)
                if error>tol:
                    bad_dynamic+=1
                    if len(failures)<30:failures.append(dict(kind='pll_dynamic',node=node,t=row['time'],expected=value,observed=row[node],atol=tol))
    return dict(passed=not failures,failures=failures,bad_windows=bad_windows,checked_points=checked,worst_normalized_error=worst,edge_counts=edge_counts)
