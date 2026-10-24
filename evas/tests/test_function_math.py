"""Pure helper math admission and source call occurrence identities (no kernel)."""
GUARDS = ['LANG', 'COMPOSE']
import unittest
from evas import compile_sources, Instance, CompileError


def compile_body(body='q=f(1.0);', function='f=exp(x);', instances=None):
    source=('`include "disciplines.vams"\nmodule m(u,y,r);input u;output y;inout r;'
            'electrical u,y,r;real q,a; analog function real f; input x;real x;'
            'begin '+function+' end endfunction analog begin '+body+' V(y,r)<+q;end endmodule')
    return compile_sources({'helper.va':source},instances or [Instance('dut','m',dict(u='u',y='y',r='0'))])


class FunctionMath(unittest.TestCase):
    def test_six_math_bodies_are_admitted(self):
        for op in ('sin','cos','exp','ln','sqrt','tanh'):
            with self.subTest(op=op):
                program=compile_body(function='f='+op+'(x);')
                program.to_dict()

    def test_original_argument_and_body_refusals_remain(self):
        for function in ('f=V(u,r);','f=idt(x,0);','f=transition(x,0,1n,1n);', 'f=absdelay(x,1n);'):
            with self.subTest(function=function),self.assertRaisesRegex(CompileError,'pure analog functions'):
                compile_body(function=function)
        with self.assertRaisesRegex(CompileError,'function arguments cannot contain history'):
            compile_body(body='q=f(exp(1));',function='f=x;')

    def test_different_call_occurrences_and_real_boundaries(self):
        program=compile_body('a=f(1.0);q=f(2.0);').to_dict()
        ops=[op for op in program['operators'] if op.get('kind') in ('sin','math') or op.get('function')=='exp']
        self.assertEqual(len(ops),2)
        self.assertNotEqual(ops[0]['origin']['expansion'],ops[1]['origin']['expansion'])




def all_nodes(value):
    if isinstance(value,dict):
        yield value
        for item in value.values():yield from all_nodes(item)
    elif isinstance(value,(list,tuple)):
        for item in value:yield from all_nodes(item)


