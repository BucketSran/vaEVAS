"""Pure driven polynomial guards preserve whole-program and accuracy boundaries."""
import unittest
from evas import CompileError, KernelError, Instance, compile_sources
from test_source_rational_guards import compile_body, run, outputs

GUARDS = ["LANG", "LIN", "ANALOG"]


class SourcePolynomialGuards(unittest.TestCase):
    def test_differential_product_clamp(self):
        p = compile_body('q=2.0*V(n,ref)*V(d,en)+0.2; if(q>0.8) q=0.8; else if(q< -0.4) q=-0.4; V(y)<+q;')
        for n, expected in [(-0.1,-0.4),(0.5,0.7),(1.0,0.8)]:
            values = outputs(run(p,n=n,ref=0.25,d=1.5,en=0.5))
            for value in values:
                self.assertAlmostEqual(value, expected)

    def test_exact_product_cancellation_boundary(self):
        p = compile_body('q=V(n)*V(d)-V(n)*V(d); V(y)<+(q>0.0)?0.9:0.0;')
        self.assertEqual(outputs(run(p,n=0.3,d=0.7)), [0,0,0])

    def test_uncertain_product_guard_rejects(self):
        p = compile_body('q=V(n)*V(d); V(y)<+(q>0.21)?0.9:0.0;')
        with self.assertRaises(KernelError) as caught:
            run(p,n=0.3,d=0.7,errors={'n':0.01})
        self.assertEqual(caught.exception.diagnostic['kind'], 'condition_precision')

    def test_event_state_stays_outside_scope(self):
        with self.assertRaises(CompileError) as caught:
            compile_body('@(initial_step) held=0; @(timer(0.25)) held=1; q=V(n)*V(d); V(y)<+(q>0.5)?held:0;', 'real held;')
        self.assertIn('decision predicates',caught.exception.diagnostic['message'])

    def test_history_stays_outside_scope(self):
        with self.assertRaises((CompileError,KernelError)):
            run(compile_body('q=V(n)*V(d); V(y)<+((q>0.5)?0.9:0.0)+idt(V(ref),0);'))

    def test_power_stays_outside_scope(self):
        with self.assertRaises(CompileError):
            compile_body('q=V(n)**2; V(y)<+(q>0.5)?0.9:0.0;')

    def test_step_bound_stays_outside_scope(self):
        with self.assertRaises(CompileError):
            compile_body('$bound_step(0.1); q=V(n)*V(d); V(y)<+(q>0.5)?0.9:0.0;')

    def test_hidden_output_dependency_is_audited(self):
        with self.assertRaises((CompileError,KernelError)):
            run(compile_body('q=V(n)*V(d); result=(V(en)>0.5)?0.9:0.0*V(y); V(y)<+(q>0.5)?result:0;'))

    def test_inout_output_is_not_actually_driven(self):
        p=compile_body('q=V(n)*V(d); result=(V(en)>0.5)?0.9:0.0*V(y); V(y)<+(q>0.5)?result:0;',inout_output=True)
        with self.assertRaises(KernelError) as caught:
            run(p)
        self.assertEqual(caught.exception.diagnostic['kind'],'unsupported_condition')

    def test_nonfinite_selected_operations_reject_before_sign_certificate(self):
        cases = [
            ('V(n)*V(d)', 1e308, 1e308),
            ('V(n)+V(d)', 1e308, 1e308),
            ('1e308*V(n)', 2.0, 0.6),
            ('(V(n)*V(d))-(V(n)*V(d))', 1e308, 1e308),
        ]
        for expression, n, d in cases:
            with self.subTest(expression=expression):
                p=compile_body('q='+expression+'; V(y)<+(q>0.5)?0.9:0.0;')
                with self.assertRaises(KernelError) as caught:
                    run(p,n=n,d=d)
                self.assertEqual(caught.exception.diagnostic['kind'],'nonfinite_arithmetic')

    def test_existing_positive_helper_with_later_transition_keeps_compile_support(self):
        # The positive guard has an older affine normalization path. A later
        # history operator must not leave a speculative source-only marker.
        p=compile_body('if(V(d)<0.55) result=0.0; else begin q=(V(n)-V(ref))/V(d); result=(q>0.5)?1.0:0.0; end V(y)<+V(ref)+V(d)*transition(result,0.0,0.01,0.01);')
        self.assertEqual(len(p.operators),1)
        def divisions(value):
            if isinstance(value,dict):
                return value.get('op')=='divide' or any(divisions(child) for child in value.values())
            if isinstance(value,list):
                return any(divisions(child) for child in value)
            return False
        self.assertFalse(divisions(p.to_dict()))

    def test_existing_positive_helper_composes_with_another_operator_instance(self):
        source = '`include "disciplines.vams"\nmodule decision(n,d,y); input n,d; output y; electrical n,d,y; real q,result;\nanalog begin if(V(d)<0.55) result=0.0; else begin\nq=V(n)/V(d); result=(q>0.5)?1.0:0.0; end V(y)<+result; end endmodule\nmodule history(a,z); input a; output z; electrical a,z;\nanalog begin V(z)<+idt(V(a),0.0); end endmodule'
        p=compile_sources({'composition.va':source},[
            Instance('first','decision',{'n':'n','d':'d','y':'y'}),
            Instance('later','history',{'a':'a','z':'z'}),
        ])
        self.assertEqual(len(p.operators),1)

    def test_expanded_ir_budget_is_unchanged(self):
        with self.assertRaises(CompileError) as caught:
            compile_body('q=V(n)*V(d); '+'q=q+q;'*20+' V(y)<+(q>0.5)?0.9:0.0;')
        self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
