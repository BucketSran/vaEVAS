"""Behavioral contracts through the public compile/solve interface.

The expected numbers and rejection cases here are independent of the lowering
implementation. Build the kernel once before running (see evas/README.md).
"""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["LANG", "LIN", "COMPOSE", "case:n_v1_02", "case:d2_v7_01"]


import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, solve

EVAS = Path(__file__).resolve().parents[1]
KERNEL = EVAS / "rust_core/target/debug/evas-kernel"
SUM = (EVAS / "validation/cases/n_v1_02/dut.va").read_text()
FEEDBACK = (EVAS / "validation/cases/d2_v7_01/dut.va").read_text()


def model(body, declarations="", ports="u,y,r", directions="input u; output y; inout r;"):
    constants = '`include "constants.vams"\n' if '`M_PI' in body or '`M_PI' in declarations else ''
    return constants + f"`include \"disciplines.vams\"\nmodule m({ports}); {directions} electrical {ports}; {declarations} analog begin {body} end endmodule"


def instance(name="dut", module="m", connections=None, parameters=None):
    return Instance(name, module, connections or dict(u="u", y="y", r="0"), parameters or {})


def execute(source, instances=None, driven=None, samples=None, **tolerances):
    program = compile_sources({"test.va": source}, instances or [instance()])
    result = solve(program, driven or ["u"], samples or [[.2]], kernel=KERNEL, **tolerances)
    return [dict(zip(result["nodes"], s["voltages"])) for s in result["solutions"]]


