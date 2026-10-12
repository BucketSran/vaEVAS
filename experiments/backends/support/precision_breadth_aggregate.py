"""Aggregate a frozen breadth selection while retaining every mandatory slot.

From the repository root, run::

    python3 -B experiments/backends/support/precision_breadth_aggregate.py \\
        --inputs FROZEN_INPUTS --selection FROZEN_SELECTION.json \\
        --catalog ANALYSIS_CATALOG.json --output NEW_AGGREGATE_DIRECTORY

The catalog is a JSON list of {batch, analysis, raw_lane} objects. Each analysis
must be sealed by ANALYSIS_MANIFEST.json. Raw lanes are independently verified.
The selection can specify slot_selection[backend] with a default_batch and
group_batches mapping. The original October 12 human-readable selection is also
accepted only when its complete policy matches the retained POLICY constant.
Freeze the selection before execution. Duplicate selected attempts are errors.

The current contract has 44 groups, 71 variants, three Q targets and four
backends. All 852 slots remain in OFFICIAL-DRAFT.json, including missing, failed,
incompatible and probe-only slots. Each Q uses its designated execution. The
tool never chooses a better profile. Numerical, behavior and evidence group
results remain separate from full qualification. The raw archive paths are
local references, not claims of public reproducibility.
Group display prioritizes execution failure, then behavior and numerical errors.
Independent layer statuses retain every known error in the same group.
"""
import argparse
import csv
import hashlib
import json
from precision_breadth_reanalysis import verify_lane, sha, load, save, profile_binding, raw_work, verified_bindings
from pathlib import Path

BACKENDS=('evas','spectre','openvaf_r_ngspice','gnucap_modelgen')
POLICY={
 'evas':'all current 71 variants, Q1/Q2/Q3 from batch-v2',
 'spectre':'all current 71 variants, Q1/Q2/Q3 from batch-v2; old source, settings and observation results retained separately',
 'openvaf_r_ngspice':'foundation F11-F20 old batch; F01-F10 and all composition from v2',
 'gnucap_modelgen':'foundation F11-F20 old batch; F01-F10 and all composition from v2'}


def verify_analysis(path):
    path=path.resolve();manifest=load(path/'ANALYSIS_MANIFEST.json')
    inventory={str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p!=path/'ANALYSIS_MANIFEST.json'}
    if inventory!=set(manifest):raise ValueError('analysis inventory drift: '+str(path))
    for name,value in manifest.items():
        p=(path/name).resolve()
        if not p.is_relative_to(path) or (path/name).is_symlink() or not p.is_file():raise ValueError('unsafe analysis artifact')
        if sha(p)!=value['sha256'] or p.stat().st_size!=value['bytes']:raise ValueError('analysis hash/size drift: '+name)
    if load(path/'COMPLETION.json')!={'returncode':0,'original_manifest_unchanged':True}:
        raise ValueError('incomplete analysis')
    return sha(path/'ANALYSIS_MANIFEST.json')


PROOF_METADATA_FIELDS=('schema','backend','image_id','binary_hashes','environment_sha256','argv_sha256','claims','run_scopes','attachments','reviews')


def external_evidence_identity(path):
    """Publish sealed external provenance without granting any qualification."""
    verify_analysis(path)
    manifest=load(path/'ANALYSIS_MANIFEST.json');analysis=load(path/'ANALYSIS_IDENTITY.json')
    name='OPEN_EVIDENCE_IDENTITY.json';expected=analysis.get('external_open_evidence_identity_sha256')
    if name not in manifest:
        if expected is not None:raise ValueError('external identity missing from sealed analysis')
        return None
    if sha(path/name)!=expected:raise ValueError('external identity is not bound to analysis identity')
    config=load(path/name);sealed=config['sealed_files']
    for filename,digest in sealed.items():
        target=path/filename
        if filename not in manifest or manifest[filename]['sha256']!=digest or sha(target)!=digest:
            raise ValueError('external artifact not covered by sealed manifest: '+filename)
        if target.is_symlink() or not target.resolve().is_relative_to(path.resolve()):
            raise ValueError('unsafe external artifact path')
    adapter=config['adapter'];proof=config.get('proof')
    if adapter not in sealed or (proof and proof not in sealed):raise ValueError('adapter/proof absent from sealed files')
    metadata=None
    if proof:
        original=load(path/proof)
        metadata={key:original[key] for key in PROOF_METADATA_FIELDS if key in original}
        for attachment,digest in original.get('attachments',{}).items():
            filename=str(Path(config['evidence_root'])/attachment)
            if sealed.get(filename)!=digest:raise ValueError('proof attachment absent from sealed identity')
    return {'identity_path':name,'identity_sha256':sha(path/name),
            'adapter_sha256':sealed[adapter],'approved_adapter_sha256':config.get('approved_adapter_sha256'),
            'proof_sha256':sealed[proof] if proof else None,'approved_proof_sha256':config.get('approved_proof_sha256'),
            'execution_input_manifest_sha256':config.get('execution_input_manifest_sha256'),
            'sealed_files':sealed,'proof_metadata':metadata,
            'scope':'external qualification only; frozen mathematical assessment and original execution unchanged'}


