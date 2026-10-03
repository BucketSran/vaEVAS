"""Voltage accuracy regressions with independent algebra/Decimal references.

These are development controls, not additional cross-backend conditions or an
untouched holdout. Thresholds describe these problems, not a global error bound.
"""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["LIN", "DEV:precision-chain"]

from decimal import Decimal, localcontext
import json
import subprocess
import unittest

from evas import KernelError, compile_sources, solve
from test_affine import KERNEL, instance, model


def cubic_root():
    # x**3+x-1 is strictly increasing; bisection in [0,1] is independent of
    # EVAS's Newton method, derivatives and binary64 expression evaluation.
    with localcontext() as context:
        context.prec = 70
        low, high = Decimal(0), Decimal(1)
        for _ in range(240):
            middle = (low + high) / 2
            if middle**3 + middle > 1:
                high = middle
            else:
                low = middle
        return (low + high) / 2


ROOT = cubic_root()
SCALED = model('V(y,r)<+V(y,r)-s*(V(y,r)+pow(V(y,r),3)-1);',
               'parameter real s=1;')


def run(source=SCALED, instances=None, samples=None, **tolerances):
    program = compile_sources({'accuracy.va': source}, instances or [instance()])
    result = solve(program, ['u'], samples or [[0]], kernel=KERNEL, **tolerances)
    return [(dict(zip(result['nodes'], item['voltages'])), item)
            for item in result['solutions']]


class VoltageAccuracy(unittest.TestCase):
    def test_equivalent_equation_scales_and_contribution_forms(self):
        forms = [SCALED, model(
            'V(y,r)<+V(y,r); V(r,y)<+s*(V(y,r)+pow(V(y,r),3)-1);',
            'parameter real s=1;')]
        for source in forms:
            for scale in (1, 1e-13, -1e-13, 1e3):
                with self.subTest(source=source, scale=scale):
                    row, _ = run(source, [instance(parameters={'s': scale})])[0]
                    self.assertLessEqual(abs(Decimal(row['y']) - ROOT), Decimal('1e-10'))

    def test_voltage_tolerance_sweep_against_high_precision_root(self):
        errors = []
        for tolerance in (1e-3, 1e-6, 1e-9, 1e-12):
            with self.subTest(tolerance=tolerance):
                row, item = run(instances=[instance(parameters={'s': 1e-13})],
                                vabstol=tolerance, reltol=0)[0]
                error = float(abs(Decimal(row['y']) - ROOT))
                errors.append(error)
                self.assertLessEqual(error, 2 * tolerance)
                for field in ('max_residual_ratio', 'max_scaled_residual_ratio',
                              'max_voltage_correction_ratio'):
                    self.assertLessEqual(item[field], 1)
                self.assertLessEqual(item['max_voltage_correction_v'], tolerance)
        self.assertLess(errors[-1], errors[0] / 1000)

    def test_voltage_magnitudes_and_relative_tolerance(self):
        source = model('V(y,r)<+a*(V(u,r)-pow(V(y,r)/a,3));',
                       'parameter real a=1;')
        for scale in (1e-9, 1e-3, 1, 1e3):
            with self.subTest(scale=scale):
                rows = run(source, [instance(parameters={'a': scale})],
                           [[-1], [0], [1]], vabstol=1e-15, reltol=1e-9)
                for (row, _), sign in zip(rows, (-1, 0, 1)):
                    reference = sign * scale * float(ROOT)
                    self.assertLessEqual(abs(row['y'] - reference),
                                         2 * (1e-15 + 1e-9 * abs(reference)))

    def test_coupled_equations_with_different_row_scales(self):
        # q=(.5,-.25); diagonal >=1, off-diagonal .25, hence a unique root.
        source = model('V(y,r)<+V(y,r)-s*(V(y,r)+pow(V(y,r),3)+.25*V(u,r)-b);',
                       'parameter real s=1; parameter real b=0;')
        instances = [
            instance('a', connections=dict(u='b', y='a', r='0'),
                     parameters=dict(s=1e-13, b=.5625)),
            instance('b', connections=dict(u='a', y='b', r='0'),
                     parameters=dict(s=1, b=-.140625)),
        ]
        for order in (instances, instances[::-1]):
            program = compile_sources({'coupled-accuracy.va': source}, order)
            result = solve(program, [], [[]], kernel=KERNEL)
            row = dict(zip(result['nodes'], result['solutions'][0]['voltages']))
            self.assertAlmostEqual(row['a'], .5, delta=1e-10)
            self.assertAlmostEqual(row['b'], -.25, delta=1e-10)

    def test_scaled_inconsistent_parallel_constraints_are_rejected(self):
        source = model('V(y,r)<+V(y,r)-s*(V(y,r)+pow(V(y,r),3)-b);',
                       'parameter real s=1; parameter real b=0;')
        # One constraint requires y=0, another requires y=cubic_root().
        instances = [instance('aa', parameters=dict(s=1e-13, b=1)),
                     instance('zz', parameters=dict(s=1, b=0))]
        with self.assertRaises(KernelError) as error:
            run(source, instances)
        self.assertEqual(error.exception.detail['kind'], 'nonconvergence')
        self.assertEqual(error.exception.detail['sample'], 0)
        self.assertIn('accuracy.va:', error.exception.detail['message'])

    def test_small_residuals_in_coupled_system_still_require_voltage_correction(self):
        # Both raw and row-scaled residuals at (0,0) are below 1e-12.
        # Subtracting the equations gives e*z=-e, hence z=-1;
        # x+e*x**3=1+e then has the unique root x=1. e is exact in binary64.
        source = model(
            'V(x,r)<+-V(z,r)-e*pow(V(x,r),3)+e; '
            'V(z,r)<+-V(x,r)-e*V(z,r)-e*pow(V(x,r),3);',
            'parameter real e=1;', ports='u,x,z,r',
            directions='input u; output x,z; inout r;')
        inst = instance(connections=dict(u='u', x='x', z='z', r='0'),
                        parameters=dict(e=2**-40))
        row, item = run(source, [inst])[0]
        self.assertAlmostEqual(row['x'], 1, delta=1e-8)
        self.assertAlmostEqual(row['z'], -1, delta=1e-8)
        self.assertLessEqual(item['max_voltage_correction_ratio'], 1)

    def test_initially_dependent_coupling_recovers_a_regular_root(self):
        source = model('V(y,r)<+1-k*V(u,r)-pow(V(y,r),3);',
                       'parameter real k=1;')
        instances = [instance('a', connections=dict(u='b', y='a', r='0')),
                     instance('b', connections=dict(u='a', y='b', r='0'),
                              parameters=dict(k=1+1e-15))]
        program = compile_sources({'ill-conditioned.va': source}, instances)
        # The Jacobian at zero is nearly singular, but the desired root is
        # regular. Eliminate b=1-a-a^3 and bisect the resulting polynomial;
        # this oracle does not use the implementation's Newton/homotopy path.
        from decimal import Decimal, localcontext
        with localcontext() as context:
            context.prec=70
            k=Decimal.from_float(1+1e-15)
            lo,hi=Decimal('.4'),Decimal('.5')
            for _ in range(220):
                a=(lo+hi)/2
                b=1-a-a**3
                if b+b**3+k*a-1 > 0: lo=a
                else: hi=a
            a=(lo+hi)/2
            expected=[float(a),float(1-a-a**3)]
        result=solve(program,[],[[]],kernel=KERNEL)
        solution=result['solutions'][0]
        for node,answer in zip(['a','b'],expected):
            self.assertAlmostEqual(solution['voltages'][program.nodes.index(node)],answer,delta=1e-10)
        self.assertLessEqual(solution['max_voltage_correction_ratio'],1)

    def test_dependent_jacobian_at_every_root_still_fails(self):
        # Both equations constrain only a+b, so no isolated voltage solution
        # exists even though their residuals can vanish.
        source=model('V(y,r)<+1-V(u,r)-pow(V(y,r)+V(u,r),3);')
        instances=[instance('a',connections=dict(u='b',y='a',r='0')),
                   instance('b',connections=dict(u='a',y='b',r='0'))]
        program=compile_sources({'dependent.va':source},instances)
        with self.assertRaisesRegex(KernelError,'singular_jacobian'):
            solve(program,[],[[]],kernel=KERNEL)

    def test_unattainable_tolerance_does_not_accept_a_rounded_away_update(self):
        source = model('V(y,r)<+3-pow(V(y,r),2);')
        with self.assertRaises(KernelError) as error:
            run(source, vabstol=1e-30, reltol=0)
        self.assertEqual(error.exception.detail['kind'], 'nonconvergence')


