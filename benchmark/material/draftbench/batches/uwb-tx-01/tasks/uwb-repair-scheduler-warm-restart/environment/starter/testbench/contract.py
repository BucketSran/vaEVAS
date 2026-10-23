"""Public contract for the transmit-chain repair task: bench netlist, stimuli,
expected edges and checks.

The bench wires the nine modules of /app/modules into the fixed transmit
chain (Spec C1). Expected edges and the expected RF output are computed here
from the Spec rules and the stimulus; the checker never reads a reference
model's waveform.
"""
from __future__ import annotations

import math
import random

import uwbtask as u

# ---------------------------------------------------------------- constants --
TS = 1 / 672e6                 # frame (symbol) period, master RO at code 288
DELTA = TS / 16                # tap spacing
T_BIT = TS / 6                 # bit-clock period (4.032 GHz)
EDGE = 2e-12                   # every logic edge, stimulus and modules
HALF = EDGE / 2                # a 2 ps edge crosses 0.5 V 1 ps after it starts
TOL = 2e-12                    # crossing-time tolerance (Spec C9)
CUT = 5e-12                    # edges in the last 5 ps of a run are not compared
FIRST_CAP = 5                  # first bit-clock edge after reset release
T_CQ, T_EV = 10e-12, 30e-12    # serial-to-symbol output delay, encoder strobe delay
N_WIDTH = 9                    # pulse width in taps
T_CONF = 200e-12               # conflict pulse width
CODE = 288
CARRIERS = [4.5e9 + k * 3e9 / 7 for k in range(8)]
TAU_RO = 200e-12 / math.log(100)
TAU_ENV = 50e-12 / math.log(100)
DF_START = 0.01
RF_TOL = 2e-3                  # outp - outn reconstruction limit, V
CARRIER_TOL = 0.02
QUIET = 1e-6                   # output limit outside pulses, V
TAIL_WIN = 300e-12             # pulse tail excluded from the quiet check
MARGIN = 5e-12                 # case design: minimum separation of distinct events
LATCH_MARGIN = 50e-12          # case design: enc_valid latch to frame edge (Spec C8)

MODULE_FILES = ('dppm_fsk_encoder8.va', 'envelope_lane.va', 'master_ro16.va', 'pulse_generator.va',
                'rf_ro_branch.va', 'ro_frequency_cal.va', 'ro_scheduler8.va', 'serial_to_symbol6.va',
                'tx_output.va')
# bench settings (Spec C1); module defaults are used where a case does not set them
BENCH = dict(n_pre=2, t_tail=150e-12, t_hold=200e-12, clk_delay=10e-12, dpc_db=(0.0,) * 8)
MODULE_DEFAULTS = dict(t_tail=150e-12, t_hold=200e-12)

IDS = dict(clk672=1, gate_a=2, gate_b=3, conflict=4, nsup1=5, nsup2=6, nsup3=7,
           **{f'pwr{k}': 10 + k for k in range(8)},
           **{f'pre{k}': 20 + k for k in range(8)},
           **{f'rel{k}': 30 + k for k in range(8)})
NSUP_LEVELS = {'nsup1': 0.5, 'nsup2': 1.5, 'nsup3': 2.5}


def gray(b):
    return b ^ (b >> 1)


def gray_to_bin(g):
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def words_for(seq):
    """6-bit words that make the encoder emit the absolute codewords (P, F)."""
    out, prev = [], 0
    for p, f in seq:
        out.append((gray((p - prev) % 8) << 3) | gray(f))
        prev = p
    return out


def bench(case):
    return {**BENCH, **case.get('bench', {})}


# ------------------------------------------------------------------ cases ----

HOLD_SEQ = [(1, 6), (7, 3), (0, 3), (3, 5), (6, 1), (0, 1), (5, 4), (4, 2), (0, 2), (6, 7),
            (3, 0), (0, 0), (5, 6), (2, 5), (0, 5), (1, 3)]
CONFLICT_SEQ = [(2, 0), (7, 1), (3, 2), (0, 3), (5, 4), (2, 5), (7, 6), (4, 7), (0, 0), (3, 1),
                (6, 2), (1, 3)]


