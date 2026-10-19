"""Public signed integer table composition; expected values use exact Fraction."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE', 'TIMED-OPERATOR']
import json
import os
from pathlib import Path
from fractions import Fraction
import unittest
from evas import CompileError, Instance, compile_sources, transient

KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL', str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))
def model(body,declarations='integer n;'):
    return '`include "disciplines.vams"\nmodule m(y); output y; electrical y; '+declarations+' analog begin '+body+' end endmodule'
def program(body,declarations='integer n;'):
    return compile_sources({'table-composition.va':model(body,declarations)},[Instance('dut','m',dict(y='y'))])
def output(p,times):
    r=transient(p,{},times,stop=times[-1],max_step=.25,kernel=KERNEL)
    return [s['voltages'][r['nodes'].index('y')] for s in r['solutions']]

class IntegerTableComposition(unittest.TestCase):
    def test_public_bitdecode_counter_uses_composed_table(self):
        p=program('@(initial_step)n=0;@(timer(1,1))if(n<255)n=n+1;V(y)<+((n/2)%2);')
        self.assertEqual(output(p,[0,.5,1.25,2.25,3.25,4.25,5.25,6.25]),[0,0,0,1,1,0,0,1])

    def test_public_sixbit_full_wire_uses_original_owner_and_exact_counter_values(self):
        ports=[f'y{k}' for k in range(6)]
        body='@(initial_step)n=0;@(timer(1,1))if(n<=223)n=n+32;else if(n<255)n=255;'
        for k,divisor in enumerate([64,32,16,8,4,2]):body+=f'b{k}=(n/{divisor})%2;V(y{k})<+b{k};'
        source='`include "disciplines.vams"\nmodule m('+','.join(ports)+');output '+','.join(ports)+';electrical '+','.join(ports)+';integer n;real '+','.join(f'b{k}' for k in range(6))+';analog begin '+body+' end endmodule'
        p=compile_sources({'sixbit.va':source},[Instance('dut','m',{name:name for name in ports})])
        owner=p._native_audit;before=owner.used
        import hashlib
        import evas.runtime as runtime
        from unittest.mock import patch
        invoke=runtime._invoke;wire_hashes=[]
        def capture(request,*args,**kwargs):
            wire_hashes.append(hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            return invoke(request,*args,**kwargs)
        with patch('evas.runtime._invoke',side_effect=capture):
            result=transient(p,{},[0]+[k+.25 for k in range(1,9)],stop=8.25,max_step=.25,kernel=KERNEL)
        self.assertEqual(len(wire_hashes),1)
        print('sixbit exact request wire sha256',wire_hashes[0])
        self.assertIs(p._native_audit,owner);self.assertTrue(owner.active);self.assertLessEqual(owner.used,100000)
        for k,divisor in enumerate([64,32,16,8,4,2]):
            expected=[int(Fraction(n,divisor))%2 for n in [0,32,64,96,128,160,192,224,255]]
            index=result['nodes'].index(f'y{k}')
            self.assertEqual([row['voltages'][index] for row in result['solutions']],expected)
        self.assertGreater(owner.counts['wire_visit'],0)
        print('sixbit actual full wire owner',before,owner.used,dict(owner.counts))

    def test_public_signed_nested_arithmetic_matches_exact_integer_oracle(self):
        for initial,step,guard in [(-127,1,'n<127'),(127,-1,'n>-127'),(-3,1,'n<127')]:
            for operation,divisor in [('/',2),('/',-2),('%',3),('%',-3)]:
                with self.subTest(initial=initial,operation=operation,divisor=divisor):
                    text='@(initial_step)n='+str(initial)+';@(timer(1,1))if('+guard+')n=n+('+str(step)+');V(y)<+((n/2)'+operation+'('+str(divisor)+'));'
                    p=program(text)
                    values=[initial]+[initial+step*k for k in range(1,6)]
                    expected=[]
                    for n in values:
                        first=int(Fraction(n,2));q=int(Fraction(first,divisor))
                        expected.append(q if operation=='/' else first-divisor*q)
                    self.assertEqual(output(p,[0,1.25,2.25,3.25,4.25,5.25]),expected)

    def test_original_type_range_and_quotient_bin_refusals_precede_mapping(self):
        cases=[
            ('integer n;','@(initial_step)n=0;@(timer(1,1))if(n<512)n=n+1;V(y)<+((n/2)%1);'),
            ('integer n;','@(initial_step)n=-2147483648;V(y)<+((n/(-1))%1);'),
            ('integer n;','@(initial_step)n=-2147483648;V(y)<+((n%(-1))%1);'),
            ('integer n;','@(initial_step)n=1;V(y)<+((n/2)%0);'),
            ('integer n;','@(initial_step)n=1;V(y)<+((((n+2147483647)-2147483647)/2)%1);'),
            ('integer n;','@(initial_step)n=1;V(y)<+((((n<0)?((n+2147483647)-2147483647):n)/2)%1);'),
            ('real n;','@(initial_step)n=1;V(y)<+((n/2)%1);'),
        ]
        for declaration,text in cases:
            with self.subTest(text=text),self.assertRaises(CompileError):program(text,declaration)

    def test_ineligible_state_value_leaf_keeps_complete_old_wire(self):
        from unittest.mock import patch
        text='@(initial_step)n=1;@(timer(1))n=2;V(y)<+(((n>0)?n:0)%3);'
        current=program(text)
        with patch('evas.instance_compiler.compose_integer_table',return_value=None):
            legacy=program(text)
        self.assertFalse(current._native_audit.active)
        self.assertEqual(current.to_dict(),legacy.to_dict())
        self.assertGreater(current._native_audit.counts['integer_compose_containers'],0)

    def test_original_real_guard_uses_same_old_consumer(self):
        from unittest.mock import patch
        text='@(initial_step)r=-0.5;@(timer(1))r=0.5;V(y)<+(((r>0)?1:0)%2);'
        current=program(text,'real r;')
        with patch('evas.instance_compiler.compose_integer_table',return_value=None):
            legacy=program(text,'real r;')
        self.assertTrue(current._native_audit.active)
        times=[0,0.5,1.25,1.5]
        self.assertEqual(output(current,times),[0,0,1,1])
        self.assertEqual(output(legacy,times),[0,0,1,1])

    def test_equal_mapped_arms_keep_original_guard_origin_and_state_read(self):
        import subprocess
        from dataclasses import asdict,fields
        from evas.ir import Select,StateRef,Affine,Origin
        from evas.native_audit import NativeAudit
        from evas.integer_table_composition import compose_integer_table
        owner=NativeAudit();origin=Origin('guard.va',1,1,'dut');state=StateRef(0)
        table=Select('lt',state,Affine(2.,()),Affine(-3.,()),Affine(3.,()),origin)
        def make(cls,*args):
            owner.debit('emit_object');owner.debit('emit_field',len(fields(cls)));return cls(*args)
        from evas.limits import check_ir
        check_ir(table,origin,work=owner.ir_work,cache=owner.ir_cache)
        mapped=compose_integer_table(table,'%',1,owner=owner,source=origin,make=make)
        self.assertIs(mapped.left,state);self.assertIs(mapped.right,table.right);self.assertIs(mapped.origin,origin)
        self.assertEqual(mapped.then_value.constant,0);self.assertEqual(mapped.else_value.constant,0)
        p=json.loads(json.dumps(program('@(initial_step)n=0;@(timer(0.5))n=1;V(y)<+0;').to_dict()))
        p['states'].append(dict(name='q',instance='dut',kind='real',initial=0.))
        p['events'].append(dict(origin=asdict(origin),trigger=dict(kind='timer',start=.5,period=0.,time_tolerance=1e-12,enabled=True),body=[dict(kind='assign',state=1,rhs=asdict(mapped))]))
        request=dict(program=p,driven=[],samples=[],transient=dict(pwl=[],output_times=[0,.5,1],stop=1,max_step=.25))
        result=subprocess.run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('cannot read state written',result.stdout+result.stderr)

    def test_hidden_wrappers_and_state_leaves_never_become_constant_tables(self):
        from dataclasses import fields
        from evas.ir import Select,StateRef,Affine,Origin,CheckedInteger,Binary
        from evas.native_audit import NativeAudit
        from evas.integer_table_composition import compose_integer_table
        origin=Origin('hidden.va',1,1,'dut')
        for bad,guard in [(StateRef(0),StateRef(0)),(CheckedInteger(Affine(2147483648.,()),origin),StateRef(0))]:
            owner=NativeAudit();table=Select('lt',guard,Affine(1.,()),Affine(0.,()),bad,origin)
            from evas.limits import check_ir
            check_ir(table,origin,work=owner.ir_work,cache=owner.ir_cache)
            calls=[]
            def make(cls,*args):calls.append(cls);owner.debit('emit_object');owner.debit('emit_field',len(fields(cls)));return cls(*args)
            self.assertIsNone(compose_integer_table(table,'%',1,owner=owner,source=origin,make=make))
            self.assertFalse(owner.active);self.assertEqual(calls,[])

    def test_same_owner_full_wire_natural_exhaustion_and_two_sticky_retries(self):
        p=program('@(initial_step)n=0;@(timer(1,1))if(n<255)n=n+1;V(y)<+((n/2)%2);')
        owner=p._native_audit;self.assertTrue(owner.active)
        successes=0
        while True:
            try:p.to_dict();successes+=1
            except CompileError:break
        self.assertGreater(successes,0);self.assertGreater(owner.used,100000)
        copies=owner.counts['copy_container']
        for _ in range(2):
            with self.assertRaises(CompileError):p.to_dict()
            self.assertEqual(owner.counts['copy_container'],copies)
        from evas.integer_table_composition import compose_integer_table
        from evas.ir import Select,StateRef,Affine,Origin
        origin=Origin('retry.va',1,1,'dut')
        table=Select('lt',StateRef(0),Affine(1.,()),Affine(0.,()),Affine(1.,()),origin)
        calls=[]
        for _ in range(2):
            with self.assertRaises(CompileError):
                compose_integer_table(table,'%',2,owner=owner,source=origin,make=lambda *args:calls.append(args))
            self.assertEqual(calls,[])
        print('composition natural owner exhaustion',successes,owner.used,dict(owner.counts))

    def test_inactive_probe_stops_before_unpaid_headroom_then_old_route_remains_available(self):
        from evas.ir import Select,Affine,Origin
        from evas.native_audit import NativeAudit
        from evas.limits import check_ir
        from evas.integer_table_composition import compose_integer_table
        owner=NativeAudit();origin=Origin('headroom.va',1,1,'dut')
        table=Select('lt',Affine(0.,()),Affine(1.,()),Affine(2.,()),Affine(3.,()),origin)
        check_ir(table,origin,work=owner.ir_work,cache=owner.ir_cache)
        owner.debit('actual_prior_work',100000-owner.used-4);calls=[]
        self.assertIsNone(compose_integer_table(table,'%',2,owner=owner,source=origin,make=lambda *args:calls.append(args)))
        self.assertEqual(owner.used,100000);self.assertFalse(owner.active);self.assertEqual(calls,[])

    def test_mutable_or_missing_original_immutable_fact_keeps_old_route(self):
        from evas.ir import Select,Affine,Origin,Term
        from evas.native_audit import NativeAudit
        from evas.limits import check_ir
        from evas.integer_table_composition import compose_integer_table
        origin=Origin('mutable.va',1,1,'dut');calls=[]
        guard=Affine(0.,[]);table=Select('lt',guard,Affine(1.,()),Affine(2.,()),Affine(3.,()),origin)
        owner=NativeAudit();check_ir(table,origin,work=owner.ir_work,cache=owner.ir_cache)
        self.assertNotIn(id(table),owner.ir_cache)
        for _ in range(2):
            self.assertIsNone(compose_integer_table(table,'%',2,owner=owner,source=origin,make=lambda *args:calls.append(args)))
            guard.terms.append(Term(999,0.))
        self.assertFalse(owner.active);self.assertEqual(calls,[])
        frozen=Select('lt',Affine(0.,()),Affine(1.,()),Affine(2.,()),Affine(3.,()),origin)
        first,foreign=NativeAudit(),NativeAudit();check_ir(frozen,origin,work=first.ir_work,cache=first.ir_cache)
        self.assertIsNone(compose_integer_table(frozen,'%',2,owner=foreign,source=origin,make=lambda *args:calls.append(args)))
        self.assertFalse(foreign.active);self.assertEqual(calls,[])

    def test_original_source_ranges_stay_fresh_in_another_instance(self):
        source=model('@(initial_step)n=0;@(timer(1,1))if(n<last)n=n+1;V(y)<+((n/2)%2);','parameter integer last=255;integer n;')
        with self.assertRaisesRegex(CompileError,'quotient-bin budget'):
            compile_sources({'fresh.va':source},[Instance('good','m',dict(y='good')),Instance('bad','m',dict(y='bad'),dict(last=512))])

    def test_guard_checked_operator_hidden_and_role_rejections_stay_in_actual_kernel(self):
        import copy,subprocess
        from dataclasses import asdict,fields
        from evas.ir import Affine,Binary,Select,StateRef,CheckedInteger,OperatorRef,IntegerRound,Origin,Term
        from evas.native_audit import NativeAudit
        from evas.limits import check_ir
        from evas.integer_table_composition import compose_integer_table
        origin=Origin('guard-role.va',1,1,'dut');constant=lambda n:Affine(float(n),())
        base=json.loads(json.dumps(program('@(initial_step)begin n=0;q=0;end @(timer(0.25))q=0;V(y)<+q;','integer n;real q;').to_dict()))
        n=next(i for i,state in enumerate(base['states']) if state['name']=='n');q=next(i for i,state in enumerate(base['states']) if state['name']=='q')
        def legacy(table):
            def tree(first,last):
                if first==last:return constant(first)
                middle=(first+last+1)//2
                return Select('lt',table,constant(middle),tree(first,middle-1),tree(middle,last),origin)
            return Binary('add',table,Binary('multiply',constant(-1),tree(-3,3)))
        cases=[(CheckedInteger(constant(2147483648),origin),'unsupported_transient',False),
            (OperatorRef(999),'unsupported_transient',False),
            (Select('lt',constant(0),constant(1),constant(0),OperatorRef(999),origin),'unsupported_transient',False),
            (Affine(0.,(Term(999,0.),)),'invalid_ir',False),
            (StateRef(n),'unsupported_cross',True),
            (IntegerRound(constant(1.5),origin),'invalid_ir',False)]
        for guard,kind,concurrent in cases:
            owner=NativeAudit();table=Select('lt',guard,constant(1),constant(-3),constant(3),origin)
            check_ir(table,origin,work=owner.ir_work,cache=owner.ir_cache)
            def make(cls,*args):owner.debit('emit_object');owner.debit('emit_field',len(fields(cls)));return cls(*args)
            mapped=compose_integer_table(table,'%',1,owner=owner,source=origin,make=make)
            self.assertIs(mapped.left,guard);self.assertIs(mapped.origin,origin)
            results=[]
            for rhs in [legacy(table),mapped]:
                raw=copy.deepcopy(base);event=next(e for e in raw['events'] if e['trigger']['kind']=='timer')
                event['body']=[dict(kind='assign',state=q,rhs=asdict(rhs))]
                if concurrent:raw['events'].append(dict(origin=asdict(origin),trigger=dict(kind='timer',start=.25,period=0.,time_tolerance=1e-12,enabled=True),body=[dict(kind='assign',state=n,rhs=asdict(constant(1)))]))
                request=dict(program=raw,driven=[],samples=[],transient=dict(pwl=[],output_times=[0,.25,.5],stop=.5,max_step=.25))
                result=subprocess.run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True,timeout=10)
                self.assertNotEqual(result.returncode,0);error=json.loads(result.stderr);self.assertEqual(error['kind'],kind);results.append(error)
            self.assertEqual(results[0],results[1])

if __name__=='__main__':unittest.main()
