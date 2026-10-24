"""Compile-only condition structure; independent finite source-behavior oracle."""
GUARDS=['LANG']
import unittest
from evas import compile_sources,Instance
from evas.frontend import parse_sources


def source(branches,context='event'):
    if context=='initial':body='@(initial_step) begin '+branches+' end'
    elif context=='event':body='@(initial_step) begin xs=0; ys=0; sel=0; end @(cross(V(u,r)-0.5,+1)) begin '+branches+' end'
    else:body=branches
    return '`include "disciplines.vams"\nmodule m(u,y,r);input u;output y;inout r;electrical u,y,r;integer xs,ys,sel;analog begin '+body+' V(y,r)<+sel;end endmodule'


def chain(levels):
    return ' else '.join('if(xs=='+str(i)+' && ys!='+str(i)+') sel='+str(i+1)+';' for i in range(levels))+' else sel=99;'


class ConditionSharing(unittest.TestCase):
    def test_long_compound_else_chain_parses_and_compiles(self):
        s=source(chain(12))
        parsed=parse_sources({'condition.va':s})['m']
        self.assertTrue(parsed.procedure)
        compile_sources({'condition.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()

    def test_initial_and_ordinary_paths_keep_one_source_condition(self):
        for context in ['initial','ordinary']:
            s=source(chain(6),context)
            if context=='ordinary':
                s=s.replace('integer xs,ys,sel;', 'real xs,ys,sel;').replace('analog begin ', 'analog begin xs=V(u,r);ys=0;',1)
            with self.subTest(context=context):
                compile_sources({'condition.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()

    def test_event_branches_match_independent_python_oracle(self):
        from evas.ir import (Affine,StateRef,IntegerState,IntegerLiteral,Select,
                             Binary,RealBinary,RealBoundary,Assignment,Conditional,
                             CheckedInteger,IntegerPrimitive)
        def execute(body,initial):
            states=dict(initial)
            divisions=[]
            def relation(op,a,b):
                return {'lt':lambda:a<b,'le':lambda:a<=b,'gt':lambda:a>b,'ge':lambda:a>=b}[op]()
            def value(expr):
                if isinstance(expr,Affine):
                    self.assertFalse(expr.terms)
                    return expr.constant
                if isinstance(expr,(StateRef,IntegerState)):return states[expr.state]
                if isinstance(expr,IntegerLiteral):return expr.value
                if isinstance(expr,(RealBoundary,CheckedInteger)):return value(expr.value)
                if isinstance(expr,Select):
                    return value(expr.then_value if relation(expr.relation,value(expr.left),value(expr.right)) else expr.else_value)
                if isinstance(expr,IntegerPrimitive):
                    args=[value(a) for a in expr.args]
                    return {'add':lambda:args[0]+args[1],'subtract':lambda:args[0]-args[1]}[expr.function]()
                if isinstance(expr,(Binary,RealBinary)):
                    a,b=value(expr.left),value(expr.right)
                    op=expr.operation if isinstance(expr,RealBinary) else expr.op
                    if op=='divide':divisions.append((a,b))
                    return {'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:a/b}[op]()
                self.fail('test oracle lacks '+type(expr).__name__)
            def body_steps(statements):
                for statement in statements:
                    if isinstance(statement,Assignment):states[statement.state]=value(statement.rhs)
                    elif isinstance(statement,Conditional):
                        body_steps(statement.then_body if relation(statement.relation,value(statement.left),value(statement.right)) else statement.else_body)
                    else:self.fail('test oracle lacks '+type(statement).__name__)
            body_steps(body)
            return states,divisions
        def compiled(branches):
            p=compile_sources({'condition.va':source(branches)},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
            return p,{state.name:i for i,state in enumerate(p.states)}
        p,ids=compiled(chain(12))
        for xs in range(-1,14):
            for ys in [xs,xs+1,-1]:
                expected=next((i+1 for i in range(12) if xs==i and ys!=i),99)
                got,_=execute(p.events[0].body,{ids['xs']:xs,ids['ys']:ys,ids['sel']:-7})
                self.assertEqual(got[ids['sel']],expected)
        cases=[('if(xs<0 && 1.0/ys<0) sel=1; else sel=2;',1,0,2,0),
               ('if(xs>0 || 1.0/ys>0) sel=1; else sel=2;',1,0,1,0),
               ('if(xs<0 && 1.0/ys<0) sel=1; else sel=2;',-1,-1,1,1),
               ('if(xs>0 || 1.0/ys>0) sel=1; else sel=2;',0,-1,2,1)]
        for code,xs,ys,expected,count in cases:
            p,ids=compiled(code)
            got,divisions=execute(p.events[0].body,{ids['xs']:xs,ids['ys']:ys,ids['sel']:-7})
            self.assertEqual((got[ids['sel']],len(divisions)),(expected,count))
        p,ids=compiled('xs=xs+1; if(xs==1 && ys!=0) begin xs=7;sel=11;end else begin xs=8;sel=12;end if(xs==7)sel=sel+1;')
        got,_=execute(p.events[0].body,{ids['xs']:0,ids['ys']:1,ids['sel']:-7})
        self.assertEqual((got[ids['xs']],got[ids['sel']]),(7,12))

    def test_new_boolean_form_keeps_dead_call_parameter_proof_and_static_errors(self):
        from evas import CompileError
        for predicate in ['gate','gate!=0','gate>0 && gate<2','!(gate==0)']:
            s=source('if('+predicate+') sel=$anything(1); else sel=2;').replace('integer xs,ys,sel;', 'parameter integer gate=0; integer xs,ys,sel;')
            with self.subTest(predicate=predicate):
                compile_sources({'condition.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()
        for predicate in ['xs','xs!=0','xs>0 && ys<2']:
            s=source('if('+predicate+') sel=$anything(1); else sel=2;')
            with self.subTest(predicate=predicate):
                with self.assertRaises(CompileError) as got:
                    compile_sources({'condition.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
                self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')

    def test_source_and_event_ir_contain_each_source_arm_once(self):
        from evas.syntax import Conditional as SourceIf,Assignment as SourceAssign,Event as SourceEvent
        from evas.ir import Conditional,Assignment
        s=source(chain(12))
        model=parse_sources({'condition.va':s})['m']
        p=compile_sources({'condition.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
        def count(body,if_type,assignment_type):
            conditions=assignments=0
            for item in body:
                if isinstance(item,if_type):
                    conditions+=1
                    for arm in [item.then_body,item.else_body]:
                        a,b=count(arm,if_type,assignment_type);conditions+=a;assignments+=b
                elif isinstance(item,assignment_type):assignments+=1
            return conditions,assignments
        self.assertEqual(count(next(item.body for item in model.procedure if isinstance(item,SourceEvent) and any(t.kind=='cross' for t in item.triggers)),SourceIf,SourceAssign),(12,13))
        self.assertEqual(count(p.events[0].body,Conditional,Assignment),(12,13))
        from evas.ir import CrossTrigger,InitialStepTrigger
        self.assertEqual(sum(isinstance(event.trigger,CrossTrigger) for event in p.events),1)
        self.assertEqual(sum(isinstance(event.trigger,InitialStepTrigger) for event in p.events),1)

    def test_predicate_domains_and_read_positions_keep_old_admission(self):
        from evas import CompileError
        prefix=('`include "disciplines.vams"\nmodule m(u,y,r);input u;output y;inout r;electrical u,y,r;'
                'integer idx;real a[0:3],q,x;analog begin @(initial_step)begin idx=0;'
                'a[0]=0;a[1]=1;a[2]=2;a[3]=3;q=0;x=0;end @(cross(V(u,r)-0.5,+1))begin ')
        good=['idx=idx+1;if(idx>=0&&idx<=3)q=a[idx];else q=0;',
              'idx=idx+1;if(idx>=0&&idx<=3&&a[idx]>0)q=1;else q=0;',
              'idx=idx+1;if(idx<0||idx>3||a[idx]<0)q=1;else q=0;',
              'idx=idx+1;if(idx==0||idx==1)q=a[idx];else q=0;',
              'idx=idx+1;if(idx!=0&&idx>=1&&idx<=3)q=a[idx];else q=0;',
              'x=V(u,r);if(x>=0&&x<=3)q=floor(x);else q=0;',
              'x=V(u,r);if(x>=0&&x<=3&&floor(x)>0)q=1;else q=0;']
        bad=['idx=idx+1;if(a[idx]>0&&idx>=0&&idx<=3)q=1;else q=0;',
             'x=V(u,r);if(floor(x)>0&&x>=0&&x<=3)q=1;else q=0;']
        for body in good:
            compile_sources({'ranges.va':prefix+body+'end V(y,r)<+q;end endmodule'},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()
        for body in bad:
            with self.assertRaises(CompileError):
                compile_sources({'ranges.va':prefix+body+'end V(y,r)<+q;end endmodule'},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])

    def test_original_cap_and_same_owner_exhaustion_are_preserved(self):
        from evas import CompileError
        from evas.limits import MAX_IR_ITEMS
        from evas.native_audit import NativeAudit
        from evas.condition_domains import compact_domains
        self.assertEqual(MAX_IR_ITEMS,100000)
        huge=source('sel=0;'*16000)
        with self.assertRaises(CompileError) as got:
            compile_sources({'huge.va':huge},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
        self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
        from evas.syntax import Event as SourceEvent
        model=parse_sources({'condition.va':source('if(xs==0&&ys!=0)sel=1;else sel=2;')})['m']
        guard=next(item.body[0] for item in model.procedure if isinstance(item,SourceEvent) and any(t.kind=='cross' for t in item.triggers))
        owner=NativeAudit();owner.activate(guard.token);owner.debit('earlier_actual_work',MAX_IR_ITEMS-owner.used-1)
        reached=[]
        def leaf(*args):reached.append(True);self.fail('proof ran after exhaustion')
        for attempt in range(2):
            with self.assertRaises(CompileError) as got:
                compact_domains(guard.relation,guard.left,guard.right,{'xs':(0,1),'ys':(0,1)},
                    refine=leaf,hull=leaf,work=lambda count:owner.debit('domain_actual_work',count))
            self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
        self.assertEqual(reached,[])
        self.assertGreater(owner.used,MAX_IR_ITEMS)

    def test_ir32_legacy_select_statement_expansion_stays_unchanged(self):
        from evas.instance_compiler import InstanceCompiler
        from evas.ir import Affine,Select,Origin,Assignment,Conditional
        c=InstanceCompiler.__new__(InstanceCompiler)
        c.procedure_builder=None;c.compact_event_candidate=lambda:False
        c.make_ir=lambda cls,*args:cls(*args)
        zero,one=Affine(0.,()),Affine(1.,())
        origin=Origin('condition.va',1,1,'dut',())
        choice=Select('lt',zero,one,one,zero,origin)
        yes,no=(Assignment(0,one),),(Assignment(0,zero),)
        old=c.event_conditional('gt',choice,zero,yes,no,origin)
        self.assertEqual(len(old),1)
        self.assertIs(old[0].left,zero)
        self.assertIsInstance(old[0].then_body[0],Conditional)
        c.procedure_builder=object()
        retained=c.event_conditional('gt',choice,zero,yes,no,origin)
        self.assertIs(retained[0].left,choice)
        self.assertIs(retained[0].then_body,yes)
        self.assertIs(retained[0].else_body,no)


    def test_partial_parameter_proofs_keep_unknown_state_unknown(self):
        good=[('gate>0&&q>0','q=$anything(1);','q=2;'),
              ('q>0&&gate>0','q=$anything(1);','q=2;'),
              ('gate>0&&(q+1)>0','q=$anything(1);','q=2;'),
              ('gate<=0||q>0','q=2;','q=$anything(1);'),
              ('q>0||gate<=0','q=2;','q=$anything(1);')]
        for predicate,yes,no in good:
            s=('`include "disciplines.vams"\nmodule m(u,y,r);input u;output y;inout r;electrical u,y,r;parameter integer gate=0;real q;'
               'analog begin @(initial_step)begin q=0;if('+predicate+')'+yes+'else '+no+'end V(y,r)<+q;end endmodule')
            with self.subTest(predicate=predicate):
                compile_sources({'partial.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()

    def test_short_circuit_call_operand_keeps_execution_and_static_legality(self):
        from evas import CompileError
        def compile_guard(predicate):
            s=('`include "disciplines.vams"\nmodule m(u,y,r);input u;output y;inout r;electrical u,y,r;'
               'parameter integer gate=0;real q;analog begin @(initial_step)begin q=0;if('+predicate+')q=1;else q=2;end V(y,r)<+q;end endmodule')
            return compile_sources({'partial.va':s},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()
        for predicate in ['gate>0&&$anything(1)>0','gate<=0||$anything(1)>0','gate>0&&$anything(1.0/0.0)>0']:
            with self.subTest(predicate=predicate):compile_guard(predicate)
        for predicate in ['$anything(1)>0&&gate>0','gate<=0&&q>0&&$anything(1)>0','gate>0||q>0&&$anything(1)>0']:
            with self.subTest(predicate=predicate):
                with self.assertRaises(CompileError) as got:compile_guard(predicate)
                self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')
        for predicate in ['gate>0&&$anything(missing)>0','gate>0&&$anything(1.0&1)>0']:
            with self.subTest(predicate=predicate):
                with self.assertRaises(CompileError):compile_guard(predicate)
