"""Floor uses only the real range proved at its sequential event use site."""
GUARDS = ['LANG', 'CROSS', 'TIMER', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'COMPOSE', 'TIMED-OPERATOR']

import math
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


CLAMP = 'c=V(u,r);if(c<0)c=0;if(c>vref)c=vref;'


def program(body=CLAMP+'q=floor(8*c/vref);', *, declarations='', parameters=None):
    text = model('@(initial_step)begin q=0;c=0;end @(cross(V(clk,r)-0.5,+1))begin '
                 + body + 'end V(y,r)<+transition(q,0,0.01,0.01);',
                 'electrical clk;parameter real vref=1;real c;integer q;' + declarations)
    return compile_sources({'event-floor.va': text}, [instance(parameters=parameters)])


def execute(p, value, **options):
    return transient(p, {'u': [[0, value], [1, value]],
                         'dut:clk': [[0, 0], [.2, 0], [.3, 1], [1, 1]]},
                     [0, .4, .5], stop=.5, max_step=.05, kernel=KERNEL, **options)


class EventFloorRanges(unittest.TestCase):
    def test_source_clamp_before_floor_reaches_real_transition_consumer(self):
        p = program()
        values = [-10, 0, math.nextafter(.125, -math.inf), .125,
                  math.nextafter(.125, math.inf), .3, .5, .999, 1, 10]
        expected = [0, 0, 0, 1, 1, 2, 4, 7, 8, 8]
        for value, want in zip(values, expected):
            with self.subTest(value=value):
                r = execute(p, value)
                self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], want)

    def test_initial_values_late_or_incomplete_writes_are_not_runtime_ranges(self):
        for body in ['q=floor(8*c);'+CLAMP,
                     'if(V(u,r)>0)begin '+CLAMP+'end q=floor(8*c);',
                     'c=V(u,r);if(c<0)c=0;q=floor(8*c);',
                     CLAMP+'c=V(u,r);q=floor(8*c);']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                program(body)

    def test_parameter_overrides_and_instances_keep_separate_facts(self):
        p = program(parameters={'vref': 2})
        r = execute(p, 1.5)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], 6)
        text = model('@(initial_step)begin q=0;c=0;end @(timer(0.25))begin '
                     + CLAMP + 'q=floor(8*c/vref);end V(y,r)<+q;',
                     'parameter real vref=1;real c;integer q;')
        for order in ((1, 2), (2, 1)):
            instances = [instance('d'+str(ref), connections=dict(u='u', y='y'+str(ref), r='0'),
                                  parameters={'vref': ref}) for ref in order]
            p = compile_sources({'instances.va': text}, instances)
            r = transient(p, {'u': [[0, 1.5], [1, 1.5]]}, [0, .4],
                          stop=.5, max_step=.05, kernel=KERNEL)
            row = dict(zip(r['nodes'], r['solutions'][-1]['voltages']))
            self.assertEqual((row['y1'], row['y2']), (8, 6))

    def test_branch_local_facts_follow_only_the_current_selected_path(self):
        p = program('if(V(u,r)>0)begin '+CLAMP+'q=floor(8*c);end else q=0;')
        for value, want in ((.3, 2), (-1, 0)):
            r = execute(p, value)
            self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], want)
        with self.assertRaises(CompileError):
            program('if(V(u,r)>0)begin '+CLAMP+'end else c=V(u,r);q=floor(8*c);')

    def test_nonbinary_and_nonpositive_reference_override_stays_outside_slice(self):
        for vref in (.9, 0, -1):
            with self.subTest(vref=vref), self.assertRaises(CompileError):
                program(parameters={'vref': vref})

    def test_floor_result_has_real_source_type_and_dead_arm_checks_survive(self):
        for body in [CLAMP+'q=floor(8*c)&1;',
                     CLAMP+'if(0>1)q=floor(8*c)+(2147483647+1);',
                     CLAMP+'if(0>1)q=floor(1/0);',
                     'if(0>1)q=floor(V(u,r));']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                program(body)

    def test_point_boxes_keep_bins_and_straddling_boxes_still_reject(self):
        text = model('@(initial_step)begin q=0;c=0;end @(timer(0.25))begin '
                     + CLAMP + 'q=floor(8*c);end V(y,r)<+q;',
                     'parameter real vref=1;real c;integer q;')
        p = compile_sources({'box.va': text}, [instance()])
        def run(value):
            return transient(p, {'u': [[0, value], [1, value]]}, [0, .4],
                stop=.5, max_step=.05, kernel=KERNEL, source_errors={'u': .01},
                vabstol=.02, reltol=0)
        r = run(.3)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], 2)
        with self.assertRaises(KernelError):
            run(.5)

    def test_real_facts_do_not_narrow_inherited_error_before_future_gain(self):
        for gain in (1, 10**12):
            text = model('@(initial_step)begin q=0;c=0;p=0;end '
                '@(timer(0.125))begin c=0.45*V(u,r);if(c<0)c=0;if(c>1)c=1;'
                'q=floor(8*c);end @(timer(0.25))p=c;'
                'V(y,r)<+transition(q,0,0.01,0.01)+'+str(gain)+'*p;',
                'real c,p;integer q;')
            p = compile_sources({'future.va': text}, [instance()])
            options = dict(stop=.5, max_step=.05, kernel=KERNEL, vabstol=1e-8, reltol=0)
            if gain == 1:
                r = transient(p, {'u': [[0, .16], [1, .16]]}, [0, .4], **options)
                self.assertAlmostEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], .072, places=12)
            else:
                with self.assertRaises(KernelError) as error:
                    transient(p, {'u': [[0, .16], [1, .16]]}, [0, .4], **options)
                self.assertEqual(error.exception.detail['kind'], 'waveform_accuracy')

    def test_source_ranges_include_constant_folding_rounding(self):
        p = program('c=0.1+0.2;q=floor(c-0.30000000000000004);')
        r = execute(p, 0)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], 0)

    def test_range_transfer_uses_typed_integer_division(self):
        for body, want in (('c=9/2;q=floor(c-0.5);', 3),
                           ('c=-9/2;q=floor(c+0.5);', -4),
                           ('c=9.0/2;q=floor(c-0.5);', 4)):
            p = program(body)
            r = execute(p, 0)
            self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')], want)

    def test_initial_other_event_and_final_step_do_not_supply_current_facts(self):
        for suffix in ['@(timer(0.35))q=floor(8*c);', '@(final_step)q=floor(8*c);']:
            text = model('@(initial_step)begin q=0;c=0.5;end '
                '@(timer(0.125))begin '+CLAMP+'end '+suffix+'V(y,r)<+q;',
                'real c;integer q;parameter real vref=1;')
            with self.subTest(suffix=suffix), self.assertRaises(CompileError):
                compile_sources({'phase.va': text}, [instance()])

    def test_partition_signed_overflow_and_original_nonfinite_checks_remain(self):
        program('c=V(u,r);if(c<0)c=0;if(c>255)c=255;q=floor(c);')
        with self.assertRaises(CompileError) as error:
            program('c=V(u,r);if(c<0)c=0;if(c>256)c=256;q=floor(c);')
        self.assertEqual(error.exception.diagnostic['code'], 'resource_budget')
        p = program('q=floor(2147483648.0);if(q>7)q=7;')
        with self.assertRaisesRegex(KernelError, 'signed 32-bit'):
            execute(p, 0)
        p = program('c='+str(float.fromhex('0x1p1023'))+'*V(u,r);'
            'if(c<0)c=0;if(c>1)c=1;q=floor(8*c);')
        with self.assertRaises(KernelError):
            execute(p, 2)

    def test_output_voltage_feedback_does_not_become_an_input_certificate(self):
        text = model('@(initial_step)begin q=0;c=0;end @(timer(0.25))begin '
            'c=V(y,r);if(c<0)c=0;if(c>1)c=1;q=floor(8*c);end V(y,r)<+q;',
            'real c;integer q;')
        p = compile_sources({'feedback.va': text}, [instance()])
        with self.assertRaises(KernelError):
            transient(p, {'u': [[0, 0], [1, 0]]}, [0, .4], stop=.5, max_step=.05, kernel=KERNEL)


if __name__ == '__main__':
    unittest.main()