class AffineContracts(unittest.TestCase):
    def test_additive_contributions_all_permutations_and_combined_form(self):
        pieces = ["V(y,r)<+1.5*V(u,r);", "V(y,r)<+-0.5*V(v,r);", "V(y,r)<+0.125;"]
        inputs = [[0, -.2, 0], [1.4, .8, 1], [-1.2, -.7, -1]]
        inst = instance(connections=dict(u="u", v="v", y="y", r="r"))
        bodies = ["".join(order) for order in itertools.permutations(pieces)]
        bodies += ["V(y,r)<+1.5*V(u,r)-0.5*V(v,r)+0.125;"]
        for body in bodies:
            with self.subTest(body=body):
                rows = execute(model(body, ports="u,v,y,r", directions="input u,v; output y; inout r;"),
                               [inst], ["u", "v", "r"], inputs)
                for row, (u, v, r) in zip(rows, inputs):
                    self.assertAlmostEqual(row["y"], r + 1.5*(u-r) - .5*(v-r) + .125, places=12)

    def test_source_default_and_overridden_parameters(self):
        for params, expected in [({}, .575), (dict(g1=-.5, g2=2, bias=-.25), .15)]:
            with self.subTest(params=params):
                rows = execute(SUM, [instance(module="dvs_sum", connections=dict(u="u", v="v", vout="y", vref="0"), parameters=params)],
                               ["u", "v"], [[.4, .3]])
                self.assertAlmostEqual(rows[0]["y"], expected, places=12)

    def test_branch_orientation_and_single_node_access(self):
        for body in ["V(y,r)<+V(u,r); V(r,y)<+-0.125;", "V(y)<+V(u)+0.125;"]:
            self.assertAlmostEqual(execute(model(body))[0]["y"], .325, places=12)

    def test_feedback_is_solved_at_first_sample_without_history(self):
        inst = instance(module="dvs_v7_linear", connections=dict(vin="u", vout="y", vref="0"))
        rows = execute(FEEDBACK, [inst], samples=[[.2], [.6], [-.3], [.2]])
        self.assertEqual(rows[0], rows[-1])
        for row, expected in zip(rows, [.4, 1.2, -.6, .4]):
            self.assertAlmostEqual(row["y"], expected, places=12)

    def test_feedback_does_not_require_fixed_point_contraction(self):
        for gain in (-4, 1.5, .999):
            inst = instance(module="dvs_v7_linear", connections=dict(vin="u", vout="y", vref="r"), parameters=dict(gain=gain))
            rows = execute(FEEDBACK, [inst], ["u", "r"], [[.5, .3]])
            self.assertAlmostEqual(rows[0]["y"], .3 + .2/(1-gain), places=9)

    def test_instance_order_and_parameter_isolation(self):
        a = instance("a", "dvs_v7_linear", dict(vin="ua", vout="ya", vref="0"), dict(gain=.5))
        b = instance("b", "dvs_v7_linear", dict(vin="ub", vout="yb", vref="0"), dict(gain=-.5))
        rows = [execute(FEEDBACK, order, ["ua", "ub"], [[.2, .6]])[0] for order in ([a,b], [b,a])]
        self.assertEqual(rows[0], rows[1])
        self.assertAlmostEqual(rows[0]["ya"], .4)
        self.assertAlmostEqual(rows[0]["yb"], .4)

    def test_coupled_instances_solve_one_system(self):
        source = model("V(y,r)<+gain*V(u,r)+bias;", "parameter real gain=0.5; parameter real bias=0;")
        # a = .5*b + 1, b = .25*a + 2 => a=16/7, b=18/7.
        instances = [instance("a", connections=dict(u="b", y="a", r="0"), parameters=dict(bias=1)),
                     instance("b", connections=dict(u="a", y="b", r="0"), parameters=dict(gain=.25,bias=2))]
        program = compile_sources({"coupled.va":source}, instances)
        result = solve(program, [], [[]], kernel=KERNEL)
        row = dict(zip(result["nodes"], result["solutions"][0]["voltages"]))
        self.assertAlmostEqual(row["a"], 16/7)
        self.assertAlmostEqual(row["b"], 18/7)

    def test_internal_nodes_are_instance_local(self):
        source = model("V(z,r)<+2*V(u,r); V(y,r)<+V(z,r)+1;", "electrical z;")
        instances = [instance("a", connections=dict(u="u", y="a", r="0")),
                     instance("b", connections=dict(u="v", y="b", r="0"))]
        row = execute(source, instances, ["u", "v"], [[1, 3]])[0]
        self.assertEqual(row["a"], 3)
        self.assertEqual(row["b"], 7)
        self.assertEqual(row["a:z"], 2)
        self.assertEqual(row["b:z"], 6)

    def test_parallel_instances_are_constraints_not_added_sources(self):
        source = model("V(y,r)<+bias;", "parameter real bias=1;")
        instances = [instance("a"), instance("b")]
        self.assertEqual(execute(source, instances)[0]["y"], 1)
        instances[1] = instance("b", parameters=dict(bias=2))
        with self.assertRaises(KernelError) as error:
            execute(source, instances)
        self.assertEqual(error.exception.detail["kind"], "residual_failure")
        self.assertIn("test.va:", error.exception.detail["message"])

    def test_singular_and_floating_circuits_fail(self):
        for source in [model("V(y,r)<+V(u,r)+V(y,r);"),
                       model("V(y,r)<+V(u,r);", "electrical floating;")]:
            with self.subTest(source=source), self.assertRaises(KernelError) as error:
                execute(source)
            self.assertEqual(error.exception.detail["kind"], "singular_system")

    def test_driven_output_still_checks_constraint_and_sample_identity(self):
        program = compile_sources({"test.va":model("V(y,r)<+V(u,r);")}, [instance()])
        with self.assertRaises(KernelError) as error:
            solve(program, ["u","y"], [[1,1],[1,2]], kernel=KERNEL)
        self.assertEqual(error.exception.detail["kind"], "residual_failure")
        self.assertEqual(error.exception.detail["sample"], 1)

    def test_random_affine_feedback_with_independent_formula(self):
        rng = random.Random(20260928)
        source = model("V(y,r)<+a*V(u,r)+b+k*V(y,r);",
                       "parameter real a=1; parameter real b=0; parameter real k=0;")
        for _ in range(30):
            a, b, k = rng.uniform(-2,2), rng.uniform(-1,1), rng.choice([-.5,.25,1.5,3.0])
            u, r = rng.uniform(-1,1), rng.uniform(-1,1)
            row = execute(source, [instance(connections=dict(u="u",y="y",r="r"),parameters=dict(a=a,b=b,k=k))],
                          ["u","r"], [[u,r]])[0]
            self.assertAlmostEqual(row["y"], r+(a*(u-r)+b)/(1-k), places=11)

    def test_parameter_dependencies_follow_instance_overrides(self):
        source = model("V(y,r)<+derived*V(u,r);", "parameter real base=2; parameter real derived=base+1;")
        self.assertAlmostEqual(execute(source, [instance(parameters=dict(base=4))])[0]["y"], 1)

    def test_numeric_scaling_and_precedence(self):
        source = model("V(y,r)<+-(2+3)*V(u,r)/2+1m; V(y,r)<+2e-3;")
        self.assertAlmostEqual(execute(source)[0]["y"], -.497)


