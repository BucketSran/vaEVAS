"""Finite genvar elaboration preserves additive relations and assignment order."""
GUARDS = ["LANG", "LIN", "COMPOSE", "case:static_loop"]

import unittest
from evas import CompileError, compile_sources, solve
from test_affine import KERNEL, instance, model


def compiled(body, declarations='genvar i; parameter real count=3;', instances=None):
    return compile_sources({'loop.va':model(body,declarations)},instances or [instance()])


def voltage(program, u=1, node='y'):
    r=solve(program,['u'],[[u]],kernel=KERNEL)
    return r['solutions'][0]['voltages'][r['nodes'].index(node)]


class StaticLoops(unittest.TestCase):
    def test_contributions_are_summed_and_parameter_override_is_instance_local(self):
        body='for(i=0;i<count;i=i+1) V(y,r)<+(i+1)*V(u,r);'
        instances=[instance('a',connections={'u':'u','y':'a','r':'0'},parameters={'count':2}),
                   instance('b',connections={'u':'u','y':'b','r':'0'},parameters={'count':4})]
        for order in (instances,instances[::-1]):
            p=compiled(body,instances=order)
            self.assertEqual(voltage(p,node='a'),3)
            self.assertEqual(voltage(p,node='b'),10)

    def test_sequential_locals_and_voltage_feedback(self):
        p=compiled('''sum=0; for(i=0;i<count;i=i+1) begin
          sum=sum+(i+1)*V(u,r); end V(y,r)<+sum-2*V(y,r);''',
                   'genvar i; parameter real count=3; real sum;')
        self.assertEqual(voltage(p,2),4)

    def test_descending_nested_and_empty_loops(self):
        p=compiled('for(i=3;i>0;i=i-1) V(y,r)<+i*V(u,r);')
        self.assertEqual(voltage(p),6)
        p=compiled('for(i=0;i<2;i=i+1) for(j=0;j<3;j=j+1) V(y,r)<+(i+1)*(j+1)*V(u,r);',
                   'genvar i,j;')
        self.assertEqual(voltage(p),18)
        p=compiled('V(y,r)<+1; for(i=0;i<0;i=i+1) V(y,r)<+100;')
        self.assertEqual(voltage(p),1)

    def test_function_calls_share_the_same_elaboration_and_relation_path(self):
        p=compiled('for(i=0;i<3;i=i+1) V(y,r)<+gain(i+1)*V(u,r);',
                   '''genvar i; analog function real gain;
                      input x; real x; begin gain=2*x; end endfunction''')
        self.assertEqual(voltage(p),12)

    def test_total_expansion_budget_applies_to_empty_nested_bodies(self):
        with self.assertRaisesRegex(CompileError, 'total static iteration budget'):
            compiled('V(y,r)<+1; for(i=0;i<4096;i=i+1) for(j=0;j<4096;j=j+1) begin end',
                     'genvar i,j;')
        for declarations in ('genvar i; parameter real i=3;', 'parameter real i=3; genvar i;'):
            with self.subTest(declarations=declarations), self.assertRaises(CompileError):
                compiled('V(y,r)<+1;', declarations)

    def test_nonterminating_dynamic_and_shadowed_loops_are_explicit(self):
        for body in (
            'for(i=0;i<2;i=i) V(y,r)<+1;',
            'for(i=0;i<2;i=i-1) V(y,r)<+1;',
            'for(i=0;i<V(u,r);i=i+1) V(y,r)<+1;',
            'for(i=0;i<2;i=i+1) for(i=0;i<2;i=i+1) V(y,r)<+1;',
            'for(i=0;i<2;i=i+1) i=1; V(y,r)<+1;',
            'for(i=0;i<2;i=i+.5) V(y,r)<+1;',
            'for(i=0;i<100000;i=i+1) V(y,r)<+1;',
        ):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compiled(body)


if __name__ == '__main__':
    unittest.main()
