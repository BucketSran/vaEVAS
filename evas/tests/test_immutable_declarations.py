"""Read-only declaration values retain variable types and cannot be overridden."""
GUARDS = ['LANG', 'COMPOSE']

import unittest
from evas import CompileError, Instance, compile_sources, solve
from test_affine import KERNEL, model, instance


def value(program):
    r = solve(program, ['u'], [[0]], kernel=KERNEL)
    return r['solutions'][0]['voltages'][r['nodes'].index('y')]


def compile_one(declarations, body='V(y,r)<+x;', parameters=None):
    return compile_sources({'immutable.va': model(body, declarations)},
                           [instance(parameters=parameters)])


class ImmutableDeclarations(unittest.TestCase):
    def test_finite_scalar_values_need_no_states_or_events(self):
        for declaration, expected in [('real x=0.25;', .25), ('integer x=-9/2;', -4),
                                      ('real x=9/2;', 4), ('real x=9.0/2;', 4.5)]:
            with self.subTest(declaration=declaration):
                p = compile_one(declaration)
                self.assertEqual(p.states, ())
                self.assertEqual(p.events, ())
                self.assertEqual(value(p), expected)

    def test_parameter_dependencies_and_instance_order_are_isolated(self):
        text = model('V(y,r)<+x;', 'parameter real P=2;real x=P/2;')
        objects = [instance('a', connections=dict(u='u', y='a', r='0'), parameters={'P':2}),
                   instance('b', connections=dict(u='u', y='b', r='0'), parameters={'P':6})]
        for order in (objects, objects[::-1]):
            p = compile_sources({'immutable.va': text}, order)
            r = solve(p, ['u'], [[0]], kernel=KERNEL)
            row = dict(zip(r['nodes'], r['solutions'][0]['voltages']))
            self.assertEqual((row['a'], row['b']), (1, 3))
            self.assertEqual(p.states, ())
        with self.assertRaises(CompileError):
            compile_one('parameter real P=2;real x=P/2;', parameters={'x':4})

    def test_any_procedural_writer_prevents_immutable_classification(self):
        for body in ['x=1;V(y,r)<+x;', 'V(y,r)<+x;x=1;',
                     'if(0>1)x=1;V(y,r)<+x;',
                     '@(initial_step)if(0>1)x=1;V(y,r)<+x;',
                     '@(initial_step)x=1;V(y,r)<+x;',
                     '@(final_step)x=1;V(y,r)<+x;',
                     'for(k=0;k<0;k=k+1)x=1;V(y,r)<+x;',
                     '@(initial_step)for(k=0;k<0;k=k+1)x=1;V(y,r)<+x;']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_one('real x=0.25;genvar k;', body)
        # Existing declared event seeds keep their original event-state role.
        p = compile_one('real x=0.25;', '@(timer(1))x=1;V(y,r)<+x;')
        self.assertEqual([(s.name, s.initial) for s in p.states], [('x', .25)])
        p = compile_one('real x=0.25;', '@(timer(1))if(0>1)x=1;V(y,r)<+x;')
        self.assertEqual([(s.name, s.initial) for s in p.states], [('x', .25)])

    def test_self_and_variable_dependencies_and_arrays_still_reject(self):
        for declarations in ['real x=x;', 'real a=0.5;real x=a;',
                             'real x=a;real a=0.5;', 'real x[0:1]=1;']:
            with self.subTest(declarations=declarations), self.assertRaises(CompileError):
                compile_one(declarations)

    def test_invalid_unused_values_and_dead_obligations_are_audited(self):
        for expression in ['1e309', '1e308*2', '1/0', 'V(u,r)', '$abstime',
                           '2147483647+1-1', '(0>1)?1/0:2', 'sin(0)']:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_one('real x='+expression+';', 'V(y,r)<+0;')
        with self.assertRaises(CompileError):
            compile_one('integer x=1.5;')

    def test_variables_keep_source_type_and_function_namespace(self):
        with self.assertRaises(CompileError):
            compile_one('real x=1;', 'V(y,r)<+x&1;')
        p = compile_one('integer x=9/2;', 'V(y,r)<+(x&3);')
        self.assertEqual(value(p), 0)
        function = 'analog function real twice;input z;real z;begin twice=2*z;end endfunction '
        p = compile_one('parameter real P=0.25;real x=twice(P);'+function)
        self.assertEqual(value(p), .5)
        for declaration, body, expected in [('real floor=0.5;', 'V(y,r)<+floor;', .5),
                                           ('real tanh=0.25;', 'V(y,r)<+tanh;', .25)]:
            self.assertEqual(value(compile_one(declaration, body)), expected)
        with self.assertRaises(CompileError):
            compile_one('parameter real x=1;real x=2;')


if __name__ == '__main__':
    unittest.main()
