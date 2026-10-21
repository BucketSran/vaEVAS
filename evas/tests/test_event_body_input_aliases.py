"""Input-selected ordinary values are sampled at the event, never at startup."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER']

import os
from pathlib import Path
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get('EVAS_EVENT_BODY_ALIAS_KERNEL', DEFAULT_KERNEL))
CLIP = '''analog function real clip; input x; real x; begin
if(x<0) clip=0; else if(x>0.5) clip=0.5; else clip=x; end endfunction'''


class EventBodyInputAliases(unittest.TestCase):
    def compile(self, body, declarations='real a,q;'):
        return compile_sources({'body-alias.va': model(body, declarations)}, [instance()])

    def run_samples(self, program, times=(0,.5,1), **options):
        return transient(program, {'u': [[0,0],[1,1]]}, list(times), stop=1,
                         max_step=1, kernel=KERNEL, **options)

    def values(self, response, node='y'):
        index = response['nodes'].index(node)
        return [row['voltages'][index] for row in response['solutions']]

    def test_clipped_alias_samples_current_input_at_both_callbacks(self):
        # At t=1/4 and3/4, min(t,1/2) is1/4 and1/2. Repeated reads
        # must evaluate the current source while observations leave history alone.
        p = self.compile('a=clip(V(u,r)); @(initial_step)q=0; '
                         '@(timer(0.25))q=a+a; @(timer(0.75))q=a+a; V(y,r)<+q;',
                         'real a,q; '+CLIP)
        for times in [(0,.5,1), (0,.125,.5,.625,1)]:
            r = self.run_samples(p, times)
            self.assertEqual(self.values(r), [0 if t<.25 else .5 if t<.75 else 1 for t in times])

    def test_finite_integer_input_alias_remains_typed_through_real_clip(self):
        # A source predicate generates integer0/2. It changes after startup,
        # and the clip consumes both this alias and the current analog source.
        p = self.compile('k=(V(u,r)>0.5)?2:0; a=clip(V(u,r)+0.125*k); '
                         '@(initial_step)q=0; @(timer(0.25))q=a; '
                         '@(timer(0.75))q=a; V(y,r)<+q;', 'integer k; real a,q; '+CLIP)
        self.assertEqual(self.values(self.run_samples(p)), [0,.25,.5])

    def test_body_condition_and_instances_share_no_alias_binding(self):
        text = model('a=clip(gain*V(u,r)); @(initial_step)q=0; '
                     '@(timer(0.25))if(a>0.1875)q=a;else q=-1; V(y,r)<+q;',
                     'parameter real gain=1; real a,q; '+CLIP)
        p = compile_sources({'instances.va':text}, [
            instance('one', connections=dict(u='u',y='ya',r='0')),
            instance('two', connections=dict(u='u',y='yb',r='0'), parameters=dict(gain=.5))])
        r = self.run_samples(p)
        self.assertEqual(self.values(r,'ya'), [0,.25,.25])
        self.assertEqual(self.values(r,'yb'), [0,-1,-1])

    def test_cross_callback_samples_selected_alias_at_physical_root(self):
        p = self.compile('a=(V(u,r)>0.25)?V(u,r):0; @(initial_step)q=0; '
                         '@(cross(V(u,r)-0.5,+1))q=a; V(y,r)<+q;')
        self.assertEqual(self.values(self.run_samples(p, (0,.25,.75,1))), [0,0,.5,.5])

    def test_selected_alias_keeps_source_error_in_future_voltage(self):
        p = self.compile('a=(V(u,r)>0)?V(u,r):0; @(initial_step)q=0; '
                         '@(timer(0.25))q=a; V(y,r)<+1000000*q;')
        with self.assertRaises(KernelError):
            self.run_samples(p, source_errors={'u':.01})

    def test_selected_body_alias_is_still_not_a_cross_guard_or_timer_setting(self):
        for event in ['@(cross(a-0.25,+1))q=1;', '@(timer(a))q=1;']:
            with self.subTest(event=event), self.assertRaises(CompileError):
                self.compile('a=(V(u,r)>0.5)?1:0; @(initial_step)q=0; '+event+' V(y,r)<+q;')

    def test_later_reassignment_preserves_the_earlier_callback_prefix(self):
        # The callback occurs between the two source assignments, so it reads
        # the selected first value1 at t=.5. The later ordinary value.5 cannot
        # replace it. Initial sampling keeps its separate single-writer gate.
        p = self.compile('@(initial_step)q=0; a=(V(u,r)>0)?1:0; '
                         '@(timer(0.5))q=a; a=V(u,r); V(y,r)<+q;')
        self.assertEqual(self.values(self.run_samples(p)), [0,1,1])

    def test_non_dominating_and_cross_callback_definitions_reject(self):
        # A conditional ordinary write before the callback is held state; see
        # test_conditional_prefix_is_held_state below.
        cases = [('','a=(V(u,r)>0)?1:0;'),
                 ('a=V(u,r); @(timer(0.125))a=V(u,r);',''),
                 ('a=b;b=a;','')]
        for before,after in cases:
            with self.subTest(before=before,after=after), self.assertRaises(CompileError):
                self.compile('@(initial_step)q=0; '+before+' @(timer(0.5))q=a; '+after+' V(y,r)<+q;',
                             'real a,b,q;')

    def test_conditional_prefix_is_held_state(self):
        # u=t leaves zero at t=0 without a crossing; the held a reads 1 at 0.5.
        p = self.compile('@(initial_step)q=0; if(V(u,r)>0)a=1; @(timer(0.5))q=a; V(y,r)<+q;',
                         'real a,b,q;')
        rows = self.run_samples(p, (0, .25, .75, 1))
        node = rows['nodes'].index('y')
        self.assertEqual([row['voltages'][node] for row in rows['solutions']], [0, 0, 1, 1])

    def test_original_array_and_zero_trip_writers_do_not_qualify_as_scalar_aliases(self):
        # Independent review EV377-ORIGINAL-SHAPE-1: scalarization must not
        # erase an original array identity or an unexecuted second writer.
        cases = [
            ('fixed_array_slot',
             'a[0]=(V(u,r)>0.25)?V(u,r):0; @(initial_step)q=0; '
             '@(timer(0.5))q=a[0]; V(y,r)<+q;', 'real a[0:1],q;'),
            ('transitive_array_slot',
             'a[0]=(V(u,r)>0.25)?V(u,r):0; b=a[0]; @(initial_step)q=0; '
             '@(timer(0.5))q=b; V(y,r)<+q;', 'real a[0:1],b,q;'),
            ('zero_trip_second_writer',
             'a=(V(u,r)>0.25)?V(u,r):0; for(i=0;i<0;i=i+1)a=0; '
             '@(initial_step)q=0; @(timer(0.5))q=a; V(y,r)<+q;', 'integer i; real a,q;'),
            ('zero_trip_event_writer',
             'a=(V(u,r)>0.25)?V(u,r):0; @(initial_step)q=0; '
             '@(timer(0.125))for(i=0;i<0;i=i+1)a=0; '
             '@(timer(0.5))q=a; V(y,r)<+q;', 'integer i; real a,q;'),
        ]
        for name,body,declarations in cases:
            with self.subTest(case=name):
                with self.assertRaises(CompileError) as failure:
                    self.compile(body, declarations)
                self.assertEqual(failure.exception.diagnostic['code'], 'unsupported_local_event')

    def test_legacy_affine_aliases_keep_zero_trip_loop_compatibility(self):
        # These already legal affine routes use the old map. Narrowing the
        # optional selected-body map must not impose a new source-writer gate.
        for writer in ['for(i=0;i<0;i=i+1)a=0;',
                       '@(timer(0.125))for(i=0;i<0;i=i+1)a=0;']:
            with self.subTest(writer=writer):
                p = self.compile('a=V(u,r); '+writer+' @(initial_step)q=0; '
                                 '@(timer(0.5))q=a; V(y,r)<+q;', 'integer i; real a,q;')
                self.assertEqual(self.values(self.run_samples(p, (0,.25,.75,1))), [0,0,.5,.5])

    def test_state_time_history_output_and_hidden_internal_dependencies_reject(self):
        for expression in ['q', '$abstime', 'idt(V(u,r),0)', 'V(y,r)', '0*V(y,r)',
                           '(1>0)?V(u,r):0*V(y,r)', 'V(u,r)*V(u,r)']:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                self.compile('a='+expression+'; @(initial_step)q=0; @(timer(0.5))q=a; V(y,r)<+q;')

    def test_real_to_integer_and_original_dead_arm_overflow_remain_rejected(self):
        for rhs in ['V(u,r)', '(V(u,r)>0)?1:(2147483647+1)', '(V(u,r)>0)?1:(1/0)']:
            with self.subTest(rhs=rhs), self.assertRaises(CompileError):
                self.compile('k='+rhs+'; a=k+0.125; @(initial_step)q=0; '
                             '@(timer(0.5))q=a; V(y,r)<+q;', 'integer k; real a,q;')

    def test_repeated_alias_expansion_keeps_existing_ir_budget(self):
        # Each alias duplicates the full selected wire tree. Object sharing must
        # not turn the existing100000-item tree cap into a DAG-size allowance.
        assignments = ['a0=(V(u,r)>0)?V(u,r):0;']
        assignments += [f'a{i}=a{i-1}+a{i-1};' for i in range(1,16)]
        declarations = 'real '+','.join(f'a{i}' for i in range(16))+',q;'
        with self.assertRaises(CompileError) as error:
            self.compile(''.join(assignments)+'@(initial_step)q=0; @(timer(0.5))q=a15; V(y,r)<+q;',declarations)
        self.assertEqual(error.exception.diagnostic['code'], 'resource_budget')


if __name__ == '__main__':
    unittest.main()
