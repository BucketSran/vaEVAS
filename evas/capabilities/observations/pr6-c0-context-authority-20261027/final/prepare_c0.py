"""Prepare the PR6 C0 authority on main 4d6ebc71: bundle intake and archive, exact governance, and the C0 candidate.

E1 is CI 40584762318 attempt 1 on PR6 head fa5556de, accepted by the coordinator under decision B (old runner pool,
runtime_profile equal to every trusted context; record pr6/e1-precheck-20261027/e1-acceptance.json). The current
context is #274's CI 40569530278 on main 4d6ebc71, an exact match of trusted context 3. The C0 candidate changes only
evas/validation/baselines/regression-v1.review.json (one appended authorization) and
scripts/context-registration-bundle.json (the bundle pointer), plus the generated catalog and traceability. The
baseline is unchanged here; the separate one-path baseline PR writes it with baseline_layout.line_per_context.

Stages write new receipts and refuse to replace them. Writable: this directory, Git objects and the private export.
No scientific test bodies, simulator, kernel or backend run here.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import fnmatch
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

D = Path(__file__).resolve().parent
B = D.parents[1]
S = D / 'source-c0'
R7 = B / 'pr6/rebind-r7-20261027'
SPLIT = B / 'catalog-split-build-r3-20261027'
WORKER = B / 'pr6/e1-bundle-sonnet-20261027'
E1A = B / 'pr6/e1-precheck-20261027/e1-acceptance.json'
BASE = '4d6ebc71efea35822a28f2861f2b0a2a6db17e59'
BASE_TREE = '33a1a097624a24d46dda3ec289b1d899280d7e18'
HEAD6 = 'fa5556de20de4fecbf9db4e3630cd5d6754b07c2'
HEAD6_TREE = '470ad588ddeb848b7c05d3f23656a96f085f8bfd'
RUN = 40584762318
MERGE = '253082c49e6b37155becf8ed2e40a899bf99c130'
E1_RAW_SHA = '35d74e62f8933cb10c8f8298f5a65389fa56b1cd6faadb4f8a09108f14d3fa75'
KERNEL_SHA = 'b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe'
KERNEL_GZIP = ('ae1cd723c5b24bd17af866805d7e6ac742cd8b86', 'evas/capabilities/observations/pr4-e1-40384473617/bundle/kernel_binary')
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
ARCHIVE_TIP = 'e89e1e1a261d171b7cf72e42650ed9c95b06b4de'
PREFIX_BUNDLE = 'evas/capabilities/observations/pr6-context-40584762318-20261027'
PREFIX_C0 = 'evas/capabilities/observations/pr6-c0-context-authority-20261027'
REVIEW_REPORT = B / 'night-coordination/pr6-exact-context-astra-r6-20261027/review-report.json'
REVIEWER = 'independent tcodex/gpt-6-astra, reasoningEffort max, serviceTier priority, fresh context'
AUTH_ID = 'pr6-support-views-CI40584762318'
OBSERVED = R7 / 'ci-40569530278/catalog-inventory/assets-before.json'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
DATA = 'evas/capabilities/data/'
WARNING_BYTES = 50 * 1024 * 1024
CRITERIA_PREFIXES = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
DUT_PREFIXES = ('evas/src/', 'evas/rust_core/')
COLLECTOR = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
             'scripts/regression_observation_policy.json', 'evas/capabilities/data/language-profile.json')
REVIEW_PATH = 'evas/validation/baselines/regression-v1.review.json'
POINTER_PATH = 'scripts/context-registration-bundle.json'
CAPTURE_PATHS = [REVIEW_PATH, POINTER_PATH]
IMMUTABLE = ['.github/workflows/numerical-assurance.yml', 'evas/validation/baselines/regression-v1.json',
             'scripts/run_trusted_regression_gate.py', 'scripts/regression_gate.py', 'scripts/regression_context_registration.py',
             'scripts/materialize_registration_bundle.py', 'scripts/run_regression.py', 'scripts/ci_evidence.py',
             'scripts/regression_reason_identity.py', 'scripts/regression_observation_policy.json']
AFFECTED_TESTS = ('test_context_registration.py', 'test_regression_admission.py', 'test_trusted_regression_gate.py',
                  'test_regression_gate.py', 'test_catalog_part_split.py', 'test_ci_selection.py', 'test_ci_inventory.py',
                  'test_fast_feedback.py', 'test_catalog_derived_outputs.py', 'test_catalog_history_selection.py')
CAPTURE_MESSAGE = 'Propose the exact context authority for the PR6 support views'
FINAL_MESSAGE = 'Bind the PR6 context authority to the generated catalog'
spec = importlib.util.spec_from_file_location('prior_c0_construction', B / 'pr4/post-review-integration-20261027/prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.S, task.OUT, task.BASE = S, D, BASE
PY = task.PY
git, write, sha = task.git, task.write, task.sha
r7 = None


def load(path): return json.loads(path.read_text())
def env(): return task.clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}


def module(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(s)
    sys.modules[name] = result
    s.loader.exec_module(result)
    return result


def build_helpers():
    """Guards, logged runs and catalog helpers of the accepted r7 build, pointed at this directory and export."""
    global r7
    if r7 is None:
        r7 = module('pr6_r7_build_helpers', R7 / 'prepare_pr6_r7.py')
        # r7 bound git/write/sha to its own helper instance, whose export is r7's; rebind every global its helpers use.
        r7.D, r7.S, r7.task, r7.PY = D, S, task, task.PY
        r7.git, r7.write, r7.sha = task.git, task.write, task.sha
        task.S, task.OUT, task.BASE = S, D, BASE
    return r7


def guard(): return build_helpers().guard()
def stable(g): return build_helpers().stable(g)


def invariant():
    guard()
    if (S / '.git').exists():
        for key in ('--absolute-git-dir', '--git-common-dir', '--show-toplevel'):
            assert Path(git('rev-parse', key, source=True).decode().strip()).resolve().is_relative_to(D.resolve())
    assert S.resolve().is_relative_to(D.resolve())


def apis():
    for name in ('regression_gate.py', 'regression_context_registration.py'):
        assert (S / 'scripts' / name).read_bytes() == git('show', BASE + ':scripts/' + name)
    return (module('pr6_c0_gate', S / 'scripts/regression_gate.py'),
            module('pr6_c0_api', S / 'scripts/regression_context_registration.py'))


def layout():
    return module('pr6_baseline_layout', D / 'baseline_layout.py')


def current():
    """#274's CI 40569530278 report on main 4d6ebc71, digest-checked by the worker and matched exactly to context 3."""
    row = load(D / 'bundle-intake.json')['current_report']
    p = Path(row['path'])
    assert sha(p.read_bytes()) == row['sha256']
    return load(p)


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', BASE], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pr6-c0'], cwd=S, env=build_helpers().private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    assert not git('status', '--porcelain=v1', source=True).strip()
    for path in IMMUTABLE + CAPTURE_PATHS:
        assert (S / path).read_bytes() == git('show', BASE + ':' + path), path
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'export': str(S), 'immutable_paths_equal_base': IMMUTABLE, 'before': before, 'after': after,
          'scientific_execution': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'export': str(S), 'base': BASE}), flush=True)


