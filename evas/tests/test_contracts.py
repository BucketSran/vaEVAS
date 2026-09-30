"""Parameter binding and versioned branch identity contracts, with hand answers."""

import copy
import json
import math
import subprocess
import unittest

from evas import CompileError, compile_sources
from evas.ir import SCHEMA_VERSION
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
    """Independent current-schema request: V(r)-V(y)=-2, with r bound to ground."""
    return dict(program=dict(schema_version=SCHEMA_VERSION, nodes=["0", "y"], contributions=[dict(
