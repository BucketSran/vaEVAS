"""Requirement links: every capability test names the card it backs.

A case lists its tests (Python methods by namespace, module and unittest id; Rust
tests by package, target and listing id), its explicit check_ methods, and binds
its requirement cards. The links are navigation for review, never support or
qualification. Fixtures use embedded sources only; the real-registry checks read
the archived Rust listing from this repository's own Git objects.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from registry import RegistryError, digest, load, reference
import requirement_links as links
import support_view

ROOT = Path(__file__).resolve().parents[2]
PYTHON = 'python-regression'
MODULE = 'evas/tests/test_demo.py'
KERNEL = dict(namespace='rust-tests', package='demo-kernel', target_kind='lib', target='demo_kernel')


def python(runtime_id, module=MODULE, namespace=PYTHON):
    return dict(namespace=namespace, module=module, runtime_id=runtime_id)


def rust(local_id, **target):
    return dict(KERNEL, **target, local_id=local_id)


def listing(*local_ids):
    binary = dict(package='demo-kernel', version='0.1.0', target_kind=['lib'], name='demo_kernel')
    return dict(schema_version=1, binaries=[binary], tests=[
        dict(binary_index=0, local_id=name, kind='test', ignored=False,
             id='rust:demo-kernel@0.1.0/lib/demo_kernel::' + name) for name in local_ids])


def rebind(objects):
    """Rebind every reference to its target's current content, until stable."""
    lookup = {(obj['id'], obj['version']): obj for obj in objects}

    def update(value):
        if isinstance(value, dict):
            if set(value) == {'id', 'version', 'sha256'} and (value['id'], value['version']) in lookup:
                return reference(lookup[(value['id'], value['version'])])
            return {key: update(item) for key, item in value.items()}
        if isinstance(value, list):
            return [update(item) for item in value]
        return value

    for _attempt in range(8):
        before = json.dumps(objects, sort_keys=True)
        for obj in objects:
            for field, value in list(obj.items()):
                if field not in ('id', 'version'):
                    obj[field] = update(value)
        if json.dumps(objects, sort_keys=True) == before:
            return
    raise AssertionError('fixture references did not stabilize')


