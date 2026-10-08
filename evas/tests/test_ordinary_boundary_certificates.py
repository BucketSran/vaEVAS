"""LANG ordinary-if decisions from original binary64 PWL rational values."""
GUARDS = ["LANG", "ANALOG"]

from fractions import Fraction
import math
import unittest

from evas import compile_sources, transient
from test_affine import KERNEL, instance, model


class OrdinaryBoundaryCertificates(unittest.TestCase):
    def test_nonbinary_interpolation_decides_discontinuous_branches(self):
        threshold = float("0.3333333333333333")
        times = [math.nextafter(1.0, -math.inf), 1.0,
                 math.nextafter(1.0, math.inf)]
        for relation in ("<", "<=", ">", ">="):
            with self.subTest(relation=relation):
                source = model(
                    f"if(V(u,r){relation}{threshold!r}) tmp=7; else tmp=-3; V(y,r)<+tmp;",
                    declarations="real tmp;")
                program = compile_sources({"test.va": source}, [instance()])
                def expected(time):
                    difference = Fraction(time) / 3 - Fraction(threshold)
                    truth = {"<": difference < 0, "<=": difference <= 0,
                             ">": difference > 0, ">=": difference >= 0}[relation]
                    return 7.0 if truth else -3.0
                self.assertGreater(Fraction(1, 3), Fraction(threshold))
                result = transient(program, {"u": [[0, 0], [3, 1]]}, times,
                                   stop=3.0, max_step=0.25, kernel=KERNEL,
                                   vabstol=1e-9, reltol=1e-10)
                actual = [s["voltages"][result["nodes"].index("y")]
                          for s in result["solutions"]]
                self.assertEqual(actual, [expected(t) for t in times])

    def test_exact_interpolated_equality_and_output_grid_invariance(self):
        times = [math.nextafter(1.0, -math.inf), 1.0,
                 math.nextafter(1.0, math.inf)]
        for relation in ("<", "<=", ">", ">="):
            with self.subTest(relation=relation):
                source = model(
                    f"if(V(u,r){relation}0.5) tmp=7; else tmp=-3; V(y,r)<+tmp;",
                    declarations="real tmp;")
                program = compile_sources({"test.va": source}, [instance()])
                expected = []
                for time in times:
                    difference = Fraction(time) / 2 - Fraction(1, 2)
                    truth = {"<": difference < 0, "<=": difference <= 0,
                             ">": difference > 0, ">=": difference >= 0}[relation]
                    expected.append(7.0 if truth else -3.0)
                for grid in (times, [0.0, 0.5] + times + [1.5, 2.0]):
                    result = transient(program, {"u": [[0, 0], [2, 1]]}, grid,
                                       stop=2.0, max_step=0.25, kernel=KERNEL)
                    actual = {t: s["voltages"][result["nodes"].index("y")]
                              for t, s in zip(grid, result["solutions"])}
                    self.assertEqual([actual[t] for t in times], expected)

    def test_exact_certificate_resource_limit_retains_rejection(self):
        from evas import KernelError
        # Original endpoint count exceeds the bounded exact-source contract.
        # Extra knots are collinear, so the same mathematical 1/3 answer exists,
        # but neither a rounded point nor a partial certificate may choose it.
        source = model(
            "if(V(u,r)>0.3333333333333333) tmp=7; else tmp=-3; V(y,r)<+tmp;",
            declarations="real tmp;")
        program = compile_sources({"test.va": source}, [instance()])
        points = [[0, 0], [3, 1]] + [[float(t), 1.0] for t in range(4, 515)]
        with self.assertRaisesRegex(KernelError, "condition_precision"):
            transient(program, {"u": points}, [1.0], stop=3.0,
                      max_step=0.25, kernel=KERNEL)

    def test_sequential_ex01_clamp_uses_original_input(self):
        source = model("f=0.4+0.5*V(u,r); if(f<0.2) f=0.2; "
                       "else if(f>1.0) f=1.0; V(y,r)<+f;", declarations="real f;")
        program = compile_sources({"test.va": source}, [instance()])
        points = [[0.0, -1.0], [2e-6, 0.0], [4e-6, 2.0],
                  [6e-6, 0.0], [8e-6, -1.0]]
        times = sorted({0.0, 8e-6, *[i*2e-10 for i in range(40001)],
                        1.2e-6, 3.2e-6, 4.8e-6, 6.8e-6})
        result = transient(program, {"u": points}, times, stop=8e-6,
                           max_step=2e-10, kernel=KERNEL, vabstol=1e-9, reltol=1e-10)
        def expected(time):
            for (start, a), (end, b) in zip(points, points[1:]):
                if time <= end:
                    value = Fraction(a)+(Fraction(b)-Fraction(a))*(Fraction(time)-Fraction(start))/(Fraction(end)-Fraction(start))
                    return min(Fraction(1.0), max(Fraction(0.2), Fraction(0.4)+Fraction(0.5)*value))
            self.fail("time outside frozen source")
        for time, solution in zip(times, result["solutions"]):
            actual = Fraction(solution["voltages"][result["nodes"].index("y")])
            self.assertLessEqual(abs(actual-expected(time)), Fraction(1e-9))
