"""Project current requirement facts for the four project backends.

The projection reads Registry.current and qualification_gaps. It does not score
coverage, confer requirement support, or read historical comparison cells as
current results. A missing toolchain version stays unknown.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from catalog import BACKENDS, NODES
from registry import digest

EXPECTED_BACKENDS = ('spectre', 'ngspice', 'gnucap', 'evas')
HEADINGS = {
    'spectre': 'Spectre',
    'ngspice': 'ngspice + OpenVAF-R',
    'gnucap': 'Gnucap + modelgen-verilog',
    'evas': 'EVAS',
}
DISTINCT_STATES = ('not_run', 'missing_evidence', 'unsupported', 'known_nonconformance')
PRESERVE_FIELDS = (
    'status', 'review', 'gap', 'budget', 'allowed_behavior', 'conditions',
    'observables', 'required_boundaries', 'source_locations', 'language_profile',
    'coverage_sufficiency',
)
HISTORICAL_FIELDS = (
    'id', 'title', 'chapter', 'label', 'status', 'review', 'evidence',
    'results', 'depends_on', 'gap', 'requirement', 'requirements',
)
FORBIDDEN_CELLS = {'', '✓', '✗', '✔', '✘', 'x', 'X', '√', '-', '—'}
LIMITS = (
    '默认视图与预览都由登记生成；adopted 只表示当前默认视图身份，不是新的项目决定，也不授予要求级支持或科学资格。',
    'pending、not_conferred 表示待审核或未取得资格，不等于 unsupported（不支持）或 known_nonconformance（已知不符合）。',
    '覆盖充分性未定义时保持 pending；单个案例资格不解释成要求或能力通过。',
    '工具链版本只来自已绑定记录上的显式 toolchain 列表；没有该列表时为 unknown。',
    'catalog.BACKENDS 的四个键不接收协议别名；无法精确对应的后端身份单独列出。',
    '历史成绩保持原身份，不进入当前要求分母。',
)
VIEW_STATUSES = {
    'current-default': {
        'title': '# 当前要求的四后端事实',
        'note': 'adopted 只表示这是当前默认支持视图，不是新的项目决定，也不授予任何资格。',
        'meaning': 'default current support view only; not a project decision; confers no requirement-level support or scientific qualification',
    },
    'preview': {
        'title': '# 预览：当前要求的四后端事实',
        'note': '预览输出不是当前默认支持视图，adopted 为 false，也不授予任何资格。',
        'meaning': 'preview output only; not the current default support view; confers no requirement-level support or scientific qualification',
    },
}
CONTRACT_FIELDS = ('allowed_behavior', 'conditions', 'observables')


class SupportViewError(ValueError):
    pass


if tuple(BACKENDS) != EXPECTED_BACKENDS:
    raise SupportViewError(
        'catalog.BACKENDS is not the fixed project four; refusing to merge aliases')


def dumps(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + '\n'


def _columns():
    return [(name, HEADINGS[name]) for name in BACKENDS]


def _fact(obj, key):
    if not isinstance(obj, dict) or key not in obj or obj[key] is None:
        return {'state': 'unknown'}
    value = obj[key]
    if isinstance(value, str) and value in DISTINCT_STATES:
        return {'state': value, 'value': value}
    return {'state': 'recorded', 'value': value}


def _toolchain(obj):
    if not isinstance(obj, dict) or 'toolchain' not in obj or obj['toolchain'] is None:
        return {'state': 'unknown', 'components': []}
    raw = obj['toolchain']
    if not isinstance(raw, list):
        return {'state': 'recorded', 'components': [], 'unparsed': raw}
    components = []
    for item in raw:
        if not isinstance(item, dict):
            components.append({'name': 'unknown', 'role': 'unknown', 'version': 'unknown',
                               'unparsed': item})
            continue
        version = item.get('version')
        components.append({
            'name': item.get('name') if isinstance(item.get('name'), str) and item.get('name') else 'unknown',
            'role': item.get('role') if isinstance(item.get('role'), str) and item.get('role') else 'unknown',
            'version': version if isinstance(version, str) and version else 'unknown',
        })
    return {'state': 'recorded', 'components': components}


def _record_toolchain(qualification, executions):
    found = []
    for obj in [qualification, *executions]:
        parsed = _toolchain(obj)
        if parsed['state'] == 'unknown':
            continue
        found.append({'owner': obj['id'], 'version': obj['version'], **parsed})
    if not found:
        return {'state': 'unknown', 'components': []}
    if len(found) == 1:
        return found[0]
    return {'state': 'records_listed', 'components': found}


def _column_name(value):
    if isinstance(value, str) and value in BACKENDS:
        return value
    return None


def _objects(registry, kind):
    rows = []
    for name, version in sorted(registry.data['current'].items()):
        obj = registry.objects[(name, version)]
        if obj['kind'] == kind:
            rows.append(obj)
    return rows


def _versions(registry, ids):
    """Object versions reached for navigation. Absence of a bound field means this is not a content binding."""
    rows = []
    for obj in registry.objects.values():
        if obj['id'] in ids:
            rows.append({
                'id': obj['id'],
                'version': obj['version'],
                'sha256': digest(obj),
                'kind': obj['kind'],
                'selected': registry.data['current'].get(obj['id']) == obj['version'],
            })
    return sorted(rows, key=lambda item: (item['id'], str(item['version'])))


def _reachable_ids(registry, obj, seen=None):
    seen = set() if seen is None else seen
    key = (obj['id'], obj['version'])
    if key in seen:
        return set()
    seen.add(key)
    found = {obj['id']}
    for ref in obj.get('dependencies') or []:
        if not isinstance(ref, dict):
            continue
        target = registry.objects.get((ref.get('id'), ref.get('version')))
        if target is not None:
            found |= _reachable_ids(registry, target, seen)
    return found


_FACT_KINDS = ('requirement', 'execution', 'analysis', 'review')


def _lookup(registry, ref):
    if not isinstance(ref, dict):
        return None
    return registry.objects.get((ref.get('id'), ref.get('version')))


def _content_bound(registry, ref):
    """Return the object only when id, version, and sha256 all match."""
    target = _lookup(registry, ref)
    if target is None or ref.get('sha256') != digest(target):
        return None
    return target


def _kind_deps(registry, obj, kind):
    found = []
    for ref in obj.get('dependencies') or []:
        target = _content_bound(registry, ref)
        if target is not None and target.get('kind') == kind:
            found.append(target)
    return found


def _unbound_fact_refs(registry, obj):
    """Keep mismatched requirement, execution, analysis, and review citations.

    The citation is the referenced triple. It does not copy the current object's
    execution, numerical, or toolchain facts.
    """
    rows = []
    seen = set()

    def add(ref):
        if not isinstance(ref, dict):
            return
        target = _lookup(registry, ref)
        if target is None or target.get('kind') not in _FACT_KINDS:
            return
        if ref.get('sha256') == digest(target):
            return
        item = {
            'id': ref.get('id'),
            'version': ref.get('version'),
            'sha256': ref.get('sha256'),
            'kind': target.get('kind'),
            'bound': False,
        }
        key = (item['kind'], item['id'], item['version'], item['sha256'])
        if key in seen:
            return
        seen.add(key)
        rows.append(item)

    for ref in obj.get('requirements') or []:
        add(ref)
    for ref in obj.get('dependencies') or []:
        add(ref)
    return rows


def _source_item(registry, ref, role):
    if not isinstance(ref, dict):
        return None
    target = registry.objects.get((ref.get('id'), ref.get('version')))
    if target is None or target.get('kind') != 'source':
        return None
    path = target.get('path')
    origin = target.get('origin')
    return {
        'role': role,
        'id': ref.get('id'),
        'version': ref.get('version'),
        'sha256': ref.get('sha256'),
        'bound': ref.get('sha256') == digest(target),
        'path': path if isinstance(path, str) and path else 'unknown',
        'origin': origin if isinstance(origin, str) and origin else 'unknown',
        'gap': target.get('gap') if 'gap' in target else None,
    }


def _evidence(registry, executions, review, gaps):
    items = []
    seen = set()
    def add(ref, role):
        item = _source_item(registry, ref, role)
        if item is None:
            return
        key = (item['role'], item['id'], item['version'], item['sha256'])
        if key in seen:
            return
        seen.add(key)
        items.append(item)
    for execution in executions:
        add(execution.get('raw_report'), 'execution.raw_report')
    if review is not None:
        add(review.get('evidence'), 'review.evidence')
    evidence_gaps = [gap for gap in gaps
                     if 'evidence' in gap or 'source file missing' in gap]
    if evidence_gaps:
        return {'state': 'missing_evidence', 'items': items, 'gaps': evidence_gaps}
    if items:
        return {'state': 'recorded', 'items': items}
    return {'state': 'unknown', 'items': []}


def _one_or_listed(rows, selector):
    if not rows:
        return {'state': 'unknown'}
    facts = [selector(row) for row in rows]
    if len(facts) == 1:
        return facts[0]
    if all(fact['state'] == 'unknown' for fact in facts):
        return {'state': 'unknown'}
    return {'state': 'records_listed', 'values': facts}


def _language(registry, requirement):
    named = requirement.get('language_profile')
    if not isinstance(named, str) or not named:
        return {'requirement_field': 'unknown', 'resolved': 'unknown'}
    profile = registry.data.get('language_profile')
    if isinstance(profile, dict) and profile.get('id') == named:
        version = profile.get('version')
        base = profile.get('base')
        return {
            'requirement_field': named,
            'resolved': {
                'id': profile.get('id'),
                'version': version if version is not None else 'unknown',
                'base': base if isinstance(base, str) and base else 'unknown',
                'selected_changes': list(profile.get('selected_changes') or []),
            },
        }
    return {'requirement_field': named, 'resolved': 'unknown'}


def _referenced(registry, requirement):
    rows = []
    for ref in requirement.get('dependencies') or []:
        if not isinstance(ref, dict):
            rows.append({'id': 'unknown', 'version': 'unknown', 'sha256': 'unknown',
                         'kind': 'unknown', 'bound': False})
            continue
        target = registry.objects.get((ref.get('id'), ref.get('version')))
        path = target.get('path') if target is not None else None
        origin = target.get('origin') if target is not None else None
        rows.append({
            'id': ref.get('id'),
            'version': ref.get('version'),
            'sha256': ref.get('sha256'),
            'kind': target.get('kind') if target is not None else 'unknown',
            'bound': target is not None and ref.get('sha256') == digest(target),
            'path': path if isinstance(path, str) and path else 'unknown',
            'origin': origin if isinstance(origin, str) and origin else 'unknown',
            'gap': target.get('gap') if target is not None and 'gap' in target else None,
            'status': target.get('status') if target is not None else 'unknown',
        })
    return rows


def _source_fields(requirement):
    return {key: requirement[key] for key in PRESERVE_FIELDS if key in requirement}


def _qualification_record(registry, qualification):
    gaps = registry.qualification_gaps(qualification['id'], historical=False)
    historical_gaps = registry.qualification_gaps(qualification['id'], historical=True)
    executions = _kind_deps(registry, qualification, 'execution')
    analyses = _kind_deps(registry, qualification, 'analysis')
    reviews = _kind_deps(registry, qualification, 'review')
    review = reviews[0] if len(reviews) == 1 else None
    scope = qualification.get('scope')
    backend = qualification.get('backend') if 'backend' in qualification else 'unknown'
    record = {
        'qualification': {
            'id': qualification['id'],
            'version': qualification['version'],
            'sha256': digest(qualification),
            'scope': scope if isinstance(scope, str) and scope else 'unknown',
            'backend': backend,
            'status': qualification.get('status'),
            'review': qualification.get('review'),
            'gap': qualification.get('gap') if 'gap' in qualification else None,
            'current_qualified': registry.qualified(qualification['id'], historical=False),
            'gaps': gaps,
            'historical_query': {
                'qualified': registry.qualified(qualification['id'], historical=True),
                'gaps': historical_gaps,
                'counts_as_current_support': False,
            },
            'confers_requirement_support': False,
        },
        'executions': [{
            'id': execution['id'],
            'version': execution['version'],
            'sha256': digest(execution),
            'backend': execution.get('backend') if 'backend' in execution else 'unknown',
            'execution': _fact(execution, 'outcome'),
            'completeness': _fact(execution, 'complete'),
            'numerical': _fact(execution, 'numerical'),
        } for execution in executions],
        'analyses': [{
            'id': analysis['id'],
            'version': analysis['version'],
            'sha256': digest(analysis),
            'outcome': _fact(analysis, 'outcome'),
            'numerical': _fact(analysis, 'numerical'),
        } for analysis in analyses],
        'toolchain': _record_toolchain(qualification, executions),
        'execution': _one_or_listed(executions, lambda execution: _fact(execution, 'outcome')),
        'completeness': _one_or_listed(executions, lambda execution: _fact(execution, 'complete')),
        'numerical': _one_or_listed([*executions, *analyses], lambda obj: _fact(obj, 'numerical')),
        'evidence': _evidence(registry, executions, review, gaps),
        'locatable_versions': _versions(registry, _reachable_ids(registry, qualification)),
        'column': _column_name(backend),
    }
    unbound_refs = _unbound_fact_refs(registry, qualification)
    if unbound_refs:
        record['unbound_references'] = unbound_refs
    return record


def _binds(registry, qualification, requirement):
    """True only when requirements and dependencies pin the same (id, version, sha256)."""
    if registry.data['current'].get(requirement['id']) != requirement['version']:
        return False
    pinned = digest(requirement)
    dependencies = qualification.get('dependencies') or []
    for ref in qualification.get('requirements') or []:
        if not isinstance(ref, dict):
            continue
        if ref.get('id') != requirement['id'] or ref.get('version') != requirement['version']:
            continue
        if ref.get('sha256') != pinned or ref not in dependencies:
            continue
        return True
    return False


def _claim_ids(qualification):
    found = []
    for ref in qualification.get('requirements') or []:
        if isinstance(ref, dict) and isinstance(ref.get('id'), str):
            found.append(ref['id'])
        elif isinstance(ref, str):
            found.append(ref)
    return found


def _historical_ids(node):
    found = []
    single = node.get('requirement')
    if isinstance(single, str) and single:
        found.append(single)
    elif isinstance(single, dict) and isinstance(single.get('id'), str):
        found.append(single['id'])
    for ref in node.get('requirements') or []:
        if isinstance(ref, str) and ref:
            found.append(ref)
        elif isinstance(ref, dict) and isinstance(ref.get('id'), str):
            found.append(ref['id'])
    return found


def _historical_node(node):
    copied = {key: node[key] for key in HISTORICAL_FIELDS if key in node}
    copied['in_current_denominator'] = False
    copied['counts_as_current_support'] = False
    return copied


def _scope(requirement):
    scope = requirement.get('scope')
    return scope if isinstance(scope, str) and scope else 'unknown'


def _status(requirement):
    status = requirement.get('status')
    return status if isinstance(status, str) and status else 'unknown'


def _sorted_counts(values):
    return {key: values[key] for key in sorted(values)}


def document(registry, historical=None, status='current-default'):
    """Return the fact projection. historical nodes are citations unless they name a requirement."""
    if status not in VIEW_STATUSES:
        raise SupportViewError('unknown support view status: ' + str(status))
    historical = historical or {
        'identity': 'unknown', 'source': 'unknown', 'scope': 'unknown', 'nodes': [],
    }
    requirements = _objects(registry, 'requirement')
    current_ids = {requirement['id'] for requirement in requirements}
    qualifications = _objects(registry, 'qualification')
    bound = {requirement['id']: [] for requirement in requirements}
    unbound = []
    partial = []
    for qualification in qualifications:
        record = _qualification_record(registry, qualification)
        targets = [requirement for requirement in requirements
                   if _binds(registry, qualification, requirement)]
        if targets:
            for requirement in targets:
                bound[requirement['id']].append(record)
            continue
        claimed = _claim_ids(qualification)
        if claimed:
            partial.append({'id': qualification['id'], 'version': qualification['version'],
                            'claimed_requirements': claimed})
        unbound.append(record)

    joined = []
    unjoined = []
    not_current = []
    by_requirement = {requirement['id']: [] for requirement in requirements}
    for node in historical.get('nodes') or []:
        copied = _historical_node(node)
        names = _historical_ids(node)
        if not names:
            unjoined.append(copied)
            continue
        if any(name not in current_ids for name in names):
            not_current.append({'requirement_ids': names, 'node': copied})
            continue
        item = {'requirement_ids': names, 'node': copied, 'in_current_denominator': False}
        joined.append(item)
        for name in names:
            by_requirement[name].append(copied)

    projected = []
    for requirement in requirements:
        records = bound[requirement['id']]
        columns = {}
        for name, heading in _columns():
            matched = [record for record in records if record['column'] == name]
            cell = {
                'backend': name,
                'heading': heading,
                'toolchain': {'state': 'unknown', 'components': []},
                'execution': {'state': 'unknown'},
                'completeness': {'state': 'unknown'},
                'numerical': {'state': 'unknown'},
                'qualification': {'state': 'unknown'},
                'evidence': {'state': 'unknown'},
                'records': matched,
            }
            if matched:
                for key in ('execution', 'completeness', 'numerical', 'evidence'):
                    if any(record[key]['state'] != 'unknown' for record in matched):
                        cell[key] = {'state': 'records_listed'}
                cell['qualification'] = {'state': 'records_listed'}
                if any(record['toolchain']['state'] != 'unknown' for record in matched):
                    cell['toolchain'] = {'state': 'records_listed'}
            columns[name] = cell
        scope = _scope(requirement)
        projected.append({
            'id': requirement['id'],
            'version': requirement['version'],
            'sha256': digest(requirement),
            'language': _language(registry, requirement),
            'scope': scope,
            'source_fields': _source_fields(requirement),
            'referenced_versions': _referenced(registry, requirement),
            'readiness_gaps': registry.qualification_gaps(requirement['id']),
            'readiness_note': 'readiness gaps are registry navigation, not a qualification verdict',
            'requirement_support': 'not_conferred',
            'coverage_sufficiency': 'pending',
            'coverage_note': 'coverage sufficiency is not defined for this requirement',
            'versions': _versions(registry, {requirement['id']}),
            'backends': columns,
            'unassigned_backend_records': [record for record in records if record['column'] is None],
            'historical_references': by_requirement[requirement['id']],
        })

    exceptions = []
    for record in unbound:
        qualification = record['qualification']
        exceptions.append({
            'kind': 'unbound_qualification',
            'id': qualification['id'],
            'version': qualification['version'],
            'reason': 'current qualification does not bind a current requirement',
        })
    for item in partial:
        exceptions.append({
            'kind': 'requirement_claim_not_bound',
            'id': item['id'],
            'version': item['version'],
            'claimed_requirements': item['claimed_requirements'],
            'reason': 'requirement claim is not a bound dependency of the current requirement',
        })
    for requirement in projected:
        exceptions.append({
            'kind': 'coverage_sufficiency_pending',
            'id': requirement['id'],
            'reason': requirement['coverage_note'],
        })
        for record in requirement['unassigned_backend_records']:
            exceptions.append({
                'kind': 'unassigned_backend',
                'id': record['qualification']['id'],
                'requirement': requirement['id'],
                'backend': record['qualification']['backend'],
                'reason': 'backend identity is not one of catalog.BACKENDS',
            })
        for name, cell in requirement['backends'].items():
            if cell['toolchain']['state'] == 'unknown':
                exceptions.append({
                    'kind': 'toolchain_unknown',
                    'requirement': requirement['id'],
                    'backend': name,
                    'reason': 'no explicit toolchain list on a bound record',
                })
    if unjoined:
        exceptions.append({
            'kind': 'historical_unjoined',
            'count': len(unjoined),
            'reason': 'historical nodes do not name a current requirement and are not joined',
        })
    for item in not_current:
        exceptions.append({
            'kind': 'historical_requirement_not_current',
            'id': item['node'].get('id'),
            'requirement_ids': item['requirement_ids'],
            'reason': 'historical node names a requirement outside the current set',
        })

    inventory = registry.data.get('inventory')
    source_index = len(inventory) if isinstance(inventory, list) else 'unknown'
    historical_counts = Counter(_node_status(node) for node in (historical.get('nodes') or []))
    cell_counts = Counter(cell['execution']['state']
                          for requirement in projected
                          for cell in requirement['backends'].values())
    qualification_counts = Counter()
    execution_counts = Counter()
    for record in _all_records(projected, unbound):
        qualification_counts['true' if record['qualification']['current_qualified'] else 'false'] += 1
        execution_counts[record['execution']['state']] += 1
    return {
        'schema': 'support-facts-v1',
        'view_status': status,
        'adopted': status == 'current-default',
        'provisional': status == 'preview',
        'adoption_meaning': VIEW_STATUSES[status]['meaning'],
        'denominators': {
            'current_requirements': len(projected),
            'source_index_items': source_index,
            'source_index_is_requirement_coverage': False,
            'historical_nodes': len(historical.get('nodes') or []),
            'historical_nodes_joined_to_current_requirements': len(joined),
            'current_requirement_support_conferred': 0,
        },
        'classifications': {
            'requirement_status': _sorted_counts(Counter(_status(requirement)
                                                         for requirement in requirements)),
            'historical_node_status': _sorted_counts(historical_counts),
            'backend_execution_cells': _sorted_counts(cell_counts),
            'qualification_records_current_qualified': _sorted_counts(qualification_counts),
            'record_execution_states': _sorted_counts(execution_counts),
            'exception_counts': _sorted_counts(Counter(item['kind'] for item in exceptions)),
        },
        'exceptions': exceptions,
        'requirements': projected,
        'unbound_qualifications': unbound,
        'historical': {
            'identity': historical.get('identity') if historical.get('identity') else 'unknown',
            'source': historical.get('source') if historical.get('source') else 'unknown',
            'scope': historical.get('scope') if historical.get('scope') else 'unknown',
            'joined': joined,
            'unjoined': unjoined,
            'not_current': not_current,
        },
        'limits': list(LIMITS),
    }


def _node_status(node):
    status = node.get('status')
    return status if isinstance(status, str) and status else 'unknown'


def _all_records(requirements, unbound):
    rows = list(unbound)
    for requirement in requirements:
        for cell in requirement['backends'].values():
            rows.extend(cell['records'])
        rows.extend(requirement['unassigned_backend_records'])
    return rows


def _show(fact):
    state = fact.get('state')
    if state in {'unknown', *DISTINCT_STATES}:
        return state
    if state == 'recorded':
        return 'recorded:' + json.dumps(fact.get('value'), ensure_ascii=False, sort_keys=True)
    return str(state)


def _component(item):
    return f"{item.get('name', 'unknown')}/{item.get('role', 'unknown')}@{item.get('version', 'unknown')}"


def _toolchain_source(source):
    parts = [_component(item) for item in source.get('components') or []]
    if not parts:
        parts = ['unparsed:' + json.dumps(source['unparsed'], ensure_ascii=False, sort_keys=True)] if 'unparsed' in source else [_show(source)]
    owner = source.get('owner')
    return (f"{owner}@{source.get('version', 'unknown')}: " if owner else '') + ', '.join(parts)


def _heading_blocks(text, prefix):
    """Blocks that start at prefix and stop before the next peer or section."""
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        for cursor in range(start + 1, end):
            if lines[cursor].startswith('## '):
                end = cursor
                break
        blocks.append(lines[start:end])
    return blocks


def _take_heading(blocks, heading):
    for index, block in enumerate(blocks):
        if block and block[0] == heading:
            return blocks.pop(index)
    return []


def _show_toolchain(fact):
    state = fact.get('state')
    if state == 'unknown':
        return 'unknown'
    if state == 'records_listed':
        sources = fact.get('components') or []
        if not sources:
            return 'records_listed'
        return 'records_listed: ' + '; '.join(_toolchain_source(source) for source in sources)
    return _toolchain_source(fact)


def _contract_line(key, fields):
    if key in fields:
        return f"原文 {key}：{json.dumps(fields[key], ensure_ascii=False, sort_keys=True)}"
    return f"原文 {key}：unknown"


def markdown(document):
    """Render document without collapsing distinct facts into one mark."""
    denominators = document['denominators']
    status = VIEW_STATUSES.get(document.get('view_status'), {'title': '# 未知视图状态', 'note': 'unknown view status'})
    lines = [
        status['title'],
        '',
        f"view_status: {document.get('view_status')}",
        f"adopted: {str(document.get('adopted')).lower()}",
        f"provisional: {str(document.get('provisional')).lower()}",
        status['note'],
        '',
        f"current_requirements: {denominators['current_requirements']}",
        f"source_index_items: {denominators['source_index_items']}",
        'source_index_is_requirement_coverage: false',
        '规范源索引不是要求覆盖率。',
        f"historical_nodes: {denominators['historical_nodes']}",
        f"historical_nodes_joined_to_current_requirements: {denominators['historical_nodes_joined_to_current_requirements']}",
        f"current_requirement_support_conferred: {denominators['current_requirement_support_conferred']}",
        '',
        '## 当前要求',
        '',
    ]
    for requirement in document['requirements']:
        language = requirement['language']
        lines.append(f"### {requirement['id']}@{requirement['version']}")
        lines.append('')
        lines.append(f"sha256：`{requirement['sha256']}`")
        lines.append(f"语言配置字段：{language['requirement_field']}")
        resolved = language['resolved']
        if isinstance(resolved, dict):
            lines.append(f"语言配置：`{resolved['id']}` version {resolved['version']}，基础 {resolved['base']}，选入 "
                         + ', '.join(str(item) for item in resolved['selected_changes']))
        else:
            lines.append('语言配置：unknown')
        lines.append(f"范围：{requirement['scope']}")
        lines.append(f"要求级支持：{requirement['requirement_support']}")
        lines.append(f"覆盖充分性：{requirement['coverage_sufficiency']}")
        lines.append(requirement['coverage_note'])
        lines.append(requirement['readiness_note'])
        for ref in requirement['referenced_versions']:
            lines.append(
                '引用：`{id}` version {version} sha256 {sha256} kind {kind} bound {bound} path {path} origin {origin}'.format(**ref)
            )
            if ref.get('gap'):
                lines.append(f"引用未决：{ref['gap']}")
        for key in ('gap', 'status', 'review', 'source_locations', 'required_boundaries', 'budget'):
            if key in requirement['source_fields']:
                lines.append(f"原文 {key}：{json.dumps(requirement['source_fields'][key], ensure_ascii=False, sort_keys=True)}")
        for key in CONTRACT_FIELDS:
            lines.append(_contract_line(key, requirement['source_fields']))
        for gap in requirement['readiness_gaps']:
            lines.append(f"就绪缺口：{gap}")
        lines.append('')
        lines.append('| 后端 | 工具链 | 执行 | 完整性 | 数值 | 资格 | 证据 |')
        lines.append('| --- | --- | --- | --- | --- | --- | --- |')
        for name in BACKENDS:
            cell = requirement['backends'][name]
            lines.append('| ' + ' | '.join([
                cell['heading'],
                _show_toolchain(cell['toolchain']),
                _show(cell['execution']),
                _show(cell['completeness']),
                _show(cell['numerical']),
                _show(cell['qualification']),
                _show(cell['evidence']),
            ]) + ' |')
        lines.append('')
        for cell in requirement['backends'].values():
            for record in cell['records']:
                lines.extend(_record_lines(record))
        for record in requirement['unassigned_backend_records']:
            lines.append(f"未归属后端：{record['qualification']['backend']}")
            lines.extend(_record_lines(record))
        if requirement['historical_references']:
            cited = ', '.join(f"`{item.get('id', 'unknown')}`" for item in requirement['historical_references'])
            lines.append(f"历史引用身份：{cited}。不计入当前分母，原成绩只列在历史引用节。")
        lines.append('')
    lines.append('## 未绑定当前要求的资格')
    lines.append('')
    if not document['unbound_qualifications']:
        lines.append('无。')
        lines.append('')
    for record in document['unbound_qualifications']:
        lines.extend(_record_lines(record))
        lines.append('')
    lines.append('## 历史引用')
    lines.append('')
    historical = document['historical']
    lines.append(f"identity: {historical['identity']}")
    lines.append(f"source: {historical['source']}")
    lines.append(f"scope: {historical['scope']}")
    lines.append('这些节点保持原身份。它们的格子不是当前要求的执行、完整性、数值、资格或证据。')
    lines.append('')
    for collection in ('joined', 'unjoined', 'not_current'):
        nodes = historical[collection]
        if collection != 'unjoined':
            nodes = [item['node'] for item in nodes]
        for node in nodes:
            lines.append(f"### 历史 {node.get('id', 'unknown')}")
            lines.append('')
            for key in ('title', 'status', 'review', 'evidence', 'gap'):
                if key in node:
                    lines.append(f"{key}：{json.dumps(node[key], ensure_ascii=False, sort_keys=True)}")
            if 'results' in node:
                lines.append('results：' + json.dumps(node['results'], ensure_ascii=False, sort_keys=True))
            lines.append('in_current_denominator: false')
            lines.append('counts_as_current_support: false')
            lines.append('')
    lines.append('## 例外')
    lines.append('')
    counts = document['classifications']['exception_counts']
    if not counts:
        lines.append('exception: none 0')
    for kind, count in counts.items():
        lines.append(f'exception: {kind} {count}')
    for item in document['exceptions']:
        if 'count' in item:
            lines.append('exception-detail: ' + json.dumps(item, ensure_ascii=False, sort_keys=True))
    lines.append('')
    lines.append('## 分类')
    lines.append('')
    lines.append('classifications: ' + json.dumps(document['classifications'], ensure_ascii=False, sort_keys=True))
    lines.append('')
    lines.append('## 本视图不做的事')
    lines.append('')
    for limit in document['limits']:
        lines.append(f'- {limit}')
    lines.append('')
    return '\n'.join(lines)


def _record_lines(record):
    qualification = record['qualification']
    historical = qualification['historical_query']
    lines = [
        f"资格记录：{qualification['id']}@{qualification['version']} sha256 {qualification['sha256']}",
        f"current_qualified: {str(qualification['current_qualified']).lower()}",
        f"historical_qualified: {str(historical['qualified']).lower()}",
        'counts_as_current_support: false',
        'confers_requirement_support: false',
        f"资格范围：{qualification['scope']}",
        f"资格后端原文：{json.dumps(qualification['backend'], ensure_ascii=False, sort_keys=True)}",
        f"执行：{_show(record['execution'])}",
        f"完整性：{_show(record['completeness'])}",
        f"数值：{_show(record['numerical'])}",
        f"工具链：{_show_toolchain(record['toolchain'])}",
        f"证据：{_show(record['evidence'])}",
    ]
    if qualification.get('gap'):
        lines.append(f"资格未决说明：{qualification['gap']}")
    for gap in qualification['gaps']:
        lines.append(f"资格缺口：{gap}")
    for ref in record.get('unbound_references') or []:
        lines.append(
            f"未绑定引用：kind {ref['kind']} `{ref['id']}` version {ref['version']} "
            f"sha256 {ref['sha256']} bound false"
        )
    for item in record['evidence'].get('items') or []:
        lines.append(
            f"证据来源：role {item['role']} `{item['id']}` version {item['version']} sha256 {item['sha256']} path {item['path']} origin {item['origin']}"
        )
        if item.get('gap'):
            lines.append(f"证据未决：{item['gap']}")
    for version in record['locatable_versions']:
        lines.append(
            f"可定位版本：`{version['id']}` version {version['version']} sha256 {version['sha256']} selected {str(version['selected']).lower()}"
        )
    for execution in record['executions']:
        lines.append(
            f"执行记录：{execution['id']}@{execution['version']} 执行 {_show(execution['execution'])} "
            f"完整性 {_show(execution['completeness'])} 数值 {_show(execution['numerical'])}"
        )
    for analysis in record['analyses']:
        lines.append(f"分析结论：{analysis['id']}@{analysis['version']} {_show(analysis['outcome'])}")
        lines.append(f"分析数值：{analysis['id']}@{analysis['version']} {_show(analysis['numerical'])}")
    return lines


def _table_cells(line):
    if not line.startswith('|'):
        return []
    return [part.strip() for part in line.strip().strip('|').split('|')]


def _header_status_fields(text):
    """view_status, adopted, and provisional values in the preamble, in order."""
    found = {key: [] for key in ('view_status', 'adopted', 'provisional')}
    for line in text.splitlines():
        if line.startswith('## '):
            break
        for key in found:
            prefix = key + ':'
            if line.startswith(prefix):
                rest = line[len(prefix):]
                found[key].append(rest[1:] if rest.startswith(' ') else rest)
                break
    return found


def _lines_after_heading(lines, heading):
    """Lines after one section heading and before the next ## heading."""
    try:
        start = lines.index(heading)
    except ValueError:
        return None
    end = len(lines)
    for cursor in range(start + 1, len(lines)):
        if lines[cursor].startswith('## '):
            end = cursor
            break
    return lines[start + 1:end]


