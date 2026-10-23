"""Public contract for the 8-branch RO scheduler: lane stimuli, expected edges, checks.

The lane signals come from an independent model of the pulse generator on an
ideal delta0 grid (S9). Expected outputs are replayed from the Spec rules and
the stimulus; the checker never reads a reference model's waveform.
"""
from __future__ import annotations

import random

import uwbtask as u

EDGE = 2e-12            # stimulus edge (linear, centred on the stated time)
TOL = 2e-12             # crossing-time tolerance (S10)
MARGIN = 10e-12         # distance kept between a timed state change and other events (S9)
MAXSTEP = 10e-12        # simulator step limit
DELTA0 = 1 / (32 * 336e6)
DEFAULTS = dict(n_pre=2, delta0=DELTA0, t_tail=150e-12, t_hold=200e-12, t_conf=200e-12,
                vdd=1.0, vth=0.5, tr=2e-12)
RANGES = dict(n_pre=(1, 15), delta0=(60e-12, 150e-12), t_tail=(20e-12, 600e-12), t_hold=(0.0, 3e-9),
              t_conf=(50e-12, 800e-12), vdd=(0.5, 1.8), vth=(0.2, 1.5), tr=(1e-12, 5e-12))
OFF, PRECHARGE, ACTIVE, TAIL, HOLD = 0, 1, 3, 4, 5
ST_V = 0.2                      # st volts per state number (S2)
# st and nsup thresholds lie 0.1 V on either side of every level (S10), so
# the crossing counts hold each level to +-0.1 V; levels 0, 0.2, 0.6, 0.8,
# 1.0 V for st and 0, 1, 2 V for nsup
ST_TH = (0.1, 0.3, 0.5, 0.7, 0.9, 1.1)
NSUP_TH = (0.5, 0.9, 1.1, 1.5, 1.9, 2.1)
PATHS = ['cold', 'warm_precharge', 'warm_active', 'warm_tail', 'warm_hold_waiting', 'warm_idle_hold',
         'take_over', 'drop', 'release', 'hand_over', 'tail_to_active', 'hold_to_active',
         'hold_waiting', 'idle_hold_off', 'tail_to_off', 'reset_off', 'reset_cancel', 'ignored_in_reset']


def gray_to_bin(g):
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def codewords(words):
    """Upstream encoder rule: 6-bit Gray words -> absolute (P, F), P[-1] = 0."""
    out, pos = [], 0
    for w in words:
        pos = (pos + gray_to_bin(w >> 3)) % 8
        out.append((pos, gray_to_bin(w & 7)))
    return out


def ramp_cross(t_mid, v0, v1, vth):
    """Crossing time of a linear EDGE-long ramp centred on t_mid."""
    return t_mid - EDGE / 2 + (vth - v0) / (v1 - v0) * EDGE


# ---------------------------------------------------------------- lanes ---

def windows(case):
    """Pulse-generator model on an ideal grid (S9).

    frames[i] is the descriptor (P, F) scheduled at the start of frame i into
    frame i + 1, or None for an empty frame. Its window starts at frame i + 1
    start + P*delta0 and lasts 9*delta0; its precharge (request) starts
    n_pre*delta0 earlier. Scheduled symbols alternate between lane a and b;
    sel_x changes delta0/2 after the scheduling frame starts.
    """
    d0, n_pre, t0 = case['delta0'], case['n_pre'], case['t0']
    out, lane = [], 0
    for i, sym in enumerate(case['frames']):
        if sym is None:
            continue
        pos, f = sym
        s = 16 * (i + 1) + pos
        out.append(dict(n=len(out), lane=lane, P=pos, F=f, frame=i + 1, sel=t0 + (16 * i + 0.5) * d0,
                        p=t0 + (s - n_pre) * d0, s=t0 + s * d0, e=t0 + (s + 9) * d0))
        lane = 1 - lane
    return out


