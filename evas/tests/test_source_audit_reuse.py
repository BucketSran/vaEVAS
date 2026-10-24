"""Overlapping typed source prefixes retain every original admission role."""
GUARDS = ['LANG', 'EVENT-CONDITIONS', 'COMPOSE']
import unittest
from unittest.mock import patch
from evas import compile_sources, Instance, CompileError


def weighted(n=10):
    return '+'.join(str(1<<i)+'*(V(u)>0.'+str(i)+')' for i in range(n))


def build(rhs=None, body=None, declarations='', instances=None, wire=False):
    source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'
      'integer c;real q;parameter integer gate=0;'+declarations+'analog begin '
      +(body or '@(initial_step)c=0;@(timer(1))c='+(rhs or weighted())+';')+
      'V(y)<+c;end endmodule')
    p=compile_sources({'audit-reuse.va':source},instances or [Instance('dut','m',dict(u='u',y='y'))])
    return p.to_dict() if wire else p


def nodes(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from nodes(child)
    elif isinstance(value,(tuple,list)):
        for child in value:yield from nodes(child)


class SourceAuditReuse(unittest.TestCase):
    def test_compound_integer_source_reuses_paid_lowering_not_source_operations(self):
        p=build();owner=p._native_audit
        self.assertTrue(owner.active)
        self.assertGreater(owner.counts['source_audit_lower_cache_lookup'],
                           owner.counts['source_audit_lower_cache_insert']//2)
        wire=p.to_dict()
        selects=[n for n in nodes(wire['events']) if n.get('op')=='select']
        self.assertEqual(len(selects),10)
        self.assertEqual(len({n['origin']['column'] for n in selects}),10)
        self.assertTrue(all(n['origin']['instance']=='dut' for n in selects))
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_intermediate_overflow_is_not_hidden_by_root_allowance_or_cancellation(self):
        for value in ('2147483647','-2147483648'):
            sign='+' if value[0]!='-' else '-'
            rhs='(((V(u)>0.0)?'+value+':'+value+')'+sign+'1)'+('-1' if sign=='+' else '+1')+'+0+0'
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):build(rhs)
        # A final safe bound is accepted without deleting any source comparison.
        self.assertTrue(build('((V(u)>0.0)?2147483646:0)+1-1',wire=True))

    def test_checked_function_and_unused_actual_keep_original_obligations(self):
        function='analog function real f;input x,z;real x,z;begin f=x;end endfunction '
        p=build(body='@(initial_step)c=0;@(timer(1))q=f(1.0,(V(u)>0.0)?1.0/0.0:0.0);',declarations=function,wire=True)
        call=next(n for n in nodes(p['events']) if n.get('op')=='real_call')
        self.assertTrue(any(n.get('operation')=='divide' for n in nodes(call)))
        self.assertTrue(call['origin']['expansion'])
        for bad in ('missing','1.0&1','V(missing)'):
            with self.subTest(bad=bad),self.assertRaises(CompileError):
                build(body='@(timer(1))if(gate>0)c=('+weighted(3)+')+'+bad+';')

    def test_statements_events_and_instance_parameter_roles_stay_distinct(self):
        body='@(initial_step)c=0;@(timer(1))c=('+weighted(3)+')+gate;@(timer(2))c=('+weighted(3)+')+gate;'
        for order in (('off','on'),('on','off')):
            p=build(body=body,instances=[Instance(name,'m',dict(u=name+'u',y=name+'y'),dict(gate=0 if name=='off' else 1)) for name in order],wire=True)
            events=[e for e in p['events'] if e['trigger']['kind']=='timer']
            self.assertEqual(len(events),4)
            self.assertEqual({e['origin']['instance'] for e in events},{'off','on'})
            self.assertEqual(len({(e['origin']['instance'],e['origin']['column']) for e in events}),4)

    def test_cache_prepaid_failure_has_no_shared_next_request(self):
        from evas.native_audit import NativeAudit
        original=NativeAudit.debit
        for target in ('source_audit_reuse_qualify_fields','source_audit_lower_cache_create',
                       'source_audit_lower_callback_guard','source_audit_lower_cache_key',
                       'source_audit_lower_cache_insert','source_audit_choice_scan_create',
                       'source_audit_choice_scan_pop','source_audit_choice_scan_edges',
                       'source_audit_observer_query','source_audit_observer_visit'):
            def fail(owner,kind,amount=1,item=None,**kwargs):
                if kind==target:
                    raise CompileError('injected cache work failure',code='resource_budget')
                return original(owner,kind,amount,item,**kwargs)
            with self.subTest(target=target):
                with patch.object(NativeAudit,'debit',fail),self.assertRaises(CompileError) as got:build()
                self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
                self.assertTrue(build(wire=True))

    def test_private_audit_reuse_keeps_callback_and_root_validator_roles(self):
        from evas.lowering import lower, _SourceAuditMemo
        from evas.native_audit import NativeAudit
        from evas.syntax import Expr, Token
        from evas.ir import Select, Origin
        token=Token('1','number',1,1,'roles.va')
        one=Expr('number',1,(),token)
        choice=Expr('>',None,(one,one),token)
        expr=Expr('+',None,(choice,one),token)
        owner=NativeAudit();checks=[]
        def resolve(name):raise AssertionError(name)
        resolve.native_work=owner.ir_work
        resolve.allow_integer_assignment_root=True
        def validate(item,value,*,root):
            checks.append((item,root))
            if item is expr and not root:raise CompileError('intermediate root role still checked')
        resolve.validate_integer_operation=validate
        def select(item,relation,left,right,yes,no):
            return Select(relation,left,right,yes,no,Origin('roles.va',1,1,'dut'))
        memo=_SourceAuditMemo(owner.ir_work,(None,select,None,None))
        bindings={}
        memo.bind(resolve,bindings,('fixed-test-role',))
        resolve._source_audit_binding=memo.binding_token
        a=lower(expr,resolve,bindings,'roles.va',decisions=select,memo=memo)
        b=lower(expr,resolve,bindings,'roles.va',decisions=select,memo=memo)
        self.assertIs(a,b)
        self.assertEqual(sum(item is expr and root for item,root in checks),2)
        resolve.allow_integer_assignment_root=False
        with self.assertRaisesRegex(CompileError,'root role'):lower(expr,resolve,bindings,'roles.va',decisions=select,memo=memo)
        # A new callback or different binding/flag view must get another memo.
        with self.assertRaises(ValueError):memo.bind(lambda name:0,bindings,('fixed-test-role',))
        with self.assertRaises(ValueError):memo.bind(resolve,bindings,('different-test-role',))
        with self.assertRaises(ValueError):memo.bind(resolve,{},('fixed-test-role',))
        with self.assertRaises(ValueError):lower(expr,resolve,bindings,'roles.va',decisions=lambda *args:None,memo=memo)

    def test_added_choice_guard_scan_and_observer_reads_are_paid(self):
        import sys
        from evas.instance_compiler import InstanceCompiler
        rows=[];active={};observer_visits=[]
        original=InstanceCompiler.numeric_observer_candidate
        def observed(c,*,visit=None):
            if visit is None:return original(c)
            def paid(statement):
                before=c.compilation.native_audit.used
                visit(statement)
                observer_visits.append(c.compilation.native_audit.used-before)
            return original(c,visit=paid)
        def trace(frame,event,arg):
            if frame.f_code.co_name!='needs_choices' or not frame.f_code.co_filename.endswith('event_specialization.py'):
                return None
            if event=='call' and frame.f_back.f_code.co_name=='shape':
                if not frame.f_locals.get('paid'):return None
                owner=frame.f_locals['compiler'].compilation.native_audit
                active[id(frame)]=(owner,owner.used)
            if event=='return' and id(frame) in active:
                owner,before=active.pop(id(frame));rows.append(owner.used-before)
            return trace
        previous=sys.gettrace()
        try:
            sys.settrace(trace)
            with patch.object(InstanceCompiler,'numeric_observer_candidate',observed):
                p=build('('+weighted(5)+')'+'+0'*60)
                build(body='q=0.0;'*30+'@(timer(1))c='+weighted(5)+';')
        finally:sys.settrace(previous)
        self.assertTrue(rows)
        self.assertTrue(all(amount>0 for amount in rows))
        self.assertGreater(p._native_audit.counts['source_audit_choice_scan_pop'],0)
        self.assertGreaterEqual(len(observer_visits),31)
        self.assertTrue(all(amount>0 for amount in observer_visits))
        self.assertEqual(p._native_audit.used,sum(p._native_audit.counts.values()))

    def test_same_owner_natural_limit_stays_sticky_and_fresh_source_succeeds(self):
        p=build();owner=p._native_audit
        for _ in range(100):
            try:p.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        else:self.fail('unchanged source/wire owner limit was not reached')
        used=owner.used
        for _ in range(2):
            with self.assertRaises(CompileError) as got:p.to_dict()
            self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
            self.assertGreater(owner.used,used)
        self.assertTrue(build(wire=True))
