"""Final-evaluation cases added to the public ones (kept out of the solver image).

Every case is checked against the operating domain of S9 with
contract.validate; random sequences are grown one frame at a time and a
frame that would leave the domain is redrawn.
"""
import random

import contract as c

T0 = 0.5e-9


def grow(base, n, seed, draw, tries=60):
    """Frames drawn one by one; a draw that leaves the domain of S9 is redrawn
    (after `tries` failures the frame stays empty)."""
    rnd = random.Random(seed)
    frames = []
    for _ in range(n):
        for _ in range(tries):
            cand = draw(rnd)
            trial = dict(base, frames=frames + [cand])
            try:
                c.validate(trial)
            except AssertionError:
                continue
            frames.append(cand)
            break
        else:
            frames.append(None)
    return dict(base, frames=frames)


def grow_words(base, n, seed, p_idle):
    """As grow(), with descriptors from random words: P[n] = P[n-1] + D[n] (mod 8)."""
    rnd = random.Random(seed)
    frames, pos = [], 0
    for _ in range(n):
        for _ in range(60):
            if rnd.random() < p_idle:
                cand, new = None, pos
            else:
                d, f = c.codewords([rnd.randrange(64)])[0]
                new = (pos + d) % 8
                cand = (new, f)
            try:
                c.validate(dict(base, frames=frames + [cand]))
            except AssertionError:
                continue
            frames.append(cand)
            pos = new
            break
        else:
            frames.append(None)
    return dict(base, frames=frames)


def final_cases():
    d0 = c.DELTA0
    # n_pre = 1: idle-hold window t_hold - delta0 = 107 ps. Same-F pairs with
    # start spacing 11 delta0 (request in TAIL), 12 (request in the idle-hold
    # window: warm) and 13 (after it: off, cold restart). Instance b has a
    # longer tail and hold, other levels and edges.
    hold_idle = dict(name='hold_idle', vin=1.0, n_pre=1, delta0=d0, t0=T0, rst=[(0.0, 0.3e-9)],
                     instances=[dict(name='a', params={}),
                                dict(name='b', params=dict(t_tail=120e-12, t_hold=380e-12, vdd=1.2, tr=3e-12))],
                     frames=[(1, 6), (7, 3), (2, 3), (5, 5), (6, 1), (2, 1), (4, 4), (5, 2), (2, 2), (3, 7),
                             (7, 0), (2, 0), (0, 6)])
    # n_pre = 8 and a long hold: when a new branch is requested, the branch of
    # the previous symbol is still busy and an older one waits in idle HOLD,
    # so the new branch takes over the idle one (positions in 0..3 keep the
    # previous window open at each request)
    preempt = grow(dict(name='preempt', vin=1.0, n_pre=8, delta0=d0, t0=T0, rst=[],
                        instances=[dict(name='a', params=dict(t_hold=2.5e-9)),
                                   dict(name='b', params=dict(t_hold=1.4e-9, t_tail=400e-12, t_conf=500e-12))]),
                   40, 5, lambda rnd: None if rnd.random() < 0.05 else (rnd.randrange(4), rnd.randrange(8)))
    # long random sequence from random words, default grid, with empty frames
    words = grow_words(dict(name='random_words', vin=1.0, n_pre=2, delta0=d0, t0=T0, rst=[(0.0, 0.3e-9)],
                            instances=[dict(name='a', params={}),
                                       dict(name='b', params=dict(t_tail=300e-12, t_hold=750e-12,
                                                                  t_conf=350e-12, vdd=1.3, tr=3e-12))]),
                       110, 20261023, p_idle=0.15)
    # other grid, n_pre = 15: three supply intervals overlap, so requests are
    # dropped (instance a often, b with its short tail rarely) and idle HOLDs
    # are taken over
    dense = grow(dict(name='random_dense', vin=0.9, n_pre=15, delta0=60e-12, t0=T0, rst=[],
                      instances=[dict(name='a', params=dict(t_tail=300e-12, t_hold=1.2e-9, t_conf=790e-12,
                                                            vth=0.4)),
                                 dict(name='b', params=dict(t_tail=100e-12, t_hold=0.0, t_conf=150e-12,
                                                            vth=0.35, vdd=0.8, tr=1.5e-12))]),
                 90, 19, lambda rnd: None if rnd.random() < 0.08 else (rnd.randrange(8), rnd.randrange(8)))
    return [reset_phases(), hold_idle, preempt, words, dense]


def reset_phases():
    """Resets at chosen phases of the activity (S7)."""
    d0 = c.DELTA0
    base = dict(name='reset_phases', vin=1.0, n_pre=3, delta0=d0, t0=T0, rst=[(0.0, 0.3e-9)],
                instances=[dict(name='a', params=dict(t_hold=700e-12, t_tail=200e-12)),
                           dict(name='b', params=dict(t_hold=0.0, t_conf=300e-12))],
                frames=[(2, 1), (5, 4), (0, 1), None, None, (3, 6), (6, 2), (1, 6), (4, 3), (7, 5),
                        (2, 0), None, (5, 0), (1, 7), (6, 2), (3, 2), None, (0, 4), (4, 4), (2, 6),
                        (7, 1), (5, 3), None, (1, 5), (3, 5)])
    w = c.windows(base)
    rst = [(0.0, 0.3e-9),
           (w[1]['p'] + 60e-12, w[1]['s'] - 40e-12),     # during a precharge: the grant is cancelled
           (w[3]['s'] + 300e-12, w[4]['p'] - 120e-12),   # gate high: gate and branch drop at once
           (w[7]['e'] + 80e-12, w[7]['e'] + 400e-12),    # during TAIL (instance a) / after it
           (w[9]['p'] - 50e-12, w[9]['p'] + 50e-12),     # request while rst is high: ignored
           (w[12]['e'] + 400e-12, w[12]['e'] + 520e-12),  # idle HOLD of instance a
           (w[16]['p'] - 30e-12, w[16]['s'] - 60e-12)]   # request ignored, rst falls before its window
    return c.validate(dict(base, rst=rst))
