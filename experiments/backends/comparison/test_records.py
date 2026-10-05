"""Acceptance controls for evidence identity, denominator and common-subset faults."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from records import BACKENDS, GROUPS, common_errors, freshness, identity, render, sha, validate
from freeze import SELECTED, freeze


class RecordControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        evidence = self.root / 'receipt.json'
        evidence.write_text('{"synthetic":true}\n')
        self.case = {'id': 'v1-main', 'group': 'V1', 'tags': [], 'input_identity': 'input-identity'}
        target = {b: {'revision': 'rev', 'runtime_identity': 'binary'} for b in BACKENDS}
        self.data = {'schema_version': 1, 'updated': '2026-10-06', 'targets': target,
            'datasets': [{'id': 'test', 'label': 'synthetic only', 'state': 'frozen', 'scope': 'finite control',
                          'cases': [self.case], 'denominator': 1, 'profiles': ['base'],
                          'case_manifest_sha256': identity([self.case])},
                         {'id': 'pending', 'label': 'pending new', 'state': 'pending', 'scope': 'unknown',
                          'cases': None, 'denominator': None, 'profiles': ['base']}],
            'coverage': {g: {'capabilities': ['LIN'], 'issues': [], 'boundary': 'boundary',
                            'independent_answer': 'independent algebra'} for g in GROUPS},
            'records': [dict(dataset='test', case='v1-main', backend=b, profile='base', input_identity='input-identity',
                verdict='P', stage='analysis', reason='observations_within_targets', accounting='reused',
                measurement={'revision': 'rev', 'runtime_identity': 'binary', 'run_id': 'synthetic-run'}, checker_identity='checker',
                evidence=[{'path': 'receipt.json', 'sha256': sha(evidence), 'kind': 'receipt'}],
                metrics={'voltage': {'property': 'maximum absolute exported output voltage error', 'unit': 'V', 'observed': .0002, 'budget': .001}})
                for b in BACKENDS]}

        self.matrix_path = self.root / 'matrix.json'
        self.matrix = {'records': [{'backend': b, 'condition': 'v1-main', 'profile': 'base',
            'source_run_id': 'synthetic-run', 'analysis': {'status': 'observations_within_targets',
                'v1_screen': {'max_observed_error': {'y': {'error_v': .0002}}}}} for b in BACKENDS]}
        self.write_matrix()

    def write_matrix(self):
        self.matrix_path.write_text(json.dumps(self.matrix))
        for r in self.data['records']:
            r['observation_binding'] = {'path': 'matrix.json', 'sha256': sha(self.matrix_path),
                'format': 'matrix', 'selector': {'backend': r['backend'], 'condition': r['case'],
                'profile': r['profile'], 'source_run_id': r['measurement']['run_id']}}

    def test_counts_round_trip_and_pending_unknown(self):
        validate(self.data, self.root)
        text = render(self.data, self.root)
        self.assertIn('P1 F0 U0 X0 I0 T0 / N=1', text)
        self.assertIn('N=unknown', text)
        for label in ('Spectre', 'ngspice + OpenVAF-R', 'Gnucap + modelgen-verilog', 'EVAS'):
            self.assertIn(label, text)
        for group in GROUPS:
            self.assertIn('| ' + group + ' |', text)

    def test_pending_application_candidate_still_checks_frozen_source(self):
        source = self.root / 'dut.va'
        checker = self.root / 'checker.py'
        cases = self.root / 'task/cases.json'
        cases.parent.mkdir()
        source.write_text('correct reference')
        checker.write_text('independent checker')
        case = {'name': 'fixed', 'input': 3}
        cases.write_text(json.dumps([case]))
        candidate = {'case_name': 'fixed', 'case_sha256': identity(case),
                     'source_sha256': sha(source), 'checker_sha256': sha(checker),
                     'sources': [{'path': str(p.relative_to(self.root)), 'sha256': sha(p)}
                                 for p in (source, checker, cases)]}
        self.data['datasets'][1]['candidates'] = [candidate]
        validate(self.data, self.root)
        candidate['case_sha256'] = 'different case'
        with self.assertRaisesRegex(ValueError, 'frozen case identity'):
            validate(self.data, self.root)
        candidate['case_sha256'] = identity(case)
        source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'fixed 40-hex revision|changed compact evidence'):
            validate(self.data, self.root)

    def test_duplicate_case_assignment_rejected(self):
        self.data['datasets'][0]['cases'].append(copy.deepcopy(self.case))
        with self.assertRaisesRegex(ValueError, 'duplicate case'):
            validate(self.data, self.root)

    def test_denominator_shrinkage_rejected(self):
        self.data['records'].pop()
        with self.assertRaisesRegex(ValueError, 'denominator shrinkage'):
            validate(self.data, self.root)

    def test_missing_evidence_cannot_pass(self):
        self.data['records'][0]['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'missing evidence'):
            validate(self.data, self.root)

    def test_stage_failure_cannot_pass(self):
        self.data['records'][0]['stage'] = 'compile'
        with self.assertRaisesRegex(ValueError, 'incomplete evidence'):
            validate(self.data, self.root)

    def test_stale_measurement_cannot_claim_latest(self):
        self.data['targets']['evas']['runtime_identity'] = 'new-binary'
        r = self.data['records'][-1]
        self.assertEqual(freshness(r, self.data['targets']), 'stale')
        self.assertIn('需复验 1', render(self.data, self.root))
        r['claimed_freshness'] = 'current'
        with self.assertRaisesRegex(ValueError, 'old measurement'):
            validate(self.data, self.root)

    def test_docs_only_reuse_needs_identity_and_justification(self):
        r = self.data['records'][-1]
        r['measurement']['revision'] = 'old-doc-revision'
        self.assertEqual(freshness(r, self.data['targets']), 'stale')
        r['reuse_justification'] = 'Runtime and parser identity unchanged; documentation only.'
        self.assertEqual(freshness(r, self.data['targets']), 'current')
        r['measurement']['runtime_identity'] = 'old-runtime'
        self.assertEqual(freshness(r, self.data['targets']), 'stale')

    def test_missing_output_never_becomes_zero_error(self):
        self.data['records'][0]['metrics'] = {}
        result = common_errors(self.data, 'test', 'base', 'voltage')
        self.assertEqual(result['cases'], [])
        self.assertTrue(all(v is None for v in result['maxima'].values()))
        with self.assertRaisesRegex(ValueError, 'metric'):
            render(self.data, self.root)

    def test_common_subset_units_and_budget_retained(self):
        result = common_errors(self.data, 'test', 'base', 'voltage')
        self.assertEqual(result['cases'], ['v1-main'])
        for value in result['maxima'].values():
            self.assertAlmostEqual(value['normalized'], .2)
            self.assertEqual(value['original'][0]['unit'], 'V')
            self.assertEqual(value['original'][0]['budget'], .001)
        self.data['records'][0]['metrics']['voltage']['budget'] = .002
        with self.assertRaisesRegex(ValueError, 'unequal'):
            common_errors(self.data, 'test', 'base', 'voltage')

    def test_nonfinite_or_zero_budget_rejected(self):
        for value in (0, float('nan'), float('inf')):
            with self.subTest(value=value):
                self.data['records'][0]['metrics']['voltage']['budget'] = value
                with self.assertRaisesRegex(ValueError, 'invalid observed|metric'):
                    validate(self.data, self.root)

    def test_raw_absence_does_not_invalidate_compact_receipt(self):
        for r in self.data['records']:
            r['availability'] = {'raw': 'private historical archive; absent locally'}
            r['accounting'] = 'reused'
        validate(self.data, self.root)
        (self.root / 'receipt.json').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed compact evidence'):
            validate(self.data, self.root)

    def test_unrun_cannot_contain_observations(self):
        self.data['records'][0]['verdict'] = 'T'
        self.data['records'][0]['accounting'] = 'unrun'
        with self.assertRaisesRegex(ValueError, 'unrun'):
            validate(self.data, self.root)

    def execution_receipt(self):
        r = self.data['records'][-1]
        observation = self.root / 'observation.json'
        observation.write_text(json.dumps({'status': 'observations_within_targets', 'v1_screen': {'max_observed_error': {'y': {'error_v': .0002}}}}))
        receipt = self.root / 'execution.json'
        value = {'backend': 'evas', 'condition': 'v1-main', 'profile': 'base',
                 'input_identity': 'input-identity', 'source_revision': 'rev', 'runtime_identity': 'binary',
                 'checker_identity': 'checker', 'commands': [{'stage': 'simulate', 'exit_code': 0}],
                 'input_manifest_sha256': 'manifest', 'kernel_sha256': 'actual-kernel',
                 'waveform_sha256': 'actual-output', 'effective_settings': {'stop': 1},
                 'execution_status': 'waveform_available',
                 'observation': {'path': 'observation.json', 'sha256': sha(observation)}}
        receipt.write_text(json.dumps(value))
        r['accounting'] = 'executed'
        r['measurement'].update(kernel_sha256='actual-kernel', output_sha256='actual-output')
        r['execution_receipt'] = {'path': 'execution.json', 'sha256': sha(receipt)}
        return r, value, receipt

    def test_new_observation_requires_real_receipt_and_kernel(self):
        self.data['records'][-1]['accounting'] = 'executed'
        with self.assertRaisesRegex(ValueError, 'execution receipt'):
            validate(self.data, self.root)
        r, value, path = self.execution_receipt()
        validate(self.data, self.root)
        value['kernel_sha256'] = None
        path.write_text(json.dumps(value))
        r['execution_receipt']['sha256'] = sha(path)
        with self.assertRaisesRegex(ValueError, 'source-only'):
            validate(self.data, self.root)

    def test_receipt_bound_to_actual_configuration(self):
        r, value, path = self.execution_receipt()
        value['condition'] = 'other-condition'
        path.write_text(json.dumps(value))
        r['execution_receipt']['sha256'] = sha(path)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            validate(self.data, self.root)

    def test_fail_unknown_unsupported_and_unrun_distinct(self):
        for r, verdict in zip(self.data['records'], ('F', 'U', 'I', 'X'), strict=True):
            r['verdict'] = verdict
            r['reason'] = 'synthetic ' + verdict
        statuses = {'F': 'observed_violation', 'U': 'confirmed_unsupported', 'I': 'unresolved', 'X': 'execution_failed'}
        for r, observed in zip(self.data['records'], self.matrix['records'], strict=True):
            r['reason'] = statuses[r['verdict']]
            observed['analysis']['status'] = r['reason']
        self.write_matrix()
        text = render(self.data, self.root)
        self.assertIn('F1', text)
        self.assertIn('U1', text)
        self.assertIn('I1', text)
        self.assertIn('X1', text)
        self.assertIn('不适用，选定分母 N=0', text)


class FrozenBatchControls(unittest.TestCase):
    def test_exact_32_shared_dut_and_current_base_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'batch'
            plan = freeze(root)
            self.assertEqual(len(plan), 32)
            self.assertEqual({p['condition'] for p in plan}, set(SELECTED))
            self.assertEqual({p['profile'] for p in plan}, {'base'})
            for case in SELECTED:
                records = [p for p in plan if p['condition'] == case]
                self.assertEqual({p['backend'] for p in records}, set(BACKENDS))
                self.assertEqual(len({p['source_sha256'] for p in records}), 1)
                self.assertEqual(len({p['input_identity'] for p in records}), 1)
                for item in records:
                    work = root / item['work']
                    self.assertIn('pre_osdi dut.osdi', (work / 'tb.cir').read_text())
                    self.assertIn('short=1e-9', (work / 'tb.gc').read_text())
                    self.assertNotIn('uic', (work / 'tb.cir').read_text().lower())
            with self.assertRaises(FileExistsError):
                freeze(root)


if __name__ == '__main__':
    unittest.main()
