"""Dynamic typed-integer event/final_step array indices (N02) via the public API.

Dynamic reads lower to complete balanced Select trees; dynamic writes to a
single-path balanced If dispatch whose only leaf assigns the selected slot.
Admission requires a static proof that every use-site index interval stays
inside the declared slot range (defaults, initialization, every event and
final_step writer, branch joins and weak dynamic updates included); budget
exhaustion and TOP are rejections. Index provenance survives scalarization
and function inlining: array-read and function-origin indices stay rejected.
"""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER', 'case:variable_array']
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def event_model(declarations, events, contribution='V(y,r)<+a[0]+2*a[1];'):
    body = '\n'.join(events)
    tail = '' if contribution is None else '\n' + contribution
    return model(body + tail, declarations)


def compiled(declarations, events, contribution='V(y,r)<+a[0]+2*a[1];',
             instances=None):
    return compile_sources({'arrays.va': event_model(declarations, events, contribution)},
                           instances or [instance()])


def final_states(program, samples=(0, 1), stop=1):
    result = transient(program, {'u': [[0, 0], [1, 0]]}, list(samples),
                       stop=stop, max_step=.25, kernel=KERNEL)
    names = result['transient']['state_names']
    return dict(zip(names, result['transient']['states'][-1])), result


def expect_reject(test, declarations, events, code, contribution='V(y,r)<+1.0;'):
    with test.assertRaises(CompileError) as caught:
        compiled(declarations, events, contribution)
    test.assertEqual(caught.exception.diagnostic.get('code'), code)
    return caught.exception


class DynamicIndexAdmission(unittest.TestCase):
    def test_sequential_write_read_update_at_use_site(self):
        # Index and RHS are evaluated at their sequential site: the second
        # write must see the new b, and only the selected slot changes.
        p = compiled('integer a[0:1],b;',
                     ['@(initial_step) begin b=1; end',
                      '@(timer(0.5,0,1e-12)) begin a[b]=7; b=0; a[b]=9; end'])
        states, _ = final_states(p)
        self.assertEqual((states['dut:a[0]'], states['dut:a[1]']), (9., 7.))

    def test_same_array_rhs_reads_statement_local_state(self):
        # One RHS evaluation; the read sees the pre-write value of the slot.
        p = compiled('integer a[0:1],b;',
                     ['@(initial_step) begin b=1; end',
                      '@(timer(0.25,0.25,1e-12)) begin a[b]=a[b]+1; end'],
                     contribution='V(y,r)<+1.0;')
        states, _ = final_states(p, samples=(0, 1))
        self.assertEqual(states['dut:a[1]'], 4.)  # four firings, one increment each
        self.assertEqual(states['dut:a[0]'], 0.)

    def test_dynamic_read_swaps_elements(self):
        p = compiled('real held[0:1]; integer b;',
                     ['@(initial_step) begin b=0; held[0]=1.0; held[1]=2.0; end',
                      '@(timer(0.5,0,1e-12)) held[1-b]=held[b];'],
                     contribution='V(y,r)<+held[0]+held[1];')
        states, _ = final_states(p)
        self.assertEqual((states['dut:held[0]'], states['dut:held[1]']), (1., 1.))

    def test_final_step_dynamic_display_read(self):
        p = compiled('real held[0:1]; integer b;',
                     ['@(initial_step) begin b=1; held[0]=1.0; held[1]=2.0; end',
                      '@(timer(0.5,0,1e-12)) b=0;',
                      '@(final_step) $display("%g", held[b]);'],
                     contribution='V(y,r)<+held[0];')
        states, _ = final_states(p)
        self.assertEqual(states['dut:b'], 0.)


