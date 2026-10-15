"""Independent finite answers and retained negative controls; standard library only."""
import argparse
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
TIMES = [Q(i, 8) for i in range(9)]
BUDGET = Q('1e-7')
NODES = {'u', 'y', 'w'}
CASES = {'original', 'singular-initial', 'constraint-change'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(token, encoding):
    require(isinstance(token, str), 'raw numeric tokens must remain strings')
    if encoding == 'decimal_tokens':
        return Q(token)
    require(encoding == 'binary64_hex', 'unknown encoding')
    require(token.lstrip('-').startswith('0x') and 'p' in token, 'not a binary64 hex token')
    value = float.fromhex(token)
    require(math.isfinite(value), 'nonfinite binary64 value')
    return Q(value)


def observations(backend):
    require(isinstance(backend['rows'], list), 'rows must be an array')
    rows = []
    for row in backend['rows']:
        require(set(row) == {'time', 'voltages'}, 'unexpected observation fields')
        require(set(row['voltages']) == NODES, 'voltage columns changed')
        rows.append((number(row['time'], backend['encoding']),
                     {n: number(v, backend['encoding']) for n, v in row['voltages'].items()}))
    require(all(a[0] < b[0] for a, b in zip(rows, rows[1:])), 'native times repeat or are unordered')
    return rows


def answer(t):
    # z=y+y², z'=rate*(1+2y) on the regular branch gives y'=rate.
    # z0=5/16 selects local y0=1/4, rate changes 1 -> 2 at 1/2.
    return {'u': Q(0), 'y': Q(1, 4)+t if t <= Q(1, 2) else Q(3, 4)+2*(t-Q(1, 2)),
            'w': 3+t}


def original_math(reference, dut):
    require([t for t, _ in reference] == TIMES, 'Spectre forcing points changed/missing')
    require([t for t, _ in dut] == TIMES, 'EVAS forcing points changed/missing')
    errors = {n: {'spectre_vs_answer': Q(0), 'evas_vs_answer': Q(0), 'paired': Q(0)} for n in NODES}
    for (time, sp), (_, ev) in zip(reference, dut):
        expected = answer(time)
        for node in NODES:
            for kind, error in [('spectre_vs_answer', abs(sp[node]-expected[node])),
                                ('evas_vs_answer', abs(ev[node]-expected[node])),
                                ('paired', abs(ev[node]-sp[node]))]:
                errors[node][kind] = max(errors[node][kind], error)
                require(error <= BUDGET, f'{node} {kind} exceeds fixed 1e-7 V budget')
    return {n: {kind: float(value) for kind, value in sorted(values.items())}
            for n, values in sorted(errors.items())}


def settings(backend):
    s = backend['effective_from_psf']
    require(s['version'] == '21.1.0.509.isr12', 'reference version changed')
    for field, expected in {'start': 0, 'stop': 1, 'reltol': Q('1e-9'), 'abstol(V)': Q('1e-9'),
                            'abstol(I)': Q('1e-12'), 'maxstep': 1, 'lteratio': Q('3.5')}.items():
        require(Q(s[field]) == expected, f'effective Spectre {field} changed')
    for field, expected in {'method': 'traponly', 'errpreset': 'moderate', 'relref': 'sigglobal'}.items():
        require(s[field] == expected, f'effective Spectre {field} changed')


def analyze(data):
    require(set(data) == {'compact_schema_version', 'qualification', 'cases'}, 'compact record fields changed')
    require(data['compact_schema_version'] == 1, 'unknown compact schema')
    require(data['qualification'] == 'not_qualified', 'no Q/callback qualification was established')
    require(set(data['cases']) == CASES, 'case matrix changed')
    matrix = []
    diagnostics = {}
    for name in ['original', 'singular-initial', 'constraint-change']:
        case = data['cases'][name]
        require(set(case) == {'role', 'spectre', 'evas'}, 'case fields/classification changed')
        require(case['role'] == ('positive' if name == 'original' else 'negative'), 'negative case relabelled')
        sp, ev = case['spectre'], case['evas']
        require(sp['status'] == 'completed' and sp['returncode'] == 0 and sp['timeout'] is False,
                'actual Spectre completion identity changed')
        settings(sp)
        rows = observations(sp)
        require(len(rows) == 9, 'Spectre native row denominator changed')
        require(rows[0][0] == 0 and rows[-1][0] == 1, 'native initial/stop point missing')
        require(all(abs(v['w']-(3+t)) <= BUDGET and v['u'] == 0 for t, v in rows),
                'retained input/unrelated-history observations changed')
        if name == 'original':
            require(ev['status'] == 'completed' and ev['returncode'] == 0 and ev['timeout'] is False,
                    'positive EVAS request did not complete')
            controls = ev['effective_from_response']
            for field, value in {'absolute_V': 1e-9, 'relative': 1e-9, 'stop_s': 1., 'max_step_s': 1.}.items():
                require(controls[field] == value, 'forwarded EVAS control changed')
            require(controls['max_step_applied'] is True, 'EVAS step application changed')
            require(ev['events'] == [{'time': .5, 'kind': 'timer', 'before': [1.], 'after': [2.]}],
                    'EVAS timer/state history changed')
            errors = original_math(rows, observations(ev))
            matrix.extend([{'case': name, 'backend': backend, 'classification': 'finite_numeric_pass'}
                           for backend in ['spectre', 'evas']])
        else:
            require(ev['status'] == 'rejected' and type(ev['returncode']) is int and ev['returncode'] != 0
                    and ev['timeout'] is False and ev['rows'] == [], 'negative EVAS case was accepted/lost')
            error = ev['error']
            expected = 'waveform_accuracy' if name == 'singular-initial' else 'unsupported_implicit_dynamics'
            require(error['kind'] == expected and error['stage'] == 'kernel' and error['code'] == 'kernel.'+expected,
                    'negative control diagnostic changed')
            if name == 'singular-initial':
                require([t for t, _ in rows] == TIMES, 'singular reference observations changed')
                require('continuous DC initialization' in error['message'], 'not an initial-root certification refusal')
                equilibrium = max(abs(v['y']+Q(1, 2)) for _, v in rows)
                require(equilibrium <= BUDGET, 'reference no longer observes the singular equilibrium')
                diagnostics[name] = {'max_distance_to_singular_equilibrium_V': float(equilibrium),
                                     'meaning': 'F_v=0 invalidates index-one uniqueness; reference rc0 is not a pass'}
                classification = 'singular_equilibrium_observed_unqualified'
            else:
                missing = [str(t) for t in TIMES if t not in [s for s, _ in rows]]
                require(missing == ['1/2'], 'retained missing forcing-point set changed')
                notes = '\n'.join(sp['log_observations'])
                require('Newton iteration fails' in notes and 'SPECTRE-17087' in notes
                        and 'stepped over' in notes, 'disaster-recovery observation was dropped')
                require('branch reselection' in error['message'], 'not the finite constraint-change refusal')
                old_flow = max(abs(v['y']-(Q(1, 4)+t)) for t, v in rows)
                diagnostics[name] = {'missing_forcing_points_s': missing,
                                     'max_distance_to_old_rate1_flow_V': float(old_flow),
                                     'meaning': 'no real post-jump root if physical z is retained; hidden rate/shift/idt states were not exported'}
                classification = 'missing_observation_and_disaster_recovery_not_pass'
            matrix.extend([{'case': name, 'backend': 'spectre', 'classification': classification},
                           {'case': name, 'backend': 'evas', 'classification': 'expected_rejection_control'}])
    # Matrix classifications distinguish numerical positives from negative controls.
    require(len(matrix) == 6, 'backend matrix lost a row')
    return {'analysis_id': 'implicit-event-restart-finite-v1', 'qualification': 'not_qualified',
            'positive_model_finite_passes': 1, 'positive_models': 1,
            'evas_expected_rejection_controls': 2, 'spectre_negative_completions_not_passes': 2,
            'backend_matrix': matrix, 'positive_max_error_V': errors, 'negative_observations': diagnostics}


def load_package(base=BASE):
    receipt = json.loads((base/'receipt.json').read_text())
    for relative, expected in receipt['retained_files_sha256'].items():
        path = (base/relative).resolve()
        require(path.is_relative_to(base.resolve()), 'retained path escapes package')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, f'retained identity changed: {relative}')
    data = json.loads((base/'records.json').read_text())
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    args = parser.parse_args()
    result = analyze(load_package(args.base))
    retained = args.base/'result.json'
    if retained.exists():
        require(result == json.loads(retained.read_text()), 'retained result disagrees with independent reanalysis')
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
