"""Recheck one frozen DC case against independent values; never interpolate."""
import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
FIXTURE = BASE / 'evas/validation/cases/case_statements'
SHARED = BASE / 'experiments/backends/function-branches/check.py'
NATIVE_TIMES = [0., .001, .003, .007, .015, .031, .063, .125, .1875,
                .25, .375, .5, .625, .75, .875, 1.]
NODES = [f'{prefix}{i}' for i in range(5) for prefix in ('y', 'f')]


# Freeze the identity projection of the retained execution receipts, not today's HEAD.
# The raw entry reconstructs this projection from PAIR/response/TOOL_IDENTITY/PREPARATION.
EXECUTION_BINDING_SHA256 = 'c2348f99915a786ccf21d4ff7efd31df952cae4330c107cca89191ea53759b07'
FIXTURE_KEYS = frozenset(['dut.va', 'expected.json', 'table.json', 'table.scs'])
RAW_KEYS = frozenset(['PAIR.json', 'PREPARATION.json', 'check.py', 'collected/spectre/COLLECTION.json', 'collected/spectre/spectre-output/TOOL_IDENTITY.json', 'collected/spectre/spectre-output/runs/case-statements/RESULT.json', 'collected/spectre/spectre-output/runs/case-statements/dut.va', 'collected/spectre/spectre-output/runs/case-statements/expected.json', 'collected/spectre/spectre-output/runs/case-statements/original-table.scs', 'collected/spectre/spectre-output/runs/case-statements/psf/tran.tran.tran', 'collected/spectre/spectre-output/runs/case-statements/spectre.log', 'collected/spectre/spectre-output/runs/case-statements/table.json', 'collected/spectre/spectre-output/runs/case-statements/tb.scs', 'evas-native.stderr', 'evas-native.stdout.json', 'native-query.json', 'normalize_psf.py', 'normalized.json', 'settings-readback.json'])
RUN_PREFIX = 'collected/spectre/spectre-output/runs/case-statements/'


def binding_digest(binding):
    return hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def required_hashes(document):
    if not isinstance(document, dict):
        raise ValueError("compact document must be an object")
    for field, required in (('fixture_sha256', FIXTURE_KEYS), ('raw_artifact_sha256', RAW_KEYS)):
        hashes = document.get(field)
        if not isinstance(hashes, dict) or set(hashes) != required:
            raise ValueError('required hash key set mismatch: ' + field)
        if any(not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None
               for value in hashes.values()):
            raise ValueError('invalid digest: ' + field)


