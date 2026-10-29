"""Validate regression observations and compare them with a reviewed Git baseline.

This module does not grant semantic correctness or capability qualification.
``successful`` remains unittest's raw result. A reviewed unchanged observation
can permit a merge while that raw result remains false. Baselines are proposed
as data; only a separately trusted full Git commit may supply the CLI comparator.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

BASELINE_PATH = 'evas/validation/baselines/regression-v1.json'
OUTCOMES = {'passed', 'failed', 'error', 'skipped', 'expected_failure', 'unexpected_success'}
COUNTERS = ('tests_run', 'failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes')
CONTEXT_KEYS = ('criteria_id', 'language_profile', 'collector_sha256', 'runtime_profile', 'invocation')
# A runner image update changes the kernel release inside platform.platform()
# and ImageVersion. Python, Rust, PATH, glibc, architecture and the other
# variables stay exact; every observation is still compared.
HOST_PLATFORM = r'Linux-([0-9][0-9A-Za-z.+_~-]*?)-{machine}-with-(glibc[0-9]+\.[0-9]+)'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _host_split(context):
    """Return (context without runner-host fields, those fields), or None."""
    if not isinstance(context, dict) or not isinstance(context.get('runtime_profile'), dict):
        return None
    neutral = copy.deepcopy(context)
    profiles = {'runtime_profile': neutral['runtime_profile']}
    if 'execution_toolchain' in neutral['runtime_profile']:
        profiles['execution_toolchain'] = neutral['runtime_profile']['execution_toolchain']
    host = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict) or not isinstance(profile.get('variables'), dict):
            return None
        machine, platform, image = profile.get('machine'), profile.get('platform'), profile['variables'].get('ImageVersion')
        if (not isinstance(machine, str) or not re.fullmatch('[A-Za-z0-9_]+', machine)
                or not isinstance(platform, str) or not isinstance(image, str) or not image):
            return None
        match = re.fullmatch(HOST_PLATFORM.format(machine=re.escape(machine)), platform)
        if not match:
            return None
        host[name] = dict(platform=platform, ImageVersion=image)
        profile['platform'] = 'Linux-' + machine + '-with-' + match.group(2)
        del profile['variables']['ImageVersion']
    return neutral, host


def _matching_contexts(entries, context):
    """Return exact matches, else the entries differing only in runner-host fields.

    Only a single host-only candidate is a match; it also returns both host values.
    Several candidates are returned without a host difference, so callers reject them.
    """
    exact = [entry for entry in entries if isinstance(entry, dict)
             and _json(entry.get('context')) == _json(context)]
    if exact:
        return exact, None
    actual = _host_split(context)
    if actual is None:
        return [], None
    candidates = []
    for entry in entries:
        trusted = _host_split(entry.get('context')) if isinstance(entry, dict) else None
        if trusted is not None and _json(trusted[0]) == _json(actual[0]):
            candidates.append((entry, trusted[1]))
    if len(candidates) != 1:
        return [entry for entry, _ in candidates], None
    return [candidates[0][0]], dict(trusted=candidates[0][1], actual=actual[1])


def _manifest(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(label + ' must be a list of nonempty IDs')
    if len(value) != len(set(value)):
        raise ValueError(label + ' contains duplicate IDs')
    return value


def _context(report):
    metadata = report['metadata']
    if not isinstance(metadata, dict):
        raise ValueError('metadata must be an object')
    for key in CONTEXT_KEYS[:3]:
        if not isinstance(metadata.get(key), str) or not re.fullmatch('[0-9a-f]{64}', metadata[key]):
            raise ValueError(key + ' must be a SHA-256 identity')
    for key in CONTEXT_KEYS[3:]:
        if not isinstance(metadata.get(key), dict):
            raise ValueError(key + ' must be an object')
    context = {key: metadata[key] for key in CONTEXT_KEYS}
    _json(context)
    return context


def _assertion_value(value, *, diagnostic_policy=False, depth=0):
    """Validate the bounded assertion-value encoding, never execute its data."""
    if not isinstance(value, dict) or depth > 64 or not isinstance(value.get('type'), str):
        raise ValueError('unknown or incomplete typed assertion value')
    kind = value['type']
    fields = {
        'none': {'type'}, 'bool': {'type', 'value'}, 'int': {'type', 'hex'},
        'float': {'type', 'hex'}, 'str': {'type', 'value'}, 'bytes': {'type', 'hex'},
        'fraction': {'type', 'numerator', 'denominator'},
        'list': {'type', 'items'}, 'tuple': {'type', 'items'}, 'dict': {'type', 'items'},
        'str-parts': {'type', 'items'}, 'diagnostic-role': {'type', 'role', 'value_type'},
    }
    if kind not in fields or set(value) != fields[kind]:
        raise ValueError('unknown or incomplete typed assertion value')

    def integer(text):
        if not isinstance(text, str):
            raise ValueError('invalid hexadecimal assertion integer')
        number = int(text, 16)
        if hex(number) != text:
            raise ValueError('noncanonical hexadecimal assertion integer')
        return number

    if kind == 'bool' and type(value['value']) is not bool:
        raise ValueError('invalid assertion boolean')
    if kind == 'str' and not isinstance(value['value'], str):
        raise ValueError('invalid assertion string')
    if kind == 'int':
        integer(value['hex'])
    if kind == 'float':
        if not isinstance(value['hex'], str):
            raise ValueError('invalid assertion float')
        number = float.fromhex(value['hex'])
        if not math.isfinite(number) or number.hex() != value['hex']:
            raise ValueError('invalid or noncanonical assertion float')
    if kind == 'bytes':
        if not isinstance(value['hex'], str) or bytes.fromhex(value['hex']).hex() != value['hex']:
            raise ValueError('invalid assertion bytes')
    if kind == 'fraction':
        numerator, denominator = integer(value['numerator']), integer(value['denominator'])
        if denominator <= 0 or math.gcd(numerator, denominator) != 1:
            raise ValueError('noncanonical assertion Fraction')
    if kind in ('list', 'tuple', 'dict', 'str-parts'):
        if not isinstance(value['items'], list):
            raise ValueError('invalid assertion sequence')
        for item in value['items']:
            if kind == 'dict':
                if not isinstance(item, list) or len(item) != 2:
                    raise ValueError('invalid typed assertion mapping')
                for part in item:
                    _assertion_value(part, diagnostic_policy=diagnostic_policy, depth=depth + 1)
            elif kind == 'str-parts':
                if isinstance(item, str):
                    continue
                if (not diagnostic_policy or not isinstance(item, dict)
                        or set(item) != {'type', 'symbol', 'with_line'}
                        or item['type'] != 'temporary-directory-root'
                        or not isinstance(item['symbol'], str) or not item['symbol']
                        or type(item['with_line']) is not int or item['with_line'] <= 0):
                    raise ValueError('unbound temporary-directory assertion token')
            else:
                _assertion_value(item, diagnostic_policy=diagnostic_policy, depth=depth + 1)
        if kind == 'dict':
            keys = [_json(item[0]) for item in value['items']]
            if len(keys) != len(set(keys)):
                raise ValueError('duplicate typed assertion mapping key')
    if kind == 'diagnostic-role' and (not diagnostic_policy or value['role'] != 'duration-seconds'
                                      or value['value_type'] != 'float'):
        raise ValueError('unknown or unbound assertion diagnostic role')


def _condition(row):
    if not isinstance(row, dict):
        raise ValueError('condition must be an object')
    if not isinstance(row.get('id'), str) or not row['id']:
        raise ValueError('condition lacks identity')
    if not isinstance(row.get('phase'), str) or not row['phase']:
        raise ValueError('condition lacks phase')
    if type(row.get('identity_complete')) is not bool:
        raise ValueError('condition lacks identity completeness')
    if row.get('outcome') not in OUTCOMES:
        raise ValueError('unknown or interrupted condition outcome')
    if 'reason' in row and not isinstance(row['reason'], dict):
        raise ValueError('condition reason must be an object')
    if ('comparison_complete' in row.get('reason', {})
            and type(row['reason']['comparison_complete']) is not bool):
        raise ValueError('invalid assertion comparison completeness')
    if 'comparison_identity' in row.get('reason', {}):
        identity = row['reason']['comparison_identity']
        operands = {'assertEqual': {'first', 'second'},
                    'assertIn': {'member', 'container'},
                    'assertGreaterEqual': {'a', 'b'}}
        fields = {'schema_version', 'kind', 'operation', 'operation_source_sha256',
                  'operands', 'message', 'policies'}
        if (not isinstance(identity, dict) or set(identity) != fields
                or type(identity.get('schema_version')) is not int
                or identity['schema_version'] != 1 or identity['kind'] != 'unittest-assertion'
                or not isinstance(identity['operation'], str)
                or identity['operation'] not in operands
                or not isinstance(identity['operation_source_sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', identity['operation_source_sha256'])
                or not isinstance(identity['operands'], dict)
                or set(identity['operands']) != operands[identity['operation']]
                or not isinstance(identity['policies'], list) or not identity['policies']):
            raise ValueError('unknown or incomplete assertion comparison identity')
        for policy in identity['policies']:
            if (not isinstance(policy, dict) or set(policy) != {'id', 'version', 'source_sha256'}
                    or any(not isinstance(policy[key], str) or not policy[key]
                           for key in ('id', 'source_sha256'))
                    or type(policy['version']) is not int or policy['version'] != 1
                    or not re.fullmatch('[0-9a-f]{64}', policy['source_sha256'])):
                raise ValueError('assertion identity lacks a version-bound diagnostic policy')
        if len({policy['id'] for policy in identity['policies']}) != len(identity['policies']):
            raise ValueError('duplicate assertion diagnostic policy')
        for value in [*identity['operands'].values(), identity['message']]:
            _assertion_value(value, diagnostic_policy=bool(identity['policies']))
    if row['outcome'] != 'passed':
        reason = row.get('reason')
        # unittest supplies no exception for an unexpected success.
        if row['outcome'] != 'unexpected_success' or reason is not None:
            if (not isinstance(reason, dict) or not isinstance(reason.get('kind'), str)
                    or not isinstance(reason.get('message'), str)):
                raise ValueError('nonpassing condition lacks diagnostic reason')
    if row.get('site') is not None and not isinstance(row['site'], dict):
        raise ValueError('condition site must be an object')


def _validate(report):
    if (not isinstance(report, dict) or type(report.get('schema_version')) is not int
            or report.get('schema_version') != 3):
        raise ValueError('unsupported report schema; version 3 required')
    if report.get('complete') is not True or report.get('collection_complete') is not True:
        raise ValueError('execution or collection incomplete')
    if type(report.get('successful')) is not bool:
        raise ValueError('raw successful must be boolean')
    _context(report)
    _json(report)
    for key in COUNTERS:
        if type(report.get(key)) is not int or report[key] < 0:
            raise ValueError(key + ' must be a nonnegative integer')
    discovered = _manifest(report['discovered_test_ids'], 'discovered_test_ids')
    selected = _manifest(report['selected_test_ids'], 'selected_test_ids')
    skipped = _manifest(report['setup_skipped_test_ids'], 'setup_skipped_test_ids')
    if not discovered:
        raise ValueError('zero discovered tests')
    count = report['shard_count']
    assignment = report['assignment']
    if type(count) is not int or count < 1 or not isinstance(assignment, list) or len(assignment) != count:
        raise ValueError('invalid shard assignment')
    assigned = [identity for i, shard in enumerate(assignment)
                for identity in _manifest(shard, 'assignment shard ' + str(i))]
    if len(assigned) != len(set(assigned)) or sorted(assigned) != sorted(discovered):
        raise ValueError('assignment missing, overlapping or unknown tests')
    merged = report.get('merged', False)
    if type(merged) is not bool:
        raise ValueError('merged must be boolean')
    if merged:
        if report.get('shard_index') is not None or selected != discovered:
            raise ValueError('merged selection must cover discovered tests')
        parts = report.get('parts')
        if not isinstance(parts, list) or len(parts) != count:
            raise ValueError('missing shard parts')
        indices = [part.get('shard_index') for part in parts if isinstance(part, dict)]
        if len(indices) != count or any(type(i) is not int for i in indices) or set(indices) != set(range(count)):
            raise ValueError('missing or duplicate shard parts')
        for part in parts:
            if part.get('complete') is not True or part.get('collection_complete') is not True:
                raise ValueError('incomplete shard part')
            if part.get('selected_test_ids') != assignment[part['shard_index']]:
                raise ValueError('shard part assignment differs')
    else:
        index = report['shard_index']
        if type(index) is not int or not 0 <= index < count or selected != assignment[index]:
            raise ValueError('invalid shard index or selection')
    tests = report['tests']
    fixtures = report['fixtures']
    if not isinstance(tests, list) or not isinstance(fixtures, list):
        raise ValueError('tests and fixtures must be arrays')
    ids = _manifest([row['id'] for row in tests], 'tests')
    if len(ids + skipped) != len(set(ids + skipped)) or sorted(ids + skipped) != sorted(selected):
        raise ValueError('executed and setup-skipped tests do not account for selection')
    if report['tests_run'] != len(tests):
        raise ValueError('tests_run disagrees with observations')
    if not tests and (merged or count == 1):
        raise ValueError('zero executed tests')
    for row in tests:
        if row.get('outcome') not in OUTCOMES:
            raise ValueError('unknown or interrupted method outcome')
        seconds = row.get('seconds')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('invalid method duration')
        conditions = row['conditions']
        if not isinstance(conditions, list) or not conditions:
            raise ValueError('method lacks condition observations')
        condition_ids = []
        for condition in conditions:
            _condition(condition)
            condition_ids.append(condition['id'])
        _manifest(condition_ids, 'conditions in ' + row['id'])
        priority = {'passed': 0, 'skipped': 1, 'expected_failure': 1,
                    'unexpected_success': 2, 'failed': 3, 'error': 4}
        observed = max(conditions, key=lambda c: priority[c['outcome']])['outcome']
        if observed != row['outcome']:
            raise ValueError('method outcome disagrees with its conditions')
    fixture_keys = []
    for fixture in fixtures:
        _condition(fixture)
        if not isinstance(fixture.get('scope'), str) or not fixture['scope']:
            raise ValueError('fixture lacks scope')
        fixture_keys.append(fixture['scope'] + ':' + fixture['id'])
    _manifest(fixture_keys, 'fixtures')
    observations = [c for row in tests for c in row['conditions']] + fixtures
    # unittest counts failing subtests individually. Expected failures and
    # unexpected successes are method events, while skips may be subtests.
    for key, outcome in [('failures', 'failed'), ('errors', 'error'), ('skipped', 'skipped'),
                         ('expected_failures', 'expected_failure'),
                         ('unexpected_successes', 'unexpected_success')]:
        if report[key] != sum(c['outcome'] == outcome for c in observations):
            raise ValueError(key + ' disagrees with condition observations')
    raw = not any(report[key] for key in ('failures', 'errors', 'unexpected_successes'))
    if raw != report['successful']:
        raise ValueError('raw successful disagrees with unittest counters')
    if any('_FailedTest' in identity for identity in discovered):
        raise ValueError('collection import failure')


def validate_report(report):
    """Return integrity facts; a complete failing run can be valid data."""
    try:
        _validate(report)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return dict(valid=False, errors=[str(error)])
    return dict(valid=True, errors=[])


def _whole(report):
    return report.get('merged') is True or report.get('shard_count') == 1


def cacheable_report(report):
    """Only complete nonempty scopes with actual passes may enter success cache."""
    return (validate_report(report)['valid'] and bool(report['tests']) and report['successful']
            and not report['setup_skipped_test_ids']
            and all(row['outcome'] == 'passed' for row in report['tests'] + report['fixtures'])
            and all(c['outcome'] == 'passed' for row in report['tests'] for c in row['conditions']))


def _reviewed(review):
    return (isinstance(review, dict) and review.get('status') == 'approved'
            and isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip())
            and isinstance(review.get('reference'), str) and bool(review['reference'].strip()))


def _baseline_observations(report):
    """Keep all comparison observations; raw payloads remain in their archive."""
    fields = ('schema_version', 'complete', 'collection_complete', 'successful',
              'discovered_test_ids', 'selected_test_ids', 'setup_skipped_test_ids',
              'assignment', 'shard_count', 'shard_index', *COUNTERS)
    observations = {key: copy.deepcopy(report[key]) for key in fields}
    observations['metadata'] = copy.deepcopy(_context(report))
    if report.get('merged') is True:
        observations['merged'] = True
        observations['parts'] = [{key: copy.deepcopy(part[key]) for key in
            ('shard_index', 'complete', 'collection_complete', 'selected_test_ids')}
            for part in report['parts']]

    def condition(row):
        retained = {key: copy.deepcopy(row[key]) for key in
            ('id', 'phase', 'kind', 'site', 'params', 'context', 'message',
             'outcome', 'identity_complete', 'repeated_identity', 'scope') if key in row}
        if 'reason' in row:
            retained['reason'] = {key: copy.deepcopy(row['reason'][key]) for key in
                ('kind', 'exception_type', 'message', 'site', 'context',
                 'context_complete', 'attribution', 'comparison_identity',
                 'comparison_complete', 'comparison_state') if key in row['reason']}
        return retained

    observations['tests'] = [dict(id=row['id'], outcome=row['outcome'], seconds=row['seconds'],
                                 conditions=[condition(c) for c in row['conditions']])
                             for row in report['tests']]
    observations['fixtures'] = [condition(row) for row in report['fixtures']]
    # This is a projection into the same observation schema, never a rewritten
    # raw execution. Its canonical source hash is stored beside the projection.
    validation = validate_report(observations)
    if not validation['valid']:
        raise ValueError('invalid baseline projection: ' + '; '.join(validation['errors']))
    return observations


def _context_frames(observations):
    conditions = [c for row in observations['tests'] for c in row['conditions']] + observations['fixtures']
    for condition in conditions:
        for context in (condition.get('context'), condition.get('reason', {}).get('context')):
            if isinstance(context, list):
                yield from (frame for frame in context if isinstance(frame, dict))


def _pool_context_values(observations):
    pool = {}
    for frame in _context_frames(observations):
        if 'value_refs' in frame:
            raise ValueError('raw context uses reserved baseline encoding fields')
        values = frame.get('values')
        if not isinstance(values, dict):
            continue
        references = {}
        for name, value in list(values.items()):
            encoded = _json(value).encode()
            if len(encoded) >= 256:
                identity = hashlib.sha256(encoded).hexdigest()
                if identity not in pool:
                    pool[identity] = value
                references[name] = identity
                del values[name]
        if references:
            frame['value_refs'] = references
    return pool


def _expand_baseline_observations(entry):
    if entry.get('observation_encoding') != 'pooled-context-v1':
        raise ValueError('unsupported baseline observation encoding')
    pool = entry.get('value_pool')
    if not isinstance(pool, dict):
        raise ValueError('baseline value pool must be an object')
    for identity, value in pool.items():
        if not isinstance(identity, str) or hashlib.sha256(_json(value).encode()).hexdigest() != identity:
            raise ValueError('baseline pooled value hash mismatch')
    observations = copy.deepcopy(entry.get('observations'))
    validation = validate_report(observations)
    if not validation['valid']:
        raise ValueError('invalid baseline observations: ' + '; '.join(validation['errors']))
    for frame in _context_frames(observations):
        if 'value_refs' not in frame:
            continue
        references = frame.pop('value_refs')
        values = frame.get('values')
        if (not isinstance(references, dict) or not isinstance(values, dict)
                or any(not isinstance(name, str) or name in values or not isinstance(identity, str)
                       or identity not in pool for name, identity in references.items())):
            raise ValueError('missing or conflicting baseline pooled context value')
        values.update({name: copy.deepcopy(pool[identity]) for name, identity in references.items()})
    return observations


def propose_baseline(report, source_identity, review=None):
    """Produce reviewable observations; this never publishes or trusts a baseline.

    ``review`` records independent review status, reviewer and reference. Semantic
    attribution may remain pending. The trusted commit is the CLI trust boundary.
    Multiple returned contexts can be assembled into one version-1 document.
    """
    validation = validate_report(report)
    if not validation['valid'] or not _whole(report):
        raise ValueError('baseline needs a complete full report: ' + '; '.join(validation['errors']))
    if not isinstance(source_identity, dict) or not source_identity:
        raise ValueError('source_identity must be a nonempty object')
    if review is None:
        review = dict(status='pending', semantic_status='pending')
    if not isinstance(review, dict):
        raise ValueError('review must be an object')
    observations = _baseline_observations(report)
    value_pool = _pool_context_values(observations)
    proposal = dict(schema_version=1, contexts=[dict(
        context=copy.deepcopy(_context(report)), source_identity=copy.deepcopy(source_identity),
        review=copy.deepcopy(review), semantic_qualification=False,
        observation_format='regression-observations-v1', observation_encoding='pooled-context-v1',
        value_pool=value_pool,
        canonical_report_sha256=hashlib.sha256(_json(report).encode()).hexdigest(),
        observations=observations)])
    if _has_comparison_subject(report):
        proposal['contexts'][0]['execution_subject'] = execution_subject(report)
    return proposal


def _matchable(condition):
    site = condition.get('site') or condition.get('reason', {}).get('site')
    return (condition['identity_complete']
            and condition.get('reason', {}).get('context_complete', True) is True
            and condition.get('reason', {}).get('comparison_complete', True) is True
            and isinstance(site, dict)
            and isinstance(site.get('source_sha256'), str)
            and bool(re.fullmatch('[0-9a-f]{64}', site['source_sha256'])))


def _signature(condition):
    # Raw diagnostics remain unchanged. Only a validated, source-bound capture
    # can supply structured comparison evidence instead of generated repr text.
    reason = condition.get('reason', {})
    diagnostic = ({'comparison_identity': reason['comparison_identity']}
                  if 'comparison_identity' in reason else {'message': reason.get('message')})
    return _json({key: condition.get(key) for key in ('id', 'phase', 'kind', 'site', 'params', 'context')} | {
        'outcome': condition['outcome'],
        'reason': {key: reason.get(key) for key in
                   ('kind', 'exception_type', 'site', 'context', 'context_complete')} | diagnostic})


def compare_report(report, baseline):
    """Compare observations conservatively, preserving the raw unittest result."""
    validation = validate_report(report)
    differences = list(validation['errors'])
    result = dict(valid=validation['valid'], raw_successful=report.get('successful')
                  if isinstance(report, dict) else None, merge_allowed=False,
                  differences=differences, semantic_qualification=False)
    if not validation['valid']:
        return result
    if not _whole(report):
        differences.append('comparison requires every shard')
        return result
    if not isinstance(baseline, dict) or baseline.get('schema_version') != 1 or not isinstance(baseline.get('contexts'), list):
        differences.append('missing or unsupported trusted baseline')
        return result
    try:
        _json(baseline)
    except (TypeError, ValueError):
        differences.append('baseline is not finite JSON data')
        return result
    context = _context(report)
    matches, host = _matching_contexts(baseline['contexts'], context)
    if len(matches) != 1:
        differences.append('expected exactly one matching trusted baseline context')
        if matches and _json(matches[0].get('context')) != _json(context):
            differences.append('runner-host difference matches more than one trusted context')
        return result
    if host is not None:
        result['host_runtime_difference'] = host
    entry = matches[0]
    try:
        old = _expand_baseline_observations(entry)
    except (KeyError, TypeError, ValueError) as error:
        differences.append('invalid baseline observation projection: ' + str(error))
        return result
    if (entry.get('observation_format') != 'regression-observations-v1'
            or not isinstance(entry.get('canonical_report_sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', entry['canonical_report_sha256'])
            or not _reviewed(entry.get('review')) or not isinstance(entry.get('source_identity'), dict)
            or not entry['source_identity'] or not validate_report(old)['valid']
            or not _whole(old) or _json(_context(old)) != _json(entry['context'])):
        differences.append('baseline context lacks reviewed complete observations')
        return result
    if report['discovered_test_ids'] != old['discovered_test_ids']:
        differences.append('method manifest changed')
    if report['setup_skipped_test_ids'] != old['setup_skipped_test_ids']:
        differences.append('setup-skipped method manifest changed')
    if report['setup_skipped_test_ids']:
        differences.append('setup-skipped methods lack method observations')
    methods = {row['id']: row for row in old['tests']}
    for row in report['tests']:
        previous = methods.get(row['id'])
        if previous is None:
            differences.append('new method: ' + row['id'])
            continue
        before = {c['id']: c for c in previous['conditions']}
        after = {c['id']: c for c in row['conditions']}
        for identity, condition in before.items():
            current = after.get(identity)
            if condition['outcome'] == 'passed' and (current is None or current['outcome'] != 'passed'
                    or _signature(current) != _signature(condition)):
                differences.append('previously passed condition missing or changed: ' + row['id'] + ':' + identity)
        for condition in row['conditions']:
            if condition['outcome'] == 'passed':
                continue
            previous_condition = before.get(condition['id'])
            if (not _matchable(condition) or previous_condition is None
                    or not _matchable(previous_condition)
                    or _signature(condition) != _signature(previous_condition)):
                differences.append('new or changed nonpassing condition: ' + row['id'] + ':' + condition['id'])
    # Fixture failures are infrastructure/lifecycle failures, never waivers.
    if any(f['outcome'] != 'passed' for f in report['fixtures']):
        differences.append('nonpassing fixture blocks comparison')
    old_fixture_passes = {_signature(f) for f in old['fixtures'] if f['outcome'] == 'passed'}
    if not old_fixture_passes.issubset({_signature(f) for f in report['fixtures']}):
        differences.append('previously passed fixture observation missing')
    result['merge_allowed'] = not differences
    return result


def load_trusted_baseline(repo, trusted_ref):
    """Read only a full immutable commit's baseline, never the working tree."""
    if not isinstance(trusted_ref, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', trusted_ref):
        raise ValueError('trusted-base must be a full hexadecimal commit ID')
    commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', trusted_ref + '^{commit}'],
                            capture_output=True, text=True)
    if commit.returncode or commit.stdout.strip() != trusted_ref:
        raise ValueError('trusted-base is not an available full commit ID')
    result = subprocess.run(['git', '-C', str(repo), 'show', trusted_ref + ':' + BASELINE_PATH],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError('trusted baseline is absent at trusted-base')
    return json.loads(result.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'propose', 'compare'):
        sub = subparsers.add_parser(name)
        sub.add_argument('report', type=Path)
        if name == 'propose':
            sub.add_argument('--source-identity', type=Path, required=True)
            sub.add_argument('--review', type=Path)
        if name == 'compare':
            sub.add_argument('--repo', type=Path, required=True)
            sub.add_argument('--trusted-base', required=True)
            sub.add_argument('--inactive', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text())
        if args.command == 'validate':
            result = validate_report(report)
            code = 0 if result['valid'] else 1
        elif args.command == 'propose':
            result = propose_baseline(report, json.loads(args.source_identity.read_text()),
                                      json.loads(args.review.read_text()) if args.review else None)
            code = 0
        else:
            baseline = load_trusted_baseline(args.repo, args.trusted_base)
            result = compare_report(report, baseline)
            code = 0 if result['merge_allowed'] else 1
            result['trusted_base'] = args.trusted_base
            if args.inactive:
                result['comparison_matches'] = result['merge_allowed']
                result['merge_allowed'] = None
        print(json.dumps(result, indent=2, allow_nan=False))
        return code
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps(dict(error=str(error), merge_allowed=None if getattr(args, 'inactive', False)
                              else False)), file=sys.stderr)
        return 2



