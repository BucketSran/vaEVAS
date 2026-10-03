"""Freeze missing backend runs from the already executed Spectre input identity."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
BACKENDS=('evas','openvaf_ngspice','gnucap')
ENV_SHA='3b85fddd09d943b331b0f6ca1b8d687c5932d6f2e2ec7683133f418e4901edba'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')


def selected(c,backend):return backend=='gnucap' or c['kind']!='v1' or c['id']=='v6-standard'


def netlists(c,p):
    sources=[]; ng=[]; gc=['load mgsim','load ./dut.so','verilog']
    signals=list(c['inputs'])+c['outputs']
    for name,points in c['inputs'].items():
        wave=' '.join(f'{x*1e-6:.17g} {y:.17g}' for x,y in points)
        sources.append(f'V{name} {name} 0 PWL({wave})')
    for i,inst in enumerate(c['instances']):
        module=inst.get('module',c.get('module'))
        params=' '.join(f'{k}={v:.17g}' for k,v in inst['params'].items())
        ng += [f"N{i} {' '.join(inst['ports'])} model{i}",f'.model model{i} {module} {params}']
        override=(' #('+', '.join(f'.{k}({v:.17g})' for k,v in inst['params'].items())+')') if inst['params'] else ''
        ports=['bench_ref' if n=='0' else n for n in inst['ports']]
        gc.append(f"\\{module}{override} {inst['name']}({','.join(ports)});")
    steps=f"{p['step']:.17g} {p['stop']:.17g} 0 {p['maxstep']:.17g}"
    options=f"reltol={p['reltol']:.17g} vntol={p['vabstol']:.17g} abstol={p['iabstol']:.17g}"
    cir=('DVS-2 '+c['id']+'\n'+'\n'.join(sources+ng)+f'\n.options {options} method=trap\n'+
         '.control\npre_osdi dut.osdi\nset filetype=ascii\nset wr_singlescale\nset wr_vecnames\nset numdgt=16\noption\n'+
         f'tran {steps}\nwrdata waveform.txt '+' '.join('v('+s+')' for s in signals)+'\noption\nquit\n.endc\n.end\n')
    gc_text=('\n'.join(gc+['spice','Vbench_ref bench_ref 0 0']+sources)+
             f'\n.options numdgt=16 short=1e-9 {options}\n.options\n'+
             '.print tran '+' '.join('v('+s+')' for s in signals+['bench_ref'])+f'\n.tran {steps} > waveform.txt\n.end\n')
    return {'tb.cir':cir,'tb.gc':gc_text}


def verify(root,manifest_sha):
    p=root/'FILE_MANIFEST.json'
    if sha(p)!=manifest_sha:raise ValueError('wrong source archive manifest')
    manifest=json.loads(p.read_text())
    for rel,entry in manifest.items():
        f=root/rel
        if not f.resolve().is_relative_to(root.resolve()) or sha(f)!=entry['sha256'] or f.stat().st_size!=entry['bytes']:
            raise ValueError('source evidence drift: '+rel)
    return manifest


def build(source,destination):
    receipt=json.loads((ROOT/'experiments/backends/dvs2-spectre-validation/results/RECEIPT.json').read_text())
    verify(source,receipt['file_manifest_sha256'])
    destination.mkdir(parents=True,exist_ok=False)
    cases=json.loads((source/'conditions.json').read_text())
    save(destination/'conditions.json',cases)
    save(destination/'expected_images.json',json.loads((ROOT/'experiments/archive/dvs2-starter-pilot/results/TOOL_IDENTITIES.json').read_text())['images'])
    save(destination/'provenance.json',dict(spectre_run_id=source.name,spectre_input_manifest_sha256=sha(source/'INPUT_MANIFEST.json'),
        spectre_file_manifest_sha256=sha(source/'FILE_MANIFEST.json'),environment_sha256=ENV_SHA,max_configurations=130,
        max_simulation_launches=130,max_compiler_launches=35,stage_timeout_s=90))
    plan=[]
    for backend in BACKENDS:
        for c in cases:
            if not selected(c,backend):continue
            for setting in ['base','fine']:
                old=source/'runs'/c['id']/setting
                work=destination/'runs'/backend/c['id']/setting
                work.mkdir(parents=True)
                for name in ['dut.va','condition.json','requested_settings.json','tb.scs']:
                    shutil.copyfile(old/name,work/name)
                p=json.loads((work/'requested_settings.json').read_text())
                for name,body in netlists(c,p).items():(work/name).write_text(body)
                save(work/'adapter.json',dict(backend=backend,revision='supplement-20260928',
                    source_unchanged=True,gnucap_short=1e-9 if backend=='gnucap' else None,
                    gnucap_ground_alias='bench_ref' if backend=='gnucap' else None,
                    physical_input_identity='unchanged from Spectre batch'))
                plan.append(dict(backend=backend,condition=c['id'],profile=setting,source_sha256=sha(work/'dut.va')))
    assert len(plan)==130
    save(destination/'RUN_PLAN.json',plan)
    shutil.copyfile(Path(__file__).with_name('remote.py'),destination/'remote.py')
    paths=set(Path(__file__).parent.glob('*.py'))|{Path(__file__).with_name('PROTOCOL.md')}
    for rel in receipt_source_files(source):paths.add(ROOT/rel)
    for rel in ['experiments/archive/dvs2-starter-pilot/results/results.json','experiments/archive/dvs2-starter-pilot/results/ARCHIVE_RECEIPT.json',
                'experiments/backends/dvs2-spectre-validation/results/RECEIPT.json','experiments/backends/dvs2-spectre-validation/results/analysis.json']:
        paths.add(ROOT/rel)
    identities={}
    for p in sorted(paths):
        rel=p.relative_to(ROOT); out=destination/'source'/rel
        out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out);identities[str(rel)]=sha(p)
    save(destination/'SOURCE_IDENTITY.json',identities)
    save(destination/'INPUT_MANIFEST.json',{str(p.relative_to(destination)):dict(sha256=sha(p),bytes=p.stat().st_size)
        for p in sorted(destination.rglob('*')) if p.is_file()})
    print('Frozen',len(plan),'configurations; unchanged common DUT and Spectre checker')


def receipt_source_files(source):
    identities=json.loads((source/'source_identity.json').read_text())
    for rel,digest in identities.items():
        if rel.endswith('.py'):
            if sha(ROOT/rel)!=digest:raise ValueError('Spectre analysis code changed: '+rel)
            yield rel


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spectre_evidence',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();build(args.spectre_evidence,args.output)
