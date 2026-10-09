"""Public error reasons, independently asserted at their owning stage."""
GUARDS = ["LANG", "TIMER", "DYNAMICS"]

import json
import unittest
from evas import CompileError, KernelError, compile_sources
from test_affine import instance, model
from test_continuous_dynamics import run
import test_manifest


class FrontendDiagnostics(unittest.TestCase):
    def test_timer_dependency_reports_scope_and_source(self):
        for value in ('V(u,r)', '0*V(u,r)', 'idt(V(u,r),0)'):
            source = model('@(initial_step) n=0; @(timer('+value+',0,1e-12)) n=n+1; V(y,r)<+n;', 'integer n;')
            with self.subTest(value=value), self.assertRaises(CompileError) as caught:
                compile_sources({'timer.va': source}, [instance()])
            error = caught.exception.diagnostic
            self.assertEqual(error['code'], 'unsupported_timer_dependency')
            self.assertEqual(error['stage'], 'lowering')
            self.assertEqual(error['capability'], 'TIMER')
            self.assertEqual(error['location']['source'], 'timer.va')
            self.assertNotIn('undeclared', error['message'])

    def test_implicit_event_reports_actual_combination_boundary(self):
        program = compile_sources({'dae.va': model('''@(initial_step) q=1;
            @(timer(0.5,0,1e-12)) q=2;
            V(y,r)<+idt(q+2*V(y,r),0)-pow(V(y,r),2);''', 'real q;')}, [instance()])
        with self.assertRaises(KernelError) as caught:
            run(program, times=[0,1])
        error = caught.exception
        self.assertEqual(error.detail['kind'], 'unsupported_implicit_dynamics')
        self.assertIn('event-free', error.detail['message'])
        self.assertEqual(error.diagnostic['category'], 'unsupported')
        self.assertEqual(error.diagnostic['capability'], 'DYNAMICS')

    def test_vector_boundary_reports_declaration_not_identifier(self):
        source = '`include "disciplines.vams"\nmodule m(y); output [1:0][1:0] y; electrical y; analog begin V(y)<+1; end endmodule'
        with self.assertRaises(CompileError) as caught:
            compile_sources({'vectors.va': source}, [instance(connections=dict(y='y'))])
        error = caught.exception.diagnostic
        self.assertEqual(error['code'], 'unsupported_vector')
        self.assertEqual(error['category'], 'unsupported')
        self.assertEqual(error['stage'], 'binding')
        self.assertEqual(error['capability'], 'LANG')
        self.assertEqual(error['location']['source'], 'vectors.va')
        self.assertIn('only one-dimensional electrical vectors', error['message'])
        self.assertNotIn('non-reserved identifier', error['message'])

    def test_unclassified_frontend_and_kernel_keep_original_information(self):
        self.assertEqual(CompileError('legacy reason').diagnostic['category'], 'unknown')
        original = dict(kind='future_failure', message='reason', sample=3, future_field=42)
        error = KernelError(original)
        self.assertEqual(error.detail, original)
        self.assertEqual(error.diagnostic['category'], 'unknown')
        self.assertEqual(error.diagnostic['sample'], 3)
        self.assertEqual(error.diagnostic['future_field'], 42)


class DiagnosticCLI(unittest.TestCase):
    setUp = test_manifest.ManifestContracts.setUp
    cli = test_manifest.ManifestContracts.cli

    def test_compile_error_is_machine_readable(self):
        (self.root/'m.va').write_text(model('@(initial_step) n=0; @(timer(V(u),0,1e-12)) n=n+1; V(y)<+n;', 'integer n;'))
        result = self.cli('compile')
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr)
        self.assertEqual(error['code'], 'unsupported_timer_dependency')
        self.assertEqual(error['diagnostic_version'], 1)
