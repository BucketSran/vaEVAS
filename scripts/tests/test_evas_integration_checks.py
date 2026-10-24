"""Early gates must distinguish the recorded wrong path and unrun evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from evas_integration_checks import budget_owners, initial_budget


class IntegrationChecks(unittest.TestCase):
    @unittest.skipUnless(shutil.which('rustc'), 'Rust primitive probe requires rustc')
    def test_production_optional_work_budget_retains_local_sticky_probe(self):
        result = initial_budget(ROOT/'evas/rust_core/src/initial_state_invariance.rs')
        self.assertEqual(result['exhausted_retry'], 'refused')
        self.assertIn('aggregate caller work still needs review', result['scope'])

    @unittest.skipUnless(shutil.which('rustc'), 'Rust primitive probe requires rustc')
    def test_optional_work_adaptation_still_rejects_a_refunding_primitive(self):
        # Calibration: refusing an oversized take must also consume the local
        # remainder. Merely adding a compilable Work type cannot turn this green.
        for fields in ['usize', 'usize, Option<crate::transition_source_plan::Work>']:
            source = ('struct Budget('+fields+');\n'
                      'impl Budget {fn take(&mut self,n:usize)->Option<()> {'
                      'if n>self.0{return None;} self.0-=n;Some(())}}\n'
                      'fn owner(){let _=Budget(3'+(',None' if ',' in fields else '')+');}\n')
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)/'budget.rs'
                path.write_text(source)
                with self.assertRaisesRegex(AssertionError, 'recovered on retry'):
                    initial_budget(path)

    def test_new_independent_allowance_has_two_production_owners(self):
        bad = '''struct Budget(usize);
fn prove(){let b=Budget(2_000_000);}
pub(crate) fn unchanged_at_inputs(){let extra=Budget(2_000_000);}
#[cfg(test)] fn unrelated_test(){let b=Budget(3);}
#[cfg(test)] mod tests {fn other(){let b=Budget(20);}}'''
        self.assertEqual(budget_owners(bad), {'prove': 1, 'unchanged_at_inputs': 1})
        good = '''struct Budget(usize);
#[cfg(test)] fn unchanged(){let b=Budget(2_000_000);}
fn prove(b:&mut Budget){}
fn legacy_remaining(limit:usize){prove(&mut Budget(limit));let remaining=Budget(limit);}
fn prove_at_inputs(b:&mut Budget){}'''
        self.assertEqual(budget_owners(good), {'legacy_remaining': 2})

    def test_nested_production_modules_and_impls_cannot_hide_allowances(self):
        for item in ('mod new_fallback { fn independent(){let b=Budget(20);} }',
                     'impl Fallback { fn independent(){let b=Budget(20);} }'):
            with self.subTest(item=item):
                owners = budget_owners('fn legacy(){let b=Budget(10);}'+item)
                self.assertEqual(len(owners), 2, owners)
                self.assertEqual(sum(owners.values()), 2)
        owners = budget_owners('fn legacy(){let b=Budget(10);}'
                              '#[cfg(test)] mod tests { impl Foo {fn new(){let b=Budget(5);}}}')
        self.assertEqual(owners, {'legacy': 1})

    def test_plan_delta_selects_contracts_and_preserves_unknown_coverage(self):
        from evas_check_policy import early_checks_for_plan
        from evas_integration_checks import CHECKS
        def selected(paths, **extra):
            return early_checks_for_plan(dict(base='a'*40, head='b'*40, paths=paths, **extra))
        self.assertEqual(selected(['README.md', '.agents/skills/evas-validate/SKILL.md']), [])
        self.assertEqual(selected(['scripts/evas_integration_checks.py']), [])
        self.assertEqual(selected(['evas/src/evas/compact_source_select.py']), ['representation'])
        self.assertEqual(selected(['evas/src/evas/event_index_domains.py']), ['integer-budget'])
        self.assertEqual(selected(['evas/src/evas/compact_source_select.py',
                                   'evas/src/evas/event_index_domains.py']),
                         ['representation', 'integer-budget'])
        for path in ('evas/rust_core/src/event_numeric.rs', 'evas/src/evas/ir.py',
                     'evas/src/evas/new_shared.py', 'evas/rust_core/Cargo.toml'):
            self.assertEqual(selected([path]), list(CHECKS))
        self.assertEqual(early_checks_for_plan({'paths': []}), list(CHECKS))
        self.assertEqual(selected(['evas/src/evas/ir.py'], mode='iteration',
                                  iteration_paths=['README.md']), [])

    def test_rust_consumer_delta_requires_actual_runtime_even_with_unchanged_ir(self):
        from evas_check_policy import early_runtime_for_plan
        plan = dict(base='a'*40, head='b'*40, paths=['evas/rust_core/src/event_numeric.rs'])
        self.assertTrue(early_runtime_for_plan(plan))
        self.assertFalse(early_runtime_for_plan(dict(plan, paths=['README.md'])))
        code = f"""import sys
sys.path[:0]=[{str(ROOT/'scripts')!r},{str(ROOT/'evas/src')!r}]
from evas_integration_checks import representation,NeedsRuntime
try:representation(require_runtime=True)
except NeedsRuntime:pass
else:raise AssertionError('unchanged compiler IR cannot qualify a changed Rust consumer')
"""
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_documentation_delta_does_not_import_candidate_or_require_kernel(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan, report = Path(temporary)/'plan.json', Path(temporary)/'report.json'
            plan.write_text(json.dumps(dict(base='a'*40, head='b'*40, paths=['README.md'])))
            result = subprocess.run([sys.executable, '-I', '-B',
                                     str(ROOT/'scripts/evas_check_policy.py'), '--early-checks',
                                     '--plan', str(plan), '--source-root', temporary,
                                     '--kernel', str(Path(temporary)/'nonexistent-kernel'),
                                     '--report', str(report)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['checks'], [])
            self.assertFalse(evidence['acceptance_complete'])

    def test_representation_gate_rejects_the_original_wrong_producer(self):
        # Force the exact wrong lowering decision with the real public compiler;
        # the test does not substitute arithmetic or manufacture expected IR.
        code = f'''import sys,runpy
sys.path[:0]=[{str(ROOT/'scripts')!r},{str(ROOT/'evas/src')!r}]
from evas import instance_compiler as compiler
from evas.ir import Assignment
compiler.InstanceCompiler.event_assignment=lambda self,state,value,origin,**kw:(Assignment(state,value),)
check=runpy.run_path({str(ROOT/'scripts/evas_integration_checks.py')!r})['representation']
try:check()
except AssertionError as error:
 assert 'RHS Select' in str(error),error
else:raise AssertionError('wrong producer escaped the gate')
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_missing_budget_check_is_blocked_not_passed(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary)/'result.json'
            result = subprocess.run(
                [sys.executable, '-I', '-B', str(ROOT/'scripts/evas_check_policy.py'),
                 '--early-checks', '--source-root', temporary, '--checks',
                 'integer-budget', '--report', str(report)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['checks'][0]['status'], 'blocked')
            self.assertFalse(evidence['passed'])
            self.assertFalse(evidence['acceptance_complete'])

    def test_unknown_contract_cannot_return_an_empty_green_result(self):
        from evas_integration_checks import run
        with self.assertRaisesRegex(ValueError, 'unknown early checks'):
            run(ROOT, checks=['unknown'])


if __name__ == '__main__':
    unittest.main()
