"""Public contract for the pulse generator: stimuli, expected edges, checks.

Expected outputs are computed here from the Spec rules, the stimulus and the
tap edges of the fixed oscillator observed in the same run; the checker never
reads a reference model's waveform.
"""
from __future__ import annotations

import uwbtask as u

EDGE = 2e-12            # stimulus edge (linear, centred on the stated time)
TOL = 2e-12             # crossing-time tolerance
DEFAULTS = dict(n_width=9, n_pre=2, t_ovr=200e-12, vdd=1.0, vth=0.5, tr=2e-12)
RO = dict(f0=600e6, fstep=0.25e6, vdd=1.0, tr=2e-12)   # fixed public oscillator
SETUP = 25e-12          # descriptor bits change this long before enc_valid rises
SCRAMBLE = 40e-12       # scrambled cases: the bits change again this long after
EV_HIGH = 400e-12       # enc_valid high time (shorter when the next word is close)
OUTPUTS = ['pre_a', 'rf_a', 'pol_a', 'sel_a0', 'sel_a1', 'sel_a2',
           'pre_b', 'rf_b', 'pol_b', 'sel_b0', 'sel_b1', 'sel_b2', 'overrun']
RULE = dict(pre='precharge from tap edge s - n_pre to s on the scheduled lane (S4, S5, S7)',
            rf='RF window from tap edge s to s + n_width on the scheduled lane (S4, S5, S7)',
            pol='polarity set when the lane is scheduled (S6)',
            sel='frequency select set when the lane is scheduled (S6)',
            overrun='one pulse per overwritten pending descriptor (S3, S7)')


# --------------------------------------------------------------- tap grid ---

class Grid:
    """Nominal tap times of the fixed oscillator, used only to place stimuli."""

    def __init__(self, code, phase0=0.0):
        self.T = 1 / (RO['f0'] + RO['fstep'] * code)
        self.d = self.T / 16
        m0 = int(16 * phase0)
        self.r = 16 * phase0 - m0
        self.n1 = 16 - m0                      # tap intervals to the first ph[0] rise

    def frame(self, k):
        """Start of frame k (the k-th ph[0] rising edge after t = 0, k >= 1)."""
        return (self.n1 + 16 * (k - 1) - self.r) * self.d

    def at(self, k, frac):
        return self.frame(k) + frac * self.T

    def gap(self, k, j):
        """Middle of the interval between taps j and j + 1 of frame k."""
        return self.frame(k) + (j + 0.5) * self.d


def descs_at(grid, items):
    """items: [(frame, frac, P, F, pol)] -> [(t, P, F, pol)]."""
    return [(grid.at(k, f), P, F, q) for k, f, P, F, q in items]


# ------------------------------------------------------------------ cases ---

def public_cases():
    g = Grid(288)
    # every P, 7 -> 0 and 0 -> 7, the same F on touching windows (7 -> 0 on
    # alternating lanes), latches early, middle and late in the frame
    seq = [(7, 3, 0), (0, 3, 1), (7, 5, 1), (0, 2, 0), (3, 2, 0), (4, 6, 0), (1, 0, 1), (6, 7, 1),
           (2, 1, 1), (5, 4, 0), (7, 4, 0), (0, 4, 1), (0, 4, 1), (7, 7, 1)]
    fracs = [0.6, 0.15, 0.92, 0.6, 0.3, 0.85, 0.4, 0.95, 0.5, 0.1, 0.7, 0.25, 0.9, 0.45]
    positions = dict(name='positions', code=288, phase0=0.0, vin=1.0, scramble=False,
                     instances=[dict(name='a', params={})],
                     descs=descs_at(g, [(2 + i, f, *d) for i, (d, f) in enumerate(zip(seq, fracs))]),
                     en=[(0.0, 1)], rst=[(0.0, g.gap(0, 10))], stop=g.at(19, 0.5))
    # en low until the middle of frame 6: words of frames 2..5 overwrite each
    # other (overrun), the frame-5 word stays pending through the frame-6 edge
    # and is scheduled at the frame-7 edge; an overrun with en high (frame 9),
    # an empty frame (10), a word right after the edge that took its
    # predecessor (frame 12) and touching same-F windows (frames 11, 12)
    items = [(2, 0.5, 3, 1, 0), (3, 0.2, 5, 6, 1), (4, 0.8, 1, 2, 0), (5, 0.4, 6, 5, 1),
             (7, 0.6, 2, 7, 0), (8, 0.35, 7, 0, 1), (9, 0.1, 4, 4, 0), (9, 0.6, 0, 3, 1),
             (11, 0.9, 7, 6, 0), (12, 0.12, 0, 6, 1), (13, 0.5, 5, 1, 1)]
    late = dict(name='late_enable', code=288, phase0=0.0, vin=1.0, scramble=False,
                instances=[dict(name='a', params={})], descs=descs_at(g, items),
                en=[(0.0, 0), (g.at(6, 0.3), 1)], rst=[(0.0, g.gap(0, 10))], stop=g.at(17, 0.5))
    return [positions, late]


