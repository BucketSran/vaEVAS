"""Standalone accept/fault/missing calibration plus manual sub-ULP controls."""
from checker import *
from pathlib import Path
import copy,json
checks=[]
def record(case,label,expected):checks.append({'case':case,'control':label,'expected':expected,'asserted':True})
for case,stop in [('mixed_source',.49),('hidden_loose',.31),('hidden_tight',.31)]:
 times={Q(0),Q(stop)}
 for _,t in clocks(case):times.update([t-Q(2e-9),t-T/4,t+T/4,t+Q(2e-9)])
 rows=[dict(time=t,**formula(case,t)) for t in sorted(times)];events=[{'event_index':i} for i,_ in clocks(case)]
 a=inspect(rows,case,stop,events);assert a['finite_numeric_status']=='P' and a['finite_event_status']=='P' and a['exact_order_status']=='P';record(case,'Fraction positive finite','P')
 bad=copy.deepcopy(rows);bad[-1]['y']+=Q(2e-6);assert inspect(bad,case,stop)['finite_numeric_status']=='F';record(case,'external voltage2uVfault','F')
 bad=copy.deepcopy(rows);bad[-1]['n']-=1;assert inspect(bad,case,stop)['finite_event_status']=='F';record(case,'missing callbackfault','F')
 assert inspect(rows,case,stop,list(reversed(events)))['exact_order_status']=='F';record(case,'reversed eventindexorder','F')
 missing=[{k:v for k,v in r.items() if k!='n'} for r in rows];assert inspect(missing,case,stop)['finite_event_status']=='I';record(case,'missing observer','I')
 if case=='hidden_tight':
  for good in [True,False]:
   a=inspect([],case,stop,rejection={'semantic_category':'cross_ttol_unrepresentable' if good else 'generic failure','accepted_waveform':False});assert a['rejection_status']==('P' if good else 'F');record(case,'specific rejection' if good else 'generic failure isnotproof',a['rejection_status'])
controls=[('mixed_source',(SOURCE_ROOT+TAU)/2,{'n':1,'k':1,'j':0,'y':2}),('mixed_source',(TAU+ONE)/2,{'n':2,'k':1,'j':0,'y':3}),('hidden_loose',(TAU+HIDDEN_ROOT)/2,{'n':2,'q':1,'h':0,'m':0,'y':0}),('hidden_loose',(HIDDEN_ROOT+ONE)/2,{'n':2,'q':1,'h':1,'m':0,'y':1})]
for case,t,want in controls:
 assert all(formula(case,t)[k]==v for k,v in want.items());checks.append({'case':case,'control':'manually expected nearby clock state','time':str(t),'expected':want,'asserted':True})
assert len(checks)==21
Path(__file__).with_name('CALIBRATION.json').write_text(json.dumps({'passed':21,'breakdown':'17 accept/fault/missing +4 manually expected nearbyclock fixtures','checks':checks},indent=2)+'\n');print('21 controls passed (17+4)')
