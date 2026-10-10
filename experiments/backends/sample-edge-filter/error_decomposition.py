"""Separate nominal-model accuracy, observed callback timing, and backend residuals.

Conditioning uses only native counter-change times, never measured held/edge/filter
values. It diagnoses errors; it does not replace the original acceptance checker.
The rational polygon / Decimal convolution is independent of the EVAS kernel.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction as F
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'evas/validation/sample_edge_filter'),
               str(ROOT / 'experiments/backends/paper')]
from contract import CASES, INPUT, CLOCK, RESET, T, initial, source
from inputs import sha, save
from observations import read_native
from runner import stage_failure
from boundary_replay import inspect as strict_inspect


def decimal(value):
    if isinstance(value, F):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)


def pwl(points, time):
    if time <= F(points[0][0]):
        return F(points[0][1])
    for (a, u), (b, v) in zip(points, points[1:]):
        a, b, u, v = map(F, (a, b, u, v))
        if time <= b:
            return u + (v-u)*(time-a)/(b-a)
    return F(points[-1][1])


def nominal_times(config, inputs, stop):
    if config['cross']:
        roots = set()
        for name in ('clk', 'rst'):
            for (a, u), (b, v) in zip(inputs[name], inputs[name][1:]):
                a, u, b, v = map(F, (a, u, b, v))
                if u < F(1, 2) <= v:
                    roots.add(a + (b-a)*(F(1, 2)-u)/(v-u))
        return sorted(roots)
    start, period = F(config['phase']), F(config['period'])
    return [start+k*period for k in range(int((F(stop)-start)//period)+1)]


def callback_times(rows, name, expected):
    if not rows or rows[0]['time'] != 0 or rows[0][name+'n'] != 0:
        raise ValueError('missing initial zero counter')
    result, previous_time, previous_count = [], -math.inf, 0
    for row in rows:
        time, count = row['time'], row[name+'n']
        if not math.isfinite(time) or time <= previous_time:
            raise ValueError('nonfinite or unordered native time')
        if not math.isfinite(count) or count != int(count) or count not in (previous_count, previous_count+1):
            raise ValueError('invalid counter sequence')
        if count == previous_count+1:
            result.append(F(time))
        previous_time, previous_count = time, count
    if len(result) != expected:
        raise ValueError('missing or extra callback')
    return result


class Reference:
    """Exact rational edge polygon with a 60-digit analytical filter evaluation.

    Parameters and PWL inputs are the binary64 values actually frozen for the VA
    experiment. Times are seconds. This finite-point evaluation is not an interval
    certificate or a proof over every time in a continuous trajectory.
    """
    def __init__(self, config, inputs, initial_value, event_times):
        self.config = config
        self.initial = F(initial_value)
        self.tau = F(config['tau'])
        self.events = []
        for time in event_times:
            value = (F(.25) if config['cross'] and pwl(inputs['rst'], time) > F(.25)
                     else F(config['gain'])*pwl(inputs['u'], time)+F(config['bias']))
            self.events.append((time, value))
        value = origin = target = self.initial
        slope = start = F(0)
        self.knots = [(start, value, slope)]
        for event, new in self.events:
            activation = event+F(config['delay'])
            if new == target:
                continue
            if slope:
                end = start+(target-value)/slope
                if end <= activation:
                    self.knots.append((end, target, F(0)))
                    value, slope, start = target, F(0), end
            current = value+slope*(activation-start)
            new_origin = (origin if (new-current)*slope > 0 else target) if slope else current
            new_slope = ((new-new_origin)/F(config['rise'] if new > current else config['fall'])
                         if new != current else F(0))
            value, start, origin, target, slope = current, activation, new_origin, new, new_slope
            self.knots.append((start, value, slope))
        if slope:
            self.knots.append((start+(target-value)/slope, target, F(0)))

    def at(self, time):
        with localcontext() as ctx:
            ctx.prec = 60
            fired = [(t, v) for t, v in self.events if t <= time]
            held = fired[-1][1] if fired else self.initial
            a, value, slope = next(k for k in reversed(self.knots) if k[0] <= time)
            edge = value+slope*(time-a)
            filtered, old_slope = decimal(self.initial), F(0)
            tau = decimal(self.tau)
            for a, _, slope in self.knots:
                if a > time:
                    break
                h = decimal(time-a)
                filtered += decimal(slope-old_slope)*(h-tau*(1-(-h/tau).exp()))
                old_slope = slope
            return dict(h=decimal(held), e=decimal(edge), f=filtered, n=len(fired))


def split_error(reference, candidate, conditioned, nominal):
    # S-E = (S-Rs) + (Rs-R0) - (E-R0), evaluated at each same physical time.
    sr, shift, er = reference-conditioned, conditioned-nominal, candidate-nominal
    return dict(reference_residual=sr, callback_shift=shift, candidate_residual=er,
                direct_difference=reference-candidate,
                reconstruction_error=(reference-candidate)-(sr+shift-er))


def verify_manifest(root, filename, expected_digest):
    if sha(root/filename) != expected_digest:
        raise ValueError('archive manifest differs from retained receipt')
    manifest = json.loads((root/filename).read_text())
    for name, digest in manifest.items():
        if sha(root/name) != digest:
            raise ValueError('changed archived artifact: '+name)


def verify_archives(spectre, evas):
    """Bind this archived batch to its earlier retained receipts, not a new lock."""
    retained = Path(__file__).parent
    original = json.loads((retained/'receipt.json').read_text())
    boundary = json.loads((retained/'boundary-receipt.json').read_text())
    verify_manifest(spectre, 'FILE_MANIFEST.json', original['spectre']['file_manifest_sha256'])
    results_key = 'runs/sample-edge-filter-20261010/boundary/evas/RESULTS.json'
    if sha(evas/'RESULTS.json') != boundary['artifacts'][results_key]:
        raise ValueError('EVAS result index differs from retained receipt')
    identity = json.loads((evas/'IDENTITY.json').read_text())
    if identity['kernel_sha256'] != boundary['implementation']['kernel_sha256']:
        raise ValueError('EVAS kernel identity differs from retained receipt')
    if json.loads(identity['kernel_identity']) != boundary['implementation']['identity']:
        raise ValueError('EVAS version identity differs from retained receipt')
    source_manifest = evas.parent/'SOURCE_MANIFEST.json'
    if sha(source_manifest) != boundary['implementation']['source_manifest_sha256']:
        raise ValueError('EVAS source manifest differs from retained receipt')
    sources = json.loads(source_manifest.read_text())
    if identity['source'] != {p: h for p, h in sources.items() if p.startswith('evas/src/')}:
        raise ValueError('EVAS Python source identity differs from retained source manifest')
    entries = json.loads((evas/'RESULTS.json').read_text())
    wanted = {(c['id'], 'native-'+s) for c in CASES for s in ('base', 'tight', 'fine')}
    selected = [e for e in entries if (e['case'], e['grid']) in wanted]
    if len(selected) != len(wanted) or {(e['case'], e['grid']) for e in selected} != wanted:
        raise ValueError('incomplete or duplicate EVAS result index')
    for entry in selected:
        directory = evas/entry['case']/entry['grid']
        if json.loads((directory/'RESULT.json').read_text()) != entry:
            raise ValueError('EVAS case receipt differs from anchored result index')
        if entry['assessment']['status'] == 'EXECUTION_FAILURE':
            raise ValueError('failed EVAS execution')
        if sha(directory/'response.json') != entry['response_sha256']:
            raise ValueError('EVAS response differs from anchored result index')
    return {p: sha(retained/p) for p in ('receipt.json', 'boundary-receipt.json')}


def read_pair(case, setting, spectre, evas):
    sp, ep = spectre/case['id']/setting, evas/case['id']/('native-'+setting)
    sreceipt = json.loads((sp/'RESULT.json').read_text())
    ereceipt = json.loads((ep/'RESULT.json').read_text())
    if stage_failure(sreceipt['execution']):
        raise ValueError('failed Spectre execution')
    raw = sp/'psf/tran.tran.tran'
    if sreceipt['raw_sha256'] != sha(raw):
        raise ValueError('raw identity mismatch')
    sr = read_native(raw, 'spectre')
    if sr != json.loads((sp/'rows.json').read_text()):
        raise ValueError('Spectre raw/rows mismatch')
    if ereceipt.get('response_sha256') != sha(ep/'response.json'):
        raise ValueError('EVAS response identity mismatch')
    response = json.loads((ep/'response.json').read_text())
    er = [dict(time=t, **dict(zip(response['nodes'], row['voltages'], strict=True)))
          for t, row in zip(response['transient']['times'], response['solutions'], strict=True)]
    if er != json.loads((ep/'rows.json').read_text()):
        raise ValueError('EVAS response/rows mismatch')
    if [r['time'] for r in sr] != [r['time'] for r in er]:
        raise ValueError('different observation grids')
    if not sr or sr[0]['time'] != 0 or any(not math.isfinite(v) for row in sr+er for v in row.values()):
        raise ValueError('incomplete or nonfinite observations')
    if (sp/'dut.va').read_text() != source(case):
        raise ValueError('frozen VA differs from the model being analyzed')
    request = json.loads((sp/'request.json').read_text())
    expected_inputs = {n: [[t*T, v] for t, v in points]
                       for n, points in [('u', INPUT), ('clk', CLOCK), ('rst', RESET)]}
    if request['inputs'] != expected_inputs or sr[-1]['time'] < request['stop']-5e-12:
        raise ValueError('wrong stimulus or incomplete stop coverage')
    return sr, er, response, request


def summarize_lane(config, sr, er, response, request):
    name = config['name']
    params = dict(config)
    for field in ('phase', 'period', 'delay', 'rise', 'fall', 'tau'):
        params[field] *= T
    nominal = nominal_times(params, request['inputs'], request['stop'])
    observed = callback_times(sr, name, len(nominal))
    # Validate candidate counter evidence too; do not condition its answer on it.
    callback_times(er, name, len(nominal))
    original = Reference(params, request['inputs'], float(initial(config)), nominal)
    conditioned = Reference(params, request['inputs'], float(initial(config)), observed)
    metrics = {p: {} for p in 'hef'}
    phases = dict(spectre_vs_nominal=0, evas_vs_nominal=0, spectre_vs_evas=0)
    bounds_misses = {p: 0 for p in 'hef'}
    bounds = response['observation_evidence']['voltage_bounds_V']
    indices = {p: response['nodes'].index(name+p) for p in 'hef'}
    if len(bounds) != len(er):
        raise ValueError('incomplete EVAS interval evidence')
    for index, (s, e) in enumerate(zip(sr, er, strict=True)):
        time = F(s['time'])
        r0, rs = original.at(time), conditioned.at(time)
        if s[name+'n'] != rs['n']:
            raise ValueError('conditioned reference lost observed phase')
        phases['spectre_vs_nominal'] += s[name+'n'] != r0['n']
        phases['evas_vs_nominal'] += e[name+'n'] != r0['n']
        phases['spectre_vs_evas'] += s[name+'n'] != e[name+'n']
        for port in 'hef':
            parts = split_error(Decimal(s[name+port]), Decimal(e[name+port]), rs[port], r0[port])
            for part, value in parts.items():
                if part not in metrics[port] or abs(value) > Decimal(metrics[port][part]['absolute_V']):
                    metrics[port][part] = dict(absolute_V=str(abs(value)), signed_V=str(value),
                                              row=index, time_s=s['time'], time_hex=s['time'].hex())
            lo, hi = bounds[index][indices[port]]
            if not all(math.isfinite(v) for v in (lo, hi)) or lo > hi:
                raise ValueError('invalid EVAS interval')
            bounds_misses[port] += not Decimal(lo) <= r0[port] <= Decimal(hi)
    return dict(instance=name, rows=len(sr), event_count=len(nominal),
                observed_callback_time_source='First native counter-change row; not hidden solver trials',
                callbacks=[dict(index=i+1, nominal_rational_s=str(a), observed_s=float(b),
                                offset_s=float(b-a), nominal_sample_V=str(original.events[i][1]),
                                conditioned_sample_V=str(conditioned.events[i][1]))
                           for i, (a, b) in enumerate(zip(nominal, observed, strict=True))],
                phase_differences=phases, maximum_terms=metrics,
                nominal_reference_outside_evas_reported_bounds=bounds_misses)


def analyze(spectre, evas, output):
    if output.exists():
        raise FileExistsError(output)
    anchors = verify_archives(spectre, evas)
    records = []
    with localcontext() as ctx:
        ctx.prec = 60
        for case in CASES:
            for setting in ('base', 'tight', 'fine'):
                record = dict(case=case['id'], setting=setting)
                try:
                    sr, er, response, request = read_pair(case, setting, spectre, evas)
                    record['instances'] = [summarize_lane(p, sr, er, response, request) for p in case['instances']]
                    record['observation_sha256'] = {
                        'spectre': sha(spectre/case['id']/setting/'rows.json'),
                        'evas': sha(evas/case['id']/('native-'+setting)/'response.json')}
                except (ValueError, KeyError, FileNotFoundError) as error:
                    record['analysis_failure'] = str(error)
                records.append(record)
                print(case['id'], setting, record.get('analysis_failure', 'analyzed'), flush=True)
    result = dict(kind='finite_point_error_decomposition_not_alignment_acceptance',
                  identity='S-E = (S-Rs) + (Rs-R0) - (E-R0); signed terms, not difference of maxima',
                  reference_precision_decimal_digits=60, fixed_configurations=12,
                  retained_receipt_sha256=anchors,
                  source_sha256={str(Path(__file__).relative_to(ROOT)): sha(Path(__file__)),
                                 'evas/validation/sample_edge_filter/contract.py': sha(ROOT/'evas/validation/sample_edge_filter/contract.py')},
                  spectre_manifest_sha256=sha(spectre/'FILE_MANIFEST.json'),
                  evas_identity=json.loads((evas/'IDENTITY.json').read_text()),
                  original_strict_verdict=strict_inspect(spectre, evas), records=records,
                  limits=['Reanalysis of archived actual runs; no new simulations.',
                          'Callback-conditioned answer diagnoses observed timing, not correct scheduling.',
                          'Residual includes source evaluation, arithmetic, operator implementation and integration; not pure LTE.',
                          '60-digit analytical point evaluation is not an interval proof or full-trajectory certificate.',
                          'All original models, thresholds, failures and exact-phase obligations remain unchanged.'])
    save(output, result)
    if any('analysis_failure' in r for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('spectre', type=Path)
    parser.add_argument('evas', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    analyze(args.spectre, args.evas, args.output)
