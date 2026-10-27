"""Exercise baseline_layout.py on the accepted E1 (CI 40584762318 attempt 1) and main 4d6ebc71, with negative controls.

Reads main's baseline, regression_gate.py and regression_context_registration.py from Git objects; writes only
layout-check/ in this directory (refuses an existing one). The entry uses placeholder provenance and review text of
PR5's size, so sizes are measurements, not the final entry; the governance stage repeats the checks on the real entry.
"""
from pathlib import Path
import copy, hashlib, importlib.util, json, os, subprocess, sys

D = Path(__file__).resolve().parent
B = D.parents[1]
OUT = D / 'layout-check'
MAIN = '4d6ebc71efea35822a28f2861f2b0a2a6db17e59'
GIT = ['/usr/bin/git', '--no-lazy-fetch', '--git-dir=/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night']
ENV = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')} | {'GIT_OPTIONAL_LOCKS': '0'}
LIMIT, WARN = 104857600, 50 * 1024 * 1024
E1 = B / 'pr6/e1-precheck-20261027/ci-40584762318/python-regression.json'
E1_SHA = '35d74e62f8933cb10c8f8298f5a65389fa56b1cd6faadb4f8a09108f14d3fa75'


def show(path): return subprocess.check_output(GIT + ['show', MAIN + ':' + path], env=ENV)
def sha(raw): return hashlib.sha256(raw).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


OUT.mkdir()
for name in ('regression_gate.py', 'regression_context_registration.py'):
    (OUT / name).write_bytes(show('scripts/' + name))
gate = module('layout_gate_main', OUT / 'regression_gate.py')
api = module('layout_api_main', OUT / 'regression_context_registration.py')
layout = module('baseline_layout_under_test', D / 'baseline_layout.py')
trusted_raw = show('evas/validation/baselines/regression-v1.json')
trusted = json.loads(trusted_raw)
assert len(trusted_raw) == 89943276 and len(trusted['contexts']) == 4
raw = E1.read_bytes()
assert sha(raw) == E1_SHA
pr5 = json.loads((B / 'pr5/context-registration-20261027/governance-draft/entry.json').read_text())
entry = gate.propose_baseline(json.loads(raw), dict(pr5['source_identity']), dict(pr5['review']))['contexts'][0]
head_raw = layout.line_per_context({'contexts': trusted['contexts'] + [entry], 'schema_version': trusted['schema_version']})
checks = layout.append_checks(trusted_raw, head_raw, entry, api.digest)
assert all(checks.values()), checks


def variant(name, mutate=None, data=None):
    doc = json.loads(head_raw)
    if mutate:
        mutate(doc)
        data = layout.line_per_context(doc)
    result = layout.append_checks(trusted_raw, data, entry, api.digest)
    failed = sorted(k for k, v in result.items() if not v)
    assert failed, name
    return {'case': name, 'failed_checks': failed}


def old_field(doc): doc['contexts'][1]['review']['reference'] += ' changed'
def swap(doc): doc['contexts'][0], doc['contexts'][1] = doc['contexts'][1], doc['contexts'][0]
def new_field(doc): doc['contexts'][-1]['review']['reference'] += ' changed'
def drop_old(doc): del doc['contexts'][2]
def extra(doc): doc['contexts'].append(copy.deepcopy(entry))
def version(doc): doc['schema_version'] = 2


negatives = [variant('old context field changed', old_field), variant('old contexts swapped', swap),
             variant('new entry field changed', new_field), variant('old context dropped', drop_old),
             variant('two contexts appended', extra), variant('schema_version changed', version),
             variant('indent2 layout of the same document', data=(json.dumps(json.loads(head_raw), indent=2, ensure_ascii=False) + '\n').encode()),
             variant('sorted-key compact layout of the same document', data=(json.dumps(json.loads(head_raw), sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()),
             variant('trailing newline added', data=head_raw + b'\n')]
indent2 = (json.dumps({'contexts': trusted['contexts'] + [entry], 'schema_version': 1}, indent=2, ensure_ascii=False) + '\n').encode()
assert json.dumps(trusted, indent=2, ensure_ascii=False).encode() + b'\n' == trusted_raw
line = len(json.dumps(entry, ensure_ascii=False, separators=(',', ':')).encode()) + 2
result = {'main': MAIN, 'e1': 'CI 40584762318 attempt 1', 'e1_report_sha256': E1_SHA,
          'module': str(D / 'baseline_layout.py'), 'module_sha256': sha((D / 'baseline_layout.py').read_bytes()),
          'entry_note': 'placeholder provenance/review text of PR5 size; the governance stage repeats these checks on the real entry',
          'checks': checks, 'negative_controls': negatives,
          'sizes': {'trusted_4ctx_indent2': len(trusted_raw), 'trusted_4ctx_line_per_context': len(layout.line_per_context(trusted)),
                    'append_5ctx_indent2': len(indent2), 'append_5ctx_line_per_context': len(head_raw), 'entry_compact_line': line},
          'limit_bytes': LIMIT, 'warning_bytes': WARN, 'indent2_exceeds_limit': len(indent2) >= LIMIT,
          'line_per_context_below_warning': len(head_raw) < WARN, 'further_appends_before_limit': (LIMIT - len(head_raw)) // line,
          'canonical': {'trusted': api.digest(trusted), 'entry': api.digest(entry),
                        'layout_invariant': api.digest(json.loads(layout.line_per_context(trusted))) == api.digest(trusted)}}
assert result['canonical']['layout_invariant']
(OUT / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k: result[k] for k in ('sizes', 'indent2_exceeds_limit', 'line_per_context_below_warning', 'further_appends_before_limit')}),
      len(negatives), 'negatives rejected', flush=True)
