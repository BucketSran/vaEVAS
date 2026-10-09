"""Fault controls for fixed-denominator reporting; no backend invocation."""
import hashlib
import copy
import json
from pathlib import Path
import tempfile
import unittest

import table


class TableControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runner_sha = '7' * 64
        self.checker_files = {'criteria.py': '8' * 64, 'oracle.py': '9' * 64, 'core-v1.json': table.CARDS_SHA}
        self.manifest = {'core.json': {'sha256': table.CARDS_SHA}}
        for name, content in (
                ('ADAPTER_IDENTITY.json', {'experiments/backends/paper/runner.py': self.runner_sha}),
                ('CHECKER_IDENTITY.json', {'evas/validation/paper/' + key: value for key, value in self.checker_files.items() if key != 'core-v1.json'})):
            path = self.root / name
            path.write_text(json.dumps(content))
            self.manifest[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for backend in table.BACKENDS:
            for card in table.BATCH['cards']:
                work = 'runs/' + backend + '/' + card['id']
                self.manifest[work + '/dut.va'] = {'sha256': hashlib.sha256(card['source'].encode()).hexdigest()}
                self.manifest[work + '/tb.deck'] = {'sha256': hashlib.sha256(('fixture deck ' + work).encode()).hexdigest()}
        self.input_manifest = self.artifact('INPUT_MANIFEST.json', self.manifest)

    def checker(self, **changes):
        dependency = {'files': self.checker_files, 'runtime': {'python': 'historical-fixture', 'math_sha256': '6' * 64}}
        dependency.update(changes)
        return {'version': 'paper-criteria-v1', **dependency,
                'sha256': hashlib.sha256(json.dumps(dependency, sort_keys=True).encode()).hexdigest()}

    def artifact(self, name, content):
        path = self.root / (str(len(list(self.root.iterdir()))) + '-' + name)
        path.write_text(json.dumps(content))
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def report(self, records, *args, **kwargs):
        # Reproduce runner's output manifest producer for each synthetic lane.
        final_rows = kwargs.pop('final_rows', None)
        if final_rows is None:
            unique = {}
            for record in records:
                if record.get('identity', {}).get('lane_started'):
                    row = json.loads(Path(record['execution']['path']).read_text())
                    unique[row['condition'], row['backend']] = row
            final_rows = list(unique.values())
        execution_path = self.root / 'EXECUTION.json'
        execution_path.write_text(json.dumps(final_rows))
        execution_sha = hashlib.sha256(execution_path.read_bytes()).hexdigest()
        for record in records:
            identity = record.get('identity', {})
            if not identity.get('lane_started'):
                continue
            refs = [record.get('execution'), *[identity.get(k) for k in ('tool', 'lane_started', 'condition_started', 'observation')]]
            entries = {str(Path(ref['path']).relative_to(self.root)): {'sha256': ref['sha256']} for ref in refs if ref}
            entries['EXECUTION.json'] = {'sha256': execution_sha}
            work = Path(identity['condition_started']['path']).parent
            for name in ('dut.va', 'tb.deck', 'waveform.csv', 'raw-response.json', 'psf/tran.tran.tran', 'simulate.log'):
                if (work / name).is_file():
                    entries[str((work / name).relative_to(self.root))] = {'sha256': hashlib.sha256((work / name).read_bytes()).hexdigest()}
            identity['execution_manifest'] = self.artifact('FILE_MANIFEST.json', entries)
        return table.render(records, *args, **kwargs)

    def record(self, status='P', condition='VR-01', backend='evas'):
        card = next(c for c in table.BATCH['cards'] if c['id'] == condition)
        work = 'runs/' + backend + '/' + condition
        source_sha = self.manifest[work + '/dut.va']['sha256']
        deck_sha = self.manifest[work + '/tb.deck']['sha256']
        run = self.root / ('attempt-' + str(len(list(self.root.iterdir())))) / 'runs' / condition
        run.mkdir(parents=True)
        (run / 'dut.va').write_text(card['source'])
        (run / 'tb.deck').write_text('fixture deck ' + work)
        waveform = run / 'waveform.csv'
        waveform.write_text('time,out\n0,1\n')
        observation = self.artifact('observation.json', {'condition_id': condition})
        diagnostic = self.artifact('compiler-diagnostic.json', {'stderr': 'fixture compiler: operator unsupported'}) if status == 'U' else None
        execution_status = {'U': 'compile_failed', 'X': 'runtime_timeout', 'T': 'not_run'}.get(status, 'waveform_available')
        execution = self.artifact('RESULT.json', {
            'condition': condition, 'backend': backend, 'status': execution_status,
            'source_sha256': source_sha, 'work': work, 'deck': 'tb.deck',
            'waveform': 'waveform.csv', 'waveform_sha256': hashlib.sha256(waveform.read_bytes()).hexdigest(),
            'condition_identity': hashlib.sha256(json.dumps(card, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'failure_stage': 'compile' if status == 'U' else 'simulate',
            'stages': [{'stage': 'compile', 'returncode': 1, 'log_sha256': diagnostic['sha256']}] if diagnostic else [],
            'observation': {'path': observation['path'], 'sha256': observation['sha256']},
        })
        assessment_data = {
            'condition_id': condition, 'execution_state': status if status in 'UXT' else 'completed', 'status': status,
            'properties': [{'name': 'voltage:out', 'status': status}],
            'checker_identity': self.checker(),
            'input_observation_sha256': observation['sha256'] if status not in 'UXT' else None,
            'execution_sha256': execution['sha256'],
        }
        if status == 'U':
            assessment_data['unsupported_evidence'] = self.artifact('unsupported.json', {
                'status': 'confirmed_unsupported', 'failure_stage': 'compile',
                'execution_sha256': execution['sha256'], 'reason': 'synthetic unsupported control',
                'diagnostic': diagnostic,
            })
        assessment = self.artifact('assessment.json', assessment_data)
        tool = self.artifact('TOOL_IDENTITY.json', {'profile_identity': 'f' * 64, 'kernel_sha256': 'e' * 64, 'reported': {'version': 'fixture-only'}, 'interpreter': {'version': 'fixture-python'}})
        started_data = {'condition': condition, 'tool_identity_sha256': tool['sha256'], 'source_sha256': source_sha, 'deck_sha256': deck_sha}
        started_path = run / 'STARTED.json'
        started_path.write_text(json.dumps(started_data))
        started = {'path': str(started_path), 'sha256': hashlib.sha256(started_path.read_bytes()).hexdigest()}
        lane_started = self.artifact('lane-STARTED.json', {'backend': backend, 'runner_sha256': self.runner_sha,
            'input_manifest_sha256': self.input_manifest['sha256'],
            'fixed_conditions': [c['id'] for c in table.BATCH['cards']]})
        return {'condition_id': condition, 'backend': backend, 'assessment': assessment,
                'execution': execution, 'identity': {'source_revision': 'fixture-head',
                'tool': tool, 'condition_started': started, 'lane_started': lane_started,
                'input_manifest': self.input_manifest, 'observation': observation, 'method': 'synthetic control only',
                'availability': 'local-only'}}

    def derived_record(self):
        record = self.record('I')
        work = Path(record['identity']['condition_started']['path']).parent
        rows = [{'time': 0., 'out': 1.}, {'time': 1., 'out': 2.}]
        original = {'schema_version': 1, 'condition': 'VR-01', 'backend': 'evas',
                    'status': 'observation_available', 'units': {'time': 's', 'voltage': 'V'},
                    'rows': rows, 'qualification': {'qualified': False},
                    'metadata': {'sample_origins': ['unknown', 'unknown'], 'coverage': True}}
        original_ref = self.artifact('original-observation.json', original)
        record['identity']['observation'] = original_ref
        execution = table.read_artifact(record['execution'])
        execution['observation'] = original_ref
        record['execution'] = self.artifact('actual-final.json', execution)
        old = table.read_artifact(record['assessment'])
        old.update(execution_sha256=record['execution']['sha256'], input_observation_sha256=original_ref['sha256'])
        old_ref = self.artifact('original-I-assessment.json', old)
        raw = work / 'raw-response.json'
        raw.write_text(json.dumps({'nodes': ['out'], 'transient': {'times': [0., 1.]},
                                   'solutions': [{'voltages': [1.]}, {'voltages': [2.]}]}))
        raw_ref = {'path': str(raw), 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest()}
        source = work / 'dut.va'
        source_ref = {'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        # Finalize the synthetic actual lane before constructing analysis-only artifacts.
        record['assessment'] = old_ref
        self.report([record], allow_pending=True)
        adapter_path = table.HERE / 'actual_observation.py'
        adapter = Path(self.tmp.name) / 'retained-actual-observation.py'
        adapter.write_bytes(adapter_path.read_bytes())
        adapter_ref = {'path': str(adapter), 'sha256': hashlib.sha256(adapter.read_bytes()).hexdigest()}
        evidence = self.artifact('adapter-evidence.json', {'schema_version': 1, 'condition': 'VR-01', 'backend': 'evas',
            'analysis_adapter': adapter_ref,
            'identities': {'normalized': original_ref, 'raw': raw_ref, 'source': source_ref},
            'roles': {'time': {'status': 'established'}},
            'execution_identity': {'artifacts': {'final_record': record['execution'],
                'lane_manifest': record['identity']['execution_manifest'], 'tool': record['identity']['tool']}}})
        derived = {**original, 'qualification': {'qualified': True, 'qualification_evidence': {'time': {
            'method': 'synthetic role control only', 'artifact_path': evidence['path'], 'sha256': evidence['sha256']}}},
            'metadata': {**original['metadata'], 'sample_origins': ['accepted', 'accepted']}}
        derived_ref = self.artifact('derived-observation.json', derived)
        packet = {'schema_version': 1, 'execution': record['execution'], 'original_observation': original_ref,
                  'derived_observation': derived_ref, 'raw': raw_ref, 'source': source_ref,
                  'adapter': adapter_ref, 'evidence': evidence}
        record.update(analysis_observation=derived_ref, derivation=self.artifact('derivation.json', packet),
                      analysis_method='Actual-response evidence reanalysis, synthetic control', prior_analyses=[old_ref])
        assessment = {**old, 'status': 'P', 'properties': [{'name': 'voltage:out', 'status': 'P'}],
                      'input_observation_sha256': derived_ref['sha256']}
        record['assessment'] = self.artifact('derived-assessment.json', assessment)
        return record

    def test_derived_analysis_keeps_original_I_without_new_attempt(self):
        record = self.derived_record()
        report = table.render([record], allow_pending=True)
        self.assertIn('1/0/0/0/0/11', report)
        self.assertIn('Derived analyses of unchanged executions', report)
        self.assertIn(Path(record['prior_analyses'][0]['path']).name, report)
        self.assertNotIn('Declared prior attempts', report)
        self.assertEqual(table.read_artifact(record['prior_analyses'][0])['status'], 'I')

    def test_derived_analysis_rejects_actual_or_analysis_artifact_drift(self):
        for name in ('original_observation', 'raw', 'source', 'adapter', 'evidence', 'derived_observation', 'execution'):
            with self.subTest(name=name):
                record = self.derived_record()
                packet = table.read_artifact(record['derivation'])
                packet[name] = {**packet[name], 'sha256': '0' * 64}
                record['derivation'] = self.artifact('drift-packet.json', packet)
                with self.assertRaises(ValueError):
                    table.render([record], allow_pending=True)

    def test_derived_analysis_cannot_change_time_voltage_or_geometry(self):
        for name in ('time', 'out', 'coverage'):
            with self.subTest(name=name):
                record = self.derived_record()
                derived = table.read_artifact(record['analysis_observation'])
                if name == 'coverage': derived['metadata'][name] = False
                else: derived['rows'][0][name] += .125
                new_ref = self.artifact('changed-derived.json', derived)
                packet = table.read_artifact(record['derivation']);packet['derived_observation'] = new_ref
                record.update(analysis_observation=new_ref, derivation=self.artifact('changed-packet.json', packet))
                assessment = table.read_artifact(record['assessment']);assessment['input_observation_sha256'] = new_ref['sha256']
                record['assessment'] = self.artifact('changed-assessment.json', assessment)
                with self.assertRaisesRegex(ValueError, 'changed actual'):
                    table.render([record], allow_pending=True)

    def test_derived_analysis_retains_required_roles_and_property_failure(self):
        record = self.derived_record()
        packet = table.read_artifact(record['derivation'])
        evidence = table.read_artifact(packet['evidence'])
        evidence['roles']['time']['status'] = 'unknown'
        packet['evidence'] = self.artifact('unestablished-evidence.json', evidence)
        derived = table.read_artifact(record['analysis_observation'])
        derived['qualification']['qualification_evidence']['time'].update(
            artifact_path=packet['evidence']['path'], sha256=packet['evidence']['sha256'])
        packet['derived_observation'] = self.artifact('unestablished-observation.json', derived)
        record.update(analysis_observation=packet['derived_observation'],
                      derivation=self.artifact('unestablished-packet.json', packet))
        assessment = table.read_artifact(record['assessment'])
        assessment['input_observation_sha256'] = packet['derived_observation']['sha256']
        record['assessment'] = self.artifact('unestablished-assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'established evidence role'):
            table.render([record], allow_pending=True)
        record = self.derived_record()
        assessment = table.read_artifact(record['assessment'])
        assessment['properties'][0]['status'] = 'I'
        record['assessment'] = self.artifact('missing-role-assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'Assessment/property status mismatch'):
            table.render([record], allow_pending=True)
        assessment['status'] = 'I';record['assessment'] = self.artifact('honest-I-assessment.json', assessment)
        self.assertIn('0/0/0/0/1/11', table.render([record], allow_pending=True))

    def test_derived_analysis_requires_original_assessment_and_exact_execution(self):
        for name in ('prior_analyses', 'analysis_method', 'execution'):
            with self.subTest(name=name):
                record = self.derived_record()
                if name == 'execution':
                    packet = table.read_artifact(record['derivation'])
                    packet['execution'] = self.record()['execution']
                    record['derivation'] = self.artifact('other-execution-packet.json', packet)
                else: record.pop(name)
                with self.assertRaises(ValueError): table.render([record], allow_pending=True)

    def test_pending_placeholder_cannot_claim_derived_analysis(self):
        record = {'condition_id': 'VR-01', 'backend': 'evas', 'status': 'T',
                  'analysis_method': 'not an actual completed analysis'}
        with self.assertRaisesRegex(ValueError, 'completed waveform'):
            table.render([record], allow_pending=True)

    def checker_reanalysis_record(self, status='I', backend='evas', derived=False):
        original = self.derived_record() if derived else self.record(status, backend=backend)
        if not derived:
            self.report([original], allow_pending=True)
        original_ref = self.artifact('original-record.json', original)
        record = copy.deepcopy(original)
        assessment = table.read_artifact(original['assessment'])
        assessment['checker_identity'] = self.checker(files=table.CHECKER_ANALYSIS_METHODS['native_si_time_order_v1'])
        record['assessment'] = self.artifact('new-checker-assessment.json', assessment)
        paths = {'criteria.py': table.CARDS_PATH.parent / 'criteria.py',
                 'oracle.py': table.CARDS_PATH.parent / 'oracle.py', 'core-v1.json': table.CARDS_PATH}
        packet = {'schema_version': 1, 'method': 'native_si_time_order_v1', 'original_record': original_ref,
                  'assessment': record['assessment'], 'checker': {'identity': assessment['checker_identity'],
                  'files': {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                            for name, path in paths.items()}},
                  'calibration': self.artifact('calibration.json', {'claim': 'synthetic control only'}),
                  'review': self.artifact('review.json', {'claim': 'synthetic control only'})}
        record['checker_reanalysis'] = self.artifact('checker-reanalysis.json', packet)
        return record

    def test_checker_reanalysis_preserves_original_verdict_for_all_backends_and_X(self):
        for backend in table.BACKENDS:
            for status in ('I', 'X'):
                with self.subTest(backend=backend, status=status):
                    record = self.checker_reanalysis_record(status, backend)
                    report = table.render([record], allow_pending=True)
                    self.assertEqual(table.validate(record)[0], status)
                    self.assertIn('Reviewed checker reanalyses', report)
                    packet = table.read_artifact(record['checker_reanalysis'])
                    original = table.read_artifact(packet['original_record'])
                    self.assertEqual(table.read_artifact(original['assessment'])['status'], status)

    def test_checker_reanalysis_composes_with_unchanged_observation_derivation(self):
        record = self.checker_reanalysis_record(derived=True)
        self.assertEqual(table.validate(record)[0], 'P')
        self.assertIn('Derived analyses of unchanged executions', table.render([record], allow_pending=True))

    def test_checker_reanalysis_rejects_unadmitted_method_and_snapshot_drift(self):
        for name in ('method', 'criteria.py', 'oracle.py', 'core-v1.json', 'calibration', 'review', 'original_record', 'assessment'):
            with self.subTest(name=name):
                record = self.checker_reanalysis_record()
                packet = table.read_artifact(record['checker_reanalysis'])
                if name == 'method': packet[name] = 'arbitrary_latest_checker'
                elif name in packet['checker']['files']: packet['checker']['files'][name]['sha256'] = '0' * 64
                else: packet[name]['sha256'] = '0' * 64
                record['checker_reanalysis'] = self.artifact('changed-checker-packet.json', packet)
                with self.assertRaises(ValueError): table.render([record], allow_pending=True)

    def test_checker_reanalysis_rejects_changes_to_execution_or_observation_fields(self):
        for name in ('execution', 'identity', 'prior_attempts', 'condition_id', 'backend', 'undeclared_null_field'):
            with self.subTest(name=name):
                record = self.checker_reanalysis_record()
                if name in ('condition_id', 'backend'): record[name] = 'unrelated'
                elif name == 'prior_attempts': record[name] = []
                elif name == 'undeclared_null_field': record[name] = None
                else: record[name] = {**record[name], 'extra': 'changed'}
                with self.assertRaises(ValueError): table.validate(record)

    def test_checker_reanalysis_requires_actual_original_record_validation(self):
        record = self.checker_reanalysis_record()
        packet = table.read_artifact(record['checker_reanalysis'])
        original = table.read_artifact(packet['original_record'])
        old = table.read_artifact(original['assessment'])
        old['checker_identity']['files']['criteria.py'] = '0' * 64
        original['assessment'] = self.artifact('invalid-original-assessment.json', old)
        packet['original_record'] = self.artifact('invalid-original-record.json', original)
        record['checker_reanalysis'] = self.artifact('invalid-original-packet.json', packet)
        with self.assertRaisesRegex(ValueError, 'Checker dependency digest mismatch'):
            table.validate(record)

    def test_derived_analysis_rejects_rehashed_evidence_identity_changes(self):
        for name in ('normalized', 'raw', 'source', 'final_record', 'lane_manifest', 'tool', 'adapter'):
            with self.subTest(name=name):
                record = self.derived_record()
                packet = table.read_artifact(record['derivation'])
                evidence = table.read_artifact(packet['evidence'])
                if name == 'adapter': target = evidence['analysis_adapter']
                elif name in evidence['identities']: target = evidence['identities'][name]
                else: target = evidence['execution_identity']['artifacts'][name]
                target['sha256'] = '0' * 64
                packet['evidence'] = self.artifact('rehashed-drift-evidence.json', evidence)
                record['derivation'] = self.artifact('rehashed-drift-packet.json', packet)
                with self.assertRaisesRegex(ValueError, 'identity mismatch|execution mismatch'):
                    table.render([record], allow_pending=True)

    def test_derived_analysis_retained_adapter_does_not_require_latest_checkout(self):
        record = self.derived_record()
        packet = table.read_artifact(record['derivation'])
        adapter = Path(packet['adapter']['path'])
        adapter.write_bytes(adapter.read_bytes() + b'\n# retained historical tool snapshot\n')
        packet['adapter']['sha256'] = hashlib.sha256(adapter.read_bytes()).hexdigest()
        evidence = table.read_artifact(packet['evidence'])
        evidence['analysis_adapter'] = packet['adapter']
        packet['evidence'] = self.artifact('retained-adapter-evidence.json', evidence)
        derived = table.read_artifact(record['analysis_observation'])
        derived['qualification']['qualification_evidence']['time'].update(
            artifact_path=packet['evidence']['path'], sha256=packet['evidence']['sha256'])
        packet['derived_observation'] = self.artifact('retained-adapter-observation.json', derived)
        record.update(analysis_observation=packet['derived_observation'],
                      derivation=self.artifact('retained-adapter-packet.json', packet))
        assessment = table.read_artifact(record['assessment'])
        assessment['input_observation_sha256'] = packet['derived_observation']['sha256']
        record['assessment'] = self.artifact('retained-adapter-assessment.json', assessment)
        self.assertEqual(table.validate(record)[0], 'P')

    def test_frozen_runner_checker_and_dependency_digest_are_bound(self):
        for change in ('runner', 'criteria.py', 'oracle.py', 'digest'):
            with self.subTest(change=change):
                record = self.record()
                if change == 'runner':
                    lane = json.loads(Path(record['identity']['lane_started']['path']).read_text())
                    lane['runner_sha256'] = 'b' * 64
                    record['identity']['lane_started'] = self.artifact('mixed-runner-STARTED.json', lane)
                else:
                    assessment = json.loads(Path(record['assessment']['path']).read_text())
                    if change == 'digest':
                        assessment['checker_identity']['sha256'] = 'b' * 64
                    else:
                        assessment['checker_identity'] = self.checker(files={**self.checker_files, change: 'b' * 64})
                    record['assessment'] = self.artifact('mixed-checker.json', assessment)
                with self.assertRaises(ValueError):
                    self.report([record], allow_pending=True)

    def test_frozen_identity_json_bytes_are_verified(self):
        for name in ('ADAPTER_IDENTITY.json', 'CHECKER_IDENTITY.json'):
            with self.subTest(name=name):
                record = self.record()
                path = self.root / name
                original = path.read_bytes()
                path.write_text('{}')
                with self.assertRaises(ValueError):
                    self.report([record], allow_pending=True)
                path.write_bytes(original)

    def test_historical_valid_frozen_checker_is_accepted(self):
        # These fixture hashes and runtime intentionally differ from this checkout.
        self.assertIn('1/0/0/0/0/11', self.report([self.record()], allow_pending=True))

    def test_malformed_record_public_url_and_observation_are_ValueError(self):
        for bad in ({}, [None]):
            with self.assertRaises(ValueError):
                table.render(bad, allow_pending=True)
        record = self.record()
        record['identity'].update(availability='public', public_url=[])
        with self.assertRaises(ValueError):
            self.report([record], allow_pending=True)
        record = self.record()
        execution = json.loads(Path(record['execution']['path']).read_text())
        execution['observation'] = 'not an object'
        record['execution'] = self.artifact('bad-observation-record.json', execution)
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment['execution_sha256'] = record['execution']['sha256']
        record['assessment'] = self.artifact('assessment.json', assessment)
        with self.assertRaises(ValueError):
            self.report([record], allow_pending=True)

    def test_frozen_waveform_deleted_or_changed_is_rejected(self):
        for change in ('delete', 'bytes'):
            with self.subTest(change=change):
                record = self.record()
                self.report([record], allow_pending=True)
                waveform = Path(record['identity']['condition_started']['path']).parent / 'waveform.csv'
                if change == 'delete':
                    waveform.unlink()
                else:
                    waveform.write_text('changed raw output')
                with self.assertRaises((ValueError, FileNotFoundError)):
                    table.render([record], allow_pending=True)

    def test_waveform_digest_and_condition_path_are_checked(self):
        for change in ('digest', 'escape', 'absolute', 'manifest'):
            with self.subTest(change=change):
                record = self.record()
                execution = json.loads(Path(record['execution']['path']).read_text())
                work = Path(record['identity']['condition_started']['path']).parent
                if change == 'digest':
                    execution['waveform_sha256'] = 'b' * 64
                elif change == 'escape':
                    execution['waveform'] = '../waveform.csv'
                    (work.parent / 'waveform.csv').write_bytes((work / 'waveform.csv').read_bytes())
                elif change == 'absolute':
                    execution['waveform'] = str(work / 'waveform.csv')
                record['execution'] = self.artifact('final-record.json', execution)
                assessment = json.loads(Path(record['assessment']['path']).read_text())
                assessment['execution_sha256'] = record['execution']['sha256']
                record['assessment'] = self.artifact('assessment.json', assessment)
                if change == 'manifest':
                    self.report([record], allow_pending=True)
                    ref = record['identity']['execution_manifest']
                    manifest = json.loads(Path(ref['path']).read_text())
                    del manifest[str((work / 'waveform.csv').relative_to(self.root))]
                    record['identity']['execution_manifest'] = self.artifact('bad-manifest.json', manifest)
                    call = lambda: table.render([record], allow_pending=True)
                else:
                    call = lambda: self.report([record], allow_pending=True)
                with self.assertRaises(ValueError):
                    call()

    def test_spectre_nested_waveform_is_accepted(self):
        record = self.record(backend='spectre')
        work = Path(record['identity']['condition_started']['path']).parent
        waveform = work / 'psf/tran.tran.tran'
        waveform.parent.mkdir()
        waveform.write_bytes((work / 'waveform.csv').read_bytes())
        execution = json.loads(Path(record['execution']['path']).read_text())
        execution['waveform'] = 'psf/tran.tran.tran'
        record['execution'] = self.artifact('final-record.json', execution)
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment['execution_sha256'] = record['execution']['sha256']
        record['assessment'] = self.artifact('assessment.json', assessment)
        self.assertIn('0/0/0/0/0/12 | 1/0/0/0/0/11', self.report([record], allow_pending=True))

    def test_partial_batch_keeps_all_denominators_and_card_design_separate(self):
        all_pending = self.report([], allow_pending=True)
        self.assertIn('| Total | 12 | ' + ' | '.join(['0/0/0/0/0/12'] * 4) + ' |', all_pending)
        explicit = [{'condition_id': c['id'], 'backend': b, 'status': 'T'} for c in table.BATCH['cards'] for b in table.BACKENDS]
        self.assertEqual(all_pending, self.report(explicit))
        records = [self.record(), self.record('F', 'EX-01', 'spectre')]
        report = self.report(records, allow_pending=True)
        self.assertIn('| Total | 12 | 1/0/0/0/0/11 | 0/1/0/0/0/11 |', report)
        self.assertIn('| structure | 1 |', report)
        self.assertIn('| combination | 3 |', report)
        self.assertIn('N=12', report)
        self.assertIn('fixture-head', report)
        self.assertIn('local-only', report)
        self.assertIn(table.BATCH['design_status'], report)

    def test_missing_duplicate_and_unknown_slots_are_rejected(self):
        record = self.record()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            self.report([record])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.report([record, record], allow_pending=True)
        for key, value in [('condition_id', 'old31'), ('backend', 'invented')]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Unknown'):
                self.report([{**record, key: value}], allow_pending=True)

    def test_fake_pass_and_changed_artifacts_are_rejected(self):
        record = self.record()
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.report([{**record, 'identity': {}}], allow_pending=True)
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment['properties'][0]['status'] = 'F'
        bad = {**record, 'assessment': self.artifact('bad-assessment.json', assessment)}
        with self.assertRaisesRegex(ValueError, 'property'):
            self.report([bad], allow_pending=True)
        Path(record['assessment']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.report([record], allow_pending=True)

    def test_condition_observation_and_card_bindings_are_checked(self):
        record = self.record()
        execution = json.loads(Path(record['execution']['path']).read_text())
        execution['observation']['sha256'] = 'b' * 64
        record['execution'] = self.artifact('RESULT.json', execution)
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment['execution_sha256'] = record['execution']['sha256']
        record['assessment'] = self.artifact('assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'observation'):
            self.report([record], allow_pending=True)
        record = self.record()
        started = json.loads(Path(record['identity']['condition_started']['path']).read_text())
        started['tool_identity_sha256'] = 'f' * 64
        record['identity']['condition_started'] = self.artifact('wrong-started.json', started)
        with self.assertRaisesRegex(ValueError, 'execution identity'):
            self.report([record], allow_pending=True)
        record = self.record()
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment['checker_identity']['files']['core-v1.json'] = 'c' * 64
        record['assessment'] = self.artifact('assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'card'):
            self.report([record], allow_pending=True)

    def test_previous_assessment_cannot_grade_new_observation_or_execution(self):
        old = self.record()
        new = self.record()
        new_observation = self.artifact('new-observation.json', {'condition_id': 'VR-01', 'rows': [{'out': 2}]})
        new['identity']['observation'] = new_observation
        execution = json.loads(Path(new['execution']['path']).read_text())
        execution['observation'] = new_observation
        new['execution'] = self.artifact('new-RESULT.json', execution)
        new['assessment'] = old['assessment']
        with self.assertRaisesRegex(ValueError, 'Assessment execution hash'):
            self.report([new], allow_pending=True)
        # Updating just execution identity cannot launder the old observation input.
        assessment = json.loads(Path(old['assessment']['path']).read_text())
        assessment['execution_sha256'] = new['execution']['sha256']
        new['assessment'] = self.artifact('rebound-assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'Assessment input observation hash'):
            self.report([new], allow_pending=True)

    def test_execution_status_cannot_be_relabelled_U_X_or_T(self):
        for status in 'UXT':
            with self.subTest(status=status):
                record = self.record(status)
                execution = json.loads(Path(record['execution']['path']).read_text())
                execution['status'] = 'waveform_available'
                record['execution'] = self.artifact('relabelled-RESULT.json', execution)
                assessment = json.loads(Path(record['assessment']['path']).read_text())
                assessment['execution_sha256'] = record['execution']['sha256']
                record['assessment'] = self.artifact('relabelled-assessment.json', assessment)
                with self.assertRaisesRegex(ValueError, 'execution status'):
                    self.report([record], allow_pending=True)
        record = self.record('U')
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        del assessment['unsupported_evidence']
        record['assessment'] = self.artifact('unconfirmed-assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'unsupported evidence'):
            self.report([record], allow_pending=True)
        record = self.record('U')
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        evidence = json.loads(Path(assessment['unsupported_evidence']['path']).read_text())
        evidence['diagnostic'] = self.artifact('unrelated-diagnostic.json', {'stderr': 'unrelated compiler rejection'})
        assessment['unsupported_evidence'] = self.artifact('wrong-unsupported.json', evidence)
        record['assessment'] = self.artifact('wrong-unsupported-assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'actual failed compile log'):
            self.report([record], allow_pending=True)
        record = self.record()
        record.pop('assessment')
        record['status'] = 'T'
        with self.assertRaisesRegex(ValueError, 'execution status'):
            self.report([record], allow_pending=True)

    def test_same_backend_two_plus_ten_requires_one_execution_identity(self):
        records = [self.record(condition=card['id']) for card in table.BATCH['cards']]
        self.assertIn('| Total | 12 | 12/0/0/0/0/0 |', self.report(records, allow_pending=True))
        for changed in ('source_revision', 'tool', 'checker', 'input_manifest'):
            with self.subTest(changed=changed):
                second = self.record(condition='EX-01')
                if changed == 'source_revision':
                    second['identity']['source_revision'] = 'different-source-revision'
                elif changed == 'tool':
                    tool = self.artifact('new-tool.json', {'reported': {'version': 'different-tool-v2'}})
                    second['identity']['tool'] = tool
                    started = json.loads(Path(second['identity']['condition_started']['path']).read_text())
                    started['tool_identity_sha256'] = tool['sha256']
                    path = Path(second['identity']['condition_started']['path'])
                    path.write_text(json.dumps(started))
                    second['identity']['condition_started']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                elif changed == 'checker':
                    assessment = json.loads(Path(second['assessment']['path']).read_text())
                    assessment['checker_identity'] = self.checker(runtime={'python': 'different-runtime'})
                    second['assessment'] = self.artifact('different-checker.json', assessment)
                else:
                    second['identity']['input_manifest'] = self.artifact('different-input-manifest.json', {**self.manifest, 'new-file': {'sha256': 'c' * 64}})
                    lane = json.loads(Path(second['identity']['lane_started']['path']).read_text())
                    lane['input_manifest_sha256'] = second['identity']['input_manifest']['sha256']
                    second['identity']['lane_started'] = self.artifact('different-lane.json', lane)
                with self.assertRaisesRegex(ValueError, 'Mixed backend execution identity'):
                    self.report([records[0], second, *records[2:]], allow_pending=True)

    def test_started_source_and_deck_match_executed_source_and_frozen_inputs(self):
        for changed in ('source_sha256', 'deck_sha256'):
            with self.subTest(changed=changed):
                record = self.record()
                path = Path(record['identity']['condition_started']['path'])
                started = json.loads(path.read_text())
                started[changed] = '9' * 64
                path.write_text(json.dumps(started))
                record['identity']['condition_started']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'source/deck'):
                    self.report([record], allow_pending=True)
        record = self.record()
        execution = json.loads(Path(record['execution']['path']).read_text())
        execution['source_sha256'] = '8' * 64
        record['execution'] = self.artifact('wrong-source-RESULT.json', execution)
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment['execution_sha256'] = record['execution']['sha256']
        record['assessment'] = self.artifact('wrong-source-assessment.json', assessment)
        with self.assertRaisesRegex(ValueError, 'source/deck'):
            self.report([record], allow_pending=True)

    def test_dynamic_tool_receipts_allow_disjoint_two_plus_ten(self):
        records = [self.record(condition=c['id']) for c in table.BATCH['cards']]
        for i, record in enumerate(records):
            tool = json.loads(Path(record['identity']['tool']['path']).read_text())
            tool['probe'] = {'completed_utc': 'synthetic batch ' + str(i >= 2), 'argv': ['different-output-path-' + str(i)]}
            record['identity']['tool'] = self.artifact('dynamic-tool.json', tool)
            path = Path(record['identity']['condition_started']['path'])
            started = json.loads(path.read_text())
            started['tool_identity_sha256'] = record['identity']['tool']['sha256']
            path.write_text(json.dumps(started))
            record['identity']['condition_started']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertNotEqual(records[0]['identity']['tool']['sha256'], records[2]['identity']['tool']['sha256'])
        self.assertIn('| Total | 12 | 12/0/0/0/0/0 |', self.report(records, allow_pending=True))
        for change in ('kernel_sha256', 'reported', 'images'):
            with self.subTest(change=change):
                backend = 'gnucap_modelgen' if change == 'images' else 'evas'
                first, second = self.record(backend=backend), self.record(condition='EX-01', backend=backend)
                if change == 'images':
                    first_tool = json.loads(Path(first['identity']['tool']['path']).read_text())
                    first_tool['images'] = {'runtime': {'config_id': 'pinned-original-image'}}
                    first['identity']['tool'] = self.artifact('original-image-tool.json', first_tool)
                    path = Path(first['identity']['condition_started']['path'])
                    started = json.loads(path.read_text())
                    started['tool_identity_sha256'] = first['identity']['tool']['sha256']
                    path.write_text(json.dumps(started))
                    first['identity']['condition_started']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                tool = json.loads(Path(second['identity']['tool']['path']).read_text())
                tool[change] = {'version': 'changed'} if change == 'reported' else {'runtime': {'config_id': 'changed-image'}} if change == 'images' else 'b' * 64
                second['identity']['tool'] = self.artifact('changed-scientific-tool.json', tool)
                path = Path(second['identity']['condition_started']['path'])
                started = json.loads(path.read_text())
                started['tool_identity_sha256'] = second['identity']['tool']['sha256']
                path.write_text(json.dumps(started))
                second['identity']['condition_started']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'Mixed backend execution identity'):
                    self.report([first, second], allow_pending=True)

    def test_other_attempt_started_or_tool_not_in_lane_manifest_is_rejected(self):
        selected, other = self.record(), self.record()
        self.report([selected], allow_pending=True)
        selected['identity']['condition_started'] = other['identity']['condition_started']
        selected['identity']['tool'] = other['identity']['tool']
        with self.assertRaisesRegex(ValueError, 'FILE_MANIFEST'):
            table.render([selected], allow_pending=True)

    def test_selected_slot_keeps_declared_prior_failure_without_increasing_N(self):
        selected, prior = self.record(), self.record('X')
        selected['prior_attempts'] = [prior['execution']]
        selected['selection_reason'] = 'Explicit authorized rerun; prior timeout retained'
        report = self.report([selected], allow_pending=True)
        self.assertIn('| Total | 12 | 1/0/0/0/0/11 |', report)
        self.assertIn('prior timeout retained', report)
        self.assertIn(Path(prior['execution']['path']).name, report)
        selected['prior_attempts'] = [self.record('X', 'EX-01')['execution']]
        with self.assertRaisesRegex(ValueError, 'prior attempt'):
            self.report([selected], allow_pending=True)
        selected['prior_attempts'] = [prior['execution']]
        del selected['selection_reason']
        with self.assertRaisesRegex(ValueError, 'selection_reason'):
            self.report([selected], allow_pending=True)

    def test_terminal_budget_failure_rejects_earlier_waveform_snapshot(self):
        record = self.record()
        earlier = json.loads(Path(record['execution']['path']).read_text())
        final = {**earlier, 'status': 'condition_directory_limit_exceeded',
                 'failure_stage': 'terminal_directory_budget',
                 'directory_budget': {'actual_bytes': 256 * 1024**2 + 1,
                     'limit_bytes': 256 * 1024**2, 'status': 'condition_directory_limit_exceeded',
                     'measurement': 'terminal directory files; not an active disk quota', 'runtime_hard_quota': False}}
        with self.assertRaisesRegex(ValueError, 'Final EXECUTION row'):
            self.report([record], allow_pending=True, final_rows=[final])
        record['execution'] = self.artifact('final-record-VR-01.json', final)
        assessment = json.loads(Path(record['assessment']['path']).read_text())
        assessment.update(status='X', execution_state='X', execution_sha256=record['execution']['sha256'])
        record['assessment'] = self.artifact('final-assessment.json', assessment)
        report = self.report([record], allow_pending=True, final_rows=[final])
        self.assertIn('| Total | 12 | 0/0/0/1/0/11 |', report)

    def test_final_lane_requires_unique_identical_row_and_unchanged_artifact(self):
        record = self.record()
        execution = json.loads(Path(record['execution']['path']).read_text())
        for final_rows in ([], [execution, execution], [{**execution, 'directory_budget': {'status': 'within_limit'}}]):
            with self.subTest(final_rows=final_rows), self.assertRaisesRegex(ValueError, 'Final EXECUTION row'):
                self.report([record], allow_pending=True, final_rows=final_rows)
        self.report([record], allow_pending=True)
        (self.root / 'EXECUTION.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'hash'):
            table.render([record], allow_pending=True)
        # A preflight not_run result has no condition STARTED or TOOL identity.
        not_run = {'condition': 'VR-01', 'backend': 'evas', 'status': 'not_run', 'reason': 'preflight failed'}
        execution = self.artifact('final-record-VR-01.json', not_run)
        (self.root / 'EXECUTION.json').write_text(json.dumps([not_run]))
        manifest = self.artifact('FILE_MANIFEST.json', {
            'EXECUTION.json': {'sha256': hashlib.sha256((self.root / 'EXECUTION.json').read_bytes()).hexdigest()},
            Path(execution['path']).name: {'sha256': execution['sha256']}})
        pending = {'condition_id': 'VR-01', 'backend': 'evas', 'status': 'T', 'execution': execution,
                   'identity': {'execution_manifest': manifest}}
        self.assertIn('| Total | 12 | 0/0/0/0/0/12 |', table.render([pending], allow_pending=True))

    def test_all_six_statuses_are_retained(self):
        records = []
        for card, status in zip(table.BATCH['cards'], table.STATUSES):
            if status == 'T':
                records.append({'condition_id': card['id'], 'backend': 'evas', 'status': 'T'})
            else:
                record = self.record(status, card['id'])
                records.append(record)
        report = self.report(records, allow_pending=True)
        self.assertIn('| Total | 12 | 1/1/1/1/1/7 |', report)
        self.assertIn('P/F/U/X/I/T', report)

    def test_gnucap_deck_parse_error_requires_immutable_final_record_and_counts_X(self):
        record=self.record(condition='EV-SH-01',backend='gnucap_modelgen')
        earlier_ref=record['execution'];earlier_bytes=Path(earlier_ref['path']).read_bytes()
        earlier=json.loads(earlier_bytes)
        final={k:v for k,v in earlier.items() if k not in ('waveform','waveform_sha256','observation')}
        work=Path(record['identity']['condition_started']['path']).parent
        log=work/'simulate.log'; log.write_text('fixture context\n'*41+'    ^ ? need )\n')
        log_sha=hashlib.sha256(log.read_bytes()).hexdigest()
        final['stages']=[{'stage':'simulate','returncode':0,'log':'simulate.log','log_sha256':log_sha}]
        final['diagnostic_log_sha256']=log_sha
        final.update(status='deck_parse_error',failure_stage='deck_parse',abort_batch=False,
                     diagnostics=[{'line_number':42,'text':'    ^ ? need )'}],
                     rejected_waveform={'path':earlier['waveform'],'sha256':earlier['waveform_sha256']})
        with self.assertRaisesRegex(ValueError,'Final EXECUTION row'):
            self.report([record],allow_pending=True,final_rows=[final])
        record['execution']=self.artifact('final-record-EV-SH-01.json',final)
        assessment=json.loads(Path(record['assessment']['path']).read_text())
        assessment.update(status='X',execution_state='X',execution_sha256=record['execution']['sha256'])
        record['assessment']=self.artifact('final-deck-parse-assessment.json',assessment)
        report=self.report([record],allow_pending=True,final_rows=[final])
        self.assertIn('| Total | 12 |',report)
        self.assertIn('0/0/0/1/0/11',report)
        self.assertEqual(Path(earlier_ref['path']).read_bytes(),earlier_bytes)
        self.assertEqual(json.loads(earlier_bytes)['status'],'waveform_available')
        Path(record['execution']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'hash'):
            table.render([record],allow_pending=True)

    def deck_parse_record(self, change=None):
        record=self.record(condition='EV-SH-01',backend='gnucap_modelgen')
        previous=json.loads(Path(record['execution']['path']).read_text())
        work=Path(record['identity']['condition_started']['path']).parent
        log=work/'simulate.log'; log.write_text('fixture context\n    ^ ? need )\n')
        log_sha=hashlib.sha256(log.read_bytes()).hexdigest()
        final={k:v for k,v in previous.items() if k not in ('waveform','waveform_sha256','observation')}
        final.update(status='deck_parse_error',failure_stage='deck_parse',abort_batch=False,
                     diagnostic_log_sha256=log_sha,
                     diagnostics=[{'line_number':2,'text':'    ^ ? need )'}],
                     stages=[{'stage':'simulate','returncode':0,'log':'simulate.log','log_sha256':log_sha}],
                     rejected_waveform={'path':previous['waveform'],'sha256':previous['waveform_sha256']})
        if change: change(final,work)
        record['execution']=self.artifact('bound-deck-parse-final.json',final)
        assessment=json.loads(Path(record['assessment']['path']).read_text())
        assessment.update(status='X',execution_state='X',execution_sha256=record['execution']['sha256'])
        record['assessment']=self.artifact('bound-deck-parse-assessment.json',assessment)
        return record

    def test_deck_parse_X_rejects_unbound_diagnostic_and_raw_evidence(self):
        changes={
            'wrong diagnostic sha': lambda f,w:f.update(diagnostic_log_sha256='0'*64),
            'wrong stage sha': lambda f,w:f['stages'][0].update(log_sha256='0'*64),
            'no simulate stage': lambda f,w:f.update(stages=[]),
            'wrong stage log': lambda f,w:f['stages'][0].update(log='other.log'),
            'wrong line number': lambda f,w:f['diagnostics'][0].update(line_number=1),
            'wrong line text': lambda f,w:f['diagnostics'][0].update(text='    ^ ? made up'),
            'no diagnostics': lambda f,w:f.update(diagnostics=[]),
            'missing rejected raw': lambda f,w:(w/f['rejected_waveform']['path']).unlink(),
            'wrong rejected raw sha': lambda f,w:f['rejected_waveform'].update(sha256='0'*64),
            'outside rejected raw': lambda f,w:f['rejected_waveform'].update(path='../waveform.csv'),
        }
        for name,change in changes.items():
            with self.subTest(name=name):
                record=self.deck_parse_record(change)
                with self.assertRaises((ValueError,FileNotFoundError)):
                    self.report([record],allow_pending=True)

    def test_deck_parse_X_requires_manifest_bound_diagnostic_log(self):
        record=self.deck_parse_record()
        self.report([record],allow_pending=True)
        ref=record['identity']['execution_manifest'];manifest=json.loads(Path(ref['path']).read_text())
        relative=next(k for k in manifest if k.endswith('/simulate.log'))
        manifest[relative]['sha256']='0'*64
        record['identity']['execution_manifest']=self.artifact('bad-log-manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'FILE_MANIFEST'):
            table.render([record],allow_pending=True)

    def test_deck_parse_X_requires_manifest_bound_rejected_raw(self):
        record=self.deck_parse_record()
        self.report([record],allow_pending=True)
        ref=record['identity']['execution_manifest'];manifest=json.loads(Path(ref['path']).read_text())
        relative=next(k for k in manifest if k.endswith('/waveform.csv'))
        manifest[relative]['sha256']='0'*64
        record['identity']['execution_manifest']=self.artifact('bad-rejected-raw-manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'FILE_MANIFEST'):
            table.render([record],allow_pending=True)

    def test_bound_deck_parse_X_needs_no_rejected_waveform_when_none_created(self):
        def no_raw(final,work):
            (work/final['rejected_waveform']['path']).unlink()
            final['rejected_waveform']=None
        record=self.deck_parse_record(no_raw)
        report=self.report([record],allow_pending=True)
        self.assertIn('0/0/0/1/0/11',report)


if __name__ == '__main__':
    unittest.main()
