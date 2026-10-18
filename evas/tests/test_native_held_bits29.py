"""Event-only logical shifts/masks keep every checked source child and dependency."""
GUARDS = ["LANG", "COMPOSE", "EVENT-ORDER", "EVENT-CONDITIONS"]
import copy
import json
import subprocess
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL
from test_native_integer_events import model


def program(body, initial='n=9;m=2;out=0;'):
    return compile_sources({'bits29.va':model(body,decl='integer n,m;real out;',initial=initial)},
                           [Instance('dut','m',dict(y='y',r='0'))])


def values(p, times=(0,1)):
    r=transient(p,{},list(times),stop=times[-1],max_step=1,kernel=KERNEL)
    return [s['voltages'][r['nodes'].index('y')] for s in r['solutions']]


class NativeHeldBits29(unittest.TestCase):
    def test_wide_event_logical_shift_uses_zero_fill_unsigned_count(self):
        # Independent signed32 word answers, not Python's signed >> or helper output.
        for n,k,want in [(-1,0,-1),(-1,1,2147483647),(-1,31,1),(-1,32,0),
                         (-1,33,0),(-1,-1,0),(-2147483648,1,1073741824),
                         (-2147483648,31,1),(9,1,4)]:
            with self.subTest(n=n,k=k):
                p=program(f'out=n>>{k};n=n+1;',initial=f'n={n};m=2;out=0;')
                self.assertEqual(values(p),[0,want])

    def test_wide_and_reads_updated_local_state_and_nested_checked_subtract(self):
        p=program('n=n+1;out=(n>>1)&1;if((n&1)==0)out=out+10.0;')
        self.assertEqual(values(p,(0,1,2)),[0,11,1])
        self.assertEqual(values(program('out=(n-m)&1;n=n+1;m=m+1;')),[0,1])

    def test_hidden_child_overflow_survives_mask_zero_and_shift_discard(self):
        for body,initial in [
            ('out=(n+1)&0;n=n+1;','n=2147483647;m=2;out=0;'),
            ('out=(n-m)>>32;n=n+1;m=m+1;','n=-2147483648;m=1;out=0;')]:
            with self.subTest(body=body),self.assertRaises(KernelError):
                values(program(body,initial))

    def test_unsigned_and_rejects_real_leaves_runtime_shift_and_new_unsupported_ops(self):
        for expression in ['n>>m','n>>1.0','n&1.0','out&1','n<<1','n|1','n^1','~n']:
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                program('out='+expression+';n=n+1;m=m+1;')
        for expression in ['((2147483647+1)&0)','((-2147483648-1)>>32)']:
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                program('if(n<0)out='+expression+';n=n+1;')

    def test_hidden_illegal_dependencies_and_zero_mask_preserve_batch_reads(self):
        for expr in ['(V(y)&0)','(out&0)']:
            with self.subTest(expr=expr),self.assertRaises(CompileError):
                program('if(n<0)out='+expr+';n=n+1;')
        text=model('out=n&0;',decl='integer n;real out;',initial='n=9;out=0;')
        text=text.replace('@(timer(1,1))begin out=n&0;end',
            '@(timer(1,1))begin n=n+1;end @(timer(1,1))begin out=n&0;end')
        p=compile_sources({'conflict29.va':text},[Instance('dut','m',dict(y='y',r='0'))])
        with self.assertRaisesRegex(KernelError,'cannot read state written'):
            values(p)

    def test_unselected_dynamic_child_error_is_lazy_but_original_tree_is_audited(self):
        p=program('if(n<0)out=(n+1)&0;n=n+0;out=2;',initial='n=2147483647;m=2;out=0;')
        self.assertEqual(values(p),[0,2])

    def test_new_nodes_keep_ordinary_contribution_and_raw_protocol_gates(self):
        for expression in ['(n>>1)&1','n&1']:
            text=model('n=n+1;').replace('V(y,r)<+out;',f'V(y,r)<+{expression};')
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                compile_sources({'target29.va':text},[Instance('dut','m',dict(y='y',r='0'))])
        p=json.loads(json.dumps(program('out=(n>>1)&1;n=n+1;').to_dict()))
        primitive=p['events'][0]['body'][0]['rhs']
        def reject(bad):
            r=subprocess.run([str(KERNEL)],input=json.dumps(dict(program=bad,driven=[],samples=[],
                transient=dict(pwl=[],output_times=[0,1],stop=1,max_step=1))),text=True,capture_output=True,timeout=10)
            self.assertNotEqual(r.returncode,0,r.stdout)
        for bad_count in [dict(op='integer_state',state=1),dict(op='integer_literal',value=2147483648),
                          dict(op='affine',constant=1,terms=[])]:
            bad=copy.deepcopy(p);bad['events'][0]['body'][0]['rhs']['args'][0]['args'][1]=bad_count;reject(bad)
        for function in ['shift_left','bit_or','bit_xor','negate','divide']:
            bad=copy.deepcopy(p);bad['events'][0]['body'][0]['rhs']['function']=function;reject(bad)
        for operand in [dict(op='integer_state',state=2),dict(op='integer_state',state=999),dict(op='affine',constant=1,terms=[])]:
            bad=copy.deepcopy(p);bad['events'][0]['body'][0]['rhs']['args'][1]=operand;reject(bad)
        bad=copy.deepcopy(p);bad['events'][0]['body'][0]['rhs']['args'][0]['origin']['instance']='foreign';reject(bad)
        bad=copy.deepcopy(p);bad['schema_version']=28;reject(bad)
        bad=copy.deepcopy(p);bad['contributions'][0]['rhs']=primitive;reject(bad)
        bad=copy.deepcopy(p);bad['events'][0]['trigger']=dict(kind='cross',guard=primitive,direction=1,time_tolerance=1e-12,expression_tolerance=1e-12);reject(bad)
        bad=copy.deepcopy(p);bad['operators']=[dict(kind='slew',input=primitive,rise=1,fall=1,origin=primitive['origin'])];reject(bad)
