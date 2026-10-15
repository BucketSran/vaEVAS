"""Live voltage times independent transition, with analytic public-path answers."""
GUARDS = ["TIMED-OPERATOR", "LANG"]
from pathlib import Path
import math
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

T = 2.0**-20
FIXTURES = Path(__file__).parent / 'fixtures' / 'live-transition'

class LiveTransitionCoefficient(unittest.TestCase):
    def run_card(self, name, times=None):
        source = (FIXTURES / (name+'.va')).read_text()
        ports = ['h','edge','y','qout','count']
        if name == 'history': ports += ['other']
        if name.startswith('filter'): ports += ['f']
        program = compile_sources({name+'.va': source},
            [Instance('M','product_card',{p:p for p in ports})])
        return transient(program, {}, times or [x*T for x in [0,1,1.25,1.5,1.75,2,3]],
            stop=3*T, max_step=T/64, vabstol=1e-10, reltol=0, kernel=KERNEL)

    def check_card(self, name):
        xs = [0,1,1.25,1.5,1.75,2,3]
        result = self.run_card(name)
        for x,row in zip(xs,result['solutions']):
            values = dict(zip(result['nodes'],row['voltages']))
            h = .25+x if name == 'history' else 2+x
            edge = max(0,min(1,x-1))
            if name == 'filter-interrupt' and x >= 1.5: edge=max(0,2-x)
            gain = 1000 if name == 'ramp-g1000' else 1
            for node,expected in [('h',h),('edge',edge),('y',gain*h*edge)]:
                self.assertAlmostEqual(values[node],expected,delta=1e-8)
            if name == 'history':
                self.assertAlmostEqual(values['other'],-.125-.5*x,delta=1e-8)
            if name.startswith('filter'):
                f=0
                if x>1:
                    if x<=2: f=x*x-x-1+math.exp(1-x)
                    else: f=x+1+(math.exp(-1)-2)*math.exp(2-x)
                if name=='filter-interrupt' and x>=1.5:
                    if x<=2:f=-x*x+2*x+2+(math.exp(-.5)-3)*math.exp(1.5-x)
                    else:f=(2+math.exp(-1)-3*math.exp(-.5))*math.exp(2-x)
                self.assertAlmostEqual(values['f'],f,delta=1e-8)

    def test_ramp(self): self.check_card('ramp')
    def test_ramp_g1000(self): self.check_card('ramp-g1000')
    def test_history(self): self.check_card('history')
    def test_filter(self): self.check_card('filter')
    def test_filter_interrupt(self): self.check_card('filter-interrupt')

