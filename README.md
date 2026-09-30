# vaEVAS

面向 Verilog-A benchmark 与可信评测的研究工作区，在同一仓库维护任务、验收逻辑与
EVAS 仿真器，支持联动修复。应用评测采用 Harbor，独立仿真器验证与应用任务分开报告。

## 当前可用内容

[独立验证集](evas/validation/README.md) 包含 31 个条件，已完成 thu-sui 上四后端、
两档设置的 [248 条配置矩阵](experiments/dvs2-four-backend-validation/results/MATRIX.md)。
结果仅证明所列有限观测，完整观察资格仍待完成。
[验证集 v1](evas/validation/versions/v1/README.md) 以 `validation-v1` 标签冻结，后续修订保留原始证据。

[EVAS](evas/README.md) 提供限定语法前端、版本化 IR、Rust 静态线性/非线性方程求解，
以及连续 PWL/仿射网络上的 `cross` 与固定 `timer` 事件、实例状态、受限 `transition` / `absdelay` / `slew` 波形、显式初值的直接 PWL `idt` 积分与同刻原子提交。
支持受限事件体 `if/else`、cross 的 OR 与输入误差认证；版本、范围和证据统一见[能力表](evas/docs/CAPABILITIES.md)。
新内核的历史 [31 条件矩阵与 absdelay/slew 专项](experiments/pr14-pr15-validation/RESULTS.md)分别记录功能覆盖和算子证据。
旧 vaBench 和 EVAS 是审查与迁移来源；
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
EVAS 的数学与实现说明从[技术手册](evas/docs/README.md)进入；
[能力与缺口总表](evas/docs/CAPABILITIES.md)统一关联 main 支持、开发 PR、实验身份和已知差异。
正式结果绑定任务/源码版本、EVAS 构建及实际使用的镜像、Harbor/Agent 配置；修复影响判分时重跑受影响部分。
题型、最终评分、完整支持范围、打包发布与应用基线仍需按实际工作确定。

## 分支与文档维护

`main` 为已审查共同基线，一批可 review 的代码、测试、数学和证据使用一个短期任务分支。
仅实际依赖使用分层 PR；工作区与分支分别管理。完整生命周期和责任规则统一维护在
[CONTRIBUTING.md](CONTRIBUTING.md#branch-lifecycle)，agent 的快速执行入口为 [AGENTS.md](AGENTS.md)。

能力总表保存当前状态，Issue 保存具体剩余工作，PR/提交保存迭代历史；
数学、接口和实验手册是长期项目资产。资产身份、公开可用性与执行收据见
[实验管理](experiments/README.md#experiment-receipts)。发布/合并/清理遵循用户授权，当前开放 PR 不自动成为 main 支持。

初始验证基线、静态仿射内核和仓库技能已分别通过
[PR #1](https://github.com/BucketSran/vaEVAS/pull/1)、
[PR #2](https://github.com/BucketSran/vaEVAS/pull/2) 和
[PR #4](https://github.com/BucketSran/vaEVAS/pull/4) 合入 `main`。
技能入口见 [AGENTS.md](AGENTS.md)；从包含这些提交的基线创建分支即可继承技能文件。

迁移应先核对来源、规格与实现；失败先区分任务、参考解、判定器、仿真器或环境责任。
不通过放宽判据掩盖失败，保留未决及失败证据。

## 参考

[analog-design-bench](https://github.com/Arcadia-1/analog-design-bench) 提供组织方式参考，
[Harbor](https://docs.harborframework.com/core-concepts/tasks/overview) 提供任务格式。
当前尚未迁入参考仓库的代码或任务内容。
