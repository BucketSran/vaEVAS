"""Conditional model timestep caps must remain local to their active interval."""
GUARDS = ["DYNAMICS", "TIMER"]

from fractions import Fraction
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evas import compile_sources
from evas.runtime import _invoke
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get("EVAS_CAUSAL_KERNEL", DEFAULT_KERNEL))
TIMES = [0.0, 0.125, 0.25, 0.5, 0.75, 1.0]
MAX_STEP = 1.0 / 512.0


def execute(control):
    source = model(
        control + "V(y,r)<+idt(V(u,r)/(1+V(u,r)*V(u,r)),0.25);",
        "real q;",
    )
    program = compile_sources({"conditional-mesh.va": source}, [instance()])
    request = dict(
        program=program.to_dict(), driven=["u"], samples=[],
        tolerances=dict(absolute=1e-8, relative=0.0),
        transient=dict(pwl=[[[0.0, 1.0], [1.0, 1.0]]],
                       output_times=TIMES, stop=1.0, max_step=MAX_STEP),
    )
    with tempfile.TemporaryDirectory() as directory, patch.dict(
        os.environ, EVAS_DIAGNOSTICS_RECORDS="65536", EVAS_DIAGNOSTICS_BYTES="8388608"
    ):
        path = Path(directory) / "diagnostics.json"
        result = _invoke(request, KERNEL, timeout=30, diagnostics_path=path)
        report = json.loads(path.read_text())
    return result, report


class ConditionalHistoryMesh(unittest.TestCase):
    def check_voltage(self, result):
        y = result["nodes"].index("y")
        # With u=1, the derivative is exactly 1/2 and the IC is 1/4.
        for t, solution in zip(TIMES, result["solutions"]):
            self.assertLessEqual(abs(solution["voltages"][y] - (0.25 + 0.5*t)), 1e-8)

    def segments(self, report):
        self.assertFalse(report["truncated"])
        return [r for r in report["records"]
                if r["kind"] == "nonlinear_candidate" and r["outcome"] == "certified"]

    def test_inactive_tight_cap_does_not_exhaust_history_work(self):
        result, report = execute(
            "@(initial_step) q=-1; if(q>=0) $bound_step(0.0000152587890625);"
        )
        self.check_voltage(result)
        segments = self.segments(report)
        self.assertTrue(segments)
        self.assertTrue(any(r["end"]-r["start"] > 1.0/65536 for r in segments))

    def test_short_time_window_caps_only_its_own_history(self):
        cap = Fraction(1, 65536)
        result, report = execute(
            "if($abstime>=0.25) if($abstime<0.265625) "
            "$bound_step(0.0000152587890625);"
        )
        self.check_voltage(result)
        segments = self.segments(report)
        active = [r for r in segments if r["start"] >= 0.25 and r["end"] <= 0.265625]
        self.assertTrue(active)
        for r in active:
            self.assertLessEqual(Fraction(r["end"])-Fraction(r["start"]), cap)
        inactive = [r for r in segments if r["end"] <= 0.25 or r["start"] >= 0.265625]
        self.assertTrue(any(Fraction(r["end"])-Fraction(r["start"]) > cap for r in inactive))

    def test_event_epoch_preserves_activation_and_releases_the_cap(self):
        cap = Fraction(1, 4096)
        result, report = execute(
            "@(initial_step) q=0; @(timer(0.25,0)) q=1; "
            "@(timer(0.5,0)) q=0; if(q>0) $bound_step(0.000244140625);"
        )
        self.check_voltage(result)
        segments = self.segments(report)
        active = [r for r in segments if r["start"] >= 0.25 and r["end"] <= 0.5]
        self.assertTrue(active)
        for r in active:
            self.assertLessEqual(Fraction(r["end"])-Fraction(r["start"]), cap)
        for lo, hi in [(0.0, 0.25), (0.5, 1.0)]:
            inactive = [r for r in segments if r["start"] >= lo and r["end"] <= hi]
            self.assertTrue(any(Fraction(r["end"])-Fraction(r["start"]) > cap for r in inactive))


if __name__ == "__main__":
    unittest.main()
