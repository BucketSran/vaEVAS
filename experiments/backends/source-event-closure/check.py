"""Independent piecewise-integral oracle for the frozen switched integrator."""
from fractions import Fraction as Q
import math


def area(points, time):
    t=Q(time); value=Q(0)
    for (a,u),(b,v) in zip(points,points[1:]):
        a,b,u,v=map(Q,(a,b,u,v)); end=min(t,b)
        if end>a:
            value+=(end-a)*(2*u+(v-u)*(end-a)/(b-a))/2
    return value


def expected(case, time):
    t=Q(time); tau=Q(.1)+Q(.2)
    total=area(case['inputs'],t)
    active=max(Q(0),total-area(case['inputs'],tau))
    charge=active if active<Q(.002) else 2*active-Q(.002)
    z=case['polarity']*charge
    w=total+max(Q(0),t-tau)
    return dict(y=float(z+w),z=float(z),w=float(w),
                count=int(t>=Q(.1))+int(t>=tau),flag=int(active>=Q(.002)),
                mark=int(t>=Q(.30000000000000004)))


def event_times(case, stop):
    tau=Q(.1)+Q(.2);target=area(case['inputs'],tau)+Q(.002)
    lo,hi=tau,Q(stop)
    for _ in range(100):
        mid=(lo+hi)/2
        if area(case['inputs'],mid)<target:lo=mid
        else:hi=mid
    return [.1,float(tau),.30000000000000004,float((lo+hi)/2)]


def assess(case, rows, contract):
    budget=contract['acceptance']['voltage_absolute_V']
    window=contract['acceptance']['event_window_s']
    events=event_times(case,contract['stop'])
    bad=[];boundary=[];max_error=0.
    for i,row in enumerate(rows):
        time=row['time']
        if not math.isfinite(time) or not 0<=time<=contract['stop']:
            bad.append(dict(row=i,reason='outside requested time domain'));continue
        answer=expected(case,time)
        near=any(abs(time-t)<=window for t in events)
        for node,value in answer.items():
            actual=row['voltages'].get(node)
            if actual is None or not math.isfinite(actual):
                bad.append(dict(row=i,node=node,reason='missing or nonfinite voltage'));continue
            if node in ('count','flag','mark'):
                if near:
                    boundary.append(dict(row=i,time=time,node=node,actual=actual,expected=value))
                elif actual!=value:
                    bad.append(dict(row=i,time=time,node=node,actual=actual,expected=value))
            else:
                error=abs(actual-value);max_error=max(max_error,error)
                if error>budget:bad.append(dict(row=i,time=time,node=node,error_V=error))
    missing=[t for t in contract['times'] if not any(row['time']==t for row in rows)]
    return dict(numerical='F' if bad else ('P' if rows else 'I'),coverage='I' if missing else 'P',
                failures=bad,missing_times=missing,boundary_observations=boundary,max_voltage_error_V=max_error)
