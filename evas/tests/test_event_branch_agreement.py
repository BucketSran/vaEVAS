"""An uncertain sign may be irrelevant when both certified paths do the same work."""
GUARDS = ["LANG", "TIMER", "COMPOSE", "EVENT-ORDER"]

from fractions import Fraction
import json
import math
import os
import tempfile
from unittest.mock import patch
from pathlib import Path
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get("EVAS_BRANCH_KERNEL", DEFAULT_KERNEL))
TIMES = [0., 0.4, 0.5, 0.6]
# The original .009 examples are now certified at the execution point.
# This extra threshold lies inside the retained sample enclosure, so the
# original branch-agreement obligations still exercise uncertain choices.
UNCERTAIN_REFERENCE = "0.009000000000000005"


def execute(body, *, times=TIMES, forced=False, extra="", q_kind="integer"):
    source = model(
        "V(y,r)<+idt(V(u,r)*V(u,r),0);V(z,r)<+q;"
        "@(cross(V(u,r)-0.3,1,1e-9,1e-9))h=V(y,r);"
        "@(timer(0.5))begin " + body + " end " + extra,
        f"real h;{q_kind} q;integer b;electrical z;",
    )
    program = compile_sources({"branch.va": source}, [instance()])
    return transient(program, {"u": [[0., 0.], [1., 1.]]}, times,
                     stop=0.6, max_step=0.05,
                     strobetimes=times if forced else [], kernel=KERNEL)


class EventBranchAgreement(unittest.TestCase):
    def assert_condition_rejected(self, body, **kwargs):
        with self.assertRaises(KernelError) as caught:
            execute(body, **kwargs)
        self.assertEqual(caught.exception.detail["kind"], "event_condition")

    def test_abs_threshold_has_the_same_result_on_both_sign_paths(self):
        # Independent answer: the sample is te**3/3, close to 0.009.
        # At the selected execution point its enclosure is above .009;
        # a separate control below retains a genuinely uncertain sign.
        body = "q=(abs(h-0.009)<=0.001)?1:2;"
        ordinary = execute(body)
        z = ordinary["nodes"].index("dut:z")
        self.assertEqual([s["voltages"][z] for s in ordinary["solutions"]], [0., 0., 1., 1.])
        forced = execute(body, forced=True)
        self.assertEqual(ordinary["solutions"], forced["solutions"])
        self.assertEqual(ordinary["transient"]["events"], forced["transient"]["events"])

    def test_both_sign_paths_can_prove_that_no_write_is_needed(self):
        result = execute("if(abs(h-0.009)>0.001)q=2;")
        z = result["nodes"].index("dut:z")
        self.assertEqual([row["voltages"][z] for row in result["solutions"]], [0., 0., 0., 0.])
        self.assertEqual(len(result["transient"]["events"]), 2)

    def test_signed_zero_formulas_are_not_merged(self):
        self.assert_condition_rejected(f"if(h>={UNCERTAIN_REFERENCE})q=0.0;else q=-0.0;", q_kind="real")

    def test_common_display_after_the_equivalent_paths_is_preserved(self):
        result = execute('q=(abs(h-0.009)<=0.001)?1:2;$display("good=%d",q);')
        self.assertEqual([r["text"] for r in result["transient"]["display_records"]], ["good=1"])

    def test_different_writes_still_require_a_proved_sign(self):
        self.assert_condition_rejected(f"if(h>={UNCERTAIN_REFERENCE})q=1;else q=2;")

    def test_equal_terminal_value_is_not_equal_write_history(self):
        self.assert_condition_rejected(f"if(h>={UNCERTAIN_REFERENCE})begin q=1;q=2;end else q=2;")

    def test_a_direct_absolute_value_keeps_its_distinct_formulas(self):
        # The two formulas are different even when their point values are tiny.
        self.assert_condition_rejected(f"q=abs(h-{UNCERTAIN_REFERENCE});", q_kind="real")

    def test_branch_displays_cannot_be_chosen_from_an_uncertain_sign(self):
        self.assert_condition_rejected(f'if(h>={UNCERTAIN_REFERENCE})begin q=1;$display("positive");end else begin q=1;$display("negative");end')

    def test_alternative_predicate_reads_keep_cross_block_writer_checks(self):
        # The canonical yes arm does not read b. The proof of its alternative
        # does, so the concurrent writer must still be rejected.
        with self.assertRaises(KernelError) as caught:
            execute(f"if(h>={UNCERTAIN_REFERENCE})q=1;else if(b>=0)q=1;else q=1;",
                    extra="@(timer(0.5))b=1;")
        self.assertEqual(caught.exception.detail["kind"], "unsupported_cross")
        self.assertIn("another selected block", caught.exception.detail["message"])

    def test_alternative_search_has_a_shared_work_limit(self):
        body = "q=1;"
        for _ in range(7):
            body = f"if(h>={UNCERTAIN_REFERENCE})begin " + body + " end else begin " + body + " end"
        self.assert_condition_rejected(body)