def stimulus(case):
    vin, lines = case['vin'], []
    wins = windows(case)
    for ln, x in ((0, 'a'), (1, 'b')):
        mine = [w for w in wins if w['lane'] == ln]
        pre = [(0.0, 0)] + [c for w in mine for c in ((w['p'], 1), (w['s'], 0))]
        rf = [(0.0, 0)] + [c for w in mine for c in ((w['s'], 1), (w['e'], 0))]
        lines.append(f'Vpre_{x} (pre_{x} 0) vsource type=pwl wave={u.pwl_levels(pre, EDGE, vin)}')
        lines.append(f'Vrf_{x} (rf_{x} 0) vsource type=pwl wave={u.pwl_levels(rf, EDGE, vin)}')
        for b in range(3):
            ch, prev = [(0.0, 0)], 0
            for w in mine:
                bit = (w['F'] >> b) & 1
                if bit != prev:
                    ch.append((w['sel'], bit))
                    prev = bit
            lines.append(f'Vsel_{x}{b} (sel_{x}{b} 0) vsource type=pwl wave={u.pwl_levels(ch, EDGE, vin)}')
    rs = [(0.0, 1 if case['rst'] and case['rst'][0][0] == 0.0 else 0)]
    for on, off in case['rst']:
        if on > 0:
            rs.append((on, 1))
        rs.append((off, 0))
    lines.append(f'Vrst (rst 0) vsource type=pwl wave={u.pwl_levels(rs, EDGE, vin)}')
    return '\n'.join(lines)


# -------------------------------------------------------------- netlist ---

def params(case, inst):
    assert 'n_pre' not in inst['params'] and 'delta0' not in inst['params'], 'grid is per case'
    return {**DEFAULTS, 'n_pre': case['n_pre'], 'delta0': case['delta0'], **inst['params']}


def given(case, inst):
    """Parameters written on the instance line (nondefault grid plus the instance's own)."""
    g = {k: case[k] for k in ('n_pre', 'delta0') if case[k] != DEFAULTS[k]}
    return {**g, **inst['params']}


def ids(k):
    base = 1000 * (k + 1)
    return dict(pwr=[base + i for i in range(8)], pre=[base + 10 + i for i in range(8)],
                rel=[base + 20 + i for i in range(8)], gate=[base + 30, base + 31], conflict=base + 32,
                nsup=[base + 40 + j for j in range(len(NSUP_TH))],
                st=[[base + 100 + 10 * j + i for i in range(8)] for j in range(len(ST_TH))])


def netlist(case, candidate, tb_dir, stop):
    lines = ['simulator lang=spectre', 'global 0',
             f'ahdl_include "{candidate}"',
             f'ahdl_include "{tb_dir / "edge_monitor.va"}"', stimulus(case)]
    for k, inst in enumerate(case['instances']):
        n, p, m = inst['name'], params(case, inst), ids(k)
        pins = (['pre_a', 'rf_a', 'sel_a2', 'sel_a1', 'sel_a0', 'pre_b', 'rf_b', 'sel_b2', 'sel_b1', 'sel_b0', 'rst']
                + [f'pw{n}{i}' for i in range(7, -1, -1)] + [f'pc{n}{i}' for i in range(7, -1, -1)]
                + [f'rl{n}{i}' for i in range(7, -1, -1)] + [f'ga{n}', f'gb{n}', f'cf{n}', f'ns{n}']
                + [f'st{n}{i}' for i in range(7, -1, -1)])
        par = ' '.join(f'{key}={val!r}' for key, val in given(case, inst).items())
        lines.append(f'X{n} ({" ".join(pins)}) ro_scheduler8 {par}'.rstrip())
        half = p['vdd'] / 2
        mons = ([(f'pw{n}{i}', m['pwr'][i], half) for i in range(8)]
                + [(f'pc{n}{i}', m['pre'][i], half) for i in range(8)]
                + [(f'rl{n}{i}', m['rel'][i], half) for i in range(8)]
                + [(f'ga{n}', m['gate'][0], half), (f'gb{n}', m['gate'][1], half), (f'cf{n}', m['conflict'], half)]
                + [(f'ns{n}', m['nsup'][j], th) for j, th in enumerate(NSUP_TH)]
                + [(f'st{n}{i}', m['st'][j][i], th) for j, th in enumerate(ST_TH) for i in range(8)])
        lines += [f'Xmon_{node}_{ident} ({node}) uwb_edge_monitor id={ident} vth={th!r}' for node, ident, th in mons]
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={stop!r} maxstep={u.fmt_ps(MAXSTEP)}', 'save rst']
    return '\n'.join(lines) + '\n'


