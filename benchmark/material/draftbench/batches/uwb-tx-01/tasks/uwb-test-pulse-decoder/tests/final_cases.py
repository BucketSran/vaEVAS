"""Final-evaluation cases added to the public ones (kept out of the solver image).

Two more seed-chain runs (another RO code with inverted pulses; two decoder
instances with different parameters) and two runs of synthetic bursts whose
truth is known in closed form: off-grid starts, carriers between channels,
positions 8 to 15, other amplitudes, inverted and phase-shifted bursts,
off-channel burst edges outside the frequency window, other clock periods and
resets after malformed pulses.
"""
import math
import random

import contract as c
import synth

CH = c.CARRIERS


def chain_cases():
    rnd = random.Random(625)
    syms = [rnd.randrange(64) for _ in range(90)]
    pols = [rnd.randrange(2) for _ in range(90)]
    # code 100: the RO runs at 625 MHz (delta = 100 ps), every pulse polarity random
    c100 = dict(name='chain100_pol', code=100, symbols=syms, pols=pols, instances=[dict(name='a', params={})])
    c100['drst'] = [c.reset_near(c100, 45)]
    rnd = random.Random(288288)
    syms = [rnd.randrange(64) for _ in range(70)]
    a = dict(v_det=0.1, t_gap=80e-12, t_lat=300e-12, t_pw=120e-12, tol_pos=0.2, tol_f=0.02,
             vdd=1.2, vth=0.4, tr=4e-12)
    two = dict(name='chain288_two', code=288, symbols=syms,
               instances=[dict(name='a', params=a), dict(name='b', params={})])
    two['drst'] = [c.reset_near(two, 30, after=0.6e-9)]
    return [c100, two]


def synth_grid():
    """800 MHz clock (delta = 78.125 ps), default parameters (tolerance 19.5 ps, 3 %)."""
    items = [
        dict(P=3, f_core=CH[2], amp=0.8),
        dict(P=6, e=28e-12, f_core=CH[5], amp=1.0),            # late start: err
        dict(P=1, e=-28e-12, f_core=CH[0], amp=1.0),           # early start: err; P_prev = 1 after it
        dict(P=5, e=12e-12, f_core=CH[6], amp=0.7),            # inside the position tolerance
        dict(P=0, e=-12e-12, f_core=CH[3], amp=1.2),           # ts before the frame edge, still P = 0
        dict(P=7, f_core=5.10e9, amp=0.9),                     # between channels 1 and 2: err
        dict(P=2, f_core=CH[3] * 1.02, amp=0.6),               # +2 %: no err
        dict(P=9, f_core=CH[4], amp=1.0),                      # P = 9: err
        dict(P=4, e=5e-12, f_core=CH[1], amp=-0.6),            # inverted
        dict(P=12, f_core=CH[7], amp=1.0),                     # P = 12: err
        dict(P=0, f_core=CH[7], amp=1.5),
        dict(P=7, e=-8e-12, f_core=CH[0] * 0.965, amp=1.0),    # -3.5 %: err
        dict(P=15, e=6e-12, f_core=CH[2], amp=0.8),            # P = 15: err
        dict(P=3, f_core=CH[5], amp=0.35, phase=math.pi / 2),  # small, antisymmetric carrier
        dict(P=6, f_core=CH[1], amp=1.1, phase=1.3),
        # channel 3 inside the frequency window, 4.0 GHz in the edges outside it: F = 3, no err
        dict(P=1, f_core=CH[3], f_edge=4.0e9, w_core=9 * 78.125e-12 / 4 + 20e-12, amp=1.0),
        dict(P=5, e=-14e-12, f_core=CH[6] * 0.975, amp=-1.0),  # inside both tolerances
        dict(P=2, e=24e-12, f_core=CH[2] * 1.035, amp=0.5),    # position and frequency err
        dict(P=8, e=-15e-12, f_core=CH[3], amp=0.9),           # P = 8: err
        dict(P=4, f_core=CH[0], amp=-1.3),
        dict(P=7, f_core=CH[6], amp=0.45, reset_before=True),  # first pulse after a reset: D = 7
        dict(P=0, f_core=CH[4], amp=1.0),
        # channel 5 inside the window, 7.8 GHz in the edges: F = 5, no err
        dict(P=3, f_core=CH[5], f_edge=7.8e9, w_core=9 * 78.125e-12 / 4 + 20e-12, amp=1.0),
    ]
    return synth.make_case('synth_grid', 1.25e-9, items, [dict(name='a', params={})])


def synth_params():
    """700 MHz clock (delta = 89.3 ps); instance a with other parameters, b with defaults.

    Bursts are 9 delta long, so for a (n_width = 7) every ts lies one delta
    later than for b: P_a = P_b + 1.
    """
    a = dict(n_width=7, tol_pos=0.15, tol_f=0.05, v_det=0.12, t_gap=70e-12, t_lat=320e-12,
             t_pw=150e-12, vdd=1.2, vth=0.45, tr=5e-12)
    items = [
        dict(P=2, f_core=CH[3], amp=1.0),
        dict(P=4, e=18e-12, f_core=CH[5], amp=0.9),            # a: err (13.4 ps), b: inside (22.3 ps)
        dict(P=7, f_core=CH[1], amp=1.0),                      # a: P = 8, err
        dict(P=1, e=-8e-12, f_core=CH[0] * 1.04, amp=0.8),     # a: inside 5 %, b: err (3 %)
        dict(P=5, e=30e-12, f_core=CH[2], amp=1.1),            # both err
        dict(P=0, f_core=CH[0] * 0.94, amp=0.7),               # both err (frequency)
        dict(P=6, e=-5e-12, f_core=CH[7], amp=-1.0),
        dict(P=3, f_core=CH[4], amp=0.5),
        dict(P=6, f_core=CH[2], amp=1.0, reset_before=True),
        dict(P=15, f_core=CH[5], amp=0.8),                     # b: P = 15, err; a: next frame, P = 0
        dict(P=2, e=10e-12, f_core=CH[1], amp=-0.7),
        dict(P=4, f_core=CH[6] * 0.985, amp=1.2),
        # channel 4 inside both instances' windows, 7.8 GHz in the edges: F = 4, no err
        dict(P=1, f_core=CH[4], f_edge=7.8e9, w_core=9 / 700e6 / 64 + 20e-12, amp=1.0),
    ]
    return synth.make_case('synth_params', 1 / 700e6, items,
                           [dict(name='a', params=a), dict(name='b', params={})])


def final_cases():
    return chain_cases() + [synth_grid(), synth_params()]
