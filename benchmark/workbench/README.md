# Benchmark 逐题设计工作区

这里保存从材料筛选到正式出题的设计记录，方便逐题 review。按 **工程动作 → 电路家族 → Case** 浏览；同一来源可以服务多道题，每道题保留独立身份。当前沿用已确认的五类方案，“测量与表征”和“开发验证工具”合并为“电路测试与表征”。

先看 [设计 review 队列](REVIEW.md)，再打开具体题卡。每张题卡说明：材料本来有什么、拟让 Agent 做什么、如何独立验收、还有哪些问题未确定。当前三个候选仅到材料筛选和设计草案，尚无本轮仿真、配套 VA 模型校准或模型试做结果。

<!-- workbench:begin -->

登记 **3 张候选设计卡**，不代表已发布或已通过验收的题目。

| 工程动作 | 候选数 |
| --- | --- |
| [按规格构建模型](cases/spec-modeling/README.md) | 0 |
| [从数据建立模型](cases/data-modeling/README.md) | 0 |
| [扩展与集成](cases/extension-integration/README.md) | 0 |
| [诊断与修复](cases/diagnosis-repair/README.md) | 0 |
| [电路测试与表征](cases/testing-characterization/README.md) | 3 |

| Case | 题目 | 工程动作 / 电路家族 | 阶段 / 设计 review | 本轮关注 |
| --- | --- | --- | --- | --- |
| [case-0001](cases/testing-characterization/power/case-0001-por-sequence/README.md) | POR 上电、欠压与恢复测试台 | 电路测试与表征 / 电源与复位 | 题目草案 / 待 review（r1） | 延迟起点及复位合同；首版只含上电、欠压、恢复 |
| [case-0002](cases/testing-characterization/power/case-0002-ldo-startup/README.md) | 固定 LDO 的启动指标测量 | 电路测试与表征 / 电源与复位 | 题目草案 / 待 review（r1） | 有限窗口定义、取样/事件语义及未建立状态 |
| [case-0003](cases/testing-characterization/amplifiers/case-0003-opamp-slew/README.md) | 运放压摆率激励与测量 | 电路测试与表征 / 放大器 | 材料筛选 / 待 review（r1） | 先选公开 DUT，再决定单向或双向测量 |

<!-- workbench:end -->

## 如何 review

建议先看 POR 完整流程，再看 LDO 限定测量环节，最后决定是否选取运放电路开展压摆率题。每次只处理题卡的“本轮需要确认”部分；同意一张设计卡不等于实现或数值校准已通过。

- [材料来源](sources/README.md)：论文、仓库、安装库的固定版本、实读范围与许可。
- [电路资产](circuits/README.md)：具体 DUT、测试台、依赖、配套 VA 模型和复现缺口。
- [同源任务](SOURCE_GROUPS.md)：哪些题共享电路、数据或衍生要求，供后续成绩分析。
- [模板及新增流程](templates/README.md)：新增题卡、修改设计、记录 review 的操作。

总表和题卡摘要由 `case.json` 生成，避免在多个地方分别修改状态。题卡正文保留人写的设计理由、改编边界和讨论记录。

## 多 Case 的组织规则

`case-0001` 这类 ID 在整个工作区唯一，不含类别和后端。目录名附上用途，例如
`cases/testing-characterization/power/case-0001-por-sequence/`。即使题目换分类或改名，ID 仍不变。暂缓的题保留记录，旧 ID 不复用。

五类是工程动作；电路家族是第二个维度。以后可以在同一类别下加入 ADC、ADPLL、放大器等，也可以让同一个 POR 在修复类和测试类下各有一道题。分类及家族显示名称登记在 [catalog.json](catalog.json)，索引工具不写死类别数量。空类别暂不凑题。

一道题通常对应一个独立工程目标与交付合同。普通斜坡速度、负载、门限和初态变体属于该题的测试场景，不另增 Case。仅给测量结果加阈值比较，也不自动变成新题。增加独立工程要求后再决定是否新建，并用 `related_cases` 记录 `derived-from`、`simplified-from` 或 `related`。

`source_ids` 指资料，`circuit_ids` 指具体电路，`source_groups` 指分析相关性时使用的组。共用同一篇方法论文不等于共用电路；未确定电路的题保留空组，不把所有未知项合为同源。共享资料只记录一次，不为每个 Case 复制一份原始仓库。

## 从草案走到正式题

`stage` 记录建设阶段：材料筛选、题目草案、实现、校准、模型试做、冻结；暂缓项保留为 `deferred`。`review_status` 单独记录设计是否待 review、待修改、本版已认可或尚未提交 review。

更改接口、指标、可修改范围或判据时递增 `design_revision`，重新标为待 review。明确获得针对该版本的认可后，才设置 `accepted` 和对应的 `reviewed_revision`，并在题卡正文记录日期、review 人和决定。脚本拒绝用旧版本的认可覆盖新设计，但不会替代人工判断或推断已有批准。

正式任务仍放在 [benchmark/tasks](../tasks/)，沿用 Harbor 格式；题卡的 `task_path` 指向它。实现前，Case 内可以保留明确标注的 `instruction.md` 草案。正式题面建立后，此处改为链接，避免两份有效题面。原始来源、设计理由与 review 历史继续留在本工作区。

这里不作为 Agent 的整个输入目录。解题包只提供题面约定的源码和公开测试，终评 checker、参考解与隐藏场景分离。小型运行和校准报告按 [实验资产约定](../../experiments/README.md)保存，并在 `evidence_paths` 中引用仓库内路径；原始批量输出留在被忽略的 runs 中。

## 后端与复现

每道题在实现、校准后固定后端与工具链；当前 `backend: null` 表示尚未选定，不能据此声称 EVAS、ngspice 或 Spectre 已运行通过。公开自测的两种形式均保留，逐题选择：固定公开测试，或固定工程连接下自定义激励与观测。

优先寻找真实电路与配套 VA 模型。用 VA 替代器件电路时，保留候选接口、公开要求、验收标准及影响判定的电路效应，校准后才可称为同题复现。改变这些要求的简化版本另建关联 Case。固定工具链下可完整验收的 ngspice 题允许独立评分；后端能力造成的正确 VA 无法执行属于环境缺陷。完整规则见 [评测与复现原则](../docs/evaluation.md)。

## 维护入口

从仓库根目录运行：

```sh
python3 -B scripts/benchmark_workbench.py --write
python3 -B scripts/benchmark_workbench.py --check
```

前者校验后刷新索引和题卡摘要；后者只读检查重复 ID、引用、分类路径、设计版本和索引是否过期。它们不运行仿真，也不能证明 checker 正确、后端适用或题目具有区分度。生成内容只在标记块内或注明 Generated 的索引页中维护。
题目迁移后，刷新会移除不再需要且带完整生成标记的类别/家族索引页，手写设计记录保留。

分类和验收边界仍由 [Issue #107](https://github.com/BucketSran/vaEVAS/issues/107)承接；全局建设见 [Issue #72](https://github.com/BucketSran/vaEVAS/issues/72)。[研究目录](../research/README.md)用于跨题材料学习，这里用于逐题形成可 review 的设计。
