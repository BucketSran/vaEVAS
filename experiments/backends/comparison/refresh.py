"""Refresh only CMP8 EVAS observations; reuse fixed external evidence, never launch."""
from __future__ import annotations
import argparse
import copy
from pathlib import Path
import shutil

from records import ROOT, BACKENDS, evidence_ok, load, sha, validate
from freeze import SELECTED, save

REUSE = 'Original Spectre receipt retained; physical inputs, checker and runtime match the refreshed target.'
KEYS = ('dataset', 'case', 'backend', 'profile')


def reference(path, root):
    path=path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('refresh evidence belongs inside the owning repository')
    return {'path':str(path.relative_to(root)), 'sha256':sha(path)}


def read(ref, root):
    evidence_ok(ref, root)
    return load(root/ref['path'])


def check_refresh(data, root=ROOT):
    """Bind this finite merge to original snapshots and frozen input bytes."""
    if data['schema_version']!=2:
        raise ValueError('receipt refresh requires schema2')
    proof=data['refresh']
    parent=read(proof['parent'],root); fresh=read(proof['fresh'],root)
    if parent['schema_version']!=2 or fresh['schema_version']!=2 or 'refresh' in fresh:
        raise ValueError('refresh requires schema2 parent and a separate fresh execution snapshot')
    validate(parent,root); validate(fresh,root)
    for name in ('datasets','coverage','tools','components','candidate_links'):
        if data.get(name)!=parent.get(name):
            raise ValueError('refresh changed unrelated historical dataset or candidate')
    for snapshot in (parent,fresh):
        batch=next(d for d in snapshot['datasets'] if d['id']=='cmp8-base')
        if {c['id'] for c in batch['cases']}!=set(SELECTED) or batch['profiles']!=['base'] or batch['denominator']!=8:
            raise ValueError('refresh only accepts the fixed eight base cases')
    if next(d for d in parent['datasets'] if d['id']=='cmp8-base')['cases']!=next(d for d in fresh['datasets'] if d['id']=='cmp8-base')['cases']:
        raise ValueError('refresh changed frozen physical case identities')
    expected_targets=copy.deepcopy(parent['targets']);expected_targets['evas']=fresh['targets']['evas']
    if data['targets']!=expected_targets or any(fresh['targets'][b]!=parent['targets'][b] for b in BACKENDS if b!='evas'):
        raise ValueError('refresh changed an external target or lost the fresh EVAS target')
    old_manifest=read(proof['old_manifest'],root);new_manifest=read(proof['new_manifest'],root)
    old_provenance=read(proof['old_provenance'],root);new_provenance=read(proof['new_provenance'],root)
    for prefix,manifest in [('old',old_manifest),('new',new_manifest)]:
        ref=proof[prefix+'_provenance'];path=root/ref['path']
        if manifest.get('provenance.json')!={'sha256':ref['sha256'],'bytes':path.stat().st_size}:
            raise ValueError('refresh provenance is not bound to its input manifest')
    checker=new_provenance['checker_identity']
    if checker!=old_provenance['checker_identity'] or new_provenance['evas_runtime_identity']!=fresh['targets']['evas']['runtime_identity']:
        raise ValueError('refresh checker or new runtime provenance mismatch')
    old_rows={tuple(r[k] for k in KEYS):r for r in parent['records']}
    fresh_rows={tuple(r[k] for k in KEYS):r for r in fresh['records']}
    actual={tuple(r[k] for k in KEYS):r for r in data['records']}
    if len(actual)!=len(data['records']) or actual.keys()!=old_rows.keys():
        raise ValueError('refresh changed the configuration denominator')
    measured=[r['measurement'] for r in fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas']
    if len(measured)!=8 or any(not m for m in measured) or len({(m['run_id'],m.get('kernel_sha256'),m['revision'],m['runtime_identity']) for m in measured})!=1:
        raise ValueError('refresh requires one complete eight-case EVAS execution identity')
    for key,old in old_rows.items():
        row=actual[key]
        if old['dataset']!='cmp8-base':
            if row!=old:raise ValueError('refresh changed an unrelated historical record')
            continue
        new=fresh_rows[key]
        if old['backend']=='evas':
            if new['accounting']!='executed' or row!=new:
                raise ValueError('refresh requires exactly eight fresh EVAS observations')
            receipt=read(new['execution_receipt'],root)
            if (receipt['run_id']==old['measurement']['run_id'] or
                new['execution_receipt']==old['execution_receipt'] or
                receipt['input_manifest_sha256']!=proof['new_manifest']['sha256'] or
                receipt['checker_identity']!=checker or
                new['measurement']['revision']!=fresh['targets']['evas']['revision'] or
                new['measurement']['runtime_identity']!=fresh['targets']['evas']['runtime_identity']):
                raise ValueError('old EVAS execution cannot impersonate the fresh integration batch')
            for filename in ('condition.json','dut.va','requested_settings.json'):
                path='runs/evas/'+old['case']+'/base/'+filename
                if path not in old_manifest or old_manifest[path]!=new_manifest.get(path):
                    raise ValueError('new EVAS changed the physical comparison input: '+path)
            entry=new_manifest.get('runs/evas/'+old['case']+'/base/dut.va',{})
            if receipt['source_sha256']!=entry.get('sha256'):
                raise ValueError('new EVAS source differs from frozen physical input')
        elif old['backend']=='spectre':
            if new['accounting']!='unrun' or old['accounting'] not in ('executed','reused'):
                raise ValueError('refresh cannot launch or replace external observations')
            expected=dict(old,accounting='reused',reuse_justification=REUSE)
            if row!=expected:
                raise ValueError('refresh changed the original Spectre receipt, identity or observation')
            receipt=read(old['execution_receipt'],root)
            if (receipt['input_manifest_sha256']!=proof['old_manifest']['sha256'] or
                receipt['checker_identity']!=checker or
                receipt['runtime_identity']!=data['targets']['spectre']['runtime_identity']):
                raise ValueError('Spectre reuse input, checker or runtime identity mismatch')
            for filename in ('condition.json','dut.va','requested_settings.json','tb.scs'):
                path='runs/spectre/'+old['case']+'/base/'+filename
                if path not in old_manifest or old_manifest[path]!=new_manifest.get(path):
                    raise ValueError('Spectre reuse changed physical input bytes: '+path)
            if receipt['source_sha256']!=old_manifest['runs/spectre/'+old['case']+'/base/dut.va']['sha256']:
                raise ValueError('Spectre receipt source differs from frozen physical input')
        else:
            if old['accounting']!='unrun' or new['accounting']!='unrun' or row!=old:
                raise ValueError('refresh must preserve all sixteen historical unrun configurations')


def refresh(parent_snapshot, fresh_snapshot, old_inputs, new_inputs, evidence, root=ROOT):
    """Return a new snapshot. Both execution snapshots and receipts stay immutable."""
    parent=load(parent_snapshot);fresh=load(fresh_snapshot)
    validate(parent,root);validate(fresh,root)
    data=copy.deepcopy(parent)
    if 'derivation' in data:data['prior_static_derivation']=data.pop('derivation')
    data['targets']['evas']=copy.deepcopy(fresh['targets']['evas'])
    new_rows={tuple(r[k] for k in KEYS):r for r in fresh['records']}
    for i,row in enumerate(data['records']):
        if row['dataset']!='cmp8-base':continue
        if row['backend']=='evas':data['records'][i]=copy.deepcopy(new_rows[tuple(row[k] for k in KEYS)])
        elif row['backend']=='spectre':row.update(accounting='reused',reuse_justification=REUSE)
    sources={'parent':parent_snapshot,'fresh':fresh_snapshot,
        'old_manifest':old_inputs/'INPUT_MANIFEST.json','new_manifest':new_inputs/'INPUT_MANIFEST.json',
        'old_provenance':old_inputs/'provenance.json','new_provenance':new_inputs/'provenance.json'}
    data['refresh']={name:reference(path,root) for name,path in sources.items()}
    check_refresh(data,root)
    evidence=evidence.resolve()
    if not evidence.is_relative_to(root.resolve()):raise ValueError('refresh archive escapes repository')
    if any(evidence.is_relative_to(inputs.resolve()) for inputs in (old_inputs,new_inputs)):
        raise ValueError('refresh archive must not modify frozen input directories')
    evidence.mkdir(parents=True,exist_ok=False)
    for name in ('old_manifest','new_manifest','old_provenance','new_provenance'):
        path=evidence/(name+'.json');shutil.copyfile(sources[name],path)
        data['refresh'][name]=reference(path,root)
    validate(data,root)
    return data


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','fresh','old_inputs','new_inputs','output'):p.add_argument(name,type=Path)
    p.add_argument('--evidence',required=True,type=Path)
    args=p.parse_args()
    save(args.output,refresh(args.parent,args.fresh,args.old_inputs,args.new_inputs,args.evidence))

if __name__=='__main__':main()