class SourceControlledTransition(unittest.TestCase):
    def execute(self, expression, times, controls=None, zero_timer=False, zero_rhs='2', real_q=False, edge_fraction=1):
        source = """`include "disciplines.vams"
module source_card(ctrl,y,count);input ctrl;output y,count;electrical ctrl,y,count;
parameter real T=9.5367431640625e-7;integer q,n;analog begin
@(initial_step)begin q=1;n=0;end
@(timer(2.5*T,0,1e-12))begin q=2;n=n+1;end
V(y)<+transition("""+expression+""",0,T,T);
V(count)<+n;end endmodule"""
        if zero_timer: source=source.replace('V(y)<+', '@(timer(0,0,1e-12))q='+zero_rhs+';V(y)<+')
        if real_q: source=source.replace('integer q,n;', 'real q;integer n;')
        if edge_fraction != 1: source=source.replace('0,T,T)',f'0,{edge_fraction}*T,{edge_fraction}*T)')
        p=compile_sources({'source.va':source},[Instance('M','source_card',dict(ctrl='ctrl',y='y',count='count'))])
        return transient(p,{'ctrl':controls or [[0,0],[T,1],[2*T,1],[3*T,0],[4*T,0]]},times,
                         stop=4*T,max_step=T/8,vabstol=1e-10,reltol=0,kernel=KERNEL)

    def test_source_thresholds_install_held_targets_without_user_events(self):
        times=[x*T for x in [0,.5,.75,1,1.5,2,2.5,2.75,3,3.5,4]]
        r=self.execute('V(ctrl)>0.5 ? q : 0',times)
        y=r['nodes'].index('y')
        # The held target rises at T/2 and reverses at 5T/2.
        # At that boundary the q assignment is masked by the false source arm.
        expected=[0,0,.25,.5,1,1,1,.75,.5,0,0]
        for row,want in zip(r['solutions'],expected):
            self.assertAlmostEqual(row['voltages'][y],want,delta=1e-8)
        dense=self.execute('V(ctrl)>0.5 ? q : 0',[i*T/16 for i in range(65)])
        self.assertEqual(r['transient']['events'],dense['transient']['events'])

    def test_source_target_value_leaves_still_cannot_be_smooth_voltage(self):
        for expression in ['V(ctrl)', '0*V(ctrl)', 'V(ctrl)>0.5 ? q : V(ctrl)']:
            with self.subTest(expression=expression):
                with self.assertRaises((CompileError, KernelError)): self.execute(expression,[0,4*T])

    def test_initial_strict_source_boundary_uses_right_hand_target_once(self):
        r=self.execute('V(ctrl)>0 ? q : 0',[0,T/4,T/2,T,1.5*T,4*T])
        y=r['nodes'].index('y')
        for row,expected in zip(r['solutions'],[0,.25,.5,1,1,0]):
            self.assertAlmostEqual(row['voltages'][y],expected,delta=1e-8)

    def test_isolated_source_point_target_is_rejected(self):
        with self.assertRaisesRegex(KernelError, 'condition_precision'):
            self.execute('(V(ctrl)>=0.5 && V(ctrl)<=0.5) ? 2 : 0',[0,4*T])

    def test_nonbinary_source_root_preserves_true_transition_time_enclosure(self):
        r=self.execute('V(ctrl)>0.5 ? q : 0',[0,T/3,T/2,T,2*T,4*T],
                       controls=[[0,0],[T,3],[4*T,3]])
        y=r['nodes'].index('y')
        # The original affine ramp crosses at exact T/6, not a binary64 point.
        for row,expected in zip(r['solutions'],[0,1/6,1/3,5/6,1,2]):
            self.assertAlmostEqual(row['voltages'][y],expected,delta=1e-8)

    def test_zero_timer_settles_source_epoch_before_history_is_initialized(self):
        r=self.execute('V(ctrl)>0 ? q : 0',[0,T/4,T/2,T],zero_timer=True)
        y=r['nodes'].index('y')
        for row,expected in zip(r['solutions'],[0,.5,1,2]):
            self.assertAlmostEqual(row['voltages'][y],expected,delta=1e-8)
        dense=self.execute('V(ctrl)>0 ? q : 0',[i*T/32 for i in range(129)],zero_timer=True)
        self.assertEqual(r['transient']['events'],dense['transient']['events'])

    def test_zero_source_bootstrap_still_refuses_internal_voltage_reads(self):
        for rhs in ['V(y)','2+0*V(y)']:
            with self.subTest(rhs=rhs), self.assertRaisesRegex(KernelError,'unsupported_initial_history'):
                self.execute('V(ctrl)>0 ? q : 0',[0,T],zero_timer=True,zero_rhs=rhs,real_q=True)

    def test_query_at_lower_enclosure_endpoint_stays_before_nonbinary_cut(self):
        from fractions import Fraction
        lo=T/6
        hi=math.nextafter(lo,math.inf)
        r=self.execute('V(ctrl)>0.5 ? q : 0',[0,lo,hi,T/3,2*T,4*T],
                       controls=[[0,0],[T,3],[4*T,3]])
        y=r['nodes'].index('y')
        self.assertEqual(r['solutions'][1]['voltages'][y],0)
        expected=float((Fraction(hi)-Fraction(T)/6)/Fraction(T))
        self.assertAlmostEqual(r['solutions'][2]['voltages'][y],expected,delta=1e-10)

    def test_source_cut_and_edge_deadline_need_equal_real_roots_not_equal_boxes(self):
        # End of the first edge is exactly (1/4 + binary64(0.1))*T.
        # The second source root is binary64(1.05)/3*T. They differ but have
        # the same outward two-float enclosure; a common upper float is no tie.
        with self.assertRaisesRegex(KernelError,'deadline ordering relative to source-target cut'):
            self.execute('V(ctrl)<0.75 ? 0 : (V(ctrl)<1.05 ? 1 : 0)',[0,T],
                controls=[[0,0],[T,3],[4*T,3]],edge_fraction=0.1)

    def test_same_nonpoint_source_cut_and_edge_deadline_can_settle_together(self):
        # (1/6 + 1/8)*T = 7/24*T = (7/8)/3*T is one real root.
        result=self.execute('V(ctrl)<0.5 ? 0 : (V(ctrl)<0.875 ? 1 : 0)',
            [x*T for x in [0,1/6,11/48,7/24,17/48,5/12,1,4]],
            controls=[[0,0],[T,3],[4*T,3]],edge_fraction=0.125)
        y=result['nodes'].index('y')
        for row,want in zip(result['solutions'],[0,0,.5,1,.5,0,0,0]):
            self.assertAlmostEqual(row['voltages'][y],want,delta=1e-8)

    def test_nonpoint_cross_and_source_cut_share_original_guard_root(self):
        source = """`include "disciplines.vams"
module source_cross(ctrl,h,y);input ctrl;output h,y;electrical ctrl,h,y;
parameter real T=9.5367431640625e-7;integer q;
analog begin @(initial_step)q=0;
@(cross(V(ctrl)-0.5,+1,1e-12,1e-10))q=1;
V(h)<+2+$abstime/T;
V(y)<+V(h)*transition((V(ctrl)>0.5 ? q : 0),0,T,T);
end endmodule"""
        p=compile_sources({'cross.va':source},[Instance('M','source_cross',dict(ctrl='ctrl',h='h',y='y'))])
        r=transient(p,{'ctrl':[[0,0],[T,3],[2*T,3]]},[0,T/3,T/2,T,2*T],
                    stop=2*T,max_step=T/64,vabstol=1e-10,reltol=0,kernel=KERNEL)
        y=r['nodes'].index('y')
        for row,want in zip(r['solutions'],[0,7/18,5/6,2.5,4]):
            self.assertAlmostEqual(row['voltages'][y],want,delta=1e-8)

    def test_equal_nonpoint_physical_modes_retain_original_root_identity(self):
        source = """`include "disciplines.vams"
module modes(ctrl,h0,h1,y);input ctrl;output h0,h1,y;electrical ctrl,h0,h1,y;
parameter real T=9.5367431640625e-7;integer q;
analog begin @(initial_step)q=0;@(timer(0.5*T,0,1e-12))q=1;
V(h0)<+idt((V(ctrl)>0.5 ? 1/T : -1/T),0);
V(h1)<+idt((2*V(ctrl)>1 ? 1/T : -1/T),0.25);
V(y)<+(V(h0)+V(h1))*transition(q,0,T,T);
end endmodule"""
        p=compile_sources({'modes.va':source},[Instance('M','modes',dict(ctrl='ctrl',h0='h0',h1='h1',y='y'))])
        r=transient(p,{'ctrl':[[0,0],[T,3],[2*T,3]]},[0,T,2*T],
                    stop=2*T,max_step=T/64,vabstol=1e-10,reltol=0,kernel=KERNEL)
        y=r['nodes'].index('y')
        for row,want in zip(r['solutions'],[0,19/24,43/12]):
            self.assertAlmostEqual(row['voltages'][y],want,delta=1e-8)

    def test_distinct_touching_nonpoint_physical_roots_are_not_merged(self):
        source = """`include "disciplines.vams"
module nearby(ctrl,h0,h1,y);input ctrl;output h0,h1,y;electrical ctrl,h0,h1,y;
parameter real T=9.5367431640625e-7;integer q;
analog begin @(initial_step)q=0;@(timer(0.5*T,0,1e-12))q=1;
V(h0)<+idt((V(ctrl)>0.5 ? 1/T : -1/T),0);
V(h1)<+idt((V(ctrl)>0.5000000000000001 ? 1/T : -1/T),0.25);
V(y)<+(V(h0)+V(h1))*transition(q,0,T,T);
end endmodule"""
        p=compile_sources({'nearby.va':source},[Instance('M','nearby',dict(ctrl='ctrl',h0='h0',h1='h1',y='y'))])
        with self.assertRaisesRegex(KernelError,'condition_precision'):
            transient(p,{'ctrl':[[0,0],[T,3],[2*T,3]]},[0,2*T],
                      stop=2*T,max_step=T/64,vabstol=1e-10,reltol=0,kernel=KERNEL)

