"""Version a static reaggregation; never rerun a backend or overwrite snapshots."""
from __future__ import annotations
import argparse
import copy
import hashlib
import subprocess
from pathlib import Path

from records import ROOT, load, sha, source_bytes, validate, voltage_metrics
from freeze import save


def freeze_candidates(data, root):
    directory = root/'experiments/backends/comparison/evidence/application-sources'
    for dataset in data['datasets']:
        for candidate in dataset.get('candidates', []):
            refs=[]
            for original in candidate['sources']:
                if 'original_path' in original:
                    source_bytes(original,root,candidate['revision'])
                    refs.append(original)
                    continue
                original=dict(original,original_path=original['path'])
                content=source_bytes(original,root,candidate['revision'])
                digest=hashlib.sha256(content).hexdigest()
                directory.mkdir(parents=True,exist_ok=True)
                path=directory/(digest+'-'+Path(original['original_path']).name)
                if path.exists():
                    if path.read_bytes()!=content:
                        raise ValueError('immutable source archive changed')
                else:
                    with path.open('xb') as stream:
                        stream.write(content)
                refs.append(dict(original,path=str(path.relative_to(root)),sha256=digest))
            candidate['sources']=refs
            candidate['identity_scope']='historical frozen revision; current checker changes require a new candidate and revalidation'


def freeze_metric_contract(data, root, revision):
    original = 'evas/validation/PROTOCOL.md'
    path = root/original
    ref = {'path': original, 'original_path': original, 'sha256': sha(path)}
    content = source_bytes(ref, root, revision)
    archive = root/'experiments/backends/comparison/evidence/application-sources'/(
        ref['sha256'] + '-PROTOCOL.md')
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        if archive.read_bytes() != content:
            raise ValueError('immutable metric contract archive changed')
    else:
        with archive.open('xb') as stream:
            stream.write(content)
    data['metric_contract'] = dict(ref, path=str(archive.relative_to(root)), revision=revision,
        interpretation='V1 main 1mV absolute output; V2 main differential 2mV and common-mode 1mV')


def derive(snapshot, root=ROOT):
    original=load(snapshot)
    validate(original,root)
    data=copy.deepcopy(original)
    data['schema_version']=2
    data['limits'] = [line.replace('v1-main/v2-main with the published 1mV static contract',
        'V1 absolute-output 1mV and V2 differential 2mV/common-mode 1mV contracts') for line in data.get('limits', [])]
    data['derivation']={'parent':{'path':str(snapshot.relative_to(root)),'sha256':sha(snapshot)},
        'operation':'static reaggregation of saved named observations; no new simulator launches',
        'legacy_limit':'schema1 V2 single-ended 1mV metric is invalid; schema2 derives differential 2mV and common-mode 1mV properties',
        'changed_execution_count':False}
    for row in data['records']:
        if row['accounting']=='unrun':
            continue
        if row['accounting']=='reused':
            refs=[r for r in row['evidence'] if r['kind']=='analysis']
            if len(refs)!=1:
                raise ValueError('one historical named matrix required')
            ref=refs[0]
            selector={'backend':row['backend'],'condition':row['case'],'profile':row['profile'],
                      'source_run_id':row['measurement']['run_id']}
            row['observation_binding']=dict(ref,format='matrix',selector=selector)
            matched=[r for r in load(root/ref['path'])['records'] if all(r.get(k)==v for k,v in selector.items())]
            if len(matched)!=1:
                raise ValueError('named historical observation missing')
            observation=matched[0]['analysis']
        else:
            receipt=load(root/row['execution_receipt']['path'])
            observation=load(root/receipt['observation']['path'])
        row['metrics']=voltage_metrics(row['case'],observation,2)
    freeze_candidates(data,root)
    freeze_metric_contract(data, root, subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip())
    validate(data,root)
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    save(args.output,derive(args.snapshot.resolve()))
