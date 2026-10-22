"""M2 check: 16-phase master RO and counter-based frequency calibration
(SPEC.md 4.4, 4.5).

Scenarios
  ro_step       RO alone. Code 288 -> 300 -> 100 from ideal PWL code bits; a
                second instance starts at phase0 = 0.3. Every tap edge is
                compared with an independent event model of the SPEC rules
                (tap k rises k*delta after ph0; a code change keeps the
                elapsed share of the current tap interval).
  cal_normal    48 MHz reference, RO and calibration with n_win = 192.
  cal_recal     n_win = 24; a second cal_start after done.
  cal_ref_lost  the reference stops during the search -> fail.
  cal_no_conv   RO with f0 = 700 MHz cannot reach 672 MHz -> fail.
  cal_too_slow  RO stuck at 100 MHz: every bit is kept, code 1023, then fail.

For the calibration runs the checker replays the SPEC search from the
observed reference and RO edges (it counts the RO edges itself) and compares
each code change, the final code and done/fail with the simulation.

Usage: python3 check_m2.py [scenario ...]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import uwbtest as u  # noqa: E402

EDGE = 2e-12
TOL = 1e-12
T_CODE, T_CQ = 5e-12, 10e-12
F0, FSTEP = 600e6, 0.25e6
T_REF = 1 / 48e6

TAP_IDS = {f'ph{k}': 100 + k for k in range(16)}
CODE_IDS = [200 + k for k in range(10)]


def code_bits_pwl(changes, stop):
    """changes: list of (t_switch, code); first entry at t=0. One PWL per bit."""
    lines = []
    for b in range(10):
        pts = [(0.0, (changes[0][1] >> b) & 1)]
        for t, c in changes[1:]:
            v_old, v_new = pts[-1][1], (c >> b) & 1
            if v_new != v_old:
                pts.append((t - EDGE / 2, v_old))
                pts.append((t + EDGE / 2, v_new))
        wave = ' '.join(f'{u.fmt_ps(t) if t else "0"} {v}' for t, v in pts)
        lines.append(f'Vc{b} (c{b} 0) vsource type=pwl wave=[{wave}]')
    return '\n'.join(lines)


def ro_model(changes, t_end, phase0=0.0):
    """Independent event model of the RO: returns list of (time, m) after each tap step."""
    f = F0 + FSTEP * changes[0][1]
    m = math.floor(16 * phase0)
    r = 16 * phase0 - m
    t_last, t_next = -r / (16 * f), (1 - r) / (16 * f)
    reads = [(t + T_CODE, c) for t, c in changes[1:]]   # code edge midpoint + t_code
    out = []
    while True:
        if reads and reads[0][0] < t_next:
            t, c = reads.pop(0)
            r = (t - t_last) / (t_next - t_last)
            f = F0 + FSTEP * c
            t_last, t_next = t - r / (16 * f), t + (1 - r) / (16 * f)
            continue
        if t_next > t_end:
            return out
        m = (m + 1) % 16
        t_last = t_next
        t_next = t_next + 1 / (16 * f)
        out.append((t_last, m))


def tap_rises(model, k):
    """Tap k rises when m becomes k (crossing at the edge midpoint)."""
    return [t + EDGE / 2 for t, m in model if m == k]


def compare(rep, label, got, exp):
    n = min(len(got), len(exp))
    worst = max((abs(a - b) for a, b in zip(got[:n], exp[:n])), default=float('inf'))
    rep.check(label, len(got) == len(exp) and worst < TOL,
              f'{len(got)} vs {len(exp)} edges, worst {worst*1e12:.3f} ps')


def scenario_ro_step(rep, out):
    stop = 60e-9
    changes = [(0.0, 288), (20.05e-9, 300), (41.3e-9, 100)]
    tb = f"""simulator lang=spectre
