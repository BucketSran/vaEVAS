# EVAS 独立验证集

这里用最小 Verilog-A 模型、明确刺激和独立数学答案检查仿真器。
它关注“语言关系有没有被正确求解”，例如贡献相加、事件定位、采样历史和积分反馈。
[Benchmark 任务](../../benchmark/README.md)评估设计任务的完成质量，两类结果分别计数。

预期结果来自模型声明的方程与状态转移，而非 EVAS 输出或 Spectre 波形。
先确认测试模型按语言语义表达了目标行为，再建立预期答案；不能把理想化的设计意图
直接当成某段 VA 代码唯一正确的结果。

独立答案用于判断数学正确性；相同模型的跨后端对照用于检查兼容性。
两个实现给出相近结果，并不能单独证明它们正确；EVAS 独立测试通过，
也不能代替 Spectre 对照。为支持[模型移交](../README.md#model-handoff)，
对照需固定源码、参数、刺激和初值，并分别检查波形误差、事件次数、顺序与时刻。
接入实际器件网表后的负载和反馈行为另做集成验证，三个层次分别报告。

对照应先固定外部的电压、事件时刻、次数和顺序要求，再分别选择后端内部设置。
同名 reltol/vabstol 的数值相同不等于等精度；cross 定位、积分历史与采样误差分别检查。
设置扫描和失败都要保留，满足同一外部准确度目标后再做速度比较。
[振荡器专项](../../experiments/backends/dvs2-spectre-validation/README.md#oscillator-compatibility)
展示了这种区分：收紧某个容差既可能减小波形误差，也可能暴露更多返回事件。

测试文件声明的契约关联与能力证据入口见[追溯矩阵](../docs/development/TRACEABILITY.md)；
它不证明逐条件覆盖或执行通过。
验证目录分两级：[smoke/](smoke/) 是各能力路径的最小可运行冒烟集，
只验证链路连通，不带期望值；[cases/](cases/) 及各协议文档构成完整验证集。

近邻事件的非线性历史与 PWL 分段传播有[独立条件和冻结判据](ordered_event_history/README.md)，原始失败与严格计时诊断分别保留。

固定时钟、保持时钟与窗口内新根的组合见[有序事件源契约](ordered_event_sources/README.md)。
[物理采样相位检查](ordered_event_sources/candidate-phase/README.md)分别验证实际返回状态、直接输出和规定拒绝。

## 验证集包含什么

原矩阵固定为 **31 个条件**：14 个不变的 v1 条件、1 个低通标准数组语法修订、
7 张补充卡展开的 16 个条件。每个条件固定模型、参数、刺激/初态、观察方式和性质。
基础档与细化档各以 31 为分母；配置数、源码数、检查点数和开发测试方法数另外报告。

<a id="七组行为要求"></a>

独立需求分为静态传递、参考/供电、阈值事件、采样复位、延迟边沿、连续动态与相位、
组合反馈七组。31 条件只覆盖其中一部分；更完整的义务与判定依据见
[范围与判定协议](PROTOCOL.md)。

## 从哪里开始

| 目的 | 入口 |
| --- | --- |
| 查看新论文集的特性映射、有限首批和独立条件卡 | [论文比较设计](paper/README.md)，设计与冻结条件；[当前 main 实测](../../experiments/backends/support/README.md)保留 I/X |
| 检查支持表的 15 个专项探针 | [固定模型、判据与校准](support/README.md)，有限开发观测 |
| 检查两级固定 slew 的独立公式与实际配对 | [输入生成与检查器](slew_cascade/compare.py)、[范围和实测](../../experiments/backends/slew-cascade/README.md) |
| 查看模型源码与条件对应关系 | [共同 DUT](cases/README.md) |
| 理解原条件的刺激、答案与错误对照 | [起步案例卡](CASE_CARDS.md)、[补充案例卡](NEXT_CASE_CARDS.md) |
| 理解误差、事件历史与正式资格 | [范围与判定协议](PROTOCOL.md)、[观察资格协议](METHOD_QUALIFICATION.md) |
| 查看当前实现的组合边界 | [四后端支持范围](../docs/COMPARISON.md)、[连续动态手册](../docs/math/continuous.md) |
| 找到执行结果、版本与原始材料说明 | [实验目录](../../experiments/README.md) |
| 运行 ngspice 共同子集对照 | [差分验证](differential/README.md) |
| 检查两类事件路径重构是否保持行为 | [共同事件验收](event_acceptance/README.md)：六模型、十二配置，原数学失败与观察限制单列 |
| 运行新增功能组合的有限确认 | [确认集及冻结检查器](confirmation/README.md) |
| 核验历史输入没有被改写 | [冻结 v1](versions/v1/README.md) |

## 当前结果与历史比较

<a id="latest-evas-checkpoint"></a>

### 当前源码与执行检查点

PR61 的 EVAS 0.13.0 / IR17 检查点 `d68d3db4` 已重跑原矩阵，两档各 **31/31**；
既有七案例确认复跑共 **14/14**。构建、源码、检查器和有限资格范围见
[提交前收据](../../experiments/runs/capability-completion/review-receipt.json)。
这些复跑没有增加未见条件数量。合并身份以 [PR61](https://github.com/BucketSran/vaEVAS/pull/61) 为准。

此前重新构建并执行 main `a7a42e17`（[PR50](https://github.com/BucketSran/vaEVAS/pull/50)，
EVAS 0.12.3 / IR16）：原矩阵两档各 **31/31**，62 份 CSV 与 PR33 收据中的哈希一致。
模型、条件与设置也逐文件匹配历史收据。检查器保留原判断公式和阈值；
目录迁移后的当前文件身份单独记录。源码、内核、逐配置判定及限制见
[本轮收据](../../experiments/runs/parallel-gap-integration/results/main-0.12.3-matrix.json)。

PR33 / 0.12.2 的历史结果仍见[原收据](../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json)，
不改写为新版本成绩。开发回归、ngspice 共同子集与原矩阵分别计数。

<a id="精度方案候选指标不冻结统一阈值"></a>

达标表示满足所列有限观测判据。误差预算与判定依据见
[精度方案](PROTOCOL.md#精度方案候选指标不冻结统一阈值)。完整观察不确定度与连续时间资格尚未完成，
**正式 DVS 资格仍为 I（未决）**。这些条件已用于开发，不能再称为未见确认集。
上述矩阵收据只有本地 EVAS 执行，没有新运行 Spectre，也没有重判旧 Spectre 波形。
GitHub CI 的 ngspice 共同子集是另一项检查，不能替代原矩阵的后端对照。

<a id="historical-four-backend-baseline"></a>

### 历史四后端基线

2026-09-28 在 thu-sui 完成 31 条件 × 四后端 × 两档，共 248 条配置记录：

| 固定后端 | 基础档达标 | 细化档达标 |
| --- | ---: | ---: |
| Spectre | 31/31 | 31/31 |
| 旧 EVAS 0.8.7 | 18/31 | 8/31 |
| OpenVAF-R＋ngspice | 16/31 | 16/31 |
| Gnucap＋modelgen-verilog | 17/31 | 16/31 |

这是固定旧版本的[历史矩阵](../../experiments/backends/dvs2-four-backend-validation/results/MATRIX.md)，
不把新版 EVAS 成绩填入旧表。失败、执行身份和设置分别保留。
IR15 至 IR16 的历次验证见[联合验证记录](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/parallel-gap-integration/README.md)。

## 专项契约

专项契约把原矩阵之外的状态、精度和组合要求展开，便于在实现前确定数学答案。
开发探针不会自动增加原 31 条件的分母。

| 契约 | 主要问题 |
| --- | --- |
| [普通 analog 条件](ANALOG_CONDITIONS_CONTRACT.md) | 局部顺序赋值、输入条件与分段仿射关系 |
| [定时与波形算子](TIMED_OPERATOR_CONTRACTS.md) | timer、有限边沿、延迟、限速与独立数学样例 |
| [积分与共同生命周期](DYNAMICS_CONTRACTS.md) | 初值、复位、历史误差、候选提交/回退及不变性 |
| [事件条件与采样复位](EVENT_CONDITIONS_CONTRACT.md) | if/else、cross OR、多事件写者和采样语义 |
| [滤波](LAPLACE_CONTRACTS.md) | 系数数组、启动响应与滤波采样 |
| [非线性瞬态](NONLINEAR_TRANSIENT_CONTRACT.md) | 独立根、前向误差与认证边界 |

2026-09-30 的 [S1 审阅补充](NEXT_CASE_CARDS.md#s1-review)增加了有理数正例、
错误波形与容差校准，并登记贡献顺序变体。该变体尚未执行后端，不把原分母改为 32。

<a id="local-checks"></a>

## 本地数学与身份检查

从仓库根目录运行，以下命令无需 Rust 内核或商业仿真器：

```sh
python3 -B evas/validation/check_design_math.py
python3 -B evas/validation/check_timed_operator_math.py
python3 -B evas/validation/check_dynamics_math.py
python3 -B evas/validation/check_event_conditions_math.py
python3 -B scripts/verify_validation_version.py
```

前四项检查数学关系和构造的正反校准，最后一项核验冻结 v1 的 Git 对象及输入身份。
它们不执行后端、不增加矩阵达标数。执行仿真请从
[EVAS 运行示例](../README.md#构建与运行)或具体实验协议进入，并保存新的执行身份。

## 版本与资产

`validation-v1` 是原 15 条件的冻结快照；`DVS-2` 和 `v2-draft-20260928` 是历史设计/批次名称，
不是 EVAS 软件版本或资格认证。冻结页与原输入保留原字节，修订使用新的模型与执行身份。
协议、判据、精简结果与收据在仓库内；大波形与日志仅本地保留，具体可用性见实验 README。

<details>
<summary>历史 IR15 检查点与原矩阵缺口的补齐过程</summary>

<a id="ir15-checkpoint"></a>

### 历史 EVAS：IR15 交付检查点（2026-10-01）

运行时 `d451605bf9991ceea010c68af9cb1143f1b50754`，EVAS 0.9.0 / IR v15。
普通 analog 条件、一阶滤波、相位与无状态多项式瞬态已联合验证，且保留受限事件与积分复位。
[精度链 review](../../experiments/runs/parallel-gap-integration/REVIEW.md#precision-chain)、
[逐配置收据](../../experiments/runs/parallel-gap-integration/results/precision-chain-matrix.json)及
[开发检查收据](../../experiments/runs/parallel-gap-integration/results/precision-chain-checks.json)绑定实际源码与二进制。

| 被测 EVAS 检查点 | 基础档 | 细化档 | 执行身份 |
| --- | ---: | ---: | --- |
| PR26 运行时 `edb004d` / IR11 | 24/31 | 24/31 | 历史已合并检查点，本轮复用结果 |
| 联合功能 `39a4545` / IR15 | 31/31 | 31/31 | 历史 62 次本地执行 |
| 优化 `ddfd379` / IR15 | 31/31 | 31/31 | 历史 62 次本地执行 |
| 精度链 `d451605` / IR15 | **31/31** | **31/31** | 该 IR15 检查点的 62 次新本地执行 |

该轮的 62 份 CSV、判定和生效设置与 `ddfd379` 一致；原 DUT、刺激、网格、目标、检查器和分母未改。
372 Python、83 Rust 测试与 locked build、Clippy、格式检查通过；一项旧性能探针 ignored。
该轮修复没有新 Spectre 执行或重分析，也未重测性能；完整 raw 仅本地保留。
“达标”只指所列有限观测判据，**正式 DVS 资格仍 I（未决）**。
这些条件已用于开发诊断，不是未见确认集，也不证明全时域精度或完整语言合规。

<a id="candidate-gap-completion"></a>

### 历史功能补齐与 PR26 基线

[联合功能记录](../../experiments/runs/parallel-gap-integration/REVIEW.md#gap-completion)固定 `39a4545`：
相对 analog `9c5d6c5` 的各 25/31 新增六条，原达标 50 份 CSV 逐字节一致。
该轮重新核验上一轮 Spectre 的 62 次结果，各 31/31；没有新启动 Spectre。
[PR26 复位对照](../../experiments/archive/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)保留
`edb004d` 各 24/31 与 PR25 `6df7f48` 各 22/31 的原执行，不能由新结果覆盖。

<a id="remaining-original-31"></a>

### 已补齐的原矩阵缺口

PR26 的 7 个拒绝条件已在 IR15 的限定范围内补齐，并由上面的新联合矩阵验证。
拒绝表示实现范围不足，不表示合法 VA 本身有错；历史失败仍保留。

| 原条件 | 数量 | IR15 的受限能力与数学入口 |
| --- | ---: | --- |
| `v1-main` | 1 | [顺序局部赋值、输入 if/else 限幅](ANALOG_CONDITIONS_CONTRACT.md) |
| `v6-standard`、`c2-main` | 2 | [常量数组、一阶 laplace_nd 与滤波采样](LAPLACE_CONTRACTS.md) |
| `d2-constant`、`d2-chirp` | 2 | [idtmod、受限 sin 与相位误差](../docs/math/operators.md#idtmod-与-sin) |
| `v7-nonlinear-0.5`、`v7-nonlinear-2.0` | 2 | [无状态、无事件、无历史多项式瞬态](NONLINEAR_TRANSIENT_CONTRACT.md) |

原 31 条件已没有未达标项；更广的 DAE 与事件/复位组合、事件后历史轨迹重定位及验证资格缺口仍见
[四后端支持范围](../docs/COMPARISON.md#支持矩阵)，不要从开发矩阵满分推导完整仿真器覆盖。

</details>
