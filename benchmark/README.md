# Verilog-A Benchmark

本 benchmark 评估模型与智能体能否用 Verilog-A 完成电路工程任务。
任务采用 Harbor 格式，交付物由经过作者校准的独立 checker 验收。
纯代码理解和技术问答不作为任务。

## 从哪里开始

| 入口 | 内容 |
| --- | --- |
| [workbench/](workbench/README.md) | 按电路功能审核、收集材料和设计题目，保存共同定义与候选 |
| [tasks/](tasks/) | 题目包及题集清单，包含输入、参考解和独立验收 |
| [checkers/](checkers/) | 多道题共用的评分代码，随题打包的副本由建设脚本维护 |
| [reference/](reference/README.md) | 保持原貌的历史 benchmark 与原始 Verilog-A 资料 |

原始资料的来源与使用范围见 `reference/` 的说明。实验协议、结果与证据由
[experiments/](../experiments/README.md)维护；仿真执行调度属于独立的 circuit harness。

## 当前审核

[56 题总览](workbench/TASKS.md)合并两批已建设任务：37 题与后续 19 题，
按五类工程动作和电路功能列出输入、交付、checker 思路、同源变体与覆盖缺口。
每道题仅计一次；历史初筛、旧七类题集和设计卡不额外加入这 56 题。

当前按 [#159](https://github.com/BucketSran/vaEVAS/issues/159) 逐类判断电路功能与场景的工程价值、
现有覆盖及扩展方向。审核使用实际电路资产，例如 [R01 采样与多通道读出](workbench/circuits/r01-sampling/README.md)。
具体题目取舍、checker 细化和 Harbor 封装在后续阶段落实。
原有 18 张设计卡与 62 个迁移来源候选留在工作区供追溯，不与题量相加。

<a id="目标与边界"></a>
<a id="评测方式与题目建设"></a>
<a id="开源复现与结果报告"></a>

## 设计与评测约定

- [设计目标与选题判断](workbench/docs/design.md)：工程价值、电压域范围、上下文层次和来源。
- [五类任务定义](workbench/docs/task-types.md)：输入、交付物、修改权限与独立验收。
- [评测与复现原则](workbench/docs/evaluation.md)：Agentic 与 One-shot、固定后端、作者校准、环境缺陷与成绩报告。

电路功能和五类工程动作通过总览与任务元数据关联。共享电路不因派生出多个任务而失去同源关系。
设计认可、作者校准、运行适配和正式发布分别记录；合入 main 不自动代表所有后端均可复现。

## 任务结构

题目相关材料集中在各自目录：

```text
benchmark/tasks/<task-id>/
├── instruction.md
├── task.toml
├── SOURCE.md
├── environment/
├── solution/
└── tests/
```

`instruction.md` 说明要求，`task.toml` 配置任务，`SOURCE.md` 记录来源与改编。
`environment/` 提供运行环境与公开输入，`solution/` 保存参考解，`tests/` 执行独立评分。
评分按 Harbor 约定输出 `/logs/verifier/reward.txt` 或 `reward.json`，详见
[Harbor 任务格式](https://docs.harborframework.com/core-concepts/tasks/overview)。
题集清单作为文件放在 `tasks/` 根下；现有旧七类清单及其历史身份见[路径对照](workbench/history/README.md#首批题集配置的位置)。

<a id="从开发问题积累候选"></a>
<a id="共享评分程序"></a>
<a id="环境与结果"></a>

## 维护与历史

开发中发现的可复用问题进入[候选登记](workbench/CANDIDATES.md)，先记录触发条件、独立预期与证据，
不自动创建题目或增加评分分母。题卡索引由 `python3 -B scripts/benchmark_workbench.py --check` 检查。
共享 checker 的副本同步、校准与环境说明见[评分实现](workbench/docs/evaluation.md#共享评分程序)。

[历史题集与建设记录](workbench/history/README.md)保留初筛、旧七类和后续两批的来源及实验入口；
[历史设计稿](workbench/examples/README.md)保留早期设想，包括已不属于当前五类的方向。
[总体议题 #72](https://github.com/BucketSran/vaEVAS/issues/72)和[分类议题 #107](https://github.com/BucketSran/vaEVAS/issues/107)用于追溯建设讨论。
