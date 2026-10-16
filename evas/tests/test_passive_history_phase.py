"""An isolated observer keeps physical history and independently certified phases."""
GUARDS = ["DYNAMICS", "TIMER", "EVENT-ORDER", "TRANSITION", "COMPOSE"]

from fractions import Fraction as F
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import unittest

from evas import Instance, KernelError, compile_sources, transient
from evas.ir import Affine, Binary, StateRef
from test_affine import KERNEL as DEFAULT_KERNEL

KERNEL = Path(os.environ.get("EVAS_PASSIVE_HISTORY_KERNEL", DEFAULT_KERNEL))
DUE = F(1, 3) + F(0.1)


def neighbours(exact):
    near = float(exact)
    return [math.nextafter(near, -math.inf), near, math.nextafter(near, math.inf)]


def execute(name, *, forced=False, dense=False, physical="", observer="",
            nonlinear=True, overlap=False, mixed=False, hidden_external=False):
    flow = "1/(1+V(u)*V(u))" if nonlinear else "1+V(z)"
    duration = float(F(1, 3)) if overlap else 0.125
    edge = (f"@(timer(0.1,0)) q=1;V(e)<+transition(q,0,{duration!r});"
            if overlap else "V(e)<+0;")
    mixed_body = ("@(cross(V(u)-1,1,1e-9,1e-9)) due=$abstime+0.1;"
                  "@(timer(due,0,1e-9)) q=q+1;" if mixed else "")
    source = f'''`include "disciplines.vams"
module physical(u,z,e);input u;output z,e;electrical u,z,e;real q,due;
analog begin @(initial_step) begin q=0;due=100;end
V(z)<+idt({flow},0);{edge}{mixed_body}{physical} end endmodule
module observer(u,z);input u,z;electrical u,z,dummy;real due,seen;integer count;
analog begin @(initial_step) begin due=100;seen=0;count=0;end
@(cross(V(u)-1,1,1e-9,1e-9)) due=$abstime+0.1;
@(timer(due,0,1e-9)) begin count=count+1;seen=V(z);$display("sample %d",count);end
{observer} end endmodule'''
    program = compile_sources({"passive-phase.va": source}, [
        Instance("D", "physical", {"u": "u", "z": "z", "e": "e"}),
        Instance("M", "observer", {"u": "u", "z": "z"})])
    if hidden_external:
        # Deliberately invalid ownership in the complete original IR. A zero
        # factor cannot authorize dropping a foreign physical consumer.
        state = next(i for i, s in enumerate(program.states)
                     if s.instance == "M" and s.name == "seen")
        first, *rest = program.contributions
        reference = Binary("multiply", Affine(0.0, ()), StateRef(state))
        first = replace(first, rhs=Binary("add", first.rhs, reference))
        program = replace(program, contributions=(first, *rest))
    times = [0.0, 0.3, *neighbours(DUE), 0.6, 0.75]
    if overlap:
        times += neighbours(F(0.1) + F(duration))
    if dense:
        times += [0.05, 0.1, 0.2, 0.35, 0.4, 0.5, 0.7]
    times = sorted(set(times))
    receipt = {"kernel_sha256": hashlib.sha256(KERNEL.read_bytes()).hexdigest(),
               "source": source, "program": program.to_dict(), "times": times,
               "exact_due": str(DUE), "forced": forced,
               "count_oracle": [int(F(t) >= DUE) for t in times]}
    if overlap:
        receipt["exact_old_deadline"] = str(F(0.1) + F(duration))
        receipt["edge_oracle"] = [min(1.0, max(0.0, float((F(t)-F(0.1))/F(duration))))
                                  for t in times]
    try:
        result = transient(program, {"u": [[0.0, 0.0], [1.0, 3.0]]}, times,
                           stop=0.75, max_step=0.05, vabstol=1e-8, reltol=0.0,
                           strobetimes=times if forced else [], kernel=KERNEL)
        receipt["result"] = result
        return result, times
    except KernelError as error:
        receipt["error"] = error.detail
        raise
    finally:
        destination = os.environ.get("EVAS_PASSIVE_HISTORY_EVIDENCE")
        if destination:
            path = Path(destination)
            path.mkdir(parents=True, exist_ok=True)
            (path / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")


class PassiveHistoryPhase(unittest.TestCase):
    def check_flow(self, result, times, nonlinear=True):
        cross=next(e for e in result['transient']['events']
                   if e['kind']=='cross' and e['origin'].endswith('(M)'))
        te=F(cross['time'])
        self.assertGreater(te,F(1,3))
        self.assertLessEqual(te-F(1,3),F(1e-9))
        self.assertGreater(3*te-1,0)
        self.assertLessEqual(3*te-1,F(1e-9))
        due=te+F(.1)
        z = result["nodes"].index("z")
        for t, row, states in zip(times, result["solutions"], result["transient"]["states"]):
            expected = math.atan(3*t)/3 if nonlinear else math.expm1(t)
            self.assertLessEqual(abs(row["voltages"][z]-expected), 1e-8)
            self.assertEqual(states[-1], int(F(t) >= due))
            if F(t) >= due:
                sample = math.atan(3*float(due))/3 if nonlinear else math.expm1(float(due))
                self.assertLessEqual(abs(states[-2]-sample), 1e-8)
        self.assertEqual([r["text"] for r in result["transient"]["display_records"]], ["sample 1"])

    def test_readonly_dense_queries_keep_common_values_bitexact(self):
        plain, times = execute("nonlinear-plain")
        dense, dense_times = execute("nonlinear-dense", dense=True)
        self.check_flow(plain, times)
        self.check_flow(dense, dense_times)
        self.assertEqual(plain["transient"]["events"], dense["transient"]["events"])
        for time, row in zip(times, plain["solutions"]):
            self.assertEqual(row, dense["solutions"][dense_times.index(time)])

    def test_forced_segmentation_keeps_events_and_the_original_math_budget(self):
        # Strong strobe accepts frames and can split numerical integration.
        # Its public contract promises the original error budget, not identical
        # rounding to the readonly-query segmentation (whose test stays above).
        plain, times = execute("nonlinear-plain")
        forced, forced_times = execute("nonlinear-forced", forced=True)
        self.assertEqual(times,forced_times)
        self.check_flow(plain,times)
        self.check_flow(forced,forced_times)
        self.assertEqual(plain["transient"]["events"],forced["transient"]["events"])
        receipt=forced["strobe_evidence"]
        self.assertEqual(receipt["times"],forced_times)
        self.assertEqual(receipt["sample_origins"],["accepted_controller_frame"]*len(forced_times))
        self.assertEqual(receipt["voltages_V"],[row["voltages"] for row in forced["solutions"]])
        z=forced["nodes"].index("z")
        for t,voltages in zip(forced_times,receipt["voltages_V"]):
            self.assertLessEqual(abs(voltages[z]-math.atan(3*t)/3),1e-8)

    def test_autonomous_affine_flow_observer(self):
        result, times = execute("autonomous", nonlinear=False)
        self.check_flow(result, times, nonlinear=False)

    def test_transition_deadline_overlap_keeps_user_event_order_rejection(self):
        # Exact endpoint and due differ even though their interval enclosures overlap.
        self.assertNotEqual(F(0.1)+F(float(F(1,3))), DUE)
        with self.assertRaises(KernelError) as caught:
            execute("overlap", overlap=True)
        self.assertEqual(caught.exception.detail["kind"], "event_resolution")
        self.assertIn("transition deadline ordering relative to user event",
                      caught.exception.detail["message"])

    def test_physical_and_mixed_callbacks_keep_anchor_requirement(self):
        for name, options in [("physical", {"observer": "V(dummy)<+seen;"}),
                              ("hidden-zero", {"observer": "V(dummy)<+0*seen;"}),
                              ("mixed", {"mixed": True}),
                              ("stepbound", {"observer": "$bound_step(0.05);"})]:
            with self.subTest(name=name):
                # These original sources do not feed the observer's writes
                # back into z. Its exact due is now derived from certified te.
                result,times=execute(name, **options)
                self.check_flow(result,times)

    def test_zero_foreign_physical_state_reference_stays_invalid(self):
        with self.assertRaises(KernelError) as caught:
            execute("hidden-foreign", hidden_external=True)
        self.assertEqual(caught.exception.detail["kind"], "invalid_ir")
        self.assertIn("state", caught.exception.detail["message"])


if __name__ == "__main__":
    unittest.main()
