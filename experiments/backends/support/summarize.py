"""Collect verified receipts without changing checks or treating missing data as passes."""
from pathlib import Path
import argparse
import collections
import copy
import hashlib
import json
import re

BACKENDS=('spectre','evas','openvaf_r_ngspice','gnucap_modelgen')
ROOT=Path(__file__).resolve().parents[3]

def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p,base):return {'path':str(p.relative_to(base)),'sha256':sha(p),'availability':'local-only'}

def verify(lane):
    manifest=load(lane/'FILE_MANIFEST.json')
    for rel,item in manifest.items():
        p=lane/rel
        if sha(p)!=item['sha256'] or p.stat().st_size!=item['bytes']:raise ValueError('manifest mismatch: '+str(p))
    return load(lane/'EXECUTION.json')

def compact(r,lane,base):
    c={k:copy.deepcopy(v) for k,v in r.items() if k in ('condition','backend','status','reason','failure_stage','waveform_sha256','source_sha256','rows_sha256','assessment','effective_settings')}
    c['receipt']=ref(lane/'runs'/r['condition']/'RESULT.json',base)
    if 'effective_settings' in c:
        c['effective_settings']={k:v for k,v in c['effective_settings'].items() if k in ('actual','requested','mismatches','status','reason','max_step_applied')}
    native=lane/'runs'/r['condition']/'spectre.log'
    if native.exists():
        c['native_control_excerpt']={'source':ref(native,base),'claim':'verbatim printed controls; values have display rounding',
            'lines':[line for line in native.read_text().splitlines() if re.match(r'^    (stop|maxstep|reltol|abstol\(V\)|abstol\(I\)|method) =',line)]}
    if 'assessment' in c:
        a=c['assessment'];bound=a.pop('boundary_rows',[]);a['boundary_row_count']=len(bound)
        if bound:a['boundary_record_location']='receipt.assessment.boundary_rows; not graded'
    c['stages']=[{k:s.get(k) for k in ('stage','returncode','timeout','status','log_sha256','cleanup')} for s in r.get('stages',[])]
    errors=[]
    for name in ('compile.log','simulate.log'):
        path=lane/'runs'/r['condition']/name
        if path.exists():
            lines=path.read_text(errors='replace').splitlines()
            errors += [line[:500] for line in lines if any(s in line.lower() for s in ('error','unsupported','not supported','assertion','^ ?','abort'))][:6]
    if errors:c['diagnostic_excerpts']=errors[:8]
    return c

