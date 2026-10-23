"""Public contract for the pulse decoder: stimuli, independent measurement, checks.

The checker measures every pulse itself from the RF waveform saved in the same
run (or, for sources whose waveform is known in closed form, from that
formula) and applies the Spec rules S1 to S6 to it. It never reads the output
of a reference decoder.

Where the waveform puts a measured quantity within the checker's resolution of
a decision boundary (S8), the expectation is a range: a peak of |v| within M_V
of v_det makes the first or last exceedance uncertain by a carrier half
period, and an error within G_POS or G_F of its tolerance accepts both err
values.
"""
from __future__ import annotations

import math
import random

import uwbtask as u

EDGE = 2e-12            # stimulus edges and chain logic edges
TOL_T = 3e-12           # strobe crossing-time tolerance (S7)
M_V = 1e-3              # |v| band around v_det inside which an exceedance is uncertain (S8)
G_POS = 2e-12           # band around tol_pos*delta inside which err may be either (S8)
G_F = 0.002             # band around tol_f inside which err may be either (S8)
G_GAP = 10e-12          # exceedance gaps this close to t_gap make a case invalid (S8)
G_Z = 1e-12             # zero crossings this close to a window edge may count or not
MAX_ZC = 24             # zero crossings from the first exceedance to t_gap after the last (S8)
CARRIERS = [4.5e9 + k * 3e9 / 7 for k in range(8)]
DEFAULTS = dict(v_det=0.05, t_gap=100e-12, n_width=9, tol_pos=0.25, tol_f=0.03,
                t_lat=200e-12, t_pw=200e-12, vdd=1.0, vth=0.5, tr=2e-12)
CLK_ID = 9


class CaseError(RuntimeError):
    """The stimulus left the operating domain (S8): an author error, not a verdict."""


def gray(b):
    return b ^ (b >> 1)


def params(inst):
    return {**DEFAULTS, **inst['params']}


# ---------------------------------------------------------- seed chain (DUT) ---

CHAIN = ['serial_to_symbol6', 'dppm_fsk_encoder8', 'master_ro16', 'pulse_generator',
         'ro_scheduler8', 'rf_ro_branch', 'envelope_lane', 'tx_output']
FIRST_CAP = 5           # first bit captured on bit-clock edge 5 (as test/m4_chain)
BCLK_DELAY = 10e-12


def ro_period(code):
    return 1 / (600e6 + 0.25e6 * code)


def capture_time(case, k):
    return BCLK_DELAY + k * ro_period(case['code']) / 6 + EDGE / 2


def frame_of_symbol(case, n):
    """Nominal start (ph0 rising crossing) of the frame that carries symbol n.

    Bits are taken at 6x the RO rate. The word of symbol n is complete at
    capture FIRST_CAP + 6n + 5, the encoder takes it three bits later and its
    strobe rises 30 ps after that; the pulse generator sends it in the frame
    after the next ph0 edge (test/m4_chain timing). Used only to place decoder
    resets between pulses; the checker measures the pulses themselves.
    """
    T = ro_period(case['code'])
    t_enc = capture_time(case, FIRST_CAP + 6 * n + 8) + 30e-12
    return (math.floor(t_enc / T) + 2) * T + EDGE / 2


def positions(symbols):
    """Absolute positions P[n] the transmitter sends for the given symbols."""
    P, out = 0, []
    for s in symbols:
        g = s >> 3
        P = (P + (g ^ (g >> 1) ^ (g >> 2))) % 8
        out.append(P)
    return out


def reset_near(case, n_target, width=150e-12, after=0.5e-9, before=0.1e-9):
    """A decoder reset in the widest free time between consecutive pulses near symbol n_target.

    The free time starts `after` past the nominal end of a pulse (room for the
    decoder's pending strobe) and ends `before` the nominal start of the next.
    Only pulses with P != 0 qualify, so that the reset changes the next symbol.
    """
    d = ro_period(case['code']) / 16
    pos = positions(case['symbols'])
    best = None
    for n in range(max(0, n_target - 10), min(len(pos) - 1, n_target + 10)):
        if pos[n] == 0:
            continue
        lo = frame_of_symbol(case, n) + (pos[n] + 9) * d + after
        hi = frame_of_symbol(case, n + 1) + pos[n + 1] * d - before
        if best is None or hi - lo > best[1] - best[0]:
            best = (lo, hi)
    if best[1] - best[0] < width:
        raise ValueError(f'no room for a reset near symbol {n_target}')
    mid = (best[0] + best[1]) / 2
    return (mid - width / 2, mid + width / 2)


