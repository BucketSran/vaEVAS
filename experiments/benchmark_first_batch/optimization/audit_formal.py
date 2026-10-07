"""Audit sealed formal optimization runs without executing archived code or Spectre.

Matrix and plan cover every preparation, including unstarted/failed attempts.
Only the explicitly selected canonical checkout supplies Python checkers.
"""
import argparse
from collections import Counter
import gzip
import io
import json
import math
import statistics
from pathlib import Path, PurePosixPath
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verification_measurement'))
from regrade_measurement import (SealedArchive, canonical, digest, load_module,
                                 require, require_same_case, verify_seal)
TOOL_SHA256 = digest(Path(__file__).read_bytes())

ORDER = [('warmup', r) for r in ('baseline', 'candidate')] + [
    (f'pair-{i:02d}', r) for i in range(1, 6) for r in ('baseline', 'candidate')]
ROLE_MAP={'semantic':'semantic_neg','performance_only':'performance_neg',
          'semantic_timing':'semantic_neg','semantic_edge':'semantic_neg','semantic_accuracy':'semantic_neg',
          'performance_and_possible_semantic':'mixed_neg',
          'reference':'reference','semantic_neg':'semantic_neg','performance_neg':'performance_neg',
          'equivalent_cpu_only':'equivalent_cpu_only','mixed_neg':'mixed_neg'}


def normalized_role(entry):
    role=entry.get('role',entry.get('category'))
    require(role in ROLE_MAP, 'unknown matrix role')
    return ROLE_MAP[role]


def safe_relative(value):
    path = PurePosixPath(value)
    require(isinstance(value, str) and value == str(path) and not path.is_absolute()
            and '..' not in path.parts and path.parts, 'unsafe evidence path')
    return value


def decode_waveform(stored, storage):
    """Bound decompression and bind both complete byte representations."""
    require(storage['version'] == 'gzip-lossless-psf-v1' and storage['encoding'] == 'gzip'
            and storage['roundtrip_verified'] is True, 'invalid lossless storage receipt')
    require(type(storage['raw_bytes']) is int and 0 < storage['raw_bytes'] <= 268435456,
            'invalid raw PSF size')
    require(len(stored) == storage['gzip_bytes'] and digest(stored) == storage['gzip_sha256'],
            'gzip identity differs')
    require(safe_relative(storage['raw_path']) == 'psf/tran.tran.tran'
            and safe_relative(storage['gzip_path']) == storage['raw_path'] + '.gz',
            'raw/gzip PSF paths differ')
    with gzip.GzipFile(fileobj=io.BytesIO(stored)) as stream:
        raw = stream.read(storage['raw_bytes'] + 1)
        require(len(raw) == storage['raw_bytes'] and not stream.read(1), 'raw PSF byte count differs')
    require(digest(raw) == storage['raw_sha256'], 'raw PSF identity differs')
    elapsed = storage['compression_elapsed_s']
    require(not isinstance(elapsed, bool) and math.isfinite(elapsed) and elapsed >= 0,
            'invalid compression time')
    return raw


def verify_attempt_order(paired):
    warmups, records = paired['warmups'], paired['records']
    require(len(warmups) <= 2 and (not records or len(warmups) == 2), 'missing warmups')
    attempts = warmups + records
    actual = [(r['phase'], r['role']) for r in attempts]
    require(actual == ORDER[:len(actual)], 'missing, duplicate or reordered paired attempts')
    if paired['status'] == 'completed':
        require(len(attempts) == 12, 'completed performance evidence requires 2 warmups and 5 AB pairs')
    else:
        require(not attempts or any(r.get('status') != 'completed' or r.get('passed') is not True
                                   for r in attempts[-1:]), 'early exit lacks a failed final attempt')
    require(all(r.get('status') == 'completed' and r.get('passed') is True
                for r in attempts[:-1]), 'attempts continued after failed work')
    return attempts


