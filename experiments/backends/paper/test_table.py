"""Fault controls for fixed-denominator reporting; no backend invocation."""
import hashlib
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
            for name in ('dut.va', 'tb.deck', 'waveform.csv', 'psf/tran.tran.tran'):
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


if __name__ == '__main__':
    unittest.main()
