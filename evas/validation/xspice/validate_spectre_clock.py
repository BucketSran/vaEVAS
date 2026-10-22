"""Freeze/admit fixed P1 same-source native references; no remote dispatch."""

import argparse
import json
from pathlib import Path
import shutil

from clock_cases import CASES, BUDGETS
from clock_reference import score_wave, native_states, pair
from validate_clock import analyze_run
from check import read_ng, read_spectre
from validate import sha
from validate_spectre_r53 import admit, selection_verdict

CHECKERS=('clock_cases.py','clock_reference.py','validate_clock.py','calibrate_clock.py',
          'validate_spectre_clock.py','check.py','validate_spectre_r53.py','trace_files.py')


def freeze(phase,local):
    phase,local=Path(phase).resolve(),Path(local).resolve();batch=phase/'batch01';batch.mkdir(exist_ok=False)
    protocol={'fixed_denominator':len(CASES),'cases':{},'budgets':BUDGETS,'availability':'local-only',
              'checker_sha256':{n:sha(Path(__file__).parent/n) for n in CHECKERS}}
    for case in CASES:
        d=batch/'spectre'/case;shutil.copytree(local/'spectre'/case,d)
        ng=local/(case+'-normal')
        names=['wave.raw','contract.json','execution.json',*[f.name for f in ng.glob('trace-*.csv.gz')]]
        protocol['cases'][case]={'sources':sorted(f.name for f in d.glob('*.va')),
                                'files':{f.name:sha(f) for f in d.iterdir() if f.is_file() and f.name!='preparation.json'},
                                'ng_directory':str(ng),'ng_files':{n:sha(ng/n) for n in names}}
    shutil.copy2(Path(__file__).parent/'run_spectre_remote.py',batch/'runner.py')
    (batch/'input-manifest.json').write_text(json.dumps({str(f.relative_to(batch)):sha(f) for f in (batch/'spectre').rglob('*') if f.is_file()},indent=2)+'\n')
    (phase/'protocol01.json').write_text(json.dumps(protocol,indent=2)+'\n')


def analyze(phase,output,cases,protocol_path):
    phase,output=Path(phase).resolve(),Path(output).resolve();output.mkdir(exist_ok=False)
    protocol_path=Path(protocol_path).resolve() if protocol_path else phase/'protocol01.json'
    protocol=json.loads(protocol_path.read_text())
    if any(sha(Path(__file__).parent/n)!=h for n,h in protocol['checker_sha256'].items()):
        raise ValueError('frozen P1 checker identity differs')
    results={}
    for case in cases:
        spec=protocol['cases'][case];d=phase/'batch01/spectre'/case
        try:
            identity=admit(d,spec);ngdir=Path(spec['ng_directory'])
            if any(sha(ngdir/n)!=h for n,h in spec['ng_files'].items()):raise ValueError('NG raw identity differs')
            if (ngdir/'contract.json').read_bytes()!=(d/'contract.json').read_bytes():raise ValueError('contract differs')
            cfg=json.loads((d/'contract.json').read_text());ng=read_ng(ngdir/'wave.raw');native=read_spectre(d/'psf/tran.tran.tran')
            local=analyze_run(ngdir,cfg,'normal',ngdir)
            physical=score_wave(native,cfg);states=native_states(native,cfg);state_pairs={}
            for key,b in states['states'].items():
                tag,name=key.split(':');a=local['traces'][tag]['states'][name];x,y=a['observed'],b['observed'];same=len(x)==len(y)
                dt=max((abs(q[0]-r[0]) for q,r in zip(x,y)),default=0) if same else None
                dv=max((abs(q[1]-r[1]) for q,r in zip(x,y)),default=0) if same else None
                initial=abs(a['initial']-b['initial'])
                state_pairs[key]={'passed':same and dt<=BUDGETS['pair_event_s'] and dv<=BUDGETS['pair_platform_V'] and initial<=BUDGETS['pair_platform_V'],
                                  'max_time_s':dt,'max_state_V':dv,'initial_difference_V':initial}
            paired=pair(ng,native,cfg)
            result={'passed':local['passed'] and physical['passed'] and states['passed'] and all(x['passed'] for x in state_pairs.values()) and paired['passed'],
                    'ng':local,'physical':physical,'states':states,'state_pairs':state_pairs,'continuous_pair':paired,'identity':identity}
        except (OSError,ValueError,KeyError,StopIteration) as exc:
            result={'passed':False,'error':str(exc)}
        results[case]=result;(output/(case+'.json')).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(case,result['passed'],result.get('error',''),flush=True)
    equivalence=None
    if all(c in results and results[c]['passed'] for c in ('binary','reverse')):
        cfg=json.loads((phase/'batch01/spectre/binary/contract.json').read_text());equivalence={}
        for engine in ('ngspice','spectre'):
            waves=[read_ng(Path(protocol['cases'][c]['ng_directory'])/'wave.raw') if engine=='ngspice' else read_spectre(phase/'batch01/spectre'/c/'psf/tran.tran.tran') for c in ('binary','reverse')]
            equivalence[engine]=pair(*waves,cfg)
    verdict=selection_verdict(results,cases,protocol)
    if verdict['complete_selection']:verdict['passed']=verdict['passed'] and equivalence is not None and all(r['passed'] for r in equivalence.values())
    final={**verdict,'fixed_denominator':protocol['fixed_denominator'],'cases':results,'declaration_order_equivalence':equivalence,
           'protocol_sha256':sha(protocol_path),'new_simulator_runs_in_analysis':0}
    (output/'analysis.json').write_text(json.dumps(final,indent=2,allow_nan=False)+'\n');return final


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--local');p.add_argument('--output');p.add_argument('--protocol');p.add_argument('--cases',default=','.join(CASES));a=p.parse_args()
    if a.prepare:freeze(a.phase,a.local)
    else:raise SystemExit(0 if analyze(a.phase,a.output,a.cases.split(','),a.protocol)['passed'] else 1)
