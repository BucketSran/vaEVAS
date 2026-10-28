"""Fixed C8 transport and independent source-RN history contracts.

The archived programs were emitted by C8, not by downgrading current IR.
These helpers contain no EVAS evaluator or production rounding imports.
"""
import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures/history_migration'
INPUT_SHA = '24d593cd9599fa5a83807d2df49c72f7de28a4182ef587946e3d3968cd5f6abd'
C8_SHA = '9c8c9fdf469c7347f2b507ad231bd3a70e355d192b648fec6e6eecd25dfc6e98'
PROGRAM_SHA = {
    'affine-held': '5325d7f5d931faff8dfa8c56260a33a27f01800478a6a4d6afd482342a8122b1',
    'selected-body-alias377': '4f25b6de74f8ffe2b6026bd488d3dd5a2910762455afedd28a074127b330272d',
    'selected-ln135': 'add3c355881d8f57f381f6b4b0712df5f772f70274b188da6893b9d2d14403e4',
}
TIMES = [i / 8 for i in range(9)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_cases():
    path = FIXTURES / 'history-native-source-inputs.json'
    assert sha(path) == INPUT_SHA
    return json.loads(path.read_text())


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def legacy_program(name):
    path = FIXTURES / (name + '.json')
    assert sha(path) == PROGRAM_SHA[name]
    value = json.loads(path.read_text())
    assert value['schema_version'] == 28
    assert not value.get('procedures') and not value.get('real_bindings')
    assert all(e.get('procedure_id') is None and e.get('expanded_statement_ordinal') is None
               for e in value['events'])
    assert not any(n.get('op') in {'real_binary', 'real_boundary', 'real_local', 'forcing'}
                   for n in walk(value))
    for state in value['states']:
        if isinstance(state['initial'], dict):
            assert name == 'selected-body-alias377' and state['name'] == 'q'
            assert state['initial']['op'] == 'select'
            assert {n['op'] for n in walk(state['initial']) if 'op' in n} == {'select', 'affine'}
    return value


def strict_equal(old, new, path=''):
    """JSON equality that does not accept bool/int or int/float substitutions."""
    assert type(old) is type(new), (path, type(old), type(new))
    if isinstance(old, dict):
        assert old.keys() == new.keys(), (path, old.keys(), new.keys())
        for key in old:
            strict_equal(old[key], new[key], path + '/' + key)
    elif isinstance(old, list):
        assert len(old) == len(new), (path, len(old), len(new))
        for i, (a, b) in enumerate(zip(old, new)):
            strict_equal(a, b, path + '/' + str(i))
    else:
        assert old == new, (path, old, new)


def response_body(value, schema, engine):
    result = copy.deepcopy(value)
    assert result.pop('schema_version') == schema
    assert result.pop('engine') == engine
    # The C8 baseline kernel predates the echoed request proof work limit. The
    # candidate echoes the default 1e9 for these default requests; that single
    # key is the only mapped difference, so it is checked and then removed.
    controls = result.get('observation_evidence', {}).get('effective_controls', {})
    if schema == 33 and 'proof_work_limit' in controls:
        assert controls.pop('proof_work_limit') == 1_000_000_000
    return result


def rn(value):
    """Integer quotient/remainder RN-even, independent of the compiler/core."""
    value = Fraction(value)
    if not value:
        return 0.0
    sign = -1 if value < 0 else 1
    n, d = abs(value.numerator), value.denominator
    exponent = n.bit_length() - d.bit_length()
    if exponent >= 0:
        if n < d << exponent:
            exponent -= 1
    elif n << -exponent < d:
        exponent -= 1
    shift = max(exponent - 52, -1074)
    if shift >= 0:
        d <<= shift
    else:
        n <<= -shift
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2):
        q += 1
    return math.copysign(math.ldexp(float(q), shift), sign)


def input_at(t, start=.7, end=-.3):
    # PWL is physical interpolation; sampling into a source real is RN.
    exact = Fraction.from_float(start) + (Fraction.from_float(end) -
            Fraction.from_float(start)) * Fraction.from_float(t)
    return rn(exact)


def selected_ln_x(t):
    v = Fraction.from_float(input_at(t))
    difference = rn(v - Fraction.from_float(.2))
    stored = rn(Fraction.from_float(abs(difference)))
    return rn(Fraction.from_float(.1 if stored < .1 else stored))


