"""Round 3 gate before any C0 stage on main b4a07295: the decision of 2026-10-29 12:01Z, OBSERVED, and the replaced basis.

Main session decision (option A): the coordinator's gate ("wait until its catalog-inventory is green", "if not green, stop
and report") is met by push CI 40864041959; the main session's own extra condition "every job success" is relaxed because
the 10 skipped jobs are the selector's intended skips for a benchmark/-only push. This script, read only on Git and gh:
  1. re-reads run 40864041959 and its jobs and records all 16 conclusions, the relaxation and the satisfied gate;
  2. downloads its catalog-inventory artifact into a new directory, checks bytes and sha256 against the artifact list
     (7,769,113 bytes, sha256:1a617dea...) and assets-before.json (source_commit b4a07295, tree fa40153a, no dirty path);
  3. runs the required check `git diff --name-only 6fed3c82 b4a07295 -- <context-key paths>` (must be empty);
  4. re-verifies the main session's replacement basis for using the 6fed3c82 stand-in, and the counter-example to the
     round-3 stop note's supporting fact;
  5. checks that every object of b4a07295 is in the shared store, and reads main's tip and the archive tip.
Writes flow/c0-r3/proceed-checks.json (new). Exit 3 (stop and report) when any required check fails.
Usage: python3 -B check_proceed_r3.py
"""
import re
import stat
import zipfile
from pathlib import PurePosixPath

from common_r3 import *

BASE, BASE_TREE, PREVIOUS = R3_MAIN, R3_MAIN_TREE, NEW_MAIN
OUT = R3_PUSH_DIR
ARTIFACT = ('catalog-inventory', 7769113, 'sha256:1a617dea5941b80943256a2068a516e37adda27caa7ff6e3b5a2cf8aa3da5ff9')
STANDIN = R2 / 'runs/main-push-40857285671-catalog/python-regression-timings/python-regression.json'
STANDIN_SHA = 'ab35087fe4aa79eb4538c0054822cc82334b9112a484353e770c9bd5a3d9c137'
EARLIER_SKIPPED = {'provenance-support', 'regression', 'static-checks', 'rust-regression', 'provenance-paper', 'fuzz-smoke',
                   'properties-and-ngspice', 'regression-coverage', 'package', 'regression-admission'}
ACCEPTED = {'success', 'skipped'}
HISTORYREF_MODULES = {'test_directed_triangle_endpoint', 'test_original079_contract', 'test_static_loops'}


def blobs(rev, paths, keep=lambda path: True):
    """{path: bytes} for regular files of rev that keep() accepts, through one read-only cat-file --batch on the shared store."""
    listing = {}
    for item in rgit('ls-tree', '-r', '-z', rev, '--', *paths).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            if kind == 'blob' and mode in ('100644', '100755') and keep(path.decode()):
                listing[path.decode()] = oid
    order = sorted(listing)
    raw = rgit('cat-file', '--batch', data=''.join(listing[p] + '\n' for p in order).encode())
    result, pos = {}, 0
    for path in order:
        end = raw.index(b'\n', pos)
        oid, kind, size = raw[pos:end].decode().split()
        assert oid == listing[path] and kind == 'blob'
        start = end + 1
        result[path] = raw[start:start + int(size)]
        pos = start + int(size) + 1
    return result


