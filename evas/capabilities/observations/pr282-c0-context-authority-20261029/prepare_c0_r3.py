"""Rebuild the #282 C0 authority on main b4a07295 (#294 squashed onto the PR-A main 6fed3c82), local only, round 3.

Generated from prepare_c0_r2.py (unchanged) by make_prepare_c0_r3.py. Differences from round 2:
  1. Base b4a07295 / tree fa40153a, single parent 6fed3c82; #294 changes 988 paths, all under benchmark/material/draftbench.
     Its objects are in the shared store (proceed-checks.json: none missing), so no commit is rebuilt. The archive tip
     18a202cb and the bundle commit 2b2569c4 are still read through the round-2 alternates (r2a2, round-1 C0 repository).
  2. Gate before any stage: flow/c0-r3/proceed-checks.json (check_proceed_r3.py). It records the main session's decision
     (option A, 12:01:32Z): the coordinator's gate is met by push CI 40864041959; the main session's extra "every job
     success" condition is relaxed. It also holds the OBSERVED download checks, the empty context-key diff and the basis.
  3. bundle_archive and governance are unchanged in method: reuse 2b2569c4; governance must equal the round-1 draft byte
     for byte (old baseline ee87e18a, entry 556035ee, authority 15259b95), else it stops. The modules at b4a07295 must be
     PR-A's (registration 098f0f4a, gate 7a88c259).
  4. catalog_gate re-reads main's tip and the archive tip with gh api right before capture; catalog_end_gate re-reads them
     after freeze. Either moving stops the run.
  5. OBSERVED is push CI 40864041959's catalog-inventory (b4a07295). capture compares the criteria and DUT manifests with
     the report of main push CI 40857285671, which ran on 6fed3c82, not on BASE; they must be equal.
  6. The registration-run stand-in stays main 6fed3c82's push CI 40857285671 (new pool), with PR6's activation CI
     40614646318 as the second positive; local positive validation only, not part of the C0 bytes.
  7. RETENTION_REVS adds b4a07295 and keeps 6fed3c82. precheck stops the chain when a check fails.
Stages write new receipts under flow/c0-r3 and refuse to replace them. No scientific test bodies, simulator or kernel run.
Usage: python3 -B prepare_c0_r3.py <stage>   (discover/generate/derive/precheck/inventory need the 3.12 lint venv)
"""
import argparse
import copy
import fnmatch
import shutil
import traceback

from common_r3 import *

D = C0R3
S = D / 'source'
BUNDLE = FLOW / 'bundle-r1'
BASE, BASE_TREE = R3_MAIN, R3_MAIN_TREE
PREVIOUS_MAIN = NEW_MAIN  # 6fed3c82, the PR-A main; #294 (b4a07295) changes only benchmark/material/draftbench
PRA_GATE_SHA = '7a88c2596cba6d7036679be65076dbdf8bcdef4aebc03f6e76940a7aba10b7c1'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
ARCHIVE_TIP = ARCHIVE_TIP_R3  # gh api re-read 2026-10-29T13:11:01Z (r2/gh/archive-ref-r3-proceed.json); catalog_gate re-reads it
PREFIX_BUNDLE = 'evas/capabilities/observations/pr282-context-40762672880-20261029'
PREFIX_C0 = 'evas/capabilities/observations/pr282-c0-context-authority-20261029'
AUTH_ID = 'pr282-capability-batch1-CI40762672880'
# Confirmed by the main session for rounds 2 and 3 (unchanged rehearsal values; the string is the resolved path round 1 used).
REVIEW_REPORT = B / 'night-coordination/pr282-exact-context-astra-r1-20261029/review-report.json'
REVIEWER = 'independent tcodex/gpt-6-astra, reasoningEffort max, serviceTier priority, fresh context'
RAW_URL = 'https://raw.githubusercontent.com/' + REPO + '/'
# Registration-run stand-ins. Primary: main 6fed3c82's push CI 40857285671 (all four shards on the new pool, context 4 under
# the host rule, DUT D0, the PR-A code). Its head is 6fed3c82, not BASE: BASE b4a07295 changes no context-key path and no
# regression module reads benchmark/material/draftbench (c0-r3/proceed-checks.json: context_key_diff, replacement_basis).
# PR6's activation CI 40614646318 stays the second positive. Both have context 29edd5bf... and D0, so the authorization
# bytes do not depend on the choice; they are local positive validation only.
STANDIN = R2 / 'runs/main-push-40857285671-catalog/python-regression-timings/python-regression.json'
STANDIN_SHA = 'ab35087fe4aa79eb4538c0054822cc82334b9112a484353e770c9bd5a3d9c137'
STANDIN_ALT = B / 'pr6/rebind-r8-20261027/activation-ci/ci-40614646318/artifacts/python-regression-timings/python-regression.json'
STANDIN_ALT_SHA = 'e75c71e11604fd2d84da6e3f53f226d2f23efee9060032ea9cfc2301dd4ffd1a'
OLD_POOL_RUN = FLOW / 'runs/main-push-40635877195/python-regression-timings/python-regression.json'
OBSERVED = R3_PUSH_DIR / 'catalog-inventory/assets-before.json'  # push CI 40864041959 on b4a07295
PRA_CONFIG = B / 'registration-rule-dut-fix-impl-opus-20261029/r2a2/catalog-02/config.json'
REGISTRATION_CONTEXT_SHA = '29edd5bfcdb765b3ca7b11dcd7ba178b97879422757a4521d046dcafba16255c'
D0_KERNEL_GZIP = ('ae1cd723c5b24bd17af866805d7e6ac742cd8b86', 'evas/capabilities/observations/pr4-e1-40384473617/bundle/kernel_binary')
ROUND1_DRAFT = ROUND1_C0 / 'governance-draft'
EXPECTED = {'old_baseline': 'ee87e18aad3c64d8a63f0d2d65e6e656ce57b03a7932c547537de4178683de0b',
            'entry': '556035ee859fd2976c8a602552a649c7cf9aed08ff65b4bc7203dd804ad37540',
            'authority': '15259b95d19e920d16f575cb0fab9f7c7f06de95f9a5b1033ec56cdf144fd0d2'}
