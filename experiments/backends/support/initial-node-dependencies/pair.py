"""Recheck the three fixed probes against local native PSF, without resampling."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import warnings


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_psf(path):
    text=path.read_text()
    version=re.search(r'^"version" "([^"]+)"',text,re.M).group(1)
    rows=[]
    for line in text.split('VALUE\n',1)[1].splitlines():
        match=re.fullmatch(r'"([^"]+)"\s+([-+\d.eE]+)',line)
        if match:
            name,value=match[1],float(match[2])
            if name=='time': rows.append(dict(time=value))
            else: rows[-1][name]=value
    return version,rows


def check(rows, expected, forced, budget):
    times=[r['time'] for r in rows]
    if not times or any(not math.isfinite(t) or t<0 or t>1 for t in times):
        raise ValueError('invalid native times')
    if any(a>=b for a,b in zip(times,times[1:])):
        raise ValueError('native times must strictly increase')
    if not set(forced)<=set(times):
        raise ValueError('missing exact quarter-time observation')
    errors={n:0. for n in expected}
    for row in rows:
        for name,answer in expected.items():
            value=row.get(name)
            if not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError('missing/nonfinite voltage '+name)
            errors[name]=max(errors[name],abs(value-answer))
            if errors[name]>budget: raise ValueError('constant-answer mismatch '+name)
    return dict(native_rows=len(rows),maximum_error_V=errors,forced_times_s=forced)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-root',type=Path,required=True)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True,help='local joint-raw directory')
    parser.add_argument('--kernel-receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    card=json.loads((root/'case.json').read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    receipt=json.loads(args.kernel_receipt.read_text())
    if sha(args.kernel)!=receipt['debug']['sha256']: raise ValueError('kernel identity differs from supplied receipt')
    sys.path.insert(0,str(args.python_root/'evas/src'))
    from evas.scs import simulate_scs
    python_files=sorted((args.python_root/'evas/src/evas').rglob('*.py'))
    python_hashes={str(p.relative_to(args.python_root)):sha(p) for p in python_files}
    results=[]
    for name,expected in card['cases'].items():
        local=root/name; reference=args.reference/name
        for f in ['dut.va','tb.scs']:
            if (local/f).read_bytes()!=(reference/f).read_bytes():raise ValueError('physical input differs '+name+'/'+f)
        execution=json.loads((reference/'RESULT.json').read_text())
        if execution['returncode']!=0 or execution['timeout']:raise ValueError('reference execution incomplete')
        for f in ['dut.va','tb.scs']:
            if sha(local/f)!=execution['source_files_sha256'][f]:raise ValueError('execution input hash differs')
        version,native=read_psf(reference/'psf/tran.tran.tran')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            response=simulate_scs(local/'tb.scs',kernel=args.kernel)
        response_path=args.output/(name+'-evas.json')
        response_path.write_text(json.dumps(response,indent=2)+'\n')
        saved=response['saved']
        rows=[dict(time=t,**dict(zip(saved['nodes'],v))) for t,v in zip(saved['times'],saved['values'])]
        forced=card['forced_times_s'];budget=card['voltage_absolute_V']
        if response['strobe_evidence']['times']!=forced:raise ValueError('EVAS forced receipt differs')
        if set(saved['times'])!=set(response['transient']['times']).union(forced):raise ValueError('EVAS all policy lost native rows')
        checks=dict(EVAS=check(rows,expected,forced,budget),Spectre=check(native,expected,forced,budget))
        pairs=[]
        rmap={r['time']:r for r in rows};smap={r['time']:r for r in native}
        for t in sorted(rmap.keys()&smap.keys()):
            errors={n:abs(rmap[t][n]-smap[t][n]) for n in expected}
            if max(errors.values())>budget:raise ValueError('paired voltage mismatch')
            pairs.append(dict(time_s=t,absolute_difference_V=errors))
        results.append(dict(case=name,status='PASS',expected_V=expected,checks=checks,exact_native_pairs=pairs,
                            Spectre_version=version,EVAS_effective_tolerances=response['testbench']['effective_tolerances'],
                            input_sha256={f:sha(local/f) for f in ['dut.va','tb.scs']},
                            reference_sha256={f:sha(reference/f) for f in ['psf/tran.tran.tran','RESULT.json','spectre.log']},
                            EVAS_response_sha256=sha(response_path),warnings=[str(w.message) for w in caught]))
    source=receipt['source']
    if sha(args.kernel_receipt.parent/source)!=receipt['source_sha256']:raise ValueError('owned-source receipt hash differs')
    for f,h in receipt['snapshot_sha256'].items():
        if sha(args.kernel_receipt.parent/f)!=h:raise ValueError('compiled snapshot hash differs')
    if sha(args.kernel)!=receipt['debug']['sha256']:raise ValueError('kernel changed during pairing')
    summary=dict(status='PASS',scope=card['scope'],voltage_absolute_V=card['voltage_absolute_V'],
                 forced_times_s=card['forced_times_s'],time_policy=card['time_policy'],
                 kernel=dict(name=args.kernel.name,sha256=sha(args.kernel),receipt_sha256=sha(args.kernel_receipt),
                             owned_source_sha256=receipt['source_sha256'],compiled_snapshots_sha256=receipt['snapshot_sha256']),
                 python_wrapper=dict(identity_basis='all Python source hashes at execution; no Git query',source_sha256=python_hashes),
                 checker_sha256=sha(Path(__file__)),case_sha256=sha(root/'case.json'),records=results,
                 limitations=['Only these three microcases; no original MUX/task pass or new Q.',
                              'Native PSF, full responses and kernel are local retained evidence, not public reference downloads.',
                              receipt.get('identity_basis','EVAS kernel and Python SCS wrapper have separately recorded execution identities.')])
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (args.output/'execution.json').write_text(json.dumps(dict(argv=sys.argv,python_executable=sys.executable,summary_sha256=sha(args.output/'summary.json')),indent=2)+'\n')
    print(json.dumps([dict(case=r['case'],status=r['status'],EVAS_rows=r['checks']['EVAS']['native_rows'],Spectre_rows=r['checks']['Spectre']['native_rows'],pairs=len(r['exact_native_pairs'])) for r in results]))


if __name__=='__main__': main()