def classify_attempt(report, functional=None, paired=None):
    if report is None or report.get('status') in {'infrastructure_error', 'checker_error', 'environment_error'}:
        return 'infrastructure_failure'
    if report.get('status') == 'submission_contract_violation':
        return 'submission_contract_failure'
    if functional is not None and functional['passed'] is False:
        return 'semantic_failure'
    if paired is not None:
        if paired['status'] == 'infrastructure_error':
            return 'infrastructure_failure'
        if paired['status'] != 'completed':
            failed = (paired['warmups'] + paired['records'])[-1:]
            if failed and failed[0].get('status') == 'completed' and failed[0].get('functional', {}).get('passed') is False:
                return 'semantic_failure'
            return 'solver_or_evidence_failure'
        return 'passed' if paired['comparison']['passed'] else 'performance_failure'
    return 'passed' if report.get('passed') is True else 'solver_or_evidence_failure'


def parse_rows(raw, case, parser, runtime, scratch):
    path = scratch / 'waveform.psf'
    path.write_bytes(raw)
    rows = parser.read_psf(path)
    runtime.validate_rows(rows, case)
    return rows


def check_equal(actual, expected, label):
    require(canonical(actual) == canonical(expected), label + ' differs')


def validate_argv(argv):
    require(isinstance(argv,list) and len(argv)==12 and isinstance(argv[0],str) and argv[0]
            and argv[1:]==['-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+lqtimeout','5','+mt=1'],
            'solver invocation differs from frozen single-thread PSF protocol')


def verify_report_projection(result, report):
    """Final structured-report projection, matching the trusted harness contract."""
    status=report.get('status')
    projected={'execution':'invalid_result','verdict':'not_evaluated','score':None}
    if isinstance(status,str):
        projected['benchmark_status']=status
        if status in {'infrastructure_error','checker_error'}:
            projected['execution']='infrastructure_error'
        else:
            reward=report.get('reward')
            valid=type(reward) in (int,float) and math.isfinite(reward) and 0<=reward<=1
            if status=='submission_contract_violation' and valid and reward==0:
                projected.update(execution='ok',verdict='fail',score=reward)
            elif status=='completed' and valid and isinstance(report.get('cases'),list) and report['cases']:
                cases=report['cases']
                if all(isinstance(c,dict) and type(c.get('passed')) is bool for c in cases):
                    graded=all(c.get('status')=='graded' or (c.get('returncode')==0 and c.get('timeout') is False
                               and isinstance(c.get('waveform_sha256'),str)) for c in cases)
                    if graded:projected.update(execution='ok',verdict='pass' if reward==1 else 'fail',score=reward)
                    else:projected['execution']='unclassified_failure'
    for key in ('execution','verdict','score','benchmark_status'):
        check_equal(result.get(key),projected.get(key),'result/report projection: '+key)


def require_full_inventory(entry, preparation, current_cases):
    names=[case['name'] for case in current_cases]
    require(names and len(names)==len(set(names)), 'invalid canonical task inventory')
    require(set(entry['conditions'])==set(names) and len(entry['conditions'])==len(names),
            'matrix omits or adds canonical full-task conditions')
    packets=[c['condition_id'] for c in preparation['cases']]
    require(set(packets)==set(names) and len(packets)==len(names),
            'preparation omits or adds canonical full-task conditions')


