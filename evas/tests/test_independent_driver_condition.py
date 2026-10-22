"""Issue #65 (MUX first blocker): an event condition reads an independent driver's state.

Minimal case from the 2026-10-16 MUX diagnosis of the original ``mux-0/1/2``
requests, which main refuses with ``kernel.unsupported_condition``. Module
``driver`` holds an integer state q=1 and contributes ``V(u)<+q``. Module
``receiver`` executes ``@(timer(0.5)) if(V(u)>0.5) p=1`` and contributes
``V(y)<+p``. The driver reads nothing from the receiver, so there is no
feedback; the receiver's write cannot change u.

Independent answer (hand derivation): u(t)=1 for all t. The timer fires at
exactly t=0.5 and reads u=1>0.5, so p becomes 1. Outputs are post-event
values, so y(t)=0 for t<0.5 and y(t)=1 for t>=0.5. The event is a timer, not
a cross, so ADR-003 (cross bodies read the right limit tau+) does not apply
and the answer is the same under the root-time and execution-time cross
conventions. Branch ``codex/evas-callback-execution`` (head ``1b90f410``)
returns exactly this answer.

Contract: a correct answer only. A refusal is today's honest behavior, but
this test describes the missing capability, so it is an expected failure for
#65. The control with the same voltage from a continuous assignment passes.
"""
GUARDS = ["EVENT-CONDITIONS", "TIMER", "COMPOSE", "DEV:independent-driver-condition"]

import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

TIMES = [0., .25, .5, .75, 1.]
STATE_DRIVER = "integer q; analog begin @(initial_step) q=1; V(u)<+q; end"
CONTINUOUS_DRIVER = "integer q; analog begin q=1; V(u)<+q; end"


def source(driver):
    return ('`include "disciplines.vams"\n'
            f'module driver(u); output u; electrical u; {driver} endmodule\n'
            'module receiver(u,y); input u; output y; electrical u,y; integer p; '
            'analog begin @(initial_step) p=0; @(timer(0.5)) if(V(u)>0.5) p=1; '
            'V(y)<+p; end endmodule')


class IndependentDriverCondition(unittest.TestCase):
    def assert_answer(self, driver):
        program = compile_sources({"model.va": source(driver)}, [
            Instance("D", "driver", {"u": "u"}), Instance("R", "receiver", {"u": "u", "y": "y"})])
        try:
            result = transient(program, {}, TIMES, stop=1., max_step=.125, kernel=KERNEL)
        except KernelError as refusal:
            self.fail(f"refused instead of the independent answer: {refusal.detail}")
        self.assertEqual([event["time"] for event in result["transient"]["events"]], [.5])
        u, y = (result["nodes"].index(node) for node in "uy")
        self.assertEqual([row["voltages"][u] for row in result["solutions"]], [1.] * len(TIMES))
        self.assertEqual([row["voltages"][y] for row in result["solutions"]],
                         [float(t >= .5) for t in TIMES])

    def test_continuous_driver_condition_is_accepted(self):
        self.assert_answer(CONTINUOUS_DRIVER)

    @unittest.expectedFailure  # Issue #65: state read through the voltage network is refused.
    def test_state_driver_condition_reads_independent_voltage(self):
        self.assert_answer(STATE_DRIVER)


if __name__ == "__main__":
    unittest.main()
