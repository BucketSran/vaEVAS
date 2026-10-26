"""Reuse fixed Astra scope for identical sources and checked generated output."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c1_candidate_task', D / 'prepare_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.invariant()
load, git, sha, write = task.load, task.git, task.sha, task.write
final = load(D / 'final-candidate.json')
prep = load(D / 'source-preparation.json')
precheck = load(D / 'precheck-acceptance.json')
generation = load(D / 'generation-acceptance.json')
assert all(row['returncode'] == 0 for row in precheck['checks'])
assert git('rev-parse', final['commit'] + '^{tree}').decode().strip() == final['tree']
source_paths = {row['path'] for row in prep['source_paths'] if row['changed_from_base']}
generated_paths = set(prep['deferred_generated_paths'])
actual = set(git('diff', '--name-only', task.BASE, final['commit']).decode().splitlines())
assert actual == set(precheck['paths']) and actual <= source_paths | generated_paths
sources = []
for row in prep['source_paths']:
    data = git('show', final['commit'] + ':' + row['path'])
    assert sha(data) == row['resolved_sha256']
    sources.append({'path': row['path'], 'sha256': sha(data), 'reviewed_source_snapshot': prep['source_snapshot'], 'composition': row['resolution']})
review_paths = [task.B / 'night-coordination' / name / 'review-report.json' for name in (
    'pr4-168a9d7a-astra-r1-20261027', 'pr4-context-increment-astra-r2-20261027',
    'pr264-maintenance-timeout-astra-r3-20261027')]
r1, r2, r3 = [load(path) for path in review_paths]
r2_acceptance = load(task.N / 'increment-review-acceptance.json')
r3_acceptance = load(task.N / 'timeout-increment-review-acceptance.json')
assert sha(review_paths[0].read_bytes()) == '523dec2ae1b146a82e060e15729331a08078c7f991f77e9bfcdd7cef67da8bd4'
assert sha(review_paths[1].read_bytes()) == r2_acceptance['review_sha256']
assert sha(review_paths[2].read_bytes()) == r3_acceptance['review_report']['sha256']
assert not r1['Spec']['findings']
assert {row['id'] for row in r1['Standards']['findings']} == {'PR4-MAINT-01', 'PR4-MAINT-02'}
assert set(r2_acceptance['closed_old_P2']) == {'PR4-MAINT-01', 'PR4-MAINT-02'}
assert not r2['Standards']['findings'] and not r2['Spec']['findings']
assert not r3['Standards']['findings'] and not r3['Spec']['findings']
assert source_paths <= set(r1['scope']['paths']) | set(r2['scope']['C1_increment']['paths'])
assert load(D / 'activation-workflow-acceptance.json')['merge_allowed']
assert load(task.N / 'baseline-merge-20261027/merge-verification.json')['merge_commit'] == task.BASE
for path in ('evas/validation/baselines/regression-v1.json', 'evas/validation/baselines/regression-v1.review.json',
             'scripts/context-registration-bundle.json', 'scripts/run_trusted_regression_gate.py',
             'scripts/regression_gate.py', 'scripts/regression_context_registration.py'):
    assert git('show', final['commit'] + ':' + path) == git('show', task.BASE + ':' + path)
write(D / 'review-reuse-acceptance.json', {
    'accepted_at_utc': datetime.now(timezone.utc).isoformat(), 'candidate': final['commit'], 'tree': final['tree'], 'base': task.BASE,
    'new_independent_review': False,
    'policy_basis': 'Standing T3 rule: accepted source and evidence identity may be reused; pure deterministic generated changes are verified by the controller, not assigned a duplicate review.',
    'reviews': [{'path': str(path), 'sha256': sha(path.read_bytes())} for path in review_paths],
    'original_findings': ['PR4-MAINT-01', 'PR4-MAINT-02'], 'closed_by_independent_R2': True,
    'remaining_actionable_findings': [], 'source_files': sources,
    'changed_source_paths': sorted(source_paths), 'deterministic_generated_paths': sorted(actual - source_paths),
    'generated_version_preservation': generation['old_versions_retained'], 'generation_acceptance': str(D / 'generation-acceptance.json'),
    'precheck': str(D / 'precheck-acceptance.json'), 'trusted_main_workflow_check': str(D / 'activation-workflow-acceptance.json'),
    'necessary_new_CI': 'pending', 'merged': False, 'batch4_accepted': False, 'scientific_qualification': False})
task.invariant()
print(json.dumps({'candidate': final['commit'], 'accepted_source_files': len(sources),
                  'generated_delta': len(actual - source_paths), 'review': 'matching R1/R2/R3 reused', 'new_CI': 'pending'}), flush=True)
