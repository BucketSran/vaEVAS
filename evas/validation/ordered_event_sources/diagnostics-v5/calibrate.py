from checker import *
from pathlib import Path
import copy,json
checks=[]
for family,stop in [('mixed_source',.49),('hidden_loose',.31),('hidden_loose_nocross',.31)]:
 ts={Q(0),Q(stop)}
 for _,clock in clocks(family):ts.update([clock-T/4,clock+T/4])
 rows=[dict(time=t,**formula(family,t)) for t in sorted(ts)];events=[{'event_index':i} for i,_ in clocks(family)];a=inspect(rows,family,stop,events)
 assert a['finite_numeric_status']=='P' and a['finite_event_status']=='P' and a['exact_order_status']=='P';checks.append({'family':family,'positive':'P'})
 bad=copy.deepcopy(rows);bad[-1]['y']+=V*2;assert inspect(bad,family,stop)['finite_numeric_status']=='F';checks.append({'family':family,'physical_voltage_fault':'F'})
 bad=copy.deepcopy(rows);bad[-1]['n']-=1;assert inspect(bad,family,stop)['finite_event_status']=='F';checks.append({'family':family,'missingtimer_fault':'F'})
 assert inspect(rows,family,stop,list(reversed(events)))['exact_order_status']=='F';checks.append({'family':family,'reversedorder_fault':'F'})
 missing=[{k:v for k,v in r.items() if k!='n'} for r in rows];assert inspect(missing,family,stop)['finite_event_status']=='I';checks.append({'family':family,'missing_observer':'I'})
assert formula('hidden_loose_nocross',Q(.31))['h']==0 and formula('hidden_loose_nocross',Q(.31))['y']==0
bad=copy.deepcopy(rows);bad[-1]['h']=1;assert inspect(bad,'hidden_loose_nocross',.31)['finite_event_status']=='F';checks.append({'family':'hidden_loose_nocross','spurious_removed_cross_fault':'F'})
assert len(checks)==16
Path(__file__).with_name('CALIBRATION.json').write_text(json.dumps({'passed':16,'controls':checks},indent=2)+'\n');print('16 controls passed')
