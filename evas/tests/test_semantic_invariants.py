"""Metamorphic history probes, each also checked against rational hand answers.

The original static permutations, instance isolation and dependent assignment
tests remain in test_affine, test_transition and test_settlement. These probes
add history contribution permutations, alpha-renaming and observation taps.
They are development regressions, not new conditions in the fixed DVS set.
"""
from fractions import Fraction as F
from itertools import permutations
import re
import unittest

from evas import compile_sources, transient
from test_affine import KERNEL, instance, model


CONTRIBUTIONS = (
    "V(mid,r)<+transition(n,0,.5,1);",
    "V(mid,r)<+transition(-n,.25,1,.5);",
    "V(mid,r)<+.25*V(u,r);",
)
SPARSE = tuple(map(F, (0, 1, 1.25, 1.5, 1.75, 2, 3, 3.5, 4, 5, 5.25, 5.75, 6)))
DENSE = tuple(F(k, 8) for k in range(49))
ERROR = F(1, 10**11)  # Absolute development comparison, not a qualification budget.


def hand_answer(t, gain):
    ticks = tuple(F(k) for k in (1, 3, 5) if k <= t)
    # Each event adds two to n. Both edges finish before the next event.
    ramp = lambda age: min(F(2), max(F(0), 4*age))
    pulse = sum((ramp(t-k)-ramp(t-k-F(1, 4)) for k in ticks), F(0))
    n = 2*len(ticks)
    held = n-1 if ticks else 0
    mid = pulse+t/8
    return {"y": F(1, 4)+gain*mid+held, "mid": F(1, 4)+mid,
            "n": F(n), "held": F(held)}


def run_probe(order=CONTRIBUTIONS, *, rename="none", taps=False, times=SPARSE):
    source = model("""
        @(initial_step) begin n=0; held=0; end
        @(timer(1,2,1e-8)) begin n=n+1; held=n; n=n+1; end
        """+"\n".join(order)+"\nV(y,r)<+gain*V(mid,r)+held;"
        + ("\nV(probe,r)<+V(mid,r); V(snapshot,r)<+held;" if taps else ""),
        "integer n,held; parameter real gain=1; electrical mid;",
        ports="u,y,r,probe,snapshot" if taps else "u,y,r",
        directions="input u; output y,probe,snapshot; inout r;" if taps
        else "input u; output y; inout r;")
    local = (dict(m="renamed_model", u="drive", y="out", r="ref", mid="hidden",
                  n="aa_count", held="zz_sample", gain="factor", probe="tap", snapshot="memory")
             if rename in ("locals", "all") else {})
    source = re.sub(r"\b[A-Za-z_]\w*\b", lambda match: local.get(match[0], match[0]), source)
    # Reverse output/instance sort order as well as spelling; ground is fixed.
    node = lambda name: ({"a": "out_z", "b": "out_a"}.get(name, f"net_{name}")
                         if rename in ("nodes", "all") else name)
    owner = lambda name: {"a": "unit_z", "b": "unit_a"}[name] if rename in ("instances", "all") else name
    instances = []
    for label, gain in (("a", 1), ("b", -2)):
        ports = {"u": node("input"), "r": node("reference"), "y": node(label)}
        if taps:
            ports.update(probe=node(f"{label}_probe"), snapshot=node(f"{label}_snapshot"))
        instances.append(instance(owner(label), module=local.get("m", "m"),
                                  connections={local.get(p, p): n for p, n in ports.items()},
                                  parameters={local.get("gain", "gain"): gain}))
    program = compile_sources({"invariants.va": source}, instances)
    result = transient(program, {node("input"): [[0, .25], [6, 3.25]],
                                 node("reference"): [[0, .25], [6, .25]]},
                       list(map(float, times)), stop=6, max_step=6, kernel=KERNEL,
                       vabstol=1e-12, reltol=1e-10)
    # Canonicalize only identities, never numeric values or event multiplicity.
    states = [(f"{owner(label)}:{local.get(s, s)}", (label, s))
              for label in ("a", "b") for s in ("n", "held")]
    state_indices = [result["transient"]["state_names"].index(name) for name, _ in states]
    samples = {}
    for k, t in enumerate(times):
        voltages = dict(zip(result["nodes"], result["solutions"][k]["voltages"]))
        sample = {key: F(result["transient"]["states"][k][j])
                  for j, (_, key) in zip(state_indices, states)}
        for label in ("a", "b"):
            sample[label, "y"] = F(voltages[node(label)])
            sample[label, "mid"] = F(voltages[f"{owner(label)}:{local.get('mid', 'mid')}"])
            if taps:
                sample[label, "probe"] = F(voltages[node(f"{label}_probe")])
                sample[label, "snapshot"] = F(voltages[node(f"{label}_snapshot")])
        samples[t] = sample
    owners = {owner(label): label for label in ("a", "b")}
    ir_events = program.to_dict()["events"]
    events = sorted((F(event["time"]), event["kind"],
                     owners[ir_events[event["event"]]["origin"]["instance"]],
                     tuple(F(event["before"][j]) for j in state_indices),
                     tuple(F(event["after"][j]) for j in state_indices))
                    for event in result["transient"]["events"])
    return samples, events


