"""Typed held targets compose with a real history-root calendar.

The oracle is a two-stage binary-rational ramp, independent of EVAS events.
Neither a source-level role refusal nor sampling a nominal root is acceptance.
"""
import copy
import json
import os
from fractions import Fraction as Q
from pathlib import Path
import subprocess
import unittest

from evas import CompileError, Instance, compile_sources, transient

GUARDS = ['TRANSITION', 'EVENT-ORDER', 'LANG', 'COMPOSE']
KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))

SOURCE = '''`include "disciplines.vams"
module calendar(h,y,z,r);
    output h,y,z;
    inout r;
    electrical h,y,z,r;
    real q;
    integer n,m;
    analog begin
        @(initial_step) begin q=0; n=0; m=0; end
        @(timer(1,1)) q=1-q;
        @(cross(V(h,r)-0.5,+1) or cross(V(h,r)-0.5,-1)) begin
            n=n+1;
            m=m+2;
        end
        V(h,r)<+transition(q,0,0.25,0.25);
        V(y,r)<+transition((n&1)?1.0:0.0,0,0.125,0.125);
        V(z,r)<+transition(((m>>1)&1)?1.0:0.0,0,0.125,0.125);
    end
endmodule
'''


def program(source=SOURCE):
    return compile_sources({'calendar.va': source}, [
        Instance('dut', 'calendar', dict(h='h', y='y', z='z', r='0'))])


def ramp(time, start, duration, before, after):
    """The independent exact affine ramp including both endpoints."""
    t = Q(time)
    if t <= start:
        return before
    if t >= start + duration:
        return after
    return before + (after-before)*(t-start)/duration


def expected(time):
    t = Q(time)
    # The timer changes only h's held target at 1 and 2. Its .5 crossings
    # occur halfway through .25 ramps, exactly at 9/8 and 17/8.
    h = (ramp(t, Q(1), Q(1, 4), Q(0), Q(1)) if t < 2 else
         ramp(t, Q(2), Q(1, 4), Q(1), Q(0)))
    y = (ramp(t, Q(9, 8), Q(1, 8), Q(0), Q(1)) if t < Q(17, 8) else
         ramp(t, Q(17, 8), Q(1, 8), Q(1), Q(0)))
    return {'h': h, 'y': y, 'z': y}


TIMES = [0., .5, 1., 1.0625, 1.1875, 1.25, 1.5,
         2., 2.0625, 2.1875, 2.25, 2.5]


class GroupEventCalendar(unittest.TestCase):
    def run_calendar(self, times):
        return transient(program(), {}, times, stop=2.5, max_step=.125,
                         vabstol=1e-9, reltol=0, kernel=KERNEL)

    def assert_oracle(self, result, times):
        self.assertEqual(len(result['solutions']), len(times))
        for time, frame in zip(times, result['solutions']):
            for node, want in expected(time).items():
                actual = frame['voltages'][result['nodes'].index(node)]
                self.assertAlmostEqual(actual, float(want), delta=1e-9,
                                       msg=f'{node} at {time}')

    def test_two_typed_states_rebind_at_history_roots_with_exact_ramp_oracle(self):
        self.assert_oracle(self.run_calendar(TIMES), TIMES)

    def test_queries_do_not_retarget_or_advance_the_history_calendar(self):
        dense = sorted(set(TIMES + [i/64 for i in range(161)]))
        sparse_result = self.run_calendar(TIMES)
        dense_result = self.run_calendar(dense)
        self.assert_oracle(sparse_result, TIMES)
        self.assert_oracle(dense_result, dense)
        for time in TIMES:
            a = sparse_result['solutions'][TIMES.index(time)]['voltages']
            b = dense_result['solutions'][dense.index(time)]['voltages']
            self.assertEqual(a, b, f'query changed accepted history at {time}')

    def test_hidden_real_or_voltage_target_cannot_borrow_integer_calendar_role(self):
        for target in ['((n&1)?1.0:0.0)+0.0*q',
                       '((n&1)?1.0:0.0)+0.0*V(h,r)',
                       '(n&1)?1.0:(0.0*q)']:
            source = SOURCE.replace('(n&1)?1.0:0.0', target)
            with self.subTest(target=target), self.assertRaises(CompileError):
                program(source)

    def test_foreign_integer_origin_in_raw_protocol_remains_rejected(self):
        p = json.loads(json.dumps(program().to_dict()))

        def forge(value):
            if isinstance(value, dict):
                if value.get('op') == 'integer_primitive':
                    value['origin']['instance'] = 'foreign'
                    return True
                return any(forge(child) for child in value.values())
            if isinstance(value, list):
                return any(forge(child) for child in value)
            return False

        targets = copy.deepcopy(p['operators'])
        self.assertTrue(forge(targets), 'fixture must mutate a typed integer leaf')
        p['operators'] = targets
        request = dict(program=p, driven=[], samples=[], transient=dict(
            pwl=[], output_times=TIMES, stop=2.5, max_step=.125))
        result = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                                capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, '')
        response = json.loads(result.stderr)
        self.assertEqual(response['kind'], 'unsupported_held_integer_target')


HELD_SOURCE = (SOURCE.replace('module calendar(h,y,z,r);', 'module calendar(h,y,z,w,r);')
               .replace('output h,y,z;', 'output h,y,z,w;')
               .replace('electrical h,y,z,r;', 'electrical h,y,z,w,r;')
               .replace('integer n,m;', 'integer n,m,k;')
               .replace('n=0; m=0; end', 'n=0; m=0; k=0; end')
               .replace('m=m+2;', 'm=m+2;\n            k=1-k;')
               .replace('    end\nendmodule', '        V(w,r)<+transition(k?1.0:0.0,0,0.125,0.125);\n    end\nendmodule'))


def held_program(source=HELD_SOURCE):
    return compile_sources({'calendar.va': source}, [
        Instance('dut', 'calendar', dict(h='h', y='y', z='z', w='w', r='0'))])


class UntypedHeldTargetInTypedCalendar(unittest.TestCase):
    """An ordinary integer-truthiness held target shares the typed calendar."""

    def test_untyped_held_integer_select_follows_the_same_exact_ramp(self):
        self.assertIn('k?1.0:0.0', HELD_SOURCE)
        result = transient(held_program(), {}, TIMES, stop=2.5, max_step=.125,
                           vabstol=1e-9, reltol=0, kernel=KERNEL)
        for time, frame in zip(TIMES, result['solutions']):
            want = expected(time)
            for node, value in [*want.items(), ('w', want['y'])]:
                actual = frame['voltages'][result['nodes'].index(node)]
                self.assertAlmostEqual(actual, float(value), delta=1e-9,
                                       msg=f'{node} at {time}')

    def test_untyped_voltage_dependent_target_remains_rejected(self):
        source = HELD_SOURCE.replace('transition(k?1.0:0.0', 'transition(k?V(h,r):0.0')
        with self.assertRaises(CompileError):
            held_program(source)
        # A forged raw request must also be refused by the kernel calendar.
        p = json.loads(json.dumps(held_program().to_dict()))
        target = p['operators'][-1]['input']
        self.assertEqual(target['then_value']['constant'], 1.0)
        target['then_value'] = dict(op='affine', constant=0.0, terms=[
            dict(node=p['nodes'].index('h'), coefficient=1.0)])
        request = dict(program=p, driven=[], samples=[], transient=dict(
            pwl=[], output_times=TIMES, stop=2.5, max_step=.125))
        result = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                                capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stderr)['kind'], 'unsupported_held_integer_target')


if __name__ == '__main__':
    unittest.main()