def _audit_qualification_records(section_lines, records):
    """Match this section's qualification records and reject extras or conflicting toolchain lines."""
    errors = []
    blocks = _heading_blocks('\n'.join(section_lines), '资格记录：')
    accounted = []
    for record in records:
        qualification = record['qualification']
        heading = (
            f"资格记录：{qualification['id']}@{qualification['version']} "
            f"sha256 {qualification['sha256']}"
        )
        block = _take_heading(blocks, heading)
        if not block:
            errors.append('markdown qualification record missing')
            continue
        expected = f"工具链：{_show_toolchain(record['toolchain'])}"
        tool_lines = [line for line in block if line.startswith('工具链：')]
        accounted.extend(tool_lines)
        if tool_lines != [expected]:
            if expected not in tool_lines:
                errors.append('markdown dropped toolchain component')
            if len(tool_lines) > (1 if expected in tool_lines else 0):
                errors.append('markdown extra toolchain line')
    if blocks:
        errors.append('markdown extra qualification record')
    section_tools = [line for line in section_lines if line.startswith('工具链：')]
    if len(section_tools) != len(accounted):
        errors.append('markdown extra toolchain line')
    return errors


def audit(document):
    """Check denominators, classifications, and the ban on collapsed marks."""
    errors = []
    requirements = document['requirements']
    denominators = document['denominators']
    status = document.get('view_status')
    expected = VIEW_STATUSES.get(status)
    if (expected is None or document.get('adopted') is not (status == 'current-default')
            or document.get('provisional') is not (status == 'preview')
            or document.get('adoption_meaning') != expected['meaning']):
        errors.append('projection adoption labels inconsistent')
    if denominators.get('current_requirements') != len(requirements):
        errors.append('current requirement denominator')
    if denominators.get('source_index_is_requirement_coverage') is not False:
        errors.append('source index used as requirement coverage')
    if denominators.get('current_requirement_support_conferred') != 0:
        errors.append('requirement support was conferred')
    if denominators.get('historical_nodes_joined_to_current_requirements') != len(document['historical']['joined']):
        errors.append('joined historical denominator')
    historical = document['historical']
    retained = len(historical['joined']) + len(historical['unjoined']) + len(historical['not_current'])
    if denominators.get('historical_nodes') != retained:
        errors.append('historical nodes were dropped')
    classifications = document['classifications']
    if classifications['requirement_status'] != _sorted_counts(Counter(
            requirement['source_fields'].get('status', 'unknown')
            if isinstance(requirement['source_fields'].get('status'), str)
            and requirement['source_fields'].get('status') else 'unknown'
            for requirement in requirements)):
        errors.append('requirement status classification')
    cell_counts = Counter(cell['execution']['state']
                          for requirement in requirements
                          for cell in requirement['backends'].values())
    if classifications['backend_execution_cells'] != _sorted_counts(cell_counts):
        errors.append('backend cell classification')
    if sum(classifications['exception_counts'].values()) != len(document['exceptions']):
        errors.append('exception classification')
    current_ids = {requirement['id'] for requirement in requirements}
    for item in document['historical']['joined']:
        if item.get('in_current_denominator') or item['node'].get('counts_as_current_support'):
            errors.append('historical join entered current support')
        if any(name not in current_ids for name in item['requirement_ids']):
            errors.append('historical join outside current requirements')
    for requirement in requirements:
        if requirement['requirement_support'] != 'not_conferred':
            errors.append('requirement support changed')
        if requirement['coverage_sufficiency'] != 'pending':
            errors.append('coverage sufficiency was scored')
        if list(requirement['backends']) != list(BACKENDS):
            errors.append('backend columns changed')
        for name, cell in requirement['backends'].items():
            for key in ('toolchain', 'execution', 'completeness', 'numerical', 'qualification', 'evidence'):
                if cell[key].get('state') in FORBIDDEN_CELLS or cell[key].get('state') in {'passed', 'failed', 'qualified'}:
                    errors.append(f'collapsed {name} {key}')
            explicit_execution = any(record['execution']['state'] != 'unknown' for record in cell['records'])
            expected_execution = 'records_listed' if explicit_execution else 'unknown'
            if cell['execution']['state'] != expected_execution:
                errors.append('records collapsed or invented')
        for copied in requirement['historical_references']:
            if copied.get('counts_as_current_support') or copied.get('in_current_denominator'):
                errors.append('historical reference counted as current')
    for record in _all_records(requirements, document['unbound_qualifications']):
        if record['qualification']['confers_requirement_support'] is not False:
            errors.append('case conferred requirement support')
        if record['qualification']['historical_query']['counts_as_current_support'] is not False:
            errors.append('historical query counted as current support')
        if record['column'] not in {None, *BACKENDS}:
            errors.append('alias entered a backend column')
        for ref in record.get('unbound_references') or []:
            if ref.get('bound') is not False or set(ref) != {'id', 'version', 'sha256', 'kind', 'bound'}:
                errors.append('unbound reference claimed binding or borrowed target facts')
        for version in record['locatable_versions']:
            if 'bound' in version:
                errors.append('locatable version claimed binding')
    return errors


