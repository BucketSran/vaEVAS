"""An integer's current ordinary value is distinct from its preserved event state."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
from fractions import Fraction as Q
from pathlib import Path
import unittest
from test_affine import KERNEL
from evas import CompileError, Instance, compile_sources, transient
from evas.ir import Affine, Binary

ORIGINAL = Path(__file__).with_name('fixtures').joinpath('ordinary114_current_mux.va').read_text()


def build(text=ORIGINAL):
    return compile_sources({'ordinary114.va': text}, [Instance('dut', 'analog_mux_threshold',
        dict(vin1='vin1', vin2='vin2', vsel='vsel', vout='vout'))])


class OrdinaryIntegerCurrentAlias(unittest.TestCase):
    def response(self, p, times):
        return transient(p, dict(vin1=[[0., .75], [2., .75]],
                                  vin2=[[0., .25], [2., .25]],
                                  vsel=[[0., 0.], [1., 1.], [2., 0.]]),
                         list(times), stop=2., max_step=.125, reltol=0., vabstol=1e-10,
                         kernel=KERNEL)

    def test_original114_current_input_select_retains_cross_state(self):
        p = build()
        self.assertEqual([(s.name, s.kind) for s in p.states], [('selector', 'integer')])
        self.assertEqual(len(p.events), 2)
        # Verify the actual public IR's original guard, directions and writes.
        # This polynomial reader compares against V(vsel)-V(0)-binary64(.45), rather
        # than synthesizing a second event program or invoking a root finder.
        def linear(expr):
            if isinstance(expr, Affine):
                row = {term.node: Q(term.coefficient) for term in expr.terms}
                return Q(expr.constant), row
            self.assertIsInstance(expr, Binary)
            a, an = linear(expr.left)
            b, bn = linear(expr.right)
            if expr.op == 'add':
                return a+b, {n: an.get(n, Q(0))+bn.get(n, Q(0)) for n in an.keys() | bn.keys()}
            self.assertEqual(expr.op, 'multiply')
            self.assertFalse(an and bn)
            return a*b, ({n: c*b for n, c in an.items()} if an else
                         {n: a*c for n, c in bn.items()})

        for event, direction, value, line in zip(p.events, (1, -1), (1., 0.), (17, 19)):
            self.assertEqual(event.trigger.kind, 'cross')
            self.assertEqual(event.trigger.direction, direction)
            constant, terms = linear(event.trigger.guard)
            self.assertEqual(constant, -Q(.45))
            self.assertEqual({n: c for n, c in terms.items() if c}, {p.nodes.index('vsel'): Q(1), p.nodes.index('0'): Q(-1)})
            self.assertEqual(event.origin.line, line)
            self.assertEqual(len(event.body), 1)
            self.assertEqual(event.body[0].state, 0)
            self.assertIsInstance(event.body[0].rhs, Affine)
            self.assertEqual((event.body[0].rhs.constant, event.body[0].rhs.terms), (value, ()))
        times = [k/4 for k in range(9)]
        response = self.response(p, times)
        node = response['nodes'].index('vout')
        # vsel=t until1, then2-t. The original strict threshold is .45.
        # Both source inputs are exact constants: .75 above, .25 at/below.
        expected = [.75 if (t if t <= 1 else 2-t) > .45 else .25 for t in times]
        self.assertEqual([row['voltages'][node] for row in response['solutions']], expected)
        records = response['transient']['events']
        self.assertEqual([record['event'] for record in records], [0, 1])
        self.assertEqual([record['before'] for record in records], [[0.], [1.]])
        self.assertEqual([record['after'] for record in records], [[1.], [0.]])
        for record, root in zip(records, (.45, 1.55)):
            self.assertAlmostEqual(record['time'], root, delta=2e-12)
        self.assertEqual(response['transient']['states'],
                         [[0.], [0.], [1.], [1.], [1.], [1.], [1.], [0.], [0.]])

    def test_extra_query_points_preserve_original_event_results(self):
        p = build()
        times = [k/4 for k in range(9)]
        sparse = self.response(p, times)
        dense = self.response(p, [k/16 for k in range(33)])
        node = sparse['nodes'].index('vout')
        self.assertEqual([r['voltages'][node] for r in sparse['solutions']],
                         [dense['solutions'][k*4]['voltages'][node] for k in range(9)])
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])

    def test_original_tree_and_event_state_roles_remain_rejected(self):
        assignment = 'selector = (V(vsel) > vth) ? 1 : 0;'
        cases = {
            'event_read': ORIGINAL.replace('selector = 1;', 'selector = selector + 1;'),
            'hidden_event_read': ORIGINAL.replace('selector = 1;',
                'selector = 1 + 0 * selector;'),
            'read_before_current_write': ORIGINAL.replace(assignment,
                'vout_val = selector; ' + assignment),
            'partial_current_write': ORIGINAL.replace(assignment,
                'if (V(vsel) > vth) selector = 1;'),
            'second_current_write': ORIGINAL.replace('if (selector == 1)',
                'selector = 1; if (selector == 1)'),
            'state_dependency': ORIGINAL.replace(assignment,
                'selector = selector + 0;'),
            'hidden_time': ORIGINAL.replace(assignment,
                'selector = (V(vsel) > vth) ? 1 : 0*$abstime;'),
            'hidden_history': ORIGINAL.replace(assignment,
                'selector = (V(vsel) > vth) ? 1 : 0*idt(V(vsel),0);'),
            'output_probe': ORIGINAL.replace(assignment,
                'selector = (V(vout) > vth) ? 1 : 0;'),
            'hidden_signed32_overflow': ORIGINAL.replace(assignment,
                'selector = (1 > 0) ? 1 : 2147483648;'),
        }
        for name, text in cases.items():
            with self.subTest(name=name), self.assertRaises(CompileError):
                build(text)

    def test_input_port_driven_by_another_instance_is_not_a_current_source(self):
        driver = ('`include "disciplines.vams"\nmodule driver(y); output y; electrical y; '
                  'analog V(y)<+0.9; endmodule')
        with self.assertRaises(CompileError):
            compile_sources({'ordinary114.va': ORIGINAL, 'driver.va': driver},
                            [Instance('drive', 'driver', {'y': 'vsel'}),
                             Instance('dut', 'analog_mux_threshold',
                                      dict(vin1='vin1', vin2='vin2', vsel='vsel', vout='vout'))])
