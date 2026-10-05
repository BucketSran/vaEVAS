"""L1a public-entry contracts with a frozen, independent Fraction oracle."""
GUARDS = ['LANG', 'ANALOG']
import json
from fractions import Fraction as F
from pathlib import Path
import unittest

from evas import CompileError, KernelError, Instance, compile_sources, solve, transient
from test_affine import KERNEL

INPUTS = ('a', 'b', 'c', 'u')
ORACLE = json.loads((Path(__file__).parent/'fixtures/l1a_expected.json').read_text())['cases']
EXPRESSIONS = {
 'and2': {'y':'(V(a)>0.5 && V(b)>0.5) ? 1.25 : -0.25'},
 'comparison_boundary':dict(lt='V(u)<.5',le='V(u)<=.5',gt='V(u)>.5',ge='V(u)>=.5'),
 'not_truth':{'value':'!V(a)'},
 'numeric_logic':{'and_value':'V(a)&&V(b)','or_value':'V(a)||V(b)'},
 'logic_precedence':{'unparenthesized':'V(a)||V(b)&&V(c)','parenthesized':'(V(a)||V(b))&&V(c)'},
 'ternary_association':{'right_associated':'V(a)?1:V(b)?2:3','explicit_left':'(V(a)?1:V(b))?2:3'},
 'unary_precedence':{'not_a_plus_one':'!V(a)+1','not_sum':'!(V(a)+1)'},
 'comparison_left_association':{'left':'V(a)>V(b)>V(c)','right':'V(a)>(V(b)>V(c))'},
}


def compile_expr(expressions, prefix='', declarations=''):
    if isinstance(expressions,str): expressions={'y':expressions}
    outputs=tuple(expressions)
    ports=','.join((*INPUTS,*outputs,'r'))
    source=f'module logic({ports}); input a,b,c,u; output '+','.join(outputs)+f'; inout r; electrical {ports}; {declarations} analog begin '
    source+=prefix+''.join(f'V({n},r)<+{expr};' for n,expr in expressions.items())+' end endmodule'
    return compile_sources({'logic.va':source},[Instance('dut','logic',{n:n for n in (*INPUTS,*outputs)}|{'r':'0'}, {})])


def values(result,node='y'):
    return [s['voltages'][result['nodes'].index(node)] for s in result['solutions']]


def run_wave(expr, selector=0, times=(1.,)):
    sources={'u':[[0,0],[3,1]],'a':[[0,0],[3,0]],'b':[[0,selector],[3,selector]],'c':[[0,0],[3,0]]}
    return transient(compile_expr(expr),sources,list(times),stop=3,max_step=3,kernel=KERNEL,vabstol=1e-9,reltol=0)