# PROTOTYPE ADDITION: keep one comparator, then validate baseline evolution.

COMPARISON_BASELINE_PATHS = (
    'evas/validation/baselines/regression-v1.json',
    'evas/validation/baselines/regression-v1.review.json',
)


def _checked_comparison_subject(value):
    fields = {'schema_version', 'report_schema_version', 'evidence_schema_version',
              'files_sha256', 'input_count', 'environment', 'excluded_baseline_paths'}
    if (not isinstance(value, dict) or set(value) != fields
            or type(value.get('schema_version')) is not int or value['schema_version'] != 1
            or type(value.get('report_schema_version')) is not int or value['report_schema_version'] != 3
            or type(value.get('evidence_schema_version')) is not int or value['evidence_schema_version'] != 3
            or not isinstance(value.get('files_sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', value['files_sha256'])
            or type(value.get('input_count')) is not int or value['input_count'] <= 0
            or not isinstance(value.get('environment'), dict) or 'shard' in value['environment']
            or value.get('excluded_baseline_paths') != list(COMPARISON_BASELINE_PATHS)):
        raise ValueError('unknown or incomplete all-input comparison subject, or exclusion policy changed')
    _json(value)
    return value


def _actual_comparison_subject(report):
    if report.get('merged') is True:
        identities = [part['source_identity']['execution_identity'] for part in report['parts']]
    else:
        identities = [report['source_identity']['execution_identity']]
    checked = []
    for identity in identities:
        value = _checked_comparison_subject(identity['comparison_subject'])
        environment = identity.get('environment')
        if (not isinstance(identity.get('key'), str) or not re.fullmatch('[0-9a-f]{64}', identity['key'])
                or type(identity.get('report_schema_version')) is not int or identity['report_schema_version'] != 3
                or type(identity.get('evidence_schema_version')) is not int or identity['evidence_schema_version'] != 3
                or type(identity.get('input_count')) is not int
                or not 0 <= identity['input_count'] - value['input_count'] <= len(COMPARISON_BASELINE_PATHS)
                or not isinstance(environment, dict)
                or _json({k:v for k,v in environment.items() if k != 'shard'}) != _json(value['environment'])):
            raise ValueError('all-input subject disagrees with its actual full execution identity')
        checked.append(value)
    if not checked or len({_json(v) for v in checked}) != 1:
        raise ValueError('merged actual parts have different all-input comparison subjects')
    return copy.deepcopy(checked[0])


def _has_comparison_subject(report):
    sources = [p.get('source_identity', {}) for p in report.get('parts', [])] if report.get('merged') is True else [report.get('source_identity', {})]
    return any(isinstance(s, dict) and isinstance(s.get('execution_identity'), dict)
               and 'comparison_subject' in s['execution_identity'] for s in sources)


def execution_subject(report):
    """Bind scientific inputs without including the baseline-containing CI fingerprint."""
    context = _context(report)
    try:
        comparison = _actual_comparison_subject(report)
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("actual raw predates the required all-input subject producer") from error
    source = report.get('source_identity')
    if not isinstance(source, dict) or 'kernel_sha256' not in source:
        raise ValueError('actual report lacks execution subject source identity')
    files = source.get('dut_files')
    if not isinstance(files, list) or not files:
        raise ValueError('actual report lacks selected DUT file identities')
    paths = []
    for item in files:
        if (not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str)
                or not item[0].startswith(('evas/src/', 'evas/rust_core/'))
                or any(part in ('..', 'baselines', '__pycache__', 'target') for part in item[0].split('/'))
                or not isinstance(item[1], str) or not re.fullmatch('[0-9a-f]{64}', item[1])):
            raise ValueError('unknown or incomplete actual DUT file identity')
        paths.append(item[0])
    if len(paths) != len(set(paths)):
        raise ValueError('actual DUT manifest must preserve unique producer entries')
    kernel = source['kernel_sha256']
    if kernel is not None and (not isinstance(kernel, str) or not re.fullmatch('[0-9a-f]{64}', kernel)):
        raise ValueError('unknown actual kernel identity')
    return dict(schema_version=1, comparison_subject=comparison, metadata=context,
                dut_files_sha256=hashlib.sha256(_json(files).encode()).hexdigest(),
                kernel_sha256=kernel)


