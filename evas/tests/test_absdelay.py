"""Independent fixed-delay development contracts, not the 31-case qualification.

The oracle uses exact rational arithmetic on the binary64 source/parameter
values actually passed to EVAS. It never reads an EVAS-generated waveform to
construct expected values. Zero delay is an EVAS extension, not an LRM demand.
"""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["ABSDELAY", "TIMED-OPERATOR"]

import copy
from fractions import Fraction
import json
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


POINTS = [[0.0, -1.0], [4e-9, 1.0], [10e-9, 1.0]]
SOURCE = model("V(y,r)<+absdelay(V(u,r),tau);", "parameter real tau=3n;")
DEFAULT_DELAY = 3 * 1e-9  # binary64 product for the explicit SI literal 3n


def expected(points, time, delay):
    query = max(Fraction(time) - Fraction(delay), 0)
    values = [(Fraction(t), Fraction(v)) for t, v in points]
    for (start, a), (end, b) in zip(values, values[1:]):
        if query <= end:
            return float(a + (b-a)*(query-start)/(end-start))
    return float(values[-1][1])


def compile_delay(source=SOURCE, instances=None):
    return compile_sources({"absdelay.va": source}, instances or [instance()])


def execute_delay(source=SOURCE, *, instances=None, sources=None, times=None,
                  stop=10e-9, step=100e-9):
    return transient(compile_delay(source, instances),
                     sources if sources is not None else {"u": POINTS},
                     times if times is not None else [0, 3e-9, 5e-9, 7e-9, 10e-9],
                     stop=stop, max_step=step, kernel=KERNEL)


def column(result, name="y"):
    index = result["nodes"].index(name)
    return [solution["voltages"][index] for solution in result["solutions"]]