class StatelessExpressionContracts(unittest.TestCase):
    def test_frozen_fraction_truth_tables_precedence_and_adjacent_thresholds(self):
        for group, expressions in EXPRESSIONS.items():
            cases=[c for c in ORACLE if c['group']==group]
            samples=[[float(F(c['inputs'].get(n,'0'))) for n in INPUTS] for c in cases]
            with self.subTest(group=group):
                result=solve(compile_expr(expressions),list(INPUTS),samples,kernel=KERNEL,vabstol=1e-9,reltol=0)
                for output in expressions:
                    self.assertEqual([F(v) for v in values(result,output)],[F(c['expected'][output]) for c in cases])

    def test_signed_zero_and_finite_nonzero_are_numeric_boolean_values(self):
        result=solve(compile_expr({'not_value':'!V(a)','and_value':'V(a)&&-3','or_value':'V(a)||0'}),
                     list(INPUTS),[[-0.,0,0,0],[0.,0,0,0],[-2.,0,0,0],[5e-324,0,0,0]],kernel=KERNEL)
        self.assertEqual(values(result,'not_value'),[1,1,0,0])
        self.assertEqual(values(result,'and_value'),[0,0,1,1])
        self.assertEqual(values(result,'or_value'),[0,0,1,1])

    def test_external_pwl_crossing_boundary_and_query_refinement(self):
        cases=[c for c in ORACLE if c['group']=='pwl_crossing']
        times=[float(F(c['inputs']['t'])) for c in cases]
        expr='(V(a)>.5 && V(b)>.5)?1.25:-.25'
        p=compile_expr(expr)
        sources={'a':[[0,0],[2,1]],'b':[[0,1],[2,1]],'c':[[0,0],[2,0]],'u':[[0,0],[2,0]]}
        baseline=None
        for grid in (times, sorted(set(times+[i/8 for i in range(17)]))):
            result=transient(p,sources,grid,stop=2,max_step=2,kernel=KERNEL,vabstol=1e-9,reltol=0)
            selected=[values(result)[grid.index(t)] for t in times]
            self.assertEqual([F(v) for v in selected],[F(c['expected']['y']) for c in cases])
            self.assertEqual(result['transient']['events'],[])
            if baseline is None:baseline=selected
            self.assertEqual(selected,baseline)

    def test_active_precision_refusal_and_unselected_nested_decisions(self):
        ambiguous='V(u)>0.3333333333333333'
        self.assertGreater(F(1,3),F(float('0.3333333333333333')))
        for expr, answer in [('0&&('+ambiguous+')',0),('1||('+ambiguous+')',1),
                             ('V(b)&&('+ambiguous+')',0),('V(b)?(('+ambiguous+')?1:2):3',3)]:
            with self.subTest(expr=expr):self.assertEqual(values(run_wave(expr)),[answer])
        for expr in [ambiguous,'1&&('+ambiguous+')','0||('+ambiguous+')','V(b)?(('+ambiguous+')?1:2):3']:
            with self.subTest(expr=expr),self.assertRaisesRegex(KernelError,'condition_precision'):
                run_wave(expr,selector=1)

    def test_original_affine_sign_is_not_separately_rounded(self):
        p=compile_expr('(V(u)+1e16>1e16)?1:0')
        result=solve(p,list(INPUTS),[[0,0,0,-1],[0,0,0,1]],kernel=KERNEL)
        self.assertEqual(values(result),[0,1])

    def test_selected_arm_keeps_the_original_voltage_error_budget(self):
        arm='1e16*(V(u)-0.3333333333333333)'
        self.assertEqual(values(run_wave('0?'+arm+':3')),[3])
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run_wave('1?'+arm+':3')

    def test_hidden_operators_and_unsupported_arms_reject_before_execution(self):
        hidden=['idt(V(u),0)','ddt(V(u))',"laplace_nd(V(u),'{1},'{1,1})",'transition(1,0,1,1)','sin(V(u))']
        invalid=['V(u)*V(u)','pow(V(u),2)','(V(y)>0?1:0)','(0*V(y)>0?1:0)',
                 '(V(u)*V(u)-V(u)*V(u)>0?1:0)','((V(u)>0?1:0)*V(b))']
        for bad in hidden+invalid:
            for expr in (f'1?{bad}:0',f'0?{bad}:0',f'1?0:{bad}',f'0&&({bad})',f'1||({bad})'):
                with self.subTest(expr=expr),self.assertRaises(CompileError):compile_expr(expr)
        for expr in ('V(u)*V(u)>0','pow(V(u),2)>0','V(y)>0','0*V(y)>0'):
            with self.subTest(expr=expr),self.assertRaises(CompileError):compile_expr(expr)
        for expr in ('0?(alias>0?1:0):0','1||(alias>0)'):
            with self.subTest(expr=expr),self.assertRaises(CompileError):
                compile_expr(expr,'alias=V(y);','real alias;')

    def test_events_initialization_parameters_and_waveform_contexts_do_not_expand(self):
        for prefix in ('@(initial_step) q=0;', '@(initial_step) q=0; @(timer(1,0,1e-12)) q=1;'):
            with self.subTest(prefix=prefix),self.assertRaises(CompileError):compile_expr('V(a)>0',prefix,'real q;')
        for decl in ('parameter real z=1?2:3;', 'parameter real z=1&&2;'):
            with self.subTest(decl=decl),self.assertRaises(CompileError):compile_expr('0',declarations=decl)
        with self.assertRaises(CompileError):compile_expr('idt(V(a)>0,0)')

    def test_equality_bitwise_nonfinite_and_unassigned_local_stay_rejected(self):
        for expr in ('V(a)==0','V(a)!=0','V(a)&V(b)','V(a)|V(b)','V(a)^V(b)','~V(a)',
                     '1?1e309:0','0?1e308*1e308:0','0?unknown:1'):
            with self.subTest(expr=expr),self.assertRaises(CompileError):compile_expr(expr)
        with self.assertRaises(CompileError):compile_expr('0?alias:1',declarations='real alias;')

    def test_local_aliases_functions_and_loop_arrays_keep_decision_structure(self):
        with self.assertRaises(CompileError):
            compile_expr('alias*V(b)','alias=V(a)>0;','real alias;')
        with self.assertRaises(CompileError):
            compile_expr('0?alias:0','alias=idt(V(u),0);','real alias;')
        function='analog function real sign_value; input x; real x; begin sign_value=x>0?2:-1; end endfunction'
        result=solve(compile_expr('sign_value(V(a))',declarations=function),list(INPUTS),
                     [[-1,0,0,0],[1,0,0,0]],kernel=KERNEL)
        self.assertEqual(values(result),[-1,2])
        prefix='for(i=0;i<2;i=i+1) z[i]=(V(a)>i)?1:0;'
        result=solve(compile_expr('z[0]+z[1]',prefix,'genvar i; real z[0:1];'),list(INPUTS),
                     [[0,0,0,0],[1,0,0,0],[2,0,0,0]],kernel=KERNEL)
        self.assertEqual(values(result),[0,1,2])
        result=solve(compile_expr('alias','alias=V(a)>0; if(alias>0) alias=3;','real alias;'),
                     list(INPUTS),[[-1,0,0,0],[1,0,0,0]],kernel=KERNEL)
        self.assertEqual(values(result),[0,3])

    def test_generated_wire_tree_budget_is_preserved(self):
        with self.assertRaisesRegex(CompileError,'(generated|expanded) IR .*limit'):
            compile_expr('!'*60+'V(a)')


if __name__=='__main__':unittest.main()
