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
 'comparison_boundary':dict(lt='V(u)<0.5',le='V(u)<=0.5',gt='V(u)>0.5',ge='V(u)>=0.5'),
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
        expr='(V(a)>0.5 && V(b)>0.5)?1.25:-0.25'
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

    def test_active_exact_certificate_and_unselected_nested_decisions(self):
        ambiguous='V(u)>0.3333333333333333'
        self.assertGreater(F(1,3),F(float('0.3333333333333333')))
        for expr, answer in [('0&&('+ambiguous+')',0),('1||('+ambiguous+')',1),
                             ('V(b)&&('+ambiguous+')',0),('V(b)?(('+ambiguous+')?1:2):3',3)]:
            with self.subTest(expr=expr):self.assertEqual(values(run_wave(expr)),[answer])
        for expr in [ambiguous,'1&&('+ambiguous+')','0||('+ambiguous+')','V(b)?(('+ambiguous+')?1:2):3']:
            with self.subTest(expr=expr):
                self.assertEqual(values(run_wave(expr,selector=1)),[1])

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
        function='analog function real sign_value; input x; real x; begin sign_value=x>0?2:-1; end endfunction '
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

    def test_unused_function_arguments_and_overwritten_rhs_keep_source_checks(self):
        discard='analog function real discard; input x; real x; begin discard=1; end endfunction '
        overwritten='analog function real overwrite; input x; real x,tmp; begin tmp=x>0; tmp=1; overwrite=1; end endfunction '
        for expression in ('discard(V(y)>0)', '0?discard(V(y)>0):2',
                           'discard(V(u)*V(u)>0)', 'discard(0*V(y)>0)',
                           'discard((V(a)>0?1:0)*V(b))', '0?discard(V(u)*V(u)):2',
                           'overwrite(V(y))', 'overwrite(V(u)*V(u))'):
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_expr(expression,declarations=discard+overwritten)
        for declaration,prefix,expression in ((discard+' real alias;', 'alias=V(y);', 'discard(alias>0)'),
                                              (discard+' real z[0:0];','z[0]=V(y);','discard(z[0]>0)'),
                                              (discard+' genvar i;', '', 'discard(0*V(y)>0)')):
            if 'genvar' in declaration:
                prefix='for(i=0;i<1;i=i+1) V(y,r)<+discard(0*V(y)>0);'
                expression='0'
            with self.subTest(prefix=prefix), self.assertRaises(CompileError):
                compile_expr(expression,prefix,declaration)

    def test_discarded_decisions_remain_rejected_in_closed_contexts(self):
        discard='analog function real discard; input x; real x; begin discard=1; end endfunction '
        fixtures=[
            ('0','','parameter real k=discard(1>0);'),
            ('q','@(initial_step) q=discard(1>0);','real q;'),
            ('q','@(initial_step) q=0; @(timer(1,0,1e-12)) q=discard(1>0);','real q;'),
            ('q','@(initial_step) q=0; @(cross(discard(V(a)>0),1,1e-9,1e-8)) q=1;','real q;'),
            ('idt(discard(V(a)>0),0)','',''),
            ('0','for(i=discard(1>0);i<2;i=i+1) V(y,r)<+0;','genvar i;'),
            ('0','for(i=0;i<discard(1>0);i=i+1) V(y,r)<+0;','genvar i;'),
            ('0','for(i=0;i<2;i=i+discard(1>0)) V(y,r)<+0;','genvar i;'),
            ('0','','real z[0:discard(1>0)];'),
            ('z[discard(1>0)]','z[0]=0; z[1]=0;','real z[0:1];'),
        ]
        for expression,prefix,declaration in fixtures:
            with self.subTest(expression=expression,prefix=prefix,declaration=declaration),self.assertRaises(CompileError):
                compile_expr(expression,prefix,discard+declaration)
        source='`include "disciplines.vams"\nmodule m(a,y,r); input a; output y; inout r; electrical a,y,r; '+discard+' parameter real k=discard(1>0); analog begin V(y,r)<+k; end endmodule'
        with self.assertRaises(CompileError):
            compile_sources({'closed.va':source},[Instance('dut','m',{'a':'a','y':'y','r':'0'},{'k':2})])

    def test_validation_obligations_do_not_add_runtime_decisions(self):
        from evas.ir import Affine
        discard='analog function real discard; input x; real x; begin discard=1; end endfunction '
        overwrite='analog function real overwrite; input x; real x,tmp; begin tmp=x>0; overwrite=1; end endfunction '
        for expression in ('discard(V(a)>0)','overwrite(V(a))',
                           'discard(V(u)>0.3333333333333333)',
                           '0?discard(V(u)>0.3333333333333333):1'):
            with self.subTest(expression=expression):
                program=compile_expr(expression,declarations=discard+overwrite)
                if not expression.startswith('0?'):
                    self.assertIsInstance(program.contributions[0].rhs,Affine)
                sources={'u':[[0,0],[3,1]],'a':[[0,0],[3,0]],'b':[[0,0],[3,0]],'c':[[0,0],[3,0]]}
                result=transient(program,sources,[1.],stop=3,max_step=3,kernel=KERNEL,vabstol=1e-9,reltol=0)
                self.assertEqual(values(result),[1])
        # A discarded ordinary nonlinear argument stays valid outside decisions.
        self.assertEqual(values(solve(compile_expr('discard(V(u)*V(u))',declarations=discard),
                                    list(INPUTS),[[0,0,0,2]],kernel=KERNEL)),[1])

    def test_discarded_function_checks_preserve_pure_function_acceptance(self):
        function='analog function real discard; input x; real x,tmp; begin tmp=x+x; discard=1; end endfunction '
        def balanced(count):
            if count == 1: return 'V(u)'
            left = count // 2
            return '('+balanced(left)+'+'+balanced(count-left)+')'
        for leaves, layers in ((11,7),(12,7),(32,7),(1,20)):
            expression=balanced(leaves)
            for _ in range(layers): expression='discard('+expression+')'
            with self.subTest(leaves=leaves,layers=layers):
                program=compile_expr(expression,declarations=function)
                from evas.ir import Affine
                self.assertIsInstance(program.contributions[0].rhs,Affine)
                self.assertEqual(values(solve(program,list(INPUTS),[[0,0,0,2]],kernel=KERNEL)),[1])

    def test_real_function_expansion_still_uses_the_tree_budget(self):
        function='analog function real twice; input x; real x; begin twice=x+x; end endfunction '
        expression='V(a)'
        for _ in range(20): expression='twice('+expression+')'
        with self.assertRaisesRegex(CompileError,'budget'):
            compile_expr(expression,declarations=function)

    def test_caller_arithmetic_keeps_original_function_budget_boundaries(self):
        function=('analog function real twice; input x; real x; '
                  'begin twice=x+x; end endfunction '
                  'analog function real discard; input x; real x; '
                  'begin discard=1; end endfunction ')
        expression='V(u)'
        for _ in range(14): expression='twice('+expression+')'
        siblings='('+expression+'+'+expression+')'
        # Each function result is in budget. The ordinary parent previously
        # folded to affine IR, and must not acquire a function AST tree limit.
        for value,expected in ((siblings,65536),('discard('+siblings+')',1)):
            with self.subTest(value=value):
                program=compile_expr(value,declarations=function)
                self.assertEqual(values(solve(program,list(INPUTS),[[0,0,0,2]],kernel=KERNEL)),[expected])

    def test_sibling_function_checks_preserve_existing_acceptance(self):
        function=('analog function real discard; input x; real x,tmp; begin '
                  +'tmp=x+1;'*32+' discard=1; end endfunction ')
        def balanced(calls):
            if calls == 1: return 'discard(V(u))'
            left=calls//2
            return '('+balanced(left)+'+'+balanced(calls-left)+')'
        program=compile_expr(balanced(1600),declarations=function)
        self.assertEqual(values(solve(program,list(INPUTS),[[0,0,0,2]],kernel=KERNEL)),[1600])

    def test_discarded_decisions_cannot_escape_electrical_node_indices(self):
        source=('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; electrical [1:0] bus; '
                'analog function real discard; input x; real x,tmp; '
                'begin tmp=x+x; discard=1; end endfunction '
                'analog begin V(bus[0])<+0; V(bus[1])<+1; '
                'V(y)<+V(bus[discard(V(u)>0)]); end endmodule')
        with self.assertRaisesRegex(CompileError,'electrical bound/index must be instance-constant'):
            compile_sources({'node-index.va':source},[Instance('dut','m',{'u':'u','y':'y'})])
        # A non-decision constant-return index keeps the existing acceptance.
        program=compile_sources({'node-index.va':source.replace('discard(V(u)>0)','discard(1)')},
                                [Instance('dut','m',{'u':'u','y':'y'})])
        self.assertEqual(values(solve(program,['u'],[[2]],kernel=KERNEL)),[1])

    def test_function_checks_bind_independently_in_each_instance(self):
        source=('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; parameter real degree=1; '
                'analog function real discard; input x; real x; begin discard=1; end endfunction '
                'analog begin V(y)<+discard((V(u)>0)+pow(V(u),degree)); end endmodule')
        good=Instance('good','m',{'u':'u','y':'good_y'},{'degree':1})
        bad=Instance('bad','m',{'u':'u','y':'bad_y'},{'degree':2})
        compile_sources({'instances.va':source},[good])
        for instances in ([good,bad],[bad,good]):
            with self.subTest(order=[i.name for i in instances]),self.assertRaises(CompileError):
                compile_sources({'instances.va':source},instances)

    def test_nested_discard_keeps_decision_alias_and_context_checks(self):
        function='analog function real discard; input x; real x,tmp; begin tmp=x+x; discard=1; end endfunction '
        for expression,prefix,declaration in (
            ('V(y)>0','',''),
            ('alias*V(b)','alias=V(a)>0;','real alias;'),
            ('pow(alias,2)','alias=V(a)>0;','real alias;'),
            ('1>0','','parameter real k=VALUE;'),
        ):
            for _ in range(7): expression='discard('+expression+')'
            if 'VALUE' in declaration:
                declaration=declaration.replace('VALUE',expression)
                expression='k'
            with self.subTest(prefix=prefix,declaration=declaration),self.assertRaises(CompileError):
                compile_expr(expression,prefix,function+declaration)

    def test_transparent_function_result_retains_integer_checks(self):
        function='analog function real identity; input x; real x; begin identity=x; end endfunction '
        with self.assertRaisesRegex(CompileError,'integer parameter arithmetic'):
            compile_expr('0',declarations=function+'parameter integer n=identity(2)/2;')
        p=compile_expr('V(a)>n',declarations=function+'parameter integer n=identity(2);')
        self.assertEqual(values(solve(p,list(INPUTS),[[1,0,0,0],[3,0,0,0]],kernel=KERNEL)),[0,1])

    def test_bound_decision_aliases_cannot_hide_in_function_obligations(self):
        functions=('analog function real discard; input x; real x; begin discard=1; end endfunction '
                   'analog function real overwrite; input x; real x,tmp; begin tmp=x*x; tmp=1; overwrite=1; end endfunction '
                   'analog function real pair; input x,z; real x,z; begin pair=1; end endfunction ')
        for expression,prefix,declaration in (
            ('discard(alias*V(b))','alias=V(a)>0;','real alias;'),
            ('discard(pow(alias,2))','alias=V(a)>0;','real alias;'),
            ('discard(other*V(b))','alias=V(a)>0; other=alias;','real alias,other;'),
            ('overwrite(alias)','alias=V(a)>0;','real alias;'),
            ('discard(z[0]*V(b))','z[0]=V(a)>0;','real z[0:0];'),
            ('0','for(i=0;i<1;i=i+1) begin z[i]=V(a)>0; V(y,r)<+discard(pow(z[i],2)); end','real z[0:0]; genvar i;'),
            ('pair(alias,discard(V(b)*V(b)))','alias=V(a)>0;','real alias;'),
            ('transition(discard(alias),0,1,1)','alias=V(a)>0;','real alias;'),
        ):
            with self.subTest(expression=expression,prefix=prefix),self.assertRaises(CompileError):
                compile_expr(expression,prefix,functions+declaration)

    def test_bound_alias_controls_keep_plain_polynomials_and_skipped_precision(self):
        discard='analog function real discard; input x; real x; begin discard=1; end endfunction '
        result=solve(compile_expr('discard(alias*V(b))','alias=V(a);',discard+'real alias;'),
                     list(INPUTS),[[1,2,0,0]],kernel=KERNEL)
        self.assertEqual(values(result),[1])
        program=compile_expr('discard(other)','alias=V(u)>0.3333333333333333; other=alias;',
                             discard+'real alias,other;')
        from evas.ir import Affine
        self.assertIsInstance(program.contributions[0].rhs,Affine)
        sources={'u':[[0,0],[3,1]],'a':[[0,0],[3,0]],'b':[[0,0],[3,0]],'c':[[0,0],[3,0]]}
        self.assertEqual(values(transient(program,sources,[1.],stop=3,max_step=3,kernel=KERNEL,
                                         vabstol=1e-9,reltol=0)),[1])

    def test_generated_wire_tree_budget_is_preserved(self):
        with self.assertRaisesRegex(CompileError,'(generated|expanded) IR .*limit'):
            compile_expr('!'*60+'V(a)')


if __name__=='__main__':unittest.main()
