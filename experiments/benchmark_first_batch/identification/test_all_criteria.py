"""Synthetic row-level contract calibration, not Spectre or VA execution."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"benchmark/checkers"))
from first_batch_identification import evaluate
from prepare_candidates import VARIANTS
import build_sh,build_sc,build_driver,build_comparator,build_pll


def fixture(task,c):
    times={0,c["stop"]}
    times.update(p["time"] for p in c["probes"])
    for grid in c.get("sample_grids",[]):
        times.update(grid["start"]+j*grid["step"] for j in range(len(grid["expected"])))
    for m in c.get("metrics",[]):times.update((m["t1"],m["t2"]))
    for e in c.get("crossings",[]):
        for t in e["expected_times"]:times.update((t-.5e-9,t,t+.5e-9))
        times.update((e["start"],e["end"]))
    rows=[]
    if task=="identify-sc-clocked-filter":
        samples=build_sc.observations(c)
    for t in sorted(times):
        if task=="identify-sh-acquisition":out=build_sh.value(c,t)
        elif task=="identify-adc-driver-settling":out=build_driver.value(c,t)
        elif task=="identify-comparator-overdrive":out=build_comparator.level(c,t)
        elif task=="identify-sc-clocked-filter":
            # No transition is observed by its probe contract.
            k=min(len(samples)-1,int((t-9e-9)/c["clock_period"])-1)
            out=samples[k] if k>=0 else 0
        else:out,tune,error=build_pll.observations(c,t)
        r=dict(time=t,out=out)
        if task=="identify-pll-hop-dynamics":r["tune"]=tune
        rows.append(r)
    return rows


class IdentificationCriteria(unittest.TestCase):
    def test_reference_contract_rows_for_all_experiments(self):
        for task in VARIANTS:
            cases=json.loads((ROOT/"benchmark/tasks"/task/"tests/cases.json").read_text())
            for c in cases:
                result=evaluate(fixture(task,c),c)
                self.assertTrue(result["passed"],(task,c["name"],result["failures"][:3]))

    def test_local_bias_missing_output_and_time_rejected(self):
        for task in VARIANTS:
            c=json.loads((ROOT/"benchmark/tasks"/task/"tests/cases.json").read_text())[0]
            rows=fixture(task,c)
            for r in rows:r["out"]+=.03
            self.assertFalse(evaluate(rows,c)["passed"],task)
            rows=fixture(task,c);del rows[0]["out"]
            self.assertFalse(evaluate(rows,c)["passed"],task)
            rows=fixture(task,c);rows[3]["time"]=rows[2]["time"]
            self.assertFalse(evaluate(rows,c)["passed"],task)

    def test_correct_monitor_with_wrong_clock_phase_rejected(self):
        c=json.loads((ROOT/"benchmark/tasks/identify-pll-hop-dynamics/tests/cases.json").read_text())[0]
        rows=fixture("identify-pll-hop-dynamics",c)
        for r in rows:r["out"]=0
        result=evaluate(rows,c)
        self.assertFalse(result["passed"])
        self.assertEqual(result["max_error_V"]["instantaneous-frequency-monitor"],0)

    def test_comparator_missing_or_late_decision_rejected(self):
        cases=json.loads((ROOT/"benchmark/tasks/identify-comparator-overdrive/tests/cases.json").read_text())
        c=cases[0];rows=fixture("identify-comparator-overdrive",c)
        for r in rows:r["out"]=0
        self.assertFalse(evaluate(rows,c)["passed"])
        c=cases[2];rows=fixture("identify-comparator-overdrive",c)
        for r in rows:
            if 40e-9<r["time"]<60e-9:r["out"]=1
        self.assertFalse(evaluate(rows,c)["passed"])

    def test_sc_low_phase_reset_rejected_for_all_experiments(self):
        cases=json.loads((ROOT/"benchmark/tasks/identify-sc-clocked-filter/tests/cases.json").read_text())
        for c in cases:
            rows=fixture("identify-sc-clocked-filter",c)
            for row in rows:
                if row["time"] % c["clock_period"] > .5*c["clock_period"]:
                    row["out"]=0
            old=copy.deepcopy(c)
            old.pop("sample_grids")
            self.assertTrue(evaluate(rows,old)["passed"],c["name"])
            result=evaluate(rows,c)
            self.assertFalse(result["passed"],c["name"])
            self.assertGreater(result["max_error_V"]["full-cycle-hold"],2e-5)

    def test_pll_grid_alias_ripple_rejected_for_all_experiments(self):
        cases=json.loads((ROOT/"benchmark/tasks/identify-pll-hop-dynamics/tests/cases.json").read_text())
        for c in cases:
            rows=fixture("identify-pll-hop-dynamics",c)
            for row in rows:
                row["out"]+=.1*math.sin(2*math.pi*row["time"]/5e-7)
            old=copy.deepcopy(c);old.pop("sample_grids")
            self.assertTrue(evaluate(rows,old)["passed"],c["name"])
            result=evaluate(rows,c)
            self.assertFalse(result["passed"],c["name"])
            self.assertGreater(result["max_error_V"]["phase-coherent-output"],.09)
            self.assertEqual(result["max_error_V"]["instantaneous-frequency-monitor"],0)

    def test_actual_public_fits_generate_each_mutant(self):
        for task,variants in VARIANTS.items():
            p=ROOT/"benchmark/tasks"/task/"solution/fit.py"
            spec=importlib.util.spec_from_file_location(task,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            parameters=m.fit(p.parents[1]/"environment/public")
            reference=m.model(parameters)
            self.assertIn("module identified_",reference)
            for variant in variants:self.assertNotEqual(reference,m.model(parameters,variant),(task,variant))


if __name__=="__main__":unittest.main()