def public_cases():
    # same-carrier pairs P = a -> 0 for a = 7 (touching), 6, 4 (held), 3, 2 (off,
    # cold restart), separated by other carriers; polarity bits and DPC gains
    hold = dict(name='hold', words=words_for(HOLD_SEQ),
                pols=[0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 1, 1, 0],
                bench=dict(dpc_db=(0.0, -1.0, 0.5, -2.0, 1.5, 0.0, -0.5, 1.0)),
                need=dict(warm=3, cold=10))
    # n_pre = 15: a request can find both supplies busy; the symbol is dropped
    conflict = dict(name='conflict', words=words_for(CONFLICT_SEQ), pols=[0] * len(CONFLICT_SEQ),
                    bench=dict(n_pre=15), need=dict(drops=2, drop_lanes=2))
    return [hold, conflict]


def random_case(name, seed, n, bench_over=None, need=None):
    rnd = random.Random(seed)
    words = [rnd.randrange(64) for _ in range(n)]
    pols = [rnd.randrange(2) for _ in range(n)]
    return dict(name=name, words=words, pols=pols, bench=bench_over or {}, need=need or {})


# ------------------------------------------------------------- timing rules --

def bit_cross(j, b):
    """0.5 V crossing of bit-clock rising edge j (j = 0 is the first edge)."""
    return b['clk_delay'] + j * T_BIT + HALF


def rst_release(b):
    return bit_cross(4, b) + T_BIT / 2


def latch_time(n, b):
    """Rising 0.5 V crossing of enc_valid for word n (Spec C2).

    sym_valid of word n falls t_cq after the capture of the third bit of word
    n + 1; the encoder takes the word at that crossing and raises enc_valid
    t_ev later.
    """
    return bit_cross(FIRST_CAP + 6 * n + 8, b) + T_CQ + HALF + T_EV + HALF


def stop_time(case):
    b = bench(case)
    return bit_cross(FIRST_CAP + 6 * len(case['words']), b) + 6 * TS


def all_words(case, stop):
    """Sent words plus the words the chain keeps forming from the held last bit."""
    b = bench(case)
    words, pols = list(case['words']), list(case['pols'])
    pad = 63 if words[-1] & 1 else 0
    out, p, n = [], 0, 0
    while True:
        tl = latch_time(n, b)
        if tl >= stop:
            return out
        w = words[n] if n < len(words) else pad
        q = pols[n] if n < len(pols) else pols[-1]
        p = (p + gray_to_bin(w >> 3)) % 8
        out.append(dict(n=n, word=w, P=p, F=gray_to_bin(w & 7), pol=q, latch=tl))
        n += 1


def frame_cross(m):
    return m * TS + HALF


def pg_windows(case, stop):
    """Lane windows (Spec C3). Times are tap-edge starts; actions follow at +2 ps."""
    b = bench(case)
    words = all_words(case, stop)
    wins, lane, j = [], 0, 0
    m = 1
    pend = None
    while frame_cross(m) < stop and (j < len(words) or pend is not None):
        while j < len(words) and words[j]['latch'] < frame_cross(m):
            pend = words[j]   # one word per frame in this bench; a newer word replaces it
            j += 1
        if pend is not None:
            s = (m + 1) * TS + pend['P'] * DELTA
            wins.append(dict(pend, lane=lane, p=s - b['n_pre'] * DELTA, s=s, e=s + N_WIDTH * DELTA))
            lane = 1 - lane
            pend = None
        m += 1
    return wins


# ------------------------------------------------------- scheduler replay ----