def intake():
    """Bind the worker's final rounds, the primary merge closure and the production evidence checks."""
    invariant()
    target = D / 'bundle-bound'
    assert not target.exists() and not (D / 'bundle-intake.json').exists()
    done = load(D / 'delegation-completed.json')
    assert done['status'] == 'completed' and not done['hasPendingChildRuns']
    assert (done['providerInstanceId'], done['model'], done['options']) == ('tclaude', 'claude-sonnet-5-5', [{'id': 'effort', 'value': 'high'}])
    top = load(WORKER / 'receipt.json')
    assert top['findings'] == 0 and top['open_gaps'] == [] and top['status']['structure_complete'] and top['guard_equal_before_after']
    for name, item in top['deliverables'].items():
        p = WORKER / name
        if p.is_file():
            assert sha(p.read_bytes()) == item['sha256'], name
    rounds = {k: Path(v) for k, v in top['final_rounds'].items()}
    receipt = load(rounds['bundle'] / 'receipt.json')
    verify = load(rounds['verify'] / 'verification.json')
    raw_verification = load(rounds['raw'] / 'raw-verification.json')
    ident = receipt['identity']
    assert (ident['head'], ident['tree'], ident['trusted_base'], ident['ci_run'], ident['attempt']) == (HEAD6, HEAD6_TREE, BASE, RUN, 1)
    assert ident['ci_merge_checkout'] == MERGE
    assert verify['all_checks_ok'] and not verify.get('failed') and len(verify['checks']) == 43
    assert sha((rounds['raw'] / 'raw-verification.json').read_bytes()) == receipt['raw_verification_sha256']
    rows = []
    for item in receipt['outputs']:
        p = rounds['bundle'] / item['path']
        assert p.is_file() and not p.is_symlink() and p.stat().st_size == item['bytes'] and sha(p.read_bytes()) == item['sha256'], item['path']
        rows.append(item)
    closure = load(D / 'merge-closure/merge-closure.json')
    assert closure['merge_commit'] == MERGE and closure['parents'] == [BASE, HEAD6] and closure['tree'] == HEAD6_TREE
    assert git('rev-list', '--parents', '-n', '1', MERGE).decode().split() == [MERGE, BASE, HEAD6]
    assert git('rev-parse', MERGE + '^{tree}').decode().strip() == HEAD6_TREE
    target.mkdir()
    for p in sorted((rounds['bundle'] / 'bundle').iterdir()):
        assert p.is_file() and not p.is_symlink()
        shutil.copyfile(p, target / p.name)
    files = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())} for p in sorted(target.iterdir())]
    assert len(files) == 10
    gate, api = apis()
    raw = (target / 'report.json').read_bytes()
    assert sha(raw) == E1_RAW_SHA
    new = json.loads(raw)
    current_path = WORKER / 'artifacts-274/python-regression-timings/python-regression.json'
    current_sha = sha(current_path.read_bytes())
    assert receipt['consumed_inputs'][str(current_path)]['sha256'] == current_sha == raw_verification['c274_raw_sha256']
    old = json.loads(current_path.read_text())
    baseline = load(S / api.BASELINE)
    assert gate.compare_report(old, baseline)['merge_allowed']
    matched, _ = gate._matching_contexts(baseline['contexts'], gate._context(old))
    assert len(matched) == 1 and api.encoded(matched[0]) == api.encoded(baseline['contexts'][3])
    assert api.encoded(matched[0]['context']) == api.encoded(gate._context(old)), 'current run must equal context 3 exactly, not only under (T)'
    rejection = gate.compare_report(new, baseline)
    assert rejection['differences'] == ['expected exactly one matching trusted baseline context'], rejection
    mapping_path = rounds['bundle'] / 'obligation-map-draft.json'
    mapping = load(mapping_path)
    assert len(mapping) == 7737 and all(row['classification'] == 'preserved' and row['attribution'] is None for row in mapping)
    api.mapped_obligations({'obligation_mapping': mapping}, gate, old, new)
    api.mapped_obligations({'obligation_mapping': mapping}, gate, gate._expand_baseline_observations(matched[0]), new)
    binding = load(rounds['bundle'] / 'bundle-byte-binding.json')
    provenance = copy.deepcopy(binding['entry_provenance_preview'])
    provenance['snapshot_reference'] = ('https://github.com/BucketSran/vaEVAS/tree/' + HEAD6 + '; actual CI merge ' + MERGE
                                        + ' (parents ' + BASE + ', ' + HEAD6 + '; tree ' + HEAD6_TREE + ') fetched and verified by the primary')
    blobs = {p.name: p.read_bytes() for p in target.iterdir() if p.name != 'report.json'}
    sub = gate.execution_subject(old)
    harness = {'artifacts': {role: {'sha256': sha(data)} for role, data in blobs.items()},
               'current_dut': {'manifest_sha256': sub['dut_files_sha256'], 'kernel_sha256': sub['kernel_sha256']},
               'e1': {'raw_sha256': sha(raw), 'execution_subject': gate.execution_subject(new)}}
    api.evidence(harness, blobs, gate, new, {'source_identity': provenance}, sub)
    assert sub['kernel_sha256'] == gate.execution_subject(new)['kernel_sha256'] == KERNEL_SHA
    proofs = [(D / 'merge-closure/merge-closure.json', 'proof/merge-closure.json'), (E1A, 'proof/e1-acceptance.json'),
              (D / 'bundle-intake.json', 'proof/bundle-intake.json'), (D / 'delegation-completed.json', 'worker/delegation-completed.json')]
    proofs += [(rounds['raw'] / name, 'proof/raw/' + name) for name in ('raw-verification.json', 'archive-download-manifest.json',
               'archive-members-verified.json', 'source-identity-field-bindings.json', 'admission-verification.json',
               'inventory-verification.json', 'condition-deltas.json') if (rounds['raw'] / name).is_file()]
    proofs += [(rounds['bundle'] / name, 'proof/' + name) for name in ('stream-boundaries.json', 'bundle-byte-binding.json',
               'obligation-map-draft.json', 'obligation-map-proof.json', 'receipt.json')]
    proofs += [(rounds['verify'] / 'verification.json', 'worker/verification.json')]
    proofs += [(WORKER / name, 'worker/' + name) for name in ('REPORT.md', 'receipt.json', 'raw-verification.json', 'brief.txt',
               'prepare_bundle.py', 'verify.py', 'raw_verify.py', 'common.py', 'intake.py')]
    for p, _ in proofs:
        assert p == D / 'bundle-intake.json' or p.is_file(), p
    write(D / 'bundle-intake.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'candidate': HEAD6, 'e1_run': RUN, 'worker_task': done['taskId'],
          'worker_model': {'providerInstanceId': done['providerInstanceId'], 'model': done['model'], 'options': done['options']},
          'worker_receipt': str(WORKER / 'receipt.json'), 'final_rounds': {k: str(v) for k, v in rounds.items()},
          'worker_failed_rounds_retained': top['failed_rounds'], 'worker_outputs_verified': rows, 'worker_checks': len(verify['checks']),
          'primary_merge_closure': str(D / 'merge-closure/merge-closure.json'), 'provenance': provenance, 'files': files,
          'current_report': {'path': str(current_path), 'sha256': current_sha, 'run': 40569530278,
                             'context': 'exact match of trusted context 3 (no host tolerance used)'},
          'mapping': {'path': str(mapping_path), 'sha256': sha(mapping_path.read_bytes()), 'rows': 7737, 'all_preserved': True},
          'primary_new_checks': ['production evidence() on the ten exact roles', 'mapped_obligations for all 7737 against the #274 report and the expanded context 3',
                                 'current report allowed and exactly equal to context 3; E1 rejected with the expected text on the unchanged baseline'],
          'metadata_correction': None, 'archive_copies': [[str(p), rel] for p, rel in proofs],
          'effective_authority': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'intake': 'bound', 'files': len(files), 'mapping': 7737, 'current_report': current_sha[:16]}), flush=True)