# --------------------------------------------------------------- netlist ---

def ramp_cross(t_mid, v0, v1, vth):
    """Crossing time of a linear EDGE-long ramp centred on t_mid."""
    return t_mid - EDGE / 2 + (vth - v0) / (v1 - v0) * EDGE


def ev_times(case):
    """(rise, fall) centre times of every enc_valid pulse."""
    ts = [d[0] for d in case['descs']]
    out = []
    for i, t in enumerate(ts):
        high = EV_HIGH if i + 1 == len(ts) else min(EV_HIGH, ts[i + 1] - t - 150e-12)
        out.append((t, t + high))
    return out


def stimulus(case):
    vin, descs = case['vin'], sorted(case['descs'])
    lines = []
    fields = [('p', b, lambda d, b=b: (d[1] >> b) & 1) for b in range(3)]
    fields += [('f', b, lambda d, b=b: (d[2] >> b) & 1) for b in range(3)]
    fields += [('pol', '', lambda d: d[3])]
    for name, b, val in fields:
        ch = [(0.0, 0)]
        for d in descs:
            ch.append((d[0] - SETUP, val(d)))
            if case['scramble']:          # bits only valid around the strobe
                ch.append((d[0] + SCRAMBLE, 1 - val(d)))
        lines.append(f'V{name}{b} ({name}{b} 0) vsource type=pwl wave={u.pwl_levels(ch, EDGE, vin)}')
    ev = [(0.0, 0)]
    for on, off in ev_times(case):
        ev += [(on, 1), (off, 0)]
    lines.append(f'Vev (ev 0) vsource type=pwl wave={u.pwl_levels(ev, EDGE, vin)}')
    lines.append(f'Ven (en 0) vsource type=pwl wave={u.pwl_levels(case["en"], EDGE, vin)}')
    rs = [(0.0, 1 if case['rst'] and case['rst'][0][0] == 0.0 else 0)]
    for on, off in case['rst']:
        if on > 0:
            rs.append((on, 1))
        rs.append((off, 0))
    lines.append(f'Vrst (rst 0) vsource type=pwl wave={u.pwl_levels(rs, EDGE, vin)}')
    code = case['code']
    lines += [f'Vc{b} (c{b} 0) vsource dc={(code >> b) & 1}' for b in range(10)]
    return '\n'.join(lines)


def vth_groups(case):
    return sorted({({**DEFAULTS, **i['params']})['vth'] for i in case['instances']})


def tap_id(group, j):
    return 1000 + 100 * group + j


def ids(k):
    base = 100 * (k + 1)
    names = OUTPUTS
    offs = [0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15, 20]
    return {n: base + o for n, o in zip(names, offs)}


def netlist(case, candidate, tb_dir, stop):
    taps = ' '.join(f'ph{j}' for j in range(15, -1, -1))
    lines = ['simulator lang=spectre', 'global 0',
             f'ahdl_include "{candidate}"',
             f'ahdl_include "{tb_dir / "master_ro16.va"}"',
             f'ahdl_include "{tb_dir / "edge_monitor.va"}"', stimulus(case),
             f'Xro ({" ".join(f"c{b}" for b in range(9, -1, -1))} {taps}) master_ro16 '
             f'phase0={case["phase0"]!r}']
    for g, vth in enumerate(vth_groups(case)):
        lines += [f'Xmon_t{g}_{j} (ph{j}) uwb_edge_monitor id={tap_id(g, j)} vth={vth!r}' for j in range(16)]
    for k, inst in enumerate(case['instances']):
        n = inst['name']
        pins = ([f'ph{j}' for j in range(15, -1, -1)] + ['p2', 'p1', 'p0', 'f2', 'f1', 'f0', 'pol', 'ev', 'en', 'rst']
                + [f'pre_a{n}', f'rf_a{n}', f'sel_a{n}2', f'sel_a{n}1', f'sel_a{n}0', f'pol_a{n}',
                   f'pre_b{n}', f'rf_b{n}', f'sel_b{n}2', f'sel_b{n}1', f'sel_b{n}0', f'pol_b{n}', f'overrun{n}'])
        params = ' '.join(f'{key}={val!r}' for key, val in inst['params'].items())
        lines.append(f'Xpg{n} ({" ".join(pins)}) pulse_generator {params}'.rstrip())
        vmon = {**DEFAULTS, **inst['params']}['vdd'] / 2
        for out, ident in ids(k).items():
            node = f'{out[:-1]}{n}{out[-1]}' if out[-1].isdigit() else f'{out}{n}'
            lines.append(f'Xmon_{node} ({node}) uwb_edge_monitor id={ident} vth={vmon!r}')
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={stop!r} maxstep=10p', 'save ev']
    return '\n'.join(lines) + '\n'