class Fixture:
    """Two Python methods, three Rust tests, one requirement card and two linked cases."""

    def __init__(self, root, rust_tests=('limits::tests::one', 'limits::tests::two', 'other::tests::three')):
        self.root = root
        self.listing = listing(*rust_tests)
        source = dict(schema_version=1, id='source:listing', version='1', kind='source', status='active',
                      origin='fixture-only', availability='repository-contained',
                      locator={'kind': 'embedded', 'value': self.listing}, sha256=digest(self.listing),
                      dependencies=[])
        entry = dict(schema_version=1, id='entry:python', version='1', kind='entrypoint', status='active',
                     namespace=PYTHON, collector='unittest', start='evas/tests', pattern='test*.py',
                     dependencies=[])
        native = dict(schema_version=1, id='entry:rust', version='1', kind='entrypoint', status='active',
                      namespace='rust-tests', collector='binary-listing', listing_profile='fixture-profile',
                      rust_target=dict(package='demo-kernel', version='0.1.0', target_kind=['lib'],
                                       name='demo_kernel'),
                      listing_source=reference(source), dependencies=[reference(source)])
        asset = dict(schema_version=1, id='asset:demo', version='1', kind='asset', status='active',
                     namespace='EVAS-assets', current_path=MODULE, content={'algorithm': 'sha256', 'value': 'a' * 64},
                     role={'status': 'pending', 'reason': 'fixture role not reviewed'},
                     consumers=[reference(entry)], consumer_status='pending', location_history=[],
                     dependencies=[])
        self.catalog, self.inline = [source, entry, native, asset], []
        for name in ('test_one', 'test_two'):
            self.add_method(name)
        card = dict(id='requirement:demo', version='1', kind='requirement', status='pending', review='pending',
                    scope='fixture card', dependencies=[])
        checker = dict(id='checker:demo', version='1', kind='checker', status='pending', review='pending',
                       scope='fixture assertions', dependencies=[])
        python_case = dict(id='case:demo-python', version='1', kind='case', status='pending', review='pending',
                           scope='fixture card tests', requirements=[reference(card)],
                           tests=[python('test_demo.Case.test_one'), python('test_demo.Case.test_two')],
                           test_scope=[dict(namespace=PYTHON, module=MODULE)],
                           dependencies=[reference(card), reference(checker)])
        rust_case = dict(id='case:demo-rust', version='1', kind='case', status='pending', review='pending',
                         scope='fixture card tests', requirements=[reference(card)],
                         tests=[rust('limits::tests::one'), rust('limits::tests::two')],
                         test_scope=[dict(KERNEL, module_path='limits::tests')],
                         dependencies=[reference(card), reference(checker)])
        self.inline.extend([card, checker, python_case, rust_case])

    def add_method(self, name):
        asset = self.get('asset:demo')
        entry = self.get('entry:python')
        self.catalog.append(dict(
            schema_version=1, id='method:' + name, version='1', kind='method', status='active', namespace=PYTHON,
            runtime_id='test_demo.Case.' + name, module=reference(asset),
            definition={'path': MODULE, 'sha256': 'b' * 64, 'line': 1, 'name': name}, generated=False,
            entrypoints=[reference(entry)], runtime_history=[], semantic_status='pending',
            dependencies=[reference(asset)]))

    def get(self, name, version='1'):
        return next(obj for obj in self.catalog + self.inline if obj['id'] == name and obj['version'] == version)

    def save(self, *, bind=True, current=None):
        objects = self.catalog + self.inline
        if bind:
            rebind(objects)
        selected = {obj['id']: obj['version'] for obj in objects}
        selected.update(current or {})
        parts = {'sources.json': ('sources', 'source'), 'entrypoints.json': ('entrypoints', 'entrypoint'),
                 'assets.json': ('assets', 'asset'), 'methods.json': ('methods', 'method')}
        header = dict(schema_version=1, objects=self.inline, object_parts=sorted(parts), current=selected)
        files = {'registry.json': header, 'source-inventory.json': {'items': []},
                 'dispositions.json': {'items': []}, 'target-scope.json': {},
                 'boundary-audit.json': {'normalized_inventory_identity': digest([])},
                 'language-profile.json': {'base': '2.4', 'selected_changes': [], 'changes': {}}}
        for name, (kind, object_kind) in parts.items():
            files[name] = dict(schema_version=1, kind=kind,
                               objects=[obj for obj in self.catalog if obj['kind'] == object_kind])
        for name, value in files.items():
            (self.root / name).write_text(json.dumps(value, sort_keys=True))
        return load(self.root, root=self.root)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.fixture = Fixture(Path(directory.name))

    def report(self, **options):
        return links.check(self.fixture.save(**options))

    def assertRejected(self, needle, **options):
        errors = self.report(**options)['errors']
        self.assertTrue(any(needle in error for error in errors), errors)
        return errors


class ResolvedLinks(FixtureCase):
    def test_bound_cases_resolve_every_python_and_rust_test(self):
        report = self.report()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['linked_tests'], 4)
        resolved = {(item['case'], item['test']) for item in report['links']}
        self.assertIn(('case:demo-python@1', 'python-regression:evas/tests/test_demo.py:test_demo.Case.test_one'), resolved)
        self.assertIn(('case:demo-rust@1', 'rust-tests:demo-kernel/lib/demo_kernel::limits::tests::two'), resolved)
        self.assertTrue(all(item['requirements'] == ['requirement:demo@1'] for item in report['links']))

    def test_links_never_confer_support_or_qualification(self):
        registry = self.fixture.save()
        self.assertEqual(links.check(registry)['errors'], [])
        for name in ('requirement:demo', 'checker:demo', 'case:demo-python', 'case:demo-rust'):
            self.assertFalse(registry.qualified(name), name)
        self.assertIs(links.check(registry)['confers_support'], False)

    def test_one_test_may_back_two_cards(self):
        second = dict(copy.deepcopy(self.fixture.get('requirement:demo')), id='requirement:second')
        self.fixture.inline.append(second)
        case = self.fixture.get('case:demo-rust')
        case['requirements'].append(reference(second))
        case['dependencies'].append(reference(second))
        report = self.report()
        self.assertEqual(report['errors'], [])
        both = [item for item in report['links'] if item['test'].endswith('limits::tests::one')]
        self.assertEqual(both[0]['requirements'], ['requirement:demo@1', 'requirement:second@1'])


