"""Proposed N09 A+B acceptance fixtures. No production modifications or hidden grading."""
from fractions import Fraction as F
TIMES=[0.,.125,.25,.28125,.3125,.34375,.375,.5]
HEADER='`include "disciplines.vams"\nmodule m(u,s,x,a,y,g); input u,s; output x,a,y,g; electrical u,s,x,a,y,g; real readv; '
TAIL=' end endmodule\n'
Q='integer q; analog begin @(initial_step) q=0; @(timer(0.25)) q=1; '
G='transition(q,0,0.125)'
H='idt(1+V(u)*V(u),0.25)'
def source(body,event=True):return HEADER+(Q if event else 'analog begin ')+body+TAIL
def h(t):t=F(t);return F(1,4)+t+t**3/3
def gate(t):return max(F(0),min(F(1),(F(t)-F(1,4))/F(1,8)))
def expected(t,kind):
 t=F(t);g=gate(t);x=h(t)
 if kind=='isolation':return {'x':x,'a':F(0),'y':F(0),'g':F(1)}
 if kind=='linear_isolation':return {'x':F(1,4)+t,'a':F(0),'y':F(0),'g':F(1)}
 if kind=='static_constant':return {'x':2+t,'a':F(0),'y':2+t,'g':F(1)}
 if kind=='static_event':return {'x':2+t,'a':F(0),'y':(2+t)*g,'g':g}
 if kind=='branch':x+=F(1,8)
 if kind=='two_state':return {'x':x,'a':1+2*t,'y':(x+1+2*t)*g,'g':g}
 if kind=='alias':return {'x':x,'a':2*x,'y':2*x*g,'g':g}
 if kind=='source_select':return {'x':x,'a':F(0),'y':(x if t<F(5,16) else 2*x)*g,'g':g}
 if kind=='held_select':return {'x':x,'a':F(0),'y':(x if t<F(1,4) else 2*x)*g,'g':g}
 return {'x':x,'a':F(0),'y':x*g,'g':g}
# Explicit a=0/y=0 equations avoid dangling declared output nodes in positive fixtures.
CASES=[
 dict(name='linear_idt_unrelated_transition_no_events',kind='linear_isolation',positive=True,source=source('V(x)<+idt(1,0.25); V(g)<+transition(1,0,0.125); V(a)<+0;V(y)<+0;',False)),
 dict(name='nonlinear_idt_unrelated_transition_no_events',kind='isolation',positive=True,source=source(f'V(x)<+{H}; V(g)<+transition(1,0,0.125);V(a)<+0;V(y)<+0;',False)),
 dict(name='static_node_coefficient_no_events',kind='static_constant',positive=True,source=source('V(x)<+2+V(u); V(y)<+V(x)*transition(1,0,0.125);V(g)<+transition(1,0,0.125);V(a)<+0;',False)),
 dict(name='static_node_timed_readout',kind='static_event',positive=True,source=source(f'V(x)<+2+V(u); V(y)<+V(x)*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='dynamic_node_timed_readout',kind='dynamic',positive=True,source=source(f'V(x)<+{H};V(y)<+V(x)*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='interleaved_operator_indices',kind='two_state',positive=True,source=source(f'V(g)<+{G};V(x)<+{H};V(a)<+idt(2,1);V(y)<+(V(x)+V(a))*{G};')),
 dict(name='dynamic_same_branch_sum',kind='branch',positive=True,source=source(f'V(x)<+{H};V(x)<+0.125;V(y)<+V(x)*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='dynamic_alias_chain',kind='alias',positive=True,source=source(f'V(x)<+{H};V(a)<+2*V(x);V(y)<+V(a)*{G};V(g)<+{G};')),
 dict(name='source_predicate_readout',kind='source_select',positive=True,source=source(f'V(x)<+{H};if(V(s)<0.3125) readv=V(x); else readv=2*V(x); V(y)<+readv*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='held_predicate_readout',kind='held_select',positive=True,source=source(f'V(x)<+{H};if(q<1) readv=V(x); else readv=2*V(x); V(y)<+readv*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='timed_output_feedback',positive=False,reason='timed readout reaches idt input; out of minimal feedforward slice',source=source(f'V(x)<+idt(1+V(y),0.25);V(y)<+V(x)*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='alias_return_feedback',positive=False,reason='readout to alias to idt forms feedback despite forward-looking output chain',source=source(f'V(x)<+idt(1+V(a),0.25);V(a)<+2*V(y);V(y)<+V(x)*{G};V(g)<+{G};')),
 dict(name='inactive_arm_feedback',positive=False,reason='all-branch union must retain hidden output feedback',source=source(f'V(x)<+idt(V(s)<10?1:V(y),0.25);V(y)<+V(x)*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='internal_voltage_predicate',positive=False,reason='predicate depends on internal node, beyond source/held admission',source=source(f'V(x)<+{H};if(V(x)<1) readv=V(x); else readv=2*V(x); V(y)<+readv*{G};V(g)<+{G};V(a)<+0;')),
 dict(name='floating_branch_partition',positive=False,reason='two unknown branch endpoints excluded by first partition contract',source=source(f'V(x,a)<+{H};V(a)<+0.125;V(y)<+V(x)*{G};V(g)<+{G};')),
 dict(name='same_branch_hidden_timed_feedback',positive=False,reason='second contribution on same branch cannot be omitted',source=source(f'V(x)<+idt(1-V(x),0.25);V(x)<+V(y);V(y)<+V(x)*{G};V(g)<+{G};V(a)<+0;')),
]
SOURCES={'u':[[0.,0.],[.5,.5]],'s':[[0.,0.],[.5,.5]]}

def check_response(case,response,times=TIMES):
 """This is a local fixture validator, not an amendment to any historical checker."""
 import math
 if not case['positive']:raise ValueError('negative fixture must be checked as structured rejection')
 names=response['nodes'];assert len(names)==len(set(names)) and set(['x','a','y','g'])<=set(names)
 assert response['transient']['times']==times
 rows=response['solutions'];assert len(rows)==len(times)
 errors=[]
 for row,t in zip(rows,times,strict=True):
  values=row['voltages'];assert len(values)==len(names) and all(math.isfinite(v) for v in values)
  for n,want in expected(t,case['kind']).items():
   err=abs(F(values[names.index(n)])-want);assert err<=F('1e-8'),(case['name'],t,n,float(err));errors.append(float(err))
 return max(errors,default=0.)
