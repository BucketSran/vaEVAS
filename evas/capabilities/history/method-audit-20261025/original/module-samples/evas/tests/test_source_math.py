"""Pure driven math composition must retain a certified root box, not just values."""
GUARDS = ['ANALOG', 'DYNAMICS', 'COMPOSE']

from decimal import Decimal, localcontext
import os
from pathlib import Path
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get('EVAS_TEST_KERNEL', DEFAULT_KERNEL))


def reference(x):
    # Independent positive-exponential formula; exact binary64 input and parameter.
    with localcontext() as ctx:
        ctx.prec = 120
        x = Decimal.from_float(x)
        z = x / Decimal.from_float(0.05)
        a, b = z.exp(), (-z).exp()
        return x * (a-b)/(a+b)


class SourceMath(unittest.TestCase):
    def program(self, rhs='V(u)*tanh(V(u)/smooth)', declarations=''):
        return compile_sources({'math.va': model('V(y)<+'+rhs+';',
            'parameter real smooth=0.05; '+declarations)}, [instance()])

    def run_value(self, program, x, **kwargs):
        return transient(program, {'u': [[0., x], [1., x]]}, [0., .5, 1.],
                         stop=1., max_step=.1, kernel=KERNEL, **kwargs)

    def test_product_contains_independent_decimal_root_in_reported_box(self):
        # Point accuracy alone cannot detect the historical absent certificate.
        program = self.program()
        for x in [-.95, -.04, 0., .02, .25, .55]:
            with self.subTest(x=x):
                response = self.run_value(program, x)
                idx = response['nodes'].index('y')
                self.assertEqual(response['nodes'], ['0', 'u', 'y'])
                for sample, bounds in zip(response['solutions'],
                        response['observation_evidence']['voltage_bounds_V']):
                    self.assertIsNotNone(bounds)
                    lo, hi = map(Decimal.from_float, bounds[idx])
                    self.assertLessEqual(lo, reference(x))
                    self.assertGreaterEqual(hi, reference(x))
                    self.assertLessEqual(lo, Decimal.from_float(sample['voltages'][idx]))
                    self.assertGreaterEqual(hi, Decimal.from_float(sample['voltages'][idx]))

    def test_true_source_error_is_propagated_and_amplification_is_refused(self):
        program = self.program('V(u)*tanh(V(u))')
        with self.assertRaises(KernelError) as caught:
            self.run_value(program, .1, source_errors={'u': 1e-6},
                           vabstol=1e-12, reltol=1e-10)
        self.assertEqual(caught.exception.detail['kind'], 'waveform_accuracy')
        # Even zero source error cannot erase uncertainty in the math certificate.
        amplified = self.program('1073741824*(V(u)*tanh(V(u))-0.009966799462495582)')
        with self.assertRaises(KernelError) as caught:
            self.run_value(amplified, .1, vabstol=1e-12, reltol=1e-10)
        self.assertEqual(caught.exception.detail['kind'], 'waveform_accuracy')

    def test_small_true_source_box_encloses_both_independent_endpoint_roots(self):
        response = self.run_value(self.program(), .1, source_errors={'u': 1e-14})
        idx = response['nodes'].index('y')
        # g(x)=x*tanh(x/smooth) increases for x>0. Both source endpoints
        # must survive the forcing transformation, even though nominal u is .1.
        for bounds in response['observation_evidence']['voltage_bounds_V']:
            self.assertIsNotNone(bounds)
            lo, hi = map(Decimal.from_float, bounds[idx])
            source = bounds[response['nodes'].index('u')]
            for x in source:
                self.assertLessEqual(lo, reference(x))
                self.assertGreaterEqual(hi, reference(x))

    def test_distinct_physical_shape_knots_are_explicitly_rejected(self):
        # The physical curve reaches 1 at 1/3, whereas nominal PWL reaches
        # 1 at .3. At .4 the true answer is tanh(1), not a new interpolation
        # of physical values sampled at nominal knots. This slice rejects it.
        shape = [dict(time_numerator='0', time_denominator='1', value_V=0.),
                 dict(time_numerator='1', time_denominator='3', value_V=1.),
                 dict(time_numerator='1', time_denominator='1', value_V=1.)]
        for rhs in ['V(u)*tanh(V(u))', 'V(u)*tanh(cos(V(u)))']:
            program = self.program(rhs)
            with self.subTest(rhs=rhs):
                with self.assertRaises(KernelError) as caught:
                    transient(program, {'u': [[0., 0.], [.3, 1.], [1., 1.]]}, [.4],
                              stop=1., max_step=1., kernel=KERNEL,
                              source_errors={'u': .125}, source_shapes={'u': shape})
                self.assertEqual(caught.exception.detail['kind'], 'unsupported_source_uncertainty')

    def test_zero_band_equal_shape_preserves_existing_native_math_consumers(self):
        # Curve::shaped proves zero-band equality at every union knot, hence
        # on each full linear interval. These are legacy consumers, not 237.
        shape = [dict(time_numerator='0', time_denominator='1', value_V=0.),
                 dict(time_numerator='1', time_denominator='1', value_V=1.)]
        bodies = [('V(a)<+tanh(V(u)); V(y)<+slew(V(u),2,-2);', 'a', 'y', .4),
                  ('V(a)<+tanh(V(u)); V(y)<+transition(1,0,0.1,0.1);', 'a', 'y', 1.),
                  ('V(a)<+0; V(y)<+tanh(V(u));', 'y', None, None)]
        with localcontext() as ctx:
            ctx.prec = 120
            x = Decimal.from_float(.4)
            positive, negative = x.exp(), (-x).exp()
            expected = (positive-negative)/(positive+negative)
        for body, math_node, other_node, other_expected in bodies:
            program = compile_sources({'legacy-math.va':model(body, ports='u,a,y,r',
                directions='input u; output a,y; inout r;')},
                [instance(connections=dict(u='u',a='a',y='y',r='0'))])
            with self.subTest(body=body):
                response = transient(program, {'u':[[0.,0.],[1.,1.]]}, [.4],
                    stop=1., max_step=1., source_errors={'u':0.},
                    source_shapes={'u':shape}, kernel=KERNEL)
                row = dict(zip(response['nodes'],response['solutions'][0]['voltages']))
                self.assertAlmostEqual(row[math_node], float(expected), delta=1e-10)
                if other_node:
                    self.assertAlmostEqual(row[other_node], other_expected, delta=1e-10)

    def test_old_affine_native_math_keeps_all_4000_unrelated_driven_sources(self):
        # Retaining unreferenced external drivers is the public SCS contract.
        # One old supported math output must not spend the optional new audit.
        sources = {'u':[[0.,.1],[1.,.1]]}
        sources.update({'spare'+str(i):[[0.,0.],[1.,0.]] for i in range(4000)})
        program = compile_sources({'direct.va':model('V(y)<+tanh(V(u));')},
                                  [instance()], external_nodes=sources)
        self.assertEqual(len(program.nodes),4003)
        response = transient(program,sources,[0.,1.],stop=1.,max_step=1.,kernel=KERNEL)
        with localcontext() as ctx:
            ctx.prec=120
            x=Decimal.from_float(.1)
            expected=(x.exp()-(-x).exp())/(x.exp()+(-x).exp())
        idx=response['nodes'].index('y')
        self.assertEqual(len(response['nodes']),4003)
        for row in response['solutions']:
            self.assertAlmostEqual(row['voltages'][idx],float(expected),delta=1e-12)

    def test_legacy_affine_math_positive_source_error_remains_explicitly_refused(self):
        # Deferring the optional new admission must not waive the old history
        # route's source-uncertainty gate, even for a small voltage band.
        with self.assertRaises(KernelError) as caught:
            self.run_value(self.program('tanh(V(u))'),.1,source_errors={'u':1e-14})
        self.assertEqual(caught.exception.detail['kind'],'unsupported_source_uncertainty')

    def test_multinode_certificate_uses_same_original_constraint_system(self):
        source = model('V(y,z)<+V(u)*tanh(V(u)/smooth); V(z)<+0.25;',
                       'electrical z; parameter real smooth=0.05;')
        program = compile_sources({'math.va':source}, [instance()])
        response = self.run_value(program, .1)
        idx = response['nodes'].index('y')
        for bounds in response['observation_evidence']['voltage_bounds_V']:
            lo, hi = map(Decimal.from_float, bounds[idx])
            self.assertLessEqual(lo, reference(.1)+Decimal('.25'))
            self.assertGreaterEqual(hi, reference(.1)+Decimal('.25'))

    def test_invalid_original_arithmetic_is_not_hidden_by_math_saturation(self):
        program = self.program('V(u)*tanh(1e308*V(u))')
        with self.assertRaises(KernelError):
            self.run_value(program, 2.)
        program = self.program('tanh(V(u))/(V(u)-0.25)')
        with self.assertRaises(KernelError):
            self.run_value(program, .25)

    def test_internal_feedback_and_dead_arm_dependencies_stay_rejected(self):
        for rhs in ['V(y)*tanh(V(u))',
                    'V(u)*tanh(V(u)+0.0*V(y))',
                    'V(u)*tanh(V(u))+(V(u)>0 ? 0 : V(y))']:
            with self.subTest(rhs=rhs), self.assertRaises((CompileError, KernelError)):
                self.run_value(self.program(rhs), .2)

    def test_existing_affine_math_route_still_has_certificates(self):
        response = self.run_value(self.program('tanh(V(u))+0.25'), .1)
        self.assertTrue(all(b is not None for b in
            response['observation_evidence']['voltage_bounds_V']))


if __name__ == '__main__':
    unittest.main()
