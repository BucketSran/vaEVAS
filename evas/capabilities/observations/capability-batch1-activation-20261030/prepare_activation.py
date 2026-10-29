"""#282 activation head: main 0ad80828 merged into #282 (84d6b71f), then the capability catalog regenerated.

Template: pr6/rebind-r8-20261027/prepare_pr6_r8.py (the PR6 activation, round 8), adapted to #282; #282 has no P3 step.

Construction chain 2 (receipts named *-c2, see common_act.C). Chain 1 (unsuffixed receipts) took main's
evas/capabilities/data/registry.json whole, as catalog data. That file also holds the hand-written requirement cards,
cases, checkers and sources, and generate_catalog.py keeps the hand-written objects and their current entries from the
source tree's registry.json. Chain 1's catalog therefore kept #282's eleven hand-written objects as old versions but not
as current, and its views dropped them; this was found after its freeze, before any check, and nothing of chain 1 was
published. Chain 2 merges registry.json three ways: main's generated header and objects (regenerated afterwards) plus
the eleven hand-written objects #282 added and their current entries. Main changed no hand-written object since
d6b7543f, so the merge has no conflict. Chain 1's sources stage is reused: its merge commit M1 differs from chain 2's only
in registry.json and the re-rendered views.
  - source (chain 1, kept): export main 0ad80828 into the private repository W/source; #282's bytes for every path only
    #282 changed, main's for every path only main changed; a three-way merge (git merge-file) where both changed a source
    path (none; a conflict stops the run). Catalog data and derived files from main.
  - remerge: the working tree of M1 plus the three-way merged registry.json, then the diagnostic inventory check and the
    render of the capability views.
  - capture: the merge commit [84d6b71f, 0ad80828]; per-path source equality; the context check (criteria, DUT, language
    profile and the four collector files equal #282's head, the registered sixth context, and E1's manifests); the asset
    receipt reuses the rows of main's push CI 40944364517 observation for unchanged blobs and hashes every other blob.
  - discover: receipts reused by exact workflow entry, collector and owner-module hashes (main's and #282's published
    construction receipts); entries #282's changes hit, or with a test module main changed, are collected again.
  - union: main's catalog objects (read from 0ad80828) plus every 84d6b71f object main lacks, and #282's current entries
    for the ids main lacks; a conflicting object version stops the run.
  - archive: the construction archive commit on the archive tip e91f96cc (a fast-forward; published by the main session).
  - generate (twice, byte for byte), derive (traceability and render; no criteria or collector path), freeze (the catalog
    commit on the merge commit: a fast-forward successor of 84d6b71f), precheck (the static-checks Traceability step
    commands with the full scripts/tests, capabilities tests, ruff through ci_lint, git diff --check) and inventory
    (collect_ci_inventory.py --require-catalog, no drift).
Stages write new receipts in W and refuse to replace them; failures stop with SystemExit. No scientific test body,
simulator, backend or Spectre runs here; the full scientific regression runs only in CI.
Usage: <lint venv python> -B prepare_activation.py <stage>
"""
from pathlib import PurePosixPath
import argparse
import copy
import fnmatch
import shutil
import traceback

from common_act import *