class PointExecutionBranchControls(unittest.TestCase):
    """Keep every original source and .009 threshold as an acceptance control."""

    def test_original_sources_choose_the_certified_execution_point_path(self):
        cases = [
            ("signed_zero", "if(h>=0.009)q=0.0;else q=-0.0;", "real", "", 0.),
            ("different_writes", "if(h>=0.009)q=1;else q=2;", "integer", "", 1.),
            ("write_history", "if(h>=0.009)begin q=1;q=2;end else q=2;", "integer", "", 2.),
            ("absolute_value", "q=abs(h-0.009);", "real", "", .009000000000000005-.009),
            ("display", 'if(h>=0.009)begin q=1;$display("positive");end else begin q=1;$display("negative");end', "integer", "", 1.),
            ("unselected_reader", "if(h>=0.009)q=1;else if(b>=0)q=1;else q=1;", "integer", "@(timer(0.5))b=1;", 1.),
        ]
        body = "q=1;"
        for _ in range(7):
            body = "if(h>=0.009)begin " + body + " end else begin " + body + " end"
        cases.append(("no_alternative_search", body, "integer", "", 1.))
        for name, body, kind, extra, expected in cases:
            with self.subTest(name=name):
                result = execute(body, q_kind=kind, extra=extra)
                crossing = result["transient"]["events"][0]
                te = crossing["time"]
                self.assertEqual(te, .30000000000000004)
                self.assertEqual(crossing["guard_value"], float(Fraction(te)-Fraction(.3)))
                self.assertGreater(Fraction(te)**3/3, Fraction(.009))
                self.assertEqual(crossing["after"][0], .009000000000000005)
                q = result["transient"]["states"][-1][result["transient"]["state_names"].index("dut:q")]
                self.assertEqual(q, expected)
                if name == "signed_zero":
                    self.assertEqual(math.copysign(1., q), 1.)
                if name == "display":
                    self.assertEqual([r["text"] for r in result["transient"]["display_records"]], ["positive"])
                if name == "unselected_reader":
                    b = result["transient"]["state_names"].index("dut:b")
                    self.assertEqual(result["transient"]["states"][-1][b], 1.)

    def test_sample_enclosure_contains_independent_integral_and_crosses_new_reference(self):
        result = execute("q=h;", q_kind="real")
        te = result["transient"]["events"][0]["time"]
        self.assertEqual(te, .30000000000000004)
        exact = Fraction(te)**3/3
        z = result["nodes"].index("dut:z")
        lo, hi = result["observation_evidence"]["voltage_bounds_V"][-1][z]
        self.assertEqual([lo, hi], [.009000000000000001, .009000000000000006])
        self.assertLessEqual(Fraction(lo), exact)
        self.assertLessEqual(exact, Fraction(hi))
        self.assertGreater(lo, .009)
        self.assertLess(lo, float(UNCERTAIN_REFERENCE))
        self.assertGreater(hi, float(UNCERTAIN_REFERENCE))

    def test_uncertain_equivalent_paths_keep_common_display_and_query_invariance(self):
        body = f'q=(abs(h-{UNCERTAIN_REFERENCE})<=0.001)?1:2;$display("good=%d",q);'
        ordinary = execute(body)
        forced = execute(body, forced=True)
        self.assertEqual([r["text"] for r in ordinary["transient"]["display_records"]], ["good=1"])
        self.assertEqual(ordinary["solutions"], forced["solutions"])
        self.assertEqual(ordinary["transient"]["events"], forced["transient"]["events"])

    def test_uncertain_alternative_search_uses_the_shared_64_attempt_budget(self):
        for depth in (5, 6, 7):
            body = "q=1;"
            for _ in range(depth):
                body = f"if(h>={UNCERTAIN_REFERENCE})begin " + body + " end else begin " + body + " end"
            with self.subTest(depth=depth):
                if depth == 5:
                    # 31 uncertain predicates need 62 extra arm proofs.
                    self.assertEqual(execute(body)["transient"]["states"][-1][-1], 1.)
                    continue
                with tempfile.TemporaryDirectory() as directory:
                    diagnostic = Path(directory)/"branches.json"
                    with patch.dict(os.environ, EVAS_DIAGNOSTICS_PATH=str(diagnostic)):
                        with self.assertRaises(KernelError) as caught:
                            execute(body)
                    self.assertEqual(caught.exception.detail["kind"], "event_condition")
                    self.assertEqual(json.loads(diagnostic.read_text())["counters"]["event_branch_proof_attempts"], 64)
