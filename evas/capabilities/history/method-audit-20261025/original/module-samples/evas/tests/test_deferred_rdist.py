"""Known random calls are selected-path failure effects, never random values."""
GUARDS = ['LANG', 'EVENT-CONDITIONS']
import unittest
from dataclasses import replace
from evas import compile_sources,Instance,CompileError


def build(call='$rdist_normal(seed,0.0,0.0)',guard=None,seed='integer seed=19;',instances=None,initial=False,wire=True):
    source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;real q;'+seed+
      'parameter integer gate=0;analog begin @(initial_step)q=0;'+
      ('@(initial_step)' if initial else '@(timer(1.0))')+
      ('if('+guard+')' if guard else '')+'q='+call+';'+('else q=2.0;' if guard else '')+
      'V(y)<+q;end endmodule')
    p=compile_sources({'rdist.va':source},instances or [Instance('dut','m',dict(u='u',y='y'))])
    return p.to_dict() if wire else p


def nodes(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from nodes(child)
    elif isinstance(value,(tuple,list)):
        for child in value:yield from nodes(child)


class DeferredRdist(unittest.TestCase):
    def test_resource_choices_keep_deferred_leaf_and_argument_choices(self):
        call = '($rdist_normal(seed,(V(u)>0.0)?1.0/0.0:0.0,0.0)>1.0)?1.0:0.0'
        p = build(call)
        leaves = [n for n in nodes(p['events']) if n.get('op') == 'unsupported_system_call']
        self.assertEqual(len(leaves), 1)
        leaf = leaves[0]
        self.assertTrue(any(n.get('operation') == 'divide' for n in nodes(leaf['args'][0])))
        self.assertTrue(any(n.get('op') == 'select' for n in nodes(leaf['args'][0])))
        self.assertEqual(leaf['origin']['instance'], 'dut')
        self.assertEqual(p['states'][leaf['seed']]['name'], 'seed')
        for invalid in ('missing', 'V(missing)', '1.0&1'):
            with self.subTest(invalid=invalid), self.assertRaises(CompileError):
                build('($rdist_normal(seed,'+invalid+',0)>1.0)?1.0:0.0', guard='gate>0')

    def test_original_audit_does_not_emit_owned_calls_in_control(self):
        for physical in (False, True):
            source = ('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'
                'integer seed=19;real q;analog function real f;input x;real x;begin f=x+1.0;end endfunction '
                'analog begin @(initial_step)q=0;@(timer(1))if(f(V(u))>0.0)'
                'q=($rdist_normal(seed,0,0)>1.0)?1.0:0.0;'+('V(y)<+q;' if physical else '')+'end endmodule')
            with self.subTest(physical=physical):
                p = compile_sources({'audit-call.va': source}, [Instance('dut','m',dict(u='u',y='y'))]).to_dict()
                calls = [n for n in nodes(p['events']) if n.get('op') == 'real_call']
                self.assertEqual(len(calls), 1)
                self.assertEqual(set(calls[0]['bindings']), set(range(len(p['real_bindings']))))
                self.assertEqual(len(p['operators']), 0)
                self.assertTrue(calls[0]['origin']['expansion'])

    def test_numeric_original_control_audit_has_no_discarded_call_slots(self):
        source = ('`include "disciplines.vams"\nmodule m(u);input u;electrical u;real q;'
            'analog function real f;input x;real x;begin f=x+1.0;end endfunction '
            'analog begin @(initial_step)q=0;@(timer(1))if(f(V(u))>0.0)q=1.0;end endmodule')
        p = compile_sources({'numeric-audit.va': source}, [Instance('dut','m',dict(u='u'))]).to_dict()
        call = next(n for n in nodes(p['events']) if n.get('op') == 'real_call')
        self.assertEqual(set(call['bindings']), set(range(len(p['real_bindings']))))
        self.assertEqual(len(p['real_bindings']), 2)

    def test_macro_clip_keeps_original_occurrences_and_origins(self):
        source = ('`include "disciplines.vams"\n'
            '`define CLIP(x) (((x)>1.0)?1.0:(((x)<-1.0)?-1.0:(x)))\n'
            'module m(y);output y;electrical y;integer seed=19;real q;analog begin '
            '@(timer(1))q=`CLIP($rdist_normal(seed,0,0));V(y)<+q;end endmodule')
        p = compile_sources({'macro-pn.va': source}, [Instance('dut','m',dict(y='y'))]).to_dict()
        leaves = [n for n in nodes(p['events']) if n.get('op') == 'unsupported_system_call']
        # Macro expansion repeats its operand three times; do not CSE effects.
        self.assertEqual(len(leaves), 3)
        for leaf in leaves:
            self.assertEqual(leaf['origin']['source'], 'macro-pn.va')
            self.assertEqual(leaf['origin']['instance'], 'dut')
            self.assertEqual(p['states'][leaf['seed']]['name'], 'seed')
            self.assertEqual(len(leaf['args']), 2)

    def test_unused_actual_retains_deferred_effect_with_resource_choice(self):
        source = ('`include "disciplines.vams"\nmodule m(y);output y;electrical y;integer seed=19;real q;'
            'analog function real f;input x;real x;begin f=2.0;end endfunction '
            'analog begin @(timer(1))q=(f($rdist_normal(seed,0,0))>1.0)?1.0:0.0;V(y)<+q;end endmodule')
        p = compile_sources({'unused-choice.va': source}, [Instance('dut','m',dict(y='y'))]).to_dict()
        calls = [n for n in nodes(p['events']) if n.get('op') == 'real_call']
        self.assertEqual(len(calls), 1)
        leaves = [n for n in nodes(calls[0]['body'][0]) if n.get('op') == 'unsupported_system_call']
        self.assertEqual(len(leaves), 1)
        self.assertEqual(len(leaves[0]['args']), 2)
        self.assertEqual(p['states'][leaves[0]['seed']]['initial'], 19.0)
        self.assertEqual(leaves[0]['origin']['source'], 'unused-choice.va')

    def test_resource_choice_uses_same_owner_and_sticky_limit(self):
        p = build('($rdist_normal(seed,0,0)>1.0)?1.0:0.0', wire=False)
        owner = p._native_audit
        self.assertTrue(owner.active)
        self.assertGreater(owner.counts['deferred_system_resource_signature'], 0)
        for _ in range(1000):
            try:
                p.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'], 'resource_budget')
                break
        else:
            self.fail('resource choice did not naturally exhaust unchanged cap')
        used = owner.used
        for _ in range(2):
            with self.assertRaises(CompileError) as failure:
                p.to_dict()
            self.assertEqual(failure.exception.diagnostic['code'], 'resource_budget')
            self.assertGreater(owner.used, used)
        self.assertTrue(build('($rdist_normal(seed,0,0)>1.0)?1.0:0.0'))

    def test_zero_sigma_keeps_leaf_and_seed_storage_identity(self):
        p=build();leaf=next(n for n in nodes(p) if n.get('op')=='unsupported_system_call')
        self.assertEqual(leaf['function'],'rdist_normal');self.assertEqual(len(leaf['args']),2)
        state=p['states'][leaf['seed']]
        self.assertEqual((state['name'],state['kind'],state['initial']),('seed','integer',19.0))
        self.assertEqual(leaf['origin']['source'],'rdist.va')
        self.assertGreater(leaf['origin']['line'],0);self.assertGreater(leaf['origin']['column'],0)
        self.assertEqual(len(p['events']),2)

    def test_initial_and_uncertain_arm_retain_failure_leaf(self):
        for options in ({'initial':True},{'guard':'V(u)>0.0'}):
            with self.subTest(options=options):
                p=build(**options);self.assertTrue(any(n.get('op')=='unsupported_system_call' for n in nodes(p['events'])))

    def test_parameter_dead_arm_is_still_statically_checked(self):
        for call in ('$rdist_normal(seed,0.0)','$rdist_normal(1,0.0,0.0)',
                     '$rdist_normal(gate,0.0,0.0)','$rdist_normal(seed,missing,0)',
                     '$rdist_normal(seed,missingfn(1),0)','$rdist_normal(seed,V(missing),0)',
                     '$rdist_normal(seed,1.0&1,0)','$rdist_normal(seed,1.0<<1,0)'):
            with self.subTest(call=call),self.assertRaises(CompileError):build(call,guard='gate>0')
        for seed in ('real seed=1.0;','integer seed[0:1];'):
            with self.subTest(seed=seed),self.assertRaises(CompileError):build(seed=seed,guard='gate>0')

    def test_nonconstant_dead_arm_args_do_not_evaluate_real_division(self):
        p=build('$rdist_normal(seed,1.0/0.0,0.0)',guard='V(u)>0.0')
        leaf=next(n for n in nodes(p) if n.get('op')=='unsupported_system_call')
        self.assertEqual(leaf['args'][0]['operation'],'divide')

    def test_function_local_or_body_seed_stays_out_of_scope(self):
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;integer seed;real q;'
           'analog function real f;input x;real x;begin f=$rdist_normal(seed,0,0);end endfunction '
           'analog begin @(timer(1))q=f(0);V(y)<+q;end endmodule')
        with self.assertRaises(CompileError):
            compile_sources({'local.va':source},[Instance('dut','m',dict(y='y'))])

    def test_unknown_system_names_do_not_gain_reachable_support(self):
        for name in ('rdist_uniform','dist_normal','normal','anything'):
            with self.subTest(name=name),self.assertRaisesRegex(CompileError,'not supported'):
                build('$'+name+'(seed,0,0)')

    def test_two_instances_keep_independent_integer_seed_indices(self):
        for names in (('a','b'),('b','a')):
            p=build(instances=[Instance(n,'m',dict(u=n+'u',y=n+'y')) for n in names])
            leaves=[n for n in nodes(p['events']) if n.get('op')=='unsupported_system_call']
            self.assertEqual(len(leaves),2);self.assertNotEqual(leaves[0]['seed'],leaves[1]['seed'])
            for leaf in leaves:self.assertEqual(p['states'][leaf['seed']]['instance'],leaf['origin']['instance'])

    def test_bad_raw_leaf_seed_and_signature_are_rejected(self):
        p=build(wire=False)
        from evas.ir import UnsupportedSystemCall
        event=next(event for event in p.events if isinstance(event.body[0].rhs.value,UnsupportedSystemCall))
        assignment=event.body[0];boundary=assignment.rhs;leaf=boundary.value
        for bad in (replace(leaf,function='rdist_uniform'),replace(leaf,seed=0),replace(leaf,args=leaf.args[:1])):
            forged=replace(p,events=(*p.events[:-1],replace(event,body=(replace(assignment,rhs=replace(boundary,value=bad)),))))
            with self.subTest(bad=bad),self.assertRaisesRegex(CompileError,'IR33:'):forged.to_dict()

    def test_caller_module_seed_in_function_argument_prefix_is_allowed(self):
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;integer seed=1;real q;'
          'analog function real f;input x;real x;begin f=2.0;end endfunction '
          'analog begin @(timer(1))q=f($rdist_normal(seed,0,0));V(y)<+q;end endmodule')
        p=compile_sources({'argument.va':source},[Instance('dut','m',dict(y='y'))]).to_dict()
        call=next(n for n in nodes(p) if n.get('op')=='real_call')
        prefix=call['body'][0]['action']['value']
        self.assertEqual(prefix['kind'],'argument')
        self.assertEqual(prefix['value']['op'],'unsupported_system_call')

    def test_unselected_argument_math_domain_is_a_retained_operator(self):
        p=build('$rdist_normal(seed,sqrt(-1.0),0.0)',guard='V(u)>0.0')
        leaf=next(n for n in nodes(p) if n.get('op')=='unsupported_system_call')
        self.assertEqual(leaf['args'][0]['op'],'operator')
        operator=p['operators'][leaf['args'][0]['operator']]
        self.assertEqual(operator['function'],'sqrt')

    def test_original_owner_charges_seed_scan_and_retries_stay_exhausted(self):
        p=build(wire=False);owner=p._native_audit
        self.assertTrue(owner.active)
        self.assertGreater(owner.counts['deferred_seed_scan_visit'],0)
        self.assertGreater(owner.counts['deferred_system_lower_signature'],0)
        for _ in range(1000):
            try:p.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        else:self.fail('unchanged100000 request limit was not reached')
        used=owner.used
        for _ in range(2):
            with self.assertRaises(CompileError):p.to_dict()
            self.assertGreater(owner.used,used);used=owner.used
        build().get('states')

    def test_module_nested_copy_in_chain_keeps_module_seed_authority(self):
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;integer seed=1;real q;'
          'analog function real g;input x;real x;begin g=x;end endfunction '
          'analog function real f;input x;real x;begin f=x;end endfunction '
          'analog begin @(timer(1))q=f(g($rdist_normal(seed,0,0)));V(y)<+q;end endmodule')
        p=compile_sources({'chain.va':source},[Instance('dut','m',dict(y='y'))]).to_dict()
        # The reviewed narrow identity producer keeps both copy/return pairs
        # without scoped slots. The effectful module argument still occurs once.
        self.assertFalse(any(n.get('op')=='real_call' for n in nodes(p)))
        self.assertEqual(sum(n.get('op')=='unsupported_system_call' for n in nodes(p)),1)
        self.assertEqual(sum(n.get('op')=='real_boundary' and n.get('kind')=='argument' for n in nodes(p)),2)
        self.assertEqual(sum(n.get('op')=='real_boundary' and n.get('kind')=='return' for n in nodes(p)),2)
        # Keep the actual retained-Call prefix-chain positive as well. These
        # duplicate writes preserve x while deliberately requiring both Calls.
        retained=source.replace('begin g=x;end','begin g=x;g=x;end').replace('begin f=x;end','begin f=x;f=x;end')
        wire=compile_sources({'chain.va':retained},[Instance('dut','m',dict(y='y'))]).to_dict()
        self.assertEqual(sum(n.get('op')=='real_call' for n in nodes(wire)),2)
        self.assertEqual(sum(n.get('op')=='unsupported_system_call' for n in nodes(wire)),1)

    def test_nested_call_argument_in_function_body_cannot_regain_authority(self):
        from evas.ir import Affine,UnsupportedSystemCall,RealBoundary,RealCall
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;integer seed;real q;'
          'analog function real g;input x;real x;begin g=x;g=x;end endfunction '
          'analog function real f;input x;real x;begin f=g(x);end endfunction '
          'analog begin @(initial_step)seed=1;@(timer(1))q=f(1.0);V(y)<+q;end endmodule')
        p=compile_sources({'body.va':source},[Instance('dut','m',dict(y='y'))])
        event=next(e for e in p.events if isinstance(e.body[0].rhs,RealBoundary) and isinstance(e.body[0].rhs.value,RealCall))
        assignment=event.body[0];outer=assignment.rhs.value
        returned=outer.body[-1];inner=returned.action.value.value
        self.assertIsInstance(inner,RealCall)
        seed=next(i for i,state in enumerate(p.states) if state.name=='seed')
        leaf=UnsupportedSystemCall('rdist_normal',seed,(Affine(0.0,()),Affine(0.0,())),inner.origin)
        first=inner.body[0];bad_first=replace(first,action=replace(first.action,value=replace(first.action.value,value=leaf)))
        bad_inner=replace(inner,body=(bad_first,*inner.body[1:]))
        bad_return=replace(returned,action=replace(returned.action,value=replace(returned.action.value,value=bad_inner)))
        bad_outer=replace(outer,body=(*outer.body[:-1],bad_return))
        bad_assignment=replace(assignment,rhs=replace(assignment.rhs,value=bad_outer))
        bad_event=replace(event,body=(bad_assignment,))
        forged=replace(p,events=tuple(bad_event if e is event else e for e in p.events))
        with self.assertRaisesRegex(CompileError,'system function seed requires'):
            forged.to_dict()
