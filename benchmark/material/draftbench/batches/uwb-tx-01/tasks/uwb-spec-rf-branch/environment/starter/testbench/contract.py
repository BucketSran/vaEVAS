"""Public contract for the RF branch oscillator: stimuli, expected vro, checks.

Expected outputs are computed here from the Spec rules and the stimulus; the
checker never reads a reference model's waveform.
"""
from __future__ import annotations

import math

import uwbtask as u

EDGE = 2e-12            # stimulus edge (linear, centred on the stated time)
TOL_V = 5e-3            # S6: absolute vro error
EXCL = 3e-12            # S6: points this close to a pwr/rel crossing are not compared
TOL_ZC = 0.2e-12        # S6: zero-crossing time error
ZC_MARGIN = 5e-12       # S6: zero crossings closer than this to a release or stop are not compared
LN100 = math.log(100.0)
DEFAULTS = dict(f_rf=6e9, a_ro=1.0, t99_amp=200e-12, t99_freq=200e-12, df_start=0.01, phi0=0.0, vth=0.5)
RANGES = dict(f_rf=(4e9, 8e9), a_ro=(0.1, 1.5), t99_amp=(0.0, 1e-9), t99_freq=(0.0, 1e-9),
              df_start=(-0.05, 0.05), phi0=(-math.pi, math.pi), vth=(0.2, 1.0))
SIGNALS = ('pwr', 'pre', 'rel')


# ------------------------------------------------------------------ cases ---
# A case gives the input level changes [(time, level)] of pwr, pre and rel
# (all start low), the input level VIN, the instances and the stop time.

def public_cases():
    ideal = dict(t99_amp=0.0, t99_freq=0.0, df_start=0.0)
    cold_starts = dict(
        name='cold_starts', vin=1.0, stop=7.5e-9,
        instances=[dict(name='seed', params={}), dict(name='ideal', params=ideal)],
        # cold start 1 ends with pwr and rel falling together (branch off);
        # cold start 2 ends with rel falling while pwr stays high
        pwr=[(1.0e-9, 1), (3.5e-9, 0), (5.0e-9, 1), (7.0e-9, 0)],
        pre=[(1.0e-9, 1), (1.186e-9, 0), (5.0e-9, 1), (5.186e-9, 0)],
        rel=[(1.186e-9, 1), (3.5e-9, 0), (5.186e-9, 1), (6.5e-9, 0)])
    return [cold_starts]


# --------------------------------------------------------------- netlist ---

def ramp_cross(t_mid, v0, v1, vth):
    """Crossing time of a linear EDGE-long ramp centred on t_mid."""
    return t_mid - EDGE / 2 + (vth - v0) / (v1 - v0) * EDGE


def crossings(case, sig, vth):
    """[(time, direction)] of one input through vth; direction 1 rising, 0 falling."""
    vin, out, prev = case['vin'], [], 0
    for t, lv in case[sig]:
        if lv != prev:
            out.append((ramp_cross(t, prev * vin, lv * vin, vth), lv))
            prev = lv
    return out


def stimulus(case):
    return '\n'.join(f'V{s} ({s} 0) vsource type=pwl wave={u.pwl_levels([(0.0, 0)] + case[s], EDGE, case["vin"])}'
                     for s in SIGNALS)


def node(inst):
    return f'vro_{inst["name"]}'


def netlist(case, candidate, tb_dir, stop):
    lines = ['simulator lang=spectre', 'global 0', f'ahdl_include "{candidate}"', stimulus(case)]
    for inst in case['instances']:
        params = ' '.join(f'{key}={val!r}' for key, val in inst['params'].items())
        lines.append(f'X{inst["name"]} (pwr pre rel {node(inst)}) rf_ro_branch {params}'.rstrip())
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={stop!r} maxstep=1p',
              'save ' + ' '.join([node(i) for i in case['instances']] + list(SIGNALS))]
    return '\n'.join(lines) + '\n'


def stop_time(case):
    return case['stop']


# -------------------------------------------------------------- expected ---

def releases(case, params):
    """Released intervals [(t_release, t_stop)] (S1, S4) and the pwr/rel crossing times."""
    p = {**DEFAULTS, **params}
    ev = sorted([(t, s, d) for s in ('pwr', 'rel') for t, d in crossings(case, s, p['vth'])],
                key=lambda e: (e[0], e[2]))          # at equal times, falls before rises
    level = dict(pwr=0, rel=0)
    out, t_rel = [], None
    for t, s, d in ev:
        level[s] = d
        if s == 'rel' and d == 1 and level['pwr'] and t_rel is None:
            t_rel = t                                 # S1 release
        elif d == 0 and t_rel is not None:
            out.append((t_rel, t))                    # S4 stop: rel or pwr falls
            t_rel = None
    if t_rel is not None:
        out.append((t_rel, case['stop']))
    return out, [t for t, _, _ in ev]