def download_catalog_inventory(run):
    artifacts = gh_save('repos/%s/actions/runs/%d/artifacts?per_page=100' % (REPO, R3_PUSH_RUN), OUT / 'api/artifacts.json')
    rows = [a for a in artifacts['artifacts'] if a['name'] == ARTIFACT[0]]
    assert len(rows) == 1, rows
    a = rows[0]
    listed = {'id': a['id'], 'bytes': a['size_in_bytes'], 'digest': a['digest'], 'expired': a['expired'],
              'workflow_run_head_sha': a['workflow_run']['head_sha']}
    zpath = OUT / (a['name'] + '.zip')
    with zpath.open('xb') as stream, (OUT / (a['name'] + '.stderr')).open('xb') as err:
        r = subprocess.run(['gh', 'api', 'repos/%s/actions/artifacts/%d/zip' % (REPO, a['id'])], env=clean_env(), stdout=stream, stderr=err)
    downloaded = {'returncode': r.returncode}
    checksum, size = sha_file(zpath)
    downloaded.update(bytes=size, sha256=checksum)
    target = OUT / a['name']
    target.mkdir()
    members = []
    with zipfile.ZipFile(zpath) as archive:
        assert archive.testzip() is None
        for member in archive.infolist():
            rel = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            assert not rel.is_absolute() and '..' not in rel.parts and '\\' not in member.filename, member.filename
            if member.is_dir():
                continue
            assert stat.S_IFMT(mode) in (0, stat.S_IFREG), member.filename
            dest = target / member.filename
            assert dest.resolve().is_relative_to(target.resolve())
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, dest.open('xb') as dst:
                for chunk in iter(lambda: src.read(1 << 20), b''):
                    dst.write(chunk)
            members.append({'path': member.filename, 'bytes': member.file_size, 'sha256': sha_file(dest)[0]})
    observed = load(target / 'assets-before.json')
    after = target / 'assets-after.json'
    observation = {'path': str(target / 'assets-before.json'), 'sha256': sha_file(target / 'assets-before.json')[0],
                   'source_commit': observed['source_commit'], 'source_tree': observed['source_tree'],
                   'dirty_paths': observed['dirty_paths'], 'assets': len(observed['assets']),
                   'assets_after_equal_before': after.exists() and after.read_bytes() == (target / 'assets-before.json').read_bytes()}
    checks = {'download_returncode_0': r.returncode == 0,
              'bytes_equal_list_and_instruction': size == a['size_in_bytes'] == ARTIFACT[1],
              'sha256_equal_list_and_instruction': 'sha256:' + checksum == a['digest'] == ARTIFACT[2],
              'artifact_from_this_head': a['workflow_run']['head_sha'] == BASE,
              'source_commit_is_base': observed['source_commit'] == BASE, 'source_tree_is_base_tree': observed['source_tree'] == BASE_TREE,
              'no_dirty_paths': observed['dirty_paths'] == []}
    return {'listed': listed, 'downloaded': downloaded, 'members': len(members), 'member_files': members,
            'observation': observation, 'checks': checks, 'ok': all(checks.values())}


def context_key_diff():
    rows = {}
    for label, extra in (('default', ()), ('no_renames', ('--no-renames',))):
        raw = rgit('diff', '--name-only', *extra, PREVIOUS, BASE, '--', *CONTEXT_KEY_PATHS)
        rows[label] = {'command': '/usr/bin/git --no-lazy-fetch diff --name-only %s%s %s -- %s' % (
                           ' '.join(extra) + ' ' if extra else '', PREVIOUS, BASE, ' '.join(CONTEXT_KEY_PATHS)),
                       'output_bytes': len(raw), 'paths': raw.decode().splitlines()}
    workflow = rgit('diff', '--name-only', PREVIOUS, BASE, '--', '.github').decode().splitlines()
    return {'paths_checked': {'criteria': list(CONTEXT_KEY_PATHS[:4]), 'dut': list(CONTEXT_KEY_PATHS[4:6]),
                              'language_profile': CONTEXT_KEY_PATHS[6], 'collector': list(CONTEXT_KEY_PATHS[7:])},
            'runs': rows, 'empty': all(not row['paths'] for row in rows.values()),
            'also_checked_workflow_dir_.github': workflow}