def audit_paired(archive, prefix, case, candidate, baseline, modules, scratch):
    parser, runtime, optimization, evaluate = modules
    paired = archive.json(prefix + 'performance_report.json')
    optimization.validate_admitted_policy(paired['policy'])
    attempts = verify_attempt_order(paired)
    expected_dirs = {phase + '-' + role for phase, role in ORDER[:len(attempts)]}
    actual_dirs = {name[len(prefix):].split('/')[0] for name in archive.members
                   if name.startswith(prefix) and '/' in name[len(prefix):]}
    require(actual_dirs == expected_dirs, 'paired directory inventory differs')
    receipts = []
    for record in attempts:
        folder = prefix + record['phase'] + '-' + record['role'] + '/'
        disk_record = archive.json(folder + 'record.json')
        validate_argv(record['argv'])
        check_equal({k:v for k,v in record.items() if k not in {'phase','role'}}, disk_record,
                    'paired record.json')
        source = baseline if record['role'] == 'baseline' else candidate
        require(archive.read(folder + 'original.va') == source == archive.read(folder + 'dut.va'),
                'paired role source differs')
        require(digest(source) == record['source_sha256'] == record['executed_source_sha256'],
                'paired source receipt differs')
        require(record['output_translation']['inverse_verified'] and not record['output_translation']['edits'],
                'unexpected paired source translation')
        require(archive.read(folder + 'tb.scs') == case['netlist'].encode()
                and digest(case['netlist'].encode()) == record['netlist_sha256'], 'paired netlist differs')
        # Even incomplete attempts remain listed; they cannot enter a performance denominator.
        if record['status'] != 'completed':
            receipts.append({'phase':record['phase'], 'role':record['role'], 'status':record['status'],
                             'classification':'solver_or_evidence_failure',
                             'source_sha256':record['source_sha256'],'netlist_sha256':record['netlist_sha256'],
                             'returncode':record.get('returncode'), 'error':record.get('error'),
                             'attempt_artifacts':{n[len(folder):]:v for n,v in archive.verified.items() if n.startswith(folder)}})
            continue
        stats = optimization.validate_solver_evidence(source, record['returncode'],
            archive.read(folder + 'spectre.log').decode(errors='replace'),
            archive.read(folder + 'stdout.log'), None, stream_layout=record['stream_layout'])
        check_equal(stats, record['statistics'], 'native solver statistics')
        storage = record['waveform_storage']
        require(folder + storage['raw_path'] not in archive.members, 'paired raw PSF was not replaced')
        raw = decode_waveform(archive.read(folder + safe_relative(storage['gzip_path'])), storage)
        require(digest(raw) == record['waveform_sha256'], 'paired waveform receipt differs')
        rows = parse_rows(raw, case, parser, runtime, scratch)
        require(len(rows) == record['waveform_rows'], 'paired waveform row count differs')
        verdict = evaluate(rows, case, scratch)
        check_equal(verdict, record['functional'], 'paired functional replay')
        require(type(verdict['passed']) is bool and verdict['passed'] == record['passed'], 'paired boolean verdict differs')
        receipts.append({'phase':record['phase'], 'role':record['role'], 'status':record['status'],
                         'functional_passed':verdict['passed'], 'waveform_rows':len(rows),
                         'storage':storage, 'solver_statistics':stats,
                         'source_sha256':record['source_sha256'],
                         'executed_source_sha256':record['executed_source_sha256'],
                         'netlist_sha256':record['netlist_sha256'],
                         'solver_process_elapsed_s':record['process_elapsed_s'],
                         'compression_elapsed_s':storage['compression_elapsed_s']})
    if paired['status'] == 'completed':
        for record in attempts:
            require(record['host'] == attempts[0]['host']
                    and record['statistics']['spectre_version'] == attempts[0]['statistics']['spectre_version'],
                    'warmup/measured host or solver identity differs')
        comparison = optimization.summarize_pairs(paired['records'], paired['policy'])
        check_equal(comparison, paired['comparison'], 'recomputed paired summary')
        require(paired['reward'] == int(comparison['passed']), 'paired summary reward differs')
    else:
        require('comparison' not in paired, 'failed attempts have a performance comparison')
        require(paired['reward'] == (None if paired['status'] == 'infrastructure_error' else 0),
                'failed paired reward differs')
    return paired, receipts