global 0
{u.include_lines('module/master_ro16.va', 'test/sources/edge_monitor.va')}
{code_bits_pwl(changes, stop)}
XroA (c9 c8 c7 c6 c5 c4 c3 c2 c1 c0 {' '.join(f'ph{k}' for k in range(15, -1, -1))}) uwb_master_ro16
XroB (c9 c8 c7 c6 c5 c4 c3 c2 c1 c0 {' '.join(f'b{k}' for k in range(15, -1, -1))}) uwb_master_ro16 phase0=0.3
{u.monitor_lines(TAP_IDS)}
{u.monitor_lines(dict(b0=150))}
opts options reltol=1e-6 vabstol=1e-6
tran tran stop={stop!r} maxstep=10p
save ph0 b0
"""
    edges = run_tb(tb, out)
    model = ro_model(changes, stop)
    for k in range(16):
        compare(rep, f'tap {k} rising edges follow the model', edges.times(100 + k, 1), tap_rises(model, k))
    exp_b = tap_rises(ro_model(changes, stop, 0.3), 0)
    compare(rep, 'phase0 = 0.3 instance: ph0 rising edges follow the model', edges.times(150, 1), exp_b)
    # direct physical statements, independent of the model's bookkeeping
    p0 = edges.times(100, 1)
    early = [b - a for a, b in zip(p0, p0[1:]) if b < 20e-9]
    rep.check('period at code 288 is 1/672 MHz', all(abs(x - 1 / 672e6) < TOL for x in early),
              f'{min(early)*1e12:.3f}..{max(early)*1e12:.3f} ps')
    late = [b - a for a, b in zip(p0, p0[1:]) if a > 42e-9]
    rep.check('period at code 100 is 1/625 MHz', all(abs(x - 1 / 625e6) < TOL for x in late),
              f'{min(late)*1e12:.3f}..{max(late)*1e12:.3f} ps')
    t0 = min(x for x in p0 if x > 10e-9)
    taps = [min(x for x in edges.times(100 + k, 1) if x > t0 - 1e-12) for k in range(16)]
    gaps = [(taps[k] - taps[0]) - k / (16 * 672e6) for k in range(16)]
    rep.check('tap k rises k*delta after ph0', all(abs(g) < TOL for g in gaps),
              f'worst {max(map(abs, gaps))*1e12:.3f} ps')


def cal_tb(stop, n_win, cal_starts, ro_params='', ref_stop=None):
    pulses = ' '.join(f'{u.fmt_ps(t - 1e-12)} 0 {u.fmt_ps(t + 1e-12)} 1 {u.fmt_ps(t + 2e-9)} 1 {u.fmt_ps(t + 2.002e-9)} 0'
                      for t in cal_starts)
    ref_extra = f' t_stop={ref_stop!r}' if ref_stop else ''
    return f"""simulator lang=spectre
global 0
{u.include_lines('module/master_ro16.va', 'module/ro_frequency_cal.va',
                 'test/sources/clock_source.va', 'test/sources/edge_monitor.va')}
