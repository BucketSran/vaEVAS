"""Separate10 independent forced-flow checker controls; no simulator imports or calls."""
from pathlib import Path
import json,copy,hashlib
import checker as c
h=Path(__file__).resolve().parent;plan=json.loads((h/'PLAN.json').read_text());assert c.Q(.3000000000000001)>c.TAU;controls=0
for item in plan['requests']:
 p=h/item['wire'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['wire_sha256'];wire=json.loads(p.read_text());times=wire['transient']['output_times'];raw={'nodes':['0','dut:z','u','y'],'solutions':[{'voltages':[0,float(c.formula(t)['z']),t,float(c.formula(t)['y'])]} for t in times],'transient':{'times':times,'state_names':['dut:n','dut:q'],'states':[[float(c.formula(t)[k]) for k in ['n','q']] for t in times],'events':[{'event':0,'time':.1,'before':[0,0],'after':[1,0]},{'event':0,'time':.3000000000000001,'before':[1,0],'after':[2,1]}]}}
 assert c.inspect(raw,wire)['status']=='P';controls+=1
 bad=copy.deepcopy(raw);bad['solutions'][-1]['voltages'][-1]+=2e-6;assert c.inspect(bad,wire)['status']=='F';controls+=1
 bad=copy.deepcopy(raw);bad['transient']['states'][-1]=[1,0];assert c.inspect(bad,wire)['status']=='F';controls+=1
 bad=copy.deepcopy(raw);bad['transient']['events'].pop();assert c.inspect(bad,wire)['status']=='F';controls+=1
 bad=copy.deepcopy(raw);bad['transient']['state_names']=[];assert c.inspect(bad,wire)['status']=='F';controls+=1
assert controls==10;print('Separate forced-anchor10 controls P; 0 simulator invocations')
