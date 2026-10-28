"""Passive instances observe certified same-time physical voltage through public API."""
GUARDS = ["EVENT-CONDITIONS", "EVENT-ORDER", "CROSS", "TIMER", "COMPOSE"]
import os
from pathlib import Path
import unittest

from evas import Instance, KernelError, compile_sources, transient

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('EVAS_PASSIVE_KERNEL', ROOT / 'rust_core/target/debug/evas-kernel'))


def program(observer_body, *, extra='', dut_rhs='q', trigger='cross(V(u)-0.5,1,0.001,0.001)'):
    dut = f'''`include "disciplines.vams"
module dut(u,y); input u; output y; electrical u,y; real q;
analog begin @(initial_step) q=0; @({trigger}) q=1; V(y)<+{dut_rhs}; end endmodule'''
    observer = f'''`include "disciplines.vams"
module obs(u,y); input u,y; electrical u,y; real seen,due; integer count;
analog begin @(initial_step) begin seen=0;due=100;count=0;end
@({trigger}) begin {observer_body} end
@(timer(due,0,0.001)) begin count=count+1; $display("due %d",count);end
{extra} end endmodule'''
    return compile_sources({'dut.va': dut, 'obs.va': observer}, [
        Instance('D','dut',{'u':'u','y':'y'}), Instance('M','obs',{'u':'u','y':'y'})])


def run(p, times=None, points=None):
    return transient(p, {'u': points or [[0,0],[1,1]]}, times or [0,.5,.75,1],
                     stop=1,max_step=1,kernel=KERNEL)


def final(result):
    return result['transient']['states'][-1]


