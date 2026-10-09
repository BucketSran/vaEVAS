"""Independent checks for distinct event blocks writing one state.

These tests cover the bounded EVENT-ORDER extension: different event blocks may
write the same state when a candidate batch selects at most one writer.
Simultaneous selected writers remain an atomic runtime conflict.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["EVENT-ORDER", "EVENT-CONDITIONS"]

import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


V3_SOURCE = model('''
  @(initial_step) q=0;
  @(cross(V(u,r)-0.65,+1,100p,100u)) q=1;
  @(cross(V(u,r)-0.35,-1,100p,100u)) q=0;
  V(y,r)<+transition(0.1+0.8*q,0,50n,50n);
''', 'integer q;')


def compile_v3(instances=None):
    return compile_sources({'event_writers.va': V3_SOURCE}, instances or [instance()])


def event_writer_instance():
    return instance(connections=dict(u='u', sel='sel', y='y', r='0'))


def execute_v3(*, sources=None, times=None, instances=None):
    return transient(
        compile_v3(instances),
        sources or {'u': [[0,.4],[1e-6,.8],[2e-6,.2],[3e-6,.8]]},
        times or [0,.7e-6,1.8e-6,2.9e-6,3e-6],
        stop=3e-6,
        max_step=10e-6,
        kernel=KERNEL,
    )


class EventWriterContracts(unittest.TestCase):
    def test_hysteresis_events_write_one_state_in_different_batches(self):
        result = execute_v3()
        self.assertEqual([event['event'] for event in result['transient']['events']], [0,1,0])
        for event, expected in zip(result['transient']['events'], [.625e-6,1.75e-6,2.75e-6]):
            self.assertAlmostEqual(event['time'], expected, delta=1e-18)
        self.assertEqual(result['transient']['states'], [[0],[1],[0],[1],[1]])
        y = result['nodes'].index('y')
        for row, expected in zip(result['solutions'], [.1,.9,.1,.9,.9]):
            self.assertAlmostEqual(row['voltages'][y], expected, places=12)

    def test_no_trigger_holds_initial_state(self):
        result = execute_v3(sources={'u': [[0,.5],[3e-6,.5]]})
        self.assertEqual(result['transient']['events'], [])
        self.assertEqual(result['transient']['states'], [[0],[0],[0],[0],[0]])
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [.1]*5)

    def test_instance_order_does_not_merge_state_writers(self):
        a = instance('a', connections=dict(u='u', y='a', r='0'))
        b = instance('b', connections=dict(u='v', y='b', r='0'))
        sources = {
            'u': [[0,.4],[1e-6,.8],[2e-6,.2],[3e-6,.8]],
            'v': [[0,.8],[.8e-6,.2],[1.8e-6,.8],[2.8e-6,.2],[3e-6,.2]],
        }
        results = [execute_v3(sources=sources, instances=order) for order in ([a,b], [b,a])]
        self.assertEqual(results[0]['solutions'], results[1]['solutions'])
        for result in results:
            final = dict(zip(result['transient']['state_names'], result['transient']['states'][-1]))
            self.assertEqual(final, {'a:q': 1, 'b:q': 0})
            self.assertEqual(len(result['transient']['events']), 6)

    def test_simultaneous_writers_are_atomic_conflicts(self):
        source = model('''@(initial_step) q=0;
          @(cross(V(u,r)-0.5,+1,100p,100u)) q=1;
          @(cross(V(u,r)-0.5,+1,100p,100u)) q=2;
          V(y,r)<+q;''', 'integer q;')
        program = compile_sources({'event_writers.va': source}, [instance()])
        with self.assertRaisesRegex(KernelError, 'event_conflict'):
            transient(
                program,
                {'u': [[0,.4],[1e-6,.6],[2e-6,.4],[3e-6,.6]]},
                [0,3e-6],
                stop=3e-6,
                max_step=10e-6,
                kernel=KERNEL,
            )

    def test_same_time_conditional_blocks_count_only_selected_assignments(self):
        writers = [
            '@(cross(V(u,r)-0.5,+1,100p,100u)) if (V(sel,r)>=0.5) q=1;',
            '@(cross(V(u,r)-0.5,+1,100p,100u)) if (V(sel,r)<0.5) q=2;',
        ]
        for label, body in [('selected_first', writers), ('selected_second', list(reversed(writers)))]:
            source = model('@(initial_step) q=0;' + ''.join(body) + 'V(y,r)<+q;',
                           'integer q;', ports='u,sel,y,r',
                           directions='input u,sel; output y; inout r;')
            program = compile_sources({'event_writers.va': source}, [event_writer_instance()])
            result = transient(
                program,
                {'u': [[0,.4],[1e-6,.6]], 'sel': [[0,.5],[1e-6,.5]]},
                [0,1e-6],
                stop=1e-6,
                max_step=10e-6,
                kernel=KERNEL,
            )
            with self.subTest(order=label):
                self.assertEqual([event['event'] for event in result['transient']['events']], [0,1])
                self.assertEqual(result['transient']['events'][0]['after'], [1])
                self.assertEqual(result['transient']['events'][1]['after'], [1])
                self.assertEqual(result['transient']['states'], [[0],[1]])
                y = result['nodes'].index('y')
                self.assertEqual([row['voltages'][y] for row in result['solutions']], [0,1])

    def test_same_time_conditional_blocks_conflict_when_both_selected_even_same_value(self):
        source = model('''@(initial_step) q=0;
          @(cross(V(u,r)-0.5,+1,100p,100u)) if (V(sel,r)>=0.5) q=1;
          @(cross(V(u,r)-0.5,+1,100p,100u)) if (V(sel,r)<=0.5) q=1;
          V(y,r)<+q;''', 'integer q;', ports='u,sel,y,r',
                       directions='input u,sel; output y; inout r;')
        program = compile_sources({'event_writers.va': source}, [event_writer_instance()])
        with self.assertRaisesRegex(KernelError, 'event_conflict'):
            transient(
                program,
                {'u': [[0,.4],[1e-6,.6]], 'sel': [[0,.5],[1e-6,.5]]},
                [0,1e-6],
                stop=1e-6,
                max_step=10e-6,
                kernel=KERNEL,
            )

    def test_cross_block_state_reads_use_structural_dependencies(self):
        cases = [
            ('same_cancel', 'real q;', '@(initial_step) q=3;', 'q', 'q-q'),
            ('same_zero', 'real q;', '@(initial_step) q=3;', 'q', '0*q'),
            ('same_underflow', 'real q;', '@(initial_step) q=3;', 'q', '(1e-200*1e-200)*q'),
            ('other_cancel', 'real p,q;', '@(initial_step) p=3; @(initial_step) q=0;', 'p', 'p-p'),
            ('other_zero', 'real p,q;', '@(initial_step) p=3; @(initial_step) q=0;', 'p', '0*p'),
            ('other_underflow', 'real p,q;', '@(initial_step) p=3; @(initial_step) q=0;', 'p', '(1e-200*1e-200)*p'),
        ]
        for label, declarations, initial, written, rhs in cases:
            source = model(f'''{initial}
              @(timer(0.5,0,1e-12)) {written}=7;
              @(timer(1.0,0,1e-12)) q={rhs};
              V(y,r)<+q;''', declarations)
            program = compile_sources({label + '.va': source}, [instance()])
            with self.subTest(label=label), self.assertRaisesRegex(KernelError, 'unsupported_cross'):
                transient(
                    program,
                    {'u': [[0,0],[1,0]]},
                    [0,0.5,1.0],
                    stop=1.0,
                    max_step=2,
                    kernel=KERNEL,
                )


if __name__ == '__main__':
    unittest.main()
