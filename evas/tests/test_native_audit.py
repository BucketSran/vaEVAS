"""One actual compiler owner pays source/type/wire work across all new targets."""
GUARDS=['LANG','COMPOSE']
import dataclasses
import unittest
from evas import Instance,CompileError,compile_sources
from evas.limits import check_ir


def source(targets=True):
    contribution=('V(y,r)<+transition((n>>1)&1,0,0.1,0.1); V(z,r)<+transition((m&1)?0.9:0.0,0,0.1,0.1);'
                  if targets else 'V(y,r)<+out;V(z,r)<+out;')
    return ('`include "disciplines.vams"\nmodule m(y,z,r); output y,z;inout r;electrical y,z,r;integer n,m;real out;analog begin '
            '@(initial_step)begin n=0;m=0;out=0;end '
            '@(timer(1,1))begin n=n+1;out=n&1;end '
            '@(timer(1.5,1))begin m=m+1;out=m>>1;end '+contribution+'end endmodule')

def compile_program(targets=True):
    return compile_sources({'ledger.va':source(targets)},[Instance('dut','m',dict(y='y',z='z',r='0'))])

def expanded(value):
    # Independent recurrence counts each occurrence, including shared children.
    if dataclasses.is_dataclass(value):return 1+sum(expanded(getattr(value,f.name)) for f in dataclasses.fields(value))
    if isinstance(value,(tuple,list)):return 1+sum(map(expanded,value))
    if isinstance(value,dict):return 1+sum(map(expanded,value.values()))
    return 1