class CapturedClockModes(unittest.TestCase):
    def execute_clock(self, independent_mux=False, times=None, capture_extra=False, guard_case=None):
        source='''`include "disciplines.vams"
module cell(ctrl,y);input ctrl;output y;electrical ctrl,y;
real captured;analog begin
@(initial_step)captured=0;
@(cross(V(ctrl)-0.5,+1,1e-12,1e-10))captured=$abstime;
V(y)<+idt(($abstime-captured < 0.25 ? 1 : -1),0);
end endmodule'''
        if capture_extra: source=source.replace('captured=$abstime;', 'captured=$abstime+0*V(ctrl);')
        if guard_case:
            source=source.replace('cross(V(ctrl)-0.5,+1,1e-12,1e-10)',guard_case)
        instances=[Instance('C'+str(k),'cell',{'ctrl':'ctrl','y':'y'+str(k)}) for k in range(4)]
        if independent_mux:
            source+='''
module mux(a,b,sel,y);input a,b,sel;output y;electrical a,b,sel,y;
integer q,selected;real read_value;analog begin
@(initial_step)q=0;@(timer(0.5,0,1e-12))q=1;
selected=(V(sel)>0.5 ? 1 : 0);
case(selected) 0:read_value=V(b); 1:read_value=V(a); endcase
V(y)<+read_value*transition(q,0,0.25,0.25);
end endmodule'''
            instances.append(Instance('M','mux',dict(a='y0',b='y1',sel='select',y='mux')))
        program=compile_sources({'clock.va':source},instances)
        inputs={'ctrl':[[0,0],[1,3]]}
        if independent_mux: inputs['select']=[[0,1],[1,1]]
        return transient(program,inputs,times or [0,1/6,0.25,5/12,0.5,1],
            stop=1,max_step=1/64,vabstol=1e-10,reltol=0,kernel=KERNEL)

    def test_four_independent_owners_keep_same_nonpoint_capture_root(self):
        result=self.execute_clock()
        for k in range(4):
            index=result['nodes'].index('y'+str(k))
            for row,want in zip(result['solutions'],[0,1/6,1/4,5/12,1/3,-1/6]):
                self.assertAlmostEqual(row['voltages'][index],want,delta=1e-8)

    def test_direct_capture_guards_do_not_project_unrelated_live_mux_equations(self):
        result=self.execute_clock(independent_mux=True)
        index=result['nodes'].index('mux')
        for row,want in zip(result['solutions'],[0,0,0,0,0,-1/6]):
            self.assertAlmostEqual(row['voltages'][index],want,delta=1e-8)

    def test_capture_without_time_provenance_still_refuses_overlapping_roots(self):
        with self.assertRaisesRegex(KernelError,'condition_precision'):
            self.execute_clock(capture_extra=True)

    def test_clock_capture_and_live_mux_are_invariant_to_output_queries(self):
        sparse=self.execute_clock(independent_mux=True)
        dense=self.execute_clock(independent_mux=True,times=[i/64 for i in range(65)])
        self.assertEqual(sparse['transient']['events'],dense['transient']['events'])
        for node in ['y0','y1','y2','y3','mux']:
            s=sparse['solutions'][-1]['voltages'][sparse['nodes'].index(node)]
            d=dense['solutions'][-1]['voltages'][dense['nodes'].index(node)]
            self.assertAlmostEqual(s,d,delta=1e-8)

    def test_internal_voltage_guard_dependencies_cannot_use_direct_projection(self):
        guards=[
            'cross(V(y)-0.01,+1,1e-12,1e-10)',
            'cross(V(ctrl)-0.5+0*V(y),+1,1e-12,1e-10)',
            'cross(V(ctrl)-0.5,+1,1e-12,1e-10) or cross(V(y)-0.01,+1,1e-12,1e-10)',
            'cross(V(ctrl)-0.5,+1,1e-12,1e-10) or cross(1+0*V(y),+1,1e-12,1e-10)',
        ]
        for guard in guards:
            with self.subTest(guard=guard), self.assertRaisesRegex(KernelError,'event_resolution|unsupported_cross'):
                self.execute_clock(independent_mux=True,guard_case=guard)