def bundle_archive():
    invariant()
    assert not (D / 'archive-data').exists() and not (D / 'bundle-archive.json').exists()
    assert build_helpers().remote_archive() == ARCHIVE_TIP
    intake_receipt = load(D / 'bundle-intake.json')
    root = D / 'archive-data'
    dest = root / PREFIX_BUNDLE
    bundle = dest / 'bundle'
    bundle.mkdir(parents=True)
    storage = []
    for item in intake_receipt['files']:
        data = (D / 'bundle-bound' / item['name']).read_bytes()
        assert sha(data) == item['sha256']
        encoding = 'identity'
        if item['name'] == 'kernel_binary':
            assert item['sha256'] == KERNEL_SHA
            data = git('show', KERNEL_GZIP[0] + ':' + KERNEL_GZIP[1])
            decoded = gzip.decompress(data)
            assert sha(decoded) == item['sha256'] and len(decoded) == item['bytes']
            encoding = 'gzip'
        (bundle / item['name']).write_bytes(data)
        storage.append({'name': item['name'], 'stored_bytes': len(data), 'stored_sha256': sha(data),
                        'materialized_bytes': item['bytes'], 'materialized_sha256': item['sha256'], 'encoding': encoding})
    kernel = {'encoding': 'gzip', 'decoded_bytes': 105862328, 'decoded_sha256': KERNEL_SHA}
    write(dest / 'storage.json', {'schema_version': 1, 'files': storage, 'kernel_binary': kernel, 'scientific_qualification': False,
          'codec': 'unchanged accepted schema2; the identical actual kernel reuses the prior single-member gzip'})
    for source_path, relative in intake_receipt['archive_copies']:
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
    (dest / 'README.md').write_text(
        '# PR6 observed context evidence\n\n'
        'PR6 head fa5556de, CI 40584762318 attempt 1 (checkout 253082c4, parents 4d6ebc71 and fa5556de, tree equal to the '
        'head tree). Nineteen jobs succeeded; trusted admission and the aggregate gate failed because the new criteria and '
        'collector context is not registered. All four regression shards ran on the old runner pool, and the context differs '
        'from every trusted context only in criteria_id and collector_sha256. The archive keeps the ten role files, the '
        'draft mapping of all 7737 conditions and their proofs. Exact context approval, the baseline append and activation '
        'remain pending. Scientific qualification is false.\n\n'
        'kernel_binary reuses the accepted single-member gzip of the identical actual kernel (see storage.json); the other '
        'nine role files keep their bytes.\n')
    index = D / 'bundle-archive.index'
    assert not index.exists()
    git('read-tree', ARCHIVE_TIP, index=index)
    files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        assert not path.is_symlink()
        data = path.read_bytes()
        assert len(data) < WARNING_BYTES, path
        rel = path.relative_to(root).as_posix()
        oid = git('hash-object', '-w', '--stdin', data=data).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + rel, index=index)
        files.append({'path': rel, 'sha256': sha(data), 'bytes': len(data), 'blob': oid})
    tree = git('write-tree', index=index).decode().strip()
    commit = git('commit-tree', tree, '-p', ARCHIVE_TIP, '-m', 'Archive PR6 observations for exact context registration').decode().strip()
    index.unlink()
    write(D / 'bundle-archive.json', {'commit': commit, 'tree': tree, 'parent': ARCHIVE_TIP, 'prefix': PREFIX_BUNDLE, 'files': files,
          'pointer': {'schema_version': 2, 'commit': commit, 'prefix': PREFIX_BUNDLE + '/bundle', 'kernel_binary': kernel},
          'published': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'bundle_archive': commit, 'files': len(files), 'published': False}), flush=True)


