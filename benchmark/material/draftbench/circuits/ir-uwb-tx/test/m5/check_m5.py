"""M5 checks: launch lead, non-ideal terms, isolation and export (SPEC.md 4.10).

Each scenario runs the seed chain (test/m4_chain/chain_tb.py) with export
records on and checks the new behavior from observed edges, waveforms and the
exported random draws. Expected values come from the SPEC rules evaluated
here: the lane windows are replayed from the observed tap edges and the
exported draws, the scheduler is replayed from the observed lane edges, and
outp - outn is rebuilt from the branch formula with the exported activation
and phase-noise values. Statistics of the draws are checked against their
configured sigma with 99.9 % bounds.

Scenarios
  lead        n_lead = 5: release 5 taps before the RF window (RELEASE_SETTLE)
  static      common offset 25 MHz, device residuals 10 MHz / 0.5 dB
  activation  per-activation offset 5 MHz and uniform random start phase
  phase_noise phase diffusion 5 deg per 1 ns on a 50 ps grid
  timing      symbol jitter 5 ps, position and width errors 2 ps
  tap_skew    static master-RO tap skew 3 ps
  isolation   branch isolation 40 dB
  export      export records -> CSV and power accounting (tools/uwb_export.py)
  combined    all of the above at the original spec's main values, n_lead = 2,
              plus a receiver-style decode of the RF output

Usage: python3 check_m5.py [scenario ...]
"""
import csv
import math
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'm4_chain'), str(HERE.parent / 'lib')]
import chain_tb as C  # noqa: E402
import check_chain as K  # noqa: E402
import uwbtest as u  # noqa: E402

TOL = 2e-12
I = C.IDS
DELTA0 = u.DELTA0
TAU_A = TAU_F = 200e-12 / math.log(100)
TAU_E = 50e-12 / math.log(100)
DF_START = 0.01
Z = 3.29                      # two-sided 99.9 % normal quantile
DEG = math.pi / 180

# the original spec's main values (SPEC.md 4.10)
MAIN_BR = dict(f_off=25e6, sigma_f_res=10e6, sigma_g_res_db=0.5, sigma_f_act=5e6, phi_random=1,
               sigma_pn_1ns=5 * DEG, t_pn_grid=50e-12)
MAIN_PG = dict(sigma_jit=5e-12, sigma_pos=2e-12, sigma_wid=2e-12)

HOLD_SEQ = [(1, 6), (7, 3), (0, 3), (3, 5), (6, 1), (0, 1), (5, 4), (4, 2), (0, 2), (6, 7),
            (3, 0), (0, 0), (5, 6), (2, 5), (0, 5), (1, 3)]


# ------------------------------------------------------------------ running ---

def run(name, symbols, pols=None, **kw):
    out = u.out_dir_for(f'm5_{name}')
    out.mkdir(parents=True, exist_ok=True)
    tb, stop = C.build(symbols, pol_bits=pols if pols and any(pols) else None, save_rf=True, export=1, **kw)
    (out / 'tb.scs').write_text(tb)
    res = u.run_evas(out / 'tb.scs', out)
    edges = u.parse_edges(res)
    edges.drop_startup()
    recs = {}
    for line in res['records']:
        p = line.split()
        if p and p[0] != 'EDGE':
            recs.setdefault(p[0], []).append([float(x) for x in p[1:]])
    rows = list(csv.DictReader(open(res['tran'])))
    wave = {k: [float(r[k]) for r in rows] for k in rows[0]}
    return dict(out=out, edges=edges, recs=recs, wave=wave, stop=stop)


def bounds_mean(xs, sigma):
    m = sum(xs) / len(xs)
    lim = Z * sigma / math.sqrt(len(xs))
    return m, lim, abs(m) <= lim


def bounds_std(xs, sigma):
    n = len(xs)
    m = sum(xs) / n
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    half = Z / math.sqrt(2 * (n - 1))
    return s, (sigma * (1 - half), sigma * (1 + half)), sigma * (1 - half) <= s <= sigma * (1 + half)


# ------------------------------------------------------------ PG windows ----

def taps_sorted(edges):
    return sorted(t for k in range(16) for t in edges.times(I[f'ph{k}'], 1))


def lane_edges(edges, lane):
    nm = 'ab'[lane]
    return (edges.times(I[f'pre_{nm}'], 1), edges.times(I[f'pre_{nm}'], 0),
            edges.times(I[f'rf_{nm}'], 1), edges.times(I[f'rf_{nm}'], 0))


