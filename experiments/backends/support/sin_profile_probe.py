"""Freeze a Q3 sine control-floor calibration without changing its checker.

Only voltage absolute tolerance varies. Source, input, stop, observation plan,
relative tolerance and external Q3 acceptance stay fixed. Historical executions
and the existing precision binding are never overwritten.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from primitives import cards, T, TIERS
from inputs import decks, save, sha


def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    card=next(c for c in cards() if c['id']=='P-sin')
    times=sorted({i*T/16 for i in range(round(card['stop_s']/T)*16+1)} |
                 {t for t,v in card['inputs']['u'] if 0<=t<=card['stop_s']})
    profile=next(p for p in json.loads((ROOT/'evas/validation/paper/precision-v2.json').read_text())['profiles']
                 if p['id']=='deep')
    plan=[]
    for floor in (1e-14,1e-13,1e-12):
        settings={**profile,'target_tier':'Q3','vabstol_V':floor,'step_units':.03125,
                  'stop_s':card['stop_s'],'maxstep_s':T/32,'spice_maxstep_s':T/32}
        physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
        generated=decks(physical,settings,{'top_module':card['top'],'ports':card['ports'],'parameters':{}},
                        times,{'records':[{'time_s':t} for t in times]})
        for backend in ('evas','spectre'):
            label='P-sin--Q3-vabstol-'+format(floor,'.0e')
            work=output/'runs'/backend/label;work.mkdir(parents=True)
            filename,text=generated[backend]
            if backend=='spectre':
                for prefix in ('simulatorOptions ','tran tran '):
                    if sum(line.startswith(prefix) for line in text.splitlines())!=1:
                        raise ValueError('unexpected Spectre insertion target')
                text='\n'.join(line+' precision="%.17g" digits=17 notation=sci'
                    if line.startswith('simulatorOptions ') else
                    line+' skipcount=1 compression=no annotate=steps annotatedigits=16'
                    if line.startswith('tran tran ') else line for line in text.splitlines())+'\n'
            (work/filename).write_text(text);(work/'dut.va').write_text(card['source'])
            for name,value in [('condition.json',card),('requested_settings.json',settings),
                               ('requested_times.json',times)]:save(work/name,value)
            plan.append({'label':label,'condition':card['id'],'backend':backend,'tier':'Q3',
                         'work':str(work.relative_to(output)),'deck':filename})
    save(output/'PLAN.json',plan)
    save(output/'CONTRACT.json',{'id':'sin-Q3-voltage-floor-calibration-v1','cards':[card],
         'budgets_V':TIERS,'target_tier':'Q3','varied_control':'vabstol only',
         'floors_V':[1e-14,1e-13,1e-12],'historical_criteria':'unchanged',
         'selection_rule':'retain all attempts; lowest floor passing original Q3 and evidence audit is the calibrated candidate'})
    sources=set()
    for directory,patterns in [('evas',('*.py','*.rs','Cargo.toml','Cargo.lock')),
                              ('experiments/backends/paper',('*.py',)),
                              ('experiments/backends/support',('*.py',)),
                              ('experiments/backends/evidence',('legacy_waveforms.py',)),
                              ('evas/validation/paper',('precision-v2.json',))]:
        for pattern in patterns:
            sources.update(p for p in (ROOT/directory).rglob(pattern)
                           if 'target' not in p.parts and '__pycache__' not in p.parts)
    save(output/'SOURCE_IDENTITY.json',{'checkpoint':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         'scope':'unchanged checkpoint EVAS; separately hashed calibration tools',
         'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(sources)}})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()})
    print(json.dumps({'positions':len(plan),'manifest_sha256':sha(output/'MANIFEST.json')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    freeze(parser.parse_args().output)