def basis():
    raw = rgit('diff', '--raw', '--no-renames', '--no-abbrev', PREVIOUS, BASE).decode().splitlines()
    status, paths = {}, []
    for line in raw:
        meta, path = line.split('\t', 1)
        letter = meta.split()[-1]
        status[letter] = status.get(letter, 0) + 1
        paths.append(path)
    diff_fact = {'paths': len(paths), 'status_counts': status,
                 'all_under_benchmark/material/draftbench/': all(p.startswith('benchmark/material/draftbench/') for p in paths),
                 'under_benchmark/material/historyref/': [p for p in paths if p.startswith('benchmark/material/historyref/')],
                 'python_files_added_or_modified': sum(1 for p in paths if p.endswith('.py'))}
    standin_raw = STANDIN.read_bytes()
    assert sha(standin_raw) == STANDIN_SHA
    report = json.loads(standin_raw)
    criteria = report['source_identity']['criteria_files']
    methods = [t['id'] for t in report['tests']]
    modules = sorted({i.split('.')[0] for i in methods})
    criteria_fact = {'criteria_files': len(criteria), 'under_benchmark/': [p for p, _ in criteria if p.startswith('benchmark/')]}
    source = blobs(BASE, (), keep=lambda p: p.endswith('.py') and not p.startswith('benchmark/'))
    historyref_readers = sorted(p for p, data in source.items() if p.startswith('evas/tests/') and b'historyref' in data)
    reader_modules = {PurePosixPath(p).stem for p in historyref_readers}
    counter = {'evas/tests .py files containing "historyref"': historyref_readers,
               'expected_three_modules': sorted(HISTORYREF_MODULES), 'equal_expected': reader_modules == HISTORYREF_MODULES,
               'their_methods_in_standin_regression': sum(1 for i in methods if i.split('.')[0] in reader_modules),
               'standin_report_contains_"historyref"': b'historyref' in standin_raw,
               'standin_report_contains_"benchmark/"': b'benchmark/' in standin_raw,
               'conclusion': 'a regression report does not record which files a test reads, so the absence of benchmark/ strings in it '
                             'does not show that benchmark/ is not a regression input (correction of r2/STOP-r3-ci-gate.md section 2)'}
    referencing = sorted(p for p, data in source.items() if b'draftbench' in data or b'DRAFT_BATCHES' in data)
    benchmark_tests = sorted(p for p in source if PurePosixPath(p).name.startswith('test') and (
        p.startswith(('experiments/benchmark_v2/', 'experiments/benchmark_next/')) or p == 'experiments/test_benchmark_paths.py'))
    stems = {PurePosixPath(p).stem for p in benchmark_tests}
    test_refs = [p for p in referencing if PurePosixPath(p).name.startswith('test')]
    helper_refs = [p for p in referencing if not PurePosixPath(p).name.startswith('test')]
    regression_sources = {p: data for p, data in source.items() if p.startswith('evas/tests/')}
    names = ('draftbench', 'DRAFT_BATCHES', 'benchmark_v2', 'benchmark_next', 'benchmark_paths', 'benchmark_package', 'benchmark_workbench')
    regression_mentions = {name: sorted(p for p, data in regression_sources.items() if name.encode() in data) for name in names}
    # CI coverage of these modules in push CI 40864041959 (saved job logs): which test modules each unittest run reported.
    first_batch = (R2 / 'gh/first-batch-job-40864041959-r1.log').read_text(errors='replace').splitlines()
    runs, current = [], set()
    for line in first_batch:
        m = re.search(r' \((test\w*)\.\w+\.\w+\) \.\.\. ', line)
        if m:
            current.add(m.group(1))
        elif re.search(r'Z Ran \d+ tests? in ', line):
            runs.append(sorted(current))
            current = set()
    top_level_v2 = sorted(PurePosixPath(p).stem for p in benchmark_tests if PurePosixPath(p).parent.as_posix() == 'experiments/benchmark_v2')
    v2_subdirectory = [p for p in benchmark_tests if p.startswith('experiments/benchmark_v2/') and PurePosixPath(p).parent.as_posix() != 'experiments/benchmark_v2']
    packages = [p for p in rgit('ls-tree', '-r', '--name-only', BASE, '--', 'experiments/benchmark_v2', 'experiments/benchmark_next').decode().splitlines()
                if p.endswith('/__init__.py')]
    identity = (R2 / 'gh/identity-job-40864041959-r1.log').read_text(errors='replace')
    selection = (R2 / 'gh/selection-job-40864041959-r1.log').read_text(errors='replace')
    coverage = {'first_batch_job_log': str(R2 / 'gh/first-batch-job-40864041959-r1.log'), 'unittest_runs': len(runs),
                'first_run_is_discover_-s_experiments/benchmark_v2': runs[0] if runs else None,
                'benchmark_v2_top_level_test_modules': top_level_v2,
                'first_run_equals_top_level_modules': bool(runs) and runs[0] == top_level_v2,
                '__init__.py_under_benchmark_v2_or_benchmark_next': packages,
                'benchmark_v2_subdirectory_test_modules_not_discovered': v2_subdirectory,
                'of_which_reference_draftbench': [p for p in v2_subdirectory if p in referencing],
                'identity_job_log_contains_unittest_of': {m: m in identity for m in ('experiments.test_benchmark_paths', 'scripts.tests.test_benchmark_package',
                                                                 'scripts.tests.test_benchmark_workbench')},
                'selection_job_ran_test_ci_selection': 'test_ci_selection.' in selection,
                'note': 'unittest discover in Python 3.12 does not enter directories without __init__.py; the first-batch loop names '
                        'experiments/benchmark_v2 itself and each experiments/benchmark_next/* directory'}
    draft_fact = {'python_files_outside_benchmark': len(source),
                  'python_files_outside_benchmark_referencing_draftbench_or_DRAFT_BATCHES': referencing,
                  'test_modules_among_them': test_refs,
                  'test_modules_outside_the_27_and_scripts/tests': [p for p in test_refs if p not in benchmark_tests and not p.startswith('scripts/tests/')],
                  'scripts/tests_modules_among_them': [p for p in test_refs if p.startswith('scripts/tests/')],
                  'files_under_evas/_among_them': [p for p in referencing if p.startswith('evas/')],
                  'non_test_modules_among_them': helper_refs,
                  'evas/tests_mentions_of_benchmark_names': regression_mentions,
                  'test_modules_in_benchmark_v2_benchmark_next_plus_test_benchmark_paths': len(benchmark_tests),
                  'those_test_modules': benchmark_tests,
                  'standin_regression_module_names': len(modules),
                  'overlap_with_standin_regression_modules': sorted(stems & set(modules)),
                  'ci_coverage_in_40864041959': coverage}
    workflow_lines = []
    for path, data in sorted(blobs(BASE, ('.github/workflows',)).items()):
        for number, line in enumerate(data.decode(errors='replace').splitlines(), 1):
            if re.search(r'benchmark_v2|benchmark_next|test_benchmark_paths|first-batch|first_batch|identity', line):
                workflow_lines.append('%s:%d: %s' % (path, number, line.strip()))
    ok = (diff_fact['all_under_benchmark/material/draftbench/'] and not diff_fact['under_benchmark/material/historyref/']
          and status == {'A': 844, 'M': 144} and not criteria_fact['under_benchmark/'] and len(criteria) == 3610
          and not draft_fact['test_modules_outside_the_27_and_scripts/tests'] and not draft_fact['files_under_evas/_among_them']
          and not draft_fact['overlap_with_standin_regression_modules'] and not any(regression_mentions.values()))
    return {'diff_6fed3c82_b4a07295': diff_fact, 'standin_criteria_files': criteria_fact, 'counter_example_historyref': counter,
            'draftbench_readers': draft_fact, 'workflow_lines_static_reading': workflow_lines, 'ok': ok}


