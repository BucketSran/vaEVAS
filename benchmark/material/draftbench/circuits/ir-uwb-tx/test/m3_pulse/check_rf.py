"""M3 check, part 2: RF branch RO and envelope lane (SPEC.md 4.8, 4.9).

Scenarios
  branch    two cold starts of one branch (pwr, pre, rel from PWL): seed
            settling (t99 200 ps, +1 % start offset) and an ideal instance.
            vro is compared with the SPEC formula evaluated here; it must be
            zero while off or precharging, restart from phi0 after each cold
            start, and the zero-crossing spacing must show the start offset
            decaying to the carrier period.
  envelope  one 9-tap gate with a 672 MHz clk. env is compared with an
            independent RK4 integration of tau*y' + y = e_cmd(t), and the tail
            must fall below 1e-6 within 150 ps of the window end.

Usage: python3 check_rf.py [scenario ...]
"""
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import uwbtest as u  # noqa: E402

EDGE = 2e-12
F = 6e9


def run_tb(tb, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tb.scs').write_text(tb)
    res = u.run_evas(out / 'tb.scs', out)
    rows = list(csv.DictReader(open(res['tran'])))
    return {k: [float(r[k]) for r in rows] for k in rows[0]}


def pwl(points):
    return '[' + ' '.join(f'{u.fmt_ps(t) if t else "0"} {v}' for t, v in points) + ']'


def step_wave(edges_list):
    """edges_list: [(t, level)], 2 ps edges centred on t."""
    pts = [(0.0, edges_list[0][1])]
    for t, v in edges_list[1:]:
        pts += [(t - EDGE / 2, pts[-1][1]), (t + EDGE / 2, v)]
    return pwl(pts)


def branch_formula(t, t_rel, f, t99a, t99f, df, phi0=0.0):
    u_ = t - t_rel
    ta, tf = t99a / math.log(100), t99f / math.log(100)
    amp = 1 - math.exp(-u_ / ta) if ta > 0 else 1.0
    ph = phi0 + 2 * math.pi * f * (u_ + (df * tf * (1 - math.exp(-u_ / tf)) if tf > 0 else 0))
    return amp * math.cos(ph)


def scenario_branch(rep, out):
    t_on = [1e-9, 5e-9]
    t_rel = [t + 186e-12 for t in t_on]
    t_off = [3.5e-9, 6.5e-9]
    pwr = step_wave([(0, 0), (t_on[0], 1), (t_off[0], 0), (t_on[1], 1), (t_off[1], 0)])
    pre = step_wave([(0, 0), (t_on[0], 1), (t_rel[0], 0), (t_on[1], 1), (t_rel[1], 0)])
    rel = step_wave([(0, 0), (t_rel[0], 1), (t_off[0], 0), (t_rel[1], 1), (t_off[1], 0)])
    tb = f"""simulator lang=spectre
global 0
{u.include_lines('module/rf_ro_branch.va')}
Vpwr (pwr 0) vsource type=pwl wave={pwr}
Vpre (pre 0) vsource type=pwl wave={pre}
Vrel (rel 0) vsource type=pwl wave={rel}
Xseed (pwr pre rel vs) uwb_rf_ro_branch f_rf={F!r}
Xideal (pwr pre rel vi) uwb_rf_ro_branch f_rf={F!r} t99_amp=0 t99_freq=0 df_start=0
opts options reltol=1e-6 vabstol=1e-6
tran tran stop=8n maxstep=1p
save vs vi pwr pre rel
"""
    w = run_tb(tb, out)
    t = w['time']
    for name, key, t99, df in (('seed', 'vs', 200e-12, 0.01), ('ideal', 'vi', 0.0, 0.0)):
        err, n_on = 0.0, 0
        for ti, v in zip(t, w[key]):
            seg = [k for k in range(2) if t_rel[k] + 1.5e-12 < ti < t_off[k] - 1.5e-12]
            far_off = all(not (t_rel[k] - 1.5e-12 <= ti <= t_off[k] + 1.5e-12) for k in range(2))
            if seg:
                exp = branch_formula(ti, t_rel[seg[0]], F, t99, t99, df)
                err = max(err, abs(v - exp)); n_on += 1
            elif far_off:
                err = max(err, abs(v))
        rep.check(f'{name}: vro equals the SPEC formula while released and 0 while off/precharging',
                  err < 1e-6, f'max error {err:.2e} V over {len(t)} points ({n_on} oscillating)')
        # zero crossings in each oscillating segment
        zc = [[], []]
        for (t0, v0), (t1, v1) in zip(zip(t, w[key]), zip(t[1:], w[key][1:])):
            for k in range(2):
                if t_rel[k] < t0 and t1 < t_off[k] and v0 * v1 < 0:
                    zc[k].append(t0 + (t1 - t0) * v0 / (v0 - v1))
        first = [z[0] - tr for z, tr in zip(zc, t_rel)]
        if df == 0:
            ok = all(abs(x - 1 / (4 * F)) < 0.3e-12 for x in first)
            rep.check(f'{name}: first zero crossing a quarter period after release (phi0 = 0), both starts',
                      ok, f'{[round(x*1e12, 3) for x in first]} ps')
        else:
            rep.check(f'{name}: both cold starts give the same waveform (repeatable preset phase)',
                      abs(first[0] - first[1]) < 0.3e-12, f'{[round(x*1e12, 3) for x in first]} ps')
            half = [b - a for a, b in zip(zc[0], zc[0][1:])]
            early, late = half[0] * 2, half[-1] * 2
            rep.check(f'{name}: first cycle faster by about the start offset, later cycles at 1/f',
                      early < 1 / F and abs(late - 1 / F) < 0.2e-12,
                      f'first {early*1e12:.3f} ps, last {late*1e12:.3f} ps, 1/f {1e12/F:.3f} ps')


def ode_env(times, t_g, t_w, t99, t_end):
    """RK4 of tau*y' + y = e_cmd, e_cmd raised cosine on [t_g, t_g + t_w]."""
    tau = t99 / math.log(100)

    def e(t):
        x = t - t_g
        return 0.5 * (1 - math.cos(2 * math.pi * x / t_w)) if 0 <= x <= t_w else 0.0

    h = 0.005e-12
    y, tc, out = 0.0, t_g, []
    for t in times:
        if t <= t_g:
            out.append(0.0)
            continue
        while tc < t - 1e-18:
            hh = min(h, t - tc)
            k1 = (e(tc) - y) / tau
            k2 = (e(tc + hh / 2) - (y + hh * k1 / 2)) / tau
            k3 = (e(tc + hh / 2) - (y + hh * k2 / 2)) / tau
            k4 = (e(tc + hh) - (y + hh * k3)) / tau
            y += hh * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            tc += hh
        out.append(y)
    return out


def scenario_envelope(rep, out):
    t_clk = 1 / 672e6
    t_g = 6e-9 + 0.25e-9
    t_w = 9 * t_clk / 16
    gate = step_wave([(0, 0), (t_g, 1), (t_g + t_w, 0)])
    tb = f"""simulator lang=spectre
global 0
{u.include_lines('module/envelope_lane.va', 'test/sources/clock_source.va')}
Xclk (clk) uwb_clock_source period={t_clk!r} delay=10p tr=2p
Vg (gate 0) vsource type=pwl wave={gate}
Xenv (gate clk env) uwb_envelope_lane
opts options reltol=1e-6 vabstol=1e-6
tran tran stop=8n maxstep=1p
save env gate
"""
    w = run_tb(tb, out)
    t, env = w['time'], w['env']
    sel = [i for i, ti in enumerate(t) if t_g - 50e-12 < ti < t_g + t_w + 300e-12]
    ref = ode_env([t[i] for i in sel], t_g, t_w, 50e-12, t_g + t_w)
    err = max(abs(env[i] - r) for i, r in zip(sel, ref))
    rep.check('envelope equals an RK4 solution of tau*y\' + y = raised cosine', err < 1e-5,
              f'max error {err:.2e} over {len(sel)} points')
    peak = max(env)
    rep.check('envelope peak close to 1 (one-sided lag of a 10.9 ps response)', 0.99 < peak <= 1.0,
              f'{peak:.6f}')
    tail = [abs(v) for ti, v in zip(t, env) if ti > t_g + t_w + 150e-12]
    rep.check('tail below 1e-6 from 150 ps after the window end', max(tail) < 1e-6, f'max {max(tail):.2e}')
    before = [abs(v) for ti, v in zip(t, env) if ti < t_g - 1.5e-12]
    rep.check('zero before the gate', max(before) == 0.0, f'max {max(before):.2e}')


def run(name):
    out = u.out_dir_for(f'm3_rf_{name}')
    rep = u.Report(f'm3_rf_{name}')
    {'branch': scenario_branch, 'envelope': scenario_envelope}[name](rep, out)
    rep.write(out)
    print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
    return rep.ok


if __name__ == '__main__':
    names = sys.argv[1:] or ['branch', 'envelope']
    ok = all([run(n) for n in names])
    sys.exit(0 if ok else 1)
