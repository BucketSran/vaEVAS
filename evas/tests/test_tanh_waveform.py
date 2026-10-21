"""Certified native tanh waveforms; high precision is only an independent oracle."""
GUARDS = ['LANG', 'ANALOG', 'DYNAMICS']

from decimal import Decimal, localcontext
import math
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from evas.frontend import parse_sources
from test_affine import KERNEL, instance, model


def reference_tanh(value):
    # Decimal's independently implemented 100-digit exponential is test-only.
    # This positive-exponential identity differs from the production negative-tail map.
    with localcontext() as context:
        context.prec = 100
        x = Decimal.from_float(value)
        positive, negative = x.exp(), (-x).exp()
        return float((positive-negative)/(positive+negative))


class TanhWaveform(unittest.TestCase):
    def compile(self, body, declarations=''):
        return compile_sources({'tanh.va':model(body, declarations)}, [instance()])

    def values(self, program, inputs):
        values = []
        for value in inputs:
            response = transient(program, {'u':[[0,value],[1,value]]}, [0.,1.],
                                 stop=1,max_step=1,kernel=KERNEL,
                                 vabstol=1e-11,reltol=1e-10)
            index = response['nodes'].index('y')
            values.append(response['solutions'][0]['voltages'][index])
            self.assertEqual(response['solutions'][1]['voltages'][index], values[-1])
        return values

    def test_both_spellings_match_high_precision_at_zero_signs_and_tails(self):
        inputs = [-256., -30., -2., -.1, -math.ulp(0.), 0., math.ulp(0.), .1, 2., 30., 256.]
        for spelling in ('tanh', '$tanh'):
            with self.subTest(spelling=spelling):
                actual = self.values(self.compile('V(y,r)<+'+spelling+'(V(u,r));'), inputs)
                for x, value in zip(inputs, actual):
                    self.assertAlmostEqual(value, reference_tanh(x), delta=1e-11)

    def test_comparator_scale_offset_and_nonconstant_pwl_inputs(self):
        program = self.compile('V(y,r)<+0.45*tanh(20*(V(u,r)-0.45))+0.45;')
        sources = {'u':[[0,.2],[1,.7]]}
        times = [0.,.25,.5,.75,1.]
        response = transient(program, sources, times, stop=1,max_step=.1,
                             vabstol=1e-11,reltol=1e-10,kernel=KERNEL)
        index = response['nodes'].index('y')
        for t, row in zip(times,response['solutions']):
            x = 20*(.2+(.7-.2)*t-.45)
            self.assertAlmostEqual(row['voltages'][index],.45*reference_tanh(x)+.45,delta=1e-10)

    def test_finite_extreme_argument_does_not_overflow_internal_scaling(self):
        values = self.values(self.compile('V(y,r)<+tanh(V(u,r));'),[-float.fromhex('0x1.fffffffffffffp1023'),float.fromhex('0x1.fffffffffffffp1023')])
        self.assertEqual(values,[-1.,1.])

    def test_source_argument_overflow_is_not_hidden_by_saturation(self):
        program = self.compile('V(y,r)<+tanh(1e308*V(u,r));')
        with self.assertRaises(KernelError):
            self.values(program,[2.])

    def test_source_uncertainty_and_downstream_amplification_are_certified(self):
        for body in ('V(y,r)<+tanh(V(u,r));','V(y,r)<+1e8*tanh(V(u,r));'):
            program = self.compile(body)
            with self.subTest(body=body),self.assertRaises(KernelError):
                transient(program,{'u':[[0,0.],[1,0.]]},[0,1],stop=1,max_step=1,
                          source_errors={'u':1e-6},vabstol=1e-11,reltol=1e-10,kernel=KERNEL)

    def test_user_function_and_variable_names_keep_existing_binding(self):
        declaration = ('parameter real tanh=0.25; ')
        self.assertEqual(self.values(self.compile('V(y,r)<+tanh;',declaration),[0.]),[.25])
        function = ('analog function real tanh; input x; real x; '
                    'begin tanh=x+1; end endfunction ')
        source = model('V(y,r)<+tanh(V(u,r))+$tanh(0);').replace('analog begin',function+'analog begin')
        program = compile_sources({'user-tanh.va':source},[instance()])
        self.assertEqual(self.values(program,[.25]),[1.25])

    def test_arity_real_type_and_unknown_system_suffix(self):
        for spelling in ('tanh','$tanh'):
            expression = parse_sources({'tanh.va':model('V(y,r)<+'+spelling+'(V(u,r));')})['m'].analog[0].rhs
            self.assertEqual(expression.op,'tanh')
            self.assertEqual(expression.result_type,'real')
            for arguments in ('()','(1,2)','(,1)','(1,)'):
                with self.subTest(spelling=spelling,arguments=arguments),self.assertRaises(CompileError):
                    parse_sources({'bad.va':model('V(y,r)<+'+spelling+arguments+';')})
        with self.assertRaises(CompileError):
            self.compile('V(y,r)<+$tanh_extra(V(u,r));')
        with self.assertRaises(CompileError):
            self.compile('V(y,r)<+tanh(1.0)&1;')

    def test_declared_function_arity_precedes_builtin_only_within_its_module(self):
        function = ('analog function real tanh; input a,b; real a,b; '
                    'begin tanh=a+b; end endfunction ')
        source = model('V(y,r)<+tanh(V(u,r),0.25)+$tanh(V(u,r));')
        source = source.replace('analog begin',function+'analog begin')
        other = model('V(y,r)<+tanh(V(u,r));').replace('module m(', 'module other(')
        parsed = parse_sources({'both.va':source+other})
        expression = parsed['m'].analog[0].rhs
        while expression.op == 'checked':
            expression = expression.args[0]
        self.assertEqual(expression.op,'+')
        self.assertEqual(expression.args[1].op,'tanh')
        self.assertEqual(parsed['other'].analog[0].rhs.op,'tanh')

    def test_event_math_and_feedback_scope_do_not_expand(self):
        with self.assertRaisesRegex(CompileError, 'event bodies do not support history/operator calls') as caught:
            self.compile('@(initial_step) q=0; @(timer(0.5)) q=tanh(V(u,r)); V(y,r)<+q;','real q;')
        self.assertEqual(caught.exception.diagnostic['stage'], 'compile')
        with self.assertRaises((CompileError,KernelError)):
            program = self.compile('V(y,r)<+tanh(V(u,r)+0.5*V(y,r));')
            self.values(program,[.2])


if __name__ == '__main__':
    unittest.main()
