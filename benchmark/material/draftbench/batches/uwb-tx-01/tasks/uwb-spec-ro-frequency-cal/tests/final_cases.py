"""Final-evaluation cases added to the public ones (kept out of the solver image)."""
import contract as c

T = c.T_REF


def final_cases():
    # default parameters: the first window (n_settle = 2, n_win = 192, target 2688)
    # decides bit 9; a reset then ends the search. A full default calibration
    # (about 45 us) exceeds the simulator memory budget (see SOURCE.md).
    t_rst = 50e-9 + 196 * T
    first = dict(name='default_first_window', vin=1.0, ref=dict(delay=0.37e-9),
                 rst=[(0.0, 10e-9), (t_rst, t_rst + 50e-9)], cal=[50e-9],
                 instances=[c.inst('a')], stop=t_rst + 200e-9)

    # RO too fast (every bit cleared, code 0) and too slow (every bit kept, code 1023)
    p8 = dict(n_win=8)
    limits = dict(name='ro_limits', vin=1.0, ref=dict(delay=2.9e-9), rst=[(0.0, 10e-9)], cal=[47e-9],
                  instances=[c.inst('f', p8, dict(f0=700e6)), c.inst('s', p8, dict(f0=100e6, fstep=0.0))],
                  stop=47e-9 + c.cal_time(p8) + 200e-9)

    # done, frozen code, a second calibration, then a reset while idle
    p4 = dict(n_win=4)
    t1 = 50e-9
    t2 = t1 + c.cal_time(p4) + 300e-9
    t_r = t2 + c.cal_time(p4) + 300e-9
    recal = dict(name='recal', vin=1.0, ref=dict(delay=6.4e-9), rst=[(0.0, 10e-9), (t_r, t_r + 100e-9)],
                 cal=[t1, t2], instances=[c.inst('a', p4)], stop=t_r + 300e-9)

    # reset during a search, cal_start while rst is high (ignored), a new calibration,
    # and a cal_start while busy that restarts the search; nondefault code_init
    pr = dict(n_win=4, code_init=77)
    per_bit = (2 + 4) * T
    t_c1 = 50e-9
    t_rst2 = t_c1 + 3.5 * per_bit
    t_c2 = t_rst2 + 0.4e-6
    t_c3 = t_c2 + 4.3 * per_bit
    reset = dict(name='reset_restart', vin=1.0, ref=dict(delay=18.6e-9),
                 rst=[(0.0, 10e-9), (t_rst2, t_rst2 + 0.22e-6)],
                 cal=[t_c1, t_rst2 + 0.12e-6, t_c2, t_c3], instances=[c.inst('a', pr)],
                 stop=t_c3 + c.cal_time(pr) + 200e-9)

    # nondefault ratio, tol, n_settle, n_lost and electrical parameters next to a
    # default instance; rst stays low, so code_init must show from the start
    pa = dict(ratio=13, tol=2, n_settle=4, n_win=6, n_lost=40, code_init=700,
              vdd=0.9, vth=0.4, tr=4e-12, t_cq=150e-12)
    pb = dict(n_win=6)
    params = dict(name='params_two_instances', vin=0.9, ref=dict(delay=15.9e-9), rst=[], cal=[300e-9],
                  instances=[c.inst('a', pa), c.inst('b', pb)],
                  stop=300e-9 + max(c.cal_time(pa), c.cal_time(pb)) + 200e-9)

    # the reference stops before cal_start: the watchdog counts from cal_start
    early = dict(name='ref_lost_before_start', vin=1.0, ref=dict(delay=3.3e-9, t_stop=200e-9),
                 rst=[(0.0, 10e-9)], cal=[300e-9],
                 instances=[c.inst('a', dict(n_lost=40)), c.inst('b', dict(n_lost=100, code_init=300))],
                 stop=600e-9)
    return [first, limits, recal, reset, params, early]