def scheduler_replay(wins, b):
    """Two supply slots (Spec C4) driven by the lane windows.

    Returns per-branch state histories [(t, state)] with t the scheduler action
    time (tap start + 2 ps, or the end of a timed interval), the per-slot count
    history, the granted and dropped windows and path statistics.
    """
    n_pre, t_tail, t_hold = b['n_pre'], b['t_tail'], b['t_hold']
    t_wait = max(0.0, t_hold - n_pre * DELTA)
    act = 2 * HALF
    events = []
    for w in wins:
        events += [(w['p'] + act, 1, 'req', w), (w['s'] + act, 2, 'start', w), (w['e'] + act, 0, 'end', w)]
    events.sort(key=lambda x: (x[0], x[1]))
    slots = [dict(br=-1, st=0, pend=0, nact=0, due=None) for _ in range(2)]
    lane_slot = {0: None, 1: None}
    hist = {k: [] for k in range(8)}
    count = [(0.0, 0)]
    grants, drops = [], []
    stats = dict(warm=0, warm_in_precharge=0, warm_from_idle=0, warm_slot1=0, warm_lane_b=0, cold=0,
                 preempt=0, preempt_two_idle=0, drops=0)
    deadlines, actions = [], []

    def set_state(i, st, t):
        sl = slots[i]
        if sl['br'] >= 0:
            hist[sl['br']].append((t, st))
        sl['st'] = st
        count.append((t, sum(1 for x in slots if x['st'] != 0)))

    def advance(t):
        """Process slot deadlines strictly before t, in time order."""
        while True:
            due = [(sl['due'], i) for i, sl in enumerate(slots)
                   if sl['due'] is not None and (sl['st'] == 4 or (sl['st'] == 5 and sl['pend'] == 0))]
            if not due:
                return
            td, i = min(due)
            if td >= t - 1e-15:
                return
            deadlines.append(td)
            sl = slots[i]
            if sl['st'] == 4:
                set_state(i, 5, td)
                if sl['pend'] == 0:
                    sl['due'] = td + t_wait
                    if t_wait <= 0:
                        set_state(i, 0, td)
                        sl['br'], sl['due'] = -1, None
                else:
                    sl['due'] = None
            else:
                set_state(i, 0, td)
                sl['br'], sl['due'] = -1, None

    for t, _, kind, w in events:
        advance(t)
        actions.append(t)
        if kind == 'req':
            k = w['F']
            hit = [i for i, sl in enumerate(slots) if sl['st'] != 0 and sl['br'] == k]
            free = [i for i, sl in enumerate(slots) if sl['st'] == 0]
            idle = [i for i, sl in enumerate(slots) if sl['st'] == 5 and sl['pend'] == 0]
            if hit:
                i = hit[0]
                stats['warm'] += 1
                stats['warm_in_precharge'] += slots[i]['st'] == 1
                stats['warm_slot1'] += i == 1
                stats['warm_lane_b'] += w['lane'] == 1
                if slots[i]['st'] == 5 and slots[i]['pend'] == 0:
                    stats['warm_from_idle'] += 1
                slots[i]['pend'] += 1
                if slots[i]['st'] == 5:
                    slots[i]['due'] = None
                lane_slot[w['lane']] = i
            elif free or idle:
                i = (free or idle)[0]
                stats['cold'] += 1
                if not free:
                    stats['preempt'] += 1
                    stats['preempt_two_idle'] += len(idle) == 2
                    set_state(i, 0, t)          # the idle hold gives up its slot
                slots[i].update(br=k, pend=1, nact=0, due=None)
                set_state(i, 1, t)
                lane_slot[w['lane']] = i
            else:
                lane_slot[w['lane']] = None
                stats['drops'] += 1
                drops.append(dict(w, t_req=t))
        elif kind == 'start':
            i = lane_slot[w['lane']]
            if i is not None:
                sl = slots[i]
                if sl['st'] != 3:
                    set_state(i, 3, t)
                sl['nact'] += 1
                sl['pend'] = max(0, sl['pend'] - 1)
                sl['due'] = None
                grants.append(dict(w, t_start=t))
        else:
            i = lane_slot[w['lane']]
            if i is not None:
                sl = slots[i]
                sl['nact'] -= 1
                if sl['nact'] <= 0:
                    sl['nact'] = 0
                    set_state(i, 4, t)
                    sl['due'] = t + t_tail
                for g in grants:
                    if g['n'] == w['n']:
                        g['t_end'] = t
            lane_slot[w['lane']] = None
    advance(math.inf)
    stats['drop_lanes'] = len({w['lane'] for w in drops})
    return dict(hist={k: settle(h) for k, h in hist.items()}, count=settle(count), grants=grants, drops=drops,
                stats=stats, deadlines=deadlines, actions=actions)


def settle(history):
    """Keep the last value at each instant: changes made in one evaluation are
    seen together, so a value left and re-entered at the same time is no edge."""
    out = []
    for t, v in history:
        if out and out[-1][0] == t:
            out.pop()
        if not out or out[-1][1] != v:
            out.append((t, v))
    return out


