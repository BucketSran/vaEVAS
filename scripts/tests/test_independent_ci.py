"""Real Git deltas retain delivery checks while avoiding unrelated installation."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IndependentDelivery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'commit.gpgsign', 'false')
        hooks = self.repo / '.git/empty-hooks'
        hooks.mkdir()
        self.git('config', 'core.hooksPath', str(hooks))
        self.path = 'evas/rust_core/src/linear.rs'
        self.write(self.path, 'fn square(x: f64) -> f64 { x * x }\n')
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()

    def write(self, name, text):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def plan(self):
        head = self.commit()
        return load('ci_selection').select(self.repo, 'push', {'before': self.base, 'after': head})

    def test_numeric_delta_keeps_regression_but_omits_installation(self):
        self.write(self.path, 'fn square(x: f64) -> f64 { x.mul_add(x, 0.0) }\n')
        plan = self.plan()
        self.assertTrue(plan['regression'])
        self.assertTrue(plan['differential'])
        self.assertTrue(plan['fuzz'])
        self.assertFalse(plan['package'])
        self.assertFalse(plan['delivery_required']['package'])

    def test_real_numeric_module_prose_does_not_create_installation_dependency(self):
        source = (ROOT / self.path).read_text()
        changed = source.replace('columns >= 32', 'columns >= 40', 1)
        self.assertNotEqual(source, changed)
        self.write(self.path, source)
        self.base = self.commit()
        self.write(self.path, changed)
        self.assertFalse(self.plan()['package'])

    def test_resource_platform_protocol_and_unknown_changes_keep_installation(self):
        for name, text in (
            (self.path, 'fn f() { let _ = include_str!("data.json"); }'),
            (self.path, '#[cfg(target_os="linux")] fn f() {}'),
            (self.path, '#[cfg /* platform */ (target_vendor="apple")] fn f() {}'),
            (self.path, '#[ /* attribute */ path="outside.rs"] mod data;'),
            (self.path, '# /* token comment */ [path="outside.rs"] mod data;'),
            (self.path, '#[unknown_attribute] fn f() {}'),
            (self.path, 'use std::{fs, env}; fn f() {}'),
            (self.path, 'use std::process::Command; fn f() {}'),
            (self.path, '#[derive(serde::Serialize)] struct Value { x: f64 }'),
            (self.path, 'custom_macro!();'),
            (self.path, 'custom_macro /* outer /* inner */ end */ !();'),
            (self.path, 'custom_macro // comment\n !();'),
            (self.path, 'std::thread_local /* comment */ ! { static X: u32 = 0; }'),
            ('evas/rust_core/src/main.rs', 'fn main() {}'),
            ('evas/rust_core/ir/src/lib.rs', 'pub const VERSION: u8 = 2;'),
            ('evas/rust_core/src/unmapped.rs', 'fn f() {}'),
            ('evas/rust_core/Cargo.lock', 'new dependency'),
            ('evas/MANIFEST.in', 'new payload'),
        ):
            with self.subTest(path=name, content=text):
                self.git('reset', '--hard', self.base)
                self.write(name, text)
                self.assertTrue(self.plan()['package'])

    def test_unavailable_content_identity_keeps_installation(self):
        ci = load('ci_selection')
        checks, _ = ci.classify_changes(self.repo, '0' * 40, self.base, [self.path])
        self.assertTrue(checks['package'])
        self.assertTrue(ci.classify([self.path])['package'])

    def test_scs_iteration_covers_public_consumers_and_retains_full_delivery(self):
        ci = load('ci_selection')
        for path in ('evas/src/evas/scs.py', 'evas/src/evas/scs_sources.py'):
            with self.subTest(path=path):
                plan = ci.execution_plan(ROOT, [path], ci.classify([path]), 'iteration')
                self.assertEqual(plan['mode'], 'iteration')
                self.assertFalse(plan['regression'])
                self.assertFalse(plan['package'])
                self.assertTrue(plan['delivery_required']['regression'])
                for name in ('scs', 'scs_pulse_delay', 'scs_save', 'scs_bsource',
                             'scs_driven_nodes', 'scs_vectors', 'source_uncertainty',
                             'ansi_ports', 'case_statements', 'held_transition_targets',
                             'r01_language', 'strobe'):
                    self.assertIn('test_' + name, plan['modules'])

    def test_workflow_prose_reuses_execution_but_unknown_inputs_invalidate(self):
        evidence = load('ci_evidence')
        for name in ('CONTRIBUTING.md', '.agents/skills/vaevas-workflow/SKILL.md',
                     'docs/contributing/workspaces.md', 'unknown.md'):
            self.write(name, 'old text')
        self.commit()
        original = evidence.fingerprint(self.repo, {'tools': 'same'})
        for name in ('CONTRIBUTING.md', '.agents/skills/vaevas-workflow/SKILL.md',
                     'docs/contributing/workspaces.md'):
            self.write(name, 'new workflow prose')
            self.assertEqual(original, evidence.fingerprint(self.repo, {'tools': 'same'}))
            self.write(name, 'old text')
        self.write('unknown.md', 'potential fixture')
        self.assertNotEqual(original, evidence.fingerprint(self.repo, {'tools': 'same'}))

    def test_source_kernel_oracle_rejects_nonfinite_wrong_or_missing_observations(self):
        smoke = load('check_source_kernel')
        for values in ([], [float('nan')], [float('inf')], [0.5]):
            with self.subTest(values=values):
                result = {'nodes': ['y'], 'solutions': [{'voltages': [v]} for v in values]}
                with self.assertRaises(ValueError):
                    smoke.verify(result, [.25])


if __name__ == '__main__':
    unittest.main()