class RejectedLinks(FixtureCase):
    def test_unknown_python_method_is_rejected(self):
        self.fixture.get('case:demo-python')['tests'].append(python('test_demo.Case.test_missing'))
        self.assertRejected('unknown test python-regression:evas/tests/test_demo.py:test_demo.Case.test_missing')

    def test_python_method_under_another_module_or_namespace_is_rejected(self):
        tests = self.fixture.get('case:demo-python')['tests']
        tests[0] = python('test_demo.Case.test_one', module='evas/tests/test_other.py')
        tests[1] = python('test_demo.Case.test_two', namespace='validation')
        errors = self.assertRejected('unknown test python-regression:evas/tests/test_other.py:test_demo.Case.test_one')
        self.assertTrue(any('unknown test validation:evas/tests/test_demo.py:test_demo.Case.test_two' in e for e in errors), errors)

    def test_unknown_rust_test_or_target_is_rejected(self):
        tests = self.fixture.get('case:demo-rust')['tests']
        tests.append(rust('limits::tests::missing'))
        tests.append(rust('limits::tests::one', target='other_kernel'))
        errors = self.assertRejected('unknown test rust-tests:demo-kernel/lib/demo_kernel::limits::tests::missing')
        self.assertTrue(any('unknown test rust-tests:demo-kernel/lib/other_kernel::limits::tests::one' in e
                            for e in errors), errors)

    def test_unreadable_rust_listing_fails_closed(self):
        source = self.fixture.get('source:listing')
        source['availability'] = 'pending'
        source['locator'] = {'kind': 'pending-archive', 'repository': 'vaevas-evidence', 'revision': None,
                             'path': 'discovery/' + 'c' * 64 + '.json'}
        errors = self.assertRejected('Rust listing unavailable')
        self.assertTrue(any('unknown test rust-tests:' in e for e in errors), errors)

    def test_unknown_requirement_is_rejected(self):
        case = self.fixture.get('case:demo-python')
        case['requirements'] = [dict(id='requirement:missing', version='1', sha256='d' * 64)]
        self.assertRejected('unknown requirement requirement:missing@1')

    def test_unknown_requirement_bound_as_a_dependency_cannot_even_load(self):
        case = self.fixture.get('case:demo-python')
        missing = dict(id='requirement:missing', version='1', sha256='d' * 64)
        case['requirements'] = [missing]
        case['dependencies'].append(missing)
        with self.assertRaisesRegex(RegistryError, 'missing dependency'):
            self.fixture.save()

    def test_requirement_content_changed_after_binding_is_rejected(self):
        self.fixture.save()
        self.fixture.get('requirement:demo')['scope'] = 'edited card'
        self.assertRejected('requirement:demo@1 content changed since the link was bound', bind=False)

    def test_requirement_must_be_a_bound_dependency(self):
        case = self.fixture.get('case:demo-python')
        case['dependencies'] = [ref for ref in case['dependencies'] if ref['id'] != 'requirement:demo']
        self.assertRejected('requirement:demo@1 is not a bound dependency')

    def test_superseded_requirement_version_is_rejected(self):
        newer = dict(copy.deepcopy(self.fixture.get('requirement:demo')), version='2', scope='revised card')
        self.fixture.inline.append(newer)
        self.assertRejected('requirement:demo@1 is not the current version',
                            current={'requirement:demo': '2'})

    def test_a_link_to_a_non_requirement_object_is_rejected(self):
        case = self.fixture.get('case:demo-python')
        checker = self.fixture.get('checker:demo')
        case['requirements'] = [reference(checker)]
        self.assertRejected('checker:demo@1 is a checker, not a requirement card')

    def test_case_needs_a_requirement_and_a_checker(self):
        case = self.fixture.get('case:demo-python')
        case['requirements'] = []
        case['dependencies'] = [ref for ref in case['dependencies'] if ref['id'] != 'checker:demo']
        errors = self.assertRejected('case:demo-python@1: tests need at least one bound requirement card')
        self.assertTrue(any('case:demo-python@1: tests need a bound current checker' in e for e in errors), errors)

    def test_tests_belong_on_a_case(self):
        card = self.fixture.get('requirement:demo')
        card['tests'] = [python('test_demo.Case.test_one')]
        self.assertRejected('requirement:demo@1: tests, test_scope and checks belong on a case, not a requirement')

    def test_malformed_and_repeated_locators_are_rejected(self):
        tests = self.fixture.get('case:demo-python')['tests']
        tests.extend([
            dict(namespace=PYTHON, module=MODULE),
            dict(python('test_demo.Case.test_one'), line=1),
            dict(namespace='unknown', module=MODULE, runtime_id='x'),
            dict(namespace=PYTHON, module='../escape.py', runtime_id='x'),
            'test_demo.Case.test_one',
            python('test_demo.Case.test_two'),
        ])
        errors = self.assertRejected('malformed test locator')
        self.assertEqual(sum('malformed test locator' in e for e in errors), 5, errors)
        self.assertTrue(any('repeated test python-regression:evas/tests/test_demo.py:test_demo.Case.test_two' in e
                            for e in errors), errors)

    def test_legacy_single_method_must_resolve(self):
        case = self.fixture.get('case:demo-python')
        case['method'] = 'test_demo.Case.test_one'
        self.assertEqual(self.report()['errors'], [])
        case['method'] = 'test_demo.Case.renamed'
        self.assertRejected('legacy method test_demo.Case.renamed does not name exactly one current method')


