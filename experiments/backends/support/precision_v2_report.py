"""Qualified v2 reanalysis; never overwrite original execution assessments."""
import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from precision_v2 import assess
from precision_report import qualification as legacy_qualification
from inputs import BACKENDS, sha
from observations import read_native


def load(path):return json.loads(path.read_text())


def step_path_is_verified(evidence,image):
    """Check identity of an explicitly reviewed installed-source audit.

    This verifies the audit's attachments, not the scientific judgment in the
    review. A boolean or an image tag alone is not parameter-path evidence.
    Attachment paths are relative to this repository, including retained runs.
    """
    if evidence.get('verified') is not True or not isinstance(image,str) or not image:
        return False
    if evidence.get('image_id')!=image:return False
    try:
        for field in ('artifact','review'):
            entry=evidence[field];path=(ROOT/entry['path']).resolve()
            if not path.is_relative_to(ROOT.resolve()) or sha(path)!=entry['sha256']:return False
        audit=load(ROOT/evidence['artifact']['path'])
        return (audit.get('image_id')==image and
                audit.get('method')=='installed_source_parameter_path' and
                set(audit.get('controls',[]))=={'maxstep','stop'} and
                bool(audit.get('source_hashes')) and bool(audit.get('binary_hashes')) and
                isinstance(evidence['review'].get('reviewer'),str) and
                bool(evidence['review']['reviewer'].strip()))
    except (OSError,ValueError,KeyError,TypeError):return False


def verify_case_inputs(work,frozen_work,plan_entry):
    """The executed reference, controls and observations must be the frozen ones."""
    for name in ('dut.va',plan_entry['deck'],'condition.json','requested_settings.json',
                 'requested_times.json','observation_plan.json'):
        if sha(work/name)!=sha(frozen_work/name):raise ValueError('executed input drift: '+name)
    if sha(work/'dut.va')!=plan_entry['source_sha256']:raise ValueError('executed model identity mismatch')


def control_qualification(work,backend,record,rows,contract,tool,step_evidence=None):
    q=legacy_qualification(work,backend,record,rows)
    issues=q['issues'];actual=q['actual'];req=load(work/'requested_settings.json')
    # Verify against the frozen request, not merely a self-consistent readback.
    for key,field in (('reltol','reltol'),('vabstol','vabstol_V'),('iabstol','iabstol_A')):
        if backend=='evas' and key=='iabstol':continue
        expected=req[field]/10 if backend=='spectre' and key=='reltol' else req[field]
        value=actual.get(key)
        if type(value) not in (float,int) or not math.isclose(value,expected,rel_tol=1e-12,abs_tol=0):
            issues.append('actual control does not match frozen profile: '+key)
    extras={};log=(work/'simulate.log').read_text() if (work/'simulate.log').exists() else ''
    expected_extra={k:v for k,v in contract['controls'][backend].items() if k in ('trtol','chgtol','itl4','dtmin','dtratio')}
    if backend=='openvaf_r_ngspice':
        post=log.rsplit('* Current simulation options *',1)[-1]
        for key,target in expected_extra.items():
            tokens=re.findall(r'(?m)^\s*'+key+r'\b[^=\n]*=\s*(\S+)',post)
            try:values=[float(t) for t in tokens]
            except ValueError:values=[]
            extras[key]=values
            if len(values)!=1 or not math.isclose(values[0],target,rel_tol=1e-12):issues.append('missing or mismatched loaded control: '+key)
    elif backend=='gnucap_modelgen':
        def spice_number(token):
            m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([a-zA-Z]?)',token)
            if not m:raise ValueError(token)
            return float(m[1])*{'':1.,'T':1e12,'G':1e9,'M':1e6,'k':1e3,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15,'a':1e-18}[m[2]]
        for key,target in expected_extra.items():
            tokens=re.findall(r'\b'+key+r'=\s*(\S+)',log)
            try:values=[spice_number(t) for t in tokens]
            except (ValueError,KeyError):values=[]
            extras[key]=sorted(set(values))
            if not values or any(not math.isclose(v,target,rel_tol=1e-12) for v in values):issues.append('missing or mismatched loaded control: '+key)
    if backend in ('evas','spectre'):
        for key,field in (('maxstep','maxstep_s'),('stop','stop_s')):
            value=actual.get(key)
            if type(value) not in (int,float) or not math.isclose(value,req[field],rel_tol=1e-12):issues.append('missing or mismatched runtime '+key)
        if backend=='evas' and q['additional_controls'].get('max_step_applied') is not True:
            issues.append('max_step was not applied')
    else:
        # Exact-version parser/solver audits can establish a setting path when
        # the installed binary has no runtime echo. A requested deck alone cannot.
        evidence=step_evidence or {}
        image_name='ngspice' if backend=='openvaf_r_ngspice' else 'gnucap'
        image=tool.get('images',{}).get(image_name,{}).get('config_id')
        if not step_path_is_verified(evidence,image):
            issues.append('maxstep/stop have no runtime echo or verified installed-version parameter path')
        else:
            q['step_setting_evidence']=evidence
            audit=load(ROOT/evidence['artifact']['path'])
            if backend=='gnucap_modelgen' and audit.get('mapping')=='gnucap-time-ticks-v1' and len(extras.get('dtmin',[]))==1:
                dtmin=extras['dtmin'][0]
                effective=math.floor(req['maxstep_s']/dtmin+.5)*dtmin
                q['source_mapped_controls']={'maxstep_s':effective,'stop_s':req['stop_s'],'dtmin_s':dtmin,
                    'basis':'reviewed installed transient parser and TIME_t round-to-tick cap; not a runtime echo'}
                if not math.isclose(effective,req['maxstep_s'],rel_tol=1e-12,abs_tol=0):
                    issues.append('maxstep is quantized to dtmin; effective cap differs from frozen profile')
            else:
                issues.append('audited maxstep/stop mapping is not implemented for this backend')
    q['verified_extra_controls']=extras;q['status']='qualified' if not issues else 'evidence_insufficient'
    q['scope']='finite native/forced observations; runtime control readbacks and any separately audited parameter paths are listed explicitly'
    return q