def pwl_bits(bits, first_capture, period, edge=EDGE, vdd=1.0):
    """NRZ bits sampled at first_capture + j*period; changes midway between captures."""
    pts = [(0.0, bits[0] * vdd)]
    for j in range(1, len(bits)):
        if bits[j] != bits[j - 1]:
            t = first_capture + (j - 0.5) * period
            pts += [(t - edge / 2, bits[j - 1] * vdd), (t + edge / 2, bits[j] * vdd)]
    return u.pwl(pts)


def decoder_rst(case):
    """Decoder reset: high from 0 to 1 ns, then the case's extra (on, off) intervals."""
    ch = [(0.0, 1), (1e-9, 0)]
    for on, off in case.get('drst', []):
        ch += [(on, 1), (off, 0)]
    return u.pwl_levels(ch, EDGE, 1.0)


def reset_intervals(case):
    """Reset intervals as seen by an instance (crossings of the 1 V ramps at vth)."""
    return [(0.0, 1e-9)] + list(case.get('drst', []))


def ids(k):
    base = 100 * (k + 1)
    return dict(sym=[base + i for i in range(6)], sv=base + 10, err=base + 11)


def decoder_lines(case, candidate_nodes):
    vp, vn, clk = candidate_nodes
    lines = [f'Vdrst (drst 0) vsource type=pwl wave={decoder_rst(case)}']
    for k, inst in enumerate(case['instances']):
        n = inst['name']
        pins = [vp, vn, clk, 'drst'] + [f'dsym_{n}{i}' for i in range(5, -1, -1)] + [f'dsv_{n}', f'derr_{n}']
        prm = ' '.join(f'{key}={val!r}' for key, val in inst['params'].items())
        lines.append(f'Xdut_{n} ({" ".join(pins)}) pulse_decoder {prm}'.rstrip())
        vmon = params(inst)['vdd'] / 2
        m = ids(k)
        nodes = [(f'dsym_{n}{i}', m['sym'][i]) for i in range(6)] + [(f'dsv_{n}', m['sv']), (f'derr_{n}', m['err'])]
        lines += [f'Xmon_{node} ({node}) uwb_edge_monitor id={i} vth={vmon!r}' for node, i in nodes]
    lines.append(f'Xmon_clk ({clk}) uwb_edge_monitor id={CLK_ID} vth={case.get("clk_vth", 0.5)!r}')
    return lines


