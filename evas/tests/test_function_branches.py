"""Real function branches preserve sequential values through public EVAS APIs."""
GUARDS = ["LANG", "LIN", "COMPOSE"]

import unittest
from pathlib import Path

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance


PREFIX = '''`include "disciplines.vams"
module m(u,y,r); input u; output y; inout r; electrical u,y,r;
parameter real vss=0, vdd=0.9;
analog function real clip;
input x; real x;
begin if(x<vss) clip=vss; else if(x>vdd) clip=vdd; else clip=x; end
endfunction
'''


def program(prefix=PREFIX, body='V(y,r)<+clip(V(u,r));', instances=None):
    return compile_sources({'function-branches.va':prefix+'analog begin '+body+' end endmodule'},
                           instances or [instance()])


class FunctionBranches(unittest.TestCase):
    def test_combined_branch_and_function_depth_is_a_structured_budget(self):
        definitions = []
        for i in range(16):
            value = f'f{i+1}(x)' if i < 15 else 'x'
            definitions.append(
                f'analog function real f{i}; input x; real x; begin f{i}=0; '
                + 'if(x>0) ' * 60 + f'f{i}={value}; end endfunction')
        prefix = PREFIX[:PREFIX.index('analog function')]+ '\n'.join(definitions)+'\n'
        with self.assertRaises(CompileError) as caught:
            program(prefix, 'V(y,r)<+f0(V(u,r));')
        self.assertEqual(caught.exception.diagnostic['code'], 'resource_budget')
        self.assertEqual(caught.exception.diagnostic['location']['source'], 'function-branches.va')

    def test_shallow_combined_branch_and_call_has_independent_answer(self):
        prefix = PREFIX[:PREFIX.index('analog function')]
        for i in range(2):
            value = 'f1(x)' if i == 0 else 'x'
            prefix += (f'analog function real f{i}; input x; real x; begin f{i}=0; '
                       + 'if(x>0) '*3 + f'f{i}={value}; end endfunction\n')
        p = program(prefix, 'V(y,r)<+f0(V(u,r));')
        result = solve(p, ['u'], [[-1], [0], [.25], [1]], kernel=KERNEL)
        self.assertEqual([row['voltages'][p.nodes.index('y')] for row in result['solutions']],
                         [0, 0, .25, 1])

    def test_real_clip_function_has_independent_voltage_table(self):
        result = solve(program(), ['u'], [[-.25], [0], [.25], [.9], [1.25]], kernel=KERNEL)
        values = [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]
        self.assertEqual(values, [0, 0, .25, .9, .9])

    def test_branch_predicate_captures_local_before_branch_writes(self):
        prefix = PREFIX[:PREFIX.index('analog function')]+'''analog function real clip;
input x; real x,t;
begin
  t=x; clip=-1;
  if(t>0) begin t=-t; clip=1; end
  else t=t-2;
  clip=clip+t;
end endfunction
'''
        result = solve(program(prefix), ['u'], [[-1], [0], [.25]], kernel=KERNEL)
        values = [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]
        self.assertEqual(values, [-4, -3, .75])

    def test_if_without_else_retains_preassigned_value(self):
        prefix = PREFIX.replace('if(x<vss) clip=vss; else if(x>vdd) clip=vdd; else clip=x;',
                                'clip=x; if(x<vss) clip=vss; if(x>vdd) clip=vdd;')
        result = solve(program(prefix), ['u'], [[-.25], [.25], [1.25]], kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')] for row in result['solutions']],
                         [0, .25, .9])

    def test_else_if_preserves_source_order_when_predicates_overlap(self):
        p = program(instances=[instance(parameters={'vss':.75,'vdd':.25})])
        result = solve(p, ['u'], [[.5], [.75]], kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')] for row in result['solutions']],
                         [.75,.25])

    def test_missing_branch_definitions_and_hidden_unsupported_operands_reject(self):
        for body in ('if(x>0) clip=x;',
                     'if(x>0) t=x; else clip=0; clip=t;',
                     'if(x>0) clip=x; else clip=idt(x,0);',
                     'if(x>0) clip=x; else clip=V(u,r);',
                     'if(x>0) clip=x; else clip=missing(x);',
                     'if(x>0) clip=x; else t=unknown; clip=1;',
                     'for(i=0;i<2;i=i+1) clip=x;'):
            prefix = PREFIX[:PREFIX.index('analog function')]+f'''analog function real clip;
input x; real x,t,i; begin {body} end endfunction
'''
            with self.subTest(body=body), self.assertRaises(CompileError):
                program(prefix)

    def test_unused_function_cannot_hide_invalid_branch(self):
        prefix = PREFIX.replace('else clip=x;', 'else clip=missing(x);')
        with self.assertRaises(CompileError):
            program(prefix, 'V(y,r)<+1;')

    def test_function_branch_certifies_original_pwl_boundary(self):
        from fractions import Fraction
        self.assertGreater(Fraction(2.7)/3, Fraction(.9))
        result = transient(program(), {'u':[[0,0],[3,1]]}, [2.7], stop=3,
                           max_step=3, kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')], .9)

    def test_instance_rails_and_continuous_crossings_have_independent_values(self):
        p = program(instances=[instance('a', connections={'u':'u','y':'a','r':'0'}),
                               instance('b', connections={'u':'u','y':'b','r':'0'},
                                        parameters={'vss':.25,'vdd':.5})])
        # u(t)=t/2 V. Include exact dyadic rails and samples on both sides of .9 V.
        times = [0,.25,.5,.75,1,1.75,1.875,2]
        result = transient(p, {'u':[[0,0],[2,1]]}, times, stop=2,
                           max_step=2, kernel=KERNEL)
        a, b = result['nodes'].index('a'), result['nodes'].index('b')
        self.assertEqual([row['voltages'][a] for row in result['solutions']],
                         [0,.125,.25,.375,.5,.875,.9,.9])
        self.assertEqual([row['voltages'][b] for row in result['solutions']],
                         [.25,.25,.25,.375,.5,.5,.5,.5])

    def test_frozen_spectre_pair_source_has_independent_pwl_answers(self):
        path = Path(__file__).resolve().parents[1]/'validation/cases/function_branches/dut.va'
        p = compile_sources({'frozen.va':path.read_text()}, [instance(module='function_branches',
                            connections={'u':'u','y':'y','z':'z'})])
        times = [0,.25,.5,.75,1,1.75,1.875,2]
        result = transient(p, {'u':[[0,0],[2,1]]}, times, stop=2, max_step=2, kernel=KERNEL)
        self.assertEqual([s['voltages'][result['nodes'].index('y')] for s in result['solutions']],
                         [0,.125,.25,.375,.5,.875,.9,.9])
        self.assertEqual([s['voltages'][result['nodes'].index('z')] for s in result['solutions']],
                         [0,.125,.25,.375,.5,.125,.0625,0])


if __name__ == '__main__':
    unittest.main()
