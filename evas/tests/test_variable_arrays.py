"""Array scalarization preserves ordered assignments and state ownership."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER', 'case:variable_array']
import unittest
from evas import CompileError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


class VariableArrays(unittest.TestCase):
    def compile(self, body, declarations='real a[0:2];', parameters=None):
        return compile_sources({'arrays.va': model(body, declarations)}, [instance(parameters=parameters or {})])

    def voltage(self, program, value=1):
        result = solve(program, ['u'], [[value]], kernel=KERNEL)
        return result['solutions'][0]['voltages'][program.nodes.index('y')]

    def test_ordered_local_elements_and_contributions(self):
        p = self.compile('a[0]=V(u,r); a[1]=2*a[0]; a[2]=a[0]+a[1]; V(y,r)<+a[2]; V(y,r)<+-2*V(y,r);')
        self.assertEqual(self.voltage(p, 3), 3)
        self.assertFalse(p.states)

    def test_parameter_bounds_and_genvar_indices(self):
        p = self.compile('s=0; for(i=0;i<N;i=i+1) begin a[i]=(i+1)*V(u,r); s=s+a[i]; end V(y,r)<+s;',
                         'parameter real N=3; real a[0:N-1],s; genvar i;', {'N': 4})
        self.assertEqual(self.voltage(p, .5), 5)

    def test_descending_and_negative_indices(self):
        p = self.compile('a[1]=V(u,r); a[0]=2*a[1]; a[-1]=a[0]+1; V(y,r)<+a[-1];', 'real a[1:-1];')
        self.assertEqual(self.voltage(p, 2), 5)

    def test_event_elements_are_distinct_ordered_states(self):
        p = self.compile('@(initial_step) begin a[0]=0; a[1]=1; end '
                         '@(timer(.25,.25,1e-9)) begin a[0]=a[0]+1; a[1]=a[0]+a[1]; end V(y,r)<+a[1];',
                         'integer a[0:1];')
        result = transient(p, {'u':[[0,0],[1,0]]}, [.5,1], stop=1, max_step=.5, kernel=KERNEL)
        self.assertEqual(result['transient']['states'][-1], [4,11])
        self.assertEqual(len(p.states),2)

    def test_instance_array_sizes_and_states_are_private(self):
        source = model('@(initial_step) begin a[0]=0; a[1]=1; end @(timer(.5,0,1e-9)) a[0]=a[1]+1; V(y,r)<+a[0];', 'real a[0:1];')
        instances = [instance('left'), instance('right')]
        p = compile_sources({'arrays.va':source}, instances)
        self.assertEqual([(state.instance,state.name) for state in p.states],
                         [('left','a[0]'),('left','a[1]'),('right','a[0]'),('right','a[1]')])

    def test_invalid_or_unsupported_indices_are_diagnostic(self):
        for body, declarations in [
            ('a[3]=1; V(y,r)<+1;', 'real a[0:2];'),
            ('a[.5]=1; V(y,r)<+1;', 'real a[0:2];'),
            ('a[0]=1; V(y,r)<+a[V(u,r)];','real a[0:2];'),
            ('a=1; V(y,r)<+1;', 'real a[0:2];'),
            ('x[0]=1; V(y,r)<+1;', 'real x;'),
            ('V(y,r)<+1;', 'real a[0:5000];'),
            ('V(y,r)<+1;', 'real a[0:.5];'),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, r'arrays.va:.*(array|index|budget)'):
                self.compile(body, declarations)

    def test_unassigned_element_does_not_borrow_another_element(self):
        with self.assertRaisesRegex(CompileError, 'not assigned before use'):
            self.compile('a[0]=1; V(y,r)<+a[1];')

    def test_indexed_function_return_cannot_silently_become_scalar(self):
        declarations = 'analog function real f; input x; real x; begin f[0]=x; end endfunction'
        with self.assertRaisesRegex(CompileError, 'scalar targets'):
            self.compile('V(y,r)<+f(V(u,r));', declarations)