def chain_netlist(case, candidate, tb_dir):
    code, symbols = case['code'], case['symbols']
    T_ro = ro_period(code)
    T = T_ro / 6
    bits = [(s >> (5 - k)) & 1 for s in symbols for k in range(6)]
    rst_release = capture_time(case, 4) + T / 2
    taps = ' '.join(f'ph{k}' for k in range(15, -1, -1))
    cbits = ' '.join(f'c{b}' for b in range(9, -1, -1))
    lines = ['simulator lang=spectre', 'global 0', f'ahdl_include "{candidate}"']
    lines += [f'ahdl_include "{tb_dir / "chain" / (m + ".va")}"' for m in CHAIN]
    lines += [f'ahdl_include "{tb_dir / "clock_source.va"}"', f'ahdl_include "{tb_dir / "edge_monitor.va"}"']
    lines += [f'Vc{b} (c{b} 0) vsource dc={(code >> b) & 1}' for b in range(10)]
    lines += [
        f'Xbclk (bclk) uwb_clock_source period={T!r} delay={BCLK_DELAY!r} tr={EDGE!r}',
        f'Vrst (rst 0) vsource type=pwl wave=[0 1 {u.fmt_ps(rst_release - 1e-12)} 1 {u.fmt_ps(rst_release + 1e-12)} 0]',
        f'Vdin (din 0) vsource type=pwl wave={pwl_bits(bits, capture_time(case, FIRST_CAP), T)}',
        'Ven (en 0) vsource dc=1',
    ]
    pols = case.get('pols')
    if pols:
        # one polarity bit per symbol, changed mid-frame (as test/m4_chain)
        lines.append(f'Vpol (pol 0) vsource type=pwl wave={pwl_bits(pols, capture_time(case, FIRST_CAP + 9), T_ro)}')
    else:
        lines.append('Vpol (pol 0) vsource dc=0')
    lines += [
        'Xs2p (bclk din rst sym5 sym4 sym3 sym2 sym1 sym0 sym_valid) uwb_serial_to_symbol6',
        'Xenc (sym5 sym4 sym3 sym2 sym1 sym0 sym_valid rst p2 p1 p0 i2 i1 i0 f2 f1 f0 '
        'q7 q6 q5 q4 q3 q2 q1 q0 enc_valid) uwb_dppm_fsk_encoder8',
        f'Xro ({cbits} {taps}) uwb_master_ro16',
        f'Xpg ({taps} p2 p1 p0 f2 f1 f0 pol enc_valid en rst pre_a rf_a sa2 sa1 sa0 pol_a '
        f'pre_b rf_b sb2 sb1 sb0 pol_b overrun) uwb_pulse_generator',
        f'Xsch (pre_a rf_a sa2 sa1 sa0 pre_b rf_b sb2 sb1 sb0 rst '
        f'{" ".join(f"pwr{k}" for k in range(7, -1, -1))} {" ".join(f"pre{k}" for k in range(7, -1, -1))} '
        f'{" ".join(f"rel{k}" for k in range(7, -1, -1))} gate_a gate_b conflict nsup '
        f'{" ".join(f"st{k}" for k in range(7, -1, -1))}) uwb_ro_scheduler8',
    ]
    lines += [f'Xbr{k} (pwr{k} pre{k} rel{k} vro{k}) uwb_rf_ro_branch f_rf={CARRIERS[k]!r}' for k in range(8)]
    lines += ['Xenva (gate_a ph0 env_a) uwb_envelope_lane', 'Xenvb (gate_b ph0 env_b) uwb_envelope_lane',
              f'Xout ({" ".join(f"vro{k}" for k in range(7, -1, -1))} env_a env_b gate_a gate_b '
              f'sa2 sa1 sa0 sb2 sb1 sb0 pol_a pol_b outp outn) uwb_tx_output']
    lines += decoder_lines(case, ('outp', 'outn', 'ph0'))
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={chain_stop(case)!r} maxstep=10p',
              'save outp outn']
    return '\n'.join(lines) + '\n'


def chain_stop(case):
    """Stop after the strobes of the last sent symbol, before those of the next word.

    After the last symbol the bit source holds its level, so the chain keeps
    sending words of all zeros or all ones; the run stops between the strobe of
    the last sent symbol and the strobe of the first such word.
    """
    n = len(case['symbols']) - 1
    d = ro_period(case['code']) / 16
    late = max(params(i)['t_lat'] + params(i)['t_pw'] for i in case['instances'])
    return frame_of_symbol(case, n) + (positions(case['symbols'])[n] + 9) * d + late + 0.25e-9


def netlist(case, candidate, tb_dir):
    if 'netlist' in case:                 # cases with their own fixed sources
        return case['netlist'](case, candidate, tb_dir)
    return chain_netlist(case, candidate, tb_dir)


def stop_time(case):
    return case['stop'] if 'stop' in case else chain_stop(case)


# ------------------------------------------------------------------ cases ---

def public_cases():
    rnd = random.Random(20261023)
    perm = list(range(64))
    rnd.shuffle(perm)
    symbols = perm + [rnd.randrange(64) for _ in range(56)]
    case = dict(name='chain288', code=288, symbols=symbols, instances=[dict(name='a', params={})])
    # a decoder-only reset between two pulses near symbol 70: afterwards
    # the decoder restarts from P_prev = 0 while the transmitter keeps its P
    case['drst'] = [reset_near(case, 70)]
    return [case]


