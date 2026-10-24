"""A source loop's proof follows its original node through pure inlining."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
import unittest
from unittest.mock import patch
from dataclasses import replace
from evas import compile_sources,Instance,CompileError
from evas.syntax import Parser,Loop,Event,Conditional
from evas.elaboration import inline_functions
from evas.loop_bounds import bound_loops
from evas.frontend import preprocess_sources

def raw_model(text):
    path,tokens=next(iter(preprocess_sources({"loops.va":text})))
    return next(iter(Parser("",path,tokens=tokens).parse_all()))


def source(function='f=x+1.0;',body='for(i=1;i<=n;i=i+1)q=f(i);',extra='',ports='y',physical=True):
    return ('`include "disciplines.vams"\nmodule m('+ports+');'+('output y;electrical y;' if ports else '')+
      'real q;integer i,j,n;'+extra+'analog function real f;input x;real x;begin '+function+'end endfunction '
      'analog begin @(initial_step)begin n=2;q=0;end @(timer(1))begin '+body+' end '+('V(y)<+q;' if physical else '')+'end endmodule')


def build(text,instances=None):
    return compile_sources({'loops.va':text},instances or [Instance('dut','m',dict(y='y'))]).to_dict()


def loops(items):
    for item in items:
        if isinstance(item,Loop):
            yield item;yield from loops(item.body)
        elif isinstance(item,Event):yield from loops(item.body)
        elif isinstance(item,Conditional):
            yield from loops(item.then_body);yield from loops(item.else_body)


def nodes(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from nodes(child)
    elif isinstance(value,(tuple,list)):
        for child in value:yield from nodes(child)


class LoopFunctionIdentity(unittest.TestCase):
    def test_inlining_keeps_same_original_statement_shared_across_views(self):
        raw=raw_model(source())
        original_analog=next(loops(raw.analog));original_process=next(loops(raw.procedure))
        self.assertIs(original_analog,original_process)
        transformed=inline_functions(raw)
        self.assertIs(next(loops(transformed.analog)),next(loops(transformed.procedure)))

    def test_two_trips_keep_three_guarded_checks_and_unique_call_origins(self):
        p=build(source(function='f=exp(x);'))
        conditions=[n for n in nodes(p['events']) if n.get('kind')=='if']
        self.assertEqual(len(conditions),3)
        calls=[n for n in nodes(p['events']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),3)
        self.assertEqual({dict(c['origin']['expansion'])['bounded_loop_trip'] for c in calls},{0,1,2})
        paths=[tuple(map(tuple,op['origin']['expansion'])) for op in p['operators']]
        self.assertEqual(len(paths),3);self.assertEqual(len(set(paths)),3)

    def test_missing_proof_cannot_be_zero_trip_proof(self):
        with patch('evas.loop_bounds._prove',return_value={}):
            with self.assertRaises(CompileError):build(source())

    def test_distinct_original_loops_with_same_token_remain_distinct(self):
        raw=raw_model(source(body='for(i=1;i<=n;i=i+1)q=f(i);for(j=1;j<=n+1;j=j+1)q=f(j);'))
        original=list(loops(raw.analog));self.assertEqual(len(original),2)
        # A deliberately colliding source location must not join two AST nodes.
        second=replace(original[1],token=original[0].token)
        def rewrite(items):
            return tuple(second if item is original[1] else replace(item,body=rewrite(item.body)) if isinstance(item,Event) else item for item in items)
        raw=replace(raw,analog=list(rewrite(raw.analog)),procedure=rewrite(raw.procedure))
        transformed=inline_functions(raw)
        result=list(loops(transformed.analog))
        self.assertIsNot(result[0],result[1]);self.assertEqual(result[0].token,result[1].token)
        self.assertIs(result[0],list(loops(transformed.procedure))[0])
        self.assertIs(result[1],list(loops(transformed.procedure))[1])
        expanded=bound_loops(transformed)
        def guarded(items):
            for item in items:
                if isinstance(item,Conditional):
                    yield item
                    yield from guarded(item.then_body);yield from guarded(item.else_body)
                elif isinstance(item,Event):yield from guarded(item.body)
        checks=list(guarded(expanded.procedure))
        self.assertEqual(len(checks),7) # two trips+terminal, three trips+terminal
        from collections import Counter
        self.assertEqual(sorted(Counter(dict(c.token.expansion)['bounded_loop'] for c in checks).values()),[3,4])

    def test_nested_loops_and_static_genvar_paths_keep_proofs(self):
        build(source(body='for(i=1;i<=n;i=i+1)for(j=1;j<=i;j=j+1)q=q+f(1.0);'))
        text=source(extra='genvar k;',body='for(i=1;i<=n;i=i+1)q=f(i);')
        # Public static genvar expansion around a second source call.
        text=text.replace('V(y)<+q;','for(k=0;k<2;k=k+1)q=f(k);V(y)<+q;')
        build(text)

    def test_one_numeric_observer_runtime_loop_remains_a_single_call(self):
        p=build(source(physical=False))
        self.assertEqual(len([n for n in nodes(p['events']) if n.get('kind')=='loop']),1)
        self.assertEqual(len([n for n in nodes(p['events']) if n.get('op')=='real_call']),1)

    def test_instances_do_not_share_parameter_bindings_or_unknown_bounds(self):
        text=source(function='f=x+offset;',extra='parameter real offset=1;')
        for order in (('a','b'),('b','a')):
            p=build(text,[Instance(name,'m',dict(y=name),dict(offset=1 if name=='a' else 2)) for name in order])
            paths={(n['origin']['instance'],tuple(map(tuple,n['origin']['expansion']))) for n in nodes(p['events']) if n.get('op')=='real_call'}
            self.assertEqual(len(paths),6)
        unknown=source(extra='parameter integer count=2;').replace('n=2;','n=count;')
        with self.assertRaises(CompileError):build(unknown)

    def test_macro_loop_occurrences_keep_distinct_complete_expansions(self):
        text='`define STEP(v) q=f(v);\n'+source(function='f=exp(x);',body='for(i=1;i<=n;i=i+1)`STEP(i) for(j=1;j<=n;j=j+1)`STEP(j)')
        p=build(text)
        origins=[tuple(map(tuple,op['origin']['expansion'])) for op in p['operators']]
        self.assertEqual(len(origins),6);self.assertEqual(len(set(origins)),6)
        self.assertTrue(all(any(kind.startswith('_macro_') for kind,_ in path) for path in origins))

    def test_while_missing_proof_rejects_and_bound_keeps_guard(self):
        text=source(body='i=1;while(i<=n)begin q=f(i);i=i+1;end')
        p=build(text)
        self.assertEqual(len([n for n in nodes(p['events']) if n.get('kind')=='if']),3)
        with patch('evas.loop_bounds._prove',return_value={}):
            with self.assertRaisesRegex(CompileError,'trip-count bound'):build(text)

class LoopArrayEmptyFlow(unittest.TestCase):
    @staticmethod
    def array_source(rhs='a[i]+1.0', extra=''):
        return ('`include "disciplines.vams"\nmodule m(y);output y;electrical y;'
                'real q;integer i,n,a[0:3];' + extra + 'analog begin '
                '@(initial_step)begin n=2;q=0;a[0]=0;a[1]=10;a[2]=20;a[3]=30;end '
                '@(timer(1))begin for(i=1;i<=n;i=i+1)q=' + rhs + ';end V(y)<+q;end endmodule')

    def test_terminal_guard_array_read_keeps_complete_static_tree(self):
        for rhs in ('a[i]+1.0', 'a[i+0]+1.0', 'a[-(-i)]+1.0'):
            with self.subTest(rhs=rhs):
                p=build(self.array_source(rhs))
                self.assertEqual(len([n for n in nodes(p['events']) if n.get('kind')=='if']),3)

    def test_helper_array_read_and_token_origins_keep_trip(self):
        helper='analog function real f;input x;real x;begin f=x+1.0;end endfunction '
        p=build(self.array_source('f(a[i])',helper))
        calls=[n for n in nodes(p['events']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),3)
        origins=[n['origin'] for n in nodes(p['events']) if n.get('op')=='select' and 'origin' in n]
        self.assertTrue(origins)
        # Live singleton reads lower to direct StateRef. The terminal dead
        # read retains a full Select whose token origin must name trip2.
        self.assertEqual({dict(o['expansion'])['bounded_loop_trip'] for o in origins},{2})
        self.assertEqual({dict(c['origin']['expansion'])['bounded_loop_trip'] for c in calls},{0,1,2})

    def test_static_bad_array_reference_is_not_hidden_by_terminal_guard(self):
        for rhs in ('missing[i]', 'a[99]', 'a[i+0.5]'):
            with self.subTest(rhs=rhs):
                with self.assertRaises(CompileError):build(self.array_source(rhs))

    def test_refinement_canonicalizes_empty_arithmetic_without_skipping_reads(self):
        from evas import event_index_domains as d
        from evas.syntax import Expr,Token
        token=Token('i','name',1,1)
        i=Expr('parameter','i',(),token)
        two=Expr('number',2,(),Token('2','number',1,3))
        yes,no=d.refine('<=',i,two,{'i':(3,3)},lambda name:0,{})
        self.assertEqual(yes['i'],d.BOTTOM);self.assertEqual(no['i'],(3,3))
        self.assertFalse(d.within((3,2),0,3))
        reads=[]
        array=Expr('index','a',(i,),token)
        value=Expr('+',None,(i,array),token)
        result=d.evaluate(value,yes,lambda name:0,{'a':(0,)},reads.append)
        self.assertEqual(result,d.BOTTOM);self.assertEqual(reads,[array])
        self.assertEqual(d.clamp((3,2)),d.BOTTOM)
