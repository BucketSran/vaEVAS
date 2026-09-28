# vaEVAS

A workspace for rebuilding a Verilog-A benchmark and its EVAS simulator.

vaEVAS 面向 DAC 投稿，以 Verilog-A benchmark 与可信评测体系为研究主线，
在同一仓库维护任务、验收逻辑和 EVAS 完整源码，支持它们的联动修复。
评测执行采用 Harbor。

## 当前阶段

目前已建立工作区与开发约定，并开始维护
[电压域行为的独立仿真器验证集设计](evas/validation/README.md)。
已完成八张起步卡的 [四后端功能试点](experiments/dvs2-starter-pilot/RESULTS.md)，
包含共同 VA 源码、运行/分析脚本和整理后的结果；正式验证资格仍待完善。
本轮已保存为 [验证集 v1](evas/validation/versions/v1/README.md)（`validation-v1` 标签），
后续优化在同一开发分支继续，不覆盖冻结证据。
仓库尚未迁入 VABench 任务数据集和完整旧 EVAS 仿真器源码。
EVAS 重构已建立[第一个可审查切片](evas/DESIGN.md)：限定语法前端、贡献 IR 与 Rust 静态线性求解。
题型、规模、评分方案和 EVAS 支持范围仍需后续设计与验证。

旧 vaBench 和 EVAS 是后续审查与迁移的来源。已有代码、任务和结果需要结合新方案
重新检查与验证，不直接作为新版本的质量证明。

## 工作区

| 路径 | 职责 |
| --- | --- |
| [tasks/](tasks/README.md) | Harbor 格式的 benchmark 任务、参考解与验收材料。 |
| [evas/](evas/README.md) | EVAS 完整源码、构建配置及仿真器自身的测试。 |
| [containers/](containers/README.md) | 共用容器环境、镜像构建与依赖版本。 |
| [experiments/](experiments/README.md) | 实验配置、分析脚本及整理后的结果。 |
| [scripts/](scripts/README.md) | 仓库维护、任务检查和发布辅助工具。 |
| [docs/](docs/workspace.md) | 设计讨论、已确定的方案与使用说明。 |

完整边界见 [工作区约定](docs/workspace.md)，开发时遵循 [AGENTS.md](AGENTS.md)。
各目录按实际需要增加内部文件；文档标明设计、实现与验证状态。

## 开发方式

围绕具体问题形成可复现用例，明确问题属于任务规格、参考解、评分器还是 EVAS，
然后联动修改并验证受影响的部分。迁移按经过审查的小批次推进。

每批正式实验记录任务版本、EVAS 版本、容器镜像及 Harbor/Agent 配置，
以便在修复影响判分的问题后定位和重跑受影响的结果。
原始运行输出存放在 Git 忽略的 `runs/` 下。

## 设计参考

- [analog-design-bench](https://github.com/Arcadia-1/analog-design-bench)
- [Harbor 任务格式](https://docs.harborframework.com/core-concepts/tasks/overview)

参考仓库用于借鉴组织方式；当前尚未迁入其代码或任务内容。
