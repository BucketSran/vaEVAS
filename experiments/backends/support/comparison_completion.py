"""Complete previously unrun fixed-table combinations without changing their oracles.

Uses the original SEF, timer-composition and nearby-timer source generators.
Execution and scientific assessment are separate. New runs never replace old scores.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'experiments/backends/support'),
                str(ROOT/'experiments/backends/paper'),
                str(ROOT/'evas/validation/strobe')]
import precision_run as execution
from inputs import decks, sha, save
from observations import read_native, READER_DEPENDENCIES
import timer_composition as timer
import near_timer as nearby

BACKENDS = ('openvaf_r_ngspice', 'gnucap_modelgen')


def load(path):
    return json.loads(path.read_text())


def checkpoint(path, data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n')
    temporary.replace(path)


def cases():
    sef = timer.sef
    stimulus = {n:[[t*sef.T,v] for t,v in points]
                for n,points in [('u',sef.INPUT), ('clk',sef.CLOCK), ('rst',sef.RESET)]}
    records = []
    for case in sef.CASES:
        ports = ['u','clk','rst',*[p['name']+x for p in case['instances'] for x in 'hefn']]
        base = dict(case=case, source=sef.source(case), inputs=stimulus,
                    binding=dict(top_module='dut', ports=ports, parameters={}),
                    stop_s=sef.STOP, unit_s=sef.T)
        records.append(dict(base, id=case['id'], family='sef', times=sef.times(case)))
        if case['id'] != 'SEF-RESET':
            records.append(dict(base, id='ST:'+case['id'], family='timer-composition',
                                times=sef.times(case,True)))
    integral = timer.INTEGRAL
    records.append(dict(id=integral['id'], case=integral, source=integral['source'],
                        family='timer-composition', inputs=integral['inputs'],
                        binding=dict(top_module=integral['top'], ports=integral['ports'],
                                     parameters=integral['parameters']),
                        stop_s=sef.STOP, unit_s=sef.T, times=execution.times_for(integral)))
    for case in nearby.CASES:
        records.append(dict(id='NT:'+case['id'], case=case, family='nearby-timer',
                            source=nearby.source(case['held'],case['chain']),
                            inputs={'u':[[0.,0.],[1.,0.]]},
                            binding=dict(top_module='m',ports=['u','y','0'],parameters={}),
                            stop_s=1.,unit_s=1.,times=nearby.STROBES))
    if len(records) != 11 or len({r['id'] for r in records}) != 11:
        raise ValueError('fixed completion scope changed')
    return records


def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    profile = next(p for p in load(ROOT/'evas/validation/paper/precision-v2.json')['profiles']
                   if p['id']=='deep')
    plan = []
    for card in cases():
        settings = dict(profile, stop_s=card['stop_s'],
                        maxstep_s=card['unit_s']*profile['step_units'],
                        spice_maxstep_s=card['unit_s']*profile['step_units'],
                        target='original engineering budget; no new Q-tier claim')
        physical = dict(id=card['id'],stimulus={n:{'points_s_V':p} for n,p in card['inputs'].items()})
        # The disconnected observer requests the existing observation times.
        # It shares only ground with the DUT and is a solver-grid control.
        points = sorted(set(card['times']))
        if card['family']=='nearby-timer':
            # Keep all original observations. The auxiliary PWL only requests
            # their neighborhoods, as allowed by this card's 16-ulp contract.
            # Adjacent-double source corners are not representable by both
            # SPICE source parsers; keep the nominal .3 corner in this cluster.
            points=[t for t in points if t==.3 or abs(t-.3)>4*math.ulp(card['stop_s'])]
        generated = decks(physical,settings,card['binding'],card['times'],
                          {'records':[{'time_s':t} for t in points]})
        for backend in BACKENDS:
            label = card['id'].replace(':','-')
            work = output/'runs'/backend/label
            work.mkdir(parents=True)
            filename,text = generated[backend]
            if backend=='gnucap_modelgen':
                text=text.replace('.options numdgt=17 dtmin=1e-15',
                                  '.options numdgt=17 method=trap dtmin=1e-16 trtol=7 dtratio=1e9')
                # Keep the fixture instance distinct from the module name:
                # INSTANCE::build_proto searches the enclosing card list.
                text=text.replace(' dut(', ' bench_dut(')
            else:
                text=text.replace(' method=trap\n',' method=trap trtol=7 chgtol=1e-14 itl4=10\n')
            if card['family']=='nearby-timer':
                if backend=='gnucap_modelgen':
                    # Verilog connection grammar requires a node identifier;
                    # the existing ideal zero-voltage reference grounds r.
                    text=text.replace('dut(u,y,0);','dut(u,y,bench_ref);')
                prefix='bench_dut' if backend=='gnucap_modelgen' else 'dut'
                signals='v(u) v(y)' + (''.join(' v('+prefix+'.'+('_b_'+n+'_r' if backend=='gnucap_modelgen' else n)+')' for n in 'hefi')
                                      if card['case']['chain'] else '')
                if backend=='gnucap_modelgen':
                    text='\n'.join('.print tran '+signals+' v(bench_ref)'
                                   if line.startswith('.print tran ') else line
                                   for line in text.splitlines())+'\n'
                    if card['case']['chain']:
                        # Populate internal nodes before resolving print probes.
                        text=text.replace('.print tran ','.op\n.print tran ',1)
                else:
                    text='\n'.join('wrdata waveform.txt '+signals
                                   if line.startswith('wrdata waveform.txt ') else line
                                   for line in text.splitlines())+'\n'
            (work/'dut.va').write_text(card['source'])
            (work/filename).write_text(text)
            save(work/'condition.json',card)
            controls = (dict(method='trap',numdgt=17,trtol=7,chgtol=1e-14,itl4=10)
                        if backend=='openvaf_r_ngspice' else
                        dict(method='trap',numdgt=17,trtol=7,dtmin_s=1e-16,dtratio=1e9,short=1e-9))
            save(work/'requested_settings.json',dict(settings,backend_controls=controls,
                 observer=dict(node='paper_observer',coupling='ground only',
                               requested_times_s=points,original_observation_times_s=card['times'],
                               role='grid requests; accepted origin needs audit')))
            save(work/'requested_times.json',card['times'])
            plan.append(dict(backend=backend,label=label,condition=card['id'],
                             family=card['family'],deck=filename,work=str(work.relative_to(output))))
    save(output/'PLAN.json',plan)
    dependencies=[Path(__file__),ROOT/'evas/validation/strobe/timer_composition.py',
                  ROOT/'evas/validation/strobe/near_timer.py',
                  ROOT/'evas/validation/sample_edge_filter/contract.py',
                  ROOT/'evas/validation/paper/precision_checker.py',
                  ROOT/'evas/validation/paper/precision-v1.json',
                  ROOT/'evas/validation/paper/precision-v2.json',
                  ROOT/'experiments/backends/paper/inputs.py',
                  ROOT/'experiments/backends/paper/observations.py',
                  ROOT/'experiments/backends/paper/runner.py',
                  ROOT/'evas/validation/adapters/paper_evas_worker.py',
                  ROOT/'experiments/backends/paper/process.py',
                  ROOT/'experiments/backends/paper/settings_readback.py',
                  ROOT/'experiments/backends/support/precision_run.py',*execution.worker_source_files(),*READER_DEPENDENCIES]
    save(output/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in dependencies})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p)
                                for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps({'conditions':11,'positions':22,'manifest_sha256':sha(output/'MANIFEST.json')}))


def verify(inputs):
    manifest=load(inputs/'MANIFEST.json')
    actual={str(p.relative_to(inputs)) for p in inputs.rglob('*')
            if p.is_file() and p!=inputs/'MANIFEST.json'}
    if actual!=set(manifest):
        raise ValueError('frozen completion inventory changed')
    for relative,digest in manifest.items():
        p=inputs/relative
        if p.is_symlink() or not p.resolve().is_relative_to(inputs.resolve()) or sha(p)!=digest:
            raise ValueError('frozen completion file changed: '+relative)
    for relative,digest in load(inputs/'SOURCE_IDENTITY.json').items():
        if sha(ROOT/relative)!=digest:
            raise ValueError('bound completion source changed: '+relative)


def run(inputs,output,backend,profile_path,selection=None):
    verify(inputs)
    plan=[r for r in load(inputs/'PLAN.json') if r['backend']==backend
          and (not selection or r['condition'] in selection)]
    if not plan:
        raise ValueError('empty completion selection')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'STARTED.json',dict(selected=plan,limits=execution.LIMITS,
                                  input_manifest_sha256=sha(inputs/'MANIFEST.json')))
    results=[]
    try:
        profile=load(profile_path)
        tool,env=execution.preflight(backend,profile,output,execution.LIMITS)
        save(output/'TOOL_IDENTITY.json',tool)
        for row in plan:
            verify(inputs)
            execution.verify_tool(tool,profile,env)
            work=output/'runs'/row['label']
            shutil.copytree(inputs/row['work'],work)
            result={**row,**execution.execute_one(backend,tool,env,work)}
            result['directory_budget']=execution.directory_budget(work)
            save(work/'RESULT.json',result)
            results.append(result)
            checkpoint(output/'EXECUTION.json',results)
            print(json.dumps({'condition':row['condition'],'execution':result['status']}),flush=True)
            if result.get('abort_batch') or result['directory_budget']['status']!='within_limit':
                break
    finally:
        recorded={r['label'] for r in results}
        results.extend(dict(r,status='not_run',reason='lane did not reach this frozen slot')
                       for r in plan if r['label'] not in recorded)
        checkpoint(output/'EXECUTION.json',results)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                         for p in sorted(output.rglob('*')) if p.is_file()})


def assess(card,rows):
    if card['family']=='sef':
        return timer.sef.assess(card['case'],rows)
    if card['family']=='timer-composition':
        return timer.assess(card['case'],rows)
    # Preserve all internal consumers. Missing exports are evidence gaps,
    # never synthesized from y or the analytical reference.
    if card['case']['chain']:
        normalized=[]
        for row in rows:
            out=dict(row)
            for node in 'hefi':
                if node not in out:
                    out[node]=row.get('bench_dut._b_'+node+'_r',row.get('bench_dut.'+node,row.get('dut.'+node,row.get('dut:'+node))))
                if not isinstance(out[node],(int,float)):
                    return {'status':'evidence_insufficient','reason':'required internal output missing: '+node}
            normalized.append(out)
        rows=normalized
    return nearby.assess(card['case'],rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path)
    r=s.add_parser('run');r.add_argument('inputs',type=Path);r.add_argument('output',type=Path)
    r.add_argument('--backend',choices=BACKENDS,required=True);r.add_argument('--profile',type=Path,required=True)
    r.add_argument('--condition',action='append')
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    else:run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),a.condition)
