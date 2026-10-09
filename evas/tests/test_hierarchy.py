"""Hierarchy is elaborated into one shared relation program with private identities."""
GUARDS = ['LANG','COMPOSE','DYNAMICS','case:hierarchy']
import unittest
from evas import CompileError, compile_sources, solve, transient
from test_affine import KERNEL, instance

LEAF = '''`include "disciplines.vams"
module gain(u,y,r); input u; output y; inout r; electrical u,y,r;
parameter real g=2; analog begin V(y,r)<+g*V(u,r); end endmodule'''


def top(items, declarations=''):
    return f'`include "disciplines.vams"\nmodule top(u,y,r); input u; output y; inout r; electrical u,y,r; {declarations} {items} endmodule'


class Hierarchy(unittest.TestCase):
    def compile(self, source, extra=None, instances=None):
        return compile_sources({'top.va':source,'gain.va':LEAF,**(extra or {})},instances or [instance(module='top')])

    def test_named_and_positional_connections_share_the_same_equation_program(self):
        for connections in ('(u,y,r)', '(.r(r),.y(y),.u(u))'):
            p=self.compile(top('gain #(.g(G)) a'+connections+';', 'parameter real G=3;'))
            r=solve(p,['u'],[[.5]],kernel=KERNEL)
            self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],1.5)
            self.assertEqual(p.contributions[0].origin.instance,'dut/a')

    def test_parent_and_child_contributions_are_solved_together(self):
        p=self.compile(top('gain a(u,z,r); analog begin V(y,r)<+V(z,r)+1; end', 'electrical z;'))
        r=solve(p,['u'],[[.5]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],2)
        self.assertIn('dut:z',p.nodes)

    def test_nested_parameter_overrides_and_internal_nets(self):
        middle='''`include "disciplines.vams"
module middle(u,y,r); input u; output y; inout r; electrical u,y,r,z;
        parameter real g=1; gain #(.g(g)) a(u,z,r); gain #(.g(0.5)) b(z,y,r); endmodule'''
        p=self.compile(top('middle #(.g(4)) m(u,y,r);'),{'middle.va':middle})
        r=solve(p,['u'],[[2]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],4)
        self.assertEqual({c.origin.instance for c in p.contributions},{'dut/m/a','dut/m/b'})

    def test_hierarchical_histories_and_state_are_private(self):
        integral='''`include "disciplines.vams"
module integral(u,y,r); input u; output y; inout r; electrical u,y,r;
        parameter real g=1; parameter real ic=0; analog begin V(y,r)<+idt(g*V(u,r),ic); end endmodule'''
        p=self.compile(top('integral #(.g(1),.ic(2)) a(u,za,r); integral #(.g(3),.ic(4)) b(u,zb,r); '
                           'analog begin V(y,r)<+V(za,r)+V(zb,r); end','electrical za,zb;'), {'integral.va':integral})
        self.assertEqual({o.origin.instance for o in p.operators},{'dut/a','dut/b'})
        r=transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        for t,row in zip([0,.5,1],r['solutions']):
            self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],6+2*t*t,delta=1e-9)

    def test_bad_hierarchy_is_rejected_before_lowering(self):
        for items, extra in [
            ('missing a(u,y,r);',{}),
            ('top a(u,y,r);',{}),
            ('gain a(u,y);',{}),
            ('gain a(.u(u),.y(y),.missing(r));',{}),
            ('gain a(.u(u),.u(u),.y(y),.r(r));',{}),
            ('gain a(v,y,r);',{}),
            ('gain #(.missing(1)) a(u,y,r);',{}),
            ('gain #(.g(V(u,r))) a(u,y,r);',{}),
            ('gain a(u,y,r); gain a(u,y,r);',{}),
        ]:
            with self.subTest(items=items),self.assertRaises(CompileError):
                self.compile(top(items),extra)

    def test_generated_and_explicit_instance_identity_collision_rejects(self):
        with self.assertRaisesRegex(CompileError,'identity'):
            self.compile(top('gain a(u,y,r);'),instances=[instance('dut',module='top'),instance('dut/a',module='gain')])

    def test_ordered_overrides_multiple_instances_and_modules_in_one_file(self):
        source=top('gain #(3) a(u,za,r),b(u,zb,r); analog begin V(y,r)<+V(za,r)+V(zb,r); end', 'electrical za,zb;')
        p=compile_sources({'combined.va': source+'\n'+LEAF},[instance(module='top')])
        r=solve(p,['u'],[[.5]],kernel=KERNEL)
        self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')],3)

    def test_hierarchical_event_states_settle_in_one_atomic_batch(self):
        counter='''`include "disciplines.vams"
module counter(u,y,r); input u; output y; inout r; electrical u,y,r;
        parameter real ic=1; integer n;
        analog begin @(initial_step) n=ic; @(timer(0.25,0.25,1e-9)) n=n+1; V(y,r)<+n; end endmodule'''
        p=self.compile(top('counter #(.ic(1)) a(u,za,r); counter #(.ic(5)) b(u,zb,r); '
                           'analog begin V(y,r)<+V(za,r)+V(zb,r); end','electrical za,zb;'),{'counter.va':counter})
        for grid in ([0,.5,1],[0,.125,.25,.5,.75,1]):
            r=transient(p,{'u':[[0,0],[1,0]]},grid,stop=1,max_step=1,kernel=KERNEL)
            self.assertEqual(r['transient']['states'][-1],[5,9])
            self.assertEqual(len(r['transient']['events']),8)
            for t,row in zip(grid,r['solutions']):
                self.assertEqual(row['voltages'][p.nodes.index('y')],6+2*int(4*t))

    def test_instance_tree_budgets_apply_before_ir_lowering(self):
        with self.assertRaisesRegex(CompileError,'budget'):
            self.compile(top(' '.join(f'gain a{i}(u,y,r);' for i in range(4096))))
        modules={f'm{i}.va':top(f'm{i+1} child(u,y,r);').replace('module top(',f'module m{i}(')
                 for i in range(65)}
        modules['m65.va']=LEAF.replace('module gain(', 'module m65(')
        with self.assertRaisesRegex(CompileError,'budget'):
            compile_sources(modules,[instance(module='m0')])
