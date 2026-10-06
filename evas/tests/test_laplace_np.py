"""One real-pole form: independent original-pole answers through public APIs."""
GUARDS = ['LANG', 'DYNAMICS', 'LAPLACE']

from decimal import Decimal, localcontext
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

TIMES = [0, .125, .25, .5, 1]


def compile_np(body="V(y,r)<+laplace_np(V(u,r),'{b0},'{p,0});", instances=None):
    source = model(body, 'parameter real b0=1; parameter real p=-4; electrical z;')
    # z is only present in the downstream-history rejection case.
    if 'V(z,' not in body:
        source = source.replace('electrical z;', '')
    return compile_sources({'pole.va': source}, instances or [instance()])


def run(program, points=None, times=TIMES):
    return transient(program, {'u': points or [[0, 0], [1, 1]]}, times,
                     stop=1, max_step=1, vabstol=1e-8, reltol=0, kernel=KERNEL)


def column(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


def pole_ramp(t, numerator=1, pole=-4):
    # Independently solve (1-s/p)Y=b0*U for U=1/s^2, not the generated nd IR.
    with localcontext() as ctx:
        ctx.prec = 90
        t, b, p = Decimal(t), Decimal(numerator), Decimal(pole)
        return b * (t + (1 - (p * t).exp()) / p)


class LaplaceNpContracts(unittest.TestCase):
    def test_unit_dc_preserves_pole_form_gain(self):
        self.assertEqual(column(run(compile_np(), [[0, 1], [1, 1]])), [1.] * len(TIMES))
        self.assertEqual(column(run(compile_np(instances=[instance(parameters={'b0': 2})]),
                                    [[0, 1], [1, 1]])), [2.] * len(TIMES))

    def test_original_pole_ramp_oracle_and_numerator_two(self):
        for b in (1, 2):
            with self.subTest(numerator=b):
                result = run(compile_np(instances=[instance(parameters={'b0': b})]))
                for t, actual in zip(TIMES, column(result)):
                    self.assertLessEqual(abs(Decimal(actual) - pole_ramp(t, b)), Decimal('1e-6'))
                self.assertTrue(all(row['max_residual_ratio'] <= 1 for row in result['solutions']))

    def test_zero_and_negative_constant_numerators_keep_the_original_gain(self):
        for b in (0, -2):
            with self.subTest(numerator=b):
                for t, actual in zip(TIMES, column(run(compile_np(instances=[instance(parameters={'b0': b})])))):
                    self.assertLessEqual(abs(Decimal(actual) - pole_ramp(t, b)), Decimal('1e-6'))

    def test_equivalent_nd_is_secondary_lowering_evidence(self):
        np = compile_np()
        nd = compile_np("V(y,r)<+laplace_nd(V(u,r),'{b0},'{1,.25});")
        self.assertEqual(np.operators[0].kind, 'laplace_nd')
        self.assertEqual(np.operators[0].numerator, (1.,))
        self.assertEqual(np.operators[0].denominator, (1., .25))
        self.assertEqual(np.operators[0].input, nd.operators[0].input)
        self.assertEqual(column(run(np)), column(run(nd)))

    def test_instances_and_call_sites_keep_separate_history(self):
        instances = [instance('a', connections={'u': 'u', 'y': 'ya', 'r': '0'}),
                     instance('b', connections={'u': 'u', 'y': 'yb', 'r': '0'}, parameters={'b0': 2, 'p': -8})]
        program = compile_np(instances=instances)
        result = run(program)
        self.assertEqual({op.origin.instance for op in program.operators}, {'a', 'b'})
        for name, b, p in [('ya', 1, -4), ('yb', 2, -8)]:
            for t, actual in zip(TIMES, column(result, name)):
                self.assertLessEqual(abs(Decimal(actual) - pole_ramp(t, b, p)), Decimal('1e-6'))
        program = compile_np("V(y,r)<+laplace_np(V(u,r),'{1},'{-4,0})+laplace_np(V(u,r),'{2},'{-8,0});")
        self.assertNotEqual(program.operators[0].origin.column, program.operators[1].origin.column)
        for t, actual in zip(TIMES, column(run(program))):
            self.assertLessEqual(abs(Decimal(actual)-pole_ramp(t)-pole_ramp(t, 2, -8)), Decimal('1e-6'))

    def test_query_grid_does_not_change_accepted_filter_history(self):
        p = compile_np()
        baseline = column(run(p))
        grid = sorted(set(TIMES + [i/32 for i in range(33)]))
        refined = column(run(p, times=grid))
        self.assertEqual(baseline, [refined[grid.index(t)] for t in TIMES])

    def test_unsupported_domains_are_explicit(self):
        calls = [
            "laplace_np(V(u,r),'{1},'{0,0})", "laplace_np(V(u,r),'{1},'{4,0})",
            "laplace_np(V(u,r),'{1},'{-4,1})", "laplace_np(V(u,r),'{1},'{-4,0,-8,0})",
            "laplace_np(V(u,r),'{1},'{-4})", "laplace_np(V(u,r),'{1,2},'{-4,0})",
            "laplace_np(V(u,r),'{},'{-4,0})", "laplace_np(V(u,r),{1},{-4,0})",
            "laplace_np(V(u,r),'{V(u,r)},'{-4,0})", "laplace_np(V(u,r),'{1},'{V(u,r),0})",
            "laplace_np(V(u,r),'{1},'{-3,0})", "laplace_np(V(u,r),'{0},'{-3,0})",
            "laplace_np(V(u,r),'{1},'{-10,0})", "laplace_np(V(u,r),'{1},'{-1e-320,0})",
            "laplace_np(V(u,r),'{1e309},'{-4,0})", "laplace_np(V(u,r),'{1},'{-1e309,0})",
        ]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(CompileError):
                compile_np('V(y,r)<+' + call + ';')
        for epsilon in ('1e-9', 'V(u,r)'):
            with self.subTest(epsilon=epsilon), self.assertRaisesRegex(CompileError, 'epsilon'):
                compile_np("V(y,r)<+laplace_np(V(u,r),'{1},'{-4,0},"+epsilon+');')

    def test_exact_reciprocal_rejection_is_not_a_rounded_product_check(self):
        self.assertEqual((-3.) * (1./3.), -1.)
        with self.assertRaisesRegex(CompileError, 'exact.*binary64'):
            compile_np(instances=[instance(parameters={'p': -3})])
        for p, tau in [(-8., .125), (-.5, 2.)]:
            program = compile_np(instances=[instance(parameters={'p': p})])
            self.assertEqual(program.operators[0].denominator, (1., tau))

    def test_downstream_history_dependency_rejection_is_unchanged(self):
        body = "V(z,r)<+laplace_np(V(u,r),'{1},'{-4,0}); V(y,r)<+absdelay(V(z,r),.25);"
        for text in (body, body.replace("laplace_np(V(u,r),'{1},'{-4,0})", "laplace_nd(V(u,r),'{1},'{1,.25})")):
            with self.subTest(text=text), self.assertRaises(KernelError):
                run(compile_np(text))


if __name__ == '__main__':
    unittest.main()
