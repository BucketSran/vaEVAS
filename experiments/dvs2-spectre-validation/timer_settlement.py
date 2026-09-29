"""Bounded same-time diagnostics; affine closure is a candidate, not an LRM verdict.

Default: six chain/feedback circuits. Optional disjoint batches diagnose
noncontractive closure and repeated assignments; freeze before either backend.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

import timer_reference as base
from cross_touch import (ROOT, Instance, audit_settings, compile_sources, digest,
                         dump, read_waveform, transient, verify)

U = base.UNIT
ALLOWANCE = base.ALLOWANCE
PORTS = ['clock', 'u', 'out', 'count', 'stamp', 'r']


def module(name, blocks, declarations, contributions):
    return ('`include "disciplines.vams"\nmodule '+name+'('+','.join(PORTS)+');\n'
            'input clock,u; output out,count,stamp; inout r;\n'
            'electrical '+','.join(PORTS)+';\n'+declarations+'\nanalog begin\n'+
            '\n'.join(blocks)+'\n'+contributions+'\nend\nendmodule\n')


def specifications(extended=False, sequence_controls=False, counter_rewrite=False):
    result = []
    for profile, step in base.STEPS.items():
        for reverse in [False, True]:
            result.append(dict(id='chains-'+profile+('-reversed' if reverse else '-forward'),
                               family='chains', reverse=reverse, maxstep=step))
        result.append(dict(id='feedback-'+profile, family='feedback', reverse=False, maxstep=step))
    if extended:
        result = [dict(id=family+'-'+profile, family=family, reverse=False, maxstep=step)
                  for profile,step in base.STEPS.items()
                  for family in ['feedback_noncontractive','local_sequence']]
    if sequence_controls:
        result = [dict(id=family+"-"+profile, family=family, reverse=False, maxstep=step)
                  for profile,step in base.STEPS.items()
                  for family in ["counter_repeated", "real_sequence", "feedback_sequence"]]
    if counter_rewrite:
        result = [dict(id="counter_rewrite-"+profile, family="counter_rewrite", reverse=False, maxstep=step)
                  for profile,step in base.STEPS.items()]
    for c in result:
        c.update(stop=19*U, ttol=U/1024, rate=1/U, inputs={'clock':[[0, 0], [19*U, 19]]},
                 output_times=sorted({0., 19*U, 8*U-U/8, 8*U+U/8,
                                      *[i*U/4 for i in range(77)]}))
    return result


def design(c):
    start = 8*U
    event = f'@(timer({start!r},0,{c["ttol"]!r}))'
    read = module('reader', ['@(initial_step) begin n=0; s=0; h=-1; end',
                  event+' begin n=n+1; s=gain*V(u,r)+bias; h=V(clock,r); end'],
                  'parameter real gain=1; parameter real bias=0; integer n; real s,h;',
                  'V(out,r)<+s; V(count,r)<+n; V(stamp,r)<+h;')
    source = module('producer', ['@(initial_step) begin n=0; h=-1; end',
                    event+' begin n=n+1; h=V(clock,r); end'], 'integer n; real h;',
                    'V(out,r)<+n; V(count,r)<+n; V(stamp,r)<+h;')
    inst, targets = [], []
    def add(name, mod, u, expected, parameters=None):
        inst.append(Instance(name, mod, dict(clock='clock', u=u, out='o_'+name,
                     count='n_'+name, stamp='h_'+name, r='0'), parameters or {}))
        targets.append(dict(id=name, expected=expected))
    if c['family'] in ['feedback','feedback_noncontractive']:
        # s = gain*s+1: unique candidates 2 and 2/3, derived without a simulator.
        gain = 2. if c['family']=='feedback_noncontractive' else .5
        add('positive', 'reader', 'o_positive', 1/(1-gain), dict(gain=gain,bias=1))
        add('negative', 'reader', 'o_negative', 2/3, dict(gain=-.5,bias=1))
        sources = {'reader.va':read}
    elif c['family'] in ['counter_repeated','real_sequence','feedback_sequence','counter_rewrite']:
        actions, expected = {
            'counter_rewrite': ('n=n+2; s=V(out,r); s=0.5*s+n;', 4.),
            'counter_repeated': ('n=n+1; n=n+1; s=n;', 2.),
            'real_sequence': ('s=1; s=s+2;', 3.),
            'feedback_sequence': ('n=n+1; s=V(out,r); s=0.5*s+n;', 2.),
        }[c['family']]
        sequence = module('sequence', ['@(initial_step) begin n=0; k=0; s=0; h=-1; end',
            event+' begin k=k+1; '+actions+' h=V(clock,r); end'],
            'integer n,k; real s,h;', 'V(out,r)<+s; V(count,r)<+k; V(stamp,r)<+h;')
        add('sequence','sequence','0',expected)
        sources = {'sequence.va':sequence}
    elif c['family']=='local_sequence':
        sequence = module('sequence', ['@(initial_step) begin n=0; s=0; h=-1; end',
            event+' begin n=n+1; n=n+1; s=V(out,r); s=0.5*s+n; h=V(clock,r); end'],
            'integer n; real s,h;', 'V(out,r)<+s; V(count,r)<+0.5*n; V(stamp,r)<+h;')
        add('sequence','sequence','0',4.)
        sources = {'sequence.va':sequence}
    else:
        add('a', 'producer', '0', 1.)
        add('b', 'reader', 'o_a', 1.)
        add('c', 'reader', 'o_b', 1.)
        blocks = [event+' begin n=n+1; h=V(clock,r); end',
                  event+' x=V(count,r);', event+' y=V(mid,r);']
        if c['reverse']: blocks.reverse()
        chain = module('chain', ['@(initial_step) begin n=0; x=0; y=0; h=-1; end',*blocks],
                       'electrical mid; integer n; real x,y,h;',
                       'V(count,r)<+n; V(mid,r)<+x; V(out,r)<+y; V(stamp,r)<+h;')
        add('single', 'chain', '0', 1.)
        sources = {'producer.va':source, 'reader.va':read, 'chain.va':chain}
    return sources, inst[::-1] if c['reverse'] else inst, targets


def build(root,extended=False,sequence_controls=False, counter_rewrite=False):
    root.mkdir(parents=True,exist_ok=False)
    cases=specifications(extended,sequence_controls,counter_rewrite)
    dump(root/'conditions.json',cases)
    dump(root/'contract.json',dict(max_spectre_attempts=len(cases),timeout_s=90,
         license_timeout_s=30,observation_allowance_v=ALLOWANCE,
         candidate='Joint same-time equations with each event applied once from the accepted old state.',
         purpose='Distinguish one pre-voltage snapshot from chain propagation and unique affine closure; compare held clock stamps.',
         limits='Candidate classification, finite observations only; no proof of hidden Spectre algorithm or universal race semantics.'))
    for c in cases:
        work=root/c['id']; work.mkdir()
        sources, inst, _=design(c)
        for name, text in sources.items(): (work/name).write_text(text)
        lines=['simulator lang=spectre',*[f'ahdl_include "{name}"' for name in sources],
               f'Vclock (clock 0) vsource type=pwl wave=[0 0 {c["stop"]:.17g} 19]']
        for i in inst:
            lines.append('X'+i.name+' ('+' '.join(i.connections[p] for p in PORTS)+') '+i.module+' '+
                         ' '.join(f'{k}={v!r}' for k,v in i.parameters.items()))
        saved=sorted({n for i in inst for n in i.connections.values() if n!='0'})
        lines+=['simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                f'tran tran stop={c["stop"]:.17g} step={c["maxstep"]:.17g} maxstep={c["maxstep"]:.17g} method=traponly',
                'save '+' '.join(saved)]
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    deps=[Path(__file__),Path(__file__).with_name('test_timer_settlement.py'),
          *[Path(__file__).with_name(n+'.py') for n in ['timer_reference','cross_touch','remote','report']],
          *[ROOT/'experiments/dvs2-starter-pilot'/n for n in ['analyze.py','suite.py']]]
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in deps})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root,kernel):
    verify(root)
    if (root/'EVAS_STARTED.json').exists(): raise ValueError('use a new run identity')
    dump(root/'EVAS_STARTED.json',dict(kernel_sha256=digest(kernel),
         source_sha256={str(p.relative_to(ROOT)):digest(p) for folder,pattern in
             [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')] for p in folder.rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        try:
            sources,inst,_=design(c)
            # Compile only frozen design inputs, never generated files/OS sidecars.
            program=compile_sources({name:(work/name).read_text() for name in sources},inst)
            result=transient(program,c['inputs'],c['output_times'],stop=c['stop'],max_step=c['maxstep'],
                             kernel=kernel,vabstol=1e-10,reltol=1e-8)
            dump(work/'evas.json',result); print(c['id'],'ok',flush=True)
        except Exception as e:
            dump(work/'evas-failure.json',dict(type=type(e).__name__,message=str(e)))
            print(c['id'],type(e).__name__,str(e),flush=True)


def inspect(rows,c):
    _,_,targets=design(c)
    required={'time','clock',*[prefix+t['id'] for t in targets for prefix in ['o_','n_','h_']]}
    if not rows or any(not required<=r.keys() for r in rows): raise ValueError('missing observations')
    if any(not math.isfinite(r[k]) for r in rows for k in required): raise ValueError('nonfinite observations')
    if rows[0]['time']!=0 or abs(rows[-1]['time']-c['stop'])>1e-18: raise ValueError('incomplete time coverage')
    if any(not 0<=b['time']-a['time']<=c['maxstep']*1.001 for a,b in zip(rows,rows[1:])):
        raise ValueError('invalid time order or output gap')
    if any(abs(r['clock']-min(c['stop'],max(0,r['time']))/U)>ALLOWANCE for r in rows):
        raise ValueError('input mismatch')
    records=[]
    for p in targets:
        key=p['id']
        try:
            h=base.history(rows,c,base.probe(key,8*U),'n_'+key,'h_'+key)
            values=[r['o_'+key] for r in rows if r['n_'+key]>.5]
            if not values or any(abs(v-values[0])>ALLOWANCE for v in values):
                raise ValueError('sample missing or not held')
            if any(abs(r['o_'+key])>ALLOWANCE for r in rows if r['n_'+key]<.5):
                raise ValueError('sample changed before event')
            records.append(dict(id=key,expected=p['expected'],observed=values[0],history=h,
                accepted_clock_v=rows[-1]['h_'+key],
                status='candidate_consistent' if abs(values[0]-p['expected'])<=ALLOWANCE else 'candidate_differs'))
        except ValueError as e:
            records.append(dict(id=key,status='finite_inconsistent',reason=str(e)))
    return dict(records=records,points=len(rows),summary=dict(Counter(p['status'] for p in records)))


def analyze(root,output,backends):
    verify(root); records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        for backend in backends:
            work=root/c['id']; r=dict(configuration=c['id'],backend=backend)
            try:
                if backend=='evas':
                    if (work/'evas-failure.json').exists(): raise ValueError((work/'evas-failure.json').read_text())
                    path=work/'evas.json'; j=json.loads(path.read_text())
                    rows=[dict(zip(j['nodes'],s['voltages']),time=t) for t,s in zip(j['transient']['times'],j['solutions'])]
                else:
                    e=json.loads((work/'spectre-execution.json').read_text())
                    if e['returncode'] or e['timeout']: raise ValueError('execution failed or timed out')
                    path=work/'psf/tran.tran.tran'; rows=read_waveform(path,'spectre')
                    actual,stop_audit=audit_settings((work/'spectre.log').read_text(),c,rows)
                    r.update(effective_settings=actual,stop_audit=stop_audit)
                r.update(inspect(rows,c),status='analyzed',waveform_sha256=digest(path))
            except (ValueError,KeyError,FileNotFoundError) as e: r.update(status='failed_or_missing',reason=str(e))
            records.append(r)
    dump(output,dict(records=records,formal_qualification=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','evas','spectre','check']); p.add_argument('root',type=Path)
    p.add_argument('--kernel',type=Path); p.add_argument('--spectre-profile',type=Path); p.add_argument('--output',type=Path)
    p.add_argument('--counter-rewrite',action='store_true')
    p.add_argument('--sequence-controls',action='store_true')
    p.add_argument('--extended',action='store_true',help='Freeze four noncontractive/local-sequence diagnostics')
    p.add_argument('--backends',nargs='+',choices=['evas','spectre'],default=['evas','spectre'])
    a=p.parse_args()
    if a.action=='build': build(a.root,a.extended,a.sequence_controls,a.counter_rewrite)
    elif a.action=='evas': run_evas(a.root,a.kernel)
    elif a.action=='spectre': base.run_spectre(a.root,a.spectre_profile)
    else: analyze(a.root,a.output,a.backends)
