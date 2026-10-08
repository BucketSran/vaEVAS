"""Statically combine three complete CMP8 executions with frozen Spectre evidence."""
from __future__ import annotations
import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import hashlib

from records import ROOT, BACKENDS, load, sha, validate, identity, evidence_ok
from freeze import SELECTED, save
from refresh import KEYS, read, reference

NEW_BACKENDS = ('openvaf_ngspice', 'gnucap', 'evas')
REUSE = 'Original Spectre receipt retained; physical inputs, checker and runtime match the completed target.'


# This bridge covers the inspected PR87 delta only. It is not a rule that
# test filenames are outside execution dependencies.
BRIDGE_REVISIONS = ('66173cfc140c0763cf5cc4d31fe95d284645b786',
                    'd4b41c797840f17222121592b9fa6f16e11e2c2b')
BRIDGE_DELTA = 'experiments/backends/dvs2-spectre-validation/test_triangle_oscillator.py'
BRIDGE_HASHES = ('8ad2b13b75cafe9c971b93f68e8a86164eba134df29d3babffa4b4fb01adb30f',
                 '2d162e2f0e0a4905e3f79b41ba52f0742bc746e3ad64256669bdcb1fca0f8c02')
CHECKER_DIRECTORIES = ('experiments/backends/dvs2-spectre-validation',
                       'experiments/archive/dvs2-history-validation',
                       'experiments/archive/dvs2-starter-pilot')
# Direct non-standard-library import closure of check_results.check/read_waveform:
# check_results -> run_suite -> suite; analyze -> suite; recheck -> history/analyze.
CHECKER_CLOSURE = ('experiments/backends/dvs2-spectre-validation/check_results.py',
                   'experiments/backends/dvs2-spectre-validation/run_suite.py',
                   'experiments/archive/dvs2-starter-pilot/analyze.py',
                   'experiments/archive/dvs2-starter-pilot/suite.py',
                   'experiments/archive/dvs2-history-validation/history.py',
                   'experiments/archive/dvs2-history-validation/recheck.py')


