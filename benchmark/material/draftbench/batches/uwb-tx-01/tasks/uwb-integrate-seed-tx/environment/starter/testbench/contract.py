"""Public contract for the seed-transmitter integration: stimuli, expected
behavior and checks (instruction S1-S7).

Only the top-level pins are observed: outp, outn, done, fail, conflict, nsup,
clk672, and the testbench's own ref and bclk. The checker replays the Spec
rules from the stimulus and from the observed clk672 crossings; it never reads
a reference model's waveform. All crossings come from the saved waveforms by
linear interpolation between simulator time points.
"""
from __future__ import annotations

import bisect
import math
import random

import uwbtask as u

# ------------------------------------------------------------- constants ---
EDGE = 2e-12                 # stimulus edges; library output edges (tr)
T_REF = 1 / 48e6
F_BASE, F_STEP = 600e6, 0.25e6
RATIO, N_SETTLE, TOL_COUNT, N_LOST = 14, 2, 1, 64
T_CQ = 10e-12                # calibration output delay
T_CODE = 5e-12               # RO code read delay
T_LATCH = 42e-12             # bclk edge of bit 3 of the next word -> enc_valid crossing
DELTA0 = 93.00595238095238e-12   # scheduler's nominal tap spacing
T_TAIL, T_HOLD, T_CONF = 150e-12, 200e-12, 200e-12
N_WIDTH = 9
TAU_E = 50e-12 / math.log(100)   # envelope response
TAU_A = TAU_F = 200e-12 / math.log(100)   # branch amplitude / frequency settling
DF_START = 0.01
CARRIERS = [4.5e9 + k * 3e9 / 7 for k in range(8)]
DEFAULTS = dict(n_pre=2, n_win=192, code_init=512, g_pa=1.0, vcm=0.5,
                **{f'f{k}': CARRIERS[k] for k in range(8)})

# acceptance limits (S7)
TOL_FREQ = 0.1e6             # clk672 frequency, Hz
TOL_FLAG = 5e-12             # done, fail, conflict, nsup crossing times
TOL_START = 10e-12           # pulse start
TOL_CARRIER = 0.02           # relative carrier frequency
MIN_CORR = 0.9               # correlation with the expected carrier
AMP_LO, AMP_HI = 0.85, 1.01  # pulse peak / g_pa
V_QUIET = 1e-3               # |outp - outn| outside pulses
V_CM = 1e-6                  # |outp + outn - 2 vcm|
NSUP_MAX = 2.0 + 1e-6
MARGIN = 3e-12               # stimulus validity: event separations the replay relies on
MAXSTEP = 10e-12
THR_PULSE = 0.2             # pulse detection threshold / g_pa


def gray(b):
    return b ^ (b >> 1)


def gray_to_bin(g):
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def symbols_for_codewords(cws):
    """Input symbols that make the encoder emit the absolute codewords (P, F)."""
    out, p_prev = [], 0
    for p, f in cws:
        out.append((gray((p - p_prev) % 8) << 3) | gray(f))
        p_prev = p
    return out


def codewords(symbols):
    out, p = [], 0
    for s in symbols:
        p = (p + gray_to_bin(s >> 3)) % 8
        out.append((p, gray_to_bin(s & 7)))
    return out


def f_code(code):
    return F_BASE + F_STEP * code


# ----------------------------------------------------------------- cases ---

def ref_edges(case, t_end):
    """Reference crossings: the clock source crosses vdd/2 tr/2 after each scheduled edge."""
    out, k = [], 0
    while True:
        t = case['ref_delay'] + k * T_REF
        if t >= min(case.get('ref_stop') or 1.0, t_end):
            return out
        out.append(t + EDGE / 2)
        k += 1


def predict_done(case):
    """Time of the done crossing for an uninterrupted reference (case design only)."""
    ref = [t for t in ref_edges(case, 1e-3) if t > case['t_cal']]
    n_win = {**DEFAULTS, **case['params']}['n_win']
    return ref[11 * (N_SETTLE + n_win) - 1] + T_CQ + EDGE / 2


