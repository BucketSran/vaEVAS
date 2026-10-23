"""Synthetic bursts for the final evaluation: fixed VA test sources with known truth.

Each burst is a raised-cosine RF burst from tests/benches/test_burst.va. The
checker evaluates the same closed form on a 0.1 ps grid, so every pulse
measurement (first and last exceedance, zero crossings) is independent of the
simulator and of the candidate. Bursts are placed on the frames of an ideal
clock so that the pulse start ts of S1 lands at frame + P*delta + e.
"""
import math
from pathlib import Path

import contract as c
import uwbtask as u

BURST = Path(__file__).resolve().parent / 'benches' / 'test_burst.va'
VCM = 0.6               # common mode of vp and vn
CLK_DELAY = 0.3e-9
DT = 0.1e-12            # truth grid


def burst_v(b, t):
    """The closed form of test_burst.va."""
    uu = t - b['t0']
    if not 0 < uu < b['width']:
        return 0.0
    x = uu - b['width'] / 2
    ax = abs(x)
    fe = b.get('f_edge') or b['f_core']
    wc = b.get('w_core', 0.0)
    cyc = b['f_core'] * ax if ax <= wc else b['f_core'] * wc + fe * (ax - wc)
    if x < 0:
        cyc = -cyc
    return b['amp'] * 0.5 * (1 - math.cos(2 * math.pi * uu / b['width'])) * math.cos(b.get('phase', 0.0) + 2 * math.pi * cyc)


def frame(case, k):
    """Rising vdd/2 crossing of clock edge k (uwb_clock_source, 2 ps edges)."""
    return CLK_DELAY + k * case['T'] + 1e-12


def place(case, items, n_width_ref=9, first_frame=3, gap=350e-12, reset_room=900e-12):
    """Bursts for items [{P, e, f_core, amp, ...}]; ts lands on frame + P*delta + e.

    The frame of each burst is the first one that leaves `gap` between burst
    envelopes (`reset_room` before an item with reset_before). Returns bursts
    and decoder resets.
    """
    d = case['T'] / 16
    bursts, resets, k, prev_end = [], [], first_frame, -1.0
    for it in items:
        width = it.get('width_taps', 9) * d
        need = reset_room if it.get('reset_before') else gap
        while True:
            centre = frame(case, k) + it['P'] * d + it.get('e', 0.0) + n_width_ref * d / 2
            t0 = centre - width / 2
            if t0 - prev_end >= need:
                break
            k += 1
        if it.get('reset_before'):
            mid = (prev_end + t0) / 2 + 0.15e-9
            resets.append((mid - 75e-12, mid + 75e-12))
        b = dict(t0=t0, width=width, amp=it['amp'], f_core=it['f_core'], phase=it.get('phase', 0.0))
        if it.get('f_edge'):
            b.update(f_edge=it['f_edge'], w_core=it['w_core'])
        bursts.append(b)
        prev_end = t0 + width
        k += 1
    return bursts, resets


def make_case(name, T, items, instances, n_width_ref=9, **kw):
    case = dict(name=name, T=T, instances=instances, netlist=netlist, truth=truth)
    case['bursts'], case['drst'] = place(case, items, n_width_ref, **kw)
    case['stop'] = case['bursts'][-1]['t0'] + case['bursts'][-1]['width'] + 1.5e-9
    case['items'] = items
    return case


def netlist(case, candidate, tb_dir):
    lines = ['simulator lang=spectre', 'global 0', f'ahdl_include "{candidate}"', f'ahdl_include "{BURST}"',
             f'ahdl_include "{tb_dir / "clock_source.va"}"', f'ahdl_include "{tb_dir / "edge_monitor.va"}"',
             f'Vcm (cm 0) vsource dc={VCM!r}',
             f'Xclk (clk) uwb_clock_source period={case["T"]!r} delay={CLK_DELAY!r} tr=2e-12']
    node = 'cm'
    for j, b in enumerate(case['bursts']):
        extra = f' f_edge={b["f_edge"]!r} w_core={b["w_core"]!r}' if 'f_edge' in b else ''
        lines.append(f'Xb{j} ({node} rf{j}) uwb_test_burst t0={b["t0"]!r} width={b["width"]!r} amp={b["amp"]!r} '
                     f'f_core={b["f_core"]!r} phase={b["phase"]!r}{extra}')
        node = f'rf{j}'
    lines += c.decoder_lines(case, (node, 'cm', 'clk'))
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={case["stop"]!r} maxstep=10p',
              f'save {node} cm']
    return '\n'.join(lines) + '\n'


def truth(case, res, p):
    """Pulses of S1 from the closed form (the run's waveform is not used)."""
    t, v = [0.0], [0.0]
    for b in case['bursts']:
        n = int(b['width'] / DT)
        t.append(b['t0'])
        v.append(0.0)
        for i in range(1, n):
            tt = b['t0'] + i * b['width'] / n
            t.append(tt)
            v.append(burst_v(b, tt))
        t.append(b['t0'] + b['width'])
        v.append(0.0)
    t.append(case['stop'])
    v.append(0.0)
    return c.measure_pulses(t, v, p)
