"""Resolve only the public healthy self-test's immutable source references.

Run: python materialize_case.py --output visible-cases.json
The output can be passed to a compatible local source harness. This helper does
not contain a final checker, final instance, or a reference candidate.
"""
from pathlib import Path
import argparse,hashlib,json

def load_cases(root):
    root=Path(root).resolve();cases=json.loads((root/'cases.json').read_text())
    for case in cases:
        support={}
        for name,item in case.pop('support_files').items():
            path=(root/item['path']).resolve()
            if not path.is_relative_to(root):raise ValueError('public source path escaped materials')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('public source identity mismatch')
            support[name]=data.decode('utf-8')
        case['support']=support
    return cases

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--materials',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args();a.output.write_text(json.dumps(load_cases(a.materials),indent=2)+'\n')
