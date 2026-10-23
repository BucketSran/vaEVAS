"""Final-evaluation cases added to the public ones (kept out of the solver image)."""
import random

import contract as c


def final_cases():
    t0 = 2e-9
    a = dict(vdd=0.9, vth=0.4, tr=5e-12, t_enc=25e-12, t_ev=60e-12, t_pw=300e-12)
    params = dict(name='params_two_instances', vin=0.9,
                  instances=[dict(name='a', params=a), dict(name='b', params={})],
                  words=c.random_words(20261023, 300, t0, 0.5e-9, 2.2e-9), rst=[(0.0, 1e-9)])
    words = c.random_words(7, 24, t0, 1.2e-9, 1.6e-9)
    tc = [t for t, _ in words]
    rst = [(0.0, 1e-9),
           (tc[3] + 5e-12, tc[4] - 600e-12),          # before t_enc: the update is cancelled
           (tc[8] - 100e-12, tc[8] + 100e-12),        # word taken while reset is high: ignored
           (tc[12] + 200e-12, tc[13] - 50e-12),       # enc_valid high at reset; word 50 ps after release
           (tc[18] + 20e-12, tc[19] - 600e-12)]       # after t_enc, before t_ev
    phases = dict(name='reset_phases', vin=1.0, instances=[dict(name='a', params={})], words=words, rst=rst)
    dense = dict(name='dense', vin=1.0, instances=[dict(name='a', params={})],
                 words=c.random_words(99, 200, t0, 0.5e-9, 0.52e-9), rst=[(0.0, 1e-9)])
    return [params, phases, dense]