def audit_markdown(document, text):
    errors = []
    denominators = document['denominators']
    required = [
        f"current_requirements: {denominators['current_requirements']}",
        f"source_index_items: {denominators['source_index_items']}",
        'source_index_is_requirement_coverage: false',
        '规范源索引不是要求覆盖率。',
        f"current_requirement_support_conferred: {denominators['current_requirement_support_conferred']}",
        f"historical_nodes: {denominators['historical_nodes']}",
        f"historical_nodes_joined_to_current_requirements: {denominators['historical_nodes_joined_to_current_requirements']}",
    ]
    for line in required:
        if line not in text:
            errors.append('markdown missing ' + line)
    status = document.get('view_status')
    expected = VIEW_STATUSES.get(status)
    top = text.splitlines()[:7]
    view_line = f"view_status: {status}"
    adopted_line = f"adopted: {str(document.get('adopted')).lower()}"
    provisional_line = f"provisional: {str(document.get('provisional')).lower()}"
    # The visible header has to echo this document and be one of the two
    # legal combinations: current-default (adopted, not provisional) or
    # preview (not adopted, provisional). Title and note come from that status.
    legal_status = (
        expected is not None
        and document.get('adopted') is (status == 'current-default')
        and document.get('provisional') is (status == 'preview')
    )
    # The preamble must contain each status key once, with this document's value.
    header_fields = _header_status_fields(text)
    expected_header = {
        'view_status': [view_line.split(': ', 1)[1]],
        'adopted': [adopted_line.split(': ', 1)[1]],
        'provisional': [provisional_line.split(': ', 1)[1]],
    }
    if (not legal_status or header_fields != expected_header or expected['title'] not in top
            or expected['note'] not in top or view_line not in top or adopted_line not in top
            or provisional_line not in top):
        errors.append('markdown view status diverged')
    head, separator, _historical = text.partition('## 历史引用')
    if not separator:
        errors.append('markdown missing historical section')
        head = text
    headings = [line for line in head.splitlines() if line.startswith('### ')]
    if len(headings) != len(document['requirements']):
        errors.append('markdown requirement headings')
    for requirement in document['requirements']:
        if f"### {requirement['id']}@{requirement['version']}" not in head:
            errors.append('markdown missing requirement ' + requirement['id'])
        for gap in requirement['readiness_gaps']:
            if gap not in head:
                errors.append('markdown dropped readiness gap')
        for ref in requirement['referenced_versions']:
            if str(ref['sha256']) not in head:
                errors.append('markdown dropped referenced sha')
    for line in head.splitlines():
        for cell in _table_cells(line):
            if cell in FORBIDDEN_CELLS:
                errors.append('markdown collapsed a current cell')
    requirement_blocks = _heading_blocks(head, '### ')
    for requirement in document['requirements']:
        heading = f"### {requirement['id']}@{requirement['version']}"
        section = _take_heading(requirement_blocks, heading)
        for key in CONTRACT_FIELDS:
            if _contract_line(key, requirement['source_fields']) not in section:
                errors.append('markdown dropped requirement contract field ' + key)
        owned = []
        for cell in requirement['backends'].values():
            owned.extend(cell['records'])
        owned.extend(requirement['unassigned_backend_records'])
        # Records match inside this requirement. Another requirement's block does not count.
        errors.extend(_audit_qualification_records(section, owned))
    if requirement_blocks:
        errors.append('markdown requirement headings')
    unbound = _lines_after_heading(head.splitlines(), '## 未绑定当前要求的资格')
    if unbound is None:
        errors.append('markdown unbound qualifications diverged')
    else:
        errors.extend(_audit_qualification_records(unbound, document['unbound_qualifications']))
    counts = document['classifications']['exception_counts']
    for kind, count in counts.items():
        if f'exception: {kind} {count}' not in text:
            errors.append('markdown missing exception ' + kind)
    if 'classifications: ' + json.dumps(document['classifications'], ensure_ascii=False, sort_keys=True) not in text:
        errors.append('markdown classifications diverged')
    return errors


