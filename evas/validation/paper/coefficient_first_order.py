"""Exact-binary64 coefficient form of the first-order reference.

This module is separate from precision_reference.py. That file is hashed by
frozen root-window receipts, so new calibration code does not belong there.
"""
from bisect import bisect_left
from decimal import Decimal, localcontext
from fractions import Fraction
import math

from precision_reference import PRECISION, Interval, interval


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
