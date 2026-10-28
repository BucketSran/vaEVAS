"""$bound_step only caps the next step (NF-12b, slot 12).

Card: requirement:bound-step-request-invariance v2 (standards line). LRM 2.4 and
2023 9.17.2: $bound_step(h) requests that the next step be no larger than h; it
does not change the solution. Adding the request to a program with an idt and an
input-driven procedural if must therefore neither change admission nor the
waveform. The refusal this card forbids is the old one: deciding every
procedural condition over the whole accepted box when only the request is
needed.

Independent answers (exact, by hand, card short bench): enable crosses 0.75 at
10.5 ns; before that target=0, then target=0.75+0.98*(V(vin)-0.75) is affine on
[10.5, 11] ns and 0.77646 after 11 ns, so vout=idt(target/20n) is 0 at 10 ns,
153969/8000000 at 11 ns, 279261/1600000 at 15 ns and 117969/320000 at 20 ns.
"""
GUARDS = ['DYNAMICS', 'LANG']

from fractions import Fraction as F
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

# The first 20 ns of the heldout-0 PWL of the card's t8/t14 repro decks.
VIN = [[0, .75], [10e-9, .75], [11e-9, .777], [20e-9, .777]]
ENABLE = [[0, 0], [10e-9, 0], [11e-9, 1.5], [20e-9, 1.5]]
TIMES = [10e-9, 11e-9, 15e-9, 20e-9]
EXACT = [F(0), F(153969, 8000000), F(279261, 1600000), F(117969, 320000)]
T8 = 'target=0.75+gain*(V(vin)-0.75);\n if(V(enable)<0.75) target=0;\n'
TAIL = ' V(q)<+idt(target/tau,0);\n V(vout)<+V(q);\n'


def ota(body):
    text = ('`include "disciplines.vams"\nmodule ota(vin,enable,vout);\n'
            'input vin,enable; output vout; electrical vin,enable,vout; electrical q;\n'
            'parameter real tau=20n, gain=0.98;\nreal target;\nanalog begin\n ' + body + 'end\nendmodule\n')
    return compile_sources({'dut.va': text}, [Instance('X', 'ota', dict(vin='vin', enable='enable', vout='vout'))])


def run(body, max_step):
    return transient(ota(body), {'vin': VIN, 'enable': ENABLE}, TIMES, stop=20e-9, max_step=max_step,
                     kernel=KERNEL)


class BoundStepRequest(unittest.TestCase):
    def check(self, result):
        y = result['nodes'].index('vout')
        controls = result['observation_evidence']['effective_controls']
        absolute, relative = F(controls['absolute_V']), F(controls['relative'])
        for row, exact in zip(result['solutions'], EXACT, strict=True):
            value = F(row['voltages'][y])
            self.assertLessEqual(abs(value - exact), absolute + relative * abs(value))

    def test_bound_step_does_not_change_admission_of_idt_with_input_if(self):
        # t8 and t14 differ by the one request line; both complete with the
        # same exact integral.
        self.check(run(T8 + TAIL, 250e-12))
        self.check(run(T8 + TAIL + ' $bound_step(0.25n);\n', 250e-12))

    def test_bound_step_value_and_activation_switch_with_predicate(self):
        body = ('target=0.75+gain*(V(vin)-0.75);\n'
                ' if(V(enable)<0.75) begin target=0; $bound_step(1n); end else $bound_step(0.25n);\n')
        self.check(run(body + TAIL, 250e-12))

    def test_bound_step_request_is_honoured_when_maxstep_is_larger(self):
        # 20 ns at a 0.25 ns cap needs at least ceil(20/0.25)=80 accepted steps.
        result = run(T8 + TAIL + ' $bound_step(0.25n);\n', 5e-9)
        self.check(result)
        self.assertGreaterEqual(result['transient']['accepted_steps'], 80)

    def test_ignored_request_is_detected(self):
        # Negative control: without the request the same bench takes far
        # fewer steps, so dropping the request would fail the test above.
        result = run(T8 + TAIL, 5e-9)
        self.check(result)
        self.assertLess(result['transient']['accepted_steps'], 80)

    def test_uncertifiable_request_value_still_refuses(self):
        # A request whose value cannot be certified keeps an explicit refusal.
        with self.assertRaises(KernelError) as caught:
            run(T8 + TAIL + ' $bound_step(1/(V(vin)-V(vin)));\n', 250e-12)
        self.assertNotEqual(caught.exception.detail['kind'], 'invalid_ir')


if __name__ == '__main__':
    unittest.main()