class ExplicitChecks(FixtureCase):
    """check_ methods need an external kernel; discovery never collects them, the source names them."""
    SOURCE = ('import unittest\n\n\nclass Case(unittest.TestCase):\n'
              '    def test_one(self):\n        pass\n\n    def test_two(self):\n        pass\n\n'
              '    def check_external(self):\n        pass\n')

    def setUp(self):
        super().setUp()
        module = self.fixture.root / MODULE
        module.parent.mkdir(parents=True)
        module.write_text(self.SOURCE)

    def check(self, runtime_id, module=MODULE):
        self.fixture.get('case:demo-python')['checks'] = [dict(module=module, runtime_id=runtime_id)]

    def test_existing_check_is_linked_to_the_card(self):
        self.check('test_demo.Case.check_external')
        report = self.report()
        self.assertEqual((report['errors'], report['linked_tests'], report['linked_checks']), ([], 4, 1))
        row = next(item for item in report['links'] if item['test'].startswith('explicit-check:'))
        self.assertEqual((row['test'], row['resolved'], row['requirements']),
                         ('explicit-check:evas/tests/test_demo.py:test_demo.Case.check_external', 'module-source',
                          ['requirement:demo@1']))

    def test_missing_check_is_rejected(self):
        self.check('test_demo.Case.check_missing')
        self.assertRejected('unknown explicit check explicit-check:evas/tests/test_demo.py:test_demo.Case.check_missing '
                            '(method not found in the module source)')

    def test_a_check_discovery_would_collect_is_rejected(self):
        self.check('test_demo.Case.test_one')
        self.assertRejected('(name starts with test, so discovery would collect it)')

    def test_a_check_outside_the_catalog_is_rejected(self):
        self.check('test_other.Case.check_external', module='evas/tests/test_other.py')
        self.assertRejected('(module is not a current catalog asset)')

    def test_malformed_check_is_rejected(self):
        self.fixture.get('case:demo-python')['checks'] = [dict(runtime_id='test_demo.Case.check_external')]
        self.assertRejected('malformed test locator')


