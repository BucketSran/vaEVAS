"""Event conditions may sample a continuous transition through an affine net."""
GUARDS=['EVENT-CONDITIONS','TIMED-OPERATOR','COMPOSE']
import unittest
import math
from fractions import Fraction
from evas import KernelError,compile_sources,transient
from test_affine import model,instance,KERNEL

class TransitionEventConditions(unittest.TestCase):
    def test_independent_continuous_endpoints_keep_their_own_physical_curves(self):
        source=model('''@(initial_step) begin a=0; b=0; end
          @(cross(V(u,r)-1,+1,1e-9,1e-9)) begin a=1; b=1; end
          @(timer(0.5,0,1e-9)) begin a=2; b=2.0000000000000004; end
          V(z,r)<+transition(a,0,0.75,0.75);
          V(w,r)<+transition(b,0,0.75,0.75); V(y,r)<+V(z,r)+V(w,r);''',
          'real a,b; electrical z,w;')
        p=compile_sources({'end-checkpoints.va':source},[instance()])
        samples=[0,.4,.5,.75,1.,math.nextafter(7/6,0),math.nextafter(7/6,math.inf),1.5]
        r=transient(p,{'u':[[0,0],[1.5,4.5]]},samples,stop=1.5,max_step=1.5,kernel=KERNEL)
        def value(t,target):
            t=Fraction(t);target=Fraction(target)
            if t<Fraction(1,3):return Fraction(0)
            if t<Fraction(1,2):return (t-Fraction(1,3))/Fraction(3,4)
            return min(target,Fraction(2,9)+target*(t-Fraction(1,2))/Fraction(3,4))
        for t,row in zip(samples,r['solutions']):
            want=value(t,2.)+value(t,2.0000000000000004)
            self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],float(want),delta=1e-10)
    def test_distinct_internal_roots_without_an_intermediate_time_keep_refusal(self):
        source=model('''@(initial_step) begin s=0; a=0; b=0; end
          @(timer(1,0,1e-12)) s=1;
          @(cross(V(z,r)-0.3,+1,1e-12,1e-12)) a=1;
          @(cross(V(z,r)-0.30000000000000004,+1,1e-12,1e-12)) b=1;
          V(z,r)<+transition(s,0,0.25,0.25); V(y,r)<+a+2*b;''',
          'real s; integer a,b; electrical z;')
        p=compile_sources({'subulp-roots.va':source},[instance()])
        with self.assertRaisesRegex(KernelError,'event_resolution'):
            transient(p,{'u':[[0,0],[2,0]]},[0,2],stop=2,max_step=2,kernel=KERNEL)

    def test_history_target_cycle_keeps_explicit_refusal(self):
        source=model('''V(z,r)<+transition((V(w,r)>0.5)?1:0,0,0.25,0.25);
          V(w,r)<+transition((V(z,r)>0.5)?1:0,0,0.25,0.25);
          V(y,r)<+V(z,r);''',ports='u,y,z,w,r',directions='input u; output y; inout z,w,r;')
        p=compile_sources({'cycle.va':source},[instance(connections=dict(u='u',y='y',z='z',w='w',r='0'))])
        with self.assertRaisesRegex(KernelError,'dependency cycle'):
            transient(p,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_expanded_contribution_predicate_tracks_voltage_written_state(self):
        source=model('''@(initial_step) q=0;
          @(timer(0.25,0,1e-12)) q=V(u,r);
          V(z,r)<+q; V(w,r)<+transition(q,0,0.125,0.125);
          V(y,r)<+((V(z,r)>0.5)?2:0);''','real q; electrical w;',
          ports='u,y,z,r',directions='input u; output y; inout z,r;')
        p=compile_sources({'state-predicate.va':source},[instance(connections=dict(u='u',y='y',z='z',r='0'))])
        with self.assertRaisesRegex(KernelError,'same-time contribution predicate'):
            transient(p,{'u':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_adjacent_internal_roots_leave_a_valid_representative_between_them(self):
        source=model('''@(initial_step) begin s=0; t=0; a=0; b=0; end
          @(timer(1,0,1e-12)) s=1;
          @(timer(1.0000000000000002,0,1e-12)) t=1;
          @(cross(V(z,r)-0.3,+1,1e-12,1e-12)) a=1;
          @(cross(V(w,r)-0.3,+1,1e-12,1e-12)) b=1;
          V(z,r)<+transition(s,0,0.25,0.25);
          V(w,r)<+transition(t,0,0.25,0.25); V(y,r)<+a+2*b;''',
          'real s,t; integer a,b; electrical z,w;')
        p=compile_sources({'serial-roots.va':source},[instance()])
        root=Fraction(1)+Fraction(.3)/4;first=float(root)
        if Fraction(first)<root:first=math.nextafter(first,math.inf)
        second=math.nextafter(first,math.inf)
        self.assertLess(Fraction(first),root+Fraction(1.0000000000000002)-1)
        r=transient(p,{'u':[[0,0],[2,0]]},[0,first,second,2],stop=2,max_step=2,kernel=KERNEL)
        self.assertEqual([row['voltages'][p.nodes.index('y')] for row in r['solutions']],[0,1,3,3])
    def test_affine_transition_sample_uses_old_continuous_level_at_event(self):
        source=model('''@(initial_step) begin s=0; q=0; end
          @(timer(0.25,0,1e-12)) s=1;
          @(timer(0.375,0,1e-12)) begin
            if(V(z,r)>=1.5) q=2; else q=3;
          end V(z,r)<+1+transition(s,0,0.25,0.25); V(y,r)<+q;''','real s,q; electrical z;')
        p=compile_sources({'sample.va':source},[instance()])
        r=transient(p,{'u':[[0,0],[1,0]]},[0,.375,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([row['voltages'][p.nodes.index('y')] for row in r['solutions']],[0,2,2,2])
        self.assertEqual([row['voltages'][next(i for i,n in enumerate(p.nodes) if n not in ('0','u','y'))] for row in r['solutions']],[1,1.5,2,2])

    def test_direct_postevent_state_voltage_loop_keeps_refusal(self):
        source=model('''@(initial_step) s=0;
          @(timer(0.25,0,1e-12)) begin if(V(z,r)>0.5) s=1; else s=0; end
          V(z,r)<+s; V(y,r)<+s;''','real s; electrical z;')
        p=compile_sources({'loop.va':source},[instance()])
        with self.assertRaisesRegex(KernelError,'unsupported_condition'):
            transient(p,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_transition_threshold_retargets_another_transition_between_events(self):
        source=model('''@(initial_step) s=0;
          @(timer(0.25,0,1e-12)) s=1;
          V(z,r)<+transition(s,0,0.25,0.25);
          V(y,r)<+transition((V(z,r)>0.5)?2:0,0,0.125,0.125);''',
          'real s;',ports='u,y,z,r',directions='input u,z; output y; inout r;')
        p=compile_sources({'cascade.va':source},[instance(connections=dict(u='u',y='y',z='z',r='0'))])
        samples=[0,.25,.375,.40625,.4375,.5,.75,1]
        r=transient(p,{'u':[[0,0],[1,0]]},samples,stop=1,max_step=1,kernel=KERNEL)
        for row,want in zip(r['solutions'],[0,0,0,.5,1,2,2,2]):
            self.assertAlmostEqual(row['voltages'][p.nodes.index('y')],want,delta=1e-10)

    def test_event_reads_selected_internal_voltage_with_transition_forcing(self):
        source=model('''@(initial_step) begin s=0; q=0; end
          @(timer(0.25,0,1e-12)) s=1;
          @(timer(0.625,0,1e-12)) begin if(V(w,r)>0.25) q=2; else q=3; end
          V(z,r)<+transition(s,0,0.25,0.25);
          V(w,r)<+(V(u,r)>0.25 ? 1-V(z,r):0.5);
          V(y,r)<+q;''','real s,q; electrical z,w;')
        p=compile_sources({'conditional-read.va':source},[instance()])
        for u,want in [(0,2),(1,3)]:
            r=transient(p,{'u':[[0,u],[1,u]]},[0,.625,1],stop=1,max_step=1,kernel=KERNEL)
            self.assertEqual([row['voltages'][p.nodes.index('y')] for row in r['solutions']],[0,want,want])

    def test_internal_cross_and_target_cut_share_the_proved_root(self):
        source=model('''@(initial_step) begin s=0; q=0; end
          @(timer(0.25,0,1e-12)) s=1;
          @(cross(V(z,r)-0.3,+1,1e-12,1e-12)) q=q+1;
          V(z,r)<+transition(s,0,0.25,0.25);
          V(y,r)<+q+transition((V(z,r)>0.3)?2:0,0,0.125,0.125);''',
          'real s,q;',ports='u,y,z,r',directions='input u,z; output y; inout r;')
        p=compile_sources({'shared-root.va':source},[instance(connections=dict(u='u',y='y',z='z',r='0'))])
        sparse=[0,.324,.326,.375,.5,1]
        results=[]
        for samples in (sparse,sorted(set(sparse+[i/512 for i in range(513)]))):
            r=transient(p,{'u':[[0,0],[1,0]]},samples,stop=1,max_step=1,kernel=KERNEL)
            values=dict(zip(samples,[row['voltages'][p.nodes.index('y')] for row in r['solutions']]))
            for t in sparse:
                want=(0 if t<.325 else 1+2*min(1,(t-.325)/.125))
                self.assertAlmostEqual(values[t],want,delta=1e-10)
            self.assertEqual(sum(e['kind']=='cross' for e in r['transient']['events']),1)
            results.append(values)
        self.assertEqual([results[0][t] for t in sparse],[results[1][t] for t in sparse])