T_RO = 1 / 672e6             # nominal frame, case design only


def make_case(name, params, symbols, *, pol=0, ref_delay=0.37e-9, t_cal=40e-9, t_start=None,
              data_after_done=20e-9, ref_stop=None, rst=(), stop=None):
    case = dict(name=name, params=params, symbols=list(symbols), pol=pol, ref_delay=ref_delay,
                ref_stop=ref_stop, t_rst0=10e-9, t_cal=t_cal, rst=list(rst))
    if t_start is None:
        t_start = predict_done(case) + data_after_done
    case['t_start'] = t_start
    case['stop'] = stop or t_start + (len(symbols) + 6) * 1.05 * T_RO + 1e-9
    return case


def public_cases():
    rnd = random.Random(20261023)
    decode = make_case('decode', dict(n_win=2), [rnd.randrange(64) for _ in range(48)])
    # n_pre = 15: P = 7, x, 0 on three different carriers -> the third request
    # finds both supplies busy and is dropped (instruction S5). Data starts
    # before done, so the words before done are overwritten (S4).
    rnd = random.Random(15)
    prefix = [(rnd.randrange(8), rnd.randrange(8)) for _ in range(18)]
    conflict = [(2, 0), (7, 1), (3, 2), (0, 3), (5, 4), (2, 5), (7, 6), (4, 7), (0, 0), (3, 1),
                (6, 2), (1, 3), (7, 4), (2, 5), (0, 6), (4, 7)]
    case = dict(ref_delay=0.37e-9, t_cal=40e-9, params=dict(n_win=1))
    t_done = predict_done(case)
    early = make_case('early_conflict', dict(n_pre=15, n_win=1), symbols_for_codewords(prefix + conflict),
                      pol=1, t_start=t_done - 12 * T_RO)
    return [decode, early]


# --------------------------------------------------------------- netlist ---

def stimulus(case):
    lines = []
    extra = f' t_stop={case["ref_stop"]!r}' if case.get('ref_stop') else ''
    lines.append(f'Xref (ref) uwb_clock_source period={T_REF!r} delay={case["ref_delay"]!r} tr={EDGE!r}{extra}')
    rs = [(0.0, 1), (case['t_rst0'], 0)]
    for on, off in case['rst']:
        rs += [(on, 1), (off, 0)]
    lines.append(f'Vrst (rst 0) vsource type=pwl wave={u.pwl_levels(rs, EDGE)}')
    cal = [(0.0, 0), (case['t_cal'], 1), (case['t_cal'] + 2e-9, 0)]
    lines.append(f'Vcal (cal 0) vsource type=pwl wave={u.pwl_levels(cal, EDGE)}')
    lines.append(f'Vpol (pol 0) vsource dc={case["pol"]}')
    syms = ' '.join(f's{i}={s}' for i, s in enumerate(case['symbols']))
    lines.append(f'Xsrc (clk672 bclk din) uwb_bit_source t_start={case["t_start"]!r} '
                 f'n_sym={len(case["symbols"])} {syms}')
    return '\n'.join(lines)


def netlist(case, candidate, tb_dir, stop):
    params = ' '.join(f'{k}={v!r}' for k, v in case['params'].items())
    lines = ['simulator lang=spectre', 'global 0',
             f'ahdl_include "{candidate}"',
             f'ahdl_include "{tb_dir / "clock_source.va"}"',
             f'ahdl_include "{tb_dir / "bit_source.va"}"',
             stimulus(case),
             f'Xtx (bclk din rst ref cal pol outp outn done fail conflict nsup clk672) uwb_tx_seed {params}'.rstrip(),
             'opts options reltol=1e-6 vabstol=1e-6',
             f'tran tran stop={stop!r} maxstep={MAXSTEP!r}',
             'save outp outn nsup clk672 bclk done fail conflict']
    return '\n'.join(lines) + '\n'


def stop_time(case):
    return case['stop']


# ------------------------------------------------------------ waveforms ---

