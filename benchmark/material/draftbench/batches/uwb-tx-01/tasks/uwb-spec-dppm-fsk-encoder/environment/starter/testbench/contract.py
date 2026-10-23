"""Public contract for the DPPM + FSK encoder: stimuli, expected edges, checks.

Expected outputs are computed here from the Spec rules and the stimulus; the
checker never reads a reference model's waveform.
"""
from __future__ import annotations

import random

import uwbtask as u

EDGE = 2e-12            # stimulus edge (linear, centred on the stated time)
TOL = 2e-12             # crossing-time tolerance
TS = 1 / 672e6          # nominal word spacing of the seed chain
DEFAULTS = dict(vdd=1.0, vth=0.5, tr=2e-12, t_enc=10e-12, t_ev=30e-12, t_pw=400e-12)


def gray(b):
    return b ^ (b >> 1)


def gray_to_bin(g):
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def de_bruijn_codewords():
    """Absolute codewords 8P+F: order-2 de Bruijn over 64 symbols, then the first."""
    k, n = 64, 2
    a, seq = [0] * (k * n), []

    def db(t, p):
        if t > n:
            if n % p == 0:
                seq.extend(a[1:p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)
    db(1, 1)
    return seq + [seq[0]]


def words_for_codewords(codewords):
    out, p_prev = [], 0
    for cw in codewords:
        p, f = cw >> 3, cw & 7
        out.append((gray((p - p_prev) % 8) << 3) | gray(f))
        p_prev = p
    return out


# ------------------------------------------------------------------ cases ---

def public_cases():
    cws = de_bruijn_codewords()
    t0 = 2e-9
    debruijn = dict(name='debruijn', vin=1.0, instances=[dict(name='a', params={})],
                    words=[(t0 + n * TS, w) for n, w in enumerate(words_for_codewords(cws))],
                    rst=[(0.0, 1e-9)])
    # repeats, a reset 20 ps after a capture (enc_valid not yet up), a reset
    # while enc_valid is high, and a word right after release
    w = [(gray(3) << 3) | gray(5)] * 6 + [(gray(1) << 3) | gray(0), (gray(7) << 3) | gray(7)]
    words = [(2e-9 + n * TS, x) for n, x in enumerate(w)]
    t_r1 = words[3][0] + 20e-12
    t_r2 = words[6][0] + 200e-12
    more = [(words[-1][0] + 4 * TS + n * TS, x) for n, x in enumerate([w[0], w[0], w[6]])]
    reset_repeat = dict(name='reset_repeat', vin=1.0, instances=[dict(name='a', params={})],
                        words=words + more,
                        rst=[(0.0, 1e-9), (t_r1, words[4][0] - 600e-12), (t_r2, more[0][0] - 50e-12)])
    return [debruijn, reset_repeat]


def random_words(seed, n, t0, gap_min, gap_max):
    rnd = random.Random(seed)
    t, out = t0, []
    for _ in range(n):
        out.append((t, rnd.randrange(64) if rnd.random() > 0.2 or not out else out[-1][1]))
        t += rnd.uniform(gap_min, gap_max)
    return out


# --------------------------------------------------------------- netlist ---

def ramp_cross(t_mid, v0, v1, vth):
    """Crossing time of a linear EDGE-long ramp centred on t_mid."""
    return t_mid - EDGE / 2 + (vth - v0) / (v1 - v0) * EDGE


def stimulus(case):
    vin, words = case['vin'], case['words']
    lines = []
    for b in range(6):
        ch, prev = [(0.0, 0)], 0
        for t, wd in words:
            bit = (wd >> b) & 1
            if bit != prev:
                ch.append((t - 300e-12, bit))
                prev = bit
        lines.append(f'Vs{b} (s{b} 0) vsource type=pwl wave={u.pwl_levels(ch, EDGE, vin)}')
    sv = [(0.0, 0)]
    for t, _ in words:
        sv += [(t - 250e-12, 1), (t, 0)]
    lines.append(f'Vsv (sv 0) vsource type=pwl wave={u.pwl_levels(sv, EDGE, vin)}')
    rs = [(0.0, 1 if case['rst'] and case['rst'][0][0] == 0.0 else 0)]
    for on, off in case['rst']:
        if on > 0:
            rs.append((on, 1))
        rs.append((off, 0))
    lines.append(f'Vrst (rst 0) vsource type=pwl wave={u.pwl_levels(rs, EDGE, vin)}')
    return '\n'.join(lines)


def ids(k):
    base = 100 * (k + 1)
    return dict(pos=[base + i for i in range(3)], inc=[base + 3 + i for i in range(3)],
                fcode=[base + 6 + i for i in range(3)], req=[base + 10 + i for i in range(8)], ev=base + 20)


def netlist(case, candidate, tb_dir, stop):
    lines = ['simulator lang=spectre', 'global 0',
             f'ahdl_include "{candidate}"',
             f'ahdl_include "{tb_dir / "edge_monitor.va"}"', stimulus(case)]
    for k, inst in enumerate(case['instances']):
        n = inst['name']
        pins = (['s5', 's4', 's3', 's2', 's1', 's0', 'sv', 'rst']
                + [f'p{n}{i}' for i in (2, 1, 0)] + [f'i{n}{i}' for i in (2, 1, 0)]
                + [f'f{n}{i}' for i in (2, 1, 0)] + [f'r{n}{i}' for i in range(7, -1, -1)] + [f'ev{n}'])
        params = ' '.join(f'{key}={val!r}' for key, val in inst['params'].items())
        lines.append(f'X{n} ({" ".join(pins)}) dppm_fsk_encoder8 {params}'.rstrip())
        vmon = {**DEFAULTS, **inst['params']}['vdd'] / 2
        m = ids(k)
        nodes = ([(f'p{n}{i}', m['pos'][i]) for i in range(3)] + [(f'i{n}{i}', m['inc'][i]) for i in range(3)]
                 + [(f'f{n}{i}', m['fcode'][i]) for i in range(3)] + [(f'r{n}{i}', m['req'][i]) for i in range(8)]
                 + [(f'ev{n}', m['ev'])])
        lines += [f'Xmon_{node} ({node}) uwb_edge_monitor id={i} vth={vmon!r}' for node, i in nodes]
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={stop!r} maxstep=10p', 'save sv']
    return '\n'.join(lines) + '\n'


def stop_time(case):
    return max(t for t, _ in case['words']) + 2e-9


# -------------------------------------------------------------- expected ---

def expected(case, params):
    """Expected edge times (vdd/2 crossings) of every output for one instance."""
    p = {**DEFAULTS, **params}
    vin, vth, half = case['vin'], p['vth'], p['tr'] / 2
    events = []
    for on, off in case['rst']:
        if on > 0:
            events.append((ramp_cross(on, 0, vin, vth), 'rst_on', None))
        events.append((ramp_cross(off, vin, 0, vth), 'rst_off', None))
    in_reset = lambda t: any((on == 0 or ramp_cross(on, 0, vin, vth) <= t) and t < ramp_cross(off, vin, 0, vth)  # noqa: E731
                             for on, off in case['rst'])
    for t, w in case['words']:
        tc = ramp_cross(t, vin, 0, vth)
        if not in_reset(tc):
            events.append((tc, 'word', w))
    events.sort()
    level = {k: 0 for k in ['pos', 'inc', 'fcode', 'req', 'ev']}
    pending = []          # (start time, kind, value)
    edges = {f'{g}{i}': [] for g, n in (('pos', 3), ('inc', 3), ('fcode', 3), ('req', 8)) for i in range(n)}
    edges['ev'] = []
    words = []
    state = dict(P=0)

    def apply(ts, kind, val):
        if kind in ('data', 'clear'):
            new = (dict(pos=val[0], inc=val[1], fcode=val[2], req=1 << val[2]) if kind == 'data'
                   else dict(pos=0, inc=0, fcode=0, req=0))
            for g, n in (('pos', 3), ('inc', 3), ('fcode', 3), ('req', 8)):
                for i in range(n):
                    a, b = (level[g] >> i) & 1, (new[g] >> i) & 1
                    if a != b:
                        edges[f'{g}{i}'].append((ts + half, b))
                level[g] = new[g]
        else:
            if isinstance(val, tuple):          # enc_valid rise of a word: (1, word info)
                words.append(val[1])
                val = val[0]
            if level['ev'] != val:
                edges['ev'].append((ts + half, val))
                level['ev'] = val

    def flush(until):
        pending.sort(key=lambda x: x[0])
        while pending and pending[0][0] <= until:
            apply(*pending.pop(0))

    for t, kind, w in events:
        flush(t)
        if kind == 'rst_on':
            pending.clear()          # reset cancels updates not yet started
            state['P'] = 0
            apply(t, 'clear', None)
            apply(t, 'ev', 0)
        elif kind == 'word':
            d, f = gray_to_bin(w >> 3), gray_to_bin(w & 7)
            state['P'] = (state['P'] + d) % 8
            pending += [(t + p['t_enc'], 'data', (state['P'], d, f)),
                        (t + p['t_ev'], 'ev', (1, (t, state['P'], d, f))),
                        (t + p['t_ev'] + p['t_pw'], 'ev', 0)]
    flush(1.0)
    return edges, words


# ----------------------------------------------------------------- checks ---

def check(case, edges_seen: u.Edges):
    reps = []
    for k, inst in enumerate(case['instances']):
        rep = u.Report(f"{case['name']}/{inst['name']}")
        exp, words = expected(case, inst['params'])
        m = ids(k)
        groups = [('pos', m['pos']), ('inc', m['inc']), ('fcode', m['fcode']), ('req', m['req'])]
        for g, idl in groups:
            for i, ident in enumerate(idl):
                got = edges_seen.by_id.get(ident, [])
                want = exp[f'{g}{i}']
                ok_dir = [d for _, d in got] == [d for _, d in want]
                rep.times_match(f'{g}[{i}] edges (rule S2/S3 timing)', [t for t, _ in got] if ok_dir else [],
                                [t for t, _ in want], TOL)
        got = edges_seen.by_id.get(m['ev'], [])
        want = exp['ev']
        ok_dir = [d for _, d in got] == [d for _, d in want]
        rep.times_match('enc_valid edges: one pulse per accepted word (S4)', [t for t, _ in got] if ok_dir else [],
                        [t for t, _ in want], TOL)
        bad = []
        p = {**DEFAULTS, **inst['params']}
        for t, P, d, f in words:
            ts = t + p['t_ev'] + p['tr']
            seen = (edges_seen.bus(m['pos'], ts), edges_seen.bus(m['inc'], ts),
                    edges_seen.bus(m['fcode'], ts), edges_seen.bus(m['req'], ts))
            if seen != (P, d, f, 1 << f):
                bad.append((round(t * 1e9, 4), seen, (P, d, f, 1 << f)))
        rep.add('position/increment/frequency/one-hot while enc_valid is high (S2)',
                f'{len(words)} words', f'{len(words) - len(bad)} correct; first wrong {bad[:2]}', not bad)
        reps.append(rep)
    return reps
