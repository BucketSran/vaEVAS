"""Independent voltage-error contracts across point solves and event history.

These probes are development regressions, not new original-matrix conditions.
An unprovable result may be refused; an accepted result must meet its budget.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DEV:precision-chain", "NONLINEAR-TRANSIENT"]

from decimal import Decimal, localcontext
from fractions import Fraction
import math
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def run(source, points, times, **tolerances):
    program = compile_sources({"precision.va": source}, [instance()])
    return transient(program, {"u": points}, times, stop=points[-1][0],
                     max_step=points[-1][0], kernel=KERNEL, **tolerances)


class PointRootAccuracy(unittest.TestCase):
    def test_point_input_near_fold_cannot_hide_root_error(self):
        source = model("V(y,r)<+V(u,r)+pow(V(y,r),2);")
        for u in [.25, math.nextafter(.25, 0), .25-2**-54,
                  .25-2**-53, .25-1e-12]:
            with self.subTest(u=u):
                try:
                    result = run(source, [[0, u], [1, u]], [0],
                                 vabstol=1e-12, reltol=0)
                except KernelError as error:
                    self.assertEqual(error.detail["kind"], "waveform_accuracy")
                    self.assertEqual(error.detail["sample"], 0)
                else:
                    y = result["solutions"][0]["voltages"][result["nodes"].index("y")]
                    with localcontext() as context:
                        context.prec = 100
                        distance = (Decimal('0.25')-Decimal.from_float(u)).sqrt()
                        roots = [Decimal('0.5')-distance, Decimal('0.5')+distance]
                        error = min(abs(Decimal.from_float(y)-root) for root in roots)
                        self.assertLessEqual(error, Decimal.from_float(1e-12))

    def test_point_input_regular_root_and_summed_contributions_remain_supported(self):
        bodies = ["V(y,r)<+V(u,r)+pow(V(y,r),2);",
                  "V(y,r)<+V(u,r); V(y,r)<+pow(V(y,r),2);",
                  "V(y,r)<+pow(V(y,r),2); V(y,r)<+V(u,r);"]
        with localcontext() as context:
            context.prec = 100
            expected = Decimal('0.5')-(Decimal('0.25')-Decimal.from_float(.2)).sqrt()
            for body in bodies:
                with self.subTest(body=body):
                    result = run(model(body), [[0, .2], [1, .2]], [0, 1],
                                 vabstol=1e-12, reltol=0)
                    node = result["nodes"].index("y")
                    for solution in result["solutions"]:
                        self.assertLessEqual(abs(Decimal.from_float(solution["voltages"][node])-expected),
                                             Decimal.from_float(1e-12))

    def test_off_knot_root_is_invariant_under_splitting_contributions(self):
        bodies = ["V(y,r)<+V(u,r)+pow(V(y,r),2);",
                  "V(y,r)<+V(u,r); V(y,r)<+pow(V(y,r),2);",
                  "V(y,r)<+pow(V(y,r),2); V(y,r)<+V(u,r);"]
        with localcontext() as context:
            context.prec = 100
            u = Decimal.from_float(.1)+(Decimal.from_float(.2)-Decimal.from_float(.1))/3
            expected = Decimal('0.5')-(Decimal('0.25')-u).sqrt()
            values = []
            for body in bodies:
                result = run(model(body), [[0, .1], [3, .2]], [1],
                             vabstol=1e-12, reltol=0)
                y = result["solutions"][0]["voltages"][result["nodes"].index("y")]
                self.assertLessEqual(abs(Decimal.from_float(y)-expected),
                                     Decimal.from_float(1e-12))
                values.append(y)
            self.assertEqual(values, [values[0]]*len(values))

    def test_near_fold_regular_root_can_pass_a_provable_looser_budget(self):
        u = .25-1e-12
        result = run(model("V(y,r)<+V(u,r)+pow(V(y,r),2);"),
                     [[0, u], [1, u]], [0], vabstol=1e-7, reltol=0)
        y = result["solutions"][0]["voltages"][result["nodes"].index("y")]
        with localcontext() as context:
            context.prec = 100
            expected = Decimal('0.5')-(Decimal('0.25')-Decimal.from_float(u)).sqrt()
            self.assertLessEqual(abs(Decimal.from_float(y)-expected), Decimal.from_float(1e-7))


class SampleHistoryAccuracy(unittest.TestCase):
    def test_equivalent_sample_forms_preserve_input_uncertainty(self):
        points = [[0, 1], [3, math.nextafter(1, math.inf)]]
        reference = Fraction(10**16)*Fraction(1, 2**52)/3
        self.assertGreater(reference, Fraction(7, 10))
        variants = [("held=V(u,r)-1;", ""),
                    ("if(V(u,r)>=0) held=V(u,r)-1; else held=0;", ""),
                    ("held=V(u,r)-1;", "+0*idt(V(u,r),0)")]
        for assignment, extra in variants:
            with self.subTest(assignment=assignment, extra=extra):
                source = model(f"""@(initial_step) held=0;
                    @(timer(1,0,1e-12)) begin {assignment} end
                    V(y,r)<+1e16*held{extra};""", "real held;")
                try:
                    result = run(source, points, [0, 1, 2, 3],
                                 vabstol=1e-12, reltol=1e-5)
                except KernelError as error:
                    self.assertIn(error.detail["kind"], ["event_accuracy", "waveform_accuracy"])
                else:
                    node = result["nodes"].index("y")
                    for solution in result["solutions"][1:]:
                        y = Fraction.from_float(solution["voltages"][node])
                        budget = Fraction.from_float(1e-12)+Fraction.from_float(1e-5)*abs(y)
                        self.assertLessEqual(abs(y-reference), budget)

    def test_accepted_sample_error_survives_until_later_amplification(self):
        # One writer: u(1)=1+2^-54 rounds to 1, within its relative budget.
        # At t=2, u=0 exactly and y=1e16*2^-54, not the rounded value zero.
        source = model("""@(initial_step) held=0;
            @(timer(1,1,1e-12)) held=1e16*held+V(u,r);
            V(y,r)<+held-1e16;""", "real held;")
        with self.assertRaises(KernelError) as caught:
            run(source, [[0, 1], [.75, 1], [1.75, math.nextafter(1, math.inf)],
                         [2, 0], [3, 0]], [0, 1, 2, 3],
                vabstol=1e-12, reltol=1e-5)
        self.assertEqual(caught.exception.detail["kind"], "event_accuracy")

    def test_state_only_transient_checks_off_knot_voltage_accuracy(self):
        source = model("""@(initial_step) held=0;
            V(y,r)<+1e16*(V(u,r)-1);""", "real held;")
        with self.assertRaises(KernelError) as caught:
            run(source, [[0, 1], [3, math.nextafter(1, math.inf)]], [0, 1, 3],
                vabstol=1e-12, reltol=1e-5)
        self.assertEqual(caught.exception.detail["kind"], "event_accuracy")

    def test_exact_sample_matches_with_and_without_constant_true_condition(self):
        forms = ["held=V(u,r);",
                 "if(V(u,r)>=0) held=V(u,r); else held=0;"]
        traces = []
        for assignment in forms:
            result = run(model(f"""@(initial_step) held=0;
                @(timer(0.5,0,1e-12)) begin {assignment} end
                V(y,r)<+held;""", "real held;"),
                         [[0, .125], [1, .875]], [0, .25, .5, .75, 1],
                         vabstol=1e-12, reltol=1e-5)
            node = result["nodes"].index("y")
            values = [s["voltages"][node] for s in result["solutions"]]
            self.assertEqual(values, [0, 0, .5, .5, .5])
            traces.append((values, result["transient"]["states"],
                           [e["time"] for e in result["transient"]["events"]]))
        self.assertEqual(traces[0], traces[1])