def crossings(t, v, vth, t_min=5e-12):
    """Threshold crossings (time, 1 rising / 0 falling) by linear interpolation."""
    out = []
    for i in range(1, len(v)):
        a, b = v[i - 1] - vth, v[i] - vth
        if (a < 0 <= b) or (a >= 0 > b):
            tc = t[i - 1] + (t[i] - t[i - 1]) * (-a) / (b - a)
            if tc > t_min:
                out.append((tc, 1 if b > a else 0))
    return out


def rising(xs):
    return [t for t, d in xs if d == 1]


# ----------------------------------------------------- calibration (S3) ---

def replay_cal(ref, ro, n_win, t_cal):
    """Replay the successive-approximation search from the reference and
    clk672 rising crossings after cal_start (port of test/m2_clock/check_m2.py).
    Returns the shown codes [(t, code)], the outcome and its time, and the
    windows with a clk672 edge within MARGIN of a boundary."""
    ref = [t for t in ref if t > t_cal]
    ro = [t for t in ro if t > t_cal]
    target = n_win * RATIO
    codes = [(t_cal + T_CQ, 512)]
    code_q, weight, trial = 0, 512, 512
    i, verify, ambiguous = 0, False, []
    while True:
        if i + N_SETTLE + n_win - 1 >= len(ref):
            last_ref = ref[-1] if ref else t_cal
            after = [t for t in ro if t > last_ref]
            if len(after) > N_LOST:          # lost reference: fail, show the kept code
                t_fail = after[N_LOST] + T_CQ
                if trial != code_q:
                    codes.append((t_fail, code_q))
                return dict(codes=codes, outcome='fail', t_flag=t_fail, code=code_q, ambiguous=ambiguous)
            return dict(codes=codes, outcome=None, t_flag=None, code=trial, ambiguous=ambiguous)
        w0 = ref[i + N_SETTLE - 1]
        w1 = ref[i + N_SETTLE - 1 + n_win]
        cnt = sum(1 for t in ro if w0 < t < w1)
        if any(abs(t - w0) < MARGIN or abs(t - w1) < MARGIN for t in ro):
            ambiguous.append(w1)
        i += N_SETTLE + n_win
        if not verify:
            if cnt <= target:
                code_q = trial
            weight //= 2
            if weight >= 1:
                trial = code_q + weight
            else:
                trial = code_q
                verify = True
            codes.append((w1 + T_CQ, trial))
        else:
            ok = abs(cnt - target) <= TOL_COUNT
            return dict(codes=codes, outcome='done' if ok else 'fail', t_flag=w1 + T_CQ, code=code_q,
                        ambiguous=ambiguous)


def freq_between(ro, a, b):
    """Mean clk672 frequency from the rising crossings inside (a, b]."""
    i, j = bisect.bisect_right(ro, a), bisect.bisect_right(ro, b)
    e = ro[i:j]
    if len(e) < 3:
        return None, len(e)
    return (len(e) - 1) / (e[-1] - e[0]), len(e)


# ---------------------------------------------------- transmission (S4) ---

def tap_time(E, idx):
    m, j = divmod(idx, 16)
    if m + 1 >= len(E):
        return math.inf
    return E[m] + j * (E[m + 1] - E[m]) / 16