class RejectionContracts(unittest.TestCase):
    def test_unsupported_and_malformed_source_is_not_silently_lowered(self):
        cases = [
            model("V(y,r)<+1/V(u,r);"),
            model("V(y,r)<+idt(V(u,r));"),
            model("@(cross(V(u,r),1)) V(y,r)<+1;"),
            model("if (1) V(y,r)<+1;"),
            model("I(y,r)<+1;"),
            model("V(y,r)<+undeclared;"),
            model("V(y,r)<+V(missing,r);"),
            model("V(y,r)<+1@;"),
            model("V(y,r)<+1e999;"),
            model("V(y,r)<+1/0;"),
            model("V(y,r)<+1e308*10;"),
            model("V(y,r)<+1;")+" junk",
            "`include \"other.vams\"\n"+model("V(y,r)<+1;"),
            model("V(y,r)<+1;")+" /* unclosed",
            model("V(y,r)<+1;", "parameter real a=b; parameter real b=a;"),
            model("V(y,r)<+1;", "parameter real a=V(u,r);"),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CompileError):
                compile_sources({"bad.va":source}, [instance()])

    def test_unknown_and_nonfinite_override(self):
        source = model("V(y,r)<+a;", "parameter real a=1;")
        for params in [dict(missing=1), dict(a=math.nan), dict(a=True), dict(a="2")]:
            with self.subTest(params=params), self.assertRaises(CompileError):
                compile_sources({"bad.va":source}, [instance(parameters=params)])

    def test_distinct_local_branches_cannot_be_merged_by_port_alias(self):
        source = model("V(y,r)<+1; V(u,r)<+2;")
        with self.assertRaisesRegex(CompileError, "distinct local contribution branches alias"):
            compile_sources({"alias.va":source}, [instance(connections=dict(u="y",y="y",r="0"))])

    def test_binding_errors(self):
        source = model("V(y,r)<+V(u,r);")
        for instances in [[], [instance(),instance()], [instance(module="missing")],
                          [instance(connections=dict(u="u",y="y"))],
                          [instance(connections=dict(u="a:z",y="y",r="0"))]]:
            with self.subTest(instances=instances), self.assertRaises(CompileError):
                compile_sources({"bad.va":source}, instances)

    def test_ir_validation_cannot_be_bypassed_by_direct_json(self):
        program = compile_sources({"test.va":model("V(y,r)<+V(u,r);")}, [instance()]).to_dict()
        base = dict(program=program, driven=["u"], samples=[[.2]])
        mutations = [
            lambda r:r["program"].update(schema_version=99),
            lambda r:r["program"].update(extra_semantics=True),
            lambda r:r["program"]["contributions"][0].update(positive=999),
            lambda r:r["program"]["contributions"][0]["rhs"]["terms"].append(dict(node=0,coefficient=3)),
            lambda r:r.update(driven=["missing"]),
            lambda r:r.update(driven=["u","u"]),
            lambda r:r.update(driven=["0"]),
            lambda r:r.update(samples=[[]]),
            lambda r:r.update(samples=[]),
            lambda r:r.update(tolerances=dict(absolute=0,relative=1e-6)),
        ]
        for mutate in mutations:
            request=json.loads(json.dumps(base)); mutate(request)
            with self.subTest(request=request):
                result = subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("kind", json.loads(result.stderr))


if __name__ == "__main__":
    unittest.main()
