# 历史题集与建设记录

这里保留初筛、旧七类和后续批次的来源、校准及实验记录。当前审核以[56 题总览](../TASKS.md)和[电路功能族](../circuits/README.md)为入口；不同批次的任务与成绩按各自原始范围解释。

当前有 6 个来自真实资产的内部初筛任务，覆盖逻辑对照、SAR 握手、ZOOM 时序、
增益校准、动态 VCO 和带负载运放。题目清单、校准和 GLM/Codex 运行协议见
[能力初筛说明](../../../experiments/va_screen/README.md)。它们尚不是正式 benchmark 发布版。
[reference/](../../reference/README.md) 保存历史 vaBench 发布包（v1 完整、v4 最新快照+文档），
以及按来源和功能整理的[原始 Verilog-A 资料](../../reference/veriloga/README.md)。
原始资料分为课题组工程模型与 Cadence 安装库模型，仅供内部研究，不对外分发。
另有一个仓库自有的修复题：[积分三角波振荡器](../../tasks/va07-triangle-repair/instruction.md)。
它检查双向事件导致的边界反复换向，单独校准，不加入原六题的初筛成绩。
原创 [ADC DNL/INL 测量首题](../../tasks/va08-adc-linearity/SOURCE.md) 已完成实际 Spectre 校准和
完整 Harbor oracle Trial，尚未完成 Agentic 主评测试跑，也不加入原六题分母。
任务位于 `tasks/`；每题 `SOURCE.md` 说明原始资产和必要改编，原始源码保持不变。

[首批工程任务](first-batch/README.md)保存按旧七类方案建设的资产，每类 5 题。
其中复用振荡器修复和 ADC DNL/INL 两题，保留原六题初筛作为独立历史基线。
[执行与检查入口](../../../experiments/benchmark_first_batch/README.md)区分实际校准、归档重判、
模型试跑和发布资格；[来源元数据](first-batch/METADATA.md)记录同源关联与上下文层次。
当前采用[五类方案](../docs/task-types.md)，旧分类与历史结果不改写。
[v2五类工程任务](../../../experiments/benchmark_v2/README.md)已建立37题。179个登记变体的作者校准及两项私有激励修订的补充校准已齐全；148个模型试做单元和五份spec的义务核对已完成，见[交付验收](../../../experiments/benchmark_v2/spec-delivery.md)。旧版本身份与完整分母见[作者校准固定报告](../../../experiments/benchmark_v2/author-calibration-final.md)，当前证据见[增量报告](../../../experiments/benchmark_v2/author-calibration-private-overlays.md)。
[下一批题目与作者校准](../../../experiments/benchmark_next/README.md)按五条已批准路线分别交付，沿用五类工程动作。各路线的任务、参考解、独立 checker 和实际校准状态分开记录；本轮没有模型解题实验。

## 首批题集配置的位置

旧七类的五份 JSON 清单已移到 `benchmark/tasks/first_batch-*.json`，内容保持原样。

| 旧路径 | 当前路径 |
| --- | --- |
| `benchmark/first_batch/model_repair.json` | [first_batch-model_repair.json](../../tasks/first_batch-model_repair.json) |
| `benchmark/first_batch/identification.json` | [first_batch-identification.json](../../tasks/first_batch-identification.json) |
| `benchmark/first_batch/integration.json` | [first_batch-integration.json](../../tasks/first_batch-integration.json) |
| `benchmark/first_batch/verification_measurement.json` | [first_batch-verification_measurement.json](../../tasks/first_batch-verification_measurement.json) |
| `benchmark/first_batch/optimization.json` | [first_batch-optimization.json](../../tasks/first_batch-optimization.json) |

首批说明与元数据约定见 [first-batch](first-batch/README.md)。已封存收据、源码快照和决策日志保留原始路径及字节；需要追溯其中的旧路径时，使用本表和该记录绑定的 Git 提交。路径迁移不重新授予校准或发布资格。
