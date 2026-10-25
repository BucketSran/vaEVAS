"""The capability registry matches its rules and the published comparison labels."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from catalog import BACKENDS, CAMPAIGNS, CHAPTERS, NODES
import render
from registry import Registry, RegistryError, reference, load, digest

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "evas/docs/COMPARISON.md"


class CapabilityRegistry(unittest.TestCase):
    def test_nodes_are_unique_and_use_known_chapters(self):
        ids = [node["id"] for node in NODES]
        self.assertEqual(len(ids), len(set(ids)))
        for node in NODES:
            self.assertIn(node["chapter"], CHAPTERS)
            self.assertIn(node["status"], ("compared", "waiting"))
            for dep in node["depends_on"]:
                self.assertIn(dep, ids)
                self.assertNotEqual(dep, node["id"])

    def test_compared_rows_quote_the_published_table(self):
        text = PUBLISHED.read_text()
        for node in NODES:
            if node["status"] != "compared":
                self.assertNotIn("results", node)
                continue
            self.assertEqual(set(node["results"]), set(BACKENDS))
            self.assertIn(node["label"], text)
            for value in node["results"].values():
                self.assertIn(value, text)

    def test_waiting_rows_are_not_given_a_result(self):
        for node in NODES:
            if node["status"] == "waiting":
                self.assertEqual(node["review"], "pending")
                self.assertIn("gap", node)
                self.assertNotIn("results", node)

    def test_views_follow_the_registry(self):
        data = render.registry()
        comparison = render.comparison_markdown(data)
        paper = render.paper_markdown(data)
        for node in NODES:
            self.assertIn(node["title"], comparison)
            if node["status"] == "waiting":
                self.assertNotIn(node["title"], paper)
            else:
                self.assertIn(node["title"], paper)
        self.assertIn("等待跑", comparison)
        campaign_ids = [item["id"] for item in CAMPAIGNS]
        self.assertIn("four-backend-q", campaign_ids)
        self.assertIn("dvs-31", campaign_ids)

    def test_generated_files_match_the_catalog(self):
        files = render.outputs(render.registry())
        for path, text in files.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(), text)




class MaintainedSourceIndex(unittest.TestCase):
    def test_selected_atoms_and_unselected_neighbors_have_separate_effective_sources(self):
        reg = load()
        self.assertEqual(reg.data['language_profile']['selected_changes'], ['7780', '7920'])
        for name in ('ln1p', '$ln1p', 'expm1', '$expm1', '$rtoi.analog-context', '$itor.analog-context'):
            self.assertEqual(reg.effective_standard(name), '2023', name)
        for name in ('pow', 'pow.negative-integer-exponent', '$min', '$max', '$abs', 'net_resolution', '$signed.analog-context', '$unsigned.analog-context', 'log1p'):
            self.assertEqual(reg.effective_standard(name), '2.4', name)

    def test_change_index_retains_blank_and_unselected_rows(self):
        reg = load()
        rows = [x for x in reg.data['inventory'] if 'mantis' in x]
        self.assertEqual(len(rows), 34)
        self.assertEqual({x['mantis'] for x in rows if x['selection'] == 'selected'}, {7780, 7920})
        self.assertEqual(next(x for x in rows if x['mantis'] == 7893)['description_status'], 'blank-in-PDF-unresolved')

    def test_deleting_an_actual_table_row_mapping_exposes_the_missing_source(self):
        data = copy.deepcopy(load().data)
        row = next(x for x in data['inventory'] if x['kind'] == 'logical_table_row')
        data['dispositions'] = [x for x in data['dispositions'] if x['source_id'] != row['id']]
        with self.assertRaisesRegex(RegistryError, 'unmapped inventory'):
            Registry(data)

    def test_registered_examples_do_not_acquire_support_from_old_success(self):
        reg = load()
        self.assertFalse(reg.qualified('qualification:sef-registration-example'))
        for name in ('requirement:expm1', 'requirement:ln1p', 'requirement:$rtoi', 'requirement:$itor'):
            self.assertFalse(reg.qualified(name))


def fixture(source=None, revision='1'):
    """Synthetic evidence chain; the embedded reports are test controls only."""
    objects = []
    def add(name, kind, **fields):
        stable = {'fixture-inputs', 'fixture-requirement', 'execution-raw', 'fixture-execution'}
        obj = dict(id=name, version='1' if name in stable else revision, kind=kind, status='active', **fields)
        objects.append(obj)
        return obj
    def receipt(name, content):
        return add(name, 'source', origin='embedded:fixture-only',
                   embedded=content, sha256=digest(content))
    spec = source or dict(id='spec', version='1', kind='source', status='active',
                          origin='embedded:fixture-code', embedded={'code': 'fixture'},
                          sha256=digest({'code': 'fixture'}))
    objects.append(spec)
    definition = add('checker-definition', 'checker-definition', scope='fixture-only',
                     budget='fixture exact-control contract', review='approved',
                     dependencies=[reference(spec)])
    controls = {'accept': ['correct'], 'reject': ['wrong']}
    raw = receipt('cal-raw', dict(schema_version=1, subject=reference(definition),
                                complete=True, backend='fixture@1',
                                outcomes={'correct': 'accepted', 'wrong': 'rejected'}))
    calibration_execution = add('cal-execution', 'calibration-execution',
                                subject=reference(definition), raw_report=reference(raw),
                                complete=True, outcome='passed', backend='fixture@1',
                                controls=controls,
                                outcomes={'correct': 'accepted', 'wrong': 'rejected'},
                                dependencies=[reference(definition), reference(raw)])
    approval = receipt('cal-approval', dict(schema_version=1, decision='approved',
                       reviewer='fixture-reviewer', subject=reference(definition),
                       execution=reference(calibration_execution), scope='fixture-only',
                       controls=controls))
    calibration = add('calibration', 'calibration', controls=controls, review='approved',
                      scope='fixture-only', reviewer='fixture-reviewer',
                      subject=reference(definition), execution=reference(calibration_execution),
                      approval=reference(approval), dependencies=[reference(definition),
                      reference(calibration_execution), reference(approval)])
    checker = add('checker', 'checker', scope='fixture-only', review='approved',
                  subject=reference(definition),
                  dependencies=[reference(definition), reference(calibration)])
    requirement = add('fixture-requirement', 'requirement', review='approved',
                      dependencies=[reference(spec)])
    requirements = [reference(requirement)]
    inputs = add('fixture-inputs', 'case-inputs', review='approved',
                 dependencies=[reference(spec)], model='synthetic fixture inputs')
    case = add('fixture-case', 'case', scope='fixture-only', requirements=requirements,
               inputs=reference(inputs), review='approved',
               dependencies=[reference(checker), reference(requirement), reference(inputs)])
    execution_raw = receipt('execution-raw', dict(schema_version=1, inputs=reference(inputs),
                            complete=True, outcome='passed', backend='fixture@1'))
    execution = add('fixture-execution', 'execution', outcome='passed', complete=True,
                    backend='fixture@1', inputs=reference(inputs),
                    raw_report=reference(execution_raw),
                    dependencies=[reference(inputs), reference(execution_raw)])
    analysis = add('fixture-analysis', 'analysis', outcome='accepted', case=reference(case),
                   dependencies=[reference(execution), reference(checker), reference(case)])
    claim = dict(scope='fixture-only', requirements=requirements, backend='fixture@1')
    review_source = receipt('review-approval', dict(schema_version=1, claim=claim,
                            analysis=reference(analysis), case=reference(case), decision='approved',
                            reviewer='fixture-reviewer'))
    review = add('fixture-review', 'review', decision='approved',
                 reviewer='fixture-reviewer', claim=claim, case=reference(case), evidence=reference(review_source),
                 dependencies=[reference(analysis), reference(requirement), reference(review_source), reference(case)])
    for name in ('consumer-a', 'consumer-b'):
        add(name, 'qualification', scope='fixture-only', requirements=requirements,
            backend='fixture@1', review='approved', dependencies=[reference(case),
            reference(execution), reference(analysis), reference(review), reference(requirement)])
    return {'schema_version': 1, 'objects': objects,
            'current': {x['id']: x['version'] for x in objects},
            'inventory': [{'id': 'section:1', 'kind': 'clause'}],
            'dispositions': [{'source_id': 'section:1', 'decision': 'included',
                              'reason': 'Fixture requirement'}]}


def by_id(data, name):
    return next(x for x in data['objects'] if x['id'] == name)


def rebind(data):
    # Rebind graph edges only. Received raw evidence remains immutable.
    lookup = {(x['id'], x['version']): x for x in data['objects']}
    complete = set()
    def bind(obj):
        key = (obj['id'], obj['version'])
        if key in complete:
            return
        def update(value):
            if isinstance(value, dict):
                if set(value) == {'id', 'version', 'sha256'}:
                    target = lookup[(value['id'], value['version'])]
                    bind(target)
                    return reference(target)
                return {k: update(v) for k, v in value.items()}
            if isinstance(value, list):
                return [update(v) for v in value]
            return value
        for field in ('dependencies', 'subject', 'execution', 'approval', 'raw_report',
                      'requirements', 'claim', 'evidence', 'inputs', 'case'):
            if field in obj:
                obj[field] = update(obj[field])
        complete.add(key)
    for obj in data['objects']:
        bind(obj)


class VersionedRegistryTests(unittest.TestCase):
    def test_deleting_disposition_exposes_external_inventory_gap(self):
        data = fixture()
        data['dispositions'].clear()
        with self.assertRaisesRegex(RegistryError, 'unmapped inventory'):
            Registry(data)

    def test_removing_source_and_mapping_cannot_shrink_the_external_denominator(self):
        data = fixture()
        data['inventory_identity'] = digest(data['inventory'])
        data['inventory'].clear()
        data['dispositions'].clear()
        with self.assertRaisesRegex(RegistryError, 'inventory identity changed'):
            Registry(data)

    def test_unselected_change_does_not_replace_base_expectation(self):
        data = fixture()
        data['language_profile'] = {'base': '2.4', 'selected_changes': ['7780', '7920'],
                                   'changes': {'7780': {'expm1': '2023'},
                                               '7900': {'pow': '2023'}}}
        reg = Registry(data)
        self.assertEqual(reg.effective_standard('expm1'), '2023')
        self.assertEqual(reg.effective_standard('pow'), '2.4')

    def test_missing_source_or_calibration_cannot_qualify(self):
        for name, field in (('spec', 'origin'), ('calibration', 'controls')):
            data = fixture()
            del by_id(data, name)[field]

            rebind(data)
            self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_revoked_checker_invalidates_both_consumers(self):
        data = fixture()
        self.assertTrue(Registry(data).qualified('consumer-a'))
        by_id(data, 'checker')['status'] = 'revoked'
        reg = Registry(data)
        for name in ('consumer-a', 'consumer-b'):
            self.assertFalse(reg.qualified(name))

    def test_new_checker_version_invalidates_old_qualifications_but_keeps_history(self):
        data = fixture()
        newer = copy.deepcopy(by_id(data, 'checker'))
        newer['version'] = '2'
        data['objects'].append(newer)
        data['current']['checker'] = '2'
        reg = Registry(data)
        for name in ('consumer-a', 'consumer-b'):
            self.assertFalse(reg.qualified(name))
            self.assertTrue(reg.qualified(name, historical=True))

    def test_same_version_content_drift_is_detected(self):
        data = fixture()
        by_id(data, 'checker')['budget'] = 'changed'
        self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_source_bytes_change_invalidates_consumers_without_metadata_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.txt'
            path.write_text('original')
            source = dict(id='spec', version='1', kind='source', status='active',
                          origin='fixture-file', path='source.txt',
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            data = fixture(source=source)
            self.assertTrue(Registry(data, root=directory).qualified('consumer-a'))
            path.write_text('changed')
            reg = Registry(data, root=directory)
            self.assertFalse(reg.qualified('consumer-a'))
            self.assertFalse(reg.qualified('consumer-b'))

    def test_execution_success_alone_cannot_qualify_a_case(self):
        data = fixture()
        consumer = data['objects'][-1]
        consumer['dependencies'] = [reference(by_id(data, 'fixture-execution'))]
        self.assertFalse(Registry(data).qualified('consumer-b'))

    def test_incomplete_execution_cannot_qualify(self):
        data = fixture()
        by_id(data, 'fixture-execution')['complete'] = False
        rebind(data)
        self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_approval_for_another_execution_cannot_qualify(self):
        data = fixture()
        # A standalone passing execution is not the case reviewed by this analysis.
        other = copy.deepcopy(by_id(data, 'fixture-execution'))
        other['id'] = 'unreviewed-execution'
        data['objects'].append(other)
        data['current'][other['id']] = other['version']
        consumer = by_id(data, 'consumer-b')
        consumer['dependencies'] = [reference(other) if r['id'] == 'fixture-execution' else r
                                    for r in consumer['dependencies']]
        self.assertFalse(Registry(data).qualified('consumer-b'))

    def test_duplicate_versions_are_rejected(self):
        data = fixture()
        data['objects'].append(copy.deepcopy(by_id(data, 'spec')))
        with self.assertRaisesRegex(RegistryError, 'duplicate'):
            Registry(data)

    def test_analysis_cannot_substitute_the_case_checker(self):
        data = fixture()
        lookup = {x['id']: x for x in data['objects']}
        other = copy.deepcopy(lookup['checker'])
        other['id'] = 'different-checker'
        data['objects'].append(other)
        data['current'][other['id']] = other['version']
        lookup['fixture-analysis']['dependencies'][1] = reference(other)
        rebind(data)
        approval = by_id(data, 'review-approval')
        approval['embedded']['analysis'] = reference(by_id(data, 'fixture-analysis'))
        approval['sha256'] = digest(approval['embedded'])
        rebind(data)
        reg = Registry(data)
        self.assertFalse(reg.qualified('consumer-a'))
        self.assertTrue(any('analysis checker identity differs' in g
                            for g in reg.qualification_gaps('consumer-a')))

    def test_named_controls_without_execution_and_raw_approval_cannot_calibrate(self):
        data = fixture()
        calibration = next(x for x in data['objects'] if x['id'] == 'calibration')
        for field in ('subject', 'execution', 'approval', 'reviewer'):
            calibration.pop(field, None)
        calibration['dependencies'] = []
        rebind(data)
        self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_qualification_cannot_expand_the_reviewed_scope(self):
        data = fixture()
        next(x for x in data['objects'] if x['id'] == 'consumer-a')['scope'] = 'all Verilog-A models on all backends'
        self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_qualification_backend_and_requirements_must_match_review(self):
        for field, value in (('backend', 'unreviewed@2'), ('requirements', [])):
            data = fixture()
            by_id(data, 'consumer-a')[field] = value
            self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_calibration_raw_receipt_cannot_be_missing_or_relabelled(self):
        for mutation in ('unavailable', 'wrong-subject', 'wrong-outcome'):
            data = fixture()
            raw = by_id(data, 'cal-raw')
            if mutation == 'unavailable':
                raw.pop('embedded')
            elif mutation == 'wrong-subject':
                raw['embedded']['subject']['sha256'] = '0' * 64
                raw['sha256'] = digest(raw['embedded'])
            else:
                raw['embedded']['outcomes']['wrong'] = 'accepted'
                raw['sha256'] = digest(raw['embedded'])
            rebind(data)
            self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_rebinding_changed_definition_cannot_reuse_old_calibration_receipts(self):
        data = fixture()
        by_id(data, 'checker-definition')['budget'] = 'changed numerical budget'
        rebind(data)
        reg = Registry(data)
        for name in ('consumer-a', 'consumer-b'):
            self.assertFalse(reg.qualified(name))

    def test_broadening_review_fields_without_new_receipt_cannot_grant_scope(self):
        data = fixture()
        for name in ('consumer-a', 'fixture-case'):
            by_id(data, name)['scope'] = 'all-models'
        # The receipt is a separate immutable object, not an alias to edited fields.
        review = by_id(data, 'fixture-review')
        review['claim'] = copy.deepcopy(review['claim'])
        review['claim']['scope'] = 'all-models'
        rebind(data)
        self.assertFalse(Registry(data).qualified('consumer-a'))

    def test_provenance_or_case_readiness_is_not_a_qualification(self):
        reg = Registry(fixture())
        for name in ('spec', 'fixture-case', 'fixture-execution', 'fixture-analysis', 'fixture-review'):
            self.assertFalse(reg.qualified(name))
        self.assertTrue(reg.qualified('checker'))
        self.assertTrue(reg.qualified('consumer-a'))

    def test_new_checker_analysis_reuses_the_original_execution_on_unchanged_inputs(self):
        original = fixture()
        updated = fixture(revision='2')
        original_execution = by_id(original, 'fixture-execution')
        updated_execution = by_id(updated, 'fixture-execution')
        self.assertEqual(reference(original_execution), reference(updated_execution))
        self.assertNotEqual(reference(by_id(original, 'fixture-analysis')),
                            reference(by_id(updated, 'fixture-analysis')))
        keys = {(x['id'], x['version']) for x in updated['objects']}
        updated['objects'].extend(x for x in original['objects']
                                 if (x['id'], x['version']) not in keys)
        self.assertTrue(Registry(updated).qualified('consumer-a'))

    def test_reanalysis_cannot_swap_inputs_case_or_the_raw_execution_identity(self):
        for mutation in ('case-inputs', 'analysis-case', 'execution-raw-inputs'):
            data = fixture()
            case = by_id(data, 'fixture-case')
            analysis = by_id(data, 'fixture-analysis')
            execution = by_id(data, 'fixture-execution')
            if mutation == 'analysis-case':
                other = copy.deepcopy(case)
                other['id'] = 'different-case'
                data['objects'].append(other)
                data['current'][other['id']] = other['version']
                analysis['case'] = reference(other)
                analysis['dependencies'] = [reference(other) if r['id'] == case['id'] else r
                                            for r in analysis['dependencies']]
            else:
                inputs = copy.deepcopy(by_id(data, 'fixture-inputs'))
                inputs['id'] = 'different-inputs'
                inputs['model'] = 'different physical model'
                data['objects'].append(inputs)
                data['current'][inputs['id']] = inputs['version']
                case['inputs'] = reference(inputs)
                case['dependencies'] = [reference(inputs) if r['id'] == 'fixture-inputs' else r
                                        for r in case['dependencies']]
                if mutation == 'execution-raw-inputs':
                    execution['inputs'] = reference(inputs)
                    execution['dependencies'] = [reference(inputs) if r['id'] == 'fixture-inputs' else r
                                                for r in execution['dependencies']]
            rebind(data)
            # Supply a new, internally consistent synthetic review. It cannot
            # authorize reuse of a physically different original execution.
            approval = by_id(data, 'review-approval')
            approval['embedded']['analysis'] = reference(analysis)
            approval['embedded']['case'] = reference(case)
            approval['sha256'] = digest(approval['embedded'])
            rebind(data)
            reg = Registry(data)
            with self.subTest(mutation=mutation):
                self.assertFalse(reg.qualified('consumer-a'))

    def test_dependency_cycles_are_rejected(self):
        data = fixture()
        source = by_id(data, 'spec')
        source['dependencies'] = [reference(source)]
        with self.assertRaisesRegex(RegistryError, 'dependency cycle'):
            Registry(data)

    def test_incomplete_negative_controls_do_not_qualify(self):
        data = fixture()
        by_id(data, 'calibration')['controls']['reject'] = []
        rebind(data)
        self.assertFalse(Registry(data).qualified('consumer-a'))


if __name__ == '__main__':
    unittest.main()