DATA = 'evas/capabilities/data/'
WARNING_BYTES = 50 * 1024 * 1024
LIMIT_BYTES = 100 * 1024 * 1024
CRITERIA_PREFIXES = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
DUT_PREFIXES = ('evas/src/', 'evas/rust_core/')
COLLECTOR = COLLECTOR4 + ('evas/capabilities/data/language-profile.json',)
PART_FILES = tuple([DATA + 'method-index-%02d.json' % i for i in range(16)] + [DATA + 'historical-index-%02d.json' % i for i in range(16)])
DERIVED_DATA = {DATA + 'registry.json', DATA + 'catalog-sources.json', DATA + 'asset-index.json', DATA + 'entrypoint-index.json',
                *PART_FILES, 'evas/docs/development/TRACEABILITY.md'}
CAPTURE_PATHS = [REVIEW_PATH, POINTER_PATH]
IMMUTABLE = ['.github/workflows/numerical-assurance.yml', BASELINE_PATH, 'scripts/run_trusted_regression_gate.py', 'scripts/regression_gate.py',
             'scripts/regression_context_registration.py', 'scripts/materialize_registration_bundle.py', 'scripts/run_regression.py',
             'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py', 'scripts/regression_observation_policy.json']
RETENTION_REVS = (('main', BASE), ('main_before_pr294', PREVIOUS_MAIN), ('main_before_pr_a', OLD_MAIN), ('main_before_pr273', 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'),
                  ('main_before_split', '02dee32b2c9b25f166cbd77f8a895953e004f288'))
CAPTURE_MESSAGE = 'Propose the exact context authority for the capability batch 1 observations'
FINAL_MESSAGE = 'Bind the capability batch 1 context authority to the generated catalog'
TOOLS = {'PATH': str(Path.home() / '.cargo/bin') + ':' + str(PY.parent) + ':/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',
         'CARGO_TARGET_DIR': str(R2 / 'cargo-target-r3'), 'CARGO_NET_OFFLINE': 'true', 'RUSTUP_AUTO_INSTALL': '0'}


def invariant():
    if (S / '.git').exists():
        for key in ('--absolute-git-dir', '--git-common-dir', '--show-toplevel'):
            assert Path(pgit(S, 'rev-parse', key).decode().strip()).resolve().is_relative_to(D.resolve())
    assert S.resolve().is_relative_to(D.resolve())


def guarded(name):
    return guard_record_r2('c0r3-' + name)['observed_at']


def show(rev, path):
    return pgit(S, 'show', rev + ':' + path)


def changed_vs(rev):
    pgit(S, 'add', '--intent-to-add', '--', '.')
    paths = pgit(S, 'diff', '--no-renames', '--name-only', rev).decode().splitlines()
    pgit(S, 'reset', '--quiet')
    return paths


def objects_dir(path):
    header = json.loads((path / 'registry.json').read_text())
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads((path / part).read_text())['objects']
    return {(item['id'], item['version']): item for item in result}


def objects_at(rev):
    header = json.loads(show(rev, DATA + 'registry.json'))
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads(show(rev, DATA + part))['objects']
    return {(item['id'], item['version']): item for item in result}


def render_outputs(root):
    sys.path.insert(0, str(root / 'evas/capabilities'))
    try:
        renderer = module('flow_r2_render_' + sha(str(root).encode())[:8], root / 'evas/capabilities/render.py')
        files = renderer.outputs(renderer.registry())
    finally:
        sys.path.pop(0)
    return sorted(Path(p).resolve().relative_to(root.resolve()).as_posix() for p in files)


def logged(name, argv, results, extra_env=None, limit=3000):
    rc = run_logged(D / name, argv, S, results, extra_env=extra_env, limit=limit)
    assert rc == 0, name
    return rc


def source():
    before = guarded('source-before')
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    proceed = load(D / 'proceed-checks.json')
    assert proceed['proceed'] and proceed['base'] == BASE and proceed['context_key_diff']['empty'], 'run check_proceed_r3.py first'
    assert proceed['observed']['ok'] and proceed['observed']['observation']['sha256'] == sha_file(OBSERVED)[0]
    pra = load(C0R2 / 'pr-a-checks.json')
    assert pra['check_0_2']['ok'] and pra['collector_pr282_equals_new_main']
    S.mkdir(parents=True)
    r = subprocess.run([GIT, '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=', '--initial-branch=pr282-c0-r3'],
                       cwd=S, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    (S / '.git/objects/info/alternates').write_text(''.join(str(p) + '\n' for p in ALTERNATES))
    assert rgit('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE, 'b4a07295 must be in the shared store itself'
    assert pgit(S, 'rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    assert pgit(S, 'rev-list', '--parents', '-n', '1', BASE).decode().split()[1:] == [PREVIOUS_MAIN]
    with (D / 'export-source.stderr').open('xb') as err:
        producer = subprocess.Popen([GIT, '--no-lazy-fetch', '--git-dir=' + str(S / '.git'), 'archive', BASE], env=private_env(),
                                    stdout=subprocess.PIPE, stderr=err, cwd=D)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=private_env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    pgit(S, 'read-tree', BASE)
    pgit(S, 'update-ref', 'HEAD', BASE)
    pgit(S, 'update-index', '-q', '--refresh', check=False)
    invariant()
    assert not pgit(S, 'status', '--porcelain=v1').strip()
    for path in IMMUTABLE + CAPTURE_PATHS:
        assert (S / path).read_bytes() == show(BASE, path) == show(PREVIOUS_MAIN, path), path
    write_r3(D / 'source-preparation.json', {'prepared_at_utc': utc(), 'base': BASE, 'base_tree': BASE_TREE, 'base_parents': [PREVIOUS_MAIN],
             'export': str(S), 'private_git': str(S / '.git'), 'alternates': [str(p) for p in ALTERNATES],
             'base_objects': 'shared store: every object of b4a07295 present (proceed-checks.json shared_store_objects_of_base); no commit rebuilt',
             'proceed_checks': str(D / 'proceed-checks.json'), 'proceed_checks_sha256': sha_file(D / 'proceed-checks.json')[0],
             'immutable_paths_equal_base_and_previous_main': IMMUTABLE + CAPTURE_PATHS, 'guard_before': before,
             'guard_after': guarded('source-after'), 'scientific_execution': False})
    print(json.dumps({'export': str(S), 'base': BASE}), flush=True)


def bundle_archive():
    """Reuse the round-1 bundle commit 2b2569c4 unchanged and prove it again from this repository."""
    invariant()
    assert not (D / 'bundle-archive.json').exists()
    old = load(ROUND1_C0 / 'bundle-archive.json')
    assert old['commit'] == BUNDLE_ARCHIVE and old['parent'] == '0b485dd319e46058bd78672943458e025183baea'
    assert pgit(S, 'rev-list', '--parents', '-n', '1', BUNDLE_ARCHIVE).decode().split()[1:] == [old['parent']]
    assert pgit(S, 'rev-parse', BUNDLE_ARCHIVE + '^{tree}').decode().strip() == old['tree']
    listed = {}
    for item in pgit(S, 'ls-tree', '-r', '-z', BUNDLE_ARCHIVE, '--', PREFIX_BUNDLE).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            listed[path.decode()] = meta.decode().split()[2]
    assert listed == {f['path']: f['blob'] for f in old['files']}
    pgit(S, 'merge-base', '--is-ancestor', old['parent'], ARCHIVE_TIP)
    assert not pgit(S, 'ls-tree', ARCHIVE_TIP, '--', PREFIX_BUNDLE).strip(), 'archive tip already has the bundle prefix'
    binding = load(BUNDLE / 'bundle-byte-binding.json')
    check_dir = D / 'materialize-check'
    check_dir.mkdir()
    (check_dir / 'bundle-pointer.json').write_bytes(dump(old['pointer']))
    gate, reg, code = production_r2(S, BASE)
    run = subprocess.run([sys.executable, '-I', code['directory'] + '/materialize_registration_bundle.py', '--repo', str(S),
                          '--manifest', str(check_dir / 'bundle-pointer.json'), '--output', str(check_dir / 'bundle')],
                         cwd=check_dir, env=private_env(), capture_output=True)
    (check_dir / 'materialize.stdout').write_bytes(run.stdout)
    (check_dir / 'materialize.stderr').write_bytes(run.stderr)
    assert run.returncode == 0, run.stdout.decode() + run.stderr.decode()
    for item in binding['files']:
        assert sha_file(check_dir / item['path'])[0] == item['sha256'], item['path']
    write_r3(D / 'bundle-archive.json', dict(old, reused=True, original_receipt=str(ROUND1_C0 / 'bundle-archive.json'),
             original_receipt_sha256=sha_file(ROUND1_C0 / 'bundle-archive.json')[0], archive_tip_now=ARCHIVE_TIP,
             relation='sibling of the archive tip (both children of 0b485dd3); the construction archive merges them',
             materializer_check={'tool': 'main b4a07295 scripts/materialize_registration_bundle.py', 'sha256': code['materialize_registration_bundle.py'],
                                 'roles_equal_bundle': 10, 'receipt': str(check_dir)}, object_store=str(ROUND1_REPO), published=False))
    print(json.dumps({'bundle_archive': BUNDLE_ARCHIVE, 'reused': True, 'files': len(listed)}), flush=True)


def governance():
    invariant()
    out = D / 'governance-draft'
    assert not out.exists()
    started = utc()
    gate, reg, code = production_r2(S, BASE)
    assert code['regression_context_registration.py'] == PRA_REGISTRATION_SHA and code['regression_gate.py'] == PRA_GATE_SHA, code
    lay = module('flow_r2_baseline_layout', FLOW / 'baseline_layout.py')
    arc, binding = load(D / 'bundle-archive.json'), load(BUNDLE / 'bundle-byte-binding.json')
    raw = (BUNDLE / 'bundle/report.json').read_bytes()
    assert sha(raw) == E1_RAW_SHA
    e1 = json.loads(raw)
    current_raw = STANDIN.read_bytes()
    assert sha(current_raw) == STANDIN_SHA
    current = json.loads(current_raw)
    alt_raw = STANDIN_ALT.read_bytes()
    assert sha(alt_raw) == STANDIN_ALT_SHA
    alternative = json.loads(alt_raw)
    old_pool = json.loads(OLD_POOL_RUN.read_bytes())
    assert reg.digest(gate._context(current)) == REGISTRATION_CONTEXT_SHA == reg.digest(gate._context(alternative))
    alt_subject = gate.execution_subject(alternative)
    assert (alt_subject['dut_files_sha256'], alt_subject['kernel_sha256']) == (D0_DUT, D0_KERNEL)
    baseline_raw = (S / BASELINE_PATH).read_bytes()
    baseline = json.loads(baseline_raw)
    review_raw = (S / REVIEW_PATH).read_bytes()
    prior_review = json.loads(review_raw)
    pointer_raw = (S / POINTER_PATH).read_bytes()
    assert (json.dumps(prior_review, ensure_ascii=False, indent=2) + '\n').encode() == review_raw
    assert (json.dumps(json.loads(pointer_raw), ensure_ascii=False, indent=2) + '\n').encode() == pointer_raw
    assert lay.line_per_context(baseline) == baseline_raw
    url = RAW_URL + arc['commit'] + '/' + PREFIX_BUNDLE
    exact_reference = (str(REVIEW_REPORT) + '; PROPOSED exact decision, effective only after fresh independent acceptance of these bytes and '
                       'C0 authority merge; raw source proof: ' + url + '/proof/download-manifest.json')
    provenance = copy.deepcopy(binding['entry_provenance_preview'])
    provenance['raw_reference'] = url + '/bundle/report.json'
    provenance['snapshot_reference'] += '; ' + url + '/proof/download-manifest.json'
    proposed_review = {'status': 'approved', 'semantic_status': 'pending', 'reviewer': REVIEWER, 'reference': exact_reference}
    entry = gate.propose_baseline(e1, provenance, proposed_review)['contexts'][0]
    mapping_raw = (W / 'e1-mapping.json').read_bytes()
    assert sha(mapping_raw) == E1_MAPPING_SHA
    mapping = json.loads(mapping_raw)
    blobs = {role: (BUNDLE / 'bundle' / role).read_bytes() for role in ROLES}
    subject = gate.execution_subject(current)
    assert (subject['dut_files_sha256'], subject['kernel_sha256']) == (D0_DUT, D0_KERNEL)
    auth = {'schema_version': 1, 'id': AUTH_ID, 'action': 'append-one-criteria-collector-context',
            'old_baseline_canonical_sha256': reg.digest(baseline), 'previous_context_sha256': reg.digest(gate._context(current)),
            'new_entry_canonical_sha256': reg.digest(entry),
            'current_dut': {'manifest_sha256': subject['dut_files_sha256'], 'kernel_sha256': subject['kernel_sha256']},
            'e1': {'raw_sha256': sha(raw), 'canonical_report_sha256': reg.digest(e1), 'execution_subject': gate.execution_subject(e1),
                   'raw_source_sha256': reg.digest(e1['source_identity']), 'entry_source_sha256': reg.digest(entry['source_identity']),
                   'entry_review_sha256': reg.digest(entry['review'])},
            'artifacts': {role: {'sha256': sha(data), 'locator': url + '/bundle/' + role + (
                '; decode schema2 gzip per ' + url + '/storage.json' if role == 'kernel_binary' else '')} for role, data in sorted(blobs.items())},
            'obligation_mapping': mapping}
    auth['independent_review'] = {'decision': 'approved-exact-context-registration', 'reviewer': REVIEWER, 'reference': exact_reference,
                                  'entry_sha256': reg.digest(entry), 'evidence_sha256': reg.digest(auth['e1']),
                                  'mapping_sha256': reg.digest(mapping), 'semantic_boundary': 'human-exact-review-not-JSON-authentication'}
    reg.authorization(auth)
    digests = {'old_baseline': reg.digest(baseline), 'entry': reg.digest(entry), 'authority': reg.digest(auth)}
    if digests != EXPECTED:
        write_r3(D / 'governance-digest-mismatch.json', {'at_utc': utc(), 'expected': EXPECTED, 'actual': digests})
        raise SystemExit('governance digests differ from the round-1 draft; stop and report: ' + json.dumps(digests))
    authority = copy.deepcopy(prior_review)
    authority.setdefault(reg.GOVERNANCE, []).append(auth)
    assert authority[reg.GOVERNANCE][:-1] == prior_review.get(reg.GOVERNANCE, [])
    appended = copy.deepcopy(baseline)
    appended['contexts'].append(entry)

    def validate(report=current, head=appended, trusted=authority, paths=(BASELINE_PATH,), raw_bytes=raw, artifact_blobs=blobs):
        return reg.validate_context_registration(gate, report, baseline, head, trusted, authority, list(paths), raw_bytes, artifact_blobs)

    production_result = validate()
    assert production_result['merge_allowed'] and production_result['transition'].get('registration'), production_result['differences']
    assert not production_result['raw_successful'] and not production_result['semantic_qualification']
    alternative_result = validate(report=alternative)
    assert alternative_result['merge_allowed'] and alternative_result['transition'].get('registration'), alternative_result['differences']
    other_image = copy.deepcopy(current)
    other_image['metadata']['runtime_profile']['variables']['ImageVersion'] += '-other-pool'
    import gzip
    d0_kernel = gzip.decompress(pgit(S, 'show', D0_KERNEL_GZIP[0] + ':' + D0_KERNEL_GZIP[1]))
    assert sha(d0_kernel) == D0_KERNEL
    cases = [('HEAD-only authorization', dict(trusted=prior_review)), ('changed raw', dict(raw_bytes=raw + b'\n')),
             ('second changed path', dict(paths=(BASELINE_PATH, REVIEW_PATH)))]
    for label, index in (('changed old context', 0), ('changed new entry', -1)):
        doc = copy.deepcopy(appended)
        doc['contexts'][index]['review']['reference'] += ' changed'
        cases.append((label, dict(head=doc)))
    swapped = copy.deepcopy(appended)
    swapped['contexts'][0:2] = swapped['contexts'][1::-1]
    cases.append(('swapped old contexts', dict(head=swapped)))
    cases += [('registration run on another runner image (ImageVersion changed)', dict(report=other_image)),
              ('registration run on the old pool (real main push CI 40635877195)', dict(report=old_pool)),
              ('E1 itself as the registration run', dict(report=e1)),
              ('kernel_binary role carries the D0 kernel bytes (PR4 archive gzip)', dict(artifact_blobs=dict(blobs, kernel_binary=d0_kernel)))]
    del d0_kernel
    negatives = []
    for label, change in cases:
        result = validate(**change)
        assert not result['merge_allowed'], label
        negatives.append({'case': label, 'differences': result['differences']})
    baseline_head = lay.line_per_context(appended)
    layout_checks = lay.append_checks(baseline_raw, baseline_head, entry, reg.digest)
    assert all(layout_checks.values()), layout_checks
    assert json.loads(baseline_head) == appended
    for name, value in (('entry.json', entry), ('authority.json', auth), ('review.json', authority), ('bundle-pointer.json', arc['pointer']),
                        ('validation-production.json', production_result), ('validation-production-alt-standin.json', alternative_result),
                        ('negative-controls.json', negatives)):
        write_r3(out / name, value)
    write_r3(out / 'baseline-append.json', baseline_head)
    identical = {name: sha_file(out / name)[0] == sha_file(ROUND1_DRAFT / name)[0]
                 for name in ('entry.json', 'authority.json', 'review.json', 'bundle-pointer.json', 'baseline-append.json')}
    if not all(identical.values()):
        write_r3(D / 'governance-bytes-mismatch.json', {'at_utc': utc(), 'identical': identical})
        raise SystemExit('governance bytes differ from the round-1 draft; stop and report: ' + json.dumps(identical))
    review_after = len((out / 'review.json').read_bytes())
    sizes = {'regression-v1.json': {'before_c0': len(baseline_raw), 'after_c0': len(baseline_raw), 'after_baseline_pr': len(baseline_head)},
             'regression-v1.review.json': {'before_c0': len(review_raw), 'after_c0': review_after, 'after_baseline_pr': review_after},
             'limit_80MiB_bytes': MIB80}
    over = [name for name, row in sizes.items() if isinstance(row, dict) and max(row.values()) > MIB80]
    if over:
        write_r3(D / 'size-stop.json', {'at_utc': utc(), 'sizes': sizes, 'over_80MiB': over})
        raise SystemExit('a registration file is predicted above 80 MiB; stop and report: ' + repr(over))
    collector = {}
    for path in COLLECTOR4:
        head_raw, main_raw = pgit(S, 'show', HEAD282 + ':' + path), show(BASE, path)
        collector[path] = {'pr282_head_sha256': sha(head_raw), 'new_main_sha256': sha(main_raw), 'equal': head_raw == main_raw}
    assert all(row['equal'] for row in collector.values()), collector
    assert sha(pgit(S, 'show', HEAD282 + ':' + COLLECTOR[-1])) == sha(show(BASE, COLLECTOR[-1]))
    files = {p.name: sha_file(p)[0] for p in sorted(out.iterdir()) if p.is_file()}
    write_r3(out / 'receipt.json', {
        'kind': 'unadopted-exact-context-proposal (round 3, main b4a07295)', 'started_at_utc': started, 'finished_at_utc': utc(), 'candidate': HEAD282,
        'e1_run': E1_RUN, 'trusted_base': BASE, 'effective_authority': False, 'independent_exact_review': 'pending',
        'review_destination': str(REVIEW_REPORT), 'reviewer_text': REVIEWER, 'reviewer_and_destination_status': 'confirmed by the main session 2026-10-29 (rounds 2 and 3)',
        'mapping': 'main session e1-mapping.json used unchanged (7737 preserved, attribution null, its own review_reference)',
        'authorization_id': AUTH_ID, 'context_count_before': len(baseline['contexts']), 'context_count_after': len(appended['contexts']),
        'old_baseline_canonical_sha256': auth['old_baseline_canonical_sha256'], 'previous_context_sha256': auth['previous_context_sha256'],
        'previous_context': 'context 4 with the new-pool host fields (stand-ins: main 6fed3c82 push CI 40857285671 and PR6 activation CI 40614646318); binds the baseline PR run to the new pool',
        'entry_canonical_sha256': auth['new_entry_canonical_sha256'], 'authority_canonical_sha256': reg.digest(auth),
        'evidence_sha256': auth['independent_review']['evidence_sha256'], 'mapping_sha256': auth['independent_review']['mapping_sha256'],
        'current_dut': auth['current_dut'], 'e1_dut': {'manifest_sha256': E1_DUT, 'kernel_sha256': E1_KERNEL},
        'equal_to_round1_draft': {'canonical': {k: digests[k] == EXPECTED[k] for k in EXPECTED}, 'bytes': identical,
                                  'round1_draft': str(ROUND1_DRAFT), 'round1_receipt_sha256': sha_file(ROUND1_DRAFT / 'receipt.json')[0]},
        'production_validation': {'module': code['regression_context_registration.py'], 'gate': code['regression_gate.py'], 'revision': BASE,
                                  'merge_allowed': production_result['merge_allowed'], 'transition': production_result['transition'],
                                  'differences': production_result['differences'], 'authorization_id': production_result.get('authorization_id'),
                                  'added_entry_sha256': production_result.get('added_entry_sha256'),
                                  'registration_run_standin': {'path': str(STANDIN), 'sha256': STANDIN_SHA, 'run': MAIN_PUSH_RUN, 'head': PREVIOUS_MAIN, 'head_is_base': False,
                                                               'basis': str(D / 'proceed-checks.json') + ' (context_key_diff, replacement_basis)',
                                                               'pool': 'new (7.0.0-1017, ImageVersion 20261026.354.1)'},
                                  'second_standin': {'path': str(STANDIN_ALT), 'sha256': STANDIN_ALT_SHA, 'run': 40614646318,
                                                     'merge_allowed': alternative_result['merge_allowed'],
                                                     'differences': alternative_result['differences']}},
        'negative_controls': len(negatives), 'negative_controls_all_rejected': True,
        'file_sizes': sizes, 'collector_rule': {'rule': 'until PR-B merges, the four collector files of #282 must equal the new main byte for byte',
                                                'files': collector, 'language_profile_equal': True},
        'baseline_layout': {'module': str(FLOW / 'baseline_layout.py'), 'module_sha256': sha_file(FLOW / 'baseline_layout.py')[0], 'checks': layout_checks,
                            'trusted_bytes': len(baseline_raw), 'head_bytes': len(baseline_head), 'head_sha256': sha(baseline_head),
                            'head_above_50MiB_warning': len(baseline_head) >= WARNING_BYTES, 'head_below_100MiB_limit': len(baseline_head) < LIMIT_BYTES},
        'old_contexts_unchanged': True, 'scientific_qualification': False, 'files': files})
    print(json.dumps({'proposal': 'identical to round 1', 'digests': digests, 'production_merge_allowed': production_result['merge_allowed'],
                      'negatives': len(negatives), 'sizes': sizes, 'collector_equal': True}), flush=True)


def tips(label):
    main_tip = gh_save('repos/%s/branches/main' % REPO, R2 / ('gh/main-branch-r3-' + label + '.json'))['commit']['sha']
    archive_tip = gh_save('repos/%s/git/ref/heads/codex/evas-method-audit-archive-20261025' % REPO,
                          R2 / ('gh/archive-ref-r3-' + label + '.json'))['object']['sha']
    return {'at_utc': utc(), 'main': main_tip, 'archive_tip': archive_tip, 'expected_main': BASE, 'expected_archive_tip': ARCHIVE_TIP,
            'ok': main_tip == BASE and archive_tip == ARCHIVE_TIP, 'base_used': BASE,
            'records': [str(R2 / ('gh/main-branch-r3-' + label + '.json')), str(R2 / ('gh/archive-ref-r3-' + label + '.json'))]}


def catalog_gate():
    """Main session rule: read main's tip with gh api right before the catalog stages; stop unless it is BASE (archive tip too)."""
    assert not (D / 'catalog-gate.json').exists()
    record = tips('catalog-gate')
    write_r3(D / 'catalog-gate.json', dict(record, rule='before capture/discover/union/archive/generate: main must be b4a07295 and the '
                                           'archive tip 18a202cb, else stop and report'))
    if not record['ok']:
        raise SystemExit('main or the archive tip moved before the catalog stages; stop and report: ' + json.dumps(record))
    print(json.dumps(record), flush=True)


def catalog_end_gate():
    """After freeze: main and the archive tip must still be the values the catalog was built on."""
    assert not (D / 'catalog-end-gate.json').exists()
    record = tips('catalog-end')
    write_r3(D / 'catalog-end-gate.json', dict(record, rule='a move while the catalog stages ran means stop and report'))
    if not record['ok']:
        raise SystemExit('main or the archive tip moved during the catalog stages; stop and report: ' + json.dumps(record))
    print(json.dumps(record), flush=True)


def capture():
    invariant()
    assert load(D / 'catalog-gate.json')['ok'], 'run catalog_gate first'
    proposal = load(D / 'governance-draft/receipt.json')
    assert not proposal['effective_authority'] and proposal['context_count_before'] == 5
    assert not (D / 'capture.json').exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == BASE
    assert not pgit(S, 'status', '--porcelain=v1').strip()
    for name, path in (('review.json', REVIEW_PATH), ('bundle-pointer.json', POINTER_PATH)):
        data = (D / 'governance-draft' / name).read_bytes()
        assert sha(data) == proposal['files'][name]
        (S / path).write_bytes(data)
    assert sorted(changed_vs(BASE)) == sorted(CAPTURE_PATHS)
    cap = commit_paths_r3(S, BASE, CAPTURE_PATHS, CAPTURE_MESSAGE, [BASE], 'capture')
    pgit(S, 'reset', '--quiet', cap['commit'])
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == cap['commit']
    assert not pgit(S, 'status', '--porcelain=v1').strip()
    write_r3(D / 'capture.json', cap)
    write_r3(D / 'source.patch', pgit(S, 'diff', '--binary', BASE, cap['commit']))
    write_r3(D / 'source.commit', pgit(S, 'cat-file', 'commit', cap['commit']))
    observed = load(OBSERVED)
    assert observed['source_commit'] == BASE and observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    before, after = entries(S, BASE), entries(S, cap['commit'])
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
    write_r3(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
             'source_commit': cap['commit'], 'source_tree': cap['tree'], 'source_object_format': 'sha1',
             'source_kind': 'immutable-export', 'source_profile': 'git-tree-regular-blobs-v1',
             'source_availability': 'local-only-before-publication', 'content_binding': 'verified-git-blob-oids',
             'scope': observed['scope'], 'assets': rows,
             'reuse_proof': {'actual_CI': R3_PUSH_RUN, 'observation': str(OBSERVED), 'observation_sha256': sha_file(OBSERVED)[0],
                             'unchanged': len(rows) - len(changed), 'changed': changed}})
    rs = module('flow_r2_runner', S / 'scripts/run_regression.py')
    criteria = rs.file_manifest(S, ('evas/tests', 'evas/validation', 'evas/examples', 'experiments'))
    dut = rs.file_manifest(S, ('evas/src', 'evas/rust_core'))
    main_report_raw = STANDIN.read_bytes()
    assert sha(main_report_raw) == STANDIN_SHA
    main_report = json.loads(main_report_raw)
    assert criteria == main_report['source_identity']['criteria_files'] and dut == main_report['source_identity']['dut_files']
    for path in IMMUTABLE:
        assert (S / path).read_bytes() == show(BASE, path), path
    write_r3(D / 'source-capture.json', {'base': BASE, 'source_capture': cap['commit'], 'paths': CAPTURE_PATHS,
             'criteria_id': rs.json_digest(criteria), 'criteria_files': len(criteria), 'dut_id': rs.json_digest(dut), 'dut_files': len(dut),
             'criteria_DUT_equal_main_push_CI_40857285671': True,
             'compared_report': {'run': MAIN_PUSH_RUN, 'head': PREVIOUS_MAIN, 'head_is_base': False, 'path': str(STANDIN), 'sha256': STANDIN_SHA},
             'note': 'push CI 40857285671 ran on 6fed3c82, not on BASE b4a07295; #294 changes no criteria, DUT, language-profile or collector '
                     'file (proceed-checks.json context_key_diff is empty), and the manifests computed on this tree equal that report\'s',
             'unchanged_execution_and_trust_paths': IMMUTABLE, 'baseline_unchanged': True,
             'proposal': str(D / 'governance-draft/receipt.json'), 'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'capture': cap['commit'], 'paths': CAPTURE_PATHS}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(PRA_CONFIG)
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
    inventory = module('flow_r2_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    found = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(found) == len(candidates) == 31, (len(found), len(candidates))
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    chosen = []
    for entry in found:
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
        assert show(locator['revision'], locator['path']) == path.read_bytes()
        pgit(S, 'merge-base', '--is-ancestor', locator['revision'], ARCHIVE_TIP)
        chosen.append({'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True, 'source_locator': locator,
                       'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances'],
                       'start': entry['start'], 'pattern': entry['pattern']})
    write_r3(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen), 'new_collections': 0,
             'workflow_sha256': parsed['workflow_sha256'], 'archive_tip_checked': ARCHIVE_TIP, 'candidates_config': str(PRA_CONFIG),
             'candidates_config_sha256': sha_file(PRA_CONFIG)[0],
             'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from PR-A\'s final construction config (30 PR273 r4 receipts '
                            'plus PR-A\'s recollected scripts/tests entry); the C0 changes no CI test file.',
             'test_bodies_executed': False, 'scientific_qualification': False})
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen), 'new_collections': 0}), flush=True)


