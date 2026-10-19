"""Independent procedural/oracle controls for initial state and total aliases."""
GUARDS=['LANG','EVENT-ORDER','COMPOSE']
import os
from pathlib import Path
import unittest
from evas import CompileError, KernelError, Instance, compile_sources, transient

KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',
    Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel'))
HEAD='`include "disciplines.vams"\nmodule m(u,y,z);input u;output y,z;electrical u,y,z;'

def program(body='@(initial_step)q=7;q=2*V(u);V(y)<+q;V(z)<+1;', declarations='real q,e;'):
    return compile_sources({'alias.va':HEAD+declarations+'analog begin '+body+'end endmodule'},
                           [Instance('M','m',dict(u='u',y='y',z='z'))])

def scalar_foreign_program(*, initial):
    seed='@(initial_step)q=7;' if initial else ''
    text=HEAD+'real q;analog begin '+seed+'q=0*V(u);V(y)<+q;V(z)<+1;end endmodule\n'
    text+='module d(o);output o;electrical o;analog begin V(o)<+0.5;end endmodule'
    return compile_sources({'foreign.va':text},[Instance('driver','d',dict(o='u')),Instance('M','m',dict(u='u',y='y',z='z'))])

def sample(p,times=(0,.125,.25,.5,1),drive=None,**kw):
    return transient(p,drive or {'u':[[0,.5],[1,.5]]},list(times),stop=1,max_step=.125,kernel=KERNEL,**kw)

def values(r,key='y'):
    return [row['voltages'][r['nodes'].index(key)] for row in r['solutions']]

