"""Statically combine three complete CMP8 executions with frozen Spectre evidence."""
from __future__ import annotations
import argparse
import copy
from pathlib import Path
import shutil

from records import ROOT, BACKENDS, load, sha, validate
from freeze import SELECTED, save
from refresh import KEYS, read, reference

NEW_BACKENDS = ('openvaf_ngspice', 'gnucap', 'evas')
REUSE = 'Original Spectre receipt retained; physical inputs, checker and runtime match the completed target.'


def check_completion(data, root=ROOT):
    proof = data['completion']
    parent = read(proof['parent'], root)
    fresh = read(proof['fresh'], root)
    if (data['schema_version'] != 2 or parent['schema_version'] != 2 or fresh['schema_version'] != 2
            or fresh.get('completion') or fresh.get('refresh') or data.get('refresh')):
        raise ValueError('completion requires schema2 and a separate fresh execution snapshot')
    validate(parent, root)
    validate(fresh, root)
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
    if checker != provenance['old']['checker_identity'] or provenance['new']['evas_runtime_identity'] != fresh['targets']['evas']['runtime_identity']:
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
                receipt['checker_identity'] != checker or
                receipt['runtime_identity'] != data['targets']['spectre']['runtime_identity']):
                raise ValueError('completion Spectre reuse identity mismatch')
        source = f'runs/{backend}/{old["case"]}/base/dut.va'
        if receipt['source_sha256'] != manifests['new'][source]['sha256']:
            raise ValueError('completion source differs from frozen DUT')


def complete(parent_snapshot, fresh_snapshot, old_inputs, new_inputs, evidence, root=ROOT):
    parent = load(parent_snapshot)
    fresh = load(fresh_snapshot)
    validate(parent, root)
    validate(fresh, root)
    data = copy.deepcopy(parent)
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
    check_completion(data, root)
    evidence = evidence.resolve()
    if not evidence.is_relative_to(root.resolve()) or any(evidence.is_relative_to(p.resolve()) for p in (old_inputs, new_inputs)):
        raise ValueError('completion archive must stay in repository and outside frozen inputs')
    evidence.mkdir(parents=True, exist_ok=False)
    for name in ('old_manifest', 'new_manifest', 'old_provenance', 'new_provenance'):
        path = evidence / (name + '.json')
        shutil.copyfile(sources[name], path)
        data['completion'][name] = reference(path, root)
    data['limits'] = ['Frozen parent limitation: ' + line for line in parent.get('limits', [])] + [
        'Three backend batches have new finite execution outcomes, including any failures; Spectre is reused. Formal qualification remains I.']
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
    args = parser.parse_args()
    save(args.output, complete(args.parent, args.fresh, args.old_inputs, args.new_inputs, args.evidence))


if __name__ == '__main__':
    main()
