"""Parameter binding and versioned branch identity contracts, with hand answers."""

import copy
import json
import math
import subprocess
import unittest

from evas import CompileError, compile_sources
from test_affine import KERNEL, execute, instance, model


class ParameterContracts(unittest.TestCase):
    def test_dependencies_use_overrides_before_arithmetic_in_either_order(self):
        declarations = ["parameter real a=0;", "parameter real b=1/a;"]
        for order in (declarations, declarations[::-1]):
            source = model("V(y,r)<+b;", " ".join(order))
            with self.subTest(order=order):
                self.assertEqual(execute(source, [instance(parameters=dict(a=2))])[0]["y"], .5)
                with self.assertRaisesRegex(CompileError, "nonzero constant denominator"):
                    compile_sources({"parameters.va": source}, [instance()])

    def test_overridden_arithmetic_is_not_evaluated(self):
        for default in ("1/0", "1e308*10"):
            source = model("V(y,r)<+a;", f"parameter real a={default};")
            with self.subTest(default=default):
                self.assertEqual(execute(source, [instance(parameters=dict(a=2))])[0]["y"], 2)
                with self.assertRaises(CompileError):
                    compile_sources({"parameters.va": source}, [instance()])

    def test_overrides_remove_only_their_own_dependency_edges(self):
        source = model("V(y,r)<+a+b;", "parameter real a=b+1; parameter real b=a+1;")
        for params, expected in [(dict(a=2), 5), (dict(a=2, b=4), 6)]:
            with self.subTest(params=params):
                self.assertEqual(execute(source, [instance(parameters=params)])[0]["y"], expected)
        with self.assertRaisesRegex(CompileError, "cyclic"):
            compile_sources({"parameters.va": source}, [instance()])
        self_cycle = model("V(y,r)<+a;", "parameter real a=a+1;")
        self.assertEqual(execute(self_cycle, [instance(parameters=dict(a=2))])[0]["y"], 2)
        with self.assertRaisesRegex(CompileError, "cyclic"):
            compile_sources({"parameters.va": self_cycle}, [instance()])
        remaining_cycle = model("V(y,r)<+a;", "parameter real a=1; parameter real b=c; parameter real c=b;")
        with self.assertRaisesRegex(CompileError, "cyclic"):
            compile_sources({"parameters.va": remaining_cycle}, [instance(parameters=dict(a=2))])

    def test_overrides_do_not_hide_invalid_default_structure(self):
        for default in ("missing", "V(u,r)", "1e999", "sin(2)"):
            source = model("V(y,r)<+1;", f"parameter real a={default};")
            with self.subTest(default=default), self.assertRaises(CompileError):
                compile_sources({"parameters.va": source}, [instance(parameters=dict(a=2))])

    def test_unused_effective_parameters_must_still_be_valid(self):
        for default in ("1/0", "1e308*10", "a+1"):
            source = model("V(y,r)<+1;", f"parameter real a={default};")
            with self.subTest(default=default), self.assertRaises(CompileError):
                compile_sources({"parameters.va": source}, [instance()])

    def test_overrides_require_representable_finite_numbers(self):
        source = model("V(y,r)<+a;", "parameter real a=1;")
        for value in (math.inf, -math.inf, math.nan, True, "2", 10**400):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(CompileError):
                compile_sources({"parameters.va": source}, [instance(parameters=dict(a=value))])

    def test_effective_dependencies_are_instance_local(self):
        source = model("V(y,r)<+b;", "parameter real a=0; parameter real b=1/a;")
        instances = [instance("a", connections=dict(u="u", y="ya", r="0"), parameters=dict(a=2)),
                     instance("b", connections=dict(u="u", y="yb", r="0"), parameters=dict(a=4))]
        for order in (instances, instances[::-1]):
            row = execute(source, order)[0]
            self.assertEqual((row["ya"], row["yb"]), (.5, .25))


def wire_request():
    """Independent v11 request: V(r)-V(y)=-2, with r bound to ground."""
    return dict(program=dict(schema_version=11, nodes=["0", "y"], contributions=[dict(
        branch=dict(instance="dut", local_positive="r", local_negative="y", kind="voltage"),
        positive=0, negative=1, rhs=dict(op="affine", constant=-2, terms=[]),
        origin=dict(source="wire.va", line=1, column=1, instance="dut"))]), driven=[], samples=[[]])


