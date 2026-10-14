"""Independent rational alternating-series enclosures, no DUT imports."""
from fractions import Fraction as F

def add(a,b):return a[0]+b[0],a[1]+b[1]
def sub(a,b):return a[0]-b[1],a[1]-b[0]
def mul(a,b):
 p=[x*y for x in a for y in b];return min(p),max(p)
def expminus(x):
 x=F(x);assert 0<=x<=1
 term=F(1);s=term
 for n in range(1,65):term*=-x/n;s+=term
 nxt=term*(-x/65);return min(s,s+nxt),max(s,s+nxt)
def atansmall(x):
 x=F(x);assert abs(x)<=F(1,2)
 s=sum(((-1)**n*x**(2*n+1)/F(2*n+1) for n in range(96)),F(0));nxt=x**193/F(193)
 return min(s,s+nxt),max(s,s+nxt)
def atan(x):
 x=F(x);assert 0<=x<=1
 if x<=F(1,2):return atansmall(x)
 # pi/4 = 4 atan(1/5) - atan(1/239), Machin identity.
 a=atansmall(F(1,5));b=atansmall(F(1,239));pi4=sub((4*a[0],4*a[1]),b)
 return add(pi4,atansmall((x-1)/(x+1)))
def exact(v):return F(v),F(v)
def expected(label,t):
 t=F(t);assert 0<=t<=1
 if label=='initial_integer':return {k:exact(v) for k,v in {'u':1,'y':5,'z':-3,'w':-1,'d':0}.items()}
 if label=='display_final':return {'u':exact(t),'y':exact(t+(1 if t<F(1,2) else 2 if t<1 else 7))}
 if label=='bsource_chain':return {'x':exact(t),'a':exact(t+F(1,4)),'u':exact(-t-F(1,8)),'y':exact(-3*(t+F(1,8)))}
 if label=='bsource_feedback':return {'u':exact(F(-1,8)),'y':exact(F(-3,8))}
 if label=='rational_bound_state':v=atan(t)
 elif label=='held_exponential':v=sub(exact(1),expminus(t)) if t<=F(1,2) else add(sub(exact(1),expminus(F(1,2))),sub(exact(1),expminus(t-F(1,2))))
 elif label=='selected_feedback':v=sub(exact(1),expminus(2*t)) if t<=F(1,2) else mul(sub(exact(1),expminus(1)),expminus(t-F(1,2)))
 else:raise ValueError(label)
 return {'u':exact(t),'y':v}
def gate(value,interval,budget):
 v=F(value);lo,hi=interval;return max(abs(v-lo),abs(v-hi))<=F(str(budget))
def calibration():
 assert gate(1,exact(1),0) and not gate(1.001,exact(1),'1e-8')
 try:gate(float('nan'),exact(0),1)
 except (ValueError,OverflowError):pass
 else:raise AssertionError('nonfinite accepted')
 assert atan(0)==exact(0) and expminus(0)==exact(1)
 return {'accept':True,'reject':True,'nonfinite_reject':True,'exact_zero':True}
