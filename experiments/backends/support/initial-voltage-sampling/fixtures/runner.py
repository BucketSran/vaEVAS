#!/usr/bin/env python3
"""Standalone frozen-baseline controls. No implementation or gold checker imports.
Expected answers use exact Fraction over specified binary64 constants. A positive
red remains a red; this program reports observations rather than changing gates.
"""
import argparse, copy, hashlib, json, os, pathlib, subprocess, sys, time
from fractions import Fraction as F
ROOT=pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode=True

def model(body, declarations='real q;'):
    return ('`include "disciplines.vams"\nmodule m(u,v,y,r); input u,v; output y; inout r; '
            'electrical u,v,y,r; '+declarations+' analog begin '+body+' end endmodule\n')

def fixtures():
    u,r,v=F(1),F(1,4),F(1,2)
    d=u-r; w=v-r
    # output expectation is absolute y voltage; model contribution is V(y,r).
    def case(name,body,answer=None,*,expected='accept',decl='real q;',**kw):
        return dict(name=name,source=model(body,decl),expected=expected,
                    answer=[str(x) for x in answer] if answer is not None else None,**kw)
    return [
      case('control-constant-nonzero-reference','@(initial_step) q=0.75; V(y,r)<+q;', [r+d]*3),
      case('sample-direct-held','@(initial_step) q=V(u,r); V(y,r)<+q;', [r+d]*3),
      case('sample-affine-held','@(initial_step) q=2*V(u,r)-V(v,r)+0.125; V(y,r)<+q;', [r+2*d-w+F(1,8)]*3),
      case('sample-selected-voltage-arm','@(initial_step) q=(V(u,r)>0.5)?(V(v,r)+0.125):V(u,r); V(y,r)<+q;', [r+w+F(1,8)]*3),
      case('sample-source-order','@(initial_step) begin q=V(u,r); a=q+0.125; q=2*q; end V(y,r)<+a+q;', [r+d+F(1,8)+2*d]*3,decl='real q,a;'),
      case('sample-strict-tie','@(initial_step) q=(V(u,r)>0.5)?V(v,r):V(u,r); V(y,r)<+q;', [r+F(1,2)]*3,u0=.75),
      case('sample-timer-zero-consumer','@(initial_step) q=V(u,r); @(timer(0)) q=q+2; V(y,r)<+q;', [r+d+2]*3),
      case('sample-timer-held-consumer','@(initial_step) q=V(u,r); @(timer(q,0)) q=q+2; V(y,r)<+q;', [r+d,r+d,r+d+2]),
      case('sample-transition-consumer','@(initial_step) q=V(u,r); V(y,r)<+transition(q,0,0.125,0.125);', [r+d]*3),
      case('sample-idt-consumer','@(initial_step) q=V(u,r); V(y,r)<+idt(q,0);', [r,r+d*F(1,2),r+d]),
      case('control-integer-predicate','@(initial_step) q=(V(u,r)>0.5); V(y,r)<+q;', [r+1]*3,decl='integer q;'),
      case('reject-implicit-real-integer','@(initial_step) q=V(u,r); V(y,r)<+q;',expected='reject',decl='integer q;'),
      case('reject-fractional-integer','@(initial_step) q=1.5; V(y,r)<+q;',expected='reject',decl='integer q;'),
      case('reject-integer-overflow','@(initial_step) q=2147483648; V(y,r)<+q;',expected='reject',decl='integer q;'),
      case('reject-nonlinear-initial','@(initial_step) q=V(u,r)*V(v,r); V(y,r)<+q;',expected='reject'),
      case('reject-undriven-sampled-input','@(initial_step) q=V(v,r); V(y,r)<+q;',expected='reject',undriven_v=True),
      case('reject-state-voltage-cycle','@(initial_step) q=V(y,r); V(y,r)<+q;',expected='reject'),
      case('reject-uncertain-selector','@(initial_step) q=(V(u,r)>0.5)?1:0; V(y,r)<+q;',expected='reject',u0=.75,errors={'u':.01}),
      case('reject-uncertain-sampled-value','@(initial_step) q=V(u,r); V(y,r)<+q;',expected='reject',errors={'u':.01}),
      case('reject-exact-but-nonrepresentable-sum','@(initial_step) q=V(u)+0.2; V(y,r)<+q;',expected='reject',u0=.1),
      case('reject-uncertainty-after-amplification','@(initial_step) q=V(u,r); V(y,r)<+1000000*q;',expected='reject',errors={'u':.01}),
      case('reject-initial-abstime-separate-scope','@(initial_step) q=$abstime; V(y,r)<+q;',expected='reject'),
    ]

