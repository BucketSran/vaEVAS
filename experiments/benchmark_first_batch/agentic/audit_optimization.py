"""Reanalyze completed Agentic optimization evidence without backend requests.

The existing sealed Trial audit binds the candidate and final package. The
formal optimization auditor supplies paired-waveform and solver-statistics
checks. Only matching current repository checkers are imported, never archive
code. Main failures correctly leave performance work not_run.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / 'experiments/benchmark_first_batch/optimization'))
from audit import summarize
from audit_formal import (SealedArchive, audit_paired, check_equal, digest,
                          load_module, parse_rows, require, verify_seal)


def audit_trial(folder):
    audited = summarize(folder)
    identity = json.loads((folder / 'identity.json').read_text())
    output = {'attempt': folder.name, 'new_model_or_solver_requests': 0,
              'candidate_final_score': audited['archives'][0]['score']
              if len(audited['archives']) == 1 else None,
              'phase_exception_type': (audited.get('exception') or {}).get('exception_type'),
              'inventory_seal_verified': bool(audited['archives']),
              'agentic_supplement_auditor_sha256': digest(Path(__file__).read_bytes()),
              'formal_auditor_sha256': digest((REPO / 'experiments/benchmark_first_batch/optimization/audit_formal.py').read_bytes()),
              'paired_cases': []}
    receipts = list(folder.glob('jobs/*/*/verifier/transport/*/archive/receipt.json'))
    require(len(receipts) <= 1, 'multiple final archives')
    if not receipts:
        output['performance_stage'] = 'not_run_no_completed_final_archive'
        return output
    output.update(audit_bound_archive(receipts[0], identity))
    return output


def audit_bound_archive(receipt_path, identity):
    """The frozen Trial identity must bind the previously sealed archive."""
    task = REPO / 'benchmark/tasks' / identity['task_id']
    canonical = {name: REPO / 'benchmark/checkers' / name for name in
                 ('adc_linearity.py', 'circuit_task.py', 'first_batch_optimization.py')}
    canonical.update({name: task / 'tests' / name for name in
                      ('evaluate.py', 'performance.json', 'baseline.va')})
    output = {'paired_cases': []}
    receipt = json.loads(receipt_path.read_text())
    archive = SealedArchive(receipt_path.with_name('job.tar.gz'), receipt)
    try:
        sealed = archive.json('run/result.json')
        result, package, manifest = verify_seal(archive, {
            'result': sealed, 'job_id': receipt['request']['job_id'],
            'condition_id': sealed['condition_id']})
        require(result['task_package_sha256'] == identity['final_task_package_sha256'],
                'paired final package differs from frozen Trial')
        require(package['task_id'] == identity['task_id'], 'paired task identity differs')
        output.update(archive_sha256=archive.receipt['package']['sha256'],
                      candidate_bundle_sha256=manifest['candidate_sha256'],
                      final_package_sha256=result['task_package_sha256'])
        if result['execution'] != 'ok':
            output['performance_stage'] = 'not_run_ungraded_infrastructure'
            return output
        for name, path in canonical.items():
            require(path.read_bytes() == archive.read('run/work/tests/' + name),
                    'current/frozen trusted optimization input differs: ' + name)
        output['trusted_source_sha256'] = {name: digest(path.read_bytes())
                                         for name, path in canonical.items()}
        modules = [load_module(canonical[name], 'agentic_paired_' + name[:-3])
                   for name in ('adc_linearity.py', 'circuit_task.py', 'first_batch_optimization.py')]
        evaluate = load_module(canonical['evaluate.py'], 'agentic_paired_evaluate').evaluate
        modules.append(evaluate)
        candidate = archive.read('candidate/files/dut.va')
        baseline = canonical['baseline.va'].read_bytes()
        cases = archive.json('run/work/tests/cases.json')
        records = {record['name']: record for record in
                   archive.json('run/work/verifier/report.json')['cases']}
        policy = json.loads(canonical['performance.json'].read_text())
        with tempfile.TemporaryDirectory(prefix='agentic-paired-audit-') as temporary:
            scratch = Path(temporary)
            for case in cases:
                if not case.get('performance'):
                    continue
                record = records.get(case['name'])
                prefix = 'run/work/verifier/' + case['name'] + '/'
                paired_prefix = prefix + 'paired/'
                paired_exists = any(name.startswith(paired_prefix) for name in archive.members)
                if not record or not record.get('waveform_sha256'):
                    require(not paired_exists, 'paired data exists without a main waveform')
                    output['paired_cases'].append({'condition': case['name'],
                        'stage': 'not_run_main_submission_or_compile_failure', 'attempts': []})
                    continue
                raw = archive.read(prefix + 'psf/tran.tran.tran')
                rows = parse_rows(raw, case, modules[0], modules[1], scratch)
                functional = evaluate(rows, case, scratch)
                check_equal(functional, record.get('functional',
                            {key: record.get(key) for key in functional}), 'main functional replay')
                if not functional['passed']:
                    require(not paired_exists, 'paired work followed a main functional failure')
                    output['paired_cases'].append({'condition': case['name'],
                        'stage': 'not_run_main_functional_failure', 'attempts': []})
                    continue
                require(paired_exists, 'main passed without paired evidence')
                paired, attempts = audit_paired(archive, paired_prefix, case,
                                                 candidate, baseline, modules, scratch)
                check_equal(paired['policy'], policy, 'paired frozen policy')
                check_equal(record.get('performance'), paired.get('comparison'),
                            'main/paired comparison')
                require(record['performance_status'] == paired['status'],
                        'main/paired status differs')
                if paired['reward'] is not None:
                    require(record['passed'] == bool(paired['reward']), 'main/paired verdict differs')
                output['paired_cases'].append({'condition': case['name'],
                    'stage': paired['status'], 'attempts': attempts,
                    'comparison': paired.get('comparison'),
                    'lossless_waveform_and_statistics_replayed': True})
        output['performance_stage'] = 'audited'
        return output
    finally:
        archive.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt')
    parser.add_argument('--output-name', default='paired-evidence-audit.json')
    args = parser.parse_args()
    require(Path(args.output_name).name == args.output_name, 'output must be one file name')
    folder = Path(os.environ['AGENTIC_OUTPUT']) / args.attempt
    destination = folder / args.output_name
    require(not destination.exists(), 'refuse overwriting retained paired audit')
    result = audit_trial(folder)
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(args.attempt, result['performance_stage'])


if __name__ == '__main__':
    main()