class UnlinkedCapabilityTests(FixtureCase):
    """A new test inside a declared capability container must name a card."""

    def test_new_python_method_in_a_linked_module_is_reported(self):
        self.fixture.add_method('test_three')
        self.assertRejected(
            'capability test python-regression:evas/tests/test_demo.py:test_demo.Case.test_three '
            'is not linked to a requirement card')

    def test_new_rust_test_in_a_linked_module_is_reported(self):
        listing_ = listing('limits::tests::one', 'limits::tests::two', 'limits::tests::added', 'other::tests::three')
        source = self.fixture.get('source:listing')
        source['locator'] = {'kind': 'embedded', 'value': listing_}
        source['sha256'] = digest(listing_)
        self.assertRejected('capability test rust-tests:demo-kernel/lib/demo_kernel::limits::tests::added '
                            'is not linked to a requirement card')

    def test_tests_outside_declared_containers_are_not_capability_tests(self):
        report = self.report()
        self.assertNotIn('other::tests::three', json.dumps(report['errors']))

    def test_a_container_without_current_tests_is_rejected(self):
        scope = self.fixture.get('case:demo-rust')['test_scope']
        scope.append(dict(KERNEL, module_path='renamed::tests'))
        self.assertRejected('test scope rust-tests:demo-kernel/lib/demo_kernel::renamed::tests has no current tests')

    def test_malformed_container_is_rejected(self):
        self.fixture.get('case:demo-python')['test_scope'].append(dict(namespace=PYTHON))
        self.assertRejected('malformed test scope')

    def test_new_tests_since_a_base_registry_are_listed_until_linked(self):
        base = self.fixture.save()
        self.fixture.add_method('test_three')
        listing_ = listing('limits::tests::one', 'limits::tests::two', 'other::tests::three', 'fresh::tests::four')
        source = self.fixture.get('source:listing')
        source['locator'] = {'kind': 'embedded', 'value': listing_}
        source['sha256'] = digest(listing_)
        report = links.new_unlinked(base, self.fixture.save())
        self.assertEqual(report['new_tests'], 2)
        self.assertEqual(report['unlinked'], [
            'python-regression:evas/tests/test_demo.py:test_demo.Case.test_three',
            'rust-tests:demo-kernel/lib/demo_kernel::fresh::tests::four'])
        self.fixture.get('case:demo-python')['tests'].append(python('test_demo.Case.test_three'))
        self.fixture.get('case:demo-rust')['tests'].append(rust('fresh::tests::four'))
        report = links.new_unlinked(base, self.fixture.save())
        self.assertEqual((report['new_tests'], report['unlinked']), (2, []))

    def test_an_unreadable_base_listing_is_a_problem_not_a_set_of_new_tests(self):
        source = self.fixture.get('source:listing')
        readable = copy.deepcopy(source)
        source['availability'] = 'pending'
        source['locator'] = {'kind': 'pending-archive', 'repository': 'vaevas-evidence', 'revision': None,
                             'path': 'discovery/' + 'c' * 64 + '.json'}
        base = self.fixture.save()
        source.clear()
        source.update(readable)
        report = links.new_unlinked(base, self.fixture.save())
        self.assertTrue(any('Rust listing unavailable' in problem for problem in report['base_problems']), report)
        self.assertEqual(report['problems'], [])


class SupportViewNavigation(FixtureCase):
    def test_bound_cases_are_listed_under_their_card_as_navigation(self):
        projected = support_view.document(self.fixture.save())
        card = next(item for item in projected['requirements'] if item['id'] == 'requirement:demo')
        self.assertEqual([(case['id'], case['tests']) for case in card['linked_cases']],
                         [('case:demo-python', {'python-regression': 2}), ('case:demo-rust', {'rust-tests': 2})])
        self.assertTrue(all(case['confers_requirement_support'] is False for case in card['linked_cases']))
        text = support_view.markdown(projected)
        self.assertIn('关联案例：`case:demo-python`@1', text)
        self.assertEqual(support_view.audit(projected) + support_view.audit_markdown(projected, text), [])

    def test_a_case_whose_card_changed_is_not_listed(self):
        self.fixture.save()
        self.fixture.get('requirement:demo')['scope'] = 'edited card'
        registry = self.fixture.save(bind=False)
        card = next(item for item in support_view.document(registry)['requirements'] if item['id'] == 'requirement:demo')
        self.assertEqual(card['linked_cases'], [])

    def test_card_fields_are_projected_and_rendered(self):
        card = self.fixture.get('requirement:demo')
        card.update(normative_basis='no clause; fixture limit', related_source_locations=[{'clause': '8.3.2'}],
                    target_scope_applicability={'included_groups': ['voltage-relations']},
                    independent_answers=[{'observable': 'count', 'derivation': 'formula'}])
        projected = support_view.document(self.fixture.save())
        fields = next(item for item in projected['requirements'] if item['id'] == 'requirement:demo')['source_fields']
        for key in ('normative_basis', 'related_source_locations', 'target_scope_applicability', 'independent_answers'):
            self.assertIn(key, fields)
        text = support_view.markdown(projected)
        self.assertIn('原文 independent_answers：[{"derivation": "formula", "observable": "count"}]', text)
        self.assertIn('原文 normative_basis："no clause; fixture limit"', text)


