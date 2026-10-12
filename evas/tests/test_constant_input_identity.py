"""A flat physical PWL source must preserve its supplied binary64 value."""
GUARDS = ["LANG", "LIN"]

import math
import unittest

from evas import Instance, compile_sources, transient
from test_affine import KERNEL, model


class ConstantInputIdentity(unittest.TestCase):
    def test_threshold_neighbors_are_exact_at_interior_times(self):
        program = compile_sources({"m.va": model("V(y,r)<+V(u,r);")},
            [Instance("dut", "m", dict(u="u", y="y", r="0"))])
        times = [i / 32 for i in range(33)]
        for value in [math.nextafter(.5, -math.inf), .5,
                      math.nextafter(.5, math.inf), -math.nextafter(.5, -math.inf),
                      math.ulp(0.), 0.]:
            with self.subTest(value=value):
                result = transient(program, {"u": [[0., value], [1., value]]},
                    times, stop=1., max_step=1/32, kernel=KERNEL)
                u = result["nodes"].index("u")
                for row in result["solutions"]:
                    self.assertEqual(row["voltages"][u].hex(), value.hex())
