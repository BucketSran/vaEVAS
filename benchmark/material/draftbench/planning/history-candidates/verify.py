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
    labels = {'confirmed_planning_candidate': '已确认候选', 'final_review_recommendation': '终审建议候选',
              'grok_expansion_recommendation': 'Grok全量复审新增建议', 'conditional_reserve': '条件后备'}
    counts = register['construction_review']['priority_counts']
    stats = register['stats']
    lines = ['# 历史候选逐项清单', '',
             f"本表由 `register.json` 生成，包含{stats['recommended_tasks']}项候选/{stats['planning_units']}个规划单元，另列U30后备。原105项确认、3项终审建议保留，本轮另建议{stats['grok_expansion_tasks']}项。新增建议尚待用户审核，所有任务仍待建设和验收。", '',
             f"P0首批{counts['P0']}项，P1第二批{counts['P1']}项，P2后置{counts['P2']}项。原六项基础题保留；新增B–M项存在偏简单风险，后置实测。建设成本L/M/H是作者工作量估计，与求解难度分开。HOLD不计入候选池。具体定义见[建设规则](README.md#建设顺序与进入正式集的条件)。", '',
             '每项都还需独立参考、正常与违约对照、评分校准和最小starter审核。下面的“改造”列出各题特有工作，不表示共同工作已经完成。', '',
             'Grok意见来自[Issue #159中的评论](https://github.com/BucketSran/vaEVAS/issues/159#issuecomment-6401348069)。[455项全量复审](GROK-REVIEW.md)列出池外条目的每项去向，[候选意见与补充原文](review-response.json)保留来源身份。S/R/T/I按实际交付责任建设，评论没有直接验收新增题目。', '',
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
        if row.get('planned_asset_dependencies'):
            lines += ['- 计划共建对象：' + '、'.join(row['planned_asset_dependencies']) + '；尚未提供或建成，同源对象与实质复用部分须共同考虑数据划分。', '']
    return '\n'.join(lines).rstrip() + '\n'


def render_pool_review(register, sources, pool):
    counts = pool['counts']
    labels = {'existing': '保留已有', 'add': '新增建议', 'variant': '并入方向，保留变体', 'support': '配套', 'defer': '暂缓'}
    groups = {'complete': '摘录完整', 'spec_gap': '规格待补', 'observation_gap': '观测待改'}
    lines = ['# Grok 455项来源的全面复审', '',
             f"核对342项摘录完整来源和113项待改造来源。{counts['baseline_mapped_sources']}项直接关联原候选（含U30后备），其余{counts['outside_reviewed']}项逐项复审。原108项加{counts['new_tasks']}项新增建议，当前{counts['current_tasks']}任务/{counts['current_units']}规划单元，另1后备；这些是规划候选，尚未录取或建题。", '',
             '来源数与任务数分开计。同源S/R/T和跨模块组合可能是一源多任务，多个来源也可能归入一个变体方向。变体并入不宣称数值或协议等价，原案例及具体差异仍保留。配套资产不计作独立候选；暂缓也保留接口与重审条件。', '',
             '[当前候选与建设要求](CANDIDATES.md) · [机器逐项登记及补充原文](pool-review.json) · [评论来源](https://github.com/BucketSran/vaEVAS/issues/159#issuecomment-6401348069)', '',
             '| 处置 | 来源数 |', '| --- | ---: |']
    lines += ['| ' + labels[k] + ' | ' + str(counts['dispositions'].get(k, 0)) + ' |' for k in labels]
    lines += ['', '455份首选公开原件按SHA256核对，290份随仓库、165份为local-only。348项本轮回读行为、参数及相关合同；107项沿用6b1270f0的逐项复审，并重新核对身份和关联。未逐份深审全部版本实现/评分器，未运行仿真或难度实测。', '']
    for family, title in register['families'].items():
        rows = [x for x in pool['rows'] if x['family'] == family]
        if not rows:
            continue
        lines += ['## ' + title, '', '| 历史条目 / 原题版本 | Grok组 | 本轮处置 / 去向 | 复用、改造与判断理由 |', '| --- | --- | --- | --- |']
        for row in rows:
            source = sources[row['source']]
            label = source['label']
            if source.get('repo_path'):
                label = '[' + label + '](../../../../../' + source['repo_path'] + ')'
            else:
                label += '，原件local-only'
            targets = '、'.join('[' + t + '](CANDIDATES.md#' + t.lower() + ')' for t in row['targets']) or '保留资产'
            cells = ['`' + row['source_row'] + '`<br>' + label,
                     groups[row['group']], labels[row['decision']] + '<br>' + targets,
                     '复用：' + row['reuse'] + '<br>改造：' + row['change'] + '<br>理由：' + row['reason']]
            lines.append('| ' + ' | '.join(x.replace('|', '/').replace('\n', ' ') for x in cells) + ' |')
        lines.append('')
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
    pool = json.loads((HERE / 'pool-review.json').read_text())
    require(register['schema_version'] == 3, 'construction review schema')
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
    require(statuses == {'confirmed_planning_candidate': 105, 'final_review_recommendation': 3,
                         'grok_expansion_recommendation': pool['counts']['new_tasks'], 'conditional_reserve': 1}, 'admission states')
    final = [r for r in candidates if r['status'] != 'conditional_reserve']
    require(len(final) == register['stats']['recommended_tasks'] == pool['counts']['current_tasks'], 'recommended task count')
    require(len({r['unit_id'] for r in final}) == register['stats']['planning_units'] == pool['counts']['current_units'], 'planning unit count')
    require(len({r['case_anchor'] for r in final}) == register['stats']['planning_units'], 'resolved source anchor count')
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
        require(set(row.get('planned_asset_dependencies', [])) <= {r['task_id'] for r in final}, row['task_id'] + ': unresolved planned dependency')
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
    require(response['coverage']['primary_contract_identities_verified'] == len(response['source_reviews']) and response['coverage']['main_candidates'] == len(final),
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
    pool_rows = pool['rows']
    require(len({x['source_row'] for x in pool_rows}) == len(pool_rows) == 455, 'complete 455-source pool review')
    require(dict(collections.Counter(x['group'] for x in pool_rows)) == pool['counts']['grok_groups'] ==
            {'complete': 342, 'spec_gap': 101, 'observation_gap': 12}, 'Grok source group counts')
    require(dict(collections.Counter(x['decision'] for x in pool_rows)) == pool['counts']['dispositions'], 'pool disposition counts')
    require(sum(not x['baseline_candidates'] for x in pool_rows) == pool['counts']['outside_reviewed'] == 348, 'outside review count')
    require(sum(bool(x['baseline_candidates']) for x in pool_rows) == pool['counts']['baseline_mapped_sources'] == 107, 'baseline mapped sources')
    require(dict(collections.Counter(x['availability'] for x in pool_rows)) == pool['counts']['source_availability'], 'pool availability')
    require(len({x['source'] for x in pool_rows}) == pool['counts']['distinct_source_identities'], 'distinct pool sources')
    new_candidates = {x['task_id']: x for x in candidates if x['status'] == 'grok_expansion_recommendation'}
    require({t for x in pool_rows if x['decision'] == 'add' for t in x['targets']} == new_candidates.keys(), 'new task/review correspondence')
    require(len(new_candidates) == register['stats']['grok_expansion_tasks'] == pool['counts']['new_tasks'], 'new task totals')
    require(pool['counts']['baseline_tasks'] == 108 and len(final) == 108 + len(new_candidates), 'pool additions')
    by_task = {x['task_id']: x for x in candidates}
    require(len(pool['baseline_candidates']) == 109, 'baseline identities denominator')
    for baseline in pool['baseline_candidates']:
        require(all(by_task[baseline['task_id']][k] == value for k, value in baseline.items()), baseline['task_id'] + ': prior candidate changed')
    case_fields = ('case_id', 'title', 'family', 'source_ids', 'original_assessment', 'historical_forms')
    case_identity = [{k: x[k] for k in case_fields} for x in register['cases']]
    require(digest(json.dumps(case_identity, ensure_ascii=False, sort_keys=True).encode()) == pool['historical_case_identity_sha256'],
            'historical case identity/assessment/form preservation')
    for row in pool_rows:
        rid = row['source_row']
        require(row['decision'] in ('existing', 'add', 'variant', 'support', 'defer'), rid + ': disposition')
        require(rid in by_row and row['source'] == by_row[rid]['source'], rid + ': pool source relation')
        require(row['case_id'] == by_row[rid]['case_id'] and row['historical_merge_into'] == by_row[rid]['merge_into'], rid + ': historical lineage')
        source = sources[row['source']]
        require(row['source_sha256'] == source['sha256'] and row['source_identity_verified_locally'] is True, rid + ': pool identity')
        require(row['availability'] == source['availability'] and row['source_label'] == source['label'], rid + ': source metadata')
        require(set(row['targets']) <= by_task.keys(), rid + ': unresolved target')
        require(all(str(row[k]).strip() for k in ('reuse', 'change', 'reason', 'review_method')), rid + ': missing individual decision')
        require(bool(row['targets']) == (row['decision'] in ('existing', 'add', 'variant')), rid + ': target responsibility')
        if row['decision'] == 'existing':
            require(set(row['targets']) == set(row['baseline_candidates']), rid + ': baseline association')
        if row['decision'] == 'add':
            require(len(row['targets']) == 1 and new_candidates[row['targets'][0]]['expansion_source'] == rid, rid + ': new candidate identity')
        if source['availability'] == 'repository-contained':
            original = (ROOT / source['repo_path']).read_text()
            for section in row['supplemental_public_context']:
                for part in section['text'].split('[该段已保留于 inventory.jsonl 对应来源的 behavior_excerpt。]'):
                    require(part.strip() in original, rid + ': pool context mismatch')
    for family, counts in pool['counts']['by_family'].items():
        require(dict(collections.Counter(x['decision'] for x in pool_rows if x['family'] == family)) == counts, family + ': disposition drift')
    require((HERE / 'CANDIDATES.md').read_text() == render_table(register, sources), 'candidate table is stale; regenerate with --render-table')
    require((HERE / 'GROK-REVIEW.md').read_text() == render_pool_review(register, sources, pool), 'full review view is stale; regenerate with --render-pool-review')
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
    for file in (HERE / 'README.md', HERE / 'CANDIDATES.md', HERE / 'GROK-REVIEW.md'):
        for link in re.findall(r'\]\(([^)]+)\)', file.read_text()):
            if not link.startswith(('https:', 'http:', '#')):
                target = link.split('#')[0]
                require((file.parent / target).exists(), file.name + ': missing ' + link)
    return dict(status='pass', static_checks=checks, tasks=len(final), planning_units=register['stats']['planning_units'],
                conditional_reserves=1, repository_source_hashes_verified=checked_sources,
                local_only_source_identities=len(sources)-checked_sources,
                construction_priorities=summary['priority_counts'],
                construction_review_items=len(candidates),
                grok_sources_reviewed=len(pool_rows), outside_sources_reviewed=pool['counts']['outside_reviewed'],
                source_dispositions=pool['counts']['dispositions'],
                runtime_executed=False, independent_task_acceptance=False)


def show(identifier, register, sources, inventory):
    by_row = {r['id']: r for r in inventory}
    cases = {r['case_id']: r for r in register['cases']}
    candidate = next((r for r in register['candidates'] if r['task_id'] == identifier), None)
    pool = json.loads((HERE / 'pool-review.json').read_text())
    review = next((r for r in pool['rows'] if r['source_row'] == identifier), None)
    if review:
        print(json.dumps({'full_pool_review': review}, ensure_ascii=False, indent=2))
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
    parser.add_argument('--render-pool-review', action='store_true', help='print the full Grok source-review Markdown')
    args = parser.parse_args()
    data = load()
    if args.render_table:
        print(render_table(*data[:2]), end='')
    elif args.render_pool_review:
        print(render_pool_review(*data[:2], json.loads((HERE / 'pool-review.json').read_text())), end='')
    elif args.show:
        show(args.show, *data)
    else:
        print(json.dumps(verify(*data), ensure_ascii=False, indent=2))
