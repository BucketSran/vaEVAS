"""Typed event arithmetic retains the real signed32 counter and source order."""
GUARDS = ["LANG", "COMPOSE", "EVENT-ORDER", "EVENT-CONDITIONS"]
import unittest
from evas import Instance, compile_sources, transient, CompileError, KernelError
from test_affine import KERNEL


def model(body, decl="integer n;real out;", initial="n=0;out=0;"):
    return ('`include "disciplines.vams"\nmodule m(y,r);output y;inout r;electrical y,r;'
            + decl + 'analog begin @(initial_step)begin '+initial+'end '
            +'@(timer(1,1))begin '+body+'end V(y,r)<+out;end endmodule')


def program(body="n=n+1;out=n%8;", **kwargs):
    return compile_sources({"native.va":model(body,**kwargs)},[Instance("dut","m",dict(y="y",r="0"))])


class NativeIntegerEvents(unittest.TestCase):
    def test_real_counter_increments_before_constant_remainder(self):
        p=program()
        r=transient(p,{},list(range(10)),stop=9,max_step=1,kernel=KERNEL)
        y=r["nodes"].index("y")
        self.assertEqual([s["voltages"][y] for s in r["solutions"]],[0,1,2,3,4,5,6,7,0,1])

    def test_signed_remainder_and_later_guards_see_prior_writes(self):
        for initial, divisor, want in [(-9,8,-1),(9,-8,1),(-9,-8,-1)]:
            with self.subTest(initial=initial, divisor=divisor):
                p=program('out=n%'+str(divisor)+';n=n+1;',initial=f'n={initial};out=0;')
                r=transient(p,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
                self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],want)

    def test_typed_predicate_only_callback_uses_causal_path(self):
        p=program('n=n+1;if(n%8==1)out=10;if(n%8==1)out=out+1;')
        r=transient(p,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],11)

    def test_nested_add_preserves_every_original_checked_node(self):
        p=program('out=((n+1)+1)%8;n=n+1;')
        r=transient(p,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],2)

    def test_original_counter_overflow_and_nested_add_are_not_ring_counters(self):
        p=program(initial='n=2147483646;out=0;')
        transient(p,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
        with self.assertRaises(KernelError):
            transient(p,{},[0,1,2],stop=2,max_step=1,kernel=KERNEL)
        for body in ['out=(n+1)%8;n=n+0;', 'out=0*((n+1)%8);n=n+0;',
                     'n=n+1;n=0;out=0;']:
            with self.subTest(body=body),self.assertRaises(KernelError):
                transient(program(body,initial='n=2147483647;out=0;'),{},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_original_division_overflow_and_zero_or_runtime_divisor_reject(self):
        with self.assertRaises(KernelError):
            transient(program('n=n+0;out=n%-1;',initial='n=-2147483648;out=0;'),{},[0,1],stop=1,max_step=1,kernel=KERNEL)
        for body,decl in [('n=n+0;out=n%0;','integer n;real out;'),
                          ('n=n+0;d=d+0;out=n%d;','integer n,d;real out;'),
                          ('n=n+0;out=n%8.0;','integer n;real out;')]:
            with self.subTest(body=body),self.assertRaises(CompileError):
                program(body,decl=decl)

    def test_unselected_dynamic_overflow_is_audited_but_not_executed(self):
        p=program('if(n<0)out=(n+1)%8;n=n+0;out=2;',initial='n=2147483647;out=0;')
        r=transient(p,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],2)
        with self.assertRaises(CompileError):
            program('if(n<0)out=2147483647+1;n=n+0;out=2;')

    def test_raw_typed_boundary_rejects_forged_operands_and_non_event_uses(self):
        import json,subprocess,copy
        p=json.loads(json.dumps(program().to_dict()))
        primitive=p['events'][0]['body'][1]['rhs']
        def request(value):
            r=subprocess.run([str(KERNEL)],input=json.dumps(dict(program=value,driven=[],samples=[],
                transient=dict(pwl=[],output_times=[0,1],stop=1,max_step=1))),text=True,capture_output=True,timeout=10)
            self.assertNotEqual(r.returncode,0,r.stdout)
        for field,value in [('args',[{'op':'affine','constant':1,'terms':[]},{'op':'integer_literal','value':8}]),
                            ('args',[{'op':'integer_state','state':1},{'op':'integer_literal','value':8}]),
                            ('args',[{'op':'integer_state','state':0},{'op':'integer_literal','value':0}]),
                            ('function','divide'),('origin',dict(source='raw.va',line=1,column=1,instance='foreign'))]:
            bad=copy.deepcopy(p);bad['events'][0]['body'][1]['rhs'][field]=value;request(bad)
        bad=copy.deepcopy(p);bad['contributions'][0]['rhs']=primitive;request(bad)
        bad=copy.deepcopy(p);bad['events'][0]['trigger']=dict(kind='cross',guard=primitive,direction=1,time_tolerance=1e-12,expression_tolerance=1e-12);request(bad)
        bad=copy.deepcopy(p);bad['schema_version']=26;request(bad)

    def test_checked_integer_observer_node_does_not_gain_physical_permission(self):
        import json,subprocess
        p=json.loads(json.dumps(program().to_dict()))
        p['events'][0]['body'][1]['rhs']={'op':'checked_integer','value':{'op':'state','state':0},
            'origin':dict(source='raw.va',line=1,column=1,instance='dut')}
        r=subprocess.run([str(KERNEL)],input=json.dumps(dict(program=p,driven=[],samples=[],
            transient=dict(pwl=[],output_times=[0,1],stop=1,max_step=1))),text=True,capture_output=True,timeout=10)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('isolated observer',r.stderr)

    def test_zero_timer_typed_predicate_bootstraps_existing_real_transition_target(self):
        text=model('n=n+1;if(n%8==1)out=11;else out=5;')
        text=text.replace('@(timer(1,1))','@(timer(0,1))').replace('V(y,r)<+out;', 'V(y,r)<+transition(out,0,0.1,0.1);')
        p=compile_sources({'bootstrap.va':text},[Instance('dut','m',dict(y='y',r='0'))])
        r=transient(p,{},[0,0.5,1.5],stop=1.5,max_step=0.1,kernel=KERNEL)
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],[11,11,5])
