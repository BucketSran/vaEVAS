"""Create a new snapshot from published historical summaries and an explicit unrun batch."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
from records import ROOT, BACKENDS, identity, load, sha, voltage_metrics
from freeze import SELECTED, conditions, input_identity, runtime_identity, save

HISTORICAL = 'experiments/backends/dvs2-four-backend-validation/results/matrix.json'
RECEIPT = 'experiments/backends/dvs2-four-backend-validation/results/RECEIPT.json'


def group(c):
    if c['kind'] in ('e1',): return 'V3'
    if c['kind'] in ('e2',): return 'V4'
    if c['kind'] in ('c1', 'c2'): return 'V7'
    if c['kind'] in ('d1', 'd2'): return 'V6'
    if c['kind'] == 's1': return 'V1'
    return 'V' + c['id'][1]


def dataset(name, label, cases, profiles, scope):
    return {'id': name, 'label': label, 'state': 'frozen', 'cases': cases,
            'profiles': profiles, 'denominator': len(cases), 'case_manifest_sha256': identity(cases), 'scope': scope}


def create():
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    historical = load(ROOT / HISTORICAL)
    receipt = load(ROOT / RECEIPT)
    tools = load(ROOT / 'experiments/archive/dvs2-starter-pilot/results/TOOL_IDENTITIES.json')
    spectre_receipt = load(ROOT / 'experiments/backends/dvs2-spectre-validation/results/RECEIPT.json')
    ids = {'spectre': spectre_receipt['binary_sha256'], 'openvaf_ngspice': identity({k: tools['images'][k]['config_id']
            for k in ('openvaf_runtime', 'ngspice')}), 'gnucap': identity({'gnucap': tools['images']['gnucap']['config_id']}),
           'evas': tools['images']['evas']['config_id']}
    targets = {b: {'revision': 'unknown', 'runtime_identity': ids[b]} for b in BACKENDS}
    targets['evas'] = {'revision': revision, 'runtime_identity': runtime_identity()}
    lookup = {c['id']: c for c in conditions()}
    frozen = [{'id': c['id'], 'group': group(c), 'tags': [],
               'input_identity': identity({'historical_input_manifest': receipt['input_manifest_sha256'], 'case': c['id']})}
              for c in lookup.values()]
    batch = [{'id': name, 'group': group(lookup[name]), 'tags': [], 'input_identity': input_identity(lookup[name])}
             for name in SELECTED]
    datasets = [{'id': 'paper-new', 'label': '新论文评价集，pending', 'state': 'pending', 'denominator': None,
                 'cases': None, 'profiles': ['base'], 'scope': '今晚尚未冻结。旧31条件与确认14/14均不填入此集。'},
                dataset('development31-20260928', '历史31开发条件', frozen, ['base', 'fine'],
                        '2026-09-28 固定有限导出观测；正式连续时间资格 I。EVAS为旧0.8.7，当前目标需复验。'),
                dataset('cmp8-base', '今晚8开发条件，32配置', batch, ['base'],
                        '固定8条件×4后端，基础档；未执行不得继承旧矩阵分数。'),
                {'id': 'application-reference', 'label': 'C 固定正确参考应用回放', 'state': 'pending', 'denominator': None,
                 'cases': None, 'profiles': ['base'], 'scope': '应用回放条件及同源四后端编码尚未冻结。错误候选仅用于校准，分母 unknown。'}]
    mapping = {'observations_within_targets': 'P', 'observed_violation': 'F', 'unresolved': 'I',
               'observation_invalid': 'I', 'compile_failed': 'X', 'compile_timeout': 'X',
               'execution_failed': 'X', 'runtime_timeout': 'X', 'missing_waveform': 'I'}
    records = []
    for old in historical['records']:
        status = old['analysis']['status']
        records.append({'dataset': 'development31-20260928', 'case': old['condition'], 'backend': old['backend'],
                        'profile': old['profile'], 'input_identity': next(c['input_identity'] for c in frozen if c['id'] == old['condition']),
                        'verdict': mapping[status], 'qualification': 'I', 'stage': 'analysis' if status in
                        ('observations_within_targets', 'observed_violation', 'unresolved', 'observation_invalid') else old.get('failure_stage', 'execute'),
                        'reason': status, 'accounting': 'reused', 'reuse_justification': 'Historical summary retained with original input/runtime/checker identities; no rerun or raw reanalysis.',
                        'measurement': {'revision': 'unknown', 'runtime_identity': ids[old['backend']],
                                        'run_id': old['source_run_id'], 'version': tools['tool_versions'].get(
                                            {'spectre': 'spectre', 'evas': 'evas_package', 'openvaf_ngspice': 'openvaf_cli_self_report', 'gnucap': 'gnucap_environment_snapshot'}[old['backend']])},
                        'checker_identity': receipt['frozen_sources']['experiments/dvs2-spectre-validation/check_results.py'],
                        'evidence': [{'path': HISTORICAL, 'sha256': sha(ROOT / HISTORICAL), 'kind': 'analysis'},
                                     {'path': RECEIPT, 'sha256': sha(ROOT / RECEIPT), 'kind': 'receipt'}],
                        'availability': {'compact': 'repository-contained', 'raw': 'private historical archive; local presence not assumed'},
                        'metrics': {}})
        records[-1]['observation_binding'] = {'path': HISTORICAL, 'sha256': sha(ROOT / HISTORICAL),
            'format': 'matrix', 'selector': {k: old[k] for k in ('backend', 'condition', 'profile', 'source_run_id')}}
        records[-1]['metrics'] = voltage_metrics(old['condition'], old['analysis'], 2)
    for c in batch:
        for b in BACKENDS:
            records.append({'dataset': 'cmp8-base', 'case': c['id'], 'backend': b, 'profile': 'base',
                            'input_identity': c['input_identity'], 'verdict': 'T', 'qualification': 'I', 'stage': 'launch',
                            'reason': 'Reserved for coordinated CMP32 execution; no launch yet.', 'accounting': 'unrun',
                            'measurement': None, 'metrics': {}, 'evidence': []})
    gaps = {
        'V1': (['LANG', 'LIN'], [65], '更广静态比较/分段与参数语法未构成独立新集。', '按每个分段写代数映射，并在阈值两侧/等号处独立计算电压。'),
        'V2': (['LIN', 'COMPOSE'], [68], '本范围没有有限负载、CMRR/PSRR器件网络。', '固定参考平移与差/共模的代数不变量；若扩展负载则须另定电流契约。'),
        'V3': (['CROSS', 'EVENT-ORDER'], [70], '双向自换向的根窗口仍拒绝；D7候选未测。', '使用有理数根窗口与单一一致事件历史；端点案例须独立证明合法交叉次数。'),
        'V4': (['LANG', 'EVENT-ORDER'], [65], '量化边界、位序和离散递推未冻结。', '从外部电压/时钟构造离散状态递推，明确复位优先级和沿上的采样值。'),
        'V5': (['TRANSITION', 'ABSDELAY', 'SLEW', 'TIMER'], [62], '动态参数、门控与一般嵌套延迟仍缺。', '移位历史或分段斜率限制的解析轨迹，覆盖起始历史与边沿中断。'),
        'V6': (['DYNAMICS'], [66], '长期相位、一般极点/函数与DAE事件组合未覆盖。', '积分闭式解、稳定滤波完整启动响应和累计误差上界。'),
        'V7': (['COMPOSE', 'NONLINEAR'], [62, 63], '更广离散选择组合、任意多实例与矢量网表尚非比较支持。', '独立联立关系残差及唯一解证明；交换实例顺序不改变物理状态。')}
    components = [
        {'name': 'Spectre', 'version': tools['tool_versions']['spectre'], 'artifact': ids['spectre'],
         'upstream_license': 'unknown', 'license_source': None, 'verification': 'unknown; installed commercial license terms not retrieved'},
        {'name': 'OpenVAF-R', 'version': 'OpenVAF-reloaded unknown; package label v24.0.2mob',
         'artifact': next(iter(tools['compiler_artifact_sha256'].values())),
         'upstream_license': 'GPL-3.0', 'license_source': 'https://github.com/OpenVAF/OpenVAF-Reloaded/blob/mob/LICENSE',
         'verification': 'upstream fork identified; installed license/artifact-source mapping remains unknown'},
        {'name': 'ngspice', 'version': tools['tool_versions']['ngspice'], 'artifact': tools['images']['ngspice']['config_id'],
         'upstream_license': 'Modified BSD; component exceptions', 'license_source': 'https://ngspice.sourceforge.io/faq.html',
         'verification': 'upstream declaration checked 2026-10-06; installed component license inventory remains unknown'},
        {'name': 'Gnucap', 'version': 'unknown; environment label 2026.07.29',
         'artifact': 'cc96c5fca3772f20cd143c38105aa05d97af5bcd661b066bd3abc2d0ece41478',
         'upstream_license': 'GPL-3.0', 'license_source': 'https://github.com/gnucap/gnucap/blob/develop/COPYING',
         'verification': 'upstream COPYING checked; installed build/source-license mapping remains unknown'},
        {'name': 'modelgen-verilog', 'version': 'unknown',
         'artifact': 'ad7a0efcaaa3b0399bd4eafe89d88004c096e15a15d17f9344bf73a59e8a6561',
         'upstream_license': 'GPL-3.0-or-later; generated outputs follow input license',
         'license_source': 'https://github.com/gnucap/gnucap-modelgen-verilog/blob/develop/README',
         'verification': 'upstream component separately checked; installed license mapping remains unknown'},
        {'name': 'EVAS', 'version': 'current source target 0.13.0; measured historical 0.8.7',
         'artifact': targets['evas']['runtime_identity'], 'upstream_license': 'unknown', 'license_source': None,
         'verification': 'no explicit license file located in this checkout; target source hash is not a measured kernel'}]
    data = {'schema_version': 2, 'updated': '2026-10-06', 'targets': targets, 'datasets': datasets,
            'records': records, 'coverage': {g: dict(zip(('capabilities', 'issues', 'boundary', 'independent_answer'), values)) for g, values in gaps.items()},
            'tools': tools, 'components': components, 'candidate_links': [],
            'limits': ['Voltage common subset is restricted to V1 absolute-output 1mV and V2 differential 2mV/common-mode 1mV contracts; no common measured timing property is declared.',
                       'The maintained current EVAS source is a target, not new simulator evidence.']}

    from derive import freeze_metric_contract
    freeze_metric_contract(data, ROOT, revision)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    save(args.output, create())
