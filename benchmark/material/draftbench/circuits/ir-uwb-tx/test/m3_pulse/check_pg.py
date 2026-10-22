"""M3 check, part 1: pulse generator (SPEC.md 4.6).

The master RO runs at code 288 (672 MHz). Descriptors (P, F, pol) and
enc_valid come from ideal PWL sources, one per frame at 0.6 Ts after the
nominal frame start, so the PG is tested without the encoder.

Scenarios
  positions   all P values, P 7 -> 0 and 0 -> 7, the same F on consecutive
              symbols with touching windows (7 -> 0), n_pre = 2
  pre15       n_pre = 15 (precharge starts in the scheduling frame)
  pre0        n_pre = 0 (no precharge window; sel/pol read at rf)
  en_late     en rises in the middle of frame 6; descriptors latched while
              disabled stay pending and are overwritten (overrun)

Expected windows are derived from the observed tap edges: a descriptor
scheduled at a ph0 edge starts at the (16 + P)-th tap rising edge after that
ph0 edge, ends n_width tap edges later and its precharge starts n_pre tap
edges earlier. Lanes alternate a, b, a, ... from reset.

Usage: python3 check_pg.py [scenario ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import uwbtest as u  # noqa: E402

EDGE = 2e-12
TOL = 1e-12
TS = u.TS
TAPS = {f'ph{k}': 100 + k for k in range(16)}
LANE_IDS = dict(pre_a=10, rf_a=11, pol_a=12, sa0=13, sa1=14, sa2=15,
                pre_b=20, rf_b=21, pol_b=22, sb0=23, sb1=24, sb2=25, overrun=30)


def pwl_levels(changes, edge=EDGE):
    pts = [(0.0, changes[0][1])]
    for t, v in changes[1:]:
        if v != pts[-1][1]:
            pts.append((t - edge / 2, pts[-1][1]))
            pts.append((t + edge / 2, v))
    return '[' + ' '.join(f'{u.fmt_ps(t) if t else "0"} {v}' for t, v in pts) + ']'


def descriptor_sources(descs, frames):
    """descs[i] = (P, F, pol) latched in frames[i] at frame*Ts + 0.6 Ts."""
    lines = []
    t_ev = [k * TS + 0.6 * TS for k in frames]
    for name, val in (('p', lambda d: d[0]), ('f', lambda d: d[1])):
        for b in range(3):
            ch = [(0.0, 0)] + [(t - 20e-12, (val(d) >> b) & 1) for t, d in zip(t_ev, descs)]
            lines.append(f'V{name}{b} ({name}{b} 0) vsource type=pwl wave={pwl_levels(ch)}')
    ch = [(0.0, 0)] + [(t - 20e-12, d[2]) for t, d in zip(t_ev, descs)]
    lines.append(f'Vpol (pol 0) vsource type=pwl wave={pwl_levels(ch)}')
    ch = [(0.0, 0)]
    for t in t_ev:
        ch += [(t, 1), (t + 400e-12, 0)]
    lines.append(f'Vev (ev 0) vsource type=pwl wave={pwl_levels(ch)}')
    return '\n'.join(lines), t_ev


def build_tb(descs, frames, n_pre, en_wave, stop):
    src, t_ev = descriptor_sources(descs, frames)
    taps = ' '.join(f'ph{k}' for k in range(15, -1, -1))
    code = ' '.join(f'c{b}' for b in range(9, -1, -1))
    code_src = '\n'.join(f'Vc{b} (c{b} 0) vsource dc={(288 >> b) & 1}' for b in range(10))
    tb = f"""simulator lang=spectre
