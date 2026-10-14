"""Auxiliary continuous dependency roots (N09b).

Internal voltages consumed only by $bound_step active/value controls or by
independently observed mathematical functions must receive algebraic mapping
columns before elimination. Expected values are independent closed-form
answers: with u≡1 and z(0)=1/4 the selected ODE z'=(1-z)/2 gives
z(t)=1-(3/4)exp(-t/2), f=2u, and an independent transition with rise 1/4
starting at 1/4 produces clamp(4t-1,0,1). Rejections must keep rejecting:
underconstrained or conflicting definitions, hidden zero-coefficient timed
feedback and internal-voltage predicates stay unsupported.

Build the kernel once before running (see evas/README.md).
"""
GUARDS = ["LANG", "DYNAMICS", "COMPOSE", "DEV:auxiliary-roots"]


import math
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient

EVAS = Path(__file__).resolve().parents[1]
KERNEL = EVAS / "rust_core/target/debug/evas-kernel"
TIMES = [0.0, 0.25, 0.5, 1.0]


def model(body, declarations="", ports="u,y,r", directions="input u; output y; inout r;"):
    return (f'`include "disciplines.vams"\nmodule m({ports}); {directions} electrical {ports};'
            f" {declarations} analog begin {body} end endmodule")


def instance(name="dut", module="m", connections=None, parameters=None):
    return Instance(name, module, connections or dict(u="u", y="y", r="0"), parameters or {})


def ode_z():
    """Nonlinear-in-u relaxation arm; with u≡1 it is z'=(1-z)/2."""
    return "V(z,r)<+idt((1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);"


def run(source, inst=None, sources=None, times=TIMES, **extra):
    program = compile_sources({"test.va": source}, [inst or instance()])
    result = transient(program, sources or {"u": [[0.0, 1.0], [1.0, 1.0]]}, times,
                       stop=1.0, max_step=0.125, vabstol=1e-8, reltol=0.0,
                       kernel=KERNEL, **extra)
    nodes = result["nodes"]
    return {name: [row["voltages"][nodes.index(name)] for row in result["solutions"]]
            for name in nodes}


def relax(t):
    return 1.0 - 0.75 * math.exp(-t / 2.0)


RELAXED = [relax(t) for t in TIMES]