def check_pg_edges(rep, label, sim, n_pre, n_lead, n_width=9):
    """Lane edges = tap edges (counted from the scheduling ph0 edge) + latency + draws."""
    edges, pgs = sim['edges'], sim['recs'].get('PGS', [])
    taps = taps_sorted(edges)
    ph0 = edges.times(I['ph0'], 1)
    exp = {0: ([], [], [], []), 1: ([], [], [], [])}
    for r in pgs:
        t_s, lane, P = r[0], int(r[2]), int(r[3])
        j, ep, ew, lat = r[9], r[10], r[11], r[12]
        rep_ok = (int(r[6]) == 16 + P and int(r[7]) == 16 + P + n_width and int(r[8]) == 16 + P - n_lead - n_pre)
        if not rep_ok:
            rep.add(f'{label}: PGS record offsets follow 16+P, +n_width, -n_lead-n_pre', '', str(r), False)
        f0 = min((x for x in ph0 if abs(x - t_s) < 3e-12), default=None)
        if f0 is None:
            continue
        idx = [i for i, t in enumerate(taps) if t > f0 + 1e-13]

        def tap(n):
            return taps[idx[n - 1]] if 0 < n <= len(idx) else math.inf

        s = 16 + P
        hop = 1e-12          # PG output edge crosses 1 ps after it starts
        e = exp[lane]
        e[0].append(tap(s - n_lead - n_pre) + lat + j + hop)
        e[1].append(tap(s - n_lead) + lat + j + hop)
        e[2].append(tap(s) + lat + j + ep + hop)
        e[3].append(tap(s + n_width) + lat + j + ep + ew + hop)
    lim = sim['stop'] - 5e-12
    for lane in (0, 1):
        got = lane_edges(edges, lane)
        for name, g, x in zip(('pre rise', 'pre fall (release)', 'rf rise', 'rf fall'), got, exp[lane]):
            x = [t for t in x if t < lim]
            g = [t for t in g if t < lim]
            rep.times_match(f"{label}: lane {'ab'[lane]} {name} = tap + latency + draws", g, x, TOL)


def windows_from_lanes(sim):
    """Scheduled pulses with their observed lane edge times (PGS order per lane)."""
    edges, pgs = sim['edges'], sim['recs'].get('PGS', [])
    wins = []
    for lane in (0, 1):
        pr, pf, rr, rf = lane_edges(edges, lane)
        mine = [r for r in pgs if int(r[2]) == lane]
        for i, r in enumerate(mine):
            if i >= len(pr):
                break
            g = lambda lst: lst[i] if i < len(lst) else math.inf  # noqa: E731
            wins.append(dict(n=int(r[1]), lane=lane, P=int(r[3]), F=int(r[4]), pol=int(r[5]),
                             p=g(pr), r=g(pf), s=g(rr), e=g(rf)))
    return sorted(wins, key=lambda w: w['p'])


def scheduler_replay(wins, n_pre, t_tail=K.T_TAIL, t_hold=K.T_HOLD):
    """check_chain's two-slot replay with a release event at the falling pre edge."""
    t_wait = max(0.0, t_hold - n_pre * DELTA0)
    events = []
    for w in wins:
        events += [(w['p'], 1, 'req', w), (w['r'], 1.5, 'release', w), (w['s'], 2, 'start', w),
                   (w['e'], 0, 'end', w)]
    events.sort(key=lambda x: (x[0], x[1]))
    slots = [dict(br=-1, st=0, pend=0, nact=0, due=None) for _ in range(2)]
    lane_slot = {0: None, 1: None}
    hist = {k: [] for k in range(8)}
    drops, grants = [], []

    def set_state(i, st, t):
        if slots[i]['br'] >= 0:
            hist[slots[i]['br']].append((t, st))
        slots[i]['st'] = st

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
        if math.isinf(t):
            continue
        advance(t)
        i = lane_slot[w['lane']]
        if kind == 'req':
            k = w['F']
            hit = [j for j, sl in enumerate(slots) if sl['st'] != 0 and sl['br'] == k]
            free = [j for j, sl in enumerate(slots) if sl['st'] == 0]
            idle = [j for j, sl in enumerate(slots) if sl['st'] == 5 and sl['pend'] == 0]
            if hit:
                j = hit[0]
                slots[j]['pend'] += 1; lane_slot[w['lane']] = j
                if slots[j]['st'] == 5:
                    slots[j]['due'] = None
            elif free or idle:
                j = (free or idle)[0]
                if slots[j]['br'] >= 0:
                    set_state(j, 0, t)
                slots[j].update(br=k, pend=1, nact=0, due=None)
                set_state(j, 1, t)
                lane_slot[w['lane']] = j
            else:
                lane_slot[w['lane']] = None
                drops.append(w)
        elif kind == 'release':
            if i is not None and slots[i]['st'] == 1:
                set_state(i, 2, t)
        elif kind == 'start':
            if i is not None:
                sl = slots[i]
                if sl['st'] != 3:
                    set_state(i, 3, t)
                sl['nact'] += 1; sl['pend'] = max(0, sl['pend'] - 1); sl['due'] = None
                grants.append(w)
        else:
            if i is not None:
                sl = slots[i]
                sl['nact'] -= 1
                if sl['nact'] <= 0:
                    sl['nact'] = 0
                    set_state(i, 4, t)
                    sl['due'] = t + t_tail
            lane_slot[w['lane']] = None
    advance(1.0)
    return hist, grants, drops