global 0
{u.include_lines('module/master_ro16.va', 'module/pulse_generator.va', 'test/sources/edge_monitor.va')}
{code_src}
Xro ({code} {taps}) uwb_master_ro16
{src}
Ven (en 0) vsource type=pwl wave={en_wave}
Vrst (rst 0) vsource type=pwl wave=[0 1 0.5n 1 0.502n 0]
Xpg ({taps} p2 p1 p0 f2 f1 f0 pol ev en rst pre_a rf_a sa2 sa1 sa0 pol_a pre_b rf_b sb2 sb1 sb0 pol_b overrun) uwb_pulse_generator n_pre={n_pre}
{u.monitor_lines(TAPS)}
{u.monitor_lines(LANE_IDS)}
opts options reltol=1e-6 vabstol=1e-6
tran tran stop={stop!r} maxstep=10p
save rf_a rf_b
"""
    return tb, t_ev


def run_tb(tb, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tb.scs').write_text(tb)
    edges = u.parse_edges(u.run_evas(out / 'tb.scs', out))
    edges.drop_startup()
    return edges


def expected_schedule(edges, t_ev, descs, en_rise, n_pre, n_width=9):
    """Replay SPEC 4.6 from the observed edges. Returns per-symbol dicts and overruns."""
    ph0 = edges.times(100, 1)
    all_taps = sorted(t for k in range(16) for t in edges.times(100 + k, 1))
    pend = None
    out, overruns = [], []
    ev_iter = sorted(zip(t_ev, descs))
    lane = 0
    for t0 in ph0:
        # descriptors latched before this frame edge
        while ev_iter and ev_iter[0][0] < t0:
            t, d = ev_iter.pop(0)
            if pend is not None:
                overruns.append(t)
            pend = (t, d)
        if pend is not None and t0 > en_rise:
            idx = [i for i, t in enumerate(all_taps) if t > t0 + 1e-13]
            if len(idx) < 16 + pend[1][0] + n_width:
                break                       # this pulse would end after the run
            s = all_taps[idx[16 + pend[1][0] - 1]]
            e = all_taps[idx[16 + pend[1][0] - 1 + n_width]]
            p = all_taps[idx[16 + pend[1][0] - 1 - n_pre]] if n_pre else s
            out.append(dict(desc=pend[1], lane=lane, s=s, e=e, p=p, t_sched=t0))
            lane = 1 - lane
            pend = None
    return out, overruns


def check(rep, edges, sched, overruns, n_pre, label):
    lanes = {0: (10, 11, 12, (13, 14, 15)), 1: (20, 21, 22, (23, 24, 25))}
    for ln in (0, 1):
        pre, rf, pol, sel = lanes[ln]
        mine = [x for x in sched if x['lane'] == ln and x['e'] < edges_end(edges)]
        rf_r, rf_f = edges.times(rf, 1), edges.times(rf, 0)
        exp_r = [x['s'] + EDGE / 2 for x in mine]
        exp_f = [x['e'] + EDGE / 2 for x in mine]
        name = 'ab'[ln]
        rep.check(f'{label}: lane {name} rf rises at tap s', match(rf_r, exp_r), diff(rf_r, exp_r))
        rep.check(f'{label}: lane {name} rf falls at tap s + n_width', match(rf_f, exp_f), diff(rf_f, exp_f))
        if n_pre:
            pr_r, pr_f = edges.times(pre, 1), edges.times(pre, 0)
            rep.check(f'{label}: lane {name} pre rises at tap s - n_pre', match(pr_r, [x['p'] + EDGE / 2 for x in mine]),
                      diff(pr_r, [x['p'] + EDGE / 2 for x in mine]))
            rep.check(f'{label}: lane {name} pre falls at tap s', match(pr_f, exp_r), diff(pr_f, exp_r))
        else:
            rep.check(f'{label}: lane {name} pre never rises', not edges.times(pre, 1))
        t_latch = [x['p'] if n_pre else x['s'] for x in mine]
        bad = [(x['desc'], u.bus_value(edges, list(sel), t), edges.level(pol, t))
               for x, t in zip(mine, t_latch)
               if (u.bus_value(edges, list(sel), t), edges.level(pol, t)) != (x['desc'][1], x['desc'][2])]
        rep.check(f'{label}: lane {name} sel/pol hold F/pol when pre (or rf) rises', not bad, f'first {bad[:3]}')
    widths = [x['e'] - x['s'] for x in sched]
    rep.check(f'{label}: every window is 9 tap intervals (837.05 ps)',
              all(abs(w - 9 * u.DELTA0) < 2 * TOL for w in widths),
              f'{min(widths)*1e12:.3f}..{max(widths)*1e12:.3f} ps')
    ov = edges.times(30, 1)
    rep.check(f'{label}: overrun pulses where a pending descriptor was overwritten',
              match(ov, [t + EDGE / 2 for t in overruns]), diff(ov, [t + EDGE / 2 for t in overruns]))


def edges_end(edges):
    return max(t for lst in edges.by_id.values() for t, _ in lst)


def match(got, exp):
    return len(got) == len(exp) and all(abs(a - b) < TOL for a, b in zip(got, exp))


def diff(got, exp):
    n = min(len(got), len(exp))
    w = max((abs(a - b) for a, b in zip(got[:n], exp[:n])), default=0.0)
    return f'{len(got)} vs {len(exp)} edges, worst {w*1e12:.3f} ps'


def run(name):
    out = u.out_dir_for(f'm3_pg_{name}')
    rep = u.Report(f'm3_pg_{name}')
    # P sequence with 7 -> 0, 0 -> 7 and all values; F repeats where windows touch
    descs = [(7, 3, 0), (0, 3, 1), (7, 5, 0), (0, 2, 1), (3, 2, 0), (4, 6, 0), (1, 0, 1), (6, 7, 0),
             (2, 1, 1), (5, 4, 0), (7, 4, 1), (0, 4, 0), (0, 4, 1), (7, 7, 0)]
    frames = list(range(2, 2 + len(descs)))
    en_rise = 0.0
    n_pre = 2
    en_wave = '[0 1]'
    if name == 'pre15':
        n_pre = 15
    elif name == 'pre0':
        n_pre = 0
    elif name == 'en_late':
        en_rise = 6 * TS + 0.3 * TS
        en_wave = f'[0 0 {u.fmt_ps(en_rise - 1e-12)} 0 {u.fmt_ps(en_rise + 1e-12)} 1]'
    elif name != 'positions':
        raise SystemExit(f'unknown scenario {name}')
    stop = (frames[-1] + 5) * TS
    tb, t_ev = build_tb(descs, frames, n_pre, en_wave, stop)
    edges = run_tb(tb, out)
    sched, overruns = expected_schedule(edges, t_ev, descs, en_rise, n_pre)
    # en_late: descriptors of frames 2..5 overwrite each other; the one from
    # frame 6 (latched after en rose) is the first scheduled
    want = len(descs) - (4 if name == 'en_late' else 0)
    rep.check(f'{name}: descriptors scheduled', len(sched) == want, f'{len(sched)} scheduled of {want}')
    check(rep, edges, sched, overruns, n_pre, name)
    rep.write(out)
    print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
    return rep.ok


if __name__ == '__main__':
    names = sys.argv[1:] or ['positions', 'pre15', 'pre0', 'en_late']
    ok = all([run(n) for n in names])
    sys.exit(0 if ok else 1)
