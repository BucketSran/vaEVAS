"""A cross callback observes one certified time strictly after its root."""
GUARDS = ['EVENT-ORDER', 'DYNAMICS', 'COMPOSE']
from fractions import Fraction
import math
import unittest
from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


def execute(*, falling=False, nonpoint=False, timer=False, times=None, root_at_stop=False, controls=None, or_timer=False):
    threshold=1 if nonpoint else .5
    height=3 if nonpoint else 1
    source='''`include "disciplines.vams"
module x(u,strict,nonstrict,sample,stamp,count,timerstamp);input u;
output strict,nonstrict,sample,stamp,count,timerstamp;
electrical u,strict,nonstrict,sample,stamp,count,timerstamp;
real a,b,s,t,n,ts;
analog begin
@(initial_step)begin a=0;b=0;s=0;t=0;n=0;ts=-1;end
@(cross(V(u)-THRESHOLD,DIRECTION,1e-6,1e-6))begin
if(V(u) STRICT THRESHOLD)a=1;
if(V(u) NONSTRICT THRESHOLD)b=1;
s=V(u);t=$abstime;n=n+1;end
TIMER
V(strict)<+a;V(nonstrict)<+b;V(sample)<+s;V(stamp)<+t;V(count)<+n;V(timerstamp)<+ts;
end endmodule'''.replace('THRESHOLD',repr(threshold)).replace('DIRECTION','-1' if falling else '+1').replace('NONSTRICT','<=' if falling else '>=').replace('STRICT','<' if falling else '>')
    tau=float(Fraction(threshold)/height)
    if or_timer: source=source.replace('cross(V(u)-'+repr(threshold)+',-1,1e-6,1e-6)' if falling else 'cross(V(u)-'+repr(threshold)+',+1,1e-6,1e-6)', 'cross(V(u)-'+repr(threshold)+(','+'-1' if falling else ',+1')+',1e-6,1e-6) or timer('+repr(tau)+',0,0)')
    source=source.replace('TIMER',f'@(timer({tau!r},0,0))ts=$abstime;' if timer else '')
    p=compile_sources({'x.va':source},[Instance('M','x',{n:n for n in ['u','strict','nonstrict','sample','stamp','count','timerstamp']})])
    stop=tau if root_at_stop else 1
    controls=controls or ([[0,height],[1,0]] if falling else [[0,0],[1,height]])
    return transient(p,{'u':controls},times or [0,tau,min(1,tau+1e-5),stop],stop=stop,max_step=.125,vabstol=1e-10,reltol=0,kernel=KERNEL)