def check_scheduler(rep, label, sim, wins, n_pre):
    """Scheduler outputs follow the replay; they cross 1 ps after the lane edge crossing."""
    edges = sim['edges']
    hist, grants, drops = scheduler_replay(wins, n_pre)
    hop = 1e-12
    lim = sim['stop'] - 5e-12

    def lv(h, pred):
        out, level = [], 0
        for t, st in h:
            new = 1 if pred(st) else 0
            if new != level:
                out.append((t + hop, new))
                level = new
        return out

    def cmp(name, got, exp):
        got = [e for e in got if e[0] < lim]
        exp = [e for e in exp if e[0] < lim]
        ok = len(got) == len(exp) and all(a[1] == b[1] and abs(a[0] - b[0]) <= TOL for a, b in zip(got, exp))
        worst = max((abs(a[0] - b[0]) for a, b in zip(got, exp)), default=0.0)
        rep.add(f'{label}: {name}', f'{len(exp)} edges, |error| <= {TOL*1e12:g} ps',
                f'{len(got)} edges, worst {worst*1e12:.3f} ps', ok)

    bad = []
    for k in range(8):
        for nm, pred in (('pwr', lambda s: s != 0), ('pre', lambda s: s == 1), ('rel', lambda s: s >= 2)):
            got = [e for e in edges.by_id.get(I[f'{nm}{k}'], []) if e[0] < lim]
            exp = [e for e in lv(hist[k], pred) if e[0] < lim]
            if not (len(got) == len(exp) and all(a[1] == b[1] and abs(a[0] - b[0]) <= TOL
                                                for a, b in zip(got, exp))):
                bad.append(f'{nm}{k}')
    rep.add(f'{label}: branch pwr/pre/rel edges follow the scheduler replay (release at falling pre)',
            '24 signals', f'mismatched {bad}' if bad else 'all match', not bad)
    for lane in (0, 1):
        mine = [w for w in grants if w['lane'] == lane]
        exp = sorted([(w['s'] + hop, 1) for w in mine] + [(w['e'] + hop, 0) for w in mine])
        cmp(f"gate_{'ab'[lane]} follows granted windows", edges.by_id.get(I[f"gate_{'ab'[lane]}"], []), exp)
    return hist, grants, drops


# ------------------------------------------------------------- RF rebuild ---

def activations(sim):
    """Per branch: list of (t_rel, t_stop, f_act, a_dev, phi_act, pn list)."""
    edges, recs = sim['edges'], sim['recs']
    pn = {}
    for r in recs.get('PN', []):
        pn.setdefault((int(r[1]), int(r[2])), []).append((r[0], r[3], r[4]))
    acts = {k: [] for k in range(8)}
    for r in recs.get('ACT', []):
        t_rel, k, n = r[0], int(r[1]), int(r[2])
        stops = [t for t in edges.times(I[f'rel{k}'], 0) + edges.times(I[f'pwr{k}'], 0) if t > t_rel + 1e-12]
        acts[k].append(dict(t_rel=t_rel, t_stop=min(stops, default=math.inf), f=r[3], a=r[4], phi=r[5],
                            f_dev=r[6], g_db=r[7], n=n, pn=sorted(pn.get((k, n), []))))
    return acts