# ------------------------------------------------------- pulse measurement ---

def _level_crossings(t, v, x):
    """Times where |v| rises above x and falls below x (piecewise-linear v)."""
    ups, downs = [], []
    for i in range(len(t) - 1):
        t1, t2, v1, v2 = t[i], t[i + 1], v[i], v[i + 1]
        if t2 <= t1:
            continue
        for lvl, up_dir in ((x, 1), (-x, -1)):
            a, b = v1 - lvl, v2 - lvl
            if (a <= 0 < b) or (a >= 0 > b):
                tc = t1 + (t2 - t1) * a / (a - b)
                rising = b > a
                (ups if rising == (up_dir == 1) else downs).append(tc)
    return sorted(ups), sorted(downs)


def exceedances(t, v, x):
    """Maximal intervals with |v| > x, from the samples."""
    ups, downs = _level_crossings(t, v, x)
    ev = sorted([(a, 1) for a in ups] + [(b, 0) for b in downs])
    out, start = [], (t[0] if abs(v[0]) > x else None)
    for tt, kind in ev:
        if kind == 1 and start is None:
            start = tt
        elif kind == 0 and start is not None:
            out.append((start, tt))
            start = None
    if start is not None:
        out.append((start, t[-1]))
    return out


def group(intervals, t_gap):
    """Join exceedances whose gap is shorter than t_gap; returns (start, end, gaps inside, gap before)."""
    out = []
    for a, b in intervals:
        if out and a - out[-1][1] < t_gap:
            out[-1][2].append(a - out[-1][1])
            out[-1][1] = b
        else:
            out.append([a, b, [], (a - out[-1][1]) if out else math.inf])
    return out


def zero_crossings(t, v):
    out = []
    for i in range(len(t) - 1):
        if v[i] * v[i + 1] < 0:
            out.append(t[i] + (t[i + 1] - t[i]) * v[i] / (v[i] - v[i + 1]))
    return out


def measure_pulses(t, v, p, zc=None):
    """Pulses of S1 with uncertainty ranges: [{tf: (lo, hi), tl: (lo, hi), zc: [...]}]."""
    zc = zero_crossings(t, v) if zc is None else zc
    groups = {}
    for key, x in (('mid', p['v_det']), ('lo', p['v_det'] - M_V), ('hi', p['v_det'] + M_V)):
        groups[key] = group(exceedances(t, v, x), p['t_gap'])
    pulses = []
    for g in groups['mid']:
        for gap in g[2] + ([g[3]] if g[3] < math.inf else []):
            if abs(gap - p['t_gap']) < G_GAP:
                raise CaseError(f'exceedance gap {gap*1e12:.1f} ps within {G_GAP*1e12:g} ps of t_gap '
                                f'near {g[0]*1e9:.4f} ns')
        lo = [h for h in groups['lo'] if h[0] < g[1] and h[1] > g[0]]
        hi = [h for h in groups['hi'] if h[0] < g[1] and h[1] > g[0]]
        if len(lo) != 1 or len(hi) != 1:
            raise CaseError(f'pulse near {g[0]*1e9:.4f} ns splits, merges or vanishes within '
                            f'{M_V*1e3:g} mV of v_det')
        hi = hi[0]
        pulses.append(dict(tf=(lo[0][0], hi[0]), tl=(hi[1], lo[0][1]),
                           zc=[z for z in zc if lo[0][0] - 1e-9 < z < lo[0][1] + 1e-9]))
    if len(groups['lo']) != len(pulses):
        raise CaseError(f'{len(groups["lo"])} pulses at v_det - {M_V*1e3:g} mV but {len(pulses)} at v_det')
    return pulses


def chain_truth(case, res, p):
    rows = u.read_rows(res['rows'])
    v = [a - b for a, b in zip(rows['outp'], rows['outn'])]
    return measure_pulses(rows['time'], v, p)


