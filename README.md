# vaEVAS

面向 Verilog-A benchmark 与可信评测的研究工作区，在同一仓库维护任务、验收逻辑与
EVAS 仿真器，支持联动修复。应用评测采用 Harbor，独立仿真器验证与应用任务分开报告。

## 当前可用内容

[独立验证集](evas/validation/README.md) 包含原 31 个条件。EVAS 的
[最新 IR16 检查点](evas/validation/README.md#latest-evas-checkpoint)两档本地瞬态回放各 31/31 达标。
IR16 的[连续动态说明](evas/docs/CONTINUOUS.md#checkpoint-evidence)记录积分反馈、动态 cross、
ddt、高阶滤波与 manifest 重编译；混合动态与共同事件生命周期已由
[PR32](https://github.com/BucketSran/vaEVAS/pull/32) 集成，已知事件截止点已由
[PR33](https://github.com/BucketSran/vaEVAS/pull/33) 合并。新检查不增加原矩阵的条件数。
thu-sui 的[历史四后端 248 配置矩阵](experiments/dvs2-four-backend-validation/results/MATRIX.md)
另行保存，其中 EVAS 为旧版 0.8.7。结果仅证明所列有限观测，完整观察资格仍为 I。
[验证集 v1](evas/validation/versions/v1/README.md) 以 `validation-v1` 标签冻结，后续修订保留原始证据。

[EVAS](evas/README.md) 提供限定语法前端、版本化 IR、Rust 静态线性/非线性方程求解，
以及受限连续动态联合求解、`cross` / 固定 `timer` 事件、实例状态与波形算子。
各项语言、精度及组合边界统一见[能力表](evas/docs/CAPABILITIES.md)。
新内核的各阶段矩阵、专项和执行身份从[实验索引](experiments/README.md#checkpoint-evidence)进入。
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

迁移应先核对来源、规格与实现；失败先区分任务、参考解、判定器、仿真器或环境责任。
不通过放宽判据掩盖失败，保留未决及失败证据。

## 参考

[analog-design-bench](https://github.com/Arcadia-1/analog-design-bench) 提供组织方式参考，
[Harbor](https://docs.harborframework.com/core-concepts/tasks/overview) 提供任务格式。
当前尚未迁入参考仓库的代码或任务内容。
