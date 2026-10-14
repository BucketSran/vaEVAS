"""Additional finite sample comparison only. Does not change exact-native qualification."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
import hashlib,json,math,re
E=Path(__file__).resolve().parent
old_files=[E/'spectre-v2/ANALYSIS.json',E/'spectre-v1/ANALYSIS.json',E/'near-sample/AUDIT.json']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):sha(p) for p in old_files}
contract=json.loads((E/'controls/CONTRACT.json').read_text())
points=[(F(float(t)),F(float(v))) for t,v in contract['transient_controls']['pwl']]
tau=F(0.5e-6)
U=max(abs((v-u)/(b-a)) for (a,u),(b,v) in zip(points,points[1:]))
L=U+2/tau
assert L>6000000 and L<6000001
LB=F(6000001)
def text(f):
 with localcontext() as ctx:
  ctx.prec=70
  return str(D(f.numerator)/D(f.denominator))
def oracle(t):
 with localcontext() as ctx:
  ctx.prec=100
  dec=lambda f:D(f.numerator)/D(f.denominator)
  t=dec(F(float(t)));state=D(0);tau_d=dec(tau)
  for (fa,fu),(fb,fv) in zip(points,points[1:]):
   a,u,b,v=map(dec,(fa,fu,fb,fv));h=min(t,b)-a
   if h<0:break
   slope=(v-u)/(b-a);ex=(-h/tau_d).exp()
   state=state*ex+u*(1-ex)+slope*(h-tau_d*(1-ex));value=u+slope*h
   if t<=b:return F(value*state)
  h=t-dec(points[-1][0]);u=dec(points[-1][1]);return F(u*(u+(state-u)*(-h/tau_d).exp()))
def read_rows(p):
 rows=[]
 for name,token in re.findall(r'^"([^"\n]+)" ([^\n]+)$',p.read_text().split('\nVALUE\n',1)[1].split('\nEND',1)[0],re.M):
  if name=='time':rows.append({'time':float(token),'time_token':token})
  else:rows[-1][name]=float(token)
 return rows
def upper(v,oq,dt,li,voltage_round,time_round):
 assert dt>=0 and li>=0 and voltage_round>=0 and time_round>=0
 return abs(F(v)-oq)+li*(dt+time_round)+voltage_round+F(1,10**60)
def gate(*args,budget):return upper(*args)<=budget
B=F(2,10**9)
cal={
 'exact_good_accept':gate(0,F(0),F(0),LB,F(0),F(0),budget=B),
 'large_voltage_reject':not gate(1e-8,F(0),F(0),LB,F(0),F(0),budget=B),
 'large_time_shift_reject':not gate(0,F(0),F(1,10**12),LB,F(0),F(0),budget=B),
 'rounding_consumes_budget_reject':not gate(0,F(0),F(0),LB,B+F(1,10**12),F(0),budget=B),
 'zero_model_zero_derivative_accept':gate(0,F(0),F(1),F(0),F(0),F(0),budget=B),
}
assert all(cal.values())
out={'role':'additional_finite_near_sample_vs_exact_query_oracle_evidence_only','not_claimed':['Spectre value at missing query','Spectre numerical trajectory between native rows','exact_native_query qualification','whole-time trajectory certification','Q qualification'], 'U_exact':str(U),'U_decimal':text(U),'tau_exact':str(tau),'minimal_proven_L_decimal':text(L),'L_used':6000001,'calibration':cal,'cases':{}}
for name in ['zero_forcing_filter','input_filter_product']:
 rows=read_rows(E/'spectre-v2'/name/'near-samples.psf')
 budget=F(1,10**9) if name=='zero_forcing_filter' else B
 li=F(0) if name=='zero_forcing_filter' else LB
 results=[]
 for q in contract['transient_controls']['output_times']:
  r=min(rows,key=lambda r:abs(F(r['time'])-F(float(q))))
  dt=abs(F(r['time'])-F(float(q)));oq=F(0) if li==0 else oracle(q);on=F(0) if li==0 else oracle(r['time'])
  er=F(math.ulp(r['y']))/2;et=F(math.ulp(r['time']))/2
  bound=upper(r['y'],oq,dt,li,er,et)
  assert abs(oq-on)<=li*dt+F(2,10**60)
  results.append({'query':q,'actual_native_time_token':r['time_token'],'exact_native':r['time']==q,'time_distance_seconds':text(dt),'query_oracle':text(oq),'observed_y':r['y'],'measured_vs_query_oracle_plus_time_and_rounding_bound_V':text(bound),'budget_V':text(budget),'passed':bound<=budget})
 out['cases'][name]={'queries':results,'all_finite_comparisons_pass':all(r['passed'] for r in results),'max_bound_V':max(results,key=lambda r:D(r['measured_vs_query_oracle_plus_time_and_rounding_bound_V']))['measured_vs_query_oracle_plus_time_and_rounding_bound_V']}
# A numerical curve can agree at both native endpoints yet spike at missing q.
# This deliberately passes the finite sample check; it must never be called a q-trajectory check.
out['scope_counterexample']={'analytic_y':'0 for all t','native_samples':[[0.,0.],[1.,0.]],'missing_query':0.5,'possible_unrecorded_numerical_curve':'S(t)=1-2*abs(t-0.5) on [0,1]','S_query':1,'finite_near_sample_check_passes':gate(0,F(0),F(1,2),F(0),F(0),F(0),budget=B),'therefore_certifies_S_at_query':False}
assert all(sha(p)==before[str(p)] for p in old_files)
out['old_files_unchanged_sha256']=before
archived=json.loads((E/'near-sample/AUDIT.json').read_text())
assert out['cases']==archived['cases']
assert out['calibration']==archived['calibration']
assert out['L_used']==archived['L_used']
inventory=json.loads((E/'INVENTORY.json').read_text())
assert all(sha(E/n)==v['sha256'] for n,v in inventory['files'].items())
print(json.dumps({'U':text(U),'L':text(L),'calibration':cal,'max_bounds':{n:v['max_bound_V'] for n,v in out['cases'].items()}},indent=2))

# Same-source constants reuse: check retained actual native samples and new IR19 response.
assert sha(E/'constants/dut.va')==json.loads((E/'constants/reference/RESULT.json').read_text())['source_sha256']
constant_rows=read_rows(E/'constants/reference/psf/tran.tran.tran')
answers=json.loads((E/'constants/ORACLES.json').read_text())
with localcontext() as ctx:
 ctx.prec=80
 for row in constant_rows:
  assert all(abs(D.from_float(row[k])-D(v))<=D('1e-14') for k,v in answers.items())
request=json.loads((E/'constants/candidate-request.json').read_text())
response=json.loads((E/'constants/candidate-response.json').read_text())
nodes=request['program']['nodes']
queries=response['strobe_evidence']
assert len(constant_rows)==16 and len(queries['times'])==4
assert all(any(r['time']==t for r in constant_rows) for t in queries['times'])
with localcontext() as ctx:
 ctx.prec=80
 for values in queries['voltages_V']:
  assert all(abs(D.from_float(values[nodes.index(k)])-D(v))<=D('1e-14') for k,v in answers.items())
print('retained actual constants: 16 native rows / 224 values; candidate: 4 queries / 56 values PASS')

for name, entry in inventory['files'].items():
 if entry['kind']=='lossless_JSON_encoded_original_log_text':
  original=json.loads((E/name).read_text())['original_log_text'].encode('utf-8')
  assert hashlib.sha256(original).hexdigest()==entry['original_sha256']
