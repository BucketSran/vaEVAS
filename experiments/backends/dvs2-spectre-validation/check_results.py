"""Independent finite-observation checks for the fixed Spectre batch.

Raw accepted points are never interpolated or removed. P/F/I refer to the
stated finite numeric assumptions; formal observation qualification remains I.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import sys

from run_suite import ROOT, T, v1
from dvs2.checker import (lowpass, lowpass_slope, histories, nominal_history,
                          reference, quality, integrator_check, check,
                          Event, check_history, event_contract, analyze_v1)
# Legacy waveform projection remains an adapter dependency until reader migration.
sys.path.insert(0, str(ROOT/'experiments/archive/dvs2-starter-pilot'))
from analyze import read_waveform


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args(); root=args.root.resolve()
    if args.output.resolve().is_relative_to(root) or args.output.exists(): raise ValueError('output must be new and outside raw evidence')
    manifest=json.loads((root/'FILE_MANIFEST.json').read_text())
    # Verify all archived files, not just successful waveforms.
    for rel,d in manifest.items():
        p=root/rel
        if not p.resolve().is_relative_to(root) or sha(p)!=d['sha256'] or p.stat().st_size!=d['bytes']:
            raise ValueError('evidence drift: '+rel)
    source=json.loads((root/'source_identity.json').read_text())
    for rel,digest in source.items():
        if rel.endswith('.py') and sha(ROOT/rel)!=digest: raise ValueError('analysis source differs from pre-run freeze: '+rel)
    records=[]
    for case in json.loads((root/'conditions.json').read_text()):
        for profile in ['base','fine']:
            work=root/'runs'/case['id']/profile
            result=json.loads((work/'result.json').read_text())
            if (result['condition'],result['profile'])!=(case['id'],profile): raise ValueError('result identity mismatch')
            if result['status']=='waveform_available':
                try: analysis=check(read_waveform(work/result['waveform'],'spectre'),case)
                except (ValueError,KeyError,TypeError,IndexError) as exc: analysis=dict(status='observation_invalid',reason=str(exc),formal_dvs_qualification='I')
            else: analysis=dict(status=result['status'],formal_dvs_qualification='I')
            records.append(dict(condition=case['id'],card=case['card'],kind=case['kind'],profile=profile,
                                execution_status=result['status'],elapsed_s=result['elapsed_s'],analysis=analysis))
            print(case['id'],profile,analysis['status'],flush=True)
    summary=dict(configurations=len(records),conditions=len({r['condition'] for r in records}),
                 execution=dict(Counter(r['execution_status'] for r in records)),
                 observation=dict(Counter(r['analysis']['status'] for r in records)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(run_id=root.name,file_manifest_sha256=sha(root/'FILE_MANIFEST.json'),
        input_manifest_sha256=sha(root/'INPUT_MANIFEST.json'),source_identity=source,summary=summary,records=records),indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__': main()
