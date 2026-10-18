"""Constant initial output snapshots, with answers from procedural source order.

A snapshot must retain the value at the call site, while State.initial and cold
transition histories use the final initialization value. No initial voltage
observation or dynamic seed contract is added here.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'TRANSITION', 'COMPOSE']

import copy
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from evas.runtime import _invoke
from test_affine import KERNEL, instance, model


def compile_body(body, declarations='integer q;'):
    return compile_sources({'active_initial.va': model(body, declarations)}, [instance()])


def run(program, times=None):
    return transient(program, {'u':[[0,1],[1,1]]}, times or [0,.25,0.5,1],
                     stop=1, max_step=1, kernel=KERNEL)


def texts(result):
    return [(r['time'], r['text']) for r in result['transient']['display_records']]


class ActiveInitialOutput(unittest.TestCase):
    def test_strobe_initial_snapshots_and_cold_history_use_different_values(self):
        p=compile_body('''@(initial_step) begin
            $strobe("before=%d",q); q=3; $strobe("middle=%d",q);
            q=q+2; $strobe("after=%d",q);
            end V(y,r)<+transition(q,0,0.125,0.125);''')
        r=run(p)
        self.assertEqual(texts(r),[(0,'before=0'),(0,'middle=3'),(0,'after=5')])
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],[5]*4)
        self.assertEqual(r['transient']['states'],[[5]]*4)

    def test_separate_initial_blocks_and_static_condition_preserve_source_order(self):
        p=compile_body('''@(initial_step) q=1;
            @(initial_step) begin $display("a=%d",q);
                if (pick>0) begin q=4; $strobe("yes=%d",q); end
                else begin q=8; $strobe("no=%d",q); end end
            @(initial_step) begin q=q+2; $strobe("b=%d",q); end
            V(y,r)<+q;''', 'integer q; parameter integer pick=1;')
        self.assertEqual(texts(run(p)),[(0,'a=1'),(0,'yes=4'),(0,'b=6')])

    def test_initial_snapshots_precede_timer_zero_and_final_observation(self):
        p=compile_body('''@(initial_step) begin
                $strobe("before=%d",q); q=3; $display("seed=%d",q); end
            @(timer(0)) begin $strobe("timer=%d",q); q=7; end
            V(y,r)<+transition(q,0,0.125,0.125);''')
        r=run(p)
        self.assertEqual(texts(r),[(0,'before=0'),(0,'seed=3'),(0,'timer=3')])
        self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('y')],7)

    def test_parameter_snapshots_are_per_instance(self):
        text=model('''@(initial_step) begin q=seed; $strobe("q=%d",q); end
            V(y,r)<+q;''','parameter integer seed=2; integer q;')
        p=compile_sources({'pair.va':text},[instance(),instance(name='second',
            connections=dict(u='u',y='z',r='0'),parameters=dict(seed=7))])
        r=run(p)
        self.assertEqual([v for _,v in texts(r)],['q=2','q=7'])
        self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('y')],2)
        self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('z')],7)

    def test_runtime_strobe_fixed_formats_and_rejected_trials_do_not_duplicate(self):
        p=compile_body('''@(initial_step) q=2;
            @(timer(0.5)) begin $strobe("before=%d",q); q=q+1;
              $strobe("q=%d t=%.3f neg=%.2f zero=%.0f default=%f %%",q,$abstime,-1.25,-0.0001,1.5);
            end V(y,r)<+q;''')
        r=run(p,[0,1])
        self.assertGreater(r['transient']['discarded_trials'],0)
        self.assertEqual(texts(r),[(.5,'before=2'),(.5,'q=3 t=0.500 neg=-1.25 zero=-0 default=1.500000 %')])

    def test_constant_initial_output_with_no_states(self):
        p=compile_body('''@(initial_step) $strobe("fixed=%.2f",1.25);
            V(y,r)<+1;''','')
        self.assertEqual(texts(run(p)),[(0,'fixed=1.25')])

    def test_active_initial_voltage_or_history_reads_are_rejected(self):
        for expr in ['V(u,r)','V(y,r)','transition(1,0,0.1,0.1)']:
            with self.subTest(expr=expr), self.assertRaises(CompileError):
                compile_body('@(initial_step) $strobe("v=%g",'+expr+'); V(y,r)<+q;')
        with self.assertRaises(CompileError):
            compile_body('''@(initial_step) begin if(V(u,r)>0) $display("yes"); end V(y,r)<+q;''')

    def test_active_initial_snapshot_of_input_selected_seed_is_rejected(self):
        with self.assertRaises(CompileError):
            compile_body('''@(initial_step) begin q=V(u,r)>0?1:0;
                $strobe("q=%d",q); end V(y,r)<+q;''')

    def test_initial_output_in_static_loop_or_hierarchical_owner_remains_rejected(self):
        # Loop initialization retains its assignment-only contract. Zero-trip
        # loops must not erase an unsupported voltage output operation.
        for count in [0,2]:
            with self.subTest(count=count),self.assertRaises(CompileError):
                compile_body('@(initial_step) for(k=0;k<'+str(count)+
                             ';k=k+1) $strobe("x=%g",V(y,r)); V(y,r)<+q;',
                             'integer q; genvar k;')
        child=model('V(y,r)<+0;','').replace('module m(', 'module child(')
        parent=model('@(initial_step) $strobe("fixed"); V(y,r)<+0;',
                     '').replace('analog begin','child c(u,y,r); analog begin')
        with self.assertRaises(CompileError):
            compile_sources({'hier.va':child+parent},[instance()])

    def test_snapshot_arithmetic_overflow_is_a_located_compile_error(self):
        # Finite conditional seeds can still overflow when the snapshot raises
        # them to a power. No host arithmetic exception may cross the API.
        for seed, expression in [('pick>0?1e100:1','pow(z,32)'),
                                 ('pick>0?-1e100:1','pow(z,31)'),
                                 ('pick>0?1e100:1','z*z*z*z')]:
            with self.subTest(seed=seed,expression=expression):
                with self.assertRaises(CompileError) as caught:
                    compile_body('@(initial_step) begin z='+seed+
                                 '; $strobe("x=%g",'+expression+'); end V(y,r)<+0;',
                                 'parameter integer pick=1; real z;')
                diagnostic=caught.exception.diagnostic
                self.assertEqual(diagnostic['code'],'unsupported_initial_event')
                self.assertEqual(diagnostic['location']['source'],'active_initial.va')
                self.assertEqual(diagnostic['instance'],'dut')
                self.assertIn('finite snapshots',diagnostic['message'])

    def test_finite_conditional_seed_power_still_produces_output(self):
        # The unselected seed is large but finite. Only the selected seed is
        # exponentiated, giving exactly 1 or 4294967296 before formatting.
        for pick,seed,expected in [(-1,'pick>0?1e100:1','x=1'),
                                   (1,'pick>0?2:1','x=4294967296')]:
            p=compile_body('@(initial_step) begin z='+seed+
                           '; $strobe("x=%.0f",pow(z,32)); end V(y,r)<+0;',
                           'parameter integer pick='+str(pick)+'; real z;')
            self.assertEqual(texts(run(p)),[(0,expected)])

    def test_invalid_fixed_formats_and_arity_are_rejected(self):
        for fmt,args in [('%.33f',',1'),('%.03f',',1'),('%.f',',1'),('%.0g',',1'),('%.2d',',1'),('%f','')]:
            with self.subTest(fmt=fmt),self.assertRaises(CompileError):
                compile_body('@(timer(0.5)) $strobe("'+fmt+'"'+args+'); V(y,r)<+q;')

    def test_raw_ir_cannot_turn_active_initial_snapshots_into_state_writes_or_voltage_reads(self):
        p=compile_body('@(initial_step) $strobe("seed=%g",1); V(y,r)<+q;').to_dict()
        for mode in ['state_write','voltage_read']:
            payload=copy.deepcopy(p)
            if mode=='state_write':
                payload['events'][0]['body']=(dict(kind='assign',state=0,rhs=dict(op='affine',constant=2,terms=[])), *payload['events'][0]['body'])
            else:
                payload['events'][0]['body'][0]['args']=[dict(op='affine',constant=0,terms=[dict(node=p['nodes'].index('y'),coefficient=1)])]
            with self.subTest(mode=mode),self.assertRaises(KernelError):
                _invoke(dict(program=payload,driven=['u'],samples=[],transient=dict(
                    pwl=[[[0,1],[1,1]]],output_times=[0,1],stop=1,max_step=1)),KERNEL)