def pg_replay(case, E, bclk, flag_on, t_rst):
    """Lane windows of the pulse generator (S4) from the frame edges E, the
    word latch times and the enable (done) intervals. Times are tap crossings."""
    p = {**DEFAULTS, **case['params']}
    cws = codewords(case['symbols'])
    n_words = len(case['symbols'])
    latches = [(bclk[6 * n + 8] + T_LATCH, n) for n in range(n_words) if 6 * n + 8 < len(bclk)]
    events = [(t, 1, 'latch', n) for t, n in latches] + [(t, 0, 'rst', None) for t in t_rst]
    events += [(t, 2, 'frame', m) for m, t in enumerate(E)]
    events.sort(key=lambda x: (x[0], x[1]))
    wins, pend, lane, near = [], None, 0, []
    in_rst = lambda t: any(on <= t < off for on, off in case['rst']) or t < case['t_rst0']  # noqa: E731
    for t, _, kind, n in events:
        if kind == 'rst':
            pend, lane = None, 0
            for w in wins:
                w['cut'] = t if w['cut'] is None or t < w['cut'] else w['cut']
        elif kind == 'latch':
            if not in_rst(t):
                pend = n
        else:
            m = n
            if any(abs(t - x) < MARGIN for x, _ in flag_on):
                near.append(t)
            en = any(a < t < b for a, b in flag_on)
            if en and not in_rst(t) and pend is not None:
                P, F = cws[pend]
                s = 16 * (m + 1) + P
                wins.append(dict(n=pend, P=P, F=F, pol=case['pol'], lane=lane, idx_s=s,
                                 p=tap_time(E, s - p['n_pre']), s=tap_time(E, s), e=tap_time(E, s + N_WIDTH),
                                 frame=m + 1, cut=None))
                lane, pend = 1 - lane, None
    for w in wins:                      # a reset clears windows not yet finished
        if w['cut'] is not None and w['cut'] < w['p']:
            w['cut'] = -1.0
    wins = [w for w in wins if w['cut'] is None or w['cut'] >= w['p']]
    return wins, latches, near


# ---------------------------------------------------------- supply (S5) ---

def scheduler_replay(wins, n_pre, t_rst):
    """Two-supply scheduler (S5), port of test/m4_chain/check_chain.py.
    Lane times are the pulse-generator crossings (tap + 1 ps)."""
    t_wait = max(0.0, T_HOLD - n_pre * DELTA0)
    ev = []
    for w in wins:
        for key, prio, kind in (('p', 1, 'req'), ('s', 2, 'start'), ('e', 0, 'end')):
            t = w[key] + EDGE / 2
            if w['cut'] is None or t < w['cut']:
                ev.append((t, prio, kind, w))
    ev += [(t, -1, 'rst', None) for t in t_rst]
    ev.sort(key=lambda x: (x[0], x[1]))
    slots = [dict(br=-1, st=0, pend=0, nact=0, due=None, tref=None) for _ in range(2)]
    lane_slot = {0: None, 1: None}
    count = [(0.0, 0)]
    drops, grants, near = [], [], []

    def note(t):
        n = sum(1 for s in slots if s['st'] != 0)
        if count[-1][0] == t:
            count[-1] = (t, n)
        elif count[-1][1] != n:
            count.append((t, n))
        if len(count) > 1 and count[-1][1] == count[-2][1]:
            count.pop()

    def advance(t):
        while True:
            due = [(sl['due'], i) for i, sl in enumerate(slots)
                   if sl['due'] is not None and (sl['st'] == 4 or (sl['st'] == 5 and sl['pend'] == 0))]
            if not due:
                return
            td, i = min(due)
            if td >= t - 1e-15:
                return
            sl = slots[i]
            if sl['st'] == 4:
                sl['st'] = 5
                if sl['pend'] == 0:
                    sl['due'] = td + t_wait
                    if t_wait <= 0:
                        sl.update(st=0, br=-1, due=None)
                else:
                    sl['due'] = None
            else:
                sl.update(st=0, br=-1, due=None)
            note(td)

    for t, _, kind, w in ev:
        advance(t)
        if kind == 'rst':
            for sl in slots:
                sl.update(br=-1, st=0, pend=0, nact=0, due=None, tref=None)
            lane_slot = {0: None, 1: None}
            note(t)
            continue
        ln = w['lane']
        if kind == 'req':
            for sl in slots:            # a request right at a supply deadline is ambiguous
                if sl['due'] is not None and abs(sl['due'] - t) < MARGIN:
                    near.append(t)
            k = w['F']
            hit = [i for i, sl in enumerate(slots) if sl['st'] != 0 and sl['br'] == k]
            free = [i for i, sl in enumerate(slots) if sl['st'] == 0]
            idle = [i for i, sl in enumerate(slots) if sl['st'] == 5 and sl['pend'] == 0]
            if hit:
                i = hit[0]
                slots[i]['pend'] += 1
                if slots[i]['st'] == 5:
                    slots[i]['due'] = None
                lane_slot[ln] = i
            elif free or idle:
                i = (free or idle)[0]
                slots[i].update(br=k, st=1, pend=1, nact=0, due=None, tref=None)
                lane_slot[ln] = i
            else:
                lane_slot[ln] = None
                drops.append(dict(w, t_req=t))
            note(t)
        elif kind == 'start':
            i = lane_slot[ln]
            if i is not None:
                sl = slots[i]
                cold = sl['st'] == 1
                if cold:
                    sl['tref'] = t + EDGE / 2       # release: rel crosses 1 ps after the lane edge
                sl.update(st=3, nact=sl['nact'] + 1, pend=max(0, sl['pend'] - 1), due=None)
                grants.append(dict(w, cold=cold, tref=sl['tref'], t_gate=t + EDGE / 2,
                                   whole=w['cut'] is None or w['cut'] > w['e'] + 300e-12))
            note(t)
        else:
            i = lane_slot[ln]
            if i is not None:
                sl = slots[i]
                sl['nact'] -= 1
                if sl['nact'] <= 0:
                    sl.update(nact=0, st=4, due=t + T_TAIL)
            lane_slot[ln] = None
            note(t)
    advance(math.inf)
    return grants, drops, count, near