def answers_match(actual, expected):
    """Check the full fixed observation vector before numeric comparison."""
    return len(actual)==len(expected) and all(
        abs(F.from_float(float(x))-F(y))<=F(1,10**10)
        for x,y in zip(actual,expected))


def calibrate_checker(response):
    """Mutate a real successful waveform, with independently fixed answers."""
    expected=['1','1','1']
    cases=[]
    for name,keep,want in [('complete',3,True),('empty',0,False),
                           ('one_sample_only',1,False),('missing_last_sample',2,False)]:
        altered=copy.deepcopy(response)
        altered['solutions']=altered['solutions'][:keep]
        yi=altered['nodes'].index('y')
        actual=[row['voltages'][yi] for row in altered['solutions']]
        got=answers_match(actual,expected)
        cases.append(dict(name=name,actual=actual,expected=expected,
                          accepted=got,expected_accept=want,passed=got==want))
    return dict(checker='answers_match, shared by public and raw IR checks',
                control_origin='actual constant nonzero-reference release-kernel response',
                cases=cases,passed=all(c['passed'] for c in cases))


def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def hashfile(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kernel',type=pathlib.Path,required=True)
    ap.add_argument('--source',type=pathlib.Path,required=True)
    ap.add_argument('--out',type=pathlib.Path,required=True);ap.add_argument('--require-contract',action='store_true');a=ap.parse_args()
    sys.path.insert(0,str(a.source.resolve()))
    from evas import compile_sources,Instance,transient
    a.out.mkdir(parents=True,exist_ok=False)
    cases=fixtures();rows=[]
    for c in cases:
        path=a.out/c['name'];path.mkdir();(path/'dut.va').write_text(c['source']);dump(path/'contract.json',c)
        row={'name':c['name'],'expected':c['expected'],'answer':c['answer']};start=time.monotonic()
        sources={'u':[[0,c.get('u0',1.)],[.25,c.get('u0',1.)],[.5,2.],[1,2.]],'v':[[0,.5],[1,.5]],'r':[[0,.25],[1,.25]]}
        if c.get('undriven_v'):sources.pop('v')
        try:
            p=compile_sources({'dut.va':c['source']},[Instance('dut','m',dict(u='u',v='v',y='y',r='r'))]);dump(path/'program.json',p.to_dict())
            row['stage']='kernel'
            result=transient(p,sources,[0,.5,1],stop=1,max_step=.125,source_errors=c.get('errors'),kernel=a.kernel,timeout=20)
            dump(path/'response.json',result);yi=result['nodes'].index('y');actual=[s['voltages'][yi] for s in result['solutions']]
            row.update(observed='accept',actual=actual)
            if c['answer'] is not None:
                # Independent fixed tolerance, far tighter than every fixture signal.
                row['matches_answer']=answers_match(actual,c['answer'])
        except Exception as e:
            row.update(observed='reject',exception=type(e).__name__,diagnostic=getattr(e,'detail',getattr(e,'diagnostic',str(e))))
            row.setdefault('stage','compiler')
        row['contract_pass']=(row['observed']==row['expected'] and row.get('matches_answer',True));row['seconds']=time.monotonic()-start;dump(path/'result.json',row);rows.append(row)
    # Raw IR controls isolate runtime admission. No helper computes DUT answers.
    seed=compile_sources({'seed.va':model('@(initial_step) q=(V(u,r)>0.5); V(y,r)<+q;')},[Instance('dut','m',dict(u='u',v='v',y='y',r='r'))]).to_dict()
    idx={n:i for i,n in enumerate(seed['nodes'])}
    def affine(constant=0,terms=()):return dict(op='affine',constant=constant,terms=[dict(node=idx[n],coefficient=x) for n,x in terms])
    raw=[('raw-direct-exact',affine(terms=[('u',1),('r',-1)]),'accept',{},['1','1','1']),
         ('raw-uncertain-sample',affine(terms=[('u',1),('r',-1)]),'reject',{'pwl_errors_V':[.01,0,0]},None),
         ('raw-undriven-sample',affine(terms=[('v',1),('r',-1)]),'reject',{'undriven_v':True},None),
         ('raw-cycle-sample',affine(terms=[('y',1),('r',-1)]),'reject',{},None)]
    for name,initial,expected,extra,answer in raw:
        path=a.out/name;path.mkdir();p=copy.deepcopy(seed);p['states'][0]['initial']=initial
        sources=[[[0,1],[.25,1],[.5,2],[1,2]],[[0,.5],[1,.5]],[[0,.25],[1,.25]]];driven=['u','v','r']
        if extra.get('undriven_v'):sources.pop(1);driven.pop(1)
        config=dict(pwl=sources,output_times=[0,.5,1],stop=1,max_step=.125)
        if 'pwl_errors_V' in extra:config['pwl_errors_V']=extra['pwl_errors_V']
        request=dict(program=p,driven=driven,samples=[],transient=config)
        dump(path/'request.json',request)
        proc=subprocess.run([str(a.kernel.resolve())],input=json.dumps(request),text=True,capture_output=True,timeout=20)
        (path/'stdout.json').write_text(proc.stdout);(path/'stderr.json').write_text(proc.stderr)
        observed='accept' if proc.returncode==0 else 'reject'
        row=dict(name=name,stage='kernel_raw_ir',expected=expected,observed=observed,returncode=proc.returncode,contract_pass=observed==expected)
        if observed=='reject':
            try:row['diagnostic']=json.loads(proc.stderr)
            except ValueError:row['diagnostic']=proc.stderr
        else:
            out=json.loads(proc.stdout);yi=out['nodes'].index('y');row['actual']=[s['voltages'][yi] for s in out['solutions']]
            if answer:row['contract_pass'] &= answers_match(row['actual'],answer)
        dump(path/'result.json',row);rows.append(row)
    # Reuse one compiled public program after a failure. This checks request value
    # isolation only, since public adapter launches a new kernel each time.
    path=a.out/'public-retry';path.mkdir();observed=[]
    p=compile_sources({'retry.va':model('@(initial_step) q=(V(u,r)>0.5); V(y,r)<+q;')},[Instance('dut','m',dict(u='u',v='v',y='y',r='r'))])
    before=p.to_dict();sources={'u':[[0,.75],[1,.75]],'v':[[0,.5],[1,.5]],'r':[[0,.25],[1,.25]]}
    for errors in ({'u':.01},{},{}):
        try:
            out=transient(p,sources,[0],stop=1,max_step=1,source_errors=errors,kernel=a.kernel,timeout=20)
            observed.append(dict(accept=True,states=out['transient']['states']))
        except Exception as e:observed.append(dict(accept=False,detail=getattr(e,'detail',str(e))))
    retry=dict(name='public-retry',expected='reject_then_accept_twice',observed=observed,program_unchanged=before==p.to_dict(),same_engine=False)
    retry['contract_pass']=(not observed[0]['accept'] and all(x['accept'] for x in observed[1:]) and retry['program_unchanged'])
    dump(path/'result.json',retry);rows.append(retry)
    calibration=calibrate_checker(json.loads((a.out/'control-constant-nonzero-reference/response.json').read_text()))
    dump(a.out/'checker-calibration.json',calibration)
    if not calibration['passed']:raise RuntimeError('Independent checker calibration failed')
    summary=dict(checker_calibration=calibration,source_revision=None,python_source_path=str(a.source.resolve()),python_source_manifest={str(p.relative_to(a.source)):hashfile(p) for p in sorted(a.source.rglob('*.py'))},kernel=str(a.kernel.resolve()),kernel_sha256=hashfile(a.kernel),kernel_profile='caller_supplied_unknown',runner_sha256=hashfile(pathlib.Path(__file__)),results=rows,counts={'total':len(rows),'contract_pass':sum(r['contract_pass'] for r in rows),'red':sum(not r['contract_pass'] for r in rows)},limits=['Development fixtures, not original family acceptance or Spectre evidence.','Public retry uses distinct processes; same-engine rollback remains separate.','No core source changes and no kernel build.'])
    dump(a.out/'summary.json',summary);print(json.dumps(summary['counts']));print(a.out/'summary.json')
    if a.require_contract and summary['counts']['red']:raise SystemExit(1)

if __name__=='__main__':main()