def vro(act_list, t, grid):
    for a in act_list:
        if a['t_rel'] < t < a['t_stop']:
            uu = t - a['t_rel']
            amp = a['a'] * (1 - math.exp(-uu / TAU_A))
            ph = a['phi'] + 2 * math.pi * a['f'] * (uu + DF_START * TAU_F * (1 - math.exp(-uu / TAU_F)))
            for tk, base, inc in reversed(a['pn']):
                if tk <= t:
                    ph += base + inc * (t - tk) / grid
                    break
            return amp * math.cos(ph)
    return 0.0


def rebuild(rep, label, sim, grants, *, iso_db=None, grid=50e-12, g_pa=1.0, limit=2e-3, skip=None):
    """Compare outp - outn with the SPEC reconstruction at every saved point."""
    edges, w = sim['edges'], sim['wave']
    acts = activations(sim)
    ph0 = edges.times(I['ph0'], 1)
    leak = 10 ** (-iso_db / 20) if iso_db is not None else 0.0
    pulses = []                                  # lane, branch, pol, gate on, gate off, tw
    gate_edges = []
    for lane in (0, 1):
        g = edges.by_id.get(I[f"gate_{'ab'[lane]}"], [])
        on = [t for t, d in g if d == 1]
        off = [t for t, d in g if d == 0]
        gate_edges += [t for t, _ in g]
        mine = [x for x in grants if x['lane'] == lane]
        for t_on in on:
            wsel = min(mine, key=lambda x: abs(x['s'] + 1e-12 - t_on), default=None)
            if wsel is None or abs(wsel['s'] + 1e-12 - t_on) > 3e-12:
                rep.add(f'{label}: every gate matches a granted window', '', f'gate at {t_on}', False)
                continue
            t_off = min((t for t in off if t > t_on), default=math.inf)
            prev = [x for x in ph0 if x < t_on]
            tw = 9 * (prev[-1] - prev[-2]) / 16
            pulses.append((lane, wsel['F'], wsel['pol'], t_on, t_off, tw))
    # a branch stops abruptly when rel or pwr falls; with leakage that step
    # reaches the output, so points within 2 ps of those crossings are skipped
    stop_edges = [t for k in range(8) for t in edges.times(I[f'rel{k}'], 0) + edges.times(I[f'pwr{k}'], 0)]
    t, vd = w['time'], [p - n for p, n in zip(w['outp'], w['outn'])]
    err, worst_t, n = 0.0, 0.0, 0
    for ti, vi in zip(t, vd):
        if skip and skip(ti):
            continue
        if leak and any(abs(ti - ge) < 2e-12 for ge in gate_edges + stop_edges):
            continue                 # the leakage term switches at these crossings
        exp = 0.0
        closed = set()
        for lane, k, pol, tg, te, tw in pulses:
            if tg - 1e-12 < ti < te + 400e-12:
                if ti < te:
                    e = K.env_resp(ti - tg, tw, TAU_E)
                    closed.add(k)
                else:
                    e = K.env_resp(te - tg, tw, TAU_E) * math.exp(-(ti - te) / TAU_E)
                exp += (-1 if pol else 1) * e * vro(acts[k], ti, grid)
        if leak:
            exp += leak * sum(vro(acts[k], ti, grid) for k in range(8) if k not in closed)
        exp *= g_pa
        d = abs(vi - exp)
        if d > err:
            err, worst_t = d, ti
        n += 1
    rep.add(f'{label}: outp - outn equals the reconstruction from the exported draws',
            f'|error| <= {limit} V', f'{err:.2e} V at {worst_t*1e9:.4f} ns over {n} points', err <= limit)
    return acts, pulses


# ------------------------------------------------------------- scenarios ---

def random_symbols(seed, n):
    rnd = random.Random(seed)
    return [rnd.randrange(64) for _ in range(n)], [rnd.randrange(2) for _ in range(n)]


def common(rep, label, sim, n_pre=2, n_lead=0, iso_db=None):
    check_pg_edges(rep, label, sim, n_pre, n_lead)
    wins = windows_from_lanes(sim)
    hist, grants, drops = check_scheduler(rep, label, sim, wins, n_pre)
    pwr = sorted((t, d) for k in range(8) for t, d in sim['edges'].by_id.get(I[f'pwr{k}'], []))
    n = worst = 0
    for _t, d in pwr:
        n += 1 if d else -1
        worst = max(worst, n)
    rep.add(f'{label}: never more than 2 branches powered', '<= 2', str(worst), worst <= 2)
    acts, pulses = rebuild(rep, label, sim, grants, iso_db=iso_db)
    return wins, hist, grants, drops, acts, pulses


