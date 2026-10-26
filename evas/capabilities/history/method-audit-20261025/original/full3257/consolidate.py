"""Validate full audit coverage and preserve separate execution and test verdicts."""
import collections, csv, hashlib, json, re
from pathlib import Path
OUT=Path(__file__).resolve().parent
PRIMARY=Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current')
ROOT=Path(json.loads((OUT/'scope.json').read_text())['source_root'])
inventory=json.loads((OUT/'inventory.json').read_text())
by_id={r['id']:r for r in inventory}
allowed={'no_defect_found','test_defect','mixed','evidence_gap'}
roles={'behavior','rejection','internal_contract','metamorphic','checker','mixed'}
rows=[];findings=[];reviews=[];errors=[]
for lane in range(1,7):
    inp=json.loads((OUT/f'input-{lane}.json').read_text())
    path=OUT/f'review-{lane}.json'
    if not path.exists():errors.append(f'missing lane {lane}');continue
    data=json.loads(path.read_text())
    expected={r['id'] for r in inp['methods']}
    reviewed=[r['id'] for r in data['rows']]
    if len(reviewed)!=len(set(reviewed)) or set(reviewed)!=expected:
        errors.append(f'lane {lane}: missing={len(expected-set(reviewed))} extra={len(set(reviewed)-expected)} duplicate={len(reviewed)-len(set(reviewed))}')
    read_files={f['path']:f for f in data.get('reviewed_files',[]) if isinstance(f,dict) and 'path' in f}
    for module in {r['module_file'] for r in inp['methods']}:
        if module not in read_files:errors.append(f'lane {lane}: module not recorded as read {module}')
    for name,record in read_files.items():
        p=Path(name) if Path(name).is_absolute() else ROOT/name
        if not p.exists() and name.startswith('runs/'):p=PRIMARY/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=record.get('sha256'):errors.append(f'lane {lane}: read file identity mismatch {name}')
    for row in data['rows']:
        if row['id'] not in expected:continue
        for k in ('oracle','assertion_assessment'):
            if not isinstance(row.get(k),str) or not row[k].strip():errors.append(f'{row["id"]}: empty {k}')
        if not row.get('contract') or not isinstance(row['contract'],(str,list)):errors.append(f'{row["id"]}: empty contract')
        if isinstance(row.get('contract'),list) and not all(isinstance(x,str) and x.strip() for x in row['contract']):errors.append(f'{row["id"]}: invalid contract references')
        if str(row.get('oracle','')).strip().endswith('exact answer/control expressions:') or re.fullmatch(r'Actual assertions:\s*\.',str(row.get('assertion_assessment','')).strip()):
            errors.append(f'{row["id"]}: empty extracted assertion/oracle; helper review required')
        if not isinstance(row.get('remaining_evidence'),(str,list)):errors.append(f'{row["id"]}: invalid remaining_evidence')
        if row.get('verdict') not in allowed:errors.append(f'{row["id"]}: invalid verdict')
        if row.get('role') not in roles:errors.append(f'{row["id"]}: invalid role')
        if not row.get('refs'):errors.append(f'{row["id"]}: no refs')
        for ref in row.get('refs',[]):
            m=re.fullmatch(r'([^:]+):(\d+)(?:[-–]\d+)?',ref)
            if m:
                p=ROOT/m[1]
                if not p.exists() and m[1].startswith('runs/'):p=PRIMARY/m[1]
                if not p.is_file() or not 1<=int(m[2])<=len(p.read_text().splitlines()):errors.append(f'{row["id"]}: bad ref {ref}')
        original=by_id[row['id']]
        p=ROOT/original['module_file']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=original['module_sha256']:errors.append(f'changed source {p}')
        verdict=row['verdict']
        action=('repair_test_before_using_affected_assertion' if verdict in ('test_defect','mixed') else
                'resolve_contract_or_oracle_gap_before_targeting' if verdict=='evidence_gap' else 'retain_for_stated_reviewed_scope')
        rows.append(dict(row,execution_outcome=original['outcome'],source_file=original['source_file'],
                         source_line=original['start_line'],source_method_sha256=original['method_sha256'],
                         source_module_sha256=original['module_sha256'],generated=original['generated'],
                         expected_failure=original['expected_failure'],lane=lane,development_action=action,
                         prior_failure_category=(original['prior_failure_audit'] or {}).get('category'),
                         prior_category_scope='historical failing-obligation classification only; not current test validity',
                         prior_capability_navigation=original.get('prior_mapping')))
    findings.extend(data.get('findings',[]))
    reviews.append(dict(lane=lane,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),methods=len(reviewed),limits=data.get('limits'),reviewed_files=data.get('reviewed_files'),withdrawn_findings=data.get('withdrawn_findings',[]),coordinator_corrections=data.get('coordinator_corrections',[])))
if len(rows)!=3257 or len({r['id'] for r in rows})!=3257:errors.append('full denominator not 3257')
finding_by_id={f['id']:f for f in findings}
if len(finding_by_id)!=len(findings):errors.append('duplicate finding IDs')
for row in rows:
    for fid in row.get('finding_ids',[]):
        if fid not in finding_by_id:errors.append(f'{row["id"]}: missing finding {fid}')
        elif row['id'] not in finding_by_id[fid].get('affected_ids',[]):errors.append(f'{row["id"]}: missing reverse finding mapping {fid}')
for f in findings:
    for ident in f.get('affected_ids',[]):
        if ident not in by_id:errors.append(f'{f["id"]}: unknown method {ident}')
result={'complete':not errors,'errors':errors,'rows':len(rows),'unique_ids':len({r['id'] for r in rows}),
        'source_modules':len({r['source_file'] for r in rows})}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
if errors:print(json.dumps(result,ensure_ascii=False));raise SystemExit(1)
rows.sort(key=lambda r:r['id'])
summary=dict(scope=json.loads((OUT/'scope.json').read_text()),
             audit_kind='full method source/contract/oracle/assertion audit; targeted probes; not full calibration or simulator qualification',
             verdict_counts=dict(collections.Counter(r['verdict'] for r in rows)),
             outcome_by_verdict={out:dict(collections.Counter(r['verdict'] for r in rows if r['execution_outcome']==out)) for out in sorted({r['execution_outcome'] for r in rows})},
             role_counts=dict(collections.Counter(r['role'] for r in rows)),
             finding_count=len(findings),reviews=reviews)
(OUT/'audit.json').write_text(json.dumps({'summary':summary,'rows':rows,'findings':findings},ensure_ascii=False,indent=2)+'\n')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
columns=['id','execution_outcome','verdict','role','source_file','source_line','contract','oracle','assertion_assessment','refs','finding_ids','remaining_evidence','development_action','prior_failure_category']
with (OUT/'methods.tsv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=columns,delimiter='\t');writer.writeheader()
    for row in rows:
        writer.writerow({k:json.dumps(row.get(k),ensure_ascii=False) if isinstance(row.get(k),(list,dict)) else str(row.get(k,'') or '').replace('\t',' ').replace('\n',' ') for k in columns})
print(json.dumps({k:summary[k] for k in ('verdict_counts','outcome_by_verdict','role_counts','finding_count')},ensure_ascii=False))