def load_historical_import(path=None):
    if path is None:
        path = Path(__import__('catalog').__file__).resolve().parent / 'data' / 'historical-comparison.json'
    data = json.loads(Path(path).read_text())
    nodes = data.get('nodes')
    return {
        'identity': data.get('identity') if data.get('identity') else 'unknown',
        'source': data.get('source') if data.get('source') else 'unknown',
        'scope': data.get('scope') if data.get('scope') else 'unknown',
        'nodes': nodes if isinstance(nodes, list) else [],
    }


def projection_texts(registry, historical=None, status='current-default'):
    """Return the JSON and Markdown produced from one registry projection."""
    if historical is None:
        historical = load_historical_import()
        imported = [node.get('id') for node in historical['nodes']]
        if imported != [node.get('id') for node in NODES]:
            raise SupportViewError('historical import nodes differ from catalog.NODES')
    document_ = document(registry, historical=historical, status=status)
    text = markdown(document_)
    problems = audit(document_) + audit_markdown(document_, text)
    if problems:
        raise SupportViewError('support view audit failed:\n' + '\n'.join(problems))
    return dumps(document_), text


def write_preview(registry, directory, *, historical=None):
    facts, text = projection_texts(registry, historical, status='preview')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / 'support-facts.json', directory / 'support.md']
    paths[0].write_text(facts)
    paths[1].write_text(text)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir')
    parser.add_argument('--root')
    parser.add_argument('--preview', required=True)
    args = parser.parse_args(argv)
    from registry import load
    kwargs = {}
    if args.data_dir is not None:
        kwargs['data_dir'] = args.data_dir
    if args.root is not None:
        kwargs['root'] = args.root
    try:
        written = write_preview(load(**kwargs), args.preview)
    except SupportViewError as error:
        raise SystemExit(str(error))
    print(f'wrote {len(written)} support preview files')


if __name__ == '__main__':
    main()
