"""Bind matching independent review to the frozen PR266 rebind; the delta adds no reviewed-source change."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('rebind_task', D / 'prepare_rebind.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
load, git, sha, write = task.load, task.git, task.sha, task.write
task.invariant()
assert not (D / 'review-reuse-acceptance.json').exists()
final = load(D / 'final-candidate.json')
pre = load(D / 'precheck-acceptance.json')
flow = load(D / 'activation-workflow-acceptance.json')
prep = load(D / 'source-preparation.json')
r3 = load(task.F / 'review-r3-acceptance.json')
r4 = load(task.X / 'review-r4-acceptance.json')
assert r3['candidate'] == task.OLD_PR and r3['tree'] == task.OLD_PR_TREE
assert r3['standards_findings'] == r3['spec_findings'] == [] and r3['source_increment_review_accepted']
assert sha(Path(r3['report']).read_bytes()) == r3['report_sha256']
assert r4['Standards_findings'] == r4['Spec_findings'] == [] and r4['exact_governance']['accepted']
assert sha(Path(r4['review_report']['path']).read_bytes()) == r4['review_report']['sha256']
assert all(row['returncode'] == 0 for row in pre['checks'])
assert all(sha((task.S / p).read_bytes()) == digest for p, digest in pre['files'].items())
assert flow['merge_allowed'] and flow['bundle_requested'] is False
source_paths = [row['path'] for row in prep['source_paths']]
for path in source_paths:
    assert git('rev-parse', final['commit'] + ':' + path) == git('rev-parse', task.OLD_PR + ':' + path), path
delta = set(git('diff', '--name-only', task.OLD_PR, final['commit']).decode().splitlines())
main_delta = set(git('diff', '--name-only', task.OLD_BASE, task.BASE).decode().splitlines())
assert delta <= task.GENERATED | main_delta, sorted(delta - task.GENERATED - main_delta)
for path in delta & main_delta - task.GENERATED:
    assert git('rev-parse', final['commit'] + ':' + path) == git('rev-parse', task.BASE + ':' + path), path
write(D / 'review-reuse-acceptance.json', {
    'accepted_at_utc': datetime.now(timezone.utc).isoformat(), 'accepted_by': 'tclaude/claude-opus-5-5 main controller',
    'candidate': final['commit'], 'tree': final['tree'], 'base': task.BASE, 'previous_reviewed_head': task.OLD_PR,
    'source_review': {'acceptance': str(task.F / 'review-r3-acceptance.json'), 'report': r3['report'], 'report_sha256': r3['report_sha256'],
                      'model': r3['actual_model'], 'options': r3['actual_options'], 'findings': 0},
    'context_review': {'acceptance': str(task.X / 'review-r4-acceptance.json'), 'report': r4['review_report']['path'],
                       'report_sha256': r4['review_report']['sha256'], 'findings': 0},
    'reviewed_source_paths_exact': len(source_paths),
    'delta_from_reviewed_head': sorted(delta),
    'delta_classes': {'generated_regenerated': sorted(delta & task.GENERATED),
                      'main_reviewed_merged': sorted(delta & main_delta - task.GENERATED)},
    'generated_checks': [row['receipt'] for row in pre['checks']],
    'activation_workflow': str(D / 'activation-workflow-acceptance.json'),
    'remaining_actionable_findings': [],
    'new_review_round_required': False,
    'reason': 'Every reviewed 983b source byte is retained; the remaining delta is main content already accepted by r4 and merged (#267, #268) plus deterministic catalog/traceability outputs checked by the generator, ci_lint and 82-view consistency (README rule: derived-output corrections are verified by the main controller).',
    'necessary_CI': 'pending', 'scientific_qualification': False})
print(json.dumps({'candidate': final['commit'], 'reviewed_source_paths_exact': len(source_paths), 'delta': len(delta), 'new_review_round_required': False}), flush=True)