def audit_one(directory, wrapper, entry, root, scratch):
    path = directory / 'remote' / wrapper['job_id'] / 'archive/job.tar.gz'
    archive = SealedArchive(path, json.loads(path.with_name('receipt.json').read_text()))
    try:
        result, package, manifest = verify_seal(archive, wrapper)
        require(package['task_id'] == entry['task_id'] and manifest['candidate_sha256'] == entry['candidate_sha256']
                and package['criteria_sha256'] == entry['criteria_sha256'], 'matrix identity differs')
        prepared = json.loads((directory / 'preparation.json').read_text())
        require(prepared['candidate']['candidate_sha256'] == manifest['candidate_sha256']
                and prepared['criteria_sha256'] == package['criteria_sha256'], 'preparation identity differs')
        require(digest(json.dumps(prepared['source_identity'],sort_keys=True).encode()) == package['criteria_sha256'],
                'criteria digest differs from full preparation source inventory')
        packet = [c for c in prepared['cases'] if c['condition_id'] == wrapper['condition_id']]
        require(len(packet) == 1 and packet[0]['sha256'] == result['task_package_sha256'], 'prepared packet differs')
        task = root / 'benchmark/tasks' / entry['task_id']
        for name in ('cases.json','instruction.md'):
            path=task/'instruction.md' if name=='instruction.md' else task/'tests/cases.json'
            require(prepared['source_identity'][name] == digest(path.read_bytes()),
                    'current full task identity differs: ' + name)
        require(prepared['source_identity']['test.sh'] == digest(archive.read('run/work/tests/test.sh')),
                'frozen entrypoint identity differs')
        frozen = archive.json('run/work/tests/cases.json')
        current = json.loads((task / 'tests/cases.json').read_text())
        require(len(frozen) == 1 and frozen[0]['name'] == wrapper['condition_id'], 'invalid condition packet')
        case = frozen[0]
        matching = [c for c in current if c['name'] == case['name']]
        require(len(matching) == 1, 'current condition missing or duplicate')
        require_same_case(matching[0], case)
        canonical_files = {name:root/'benchmark/checkers'/name for name in
                           ('adc_linearity.py','circuit_task.py','first_batch_optimization.py')}
        canonical_files.update({name:task/'tests'/name for name in
                                ('verify.py','evaluate.py','contract.json','performance.json','baseline.va')})
        for name, current_path in canonical_files.items():
            require(archive.read('run/work/tests/' + name) == current_path.read_bytes(),
                    'current/frozen checker or contract differs: ' + name)
            require(prepared['source_identity'][name] == digest(current_path.read_bytes()),
                    'preparation/current identity differs: ' + name)
        candidate = archive.read('candidate/files/dut.va')
        require(candidate == archive.read('run/work/candidate/dut.va'), 'working candidate differs')
        baseline = (task / 'tests/baseline.va').read_bytes()
        modules = [load_module(canonical_files[name], 'formal_audit_' + name[:-3]) for name in
                   ('adc_linearity.py','circuit_task.py','first_batch_optimization.py')]
        evaluate = load_module(task/'tests/evaluate.py', 'formal_audit_evaluate').evaluate
        modules.append(evaluate)
        parser, runtime, optimization, _ = modules
        policy = json.loads((task/'tests/performance.json').read_text())
        optimization.classify_case_packet(frozen, policy)
        output = {'task_id':entry['task_id'], 'role':entry['role'], 'variant':entry['variant'],
                  'declared_category':entry.get('category',entry['role']),
                  'condition_id':case['name'], 'job_id':wrapper['job_id'],
                  'archive_sha256':archive.receipt['package']['sha256'],
                  'archive_bytes':archive.receipt['package']['bytes'],
                  'verified_member_bytes':sum(r['bytes'] for r in archive.verified.values()),
                  'verified_members':len(archive.members), 'result':result,
                  'results_sha256':digest((directory/'results.json').read_bytes()),
                  'case_sha256':digest(canonical(case)), 'candidate_sha256':manifest['candidate_sha256'],
                  'canonical_identity':{k:digest(p.read_bytes()) for k,p in canonical_files.items()}}
        report_path = 'run/work/verifier/report.json'
        if report_path not in archive.members:
            output.update(classification='infrastructure_failure', reason='no verifier report; no semantic rejection evidence')
            return output
        report = archive.json(report_path)
        verify_report_projection(result,report)
        output['report_sha256'] = digest(archive.read(report_path))
        require(report['reward'] == result['score'], 'report/result score differs')
        require(report['candidate_sha256'] == digest(candidate), 'report candidate identity differs')
        for key, name in {'cases_sha256':'cases.json','contract_sha256':'contract.json',
                          'checker_sha256':'verify.py','runtime_sha256':'circuit_task.py','parser_sha256':'adc_linearity.py'}.items():
            require(report[key] == digest(archive.read('run/work/tests/' + name)), 'report identity differs: ' + key)
        if not report['cases']:
            # A source-policy rejection can be verified without executing the source.
            if report['status'] == 'submission_contract_violation':
                try:
                    optimization.validate_performance_source(candidate)
                    runtime.prepare_source(candidate, ['dut.va'], [], scratch/'guard')
                except ValueError:
                    pass
                else:
                    raise ValueError('source rejection not reproduced by canonical guards')
            output.update(classification=classify_attempt(report), report_status=report['status'])
            return output
        require(len(report['cases']) == 1, 'report condition inventory differs')
        old = report['cases'][0]
        validate_argv(old['argv'])
        require(old['name'] == case['name'], 'report condition differs')
        prefix = 'run/work/verifier/' + safe_relative(case['name']) + '/'
        require(archive.read(prefix+'original/dut.va') == candidate == archive.read(prefix+'dut.va'), 'main source differs')
        identities = old['candidate_files']['dut.va']
        require(identities['original_sha256'] == identities['executed_sha256'] == digest(candidate)
                and identities['output_translation']['inverse_verified'] and not identities['output_translation']['edits'],
                'main candidate receipt differs')
        require(archive.read(prefix+'tb.scs') == case['netlist'].encode()
                and old['netlist_sha256'] == digest(case['netlist'].encode()), 'main netlist differs')
        for name, source in case.get('support', {}).items():
            require(archive.read(prefix+safe_relative(name)) == source.encode(), 'main support differs')
        if old['status'] != 'graded' and 'waveform_sha256' not in old:
            output.update(classification=classify_attempt(report), condition_status=old['status'])
            return output
        stats = optimization.validate_solver_evidence(candidate, old['returncode'],
            archive.read(prefix+'spectre.log').decode(errors='replace'), archive.read(prefix+'stdout.log'),
            None, stream_layout='merged')
        raw = archive.read(prefix+'psf/tran.tran.tran')
        require(digest(raw) == old['waveform_sha256'], 'main waveform identity differs')
        rows = parse_rows(raw, case, parser, runtime, scratch)
        require(len(rows) == old['waveform_rows'], 'main waveform row count differs')
        functional = evaluate(rows, case, scratch)
        paired, receipts = None, []
        if case.get('performance') and functional['passed']:
            check_equal(functional, old['functional'], 'main functional replay')
            paired, receipts = audit_paired(archive, prefix+'paired/', case, candidate, baseline, modules, scratch)
            check_equal(paired['policy'], policy, 'paired/current policy')
            check_equal(old.get('performance'), paired.get('comparison'), 'main/paired comparison')
            if paired['reward'] is None:
                require(old['status'] == 'infrastructure_error' and report['reward'] is None,
                        'paired infrastructure failed as a scored rejection')
            else:
                require(old['performance_status'] == paired['status'] and old['passed'] == bool(paired['reward']),
                        'main/paired verdict differs')
        else:
            check_equal(functional, {k:old[k] for k in functional}, 'main functional replay')
            require(not any(n.startswith(prefix+'paired/') for n in archive.members), 'unexpected paired work')
        if report['reward'] is not None:
            require(report['reward'] == int(old['passed']), 'condition/report reward differs')
        output.update(classification=classify_attempt(old, functional, paired), functional=functional,
                      main_waveform_sha256=digest(raw), main_waveform_rows=len(rows),
                      main_solver_statistics=stats, main_process_elapsed_s=old['elapsed_s'], paired_attempts=receipts,
                      main_source_sha256=digest(candidate), main_netlist_sha256=digest(case['netlist'].encode()),
                      performance_comparison=paired.get('comparison') if paired else None)
        if paired and paired['status']=='completed':
            measured=paired['records']
            a=statistics.median(r['process_elapsed_s'] for r in measured[::2])
            b=statistics.median(r['process_elapsed_s'] for r in measured[1::2])
            require(a>0 and b>0 and math.isfinite(a) and math.isfinite(b), 'invalid process duration')
            output['process_time_diagnostic']={'baseline_median_s':a,'candidate_median_s':b,
                                              'median_ratio':b/a,'used_for_reward':False}
        return output
    finally:
        archive.close()


