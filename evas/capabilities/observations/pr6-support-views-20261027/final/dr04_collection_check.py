"""DR-04 evidence: compare actual CI collection before and after batch 5 (read-only; no test bodies run)."""
from pathlib import Path
from datetime import datetime, timezone
import collections
import fnmatch
import hashlib
import json
import os
import subprocess

R = Path(__file__).resolve().parent
B = R.parents[1]
GD = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night')
BEFORE = {'commit': 'e10e1af5796f0cc7af3b6b5f5d26c420c0c03325', 'CI': 40429826545,
          'dir': B / 'pr4/post-review-integration-20261027/catalog-index-recovery-20261027/ci-40429826545/raw-intake-grok/artifacts/catalog-inventory'}
AFTER = {'commit': 'ac1b6e8d8de743b8da3f862c0f50bdf0a1a1ca14', 'CI': 40473087175,
         'dir': B / 'pr5/context-registration-20261027/pr266-rebind-20261027/ci-40473087175/artifacts/catalog-inventory'}
ENV = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def inventory(side):
    entries = {}
    for p in sorted(side['dir'].glob('entry-*.json')):
        v = json.loads(p.read_text())
        entries[v['entry']['entry_id']] = {'file': str(p), 'sha256': sha(p), 'entry': v['entry'], 'receipt': v['receipt']}
    summary = json.loads((side['dir'] / 'summary.json').read_text())
    return entries, summary


def tree_files(commit):
    out = subprocess.check_output(['/usr/bin/git', '--no-lazy-fetch', f'--git-dir={GD}', 'ls-tree', '-r', '--name-only', '-z', commit], env=ENV)
    return [p for p in out.decode().split('\0') if p]


result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'actual CI catalog-inventory receipts; collection only, no test bodies',
          'before': {k: (str(v) if isinstance(v, Path) else v) for k, v in BEFORE.items()},
          'after': {k: (str(v) if isinstance(v, Path) else v) for k, v in AFTER.items()}}
sides = {}
for name, side in (('before', BEFORE), ('after', AFTER)):
    entries, summary = inventory(side)
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], name
    per_ns = collections.defaultdict(set)
    defs = {}
    zero, dup_within, incomplete = [], [], []
    for eid, e in entries.items():
        r = e['receipt']
        ids = [m['runtime_id'] for m in r['methods']]
        if r['discovered_instances'] == 0 or not ids:
            zero.append(eid)
        dups = [i for i, c in collections.Counter(ids).items() if c > 1]
        if dups:
            dup_within.append({'entry_id': eid, 'duplicates': dups})
        if not r['complete'] or r['errors'] or r['unresolved_instances']:
            incomplete.append(eid)
        for m in r['methods']:
            per_ns[r['namespace']].add(m['runtime_id'])
            defs[(r['namespace'], m['runtime_id'])] = (m['definition']['path'], m['definition']['name'], m['definition']['sha256'])
    sides[name] = {'entries': entries, 'per_ns': per_ns, 'defs': defs}
    result[name].update(entry_count=len(entries), summary_flags={k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count')},
                        zero_collection_entries=zero, within_entry_duplicates=dup_within, incomplete_entries=incomplete,
                        methods_per_namespace={ns: len(s) for ns, s in sorted(per_ns.items())})
    assert not zero and not dup_within and not incomplete, name
b, a = sides['before'], sides['after']
result['entries_added'] = [{'entry_id': eid, 'start': a['entries'][eid]['entry']['start'], 'pattern': a['entries'][eid]['entry']['pattern'],
                            'instances': a['entries'][eid]['receipt']['discovered_instances']} for eid in sorted(a['entries'].keys() - b['entries'].keys())]
result['entries_removed'] = sorted(b['entries'].keys() - a['entries'].keys())
changes = {}
for ns in sorted(set(b['per_ns']) | set(a['per_ns'])):
    old, new = b['per_ns'].get(ns, set()), a['per_ns'].get(ns, set())
    removed, added = sorted(old - new), sorted(new - old)
    new_by_def = {a['defs'][(ns, i)]: i for i in added}
    mapped = [{'old': i, 'new': new_by_def[b['defs'][(ns, i)]]} for i in removed if b['defs'][(ns, i)] in new_by_def]
    unmapped = [i for i in removed if b['defs'][(ns, i)] not in new_by_def]
    changes[ns] = {'before': len(old), 'after': len(new), 'removed': removed, 'added_count': len(added),
                   'added_modules': sorted({a['defs'][(ns, i)][0] for i in added}), 'renamed_same_definition': mapped, 'removed_without_mapping': unmapped}
result['method_changes'] = changes
# Missing collection: tracked test modules that no actual CI entry collects.
after_modules = {m['module_path'] for e in a['entries'].values() for m in e['receipt']['methods']}
candidates = [p for p in tree_files(AFTER['commit']) if fnmatch.fnmatch(p.rsplit('/', 1)[-1], 'test*.py')]
uncovered = sorted(p for p in candidates if p not in after_modules)
result['tracked_test_modules'] = len(candidates)
result['collected_test_modules'] = len(after_modules)
result['uncollected_tracked_test_modules'] = uncovered
result['uncollected_by_top_directory'] = dict(collections.Counter('/'.join(p.split('/')[:2]) for p in uncovered))
before_modules = {m['module_path'] for e in b['entries'].values() for m in e['receipt']['methods']}
result['modules_collected_before_but_not_after'] = sorted(before_modules - after_modules)
result['scientific_qualification'] = False
(R / 'dr04-collection-check.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'before_entries': result['before']['entry_count'], 'after_entries': result['after']['entry_count'],
                  'entries_added': [(e['start'], e['pattern'], e['instances']) for e in result['entries_added']], 'entries_removed': result['entries_removed'],
                  'per_ns': {ns: (c['before'], c['after'], len(c['removed']), c['added_count'], len(c['removed_without_mapping'])) for ns, c in changes.items()},
                  'modules_lost': result['modules_collected_before_but_not_after'], 'uncollected': len(uncovered),
                  'uncollected_by_dir': result['uncollected_by_top_directory']}, ensure_ascii=False))
