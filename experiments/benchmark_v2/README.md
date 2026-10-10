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
| tests/cases.json | 唯一 `name`、`netlist`、`stop`、`signals`，可选不可修改 `support` 文本或 `support_files` 路径/SHA引用 |
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

`support_files` 将模拟文件名映射到 `{"path": "dut/model.spice", "sha256": "…"}`。路径以私有 `tests/` 为根；runtime 在启动后端前核对普通文件类型、根目录约束与原字节SHA，再按原UTF-8内容写入隔离运行目录。引用不能覆盖候选，也不能与内联support重名。多个条件可共享同一文件，材料去重不改变实际仿真输入。

## 模型试做

`pilot.py` 负责封存公开材料、生成 stock Harbor/Pi 配置和一次性模型请求。
Agent 循环、公开工具、作业恢复及独立终评继续由 circuit harness 提供。
它不自动遍历题库，也不根据试跑结果修改候选或选取最佳答案。

| 命令 | 输入和结果 |
| --- | --- |
| `public-package` | 从题目公开目录选择固定 netlist，封存公开反馈包；不读取隐藏 cases 或参考解 |
| `prepare` | 绑定公开会话、独立终评配置、模型 catalog、镜像和网关地址，导出 Harbor job |
| `preflight` | 验证封存 job 的部署配置；此结果不证明容器能连接网关或模型服务 |
| `run` | 调用 stock Harbor，一次 Trial，保存异常和终评状态；显式提交或会话结束时封存最后完整候选 |
| `one-shot` | 将相同题面与公开文件发给指定模型一次，保存请求、原响应和精确候选字节 |

各命令的参数见 `python3 -B experiments/benchmark_v2/pilot.py <command> --help`。
运行前通过调用进程环境注入 `BENCHMARK_MODEL_KEY`，不写入配置或证据文件。
部署配置、原模型响应、轨迹和完整仿真产物留在忽略的 `runs/`，发布精简结果与身份。
Agentic 运行前必须由协调者预留 Spectre 槽；公开测试和终评共同计入全局 4 并发。
网关地址须从所选 Agent 容器实际可达，不能将某个宿主平台的默认 DNS 名称当作已验证事实。

公开指引列出所有 `candidate_files`。仅修改容器工作目录不会提交候选，须通过
`evas_write` 写入每个正式路径。`evas_testbench` 可以提供临时 netlist 和支持 VA；
这些文件仅用于诊断，不进入正式提交。未知动作只能用原 action ID 和原参数查询，
不得换 ID 重交。公开反馈包返回实际波形与诊断，不返回隐藏评分结论。

One-shot 的材料导出只包含题面及公开目录。非 UTF-8 文件以 base64 表示；这种封装
不证明模型可以等价使用二进制数据，数据题仍须单独评估材料等价性。
响应须为完整 `files` JSON 对象，可以带一个完整的外层 JSON 代码围栏。
解析不选择多个答案、不改写 VA、不补交缺失文件。原响应和提取版本均保留身份。
预算耗尽、格式错误、后端缺陷和实际电路不合格分别记录，不能混成一个电路失败率。

`test_pilot.py` 验证公开导出、严格路径、原响应与候选字节保留，以及公开反馈包边界。
这些本地测试不等于真实模型 Trial；各类任务的实际试做记录随其验收证据发布。

[公开环境探针记录](public-probe-calibration.json)保留18个实际Spectre作者探针的完整分母、公开文件身份、候选来源、原始与有效网表摘要和归档摘要。17个通用探针及POR的SPICE混合网表均返回0，报告最大约14.6MB；024的一次未知状态按原作业ID恢复，没有重新提交。这些结果证明相应公开诊断可运行，不替代隐藏终评校准或模型试做。完整原始归档按摘要保留在本地执行记录。