class BranchContracts(unittest.TestCase):
    def request(self, request, error=None):
        payload = request if isinstance(request, str) else json.dumps(request)
        result = subprocess.run([str(KERNEL)], input=payload, text=True, capture_output=True)
        if error:
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, "")
            detail = json.loads(result.stderr)
            self.assertEqual(detail["kind"], error)
            return detail
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["schema_version"], 11)
        return response

    def test_compiler_preserves_local_identity_and_reversed_contributions(self):
        source = model("V(y,r)<+1; V(r,y)<+-2;")
        program = compile_sources({"branch.va": source}, [instance()]).to_dict()
        self.assertEqual(program["schema_version"], 11)
        for contribution in program["contributions"]:
            self.assertEqual(contribution["branch"], dict(
                instance="dut", local_positive="r", local_negative="y", kind="voltage"))
            self.assertEqual(program["nodes"][contribution["positive"]], "0")
            self.assertEqual(program["nodes"][contribution["negative"]], "y")
        self.assertEqual(execute(source)[0]["y"], 3)

    def test_implicit_and_explicit_ground_share_a_branch(self):
        source = model("V(y)<+1; V(y,0)<+2;")
        program = compile_sources({"ground.va": source}, [instance()]).to_dict()
        self.assertEqual(program["contributions"][0]["branch"], program["contributions"][1]["branch"])
        self.assertEqual(program["contributions"][0]["branch"]["local_positive"], "0")
        self.assertEqual(execute(source)[0]["y"], 3)

    def test_handwritten_wire_request_and_additive_identity(self):
        request = wire_request()
        request["program"]["contributions"].append(copy.deepcopy(request["program"]["contributions"][0]))
        request["program"]["contributions"][1]["rhs"]["constant"] = -3
        self.assertEqual(self.request(request)["solutions"][0]["voltages"], [0, 5])

    def test_branch_shape_and_identity_are_checked_by_rust(self):
        cases = [
            (dict(instance=""), "invalid_ir"),
            (dict(instance="other"), "invalid_ir"),
            (dict(local_positive=""), "invalid_ir"),
            (dict(local_negative=""), "invalid_ir"),
            (dict(local_positive="z"), "invalid_ir"),
            (dict(kind="current"), "invalid_request"),
            (dict(extra_identity=True), "invalid_request"),
        ]
        for fields, error in cases:
            request = wire_request()
            request["program"]["contributions"][0]["branch"].update(fields)
            with self.subTest(fields=fields):
                self.request(request, error)
        for malformed in ("r,y", {}, None):
            request = wire_request()
            request["program"]["contributions"][0]["branch"] = malformed
            with self.subTest(branch=malformed):
                self.request(request, "invalid_request")

    def test_conflicting_bindings_and_port_aliases_are_rejected(self):
        for mutation in ("same_branch", "shared_node", "alias", "ground", "same_local_node"):
            request = wire_request()
            program = request["program"]
            first = program["contributions"][0]
            other = copy.deepcopy(first)
            program["nodes"] += ["u", "v"]
            if mutation == "same_branch":
                other["negative"] = 2
            elif mutation == "shared_node":
                other["branch"]["local_negative"] = "z"
                other.update(positive=2, negative=3)
            elif mutation == "alias":
                other["branch"]["local_negative"] = "z"
            elif mutation == "ground":
                other["branch"]["local_positive"] = "0"
                other["positive"] = 2
            else:
                other["branch"]["local_negative"] = "r"
            program["contributions"].append(other)
            with self.subTest(mutation=mutation):
                self.request(request, "invalid_ir")

    def test_old_and_unknown_versions_are_rejected_before_payload_decoding(self):
        for version in (1, 2, 3, 4, 5, 6, 7, 8, 99):
            request = wire_request()
            request["program"]["schema_version"] = version
            request["program"]["contributions"][0]["branch"] = "r,y"
            with self.subTest(version=version):
                self.request(request, "unsupported_ir_version")
        for version in (None, "2", 2.5):
            request = wire_request()
            request["program"]["schema_version"] = version
            with self.subTest(version=version):
                self.request(request, "invalid_request")

    def test_version_preflight_does_not_hide_duplicate_payload_fields(self):
        payload = json.dumps(wire_request()).replace('"constant": -2', '"constant": -3, "constant": -2')
        self.request(payload, "invalid_request")
