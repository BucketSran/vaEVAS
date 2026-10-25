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
    labels = {'confirmed_planning_candidate': '已确认候选', 'final_review_recommendation': '终审建议候选', 'conditional_reserve': '条件后备'}
    counts = register['construction_review']['priority_counts']
    lines = ['# 历史候选逐项清单', '',
             '本表由 `register.json` 生成，包含108项主候选与另列的U30后备。105项原确认、3项终审建议的来源状态保持不变；本轮只重新安排建设。所有任务仍待建设和验收。', '',
             f"P0首批{counts['P0']}项，P1第二批{counts['P1']}项，P2后置{counts['P2']}项，其中包含既定六项基础题。建设成本L/M/H分别为低/中/高，是作者工作量估计，与题目难度分开。HOLD不计入108。具体定义见[建设规则](README.md#建设顺序与进入正式集的条件)。", '',
             '每项都还需独立参考、正常与违约对照、评分校准和最小starter审核。下面的“改造”列出各题特有工作，不表示共同工作已经完成。', '',
             'Grok意见来自[Issue #159中的评论](https://github.com/BucketSran/vaEVAS/issues/159#issuecomment-6401348069)，针对历史来源代表。新S/R/T/I职责由本规划提出，评论没有直接验收它们。[逐条对应及补充原文](review-response.json)记录了意见来源、版本和参数/行为上下文。', '',
             '| 候选 / 来源案例 | 任务内容 | 功能家族 | 动作 | 预估难度 | 优先级 / 建设成本 | 状态 | 原始题号和版本 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in register['candidates']:
        source = sources[row['primary_source']]
        label = source['label']
        if 'repo_path' in source:
            label = '[' + label + '](../../../../../' + source['repo_path'] + ')'
        else:
            label += '，原件local-only，行为摘录随清单保留'
        cells = ['[' + row['task_id'] + '](#' + row['task_id'].lower() + ') / ' + row['case_anchor'],
                 row['title'], register['families'][row['family']], row['action'], row['difficulty'],
                 row['priority'] + ' / ' + row['construction']['cost'], labels[row['status']], label]
        lines.append('| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in cells) + ' |')
    lines += ['', '## 逐项建设与意见处理', '']
    for row in register['candidates']:
        plan = row['construction']
        review = row['grok_review']
        lines += ['### ' + row['task_id'], '', row['title'] + '。' + row['priority'] + '，建设成本' + plan['cost'] + '，' + plan['work_kind'] + '。', '',
                  '- 可复用：' + row['reuse'],
                  '- 需要改：' + row['author_work'],
                  '- 排序理由：' + plan['priority_reason'],
                  '- Grok意见处理：' + review['decision'] + '。' + review['reason'],
                  '- 对应历史条目：' + '、'.join('`' + x + '`' for x in review['claim_refs']) + '。', '']
    return '\n'.join(lines).rstrip() + '\n'


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
    response = json.loads((HERE / 'review-response.json').read_text())
    require(register['schema_version'] == 2, 'construction review schema')
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
        construction = row['construction']
        review = row['grok_review']
        require(row['priority'] in ('P0', 'P1', 'P2', 'HOLD'), row['task_id'] + ': priority')
        require((row['priority'] == 'HOLD') == (row['status'] == 'conditional_reserve'), row['task_id'] + ': reserve priority')
        require(construction['cost'] in ('L', 'M', 'H') and bool(construction['priority_reason']), row['task_id'] + ': construction cost/reason')
        require(construction['work_kind'] in ('补行为边界', '基础整理', '整理既有规格', '新增对象或真值', '故障核实'), row['task_id'] + ': construction kind')
        require(construction['acceptance_state'] == 'planning_only', row['task_id'] + ': no task admission')
        require(all(str(value).strip() for value in (row['reuse'], row['author_work'], review['reason'])), row['task_id'] + ': missing per-task judgment')
        require(review['decision'] in ('部分采纳', '采纳方向', '采纳缺口', '采纳重建'), row['task_id'] + ': review decision')
        require(bool(review['claim_refs']) and set(review['claim_refs']) <= response['claims'].keys(), row['task_id'] + ': external claim references')
        for rid in review['claim_refs']:
            require((by_row[rid]['case_id'] is not None and by_row[rid]['case_id'] == row['case_anchor']) or row['primary_ref'] == rid,
                    row['task_id'] + ': claim/source mismatch')
        require(construction['source_review'] == row['primary_source'] and row['primary_source'] in response['source_reviews'], row['task_id'] + ': contract review identity')
        referenced.add(row['primary_source'])
        referenced.update(row.get('source_contracts', []))
    require(referenced <= sources.keys(), 'unresolved source identities')
    summary = register['construction_review']
    for field, values in (
        ('priority_counts', [r['priority'] for r in final]),
        ('cost_counts', [r['construction']['cost'] for r in final]),
        ('work_kind_counts', [r['construction']['work_kind'] for r in final]),
        ('decision_counts', [r['grok_review']['decision'] for r in final]),
    ):
        require(dict(collections.Counter(values)) == summary[field], field + ': summary drift')
    require(set(response['source_reviews']) == {r['primary_source'] for r in candidates}, 'public contract review coverage')
    require(set(response['claims']) == {rid for r in candidates for rid in r['grok_review']['claim_refs']}, 'external claim coverage')
    require(response['coverage']['primary_contract_identities_verified'] == 109 and response['coverage']['main_candidates'] == 108,
            'review denominators')
    require(response['coverage']['selected_comment_sources'] == len(response['claims']), 'selected comment source count')
    require(response['coverage']['source_availability'] == dict(collections.Counter(sources[sid]['availability'] for sid in response['source_reviews'])),
            'review source availability count')
    require(response['coverage']['runtime_executed'] is False and response['coverage']['full_implementation_audit'] is False,
            'review execution boundary')
    for rid, claim in response['claims'].items():
        require(claim['source_row'] == rid and rid in by_row, rid + ': claim identity')
        require(claim['group'] in ('behavior_complete_in_excerpt', 'missing_contract_in_excerpt', 'observation_mismatch'), rid + ': claim group')
    for sid, review in response['source_reviews'].items():
        require(review['sha256'] == sources[sid]['sha256'] and review['identity_verified_locally'] is True, sid + ': review/source identity')
        if sources[sid]['availability'] == 'repository-contained':
            original = (ROOT / sources[sid]['repo_path']).read_text()
            for section in review['supplemental_public_context']:
                for part in section['text'].split('[该段已保留于 inventory.jsonl 对应来源的 behavior_excerpt。]'):
                    require(part.strip() in original, sid + ': supplemental public context mismatch')
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
                construction_priorities=summary['priority_counts'],
                construction_review_items=len(candidates),
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
        response = json.loads((HERE / 'review-response.json').read_text())
        print(json.dumps({'external_comment': response['external_comment']['url'],
                          'grok_claims': [response['claims'][rid] for rid in candidate['grok_review']['claim_refs']],
                          'primary_contract_review': response['source_reviews'][candidate['primary_source']]},
                         ensure_ascii=False, indent=2))
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
