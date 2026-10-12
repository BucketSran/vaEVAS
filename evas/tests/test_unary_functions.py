"""Public transient checks for finite unary maps and their mathematical domains."""
GUARDS = ["LANG", "DYNAMICS"]

from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest

from evas import compile_sources, transient, Instance, KernelError, CompileError
from test_affine import KERNEL, model

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'validation/paper'))
from primitives import cards, assess, T


class UnaryFunctions(unittest.TestCase):
    def test_nested_integer_power_binds_exponent_once(self):
        from evas.lowering import lower
        from evas.ir import Affine
        from evas.syntax import Expr, Token
        token = Token('pow', 'name', 1, 1, 'nested.va')
        expression = Expr('parameter', 'one', (), token)
        depth = 30
        for _ in range(depth):
            expression = Expr('power', None,
                              (Expr('number', 1., (), token), expression), token)
        bindings = []
        def parameter(name):
            self.assertEqual(bindings, [], 'exponent was bound more than once')
            bindings.append(name)
            return 1.
        self.assertEqual(lower(expression, parameter, {}, 'nested.va'), Affine(1., ()))
        self.assertEqual(bindings, ['one'])

    def test_half_power_preserves_conditional_admission(self):
        for body in ['if (V(u,r)>0) q=pow(V(u,r),0.5); else q=0; V(y,r)<+q;',
                     'V(y,r)<+(V(u,r)>0 ? pow(V(u,r),0.5) : 0);']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_sources({'m.va':model(body,'real q;')},
                    [Instance('dut','m',dict(u='u',y='y',r='0'))])

    def test_original_primitive_cards_at_q3(self):
        for card in cards():
            if card['id'] not in ('P-cos', 'P-exp', 'P-ln', 'P-sqrt', 'P-pow-half'):
                continue
            with self.subTest(card=card['id']):
                program = compile_sources({'dut.va': card['source']},
                    [Instance('dut', card['top'], {p:p for p in card['ports']})])
                times = sorted({i*T/16 for i in range(65)} |
                               {t for t,_ in card['inputs']['u']})
                result = transient(program, card['inputs'], times, stop=card['stop_s'],
                    max_step=T/32, strobetimes=times, kernel=KERNEL,
                    vabstol=1e-12, reltol=1e-10)
                rows = [{'time':t, **dict(zip(result['nodes'], v))}
                        for t,v in zip(times, result['strobe_evidence']['voltages_V'])]
                self.assertEqual(assess(card, rows, 'Q3')['status'], 'pass')

    def test_zero_and_invalid_domains(self):
        for expression, value in [('sqrt(V(u,r))', -1.), ('ln(V(u,r))', 0.),
                                  ('pow(V(u,r),0.5)', -1.), ('exp(V(u,r))', 1000.)]:
            with self.subTest(expression=expression, value=value):
                program = compile_sources({'m.va':model('V(y,r)<+'+expression+';')},
                    [Instance('dut','m',dict(u='u',y='y',r='0'))])
                with self.assertRaises(KernelError):
                    transient(program, {'u':[[0.,value],[1.,value]]}, [0.,1.],
                              stop=1., max_step=1., kernel=KERNEL)

    def test_nested_integral_and_independent_calls(self):
        source = model('V(y,r)<+exp(idt(V(u,r),0.125)); V(z,r)<+sqrt(V(u,r));',
                       ports='u,y,z,r', directions='input u; output y,z; inout r;')
        program=compile_sources({'m.va':source},
                   [Instance('dut','m',dict(u='u',y='y',z='z',r='0'))])
        times=[0.,.25,.5,1.]
        response=transient(program, {'u':[[0.,.25],[1.,.25]]}, times,
                           stop=1.,max_step=1.,kernel=KERNEL)
        with localcontext() as context:
            context.prec=70
            for t,sample in zip(times,response['solutions']):
                row=dict(zip(response['nodes'],sample['voltages']))
                expected=(Decimal('.125')+Decimal(t)*Decimal('.25')).exp()
                self.assertAlmostEqual(row['y'],float(expected),delta=1e-11)
                self.assertEqual(row['z'],.5)
