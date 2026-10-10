"""Recompute the pilot from collected raw data and qualify the actual settings.

Does not rewrite runner receipts. Known conservative-preset transformations are
recorded explicitly; an unexplained discrepancy remains evidence insufficient.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
from inputs import BACKENDS, sha
from observations import read_native
from precision_checker import assess


def load(p):return json.loads(p.read_text())


def qualification(work, backend, record, rows):
    settings=record.get('effective_settings',{})
    actual=dict(settings.get('actual',{}));requested=settings.get('requested',{})
    issues=[];notes=[];extra={}
    if not actual:issues.append('no actual settings readback')
    needed=('reltol','vabstol') if backend=='evas' else ('reltol','vabstol','iabstol')
    for key in needed:
        if not isinstance(actual.get(key),(float,int)) or not math.isfinite(actual[key]) or actual[key]<=0:
            issues.append('missing actual '+key)
    for key in settings.get('mismatches',[]):
        # The predeclared conservative preset reduces transient reltol by 10.
        # Require matching independent log and PSF metadata, not just tighter values.
        scoped=settings.get('scoped_readback',{})
        preset=(backend=='spectre' and key=='reltol' and 'errpreset=conservative' in (work/'tb.scs').read_text()
                and math.isclose(actual[key],requested[key]/10,rel_tol=1e-12)
                and scoped.get('psf_effective',{}).get('reltol',{}).get('value')==actual[key])
        if preset:notes.append('conservative preset: transient reltol is requested global reltol / 10; log and PSF agree')
        else:issues.append('unexplained requested/actual mismatch: '+key)
    if backend=='openvaf_r_ngspice':
        lines=(work/'simulate.log').read_text().splitlines()
        method_line=settings.get('scoped_readback',{}).get('effective',{}).get('method',{}).get('line')
        if isinstance(method_line,int):
            post='\n'.join(lines[method_line-1:])
            for key in ('trtol','chgtol','itl4'):
                found=re.findall(r'(?m)^'+key+r'[^=\n]*=\s*(\S+)',post)
                extra[key]={'values':sorted(set(found)),'scope':'post_analysis_loaded_circuit'}
    if backend=='gnucap_modelgen':
        text=(work/'simulate.log').read_text()
        methods=re.findall(r'(?m)^\.options\s+method=(\w+)',text)
        if not methods or set(methods)!={'trap'}:issues.append('Gnucap method readback absent or changed')
        else:actual['method']='trap'
        for key in ('dtmin','trtol','dtratio'):
            found=re.findall(r'\b'+key+r'=\s*(\S+)',text)
            extra[key]=sorted(set(found))
        if any(not isinstance(r.get('bench_ref'),(float,int)) or not math.isfinite(r['bench_ref']) or abs(r['bench_ref'])>1e-10 for r in rows):
            issues.append('invalid or missing Gnucap ground reference')
    elif backend!='evas' and actual.get('method')!=('traponly' if backend=='spectre' else 'trap'):
        issues.append('integration method missing or unexpected')
    if backend=='evas':
        raw=load(work/'raw-response.json');ts=load(work/'requested_times.json')
        evidence=raw.get('observation_evidence',{})
        if evidence.get('initial_settled') is not True or evidence.get('schema_version')!=1 or evidence.get('nodes')!=raw.get('nodes'):
            issues.append('missing settled initial/response identity')
        if record.get('observation_mode')=='ordinary-query':
            e={'times':raw.get('transient',{}).get('times'),'sample_origins':evidence.get('sample_origins',[]),
               'voltages_V':[v['voltages'] for v in raw.get('solutions',[])]}
            allowed=('accepted_controller_frame','certified_causal_frame')
            extra['observation_mode']='physical-state query at exact requested time; not forced solve or accepted-step claim'
        else:
            e=raw.get('strobe_evidence',{});allowed=('stateless_working_point','accepted_controller_frame','implicit_history_evaluation')
            extra['observation_mode']='forced solver observation'
        origins=e.get('sample_origins',[])
        if e.get('times')!=ts or len(origins)!=len(ts) or any(o not in allowed for o in origins):
            issues.append('invalid observation provenance')
        expected=[dict(zip(['time',*raw['nodes']],[t,*v],strict=True)) for t,v in zip(e.get('times',[]),e.get('voltages_V',[]),strict=True)]
        if rows!=expected:issues.append('CSV differs from raw response values or times')
        extra.update(origins=sorted(set(origins)),max_step_applied=settings.get('max_step_applied'),
                     engine=raw.get('engine'),accepted_steps=raw.get('transient',{}).get('accepted_steps'),
                     control_note='iabstol/method unsupported; max_step_applied is reported, never inferred')
    return {'status':'qualified' if not issues else 'evidence_insufficient','issues':issues,
            'notes':notes,'actual':actual,'requested':requested,'additional_controls':extra,
            'scope':'finite exported native/forced observations; ngspice/Gnucap stop/maxstep are deck-only controls, with actual extent independently checked'}


def report(base):
    frozen=base/'inputs';data=load(frozen/'cards.json')
    for rel,digest in load(frozen/'MANIFEST.json').items():
        if sha(frozen/rel)!=digest:raise ValueError('frozen input drift: '+rel)
    # Reanalysis is allowed only with the same mathematical checker and reader.
    for rel in ('evas/validation/paper/precision_checker.py','experiments/backends/paper/inputs.py','experiments/backends/paper/observations.py',
                'experiments/archive/dvs2-starter-pilot/analyze.py','experiments/archive/dvs2-starter-pilot/suite.py'):
        if sha(ROOT/rel)!=load(frozen/'SOURCE_IDENTITY.json')[rel]:raise ValueError('analysis dependency drift: '+rel)
    dependencies=('evas/validation/paper/precision_checker.py','experiments/backends/paper/inputs.py',
                  'experiments/backends/paper/observations.py','experiments/archive/dvs2-starter-pilot/analyze.py',
                  'experiments/archive/dvs2-starter-pilot/suite.py')
    result={'schema_version':1,'purpose':'eight development-informed conditions; finite engineering acceptance, not a held-out final paper suite',
            'source':load(base/'SOURCE_PROVENANCE.json'),'cards_sha256':sha(frozen/'cards.json'),
            'input_manifest_sha256':sha(frozen/'MANIFEST.json'),'analysis_sha256':sha(Path(__file__)),
            'analysis_dependencies':{p:sha(ROOT/p) for p in dependencies},
            'limits':{'stage_s':90,'memory_bytes':4294967296,'file_bytes':33554432,'condition_bytes':268435456,'condition_limit_enforcement':'active polling, not a filesystem quota','serial':True,'automatic_retries':False},
            'budgets':data['budgets'],'profiles':data['profiles'],'lanes':{},'results':[],'summary':{}}
    lanes=[(family,backend,family+'-'+backend) for family in ('sample_hold','first_order') for backend in BACKENDS]
    if (base/'collected/query-evas/COLLECTION.json').is_file():lanes.append(('sample_hold','evas','query-evas'))
    for family,backend,lane in lanes:
            col=base/'collected'/lane;out=col/'outputs'/lane
            manifest=load(out/'FILE_MANIFEST.json')
            for rel,entry in manifest.items():
                path=(out/rel).resolve()
                if not path.is_relative_to(out.resolve()) or sha(path)!=entry['sha256'] or path.stat().st_size!=entry['bytes']:raise ValueError('raw artifact drift: '+rel)
            collection=load(col/'COLLECTION.json')
            if sha(col/'raw.tar.gz')!=collection['archive_sha256']:raise ValueError('archive drift')
            operator=load(col/'operator-receipts'/(lane+'.json'))
            if not operator.get('cleanup_confirmed') or operator.get('child_exit_code')!=0 or operator.get('status')!='complete' or operator.get('exit_code')!=0:
                raise ValueError('operator incomplete')
            if lane=='query-evas':
                query_identity=load(col/'QUERY_IDENTITY.json')
                if sha(col/'repo/experiments/backends/support/precision_query.py')!=query_identity['driver_sha256'] or sha(col/'query_control.py')!=query_identity['query_control.py']:
                    raise ValueError('query driver identity mismatch')
                result['query_identity']=query_identity
            tool=load(out/'TOOL_IDENTITY.json')
            # Omit machine paths and stage command payloads from the public compact receipt.
            identity={k:tool[k] for k in ('binary_sha256','version','compiler_sha256','images','kernel_sha256','reported','unknowns') if k in tool}
            if 'versions' in tool:identity['versions']={k:v['self_report'] for k,v in tool['versions'].items()}
            result['lanes'][lane]={'archive_sha256':collection['archive_sha256'],'verified_files':len(manifest),
                  'availability':'local-only; source recipes in this checkout, raw archive retained locally and on existing server',
                  'tool_identity_sha256':sha(out/'TOOL_IDENTITY.json'),'tool':identity,'cleanup_confirmed':True}
            if backend=='evas':
                build=load(col/'build/BUILD.json')
                result['lanes'][lane]['build']={k:build[k] for k in ('source_revision','source_manifest_sha256','kernel_sha256','cargo_lock_sha256','toolchain','returncode')}
                result['lanes'][lane]['build']['compiler_identity']={
                    name:{k:identity[k] for k in ('actual_binary_sha256','version')}
                    for name,identity in build.get('compiler_identity',{}).items()}
            for record in load(out/'EXECUTION.json'):
                work=out/'runs'/record['label'];row={k:record[k] for k in ('condition','profile','family','backend','status')}
                row['execution_status']=row.pop('status')
                row['observation_mode']=record.get('observation_mode','forced-observation')
                row['lane']=lane
                if row['execution_status']=='not_run':
                    row.update(status='not_run',reason=record.get('reason','batch stopped before this condition'))
                    result['results'].append(row)
                    continue
                row['source_sha256']=sha(work/'dut.va');row['deck_sha256']=sha(work/record['deck'])
                row['receipt_sha256']=sha(work/'RESULT.json');row['runner_verdict']=record.get('engineering_verdict')
                if row['execution_status']=='waveform_available':
                    rows=read_native(work/record['waveform'],backend);card=load(work/'condition.json')
                    assessment=assess(card,rows,data['budgets']);q=qualification(work,backend,record,rows)
                    row['status']=assessment['status'] if q['status']=='qualified' or assessment['status']!='pass' else 'evidence_insufficient'
                    row['assessment']={k:v for k,v in assessment.items() if k!='event_records'}
                    if assessment.get('event_records'):
                        row['events']={'count':len(assessment['event_records']),
                            'max_bracket_s':max(e['counter_bracket_s'][1]-e['counter_bracket_s'][0] for e in assessment['event_records']),
                            'max_hold_drift_V':max(e['hold_drift_upper_V'] for e in assessment['event_records'])}
                    row['qualification']=q;row['waveform_sha256']=sha(work/record['waveform'])
                else:
                    row['status']=row['execution_status'];row['reason']=record.get('reason')
                    row['logs']={n:sha(work/n) for n in ('compile.log','simulate.log') if (work/n).exists()}
                result['results'].append(row)
    for family in ('sample_hold','first_order'):
        result['summary'][family]={}
        for backend in BACKENDS:
            cards=[c['id'] for c in data['cards'] if c['family']==family];selection={}
            for cid in cards:
                attempts=[r for r in result['results'] if r['backend']==backend and r['condition']==cid]
                passing=next((r for p in data['profiles'] for r in attempts if r['profile']==p['id'] and r['status']=='pass'),None)
                selection[cid]={'selected_profile':passing['profile'] if passing else None,
                                'selected_observation':passing['observation_mode'] if passing else None,
                                'attempts':{r['observation_mode']+':'+r['profile']:r['status'] for r in attempts}}
            result['summary'][family][backend]={'passed':sum(v['selected_profile'] is not None for v in selection.values()),'total':len(cards),'conditions':selection}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    value=report(a.base.resolve())
    with a.output.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps(value['summary'],indent=2,ensure_ascii=False))