def _retention_condition(condition):
    # Opaque passes remain observations with false identity flags, never qualification.
    return dict(signature=_signature(condition), identity_complete=condition['identity_complete'],
                repeated_identity=condition.get('repeated_identity'),
                context_complete=condition.get('reason', {}).get('context_complete', True),
                comparison_complete=condition.get('reason', {}).get('comparison_complete', True))


def _retention_observations(report):
    """Compare every projected observation, omitting execution duration and raw bulk."""
    projected = _baseline_observations(report)
    for row in projected['tests']:
        row.pop('seconds')
        row['conditions'] = [_retention_condition(c) for c in row['conditions']]
    projected['fixtures'] = [dict(scope=c.get('scope'), **_retention_condition(c))
                             for c in projected['fixtures']]
    return projected


def _passed_observations(report):
    return {(row['id'], c['id'], _json(_retention_condition(c)))
            for row in report['tests'] for c in row['conditions'] if c['outcome'] == 'passed'} | {
        ('fixture:' + c['scope'], c['id'], _json(_retention_condition(c)))
        for c in report['fixtures'] if c['outcome'] == 'passed'}


def _observed_keys(report, nonpassing_only=False):
    return {(row['id'], c['id']) for row in report['tests'] for c in row['conditions']
            if not nonpassing_only or c['outcome'] != 'passed'} | {
        ('fixture:' + c['scope'], c['id']) for c in report['fixtures']
        if not nonpassing_only or c['outcome'] != 'passed'}