def sc_lead(rep):
    syms = u.symbols_for_codewords([8 * p + f for p, f in HOLD_SEQ])
    sim = run('lead', syms, pg=dict(n_lead=5))
    wins, hist, grants, drops, acts, pulses = common(rep, 'lead', sim, n_lead=5)
    settle = [h for k in range(8) for h in hist[k] if h[1] == 2]
    rep.add('lead: cold starts pass through RELEASE_SETTLE', '>= 1', str(len(settle)), len(settle) >= 1)
    # release precedes the RF window by n_lead taps: amplitude settled at window start
    frac = []
    for lane, k, pol, tg, te, tw in pulses:
        a = [x for x in acts[k] if x['t_rel'] < tg < x['t_stop']]
        if a:
            frac.append(1 - math.exp(-(tg - a[0]['t_rel']) / TAU_A))
    rep.add('lead: branch amplitude at the RF window start (cold starts, 5 taps lead)',
            '>= 1 - exp(-5 delta0 / tau_a) = 0.99998',
            f'min {min(frac):.5f} over {len(frac)} pulses', min(frac) >= 1 - math.exp(-5 * DELTA0 / TAU_A) - 1e-6)


def sc_static(rep):
    syms, pols = random_symbols(5, 60)
    sim = run('static', syms, pols, br=dict(f_off=25e6, sigma_f_res=10e6, sigma_g_res_db=0.5))
    wins, hist, grants, drops, acts, pulses = common(rep, 'static', sim)
    bad = []
    res = {}
    for k in range(8):
        for a in acts[k]:
            fres = a['f_dev'] - u.CARRIERS[k] - 25e6
            res.setdefault(k, set()).add((round(fres, 3), round(a['g_db'], 9)))
            if abs(a['f'] - a['f_dev']) > 1e-3 or abs(a['a'] - 10 ** (a['g_db'] / 20)) > 1e-12:
                bad.append(k)
    rep.add('static: f_act = f_k + f_off + f_res and a_dev = 10^(g_res/20), no activation offset',
            'every activation', f'bad branches {sorted(set(bad))}', not bad)
    fixed = all(len(v) == 1 for v in res.values())
    rep.add('static: each device keeps one residual pair over all its activations', 'one per branch',
            str({k: len(v) for k, v in res.items()}), fixed and len(res) >= 6)
    vals = [next(iter(v))[0] for v in res.values()]
    rep.add('static: residuals differ between devices and stay within 4 sigma', '|f_res| <= 40 MHz, distinct',
            f'{[round(x/1e6, 2) for x in vals]} MHz', len(set(vals)) == len(vals) and max(map(abs, vals)) <= 40e6)


def sc_activation(rep):
    syms, pols = random_symbols(7, 160)
    sim = run('activation', syms, pols, br=dict(sigma_f_act=5e6, phi_random=1))
    wins, hist, grants, drops, acts, pulses = common(rep, 'activation', sim)
    allacts = [a for k in range(8) for a in acts[k]]
    df = [a['f'] - a['f_dev'] for a in allacts]
    m, lim, ok = bounds_mean(df, 5e6)
    rep.add('activation: mean of the frequency draws', f'|mean| <= {lim/1e6:.2f} MHz (99.9 %)', f'{m/1e6:.3f} MHz', ok)
    s, (lo, hi), ok = bounds_std(df, 5e6)
    rep.add('activation: std of the frequency draws', f'{lo/1e6:.2f}..{hi/1e6:.2f} MHz', f'{s/1e6:.3f} MHz', ok)
    ph = [a['phi'] for a in allacts]
    R = math.hypot(sum(math.cos(x) for x in ph), sum(math.sin(x) for x in ph)) / len(ph)
    p = math.exp(-len(ph) * R * R)                 # Rayleigh test
    rep.add('activation: start phases uniform (Rayleigh test)', 'p >= 0.001', f'R {R:.3f}, p {p:.3g}, n {len(ph)}',
            p >= 1e-3 and min(ph) >= 0 and max(ph) < 2 * math.pi)
    rel_rises = sum(len(sim['edges'].times(I[f'rel{k}'], 1)) for k in range(8))
    rep.add('activation: one draw per cold start; held branches keep their draw',
            'ACT records = rel rising edges', f'{len(allacts)} vs {rel_rises}', len(allacts) == rel_rises)


