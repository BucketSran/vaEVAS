"""Procedure-bound reals in idt assert paths and cross thresholds (H1, #270 R3-N2).

Card: requirement:idt-reset-argument-procedure-frame v6 (standards line). IR33
binds program reals such as a clamped `freq` or a threshold `th` in the analog
procedure; kernel consumers outside that procedure frame returned
kernel.invalid_ir ("unbound real value requires its procedure frame").

Independent answers (exact, by hand): with c=1 V, freq=1e6+1e5*V(c)=1.1e6 Hz
and no clamp applies, so idt(freq,0) is 11/10 V per microsecond. LRM 4.5.4
Table 4-18: idt(x,ic,0) equals idt(x,ic) (the assert is never nonzero); with a
state assert the output holds ic while it is nonzero and integrates from the
release time, here 3 us. The certified budget is the effective
vabstol+reltol*|v| echoed in observation_evidence.
"""
GUARDS = ['DYNAMICS', 'LANG', 'CROSS']

from fractions import Fraction as F
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

HEAD = ('`include "disciplines.vams"\nmodule m(c,y); input c; output y; electrical c,y;\n'
        'real freq,acc; integer a;\nanalog begin\n')
CLAMP = 'freq=1e6+1e5*V(c); if(freq<1e6) freq=1e6; if(freq>70e6) freq=70e6; '
ZERO = CLAMP + 'acc=idt(freq,0,0); V(y)<+acc;'
PLAIN = CLAMP + 'acc=idt(freq,0); V(y)<+acc;'
STATE = '@(initial_step) a=1; @(timer(3u)) a=0; ' + CLAMP + 'acc=idt(freq,0,a); V(y)<+acc;'
TIMES = [0, 1e-6, 2e-6, 3e-6, 4e-6, 5e-6]


def program(body):
    return compile_sources({'h1.va': HEAD + body + '\nend\nendmodule\n'},
                           [Instance('dut', 'm', dict(c='c', y='y'))])


def review_bench(body):
    # The card's bench: c=1 V on [0, 5 us], outputs every microsecond.
    return transient(program(body), {'c': [[0, 1], [5e-6, 1]]}, TIMES, stop=5e-6, max_step=1e-6,
                     kernel=KERNEL)


class MustRun(unittest.TestCase):
    def check(self, result, expected):
        y = result['nodes'].index('y')
        controls = result['observation_evidence']['effective_controls']
        absolute, relative = F(controls['absolute_V']), F(controls['relative'])
        boxes = result['observation_evidence']['voltage_bounds_V']
        self.assertEqual(len(result['solutions']), len(expected))
        for row, box, exact in zip(result['solutions'], boxes, expected):
            value = F(row['voltages'][y])
            budget = absolute + relative * abs(value)
            self.assertLessEqual(abs(value - exact), budget)
            low, high = F(box[y][0]), F(box[y][1])
            self.assertLessEqual(low, exact)
            self.assertLessEqual(exact, high)
            self.assertLessEqual((high - low) / 2, budget)

    def test_constant_zero_assert_runs_and_equals_plain_idt(self):
        zero = review_bench(ZERO)
        self.check(zero, [F(11, 10) * k for k in range(6)])
        plain = review_bench(PLAIN)
        self.assertEqual(zero['solutions'], plain['solutions'])
        self.assertEqual(zero['observation_evidence']['voltage_bounds_V'],
                         plain['observation_evidence']['voltage_bounds_V'])

    def test_state_assert_with_procedural_integrand(self):
        # a=1 holds ic=0 until the timer releases it at 3 us.
        self.check(review_bench(STATE), [0, 0, 0, 0, F(11, 10), F(11, 5)])


class ZeroAssertEquivalence(unittest.TestCase):
    """Adding idt's constant-zero assert never changes the outcome (card property)."""

    def outcome(self, body, sources, times, stop, max_step):
        try:
            result = transient(program(body), sources, times, stop=stop, max_step=max_step,
                               kernel=KERNEL, timeout=900)
        except KernelError as error:
            self.assertNotEqual(error.detail['kind'], 'invalid_ir', str(error))
            return ('refused', error.detail['kind'], error.detail['message'])
        return ('completed', result['solutions'], result['observation_evidence']['voltage_bounds_V'])

    def test_step_budget_pair_has_one_outcome(self):
        # The second pair of the card: c covers stop=1 s and max_step=1e-7 asks
        # for 10,000,000 steps, above the 1,000,000-step limit. Both members
        # complete identically or stop with the same kind for the same cause.
        args = ({'c': [[0, 1], [1, 1]]}, [0, 1], 1, 1e-7)
        self.assertEqual(self.outcome(ZERO, *args), self.outcome(PLAIN, *args))


