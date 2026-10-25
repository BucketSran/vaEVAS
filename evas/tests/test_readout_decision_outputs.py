"""Unread grounded outputs whose decisions are nonlinear in inputs and held values.

Each row is evaluated from the certified core node boxes. Independent answers
are hand-derived piecewise formulas; nearby programs keep explicit refusals.
"""
GUARDS = ['EVENT-CONDITIONS', 'COMPOSE', 'TRANSITION']
import os
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient

ROOT = Path(__file__).resolve().parents[2]
KERNEL = Path(os.environ.get('EVAS_KERNEL', os.environ.get('EVAS_TEST_KERNEL',
    str(ROOT / 'evas/rust_core/target/debug/evas-kernel'))))

CLK = [[0, 0], [.4, 0], [.6, 1], [1, 1]]   # rising edge crosses 0.5 at t=0.5
RAMP = [[0, 0], [1, .8]]                    # V(u) = 0.8 t


def module(body, extra=''):
    return '''`include "disciplines.vams"
module m(clk,u,y,z);input clk,u;output y,z;electrical clk,u,y,z;
real g; real s; real x; real w;
analog begin
@(initial_step) begin g=1; s=-1; end
@(cross(V(clk)-0.5,+1)) begin g=2; s=1; ''' + extra + ''' end
''' + body + '''
V(z) <+ transition(s,0,1e-3,1e-3);
end endmodule'''


def run(body, times, extra='', u=RAMP):
    program = compile_sources({'readout.va': module(body, extra)}, [Instance(
        'M', 'm', dict(clk='clk', u='u', y='y', z='z'))])
    return transient(program, dict(clk=CLK, u=u), times, stop=1, max_step=.125,
                     vabstol=1e-10, reltol=0, kernel=KERNEL)


CLAMP = '''x = g*V(u);
if (x > 1) x = 1;
if (x < 0) x = 0;
V(y) <+ x;'''


class ReadoutDecisionOutputs(unittest.TestCase):
    def check(self, result, times, expected):
        y = result['nodes'].index('y')
        self.assertEqual(result['nodes'], ['0', 'clk', 'u', 'y', 'z'])
        boxes = result['observation_evidence']['voltage_bounds_V']
        for time, row, box in zip(times, result['solutions'], boxes):
            want = expected(time)
            self.assertLessEqual(abs(row['voltages'][y] - want), 1e-12, time)
            self.assertLessEqual(box[y][0], want + 1e-15, time)
            self.assertLessEqual(want - 1e-15, box[y][1], time)

    def test_held_gain_times_input_is_clamped_on_both_sides_of_the_event(self):
        times = [0, .25, .45, .6, .7, 1]
        expected = lambda t: min(1., (1 if t < .5 else 2) * .8 * t)
        self.check(run(CLAMP, times), times, expected)

    def test_operator_sample_times_input_with_lower_and_upper_clamps(self):
        # z settles to s within 1 ms; sample away from the edge.
        body = '''w = 0.5 + 2*(V(u) - 0.3)*transition(s,0,1e-3,1e-3);
if (w < 0) w = 0;
else if (w > 0.9) w = 0.9;
V(y) <+ w;'''
        times = [0, .1, .45, .52, .6, .9]
        def expected(t):
            sign = -1 if t < .5 else 1
            return min(.9, max(0., .5 + 2*(.8*t - .3)*sign))
        self.check(run(body, times), times, expected)

    def test_output_read_by_an_event_keeps_the_original_refusal(self):
        with self.assertRaisesRegex(CompileError, 'ordinary analog if predicates must be affine'):
            run(CLAMP, [0, 1], extra='g = V(y) + 1;')

    def test_clamped_value_feeding_a_transition_keeps_the_original_refusal(self):
        body = CLAMP.replace('V(y) <+ x;', 'V(y) <+ transition(x,0,1e-3,1e-3);')
        with self.assertRaisesRegex(CompileError, 'ordinary analog if predicates must be affine'):
            run(body, [0, 1])

    def test_division_by_a_box_containing_zero_is_refused(self):
        # At t=0.5 the selected arm divides by V(u)-0.4 = 0 exactly.
        body = '''x = g*V(u);
if (x > 5) x = 1;
else x = 0.01/(V(u) - 0.4);
V(y) <+ x;'''
        with self.assertRaisesRegex(KernelError, 'program-real arithmetic: DivisionByZero'):
            run(body, [0, .5, 1])

    def test_driven_or_shared_output_is_not_a_readout(self):
        # y is also forced by a second contribution: the output is shared.
        body = CLAMP + '\nV(y) <+ 0.1*V(u);'
        with self.assertRaises((CompileError, KernelError)):
            run(body, [0, 1])

    def test_held_only_or_live_only_decisions_beside_held_state_keep_refusals(self):
        # Neither shape couples a held gain with a live voltage, and the
        # instance holds state, so the original diagnostics stand.
        for body in ('x = g*g; if (x > 1) x = 1; V(y) <+ x;',
                     'x = V(u)*V(u); if (x > 0.25) x = 0.25; V(y) <+ x + g;'):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, 'must be affine'):
                run(body, [0, 1])


STATELESS = '''`include "disciplines.vams"
module square_limit(a,b,y);input a,b;output y;electrical a,b,y;
real x;
analog begin
x = V(a)*V(b);
if (x > 0.25) x = 0.25;
V(y) <+ x;
end endmodule
module toggler(clk,z);input clk;output z;electrical clk,z;
real s;
analog begin
@(initial_step) s=0;
@(cross(V(clk)-0.5,+1)) s=1-s;
V(z) <+ transition(s,0,1e-3,1e-3);
end endmodule'''


class StatelessAlgebraicReadout(unittest.TestCase):
    def run_pair(self, source, times):
        program = compile_sources({'pair.va': source}, [
            Instance('A', 'square_limit', dict(a='a', b='b', y='y')),
            Instance('T', 'toggler', dict(clk='clk', z='z'))])
        return transient(program, dict(a=RAMP, b=[[0, 1], [1, 1]], clk=CLK), times,
                         stop=1, max_step=.125, vabstol=1e-10, reltol=0, kernel=KERNEL)

    def test_stateless_instance_beside_held_state_reads_rows(self):
        # y = min(0.25, 0.8*t); the clamp switches at t = 0.3125.
        times = [0, .25, .3, .5, 1]
        result = self.run_pair(STATELESS, times)
        y = result['nodes'].index('y')
        boxes = result['observation_evidence']['voltage_bounds_V']
        for time, row, box in zip(times, result['solutions'], boxes):
            want = min(.25, .8*time)
            self.assertLessEqual(abs(row['voltages'][y] - want), 1e-12, time)
            self.assertLessEqual(box[y][0], want + 1e-15, time)
            self.assertLessEqual(want - 1e-15, box[y][1], time)

    def test_stateless_instance_must_not_own_state(self):
        source = STATELESS.replace('real x;\nanalog begin\nx', 'real x, w;\nanalog begin\n@(initial_step) w=0;\nx', 1)
        with self.assertRaisesRegex(CompileError, 'predicates must be affine'):
            self.run_pair(source, [0, 1])


if __name__ == '__main__':
    unittest.main()
