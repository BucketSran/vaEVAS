"""Portable task verifier. Requires licensed Spectre on PATH; Python stdlib only.

Canonical copy: regenerate task-local copies with experiments.va_screen.build_tasks.
"""
import argparse
import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_psf(path):
    lines=path.read_text().splitlines()
    if not lines or lines[-1].strip()!='END':raise ValueError('incomplete PSF')
    start=lines.index('VALUE')+1;rows=[];row=None
    for line in lines[start:-1]:
        m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line.strip())
        if not m:raise ValueError('unsupported PSF value: '+line[:100])
        if m[1]=='time':
            if row is not None:rows.append(row)
            row={'time':float(m[2])}
        else:
            if row is None or m[1] in row:raise ValueError('duplicate signal or missing time')
            row[m[1]]=float(m[2])
    if row is not None:rows.append(row)
    return rows


def evaluate(rows, case):
    names={p['node'] for p in case['samples']}|{p['node'] for p in case['edges']}
    if len(rows)<2 or any(not names.issubset(r) for r in rows):
        return dict(passed=False,reason='missing signals or waveform')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        return dict(passed=False,reason='non-finite waveform')
    ts=[r['time'] for r in rows]
    if any(a>b for a,b in zip(ts,ts[1:])):raise ValueError('unordered PSF times')
    if abs(ts[0])>1e-15 or abs(ts[-1]-case['stop'])>max(1e-15,case['stop']*1e-8):
        return dict(passed=False,reason='incomplete transient interval')
    failures=[];worst=0;badpoints=0
    for sample in case['samples']:
        t=sample['t'];j=bisect.bisect_right(ts,t)-1;j=max(0,min(j,len(rows)-2))
        a,b=rows[j],rows[j+1];v=a[sample['node']]
        if ts[j+1]>ts[j]:v+=(b[sample['node']]-v)*(t-ts[j])/(ts[j+1]-ts[j])
        error=abs(v-sample['value']);worst=max(worst,error/sample['atol'])
        if error>sample['atol']:
            badpoints+=1
            if len(failures)<12:failures.append(dict(kind='sample',**sample,observed=v))
    badedges=0;edge_counts={}
    for spec in case['edges']:
        observed=[];node=spec['node'];level=spec['threshold']
        for a,b in zip(rows,rows[1:]):
            if (a[node]<level<=b[node]) or (a[node]>level>=b[node]):
                t=a['time']+(b['time']-a['time'])*(level-a[node])/(b[node]-a[node])
                if t>=spec.get('start',0):observed.append(t)
        expected=spec['times'];edge_counts[node]=dict(expected=len(expected),observed=len(observed))
        if len(observed)!=len(expected):
            badedges+=1;failures.append(dict(kind='edge_count',node=node,**edge_counts[node]))
        else:
            errors=[abs(a-b) for a,b in zip(observed,expected)]
            if errors and max(errors)>spec['atol']:
                k=max(range(len(errors)),key=errors.__getitem__);badedges+=1
                failures.append(dict(kind='edge_time',node=node,index=k,expected=expected[k],observed=observed[k],atol=spec['atol']))
    return dict(passed=badpoints==0 and badedges==0,sample_count=len(case['samples']),bad_samples=badpoints,
                bad_edge_checks=badedges,edge_counts=edge_counts,worst_normalized_sample_error=worst,failures=failures)


def verify(candidate, output):
    output.mkdir(parents=True,exist_ok=True)
    cases_path=Path(__file__).with_name('cases.json');cases=json.loads(cases_path.read_text())
    report=dict(candidate_sha256=sha(candidate),cases_sha256=sha(cases_path),checker_sha256=sha(__file__),cases=[],status='completed')
    text=candidate.read_text()
    includes=re.findall(r'`include\s+"([^"]+)"',text)
    if any(i not in ['disciplines.vams','constants.vams','discipline.h','constants.h'] for i in includes) or re.search(r'\$(?:system|fopen|fwrite|fdisplay|readmem\w*)\b',text):
        report.update(status='submission_contract_violation',reward=0,reason='external I/O or nonstandard include')
    elif not shutil.which(os.environ.get('SPECTRE','spectre')):
        report.update(status='infrastructure_error',reward=None,reason='Spectre unavailable')
    else:
        binary=os.environ.get('SPECTRE','spectre')
        report['spectre_version']=subprocess.run([binary,'-W'],capture_output=True,text=True,timeout=30).stdout.strip()
        for case in cases:
            work=output/case['name'];work.mkdir()
            shutil.copyfile(candidate,work/'dut.va');(work/'tb.scs').write_text(case['netlist'])
            argv=[binary,'-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+lqtimeout','5','+mt=1']
            start=time.monotonic()
            try:
                with (work/'stdout.log').open('w') as stream:
                    completed=subprocess.run(argv,cwd=work,stdout=stream,stderr=subprocess.STDOUT,timeout=90)
                log=(work/'stdout.log').read_text(errors='replace')
                record=dict(name=case['name'],returncode=completed.returncode,elapsed_s=time.monotonic()-start)
                record['log_tail']=log[-5000:];record['netlist_sha256']=sha(work/'tb.scs')
                if re.search(r'(license.*(?:not available|failed|failure|unable)|unable.*license|No such file or directory.*spectre)',log,re.I):
                    record.update(status='infrastructure_error',passed=False)
                elif completed.returncode!=0:
                    record.update(status='compile_or_simulation_failure',passed=False)
                else:
                    wave=work/'psf/tran.tran.tran'
                    if not wave.exists():record.update(status='missing_waveform',passed=False)
                    else:
                        record.update(evaluate(read_psf(wave),case));record.update(status='graded',waveform_sha256=sha(wave))
            except subprocess.TimeoutExpired:
                record=dict(name=case['name'],status='simulation_timeout',passed=False)
            except Exception as exc:
                record=dict(name=case['name'],status='checker_error',passed=False,error=f'{type(exc).__name__}: {exc}')
            report['cases'].append(record)
        if any(c['status'] in ['infrastructure_error','checker_error'] for c in report['cases']):
            report.update(status='infrastructure_error',reward=None)
        else:report['reward']=int(all(c['passed'] for c in report['cases']))
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['reward'] is not None:(output/'reward.txt').write_text(str(report['reward'])+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=verify(args.candidate.resolve(),args.output.resolve())
    print(json.dumps(dict(status=result['status'],reward=result['reward'])))
    raise SystemExit(2 if result['reward'] is None else 0)
