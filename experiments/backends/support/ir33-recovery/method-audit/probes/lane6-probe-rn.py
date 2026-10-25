from fractions import Fraction as Q
from decimal import Decimal as D,localcontext
import json,hashlib
from pathlib import Path
from probe_context import context
ROOT,P=context()
def exact(v):return {'fraction':str(Q(v)),'float':float(v),'hex':float(v).hex()}
u=lambda t:Q(1)+Q(t)/3*Q(2**-52)
lineage_u=lambda t:Q(.2)*Q(t)/2
sampled=Q(float(lineage_u(.25)));q=Q(float(sampled+Q(.25)));read=Q(float(lineage_u(1.5)));delta=Q(float(q-read))
product=Q(.45)*Q(.16);stored=Q(float(product));voltage=10**12*stored+1
with localcontext() as c:
 c.prec=100
 time=D('1.5');e=(-D('.5')).exp();drive=D(10**16)/D(3*2**52)
 old=drive+(1-drive)*e
 filter_case={'input_pwl':[[0,1],[3,float(Q(1)+Q(2**-52))]],'program':'@(initial_step)q=1; @(timer(1,1,1e-12))q=1e16*(V(u)-1); y=laplace_nd(q,{1},{1,1})','rn_drives':[{ 'time':k,'exact_source':exact(u(k)),'sampled_binary64':exact(float(u(k))),'difference_after_RN':exact(float(Q(float(u(k)))-1)),'stored_q':exact(float(Q(10**16)*Q(float(Q(float(u(k)))-1))))} for k in [1,2]],'query_time':1.5,'derivation':'y(1)=1; q=0 on (1,2), so y(1.5)=exp(-.5). Old helper uses pre-RN q=1e16/(3*2^52).','new_oracle':str(e),'old_helper_formula':str(old),'absolute_difference':str(old-e),'test_budget':1.01e-6}
out={'purpose':'Standalone exact arithmetic and independent Decimal analytic derivation; not simulator output','filter':filter_case,'lineage':{'original_sampled_pre_RN':exact(lineage_u(.25)+Q(.25)),'stored_q':exact(q),'sampled_u_at_1_5':exact(read),'RN_subtraction':exact(delta),'strict_gt_0_125':delta>Q(.125),'explanation':'Full RN gives y=0 at1.5 as asserted; forced h nonpoint enclosure of pre-RN q is wrong target.'},'continuous_amplification_countercheck':{'exact_product':exact(product),'stored_RN_product':exact(stored),'physical_voltage':exact(voltage),'nearest_binary64_error':str(abs(Q(float(voltage))-voltage)),'budget':1e-8,'required_reject':abs(Q(float(voltage))-voltage)>Q(1e-8),'explanation':'Even after program RN, continuous gain1e12 leads unrepresentable physical voltage at1e-8 budget. Do not weaken these rejection tests.'},'source_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
P.write_text(json.dumps(out,indent=2)+'\n')
print(P)
print('filter difference',filter_case['absolute_difference'])
