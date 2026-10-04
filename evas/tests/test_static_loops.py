"""Finite genvar elaboration preserves additive relations and assignment order."""
GUARDS = ["LANG", "LIN", "COMPOSE", "TIMER", "CROSS", "EVENT-ORDER", "case:static_loop"]

import unittest
from pathlib import Path
from evas import CompileError, Instance, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


def compiled(body, declarations='genvar i; parameter real count=3;', instances=None):
    return compile_sources({'loop.va':model(body,declarations)},instances or [instance()])


def voltage(program, u=1, node='y'):
    r=solve(program,['u'],[[u]],kernel=KERNEL)
    return r['solutions'][0]['voltages'][r['nodes'].index(node)]


class StaticLoops(unittest.TestCase):
    def test_nested_event_controls_substitute_body_and_keep_instance_identity(self):
        p=compiled('''@(initial_step) n=0;
          for(i=0;i<count;i=i+1) for(j=0;j<2;j=j+1)
            @(timer(at(4*i+j))) n=10*i+j+1;
          @(timer(.875)) n=99; V(y,r)<+n;''',
          '''genvar i,j; parameter integer count=2; integer n;
          analog function real at; input x; real x;
            begin at=.125+.125*x; end endfunction''',
          [instance('a',connections={'u':'u','y':'a','r':'0'},parameters={'count':1}),
           instance('b',connections={'u':'u','y':'b','r':'0'})])
        times=[0,.125,.25,.625,.75,.875,1]
        result=transient(p,{'u':[[0,0],[1,1]]},times,stop=1,max_step=1,kernel=KERNEL)
        for name,expected in [('a',[0,1,2,2,2,99,99]),('b',[0,1,2,11,12,99,99])]:
            self.assertEqual([r['voltages'][p.nodes.index(name)] for r in result['solutions']],expected)
        self.assertEqual([e.origin.expansion for e in p.events],
                         [(('i',0),('j',0)),(('i',0),('j',1)),(),
                          (('i',0),('j',0)),(('i',0),('j',1)),(('i',1),('j',0)),(('i',1),('j',1)),()])
        self.assertEqual(len({(e.origin.instance,e.origin.line,e.origin.column,e.origin.expansion) for e in p.events}),8)

    def test_loop_event_or_uses_vector_guards_and_private_array_targets(self):
        p=compiled('''@(initial_step) begin n[0]=0; n[1]=0; end
          for(i=0;i<2;i=i+1) begin
            V(bus[i],r)<+V(u,r);
            @(cross(V(bus[i],r)-(i+1)*.25,1,1e-12,1e-9) or timer((i+1)*.25)) n[i]=i+1;
          end V(y,r)<+n[0]+10*n[1];''',
          'genvar i; electrical [0:1] bus; integer n[0:1];')
        result=transient(p,{'u':[[0,0],[1,1]]},[0,.25,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([r['voltages'][p.nodes.index('y')] for r in result['solutions']],[0,1,21,21])
        self.assertEqual([e['time'] for e in result['transient']['events']],[.25,.5])
        self.assertTrue(all(len(e['fired_triggers'])==2 for e in result['transient']['events']))

    def test_loop_guard_operators_have_distinct_call_sites(self):
        p=compiled('''@(initial_step) begin n[0]=0; n[1]=0; end
          for(i=0;i<2;i=i+1)
            @(cross(idt(V(u,r),0)-(i+1)*.25,1,1e-9,1e-8)) n[i]=i+1;
          V(y,r)<+n[0]+10*n[1];''','genvar i; integer n[0:1];')
        self.assertEqual([op.origin.expansion for op in p.operators],[(('i',0),),(('i',1),)])
        result=transient(p,{'u':[[0,1],[1,1]]},[0,.4,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([r['voltages'][p.nodes.index('y')] for r in result['solutions']],[0,1,21])
        for event,expected in zip(result['transient']['events'],[.25,.5],strict=True):
            self.assertAlmostEqual(event['time'],expected,delta=1e-9)

    def test_event_body_conditions_keep_their_existing_semantics(self):
        p=compiled('''@(initial_step) n=0;
          for(i=0;i<2;i=i+1) @(timer(.25+.5*i))
            if(V(u,r)>.5) n=i+10; else n=i+1;
          V(y,r)<+n;''','genvar i; integer n;')
        result=transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([r['voltages'][p.nodes.index('y')] for r in result['solutions']],[0,1,11])
        self.assertEqual(p.events[1].body[0].origin.expansion,(('i',1),))

    def test_loop_unrolling_does_not_prioritize_conflicting_writers(self):
        p=compiled('''@(initial_step) n=0;
          for(i=0;i<2;i=i+1) @(timer(.25)) n=i; V(y,r)<+n;''','genvar i; integer n;')
        with self.assertRaisesRegex(KernelError,'event_conflict'):
            transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_event_elaboration_rejects_runtime_activation_and_expansion_overflow(self):
        for body,message in [
            ('if(V(u,r)>0) for(i=0;i<2;i=i+1) @(timer(i+1)) n=i;', 'conditional'),
            ('for(i=0;i<2;i=i+1) @(initial_step) n=i;', 'initial_step'),
            ('for(i=0;i<2050;i=i+1) @(timer(i+1)) n=i;', 'statement budget'),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError,message):
                compiled('@(initial_step) n=0; '+body+' V(y,r)<+n;','genvar i; integer n;')

    def test_original_zoom_source_expands_every_clock_without_rewriting(self):
        source=Path(__file__).resolve().parents[2]/'benchmark/tasks/va03-zoom-timing/solution/dut.va'
        ports='RST S SAR RES INT CLK_SAR ZOOM CLK_ZOOM RST_ZOOM'.split()
        p=compile_sources({'dut.va':source.read_text()},[Instance('dut','CLOCK_VA',dict(zip(ports,ports)),{})])
        # Two edges for each of 1+4+28+4+32+32+128+32+32 pulses.
        self.assertEqual(len(p.events),586)
        self.assertEqual(len(p.operators),9)
        self.assertEqual(len({(e.origin.line,e.origin.column,e.origin.expansion) for e in p.events}),586)

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