class NativeAuditTests(unittest.TestCase):
    def test_expanded_wire_copy_and_delegated_typing_charge_actual_work(self):
        import sys
        import evas.integer_bits as bits
        actual_typing=0
        def profile(frame,event,arg):
            nonlocal actual_typing
            if event=='call' and frame.f_code is bits.integer_type.__code__ and frame.f_locals.get('visit') is not None:
                actual_typing+=1
        prior=sys.getprofile()
        sys.setprofile(profile)
        try:p=compile_program()
        finally:sys.setprofile(prior)
        o=p._native_audit
        self.assertEqual(o.counts['typing_visit'],actual_typing)
        self.assertEqual(len(o.events),2)
        self.assertEqual(o.activations,2)
        self.assertGreater(o.counts['typing_visit'],0)
        self.assertGreater(o.counts['bound_visit'],0)
        self.assertTrue(o.active)
        before=o.counts.copy();wire=p.to_dict()
        self.assertEqual(o.counts['wire_visit']-before['wire_visit'],expanded(p))
        self.assertEqual(expanded(p),expanded(wire))
        self.assertEqual(o.used,sum(o.counts.values()))
        self.assertEqual(o.counts['copy_atom']-before['copy_atom']+o.counts['copy_container']-before['copy_container'],o.counts['wire_visit']-before['wire_visit'])
        self.assertEqual(check_ir(p)[1],expanded(p))

    def test_two_events_two_targets_naturally_exhaust_same_owner_and_retry_twice(self):
        p=compile_program();o=p._native_audit
        successful=0
        for _ in range(100001):
            try:p.to_dict();successful+=1
            except CompileError as e:
                self.assertEqual(e.diagnostic['code'],'resource_budget');break
        else:self.fail('real repeated wire work did not exhaust the unchanged100000 cap')
        self.assertGreater(successful,1)
        self.assertEqual(len(o.events),2);self.assertEqual(o.activations,2)
        exhausted=o.used
        self.assertGreater(exhausted,100000)
        for _ in range(2):
            with self.assertRaises(CompileError):p.to_dict()
            self.assertGreater(o.used,exhausted);exhausted=o.used

    def test_old_no_typed_target_program_keeps_original_event_local_admission(self):
        p=compile_program(False);o=p._native_audit
        self.assertFalse(o.active)
        local=dict(o.events)
        for _ in range(100):p.to_dict()
        self.assertEqual(o.events,local)
        self.assertEqual(o.counts['wire_visit'],0)

    def test_first_target_activation_counts_prior_two_event_consumption(self):
        text=source(False).replace('n=n+1;out=n&1;','n=n+1;'*320+'out=n&1;').replace('m=m+1;out=m>>1;','m=m+1;'*320+'out=m>>1;')
        instances=[Instance('dut','m',dict(y='y',z='z',r='0'))]
        old=compile_sources({'ledger.va':text},instances)
        owner=old._native_audit
        self.assertGreater(owner.used,100000)
        self.assertTrue(all(used<100000 for used in owner.events.values()))
        self.assertFalse(owner.active)
        target=text.replace('V(y,r)<+out;V(z,r)<+out;',
            'V(y,r)<+transition(n&1,0,0.1,0.1);V(z,r)<+transition(m&1,0,0.1,0.1);')
        with self.assertRaisesRegex(CompileError,'aggregate audit'):
            compile_sources({'ledger.va':target},instances)

    def test_same_module_instances_keep_distinct_original_event_views(self):
        # Source AST tuple addresses can be reused after a bound compiler dies.
        # Exercise real sequential binding, not duplicated synthetic object IDs.
        for count in [2,3,5,10,20,40]:
            p=compile_sources({'shared.va':source(False)},[
                Instance('dut'+str(i),'m',dict(y='y'+str(i),z='z'+str(i),r='0'))
                for i in range(count)])
            self.assertEqual(len(p.events),2*count)
            self.assertEqual(len(p._native_audit.events),len(p.events),str(count))
        p=compile_sources({'shared.va':source(False)},[
            Instance('a','m',dict(y='a',z='az',r='0')),
            Instance('b','m',dict(y='b',z='bz',r='0'))])
        o=p._native_audit
        self.assertFalse(o.active)
        self.assertEqual(len(p.events),4)
        self.assertEqual(len(o.events),4)
        self.assertEqual(o.event_serial,4)
        self.assertEqual(o.event_view_calls,4)
        before=dict(o.events)
        for key,view in list(o.event_views.items()):
            self.assertIs(o.event_view(key),view)
            self.assertIs(view.owner,o)
        self.assertEqual(o.event_serial,4)
        self.assertEqual(o.event_view_calls,8)
        self.assertEqual(o.events,before)
        self.assertEqual(sorted(o.events.values())[:2],sorted(o.events.values())[2:])

    def test_real_native_fallback_captures_the_original_logical_event_view(self):
        from unittest.mock import patch
        from evas.instance_compiler import InstanceCompiler
        original=InstanceCompiler.native_event_integer
        observed=[]
        def measured(compiler,expr,resolve,charge):
            observed.append((compiler.instance.name,charge))
            return original(compiler,expr,resolve,charge)
        with patch.object(InstanceCompiler,'native_event_integer',measured):
            p=compile_sources({'shared.va':source(False)},[
                Instance('a','m',dict(y='a',z='az',r='0')),
                Instance('b','m',dict(y='b',z='bz',r='0'))])
        owner=p._native_audit
        self.assertGreater(len(observed),4)
        self.assertEqual(len({id(charge) for _,charge in observed}),4)
        for instance,charge in observed:
            self.assertIs(charge.owner,owner)
            self.assertEqual(charge.event[0],instance)
            self.assertIs(charge,owner.event_views[charge.event])
        self.assertEqual(owner.event_serial,4)
        self.assertEqual(owner.event_view_calls,4)

    def test_real_failed_fallback_retry_reuses_exhausted_logical_event_allowance(self):
        from unittest.mock import patch
        from evas.instance_compiler import InstanceCompiler
        original=InstanceCompiler.native_event_integer
        calls=[]
        def measured(compiler,expr,resolve,charge):
            calls.append((compiler,expr,resolve,charge))
            return original(compiler,expr,resolve,charge)
        with patch.object(InstanceCompiler,'native_event_integer',measured):
            p=compile_program(False)
        compiler,expr,resolve,view=calls[0]
        owner=p._native_audit;created=owner.event_serial
        successes=0
        for _ in range(100001):
            try:original(compiler,expr,resolve,view);successes+=1
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        else:self.fail('actual repeated source fallback did not exhaust its original local cap')
        self.assertGreater(successes,1)
        self.assertFalse(owner.active)
        for _ in range(2):
            same=owner.event_view(view.event)
            self.assertIs(same,view)
            with self.assertRaises(CompileError):original(compiler,expr,resolve,same)
            self.assertEqual(owner.event_serial,created)
            self.assertGreater(owner.events[view.event],100000)
