"""Final-evaluation cases added to the public ones (kept out of the solver image)."""
import random

import contract as c


def final_cases():
    # n_pre = 1: the idle-hold window is t_hold - delta = 107 ps; same-carrier
    # starts 11, 12 and 13 taps apart give a request in TAIL, in the idle-hold
    # window and after it (off, cold restart)
    hold_idle = dict(name='hold_idle', bench=dict(n_pre=1),
                     words=c.words_for([(1, 6), (7, 3), (2, 3), (5, 5), (6, 1), (2, 1), (4, 4), (5, 2), (2, 2),
                                        (3, 7), (7, 0), (2, 0), (0, 6)]),
                     pols=[0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1], need=dict(warm_from_idle=1, warm=2))
    # t_hold = 2 ns keeps branches in idle HOLD, so new carriers take an idle
    # slot and returning carriers are granted from idle HOLD
    preempt = dict(name='preempt', bench=dict(t_hold=2e-9),
                   words=c.words_for([(3, 0), (2, 1), (5, 2), (1, 3), (6, 4), (0, 5), (4, 6), (7, 7), (2, 0), (5, 1)]),
                   pols=[0] * 10, need=dict(preempt=1, warm_from_idle=1))
    # n_pre = 4 (T_pre = 372 ps > t_hold): gaps of 129, 222 and 315 ps keep the
    # branch running, 408 ps turns it off
    long_pre = dict(name='long_precharge', bench=dict(n_pre=4),
                    words=c.words_for([(5, 0), (4, 1), (0, 1), (6, 7), (3, 2), (0, 2), (5, 3), (2, 5), (0, 5),
                                       (7, 4), (1, 6), (0, 6), (3, 0)]),
                    pols=[1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 1, 0], need=dict(warm=3))
    # carriers cycle, so no request is ever warm: the fault does not show here,
    # but supply, hold timeout and off timing must stay as they are
    rnd = random.Random(5)
    cyc = [(rnd.randrange(8), n % 8) for n in range(48)]
    cold = dict(name='cold_cycle', words=c.words_for(cyc), pols=[rnd.randrange(2) for _ in cyc],
                need=dict(cold=48))
    rnd = random.Random(31)
    random_a = c.random_case('random_a', 20261023, 80,
                             bench_over=dict(dpc_db=tuple(round(rnd.uniform(-6, 6), 2) for _ in range(8))),
                             need=dict(warm=2))
    random_b = c.random_case('random_b', 7741, 80,
                             bench_over=dict(n_pre=3, t_tail=100e-12, t_hold=300e-12, clk_delay=700e-12),
                             need=dict(warm=2))
    # n_pre = 15 and t_hold = 2.5 ns: drops on both lanes, preemption of idle
    # holds, and warm grants in PRECHARGE, ACTIVE, TAIL and HOLD together
    busy = c.random_case('busy', 4, 70, bench_over=dict(n_pre=15, t_hold=2.5e-9),
                         need=dict(drops=2, drop_lanes=2, preempt=2, warm_from_idle=2, warm_in_precharge=2, warm=2))
    return [hold_idle, preempt, long_pre, cold, random_a, random_b, busy]
