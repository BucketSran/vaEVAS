"""Input-only rational guards through the public compiler and PWL runtime.

Other state/history/output-dependent programs retain the narrower guard scope.
EVAS_RATIONAL_PROBE_KERNEL selects an explicit candidate executable for replay.
"""
import os
from pathlib import Path
import unittest

from evas import CompileError,Instance,KernelError,compile_sources,transient

GUARDS = ["LANG", "LIN", "ANALOG"]

KERNEL=Path(os.environ.get('EVAS_RATIONAL_PROBE_KERNEL',str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))


def compile_body(body, declarations='', *, inout_output=False):
    source='''`include "disciplines.vams"
module m(n,d,ref,en,y); input n,d,ref,en; output y;
electrical n,d,ref,en,y;
real q,result; '''+declarations+' analog begin '+body+' end endmodule'
    if inout_output:
        source=source.replace('output y;', 'inout y;')
    return compile_sources({'source-rational.va':source},[Instance('dut','m',{n:n for n in ['n','d','ref','en','y']})])


def run(program,n=.3,d=.6,ref=.25,en=1.,errors=None):
    return transient(program,{name:[[0,v],[1,v]] for name,v in [('n',n),('d',d),('ref',ref),('en',en)]},
                     [0,.5,1],stop=1,max_step=.1,source_errors=errors,kernel=KERNEL)


def outputs(response):
    i=response['nodes'].index('y')
    return [s['voltages'][i] for s in response['solutions']]


class SourceOnlyRationalContracts(unittest.TestCase):
    def test_direct_quotient_guard_away_from_boundary(self):
        p=compile_body('q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')
        self.assertEqual(outputs(run(p,n=.375,d=.5)),[.9,.9,.9])

    def test_exact_quotient_boundary_uses_original_source_certificate(self):
        p=compile_body('q=V(n)/V(d)-V(n)/V(d); V(y)<+(q>0.0)?0.9:0.0;')
        self.assertEqual(outputs(run(p,d=.7)),[0,0,0])

    def test_rational_sum_and_difference_keep_original_tree(self):
        p=compile_body('q=V(n)/V(d)+V(ref)-0.125; V(y)<+(q>0.5)?0.9:0.0;')
        self.assertEqual(outputs(run(p,n=.125,d=.5,ref=.25)),[0,0,0])
        self.assertEqual(outputs(run(p,n=.25,d=.5,ref=.25)),[.9,.9,.9])

    def test_negative_but_nonzero_selected_denominator_is_evaluated(self):
        p=compile_body('q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')
        self.assertEqual(outputs(run(p,n=-.375,d=-.5)),[.9,.9,.9])

    def test_selected_zero_denominator_rejects(self):
        p=compile_body('q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')
        with self.assertRaisesRegex(KernelError,'program-real arithmetic: DivisionByZero'):
            run(p,d=0)

    def test_denominator_error_box_crossing_zero_rejects(self):
        p=compile_body('q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')
        with self.assertRaises(KernelError) as caught:
            run(p,d=.1,errors={'d':.2})
        self.assertEqual(caught.exception.diagnostic['kind'], 'real_arithmetic')
        self.assertIn('DivisionAcrossZero', caught.exception.diagnostic['message'])

    def test_uncertain_guard_without_exact_source_provenance_rejects(self):
        p=compile_body('q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')
        with self.assertRaises(KernelError) as caught:
            run(p,errors={'n':.01})
        self.assertEqual(caught.exception.diagnostic['kind'], 'event_condition')
        self.assertIn('not certified over its complete source-position enclosure',
                      caught.exception.diagnostic['message'])

    def test_inactive_variable_pole_keeps_existing_lazy_value_semantics(self):
        p=compile_body('q=(V(en)>0.5)?V(n)/V(d):0.0; V(y)<+q;')
        self.assertEqual(outputs(run(p,d=0,en=0)),[0,0,0])

    def test_unselected_constant_zero_divisor_is_still_audited(self):
        # IR33 retains both source arms, but numeric domain errors belong to
        # the selected arm. The original source with en=1 has q=0.5 exactly.
        p=compile_body('q=(V(en)>0.5)?V(n)/V(d):1.0/0.0; V(y)<+(q>0.5)?0.9:0.0;')
        self.assertEqual(outputs(run(p)),[0,0,0])
        with self.assertRaisesRegex(KernelError,'DivisionByZero'):
            run(p,en=0)
        # Laziness does not license an invalid name in the unselected arm.
        with self.assertRaises(CompileError):
            compile_body('q=(V(en)>0.5)?V(n)/V(d):unknown; V(y)<+q;')

    def test_unselected_hidden_zero_output_dependency_stays_outside_scope(self):
        with self.assertRaises((CompileError,KernelError)):
            p=compile_body('q=V(n)/V(d); result=(V(en)>0.5)?0.9:0.0*V(y); V(y)<+(q>0.5)?result:0.0;')
            run(p,n=.375,d=.5)

    def test_inout_label_does_not_make_an_undriven_output_a_source(self):
        p=compile_body('q=V(n)/V(d); result=(V(en)>0.5)?0.9:0.0*V(y); V(y)<+(q>0.5)?result:0.0;',
                       inout_output=True)
        with self.assertRaises(KernelError) as caught:
            run(p,n=.375,d=.5)
        self.assertEqual(caught.exception.diagnostic['kind'], 'unsupported_condition')

    def test_program_with_event_state_stays_outside_scope(self):
        with self.assertRaises(CompileError) as caught:
            compile_body('@(initial_step) held=0; @(timer(0.25)) held=1; q=V(n)/V(d); V(y)<+(q>0.5)?held:0.0;', 'real held;')
        self.assertIn('decision predicates', caught.exception.diagnostic['message'])

    def test_program_with_history_operator_stays_outside_scope(self):
        with self.assertRaises((CompileError,KernelError)):
            p=compile_body('q=V(n)/V(d); V(y)<+((q>0.5)?0.9:0.0)+idt(V(ref),0);')
            run(p,n=.375,d=.5)

    def test_nonfinite_guard_division_cannot_be_rescued_by_exact_sign(self):
        p=compile_body('q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')
        with self.assertRaises(KernelError) as caught:
            run(p,n=1e308,d=.1)
        self.assertEqual(caught.exception.diagnostic['kind'], 'nonfinite_arithmetic')

    def test_step_bound_program_stays_outside_the_new_guard_scope(self):
        with self.assertRaises(CompileError):
            compile_body('$bound_step(0.1); q=V(n)/V(d); V(y)<+(q>0.5)?0.9:0.0;')

    def test_power_keeps_its_existing_scope(self):
        with self.assertRaises(CompileError):
            compile_body('q=V(n)**2/V(d); V(y)<+(q>0.5)?0.9:0.0;')

    def test_exact_certificate_counts_expanded_occurrences(self):
        body='q=V(n)/V(d)-V(n)/V(d); '+' '.join('q=q+q;' for _ in range(8))
        p=compile_body(body+' V(y)<+(q>0.0)?0.9:0.0;')
        with self.assertRaises(KernelError) as caught:
            run(p,d=.7)
        self.assertEqual(caught.exception.diagnostic['kind'], 'condition_precision')

    def test_expanded_source_ir_resource_limit_remains(self):
        expansion='q=V(n)/V(d); '+' '.join('q=q+q;' for _ in range(20))
        with self.assertRaises(CompileError) as caught:
            compile_body(expansion+' V(y)<+(q>0.5)?0.9:0.0;')
        self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
