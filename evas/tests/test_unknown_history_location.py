"""Two independent verdicts for the original location-reference controls.

The original VA, requests and budgets are unchanged. Freeze30 preserves the
previous rejection assertions and their actual red results. These successor
checks distinguish physical execution e from the extra mathematical-root
answer; an unknown root answer never passes by default.
"""
GUARDS = ["CROSS", "DYNAMICS", "COMPOSE"]
import math
import unittest
from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL
from fractions import Fraction as F
from reference_verdicts import LayeredVerdict, Verdict, assess_layers


def execution(result, kind='cross', index=0):
    return F([e for e in result['transient']['events'] if e['kind']==kind][index]['time'])


def assert_layers(test, result, physical, root, budget, root_verdict=Verdict.PASS):
    verdict=assess_layers(result, physical_expected=physical, root_expected=root, budget=budget)
    test.assertEqual(verdict,LayeredVerdict(Verdict.PASS,root_verdict))



def program(body, *, kind='real', flow='q', guard='pow(V(u),2)-2'):
    source = f'''`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;{kind} q;
analog begin @(initial_step)q=0;
@(cross({guard},1,1e-3,1e-3)){body}
V(y)<+idt({flow},0);end endmodule'''
    return compile_sources({'location.va': source}, [Instance('M','dut',{'u':'u','y':'y'})])


def run(p, budget=1e-10, times=None, stop=2):
    return transient(p, {'u': [[0,0],[stop,stop]]}, times or [0,stop],
                     stop=stop, max_step=.1, vabstol=budget, reltol=0, kernel=KERNEL)