def union():
    invariant()
    union_dir = D / 'previous-union'
    assert not union_dir.exists() and not (D / 'union-acceptance.json').exists()
    union_dir.mkdir()
    header = json.loads(show(BASE, DATA + 'registry.json'))
    for name in ['registry.json', *header['object_parts']]:
        (union_dir / name).write_bytes(show(BASE, DATA + name))
    merged = objects_dir(union_dir)
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
        retention[name] = {'revision': rev, 'objects': len(expected)}
    assert merged == objects_dir(S / 'evas/capabilities/data')
    write_r3(D / 'union-acceptance.json', {'previous': BASE, 'union_dir': str(union_dir), 'union_objects': len(merged), 'retention': retention,
             'scientific_qualification': False})
    print(json.dumps({'union_objects': len(merged)}), flush=True)


def archive():
    """Construction archive: a merge of the archive tip 18a202cb and the reused bundle commit 2b2569c4, plus the C0 receipts."""
    invariant()
    assert not (D / 'archive.json').exists()
    bundle = load(D / 'bundle-archive.json')
    dest = D / 'archive-files' / PREFIX_C0
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'source-preparation.json', 'source-capture.json', 'discovery-selection.json',
                 'union-acceptance.json', 'assets.json', 'base-checks.json', 'proceed-checks.json', 'catalog-gate.json', 'bundle-archive.json'):
        shutil.copyfile(D / name, dest / name)
    for path in (R2 / 'prepare_c0_r3.py', R2 / 'common_r3.py', R2 / 'common_r2.py', R2 / 'check_pr_a.py', R2 / 'check_base_r3.py',
                 R2 / 'check_proceed_r3.py', FLOW / 'common.py', FLOW / 'baseline_layout.py', FLOW / 'check_baseline.py',
                 FLOW / 'bundle_e1.py', C0R2 / 'pr-a-checks.json'):
        shutil.copyfile(path, dest / path.name)
    for source_path, relative in ((D / 'governance-draft/receipt.json', 'proposal-receipt.json'),
                                  (D / 'governance-draft/validation-production.json', 'proposal-validation-production.json'),
                                  (D / 'governance-draft/negative-controls.json', 'proposal-negative-controls.json'),
                                  (W / 'e1-registration-record.json', 'e1-registration-record.json'),
                                  (BUNDLE / 'bundle-intake.json', 'bundle-intake.json')):
        shutil.copyfile(source_path, dest / relative)
    (dest / 'README.md').write_text(
        '# Exact capability batch 1 (#282) context authority proposal\n\n'
        'The C0 candidate on main b4a07295 (#294, benchmark/ only, on the PR-A main 6fed3c82) changes only the exact authority '
        'record and the bundle pointer, plus the '
        'generated catalog. It keeps main criteria, DUT, collector, baseline and workflow. All 31 Python discovery entries are '
        'reused by exact source identity; no new collection or scientific execution is represented. The authority fields are '
        'proposed bytes and take effect only after an independent exact review and the C0 merge. E1 ran on the new runner pool on '
        '#282\'s own DUT; PR-A records the registration run (D0) and E1 (D1) separately, and main\'s production registration check '
        'accepts this proposal (proposal-validation-production.json). The authority binds the new-pool current context, so the '
        'baseline PR must run there too.\n')
    index = R2 / 'indexes' / 'r3-construction-archive.index'
    assert not index.exists()
    index.parent.mkdir(exist_ok=True)
    pgit(S, 'read-tree', ARCHIVE_TIP, index=index)
    merged_bundle = []
    for item in pgit(S, 'ls-tree', '-r', '-z', BUNDLE_ARCHIVE, '--', PREFIX_BUNDLE).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            pgit(S, 'update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path.decode(), index=index)
            merged_bundle.append(path.decode())
    files = []
    root = D / 'archive-files'
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        assert len(raw) < WARNING_BYTES, (p, len(raw))
        rel = p.relative_to(root).as_posix()
        oid = pgit(S, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
        pgit(S, 'update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + rel, index=index)
        files.append({'path': rel, 'sha256': sha(raw), 'bytes': len(raw), 'blob': oid})
    tree = pgit(S, 'write-tree', index=index).decode().strip()
    commit = pgit(S, 'commit-tree', tree, '-p', ARCHIVE_TIP, '-p', BUNDLE_ARCHIVE, '-m',
                  'Archive the capability batch 1 C0 authority construction on main b4a07295' + TRAILER).decode().strip()
    index.unlink()
    for anc in (ARCHIVE_TIP, BUNDLE_ARCHIVE):
        pgit(S, 'merge-base', '--is-ancestor', anc, commit)
    assert not pgit(S, 'diff', '--name-only', ARCHIVE_TIP, commit, '--', ':!' + PREFIX_BUNDLE, ':!' + PREFIX_C0).strip()
    write_r3(D / 'archive.json', {'commit': commit, 'tree': tree, 'parents': [ARCHIVE_TIP, BUNDLE_ARCHIVE], 'prefix': PREFIX_C0, 'files': files,
             'bundle_paths_from_2b2569c4': len(merged_bundle), 'published': False, 'object_store': str(S / '.git'),
             'publication': 'fast-forward of ' + ARCHIVE_REF + ' from ' + ARCHIVE_TIP + ' (first parent); the publication archive is its child'})
    config = load(PRA_CONFIG)
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(D / 'previous-union'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    for row in load(D / 'discovery-selection.json')['entries']:
        config['discoveries'].append({'entry_file': row['entry_file']})
        config['discovery_source_locators'][row['entry_id']] = row['source_locator']
    ids = {row['entry_id'] for row in load(D / 'discovery-selection.json')['entries']}
    for bridge in config['bridge_evidence']:
        assert set(bridge['consumer_entry_ids']) <= ids, bridge['path']
    write_r3(D / 'config.json', config)
    print(json.dumps({'construction_archive': commit, 'parents': [ARCHIVE_TIP, BUNDLE_ARCHIVE], 'files': len(files)}), flush=True)


def generate():
    invariant()
    assert load(D / 'config.json')['previous_data_dir'] == str(D / 'previous-union')
    assert not (D / 'generation-acceptance.json').exists()
    env = env_py() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    for name in ('catalog', 'catalog-repeat'):
        with (D / ('generation-' + name + '.stdout')).open('xb') as out, (D / ('generation-' + name + '.stderr')).open('xb') as err:
            run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / 'config.json'),
                                  '--output', str(D / name)], cwd=S, env=env, stdout=out, stderr=err)
        assert run.returncode == 0, 'Read generation-' + name + '.stderr'
    first, second = D / 'catalog/tree/evas/capabilities/data', D / 'catalog-repeat/tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(D / 'catalog/generation-report.json')
    previous, current = objects_dir(D / 'previous-union'), objects_dir(first)
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = objects_at(rev)
        missing = [list(k) for k in expected if k not in current]
        rewritten = [list(k) for k, v in expected.items() if k in current and current[k] != v]
        assert not missing and not rewritten, (name, len(missing), len(rewritten))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': 0}
    header = load(first / 'registry.json')
    inline_before = {o['id']: o for o in json.loads((S / DATA / 'registry.json').read_text())['objects']}
    inline_after = {o['id']: o for o in header['objects']}
    assert all(inline_after.get(k) == v for k, v in inline_before.items()), 'hand-written registry objects changed'
    versions, prev_versions = {}, {}
    for (i, v) in current:
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
        target = S / DATA / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / DATA).glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = [k for k in current if k not in previous]
    by_kind = {}
    for k in new_objects:
        kind = current[k].get('kind', 'unknown')
        by_kind[kind] = by_kind.get(kind, 0) + 1
    largest = max(sizes.items(), key=lambda x: x[1])
    write_r3(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
             'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind, 'new_object_ids': sorted({k[0] for k in new_objects}),
             'deterministic_double_generation': True, 'hand_written_registry_objects_unchanged': len(inline_before),
             'version_lists': {'ids': len(versions), 'problems': 0, 'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
             'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes, 'largest_data_file': largest,
             'scientific_qualification': False})
    print(json.dumps({'generated_paths': len(paths), 'new_object_versions': len(new_objects), 'by_kind': by_kind, 'largest': largest}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    logged('traceability-generate.txt', [PY, '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    logged('capability-render.txt', [PY, '-B', 'evas/capabilities/render.py'], results)
    cap = load(D / 'capture.json')
    paths = changed_vs(cap['commit'])
    rendered = set(render_outputs(S))
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write_r3(D / 'derive-acceptance.json', {'capture_commit': cap['commit'], 'paths_vs_capture': paths, 'render_outputs': len(rendered),
             'checks': results, 'files': {p: sha_file(S / p)[0] for p in sorted(paths) if (S / p).is_file()},
             'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'paths_vs_capture': paths}), flush=True)


def freeze():
    invariant()
    cap, der = load(D / 'capture.json'), load(D / 'derive-acceptance.json')
    assert not (D / 'final-candidate.json').exists()
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha_file(S / path)[0] == value for path, value in der['files'].items())
    generated = changed_vs(cap['commit'])
    assert sorted(generated) == sorted(der['paths_vs_capture'])
    final = commit_paths_r3(S, cap['commit'], generated, FINAL_MESSAGE, [cap['commit']], 'final')
    complete = sorted(pgit(S, 'diff', '--no-renames', '--name-only', BASE, final['commit']).decode().splitlines())
    assert set(CAPTURE_PATHS) <= set(complete)
    others = [p for p in complete if p not in CAPTURE_PATHS]
    assert not [p for p in others if p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR or p in IMMUTABLE], complete
    assert set(others) <= DERIVED_DATA | set(render_outputs(S)), complete
    blobs, changed = [], set(complete)
    for line in pgit(S, 'ls-tree', '-r', '-l', final['commit']).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    final.update(base=BASE, capture=cap['commit'], complete_paths=complete, derive=str(D / 'derive-acceptance.json'),
                 large_unchanged_blobs=blobs, precheck='runs on the frozen head', review='pending: incremental priority Astra', CI='pending',
                 published=False, scientific_qualification=False)
    write_r3(D / 'final-candidate.json', final)
    write_r3(D / 'candidate.patch', pgit(S, 'diff', '--binary', BASE, final['commit']))
    pgit(S, 'reset', '--quiet', final['commit'])
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == final['commit']
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'complete_paths': complete}), flush=True)


def precheck():
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'precheck-acceptance.json').exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == final['commit']
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    guard_start = guarded('precheck-before')
    results, failures = [], []
    paths = final['complete_paths']
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write_r3(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths), 'focused': False,
             'scope': '#282 C0 authority on main b4a07295: quick maintenance gate plus every static-checks traceability step command; full scientific regression is CI only.'})
    fixtures = D / 'git-fixture-isolation'
    assert not fixtures.exists(), 'GIT_FIXTURE_RETAIN_DIR must not exist before the run'
    static_env = TOOLS | {'GIT_FIXTURE_RETAIN_DIR': str(fixtures)}
    steps = [('maintenance-fast-checks.txt', [PY, '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')], TOOLS),
             ('capability-views.txt', [PY, '-B', 'evas/capabilities/render.py', '--check'], TOOLS),
             ('static-1-traceability-check.txt', [PY, '-B', 'scripts/traceability.py', '--check', '--catalog-data', 'evas/capabilities/data'], static_env),
             ('static-2-diagnostic-inventory-check.txt', [PY, '-B', 'scripts/diagnostic_inventory.py', '--check'], static_env),
             ('static-3-verify-validation-version.txt', [PY, '-B', 'scripts/verify_validation_version.py'], static_env),
             ('static-4-scripts-tests-full.txt', [PY, '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-v'], static_env),
             ('static-5-capabilities-tests.txt', [PY, '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], static_env),
             ('diff-check.txt', ['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], {})]
    for name, argv, extra in steps:
        rc = run_logged(D / name, argv, S, results, extra_env=extra, limit=3000)
        if rc:
            failures.append(name)
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip(), 'checks changed committed bytes'
    fixture_files = sorted(p.relative_to(fixtures).as_posix() for p in fixtures.rglob('*') if p.is_file()) if fixtures.exists() else []
    write_r3(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': paths,
             'checks': results, 'failures': failures, 'git_fixture_retain_dir': str(fixtures), 'git_fixture_files': fixture_files,
             'environment_note': 'lint venv python 3.12 (CI 3.12.15); TMPDIR is the macOS default under /var/folders; Rust offline, no auto-install',
             'guard_before': guard_start, 'guard_after': guarded('precheck-after'), 'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'checks': len(results), 'failures': failures}), flush=True)
    if failures:
        raise SystemExit('precheck failures; stop and report (do not change benchmark/): ' + ', '.join(failures))


def inventory():
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'inventory-acceptance.json').exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == final['commit']
    results = []
    out = D / 'catalog-inventory-local'
    logged('inventory-local.txt', [PY, '-B', 'scripts/capabilities/collect_ci_inventory.py', '--root', '.', '--output', str(out),
                                   '--require-catalog', '--registry-data', 'evas/capabilities/data'], results,
           extra_env={'CI_INVENTORY_BASE': BASE, 'CI_INVENTORY_HEAD': final['commit']})
    summary = load(out / 'summary.json')
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], summary.get('errors')
    assert summary['source']['source_tree'] == final['tree']
    write_r3(D / 'inventory-acceptance.json', {'candidate': final['commit'], 'tree': final['tree'], 'checks': results,
             'summary': {k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count', 'denominators')},
             'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'inventory': 'reconciled', 'entries': summary['entry_count']}), flush=True)


STAGES = ['source', 'bundle_archive', 'governance', 'catalog_gate', 'capture', 'discover', 'union', 'archive', 'generate', 'derive',
          'freeze', 'catalog_end_gate', 'precheck', 'inventory']

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=STAGES)
    stage = parser.parse_args().stage
    kernel_slot(stage)
    try:
        globals()[stage]()
    except BaseException:
        write_r3(D / ('failure-' + stage + '-' + utc().replace(':', '') + '.json'), {'stage': stage, 'at_utc': utc(), 'traceback': traceback.format_exc()})
        raise
