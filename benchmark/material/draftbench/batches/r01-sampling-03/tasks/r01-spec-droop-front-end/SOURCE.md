# 来源与建设记录

2026-10-29 按 P1 建题（R01 第一单的第二题）新建，阶段 implementation，`pending = ["grading", "runtime"]`。本机没有 Spectre，本题**未仿真**：没有执行 Spectre 电路仿真，也没有运行模型解题；EVAS 结果只作开发证据。本页不表示科学校准、模型试做、题目审核或正式录取。

## 行为依据

### 规划候选身份

| 项目 | 值 |
| --- | --- |
| task_id | `C067-S1`（规划候选，规格建模） |
| unit_id / primary_ref | `C067` / `C067` |
| 主来源 | `src-c7493e03f385`：v4:100-sample-hold-droop-front-end 的历史修订，local-only。路径文本 `证据卷/historical-purification-20261022/improve-packs/sampleholddroopfrontend/OUTPUT/instruction.md`，SHA256 `acd3a1de2e51433ad78ff7062cd63e4f10613074a96f2486938a7c93467f5920`，与[规划来源表](../../../../planning/history-candidates/sources.json)一致；外接盘只读 |
| 规划登记 | [register.json](../../../../planning/history-candidates/register.json) 的 C067-S1：P1，结构估计难度 M，建设成本 M，“补行为边界”；可复用“孔径预约、valid脉冲、采样时轨间钳位及tau/dt参数”；作者工作“明确低时钟期间的下垂更新式、目标电平与采样/下垂冲突；保留采样瞬间电源轨”；差异“多种机制在同一保持状态耦合”。[候选说明](../../../../planning/history-candidates/CANDIDATES.md#c067-s1)同此；排序理由是先复用 C056 与 C057 的边界经验 |
| Grok 意见 | 采纳缺口：完整修订原题有 tau = 90 ns 和 dt = 0.5 ns，但没有唯一的下垂更新关系。本题把它定为唯一的、可评分的规则（建设决定第 8 条） |
| P1 队列 | `runs/t3-p1-plan-20261028/p1-queue.json`：C067-S1 没有同源的已建题，不需要独立性检查 |

本题号 `r01-spec-droop-front-end` 沿用Benchmark 维护方 brief。`source_group` 取新组名 `v4-100`，覆盖 v4 100 与同族的 1100（bugfix）、600（testbench）和外接盘上的历史修订；SOURCE_GROUPS 中原无此组，正式组名由Benchmark 维护方登记时确定。

### 讨论记录中的已定事项

本线讨论记录在工作树外：`local/research/benchmark-submission-20261025/README.md`（SHA256 `562a36df97370ff163d45d81200d104b4a228695982a99e5c037375770c97c19`），只读。检索 C067、C057、droop、leak、下垂、sampleholddroopfrontend 等词，相关的是以下三节（同 C057-S1 的检索）；决策卡目录没有本题的卡。

- 「R01B · 单级保持误差扩展」（第 688 行起）：扩展与集成任务，从健康 basic 增加注入与漏电，保留原采集。本题是规格建模，没有有限采集与注入；下垂受时钟门控、在固定网格上按 `exp(−dt/tau)` 分步，并与孔径、钳位、`valid`、`coarse` 耦合。两者都涉及保持误差，但交付责任和机制不同，不是同一职责；R01B 仍待建。
- 「H08 · 保持下垂与孔径非理想参考」（第 1194 行起）：待补“优先并入 R01 保持误差的材料；若单独成题须有不同采样/孔径合同”。本题与同族已有题的采样合同不同，见下节：C056-S1 的孔径采样明确不钳位、电压对地、没有 `valid`、`coarse` 与下垂；本题在采样瞬间按当时的电源轨钳位，以 `vss` 为参考，同一保持值还受时钟门控的下垂改写。
- 「E12 · 单级采集/下垂与全窗口建立判定」（第 918 行起）：测量类方向，不是规格建模，不重复。

### 历史原件与改编

[v4 100 发布题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/100-sample-hold-droop-front-end/public/instruction.md)（SHA256 `e7634c32…b8ae`）规定：`clk` 上升穿越后经 `taperture` 采样；采样时读 `vin`，把保持值钳到本地 `vss` 到 `vdd` 之间，更新 `vout`，置位 `valid`，更新 `coarse`；`coarse` 在采样值高于 `vth` 时为高；时钟低电平期间用 `tau` 和 `dt` 施加“有界下垂”；`valid` 在 `valid_width` 后撤销。参数缺省 `vth = 0.45 V`、`trf = 40 ps`、`tau = 90 ns`、`dt = 0.5 ns`、`taperture = 200 ps`、`valid_width = 2 ns`，端口 `vdd, vss, clk, vin, vout, valid, coarse`。外接盘上的历史修订（`OUTPUT/instruction.md`）只加了一句：钳位用孔径采样瞬间的 `vss`、`vdd`，更新后的 `vout` 位于两轨之间。本题沿用这些行为、缺省值和端口顺序。

[v4 100 gold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/100-sample-hold-droop-front-end/evaluator/solution/sample_hold_droop_ref.va)（SHA256 `2318eaa2…7276`）只作实现线索：全部电压相对 `vss`；采样时用 `V(vdd, vss)` 钳位、置 `coarse` 与 `valid` 的高电平；`timer(0, dt)` 网格上 `clk` 为低时把输出乘 `exp(−dt/tau)`；`valid` 在同一网格上、`$abstime > valid_until` 时才撤销，所以实际脉宽是 2.275 ns。参考解另写，没有复制。

历史修订的审核记录（`DEFECTS.json`，SHA256 `a5dc9fde…28e4`；`OUTPUT/CHANGES.md`，SHA256 `185f7ee0…ff57`）只修了一项：原台架电源轨恒定、`vin` 从不越轨，钳位分支从未被触发；修订在 170 ns 后追加越轨采样和 `vss`、`vdd` 的变化。它列为“不修”的覆盖缺口包括：参数全部取缺省、`valid` 按 `dt` 网格撤销使脉宽长 14 %、“有界”没有量化、`valid`/`coarse` 电平与初态未规定、`coarse` 在采样时判定还是随下垂连续判定无法区分。历史 checker（`CHECKER_SOURCE/closure.py`，SHA256 `a91d83a2…aa17`）按连续指数 `start·exp(−Δt/tau)` 比较下垂，容差 max(35 mV, 12 %)，离散与连续两种下垂都能通过，这就是 Grok 指出的“没有唯一的下垂更新关系”。本题不继承它的判据和成绩。

同族历史形式按实际改动核对：
- [v4 1100 坏版](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1100-sample-hold-droop-front-end-bugfix/public/buggy_bundle/sample_hold_droop_ref.va)：改为下降沿触发，`vout` 与 `valid` 乘 0.42。
- v4 600 的五个负例：`neg_001_zero` 三个输出都为 0；`neg_002_threshold_shifted` 把 vth 缺省改为 0.57 V 并乘 0.42；`neg_003_event_edge_wrong` 与 1100 坏版相同（下降沿加 0.42）；`neg_004_aperture_delay_removed` 在沿上立即采样；`neg_005_metric_scale_low` 只乘 0.42。按实际改动，本题收 `historical_v4_1100_buggy`、`zero_outputs`、`vth_default_0p57`、`no_aperture`、`output_scale_0p42`、`falling_trigger` 六个候选，不按名字另列。

### 同源关系与职责差异

| 题目或候选 | 来源组 | 职责 | 与本题的关系 |
| --- | --- | --- | --- |
| 首批30 [v2-spec-024](../../../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) | `v4-024` | `V(CLK, VSS)` 上升穿越时立即采样，输出相对本地电源，初态 `OUT = VSS`，电源恒定 | 同样以 `vss` 为参考、初态为 `vss`；本题在孔径时刻采样，按采样瞬间的电源轨钳位，另有 `valid`、`coarse` 和时钟门控的下垂 |
| 第二批草稿 [v2-spec-071](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md)（C055 已并入） | `v4-071` | 采集窗口内在全局 tick 上按 `alpha` 逼近输入 | 都有从 t = 0 起的全局网格；071 的网格驱动获取期动态，本题的网格驱动保持期下垂，只在时钟低电平时生效 |
| R01 [r01-spec-ideal](../../../r01-sampling-01/tasks/r01-spec-ideal/instruction.md)、[r01-spec-acquisition](../../../r01-sampling-01/tasks/r01-spec-acquisition/instruction.md) | `r01-ideal`、`r01-basic` | 透明跟踪保持；连续有限采集 | 机制不同 |
| R01 [r01-spec-aperture-delay](../../../r01-sampling-02/tasks/r01-spec-aperture-delay/instruction.md)（C056-S1） | `v4-family-072` | 上升沿预约、孔径时刻读入；`VDD`、`VSS` 不影响模型，不钳位；电压对地；无复位、无下垂 | 复用其“预约一次、孔径时刻读入、读入时刻的 `clk` 电平无关、触发间隔大于孔径”的边界经验。本题另加采样瞬间钳位、`vss` 参考系、`valid`、`coarse` 与下垂；初值为 `vss` 而不是 vin(0) |
| C057-S1 [r01-spec-droop-leakage-hold](../r01-spec-droop-leakage-hold/instruction.md)（同批） | `v4-042` | 自由运行网格上每步乘 `decay` 的泄漏，与 `sample` 电平无关，异步复位 | 复用“全局网格从 t = 0 起、事件离网格时刻 50 ps 以上、离散律与连续律可分”的边界经验。本题的下垂受 `clk` 门控（候选 `droop_always` 被拒），每步因子为 `exp(−dt/tau)`，没有复位，并与孔径、钳位耦合 |
| R01B（规划，未建） | — | 从健康 basic 增加注入与漏电 | 职责不同，见上节 |
| C061-S1、C068-S1（规划，不在本单） | — | 双轨两级保持；跟踪保持切换与累计下垂监控 | 本单不建。规划说明已写明 C068 与本题的区别：本题是边沿延迟采样，C068 持续跟踪后再进入保持；C061 的两级相位传递也不是本题职责 |
| 原56题 | 各自来源组 | 024、071、`v2-data-sampling-identification` 与采样相关 | 本次只读采样相关题面，未复审全部 56 题；没有题以 v4:100 为来源 |

本题只计 C067-S1 一项，不与上述各题重复计数。

### 外部来源与许可

来源声明分三类（完整清单见 sources.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/sources.json`））：

1. 新写的实现：参考解、checker（`tests/verify.py`，公开副本相同）、用例与公开台架（由证据目录的 build_cases.py（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/build_cases.py`） 生成）、`tests/calibration/` 三件（34 个错误候选由参考解经检查过的文本替换得到，另有作者写的五个正确或余量候选）、题面与本页。共用的 Harbor 运行文件与首批模板逐字节相同，不是本题新写的。
2. 从仓库内历史资产原样读取的对照：校准候选 `original_v4_100_gold`、`historical_v4_1100_buggy` 由 `mutants.py` 在仓库内运行时从 `benchmark/material/historyref` 读取原字节，只把模块名改为本题的 `sample_hold_droop`，题包不存其文本。外接盘上的历史修订与历史 Spectre 运行只读，没有复制任何文件。
3. 外部许可代码：没有复制任何外部代码。

| 来源 | 版本 | 许可 | 用途 |
| --- | --- | --- | --- |
| [Verilog-AMS LRM](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（Accellera） | 2.4.0，2014-05-30；PDF SHA256 `621b2a1a3751e7685600f180fe8f362766fe13e952023ded3d7ae48314337c03` | 标准文本，版权所有 | 按 5.10.3.1 `cross()`、5.10.3.3 `timer()`（绝对 timer 在时刻改变时重新排定，周期 timer 从起始时刻起）、4.5.8 `transition()`、5.10.2 `initial_step` 写参考解和校准候选。未复制文字 |
| [ADI MT-090](https://www.analog.com/media/en/training-seminars/tutorials/MT-090.pdf)，Walt Kester，“Sample-and-Hold Amplifiers” | Rev.0 10/08，版权 2009；PDF SHA256 `fce0494588ad54cf7e286b1f3f21dd15c034306ef711a477b0b3a3c46ffdda96`（取得记录在 C057-S1 证据目录） | Analog Devices 版权教程 | 只引用工程定义：孔径延迟决定输入相对采样时钟沿实际被采样的时刻；保持期间漏电流使保持电压下垂。未复制文字或图 |
| [Arcadia-1/behavioral-veriloga-eval](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd) | 提交 `7b5616dc52195ec275ec6d21c71d7763613702cd` | 公开仓库，顶层未见 LICENSE | 只用于记忆污染核对：其 v4 100 gold 的 git blob 为 `9f582279…0dab`，与本仓库 historyref 副本相同。未复制代码 |

记忆污染风险：中到高。公开 v4:100 gold 与本题的端口、参数、孔径预约、钳位、判定、下垂网格和下垂因子 `exp(−dt/tau)` 都相同，只差模块名和 `valid` 的结束时刻。改名后原样提交，它在六个用例都因 `valid` 晚落而被拒（旧版开发证据，与预期一致）；但只要改一行 `valid` 的撤销方式就能通过。外接盘上的修订题面与审核记录是 local-only，不在公开仓库。评测时应考虑模型可能见过原题。

## 建模选择

### 建设决定

1. 模块名改为 `sample_hold_droop`，端口顺序沿用。理由：原名 `sample_hold_droop_ref` 的 `_ref` 是历史 gold 命名，按 C056-S1 先例改为电路功能名。
2. 参数与合法域：`vth` 0.2–0.7 V，`trf` 10–200 ps 且不大于 `dt/4`，`tau` 10 ns–1 µs，`dt` 0.2–5 ns，`taperture` 20 ps–2 ns，`valid_width` 0.5–10 ns。原题写“有限实数”“≥ 0”“> 0”。理由：终评要覆盖参数端点；`trf ≤ dt/4` 保证每次下垂更新在下一次之前到达并留下评分行；`taperture > 0` 同 C056-S1 的 Q2（零孔径退化为沿上采样，且预约与读入同刻）。这是缩域，原列待用户确认 Q5（待确认清单第 56 项），已定（用户 2026-10-29，决定单第 33 项）。
3. 【已定（用户 2026-10-29，决定单第 32 项）；原标“待用户确认 Q4”，即待确认清单第 55 项】参照系与电源轨：`V(vss)` 在一次运行中恒定，取 −0.2 V 到 +0.2 V；`V(vdd) − V(vss)` 在 0.8–1.5 V；`vdd` 只在 `valid` 与 `coarse` 都为低时变化，且离任一采样时刻 0.5 ns 以上不变。时钟门限、判定门限、下垂目标和低电平都以 `V(vss)` 为参考；`vout = V(vss) + h`。理由：本地电源的前端以 `vss` 为地（与 v2-spec-024 一致，gold 也如此）；在这一合法域里，“采样后是否随 vdd 重新钳位”“高电平锁存还是跟随 vdd”“`vss` 移动时保持值是否跟随”三个问题都不出现，合同唯一。历史修订台架曾让 `vss` 变化，但刻意避开了这些情形。另一读法：允许 `vss` 移动并规定保持值跟随 `vss`（保持电容下极板接 `vss`），允许 `valid`/`coarse` 为高时 vdd 变化并规定高电平跟随 vdd。
4. 采样：`V(clk) − V(vss)` 在 t = 0 之后上升穿过 `vth` 为触发，预约唯一一次采样于 `c_k = t_k + taperture`；触发时刻的 `vin` 不用；下降穿越和 `c_k` 时 `clk` 的电平都不开始也不取消采样，`clk` 已回到低电平时照样采样；相邻触发至少相隔 `max(taperture, valid_width) + 0.5 ns`，所以触发时没有待采样，`valid` 也在下一次采样前结束。理由：沿用原题与 C056-S1 的边界；`param-override` 有两次时钟高电平短于孔径的采样（候选 `need_clk_high` 被拒）。
5. 钳位：在 `c_k` 读 `V(vin) − V(vss)` 与 `V(vdd) − V(vss)`，`h` 取前者钳到 0 到后者之间（作者工作“保留采样瞬间电源轨”）。`base` 中 vdd 在两次采样之间降到 0.8 V，下一次 1.05 V 的采样钳到 0.8 V；`param-override` 在触发后、采样前 1 ns 改 vdd，分出“在触发沿读电源轨”的写法；`rails-reference` 有低于 `vss` 的采样。
6. `coarse`：在 `c_k` 当 `h > vth` 时为高，否则为低，保持到下一次采样，下垂不改变它；合法域要求每个 `h` 离 `vth` 至少 5 mV（用例至少 20 mV），所以严格大于与大于等于不可区分，也不必区分。理由：沿用 gold；原题“derived from the held sample”读作采样判定。`base`、`rails-reference` 各有一个 0.47 V 的样本在低电平期间下垂到 0.45 V 以下，“随下垂重判”的写法被拒。
7. 【已定（用户 2026-10-29，决定单第 30 项）；原标“待用户确认 Q2”，即待确认清单第 53 项】`valid`：从 `c_k` 到 `c_k + valid_width` 为高，其余为低。理由：参数名就是脉冲时长；gold 把撤销量化到 `dt` 网格、脉宽变成 2.275 ns，历史修订的审核已列为缺口。另一读法是沿用 gold：在 `c_k + valid_width` 之后的第一个下垂更新时刻撤销。
8. 【已定（用户 2026-10-29，决定单第 29 项）；原标“待用户确认 Q1”，即待确认清单第 52 项】下垂律（Grok 采纳的缺口）：更新时刻 `u_j = j·dt`（j = 1, 2, …），从 t = 0 起，由模型自己产生；在 `V(clk) − V(vss) < vth` 的更新时刻，`h ← h·exp(−dt/tau)`；`clk` 为高的更新时刻 `h` 不变；`h` 只在采样与这些更新时改变，下垂趋向 `vss`、不越过它。理由：参数里同时有 `tau` 与 `dt`，`dt` 是更新间隔，离散更新律最自然；因子 `exp(−dt/tau)` 使不间断的低电平段在 `dt` 的整数倍上与时间常数 `tau` 的连续指数完全一致；gold 与其历史 Spectre 运行逐个确认了这一网格、因子和门控（见下文）。“有界”在这一律下自动成立，题面改写为“趋向 vss、不越过它”。另一读法是低电平期间连续指数 `dh/dt = −h/tau`（`dt` 不再起作用），或网格从每个下降沿起算；它们与 Euler 因子 `1 − dt/tau` 都在本题用例中被拒（Euler 只在 `param-override` 可见）。
9. 【已定（用户 2026-10-29，决定单第 31 项）；原标“待用户确认 Q3”，即待确认清单第 54 项】同刻：每个 `clk` 穿越与每个采样时刻离任一下垂更新时刻至少 50 ps（用例至少 50.75 ps，修正 r1 后）。理由：`clk` 穿越恰在更新时刻时，该次更新是否生效取决于事件次序；`clk` 已低时采样恰在更新时刻，先下垂后采样与先采样后下垂差 `h·(1 − exp(−dt/tau))`（0.8 V 时 4.4 mV，超过 2 mV），属 TIE-RULE 第 (ii) 类，必须避开。`valid` 结束与更新时刻同刻只涉及不同输出，属第 (i) 类，合同不排除（`param-endpoints-low` 中最近 6.75 ps）。另一读法是规定次序（例如“同刻时先下垂后采样”）并保留同刻输入。
10. 初态：t = 0 时 `h = 0`（`vout = vss`），`valid`、`coarse` 为低，与输入无关（沿用 gold，原题未写）。t = 0 时 `clk` 已高不算触发，由修正 r1 新加的 `start-high` 终评（审核 R01-05）；整段没有触发的记录 checker 照常评分（审核 R01-03，见“2026-10-29 修正 r1”一节）。
11. 输出与评分起点（F01，用户已确认 2026-10-28，经项目协调方答复“全部按推荐”）：`vout` 驱动 `V(vss) + h`，`valid`、`coarse` 高为 `V(vdd)`、低为 `V(vss)`；每个输出在改变其期望值的时刻后 trf 内到达；只有该输出的期望值一次变化超过 0.1 mV（题面写明的门限 δ，修正 r1，LIST 第 4.9 版第 0.5 节第 20 条）时才开不评分窗（C109 写法），窗长 1.25·trf，不超过 0.1 mV 的变化不开窗；误差上限 2 mV；评分波形步长不粗于 trf/4。迟到负例 `late_arrival_1p3trf` 八例都被拒，窗内对照 `margin_arrival_1p2trf` 八例都通过，这是用户已接受的余量。
12. 合法输入：`clk` 在 `V(vss)` 与 `V(vss) + 0.9 V` 之间切换，边沿不长于 200 ps（修正 r1 在题面写明：转移指 `V(clk) − V(vss)` 离两个电平都超过 1 mV 的那段时间；checker 由保存行检查，审核 R01-06），不停在门限、不触碰后返回，t = 0 时离门限至少 50 mV（P0 触碰门限决策卡推荐 A）；相邻穿越至少 1 ns；`vin` 在 −0.5 V 到 1.8 V 之间，采样时刻前后 trf/4 内变化小于 0.25 mV。trf/4 与评分步长上限相同，保证 checker 由行插值读到的 `vin` 就是采样值，同时让 20 ps 的最小孔径仍能在孔径内改变 `vin`。
13. 不沿用 v4 对电流贡献、`ddt()`、`idt()` 的语法限制，理由同 C056-S1 第 12 条。
14. 用例共 8 个，公开 1 个（`base`）。每个采样时刻与 `valid` 结束都落在各自输出网格行之后的固定相位，其后 (1.25·trf, 1.3·trf) 内有评分行；修正 r1（审核 R01-08）后没有保存行恰在任何一次变化的评分起点 1.25·trf 上（缺省参数的四例改为 8 ps 网格、穿越在行后 5 ps，下垂更新落在行上或行后 4 ps；`param-override` 2 ps 网格、行后 0.5 ps；`param-endpoints-low` 2 ps 网格、行后 1.25 ps；`interrupt` 4 ps 网格、行后 1 ps）。`param-override` 与 `interrupt` 的下垂台阶大到能看出迟到，它们的下垂更新落在网格行上，其后第一个评分行在 1.26·trf，作为下垂更新的迟到对照行（见文末一节第 4 条）。每次采样前，`vin` 先停在一个诱饵值，再在孔径内改到采样值：

| 用例 | 参数与电源 | 主要区分 |
| --- | --- | --- |
| `base`（公开） | 默认，8 ps 网格；vdd 0.9 V（期间降到 0.8 V 再回升），vss 0 V | 八次采样；0.47 V 样本在 14 ns 低电平内下垂到 vth 以下而 `coarse` 不变；1.05 V 钳到 0.9 V 与 0.8 V，−0.15 V 钳到 0 V；高电平 1.504–8 ns；保持期间 `vin` 变化；触发离更新时刻最近 53 ps |
| `rails-reference` | 默认，8 ps 网格；vss 0.15 V，vdd 1.05 V（期间降到 0.95 V，跨度 0.8 V 下端），200 ps 时钟边沿（合法最长） | 门限、判定、下垂目标、低电平都相对 vss；0.55 V 的输入对 vss 只有 0.40 V，判低；0.05 V 钳到 vss；地参考门限早 33 ps |
| `phase-grid` | 默认，8 ps 网格 | 十个周期的下降沿在更新时刻后 53 ps 或前 55 ps，采样时刻在更新时刻前 55 ps 等多种相位；低电平 3.8–12 ns、高电平 1.104–6 ns |
| `param-override` | vth 0.25 V、trf 100 ps、tau 10 ns、dt 2 ns、taperture 1.5 ns、valid_width 4 ns，180 ps 时钟边沿，2 ps 网格 | 两次采样时 `clk` 已回到低电平（时钟高电平 1.02 ns 与 1.2 ns）；孔径窗口内 vdd 降到 0.85 V；0.30 V 样本只在 vth = 0.25 V 时判高；每步下垂 18 %（`exp(−0.2)`，不是 0.8） |
| `param-endpoints-low` | vth 0.2 V、trf 10 ps、tau 10 ns、dt 0.2 ns、taperture 20 ps、valid_width 0.5 ns（都在下端），2 ps 网格 | 20 ps 孔径内触发后 4.75–8.75 ps 改变 `vin`；1.002 ns 的时钟高电平（1 ns 下界加一个 2 ps 网格步）；离下垂更新 50.75 ps 的采样（50 ps 下界加不到一个网格步）；0.25 V 判高、0.12 V 判低 |
| `param-endpoints-high` | vth 0.7 V、trf 200 ps、tau 1 µs、dt 5 ns、taperture 2 ns、valid_width 10 ns（都在上端），40 ps 网格 | 0.75 V 判高、0.60 V 判低；10 ns 的 `valid`；每 5 ns 0.5 % 的下垂；0.45 V 门限早 50 ps |
| `start-high`（修正 r1 新加） | 默认，8 ps 网格 | t = 0 时 `clk` 已高、`vin` 为 0.7 V：不算触发，三个输出保持初态，经第一次下降穿越（2.333 ns）直到第一次采样（5.309 ns）；之后 0.62 V 样本（`coarse` 高）在 `clk` 为低时下垂，0.30 V 样本（`coarse` 低） |
| `interrupt`（修正 r1 新加） | trf 200 ps、tau 10 ns、dt 1 ns、taperture 1.5 ns、valid_width 0.5 ns，vth 取缺省，4 ps 网格 | 三次采样时 `clk` 已回到低电平；下一次下垂更新在采样后 55 ps、95 ps 与 195 ps，打断正在进行的 200 ps `vout` 斜坡：前两次同向（0.8 V、0.3 V 样本），第三次反向（0.9 V 样本走到斜坡的 97.5 %）；每次下垂 9.5 % |

15. 台架按标准审核网表约定清单写（`runs/standard-line-20261028/netlist-conventions/LIST.md`，第 3 版，SHA256 `6a6b17cddf813a8e7c7c4be3d47fed3bac5ab63b23fa207e0f49ff9a0f7713af`，只读）：
    - “必须”一档照写：`simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，`tran` 写 `stop`、`maxstep`、`strobeperiod`、`errpreset=moderate`、`strobeoutput=strobeonly`，`save` 列出全部 7 个信号；常值源写 `type=dc dc=…`（建题时漏写 `type=dc`，修正 r1 补上，审核 R01-15），PWL 从 t = 0 起、严格递增、末点覆盖 stop。容差取标准审核给 D1 定的值作起点，这是选值依据，实际误差待 Spectre 校准验证，不是误差保证。修正 r1 按第 4.9 版复查，见文末一节。
    - “不必”一档一律不写；precision 不写进用例网表；“PWL 控制在 20 点以内”一条不执行。
    - Spectre 执行路径在打包时于作业网表末尾追加 `vabenchExecPath options precision="%.17g" src_allbrkpts=yes`（样板 r2.18）；用例网表不写 precision 与 `src_allbrkpts`。checker 不依赖输出行落在哪里：评分行都是 strobe 网格行，穿越在网格行之间的同一段线性边沿上插值得到。
    - 参数端点在实例行上用题面与参考解 `from` 范围的同一写法（`dt=0.2n`、`valid_width=0.5n`、`tau=1u`、`taperture=20p`/`2n`、`trf=10p`/`200p`），生成器断言实例行的值与用例 `params` 相等。建题首轮用 `200p`、`1000n` 写的两个端点用例被 EVAS 02dee32b 在 a 阶段以 `parameter_range` 拒绝，原因是 EVAS 对带比例符号的字面量舍入两次（#289）：`0.2n` 解析成 2.0000000000000003e-10，比 `200p` 大 1 ulp，`1000n` 比 `1u` 大 1 ulp；改成同一写法后通过 a 阶段。Spectre 对带比例符号的字面量是一次舍入（标准审核 FU-01b 已测得，见 `runs/standard-line-20261028/logs/preimages/JUDGMENT-FU1-FU2a-7659d470.md` 第 1.5 节，只读），这两对在 Spectre 上各自是同一个值，#289 修好后 EVAS 也一样（修正 r1 更正原因归属，审核 R01-12）。这条字面量规则是标准审核的测量结论；本题自身仍未仿真，参考解与用例的 Spectre 运行待做。
16. checker（[tests/verify.py](tests/verify.py)）只读波形，不读候选源码或参考解：按记录的穿越、`vin`、`vdd`、`vss` 算出三个输出的期望值；台架义务出错时抛出异常（不判分，不记候选失败），包括参数越界、分辨率、`vss` 不恒定或越界、跨度越界、`clk` 电平与间距、`clk` 转移长于 200 ps（修正 r1，由保存行检查）、触发间隔、穿越或采样时刻离更新时刻不足 50 ps、采样附近 `vin` 或 `vdd` 移动、`valid`/`coarse` 为高时 vdd 变化、采样值离 `vth` 不足 5 mV、控制停在门限。整段没有触发的记录照常评分（修正 r1 去掉了原先的 `no trigger` 台架错误，审核 R01-03）。期望值变化是否开窗用题面写明的 δ = 0.1 mV（修正 r1）。穿越提取与 P0 六题统一。共用文件与首批逐字节相同。
17. 参考解 [solution/circuit.va](solution/circuit.va) 按自然写法、以 Spectre 可解为准：`cross` 预约，`timer(t_sample)` 采样、钳位、判定并置 `valid`，`timer(t_valid_off)` 撤销 `valid`，`timer(0, dt)` 在 `clk` 为低时下垂，三个 `transition(…, 0, trf, trf)` 以 `vss` 为参考输出。没有为任何 EVAS 版本改写。
18. 校准候选见 [tests/calibration](tests/calibration/README.md)：38 个错误、5 个正确或余量候选（含 `alt_following_levels`、`alt_counter_grid`；修正 r1 新加错误候选 `trigger_initial_high`、`droop_after_ramp`）。被拒矩阵另存为 `expected.json`，条目都是待 Spectre 校准的预期。

### 待用户确认（五项都已定，用户 2026-10-29）

下面五项原为“待用户确认”，用户 2026-10-29 已按推荐定：Q1–Q5 依次是待确认清单第 52–56 项，即决定单第 29–33 项。推荐、另一读法与理由的原文保留，r01-fix-r2 只改状态（上文建设决定第 2、3、7、8、9 条同样只改了状态）。

| 编号 | 选择 | 推荐（已写入题面） | 另一读法 |
| --- | --- | --- | --- |
| Q1 | 【已定（用户 2026-10-29，决定单第 29 项）】下垂更新式与目标电平 | 从 t = 0 起的网格 `j·dt`，`clk` 为低的更新时刻乘 `exp(−dt/tau)`，趋向 `vss`（gold 与其历史 Spectre 运行的行为） | 低电平期间连续指数 `dh/dt = −h/tau`（`dt` 不再起作用）；或网格从每个下降沿起算；或趋向地 0 V |
| Q2 | 【已定（用户 2026-10-29，决定单第 30 项）】`valid` 时序 | 恰好从 `c_k` 到 `c_k + valid_width` | 沿用 gold：在 `c_k + valid_width` 之后的第一个下垂更新时刻撤销（脉宽 2.275 ns） |
| Q3 | 【已定（用户 2026-10-29，决定单第 31 项）】采样与下垂、时钟与下垂同刻 | 排除：穿越与采样时刻离更新时刻至少 50 ps | 在合同中规定次序（如先下垂后采样），保留同刻输入 |
| Q4 | 【已定（用户 2026-10-29，决定单第 32 项）】电源轨的合法域 | `vss` 恒定；`vdd` 只在 `valid`、`coarse` 都为低时、离采样时刻 0.5 ns 以上变化 | 允许 `vss` 移动并规定保持值跟随 `vss`；允许 `valid`/`coarse` 为高时 vdd 变化并规定高电平跟随 vdd |
| Q5 | 【已定（用户 2026-10-29，决定单第 33 项）】参数合法域 | 有限闭区间（见建设决定第 2 条），`trf ≤ dt/4`，`taperture ≥ 20 ps`，端点进终评 | 沿用原题的开区间，允许零孔径与零 `trf` |

用户已确认（2026-10-28）：评分起点按 F01 的推荐写法（上文第 11 条）。

### 平局、零边沿、实数比较与零点核对

按标准审核定稿的平局判据（`runs/standard-line-20261028/rules/TIE-RULE.md`，SHA256 `a4cf0e73dfc91af72416bb42d273b9b578f6caa2dc6fa098153751dfd280ffa7`，只读），用 build_cases.py（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/build_cases.py`） 以精确时刻逐例扫描，结果在 build-cases-report.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/build-cases-report.json`）：

- 第 1 种（不同来源的事件精确同刻）：八例都没有（修正 r1 按改后的用例重扫）。第 (ii) 类的两种同刻由合法域排除（Q3）；生成时曾出现 `clk` 下降与 `valid` 结束、`clk` 下降与采样时刻同刻（`clk` 下降不是参考解的事件，属第 (i) 类），也已挪开。
- 第 2 种（事件恰在斜坡终点改写目标）：按每个输出的实际完成时刻与名义终点两种口径扫描，八例都没有。修正 r1 新加的 `interrupt` 有三次被打断的 `vout` 过渡（下一次下垂更新在采样后 0.275、0.475、0.975·trf），改写都在斜坡中途，离实际完成时刻至少 5 ps；其余七例同一输出两次变化至少相隔 1.775·trf。
- 第 4 种（timer 落在时间比较边界）：参考解的三个 timer 都不做时间比较；下垂 timer 读 `clk` 电平，合法域使它离穿越至少 50 ps。不适用。
- 第 5 种（不同来源的两个 timer 只差 1 到 64 ulp，TIE-RULE.md `418d542a…`，2026-10-29 补；修正 r1 核对）：八例中不同 timer 相距不足 50 ps 的只有 `param-endpoints-low` 的 `valid` 结束与下垂更新（6.75 ps、17.25 ps、33.25 ps、49.25 ps），只涉及不同输出，属第 (i) 类，且远大于 64 ulp。不适用。
- 零边沿 `transition()`（样板 r2.18）：已核对。参考解与全部校准候选的 `transition()` 都显式写出非零的 rise/fall（`trf` 或其倍数、`trx = max(trf, 20p)`），台架没有 `transition()`；`zero_outputs` 也显式写 `trf`；`continuous_droop` 用 `transition()` 输出乘一个连续因子，判定不依赖边沿宽度。修正 r1 新加的两个候选同样显式写 `trf`。
- 实数 `==`（样板 r2.18）：已核对。参考解没有实数 `==`、`!=`；钳位比较在恰等于轨时两个分支结果相同；`held > vth` 有 5 mV 余量；`V(clk, vss) < vth` 离穿越至少 50 ps。checker 判断期望值是否改变时，建题时用 1 nV 的差值门限，修正 r1 按 LIST 第 4.9 版第 0.5 节第 20 条改为写进题面的 0.1 mV（审核 R01-02）；判断“高电平期间 vdd 不变”用电平差 0.4 V；穿越提取沿用六题统一规则，按行值与门限精确比较，但用例中没有一行恰在门限上。其余属第 20 条范围的判断见文末一节第 8 条。
- 直流工作点（样板 r2.18；FU-01d 更正了其中 1.5e-12 的说法，审核 R01-13）：已核对。参考解在 `initial_step` 里不读节点。由 vsource 直接驱动的节点在 t = 0 那一行是逐位精确的值；checker 用 t = 0 行取 `vss`，并按 1e-9 V 检查它恒定，这个 1e-9 V 不是为直流误差留的，原因见文末一节第 8 条。
- 第 38 项前提 1（内部信号恰为零）：参考解的 `cross()` 只作用于外部驱动的 `clk`，没有对内部恰为零的信号检出离开零点；`h` 为 0 时下垂仍得 0，不需要事件。引用旧版的“通过”前已核对：穿越都在网格行之间，旧版的零点与门限处理不影响这些通过结论。

### 历史 Spectre 证据

本机 v3 缓存没有本题。v4 缓存 `…/benchmark-vabench-release-v4/reports/first_n_spectre/cache/100/score/` 有两个缓存键，是原 v4:100 gold（SHA256 `2318eaa2…7276`，与 historyref 相同）在同一评分台架上的两次 Spectre 21.1.0.509.isr12 运行（`+preset=ax`，maxstep 0.1 ns），两份台架只差 `save` 列表，公共列逐行相同。复核见 historical-spectre-crosscheck.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/historical-spectre-crosscheck.json`）：

- 192 个 `clk` 为低的更新时刻都下垂一步，比值为 `exp(−0.5/90) = 0.994460`；136 个 `clk` 为高的更新时刻比值为 1，即跳过。这说明 Spectre 上 gold 的下垂就是第 8 条的离散律。
- 九次采样都在上升穿越后 200 ps；`valid` 都在 `c_k + 2 ns` 之后的第一个更新时刻落下，观测脉宽 2.275 ns。按本题合同（恰好 2 ns），18 个 `valid` 探点 gold 都不符合。

这只说明历史 gold 在历史台架上的行为，不是新参考解的 Spectre 结论。该台架的电源轨恒定、`vin` 不越轨，钳位分支未触发。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，参考解、checker 和用例都没有 Spectre 运行证据。`results/reference.json` 与 `results/calibration.json` 尚未生成。

待办：

- Spectre 校准：参考解跑全部私有与公开用例并记录误差余量；`tests/calibration` 的候选逐个过同一 checker，结果与 `expected.json` 比对。
- Spectre 待办（样板第 4a 节）：参考解有两个绝对 timer（`t_sample`、`t_valid_off`，在事件中重新排定，初值 −1 由标志位屏蔽）和一个周期 timer；`transition()` 延迟为 0。被打断的过渡只在修正 r1 新加的 `interrupt` 中出现（下垂更新在采样后 55、95、195 ps 改写 200 ps 的 `vout` 斜坡），记录 Spectre 上改写后的斜坡（LRM 4.5.8）是否在改写时刻后 trf 内到达新值。记录 Spectre 上绝对 timer 重新排定与初值在过去时的行为、采样时刻与相邻更新时刻（最近 50.75 ps）的先后、`valid` 结束与更新时刻 6.75 ps 相邻时两个 timer 的次序。校准候选 `alt_delayed_within_trf` 有待发过渡，另行记录。修正 r1 新加的 `start-high`、`interrupt` 与候选 `trigger_initial_high`、`droop_after_ramp` 同样待 Spectre 跑。
- 参数范围：记录 Spectre 对实例参数恰在 `from` 范围端点时的检查（本题已统一写法，见建设决定第 15 条）。写法不同（如 `200p` 对 `0.2n`）时的取值，标准审核 FU-01b 已测得 Spectre 上是同一个值，不再列为待办（修正 r1，审核 R01-12）。
- 作者校准：复核 2 mV、50 ps、5 mV 与 trf/4 是否需要调整；`continuous_droop` 在缺省参数下只以约两倍 atol 被拒，Spectre 上若接近容差，以 `param-override` 的 145 mV 为主要证据。
- 上面五个原“待用户确认”选择已定（用户 2026-10-29）：Q1–Q5（待确认清单第 52–56 项）为决定单第 29–33 项，都按推荐定，r01-fix-r2 改了状态。
- 难度：规划估计 M，未实测。

开发证据（证据目录 `runs/t3-p1-build-20261029/r01-spec-droop-front-end/`，命令、退出码与结果见 checks.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/checks.json`）；都不作校准、录取或 EVAS 能力验收）：

- Python 合成轨迹（未仿真，建题时）：40 个行为模型 × 6 用例共 240 次判决，事先写下预期的 199 次全部符合；7 项证据有效性控制都判为 checker 错误而非候选失败。见 synthetic-controls.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/synthetic-controls.json`）。修正 r1 后为 42 个模型 × 8 用例共 336 次判决，见文末一节第 9 条。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑（建题时）：参考解 6 个私有用例和公开用例全部通过，只用网格行重判结论不变；起始模型因空模块被拒（`ERROR [rust_lowering]: … no_continuous_linear_ir`）。41 个校准候选在 6 个用例上的 246 次判定都与 `expected.json` 一致，旧版都能运行。端点改写前的一轮（见 `scratch/legacy-evas-superseded-1`）判定逐项相同，只有两个端点用例的波形因参数差一个 ulp 而不同。见 legacy-evas.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/legacy-evas.json`）。修正 r1 改了全部 8 个用例的网表，旧版全部重跑，见文末一节第 9 条。
- EVAS 02dee32b：参考解 7 次运行都在 c 阶段停于 `kernel.unsupported_initial_history`，消息为 `changed initial transition seeds require a calendar independent of held state and histories`。它与样板已知的同码诊断（`initial_step` 读其他模块驱动的节点）触发条件不同，是新现象，交Benchmark 维护方转 EVAS。三个探针（evas_probes.py（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/evas_probes.py`），只在 scratch 改副本）定位：去掉 `initial_step` 里的 −1 初值、或整个去掉 `initial_step`，诊断都不变；只把下垂 timer 从 `timer(0, dt)` 改为 `timer(dt, dt)`（t = 0 那次只把 0 V 乘以因子，行为相同），诊断就变成已知的 `source transition proof budget exhausted: slot 2`（NF-01）。所以触发条件是：带电平判断的周期 timer 在 t = 0 发生一次。参考解按自然写法保留 `timer(0, dt)`，不为 EVAS 改。首轮还在 a 阶段以 `parameter_range` 拒绝两个端点用例（见建设决定第 15 条），改写后通过。起始模型在 a 阶段报 `module requires an analog block or child instances`。见 summary.json（`runs/t3-p1-build-20261029/r01-spec-droop-front-end/evas-02dee32b/summary.json`）。
- Docker：环境镜像与评分镜像各实际构建一次并检查，未执行电路；结果见 checks.json。

## 2026-10-29 修正 r1（r01-fix-r1，审核 R01 r1 的处理）

本节**未仿真**：没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。依据是独立审核 `runs/t3-p1-build-20261029/review-r01-r1/astra-review.json`（sha256 `7793e313…6d108`）与Benchmark 维护方 brief `runs/t3-p1-build-20261029/briefs/r01-fix-r1.md`，以及项目协调方 2026-10-29 的补充：标准审核网表约定清单第 4.9 版（sha256 `f05138e7…eeed5`）第 0.5 节第 20 条“checker 的变化门限”、平局判据第 5 种情形（TIE-RULE.md `418d542a…b108`）、FU2b 判读（`5691c10e…`）。逐条处理、命令与退出码见 disposition.md（`runs/t3-p1-build-20261029/r01-fix-r1/disposition.md`）。本题涉及 R01-02、R01-03、R01-04、R01-05、R01-06、R01-08、R01-12、R01-13、R01-15、R01-16。R01-11（共用入口追加执行路径一行、核对日志接受步数）不在本轮：`tests/v2_runtime.py` 是全部题目逐字节共用的文件，待共用入口一轮（execpath-runtime）统一改。

1. **R01-02 与第 20 条：变化门限 δ。** 题面观察规则改为：只有某个输出的期望值一次变化**超过 0.1 mV** 的时刻之后 `1.25*trf` 内，该输出的点不评分；不超过 0.1 mV 的变化不开窗。checker 用同一个 δ = 1e-4 V，与该输出在这次事件之前的期望值比较（建题时用题面没写的 1 nV）。
   - 推导（按第 4.10 版的算法重算）：被比较的期望值由保存的 `vin`、`vdd`、`vss` 算出，|vin| ≤ 1.8 V，|vss| ≤ 0.2 V，|vdd| ≤ 1.7 V。八份终评网表都写了 options 的 reltol 1e-6、vabstol 1e-8 V 和 tran 的 errpreset=moderate，所以瞬态实际用的 reltol = 1e-6 × moderate 的倍数 1 = 1e-6，vabstol 取 options 的 1e-8 V（errpreset 不改它），不用 Spectre 缺省。`vout` 的期望值按 `vin` 一次、`vss` 两次计，一侧噪声带 (1e-8 + 1e-6×1.8) + 2×(1e-8 + 1e-6×0.2) = 2.23e-6 V，两侧相加 4.46e-6 V，10 倍为 44.6 µV；`valid`、`coarse` 的期望电平按 `vdd` 一次、`vss` 两次计，下界 42.6 µV。合同允许任意小的合法变化（下垂的指数尾、几乎相等的两次采样、h = 0 时的下垂），所以门限写进题面；上界取 atol（2 mV）的一半，1 mV（这一取法交Benchmark 维护方确认）。取 δ = 0.1 mV。八个用例里没有不超过 δ 的名义变化，也没有离 δ 不到一倍的（生成器按精确有理数统计）。
   - 控制（改前、改后 checker 各判一次）：采样使 `vout` 变化 0.05 mV、恰为 0.1 mV、刚超过的 0.101 mV、0.2 mV 与审核复现的 0.5 nV，各配干净输出、trf 内 10 mV 瞬态、窗后 10 mV 误差；`valid` 以最小合法跨度 0.8 V 变化，配同样三种输出。0.05 mV 与 0.1 mV 的窗内瞬态由改前通过变为改后被拒（这两种变化按新题面不开窗），其余判决不变；0.101 mV 的窗内瞬态改后照常通过，说明刚超过 δ 的合法变化开窗。
2. **R01-03：** checker 去掉“no trigger”台架错误，整段没有触发的记录照常评分（三个输出应保持初态）。控制：`clk` 恒低、恒高、先高再下降一次（审核复现，下降离最近更新 109 ps）三种记录，正确输出由改前报错变为改后通过；把 t = 0 的高电平当触发的轨迹在后两种记录上由改前报错变为改后被拒。终评由 `start-high` 覆盖（第 3 条）。
3. **R01-05：** 新终评用例 `start-high`（t = 0 时 `clk` 已高、`vin` 0.7 V，第一次下降穿越 2.333 ns，第一次触发 5.109 ns，此前三个输出保持初态并全部评分），新错误候选 `trigger_initial_high`（只在 t = 0 时 `clk` 高于门限时把它当作一次触发、在 taperture 采样）与同名合成控制：只在 `start-high` 被拒，其余七例与参考解相同。
4. **R01-04 与 R01-08：**
   - 新终评用例 `interrupt`（trf 200 ps、dt 1 ns、tau 10 ns、taperture 1.5 ns、valid_width 0.5 ns，4 ps 网格）：三次采样时 `clk` 已低，下一次下垂更新在采样后 55、95、195 ps 改写正在进行的 `vout` 斜坡（前两次同向，第三次反向，在斜坡的 97.5 % 处），改写离斜坡终点至少 5 ps。按最终事件清单只有这一例打断输出过渡（其余七例同一输出两次变化至少相隔 1.775·trf）。新错误候选 `droop_after_ramp`（斜坡进行中到来的新目标等斜坡结束 1 ps 后才开始；1 ps 让改写离开斜坡终点，不落在平局判据第 2 种情形上）与合成控制 `wait-old-ramp`：只在 `interrupt` 被拒（合成控制在 5.252 ns，即第一次更新后 1.26·trf 的评分行，以 35.8 mV 拒绝），其余七例与参考解相同；“完成原斜率”与“从当前值重走满 trf”两种正确读法的合成控制都通过。`expected.json` 的条件按最终事件清单重写，“至少 59 ps”改为实际的 50.75 ps（`param-endpoints-low`；缺省参数 53 ps，`interrupt` 55 ps），`valid` 结束离更新时刻最近 6.75 ps。
   - R01-08：原 10 ps 网格上下垂更新落在行上，1.25·trf = 50 ps 又是网格步的整数倍，每次下垂变化的评分起点都落在保存行上（审核复现：13.55 ns 那一行前后 1 ulp 判决翻转）。F01 的观察起点公式不改，改网格与相位：缺省参数的四例（`base`、`rails-reference`、`phase-grid`、`start-high`）改为 8 ps 网格，下垂更新落在行上或行后 4 ps（第一个评分行 1.3·trf 或 1.4·trf），`clk` 穿越在行后 5 ps（采样与 `valid` 结束后第一个评分行 1.275·trf）；`param-override` 2 ps 网格、行后 0.5 ps（1.255·trf）；`param-endpoints-low` 2 ps 网格、行后 1.25 ps（1.275·trf）；`interrupt` 4 ps 网格、行后 1 ps（1.255·trf）；`param-endpoints-high` 本来就没有这样的行。生成器按最终保存行与超过 δ 的变化断言：没有一行恰在任何一次变化的评分起点上，每个采样时刻与 `valid` 结束在 (1.25·trf, 1.3·trf) 内有评分行。
   - 周期更新的迟到对照行（R01-08 建议的第二部分，修正 r1 第二遍）：1.3·trf 到达的迟到负例在一次已稳定的下垂台阶 s 之后第一个评分行 x·trf 处差 s·(1 − x/1.3)。`param-override`（每步 18 %，最大台阶 154 mV）与 `interrupt`（每步 9.5 %，86 mV）的下垂更新落在网格行上，其后第一个评分行在 1.26·trf：`param-override` 有 11 个、`interrupt` 有 3 个台阶在这一行超出 2 mV（2.1–4.7 mV），生成器断言每例至少三个。其余六例最大的下垂台阶（缺省参数 5.0 mV，`param-endpoints-low` 16.8 mV，`param-endpoints-high` 4.5 mV）乘 1 − 1.25/1.3 都小于 0.7 mV，窗口内任何一行都看不出迟到，列为例外。合成控制 `droop-late-1p3trf`（只有下垂台阶在 1.3·trf 到达）只在这两例被拒，`droop-late-1p2trf` 八例都通过。
   - 边界控制：审核复现在原 10 ps 网格上前后 1 ulp 的翻转照旧存在（那是原台架的问题）；改后 8 ps 网格上离评分起点最近的两行（13.544 ns 不评分、13.552 ns 评分）前后各移 1 ulp，判决都不变。
5. **R01-06：** checker 检查 `clk` 的电平转移：`V(clk) − V(vss)` 离 0 V 与 0.9 V 都超过 1 mV 的保存行连成的一段，首尾时刻之差是转移长度的下界，超过 200 ps 判台架违例（不判分）；它不会把 200 ps 以内的合法边沿判错，只会漏掉比 200 ps 长不到两个网格步的违例。题面合法域一句写明“转移”指 `V(clk) − V(vss)` 离两个电平都超过 1 mV 的那段时间（1 mV 是第 20 条意义上的门限，按第 4.10 版的算法：`clk` 与 `vss` 两个波形量相加，下界 10×[(1e-8 + 1e-6×1.1) + (1e-8 + 1e-6×0.2)] = 13.2 µV；上界取 0.9 V 摆幅的一半 0.45 V）。控制：150 ps、恰 200 ps（拐角不在行上与在行上）通过；260 ps 与 1 ns（审核复现）改后报台架违例，改前照常判分。终评（最长 200 ps，`rails-reference`）与旧版波形都不触发这条检查。
6. **余量（样板 r3、U15 fix-r5）：** 下限按样本偏离 1 mV、时刻偏差 1 fs 推：`clk − vss` 的两个节点各偏 1 mV，按边沿斜率折成时间再加 1 fs，一个穿越最多移动 0.112 ps（50 ps 边沿）、0.223 ps（100 ps）、0.401 ps（180 ps）、0.445 ps（200 ps）、0.201 ps（90 ps），间距按两个穿越算；上限按测试目的，承担覆盖的用例离合同下界不超过一个网格步：`param-endpoints-low` 的 1.002 ns 时钟高电平（下界 1 ns，2 ps 网格）与离下垂更新 50.75 ps 的采样（下界 50 ps），`base` 离更新 53 ps 的触发（8 ps 网格）。触发间隔与离 vdd 变化 0.5 ns 两条义务只用来保证事件互不干扰，按测试目的不设一个网格步的上限，已核对。生成器断言全部上下限（build_cases_fix.py（`runs/t3-p1-build-20261029/r01-fix-r1/scripts/c067/build_cases_fix.py`），`--variant orig --check` 复现改前字节）。
7. **R01-12、R01-13、R01-15、R01-16：** 端点舍入的原因归属 EVAS 两次舍入（#289）、Spectre 一次舍入（FU-01b），见上文第 15 条；直流工作点的说法按 FU-01d 改写，见上文平局与零点核对；全部常值源写 `type=dc dc=…`，私有八例、公开用例与 `visible_test.scs` 同步；校准 README 开头写明未仿真，旧版段落带完整标签。
8. **checker 中判“变了没有”“是否为零”“是否相等”的地方**（第 20 条，逐处清单见 disposition）：三个输出的期望值变化、统计量 `clamped` 与 `droops` 用 δ；`clk` 的电平与转移用题面写明的 1 mV；`vin` 的平稳用题面写明的 0.25 mV，采样值离 vth 用题面写明的 5 mV。下面几处属第 20 条范围、不在 R01 发现范围内，没有改，交Benchmark 维护方：`vss` 恒定按 1e-9 V 检查（vsource 直接驱动，各行逐位相同，这个宽限不出现在题面）；“采样前后 0.5 ns 内 vdd 不变”与“`valid` 或 `coarse` 为高时 vdd 不变”按 0.25 mV 检查（题面只写“不变”）；穿越规则里行值与门限的精确比较（六题统一规则，用例中没有一行恰在门限上）。其中 `vss` 恒定的 1e-9 V 与穿越规则的精确比较已核对（扫描 B，2026-10-29，报告（`runs/t3-spectre-wave2-20261029/scan/round-b/report.md`）第 4 节末“第 20 条 δ 的核对”，sha256 `879b3a39…7fed`）：`vss` 是 dc 源，行值逐位不变，这一检查只决定台架错误，不会误拒 DUT；精确比较作用在 vsource 驱动的 `clk − vss` 上，只决定恰在门限的行与台架错误，不改判定。“vdd 不变”的 0.25 mV 不在那次核对的四处之内，状态不变。范围检查里的 1e-9 V 等余量是不等式的数值余量，不是相等判断。
9. **样板 r2.29 的核对。**
   - 零边沿 `transition()`：参考解、全部校准候选（含两个历史原件和新加的两个）与台架里没有省略或写 0 的 rise/fall。按 stop 分档的 w 与“离缺省边沿开始最近的评分时刻”因此都不适用：

     | 用例 | stop | w | 缺省边沿 | 最近的评分时刻 |
     | --- | --- | --- | --- | --- |
     | `base` | 169.8 ns | 1 ns | 无 | 不适用 |
     | `rails-reference` | 129.8 ns | 1 ns | 无 | 不适用 |
     | `phase-grid` | 117.8 ns | 1 ns | 无 | 不适用 |
     | `param-override` | 64.9 ns | 1 ns | 无 | 不适用 |
     | `param-endpoints-low` | 12.45 ns | 1 ps | 无 | 不适用 |
     | `param-endpoints-high` | 71.92 ns | 1 ns | 无 | 不适用 |
     | `start-high` | 31.8 ns | 1 ps | 无 | 不适用 |
     | `interrupt` | 27.9 ns | 1 ps | 无 | 不适用 |
   - 最后一行与 stop：checker 取最后一行，不按“时间等于 stop”找行；完整性检查的容差是 stop 的 1e-6，不是从实测偏移推出的。stop 在网格上、不在下垂更新时刻上，最后一次更新离 stop 至少 4.5·trf（`interrupt` 0.9 ns；`param-endpoints-low` 50 ps，即 5·trf），其后都有评分行，最后一次 `valid` 结束离 stop 至少 2·trf（生成器断言），没有要在 stop 处读的值。已核对。
   - 网表第 0.5 节：八份终评网表与公开网表按第 4.9 版的条目扫描（扫描时清单文件已是第 4.10 版 `e99f4ddb…`，第 4.10 版只改第 7、20 条、新增第 21 条，扫描的条目不变）（netlist-scan.json（`runs/t3-p1-build-20261029/r01-fix-r1/netlist-scan.json`），含 `list41_scan.py` 的 `check()`）：没有指数加比例符号，比例符号只有 `n`、`p`、`u`，后面不接单位；容差都非零；没有 strobetimes；每条语句一行，LF；用例网表不写 precision 与 `src_allbrkpts`；errpreset=moderate；常值源都写 `type=dc`。超过 20 点的 PWL（`phase-grid` 的 `Vclk` 最多 42 点）靠执行路径的 `src_allbrkpts=yes`，checker 只读 strobe 行，不依赖它。已核对。
   - 平局第 5 种情形：见上文平局与零点核对，不适用。FU2b：没有 `idt`、pulse 源或 `$rdist_normal`，不适用。
10. **判决与证据。** 合成控制 44 个模型 × 8 个用例共 352 次判决，改前与改后 checker 对每个模型的判决都相同，事先写下预期的 231 次全部相符；7 项证据有效性控制都报错；判决变化只出现在上面的新控制里（9 处，synthetic-controls.json（`runs/t3-p1-build-20261029/r01-fix-r1/c067/synthetic-controls.json`））。`expected.json` 加 `start-high`、`interrupt` 两列与 `trigger_initial_high`、`droop_after_ramp` 两行，原有条目不变，`checker_failure` 写明 δ，条件按改后的用例改写。旧版：全部八个用例的网表都改了（`type=dc`），参考解、起始模型与 43 个候选全部重跑，共 354 次（`param-override`、`interrupt` 改网格后又重跑一遍，前一遍移到证据卷的 `superseded-r08b`）：参考解在八个私有用例与公开用例都通过，起始模型报 `no_continuous_linear_ir`；候选 344 个有预期的条目全部一致，只用网格行重判计数相同（legacy-evas.json（`runs/t3-p1-build-20261029/r01-fix-r1/c067/legacy-evas.json`）、legacy-vs-expected.json（`runs/t3-p1-build-20261029/r01-fix-r1/c067/legacy-vs-expected.json`））。建题时的 254 次旧版运行只用改后 checker 重判，判决无一变化（legacy-regrade.json（`runs/t3-p1-build-20261029/r01-fix-r1/c067/legacy-regrade.json`））。引用这些通过之前已核对零点掩盖：参考解与候选只对外部驱动的 `clk` 用 `cross()`，穿越都在网格行之间。
11. **Benchmark 维护方补充（2026-10-29T05:42Z，`runs/t3-p1-build-20261029/briefs/r01-fix-r1.steer-list410.md`，sha256 `94875695…`）的复核**（未仿真；计算与扫描见 steer410-checks.json（`runs/t3-p1-build-20261029/r01-fix-r1/steer410-checks.json`））。依据：清单第 4.10 版（`e99f4ddb…`）、SL-DEC-20261029-05 的补充（`JUDGMENT-W2-S7S12-G400-L0A.md` 第 5 节，`2b6b7d8e…`）、样板 r2.35（`d090ca15…`）。
   - 第 20 条：δ 的下界（`vout` 44.6 µV，`valid`、`coarse` 42.6 µV）与电平带的下界（13.2 µV）已按第 4.10 版的算法重算（上文第 1、5 条），都在上下界之内，结论不变。题面原有的门限：`vin` 平稳 0.25 mV（下界 10×2×(1e-8 + 1e-6×1.8) = 36.2 µV）、采样值离 vth 5 mV（下界 10×[(1e-8 + 1e-6×1.8) + 2×(1e-8 + 1e-6×0.2)] = 22.3 µV）也满足。没写进题面的两处（上文第 8 条）：`vss` 恒定的 1e-9 V 低于按同一算法的下界 10×2×(1e-8 + 1e-6×0.2) = 4.2 µV；`vdd` 不变的 0.25 mV 高于下界 34.2 µV。`vss` 由 type=dc 源直接驱动，Spectre 上逐位精确（FU-01d），现有用例不会误报；不在 R01 发现内，没有改，交Benchmark 维护方；`vss` 恒定的 1e-9 V 已核对（扫描 B，2026-10-29，见上文第 8 条）。
   - 第 7 条：checker 取最后一行，不按 time == stop 找；完整性容差是 stop 的 1e-6（本题最小的 stop 12.45 ns 时为 1.245e-14 s），远大于实测偏移上界 3.0e-17 s，也不是从偏移推出的；没有要在 stop 附近读的值。不变。
   - 第 21 条：本题 checker 与本轮工具都不从 spectre.log 取 `$strobe`、`$display`、`$fwrite` 记录：无。
   - cross 返回根：评分依赖 `clk` 上升穿越（触发）的次数。`cross()` 都没写 time_tol（Spectre 缺省 1 s，大于 stop）与 expr_tol；按最宽读法 expr_tol = 1e-9 + 1e-6 × max|expr|，最大 0.70 µV。按精确的 PWL 源逐例求根：`V(clk, vss) − vth` 93 个根，相邻两根之间 |expr| 的最大值最小为 0.2 V（vth 为 0.2 V 与 0.7 V 的两个端点用例），是 expr_tol 的 2.9e5 倍；候选的 `− 0.45`、缺省 0.57、对地的 `V(clk) − vth` 最小为 0.45 V、0.2 V、0.2 V。都必须报两次，计数可以评分；没有根落在 PWL 折点上。合同上也成立：合法的 `clk` 在 `V(vss)` 与 `V(vss) + 0.9 V` 之间切换，每次转移不长于 200 ps，相邻穿越至少相隔 1 ns，所以两次穿越之间离 vth 至少 0.199 V（vth 在 0.2–0.7 V），checker 也按这两条检查台架。
   - 一次性 timer（FU-11b、FU-11c）：参考解的 `timer(t_sample)`、`timer(t_valid_off)` 是一次性 timer，事件体只看标志位 `pending`、`valid_on`，不拿 `$abstime` 与设定时刻比较；若并进 T 前更早的事件或断点，采样读到的 `vin`、`vdd` 在采样前后 trf/4 与 0.5 ns 内不变，`valid` 的结束只早合并距离（stop 50 ns 时约 3.75e-17 s），判决不变。候选里 `$abstime` 的比较有 5 处，都不是与 timer 的设定时刻比较：`droop_after_ramp`（本轮新写）在采样 timer 与下垂 timer 的事件体里比较 `$abstime < t_ramp_end`（当前斜坡的终点），用例中最近差 5 ps（`interrupt` 第三次采样后 195 ps 的更新对 200 ps 的终点；其余用例同一输出相邻两次变化至少相隔 1.775·trf，离终点至少 0.775·trf）；`valid_on_droop_grid`、`original_v4_100_gold`、`historical_v4_1100_buggy` 在下垂周期 timer 里比较 `$abstime` 与 `valid` 的结束时刻，最近差 6.75 ps（`param-endpoints-low`）。这些间隔都远大于合并距离：无。
   - transition 的 td（U15）：td 都是常数（0；`alt_delayed_within_trf` 为参数式 0.2·trf），没有运行中改 td 的写法：无。

## 2026-10-29 题面门限与总时限（r01-fix-r3）

本节**未仿真**：没有运行 Spectre、EVAS 或模型；下文的控制是 Python 合成波形，只检验 checker 怎么判。本轮改了题面 Rails 一段的一句、本页和 `task.toml` 的 `[verifier] timeout_sec`；网表、checker、参考解、校准件与共用文件都没改。依据：网表约定清单第 4.17 版（sha256 `2be11e0110b2e9eba364adfafc52b295a5952fa01dd3edcccd27118986db084e`）第 0.5 节第 20 条（第 71 行，“checker 的变化门限”）；建题样板 r2.38 第 4c 节（用例时限与题目总时限）；项目协调方 2026-10-29 同意本轮做这两件事。上文修正 r1 一节第 8、11 条把“vdd 不变”按 0.25 mV 检查列为题面没写的门限，交 Benchmark 维护方定；本节把它写进题面，那两条原文不改。

1. **题面写明“vdd 不变”的门限 δ = 0.25 mV。**
   - 改前（第 18 行）：“`vdd` may change during a run, but only while `valid` and `coarse` are both low, and it stays constant within 0.5 ns of every sample instant.”
   - 改后：“`vdd` may change during a run, but only while `valid` and `coarse` are both low, and not within 0.5 ns of a sample instant. A movement of less than 0.25 mV does not count as a change: within 0.5 ns of every sample instant, `vdd` stays less than 0.25 mV away from its value 0.5 ns before that instant, and while `valid` or `coarse` is high, it stays less than 0.25 mV away from its value at the latest sample instant.” 这一段的其余句子与题面其余部分都不动。
   - 理由：checker 在两处按 0.25 mV（常数 `STILL`）判 vdd 变了没有，题面原来只写“不变”。清单第 20 条要求：被比较的量来自仿真波形时，判“变了没有”用写进题面的门限 δ，不用题面没写的门限。这两处都是台架义务检查，只决定台架是否守约，不判候选；写进题面是为了合同与 checker 一致。
2. **checker 实际怎么判（照实写进题面，checker 不改）。** 两处都用 `Wave.span(t0, t1, 'vdd')`（`tests/verify.py` 第 91–96 行）：窗口 [t0, t1] 内的各保存行、以及 t1 处按相邻两行线性插值的值，离 t0 处插值的值最远有多远；不小于 0.25 mV 时抛出 ValueError，共用运行入口把它记作 checker_error（台架没有守约，不判分，也不记作候选失败）。
   - 第 169 行：每个采样时刻 c_k 取窗口 [c_k − 0.5 ns, c_k + 0.5 ns]，起点值是 c_k − 0.5 ns 处的值（报错 “vdd changes within 0.5 ns of a sample instant”）。
   - 第 274–280 行：`valid`、`coarse` 的期望值每在一个采样时刻变高或再次置高，就从这一时刻到该输出下一次期望值事件为止取一个窗口，起点值是这一采样时刻的值（报错 “vdd changes while valid or coarse is high”）。`coarse` 连续为高时在每个采样时刻分段，所以起点总是最近一次采样时刻。
   - 题面第 43 行写明输入值按保存点之间的线性插值取；分段线性的波形在窗口里离起点最远的点总落在保存点或窗口端点上，所以按改后的题面判与 checker 的计算相同。
   - `vin` 一条（第 40 行，“moves by less than 0.25 mV”）用的是同一个函数和同一个 0.25 mV，窗口是 c_k ± trf/4，起点取 c_k − trf/4。它原来就写在题面里，本轮只核对上下界：下界 10 × 2 × (1e-8 + 1e-6 × 1.8) = 36.2 µV（|vin| 最大 1.8 V），上界 1 mV（取法同下文第 3 条），0.25 mV 在两者之间。
3. **δ 的上下界（清单第 20 条）。**
   - 下界：被比较的是同一节点 `vdd` 的两个值（窗口内某一点与起点），按“两个量相比时两边相加”，取 10 × [(vabstol + reltol × |v|max) + (vabstol + reltol × |v|max)]。八个私有用例、公开用例与 `visible_test.scs` 的 options 都是 `reltol=1e-6 vabstol=1e-8`，tran 都写 `errpreset=moderate`（倍数 1），所以瞬态的 reltol = 1e-6 × 1 = 1e-6，vabstol = 1e-8 V；各网表相同，最宽的也是这一组。|v|max 取题面合法域里 V(vdd) 的最大值：V(vss) 最高 0.2 V，V(vdd) − V(vss) 最高 1.5 V，合计 1.7 V。下界 = 10 × 2 × (1e-8 V + 1e-6 × 1.7 V) = 3.42e-5 V = 34.2 µV。
   - 上界：合同允许 vdd 在 `valid`、`coarse` 都为低、离采样时刻 0.5 ns 以上时任意小地变化，没有最小的合法名义变化。按清单第 20 条与样板第 3 节变化门限一条（项目协调方 2026-10-29 对 R01 三题的取法），这时要检测的最小变化取 checker 本来要分辨的误差限。题面的误差限是 2 mV（第 43 行 “At each scored point the error of every output is at most 2 mV”，八个用例的 atol 都是 0.002），上界 = 2 mV / 2 = 1 mV。
   - δ = 0.25 mV 在 [34.2 µV, 1 mV] 之内：δ 是下界的 7.3 倍，上界是 δ 的 4 倍。所以照现状写 δ，不改 checker。这个门限的作用：高电平期间 vdd 移动不到 0.25 mV 时，按采样时刻锁存与跟随 V(vdd) 两种写法的 `valid`、`coarse` 相差不到 0.25 mV；采样前后 0.5 ns 内移动不到 0.25 mV 时，在 c_k 稍前或稍后读轨电压，钳位值与高电平也相差不到 0.25 mV；都远小于 2 mV 的误差限。
   - 例外（清单第 20 条的第 4.16、4.17 版例外）：`vdd` 由独立理想源（vsource，PWL 或 dc）直接驱动，这两处又是台架义务检查，按 v4.17 也可以改为按激励定义精确判（PWL 点的值与时刻、dc 值，不读保存行，即该条的做法甲），不用 δ。本轮不改 checker，照现状写 δ。
4. **控制（未仿真）。** Python 合成波形，用题包 checker 的副本判：缺省参数、8 ps 网格、一次采样（采样时刻 2.405 ns），输出取合同值，题包内的文件在运行前后不变。
   - vdd 在采样前 0.3 ns 移动 0.24 mV：照常判分并通过；移动 0.26 mV：报 “vdd changes within 0.5 ns of a sample instant”。
   - `valid` 为高时（采样后 1 ns）、只有 `coarse` 为高时（采样后 3 ns）移动 0.24 mV：通过；移动 0.26 mV：报 “vdd changes while valid or coarse is high”。`valid`、`coarse` 改为跟随 V(vdd) 的输出在 0.24 mV 时也通过（最大误差 0.24 mV）。
   - `valid` 为高时先升 0.2 mV、再降 0.4 mV（离起点最远 0.2 mV，峰峰 0.4 mV）：通过，说明按离起点的距离判，与改后的题面一致。
   - 合法域端点 V(vss) = 0.2 V、V(vdd) = 1.7 V，`valid` 为高时移动 −0.24 mV 通过、−0.26 mV 报错：门限是绝对值，不随电平缩放。
   - `valid`、`coarse` 都为低、离采样时刻 0.5 ns 以上的 −100 mV 变化（采样前 1 ns；`valid` 结束后、`coarse` 为低时各一例）：照常判分并通过。
   - 恰为 0.25 mV 的十进制台阶在 binary64 下差值是 2.4999999999999997e-4 V，判为通过；结果取决于舍入，只作平局诊断，不写预期。
5. **现有用例（按激励定义核对，未仿真）。** 八个私有用例里只有 `base`（两段）、`rails-reference`（一段）与 `param-override`（两段）改变 vdd，其余五例的 vdd 是常数；公开用例与 `visible_test.scs` 同 `base`。按 PWL 点精确求出采样时刻与 `valid`、`coarse` 的高电平段：vdd 的每段变化离最近的采样窗口（采样时刻 ± 0.5 ns）至少 0.4 ns（`param-override`；`base` 4.095 ns，`rails-reference` 8.247 ns），离 `valid`、`coarse` 的高电平段至少 0.9 ns（`param-override`；`base` 2.595 ns，`rails-reference` 6.747 ns）。这些窗口里 vdd 都停在平台上，所以 δ 对现有用例的判决没有作用。
6. **总时限（样板 r2.38 第 4c 节）。** `[verifier] timeout_sec` 由 600 改为 1080，`task.toml` 别的字节不动。私有用例 8 个，都没写 `timeout_s`，按共用运行入口的缺省各 120 s，和为 960 s；加 max(10 % 即 96 s, 60 s) = 96 s，得 1056 s；向上取整到整分钟为 1080 s。理由（第 4c 节）：每个用例都可以合法地跑满自己的时限，总时限小于它们的和，就会截掉按单用例规则没有超时的提交。用例时限不变，判决与期望都不变。
7. **用例时限：待交回。** 第 4c 节要求用例时限不小于参考解与正确候选在已交回 Spectre 作业里实测最长用时的 2 倍（向上取整到整分钟）。本题在 P1PC 包里的作业截至本轮都还没有交回，这一条待交回后按实测复核；用例时限照旧取缺省 120 s。打包时按 Verilog-A 模块数与步数的估计，本题参考解与应接受的候选都是一个模块，每个作业最长约 27.5 s，2 倍向上取整为 1 分钟，不超过 120 s；这只作参考，不代替实测。
8. **已发出的 Spectre 作业照样作数。** 本轮没有改网表、checker、参考解与校准件，已上传的 P1PC 八个包（`spectre-P1PC-must-01-v1`、`spectre-P1PC-rec-01-v1` 至 `spectre-P1PC-rec-06-v1`、`spectre-P1PC-opt-01-v1`）照样作数，不需要新作业：作业网表都由未改的用例网表得来（参考解与候选的作业是用例网表加执行路径一行，缺省容差对照另去掉容差一行与 `errpreset`），交回后用未改的 checker 判；包里也没有题面与 `task.toml`。本轮逐个核对了八个包的 952 个作业（本题 362 个）：作业记录里的用例文件、用例网表、checker 与 contract 的 sha256 都与现行题包相同，作业网表也都按上面的规则由现行用例网表得到。作业自己的时限按打包时的规则定，与题目总时限分开（第 4c 节）。
9. **结构与 Docker（未执行电路）。** `scripts/benchmark_workbench.py --check --package` 对本题通过，题包里没有 `__pycache__`；与本轮开工时的文件清单相比，只有题面、本页与 `task.toml` 三个文件不同。题面改后，环境镜像与评分镜像各实际构建一次并检查，7 项都通过：评分镜像的 `/app` 为空、缺产物时被拒、环境镜像的 `/app` 等于 starter、镜像里没有 `tests/` 与 `solution/`、参考解安装一致、没有后端时公开检查退出 2、独立验证器记作 infrastructure_error。两个镜像的构建目录是题包的 `environment/` 与 `tests/`，都不含题面、本页与 `task.toml`，这两个目录本轮也没有改动。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 1 处台架义务检查（C067-08，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `f9d898646278fd993d8002c1a0bac75254eab606f5bda968a2f86dce21cbe1b1`，改前 `8f25aed5…`）与本文件。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **C067-08**（evaluate 第 257 行调用 `crossings`，第 65–67 行）：保存行上相邻两行 `clk` 恰为 `V(vss) + vth`（停留）报台架错误 → 按 `clk`、`vss` 的定义判；`crossings()` 去掉这一句，穿越的定义不动。
- 随同改（决定第 1 项，起点）：evaluate 第 254–255 行 t = 0 那一行 `clk` 离 `V(vss) + vth` 不足 50 mV × `REL` 报错 → 按定义判，门槛不变。
- 碰到：改前只当“不算穿越”，现在报台架错误（决定第 2 项）。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`V(clk, vss)` 对 `vth`。`check_stimulus` 放在原来起点检查的位置，在取穿越与判分之前。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 10 个、dc 10 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。受查量是差，另按各节点值先舍成 binary64 的两种比较式算：参考解与题面的 `V(clk) − V(vss)` 与 `vth` 比（逐运算相减），checker 与题面的 `clk` 与门限 `V(vss) + vth` 比（逐运算相加）；任一成立即算在门限上。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”；离 `vth` 不足 0.04999995 V（`START_MARGIN` × `REL`，50 mV × (1 − 1e-6)），报 “starts … closer than …”；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：判分用的穿越仍由原来的 `crossings()` 从保存行取，穿越的定义不动，只去掉其中“相邻两行恰在门限上就抛出异常”一句。保存行恰在门限上（例如模块在同一输入、同一门限上求根时写下的根处行）不再引起台架错误。

### 3. 余量（数值未改）

- 起点：50 mV 乘 `REL`（1 − 1e-6）不变，报错门槛 0.04999995 V。`REL` 是 checker 各个界共用的相对余量；按定义精确比较以后它只是容让，数值未改。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`V(clk, vss)` 对 `vth`）的起点、停留、碰到按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；checker 与题面把门限写成 `V(vss) + vth`，按逐运算舍入（`vss` 的 binary64 加 `vth` 的 binary64）另算一种读法。 |
| 和、差与叠放（v4.18、v4.20） | 适用 | `V(clk, vss)` 按精确值、binary64，以及 `clk`、`vss` 各舍成 binary64 后的两种逐运算写法算（见下一行）。抵消的源 `vss` 也要读得出。叠放 0 处：两个节点各由一个 vsource 直接对地驱动；代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 10 份网表（私有 8、公开 `cases.json` 1、`visible_test.scs` 1）共 40 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 20 个（PWL 10 个、dc 10 个，含差里抵消的 `vss` 源），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 适用 | 两种写法都算：参考解 `cross(V(clk, vss) - vth, +1)` 与题面“`V(clk) - V(vss)`”是 x − a 对 b；checker 与题面“threshold `V(vss) + vth`”是 x 对 a + b。合成控制各做了只在其中一种读法下才在门限上的变体（第 6 小节）。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `sample_hold_droop` 在 `cross(V(clk, vss) - vth, +1)` 上求根，这个差就是受查量 `V(clk, vss)`，已按差处理。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，10 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 10 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前只当“不算穿越”，现在一律报台架错误。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到：instruction.md 第 37 行 “It never rests at the threshold `V(vss) + vth`, and at t = 0 it is at least 50 mV away from it. When `clk` reaches the threshold it always crosses it; it never touches the threshold and returns to the same side.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 45 行 “A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：10 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 125 行）。20 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（20/20）。
- B 候选：扫描列出的 43 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（50 组不同的行，共 2794 行）。改前、改后判决逐个相同，新 checker 不报台架错误（43/43）。
- C 变体（在 `phase-grid` 上改 `clk` 的定义，最后三个另改 `vss`（最后一个换用 `rails-reference`）；每个变体事先写下预期），15/15 符合预期：
  - `clk` 起点按十进制恰在门限上：报 “starts on”
  - `clk` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `clk` 起点离门限 0.0498999 V：报 “closer than”
  - `clk` 起点离门限 0.0500999 V：不报台架错误（照常判分）
  - `clk` 在 3.0149e-08 s 处按十进制停在门限：报 “rests on”
  - `clk` 在 3.0149e-08 s 处只在 binary64 下停在门限：报 “rests on”
  - `clk` 在 3.0149e-08 s 处按十进制碰到门限：报 “touches”
  - `clk` 在 3.0149e-08 s 处只在 binary64 下碰到门限：报 “touches”
  - `clk` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `clk` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `clk` 的源有一个值带单位 `0V`：报 “cannot read”
  - `clk` 不由 vsource 驱动：报 “is not driven”
  - 差里抵消的源 `vss` 有一个值写成参数名：报 “cannot read”
  - `vss` 写成 0.10000000000000002、`clk` 平台 0.55，在 3.0149e-08 s 处只在逐运算读法下停在门限：报 “rests on”
  - 在 `rails-reference` 上（`vss` 0.15）把 `clk` 平台写成 0.59999999999999998，在 6.8629e-08 s 处只在“`clk` 对 `V(vss) + vth`”读法下停在门限：报 “rests on”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P1PC-must-01-v1 18、spectre-P1PC-rec-04-v1 88、spectre-P1PC-rec-05-v1 128、spectre-P1PC-rec-06-v1 128，共 362 个。new 与改前 checker 整份判决 362/362 相同。与原判比 status、passed 与台架错误的有无 362/362 相同，整份判决 sha256 也相同。

### 8. 前面各节的相关句子

- 建模选择第 16 条（第 106 行）“只读波形”、台架错误里的“控制停在门限”与“穿越提取与 P0 六题统一”：checker 现在也读用例网表的 vsource 定义与 tran 行的 stop；起点、停留、碰到改按定义判，碰到报台架错误，`crossings()` 不再因停留抛出异常（穿越时刻的取法不变）。