def taus(p):
    return p['t99_amp'] / LN100, p['t99_freq'] / LN100


def phase(uu, p):
    """S2 phase at local time uu since the release."""
    _, tf = taus(p)
    extra = p['df_start'] * tf * (1 - math.exp(-uu / tf)) if tf > 0 else 0.0
    return p['phi0'] + 2 * math.pi * p['f_rf'] * (uu + extra)


def vro_expected(uu, p):
    """S2 output at local time uu since the release."""
    ta, _ = taus(p)
    amp = 1 - math.exp(-uu / ta) if ta > 0 else 1.0
    return p['a_ro'] * amp * math.cos(phase(uu, p))


def zero_crossings_expected(p, lo, hi):
    """Local times in [lo, hi] where the S2 phase equals pi/2 + k*pi (phase increases with u)."""
    k = math.ceil((phase(lo, p) - math.pi / 2) / math.pi)
    out = []
    while True:
        target = math.pi / 2 + k * math.pi
        if phase(hi, p) < target:
            return out
        a, b = lo, hi
        for _ in range(100):
            m = 0.5 * (a + b)
            a, b = (m, b) if phase(m, p) < target else (a, m)
        out.append(0.5 * (a + b))
        k += 1


def zc_window(p, length):
    """Local-time window for zero crossings: ZC_MARGIN from both ends, moved
    so that no expected crossing lies within 1 ps of an end."""
    lo, hi = ZC_MARGIN, length - ZC_MARGIN
    for _ in range(20):
        exp = zero_crossings_expected(p, lo - 1e-12, hi + 1e-12)
        near_lo = [z for z in exp if abs(z - lo) < 1e-12]
        near_hi = [z for z in exp if abs(z - hi) < 1e-12]
        if not near_lo and not near_hi:
            return lo, hi
        lo += 2e-12 if near_lo else 0
        hi -= 2e-12 if near_hi else 0
    return lo, hi


def zero_crossings_seen(times, values, t0, lo, hi):
    """Zero crossings of the saved waveform, by linear interpolation, at local times in [lo, hi]."""
    out = []
    pts = [(t - t0, v) for t, v in zip(times, values) if lo - 2e-12 <= t - t0 <= hi + 2e-12]
    for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
        if (v0 >= 0) != (v1 >= 0) and v0 != v1:
            z = u0 + (u1 - u0) * v0 / (v0 - v1)
            if lo <= z <= hi:
                out.append(z)
    return out


# ----------------------------------------------------------------- checks ---

def fmt(t):
    return f'{t * 1e9:.4f} ns'