def verify_binding(document):
    required_hashes(document)
    binding = document['execution_binding']
    if binding_digest(binding) != EXECUTION_BINDING_SHA256:
        raise ValueError('retained execution binding mismatch')
    identity = document['execution_identity']
    for key, value in binding.items():
        if key != 'EVAS_output_sha256' and identity[key] != value:
            raise ValueError('execution identity differs from retained receipts: ' + key)
    hashes = document['raw_artifact_sha256']
    for path, key in (('evas-native.stdout.json', 'EVAS_output_sha256'),
                      (RUN_PREFIX+'dut.va', 'model_sha256'),
                      (RUN_PREFIX+'tb.scs', 'executed_deck_sha256'),
                      (RUN_PREFIX+'original-table.scs', 'original_deck_sha256')):
        if hashes[path] != binding[key]:
            raise ValueError('artifact digest differs from execution binding: ' + path)
    for name in ('dut.va', 'expected.json', 'table.json'):
        if document['fixture_sha256'][name] != hashes[RUN_PREFIX+name]:
            raise ValueError('raw and maintained fixture identity mismatch: ' + name)
    if document['fixture_sha256']['table.scs'] != binding['original_deck_sha256']:
        raise ValueError('original deck differs from maintained fixture')
    # Git is evidence for the actually recorded source, not a substitution of current HEAD.
    try:
        syntax = subprocess.run(['git', 'show', binding['evas_commit']+':evas/src/evas/syntax.py'],
                                cwd=BASE, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as error:
        raise ValueError('recorded execution source unavailable in repository') from error
    if hashlib.sha256(syntax).hexdigest() != binding['frontend_syntax_sha256']:
        raise ValueError('recorded source syntax identity mismatch')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def contract():
    answer = load(FIXTURE / 'expected.json')
    times = load(FIXTURE / 'table.json')['transient']['output_times']
    expected = {node: answer[node[0]][int(node[1:])] for node in NODES}
    tolerance = answer['absolute_tolerance']
    if times != [i / 8 for i in range(9)] or len(expected) != 10:
        raise ValueError('frozen fixed denominator changed')
    if not all(finite(v) for v in expected.values()) or not finite(tolerance) or tolerance <= 0:
        raise ValueError('invalid independent contract')
    return times, expected, tolerance


def validate_rows(rows):
    if not isinstance(rows, list):
        raise ValueError("observations must be an array")
    if len(rows) != len(NATIVE_TIMES):
        raise ValueError('native row denominator mismatch')
    for t, row in zip(NATIVE_TIMES, rows):
        if not isinstance(row, dict):
            raise ValueError("observation must be an object")
        if not finite(row['time_s']) or row['time_s'] != t:
            raise ValueError('missing, duplicate or reordered native time')
        for backend in ('Spectre_V', 'EVAS_V'):
            values = row[backend]
            if not isinstance(values, dict):
                raise ValueError("backend voltages must be an object")
            if set(values) != set(NODES):
                raise ValueError('missing or unexpected channel')
            if not all(finite(value) for value in values.values()):
                raise ValueError('nonfinite voltage')


def assess(rows):
    validate_rows(rows)
    times, expected, tolerance = contract()
    maximum = {'Spectre_expected_V': 0., 'EVAS_expected_V': 0., 'EVAS_Spectre_V': 0.}
    failures = []
    for row in rows:
        for node, value in expected.items():
            errors = {
                'Spectre_expected_V': abs(row['Spectre_V'][node] - value),
                'EVAS_expected_V': abs(row['EVAS_V'][node] - value),
                'EVAS_Spectre_V': abs(row['EVAS_V'][node] - row['Spectre_V'][node]),
            }
            for key, error in errors.items():
                maximum[key] = max(maximum[key], error)
                if error > tolerance:
                    failures.append(dict(time_s=row['time_s'], node=node, comparison=key, error_V=error))
    # The validated native grid includes all nine frozen fixed observations.
    if not set(times) <= {row['time_s'] for row in rows}:
        raise ValueError('fixed query missing')
    return dict(finite_comparison='F' if failures else 'P', formal_qualification='I',
                fixed_points=len(times), fixed_scalars=len(times)*len(expected),
                native_points=len(rows), native_scalars=len(rows)*len(expected),
                maxima=maximum, failures=failures)


def check_compact(document):
    verify_binding(document)
    if document['checker_sha256'] != sha(Path(__file__)) or document['shared_psf_parser_sha256'] != sha(SHARED):
        raise ValueError('checker identity mismatch')
    for name, expected_hash in document['fixture_sha256'].items():
        if sha(FIXTURE / name) != expected_hash:
            raise ValueError('maintained fixture identity mismatch: ' + name)
    result = assess(document['observations'])
    if result != document['result']:
        raise ValueError('recorded verdict/counts/maxima do not match recalculation')
    return result


def raw_rows(bundle):
    spec = importlib.util.spec_from_file_location('function_branch_psf', SHARED)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    psf = bundle / 'collected/spectre/spectre-output/runs/case-statements/psf/tran.tran.tran'
    spectre = shared.read_psf(psf)
    response = load(bundle / 'evas-native.stdout.json')
    if not isinstance(response, dict) or not isinstance(response.get('transient'), dict):
        raise ValueError('EVAS response and transient metadata must be objects')
    nodes = response['nodes']
    if not isinstance(nodes, list) or any(not isinstance(node, str) for node in nodes):
        raise ValueError('EVAS nodes must be an array of names')
    if len(nodes) != len(set(nodes)):
        raise ValueError('duplicate EVAS node')
    if not set(NODES) <= set(nodes):
        raise ValueError('missing EVAS channel')
    times = response['transient']['times']
    solutions = response['solutions']
    if not isinstance(times, list) or not isinstance(solutions, list):
        raise ValueError('EVAS times and solutions must be arrays')
    if len(times) != len(solutions) or len(times) != len(spectre):
        raise ValueError('raw time/solution denominator mismatch')
    rows = []
    for source, t, solution in zip(spectre, times, solutions):
        if not isinstance(solution, dict) or not isinstance(solution.get('voltages'), list):
            raise ValueError('EVAS solution must contain a voltage array')
        if source['time'] != t or len(solution['voltages']) != len(nodes):
            raise ValueError('raw backend time/voltage width mismatch')
        rows.append(dict(time_s=t, Spectre_V={n:source[n] for n in NODES},
                         EVAS_V={n:solution['voltages'][nodes.index(n)] for n in NODES}))
    validate_rows(rows)
    normalized = load(bundle / 'normalized.json')['rows']
    if not isinstance(normalized, list) or any(not isinstance(row, dict) or not isinstance(row.get('voltages'), dict) for row in normalized):
        raise ValueError('normalized observations must be objects with voltage maps')
    if len(normalized) != len(rows) or any(
        a['time'] != b['time_s'] or a['voltages'] != b['Spectre_V'] for a, b in zip(normalized, rows)):
        raise ValueError('normalized rows differ from raw PSF')
    return rows


def check_raw(bundle, document):
    check_compact(document)
    for name, expected_hash in document['raw_artifact_sha256'].items():
        if sha(bundle / name) != expected_hash:
            raise ValueError('raw identity mismatch: ' + name)
    pair = load(bundle / 'PAIR.json')
    response = load(bundle / 'evas-native.stdout.json')
    tool = load(bundle / 'collected/spectre/spectre-output/TOOL_IDENTITY.json')
    prep = load(bundle / 'PREPARATION.json')
    actual_binding = dict(evas_commit=pair['head'], frontend_syntax_sha256=pair['source_sha256'],
                          kernel_sha256=pair['kernel_sha256'], EVAS_output_sha256=pair['output_sha256'],
                          engine=response['engine'], ir_schema_version=response['schema_version'],
                          spectre_version=tool['version'], spectre_binary_sha256=tool['binary_sha256'],
                          model_sha256=prep['source_sha256'], original_deck_sha256=prep['original_deck_sha256'],
                          executed_deck_sha256=prep['derived_deck_sha256'])
    if actual_binding != document['execution_binding']:
        raise ValueError('actual execution receipts differ from compact binding')
    request = load(bundle / 'native-query.json')
    if request['tolerances'] != document['requested_settings']['EVAS']:
        raise ValueError('EVAS requested settings mismatch')
    transient_settings = {k:v for k,v in request['transient'].items() if k != 'sources'}
    if transient_settings != document['requested_settings']['EVAS_transient']:
        raise ValueError('EVAS transient settings mismatch')
    if load(bundle / 'settings-readback.json') != document['effective_settings']['Spectre']:
        raise ValueError('Spectre settings readback mismatch')
    rows = raw_rows(bundle)
    if rows != document['observations']:
        raise ValueError('compact values differ from actual raw responses')
    return assess(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact', type=Path, default=Path(__file__).with_name('comparison.json'))
    parser.add_argument('--raw', type=Path, help='local-only frontend-reference-v1 bundle')
    args = parser.parse_args()
    try:
        document = load(args.compact)
        result = check_compact(document)
        if args.raw:
            result = check_raw(args.raw, document)
        print(json.dumps(dict(analysis_kind='raw reanalysis' if args.raw else 'compact arithmetic recheck',
                              checker_sha256=sha(Path(__file__)), result=result), indent=2, allow_nan=False))
        return 0 if result['finite_comparison'] == 'P' else 1
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(json.dumps(dict(status='ERROR', reason=str(error))))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