class SemanticInvariants(unittest.TestCase):
    def assert_hand_answers(self, samples, events, *, taps=False):
        for t, sample in samples.items():
            for label, gain in (("a", F(1)), ("b", F(-2))):
                expected = hand_answer(t, gain)
                for key, value in expected.items():
                    if key in ("n", "held"):
                        self.assertEqual(sample[label, key], value)
                    else:
                        self.assertLessEqual(abs(sample[label, key]-value), ERROR, (t, label, key))
                if taps:
                    self.assertLessEqual(abs(sample[label, "probe"]-expected["mid"]), ERROR)
                    self.assertLessEqual(abs(sample[label, "snapshot"]-F(1, 4)-expected["held"]), ERROR)
        expected_events = []
        for count, t in enumerate((1, 3, 5)):
            before = (F(2*count), F(2*count-1 if count else 0))*2
            after = (F(2*count+2), F(2*count+1))*2
            expected_events.extend((F(t), "timer", label, before, after) for label in ("a", "b"))
        self.assertEqual(events, expected_events)

    def assert_common_samples(self, baseline, actual):
        for t, expected in baseline.items():
            for key, value in expected.items():
                self.assertLessEqual(abs(actual[t][key]-value), ERROR, (t, key))

    def test_independent_history_contributions_commute(self):
        baseline = None
        for order in permutations(CONTRIBUTIONS):
            with self.subTest(order=order):
                samples, events = run_probe(order)
                self.assert_hand_answers(samples, events)
                if baseline is not None:
                    self.assert_common_samples(baseline, samples)
                else:
                    baseline = samples

    def test_node_instance_and_local_renaming_preserves_bindings(self):
        baseline, events = run_probe()
        self.assert_hand_answers(baseline, events)
        for rename in ("nodes", "instances", "locals", "all"):
            with self.subTest(rename=rename):
                samples, renamed_events = run_probe(rename=rename)
                self.assert_hand_answers(samples, renamed_events)
                self.assert_common_samples(baseline, samples)
                self.assertEqual(events, renamed_events)

    def test_extra_observation_times_and_unloaded_taps_preserve_history(self):
        baseline, events = run_probe()
        self.assert_hand_answers(baseline, events)
        for taps, times in ((True, SPARSE), (False, DENSE), (True, DENSE)):
            with self.subTest(taps=taps, samples=len(times)):
                samples, observed_events = run_probe(taps=taps, times=times)
                self.assert_hand_answers(samples, observed_events, taps=taps)
                self.assert_common_samples(baseline, samples)
                self.assertEqual(events, observed_events)


if __name__ == "__main__":
    unittest.main()