def audit_matrix(matrix_path, plan_path, root):
    matrix = json.loads(matrix_path.read_text())
    plan = json.loads(plan_path.read_text())
    require(isinstance(matrix,list) and matrix, 'empty matrix')
    prepared_paths = [str(Path(e['prepared']).resolve()) for e in matrix]
    require(len(set(prepared_paths)) == len(prepared_paths) and set(prepared_paths) == {str(Path(p).resolve()) for p in plan}
            and len(plan) == len(matrix), 'matrix/plan inventory differs')
    records, pending = [], []
    variants=set()
    with tempfile.TemporaryDirectory(prefix='formal-archive-audit-') as temporary:
        scratch = Path(temporary)
        for supplied in matrix:
            entry = dict(supplied)
            directory = Path(entry['prepared'])
            preparation = json.loads((directory/'preparation.json').read_text())
            if 'negative' in entry:
                entry.update(role=normalized_role(entry),
                             variant=entry['negative'], candidate_sha256=entry['frozen_candidate_sha256'],
                             conditions=[c['condition_id'] for c in preparation['cases']])
            entry['role']=normalized_role(entry)
            key=(entry['task_id'],entry['variant'])
            require(key not in variants, 'duplicate task/variant preparation')
            variants.add(key)
            require(len(set(entry['conditions'])) == len(entry['conditions']), 'duplicate matrix condition')
            current_cases=json.loads((root/'benchmark/tasks'/entry['task_id']/'tests/cases.json').read_text())
            require_full_inventory(entry,preparation,current_cases)
            path = directory/'results.json'
            wrappers = json.loads(path.read_text()) if path.exists() else []
            require(isinstance(wrappers,list), 'results must be an array')
            names = [w['condition_id'] for w in wrappers]
            require(len(names) == len(set(names)) and set(names).issubset(entry['conditions']), 'results condition inventory differs')
            for name in entry['conditions']:
                matches = [w for w in wrappers if w['condition_id'] == name]
                if not matches:
                    pending.append({'task_id':entry['task_id'],'role':entry['role'],'variant':entry['variant'],
                                    'condition_id':name,'classification':'not_completed','reason':'no result'})
                    continue
                records.append(audit_one(directory,matches[0],entry,root,scratch))
    outcomes=[]
    for entry in matrix:
        variant=entry.get('variant',entry.get('negative'))
        selected=[r for r in records if r['task_id']==entry['task_id'] and r['variant']==variant]
        waiting=[r for r in pending if r['task_id']==entry['task_id'] and r['variant']==variant]
        role=selected[0]['role'] if selected else normalized_role(entry)
        classifications=[r['classification'] for r in selected]
        complete=not waiting and bool(selected)
        clean=complete and all(c in {'passed','semantic_failure','performance_failure'} for c in classifications)
        expected=(all(c=='passed' for c in classifications) if role in {'reference','equivalent_cpu_only'} else
                  'semantic_failure' in classifications if role=='semantic_neg' else
                  any(c in {'semantic_failure','performance_failure'} for c in classifications) if role=='mixed_neg' else
                  'performance_failure' in classifications and 'semantic_failure' not in classifications)
        outcomes.append({'task_id':entry['task_id'],'variant':variant,'role':role,
                         'complete':complete,'classifications':classifications,
                         'calibration_expectation_met':bool(clean and expected) if complete else None})
    return {'schema_version':1,'mode':'sealed_formal_optimization_audit_no_simulation',
            'tool_sha256':TOOL_SHA256, 'matrix_sha256':digest(matrix_path.read_bytes()),
            'plan_sha256':digest(plan_path.read_bytes()), 'python_version':sys.version.split()[0],
            'records':records,'pending':pending,'classification_counts':dict(Counter(r['classification'] for r in records)),
            'variant_outcomes':outcomes,
            'scope':'each performance success requires 2 warmups plus 5 complete alternating AB pairs; compression is outside solver timing'}


