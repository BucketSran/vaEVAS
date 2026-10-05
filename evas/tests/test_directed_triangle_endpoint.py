"""Original VA07 half-speed endpoint: hand-derived physics, not task scoring."""
GUARDS = ["CROSS", "DYNAMICS", "EVENT-ORDER", "DEV:directed-triangle-endpoint"]

from pathlib import Path
import unittest

from evas import Instance, compile_sources, transient
from test_affine import KERNEL


class DirectedTriangleEndpoint(unittest.TestCase):
    def test_half_speed_original_grid_arrives_at_stop(self):
        root = Path(__file__).resolve().parents[2]
        reference = (root / "benchmark/tasks/va07-triangle-repair/solution/dut.va").read_text()
        expression = "sign*V(ctl,r)"
        self.assertEqual(reference.count(expression), 1)
        source = reference.replace(expression, "0.5*sign*V(ctl,r)")
        program = compile_sources({"dut.va": source}, [Instance(
            "dut", "triangle", dict(ctl="ctl", z="z", count="count", r="0"),
            dict(lower=-0.5, upper=0.5, initial_voltage=0, direction=1,
                 ttol=1e-10, vtol=1e-10))])
        times = [i * 0.005 for i in range(601)]
        result = transient(program, {"ctl": [[0, 1], [3, 1]]}, times,
                           stop=3, max_step=0.005, vabstol=1e-8, reltol=0,
                           kernel=KERNEL, timeout=60)
        # At half speed the upper arrival is t=1 and the lower arrival is
        # exactly t=3. The latter belongs to the arriving segment at stop.
        events = result["transient"]["events"]
        self.assertEqual([event["time"] for event in events], [1, 3])
        self.assertEqual([event["event"] for event in events], [0, 0])
        self.assertEqual([event["fired_triggers"][0]["trigger"] for event in events], [0, 1])
        self.assertEqual([event["after"] for event in events], [[-1, 1], [1, 2]])
        z = result["nodes"].index("z")
        count = result["nodes"].index("count")
        self.assertEqual(len(result["solutions"]), 601)
        for t, row in zip(times, result["solutions"], strict=True):
            expected = 0.5 * t if t <= 1 else 1 - 0.5 * t
            self.assertAlmostEqual(row["voltages"][z], expected, delta=1e-8)
            self.assertEqual(row["voltages"][count], 0 if t < 1 else 1 if t < 3 else 2)


if __name__ == "__main__":
    unittest.main()