class AbsDelayContracts(unittest.TestCase):
    def test_ad_ramp_and_nonzero_initial_history(self):
        result = execute_delay()
        for actual, answer in zip(column(result), [-1, -1, 0, 1, 1]):
            self.assertAlmostEqual(actual, answer, delta=2e-14)
        self.assertEqual(result["transient"]["events"], [])
        self.assertTrue(all(row["max_residual_ratio"] <= 1 for row in result["solutions"]))

    def test_ad_zero_is_current_input_identity_extension(self):
        times = [0, 2e-9, 4e-9, 10e-9]
        result = execute_delay(instances=[instance(parameters={"tau": 0})], times=times)
        for actual, answer in zip(column(result), [-1, 0, 1, 1]):
            self.assertAlmostEqual(actual, answer, delta=2e-14)

    def test_delay_beyond_stop_preserves_initial_value(self):
        result = execute_delay(instances=[instance(parameters={"tau": 100e-9})])
        self.assertEqual(column(result), [-1]*5)

    def test_shifted_corners_are_solver_breakpoints_without_output_samples(self):
        result = execute_delay(times=[0, 10e-9])
        # Source corner 4 ns plus delayed history boundary 3 ns and corner 7 ns.
        self.assertEqual(result["transient"]["accepted_steps"], 4)
        self.assertEqual(column(result), [-1, 1])

    def test_semantic_history_is_independent_of_output_grid_and_maxstep(self):
        points = [[0, -1], [1e-9, 2], [1.125e-9, -2], [2e-9, .5], [10e-9, .5]]
        times = [0, 3.5e-9, 4.0625e-9, 4.5e-9, 7e-9, 10e-9]
        dense = sorted(set(times + [i*.125e-9 for i in range(80)]))
        answers = [expected(points, t, DEFAULT_DELAY) for t in times]
        baseline = None
        for grid in [times, dense]:
            for step in [100e-9, .17e-9]:
                with self.subTest(grid=len(grid), step=step):
                    result = execute_delay(sources={"u": points}, times=grid, step=step)
                    values = [column(result)[grid.index(t)] for t in times]
                    for actual, answer in zip(values, answers):
                        self.assertAlmostEqual(actual, answer, delta=3e-13)
                    if baseline is None:
                        baseline = values
                    self.assertEqual(values, baseline)

    def test_affine_combination_uses_union_of_direct_source_knots(self):
        source = model("V(y,r)<+absdelay(2*V(u,r)-.5*V(v,r)+.125,3n);",
                       ports="u,v,y,r", directions="input u,v; output y; inout r;")
        sources = {"u": POINTS, "v": [[0, 1], [2e-9, -1], [10e-9, 0]],
                   "r": [[0, .25], [6e-9, .5], [10e-9, .5]]}
        times = [0, 2e-9, 4e-9, 5e-9, 6e-9, 8e-9, 10e-9]
        inst = instance(connections=dict(u="u", v="v", y="y", r="r"))
        result = execute_delay(source, instances=[inst], sources=sources, times=times)
        for actual, t in zip(column(result), times):
            old_r = expected(sources["r"], t, DEFAULT_DELAY)
            answer = (expected(sources["r"], t, 0)
                      + 2*(expected(sources["u"], t, DEFAULT_DELAY)-old_r)
                      - .5*(expected(sources["v"], t, DEFAULT_DELAY)-old_r) + .125)
            self.assertAlmostEqual(actual, answer, delta=3e-13)

    def test_two_instances_parameters_units_and_order_are_independent(self):
        source = model("V(y,r)<+absdelay(V(u,r),base*scale);",
                       "parameter real base=1n; parameter real scale=3;")
        a = instance("a", connections=dict(u="u", y="a", r="0"))
        b = instance("b", connections=dict(u="u", y="b", r="0"), parameters={"scale": 1})
        rows = []
        times = [0, 2e-9, 4e-9, 7e-9, 10e-9]
        for order in [[a, b], [b, a]]:
            result = execute_delay(source, instances=order, times=times)
            rows.append((column(result, "a"), column(result, "b")))
            for name, tau in [("a", DEFAULT_DELAY), ("b", 1e-9)]:
                for actual, t in zip(column(result, name), times):
                    self.assertAlmostEqual(actual, expected(POINTS, t, tau), delta=3e-14)
        self.assertEqual(rows[0], rows[1])

    def test_large_time_queries_preserve_the_exact_local_delay(self):
        offset = float(2**54)
        points = [[0, 0], [offset, 0], [offset+4, 1], [offset+8, 1]]
        times = [0, offset, offset+4, offset+8]
        for delay in [1, 3]:
            with self.subTest(delay=delay):
                result = execute_delay(instances=[instance(parameters={"tau": delay})],
                                       sources={"u": points}, times=times,
                                       stop=offset+8, step=offset+8)
                for actual, t in zip(column(result), times):
                    self.assertEqual(actual, expected(points, t, delay))

    def test_inconsistent_constraint_does_not_return_a_partial_waveform(self):
        fixed = model("V(y,r)<+0;")
        delayed = compile_sources({"absdelay.va": SOURCE, "fixed.va": fixed.replace("module m", "module fixed")},
                                  [instance(), instance("fixed", module="fixed")])
        with self.assertRaises(KernelError) as error:
            transient(delayed, {"u": [[0, 0], [4e-9, 1], [10e-9, 1]]}, [0, 10e-9],
                      stop=10e-9, max_step=100e-9, kernel=KERNEL)
        # PR13 certifies initialization before advancing. The inconsistent
        # redundant equation is rejected by that earlier exact-system check.
        self.assertEqual(error.exception.detail["kind"], "event_accuracy")
        self.assertIn("redundant", error.exception.detail["message"])
        # A separate valid retry gets the original nonzero initial history.
        self.assertEqual(column(execute_delay(times=[0])), [-1])


