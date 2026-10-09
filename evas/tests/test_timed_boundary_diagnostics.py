"""Reject timed boundary subsets with evidence-based reasons, never added support."""
GUARDS=['LANG','TRANSITION']
import json,unittest
from evas import CompileError,KernelError,compile_sources
from test_affine import instance,model
import test_manifest
SOURCE=lambda expression:model('@(initial_step) q=0; V(y,r)<+'+expression+';', 'real q;')
CASES=[('transition(q)', 'unsupported_transition_default_edges','parse','transition requires 3 or 4 explicit arguments'),
       ('transition(q,0)', 'unsupported_transition_default_edges','parse','transition requires 3 or 4 explicit arguments'),
       ('transition(q,0,0)', 'unsupported_transition_zero_edges','lowering','transition requires nonnegative delay and positive explicit edge times'),
       ('transition(q,0,0.5,0)', 'unsupported_transition_zero_edges','lowering','transition requires nonnegative delay and positive explicit edge times'),
       ('transition(q,q,0.5)', 'unsupported_transition_timing_dependency','lowering',"unknown parameter 'q'"),
       ('transition(q,0,0*q+0.5)', 'unsupported_transition_timing_dependency','lowering',"unknown parameter 'q'"),
       ('transition(q,0,0.5,q)', 'unsupported_transition_timing_dependency','lowering',"unknown parameter 'q'")]
# One representative guards the shared non-transition settings path.
OUTSIDE_BOUNDARIES=[('absdelay(q,q)','compile_error','compile',"unknown parameter 'q'"),
                    ('transition(q,0,0.5,0.5,0)','syntax_error','parse','transition requires 3 or 4 explicit arguments')]
class TimedBoundaryReasons(unittest.TestCase):
 def test_actual_api_reasons_preserve_messages_and_origins(self):
  for expression,code,stage,message in CASES:
   with self.subTest(expression=expression),self.assertRaises(CompileError) as caught:compile_sources({'timing.va':SOURCE(expression)},[instance()])
   error=caught.exception.diagnostic
   self.assertEqual((error['code'],error['category'],error['stage'],error['capability']),(code,'unsupported',stage,'TRANSITION'))
   self.assertIn(message,str(caught.exception));self.assertEqual(error['message'],str(caught.exception))
   self.assertEqual(error['location']['source'],'timing.va');self.assertGreater(error['location']['line'],0)
 def test_outside_scope_api_rejections_keep_their_original_reason(self):
  for expression in ['transition(q,-1,0.5)','transition(q,0,-0.5)','transition(q,0,0.5,-0.5)','transition(q,-1,0)','transition(q,0,missing)']:
   with self.subTest(expression=expression),self.assertRaises(CompileError) as caught:compile_sources({'negative.va':SOURCE(expression)},[instance()])
   self.assertEqual(caught.exception.diagnostic['category'],'unknown')
   self.assertEqual(caught.exception.diagnostic['code'],'compile_error')
  for expression,code,stage,message in OUTSIDE_BOUNDARIES:
   with self.subTest(expression=expression),self.assertRaises(CompileError) as caught:compile_sources({'negative.va':SOURCE(expression)},[instance()])
   diagnostic=caught.exception.diagnostic
   self.assertEqual((diagnostic['code'],diagnostic['category'],diagnostic['stage']),(code,'unknown',stage))
   self.assertIn(message,diagnostic['message'])
 def test_future_payload_and_unclassified_frontend_remain_unknown(self):
  self.assertEqual(CompileError('legacy').diagnostic['category'],'unknown')
  payload={'kind':'unsupported_transition_zero_edges','message':'future','diagnostic_version':2,'sample':4,'other':19}
  error=KernelError(payload);self.assertEqual(error.detail,payload);self.assertEqual(error.diagnostic['category'],'unknown');self.assertEqual(error.diagnostic['sample'],4)
class TimedBoundaryCLI(unittest.TestCase):
 setUp=test_manifest.ManifestContracts.setUp
 cli=test_manifest.ManifestContracts.cli
 def test_outside_scope_cli_rejections_keep_their_original_reason(self):
  controls=[('transition(q,-1,0)','compile_error','compile','transition requires nonnegative delay and positive explicit edge times'),
            ('transition(q,0,missing)','compile_error','compile',"unknown parameter 'missing'")]
  for expression,code,stage,message in controls+OUTSIDE_BOUNDARIES:
   (self.root/'m.va').write_text(SOURCE(expression))
   with self.subTest(expression=expression):
    result=self.cli('compile');self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
    diagnostic=json.loads(result.stderr);self.assertEqual((diagnostic['code'],diagnostic['category'],diagnostic['stage']),(code,'unknown',stage));self.assertIn(message,diagnostic['message'])
 def test_real_compile_cli_matches_api_reason_and_preserves_failure(self):
  for expression,code,stage,message in CASES:
   (self.root/'m.va').write_text(SOURCE(expression))
   with self.subTest(expression=expression):
    result=self.cli('compile');self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
    diagnostic=json.loads(result.stderr);self.assertEqual((diagnostic['diagnostic_version'],diagnostic['code'],diagnostic['category'],diagnostic['stage']),(1,code,'unsupported',stage));self.assertIn(message,diagnostic['message'])
if __name__=='__main__':unittest.main()