class DeclarationBounds(unittest.TestCase):
    def test_descending_declaration_admits_endpoint_indices(self):
        p = compiled('integer a[1:-1],b;',
                     ['@(initial_step) b=-1;',
                      '@(timer(0.5,0,1e-12)) a[b]=5;'],
                     contribution='V(y,r)<+1.0;')
        states, _ = final_states(p)
        self.assertEqual((states['dut:a[-1]'], states['dut:a[0]'], states['dut:a[1]']),
                         (5., 0., 0.))

    def test_nonzero_bounds_cover_endpoints_and_middle(self):
        for b, slot in ((5, 5), (6, 6), (7, 7)):
            with self.subTest(index=b):
                p = compiled('integer a[5:7],b;',
                             ['@(initial_step) begin b=%d; a[5]=0; a[6]=0; a[7]=0; end' % b,
                              '@(timer(0.5,0,1e-12)) a[b]=b;'],
                             contribution='V(y,r)<+1.0;')
                states, _ = final_states(p)
                expected = {5: (5., 0., 0.), 6: (0., 6., 0.), 7: (0., 0., 7.)}[slot]
                self.assertEqual((states['dut:a[5]'], states['dut:a[6]'], states['dut:a[7]']),
                                 expected)

    def test_constant_out_of_range_index_still_rejected(self):
        with self.assertRaises(CompileError):
            compiled('integer a[0:1];',
                     ['@(timer(0.5,0,1e-12)) a[2]=1;'])


class ConcurrentWriters(unittest.TestCase):
    def test_same_time_different_slots_execute(self):
        p = compiled('integer a[0:1],b,c;',
                     ['@(initial_step) begin b=0; c=1; end',
                      '@(timer(0.25,0,1e-12)) a[b]=7;',
                      '@(timer(0.25,0,1e-12)) a[c]=9;'])
        states, _ = final_states(p)
        self.assertEqual((states['dut:a[0]'], states['dut:a[1]']), (7., 9.))

    def test_same_time_same_slot_is_event_conflict(self):
        p = compiled('integer a[0:1],b,c;',
                     ['@(initial_step) begin b=0; c=0; end',
                      '@(timer(0.25,0,1e-12)) a[b]=7;',
                      '@(timer(0.25,0,1e-12)) a[c]=9;'])
        with self.assertRaises(KernelError) as caught:
            final_states(p)
        self.assertIn('event_conflict', str(caught.exception))


class IndependentInstances(unittest.TestCase):
    def test_instances_keep_separate_slots_and_parameters(self):
        source = event_model('integer a[0:1],b; parameter real k=1,period=0.5;',
                             ['@(initial_step) begin b=1; end',
                              '@(timer(period,0,1e-12)) a[b]=k;'],
                             contribution='V(y,r)<+a[1];')
        # Distinct parameters (including event times) keep the two instance
        # programs genuinely independent.
        instances = [Instance('one', 'm', dict(u='u', y='y1', r='0'), {'k': 3., 'period': 0.5}),
                     Instance('two', 'm', dict(u='u', y='y2', r='0'), {'k': 5., 'period': 0.6})]
        p = compile_sources({'arrays.va': source}, instances)
        result = transient(p, {'u': [[0, 0], [1, 0]]}, [0, 1],
                           stop=1, max_step=.25, kernel=KERNEL)
        names = result['transient']['state_names']
        states = dict(zip(names, result['transient']['states'][-1]))
        self.assertEqual((states['one:a[1]'], states['two:a[1]']), (3., 5.))
        self.assertEqual((states['one:a[0]'], states['two:a[0]']), (0., 0.))