class VoltageToleranceInterface(unittest.TestCase):
    def test_python_names_and_legacy_aliases_match(self):
        canonical = run(vabstol=1e-8, reltol=1e-7)
        self.assertEqual(canonical, run(absolute=1e-8, relative=1e-7))
        for options in (dict(vabstol=1e-8, absolute=1e-8),
                        dict(reltol=1e-7, relative=1e-7)):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, 'both'):
                run(**options)

    def test_wire_names_defaults_duplicates_and_invalid_values(self):
        program = compile_sources({'wire-accuracy.va': SCALED}, [instance()])
        request = dict(program=program.to_dict(), driven=['u'], samples=[[0]])

        def wire(tolerances):
            return subprocess.run([str(KERNEL)], text=True, capture_output=True,
                                  input=json.dumps(dict(request, tolerances=tolerances)))

        legacy = wire(dict(absolute=1e-8, relative=1e-7))
        canonical = wire(dict(vabstol=1e-8, reltol=1e-7))
        self.assertEqual(canonical.returncode, 0, canonical.stderr)
        self.assertEqual(legacy.stdout, canonical.stdout)
        self.assertEqual(wire({}).stdout, wire(dict(vabstol=1e-12, reltol=1e-10)).stdout)
        for options in (dict(vabstol=0), dict(vabstol=-1), dict(reltol=-1),
                        dict(vabstol='1e-6'), dict(reltol=True),
                        dict(vabstol=1e-6, absolute=1e-6),
                        dict(reltol=1e-6, relative=1e-6)):
            result = wire(options)
            with self.subTest(options=options):
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn(json.loads(result.stderr)['kind'], ('invalid_config', 'invalid_request'))


if __name__ == '__main__':
    unittest.main()
