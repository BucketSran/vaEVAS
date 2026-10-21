"""Two initialization stages through the public compiler/kernel interface.

Answers are fixed from statement order and the transition endpoint contract.
They are not generated from an EVAS run or a simulator log. Changed-seed
initial observation admits held/direct inputs only in this finite contract.
"""
GUARDS = ['LANG', 'TIMER', 'EVENT-ORDER', 'EVENT-CONDITIONS',
          'TRANSITION', 'TIMED-OPERATOR', 'COMPOSE']

import copy
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


TIMES = [0, 0.125, 0.25, 0.5, 0.75, 1]
INITIAL = '''@(initial_step) begin
    $display("before=%d", n); n=3; $display("after=%d", n);
end'''


def source(active_body, meter_body, *, initial=0, delay=0.125):
    return f'''`include "disciplines.vams"
module active(u,y,r);
    input u; output y; inout r; electrical u,y,r; real a;
    analog begin
        @(initial_step) a={initial};
        {active_body}
        V(y,r)<+transition(a,{delay},0.5,0.5);
    end
endmodule
module meter(u,y,r);
    input u,y; inout r; electrical u,y,r; integer n;
    analog begin
        {meter_body}
    end
endmodule
'''


def compile_pair(text):
    return compile_sources({'initial_display_transition.va': text}, [
        Instance('active', 'active', connections=dict(u='u', y='y', r='0')),
        Instance('meter', 'meter', connections=dict(u='u', y='y', r='0')),
    ])


def execute(program, *, value=0, step=0.03125, times=TIMES):
    return transient(program, {'u': [[0, value], [1, value]]}, times,
                     stop=1, max_step=step, vabstol=2**-30, reltol=0,
                     kernel=KERNEL)


def displays(result):
    return [(r['time'], r['text'])
            for r in result['transient']['display_records']]


def events_for(result, owner):
    return [e for e in result['transient']['events']
            if e['origin'].endswith(f'({owner})')]


def semantic_trace(result):
    trace = result['transient']
    return {key: trace[key] for key in
            ['times', 'state_names', 'states', 'events', 'display_records']}