def governance():
    invariant()
    out = D / 'governance-draft'
    assert not out.exists()
    gate, api = apis()
    lay = layout()
    arc, intake_receipt = load(D / 'bundle-archive.json'), load(D / 'bundle-intake.json')
    target = D / 'bundle-bound'
    raw = (target / 'report.json').read_bytes()
    assert sha(raw) == E1_RAW_SHA
    new, old = json.loads(raw), current()
    baseline_raw = (S / api.BASELINE).read_bytes()
    baseline = json.loads(baseline_raw)
    review_raw = (S / api.REVIEW).read_bytes()
    prior_review = json.loads(review_raw)
    pointer_raw = (S / POINTER_PATH).read_bytes()
    # The repository files are indent-2 JSON; re-serializing them unchanged must reproduce their bytes.
    assert (json.dumps(prior_review, ensure_ascii=False, indent=2) + '\n').encode() == review_raw
    assert (json.dumps(json.loads(pointer_raw), ensure_ascii=False, indent=2) + '\n').encode() == pointer_raw
    url = 'https://raw.githubusercontent.com/BucketSran/vaEVAS/' + arc['commit'] + '/' + PREFIX_BUNDLE
    exact_reference = (str(REVIEW_REPORT) + '; PROPOSED exact decision, effective only after fresh independent acceptance of '
                       'these bytes and C0 authority merge; raw source proof: ' + url + '/proof/merge-closure.json')
    provenance = copy.deepcopy(intake_receipt['provenance'])
    provenance['raw_reference'] = url + '/bundle/report.json'
    provenance['snapshot_reference'] += '; ' + url + '/proof/merge-closure.json'
    proposed_review = {'status': 'approved', 'semantic_status': 'pending', 'reviewer': REVIEWER, 'reference': exact_reference}
    entry = gate.propose_baseline(new, provenance, proposed_review)['contexts'][0]
    original = load(Path(intake_receipt['mapping']['path']))
    assert sha(Path(intake_receipt['mapping']['path']).read_bytes()) == intake_receipt['mapping']['sha256'] and len(original) == 7737
    mapping = copy.deepcopy(original)
    for row in mapping:
        row['review_reference'] = exact_reference
    assert all({k: v for k, v in a.items() if k != 'review_reference'} == {k: v for k, v in b.items() if k != 'review_reference'}
               for a, b in zip(original, mapping))
    blobs = {p.name: p.read_bytes() for p in target.iterdir() if p.name != 'report.json'}
    assert len(blobs) == 9
    subject = gate.execution_subject(old)
    auth = {'schema_version': 1, 'id': AUTH_ID, 'action': 'append-one-criteria-collector-context',
            'old_baseline_canonical_sha256': api.digest(baseline), 'previous_context_sha256': api.digest(gate._context(old)),
            'new_entry_canonical_sha256': api.digest(entry),
            'current_dut': {'manifest_sha256': subject['dut_files_sha256'], 'kernel_sha256': subject['kernel_sha256']},
            'e1': {'raw_sha256': sha(raw), 'canonical_report_sha256': api.digest(new), 'execution_subject': gate.execution_subject(new),
                   'raw_source_sha256': api.digest(new['source_identity']), 'entry_source_sha256': api.digest(entry['source_identity']),
                   'entry_review_sha256': api.digest(entry['review'])},
            'artifacts': {role: {'sha256': sha(data), 'locator': url + '/bundle/' + role + (
                '; decode schema2 gzip per ' + url + '/storage.json' if role == 'kernel_binary' else '')} for role, data in sorted(blobs.items())},
            'obligation_mapping': mapping}
    auth['independent_review'] = {'decision': 'approved-exact-context-registration', 'reviewer': REVIEWER, 'reference': exact_reference,
                                  'entry_sha256': api.digest(entry), 'evidence_sha256': api.digest(auth['e1']),
                                  'mapping_sha256': api.digest(mapping), 'semantic_boundary': 'human-exact-review-not-JSON-authentication'}
    authority = copy.deepcopy(prior_review)
    authority.setdefault(api.GOVERNANCE, []).append(auth)
    assert authority[api.GOVERNANCE][:-1] == prior_review.get(api.GOVERNANCE, [])
    appended = copy.deepcopy(baseline)
    appended['contexts'].append(entry)
    result = api.validate_context_registration(gate, old, baseline, appended, authority, authority, [api.BASELINE], raw, blobs)
    assert result['merge_allowed'] and result['transition']['registration'] and not result['raw_successful'] and not result['semantic_qualification'], result
    negatives = []
    for name, trusted, head, raw_bytes, paths in [('HEAD-only authorization', prior_review, appended, raw, [api.BASELINE]),
                                                   ('changed raw', authority, appended, raw + b'\n', [api.BASELINE]),
                                                   ('second changed path', authority, appended, raw, [api.BASELINE, REVIEW_PATH])]:
        rejected = api.validate_context_registration(gate, old, baseline, head, trusted, authority, paths, raw_bytes, blobs)
        assert not rejected['merge_allowed']
        negatives.append({'case': name, 'differences': rejected['differences']})
    for name, mutate in [('changed old context', lambda doc: doc['contexts'][0]['review'].__setitem__('reference', doc['contexts'][0]['review']['reference'] + ' changed')),
                         ('swapped old contexts', lambda doc: doc['contexts'].__setitem__(slice(0, 2), doc['contexts'][1::-1])),
                         ('changed new entry', lambda doc: doc['contexts'][-1]['review'].__setitem__('reference', doc['contexts'][-1]['review']['reference'] + ' changed'))]:
        changed = copy.deepcopy(appended)
        mutate(changed)
        rejected = api.validate_context_registration(gate, old, baseline, changed, authority, authority, [api.BASELINE], raw, blobs)
        assert not rejected['merge_allowed']
        negatives.append({'case': name, 'differences': rejected['differences']})
    # The registration run's context must equal #274's old-pool context exactly (decision B; code lines 143-144, 388-390).
    other_pool = copy.deepcopy(old)
    other_pool['metadata']['runtime_profile']['variables']['ImageVersion'] += '-other-pool'
    rejected = api.validate_context_registration(gate, other_pool, baseline, appended, authority, authority, [api.BASELINE], raw, blobs)
    assert not rejected['merge_allowed']
    negatives.append({'case': 'registration run on another runner image (ImageVersion changed)', 'differences': rejected['differences']})
    baseline_head = lay.line_per_context(appended)
    layout_checks = lay.append_checks(baseline_raw, baseline_head, entry, api.digest)
    assert all(layout_checks.values()), layout_checks
    assert json.loads(baseline_head) == appended
    for name, value in [('entry.json', entry), ('authority.json', auth), ('review.json', authority), ('bundle-pointer.json', arc['pointer']),
                        ('validation.json', result), ('negative-controls.json', negatives)]:
        write(out / name, value)
    with (out / 'baseline-append.json').open('xb') as fh:
        fh.write(baseline_head)
    assert (out / 'review.json').read_bytes() == (json.dumps(authority, ensure_ascii=False, indent=2) + '\n').encode()
    write(out / 'receipt.json', {'kind': 'unadopted-exact-context-proposal', 'candidate': HEAD6, 'e1_run': RUN, 'trusted_base': BASE,
          'effective_authority': False, 'independent_exact_review': 'pending', 'review_destination': str(REVIEW_REPORT),
          'mapping': '7737 exact preserved; only review_reference updated', 'authorization_id': AUTH_ID,
          'context_count_before': len(baseline['contexts']), 'context_count_after': len(appended['contexts']),
          'old_baseline_canonical_sha256': api.digest(baseline), 'previous_context_sha256': auth['previous_context_sha256'],
          'entry_canonical_sha256': api.digest(entry), 'authority_canonical_sha256': api.digest(auth),
          'baseline_layout': {'module': str(D / 'baseline_layout.py'), 'module_sha256': sha((D / 'baseline_layout.py').read_bytes()),
                              'function': 'line_per_context', 'checks': layout_checks,
                              'trusted_bytes': len(baseline_raw), 'head_bytes': len(baseline_head), 'head_sha256': sha(baseline_head),
                              'limit_bytes': 104857600, 'warning_bytes': WARNING_BYTES},
          'e1_pool': 'old runner pool; runtime_profile equal to every trusted context; record ' + str(E1A),
          'old_contexts_unchanged': True, 'scientific_qualification': False,
          'files': {p.name: sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()}})
    invariant()
    print(json.dumps({'proposal': 'ready, not adopted', 'contexts': len(appended['contexts']), 'baseline_head_bytes': len(baseline_head),
                      'entry': api.digest(entry), 'negatives': len(negatives)}), flush=True)


