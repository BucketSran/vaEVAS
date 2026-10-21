"""Ordered nonlinear samples of certified internal electrical providers.

The oracle is a Fraction recurrence over exact binary inputs. Internal producer
ports are real circuit equations, never extra entries in the driven input map.
"""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER', 'TIMED-OPERATOR']

from fractions import Fraction as Q
import os
from pathlib import Path
import unittest

from evas import Instance, KernelError, compile_sources, transient

KERNEL = Path(os.environ.get('EVAS_KERNEL',
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel'))
SOURCE = '''`include "disciplines.vams"
module producer(u,p);
input u;output p;electrical u,p;parameter real gain=0.5;
analog begin V(p)<+gain*V(u);end
endmodule
module consumer(p,y);
input p;output y;electrical p,y;real a,b,q;
analog begin
 @(initial_step)begin a=0;b=0;q=0;end
 @(timer(0.25,0.25))begin a=V(p);b=a*a;q=b+a;end
 V(y)<+transition(q,0,0.03125,0.03125);
end
endmodule
'''
SPARSE = [0., .125, .375, .625, .875, 1.]


# PENDING CAPABILITY (Issue214, group SAMPLE). The five positive contracts below
# describe nonlinear samples of internal electrical providers, which the kernel
# does not implement yet: today they stop with
#   unsupported_transient: nonlinear sampled arithmetic requires
#   state-independent driven voltage inputs
# They are kept as expected failures so the contract stays executable; remove
# the decorator when the capability lands (an unexpected success will say so).
# The two refusal controls at the end already hold and are not decorated.


def program(*, reverse=False, sequential=False, hidden=False):
    source = SOURCE
    if sequential:
        source = source.replace('a=V(p);b=a*a;q=b+a;',
                                'a=V(p);a=a+0.25;b=a*a;a=a+0.25;q=b+a;')
    if hidden:
        source = source.replace('electrical p,y;real', 'electrical p,y,unknown;real')
        source = source.replace('a=V(p);', 'a=V(p)+0*V(unknown);')
    instances = [
        Instance('PA', 'producer', dict(u='u', p='pa'), dict(gain=.5)),
        Instance('PB', 'producer', dict(u='u', p='pb'), dict(gain=.25)),
        Instance('A', 'consumer', dict(p='pa', y='ya')),
        Instance('B', 'consumer', dict(p='pb', y='yb')),
    ]
    if reverse:
        instances.reverse()
    return compile_sources({'internal-sample.va': source}, instances)


def run(p, times=SPARSE, **kwargs):
    options = {'vabstol': 1e-10}
    options.update(kwargs)
    return transient(p, {'u': [[0., 1.], [1., 1.]]}, times,
                     stop=1., max_step=.0625, kernel=KERNEL,
                     reltol=0, **options)


def values(response, node):
    index = response['nodes'].index(node)
    return [row['voltages'][index] for row in response['solutions']]


class InternalVoltageSampleContract(unittest.TestCase):
    def assert_answers(self, response, times, a, b):
        for node, expected in [('ya', a), ('yb', b)]:
            for time, observed in zip(times, values(response, node)):
                oracle = Q(0) if time < Q(1, 4) else expected
                self.assertLessEqual(abs(Q(observed) - oracle), Q(1e-10))
        self.assertTrue(all(row['max_residual_ratio'] <= 1 for row in response['solutions']))

    @unittest.expectedFailure
    def test_internal_affine_providers_feed_ordered_nonlinear_samples(self):
        p = program()
        response = run(p)
        # a_A=1/2 -> a_A^2+a_A=3/4; a_B=1/4 ->5/16.
        self.assert_answers(response, SPARSE, Q(3, 4), Q(5, 16))

    @unittest.expectedFailure
    def test_each_assignment_reads_its_source_position(self):
        response = run(program(sequential=True))
        # First a=p+1/4, then b=a^2, then a=p+1/2.
        oracle = lambda p: (p+Q(1, 4))**2 + p+Q(1, 2)
        self.assert_answers(response, SPARSE, oracle(Q(1, 2)), oracle(Q(1, 4)))

    @unittest.expectedFailure
    def test_query_and_instance_order_preserve_samples_and_events(self):
        dense = sorted(set(SPARSE + [k/64 for k in range(65)]))
        for reverse in (False, True):
            p = program(reverse=reverse)
            sparse, extra = run(p), run(p, dense)
            self.assert_answers(sparse, SPARSE, Q(3, 4), Q(5, 16))
            self.assertEqual(sparse['transient']['events'], extra['transient']['events'])
            for node in ('ya', 'yb'):
                self.assertEqual(values(sparse, node),
                                 [values(extra, node)[dense.index(t)] for t in SPARSE])

    @unittest.expectedFailure
    def test_internal_source_band_reaches_physical_output(self):
        response = run(program(), source_errors={'u': .125}, vabstol=.2)
        node = response['nodes'].index('ya')
        # p_A=[7/16,9/16], p^2+p is monotone on that interval.
        lower, upper = Q(161, 256), Q(225, 256)
        for time, boxes in zip(SPARSE, response['observation_evidence']['voltage_bounds_V']):
            if time > .25:
                lo, hi = boxes[node]
                self.assertLessEqual(Q(lo), lower)
                self.assertGreaterEqual(Q(hi), upper)

    @unittest.expectedFailure
    def test_same_band_cannot_pass_a_tight_voltage_budget(self):
        with self.assertRaises(KernelError) as caught:
            run(program(), source_errors={'u': .125}, vabstol=1e-6)
        self.assertIn(caught.exception.detail['kind'], ['waveform_accuracy', 'event_accuracy'])

    def test_zero_weight_unknown_provider_still_refuses(self):
        with self.assertRaises(KernelError) as caught:
            run(program(hidden=True))
        self.assertIn(caught.exception.detail['kind'], ['unsupported_transient', 'unsupported_cross'])

    def test_same_time_nonlinear_electrical_feedback_still_refuses(self):
        source = '''`include "disciplines.vams"
module feedback(y);output y;electrical y,p;real q;
analog begin @(initial_step)q=0;
 @(timer(0.25))q=V(p)*V(p);
 V(p)<+V(y)+0.5;V(y)<+q;
end endmodule'''
        p = compile_sources({'feedback.va': source}, [Instance('F', 'feedback', dict(y='y'))])
        with self.assertRaises(KernelError) as caught:
            transient(p, {}, SPARSE, stop=1., max_step=.0625,
                      kernel=KERNEL, reltol=0, vabstol=1e-10)
        self.assertIn(caught.exception.detail['kind'], ['unsupported_transient', 'unsupported_cross'])


if __name__ == '__main__':
    unittest.main()