D = W
OBSERVED_RECEIPT = W / 'observed/fetch-receipt.json'
# Union attempt 1 of chain 2 (previous-union-c2, main-data-c2) wrote both directories and then stopped in the registry
# check, because registry.load requires the data directory inside the source root; they are kept unchanged and unused.
UNION = W / C('previous-union-a2')
MAIN_DATA = W / C('main-data-a2')
PREFIX = 'evas/capabilities/observations/capability-batch1-activation-20261030'
MERGE_MESSAGE = 'Merge main after the batch 1 context registration into the capability batch 1 changes'
FINAL_MESSAGE = 'Regenerate the capability catalog after merging main, keeping every object version of both parents'
RETENTION_REVS = (('main', BASE), ('pr282_head', HEAD282), ('merge_base', MERGE_BASE),
                  ('main_7a487c8f', '7a487c8f6e02ea06e0ec2531674d2a1a5086602f'), ('main_b4a07295', 'b4a072959d55fa3b23e34dfcadd92103ec89f2a3'),
                  ('main_6fed3c82', '6fed3c820b6eaecdfabd6d5dcacf8febdd197e4c'), ('main_bf2ec410', 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'),
                  ('main_02dee32b', '02dee32b2c9b25f166cbd77f8a895953e004f288'))
TOOLS = {'PATH': str(Path.home() / '.cargo/bin') + ':' + str(PY.parent) + ':/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',
         # CI pins RUSTUP_TOOLCHAIN 1.99.1 and installs clippy and rustfmt for it; the local 1.99.1 is a minimal install
         # without them and installing needs the network, so the local checks use 1.99.0, the nearest toolchain that has both.
         'CARGO_TARGET_DIR': str(W / 'cargo-target'), 'RUSTUP_TOOLCHAIN': '1.99.0',
         'CARGO_HOME': str(W / 'cargo-home')}   # precheck: a copy of the local registry index and crate cache, so cargo writes only in W
CARGO_HOME_SOURCE = Path.home() / '.cargo/registry'
WORKFLOW = '.github/workflows/numerical-assurance.yml'
CONTEXT_KEY_PATHS = (*CRITERIA_DIRS, *DUT_DIRS, LANGUAGE_PROFILE, *COLLECTOR4)   # round-3 check_proceed_r3 (common_r3.py)
BASELINE_FILES = (BASELINE_PATH, REVIEW_PATH)   # the two baseline files main changed (sixth context appended)
REGISTRY = DATA + 'registry.json'
M1 = '5240711106953a504925a679f7bcecddeed0033f'   # chain 1 merge commit (superseded): main's registry.json
F1 = 'efb152d67032f7f5bde30e1b91eb7e362344c951'   # chain 1 catalog commit (superseded)
# Discovery attempt 1 of chain 1 (discovery-selection.json, new-discovery/) counted #282's changed test modules as helpers
# of the five single-module scripts/tests entries; attempt 2 (discovery-selection-r2.json) fixed that. Chain 2 runs its own.
DISCOVERY = D / C('discovery-selection.json')
NEW_DISCOVERY = D / C('new-discovery')


def invariant():
    if (S / '.git').exists():
        for key in ('--absolute-git-dir', '--git-common-dir', '--show-toplevel'):
            assert Path(pgit(S, 'rev-parse', key).decode().strip()).resolve().is_relative_to(W.resolve())
    disk_ok()


def manifest_path(path):
    return not any(part in MANIFEST_SKIP for part in PurePosixPath(path).parts)


def export(rev, target, private):
    target.mkdir(parents=True)
    with (W / 'logs' / ('export-' + target.name + '.stderr')).open('xb') as err:
        producer = subprocess.Popen([GIT, '--no-lazy-fetch', '--git-dir=' + str(VIEW), 'archive', rev], env=private_env(),
                                    stdout=subprocess.PIPE, stderr=err, cwd=W)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(target)], stdin=producer.stdout, env=private_env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    if not private:
        return
    r = subprocess.run([GIT, '--git-dir=' + str(target / '.git'), '--work-tree=' + str(target), 'init', '--quiet', '--template=',
                        '--initial-branch=pr282-activation'], cwd=target, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    (target / '.git/objects/info/alternates').write_text(''.join(str(p) + '\n' for p in ALTERNATES))
    pgit(target, 'read-tree', rev)
    pgit(target, 'update-ref', 'HEAD', rev)
    pgit(target, 'update-index', '-q', '--refresh', check=False)
    assert not pgit(target, 'status', '--porcelain=v1').strip()


def render_outputs(root):
    sys.path.insert(0, str(root / 'evas/capabilities'))
    try:
        renderer = module('act_render_' + sha(str(root).encode())[:8], root / 'evas/capabilities/render.py')
        files = renderer.outputs(renderer.registry())
    finally:
        sys.path.pop(0)
    return sorted(Path(p).resolve().relative_to(root.resolve()).as_posix() for p in files)


def objects_dir(path):
    header = json.loads((path / 'registry.json').read_text())
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads((path / part).read_text())['objects']
    return {(item['id'], item['version']): item for item in result}


def objects_at(rev):
    header = json.loads(show(rev, REGISTRY, S))
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads(show(rev, DATA + part, S))['objects']
    return {(item['id'], item['version']): item for item in result}


def commit_paths(parent, paths, message, parents, name, modes):
    """Commit S's bytes of paths (or their removal) on top of parent, in the private repository only.

    modes gives each path's Git mode (the merge commit takes #282's, as in the template; the catalog commit the merge's)."""
    index = W / 'indexes' / (name + '.index')
    assert not index.exists(), index
    index.parent.mkdir(exist_ok=True)
    pgit(S, 'read-tree', parent, index=index)
    files = {}
    for path in paths:
        target = S / path
        if target.exists():
            raw = target.read_bytes()
            mode = modes.get(path, ('100755' if os.access(target, os.X_OK) else '100644', None))[0]
            oid = pgit(S, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
            pgit(S, 'update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
            files[path] = sha(raw)
        else:
            pgit(S, 'update-index', '--force-remove', path, index=index)
            files[path] = None
    tree = pgit(S, 'write-tree', index=index).decode().strip()
    args = []
    for p in parents:
        args += ['-p', p]
    commit = pgit(S, 'commit-tree', tree, *args, '-m', message + TRAILER).decode().strip()
    index.unlink()
    return {'commit': commit, 'tree': tree, 'parents': list(parents), 'paths': sorted(paths), 'files': files, 'at_utc': utc()}


def changed_vs(rev):
    pgit(S, 'add', '--intent-to-add', '--', '.')
    paths = pgit(S, 'diff', '--no-renames', '--name-only', rev).decode().splitlines()
    pgit(S, 'reset', '--quiet')
    return paths


def hunks(diff_text):
    return [line for line in diff_text.splitlines() if line[:1] in '+- ' and not line.startswith(('+++', '---'))]


def source():
    """Chain 1 (kept for the record; refuses to run again): export main, apply #282's sources, pre-render."""
    before = guard('source-before')
    invariant()
    assert not S.exists() and not S282.exists() and not (D / 'source-preparation.json').exists()
    assert vgit('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    assert vgit('rev-parse', HEAD282 + '^{tree}').decode().strip() == HEAD282_TREE
    assert vgit('rev-list', '--parents', '-n', '1', BASE).decode().split()[1:] == BASE_PARENTS
    assert vgit('merge-base', HEAD282, BASE).decode().strip() == MERGE_BASE
    export(BASE, S, True)
    export(HEAD282, S282, False)
    pr_paths, main_paths = names(MERGE_BASE, HEAD282), names(MERGE_BASE, BASE)
    rendered_282 = set(render_outputs(S282))
    sources = sorted(set(pr_paths) - rendered_282 - DERIVED_DATA)
    modes = entries(HEAD282)
    merged = []
    for path in sources:
        ours, target = show(HEAD282, path), S / path
        if path in main_paths:
            base_raw, theirs = show(MERGE_BASE, path), show(BASE, path)
            if ours is None or base_raw is None or theirs is None:
                write_new(D / 'merge-conflict.json', {'path': path, 'pr282': pr_paths[path], 'main': main_paths[path], 'at_utc': utc()})
                raise SystemExit('both sides add or delete ' + path + '; stop and report (needs a small priority review)')
            scratch = D / 'merge-file' / path.replace('/', '__')
            scratch.mkdir(parents=True)
            for name, raw in (('ours', ours), ('base', base_raw), ('theirs', theirs)):
                (scratch / name).write_bytes(raw)
            result = subprocess.run([GIT, 'merge-file', '-p', str(scratch / 'ours'), str(scratch / 'base'), str(scratch / 'theirs')],
                                    env=private_env(), capture_output=True)
            if result.returncode:
                (scratch / 'conflicted').write_bytes(result.stdout)
                write_new(D / 'merge-conflict.json', {'path': path, 'returncode': result.returncode, 'at_utc': utc(), 'scratch': str(scratch)})
                raise SystemExit('three-way merge conflict in ' + path + '; stop and report (needs a small priority review)')
            raw, how = result.stdout, 'three-way merge of #282 and main edits'
        elif ours is None:
            target.unlink()
            merged.append({'path': path, 'sha256': None, 'resolution': '#282 deletes it (main unchanged since d6b7543f)'})
            continue
        else:
            raw, how = ours, '#282 version (main unchanged since d6b7543f)'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o755 if modes[path][0] == '100755' else 0o644)
        merged.append({'path': path, 'sha256': sha(raw), 'resolution': how})
    both = sorted(set(pr_paths) & set(main_paths))
    write_new(D / 'source-plan.json', {'pr282': HEAD282, 'base': BASE, 'merge_base': MERGE_BASE, 'merge_sources': merged,
              'pr282_render_outputs': sorted(rendered_282), 'main_paths': main_paths, 'pr282_paths': pr_paths,
              'changed_by_both': both, 'changed_by_both_outside_derived': sorted(set(both) - DERIVED_DATA - rendered_282)})
    results, regenerated = [], []
    rc = run_logged(D / 'logs/source-diagnostic-inventory-check.txt', [PY, '-B', 'scripts/diagnostic_inventory.py', '--check'], S, results, extra_env=TOOLS)
    if rc:
        assert run_logged(D / 'logs/source-diagnostic-inventory-write.txt', [PY, '-B', 'scripts/diagnostic_inventory.py', '--write'], S,
                          results, extra_env=TOOLS) == 0
        assert run_logged(D / 'logs/source-diagnostic-inventory-recheck.txt', [PY, '-B', 'scripts/diagnostic_inventory.py', '--check'], S,
                          results, extra_env=TOOLS) == 0
        regenerated.append('evas/docs/development/diagnostic-inventory.json')
    assert run_logged(D / 'logs/pre-render.txt', [PY, '-B', 'evas/capabilities/render.py'], S, results, extra_env=TOOLS) == 0
    after = guard('source-after')
    write_new(D / 'source-preparation.json', {'prepared_at_utc': utc(), 'base': BASE, 'base_tree': BASE_TREE, 'base_parents': BASE_PARENTS,
              'pr282': HEAD282, 'pr282_tree': HEAD282_TREE, 'merge_base': MERGE_BASE, 'export': str(S), 'private_git': str(S / '.git'),
              'alternates': [str(p) for p in ALTERNATES], 'pr282_export': str(S282), 'plan': str(D / 'source-plan.json'),
              'merge_sources': len(merged), 'three_way': [m['path'] for m in merged if m['resolution'].startswith('three-way')],
              'regenerated_before_capture': regenerated, 'checks': results, 'guard_before': before, 'guard_after': after,
              'scientific_execution': False})
    print(json.dumps({'merge_sources': len(merged), 'three_way': [m['path'] for m in merged if m['resolution'].startswith('three-way')],
                      'changed_by_both_outside_derived': sorted(set(both) - DERIVED_DATA - rendered_282), 'regenerated': regenerated}), flush=True)


def merged_registry():
    """registry.json for the merge: main's generated header and objects, plus the hand-written objects #282 added
    (in #282's order) and their current entries. The inline objects of registry.json are the hand-written ones; main
    changed none of them since d6b7543f, so the three-way merge of the hand-written part has no conflict. The generated
    part (current entries of generated ids, asset scope) is main's here and is regenerated by the catalog generation."""
    docs = {name: json.loads(show(rev, REGISTRY)) for name, rev in (('merge_base', MERGE_BASE), ('main', BASE), ('pr282', HEAD282))}
    raws = {name: show(rev, REGISTRY) for name, rev in (('merge_base', MERGE_BASE), ('main', BASE), ('pr282', HEAD282))}

    def key(o):
        return (o['id'], o['version'])
    inline = {name: {key(o): o for o in doc['objects']} for name, doc in docs.items()}
    base_ids = {o['id'] for o in docs['merge_base']['objects']}
    added = [o for o in docs['pr282']['objects'] if key(o) not in inline['merge_base']]
    checks = {
        'serialization_roundtrips': all((json.dumps(docs[n], indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode() == raws[n] for n in docs),
        'main_hand_written_objects_equal_merge_base': inline['main'] == inline['merge_base'],
        'pr282_keeps_merge_base_hand_written_objects': all(inline['pr282'].get(k) == v for k, v in inline['merge_base'].items()),
        'merge_base_hand_written_current_unchanged_on_both': all(docs['main']['current'].get(i) == docs['merge_base']['current'].get(i)
                                                                 == docs['pr282']['current'].get(i) for i in base_ids),
        'added_objects_absent_from_main': all(key(o) not in inline['main'] and o['id'] not in docs['main']['current'] for o in added),
        'added_objects_current_on_pr282': all(docs['pr282']['current'].get(o['id']) == o['version'] for o in added),
        'pr282_objects_are_merge_base_then_added': [key(o) for o in docs['pr282']['objects']]
                                                   == [key(o) for o in docs['merge_base']['objects']] + [key(o) for o in added],
        'header_keys_equal': set(docs['main']) == set(docs['pr282']) == set(docs['merge_base']),
    }
    if not all(checks.values()):
        write_new(D / C('registry-merge-conflict.json'), {'at_utc': utc(), 'checks': checks})
        raise SystemExit('registry.json hand-written objects do not merge cleanly; stop and report: ' + json.dumps(checks))
    merged = copy.deepcopy(docs['main'])
    merged['objects'] = docs['main']['objects'] + copy.deepcopy(added)
    merged['current'] = dict(docs['main']['current']) | {o['id']: docs['pr282']['current'][o['id']] for o in added}
    raw = (json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode()
    info = {'checks': checks, 'added': [list(key(o)) for o in added], 'added_current': {o['id']: o['version'] for o in added},
            'main_objects': len(docs['main']['objects']), 'merged_objects': len(merged['objects']),
            'main_current': len(docs['main']['current']), 'merged_current': len(merged['current']),
            'other_header_keys_from_main': sorted(k for k in merged if k not in ('objects', 'current')),
            'sha256': {'merge_base': sha(raws['merge_base']), 'main': sha(raws['main']), 'pr282': sha(raws['pr282']), 'merged': sha(raw)},
            'serialization': 'json.dumps(indent=2, ensure_ascii=False, sort_keys=True) + newline; reproduces all three inputs byte for byte'}
    return raw, info


def remerge():
    """Chain 2, step 1: M1's tree plus the three-way merged registry.json, then the diagnostic inventory check and the
    capability view render (pre-render, as in chain 1)."""
    before = guard(C('remerge-before'))
    invariant()
    out = D / C('remerge.json')
    assert not out.exists()
    head = pgit(S, 'rev-parse', 'HEAD').decode().strip()
    assert head == F1 and not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip(), head
    pgit(S, 'reset', '--quiet', '--hard', M1)
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == M1
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    raw, info = merged_registry()
    (S / REGISTRY).write_bytes(raw)
    results = []
    assert run_logged(D / 'logs' / C('remerge-diagnostic-inventory-check.txt'), [PY, '-B', 'scripts/diagnostic_inventory.py', '--check'],
                      S, results, extra_env=TOOLS) == 0
    assert run_logged(D / 'logs' / C('remerge-render.txt'), [PY, '-B', 'evas/capabilities/render.py'], S, results, extra_env=TOOLS) == 0
    changed = sorted(changed_vs(M1))
    rendered = set(render_outputs(S))
    assert REGISTRY in changed and set(changed) - rendered == {REGISTRY}, changed
    write_new(out, {'at_utc': utc(), 'chain': CHAIN, 'chain1_merge_commit': M1, 'chain1_catalog_commit': F1,
                    'reset': 'private repository branch pr282-activation moved from ' + F1 + ' to ' + M1 + ' (git reset --hard, inside W)',
                    'registry_merge': info, 'changed_vs_chain1_merge': changed,
                    'render_outputs_changed': sorted(set(changed) - {REGISTRY}), 'checks': results,
                    'guard_before': before, 'guard_after': guard(C('remerge-after')), 'scientific_execution': False})
    print(json.dumps({'registry_added': len(info['added']), 'changed_vs_chain1_merge': changed}), flush=True)


def context_check(head):
    """Brief item 2: the merged head must still produce the registered sixth context (E1, CI 40762672880 on 84d6b71f).

    Method of round 3 (r2/check_proceed_r3.py context_key_diff): git diff --name-only, default and --no-renames, from E1's
    head to the merged head over the context key paths; the only allowed paths are the two baseline files. Then each item
    is listed (files, blobs equal), and scripts/run_regression.py observation_identity on the merged export is compared
    with the sixth context of main's baseline and with the E1 report."""
    runs = {}
    for label, extra in (('default', ()), ('no_renames', ('--no-renames',))):
        raw = pgit(S, 'diff', '--name-only', *extra, HEAD282, head, '--', *CONTEXT_KEY_PATHS)
        runs[label] = {'command': '/usr/bin/git --no-lazy-fetch diff --name-only %s%s %s -- %s' % (
                           ' '.join(extra) + ' ' if extra else '', HEAD282, head, ' '.join(CONTEXT_KEY_PATHS)),
                       'output_bytes': len(raw), 'paths': raw.decode().splitlines()}
    allowed = sorted(BASELINE_FILES)
    diff_ok = all(sorted(row['paths']) == allowed for row in runs.values())
    got_all, want_all, main_all = entries(head, S), entries(HEAD282), entries(BASE)
    items = []
    for item in CONTEXT_KEY_PATHS:
        def under(rows):
            return {p: v for p, v in rows.items() if p == item or p.startswith(item + '/')}
        got, want = under(got_all), under(want_all)
        differ = sorted(p for p in set(got) | set(want) if got.get(p) != want.get(p))
        kind = ('criteria' if item in CRITERIA_DIRS else 'DUT' if item in DUT_DIRS else
                'language profile' if item == LANGUAGE_PROFILE else 'collector')
        row = {'item': item, 'kind': kind, 'files_merged_head': len(got), 'files_e1_head': len(want),
               'equal_blobs': sum(1 for p in got if want.get(p) == got[p]), 'differences': differ,
               'differences_allowed': [p for p in differ if p in BASELINE_FILES],
               'equal_except_the_two_baseline_files': all(p in BASELINE_FILES for p in differ)}
        if item in (LANGUAGE_PROFILE, *COLLECTOR4):
            row['blob'] = {'merged_head': got.get(item, (None, None))[1], 'e1_head': want.get(item, (None, None))[1]}
        items.append(row)
    baselines_dir = 'evas/validation/baselines/'
    baseline_rows = {p: {'merged_head': got_all.get(p, (None, None))[1], 'e1_head': want_all.get(p, (None, None))[1],
                         'main': main_all.get(p, (None, None))[1]}
                     for p in sorted(p for p in set(got_all) | set(want_all) if p.startswith(baselines_dir))}
    workflow = {'merged_head_blob': got_all.get(WORKFLOW, (None, None))[1], 'e1_head_blob': want_all.get(WORKFLOW, (None, None))[1]}
    workflow['equal'] = workflow['merged_head_blob'] == workflow['e1_head_blob']
    rs = module('act_runner', S / 'scripts/run_regression.py')
    metadata, identity = rs.observation_identity(S / 'evas/tests', S, [], 'test*.py')
    e1_raw = E1_REPORT.read_bytes()
    assert sha(e1_raw) == E1_RAW_SHA
    e1 = json.loads(e1_raw)
    baseline = json.loads(show(head, BASELINE_PATH, S))
    sixth = baseline['contexts'][-1]
    keys = ('criteria_id', 'language_profile', 'collector_sha256', 'invocation')
    checks = {
        'git_diff_context_key_paths_only_the_two_baseline_files': diff_ok,
        'every_item_equal_except_the_two_baseline_files': all(row['equal_except_the_two_baseline_files'] for row in items),
        'baseline_files_equal_main': all(show(head, p, S) == show(BASE, p) for p in BASELINE_FILES),
        'six_contexts_sixth_bound_to_e1_head': len(baseline['contexts']) == 6 and sixth['source_identity']['snapshot_revision'] == HEAD282,
        'workflow_equal_e1_head': workflow['equal'],
        'criteria_manifest_equals_E1': identity['criteria_files'] == e1['source_identity']['criteria_files'],
        'dut_manifest_equals_E1': identity['dut_files'] == e1['source_identity']['dut_files'],
        'context_keys_equal_sixth_context': all(metadata[k] == sixth['context'][k] for k in keys),
        'context_keys_equal_E1_report': all(metadata[k] == e1['metadata'][k] for k in keys),
    }
    return {'checks': checks, 'ok': all(checks.values()), 'e1_head': HEAD282, 'merged_head': head, 'context_key_paths': list(CONTEXT_KEY_PATHS),
            'git_diff': runs, 'allowed_paths': allowed, 'items': items, 'baselines_directory': baseline_rows, 'workflow': workflow,
            'computed': {k: metadata[k] for k in keys} | {'criteria_files': len(identity['criteria_files']), 'dut_files': len(identity['dut_files']),
                                                           'dut_manifest_sha256': rs.json_digest(identity['dut_files'])},
            'sixth_context': {k: sixth['context'][k] for k in keys} | {'snapshot_revision': sixth['source_identity']['snapshot_revision']},
            'e1_report': {k: e1['metadata'][k] for k in keys} | {'path': str(E1_REPORT), 'sha256': E1_RAW_SHA,
                                                               'criteria_files': len(e1['source_identity']['criteria_files']),
                                                               'dut_files': len(e1['source_identity']['dut_files'])},
            'manifest_exclusions': 'scripts/run_regression.py file_manifest skips path parts ' + ', '.join(MANIFEST_SKIP)}


def capture():
    invariant()
    plan, prep, rem = load(D / 'source-plan.json'), load(D / 'source-preparation.json'), load(D / C('remerge.json'))
    assert not (D / C('capture.json')).exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == M1 and not prep['regenerated_before_capture']
    obs = load(OBSERVED_RECEIPT)
    assert obs['accepted'] and obs['run'] == PUSH_RUN and sha_file(obs['assets_before'])[0] == obs['assets_before_sha256']
    observed = load(obs['assets_before'])
    assert observed['source_commit'] == BASE and observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    registry_raw = (S / REGISTRY).read_bytes()
    assert sha(registry_raw) == rem['registry_merge']['sha256']['merged']
    rendered = set(render_outputs(S))
    merge_paths = sorted({m['path'] for m in plan['merge_sources']} | {REGISTRY}
                         | {p for p in rendered if show(BASE, p) != ((S / p).read_bytes() if (S / p).exists() else None)})
    cap = commit_paths(BASE, merge_paths, MERGE_MESSAGE, [HEAD282, BASE], C('merge'), entries(BASE) | entries(HEAD282))
    head, tree = cap['commit'], cap['tree']
    pgit(S, 'reset', '--quiet', head)
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == head
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    pgit(S, 'merge-base', '--is-ancestor', HEAD282, head)
    pgit(S, 'merge-base', '--is-ancestor', BASE, head)
    vs_m1 = sorted(names(M1, head, S))
    assert set(vs_m1) <= {REGISTRY} | rendered and REGISTRY in vs_m1, vs_m1
    pr_paths, main_paths = set(plan['pr282_paths']), set(plan['main_paths'])
    excluded = DERIVED_DATA | set(plan['pr282_render_outputs']) | rendered
    rows, problems = [], []
    for path in sorted((pr_paths | main_paths) - excluded):
        got = show(head, path, S)
        if path in pr_paths and path not in main_paths:
            expected, kind = show(HEAD282, path), '#282 only: equals the reviewed #282 head'
        elif path in main_paths and path not in pr_paths:
            expected, kind = show(BASE, path), 'main only: equals main'
        else:
            expected, kind = (S / path).read_bytes(), 'both: three-way merge'
            vs_main, vs_pr = pgit(S, 'diff', BASE, head, '--', path).decode(), pgit(S, 'diff', HEAD282, head, '--', path).decode()
            pr_change, main_change = pgit(S, 'diff', MERGE_BASE, HEAD282, '--', path).decode(), pgit(S, 'diff', MERGE_BASE, BASE, '--', path).decode()
            both = {'merged_vs_main_equals_pr282_change': hunks(vs_main) == hunks(pr_change),
                    'merged_vs_pr282_equals_main_change': hunks(vs_pr) == hunks(main_change)}
            (D / C('merge-diffs')).mkdir(exist_ok=True)
            for name, text in (('vs-main', vs_main), ('vs-pr282', vs_pr), ('pr282-change', pr_change), ('main-change', main_change)):
                (D / C('merge-diffs') / (path.replace('/', '__') + '.' + name + '.diff')).write_text(text)
            if not all(both.values()):
                problems.append({'path': path, **both})
            kind += ' ' + json.dumps(both)
        ok = got == expected
        if not ok:
            problems.append({'path': path, 'kind': kind, 'ok': False})
        rows.append({'path': path, 'kind': kind, 'sha256': sha(got) if got is not None else None, 'equal': ok})
    registry_row = {'path': REGISTRY, 'kind': 'both: hand-written objects merged three ways, generated part from main (regenerated later)',
                    'sha256': sha(show(head, REGISTRY, S)), 'equal': show(head, REGISTRY, S) == registry_raw,
                    'merge': rem['registry_merge']}
    if not registry_row['equal']:
        problems.append({'path': REGISTRY, 'ok': False})
    ctx = context_check(head)
    write_new(D / C('context-check.json'), ctx)
    if problems or not ctx['ok']:
        write_new(D / C('capture-stop.json'), {'at_utc': utc(), 'problems': problems, 'context_checks': ctx['checks']})
        raise SystemExit('source equality or context check failed; stop and report: ' + json.dumps({'problems': problems[:5], 'context': ctx['checks']}))
    write_new(D / C('source-equality.json'), {'merge_commit': head, 'tree': tree, 'parents': [HEAD282, BASE], 'rows': rows,
              'registry_row': registry_row, 'problems': problems, 'paths_vs_chain1_merge': vs_m1})
    write_new(D / C('capture.json'), dict(cap, base=BASE, pr282=HEAD282, merge_paths=merge_paths, context_check=str(D / C('context-check.json')),
              chain=CHAIN, chain1_merge_commit=M1, paths_vs_chain1_merge=vs_m1, non_force_successor_of_pr282_head=True,
              scientific_qualification=False))
    write_new(D / C('source.patch'), pgit(S, 'diff', '--binary', BASE, head))
    write_new(D / C('source.commit'), pgit(S, 'cat-file', 'commit', head))
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = entries(BASE), entries(head, S)
    assert set(prior) == set(old_rows)
    out, changed = [], []
    for path, (mode, oid) in sorted(after.items()):
        old = old_rows.get(path)
        if prior.get(path) == (mode, oid):
            assert (old['git_mode'], old['observed_blob_oid'], old['index_blob_oid']) == (mode, oid, oid), path
            value, actual_mode = old['sha256'], old['actual_mode']
        else:
            raw = (S / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid, path
            value, actual_mode = sha(raw), (S / path).stat().st_mode & 0o777
            changed.append(path)
        out.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual_mode, 'git_blob_oid': oid})
    expected_changed = sorted(p for p, s in names(BASE, head, S).items() if s != 'D')
    assert sorted(changed) == expected_changed, (len(changed), len(expected_changed))
    write_new(D / C('assets.json'), {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
              'source_commit': head, 'source_tree': tree, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
              'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
              'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': out,
              'reuse_proof': {'actual_CI': PUSH_RUN, 'observation': obs['assets_before'], 'observation_sha256': obs['assets_before_sha256'],
                              'unchanged': len(out) - len(changed), 'changed': changed}})
    print(json.dumps({'merge': head, 'tree': tree, 'paths': len(merge_paths), 'assets': len(out), 'changed_assets': len(changed),
                      'source_rows': len(rows), 'paths_vs_chain1_merge': vs_m1, 'context_ok': ctx['ok']}), flush=True)


def discover():
    """Brief item 4: reuse receipts by exact workflow entry, collector and owner-module hashes; collect again every entry
    that #282's changes hit (a changed test or Python helper module under its start, or an entry definition that #282's
    workflow change introduced), and every entry with a test module main changed since d6b7543f (the template's rule)."""
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not DISCOVERY.exists()
    candidates = {}
    for label, config_path in (('main', C0R3 / 'config.json'), ('pr282', R282 / 'config.json')):
        config = load(config_path)
        for item in config['discoveries']:
            path = Path(item['entry_file'])
            value = load(path)
            row = candidates.setdefault(str(path.resolve()), {'path': path, 'value': value, 'labels': [], 'locators': {}})
            row['labels'].append(label)
            row['locators'][label] = config['discovery_source_locators'][value['entry']['entry_id']]
    main_entries = [c['value']['entry'] for c in candidates.values() if 'main' in c['labels']]
    assert len(main_entries) == 31
    cap, plan = load(D / C('capture.json')), load(D / 'source-plan.json')
    pr_changed = sorted(set(plan['pr282_paths']) - DERIVED_DATA)
    main_changed = sorted(set(plan['main_paths']) - DERIVED_DATA)
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ.update(CI_INVENTORY_BASE=BASE, CI_INVENTORY_HEAD=cap['commit'], TMPDIR=str(TMP))
    inventory = module('act_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    found = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(found) == 31, len(found)
    assets = {r['path']: r['sha256'] for r in load(D / C('assets.json'))['assets']}
    chosen, new_count = [], 0
    for i, entry in enumerate(found):
        start = entry['start'].rstrip('/') + '/'

        def hit(paths, helpers):
            """Paths under start matching the entry's pattern; with helpers, also non-test Python modules there."""
            return sorted(p for p in paths if p.startswith(start) and (fnmatch.fnmatch(p.rsplit('/', 1)[-1], entry['pattern'])
                                                                       or (helpers and p.endswith('.py')
                                                                           and not p.rsplit('/', 1)[-1].startswith('test'))))
        reasons = {'pr282_changed_paths': hit(pr_changed, True), 'main_changed_paths': hit(main_changed, False),
                   'entry_definition_from_pr282_workflow': entry not in main_entries}
        forced = bool(reasons['pr282_changed_paths'] or reasons['main_changed_paths'] or reasons['entry_definition_from_pr282_workflow'])
        matching = []
        if not forced:
            for c in candidates.values():
                r = c['value']['receipt']
                if c['value']['entry'] != entry or not r['complete'] or r['errors'] or r['unresolved_instances']:
                    continue
                if assets.get(r['collector']['path']) != r['collector']['sha256']:
                    continue
                if any(assets.get(m['module_path']) != m['module_sha256'] for m in r['methods']):
                    continue
                matching.append(c)
            semantic = {json.dumps({k: v for k, v in c['value']['receipt'].items() if k != 'transport'}, sort_keys=True) for c in matching}
            assert len(semantic) <= 1, (entry['entry_id'], [str(c['path']) for c in matching])
        if matching:
            c = sorted(matching, key=lambda c: ('main' not in c['labels'], str(c['path'])))[0]
            label = 'main' if 'main' in c['labels'] else 'pr282'
            locator = c['locators'][label]
            assert all(v == locator for v in c['locators'].values()), (entry['entry_id'], c['locators'])
            assert show(locator['revision'], locator['path'], S) == c['path'].read_bytes()
            pgit(S, 'merge-base', '--is-ancestor', locator['revision'], ARCHIVE_TIP)
            row = {'entry_file': str(c['path']), 'entry_id': entry['entry_id'], 'reused': True, 'reused_from': c['labels'],
                   'source_locator': locator, 'matching_candidates': [[x['labels'], str(x['path'])] for x in matching],
                   'sha256': sha(c['path'].read_bytes()), 'instances': c['value']['receipt']['discovered_instances']}
        else:
            with KernelWatch(C('discover') + ' entry %03d' % i):
                r = inventory.child(S, entry, 900)
            assert r['complete'] and not r['errors'] and not r['unresolved_instances'], (entry['entry_id'], r['errors'][:2])
            path = NEW_DISCOVERY / ('entry-%03d.json' % i)
            write_new(path, {'entry': entry, 'receipt': r})
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': False, 'forced': forced, 'reasons': reasons,
                   'sha256': sha(path.read_bytes()), 'instances': r['discovered_instances']}
            new_count += 1
        row.update(start=entry['start'], pattern=entry['pattern'], namespace=entry['namespace'])
        chosen.append(row)
    write_new(DISCOVERY, {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen) - new_count,
              'new_collections': new_count, 'workflow_sha256': parsed['workflow_sha256'], 'pr282_changed_paths': pr_changed,
              'main_changed_paths': main_changed, 'archive_tip_checked': ARCHIVE_TIP, 'chain': CHAIN,
              'candidates': {'main': str(C0R3 / 'config.json'), 'pr282': str(R282 / 'config.json')},
              'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from main\'s last construction (merged as '
                             '#296) and #282\'s own construction (head 84d6b71f), receipts compared without their transport block; '
                             'entries hit by a test or Python helper module #282 changed under their start, entries whose '
                             'definition comes from #282\'s workflow change, and entries with a test module main changed since '
                             'd6b7543f are collected again here. The local and CI catalog-inventory recollect all 31 entries.',
              'test_bodies_executed': False, 'scientific_qualification': False})
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count,
                      'recollected': [[c['start'], c['pattern'], c['instances']] for c in chosen if not c['reused']]}), flush=True)


def union():
    """Previous catalog for generation: main's catalog (read from 0ad80828) plus every 84d6b71f object it lacks, and
    #282's current entries for the ids main's current lacks (main's entry wins where both have one)."""
    invariant()
    assert not UNION.exists() and not MAIN_DATA.exists() and not (D / C('union-acceptance.json')).exists()
    names_at_base = sorted(p for p in entries(BASE) if p.startswith(DATA) and '/' not in p[len(DATA):])
    MAIN_DATA.mkdir()
    for path in names_at_base:
        (MAIN_DATA / path[len(DATA):]).write_bytes(show(BASE, path))
    shutil.copytree(MAIN_DATA, UNION)
    writer = module('act_union_writer', S / 'scripts/capabilities/generate_catalog.py')
    header = load(UNION / 'registry.json')
    present = objects_dir(UNION)
    assert present == objects_at(BASE)
    docs = {name: load(UNION / name) for name in header['object_parts']}
    kind_file = {'sources': 'catalog-sources.json', 'assets': 'asset-index.json', 'entrypoints': 'entrypoint-index.json'}
    added, conflicts, by_part = [], [], {}
    pr_header = json.loads(show(HEAD282, REGISTRY))
    pr_parts = {'registry.json': pr_header['objects']}
    for part in pr_header['object_parts']:
        doc = json.loads(show(HEAD282, DATA + part))
        pr_parts[part] = (doc['kind'], doc['objects'])
    header_objects = list(header['objects'])
    for part, value in pr_parts.items():
        kind, items = (None, value) if part == 'registry.json' else value
        for obj in items:
            key = (obj['id'], obj['version'])
            if key in present:
                if present[key] != obj:
                    conflicts.append(list(key))
                continue
            if part == 'registry.json':
                header_objects.append(obj)
                target = 'registry.json'
            else:
                target = writer.part_file(kind, obj['id']) if kind in ('methods', 'history') else kind_file[kind]
                docs[target]['objects'].append(obj)
            present[key] = obj
            added.append({'part': target, 'id': obj['id'], 'version': obj['version']})
            by_part[target] = by_part.get(target, 0) + 1
    if conflicts:
        write_new(D / C('union-conflicts.json'), {'at_utc': utc(), 'conflicts': conflicts})
        raise SystemExit('conflicting catalog object versions between main and #282; stop and report: ' + json.dumps(conflicts[:5]))
    current_added = {i: v for i, v in pr_header['current'].items() if i not in header['current']}
    assert all((i, v) in present for i, v in current_added.items())
    header['objects'] = header_objects
    header['current'] = dict(header['current']) | current_added
    (UNION / 'registry.json').write_text(json.dumps(header, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    for name, doc in docs.items():
        (UNION / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    merged = objects_dir(UNION)
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
        retention[name] = {'revision': rev, 'objects': len(expected)}
    sys.path.insert(0, str(S / 'evas/capabilities'))
    registry = module('act_registry', S / 'evas/capabilities/registry.py')
    # registry.load needs the data inside the source root: the merge commit's data (main's parts, merged registry.json).
    names_in_tree = sorted(p.name for p in (S / DATA).glob('*.json'))
    assert names_in_tree == sorted(p[len(DATA):] for p in names_at_base)
    for name in names_in_tree:
        expected = load(D / C('remerge.json'))['registry_merge']['sha256']['merged'] if name == 'registry.json' else sha(show(BASE, DATA + name))
        assert sha((S / DATA / name).read_bytes()) == expected, name
    before = registry.load(S / DATA, root=S, repositories={'vaevas': S})
    candidate = copy.deepcopy(before.data)
    base_keys = set(objects_dir(S / DATA))
    candidate['objects'].extend(copy.deepcopy(obj) for key, obj in merged.items() if key not in base_keys)
    candidate['current'] = dict(header['current'])
    after = registry.Registry(candidate, root=S, repositories={'vaevas': S})
    assert after.data['current'] == header['current']
    kinds = {}
    for i in current_added:
        kinds[i.split(':')[0]] = kinds.get(i.split(':')[0], 0) + 1
    write_new(D / C('union-acceptance.json'), {'base': BASE, 'pr282': HEAD282, 'union_dir': str(UNION), 'main_data_dir': str(MAIN_DATA),
              'base_objects': len(objects_at(BASE)), 'pr282_objects': sum(len(v if k == 'registry.json' else v[1]) for k, v in pr_parts.items()),
              'added_from_pr282': len(added), 'added_by_part': by_part, 'conflicts': conflicts, 'union_objects': len(merged),
              'current_added_from_pr282': len(current_added), 'current_added_by_kind': kinds, 'current_entries': len(header['current']),
              'retention': retention, 'registry_validation_passed': True, 'added': added, 'scientific_qualification': False})
    print(json.dumps({'added_from_pr282': len(added), 'current_added_from_pr282': len(current_added), 'current_added_by_kind': kinds,
                      'union_objects': len(merged)}), flush=True)


def remote_archive():
    stamp = utc().replace(':', '').replace('-', '')[:15]
    return gh_json('repos/%s/git/ref/%s' % (REPO, ARCHIVE_REF.removeprefix('refs/')), W / 'gh' / ('archive-ref-' + stamp + '.json'))['object']['sha']


def archive():
    invariant()
    assert not (D / C('archive.json')).exists()
    tip = remote_archive()
    if tip != ARCHIVE_TIP:
        write_new(D / C('archive-tip-moved.json'), {'at_utc': utc(), 'expected': ARCHIVE_TIP, 'actual': tip})
        raise SystemExit('the archive tip moved; stop and report: ' + tip)
    assert not pgit(S, 'ls-tree', ARCHIVE_TIP, '--', PREFIX).strip(), 'archive tip already has the prefix'
    root = D / C('archive-files')
    dest = root / PREFIX
    dest.mkdir(parents=True)
    for name in ('remerge.json', 'capture.json', 'source.patch', 'source.commit', 'source-equality.json', 'context-check.json',
                 'union-acceptance.json'):
        shutil.copyfile(D / C(name), dest / name)
    for name in ('source-plan.json', 'source-preparation.json'):
        shutil.copyfile(D / name, dest / name)
    shutil.copyfile(DISCOVERY, dest / 'discovery-selection.json')
    shutil.copyfile(OBSERVED_RECEIPT, dest / 'observed-catalog-inventory-receipt.json')
    for src, sub in ((NEW_DISCOVERY, 'new-discovery'), (D / C('merge-diffs'), 'merge-diffs')):
        if src.exists():
            shutil.copytree(src, dest / sub)
    for path in (W / 'prepare_activation.py', W / 'common_act.py', W / 'fetch_observed.py'):
        shutil.copyfile(path, dest / path.name)
    (dest / 'README.md').write_text('# Capability batch 1 activation head\n\n'
        'The merge commit joins the capability batch 1 changes (head 84d6b71f) with main after the context registration '
        '(registration authority #296 and baseline append #297, main 0ad80828). Paths changed only by the batch keep its bytes '
        'and paths changed only by main keep main\'s. No source path is changed by both; `evas/capabilities/data/registry.json` '
        'keeps main\'s generated content and adds the eleven hand-written objects of the batch with their current entries '
        '(remerge.json), and the other catalog files are regenerated. Criteria, DUT, language profile and collector equal the '
        'batch head, so the registered sixth context applies (context-check.json). The catalog is regenerated from the union '
        'of both parents. Scientific qualification is false.\n')
    index = W / 'indexes' / (C('construction-archive') + '.index')
    assert not index.exists()
    index.parent.mkdir(exist_ok=True)
    pgit(S, 'read-tree', ARCHIVE_TIP, index=index)
    files = []
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
    commit = pgit(S, 'commit-tree', tree, '-p', ARCHIVE_TIP, '-m', 'Archive the capability batch 1 activation construction' + TRAILER).decode().strip()
    index.unlink()
    pgit(S, 'merge-base', '--is-ancestor', ARCHIVE_TIP, commit)
    assert not pgit(S, 'diff', '--name-only', ARCHIVE_TIP, commit, '--', ':!' + PREFIX).strip()
    write_new(D / C('archive.json'), {'parent': ARCHIVE_TIP, 'remote_tip_checked': tip, 'commit': commit, 'tree': tree, 'prefix': PREFIX,
              'files': files, 'published': False, 'object_store': str(S / '.git'), 'chain': CHAIN,
              'publication': 'fast-forward of ' + ARCHIVE_REF + ' from ' + ARCHIVE_TIP + ' (main session)'})
    config = load(C0R3 / 'config.json')
    pr_config = load(R282 / 'config.json')
    assert set(config) == set(pr_config)
    for key in ('archive_commit', 'bridge_evidence', 'readiness_file', 'readiness_source_locator'):
        assert config[key] == pr_config[key], key
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(UNION), asset_receipt=str(D / C('assets.json')),
                  source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={},
                  rust_listings=pr_config['rust_listings'])   # evas/rust_core of the merged head is #282's
    selection = load(DISCOVERY)
    for row in selection['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': commit, 'path': PREFIX + '/new-discovery/' + path.name}
        if not row['reused']:
            assert show(commit, PREFIX + '/new-discovery/' + path.name, S) == path.read_bytes()
    ids = {row['entry_id'] for row in selection['entries']}
    for bridge in config['bridge_evidence']:
        assert set(bridge['consumer_entry_ids']) <= ids, bridge['path']
    for listing in config['rust_listings']:
        pgit(S, 'merge-base', '--is-ancestor', listing['source_locator']['revision'], ARCHIVE_TIP)
        assert show(listing['source_locator']['revision'], listing['source_locator']['path'], S) == Path(listing['receipt_file']).read_bytes()
    write_new(D / C('config.json'), config)
    print(json.dumps({'construction_archive': commit, 'parent': ARCHIVE_TIP, 'files': len(files)}), flush=True)


def generate():
    """Generate twice from the same inputs; the two outputs must be byte-identical."""
    invariant()
    cap = load(D / C('capture.json'))
    assert load(D / C('config.json'))['previous_data_dir'] == str(UNION)
    assert not (D / C('generation-acceptance.json')).exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == cap['commit']
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    env = clean_env() | TOOLS | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    for name in (C('catalog'), C('catalog-repeat')):
        with KernelWatch('generate ' + name), (D / 'logs' / ('generation-' + name + '.stdout')).open('xb') as out, \
                (D / 'logs' / ('generation-' + name + '.stderr')).open('xb') as err:
            run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / C('config.json')),
                                  '--output', str(D / name)], cwd=S, env=env, stdout=out, stderr=err)
        assert run.returncode == 0, 'Read logs/generation-' + name + '.stderr'
    first, second = D / C('catalog') / 'tree/evas/capabilities/data', D / C('catalog-repeat') / 'tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(D / C('catalog') / 'generation-report.json')
    previous, current = objects_dir(UNION), objects_dir(first)
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
    inline_after = {(o['id'], o['version']): o for o in header['objects']}
    inline_sources = {}
    for name, rev in (('main', BASE), ('pr282_head', HEAD282)):
        parent = json.loads(show(rev, REGISTRY))
        inline = {(o['id'], o['version']): o for o in parent['objects']}
        kept = [k for k, v in inline.items() if inline_after.get(k) == v]
        assert len(kept) == len(inline), (name, 'hand-written registry objects changed or dropped', sorted(set(inline) - set(kept))[:5])
        lost = [i for (i, v) in inline if parent['current'].get(i) == v and header['current'].get(i) != v]
        assert not lost, (name, 'hand-written registry objects no longer current', lost)
        inline_sources[name] = {'objects': len(inline), 'kept_unchanged': len(kept), 'still_current': len(inline) - len(lost)}
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
    write_new(D / C('generation-acceptance.json'), {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
              'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind, 'new_object_ids': sorted({k[0] for k in new_objects}),
              'deterministic_double_generation': True, 'hand_written_registry_objects': inline_sources,
              'inline_registry_objects_after': len(inline_after), 'current_entries': len(header['current']),
              'version_lists': {'ids': len(versions), 'problems': 0,
                                'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
              'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
              'largest_data_file': max(sizes.items(), key=lambda x: x[1]), 'scientific_qualification': False})
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'new_object_versions': len(new_objects),
                      'by_kind': by_kind, 'hand_written': inline_sources, 'largest': max(sizes.items(), key=lambda x: x[1])}), flush=True)