def level_crossings(count, vth):
    """Crossings of vth by nsup (1 V per powered branch, 2 ps linear steps)."""
    out = []
    for (t0, a), (t1, b) in zip(count, count[1:]):
        if min(a, b) < vth < max(a, b):
            out.append((t1 + EDGE * (vth - a) / (b - a), 1 if b > a else 0))
    return out


def conflict_edges(drops):
    out, off = [], None
    for d in sorted(drops, key=lambda x: x['t_req']):
        t = d['t_req']
        if off is not None and t < off:
            off = t + T_CONF
            continue
        if off is not None:
            out.append((off + EDGE / 2, 0))
        out.append((t + EDGE / 2, 1))
        off = t + T_CONF
    if off is not None:
        out.append((off + EDGE / 2, 0))
    return out


# -------------------------------------------------------------- RF (S4) ---

def env_resp(x, tw, tau):
    """First-order response to a raised cosine of length tw started x ago."""
    if x <= 0:
        return 0.0
    w = 2 * math.pi / tw
    xe = min(x, tw)
    k = 1 / (1 + w * w * tau * tau)
    y = 0.5 * (1 - math.exp(-xe / tau)) - 0.5 * k * (math.cos(w * xe) + w * tau * math.sin(w * xe) - math.exp(-xe / tau))
    if x > tw:
        y *= math.exp(-(x - tw) / tau)
    return y


def rf_groups(t, v, thr, merge=180e-12):
    """Samples with |v| > thr, grouped. Inside a pulse whose envelope exceeds thr
    the carrier peaks give a sample above thr every half carrier period (< 143 ps
    for f >= 3.5 GHz); between two touching windows the envelope stays below
    0.2 of its peak for about 240 ps."""
    groups = []
    for ti, vi in zip(t, v):
        if abs(vi) > thr:
            if groups and ti - groups[-1][1] < merge:
                groups[-1][1] = ti
            else:
                groups.append([ti, ti])
    return groups


def period_before(E, t):
    i = bisect.bisect_right(E, t) - 1
    return E[i] - E[i - 1] if i >= 1 else None


