"""Line-per-context layout of evas/validation/baselines/regression-v1.json and the baseline-PR byte check.

The layout is '{"contexts":[', a newline, each context as compact JSON (separators ',' and ':', ensure_ascii=False,
allow_nan=False, keys in parsed order) joined by ',' plus newline, a newline, then '],"schema_version":' with the
version and '}' plus newline. It changes bytes only: the trusted gate and the registration code parse JSON, and the
C0 authority binds canonical digests (sorted keys), which no layout changes.
"""
import json


def line_per_context(doc):
    """Serialize a parsed baseline in the line-per-context layout."""
    if (not isinstance(doc, dict) or set(doc) != {'schema_version', 'contexts'}
            or not isinstance(doc['contexts'], list) or not doc['contexts']):
        raise ValueError('baseline must have exactly schema_version and a non-empty contexts array')
    body = ',\n'.join(json.dumps(c, ensure_ascii=False, separators=(',', ':'), allow_nan=False) for c in doc['contexts'])
    return ('{"contexts":[\n' + body + '\n],"schema_version":' + json.dumps(doc['schema_version']) + '}\n').encode()


def append_checks(trusted_raw, head_raw, entry, digest):
    """Check a one-context append against the coordinator's baseline-PR definition, except the one-path Git check.

    entry is the authorized new context; digest is the canonical SHA256 of regression_context_registration.py on
    the trusted base. Every check is reported; the caller requires all of them.
    """
    trusted, head = json.loads(trusted_raw), json.loads(head_raw)
    n = len(trusted['contexts'])
    from_trusted = line_per_context({'contexts': trusted['contexts'] + [entry], 'schema_version': trusted['schema_version']})
    from_head = line_per_context(head)
    return {
        'top_level_fields_unchanged': set(head) == set(trusted) == {'schema_version', 'contexts'}
                                      and head['schema_version'] == trusted['schema_version'],
        'exactly_one_context_appended': len(head['contexts']) == n + 1,
        'old_contexts_equal_in_order': [digest(c) for c in head['contexts'][:n]] == [digest(c) for c in trusted['contexts']],
        'new_context_equals_authorized_entry': len(head['contexts']) == n + 1 and digest(head['contexts'][-1]) == digest(entry),
        'write_from_trusted_plus_entry_equals_head_bytes': from_trusted == head_raw,
        'rewrite_of_head_equals_head_bytes': from_head == head_raw,
        'repeated_write_identical': line_per_context(json.loads(from_head)) == from_head,
    }