def stop_time(case):
    last = max([w['e'] for w in windows(case)] + [off for _, off in case['rst']])
    longest = max(params(case, i)['t_tail'] + params(case, i)['t_hold'] for i in case['instances'])
    return last + longest + 1e-9


# ------------------------------------------------------------- expected ---

def replay(case, p):
    """Spec rules S1-S7 for one instance driven by the case's lanes.

    Returns per-branch state changes [(t, state)], gate windows per lane,
    conflict pulses, path counts and the stimulus issues that would leave the
    operating domain of S9.
    """
    vin, vth = case['vin'], p['vth']
    t_wait = max(0.0, p['t_hold'] - p['n_pre'] * p['delta0'])
    events = []
    for w in windows(case):
        events += [(ramp_cross(w['p'], 0, vin, vth), 2, 'req', w),
                   (ramp_cross(w['s'], 0, vin, vth), 0, 'start', w),
                   (ramp_cross(w['e'], vin, 0, vth), 1, 'end', w)]
    in_reset = bool(case['rst']) and case['rst'][0][0] == 0.0
    for on, off in case['rst']:
        if on > 0:
            events.append((ramp_cross(on, 0, vin, vth), 3, 'rst_on', None))
        events.append((ramp_cross(off, vin, 0, vth), 3, 'rst_off', None))
    # a window start sorts before a window end less than 1 ps later: touching
    # windows on one branch hand over without a TAIL (S4)
    events.sort(key=lambda x: (x[0] - (1e-12 if x[2] == 'start' else 0.0), x[1]))
    br = [dict(st=OFF, wait=0, nopen=0, due=None) for _ in range(8)]
    hist = {k: [] for k in range(8)}
    grant, gate_on, gates = [None, None], [None, None], [[], []]
    conflicts, fired, issues = [], [], []
    stats = dict.fromkeys(PATHS, 0)

    def set_state(k, st, t):
        h = hist[k]
        while h and abs(h[-1][0] - t) < 1e-16:      # same instant: only the final state shows
            h.pop()
        if st != (h[-1][1] if h else OFF):
            h.append((t, st))
        br[k]['st'] = st

    def deadline(k):
        b = br[k]
        return b['due'] if b['st'] == TAIL or (b['st'] == HOLD and b['wait'] == 0) else None

    def advance(t):
        """Timed changes strictly before t, in time order (S5)."""
        while True:
            due = [(deadline(k), k) for k in range(8) if deadline(k) is not None]
            if not due or min(due)[0] >= t:
                return
            td, k = min(due)
            b = br[k]
            fired.append(td)
            if b['st'] == TAIL:
                set_state(k, HOLD, td)
                if b['wait'] > 0:
                    b['due'] = None
                    stats['hold_waiting'] += 1
                elif t_wait <= 0:
                    set_state(k, OFF, td)
                    b['due'] = None
                    stats['tail_to_off'] += 1
                else:
                    b['due'] = td + t_wait
            else:
                set_state(k, OFF, td)
                b['due'] = None
                stats['idle_hold_off'] += 1

    def cold(k, x, t):
        set_state(k, PRECHARGE, t)
        br[k].update(wait=1, nopen=0, due=None)
        grant[x] = k

    for t, _, kind, w in events:
        advance(t)
        for k in range(8):
            d = deadline(k)
            if d is not None and abs(d - t) < MARGIN:
                issues.append(f'{kind} at {t * 1e9:.4f} ns within {MARGIN * 1e12:g} ps of a timed change of branch {k}')
        if kind == 'rst_on':
            in_reset = True
            if conflicts and conflicts[-1][1] > t:
                issues.append(f'reset at {t * 1e9:.4f} ns during a conflict pulse')
            for k in range(8):
                if br[k]['st'] != OFF:
                    set_state(k, OFF, t)
                    stats['reset_off'] += 1
                br[k].update(wait=0, nopen=0, due=None)
            for x in (0, 1):
                if gate_on[x] is not None:
                    gates[x].append((gate_on[x], t))
                    gate_on[x] = None
                if grant[x] is not None:
                    stats['reset_cancel'] += 1
                grant[x] = None
        elif kind == 'rst_off':
            in_reset = False
        elif kind == 'req':
            x = w['lane']
            grant[x] = None
            if in_reset:
                stats['ignored_in_reset'] += 1
                continue
            k = w['F']
            b = br[k]
            powered = [j for j in range(8) if br[j]['st'] != OFF]
            if b['st'] != OFF:                                   # S3 (a) warm
                name = {PRECHARGE: 'warm_precharge', ACTIVE: 'warm_active', TAIL: 'warm_tail',
                        HOLD: 'warm_hold_waiting' if b['wait'] else 'warm_idle_hold'}[b['st']]
                stats[name] += 1
                b['wait'] += 1
                if b['st'] == HOLD:
                    b['due'] = None
                grant[x] = k
            elif len(powered) < 2:                               # S3 (b) cold
                stats['cold'] += 1
                cold(k, x, t)
            else:
                idle = [j for j in powered if br[j]['st'] == HOLD and br[j]['wait'] == 0]
                if len(idle) > 1:
                    issues.append(f'request at {t * 1e9:.4f} ns finds two idle HOLD branches')
                if idle:                                         # S3 (c) take-over
                    stats['take_over'] += 1
                    set_state(idle[0], OFF, t)
                    br[idle[0]]['due'] = None
                    cold(k, x, t)
                else:                                            # S3 (d) drop, S6
                    stats['drop'] += 1
                    if conflicts and conflicts[-1][1] > t:
                        conflicts[-1] = (conflicts[-1][0], t + p['t_conf'])
                    else:
                        conflicts.append((t, t + p['t_conf']))
        elif kind == 'start':
            x = w['lane']
            k = grant[x]
            if k is None:
                continue
            b = br[k]
            assert b['st'] != OFF, 'a granted branch cannot be off'
            stats[{PRECHARGE: 'release', ACTIVE: 'hand_over', TAIL: 'tail_to_active',
                   HOLD: 'hold_to_active'}[b['st']]] += 1
            b['wait'] -= 1
            b['nopen'] += 1
            b['due'] = None
            set_state(k, ACTIVE, t)
            gate_on[x] = t
        else:                                                    # window end
            x = w['lane']
            if gate_on[x] is not None:
                gates[x].append((gate_on[x], t))
                gate_on[x] = None
                b = br[grant[x]]
                b['nopen'] -= 1
                if b['nopen'] == 0:
                    set_state(grant[x], TAIL, t)
                    b['due'] = t + p['t_tail']
            grant[x] = None
    advance(float('inf'))
    times = [e[0] for e in events] + fired
    for td in fired:
        if sum(1 for t in times if abs(t - td) < MARGIN) > 1:
            issues.append(f'timed change at {td * 1e9:.4f} ns within {MARGIN * 1e12:g} ps of another event')
    lane_t = [e[0] for e in events if e[2] in ('req', 'start', 'end')]
    for e in events:
        if e[2] in ('rst_on', 'rst_off') and any(abs(e[0] - t) < MARGIN for t in lane_t):
            issues.append(f'rst crossing at {e[0] * 1e9:.4f} ns within {MARGIN * 1e12:g} ps of a lane edge')
    req_t = [e[0] for e in events if e[2] == 'req']
    for _, off in conflicts:
        if any(abs(off - t) < MARGIN for t in req_t):
            issues.append(f'request within {MARGIN * 1e12:g} ps of the end of a conflict pulse at {off * 1e9:.4f} ns')
    return dict(hist=hist, gates=gates, conflicts=conflicts, stats=stats, issues=issues)