def derive():
    invariant()
    assert not (D / C('derive-acceptance.json')).exists()
    results = []
    for name, argv in (('derive-traceability-generate.txt', [PY, '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data']),
                       ('derive-capability-render.txt', [PY, '-B', 'evas/capabilities/render.py'])):
        assert run_logged(D / 'logs' / C(name), argv, S, results, extra_env=TOOLS) == 0, name
    cap = load(D / C('capture.json'))
    paths = changed_vs(cap['commit'])
    rendered = set(render_outputs(S))
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    touched = [p for p in paths if p.startswith(tuple(d + '/' for d in CRITERIA_DIRS)) or p in COLLECTOR4 or p == LANGUAGE_PROFILE]
    assert not touched, touched
    write_new(D / C('derive-acceptance.json'), {'merge_commit': cap['commit'], 'paths_vs_merge': paths, 'render_outputs': len(rendered),
              'criteria_or_collector_paths_touched': touched, 'checks': results,
              'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
              'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'paths_vs_merge': paths}), flush=True)


def freeze():
    invariant()
    cap, der = load(D / C('capture.json')), load(D / C('derive-acceptance.json'))
    assert not (D / C('final-candidate.json')).exists()
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = changed_vs(cap['commit'])
    assert sorted(generated) == sorted(der['paths_vs_merge'])
    final = commit_paths(cap['commit'], generated, FINAL_MESSAGE, [cap['commit']], C('final'), entries(HEAD282) | entries(cap['commit'], S))
    for anc in (HEAD282, BASE, cap['commit']):
        pgit(S, 'merge-base', '--is-ancestor', anc, final['commit'])
    complete = sorted(pgit(S, 'diff', '--no-renames', '--name-only', BASE, final['commit']).decode().splitlines())
    criteria = sorted(p for p in complete if p.startswith(tuple(d + '/' for d in CRITERIA_DIRS)))
    dut = sorted(p for p in complete if p.startswith(tuple(d + '/' for d in DUT_DIRS)))
    collector = sorted(p for p in complete if p in COLLECTOR4 or p == LANGUAGE_PROFILE)
    vs_pr = sorted(pgit(S, 'diff', '--no-renames', '--name-only', HEAD282, final['commit']).decode().splitlines())
    leak = [p for p in vs_pr if (p.startswith(tuple(d + '/' for d in CRITERIA_DIRS + DUT_DIRS)) and manifest_path(p))
            or p in COLLECTOR4 or p == LANGUAGE_PROFILE]
    assert not leak, leak
    blobs, changed = [], set(complete)
    for line in pgit(S, 'ls-tree', '-r', '-l', final['commit']).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    views = {p: {'equals_pr282_head': show(final['commit'], p, S) == show(HEAD282, p), 'equals_main': show(final['commit'], p, S) == show(BASE, p)}
             for p in sorted(set(render_outputs(S)))
             if show(final['commit'], p, S) != show(HEAD282, p) or show(final['commit'], p, S) != show(BASE, p)}
    final.update(base=BASE, merge_commit=cap['commit'], pr282=HEAD282, complete_paths=complete, criteria_changes_vs_main=criteria,
                 dut_changes_vs_main=dut, collector_changes_vs_main=collector, paths_vs_pr282_head=vs_pr,
                 criteria_dut_collector_changes_vs_pr282_head=leak, derive=str(D / C('derive-acceptance.json')),
                 source_equality=str(D / C('source-equality.json')), context_check=str(D / C('context-check.json')),
                 views_differing_from_a_parent=views, large_unchanged_blobs=blobs, chain=CHAIN,
                 fast_forward_of=HEAD282, published=False, CI='pending', scientific_qualification=False)
    write_new(D / C('final-candidate.json'), final)
    write_new(D / C('candidate.patch'), pgit(S, 'diff', '--binary', BASE, final['commit']))
    write_new(D / C('candidate.patch.identity.json'), {'base': BASE, 'head': final['commit'], 'command': 'git diff --binary <base> <head>',
              'sha256': sha_file(D / C('candidate.patch'))[0]})
    pgit(S, 'reset', '--quiet', final['commit'])
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == final['commit']
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'complete_paths': len(complete), 'paths_vs_pr282': len(vs_pr),
                      'views_differing_from_a_parent': views}), flush=True)


