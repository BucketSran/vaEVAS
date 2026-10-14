"""An uncertain sign may be irrelevant when both certified paths do the same work."""
GUARDS = ["LANG", "TIMER", "COMPOSE", "EVENT-ORDER"]

import os
from pathlib import Path
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get("EVAS_BRANCH_KERNEL", DEFAULT_KERNEL))
TIMES = [0., 0.4, 0.5, 0.6]


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
        # Independent answer: the sample is 0.3**3/3, close to 0.009.
        # Its rounding enclosure crosses 0.009, but either absolute-value
        # sign path is well within the unchanged 0.001 threshold.
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
        self.assert_condition_rejected("if(h>=0.009)q=0.0;else q=-0.0;", q_kind="real")

    def test_common_display_after_the_equivalent_paths_is_preserved(self):
        result = execute('q=(abs(h-0.009)<=0.001)?1:2;$display("good=%d",q);')
        self.assertEqual([r["text"] for r in result["transient"]["display_records"]], ["good=1"])

    def test_different_writes_still_require_a_proved_sign(self):
        self.assert_condition_rejected("if(h>=0.009)q=1;else q=2;")

    def test_equal_terminal_value_is_not_equal_write_history(self):
        self.assert_condition_rejected("if(h>=0.009)begin q=1;q=2;end else q=2;")

    def test_a_direct_absolute_value_keeps_its_distinct_formulas(self):
        # The two formulas are different even when their point values are tiny.
        self.assert_condition_rejected("q=abs(h-0.009);", q_kind="real")

    def test_branch_displays_cannot_be_chosen_from_an_uncertain_sign(self):
        self.assert_condition_rejected('if(h>=0.009)begin q=1;$display("positive");end else begin q=1;$display("negative");end')

    def test_alternative_predicate_reads_keep_cross_block_writer_checks(self):
        # The canonical yes arm does not read b. The proof of its alternative
        # does, so the concurrent writer must still be rejected.
        with self.assertRaises(KernelError) as caught:
            execute("if(h>=0.009)q=1;else if(b>=0)q=1;else q=1;",
                    extra="@(timer(0.5))b=1;")
        self.assertEqual(caught.exception.detail["kind"], "unsupported_cross")
        self.assertIn("another selected block", caught.exception.detail["message"])

    def test_alternative_search_has_a_shared_work_limit(self):
        body = "q=1;"
        for _ in range(7):
            body = "if(h>=0.009)begin " + body + " end else begin " + body + " end"
        self.assert_condition_rejected(body)
