"""Exact physical order through the actual transient controller."""
GUARDS = ["TIMER", "EVENT-ORDER", "CROSS", "DYNAMICS", "COMPOSE"]
from fractions import Fraction as Q
import unittest
from evas import compile_sources, transient
from test_affine import KERNEL, instance, model

class BoundedEventClosure(unittest.TestCase):
    def test_mixed_source_root_and_two_exact_clocks(self):
        source=model("""@(initial_step) begin n=0;k=0;j=0;end
@(timer(0.1,0.2,1e-6)) n=n+1;
@(cross(V(u,r),1,1e-6,1e-6)) k=k+1;
@(timer(0.30000000000000004,0,1e-6)) j=j+1;
V(y,r)<+n+k+j;""", "integer n,k,j;")
        root=Q(.4)*Q(.3)/(Q(.3)+Q(.1))
        physical=sorted([(Q(.1),0),(Q(.1)+Q(.2),0),(root,1),(Q(.30000000000000004),2)])
        baseline=None
        for times,step in [([0,.49],.49),([0,.15,.29,.3,.30000000000000004,.3000000000000001,.49],.012)]:
            result=transient(compile_sources({"mixed.va":source},[instance()]),{"u":[[0,-.3],[.4,.1],[.49,.1]]},times,stop=.49,max_step=step,kernel=KERNEL)
            self.assertEqual(result["transient"]["states"][-1],[2,1,1])
            events=result["transient"]["events"]
            self.assertEqual([e["event"] for e in events],[i for _,i in physical])
            self.assertTrue(all(a["time"]<b["time"] for a,b in zip(events,events[1:])))
            for query,state in zip(times,result["transient"]["states"]):
                t=Q(query)
                self.assertEqual(state,[int(t>=Q(.1))+int(t>=Q(.1)+Q(.2)),int(t>=root),int(t>=Q(.30000000000000004))])
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events

    def test_point_certified_held_timer_preserves_exact_order(self):
        source=model("""@(initial_step) begin a=0.1;p=0.2;n=0;k=0;j=0;end
@(timer(a,p,1e-6)) n=n+1;
@(timer(0.30000000000000004,0,1e-6)) k=k+1;
V(y,r)<+n+k+j;""", "real a,p;integer n,k,j;")
        result=transient(compile_sources({"held.va":source},[instance()]),{"u":[[0,0],[.31,0]]},[0,.31],stop=.31,max_step=.31,kernel=KERNEL)
        self.assertEqual(result["transient"]["states"][-1],[.1,.2,2,1,0])
        self.assertEqual([e["event"] for e in result["transient"]["events"]],[0,0,1])

    def hidden(self, polynomial=False, chain=False, tight=False):
        from evas import KernelError
        source=model("""@(initial_step) begin n=0;q=0;h=0;m=0;j=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
@(timer(0.30000000000000004,0,1e-6)) m=m+1;
V(z,r)<+idt(FLOW,0);
@(cross(V(z,r)-1e-18,1,TTOL,1e-6)) h=h+1;
EXTRA V(y,r)<+h+j;""", "integer n,q,h,m,j;electrical z;")
        flow="q" if not chain else "q+h"
        if polynomial:flow="("+flow+")*(1+V(z,r))*(1+V(z,r))"
        source=source.replace("FLOW",flow).replace("TTOL","1e-20" if tight else "1e-6").replace("EXTRA", "@(cross(V(z,r)-3e-18,1,1e-6,1e-6)) j=j+1;" if chain else "")
        program=compile_sources({"hidden.va":source},[instance()])
        baseline=None
        grids=[([0,.31],.31),([0,.15,.29,.3,.305,.31],.012),([0,.3,.30000000000000004,.3000000000000001,.30000000000000016,.3000000000000002,.31],.31)]
        for times,step in grids:
            if tight:
                with self.assertRaisesRegex(KernelError,"cross_ttol_unrepresentable"):
                    transient(program,{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=step,vabstol=1.,reltol=0.,kernel=KERNEL)
                continue
            result=transient(program,{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=step,vabstol=1.,reltol=0.,kernel=KERNEL)
            self.assertEqual(result["transient"]["states"][-1],[2,1,1,1,int(chain)])
            expected_order=[0,0,2,3,1] if chain else [0,0,2,1]
            events=result["transient"]["events"]
            self.assertEqual([e["event"] for e in events],expected_order)
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events
            elapsed=Q(.31)-Q(.1)-Q(.2)
            area=elapsed if not chain else 2*elapsed-Q(1e-18)/(1+Q(1e-18)) if polynomial else 2*elapsed-Q(1e-18)
            expected=area/(1-area) if polynomial else area
            z=result["solutions"][-1]["voltages"][result["nodes"].index("dut:z")]
            self.assertAlmostEqual(z,float(expected),delta=1e-10)
            if not chain:
                tau=Q(.1)+Q(.2)
                for query,state in zip(times,result["transient"]["states"]):
                    t=Q(query)
                    n=int(t>=Q(.1))+int(t>=tau)
                    self.assertEqual(state,[n,max(0,n-1),int(t>=tau+Q(1e-18)),int(t>=Q(.30000000000000004)),0])
    def test_hidden_root_is_inserted_before_the_next_physical_clock(self):self.hidden()
    def test_hidden_tight_time_tolerance_has_a_specific_refusal(self):self.hidden(tight=True)
    def test_local_affine_flow_change_exposes_a_second_causal_root(self):self.hidden(chain=True)
    def test_local_polynomial_flow_change_exposes_a_second_causal_root(self):self.hidden(polynomial=True,chain=True)

    def test_dense_causal_sequence_refuses_at_explicit_resource_bound(self):
        from evas import KernelError
        guards="".join(f"@(cross(V(z,r)-{k*1e-20!r},1,1e-6,1e-6)) begin end\n" for k in range(1,67))
        source=model("""@(initial_step) begin n=0;q=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
@(timer(0.30000000000000004,0,1e-6)) begin end
V(z,r)<+idt(q,0);"""+guards+"V(y,r)<+V(z,r);","integer n,q;electrical z;")
        with self.assertRaisesRegex(KernelError,"event_budget.*64 microevents"):
            transient(compile_sources({"resource.va":source},[instance()]),{"u":[[0,0],[.31,.31]]},[0,.31],stop=.31,max_step=.31,vabstol=1.,reltol=0.,kernel=KERNEL)

    def test_local_or_deduplicates_only_the_same_physical_root(self):
        source=model("""@(initial_step) begin n=0;q=0;h=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
V(z,r)<+idt(q,0);
@(cross(V(z,r)-1e-18,1,1e-6,1e-6) or cross(V(z,r)-1e-18,0,1e-6,1e-6) or cross(V(z,r)-3e-18,1,1e-6,1e-6)) h=h+1;
V(y,r)<+h;""", "integer n,q,h;electrical z;")
        baseline=None
        for times,step in [([0,.31],.31),([0,.15,.3,.305,.31],.012)]:
            result=transient(compile_sources({"or.va":source},[instance()]),{"u":[[0,0],[.31,0]]},times,stop=.31,max_step=step,vabstol=1.,reltol=0.,kernel=KERNEL)
            events=result["transient"]["events"]
            self.assertEqual([e["event"] for e in events],[0,0,1,1])
            self.assertEqual([len(e.get("fired_triggers", [e])) for e in events],[1,1,2,1])
            self.assertEqual(result["transient"]["states"][-1],[2,1,2])
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events

    def test_local_closure_preserves_source_driven_coupled_state(self):
        source=model("""@(initial_step) begin n=0;q=0;h=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
V(z,r)<+idt(q+1e-30*V(u,r),0); V(w,r)<+idt(q+V(u,r),0);
@(cross(V(z,r)-1e-18,1,1e-6,1e-6)) h=h+1;
V(y,r)<+h+V(w,r);""", "integer n,q,h;electrical z,w;")
        program=compile_sources({"nonautonomous.va":source},[instance()])
        baseline=None
        for times,step in [([0,.31],.31),([0,.3,.30000000000000004,.305,.31],.012)]:
            result=transient(program,{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=step,vabstol=1e-7,reltol=0.,kernel=KERNEL)
            self.assertEqual(result["transient"]["states"][-1],[2,1,1])
            events=result["transient"]["events"]
            self.assertEqual([e["event"] for e in events],[0,0,1])
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events
            for time,row in zip(times,result["solutions"]):
                self.assertAlmostEqual(row["voltages"][result["nodes"].index("dut:w")],time*time/2+float(max(Q(0),Q(time)-Q(.1)-Q(.2))),delta=1e-7)
            self.assertAlmostEqual(result["solutions"][-1]["voltages"][result["nodes"].index("y")],1+.31*.31/2+float(Q(.31)-Q(.1)-Q(.2)),delta=1e-7)

    def test_source_driven_local_closure_crosses_input_corner_and_restarts(self):
        source=model("""@(initial_step) begin n=0;q=0;h=0;m=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
@(timer(0.30000000000000004,0,1e-6)) m=m+1;
V(z,r)<+idt((q+h)*V(u,r),0); V(w,r)<+idt(V(u,r),0);
@(cross(V(z,r)-0.002,1,1e-9,1e-9)) h=h+1;
V(y,r)<+V(z,r)+V(w,r);""", "integer n,q,h,m;electrical z,w;")
        program=compile_sources({"forced-chain.va":source},[instance()])
        inputs=[[0,1],[.305,1.305],[.31,1.1]]
        tau=Q(.1)+Q(.2)
        # Independent piecewise trapezoid integration of the supplied PWL.
        def area(t):
            t=Q(t); total=Q(0)
            for (a,u),(b,v) in zip(inputs,inputs[1:]):
                a,b,u,v=map(Q,(a,b,u,v)); end=min(t,b)
                if end>a: total+=(end-a)*(u+(u+(v-u)*(end-a)/(b-a)))/2
            return total
        events=None
        for times,step in [([0,.3,.30000000000000004,.31],.31),([0,.3,.30000000000000004,.3000000000000001,.302,.305,.308,.31],.005)]:
            result=transient(program,{'u':inputs},times,stop=.31,max_step=step,vabstol=1e-7,reltol=0,kernel=KERNEL)
            self.assertEqual(result['transient']['states'][-1],[2,1,1,1])
            observed=result['transient']['events']
            self.assertEqual([e['event'] for e in observed],[0,0,1,2])
            if events is not None:self.assertEqual(events,observed)
            events=observed
            for t,row in zip(times,result['solutions']):
                integral=max(Q(0),area(t)-area(tau))
                z=integral if integral<Q(.002) else 2*integral-Q(.002)
                self.assertAlmostEqual(row['voltages'][result['nodes'].index('dut:w')],float(area(t)),delta=1e-7)
                self.assertAlmostEqual(row['voltages'][result['nodes'].index('dut:z')],float(z),delta=1e-7)

    def test_physical_phase_without_a_cross_trigger(self):
        source=model("""@(initial_step) begin n=0;q=0;m=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
@(timer(0.30000000000000004,0,1e-6)) m=m+1;
V(z,r)<+idt(q,0); V(y,r)<+q+10*m;""", "integer n,q,m;electrical z;")
        baseline=None
        for times,step in [([0,.31],.31),([0,.3,.3000000000000001,.31],.31),([0,.3,.30000000000000004,.3000000000000001,.31],.012)]:
            result=transient(compile_sources({"nocross.va":source},[instance()]),{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=step,vabstol=1.,reltol=0.,kernel=KERNEL)
            for query,state,solution in zip(times,result["transient"]["states"],result["solutions"]):
                t=Q(query);n=int(t>=Q(.1))+int(t>=Q(.1)+Q(.2));m=int(t>=Q(.30000000000000004))
                self.assertEqual(state,[n,max(0,n-1),m])
                self.assertAlmostEqual(solution["voltages"][result["nodes"].index("y")],max(0,n-1)+10*m,delta=1e-10)
            events=result["transient"]["events"]
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events

    def test_isolated_timer_representative_query_keeps_forced_history_supported(self):
        source=model("""@(initial_step) begin n=0;q=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
V(z,r)<+idt(q*V(u,r),0);V(y,r)<+V(z,r);""", "integer n,q;electrical z;")
        program=compile_sources({"forced-no-closure.va":source},[instance()])
        baseline=None
        for times in [[0,.31],[0,.3000000000000001,.31]]:
            result=transient(program,{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=.31,vabstol=1e-7,reltol=0,kernel=KERNEL)
            for time,row in zip(times,result["solutions"]):
                tau=Q(.1)+Q(.2)
                expected=max(Q(0),(Q(time)**2-tau**2)/2)
                self.assertAlmostEqual(row["voltages"][result["nodes"].index("y")],float(expected),delta=1e-7)
            events=result["transient"]["events"]
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events

    def test_overlap_with_physically_later_timer_does_not_force_local_history(self):
        source=model("""@(initial_step) begin n=0;q=0;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;end
@(timer(0.10000000000000006,0.20000000000000007,1e-6)) begin end
V(z,r)<+idt(q*V(u,r),0);V(y,r)<+V(z,r);""", "integer n,q;electrical z;")
        query=.3000000000000001
        # The successor enclosure overlaps the representative query, but
        # its exact physical occurrence is strictly later than the query.
        self.assertGreater(Q(.10000000000000006)+Q(.20000000000000007),Q(query))
        program=compile_sources({"later-overlap.va":source},[instance()])
        baseline=None
        for times in [[0,.31],[0,query,.31]]:
            result=transient(program,{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=.31,vabstol=1e-7,reltol=0,kernel=KERNEL)
            for time,row in zip(times,result["solutions"]):
                expected=max(Q(0),(Q(time)**2-(Q(.1)+Q(.2))**2)/2)
                self.assertAlmostEqual(row["voltages"][result["nodes"].index("y")],float(expected),delta=1e-7)
            events=result["transient"]["events"]
            if baseline is not None:self.assertEqual(events,baseline)
            baseline=events

    def test_rebuilt_held_deadline_does_not_use_stale_phase_permission(self):
        for action,trigger in [("next=0.30000000000000004+0.1*q;", "next,0,1e-6"), ("en=1-q;", "next,0,1e-6,en")]:
            for history_guard in ["", "@(cross(V(z,r)-1,1,1e-6,1e-6)) h=h+1;"]:
                source=model("""@(initial_step) begin n=0;q=0;m=0;h=0;en=1;next=0.30000000000000004;end
@(timer(0.1,0.2,1e-6)) begin n=n+1;q=n-1;ACTION end
@(timer(TRIGGER)) m=m+1;
V(z,r)<+idt(q*V(u,r),0);V(y,r)<+V(z,r);GUARD""", "integer n,q,m,h,en;real next;electrical z;").replace("ACTION",action).replace("TRIGGER",trigger).replace("GUARD",history_guard)
                program=compile_sources({"replanned-held.va":source},[instance()])
                baseline=None
                for times in [[0,.31],[0,.3000000000000001,.31]]:
                    result=transient(program,{"u":[[0,0],[.31,.31]]},times,stop=.31,max_step=.31,vabstol=1e-7,reltol=0,kernel=KERNEL)
                    self.assertEqual(result["transient"]["states"][-1][:4],[2,1,0,0])
                    for time,row in zip(times,result["solutions"]):
                        expected=max(Q(0),(Q(time)**2-(Q(.1)+Q(.2))**2)/2)
                        self.assertAlmostEqual(row["voltages"][result["nodes"].index("y")],float(expected),delta=1e-7)
                    events=result["transient"]["events"]
                    if baseline is not None:self.assertEqual(events,baseline)
                    baseline=events

    def test_query_inside_uncertified_held_clock_interval_is_refused(self):
        from evas import KernelError
        source=model("""@(initial_step) begin next=0.4;n=0;end
@(timer(0.01,0,1e-6)) next=0.1*V(u,r);
@(timer(next,0,1e-6)) n=n+1; V(y,r)<+n;""", "real next;integer n;")
        program=compile_sources({"ambiguous.va":source},[instance()])
        # The product Q(.1)*Q(.3) needs a non-point retained state interval.
        # Its interval overlaps Q(.03); no exact held-clock certificate exists.
        self.assertNotEqual(Q(.1)*Q(.3),Q(.03))
        for step in [.5,.012]:
            with self.assertRaisesRegex(KernelError,"output query cannot certify its physical event phase"):
                transient(program,{"u":[[0,.3],[.5,.3]]},[0,.03,.5],stop=.5,max_step=step,kernel=KERNEL)
        result=transient(program,{"u":[[0,.3],[.5,.3]]},[0,.031,.5],stop=.5,max_step=.5,kernel=KERNEL)
        self.assertEqual(result["transient"]["states"][-1][1],1)