def level_edges(hist_k, pred):
    out, level = [], 0
    for t, st in hist_k:
        new = 1 if pred(st) else 0
        if new != level:
            out.append((t + HALF, new))
            level = new
    return out


def expected(case, stop):
    b = bench(case)
    wins = pg_windows(case, stop)
    rp = scheduler_replay(wins, b)
    exp = {}
    for k in range(8):
        h = rp['hist'][k]
        exp[f'pwr{k}'] = level_edges(h, lambda st: st != 0)
        exp[f'pre{k}'] = level_edges(h, lambda st: st == 1)
        exp[f'rel{k}'] = level_edges(h, lambda st: st >= 2)
    for ln, nm in ((0, 'gate_a'), (1, 'gate_b')):
        mine = [g for g in rp['grants'] if g['lane'] == ln]
        exp[nm] = sorted([(g['t_start'] + HALF, 1) for g in mine]
                         + [(g['t_end'] + HALF, 0) for g in mine if 't_end' in g])
    exp['conflict'] = sorted([(d['t_req'] + HALF, 1) for d in rp['drops']]
                             + [(d['t_req'] + T_CONF + HALF, 0) for d in rp['drops']])
    m, clk = 1, []
    while m * TS < stop:
        clk += [(m * TS + HALF, 1), (m * TS + TS / 2 + HALF, 0)]
        m += 1
    exp['clk672'] = [(0.5 * TS + HALF, 0)] + clk
    cnt = rp['count']
    for name, level in NSUP_LEVELS.items():
        lst = []
        for (_, c0), (t, c1) in zip(cnt, cnt[1:]):
            if min(c0, c1) < level < max(c0, c1):
                lst.append((t + EDGE * (level - c0) / (c1 - c0), 1 if c1 > c0 else 0))
        exp[name] = lst
    design = design_problems(case, rp, exp, stop)
    return dict(edges=exp, replay=rp, windows=wins, design=design)


def design_problems(case, rp, exp, stop):
    """Case-design guard: no timed interval may end within MARGIN of a lane
    action, no output may change twice within MARGIN, and every enc_valid
    latch stays LATCH_MARGIN away from a frame edge (Spec C8); otherwise
    simulator timing error could change the expected order."""
    bad = []
    b = bench(case)
    for w in all_words(case, stop):
        m = round((w['latch'] - HALF) / TS)
        if abs(w['latch'] - frame_cross(m)) < LATCH_MARGIN:
            bad.append(f"word {w['n']}: latch within {LATCH_MARGIN * 1e12:g} ps of a frame edge")
            break
    if not 1 <= b['n_pre'] <= 15:
        bad.append('n_pre outside 1..15')
    acts = sorted(rp['actions'])
    for td in rp['deadlines']:
        if any(abs(td - a) < MARGIN for a in acts):
            bad.append(f'deadline {td * 1e9:.4f} ns near a lane action')
    for name, lst in exp.items():
        ts = [t for t, _ in lst if t < stop]
        if any(t2 - t1 < MARGIN for t1, t2 in zip(ts, ts[1:])):
            bad.append(f'{name}: two edges within {MARGIN * 1e12:g} ps')
        if any(abs(t - (stop - CUT)) < MARGIN for t in ts):
            bad.append(f'{name}: an edge within {MARGIN * 1e12:g} ps of the comparison end')
    return bad


# --------------------------------------------------------------- netlist ----

def stimulus(case, stop):
    b = bench(case)
    bits = [(w >> (5 - k)) & 1 for w in case['words'] for k in range(6)]
    ch = [(0.0, bits[0])]
    for j in range(1, len(bits)):
        if bits[j] != bits[j - 1]:
            ch.append((bit_cross(FIRST_CAP + j, b) - T_BIT / 2, bits[j]))
    words = all_words(case, stop)
    pol = [(0.0, words[0]['pol'] if words else 0)]
    for a, c in zip(words, words[1:]):
        if c['pol'] != a['pol']:
            pol.append(((a['latch'] + c['latch']) / 2, c['pol']))
    return [
        '\n'.join(f'Vc{i} (c{i} 0) vsource dc={(CODE >> i) & 1}' for i in range(10)),
        f'Xbclk (bclk) uwb_clock_source period={T_BIT!r} delay={b["clk_delay"]!r} tr={EDGE!r}',
        f'Vrst (rst 0) vsource type=pwl wave={u.pwl_levels([(0.0, 1), (rst_release(b), 0)], EDGE)}',
        f'Vdin (din 0) vsource type=pwl wave={u.pwl_levels(ch, EDGE)}',
        'Ven (en 0) vsource dc=1',
        f'Vpol (pol 0) vsource type=pwl wave={u.pwl_levels(pol, EDGE)}' if len(pol) > 1
        else f'Vpol (pol 0) vsource dc={pol[0][1]}',
    ]