BATCH1_CARDS = {
    'evas/tests/test_proof_work_limit.py': 'requirement:proof-work-limit',
    'evas/tests/test_output_point_limit.py': 'requirement:output-point-limit',
}
BATCH1_PYTHON = {
    'evas/tests/test_proof_work_limit.py': [
        'ProofWorkLimitEndToEnd.test_a_lower_request_limit_exhausts_the_same_request_that_default_completes',
        'ProofWorkLimitEndToEnd.test_default_exhausts_naturally_and_a_larger_limit_completes_with_exact_answers',
        'ProofWorkLimitEndToEnd.test_failed_reservations_are_not_refunded_so_a_retry_cannot_launder_the_ledger',
        'ProofWorkLimitFrontend.test_integer_subclass_is_not_an_integer_request',
        'ProofWorkLimitFrontend.test_invalid_values_are_rejected_and_never_sent',
        'ProofWorkLimitFrontend.test_limits_are_the_designed_named_constants',
        'ProofWorkLimitFrontend.test_set_value_is_sent_as_an_exact_integer',
        'ProofWorkLimitFrontend.test_unset_request_is_byte_identical_to_the_previous_request',
        'ProofWorkLimitKernel.test_explicit_default_is_the_same_ledger_as_unset',
        'ProofWorkLimitKernel.test_kernel_accepts_the_exact_boundaries',
        'ProofWorkLimitKernel.test_kernel_rejects_an_unknown_transient_field_by_name',
        'ProofWorkLimitKernel.test_kernel_rejects_every_invalid_shape_as_invalid_inputs',
        'ProofWorkLimitProtocol.test_c8_comparison_requires_the_echoed_default_before_removing_it',
        'ProofWorkLimitProtocol.test_default_request_echoes_the_default_limit',
        'ProofWorkLimitProtocol.test_echo_must_equal_a_requested_limit',
        'ProofWorkLimitProtocol.test_malformed_echoes_are_invalid_responses',
        'ProofWorkLimitProtocol.test_old_kernel_without_the_echo_is_still_accepted_without_a_request',
        'ProofWorkLimitProtocol.test_requested_limit_cannot_be_silently_dropped',
        'ProofWorkLimitProtocol.test_unrequested_echo_must_be_the_default',
        'ProofWorkLimitSurfaces.test_cli_flag_is_only_for_transient_and_simulate',
        'ProofWorkLimitSurfaces.test_cli_manifest_null_limit_is_rejected_before_any_kernel_runs',
        'ProofWorkLimitSurfaces.test_cli_manifest_without_the_limit_or_with_an_integer_reaches_the_kernel',
        'ProofWorkLimitSurfaces.test_cli_rejects_malformed_values_before_running',
        'ProofWorkLimitSurfaces.test_cli_simulate_accepts_a_digits_only_limit',
        'ProofWorkLimitSurfaces.test_cli_transient_manifest_forwards_the_limit',
        'ProofWorkLimitSurfaces.test_simulate_scs_forwards_and_echoes_the_limit',
    ],
    'evas/tests/test_output_point_limit.py': [
        'KernelCheckpoint.test_kernel_rejects_one_more_than_the_limit_of_forced_points',
        'LargeGridEndToEnd.test_exceeding_the_new_limit_is_still_rejected_with_the_actual_constant',
        'LargeGridEndToEnd.test_stateless_gain_over_a_hundred_thousand_rows_matches_the_closed_form',
        'OutputPointLimitConstants.test_no_stray_hundred_thousand_remains_at_the_eight_checkpoints',
        'OutputPointLimitConstants.test_python_symbols_are_the_one_named_limit',
        'OutputPointLimitConstants.test_rust_constant_has_the_same_value_and_guards_the_kernel_check',
        'PulseCornerCheckpoint.test_corner_count_cap_minus_one_cap_and_cap_plus_one',
        'PulseCornerCheckpoint.test_real_limit_rejects_before_building_a_million_corners',
        'ResponseEvidenceCheckpoint.test_times_length_cap_minus_one_cap_and_cap_plus_one',
        'ScsCornerAndSavedCheckpoints.test_rows_after_including_source_corners',
        'ScsCornerAndSavedCheckpoints.test_saved_rows_with_forced_points',
        'ScsGridCheckpoint.test_grid_is_admitted_exactly_while_floor_ratio_plus_two_fits',
        'ScsGridCheckpoint.test_message_names_the_enforced_limit',
        'ScsGridCheckpoint.test_the_previous_hundred_thousand_rows_are_no_longer_rejected',
        'StrobeCheckpoints.test_explicit_count',
        'StrobeCheckpoints.test_patched_symbol_changes_the_enforced_limit_and_message',
        'StrobeCheckpoints.test_periodic_count',
        'StrobeCheckpoints.test_union_count',
    ],
}
PROOF, POINTS = 'requirement:proof-work-limit', 'requirement:output-point-limit'
# Explicit check_ methods: they need a kernel built from main or a release kernel,
# so discovery does not collect them and CI records no skip for them.
BATCH1_CHECKS = {
    ('evas/tests/test_proof_work_limit.py',
     'test_proof_work_limit.ProofWorkLimitKernel.check_kernel_without_the_field_rejects_it_explicitly'): PROOF,
    ('evas/tests/test_proof_work_limit.py',
     'test_proof_work_limit.ProofWorkLimitKernel.check_default_request_response_equals_main_except_the_echoed_default'): PROOF,
    ('evas/tests/test_output_point_limit.py',
     'test_output_point_limit.LargeGridEndToEnd.check_rc_step_response_over_a_hundred_thousand_rows'): POINTS,
}
BATCH1_RUST = {
    ('evas-ir', 'evas_ir', 'request_resource_limit_tests::named_limits_have_the_designed_values'): {PROOF, POINTS},
    ('evas-ir', 'evas_ir', 'request_resource_limit_tests::field_is_request_metadata_and_never_part_of_the_serialized_config'): {PROOF},
    ('evas-ir', 'evas_ir', 'request_resource_limit_tests::integers_within_one_and_the_hard_bound_are_accepted_exactly'): {PROOF},
    ('evas-ir', 'evas_ir', 'request_resource_limit_tests::every_other_shape_is_invalid_inputs'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'observation::echo_tests::effective_controls_echo_the_requested_and_the_default_proof_limit'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'pwl::output_point_limit_tests::trajectory_rejects_an_out_of_range_proof_limit'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'pwl::output_point_limit_tests::strobe_count_boundary_is_the_shared_million_point_limit'): {POINTS},
    ('evas-kernel', 'evas_kernel', 'pwl::output_point_limit_tests::previous_hundred_thousand_boundary_no_longer_rejects'): {POINTS},
    ('evas-kernel', 'evas_kernel', 'transition_source_plan::budget_tests::request_constructors_equal_the_default_ledger_when_unset'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'transition_source_plan::budget_tests::request_constructors_change_only_the_work_slot'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'transition_source_plan::budget_tests::request_constructor_rejects_an_unvalidated_limit'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'transition_source_plan::budget_tests::config_identity_bytes_and_their_charge_do_not_depend_on_the_requested_limit'): {PROOF},
    ('evas-kernel', 'evas_kernel', 'transition_source_plan::budget_tests::requested_limit_is_one_sticky_ledger_with_the_actual_limit_in_the_message'): {PROOF},
}


