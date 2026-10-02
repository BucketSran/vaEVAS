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
| 当前版本实际验证了什么？ | [当前执行证据](parallel-gap-integration/README.md#当前证据) |
| 正确答案与精度要求从哪里来？ | [独立验证集](../evas/validation/README.md)、[技术手册](../evas/docs/README.md) |
| Spectre 的事件与历史行为有何差异？ | [Spectre 对照](dvs2-spectre-validation/README.md)、[共同生命周期历史报告](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/parallel-gap-integration/README.md#shared-lifecycle-review) |
| 旧四后端的结果与失败是什么？ | [历史矩阵](dvs2-four-backend-validation/results/MATRIX.md)、[故障归因](dvs2-four-backend-validation/DIAGNOSIS.md) |
| 怎样重新运行或取得原材料？ | [当前复现入口](parallel-gap-integration/README.md#复现入口)及各目录的协议/资产说明 |

<a id="checkpoint-evidence"></a>

## 现有目录如何处理

这些名称沿用历史批次。以下区分仍在使用的工具、需要保留的比较证据和待归档材料：

| 现有目录 | main 需要保留的职责与文件 | 整理方向 |
| --- | --- | --- |
| [dvs2-starter-pilot](dvs2-starter-pilot/README.md) | `suite.py` 输入生成、`analyze.py` 波形读取；冻结 v1 的来源与工具身份材料 | 把共享输入/读取工具迁入 validation；试点长报告与一次性诊断从历史提交查阅 |
| [dvs2-history-validation](dvs2-history-validation/README.md) | `history.py` 精确有理数事件判据、`recheck.py` 中仍被复用的契约、检查器校准 | 共享判据迁入 validation；旧波形重判保持原执行身份并归档 |
| [dvs2-spectre-validation](dvs2-spectre-validation/README.md) | `run_suite.py`、`check_results.py` 和校准；后端运行/报告工具、协议、31 条件 Spectre 基线及身份收据 | 输入与判据迁入 validation；执行工具继续归 experiments；各旧版本专项报告已改为固定历史链接 |
| [dvs2-four-backend-validation](dvs2-four-backend-validation/README.md) | 四后端适配工具、共同设置协议、完整分母的矩阵与失败归因 | 精简比较证据留在 main；已结束的一次性诊断可归档，不能以新版结果覆盖旧基线 |
| [pr14-pr15-validation](pr14-pr15-validation/README.md) | `matrix.py` 仍负责当前 EVAS 矩阵执行；`operators.py` 等独立算子探针与校准 | 将算子判据迁入 validation，矩阵执行工具按职责整理；完成迁移后取消 PR 编号目录 |
| [parallel-gap-integration](parallel-gap-integration/README.md) | 当前检查点收据、矩阵分析、生命周期验证工具及独立校准 | 当前证据持续维护；阶段叙述已改为历史链接，旧收据按所支撑结论逐项判断保留/归档 |

**为什么目前保留这些路径？** [静态回归](../evas/tests/run_static_regression.py)直接导入
Spectre 目录的输入与检查器；后者又依赖 starter 和 history。
[当前矩阵执行器](pr14-pr15-validation/matrix.py)还读取旧工具身份并复用四后端适配工具。
直接删除这些目录会破坏验证入口；迁移必须同时处理导入、命令、输入生成与身份记录，
对迁移后的工具做校准并产生新的分析身份。历史收据与冻结快照保持原字节。
本轮保留这些依赖，尚未执行工具迁移。

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
