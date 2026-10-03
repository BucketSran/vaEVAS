"""Read-only analysis and provenance-aware 31 x 4 x 2 result matrix."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from build_inputs import ROOT, verify, selected, sha
sys.path.insert(0,str(ROOT/'experiments/backends/dvs2-spectre-validation'))
from check_results import check, read_waveform

BACKENDS=('spectre','evas','openvaf_ngspice','gnucap')
LABELS={'observations_within_targets':'✓','observed_violation':'输出错误','unresolved':'未决',
        'observation_invalid':'观察不合格','compile_failed':'编译失败','compile_timeout':'编译超时',
        'execution_failed':'执行失败','runtime_timeout':'超时','missing_waveform':'缺波形'}


def read_json(p):return json.loads(p.read_text())


def analyze_record(work,r,c,backend):
    if r['status']!='waveform_available':return dict(status=r['status'],formal_dvs_qualification='I')
    if sha(work/'dut.va')!=r['source_sha256'] or sha(work/r['waveform'])!=r['waveform_sha256']:
        raise ValueError('run hash mismatch')
    try:
        rows=read_waveform(work/r['waveform'],backend)
        if backend=='gnucap' and (not rows or any('bench_ref' not in row or not math.isfinite(row['bench_ref']) or abs(row['bench_ref'])>1e-7 for row in rows)):
            return dict(status='observation_invalid',reason='ground alias observation invalid',formal_dvs_qualification='I')
        return check(rows,c)
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        return dict(status='observation_invalid',reason=str(exc),formal_dvs_qualification='I')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('new_evidence',type=Path);parser.add_argument('v1_evidence',type=Path)
    parser.add_argument('spectre_evidence',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();new=args.new_evidence;old=args.v1_evidence;spectre=args.spectre_evidence
    if args.output.exists() or any(args.output.resolve().is_relative_to(p.resolve()) for p in [new,old,spectre]):
        raise ValueError('output must be new and outside evidence')
    old_receipt=read_json(ROOT/'experiments/archive/dvs2-starter-pilot/results/ARCHIVE_RECEIPT.json')
    sp_receipt=read_json(ROOT/'experiments/backends/dvs2-spectre-validation/results/RECEIPT.json')
    counts={}
    for label,path,expected in [('new',new,sha(new/'FILE_MANIFEST.json')),('v1',old,old_receipt['file_manifest_sha256']),('spectre',spectre,sp_receipt['file_manifest_sha256'])]:
        counts[label]=len(verify(path,expected))
    identities=read_json(new/'SOURCE_IDENTITY.json')
    for rel,digest in identities.items():
        if rel.endswith('.py') and sha(ROOT/rel)!=digest:raise ValueError('analysis code differs from pre-run freeze: '+rel)
    sp_path=ROOT/'experiments/backends/dvs2-spectre-validation/results/analysis.json'
    if sha(sp_path)!=sp_receipt['analysis_sha256']:raise ValueError('Spectre analysis drift')
    sp={(r['condition'],r['profile']):r for r in read_json(sp_path)['records']}
    cases=read_json(new/'conditions.json');records=[]
    for backend in BACKENDS:
        for c in cases:
            for profile in ['base','fine']:
                if backend=='spectre':
                    r=sp[c['id'],profile]
                    record=dict(backend=backend,condition=c['id'],card=c['card'],profile=profile,
                        source_run_id=spectre.name,evidence_use='reused_analysis',execution_status=r['execution_status'],analysis=r['analysis'])
                else:
                    fresh=selected(c,backend)
                    work=(new/'runs'/backend/c['id']/profile) if fresh else old/'runs'/backend/c['id']/profile
                    r=read_json(work/'result.json');oc=read_json(work/'condition.json')
                    if (r['backend'],r['condition'],r['profile'])!=(backend,c['id'],profile):raise ValueError('run identity mismatch')
                    if fresh:
                        if oc!=c:raise ValueError('condition drift')
                    else:
                        if any(c.get(k)!=v for k,v in oc.items()):raise ValueError('historical contract differs')
                    if sha(work/'dut.va')!=sha(spectre/'runs'/c['id']/profile/'dut.va'):
                        raise ValueError('common source differs from Spectre')
                    a=analyze_record(work,r,c,backend)
                    record=dict(backend=backend,condition=c['id'],card=c['card'],profile=profile,
                        source_run_id=new.name if fresh else old.parent.name,evidence_use='new' if fresh else 'reused_execution_reanalyzed',
                        execution_status=r['status'],analysis=a)
                    if r.get('failure_stage'):record['failure_stage']=r['failure_stage']
                    if r.get('build',{}):record['build_status']=r['build']['status']
                records.append(record)
                print(backend,c['id'],profile,record['analysis']['status'],flush=True)
    assert len(records)==248 and len({(r['backend'],r['condition'],r['profile']) for r in records})==248
    summary={backend:{profile:dict(Counter(r['analysis']['status'] for r in records if r['backend']==backend and r['profile']==profile))
        for profile in ['base','fine']} for backend in BACKENDS}
    result=dict(run_id=new.name,date='2026-09-28',summary=summary,
        evidence_use=dict(Counter(r['evidence_use'] for r in records)),verified_file_counts=counts,
        evidence_manifests={p.name:sha(p/'FILE_MANIFEST.json') for p in [new,old,spectre]},
        analyzer_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__).resolve(),ROOT/'experiments/backends/dvs2-spectre-validation/check_results.py']},
        formal_dvs_qualification='I',records=records)
    args.output.mkdir(parents=True)
    (args.output/'matrix.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    with (args.output/'matrix.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['condition','backend','profile','status','execution_status','evidence_use','source_run_id'])
        writer.writeheader()
        for r in records:writer.writerow({**{k:r[k] for k in writer.fieldnames if k!='status'},'status':r['analysis']['status']})
    lines=['# 当前 31 条件 × 四方案结果','',
        '2026-09-28。每格为基础档 / 细化档；✓ 表示固定有限观测判据达标。正式观察资格仍为 I。','',
        '| # | 条件 | Spectre | EVAS 0.8.7 | OpenVAF-R＋ngspice | Gnucap＋modelgen |',
        '| ---: | --- | --- | --- | --- | --- |']
    lookup={(r['backend'],r['condition'],r['profile']):r for r in records}
    for i,c in enumerate(cases,1):
        cells=[' / '.join(LABELS[lookup[b,c['id'],p]['analysis']['status']] for p in ['base','fine']) for b in BACKENDS]
        lines.append('| '+str(i)+' | '+c['id']+' | '+' | '.join(cells)+' |')
    lines+=['','Spectre 复用本轮 62 条结果；EVAS、OpenVAF-R 各补测 34 条并对旧 28 条重判；Gnucap 在统一修订设置下重跑 62 条。',
            'Gnucap 使用具名零伏参考与 short=1e-9；各方案设置含义不视作等价。编译、执行、数值错误与观察资格不足分别保留。',
            '完整证据、统计和限制见[报告](../README.md)；逐配置数据见[matrix.json](matrix.json)。','']
    (args.output/'MATRIX.md').write_text('\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