class CrossExecution(unittest.TestCase):
    def test_rising_and_falling_point_callbacks_observe_the_same_after_root_time(self):
        for falling in [False,True]:
            with self.subTest(falling=falling):
                r=execute(falling=falling)
                event=next(e for e in r['transient']['events'] if e['kind']=='cross')
                self.assertGreater(event['time'],.5)
                names=r['nodes'];old=r['solutions'][1]['voltages'];last=r['solutions'][-1]['voltages']
                self.assertEqual(old[names.index('count')],0)
                self.assertEqual(last[names.index('strict')],1)
                self.assertEqual(last[names.index('nonstrict')],1)
                self.assertEqual(last[names.index('stamp')],event['time'])
                sample=last[names.index('sample')]
                self.assertLess(sample,.5) if falling else self.assertGreater(sample,.5)
                self.assertAlmostEqual(sample,1-event['time'] if falling else event['time'],delta=1e-10)

    def test_mixed_arrival_and_post_root_callbacks_keep_leaf_specific_proofs(self):
        te = math.nextafter(.5, math.inf)
        for falling in [False, True]:
            for reverse in [False, True]:
                direction = -1 if falling else 1
                relation = '<' if falling else '>'
                bodies = [
                    f'@(cross(V(u)-0.5,{direction},1e-6,1e-6))begin '
                    f'if(V(u){relation}0.5)a=1;else a=2;ta=$abstime;end',
                    f'@(cross(V(v),{direction},1e-6,1e-6))begin '
                    f'if(V(v){relation}0)b=1;else b=2;tb=$abstime;end']
                if reverse:
                    bodies.reverse()
                source = ('`include "disciplines.vams"\n'
                    'module x(u,v,y,z,sa,sb);input u,v;output y,z,sa,sb;'
                    'electrical u,v,y,z,sa,sb;real a,b,ta,tb;analog begin '
                    '@(initial_step)begin a=0;b=0;ta=0;tb=0;end ' + ''.join(bodies) +
                    ' V(y)<+a;V(z)<+b;V(sa)<+ta;V(sb)<+tb;end endmodule')
                program = compile_sources({'mixed.va':source}, [Instance('M','x',
                    {name:name for name in ['u','v','y','z','sa','sb']})])
                u = [[0,1],[1,0]] if falling else [[0,0],[1,1]]
                v = [[0,1],[te,0],[1,-1]] if falling else [[0,-1],[te,0],[1,1]]
                result = transient(program, {'u':u,'v':v}, [0,.5,te,1], stop=1,
                    max_step=.125,vabstol=1e-10,reltol=0,kernel=KERNEL)
                with self.subTest(falling=falling,reverse=reverse):
                    events = result['transient']['events']
                    self.assertEqual([event['time'] for event in events], [te,te])
                    old = result['solutions'][1]['voltages']
                    row = result['solutions'][2]['voltages']
                    at = lambda values,name: values[result['nodes'].index(name)]
                    self.assertEqual([at(old,'y'),at(old,'z')], [0,0])
                    self.assertEqual([at(row,'y'),at(row,'z')], [1,2])
                    self.assertEqual([at(row,'sa'),at(row,'sb')], [te,te])
                    guards = [event['guard_value'] for event in events]
                    self.assertEqual(sum(value == 0 for value in guards),1)
                    self.assertTrue(any(value < 0 if falling else value > 0 for value in guards))

    def test_local_execution_keeps_operator_sample_and_captured_clock_before_later_timer(self):
        from test_continuous_dynamics import compile_model
        source = (
            '@(initial_step)begin n=0;q=0;h=0;m=0;s=0;strict=0;captured=100;timed=0;end '
            '@(timer(0.1,0.2,1e-6))begin n=n+1;q=n-1;end '
            '@(timer(0.30000000000000004,0,1e-6))m=m+1; '
            'V(z,r)<+idt(q,0); '
            '@(cross(V(z,r)-1e-18,1,1e-6,1e-6))begin '
            'h=h+1;s=V(z,r);if(V(z,r)>1e-18)strict=1;captured=$abstime;end '
            '@(timer(captured+1e-18,0,1e-6))timed=timed+1; '
            'V(y,r)<+s;V(a,r)<+strict;V(b,r)<+1.0*timed;')
        program = compile_model(source,'integer n,q,h,m,strict,timed;real s,captured;electrical z,a,b;')
        result = transient(program,{'u':[[0,0],[.31,.31]]},[0,.31],stop=.31,
            max_step=.31,vabstol=1e-10,reltol=0,kernel=KERNEL)
        events = result['transient']['events']
        self.assertEqual([e['event'] for e in events],[0,0,2,3,1])
        row = result['solutions'][-1]['voltages']
        sample = row[result['nodes'].index('y')]
        self.assertGreater(sample,1e-18)
        self.assertLess(sample,2e-18)
        self.assertEqual(row[result['nodes'].index('dut:a')],1)
        self.assertEqual(row[result['nodes'].index('dut:b')],1)
        self.assertEqual(result['transient']['states'][-1][2:4],[1,1])

    def test_nonpoint_root_is_not_the_callback_observation(self):
        r=execute(nonpoint=True)
        event=r['transient']['events'][0]
        self.assertGreater(Fraction(event['time']),Fraction(1,3))
        names=r['nodes'];last=r['solutions'][-1]['voltages']
        self.assertEqual(last[names.index('strict')],1)
        self.assertEqual(last[names.index('stamp')],event['time'])
        self.assertGreater(last[names.index('sample')],1)

    def test_exact_timer_at_root_stays_before_cross_execution(self):
        r=execute(timer=True)
        events=r['transient']['events'];cross=next(e for e in events if e['kind']=='cross');timer=next(e for e in events if e['kind']=='timer')
        self.assertEqual(timer['time'],.5)
        self.assertGreater(cross['time'],timer['time'])
        names=r['nodes'];at=r['solutions'][1]['voltages']
        self.assertEqual(at[names.index('timerstamp')],.5)
        self.assertEqual(at[names.index('count')],0)

    def test_cross_and_timer_or_keep_two_actual_execution_times(self):
        r=execute(or_timer=True)
        events=[e for e in r['transient']['events'] if e['kind']=='or']
        self.assertEqual(len(events),2)
        self.assertEqual(events[0]['time'],.5)
        self.assertGreater(events[1]['time'],.5)
        count=r['nodes'].index('count')
        self.assertEqual(r['solutions'][1]['voltages'][count],1)
        self.assertEqual(r['solutions'][-1]['voltages'][count],2)

    def test_root_at_stop_keeps_reference_backed_arrival(self):
        r=execute(root_at_stop=True,times=[0,.5])
        self.assertEqual(len(r['transient']['events']),1)
        self.assertEqual(r['transient']['events'][0]['time'],.5)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('count')],1)

    def test_knot_continuation_and_reference_backed_plateau_arrival(self):
        r=execute(controls=[[0,0],[.5,.5],[1,1]])
        self.assertEqual(len(r['transient']['events']),1)
        self.assertEqual(r['transient']['events'][0]['time'],.5)
        plateau=execute(controls=[[0,0],[.5,.5],[.75,.5],[1,1]])
        self.assertEqual(len(plateau['transient']['events']),1)
        self.assertEqual(plateau['transient']['events'][0]['time'],.5)

    def test_adjacent_root_free_nonlinear_mode_has_exact_rational_witness(self):
        source='''`include "disciplines.vams"
module mode(u,z,side,stamp);input u;output z,side,stamp;electrical u,z,side,stamp;real t;
analog begin @(initial_step)t=0;
@(cross(V(u)-0.5,+1,1e-6,1e-6))t=$abstime;
V(z)<+idt((V(u)>0.5 ? 1 : 0)*(1-V(z)*V(z)),0);
V(side)<+(V(u)>0.5 ? 1 : 0);V(stamp)<+t;end endmodule'''
        p=compile_sources({'mode.va':source},[Instance('M','mode',{n:n for n in ['u','z','side','stamp']})])
        r=transient(p,{'u':[[0,0],[1,1]]},[0,.5,.75,1],stop=1,max_step=.125,vabstol=1e-10,reltol=0,kernel=KERNEL)
        z=r['nodes'].index('z');side=r['nodes'].index('side')
        for x,row in zip([0,.5,.75,1],r['solutions']):
            self.assertAlmostEqual(row['voltages'][z],math.tanh(max(0,x-.5)),delta=1e-10)
            self.assertEqual(row['voltages'][side],int(x>.5))
        self.assertGreater(r['transient']['events'][0]['time'],.5)

    def test_adjacent_linear_mode_has_unit_area_and_keeps_exact_endpoint_predicate(self):
        end=math.nextafter(1,math.inf)
        source='''`include "disciplines.vams"
module narrow(u,z,side);input u;output z,side;electrical u,z,side;
analog begin V(z)<+idt(V(u)>1 ? 4503599627370496 : 0,0);
V(side)<+(V(u)>1 ? 1 : 0);end endmodule'''
        p=compile_sources({'narrow.va':source},[Instance('M','narrow',{n:n for n in ['u','z','side']})])
        r=transient(p,{'u':[[0,0],[1,1],[end,end]]},[0,1,end],stop=end,max_step=.125,vabstol=1e-10,reltol=0,kernel=KERNEL)
        z=r['nodes'].index('z');side=r['nodes'].index('side')
        self.assertAlmostEqual(r['solutions'][1]['voltages'][z],0,delta=1e-12)
        self.assertAlmostEqual(r['solutions'][2]['voltages'][z],1,delta=1e-12)
        self.assertEqual([row['voltages'][side] for row in r['solutions']],[0,0,1])

    def test_prior_write_rechecks_condition_and_trigger_keeps_prewrite_guard(self):
        source='''`include "disciplines.vams"
module prior(u,y,t,s);input u;output y,t,s;electrical u,y,t,s;real threshold,q,stamp,sample;
analog begin @(initial_step)begin threshold=0;q=0;stamp=0;sample=0;end
@(cross(V(u)-0.5-threshold,+1,1e-6,1e-6))begin
threshold=-threshold;if(V(u)-0.5>threshold)q=1;else q=2;stamp=$abstime;sample=V(u);end
V(y)<+q;V(t)<+stamp;V(s)<+sample;end endmodule'''
        p=compile_sources({'prior.va':source},[Instance('M','prior',{n:n for n in ['u','y','t','s']})])
        r=transient(p,{'u':[[0,0],[1,1]]},[0,.5,.6],stop=.6,max_step=.125,vabstol=1e-10,reltol=0,kernel=KERNEL)
        events=r['transient']['events'];self.assertEqual(len(events),1)
        self.assertGreater(events[0]['time'],.5)
        self.assertLess(abs(events[0]['guard_value']),1e-6)
        last=r['solutions'][-1]['voltages'];names=r['nodes']
        self.assertEqual(last[names.index('y')],1)
        self.assertEqual(last[names.index('t')],events[0]['time'])
        self.assertGreater(last[names.index('s')],.5)

    def test_history_root_upper_endpoint_proves_strict_post_side_at_stop(self):
        source='''`include "disciplines.vams"
module endpoint(ctl,z,y);input ctl;output z,y;electrical ctl,z,y;real slope;integer n;
analog begin @(initial_step)begin n=0;slope=1;end
V(z)<+idt(slope,0);
@(cross((V(z)-0.5)*(V(z)+0.5),0,1e-9,1e-8))n=n+1;
V(y)<+n;end endmodule'''
        p=compile_sources({'endpoint.va':source},[Instance('M','endpoint',{n:n for n in ['ctl','z','y']})])
        stop=.500000000001
        r=transient(p,{'ctl':[[0,0],[stop,stop]]},[0,stop],stop=stop,max_step=.002,vabstol=1e-10,reltol=1e-8,kernel=KERNEL)
        event,=r['transient']['events']
        self.assertGreater(event['time'],.5);self.assertLessEqual(event['time'],stop)
        self.assertGreater(event['guard_value'],0);self.assertLessEqual(event['guard_value'],1e-8)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],1)


