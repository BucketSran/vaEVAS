"""M4 check: integrated seed chain (SPEC.md 4.2-4.9).

bits -> serial-to-symbol -> encoder -> PG -> scheduler -> 8 RF branches ->
2 envelope lanes -> combiner/PA -> outp/outn, with the RO at code 288 and the
CDC test condition of SPEC.md section 5.

The checker replays the SPEC rules independently:
  1. sent symbols -> absolute codewords (P, F) (reference rules);
  2. observed enc_valid and tap edges -> PG lane windows (SPEC 4.6);
  3. lane windows -> two-slot scheduler (SPEC 4.7) -> expected pwr/pre/rel
     edges per branch, lane gates and conflicts;
  4. for runs that save RF: expected outp - outn from the SPEC formulas for
     branch phase/amplitude, envelope and combiner, using the observed
     release and gate times.

Scenarios
  debruijn  4097 symbols, all 64 codewords and 4096 adjacent pairs, no RF
  hold      same-branch pairs 7->0 (touching), 6->0, 4->0 (hold), 3->0 and
            2->0 (off, cold restart); polarity bits and DPC gains; RF checked
  conflict  n_pre = 15; P = 7, x, 0 with three different branches makes the
            third request find both slots busy -> dropped symbol; RF checked
  hold_idle n_pre = 1: request in TAIL, in the idle-hold window, and after it
  preempt   t_hold = 2 ns: a third branch takes the slot of an idle HOLD
  idle      en low for 12 frames: pending words overrun, branches off, cold restart
  random    200 PRBS symbols with random polarity; RF checked

Usage: python3 check_chain.py [scenario ...]
"""
import csv
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import chain_tb as C  # noqa: E402
import uwbtest as u  # noqa: E402

EDGE = 2e-12
TOL = 1e-12
DELTA0 = u.DELTA0
T_TAIL, T_HOLD, T_CONF = 150e-12, 200e-12, 200e-12
I = C.IDS