def compact_receipt(report):
    """Retain identities, judgments and timing evidence without artifact dictionaries."""
    compact=json.loads(json.dumps(report))
    compact['availability']='local-only; complete sealed archives and full audit output remain in ignored runs'
    for record in compact['records']:
        result=record.pop('result')
        record['result_identity']={key:result[key] for key in
            ('execution','verdict','score','benchmark_status','task_id','task_version','condition_id',
             'criteria_sha256','candidate_sha256','task_package_sha256') if key in result}
    return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canonical-root',type=Path,required=True)
    parser.add_argument('--matrix',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compact-output',type=Path,help='Optional new compact receipt alongside full ignored audit')
    args = parser.parse_args()
    require(not args.output.exists(), 'output must be new')
    require(args.compact_output is None or not args.compact_output.exists(), 'compact output must be new')
    report = audit_matrix(args.matrix,args.plan,args.canonical_root.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    if args.compact_output is not None:
        args.compact_output.parent.mkdir(parents=True,exist_ok=True)
        args.compact_output.write_text(json.dumps(compact_receipt(report),indent=2,allow_nan=False)+'\n')
    print(json.dumps({'records':len(report['records']),'pending':len(report['pending']),
                      'classification_counts':report['classification_counts']}))


if __name__ == '__main__':
    main()