def fixed_git(arguments, root):
    try:
        return subprocess.check_output(['git', *arguments], cwd=root, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ValueError('missing fixed checker Git blob: ' + ' '.join(arguments)) from exc


def retained_reference(ref, root):
    evidence_ok(ref, root)
    prefix = (root / 'experiments/backends/comparison').resolve()
    if not (root / ref['path']).resolve().is_relative_to(prefix):
        raise ValueError('checker reanalysis requires retained comparison evidence')


def checker_sources(revision, root=ROOT):
    paths = []
    for directory in CHECKER_DIRECTORIES:
        listed = fixed_git(['ls-tree', '-r', '--name-only', revision, '--', directory], root).decode().splitlines()
        paths.extend(p for p in listed if p.endswith('.py') and Path(p).parent == Path(directory))
    return {p: hashlib.sha256(fixed_git(['show', revision + ':' + p], root)).hexdigest()
            for p in sorted(paths)}


def check_checker_reanalysis(proof, parent, old_manifest, new_manifest, root=ROOT):
    """Validate the finite PR87 bridge while retaining original executions."""
    if (proof.get('kind') != 'cmp8-pr87-fixed-checker-reanalysis' or
            (proof.get('old_revision'), proof.get('new_revision')) != BRIDGE_REVISIONS or
            proof.get('simulation_launches') != 0):
        raise ValueError('unknown checker reanalysis boundary')
    for ref in [proof['parent'], proof['analysis_driver'], proof['analysis_runner'],
                *proof['inputs'].values(),
                *(r['old_receipt'] for r in proof.get('rows', [])),
                *(r['assessment'] for r in proof.get('rows', []))]:
        retained_reference(ref, root)
    expected_runner = hashlib.sha256(fixed_git(['show',
        BRIDGE_REVISIONS[1] + ':experiments/backends/comparison/runner.py'], root)).hexdigest()
    if proof['analysis_runner']['sha256'] != expected_runner or proof['analysis_runner_sha256'] != expected_runner:
        raise ValueError('checker reanalysis runner identity mismatch')
    sources = [checker_sources(rev, root) for rev in BRIDGE_REVISIONS]
    if any(proof.get(name + '_sources') != source or identity(source) != proof.get(name + '_checker_identity')
           for name, source in zip(('old', 'new'), sources)):
        raise ValueError('checker reanalysis source identity mismatch')
    if (sources[0].keys() != sources[1].keys() or
            {p for p in sources[0] if sources[0][p] != sources[1][p]} != {BRIDGE_DELTA} or
            tuple(source[BRIDGE_DELTA] for source in sources) != BRIDGE_HASHES or
            any(sources[0].get(p) != sources[1].get(p) or p not in sources[0] for p in CHECKER_CLOSURE)):
        raise ValueError('unknown executable checker dependency change')
    if read(proof['parent'], root) != parent:
        raise ValueError('checker reanalysis parent mismatch')
    for name, manifest in (('old', old_manifest), ('new', new_manifest)):
        refs = proof['inputs']
        if read(refs[name + '_INPUT_MANIFEST.json'], root) != manifest:
            raise ValueError('checker reanalysis input manifest mismatch')
        provenance_ref = refs[name + '_provenance.json']
        provenance = read(provenance_ref, root)
        if (manifest.get('provenance.json') != {'sha256': provenance_ref['sha256'],
                'bytes': (root / provenance_ref['path']).stat().st_size} or
                provenance['checker_identity'] != proof[name + '_checker_identity']):
            raise ValueError('checker reanalysis provenance mismatch')
    old_rows = {r['case']: r for r in parent['records'] if r['dataset'] == 'cmp8-base' and r['backend'] == 'spectre'}
    rows = proof.get('rows', [])
    if len(rows) != 8 or {r['case'] for r in rows} != set(SELECTED):
        raise ValueError('checker reanalysis requires eight unique assessments')
    for row in rows:
        original = old_rows[row['case']]
        if row['old_receipt'] != original['execution_receipt']:
            raise ValueError('checker reanalysis original receipt changed')
        receipt = read(row['old_receipt'], root)
        assessment = read(row['assessment'], root)
        if (row.get('assessment_sha256') != row['assessment']['sha256'] or
                row['waveform_sha256'] != receipt['waveform_sha256'] or
                assessment != read(receipt['observation'], root) or
                receipt['checker_identity'] != proof['old_checker_identity'] or
                receipt['input_manifest_sha256'] != proof['inputs']['old_INPUT_MANIFEST.json']['sha256']):
            raise ValueError('checker reanalysis raw or assessment changed')
        for filename in ('condition.json', 'dut.va', 'requested_settings.json', 'tb.scs'):
            path = f'runs/spectre/{row["case"]}/base/{filename}'
            if path not in old_manifest or old_manifest[path] != new_manifest.get(path):
                raise ValueError('checker reanalysis physical input changed')


def check_completion(data, root=ROOT):
    proof = data['completion']
    parent = read(proof['parent'], root)
    fresh = read(proof['fresh'], root)
    if (data['schema_version'] != 2 or parent['schema_version'] != 2 or fresh['schema_version'] != 2
            or fresh.get('completion') or fresh.get('refresh') or data.get('refresh')):
        raise ValueError('completion requires schema2 and a separate fresh execution snapshot')
    validate(parent, root)
    validate(fresh, root)
    if data['updated'] != fresh['updated']:
        raise ValueError('completion updated differs from fresh snapshot')
    for name in ('old_manifest', 'new_manifest', 'old_provenance', 'new_provenance'):
        retained_reference(proof[name], root)
    for name in ('datasets', 'coverage', 'tools', 'components', 'candidate_links'):
        if data.get(name) != parent.get(name):
            raise ValueError('completion changed an unrelated dataset, component or candidate')
    for snapshot in (parent, fresh):
        batch = next(d for d in snapshot['datasets'] if d['id'] == 'cmp8-base')
        if {c['id'] for c in batch['cases']} != set(SELECTED) or batch['profiles'] != ['base'] or batch['denominator'] != 8:
            raise ValueError('completion only accepts fixed CMP8 base cases')
    if (next(d for d in parent['datasets'] if d['id'] == 'cmp8-base')['cases'] !=
            next(d for d in fresh['datasets'] if d['id'] == 'cmp8-base')['cases']):
        raise ValueError('completion changed frozen physical cases')
    expected_targets = copy.deepcopy(parent['targets'])
    for backend in NEW_BACKENDS:
        expected_targets[backend] = fresh['targets'][backend]
    if data['targets'] != expected_targets or fresh['targets']['spectre'] != parent['targets']['spectre']:
        raise ValueError('completion target identity mismatch')
    manifests = {name: read(proof[name + '_manifest'], root) for name in ('old', 'new')}
    provenance = {name: read(proof[name + '_provenance'], root) for name in ('old', 'new')}
    for name in ('old', 'new'):
        ref = proof[name + '_provenance']
        if manifests[name].get('provenance.json') != {'sha256': ref['sha256'], 'bytes': (root / ref['path']).stat().st_size}:
            raise ValueError('completion provenance differs from manifest')
    checker = provenance['new']['checker_identity']
    if checker != provenance['old']['checker_identity']:
        if 'checker_reanalysis' not in proof:
            raise ValueError('completion checker changed without bounded reanalysis')
        retained_reference(proof['checker_reanalysis'], root)
        bridge = read(proof['checker_reanalysis'], root)
        check_checker_reanalysis(bridge, parent, manifests['old'], manifests['new'], root)
        if (bridge['old_checker_identity'] != provenance['old']['checker_identity'] or
                bridge['new_checker_identity'] != checker):
            raise ValueError('completion checker reanalysis identity mismatch')
    elif 'checker_reanalysis' in proof:
        raise ValueError('unnecessary checker reanalysis bridge')
    if provenance['new']['evas_runtime_identity'] != fresh['targets']['evas']['runtime_identity']:
        raise ValueError('completion checker or runtime provenance mismatch')
    key = lambda row: tuple(row[k] for k in KEYS)
    old_rows = {key(r): r for r in parent['records']}
    new_rows = {key(r): r for r in fresh['records']}
    actual = {key(r): r for r in data['records']}
    if actual.keys() != old_rows.keys() or new_rows.keys() != old_rows.keys() or len(actual) != len(data['records']):
        raise ValueError('completion changed the configuration denominator')
    previous_ids = {r['measurement']['run_id'] for r in parent['records']
                    if r['dataset'] == 'cmp8-base' and r.get('measurement')}
    new_ids = set()
    for backend in NEW_BACKENDS:
        rows = [r for r in fresh['records'] if r['dataset'] == 'cmp8-base' and r['backend'] == backend]
        if len(rows) != 8 or any(r['accounting'] != 'executed' or not r.get('measurement') for r in rows):
            raise ValueError('completion requires all eight execution outcomes, including failures')
        identities = {(r['measurement']['run_id'], r['measurement']['revision'],
                       r['measurement']['runtime_identity'], r['measurement'].get('kernel_sha256')) for r in rows}
        if len(identities) != 1:
            raise ValueError('completion mixed execution identities')
        run_id = next(iter(identities))[0]
        if run_id in previous_ids or run_id in new_ids:
            raise ValueError('completion duplicated an existing run identity')
        new_ids.add(run_id)
    for key_value, old in old_rows.items():
        row = actual[key_value]
        if old['dataset'] != 'cmp8-base':
            if row != old:
                raise ValueError('completion changed a historical record')
            continue
        new = new_rows[key_value]
        backend = old['backend']
        filenames = ('condition.json', 'dut.va', 'requested_settings.json')
        if backend != 'evas':
            filenames += ({'spectre': 'tb.scs', 'openvaf_ngspice': 'tb.cir', 'gnucap': 'tb.gc'}[backend],)
        for filename in filenames:
            path = f'runs/{backend}/{old["case"]}/base/{filename}'
            if path not in manifests['old'] or manifests['old'][path] != manifests['new'].get(path):
                raise ValueError('completion changed frozen physical input: ' + path)
        if backend in NEW_BACKENDS:
            if row != new or row['qualification'] != 'I':
                raise ValueError('completion changed a new outcome or upgraded formal qualification')
            receipt = read(row['execution_receipt'], root)
            measured = row['measurement']
            if (not receipt.get('started_sha256') or
                receipt['input_manifest_sha256'] != proof['new_manifest']['sha256'] or
                receipt['checker_identity'] != checker or
                measured['revision'] != data['targets'][backend]['revision'] or
                measured['runtime_identity'] != data['targets'][backend]['runtime_identity']):
                raise ValueError('completion fresh execution identity mismatch')
        else:
            if old['accounting'] not in ('executed', 'reused') or new['accounting'] != 'unrun':
                raise ValueError('completion must reuse Spectre rather than launch or replace it')
            if row != dict(old, accounting='reused', reuse_justification=REUSE):
                raise ValueError('completion changed original Spectre evidence or observation')
            receipt = read(old['execution_receipt'], root)
            if (receipt['input_manifest_sha256'] != proof['old_manifest']['sha256'] or
                receipt['checker_identity'] != provenance['old']['checker_identity'] or
                receipt['runtime_identity'] != data['targets']['spectre']['runtime_identity']):
                raise ValueError('completion Spectre reuse identity mismatch')
        source = f'runs/{backend}/{old["case"]}/base/dut.va'
        if receipt['source_sha256'] != manifests['new'][source]['sha256']:
            raise ValueError('completion source differs from frozen DUT')


def complete(parent_snapshot, fresh_snapshot, old_inputs, new_inputs, evidence, root=ROOT, checker_reanalysis=None):
    evidence = evidence.resolve()
    if (not evidence.is_relative_to((root / 'experiments/backends/comparison').resolve()) or
            any(evidence.is_relative_to(p.resolve()) for p in (old_inputs, new_inputs))):
        raise ValueError('completion archive requires retained comparison evidence outside frozen inputs')
    parent = load(parent_snapshot)
    fresh = load(fresh_snapshot)
    validate(parent, root)
    validate(fresh, root)
    data = copy.deepcopy(parent)
    data['updated'] = fresh['updated']
    for name in ('derivation', 'refresh', 'completion'):
        if name in data:
            data['prior_' + name] = data.pop(name)
    for backend in NEW_BACKENDS:
        data['targets'][backend] = copy.deepcopy(fresh['targets'][backend])
    new_rows = {tuple(r[k] for k in KEYS): r for r in fresh['records']}
    for i, row in enumerate(data['records']):
        if row['dataset'] != 'cmp8-base':
            continue
        if row['backend'] in NEW_BACKENDS:
            data['records'][i] = copy.deepcopy(new_rows[tuple(row[k] for k in KEYS)])
        else:
            row.update(accounting='reused', reuse_justification=REUSE)
    sources = {'parent': parent_snapshot, 'fresh': fresh_snapshot,
               'old_manifest': old_inputs / 'INPUT_MANIFEST.json', 'new_manifest': new_inputs / 'INPUT_MANIFEST.json',
               'old_provenance': old_inputs / 'provenance.json', 'new_provenance': new_inputs / 'provenance.json'}
    data['completion'] = {name: reference(path, root) for name, path in sources.items()}
    if checker_reanalysis is not None:
        data['completion']['checker_reanalysis'] = reference(checker_reanalysis, root)
    evidence.mkdir(parents=True, exist_ok=False)
    for name in ('old_manifest', 'new_manifest', 'old_provenance', 'new_provenance'):
        path = evidence / (name + '.json')
        shutil.copyfile(sources[name], path)
        data['completion'][name] = reference(path, root)
    check_completion(data, root)
    data['limits'] = ['Frozen parent limitation: ' + line for line in parent.get('limits', [])] + [
        'Three backend batches have new finite execution outcomes, including any failures; Spectre is reused. Formal qualification remains I.']
    if checker_reanalysis is not None:
        data['limits'].append('Spectre原执行/判定保留；8项原raw在固定PR87 checker聚合变化后重新分析，观察完全相同，重分析不增加仿真次数。')
    evas = next(r for r in data['records'] if r['dataset'] == 'cmp8-base' and r['backend'] == 'evas')
    measured = evas['measurement']
    tool = read(evas['execution_receipt'], root)['tool']
    data['limits'].append(f"EVAS执行源码 {measured['revision']}，runtime {measured['runtime_identity']}；实际内核SHA {measured['kernel_sha256']}，自报版本 {tool.get('kernel_version', 'unknown')}。内核build revision未知时仍为未知。")
    validate(data, root)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'fresh', 'old_inputs', 'new_inputs', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--checker-reanalysis', type=Path)
    args = parser.parse_args()
    save(args.output, complete(args.parent, args.fresh, args.old_inputs, args.new_inputs, args.evidence, checker_reanalysis=args.checker_reanalysis))


if __name__ == '__main__':
    main()