def cargo_home():
    """CARGO_HOME inside W: copies of the local crates.io index cache and .crate files (read from ~/.cargo/registry).

    Cargo.lock has only crates.io dependencies; with CARGO_NET_OFFLINE=true cargo resolves from these copies and
    extracts sources under W/cargo-home/registry/src, so neither ~/.cargo nor the network is written or used."""
    home = Path(TOOLS['CARGO_HOME'])
    record = home.parent / 'cargo-home.json'
    if record.exists():
        return load(record)
    assert not home.exists()
    copied = {}
    for name in ('index', 'cache'):
        shutil.copytree(CARGO_HOME_SOURCE / name, home / 'registry' / name, symlinks=True)
        files = [p for p in (home / 'registry' / name).rglob('*') if p.is_file()]
        copied[name] = {'files': len(files), 'bytes': sum(p.stat().st_size for p in files)}
    lock = (S / 'evas/rust_core/Cargo.lock').read_text()
    sources = sorted(set(re.findall(r'^source = "([^"]+)"$', lock, re.M)))
    assert sources == ['registry+https://github.com/rust-lang/crates.io-index'], sources
    return load(write_new(record, {'cargo_home': str(home), 'copied_from': str(CARGO_HOME_SOURCE), 'copied': copied, 'at_utc': utc(),
                                   'lockfile_sources': sources, 'network': 'CARGO_NET_OFFLINE=true'}))


