"""Replay 33 transport/query-state controls and 6 separate direct-y controls, without EVAS."""
from pathlib import Path
import json,importlib.util,copy,hashlib
from adapter_v2 import transport_rejection,query_state_contract
from phase_y import direct_phase_y
home=Path(__file__).resolve().parent
plan=json.loads((home/'PHASE_PLAN.json').read_text())['requests']
def checker(item):
 p=home/item['checker'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['checker_sha256'];s=importlib.util.spec_from_file_location('oracle',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c);return c
count=0
for x in json.loads((home/'ADAPTER_V2_CALIBRATION.json').read_text())['controls']:
 if 'transport' in x:
  t=x['transport'];assert transport_rejection(t['stdout'],t['stderr'],t['returncode'])['status']==x['expected'];count+=1
for x in plan:
 if x['expected']=='specific_rejection':continue
 c=checker(x);probes=x['extra_queries'];before=probes['before_tau'];after=probes['strictly_after_all_roots'];assert c.Q(before)<c.TAU;assert c.Q(after)>max(t for _,t in c.clocks(x['family']))
 req=json.loads((home/x['wire']).read_text());names=[s['name'] for s in req['program']['states']];t={'times':[before,after],'state_names':['Xdut:'+n for n in names],'states':[[float(c.formula(x['family'],c.Q(clock))[n]) for n in names] for clock in [before,after]]}
 assert query_state_contract(t,c,x['family'])['status']=='P';bad=copy.deepcopy(t);bad['states'][-1][0]-=1;assert query_state_contract(bad,c,x['family'])['status']=='F';count+=2
assert count==33
seen=set();direct=0
for x in plan:
 family=x['family']
 if family=='hidden_tight' or family in seen:continue
 seen.add(family);c=checker(x);probes=x['extra_queries'];rows=[{'time':t,'y':float(c.formula(family,c.Q(t))['y'])} for t in probes.values()]
 assert direct_phase_y(rows,c,family,probes)['status']=='P';bad=copy.deepcopy(rows);bad[-1]['y']+=2e-6;assert direct_phase_y(bad,c,family,probes)['status']=='F';direct+=2
assert direct==6
print('33 transport/query-state controls P; separate 6 direct-y controls P; no simulator calls')
