"""Independent semantic variants over the admitted R01 state sampling and operator paths.

One probe model combines the currently supported paths: sequential event state,
conditional input sampling in an event body, transition output and an exact
integral. Equivalent writings of that model -- alpha-renaming, per-instance
inputs and reversed instance order, splitting the independent analog
contributions, an integral of the doubled source instead of a doubled integral,
a selected-expression sampling form, and extra passive observations -- must all
match a separately derived rational answer, the committed state values and the
observed event multiplicity. Event-body statements execute in program order and
are never permuted here. Voltage comparisons use the shared development
tolerance; no exact cross-backend floating equality is required. Negative
controls exercise a genuinely uncertain branch condition and a simultaneous
state-writer conflict. These are development regressions, not new conditions in
the fixed DVS set.
"""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["TRANSITION", "TIMED-OPERATOR", "COMPOSE", "EVENT-ORDER", "EVENT-CONDITIONS"]

from fractions import Fraction as F
from itertools import permutations
import re
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


# Drives are single binary64-exact linear segments u(t) = intercept + slope*t.
INPUT = (F(1, 4), F(1, 2))    # knots [[0, .25], [6, 3.25]]
INPUT_B = (F(1, 2), F(1, 4))  # knots [[0, .5], [6, 2]]
DRIVES = {"in": [[0, .25], [6, 3.25]], "vin": [[0, .5], [6, 2]]}
EVENT_TIMES = (1, 3, 5)  # timer(1, 2, 1e-8); each ramp of 0.5 finishes before the next.
SPARSE = (0, F(1, 2), 1, F(5, 4), 2, 3, F(13, 4), 4, 5, F(21, 4), 6)
DENSE = tuple(F(k, 16) for k in range(97))
ERROR = F(1, 10**11)  # Absolute development comparison, not a qualification budget.

EVENT_IF = """  @(initial_step) begin n=0; held=0.25; end
  @(timer(1,2,1e-8)) begin
    n=n+1;
    if (V(u,r)>1) held=held+0.5*V(u,r); else held=held-0.25;
  end
"""
EVENT_SELECT = """  @(initial_step) begin n=0; held=0.25; end
  @(timer(1,2,1e-8)) begin
    n=n+1;
    held=held+(V(u,r)>1 ? 0.5*V(u,r) : -0.25);
  end
"""
OPERATORS = ("V(mid,r)<+transition(n,0,0.5,0.5);", "V(acc,r)<+idt(V(u,r),0);")
Y_COMBINED = ("V(y,r)<+gain*V(mid,r)+held+2*V(acc,r);",)
Y_SPLIT = ("V(y,r)<+gain*V(mid,r);", "V(y,r)<+held;", "V(y,r)<+2*V(acc,r);")
# Integrating the doubled source is the same mathematics as doubling the integral.
DOUBLED_OPERATORS = OPERATORS + ("V(dacc,r)<+idt(2*V(u,r),0);",)
Y_DOUBLED = ("V(y,r)<+gain*V(mid,r);", "V(y,r)<+held;", "V(y,r)<+V(dacc,r);")
TAPS = "\nV(probe,r)<+V(mid,r); V(snapshot,r)<+held+2*V(acc,r);"


def hand_answer(t, gain=F(1), drive=INPUT):
    """Rational trajectory derived from the input knots, not from EVAS output."""
    intercept, slope = drive
    value = lambda time: intercept+slope*time
    n, held, last = 0, F(1, 4), None
    for k in EVENT_TIMES:
        if k > t:
            break
        n, last = n+1, F(k)
        held = held+(value(F(k))/2 if value(F(k)) > 1 else F(-1, 4))
    mid = F(0) if last is None else F(n-1)+min(F(1), max(F(0), 2*(t-last)))
    acc = intercept*t+slope*t*t/2  # Exact area of the one linear segment.
    return {"n": F(n), "held": held, "mid": mid, "acc": acc,
            "dacc": 2*acc, "probe": mid, "snapshot": held+2*acc, "y": gain*mid+held+2*acc}


def hand_events(labels=(("a", INPUT), ("b", INPUT))):
    # Each timer row reports the batch state of both instances, in label order.
    held = {label: F(1, 4) for label, _ in labels}
    events = []
    for count, t in enumerate(EVENT_TIMES):
        before = tuple(v for label, _ in labels for v in (F(count), held[label]))
        held = {label: hand_answer(F(t), drive=drive)["held"] for label, drive in labels}
        after = tuple(v for label, _ in labels for v in (F(count+1), held[label]))
        events.extend((F(t), "timer", label, before, after) for label, _ in labels)
    return sorted(events)


