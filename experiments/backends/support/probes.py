"""Freeze/run bounded four-backend feature probes; never changes a simulator.

Reuses the maintained paper adapter's native deck generation, process cleanup,
tool identity probes and format readers, but not the paper's qualification gate.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'experiments/backends/paper'))
from inputs import BACKENDS, decks, sha, save
from runner import preflight, verify_tool, stage, stage_failure, container_stage, result_state, effective_settings
from observations import read_native
sys.path.insert(0, str(ROOT/'evas/validation/support'))
from checker import assess


def freeze(output, cards_path=None, gnucap_time_bits=None):
    if gnucap_time_bits is not None and (type(gnucap_time_bits) is not int or not 1 <= gnucap_time_bits <= 40):
        raise ValueError('gnucap_time_bits must be an integer from 1 to 40')
    data = json.loads((cards_path or ROOT/'evas/validation/support/cases-v2.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    save(output/'cards.json', data)
    for c in data['cards']:
        unit, stop = c['unit_s'], c['stop_x']*c['unit_s']
        times = [i*c['grid_x']*unit for i in range(round(c['stop_x']/c['grid_x'])+1)]
        points = sorted(set([0., stop, *times, *(x*unit for p in c['inputs'].values() for x, _ in p)]))
        breakpoints = {'records': [{'time_s': t} for t in points]}
        settings = dict(stop_s=stop, maxstep_s=c['maxstep_x']*unit, spice_maxstep_s=c['maxstep_x']*unit,
                        reltol=1e-7, vabstol_V=1e-9, iabstol_A=1e-13)
        import re
        declared = re.search(r'module\s+'+c['top']+r'\s*\(([^)]+)\)', c['source'])
        ports = [n.strip() for n in declared[1].split(',')]
        assert set(ports) == set(c['inputs']) | set(c['outputs'])
        bind = dict(ports=ports, top_module=c['top'], parameters=c['parameters'])
        card = dict(id=c['id'], stimulus={n: {'points_s_V': [[x*unit,v] for x,v in p]} for n,p in c['inputs'].items()})
        for backend, (filename, text) in decks(card,settings,bind,times,breakpoints).items():
            work = output/backend/c['id']; work.mkdir(parents=True)
            backend_settings = dict(settings)
            if backend == 'gnucap_modelgen' and gnucap_time_bits is not None:
                # Gnucap quantizes physical time using dtmin. Keep the model,
                # stimulus, observation grid and checker fixed; record a new
                # solver setting rather than rounding observations into place.
                quantum = unit / 2**gnucap_time_bits
                assert text.count('dtmin=1e-15') == 1
                text = text.replace('dtmin=1e-15', f'dtmin={quantum:.17g}')
                backend_settings['gnucap_dtmin_s'] = quantum
            (work/'dut.va').write_text(c['source'])
            (work/filename).write_text(text)
            save(work/'requested_times.json', times)
            save(work/'requested_settings.json', backend_settings)
    paths = [*(ROOT/'evas/validation/support').glob('*.py'), *Path(__file__).parent.glob('*.py'), * (ROOT/'experiments/backends/paper').glob('*.py'),
             ROOT/'experiments/archive/dvs2-starter-pilot/analyze.py', ROOT/'experiments/archive/dvs2-starter-pilot/suite.py',
             ROOT/'experiments/backends/dvs2-spectre-validation/report.py']
    save(output/'ADAPTER_IDENTITY.json', {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)})
    save(output/'INPUT_MANIFEST.json', {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def verify(inputs):
    manifest = json.loads((inputs/'INPUT_MANIFEST.json').read_text())
    assert set(manifest) == {str(p.relative_to(inputs)) for p in inputs.rglob('*') if p.is_file() and p.name != 'INPUT_MANIFEST.json'}
    for rel, digest in manifest.items():
        assert sha(inputs/rel) == digest, rel
    for rel, digest in json.loads((inputs/'ADAPTER_IDENTITY.json').read_text()).items():
        assert sha(ROOT/rel) == digest, rel


def run(inputs, output, backend, profile_path):
    verify(inputs)
    profile = json.loads(profile_path.read_text())
    a = dict(stage_timeout_s=90,license_timeout_s=30,memory_limit_bytes=4*1024**3,file_limit_bytes=32*1024**2,threads=1)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'STARTED.json',dict(backend=backend,input_manifest_sha256=sha(inputs/'INPUT_MANIFEST.json'),profile_sha256=sha(profile_path),limits=a,automatic_retries=0))
    tool, env = preflight(backend,profile,output,a)
    save(output/'TOOL_IDENTITY.json',tool)
    results=[]
    for c in json.loads((inputs/'cards.json').read_text())['cards']:
        verify(inputs); verify_tool(tool,profile,env)
        work=output/'runs'/c['id']; shutil.copytree(inputs/backend/c['id'],work)
        stages=[]; compiled=None; wr=None
        if backend=='evas':
            wave='waveform.csv'
            stages.append(stage([sys.executable,'-B',str(ROOT/'experiments/backends/paper/runner.py'),'worker',str(work),tool['kernel']],work,'simulate',a))
            wr=json.loads((work/'worker-result.json').read_text()) if (work/'worker-result.json').exists() else {'status':'execution_failed','reason':'no worker result'}
        elif backend=='spectre':
            wave='psf/tran.tran.tran'
            (work/'run.csh').write_text(tool['setup']+tool['binary']+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
            stages.append(stage(['/bin/csh','-f','run.csh'],work,'simulate',a))
        else:
            wave='waveform.txt'
            if backend=='openvaf_r_ngspice':
                compiled='dut.osdi'
                stages.append(container_stage(env,tool['images']['openvaf_runtime']['config_id'],'/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',['dut.va','-o',compiled],work,'compile',a))
                image=tool['images']['ngspice']['config_id']; executable='/opt/ngspice/bin/ngspice'; arguments=['-b','tb.cir']
            else:
                compiled='dut.so'; image=tool['images']['gnucap']['config_id']
                cmd='/opt/gnucap/bin/gnucap-mg-vams -I /opt/gnucap/include/gnucap -o dut.cc --cc dut.va && /usr/bin/c++ -std=c++14 -I /opt/gnucap/include/gnucap -fPIC -shared dut.cc -o dut.so'
                stages.append(container_stage(env,image,'/bin/sh',['-c',cmd],work,'compile',a))
                executable='/opt/gnucap/bin/gnucap'; arguments=['tb.gc']
            if not stage_failure(stages[-1]) and (work/compiled).is_file():
                stages.append(container_stage(env,image,executable,arguments,work,'simulate',a))
        state=result_state(stages,work,wave,compiled,wr,backend=backend)
        result=dict(condition=c['id'],backend=backend,**state,stages=stages,source_sha256=sha(work/'dut.va'))
        if state['status']=='waveform_available':
            try:
                rows=read_native(work/wave,backend)
                if backend=='gnucap_modelgen' and any(abs(r.get('bench_ref',float('inf')))>1e-7 for r in rows):
                    raise ValueError('invalid ground alias')
                save(work/'rows.json',rows)
                result['assessment']=assess(c,rows)
                result['rows_sha256']=sha(work/'rows.json')
            except (ValueError,KeyError,TypeError,OSError,IndexError) as e:
                result['assessment']={'status':'observation_invalid','reason':str(e)}
            try:
                result['effective_settings']=effective_settings(work,backend)
            except (ValueError,KeyError,TypeError,OSError) as e:
                result['effective_settings']={'status':'unknown','reason':str(e)}
        save(work/'RESULT.json',result); results.append(result)
        print(backend,c['id'],state['status'],result.get('assessment',{}).get('status'),flush=True)
        if state['abort_batch']:
            raise RuntimeError('cleanup incomplete; batch stopped')
    save(output/'EXECUTION.json',results)
    save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','run']);ap.add_argument('inputs',type=Path)
    ap.add_argument('--cards',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--backend',choices=BACKENDS);ap.add_argument('--profile',type=Path)
    ap.add_argument('--gnucap-time-bits',type=int,help='freeze only: dtmin = case unit / 2**bits; does not change the checker')
    args=ap.parse_args()
    if args.action=='freeze':freeze(args.inputs,args.cards,args.gnucap_time_bits)
    elif args.gnucap_time_bits is not None:ap.error('--gnucap-time-bits is a freeze-only setting')
    else:run(args.inputs,args.output,args.backend,args.profile)
