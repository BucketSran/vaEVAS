"""Correct initial generic gate to unchanged original N07 zero-V budget. No backend execution."""
import json,hashlib,argparse
from pathlib import Path
from decimal import Decimal as Q
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();O=a.output
x=json.loads((O/'ANALYSIS.json').read_text())
def gate(v):
 if not v.is_finite():raise ValueError('nonfinite')
 return v==0
assert gate(Q(0)) and not gate(Q('1e-30'))
try:gate(Q('NaN'));raise AssertionError('nonfinite accepted')
except ValueError:pass
for c in x['cases']:
 c['original_budget_V']=0
 if c['status']=='completed':c['finite_pair_pass']=not c['exact_native_missing_tokens'] and len(c['pairs'])==len(c['request']['output_times']) and all(gate(Q(r['error_V'])) and gate(Q(r['analytic_error_V'])) for r in c['pairs']) and c['callback_sequence_pass']
x['budget_correction']='Initial runner generic 1e-8 gate was incorrect. This final analysis restores unchanged frozen N07 zero-V budget. No backend rerun or response modifications; both dyadic controls have exactly zero difference.'
x['finalizer_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();x['zero_budget_gate_calibration']={'accept_zero':True,'reject_nonzero':True,'reject_nonfinite':True}
(O/'ANALYSIS-original-budget.json').write_text(json.dumps(x,indent=2)+'\n')
