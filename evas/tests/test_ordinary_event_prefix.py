"""Pure-input ordinary prefixes retain their value at each event source site."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']

import os
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient


def program(body, declarations='real a,q;'):
    source = ('`include "disciplines.vams"\nmodule m(u,y);input u;output y;'
              'electrical u,y;' + declarations + 'analog begin ' + body +
              'end endmodule')
    return compile_sources({'ordinary-prefix.va': source},
                           [Instance('dut', 'm', {'u': 'u', 'y': 'y'})])


class OrdinaryEventPrefix(unittest.TestCase):
    def run_values(self, p, times=(0., 0.25, 0.5, 0.75, 1.), **kw):
        result = transient(p, {'u': [[0., 0.], [1., 1.]]}, list(times),
                           stop=1., max_step=0.25,
                           kernel=Path(os.environ['EVAS_TEST_KERNEL']),
                           vabstol=1e-10, reltol=0., **kw)
        node = result['nodes'].index('y')
        return result, [row['voltages'][node] for row in result['solutions']]

    def test_original_typed_source_keeps_default_budget_and_full_wire(self):
        import hashlib
        from test_native_audit import source
        original = source(True)

        def consumer(k):
            return original.replace('n=n+1;', 'n=n+1;'*k).replace('m=m+1;', 'm=m+1;'*k)

        text225 = consumer(225)
        self.assertEqual(hashlib.sha256(text225.encode()).hexdigest(),
                         '2071555869fc4bb90e83e54ccc859aa9d89d7beaf934218acade489f9ffc12da')
        instances = [Instance('dut', 'm', dict(y='y', z='z', r='0'))]
        p = compile_sources({'ledger.va': text225}, instances)
        # These are the original consumer's independently observed owner totals,
        # including its complete wire materialization under the unchanged cap.
        self.assertEqual(p._native_audit.used, 82919)
        self.assertIsInstance(p.to_dict(), dict)
        self.assertEqual(p._native_audit.used, 99899)
        with self.assertRaises(CompileError) as failure:
            compile_sources({'ledger.va': consumer(226)}, instances).to_dict()
        self.assertEqual(failure.exception.diagnostic['code'], 'resource_budget')

    def test_old_single_writer_transitive_sampled_alias_keeps_its_value(self):
        # u(t)=t gives b(1/2)=2*abs(1/2-1/4)=1/2. Both aliases have
        # exactly one writer and already belong to the old sampled-body route.
        p = program('@(initial_step)q=0; a=abs(V(u)-0.25); b=2*a; '
                    '@(timer(0.5))q=b; V(y)<+q;', 'real a,b,q;')
        _, values = self.run_values(p)
        self.assertEqual(values, [0., 0., 0.5, 0.5, 0.5])
        self.assertEqual([state.name for state in p.states], ['q'])

    def test_multiwriter_pure_input_prefix_samples_current_root(self):
        # The exact input is u(t)=t. This source prefix computes
        # a(t)=min(1/4+abs(t-1/4),3/4). At t=1/2 its value is1/2.
        # q must sample this value at the callback, rather than the t=0 value
        # or an unrelated later ordinary assignment. All constants are dyadic.
        p = program('@(initial_step)q=0; '
                    'a=0.25+abs(V(u)-0.25); if(a>0.75)a=0.75; '
                    '@(timer(0.5))q=a; V(y)<+q;')
        r = transient(p, {'u': [[0., 0.], [1., 1.]]},
                      [0., 0.25, 0.5, 0.75, 1.], stop=1., max_step=0.25,
                      kernel=Path(os.environ['EVAS_TEST_KERNEL']),
                      vabstol=1e-10, reltol=0.)
        node = r['nodes'].index('y')
        self.assertEqual([row['voltages'][node] for row in r['solutions']],
                         [0., 0., 0.5, 0.5, 0.5])
        self.assertEqual([(s.name, s.initial) for s in p.states], [('q', 0.)])

    def test_two_event_positions_keep_distinct_prefix_values(self):
        # q1 samples t at1/4; q2 samples2*t at3/4.
        p = program('@(initial_step)begin q=0; b=0;end '
                    'a=V(u); @(timer(0.25))q=a; '
                    'a=2*V(u); @(timer(0.75))b=a; V(y)<+q+b;', 'real a,b,q;')
        _, values = self.run_values(p)
        self.assertEqual(values, [0., 0.25, 0.25, 1.75, 1.75])

    def test_branch_merge_and_transitive_prefix_have_independent_answer(self):
        p = program('@(initial_step)q=0; a=V(u); '
                    'if(a>0.5)a=0.5; b=2*a; @(timer(0.75))q=b; V(y)<+q;',
                    'real a,b,q;')
        _, values = self.run_values(p)
        self.assertEqual(values, [0., 0., 0., 1., 1.])

    def test_same_time_callback_order_and_extra_queries_preserve_prefix(self):
        # Different event targets preserve the existing simultaneous-writer
        # contract. The two lexical prefixes sample t and2*t respectively.
        p = program('@(initial_step)begin q=0;b=0;end '
                    'a=V(u); if(a>0.75)a=0.75; @(timer(0.5))q=a; '
                    'a=2*V(u); if(a>1.5)a=1.5; @(timer(0.5))b=a; V(y)<+q+b;',
                    'real a,b,q;')
        sparse, actual = self.run_values(p)
        dense_times = tuple(k/16 for k in range(17))
        dense, expanded = self.run_values(p, dense_times)
        self.assertEqual(actual, [0., 0., 1.5, 1.5, 1.5])
        self.assertEqual(expanded, [0. if t<0.5 else 1.5 for t in dense_times])
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])

    def test_simultaneous_conflicting_writers_keep_the_original_rejection(self):
        p = program('@(initial_step)q=0; a=V(u); if(a>0.75)a=0.75; '
                    '@(timer(0.5))q=a; @(timer(0.5))q=q+a; V(y)<+q;')
        with self.assertRaises(KernelError) as failure:
            self.run_values(p)
        self.assertEqual(failure.exception.detail['kind'], 'event_conflict')

    def test_input_prefix_can_feed_post_callback_initial_only_metric(self):
        # q remains1/4 throughout this model. metric's state retains its cold
        # seed7, while ordinary output observes2*q-a at each current input.
        p = program('@(initial_step)begin q=0.25; metric=7;end '
                    'a=abs(V(u)-0.25); if(a>0.5)a=0.5; '
                    '@(timer(0.5))q=a; metric=q-a; V(y)<+metric+q;',
                    'real a,q,metric;')
        result, values = self.run_values(p)
        self.assertEqual(values, [0.25, 0.5, 0.25, 0., 0.])
        self.assertEqual(result['transient']['states'], [[0.25, 7.]]*5)

    def test_missing_future_state_time_history_output_and_loop_prefixes_reject(self):
        cases = [
            ('', 'a=V(u);'),
            ('if(V(u)>0)a=V(u);', ''),
            ('a=q; a=a+1;', ''),
            ('a=$abstime; a=a+1;', ''),
            ('a=idt(V(u),0); a=a+1;', ''),
            ('a=0*V(y); a=a+1;', ''),
            ('a=(1>0)?V(u):0*V(y); a=a+1;', ''),
            ('a=V(u)*V(u); a=a+1;', ''),
            ('a=V(u); for(i=0;i<0;i=i+1)a=0; a=a+1;', ''),
            ('a=V(u); @(timer(0.125))a=0; a=a+1;', ''),
        ]
        for before, after in cases:
            with self.subTest(before=before, after=after), self.assertRaises(CompileError) as failure:
                program('@(initial_step)q=0; '+before+
                        '@(timer(0.5))q=a; '+after+'V(y)<+q;', 'integer i;real a,q;')
            self.assertNotEqual(failure.exception.diagnostic['code'], 'syntax_error')

    def test_body_prefix_does_not_enter_triggers_or_settings(self):
        for event in ['@(cross(a-0.25,+1))q=1;', '@(timer(a))q=1;',
                      '@(timer(0.5,0,a))q=1;']:
            with self.subTest(event=event), self.assertRaises(CompileError) as failure:
                program('@(initial_step)q=0; a=V(u); if(a>0.5)a=0.5; '+
                        event+'V(y)<+q;')
            self.assertNotEqual(failure.exception.diagnostic['code'], 'syntax_error')

    def test_prefix_does_not_erase_source_uncertainty_after_sampling(self):
        p = program('@(initial_step)q=0; a=V(u); if(a>0.75)a=0.75; '
                    '@(timer(0.5))q=a; V(y)<+1000000*q;')
        with self.assertRaises(KernelError):
            self.run_values(p, source_errors={'u': .01})

    def test_reassigned_prefix_retains_original_expanded_wire_budget(self):
        # Actual tree duplication across twenty source assignments exceeds the
        # unchanged100000-item cap. Python object sharing grants no larger cap.
        with self.assertRaises(CompileError) as error:
            program('@(initial_step)q=0; a=(V(u)>0)?V(u):0; '+
                    'a=a+a;'*20+'@(timer(0.5))q=a; V(y)<+q;')
        self.assertEqual(error.exception.diagnostic['code'], 'resource_budget')

    def test_held_guard_before_callback_cannot_masquerade_as_pure_input_prefix(self):
        # Each branch value is a pure constant, but which value e receives
        # depends on the earlier held n. A later callback changes n, so this
        # prefix cannot use the final Frame's n as a replacement for its source
        # position. Preserve the existing initial-only State/order rejection.
        with self.assertRaises(CompileError) as failure:
            program('@(initial_step)begin q=7;n=0;end '
                    'if(n>0)e=2;else e=1; @(timer(0.25))n=1; '
                    'q=e;V(y)<+q;', 'real e,q;integer n;')
        self.assertEqual(failure.exception.diagnostic['code'], 'unsupported_local_event')


if __name__ == '__main__':
    unittest.main()