def sc_phase_noise(rep):
    syms, pols = random_symbols(9, 80)
    sig = 5 * DEG
    sim = run('phase_noise', syms, pols, br=dict(sigma_pn_1ns=sig, t_pn_grid=50e-12))
    wins, hist, grants, drops, acts, pulses = common(rep, 'phase_noise', sim)
    inc = [r[4] for r in sim['recs'].get('PN', [])]
    step = sig * math.sqrt(50e-12 / 1e-9)
    s, (lo, hi), ok = bounds_std(inc, step)
    rep.add('phase_noise: increments per 50 ps grid step', f'std {lo/DEG:.3f}..{hi/DEG:.3f} deg',
            f'{s/DEG:.3f} deg over {len(inc)} steps', ok)
    grid_ok = all(abs(r[0] / 50e-12 - round(r[0] / 50e-12)) < 1e-6 for r in sim['recs'].get('PN', []))
    rep.add('phase_noise: grid points sit on the fixed time grid k * 50 ps', 'all', str(grid_ok), grid_ok)


def sc_timing(rep):
    syms, pols = random_symbols(11, 160)
    sim = run('timing', syms, pols, pg=dict(MAIN_PG))
    wins, hist, grants, drops, acts, pulses = common(rep, 'timing', sim)
    pgs = sim['recs'].get('PGS', [])
    for col, name, sig in ((9, 'symbol jitter', 5e-12), (10, 'position error', 2e-12), (11, 'width error', 2e-12)):
        xs = [r[col] for r in pgs]
        s, (lo, hi), ok = bounds_std(xs, sig)
        clip = max(map(abs, xs)) <= 4 * sig + 1e-18
        rep.add(f'timing: {name} draws', f'std {lo*1e12:.2f}..{hi*1e12:.2f} ps, |x| <= 4 sigma',
                f'{s*1e12:.3f} ps over {len(xs)}', ok and clip)
    lat = {round(r[12], 18) for r in pgs}
    rep.add('timing: common latency = 4 (sigma_jit + sigma_pos + sigma_wid) = 36 ps', '36 ps',
            str([x * 1e12 for x in lat]), lat == {round(36e-12, 18)})


def sc_tap_skew(rep):
    syms = u.symbols_for_codewords([8 * p + f for p, f in HOLD_SEQ])
    sim = run('tap_skew', syms, ro=dict(sigma_tap=3e-12))
    tap = sim['recs'].get('TAP', [])
    rep.add('tap_skew: one TAP record', '1', str(len(tap)), len(tap) == 1)
    lat, sk = tap[0][1], tap[0][2:18]
    # undo the reported skews: the taps must then form a uniform delta grid
    worst = 0.0
    ph = [sim['edges'].times(I[f'ph{k}'], 1) for k in range(16)]
    nfr = min(len(x) for x in ph) - 1
    for i in range(1, nfr):
        base = ph[0][i] - sk[0]
        delta = (ph[0][i + 1] - ph[0][i]) / 16
        for k in range(16):
            tk = min((t for t in ph[k] if t > ph[0][i] - 20e-12), default=None)
            worst = max(worst, abs(tk - sk[k] - base - k * delta))
    rep.add('tap_skew: tap k edges = uniform grid + common latency + reported skew_k', f'|error| <= {TOL*1e12:g} ps',
            f'worst {worst*1e12:.3f} ps', worst <= TOL)
    s = math.sqrt(sum(x * x for x in sk) / 16)
    rep.add('tap_skew: reported skews', '|skew| <= 12 ps, latency 12 ps',
            f'rms {s*1e12:.2f} ps, latency {lat*1e12:.1f} ps', max(map(abs, sk)) <= 12e-12 and abs(lat - 12e-12) < 1e-18)
    common(rep, 'tap_skew', sim)


