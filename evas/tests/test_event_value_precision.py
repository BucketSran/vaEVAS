"""Event comparisons follow exact point arithmetic, not floating cancellation."""
GUARDS = ['EVENT-CONDITIONS', 'COMPOSE', 'LANG']
from fractions import Fraction as Q
import unittest
from evas import KernelError,compile_sources,transient
from test_affine import model,instance,KERNEL

class EventValuePrecision(unittest.TestCase):
    def test_integer_ratio_at_boundary_uses_exact_ir_coefficient(self):
        source=model('''@(initial_step) begin n=0; q=0; end
          @(timer(0.25,0,1e-12)) begin n=3; if (n/3.0>1) q=1; else q=2; end
          V(y,r)<+q;''','integer n; real q;')
        p=compile_sources({'boundary.va':source},[instance()])
        self.assertLess(3*Q(1/3),1)
        r=transient(p,{'u':[[0,0],[1,0]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([x['voltages'][p.nodes.index('y')] for x in r['solutions']],[0,2,2])

    def test_dependent_assignments_preserve_exact_local_cancellation(self):
        source=model('''@(initial_step) q=0;
          @(timer(0.25,0,1e-12)) begin a=0.3*V(u,r); b=a; e=b-a;
            if(e<0) q=1; else q=2; end V(y,r)<+q;''','real q,a,b,e;')
        p=compile_sources({'cancel.va':source},[instance()])
        r=transient(p,{'u':[[0,.7],[1,.7]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([x['voltages'][p.nodes.index('y')] for x in r['solutions']],[0,2,2])

    def test_correlated_values_survive_an_accepted_event_and_later_comparison(self):
        source=model('@(initial_step) begin a=0; b=0; q=0; end\n          @(timer(0.25,0,1e-12)) begin a=0.3*V(u,r); b=a; end\n          @(timer(0.5,0,1e-12)) begin e=b-a; if(e<0) q=1; else q=2; end\n          V(y,r)<+q;','real a,b,q,e;')
        p=compile_sources({'correlation.va':source},[instance()])
        r=transient(p,{'u':[[0,.7],[1,.7]]},[0,.375,.75,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([row['voltages'][p.nodes.index('y')] for row in r['solutions']],[0,0,2,2])

    def test_uncertain_input_cannot_seed_an_exact_value(self):
        source=model('''@(initial_step) q=0; @(timer(0.25,0,1e-12)) begin
          a=V(u,r); if(a>0.5) q=1; else q=2; end V(y,r)<+q;''','real q,a;')
        p=compile_sources({'unknown.va':source},[instance()])
        with self.assertRaisesRegex(KernelError,'event_condition'):
            transient(p,{'u':[[0,.5],[1,.5]]},[0,1],stop=1,max_step=1,
                      source_errors={'u':.01},kernel=KERNEL,vabstol=.1)
