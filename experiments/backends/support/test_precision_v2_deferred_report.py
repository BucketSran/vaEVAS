"""Synthetic deferred execution through identity-checked local v2 reporting."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import precision_v2_run as runner
import precision_v2_report as reporter
from precision_v2 import load_contract, observation_plan
from inputs import save, sha


class DeferredReportTests(unittest.TestCase):
    def fixture(self, base, broken=None):
        inputs = base / 'inputs'
        inputs.mkdir()
        contract = load_contract()
        card = copy.deepcopy(next(c for c in contract['cards'] if c['id'] == 'LP-NONZERO'))
        card.update(id='LP-TEST', inputs={'u': [[0., 1.], [1., 1.]]},
                    stop_s=1., unit_s=1., tau_s=1., initial_V=1.)
        contract['cards'] = [card]
        contract['profiles'] = contract['profiles'][:1]
        times = observation_plan(card, contract)['times_s']
        request = {'reltol': 1e-5, 'vabstol_V': 1e-9, 'iabstol_A': 1e-13,
                   'stop_s': 1., 'maxstep_s': .03125, 'spice_maxstep_s': .03125}
        save(inputs / 'cards.json', contract)
        plan = []
        for label in ('a', 'b'):
            work = inputs / label
            work.mkdir()
            (work / 'dut.va').write_text(card['source'])
            (work / 'request.json').write_text('{}')
            save(work / 'condition.json', card)
            save(work / 'requested_settings.json', request)
            save(work / 'requested_times.json', times)
            save(work / 'observation_plan.json', observation_plan(card, contract))
            plan.append({'label': label, 'condition': card['id'], 'backend': 'evas',
                         'family': 'first_order', 'profile': 'base', 'work': label,
                         'deck': 'request.json', 'source_sha256': sha(work / 'dut.va')})
        save(inputs / 'PLAN.json', plan)
        save(inputs / 'MANIFEST.json', {str(p.relative_to(inputs)): sha(p)
                                      for p in inputs.rglob('*') if p.is_file()})
        save(base / 'SOURCE_PROVENANCE.json', {'kind': 'synthetic control-chain calibration'})
        profile = base / 'host.json'
        save(profile, {})
        col = base / 'collected' / 'first_order-evas'
        out = col / 'outputs' / 'first_order-evas'
        def export(backend, tool, env, work):
            (work / 'waveform.csv').write_text('time,u,y\n' + ''.join(f'{t!r},1,1\n' for t in times))
            save(work / 'effective.json', {'runtime_controls': {'relative': request['reltol'],
                 'absolute_V': request['vabstol_V'], 'stop_s': 1., 'max_step_s': .03125,
                 'max_step_applied': True}})
            save(work / 'raw-response.json', {'nodes': ['u', 'y'], 'engine': 'synthetic',
                 'observation_evidence': {'initial_settled': True, 'schema_version': 1, 'nodes': ['u', 'y']},
                 'strobe_evidence': {'times': times, 'sample_origins': ['accepted_controller_frame'] * len(times),
                                     'voltages_V': [[1., 1.]] * len(times)},
                 'transient': {'accepted_steps': len(times)}})
            if work.name == 'a' and broken == 'missing_controls':
                (work / 'effective.json').unlink()
            if work.name == 'a' and broken == 'bad_controls':
                (work / 'effective.json').write_text('{')
            if work.name == 'a' and broken == 'bad_response':
                (work / 'raw-response.json').write_text('[]')
            if work.name == 'a' and broken == 'missing_response':
                (work / 'raw-response.json').unlink()
            if work.name == 'a' and broken == 'bad_control_shape':
                (work / 'effective.json').write_text('[]')
            if work.name == 'a' and broken == 'unapplied_controls':
                effective = json.loads((work / 'effective.json').read_text())
                effective['runtime_controls']['max_step_applied'] = False
                (work / 'effective.json').write_text(json.dumps(effective))
            return {'status': 'waveform_available', 'waveform': 'waveform.csv', 'abort_batch': False}
        with patch.object(runner, 'verify'), patch.object(runner, 'verify_tool'), \
             patch.object(runner, 'preflight', return_value=({'kernel_sha256': 'synthetic'}, {})), \
             patch.object(runner, 'execute_one', side_effect=export), \
             patch.object(runner, 'effective_settings', side_effect=AssertionError('remote analysis')):
            runner.run(inputs, out, 'evas', profile, 'first_order', defer_analysis=True)
        (col / 'operator-receipts').mkdir()
        (col / 'build').mkdir()
        save(col / 'operator-receipts' / 'first_order-evas.json',
             {'cleanup_confirmed': True, 'status': 'complete', 'child_exit_code': 0, 'exit_code': 0})
        (col / 'raw.tar.gz').write_bytes(b'synthetic collected archive identity')
        save(col / 'COLLECTION.json', {'archive_sha256': sha(col / 'raw.tar.gz')})
        save(col / 'build' / 'BUILD.json', {k: 'synthetic' for k in
             ('source_revision', 'source_manifest_sha256', 'kernel_sha256', 'cargo_lock_sha256', 'toolchain')} | {'returncode': 0})
        return out

    def test_deferred_raw_controls_restore_qualified_report_without_rewriting_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out = self.fixture(base)
            before = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
            value = reporter.report(base)
            self.assertEqual([r['qualification']['status'] for r in value['results']], ['qualified', 'qualified'])
            self.assertTrue(all(t['status'] == 'pass' for r in value['results'] for t in r['tiers'].values()))
            for r in value['results']:
                self.assertEqual(r['settings_readback']['origin'], 'reconstructed_from_verified_raw')
                self.assertEqual(r['settings_readback']['artifacts']['effective.json'], sha(out / 'runs' / r['label'] / 'effective.json'))
                self.assertEqual(r['effective_settings']['actual']['maxstep'], .03125)
            self.assertIn('experiments/backends/paper/settings_readback.py', value['analysis_dependencies'])
            self.assertEqual(before, {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()})

    def test_missing_or_malformed_control_evidence_remains_nonqualified_and_batch_continues(self):
        for broken in ('missing_controls', 'bad_controls', 'bad_response', 'missing_response',
                       'bad_control_shape', 'unapplied_controls'):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                self.fixture(base, broken)
                value = reporter.report(base)
                a, b = value['results']
                self.assertEqual(a['qualification']['status'], 'evidence_insufficient')
                self.assertTrue(a['qualification']['issues'])
                self.assertTrue(all(t['status'] == 'evidence_insufficient' for t in a['tiers'].values()))
                self.assertEqual(b['qualification']['status'], 'qualified')

    def test_raw_identity_drift_is_rejected_before_settings_reconstruction(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out = self.fixture(base)
            (out / 'runs' / 'a' / 'effective.json').write_text('{}')
            with patch.object(reporter, 'effective_settings', create=True) as settings:
                with self.assertRaisesRegex(ValueError, 'execution file drift'):
                    reporter.report(base)
                settings.assert_not_called()

    def test_unsealed_added_control_evidence_cannot_restore_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out = self.fixture(base, 'missing_controls')
            (out / 'runs' / 'a' / 'effective.json').write_bytes((out / 'runs' / 'b' / 'effective.json').read_bytes())
            with patch.object(reporter, 'effective_settings') as settings:
                with self.assertRaisesRegex(ValueError, 'unsealed analysis input'):
                    reporter.report(base)
                settings.assert_not_called()

    def test_sealed_execution_request_drift_cannot_restore_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out = self.fixture(base)
            path = out / 'runs' / 'a' / 'requested_settings.json'
            value = json.loads(path.read_text())
            value['reltol'] *= 10
            path.write_text(json.dumps(value))
            manifest_path = out / 'FILE_MANIFEST.json'
            manifest = json.loads(manifest_path.read_text())
            manifest[str(path.relative_to(out))] = {'sha256': sha(path), 'bytes': path.stat().st_size}
            manifest_path.write_text(json.dumps(manifest))
            with patch.object(reporter, 'effective_settings') as settings:
                with self.assertRaisesRegex(ValueError, 'executed input drift'):
                    reporter.report(base)
                settings.assert_not_called()


if __name__ == '__main__':
    unittest.main()