def sc_isolation(rep):
    syms = u.symbols_for_codewords([8 * p + f for p, f in HOLD_SEQ])
    sim = run('isolation', syms, out=dict(iso_db=40))
    wins, hist, grants, drops, acts, pulses = common(rep, 'isolation', sim, iso_db=40)
    # direct observation: a held branch with no gate leaks at 1 %
    held = []
    for k in range(8):
        for (t0, s0), (t1, _s1) in zip(hist[k], hist[k][1:]):
            if s0 == 5 and t1 - t0 > 10e-12:
                held.append((t0 + 2e-12, t1))
    t, vd = sim['wave']['time'], [p - n for p, n in zip(sim['wave']['outp'], sim['wave']['outn'])]
    gates = [(a, b) for lane, k, pol, a, b, tw in pulses]
    peak = 0.0
    for a, b in held:
        for ti, vi in zip(t, vd):
            if a < ti < b - 2e-12 and all(not (g0 - 1e-12 < ti < g1 + 152e-12) for g0, g1 in gates):
                peak = max(peak, abs(vi))
    rep.add('isolation: output during an idle HOLD with no gate open', 'peak <= 0.01 V and > 0',
            f'{peak:.4f} V over {len(held)} holds', 0 < peak <= 0.0101 if held else False)


def sc_export(rep):
    syms, pols = random_symbols(13, 60)
    sim = run('export', syms, pols, pg=dict(n_lead=2))
    wins, hist, grants, drops, acts, pulses = common(rep, 'export', sim, n_lead=2)
    log = sim['out'] / 'sim' / 'strobe.txt'
    out = sim['out'] / 'export'
    tool = HERE.parent.parent / 'tools' / 'uwb_export.py'
    t0, t1 = 3e-9, sim['stop'] - 2e-9
    p = subprocess.run([sys.executable, str(tool), str(log), str(out), '--params', str(tool.parent / 'power_params.json'),
                        '--t0', repr(t0), '--t1', repr(t1), '--models', str(HERE.parent.parent / 'module')],
                       capture_output=True, text=True)
    rep.add('export: tool runs', 'exit 0', str(p.returncode), p.returncode == 0)
    rows = lambda f: list(csv.DictReader(open(out / f)))  # noqa: E731
    sy = rows('symbols.csv')
    cws = K.codewords(syms)
    ok = all((int(r['P']), int(r['F'])) == cws[i] for i, r in enumerate(sy[:len(syms)]))
    rep.add('export: symbols.csv holds every sent word with its P and F', f'{len(syms)} words', f'{len(sy)} rows', ok)
    bs = rows('branch_states.csv')
    STATES = ['OFF', 'PRECHARGE', 'RELEASE_SETTLE', 'ACTIVE', 'TAIL', 'HOLD']
    bad = 0
    for k in range(8):
        exp = []
        for r in bs:
            if int(r['branch']) == k and (r['from_state'] == 'OFF') != (r['to_state'] == 'OFF'):
                exp.append((float(r['t_s']) + 1e-12, 0 if r['to_state'] == 'OFF' else 1))
        got = sim['edges'].by_id.get(I[f'pwr{k}'], [])
        if len(got) != len(exp) or any(a[1] != b[1] or abs(a[0] - b[0]) > TOL for a, b in zip(got, exp)):
            bad += 1
    rep.add('export: branch_states.csv power on/off times match the pwr monitors', 'all 8 branches',
            f'{8 - bad} match', bad == 0)
    import json
    pw = json.loads((out / 'power.json').read_text())
    # independent state times from the replayed scheduler history
    tot = [0.0] * 6
    for k in range(8):
        cur = 0
        for t, st in hist[k]:
            if t <= t0:
                cur = st
        seq = [(t0, cur)] + [(t, st) for t, st in hist[k] if t0 < t < t1] + [(t1, None)]
        for (ta, sa), (tb, _sb) in zip(seq, seq[1:]):
            tot[sa] += tb - ta
    diff = max(abs(pw['state_time_s'][STATES[st]] - tot[st]) for st in range(1, 6))
    rep.add('export: power.json state times match the replayed scheduler', '|diff| <= 50 ps per state',
            f'{diff*1e12:.2f} ps', diff <= 50e-12)
    rep.add('export: energy stays pending while parameters are placeholders', 'pending extraction',
            pw['energy']['status'], pw['energy']['status'] == 'pending extraction')