def chain(case):
    """The fixed transmit chain (Spec C1): one instance per module, connected by port order."""
    b = bench(case)
    taps = ' '.join(f'ph{k}' for k in range(15, -1, -1))
    code = ' '.join(f'c{i}' for i in range(9, -1, -1))

    def bus(name):
        return ' '.join(f'{name}{k}' for k in range(7, -1, -1))
    sch = f'n_pre={b["n_pre"]}'
    for key in ('t_tail', 't_hold'):
        if b[key] != MODULE_DEFAULTS[key]:
            sch += f' {key}={b[key]!r}'
    dpc = ' '.join(f'dpc_db{k}={v!r}' for k, v in enumerate(b['dpc_db']) if v != 0)
    lines = [
        'Xs2p (bclk din rst sym5 sym4 sym3 sym2 sym1 sym0 sym_valid) uwb_serial_to_symbol6',
        'Xenc (sym5 sym4 sym3 sym2 sym1 sym0 sym_valid rst p2 p1 p0 i2 i1 i0 f2 f1 f0 '
        'q7 q6 q5 q4 q3 q2 q1 q0 enc_valid) uwb_dppm_fsk_encoder8',
        f'Xro ({code} {taps}) uwb_master_ro16',
        f'Xpg ({taps} p2 p1 p0 f2 f1 f0 pol enc_valid en rst pre_a rf_a sa2 sa1 sa0 pol_a '
        f'pre_b rf_b sb2 sb1 sb0 pol_b overrun) uwb_pulse_generator n_pre={b["n_pre"]}',
        f'Xsch (pre_a rf_a sa2 sa1 sa0 pre_b rf_b sb2 sb1 sb0 rst {bus("pwr")} {bus("pre")} {bus("rel")} '
        f'gate_a gate_b conflict nsup {bus("st")}) uwb_ro_scheduler8 {sch}',
    ]
    lines += [f'Xbr{k} (pwr{k} pre{k} rel{k} vro{k}) uwb_rf_ro_branch f_rf={CARRIERS[k]!r}' for k in range(8)]
    lines += ['Xenva (gate_a ph0 env_a) uwb_envelope_lane', 'Xenvb (gate_b ph0 env_b) uwb_envelope_lane',
              (f'Xout ({bus("vro")} env_a env_b gate_a gate_b sa2 sa1 sa0 sb2 sb1 sb0 pol_a pol_b outp outn) '
               f'uwb_tx_output {dpc}').rstrip()]
    return lines


def netlist(case, module_files, tb_dir, stop):
    lines = ['simulator lang=spectre', 'global 0']
    lines += [f'ahdl_include "{f}"' for f in module_files]
    lines += [f'ahdl_include "{tb_dir / "clock_source.va"}"', f'ahdl_include "{tb_dir / "edge_monitor.va"}"']
    lines += stimulus(case, stop) + chain(case)
    nodes = dict(clk672='ph0', gate_a='gate_a', gate_b='gate_b', conflict='conflict',
                 nsup1='nsup', nsup2='nsup', nsup3='nsup',
                 **{f'{g}{k}': f'{g}{k}' for g in ('pwr', 'pre', 'rel') for k in range(8)})
    for name, ident in IDS.items():
        vth = NSUP_LEVELS.get(name, 0.5)
        lines.append(f'Xmon_{name} ({nodes[name]}) uwb_edge_monitor id={ident} vth={vth!r}')
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={stop!r} maxstep=10p', 'save outp outn']
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------ checks ---