class CurrentRegistryLinks(unittest.TestCase):
    """The real registry. Rust IDs come from the archived native listing it binds."""

    @classmethod
    def setUpClass(cls):
        cls.registry = load(root=ROOT, repositories={'vaevas': ROOT})
        cls.report = links.check(cls.registry)
        cls.cards = {}
        for item in cls.report['links']:
            cls.cards.setdefault(item['test'], set()).update(
                name.rsplit('@', 1)[0] for name in item['requirements'])

    def test_every_current_link_resolves_and_every_declared_container_is_linked(self):
        self.assertEqual(self.report['errors'], [])

    def test_each_batch1_python_method_is_linked_to_its_card(self):
        self.assertEqual(sum(map(len, BATCH1_PYTHON.values())), 44)
        for module, names in BATCH1_PYTHON.items():
            stem = Path(module).stem
            for name in names:
                with self.subTest(module=module, name=name):
                    key = f'{PYTHON}:{module}:{stem}.{name}'
                    self.assertEqual(self.cards.get(key), {BATCH1_CARDS[module]})

    def test_each_batch1_rust_test_is_linked_to_its_cards(self):
        self.assertEqual(len(BATCH1_RUST), 13)
        for (package, target, local_id), cards in BATCH1_RUST.items():
            with self.subTest(local_id=local_id):
                self.assertEqual(self.cards.get(f'rust-tests:{package}/lib/{target}::{local_id}'), cards)

    def test_each_batch1_explicit_check_is_linked_to_its_card(self):
        self.assertEqual(len(BATCH1_CHECKS), 3)
        for (module, runtime_id), card in BATCH1_CHECKS.items():
            with self.subTest(runtime_id=runtime_id):
                self.assertEqual(self.cards.get(f'explicit-check:{module}:{runtime_id}'), {card})

    def test_batch1_cards_are_current_pending_and_unqualified(self):
        current = self.registry.data['current']
        for name in (PROOF, POINTS):
            card = self.registry.objects[(name, current[name])]
            self.assertEqual((card['kind'], card['status'], card['review']), ('requirement', 'pending', 'pending'))
            for field in ('source_locations', 'related_source_locations', 'normative_basis',
                          'target_scope_applicability', 'allowed_behavior', 'observables', 'budget',
                          'independent_answers'):
                self.assertIn(field, card, (name, field))
            self.assertFalse(self.registry.qualified(name))
        cases = [item['case'].rsplit('@', 1)[0] for item in self.report['links']]
        for name in set(cases):
            case = self.registry.objects[(name, current[name])]
            self.assertEqual((case['status'], case['review']), ('pending', 'pending'), name)
            self.assertFalse(self.registry.qualified(name))