class ExternalConditionObservation(unittest.TestCase):
    def test_unchanged_external_transition_is_a_certified_condition_input(self):
        source = '''`include "disciplines.vams"
module source(u,g);input u;output g;electrical u,g;real q;
analog begin @(initial_step)q=1; V(g)<+transition(q,0,0.01);end endmodule
module reader(u,g,y);input u,g;output y;electrical u,g,y;real q;
analog begin @(initial_step)q=0;
@(cross(V(u)-0.5,+1,1e-6,1e-6))if(V(g)>0.5)q=1;else q=2;
V(y)<+q;end endmodule'''
        p=compile_sources({'external.va':source},[Instance('E','source',{'u':'u','g':'g'}),Instance('D','reader',{'u':'u','g':'g','y':'y'})])
        r=transient(p,{'u':[[0,0],[1,1]]},[0,.5,.75,1],stop=1,max_step=.125,vabstol=1e-9,reltol=0,kernel=KERNEL)
        self.assertEqual(r['solutions'][1]['voltages'][r['nodes'].index('y')],0)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],1)

    def test_condition_rejects_own_indirect_writer_and_simultaneous_external_writer(self):
        for own in [False, True]:
            for zero in [False, True]:
                with self.subTest(own=own, zero=zero):
                    if own:
                        source = '''`include "disciplines.vams"
module own(u,y);input u;output y;electrical u,y,g;real q;
analog begin @(initial_step)q=1;
@(cross(V(u)-0.5,+1,1e-6,1e-6))begin if(V(g)>0.5)q=2;else q=3;end
V(g)<+transition(COEFF*q,0,0.01);V(y)<+q;end endmodule'''.replace('COEFF','0' if zero else '1')
                        instances=[Instance('E','own',{'u':'u','y':'y'})]
                    else:
                        source = '''`include "disciplines.vams"
module source(u,g);input u;output g;electrical u,g;real q;
analog begin @(initial_step)q=1;
@(cross(V(u)-0.5,+1,1e-6,1e-6))q=2;
V(g)<+transition(COEFF*q,0,0.01);end endmodule
module reader(u,g,y);input u,g;output y;electrical u,g,y;real q;
analog begin @(initial_step)q=0;
@(cross(V(u)-0.5,+1,1e-6,1e-6))if(V(g)>0.5)q=1;else q=2;
V(y)<+q;end endmodule'''.replace('COEFF','0' if zero else '1')
                        instances=[Instance('E','source',{'u':'u','g':'g'}),Instance('D','reader',{'u':'u','g':'g','y':'y'})]
                    p=compile_sources({'dependency.va':source},instances)
                    with self.assertRaisesRegex(KernelError,'unsupported_condition|unsupported_cross'):
                        transient(p,{'u':[[0,0],[1,1]]},[0,.75,1],stop=1,max_step=.125,vabstol=1e-9,reltol=0,kernel=KERNEL)


