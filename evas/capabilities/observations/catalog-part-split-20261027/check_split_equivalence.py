"""Compare a monolithic catalog directory with a split one.

The logical registry is registry.json plus every file named by object_parts.
Object identity is (kind, id, version). Canonical bytes are
json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False).

Allowed differences are only the object_parts list and asset objects whose
current_path is one of the catalog's own data files (registry.json, either
side's part files, or the retired method-index.json / historical-index.json).
Every such difference is listed. Any other difference fails the check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

WARNING_BYTES = 50 * 1024 * 1024
DECIMAL_50MB = 50_000_000
DATA_PREFIX = 'evas/capabilities/data/'
RETIRED = {'historical-index.json', 'method-index.json'}


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def load_directory(data_dir):
    data_dir = Path(data_dir)
    header = json.loads((data_dir / 'registry.json').read_text())
    parts = header.get('object_parts')
    if not isinstance(parts, list) or len(parts) != len(set(parts)):
        raise ValueError('duplicate or invalid object_parts in ' + str(data_dir))
    documents = []
    index = {}
    versions = {}
    asset_paths = {}
    duplicates = []
    for name in parts:
        raw = (data_dir / name).read_bytes()
        document = json.loads(raw)
        if set(document) != {'schema_version', 'kind', 'objects'} or document['schema_version'] != 1:
            raise ValueError('part schema is not schema_version/kind/objects: ' + name)
        if not isinstance(document['objects'], list):
            raise ValueError('part objects are not a list: ' + name)
        documents.append({'name': name, 'bytes': len(raw), 'kind': document['kind'],
                          'objects': len(document['objects']), 'rows': document['objects']})
    rows = list(header.get('objects', []))
    for document in documents:
        rows.extend(document['rows'])
    for obj in rows:
        key = (obj.get('kind'), obj.get('id'), obj.get('version'))
        digest = canonical(obj)
        if key in index:
            duplicates.append({'key': list(key), 'same_bytes': index[key] == digest})
            continue
        index[key] = digest
        versions.setdefault((obj.get('kind'), obj.get('id')), []).append(obj.get('version'))
        if obj.get('kind') == 'asset':
            asset_paths[(obj.get('id'), obj.get('version'))] = obj.get('current_path')
    for key, values in versions.items():
        values.sort()
    for document in documents:
        document.pop('rows')
    return {'header': header, 'parts': documents, 'index': index, 'versions': versions,
            'asset_paths': asset_paths, 'duplicates': duplicates}


def part_names(loaded):
    return set(loaded['header'].get('object_parts', []))


def catalog_data_path(path, names):
    if not isinstance(path, str) or not path.startswith(DATA_PREFIX):
        return False
    name = path[len(DATA_PREFIX):]
    return '/' not in name and (name == 'registry.json' or name in RETIRED or name in names)


def catalog_asset_ids(before, after, names):
    flags = {}
    for loaded in (before, after):
        for (object_id, version), path in loaded['asset_paths'].items():
            flags.setdefault(object_id, []).append(catalog_data_path(path, names))
    allowed = {object_id for object_id, values in flags.items() if values and all(values)}
    mixed = sorted(object_id for object_id, values in flags.items() if any(values) and not all(values))
    return allowed, mixed


def path_reason(path):
    name = path.rsplit('/', 1)[-1]
    if name in RETIRED:
        return ('该文件是拆分前的 methods 或 history 单体 part。拆分后 object_parts 不再列出它；'
                '同一输入收据仍观察得到这个路径，所以写入端按普通源码文件保留其资产身份。')
    if name.startswith('method-index-') or name.startswith('historical-index-'):
        return ('该文件是 methods 或 history 的固定 part。写入端把它登记为目录元数据资产；'
                '同一次输入收据还没有这个新文件。')
    return '该文件是目录自身的数据文件，其资产记录可以随 object_parts 变化，差异必须单独列出。'


def compare(before_dir, after_dir, committed_dir=None):
    before = load_directory(before_dir)
    after = load_directory(after_dir)
    names = part_names(before) | part_names(after)
    allowed_ids, mixed_ids = catalog_asset_ids(before, after, names)
    allowed = []
    unexpected = []
    if before['duplicates'] or after['duplicates']:
        unexpected.append({'class': 'duplicate-object-version', 'before': before['duplicates'][:20],
                           'after': after['duplicates'][:20]})
    if mixed_ids:
        unexpected.append({'class': 'mixed-catalog-asset-id', 'ids': mixed_ids,
                           'reason': '同一资产 id 同时有目录数据路径和其他路径，不能整类放过'})

    if before['header'].get('object_parts') != after['header'].get('object_parts'):
        allowed.append({'class': 'registry-field', 'field': 'object_parts',
                        'before': before['header'].get('object_parts'),
                        'after': after['header'].get('object_parts'),
                        'reason': 'methods 与 history 各写成固定数量的 part；sources、assets、entrypoints 仍是单文件。读端按该列表加载。'})

    before_keys = set(before['index'])
    after_keys = set(after['index'])
    for key in sorted(before_keys & after_keys):
        if before['index'][key] != after['index'][key]:
            unexpected.append({'class': 'canonical-mismatch', 'kind': key[0], 'id': key[1], 'version': key[2],
                               'before_sha256': before['index'][key], 'after_sha256': after['index'][key]})
    for key in sorted(before_keys ^ after_keys):
        side = 'before-only' if key in before_keys else 'after-only'
        loaded = before if key in before_keys else after
        path = loaded['asset_paths'].get((key[1], key[2]))
        item = {'class': 'object-' + side, 'kind': key[0], 'id': key[1], 'version': key[2],
                'sha256': loaded['index'][key], 'current_path': path}
        if key[0] == 'asset' and key[1] in allowed_ids and catalog_data_path(path, names):
            item['reason'] = path_reason(path)
            allowed.append(item)
        else:
            unexpected.append(item)

    for kind, object_id in sorted(set(before['versions']) | set(after['versions'])):
        left = before['versions'].get((kind, object_id))
        right = after['versions'].get((kind, object_id))
        if left == right:
            continue
        item = {'class': 'version-list', 'kind': kind, 'id': object_id, 'before': left, 'after': right}
        if kind == 'asset' and object_id in allowed_ids:
            paths = []
            for loaded in (before, after):
                for (asset_id, version), path in loaded['asset_paths'].items():
                    if asset_id == object_id:
                        paths.append(path)
            item['current_paths'] = sorted(set(paths))
            item['reason'] = '该资产 id 只对应目录数据文件，版本列表可以随这些文件的登记变化。'
            allowed.append(item)
        else:
            unexpected.append(item)

    before_current = before['header'].get('current', {})
    after_current = after['header'].get('current', {})
    for object_id in sorted(set(before_current) | set(after_current)):
        if before_current.get(object_id) == after_current.get(object_id):
            continue
        item = {'class': 'current', 'id': object_id, 'before': before_current.get(object_id),
                'after': after_current.get(object_id)}
        if object_id in allowed_ids:
            chosen = after_current.get(object_id) or before_current.get(object_id)
            path = after['asset_paths'].get((object_id, chosen)) or before['asset_paths'].get((object_id, chosen))
            item['current_path'] = path
            item['reason'] = 'current 变化只指向目录数据文件资产。' + (path_reason(path) if path else '')
            allowed.append(item)
        else:
            unexpected.append(item)

    skip = {'object_parts', 'current', 'objects'}
    for field in sorted((set(before['header']) | set(after['header'])) - skip):
        if before['header'].get(field) != after['header'].get(field):
            unexpected.append({'class': 'registry-field', 'field': field})
    before_header = {(obj.get('kind'), obj.get('id'), obj.get('version')): canonical(obj)
                     for obj in before['header'].get('objects', [])}
    after_header = {(obj.get('kind'), obj.get('id'), obj.get('version')): canonical(obj)
                    for obj in after['header'].get('objects', [])}
    for key in sorted(set(before_header) | set(after_header)):
        if before_header.get(key) == after_header.get(key):
            continue
        if key[0] == 'asset' and key[1] in allowed_ids:
            allowed.append({'class': 'header-object', 'kind': key[0], 'id': key[1], 'version': key[2],
                            'reason': 'registry.json 内联对象里的目录数据文件资产。'})
        else:
            unexpected.append({'class': 'header-object', 'kind': key[0], 'id': key[1], 'version': key[2]})

    def placement(loaded):
        files = {}
        id_files = {}
        for document in loaded['parts']:
            files.setdefault(document['kind'], []).append(document['name'])
        # Re-read is unnecessary: id placement uses versions plus a second pass over files.
        return {'files_by_kind': {kind: names_for for kind, names_for in files.items()},
                'empty_parts': [document['name'] for document in loaded['parts'] if document['objects'] == 0]}

    def same_file(data_dir, loaded):
        located = {}
        header = loaded['header']
        for name in header.get('object_parts', []):
            document = json.loads((Path(data_dir) / name).read_text())
            if document.get('kind') not in ('methods', 'history'):
                continue
            for obj in document['objects']:
                located.setdefault(obj['id'], set()).add(name)
        violations = sorted(object_id for object_id, names_for in located.items() if len(names_for) != 1)
        return {'same_id_single_file': not violations, 'violations': violations[:20],
                'tracked_ids': len(located)}

    after_parts = sorted(after['parts'], key=lambda item: item['name'])
    largest = max(after_parts, key=lambda item: item['bytes'])
    result = {
        'ok': not unexpected and not before['duplicates'] and not after['duplicates'],
        'before': str(before_dir),
        'after': str(after_dir),
        'object_counts': {'before': len(before['index']), 'after': len(after['index'])},
        'allowed_difference_count': len(allowed),
        'unexpected_difference_count': len(unexpected),
        'allowed_differences': allowed,
        'unexpected_differences': unexpected,
        'parts': {'before': [{key: document[key] for key in ('name', 'bytes', 'kind', 'objects')}
                             for document in before['parts']],
                  'after': [{key: document[key] for key in ('name', 'bytes', 'kind', 'objects')}
                            for document in after_parts]},
        'max_part': {'name': largest['name'], 'bytes': largest['bytes'], 'kind': largest['kind'],
                     'ratio_to_50_mib': largest['bytes'] / WARNING_BYTES,
                     'ratio_to_50_000_000': largest['bytes'] / DECIMAL_50MB,
                     'warning_line_bytes': WARNING_BYTES,
                     'below_warning_line': largest['bytes'] < WARNING_BYTES},
        'placement': {'before': {**placement(before), **same_file(before_dir, before)},
                      'after': {**placement(after), **same_file(after_dir, after)}},
    }
    if committed_dir is not None:
        committed = load_directory(committed_dir)
        missing = [list(key) for key in sorted(set(committed['index']) - set(after['index']))]
        rewritten = [list(key) for key in sorted(set(committed['index']) & set(after['index']))
                     if committed['index'][key] != after['index'][key]]
        result['committed_retention'] = {
            'committed': str(committed_dir), 'committed_objects': len(committed['index']),
            'missing_count': len(missing), 'rewritten_count': len(rewritten),
            'missing': missing[:50], 'rewritten': rewritten[:50],
            'ok': not missing and not rewritten}
        result['ok'] = result['ok'] and result['committed_retention']['ok']
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--committed', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare(args.before, args.after, args.committed)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(text)
    print(json.dumps({key: result[key] for key in
                      ('ok', 'object_counts', 'allowed_difference_count', 'unexpected_difference_count', 'max_part')
                      if key in result}, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