class IndependentIndexCounterexamples(unittest.TestCase):
    def test_modulo_and_negative_divisor_cannot_hide_out_of_range_index(self):
        for bounds, body in [
                ('0:0', 'a[b%3]=7;'),
                ('-2:-2', 'a[b/(-3)]=7;'),
                ('0:0', 'c=b%3; a[c]=7;')]:
            with self.subTest(bounds=bounds, body=body):
                expect_reject(self, 'integer b,c; real a['+bounds+'];',
                              ['@(initial_step) b=5;',
                               '@(timer(0.5)) begin '+body+' end'], 'array_index_range')

    def test_quotient_and_remainder_use_truncation_toward_zero(self):
        for numerator, divisor, quotient, remainder in [
                (5, 3, 1, 2), (5, -3, -1, 2),
                (-5, 3, -1, -2), (-5, -3, 1, -2)]:
            for op, answer in [('/', quotient), ('%', remainder)]:
                with self.subTest(numerator=numerator, divisor=divisor, op=op):
                    p = compiled(f'integer b; real a[{answer}:{answer}];',
                                 [f'@(initial_step) b={numerator};',
                                  f'@(timer(0.5)) a[b{op}({divisor})]=7;'],
                                 contribution='V(y,r)<+1.0;')
                    states, _ = final_states(p)
                    self.assertEqual(states[f'dut:a[{answer}]'], 7.)

    def test_unwritten_index_defaults_and_scalar_rhs_reads(self):
        p = compiled('integer b; real a[0:1],x;',
                     ['@(timer(0.5)) begin a[b]=7; x=a[b]; end'],
                     contribution='V(y,r)<+x;')
        states, _ = final_states(p)
        self.assertEqual((states['dut:b'], states['dut:a[0]'], states['dut:x']), (0., 7., 7.))

    def test_static_slot_rhs_reads_default_dynamic_index(self):
        p = compiled('integer b; real a[0:1],c[0:1];',
                     ['@(initial_step) a[0]=7;', '@(timer(0.5)) c[0]=a[b];'],
                     contribution='V(y,r)<+c[0];')
        states, _ = final_states(p)
        self.assertEqual((states['dut:b'], states['dut:c[0]']), (0., 7.))


class Rejections(unittest.TestCase):
    def assert_rejects(self, declarations, events, code, contribution=None):
        return expect_reject(self, declarations, events, code, contribution)

    def test_index_of_index_rejected_before_scalarization(self):
        # The inner constant-subscript read would become a plain element state
        # during scalarization; the provenance gate rejects it before that.
        self.assert_rejects('integer a[0:1];',
                            ['@(initial_step) a[0]=0;',
                             '@(timer(0.5,0,1e-12)) a[a[0]]=1;'], 'array_index_type')

    def test_index_of_index_read_rejected(self):
        self.assert_rejects('integer a[0:1],x;',
                            ['@(initial_step) begin a[0]=0; a[1]=1; end',
                             '@(timer(0.5,0,1e-12)) x=a[a[0]]+1;'], 'array_index_type')

    def test_function_origin_index_rejected_after_inlining(self):
        self.assert_rejects(
            'integer a[0:1]; analog function real f; input x; real x; begin f=0.5; end endfunction',
            ['@(timer(0.5,0,1e-12)) a[f(1)]=1;'], 'array_index_type')

    def test_voltage_index_rejected(self):
        self.assert_rejects('integer a[0:1];',
                            ['@(timer(0.5,0,1e-12)) a[V(u,r)]=1;'], 'array_index_type')

    def test_event_write_breaking_entry_range_rejected(self):
        error = self.assert_rejects('integer a[0:1],b;',
                                    ['@(initial_step) b=1;',
                                     '@(timer(0.5,0,1e-12)) begin a[b]=1; b=5; end'],
                                    'array_index_range')
        self.assertIn('[1,5]', str(error))

    def test_final_step_write_breaking_range_rejected(self):
        self.assert_rejects('integer a[0:1],b;',
                            ['@(initial_step) b=1;',
                             '@(timer(0.5,0,1e-12)) a[b]=1;',
                             '@(final_step) b=7;'], 'array_index_range')

    def test_uncertain_entry_range_rejected_even_when_runtime_never_writes_out(self):
        # b only becomes 3 after the indexed write has fired; admission still
        # requires the closed event invariant, not a per-firing runtime check.
        self.assert_rejects('integer a[0:1],b;',
                            ['@(initial_step) b=0;',
                             '@(timer(0.25,0,1e-12)) a[b]=1;',
                             '@(timer(0.5,0,1e-12)) b=3;'], 'array_index_range')

    def test_dynamic_read_range_rejected(self):
        self.assert_rejects('real held[0:1]; integer b;',
                            ['@(initial_step) b=0;',
                             '@(timer(0.5,0,1e-12)) held[b]=1.0;',
                             '@(timer(0.75,0,1e-12)) b=3;'], 'array_index_range')

    def test_weak_dynamic_update_feeding_second_index_rejected(self):
        # a[b]=1 weak-updates every slot of a; a[1] then ranges over [0,5],
        # so using it as x's index must fail even though b actually selects 0.
        self.assert_rejects('integer a[0:1],b,i; integer x[0:1];',
                            ['@(initial_step) begin b=0; a[1]=5; end',
                             '@(timer(0.5,0,1e-12)) begin a[b]=1; i=a[1]; x[i]=2; end'],
                            'array_index_range')

    def test_hidden_intermediate_overflow_rejected(self):
        # The typed intermediate obligation is independent of index admission.
        with self.assertRaises(CompileError) as caught:
            compiled('integer i,j;',
                     ['@(initial_step) begin i=0; j=0; end',
                      '@(timer(0.5,0,1e-12)) begin i=2147483647; j=(i+1)-1; i=0; end'],
                     contribution='V(y,r)<+1.0;')
        self.assertIn('signed 32-bit', str(caught.exception))

    def test_unbounded_counter_widening_is_rejection_not_top_admission(self):
        with self.assertRaises(CompileError):
            compiled('integer a[0:1],b;',
                     ['@(initial_step) b=0;',
                      '@(timer(0.25,0.25,1e-12)) begin b=b*2+1; a[b]=1; end'])