class FunctionMathOccurrence(unittest.TestCase):
    def test_repeated_local_and_obligations_share_one_occurrence(self):
        p=compile_body(function='f=exp(x);f=f+f;').to_dict()
        self.assertEqual(len(p['operators']),1)
        references=[n['operator'] for n in all_nodes(p['procedures']) if n.get('op')=='operator']
        self.assertTrue(references)
        self.assertEqual(set(references),{0})
        boundaries={n['kind'] for n in all_nodes(p) if n.get('op')=='real_boundary'}
        self.assertTrue({'argument','return'}.issubset(boundaries))
        self.assertTrue(any(n.get('op')=='real_binary' for n in all_nodes(p)))

    def test_same_helper_snapshot_occurrences_and_instances_are_distinct(self):
        body='a=1.0;q=f(a);a=2.0;q=f(a);'
        for instances in ([Instance('a','m',dict(u='u1',y='y1',r='0')),Instance('b','m',dict(u='u2',y='y2',r='0'))],
                          [Instance('b','m',dict(u='u2',y='y2',r='0')),Instance('a','m',dict(u='u1',y='y1',r='0'))]):
            p=compile_body(body,instances=instances).to_dict()
            self.assertEqual(len(p['operators']),4)
            origins=[op['origin'] for op in p['operators']]
            keys={(o['instance'],tuple(map(tuple,o['expansion']))) for o in origins}
            self.assertEqual(len(keys),4)
            self.assertEqual({o['instance'] for o in origins},{'a','b'})

    def test_source_views_keep_one_function_call_tag(self):
        from evas.frontend import parse_sources
        from evas.syntax import Expr
        source=('`include "disciplines.vams"\nmodule m(y); output y;electrical y;real q; analog function real f; input x;real x;begin f=exp(x);end endfunction '
                'analog begin @(initial_step)q=f(1);@(timer(1))q=f(2);end endmodule')
        model=parse_sources({'views.va':source})['m']
        def tags(value):
            result=set();pending=[value]
            from dataclasses import fields,is_dataclass
            while pending:
                item=pending.pop()
                if isinstance(item,Expr) and item.op=='exp':result.add(item.expansion)
                if is_dataclass(item):pending.extend(getattr(item,f.name) for f in fields(item))
                elif isinstance(item,(tuple,list)):pending.extend(item)
            return result
        self.assertEqual(tags(model.procedure),tags((model.analog,model.initial,model.events)))
        self.assertEqual(len(tags(model.procedure)),2)

    def test_unselected_negative_domain_retains_math_and_source_checks(self):
        p=compile_body('q=f(-1.0);','if(x>0)f=sqrt(x);else f=0;').to_dict()
        self.assertEqual(p['operators'][0]['function'],'sqrt')
        self.assertTrue(any(n.get('kind')=='procedure_if' for n in all_nodes(p)))
        for function in ('if(x>0)f=sqrt(missing);else f=0;',
                         'if(x>0)f=V(missing);else f=0;',
                         'if(x>0)f=missingfn(x);else f=0;'):
            with self.subTest(function=function),self.assertRaises(CompileError):
                compile_body('q=f(-1.0);',function)

    def test_initial_event_math_has_call_origins_and_no_extra_gates(self):
        p=compile_body('@(initial_step)q=f(1.0);@(timer(1))q=f(2.0);').to_dict()
        returns=[n for n in all_nodes(p['events']) if n.get('op')=='real_boundary' and n.get('kind')=='return']
        self.assertEqual(len(returns),2)
        self.assertNotEqual(returns[0]['origin']['expansion'],returns[1]['origin']['expansion'])
        self.assertEqual(len(p['events']),2)

    def test_original_integer_and_voltage_argument_contexts(self):
        # Existing argument qualification permits a physical voltage argument;
        # it still forbids operators even though the helper body now accepts math.
        compile_body('q=f(V(u,r));').to_dict()
        for argument in ('exp(1.0)','idt(1.0,0)','unknownfn(1.0)'):
            with self.subTest(argument=argument),self.assertRaises(CompileError):
                compile_body('q=f('+argument+');')

    def test_registry_preserves_signed_zero_and_input_binding_identity(self):
        from evas.memoryless_operators import Registry
        from evas.native_audit import NativeAudit
        from evas.ir import Affine,MathFunction,Origin,RealLocal
        owner=NativeAudit();owner.activate(None);registry=Registry(owner);operators=[]
        origin=Origin('x',1,2,'dut',(('function_call',1),))
        for a in (0.0,-0.0):registry.register(MathFunction('exp',Affine(a,()),origin),operators)
        self.assertEqual(len(operators),2)
        for a in (0,1):registry.register(MathFunction('exp',RealLocal(a),origin),operators)
        self.assertEqual(len(operators),4)
        before=owner.used
        self.assertEqual(registry.register(MathFunction('exp',RealLocal(1),origin),operators),3)
        self.assertGreater(owner.used,before)
        self.assertEqual(len(operators),4)
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_registry_failed_retry_uses_original_owner(self):
        from evas.memoryless_operators import Registry
        from evas.native_audit import NativeAudit
        from evas.ir import Affine,MathFunction,Origin
        from evas.limits import MAX_IR_ITEMS
        owner=NativeAudit();owner.activate(None);registry=Registry(owner);operators=[]
        spec=MathFunction('exp',Affine(1.0,()),Origin('x',1,2,'dut'))
        registry.register(spec,operators)
        owner.debit('test_fill_original_request_allowance',MAX_IR_ITEMS-owner.used)
        for _ in range(2):
            before=owner.used
            with self.assertRaises(CompileError) as failure:registry.register(spec,operators)
            self.assertEqual(failure.exception.diagnostic['code'],'resource_budget')
            self.assertGreater(owner.used,before)
        self.assertEqual(len(operators),1)

    def test_nested_helpers_keep_full_expansion_path(self):
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;real q;'
                'analog function real g;input x;real x;begin g=exp(x);end endfunction '
                'analog function real f;input x;real x;begin f=g(x);end endfunction '
                'analog begin q=f(1);q=f(2);V(y)<+q;end endmodule')
        p=compile_sources({'nested.va':source},[Instance('dut','m',dict(y='y'))]).to_dict()
        self.assertEqual(len(p['operators']),2)
        paths=[o['origin']['expansion'] for o in p['operators']]
        self.assertTrue(all(len(path)==2 for path in paths))
        self.assertNotEqual(paths[0],paths[1])

    def test_default_aggregate_limit_and_fresh_request(self):
        with self.assertRaises(CompileError) as failure:
            compile_body('q=f(1.0);'*100).to_dict()
        self.assertEqual(failure.exception.diagnostic['code'],'resource_budget')
        compile_body('q=f(1.0);'*10).to_dict()

    def test_math_operand_keeps_each_source_real_operation(self):
        p=compile_body(function='f=exp((9007199254740992.0+x)-9007199254740992.0);').to_dict()
        operand=p['operators'][0]['input']
        self.assertEqual(operand['op'],'real_binary')
        self.assertEqual(operand['operation'],'subtract')
        self.assertEqual(operand['left']['operation'],'add')
        self.assertEqual(operand['left']['right']['op'],'real_local')
        self.assertTrue(any(n.get('op')=='real_boundary' and n.get('kind')=='argument' for n in all_nodes(p['procedures'])))
        self.assertTrue(operand['origin']['expansion'])

    def test_ordinary_non_function_math_decision_retains_existing_refusal(self):
        for body in ('a=1;q=(a>0)?sqrt(a):0;',
                     'a=1;q=(a>0)?exp(a):0;'):
            with self.subTest(body=body),self.assertRaisesRegex(CompileError,'decision expressions do not support waveform'):
                compile_body(body,function='f=x;')
        # Unused helper declaration cannot grant provenance to caller math.
        with self.assertRaisesRegex(CompileError,'decision expressions do not support waveform'):
            compile_body('a=f(1);q=(a>0)?sqrt(a):0;')