def capture():
    invariant()
    proposal = load(D / 'governance-draft/receipt.json')
    assert not proposal['effective_authority'] and proposal['context_count_before'] == 4
    assert not (D / 'capture.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == BASE
    assert not git('status', '--porcelain=v1', source=True).strip()
    for name, path in (('review.json', REVIEW_PATH), ('bundle-pointer.json', POINTER_PATH)):
        data = (D / 'governance-draft' / name).read_bytes()
        assert sha(data) == proposal['files'][name]
        (S / path).write_bytes(data)
    assert sorted(git('diff', '--name-only', source=True).decode().splitlines()) == sorted(CAPTURE_PATHS)
    cap = task.make_commit(BASE, CAPTURE_PATHS, CAPTURE_MESSAGE + TRAILER, 'capture')
    git('read-tree', cap['commit'], source=True)
    git('update-ref', 'HEAD', cap['commit'], BASE, source=True)
    write(D / 'capture.json', cap)
    (D / 'source.patch').write_bytes(git('diff', '--binary', BASE, cap['commit']))
    (D / 'source.commit').write_bytes(git('cat-file', 'commit', cap['commit']))
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    before, after = task.entries(BASE), task.entries(cap['commit'])
    assert set(old_rows) == set(before) == set(after)
    rows, changed = [], []
    for path, (mode, oid) in sorted(after.items()):
        item = old_rows[path]
        if before[path] == (mode, oid):
            assert (item['git_mode'], item['observed_blob_oid'], item['index_blob_oid']) == (mode, oid, oid), path
            value, actual = item['sha256'], item['actual_mode']
        else:
            data = (S / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid
            value, actual = sha(data), (S / path).stat().st_mode & 0o777
            changed.append(path)
        rows.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual, 'git_blob_oid': oid})
    assert sorted(changed) == sorted(CAPTURE_PATHS)
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': cap['commit'], 'source_tree': cap['tree'], 'source_object_format': 'sha1',
          'source_kind': 'immutable-export', 'source_profile': 'git-tree-regular-blobs-v1',
          'source_availability': 'local-only-before-publication', 'content_binding': 'verified-git-blob-oids',
          'scope': observed['scope'], 'assets': rows,
          'reuse_proof': {'actual_CI': 40569530278, 'observation': str(OBSERVED), 'unchanged': len(rows) - len(changed), 'changed': changed}})
    rs = module('pr6_c0_runner', S / 'scripts/run_regression.py')
    old = current()
    criteria = rs.file_manifest(S, ('evas/tests', 'evas/validation', 'evas/examples', 'experiments'))
    dut = rs.file_manifest(S, ('evas/src', 'evas/rust_core'))
    assert criteria == old['source_identity']['criteria_files'] and dut == old['source_identity']['dut_files']
    for path in IMMUTABLE:
        assert (S / path).read_bytes() == git('show', BASE + ':' + path), path
    write(D / 'source-capture.json', {'base': BASE, 'source_capture': cap['commit'], 'paths': CAPTURE_PATHS,
          'criteria_id': rs.json_digest(criteria), 'criteria_files': len(criteria), 'dut_id': rs.json_digest(dut), 'dut_files': len(dut),
          'criteria_DUT_exact_current_context': True, 'unchanged_execution_and_trust_paths': IMMUTABLE, 'baseline_unchanged': True,
          'proposal': str(D / 'governance-draft/receipt.json'), 'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'capture': cap['commit'], 'paths': CAPTURE_PATHS}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(SPLIT / 'config.json')
    candidates = []
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates.append((path, value, config['discovery_source_locators'][value['entry']['entry_id']]))
    cap = load(D / 'capture.json')
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = cap['commit']
    inventory = module('pr6_c0_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(entries) == len(candidates) == 31, (len(entries), len(candidates))
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    chosen = []
    for entry in entries:
        start = entry['start'].rstrip('/') + '/'
        touched = [p for p in CAPTURE_PATHS if p.startswith(start) and fnmatch.fnmatch(p.rsplit('/', 1)[-1], entry['pattern'])]
        assert not touched, (entry['entry_id'], touched)
        matching = []
        for path, value, locator in candidates:
            r = value['receipt']
            if value['entry'] != entry or not r['complete'] or r['errors'] or r['unresolved_instances']:
                continue
            if assets.get(r['collector']['path']) != r['collector']['sha256']:
                continue
            if any(assets.get(m['module_path']) != m['module_sha256'] for m in r['methods']):
                continue
            matching.append((path, value, locator))
        assert len(matching) == 1, entry['entry_id']
        path, value, locator = matching[0]
        assert git('show', locator['revision'] + ':' + locator['path']) == path.read_bytes()
        git('merge-base', '--is-ancestor', locator['revision'], ARCHIVE_TIP)
        chosen.append({'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True, 'source_locator': locator,
                       'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances'],
                       'start': entry['start'], 'pattern': entry['pattern']})
    write(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen), 'new_collections': 0,
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the main (#274) construction receipts; the C0 changes no CI test file.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen), 'new_collections': 0}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    bundle = load(D / 'bundle-archive.json')
    parent = bundle['commit']
    git('merge-base', '--is-ancestor', ARCHIVE_TIP, parent)
    dest = D / 'archive-files' / PREFIX_C0
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'source-preparation.json', 'source-capture.json', 'discovery-selection.json'):
        shutil.copyfile(D / name, dest / name)
    for name in ('prepare_c0.py', 'baseline_layout.py', 'check_layout.py'):
        shutil.copyfile(D / name, dest / name)
    for source_path, relative in ((D / 'governance-draft/receipt.json', 'proposal-receipt.json'),
                                  (D / 'governance-draft/validation.json', 'proposal-validation.json'),
                                  (D / 'governance-draft/negative-controls.json', 'proposal-negative-controls.json'),
                                  (D / 'layout-check/result.json', 'layout-check-result.json'),
                                  (E1A, 'e1-acceptance.json'), (D / 'bundle-intake.json', 'bundle-intake.json')):
        shutil.copyfile(source_path, dest / relative)
    (dest / 'README.md').write_text(
        '# Exact PR6 context authority proposal\n\n'
        'The C0 candidate changes only the exact authority record and the bundle pointer, plus the generated catalog and '
        'traceability. It keeps main criteria, DUT, collector, baseline and workflow. All 31 Python discovery entries are '
        'reused by exact source identity; no new collection or scientific execution is represented. The authority fields '
        'are proposed bytes and take effect only after an independent exact review and the C0 merge. E1 ran on the old '
        'runner pool with a runtime_profile equal to every trusted context; the baseline PR must run there too. The '
        'baseline append and PR6 activation remain separate steps; the append uses baseline_layout.line_per_context.\n')
    idx = D / 'archive.index'
    assert not idx.exists()
    git('read-tree', parent, index=idx)
    files = []
    for p in sorted((D / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        assert not p.is_symlink()
        rel = p.relative_to(D / 'archive-files').as_posix()
        raw = p.read_bytes()
        assert len(raw) < WARNING_BYTES, (rel, len(raw))
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + rel, index=idx)
        files.append({'path': rel, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive PR6 C0 authority construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'commit': head, 'tree': tree, 'parent': parent, 'prefix': PREFIX_C0, 'files': files, 'published': False})
    config = load(SPLIT / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    for row in load(D / 'discovery-selection.json')['entries']:
        config['discoveries'].append({'entry_file': row['entry_file']})
        config['discovery_source_locators'][row['entry_id']] = row['source_locator']
    ids = {row['entry_id'] for row in load(D / 'discovery-selection.json')['entries']}
    for bridge in config['bridge_evidence']:
        assert set(bridge['consumer_entry_ids']) <= ids, bridge['path']
    write(D / 'config.json', config)
    invariant()
    print(json.dumps({'construction_archive': head, 'parent': parent, 'files': len(files)}), flush=True)


def generate():
    """Generate twice from the same inputs; the outputs must be byte-identical and keep every main object version."""
    invariant()
    h = build_helpers()
    assert load(D / 'config.json')['previous_data_dir'] == str(S / 'evas/capabilities/data')
    assert not (D / 'generation-acceptance.json').exists()
    for name in ('catalog', 'catalog-repeat'):
        with (D / ('generation-' + name + '.stdout')).open('xb') as out, (D / ('generation-' + name + '.stderr')).open('xb') as err:
            run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / 'config.json'),
                                  '--output', str(D / name)], cwd=S, env=env(), stdout=out, stderr=err)
        assert run.returncode == 0, 'Read generation-' + name + '.stderr'
    first, second = D / 'catalog/tree/evas/capabilities/data', D / 'catalog-repeat/tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(D / 'catalog/generation-report.json')
    previous, current_objects = task.objects(S / 'evas/capabilities/data'), task.objects(first)
    assert previous == h.objects_at(BASE)
    assert all(current_objects.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    header = load(first / 'registry.json')
    versions, prev_versions = {}, {}
    for (i, v) in current_objects:
        versions.setdefault(i, []).append(v)
    for (i, v) in previous:
        prev_versions.setdefault(i, []).append(v)
    problems = []
    for i, vs in versions.items():
        new = set(vs) - set(prev_versions.get(i, []))
        if len(new) > 1 or (new and header['current'].get(i) not in new):
            problems.append({'id': i, 'new_versions': sorted(new), 'current': header['current'].get(i)})
        if i in header['current'] and header['current'][i] not in vs:
            problems.append({'id': i, 'current_missing': header['current'][i]})
    assert not problems, problems[:5]
    paths = []
    for p in sorted(first.glob('*.json')):
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / 'evas/capabilities/data').glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = sorted(k for k in current_objects if k not in previous)
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
          'deterministic_double_generation': True, 'new_object_versions': len(new_objects), 'new_object_ids': sorted({k[0] for k in new_objects}),
          'version_lists': {'ids': len(versions), 'problems': 0, 'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
          'largest_data_file': max(sizes.items(), key=lambda x: x[1]), 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'new_object_versions': len(new_objects), 'old_versions_retained': len(previous)}), flush=True)


