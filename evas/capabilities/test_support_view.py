"""Fixture checks for the four-backend requirement projection (current default support view).

These controls do not add requirements to the real registry and do not confer
scientific qualification.
"""
import copy
import itertools
import json
import re
import unittest
from pathlib import Path

import render
import support_view
from registry import Registry, digest
from support_view import CONTRACT_FIELDS, audit, audit_markdown, document, dumps, markdown, write_preview
from test_registry import by_id, fixture


def refresh(data):
    """Rebind references, including receipts, after an in-memory fixture edit."""
    from registry import reference
    lookup = {(obj['id'], obj['version']): obj for obj in data['objects']}

    def update(value):
        if isinstance(value, dict):
            if set(value) == {'id', 'version', 'sha256'}:
                return reference(lookup[(value['id'], value['version'])])
            return {key: update(item) for key, item in value.items()}
        if isinstance(value, list):
            return [update(item) for item in value]
        return value

    for _attempt in range(8):
        for obj in data['objects']:
            for field, value in list(obj.items()):
                obj[field] = update(value)
        moved = False
        for obj in data['objects']:
            if obj.get('kind') == 'source' and 'embedded' in obj:
                sha = digest(obj['embedded'])
                if obj.get('sha256') != sha:
                    obj['sha256'] = sha
                    moved = True
        if not moved:
            return data
    raise AssertionError('fixture references did not stabilize')


def retarget(data, backend):
    data = copy.deepcopy(data)

    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if value == 'fixture@1':
            return backend
        return value

    data['objects'] = walk(data['objects'])
    return refresh(data)


def set_outcome(data, outcome, numerical=None):
    execution = by_id(data, 'fixture-execution')
    execution['outcome'] = outcome
    if numerical is not None:
        execution['numerical'] = numerical
    raw = by_id(data, 'execution-raw')
    raw['embedded']['outcome'] = outcome
    return refresh(data)


def add_inventory(data, name):
    data['inventory'].append({'id': name, 'kind': 'clause'})
    data['dispositions'].append({'source_id': name, 'decision': 'pending',
                                 'reason': 'source index row without a requirement'})


def bare_registry():
    data = fixture()
    spec = by_id(data, 'spec')
    data['objects'].append({
        'id': 'bare-requirement',
        'version': '1',
        'kind': 'requirement',
        'status': 'pending',
        'review': 'pending',
        'scope': 'fixture bare scope',
        'language_profile': 'fixture-profile',
        'gap': 'no evidence recorded for this requirement',
        'dependencies': [rebind_ref(spec)],
    })
    data['current']['bare-requirement'] = '1'
    data['language_profile'] = {
        'id': 'fixture-profile', 'version': '9', 'base': '2.4', 'selected_changes': ['7780'],
    }
    add_inventory(data, 'section:extra')
    add_inventory(data, 'section:extra-2')
    return Registry(data)


def rebind_ref(obj):
    from registry import reference
    return reference(obj)


def checked(registry, historical=None):
    projected = document(registry, historical=historical)
    text = markdown(projected)
    problems = audit(projected) + audit_markdown(projected, text)
    if problems:
        raise AssertionError('\n'.join(problems))
    return projected, text


def independent_registry():
    """Two requirements with distinct contract text and records on the second one."""
    data = retarget(copy.deepcopy(bare_registry().data), 'ngspice')
    for index, name in enumerate(('bare-requirement', 'fixture-requirement')):
        by_id(data, name).update(
            allowed_behavior=f'independent behavior {index}',
            conditions=[f'independent condition {index}'],
            observables=[f'independent observable {index}'],
        )
    by_id(data, 'fixture-execution')['toolchain'] = [
        {'role': 'simulator', 'name': 'ngspice', 'version': 'sim-12345'}]
    for name in ('consumer-a', 'consumer-b'):
        by_id(data, name)['toolchain'] = [
            {'role': 'compiler', 'name': 'OpenVAF-R', 'version': 'cc-67890'}]
    return Registry(refresh(data))


def requirement(projected, name):
    return next(item for item in projected['requirements'] if item['id'] == name)


def evas_records(projected, name='fixture-requirement'):
    return requirement(projected, name)['backends']['evas']['records']


MARKDOWN_VARIANT_KINDS = (
    'status-view_status', 'status-adopted', 'status-provisional', 'qualification-record', 'toolchain',
    'contract-field', 'reference', 'delete-line', 'indent-line', 'heading-level', 'reorder-allowed',
    'blank-reallocation')


def _first_difference_for(facts, text):
    return next(error for error in audit_markdown(facts, text) if error.startswith('markdown differs'))