def select(results,contract):
    summary={}
    for family in ('sample_hold','first_order'):
        summary[family]={}
        cards=[c for c in contract['cards'] if c['family']==family]
        for backend in BACKENDS:
            lanes={}
            for tier in contract['tiers']:
                selected={};regressions=[]
                for card in cards:
                    attempts={r['profile']:r['tiers'][tier['id']]['status'] for r in results if r['backend']==backend and r['condition']==card['id']}
                    first=None;seen_pass=False
                    for p in contract['profiles']:
                        status=attempts.get(p['id'],'not_run')
                        if status=='pass':
                            if first is None:first=p['id']
                            seen_pass=True
                        elif seen_pass:regressions.append({'condition':card['id'],'profile':p['id'],'status':status})
                    selected[card['id']]={'selected_profile':first,'attempts':attempts}
                lanes[tier['id']]={'passed':sum(v['selected_profile'] is not None for v in selected.values()),
                                   'total':len(cards),'conditions':selected,'later_nonpass':regressions}
            summary[family][backend]=lanes
    return summary


def report(base,step_evidence=None):
    frozen=base/'inputs';contract=load(frozen/'cards.json');plan=load(frozen/'PLAN.json')
    for rel,digest in load(frozen/'MANIFEST.json').items():
        path=(frozen/rel).resolve()
        if not path.is_relative_to(frozen.resolve()) or sha(path)!=digest:raise ValueError('frozen input drift: '+rel)
    output={'schema_version':2,'analysis':'precision-engineering-v2','results':[],'lanes':{},
            'source':load(base/'SOURCE_PROVENANCE.json'),'input_manifest_sha256':sha(frozen/'MANIFEST.json'),
            'contract':{k:v for k,v in contract.items() if k!='cards'},
            'analysis_dependencies':{str(p.relative_to(ROOT)):sha(p) for p in
                [Path(__file__),ROOT/'evas/validation/paper/precision_v2.py',ROOT/'evas/validation/paper/precision_reference.py',
                 ROOT/'experiments/backends/support/precision_report.py',ROOT/'experiments/backends/paper/observations.py',
                 ROOT/'experiments/archive/dvs2-starter-pilot/analyze.py',ROOT/'experiments/archive/dvs2-starter-pilot/suite.py']},
            'claim':'finite development-informed conditions, not held-out paper suite; original v1 scores unchanged'}
    for family in ('sample_hold','first_order'):
        for backend in BACKENDS:
            lane=family+'-'+backend;col=base/'collected'/lane;out=col/'outputs'/lane
            selected=[p for p in plan if p['family']==family and p['backend']==backend]
            records={};tool={};lane_issues=[]
            if (out/'EXECUTION.json').exists():
                collection=load(col/'COLLECTION.json')
                if sha(col/'raw.tar.gz')!=collection['archive_sha256']:raise ValueError('archive identity mismatch')
                manifest=load(out/'FILE_MANIFEST.json')
                for rel,entry in manifest.items():
                    path=(out/rel).resolve()
                    if not path.is_relative_to(out.resolve()) or sha(path)!=entry['sha256'] or path.stat().st_size!=entry['bytes']:raise ValueError('execution file drift: '+rel)
                operator=load(col/'operator-receipts'/(lane+'.json'))
                if not operator.get('cleanup_confirmed'):raise ValueError('operator cleanup unconfirmed')
                if operator.get('status')!='complete' or operator.get('child_exit_code')!=0 or operator.get('exit_code')!=0:
                    lane_issues.append('operator did not confirm a completed execution')
                records={r['label']:r for r in load(out/'EXECUTION.json')}
                tool=load(out/'TOOL_IDENTITY.json') if (out/'TOOL_IDENTITY.json').exists() else {}
                output['lanes'][lane]={'archive_sha256':collection['archive_sha256'],'availability':'local-only',
                    'manifest_sha256':sha(out/'FILE_MANIFEST.json'),'cleanup_confirmed':True,
                    'tool':{k:v for k,v in tool.items() if k in ('version','binary_sha256','compiler_sha256','images','reported','kernel_sha256','unknowns')}}
                if backend=='evas':
                    build=load(col/'build/BUILD.json');output['lanes'][lane]['build']={k:build[k] for k in ('source_revision','source_manifest_sha256','kernel_sha256','cargo_lock_sha256','toolchain','returncode')}
                    if build['returncode']!=0 or build['kernel_sha256']!=tool.get('kernel_sha256'):raise ValueError('EVAS build identity mismatch')
            for p in selected:
                rec=records.get(p['label'],{'status':'not_run','reason':'missing finalized lane'})
                r={k:p[k] for k in ('condition','backend','family','profile','label')};r['execution_status']=rec['status']
                r['tiers']={q['id']:{'status':rec['status'],'reasons':[rec.get('reason','no completed waveform')]} for q in contract['tiers']}
                work=out/'runs'/p['label']
                if rec['status']=='waveform_available':
                    verify_case_inputs(work,frozen/p['work'],p)
                    rows=read_native(work/rec['waveform'],backend)
                    assessment=assess(load(work/'condition.json'),rows,contract)
                    q=control_qualification(work,backend,rec,rows,contract,tool,(step_evidence or {}).get(backend))
                    q['issues']+=lane_issues
                    if q['issues']:q['status']='evidence_insufficient'
                    r.update(assessment={k:v for k,v in assessment.items() if k!='event_records'},qualification=q,
                             waveform_sha256=sha(work/rec['waveform']),receipt_sha256=sha(work/'RESULT.json'))
                    r['tiers']={k:{**v,'status':'evidence_insufficient' if v['status']=='pass' and q['issues'] else v['status'],
                                   'reasons':v['reasons']+q['issues']} for k,v in assessment['tiers'].items()}
                elif work.exists():
                    r['logs']={n:sha(work/n) for n in ('compile.log','simulate.log') if (work/n).exists()}
                output['results'].append(r)
    output['summary']=select(output['results'],contract)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--step-evidence',type=Path);a=p.parse_args()
    value=report(a.base.resolve(),load(a.step_evidence) if a.step_evidence else None)
    with a.output.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps({f:{b:{q:v['passed'] for q,v in grades.items()} for b,grades in bs.items()} for f,bs in value['summary'].items()},indent=2))