def check(case, rows):
    reps, times = [], rows.get('time', [])
    for inst in case['instances']:
        rep = u.Report(f"{case['name']}/{inst['name']}")
        p = {**DEFAULTS, **inst['params']}
        vals = rows.get(node(inst))
        finite = vals is not None and len(vals) == len(times) > 0 and all(math.isfinite(v) for v in vals)
        rep.add('vro saved and finite at every saved point (S6)', f'{len(times)} points',
                'missing' if vals is None else f'{sum(math.isfinite(v) for v in vals)} finite', finite)
        if not finite:
            reps.append(rep)
            continue
        ivs, ctrl = releases(case, inst['params'])
        n_off = n_on = 0
        off_err = on_err = 0.0
        off_at = on_at = None
        for t, v in zip(times, vals):
            if any(abs(t - c) <= EXCL for c in ctrl):
                continue
            seg = [(a, b) for a, b in ivs if a < t < b]
            if seg:
                e = abs(v - vro_expected(t - seg[0][0], p))
                n_on += 1
                if e > on_err:
                    on_err, on_at = e, t
            else:
                e = abs(v)
                n_off += 1
                if e > off_err:
                    off_err, off_at = e, t
        rep.add('vro = 0 while off, precharging or stopped (S1, S4)', f'|vro| <= {TOL_V * 1e3:g} mV at {n_off} points',
                f'worst {off_err * 1e3:.3g} mV' + (f' at {fmt(off_at)}' if off_at else ''), off_err <= TOL_V)
        rep.add(f'vro follows S2 in each of {len(ivs)} releases (S2, S3)',
                f'|error| <= {TOL_V * 1e3:g} mV at {n_on} points',
                f'worst {on_err * 1e3:.3g} mV' + (f' at {fmt(on_at)}' if on_at else ''), on_err <= TOL_V and n_on > 0)
        seen_rel = []
        for j, (a, b) in enumerate(ivs):
            lo, hi = zc_window(p, b - a)
            want = zero_crossings_expected(p, lo, hi)
            got = zero_crossings_seen(times, vals, a, lo, hi)
            seen_rel.append(got)
            n = min(len(got), len(want))
            worst = max((abs(x - y) for x, y in zip(got, want)), default=0.0)
            info = ''
            if len(got) >= 3 and len(want) >= 3:
                info = (f'; first cycle {(got[2] - got[0]) * 1e12:.3f} ps (S2 {(want[2] - want[0]) * 1e12:.3f}), '
                        f'last {(got[-1] - got[-3]) * 1e12:.3f} ps (S2 {(want[-1] - want[-3]) * 1e12:.3f})')
            rep.add(f'release {j + 1} at {fmt(a)}: zero crossings match S2, start offset settling (S2)',
                    f'{len(want)} crossings, |error| <= {TOL_ZC * 1e12:g} ps',
                    f'{len(got)} crossings, worst {worst * 1e12:.3f} ps over {n}{info}',
                    len(got) == len(want) and worst <= TOL_ZC)
        if len(seen_rel) >= 2:
            m = min(len(z) for z in seen_rel)
            diff = max((abs(z[i] - seen_rel[0][i]) for z in seen_rel[1:] for i in range(m)), default=0.0)
            rep.add(f'{len(seen_rel)} cold starts repeat the same waveform from phi0 (S3)',
                    f'first {m} zero crossings after each release agree within {TOL_ZC * 1e12:g} ps',
                    f'worst difference {diff * 1e12:.3f} ps', m > 0 and diff <= TOL_ZC)
        reps.append(rep)
    return reps


# ----------------------------------------------------------------- domain ---

def domain_problems(case):
    """Author check that a case stays inside S5 (empty list when it does)."""
    bad, vin = [], case['vin']
    for inst in case['instances']:
        p = {**DEFAULTS, **inst['params']}
        bad += [f"{inst['name']}: {k} = {v} outside {RANGES[k]}" for k, v in p.items()
                if not RANGES[k][0] <= v <= RANGES[k][1]]
        if not p['vth'] + 0.3 <= vin <= 1.8:
            bad.append(f"{inst['name']}: VIN {vin} outside vth + 0.3 V .. 1.8 V")
        cr = {s: crossings(case, s, p['vth']) for s in SIGNALS}

        def level(s, t):
            lv = 0
            for tc, d in cr[s]:
                if tc <= t:
                    lv = d
            return lv
        pr = sorted([(t, s, d) for s in ('pwr', 'rel') for t, d in cr[s]])
        for (t0, s0, d0), (t1, s1, d1) in zip(pr, pr[1:]):
            together_fall = d0 == d1 == 0 and s0 != s1 and t1 - t0 <= EDGE
            if t1 - t0 < 100e-12 and not together_fall:
                bad.append(f"{inst['name']}: {s0}/{s1} crossings {fmt(t0)}, {fmt(t1)} closer than 100 ps")
        for t, d in cr['rel']:
            if d == 1 and level('pwr', t):
                ok = all(level('pwr', x) and level('pre', x) and not level('rel', x)
                         for x in [t - 100e-12 + k * 5e-12 for k in range(20)])
                if not ok:
                    bad.append(f"{inst['name']}: release at {fmt(t)} without 100 ps of precharge")
        near_pwr = lambda t: any(abs(t - x) <= EDGE for x, _ in cr['pwr'])  # noqa: E731
        for k in range(int(case['stop'] / 5e-12)):
            t = k * 5e-12
            if level('pre', t) and not level('pwr', t) and not near_pwr(t):
                bad.append(f"{inst['name']}: pre high while pwr is low at {fmt(t)}")
                break
        rel_hi = [(a, b) for (a, da), (b, _) in zip(cr['rel'], cr['rel'][1:] + [(case['stop'], 0)]) if da == 1]
        for a, b in rel_hi:
            if level('pre', a + EDGE):
                bad.append(f"{inst['name']}: pre still high {EDGE * 1e12:g} ps after rel rose at {fmt(a)}")
        for t, d in cr['pre']:
            if any(a + EDGE < t < b for a, b in rel_hi) or (d == 1 and any(a < t < b for a, b in rel_hi)):
                bad.append(f"{inst['name']}: pre crossing at {fmt(t)} while rel is high")
    return bad
