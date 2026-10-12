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
import struct
import hashlib
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
from inputs import BACKENDS, sha
from observations import read_native
from precision_checker import assess
from settings_readback import (spectre, ReadbackError, SPECTRE_CALIBRATED_VERSION,
                               SPECTRE_FORMAT_CALIBRATION_SHA256)


def load(p):return json.loads(p.read_text())


SPECTRE_CALIBRATED_BINARY_SHA256 = '72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f'


def spectre_calibration_binary_value(raw, name):
    """Decode one captured double control record; reject incomplete evidence."""
    try:
        tag, length = struct.unpack_from('>II', raw)
        padded = (length+3)//4*4
        if tag != 0x23 or raw[8:8+length].decode() != name or len(raw) != 16+padded:
            raise ReadbackError('invalid calibration binary typed record')
        value = struct.unpack_from('>d', raw, 8+padded)[0]
    except (struct.error, UnicodeDecodeError) as exc:
        raise ReadbackError('invalid calibration binary typed record') from exc
    if not math.isfinite(value) or value <= 0:
        raise ReadbackError('invalid calibration binary control value')
    return value


def spectre_fullprecision_settings(work, tool, *, frozen_deck_sha256):
    """Explicit current-installation API; the caller verifies frozen execution.

    Tool identity must come from the external runner's actual binary/version
    preflight. The frozen hash comes from its verified input manifest, not a
    self-declared case flag. This only admits settings, never native observations
    or numerical acceptance. Default runner/readback behavior stays strict.
    """
    version = tool.get('version')
    if (tool.get('binary_sha256') != SPECTRE_CALIBRATED_BINARY_SHA256 or
            not isinstance(version,str) or
            not re.fullmatch(r'sub-version\s+'+re.escape(SPECTRE_CALIBRATED_VERSION),version.strip())):
        raise ReadbackError('uncalibrated Spectre producer identity')
    if not re.fullmatch('[0-9a-f]{64}',str(frozen_deck_sha256)) or sha(work/'tb.scs') != frozen_deck_sha256:
        raise ReadbackError('Spectre frozen deck identity mismatch')
    deck = (work/'tb.scs').read_text()
    lines = [line.split('//',1)[0].strip() for line in deck.splitlines()]
    options = [line for line in lines if re.match(r'^\w+ options(?:\s|$)',line)]
    trans = [line for line in lines if re.match(r'^\w+ tran(?:\s|$)',line)]
    if len(options) != 1 or len(trans) != 1 or not trans[0].startswith('tran tran '):
        raise ReadbackError('ambiguous Spectre producer deck scope')
    for name,value,line in [('digits','17',options[0]),('notation','sci',options[0]),
                            ('precision','"%.17g"',options[0]),('transres','1e-20',trans[0]),
                            ('errpreset','conservative',trans[0]),('method','traponly',trans[0])]:
        found = re.findall(r'(?<![\w])'+name+r'\s*=\s*("[^"]*"|[^\s]+)',line)
        if found != [value]:
            raise ReadbackError('uncalibrated Spectre producer control: '+name)
    evidence = (ROOT/'experiments/backends/paper/fixtures/spectre-21.1.0.509-format-calibration.json').read_bytes()
    # Pin actual captured evidence. A caller-provided verified flag is absent.
    if hashlib.sha256(evidence).hexdigest() != SPECTRE_FORMAT_CALIBRATION_SHA256:
        raise ReadbackError('Spectre calibration artifact changed')
    fixture = json.loads(evidence)
    calibration = spectre(fixture['log'],fixture['psf_header'],format_evidence=evidence)
    mapping = {'reltol':'reltol','abstol(V)':'vabstol_V','abstol(I)':'iabstol_A',
               'maxstep':'maxstep_s','stop':'stop_s'}
    # Independent binary typed records were captured from the configuration-
    # equivalent binary run; they are not inferred from requested controls.
    for name,key in mapping.items():
        raw = bytes.fromhex(fixture['binary_records_hex'][name])
        value = spectre_calibration_binary_value(raw,name)
        interval = calibration['psf_printed_intervals'][key]
        if not (Decimal(interval['log_lower_s_or_native']) <= Decimal.from_float(value)
                <= Decimal(interval['log_upper_s_or_native'])):
            raise ReadbackError('calibration log disagrees with exact binary control')
    log_path = work/'spectre.log'; psf_path = work/'psf/tran.tran.tran'
    scoped = spectre(log_path.read_text(),psf_path.read_text(),format_evidence=evidence)
    request = load(work/'requested_settings.json')
    expected = {'reltol':request['reltol'],'vabstol':request['vabstol_V'],
                'iabstol':request['iabstol_A'],'stop':request['stop_s'],'maxstep':request['maxstep_s']}
    keymap = {'reltol':'reltol','vabstol':'vabstol_V','iabstol':'iabstol_A','stop':'stop_s','maxstep':'maxstep_s','method':'method'}
    actual = {key:scoped['effective'][name]['value'] for key,name in keymap.items()}
    for key, field in [('reltol','reltol'),('vabstol','vabstol_V'),('iabstol','iabstol_A')]:
        if not math.isclose(scoped['global_user'][field]['value'],expected[key],rel_tol=1e-12,abs_tol=0):
            raise ReadbackError('Spectre observed global control differs from frozen request: '+key)
    mismatches = [key for key,value in expected.items() if not math.isclose(actual[key],value,rel_tol=1e-12,abs_tol=0)]
    binding = {'calibration_sha256':SPECTRE_FORMAT_CALIBRATION_SHA256,
               'binary_sha256':tool['binary_sha256'],'version':SPECTRE_CALIBRATED_VERSION,
               'frozen_deck_sha256':frozen_deck_sha256,'log_sha256':sha(log_path),'psf_sha256':sha(psf_path),
               'claim':'external preflight and frozen input identity required; observed log values with calibrated PSF printed-interval crosscheck'}
    return {'actual':actual,'requested':expected,'mismatches':mismatches,'scoped_readback':scoped,
            'producer_binding':binding,'status':'I' if mismatches else 'readback_matches',
            'claim':'settings readback only; not numerical or native observation qualification'}


