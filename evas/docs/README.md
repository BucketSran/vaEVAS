# EVAS 技术手册

本手册是 EVAS 的**原理与边界层**：解释如何求解电压关系、推进事件、
保存历史和控制误差。使用与构建先读 [EVAS README](../README.md)。

## 目录结构

| 文件/目录 | 内容 |
| --- | --- |
| 本页 | 阅读入口与分层说明 |
| [UPDATE.md](UPDATE.md) | 按版本/检查点的更新摘要 |
| [PROCESS.md](PROCESS.md) | TDD 开发流程与硬性检查规则 |
| [CAPABILITIES.md](CAPABILITIES.md) | 能力与缺口总表（一句话矩阵 + 检查点身份） |
| [TRACEABILITY.md](TRACEABILITY.md) | 追溯矩阵（**自动生成**，勿手编） |
| [math/](math/README.md) | 数学原理章节：求解、事件、算子、连续动态 |

## 按问题阅读

| 想了解的问题 | 文档 |
| --- | --- |
| 现在支持什么，还缺什么？ | [能力表](CAPABILITIES.md) |
| 哪些测试文件声明检查某能力，历史证据在哪里？ | [追溯矩阵](TRACEABILITY.md) |
| 新能力怎么开发、测试怎么写？ | [开发流程](PROCESS.md) |
| 电压关系如何联立求解？ | [求解](math/solving.md) |
| `cross`、`timer` 如何定位？同刻赋值如何处理？ | [事件](math/events.md) |
| `transition`、延迟、限速、积分和相位的数学含义？ | [算子](math/operators.md) |
| 积分反馈、滤波、`ddt`、DAE 怎样组合？ | [连续动态](math/continuous.md) |
| 正确答案从哪里来？ | [验证集](../validation/README.md) |
| 实际跑了什么，哪些材料可以复核？ | [实验索引](../../experiments/README.md) |

## 分层约定

- 数学推导与数值方法只在 `math/` 章节维护；同一算子经过不同求解路径时，
  各章节只解释自己的路径。
- 能力表维护证据入口，[追溯矩阵](TRACEABILITY.md)汇集文件级测试关联与这些入口。
  标签不能证明测试通过或完整覆盖；执行身份以收据为准。
- 过程叙事（PR 修复过程、逐轮审查）保留在 PR/实验收据/固定历史提交，
  不在手册正文重复维护；版本摘要只进 [UPDATE.md](UPDATE.md)。

<a id="feature-documentation-contract"></a>

## 特性文档契约

新增动态能力时，`math/` 对应章节须覆盖七项：行为、源码/假设区分、数学、
数值方法、代码地图、独立证据入口和局限。证据入口指向矩阵与收据，
不在正文复制链接列表。

## 参与讨论与改进

Issue 可以围绕能力 ID 提出，附上版本、最小模型与刺激、数学/规范依据、
期望行为与当前差异。改动请遵循 [PROCESS.md](PROCESS.md) 的五步流程。