def main():
    out = C0R3 / 'proceed-checks.json'
    assert not out.exists() and not OUT.exists()
    started = utc()
    OUT.mkdir(parents=True)
    (OUT / 'api').mkdir()
    run = gh_save('repos/%s/actions/runs/%d' % (REPO, R3_PUSH_RUN), OUT / 'api/run.json')
    jobs = gh_save('repos/%s/actions/runs/%d/attempts/%d/jobs?per_page=100' % (REPO, R3_PUSH_RUN, run['run_attempt']), OUT / 'api/jobs.json')
    conclusions = {j['name']: j['conclusion'] for j in jobs['jobs']}
    unacceptable = {n: c for n, c in conclusions.items() if c not in ACCEPTED}
    skipped = {n for n, c in conclusions.items() if c == 'skipped'}
    gate = {'run': R3_PUSH_RUN, 'event': run['event'], 'head_sha': run['head_sha'], 'run_attempt': run['run_attempt'],
            'status': run['status'], 'conclusion': run['conclusion'], 'jobs_total': len(conclusions), 'jobs': conclusions,
            'counts': {c: sum(1 for v in conclusions.values() if v == c) for c in sorted(set(map(str, conclusions.values())))},
            'failures': len(unacceptable), 'jobs_not_success_or_skipped': unacceptable,
            'skipped_equal_round3_stop_note': skipped == EARLIER_SKIPPED,
            'coordinator_gate': {'text': '等它的 catalog-inventory 绿了再继续 C0；万一不绿，先停下报我',
                                 'catalog_inventory_conclusion': conclusions.get('catalog-inventory'),
                                 'met': conclusions.get('catalog-inventory') == 'success' and run['conclusion'] == 'success' and not unacceptable},
            'relaxed_condition': {'text': '每个 job 都 success', 'added_by': 'main session (not the coordinator)',
                                  'relaxed_by': 'main session decision, option A',
                                  'relaxed_at_utc': '2026-10-29T12:01:32Z',
                                  'relaxed_at_source': 'T3 thread record: requestedAt of run 3, the main session message evas-pr282-c0-r3-proceed-a-20261029',
                                  'reason': 'the 10 skipped jobs are the CI selector\'s intended skips for a benchmark/-only push (Selected: benchmark)'}}
    gate_ok = (run['status'] == 'completed' and run['conclusion'] == 'success' and run['head_sha'] == BASE and run['event'] == 'push'
               and gate['coordinator_gate']['met'] and gate['skipped_equal_round3_stop_note'])
    artifact = download_catalog_inventory(run)
    keys = context_key_diff()
    facts = basis()
    listing = rgit('rev-list', '--objects', '--missing=print', BASE)
    lines = listing.decode().splitlines()
    objects = {'command': '/usr/bin/git --no-lazy-fetch rev-list --objects --missing=print ' + BASE + ' (shared store)',
               'objects': len(lines), 'missing': [l for l in lines if l.startswith('?')]}
    tips_at = utc()
    main_tip = gh_save('repos/%s/branches/main' % REPO, R2 / 'gh/main-branch-r3-proceed.json')['commit']['sha']
    archive_tip = gh_save('repos/%s/git/ref/heads/codex/evas-method-audit-archive-20261025' % REPO, R2 / 'gh/archive-ref-r3-proceed.json')['object']['sha']
    authority = gh_save('repos/%s/git/ref/heads/codex/pr4-context-authority' % REPO, R2 / 'gh/aux-authority-ref-r3-proceed.json')['object']['sha']
    baseline = gh_save('repos/%s/git/ref/heads/codex/pr4-context-baseline' % REPO, R2 / 'gh/aux-baseline-ref-r3-proceed.json')['object']['sha']
    tips = {'at_utc': tips_at, 'main': main_tip, 'main_is_base': main_tip == BASE, 'archive': archive_tip,
            'archive_is_18a202cb': archive_tip == ARCHIVE_TIP_R3, 'codex/pr4-context-authority': authority, 'codex/pr4-context-baseline': baseline}
    proceed = gate_ok and artifact['ok'] and keys['empty'] and facts['ok'] and not objects['missing'] and tips['main_is_base'] and tips['archive_is_18a202cb']
    write_r3(out, {
        'round': 3, 'base': BASE, 'base_tree': BASE_TREE, 'previous_main': PREVIOUS, 'started_at_utc': started,
        'decision': 'main session option A (2026-10-29T12:01:32Z): proceed from source to inventory on b4a07295',
        'ci_gate': gate, 'ci_gate_ok': gate_ok,
        'observed': artifact,
        'context_key_diff': keys,
        'registration_run_standin': {'path': str(STANDIN), 'sha256': STANDIN_SHA, 'run': MAIN_PUSH_RUN, 'head': PREVIOUS,
                                     'head_is_base': False, 'pool': 'new (7.0.0-1017, ImageVersion 20261026.354.1)',
                                     'second_positive': 40614646318, 'use': 'local positive validation only; not part of the C0 bytes',
                                     'basis': 'replacement_basis below (main session section 2), re-verified here'},
        'replacement_basis': facts,
        'shared_store_objects_of_base': objects,
        'tips': tips,
        'earlier_stop_receipt': {'path': str(C0R3 / 'base-checks.json'), 'sha256': sha_file(C0R3 / 'base-checks.json')[0],
                                 'note': 'unchanged; its stop was the main session\'s every-job condition, relaxed above'},
        'proceed': proceed, 'finished_at_utc': utc()})
    print(json.dumps({'proceed': proceed, 'ci_gate_ok': gate_ok, 'artifact_ok': artifact['ok'], 'context_key_diff_empty': keys['empty'],
                      'basis_ok': facts['ok'], 'objects': objects['objects'], 'missing': len(objects['missing']), 'tips': tips}), flush=True)
    return 0 if proceed else 3


if __name__ == '__main__':
    raise SystemExit(main())