def truth(case, res, p):
    if 'truth' in case:
        return case['truth'](case, res, p)
    return chain_truth(case, res, p)


# -------------------------------------------------------------- expected ---

def clock(edges_seen):
    """Rising clk crossings and the period (S2; S8: the period is constant in a run)."""
    ck = edges_seen.times(CLK_ID, 1)
    if len(ck) < 3:
        raise CaseError('fewer than three clk edges')
    T = (ck[-1] - ck[0]) / (len(ck) - 1)
    worst = max(abs((b - a) - T) for a, b in zip(ck, ck[1:]))
    if worst > 1e-12 or not 1.1e-9 <= T <= 1.75e-9:
        raise CaseError(f'clk period {T*1e9:.4f} ns varies by {worst*1e12:.2f} ps or is outside 1.1 to 1.75 ns')
    return ck, T


def window_frequency(zc, c, w):
    """S3 at one centre: (N, f) from the zero crossings in [c - w, c + w]."""
    inside = [z for z in zc if c - w <= z <= c + w]
    if len(inside) < 2:
        return len(inside), None
    return len(inside), (len(inside) - 1) / (2 * (inside[-1] - inside[0]))


def nearest(f):
    return min(range(8), key=lambda k: abs(CARRIERS[k] - f))


def either(lo_ok, hi_ok):
    """1 / 0 when every value in a range is outside / inside a limit, else None."""
    return 1 if lo_ok else (0 if hi_ok else None)