class BranchAndModulo(unittest.TestCase):
    def assert_rejects(self, declarations, events, code, contribution=None):
        return expect_reject(self, declarations, events, code, contribution)
    def test_branch_join_toggle_keeps_closed_domain(self):
        p = compiled('integer a[0:1],b;',
                     ['@(initial_step) b=0;',
                      '@(timer(0.25,0.25,1e-12)) begin '
                      'if(b<1) b=b+1; else b=b-1; a[b]=1; end'])
        states, _ = final_states(p)
        self.assertEqual((states['dut:a[0]'], states['dut:a[1]'], states['dut:b']),
                         (1., 1., 0.))

    def test_singleton_modulo_index_admits(self):
        p = compiled('integer a[0:2],b;',
                     ['@(initial_step) b=5;',
                      '@(timer(0.5,0,1e-12)) a[b%3]=1;'],
                     contribution='V(y,r)<+a[0]+2*a[1]+3*a[2];')
        states, _ = final_states(p)
        self.assertEqual((states['dut:a[0]'], states['dut:a[1]'], states['dut:a[2]']),
                         (0., 0., 1.))

    def test_negative_modulo_singleton_rejected_with_truncation_semantics(self):
        # C truncation keeps -2 % 3 negative; the interval proof must too.
        error = self.assert_rejects('integer a[0:2],b;',
                                    ['@(initial_step) b=-2;',
                                     '@(timer(0.5,0,1e-12)) a[b%3]=1;'],
                                    'array_index_range')
        self.assertIn('[-2,-2]', str(error))


class HistoryPreservation(unittest.TestCase):
    def test_dynamic_write_of_other_slot_keeps_transition_history(self):
        # With unselected-slot self-writes this same model fails with
        # "cannot certify unchanged transition input history"; the dispatch
        # leaf must be the only writer.
        p = compiled('real a[0:1]; integer b,c;',
                     ['@(initial_step) begin b=0; c=1; a[0]=0.0; a[1]=0.0; end',
                      '@(timer(0.5,0,1e-9)) a[b]=V(u,r);',
                      '@(timer(1.0,0,1e-9)) a[c]=1.0;'],
                     contribution='V(y,r)<+transition(a[0],0.0,0.25);')
        result = transient(p, {'u': [[0, 0], [2, 1]]}, [0, 1.5],
                           stop=1.5, max_step=.25, kernel=KERNEL)
        y = result['nodes'].index('y')
        # u ramps to 0.25 at t=0.5; the transition then eases toward it and
        # has finished well before the 1.5 sample.
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [0., 0.25])