def qualification(work, backend, record, rows, *, spectre_tool=None):
    settings=record.get('effective_settings',{})
    actual=dict(settings.get('actual',{}));requested=settings.get('requested',{})
    issues=[];notes=[];extra={}
    printed_mode = settings.get('scoped_readback',{}).get('readback_mode') == 'calibrated_sci_log_printed_psf_intervals'
    producer_verified = False
    if backend == 'spectre' and printed_mode:
        try:
            rebound = spectre_fullprecision_settings(work,spectre_tool or {},
                frozen_deck_sha256=settings.get('producer_binding',{}).get('frozen_deck_sha256'))
            if rebound != settings:
                raise ReadbackError('Spectre settings differ from raw producer readback')
            producer_verified = True
            extra['spectre_producer_binding'] = rebound['producer_binding']
        except (ReadbackError,OSError,ValueError,KeyError,TypeError) as exc:
            issues.append('unqualified calibrated Spectre producer: '+str(exc))
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
                and (scoped.get('psf_effective',{}).get('reltol',{}).get('value')==actual[key]
                     or (printed_mode and producer_verified)))
        if preset:notes.append('conservative preset: transient reltol is requested global reltol / 10; '+
            ('full-precision log and calibrated PSF printed interval are compatible' if printed_mode else 'log and PSF agree'))
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
    # Reanalysis is allowed only with the same mathematical checker and readers.
    dependencies=('evas/validation/paper/precision_checker.py','experiments/backends/paper/inputs.py',
                  'experiments/backends/paper/observations.py','experiments/backends/paper/settings_readback.py',
                  'experiments/archive/dvs2-starter-pilot/analyze.py','experiments/archive/dvs2-starter-pilot/suite.py')
    source_identity=load(frozen/'SOURCE_IDENTITY.json')
    for rel in dependencies:
        if sha(ROOT/rel)!=source_identity.get(rel):raise ValueError('analysis dependency drift: '+rel)
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
                    assessment=assess(card,rows,data['budgets'])
                    q=qualification(work,backend,record,rows,spectre_tool=tool if backend=='spectre' else None)
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
