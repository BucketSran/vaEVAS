"""Constant aliases obey source order through public initialization and events."""
GUARDS = ['LANG', 'CROSS', 'TIMER', 'EVENT-ORDER']

import unittest

from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


class ConstantEventAliases(unittest.TestCase):
    def test_parameter_aliases_drive_initial_and_cross_with_instance_overrides(self):
        # upper=.25 and lower=-.25. The input begins above upper, falls through
        # lower at .625, and returns through upper at 1.625.
        text = model('''upper=offset+width/2.0; lower=offset-width/2.0;
            @(initial_step) if(V(u,r)>=upper) q=1; else q=0;
            @(cross(V(u,r)-upper,1)) q=1;
            @(cross(V(u,r)-lower,-1)) q=0;
            V(y,r)<+q;''', 'parameter real offset=0; parameter real width=1; '
            'real upper,lower; integer q;')
        program = compile_sources({'aliases.va':text}, [instance(parameters={'width':.5})])
        result = transient(program, {'u':[[0,1],[1,-1],[2,1]]}, [0,.75,1.5,1.75],
                           stop=2, max_step=1, kernel=KERNEL)
        ys = [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]
        self.assertEqual(ys, [1,0,0,1])
        self.assertEqual([state.name for state in program.states], ['q'])

    def test_chained_aliases_keep_parameter_binding_and_statement_order(self):
        text = model('a=bias; b=2*a; @(initial_step) q=b; '
                     '@(timer(0.5)) q=a; V(y,r)<+q;',
                     'parameter real bias=3; real a,b,q;')
        program = compile_sources({'aliases.va':text}, [instance()])
        result = transient(program, {'u':[[0,0],[1,0]]}, [0,1],
                           stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')] for row in result['solutions']], [6,3])

    def test_constant_timer_aliases_are_instance_local(self):
        text = model('start=delay; tolerance=0.001; @(initial_step) q=0; '
                     '@(timer(start,0,tolerance)) q=2; V(y,r)<+q;',
                     'parameter real delay=0.5; real start,tolerance,q;')
        instances = [instance('a', connections={'u':'u','y':'ya','r':'0'}),
                     instance('b', connections={'u':'u','y':'yb','r':'0'},
                              parameters={'delay':0.75})]
        program = compile_sources({'aliases.va':text}, instances)
        result = transient(program, {'u':[[0,0],[1,0]]}, [0,0.6,0.9],
                           stop=1, max_step=1, kernel=KERNEL)
        for name, expected in [('ya',[0,2,2]), ('yb',[0,0,2])]:
            observed = [row['voltages'][result['nodes'].index(name)] for row in result['solutions']]
            self.assertEqual(observed, expected)

    def test_future_reassigned_and_dynamic_aliases_still_reject(self):
        bodies = [
            '@(initial_step) q=a; a=1;',
            '@(timer(0.5)) q=a; a=1;',
            'a=1; @(initial_step) q=a; a=2;',
            'a=1; if(V(u,r)>0) a=2; @(timer(0.5)) q=a;',
            'a=b; b=2; @(initial_step) q=a;',
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_sources({'aliases.va':model(body+' V(y,r)<+q;', 'real a,b,q;')}, [instance()])


class RealInitialSampling(unittest.TestCase):
    def test_input_affine_initial_value_is_sampled_once_before_timer(self):
        # The initial voltage is .5, hence q=.375. A zero-time event adds .25;
        # later input motion must not change the held real value.
        text = model('@(initial_step) q=0.5*V(u,r)+0.125; '
                     '@(timer(0)) q=q+0.25; V(y,r)<+q;', 'real q;')
        program = compile_sources({'sample.va':text}, [instance()])
        result = transient(program, {'u':[[0,.5],[1,1.5]]}, [0,.5,1],
                           stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual(result['transient']['states'], [[.625],[.625],[.625]])

    def test_selected_affine_initial_arms_retain_source_order(self):
        text = model('@(initial_step) begin q=V(u,r); '
                     'if(q>0.5) q=2*q; else q=q+0.25; p=q+0.125; end '
                     'V(y,r)<+p;', 'real q,p;')
        program = compile_sources({'sample.va':text}, [instance()])
        for input_value, expected in [(.25,.625),(.75,1.625)]:
            with self.subTest(input=input_value):
                result = transient(program, {'u':[[0,input_value],[1,0]]}, [0,1],
                                   stop=1, max_step=1, kernel=KERNEL)
                self.assertEqual([row['voltages'][result['nodes'].index('y')]
                                  for row in result['solutions']], [expected,expected])

    def test_integer_nonlinear_and_noninput_samples_still_reject(self):
        for kind, rhs in [('integer','V(u,r)'), ('real','V(u,r)*V(u,r)'),
                          ('real','V(y,r)'), ('real','0*V(y,r)')]:
            with self.subTest(kind=kind,rhs=rhs), self.assertRaises(CompileError):
                compile_sources({'sample.va':model('@(initial_step) q='+rhs+'; V(y,r)<+q;',
                                                    kind+' q;')}, [instance()])


if __name__ == '__main__':
    unittest.main()