def derive():
    invariant()
    h = build_helpers()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    h.run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    h.run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    cap = load(D / 'capture.json')
    paths = h.changed_vs(cap['commit'])
    rendered = set(h.render_outputs(S))
    unexpected = sorted(set(paths) - rendered - h.DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write(D / 'derive-acceptance.json', {'capture_commit': cap['commit'], 'paths_vs_capture': paths, 'render_outputs': len(rendered),
          'checks': results, 'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_capture': paths}), flush=True)


def freeze():
    invariant()
    h = build_helpers()
    cap, der = load(D / 'capture.json'), load(D / 'derive-acceptance.json')
    assert not (D / 'final-candidate.json').exists()
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = h.changed_vs(cap['commit'])
    assert sorted(generated) == sorted(der['paths_vs_capture'])
    final = task.make_commit(cap['commit'], generated, FINAL_MESSAGE + TRAILER, 'final')
    complete = sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines())
    assert set(CAPTURE_PATHS) <= set(complete)
    # attempt-r1 also applied the prefix rule to the two capture paths; the review record sits under evas/validation/
    # but outside the criteria manifest, which capture() proved equal to the current context's.
    others = [p for p in complete if p not in CAPTURE_PATHS]
    assert not [p for p in others if p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR or p in IMMUTABLE], complete
    assert load(D / 'source-capture.json')['criteria_DUT_exact_current_context']
    assert set(complete) - set(CAPTURE_PATHS) <= h.DERIVED_DATA | set(h.render_outputs(S)), complete
    blobs, changed = [], set(complete)
    for line in git('ls-tree', '-r', '-l', final['commit']).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    final.update(base=BASE, capture=cap['commit'], complete_paths=complete, derive=str(D / 'derive-acceptance.json'),
                 large_unchanged_blobs=blobs, precheck='runs on the frozen head in parallel with CI',
                 review='pending: incremental priority Astra', CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', BASE, final['commit']))
    git('read-tree', final['commit'], source=True)
    git('update-ref', 'HEAD', final['commit'], source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'complete_paths': complete}), flush=True)


