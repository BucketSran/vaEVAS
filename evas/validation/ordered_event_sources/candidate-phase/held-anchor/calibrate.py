"""Portable separate10 controls for each frozen single-timer or held-replan diagnostic."""
from pathlib import Path
import argparse,json,copy,hashlib,importlib.util
p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args();h=a.fixture;sp=importlib.util.spec_from_file_location('independentchecker',h/'checker.py');c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c);plan=json.loads((h/'PLAN.json').read_text());assert c.Q(.3000000000000001)>c.TAU
if hasattr(c,'ONE'):assert c.TAU<c.ONE<c.Q(.3000000000000001) and c.ONE+c.A>c.STOP
controls=0
for item in plan['requests']:
 pp=h/item['wire'];assert hashlib.sha256(pp.read_bytes()).hexdigest()==item['wire_sha256'];wire=json.loads(pp.read_text());times=wire['transient']['output_times'];names=[s['name'] for s in wire['program']['states']]
 before1=[float(c.formula(0)[k]) for k in names];after1=[float(c.formula(.15)[k]) for k in names];after2=[float(c.formula(.3000000000000001)[k]) for k in names]
 raw={'nodes':['0','dut:z','u','y'],'solutions':[{'voltages':[0,float(c.formula(t)['z']),t,float(c.formula(t)['y'])]} for t in times],'transient':{'times':times,'state_names':['dut:'+n for n in names],'states':[[float(c.formula(t)[k]) for k in names] for t in times],'events':[{'event':0,'time':.1,'before':before1,'after':after1},{'event':0,'time':.3000000000000001,'before':after1,'after':after2}]}}
 assert c.inspect(raw,wire)['status']=='P';controls+=1
 bad=copy.deepcopy(raw);bad['solutions'][-1]['voltages'][-1]+=2e-6;assert c.inspect(bad,wire)['status']=='F';controls+=1
 bad=copy.deepcopy(raw);bad['transient']['states'][-1]=after1;assert c.inspect(bad,wire)['status']=='F';controls+=1
 bad=copy.deepcopy(raw);bad['transient']['events'].pop();assert c.inspect(bad,wire)['status']=='F';controls+=1
 bad=copy.deepcopy(raw);bad['transient']['state_names']=[];assert c.inspect(bad,wire)['status']=='F';controls+=1
assert controls==10;print('Separate scope-case10 controls P; 0 simulator invocations')
