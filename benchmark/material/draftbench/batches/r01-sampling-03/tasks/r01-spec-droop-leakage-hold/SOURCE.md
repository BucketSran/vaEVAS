# 来源与建设记录

2026-10-29 按 P1 建题（R01 第一单）新建，阶段 implementation，`pending = ["grading", "runtime"]`。本机没有 Spectre，本题**未仿真**：没有执行 Spectre 电路仿真，也没有运行模型解题；EVAS 结果只作开发证据。本页不表示科学校准、模型试做、题目审核或正式录取。

## 行为依据

### 规划候选身份

| 项目 | 值 |
| --- | --- |
| task_id | `C057-S1`（规划候选，规格建模） |
| unit_id / primary_ref | `C057` / `C057` |
| 主来源 | `src-4ea59e41b115`：[v4 042 公开题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/042-sample-and-hold-with-droop-leakage/public/instruction.md)，SHA256 `ed8bf50e46a20b4ec049494b0e31c04e6e649e3419cc2ee6a89ab5fb838a4285`，与[规划来源表](../../../../planning/history-candidates/sources.json)一致 |
| 规划登记 | [register.json](../../../../planning/history-candidates/register.json) 的 C057-S1：P1，结构估计难度 M，建设成本 L，“补行为边界”；可复用“decay=0.985、1ns泄漏更新及捕获/复位行为”；作者工作“明确泄漏相位、捕获与泄漏同刻顺序和复位释放；区分保持泄漏与C055获取动态”；差异“保持期动态而非获取期动态”。[候选说明](../../../../planning/history-candidates/CANDIDATES.md#c057-s1)同此 |
| Grok 意见 | 采纳方向：采纳时序代表，保留在保持期持续更新这一差异；不将近似采样版本全部单列 |
| P1 队列 | `runs/t3-p1-plan-20261028/p1-queue.json`：C057-S1 没有同源的已建题（`same_source_existing_tasks` 为空），不需要独立性检查 |

本题号 `r01-spec-droop-leakage-hold` 沿用Benchmark 维护方 brief。`source_group` 取新组名 `v4-042`，覆盖 v4 042 与同族的 1042（bugfix）、542（testbench）两种形式；SOURCE_GROUPS 中原无此组，正式组名由Benchmark 维护方登记时确定。

### 讨论记录中的已定事项

本线讨论记录在工作树外：`local/research/benchmark-submission-20261025/README.md`（SHA256 `562a36df97370ff163d45d81200d104b4a228695982a99e5c037375770c97c19`），只读。检索 C057、C067、droop、leak、下垂、漏电、泄漏、sampleandholdwithdroopleakage、sampleholddroopfrontend，相关的只有以下三节；第 179 行的“邻点泄漏”指数据划分，第 1376 行的“泄漏”属电源题，与本题无关。`runs/t3-p0-pilot-20261027/decision-cards/` 的三张决策卡都不涉及本题；其中“触碰门限”卡的推荐 A 已写进本题合法输入。

- 「R01B · 单级保持误差扩展」（第 688 行起，主集候选，来源 R01-03）：待补“从健康 basic 增加注入/漏电，保留原采集；建题包及独立验收”，依据 [r01-sampling/reference.md](../../../../circuits/r01-sampling/reference.md)。R01B 是扩展与集成任务：起始源码是已有的健康 basic（有限采集、理想保持），要在同一采集行为上加有限注入、漏电和状态继承，作者侧材料是 core 模块（保持时 `dx/dt = (vleak − x)/tau_hold`，连续向 `vleak` 衰减，另有注入）。本题是规格建模：从合同写出整个模型，捕获是边沿瞬时读入，没有有限采集、注入和 `vleak`，泄漏是自由运行网格上的离散乘法更新。两者都涉及“保持漏电”这一现象，但交付责任、起始材料和泄漏律都不同，不是同一职责，本题不占 R01B 的位置；R01B 仍待建。以后两题若共用漏电相关的检查或用例，应登记共享资产。
- 「H08 · 保持下垂与孔径非理想参考」（第 1194 行起，扩展集候选，来源含 sampleandholdwithdroopleakage 与 sampleholddroopfrontend）：待补“优先并入 R01 保持误差的材料；若单独成题须有不同采样/孔径合同”。此后的规划把 C057、C067 定为独立 P1 候选。本题的采样合同与同族已有题的不同见下一节：没有孔径、没有采集窗口，下垂由模型内部自由运行的网格驱动，与采样事件、复位分别更新同一个保持值。
- 「E12 · 单级采集/下垂与全窗口建立判定」（第 918 行起）：是测量类方向，“优先成为 R01 仪器或校准对照”，不是规格建模，与本题不重复。

### 历史原件与改编

[v4 042 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/042-sample-and-hold-with-droop-leakage/public/instruction.md)规定：`sample` 上升穿越且复位为低时捕获 `vin`；复位为低时周期性地把保持值乘以 `decay`；复位为高时保持值清零；`vout` 平滑输出。参数缺省值 `vth = 0.45 V`、`decay = 0.985`、`leak_period = 1 ns`、`tr = 500 ps`，端口顺序 `sample, rst, vin, vout`。本题沿用这些行为、缺省值、模块名和端口顺序。

[v4 042 gold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/042-sample-and-hold-with-droop-leakage/evaluator/solution/leaky_hold.va)（SHA256 `7f3099bd…62dd`）只作实现线索：`timer(0, leak_period)` 从 t = 0 起的固定泄漏网格，捕获事件和泄漏事件里各自读 `rst` 电平、为高则清零。它的公开性质说明写的是“复位在采样或泄漏更新事件时清零”，题面写的却是“复位为高时清零”。参考解另写，没有复制。原 042 公开台架只有三次捕获、一次复位，复位上升在两个泄漏时刻之间（120.125 ns），gold 到 121 ns 才清零。

同族历史形式：
- [v4 1042 坏版](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1042-sample-and-hold-with-droop-leakage-bugfix/public/buggy_bundle/leaky_hold.va)（SHA256 `0d8198c9…08aa`）与 gold 相比有两处实际改动：捕获时存 0 V，`decay` 缺省改为 0.900。
- [v4 542 变异目录](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/542-sample-and-hold-with-droop-leakage-testbench/evaluator/mutation_catalog.json)的五个负例 `neg_001`–`neg_005` 名为“端点”“定时窗”“极性”“复位”“度量”，实际改动逐个核对后都与 1042 坏版相同（同两处改动，另加注释）；`neg_004` 的注释写“少一处初态赋值”，但代码没有少。按实际改动，本题只收一个历史错误候选 `historical_v4_1042_buggy`，不按名字另列。

### 同源关系与职责差异

| 题目或候选 | 来源组 | 职责 | 与本题的关系 |
| --- | --- | --- | --- |
| 首批30 [v2-spec-024](../../../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) | `v4-024` | 时钟上升沿瞬时采样，沿间理想保持，无复位 | 同为边沿捕获；本题另有保持期的离散泄漏网格和异步复位，024 的保持值不变 |
| 第二批草稿 [v2-spec-071](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md)（C055 已并入） | `v4-071` | 采集窗口打开时在全局 tick 上按 `alpha` 逼近输入；关窗理想保持；复位只在 tick 生效 | 都有从 t = 0 起的全局网格。071 的网格驱动获取期动态，只在窗口内更新，保持期不变；本题的网格驱动保持期动态，对任何保持值都更新，捕获是瞬时的。复位约定也不同：071 在 tick 复位，本题在 `rst` 上升时立即复位（原列待用户确认 Q2，已定：用户 2026-10-29，决定单第 26 项） |
| R01 [r01-spec-ideal](../../../r01-sampling-01/tasks/r01-spec-ideal/instruction.md) | `r01-ideal` | 窗口打开时透明跟踪，关窗冻结，复位优先 | 本题不跟踪；`sample` 为高时不跟随 `vin`（候选 `track_while_high` 被拒） |
| R01 [r01-spec-acquisition](../../../r01-sampling-01/tasks/r01-spec-acquisition/instruction.md) | `r01-basic` | 输入相关的连续有限采集，保持冻结 | 机制不同：本题没有采集动态，保持期才有动态 |
| R01 [r01-spec-aperture-delay](../../../r01-sampling-02/tasks/r01-spec-aperture-delay/instruction.md)（C056-S1） | `v4-family-072` | 上升沿预约、孔径时刻读入，理想保持，无复位 | 本题在沿上读入，没有孔径；保持期有泄漏，另有复位 |
| C067-S1 [r01-spec-droop-front-end](../r01-spec-droop-front-end/instruction.md)（同批，本单第二题） | `v4-100` | 孔径采样、轨间钳位、`valid` 与 `coarse`，只在时钟低电平期间按 `exp(−dt/tau)` 下垂 | 同为保持下垂。C067 的下垂受时钟门控、用 `tau` 与 `dt` 定义，并与孔径和钳位耦合；本题的泄漏不受 `sample` 电平门控（候选 `leak_only_sample_low` 被拒），用每步乘数 `decay` 定义，另有复位 |
| R01B（规划，未建） | — | 从健康 basic 增加注入与漏电 | 见上节，职责不同 |
| C061-S1、C068-S1（规划，不在本单） | — | 双轨两级保持；跟踪保持切换与累计下垂监控 | 本单不建。C061 的两级相位传递、C068 的持续跟踪后转入保持与累计下垂资格，都不是本题职责 |
| 原56题 | 各自来源组 | 024、071、`v2-data-sampling-identification` 与采样相关 | 本次只读采样相关题面，未复审全部 56 题；没有题以 v4:042 为来源 |

本题只计 C057-S1 一项，不与上述各题重复计数。

### 外部来源与许可

来源声明分三类（完整清单见 sources.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/sources.json`））：

1. 新写的实现：参考解、checker（`tests/verify.py`，公开副本相同）、用例与公开台架（由证据目录的 build_cases.py（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/build_cases.py`） 生成）、`tests/calibration/` 三件（23 个错误候选由参考解经检查过的文本替换得到，另加作者写的 `alt_counter_grid` 等正确候选）、题面与本页。共用的 Harbor 运行文件与首批模板逐字节相同，不是本题新写的。
2. 从仓库内历史资产原样读取的对照：校准候选 `original_v4_042_gold`、`historical_v4_1042_buggy` 由 `mutants.py` 在仓库内运行时从 `benchmark/material/historyref` 按原字节读取，题包不存其文本；历史 Spectre 运行只读，见下文。
3. 外部许可代码：没有复制任何外部代码。

| 来源 | 版本 | 许可 | 用途 |
| --- | --- | --- | --- |
| [Verilog-AMS LRM](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（Accellera） | 2.4.0，2014-05-30；PDF SHA256 `621b2a1a3751e7685600f180fe8f362766fe13e952023ded3d7ae48314337c03`，与 U15-S1、C056-S1 核验的文件相同 | 标准文本，版权所有 | 按 5.10.3.1 `cross()`、5.10.3.3 `timer()`（周期 timer 从起始时刻起，事件点在设定时刻或稍后）、4.5.8 `transition()`（零延迟被打断时的补全斜率）、5.10.2 `initial_step` 写参考解和校准候选。未复制文字 |
| [ADI MT-090](https://www.analog.com/media/en/training-seminars/tutorials/MT-090.pdf)，Walt Kester，“Sample-and-Hold Amplifiers” | Rev.0 10/08，版权 2009；2026-10-28 取得的 PDF SHA256 `fce0494588ad54cf7e286b1f3f21dd15c034306ef711a477b0b3a3c46ffdda96` | Analog Devices 版权教程 | 只引用工程定义：保持期间漏电流流入或流出保持电容，使保持电压逐渐变化，称为下垂，以 V/µs 表示。它说明保持期动态的工程背景，不是本题离散泄漏律的出处。未复制文字或图 |
| [Arcadia-1/behavioral-veriloga-eval](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd) | 提交 `7b5616dc52195ec275ec6d21c71d7763613702cd` | 公开仓库，顶层未见 LICENSE | 只用于记忆污染核对：其 `benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/042-…/evaluator/solution/leaky_hold.va` 的 git blob 为 `7128db1d…6f1883`，与本仓库 historyref 副本相同。未复制代码 |

离散泄漏律的工程读法（作者说明，不是来源原文）：保持电容 `C_h` 经一个由自由运行时钟切换的寄生电容 `C_p` 放电时，每个时钟周期电荷均分一次，保持电压乘以 `C_h/(C_h + C_p)`，下垂发生在时钟沿上，与采样时刻无关。本题的 `decay` 与 `leak_period` 按这一读法理解。

记忆污染风险：中到高。公开 v4:042 gold 与本题的模块名、端口、参数、泄漏网格（`timer(0, leak_period)`）和捕获规则相同，只在复位上不同：它在泄漏时刻和 `sample` 上升时读取 `rst`。原样提交时，它在有 `rst` 上升的五个用例被拒，在 `phase-grid` 通过（旧版开发证据，与预期一致）。评测时应考虑模型可能见过原题；本题的合法域、复位约定和用例是新写的。

## 建模选择

### 建设决定

1. 模块名 `leaky_hold` 与端口顺序 `sample, rst, vin, vout` 沿用 v4 042。理由：这是电路功能名，不是历史 gold 的 `_ref` 命名；接口复用属于规划的“可复用”。
2. 参数与合法域：`vth` 0.1–0.8 V，`decay` 0.5–1，`leak_period` 0.5–10 ns，`tr` 10 ps–1 ns 且不大于 `leak_period/2`。原题只写 `decay` 在 (0, 1]、其余为正。理由：终评要覆盖参数端点，开区间没有可测的端点；`tr ≤ leak_period/2` 保证每次泄漏更新在下一次之前到达并留下评分行，否则泄漏段全部落在不评分窗里。`decay = 1` 保留为合法值（理想保持），它是连续化写法 `ln(decay)` 的奇点，值得测。这是缩域，原列待用户确认 Q4（待确认清单第 51 项），已定（用户 2026-10-29，决定单第 28 项）。
3. 【已定（用户 2026-10-29，决定单第 25 项）；原标“待用户确认 Q1”，即待确认清单第 48 项】泄漏相位：泄漏时刻为 `k·leak_period`（k = 1, 2, …），从 t = 0 起，由模型自己产生，捕获与复位都不增加、跳过或移动它。理由：v4 042 gold 用 `timer(0, leak_period)`，历史 Spectre 运行逐个确认了 121 个泄漏台阶都起于整数纳秒（见下文）；规划把“1 ns 泄漏更新”列为可复用；作者的开关电容读法也对应自由运行的网格。另一读法是网格在每次捕获时重新起算（下垂只取决于保持时长）；在本题用例中它被拒（`leak_from_capture`）。
4. 泄漏律：每个泄漏时刻 `h ← decay·h`，两次更新之间 `h` 不变。对负值同样适用，`h` 从两侧趋向 0 V；与 `sample` 电平无关。理由：题面“每次泄漏更新乘以 decay”是离散律；brief 要求离散律与等效连续律能被用例区分。连续衰减 `decay^((t − t_c)/leak_period)`（`continuous_leak`）在 decay < 1 的五例被拒，`base` 中最大偏差 12.9 mV，`param-override`（decay 0.9、tr 100 ps）中 78 mV。
5. 捕获：`sample` 在 t = 0 之后的上升穿越、且此刻 `rst` 为低时，`h` 取穿越时刻的 `V(vin)`。下降穿越和 `sample` 电平不改变 `h`，`sample` 为高时不跟踪；t = 0 时 `sample` 已高不算捕获。捕获值保持到下一个泄漏时刻，再照常乘 `decay`。理由：沿用原题；“捕获不重启网格”是第 3 条的直接推论，写明以免读成捕获后再等一个周期。
6. 【已定（用户 2026-10-29，决定单第 26 项）；原标“待用户确认 Q2”，即待确认清单第 49 项】复位：`rst` 上升穿越时立即把 `h` 置 0 V，不等泄漏时刻或捕获；`rst` 为高期间 `sample` 上升不算捕获，`h` 保持 0 V；`rst` 下降不做任何事，即使此时 `sample` 已高，`h` 也保持 0 V 直到下一次捕获；t = 0 时 `rst` 已高则从 t = 0 起处于复位。理由：原题面“复位为高时清零”读作电平条件，保持电容上的复位开关在接通时立即放电；brief 要求明确复位期间与释放后的状态，按立即清零写，复位期间状态唯一，释放规则也简单。gold 的事件同步复位最多晚一个泄漏周期，且完全不理会不含事件的短复位脉冲（`reset-release` 中 0.525 ns 的脉冲清掉 0.68 V，gold 不清）。另一读法是沿用 gold：`rst` 只在泄漏时刻和 `sample` 上升时读取；同族 v2-spec-071 就是在 tick 复位的先例。U17-S1 用的是立即复位。
7. 【已定（用户 2026-10-29，决定单第 27 项）；原标“待用户确认 Q3”，即待确认清单第 50 项】捕获与泄漏同刻：排除在合法输入外，要求每个 `sample` 上升穿越离任一泄漏时刻至少 50 ps（用例实际至少 50.35 ps，修正 r1 后）。理由：同刻时先泄漏后捕获得 `vin`，先捕获后泄漏得 `decay·vin`，差 1.5 %（0.8 V 时 12 mV），属 TIE-RULE 第 (ii) 类，必须避开；仿真器无法精确产生外部穿越与内部 timer 同刻，规定次序也测不到。另一读法是在合同中规定次序（例如“同刻时先泄漏、后捕获”）并保留同刻输入。
8. 其他同刻：`rst` 穿越离 `sample` 上升穿越至少 0.5 ns，因为捕获要读 `rst` 电平。`rst` 上升与泄漏时刻同刻时两种次序都得 0 V，`rst` 下降时 `h` 已为 0，都属第 (i) 类，合同不排除；用例中 `rst` 穿越离泄漏时刻至少 22.5 ps，且该时刻 `rst` 电平离 `vth` 至少 0.2 V，所以若用户选 Q2 的另一读法，用例也不必改（Q2 已按推荐定，这句只作记录）。
9. 初态：t = 0 时 `h` 为 0 V，与输入无关（沿用原题）。`initial_vin`（初值取 vin(0) 且不理会 t = 0 的复位电平）在除 `phase-grid` 外的六例被拒；t = 0 时 `sample` 已高不算捕获，由修正 r1 新加的 `start-high` 终评（审核 R01-05），只在这种情形误捕获的 `capture_initial_high` 只在该例被拒。
10. 输出与评分起点（F01，用户已确认 2026-10-28，经项目协调方答复“全部按推荐”）：题面写明 checker 的实际观察起点：只有期望 `h` 一次变化超过 0.1 mV（题面写明的门限 δ，修正 r1，LIST 第 4.9 版第 0.5 节第 20 条）时才开不评分窗（C109 写法），窗长 1.25·tr，不超过 0.1 mV 的变化不开窗；期限 tr 与评分起点 1.25·tr 分开写；误差上限 2 mV；评分波形步长不粗于 tr/4。迟到负例 `late_arrival_1p3tr` 在七例都被拒；窗内对照 `margin_arrival_1p2tr`（1.2·tr 到达）七例都通过，这是用户已接受的余量。
11. 合法输入：控制为 0/0.9 V 逻辑电平，边沿不长于 200 ps（修正 r1 在题面写明：转移指离两个电平都超过 1 mV 的那段时间；checker 由保存行检查，审核 R01-06），不停在 `vth`、不触碰后返回，t = 0 时离 `vth` 至少 50 mV（P0 触碰门限决策卡的推荐 A）；同一输入相邻穿越至少 0.5 ns；`vin` 连续，在 −1 V 到 +1 V 之间，`sample` 上升穿越前后 100 ps 内变化小于 0.25 mV。
12. 不沿用 v4 对电流贡献、`ddt()`、`idt()` 的语法限制。理由同 C056-S1 第 12 条：验收只看外部行为，checker 不检查写法。
13. 用例共 7 个，公开 1 个（`base`）。泄漏时刻是网格行；修正 r1（审核 R01-08）后，每个捕获与清零都落在网格行之后的固定相位，使其后 (1.25·tr, 1.3·tr) 内有评分行，且没有保存行恰在任何一次变化的评分起点 1.25·tr 上（缺省参数的四例 10 ps 网格，穿越在行后 2.5 ps 或 7.5 ps；`param-override` 2 ps 网格、行后 0.5 ps；`param-endpoints-low` 0.8 ps 网格、行后 0.05 ps；`param-endpoints-high` 不变）。`param-override` 与 `param-endpoints-low` 的泄漏台阶大到能看出迟到，泄漏后第一个评分行在 1.26·tr 与 1.28·tr，作为泄漏更新的迟到对照行（见文末一节第 4 条）：

| 用例 | 参数 | 主要区分 |
| --- | --- | --- |
| `base`（公开） | 默认，10 ps 网格 | 首次捕获前 `vin` 变化；0.8 V 捕获后保持 30 个周期，期间 `sample` 高 10 ns、`vin` 跳两次；负捕获；泄漏时刻后 72.5 ps 与前 52.5 ps 的捕获；0.525 ns 的复位脉冲在相位 0.17 清掉非零值；跨过一次 `sample` 上升的复位，在 `sample` 仍高时释放 |
| `phase-grid` | 默认，10 ps 网格 | 十次捕获的相位从 0.07 到 0.95，各保持 2–4 个周期，正负交替；最后两次捕获相距 1.05 ns（高、低各 0.525 ns） |
| `reset-release` | 默认，10 ps 网格 | t = 0 起复位，复位期间有 `sample` 上升；两个泄漏时刻之间 0.525 ns、不含任何事件的复位脉冲清掉 0.68 V；第二次上升遇到 0 V 的双复位；`sample` 为高时复位、释放 2 ns 后 `sample` 才下降；复位保持到结尾，期间两个 `sample` 脉冲 |
| `param-override` | vth 0.2 V、decay 0.9、leak_period 10 ns（上端）、tr 100 ps，2 ps 网格 | 180 ps 边沿上 0.45 V 门限晚 50 ps；同一周期内两次捕获；泄漏时刻前 57.5 ps 的负捕获；复位清零；每步 10 % 的泄漏 |
| `param-endpoints-low` | vth 0.1 V、decay 0.5、leak_period 0.5 ns（实例行写 `0.5n`）、tr 10 ps（都在下端），0.8 ps 网格 | 0.5008 ns 的 `sample` 高电平与低电平、0.5008 ns 的复位脉冲（0.5 ns 下界加一个 0.8 ps 网格步）；泄漏时刻前 56.75 ps、50.35 ps 的捕获；每 0.5 ns 减半 |
| `param-endpoints-high` | vth 0.8 V、decay 1、leak_period 2 ns、tr 1 ns（vth、decay、tr 的上端；tr = leak_period/2），20 ps 网格 | 不漏电时保持不变；180 ps 边沿上 0.45 V 门限早 70 ps；负捕获后复位清零 |
| `start-high`（修正 r1 新加） | 默认，10 ps 网格 | t = 0 时 `sample` 已高、`vin` 为 0.6 V：不算捕获，`h` 保持 0 V，经第一次下降穿越（2.7225 ns）直到第一次上升穿越（5.3225 ns），其间三个泄漏时刻作用在 0 V 上；之后捕获 0.35 V 与 −0.45 V，0.525 ns 的复位脉冲清掉负值 |

14. 台架按标准审核网表约定清单写（`runs/standard-line-20261028/netlist-conventions/LIST.md`，第 3 版，SHA256 `6a6b17cddf813a8e7c7c4be3d47fed3bac5ab63b23fa207e0f49ff9a0f7713af`，只读）：
    - “必须”一档照写：`simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，`tran` 写 `stop`、`maxstep`、`errpreset=moderate`，用了 strobe 就写 `strobeperiod` 与 `strobeoutput=strobeonly`，`save` 列出 checker 读的全部信号；PWL 从 t = 0 起、时间严格递增、末点覆盖 stop。容差取标准审核给 D1 定的值作起点，这是选值依据，实际误差待 Spectre 校准验证，不是误差保证。
    - “不必”一档一律不写（PWL 的 `dc`、`offset`、`delay`，`tran` 的 `step`、`method` 等）；precision 不写进用例网表；“PWL 控制在 20 点以内”一条不执行，部分 PWL 超过 20 点。
    - 参数端点在实例行上的写法与参考解 `from` 范围相同：`vth=0.1`/`0.8`、`decay=0.5`/`1`、`tr=10p`/`1n`、`leak_period=0.5n`/`10n`。修正 r1（审核 R01-14）把 `leak_period=500p` 改为 `0.5n`，生成器同时按文本与按值断言。两种写法在一次舍入下是同一个 binary64 值（5e-10）；C067-S1 的 `200p` 与 `0.2n`、`1000n` 与 `1u` 的差别来自 EVAS 02dee32b 对带比例符号字面量的两次舍入（#289），Spectre 是一次舍入（标准审核 FU-01b），这两对在 Spectre 上各自相等（审核 R01-12 更正归属）。
    - Spectre 执行路径在打包时于作业网表末尾追加 `vabenchExecPath options precision="%.17g" src_allbrkpts=yes`（样板 r2.18）；用例网表不写 precision 与 `src_allbrkpts`，源上也不写 `allbrkpts`。checker 不依赖输出行落在哪里：评分行都是 strobe 网格行，穿越在两侧网格行之间的同一段线性边沿上插值得到；折点是否成为时间行不影响判定。
15. checker（[tests/verify.py](tests/verify.py)）只读波形，不读候选源码或参考解：按记录的穿越与 `vin` 计算期望 `h`；台架义务出错时抛出异常（不判分，不记候选失败），包括参数越界、分辨率、控制电平与间距、控制的电平转移长于 200 ps（由离两电平都超过 1 mV 的保存行给出下界，修正 r1，审核 R01-06）、`sample` 上升离泄漏时刻不足 50 ps、`rst` 离 `sample` 上升不足 0.5 ns、`vin` 越界或在捕获附近移动、控制停在门限上。期望 `h` 的一次变化超过 0.1 mV（题面写明的门限 δ）才开不评分窗，评分点与该时刻的期望 `h` 比较（修正 r1，审核 R01-02）。穿越提取与 P0 六题统一（触碰不算穿越，停在门限上报错）。共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile、公开 `check.py` 与首批逐字节相同。
16. 参考解 [solution/circuit.va](solution/circuit.va) 按自然写法、以 Spectre 可解为准：`timer(0, leak_period)` 乘 `decay`，`rst` 上升清零，`sample` 上升在 `rst` 为低时读 `vin`，`transition(held, 0, tr, tr)` 输出。没有为任何 EVAS 版本改写。
17. 校准候选见 [tests/calibration](tests/calibration/README.md)：24 个错误（修正 r1 加 `capture_initial_high`）、4 个正确（含用绝对 timer 与计数器实现同一网格的 `alt_counter_grid`）。被拒矩阵另存为 `expected.json`，条目都是待 Spectre 校准的预期。

### 待用户确认（四项都已定，用户 2026-10-29）

下面四项原为“待用户确认”，用户 2026-10-29 已按推荐定：Q1–Q4 依次是待确认清单第 48–51 项，即决定单第 25–28 项。推荐、另一读法与理由的原文保留，r01-fix-r2 只改状态（上文同源关系表的 v2-spec-071 一行、建设决定第 2、3、6、7、8 条同样只改了状态）。

| 编号 | 选择 | 推荐（已写入题面） | 另一读法 |
| --- | --- | --- | --- |
| Q1 | 【已定（用户 2026-10-29，决定单第 25 项）】泄漏相位 | 从 t = 0 起的固定网格 `k·leak_period`，捕获与复位不影响它（v4 042 gold 与其历史 Spectre 运行的行为） | 每次捕获后重新起算，第一次泄漏在捕获后一个 `leak_period`（下垂只取决于保持时长）；或从复位释放起算 |
| Q2 | 【已定（用户 2026-10-29，决定单第 26 项）】复位 | `rst` 上升时立即清零，复位期间不捕获，释放不做任何事 | 沿用 v4 042 gold：只在泄漏时刻和 `sample` 上升时读取 `rst`，为高则清零；要求每个复位高电平至少含一个泄漏时刻（同族 v2-spec-071 的 tick 复位先例） |
| Q3 | 【已定（用户 2026-10-29，决定单第 27 项）】捕获与泄漏同刻 | 排除：`sample` 上升离任一泄漏时刻至少 50 ps | 在合同中规定次序（如先泄漏后捕获），保留同刻输入 |
| Q4 | 【已定（用户 2026-10-29，决定单第 28 项）】参数合法域 | 有限闭区间：`vth` 0.1–0.8 V、`decay` 0.5–1、`leak_period` 0.5–10 ns、`tr` 10 ps–1 ns 且 ≤ `leak_period/2`，端点进终评 | 沿用原题的开区间（`decay` 在 (0, 1]，其余为正），不设 `tr` 与 `leak_period` 的关系 |

用户已确认（2026-10-28）：评分起点按 F01 的推荐写法（上文第 10 条）。

### 平局与零点核对

按标准审核定稿的平局判据（`runs/standard-line-20261028/rules/TIE-RULE.md`，SHA256 `a4cf0e73dfc91af72416bb42d273b9b578f6caa2dc6fa098153751dfd280ffa7`，只读），用 build_cases.py（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/build_cases.py`） 以精确有理数逐例扫描，结果在 build-cases-report.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/build-cases-report.json`）：

- 第 1 种（不同来源的事件精确同刻）：六例都没有。捕获与泄漏同刻是第 (ii) 类，由合法域排除（Q3）；`rst` 与泄漏同刻是第 (i) 类，用例也没有。
- 第 2 种（事件恰在 transition 斜坡终点改写目标）：按每次变化的实际完成时刻（LRM 4.5.8 补全斜率）和名义终点“事件加 tr”两种口径扫描，都没有。用例中有被打断的过渡（`base` 7 次、`phase-grid` 11 次、`reset-release` 6 次、`param-override` 1 次），按 LRM 4.5.8 在打断后 tr 内到达新值，合同不排除打断。
- 第 3 种（过渡终点碰上不改写该 transition 的事件）：不是先后之争；扫描也没有发现。
- 第 4 种（timer 落在时间比较的边界）：参考解的 timer 体只读保持值，没有时间比较，不适用。
- 零边沿 `transition()`（样板 r2.18）：已核对。参考解与全部校准候选的 `transition()` 都显式写出非零的 rise/fall（`tr`、其倍数或 `max(tr, 100p)`），台架没有 `transition()`；`continuous_leak`、`track_while_high` 两个错误候选用了不经 `transition()` 的直接贡献，它们的跳变都在不评分窗内，判定不依赖跳变宽度。
- 实数 `==`（样板 r2.18）：已核对。参考解没有实数 `==`、`!=`；它唯一的比较 `V(rst) <= vth` 在捕获时离门限至少 0.1 V（合法域保证 `rst` 不在过渡中）。checker 判断期望值是否改变时不用实数 `!=`：建题时用 1 nV 的差值门限，修正 r1 按 LIST 第 4.9 版第 0.5 节第 20 条改为写进题面的 0.1 mV（审核 R01-02）；穿越提取沿用六题统一规则，按行值与门限精确比较，但用例中没有一行恰在门限上（穿越都在网格行之间）。
- 直流工作点（样板 r2.18）：已核对。参考解在 `initial_step` 里只置 `held = 0`，不读节点；checker 只用 t = 0 行判断控制的初始电平（离门限至少 50 mV）。由 vsource 直接驱动的节点在 t = 0 是逐位精确的值（FU-01d 更正了样板 r2.18 的 1.5e-12 说法，审核 R01-13）。
- 第 38 项前提 1（内部信号恰为零）：参考解的 `cross()` 只作用于外部驱动的 `sample`、`rst`，不对任何内部恰为零的信号检出离开零点；`h` 为 0 时泄漏仍得 0，不需要事件。引用旧版的“通过”前已核对：用例中的控制穿越都在网格行之间，没有恰在门限上的行，旧版的零点与门限处理不影响这些通过结论。

### 历史 Spectre 证据

本机 v3 缓存 `legacy/behavioral-veriloga-eval/results/_local/v3_skeleton_dual_parity_cache/hidden/` 没有本题。v4 缓存 `…/benchmark-vabench-release-v4/reports/first_n_spectre/cache/042/score/` 有五个缓存键，指向同一份波形（CSV SHA256 `c3b126cc…3743`）：原 v4:042 gold（SHA256 `7f3099bd…62dd`，与 historyref 相同）在一份旧评分台架（SHA256 `8d3c1d44…c5a`，与发布版 `score_tb.scs` 不同）上的 Spectre 21.1.0.509.isr12 运行（`+preset=ax`，maxstep 250 ps，无 strobe）。复核见 historical-spectre-crosscheck.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/historical-spectre-crosscheck.json`）：

- 121 个泄漏台阶都起于整数纳秒：每个泄漏时刻都有一行，值仍是台阶前的值，之后按 0.985 下降。这说明 Spectre 上 `timer(0, 1n)` 的网格从 t = 0 起，`transition()` 在事件时刻开始移动。
- 复位：`rst` 在 120.125 ns 上升，gold 到 121 ns 的泄漏时刻才清零。按本题合同（立即清零），这一处 gold 与期望值不同（127 个探点中 1 个）。

这只说明历史 gold 在历史台架上的行为，不是新参考解的 Spectre 结论。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，参考解、checker 和用例都没有 Spectre 运行证据。`results/reference.json` 与 `results/calibration.json` 尚未生成。

待办：

- Spectre 校准：参考解跑全部私有与公开用例并记录误差余量；`tests/calibration` 的候选逐个过同一 checker，结果与 `expected.json` 比对。
- Spectre 待办（样板第 4a 节）：参考解的 `transition()` 延迟为 0，没有待发过渡，但用例中有被打断的过渡（捕获后 52.5 ps、57.5 ps 的泄漏，泄漏斜坡中的清零），记录它们是否按 LRM 4.5.8 的补全斜率运行；记录 `timer(0, leak_period)` 的事件时刻与 strobe 行的关系，以及捕获离泄漏时刻 50.35 ps 至 57.5 ps 时 `cross()` 与 `timer()` 的先后（合法域已排除精确同刻）。校准候选 `alt_delayed_within_tr` 有待发过渡，另行记录。
- 作者校准：按上述结果写结果文件，复核 2 mV、50 ps、0.5 ns 是否需要调整。
- 上面四个原“待用户确认”选择已定（用户 2026-10-29）：Q1–Q4（待确认清单第 48–51 项）为决定单第 25–28 项，都按推荐定，r01-fix-r2 改了状态。
- 难度：规划估计 M，未实测。

开发证据（证据目录 `runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/`，命令、退出码与结果见 checks.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/checks.json`）；都不作校准、录取或 EVAS 能力验收）：

- Python 合成轨迹（未仿真）：建题时 27 个行为模型 × 6 用例共 162 次判决，事先写下预期的 151 次全部符合；7 项证据有效性控制都判为 checker 错误而非候选失败。修正 r1 后为 30 个模型 × 7 用例，见“2026-10-29 修正 r1”一节。见 synthetic-controls.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/synthetic-controls.json`）。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：参考解 6 个私有用例和公开用例全部通过，只用网格行重判结论不变；起始模型因空模块被拒（`ERROR [rust_lowering]: … no_continuous_linear_ir`）。27 个校准候选各 6 个用例共 162 个条目：150 个与 `expected.json` 一致，0 个不一致，12 个无判决（旧版不能运行的 `tr_floor_100p`、`track_while_high` 各 6 个）；`tr_floor_100p` 的旧版可运行探针 6 次判定与它的预期一致，`track_while_high` 没有可运行的探针，待 Spectre 验证（审核 R01-10 更正说法）。修正 r1 后的计数见“2026-10-29 修正 r1”一节。见 legacy-evas.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/legacy-evas.json`）。
- EVAS 02dee32b：参考解 `phase-grid`、`reset-release`、`param-endpoints-high` 跑完 c 阶段并通过 checker；`base`（私有与公开）、`param-override`、`param-endpoints-low` 在 c 阶段停于已知诊断 `source transition proof budget exhausted: slot 2`（#270 NF-01）；起始模型在 a 阶段报 `module requires an analog block or child instances`。见 summary.json（`runs/t3-p1-build-20261029/r01-spec-droop-leakage-hold/evas-02dee32b/summary.json`）。
- Docker：环境镜像与评分镜像各实际构建一次并检查，未执行电路；结果见 checks.json。

## 2026-10-29 修正 r1（r01-fix-r1，审核 R01 r1 的处理）

本节**未仿真**：没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。依据是独立审核 `runs/t3-p1-build-20261029/review-r01-r1/astra-review.json`（sha256 `7793e313…6d108`）与Benchmark 维护方 brief `runs/t3-p1-build-20261029/briefs/r01-fix-r1.md`，以及项目协调方 2026-10-29 的补充：标准审核网表约定清单第 4.9 版（sha256 `f05138e7…eeed5`）第 0.5 节第 20 条“checker 的变化门限”、平局判据第 5 种情形（TIE-RULE.md `418d542a…b108`）、FU2b 判读（`5691c10e…`）。逐条处理、命令与退出码见 disposition.md（`runs/t3-p1-build-20261029/r01-fix-r1/disposition.md`）。本题涉及 R01-02、R01-05、R01-06、R01-08、R01-10、R01-12、R01-13、R01-14、R01-16。R01-11（共用入口追加执行路径一行、核对日志接受步数）不在本轮：`tests/v2_runtime.py` 是全部题目逐字节共用的文件，待共用入口一轮（execpath-runtime）统一改。

1. **R01-02 与第 20 条：变化门限 δ。** 题面观察规则改为：只有期望 `h` 一次变化**超过 0.1 mV** 的时刻之后 `1.25*tr` 内的点不评分，不超过 0.1 mV 的变化不开窗。checker 用同一个 δ = 1e-4 V，与该事件之前的期望 `h` 比较；评分点与该时刻的期望 `h` 比较（原先与最近一次开窗时的值比较，两者最多差 1 nV）。
   - 推导（按第 4.10 版的算法重算）：被比较的 `h` 由保存的 `vin` 算出（捕获）或由它乘参数 `decay` 得到，|vin| ≤ 1 V。七份终评网表都写了 options 的 reltol 1e-6、vabstol 1e-8 V 和 tran 的 errpreset=moderate，所以瞬态实际用的 reltol = 1e-6 × moderate 的倍数 1 = 1e-6，vabstol 取 options 的 1e-8 V（errpreset 不改它），不用 Spectre 缺省；一侧噪声带 1e-8 + 1e-6 × 1 = 1.01e-6 V，两侧 2.02e-6 V，下界 10 倍为 20.2 µV。合同允许任意小的合法变化（泄漏的指数尾、近于相等的两次捕获、decay = 1），所以门限写进题面；上界取 atol（2 mV）的一半，1 mV。取 δ = 0.1 mV。七个用例里没有离 δ 不到一倍的名义变化（生成器统计）。
   - 控制（改前、改后 checker 各判一次）：捕获使 `h` 变化 0.05 mV、恰为 0.1 mV、刚超过的 0.101 mV、0.2 mV 与审核复现的 0.5 nV，各配干净输出、tr 内 10 mV 瞬态、窗后 10 mV 误差：0.05 mV 与 0.1 mV 的窗内瞬态由改前通过变为改后被拒（这两种变化按新题面不开窗），其余判决不变。
2. **R01-05：** 新终评用例 `start-high`（t = 0 时 `sample` 已高、`vin` 0.6 V，第一次上升穿越在 5.3225 ns 前全部评分），新错误候选 `capture_initial_high`（只在 t = 0 时 `sample` 为高、`rst` 为低时把 vin(0) 当作捕获）与同名合成控制：只在 `start-high` 被拒，其余六例与参考解相同。
3. **R01-06：** checker 检查控制的电平转移：离 0 V 与 0.9 V 都超过 1 mV 的保存行连成的一段，首尾时刻之差是转移长度的下界，超过 200 ps 判台架违例（不判分）；它不会把 200 ps 以内的合法边沿判错，只会漏掉比 200 ps 长不到两个网格步的违例。题面合法域一句写明“转移”指离两个电平都超过 1 mV 的那段时间（1 mV 是第 20 条意义上的门限，按第 4.10 版的算法：下界 10×(1e-8 + 1e-6×0.9) = 9.1 µV，与常数电平比较只计一边；上界取 0.9 V 摆幅的一半 0.45 V）。控制：`sample` 边沿 150 ps、恰 200 ps（拐角不在行上与在行上）通过；260 ps、1 ns（审核复现）与 `rst` 1 ns 边沿改后报台架违例，改前照常判分。终评与建题时的旧版波形都不触发这条检查。
4. **R01-08：** 泄漏时刻是网格行，原先 1.25·tr 是网格步的整数倍，每次泄漏变化的评分起点都落在保存行上。改法（F01 的观察起点公式不改）：缺省参数的三例（`base`、`phase-grid`、`reset-release`）网格 25 ps 改为 10 ps，穿越时刻一个不动（原在行后 22.5 ps，现在行后 2.5 ps 或 7.5 ps）；`param-override` 改为 2 ps 网格（第一遍用 10 ps 网格，并把在行后 7.5 ps 的那次捕获提前 5 ps，离泄漏 57.5 ps；第二遍改为 2 ps 网格，穿越都在行后 0.5 ps）；`param-endpoints-low` 改为 0.8 ps 网格（第一遍 2 ps 网格；第二遍捕获与清零在行后 0.05 ps，最短脉冲、间隔与复位脉冲改为 0.5008 ns，离泄漏最近的捕获改为 50.35 ps，挪动都不超过 1.2 ps）；`param-endpoints-high` 本来就没有这样的行（decay = 1，泄漏不改变 `h`），不改。生成器按最终保存行与超过 δ 的变化断言评分起点不在行上，并断言每例至少三次 300 mV 以上的捕获或清零在 (1.25·tr, 1.3·tr) 内有评分行（第一个评分行在 1.255、1.265、1.275 或 1.262·tr）。
   - 周期更新的迟到对照行（R01-08 建议的第二部分，修正 r1 第二遍）：1.3·tr 到达的迟到负例在一次已稳定的泄漏台阶 s 之后第一个评分行 x·tr 处差 s·(1 − x/1.3)。`param-override`（每步 10 %，最大台阶 85 mV）泄漏后第一个评分行在 1.26·tr，3 个台阶在这一行超出 2 mV（2.2–2.6 mV）；`param-endpoints-low`（每步 50 %，最大台阶 475 mV）在 1.28·tr，11 个台阶超出 2 mV（2.3–7.3 mV）；生成器断言这两例各至少三个。缺省参数的四例在泄漏后 1.26·tr 也有评分行，但最大的泄漏台阶（h 的 1.5 %，14.25 mV）乘 1 − 1.25/1.3 只有 0.55 mV，窗口内任何一行都看不出迟到，列为例外；`param-endpoints-high` 没有泄漏变化。合成控制 `leak-late-1p3tr`（只有已稳定的泄漏台阶在 1.3·tr 到达）只在 `param-override` 与 `param-endpoints-low` 被拒，`leak-late-1p2tr` 七例都通过。
   - 边界控制：审核复现在原 25 ps 网格上前后 1 ulp 的翻转照旧存在（那是原台架的问题），改后 10 ps 网格上离评分起点最近的两行在前后 1 ulp 时判决都不变。
5. **余量：** 下限按样本偏离 1 mV、时刻偏差 1 fs 推，一个穿越最多移动 1 mV/斜率 + 1 fs（100 ps 边沿 0.112 ps，180 ps 边沿 0.201 ps，90 ps 边沿 0.101 ps），间距按两个穿越算；上限按测试目的，承担覆盖的用例离合同下界不超过一个网格步：`param-endpoints-low` 的 0.5008 ns 脉冲、间隔与复位脉冲（下界 0.5 ns，0.8 ps 网格，下限 0.5 ns + 0.202 ps），离泄漏时刻 50.35 ps 的捕获（下界 50 ps，下限 50.101 ps）；`base`、`phase-grid` 的 52.5 ps 在 10 ps 网格的一个网格步内。`rst` 离 `sample` 上升的最近间距是 0.7392 ns，这条义务只用来保证捕获时 `rst` 电平明确，按测试目的不设一个网格步的上限，已核对。生成器断言全部上下限（build_cases_fix.py（`runs/t3-p1-build-20261029/r01-fix-r1/scripts/c057/build_cases_fix.py`），`--variant orig --check` 复现改前字节）。
6. **R01-10、R01-12、R01-13、R01-14、R01-16：** 旧版不能运行的两个候选的说法改为“`tr_floor_100p` 有替代探针且一致，`track_while_high` 待 Spectre 验证”（上文待定项与校准 README）；端点舍入的原因归属 EVAS 两次舍入、Spectre 一次舍入（上文第 14 条）；直流工作点的说法按 FU-01d 改写（上文平局与零点核对）；实例行 `leak_period=0.5n`；校准 README 开头写明未仿真，旧版段落带完整标签。
7. **样板 r2.29 的核对。**
   - 零边沿 `transition()`：参考解、全部校准候选（含两个历史原件）与台架里没有省略或写 0 的 rise/fall（`continuous_leak`、`track_while_high` 是不经 `transition()` 的直接贡献，跳变在不评分窗内）。按 stop 分档的 w 与“离缺省边沿开始最近的评分时刻”因此都不适用：

     | 用例 | stop | w | 缺省边沿 | 最近的评分时刻 |
     | --- | --- | --- | --- | --- |
     | `base` | 130.8 ns | 1 ns | 无 | 不适用 |
     | `phase-grid` | 45.8 ns | 1 ps | 无 | 不适用 |
     | `reset-release` | 50.8 ns | 1 ns | 无 | 不适用 |
     | `param-override` | 118 ns | 1 ns | 无 | 不适用 |
     | `param-endpoints-low` | 11.8 ns | 1 ps | 无 | 不适用 |
     | `param-endpoints-high` | 51.5 ns | 1 ns | 无 | 不适用 |
     | `start-high` | 20.8 ns | 1 ps | 无 | 不适用 |
   - 最后一行与 stop：checker 取最后一行，不按“时间等于 stop”找行；完整性检查的容差是 stop 的 1e-6，不是从实测偏移推出的。stop 不在泄漏时刻上，最后一次泄漏离 stop 超过 1.25·tr 加一个网格步，最后一次捕获或清零离 stop 至少 2·tr（生成器断言），没有要在 stop 处读的值。已核对。
   - 网表第 0.5 节：七份终评网表与公开网表按第 4.9 版的条目扫描（扫描时清单文件已是第 4.10 版 `e99f4ddb…`，第 4.10 版只改第 7、20 条、新增第 21 条，扫描的条目不变）（netlist-scan.json（`runs/t3-p1-build-20261029/r01-fix-r1/netlist-scan.json`），含 `list41_scan.py` 的 `check()`）：没有指数加比例符号，比例符号只有 `n`、`p`；容差都非零；没有 strobetimes；每条语句一行，LF；用例网表不写 precision 与 `src_allbrkpts`；errpreset=moderate。超过 20 点的 PWL（`phase-grid` 的 `Vsample` 最多 50 点）靠执行路径的 `src_allbrkpts=yes`，checker 只读 strobe 行，不依赖它。已核对。
   - 平局第 5 种情形：参考解只有一个 timer（泄漏网格），捕获与它至少相距 50 ps，不适用。FU2b：没有 `idt`、pulse 源或 `$rdist_normal`，不适用。
8. **checker 中判“变了没有”“是否为零”“是否相等”的地方**（第 20 条，逐处清单见 disposition）：期望 `h` 的变化、清零前 `h` 是否为零、泄漏是否改变 `h` 都用 δ；控制是否处在某个电平用题面写明的 1 mV；`vin` 的平稳用题面写明的 0.25 mV；穿越规则里行值与门限的精确比较（六题统一规则）与统计量 `negative_captures` 的符号判断属第 20 条范围、不在 R01 发现范围内，没有改，交Benchmark 维护方；已核对（扫描 B，2026-10-29，报告（`runs/t3-spectre-wave2-20261029/scan/round-b/report.md`）第 4 节末“第 20 条 δ 的核对”，sha256 `879b3a39…7fed`）：前者作用在 vsource 驱动的 `sample`、`rst` 上，只决定恰在门限的行与台架错误，不改判定；后者只是统计，不进判决。
9. **判决与证据。** 合成控制 30 个模型 × 7 个用例共 210 次判决，改前与改后 checker 对每个模型的判决都相同，事先写下的 172 个预期全部相符，原有用例上与建题记录相同；7 项证据有效性控制都报错；判决变化只出现在上面的新控制里（5 处，synthetic-controls.json（`runs/t3-p1-build-20261029/r01-fix-r1/c057/synthetic-controls.json`））。`expected.json` 加 `start-high` 一列与 `capture_initial_high` 一行，原有条目不变，`checker_failure` 写明 δ，条件按改后的用例改写。旧版：改动与新加的六个用例重跑 183 次（`param-override`、`param-endpoints-low` 改网格后又重跑一遍，前一遍移到证据卷的 `superseded-r08b`；参考解全部通过；候选有预期的 169 个条目 157 个一致、12 个无判决，即旧版不能运行的两个候选；探针 6 个一致），`param-endpoints-high` 的建题运行只用改后 checker 重判，判决无一变化（legacy-regrade.json（`runs/t3-p1-build-20261029/r01-fix-r1/c057/legacy-regrade.json`））。合起来 196 个有预期的条目：182 个一致，0 个不一致，14 个无判决（`tr_floor_100p`、`track_while_high` 各 7 个）；只用网格行重判计数相同；`tr_floor_100p_param` 探针 7 个用例都与 `tr_floor_100p` 的预期一致（legacy-vs-expected.json（`runs/t3-p1-build-20261029/r01-fix-r1/c057/legacy-vs-expected.json`））。
10. **Benchmark 维护方补充（2026-10-29T05:42Z，`runs/t3-p1-build-20261029/briefs/r01-fix-r1.steer-list410.md`，sha256 `94875695…`）的复核**（未仿真；计算与扫描见 steer410-checks.json（`runs/t3-p1-build-20261029/r01-fix-r1/steer410-checks.json`））。依据：清单第 4.10 版（`e99f4ddb…`）、SL-DEC-20261029-05 的补充（`JUDGMENT-W2-S7S12-G400-L0A.md` 第 5 节，`2b6b7d8e…`）、样板 r2.35（`d090ca15…`）。
   - 第 20 条：δ 与电平带的下界已按第 4.10 版的算法重算（上文第 1、3 条）：20.2 µV ≤ 0.1 mV ≤ 1 mV；9.1 µV ≤ 1 mV ≤ 0.45 V，结论不变。题面原有的 `vin` 平稳 0.25 mV 按同一算法下界为 10×2×(1e-8 + 1e-6×1) = 20.2 µV，也满足。
   - 第 7 条：checker 取最后一行，不按 time == stop 找；完整性容差是 stop 的 1e-6（本题最小的 stop 11.8 ns 时为 1.18e-14 s），远大于实测偏移上界 3.0e-17 s，也不是从偏移推出的；没有要在 stop 附近读的值。不变。
   - 第 21 条：本题 checker 与本轮工具都不从 spectre.log 取 `$strobe`、`$display`、`$fwrite` 记录：无。
   - cross 返回根：评分依赖 `sample` 上升穿越（捕获）与 `rst` 上升穿越（清零）的次数。`cross()` 都没写 time_tol（Spectre 缺省 1 s，大于 stop）与 expr_tol；按最宽读法 expr_tol = 1e-9 + 1e-6 × max|expr|，最大 0.80 µV。按精确的 PWL 源逐例求根：`V(sample) − vth` 91 个根、`V(rst) − vth` 22 个根，相邻两根之间 |expr| 的最大值最小都是 0.1 V（`param-endpoints-low`，vth = 0.1 V），是 expr_tol 的 1.2e5 倍；`vth_fixed` 类候选的 `− 0.45` 最小 0.45 V。都必须报两次，计数可以评分；没有根落在 PWL 折点上。合同上也成立：合法的 `sample`、`rst` 在两个电平之间切换，每次转移不长于 200 ps，相邻穿越至少相隔 0.5 ns，所以两次穿越之间信号一定到另一电平的 1 mV 以内，离 vth 至少 0.9 − 0.001 − 0.8 = 0.099 V，checker 也按这两条检查台架。
   - 一次性 timer（FU-11b、FU-11c）：参考解只有周期 timer `timer(0, leak_period)`；候选里 `leak_from_capture`、`alt_counter_grid` 用一次性 timer，事件体里都不拿 `$abstime` 与设定时刻比较。`$abstime` 的比较只有 `sample_deglitch_0p6n` 一处，在 `sample` 上升的 cross 事件体里比较低电平时长与 0.6 ns，用例中最近差 11.6 ps（`param-endpoints-low` 的 0.5884 ns 低电平），不是与 timer 的设定时刻比较：无。
   - transition 的 td（U15）：td 都是常数（0；`alt_delayed_within_tr` 为参数式 0.2·tr），没有运行中改 td 的写法：无。

## 2026-10-29 题面门限与总时限（r01-fix-r3）

本节**未仿真**：没有运行 Spectre、EVAS 或模型。本题只改了 `task.toml` 的 `[verifier] timeout_sec` 与本页；题面、网表、checker、参考解、校准件与共用文件都没改。依据：建题样板 r2.38 第 4c 节（用例时限与题目总时限）；项目协调方 2026-10-29 同意本轮现在改。同一轮的题面门限一项只涉及同批的 [r01-spec-droop-front-end](../r01-spec-droop-front-end/SOURCE.md)，本题题面不动。

1. **总时限（样板 r2.38 第 4c 节）。** `[verifier] timeout_sec` 由 600 改为 960，`task.toml` 别的字节不动。私有用例 7 个，都没写 `timeout_s`，按共用运行入口的缺省各 120 s，和为 840 s；加 max(10 % 即 84 s, 60 s) = 84 s，得 924 s；向上取整到整分钟为 960 s。理由（第 4c 节）：每个用例都可以合法地跑满自己的时限，总时限小于它们的和，就会截掉按单用例规则没有超时的提交。用例时限不变，判决与期望都不变。
2. **用例时限：待交回。** 第 4c 节要求用例时限不小于参考解与正确候选在已交回 Spectre 作业里实测最长用时的 2 倍（向上取整到整分钟）。本题在 P1PC 包里的作业截至本轮都还没有交回，这一条待交回后按实测复核；用例时限照旧取缺省 120 s。打包时按 Verilog-A 模块数与步数的估计，本题参考解与应接受的候选都是一个模块，每个作业最长约 32.8 s，2 倍为 65.6 s，向上取整为 2 分钟，不超过 120 s；这只作参考，不代替实测。
3. **已发出的 Spectre 作业照样作数。** 本轮没有改网表、checker、参考解与校准件，已上传的 P1PC 八个包（`spectre-P1PC-must-01-v1`、`spectre-P1PC-rec-01-v1` 至 `spectre-P1PC-rec-06-v1`、`spectre-P1PC-opt-01-v1`）照样作数，不需要新作业：作业网表都由未改的用例网表得来（参考解与候选的作业是用例网表加执行路径一行，缺省容差对照另去掉容差一行与 `errpreset`），交回后用未改的 checker 判；包里也没有题面与 `task.toml`。本轮逐个核对了八个包的 952 个作业（本题 212 个）：作业记录里的用例文件、用例网表、checker 与 contract 的 sha256 都与现行题包相同，作业网表也都按上面的规则由现行用例网表得到。作业自己的时限按打包时的规则定，与题目总时限分开（第 4c 节）。
4. **结构（未执行电路）。** `scripts/benchmark_workbench.py --check --package` 对本题通过，题包里没有 `__pycache__`；与本轮开工时的文件清单相比，只有本页与 `task.toml` 两个文件不同。Docker 镜像的构建目录是题包的 `environment/` 与 `tests/`，不含这两个文件，这两个目录本轮也没有改动，所以本轮没有重建镜像。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 1 处台架义务检查（C057-06，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `e35ec3bc4159c5c5b69ea1acc5e32733154a299c87894b16604eb502e69f041c`，改前 `697399fd…`）与本文件。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **C057-06**（`control_crossings` 第 128 行调用 `crossings`，第 60–62 行）：`sample`、`rst` 的保存行上相邻两行恰为 `vth`（停留）报台架错误 → 按定义判；`crossings()` 去掉这一句，穿越的定义不动。
- 随同改（决定第 1 项，起点）：`control_crossings` 第 126–127 行 t = 0 那一行离 `vth` 不足 50 mV × `REL` 报错 → 按定义判，门槛不变。
- 碰到：改前只当“不算穿越”，现在报台架错误（决定第 2 项）。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`sample`、`rst` 各自对 `vth`。`check_stimulus` 在 `control_crossings` 里逐个输入调用，放在原来起点检查的位置（电平范围与转移长度检查之后、取穿越之前）。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 18 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”；离 `vth` 不足 0.04999995 V（`START_MARGIN` × `REL`），报 “starts … closer than …”；
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
| 做法甲（v4.17） | 适用 | 受查量（`sample`、`rst` 各自对 `vth`）的起点、停留、碰到按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点对地；没有叠放源（本题网表里受查节点各由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 9 份网表（私有 7、公开 `cases.json` 1、`visible_test.scs` 1）共 27 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 18 个（PWL 18 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(x)` 与 `vth`，参考解在 `V(x) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `leaky_hold` 在 `cross(V(rst) - vth, +1)`、`cross(V(sample) - vth, +1)` 上求根，就是受查输入本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，9 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 9 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前只当“不算穿越”，现在一律报台架错误。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到：instruction.md 第 28 行 “They never rest at `vth`, and at t = 0 each is at least 50 mV away from `vth`. An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 36 行 “A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：9 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 153 行）。18 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（18/18）。
- B 候选：扫描列出的 28 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（54 组不同的行，共 2208 行）。改前、改后判决逐个相同，新 checker 不报台架错误（28/28）。
- C 变体（在 `base` 上改 `rst` 的定义；每个变体事先写下预期），12/12 符合预期：
  - `rst` 起点按十进制恰在门限上：报 “starts on”
  - `rst` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `rst` 起点离门限 0.0498999 V：报 “closer than”
  - `rst` 起点离门限 0.0500999 V：不报台架错误（照常判分）
  - `rst` 在 7.796e-08 s 处按十进制停在门限：报 “rests on”
  - `rst` 在 7.796e-08 s 处只在 binary64 下停在门限：报 “rests on”
  - `rst` 在 7.796e-08 s 处按十进制碰到门限：报 “touches”
  - `rst` 在 7.796e-08 s 处只在 binary64 下碰到门限：报 “touches”
  - `rst` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `rst` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `rst` 的源有一个值带单位 `0V`：报 “cannot read”
  - `rst` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P1PC-must-01-v1 16、spectre-P1PC-rec-02-v1 21、spectre-P1PC-rec-03-v1 133、spectre-P1PC-rec-04-v1 42，共 212 个。new 与改前 checker 整份判决 212/212 相同。与原判比 status、passed 与台架错误的有无 212/212 相同，整份判决 sha256 也相同。

### 8. 前面各节的相关句子

- 建模选择第 15 条（第 105 行）“只读波形”、台架错误里的“控制停在门限上”与“穿越提取与 P0 六题统一（触碰不算穿越，停在门限上报错）”：checker 现在也读用例网表的 vsource 定义与 tran 行的 stop；起点、停留、碰到改按定义判，碰到报台架错误，`crossings()` 不再因停留抛出异常（穿越时刻的取法不变）。
