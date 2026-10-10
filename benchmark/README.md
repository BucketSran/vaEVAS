# Verilog-A Benchmark

本模块评估模型与智能体能否用 Verilog-A 完成工程任务，按任务要求验收交付物。
任务格式已确定：使用 **Harbor 原生格式**。
所有任务均须配备依据公开合同和独立判据建立、经过校准的 checker。
纯代码理解和技术问答不作为 benchmark 任务，也不另设此类辅助题集。

当前有 6 个来自真实资产的内部初筛任务，覆盖逻辑对照、SAR 握手、ZOOM 时序、
增益校准、动态 VCO 和带负载运放。题目清单、校准和 GLM/Codex 运行协议见
[能力初筛说明](../experiments/va_screen/README.md)。它们尚不是正式 benchmark 发布版。
[reference/](reference/README.md) 保存历史 vaBench 发布包（v1 完整、v4 最新快照+文档），
以及按来源和功能整理的[原始 Verilog-A 资料](reference/veriloga/README.md)。
原始资料分为课题组工程模型与 Cadence 安装库模型，仅供内部研究，不对外分发。
另有一个仓库自有的修复题：[积分三角波振荡器](tasks/va07-triangle-repair/instruction.md)。
它检查双向事件导致的边界反复换向，单独校准，不加入原六题的初筛成绩。
原创 [ADC DNL/INL 测量首题](tasks/va08-adc-linearity/SOURCE.md) 已完成实际 Spectre 校准和
完整 Harbor oracle Trial，尚未完成 Agentic 主评测试跑，也不加入原六题分母。
任务位于 `tasks/`；每题 `SOURCE.md` 说明原始资产和必要改编，原始源码保持不变。

[首批工程任务](first_batch/README.md)保存按旧七类方案建设的资产，每类 5 题。
其中复用振荡器修复和 ADC DNL/INL 两题，保留原六题初筛作为独立历史基线。
[执行与检查入口](../experiments/benchmark_first_batch/README.md)区分实际校准、归档重判、
模型试跑和发布资格；[来源元数据](first_batch/METADATA.md)记录同源关联与上下文层次。
当前采用[五类方案](docs/task-types.md)，旧分类与历史结果不改写。选题材料与学习入口见
[五类任务材料研究](research/README.md)。

新的逐题设计记录集中在 [Benchmark 工作区](workbench/README.md)，按工程动作、电路家族和
稳定 Case ID 组织。旧题优先复用的本轮结果见[迁移筛选](workbench/migration/README.md)。[Review 队列](workbench/REVIEW.md)汇总待讨论事项，来源与电路记录单独维护。
首批从 POR 测试台、LDO 启动测量和运放压摆率开始，后续候选扩展到五类工程动作；
具体数量与阶段以工作区索引为准。设计卡不等于正式评分题，既有任务与历史成绩没有迁移或重新计数。

## 目标与边界

核心设计判断集中在 [benchmark/docs/](docs/README.md)。
[设计目标与选题判断](docs/design.md)说明工程价值、电压域范围、上下文层次、来源与难度判断；
[五类任务定义](docs/task-types.md)说明各类的输入、交付物、修改权限与独立验收。
当前采用五类工程动作，旧分类与结果保持原身份，候选方向不等于已建成评分任务。

## 评测方式与题目建设

