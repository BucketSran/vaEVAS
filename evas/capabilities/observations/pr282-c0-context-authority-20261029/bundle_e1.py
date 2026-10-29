"""Compose the ten-role registration bundle of E1 (CI 40762672880 attempt 1, #282 head 84d6b71f) from its original
artifact bytes, then test it with the production code of main d6b7543f.

Inputs: e1/ (fetch_e1.py: every zip equal to its API digest), the shared Git objects (read only), main's trusted
baseline, W/e1-mapping.json (the main session's mapping, used unchanged), and two real registration-run stand-ins:
  - PR6 activation CI 40614646318 (head 64fc1d39): all four shards on the new pool, matched context 4 under the host
    rule, DUT and kernel D0. Closest real stand-in for the baseline PR's own run on the new pool.
  - main d6b7543f push CI 40635877195: old pool, exact context 4, D0.
Differences from PR6's worker (pr6/e1-bundle-sonnet-20261027/prepare_bundle.py), each for a #282 fact:
  - E1 is a workflow_dispatch run on the head itself, so the snapshot is the head tree 84d6b71f (no merge closure);
  - E1's DUT and kernel are #282's (7713308b / 3353bed8), not D0; PR6 asserted equality, here it is recorded and the
    production consequences are tested (V1-V3 below) instead of assumed;
  - the kernel is E1's own (shard artifacts), stored schema-2 gzip (no earlier archive holds this kernel);
  - the mapping is the main session's e1-mapping.json, replayed, not rebuilt.
Writes only the new directory given (under W/flow). Never executes the kernel or any test.
Usage: python3 -B bundle_e1.py OUTPUT_NAME
"""
import copy
import gzip
import io
import traceback

from common import *

A = F / 'e1/artifacts'
STANDINS = {
    'pr6-activation-40614646318': {
        'path': B / 'pr6/rebind-r8-20261027/activation-ci/ci-40614646318/artifacts/python-regression-timings/python-regression.json',
        'sha256': 'e75c71e11604fd2d84da6e3f53f226d2f23efee9060032ea9cfc2301dd4ffd1a', 'pool': 'new', 'run': 40614646318,
        'head': '64fc1d395a1a457e25b4ea2ef246463cfa2aa375'},
    'main-push-40635877195': {
        'path': F / 'runs/main-push-40635877195/python-regression-timings/python-regression.json',
        'sha256': None, 'pool': 'old', 'run': 40635877195, 'head': MAIN},
}
COLLECTOR = {'runner': 'scripts/run_regression.py', 'environment_policy': 'scripts/ci_evidence.py',
             'assertion_capture': 'scripts/regression_reason_identity.py', 'assertion_policy': 'scripts/regression_observation_policy.json'}


def dut_manifest(gate, rev):
    """Collector-order DUT manifest digest of rev from Git blobs (evas/src then evas/rust_core, PurePosixPath order)."""
    from pathlib import PurePosixPath
    paths = {}
    for path, (mode, oid) in entries(None, rev).items():
        if path.startswith(('evas/src/', 'evas/rust_core/')) and not ({'__pycache__', 'target', 'baselines', '.git', 'runs'} & set(path.split('/'))):
            paths[path] = oid
    files = []
    for directory in ('evas/src/', 'evas/rust_core/'):
        for path in sorted((p for p in paths if p.startswith(directory)), key=PurePosixPath):
            files.append([path, sha(rgit('cat-file', 'blob', paths[path]))])
    return sha(gate._json(files).encode()), len(files)


def deterministic_gzip(data):
    stream = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', compresslevel=9, mtime=0, fileobj=stream) as handle:
        handle.write(data)
    return stream.getvalue()


def attempt(label, function):
    try:
        function()
        return {'case': label, 'accepted': True, 'error': None}
    except (KeyError, TypeError, ValueError, StopIteration, IndexError, OverflowError) as error:
        return {'case': label, 'accepted': False, 'error': str(error)}


