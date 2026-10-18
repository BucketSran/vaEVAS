"""Source-typed event subtraction and dynamic remainder keep ordered i32 checks."""
GUARDS = ["LANG", "COMPOSE", "EVENT-ORDER", "EVENT-CONDITIONS"]
import copy
import json
import subprocess
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL
from test_native_integer_events import model


def program(body, initial='n=9;d=8;m=2;out=0;'):
    text=model(body,decl='integer n,d,m;real out;',initial=initial)
    return compile_sources({'integer28.va':text},[Instance('dut','m',dict(y='y',r='0'))])


def values(p, times=(0,1)):
    r=transient(p,{},list(times),stop=times[-1],max_step=1,kernel=KERNEL)
    return [s['voltages'][r['nodes'].index('y')] for s in r['solutions']]


class NativeInteger28(unittest.TestCase):
    def test_runtime_remainder_uses_current_divisor_and_source_sign(self):
        # Literal answers follow n=d*trunc(n/d)+r, not Python's floor modulo.
        for n,d,want in [(-9,8,-1),(9,-8,1),(-9,-8,-1),(9,8,1)]:
            with self.subTest(n=n,d=d):
                self.assertEqual(values(program('n=n+0;d=d+0;out=n%d;',
                    initial=f'n={n};d={d};m=2;out=0;')),[0,want])
        p=program('out=n%d;d=3;out=10.0*out+n%d;n=n+1;')
        self.assertEqual(values(p,(0,1,2)),[0,10,11])

    def test_binary_subtraction_precedes_real_promotion_and_later_predicate(self):
        self.assertEqual(values(program('out=(n-m+0.0)/2.0;n=n+1;m=m+1;')),[0,3.5])
        p=program('if(n%d==d-1)out=9;else out=4;n=n+1;d=d+0;',
                  initial='n=5;d=3;m=2;out=0;')
        self.assertEqual(values(p,(0,1,2)),[0,9,4])

    def test_nested_divisor_and_subtraction_observe_prior_assignments(self):
        p=program('d=m+1;out=(n-(m-1))%d;m=m+1;n=n+0;')
        self.assertEqual(values(p,(0,1,2)),[0,2,3])

    def test_runtime_failures_retain_each_original_node_before_clamp_or_cancel(self):
        cases=[('out=n%d;n=n+1;d=d+1;d=1;', 'n=9;d=0;m=0;out=0;'),
               ('out=n%d;n=0;', 'n=-2147483648;d=-1;m=0;out=0;'),
               ('out=0.0*(n-m);n=n+1;m=m+1;n=0;m=0;', 'n=-2147483648;d=8;m=1;out=0;'),
               ('out=(n-m)%d;n=n+1;m=m+1;n=0;m=0;', 'n=2147483647;d=8;m=-1;out=0;')]
        for body,initial in cases:
            with self.subTest(body=body),self.assertRaises(KernelError):
                values(program(body,initial))

    def test_static_constant_and_type_failures_do_not_become_runtime_fallbacks(self):
        for body in ['out=n%0;','out=n%8.0;','out=2147483647+1;',
                     'out=-2147483648-1;','out=0.0*(2147483647+1);',
                     'if(n<0)out=1%0;','out=n/(d+0);',
                     'out=(n<<1);','out=(-n)%8;']:
            with self.subTest(body=body),self.assertRaises(CompileError):
                program(body+'n=n+1;d=d+1;m=m+1;')

    def test_raw_new_trees_keep_operand_owner_version_and_consumer_gates(self):
        p=json.loads(json.dumps(program('n=n+1;d=d+1;out=(n-m)%d;m=m+1;').to_dict()))
        slot=next(i for i,b in enumerate(p['events'][0]['body'])
                  if b.get('rhs',{}).get('function')=='remainder')
        primitive=p['events'][0]['body'][slot]['rhs']
        def reject(bad):
            r=subprocess.run([str(KERNEL)],input=json.dumps(dict(program=bad,driven=[],samples=[],
                transient=dict(pwl=[],output_times=[0,1],stop=1,max_step=1))),text=True,capture_output=True,timeout=10)
            self.assertNotEqual(r.returncode,0,r.stdout)
        for function in ['divide','multiply','negate','bitand']:
            bad=copy.deepcopy(p);bad['events'][0]['body'][slot]['rhs']['function']=function;reject(bad)
        for operand in [dict(op='integer_state',state=3),dict(op='integer_state',state=999),
                        dict(op='affine',constant=3,terms=[]),dict(op='integer_literal',value=0)]:
            bad=copy.deepcopy(p);bad['events'][0]['body'][slot]['rhs']['args'][1]=operand;reject(bad)
        bad=copy.deepcopy(p);bad['events'][0]['body'][slot]['rhs']['args'][0]['origin']['instance']='foreign';reject(bad)
        bad=copy.deepcopy(p);bad['schema_version']=27;reject(bad)
        bad=copy.deepcopy(p);bad['contributions'][0]['rhs']=primitive;reject(bad)
        bad=copy.deepcopy(p);bad['events'][0]['trigger']=dict(kind='cross',guard=primitive,direction=1,time_tolerance=1e-12,expression_tolerance=1e-12);reject(bad)
        bad=copy.deepcopy(p);bad['operators']=[dict(kind='transition',input=primitive,delay=0,rise=0.1,fall=0.1,origin=primitive['origin'])];reject(bad)

    def test_unselected_runtime_zero_is_not_evaluated_but_static_errors_remain(self):
        p=program('if(n<0)out=n%d;n=n+1;d=d+1;out=2;',initial='n=9;d=0;m=2;out=0;')
        self.assertEqual(values(p),[0,2])