def validate_baseline_transition(report, trusted_baseline, head_proposal):
    """Retain improvements only after old trusted comparison permits the candidate.

    Head data cannot waive current differences. Approval fields record independent
    review identity; the workflow still owns who may provide that approval.
    """
    trusted = compare_report(report, trusted_baseline)
    result = dict(valid=trusted['valid'], raw_successful=trusted['raw_successful'],
                  merge_allowed=False, differences=list(trusted['differences']),
                  semantic_qualification=False, trusted_comparison=trusted,
                  transition=dict(proposal_evaluated=False, refresh_required=None,
                                  accepted=False, differences=[]))
    if 'host_runtime_difference' in trusted:
        result['host_runtime_difference'] = copy.deepcopy(trusted['host_runtime_difference'])
    # Do not even inspect head data when the authority comparison rejected.
    if not trusted['merge_allowed']:
        return result
    differences = result['transition']['differences']
    try:
        context = _context(report)
        matched, host = _matching_contexts(trusted_baseline['contexts'], context)
        if len(matched) != 1:
            raise ValueError('trusted context match differs from the comparison')
        old_entry = matched[0]
        old = _expand_baseline_observations(old_entry)
        actual_conditions = [c for row in report['tests'] for c in row['conditions']] + report['fixtures']
        if any(c['outcome'] != 'passed' and not _matchable(c) for c in actual_conditions):
            raise ValueError('unknown or incomplete actual condition identity')
        newly_passed = _passed_observations(report) - _passed_observations(old)
        # compare_report checks the passes it keeps and the non-passes it sees; a registered
        # non-pass that no longer occurs at all is a change too, never an unchanged result.
        vanished = _observed_keys(old, nonpassing_only=True) - _observed_keys(report)
        result['transition']['refresh_required'] = bool(newly_passed or vanished)
        result['transition']['new_passed_observations'] = [dict(owner=o, condition=c) for o,c,_ in sorted(newly_passed)]
        result['transition']['vanished_nonpassing_observations'] = [dict(owner=o, condition=c) for o,c in sorted(vanished)]
        unchanged = _json(head_proposal) == _json(trusted_baseline)
        if unchanged and not newly_passed and not vanished:
            result['transition'].update(accepted=True, reused_trusted_baseline=True)
            result['merge_allowed'] = True
            return result
        if unchanged and newly_passed:
            raise ValueError('newly passed observations require a reviewed refreshed baseline')
        if unchanged:
            raise ValueError('vanished nonpassing observations require a reviewed refreshed baseline')
        result['transition']['proposal_evaluated'] = True
        if (not isinstance(head_proposal, dict) or type(head_proposal.get('schema_version')) is not int
                or head_proposal['schema_version'] != 1 or not isinstance(head_proposal.get('contexts'), list)):
            raise ValueError('unknown or incomplete head baseline proposal')
        _json(head_proposal)
        # A refresh keeps the registered context, including its runner host.
        matches = [e for e in head_proposal['contexts'] if isinstance(e, dict)
                   and _json(e.get('context')) == _json(old_entry['context'])]
        if len(matches) != 1:
            raise ValueError('head proposal must retain exactly one current context')
        proposed_entry = matches[0]
        before_other = [e for e in trusted_baseline['contexts'] if e is not old_entry]
        after_other = [e for e in head_proposal['contexts'] if e is not proposed_entry]
        if _json(before_other) != _json(after_other):
            raise ValueError('head proposal changed an unrelated trusted context')
        # Reuse the existing public comparator for proposal shape/review validation;
        # it never replaces the earlier comparison against old authority.
        proposed_check = compare_report(report, head_proposal)
        if not proposed_check['merge_allowed']:
            raise ValueError('head proposal is not reviewed complete observations: ' + '; '.join(proposed_check['differences']))
        proposed = _expand_baseline_observations(proposed_entry)
        proposed_conditions = [c for row in proposed['tests'] for c in row['conditions']] + proposed['fixtures']
        if any(c['outcome'] != 'passed' and not _matchable(c) for c in proposed_conditions):
            raise ValueError('unknown or incomplete proposed condition identity')
        actual = _retention_observations(report)
        if host is not None:
            # Observations from another runner host keep the registered context;
            # the entry's provenance must name the host they were actually taken on.
            actual['metadata'] = copy.deepcopy(old_entry['context'])
            source = proposed_entry.get('source_identity')
            if (not isinstance(source, dict) or _json(source.get('observed_host')) != _json(host['actual'])
                    or not isinstance(source.get('observed_run'), str) or not source['observed_run'].strip()):
                raise ValueError('refreshed entry must record the actual runner host and run')
        if _json(_retention_observations(proposed)) != _json(actual):
            raise ValueError('head proposal does not retain every actual observation and context')
        subject = execution_subject(report)
        if _json(proposed_entry.get('execution_subject')) != _json(subject):
            raise ValueError('head proposal execution subject differs from actual selected DUT/kernel/context')
        result['transition'].update(accepted=True, execution_subject=subject,
            proposal_canonical_source_sha256=proposed_entry['canonical_report_sha256'],
            current_canonical_report_sha256=hashlib.sha256(_json(report).encode()).hexdigest(),
            review=copy.deepcopy(proposed_entry['review']))
        result['merge_allowed'] = True
    except (KeyError, TypeError, ValueError, StopIteration, OverflowError) as error:
        differences.append(str(error))
        result['differences'].append('baseline transition: ' + str(error))
    return result




if __name__ == '__main__':
    raise SystemExit(main())
