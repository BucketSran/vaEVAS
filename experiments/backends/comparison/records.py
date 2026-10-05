"""Validate and render frozen comparison records without running any backend."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKENDS = ('spectre', 'openvaf_ngspice', 'gnucap', 'evas')
LABELS = ('Spectre', 'ngspice + OpenVAF-R', 'Gnucap + modelgen-verilog', 'EVAS')
GROUPS = tuple(f'V{i}' for i in range(1, 8))
VERDICTS = 'PFUXIT'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text())


def evidence_ok(ref, root: Path):
    """A compact historical receipt remains usable even when its private raw is absent."""
    path = (root / ref['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('evidence path escapes repository')
    if not path.is_file() or sha(path) != ref['sha256']:
        raise ValueError('missing or changed compact evidence: ' + ref['path'])


STATUS = {'observations_within_targets': 'P', 'observed_violation': 'F', 'unresolved': 'I',
          'observation_invalid': 'I', 'compile_failed': 'X', 'compile_timeout': 'X',
          'execution_failed': 'X', 'runtime_timeout': 'X', 'timeout': 'X',
          'missing_waveform': 'I', 'missing_compile_artifact': 'X', 'confirmed_unsupported': 'U'}
HISTORICAL = 'experiments/backends/dvs2-four-backend-validation/results/matrix.json'


def source_bytes(ref, root, revision):
    """Read a frozen source. Legacy mutable paths resolve at their fixed commit."""
    path = (root / ref['path']).resolve()
    if 'original_path' in ref:
        evidence_ok(ref, root)
    if not path.is_relative_to(root.resolve()):
        raise ValueError('source path escapes repository')
    if path.is_file() and sha(path) == ref['sha256']:
        content = path.read_bytes()
    else:
        if not re.fullmatch(r'[0-9a-f]{40}', revision or ''):
            raise ValueError('frozen source requires a fixed 40-hex revision')
        relative = Path(ref.get('original_path', ref['path']))
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('source path escapes repository')
        try:
            content = subprocess.check_output(['git', 'show', revision + ':' + relative.as_posix()],
                                              cwd=root, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise ValueError('missing frozen source blob') from error
    if hashlib.sha256(content).hexdigest() != ref['sha256']:
        raise ValueError('missing or changed compact evidence: ' + ref['path'])
    if 'original_path' in ref:
        if not re.fullmatch(r'[0-9a-f]{40}', revision or ''):
            raise ValueError('frozen source requires a fixed 40-hex revision')
        relative = Path(ref['original_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('source path escapes repository')
        try:
            blob = subprocess.check_output(['git', 'show', revision + ':' + relative.as_posix()],
                                           cwd=root, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise ValueError('missing frozen source blob') from error
        if blob != content:
            raise ValueError('archive source differs from fixed revision blob')
    return content


def voltage_metrics(case, analysis, schema_version=2):
    screen = analysis.get('v1_screen', {})
    if case not in ('v1-main', 'v2-main') or not screen.get('max_observed_error'):
        return {}
    if schema_version == 1 or case == 'v1-main':
        value = {'property': 'maximum absolute exported output voltage error', 'unit': 'V',
                 'observed': max(v['error_v'] for v in screen['max_observed_error'].values()), 'budget': .001}
        return {'voltage': value if schema_version == 1 else [value]}
    return {'voltage': [
        {'property': 'maximum absolute differential output voltage error', 'unit': 'V',
         'observed': screen['differential_error_v'], 'budget': .002},
        {'property': 'maximum absolute common-mode output voltage error', 'unit': 'V',
         'observed': screen['common_mode_error_v'], 'budget': .001}]}


def metric_components(value):
    return value if isinstance(value, list) else [value]


def bound_observation(record, root, schema_version):
    if record['accounting'] == 'executed' or (record['accounting'] == 'reused' and record.get('execution_receipt')):
        receipt = load(root / record['execution_receipt']['path'])
        ref = receipt.get('observation')
        if not ref:
            raise ValueError('execution receipt lacks named observation')
        evidence_ok(ref, root)
        observation = load(root / ref['path'])
    else:
        ref = record.get('observation_binding')
        if not ref and schema_version == 1 and record['dataset'] == 'development31-20260928':
            matches = [r for r in record['evidence'] if r['path'] == HISTORICAL]
            if len(matches) != 1:
                raise ValueError('historical observation binding missing')
            ref = dict(matches[0], format='matrix')
        if not ref or ref.get('format') != 'matrix':
            raise ValueError('reused record requires named matrix observation binding')
        evidence_ok(ref, root)
        matrix = load(root / ref['path'])
        selector = {'backend': record['backend'], 'condition': record['case'], 'profile': record['profile'],
                    'source_run_id': record['measurement']['run_id']}
        if 'selector' in ref and ref['selector'] != selector:
            raise ValueError('observation selector differs from record identity')
        matches = [r for r in matrix['records'] if all(r.get(k) == v for k, v in selector.items())]
        if len(matches) != 1:
            raise ValueError('named observation not unique or missing')
        observation = matches[0]['analysis']
        if record['dataset'] == 'development31-20260928':
            receipts = [load(root / r['path']) for r in record['evidence'] if r['kind'] == 'receipt']
            if len(receipts) != 1 or receipts[0].get('matrix_sha256') != ref['sha256']:
                raise ValueError('historical observation differs from matrix receipt')
            expected_input = identity({'historical_input_manifest': receipts[0]['input_manifest_sha256'], 'case': record['case']})
            if record['input_identity'] != expected_input:
                raise ValueError('historical observation input identity mismatch')
            frozen = receipts[0].get('frozen_sources', {})
            checker = frozen.get('experiments/dvs2-spectre-validation/check_results.py')
            if checker != record['checker_identity']:
                raise ValueError('historical observation checker identity mismatch')
    status = observation.get('status')
    if STATUS.get(status) != record['verdict'] or status != record['reason']:
        raise ValueError('verdict/reason differs from bound observation')
    if record.get('metrics', {}) != voltage_metrics(record['case'], observation, schema_version):
        raise ValueError('metric differs from bound observation or property budget')
    return observation


def freshness(record, target):
    measured = record.get('measurement')
    if measured is None:
        return 'unmeasured'
    expected = target[record['backend']]
    if measured['runtime_identity'] != expected['runtime_identity']:
        return 'stale'
    if measured['revision'] != expected['revision'] and not record.get('reuse_justification'):
        return 'stale'
    return 'current'


def validate(data, root=ROOT, target=None):
    if data['schema_version'] not in (1, 2):
        raise ValueError('unsupported schema version')
    if data['schema_version'] == 2:
        contract = data.get('metric_contract')
        if not contract or contract.get('original_path') != 'evas/validation/PROTOCOL.md':
            raise ValueError('metric property/budget contract source required')
        source_bytes(contract, root, contract.get('revision'))
    target = target or data['targets']
    if set(target) != set(BACKENDS):
        raise ValueError('exactly four backend targets required')
    if data.get('derivation'):
        parent_ref = data['derivation']['parent']
        evidence_ok(parent_ref, root)
        parent = load(root / parent_ref['path'])
        key = lambda row: tuple(row[k] for k in ('dataset', 'case', 'backend', 'profile'))
        old_rows = {key(r): r for r in parent['records']}
        if set(old_rows) != {key(r) for r in data['records']}:
            raise ValueError('static derivation changed configuration denominator')
        fields = ('verdict', 'qualification', 'stage', 'reason', 'accounting', 'measurement',
                  'checker_identity', 'input_identity', 'evidence', 'execution_receipt')
        for row in data['records']:
            if any(row.get(k) != old_rows[key(row)].get(k) for k in fields):
                raise ValueError('static derivation changed historical execution identity or verdict')
    if data.get('refresh'):
        from refresh import check_refresh
        check_refresh(data, root)
    datasets = {d['id']: d for d in data['datasets']}
    if len(datasets) != len(data['datasets']):
        raise ValueError('duplicate dataset')
    expected = set()
    cases_by_dataset = {}
    for d in data['datasets']:
        for candidate in d.get('candidates', []):
            if data['schema_version'] == 2 and any('original_path' not in r for r in candidate['sources']):
                raise ValueError('schema2 candidate requires immutable source archive')
            for ref in candidate['sources']:
                source_bytes(ref, root, candidate.get('revision'))
            refs = {ref['path']: ref['sha256'] for ref in candidate['sources']}
            if candidate['source_sha256'] not in refs.values() or candidate['checker_sha256'] not in refs.values():
                raise ValueError('application source/checker identity mismatch')
            if 'adapter_checker_sha256' in candidate:
                adapters = [r for r in candidate['sources'] if r.get('original_path', r['path']).endswith('/triangle_evas.py')]
                if len(adapters) != 1 or adapters[0]['sha256'] != candidate['adapter_checker_sha256']:
                    raise ValueError('application adapter checker identity mismatch')
            case_refs = [ref for ref in candidate['sources'] if ref.get('original_path', ref['path']).endswith('/cases.json')]
            if len(case_refs) != 1:
                raise ValueError('application case source required')
            cases = [c for c in json.loads(source_bytes(case_refs[0], root, candidate.get('revision'))) if c['name'] == candidate['case_name']]
            if len(cases) != 1 or identity(cases[0]) != candidate['case_sha256']:
                raise ValueError('application frozen case identity mismatch')
        if d['state'] == 'pending':
            if d['cases'] is not None or d['denominator'] is not None:
                raise ValueError('pending denominator must be unknown')
            continue
        cases = {c['id']: c for c in d['cases']}
        if len(cases) != len(d['cases']) or len(cases) != d['denominator']:
            raise ValueError('duplicate case assignment or denominator shrinkage')
        if identity(d['cases']) != d['case_manifest_sha256']:
            raise ValueError('frozen case manifest changed')
        if any(c['group'] not in GROUPS for c in cases.values()):
            raise ValueError('one valid primary group required per condition')
        cases_by_dataset[d['id']] = cases
        expected.update((d['id'], c, b, p) for c in cases for b in BACKENDS for p in d['profiles'])
    actual = set()
    for r in data['records']:
        key = (r['dataset'], r['case'], r['backend'], r['profile'])
        if key in actual:
            raise ValueError('duplicate configuration')
        actual.add(key)
        if key not in expected:
            raise ValueError('configuration outside frozen denominator')
        case = cases_by_dataset[r['dataset']][r['case']]
        if r['input_identity'] != case['input_identity']:
            raise ValueError('measurement input identity differs from frozen case')
        if r['verdict'] not in VERDICTS or len(r['verdict']) != 1:
            raise ValueError('unknown verdict')
        if r['accounting'] not in ('executed', 'reused', 'unrun'):
            raise ValueError('unknown accounting state')
        if not r['stage'] or not r['reason']:
            raise ValueError('stage and interpretation required')
        for ref in r.get('evidence', []):
            evidence_ok(ref, root)
        if r['verdict'] == 'T':
            if r['accounting'] != 'unrun' or r.get('measurement') is not None or r.get('metrics'):
                raise ValueError('unrun record cannot contain observations')
        else:
            m = r.get('measurement')
            if r['accounting'] == 'unrun' or not m or not m['runtime_identity'] or not m['revision']:
                raise ValueError('observed record needs measured identity')
            if not r.get('evidence'):
                raise ValueError('missing evidence for observation or pass')
            if r['verdict'] == 'P' and not r.get('checker_identity'):
                raise ValueError('pass requires independent checker identity')
            if r['verdict'] == 'P' and r['stage'] != 'analysis':
                raise ValueError('incomplete evidence cannot be a pass')
            if r['accounting'] == 'reused' and r.get('execution_receipt') and not data.get('refresh'):
                raise ValueError('receipt reuse requires a bound finite refresh parent')
            if r['accounting'] == 'executed' or r.get('execution_receipt'):
                ref = r.get('execution_receipt')
                if not ref:
                    raise ValueError('new observation requires execution receipt')
                evidence_ok(ref, root)
                receipt = load(root / ref['path'])
                for source in receipt.get('runner_sources', []):
                    evidence_ok(source, root)
                bindings = {'backend': r['backend'], 'condition': r['case'], 'profile': r['profile'],
                            'input_identity': r['input_identity'], 'source_revision': m['revision'],
                            'runtime_identity': m['runtime_identity'], 'checker_identity': r['checker_identity']}
                if data.get('refresh') and receipt.get('run_id') != m.get('run_id'):
                    raise ValueError('execution receipt run identity mismatch')
                if any(receipt.get(k) != v for k, v in bindings.items()):
                    raise ValueError('execution receipt identity mismatch')
                if not receipt.get('commands') or not receipt.get('input_manifest_sha256'):
                    raise ValueError('execution receipt lacks commands/input manifest')
                if r['backend'] == 'evas' and not receipt.get('kernel_sha256'):
                    raise ValueError('source-only identity is not measured EVAS kernel evidence')
                if m.get('kernel_sha256') != receipt.get('kernel_sha256'):
                    raise ValueError('measured kernel hash differs from execution receipt')
                tool = receipt.get('tool')
                tool_bindings = {'revision': m['revision'], 'runtime_identity': m['runtime_identity']}
                if r['backend'] == 'evas':
                    tool_bindings['kernel_sha256'] = m['kernel_sha256']
                if not isinstance(tool, dict) or any(tool.get(k) != v for k, v in tool_bindings.items()):
                    raise ValueError('execution receipt tool identity differs from measured identity')
                if r['verdict'] == 'P':
                    observation = receipt.get('observation')
                    if not observation or not receipt.get('waveform_sha256') or not receipt.get('effective_settings'):
                        raise ValueError('pass needs output hash, observation and effective settings')
                    evidence_ok(observation, root)
                    if load(root / observation['path']).get('status') != 'observations_within_targets':
                        raise ValueError('pass differs from independent observation')
                    if receipt.get('execution_status') != 'waveform_available' or any(
                            c.get('exit_code') != 0 or c.get('timed_out') for c in receipt['commands']):
                        raise ValueError('failed execution cannot pass')
                    if m.get('output_sha256') != receipt['waveform_sha256']:
                        raise ValueError('measured output hash differs from execution receipt')
            bound_observation(r, root, data['schema_version'])
        if r.get('claimed_freshness') == 'current' and freshness(r, target) != 'current':
            raise ValueError('old measurement claimed as new revision')
        for metric in [m for value in r.get('metrics', {}).values() for m in metric_components(value)]:
            if metric['unit'] not in ('V', 's') or not metric['property']:
                raise ValueError('declared metric property and original unit required')
            if any(not isinstance(metric[k], (int, float)) or not math.isfinite(metric[k])
                   for k in ('observed', 'budget')) or metric['observed'] < 0 or metric['budget'] <= 0:
                raise ValueError('invalid observed error or external budget')
    if actual != expected:
        raise ValueError('denominator shrinkage: missing configurations')
    if set(data['coverage']) != set(GROUPS):
        raise ValueError('V1-V7 gap map required')
    for gap in data['coverage'].values():
        if not gap['capabilities'] or not gap['boundary'] or not gap['independent_answer']:
            raise ValueError('coverage gap needs capability, boundary and independent answer')
    return target


def common_errors(data, dataset, profile, metric_name):
    """One declared subset, same properties/units/budgets for all four backends."""
    records = {(r['case'], r['backend']): r for r in data['records']
               if r['dataset'] == dataset and r['profile'] == profile}
    d = next(d for d in data['datasets'] if d['id'] == dataset)
    included, excluded = [], {}
    for case in d['cases'] or []:
        rows = [records.get((case['id'], b)) for b in BACKENDS]
        if any(r is None or r['verdict'] != 'P' or metric_name not in r.get('metrics', {}) for r in rows):
            excluded[case['id']] = 'not all backends have passed with this measured property'
            continue
        if data['schema_version'] == 1 and case['id'] == 'v2-main':
            excluded[case['id']] = 'legacy schema1 V2 metric invalid: single-ended 1mV is not differential/common-mode budget'
            continue
        specs = {tuple((m['property'], m['unit'], m['budget']) for m in metric_components(r['metrics'][metric_name])) for r in rows}
        if len(specs) != 1:
            raise ValueError('unequal common-subset metric definitions')
        included.append(case['id'])
    maxima = {}
    for backend in BACKENDS:
        values = [m for c in included for m in metric_components(records[c, backend]['metrics'][metric_name])]
        maxima[backend] = None if not values else {
            'normalized': max(m['observed'] / m['budget'] for m in values),
            'original': [{'case': c, **m} for c in included for m in metric_components(records[c, backend]['metrics'][metric_name])]}
    return {'cases': included, 'excluded': excluded, 'maxima': maxima}


def count_cell(rows, targets):
    if not rows:
        return '不适用，选定分母 N=0'
    counts = Counter(r['verdict'] for r in rows)
    text = ' '.join(f'{v}{counts[v]}' for v in VERDICTS) + f' / N={len(rows)}'
    stale = sum(freshness(r, targets) == 'stale' for r in rows)
    return text + (f'; 需复验 {stale}' if stale else '')


def render(data, root=ROOT, target=None):
    targets = validate(data, root, target)
    lines = ['# 四后端行为证据', '', f"记录更新 {data['updated']}; 目标 EVAS {targets['evas']['revision']}。",
             '', 'P=限定性质通过，F=性质失败，U=确认不支持，X=执行失败，I=未决，T=未运行。',
             '正式连续时间资格另列，历史有限观测 P 不代表完整 DVS 资格。无耗时排名。', '']
    if data.get('refresh'):
        parent = data['refresh']['parent']
        lines += [f"integration 刷新：新 EVAS8 实测，Spectre8 复用原收据；另外16项T仅引用原未运行/失败预检，本轮无外部启动或环境重验。原快照 [{parent['path']}]({'../../../' + parent['path']})，SHA {parent['sha256']}。", '']
    if data['schema_version'] == 1:
        lines += ['历史 schema1：V2 单端1mV归一化指标已失效，明确排除B；本表不追认旧指标。新结论请使用 schema2 派生快照。', '']
    header = '| 组 | ' + ' | '.join(LABELS) + ' |'
    divider = '| --- | ' + ' | '.join('---' for _ in BACKENDS) + ' |'
    for d in data['datasets']:
        lines += [f"## {d['label']}", '', d['scope'], '']
        if d['state'] == 'pending':
            lines += ['分母 N=unknown，待冻结。', '', header, divider]
            for group in GROUPS:
                lines.append('| ' + group + ' | ' + ' | '.join('pending' for _ in BACKENDS) + ' |')
            lines.append('')
            for candidate in d.get('candidates', []):
                lines += [f"固定正确参考候选 {candidate['id']}，case={candidate['case_name']}，source revision={candidate['revision']}。",
                          f"源码 SHA={candidate['source_sha256']}；case SHA={candidate['case_sha256']}；checker SHA={candidate['checker_sha256']}。",
                          f"公共合同待冻结: {candidate['pending_contract']}。历史单后端开发入口 [{candidate['id']}]({ '../../../' + candidate['history_path'] })，不填四方分母。", '']
            continue
        for profile in d['profiles']:
            lines += [f"A 行为计数，profile={profile}，各后端 N={d['denominator']}。", '', header, divider]
            for group in GROUPS:
                ids = {c['id'] for c in d['cases'] if c['group'] == group}
                cells = [count_cell([r for r in data['records'] if r['dataset'] == d['id'] and r['profile'] == profile
                                    and r['backend'] == b and r['case'] in ids], targets) for b in BACKENDS]
                lines.append('| ' + group + ' | ' + ' | '.join(cells) + ' |')
            lines += ['', 'B 最大目标归一化观测误差，四后端相同通过子集。数字属于固定测量身份，需复验状态见A/逐配置记录。', '',
                      '| 性质 | 共同 n | ' + ' | '.join(LABELS) + ' |',
                      '| --- | ---: | ' + ' | '.join('---' for _ in BACKENDS) + ' |']
            for metric in ('voltage', 'time'):
                result = common_errors(data, d['id'], profile, metric)
                cells = []
                for b in BACKENDS:
                    value = result['maxima'][b]
                    if value is None:
                        cells.append('无数值比较')
                    else:
                        originals = value['original']
                        raw = max(m['observed'] for m in originals)
                        budgets = sorted({m['budget'] for m in originals})
                        cells.append(f"{value['normalized']:.6g}; {raw:.6g} {originals[0]['unit']}; budget={budgets}")
                lines.append(f"| {metric} | {len(result['cases'])} | " + ' | '.join(cells) + ' |')
                lines += [f"<!-- {metric} common cases: {json.dumps(result['cases'])}; excluded: {json.dumps(result['excluded'], ensure_ascii=False)} -->"]
            lines.append('')
    lines += ['## V1-V7 缺口与独立答案', '', '| 组 | 能力 | 尚未覆盖/边界 | 未来独立答案 |', '| --- | --- | --- | --- |']
    for group, gap in data['coverage'].items():
        caps = ', '.join(f'[{c}](../../../evas/docs/CAPABILITIES.md)' for c in gap['capabilities'])
        issues = ', '.join(f'[#{i}](https://github.com/BucketSran/vaEVAS/issues/{i})' for i in gap['issues'])
        lines.append(f"| {group} | {caps} {issues} | {gap['boundary']} | {gap['independent_answer']} |")
    lines += ['', '## 逐配置记录', '', '| 数据集 / 条件 / profile | 后端 | 判定 | 阶段 | 身份状态 | 证据/未运行原因 |',
              '| --- | --- | --- | --- | --- | --- |']
    for r in data['records']:
        refs = ', '.join(f"[{ref['kind']}]({ '../../../' + ref['path'] })" for ref in r.get('evidence', []))
        state = freshness(r, targets)
        lines.append(f"| {r['dataset']} / {r['case']} / {r['profile']} | {r['backend']} | {r['verdict']} | {r['stage']} | {state}; {r['accounting']} | {refs}; {r['reason']} |")
    lines += ['', '## 工具组成与许可证核实', '', '| 组件 | 实测版本/工件 | 上游声明 | 对实际组件的核实 |', '| --- | --- | --- | --- |']
    for component in data.get('components', []):
        link = component.get('license_source')
        declared = f"[{component['upstream_license']}]({link})" if link else component['upstream_license']
        lines.append(f"| {component['name']} | {component['version']}; {component['artifact']} | {declared} | {component['verification']} |")
    for candidate in data.get('candidate_links', []):
        lines += ['', f"候选 {candidate['name']}: {candidate['revision']}, {candidate['state']}; [{candidate['name']}]({candidate['url']})。"]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records', type=Path)
    parser.add_argument('--target', type=Path, help='latest targets; never changes the frozen records')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true', help='check records and optional generated table')
    args = parser.parse_args()
    text = render(load(args.records), target=load(args.target) if args.target else None)
    if args.check:
        if args.output and args.output.read_text() != text:
            raise ValueError('generated table is out of date')
        print('comparison records and table consistent')
    elif args.output:
        with args.output.open('x') as stream:
            stream.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