[评测与复现原则](docs/evaluation.md)维护 Agentic 与 One-shot、公开自测与独立终评、
固定后端、checker 校准、环境缺陷与重跑规则。题目按工程场景、公开合同、
参考解与错误版本校准、模型试跑的顺序建设，合格后冻结版本。
[Issue #72](https://github.com/BucketSran/vaEVAS/issues/72)跟进总体推进，
[Issue #107](https://github.com/BucketSran/vaEVAS/issues/107)跟进五类定义与代表题设计。

## 开源复现与结果报告

[开源复现规则](docs/evaluation.md#开源复现保留同一道题的要求)说明公开主集与 Spectre 扩展集的资格，
以及替代后端、配套 VA 环境与简化变体的边界。
[成绩分析原则](docs/evaluation.md#分析成绩时保留工程差异)说明同源关联、任务计数与分组，
各次实验的具体配置、成绩和证据继续由对应实验入口维护。

## 从开发问题积累候选

[CANDIDATES.md](CANDIDATES.md) 记录开发中发现的问题及可能形成的建模任务。
先保留最小触发条件、独立预期、实际失败和证据；后续再集中做题目改造、评分和环境适配。
记录候选不自动创建 Harbor 目录，不增加正式题目或评分分母。
振荡器修复题已完成首批改造与校准，具体证据见[非性能题校准](../experiments/benchmark_first_batch/CALIBRATION.md)。
开发、验证和 review 入口都执行这项记录规则，具体步骤见
[协作流程](../docs/contributing/validation.md#development-bench-candidates)。

[历史任务设计稿](examples/README.md) 保存六份具体事例：真实电路闭环校准、从数据建立模型、
故障修复、功能扩展、测量工具及仿真优化。每份说明题面、输入材料、交付物、
独立 checker 和落地缺口。ADC 测量首题的实际校准与试跑状态见
[任务记录](tasks/va08-adc-linearity/SOURCE.md)；这些方向不加入原六题初筛分母。
其中仿真优化示例仅作历史保留，不属于当前五类选题方向。

## 任务结构

任务放在 `benchmark/tasks/<task-id>/`。每个任务使用以下结构：

```text
benchmark/tasks/<task-id>/
├── instruction.md
├── task.toml
├── environment/
│   └── Dockerfile
├── solution/
│   └── solve.sh
└── tests/
    └── test.sh
```

| 文件 | 用途 |
| --- | --- |
| `instruction.md` | 说明建模要求、可用输入和完成条件 |
| `task.toml` | 配置任务信息、运行资源和时间限制 |
| `environment/Dockerfile` | 建立任务使用的工具与输入环境 |
| `solution/solve.sh` | 执行参考解，用于验证任务和评分程序 |
| `tests/test.sh` | 检查提交的模型，并输出评分结果 |

本项目的任务随任务保存参考解。Harbor 的结构和环境选项见
[官方任务说明](https://docs.harborframework.com/core-concepts/tasks/overview)。
评分程序按 Harbor 约定写入 `/logs/verifier/reward.txt`，或使用其支持的 `reward.json` 格式。

## 共享评分程序

[checkers/spectre_waveform.py](checkers/spectre_waveform.py) 是六题共用的评分源码。
[任务生成器](../experiments/va_screen/build_tasks.py)将它复制到每题的 `tests/verify.py`；
任务运行时执行该副本，`tests/cases.json` 保存各题的网表、独立期望值与容差。

修改共享源后，需要同步受影响的执行副本，并重做其参考解和错误版本校准。
生成器会重建全部六题文件，运行前应保留正在修改的任务。提交前使用
[身份检查](../experiments/va_screen/README.md#身份与再校准)确认源、副本及校准记录一致。
校准通过证明这些已测条件，不能证明评分程序覆盖任意错误实现。

[checkers/triangle_oscillator.py](checkers/triangle_oscillator.py) 单独负责振荡器修复题。
它使用正速度的分段解析积分和三角波折返关系；固定题目配置与错误版本校准见
[来源和验证边界](tasks/va07-triangle-repair/SOURCE.md)。无需 Spectre 的检查器回归：

```sh
python3 -B -m unittest discover -s experiments/backends/dvs2-spectre-validation -p test_triangle_oscillator.py -v
```

当前 EVAS 的本地接入验收入口是 [triangle_evas.py](checkers/triangle_evas.py)，
通过操作者指定的 circuit harness 执行，仅覆盖 `constant-tighter` 开发配置。
[调用方式、配置映射与未完成的负例验收](tasks/va07-triangle-repair/SOURCE.md#local-evas)
由该任务维护。原解析判据与 case 文件字节保持不变。当前 Spectre 入口经由共享的
`circuit_task` 执行，旧校准与当前入口的复核证据分别记录。

## 环境与结果

每个任务在自己的 `environment/` 中声明运行环境。
当前使用固定 digest 的 Python 基础镜像与远端 Spectre verifier；
任务镜像本身不包含商业仿真器，运行时必须按初筛说明指定 verifier。
镜像应记录依赖版本和构建方法；执行记录应保存实际使用的镜像身份。
完整运行日志与临时输出放在 Git 忽略的 `runs/` 中。

Benchmark 评分与 [EVAS 正确性验证](../evas/validation/README.md)分别维护和报告。
EVAS 的构建与运行方法见 [仿真器说明](../evas/README.md)。