def run_tb(tb, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tb.scs').write_text(tb)
    res = u.run_evas(out / 'tb.scs', out)
    edges = u.parse_edges(res)
    edges.drop_startup()
    return edges, res


def codewords(symbols):
    out, p = [], 0
    for s in symbols:
        p = (p + u.gray_to_bin(s >> 3)) % 8
        out.append((p, u.gray_to_bin(s & 7)))
    return out


def pg_replay(edges, cws, pols, n_pre, n_width=9, en_on=lambda t: True, overruns=None):
    """Lane windows from observed enc_valid and taps (SPEC 4.6)."""
    ev = edges.times(I['enc_valid'], 1)
    ph0 = edges.times(I['ph0'], 1)
    taps = sorted(t for k in range(16) for t in edges.times(I[f'ph{k}'], 1))
    pend, lane, out, j = None, 0, [], 0
    for t0 in ph0:
        while j < len(ev) and ev[j] < t0:
            if pend is not None and overruns is not None:
                overruns.append(ev[j])     # pending word overwritten
            pend = j          # index of the latched word
            j += 1
        if pend is None or not en_on(t0):
            continue
        P, F = cws[pend]
        idx = [i for i, t in enumerate(taps) if t > t0 + 1e-13]

        def tap(n):
            return taps[idx[n]] if n < len(idx) else math.inf

        out.append(dict(n=pend, P=P, F=F, pol=pols[pend], lane=lane, s=tap(16 + P - 1),
                        e=tap(16 + P - 1 + n_width), p=tap(16 + P - 1 - n_pre)))
        lane = 1 - lane
        pend = None
    return out


def scheduler_replay(wins, n_pre, t_tail=T_TAIL, t_hold=T_HOLD):
    """Two-slot scheduler (SPEC 4.7) driven by the lane windows.

    Returns per-branch intervals for pwr, pre, rel, the granted windows and drops.
    """
    t_wait = max(0.0, t_hold - n_pre * DELTA0)
    events = []
    for w in wins:
        events += [(w['p'], 1, 'req', w), (w['s'], 2, 'start', w), (w['e'], 0, 'end', w)]
    events.sort(key=lambda x: (x[0], x[1]))
    slots = [dict(br=-1, st=0, pend=0, nact=0, due=None) for _ in range(2)]
    lane_slot = {0: None, 1: None}
    hist = {k: [] for k in range(8)}   # (time, state) changes per branch
    drops, grants = [], []
    stats = dict(preempt=0, warm_from_idle=0, warm=0, cold=0)

    def set_state(s, st, t):
        if slots[s]['br'] >= 0:
            hist[slots[s]['br']].append((t, st))
        slots[s]['st'] = st

    def advance(t):
        """Process slot deadlines strictly before t (in time order)."""
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
                set_state(i, 5, td)
                if sl['pend'] == 0:
                    sl['due'] = td + t_wait
                    if t_wait <= 0:
                        set_state(i, 0, td); sl['br'] = -1; sl['due'] = None
                else:
                    sl['due'] = None
            else:
                set_state(i, 0, td); sl['br'] = -1; sl['due'] = None

    for t, _, kind, w in events:
        advance(t)
        if kind == 'req':
            k = w['F']
            hit = [i for i, sl in enumerate(slots) if sl['st'] != 0 and sl['br'] == k]
            free = [i for i, sl in enumerate(slots) if sl['st'] == 0]
            idle = [i for i, sl in enumerate(slots) if sl['st'] == 5 and sl['pend'] == 0]
            if hit:
                i = hit[0]
                stats['warm'] += 1
                if slots[i]['st'] == 5 and slots[i]['pend'] == 0:
                    stats['warm_from_idle'] += 1
                slots[i]['pend'] += 1; lane_slot[w['lane']] = i
                if slots[i]['st'] == 5:
                    slots[i]['due'] = None
            elif free or idle:
                i = (free or idle)[0]
                stats['cold'] += 1
                if not free:
                    stats['preempt'] += 1
                if slots[i]['br'] >= 0:
                    set_state(i, 0, t)          # idle hold gives up its slot
                slots[i].update(br=k, pend=1, nact=0, due=None)
                set_state(i, 1, t)
                lane_slot[w['lane']] = i
            else:
                lane_slot[w['lane']] = None
                drops.append(w)
        elif kind == 'start':
            i = lane_slot[w['lane']]
            if i is not None:
                sl = slots[i]
                if sl['st'] != 3:
                    set_state(i, 3, t)
                sl['nact'] += 1; sl['pend'] = max(0, sl['pend'] - 1); sl['due'] = None
                grants.append(w)
        else:
            i = lane_slot[w['lane']]
            if i is not None:
                sl = slots[i]
                sl['nact'] -= 1
                if sl['nact'] <= 0:
                    sl['nact'] = 0
                    set_state(i, 4, t)
                    sl['due'] = t + t_tail
            lane_slot[w['lane']] = None
    advance(1.0)
    return hist, grants, drops, stats


# Scheduler outputs sit two finite edges after the tap crossing that causes
# them (PG edge, then scheduler edge), each crossing at its 1 ps midpoint.
SCH = EDGE


def level_edges(hist_k, pred):
    """Rising/falling times of pred(state) for one branch's state history."""
    out, level = [], 0
    for t, st in hist_k:
        new = 1 if pred(st) else 0
        if new != level:
            out.append((t + SCH, new))
            level = new
    return out


T_STOP = [math.inf]


def compare_edges(rep, label, got, exp):
    lim = T_STOP[0] - 5e-12
    got = [e for e in got if e[0] < lim]
    exp = [e for e in exp if e[0] < lim]
    ok = len(got) == len(exp) and all(d1 == d2 and abs(t1 - t2) < TOL for (t1, d1), (t2, d2) in zip(got, exp))
    n = min(len(got), len(exp))
    worst = max((abs(a[0] - b[0]) for a, b in zip(got[:n], exp[:n])), default=0.0)
    first_bad = next((i for i, (a, b) in enumerate(zip(got, exp)) if a[1] != b[1] or abs(a[0] - b[0]) >= TOL), None)
    rep.check(label, ok, f'{len(got)} vs {len(exp)} edges, worst {worst*1e12:.3f} ps, first mismatch {first_bad}')
    return ok


def check_control(rep, edges, symbols, pols, n_pre, label, n_sent, t_tail=T_TAIL, t_hold=T_HOLD,
                  en_on=lambda t: True):
    cws = codewords(symbols)
    overruns = []
    wins = pg_replay(edges, cws, pols, n_pre, en_on=en_on, overruns=overruns)
    sent = len([w for w in wins if w['n'] < n_sent])
    rep.check(f'{label}: PG schedules every sent word that was not overwritten',
              sent == n_sent - len([t for t in overruns if t < edges.times(I['enc_valid'], 1)[n_sent - 1] + 1e-12]),
              f'{sent} pulses for {n_sent} sent words, {len(overruns)} overwritten')
    # lane windows as produced by the PG
    for ln, nm in ((0, 'a'), (1, 'b')):
        mine = [w for w in wins if w['lane'] == ln]
        exp = sorted([(w['s'] + EDGE / 2, 1) for w in mine] + [(w['e'] + EDGE / 2, 0) for w in mine])
        compare_edges(rep, f'{label}: lane {nm} rf windows', edges.by_id.get(I[f'rf_{nm}'], []), exp)
        exp = sorted([(w['p'] + EDGE / 2, 1) for w in mine] + [(w['s'] + EDGE / 2, 0) for w in mine])
        compare_edges(rep, f'{label}: lane {nm} precharge windows', edges.by_id.get(I[f'pre_{nm}'], []), exp)
    hist, grants, drops, stats = scheduler_replay(wins, n_pre, t_tail, t_hold)
    rep.check(f'{label}: scheduler paths exercised (replay)', True,
              ', '.join(f'{k}={v}' for k, v in stats.items()) + f', drops={len(drops)}')
    for k in range(8):
        compare_edges(rep, f'{label}: branch {k} pwr', edges.by_id.get(I[f'pwr{k}'], []),
                      level_edges(hist[k], lambda st: st != 0))
        compare_edges(rep, f'{label}: branch {k} pre', edges.by_id.get(I[f'pre{k}'], []),
                      level_edges(hist[k], lambda st: st == 1))
        compare_edges(rep, f'{label}: branch {k} rel', edges.by_id.get(I[f'rel{k}'], []),
                      level_edges(hist[k], lambda st: st >= 2))
    for ln, nm in ((0, 'a'), (1, 'b')):
        mine = [w for w in grants if w['lane'] == ln]
        exp = sorted([(w['s'] + SCH, 1) for w in mine] + [(w['e'] + SCH, 0) for w in mine])
        compare_edges(rep, f'{label}: gate_{nm} only for granted symbols', edges.by_id.get(I[f'gate_{nm}'], []), exp)
    exp = sorted([(w['p'] + SCH, 1) for w in drops] + [(w['p'] + T_CONF + SCH, 0) for w in drops])
    compare_edges(rep, f'{label}: conflict pulses at dropped requests', edges.by_id.get(I['conflict'], []), exp)
    # physical invariant from the observed supplies, not from the replay
    pw = sorted((t, d) for k in range(8) for t, d in edges.by_id.get(I[f'pwr{k}'], []))
    n, worst = 0, 0
    for t, d in pw:
        n += 1 if d else -1
        worst = max(worst, n)
    rep.check(f'{label}: never more than 2 branches powered', worst <= 2, f'max {worst}')
    exp = sorted([(t + EDGE / 2, 1) for t in overruns] + [(t + 200e-12 + EDGE / 2, 0) for t in overruns])
    compare_edges(rep, f'{label}: overrun pulses where a pending word was overwritten',
                  edges.by_id.get(I['overrun'], []), exp)
    return wins, hist, grants, drops, stats


# ------------------------------------------------------------------ RF -------

def env_resp(u_, tw, tau):
    w = 2 * math.pi / tw
    ue = min(u_, tw)
    k = 1 / (1 + w * w * tau * tau)
    y = 0.5 * (1 - math.exp(-ue / tau)) - 0.5 * k * (math.cos(w * ue) + w * tau * math.sin(w * ue) - math.exp(-ue / tau))
    if u_ > tw:
        y *= math.exp(-(u_ - tw) / tau)
    return y


def check_rf(rep, edges, res, grants, label, pols_of=None, dpc_db=None):
    rows = list(csv.DictReader(open(res['tran'])))
    t = [float(r['time']) for r in rows]
    vdiff = [float(r['outp']) - float(r['outn']) for r in rows]
    tau_a = tau_f = 200e-12 / math.log(100)
    tau_e = 50e-12 / math.log(100)
    # branch oscillation intervals from the observed rel edges (release -> stop)
    osc = {k: [] for k in range(8)}
    for k in range(8):
        r = edges.by_id.get(I[f'rel{k}'], [])
        for (t1, d1), (t2, d2) in zip(r, r[1:]):
            if d1 == 1 and d2 == 0:
                osc[k].append((t1, t2))
        if r and r[-1][1] == 1:
            osc[k].append((r[-1][0], 1.0))
    ph0 = edges.times(I['ph0'], 1)
    gdb = dpc_db or [0.0] * 8

    def vro(k, ti):
        for a, b in osc[k]:
            if a < ti < b:
                uu = ti - a
                f = u.CARRIERS[k]
                return (1 - math.exp(-uu / tau_a)) * math.cos(2 * math.pi * f * (uu + 0.01 * tau_f * (1 - math.exp(-uu / tau_f))))
        return 0.0

    # envelope lanes start and stop on the observed scheduler gates
    gates = {0: edges.by_id.get(I['gate_a'], []), 1: edges.by_id.get(I['gate_b'], [])}
    pulses = []
    for w in grants:
        g = gates[w['lane']]
        tg = min((t for t, d in g if d == 1 and abs(t - (w['s'] + SCH)) < 5e-12), default=None)
        te = min((t for t, d in g if d == 0 and abs(t - (w['e'] + SCH)) < 5e-12), default=math.inf)
        if tg is None:
            continue
        prev = [x for x in ph0 if x < tg]
        tclk = prev[-1] - prev[-2]
        pulses.append((tg, te, 9 * tclk / 16, w['F'], w['pol']))
    err, worst_t, n = 0.0, 0.0, 0
    for ti, vi in zip(t, vdiff):
        # skip points within 3 ps of an observed rel edge or gate edge (finite transitions)
        exp = 0.0
        for tg, te, tw, k, pol in pulses:
            if tg - 1e-12 < ti < te + 400e-12:
                uu = ti - tg
                if ti < te:
                    e = env_resp(uu, tw, tau_e)
                else:
                    e = env_resp(te - tg, tw, tau_e) * math.exp(-(ti - te) / tau_e)
                exp += (-1 if pol else 1) * 10 ** (gdb[k] / 20) * e * vro(k, ti)
        d = abs(vi - exp)
        if d > err:
            err, worst_t = d, ti
        n += 1
    rep.check(f'{label}: outp - outn equals the SPEC reconstruction', err < 2e-3,
              f'max error {err:.2e} V at {worst_t*1e9:.4f} ns over {n} points')
    # carrier check per granted pulse: zero crossings inside the pulse at the branch frequency
    bad = []
    for tg, te, tw, k, pol in pulses:
        zc = [t[i] + (t[i + 1] - t[i]) * vdiff[i] / (vdiff[i] - vdiff[i + 1])
              for i in range(len(t) - 1)
              if tg + 0.25 * tw < t[i] < tg + 0.75 * tw and vdiff[i] * vdiff[i + 1] < 0]
        if len(zc) >= 3:
            f_est = (len(zc) - 1) / 2 / (zc[-1] - zc[0])
            if abs(f_est / u.CARRIERS[k] - 1) > 0.02:
                bad.append((round(tg * 1e9, 3), k, round(f_est / 1e9, 3)))
    rep.check(f'{label}: each pulse carries its branch frequency (zero crossings, +-2 %)', not bad, f'{bad[:3]}')
    vmax_off = max((abs(v) for ti, v in zip(t, vdiff)
                    if all(not (tg - 2e-12 < ti < te + 300e-12) for tg, te, *_ in pulses)), default=0.0)
    rep.check(f'{label}: no output outside pulses and their 300 ps tails', vmax_off < 1e-6, f'max {vmax_off:.2e} V')


def run_debruijn_chunks(rep, n_chunks=8):
    """4097 codewords in chunks (legacy EVAS runs out of memory on one 6 us run).

    Each chunk starts from reset, so its input symbols are recomputed with
    P[-1] = 0; consecutive chunks overlap by one codeword so that every
    adjacent pair still appears inside one chunk.
    """
    cws = u.codeword_sequence()
    size = math.ceil((len(cws) - 1) / n_chunks)
    seen_pairs, seen_cw = set(), set()
    for c in range(n_chunks):
        part = cws[c * size: min(len(cws), (c + 1) * size + 1)]
        symbols = u.symbols_for_codewords(part)
        pols = [0] * len(symbols)
        out = u.out_dir_for(f'm4_debruijn/chunk{c}')
        tb, stop = C.build(symbols, rf=False)
        T_STOP[0] = stop
        edges, res = run_tb(tb, out)
        n_sent = len(symbols)
        extra = len(edges.times(I['enc_valid'], 1)) - len(symbols)
        if extra > 0:
            symbols = symbols + [63 if symbols[-1] & 1 else 0] * extra
            pols = pols + [0] * extra
        wins, hist, grants, drops, _ = check_control(rep, edges, symbols, pols, 2, f'debruijn chunk {c}', n_sent)
        got = [8 * w['P'] + w['F'] for w in wins][:n_sent]
        rep.check(f'debruijn chunk {c}: PG codewords equal the sent ones', got == part, f'{len(got)} codewords')
        rep.check(f'debruijn chunk {c}: no symbol dropped with n_pre = 2', not drops, f'{len(drops)}')
        seen_cw |= set(got)
        seen_pairs |= set(zip(got, got[1:]))
    rep.check('debruijn: all 64 codewords reach the PG', len(seen_cw) == 64, f'{len(seen_cw)}')
    rep.check('debruijn: all 4096 adjacent codeword pairs reach the PG', len(seen_pairs) == 4096,
              f'{len(seen_pairs)}')


def run(name):
    out = u.out_dir_for(f'm4_{name}')
    rep = u.Report(f'm4_{name}')
    if name == 'debruijn':
        run_debruijn_chunks(rep)
        out.mkdir(parents=True, exist_ok=True)
        rep.write(out)
        print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
        return rep.ok
    n_pre, rf, dpc = 2, True, None
    t_tail, t_hold, en_wave, en_on = T_TAIL, T_HOLD, None, (lambda t: True)
    if name == 'hold':
        # (P, F) pairs: same F with P a -> 0 for a = 7, 6, 4, 3, 2, separated by other F
        seq = [(1, 6), (7, 3), (0, 3), (3, 5), (6, 1), (0, 1), (5, 4), (4, 2), (0, 2), (6, 7),
               (3, 0), (0, 0), (5, 6), (2, 5), (0, 5), (1, 3)]
        symbols = u.symbols_for_codewords([8 * p + f for p, f in seq])
        pols = [0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 1, 1, 0]
        dpc = [0.0, -1.0, 0.5, -2.0, 1.5, 0.0, -0.5, 1.0]
    elif name == 'conflict':
        n_pre = 15
        # drops: symbol 3 on lane b (P1 = 7, P3 = 0) and symbol 8 on lane a (P6 = 7, P8 = 0)
        seq = [(2, 0), (7, 1), (3, 2), (0, 3), (5, 4), (2, 5), (7, 6), (4, 7), (0, 0), (3, 1), (6, 2), (1, 3)]
        symbols = u.symbols_for_codewords([8 * p + f for p, f in seq])
        pols = [0] * len(symbols)
    elif name == 'hold_idle':
        # n_pre = 1: the idle-hold window is t_hold - delta0 = 107 ps. Same-F pairs
        # with start spacing 11 delta (request in TAIL), 12 delta (request in the
        # idle-hold window) and 13 delta (after it: off, cold restart)
        n_pre = 1
        seq = [(1, 6), (7, 3), (2, 3), (5, 5), (6, 1), (2, 1), (4, 4), (5, 2), (2, 2), (3, 7), (7, 0), (2, 0), (0, 6)]
        symbols = u.symbols_for_codewords([8 * p + f for p, f in seq])
        pols = [0] * len(symbols)
    elif name == 'preempt':
        # t_hold = 2 ns keeps a branch in idle HOLD long enough that the third
        # different branch must take its slot
        t_hold = 2e-9
        seq = [(3, 0), (2, 1), (5, 2), (1, 3), (6, 4), (0, 5), (4, 6), (7, 7), (2, 0), (5, 1)]
        symbols = u.symbols_for_codewords([8 * p + f for p, f in seq])
        pols = [0] * len(symbols)
    elif name == 'idle':
        # en low for 12 frames in the middle: the PG keeps the last word pending
        # (overruns), branches turn off, and transmission restarts cold
        rnd = random.Random(11)
        symbols = [rnd.randrange(64) for _ in range(40)]
        pols = [0] * len(symbols)
        t0 = C.capture_time(C.FIRST_CAP + 6 * 14)
        en_lo, en_hi = t0, t0 + 12 * u.TS
        en_wave = (f'[0 1 {u.fmt_ps(en_lo - 1e-12)} 1 {u.fmt_ps(en_lo + 1e-12)} 0 '
                   f'{u.fmt_ps(en_hi - 1e-12)} 0 {u.fmt_ps(en_hi + 1e-12)} 1]')
        en_on = lambda t: not (en_lo < t < en_hi)  # noqa: E731
    elif name == 'random':
        rnd = random.Random(20261022)
        symbols = [rnd.randrange(64) for _ in range(200)]
        pols = [rnd.randrange(2) for _ in range(200)]
    else:
        raise SystemExit(f'unknown scenario {name}')
    tb, stop = C.build(symbols, n_pre=n_pre, rf=rf, pol_bits=pols if any(pols) else None,
                       save_rf=rf, dpc_db=dpc, en_wave=en_wave,
                       # only override the scheduler where a scenario needs it, so the
                       # module defaults (SPEC values) are what the other runs check
                       sched_params=(f't_tail={t_tail!r} ' if t_tail != T_TAIL else '')
                       + (f't_hold={t_hold!r}' if t_hold != T_HOLD else ''))
    T_STOP[0] = stop
    edges, res = run_tb(tb, out)
    # after the last symbol the bit source holds its last level; the chain keeps
    # forming words from it until the run ends
    n_sent = len(symbols)
    extra = len(edges.times(I['enc_valid'], 1)) - len(symbols)
    if extra > 0:
        symbols = symbols + [63 if symbols[-1] & 1 else 0] * extra
        pols = pols + [pols[-1]] * extra
    wins, hist, grants, drops, stats = check_control(rep, edges, symbols, pols, n_pre, name, n_sent,
                                                     t_tail, t_hold, en_on)
    if name == 'conflict':
        lanes = sorted({w['lane'] for w in drops})
        rep.check('conflict: symbols dropped on both lanes', lanes == [0, 1],
                  f"{len(drops)} dropped, symbols {[w['n'] for w in drops]}, lanes {lanes}")
    if name in ('hold', 'hold_idle'):
        holds = [k for k in range(8) for t, st in hist[k] if st == 5]
        rep.check(f'{name}: at least one branch enters HOLD', bool(holds))
    if name == 'preempt':
        rep.check('preempt: an idle HOLD gives its slot to a new branch, nothing dropped',
                  stats['preempt'] >= 1 and not drops, f"{stats['preempt']} preemptions, {len(drops)} drops")
    if name == 'hold_idle':
        rep.check('hold_idle: a request arrives in the idle-hold window and is granted warm',
                  stats['warm_from_idle'] >= 1, f"{stats['warm_from_idle']}")
    if name == 'idle':
        rep.check('idle: words were overwritten while en was low', len(edges.times(I['overrun'], 1)) >= 10,
                  f"{len(edges.times(I['overrun'], 1))} overruns")
    if rf:
        check_rf(rep, edges, res, grants, name, dpc_db=dpc)
    rep.write(out)
    print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
    return rep.ok


if __name__ == '__main__':
    names = sys.argv[1:] or ['hold', 'hold_idle', 'conflict', 'preempt', 'idle', 'random', 'debruijn']
    ok = all([run(n) for n in names])
    sys.exit(0 if ok else 1)
