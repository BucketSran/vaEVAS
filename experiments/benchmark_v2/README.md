# 五类工程任务的实施与校准

本目录支撑规格 #133–#137 的完整 v2 实施。当前任务和证据分别归属
`spec_modeling/`、`data_modeling/`、`extension_integration/`、
`diagnosis_repair/`、`testing_characterization/`。
覆盖范围是32个P1来源及各规格规定的外部代表，具体任务量由独立工程目标决定。
参考解运行、checker校准、模型试做和发布资格分别记录，旧first_batch成绩不代替本轮证据。

## 固定后端入口

`benchmark/checkers/v2_runtime.py` 接受固定 Spectre 台架及独立
`evaluate(rows, case, work)` 回调。输入/输出协议见下表。

| 材料 | 内容 |
| --- | --- |
| tests/contract.json | `candidate_files`，首项 `dut.va`，以及报告文件清单 |
| tests/cases.json | 唯一 `name`、`netlist`、`stop`、`signals`，可选不可修改 `support` 文本 |
| verifier 回调 | 接收实际时间/电压行、case合同和本条件的目录；返回布尔 `passed` 与测量细节 |
| report.json | 条件状态、候选/台架/checker/波形身份、后端版本、诊断和可评分时的reward |

候选源码按原字节执行，不继承历史词法限制。明确缺失候选文件属于提交合同错误。
仿真非零退出、超时、证据不足或checker故障保留未评分状态，需诊断后才能归因，
不自动得到零分或通过。所有必需条件有独立行为判定时，才产生正式0/1分数。
`$strobe`文本可供测量checker读取，但不能自行证明环境故障或任务通过。
台架、候选或配套文件在执行后发生变化会使该次证据无效。

这个入口负责题目评分，不是进程隔离层。共享执行、隔离、公开反馈、远端作业和
封存回收由 circuit harness 提供。作者校准可以使用可信参考与人工错版；
Agent提交必须使用经过验证的隔离部署，不能把目录约定或执行后哈希当作读写隔离。

## 准备与执行

```sh
python3 -B experiments/benchmark_v2/runtime.py \
  --task /absolute/task --candidate /absolute/candidate/dut.va \
  --output /absolute/new/prepared --harness-checkout /absolute/harness
```

准备复用既有first_batch包封存逻辑，但任务版本独立为
`circuit-benchmark-v2-development`。每个case一个固定作业，现有任务默认版本不变。
运行继续使用 `experiments/benchmark_first_batch/runtime.py execute` 及其恢复协议，
不要在状态未知时重复提交新作业ID。部署配置和批量原始产物留在忽略的 `runs/`。

Spectre全局最多4并发，包括参考校准和模型终评。由同一协调者串联所有队列；
参考通过及编译失败均不能计作语义错版被独立checker拒绝。

`test_runtime.py` 使用独立进程fixture检验评分/未评分协议、源码完整性和文件冲突。
这些测试不执行真正的Spectre，不构成电路校准证据。

首轮[运行记录](runtime-calibration.json)保留10个作者参考候选的完整分母：
5个任务的全部条件通过，2个任务暴露行为错误，3个任务因作者源码编译失败未评分。
记录绑定`6ec29fa0`的runtime、冻结候选、判据和返回报告身份，检验了实际
Spectre到既有harness的评分消费路径。它不代表五类规格已完成，也不替代
任务修正后的重新校准、模型试做或隔离验收。