def main(out):
    started = utc()
    guard_before = guard_record('bundle-' + out.name + '-before')
    gate, reg, code = production(MAIN)
    members = {}
    for file in sorted((F / 'e1/zips').glob('*.members.json')):
        for row in load(file):
            members[(file.name.removesuffix('.members.json'), row['path'])] = row['sha256']
    download = load(F / 'e1/download-manifest.json')
    assert download['head'] == HEAD282 and download['run_attempt'] == 1 and download['event'] == 'workflow_dispatch'

    def consume(artifact, path):
        raw = (A / artifact / path).read_bytes()
        assert sha(raw) == members[(artifact, path)], (artifact, path)
        return raw

    # ---- E1 report and identities -------------------------------------------------------------------------------------
    report_raw = consume('python-regression-timings', 'python-regression.json')
    assert sha(report_raw) == E1_RAW_SHA == sha((W / 'ci-40762672880/python-regression.json').read_bytes())
    e1 = json.loads(report_raw)
    assert gate.validate_report(e1)['valid'] and gate._whole(e1) and e1['merged'] and e1['shard_count'] == 4
    subject = gate.execution_subject(e1)
    assert (subject['dut_files_sha256'], subject['kernel_sha256']) == (E1_DUT, E1_KERNEL)
    ci_dir = F / 'code' / ('ci-evidence-' + HEAD282[:8])
    ci_dir.mkdir(parents=True, exist_ok=True)
    for name in ('ci_evidence.py', 'regression_gate.py'):
        raw = rshow(HEAD282, 'scripts/' + name)
        assert raw == rshow(MAIN, 'scripts/' + name), name
        if not (ci_dir / name).exists():
            (ci_dir / name).write_bytes(raw)
        assert (ci_dir / name).read_bytes() == raw
    ci = module('flow_ci_evidence', ci_dir / 'ci_evidence.py')
    assets = load(A / 'catalog-inventory/assets-before.json')
    assert assets == load(A / 'catalog-inventory/assets-after.json')
    assert (assets['source_commit'], assets['source_tree'], assets['dirty_paths']) == (HEAD282, HEAD282_TREE, [])
    rows = {r['path']: r for r in assets['assets']}
    tree = entries(None, HEAD282)
    assert set(rows) == set(tree) and len(rows) == len(assets['assets'])
    snapshot = []
    for path, (mode, oid) in tree.items():
        if path in ci.EXCLUDED:
            continue
        r = rows[path]
        assert (r['git_mode'], r['observed_blob_oid'], r['index_blob_oid']) == (mode, oid, oid), path
        snapshot.append([path, r['git_mode'], r['actual_mode'], r['sha256']])
    identities = []
    for i in range(4):
        artifact = 'python-regression-shard-%d-attempt-1' % i
        identity = json.loads(consume(artifact, 'regression-identity.json'))
        env = identity['environment']
        assert digest(dict(version=3, report_schema_version=3, files=snapshot, environment=env)) == identity['key'], i
        assert identity['input_count'] == len(snapshot) and identity['excluded'] == sorted(ci.EXCLUDED)
        assert ci.comparison_subject(snapshot, env) == identity['comparison_subject'], i
        assert (env['platform'], env['variables']['ImageVersion']) == (NEW_POOL['platform'], NEW_POOL['ImageVersion']), i
        assert env['kernel_sha256'] == E1_KERNEL and env['shard'] == '%d-of-4' % i
        identities.append(identity)
    files_by_path = {row[0]: row[3] for row in snapshot}
    collector = {role: files_by_path[path] for role, path in COLLECTOR.items()}
    assert digest(collector) == e1['metadata']['collector_sha256']
    for path in COLLECTOR.values():
        assert sha(rshow(HEAD282, path)) == files_by_path[path] == sha(rshow(MAIN, path)), path
    assert files_by_path['evas/capabilities/data/language-profile.json'] == e1['metadata']['language_profile']
    duts = {rev: dut_manifest(gate, rev) for rev in (HEAD282, MAIN)}
    assert duts[HEAD282][0] == E1_DUT and duts[MAIN][0] == D0_DUT and duts[HEAD282][1] == len(e1['source_identity']['dut_files'])

    # ---- ten role files ------------------------------------------------------------------------------------------------
    bundle = out / 'bundle'
    bundle.mkdir()
    written = {}

    def put(name, data):
        with (bundle / name).open('xb') as stream:
            stream.write(data)
        written[name] = sha(data)
        return written[name]

    put('report.json', report_raw)
    snapshot_sha = put('snapshot_manifest', dump({'schema_version': 1, 'entries': snapshot}))
    put('collector_manifest', dump(collector))
    kernels = []
    for i in range(4):
        path = A / ('python-regression-shard-%d-attempt-1' % i) / 'regression-build/evas-kernel'
        checksum, size = sha_file(path)
        assert checksum == members[('python-regression-shard-%d-attempt-1' % i, 'regression-build/evas-kernel')] == E1_KERNEL
        kernels.append({'shard_index': i, 'bytes': size, 'sha256': checksum})
    kernel_raw = (A / 'python-regression-shard-0-attempt-1/regression-build/evas-kernel').read_bytes()
    put('kernel_binary', kernel_raw)
    boundaries, streams = {}, {}
    for role in ('stdout', 'stderr'):
        pieces, parts, offset = [], [], 0
        for i in range(4):
            data = consume('python-regression-shard-%d-attempt-1' % i, 'regression-evidence/%s.txt' % role)
            parts.append({'shard_index': i, 'offset': offset, 'bytes': len(data), 'sha256': sha(data)})
            pieces.append(data)
            offset += len(data)
        streams[role] = b''.join(pieces)
        put(role, streams[role])
        boundaries[role] = {'parts': parts, 'total_bytes': len(streams[role]), 'total_sha256': sha(streams[role]),
                            'order': 'ascending shard_index 0..3, plain byte concatenation without separator'}
    write_new(out / 'stream-boundaries.json', boundaries)
    shard_bytes = [consume('python-regression-shard-%d-attempt-1' % i, 'regression-evidence/report.json') for i in range(4)]
    texts = [x.decode('utf-8') for x in shard_bytes]
    assert [t.encode('utf-8') for t in texts] == shard_bytes
    put('shard_reports', dump(texts))
    selection = json.loads(consume('python-regression-timings', 'regression-shard-selection.json'))
    assert selection['valid'] and not selection['superseded'] and not selection['errors'] and selection['run_attempt'] == 1
    assert [row['report_sha256'] for row in selection['selected']] == [sha(x) for x in shard_bytes]
    profile = {k: e1['metadata'][k] for k in ('language_profile', 'runtime_profile', 'invocation')}
    recipe = {'schema_version': 1, 'dut_revision': HEAD282, 'snapshot_sha256': snapshot_sha, 'dut_manifest_sha256': subject['dut_files_sha256'],
              'kernel_sha256': subject['kernel_sha256'], 'criteria_id': e1['metadata']['criteria_id'],
              'collector_sha256': e1['metadata']['collector_sha256'], 'profile_sha256': digest(profile)}
    put('composition_recipe', dump(recipe))
    build_rows = []
    for i in range(4):
        row = {}
        for name in ('stdout.txt', 'stderr.txt'):
            data = consume('python-regression-shard-%d-attempt-1' % i, 'regression-build/' + name)
            row[name] = {'bytes': len(data), 'sha256': sha(data)}
        build_rows.append(row)
    env0 = identities[0]['environment']
    identity_shas = [members[('python-regression-shard-%d-attempt-1' % i, 'regression-identity.json')] for i in range(4)]
    toolchain = (E1_RUN_URL + ' attempt 1; actual regression-identity.json environment of all four shards (sha256 ' + ', '.join(identity_shas)
                 + '): python ' + env0['python'].split()[0] + ', ' + env0['rustc'].splitlines()[0] + ', ' + env0['cargo'].splitlines()[0]
                 + ', platform ' + env0['platform'] + ', ImageVersion ' + env0['variables']['ImageVersion'])
    build_reference = (E1_RUN_URL + ' attempt 1 (workflow_dispatch on codex/evas-capability-batch1), head ' + HEAD282 + ' (tree ' + HEAD282_TREE
                       + '); CI checked out the head itself; original regression-build/{stdout.txt,stderr.txt,evas-kernel} of all four shards '
                       'retained and bound: kernel sha256 ' + E1_KERNEL + ' identical in 4 shards; build stdout sha256 '
                       + '/'.join(r['stdout.txt']['sha256'][:16] for r in build_rows) + '; build stderr sha256 '
                       + '/'.join(r['stderr.txt']['sha256'][:16] for r in build_rows) + '; DUT manifest of ' + HEAD282
                       + ' (it differs from main D0 ' + D0_DUT[:16] + '); kernel not executed here')
    put('dut_build', dump({'schema_version': 1, 'dut_revision': HEAD282, 'dut_manifest_sha256': subject['dut_files_sha256'],
                           'kernel_sha256': subject['kernel_sha256'], 'toolchain_reference': toolchain, 'build_reference': build_reference}))
    capture_reference = (E1_RUN_URL + ' attempt 1; 14 original zipped artifacts, each equal to its API sha256 digest '
                         '(flow/e1/download-manifest.json); report.json is python-regression-timings/python-regression.json byte for byte; '
                         'shard_reports are the four regression-evidence/report.json texts in shard-index order (equal to '
                         'regression-shard-selection.json of the coverage job); stdout/stderr are shard-index-order concatenations, '
                         'byte boundaries in stream-boundaries.json')
    put('artifact_manifest', dump({'schema_version': 1, 'raw_report_sha256': E1_RAW_SHA, 'capture_reference': capture_reference,
                                   'stdout_sha256': sha(streams['stdout']), 'stderr_sha256': sha(streams['stderr']),
                                   'shard_report_sha256': [sha(x) for x in shard_bytes]}))
    assert sorted(p.name for p in bundle.iterdir()) == sorted(ROLES + ('report.json',))
    stored = deterministic_gzip(kernel_raw)
    storage = out / 'storage'
    storage.mkdir()
    write_new(storage / 'kernel_binary.gz', stored)
    materializer_path = F / 'code' / ('main-' + MAIN[:8]) / 'materialize_registration_bundle.py'
    materializer_raw = rshow(MAIN, 'scripts/materialize_registration_bundle.py')
    if not materializer_path.exists():
        materializer_path.write_bytes(materializer_raw)
    assert materializer_path.read_bytes() == materializer_raw
    materializer = module('flow_materializer', materializer_path)
    assert materializer._gunzip_member(stored, len(kernel_raw)) == kernel_raw
    kernel_descriptor = {'encoding': 'gzip', 'decoded_bytes': len(kernel_raw), 'decoded_sha256': E1_KERNEL}

    # ---- trusted baseline, current-run stand-ins and the production checks --------------------------------------------------
    baseline_raw = rshow(MAIN, BASELINE_PATH)
    baseline = json.loads(baseline_raw)
    assert len(baseline['contexts']) == 5 and len(baseline_raw) == 50578629
    e1_compare = gate.compare_report(e1, baseline)
    assert not e1_compare['merge_allowed'] and e1_compare['differences'] == ['expected exactly one matching trusted baseline context']
    standins = {}
    for name, item in STANDINS.items():
        raw = Path(item['path']).read_bytes()
        if item['sha256'] is not None:
            assert sha(raw) == item['sha256'], name
        report = json.loads(raw)
        compared = gate.compare_report(report, baseline)
        matched, host = gate._matching_contexts(baseline['contexts'], gate._context(report))
        sub = gate.execution_subject(report)
        standins[name] = {'report': report, 'raw_sha256': sha(raw), 'path': str(item['path']), 'run': item['run'], 'head': item['head'],
                          'pool': item['pool'], 'merge_allowed': compared['merge_allowed'], 'differences': compared['differences'],
                          'host_runtime_difference': compared.get('host_runtime_difference'),
                          'matched_context_index': baseline['contexts'].index(matched[0]) if len(matched) == 1 else None,
                          'dut_files_sha256': sub['dut_files_sha256'], 'kernel_sha256': sub['kernel_sha256'],
                          'context_sha256': digest(gate._context(report)), 'subject': sub}
        assert compared['merge_allowed'] and standins[name]['matched_context_index'] == MATCHED_CONTEXT, (name, compared['differences'])
        assert (sub['dut_files_sha256'], sub['kernel_sha256']) == (D0_DUT, D0_KERNEL), name
    new_pool = standins['pr6-activation-40614646318']
    # The registration run's context: context 4 with the new pool's host values; E1 equals it except criteria_id.
    expected_current = copy.deepcopy(baseline['contexts'][MATCHED_CONTEXT]['context'])
    for profile_name in ('runtime_profile', 'execution_toolchain'):
        target = expected_current['runtime_profile'] if profile_name == 'runtime_profile' else expected_current['runtime_profile']['execution_toolchain']
        target['platform'], target['variables']['ImageVersion'] = NEW_POOL['platform'], NEW_POOL['ImageVersion']
    e1_context = gate._context(e1)
    e1_except_criteria = dict(e1_context, criteria_id=expected_current['criteria_id'])
    context_facts = {'expected_registration_context_sha256': digest(expected_current),
                     'new_pool_standin_context_equals_expected': gate._context(new_pool['report']) == expected_current,
                     'e1_context_equals_expected_except_criteria_id': e1_except_criteria == expected_current,
                     'e1_criteria_id': e1_context['criteria_id'], 'context4_criteria_id': expected_current['criteria_id']}
    assert context_facts['new_pool_standin_context_equals_expected'] and context_facts['e1_context_equals_expected_except_criteria_id'], context_facts
    environments = {name: s['subject']['comparison_subject']['environment'] for name, s in standins.items()}
    e1_environment = subject['comparison_subject']['environment']
    environment_facts = {}
    for name, value in environments.items():
        differing = sorted(k for k in set(value) | set(e1_environment) if value.get(k) != e1_environment.get(k))
        variables = sorted(k for k in set(value.get('variables', {})) | set(e1_environment.get('variables', {}))
                           if value.get('variables', {}).get(k) != e1_environment.get('variables', {}).get(k))
        environment_facts[name] = {'top_level_keys_differing_from_E1': differing, 'variables_differing_from_E1': variables}

    blobs = {role: (bundle / role).read_bytes() for role in ROLES}
    provenance = {'schema_version': 1, 'snapshot_revision': HEAD282,
                  'snapshot_reference': REPO_URL + '/tree/' + HEAD282 + '; ' + E1_RUN_URL + ' (workflow_dispatch) checked out this head; tree ' + HEAD282_TREE,
                  'raw_reference': E1_RUN_URL + ' attempt 1, artifact python-regression-timings/python-regression.json',
                  'recipe_sha256': written['composition_recipe'], 'artifact_manifest_sha256': written['artifact_manifest']}
    entry_stub = {'source_identity': provenance}
    current = new_pool['subject']

    def harness(current_dut):
        return {'artifacts': {role: {'sha256': sha(data), 'locator': 'bundle/' + role} for role, data in blobs.items()},
                'current_dut': current_dut, 'e1': {'raw_sha256': E1_RAW_SHA, 'execution_subject': subject}}
    d0 = {'manifest_sha256': current['dut_files_sha256'], 'kernel_sha256': current['kernel_sha256']}
    d1 = {'manifest_sha256': subject['dut_files_sha256'], 'kernel_sha256': subject['kernel_sha256']}
    evidence_cases = [
        attempt('V1 production shape: current_dut = D0 (registration run), current = new-pool stand-in',
                lambda: reg.evidence(harness(d0), blobs, gate, e1, entry_stub, current)),
        attempt('V2 current_dut = E1 DUT/kernel, current = new-pool stand-in',
                lambda: reg.evidence(harness(d1), blobs, gate, e1, entry_stub, current)),
        attempt('V3 diagnostic only (not a possible CI fact): current subject replaced by E1 own subject, current_dut = E1',
                lambda: reg.evidence(harness(d1), blobs, gate, e1, entry_stub, subject)),
    ]
    assert [c['accepted'] for c in evidence_cases] == [False, False, True], evidence_cases

    # ---- mapping replay (unchanged object) ----------------------------------------------------------------------------------
    mapping_raw = (W / 'e1-mapping.json').read_bytes()
    assert sha(mapping_raw) == E1_MAPPING_SHA
    mapping = json.loads(mapping_raw)
    expanded = gate._expand_baseline_observations(baseline['contexts'][MATCHED_CONTEXT])
    reg.mapped_obligations({'obligation_mapping': mapping}, gate, expanded, e1)
    replay_standin = attempt('mapping against the new-pool stand-in observations',
                             lambda: reg.mapped_obligations({'obligation_mapping': mapping}, gate, new_pool['report'], e1))
    record = load(W / 'e1-registration-record.json')

    # ---- receipts ---------------------------------------------------------------------------------------------------------------
    files = [{'path': 'bundle/' + p.name, 'bytes': p.stat().st_size, 'sha256': sha_file(p)[0]} for p in sorted(bundle.iterdir())]
    write_new(out / 'bundle-byte-binding.json', {
        'run': E1_RUN, 'attempt': 1, 'event': 'workflow_dispatch', 'head': HEAD282, 'tree': HEAD282_TREE, 'trusted_base': MAIN,
        'files': files, 'kernel_storage': {'path': 'storage/kernel_binary.gz', 'bytes': len(stored), 'sha256': sha(stored),
                                           'descriptor': kernel_descriptor, 'decoder': 'main materialize_registration_bundle._gunzip_member',
                                           'gzip': 'single member, mtime 0, no file name, level 9'},
        'snapshot_entries': len(snapshot), 'snapshot_order': 'git ls-tree order of the head, as ci_evidence.fingerprint lists it; reproduces 4 identity keys',
        'entry_provenance_preview': provenance,
        'role_sources': {'report.json': 'python-regression-timings/python-regression.json (byte copy)',
                         'shard_reports': '4 x python-regression-shard-N-attempt-1/regression-evidence/report.json as a JSON array',
                         'kernel_binary': 'python-regression-shard-0-attempt-1/regression-build/evas-kernel (4 shards identical, never executed)',
                         'stdout': 'shard-index-order concatenation', 'stderr': 'shard-index-order concatenation',
                         'snapshot_manifest': 'catalog-inventory/assets-before.json x git ls-tree order of ' + HEAD282,
                         'collector_manifest': 'four collector source SHA256 from the snapshot', 'composition_recipe': 'derived',
                         'dut_build': 'derived from shard build records and identities', 'artifact_manifest': 'derived'},
        'authorization_created': False, 'semantic_qualification': False})
    receipt = {
        'kind': '#282 E1 bundle intake from original artifact bytes', 'started_at_utc': started, 'finished_at_utc': utc(),
        'e1': {'run': E1_RUN, 'attempt': 1, 'event': 'workflow_dispatch', 'head': HEAD282, 'tree': HEAD282_TREE, 'raw_sha256': E1_RAW_SHA,
               'record': str(W / 'e1-registration-record.json'), 'record_sha256': sha((W / 'e1-registration-record.json').read_bytes()),
               'record_matched_context': record['matched_old_context'], 'pool': NEW_POOL,
               'download_manifest_sha256': sha((F / 'e1/download-manifest.json').read_bytes())},
        'code': code, 'ci_evidence_sha256': sha((ci_dir / 'ci_evidence.py').read_bytes()),
        'execution_subjects': {'e1': {'dut_files_sha256': subject['dut_files_sha256'], 'kernel_sha256': subject['kernel_sha256']},
                               'd0_main': {'dut_files_sha256': D0_DUT, 'kernel_sha256': D0_KERNEL},
                               'dut_manifest_from_git': {k: {'sha256': v[0], 'files': v[1]} for k, v in duts.items()},
                               'e1_differs_from_d0': True},
        'kernel': {'sha256': E1_KERNEL, 'bytes': len(kernel_raw), 'shards': kernels, 'executed': False},
        'snapshot': {'entries': len(snapshot), 'identity_keys_reproduced': 4, 'comparison_subject_reproduced': 4, 'sha256': snapshot_sha},
        'files': files, 'stream_boundaries': str(out / 'stream-boundaries.json'),
        'trusted_baseline': {'revision': MAIN, 'bytes': len(baseline_raw), 'sha256': sha(baseline_raw), 'contexts': len(baseline['contexts']),
                             'canonical_sha256': reg.digest(baseline)},
        'e1_compare_on_unchanged_baseline': {'merge_allowed': e1_compare['merge_allowed'], 'differences': e1_compare['differences']},
        'registration_run_standins': {k: {kk: vv for kk, vv in v.items() if kk not in ('report', 'subject')} for k, v in standins.items()},
        'registration_context': context_facts, 'environment_vs_e1': environment_facts,
        'production_evidence_cases': evidence_cases,
        'mapping': {'path': str(W / 'e1-mapping.json'), 'sha256': E1_MAPPING_SHA, 'rows': len(mapping),
                    'canonical_sha256': reg.digest(mapping), 'classification': sorted({r['classification'] for r in mapping}),
                    'production_mapped_obligations_vs_context4_expansion': 'accepted',
                    'vs_new_pool_standin_observations': replay_standin, 'object_changed': False},
        'guard_before': guard_before['observed_at'], 'scientific_execution': False, 'semantic_qualification': False,
        'command': [sys.executable, '-B', str(Path(__file__).resolve()), out.name]}
    receipt['guard_after'] = guard_record('bundle-' + out.name + '-after')['observed_at']
    write_new(out / 'bundle-intake.json', receipt)
    print(json.dumps({'output': str(out), 'files': len(files), 'evidence_cases': [(c['case'][:3], c['accepted'], c['error']) for c in evidence_cases],
                      'context': context_facts, 'environment_vs_e1': environment_facts}, indent=1), flush=True)


if __name__ == '__main__':
    target = F / sys.argv[1]
    assert not target.exists()
    target.mkdir()
    try:
        main(target)
    except BaseException:
        write_new(target / 'failure.json', {'at_utc': utc(), 'traceback': traceback.format_exc(), 'kept': 'all partial outputs retained'})
        raise
