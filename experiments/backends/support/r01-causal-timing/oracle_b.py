"""Independent closed-form N09b answers. No EVAS or Spectre readback."""
from fractions import Fraction as F
from decimal import Decimal as D,localcontext,ROUND_FLOOR,ROUND_CEILING
BUDGET=F('1e-8');HYPOTHESES=('closed_form',)
def exp_bounds(x):
 if x==0:return F(1),F(1)
 with localcontext() as ctx:
  ctx.prec=90;ctx.rounding=ROUND_FLOOR;lo=D(x.numerator)/D(x.denominator)
  ctx.rounding=ROUND_CEILING;hi=D(x.numerator)/D(x.denominator)
  return F(lo.exp().next_minus()),F(hi.exp().next_plus())
def z_bounds(t,u):
 # z'=(1-z)/(1+u*u), z(0)=1/4; solve separation of variables.
 a,b=exp_bounds(-t/(1+u*u));return 1-F(3,4)*b,1-F(3,4)*a
def ramp(t):return min(F(1),max(F(0),4*(t-F(1,4))))
def expected(case,t,hypothesis):
 if hypothesis!='closed_form':raise ValueError('hypothesis')
 t=F(t)
 if not 0<=t<=1:raise ValueError('oracle domain')
 r=ramp(t)
 if case=='two_instances_chain':
  return dict(u=(F(1),F(1)),v=(F(2),F(2)),y0=(r,r),z0=z_bounds(t,F(1)),y1=(r,r),z1=z_bounds(t,F(2)))
 y=(r,r)
 if case=='math_only_exp':
  lo,hi=exp_bounds(F(2));y=(r+lo,r+hi)
 elif case not in ['bound_only_affine','inactive_bound']:raise ValueError('case')
 return dict(u=(F(1),F(1)),y=y,z=z_bounds(t,F(1)))