class AuxiliaryRootContracts(unittest.TestCase):
    def assert_rows(self, rows, expected):
        self.assertEqual(set(rows), set(expected))
        for node, wanted in expected.items():
            self.assertEqual(len(rows[node]), len(wanted))
            for got, want in zip(rows[node], wanted):
                self.assertAlmostEqual(got, want, places=12, msg=node)

    def assert_relaxation_rows(self, rows, times=TIMES, f=2.0, g=None, y=None):
        expected = {"0": [0.0] * len(times), "u": [1.0] * len(times),
                    "dut:z": [relax(t) for t in times],
                    "y": [relax(t) for t in times] if y is None else y}
        if f is not None:
            expected["dut:f"] = [f] * len(times)
        if g is not None:
            expected["dut:g"] = [g] * len(times)
        self.assert_rows(rows, expected)

    def test_bound_only_affine_internal_voltage(self):
        src = model("V(f,r)<+2*V(u,r);" + ode_z() + "V(y,r)<+V(z,r);"
                    "$bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f;")
        rows = run(src)
        self.assert_relaxation_rows(rows)
        for got, want in zip(rows["dut:z"], RELAXED):
            self.assertAlmostEqual(got, want, places=12)

    def test_inactive_bound_arm_keeps_structural_dependency(self):
        src = model("V(f,r)<+2*V(u,r);V(z,r)<+idt(V(u,r)>2?(V(f,r)-V(z,r))/(1+V(f,r)*V(f,r)):(1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);"
                    "V(y,r)<+V(z,r);if(V(u,r)>2) $bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f;")
        rows = run(src)
        self.assert_relaxation_rows(rows)
        # u≡1 selects the (1-z)/2 arm; the bound arm is inactive but its
        # definition must still be solved, not substituted or dropped.
        for got, want in zip(rows["dut:z"], RELAXED):
            self.assertAlmostEqual(got, want, places=12)

    def test_mathematical_output_of_affine_internal_voltage(self):
        src = model("@(timer(0.25,0,0)) n=1;V(f,r)<+2*V(u,r);" + ode_z()
                    + "V(y,r)<+transition(n,0,0.25)+exp(V(f,r));", "integer n; electrical z,f;")
        rows = run(src)
        self.assert_relaxation_rows(rows, y=[math.exp(2.0) + min(max(4*t-1, 0.0), 1.0) for t in TIMES])
        ramp = [min(max(4.0 * t - 1.0, 0.0), 1.0) for t in TIMES]
        for got, want in zip(rows["dut:z"], RELAXED):
            self.assertAlmostEqual(got, want, places=12)
        y = rows.get("dut:y", rows.get("y"))
        for got, want in zip(y, [math.exp(2.0) + r for r in ramp]):
            self.assertAlmostEqual(got, want, places=12)

    def test_bound_only_internal_voltage_without_transition(self):
        src = model("V(f,r)<+2*V(u,r);" + ode_z()
                    + "V(y,r)<+V(z,r);$bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f;")
        rows = run(src)
        self.assert_relaxation_rows(rows)
        for got, want in zip(rows["dut:z"], RELAXED):
            self.assertAlmostEqual(got, want, places=12)

    def test_two_node_affine_chain_bound_only(self):
        src = model("V(g,r)<+V(u,r)+1;V(f,r)<+V(g,r);" + ode_z() + "V(y,r)<+V(z,r);"
                    + "$bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f,g;")
        rows = run(src)
        self.assert_relaxation_rows(rows, g=2.0)
        # f=u+1=2, identical mathematics to the single-node bound case.
        for got, want in zip(rows["dut:z"], RELAXED):
            self.assertAlmostEqual(got, want, places=12)

    def test_bound_reading_network_state_is_unchanged(self):
        src = model("V(f,r)<+2*V(u,r);" + ode_z()
                    + "@(timer(0.25,0,0)) n=1;V(y,r)<+transition(n,0,0.25);"
                    + "$bound_step((1+V(z,r)*V(z,r))/16);", "integer n; electrical z,f;")
        rows = run(src)
        self.assert_relaxation_rows(rows, y=[min(max(4*t-1, 0.0), 1.0) for t in TIMES])
        for got, want in zip(rows["dut:z"], RELAXED):
            self.assertAlmostEqual(got, want, places=12)

    def test_direct_and_internal_bound_forms_agree(self):
        internal = model("V(f,r)<+2*V(u,r);" + ode_z() + "V(y,r)<+V(z,r);"
                         + "$bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f;")
        direct = model(ode_z() + "V(y,r)<+V(z,r);"
                       + "$bound_step((1+4*V(u,r)*V(u,r))/16);", "electrical z;")
        internal_rows, direct_rows = run(internal), run(direct)
        self.assert_relaxation_rows(internal_rows)
        self.assert_relaxation_rows(direct_rows, f=None)
        for got, want in zip(internal_rows["dut:z"], direct_rows["dut:z"]):
            self.assertAlmostEqual(got, want, places=12)

    def test_sparse_and_dense_queries_agree(self):
        src = model("V(f,r)<+2*V(u,r);" + ode_z() + "V(y,r)<+V(z,r);"
                    + "$bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f;")
        dense_times = [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]
        sparse_rows = run(src, times=TIMES)
        dense_rows = run(src, times=dense_times)
        self.assert_relaxation_rows(sparse_rows)
        self.assert_relaxation_rows(dense_rows, times=dense_times)
        for time, row in zip((0.0, 0.25, 0.5, 1.0), (0, 2, 4, 8)):
            self.assertAlmostEqual(sparse_rows["dut:z"][TIMES.index(time)],
                                   dense_rows["dut:z"][row], places=12)
            self.assertAlmostEqual(dense_rows["dut:z"][row], relax(time), places=12)

    def test_underconstrained_internal_voltage_still_rejects(self):
        src = model(ode_z() + "V(y,r)<+V(z,r);$bound_step((1+V(f,r)*V(f,r))/16);",
                    "electrical z,f;")
        with self.assertRaises(KernelError) as raised:
            run(src)
        self.assertEqual(raised.exception.diagnostic["kind"], "event_resolution")

    def test_conflicting_internal_definitions_still_rejects(self):
        leaf = ('`include "disciplines.vams"\nmodule drv(out,r); inout out,r; electrical out,r;'
                " parameter real c=0.5; analog begin V(out,r)<+c; end endmodule\n"
                'module m(u,y,r); input u; output y; inout r; electrical u,y,r,f,z;'
                " drv #(.c(0.5)) a(f,r); drv #(.c(-0.25)) b(f,r);"
                " analog begin " + ode_z() + "V(y,r)<+V(z,r);"
                "$bound_step((1+V(f,r)*V(f,r))/16); end endmodule")
        inst = instance(connections=dict(u="u", y="y", r="0"))
        with self.assertRaises(KernelError) as raised:
            run(leaf, inst)
        self.assertEqual(raised.exception.diagnostic["kind"], "event_resolution")

    def test_source_product_auxiliary_definition(self):
        # A valid source product already works in root-v8. It is a positive
        # regression, not a claim that every nonlinear definition must reject.
        src = model("V(f,r)<+V(u,r)*V(w,r);" + ode_z() + "V(y,r)<+V(z,r);"
                    + "$bound_step((1+V(f,r)*V(f,r))/16);", "electrical z,f;",
                    ports="u,w,y,r", directions="input u,w; output y; inout r;")
        inst = instance(connections=dict(u="u", w="w", y="y", r="0"))
        rows = run(src, inst, sources={"u": [[0.0, 1.0], [1.0, 1.0]],
                                      "w": [[0.0, 1.0], [1.0, 1.0]]})
        self.assert_rows(rows, {"0": [0.0] * 4, "u": [1.0] * 4,
                                "w": [1.0] * 4, "dut:f": [1.0] * 4,
                                "dut:z": RELAXED, "y": RELAXED})

    def test_hidden_zero_transition_feedback_still_rejects(self):
        src = model("V(f,r)<+2*V(u,r)+0*V(y,r);" + ode_z()
                    + "@(timer(0.25,0,0)) n=1;V(y,r)<+transition(n,0,0.25);"
                    + "$bound_step((1+V(f,r)*V(f,r))/16);", "integer n; electrical z,f;")
        # The zero coefficient must not delete the structural timed edge.
        with self.assertRaises(KernelError) as raised:
            run(src)
        self.assertEqual(raised.exception.diagnostic["kind"], "unsupported_operator")

    def test_true_timed_feedback_still_rejects(self):
        src = model("V(f,r)<+2*V(u,r);V(z,r)<+idt((V(y,r)-V(z,r))/(1+V(u,r)*V(u,r)),0.25);"
                    "@(timer(0.25,0,0)) n=1;V(y,r)<+transition(n,0,0.25);",
                    "integer n; electrical z,f;")
        with self.assertRaises(KernelError) as raised:
            run(src)
        self.assertEqual(raised.exception.diagnostic["kind"], "unsupported_operator")

    def test_private_internal_predicate_still_rejects(self):
        src = model("V(f,r)<+2*V(u,r);V(z,r)<+idt(V(f,r)>1?1:0,0.25);V(y,r)<+V(z,r);", "electrical z,f;")
        with self.assertRaises(CompileError) as raised:
            run(src)
        self.assertEqual(raised.exception.diagnostic["kind"], "compile_error")
        self.assertIn("decision predicates must depend only on input/inout ports",
                      str(raised.exception))

    def test_port_internal_predicate_still_rejects(self):
        body = ("@(timer(0.25,0,0)) n=1;V(f,r)<+2*V(u,r);V(z,r)<+idt(V(f,r)>1?1:0,0.25);"
                "V(y,r)<+transition(n,0,0.25);")
        src = model(body, "integer n; electrical z;", ports="u,f,y,r",
                    directions="input u; inout f,r; output y;")
        inst = instance(connections=dict(u="u", f="f", y="y", r="0"))
        with self.assertRaises(KernelError) as raised:
            run(src, inst)
        self.assertEqual(raised.exception.diagnostic["kind"], "unsupported_transient")


if __name__ == "__main__":
    unittest.main()