def readback_provenance(record):
    legacy=record.get('legacy_qualification')
    config=legacy['configuration'] if legacy else record.get('configuration',{})
    requested=record.get('profile_binding',{}).get('requested',config.get('requested',{}))
    return {'legacy_configuration':config,'actual_settings':config.get('actual',{}),
            'requested_settings':requested,
            'settings_provenance':{'actual':'legacy_qualification.configuration.actual' if legacy else 'configuration.actual',
                                  'requested':'profile_binding.requested' if 'requested' in record.get('profile_binding',{}) else 'legacy configuration requested',
                                  'scope':'method setting/readback is distinct from actual device integrator path'}}


def external_axes(record,backend):
    external=record.get('external_open_evidence')
    default={'status':'unknown' if backend in BACKENDS[2:] else 'not_applicable',
             'scope':'open-backend actual device integrator evidence'}
    integrator=record.get('actual_integrator',default)
    if external:
        if backend not in BACKENDS[2:]:raise ValueError('open external evidence attached to non-open backend')
        if integrator!=external.get('integrator'):raise ValueError('external integrator receipt mismatch')
        if record['configuration']['status']=='qualified' and any(external.get(axis,{}).get('status')!='qualified' for axis in ('identity','config','integrator')):
            raise ValueError('complete external configuration lacks identity/config/actual integrator qualification')
    return {'integrator':integrator['status'],'integrator_evidence':integrator,'external_qualification':external}


def verified_cards_digest(inputs,manifest):
    path=inputs/'cards.json'
    if 'cards.json' not in manifest or path.is_symlink() or sha(path)!=manifest['cards.json']:
        raise ValueError('official cards absent from verified input manifest or hash drift')
    return sha(path)


def source_batch(backend,card,selection):
    if 'slot_selection' in selection:
        rule=selection['slot_selection'][backend]
        return rule.get('group_batches',{}).get(card['group_id'],rule['default_batch'])
    if selection['official_selection']!=POLICY:raise ValueError('selection policy changed; explicit new adjudication required')
    old=(backend in BACKENDS[2:] and card['family']=='foundation' and 11<=int(card['group_id'][1:])<=20)
    return selection['old_batch'] if old else selection['new_batch']


def group_status(cells):
    states=[c['final'] for c in cells]
    if all(s=='pass' for s in states):return 'pass'
    for failure in ('execution_failed','behavior_error','numerical_error'):
        if failure in states:return failure
    return 'evidence_insufficient'


def layer_status(cells,key,passed,failure=None):
    states=[c[key] for c in cells]
    if failure and failure in states:return failure
    if all(state==passed for state in states):return passed
    return 'evidence_insufficient' if key=='evidence' else 'unknown'


def compatible_contract(snapshot,official):
    """New execution profiles cannot alter the scientific contract or old profiles."""
    if {k:v for k,v in snapshot.items() if k!='profiles'}!={k:v for k,v in official.items() if k!='profiles'}:
        raise ValueError('analysis scientific contract differs from official freeze')
    current={p['id']:p for p in official.get('profiles',[])}
    if any(current.get(p['id'])!=p for p in snapshot.get('profiles',[])):
        raise ValueError('analysis execution profile changed')
    return {'added_official_profiles':sorted(set(current)-{p['id'] for p in snapshot.get('profiles',[])}),
            'claim':'old settings remain original; added profiles do not certify old execution'}


