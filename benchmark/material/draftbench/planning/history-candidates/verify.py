#!/usr/bin/env python3
"""Validate a planning register and inspect its historical evidence, without simulation."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load():
    register = json.loads((HERE / 'register.json').read_text())
    sources = json.loads((HERE / 'sources.json').read_text())
    inventory = [json.loads(line) for line in (HERE / 'inventory.jsonl').read_text().splitlines()]
    return register, sources, inventory


def render_table(register, sources):
    labels = {'confirmed_planning_candidate': '已确认候选', 'final_review_recommendation': '本轮建议新增', 'conditional_reserve': '条件后备'}
    lines = ['# 历史候选逐项清单', '',
             '本表由 `register.json` 的 candidates 生成。前105项已确认进入规划池，另建议3项，1项保留为条件后备。所有任务仍待建设与题目验收。编号不代表新的正式题号。', '',
             '| 候选 / 来源案例 | 任务内容 | 功能家族 | 动作 | 预估难度 / 优先级 | 状态 | 原始题号和版本 | 复用与待补 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in register['candidates']:
        source = sources[row['primary_source']]
        label = source['label']
        if 'repo_path' in source:
            label = '[' + label + '](../../../../../' + source['repo_path'] + ')'
        else:
            label += '，原件local-only，行为摘录随清单保留'
        cells = [row['task_id'] + ' / ' + row['case_anchor'], row['title'], register['families'][row['family']],
                 row['action'], row['difficulty'] + ' / ' + row['priority'], labels[row['status']], label,
                 row['reuse_level'] + '；' + row['author_work']]
        lines.append('| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in cells) + ' |')
    return '\n'.join(lines) + '\n'


def verify(register, sources, inventory):
    checks = 0

    def require(condition, message):
        nonlocal checks
        if not condition:
            raise ValueError(message)
        checks += 1

    by_row = {r['id']: r for r in inventory}
    cases = {r['case_id']: r for r in register['cases']}
    candidates = register['candidates']
    require(len(by_row) == len(inventory) == 751, 'source row identities')
    require(len({r['source_unit'] for r in inventory}) == 618, 'source unit denominator')
    require(len(cases) == len(register['cases']) == 422, 'case identities')
    require(len({r['task_id'] for r in candidates}) == len(candidates), 'candidate identity collision')
    referenced = set(register['implementation_evidence'])
    for row in inventory:
        require(digest(row['behavior_excerpt'].encode()) == row['excerpt_sha256'], row['id'] + ': excerpt digest')
        require(row['source'] in sources, row['id'] + ': missing canonical source')
        referenced.add(row['source'])
        referenced.update(row['original_sources'])
        if row['merge_into']:
            require(row['merge_into'] in by_row, row['id'] + ': unresolved merge target')
        if row['case_id']:
            require(row['case_id'] in cases, row['id'] + ': unresolved case')
        source = sources[row['source']]
        if source['availability'] == 'repository-contained' and row['excerpt_kind'] == 'verbatim_substring':
            require(row['behavior_excerpt'] in (ROOT / source['repo_path']).read_text(), row['id'] + ': excerpt/source mismatch')
    mapped = []
    historical_forms = []
    for case in cases.values():
        mapped.extend(case['source_ids'])
        for rid in case['source_ids']:
            require(rid in by_row and by_row[rid]['case_id'] == case['case_id'], case['case_id'] + ': source membership')
        for form in case['historical_forms']:
            historical_forms.append(form['task_id'])
            require(set(form['source_ids']) <= set(case['source_ids']), form['task_id'] + ': crossed case lineage')
    eligible = {r['id'] for r in inventory if r['initial_status'] in ('A', 'B')}
    require(len(mapped) == len(set(mapped)) == 541 and set(mapped) == eligible, '541 rows must map once to cases')
    require(len(historical_forms) == len(set(historical_forms)) == 495, 'historical task form denominator')
    statuses = collections.Counter(r['status'] for r in candidates)
    require(statuses == {'confirmed_planning_candidate': 105, 'final_review_recommendation': 3, 'conditional_reserve': 1}, 'admission states')
    final = [r for r in candidates if r['status'] != 'conditional_reserve']
    require(len(final) == register['stats']['recommended_tasks'] == 108, 'recommended task count')
    require(len({r['unit_id'] for r in final}) == register['stats']['planning_units'] == 103, 'planning unit count')
    require(len({r['case_anchor'] for r in final}) == 103, 'resolved source anchor count')
    require(dict(collections.Counter(r['action'] for r in final)) == register['stats']['actions'], 'action totals')
    require({r['task_id'] for r in final if r['difficulty'] == 'B'} == {'C066-S1','C083-S1','C128-S1','C250-S1','C396-S1','C402-S1'}, 'basic layer changed')
    for row in candidates:
        require(row['action'] in 'SRTID' and row['task_id'].split('-')[1][0] == row['action'], row['task_id'] + ': action identity')
        require(row['primary_ref'] in cases or row['primary_ref'] in by_row, row['task_id'] + ': source anchor')
        if row['case_anchor'] in cases:
            require(row['task_id'] in cases[row['case_anchor']]['candidate_tasks'], row['task_id'] + ': missing case task relation')
        require(row['difficulty_measured'] is False, row['task_id'] + ': unmeasured difficulty')
        require(bool(row['author_work']) and bool(row['difference']), row['task_id'] + ': missing construction/difference')
        referenced.add(row['primary_source'])
        referenced.update(row.get('source_contracts', []))
    require(referenced <= sources.keys(), 'unresolved source identities')
    require((HERE / 'CANDIDATES.md').read_text() == render_table(register, sources), 'candidate table is stale; regenerate with --render-table')
    checked_sources = 0
    for sid, source in sources.items():
        require(source['availability'] in ('repository-contained', 'local-only'), sid + ': availability')
        if source['availability'] == 'repository-contained':
            file = ROOT / source['repo_path']
            require(file.is_file() and digest(file.read_bytes()) == source['sha256'], sid + ': source identity drift')
            checked_sources += 1
    for file in HERE.iterdir():
        if file.suffix in ('.json', '.jsonl', '.md'):
            require('/Users/' not in file.read_text(), file.name + ': machine-private path')
    for file in (HERE / 'README.md', HERE / 'CANDIDATES.md'):
        for link in re.findall(r'\]\(([^)]+)\)', file.read_text()):
            if not link.startswith(('https:', 'http:', '#')):
                target = link.split('#')[0]
                require((file.parent / target).exists(), file.name + ': missing ' + link)
    return dict(status='pass', static_checks=checks, tasks=108, planning_units=103,
                conditional_reserves=1, repository_source_hashes_verified=checked_sources,
                local_only_source_identities=len(sources)-checked_sources,
                runtime_executed=False, independent_review=False)


def show(identifier, register, sources, inventory):
    by_row = {r['id']: r for r in inventory}
    cases = {r['case_id']: r for r in register['cases']}
    candidate = next((r for r in register['candidates'] if r['task_id'] == identifier), None)
    additional = []
    if candidate:
        print(json.dumps(candidate, ensure_ascii=False, indent=2))
        evidence = {candidate['primary_source'], *candidate.get('source_contracts', [])}
        print(json.dumps({sid: sources[sid] for sid in sorted(evidence)}, ensure_ascii=False, indent=2))
        additional = [r['id'] for r in inventory if r['source'] in evidence]
        identifier = candidate['primary_ref']
    if identifier in cases:
        print(json.dumps(cases[identifier], ensure_ascii=False, indent=2))
        ids = cases[identifier]['source_ids']
    elif identifier in by_row:
        ids = [identifier]
    else:
        raise ValueError('unknown candidate/case/source-row ID: ' + identifier)
    for rid in dict.fromkeys(ids + additional):
        row = by_row[rid]
        print('\n' + rid + '\n' + json.dumps(sources[row['source']], ensure_ascii=False, indent=2))
        print(row['behavior_excerpt'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show', help='candidate ID, case ID or original source-row slug')
    parser.add_argument('--render-table', action='store_true', help='print the candidate Markdown table')
    args = parser.parse_args()
    data = load()
    if args.render_table:
        print(render_table(*data[:2]), end='')
    elif args.show:
        show(args.show, *data)
    else:
        print(json.dumps(verify(*data), ensure_ascii=False, indent=2))