Xref (ref) uwb_clock_source period={T_REF!r} delay=0.37n tr={EDGE!r}{ref_extra}
Vrst (rst 0) vsource type=pwl wave=[0 1 10n 1 10.002n 0]
Vcal (cal 0) vsource type=pwl wave=[0 0 {pulses}]
Xro (k9 k8 k7 k6 k5 k4 k3 k2 k1 k0 {' '.join(f'ph{k}' for k in range(15, -1, -1))}) uwb_master_ro16 {ro_params}
Xcal (ref ph0 cal rst k9 k8 k7 k6 k5 k4 k3 k2 k1 k0 done fail busy) uwb_ro_frequency_cal n_win={n_win}
{u.monitor_lines(dict(ref=1, ph0=100, cal=3, done=4, fail=5, busy=6, **{f'k{b}': 200 + b for b in range(10)}))}
opts options reltol=1e-6 vabstol=1e-6
tran tran stop={stop!r} maxstep=100p
save done fail busy
"""


def replay_cal(edges, n_win, t_start, ratio=14, n_settle=2, tol=1, n_lost=64):
    """Replay the SPEC search from observed edges. Returns list of events."""
    ref = [t for t in edges.times(1, 1) if t > t_start]
    ro = [t for t in edges.times(100, 1) if t > t_start]
    target = n_win * ratio
    events = [(t_start + T_CQ, 0, 'code')]      # trial 512 shown after cal_start
    code_q, weight, trial = 0, 512, 512
    events[-1] = (t_start + T_CQ, trial, 'code')
    i = 0
    ambiguous = 0
    verify = False
    # lost-reference watchdog: count RO edges between consecutive reference edges
    prev = t_start
    while True:
        # settle: n_settle reference edges, then a window of n_win more
        if i + n_settle + n_win - 1 >= len(ref):
            # reference stops: find the RO edge that exceeds n_lost since the last ref edge
            last_ref = ref[-1] if ref else t_start
            after = [t for t in ro if t > max(last_ref, prev)]
            if len(after) > n_lost:
                # on fail the block shows the last kept code, not the untested trial
                t_fail = after[n_lost] + T_CQ
                return events + [(t_fail, code_q, 'code'), (t_fail, code_q, 'fail')], ambiguous
            return events + [(None, None, 'incomplete')], ambiguous
        w0 = ref[i + n_settle - 1]
        w1 = ref[i + n_settle - 1 + n_win]
        cnt = sum(1 for t in ro if w0 < t < w1)
        if any(abs(t - w0) < 2e-12 or abs(t - w1) < 2e-12 for t in ro):
            ambiguous += 1
        i = i + n_settle + n_win
        prev = w1
        if not verify:
            if cnt <= target:
                code_q = trial
            weight //= 2
            if weight >= 1:
                trial = code_q + weight
            else:
                trial = code_q
                verify = True
            events.append((w1 + T_CQ, trial, 'code'))
        else:
            ok = abs(cnt - target) <= tol
            events.append((w1 + T_CQ, code_q, 'done' if ok else 'fail'))
            return events, ambiguous


# Calibration benches use maxstep = 100p for speed; legacy EVAS then locates
# crossings within a few ps (up to ~10 ps on the 2 ps RO edges). The checks
# below only need to identify the reference edge (period 20.8 ns).
TOL_CAL = 25e-12


def check_cal(rep, edges, n_win, t_start, label, expect, t_end=1.0):
    events, amb = replay_cal(edges, n_win, t_start)
    rep.check(f'{label}: no RO edge within 2 ps of a window boundary', amb == 0, f'{amb} ambiguous')
    code_edges = sorted(set(t for b in CODE_IDS for t in edges.times(b) if t_start < t < t_end))
    # group bit edges that belong to one code update (same instant)
    updates = []
    for t in code_edges:
        if not updates or t - updates[-1] > 5e-12:
            updates.append(t)
    exp_codes = [(t, c) for t, c, kind in events if kind == 'code' and t is not None]
    # each expected code that differs from the previous output must appear at t + edge/2
    shown = []
    prev = u.bus_value(edges, CODE_IDS, t_start)
    for t, c in exp_codes:
        if c != prev:
            shown.append((t + EDGE / 2, c))
            prev = c
    ok = len(shown) == len(updates) and all(abs(a - b[0]) < TOL_CAL for a, b in zip(updates, shown))
    rep.check(f'{label}: code updates at the replayed reference edges', ok,
              f'{len(updates)} vs {len(shown)} updates')
    bad = [(t, c, u.bus_value(edges, CODE_IDS, t + TOL_CAL)) for t, c in shown
           if u.bus_value(edges, CODE_IDS, t + TOL_CAL) != c]
    rep.check(f'{label}: code values equal the replayed search', not bad, f'first {bad[:3]}')
    final = events[-1]
    rep.check(f'{label}: outcome {expect}', final[2] == expect, f'replay says {final[2]}')
    if final[0] is not None:
        t_flag = final[0] + EDGE / 2
        flag_id = 4 if final[2] == 'done' else 5
        got = [t for t in edges.times(flag_id, 1) if t > t_start]
        rep.check(f'{label}: {final[2]} rises at the deciding edge + t_cq', bool(got) and abs(got[0] - t_flag) < TOL_CAL,
                  f'got {got[:1]}, expected {t_flag}')
        busy_fall = [t for t in edges.times(6, 0) if t > t_start]
        rep.check(f'{label}: busy falls with the outcome', bool(busy_fall) and abs(busy_fall[0] - t_flag) < TOL_CAL)
    return events


def run_tb(tb, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tb.scs').write_text(tb)
    edges = u.parse_edges(u.run_evas(out / 'tb.scs', out))
    edges.drop_startup()
    return edges


def run(name):
    out = u.out_dir_for(f'm2_{name}')
    rep = u.Report(f'm2_{name}')
    t_cal = 50e-9                 # cal_start crossing (PWL edge midpoint)
    if name == 'ro_step':
        scenario_ro_step(rep, out)
    elif name == 'cal_normal':
        stop = 50e-9 + 11 * 194 * T_REF + 200e-9
        edges = run_tb(cal_tb(stop, 192, [50e-9]), out)
        events = check_cal(rep, edges, 192, t_cal, 'n_win=192', 'done')
        final = events[-1][1]
        rep.check('final code within 1 of 288', abs(final - 288) <= 1, f'code {final}')
        p0 = [t for t in edges.times(100, 1) if t > events[-1][0] + 20e-9]
        f_meas = (len(p0) - 1) / (p0[-1] - p0[0])
        rep.check('RO runs at 672 MHz +- 0.25 MHz after done', abs(f_meas - 672e6) <= 0.25e6 + 1e3,
                  f'{f_meas/1e6:.4f} MHz')
    elif name == 'cal_recal':
        t2 = 50e-9 + 11 * 26 * T_REF + 300e-9
        stop = t2 + 11 * 26 * T_REF + 300e-9
        edges = run_tb(cal_tb(stop, 24, [50e-9, t2]), out)
        ev1 = check_cal(rep, edges, 24, t_cal, 'first calibration', 'done', t_end=t2)
        rep.check('done stays high until the second cal_start',
                  edges.level(4, t2 - 1e-9) == 1 and not [t for t in edges.times(4, 0) if ev1[-1][0] < t < t2])
        dfall = [t for t in edges.times(4, 0) if t > t2]
        rep.check('second cal_start clears done', bool(dfall) and abs(dfall[0] - (t2 + T_CQ + EDGE / 2)) < TOL_CAL,
                  f'{dfall[:1]}')
        check_cal(rep, edges, 24, t2, 'second calibration', 'done')
    elif name == 'cal_ref_lost':
        t_stop = 50e-9 + 3.5 * 26 * T_REF
        stop = t_stop + 400e-9
        edges = run_tb(cal_tb(stop, 24, [50e-9], ref_stop=t_stop), out)
        check_cal(rep, edges, 24, t_cal, 'reference lost', 'fail')
    elif name == 'cal_no_conv':
        stop = 50e-9 + 11 * 26 * T_REF + 300e-9
        edges = run_tb(cal_tb(stop, 24, [50e-9], ro_params='f0=700e6'), out)
        ev = check_cal(rep, edges, 24, t_cal, 'RO too fast', 'fail')
        rep.check('search ends at code 0', ev[-1][1] == 0, f'{ev[-1][1]}')
    elif name == 'cal_too_slow':
        stop = 50e-9 + 11 * 26 * T_REF + 300e-9
        edges = run_tb(cal_tb(stop, 24, [50e-9], ro_params='f0=100e6 fstep=0'), out)
        ev = check_cal(rep, edges, 24, t_cal, 'RO too slow', 'fail')
        rep.check('search ends at code 1023', ev[-1][1] == 1023, f'{ev[-1][1]}')
    else:
        raise SystemExit(f'unknown scenario {name}')
    rep.write(out)
    print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
    return rep.ok


if __name__ == '__main__':
    names = sys.argv[1:] or ['ro_step', 'cal_recal', 'cal_ref_lost', 'cal_no_conv', 'cal_too_slow', 'cal_normal']
    ok = all([run(n) for n in names])
    sys.exit(0 if ok else 1)
