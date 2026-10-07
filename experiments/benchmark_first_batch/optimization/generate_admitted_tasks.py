"""Generate formal optimization tasks only after reviewed actual admission.

No pending task directories are made. The generator consumes actual paired
analysis plus independent full-functional calibration, and never runs Spectre.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
LOCAL=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'benchmark/checkers'))
from first_batch_optimization import canonical_case_sha256,validate_admitted_policy,validate_performance_source

FAMILIES={'optimize-vco-step':'vco_boundstep','optimize-flash-thresholds':'flash_thresholds',
          'optimize-power-monitor':'power_monitor','optimize-sar-calendar':'sar_calendar',
          'optimize-uart-calendar':'uart_calendar'}

SPECS={
'vco_boundstep':('连续相位PLL正弦VCO', '''模块 `tuning_vco(control,out)`。fmin=4MHz、fmax=400MHz，控制量钳在0..1；
频率为 fmin+(fmax-fmin)*clamp(control)。从零相位开始积分频率，不得将相位写成f(t)*t。
输出 offset+amplitude*sin(2*pi*phase)，默认offset=0.6V、amplitude=0.5V。
恒频必须保留每周期至少64个真实时间点；相邻解析相位前进不得超过1/64+1e-10周期。
变频/钳位条件核验全部真实点和独立均匀探针，解析电压误差不超过3mV。规定真实
低频负载20us、7.96MHz、159.2周期，另检查连续调谐与高频端。'''),
'flash_thresholds':('采样非均匀阈值flash ADC', '''模块 `offset_flash(vin,clock,code)`。255个有序阈值：
vref*(k/256+skew*(k/256)*(1-k/256))，k=1..255，skew在[-0.3,0.3]。
上升clock阈值0.5V时采样，码是输入不小于的阈值个数，归一化为code/255，初码0。
采样间保持，delay=0.2ns、线性rise=0.3ns须保留；sample/hold及边沿电压误差0.3mV。
固定负载100us、100MHz采样、10000次转换；另检查不同vref和正负skew。'''),
'power_monitor':('电源资格时间与迟滞监督', '''模块 `supply_supervisor(supply,enable)`。连续电压不低于on_voltage=1.0V
达到qualification=5us才使能；已使能时在off_voltage=0.85V到1.0V之间保持，低于0.85V
及时关断。短毛刺不能累积资格，失去资格后须重新计时。初始高电压也须等待资格。
输出线性rise=0.5ns；独立解析阈值/资格边沿误差不超过2ns，稳态1mV，有限边沿须保留。
固定负载100us电源启动/迟滞保持/关断；另测毛刺恢复、初始高及qualification=3us。
给定基线1ns轮询已有浮点比较裕量，满足合同；本题优化不包括修复该数值边界。'''),
'sar_calendar':('传感器12bit SAR转换控制器', '''模块 `sensor_sar(vin,start,reset,busy,valid,code,dac)`。空闲start上升0.5V时
采样并保持vin，依次12个bit_period=50ns执行MSB-first试探；dac公开每位试探电压，
不能跳过逐位控制阶段。码为floor(vin/vref*4096)，钳0..4095；code以4095归一化，
dac以4096归一化。busy时忽略start，reset高于0.5V取消并清输出；完成code保持，
valid完成置位、下个接受start/reset清除。输出线性rise=0.5ns，事件误差2ns、电压4uV。
固定负载100us、20次转换、240次位决策；另测busy冲突/reset、80ns位周期与不同vref。
输入在转换期间改变，必须保持开始时的采样；公开dac阶梯也逐位评分。'''),
'uart_calendar':('异步8N1 UART接收控制器', '''模块 `uart_receiver(rx,reset,busy,valid,error,data,shift)`。空闲下降start阈值0.5V
开始，半bit确认start仍低后按nominal bit中心接收8位LSB-first，stop中心判断正确/错误。
短假start须取消，reset取消并清所有输出。正确stop才更新data和valid，错误stop保持旧data
并置error；valid/error保持至下一接受start/reset。shift公开每位移入进度、start/reset清零。
data/shift按255归一化，输出线性rise=10ns必须保留。事件误差0.08bit、稳定电压4uV。
固定负载115200baud、100ms、10帧/80数据位、1次假start；另测framing/reset、57600baud。
发送时钟漂移±2%，假start持续0.2/0.3bit；不含恰落采样中心的额外毛刺。给定模型是
公开简化中心采样合同，不要求FIFO或多数表决等未定义功能。''')}


def sha(data):return hashlib.sha256(data).hexdigest()


def functional_records(document):
    for record in document.get('records',[]):
        if 'run_name' in record:
            name=record['run_name'];task=next((task for task in FAMILIES if name.startswith(task+'-')),None)
            if task is None:continue
            role='baseline' if '-baseline-' in name else 'reference'
            if 'replay' in record:
                yield task,role,record['case'],record['candidate_sha256'],record['replay']['passed']
            else:
                for case in record.get('cases',[]):yield task,role,case['name'],record['candidate_sha256'],case['passed']
        elif 'task_id' in record:
            source=record.get('statistics',{}).get('source_identity',{}).get('source_sha256')
            yield record['task_id'],record['role'],record['case'],source,record['passed']


def admission_policy(task,config,paired,paired_sha,cases,family):
    if config.get('admitted') is not True:raise ValueError(task+': reviewed admission is missing')
    summary=paired.get('paired_summaries',{}).get(task)
    if paired.get('kind')!='offline_analysis_of_actual_spectre_jobs' or not summary or summary['pairs']<5:
        raise ValueError(task+': actual five-pair evidence missing')
    if config.get('metric') not in ('intrinsic_cpu_s','accepted_steps'):raise ValueError('unsupported admitted metric')
    policy=dict(config,admission_evidence_sha256=paired_sha,pairs=5,allow_private_condition_packets=True,
                case_inventory=[dict(name=c['name'],performance=bool(c.get('performance')),case_sha256=canonical_case_sha256(c)) for c in cases])
    validate_admitted_policy(policy)
    expected={role:sha((family/(role+'.va')).read_bytes()) for role in ('baseline','reference')}
    attempts=paired['attempts'];records=paired['records']
    measurement=[(a,r) for a,r in zip(attempts,records) if a['task_id']==task and a['phase']=='measurement']
    if len(measurement)<10 or [a['side'] for a,_ in measurement]!=['baseline','reference']*(len(measurement)//2):
        raise ValueError(task+': declared actual trials did not alternate AB')
    perf=next(c for c in cases if c.get('performance'))
    for a,r in measurement:
        if r['source_sha256']!=expected[a['side']] or r['condition_id']!=perf['name'] or r['functional_result'].get('passed') is not True:
            raise ValueError(task+': source/functional/workload identity mismatch')
        if r['solver_argv'][-1]!='+mt=1':raise ValueError(task+': backend thread setting changed')
    hosts={r['native_statistics'].get('native_host') for _,r in measurement}
    if None in hosts or len(hosts)!=1:raise ValueError(task+': actual same-host identity missing')
    metrics=summary['metrics'][policy['metric']]
    ratio=metrics['reference']['median']/metrics['baseline']['median']
    winning=sum(b>a for b,a in zip(metrics['baseline']['values'],metrics['reference']['values']))
    if ratio>policy['max_median_ratio'] or winning<policy['min_winning_pairs']:
        raise ValueError(task+': actual pair results do not meet proposed threshold')
    passed=set()
    for evidence in config.get('functional_evidence',[]):
        document=json.loads(Path(evidence).read_text())
        for t,role,name,source,ok in functional_records(document):
            if t==task and source==expected[role] and ok is True:passed.add((role,name))
    required={(role,c['name']) for role in ('baseline','reference') for c in cases}
    if not required<=passed:raise ValueError(task+': full independent functional calibration for both sources missing')
    # Functional calibration paths are publication evidence, not runtime policy.
    policy.pop('functional_evidence',None)
    return policy


def write_task(task,policy,family,destination,shared_runtime):
    destination.mkdir(parents=True,exist_ok=False)
    for sub in ('environment/public','solution','tests/negatives'):(destination/sub).mkdir(parents=True)
    title,contract=SPECS[family.name]
    metric='intrinsic tran CPU' if policy['metric']=='intrinsic_cpu_s' else 'native accepted tran steps'
    instruction=f'''# 优化{title}的仿真实现

将 `/work/public/starter.va` 改成 `/work/dut.va`，保持以下电路行为并降低给定固定负载的实际仿真成本。
只提交dut.va，不写额外结果文件。公开输入包含原始合格基线和visible.scs，可用其自测。

{contract}

性能评分使用Spectre 21.1.0.509.isr12、`+mt=1`、psfascii，网表固定reltol=1e-6、
vabstol=1e-9、iabstol=1e-14、errpreset=conservative。不能改网表、容差、真实工作量、
输出有限边沿或规定分辨率取得成绩。最终满分要求所有功能条件通过，且同一job同机执行
的两侧warmup与五对交替求解每次都通过独立波形判据。性能条件可在其他功能条件之前
执行，但任何功能失败都会使整题失败；失败运行不能进入计时分母。

规定{metric}候选中位数/基线中位数不超过{policy['max_median_ratio']:.6g}，
且五对中至少{policy['min_winning_pairs']}对候选成本低于基线。CPU仅取原生intrinsic tran分项，
编译/许可证/启动/网络单独记录，不参与该CPU指标；steps只能取原生日志，PSF点数不能代替。
未变更基线可通过功能但不能取得性能分。终评同时保留端到端过程计时、原生版本/负载及全部原始波形。

允许重新组织内部实现；所有公开接口/参数、采样/状态/波形合同保持。禁止active日志输出及
仿真终止/控制system tasks，防止伪造native统计或提前退出。标准disciplines.vams/constants.vams可include；
无额外非声明include，宏、系统调用、环境读取和外部文件读取不在提交合同内。参考优化源码不在公开输入中。
'''
    (destination/'instruction.md').write_text(instruction)
    (destination/'task.toml').write_text(f'''schema_version = "1.4"
[metadata]
name = "{task}"
category = "verilog-a"
action = "simulation-implementation-optimization"
source_group = "original-{family.name}-optimization"
[agent]
timeout_sec = 1800
[verifier]
timeout_sec = 900
[environment]
build_timeout_sec = 600
cpus = 1
memory_mb = 2048
storage_mb = 2048
''')
    (destination/'environment/Dockerfile').write_text('FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c\nWORKDIR /work\nCOPY public/ /work/public/\nRUN mkdir -p /work/output\n')
    shutil.copyfile(family/'baseline.va',destination/'environment/public/starter.va')
    shutil.copyfile(family/'reference.va',destination/'solution/dut.va')
    shutil.copyfile(family/'baseline.va',destination/'tests/baseline.va')
    cases=json.loads((family/'cases.json').read_text());perf=next(c for c in cases if c.get('performance'))
    (destination/'environment/public/visible.scs').write_text(perf['netlist'].replace('"dut.va"','"/work/dut.va"'))
    (destination/'environment/public/README.md').write_text('starter.va是实际功能校准合格的原始基线；visible.scs是固定性能负载。\n提交/work/dut.va，保持题面所有参数与电路行为。参考优化代码不公开。\n')
    shutil.copyfile(family/'evaluate.py',destination/'tests/evaluate.py')
    shutil.copyfile(shared_runtime,destination/'tests/circuit_task.py')
    for name in ('adc_linearity.py','first_batch_optimization.py'):shutil.copyfile(ROOT/'benchmark/checkers'/name,destination/'tests'/name)
    for name in ('verify.py',):shutil.copyfile(LOCAL/'scoring_prototype'/name,destination/'tests'/name)
    (destination/'tests/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    (destination/'tests/contract.json').write_text(json.dumps(dict(candidate_files=['dut.va'],output_files=[]),indent=2)+'\n')
    (destination/'tests/performance.json').write_text(json.dumps(policy,indent=2)+'\n')
    for p in sorted((family/'negative').glob('*.va')):shutil.copyfile(p,destination/'tests/negatives'/p.name)
    (destination/'tests/test.sh').write_text('#!/bin/sh\nset -eu\npython3 -B /tests/verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"\n')
    (destination/'solution/solve.sh').write_text('#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
    for name in ('tests/test.sh','solution/solve.sh'):(destination/name).chmod(0o755)
    (destination/'SOURCE.md').write_text(f'''# 来源与冻结范围

{title}模型由本次公开电路合同独立编写，没有复制来源许可不明的历史VA。
SOURCE不把旧power基线计时错误称作优化；已修合法基线重新实际校准后才准入。
本题属于Spectre扩展集，未声称开源后端可重评分。完整校准范围与失败记录保存在
experiments/benchmark_first_batch/optimization，五对准入证据SHA256为
`{policy['admission_evidence_sha256']}`。该哈希绑定归档、源码、判据和实际计时；
题数/Agentic/负例正式校准状态由首批inventory维护，不由目录存在推导完成。

性能专用执行profile须保留完整原始PSF，建议至少1GiB收集上限及900s，
不能使用原功能profile256MiB上限，也不删波形片段绕开资源限制。
''')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--admission',type=Path,required=True)
    parser.add_argument('--tasks-root',type=Path,default=ROOT/'benchmark/tasks')
    parser.add_argument('--shared-runtime',type=Path,default=ROOT/'benchmark/checkers/circuit_task.py')
    args=parser.parse_args();admission=json.loads(args.admission.read_text())
    paired_path=Path(admission['paired_evidence']);raw=paired_path.read_bytes();paired=json.loads(raw)
    plans=[]
    for task,config in admission['tasks'].items():
        if task not in FAMILIES:raise ValueError('unknown task '+task)
        family=LOCAL/FAMILIES[task];cases=json.loads((family/'cases.json').read_text())
        policy=admission_policy(task,config,paired,sha(raw),cases,family)
        destination=args.tasks_root/task
        if destination.exists():raise FileExistsError('never overwrite existing task '+str(destination))
        plans.append((task,policy,family,destination))
    if not plans or not args.shared_runtime.is_file():raise ValueError('no admitted task or missing declared runtime')
    for task,policy,family,destination in plans:write_task(task,policy,family,destination,args.shared_runtime)
    print('Generated admitted tasks: '+', '.join(task for task,_,_,_ in plans))

if __name__=='__main__':main()
