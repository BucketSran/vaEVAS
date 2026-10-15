"""Extract compact author receipts; preserve all actual predecessor attempts."""
from pathlib import Path
import argparse,hashlib,json,re,tarfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
from audit_delivery import write as audit_delivery
import sys as _benchmark_sys
from pathlib import Path as _BenchmarkPath
_benchmark_sys.path.insert(0, str(_BenchmarkPath(__file__).resolve().parents[3]))
from experiments.benchmark_paths import material_path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def receipt(prepared):
 p=ROOT/prepared;s=json.loads((p/'summary.json').read_text());pre=json.loads((p/'preparation.json').read_text());conditions=[]
 for c in s['conditions']:
  archive=Path(c['archive'])
  with tarfile.open(archive) as t:data=t.extractfile('run/work/verifier/report.json').read()
  assert hashlib.sha256(data).hexdigest()==c['report_sha256']
  r=json.loads(data);version=re.search(r'sub-version\s+(\S+)',r['spectre_version'])
  conditions.append(dict(condition=c['condition_id'],job_id=c['job_id'],execution=c['execution'],score=c['score'],report_status=r['status'],report_sha256=c['report_sha256'],archive_sha256=digest(archive),archive=str(archive.relative_to(ROOT)),spectre_version=version.group(1) if version else 'unknown',candidate_sha256=r['candidate_sha256'],checker_files=r['checker_files'],cases=r['cases']))
  # Simulator logs may contain private server details and are not compact evidence.
  for case in conditions[-1]['cases']:
   for k in ['log_tail','candidate_files','argv']:case.pop(k,None)
 return dict(prepared=str(p.relative_to(ROOT)),preparation_sha256=digest(p/'preparation.json'),source_identity=pre['source_identity'],task=s['task_id'],candidate_sha256=s['candidate_sha256'],criteria_sha256=s['criteria_sha256'],all_selected_conditions_graded=s['all_conditions_graded'],all_selected_conditions_passed=s['reference_passed'],has_selected_graded_failure=s['has_graded_failure'],conditions=conditions)

