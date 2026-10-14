"""Exact polynomial integration from original binary64 source points; rigorous one-pole filter."""
from fractions import Fraction as F
from decimal import Decimal as D,localcontext,ROUND_FLOOR,ROUND_CEILING
import math
BUDGET=F('1e-6');HYPOTHESES=('physical_history',)
A=F(1e-7);E=F(1.002e-7);STOP=F(2e-7);ROOT=(A+E)/2;UP=F(float(ROOT));LO=F(math.nextafter(float(ROOT),-math.inf))
assert LO<ROOT<UP
CASES={
 'third_rise_integral':dict(third=True,reverse=False,nested=False,gain=F(2),old=0,post=1,h=F(3,4),stop=F(1),down='integral',scale=F(1),ic=F(1,8)),
 'endpoint_rise_after_cascade':dict(third=False,reverse=False,nested=False,gain=F(1e7),old=1,post=2,h=UP,stop=STOP,down='integral',scale=F(1e7),ic=F(0)),
 'endpoint_fall_before_cascade':dict(third=False,reverse=True,nested=True,gain=F(1e7),old=1,post=2,h=LO,stop=STOP,down='integral',scale=F(1e7),ic=F(0)),
 'endpoint_rise_separated':dict(third=False,reverse=False,nested=False,gain=F(1e7),old=0,post=1,h=F(1.2e-7),stop=STOP,down='integral',scale=F(1e7),ic=F(0)),
 'third_fall_filter':dict(third=True,reverse=True,nested=True,gain=F(2),old=0,post=1,h=F(3,4),stop=F(1),down='filter',tau=F(1,8),ic=F(0)),
 'endpoint_highgain_safety':dict(third=False,reverse=False,nested=False,gain=F(1e16),old=0,post=1,h=UP,stop=STOP,down='constant',ic=F(0)),
}
def source(c):
 if c['third']:return [(F(0),F(3) if c['reverse'] else F(0)),(F(1),F(0) if c['reverse'] else F(3))]
 x,y=(F(1.8),F(0)) if c['reverse'] else (F(0),F(1.8))
 return [(F(0),x),(A,x),(E,y),(STOP,y)]
def root(c):return F(1,3) if c['third'] else ROOT
def poly(p,t):return sum(v*t**i for i,v in enumerate(p))
def derivative(p):return [i*v for i,v in enumerate(p)][1:]
def antiderivative(p):return [F(0)]+[v/(i+1) for i,v in enumerate(p)]
def source_poly(c,t):
 points=source(c)
 for (a,x),(b,y) in zip(points,points[1:]):
  if a<=t<=b:m=(y-x)/(b-a);return [x-m*a,m]
 raise ValueError('source domain')
def segments(c):
 cuts=sorted(set([F(0),c['stop'],root(c),c['h']]+[t for t,_ in source(c)]));out=[];value=F(0)
 for a,b in zip(cuts,cuts[1:]):
  u=source_poly(c,(a+b)/2);v0,v1=u
  factor=c['gain']*(c['old'] if (a+b)/2<root(c) else c['post']) if (a+b)/2<c['h'] else F(0)
  primitive=antiderivative([factor*(1+v0*v0),factor*2*v0*v1,factor*v1*v1]);primitive[0]=value-poly(primitive,a)
  out.append((a,b,primitive));value=poly(primitive,b)
 return out
SEGMENTS={k:segments(v) for k,v in CASES.items()}
def exp_bounds(x):
 # Decimal.exp is correctly rounded; rational argument is bracketed, then each
 # result is widened one decimal ULP. Monotonicity gives an enclosure.
 with localcontext() as ctx:
  ctx.prec=90;ctx.rounding=ROUND_FLOOR;lo=D(x.numerator)/D(x.denominator)
  ctx.rounding=ROUND_CEILING;hi=D(x.numerator)/D(x.denominator)
  return F(lo.exp().next_minus()),F(hi.exp().next_plus())
def interval_add(a,b):return a[0]+b[0],a[1]+b[1]
def interval_mul(a,b):v=[x*y for x in a for y in b];return min(v),max(v)
def filter_particular(p,tau):
 q=[F(0)]*len(p);d=p;sign=F(1)
 while d:
  for i,v in enumerate(d):q[i]+=sign*v
  d=derivative(d);sign*=-tau
 return q
def expected(case,t,hypothesis):
 if hypothesis!='physical_history':raise ValueError(hypothesis)
 t=F(t);c=CASES[case]
 if not 0<=t<=c['stop']:raise ValueError('oracle domain')
 y=F(0);w=(c['ic'],c['ic'])
 for a,b,p in SEGMENTS[case]:
  if t<a:break
  end=min(t,b);y=poly(p,end)
  if c['down']=='integral':
   ap=antiderivative(p);area=c['scale']*(poly(ap,end)-poly(ap,a));w=interval_add(w,(area,area))
  elif c['down']=='filter':
   q=filter_particular(p,c['tau']);qa=poly(q,a);qe=poly(q,end)
   w=interval_add((qe,qe),interval_mul((w[0]-qa,w[1]-qa),exp_bounds(-(end-a)/c['tau'])))
  if t<=b:break
 u=poly(source_poly(c,t),t);z=F(t>=c['h'])
 return {'u':(u,u),'y':(y,y),'z':(z,z),'w':w}
