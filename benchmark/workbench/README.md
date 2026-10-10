# Benchmark 逐题设计工作区

这里保存从材料筛选到正式出题的设计记录，方便逐题 review。按 **工程动作 → 电路家族 → Case** 浏览；同一来源可以服务多道题，每道题保留独立身份。当前沿用已确认的五类方案，“测量与表征”和“开发验证工具”合并为“电路测试与表征”。

当前先看[按电路功能组织的迁移总览](migration/README.md#当前先按电路功能看迁移方向)，宏观判断主要迁移内容与工程用途。逐题细节按需从[设计 review 队列](REVIEW.md)查阅，不要求用户逐题审核完整规格和checker。每张题卡说明：材料本来有什么、拟让 Agent 做什么、如何独立验收、还有哪些问题未确定。当前候选仅到材料筛选和设计草案，尚无本轮仿真、配套 VA 模型校准或模型试做结果。

2026-10-10，用户已认可 case-0001 至 case-0010 的选题思路。现阶段先理清工程需求与任务边界，准备与领域同行讨论；入口为 [选题思路与专家讨论](DISCUSSION.md)。这些题卡的“待 review”针对具体设计，不要求现在逐项冻结数值和 checker。

旧 benchmark 的优先移植见[迁移筛选入口](migration/README.md)。新增 case-0011 至 case-0015 来自 v4 单模块素材。case-0011 已确认作为基础题保留，并补写[r2 规格](cases/spec-modeling/adc/case-0011-clocked-sample-hold/instruction.md)；case-0012已确认完整Alexander内部采样方向，其余三卡继续讨论。各卡具体设计和校准仍需 review，不沿用旧认证。

继续细看family111后，新增 [case-0016 比较器翻转电压与表观滞回测量](cases/testing-characterization/comparators/case-0016-hysteresis-characterizer/README.md)。r1记录原电路、测量合同和独立checker方案，尚待讨论与校准。

全部 v4 的GLM静态审核已完成400/400家族。当前先看[优先迁移清单](migration/v4-migration-priorities.md)，按电路功能查看五类对应、可复用资产、需重做部分和未选理由；[全库取舍索引](migration/v4-migration-index.tsv)用于追溯。[阶段功能汇总](migration/v4-functional-summary.md)保留历史快照，本轮未批量新建题卡。

<!-- workbench:begin -->

登记 **16 张候选设计卡**，不代表已发布或已通过验收的题目。

| 工程动作 | 候选数 |
| --- | --- |
| [按规格构建模型](cases/spec-modeling/README.md) | 5 |
| [从数据建立模型](cases/data-modeling/README.md) | 1 |
| [扩展与集成](cases/extension-integration/README.md) | 1 |
| [诊断与修复](cases/diagnosis-repair/README.md) | 4 |
| [电路测试与表征](cases/testing-characterization/README.md) | 5 |

| Case | 题目 | 工程动作 / 电路家族 | 阶段 / 设计 review | 本轮关注 |
| --- | --- | --- | --- | --- |
| [case-0001](cases/testing-characterization/power/case-0001-por-sequence/README.md) | POR 上电、欠压与恢复测试台 | 电路测试与表征 / 电源与复位 | 题目草案 / 待 review（r1） | 延迟起点及复位合同；首版只含上电、欠压、恢复 |
| [case-0002](cases/testing-characterization/power/case-0002-ldo-startup/README.md) | 固定 LDO 的启动指标测量 | 电路测试与表征 / 电源与复位 | 题目草案 / 待 review（r1） | 有限窗口定义、取样/事件语义及未建立状态 |
| [case-0003](cases/testing-characterization/amplifiers/case-0003-opamp-slew/README.md) | 运放压摆率激励与测量 | 电路测试与表征 / 放大器 | 材料筛选 / 待 review（r1） | 先选公开 DUT，再决定单向或双向测量 |
| [case-0004](cases/spec-modeling/pll/case-0004-adpll-dco/README.md) | 固定 ADPLL 工程内补齐 DCO | 按规格构建模型 / PLL 与时钟 | 题目草案 / 待 review（r1） | 先定粗调码频合同与换码相位语义，再建立健康 VA 闭环 |
| [case-0005](cases/spec-modeling/filters/case-0005-sc-opamp/README.md) | 为固定 SC 滤波工程建立运放模型 | 按规格构建模型 / 滤波与均衡 | 材料筛选 / 待 review（r1） | 电压域抽象能否保留本题需要的 SC 建立与过载恢复行为 |
| [case-0006](cases/data-modeling/adc/case-0006-sampling-identification/README.md) | 采样级固定数据包动态建模 | 从数据建立模型 / ADC 与采样 | 题目草案 / 待 review（r1） | 先确认可观测动态及数据覆盖，再冻结输入格式与验收误差 |
| [case-0007](cases/extension-integration/pll/case-0007-adpll-fine-tdc/README.md) | 为粗调 ADPLL 接入 fine TDC 路径 | 扩展与集成 / PLL 与时钟 | 材料筛选 / 待 review（r1） | 先具备健康粗调闭环与有效细调执行能力，再界定新增集成范围 |
| [case-0008](cases/diagnosis-repair/pll/case-0008-pfd-reset/README.md) | PFD 外部复位与挂起事件修复 | 诊断与修复 / PLL 与时钟 | 材料筛选 / 待 review（r1） | 先校正 v4 starter 来源与复位合同，再评估整体重写下的区分度 |
| [case-0009](cases/diagnosis-repair/power/case-0009-uvlo-reset-chain/README.md) | UVLO、复位释放与使能链的系统修复 | 诊断与修复 / 电源与复位 | 题目草案 / 待 review（r1） | 建立有真实模块依赖的健康电源控制链，再选择跨模块故障 |
| [case-0010](cases/testing-characterization/adc/case-0010-adc-spectrum-records/README.md) | 从 ADC 观测记录提取动态指标 | 电路测试与表征 / ADC 与采样 | 题目草案 / 待 review（r1） | 先冻结采样、频点与谱功率定义，再决定是否引入非相干窗口 |
| [case-0011](cases/spec-modeling/adc/case-0011-clocked-sample-hold/README.md) | 按规格建立边沿采样保持模块 | 按规格构建模型 / ADC 与采样 | 题目草案 / 待 review（r2） | 基础题已确认保留；r2 公开语义已补齐，过渡容差与 checker 待校准 |
| [case-0012](cases/spec-modeling/pll/case-0012-bbpd/README.md) | 按规格建立内部采样的 Alexander BBPD | 按规格构建模型 / PLL 与时钟 | 题目草案 / 待 review（r2） | Alexander 内部采样方向已确认；r2 初始化、发布、重合窗口与 checker 待 review |
| [case-0013](cases/spec-modeling/adc/case-0013-sar-handshake/README.md) | 按规格建立四位 SAR 前端握手模块 | 按规格构建模型 / ADC 与采样 | 材料筛选 / 待 review（r1） | 与既有 va02 的取舍；比较器合法事件、发布时刻与原工程来源 |
| [case-0014](cases/diagnosis-repair/power/case-0014-debounce-qualification/README.md) | 修复控制输入的去抖资格计时 | 诊断与修复 / 电源与复位 | 材料筛选 / 待 review（r1） | 完整重写后是否值得作为基础修复题；复位释放及初态边界 |
| [case-0015](cases/diagnosis-repair/power/case-0015-reset-release-sequencer/README.md) | 修复电源与偏置就绪后的复位释放序列 | 诊断与修复 / 电源与复位 | 材料筛选 / 待 review（r1） | 同步行为与合法阶段范围；纠正旧故障标签并评估重写难度 |
| [case-0016](cases/testing-characterization/comparators/case-0016-hysteresis-characterizer/README.md) | 比较器翻转电压与表观滞回测量 | 电路测试与表征 / 比较器与门限检测 | 题目草案 / 待 review（r1） | 测量定义、最近双向捕获语义与独立事件验收；数值容差待校准 |

<!-- workbench:end -->

## 如何 review

当前先用 [讨论说明](DISCUSSION.md)梳理工程动机、输入、交付和验收依据，再选一张题卡与领域同行讨论。POR 可说明完整测试流程，采样级可说明数据与动态建模，ADPLL 两题可帮助区分补模块与扩展系统。题卡中的“本轮需要确认”保留为后续细化线索，现阶段无需逐项定数值；同意方向也不等于具体设计、实现或校准已通过。

2026-10-10 新增 case-0004 至 case-0010：规格建模的 DCO 与 SC 运放、采样级数据建模、ADPLL fine TDC 集成、单模块 PFD 与多模块 UVLO 修复，以及 ADC 频谱测量。它们把已收集材料转成待讨论的工程合同，不是为了给五类凑齐相同数量的题。ADC 频谱卡重新审查已有任务，不重复新增计分项；两个 ADPLL 候选共用来源组。

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

仅认可选题思路时，在正文记录“方向认可”及其范围，保留具体设计的 pending 状态。本次方向认可不增加设计版本，不把未讨论的规格、数值和 checker 自动变成已批准要求。

正式任务仍放在 [benchmark/tasks](../tasks/)，沿用 Harbor 格式；题卡的 `task_path` 指向它。实现前，Case 内可以保留明确标注的 `instruction.md` 草案。正式题面建立后，此处改为链接，避免两份有效题面。原始来源、设计理由与 review 历史继续留在本工作区。

这里不作为 Agent 的整个输入目录。解题包只提供题面约定的源码和公开测试，终评 checker、参考解与隐藏场景分离。小型运行和校准报告按 [实验资产约定](../../experiments/README.md)保存，并在 `evidence_paths` 中引用仓库内路径；原始批量输出留在被忽略的 runs 中。

## 后端与复现

每道题在实现、校准后固定后端与工具链；当前 `backend: null` 表示尚未选定，不能据此声称 EVAS、ngspice 或 Spectre 已运行通过。公开自测的两种形式均保留，逐题选择：固定公开测试，或固定工程连接下自定义激励与观测。

优先寻找真实电路与配套 VA 模型。用 VA 替代器件电路时，保留候选接口、公开要求、验收标准及影响判定的电路效应，校准后才可称为同题复现。改变这些要求的简化版本另建关联 Case。固定工具链下可完整验收的 ngspice 题允许独立评分；后端能力造成的正确 VA 无法执行属于环境缺陷。完整规则见 [benchmark 合同](../README.md#评测方式与题目建设)。

## 维护入口

从仓库根目录运行：

```sh
python3 -B scripts/benchmark_workbench.py --write
python3 -B scripts/benchmark_workbench.py --check
```

前者校验后刷新索引和题卡摘要；后者只读检查重复 ID、引用、分类路径、设计版本和索引是否过期。它们不运行仿真，也不能证明 checker 正确、后端适用或题目具有区分度。生成内容只在标记块内或注明 Generated 的索引页中维护。
题目迁移后，刷新会移除不再需要且带完整生成标记的类别/家族索引页，手写设计记录保留。

分类和验收边界仍由 [Issue #107](https://github.com/BucketSran/vaEVAS/issues/107)承接；全局建设见 [Issue #72](https://github.com/BucketSran/vaEVAS/issues/72)。[研究目录](../research/README.md)用于跨题材料学习，这里用于逐题形成可 review 的设计。
