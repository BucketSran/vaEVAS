"""Behavior tests for criteria. These are synthetic row tests, not VA execution."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"benchmark/checkers"))
from first_batch_identification import evaluate


class SampleHoldCriteria(unittest.TestCase):
    def setUp(self):
        self.cases=json.loads((ROOT/"benchmark/tasks/identify-sh-acquisition/tests/cases.json").read_text())

    def rows(self,case):
        # Separate interpolation fixture uses the fixed contractual probes,
        # plus metric endpoints. It does not call the authoring model.
        values={p["time"]:p["expected"] for p in case["probes"]}
        for m in case["metrics"]:
            # The hold segment is affine. Event endpoints are already probes.
            if m["name"]=="droop":
                hold=[p for p in case["probes"] if p["metric"]=="hold"]
                a,b=hold[0],hold[-1]
                for t in (m["t1"],m["t2"]):
                    values[t]=a["expected"]+(b["expected"]-a["expected"])*(t-a["time"])/(b["time"]-a["time"])
        return [dict(time=t,out=v) for t,v in sorted(values.items())]

    def test_contractual_positive(self):
        for c in self.cases:
            self.assertTrue(evaluate(self.rows(c),c)["passed"],c["name"])

    def test_local_errors_are_rejected(self):
        c=self.cases[0]
        for metric in ("acquisition","hold","reacquisition"):
            rows=self.rows(c)
            target=next(p for p in c["probes"] if p["metric"]==metric)
            next(r for r in rows if r["time"]==target["time"])["out"]+=0.0003
            self.assertFalse(evaluate(rows,c)["passed"],metric)

    def test_no_droop_rejected(self):
        c=self.cases[0]
        rows=self.rows(c)
        start=c["hold_start"]
        for r in rows:
            if start<r["time"]<c["track_again"]:
                r["out"]+=12*(r["time"]-start)
        self.assertFalse(evaluate(rows,c)["passed"])

    def test_float_endpoint_identity_and_real_truncation(self):
        c=self.cases[-1]
        rows=self.rows(c)
        rows[-1]["time"]=math.nextafter(rows[-1]["time"], -math.inf)
        self.assertTrue(evaluate(rows,c)["passed"])
        rows[-1]["time"]-=1e-12
        self.assertFalse(evaluate(rows,c)["passed"])

    def test_truncated_nonfinite_and_bad_time_rejected(self):
        c=self.cases[0]
        rows=self.rows(c)
        self.assertFalse(evaluate(rows[:-10],c)["passed"])
        rows[3]["out"]=float("nan")
        self.assertFalse(evaluate(rows,c)["passed"])
        rows=self.rows(c)
        rows[3]["time"]=rows[2]["time"]
        self.assertFalse(evaluate(rows,c)["passed"])


if __name__=="__main__":
    unittest.main()