def summarize(base):
    core=[];supp=[];history=[];tools={};receipts=[];new_support_attempts=0
    expected={c['id']:c for c in load(ROOT/'evas/validation/support/cases-v2.json')['cards']}
    original={c['id']:c for c in load(ROOT/'evas/validation/support/cases-v1.json')['cards']}
    assert set(expected)==set(original)
    for cid,c in expected.items():
        assert {k:v for k,v in c.items() if k!='source'}=={k:v for k,v in original[cid].items() if k!='source'},cid
    for b in BACKENDS:
        lane=base/'collected'/b/'outputs'/b
        rows=verify(lane);assert len(rows)==12
        tools[b]={'core':ref(lane/'TOOL_IDENTITY.json',base)}
        for r in rows:
            a=load(base/'assessment'/(b+'-'+r['condition']+'-assessment.json'))
            core.append({'condition':r['condition'],'backend':b,'execution':r['status'],'qualification':a['status'],
                         'receipt':ref(lane/('final-record-'+r['condition']+'.json'),base),
                         'assessment':ref(base/'assessment'/(b+'-'+r['condition']+'-assessment.json'),base)})
        old=base/'supplement-collected'/b/'supplement-outputs'/b
        new=base/'portable-v2/collected'/b/'outputs'/b
        oldrows={r['condition']:r for r in verify(old)};newrows={r['condition']:r for r in verify(new)}
        assert set(newrows)==set(expected)-{'LANG-functions','LANG-array-events'}
        new_support_attempts+=len(newrows)
        tools[b]['support']=ref(new/'TOOL_IDENTITY.json',base)
        for cid,c in expected.items():
            origin=old if cid in ('LANG-functions','LANG-array-events') else new
            r=(oldrows if origin==old else newrows)[cid]
            source=origin/'runs'/cid/'dut.va'
            assert sha(source)==hashlib.sha256(c['source'].encode()).hexdigest(),cid
            rec=compact(r,origin,base);rec['source_generation']='v1 unchanged reuse' if origin==old else 'v2 new execution'
            supp.append(rec)
        history.append({'backend':b,'configurations':len(oldrows),'statuses':dict(collections.Counter(r.get('assessment',{}).get('status',r['status']) for r in oldrows.values())),
                        'receipt':ref(old/'EXECUTION.json',base),'retained':True})
        for p in [base/'collected'/b/'operator-receipts'/(b+'.json'),base/'supplement-collected'/b/'supplement-receipts'/(b+'.json'),base/'portable-v2/collected'/b/'operator-receipts'/(b+'.json')]:
            rec=load(p);assert rec['cleanup_confirmed'] is True and rec.get('finished_unix_ns')
            receipts.append(ref(p,base))
    sweep=base/'slew-scan/collected/spectre/outputs/spectre'
    sweep_rows=verify(sweep);assert len(sweep_rows)==3
    sweep_receipt=base/'slew-scan/collected/spectre/operator-receipts/spectre.json'
    assert load(sweep_receipt)['cleanup_confirmed']
    receipts.append(ref(sweep_receipt,base))
    paired=load(base/'paired/comparisons.json')
    counts={b:{'core_execution':dict(collections.Counter(r['execution'] for r in core if r['backend']==b)),
                'core_qualification':dict(collections.Counter(r['qualification'] for r in core if r['backend']==b)),
                'support':dict(collections.Counter(r.get('assessment',{}).get('status',r['status']) for r in supp if r['backend']==b))} for b in BACKENDS}
    keys=[(r['condition'],r['backend']) for r in core+supp]
    assert len(keys)==len(set(keys)), 'duplicate main comparison slot'
    return {'schema_version':1,'run_id':base.name,'source_revision':load(base/'SOURCE_PROVENANCE.json')['source_revision'],
            'claim':'Observed execution and finite outputs; no all-domain support, full uncertainty qualification, or performance claim',
            'counts':counts,'core':core,'support':supp,'superseded_v1':history,
            'spectre_slew_setting_scan':[compact(r,sweep,base) for r in sweep_rows],
            'core_exact_time_pairs':[r for r in paired['comparisons'] if r['test_backend']=='evas'],
            'tool_identities':tools,'operator_receipts':receipts,
            'tool_version_reports':{b:({k:v.get('self_report') for k,v in load(base/'collected'/b/'outputs'/b/'TOOL_IDENTITY.json').get('versions',{}).items()} or {k:v for k,v in load(base/'collected'/b/'outputs'/b/'TOOL_IDENTITY.json').items() if k in ('version','reported','binary_sha256','kernel_sha256')}) for b in BACKENDS},
            'build':{'receipt':ref(base/'collected/evas/build/BUILD.json',base),'record':load(base/'collected/evas/build/BUILD.json')},
            'inputs':{str(p.relative_to(base)):sha(p) for p in [base/'inputs/INPUT_MANIFEST.json',base/'supplement-inputs/INPUT_MANIFEST.json',base/'portable-v2/inputs/INPUT_MANIFEST.json',base/'slew-scan/inputs/INPUT_MANIFEST.json']},
            'checked_in_sources':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'evas/validation/support/cases-v1.json',ROOT/'evas/validation/support/cases-v2.json',ROOT/'evas/validation/support/checker.py',ROOT/'evas/validation/support/test_checker.py',Path(__file__)]},
            'raw_availability':'local-only; paths relative to runs/'+base.name+'; original remote directories retained',
            'new_backend_configurations':len(core)+sum(h['configurations'] for h in history)+new_support_attempts+len(sweep_rows),
            'selected_base_slots':len(keys),'v2_non_source_contract_matches_v1':True,
            'selection':'core 48 new; support 60 = 52 portable v2 new + 8 unchanged v1 reused; all 60 v1 attempts and 3 Spectre settings probes retained'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    data=summarize(args.run.resolve())
    with args.output.open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps(data['counts'],indent=2))