class PassiveEvents(unittest.TestCase):
    def test_post_physical_voltage_order_display_and_own_timer(self):
        p=program('if(V(y)>0.5) begin seen=V(y); due=0.75; $display("seen %.2g",seen); end')
        r=run(p)
        self.assertEqual(final(r), [1,1,.75,1])
        text=[d['text'] for d in r['transient']['display_records']]
        self.assertEqual(text,['seen 1','due 1'])
        self.assertEqual(r['transient']['events'][0]['after'],[1,1,.75,0])

    def test_queries_do_not_accumulate_measurements(self):
        p=program('seen=V(y);count=count+1;due=0.75;')
        a=run(p)
        b=run(p,[0,.125,.25,.5,.625,.75,.875,1])
        self.assertEqual(final(a),[1,1,.75,2])
        self.assertEqual(final(a),final(b))
        self.assertEqual(a['transient']['events'],b['transient']['events'])

    def test_same_block_prior_assignment_controls_branch(self):
        p=program('seen=V(y);if(seen>0.5) begin seen=seen+2;due=0.75;end')
        self.assertEqual(final(run(p)),[1,3,.75,1])

    def test_own_contribution_preserves_physical_dependency_rejection(self):
        p=program('if(V(y)>0.5) seen=V(y);',extra='V(y)<+0*seen;')
        with self.assertRaisesRegex(KernelError,'event condition may depend on state through the voltage network'):
            run(p)

    def test_cross_block_state_reader_remains_rejected(self):
        p=program('seen=V(y);',extra='@(cross(V(u)-0.5,1,0.001,0.001)) if(seen>0.5) due=0.75;')
        with self.assertRaisesRegex(KernelError,'simultaneous event condition reads state written by another'):
            run(p)

    def test_condition_at_exact_cross_root_keeps_strict_comparison(self):
        p=program('if(V(y)>0.5) seen=1;',dut_rhs='V(u)')
        # y=u=.5 at the physical root, independently of its rounded time. The
        # passive body reads at tau+ (LRM 2.4 5.10.3.1), where y=u rises, so
        # the condition decidable just after the root fires: seen=1.
        result=run(p,points=[[0,.1],[1,.9]])
        self.assertEqual(final(result),[1,1,100,0])
        # IR33 records each instance's initial_step batch at t=0 first.
        self.assertEqual(len([e for e in result['transient']['events']
                              if e['kind']!='initial_step']),2)
        # Negative control: a falling observed node crosses the threshold from
        # above (u(t)=0.9-0.8t, root at t=0.5), so y<0.5 just after the root
        # and the body must not fire. Cross fires in either direction here.
        p=program('if(V(y)>0.5) seen=1;',dut_rhs='V(u)',
                  trigger='cross(V(u)-0.5,0,0.001,0.001)')
        falling=run(p,points=[[0,.9],[1,.1]])
        self.assertEqual(final(falling),[1,0,100,0])
        # The same root with the comparison reversed fires instead.
        p=program('if(V(y)<0.5) seen=1;',dut_rhs='V(u)',
                  trigger='cross(V(u)-0.5,0,0.001,0.001)')
        self.assertEqual(final(run(p,points=[[0,.9],[1,.1]])),[1,1,100,0])
        self.assertEqual(final(run(p,points=[[0,.9],[1,.1]]))[1],1)
        # Negative control: the observed node is not provably monotone. q jumps
        # at the root, so the pre-root trajectory derivative of y is no
        # certificate and the strict comparison stays refused.
        p=program('if(V(y)>0.5) seen=1;',dut_rhs='q-V(u)')
        with self.assertRaisesRegex(KernelError,'event_condition'):
            run(p,points=[[0,0],[1,1]])
        # A true input band at a fixed timer has no exact root identity.
        p=compile_sources({'band.va': '''`include "disciplines.vams"
module dut(u,y); input u; output y; electrical u,y;
analog begin V(y)<+V(u); end endmodule
module obs(y); input y; electrical y; real seen;
analog begin @(initial_step) seen=0;
@(timer(0.5,0,0.001)) if(V(y)>0.5) seen=1;
end endmodule'''}, [Instance('D','dut',{'u':'u','y':'y'}),
                    Instance('M','obs',{'y':'y'})])
        with self.assertRaisesRegex(KernelError,'event_condition'):
            transient(p,{'u':[[0,.5],[1,.5]]},[0,1],stop=1,max_step=1,
                      source_errors={'u':1e-12},kernel=KERNEL)

    def test_nonrepresentable_root_retains_tau_sample_interval(self):
        p=program('seen=V(y);due=$abstime+0.25;',dut_rhs='q+V(u)',
                  trigger='cross(V(u)-1,1,0.001,0.001)')
        r=run(p,points=[[0,0],[1,3]])
        event=r['transient']['events'][0]
        self.assertAlmostEqual(event['after'][1],2,places=12)
        self.assertAlmostEqual(event['after'][2],1/3+.25,places=12)
        self.assertEqual(final(r)[3],1)

    def test_repeated_integer_writes_keep_local_order(self):
        p=program('count=count+1;count=count+1;seen=V(y);')
        self.assertEqual(final(run(p)),[1,1,100,2])

    def test_two_direct_operator_guards_preserve_indices_with_and_without_observer(self):
        physical_source = '`include "disciplines.vams"\nmodule dut(u,y);input u;output y;electrical u,y;real q;\nanalog begin @(initial_step)q=0;\nV(y)<+q+idt(1,0);\n@(cross(idt(1,0)-0.5,1,0.001,0.001)) if(V(u)>0.1) q=1;\n@(cross(idt(1,0)-0.75,1,0.001,0.001)) if(V(u)>0.1) q=2;\nend endmodule'
        observer_source = '''module obs(u,y);input u,y;electrical u,y;real seen;
analog begin @(initial_step) seen=0;
@(timer(0.5,0.25,0.001)) if(V(y)>1) seen=V(y);end endmodule'''
        for observer in [False,True]:
            with self.subTest(observer=observer):
                instances=[Instance('D','dut',{'u':'u','y':'y'})]
                if observer:
                    instances.append(Instance('M','obs',{'u':'u','y':'y'}))
                p=compile_sources({'no-observer.va':physical_source+'\n'+(observer_source if observer else '')},instances)
                r=run(p,[0,.25,.5,.75,1],points=[[0,1],[1,1]])
                self.assertEqual([row[0] for row in r['transient']['states']],[0,0,1,2,2])
                y=r['nodes'].index('y')
                self.assertEqual([row['voltages'][y] for row in r['solutions']],[0,.25,1.5,2.75,3])
                if observer:
                    self.assertEqual([row[1] for row in r['transient']['states']],[0,0,1.5,2.75,3])

    def test_operator_zero_is_not_the_constant_column_of_passive_root_identity(self):
        source = '`include "disciplines.vams"\nmodule dut(u,y);input u;output y;electrical u,y;real q;\nanalog begin @(initial_step)q=0;@(cross(idt(1,0)-0.5,1,0.001,0.001))q=1;V(y)<+q;end endmodule\nmodule obs(u,y);input u,y;electrical u,y;real seen;\nanalog begin @(initial_step)seen=0;@(timer(0.5,0,0.001))begin if(V(u)-V(u)>-1)seen=1;else seen=-1;$display("seen %g",seen);end end endmodule'
        p=compile_sources({'operator-root.va':source},[Instance('D','dut',{'u':'u','y':'y'}),Instance('M','obs',{'u':'u','y':'y'})])
        r=run(p,[0,.5,1],points=[[0,1],[1,1]])
        self.assertEqual(final(r),[1,1])
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['seen 1'])
