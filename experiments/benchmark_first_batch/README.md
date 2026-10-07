# 首批任务的校准入口

任务范围与准入条件见 [首批合同](../../benchmark/first_batch/README.md)。
本目录提供任务打包、校准队列和各类任务的独立判据回归。
远端提交、进程限制、清理和归档由已有 circuit harness 执行。

## 执行

需要操作者指定的 circuit harness checkout、Python 3.12 和已完成真实许可证预检的
Spectre 部署。配置和批量输出放在 ignored `runs/`。任务自身的 Docker 镜像不含 Spectre。
这些任务目前按 Spectre 扩展集候选建设，不代表公开 EVAS 能执行所有参考解。

```sh
python3 -B experiments/benchmark_first_batch/runtime.py prepare \
  --task benchmark/tasks/spec-latched-comparator \
  --candidate benchmark/tasks/spec-latched-comparator/solution/dut.va \
  --output runs/first-batch/comparator-reference \
  --harness-checkout /absolute/path/to/circuit-harness
python3 -B experiments/benchmark_first_batch/runtime.py execute \
  runs/first-batch/comparator-reference --config /absolute/path/to/operator-config.json
```

`prepare` 只冻结输入，不执行模拟器。每个条件是一个独立 harness job；候选源码、
完整判据和单条件包都有身份。`--case NAME` 可选择语义负例的代表条件。
`execute` 保存 job ID 后提交，恢复时只查询原 ID。状态未知或归档失败时停止，
不能换 ID 盲重试。新校准必须使用新输出目录，旧证据不覆盖。

批量计划是上述已准备目录的 JSON 数组，最多四个并发执行者。
不要同时另开 Spectre 队列或 Agent 终评。操作者负责全局并发上限。

```sh
python3 -B experiments/benchmark_first_batch/batch.py runs/first-batch/plan.json \
  --config /absolute/path/to/operator-config.json --workers 4
```

队列复用 `runtime.py`，不另行实现远端协议。它核验归档内 report 的哈希与候选/判据
身份，再产生每个提交的 `summary.json`。参考必须所有条件 `graded` 且通过。
语义负例必须所有选定条件完成实际波形评分，并至少一个 `graded` 失败。
源码合同拒绝、编译失败或超时虽可得到任务零分，均不能充当语义负例校准。
真实基础设施故障保持未评分状态，保留在固定尝试清单中。

`prepare_calibration.py` 根据首批登记表冻结参考和语义错版，并保存明确角色的
`matrix.json` 与队列 `plan.json`。辨识类先运行 `identification/prepare_candidates.py`，
从公开表征数据构建候选。验证工具类使用 `calibration_plan.json` 指定的代表负例条件；
其他任务默认保留完整条件。冻结、执行、评分成功分别记录，不由目录数量推导。

## 可移植评分副本

`benchmark/checkers/circuit_task.py` 维护公共执行边界，复用既有 `adc_linearity.py`
的源码词法分析与 PSF 读取。各任务的 `first_batch_*.py` 定义独立正确性条件。
Harbor 任务的 `tests/` 保存这些模块的逐字副本。更新共享源后运行：

```sh
python3 -B experiments/benchmark_first_batch/sync_runtime.py
python3 -B experiments/benchmark_first_batch/sync_runtime.py --check
python3 -B -m unittest discover -s experiments/benchmark_first_batch -p test_circuit_task.py -v
```

打包时从维护源重新取相同模块，并生成使用 `python3.12 -B` 的远端入口。
禁止字节码输出可避免现有 harness 的完整 benchmark 清单和归档排除 `__pycache__`
规则冲突。评分代码不把候选可打印的 stdout 文本当成许可证故障证据。
许可证可用性由候选之外的部署预检核验，候选编译或仿真失败仍保留零分。
同步工具也从每题 `contract.json` 生成公开题面中的源码和文件限制，避免只在隐藏
checker 中拒绝宏、文件访问或未列出的 include。标记块外的题面由任务作者维护。

## 性能配对

性能候选先完成实际功能校准。`prepare_pairs.py` 每个选定条件冻结一对预热及五对
baseline/reference，顺序固定为 A B A B。使用 `batch.py --workers 1` 串行执行；
计时窗口暂停其他受本轮控制的 Spectre 队列，并另行记录宿主硬件和负载观测。

```sh
python3 -B experiments/benchmark_first_batch/prepare_pairs.py \
  --output runs/first-batch/performance-pairs \
  --harness-checkout /absolute/path/to/circuit-harness \
  --task-case optimize-vco-step low-band-end-to-end
python3 -B experiments/benchmark_first_batch/batch.py \
  runs/first-batch/performance-pairs/plan.json \
  --config /absolute/path/to/operator-config.json --workers 1
python3 -B experiments/benchmark_first_batch/performance.py \
  --manifest runs/first-batch/performance-pairs/manifest.json \
  --output runs/first-batch/performance-analysis.json
```

离线分析核对归档内源码、实际波形、评分报告及原生日志的身份；任何功能失败或
缺失尝试都会阻止配对汇总。它单列原生 transient CPU/elapsed、accepted steps 与
求解进程 elapsed，输出逐次数据、范围、中位数和逐对比率。缺失的 rejected steps
保持未知。当前执行边界合并捕获 stdout/stderr，分析按真实合并流检查致命诊断，
不会虚构独立 stderr。每次使用新 sandbox，编译或缓存状态以原生日志为准；
求解 CPU 与整体进程开销分别呈现。大容量性能终评使用单独的操作者 profile，
客户端 `job_wait_timeout_s` 只控制等候归档的期限，不代替 harness 的执行/容量限制。
该工具不自动选择达标阈值，也不将可提取统计视为已证明性能改进。

这里的 process fixture 只测试文件与评分协议，不执行 Verilog-A，不构成后端证据。
各子目录说明实际电路条件、参考构建和代表错版。原始波形、模型轨迹和机器私有配置
留在 `runs/`；维护目录只保留可重放工具和与明确归档身份绑定的精简诊断。