def expected(pulses, ck, T, p, resets):
    """S2 to S6 for every pulse: list of dicts with the allowed outcomes."""
    delta = T / 16
    nw = p['n_width']
    out, p_prev = [], 0
    rs = sorted(resets)
    for k, pu in enumerate(pulses):
        # S8: resets only while no pulse is in progress and no output is pending
        prev_busy = pulses[k - 1]['tl'][1] + p['t_lat'] + p['t_pw'] + p['tr'] + 50e-12 if k else -1.0
        for on, off in rs:
            if on < pu['tl'][1] and off > pu['tf'][0] - 50e-12:
                raise CaseError(f'reset {on*1e9:.4f}-{off*1e9:.4f} ns overlaps the pulse at {pu["tf"][0]*1e9:.4f} ns')
            if prev_busy < on < pu['tf'][0]:
                p_prev = 0          # S7: the next pulse starts from P_prev = 0
            elif k and pulses[k - 1]['tl'][0] < on < prev_busy:
                raise CaseError(f'reset at {on*1e9:.4f} ns while an output is pending')
        if k and pu['tl'][0] - pulses[k - 1]['tl'][1] < p['t_lat'] + p['t_pw'] + 50e-12:
            raise CaseError(f'pulse at {pu["tf"][0]*1e9:.4f} ns ends less than t_lat + t_pw + 50 ps after the previous one')
        if len([z for z in pu['zc'] if pu['tf'][0] <= z <= pu['tl'][1] + p['t_gap']]) > MAX_ZC:
            raise CaseError(f'pulse at {pu["tf"][0]*1e9:.4f} ns has more than {MAX_ZC} zero crossings')
        if pu['tl'][1] - pu['tf'][0] > 1.2e-9:
            raise CaseError(f'pulse at {pu["tf"][0]*1e9:.4f} ns lasts longer than 1.2 ns')
        if len([x for x in ck if x < pu['tf'][0]]) < 2:
            raise CaseError(f'fewer than two clk edges before the pulse at {pu["tf"][0]*1e9:.4f} ns')
        c_lo = (pu['tf'][0] + pu['tl'][0]) / 2
        c_hi = (pu['tf'][1] + pu['tl'][1]) / 2
        ps, es = set(), []
        for c in (c_lo, c_hi):
            ts = c - nw * delta / 2
            prior = [x for x in ck if x <= ts + delta / 2]
            if not prior:
                raise CaseError(f'no clk edge before the pulse at {c*1e9:.4f} ns')
            frame = prior[-1]
            P = round((ts - frame) / delta)
            ps.add(P)
            es.append(ts - frame - P * delta)
        if len(ps) != 1:
            raise CaseError(f'pulse at {c_lo*1e9:.4f} ns: position rounds differently inside its uncertainty')
        P = ps.pop()
        e_min = 0.0 if es[0] <= 0 <= es[1] else min(abs(es[0]), abs(es[1]))
        e_max = max(abs(es[0]), abs(es[1]))
        lim = p['tol_pos'] * delta
        bad_pos = either(e_min > lim + G_POS, e_max < lim - G_POS)
        # S3 over the centre range and window edges +- G_Z
        w = nw * delta / 4
        if c_lo - w < pu['tf'][1] or c_hi + w > pu['tl'][0]:
            raise CaseError(f'pulse at {c_lo*1e9:.4f} ns: the frequency window is not inside the pulse (S8)')
        fs, ns = [], set()
        steps = 8
        for j in range(steps + 1):
            c = c_lo + (c_hi - c_lo) * j / steps
            for dw in (-G_Z, 0.0, G_Z):
                n, f = window_frequency(pu['zc'], c, w + dw)
                ns.add(n)
                fs.append(f)
        if any(f is None for f in fs):
            if not all(f is None for f in fs):
                raise CaseError(f'pulse at {c_lo*1e9:.4f} ns: fewer than two crossings at some window positions')
            F, bad_f, f_rep, rel = 0, 1, None, None
        else:
            Fs = {nearest(f) for f in fs}
            if len(Fs) != 1:
                raise CaseError(f'pulse at {c_lo*1e9:.4f} ns: carrier lies between two channels within resolution')
            F = Fs.pop()
            rels = [abs(f / CARRIERS[F] - 1) for f in fs]
            bad_f = either(min(rels) > p['tol_f'] + G_F, max(rels) < p['tol_f'] - G_F)
            f_rep, rel = fs[len(fs) // 2], max(rels)
        flags = [bad_pos, 1 if P > 7 else 0, bad_f]
        err = 1 if 1 in flags else (0 if all(x == 0 for x in flags) else None)
        D = (P - p_prev) % 8
        out.append(dict(n=len(out), tf=pu['tf'], tl=pu['tl'], P=P, D=D, F=F, e=es, f=f_rep, f_rel=rel,
                        sym=(gray(D) << 3) | gray(F), err=err, n_zc=sorted(ns)))
        p_prev = P % 8
    return out


# ----------------------------------------------------------------- checks ---

def strobes(edges_seen, ident):
    """(rise, fall) pairs of sym_valid crossings; a missing fall is math.inf."""
    out, rise = [], None
    for tt, d in edges_seen.by_id.get(ident, []):
        if d == 1:
            if rise is not None:
                out.append((rise, math.inf))
            rise = tt
        elif rise is not None:
            out.append((rise, tt))
            rise = None
    if rise is not None:
        out.append((rise, math.inf))
    return out


def check(case, edges_seen: u.Edges, res):
    """Rows for every instance of one case; returns (reports, info)."""
    reps, info = [], []
    ck, T = clock(edges_seen)
    resets = reset_intervals(case)
    for k, inst in enumerate(case['instances']):
        p = params(inst)
        rep = u.Report(f"{case['name']}/{inst['name']}")
        # the chain keeps sending until the run stops: a pulse whose strobe would
        # start after the stop time is not graded; the stop time never cuts a strobe
        stop = stop_time(case)
        pulses = []
        for pu in truth(case, res, p):
            t_d = pu['tl'][1] + p['t_lat']
            if t_d < stop and t_d + p['t_pw'] + p['tr'] + 20e-12 > stop:
                raise CaseError(f'stop time {stop*1e9:.4f} ns cuts the strobe of the pulse at {pu["tf"][0]*1e9:.4f} ns')
            if t_d < stop:
                pulses.append(pu)
        exp = expected(pulses, ck, T, p, resets)
        m = ids(k)
        got = strobes(edges_seen, m['sv'])
        half = p['tr'] / 2
        # S6 timing: one strobe per pulse, rising t_lat after the last exceedance
        n = min(len(got), len(exp))
        worst, bad_t = 0.0, []
        for (r, f), x in zip(got[:n], exp[:n]):
            lo = x['tl'][0] + p['t_lat'] + half
            hi = x['tl'][1] + p['t_lat'] + half
            dr = max(lo - r, r - hi, 0.0)
            df = max(lo + p['t_pw'] - f, f - hi - p['t_pw'], 0.0)
            worst = max(worst, dr, df)
            if dr > TOL_T or df > TOL_T:
                bad_t.append((x['n'], round(r * 1e9, 4), round((x['tl'][0] + p['t_lat']) * 1e9, 4)))
        rep.add('one sym_valid pulse per pulse; rises t_lat after the last exceedance, high for t_pw (S1, S6)',
                f'{len(exp)} pulses, |error| <= {TOL_T*1e12:g} ps beyond the last-exceedance range',
                f'{len(got)} pulses, worst {worst*1e12:.3f} ps' + (f', first late/early {bad_t[:2]}' if bad_t else ''),
                len(got) == len(exp) and not bad_t)
        # S4/S5 values at the middle of each strobe; no sym/err edge while it is high
        wrong_sym, wrong_err, ambiguous, moving = [], [], 0, []
        for (r, f), x in zip(got[:n], exp[:n]):
            tm = (r + min(f, r + p['t_pw'])) / 2
            s = edges_seen.bus(m['sym'], tm)
            e = edges_seen.level(m['err'], tm)
            if s != x['sym']:
                wrong_sym.append(dict(pulse=x['n'], got=s, want=x['sym'], P=x['P'], D=x['D'], F=x['F']))
            if x['err'] is None:
                ambiguous += 1
            elif e != x['err']:
                wrong_err.append(dict(pulse=x['n'], got=e, want=x['err'], P=x['P'],
                                      e_ps=[round(z * 1e12, 2) for z in x['e']],
                                      f_rel=None if x['f_rel'] is None else round(x['f_rel'], 4)))
            for ident in m['sym'] + [m['err']]:
                if any(r + half < tt < f - half for tt in edges_seen.times(ident)):
                    moving.append(x['n'])
                    break
        rep.add('sym = 8*Gray(D) + Gray(F) on every strobe (S2, S3, S4)', f'{n} strobes',
                f'{n - len(wrong_sym)} correct; first wrong {wrong_sym[:2]}', not wrong_sym)
        n_bad = sum(1 for x in exp[:n] if x['err'] == 1)
        rep.add('err high exactly for malformed pulses (S5)',
                f'{n} strobes ({n_bad} malformed, {ambiguous} at a boundary: either)',
                f'{n - ambiguous - len(wrong_err)} correct; first wrong {wrong_err[:2]}', not wrong_err)
        rep.add('sym and err hold their values while sym_valid is high (S6)', 'no sym/err edge inside a strobe',
                f'{len(moving)} strobes with an edge {moving[:3]}', not moving)
        # S7: outputs low while rst is high (checked in the middle of every reset)
        lows = []
        for on, off in resets:
            tm = (on + off) / 2
            lv = (edges_seen.bus(m['sym'], tm), edges_seen.level(m['err'], tm), edges_seen.level(m['sv'], tm))
            if lv != (0, 0, 0):
                lows.append((round(tm * 1e9, 3), lv))
        rep.add('sym, err and sym_valid are low while rst is high (S7)', f'{len(resets)} reset intervals',
                f'{len(lows)} with a high output {lows[:2]}', not lows)
        reps.append(rep)
        info.append(dict(instance=inst['name'], pulses=len(exp), malformed=n_bad, ambiguous=ambiguous,
                         symbols=[x['sym'] for x in exp], err=[x['err'] for x in exp],
                         P=[x['P'] for x in exp], F=[x['F'] for x in exp],
                         e_ps=[[round(z * 1e12, 2) for z in x['e']] for x in exp],
                         f_rel=[None if x['f_rel'] is None else round(x['f_rel'], 5) for x in exp]))
    return reps, info
