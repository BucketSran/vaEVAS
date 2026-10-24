"""Source-position history captures, source RN forcing and structural refusals."""
GUARDS = ['LANG', 'DYNAMICS', 'TRANSITION', 'COMPOSE', 'EVENT-ORDER']

import math
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def execute(body, declarations, times, *, sources=None, stop=1):
    p = compile_sources({'history-input.va': model(body, declarations)}, [instance()])
    result = transient(p, sources or {'u': [[0, 0], [stop, 3]]}, times,
                       stop=stop, max_step=.125, vabstol=1e-8, reltol=0, kernel=KERNEL)
    return result


def values(result, node):
    return [r['voltages'][result['nodes'].index(node)] for r in result['solutions']]


class HistoryInputCaptures(unittest.TestCase):
    def test_held_rebind_uses_capture_before_later_overwrite(self):
        result = execute('''@(initial_step) q=0; @(timer(0.5)) q=1;
            a=q; V(y,r)<+transition(a,0,0.125); a=9;''', 'real q,a;',
                         [0, .25, .5, .5625, .625, 1])
        self.assertEqual(values(result, 'y'), [0, 0, 0, .5, 1, 1])

    def test_two_call_sites_keep_distinct_versions_of_same_binding(self):
        result = execute('''@(initial_step) q=0; @(timer(0.5)) q=1;
            a=q; V(y,r)<+transition(a,0,0.125);
            a=1-q; V(z,r)<+transition(a,0,0.25); a=9;''',
                         'real q,a; electrical z;', [0, .5, .5625, .625, .75, 1])
        self.assertEqual(values(result, 'y'), [0, 0, .5, 1, 1, 1])
        self.assertEqual(values(result, 'dut:z'), [1, 1, .75, .5, 0, 0])

    def test_source_rn_integral_keeps_independent_history_under_extra_queries(self):
        body = 'rate=1/(1+V(u,r)*V(u,r)); V(y,r)<+idt(rate,0.25);'
        sparse = [0, .5, .75, 1]
        dense = [i/16 for i in range(17)]
        a = execute(body, 'real rate;', sparse)
        b = execute(body, 'real rate;', dense)
        for t, got in zip(dense, values(b, 'y')):
            self.assertLessEqual(abs(got-(.25+math.atan(3*t)/3)), 1e-8)
        for t, got in zip(sparse, values(a, 'y')):
            self.assertLessEqual(abs(got-values(b, 'y')[dense.index(t)]), 1e-8)
        self.assertEqual(a['transient']['events'], b['transient']['events'])

    def test_zero_weight_internal_rn_feedback_is_not_source_forcing(self):
        with self.assertRaises(KernelError) as caught:
            execute('rate=V(u,r)+0*V(y,r); V(y,r)<+idt(rate,0.25);',
                    'real rate;', [0, 1])
        self.assertEqual(caught.exception.diagnostic['kind'], 'unsupported_history_input')

    def test_inactive_numeric_domain_is_not_executed_by_history_metadata(self):
        result = execute('''if(V(u,r)>2) rate=1/(V(u,r)-V(u,r));
            else rate=1/(1+V(u,r)*V(u,r)); V(y,r)<+idt(rate,0.25);''',
                         'real rate;', [0, .5, 1], sources={'u': [[0, 0], [1, 0]]})
        self.assertEqual(values(result, 'y'), [.25, .75, 1.25])

    def test_adjacent_rn_cuts_cannot_erase_an_integral_pulse(self):
        # RN(t) is nextUp(.5) between .5+2^-54 and .5+3*2^-54.
        # Rate 2^53 therefore has integral one, even though binary side
        # witnesses jump over this complete mode. Such a window must reject
        # until the integrator supports exact multi-cut window propagation.
        with self.assertRaises(KernelError) as caught:
            execute('''x=V(u,r); if(x>0.5) begin
                if(x>0.5000000000000001) rate=0; else rate=9007199254740992;
                end else rate=0; V(y,r)<+idt(rate,0);''',
                    'real x,rate;', [0, .75, 1], sources={'u': [[0, 0], [1, 1]]})
        self.assertEqual(caught.exception.diagnostic['kind'], 'condition_precision')


if __name__ == '__main__':
    unittest.main()
