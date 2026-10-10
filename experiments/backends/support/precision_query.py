"""Append ordinary-query diagnostics for the three timer cards rejected by strobe.

The DUT, times, budgets, four profiles and kernel are unchanged. This is a new
observation configuration, never an edit to an earlier failed run.
"""
import json
from pathlib import Path
import shutil
import sys

from precision_run import ROOT, LIMITS, load, verify
from runner import preflight, verify_tool, stage, stage_failure, effective_settings, directory_budget
from inputs import save, sha
from observations import read_native
from precision_checker import assess


def run(inputs, output, profile_path):
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    profile=load(profile_path);data=load(inputs/'cards.json')
    selected=[r for r in load(inputs/'PLAN.json') if r['backend']=='evas' and r['condition'] in ('SH-T-RAMP','SH-T-SMALL','SH-T-LONG')]
    save(output/'STARTED.json',{'observation_mode':'ordinary physical-state query; no forced solve claim',
        'input_manifest_sha256':sha(inputs/'MANIFEST.json'),'driver_sha256':sha(Path(__file__)),
        'profile_sha256':sha(profile_path),'selected':selected,'limits':LIMITS})
    results=[]
    try:
        tool,env=preflight('evas',profile,output,LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for row in selected:
            verify(inputs);verify_tool(tool,profile,env)
            work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
            process=stage([sys.executable,'-B',str(ROOT/'experiments/backends/paper/runner.py'),'worker',str(work),tool['kernel']],work,'simulate',LIMITS)
            failure=stage_failure(process)
            receipt=load(work/'worker-result.json') if (work/'worker-result.json').is_file() else {'status':'execution_failed'}
            result={**row,**(failure or receipt),'stages':[process],'observation_mode':'ordinary-query'}
            if result['status']=='waveform_available':
                raw=load(work/'raw-response.json');origins=raw.get('observation_evidence',{}).get('sample_origins',[])
                ts=load(work/'requested_times.json');actual=read_native(work/'waveform.csv','evas')
                qualified=(raw.get('transient',{}).get('times')==ts and len(origins)==len(ts) and
                           all(o in ('accepted_controller_frame','certified_causal_frame') for o in origins))
                result['observation_qualification']={'status':'qualified' if qualified else 'evidence_insufficient','origins':sorted(set(origins)),
                    'basis':'physical_order_at chooses one stage at this request time; ambiguity rejects; no interpolation across a jump',
                    'claim':'physical-state query, not native accepted solver point or successful strobe'}
                result['assessment']=assess(load(work/'condition.json'),actual,data['budgets'])
                result['effective_settings']=effective_settings(work,'evas');result['waveform']='waveform.csv';result['waveform_sha256']=sha(work/'waveform.csv')
            result['directory_budget']=directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            print(json.dumps({'case':row['label'],'execution':result['status'],'assessment':result.get('assessment',{}).get('status')}),flush=True)
            if failure and failure.get('abort_batch') or result['directory_budget']['status']!='within_limit':break
    finally:
        known={r['label'] for r in results}
        results.extend({**r,'status':'not_run'} for r in selected if r['label'] not in known)
        save(output/'EXECUTION.json',results)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()})

if __name__=='__main__':run(*(Path(s).resolve() for s in sys.argv[1:]))
