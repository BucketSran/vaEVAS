"""Freeze the two reviewed v3 sources; share bounded serial execution adapters.

This adds separate identities, never edits historical inputs, and does not grade
execution success. Q targets select controls before execution; report separately.
"""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from inputs import decks, save, sha
from precision_binding_run import recipe, TRACE
from precision_breadth_run import run, TIER_PROFILES
from precision_run import source_files
from precision_v2 import load_contract
from precision_breadth import load_contract as breadth_contract, observation_plan
from breadth_callback_trace import instrument
from root_windows import reference_roots


def observation_deck(text):
    """Reject a missing/duplicate calibration marker before freezing a run."""
    if text.count(' precision="%.17g"')!=1 or text.count('tran tran ')!=1:
        raise ValueError('missing or ambiguous Spectre observation calibration marker')
    return text.replace(' precision="%.17g"',' precision="%.17g" digits=17 notation=sci').replace(
        'tran tran ','tran tran transres=1e-20 ')


def ec04_recipe(card,profile,backend,trace):
    data=breadth_contract();observation=observation_plan(card,data);times=observation['times_s']
    settings={**profile,'stop_s':card['stop_s'],'maxstep_s':card['unit_s']*profile['step_units'],
              'spice_maxstep_s':card['unit_s']*profile['step_units']}
    physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
    bind={'top_module':card['top'],'ports':card['ports'],'parameters':card['parameters']}
    filename,text=decks(physical,settings,bind,times,{'records':[{'time_s':t} for t in times]})[backend]
    if backend=='spectre':
        text='\n'.join(line+' precision="%.17g"' if line.startswith('simulatorOptions ') else
            line+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else
            line for line in text.splitlines())+'\n'
    source=instrument(card,format_version=2)[0] if trace else card['source']
    return {filename:text,'dut.va':source,'condition.json':card,'requested_settings.json':settings,
            'requested_times.json':times,'observation_plan.json':observation}


def freeze(output):
    data=load_contract();breadth=breadth_contract();profiles={p['id']:p for p in data['profiles']}
    cards=[next(c for c in data['cards'] if c['id']=='SH-X-RAMP'),
           next(c for c in breadth['cards'] if c['id']=='EC04-v1')]
    output.mkdir(parents=True,exist_ok=False)
    for sub,trace in [('original',False),('trace',True)]:
        base=output/sub;base.mkdir();plan=[]
        mapping={b:dict(TIER_PROFILES) for b in ('evas','spectre')}
        mapping['spectre']['Q3']='deep_bound'
        candidates={**profiles,'deep_bound':{**profiles['deep'],'id':'deep_bound','step_units':.0004}}
        observation_controls={'spectre_digits':17,'spectre_notation':'sci',
                              'spectre_precision':'%.17g','spectre_transres_s':1e-20}
        for tier,pid in list(mapping['spectre'].items()):
            name=pid+'_native_v3'
            candidates[name]={**candidates[pid],'id':name,**observation_controls}
            mapping['spectre'][tier]=name
        save(base/'cards.json',{**data,'cards':cards,'profiles':list(candidates.values())})
        save(base/'PROFILE_BINDINGS.json',{'schema_version':'root-window-v3',
             'backend_tier_profiles':mapping,'profiles':candidates})
        save(base/'ORIGINAL_CONTRACTS.json',{'precision_v2':data,'breadth':breadth})
        for card in cards:
            reference_roots(card) # fail before any run on unreviewed source/contract
            for backend in (('spectre',) if trace else ('evas','spectre')):
                for tier in TIER_PROFILES:
                    profile=candidates[mapping[backend][tier]]
                    files=(recipe(card,profile,backend,callback_trace=trace) if card['id']=='SH-X-RAMP'
                           else ec04_recipe(card,profile,backend,trace))
                    # Readback calibration is fixed before execution; no numeric
                    # control or observation request changes are introduced here.
                    if backend=='spectre':
                        files['tb.scs']=observation_deck(files['tb.scs'])
                    label=card['id']+'--'+tier;work=base/'runs'/backend/label;work.mkdir(parents=True)
                    for name,value in files.items():
                        if isinstance(value,str):(work/name).write_text(value)
                        else:save(work/name,value)
                    deck='request.json' if backend=='evas' else 'tb.scs'
                    plan.append({'condition':card['id'],'group_id':card['id'],'tier':tier,
                        'profile':profile['id'],'family':'root-window-v3','backend':backend,'label':label,
                        'callback_trace':trace,'work':str(work.relative_to(base)),'deck':deck,
                        'source_sha256':sha(work/'dut.va')})
        save(base/'PLAN.json',plan)
        paths=set(source_files())|{Path(__file__),ROOT/'experiments/backends/support/precision_binding_run.py',
            ROOT/'experiments/backends/support/precision_breadth_run.py',
            ROOT/'experiments/backends/support/breadth_callback_trace.py',
            ROOT/'experiments/backends/support/root_callback_evidence.py',
            ROOT/'experiments/backends/support/root_window_report.py',
            ROOT/'experiments/backends/support/callback_evidence.py',
            ROOT/'experiments/backends/support/spectre_callback_evidence.py',
            ROOT/'experiments/backends/support/precision_binding_evidence.py',
            ROOT/'evas/validation/paper/precision-v2.json',ROOT/'evas/validation/paper/precision-root-v3.json'}
        save(base/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)})
        save(base/'MANIFEST.json',{str(p.relative_to(base)):sha(p) for p in sorted(base.rglob('*')) if p.is_file()})
    return {'original':12,'trace':6,'claim':'new attempts; original histories and budgets preserved'}


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path)
    r=s.add_parser('run');r.add_argument('inputs',type=Path);r.add_argument('output',type=Path)
    r.add_argument('--backend',choices=('evas','spectre'),required=True)
    r.add_argument('--profile',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='freeze':print(freeze(a.output.resolve()))
    else:run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),'root-window-v3',defer_analysis=True)