def precheck():
    invariant()
    h = build_helpers()
    final = load(D / 'final-candidate.json')
    assert not (D / 'precheck-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    results = []
    paths = final['complete_paths']
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths), 'focused': False,
          'scope': 'PR6 C0 authority and generated assets, quick maintenance gate; full scientific regression is CI only.'})
    h.run_logged('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')], results)
    h.run_logged('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'], results)
    h.run_logged('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], results)
    tools = {'PATH': str(Path.home() / '.cargo/bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')}
    for name in AFFECTED_TESTS:
        h.run_logged('affected-' + name.removesuffix('.py') + '.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', name, '-v'],
                     results, extra_env=tools)
    h.run_logged('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], results)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip(), 'checks changed committed bytes'
    write(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': paths,
          'checks': results, 'actual_registration_controls': str(D / 'governance-draft/validation.json'),
          'actual_registration_rejections': str(D / 'governance-draft/negative-controls.json'),
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def inventory():
    invariant()
    h = build_helpers()
    final = load(D / 'final-candidate.json')
    assert not (D / 'inventory-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    results = []
    out = D / 'catalog-inventory-local'
    h.run_logged('inventory-local.txt', [str(PY), '-B', 'scripts/capabilities/collect_ci_inventory.py', '--root', '.', '--output', str(out),
                                         '--require-catalog', '--registry-data', 'evas/capabilities/data'], results,
                 extra_env={'CI_INVENTORY_BASE': BASE, 'CI_INVENTORY_HEAD': final['commit']})
    summary = load(out / 'summary.json')
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], summary.get('errors')
    assert summary['source']['source_tree'] == final['tree']
    write(D / 'inventory-acceptance.json', {'candidate': final['commit'], 'tree': final['tree'], 'checks': results,
          'summary': {k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count', 'denominators')},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'inventory': 'reconciled', 'entries': summary['entry_count']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['source', 'intake', 'bundle_archive', 'governance', 'capture', 'discover', 'archive',
                                          'generate', 'derive', 'freeze', 'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()