def selected_ln_oracle(t):
    # ln remains the mathematical memoryless function of the rounded program
    # value. Do not round the transcendental result to a source store here.
    with localcontext() as context:
        context.prec = 100
        return Decimal.from_float(selected_ln_x(t)).ln()


def assert_voltage(test, response, node, expected):
    index = response['nodes'].index(node)
    assert len(response['solutions']) == len(TIMES)
    bounds = response['observation_evidence']['voltage_bounds_V']
    assert len(bounds) == len(TIMES)
    for t, solution, box in zip(TIMES, response['solutions'], bounds):
        want = expected(t)
        if isinstance(want, Fraction):
            want = Decimal(want.numerator) / Decimal(want.denominator)
        test.assertLess(abs(solution['voltages'][index] - float(want)), 1e-10, (node, t))
        test.assertLessEqual(Decimal.from_float(box[index][0]), want, (node, t))
        test.assertGreaterEqual(Decimal.from_float(box[index][1]), want, (node, t))
        controls = response['observation_evidence']['effective_controls']
        tolerance = controls['absolute_V'] + controls['relative'] * max(abs(box[index][0]), abs(box[index][1]))
        test.assertLessEqual((box[index][1] - box[index][0]) / 2, tolerance, (node, t, 'certificate width'))


def audit_native_program(name, old, new):
    assert new['schema_version'] == 33 and len(new['procedures']) == 1
    key = lambda s: (s['instance'], s['name'], s['kind'])
    assert len({key(s) for s in new['states']}) == len(new['states'])
    assert [key(s) for s in old['states']] == [key(s) for s in new['states']]
    assert old['nodes'] == new['nodes']
    expected_names = {'affine-held': ['z', 'pol', 'mix'],
                      'selected-body-alias377': ['selected'], 'selected-ln135': ['x']}
    assert [b['name'] for b in new['real_bindings']] == expected_names[name]
    for binding in new['real_bindings']:
        assert binding['procedure_id'] == new['procedures'][0]['procedure_id']
        assert binding['lifetime'] == 'occurrence'
        assert binding['origin']['instance'] == new['procedures'][0]['instance']
    assert len(old['contributions']) == len(new['contributions'])
    assert len(old['operators']) == len(new['operators'])
    steps = [n for n in walk(new['procedures'][0]['body']) if 'action' in n]
    ordinals = [n['expanded_statement_ordinal'] for n in steps]
    assert ordinals == list(range(len(steps)))
    gates = [s['action']['event'] for s in steps if s['action']['kind'] == 'event_gate']
    assert len(gates) == len(set(gates)) == len(new['events'])
    for index, event in enumerate(new['events']):
        assert event['procedure_id'] == new['procedures'][0]['procedure_id']
        step = next(s for s in steps if s['action'].get('event') == index and
                    s['action']['kind'] == 'event_gate')
        assert step['expanded_statement_ordinal'] == event['expanded_statement_ordinal']
    old_events = {(e['trigger']['kind'], json.dumps(e['origin'], sort_keys=True)): e for e in old['events']}
    new_events = {(e['trigger']['kind'], json.dumps(e['origin'], sort_keys=True)): e for e in new['events']}
    assert len(new_events) == len(new['events'])
    assert old_events.keys() <= new_events.keys()
    for identity, event in old_events.items():
        strict_equal(event['trigger'], new_events[identity]['trigger'])
    assert len(new_events) - len(old_events) == (0 if name == 'selected-ln135' else 1)
    if name == 'selected-ln135':
        assert not new['events'] and not new['states']
        assert any(n.get('op') == 'real_binary' and n['operation'] == 'subtract' for n in walk(new))
        assert any(n.get('kind') == 'sample' for n in walk(new))
        assert any(n.get('kind') == 'snapshot' for n in walk(new))
        assert any(n.get('kind') == 'procedure_if' and n['relation'] == 'lt' for n in walk(new))


def map_stateless_controller_metadata(previous, current):
    """Validate this route migration before mapping its exact metadata fields."""
    old = previous['observation_evidence']
    new = current['observation_evidence']
    strict_equal(old['effective_controls']['max_step_applied'], False)
    strict_equal(new['effective_controls']['max_step_applied'], True)
    strict_equal(old['sample_origins'], ['stateless_working_point'] * len(TIMES))
    strict_equal(new['sample_origins'], ['accepted_controller_frame'] * len(TIMES))
    strict_equal(previous['transient']['accepted_steps'], 0)
    strict_equal(current['transient']['accepted_steps'], len(TIMES) - 1)
    strict_equal(previous['transient']['discarded_trials'], 0)
    strict_equal(current['transient']['discarded_trials'], 0)
    for solution in current['solutions']:
        for field in ('max_scaled_residual_ratio', 'max_voltage_correction_v',
                      'max_voltage_correction_ratio'):
            strict_equal(solution.pop(field), 0.0)
    new['effective_controls']['max_step_applied'] = False
    new['sample_origins'] = old['sample_origins'][:]
    current['transient']['accepted_steps'] = 0


