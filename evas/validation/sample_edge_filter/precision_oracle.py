"""Independent query-phase reference from the original binary64 case inputs.

Exact fractions construct the handwritten stimulus and transition polygon.
Decimal's exponential propagates each affine forcing segment in sequence;
this does not use EVAS's slope-change sum or its Taylor implementation.
The engineering checker and its budgets are unchanged.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as F
import contract as sef


def binary(value):
    return F.from_float(float(value))


def signal(points):
    return [(binary(t*sef.T), binary(v)) for t, v in points]


def sample(points, t):
    for (a, u), (b, v) in zip(points, points[1:]):
        if a <= t <= b:
            return u+(v-u)*(t-a)/(b-a)
    raise ValueError('query outside source')


def rising(points):
    half=F(1, 2)
    return [a+(half-u)*(b-a)/(v-u) for (a,u),(b,v) in zip(points,points[1:]) if u<half<=v]


def polygon(p):
    inputs=signal(sef.INPUT)
    reset=signal(sef.RESET)
    if p['cross']:
        events=sorted(rising(signal(sef.CLOCK))+rising(reset))
    else:
        phase=binary(p['phase']*sef.T)
        period=binary(p['period']*sef.T)
        events=[phase+i*period for i in range(16) if phase+i*period<binary(sef.STOP)]
    value=binary(float(sef.initial(p)))
    start=F(0); slope=F(0); origin=target=value
    points=[(start,value,slope)]
    for event in events:
        new=F(1,4) if p['cross'] and sample(reset,event)>F(1,4) else binary(p['gain'])*sample(inputs,event)+binary(p['bias'])
        if new==target:
            continue
        activation=event+binary(p['delay']*sef.T)
        if slope:
            end=start+(target-value)/slope
            if end<=activation:
                points.append((end,target,F(0)))
                start=end;value=target;slope=F(0)
        current=value+slope*(activation-start)
        origin=(origin if (new-current)*slope>0 else target) if slope else current
        duration=binary((p['rise'] if new>current else p['fall'])*sef.T)
        slope=(new-origin)/duration if new!=current else F(0)
        start=activation;value=current;target=new
        points.append((start,value,slope))
    if slope:
        points.append((start+(target-value)/slope,target,F(0)))
    return points


def filter_value(p, time, digits=80):
    """Closed-form ODE propagation on each affine segment, at one query."""
    def decimal(value):
        return Decimal(value.numerator)/Decimal(value.denominator)
    query=binary(time)
    segments=polygon(p)
    with localcontext() as ctx:
        ctx.prec=digits
        tau=decimal(binary(p['tau']*sef.T))
        value=decimal(segments[0][1])
        for i,(start,forcing,slope) in enumerate(segments):
            if query<=start:
                break
            end=min(query,segments[i+1][0]) if i+1<len(segments) else query
            h=decimal(end-start); u=decimal(forcing); m=decimal(slope)
            value=u+m*h-tau*m+(value-u+tau*m)*(-h/tau).exp()
            if end==query:
                break
        return value


def side(p, time):
    """Require a stable nonzero guard sign at two independent precisions."""
    signs=[]
    for precision in (80,110):
        with localcontext() as ctx:
            ctx.prec=precision
            threshold=Decimal.from_float(p['threshold'])
            guard=filter_value(p,time,precision)-threshold
            if abs(guard)<Decimal('1e-60'):
                raise ValueError('reference phase not separated from zero')
            signs.append(1 if guard>0 else -1)
    if signs[0]!=signs[1]:
        raise ValueError('reference phase did not stabilize')
    return signs[0]
