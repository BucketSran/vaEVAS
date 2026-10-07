import copy,json
from fractions import Fraction as F
from pathlib import Path
from checker import inspect,formula,events
root=Path(__file__).resolve().parent
checks=[]
def run(name,rows,case,expect_numeric=None,expect_event=None,origin='synthetic_exact'):
 r=inspect(rows,case,1 if case in ('E1','E2') else 2,F(1,50),origin=origin)
 ok=(expect_numeric is None or r['numeric_status']==expect_numeric) and (expect_event is None or r['event_status']==expect_event)
 checks.append({'name':name,'pass':ok,'numeric_status':r['numeric_status'],'event_status':r['event_status'],'failures':r['failures']})
 assert ok,(name,r)
for case in ('E1','E2','E3','E4','E5','E6'):
 stop=1 if case in ('E1','E2') else 2
 times={F(i,50) for i in range(stop*50+1)}
 for _,nom,_ in events(case):times.update(nom+F(i,50_000_000) for i in range(-50,51))
 rows=[dict(formula(case,t),time=t) for t in sorted(times)]
 run(case+' positive',rows,case,'P','P')
 bad=copy.deepcopy(rows);bad[-1]['z']+=F(2,10**6);run(case+' voltage exceeds 1uV',bad,case,'F')
 bad=copy.deepcopy(rows);bad[-1]['count']=2;run(case+' duplicate count',bad,case,expect_event='F')
 sparse=[r for r in rows if all(abs(r['time']-nom)>F(1,10000) for _,nom,_ in events(case))]
 run(case+' insufficient event observations',sparse,case,expect_event='I')
 bad=copy.deepcopy(rows);bad[-1]['u']=float('nan');run(case+' nonfinite',bad,case,'F','F')
 missing=rows[:-1];run(case+' missing scientific stop',missing,case,'I','I')
 r=inspect(rows,case,stop,F(1,50),origin='unqualified_decimal_export');assert r['qualification_status']=='I';checks.append({'name':case+' origin unqualified','pass':True})
 # Old root retained or changed deadline ignored must fail counts independently.
 bad=copy.deepcopy(rows)
 for row in bad:row['count']=F(row['time']>(F(1,2) if case=='E4' else F(3,4)))
 run(case+' stale root/deadline',bad,case,expect_event='F')
(root/'CALIBRATION.json').write_text(json.dumps({'checks':checks,'passed':sum(c['pass'] for c in checks),'total':len(checks)},indent=2)+'\n')
print(len(checks),'calibration controls passed')