class ProceduralThresholds(unittest.TestCase):
    def test_procedural_real_threshold_in_cross(self):
        # th=0.5*vh=0.05 V; u rises 0 -> 1 V over 1 ns and crosses th at 50 ps.
        text = ('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y;\n'
                'parameter real vh=0.1; real th; integer n;\nanalog begin\n'
                'th=0.5*vh; @(cross(V(u)-th,+1)) n=n+1; V(y)<+n;\nend\nendmodule\n')
        p = compile_sources({'threshold.va': text}, [Instance('dut', 'm', dict(u='u', y='y'))])
        result = transient(p, {'u': [[0, 0], [1e-9, 1]]}, [0, 25e-12, 75e-12, 1e-9], stop=1e-9,
                           max_step=1e-10, kernel=KERNEL)
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [0, 0, 1, 1])

    def test_hysteresis_comparator_thresholds(self):
        # upper=0.1, lower=-0.1; V(inp) rises through 0.1 at 0.6 us and falls
        # through -0.1 at 1.6 us.
        text = ('`include "disciplines.vams"\nmodule cmp(inp,inm,y); input inp,inm; output y; '
                'electrical inp,inm,y;\nparameter real offset=0; parameter real vhys=0.2;\n'
                'real upper_th, lower_th; integer state;\nanalog begin\n'
                'upper_th = offset + 0.5 * vhys; lower_th = offset - 0.5 * vhys;\n'
                '@(cross(V(inp, inm) - upper_th, +1)) state = 1;\n'
                '@(cross(V(inp, inm) - lower_th, -1)) state = 0;\n'
                'V(y) <+ state;\nend\nendmodule\n')
        p = compile_sources({'hysteresis.va': text},
                            [Instance('dut', 'cmp', dict(inp='inp', inm='0', y='y'))])
        times = [0, .5e-6, .7e-6, 1.5e-6, 1.7e-6, 2e-6]
        result = transient(p, {'inp': [[0, -.5], [1e-6, .5], [2e-6, -.5]]}, times, stop=2e-6,
                           max_step=.1e-6, kernel=KERNEL)
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [0, 0, 1, 1, 0, 0])


# Probe forms modelled on the constructs the card quotes (R11-1, R12-1, R26-1,
# the second-batch hysteresis comparator and E-H h19); they are not the
# Benchmark files. Each must run or stop with a typed refusal.
NEVER_INVALID = {
    'r11-constant-assert': ('m(coarse,fine,out)', 'input coarse,fine; output out; electrical coarse,fine,out;',
                            'real freq,phase;',
                            'freq=20e6+1e6*V(coarse)+250e3*V(fine); if(freq<1e6) freq=1e6; '
                            'if(freq>70e6) freq=70e6; phase=idt(freq,0,0); V(out)<+phase;'),
    'r11-state-assert': ('m(coarse,fine,out)', 'input coarse,fine; output out; electrical coarse,fine,out;',
                         'real freq,phase; integer rst;',
                         '@(initial_step) rst=1; @(timer(1u)) rst=0; '
                         'freq=20e6+1e6*V(coarse)+250e3*V(fine); if(freq<1e6) freq=1e6; '
                         'if(freq>70e6) freq=70e6; phase=idt(freq,0,rst); V(out)<+phase;'),
    'r12-assert': ('m(coarse,fine,out)', 'input coarse,fine; output out; electrical coarse,fine,out;',
                   'real freq,phase; integer rst;',
                   '@(initial_step) rst=0; @(timer(1u)) rst=1; @(timer(2u)) rst=0; '
                   'freq=10e6+1e6*V(coarse); phase=idt(freq,0,rst); V(out)<+phase;'),
    # R26-1 writes the assert as !active; this front end refuses a stateful
    # decision there, so the probe holds the complement in its own state.
    'r26-active-assert': ('m(coarse,fine,out)', 'input coarse,fine; output out; electrical coarse,fine,out;',
                          'real theta; integer active, hold;',
                          '@(initial_step) begin active=1; hold=0; end '
                          '@(timer(2u)) begin active=0; hold=1; end theta=0.5; '
                          'V(out) <+ idt(V(coarse)*sin(theta)*active,0,hold);'),
    'hysteresis': ('m(coarse,fine,out)', 'input coarse,fine; output out; electrical coarse,fine,out;',
                   'parameter real offset=0; parameter real vhys=0.2; real upper_th,lower_th; integer state;',
                   'upper_th = offset + 0.5 * vhys; lower_th = offset - 0.5 * vhys; '
                   '@(cross(V(coarse, fine) - upper_th, +1)) state = 1; '
                   '@(cross(V(coarse, fine) - lower_th, -1)) state = 0; V(out) <+ state;'),
    'h19-held-integral': ('m(coarse,fine,out)', 'input coarse,fine; output out; electrical coarse,fine,out;',
                          'real ph;', 'ph=idt(V(coarse),0); V(out)<+tanh(ph);'),
}


class NeverInvalidIr(unittest.TestCase):
    def test_compiled_programs_never_return_invalid_ir(self):
        for name, (header, ports, declarations, body) in NEVER_INVALID.items():
            text = (f'`include "disciplines.vams"\nmodule {header}; {ports}\n{declarations}\n'
                    f'analog begin\n{body}\nend\nendmodule\n')
            program = compile_sources({name + '.va': text},
                                      [Instance('dut', 'm', dict(coarse='coarse', fine='fine', out='out'))])
            with self.subTest(name=name):
                try:
                    transient(program, {'coarse': [[0, 1], [3e-6, -1]], 'fine': [[0, 0], [3e-6, 0]]},
                              [0, 1.5e-6, 3e-6], stop=3e-6, max_step=.1e-6, kernel=KERNEL)
                except KernelError as error:
                    self.assertNotEqual(error.detail['kind'], 'invalid_ir', str(error))


if __name__ == '__main__':
    unittest.main()
