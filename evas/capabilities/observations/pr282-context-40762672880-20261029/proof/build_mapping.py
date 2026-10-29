"""E1 obligation mapping for PR #282 (capability batch 1), built from CI 40762672880 against the trusted context the
registration PR's current run will match (context 4, the PR6 context; host-only difference on the new pool).

Pairing, in order, without choosing outcomes:
  1. identity: same (owner, condition id) in old and E1;
  2. position-free identity: same owner, and the same condition record with the position fields removed
     (site.line, site.source_sha256, context[].line); these change when only the test file bytes change;
  3. order: the remaining conditions of one owner, when old and E1 have the same number, paired in report order.
Every old obligation must be paired. Preserved needs equal outcomes; any other outcome change is listed, not classified.
The result is replayed through the production mapped_obligations() of main d6b7543f.
Usage: python3 -I -B build_mapping.py   (writes e1-mapping.json and e1-mapping-summary.json here; refuses to overwrite)
"""
from collections import defaultdict
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess

R = Path(__file__).resolve().parent
MAIN = 'd6b7543fc815aaa584c886108691b6f2c01eb220'
RUN = '40762672880'
GIT = ['/usr/bin/git', '--no-lazy-fetch', '--git-dir=/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night']
ENV = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')} | {'GIT_OPTIONAL_LOCKS': '0'}
REVIEW = ('PR #282 r3 head 84d6b71f; independent review astra r2 (approved_with_nonblocking_findings, d1c930b6); '
          'Standards SL-SO-20261029-005; E1 = CI 40762672880 (coordinator 2026-10-29)')


def show(path):
    return subprocess.check_output(GIT + ['show', MAIN + ':' + path], env=ENV)


def load(name, raw):
    path = R / (name + '_d6b7543f.py')
    if not path.exists():
        path.write_bytes(raw)
    assert path.read_bytes() == raw, path
    spec = importlib.util.spec_from_file_location(name + '_d6', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = load('regression_gate', show('scripts/regression_gate.py'))
reg = load('regression_context_registration', show('scripts/regression_context_registration.py'))
baseline = json.loads(show('evas/validation/baselines/regression-v1.json'))
e1_raw = (R / ('ci-' + RUN) / 'python-regression.json').read_bytes()
e1 = json.loads(e1_raw)
e1_context = gate._context(e1)
contexts = baseline['contexts']
assert len(contexts) == 5, len(contexts)
# The context that differs from E1 only by criteria and host fields: the one the registration PR's current run matches.
def without(ctx, keys):
    c = copy.deepcopy(ctx)
    for k in keys:
        c.pop(k, None)
    return c
host_e1 = gate._host_split(without(e1_context, ['criteria_id']) | {'criteria_id': ''})
candidates = []
for i, entry in enumerate(contexts):
    trusted = gate._host_split(without(entry['context'], ['criteria_id']) | {'criteria_id': ''})
    if trusted is not None and host_e1 is not None and gate._json(trusted[0]) == gate._json(host_e1[0]):
        candidates.append(i)
assert candidates == [4], candidates
old = gate._expand_baseline_observations(contexts[4])
before, after = reg.observations(gate, old), reg.observations(gate, e1)


def position_free(cond):
    c = copy.deepcopy(cond)
    c.pop('id', None)
    c.pop('outcome', None)
    c.pop('message', None)
    site = c.get('site')
    if isinstance(site, dict):
        site.pop('line', None)
        site.pop('source_sha256', None)
    for frame in c.get('context') or []:
        if isinstance(frame, dict):
            frame.pop('line', None)
    return gate._json(c)


pairs, how = {}, {}
for key in before:
    if key in after:
        pairs[key] = key
        how[key] = 'identity'
used = set(pairs.values())
old_by_owner, new_by_owner = defaultdict(list), defaultdict(list)
for key in before:
    if key not in pairs:
        old_by_owner[key[0]].append(key)
for key in after:
    if key not in used:
        new_by_owner[key[0]].append(key)
for owner, olds in old_by_owner.items():
    news = new_by_owner.get(owner, [])
    free = defaultdict(list)
    for k in news:
        free[position_free(after[k])].append(k)
    rest = []
    for k in olds:
        bucket = free.get(position_free(before[k]))
        if bucket and len(bucket) == 1 and len([o for o in olds if position_free(before[o]) == position_free(before[k])]) == 1:
            pairs[k] = bucket.pop()
            how[k] = 'position-free'
        else:
            rest.append(k)
    remaining = [k for k in news if k not in set(pairs.values())]
    if rest and len(rest) == len(remaining):
        for a, b in zip(rest, remaining):
            pairs[a] = b
            how[a] = 'order'
unmapped = [list(k) for k in before if k not in pairs]
mapping, changes = [], []
for a, b in pairs.items():
    oa, ob = before[a]['outcome'], after[b]['outcome']
    item = {'old_owner': a[0], 'old_condition': a[1], 'old_signature_sha256': reg.digest(gate._retention_condition(before[a])),
            'new_owner': b[0], 'new_condition': b[1], 'new_signature_sha256': reg.digest(gate._retention_condition(after[b])),
            'classification': 'preserved', 'review_reference': REVIEW, 'attribution': None}
    if oa != ob:
        changes.append({'old': list(a), 'new': list(b), 'old_outcome': oa, 'new_outcome': ob, 'pairing': how[a]})
    mapping.append(item)
new_only = [list(k) for k in after if k not in set(pairs.values())]
counts = defaultdict(int)
for k in pairs:
    counts[how[k]] += 1
changed_owners = sorted({a[0] for a, b in pairs.items() if how[a] != 'identity'})
replay = None
if not unmapped and not changes:
    try:
        reg.mapped_obligations({'obligation_mapping': mapping}, gate, old, e1)
        replay = 'accepted by production mapped_obligations (d6b7543f)'
    except ValueError as error:
        replay = 'rejected: ' + str(error)
summary = {'run': RUN, 'e1_report_sha256': hashlib.sha256(e1_raw).hexdigest(), 'main': MAIN, 'old_context_index': 4,
           'old_obligations': len(before), 'e1_obligations': len(after), 'paired': len(pairs), 'pairing_counts': dict(counts),
           'unmapped_old': unmapped, 'outcome_changes': changes, 'new_only_count': len(new_only),
           'new_only_outcomes': dict(sorted({o: sum(1 for k in new_only if after[tuple(k)]['outcome'] == o) for o in {after[tuple(k)]['outcome'] for k in new_only}}.items())),
           'non_identity_owners': changed_owners, 'production_replay': replay}
for name, value in (('e1-mapping.json', mapping), ('e1-mapping-summary.json', summary), ('e1-new-only.json', new_only)):
    with (R / name).open('x') as fh:
        fh.write(json.dumps(value, indent=1, ensure_ascii=False) + '\n')
print(json.dumps({k: summary[k] for k in ('old_obligations', 'e1_obligations', 'paired', 'pairing_counts', 'new_only_count', 'new_only_outcomes', 'production_replay')}))
print('unmapped', len(unmapped), 'outcome changes', len(changes), 'non-identity owners', len(changed_owners))