class AbsDelayRejections(unittest.TestCase):
    def test_dynamic_delay_maxdelay_and_implicit_delay_rejected(self):
        for expression in ["absdelay(V(u),-1n)", "absdelay(V(u),V(u))",
                           "absdelay(V(u),1n,2n)", "absdelay(V(u))"]:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_delay(model(f"V(y,r)<+{expression};"))

    def test_internal_state_nested_nonlinear_and_feedback_inputs_rejected(self):
        cases = [
            model("V(z,r)<+V(u,r); V(y,r)<+absdelay(V(z,r),1n);", "electrical z;"),
            model("V(z,r)<+V(u,r); V(y,r)<+absdelay(0*V(z,r)+V(u,r),1n);", "electrical z;"),
            model("V(z,r)<+V(u,r); V(y,r)<+absdelay(V(z,r)-V(z,r)+V(u,r),1n);", "electrical z;"),
            model("V(z,r)<+V(u,r); V(y,r)<+absdelay(V(z,z)+V(u,r),1n);", "electrical z;"),
            model("V(z,r)<+V(u,r); V(y,r)<+absdelay(V(z,r)/1e308/1e308+V(u,r),1n);", "electrical z;"),
            model("@(initial_step) q=1; V(y,r)<+absdelay(q,1n);", "real q;"),
            model("V(y,r)<+absdelay(absdelay(V(u,r),1n),1n);"),
            model("V(y,r)<+absdelay(V(u,r)*V(u,r),1n);"),
            model("V(y,r)<+absdelay(V(y,r),1n);"),
            model("V(y,r)<+absdelay(V(u,r),1n)*V(u,r);"),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises((CompileError, KernelError)):
                execute_delay(source)

    def test_cross_on_delayed_output_direct_or_indirect_is_rejected(self):
        for guard in ["V(y,r)-.5", "V(z,r)-.5", "0*V(z,r)+V(u,r)-.5"]:
            source = model(f'''@(initial_step) n=0;
              V(y,r)<+absdelay(V(u,r),1n); V(z,r)<+2*V(y,r);
              @(cross({guard},1)) n=n+1;''', "integer n; electrical z;")
            with self.subTest(guard=guard), self.assertRaises((CompileError, KernelError)):
                execute_delay(source)

    def test_cross_instance_guard_dependency_survives_cancellation(self):
        producer = SOURCE.replace("module m", "module delayed")
        for link in ["V(u,r)", "0*V(u,r)+V(v,r)",
                     "V(u,r)-V(u,r)+V(v,r)", "V(u,r)/1e308/1e308+V(v,r)"]:
            monitor = model(f'''@(initial_step) n=0; V(z,r)<+{link};
              @(cross(V(z,r)-.5,1)) n=n+1; V(y,r)<+n;''', "integer n; electrical z;",
                            ports="u,v,y,r", directions="input u,v; output y; inout r;")
            instances = [instance("producer", module="delayed", connections=dict(u="u", y="d", r="0")),
                         instance("monitor", connections=dict(u="d", v="u", y="y", r="0"))]
            with self.subTest(link=link), self.assertRaises((CompileError, KernelError)):
                program = compile_sources({"producer.va": producer, "monitor.va": monitor}, instances)
                transient(program, {"u": POINTS}, [0, 10e-9], stop=10e-9, max_step=100e-9, kernel=KERNEL)

    def test_discontinuous_input_and_static_analysis_are_rejected(self):
        with self.assertRaises(KernelError):
            execute_delay(sources={"u": [[0, -1], [1e-9, -1], [1e-9, 1], [10e-9, 1]]})
        with self.assertRaises(KernelError) as error:
            solve(compile_delay(), ["u"], [[0]], kernel=KERNEL)
        self.assertEqual(error.exception.detail["kind"], "unsupported_analysis")

    def test_malformed_raw_ir_and_hidden_internal_dependency_are_rejected(self):
        program = compile_delay().to_dict()
        internal = program["nodes"].index("y")
        bad_inputs = [
            dict(op="affine", constant=0, terms=[dict(node=999, coefficient=1)]),
            dict(op="affine", constant=0, terms=[dict(node=internal, coefficient=0)]),
            dict(op="multiply", left=dict(op="affine", constant=0, terms=[]),
                 right=dict(op="affine", constant=0, terms=[dict(node=internal, coefficient=1)])),
        ]
        mutations = [("input", value) for value in bad_inputs]
        mutations += [("delay", -1), ("delay", "1n"), ("maxdelay", 2e-9)]
        for key, value in mutations:
            raw = copy.deepcopy(program)
            raw["operators"][0][key] = value
            request = dict(program=raw, driven=["u"], samples=[],
                           transient=dict(pwl=[POINTS], output_times=[0, 10e-9],
                                          stop=10e-9, max_step=100e-9))
            with self.subTest(key=key, value=value):
                result = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                                        capture_output=True, check=False)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("kind", json.loads(result.stderr))


if __name__ == "__main__":
    unittest.main()
