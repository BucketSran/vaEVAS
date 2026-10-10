"""Prepare or execute the bounded sample/edge/filter comparison.

Spectre runs serially with the maintained process/identity/readback helpers.
No automatic retries. Every new execution requires a new output directory.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/backends/paper'),str(ROOT/'evas/validation/sample_edge_filter')]
from inputs import sha,save,decks
from runner import preflight,verify_tool,stage,effective_settings,stage_failure
from observations import read_native
from contract import CASES,T,STOP,INPUT,CLOCK,RESET,source,times,assess
LIMITS=dict(stage_timeout_s=90,license_timeout_s=30,memory_limit_bytes=4*1024**3,file_limit_bytes=32*1024**2,threads=1)
SETTINGS={'base':(1e-5,1e-7,T/64),'tight':(1e-9,1e-11,T/64),'fine':(1e-9,1e-11,T/256)}


def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'cases.json',CASES)
    for c in CASES:
        src=source(c)
        ports=['u','clk','rst',*[p['name']+x for p in c['instances'] for x in 'hefn']]
        stimuli={n:{'points_s_V':[[t*T,v] for t,v in points]} for n,points in [('u',INPUT),('clk',CLOCK),('rst',RESET)]}
        for setting,(rt,at,step) in SETTINGS.items():
            work=output/c['id']/setting;work.mkdir(parents=True)
            settings=dict(stop_s=STOP,maxstep_s=step,spice_maxstep_s=step,reltol=rt,vabstol_V=at,iabstol_A=at*1e-4)
            ts=times(c)
            # Only requested native strobes. No disconnected observer source.
            generated=decks(dict(id=c['id'],stimulus=stimuli),settings,dict(ports=ports,top_module='dut',parameters={}),ts,dict(records=[]))
            text=generated['spectre'][1]
            text='\n'.join(line for line in text.splitlines() if not line.startswith('Vpaper_observer'))+'\n'
            text=text.replace('simulatorOptions options ','simulatorOptions options precision="%.17g" ')
            text=text.replace('strobeoutput=all','strobeoutput=all compression=no skipcount=1')
            (work/'dut.va').write_text(src)
            (work/'tb.scs').write_text(text)
            save(work/'requested_settings.json',settings)
            save(work/'requested_times.json',ts)
            save(work/'request.json',dict(source='dut.va',instances=[dict(name='dut',module='dut',ports={p:p for p in ports},parameters={})],inputs={n:s['points_s_V'] for n,s in stimuli.items()},stop=STOP,max_step=step,vabstol=1e-7,reltol=0))
    save(output/'INPUT_MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def verify(inputs):
    for name,digest in json.loads((inputs/'INPUT_MANIFEST.json').read_text()).items():
        if sha(inputs/name)!=digest:raise ValueError('input changed: '+name)


def spectre(inputs,output,profile):
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'STARTED.json',dict(limits=LIMITS,conditions=4,configurations=12,automatic_retries=0,input_manifest_sha256=sha(inputs/'INPUT_MANIFEST.json')))
    profile=json.loads(profile.read_text())
    tool,env=preflight('spectre',profile,output,LIMITS)
    save(output/'TOOL_IDENTITY.json',tool)
    records=[]
    for c in CASES:
        for setting in SETTINGS:
            verify(inputs);verify_tool(tool,profile,env)
            work=output/c['id']/setting;shutil.copytree(inputs/c['id']/setting,work)
            (work/'run.csh').write_text(tool['setup']+tool['binary']+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
            result=stage(['/bin/csh','-f','run.csh'],work,'simulate',LIMITS)
            rec=dict(case=c['id'],setting=setting,execution=result,source_sha256=sha(work/'dut.va'),deck_sha256=sha(work/'tb.scs'))
            raw=work/'psf/tran.tran.tran'
            if not stage_failure(result) and raw.exists():
                try:
                    rows=read_native(raw,'spectre');save(work/'rows.json',rows)
                    rec.update(raw_sha256=sha(raw),assessment=assess(c,rows),effective_settings=effective_settings(work,'spectre'))
                except Exception as e:
                    rec['assessment']=dict(status='ANALYSIS_FAILURE',reason=str(e))
            else:rec['assessment']=dict(status='EXECUTION_FAILURE')
            save(work/'RESULT.json',rec);records.append(rec)
            print(c['id'],setting,rec['assessment']['status'],flush=True)
            if not result.get('cleanup',{}).get('complete',False):raise RuntimeError('incomplete process cleanup')
    save(output/'RESULTS.json',records)
    save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def evas(inputs,output,kernel,spectre_root=None):
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import Instance,compile_sources,transient
    save(output/'IDENTITY.json',dict(kernel_sha256=sha(kernel),kernel_identity=subprocess.check_output([str(kernel.resolve()),'--version','--json'],text=True),source={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'evas/src').rglob('*.py'))}))
    records=[]
    for c in CASES:
        work=inputs/c['id']/'base';req=json.loads((work/'request.json').read_text())
        inst=[Instance(i['name'],i['module'],i['ports'],i['parameters']) for i in req['instances']]
        compile_error=None
        try:p=compile_sources({'dut.va':(work/'dut.va').read_text()},inst)
        except Exception as e:compile_error=str(e)
        grids={'sparse':times(c),'dense':times(c,True)}
        if spectre_root:
            for setting in SETTINGS:
                path=spectre_root/c['id']/setting/'rows.json'
                if path.exists():grids['native-'+setting]=[r['time'] for r in json.loads(path.read_text())]
        for name,ts in grids.items():
            dest=output/c['id']/name;dest.mkdir(parents=True)
            save(dest/'times.json',ts)
            try:
                if compile_error is not None:raise ValueError('compile: '+compile_error)
                response=transient(p,req['inputs'],ts,stop=STOP,max_step=req['max_step'],vabstol=req['vabstol'],reltol=0,kernel=kernel,timeout=90)
                save(dest/'response.json',response)
                rows=[dict(time=t,**dict(zip(response['nodes'],r['voltages']))) for t,r in zip(response['transient']['times'],response['solutions'],strict=True)]
                save(dest/'rows.json',rows)
                rec=dict(case=c['id'],grid=name,assessment=assess(c,rows),response_sha256=sha(dest/'response.json'))
            except Exception as e:rec=dict(case=c['id'],grid=name,assessment=dict(status='EXECUTION_FAILURE',reason=str(e)))
            save(dest/'RESULT.json',rec);records.append(rec)
            print(c['id'],name,rec['assessment']['status'],flush=True)
    save(output/'RESULTS.json',records)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','spectre','evas']);a.add_argument('inputs',type=Path);a.add_argument('--output',type=Path);a.add_argument('--profile',type=Path);a.add_argument('--kernel',type=Path);a.add_argument('--spectre-root',type=Path)
    args=a.parse_args()
    if args.mode=='freeze':freeze(args.inputs)
    elif args.mode=='spectre':spectre(args.inputs,args.output,args.profile)
    else:evas(args.inputs,args.output,args.kernel,args.spectre_root)
