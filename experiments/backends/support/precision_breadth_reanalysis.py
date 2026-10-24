"""Reassess one collected breadth lane without changing its original receipts.

From the repository root, run::

    python3 -B experiments/backends/support/precision_breadth_reanalysis.py \\
        --primary CHECKER_CHECKOUT --inputs FROZEN_INPUTS \\
        --lane COLLECTED_OUTPUT_LANE --output NEW_ANALYSIS_DIRECTORY

The lane must have an exhaustive FILE_MANIFEST.json. Frozen inputs contain
cards.json, SOURCE_IDENTITY.json and MANIFEST.json. The output must be a new
directory outside the original lane. Use an ignored runs directory for bulk
artifacts. The tool copies its checker dependencies and runs from that snapshot.

REANALYSIS.json separates original execution, numerical, behavior, evidence,
configuration, native observations and runtime controls. Source or physical
input changes require new execution. Missing exact-input evidence remains
unknown, including F03/F04 threshold cases. Optional external open evidence
uses a separately sealed adapter/proof and original execution manifest; legacy
configuration, official profiles and actual integrator evidence all remain gates. Original verdicts and hashes remain
in each record. No simulator or remote command runs here.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import inspect
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''): h.update(block)
    return h.hexdigest()


def load(path): return json.loads(path.read_text())
def save(path, data): path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+'\n')


def raw_work(lane,label):
    runs=lane.resolve()/'runs';candidate=runs/label
    if runs.is_symlink() or candidate.is_symlink():raise ValueError('symlink raw work path')
    for parent in candidate.parents:
        if parent==runs:break
        if parent.is_symlink():raise ValueError('symlink raw work ancestor')
    resolved=candidate.resolve()
    if resolved==runs or not resolved.is_relative_to(runs):raise ValueError('raw label escapes runs directory')
    return resolved


def verified_bindings(inputs,manifest):
    path=inputs/'PROFILE_BINDINGS.json'
    if 'PROFILE_BINDINGS.json' not in manifest or path.is_symlink():
        raise ValueError('official profile bindings absent from verified input manifest')
    if sha(path)!=manifest['PROFILE_BINDINGS.json']:raise ValueError('official profile bindings hash drift')
    return load(path)


def freeze_inputs(inputs, output, source_hashes):
    """Bind the analysis to explicit scientific inputs without changing them."""
    manifest = load(inputs/'MANIFEST.json')
    verified_bindings(inputs,manifest)
    for name, digest in manifest.items():
        path = (inputs/name).resolve()
        if not path.is_relative_to(inputs.resolve()) or sha(path) != digest:
            raise ValueError('frozen input hash drift: '+name)
    expected = load(inputs/'SOURCE_IDENTITY.json')
    required = [name for name in expected if name.endswith('.py')]
    required += ['evas/validation/paper/precision-v2.json']
    if any(source_hashes.get(name) != expected.get(name) for name in required):
        raise ValueError('analysis scientific sources differ from explicit frozen inputs')
    save(output/'OFFICIAL_INPUT_IDENTITY.json', {'path':str(inputs.resolve()),
         'manifest_sha256':sha(inputs/'MANIFEST.json'), 'cards_sha256':sha(inputs/'cards.json')})
    shutil.copyfile(inputs/'cards.json',output/'OFFICIAL_CARDS.json')
    shutil.copyfile(inputs/'PROFILE_BINDINGS.json',output/'OFFICIAL_PROFILE_BINDINGS.json')
    identity=load(output/'OFFICIAL_INPUT_IDENTITY.json')
    identity['profile_bindings_sha256']=sha(inputs/'PROFILE_BINDINGS.json')
    save(output/'OFFICIAL_INPUT_IDENTITY.json',identity)


def profile_binding(card, work, original, bindings):
    """Certify the requested configuration belongs to this designated target."""
    requested_path=work/'requested_settings.json';input_path=work/'INPUT_IDENTITY.json'
    issues=[];expected={};requested=load(requested_path) if requested_path.is_file() else {}
    backend=original['backend'];tier=original['tier']
    expected_label=card['id']+'--'+tier
    if original.get('label')!=expected_label:
        issues.append({'field':'RESULT.label','expected':expected_label,'actual':original.get('label')})
    profile_id=bindings.get('backend_tier_profiles',{}).get(backend,{}).get(tier)
    profile=bindings.get('profiles',{}).get(profile_id)
    if profile is None:issues.append({'field':'profile_binding','expected':'declared backend/tier profile','actual':profile_id})
    else:
        expected={**profile,'target_tier':tier,'stop_s':card['stop_s'],
                  'maxstep_s':card['unit_s']*profile['step_units'],
                  'spice_maxstep_s':card['unit_s']*profile['step_units']}
        for key,value in expected.items():
            if requested.get(key)!=value:issues.append({'field':key,'expected':value,'actual':requested.get(key)})
        for key in set(requested)-set(expected)-{'candidate_status'}:
            issues.append({'field':key,'expected':'no additional requested control','actual':requested[key]})
        if original.get('profile')!=profile_id:
            issues.append({'field':'RESULT.profile','expected':profile_id,'actual':original.get('profile')})
    digest=sha(requested_path) if requested_path.is_file() else None
    recorded=load(input_path).get('requested_settings_sha256') if input_path.is_file() else None
    if digest is None or digest!=recorded:
        issues.append({'field':'INPUT_IDENTITY.requested_settings_sha256','expected':digest,'actual':recorded})
    return {'status':'matched' if not issues else 'unmatched','issues':issues,'expected':expected,'requested':requested,
            'requested_settings_sha256':digest,'input_identity_sha256':sha(input_path) if input_path.is_file() else None,
            'claim':'requested profile membership only; actual readback and runtime remain independent gates'}


def verify_lane(lane):
    """Require exhaustive hashes and sizes, including every original RESULT."""
    lane = lane.resolve(); manifest = load(lane/'FILE_MANIFEST.json')
    actual = {str(p.relative_to(lane)) for p in lane.rglob('*') if p.is_file() and p != lane/'FILE_MANIFEST.json'}
    if actual != set(manifest): raise ValueError('manifest file inventory differs')
    for name, identity in manifest.items():
        p = (lane/name).resolve()
        if not p.is_relative_to(lane) or not p.is_file() or (lane/name).is_symlink():
            raise ValueError('unsafe manifest path: '+name)
        if p.stat().st_size != identity['bytes'] or sha(p) != identity['sha256']:
            raise ValueError('manifest mismatch: '+name)
    return {'manifest_sha256':sha(lane/'FILE_MANIFEST.json'), 'files':len(manifest), 'status':'verified'}


def snapshot(primary, output):
    """Copy complete import dependencies, rejecting concurrent source changes."""
    areas = ('evas/validation/paper', 'evas/src', 'experiments/backends/paper',
             'experiments/backends/support')
    files = sorted(p for area in areas for p in (primary/area).rglob('*')
                   if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts)
    from actual_observation import worker_dependencies
    files = sorted(set(files) | {primary/name for name in worker_dependencies(primary)})
    before = {str(p.relative_to(primary)):sha(p) for p in files}
    frozen = output/'frozen-repo'; frozen.mkdir()
    for p in files:
        target = frozen/p.relative_to(primary); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p,target)
    if any(sha(primary/name) != digest or sha(frozen/name) != digest for name,digest in before.items()):
        raise ValueError('primary changed while snapshotting')
    script = output/'REANALYZER.py'; shutil.copyfile(Path(__file__),script)
    identity = {'created_utc':datetime.now(timezone.utc).isoformat(),
                'primary':str(primary),'revision':subprocess.check_output(['git','-C',str(primary),'rev-parse','HEAD'],text=True).strip(),
                'source_hashes':before,'reanalyzer_sha256':sha(script), 'claim':'analysis imports only this copied snapshot; DUT/kernel remain original'}
    save(output/'ANALYSIS_IDENTITY.json', identity)
    return frozen, script


def compatible(card, work, old):
    digest = sha(work/'dut.va'); current = hashlib.sha256(card['source'].encode()).hexdigest()
    oldcard = load(work/'condition.json')
    physical = ('id','group_id','family','top','ports','parameters','inputs','outputs','scale_V','unit_s','stop_s')
    issues = []
    if digest != current: issues.append('DUT source differs from current card; requires new execution')
    if hashlib.sha256(oldcard['source'].encode()).hexdigest() != digest: issues.append('original condition/source mismatch')
    if old.get('source_sha256') != digest: issues.append('original RESULT source identity mismatch')
    if any(oldcard.get(k) != card.get(k) for k in physical): issues.append('physical card contract differs')
    return {'status':'compatible' if not issues else 'incompatible','original_source_sha256':digest,
            'current_source_sha256':current,'issues':issues}


def failed_assessment(contract, reason):
    return {'tiers':{q['id']:{'status':'evidence_insufficient','numerical':{'status':'unknown'},
                    'behavior':{'status':'unknown'},'evidence':{'status':'evidence_insufficient','issues':[reason]}}
                    for q in contract['tiers']},'reason':reason}


def slot_status(execution, assessment, config, native, runtime, q, binding=None):
    if binding is not None and binding.get('status')!='matched':return 'evidence_insufficient'
    if binding is not None and binding.get('expected',{}).get('target_tier')!=q:return 'evidence_insufficient'
    if execution != 'waveform_available': return 'evidence_insufficient' if execution == 'not_run' else 'execution_failed'
    status = assessment['tiers'][q]['status']
    if status == 'pass' and any(x.get('status') != 'qualified' for x in (config,native,runtime)):
        return 'evidence_insufficient'
    return status


def exact_dc_inputs(card, rows, backend, config):
    """Diagnostic candidate chain only; never override the core evidence gate."""
    if not card.get('input_exact_evidence_required'): return {'status':'not_required'}
    channels = {}; issues = []
    for name, points in card['inputs'].items():
        values = {float(v).hex() for t,v in points}
        if len(values) != 1:
            issues.append('not a constant represented input: '+name); continue
        expected = next(iter(values)); actual = {float(row[name]).hex() for row in rows}
        channels[name] = {'expected_binary64_hex':expected,'observed_binary64_hex':sorted(actual),
                          'all_rows_equal':actual == {expected}}
        if actual != {expected}: issues.append('observed input is not exactly the declared represented value: '+name)
    if backend != 'evas' or config.get('status') != 'qualified':
        issues.append('strict EVAS raw-response/CSV identity chain not qualified')
    return {'status':'candidate_chain_complete' if not issues else 'unclosed','channels':channels,'issues':issues,
            'qualification_override':False,
            'limit':'exact constant node values plus raw/CSV equality only; actual evidence API/review still required, B/100 is never an exact-identity proof'}


OPEN_AXES=('identity','config','runtime','native','integrator','diagnostics','observations')
OPEN_INPUTS=('dut.va','condition.json','requested_settings.json','requested_times.json','observation_plan.json')
OPEN_BACKENDS={'gnucap_modelgen':('tb.gc','dut.so'),'openvaf_r_ngspice':('tb.cir','dut.osdi')}


def verified_execution_inputs(inputs):
    manifest=load(inputs/'MANIFEST.json')
    if not isinstance(manifest,dict) or not manifest:
        raise ValueError('empty execution input manifest')
    for name,digest in manifest.items():
        path=inputs/name;resolved=path.resolve()
        linked=path.is_symlink()
        for parent in path.parents:
            if parent==inputs:break
            linked=linked or parent.is_symlink()
        if linked or not resolved.is_relative_to(inputs.resolve()) or sha(resolved)!=digest:
            raise ValueError('execution input manifest mismatch: '+name)
    return manifest


def seal_open_evidence(args,output):
    """External qualification has its own identity, outside frozen science."""
    if not args.open_evidence_adapter:
        if any((args.open_proof,args.approved_open_proof_sha256,args.proof_evidence_root,args.execution_inputs,args.approved_open_adapter_sha256)):
            raise ValueError('open evidence options require an external adapter')
        return
    directory=output/'external-open-evidence';directory.mkdir()
    adapter=directory/'adapter.py';shutil.copyfile(args.open_evidence_adapter,adapter)
    config={'adapter':'external-open-evidence/adapter.py',
            'approved_proof_sha256':args.approved_open_proof_sha256,
            'approved_adapter_sha256':args.approved_open_adapter_sha256,
            'proof':None,'evidence_root':'external-open-evidence/attachments'}
    if args.execution_inputs:
        manifest=verified_execution_inputs(args.execution_inputs.resolve())
        save(directory/'EXECUTION_MANIFEST.json',manifest)
        config['execution_input_manifest_sha256']=sha(args.execution_inputs/'MANIFEST.json')
    if args.open_proof:
        proof=load(args.open_proof)
        shutil.copyfile(args.open_proof,directory/'proof.json');config['proof']='external-open-evidence/proof.json'
        attachments=proof.get('attachments',{})
        if not isinstance(attachments,dict):raise ValueError('proof attachments must be a mapping')
        if attachments and not args.proof_evidence_root:raise ValueError('proof attachment root required')
        for name,digest in attachments.items():
            root=args.proof_evidence_root.resolve();source=root/name
            if source.is_symlink() or not source.resolve().is_relative_to(root) or sha(source)!=digest:
                raise ValueError('proof attachment identity mismatch: '+name)
            target=directory/'attachments'/name
            if not target.resolve().is_relative_to((directory/'attachments').resolve()):
                raise ValueError('escaping proof attachment')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    config['sealed_files']={str(p.relative_to(output)):sha(p) for p in directory.rglob('*') if p.is_file()}
    save(output/'OPEN_EVIDENCE_IDENTITY.json',config)
    analysis=load(output/'ANALYSIS_IDENTITY.json')
    analysis['external_open_evidence_identity_sha256']=sha(output/'OPEN_EVIDENCE_IDENTITY.json')
    analysis['external_qualification_claim']='separate adapter/proof identity; scientific snapshot and original grades unchanged'
    save(output/'ANALYSIS_IDENTITY.json',analysis)


def external_open_evidence(output,work,tool,old):
    unknown={axis:{'status':'unknown','issues':['external approved evidence unavailable']} for axis in OPEN_AXES}
    identity_path=output/'OPEN_EVIDENCE_IDENTITY.json'
    if not identity_path.is_file():return unknown
    trusted=load(output/'ANALYSIS_IDENTITY.json').get('external_open_evidence_identity_sha256')
    if sha(identity_path)!=trusted:raise ValueError('external evidence identity drift')
    config=load(identity_path)
    for name,digest in config['sealed_files'].items():
        path=output/name
        if not path.resolve().is_relative_to(output.resolve()) or sha(path)!=digest:
            raise ValueError('sealed external evidence drift: '+name)
    try:
        if sha(output/config['adapter'])!=config.get('approved_adapter_sha256'):
            raise ValueError('external adapter lacks exact approved digest')
        if not config['proof'] or sha(output/config['proof'])!=config.get('approved_proof_sha256'):
            raise ValueError('external proof lacks exact approved digest')
        manifest_path=output/'external-open-evidence/EXECUTION_MANIFEST.json'
        if not manifest_path.is_file():raise ValueError('verified original execution manifest unavailable')
        manifest=load(manifest_path);backend=old['backend'];deck,compiled=OPEN_BACKENDS[backend]
        prefix='runs/'+backend+'/'+old['label']+'/'
        frozen_manifest={name:manifest[prefix+name] for name in (*OPEN_INPUTS,deck)}
        raw_lane=work.parent.parent
        verify_lane(raw_lane)
        raw=load(raw_lane/'FILE_MANIFEST.json');rawprefix='runs/'+old['label']+'/'
        raw_manifest={name:raw[rawprefix+name]['sha256'] for name in
                      ('simulate-final.json','simulate.log','waveform.txt',compiled,'INPUT_IDENTITY.json','RESULT.json')}
        spec=importlib.util.spec_from_file_location('sealed_open_evidence',output/config['adapter'])
        adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
        result=adapter.qualify_open_backend(work,backend,tool,frozen_manifest,raw_manifest,
            proof_path=output/config['proof'] if config['proof'] else None,
            evidence_root=output/config['evidence_root'],approved_proof_sha256=config['approved_proof_sha256'])
        if not isinstance(result,dict) or any(axis not in result for axis in OPEN_AXES):
            raise ValueError('external adapter omitted qualification axes')
        return result
    except (ValueError,KeyError,FileNotFoundError,TypeError) as exc:
        return {axis:{'status':'unknown','issues':[str(exc)]} for axis in OPEN_AXES}


def integrator_axis(backend,open_axes):
    if backend not in OPEN_BACKENDS:
        return {'status':'not_applicable','scope':'external open-backend actual-device proof only; original backend method qualification unchanged'}
    return open_axes['integrator'] if open_axes else {'status':'unknown','scope':'open backend actual device integrator',
                   'issues':['baseline did not independently qualify open-backend actual device integrator']}


def open_gate(legacy,binding,adapter):
    issues=[]
    if legacy.get('status')!='qualified':issues.append('legacy configuration qualification incomplete')
    if binding.get('status')!='matched':issues.append('official profile binding incomplete')
    for axis in ('identity','config','integrator'):
        if adapter.get(axis,{}).get('status')!='qualified':issues.append('external '+axis+' qualification incomplete')
    config={'status':'qualified' if not issues else 'unknown','issues':issues,
            'claim':'legacy configuration AND official binding AND external identity/config/actual integrator'}
    return config,adapter['native'],adapter['runtime']


def worker(frozen, lane, output):
    sys.path[:0] = [str(frozen/'experiments/backends/support'),str(frozen/'experiments/backends/paper'),
                    str(frozen/'evas/validation/paper'),str(frozen/'evas/src')]
    from precision_breadth import load_contract, assess
    from precision_breadth_run import native_observation_evidence, runtime_control_evidence
    from precision_run import effective_settings
    from precision_report import qualification
    from observations import read_native
    if not {'card','contract'} <= set(inspect.signature(native_observation_evidence).parameters):
        raise RuntimeError('frozen runner lacks whole-stop-ULP native provenance API; update primary before a new analysis')
    contract = load_contract()
    if (output/'OFFICIAL_CARDS.json').is_file():
        official = load(output/'OFFICIAL_CARDS.json')
        if sha(output/'OFFICIAL_CARDS.json') != load(output/'OFFICIAL_INPUT_IDENTITY.json')['cards_sha256']:
            raise ValueError('frozen analysis input cards changed')
        if {k:v for k,v in contract.items() if k!='profiles'} != {k:v for k,v in official.items() if k!='profiles'}:
            raise ValueError('generated scientific card contract differs from explicit frozen inputs')
    save(output/'CURRENT_CARDS.json',contract)
    cards = {c['id']:c for c in contract['cards']}; tool = load(lane/'TOOL_IDENTITY.json')
    bindings=load(output/'OFFICIAL_PROFILE_BINDINGS.json') if (output/'OFFICIAL_PROFILE_BINDINGS.json').is_file() else None
    if bindings is not None and sha(output/'OFFICIAL_PROFILE_BINDINGS.json')!=load(output/'OFFICIAL_INPUT_IDENTITY.json')['profile_bindings_sha256']:
        raise ValueError('frozen profile bindings changed')
    save(output/'ORIGINAL_TOOL_IDENTITY.json',tool)
    save(output/'ORIGINAL_STARTED.json',load(lane/'STARTED.json') if (lane/'STARTED.json').is_file() else {})
    records = load(lane/'EXECUTION.json'); results = []; labels = set()
    if len({r['backend'] for r in records}) != 1:
        raise ValueError('single lane must contain exactly one backend')
    for recorded in records:
        label = recorded['label']
        if label in labels: raise ValueError('duplicate original slot; official attempt mapping required')
        labels.add(label); work = raw_work(lane,label)
        oldpath = work/'RESULT.json'; old = load(oldpath) if oldpath.is_file() else recorded
        for key in ('label','backend','condition','tier','status'):
            if old.get(key) != recorded.get(key): raise ValueError('RESULT/EXECUTION mismatch: '+label)
        card = cards.get(old['condition']); q = old['tier']
        identity = {'original_result_sha256':sha(oldpath) if oldpath.is_file() else None,
                    'original_tool_identity_sha256':sha(lane/'TOOL_IDENTITY.json'),
                    'kernel_or_binary_sha256':tool.get('kernel_sha256',tool.get('binary_sha256')),
                    'original_input_identity':load(work/'INPUT_IDENTITY.json') if (work/'INPUT_IDENTITY.json').is_file() else None,
                    'original_artifact_hashes':{str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()} if work.is_dir() else {},
                    'original_assessment_tiers':old.get('assessment',{}).get('tiers'),
                    'original_qualified_tiers':old.get('qualified_tiers')}
        comp = compatible(card,work,old) if card and (work/'dut.va').is_file() else {'status':'incompatible','issues':['missing card or original source']}
        binding=profile_binding(card,work,old,bindings) if bindings is not None and card else {'status':'unknown','issues':['explicit profile bindings unavailable']}
        assessment = failed_assessment(contract, 'source incompatible or no raw waveform')
        config = native = runtime = {'status':'unknown'}; effective = {}; error = None
        exact = {'status':'unavailable','qualification_override':False}
        legacy_axes=None;open_axes=None
        if comp['status'] == 'compatible' and old['status'] == 'waveform_available':
            try:
                waveform = (work/old['waveform']).resolve()
                if not waveform.is_relative_to(work.resolve()) or sha(waveform) != old['waveform_sha256']:
                    raise ValueError('waveform identity mismatch')
                rows = read_native(waveform,old['backend'])
                assessment = assess(card,rows,contract)
                effective = effective_settings(work,old['backend'])
                revised = {**old,'effective_settings':effective}
                config = qualification(work,old['backend'],revised,rows)
                exact = exact_dc_inputs(card,rows,old['backend'],config)
                native = native_observation_evidence(work,old['backend'],config,rows,tool=tool,card=card,contract=contract)
                runtime = runtime_control_evidence(old['backend'],effective)
                if old['backend'] in OPEN_BACKENDS and (output/'OPEN_EVIDENCE_IDENTITY.json').is_file():
                    legacy_axes={'configuration':config,'native_observations':native,'runtime_controls':runtime}
                    open_axes=external_open_evidence(output,work,tool,old)
                    config,native,runtime=open_gate(config,binding,open_axes)
            except Exception as exc:
                error = repr(exc)
                # Retain a completed independent mathematical assessment, but
                # never preserve a partially completed provenance qualification.
                config = native = runtime = {'status':'unknown','reason':error}
        result = {'label':label,'condition':old['condition'],'group_id':old['group_id'],'backend':old['backend'],
                  'executed_target_tier':q,'execution_status':old['status'],'source_compatibility':comp,
                  'inheritance':'same raw execution, new independent analysis' if comp['status']=='compatible' else 'new source requires retest; original result retained',
                  'identity':identity,'assessment':assessment,'settings':effective,'configuration':config,
                  'native_observations':native,'runtime_controls':runtime,'analysis_error':error,
                  'profile_binding':binding,
                  'legacy_qualification':legacy_axes,'external_open_evidence':open_axes,
                  'actual_integrator':integrator_axis(old['backend'],open_axes),
                  'exact_input_diagnostic':exact,
                  'qualified_tiers':{tier['id']:slot_status(old['status'],assessment,config,native,runtime,tier['id'],binding) for tier in contract['tiers']}}
        if binding['status']!='matched':
            result['configuration']={**config,'status':'unknown','original_readback_status':config.get('status'),
                                      'binding_issues':binding['issues']}
        results.append(result)
        save(output/(label+'.json'),result)
    save(output/'REANALYSIS.json',results)
    # A single lane table always keeps every mandatory variant. Each Q uses
    # its prebound target slot; cross-profile best-of selection is forbidden.
    lookup = {(r['condition'],r['executed_target_tier']):r for r in results}
    if len(lookup) != len(results): raise ValueError('multiple attempts for condition/tier require official mapping')
    table = []
    for c in contract['cards']:
        for tier in contract['tiers']:
            q = tier['id']; r = lookup.get((c['id'],q)); a = r['assessment']['tiers'][q] if r else {}
            table.append({'group':c['group_id'],'variant':c['id'],'Q':q,'label':r['label'] if r else '',
                          'execution':r['execution_status'] if r else 'not_in_lane',
                          'numeric':a.get('numerical',{}).get('status','unknown'),
                          'behavior':a.get('behavior',{}).get('status','unknown'),
                          'evidence':a.get('evidence',{}).get('status','evidence_insufficient'),
                          'config':r['configuration']['status'] if r else 'unknown',
                          'native':r['native_observations']['status'] if r else 'unknown',
                          'runtime':r['runtime_controls']['status'] if r else 'unknown',
                          'integrator':r['actual_integrator']['status'] if r else 'unknown',
                          'final':r['qualified_tiers'][q] if r else 'not_in_lane',
                          'compatibility':r['source_compatibility']['status'] if r else 'not_in_lane'})
    with (output/'VARIANTS.tsv').open('w') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(table[0]),delimiter='\t'); writer.writeheader();writer.writerows(table)
    groups = []
    for group in sorted({c['group_id'] for c in contract['cards']}):
        for tier in contract['tiers']:
            cells = [r for r in table if r['group']==group and r['Q']==tier['id']]
            groups.append({'group':group,'Q':tier['id'],'required_variants':len(cells),
                           'status':'pass' if all(r['final']=='pass' for r in cells) else 'incomplete_or_nonpass',
                           'variant_statuses':{r['variant']:r['final'] for r in cells},
                           'claim':'single lane only; no official latest-attempt selection'})
    save(output/'GROUPS.json',groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lane',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--primary',type=Path);parser.add_argument('--frozen',type=Path)
    parser.add_argument('--inputs',type=Path,help='explicit immutable input directory; required for a new analysis')
    parser.add_argument('--open-evidence-adapter',type=Path)
    parser.add_argument('--approved-open-adapter-sha256',help='externally reviewed adapter digest; absence preserves unknown')
    parser.add_argument('--open-proof',type=Path)
    parser.add_argument('--approved-open-proof-sha256')
    parser.add_argument('--proof-evidence-root',type=Path)
    parser.add_argument('--execution-inputs',type=Path,help='original execution freeze; independent verified MANIFEST')
    args = parser.parse_args(); lane = args.lane.resolve(); output = args.output.resolve()
    if args.frozen:
        frozen = args.frozen.resolve()
        if frozen != output/'frozen-repo' or (output/'REANALYSIS.json').exists():
            raise ValueError('internal worker requires unused exclusive snapshot directory')
        identity = load(output/'ANALYSIS_IDENTITY.json')
        if any(sha(frozen/name) != digest for name,digest in identity['source_hashes'].items()):
            raise ValueError('frozen analysis source drift')
        if sha(Path(__file__)) != identity['reanalyzer_sha256']:
            raise ValueError('frozen reanalyzer drift')
        worker(args.frozen.resolve(),lane,output); return
    if not args.primary or not args.inputs: parser.error('--primary and --inputs required')
    if output.is_relative_to(lane) or lane.is_relative_to(output):
        parser.error('--output must be a new directory disjoint from original lane')
    verification = verify_lane(lane)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'ORIGINAL_MANIFEST_VERIFICATION.json',verification)
    frozen, script = snapshot(args.primary.resolve(),output)
    freeze_inputs(args.inputs.resolve(), output, load(output/'ANALYSIS_IDENTITY.json')['source_hashes'])
    seal_open_evidence(args,output)
    result = subprocess.run([sys.executable,'-B',str(script),'--lane',str(lane),'--output',str(output),'--frozen',str(frozen)],
                            capture_output=True,text=True)
    (output/'worker.stdout').write_text(result.stdout);(output/'worker.stderr').write_text(result.stderr)
    final = verify_lane(lane)
    if final != verification: raise ValueError('original lane changed during analysis')
    save(output/'COMPLETION.json',{'returncode':result.returncode,'original_manifest_unchanged':True})
    if result.returncode: raise RuntimeError('analysis worker failed; see worker.stderr')
    save(output/'ANALYSIS_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                        for p in output.rglob('*') if p.is_file()})
    print(json.dumps({'output':str(output),'status':'complete','original_manifest':verification}))


if __name__ == '__main__': main()
