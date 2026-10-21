"""Procedural while and runtime-for loops with proven integer trip-count bounds.

Modules with physical outputs have no kernel runtime-loop path. A loop is
accepted there only when a closed integer invariant proves its maximal trip
count; it then runs as consecutive guarded trips. Unproven bounds keep an
explicit diagnostic. Related frontend gaps: $bound_step in event bodies and
bitwise initialization-loop values.
"""
GUARDS = ['LANG', 'EVENT-ORDER']
import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


def compile_body(body, declarations='integer p;'):
    return compile_sources({'loops.va': model(body, declarations)}, [instance()])


def outputs(program, times):
    result = transient(program, {'u': [[0, 1], [1, 1]]}, list(times), stop=1, max_step=0.05,
                       kernel=KERNEL)
    index = result['nodes'].index('y')
    return [round(row['voltages'][index], 12) for row in result['solutions']]


def loops(value):
    if isinstance(value, dict):
        return (value.get('kind') == 'loop') + sum(loops(v) for v in value.values())
    if isinstance(value, list):
        return sum(loops(v) for v in value)
    return 0


def code(body, declarations='integer p;'):
    try:
        compile_body(body, declarations)
    except CompileError as error:
        return error.diagnostic['code']
    raise AssertionError('expected CompileError')


WRAP = '@(timer(0.1,0.1)) begin p = p + 3; while (p >= 8) p = p - 8; end V(y) <+ p;'


class WhileLoops(unittest.TestCase):
    def test_bounded_integer_while_matches_modulo_sequence(self):
        program = compile_body(WRAP)
        self.assertEqual(loops(program.to_dict()), 0)
        # Events at .1,.2,...: p = 3,6,1,4,7,2,5,0 (every trip count <= 1).
        times = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
        self.assertEqual(outputs(program, times), [0, 3, 6, 1, 4, 7, 2, 5, 0])

    def test_multi_trip_while_and_nonrelational_condition(self):
        # p in [0,3]; p+9 needs up to three trips, proven from the closed invariant.
        body = ('@(timer(0.1,0.1)) begin p = p + 9; while (p >= 4) p = p - 4; '
                'q = 0; while (!(q >= 2)) q = q + 1; end V(y) <+ p + 100*q;')
        program = compile_body(body, 'integer p, q;')
        self.assertEqual(outputs(program, [0.15, 0.25, 0.35, 0.45]), [201, 202, 203, 200])

    def test_real_or_unproven_conditions_keep_explicit_refusal(self):
        cases = [
            ('@(timer(0.1,0.1)) begin x = x + 0.3; while (x > 1.0) x = x - 1.0; end V(y) <+ x;', 'real x;'),
            # Interval invariant widens p to signed32; no finite trip bound follows.
            ('@(timer(0.1,0.1)) begin p = p + 1; while (p > 100) p = p - 1; end V(y) <+ p;', 'integer p;'),
            ('@(timer(0.1,0.1)) begin while (p >= 0) p = p + 1; end V(y) <+ p;', 'integer p;'),
        ]
        for body, declarations in cases:
            with self.subTest(body=body):
                self.assertEqual(code(body, declarations), 'unsupported_loop_bound')

    def test_while_outside_runtime_events_is_rejected(self):
        self.assertEqual(code('p = 3; while (p > 0) p = p - 1; V(y) <+ p;'), 'unsupported_loop_bound')
        self.assertEqual(code('@(initial_step) begin p = 3; while (p > 0) p = p - 1; end V(y) <+ p;'),
                         'unsupported_initial_event')

    def test_while_is_reserved(self):
        self.assertEqual(code('V(y) <+ 0;', 'integer while;'), 'syntax_error')


class PhysicalRuntimeFor(unittest.TestCase):
    def test_input_selected_limit_runs_bounded_trips(self):
        body = ('@(timer(0.1,0.1)) begin n = 0; if (V(u) > 0.5) n = n + 3; q = 0; '
                'for (i = 0; i < n; i = i + 1) q = q + 2; end V(y) <+ q + 10*i;')
        program = compile_body(body, 'integer i, n, q;')
        self.assertEqual(loops(program.to_dict()), 0)
        self.assertEqual(outputs(program, [0.05, 0.15]), [0, 36])

    def test_zero_trip_bound_admits_a_limit_written_by_the_body(self):
        # n is only written inside a loop that never starts, so n stays 0 and
        # the single retained test is false (formerly an unconditional refusal).
        body = '@(timer(0.5)) for (i = 0; i < n; i = i + 1) n = n + 1; V(y) <+ n + 10*i;'
        self.assertEqual(outputs(compile_body(body, 'integer n, i;'), [0.25, 0.75]), [0, 0])

    def test_unbounded_runtime_for_keeps_existing_rejection(self):
        body = ('@(timer(0.1,0.1)) begin n = n + 1; q = 0; '
                'for (i = 0; i < n; i = i + 1) q = q + 2; end V(y) <+ q;')
        self.assertEqual(code(body, 'integer i, n, q;'), 'unsupported_event_loop')


class RelatedFrontendGaps(unittest.TestCase):
    def test_bound_step_in_event_body_has_explicit_diagnostic(self):
        self.assertEqual(code('@(timer(0.1,0.1)) begin p = p + 1; $bound_step(0.01); end V(y) <+ p;'),
                         'unsupported_task_context')

    def test_random_system_function_has_explicit_diagnostic(self):
        self.assertEqual(code('@(timer(0.1,0.1)) p = $rdist_normal(p, 0, 1); V(y) <+ p;'),
                         'unsupported_system_function')
        self.assertEqual(code('V(y) <+ $ x;', 'real x;'), 'syntax_error')

    def test_initialization_loop_folds_typed_constant_bits(self):
        body = ('@(initial_step) for (i = 0; i < 4; i = i + 1) b[i] = (s >> i) & 1; '
                'V(y) <+ b[0] + 2*b[1] + 4*b[2] + 8*b[3];')
        program = compile_body(body, 'parameter integer s = 42; integer b[0:3]; integer i;')
        self.assertEqual(outputs(program, [0.5]), [10])
        self.assertEqual(code(body, 'parameter real s = 42; integer b[0:3]; integer i;'),
                         'unsupported_initial_event')


if __name__ == '__main__':
    unittest.main()