def decode(sim, pulses_seen=None):
    """Receiver-style decode of outp - outn.

    Pulses are groups of samples with |v| above 0.2 V (gaps under 180 ps
    bridged). The pulse centre is the energy centroid of v^2 over the group
    (the raised-cosine envelope is symmetric), so the start is centre - 9 delta/2.
    DPPM: D = round((start - previous start) / delta) - 16 mod 8; the first
    pulse is referred to its frame edge. FSK: zero crossings within centre
    +- 9 delta / 4 give the frequency; the nearest carrier wins.
    """
    t, v = sim['wave']['time'], [p - n for p, n in zip(sim['wave']['outp'], sim['wave']['outn'])]
    groups, cur = [], None
    for i, x in enumerate(v):
        if abs(x) > 0.2:
            if cur and t[i] - t[cur[1]] < 180e-12:
                cur[1] = i
            else:
                cur = [i, i]
                groups.append(cur)
    ph0 = sim['edges'].times(I['ph0'], 1)
    tw = 9 * DELTA0
    out, s_prev, p_prev = [], None, 0
    for i0, i1 in groups:
        lo = max(0, i0 - 40)
        hi = min(len(t) - 1, i1 + 40)
        num = den = 0.0
        for i in range(lo, hi):
            dt = t[i + 1] - t[i]
            w2 = 0.5 * (v[i] ** 2 + v[i + 1] ** 2) * dt
            num += w2 * 0.5 * (t[i] + t[i + 1])
            den += w2
        centre = num / den
        s0 = centre - tw / 2
        if s_prev is None:
            lat = sim['recs']['PGS'][0][12] if sim['recs'].get('PGS') else 0.0
            frame0 = max(x for x in ph0 if x < s0 - lat + DELTA0 / 2) + lat
            P = round((s0 - frame0) / DELTA0) % 16
            d = (P - p_prev) % 8
        else:
            d = (round((s0 - s_prev) / DELTA0) - 16) % 8
        s_prev = s0
        mid = [(t[i], v[i]) for i in range(lo, hi) if abs(t[i] - centre) < tw / 4]
        zc = [t1 + (t2 - t1) * x1 / (x1 - x2) for (t1, x1), (t2, x2) in zip(mid, mid[1:]) if x1 * x2 < 0]
        f = (len(zc) - 1) / 2 / (zc[-1] - zc[0]) if len(zc) > 2 else 0
        F = min(range(8), key=lambda k: abs(u.CARRIERS[k] - f))
        out.append((u.gray(d) << 3) | u.gray(F))
    return out


def sc_combined(rep):
    syms, pols = random_symbols(17, 150)
    br = dict(MAIN_BR, seed=301)
    sim = run('combined', syms, pols, pg=dict(MAIN_PG, n_lead=2), ro=dict(sigma_tap=2e-12), br=br,
              out=dict(iso_db=40))
    wins, hist, grants, drops, acts, pulses = common(rep, 'combined', sim, n_lead=2, iso_db=40)
    got = decode(sim, pulses)
    n = min(len(got), len(syms))
    wrong = [i for i in range(n) if got[i] != syms[i]]
    rep.add('combined: receiver-style decode of the RF output (main non-ideal values)',
            'reported; 0 errors expected at these sigmas', f'{n - len(wrong)}/{n} correct, first wrong {wrong[:5]}',
            not wrong and n >= len(syms) - 1)


SCEN = dict(lead=sc_lead, static=sc_static, activation=sc_activation, phase_noise=sc_phase_noise,
            timing=sc_timing, tap_skew=sc_tap_skew, isolation=sc_isolation, export=sc_export, combined=sc_combined)


class Rep(u.Report):
    def add(self, label, limit, value, ok):
        return self.check(label, ok, f'{value} (limit {limit})' if limit else str(value))

    def times_match(self, label, got, exp, tol):
        n = min(len(got), len(exp))
        worst = max((abs(a - b) for a, b in zip(got[:n], exp[:n])), default=0.0)
        return self.add(label, f'{len(exp)} edges, |error| <= {tol*1e12:g} ps',
                        f'{len(got)} edges, worst {worst*1e12:.3f} ps', len(got) == len(exp) and worst <= tol)


def main(names):
    ok_all = True
    for name in names:
        rep = Rep(f'm5_{name}')
        try:
            SCEN[name](rep)
        except Exception as exc:          # a broken scenario is a failure, with its cause
            import traceback
            traceback.print_exc()
            rep.check(f'{name}: scenario ran', False, repr(exc)[:300])
        out = u.out_dir_for(f'm5_{name}')
        out.mkdir(parents=True, exist_ok=True)
        rep.write(out)
        print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
        ok_all &= rep.ok
    return ok_all


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:] or list(SCEN)) else 1)
