"""Development regression of the frozen paper circuits through the public API.

Anchor checks and query invariance do not grant paper observation qualification
or establish Spectre compatibility. The separate backend comparison retains both.
Run from a full repository checkout: the cards own the independent answers,
and the paper input builder supplies the same top-module binding as backend runs.
"""

GUARDS = ["COMPOSE", "CROSS", "TIMER", "TRANSITION", "DYNAMICS"]

import importlib.util
import json
from pathlib import Path
import unittest

from evas import Instance, compile_sources, transient
from test_affine import KERNEL


ROOT = Path(__file__).resolve().parents[2]
CARDS = json.loads((ROOT / "evas/validation/paper/core-v1.json").read_text())
SPEC = importlib.util.spec_from_file_location(
    "paper_scenario_inputs", ROOT / "experiments/backends/paper/inputs.py")
INPUTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INPUTS)
T = CARDS["units"]["T_s"]


class PaperScenarios(unittest.TestCase):
    def test_frozen_circuits_keep_anchors_and_history_when_queries_are_added(self):
        budgets = CARDS["shared_contract"]["acceptance_budgets"]
        for card in CARDS["cards"]:
            with self.subTest(condition=card["id"]):
                binding = INPUTS.binding(card)
                program = compile_sources({"dut.va": card["source"]}, [Instance(
                    "dut", binding["top_module"],
                    {port: port for port in binding["ports"]}, card["parameters"])])
                stop = card["stop_T"] * T
                sources = {
                    port: ([[0, source["value_V"]], [stop, source["value_V"]]]
                           if source["kind"] == "dc" else
                           [[t * T, v] for t, v in source["points_T_V"]])
                    for port, source in card["stimulus"].items()
                }
                anchors = {anchor["t_T"] * T for anchor in card["anchors"]}
                sparse = sorted({0.0, stop, *anchors})
                extra = {w[key] * T for w in card["observation_windows"]
                         for key in ("start_T", "center_T", "end_T")}
                dense = sorted({*sparse, *extra,
                                *((a + b) / 2 for a, b in zip(sparse, sparse[1:]))})
                baseline = None
                for times in (sparse, dense):
                    response = transient(
                        program, sources, times, stop=stop, max_step=2e-10,
                        vabstol=1e-7, reltol=1e-5, kernel=KERNEL, timeout=90)
                    rows = {t: dict(zip(response["nodes"], solution["voltages"]))
                            for t, solution in zip(times, response["solutions"], strict=True)}
                    for anchor in card["anchors"]:
                        for key, expected in anchor.items():
                            if key == "t_T":
                                continue
                            port = key.removesuffix("_V")
                            actual = rows[anchor["t_T"] * T][port]
                            error = abs(actual - expected)
                            budget = budgets["static_voltage_V"]
                            if port == "phase":
                                budget = budgets["phase_cycles"]
                                if card["id"] in ("CP-02", "CO-VCO-01"):
                                    slack = CARDS["shared_contract"]["required_observation_error"]["voltage_V"]
                                    self.assertGreaterEqual(actual, -slack)
                                    self.assertLessEqual(actual, 1 + slack)
                                    error = abs((actual - expected + .5) % 1 - .5)
                            elif port == "out" and card["id"] in ("CP-02", "CO-VCO-01"):
                                budget = budgets["sine_voltage_V"]
                            elif port == "out" and card["id"] in (
                                    "TM-01", "CO-SH-01", "CO-HC-01"):
                                # The existing criteria use the edge budget for
                                # this output at every time; held state ports
                                # keep the separate 1mV budget, even after edges.
                                budget = budgets["edge_voltage_V"]
                            self.assertLessEqual(error, budget, (card["id"], anchor, port))
                    for port, expected in card["callback_counts"].items():
                        self.assertAlmostEqual(rows[stop][port], expected,
                                               delta=budgets["counter_voltage_V"])
                    if baseline is None:
                        baseline = (response["transient"]["events"], rows)
                    else:
                        self.assertEqual(response["transient"]["events"], baseline[0])
                        self.assertEqual({t: rows[t] for t in sparse}, baseline[1])


if __name__ == "__main__":
    unittest.main()
