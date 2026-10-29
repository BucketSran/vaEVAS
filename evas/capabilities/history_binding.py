"""Fixed original-source protocols. No caller-supplied field projections."""
import re

PROTOCOLS = {'evas-method-audit-3257-v1': ('historical-audit-record', '/rows/', '/summary/scope'),
             'evas-passing-oracles-v1': ('historical-finding', '/confirmed/', '/scope'),
             'evas-passing-negative-v1': ('historical-finding', '/findings/', ''),
             'evas-passing-raw-v1': ('historical-finding', '/findings/', '')}


def shape(obj):
    binding = obj.get('identity_binding')
    status = obj.get('alignment', {}).get('status')
    if status not in ('pending', 'matched') or binding not in ('bound', 'unbound'):
        raise ValueError('history needs explicit binding and alignment status')
    refs = ([obj['method']] if 'method' in obj else obj.get('methods', []))
    if 'method' in obj and 'methods' in obj:
        raise ValueError('ambiguous historical method references')
    protocol = obj.get('history_protocol')
    if protocol is not None and protocol not in PROTOCOLS:
        raise ValueError('unknown historical source protocol')
    if binding == 'unbound':
        if refs or status != 'pending':
            raise ValueError('unbound history cannot borrow a method or claim matched')
        return []
    if protocol not in PROTOCOLS or not isinstance(refs, list) or not refs:
        raise ValueError('bound history requires a fixed protocol and methods')
    if any(not isinstance(ref, dict) or set(ref) != {'id', 'version', 'sha256'} for ref in refs):
        raise ValueError('invalid historical method reference schema')
    kind, prefix, scope = PROTOCOLS[protocol]
    if obj['kind'] != kind or obj['scope_pointer'] != scope or not re.fullmatch(re.escape(prefix)+r'(0|[1-9][0-9]*)', obj['row_pointer']):
        raise ValueError('historical source protocol/kind/pointer mismatch')
    if kind == 'historical-finding' and status == 'matched':
        raise ValueError('original finding protocols cannot claim full method matched')
    if kind == 'historical-audit-record' and len(refs) != 1:
        raise ValueError('audit rows have exactly one subject')
    return refs


def _copied(obj, field, actual):
    if field in obj and (actual is None or obj[field] != actual):
        raise ValueError('copied historical field differs from actual source: ' + field)


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate(obj, document, row, methods):
    shape(obj)
    if not isinstance(row, dict):
        raise ValueError('historical row must be an object')
    if obj['identity_binding'] == 'unbound':
        _copied(obj, 'original_verdict', row.get('verdict'))
        if any(key in obj for key in ('source_method_sha256', 'source_module_sha256')):
            raise ValueError('unbound source cannot assert method/module identity')
        return
    protocol = obj['history_protocol']
    ids = [method['runtime_id'] for method, owner in methods]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate bound historical subjects')
    if protocol == 'evas-method-audit-3257-v1':
        if row.get('verdict') not in ('no_defect_found', 'evidence_gap', 'mixed', 'test_defect'):
            raise ValueError('unknown/missing original audit verdict')
        if row.get('id') != ids[0]:
            raise ValueError('audit raw row ID differs from bound runtime ID')
        method, owner = methods[0]
        if row.get('source_file') != owner['current_path']:
            raise ValueError('audit row module path differs from bound owner')
        actual_method, actual_module = row.get('source_method_sha256'), row.get('source_module_sha256')
        _copied(obj, 'original_verdict', row.get('verdict'))
        _copied(obj, 'source_method_sha256', actual_method)
        _copied(obj, 'source_module_sha256', actual_module)
        if obj['alignment']['status'] == 'matched' and (not _sha(actual_method) or not _sha(actual_module) or actual_method != method['definition']['sha256'] or actual_module != owner['content'].get('value')):
            raise ValueError('actual audited method/module hash does not match bound method')
        return
    if protocol == 'evas-passing-oracles-v1':
        subjects = row.get('test_ids')
        eligibility = row.get('eligibility')
        if not isinstance(subjects, list) or not isinstance(eligibility, list) or any(not isinstance(e, dict) for e in eligibility) or len(eligibility) != len(subjects) or {e.get('id') for e in eligibility} != set(subjects):
            raise ValueError('oracle finding eligibility and test_ids disagree')
        facts = {e['id']: (e.get('source_file'), e.get('current_module_sha256'), e.get('previous_audit')) for e in eligibility}
    elif protocol == 'evas-passing-negative-v1':
        subjects = [row.get('method_id')]
        facts = {row.get('method_id'): (row.get('file'), None, None)}
    else:
        subjects = row.get('methods')
        reviewed = document.get('reviewed_methods', [])
        facts = {}
        for item in reviewed:
            if item.get('id') in (subjects or []):
                if item['id'] in facts:
                    raise ValueError('duplicate raw-finding reviewed subject')
                path = item.get('file')
                facts[item['id']] = (path, document.get('source_sha256', {}).get(path), None)
    if not isinstance(subjects, list) or any(not isinstance(i, str) or not i for i in subjects) or len(subjects) != len(set(subjects)) or not set(ids) <= set(subjects):
        raise ValueError('finding actual subject IDs differ from bound methods')
    coverage = obj.get('subject_coverage', 'complete')
    if coverage not in ('complete', 'partial') or (coverage == 'complete' and set(ids) != set(subjects)):
        raise ValueError('finding subjects require complete or explicit partial binding')
    _copied(obj, 'original_finding_id', row.get('id'))
    _copied(obj, 'original_status', row.get('status'))
    for method, owner in methods:
        path, module_sha, verdict = facts.get(method['runtime_id'], (None, None, None))
        if path != owner['current_path']:
            raise ValueError('finding subject lacks its actual declared module path')
        _copied(obj, 'original_verdict', verdict)
        _copied(obj, 'source_module_sha256', module_sha)
        _copied(obj, 'source_method_sha256', None)
    # All three original detector protocols lack tested method SHA. A module match
    # alone preserves a historical relationship, never full method or semantic alignment.
    if obj['alignment']['status'] == 'matched':
        raise ValueError('original finding has no tested-method SHA; alignment must remain pending')