def compare_native_response(test, name, old, new, program, engine):
    """Only named semantic differences are mapped; every other field is strict."""
    previous = response_body(old, 28, 'evas-events-0.21.0')
    current = response_body(new, 33, engine)
    test.assertEqual(current['transient']['times'], TIMES)
    if name != 'selected-ln135':
        initial = current['transient']['events'][0]
        origin = ('legacy.va:7:3 (one)' if name == 'affine-held' else 'alias.va:4:1 (one)')
        initial_id = next(i for i, event in enumerate(program['events'])
                          if event['trigger']['kind'] == 'initial_step')
        after = 0.0 if name == 'affine-held' else .75
        strict_equal(initial, dict(time=0.0, event=initial_id, origin=origin,
                                   kind='initial_step', before=[0.0], after=[after]))
        test.assertEqual(len(current['transient']['events']), 2)
        # Validate this single added record before mapping the old timer record.
        del current['transient']['events'][0]
        records = current['portability_advisories']['records']
        test.assertEqual(len(records), len(previous['portability_advisories']['records']))
        for a, b in zip(previous['portability_advisories']['records'], records):
            test.assertEqual(b['event_record'], a['event_record'] + 1)
            b['event_record'] -= 1
        strict_equal(previous, current)
        if name == 'affine-held':
            def affine(t):
                u = Fraction.from_float(rn(Fraction.from_float(t) / 2))
                sub = rn(u - Fraction(1, 2))
                product = rn(Fraction(5, 4) * Fraction.from_float(sub))
                scaled = rn(Fraction.from_float(product) * Fraction(1))
                return Fraction.from_float(rn(Fraction(1, 2) + Fraction.from_float(scaled)))
            assert_voltage(test, new, 'y', affine)
            assert_voltage(test, new, 'metric', lambda t: min(Fraction(1), max(Fraction(0), (Fraction.from_float(t) - Fraction(1,4))*8)))
        else:
            assert_voltage(test, new, 'y', lambda t: Fraction(3,4) if t <= .25 else Fraction(5,8))
    else:
        assert_voltage(test, new, 'y', selected_ln_oracle)
        map_stateless_controller_metadata(previous, current)
        # Validate all unchanged physical inputs, metadata, controller records,
        # residuals and certificate fields. Only y's RN-dependent point and box
        # have a different contract, checked above with the original thresholds.
        y = current['nodes'].index('y')
        for a, b in zip(previous['solutions'], current['solutions']):
            a['voltages'][y] = b['voltages'][y]
        for a, b in zip(previous['observation_evidence']['voltage_bounds_V'],
                        current['observation_evidence']['voltage_bounds_V']):
            a[y] = b[y]
        strict_equal(previous, current)


def run_case(kernel, program, case, evidence, *, expected_sha, max_step=1):
    import os
    import subprocess
    kernel = Path(kernel).resolve()
    assert sha(kernel) == expected_sha, ('kernel identity before exec', str(kernel))
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=False)
    request = dict(program=program, driven=case['driven'], samples=[], transient=dict(
        pwl=case['pwl'], output_times=TIMES, stop=1, max_step=max_step))
    payload = json.dumps(request, indent=2) + '\n'
    (evidence / 'request.json').write_text(payload)
    (evidence / 'kernel-identity.json').write_text(json.dumps(dict(
        path=str(kernel), expected_sha256=expected_sha), indent=2) + '\n')
    result = subprocess.run([str(kernel)], input=payload, text=True, capture_output=True,
                            timeout=20, env=dict(os.environ, EVAS_DIAGNOSTICS_PATH=str(evidence / 'diagnostics.json')))
    (evidence / 'stdout.json').write_text(result.stdout)
    (evidence / 'stderr.txt').write_text(result.stderr)
    (evidence / 'returncode.json').write_text(json.dumps(result.returncode) + '\n')
    assert sha(kernel) == expected_sha, ('kernel identity after exec', str(kernel))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), json.loads((evidence / 'diagnostics.json').read_text())
