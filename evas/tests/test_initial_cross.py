"""Constant initialization/cross OR through the public compiler and Rust path."""
GUARDS = ["LANG", "CROSS", "EVENT-ORDER", "EVENT-CONDITIONS"]

import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, model


def source(initial='initial_step or cross(V(u,r)-2,1,1e-12,1e-9)', value='7'):
    return model(f'''@({initial}) n={value};
      @(cross(V(v,r)-1,1,1e-12,1e-9)) n=2; V(y,r)<+n;''',
      'integer n; parameter integer seed=7;', ports='u,v,y,r',
      directions='input u,v; output y; inout r;')


def compiled(text, instances=None):
    return compile_sources({'initial-cross.va': text}, instances or [
        Instance('dut', 'm', {'u': 'u', 'v': 'v', 'y': 'y', 'r': '0'})])


def run(program):
    return transient(program, {'u': [[0, 0], [2.5, 2.5]], 'v': [[0, 0], [2.5, 2.5]]},
                     [0, .5, 1.5, 2.5], stop=2.5, max_step=2.5, kernel=KERNEL)


def values(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class InitialCross(unittest.TestCase):
    def test_shared_body_initializes_once_then_runs_again_on_reset_cross(self):
        result = run(compiled(source()))
        self.assertEqual(values(result), [7, 7, 2, 7])
        self.assertEqual(len(result['transient']['events']), 2)
        for event, expected in zip(result['transient']['events'], [1, 2]):
            self.assertAlmostEqual(event['time'], expected, delta=1e-9)

    def test_instance_constants_and_repeated_simulations_do_not_leak_state(self):
        a = Instance('a', 'm', {'u': 'u', 'v': 'v', 'y': 'a', 'r': '0'}, {'seed': 7})
        b = Instance('b', 'm', {'u': 'u', 'v': 'v', 'y': 'b', 'r': '0'}, {'seed': 9})
        for order in ([a, b], [b, a]):
            program = compiled(source(value='seed'), order)
            for _ in range(2):
                result = run(program)
                self.assertEqual(values(result, 'a'), [7, 7, 2, 7])
                self.assertEqual(values(result, 'b'), [9, 9, 2, 9])
                self.assertEqual(len(result['transient']['events']), 4)

    def test_cross_leaf_order_and_redundant_cross_union_preserve_initialization(self):
        for trigger in (
            'cross(V(u,r)-2,1,1e-12,1e-9) or initial_step',
            'cross(V(u,r)-2,1,1e-12,1e-9) or initial_step or cross(V(u,r)-2,1,1e-12,1e-9)',
        ):
            with self.subTest(trigger=trigger):
                result = run(compiled(source(initial=trigger)))
                self.assertEqual(values(result), [7, 7, 2, 7])
                self.assertEqual(len(result['transient']['events']), 2)
                if trigger.count('cross') == 2:
                    self.assertEqual(len(result['transient']['events'][-1]['fired_triggers']), 2)

    def test_constant_array_body_reuses_existing_unique_initialization(self):
        text = model('''@(initial_step or cross(V(u,r)-2,1,1e-12,1e-9))
          begin n[0]=3; n[1]=4; end
          @(cross(V(v,r)-1,1,1e-12,1e-9)) begin n[0]=9; n[1]=8; end
          V(y,r)<+n[0]+10*n[1];''', 'integer n[0:1];', ports='u,v,y,r',
          directions='input u,v; output y; inout r;')
        self.assertEqual(values(run(compiled(text))), [43, 43, 89, 43])

    def test_initialization_precedes_separate_t0_timer_without_extra_record(self):
        text = source().replace('cross(V(v,r)-1,1,1e-12,1e-9)', 'timer(0,0,1e-12)')
        result = run(compiled(text))
        self.assertEqual(values(result), [2, 2, 2, 7])
        self.assertEqual(len(result['transient']['events']), 2)
        self.assertEqual(result['transient']['events'][0]['time'], 0)
        self.assertEqual(result['transient']['events'][0]['before'], [7])

    def test_same_time_writers_remain_atomic_conflicts(self):
        text = source().replace('cross(V(v,r)-1,1,1e-12,1e-9)', 'cross(V(v,r)-2,1,1e-12,1e-9)')
        with self.assertRaisesRegex(KernelError, 'event_conflict'):
            run(compiled(text))

    def test_dynamic_initial_values_have_initialization_diagnostic(self):
        for value in ('V(u,r)', 'n', 'idt(V(u,r),0)'):
            with self.subTest(value=value), self.assertRaises(CompileError) as caught:
                compiled(source(value=value))
            self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_initial_event')
            self.assertIn('initial_step values must be instance constants', str(caught.exception))

    def test_qualified_repeated_initial_and_timer_mixtures_remain_rejected(self):
        for trigger in (
            'initial_step("dc") or cross(V(u,r)-2,1,1e-12,1e-9)',
            'initial_step or initial_step("tran") or cross(V(u,r)-2,1,1e-12,1e-9)',
            'initial_step or initial_step or cross(V(u,r)-2,1,1e-12,1e-9)',
            'initial_step or timer(0)',
            'timer(0) or initial_step',
            'initial_step or cross(V(u,r)-2,1,1e-12,1e-9) or timer(1)',
        ):
            with self.subTest(trigger=trigger), self.assertRaises(CompileError) as caught:
                compiled(source(initial=trigger))
            self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_initial_event')

    def test_mixed_body_preserves_unique_complete_unconditional_initialization(self):
        valid = source()
        invalid = [
            valid.replace('n=7;', 'begin n=7; n=8; end', 1),
            valid.replace('integer n;', 'integer n,p;'),
            valid.replace('n=7;', 'if(V(u,r)>0) n=7;', 1),
            valid.replace('n=7;', '@(timer(1)) n=7;', 1),
        ]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(CompileError):
                compiled(text)


if __name__ == '__main__':
    unittest.main()
