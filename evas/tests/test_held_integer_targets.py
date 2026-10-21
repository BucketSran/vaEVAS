"""Strict held integer Transition projections bind actual point boxes per epoch."""
GUARDS = ["LANG", "TRANSITION", "EVENT-ORDER", "TIMER", "COMPOSE"]
import unittest
from evas import Instance, compile_sources, transient, CompileError, KernelError
from test_affine import KERNEL
from test_native_integer_events import model


def program(target='(n&1)?0.9:0.0',body='n=n+1;',initial='n=0;m=0;out=0;',timer0=False):
    text=model(body,decl='integer n,m;real out;',initial=initial)
    text=text.replace('V(y,r)<+out;',f'V(y,r)<+transition({target},0,0.1,0.1);')
    if timer0:text=text.replace('@(timer(1,1))','@(timer(0,1))')
    return compile_sources({'held-bits.va':text},[Instance('dut','m',dict(y='y',r='0'))])


def output(p,times):
    r=transient(p,{},times,stop=times[-1],max_step=.1,kernel=KERNEL)
    return [s['voltages'][r['nodes'].index('y')] for s in r['solutions']]


class HeldIntegerTargets(unittest.TestCase):
    def test_select_targets_rebind_after_ordered_callback_writes(self):
        self.assertEqual(output(program(),[0,.5,1.2,2.2]),[0,0,.9,0])

    def test_constant_projection_and_unchanged_bit_use_fresh_integer_epoch(self):
        self.assertEqual(output(program('0.9*((n>>1)&1)'),[0,1.2,2.2,3.2]),[0,0,.9,.9])

    def test_exact_timer_zero_initializes_settled_point_without_a_cold_edge(self):
        self.assertEqual(output(program(timer0=True),[0,.05,.5,1.2]),[.9,.9,.9,0])

    def test_hidden_real_voltage_time_and_other_operators_are_not_held(self):
        for target in ['(n&1)+0.0*out','(n&1)+0.0*V(y,r)',
                       '(n&1)+0.0*$abstime','(n&1)?0.9:(out*0.0)',
                       '(n&1)?0.9:ddt(0.0)','(n&1)?0.9:(1<<n)',
                       '(n&1)+(m>>n)']:
            with self.subTest(target=target),self.assertRaises(CompileError):
                program(target)

    def test_each_source_child_overflow_precedes_mask_and_retarget(self):
        for target in ['(n+1)&0','(n+1)>>32','((n+1)&1)?0.9:0.0']:
            p=program(target,initial='n=2147483646;m=0;out=0;')
            with self.subTest(target=target),self.assertRaises(KernelError):
                output(p,[0,1.2])

    def test_queries_do_not_change_future_held_history_and_both_states_rebind(self):
        p=program('((n>>1)&1)?((m&1)?0.9:0.3):0.0',body='n=n+1;m=m+1;')
        times=[0,1.2,2.2,3.2,4.2]
        expected=[0,0,.3,.9,0]
        self.assertEqual(output(p,times),expected)
        dense=sorted(set(times+[.05,.5,1.05,2.05,2.1,3.05]))
        actual=dict(zip(dense,output(p,dense)))
        self.assertEqual([actual[t] for t in times],expected)

    def test_raw_target_protocol_audits_unselected_and_canceled_dependencies(self):
        import copy,json,subprocess
        p=json.loads(json.dumps(program().to_dict()))
        primitive=p['operators'][0]['input']['left']
        def reject(target):
            bad=copy.deepcopy(p);bad['operators'][0]['input']=target
            r=subprocess.run([str(KERNEL)],input=json.dumps(dict(program=bad,driven=[],samples=[],transient=dict(pwl=[],output_times=[0,1],stop=1,max_step=.1))),text=True,capture_output=True,timeout=10)
            self.assertNotEqual(r.returncode,0,r.stdout)
        constant=lambda n:dict(op='affine',constant=n,terms=[])
        for leaf in [dict(op='state',state=2),dict(op='state',state=999),
                     dict(op='affine',constant=0,terms=[dict(node=1,coefficient=0)]),
                     dict(op='operator',operator=0),
                     dict(op='checked_integer',value=constant(0),origin=p['operators'][0]['origin']),
                     dict(op='event_math',function='floor',args=[constant(0)],origin=p['operators'][0]['origin'])]:
            reject(dict(op='add',left=primitive,right=dict(op='multiply',left=constant(0),right=leaf)))
        bad=copy.deepcopy(primitive);bad['origin']['instance']='foreign';reject(bad)
        bad=copy.deepcopy(primitive);bad['args'][0]=dict(op='integer_state',state=2);reject(bad)

    def test_real_projection_preserves_forward_box_and_initial_voltage_gate(self):
        from fractions import Fraction as Q
        p=program('0.9*((n>>1)&3)',initial='n=6;m=0;out=0;')
        r=transient(p,{},[0,.5,1.2],stop=1.2,max_step=.1,vabstol=1e-12,reltol=0,kernel=KERNEL)
        y=r['nodes'].index('y');want=Q(.9)*3
        for frame in r['observation_evidence']['voltage_bounds_V']:
            lo,hi=map(Q,frame[y]);self.assertLessEqual(lo,want);self.assertGreaterEqual(hi,want)
            self.assertLess(lo,hi)
        # The original high-gain initial V certificate must see that error box.
        text=model('n=n+1;',decl='integer n;real out;',initial='n=6;out=0;')
        text=text.replace('V(y,r)<+out;', 'V(y,r)<+1099511627776*(transition(0.9*((n>>1)&3),0,0.1,0.1)-2.7);')
        amplified=compile_sources({'gain-held.va':text},[Instance('dut','m',dict(y='y',r='0'))])
        with self.assertRaises(KernelError):
            transient(amplified,{},[0,.5],stop=.5,max_step=.1,vabstol=1e-12,reltol=0,kernel=KERNEL)