class InitialDisplayTransition(unittest.TestCase):
    def assert_waveform(self, result, expected):
        column = result['nodes'].index('y')
        self.assertEqual(len(result['solutions']), len(expected))
        for row, answer in zip(result['solutions'], expected):
            self.assertAlmostEqual(row['voltages'][column], answer, delta=2e-12)
            self.assertLessEqual(row['max_residual_ratio'], 1)

    def assert_initial_then_zero_timer(self, result, *, timer_kind='timer'):
        events = result['transient']['events']
        self.assertEqual(events[0]['kind'], 'initial_step')
        self.assertTrue(events[0]['origin'].endswith('(meter)'))
        self.assertEqual([(e['time'], e['kind']) for e in events_for(result, 'meter')],
                         [(0, 'initial_step'), (0, timer_kind)])

    def test_changed_seed_uses_initial_state_before_zero_timer_displays(self):
        # Final zero-time transition seed is 1, so delay creates no initial edge.
        # The meter's initial stage sees n=0, writes 3, then timer(0) sees 3.
        for ttol in ['0', '0.0009765625']:
            with self.subTest(ttol=ttol):
                program = compile_pair(source(
                    f'@(timer(0,0,{ttol})) a=1;',
                    INITIAL + f'\n@(timer(0,0,{ttol})) $display("timer=%d",n);'))
                result = execute(program)
                self.assert_waveform(result, [1] * len(TIMES))
                self.assertEqual(displays(result),
                                 [(0, 'before=0'), (0, 'after=3'), (0, 'timer=3')])
                self.assert_initial_then_zero_timer(result)
                self.assertEqual(len(result['transient']['events']), 3)
                active = events_for(result, 'active')
                self.assertEqual([(e['time'], e['kind']) for e in active], [(0, 'timer')])
                a = result['transient']['state_names'].index('active:a')
                n = result['transient']['state_names'].index('meter:n')
                self.assertEqual((active[0]['before'][a], active[0]['after'][a]), (0, 1))
                self.assertEqual((active[0]['before'][n], active[0]['after'][n]), (3, 3))

    def test_zero_timer_condition_reads_prior_initial_assignment(self):
        program = compile_pair(source('@(timer(0,0,0)) a=1;', INITIAL + '''
            @(timer(0,0,0)) if(n>2) $display("timer=%d",n);
            else $display("wrong=%d",n);'''))
        result = execute(program)
        self.assertEqual(displays(result),
                         [(0, 'before=0'), (0, 'after=3'), (0, 'timer=3')])
        self.assert_waveform(result, [1] * len(TIMES))

    def test_zero_or_bodies_run_once_and_positive_neighbors_remain(self):
        # Two zero leaves share each OR body. Each body increments only once.
        # At t=1/4 the target becomes 2. The half-second edge has midpoint 3/2
        # at t=1/2 and reaches 2 at t=3/4; final seed was already 1 at t=0.
        program = compile_pair(source('''
            @(timer(0,0,0) or timer(0,0,0)) a=a+1;
            @(timer(0.25,0,0)) a=a+1;''', INITIAL + '''
            @(timer(0,0,0) or timer(0,0,0)) begin
                n=n+1; $display("timer=%d",n);
            end
            @(timer(0.25,0,0)) begin n=n+1; $display("neighbor=%d",n); end''',
            delay=0))
        for step in [1, 0.03125]:
            with self.subTest(step=step):
                result = execute(program, step=step)
                self.assert_waveform(result, [1, 1, 1, 1.5, 2, 2])
                self.assertEqual(displays(result),
                                 [(0, 'before=0'), (0, 'after=3'),
                                  (0, 'timer=4'), (0.25, 'neighbor=5')])
                events = result['transient']['events']
                self.assertEqual(len(events), 5)
                self.assertEqual(events[0]['kind'], 'initial_step')
                for owner in ['active', 'meter']:
                    zero = [e for e in events_for(result, owner) if e['kind'] == 'or']
                    self.assertEqual(len(zero), 1)
                    self.assertEqual(zero[0]['time'], 0)
                    self.assertEqual(len(zero[0]['fired_triggers']), 2)
                    self.assertEqual(len({t['trigger'] for t in zero[0]['fired_triggers']}), 2)
                    self.assertEqual([(e['time'], e['kind']) for e in events_for(result, owner)
                                      if e['time'] > 0], [(0.25, 'timer')])

    def test_nonbare_point_certificate_retries_without_program_or_record_mutation(self):
        text = source('@(timer(0,0,0)) a=V(u,r)+0.125;',
                      INITIAL + '\n@(timer(0,0,0)) $display("timer=%d",n);')
        # Only bare State targets have the new bounded constructor.
        text = text.replace('transition(a,', 'transition(a+0.0,')
        program = compile_pair(text)
        original = copy.deepcopy(program.to_dict())
        # 1/8 + 2^-60 cannot be stored exactly in binary64 near 1/8.
        # The changed-seed final-point certificate must reject it, even though
        # a rounded scalar looks like 1/8. No output is accepted on this path.
        for _ in range(2):
            with self.assertRaises(KernelError) as caught:
                execute(program, value=2**-60)
            self.assertEqual(caught.exception.detail['kind'], 'unsupported_initial_history')
            self.assertEqual(program.to_dict(), original)
        retry = execute(program, value=0)
        clean = execute(compile_pair(text), value=0)
        self.assertEqual(program.to_dict(), original)
        self.assertEqual(semantic_trace(retry), semantic_trace(clean))
        self.assertEqual(displays(retry),
                         [(0, 'before=0'), (0, 'after=3'), (0, 'timer=3')])
        self.assertEqual(len(retry['transient']['events']), 3)
        self.assert_waveform(retry, [0.125] * len(TIMES))

    def test_changed_seed_internal_voltage_initial_display_is_explicitly_unsupported(self):
        program = compile_pair(source('@(timer(0,0,0)) a=1;', '''
            @(initial_step) begin $display("voltage=%.12g",V(y,r)); n=3; end
            @(timer(0,0,0)) $display("timer=%d",n);'''))
        original = copy.deepcopy(program.to_dict())
        for _ in range(2):
            with self.assertRaises(KernelError) as caught:
                execute(program)
            self.assertEqual(caught.exception.detail['kind'], 'unsupported_initial_history')
            self.assertEqual(program.to_dict(), original)

    def test_unchanged_seed_preserves_internal_voltage_initial_display(self):
        program = compile_pair(source('@(timer(0,0,0)) a=a;', '''
            @(initial_step) begin $display("voltage=%.12g",V(y,r)); n=3; end
            @(timer(0,0,0)) $display("timer=%d",n);''', initial=1))
        result = execute(program)
        self.assertEqual(displays(result), [(0, 'voltage=1'), (0, 'timer=3')])
        self.assert_initial_then_zero_timer(result)
        self.assertEqual(len(result['transient']['events']), 3)
        self.assert_waveform(result, [1] * len(TIMES))

    def test_initial_and_timer_display_replay_preserves_each_statement_position(self):
        program = compile_pair(source('''@(timer(0,0,0)) begin
            $display("active_before=%.12g",a); a=1;
            $display("active_after=%.12g",a); end''', INITIAL + '''
            @(timer(0,0,0)) begin $display("timer_before=%d",n);
                n=n+1; $display("timer_after=%d",n); end'''))
        result = execute(program)
        records = result['transient']['display_records']
        self.assertEqual([r['text'] for r in records[:2]], ['before=0', 'after=3'])
        self.assertEqual([r['text'] for r in records if r['origin'].endswith('(active)')],
                         ['active_before=0', 'active_after=1'])
        self.assertEqual([r['text'] for r in records if r['origin'].endswith('(meter)')],
                         ['before=0', 'after=3', 'timer_before=3', 'timer_after=4'])
        self.assertEqual([r['time'] for r in records], [0] * 6)
        self.assertEqual(len(result['transient']['events']), 3)
        self.assert_waveform(result, [1] * len(TIMES))

    def test_final_seed_and_display_answers_do_not_depend_on_output_grid(self):
        program = compile_pair(source('@(timer(0,0,0)) a=1;',
                                      INITIAL + '\n@(timer(0,0,0)) $display("timer=%d",n);'))
        coarse = execute(program, step=1, times=[0, 1])
        dense = execute(program, times=TIMES)
        self.assertEqual(displays(coarse), displays(dense))
        self.assertEqual(coarse['transient']['events'], dense['transient']['events'])
        self.assert_waveform(coarse, [1, 1])
        self.assert_waveform(dense, [1] * len(TIMES))


if __name__ == '__main__':
    unittest.main()
