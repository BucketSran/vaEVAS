"""Preprocessing preserves model meaning, budgets and expanded history identities."""
GUARDS = ['LANG','COMPOSE','DYNAMICS','case:preprocessor']
import unittest
from evas import CompileError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


class Preprocessor(unittest.TestCase):
    def compile(self, source, headers=None):
        return compile_sources({'dut.va':source, **(headers or {})},[instance()])

    def test_object_function_and_nested_macros_have_hand_answers(self):
        p=self.compile('`define G 3\n`define SCALE(x) (`G*(x))\n'+model('V(y,r)<+`SCALE(V(u,r))+1;'))
        r=solve(p,['u'],[[2]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],7)

    def test_include_guards_relative_paths_and_conditionals(self):
        header='''`ifndef MY_G
`define MY_G
`define G 4
`endif
'''
        source='''`include "headers/g.vams"
`include "headers/g.vams"
`ifdef MY_G
`define ACTIVE `G
`else
unsupported $$$ code
`endif
'''+model('V(y,r)<+`ACTIVE*V(u,r);')
        p=self.compile(source, {'headers/g.vams':header})
        r=solve(p,['u'],[[.5]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],2)

    def test_else_if_undef_and_inactive_directives(self):
        source='''`define A 1
`undef A
`ifdef A
`include "missing.vams"
`define G 100
`elsif M_PI
`define G 2
`else
`define G 200
`endif
'''+model('V(y,r)<+`G;')
        p=self.compile(source)
        r=solve(p,['u'],[[0]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],2)

    def test_nested_same_function_macro_is_not_a_recursive_definition(self):
        p=self.compile('`define F(x) (2*(x))\n'+model('V(y,r)<+`F(`F(1));'))
        result=solve(p,['u'],[[0]],kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][p.nodes.index('y')],4)

    def test_continuations_header_order_and_predefined_line(self):
        source='`define F(x) ((x)+ \\\n1)\n`undef __VAMS_ENABLE__\n`ifdef __VAMS_ENABLE__\n'+model('V(y,r)<+`F(`__LINE__);')+'\n`endif\n'
        p=self.compile(source)
        r=solve(p,['u'],[[0]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],6)
        inventory={'header.vams':'`define G 3\n','dut.va':'`include "header.vams"\n'+model('V(y,r)<+`G;')}
        p=compile_sources(inventory,[instance()])
        r=solve(p,['u'],[[0]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],3)

    def test_macro_copies_get_distinct_histories_and_original_source_identity(self):
        source='`define TWICE(x) (idt((x),1)+idt(2*(x),2))\n'+model('V(y,r)<+`TWICE(V(u,r));')
        p=self.compile(source)
        self.assertEqual(len(p.operators),2)
        origins=[o.origin for o in p.operators]
        self.assertEqual({o.source for o in origins},{'dut.va'})
        self.assertEqual({o.line for o in origins},{2})
        self.assertNotEqual(origins[0].expansion,origins[1].expansion)
        r=transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        for t,row in zip([0,.5,1],r['solutions']):
            self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],3+1.5*t*t,delta=1e-9)

    def test_copied_history_argument_and_loop_macro_have_distinct_paths(self):
        for source, answer in (
            ('`define DUP(x) ((x)+(x))\n'+model('V(y,r)<+`DUP(idt(V(u,r),1));'), 3),
            ('`define INTEGRAL(x,ic) idt((x),(ic))\n'+model('for(i=0;i<2;i=i+1) V(y,r)<+`INTEGRAL((i+1)*V(u,r),i);','genvar i;'),2.5),
        ):
            p=self.compile(source)
            self.assertEqual(len(p.operators),2)
            self.assertNotEqual(p.operators[0].origin.expansion,p.operators[1].origin.expansion)
            r=transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
            self.assertAlmostEqual(r['solutions'][-1]['voltages'][p.nodes.index('y')],answer,delta=1e-9)

    def test_comments_do_not_create_macros_and_included_diagnostics_name_header(self):
        p=self.compile('// `define G 100\n`define G 2\n'+model('V(y,r)<+`G;'))
        result=solve(p,['u'],[[0]],kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][p.nodes.index('y')],2)
        with self.assertRaisesRegex(CompileError,r'bad.vams:1:'):
            self.compile('`include "bad.vams"\n',{'bad.vams':model('V(y,r)<+@;')})
        with self.assertRaisesRegex(CompileError,r'bad.vams:1:'):
            self.compile(model('V(y,r)<+1;', '`include "bad.vams"\n'),{'bad.vams':'parameter real x=V(u,r);'})

    def test_repeated_includes_own_distinct_integral_histories(self):
        source=model('\n`include "hist.vams"\n`include "hist.vams"\n')
        p=self.compile(source, {'hist.vams':'V(y,r)<+idt(V(u,r),1);'})
        for times in ([0,.5,1], [0,.125,.25,.5,.75,1]):
            r=transient(p,{'u':[[0,0],[1,1]]},times,stop=1,max_step=1,kernel=KERNEL)
            for t,row in zip(times,r['solutions']):
                # Two separate integrals of u=t, each with IC=1.
                self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],2+t*t,delta=1e-9)
        self.assertNotEqual(p.operators[0].origin.expansion,p.operators[1].origin.expansion)
        self.assertEqual({o.origin.source for o in p.operators},{'hist.vams'})

    def test_nested_includes_macros_and_loops_preserve_every_history(self):
        source='`define H(x,ic) idt((x),(ic))\n'+model(
            'for(i=0;i<2;i=i+1) begin\n`include "outer.vams"\nend','genvar i;')
        inventory={'dut.va':source, 'outer.vams':'`include "inner.vams"\n`include "inner.vams"\n',
                   'inner.vams':'V(y,r)<+`H((i+1)*V(u,r),i);'}
        for files in (inventory,dict(reversed(list(inventory.items())))):
            p=compile_sources(files,[instance()])
            identities={(o.origin.source,o.origin.line,o.origin.column,o.origin.expansion)
                        for o in p.operators}
            self.assertEqual(len(identities),4)
            r=transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
            for t,row in zip([0,.5,1],r['solutions']):
                # Two copies each of IC=0/gain=1 and IC=1/gain=2.
                self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],2+3*t*t,delta=1e-9)

    def test_repeated_includes_in_implicit_feedback_keep_distinct_histories(self):
        source=model('\n`include "hist.vams"\n`include "hist.vams"\n'
                     'V(y,r)<+-pow(V(y,r),2);')
        p=self.compile(source,{'hist.vams':'V(y,r)<+idt(.5+V(y,r),0);'})
        times=[0,.25,.5,1]
        r=transient(p,{'u':[[0,0],[1,0]]},times,stop=1,max_step=1,
                    kernel=KERNEL,vabstol=1e-10,reltol=0)
        # y+y^2=z0+z1; z0'=z1'=.5+y, z0(0)=z1(0)=0 => y=t.
        for t,row in zip(times,r['solutions']):
            self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],t,delta=1e-10)

    def test_missing_recursive_undefined_and_over_budget_inputs_are_diagnostic(self):
        sources=[
            ('`include "missing.vams"\n'+model('V(y,r)<+1;'),{}),
            ('`include "headers/constants.vams"\n'+model('V(y,r)<+1;'),{}),
            ('`include "loop.vams"\n'+model('V(y,r)<+1;'),{'loop.vams':'`include "loop.vams"\n'}),
            ('`define A `B\n`define B `A\n'+model('V(y,r)<+`A;'),{}),
            (model('V(y,r)<+`MISSING;'),{}),
            ('`ifdef A\n'+model('V(y,r)<+1;'),{}),
            ('`else\n'+model('V(y,r)<+1;'),{}),
            ('`define F(x,y) ((x)+(y))\n'+model('V(y,r)<+`F(1);'),{}),
            ('`define F(x) ((x)+(x))\n'+model('V(y,r)<+'+'`F('*20+'1'+')'*20+';'),{}),
        ]
        for source,headers in sources:
            with self.subTest(source=source[:40]),self.assertRaises(CompileError):
                self.compile(source,headers)
