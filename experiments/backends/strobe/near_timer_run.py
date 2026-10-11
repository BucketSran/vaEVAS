"""Freeze/replay nearby timer cases and inspect actual Spectre exports.

Run Spectre with the existing callback_probe.run against the frozen inputs.
This tool does not launch remote jobs or alter simulator observations.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'evas/src'),str(ROOT/'evas/validation/strobe'),
              str(ROOT/'experiments/backends/support'),str(ROOT/'experiments/backends/paper')]
from inputs import sha,save
from near_timer import CASES,STROBES,source,assess,BUDGET_V
from precision_report import qualification


def load(path):return json.loads(path.read_text())


def verify(directory):
    for rel,digest in load(directory/'MANIFEST.json').items():
        path=(directory/rel).resolve()
        if not path.is_relative_to(directory.resolve()) or sha(path)!=digest:
            raise ValueError('artifact drift: '+rel)


def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    profiles=load(ROOT/'evas/validation/paper/precision-v1.json')['profiles']
    for case in CASES:
        for profile in profiles:
            work=output/(case['id']+'-'+profile['id']);work.mkdir()
            (work/'dut.va').write_text(source(case['held'],case['chain']))
            settings=dict(stop_s=1.,maxstep_s=profile['step_units'],reltol=profile['reltol'],
                          vabstol_V=profile['vabstol_V'],iabstol_A=profile['iabstol_A'],
                          errpreset='conservative',method='traponly')
            times=' '.join(format(t,'.17g') for t in STROBES)
            deck=('simulator lang=spectre\nahdl_include "dut.va"\nVu (u 0) vsource dc=0\ndut (u y 0) m\n'
                  f'simulatorOptions options precision="%.17g" reltol={settings["reltol"]:.17g} vabstol={settings["vabstol_V"]:.17g} iabstol={settings["iabstol_A"]:.17g}\n'
                  f'tran tran stop=1 maxstep={settings["maxstep_s"]:.17g} errpreset=conservative method=traponly strobetimes=[{times}] strobeoutput=all compression=no skipcount=1\n'
                  'save u y'+(' dut.h dut.e dut.f dut.i' if case['chain'] else '')+'\n')
            (work/'tb.scs').write_text(deck)
            for name,data in [('requested_settings.json',settings),('case.json',case),('requested_times.json',STROBES)]:save(work/name,data)
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def evas(inputs,output,kernel):
    from evas import Instance,compile_sources,transient
    verify(inputs);output.mkdir(parents=True,exist_ok=False);records=[]
    for work in sorted(p for p in inputs.iterdir() if p.is_dir()):
        case=load(work/'case.json');settings=load(work/'requested_settings.json');times=load(work/'requested_times.json')
        program=compile_sources({'dut.va':(work/'dut.va').read_text()},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
        result=transient(program,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=settings['maxstep_s'],
                         strobetimes=times,vabstol=settings['vabstol_V'],reltol=settings['reltol'],kernel=kernel)
        save(output/(work.name+'.json'),result)
        receipt=result['strobe_evidence']
        if receipt['times']!=times or receipt['sample_origins']!=['accepted_controller_frame']*len(times):
            raise ValueError('unaccepted forced phase: '+work.name)
        rows=[dict(time=t,**dict(zip(result['nodes'],v))) for t,v in zip(times,receipt['voltages_V'])]
        if case['chain']:rows=[{**row,**{k:row['dut:'+k] for k in 'hefi'}} for row in rows]
        records.append(dict(case=work.name,assessment=assess(case,rows),response_sha256=sha(output/(work.name+'.json')),
                            events=result['transient']['events'],tolerances=result.get('tolerances'),
                            engine=result.get('engine'),observation_origins=receipt['sample_origins']))
    source_files={str(p.relative_to(ROOT)):sha(p) for directory in ['evas/src/evas','evas/rust_core/src']
                  for p in sorted((ROOT/directory).glob('*')) if p.is_file()}
    save(output/'SUMMARY.json',dict(base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        kernel_sha256=sha(kernel),input_manifest_sha256=sha(inputs/'MANIFEST.json'),
        checker_sha256=sha(ROOT/'evas/validation/strobe/near_timer.py'),source_manifest=source_files,results=records))


def report(inputs,ev,sp,output):
    verify(inputs);verify(sp)
    evas_summary=load(ev/'SUMMARY.json')
    if evas_summary['input_manifest_sha256']!=sha(inputs/'MANIFEST.json'):
        raise ValueError('EVAS input identity differs')
    if evas_summary['checker_sha256']!=sha(ROOT/'evas/validation/strobe/near_timer.py'):
        raise ValueError('EVAS assessment uses a different checker')
    for result in evas_summary['results']:
        if result['response_sha256']!=sha(ev/(result['case']+'.json')):
            raise ValueError('EVAS response drift: '+result['case'])
    records=[]
    for work in sorted(p for p in inputs.iterdir() if p.is_dir()):
        actual=sp/work.name;case=load(work/'case.json');raw=load(actual/'rows.json');record=load(actual/'RESULT.json')
        if sha(work/'dut.va')!=sha(actual/'dut.va') or sha(work/'tb.scs')!=sha(actual/'tb.scs'):
            raise ValueError('reference differs from frozen input')
        rows=raw if not case['chain'] else [{**r,**{k:r['dut.'+k] for k in 'hefi'}} for r in raw]
        r=dict(case=work.name,assessment=assess(case,rows),qualification=qualification(actual,'spectre',record,raw),
               source_sha256=sha(work/'dut.va'),deck_sha256=sha(work/'tb.scs'),
               native_sha256=sha(actual/'psf/tran.tran.tran'),receipt_sha256=sha(actual/'RESULT.json'))
        records.append(r)
    tool=load(sp/'TOOL_IDENTITY.json')
    save(output,dict(schema_version=1,denominator=12,voltage_budget_V=BUDGET_V,
        scope='finite native/forced observations; full boundary records retained; no complete-trajectory proof',
        input_manifest_sha256=sha(inputs/'MANIFEST.json'),checker_sha256=sha(ROOT/'evas/validation/strobe/near_timer.py'),
        reader_sha256=sha(ROOT/'experiments/backends/paper/observations.py'),analysis_sha256=sha(Path(__file__)),
        spectre_tool={k:tool[k] for k in ('binary_sha256','version','versions') if k in tool},
        spectre_tool_identity_sha256=sha(sp/'TOOL_IDENTITY.json'),spectre=records,evas=evas_summary,
        availability='repository-contained recipes/summary; raw outputs and full logs local-only'))
    for r in records:print(r['case'],r['assessment']['status'],r['qualification']['status'],r['assessment']['maximum_nominal_error_V'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='mode',required=True)
    f=sub.add_parser('freeze');f.add_argument('output',type=Path)
    e=sub.add_parser('evas');e.add_argument('inputs',type=Path);e.add_argument('output',type=Path);e.add_argument('--kernel',type=Path,required=True)
    r=sub.add_parser('report');r.add_argument('inputs',type=Path);r.add_argument('evas',type=Path);r.add_argument('spectre',type=Path);r.add_argument('output',type=Path)
    a=parser.parse_args()
    if a.mode=='freeze':freeze(a.output)
    elif a.mode=='evas':evas(a.inputs,a.output,a.kernel)
    else:report(a.inputs,a.evas,a.spectre,a.output)
