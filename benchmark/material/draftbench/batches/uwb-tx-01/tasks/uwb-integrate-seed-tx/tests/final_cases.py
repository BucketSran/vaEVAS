"""Final-evaluation cases added to the public ones (kept out of the solver image)."""
import random

import contract as c


def final_cases():
    # n_pre = 1 (idle-hold window 107 ps): same-carrier pairs held through the
    # idle window (dP = -4), held from TAIL (-5), touching (-7) and restarted
    # cold (-3, 0); nondefault gain, common mode, start code and carriers in
    # descending order; another reference phase
    rnd = random.Random(31)
    pairs = [(5, 2), (1, 2), (3, 7), (7, 4), (0, 4), (2, 5), (6, 1), (3, 1), (5, 0), (4, 6), (0, 6),
             (3, 3), (6, 0), (1, 0), (4, 5), (2, 3), (2, 3), (6, 4), (7, 7), (3, 7), (0, 7), (5, 1)]
    cws = pairs + [(rnd.randrange(8), rnd.randrange(8)) for _ in range(18)]
    hold = c.make_case('params_hold', dict(n_pre=1, n_win=3, code_init=100, g_pa=0.6, vcm=0.65,
                                           **{f'f{k}': 7.6e9 - k * 0.45e9 for k in range(8)}),
                       c.symbols_for_codewords(cws), ref_delay=5.3e-9, t_cal=47e-9, data_after_done=31.7e-9)
    # n_pre = 3, high start code, large gain, low common mode, permuted carriers,
    # polarity high, another reference and data phase
    rnd = random.Random(20261024)
    fk = [6.3e9, 4.2e9, 7.4e9, 5.0e9, 3.8e9, 6.8e9, 4.6e9, 5.6e9]
    other = c.make_case('params_permuted', dict(n_pre=3, n_win=1, code_init=1023, g_pa=1.5, vcm=0.35,
                                                **{f'f{k}': fk[k] for k in range(8)}),
                        [rnd.randrange(64) for _ in range(60)], pol=1, ref_delay=7.1e-9, t_cal=33e-9,
                        data_after_done=7.3e-9)
    # the reference stops during the search: fail, no transmission
    base = dict(ref_delay=0.37e-9, t_cal=40e-9, params=dict(n_win=2))
    t_lost = base['t_cal'] + 4.6 * (c.N_SETTLE + 2) * c.T_REF
    t_fail = t_lost + 87 * c.T_RO      # 65 RO periods after the last reference edge, with margin
    rnd = random.Random(5)
    lost = c.make_case('ref_lost', dict(n_win=2, code_init=300), [rnd.randrange(64) for _ in range(24)],
                       ref_stop=t_lost, t_start=t_fail + 10e-9)
    # reset during a pulse: RF stops at once, done falls, the RO returns to code_init
    rnd = random.Random(9)
    case = dict(ref_delay=0.37e-9, t_cal=40e-9, params=dict(n_win=1))
    t_start = c.predict_done(case) + 20e-9
    t_rst = t_start + 20.22e-9         # inside the pulse window of word 10 (from an author run)
    reset = c.make_case('reset', dict(n_win=1, code_init=700), [rnd.randrange(64) for _ in range(30)],
                        t_start=t_start, rst=[(t_rst, t_rst + 300e-12)])
    return [hold, other, lost, reset]
