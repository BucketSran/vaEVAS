"""Independent analytic oracle for the VCO candidate. No reference-model import."""
import bisect
import math


def phase_cycles(t, case):
    total = 0.0
    controls = case['controls']
    for (ta, va), (tb, vb) in zip(controls, controls[1:]):
        end = min(t, tb)
        if end <= ta:
            break
        slope = (vb - va) / (tb - ta)
        cuts = [ta, end]
        if slope:
            for bound in (0.0, 1.0):
                crossing = ta + (bound - va) / slope
                if ta < crossing < end:
                    cuts.append(crossing)
        cuts.sort()
        for a, b in zip(cuts, cuts[1:]):
            ca = min(1.0, max(0.0, va + slope * (a - ta)))
            cb = min(1.0, max(0.0, va + slope * (b - ta)))
            total += (b-a) * (case['fmin'] + (case['fmax']-case['fmin'])*(ca+cb)/2.0)
        if t <= tb:
            break
    return total


def expected(t, case):
    return case['offset'] + case['amplitude'] * math.sin(2.0*math.pi*phase_cycles(t, case))


def evaluate(rows, case, work=None):
    failures=[]
    if len(rows) < 2:
        return dict(passed=False, failures=['missing waveform'])
    if any(not math.isfinite(row[key]) for row in rows for key in ('time', 'out')):
        return dict(passed=False, failures=['non-finite waveform'])
    times=[row['time'] for row in rows]
    if times[0] > 1e-15 or times[-1] < case['stop']*(1-1e-8):
        failures.append('incomplete time coverage')
    if any(b <= a for a,b in zip(times,times[1:])):
        failures.append('non-increasing time')
    phases=[phase_cycles(t,case) for t in times]
    max_phase_advance=max(b-a for a,b in zip(phases,phases[1:]))
    if 'max_phase_advance' in case and max_phase_advance>case['max_phase_advance']:
        failures.append('prescribed 64 samples per constant-frequency cycle not retained')
    point_errors=[abs(row['out']-expected(row['time'],case)) for row in rows]
    max_point_error=max(point_errors)
    # Independent uniformly spaced probes catch a candidate that returns a few
    # accurate points while skipping whole cycles between them.
    probe_error=0.0
    for i in range(4097):
        t=case['stop']*i/4096
        j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
        a,b=rows[j],rows[j+1]
        observed=a['out']+(b['out']-a['out'])*(t-a['time'])/(b['time']-a['time'])
        probe_error=max(probe_error,abs(observed-expected(t,case)))
    if not math.isfinite(max_point_error) or max_point_error > case['waveform_atol']:
        failures.append('analytic phase or amplitude mismatch')
    if not math.isfinite(probe_error) or probe_error > case['waveform_atol']:
        failures.append('inadequate waveform resolution')
    return dict(passed=not failures,failures=failures,max_point_error_v=max_point_error,
                max_interpolated_error_v=probe_error,saved_waveform_points=len(rows),
                expected_cycles=phase_cycles(case['stop'],case),max_phase_advance=max_phase_advance)
