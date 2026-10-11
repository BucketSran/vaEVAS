"""Finite SH-X boundary diagnostics. This does not grant callback qualification."""
from fractions import Fraction
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'evas/validation/paper'))
from precision_v2 import load_contract, rows_digest
from precision_reference import pwl_exact, outward


def roots_and_times(card):
    canonical = next(c for c in load_contract()['cards'] if c['id'] == 'SH-X-RAMP')
    if card != canonical:
        raise ValueError('boundary probe requires the frozen SH-X-RAMP fixture')
    roots = []
    for (a, u), (b, v) in zip(card['inputs']['clk'], card['inputs']['clk'][1:]):
        if u < .5 <= v:
            a, b, u, v = map(Fraction, (a, b, u, v))
            roots.append(a + (Fraction(1, 2)-u)*(b-a)/(v-u))
    if len(roots) != card['expected_events']:
        raise ValueError('independent root count differs from the fixture')
    times = set()
    for root in roots:
        times.add(float(root))
        for side in (-math.inf, math.inf):
            t = float(root)
            for _ in range(3):
                t = math.nextafter(t, side)
                times.add(t)
    return roots, sorted(times)


def assess_boundaries(card, rows):
    roots, times = roots_and_times(card)
    if (not rows or any(any(type(r.get(k)) not in (int, float) or not math.isfinite(r[k])
                            for k in ('time', 'count', 'y', 'u', 'clk')) for r in rows)
            or any(b['time'] <= a['time'] for a, b in zip(rows, rows[1:]))):
        raise ValueError('invalid finite, ordered native observations')
    indexed = {r['time']: r for r in rows}
    missing = [t for t in times if t not in indexed]
    if missing:
        raise ValueError('missing exact native boundary observations')
    checks = []
    for t in times:
        row = indexed[t]
        count = sum(Fraction(t) >= root for root in roots)
        expected = (Fraction(card['initial_V']) if count == 0 else
                    pwl_exact(card['inputs']['u'], roots[count-1]))
        error = abs(Fraction(row['y'])-expected)
        checks.append({'time_s': t, 'expected_count': count, 'actual_count': row['count'],
                       'count_matches': row['count'] == count,
                       'held_error_upper_V': outward(error, True)})
    return {'method': 'represented-source-neighbor-queries-v1',
            'waveform_rows_sha256': rows_digest(rows),
            'roots_rational_s': [str(r) for r in roots], 'observations': checks,
            'matching_counts': sum(c['count_matches'] for c in checks),
            'total_count_checks': len(checks),
            'held_error_upper_V': max(c['held_error_upper_V'] for c in checks),
            'callback_qualification': 'not_established',
            'scope': 'observable states at the listed binary64 times; no assertion about unobserved callback time or all-time error'}