def run_probe(event=EVENT_IF, operators=OPERATORS, contributions=Y_COMBINED, *,
              rename="none", taps=False, times=SPARSE, separate=False, order=("a", "b")):
    doubled = any("dacc" in statement for statement in operators+contributions)
    declarations = ("integer n; real held; parameter real gain=1; electrical mid,acc,dacc;"
                    if doubled else "integer n; real held; parameter real gain=1; electrical mid,acc;")
    ports = "u,y,probe,snapshot,r" if taps else "u,y,r"
    directions = ("input u; output y,probe,snapshot; inout r;" if taps
                  else "input u; output y; inout r;")
    source = model(event+"\n".join(operators+contributions)+(TAPS if taps else ""),
                   declarations, ports=ports, directions=directions)
    local = (dict(m="renamed_model", u="drive", y="out", r="ref", mid="hidden", n="aa_count",
                  held="zz_sample", gain="factor", acc="store", dacc="twostore",
                  probe="tap", snapshot="memory") if rename in ("locals", "all") else {})
    source = re.sub(r"\b[A-Za-z_]\w*\b", lambda match: local.get(match[0], match[0]), source)
    # Reverse output/instance sort order as well as spelling; ground is fixed.
    node = lambda name: ({"a": "out_z", "b": "out_a"}.get(name, f"net_{name}")
                         if rename in ("nodes", "all") else name)
    owner = lambda name: {"a": "unit_z", "b": "unit_a"}[name] if rename in ("instances", "all") else name
    instances = []
    for label in order:
        ports_map = {"u": node("in" if label == "a" or not separate else "vin"),
                     "y": node(label), "r": "0"}
        if taps:
            ports_map.update(probe=node(f"{label}_probe"), snapshot=node(f"{label}_snapshot"))
        instances.append(instance(owner(label), module=local.get("m", "m"),
                                  connections={local.get(p, p): n for p, n in ports_map.items()},
                                  parameters={local.get("gain", "gain"): dict(a=1, b=-2)[label]}))
    program = compile_sources({"variants.va": source}, instances)
    driven = ({node("in"): DRIVES["in"], node("vin"): DRIVES["vin"]} if separate
              else {node("in"): DRIVES["in"]})
    result = transient(program, driven, list(map(float, times)), stop=6, max_step=6,
                       kernel=KERNEL, vabstol=1e-12, reltol=1e-10)
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
            sample[label, "acc"] = F(voltages[f"{owner(label)}:{local.get('acc', 'acc')}"])
            if doubled:
                sample[label, "dacc"] = F(voltages[f"{owner(label)}:{local.get('dacc', 'dacc')}"])
            if taps:
                sample[label, "probe"] = F(voltages[node(f"{label}_probe")])
                sample[label, "snapshot"] = F(voltages[node(f"{label}_snapshot")])
        samples[t] = sample
    owners = {owner(label): label for label in ("a", "b")}
    ir_events = program.to_dict()["events"]
    events = [(F(event["time"]), event["kind"],
                     owners[ir_events[event["event"]]["origin"]["instance"]],
                     tuple(F(event["before"][j]) for j in state_indices),
                     tuple(F(event["after"][j]) for j in state_indices))
                    for event in result["transient"]["events"]]
    return samples, canonical_events(events)


def canonical_events(events):
    """Allow only same-time independent-instance permutations, never time travel."""
    from itertools import groupby
    if any(left[0] > right[0] for left, right in zip(events, events[1:])):
        raise AssertionError("event records are not chronological")
    return [event for _, batch in groupby(events, key=lambda event: event[0])
            for event in sorted(batch)]