def stop_time(case):
    return case['stop']


# -------------------------------------------------------------- expected ---

def observed_taps(edges_seen, case, vth):
    """Rising crossings of every tap through the instance's vth: [(t, j)]."""
    g = vth_groups(case).index(vth)
    return sorted((t, j) for j in range(16) for t in edges_seen.times(tap_id(g, j), 1))


def en_level(case, vth):
    vin = case['vin']
    pts, prev = [], case['en'][0][1]
    for t, v in case['en'][1:]:
        if v != prev:
            pts.append((ramp_cross(t, prev * vin, v * vin, vth), v))
            prev = v
    init = case['en'][0][1]
    return lambda t: ([v for tc, v in pts if tc <= t] or [init])[-1]


def input_events(case, vth):
    vin = case['vin']
    ev = [(ramp_cross(t, 0, vin, vth), 'latch', (P, F, q)) for t, P, F, q in sorted(case['descs'])]
    for on, off in case['rst']:
        if on > 0:
            ev.append((ramp_cross(on, 0, vin, vth), 'rst_on', None))
        ev.append((ramp_cross(off, vin, 0, vth), 'rst_off', None))
    return ev


def expected(case, params, taps):
    """Expected vdd/2 crossings of every output of one instance (S2-S7).

    taps: observed tap rising crossings [(t, j)] at this instance's vth.
    Returns ({output: [(t, dir)]}, [scheduled window dicts]).
    """
    p = {**DEFAULTS, **params}
    half = p['tr'] / 2
    en_at = en_level(case, p['vth'])
    events = sorted([(t, 1, 'tap', j) for t, j in taps]
                    + [(t, 0, kind, x) for t, kind, x in input_events(case, p['vth'])], key=lambda e: e[:2])
    level = {n: 0 for n in OUTPUTS}
    edges = {n: [] for n in OUTPUTS}

    def put(name, t, v):
        if level[name] != v:
            edges[name].append((t + half, v))
            level[name] = v

    rst = bool(case['rst']) and case['rst'][0][0] == 0.0
    pend, lane, n = None, 0, 0
    win = dict(a=None, b=None)
    windows = []
    for t, _, kind, x in events:
        if kind == 'tap':
            n += 1                                      # tap rising edge number n
            for ln in 'ab':
                w = win[ln]
                if w is None:
                    continue
                if p['n_pre'] and n == w['p']:
                    put(f'pre_{ln}', t, 1)
                    w['t_p'] = t
                if n == w['s']:
                    put(f'pre_{ln}', t, 0)
                    put(f'rf_{ln}', t, 1)
                    w['t_s'] = t
                if n == w['e']:
                    put(f'rf_{ln}', t, 0)
                    w['t_e'] = t
                    win[ln] = None
            if x == 0 and not rst and en_at(t) and pend is not None:
                P, F, q = pend
                pend = None
                ln = 'ab'[lane]
                lane ^= 1
                s = n + 16 + P
                win[ln] = dict(lane=ln, desc=(P, F, q), t_sched=t, p=s - p['n_pre'], s=s, e=s + p['n_width'])
                windows.append(win[ln])
                for i in range(3):
                    put(f'sel_{ln}{i}', t, (F >> i) & 1)
                put(f'pol_{ln}', t, q)
        elif kind == 'latch':
            if rst:
                continue
            if pend is not None:
                edges['overrun'] += [(t + half, 1), (t + p['t_ovr'] + half, 0)]
            pend = x
        elif kind == 'rst_on':
            rst, pend, lane = True, None, 0
            for ln in 'ab':
                if win[ln] is not None:
                    win[ln]['t_rst'] = t
                put(f'pre_{ln}', t, 0)
                put(f'rf_{ln}', t, 0)
                win[ln] = None
        elif kind == 'rst_off':
            rst = False
    if any(win.values()):
        raise ValueError(f"{case['name']}: a window is still open at the end of the run; extend stop")
    edges['overrun'].sort()
    return edges, windows