def nsup_levels(hist):
    """Number of powered branches after all changes at each instant."""
    changes = sorted((t, k, st) for k in range(8) for t, st in hist[k])
    state, out, level, i = [OFF] * 8, [], 0, 0
    while i < len(changes):
        t = changes[i][0]
        while i < len(changes) and changes[i][0] - t < 1e-16:
            state[changes[i][1]] = changes[i][2]
            i += 1
        n = sum(1 for s in state if s != OFF)
        if n != level:
            out.append((t, n))
            level = n
    return out


def crossings(levels, ths, tr, v0=0.0):
    """Expected crossings of each threshold in ths by an output whose changes
    [(t, v)] are linear edges of length tr (S8): {th: [(time, dir, timed)]}.

    Of the thresholds an edge passes, only the one nearest the middle of the
    edge (the earlier one on a tie) is timed (S10); the others are compared in
    count and direction.
    """
    out, prev = {th: [] for th in ths}, v0
    for t, v in levels:
        hit = [((th - prev) / (v - prev), th) for th in ths if min(prev, v) < th < max(prev, v)]
        if hit:
            timed = min(hit, key=lambda x: (abs(x[0] - 0.5), x[0]))[1]
            for frac, th in hit:
                out[th].append((t + frac * tr, 1 if v > prev else 0, th == timed))
        prev = v
    return out