def markdown_variant_cases(facts, text, *, full=True):
    """(kind, name, changed text, must be rejected) for every class of edit to a generated view.

    Fact lines of each kind (the three status keys, qualification record, toolchain, contract field and
    reference lines) are inserted at every structural position, indented 0-3 spaces, as the same value and
    as a contradictory value. Any generated line deleted, indented or re-levelled must be rejected, and so
    must a blank line moved or added inside a record run unless a legal block reordering carries it; the
    two allowed reorderings must be accepted. full=False trims the position and indent grid for a large text.
    """
    lines = text.split('\n')
    first = lambda prefix: next(line for line in lines if line.startswith(prefix))
    status = {key: first(key + ':') for key in ('view_status', 'adopted', 'provisional')}
    flip = {'current-default': 'preview', 'preview': 'current-default', 'true': 'false', 'false': 'true'}
    sample = {
        'status-view_status': (status['view_status'], 'view_status: ' + flip[facts['view_status']]),
        'status-adopted': (status['adopted'], 'adopted: ' + flip[status['adopted'].split(': ')[1]]),
        'status-provisional': (status['provisional'], 'provisional: ' + flip[status['provisional'].split(': ')[1]]),
        'qualification-record': (first('资格记录：'), first('资格记录：') + ' contradictory'),
        'toolchain': (first('工具链：'), '工具链：consumer-a@1: OpenVAF-R/compiler@wrong-version'),
        'reference': (first('引用：'), first('引用：') + ' contradictory'),
    }
    for key in CONTRACT_FIELDS:
        sample.setdefault('contract-field', []).append((first('原文 ' + key + '：'), first('原文 ' + key + '：') + ' contradictory'))
    where = {}
    at = lines.index
    current, unbound, historical = at('## 当前要求'), at('## 未绑定当前要求的资格'), at('## 历史引用')
    exceptions, classes, limits = at('## 例外'), at('## 分类'), at('## 本视图不做的事')
    heads = [i for i, line in enumerate(lines) if line.startswith('### ') and current < i < unbound]
    where.update({'header-1': 1, 'header-2': 2, 'header-5': 5, 'header-6': 6,
                  'current-preamble': current + 1, 'before-first-requirement': heads[0]})
    for number, head in enumerate(heads):
        end = heads[number + 1] if number + 1 < len(heads) else unbound
        where.update({f'requirement-{number}-after-heading': head + 1, f'requirement-{number}-middle': (head + end) // 2,
                      f'requirement-{number}-last-line': end - 1, f'requirement-{number}-end': end})
    where.update({'unbound-after-heading': unbound + 1, 'unbound-end': historical - 1, 'before-historical': historical,
                  'historical-after-heading': historical + 1, 'historical-middle': (historical + exceptions) // 2,
                  'historical-end': exceptions, 'exceptions-section': exceptions + 1, 'classification-section': classes + 1,
                  'limits-section': limits + 1, 'end-of-text-before-last': len(lines) - 1, 'end-of-text': len(lines)})
    indents = ('', ' ', '  ', '   ') if full else ('', '   ')
    positions = list(where.items()) if full else [
        item for item in where.items() if item[0] in (
            'header-2', 'current-preamble', 'requirement-0-after-heading', 'requirement-1-end', 'unbound-end',
            'historical-middle', 'limits-section', 'end-of-text')]
    cases = []

    def add(kind, name, changed_lines, expect_reject=True):
        cases.append((kind, name, '\n'.join(changed_lines), expect_reject))

    for kind, value in sample.items():
        for entry in (value if isinstance(value, list) else [value]):
            same, contradictory = entry
            for label, line in (('same', same), ('contradictory', contradictory)):
                for indent in indents:
                    for place, index in positions:
                        add(kind, f'{label}/indent{len(indent)}/{place}', lines[:index] + [indent + line] + lines[index:])
                    for heading in ('## 未绑定当前要求的资格', '## 当前要求', '## 补充资格', '### extra@1'):
                        block = [heading, '', indent + line, '']
                        add(kind, f'{label}/indent{len(indent)}/extra-section {heading}',
                            lines[:historical] + block + lines[historical:])
                        add(kind, f'{label}/indent{len(indent)}/extra-section-at-end {heading}', lines + block)
    for index, line in enumerate(lines):
        add('delete-line', f'line {index + 1}', lines[:index] + lines[index + 1:])
        if line and (full or index % 5 == 0):
            for pad in ((' ', '  ', '   ') if full else (' ', '   ')):
                add('indent-line', f'line {index + 1}/{len(pad)}', lines[:index] + [pad + line] + lines[index + 1:])
        if line.startswith('#'):
            add('heading-level', f'line {index + 1}', lines[:index] + ['#' + line] + lines[index + 1:])
            if line.startswith('###'):
                add('heading-level', f'line {index + 1}/demote', lines[:index] + [line[1:]] + lines[index + 1:])
    if full:
        add('delete-line', 'trailing newline', lines[:-1])
        add('indent-line', 'trailing blank', lines + [''])
    # The two reorderings the audit allows.
    sections = [(heads[n], heads[n + 1] if n + 1 < len(heads) else unbound) for n in range(len(heads))]
    if len(sections) >= 2:
        order = [lines[a:b] for a, b in sections]
        add('reorder-allowed', 'requirement-order', lines[:heads[0]] + [x for part in reversed(order) for x in part] + lines[unbound:], False)
    for number, (a, b) in enumerate(sections):
        part = lines[a:b]
        starts = [i for i, line in enumerate(part) if line.startswith('资格记录：')]
        if len(starts) >= 2:
            ends = starts[1:] + [len(part) - 1 if part[-1] == '' else len(part)]
            blocks = [part[x:y] for x, y in zip(starts, ends)]
            tail = part[ends[-1]:]
            rebuilt = part[:starts[0]] + [x for block in reversed(blocks) for x in block] + tail
            add('reorder-allowed', f'record-order requirement {number}', lines[:a] + rebuilt + lines[b:], False)
            if tail == ['']:
                # A block may also take its own separator along: the blocks are then the same units.
                carried = blocks[-1] + [''] + [x for block in reversed(blocks[:-1]) for x in block]
                add('reorder-allowed', f'record-order with carried separator requirement {number}',
                    lines[:a] + part[:starts[0]] + carried + lines[b:], False)
                # Blank lines are compared as text: with the block order unchanged a separator moves nowhere.
                for split in starts[1:]:
                    add('blank-reallocation', f'requirement {number} separator moved to record at {split}',
                        lines[:a] + part[:split] + [''] + part[split:-1] + lines[b:])
                    add('blank-reallocation', f'requirement {number} separator added at record at {split}',
                        lines[:a] + part[:split] + [''] + part[split:] + lines[b:])
                if len(starts) >= 3:
                    # Reordered, but the separator now follows a block that never owned it.
                    wrong = [x for block in reversed(blocks[:-1]) for x in block] + [''] + blocks[-1]
                    add('blank-reallocation', f'requirement {number} reordered, separator after another block',
                        lines[:a] + part[:starts[0]] + wrong + lines[b:])
    return cases