# Batch 2 (defect fixes): each card links whole test modules and, where it has
# kernel unit tests, one kernel test module.
BATCH2 = {
    'requirement:cross-event-body-right-limit': dict(
        python={'evas/tests/test_cross_right_limit.py': 15, 'evas/tests/test_cross_body_right_limit_cases.py': 18},
        rust=('procedure::plan::right_limit::tests', 4)),
    'requirement:event-observer-math-isolation': dict(
        python={'evas/tests/test_group_math_sampled_domain.py': 10,
                'evas/tests/test_event_observer_math_display.py': 2},
        rust=None),
    'requirement:idt-reset-argument-procedure-frame': dict(
        python={'evas/tests/test_idt_reset_procedure_frame.py': 6},
        rust=('canonical::tests', 3)),
    'requirement:bound-step-request-invariance': dict(
        python={'evas/tests/test_bound_step_request_invariance.py': 5},
        rust=None),
}


class Batch2RegistryLinks(unittest.TestCase):
    """The real registry: every batch-2 test module is linked to its card only."""

    @classmethod
    def setUpClass(cls):
        cls.registry = load(root=ROOT, repositories={'vaevas': ROOT})
        cls.report = links.check(cls.registry)
        cls.cards = {}
        for item in cls.report['links']:
            cls.cards.setdefault(item['test'], set()).update(
                name.rsplit('@', 1)[0] for name in item['requirements'])

    def test_every_batch2_python_method_is_linked_to_its_card(self):
        import ast
        for card, spec in BATCH2.items():
            for module, count in spec['python'].items():
                tree = ast.parse((ROOT / module).read_text())
                names = [f'{node.name}.{item.name}' for node in tree.body if isinstance(node, ast.ClassDef)
                         for item in node.body if isinstance(item, ast.FunctionDef) and item.name.startswith('test')]
                self.assertEqual(len(names), count, module)
                for name in names:
                    with self.subTest(module=module, name=name):
                        key = f'{PYTHON}:{module}:{Path(module).stem}.{name}'
                        self.assertEqual(self.cards.get(key), {card})

    def test_every_batch2_rust_test_is_linked_to_its_card(self):
        for card, spec in BATCH2.items():
            if spec['rust'] is None:
                continue
            module, count = spec['rust']
            prefix = f'rust-tests:evas-kernel/lib/evas_kernel::{module}::'
            linked = sorted(key for key, cards in self.cards.items() if key.startswith(prefix))
            self.assertEqual(len(linked), count, module)
            for key in linked:
                self.assertEqual(self.cards[key], {card}, key)

    def test_batch2_cards_are_current_pending_and_unqualified(self):
        current = self.registry.data['current']
        for name in BATCH2:
            card = self.registry.objects[(name, current[name])]
            self.assertEqual((card['kind'], card['status'], card['review']), ('requirement', 'pending', 'pending'))
            for field in ('source_locations', 'allowed_behavior', 'observables', 'budget', 'independent_answers',
                          'card_source'):
                self.assertIn(field, card, (name, field))
            self.assertEqual(card['version'], card['card_source']['version'])
            self.assertFalse(self.registry.qualified(name))


if __name__ == '__main__':
    unittest.main()