class InitialOrdinaryAlias(unittest.TestCase):
    def test_public_red_total_alias_preserves_seed_slot(self):
        p=program()
        self.assertEqual([(s.name,s.initial) for s in p.states],[('q',7.)])
        r=sample(p)
        self.assertEqual(values(r),[1]*5)
        self.assertEqual(r['transient']['states'],[[7.]]*5)

    def test_each_source_position_reads_its_current_alias(self):
        p=program('@(initial_step)q=7;q=V(u);V(y)<+q;q=q+1;V(z)<+q;')
        r=sample(p)
        self.assertEqual(values(r),[.5]*5)
        self.assertEqual(values(r,'z'),[1.5]*5)
        self.assertEqual(p.states[0].initial,7.)

    def test_conditional_both_arms_and_missing_arm_after_total_write(self):
        for body in ['if(V(u)>0.5)q=2;else q=3;',
                     'q=3;if(V(u)>0.5)q=2;']:
            p=program('@(initial_step)q=9;'+body+'V(y)<+q;V(z)<+1;')
            r=sample(p,(0,.25,.5,.75,1),{'u':[[0,0],[1,1]]})
            self.assertEqual(values(r),[3,3,3,2,2])

    def test_initial_order_and_output_snapshots_remain_initial_values(self):
        p=program('@(initial_step)begin q=2;$strobe("before=%g",q);q=q+3;$display("after=%g",q);end '
                  'q=2*V(u);V(y)<+q;V(z)<+1;')
        r=sample(p)
        self.assertEqual([(x['time'],x['text']) for x in r['transient']['display_records']],[(0,'before=2'),(0,'after=5')])
        self.assertEqual(values(r),[1]*5)
        self.assertEqual(p.states[0].initial,5.)

    def test_initial_input_seed_and_live_ordinary_input_are_distinct(self):
        p=program('@(initial_step)q=V(u);q=2*V(u);V(y)<+q;V(z)<+1;')
        r=sample(p,(0,.25,.5,.75,1),{'u':[[0,.25],[1,.75]]})
        self.assertEqual(values(r),[.5,.75,1,1.25,1.5])
        self.assertEqual(r['transient']['states'],[[.25]]*5)

    def test_301_style_local_integer_state_same_callback_order_and_query_invariance(self):
        # n is written twice within the same callback; metric must use final n=1,
        # while initial seed q=7 stays in its own slot. Then n=-1 at t=.75.
        p=program('@(initial_step)begin q=7;n=0;end '
                  '@(timer(0.25))begin n=-1;n=n+2;end @(timer(0.75))n=-1;'
                  'q=(n<0)?0.125:(n>0)?0.875:0.5;V(y)<+q;V(z)<+n;',
                  'real q;integer n;')
        sparse=(0,.125,.25,.5,.75,1)
        dense=tuple(k/16 for k in range(17))
        a,b=sample(p,sparse),sample(p,dense)
        want=lambda t:.5 if t<.25 else .875 if t<.75 else .125
        self.assertEqual(values(a),[want(t) for t in sparse])
        self.assertEqual(values(b),[want(t) for t in dense])
        self.assertEqual(values(a),[values(b)[dense.index(t)] for t in sparse])
        self.assertEqual(values(a,'z'),[0,0,1,1,-1,-1])

    def test_nonpoint_source_band_remains_a_band_or_an_existing_rejection(self):
        # y=2*u: a nonzero source box must not collapse to its center. The
        # existing kernel may reject that uncertainty, but cannot invent zero.
        p=program()
        try:
            r=sample(p,source_errors={'u':1e-6},vabstol=1e-4,reltol=0)
        except KernelError as error:
            print('nonpoint ordinary source:',error.detail['kind'])
            self.assertIn(error.detail['kind'],['unsupported_source_uncertainty','waveform_accuracy','condition_precision','event_accuracy'])
        else:
            print('nonpoint ordinary source: accepted full propagated voltage box')
            idx=r['nodes'].index('y')
            for boxes in r['observation_evidence']['voltage_bounds_V']:
                lo,hi=boxes[idx]
                self.assertLessEqual(lo,1-2e-6)
                self.assertGreaterEqual(hi,1+2e-6)

    def test_prefix_state_and_interleaved_initialization_do_not_gain_A_eligibility(self):
        bodies=[
            '@(initial_step)begin q=7;n=0;end q=n;@(timer(0.25))n=1;V(y)<+q;V(z)<+1;',
            '@(initial_step)begin q=7;n=0;end e=n;@(timer(0.25))n=1;q=e;V(y)<+q;V(z)<+1;',
            'q=V(u);@(initial_step)q=7;q=2*V(u);V(y)<+q;V(z)<+1;']
        for body in bodies:
            with self.subTest(body=body),self.assertRaisesRegex(CompileError,'initial-only ordinary alias'):
                program(body,'real q,e;integer n;')

    def test_301_style_transition_consumer_keeps_real_half_edge(self):
        p=program('@(initial_step)begin q=7;n=0;end @(timer(0.25))begin n=-1;n=n+2;end '
                  'q=(n>0)?0.875:0.5;V(y)<+transition(q,0,0.125,0.125);V(z)<+n;',
                  'real q;integer n;')
        r=sample(p,(0,.25,.3125,.375,.5,1))
        self.assertEqual(values(r),[.5,.5,.6875,.875,.875,.875])

    def test_A_alias_and_unrelated_transition_preserve_both_instance_orders(self):
        from fractions import Fraction
        source='''`include "disciplines.vams"
module alias_A(a,b,y,z); input a,b; output y,z; electrical a,b,y,z;
real q; analog begin
  @(initial_step)q=7;
  q=V(a)*V(b); V(y)<+q; q=q+1; V(z)<+q;
end endmodule
module history(m); output m; electrical m; real held; analog begin
  @(initial_step)held=0;
  @(timer(0.25))held=1;
  V(m)<+transition(held,0,0.125,0.125);
end endmodule
'''
        alias=Instance('A','alias_A',dict(a='a',b='b',y='y',z='z'))
        history=Instance('H','history',dict(m='m'))
        times=(0,.125,.25,.3125,.375,.5,1)
        # a=t, b=1-t gives y=t*(1-t), z=y+1. The independent history
        # changes from 0 to 1 over [.25,.375], so its midpoint is exactly .5.
        want=(Fraction(0),Fraction(7,64),Fraction(3,16),Fraction(55,256),
              Fraction(15,64),Fraction(1,4),Fraction(0))
        history_want=(0,0,0,.5,1,1,1)
        for instances in ([alias,history],[history,alias]):
            with self.subTest(order=[item.name for item in instances]):
                p=compile_sources({'ordered-A-history.va':source},instances)
                qindex=next(i for i,state in enumerate(p.states)
                            if (state.instance,state.name)==('A','q'))
                self.assertEqual(p.states[qindex].initial,7.)
                r=transient(p,{'a':[[0,0],[1,1]],'b':[[0,1],[1,0]]},
                            list(times),stop=1,max_step=.125,kernel=KERNEL)
                for key,offset in (('y',0),('z',1)):
                    index=r['nodes'].index(key)
                    for row,frame,answer in zip(r['solutions'],
                            r['observation_evidence']['voltage_bounds_V'],want):
                        answer+=offset
                        self.assertLessEqual(abs(row['voltages'][index]-float(answer)),1e-10)
                        lo,hi=frame[index]
                        self.assertLessEqual(Fraction.from_float(lo),answer)
                        self.assertGreaterEqual(Fraction.from_float(hi),answer)
                for actual,answer in zip(values(r,'m'),history_want):
                    self.assertLessEqual(abs(actual-answer),1e-10)
                self.assertEqual([frame[qindex] for frame in r['transient']['states']],
                                 [7.]*len(times))

    def test_source_band_after_event_state_does_not_gain_sampling_permission(self):
        p=program('@(initial_step)begin q=7;n=0;end @(timer(0.25))n=(V(u)>0.5)?1:-1;'
                  'q=(n>0)?1:0;V(y)<+q;V(z)<+n;', 'real q;integer n;')
        with self.assertRaises(KernelError):
            sample(p,source_errors={'u':.01})

    def test_incomplete_write_old_read_and_two_mixed_roles_remain_rejected(self):
        for body in ['if(V(u)>0)q=1;V(y)<+q;',
                     'V(y)<+q;q=1;',
                     'q=q+1;V(y)<+q;',
                     '@(timer(0.25))q=q+1;q=2;V(y)<+q;',
                     '@(timer(0.25))e=q;q=2;V(y)<+q;',
                     '@(cross(q-0.5,+1))e=1;q=2;V(y)<+q;']:
            with self.subTest(body=body),self.assertRaises(CompileError):
                program('@(initial_step)q=7;'+body+'V(z)<+1;')

    def test_integer_ordinary_constant_keeps_the_original_initial_state(self):
        # Keep the former integer rejection verbatim. Continuous evaluation
        # reads1, while the original event State remains its initial value7.
        p=program('@(initial_step)q=7;q=1;V(y)<+q;V(z)<+1;', 'integer q;')
        self.assertEqual([(s.name,s.initial) for s in p.states],[('q',7.)])
        r=sample(p)
        self.assertEqual(values(r),[1.]*5)
        self.assertEqual(values(r,'z'),[1.]*5)
        self.assertEqual(r['transient']['states'],[[7.]]*5)

    def test_target_arrays_loops_and_time_are_not_added(self):
        cases=[('real q;integer i;','for(i=0;i<0;i=i+1)q=1;q=2;'),
               ('real q,a[0:1];','q=1;'),
               ('real q;','q=$abstime;')]
        for decl,body in cases:
            with self.subTest(decl=decl,body=body),self.assertRaises(CompileError):
                program('@(initial_step)q=7;'+body+'V(y)<+q;V(z)<+1;',decl)

    def test_declaration_identity_and_instance_parameter_binding(self):
        text=HEAD+'parameter real seed=3;real q;analog begin @(initial_step)q=seed;q=2*V(u);V(y)<+q;V(z)<+1;end endmodule'
        p=compile_sources({'pair.va':text},[Instance('A','m',dict(u='u',y='ya',z='za')),Instance('B','m',dict(u='u',y='yb',z='zb'),dict(seed=5))])
        self.assertEqual([state.initial for state in p.states],[3.,5.])
        r=sample(p)
        self.assertEqual(values(r,'ya'),[1]*5)
        self.assertEqual(values(r,'yb'),[1]*5)
        with self.assertRaises(CompileError):
            program(declarations='real q=2,e;')

    def test_first_activation_includes_prior_inactive_compilation_work(self):
        # An old local-only instance naturally accumulates unpaid-by-ceiling
        # work. The next instance activates the same owner's unchanged cap.
        from evas.native_audit import NativeAudit
        from unittest.mock import patch
        observed=[]
        original=NativeAudit.activate
        def activate(owner,item):
            observed.append(owner.used)
            return original(owner,item)
        old='module l(u,y);input u;output y;electrical u,y;real a;analog begin '+'a=V(u);'*1800+'V(y)<+a;end endmodule'
        new=HEAD+'real q;analog begin @(initial_step)q=7;q=V(u);V(y)<+q;V(z)<+1;end endmodule'
        with patch.object(NativeAudit,'activate',activate),self.assertRaises(CompileError) as failure:
            compile_sources({'many.va':'`include "disciplines.vams"\n'+old+'\n'+new.split('\n',1)[1]},[Instance('L','l',dict(u='u',y='old')),Instance('M','m',dict(u='u',y='y',z='z'))])
        self.assertEqual(failure.exception.diagnostic['code'],'resource_budget')
        self.assertGreater(observed[0],100000)

    def test_initial_obligations_survive_total_overwrite(self):
        for init in ['q=7;e=1/0;', 'q=1/0;', 'if(1>0)q=2;else q=1/0;',
                     'q=transition(1,0,0.1,0.1);', 'q=V(y);',
                     '$strobe("bad=%g",V(u));q=3;']:
            with self.subTest(init=init),self.assertRaises(CompileError):
                program('@(initial_step)begin '+init+'end q=2*V(u);V(y)<+q;V(z)<+1;')

    def test_hidden_output_history_settings_and_missing_local_are_rejected(self):
        for rhs in ['0*V(y)', '(1>0)?V(u):0*V(y)',
                    'transition(V(u),0,0.1,0.1)', 'e', '0*$abstime']:
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):
                program('@(initial_step)q=7;q='+rhs+';V(y)<+q;V(z)<+1;')
        for tail in ['V(y)<+transition(1,0,q,q);', '$bound_step(q);V(y)<+1;']:
            with self.subTest(tail=tail),self.assertRaises(CompileError):
                program('@(initial_step)q=7;q=V(u);'+tail+'V(z)<+1;')

    def test_foreign_physical_input_even_zero_weight_is_rejected(self):
        with self.assertRaises(CompileError) as failure:
            scalar_foreign_program(initial=True)
        self.assertEqual(failure.exception.diagnostic['code'],'unsupported_local_event')
        self.assertIn('initial-only ordinary alias',str(failure.exception))

    def test_same_scalar_foreign_connection_without_A_role_is_admitted(self):
        # Identical ports, driver and zero-weight input reach the old local
        # route. Only removal of the initial writer removes the A role.
        p=scalar_foreign_program(initial=False)
        self.assertFalse(p.states)

    def test_unsafe_guards_and_integer_conversion_keep_all_hidden_obligations(self):
        for guard in ['V(y)>0', '$abstime>0']:
            with self.subTest(guard=guard),self.assertRaises(CompileError):
                program('@(initial_step)q=7;if('+guard+')q=1;else q=2;q=3;V(y)<+q;V(z)<+1;')
        with self.assertRaises(CompileError):
            program('@(initial_step)q=7;k=V(u);q=k;V(y)<+q;V(z)<+1;','real q;integer k;')
        with self.assertRaises(CompileError):
            program('@(initial_step)q=7;q=(1>0)?1:(1/0);V(y)<+q;V(z)<+1;')

    def test_native_work_sticky_wire_exhaustion_and_scan_growth(self):
        a=program();b=program('@(initial_step)q=7;q='+ '+'.join(['V(u)']*32)+';V(y)<+q;V(z)<+1;')
        self.assertTrue(a._native_audit.active)
        self.assertGreater(b._native_audit.counts['initial_ordinary_expression'],a._native_audit.counts['initial_ordinary_expression'])
        owner=a._native_audit
        for _ in range(100001):
            try:a.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget')
                break
        else:self.fail('natural wire work did not exhaust unchanged 100000')
        before=owner.used
        self.assertGreater(before,100000)
        for _ in range(2):
            with self.assertRaises(CompileError):a.to_dict()
            self.assertGreater(owner.used,before)
            before=owner.used

if __name__=='__main__':unittest.main(verbosity=2)
