"""Independent references for the represented PWL inputs and first-order ODE.

PWL evaluation uses rational arithmetic. The ODE closed form uses directed
80-digit Decimal interval operations. Decimal.exp is correctly rounded to
nearest; next_minus/next_plus enclose its result by one decimal ulp. This bound,
not agreement between two precisions, supports the reference qualification.
Numbers from a card denote the exact binary64 values sent to the backends using
round-trip decimal tokens. Output conversion is rounded outward as well.
"""
from bisect import bisect_left
from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_CEILING
from fractions import Fraction
import math

PRECISION = 80


def rational(x):
    return Fraction(x)


def outward(x, up):
    f=float(x)
    if (Fraction(f) < x) if up else (Fraction(f) > x):
        f=math.nextafter(f,math.inf if up else -math.inf)
    return f


def pwl_exact(points, t):
    t=rational(t)
    for (a,y),(b,z) in zip(points,points[1:]):
        a,b,y,z=map(rational,(a,b,y,z))
        if t<=a:return y
        if t<=b:return y+(z-y)*(t-a)/(b-a)
    return rational(points[-1][1])


def pwl_range(points, a, b):
    values=[pwl_exact(points,a),pwl_exact(points,b)]
    values.extend(rational(v) for t,v in points if a<t<b)
    low,high=min(values),max(values)
    lo,hi=outward(low,False),outward(high,True)
    conversion=max(rational(lo)-low,low-rational(lo),rational(hi)-high,high-rational(hi))
    return lo,hi,outward(conversion,True)


def slope_bound(points):
    return outward(max((abs((rational(v)-rational(u))/(rational(b)-rational(a)))
                        for (a,u),(b,v) in zip(points,points[1:])),default=Fraction(0)),True)


class Interval:
    def __init__(self, lo, hi=None):
        self.lo=lo if isinstance(lo,Decimal) else Decimal(lo)
        self.hi=self.lo if hi is None else hi

    @staticmethod
    def pair(op, a, b):
        bounds=[]
        for rounding in (ROUND_FLOOR,ROUND_CEILING):
            with localcontext() as ctx:
                ctx.prec=PRECISION;ctx.rounding=rounding
                vals=[op(x,y) for x in (a.lo,a.hi) for y in (b.lo,b.hi)]
                bounds.append(min(vals) if rounding==ROUND_FLOOR else max(vals))
        return Interval(*bounds)

    def __add__(self,other):return self.pair(lambda a,b:a+b,self,interval(other))
    def __sub__(self,other):return self.pair(lambda a,b:a-b,self,interval(other))
    def __mul__(self,other):return self.pair(lambda a,b:a*b,self,interval(other))
    def __truediv__(self,other):
        other=interval(other)
        if other.lo<=0<=other.hi:raise ValueError('division interval contains zero')
        return self.pair(lambda a,b:a/b,self,other)

    def exp(self):
        with localcontext() as ctx:
            ctx.prec=PRECISION
            return Interval(self.lo.exp().next_minus(), self.hi.exp().next_plus())

    def floats(self):return outward(Fraction(self.lo),False),outward(Fraction(self.hi),True)


def interval(x):return x if isinstance(x,Interval) else Interval(x)


class FirstOrder:
    def __init__(self,card):
        self.tau=interval(card['tau_s'])
        self.points=card['inputs']['u']
        self.times=[t for t,_ in self.points]
        self.states=[interval(card['initial_V'])]
        for (a,u),(b,v) in zip(self.points,self.points[1:]):
            h=interval(b)-interval(a)
            self.states.append(self.segment(interval(u),(interval(v)-interval(u))/h,h,self.states[-1]))

    def segment(self,a,m,h,y0):
        # y = a + m(h-tau) + (y0-a+m*tau) exp(-h/tau).
        return a+m*(h-self.tau)+(y0-a+m*self.tau)*((interval(0)-h)/self.tau).exp()

    def bounds(self,t):
        if t<=self.times[0]:return self.states[0].floats()
        i=max(0,bisect_left(self.times,t)-1)
        if i>=len(self.points)-1:
            a,u=self.points[-1];m=interval(0)
        else:
            a,u=self.points[i];b,v=self.points[i+1]
            m=(interval(v)-interval(u))/(interval(b)-interval(a))
        return self.segment(interval(u),m,interval(t)-interval(a),self.states[i]).floats()


def exact_decimal(x):
    value=Fraction(x)
    digits=max(PRECISION,value.numerator.bit_length()+value.denominator.bit_length()+5)
    with localcontext() as ctx:
        ctx.prec=digits
        result=Decimal(value.numerator)/Decimal(value.denominator)
    if result*Decimal(value.denominator)!=Decimal(value.numerator):
        raise ValueError('binary64 value was not converted exactly')
    return result


def binary_interval(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)):
        raise TypeError('coefficient must be an exact binary64 number')
    if isinstance(x,float) and not math.isfinite(x):
        raise ValueError('non-finite coefficient')
    exact=exact_decimal(x)
    return Interval(exact,exact)


class CoefficientFirstOrder:
    """b0/d0/d1 form on exact binary64 values. Not the v1 Decimal(str) replay policy.

    Initial policy ``dc_equilibrium`` sets y(0) to gain times the first input.
    The segment formula is tau*y' + y = gain*u for a linear input piece.
    """
    def __init__(self,points,b0,d0,d1,*,initial='dc_equilibrium'):
        if initial!='dc_equilibrium':raise ValueError('unsupported initial policy')
        if len(points)<2:raise ValueError('need a PWL segment')
        self.initial=initial
        self.numeric_policy='exact_binary64_directed_interval'
        self.gain=binary_interval(b0)/binary_interval(d0)
        self.tau=binary_interval(d1)/binary_interval(d0)
        self.points=[(binary_interval(t),binary_interval(v)) for t,v in points]
        self.times=[t for t,_ in points]
        self.states=[self.gain*self.points[0][1]]
        for (a,u),(b,v) in zip(self.points,self.points[1:]):
            h=b-a
            self.states.append(self.segment(self.gain*u,self.gain*((v-u)/h),h,self.states[-1]))

    def segment(self,level,slope,h,y0):
        return level+slope*(h-self.tau)+(y0-level+slope*self.tau)*((interval(0)-h)/self.tau).exp()

    def coefficient_decimals(self):
        return {'gain':(self.gain.lo,self.gain.hi),'tau':(self.tau.lo,self.tau.hi)}

    def bounds(self,t):
        if t<=self.times[0]:return self.states[0].floats()
        i=max(0,bisect_left(self.times,t)-1)
        if i>=len(self.points)-1:
            origin,u=self.points[-1]
            level,slope=self.gain*u,self.gain*interval(0)
        else:
            origin,u=self.points[i]
            b,v=self.points[i+1]
            level,slope=self.gain*u,self.gain*((v-u)/(b-origin))
        return self.segment(level,slope,binary_interval(t)-origin,self.states[i]).floats()