def precheck():
    """Local checks on the frozen head; they do not change a committed byte. Stops when one fails."""
    invariant()
    final = load(D / C('final-candidate.json'))
    assert not (D / C('precheck-acceptance.json')).exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == final['commit']
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    guard_start = guard(C('precheck-before'))
    cargo = cargo_home()
    results, failures = [], []
    paths = final['complete_paths']
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write_new(D / C('maintenance-plan.json'), {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths), 'focused': False,
              'scope': '#282 activation head: fast-checks lint (ruff 0.14.1, cargo fmt and clippy, generated metadata) plus every '
                       'static-checks Traceability step command; full scientific regression is CI only.'})
    fixtures = D / C('git-fixture-isolation')
    assert not fixtures.exists(), 'GIT_FIXTURE_RETAIN_DIR must not exist before the run'
    fast_env = TOOLS | {'PYTHONPATH': 'evas/src', 'CARGO_PROFILE_DEV_OPT_LEVEL': '1', 'CARGO_PROFILE_DEV_DEBUG_ASSERTIONS': 'true',
                        'CARGO_PROFILE_DEV_OVERFLOW_CHECKS': 'true'}
    static_env = TOOLS | {'GIT_FIXTURE_RETAIN_DIR': str(fixtures)}
    checks_dir = D / C('checks')
    steps = [('fast-checks-ci-lint.txt', [PY, '-B', 'scripts/ci_lint.py', '--plan', str(D / C('maintenance-plan.json'))], fast_env, ()),
             ('capability-views.txt', [PY, '-B', 'evas/capabilities/render.py', '--check'], TOOLS, ('PYTHONPATH',)),
             ('requirement-links.txt', [PY, '-B', 'evas/capabilities/requirement_links.py'], TOOLS, ('PYTHONPATH',)),
             ('static-1-traceability-check.txt', [PY, '-B', 'scripts/traceability.py', '--check', '--catalog-data', 'evas/capabilities/data'], static_env, ('PYTHONPATH',)),
             ('static-2-diagnostic-inventory-check.txt', [PY, '-B', 'scripts/diagnostic_inventory.py', '--check'], static_env, ('PYTHONPATH',)),
             ('static-3-verify-validation-version.txt', [PY, '-B', 'scripts/verify_validation_version.py'], static_env, ('PYTHONPATH',)),
             ('static-4-scripts-tests-full.txt', [PY, '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-v'], static_env, ('PYTHONPATH',)),
             ('static-5-capabilities-tests.txt', [PY, '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], static_env, ('PYTHONPATH',)),
             ('diff-check.txt', ['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], {}, ())]
    for name, argv, extra, remove in steps:
        rc = run_logged(checks_dir / name, argv, S, results, extra_env=extra, limit=3600, remove=remove)
        if rc:
            failures.append(name)
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip(), 'checks changed committed bytes'
    fixture_files = sorted(p.relative_to(fixtures).as_posix() for p in fixtures.rglob('*') if p.is_file()) if fixtures.exists() else []
    ran = {}
    for name in ('static-4-scripts-tests-full.txt', 'static-5-capabilities-tests.txt'):
        found = re.findall(r'^Ran (\d+) tests? in ', (checks_dir / name).read_text(), re.M)
        ran[name] = int(found[-1]) if found else None
    write_new(D / C('precheck-acceptance.json'), {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': paths,
              'checks': results, 'failures': failures, 'tests_ran': ran, 'git_fixture_retain_dir': str(fixtures),
              'git_fixture_files': fixture_files, 'cargo_home': cargo, 'ruff': 'ruff 0.14.1 in the lint venv (the fast-checks job installs ruff==0.14.1)',
              'rust_toolchain': '1.99.0 locally (CI 1.99.1; the local 1.99.1 has no clippy or rustfmt and installing needs the network)',
              'environment_note': 'lint venv python 3.12 (CI 3.12.15); TMPDIR inside W; Rust offline, no auto-install, CARGO_HOME inside W',
              'guard_before': guard_start, 'guard_after': guard(C('precheck-after')), 'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'checks': len(results), 'failures': failures, 'tests_ran': ran}), flush=True)
    if failures:
        raise SystemExit('precheck failures; stop and report: ' + ', '.join(failures))


def find_drift(value, path=''):
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if 'drift' in k.lower() and v:
                found.append(path + '/' + k)
            found += find_drift(v, path + '/' + k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += find_drift(v, path + '/%d' % i)
    return found


def inventory():
    invariant()
    final = load(D / C('final-candidate.json'))
    assert not (D / C('inventory-acceptance.json')).exists()
    assert pgit(S, 'rev-parse', 'HEAD').decode().strip() == final['commit']
    results = []
    out = D / C('catalog-inventory-local')
    assert run_logged(D / C('checks') / 'inventory-local.txt', [PY, '-B', 'scripts/capabilities/collect_ci_inventory.py', '--root', '.', '--output', str(out),
                      '--require-catalog', '--registry-data', 'evas/capabilities/data'], S, results,
                      extra_env=TOOLS | {'CI_INVENTORY_BASE': BASE, 'CI_INVENTORY_HEAD': final['commit']}, remove=('PYTHONPATH',)) == 0
    summary = load(out / 'summary.json')
    drift = find_drift(summary)
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], summary.get('errors')
    assert summary['source']['source_tree'] == final['tree'] and not drift, drift
    assert not pgit(S, 'status', '--porcelain=v1', '--untracked-files=no').strip()
    write_new(D / C('inventory-acceptance.json'), {'candidate': final['commit'], 'tree': final['tree'], 'checks': results, 'drift': drift,
              'summary': {k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count', 'denominators')},
              'explicit_checks': summary.get('explicit_checks'),
              'command_matches_CI_step': 'python3 -B scripts/capabilities/collect_ci_inventory.py --root . --output runs/catalog-inventory '
                                         '--require-catalog --registry-data evas/capabilities/data',
              'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'inventory': 'reconciled', 'entries': summary['entry_count'], 'denominators': summary['denominators'], 'drift': drift}), flush=True)


STAGES = ['source', 'remerge', 'capture', 'discover', 'union', 'archive', 'generate', 'derive', 'freeze', 'precheck', 'inventory']

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=STAGES)
    stage = parser.parse_args().stage
    try:
        globals()[stage]()
    except BaseException:
        write_new(D / 'failures' / (C(stage) + '-' + utc().replace(':', '') + '.json'), {'stage': stage, 'chain': CHAIN, 'at_utc': utc(),
                  'traceback': traceback.format_exc()})
        raise
