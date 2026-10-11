"""Independent finite contract for nearby timer forced points.

The existing .3 / (.1+.2) counter retains its 1 us timer tolerance. New
continuous consumers use an explicit 1 ps tolerance and a fixed 1 uV voltage
budget, chosen before reference execution. No event-window rows are dropped.
"""
from fractions import Fraction as F
import math

BUDGET_V = 1e-6
STOP = 1.
STROBES = [0., .05, .1, .2, math.nextafter(.3, -math.inf), .3,
           math.nextafter(.3, math.inf), .325, .35, .4, .5, .6, .7, .8, .9, 1.]

def source(held=False, chain=False):
    declaration = 'real p; ' if held else ''
    initialization = 'p=0.2; ' if held else ''
    period = 'p' if held else '0.2'
    tolerance = '1e-12' if chain else '1e-6'
    extra = ("V(h,r)<+0.01*a+0.1*b; V(e,r)<+transition(0.01*a+0.1*b,0,0.05); "
             "V(f,r)<+laplace_nd(V(e,r),'{1},'{1,0.05}); "
             "V(i,r)<+idt(V(h,r),0);" if chain else '')
    return ('`include "disciplines.vams"\n'
            'module m(u,y,r); input u; output y; inout r; electrical u,y,r; '
            + ('electrical h,e,f,i; ' if chain else '')
            + declaration + 'integer a,b; analog begin '
            '@(initial_step) begin ' + initialization + 'a=0; b=0; end '
            '@(timer(0.3,0,' + tolerance + ')) a=1; '
            '@(timer(0.1,' + period + ',' + tolerance + ')) b=b+1; '
            'V(y,r)<+a+10*b; ' + extra + ' end endmodule\n')

CASES = [dict(id='fixed', held=False, chain=False, tt=1e-6),
         dict(id='held', held=True, chain=False, tt=1e-6),
         dict(id='chain', held=False, chain=True, tt=1e-12)]


def clocks():
    return [(F.from_float(.3), 1., .01)] + [
        (F.from_float(.1) + k*F.from_float(.2), 10., .1) for k in range(5)]


def ramp(t):
    return min(1., max(0., t/.05))


def filtered_ramp(t):
    if t <= 0: return 0.
    if t < .05: return (t + .05*math.expm1(-t/.05))/.05
    return 1. - math.exp(-(t-.05)/.05)*(-math.expm1(-1.))


def continuous(t, key):
    response = {'e':ramp, 'f':filtered_ramp, 'i':lambda x:max(0., x)}[key]
    return sum(delta*response(t-float(clock)) for clock, _, delta in clocks())


def assess(case, rows):
    failures=[]; maxima={k:0. for k in (['e','f','i'] if case['chain'] else [])}
    seen=[]
    for row in rows:
        t=row['time']; seen.append(t); q=F.from_float(t); tt=F.from_float(case['tt'])
        possible={0.}
        for clock,weight,_ in clocks():
            if clock+tt < q:possible={v+weight for v in possible}
            elif clock-tt <= q:possible|={v+weight for v in possible}
        value=row['y']
        if not math.isfinite(value) or not any(abs(value-v)<=BUDGET_V for v in possible):
            failures.append(dict(time=t,node='y',value=value,allowed=sorted(possible)))
        if case['chain']:
            for key in maxima:
                error=abs(row[key]-continuous(t,key));maxima[key]=max(maxima[key],error)
                if not math.isfinite(row[key]) or error>BUDGET_V:
                    failures.append(dict(time=t,node=key,error_V=error))
            # y and h observe the same a,b. Even within an event window an
            # intermediate h or a phase inconsistent with y is impossible.
            paired_states=[v for v in possible if abs(value-v)<=BUDGET_V]
            if not math.isfinite(row['h']) or not any(
                    abs(row['h']-.01*v)<=BUDGET_V for v in paired_states):
                failures.append(dict(time=t,node='h',value=row['h'],
                                     allowed=[.01*v for v in sorted(paired_states)]))
    if not rows or seen[-1] != STOP or abs(rows[-1]['y']-51)>BUDGET_V:
        failures.append(dict(reason='missing endpoint or wrong final event counts'))
    # All declared interior observation neighborhoods must be present. This
    # does not rename exported times or prove exact strobe hits for Spectre.
    missing=[t for t in STROBES[1:-1] if not any(abs(s-t)<=16*math.ulp(STOP) for s in seen)]
    if missing:failures.append(dict(missing_neighborhoods=missing))
    return dict(status='pass' if not failures else 'fail', points=len(rows),
                maximum_nominal_error_V=maxima, failures=failures[:20],
                failure_count=len(failures), exact_requested_hits=[t for t in STROBES if t in seen])
