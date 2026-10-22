"""Independent P1 positive and fault-injection grading calibration."""

import argparse
import copy
import json
from pathlib import Path

from clock_cases import configuration, CASES
from clock_reference import score_wave, state_series, pair
from validate_clock import negative_verdict
from validate_spectre_r53 import selection_verdict


def calibrate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    cfg=configuration("positive")
    times=[0,.5e-9,1e-9,1.005e-9,1.01e-9,1.015e-9,1.02e-9,1.021e-9,2e-9,25e-9]
    wave={"time":times,"ya":[.4+.7*min(1,max(0,(t-1e-9)/20e-12)) for t in times]}
    rows={"independent_linear_edge":score_wave(wave,cfg)["passed"]}
    for name,index,delta in [("platform",-1,1.01e-4),("edge",4,.0061),("t0",0,.000101)]:
        bad=copy.deepcopy(wave);bad["ya"][index]+=delta
        rows[name+"_rejected"]=not score_wave(bad,cfg)["passed"]
    for name in ("missing_edge","nonfinite","truncated","range"):
        bad=copy.deepcopy(wave)
        if name=="missing_edge":bad["ya"]=[.4]*len(times)
        if name=="nonfinite":bad["ya"][4]=float('nan')
        if name=="truncated":bad["ya"].pop()
        if name=="range":
            for values in bad.values():values.pop()
        rows[name+"_rejected"]=not score_wave(bad,cfg)["passed"]
    # Endpoints are correct but contain no middle pulses. Do not manufacture
    # this control with the checker's curve or design-calendar generator.
    cfg32=configuration('default32')
    sparse={'time':[0,3700e-9],'rsta':[1.1,0],'sa':[0,0],'ssa':[0,0],
            'nc_aza':[0,0],'nca':[0,0],'conva':[0,1.1]}
    rows['two_endpoint_wave_rejected']=not score_wave(sparse,cfg32)['passed']
    tiny=configuration('tiny');ts=[0,1e-15,10e-12,20.001e-12,1e-9]
    tiny_wave={'time':ts,'ya':[1.1*min(1,max(0,(t-1e-15)/20e-12)) for t in ts]}
    rows['tiny_correct']=score_wave(tiny_wave,tiny)['passed']
    tiny_wave['ya'][0]=.001
    rows['tiny_t0_1mV_rejected']=not score_wave(tiny_wave,tiny)['passed']
    for name,ts,values in [
        ('state_correct',[0,1e-9,25e-9],[.4,1.1,1.1]),
        ('late',[0,1.0002e-9,25e-9],[.4,1.1,1.1]),
        ('early',[0,.9998e-9,25e-9],[.4,1.1,1.1]),
        ('lost',[0,25e-9],[.4,.4]),
        ('duplicate',[0,1e-9,2e-9,25e-9],[.4,1.1,.4,1.1]),
        ('wrong_state',[0,1e-9,25e-9],[.4,1.100101,1.100101]),
    ]:
        actual=state_series(ts,values,.4,[[1e-9,1.1]],cfg['budgets'])['passed']
        rows[name]=actual==(name=='state_correct')
    rows['integer_rounding_rejected']=not state_series([0,1e-8],[1,2.000001],1,[[1e-8,2]],cfg['budgets'],True)['passed']
    rows['pair_correct']=pair(wave,wave,cfg)['passed']
    for name,index,delta in [('platform',-1,.000201),('edge',4,.0121),('retry',-1,5.01e-8)]:
        bad=copy.deepcopy(wave);bad['ya'][index]+=delta
        rows['pair_'+name+'_rejected']=not pair(wave,bad,cfg,5e-8 if name=='retry' else None)['passed']
    execution={'exit_code':0}
    rows['absent_batch_injection_not_pass']=not negative_verdict('batch-leak',execution,True,{},None)['passed']
    rows['absent_DC_injection_not_pass']=not negative_verdict('dc-leak',execution,False,{'dc_calls':0},None)['passed']
    rb={'activated':True,'kind_matches':True,'restored':False}
    rows['actual_batch_leak_detected']=negative_verdict('batch-leak',execution,True,{},rb)['passed']
    rows['early_exit_not_batch_leak_pass']=not negative_verdict('batch-leak',{'exit_code':1},False,{},rb)['passed']
    rows['actual_DC_leak_detected']=negative_verdict('dc-leak',execution,False,{'dc_calls':3,'dc_injected':True,'dc_state_invariants':False},None)['passed']
    rows['valid_DC_retry_not_leak']=not negative_verdict('dc-leak',execution,True,{'dc_calls':3,'dc_injected':True,'dc_state_invariants':True},None)['passed']
    protocol={'cases':dict.fromkeys(CASES),'fixed_denominator':len(CASES)}
    good={n:{'passed':True} for n in CASES}
    rows['complete15_gate']=selection_verdict(good,list(CASES),protocol)['passed']
    rows['partial_not_suite_pass']=not selection_verdict({'zero':{'passed':True}},['zero'],protocol)['passed']
    missing=dict(good);missing.pop('near')
    rows['missing_case_not_suite_pass']=not selection_verdict(missing,list(missing),protocol)['passed']
    result={'passed':all(rows.values()),'total':len(rows),'controls':rows,'new_simulator_runs':0}
    (output/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('P1 calibration',result['passed'],len(rows),[k for k,v in rows.items() if not v]);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');a=p.parse_args()
    raise SystemExit(0 if calibrate(a.output)['passed'] else 1)
