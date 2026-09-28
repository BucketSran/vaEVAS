# vaEVAS

面向 Verilog-A benchmark 与可信评测的研究工作区，在同一仓库维护任务、验收逻辑与
EVAS 仿真器，支持联动修复。应用评测采用 Harbor，独立仿真器验证与应用任务分开报告。

## 当前可用内容

[独立验证集](evas/validation/README.md) 包含 31 个条件，已完成 thu-sui 上四后端、
两档设置的 [248 条配置矩阵](experiments/dvs2-four-backend-validation/results/MATRIX.md)。
结果仅证明所列有限观测，完整观察资格仍待完成。
[验证集 v1](evas/validation/versions/v1/README.md) 以 `validation-v1` 标签冻结，后续修订保留原始证据。

[EVAS](evas/README.md) 迭代在独立开发分支推进。旧 vaBench 和 EVAS 是审查与迁移来源；
本仓库尚未迁入 VABench 任务数据集和完整旧仿真器，旧成绩不自动成为新版本的质量证明。

## 工作区

| 路径 | 职责 |
| --- | --- |
| [tasks/](tasks/README.md) | 有实际建模用途的 Harbor 任务、参考解与验收材料 |
| [evas/](evas/README.md) | 仿真器源码、构建与回归；`validation/` 保存独立跨后端契约 |
| [containers/](containers/README.md) | 共用容器环境、构建与依赖版本 |
| [experiments/](experiments/README.md) | 实验协议、分析与整理后的结果证据 |
| [scripts/](scripts/README.md) | 仓库维护和验证工具 |

开发约定见 [AGENTS.md](AGENTS.md)。原始运行输出与临时材料存放在 Git 忽略的 `runs/`。
正式结果绑定任务/源码版本、EVAS 构建、镜像及 Harbor/Agent 配置；修复影响判分时重跑受影响部分。
题型、最终评分、完整支持范围、打包发布与应用基线仍需按实际工作确定。

## 分支与文档维护

- [PR #1](https://github.com/BucketSran/vaEVAS/pull/1)：测试契约、用例、判定器与跨后端证据，目标为 `main`。
- [PR #2](https://github.com/BucketSran/vaEVAS/pull/2)：EVAS 源码、接口与自身回归，当前以 PR #1 分支为基底。
- 每个阶段用独立提交保留可 review 的检查点，继续更新对应 PR；达到可合并里程碑后再合入 `main`。
  PR #1 先合并后，将 PR #2 基底调整为 `main` 并核对差异。PR 合并即结束该批次，后续批次再开对应方向的新 PR。
- 仓库长期保留使用说明、当前接口/测试契约与可复核结果。阶段计划、设计讨论及 review 流水记录放在 PR 和 Git 历史，避免重复状态文档。

迁移应先核对来源、规格与实现；失败先区分任务、参考解、判定器、仿真器或环境责任。
不通过放宽判据掩盖失败，保留未决及失败证据。

## 参考

[analog-design-bench](https://github.com/Arcadia-1/analog-design-bench) 提供组织方式参考，
[Harbor](https://docs.harborframework.com/core-concepts/tasks/overview) 提供任务格式。
当前尚未迁入参考仓库的代码或任务内容。