class SupportViewFixtures(unittest.TestCase):
    def test_requirement_without_evidence_has_unknown_backend_facts(self):
        projected, text = checked(bare_registry())
        self.assertEqual(projected['denominators']['current_requirements'], 2)
        self.assertEqual(projected['denominators']['source_index_items'], 3)
        self.assertFalse(projected['denominators']['source_index_is_requirement_coverage'])
        self.assertIn('规范源索引不是要求覆盖率。', text)
        bare = requirement(projected, 'bare-requirement')
        self.assertEqual(bare['language']['resolved']['version'], '9')
        self.assertEqual(bare['scope'], 'fixture bare scope')
        self.assertEqual(bare['requirement_support'], 'not_conferred')
        self.assertEqual(bare['coverage_sufficiency'], 'pending')
        named = requirement(projected, 'fixture-requirement')
        self.assertEqual(named['language']['requirement_field'], 'unknown')
        self.assertEqual(named['language']['resolved'], 'unknown')
        for cell in bare['backends'].values():
            for key in ('toolchain', 'execution', 'completeness', 'numerical',
                        'qualification', 'evidence'):
                self.assertEqual(cell[key]['state'], 'unknown', key)
            self.assertEqual(cell['records'], [])
        self.assertIn('no evidence recorded for this requirement', text)
        self.assertEqual(projected['denominators']['current_requirement_support_conferred'], 0)

    def test_historical_pass_does_not_enter_current_denominator(self):
        historical = {'identity': 'other-lineage', 'source': 'historical-fixture',
                      'scope': 'different inputs and criteria', 'nodes': [
                          {'id': 'old-pass', 'status': 'compared', 'evidence': 'old/table',
                           'requirement': 'bare-requirement',
                           'results': {'evas': '✓ Q3', 'spectre': '✓ Q3', 'ngspice': '✓ Q3',
                                       'gnucap': '✓ Q3'}},
                          {'id': 'old-unjoined', 'status': 'compared', 'evidence': 'old/other',
                           'results': {'evas': '✓ Q3'}},
                          {'id': 'old-absent', 'status': 'compared', 'requirement': 'not-a-current-requirement',
                           'results': {'evas': '✓ Q3'}},
                      ]}
        projected, text = checked(bare_registry(), historical)
        bare = requirement(projected, 'bare-requirement')
        self.assertEqual(bare['backends']['evas']['execution']['state'], 'unknown')
        self.assertEqual(bare['historical_references'][0]['results']['evas'], '✓ Q3')
        self.assertFalse(bare['historical_references'][0]['counts_as_current_support'])
        self.assertEqual(projected['denominators']['current_requirements'], 2)
        self.assertEqual(projected['denominators']['historical_nodes'], 3)
        self.assertEqual(projected['denominators']['historical_nodes_joined_to_current_requirements'], 1)
        self.assertEqual(projected['denominators']['current_requirement_support_conferred'], 0)
        head, _separator, tail = text.partition('## 历史引用')
        self.assertNotIn('✓', head)
        self.assertIn('✓ Q3', tail)
        self.assertIn('old-unjoined', tail)
        self.assertIn('not-a-current-requirement', json.dumps(projected['historical']['not_current']))

    def test_execution_pass_with_pending_qualification_stays_split(self):
        data = retarget(fixture(), 'evas')
        for name in ('consumer-a', 'consumer-b'):
            by_id(data, name)['status'] = 'pending'
        projected, text = checked(Registry(data))
        row = requirement(projected, 'fixture-requirement')
        evas = row['backends']['evas']
        self.assertEqual(evas['execution']['state'], 'records_listed')
        self.assertEqual(evas['numerical']['state'], 'unknown')
        self.assertEqual(evas['toolchain']['state'], 'unknown')
        for name in ('spectre', 'ngspice', 'gnucap'):
            self.assertEqual(row['backends'][name]['execution']['state'], 'unknown')
        record = evas['records'][0]
        self.assertEqual(record['execution']['value'], 'passed')
        self.assertEqual(record['completeness']['value'], True)
        self.assertEqual(record['numerical']['state'], 'unknown')
        self.assertFalse(record['qualification']['current_qualified'])
        self.assertTrue(any(gap.endswith(': pending') for gap in record['qualification']['gaps']))
        self.assertEqual(record['analyses'][0]['outcome']['value'], 'accepted')
        self.assertEqual(record['analyses'][0]['numerical']['state'], 'unknown')
        self.assertEqual(row['requirement_support'], 'not_conferred')
        self.assertEqual(row['coverage_sufficiency'], 'pending')
        self.assertIn('recorded:"passed"', text)
        self.assertIn('分析结论：', text)
        self.assertIn('数值：unknown', text)
        self.assertNotIn('✓', text.partition('## 历史引用')[0])

    def test_revoked_dependency_changes_json_and_markdown(self):
        data = retarget(fixture(), 'evas')
        before, before_text = checked(Registry(data))
        before_json = dumps(before)
        old_sha = digest(by_id(data, 'checker'))
        self.assertTrue(all(record['qualification']['current_qualified']
                            for record in evas_records(before)))
        by_id(data, 'checker')['status'] = 'revoked'
        after, after_text = checked(Registry(data))
        after_json = dumps(after)
        self.assertNotEqual(before_json, after_json)
        self.assertNotEqual(before_text, after_text)
        ids = []
        for record in evas_records(after):
            ids.append(record['qualification']['id'])
            self.assertFalse(record['qualification']['current_qualified'])
            self.assertFalse(record['qualification']['historical_query']['qualified'])
            self.assertTrue(any('revoked' in gap for gap in record['qualification']['gaps']))
        self.assertEqual(ids, ['consumer-a', 'consumer-b'])
        new_sha = digest(by_id(data, 'checker'))
        self.assertNotEqual(old_sha, new_sha)
        for text in (after_json, after_text):
            self.assertIn('revoked', text)
            self.assertIn('consumer-a', text)
            self.assertIn('consumer-b', text)
            self.assertIn(new_sha, text)
            self.assertIn('not_conferred', text)
        self.assertNotIn(old_sha, after_json)
        self.assertEqual(after['denominators']['current_requirement_support_conferred'], 0)

    def test_superseded_version_remains_locatable_without_current_support(self):
        data = retarget(fixture(), 'evas')
        original = by_id(data, 'checker')
        original_sha = digest(original)
        newer = copy.deepcopy(original)
        newer['version'] = '2'
        data['objects'].append(newer)
        data['current']['checker'] = '2'
        projected, text = checked(Registry(data))
        record = evas_records(projected)[0]
        self.assertFalse(record['qualification']['current_qualified'])
        self.assertTrue(record['qualification']['historical_query']['qualified'])
        self.assertFalse(record['qualification']['historical_query']['counts_as_current_support'])
        versions = [item for item in record['locatable_versions'] if item['id'] == 'checker']
        self.assertEqual({item['version'] for item in versions}, {'1', '2'})
        retained = next(item for item in versions if item['version'] == '1')
        self.assertEqual(retained['sha256'], original_sha)
        self.assertFalse(retained['selected'])
        self.assertIn(original_sha, text)
        self.assertIn('historical_qualified: true', text)
        self.assertIn('current_qualified: false', text)
        self.assertIn('counts_as_current_support: false', text)
        self.assertEqual(projected['denominators']['current_requirement_support_conferred'], 0)

    def test_missing_toolchain_and_aliases_are_not_filled(self):
        data = retarget(fixture(), 'ngspice')
        requirement_ref = rebind_ref(by_id(data, 'fixture-requirement'))
        for name, backend, toolchain in (
            ('alias-openvaf', 'OpenVAF', [{'role': 'compiler', 'name': 'OpenVAF', 'version': '9.9.9'}]),
            ('alias-heading', 'ngspice + OpenVAF-R', [{'role': 'simulator', 'name': 'ngspice', 'version': '41'}]),
            ('alias-compiler', 'openvaf-r', [{'role': 'compiler', 'name': 'OpenVAF-R', 'version': '0.8.7'}]),
        ):
            data['objects'].append({
                'id': name, 'version': '1', 'kind': 'qualification', 'status': 'active',
                'review': 'approved', 'scope': 'alias probe', 'backend': backend,
                'requirements': [requirement_ref], 'dependencies': [requirement_ref],
                'toolchain': toolchain,
            })
            data['current'][name] = '1'
        projected, _text = checked(Registry(data))
        row = requirement(projected, 'fixture-requirement')
        ngspice = row['backends']['ngspice']
        self.assertEqual(ngspice['toolchain']['state'], 'unknown')
        self.assertNotIn('9.9.9', json.dumps(ngspice))
        self.assertNotIn('41', json.dumps(ngspice['toolchain']))
        self.assertNotIn('0.8.7', json.dumps(ngspice))
        for name in ('spectre', 'gnucap', 'evas'):
            self.assertEqual(row['backends'][name]['toolchain']['state'], 'unknown')
            self.assertEqual(row['backends'][name]['records'], [])
        unassigned = {record['qualification']['backend'] for record in row['unassigned_backend_records']}
        self.assertEqual(unassigned, {'OpenVAF', 'ngspice + OpenVAF-R', 'openvaf-r'})
        self.assertTrue(all(record['qualification']['current_qualified'] for record in ngspice['records']))
        self.assertEqual(row['requirement_support'], 'not_conferred')
        self.assertEqual(row['coverage_sufficiency'], 'pending')

    def test_distinct_states_are_not_collapsed(self):
        data = set_outcome(retarget(fixture(), 'evas'), 'not_run', numerical='known_nonconformance')
        projected, text = checked(Registry(data))
        record = evas_records(projected)[0]
        execution = record['executions'][0]
        self.assertEqual(execution['execution']['state'], 'not_run')
        self.assertEqual(execution['completeness']['state'], 'recorded')
        self.assertEqual(execution['completeness']['value'], True)
        self.assertEqual(execution['numerical']['state'], 'known_nonconformance')
        self.assertEqual(record['analyses'][0]['numerical']['state'], 'unknown')
        self.assertFalse(record['qualification']['current_qualified'])
        for token in ('not_run', 'known_nonconformance', 'recorded:true', 'unknown'):
            self.assertIn(token, text)
        head = text.partition('## 历史引用')[0]
        for line in head.splitlines():
            if line.startswith('|') and not line.startswith('| ---') and not line.startswith('| 后端'):
                cells = [part.strip() for part in line.strip().strip('|').split('|')]
                self.assertTrue(all(cell not in {'', '✓', '✗', 'x', 'X'} for cell in cells))

    def test_preview_writes_both_views_and_render_delegates(self):
        registry = Registry(fixture())
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            paths = write_preview(registry, directory, historical={
                'identity': 'fixture-history', 'source': 'fixture', 'scope': 'fixture', 'nodes': [],
            })
            self.assertEqual([path.name for path in paths], ['support-facts.json', 'support.md'])
            saved = json.loads(paths[0].read_text())
            self.assertEqual(saved['view_status'], 'preview')
            self.assertFalse(saved['adopted'])
            self.assertTrue(saved['provisional'])
            self.assertIn('not_conferred', paths[1].read_text())
            self.assertEqual(paths[0].read_text(), dumps(saved))
        seen = {}
        def fake_write(reg, directory, **kwargs):
            seen['registry'] = reg
            seen['directory'] = directory
            return [Path(directory) / 'support-facts.json', Path(directory) / 'support.md']
        original = (support_view.write_preview, render.load, render.outputs)
        support_view.write_preview = fake_write
        render.load = lambda: {'marker': 'loaded'}
        render.outputs = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('historical outputs built'))
        try:
            with self.assertRaises(SystemExit):
                render.main(['--check', '--support-preview', 'unused'])
            render.main(['--support-preview', 'preview-dir'])
        finally:
            support_view.write_preview, render.load, render.outputs = original
        self.assertEqual(seen, {'registry': {'marker': 'loaded'}, 'directory': 'preview-dir'})

    def test_requirement_content_mismatch_stays_off_the_current_requirement(self):
        data = retarget(fixture(), 'evas')
        _break_citation(data, 'consumer-a', 'fixture-requirement', ('requirements', 'dependencies'))
        projected, text = checked(Registry(data))
        evas = requirement(projected, 'fixture-requirement')['backends']['evas']
        bound = _records_by_id(evas['records'])
        self.assertIn('consumer-b', bound)
        self.assertNotIn('consumer-a', bound)
        self.assertEqual(bound['consumer-b']['execution']['value'], 'passed')
        self.assertTrue(bound['consumer-b']['qualification']['current_qualified'])
        self.assertEqual(evas['execution']['state'], 'records_listed')
        consumer = _records_by_id(projected['unbound_qualifications'])['consumer-a']
        self.assertFalse(consumer['qualification']['current_qualified'])
        self.assertTrue(any('fixture-requirement' in gap for gap in consumer['qualification']['gaps']))
        cited = [ref for ref in consumer['unbound_references'] if ref['id'] == 'fixture-requirement']
        self.assertEqual(cited, [{
            'id': 'fixture-requirement',
            'version': '1',
            'sha256': '0' * 64,
            'kind': 'requirement',
            'bound': False,
        }])
        self.assertEqual(consumer['execution']['value'], 'passed')
        self.assertIn('未绑定引用：kind requirement `fixture-requirement`', text)
        self.assertIn('bound false', text)

    def test_execution_content_mismatch_does_not_borrow_current_observation(self):
        data = retarget(fixture(), 'evas')
        execution = by_id(data, 'fixture-execution')
        execution['numerical'] = 'borrowed-numerical'
        execution['toolchain'] = [{'role': 'simulator', 'name': 'EVAS', 'version': 'borrowed-toolchain'}]
        data = refresh(data)
        _break_citation(data, 'consumer-a', 'fixture-execution', ('dependencies',))
        projected, text = checked(Registry(data))
        evas = requirement(projected, 'fixture-requirement')['backends']['evas']
        bound = _records_by_id(evas['records'])
        self.assertEqual(set(bound), {'consumer-a', 'consumer-b'})
        self.assertEqual(evas['execution']['state'], 'records_listed')
        other = bound['consumer-b']
        self.assertEqual(other['execution']['value'], 'passed')
        self.assertEqual(other['executions'][0]['numerical']['value'], 'borrowed-numerical')
        self.assertIn('borrowed-toolchain', json.dumps(other['toolchain']))
        self.assertTrue(other['qualification']['current_qualified'])
        consumer = bound['consumer-a']
        self.assertFalse(consumer['qualification']['current_qualified'])
        self.assertEqual(consumer['execution'], {'state': 'unknown'})
        self.assertEqual(consumer['executions'], [])
        self.assertEqual(consumer['numerical'], {'state': 'unknown'})
        self.assertEqual(consumer['toolchain'], {'state': 'unknown', 'components': []})
        self.assertEqual(consumer['analyses'][0]['outcome']['value'], 'accepted')
        self.assertNotIn('borrowed-toolchain', json.dumps(consumer))
        self.assertNotIn('borrowed-numerical', json.dumps(consumer))
        self.assertTrue(any(gap.endswith('dependency content changed: fixture-execution')
                            for gap in consumer['qualification']['gaps']))
        self.assertEqual(consumer['unbound_references'], [{
            'id': 'fixture-execution',
            'version': '1',
            'sha256': '0' * 64,
            'kind': 'execution',
            'bound': False,
        }])
        self.assertTrue(all('bound' not in item for item in consumer['locatable_versions']))
        located = [item for item in consumer['locatable_versions'] if item['id'] == 'fixture-execution']
        self.assertTrue(located)
        self.assertNotEqual(located[0]['sha256'], '0' * 64)
        self.assertIn('未绑定引用：kind execution `fixture-execution`', text)

    def test_analysis_content_mismatch_does_not_borrow_outcome(self):
        data = retarget(fixture(), 'evas')
        by_id(data, 'fixture-analysis')['numerical'] = 'borrowed-analysis-numerical'
        data = refresh(data)
        _break_citation(data, 'consumer-a', 'fixture-analysis', ('dependencies',))
        projected, _text = checked(Registry(data))
        bound = _records_by_id(evas_records(projected))
        consumer = bound['consumer-a']
        other = bound['consumer-b']
        self.assertEqual(consumer['analyses'], [])
        self.assertEqual(consumer['execution']['value'], 'passed')
        self.assertNotIn('borrowed-analysis-numerical', json.dumps(consumer))
        self.assertEqual(consumer['unbound_references'], [{
            'id': 'fixture-analysis',
            'version': '1',
            'sha256': '0' * 64,
            'kind': 'analysis',
            'bound': False,
        }])
        self.assertEqual(other['analyses'][0]['outcome']['value'], 'accepted')
        self.assertEqual(other['analyses'][0]['numerical']['value'], 'borrowed-analysis-numerical')
        self.assertFalse(consumer['qualification']['current_qualified'])
        self.assertTrue(other['qualification']['current_qualified'])
        self.assertEqual(requirement(projected, 'fixture-requirement')['backends']['evas']['execution']['state'],
                         'records_listed')

    def test_review_content_mismatch_does_not_borrow_evidence(self):
        data = retarget(fixture(), 'evas')
        _break_citation(data, 'consumer-a', 'fixture-review', ('dependencies',))
        projected, _text = checked(Registry(data))
        bound = _records_by_id(evas_records(projected))
        consumer = bound['consumer-a']
        other = bound['consumer-b']
        consumer_ids = [item['id'] for item in consumer['evidence'].get('items') or []]
        other_ids = [item['id'] for item in other['evidence'].get('items') or []]
        self.assertNotIn('review-approval', consumer_ids)
        self.assertIn('review-approval', other_ids)
        self.assertIn('execution-raw', consumer_ids)
        self.assertEqual(consumer['execution']['value'], 'passed')
        self.assertEqual(consumer['unbound_references'], [{
            'id': 'fixture-review',
            'version': '1',
            'sha256': '0' * 64,
            'kind': 'review',
            'bound': False,
        }])
        self.assertFalse(consumer['qualification']['current_qualified'])
        self.assertTrue(other['qualification']['current_qualified'])
        self.assertTrue(all(item['bound'] is True for item in consumer['evidence']['items']))


    def test_adoption_labels_confer_no_support(self):
        projected, text = checked(Registry(fixture()))
        self.assertEqual(projected['view_status'], 'current-default')
        self.assertEqual((projected['adopted'], projected['provisional']), (True, False))
        self.assertEqual(projected['denominators']['current_requirement_support_conferred'], 0)
        self.assertTrue(all(item['requirement_support'] == 'not_conferred' for item in projected['requirements']))
        self.assertIn('adopted: true', text)
        self.assertNotIn('暂定', text)
        for field, value in (('adopted', False), ('provisional', True), ('adoption_meaning', ''), ('view_status', 'other')):
            changed = copy.deepcopy(projected)
            changed[field] = value
            self.assertIn('projection adoption labels inconsistent', audit(changed))
        conferred = copy.deepcopy(projected)
        conferred['denominators']['current_requirement_support_conferred'] = 1
        self.assertIn('requirement support was conferred', audit(conferred))
        preview = document(Registry(fixture()), status='preview')
        preview_text = markdown(preview)
        self.assertEqual(audit(preview) + audit_markdown(preview, preview_text), [])
        self.assertEqual((preview['adopted'], preview['provisional']), (False, True))
        self.assertIn('markdown view status diverged', audit_markdown(projected, preview_text))

    def test_multi_source_toolchain_versions_are_listed(self):
        for backend, simulator, compiler in (('ngspice', 'ngspice', 'OpenVAF-R'), ('gnucap', 'Gnucap', 'modelgen-verilog')):
            data = retarget(fixture(), backend)
            by_id(data, 'fixture-execution')['toolchain'] = [{'role': 'simulator', 'name': simulator, 'version': 'sim-12345'}]
            for name in ('consumer-a', 'consumer-b'):
                by_id(data, name)['toolchain'] = [{'role': 'compiler', 'name': compiler, 'version': 'cc-67890'}]
            projected, text = checked(Registry(refresh(data)))
            records = requirement(projected, 'fixture-requirement')['backends'][backend]['records']
            self.assertTrue(records)
            self.assertTrue(all(record['toolchain']['state'] == 'records_listed' for record in records))
            for token in (f'{simulator}/simulator@sim-12345', f'{compiler}/compiler@cc-67890'):
                self.assertIn(token, text)
            self.assertIn('markdown dropped toolchain component', audit_markdown(projected, text.replace('sim-12345', 'sim-x')))

    def test_contract_fields_are_displayed_or_unknown(self):
        data = fixture()
        target = by_id(data, 'fixture-requirement')
        target['allowed_behavior'] = 'fixture allowed behavior'
        target['conditions'] = ['fixture condition x > -1']
        target.pop('observables', None)
        projected, text = checked(Registry(refresh(data)))
        self.assertIn('原文 allowed_behavior："fixture allowed behavior"', text)
        self.assertIn('原文 conditions：["fixture condition x > -1"]', text)
        self.assertIn('原文 observables：unknown', text)
        self.assertIn('markdown dropped requirement contract field allowed_behavior',
                      audit_markdown(projected, text.replace('fixture allowed behavior', 'other')))

    def test_one_registration_change_reaches_default_json_and_markdown(self):
        data = retarget(fixture(), 'evas')
        first = Registry(copy.deepcopy(data))
        by_id(data, 'checker')['status'] = 'revoked'
        second = Registry(data)
        node = {
            'id': 'sin',
            'title': 'sin',
            'chapter': '语言',
            'status': 'waiting',
            'review': 'pending',
            'gap': 'historical gap text',
            'evidence': 'evas/docs/COMPARISON.md#支持矩阵',
            'depends_on': [],
        }
        view = {
            'nodes': [node],
            'historical_view': {
                'identity': 'historical-comparison-import-f210ebd5',
                'source': 'evas/docs/COMPARISON.md',
                'scope': 'Historical transcription; not qualification for current main',
                'role': 'historical-index',
                'in_current_requirement_denominator': False,
            },
        }
        original_load = render.load
        original_normative = render.normative_markdown
        try:
            render.normative_markdown = lambda reg: 'normative\n'
            render.load = lambda: first
            before = render.outputs(view)
            render.load = lambda: second
            after = render.outputs(view)
            pair = render.support_pair(second)
        finally:
            render.load = original_load
            render.normative_markdown = original_normative

        def pick(files, name):
            return next(value for path, value in files.items() if path.name == name)

        self.assertEqual(pick(after, 'support-facts.json'), pair[0])
        self.assertEqual(pick(after, 'support.md'), pair[1])
        self.assertNotEqual(pick(before, 'support-facts.json'), pick(after, 'support-facts.json'))
        self.assertNotEqual(pick(before, 'support.md'), pick(after, 'support.md'))
        for value in (pick(after, 'support-facts.json'), pick(after, 'support.md')):
            self.assertIn('revoked', value)
            self.assertIn('not_conferred', value)
        comparison = pick(after, 'comparison.md')
        self.assertIn('历史视图身份：`historical-comparison-import-f210ebd5`', comparison)
        self.assertIn('原输入：`evas/docs/COMPARISON.md`', comparison)
        self.assertIn('当前要求分母只计登记中的当前要求。', comparison)
        self.assertIn('等待跑', comparison)
        self.assertNotIn('current_requirements:', comparison)
        page = next(value for path, value in after.items() if path.as_posix().endswith('sin/README.md'))
        self.assertIn('historical-comparison-import-f210ebd5', page)
        self.assertIn('historical gap text', page)
        self.assertIn('evas/docs/COMPARISON.md#支持矩阵', page)
        self.assertIn('当前要求分母只计登记中的当前要求。', page)

    def test_duplicate_contract_line_must_remain_in_each_requirement(self):
        projected, text = checked(bare_registry())
        headings = [line for line in text.splitlines() if line.startswith('### ')]
        self.assertGreaterEqual(len(headings), 2)
        self.assertEqual(audit_markdown(projected, text), [])
        for key in ('allowed_behavior', 'conditions', 'observables'):
            matches = [line for line in text.splitlines() if line.startswith('原文 ' + key + '：')]
            self.assertGreaterEqual(len(matches), 2, key)
            self.assertEqual(set(matches), {matches[0]}, key)
            changed = _drop_line_under_heading(text, headings[0], matches[0])
            self.assertIn(matches[0], changed.splitlines())
            self.assertIn('markdown dropped requirement contract field ' + key,
                          audit_markdown(projected, changed))

    def test_toolchain_source_is_not_covered_by_another_record(self):
        data = retarget(fixture(), 'ngspice')
        by_id(data, 'fixture-execution')['toolchain'] = [
            {'role': 'simulator', 'name': 'ngspice', 'version': 'sim-12345'}]
        for name in ('consumer-a', 'consumer-b'):
            by_id(data, name)['toolchain'] = [
                {'role': 'compiler', 'name': 'OpenVAF-R', 'version': 'cc-67890'}]
        projected, text = checked(Registry(refresh(data)))
        self.assertEqual(audit_markdown(projected, text), [])
        tool_lines = [line for line in text.splitlines() if line.startswith('工具链：records_listed:')]
        self.assertGreaterEqual(len(tool_lines), 2)
        self.assertIn('consumer-a@1: ', tool_lines[0])
        dropped_source = text.replace(tool_lines[0] + '\n', '', 1)
        self.assertIn('OpenVAF-R/compiler@cc-67890', dropped_source)
        self.assertIn('markdown dropped toolchain component', audit_markdown(projected, dropped_source))
        dropped_owner = text.replace('consumer-a@1: ', '', 1)
        self.assertNotIn('consumer-a@1: ', dropped_owner)
        self.assertIn('OpenVAF-R/compiler@cc-67890', dropped_owner)
        self.assertIn('markdown dropped toolchain component', audit_markdown(projected, dropped_owner))

    def test_markdown_status_requires_view_status_and_provisional(self):
        projected, text = checked(Registry(fixture()))
        self.assertEqual(audit_markdown(projected, text), [])
        preview = document(Registry(fixture()), status='preview')
        preview_text = markdown(preview)
        self.assertEqual(audit(preview) + audit_markdown(preview, preview_text), [])
        replacements = (
            ('view_status: current-default', 'view_status: preview'),
            ('provisional: false', 'provisional: true'),
        )
        for old, new in replacements:
            changed = text.replace(old, new, 1)
            self.assertIn('# 当前要求的四后端事实', changed)
            self.assertIn('adopted: true', changed)
            self.assertIn('markdown view status diverged', audit_markdown(projected, changed))
            dropped = text.replace(old + '\n', '', 1)
            self.assertIn('markdown view status diverged', audit_markdown(projected, dropped))

    def test_records_stay_with_their_requirement_and_header_status_is_unique(self):
        registry = independent_registry()
        projected = document(registry)
        text = markdown(projected)
        self.assertEqual(audit(projected) + audit_markdown(projected, text), [])

        pre, body = text.split('## 当前要求\n\n', 1)
        body, post = body.split('## 未绑定当前要求的资格', 1)
        sections = [item for item in re.split(r'(?=^### )', body, flags=re.M) if item.strip()]
        self.assertEqual(len(sections), 2)
        first, second = sections
        self.assertIn('bare-requirement', first.splitlines()[0])
        record_start = second.index('资格记录：')
        record_block = second[record_start:]
        chunks = [item for item in re.split(r'(?=^资格记录：)', record_block, flags=re.M) if item.strip()]
        self.assertEqual(len(chunks), 2)
        line = next(item for item in text.splitlines() if item.startswith('工具链：'))
        current = '## 当前要求\n\n'
        unbound = '## 未绑定当前要求的资格'
        variants = (
            ('requirement-order-only', pre + current + ''.join(reversed(sections)) + unbound + post, False),
            ('record-order-only', text.replace(record_block, ''.join(reversed(chunks)), 1), False),
            ('move-all-records-to-wrong-requirement',
             pre + current + first + record_block + second[:record_start] + unbound + post, True),
            ('duplicate-all-records', pre + current + first + second + record_block + unbound + post, True),
            ('move-records-to-unbound-section',
             pre + current + first + second[:record_start] + unbound + '\n\n' + record_block + post, True),
            ('duplicate-toolchain-line', text.replace(line, line + '\n' + line, 1), True),
            ('contradictory-toolchain-line',
             text.replace(line, line + '\n工具链：consumer-a@1: OpenVAF-R/compiler@wrong-version', 1), True),
            ('wrong-toolchain-line-only',
             text.replace(line, '工具链：consumer-a@1: OpenVAF-R/compiler@wrong-version', 1), True),
            ('duplicate-requirement-section', pre + current + first + first + second + unbound + post, True),
        )
        for name, changed, expect_reject in variants:
            self.assertNotEqual(changed, text, name)
            errors = audit_markdown(projected, changed)
            if expect_reject:
                self.assertTrue(errors, name)
            else:
                self.assertEqual(errors, [], name)
        self.assertIn('markdown extra qualification record', audit_markdown(
            projected, variants[2][1]))
        self.assertIn('markdown qualification record missing', audit_markdown(
            projected, variants[2][1]))
        self.assertIn('markdown extra toolchain line', audit_markdown(projected, variants[5][1]))
        self.assertIn('markdown extra toolchain line', audit_markdown(projected, variants[6][1]))
        self.assertIn('markdown dropped toolchain component', audit_markdown(projected, variants[7][1]))
        self.assertIn('markdown requirement headings', audit_markdown(projected, variants[8][1]))

        for status in ('current-default', 'preview'):
            facts = document(registry, status=status)
            rendered = markdown(facts)
            self.assertEqual(audit(facts) + audit_markdown(facts, rendered), [])
            wrong = 'preview' if status == 'current-default' else 'current-default'
            changed = rendered.replace('\n\n', '\nview_status: ' + wrong + '\n', 1)
            self.assertNotEqual(changed, rendered, status)
            self.assertIn('markdown view status diverged', audit_markdown(facts, changed))


    def test_markdown_is_accepted_only_as_the_generated_view_up_to_two_reorderings(self):
        registry = independent_registry()
        generated = Path(__file__).resolve().parent / 'generated'
        real = json.loads((generated / 'support-facts.json').read_text())
        subjects = [
            ('fixture-current-default', document(registry), True),
            ('fixture-preview', document(registry, status='preview'), True),
            ('real-current-default', real, False),
        ]
        total = {}
        for label, facts, full in subjects:
            text = markdown(facts)
            if label == 'real-current-default':
                self.assertEqual(text, (generated / 'support.md').read_text())
            self.assertEqual(audit(facts) + audit_markdown(facts, text), [], label)
            for kind, name, changed, expect_reject in markdown_variant_cases(facts, text, full=full):
                if changed == text:
                    self.fail(f'{label} {kind} {name}: variant equals the generated text')
                errors = audit_markdown(facts, changed)
                counts = total.setdefault(kind, [0, 0])
                counts[0] += 1
                counts[1] += bool(errors) == expect_reject
                if bool(errors) != expect_reject:
                    self.fail(f'{label} {kind} {name}: expected reject={expect_reject}, got {errors}')
                if expect_reject:
                    self.assertTrue(any(error.startswith('markdown differs from the generated view at line')
                                        for error in errors), (label, kind, name, errors))
        # Every class was generated and every variant behaved as required.
        self.assertTrue(all(done == count for count, done in total.values()), total)
        for kind in MARKDOWN_VARIANT_KINDS:
            self.assertGreater(total[kind][0], 0, kind)

    def test_blank_lines_in_a_record_run_move_only_with_the_block_that_owns_them(self):
        """Four records, every order, the one separator after every position: a separator stays where the
        generated view has it, or travels with the block that owns it, and nowhere else."""
        facts = document(independent_registry())
        records = requirement(facts, 'fixture-requirement')['backends']['ngspice']['records']
        for number in (3, 4):
            extra = copy.deepcopy(records[0])
            extra['qualification']['id'] = f'extra-record-{number}'
            records.append(extra)
        text = markdown(facts)
        self.assertEqual(audit_markdown(facts, text), [])
        lines = text.split('\n')
        first = next(i for i, line in enumerate(lines) if line.startswith('资格记录：'))
        end = next(i for i in range(first, len(lines)) if lines[i] == '')
        starts = [i for i in range(first, end) if lines[i].startswith('资格记录：')]
        blocks = [lines[a:b] for a, b in zip(starts, starts[1:] + [end])]
        self.assertEqual(len(blocks), 4)
        counts = {True: 0, False: 0}
        for order in itertools.permutations(range(len(blocks))):
            for slot in range(len(blocks)):
                rebuilt = []
                for position, index in enumerate(order):
                    rebuilt.extend(blocks[index])
                    if position == slot:
                        rebuilt.append('')
                changed = lines[:first] + rebuilt + lines[end + 1:]
                if changed == lines:
                    continue
                legal = slot == len(blocks) - 1 or order[slot] == len(blocks) - 1
                counts[legal] += 1
                self.assertEqual(not audit_markdown(facts, '\n'.join(changed)), legal, (order, slot))
        # 23 orders keep the separator last; 3 slots x 6 orders carry it with the block that owned it.
        self.assertEqual(counts, {True: 23 + 18, False: 95 - 41})
        # With the order unchanged, any other blank placement differs: moved, doubled, dropped or whitespace-only.
        for slot in range(len(blocks) - 1):
            moved = lines[:first] + [x for position, block in enumerate(blocks) for x in block + ([''] if position == slot else [])] + lines[end + 1:]
            doubled = lines[:end] + ['', ''] + lines[end + 1:]
            spaced = lines[:end] + [' '] + lines[end + 1:]
            for changed in (moved, doubled, spaced):
                self.assertTrue(audit_markdown(facts, '\n'.join(changed)))
        self.assertTrue(audit_markdown(facts, '\n'.join(lines[:end] + lines[end + 1:])))

    def test_difference_report_names_the_first_changed_line(self):
        projected = document(independent_registry())
        text = markdown(projected)
        lines = text.split('\n')
        index = next(i for i, line in enumerate(lines) if line.startswith('工具链：'))
        changed = lines[:index] + ['  ' + lines[index]] + lines[index + 1:]
        [error] = [e for e in audit_markdown(projected, '\n'.join(changed)) if e.startswith('markdown differs')]
        self.assertIn(f'line {index + 1} ', error)
        self.assertIn(repr(lines[index]), error)
        self.assertIn(repr('  ' + lines[index]), error)
        self.assertIn('<end of text>', _first_difference_for(projected, text + '\nextra'))
        self.assertIn('actual <end of text>', _first_difference_for(projected, text[:-1]))


def _drop_line_under_heading(text, heading, line):
    newline = '\n' if text.endswith('\n') else ''
    lines = text.splitlines()
    start = lines.index(heading)
    end = next((index for index in range(start + 1, len(lines))
                if lines[index].startswith('### ') or lines[index].startswith('## ')), len(lines))
    section = lines[start:end]
    if line not in section:
        raise AssertionError('line not in section ' + heading)
    section.remove(line)
    return '\n'.join(lines[:start] + section + lines[end:]) + newline


def _break_citation(data, owner, ref_id, fields):
    for field in fields:
        for ref in by_id(data, owner).get(field) or []:
            if isinstance(ref, dict) and ref.get('id') == ref_id:
                ref['sha256'] = '0' * 64


def _records_by_id(records):
    return {record['qualification']['id']: record for record in records}


if __name__ == '__main__':
    unittest.main()