def main():
 manifest=json.loads((OUT/'manifest.json').read_text());final=[]
 for row in manifest['calibrations']:
  tid=Path(row['task']).name;v=row['variant']
  run='r4'
  if v=='reference':run='r3' if 'dac-linearity' in tid else 'r8'
  if 'adc-spectrum' in tid:run='r5'
  if 'dac-linearity' in tid and v=='ignore-order':run='r6'
  if v in ['bit-order','harmonics-as-fundamental']:run='r7'
  r=receipt(Path('runs')/('benchmark-next-converter-'+run)/tid/v)
  candidate=material_path(ROOT, row['candidate'])/'dut.va';assert all(c['candidate_sha256']==digest(candidate) for c in r['conditions']),(tid,v,'source changed')
  r['dut_file_sha256']=digest(candidate)
  expected=row['case_names'] or [c['name'] for c in json.loads((material_path(ROOT, row['task'])/'tests/cases.json').read_text())]
  assert set(expected)=={c['condition'] for c in r['conditions']}
  r.update(variant=v,expected_pass=row['expected_pass'],selected_case_names=expected,calibration_met=r['all_selected_conditions_graded'] and (r['all_selected_conditions_passed'] if row['expected_pass'] else r['has_selected_graded_failure']))
  final.append(r)
 history=[]
 for tid in ['segmented','thermometer','nonideal','subradix']:
  r=receipt(Path('runs/benchmark-next-converter-r2')/('v3-converter-'+tid)/'reference');r['disposition']='early DAC instruction bytes were not retained; superseded by full current-source snapshot and r8 calibration';history.append(r)
 for run,tid,v,reason in [('r2','v3-converter-dac-linearity','reference','predecessor3-condition contract, before reset-truncated condition added'),('r2','v3-converter-adc-spectrum','reference','fixture port ordering defect, retained failures'),('r4','v3-converter-dac-linearity','ignore-order','semantically identical predecessor candidate with trailing whitespace')]:
  r=receipt(Path('runs')/('benchmark-next-converter-'+run)/tid/v);r['disposition']=reason;history.append(r)
 p=ROOT/'runs/benchmark-next-converter-calibration/v3-converter-segmented/reference';pre=json.loads((p/'preparation.json').read_text());res=json.loads((p/'results.json').read_text());c=res[0];ar=p/'remote'/c['job_id']/'archive/job.tar.gz'
 with tarfile.open(ar) as t:data=t.extractfile('run/preflight/report.json').read()
 history.append(dict(prepared=str(p.relative_to(ROOT)),job_id=c['job_id'],execution=c['result']['execution'],score=c['result'].get('score'),candidate_sha256=pre['candidate']['candidate_sha256'],criteria_sha256=pre['criteria_sha256'],archive_sha256=digest(ar),preflight_sha256=hashlib.sha256(data).hexdigest(),preflight=json.loads(data),disposition='old deployment approved task-scope gate stopped before simulation'))
 result=dict(spec=151,task_count=6,formal_conditions=17,variant_count=len(final),final_executed_positions=sum(len(r['conditions']) for r in final),all_registered_calibrations_met=all(r['calibration_met'] for r in final),no_model_experiments=True,final=final,historical_attempts=history,limits=['Spectre extension set only, open-source equivalent not verified','Synthetic ADC record, no actual measured ADC source','Negative candidates run selected targeted conditions only, unrun conditions remain unknown','Actual raw archives kept in ignored runs; compact source and report identities published'])
 result['transport_interruptions']=[dict(job_id='bf-7a09b994dfa94d519457-repeat-code',operation='job-status',timeout_seconds=30,recovery='same prepared directory and same job ID; no duplicate submission',operator_log_sha256=digest(ROOT/'runs/benchmark-next-converter-r4/v3-converter-dac-linearity/ignore-order/operator.log'))]
 plans=['runs/benchmark-next-converter-calibration/reference-plan.json.results.json','runs/benchmark-next-converter-r2/reference-plan.json.results.json','runs/benchmark-next-converter-r5/final-plan.json.results.json','runs/benchmark-next-converter-r5/resume-plan.json.results.json','runs/benchmark-next-converter-r7/plan.json.results.json','runs/benchmark-next-converter-r8/reference-plan.json.results.json']
 result['queue_attempts']=[dict(path=f,sha256=digest(ROOT/f),statuses=[row['status'] for row in json.loads((ROOT/f).read_text())]) for f in plans]
 result['delivery_reuse_analysis']=audit_delivery(final)
 result['task_source_snapshot']=json.loads((OUT/'task-snapshot.json').read_text())
 (OUT/'author-calibration.json').write_text(json.dumps(result,indent=2)+'\n')
 assert result['all_registered_calibrations_met'], 'calibration gap remains'
 lines=['# 转换器作者校准','',f"规格 #151 的六题、{len(final)} 个登记变体和 {result['final_executed_positions']} 个最终作者条件位置均完成。12个正确变体覆盖全部17个正式条件，22个语义错版各运行预先登记的目标条件并被独立判据拒绝。未运行的错版条件保持未知，不能据此称完整任务得0分。没有模型实验。",'', '| 任务 | 正确实现条件位置 | 针对负例位置 | 状态 |','| --- | --- | --- | --- |']
 for tid in sorted({r['task'] for r in final}):
  group=[r for r in final if r['task']==tid];good=sum(len(r['conditions']) for r in group if r['expected_pass']);bad=sum(len(r['conditions']) for r in group if not r['expected_pass']);lines.append(f'| {tid} | {good} | {bad} | 完成 |')
 lines.extend(['','固定后端实际返回Spectre sub-version21.1.0.509.isr12。所有最终条件均产生returncode0的完整仿真和graded行为判定；负例拒绝不是编译失败。每个报告绑定候选、独立checker、台架、波形、原始归档SHA，完整身份见[机器收据](author-calibration.json)与[材料清单](files-sha256.json)。','', '正式题包已补入与冻结准备完全同字节的运行时和PSF读取依赖。六题分别复制到隔离目录直接执行原tests/test.sh --help，均成功启动参数入口。这项检查不证明完整Harbor容器Trial。34份冻结准备的204项可执行评分资产逐一与交付版本相同。题面单位说明的精确差异、逐题旧新SHA及独立离线分析身份见[交付复用审计](delivery-reuse.json)。早期四DAC参考的旧题面只留SHA，原文差异未知，原结果移入历史。四DAC参考按当前题面和完整题包重新执行全部8条件并通过。其余可恢复的文字差异仅为单位说明，按不变的可执行判据复用。[完整题包快照](task-snapshot.json)保留六题91个文件的清单和归档身份。','', 'DAC判据从公开单元权重与实际采样时刻求和，检查保持区间。扫描从固定DUT实际输出建立端点直线；频谱checker用余弦自相关功率，VA参考分别使用在线DFT和整记录批量DFT。已知单音加十分之一幅度谐波的20dB真值及人工端点例子另由本地4项检查校准。','', '最终正确实现的最大实测误差如下。公开容差仍是1mV、DNL/INL1e-3LSB、0.03dB、ENOB0.006bit；1ns建立窗口之后检查实际波形，未按模型表现调整阈值。','', '| 输出 | 正确实现最大绝对误差 |','| --- | --- |'])
 errors={}
 for r in final:
  if r['expected_pass']:
   for c in r['conditions']:
    for case in c['cases']:
     for n,e in case.get('errors',{}).items():errors[n]=max(errors.get(n,0),e)
 for n,e in sorted(errors.items()):lines.append(f'| {n} | {e:.6g} |')
 lines.extend(['','历史尝试保留18个独立位置，包括早期四DAC题面原字节缺失后被当前参考校准取代的8个位置、初版部署的1个未进入仿真的前缀资格失败、扫描补条件前3个参考位置、频谱端口连接错误的5个位置、以及同语义尾空白错版的1个位置。它们不替代最终56个位置。一次状态查询SSH超时按原作业ID恢复，不另计仿真位置。原始资料留在忽略runs目录，机器收据保留其身份。','', '原solution/solve.sh保持原字节，通过固定路径映射cp执行，其产物作为真实参考候选。这里证明作者参考脚本产物和Spectre评分入口，不宣称已执行新题完整Harbor容器Trial。','', 'E1/E2四个旧来源分别建题。E3审计并保留va08原ADC直方图资产，新题补DAC端点扫描；E4复用旧64点频谱，不重计这段方法为新来源。344和190只保留准备资产，见[资产审计](asset-audit.md)和[来源身份](provenance.json)。','', '本批仍是Spectre扩展集，开源同题等价未验证。ADC记录为行为合成，未取得实测器件记录；非相干窗口、噪声统计和DEM不在本规格核心验收。'])
 (OUT/'author-calibration.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({k:result[k] for k in ['task_count','formal_conditions','variant_count','final_executed_positions','all_registered_calibrations_met']}))
if __name__=='__main__':main()
