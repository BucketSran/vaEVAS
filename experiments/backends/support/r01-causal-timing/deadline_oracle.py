"""Prepared independent nominal-root finite answers; no DUT or reference imports."""
from fractions import Fraction as F
from decimal import Decimal as D,localcontext,ROUND_FLOOR,ROUND_CEILING
ROOT=F(1,3);RISE=F(1,100);TAU=F(1,100)
def exp_bounds(x):
 if x==0:return F(1),F(1)
 with localcontext() as ctx:
  ctx.prec=90;ctx.rounding=ROUND_FLOOR;a=D(x.numerator)/D(x.denominator)
  ctx.rounding=ROUND_CEILING;b=D(x.numerator)/D(x.denominator)
  return F(a.exp().next_minus()),F(b.exp().next_plus())
def nominal(label,time):
 # Query times are the original Python binary64 values, not altered rational literals.
 t=F(time) if isinstance(time,float) else F(str(time))
 x=t-ROOT-(F(1,500) if label=='delay_two_instances' else 0)
 y=min(F(1),max(F(0),x/RISE));a=2*y
 if label=='delay_two_instances':return {'u':(3*t,3*t),'y0':(y,y),'y1':(y,y),'d0:a':(a,a),'d1:a':(a,a)}
 out={'u':(3*t,3*t),'y':(y,y),'dut:a':(a,a)}
 if label=='idt_laplace_consumers':
  integral=F(0) if x<=0 else x*x/(2*RISE) if x<RISE else x-RISE/2
  if x<=0:filtered=(F(0),F(0))
  elif x<RISE:
   lo,hi=exp_bounds(-x/TAU);filtered=(2*(x-TAU+TAU*lo)/RISE,2*(x-TAU+TAU*hi)/RISE)
  else:
   lo,hi=exp_bounds(-x/TAU);a0,b0=exp_bounds(-(x-RISE)/TAU)
   filtered=(2+2*lo-2*b0,2+2*hi-2*a0)
  out['dut:i']=(integral,integral);out['dut:f']=filtered
 else:assert label=='same_source_two_fresh'
 return out