def analyse_pulses(t, v, E, thr, fk):
    """Receiver-style measurement of every pulse in outp - outn."""
    groups = rf_groups(t, v, thr)
    out = []
    for g, (a, b) in enumerate(groups):
        lo = (groups[g - 1][1] + a) / 2 if g else a - 300e-12
        hi = (b + groups[g + 1][0]) / 2 if g + 1 < len(groups) else b + 300e-12
        i0, i1 = bisect.bisect_left(t, lo), bisect.bisect_right(t, hi)
        num = den = 0.0
        for i in range(max(i0, 1), i1):
            dt = t[i] - t[i - 1]
            e0, e1 = v[i - 1] ** 2, v[i] ** 2
            num += 0.5 * (t[i - 1] * e0 + t[i] * e1) * dt
            den += 0.5 * (e0 + e1) * dt
        tclk = period_before(E, a) or T_RO
        tw = N_WIDTH * tclk / 16
        start = num / den - tw / 2 - TAU_E if den > 0 else a
        peak = max(abs(v[i]) for i in range(i0, i1)) if i1 > i0 else 0.0
        zs, ze = start + 0.25 * tw, start + 0.75 * tw
        j0, j1 = bisect.bisect_left(t, zs), bisect.bisect_right(t, ze)
        zc = [t[i] + (t[i + 1] - t[i]) * v[i] / (v[i] - v[i + 1])
              for i in range(j0, min(j1, len(t) - 1)) if v[i] * v[i + 1] < 0]
        f_est = (len(zc) - 1) / 2 / (zc[-1] - zc[0]) if len(zc) >= 3 else 0.0
        F = min(range(8), key=lambda k: abs(fk[k] - f_est))
        m = bisect.bisect_right(E, start + tclk / 32) - 1
        if m >= 0 and m + 1 < len(E):
            d = (E[m + 1] - E[m]) / 16
            P = round((start - E[m]) / d)
        else:
            d, P = tclk / 16, None
        out.append(dict(a=a, b=b, start=start, peak=peak, f=f_est, F=F, P=P, frame=m, delta=d, tw=tw))
    return out


def correlation(t, v, g, fk):
    """Normalized correlation of outp - outn with the expected pulse shape."""
    f = fk[g['F']]
    tw = N_WIDTH * g['tclk'] / 16
    t0, t1 = g['t_gate'], g['t_gate'] + tw
    i0, i1 = bisect.bisect_left(t, t0), bisect.bisect_right(t, t1)
    svm = svv = smm = 0.0
    for i in range(max(i0, 1), i1):
        dt = t[i] - t[i - 1]
        x = t[i] - g['tref']
        amp = 1 - math.exp(-x / TAU_A)
        ph = 2 * math.pi * f * (x + DF_START * TAU_F * (1 - math.exp(-x / TAU_F)))
        m = env_resp(t[i] - t0, tw, TAU_E) * amp * math.cos(ph)
        svm += v[i] * m * dt
        svv += v[i] * v[i] * dt
        smm += m * m * dt
    return svm / math.sqrt(svv * smm) if svv > 0 and smm > 0 else 0.0


# ----------------------------------------------------------------- checks ---

def match_edges(rep, spec, got, want, tol):
    ok_dir = [d for _, d in got] == [d for _, d in want]
    return rep.times_match(spec, [x for x, _ in got] if ok_dir else [], [x for x, _ in want], tol)