# ----------------------------------------------------------------- checks ---

def check(case, edges_seen: u.Edges):
    reps = []
    for k, inst in enumerate(case['instances']):
        p = {**DEFAULTS, **inst['params']}
        rep = u.Report(f"{case['name']}/{inst['name']}")
        exp, windows = expected(case, inst['params'], observed_taps(edges_seen, case, p['vth']))
        m = ids(k)
        for name in OUTPUTS:
            got = edges_seen.by_id.get(m[name], [])
            want = exp[name]
            ok_dir = [d for _, d in got] == [d for _, d in want]
            label = name if not name[-1].isdigit() else f'{name[:-1]}[{name[-1]}]'
            rule = RULE[name.split('_')[0]] if name != 'overrun' else RULE['overrun']
            rep.times_match(f'{label} edges: {rule}', [t for t, _ in got] if ok_dir else [],
                            [t for t, _ in want], TOL)
        # diagnostic summary: lane outputs at each window start
        bad = []
        for w in windows:
            if 't_s' not in w:
                continue                                 # cancelled by a reset before it started
            ln, (P, F, q) = w['lane'], w['desc']
            ts = w['t_s'] + p['tr']
            sel = edges_seen.bus([m[f'sel_{ln}{i}'] for i in range(3)], ts)
            seen = (sel, edges_seen.level(m[f'pol_{ln}'], ts), edges_seen.level(m[f'rf_{ln}'], ts))
            if seen != (F, q, 1):
                bad.append((round(w['t_sched'] * 1e9, 4), ln, seen, (F, q, 1)))
        started = sum('t_s' in w for w in windows)
        rep.add('rf high with sel/pol = F/pol of the scheduled descriptor at each window start (S5, S6)',
                f'{started} windows', f'{started - len(bad)} correct; first wrong {bad[:2]}', not bad)
        reps.append(rep)
    return reps


def domain_margins(case, edges_seen: u.Edges):
    """Author check that a case stays inside S8 (not part of the score).

    Distances in ps; the S8 limits are 30 ps (enc_valid and en to frame
    edges, rst to tap edges and to enc_valid) and t_ovr + 100 ps (spacing).
    """
    out = {}
    for inst in case['instances']:
        p = {**DEFAULTS, **inst['params']}
        taps = observed_taps(edges_seen, case, p['vth'])
        ph0 = [t for t, j in taps if j == 0]
        tall = [t for t, _ in taps]
        ev = input_events(case, p['vth'])
        lat = [t for t, k, _ in ev if k == 'latch']
        rst = [t for t, k, _ in ev if k.startswith('rst')]
        en_pts, prev = [], case['en'][0][1]
        for t, v in case['en'][1:]:
            if v != prev:
                en_pts.append(ramp_cross(t, prev * case['vin'], v * case['vin'], p['vth']))
                prev = v

        def dmin(xs, ys):
            return min((abs(a - b) for a in xs for b in ys), default=float('inf'))
        exp, _ = expected(case, inst['params'], taps)
        ovr = exp['overrun']
        ovr_hi = [(ovr[i][0], ovr[i + 1][0]) for i in range(0, len(ovr), 2)]
        rst_on = [t for t, k, _ in ev if k == 'rst_on']
        spacing = min((b - a for a, b in zip(lat, lat[1:])), default=float('inf'))
        out[inst['name']] = dict(
            enc_valid_to_ph0_ps=dmin(lat, ph0) * 1e12, en_to_ph0_ps=dmin(en_pts, ph0) * 1e12,
            rst_to_tap_ps=dmin(rst, tall) * 1e12, rst_to_enc_valid_ps=dmin(rst, lat) * 1e12,
            enc_valid_spacing_minus_t_ovr_ps=(spacing - p['t_ovr']) * 1e12,
            rst_rise_during_overrun=any(a <= t <= b for t in rst_on for a, b in ovr_hi))
    return out
