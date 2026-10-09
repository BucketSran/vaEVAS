"""Independent forced single-timer flow; exact binary64 literal and PWL identities."""
from fractions import Fraction as F
Q=F.from_float
A=Q(.1);P=Q(.2);TAU=A+P;STOP=Q(.31);BUDGET=Q(1e-7);T=F(1,10**9)
def formula(t):
 t=Q(t) if isinstance(t,float) else F(t)
 n=F(int(t>A)+int(t>TAU));q=max(F(0),n-1);z=(t*t-TAU*TAU)/2 if t>TAU else F(0)
 return {'u':t,'z':z,'y':z,'n':n,'q':q}
def inspect(raw,wire):
 failures=[];tr=raw.get('transient',{});times=tr.get('times',[])
 if times!=wire['transient']['output_times']:failures.append('wrong output times')
 names=['dut:'+s['name'] for s in wire['program']['states']]
 if tr.get('state_names')!=names:failures.append('wrong actual state layout')
 states=tr.get('states',[]);solutions=raw.get('solutions',[]);nodes=raw.get('nodes',[]);rows=[]
 if len(states)!=len(times) or len(solutions)!=len(times):failures.append('missing actual query states/solutions')
 for t,sv,sol in zip(times,states,solutions):
  ans=formula(t);values=dict(zip(nodes,sol['voltages']));wanted=[ans[n.split(':')[-1]] for n in names]
  if len(sv)!=len(names) or [Q(x) for x in sv]!=wanted:failures.append('wrong actual physical query phase')
  err={}
  for node,key in [('u','u'),('dut:z','z'),('y','y')]:
   if node not in values:failures.append('missing '+node);continue
   err[key]=float(abs(Q(values[node])-ans[key]))
   if abs(Q(values[node])-ans[key])>BUDGET:failures.append('physical voltage error '+node)
  rows.append({'time':t,'exact_query':str(Q(t)),'actual_states':sv,'expected_states':[str(x) for x in wanted],'expected_y':float(ans['y']),'actual_y':values.get('y'),'errors_V':err})
 ev=tr.get('events',[])
 if [x.get('event') for x in ev]!=[0,0]:failures.append('wrong callback count/order')
 for i,(event,clock) in enumerate(zip(ev,[A,TAU])):
  if event.get('before')!=[float(i),float(max(0,i-1))] or event.get('after')!=[float(i+1),float(i)]:failures.append('wrong callback states')
  if abs(Q(event['time'])-clock)>T:failures.append('callback representative outside1ns')
 return {'status':'F' if failures else 'P','failures':failures,'observations':rows,'event_source_order':[x.get('event') for x in ev],'scope':'Separate forced single-timer scope probe; no uncertain jump-window omission at the proven queries. Numeric/event/query-state checks do not establish exact representative=physicalclock equality.'}
