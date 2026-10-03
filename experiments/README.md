# 实验与结果

这里提供 vaEVAS 的执行工具、精简结果、收据与历史材料入口。
目前已有记录主要验证 EVAS 仿真器；Benchmark 任务迁入后的评测另行登记，
仿真器语义测试的通过数不作为建模任务成绩。

## main 保留什么

持续使用的执行/分析工具，以及支撑当前验证和已公开比较的最小证据留在 main。
独立模型、数学判据和检查器归 [evas/validation/](../evas/validation/README.md)；
原理与支持范围归 [evas/docs/](../evas/docs/README.md)。
已有工具尚有历史路径依赖，暂按下表保留，迁移时一起更新调用者。
已结束的审查和逐轮开发叙述通过固定 Git 提交归档，大波形与日志保存在 ignored `runs/` 或外部归档。
详细标准见[贡献指南](../CONTRIBUTING.md#main-branch-contents)。

## 从哪里开始

| 想了解什么 | 阅读入口 |
| --- | --- |
| 当前支持什么、还有哪些限制？ | [能力表](../evas/docs/CAPABILITIES.md) |
| 当前版本实际验证了什么？ | [当前执行证据](runs/parallel-gap-integration/README.md#当前证据) |
| 正确答案与精度要求从哪里来？ | [独立验证集](../evas/validation/README.md)、[技术手册](../evas/docs/README.md) |
| Spectre 的事件与历史行为有何差异？ | [Spectre 对照](backends/dvs2-spectre-validation/README.md)、[共同生命周期历史报告](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/parallel-gap-integration/README.md#shared-lifecycle-review) |
| 旧四后端的结果与失败是什么？ | [历史矩阵](backends/dvs2-four-backend-validation/results/MATRIX.md)、[故障归因](backends/dvs2-four-backend-validation/DIAGNOSIS.md) |
| 怎样重新运行或取得原材料？ | [当前复现入口](runs/parallel-gap-integration/README.md#复现入口)及各目录的协议/资产说明 |

<a id="checkpoint-evidence"></a>

## 目录结构

目录名沿用历史批次名（保留原目录名以便历史链接与来源追溯），按职责分为三类：

| 目录 | 职责 | 内容 |
| --- | --- | --- |
| [runs/](runs/) | 当前证据 | [parallel-gap-integration](runs/parallel-gap-integration/README.md)：当前检查点收据、矩阵分析、生命周期验证工具及独立校准，持续维护 |
| [backends/](backends/) | 跨后端对照 | [dvs2-spectre-validation](backends/dvs2-spectre-validation/README.md)：31 条件 Spectre 基线、后端运行/报告工具与身份收据；[dvs2-four-backend-validation](backends/dvs2-four-backend-validation/README.md)：四后端适配工具、共同设置协议、完整分母矩阵与失败归因 |
| [archive/](archive/) | 已结束批次 | [dvs2-starter-pilot](archive/dvs2-starter-pilot/README.md)：试点输入生成与工具身份；[dvs2-history-validation](archive/dvs2-history-validation/README.md)：精确有理数事件判据与旧波形重判；[pr14-pr15-validation](archive/pr14-pr15-validation/README.md)：该批次矩阵与算子探针 |

历史收据与冻结输入保持原字节；仍在使用的工具可维护其导入路径。
其中 [pr14-pr15-validation/matrix.py](archive/pr14-pr15-validation/matrix.py)
**目前仍承担当前 EVAS 矩阵执行**，待其职责迁移到 runs/ 后才真正退役。

**工具依赖现状：** [静态回归](../evas/tests/run_static_regression.py)直接导入
backends 中 Spectre 目录的输入与检查器；后者又依赖 archive 的 starter 和 history。
当前矩阵执行器还读取旧工具身份并复用四后端适配工具。
归档目录因此不能删除；迁移必须同时处理导入、命令、输入生成与身份记录，
对迁移后的工具做校准并产生新的分析身份。历史收据与冻结快照保持原字节。

### 旧路径与当前位置

旧收据里的路径属于记录所绑定的提交。查历史时使用原提交和原路径；
查当前资产时使用下表。此表不改变原哈希或执行命令，也不证明新工具已重跑。

| 历史路径 | 当前目录 |
| --- | --- |
| `experiments/dvs2-starter-pilot/` | [archive/dvs2-starter-pilot/](archive/dvs2-starter-pilot/) |
| `experiments/dvs2-history-validation/` | [archive/dvs2-history-validation/](archive/dvs2-history-validation/) |
| `experiments/pr14-pr15-validation/` | [archive/pr14-pr15-validation/](archive/pr14-pr15-validation/) |
| `experiments/dvs2-spectre-validation/` | [backends/dvs2-spectre-validation/](backends/dvs2-spectre-validation/) |
| `experiments/dvs2-four-backend-validation/` | [backends/dvs2-four-backend-validation/](backends/dvs2-four-backend-validation/) |
| `experiments/parallel-gap-integration/` | [runs/parallel-gap-integration/](runs/parallel-gap-integration/) |

冻结 v1 的 README 也保留旧上下文；阅读其相对链接时使用
[迁移前的固定版本](https://github.com/BucketSran/vaEVAS/blob/1527502c9affb77fec12aac03adba5446f0f241e/evas/validation/versions/v1/README.md)。

## 已归档材料

[旧 EVAS 源码审查](https://github.com/BucketSran/vaEVAS/tree/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/legacy-evas-migration)
已从当前目录移除，完整报告、探针、证据与复核工具保留在已发布的固定提交 `f3440b2`。
它针对固定旧源码寻找边界和反例，不代表整个旧项目的缺陷率；新版设计约束与数学解释由技术手册维护。

Spectre 专项和联合开发阶段的完整报告也链接到该固定提交，避免在 main 复制长篇旧报告。
归档不会改写原始结果或删除提交历史。若重跑旧实验，应使用报告所绑定的源码、输入和工具；
其私有原始波形并未因 Git 归档变为公开可下载数据。

## 后续实验与证据

新工具按职责归属，不再按 PR 编号建目录：共享数学判据和输入生成器进入 validation，
后端执行与分析留在 experiments。新结果沿用对应研究问题的协议与收据格式，
每次执行或重判使用独立身份；不为每轮增加一套进度、设计和 review 文档。
是否进入 main，以持续用途或支撑的公开结论为依据。

<a id="experiment-receipts"></a>

收据字段与可用性要求统一见[贡献指南：执行收据](../CONTRIBUTING.md#execution-receipts)。
README 说明研究问题、结果入口、复现条件和材料可用性；收据绑定源码、输入、检查器与实际设置。
公开摘要、旧波形重判和新仿真分别报告；取得仅本地保留的原始材料之前，不能宣称已完整复现。
