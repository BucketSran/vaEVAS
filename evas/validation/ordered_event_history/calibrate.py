import copy,json
from pathlib import Path
from fractions import Fraction as F
from history_checker import analytic,inspect,US,A,B,C,STOP,M
from spec_b_checker import inspect as spec_inspect,formula as spec_formula,events
root=Path(__file__).resolve().parent;checks=[]
def record(name,r,num=None,event=None):
 ok=(num is None or r['numeric_status']==num) and (event is None or r['event_status']==event);checks.append(dict(name=name,pass_=ok,numeric=r['numeric_status'],event=r['event_status']));assert ok,(name,r)
for case in ('nonlinear_near','linear_pwl_near'):
 times={F(i,10**8) for i in range(700)}|{STOP}
 for c in (A,B,2*A,3*A,2*B):times.update(c+F(i,20_000_000_000) for i in range(-40,41))
 rows=[dict(analytic(case,t),time=t) for t in sorted(times)]
 record(case+' independent positive',inspect(rows,case,F('0.00000011')),'P','P')
 for signal in ('z','y'):
  bad=copy.deepcopy(rows);bad[-1][signal]+=F(2,10**6);record(case+' '+signal+' 2uV fault',inspect(bad,case,F('0.00000011')),'F')
 bad=copy.deepcopy(rows);bad[-1]['n']=4;record(case+' duplicate timer',inspect(bad,case,F('0.00000011')),event='F')
 bad=copy.deepcopy(rows)
 for row in bad:row.pop('n')
 record(case+' missing counter observation',inspect(bad,case,F('0.00000011')),event='I')
 sparse=[row for row in rows if all(abs(row['time']-c)>F(2,10**9) for c in (A,B,2*A,3*A,2*B))]
 record(case+' insufficient event bracket',inspect(sparse,case,F('0.00000011')),event='I')
 bad=copy.deepcopy(rows)
 for row in bad:row['m']=sum(row['time']>c+F(2,10**9) for c in (B,2*B))
 record(case+' delayed2ns counter',inspect(bad,case,F('0.00000011')),event='F')
 bad=copy.deepcopy(rows);bad[-1]['z']=float('nan');record(case+' nonfinite',inspect(bad,case,F('0.00000011')),'F','F')
 record(case+' missing scientific stop',inspect(rows[:-1],case,F('0.00000011')),'I','I')
 bad=copy.deepcopy(rows);bad[-1]['h']=1;record(case+' spuriouscross',inspect(bad,case,F('0.00000011')),event='F')
times={F(i,500) for i in range(1001)}
for _,c,_ in events('E6'):times.update(c+F(i,50_000_000) for i in range(-50,51))
rows=[dict(spec_formula('E6',t),time=t) for t in sorted(times)]
record('E6 unchanged checker positive',spec_inspect(rows,'E6',2,F('.002')),'P','P')
bad=copy.deepcopy(rows);bad[-1]['z']+=F(2,10**6);record('E6 unchanged checker2uVreject',spec_inspect(bad,'E6',2,F('.002')),'F')
# Exact literal calendar and sample controls independent of backend results.
assert 3*A<2*B and C==2*B
mid=(3*A+2*B)/2
for case in ('nonlinear_near','linear_pwl_near'):
 at=analytic(case,3*A);between=analytic(case,mid);end=analytic(case,2*B)
 assert (at['n'],at['m'])==(2,1)
 assert (between['n'],between['m'])==(3,1)
 assert (end['n'],end['m'])==(3,1)
 z_at_second_sample=1/(1+M*(16*B-6*A)) if case=='nonlinear_near' else M*(17*B-6*A)
 assert analytic(case,2*B)['z']==z_at_second_sample
 after=analytic(case,2*B+F(1,10**12))
 assert after['y']==z_at_second_sample and after['n']==3 and after['m']==2
 checks.append(dict(name=case+' exact3A-between-2B calendar/sample control',pass_=True))
(root/'CALIBRATION.json').write_text(json.dumps(dict(checks=checks,passed=sum(c['pass_'] for c in checks),total=len(checks)),indent=2)+'\n');print(len(checks),'controls passed')
