"""Final-evaluation cases added to the public ones (kept out of the solver image)."""
import random

import contract as c


def random_items(seed, frames, counts):
    """counts[i] descriptors in frame frames[i] with random P/F/pol and latch phases."""
    rnd = random.Random(seed)
    out, last = [], None
    for k, n in zip(frames, counts):
        if n == 1:
            fr = [rnd.uniform(0.04, 0.96)]
        elif n == 2:
            a = rnd.uniform(0.04, 0.45)
            fr = [a, rnd.uniform(a + 0.38, 0.96)]
        else:
            fr = []
        for f in fr:
            if last is not None and (k + f) - last < 0.4:   # keep words >= 0.4 T apart
                f = last + 0.4 - k
            out.append((k, f, rnd.randrange(8), rnd.randrange(8), rnd.randrange(2)))
            last = k + f
    return out


def final_cases():
    g = c.Grid(288)
    # two instances on the same taps: precharge 15 tap intervals (it starts in
    # the scheduling frame and overlaps the other lane) and no precharge
    seq = [(0, 5, 1), (7, 2, 0), (0, 2, 1), (3, 3, 0), (7, 6, 1), (1, 6, 0), (6, 0, 0), (2, 7, 1),
           (5, 1, 0), (4, 4, 1), (0, 4, 0), (7, 4, 1), (7, 3, 0), (0, 1, 1)]
    fracs = [0.05, 0.55, 0.95, 0.4, 0.75, 0.2, 0.6, 0.97, 0.3, 0.8, 0.1, 0.5, 0.9, 0.35]
    pre = dict(name='pre15_pre0', code=288, phase0=0.0, vin=1.0, scramble=False,
               instances=[dict(name='a', params=dict(n_pre=15)), dict(name='b', params=dict(n_pre=0))],
               descs=c.descs_at(g, [(2 + i, f, *d) for i, (d, f) in enumerate(zip(seq, fracs))]),
               en=[(0.0, 1)], rst=[(0.0, g.gap(0, 10))], stop=g.at(19, 0.5))

    # nondefault parameters, low input level, another oscillator phase;
    # overruns at close word spacing (>= t_ovr + 100 ps for instance a)
    g2 = c.Grid(288, 0.2)
    a = dict(n_width=7, n_pre=4, t_ovr=350e-12, vdd=0.9, vth=0.4, tr=5e-12)
    b = dict(n_width=1, n_pre=1, t_ovr=60e-12)
    items = [(2, 0.3, 6, 2, 1), (3, 0.1, 1, 5, 0), (3, 0.42, 7, 5, 1), (4, 0.7, 0, 5, 0),
             (5, 0.5, 4, 0, 1), (6, 0.05, 2, 3, 0), (6, 0.37, 5, 6, 1), (6, 0.69, 3, 7, 0),
             (8, 0.9, 7, 1, 1), (9, 0.6, 0, 1, 0), (10, 0.2, 2, 4, 1), (11, 0.55, 6, 6, 0),
             (12, 0.15, 1, 2, 1), (12, 0.8, 4, 3, 1), (13, 0.45, 7, 0, 0)]
    params = dict(name='params_two_instances', code=288, phase0=0.2, vin=0.8, scramble=False,
                  instances=[dict(name='a', params=a), dict(name='b', params=b)],
                  descs=c.descs_at(g2, items), en=[(0.0, 1)], rst=[(0.0, g2.gap(0, 10))],
                  stop=g2.at(17, 0.5))

    # another oscillator code and phase, random words with empty frames and
    # overruns, descriptor bits valid only around the strobe, en low over the
    # frame edges 13..16 (a window scheduled at edge 12 must still complete;
    # the word of frame 15 stays pending through edge 16 and goes out at 17)
    g3 = c.Grid(340, 0.43)
    frames = list(range(2, 32))
    counts = [1, 1, 0, 2, 1, 1, 0, 1, 1, 2, 1, 2, 1, 1, 0, 1, 1, 0, 2, 1, 1, 0, 1, 2, 1, 1, 0, 1, 2, 1]
    rnd = dict(name='random_code340', code=340, phase0=0.43, vin=1.0, scramble=True,
               instances=[dict(name='a', params={})],
               descs=c.descs_at(g3, random_items(20261023, frames, counts)),
               en=[(0.0, 1), (g3.at(12, 0.3), 0), (g3.at(16, 0.7), 1)], rst=[(0.0, g3.gap(0, 10))],
               stop=g3.at(34, 0.5))

    # resets in the middle of activity (times for the default instance a;
    # instance b has longer precharge and shorter windows on the same inputs)
    items = [(2, 0.5, 2, 1, 0), (3, 0.4, 5, 4, 1), (4, 0.6, 1, 6, 1),   # lanes a, b, a
             (7, 0.3, 4, 2, 0),                    # pending when reset R1 rises
             (7, 0.85, 5, 3, 0),                   # after R1: no overrun, lane a; R2 hits its precharge
             (9, 0.8, 7, 2, 1), (10, 0.5, 0, 5, 0),  # R3: rf_a of the first and pre_b of the second
             (12, 0.1, 6, 6, 1),                   # latched while rst is high: ignored
             (13, 0.5, 3, 7, 1),                   # R4 in the middle of its RF window
             (15, 0.7, 6, 1, 0), (16, 0.5, 0, 0, 1), (17, 0.3, 2, 6, 0),
             (18, 0.2, 4, 5, 1), (18, 0.7, 1, 2, 0),  # overrun; R5 rises during its pulse
             (19, 0.4, 7, 4, 1)]                   # after R5: lane a again
    rst = [(0.0, g.gap(0, 10)),
           (g.gap(7, 9), g.gap(7, 11)),             # R1: only a pending word
           (g.gap(9, 3), g.gap(9, 6)),              # R2: lane a precharge (taps 3..5 of frame 9)
           (g.gap(11, 14), g.gap(12, 3)),           # R3: rf_a high, pre_b high; spans the frame-12 edge
           (g.gap(15, 6), g.gap(15, 9)),            # R4: rf_a high
           (g.gap(18, 12), g.gap(18, 14))]          # R5: overrun high, a word pending, lane a scheduled (b: in precharge)
    resets = dict(name='reset_activity', code=288, phase0=0.0, vin=1.0, scramble=False,
                  instances=[dict(name='a', params={}), dict(name='b', params=dict(n_pre=6, n_width=5))],
                  descs=c.descs_at(g, items), en=[(0.0, 1)], rst=rst, stop=g.at(22, 0.5))
    return [pre, params, rnd, resets]