class NightSemanticVariants(unittest.TestCase):
    def test_event_order_calibration_rejects_reversed_physical_time(self):
        expected = hand_events((("a", INPUT), ("b", INPUT)))
        with self.assertRaisesRegex(AssertionError, "not chronological"):
            canonical_events(list(reversed(expected)))

    def test_event_order_calibration_allows_only_same_time_permutations(self):
        expected = hand_events((("a", INPUT), ("b", INPUT)))
        swapped = [event for i in range(0, len(expected), 2)
                   for event in reversed(expected[i:i+2])]
        self.assertEqual(canonical_events(swapped), expected)

    def assert_hand_answers(self, samples, events, *, taps=False, doubled=False,
                            separate=False):
        labels = (("a", F(1), INPUT), ("b", F(-2), INPUT_B if separate else INPUT))
        optional = {"dacc": doubled, "probe": taps, "snapshot": taps}
        for t, sample in samples.items():
            for label, gain, drive in labels:
                expected = hand_answer(t, gain, drive)
                for key, value in expected.items():
                    if key not in optional or optional[key]:
                        if key in ("n", "held"):
                            self.assertEqual(sample[label, key], value, (t, label, key))
                        else:
                            self.assertLessEqual(abs(sample[label, key]-value), ERROR, (t, label, key))
        self.assertEqual(events, hand_events(tuple((label, drive)
                                                   for label, _, drive in labels)))

    def assert_common_samples(self, baseline, actual):
        for t, expected in baseline.items():
            for key, value in expected.items():
                self.assertLessEqual(abs(actual[t][key]-value), ERROR, (t, key))

    def test_baseline_probe_matches_rational_hand_answers(self):
        samples, events = run_probe()
        self.assert_hand_answers(samples, events)

    def test_equivalent_decompositions_preserve_answer_and_events(self):
        baseline, events = run_probe()
        self.assert_hand_answers(baseline, events)
        variants = [(EVENT_IF, OPERATORS, order) for order in permutations(Y_SPLIT)]
        variants.append((EVENT_IF, DOUBLED_OPERATORS, Y_DOUBLED))
        variants.append((EVENT_SELECT, OPERATORS, Y_COMBINED))
        for event, operators, contributions in variants:
            doubled = any("dacc" in statement for statement in operators+contributions)
            with self.subTest(select_form=event is EVENT_SELECT, doubled=doubled,
                              contributions=contributions):
                samples, observed = run_probe(event, operators, contributions)
                self.assert_hand_answers(samples, observed, doubled=doubled)
                self.assert_common_samples(baseline, samples)
                self.assertEqual(events, observed)

    def test_renaming_preserves_bindings_answers_and_events(self):
        baseline, events = run_probe()
        for rename in ("nodes", "instances", "locals", "all"):
            with self.subTest(rename=rename):
                samples, renamed_events = run_probe(rename=rename)
                self.assert_hand_answers(samples, renamed_events)
                self.assert_common_samples(baseline, samples)
                self.assertEqual(events, renamed_events)

    def test_independent_instances_own_inputs_and_order(self):
        baseline = None
        for order in (("a", "b"), ("b", "a")):
            with self.subTest(order=order):
                samples, events = run_probe(separate=True, order=order)
                self.assert_hand_answers(samples, events, separate=True)
                if baseline is not None:
                    self.assert_common_samples(baseline, samples)
                    self.assertEqual(baseline_events, events)
                else:
                    baseline, baseline_events = samples, events

    def test_extra_observation_times_and_unloaded_taps_preserve_history(self):
        baseline, events = run_probe()
        for taps, times in ((True, SPARSE), (False, DENSE), (True, DENSE)):
            with self.subTest(taps=taps, samples=len(times)):
                samples, observed_events = run_probe(taps=taps, times=times)
                self.assert_hand_answers(samples, observed_events, taps=taps)
                self.assert_common_samples(baseline, samples)
                self.assertEqual(events, observed_events)

    def uncertain_run(self, points):
        source = model("""@(initial_step) begin n=0; held=0.25; end
            @(timer(0.5,0,0.001)) begin n=n+1;
              if (V(u,r)>0.5) held=held+0.5*V(u,r); else held=held-0.25; end
            V(mid,r)<+transition(n,0,0.5,0.5);
            V(acc,r)<+idt(V(u,r),0);
            V(y,r)<+V(mid,r)+held+2*V(acc,r);""",
                       "integer n; real held; electrical mid,acc;")
        program = compile_sources({"variants.va": source}, [instance()])
        return transient(program, {"u": points}, [0, .5, 1], stop=1, max_step=1,
                         kernel=KERNEL, vabstol=1e-12, reltol=1e-10)

    def test_uncertain_branch_condition_is_refused_and_decidable_input_passes(self):
        # The exact midpoint of the submitted binary64 endpoints differs from
        # 0.5 and its enclosure straddles 0.5, so no branch may be selected.
        with self.assertRaisesRegex(KernelError, "event_condition"):
            self.uncertain_run([[0, .1], [1, .9]])
        # Same model with a provably sub-threshold sample takes the else branch.
        result = self.uncertain_run([[0, .1], [1, .7]])
        self.assertEqual(result["transient"]["states"], [[0, .25], [1, 0], [1, 0]])

    def test_simultaneous_writers_conflict_but_sequential_writers_commit(self):
        writers = """@(initial_step) held=0.25;
          @(timer({first},0,0.001)) held=held+1;
          @(timer({second},0,0.001)) held=held-1;
          V(y,r)<+held;"""
        conflict = model(writers.format(first=0.5, second=0.5), "real held;")
        with self.assertRaisesRegex(KernelError, "event_conflict"):
            transient(compile_sources({"variants.va": conflict}, [instance()]),
                      {"u": [[0, .25], [2, .25]]}, [0, 1], stop=1, max_step=1, kernel=KERNEL)
        sequential = model(writers.format(first=0.5, second=1.5), "real held;")
        result = transient(compile_sources({"variants.va": sequential}, [instance()]),
                           {"u": [[0, .25], [2, .25]]}, [0, .5, 1.5], stop=1.5,
                           max_step=1.5, kernel=KERNEL)
        self.assertEqual(result["transient"]["states"], [[.25], [1.25], [.25]])
        y = result["nodes"].index("y")
        self.assertEqual([row["voltages"][y] for row in result["solutions"]], [.25, 1.25, .25])


if __name__ == "__main__":
    unittest.main()