def compare(rep, label, got, want, cut):
    got = [e for e in got if e[0] < cut]
    want = [e for e in want if e[0] < cut]
    n = min(len(got), len(want))
    worst = max((abs(a[0] - c[0]) for a, c in zip(got[:n], want[:n])), default=0.0)
    first = next((i for i, (a, c) in enumerate(zip(got, want)) if a[1] != c[1] or abs(a[0] - c[0]) > TOL),
                 None if len(got) == len(want) else n)
    ok = first is None
    where = '' if ok else (f'; first mismatch #{first}: got {_fmt(got, first)}, expected {_fmt(want, first)}')
    rep.add(label, f'{len(want)} edges, error <= {TOL * 1e12:g} ps',
            f'{len(got)} edges, worst {worst * 1e12:.3f} ps{where}', ok)
    return ok


def _fmt(lst, i):
    if i is None or i >= len(lst):
        return 'none'
    t, d = lst[i]
    return f"{'rise' if d else 'fall'} at {t * 1e9:.4f} ns"


def env_resp(uu, tw, tau):
    w = 2 * math.pi / tw
    ue = min(uu, tw)
    k = 1 / (1 + w * w * tau * tau)
    y = 0.5 * (1 - math.exp(-ue / tau)) - 0.5 * k * (math.cos(w * ue) + w * tau * math.sin(w * ue)
                                                      - math.exp(-ue / tau))
    if uu > tw:
        y *= math.exp(-(uu - tw) / tau)
    return y


def check_rf(rep, edges, rows, grants, b, cut):
    """outp - outn against the Spec C5/C6 formulas, using the observed release
    and gate crossings and the observed clk672 period."""
    t, vdiff = rows['time'], [p - q for p, q in zip(rows['outp'], rows['outn'])]
    osc = {k: [] for k in range(8)}
    for k in range(8):
        r = edges.by_id.get(IDS[f'rel{k}'], [])
        for (t1, d1), (t2, d2) in zip(r, r[1:]):
            if d1 == 1 and d2 == 0:
                osc[k].append((t1, t2))
        if r and r[-1][1] == 1:
            osc[k].append((r[-1][0], math.inf))
    clk = edges.times(IDS['clk672'], 1)
    gains = [10 ** (g / 20) for g in b['dpc_db']]

    def vro(k, ti):
        for a, c in osc[k]:
            if a < ti < c:
                uu = ti - a
                return (1 - math.exp(-uu / TAU_RO)) * math.cos(
                    2 * math.pi * CARRIERS[k] * (uu + DF_START * TAU_RO * (1 - math.exp(-uu / TAU_RO))))
        return 0.0

    gates = {0: edges.by_id.get(IDS['gate_a'], []), 1: edges.by_id.get(IDS['gate_b'], [])}
    pulses, missing = [], 0
    for g in grants:
        if g['t_start'] + HALF >= cut:
            continue
        lst = gates[g['lane']]
        tg = min((x for x, d in lst if d == 1 and abs(x - (g['t_start'] + HALF)) < 5e-12), default=None)
        te = min((x for x, d in lst if d == 0 and 't_end' in g and abs(x - (g['t_end'] + HALF)) < 5e-12),
                 default=math.inf)
        prev = [x for x in clk if x < (tg if tg is not None else -1)]
        if tg is None or len(prev) < 2:
            missing += 1
            continue
        pulses.append((tg, te, N_WIDTH * (prev[-1] - prev[-2]) / 16, g['F'], g['pol']))
    pulses.sort()
    err, worst_t, first = 0.0, 0.0, 0
    for ti, vi in zip(t, vdiff):
        ex = 0.0
        while first < len(pulses) and pulses[first][1] + 400e-12 < ti:
            first += 1
        for tg, te, tw, k, pol in pulses[first:]:
            if tg >= ti:
                break
            if ti < te + 400e-12:
                e = env_resp(ti - tg, tw, TAU_ENV) if ti < te else \
                    env_resp(te - tg, tw, TAU_ENV) * math.exp(-(ti - te) / TAU_ENV)
                ex += (-1 if pol else 1) * gains[k] * e * vro(k, ti)
        d = abs(vi - ex)
        if not d <= err:            # also catches NaN
            err, worst_t = d, ti
    rep.add('outp - outn equals the reconstruction from release, gate, carrier, envelope, polarity '
            'and DPC rules (C5, C6)', f'max abs. error < {RF_TOL * 1e3:g} mV at all {len(t)} saved points, '
            'every granted pulse located',
            f'max {err * 1e3:.3g} mV at {worst_t * 1e9:.4f} ns over {len(pulses)} pulses; '
            f'{missing} granted pulses without a gate edge',
            err < RF_TOL and missing == 0)
    bad, n_full = [], 0
    for tg, te, tw, k, pol in pulses:
        if tg + 0.75 * tw >= cut:
            continue                # the middle half of this pulse is not inside the run
        n_full += 1
        zc = [t[i] + (t[i + 1] - t[i]) * vdiff[i] / (vdiff[i] - vdiff[i + 1])
              for i in range(len(t) - 1)
              if tg + 0.25 * tw < t[i] < tg + 0.75 * tw and vdiff[i] * vdiff[i + 1] < 0]
        f_est = (len(zc) - 1) / 2 / (zc[-1] - zc[0]) if len(zc) >= 3 else 0.0
        if abs(f_est / CARRIERS[k] - 1) > CARRIER_TOL:
            bad.append((round(tg * 1e9, 3), k, round(f_est / 1e9, 3)))
    rep.add('each granted pulse carries the carrier of its branch (C5)',
            f'{n_full} pulses whose middle half lies in the run, abs(f/f_k - 1) <= {CARRIER_TOL:g} there',
            f'{len(bad)} off; first {bad[:2]}', not bad)
    vmax, first = 0.0, 0
    for ti, v in zip(t, vdiff):
        while first < len(pulses) and pulses[first][1] + TAIL_WIN <= ti:
            first += 1
        near = False
        for tg, te, *_ in pulses[first:]:
            if tg - 2e-12 >= ti:
                break
            near = near or ti < te + TAIL_WIN
        if not near:
            vmax = max(vmax, abs(v)) if v == v else math.inf
    rep.add('no output outside granted pulses and their 300 ps tails (C6)', f'abs(outp - outn) < {QUIET:g} V',
            f'max {vmax:.3g} V', vmax < QUIET)