def check(case, rows):
    p = {**DEFAULTS, **case['params']}
    rep = u.Report(case['name'])
    t = rows['time']
    v = [a - b for a, b in zip(rows['outp'], rows['outn'])]
    E = rising(crossings(t, rows['clk672'], 0.5))
    bclk = rising(crossings(t, rows['bclk'], 0.5))
    done_x = crossings(t, rows['done'], 0.5)
    fail_x = crossings(t, rows['fail'], 0.5)
    conf_x = crossings(t, rows['conflict'], 0.5)
    t_end = t[-1]
    t_rst = [on for on, _ in case['rst']]
    fk = [p[f'f{k}'] for k in range(8)]

    # ---- S3 calibration and clk672
    f0, n0 = freq_between(E, 2e-9, case['t_cal'] + T_CQ)
    want = f_code(p['code_init'])
    rep.add('clk672 before cal_start runs at 600 MHz + 0.25 MHz x code_init (S3)',
            f'{want / 1e6:.3f} MHz +- {TOL_FREQ / 1e6:g} MHz',
            f'{f0 / 1e6:.4f} MHz over {n0} edges' if f0 else f'{n0} edges', f0 is not None and abs(f0 - want) <= TOL_FREQ)
    ref = ref_edges(case, t_end)
    t_cal_end = min(t_rst) if t_rst else t_end
    cal = replay_cal([x for x in ref if x < t_cal_end], [x for x in E if x < t_cal_end], p['n_win'], case['t_cal'])
    rep.add('stimulus validity: no clk672 edge within 3 ps of a counting-window boundary',
            '0 windows', f"{len(cal['ambiguous'])} windows", not cal['ambiguous'])
    # codes shown over time, then reset to code_init
    shown = list(cal['codes'])
    for tr in t_rst:
        shown = [(x, c) for x, c in shown if x < tr] + [(tr + T_CQ, p['code_init'])]
    worst, bad, nint = 0.0, [], 0
    for (a, c), (b, _) in zip(shown, shown[1:] + [(t_end, None)]):
        f, n = freq_between(E, a + T_CODE + EDGE, b + T_CODE)
        if n < 3:
            continue
        nint += 1
        err = abs(f - f_code(c))
        worst = max(worst, err)
        if err > TOL_FREQ:
            bad.append((round(a * 1e9, 2), c, round(f / 1e6, 3)))
    rep.add('clk672 frequency follows every code of the replayed search, the final code and reset (S3)',
            f'{nint} intervals, |error| <= {TOL_FREQ / 1e6:g} MHz',
            f'worst {worst / 1e6:.4f} MHz; first wrong (ns, code, MHz) {bad[:2]}', nint > 0 and not bad)
    flag_on = []
    exp_done, exp_fail = [], []
    if cal['outcome'] is not None:
        tf = cal['t_flag'] + EDGE / 2
        off = [tr + T_CQ + EDGE / 2 for tr in t_rst if tr > tf]
        (exp_done if cal['outcome'] == 'done' else exp_fail).append((tf, 1))
        if off:
            (exp_done if cal['outcome'] == 'done' else exp_fail).append((off[0], 0))
        if cal['outcome'] == 'done':
            flag_on.append((tf, off[0] if off else math.inf))
    match_edges(rep, f"done edges: search outcome {cal['outcome']}, cleared by rst (S3)", done_x, exp_done, TOL_FLAG)
    match_edges(rep, 'fail edges (S3)', fail_x, exp_fail, TOL_FLAG)

    # ---- S4 transmission
    n_words = len(case['symbols'])
    rep.add('bit source sent every bit (needs a running clk672, S3/S6)', f'{6 * n_words + 3} bclk rising edges',
            f'{len(bclk)}', len(bclk) == 6 * n_words + 3)
    wins, latches, near_en = pg_replay(case, E, bclk, flag_on, t_rst)
    grants, drops, count, near_sch = scheduler_replay(wins, p['n_pre'], t_rst)
    rep.add('stimulus validity: done, requests and supply deadlines at least 3 ps from each other',
            '0 coincidences', f'{len(near_en) + len(near_sch)}', not near_en and not near_sch)
    for g in grants:
        g['tclk'] = period_before(E, g['t_gate']) or T_RO
    thr = THR_PULSE * p['g_pa']
    pulses = analyse_pulses(t, v, E, thr, fk)
    rep.add('one RF pulse per transmitted word, none for dropped words (S4, S5)', f'{len(grants)} pulses',
            f'{len(pulses)} pulses', len(pulses) == len(grants))
    # pulses cut short by rst are counted but not measured
    pairs = [(g, o) for g, o in zip(grants, pulses) if g['whole']]
    same = len(pulses) == len(grants)     # per-pulse rows need the one-to-one pairing
    errs = [abs(o['start'] - g['t_gate']) for g, o in pairs]
    rep.add('pulse start (energy centroid - Tw/2 - 10.9 ps) at frame edge + P x T/16 + 2 ps (S4)',
            f'|error| <= {TOL_START * 1e12:g} ps', f'worst {max(errs, default=0) * 1e12:.2f} ps over {len(errs)}',
            same and max(errs, default=0) <= TOL_START)
    dec_ok, prev, wrong = 0, None, []
    for g, o in pairs:
        ok = o['P'] == g['P'] and o['F'] == g['F'] and o['frame'] == g['frame']
        if prev is not None and prev[0]['n'] == g['n'] - 1 and o['frame'] == prev[1]['frame'] + 1:
            d = (round((o['start'] - prev[1]['start']) / o['delta']) - 16) % 8
            ok = ok and ((gray(d) << 3) | gray(o['F'])) == case['symbols'][g['n']]
        elif g['n'] == 0:
            ok = ok and ((gray(o['P']) << 3) | gray(o['F'])) == case['symbols'][0]
        dec_ok += ok
        if not ok:
            wrong.append((g['n'], (g['P'], g['F']), (o['P'], o['F'])))
        prev = (g, o)
    rep.add('decoded words equal the sent ones: P from the clk672 frame, D from pulse spacing, F from zero crossings (S4)',
            f'{len(pairs)} words', f'{dec_ok} correct; first wrong (word, sent P/F, decoded P/F) {wrong[:2]}',
            same and dec_ok == len(pairs))
    ferr = [abs(o['f'] / fk[g['F']] - 1) for g, o in pairs]
    rep.add('carrier frequency of each pulse (zero crossings in the middle half, S4)',
            f'|f/f_k - 1| <= {TOL_CARRIER:g}', f'worst {max(ferr, default=0):.4f}',
            same and max(ferr, default=0) <= TOL_CARRIER)
    corr = [(1 - 2 * g['pol']) * correlation(t, v, g, fk) for g, _ in pairs]
    rep.add('polarity and carrier phase: correlation with (-1)^pol x expected carrier (S4)',
            f'>= {MIN_CORR:g} for every pulse', f'min {min(corr, default=0):.3f}',
            same and min(corr, default=1) >= MIN_CORR)
    amp = [o['peak'] / p['g_pa'] for _, o in pairs]
    rep.add('pulse peak |outp - outn| scales with g_pa (S4)', f'{AMP_LO:g} to {AMP_HI:g} x g_pa',
            f'{min(amp, default=0):.3f} to {max(amp, default=0):.3f}',
            same and min(amp, default=1) >= AMP_LO and max(amp, default=1) <= AMP_HI)
    first = min((g['t_gate'] for g in grants), default=t_end)
    early = max((abs(x) for ti, x in zip(t, v) if ti < first - 3e-12), default=0.0)
    rep.add('no RF before the first enabled frame (S4)', f'|outp - outn| <= {V_QUIET * 1e3:g} mV',
            f'max {early * 1e3:.3g} mV', early <= V_QUIET)
    spans = sorted((g['t_gate'] - 3e-12, min(g['e'] + EDGE / 2, g.get('cut') or math.inf) + 300e-12) for g in grants)
    outside, k = 0.0, 0
    for ti, x in zip(t, v):
        while k < len(spans) and spans[k][1] < ti:
            k += 1
        if ti >= first and not (k < len(spans) and spans[k][0] <= ti <= spans[k][1]):
            outside = max(outside, abs(x))
    if t_rst:
        outside = max([outside] + [abs(x) for ti, x in zip(t, v) if ti > t_rst[0] + 5e-12])
    rep.add('no RF outside the transmitted pulses and their 300 ps tails; none after rst (S4, S5)',
            f'|outp - outn| <= {V_QUIET * 1e3:g} mV', f'max {outside * 1e3:.3g} mV', outside <= V_QUIET)
    cm = max(abs(a + b - 2 * p['vcm']) for a, b in zip(rows['outp'], rows['outn']))
    rep.add('common mode outp + outn = 2 vcm (S4)', f'|error| <= {V_CM:g} V', f'{cm:.2e} V', cm <= V_CM)

    # ---- S5 supplies and conflicts
    nmax = max(rows['nsup'])
    rep.add('nsup never exceeds 2 V (S5)', '<= 2 V', f'{nmax:.6f} V', nmax <= NSUP_MAX)
    for vth in (0.5, 1.5):
        match_edges(rep, f'nsup crossings of {vth:g} V follow the supply rules (S5)',
                    crossings(t, rows['nsup'], vth), level_crossings(count, vth), TOL_FLAG)
    match_edges(rep, f'conflict pulses at the {len(drops)} dropped requests (S5)', conf_x, conflict_edges(drops), TOL_FLAG)
    return [rep]