def logic(hist_k, pred):
    out, level = [], 0
    for t, st in hist_k:
        new = 1 if pred(st) else 0
        if new != level:
            out.append((t, new))
            level = new
    return out


def pulses(intervals):
    return [c for a, b in intervals for c in ((a, 1), (b, 0))]


def validate(case):
    """Author check: the case stays inside the operating domain of S9."""
    wins = windows(case)
    for ln in (0, 1):
        mine = [w for w in wins if w['lane'] == ln]
        assert all(b['p'] > a['e'] for a, b in zip(mine, mine[1:])), 'lane request before its previous window ends'
    assert 1 <= case['n_pre'] <= 15
    for inst in case['instances']:
        p = params(case, inst)
        for key, (lo, hi) in RANGES.items():
            assert lo <= p[key] <= hi, f'{case["name"]}/{inst["name"]}: {key} out of range'
        assert p['vth'] + 0.3 <= case['vin'] <= 1.8, 'VIN outside S9'
        slack = p['t_hold'] - p['n_pre'] * p['delta0']
        assert slack <= 0 or slack >= MARGIN, 'idle HOLD shorter than 10 ps'
        r = replay(case, p)
        assert not r['issues'], f'{case["name"]}/{inst["name"]}: ' + '; '.join(r['issues'][:3])
    return case


# ---------------------------------------------------------------- cases ---

def public_cases():
    # hold: same-F pairs with P a -> 0 for a = 7 (windows touch), 6, 4 (kept),
    # 3 and 2 (off, cold restart), separated by other branches
    hold = dict(name='hold', vin=1.0, n_pre=2, delta0=DELTA0, t0=0.5e-9, rst=[(0.0, 0.3e-9)],
                instances=[dict(name='a', params={})],
                frames=[(1, 6), (7, 3), (0, 3), (3, 5), (6, 1), (0, 1), (5, 4), (4, 2), (0, 2), (6, 7),
                        (3, 0), (0, 0), (5, 6), (2, 5), (0, 5), (1, 3)])
    # conflict: n_pre = 15 puts three branches' supply intervals over each
    # other; P = 7, x, 0 on three branches drops the third request, on lane b
    # and later on lane a
    conflict = dict(name='conflict', vin=1.0, n_pre=15, delta0=DELTA0, t0=0.5e-9, rst=[],
                    instances=[dict(name='a', params={})],
                    frames=[(2, 0), (7, 1), (3, 2), (0, 3), (5, 4), (2, 5), (7, 6), (4, 7), (0, 0), (3, 1),
                            (6, 2), (1, 3)])
    return [validate(hold), validate(conflict)]


# -------------------------------------------------------------- checks ---