class ReadOnlyQueryCertificates(unittest.TestCase):
    def test_queries_cannot_suppress_source_refinement_in_history_calendar(self):
        from test_affine import model, instance
        from decimal import Decimal, localcontext
        body = '''@(initial_step)begin q=-1;n=0;end
@(cross(V(u,r)*V(u,r)-0.125,1,1e-9,1e-8))q=0.3535533905932738;
V(z,r)<+idt(0,0);
@(cross(V(z,r)+V(u,r)-q,1,1e-9,1e-8))n=n+1;
V(y,r)<+n;'''
        for strobes, target_cut in [(None,False),([.25],False),(None,True),([.2,.25],True)]:
            with self.subTest(strobes=strobes,target_cut=target_cut):
                extra = 'V(g,r)<+transition(V(u,r)>0.25 ? 1:0,0,0.01,0.01);' if target_cut else ''
                p=compile_sources({'query-proof.va':model(body+extra,'real q;integer n;electrical z,g;')},[instance()])
                def one(times):
                    return transient(p,{'u':[[0,0],[1,1]]},times,stop=1,max_step=2,
                                     strobetimes=strobes,vabstol=1e-8,reltol=0,kernel=KERNEL)
                sparse=one([0,1]);event=sparse['transient']['events'][0]
                e=event['time']
                dense=one(sorted(set([0,.25,0.3535533905932738,e,.5,1])))
                self.assertEqual(sparse['transient']['events'],dense['transient']['events'])
                self.assertEqual(sparse['solutions'][-1],dense['solutions'][-1])
                with localcontext() as c:
                    c.prec=60;tau=(Decimal(1)/8).sqrt();execution=Decimal.from_float(e)
                    self.assertGreater(execution,tau)
                    self.assertLessEqual(execution-tau,Decimal('1e-9'))
                self.assertGreater(event['guard_value'],0)
                self.assertLessEqual(event['guard_value'],1e-8)
