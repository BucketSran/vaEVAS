"""Audit fixed calibration inputs against sealed actual Spectre archives.

Read-only: imports the existing seal and batch-summary implementations, never
executes an archived checker, simulator, model API, or remote lifecycle. Absolute
local paths are supplied by the operator; retained output uses logical run IDs.
"""
import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_text())


def stats(records):
    return dict(conditions=len(records), statuses=dict(Counter(r['classification'] for r in records)))


def role(variant):
    return 'reference' if variant == 'reference' else 'equivalent' if variant == 'equivalent' else 'semantic_negative'


def audit(root, run_root, legacy_audit):
    base = root / 'experiments/benchmark_first_batch'
    seal = load(base / 'verification_measurement/regrade_measurement.py', 'calibration_archive_seal')
    batch = load(base / 'batch.py', 'calibration_batch_summary')
    measurement_path = base / 'verification_measurement/measurement_regrade_round2_receipt.json'
    measurement = read_json(measurement_path)
    def reachable_revision(revision):
        full = subprocess.check_output(['git','rev-parse','--verify',revision+'^{commit}'],cwd=root,text=True).strip()
        seal.require(subprocess.run(['git','merge-base','--is-ancestor',full,'HEAD'],cwd=root).returncode==0,
                     'fixed Git dependency is not reachable from canonical root HEAD: '+full)
        return full
    # Use the integrated root revisions: an available worker object is not a
    # publication dependency until it is reachable from the deliverable history.
    measurement_revision = reachable_revision('c11367b41b59d7b3412a043ddcfbc91918d5710b')
    adc_execution_revision = reachable_revision('c826fd17f259d625c4f79408a1f7295e02b03fae')
    published_measurement = subprocess.check_output(['git','show',measurement_revision+':'+str(measurement_path.relative_to(root))],cwd=root)
    seal.require(published_measurement == measurement_path.read_bytes(), 'measurement compact receipt differs from fixed revision')
    seal.require(measurement['tool_sha256'] == digest((base/'verification_measurement/regrade_measurement.py').read_bytes()), 'measurement strict regrade tool differs')
    measurement_checker = root / 'benchmark/checkers/first_batch_measurement.py'
    seal.require(digest(measurement_checker.read_bytes()) == measurement['canonical_identity']['first_batch_measurement.py'], 'measurement regrade checker differs from current')
    measurement_records = {r['job_id']: r for r in measurement['records']}
    matrix = read_json(run_root / 'round2-active-matrix.json')
    followup = read_json(run_root / 'followup-function-plan-v3.json')
    entries = [dict(x, round='round2') for x in matrix]
    excluded = []
    for directory in followup:
        directory = Path(directory)
        if directory.parent.name.startswith('optimize-'):
            excluded.append(str(directory.relative_to(run_root))); continue
        entries.append(dict(task_id=directory.parent.name, variant=directory.name,
                            role=role(directory.name), prepared=str(directory), round='followup-v3'))
    for item in read_json(run_root / 'legacy-va07-current-v1/matrix.json'):
        entries.append(dict(item, task_id='va07-triangle-repair', role=role(item['variant']), round='va07-current-v1'))
    latest = {(x['task_id'], x['variant']): i for i, x in enumerate(entries)}
    records, variants = [], []
    derived_reference = {}
    instruction_deltas = {}
    def instruction_delta(task, frozen_hash):
        key = (task.name, frozen_hash)
        if key in instruction_deltas:
            return instruction_deltas[key]
        relative = str((task/'instruction.md').relative_to(root))
        revisions = subprocess.check_output(['git','log','--format=%H','--',relative],cwd=root,text=True).splitlines()
        current = (task/'instruction.md').read_text()
        def strip_policy(text):
            return re.sub(r'<!-- generated submission policy -->.*?<!-- end generated submission policy -->', '', text, flags=re.S).strip()
        interpretation = 'public_instruction_identity_changed_not_run'
        for revision in revisions:
            old = subprocess.check_output(['git','show',revision+':'+relative],cwd=root)
            if digest(old) == frozen_hash:
                if strip_policy(old.decode()) == strip_policy(current):
                    interpretation = 'verified_public_submission_policy_text_only'
                break
        instruction_deltas[key] = interpretation
        return interpretation
    def reference_source(task, name):
        fit_path = task/'solution/fit.py'
        if fit_path.is_file() and name == 'dut.va':
            if task.name not in derived_reference:
                fitter = load(fit_path, 'calibration_fit_'+task.name.replace('-','_'))
                source = fitter.model(fitter.fit(task/'environment/public'),'reference').encode()
                derived_reference[task.name] = dict(source=source, fit_sha256=digest(fit_path.read_bytes()),
                    public_observations={str(p.relative_to(task)):digest(p.read_bytes()) for p in (task/'environment/public').rglob('*') if p.is_file()})
            return derived_reference[task.name]['source']
        path=task/'solution'/name
        return path.read_bytes() if path.is_file() else None
    for index, entry in enumerate(entries):
        directory = Path(entry['prepared'])
        # Reuse summary's report/plan identity checks, but do not trust its saved JSON.
        summary = batch.summarize(directory)
        preparation = read_json(directory / 'preparation.json')
        seal.require(digest(json.dumps(preparation['source_identity'],sort_keys=True).encode())==preparation['criteria_sha256'], 'prepared full criteria hash computation')
        wrappers = read_json(directory / 'results.json')
        selected = latest[(entry['task_id'], entry['variant'])] == index
        group = []
        for wrapper in wrappers:
            archive_path = directory / 'remote' / wrapper['job_id'] / 'archive/job.tar.gz'
            archive = seal.SealedArchive(archive_path, read_json(archive_path.with_name('receipt.json')))
            try:
                result, package, candidate = seal.verify_seal(archive, wrapper)
                seal.require(result['candidate_sha256'] == preparation['candidate']['candidate_sha256'], 'prepared candidate differs')
                seal.require(result['criteria_sha256'] == preparation['criteria_sha256'], 'prepared criteria differs')
                report = archive.json('run/work/verifier/report.json')
                seal.require(len(report['cases']) == 1, 'expected one condition per job')
                old = report['cases'][0]
                seal.require(old['name'] == wrapper['condition_id'], 'case name mismatch')
                task = root / 'benchmark/tasks' / entry['task_id']
                frozen_bytes = archive.read('run/work/tests/cases.json')
                frozen = json.loads(frozen_bytes)[0]
                seal.require(digest(frozen_bytes) == report['cases_sha256'], 'report cases binding')
                current_case = next(c for c in read_json(task / 'tests/cases.json') if c['name'] == frozen['name'])
                case_equal = current_case == frozen
                differences, graders = [], {}
                for filename, old_hash in preparation['source_identity'].items():
                    if filename not in ('instruction.md','cases.json'):
                        seal.require(digest(archive.read('run/work/tests/'+filename))==old_hash, 'archived template differs from prepared source identity: '+filename)
                    if filename == 'instruction.md':
                        current_path = task / filename
                    else:
                        current_path = task / 'tests' / filename
                    if not current_path.is_file():
                        differences.append(dict(file=filename, frozen_sha256=old_hash, current_sha256=None, interpretation='missing_current_file')); continue
                    current_hash = digest(current_path.read_bytes())
                    if current_hash != old_hash:
                        interpretation = (instruction_delta(task,old_hash) if filename == 'instruction.md' else
                                          'protocol_runtime_identity_changed_not_rerun' if filename in ('circuit_task.py','test.sh') else
                                          'full_case_file_identity_change' if filename == 'cases.json' else 'numerical_or_submission_identity_changed')
                        if filename == 'circuit_task.py':
                            old_tree=ast.parse(archive.read('run/work/tests/circuit_task.py'))
                            new_tree=ast.parse(current_path.read_bytes())
                            for node in new_tree.body:
                                if isinstance(node,ast.FunctionDef) and node.name=='verify':
                                    node.body=[item for item in node.body if not (isinstance(item,ast.For) and isinstance(item.iter,ast.Name) and item.iter.id=='cases' and
                                        len(item.body)==1 and isinstance(item.body[0],ast.If) and ast.unparse(item.body[0].test)=="'signals' not in case")]
                            for tree in (old_tree,new_tree):
                                for node in ast.walk(tree):
                                    if isinstance(node,(ast.Module,ast.FunctionDef,ast.ClassDef)) and node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
                                        node.body=node.body[1:]
                            if ast.dump(old_tree)==ast.dump(new_tree):
                                interpretation='verified_default_signals_metadata_patch_only_not_rerun'
                        if filename == 'test.sh':
                            interpretation='frozen_explicit_python312_entrypoint_vs_current_task_template'
                        differences.append(dict(file=filename, frozen_sha256=old_hash,current_sha256=current_hash,interpretation=interpretation))
                    if filename.startswith('first_batch_') or filename == 'triangle_oscillator.py':
                        graders[filename] = dict(frozen_sha256=old_hash,current_sha256=current_hash)
                numerical_equal = all(v['frozen_sha256'] == v['current_sha256'] for v in graders.values())
                source_files = {}
                for name, identity in candidate['files'].items():
                    source = archive.read('candidate/files/' + name)
                    seal.require(digest(source) == identity['sha256'], 'candidate source binding')
                    reference = task / 'solution' / name
                    source_files[name] = dict(sha256=identity['sha256'], current_reference_matches=reference_source(task,name) == source)
                    execution_binding=old.get('candidate_files',{}).get(name)
                    if execution_binding:
                        original=archive.read('run/work/candidate/'+name)
                        executed=archive.read('run/work/verifier/'+old['name']+'/'+name)
                        seal.require(original==source and digest(original)==execution_binding['original_sha256'], 'actual original source binding')
                        seal.require(digest(executed)==execution_binding['executed_sha256'], 'actual executed source binding')
                        translation=execution_binding['output_translation']
                        seal.require(translation['inverse_verified'], 'candidate output translation inverse')
                        restored=executed
                        for edit in reversed(translation['edits']):
                            new=edit['executed_literal'].encode();previous=edit['original_literal'].encode()
                            seal.require(restored.count(new)==1, 'ambiguous output literal inverse')
                            restored=restored.replace(new,previous,1)
                        seal.require(restored==source,'actual executed source differs beyond allowed output paths')
                        source_files[name]['executed_sha256']=digest(executed)
                        source_files[name]['inverse_translation_verified']=True
                reference_matches = entry['role'] != 'reference' or all(x['current_reference_matches'] for x in source_files.values())
                status = old['status']
                classification = ('graded_pass' if old.get('passed') else 'graded_rejection') if status == 'graded' else status
                if status == 'graded':
                    seal.require(report['reward']==result['score']==int(old['passed']), 'graded verdict/report/result inconsistency')
                    seal.require(old['returncode']==0 and old.get('waveform_sha256'), 'graded result lacks complete actual waveform')
                if old.get('netlist_sha256'):
                    actual_netlist=archive.read('run/work/verifier/'+old['name']+'/tb.scs')
                    seal.require(digest(actual_netlist)==old['netlist_sha256']==digest(frozen['netlist'].encode()), 'executed netlist differs from frozen numerical stimulus')
                    for name,text in frozen.get('support',{}).items():
                        seal.require(archive.read('run/work/verifier/'+old['name']+'/'+name)==text.encode(), 'executed support stimulus differs')
                waveform = old.get('waveform_sha256')
                if waveform:
                    raw = archive.read('run/work/verifier/' + old['name'] + '/psf/tran.tran.tran')
                    seal.require(digest(raw) == waveform and raw.rstrip().endswith(b'END'), 'waveform hash/completeness')
                regraded = measurement_records.get(wrapper['job_id'])
                regrade_binding = None
                if regraded:
                    for key, value in [('archive_sha256',archive.receipt['package']['sha256']),('report_sha256',digest(archive.read('run/work/verifier/report.json'))),('waveform_sha256',waveform),('candidate_bundle_sha256',candidate['candidate_sha256'])]:
                        seal.require(regraded[key] == value, 'strict measurement regrade binding: '+key)
                    seal.require(regraded['original_score'] == result['score'] == regraded['regraded_score'], 'measurement regrade verdict')
                    numerical_equal = True
                    regrade_binding = dict(receipt_fixed_git_revision=measurement_revision,receipt_sha256=digest(measurement_path.read_bytes()), checker_sha256=measurement['canonical_identity']['first_batch_measurement.py'], simulation_executed=False)
                current_numeric_valid = case_equal and numerical_equal and reference_matches and status == 'graded'
                record = dict(task_id=entry['task_id'],variant=entry['variant'],role=entry['role'],round=entry['round'],selected=selected,
                    condition_id=wrapper['condition_id'],job_id=wrapper['job_id'],classification=classification,
                    execution=result['execution'],score=result.get('score'),failure_details=dict(count=len(old.get('failures',[])),sha256=digest(seal.canonical(old.get('failures',[]))),examples=old.get('failures',[])[:3]),failure_kind=old.get('failure_kind'),
                    current_numerical_contract_covered=current_numeric_valid,current_case_values_match=case_equal,
                    archive_sha256=archive.receipt['package']['sha256'],report_sha256=digest(archive.read('run/work/verifier/report.json')),
                    waveform_sha256=waveform,waveform_rows=old.get('waveform_rows'),netlist_sha256=old.get('netlist_sha256'),
                    frozen_case_file_sha256=digest(frozen_bytes),case_value_sha256=digest(seal.canonical(frozen)),
                    contract_sha256=report.get('contract_sha256'),runtime_sha256=report.get('runtime_sha256'),parser_sha256=report.get('parser_sha256'),
                    candidate_bundle_sha256=candidate['candidate_sha256'],candidate_files=source_files,criteria_sha256=result['criteria_sha256'],
                    task_package_sha256=result['task_package_sha256'],numerical_graders=graders,identity_differences=differences,
                    strict_measurement_regrade=regrade_binding,spectre_version=report.get('spectre_version'),
                    archive_locator=str(archive_path.relative_to(run_root)),all_archive_members_verified=len(archive.members))
                records.append(record);group.append(record)
            finally:
                archive.close()
        variants.append(dict(task_id=entry['task_id'],variant=entry['variant'],role=entry['role'],round=entry['round'],selected=selected,
            planned_conditions=len(preparation['cases']),actual_conditions=len(group),all_current_numerical_conditions_covered=all(r['current_numerical_contract_covered'] for r in group),
            all_passed=all(r['classification']=='graded_pass' for r in group),has_semantic_rejection=any(r['classification']=='graded_rejection' for r in group)))
        print(json.dumps(dict(audited=entry['task_id']+'/'+entry['variant'],round=entry['round'],conditions=len(group))),flush=True)
    # VA08 retains its existing standalone numeric execution boundary. Reverify
    # sealed bytes and the previously audited current/frozen mathematical inputs.
    legacy = read_json(legacy_audit)
    adc_task = root / 'benchmark/tasks/va08-adc-linearity'
    adc_compact_path = root / 'experiments/adc_linearity/calibration-20261007.json'
    adc_compact = read_json(adc_compact_path)
    adc_expected = {r['job_id']:r for r in adc_compact['corrected_original_calibration']['jobs']+[adc_compact['isolated_early_read']]}
    adc_checker = load(root/'benchmark/checkers/adc_linearity.py','calibration_adc_oracle')
    adc_cases = {c['name']:c for c in read_json(adc_task/'tests/cases.json')}
    adc_criteria = digest((adc_task/'instruction.md').read_bytes()+(adc_task/'tests/verify.py').read_bytes()+(adc_task/'tests/cases.json').read_bytes())
    for audited in legacy['va08']['jobs']:
        path = Path(audited['archive']);archive=seal.SealedArchive(path,read_json(path.with_name('receipt.json')))
        try:
            result=archive.json('run/result.json');wrapper=dict(job_id=audited['job_id'],condition_id=audited['condition'],result=result)
            result,package,candidate=seal.verify_seal(archive,wrapper)
            expected=adc_expected[audited['job_id']]
            report=archive.json('run/work/verifier/report.json');old=report['cases'][0];name=old['name']
            frozen_bytes=archive.read('run/work/tests/cases.json');case=json.loads(frozen_bytes)[0]
            source=archive.read('candidate/files/dut.va');raw=archive.read('run/work/verifier/'+name+'/psf/tran.tran.tran')
            seal.require(archive.receipt['package']['sha256']==audited['archive_sha256']==(expected.get('archive_sha256') or expected['archive']['package']['sha256']), 'VA08 archive identity')
            seal.require(source and digest(source)==report['candidate_sha256']==candidate['files']['dut.va']['sha256'], 'VA08 original source')
            seal.require(archive.read('run/work/tests/verify.py')==(adc_task/'tests/verify.py').read_bytes(), 'VA08 current checker differs')
            seal.require(frozen_bytes==(json.dumps([adc_cases[name]],indent=2)+'\n').encode(), 'VA08 case values differ')
            seal.require(package['criteria_sha256']==adc_criteria==adc_compact['criteria_sha256'], 'VA08 original full criteria differ')
            seal.require(archive.read('run/work/verifier/'+name+'/adc.va')==adc_checker.adc_source(case['thresholds'],case['delay']).encode(), 'VA08 ADC oracle stimulus differs')
            seal.require(archive.read('run/work/verifier/'+name+'/tb.scs')==adc_checker.netlist().encode(), 'VA08 netlist differs')
            seal.require(digest(raw)==old['waveform_sha256'] and raw.rstrip().endswith(b'END'), 'VA08 waveform identity/completeness')
            seal.require(old['status']=='graded' and old['returncode']==0 and int(old['passed'])==expected['score']==result['score'], 'VA08 numeric verdict differs')
            executed=archive.read('run/work/verifier/'+name+'/dut.va');seal.require(digest(executed)==old['executed_source_sha256'], 'VA08 executed source hash')
            translated=old['output_translation'];seal.require(translated['inverse_verified'],'VA08 path inverse not verified')
            restored=executed
            for edit in reversed(translated['edits']):
                original=edit['original_literal'].encode();new=edit['executed_literal'].encode()
                seal.require(restored.count(new)==1,'VA08 translated literal ambiguous');restored=restored.replace(new,original,1)
            seal.require(restored==source,'VA08 inverse translation source bytes')
            rrole='reference' if result['score']==1 else 'semantic_negative';variant='reference' if rrole=='reference' else audited['job_id']
            if rrole=='reference':seal.require(source==(adc_task/'solution/reference.va').read_bytes(),'VA08 reference source differs')
            records.append(dict(task_id='va08-adc-linearity',variant=variant,role=rrole,round='va08-historical-reuse',selected=True,
                condition_id=name,job_id=audited['job_id'],classification='graded_pass' if result['score']==1 else 'graded_rejection',
                execution=result['execution'],score=result['score'],current_numerical_contract_covered=True,current_case_values_match=True,
                archive_sha256=archive.receipt['package']['sha256'],report_sha256=digest(archive.read('run/work/verifier/report.json')),
                waveform_sha256=digest(raw),candidate_bundle_sha256=candidate['candidate_sha256'],candidate_files={'dut.va':{'sha256':digest(source)}},
                frozen_case_file_sha256=digest(frozen_bytes),case_value_sha256=digest(seal.canonical(case)),
                netlist_sha256=digest(adc_checker.netlist().encode()),executed_source_sha256=digest(executed),criteria_sha256=result['criteria_sha256'],task_package_sha256=result['task_package_sha256'],
                numerical_graders={'verify.py':{'frozen_sha256':report['checker_sha256'],'current_sha256':digest((adc_task/'tests/verify.py').read_bytes())}},
                identity_differences=[],spectre_version=report['spectre_version'],archive_locator='va08-local-archive/'+audited['job_id'],
                all_archive_members_verified=len(archive.members),support_boundary='Existing standalone VA08 adapter; no shared runtime or named-model evaluation claim.'))
        finally:archive.close()
    adc_records=[r for r in records if r['task_id']=='va08-adc-linearity']
    for variant in sorted({r['variant'] for r in adc_records}):
        group=[r for r in adc_records if r['variant']==variant]
        variants.append(dict(task_id='va08-adc-linearity',variant=variant,role=group[0]['role'],round='va08-historical-reuse',selected=True,
            planned_conditions=len(group),actual_conditions=len(group),all_current_numerical_conditions_covered=True,
            all_passed=all(r['classification']=='graded_pass' for r in group),has_semantic_rejection=any(r['classification']=='graded_rejection' for r in group)))
    # Store repeated file-level identities once, retaining per-condition hashes.
    identity_sets = {}
    for record in records:
        identities = {key:record.pop(key) for key in ('candidate_files','numerical_graders','identity_differences')}
        identities['strict_measurement_regrade'] = record.pop('strict_measurement_regrade',None)
        identity_id = digest(seal.canonical(identities))
        identity_sets[identity_id] = identities
        record['file_identity_set_sha256'] = identity_id
    tasks=[]
    chosen=[r for r in records if r['selected']]
    for task in sorted({r['task_id'] for r in chosen}):
        selected=[r for r in chosen if r['task_id']==task]
        task_variants=[v for v in variants if v['selected'] and v['task_id']==task]
        tasks.append(dict(task_id=task,
            reference_candidates=sum(v['role']=='reference' for v in task_variants),
            semantic_negative_candidates=sum(v['role']=='semantic_negative' for v in task_variants),
            semantic_negative_candidates_with_actual_rejection=sum(v['role']=='semantic_negative' and v['has_semantic_rejection'] for v in task_variants),
            reference_conditions=stats([r for r in selected if r['role']=='reference']),
            equivalent_conditions=stats([r for r in selected if r['role']=='equivalent']),semantic_negative_conditions=stats([r for r in selected if r['role']=='semantic_negative']),
            uncovered_current_numerical_conditions=[r['job_id'] for r in selected if not r['current_numerical_contract_covered']],
            current_task_metadata_sha256=digest((root/'benchmark/tasks'/task/'task.toml').read_bytes())))
    history={}
    for rnd in sorted({r['round'] for r in records}):history[rnd]=stats([r for r in records if r['round']==rnd])
    return dict(schema_version=1,evidence_kind='sealed_actual_spectre_calibration_audit',simulator_executed=False,
        canonical_root_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        scope='30 non-optimization tasks; functional-only optimization jobs explicitly excluded. Counts describe authored calibration candidates, not model success rate.',
        raw_evidence_availability='local-only archives; no anonymous public download claim. Compact receipt records hashes and logical locators only.',
        selection='Last explicitly listed task/variant evidence in round2 then followup-v3; current VA07; audited unchanged standalone VA08.',
        tool_sha256=digest(Path(__file__).read_bytes()),inputs={p.name:digest(p.read_bytes()) for p in [run_root/'round2-active-matrix.json',run_root/'followup-function-plan-v3.json',run_root/'legacy-va07-current-v1/matrix.json',measurement_path,adc_compact_path]},
        fixed_git_dependencies=dict(measurement_receipt_revision=measurement_revision,
            legacy_adc_execution_revision=adc_execution_revision,all_reachable_from_canonical_root_head=True,
            boundary='Root-history reachability verified locally; not a claim of anonymous public access.'),
        dependency_identity={p.name:digest(p.read_bytes()) for p in [base/'batch.py',base/'verification_measurement/regrade_measurement.py']},
        totals=dict(tasks=len(tasks),selected_conditions=stats(chosen),historical_attempted_conditions=stats(records),
                    selected_role_conditions={k:stats([r for r in chosen if r['role']==k]) for k in ('reference','equivalent','semantic_negative')},
                    selected_variants=len({(r['task_id'],r['variant']) for r in chosen}),
                    selected_reference_variants=sum(v['selected'] and v['role']=='reference' for v in variants),
                    selected_negative_variants=sum(v['selected'] and v['role']=='semantic_negative' for v in variants),
                    selected_negative_variants_with_actual_semantic_rejection=sum(v['selected'] and v['role']=='semantic_negative' and v['has_semantic_rejection'] for v in variants),uncovered_current_numerical_conditions=sum(not r['current_numerical_contract_covered'] for r in chosen)),
        historical_variant_attempts=len(variants),historical_fixed_denominators=history,excluded_optimization_function_jobs=excluded,
        limitations=['Original failed/compile attempts remain in historical denominators; no-waveform compile failures are not semantic rejection.',
            'Protocol/policy identity deltas do not claim that the current entire task package was executed; exact frozen criteria/package hashes are retained per condition.',
            'Measurement zero-code and empty PLL reference guards have row-level tests only; no actual VA induction established.',
            'This selected-input history is not an inventory of every earlier exploratory run in the repository.',
            'Targeted negative calibration does not establish full cross-product coverage; no Agentic named-model conclusions.'],
        legacy_va08_documentation_identity_delta=dict(file='benchmark/tasks/va08-adc-linearity/SOURCE.md',
            execution_revision=adc_execution_revision,frozen_sha256=digest(subprocess.check_output(['git','show',adc_execution_revision+':benchmark/tasks/va08-adc-linearity/SOURCE.md'],cwd=root)),
            current_sha256=digest((adc_task/'SOURCE.md').read_bytes()),interpretation='Historical evidence documentation changed; numeric inputs/reference/checker and standalone task boundary verified separately.'),
        public_reference_derivation={name:{key:value for key,value in data.items() if key!='source'} for name,data in derived_reference.items()},
        file_identity_sets=identity_sets,tasks=tasks,variants=variants,conditions=records)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--canonical-root',type=Path,required=True)
    parser.add_argument('--run-root',type=Path,required=True)
    parser.add_argument('--legacy-audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audit-output',type=Path,help='Explicit local-only detailed audit; compact receipt binds its SHA256')
    args=parser.parse_args()
    report=audit(args.canonical_root.resolve(),args.run_root.resolve(),args.legacy_audit.resolve())
    if args.audit_output:
        audit_bytes=(json.dumps(report,indent=2)+'\n').encode()
        args.audit_output.write_bytes(audit_bytes)
        report['local_only_full_audit_sha256']=digest(audit_bytes)
        report['local_only_full_audit_availability']='Operator retained ignored audit output; not a public download claim.'
        for condition in report['conditions']:
            condition.pop('failure_details',None)
            condition.pop('all_archive_members_verified',None)
            condition.pop('spectre_version',None)
        report['full_archive_verification']='Every archive member verified against sealed receipt; full per-job detail is bound by local audit SHA256.'
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['totals'],indent=2))


if __name__=='__main__':main()