def check(case, edges, rows, stop):
    b = bench(case)
    ex = expected(case, stop)
    rep = u.Report(case['name'])
    st = ex['replay']['stats']
    need = case.get('need', {})
    rep.add('case design: scheduler paths exercised by the expected sequence (C4)',
            ', '.join(f'{k} >= {v}' for k, v in need.items()) or 'record only',
            ', '.join(f'{k}={v}' for k, v in st.items()) + (f"; design issues {ex['design']}" if ex['design'] else ''),
            all(st.get(k, 0) >= v for k, v in need.items()) and not ex['design'])
    cut = stop - CUT
    e = ex['edges']
    compare(rep, 'clk672 frame clock edges (C3)', edges.by_id.get(IDS['clk672'], []), e['clk672'], cut)
    for k in range(8):
        for g, rule in (('pwr', 'supply'), ('pre', 'precharge'), ('rel', 'release')):
            compare(rep, f'branch {k} {g} edges ({rule}; C4, C7)', edges.by_id.get(IDS[f'{g}{k}'], []),
                    e[f'{g}{k}'], cut)
    compare(rep, 'gate_a edges: one window per granted lane-a pulse (C4, C7)',
            edges.by_id.get(IDS['gate_a'], []), e['gate_a'], cut)
    compare(rep, 'gate_b edges: one window per granted lane-b pulse (C4, C7)',
            edges.by_id.get(IDS['gate_b'], []), e['gate_b'], cut)
    compare(rep, 'conflict pulses at dropped requests (C4, C7)', edges.by_id.get(IDS['conflict'], []),
            e['conflict'], cut)
    for name, level in NSUP_LEVELS.items():
        compare(rep, f'nsup crossings of {level:g} V: powered-branch count (C4)', edges.by_id.get(IDS[name], []),
                e[name], cut)
    pw = sorted((t, d) for k in range(8) for t, d in edges.by_id.get(IDS[f'pwr{k}'], []))
    n, worst = 0, 0
    for _, d in pw:
        n += 1 if d else -1
        worst = max(worst, n)
    rep.add('never more than two branches powered, from the observed pwr edges (C4)', '<= 2', f'max {worst}',
            worst <= 2)
    check_rf(rep, edges, rows, ex['replay']['grants'], b, cut)
    return rep
