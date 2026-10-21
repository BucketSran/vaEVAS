"""A same-time batch may mix a nonlinear sampled event with an event that
samples a node forced by a positive-edge transition.

The transition output is continuous at the event time, so its sampled value
does not depend on the targets assigned in the same batch. A node forced
directly by a state assigned in that batch remains a joint voltage assignment.
"""
from fractions import Fraction as Q
import os
from pathlib import Path
import unittest

from evas import Instance, KernelError, compile_sources, transient

KERNEL = Path(os.environ.get('EVAS_KERNEL',
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel'))
SOURCE = '''`include "disciplines.vams"
module amp(u,y);
input u;output y;electrical u,y;real g,q;
analog begin
 @(initial_step)begin g=0;q=0;end
 @(timer(0.25,0.25))begin g=g+1;q=g*V(u);end
 V(y)<+transition(q,0,0.03125,0.03125);
end
endmodule
module mon(y,z);
input y;output z;electrical y,z;real s;
analog begin
 @(initial_step)s=0;
 @(timer(0.25,0.25))s=V(y);
 V(z)<+transition(s,0,0.03125,0.03125);
end
endmodule
'''
TIMES = [0., .125, .375, .625, .875, 1.]


def program(source=SOURCE, reverse=False):
    instances = [Instance('A', 'amp', dict(u='u', y='y')),
                 Instance('M', 'mon', dict(y='y', z='z'))]
    if reverse:
        instances.reverse()
    return compile_sources({'batch.va': source}, instances)


def run(p):
    return transient(p, {'u': [[0., 1.], [1., 1.]]}, TIMES, stop=1.,
                     max_step=.0625, kernel=KERNEL, reltol=0, vabstol=1e-10)


def values(response, node):
    index = response['nodes'].index(node)
    return [row['voltages'][index] for row in response['solutions']]


class TransitionProviderBatch(unittest.TestCase):
    def test_monitor_samples_continuous_transition_output(self):
        # q_k = k after the k-th tick; the monitor reads y(tau_k) = q_{k-1}.
        y = [0, 0, 1, 2, 3, 4]
        z = [0, 0, 0, 1, 2, 3]
        for reverse in (False, True):
            response = run(program(reverse=reverse))
            for node, oracle in (('y', y), ('z', z)):
                for time, observed, expected in zip(TIMES, values(response, node), oracle):
                    if time in (0., 1.):
                        continue  # 1.0 is a tick instant itself
                    self.assertLessEqual(abs(Q(observed) - expected), Q(1e-10), (node, time))

    def test_directly_forced_assigned_state_still_refuses(self):
        source = SOURCE.replace('V(y)<+transition(q,0,0.03125,0.03125);', 'V(y)<+q;')
        with self.assertRaises(KernelError) as caught:
            run(program(source))
        self.assertIn(caught.exception.detail['kind'],
                      ['unsupported_cross', 'unsupported_transient', 'unsupported_condition'])


if __name__ == '__main__':
    unittest.main()