class UnknownHistoryLocation(unittest.TestCase):
    def test_unconditional_sample_history_retains_root_location_budget(self):
        p=program('q=V(u);')
        r=run(p,2e-5,[0,2,10],10)
        e=execution(r)
        assert_layers(self,r,e*(F(10)-e),10*math.sqrt(2)-2,2e-5)
        expected=10*math.sqrt(2)-2
        self.assertLessEqual(abs(r['solutions'][-1]['voltages'][r['nodes'].index('y')]-expected),2e-5)
        dense=run(p,2e-5,[0,1,math.sqrt(2),1.5,2,5,10],10)
        self.assertEqual(r['transient']['events'],dense['transient']['events'])
        self.assertEqual(r['solutions'][-1],dense['solutions'][-1])

    def test_independent_branch_distinguishes_execution_and_root_answers(self):
        # The binary64 threshold lies strictly above sqrt(2), below the first
        # certifiable post-root callback. Its right-limit branch is q=1;
        # actual e selects q=2. Point consistency cannot certify their error.
        p=program('if(V(u)>1.4142135623730951)q=2;else q=1;',kind='integer')
        result=run(p)
        assert_layers(self,result,2*(F(2)-execution(result)),2-math.sqrt(2),1e-10,Verdict.FAIL)

    def test_direct_branch_distinguishes_execution_and_root_answers(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;integer q;
analog begin @(initial_step)q=0;
@(cross(pow(V(u),2)-2,1,1e-3,1e-3))if(V(u)>1.4142135623730951)q=2;else q=1;
V(y)<+q;end endmodule"""
        p=compile_sources({'direct-location.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        result=run(p)
        assert_layers(self,result,2,1,1e-10,Verdict.FAIL)

    def test_inherited_sample_error_survives_later_history_amplification(self):
        from fractions import Fraction as F
        source = """`include "disciplines.vams"
module dut(u,v,y);input u,v;output y;electrical u,v,y;real q;
analog begin @(initial_step)q=0;@(timer(0.5,0,0))q=V(v)-1;
@(cross(pow(V(u),2)-2,1,1e-5,1e-4))q=1e16*q;V(y)<+idt(q,0);end endmodule"""
        p=compile_sources({'inherited-location.va':source},[Instance('M','dut',{'u':'u','v':'v','y':'y'})])
        q0=(F(math.nextafter(1,math.inf))-1)/6
        self.assertGreater(float(q0)*((math.sqrt(2)-.5)+1e16*(3-math.sqrt(2))),.5)
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            transient(p,{'u':[[0,0],[3,3]],'v':[[0,1],[3,math.nextafter(1,math.inf)]]},[0,3],
                      stop=3,max_step=.1,vabstol=1e-7,reltol=0,kernel=KERNEL)
        self.assertEqual(assess_layers(None,physical_expected=None,root_expected=None,budget=1e-7),
                         LayeredVerdict(Verdict.REJECTED,Verdict.UNKNOWN))

    def test_stable_independent_branch_uses_original_math_budget(self):
        r=run(program('if(V(u)>1.41425)q=2;else q=1;',kind='integer'))
        assert_layers(self,r,F(2)-execution(r),2-math.sqrt(2),1e-10)
        y=r['solutions'][-1]['voltages'][r['nodes'].index('y')]
        self.assertLessEqual(abs(y-(2-math.sqrt(2))),1e-10)

    def test_matching_strict_guard_uses_certified_right_side_for_location(self):
        r=run(program('if(V(u)>0.5)q=1;else q=2;',guard='V(u)-0.5'))
        e=r['transient']['events'][0]
        assert_layers(self,r,F(2)-execution(r),1.5,1e-10)
        self.assertGreater(e['time'],.5)
        self.assertEqual(e['after'],[1])
        self.assertLessEqual(abs(r['solutions'][-1]['voltages'][r['nodes'].index('y')]-1.5),1e-10)

    def test_independent_held_clock_preserves_family_and_exact_occurrence(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;real q,clock;
analog begin @(initial_step)begin q=0;clock=1.75;end
@(cross(V(u)*V(u)-2,1,1e-3,1e-3))q=V(u);
@(timer(clock))q=2*q;V(y)<+idt(q,0);end endmodule"""
        p=compile_sources({'uniform-clock.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        r=run(p,1e-8)
        e=execution(r)
        assert_layers(self,r,e*(F(9,4)-e),2.25*math.sqrt(2)-2,1e-8)
        self.assertEqual(next(e['time'] for e in r['transient']['events'] if e['kind']=='timer'),1.75)
        y=r['solutions'][-1]['voltages'][r['nodes'].index('y')]
        self.assertLessEqual(abs(y-(2.25*math.sqrt(2)-2)),1e-8)

    def test_sensitive_held_clock_has_separate_execution_and_root_verdicts(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;real clock,x;
analog begin @(initial_step)begin clock=10;x=0;end
@(cross(V(u)*V(u)-2,1,1e-3,1e-3))clock=$abstime+0.25;
@(timer(clock))x=1;V(y)<+idt(x,0);end endmodule"""
        p=compile_sources({'dependent-clock.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        result=run(p,1e-8)
        assert_layers(self,result,F(2)-execution(result,'timer'),1.75-math.sqrt(2),1e-8)

    def test_second_location_window_retains_the_first_sample_error(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;real q;
analog begin @(initial_step)q=0;
@(cross(V(u)*V(u)-2,1,1e-3,1e-3))q=q+V(u);
@(cross(V(u)*V(u)-3,1,1e-3,1e-3))q=q+V(u);
V(y)<+idt(q,0);end endmodule"""
        p=compile_sources({'two-windows.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        r=run(p,1e-8)
        y=r['solutions'][-1]['voltages'][r['nodes'].index('y')]
        self.assertLessEqual(abs(y-(2*(math.sqrt(2)+math.sqrt(3))-5)),1e-8)
        es=[execution(r,index=i) for i in [0,1]]
        assert_layers(self,r,sum(e*(F(2)-e) for e in es),
                      2*(math.sqrt(2)+math.sqrt(3))-5,1e-8)
        self.assertEqual(len(r['transient']['events']),2)

    def test_dependent_future_cross_preserves_physical_calendar_and_root_answer(self):
        source = """`include "disciplines.vams"
module dut(u,y,n);input u;output y,n;electrical u,y,n;real q;integer count;
analog begin @(initial_step)begin q=0;count=0;end
@(cross(V(u)*V(u)-2,1,1e-3,1e-3))q=V(u);
V(y)<+idt(q,0);@(cross(V(y)-0.1,1,1e-6,1e-8))count=count+1;
V(n)<+count;end endmodule"""
        p=compile_sources({'dependent-guard.va':source},[Instance('M','dut',{'u':'u','y':'y','n':'n'})])
        result=run(p,1e-8)
        e=execution(result)
        assert_layers(self,result,e*(F(2)-e),2*math.sqrt(2)-2,1e-8)
        self.assertEqual(len(result['transient']['events']),2)

    def test_unattainable_history_budget_is_not_accepted_after_full_contraction(self):
        p=program('if(V(u)>1.41425)q=2;else q=1;',kind='integer')
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(p,1e-20)
        self.assertEqual(assess_layers(None,physical_expected=None,root_expected=None,budget=1e-20),
                         LayeredVerdict(Verdict.REJECTED,Verdict.UNKNOWN))


class LocationOccurrenceDependencies(unittest.TestCase):
    def test_node_mediated_clock_keeps_two_independent_answers(self):
        # The timer's branch is sensitive to a threshold strictly between the
        # ideal root-derived clock and actual-e-derived clock. Alias spelling,
        # depth, and an explicit zero term cannot hide its continuous consumer.
        for forcing in ['V(aux)', 'V(other)', 'V(deep)', 'V(deep)+0*V(aux)']:
            with self.subTest(forcing=forcing):
                source = f'''`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y,aux,other,deep;real clock,x;
analog begin @(initial_step)begin clock=10;x=0;end
@(cross(pow(V(u),2)-2,1,1e-3,1e-3))clock=$abstime+0.25;
@(timer(clock))if(V(u)>1.6642135623730951)x=2;else x=1;
V(aux)<+x;V(other)<+x;V(deep)<+V(aux);V(y)<+idt({forcing},0);
end endmodule'''
                p=compile_sources({'aliased-clock.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
                result=run(p,1e-8)
                assert_layers(self,result,2*(F(2)-execution(result,'timer')),
                              1.75-math.sqrt(2),1e-8,Verdict.FAIL)

    def test_time_varying_timer_predicate_with_constant_rhs_is_sensitive(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;real clock,x;
analog begin @(initial_step)begin clock=10;x=0;end
@(cross(pow(V(u),2)-2,1,1e-3,1e-3))clock=$abstime+0.25;
@(timer(clock))if(V(u)>1.6642135623730951)x=2;else x=1;
V(y)<+x;end endmodule"""
        p=compile_sources({'clock-predicate.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        result=run(p,1e-8)
        assert_layers(self,result,2,1,1e-8,Verdict.FAIL)

    def test_cross_only_occurrence_keeps_two_independent_answers(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y;real q,x;
analog begin @(initial_step)begin q=10;x=0;end
@(cross(pow(V(u),2)-2,1,1e-3,1e-3))q=V(u)+0.25;
@(cross(V(u)-q,1,1e-3,1e-3))if(V(u)>1.6642135623730951)x=2;else x=1;
V(y)<+idt(x,0);end endmodule"""
        p=compile_sources({'guard-only-clock.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        result=run(p,1e-8)
        assert_layers(self,result,2*(F(2)-execution(result,index=1)),
                      1.75-math.sqrt(2),1e-8,Verdict.FAIL)

    def test_dynamic_guard_external_sample_gain_requires_location_certificate(self):
        source = """`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y,x;real q;
analog begin @(initial_step)q=0;V(x)<+idt(V(u),0);
@(cross(V(x)-1,1,1e-3,1e-3))q=V(u);V(y)<+1048576*q;
end endmodule"""
        p=compile_sources({'dynamic-location-gain.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
        for budget in [1e-8,1e-9,1e-10]:
            with self.subTest(budget=budget):
                result=run(p,budget,[0,1.5,2])
                assert_layers(self,result,1048576*execution(result),
                              1048576*math.sqrt(2),budget,Verdict.FAIL)

    def test_dynamic_guard_constant_forcing_onset_has_location_error(self):
        # Constant sampled values still move the start of an integral. The
        # ideal y(2)=G*(2-sqrt(2)) cannot use actual e as an exact root.
        for gain in [1,1048576]:
            with self.subTest(gain=gain):
                source=f'''`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y,x;real q;
analog begin @(initial_step)q=0;V(x)<+idt(V(u),0);
@(cross(V(x)-1,1,1e-3,1e-3))q=1;V(y)<+{gain}*idt(q,0);
end endmodule'''
                p=compile_sources({'dynamic-onset.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
                result=run(p,1e-8)
                assert_layers(self,result,gain*(F(2)-execution(result)),
                              gain*(2-math.sqrt(2)),1e-8,Verdict.FAIL)

    def test_terminal_local_sample_keeps_original_output_budget(self):
        for gain,budget in [(1,1e-10),(1099511627776,1e-25)]:
            with self.subTest(gain=gain,budget=budget):
                source=f'''`include "disciplines.vams"
module dut(u,y);input u;output y;electrical u,y,z;integer n,q;real s;
analog begin @(initial_step)begin n=0;q=0;s=0;end
@(timer(0.1,0.2,1e-6))begin n=n+1;q=n-1;end
V(z)<+idt(q,0);@(cross(V(z)-1e-18,1,1e-6,1e-6))s=V(z);
V(y)<+{gain}*s;end endmodule'''
                p=compile_sources({'local-location.va':source},[Instance('M','dut',{'u':'u','y':'y'})])
                if gain==1:
                    result=run(p,budget,[0,.31],.31)
                    y=result['solutions'][-1]['voltages'][result['nodes'].index('y')]
                    self.assertGreater(y,1e-18)
                    self.assertLessEqual(abs(y-1e-18),budget)
                    # The public float representative does not expose exact
                    # local execution delta. Do not invent an independent-e
                    # oracle from that representative or from sampled state.
                    self.assertEqual(assess_layers(result,physical_expected=None,
                        root_expected=1e-18,budget=budget),
                        LayeredVerdict(Verdict.UNKNOWN,Verdict.PASS))
                else:
                    with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
                        run(p,budget,[0,.31],.31)
                    self.assertEqual(assess_layers(None,physical_expected=None,
                        root_expected=None,budget=budget),
                        LayeredVerdict(Verdict.REJECTED,Verdict.UNKNOWN))