def compare(rep, spec, pairs):
    """One row for several monitored crossings: counts and directions one to
    one, and the time of every timed crossing within TOL (S10)."""
    n_got = n_exp = n_timed = 0
    worst, first, ok = 0.0, None, True
    for label, got, exp in pairs:
        n_got += len(got)
        n_exp += len(exp)
        if len(got) != len(exp):
            ok = False
            first = first or f'{label}: {len(got)} crossings, expected {len(exp)}'
        for (tg, dg), (te, de, timed) in zip(got, exp):
            if dg != de:
                ok = False
                first = first or f'{label}: wrong direction near {te * 1e9:.4f} ns'
                break
            if not timed:
                continue
            n_timed += 1
            worst = max(worst, abs(tg - te))
            if abs(tg - te) > TOL:
                ok = False
                first = first or f'{label}: {tg * 1e9:.4f} ns, expected {te * 1e9:.4f} ns'
    value = f'{n_got} crossings, worst timed error {worst * 1e12:.3f} ps' + (f'; first mismatch {first}' if first else '')
    limit = f'{n_exp} crossings, same directions, {n_timed} timed with |error| <= {TOL * 1e12:g} ps'
    return rep.add(spec, limit, value, ok)


def check(case, seen: u.Edges):
    reps = []
    for k, inst in enumerate(case['instances']):
        p, m = params(case, inst), ids(k)
        rep = u.Report(f"{case['name']}/{inst['name']}")
        r = replay(case, p)
        tr = p['tr']
        got = lambda ident: seen.by_id.get(ident, [])  # noqa: E731
        for b in range(8):
            h = r['hist'][b]
            exp = [('pwr', logic(h, lambda s: s != OFF)), ('pre', logic(h, lambda s: s == PRECHARGE)),
                   ('rel', logic(h, lambda s: s in (ACTIVE, TAIL, HOLD)))]
            compare(rep, f'branch {b}: pwr, pre, rel edges (S2-S5, S7)',
                    [(f'{nm}[{b}]', got(m[nm][b]), crossings(lv, [0.5], tr)[0.5]) for nm, lv in exp])
        for b in range(8):
            cr = crossings([(t, ST_V * s) for t, s in r['hist'][b]], ST_TH, tr)
            compare(rep, f'branch {b}: st = 0.2 V x state number (S2, S5)',
                    [(f'st[{b}] at {th:g} V', got(m['st'][j][b]), cr[th]) for j, th in enumerate(ST_TH)])
        for x, nm in ((0, 'a'), (1, 'b')):
            compare(rep, f'gate_{nm}: high for granted rf_{nm} windows only (S4, S7)',
                    [(f'gate_{nm}', got(m['gate'][x]), crossings(pulses(r['gates'][x]), [0.5], tr)[0.5])])
        compare(rep, 'conflict: t_conf pulse at each dropped request (S3, S6)',
                [('conflict', got(m['conflict']), crossings(pulses(r['conflicts']), [0.5], tr)[0.5])])
        cr = crossings([(t, 1.0 * n) for t, n in nsup_levels(r['hist'])], NSUP_TH, tr)
        compare(rep, 'nsup = 1 V per powered branch (S2)',
                [(f'nsup at {th:g} V', got(m['nsup'][j]), cr[th]) for j, th in enumerate(NSUP_TH)])
        pw = sorted((t, d) for b in range(8) for t, d in got(m['pwr'][b]))
        n, most = 0, 0
        for _, d in pw:
            n += 1 if d else -1
            most = max(most, n)
        rep.add('at most two branches powered, from the observed pwr edges (S3)', '<= 2', f'max {most}', most <= 2)
        rep.add('scheduler paths in this case (replay of S3-S7; informational)', 'informational',
                ', '.join(f'{key}={v}' for key, v in r['stats'].items() if v), True)
        reps.append(rep)
    return reps


def random_frames(seed, n, branches=range(8), p_idle=0.0, words=False):
    """Random descriptors; with words=True they come from random 6-bit words through the encoder rule."""
    rnd = random.Random(seed)
    if words:
        cws = codewords([rnd.randrange(64) for _ in range(n)])
        return [None if rnd.random() < p_idle else c for c in cws]
    return [None if rnd.random() < p_idle else (rnd.randrange(8), rnd.choice(list(branches))) for _ in range(n)]