def assemble(contract,selection,analyses):
    """No ranking by waveform outcome, profile, or analysis status is permitted."""
    index={};ignored=[]
    cards={c['id']:c for c in contract['cards']}
    for batch,analysis,records in analyses:
        for r in records:
            key=(r['backend'],r['condition'],r['executed_target_tier'])
            if r['condition'] not in cards or source_batch(r['backend'],cards[r['condition']],selection)!=batch:
                ignored.append({'analysis':analysis,'label':r['label'],'backend':r['backend'],'batch':batch,
                                'reason':'outside fixed official selection'});continue
            if key in index:raise ValueError('duplicate selected attempt requires root mapping: '+str(key))
            index[key]=(r,analysis,batch)
    rows=[]
    for backend in BACKENDS:
        for c in contract['cards']:
            for tier in contract['tiers']:
                q=tier['id'];batch=source_batch(backend,c,selection);picked=index.get((backend,c['id'],q))
                base={'backend':backend,'group':c['group_id'],'variant':c['id'],'Q':q,'selected_batch':batch,
                      'unit_s':c.get('unit_s'),'model_top':c.get('top'),
                      'probe_only':bool(c.get('probe_only') or c.get('support_probe_only')),
                      'source_sha256':hashlib.sha256(c['source'].encode()).hexdigest(),
                      'original_execution':'not_collected','numeric':'unknown','behavior':'unknown',
                      'evidence':'evidence_insufficient','config':'unknown','native':'unknown','runtime':'unknown',
                      'integrator':'unknown' if backend in BACKENDS[2:] else 'not_applicable',
                      'integrator_evidence':None,'external_qualification':None,'legacy_configuration':None,'settings_provenance':None,
                      'source_compatibility':'unknown','final':'evidence_insufficient',
                      'analysis':None,'label':None,'inheritance':'selected execution not yet collected'}
                if picked:
                    r,path,batch=picked;a=r['assessment']['tiers'][q]
                    base.update(original_execution=r['execution_status'],analysis=path,label=r['label'],
                                inheritance=r['inheritance'],original_result_sha256=r['identity']['original_result_sha256'],
                                kernel_or_binary_sha256=r['identity']['kernel_or_binary_sha256'],
                                source_compatibility=r['source_compatibility']['status'])
                    base.update(original_input_identity=r['identity'].get('original_input_identity'),
                                raw_artifact_hashes={k:v for k,v in r['identity'].get('original_artifact_hashes',{}).items()
                                      if k in ('waveform.txt','waveform.csv','waveform.raw','RESULT.json','dut.va','dut.so','INPUT_IDENTITY.json','requested_settings.json','observation_plan.json')},

                                tool_identity_sha256=r['identity'].get('original_tool_identity_sha256'))
                    base.update(readback_provenance(r));base.update(external_axes(r,backend))
                    if r['source_compatibility']['status']=='compatible':
                        if r['source_compatibility']['current_source_sha256']!=base['source_sha256']:
                            raise ValueError('analysis uses a different current DUT source')
                        base.update(numeric=a.get('numerical',{}).get('status','unknown'),
                                    behavior=a.get('behavior',{}).get('status','unknown'),
                                    evidence=a.get('evidence',{}).get('status','evidence_insufficient'),
                                    config=r['configuration']['status'],native=r['native_observations']['status'],
                                    runtime=r['runtime_controls']['status'],final=r['qualified_tiers'][q])
                        base.update(error_lower_V=a.get('numerical',{}).get('error_lower_V'),
                                    error_upper_V=a.get('numerical',{}).get('error_upper_V'),
                                    voltage_budget_V=a.get('voltage_budget_V'),
                                    output_witnesses={name:{key:value for key,value in info.items() if key in
                                         ('worst','error_lower_V','error_upper_V','reference_uncertainty_V','input_uncertainty_V','unresolved_uncertainty_V','unqualified_observations')}
                                         for name,info in r['assessment'].get('outputs',{}).items()},
                                    evidence_issues=a.get('evidence',{}).get('issues',[]),
                                    behavior_errors=a.get('behavior',{}).get('errors',[]))
                        if base['probe_only'] and base['final']=='pass':
                            raise ValueError('probe-only condition cannot count as pass')
                        if 'profile_binding' in r:
                            base['profile_binding']=r['profile_binding']
                            if r['profile_binding']['status']!='matched':
                                base['config']='unknown';base['final']='evidence_insufficient'
                    else:
                        base['inheritance']='incompatible selected source: current scientific status unknown; original execution retained'
                rows.append(base)
    groups=[]
    for backend in BACKENDS:
        for group in sorted({c['group_id'] for c in contract['cards']}):
            for tier in contract['tiers']:
                cells=[r for r in rows if r['backend']==backend and r['group']==group and r['Q']==tier['id']]
                groups.append({'backend':backend,'group':group,'Q':tier['id'],'mandatory_variants':len(cells),
                               'numeric':layer_status(cells,'numeric','pass','numerical_error'),
                               'behavior':layer_status(cells,'behavior','pass','behavior_error'),
                               'evidence':layer_status(cells,'evidence','complete'),
                               'config':layer_status(cells,'config','qualified'),
                               'native':layer_status(cells,'native','qualified'),
                               'runtime':layer_status(cells,'runtime','qualified'),
                               'integrator':'not_applicable' if backend not in BACKENDS[2:] else ('qualified' if all(r['integrator']=='qualified' for r in cells) else 'unknown'),
                               'status':group_status(cells),'variants':{r['variant']:r['final'] for r in cells},
                               'execution_relations':{r['variant']:{'batch':r['selected_batch'],'original_execution':r['original_execution'],
                                                      'inheritance':r['inheritance'],'analysis':r['analysis']} for r in cells}})
    return {'slots':rows,'groups':groups,'excluded_original_attempts':ignored}


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--selection',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=a.output.resolve()
    tool_paths=(Path(__file__).resolve(),Path(profile_binding.__code__.co_filename).resolve())
    tool_hashes={path.name:sha(path) for path in tool_paths}
    if output.is_relative_to(a.inputs.resolve()) or a.inputs.resolve().is_relative_to(output):
        p.error('--output must be a new directory disjoint from frozen inputs')
    contract=load(a.inputs/'cards.json');selection=load(a.selection);expected=load(a.inputs/'SOURCE_IDENTITY.json')
    manifest=load(a.inputs/'MANIFEST.json')
    for name,digest in manifest.items():
        path=(a.inputs/name).resolve()
        if not path.is_relative_to(a.inputs.resolve()) or sha(path)!=digest:raise ValueError('frozen official input drift')
    official_cards_sha256=verified_cards_digest(a.inputs,manifest)
    bindings=verified_bindings(a.inputs,manifest)
    if len(contract['cards'])!=71 or len({c['group_id'] for c in contract['cards']})!=44 or len(contract['tiers'])!=3:
        raise ValueError('official inventory differs from 44 groups/71 variants/3 Q')
    if selection['denominator']!={'groups':44,'variants':71,'targets_per_backend':213,'total_official_slots':852}:
        raise ValueError('official denominator changed')
    entries=[];identities=[]
    allowed_batches={source_batch(backend,card,selection) for backend in BACKENDS for card in contract['cards']}
    for entry in load(a.catalog):
        if entry['batch'] not in allowed_batches:raise ValueError('catalog names an unselected batch')
        path=Path(entry['analysis']).resolve();digest=verify_analysis(path)
        raw_lane=Path(entry['raw_lane']).resolve()
        if any(output.is_relative_to(area) or area.is_relative_to(output) for area in (path,raw_lane)):
            p.error('--output must be disjoint from raw lanes and sealed analyses')
        raw_verification=verify_lane(raw_lane)
        if raw_verification!=load(path/'ORIGINAL_MANIFEST_VERIFICATION.json'):
            raise ValueError('original raw lane differs from sealed analysis')
        identity=load(path/'ANALYSIS_IDENTITY.json');available=identity['source_hashes']
        required=[name for name in expected if name.endswith('.py')]
        required+=['evas/validation/paper/precision-v2.json']
        if any(available.get(name)!=expected.get(name) for name in required):
            raise ValueError('analysis checker/reader provenance differs from official frozen identity: '+str(path))
        contract_relation=compatible_contract(load(path/'CURRENT_CARDS.json'),contract)
        external_identity=external_evidence_identity(path)
        records=load(path/'REANALYSIS.json');cards={card['id']:card for card in contract['cards']}
        for record in records:
            if record['condition'] not in cards:continue
            work=raw_work(raw_lane,record['label'])
            original=load(work/'RESULT.json')
            record['profile_binding']=profile_binding(cards[record['condition']],work,original,bindings)
            record['profile_binding']['official_bindings_sha256']=sha(a.inputs/'PROFILE_BINDINGS.json')
        entries.append((entry['batch'],str(path),records))
        identities.append({'analysis':str(path),'batch':entry['batch'],'analysis_manifest_sha256':digest,
                           'identity_sha256':sha(path/'ANALYSIS_IDENTITY.json'),'checker_revision':identity['revision'],
                           'contract_relation':contract_relation,'raw_lane':str(raw_lane),
                           'raw_manifest':raw_verification,'tool_identity_sha256':sha(path/'ORIGINAL_TOOL_IDENTITY.json'),
                           'external_evidence':external_identity})
    result=assemble(contract,selection,entries)
    if len(result['slots'])!=852:raise ValueError('official slot denominator lost')
    if any(sha(path)!=tool_hashes[path.name] for path in tool_paths):raise ValueError('aggregation tool changed during analysis')
    output.mkdir(parents=True,exist_ok=False)
    (output/'CATALOG.json').write_bytes(a.catalog.read_bytes())
    (output/'SELECTION.json').write_bytes(a.selection.read_bytes())
    (output/'SOURCE_IDENTITY.json').write_bytes((a.inputs/'SOURCE_IDENTITY.json').read_bytes())
    save(output/'OFFICIAL-DRAFT.json',{'claim':'fixed pre-execution selection; incomplete collection remains evidence insufficient',
           'selection_sha256':sha(a.selection),'official_input_manifest_sha256':sha(a.inputs/'MANIFEST.json'),
           'aggregate_source_sha256':sha(Path(__file__)),'catalog_sha256':sha(a.catalog),
           'tool_source_hashes':tool_hashes,'official_cards_sha256':official_cards_sha256,
           'analyses':identities,**result})
    with (output/'SLOTS.tsv').open('w') as f:
        names=sorted({key for row in result['slots'] for key in row});w=csv.DictWriter(f,names,delimiter='\t');w.writeheader();w.writerows(result['slots'])
    lines=['# 四后端固定映射草稿','', '保留 852 个官方槽，按冻结 SELECTION 选择；尚未收集的槽为证据不足，未选择最好结果。', '',
           '| 后端 | 已收集 | pass | 数值错 | 行为错 | 原执行失败 | I/未收集 |','|---|---:|---:|---:|---:|---:|---:|']
    for backend in BACKENDS:
        cells=[r for r in result['slots'] if r['backend']==backend];n=lambda s:sum(r['final']==s for r in cells)
        lines.append(f'| {backend} | {sum(r["analysis"] is not None for r in cells)}/213 | {n("pass")} | {n("numerical_error")} | {n("behavior_error")} | {n("execution_failed")} | {n("evidence_insufficient")} |')
    lines+=['','数值、行为、证据、设置、native 和 runtime 的独立结果见 SLOTS.tsv；组必须包含全部 mandatory variants 才能 pass。',
            '同源码原波形的重分析继承原执行，不是修复后 kernel 复测；源码不兼容仍记录原执行，但当前科学结论未知。',
            '完整 checker 身份、原 RESULT/kernel hash 和每组继承／复测关系见 OFFICIAL-DRAFT.json。']
    lines+=['','独立槽位统计（通过数值不等于完整通过）：','',
            '| 后端 | 数值 pass | 行为 pass | 证据 complete | 设置 qualified | native qualified | runtime qualified | 完整 pass |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for backend in BACKENDS:
        cells=[r for r in result['slots'] if r['backend']==backend]
        counts=[sum(r[key]==state for r in cells) for key,state in [('numeric','pass'),('behavior','pass'),('evidence','complete'),('config','qualified'),('native','qualified'),('runtime','qualified'),('final','pass')]]
        lines.append('| '+backend+' | '+' | '.join(map(str,counts))+' |')
    lines+=['','44 组完整资格：每格按 Q1 / Q2 / Q3 列出指定配置的实际结果，未跨配置推断；P=pass，N=数值错，B=行为错，X=执行失败，I=证据不足／未收集。','',
            '| 组 | EVAS | Spectre | OpenVAF/ngspice | Gnucap |','|---|---|---|---|---|']
    symbols={'pass':'P','numerical_error':'N','behavior_error':'B','execution_failed':'X','evidence_insufficient':'I'}
    for group in sorted({c['group_id'] for c in contract['cards']}):
        cells=[]
        for backend in BACKENDS:
            cells.append(' / '.join(symbols[next(g['status'] for g in result['groups'] if g['backend']==backend and g['group']==group and g['Q']==tier['id'])] for tier in contract['tiers']))
        lines.append('| '+group+' | '+' | '.join(cells)+' |')
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    save(output/'MANIFEST.json',{str(f.relative_to(output)):{'sha256':sha(f),'bytes':f.stat().st_size} for f in output.rglob('*') if f.is_file()})
    print(json.dumps({'output':str(output),'slots':852,'groups':len(result['groups']),'selected_analyses':len(entries)}))


if __name__=='__main__':main()
