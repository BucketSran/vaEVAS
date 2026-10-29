# 来源与验收状态

## 行为依据

### 规划候选身份

规划候选身份：`task_id` C061-S1，`unit_id` C061，来源 `src-f4ebc63fbfa6`，`primary_ref` C061，动作 S（spec-modeling），家族 R01（采样保持与多通道读出），优先级 P1，难度 M，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 C061-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。登记要求：
- reason：两级状态与相位交互构成独特机制；difference：两份模拟状态在不同相位传递；
- reuse：低相输入级获取、高相输出级获取，两套 alpha 及轨间钳位；
- author_work：规定 timer 与相位边沿的次序、初态和动态电源轨处理；分别检查两级保持，不能改成一次复制；
- Grok 意见（采纳方向）：采纳独立两级状态；与理想采样合并会丢掉相位传递机制。

本题放在 R01 的 `r01-sampling-03` 批次（批次目录与 README 由主控写），题号 `r01-spec-dual-track-hold`。`source_group` 取新组名 `v4-236`：已建题包和 SOURCE_GROUPS 中原来都没有以 v4:236 或 v3:285 为来源的组。P1 队列 `runs/t3-p1-plan-20261028/p1-queue.json` 中本候选的 `same_source_existing_tasks` 为空。

讨论记录中的已定事项：本线讨论记录 `local/research/benchmark-submission-20261025/README.md`（不在本工作树，sha256 `562a36df97370ff163d45d81200d104b4a228695982a99e5c037375770c97c19`）「### B13 · 双级交替采集与状态交接」一节（第 1426 行起）：
- 待补：“输入级低相采集、输出级高相跟踪前级；gold 为 tick 更新，不当连续 R01 core。若改连续，另写完整合同。”本题保留 tick 更新（建模选择第 2 条；原列待用户确认 1，已定：用户 2026-10-29，决定单第 20 项），把 gold 的 tick 行为写成可以独立理解的完整合同，不把它当连续 R01 core。
- 去重关系：“级联双状态，不是 R01 并联乒乓；保留同家族关联，不按名称合并。”本题的两份状态串联：输出级跟踪的是输入级保持住的值。这与同一记录中 R01G（MUX 提前选通、交错与乒乓集成，第 738 行起）、R01I（乒乓输出窗口测试，第 760 行起）的两支路并联交替不同，见下文“同源关系与职责差异”。
- 在记录中检索 C061、dualtrack、dual-track、双级、乒乓：除 B13 一节和第 320 行家族表中的“扩 B13 双级交替采集与状态交接”外，没有其他关于本候选的已定事项；“乒乓”只出现在 R01G、R01I 两节和家族表。决定卡目录 `runs/t3-p0-pilot-20261027/decision-cards/` 中没有本候选的卡；P0 门限触碰卡（选项 A）的规则照用，见建模选择第 11 条。本单没有发现记录与 brief 不一致的已定事项。

用户已确认的口径：评分起点（F01，用户已确认，2026-10-28）见建模选择第 10 条；参考解按自然写法、以 Spectre 可解为准（用户 2026-10-28）见建模选择第 14 条。

### 历史原件与改编

主来源是仓库内的 [v4:236 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/236-dual-track-sample-hold/public/instruction.md)，sha256 `ee727fba0bbe46cdbcbe2e7975581a8db217ac98d93c4f1cbadc1e2011759937`，规划登记为 repository-contained。原题沿用的事实：
- 模块 `dual_track_sample_hold` 与位置端口 `vdd, vss, clk, vin, vout, phase`；参数 `vth` 0.45 V、`tick` 0.5 ns、`alpha_in` 0.45、`alpha_out` 0.55、`tedge` 50 ps、`vinit` 0 V；
- 时钟低时输入级有限采集、输出级保持；上升沿后输入级保持；时钟高时输出级以有限带宽跟踪输入级保持的值；下降沿后输出级保持到下一个高相；存储电压钳在本地轨之间；`phase` 只在输出级跟踪时为高。

原题面没有写：tick 网格的起点和相位、tick 与时钟沿的先后、每次更新的公式（只有“tracking fraction per update”这个名字）、输出级读输入级哪一刻的值、两级初值、钳位读哪一刻的轨、保持的那一级是否也钳、各电压的参考端、`phase` 的电平、合法输入域和观察容差。这些是 author_work 要补的，见建模选择。

原 gold 是 [dual_track_sample_hold.va](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/236-dual-track-sample-hold/evaluator/solution/dual_track_sample_hold.va)（sha256 `edf530177c2a6fd721c1196b85b2cadef46a638786e4900c5ea69ea7d6b8feab`）。它的写法：`initial_step` 把两级置为 `vinit`，按时钟电平置相位标志；`cross` 在两个方向上改相位标志；`@(timer(0, tick))` 每个 tick 读 `V(vdd, vss)`，低相 `stage_in += alpha_in*(V(vin, vss) - stage_in)`，高相 `stage_out += alpha_out*(stage_in - stage_out)`，然后两级都钳到 `[0, vspan]`；`vout` 与 `phase` 都相对 `vss` 输出，`phase` 的高电平是最近一次 tick 读到的轨间电压。新合同把这些行为写成可观察的规则，结论与原 gold 相同（建模选择第 3 至 9 条），所以原 gold 能原样通过本题，见“外部来源与许可”中的记忆污染一段。

原 checker 是本机 legacy 仓库的 `runners/checkers/v4/task_236.py`（路径 `legacy/behavioral-veriloga-eval/runners/checkers/v4/task_236.py`，sha256 `f9e13f882c4fdf460497dba4d24c4cc02779c871259ebf1d4839dac9d07ccd11`，legacy 提交 `fc1f3b3631`，只读）。它的局限：
- 参考更新模型写死了 `tick`、两个 alpha、0.45 V 门限和 0.9 V 钳位上界，参数覆盖不受检验；
- 在每个 tick 后 150 ps 取 `vout` 比较，按平均误差 35 mV、最大误差 120 mV 判定；保持窗允许 60 mV 变化；
- 台架只用默认参数、0.9 V/0 V 的固定轨，`vin` 在 0.16 V 到 0.82 V 之间，钳位从未触发；后两个上升沿时 `vin` 恒定，只有前四个沿能区分保持值与实时输入。
本题不继承它的判据和成绩。

外接盘的历史净化包（路径文本 `证据卷/historical-purification-20261022/improve-packs/dualtracksamplehold/`，只读，不链接）记录了同样的缺口：
- `DEFECTS.json`（sha256 `d7ca08630fd2e846a390355669f759229dc088925799efcef1a4946b9e3401c9`）的 D1“钳位没有激励”判定属实，修复只改激励（在原 stop 后追加越过两轨的 `vin`）。`OUTPUT/CHANGES.md`（sha256 `ddbed646f74ac6f7b0c68c1d49fc95ccc5ee0e5e8e4a820f692383ce3b359b9a`）与 `OUTPUT/manifest.json`（sha256 `ffc385b83062ca17a352bfd48136a4a44d2a07c31aac78564de8fd9fa6b88378`）有逐项证据；checker 闭包 `CHECKER_SOURCE/closure.py` 的 sha256 为 `5e7cdbdf1fbf3247e89289d4b311150d72e71b94da207e0ae5d8db35925c3265`。
- 遗留问题是 tick 网格的起点没有写明；`coverage_gaps_not_to_fix` 还列出参数只用默认值、轨固定、输入级只能经下一个高相间接观察。
- 净化包把“先钳输入再采集”的变体当作另一种合法实现（它的激励里两种写法收敛到同一值）。本题按原文“钳位存储电压”写成先更新后限幅，先钳输入是错误模型 `clamp_input_first`：在越轨输入的短低相之后，两种写法的保持值相差 75 mV 到 123 mV（合成控制），在 `base`、`rails-offset`、`param-endpoints-low` 被拒。
本题把这些缺口写成合同和台架要求：tick 从 t = 0 起（第 4 条）；钳位用例（`base`、`rails-offset` 与两个端点用例）；动态轨（`rail-droop`）；参数覆盖（`param-override` 与两个端点用例）；短相位让两级的未完成采集都在输出上可见（`base`、`grid-phase`）。

同源的历史形式，按规划不另计题：
- [v4:1236 修复题](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1236-dual-track-sample-hold-bugfix/public/instruction.md)（sha256 `0c5664979582d9657207944e8149e445b25679558aa51953938daddda4ec70d9`）的错误包 `dual_track_sample_hold.va`（sha256 `063e1bc43c6d834432143f13bdb2db6f156280ee280cc4fd7da10f0c84bf364d`）与下面的 `neg_002_single_edge_sampler` 逐字节相同；
- [v4:736 测试台题](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/736-dual-track-sample-hold-testbench/public/instruction.md)（sha256 `82c259006fcb261dfe888195bb0109505d72146fb872c85b2881a161c185cfb7`）要求测试台检出五个变异，见 [mutation_catalog.json](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/736-dual-track-sample-hold-testbench/evaluator/mutation_catalog.json)（sha256 `ef749f368a583c6a32734df2608ad115ba878f7a3c125399a6329ba7c4812b7f`）；
- v3:285 `285-dual-track-sample-hold` 是 v4:236 的前身（v4 checker profile 的 `source_task_id`），gold 在公开仓库中与 v4:236 是同一 git 对象 `6ec12039`。

本题校准候选与五个历史变异的对应，按各变异包相对原 gold 的实际改动核对：
- `neg_001_transparent_output`：每个 tick 把输出值置为钳位后的 `V(vin, vss)`，不分相位，对应 `transparent_output`（每个 tick `b = V(vin, vss)` 后限幅），改动相同；
- `neg_002_single_edge_sampler`：去掉 timer，上升穿越时把钳位后的 `V(vin, vss)` 存为输出，对应 `single_edge_sampler`，改动相同；
- `neg_003_wrong_track_phase`：输入级的更新条件由 `out_tracks < 0.5` 改成 `> 0.5`，两级相位互换，对应 `wrong_track_phase`；
- `neg_004_no_output_hold`：输入级只在低相更新，输出级在每个 tick 都更新，对应 `no_output_hold`；
- `neg_005_phase_monitor_wrong`：`phase` 取反，对应 `phase_inverted`。
neg_003 至 neg_005 还把 `initial_step` 中 `vspan` 的赋值挪到两级初值之后，次序变化不影响行为。其余 33 个错误候选是新写的，其中针对两级交接的有 `input_stage_ideal`、`output_stage_ideal`（一级退化为复制）、`output_copy_at_rising_edge`、`input_sample_at_rising_edge`（一级在边沿理想复制）、`output_reads_vin`（输出级绕过输入级）和 `input_tracks_both_phases`（输入级不保持）。

### 历史 Spectre 证据

按样板第 3a 节查了 v3 缓存 `legacy/behavioral-veriloga-eval/results/_local/v3_skeleton_dual_parity_cache/hidden/`（没有本题或 v3:285 的条目），以及 v4 缓存，后者有原 gold 在原 score 台架上的一次运行：路径文本 `legacy/behavioral-veriloga-eval/benchmark-vabench-release-v4/reports/first_n_spectre/cache/236/score/29ebd5a6ce448b632337bc42843c1d3a3e2fec211dff37a9b72d0221d23ff859/`。身份：Spectre 21.1.0.509.isr12，Spectre X `+preset=ax`（日志显示 `maxstep` 被 Spectre X 停用，reltol 1e-3），2026-07-11；DUT 与 historyref 的 gold 逐字节相同（sha256 `edf53017…feab`）；台架除 include 路径与缩进外与 release 的 `evaluator/score_tb.scs` 相同；波形 `tran_spectre.csv` sha256 `2f2d6c45cbfeb5e2de4037363063c023fd8ac9f671db1efc7cdb5b6b1e0dad07`，580 行。用本题合同的 tick 递推在同一组记录输入上复核，记录见 historical-spectre-crosscheck.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/historical-spectre-crosscheck.json`）：
- `vout` 只在 `[k*0.5 ns, k*0.5 ns + 50 ps]` 内变化：每次过渡从 tick 起动，50 ps 后到位；
- 评分窗外 442 行 `vout` 与递推（低相 `alpha_in` 0.45，高相 `alpha_out` 0.55 且用 tick 前的输入级值，限幅到 `[0, 0.9 V]`，两级从 0 起）的最大差为 0.0 mV；542 行 `phase` 与 `vdd`、`vss` 的最大差为 0.0 mV；
- 时钟穿越在 tick 后 30 ps 与 90 ps；钳位从未触发；第一个低相长 12.03 ns，t = 0 的 tick 是否更新输入级，这次运行看不出来（影响小于 1e-6 V）。
这次运行不属于本题包，只说明历史 gold 在历史台架上的 Spectre 行为，不是本题参考解的 Spectre 结论。

### 同源关系与职责差异

均不重复计数。
- 首批30题：slot 1 的 [v2-spec-024-clocked-sample-and-hold](../../../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) 是单级理想采样保持：每个上升穿越瞬时采下输入并保持，没有采集动态，供电固定。本题有两级、每级按 tick 有限采集，输出只经输出级在高相的 tick 更新改变。v2-spec-024 的行为在本题是错误模型 `single_edge_sampler`（也是历史变异 neg_002）。
- 第二批草稿：[v2-spec-071-acquisition-limited-sample-and-hold](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md)（C055 已并入）是单级获取受限采样保持：全局 tick 网格从 t = 0 起，采样窗由 `sample` 穿越开关，复位在 tick 生效，输入直接是 `vin`。本题沿用同样的 tick 递推和 t = 0 起点，但有两份状态串联、相位互补，输出级的输入是输入级保持的值；没有复位；轨可以移动，各量以 `vss` 为参考；tick 与穿越同刻由 50 ps 的间距排除，而 v2-spec-071 规定同刻时穿越先生效。针对交接的错误候选（`output_reads_vin` 把两级合成一个 071 式的单级，`input_stage_ideal`、`output_stage_ideal` 让一级退化为复制）不是 v2-spec-071 的错误模型。
- R01 已建题：[r01-spec-ideal](../../../r01-sampling-01/tasks/r01-spec-ideal/instruction.md) 是理想跟踪保持（跟踪期瞬时跟随、窗口关闭时冻结，有复位）；[r01-spec-acquisition](../../../r01-sampling-01/tasks/r01-spec-acquisition/instruction.md) 是单级连续有限采集（时间常数随输入变化，有复位）；[r01-spec-aperture-delay](../../../r01-sampling-02/tasks/r01-spec-aperture-delay/instruction.md)（C056-S1）在时钟沿后的孔径时刻理想采样，没有采集动态，不读供电。三题都是单级状态；本题的职责是两份状态在互补相位上交接，各自有限采集、各自保持，并受同一组动态轨限幅。
- R01 并联乒乓（讨论记录 R01G、R01I）：两条支路采同一个输入、轮流向后级提供保持支路。本题是两级串联：第二级只看第一级保持的值，不直接看输入，输出在整个周期只经一次有限交接改变。两者共用“双状态”的名字，不按名称合并（B13 去重关系）。
- 规划中同族、不在本单范围的候选，只写边界：C057-S1（保持漏电下垂）和 C067-S1（下垂前端：孔径、采样时钳位与低相下垂）由另一个子任务在同一批次建，本题不读不依赖；C068-S1（v4:180，跟踪保持切换与累计下垂监控）是单级持续跟踪再保持，另有下垂累计与资格状态；C064-S1（四通道采样读出）与首批 v2-integrate-349-multichannel-readout 同源，不建。U02-I1（共享采集通路的串扰与吞吐预算）把本候选列为比较对象，它的职责是共享通路造成的通道历史污染，本题没有。
- 原56题：没有以 v4:236 或 v3:285 为来源的题。

### 外部来源与许可

- [Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）：
  - §5.10.3.3 `timer`：在起始时刻产生事件，此后每隔一个周期产生一次；
  - §5.10.3.1 `cross`：事件发生在门限穿越之后、在容差框之内；
  - §5.10.2 `initial_step`；
  - §4.5.8 `transition()`：输出从改变目标的事件起动；过渡被打断时按完成规则继续；
  - §4.5.2：每个方程至少要有容差（标准线引用的同一要求）。
- Cadence Verilog-A Language Reference，Product Version 21.1（2022 年 1 月），“Detecting and Using Analog Events”一章第 129、132 页（本机只读副本，见 `runs/spectre-docs-20261008/manuals/` 的 MANIFEST.json；中文转述，不引原文）：`cross` 的缺省时间容差大到几乎总能满足，事件位置实际由表达式容差（一个绝对下限加 reltol 乘信号最大值）决定；`timer` 在起始时刻或紧随其后放一个时间点，此后每个周期放一个。按台架的 reltol 1e-6，0.9 V 时钟的穿越定位误差远小于 1 ps，50 ps 的穿越与 tick 间距足以让各种合理写法在 tick 处判出同一相位。
- GitHub 与 arXiv 检索（2026-10-28，代理 `HTTPS_PROXY=http://127.0.0.1:12639`，命令、stdout、stderr 与退出码存在证据目录 `scratch/search/`）：`dual_track_sample_hold` 只找到 Arcadia-1/behavioral-veriloga-eval 中 v3:285 和 v4:236/1236/736 的各版本副本（gold、starter、负例）；`master slave track and hold extension:va` 只命中一个无关的比较器模型（simra-tech/OpenADA，没有读取）；其余代码与仓库检索都是零命中（退出码 0、空列表）；arXiv 对 master-slave track-and-hold、track-and-hold behavioral model、track-and-hold Verilog-A 都是 0 条结果。没有找到可借用的外部实现。
- 外部来源与许可证另列在 sources.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/sources.json`）。

来源声明分三类：
- 新写：参考解、checker（`tests/verify.py`）、八个用例、合成控制，以及除 `original_v4_236_gold` 外的 44 个校准候选，都是作者按本题合同自写，没有复制外部或历史代码。参考解的结构（`timer` 递推、`cross` 维护相位、`transition` 输出）与原 gold 相同，这是这类模型最常见的写法。
- 仓库内历史资产原样读取的对照：`original_v4_236_gold`。`tests/calibration/mutants.py` 只在仓库内运行时读取 historyref 中 v4:236 的 gold（sha256 `edf53017…feab`，迁入快照 commit `7b5616dc`），原样写出；题包里不存这段文本，在仓库外运行时不生成这个候选。按 [historyref 的使用约定](../../../../../historyref/README.md)，它仅供课题组内部研究、不对外分发；这个对照只用于组内校准，不是参考解或其他候选的来源，也不构成任何许可依据。
- 外部许可代码：无。

记忆污染风险：高。v4:236 的题面与 gold、v3:285 的同一 gold 都在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/236-dual-track-sample-hold) 中，与本仓库副本的 git 对象一致（题面 `7a1cc7d5`，gold `6ec12039`）；该仓库没有 LICENSE 文件。模块名、端口与参数和本题相同。新合同补写的次序、初态和轨处理都与原 gold 的行为一致，所以原 gold 原样提交能通过全部用例（校准候选 `original_v4_236_gold` 在应接受组，旧版开发证据见“待定项”）。原列待用户确认 4，已定（用户 2026-10-29，决定单第 21 项）：接受，合同不为此改，评测报告把这类题单列，给出含与不含它们的两个分数（样板第 3 节）。

## 建模选择

### 建设决定

每条决定都附理由。标“待用户确认”的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目，单列在下一节。（第 2、4、6 条与下一节的四项原标“待用户确认”，用户 2026-10-29 已按推荐定：第 1–3 项为决定单第 20 项，第 4 项为决定单第 21 项；r01-fix-r2 改了各处的状态，理由原文不动。）

1. 接口：模块名 `dual_track_sample_hold` 与六个位置端口照原题，全部为 electrical；`vdd`、`vss` 在 starter 中声明为 inout，`clk`、`vin` 为 input，`vout`、`phase` 为 output。交付 `/app/circuit.va` 单个文件，题面写明可以在文件内定义辅助模块。Deliverable 写明不要求特定的状态变量、事件算子或事件组织；starter 只有 include、模块与端口声明和 TODO。`context_level` 取 `single-module`：合同只规定一个公开模块。保留 `phase`：它是原题接口的一部分，也是工程上常见的相位监视输出，能单独检出相位极性与电平错误。
2. 【已定（用户 2026-10-29，决定单第 20 项）；原标“待用户确认 1”，即待确认清单第 44 项】更新方式：保留原题的 tick 更新，不改成连续 RC 跟踪。理由：登记的 reuse 与 author_work 都以“两套 alpha”“timer 与相位边沿的次序”立题；讨论记录 B13 写明 gold 为 tick 更新、不当连续 R01 core；连续有限采集已由 r01-spec-acquisition 覆盖。每次更新 `v + alpha*(u - v)` 也有电路含义：一个小采样电容每个内部时钟周期与保持电容分享一次电荷，`alpha` 是两者电容比。
3. 每个 tick 的工作次序（author_work 的“timer 与相位边沿的次序”与 brief 问到的新值、旧值）：读 `s`、`u` 与时钟电平；低相时 `a` 更新、`b` 不变，高相时 `b` 用本 tick 之前的 `a` 更新、`a` 不变；然后两级各自限幅到 `[0, s]`。同一个 tick 只有一级更新，所以输出级读到的输入级值总是上一个低相 tick 留下、并经此后各 tick 限幅的值；“同一 tick 输入级刚更新的新值”在本合同里不会出现。题面写明“using `a` as it was before this tick”，把限幅放在更新之后，次序没有歧义。
4. tick 网格：`t_k = k*tick`，k 从 0 起，第一个 tick 在 t = 0（原 gold 的 `timer(0, tick)`，与 v2-spec-071 相同）；模型自己产生 tick，时钟穿越不增、不移、不跳过 tick，也不改存储值；不含 tick 的相位不改变任何一级。净化包留下的“网格起点未写明”由此关闭。`grid-phase` 的第一个上升穿越在 1.145 ns，之前只有 3 个低相 tick（含 t = 0），`vin(0)` 与 `vinit` 相差 0.8 V，缺 t = 0 的 tick 或网格偏半个 tick 都差 100 mV 以上（合成控制）。t = 0 的 tick 是否计入原属待用户确认 3（待确认清单第 46 项），已定（用户 2026-10-29，决定单第 20 项）：计入。
5. 初态：t = 0 时两级都等于 `vinit`，`vinit` 必须在 0 V 与 t = 0 的轨间电压之间。时钟可以从高开始：此时输出级在 t = 0 起跟踪仍是 `vinit` 的输入级，`vout` 保持 `vinit`（`start-high`，`vinit` 0.3 V、`vin(0)` 0.7 V）。这样参考解在 t = 0 不改写任何 transition 目标：低相 tick 只改 `a`，高相 tick 在 `a = b` 时不改 `b`，限幅在合法域内不动作。
6. 【已定（用户 2026-10-29，决定单第 20 项）；原标“待用户确认 2”，即待确认清单第 45 项】轨与参考端（author_work 的“动态电源轨处理”）：`vss` 是本地地，时钟电平、输入 `u`、轨间电压 `s`、两份存储值和 `vout` 都相对 `vss`（原 gold 的写法）。限幅在每个 tick 进行，读本 tick 的 `s`，两级都限，包括本 tick 保持的那一级。合法域要求轨连续变化，任一长度为 `tick` 的区间内 `V(vss)` 与 `s` 各自变化不超过 1 mV。这样“先更新后限幅”与“先限幅再更新”、tick 处限幅与连续限幅、`phase` 跟随瞬时轨与跟随 tick 时锁存的轨，彼此最多差约 1 mV，都在 2 mV 判据之内，评的是“读当时的轨、保持的值也受轨限”这件事，不是限幅的微观次序。`rail-droop` 让 `vdd` 以每 tick 0.78 mV 从 0.95 V 降到 0.70 V，`vin` 为 0.85 V，两级都被下降的轨限住，包括 20 ns 与 15 ns 的低相中保持的输出级；之后 `vss` 以每 tick 0.5 mV 从 0 滑到 -0.08 V，`vout` 在 30 ns 的低相中随 `vss` 平移。
7. 输出：`V(vout) - V(vss)` 显示 `b`，每次改变 `b` 的 tick 之后在 `tedge` 内到位；`phase` 在时钟高时显示 `vdd`、低时显示 `vss`，在每次穿越后 `tedge` 内到位，轨移动时跟随；`tedge` 内的波形不作规定。`tedge` 不超过 `tick/4`，所以每次输出过渡在下一个 tick 前完成，不会被打断。
8. 参数与合法域（原题只写 finite，或 `(0:inf)`、`(0:1]`）：`vth` 0.1 V 至 0.8 V，`tick` 0.25 ns 至 5 ns，`alpha_in`、`alpha_out` 大于 0、不超过 1，`tedge` 10 ps 至 `tick/4`，`vinit` 0 V 至 t = 0 的 `s`；`V(vss)` 在 -0.5 V 至 0.5 V，`s` 在 0.4 V 至 1.5 V；`u` 在 -0.5 V 至 `s + 0.5 V`，可以越过两轨；时钟相对 `vss` 在 t = 0 离 `vth` 至少 50 mV，相邻两次穿越之间离 `vth` 至少 50 mV（2026-10-29 修正 r2），相邻穿越至少 `4*tedge`，每个穿越离任一 tick 至少 50 ps。参考解用 `from` 写出能写成常数的范围。
9. 两级分别检查（author_work 的“分别检查两级保持，不能改成一次复制”）：短低相（2 到 4 个 tick）让输入级没有采完，短高相（1 到 3 个 tick）让输出级没有跟上，两种未完成都会在随后的保持段显示在 `vout` 上；低相中 `vin` 变化检验输出级保持，高相中 `vin` 变化检验输入级保持和输出级不绕过输入级。一级退化为复制的写法在下列用例被拒（合成控制）：`input_stage_ideal` 在 6 个用例（`rail-droop` 输入恒定、`param-endpoints-high` 的 alpha 为 1，除外），`output_stage_ideal` 在 7 个用例，`output_copy_at_rising_edge` 与 `input_sample_at_rising_edge` 在 8 个与 7 个用例，最大误差 66 mV 到 1.5 V。
10. 观察与评分（F01，用户已确认，2026-10-28）：题面写明 checker 实际的观察起点：“除 `vout` 在改变 `b` 的 tick 之后、`phase` 在穿越之后 `1.25*tedge` 内的点外，所有保存点都评分”，checker 不动；到达期限 `tedge` 与评分起点分开写；不评分窗按输出分别开，只在该输出的期望值真正变化时开。期限与评分起点之间到达不区分，这是用户已接受的余量。
   - 迟到负例 `late_arrival_1p3tedge`：`param-override` 的网格 10 ps、`tedge` 55 ps，每个改变 `b` 的 tick 之后 70 ps、每个穿越之后 69.5 ps 有评分行，都落在 `(68.75, 71.5)` ps 内；13 个穿越的迟到全部可见（`phase` 摆幅 0.9 V，误差 25.2 mV），20 次 `b` 变化中 6 次可见（可见门槛约 95 mV 的变化量，最大误差 5.5 mV），其余 14 次变化太小，列为例外。`param-endpoints-high` 的 6 个上升穿越后 1611 ps 有评分行，6 次全部可见（误差 12.8 mV）。窗内对照 `margin_arrival_1p2tedge` 在全部用例通过，这是用户已接受的余量。
   - 其余用例的网格（10 ps、20 ps、2 ps、250 ps）在 `(1.25*tedge, 1.3*tedge)` 内没有行，也没有行恰好落在 `1.25*tedge` 上（生成器用精确有理数断言），迟到在那里按构造看不到，被拒矩阵对这些用例不设预期。`rail-droop` 的 `vss` 斜坡把 2 个穿越移出网格，那里能看到迟到，不作要求。
   - 每个评分点 `V(vout) - V(vss)` 与 `b` 之差、`phase` 与应显示的轨之差都不超过 2 mV，与首批同类规格一致；评分波形步长不粗于 `tedge/4`。
11. 门限触碰（P0 门限触碰卡选项 A，按 brief 执行）：题面写明时钟到达 `vth` 时必定穿过，不触碰后返回、不停在 `vth` 上，t = 0 时离 `vth` 至少 50 mV。checker 用 P0 六题统一的穿越规则：触碰不算穿越，连续两行停在门限上抛出异常、不判分。参考解只对外部驱动的时钟用 `cross()`，不靠 `cross()` 检出内部信号离开零点（第 38 项前提 1）；内部值 `0` 只用于限幅比较，不产生事件。
12. 台架：八个用例，全部按标准线网表约定清单第 3 版写（`runs/standard-line-20261028/netlist-conventions/LIST.md`，sha256 `6a6b17cddf813a8e7c7c4be3d47fed3bac5ab63b23fa207e0f49ff9a0f7713af`）：
   - 每个网表写 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，`tran` 写 `stop`、`maxstep`、`strobeperiod`、`errpreset=moderate`、`strobeoutput=strobeonly`；恒定的轨用 `type=dc dc=…`，其余源用从 t = 0 起、覆盖 `stop` 的 PWL（只写 `type` 与 `wave`）；`save` 列出 checker 读的六个信号；“不必”一档的参数一律不写；`precision` 与 `src_allbrkpts` 不写进用例网表；“PWL 控制在 20 点以内”不执行。容差以标准线给 D1 定的值为起点（`D1-TOLERANCES.md`）：信号在 2 V 以内时每个节点的允许误差约 2e-6 V，比 2 mV 判据小三个数量级。这是选值依据，不是误差保证，实际误差待 Spectre 校准验证。
   - `vin` 与轨的 PWL 拐点都在本用例的 strobe 网格上，时钟拐点在网格上（`param-override` 在 0.5 ps 网格上），每个穿越两侧的两行之间没有时钟拐点，所以 checker 按行线性插值读到的 `vin`、轨与穿越时刻都没有插值误差；checker 不依赖仿真器把输出行放在哪里。Spectre 执行路径在打包时于作业网表末尾追加 `vabenchExecPath options precision="%.17g" src_allbrkpts=yes`（样板 r2.18，标准线结论 SL-EXEC-PATH-v1），用例网表不写这两项，源上也不写 `allbrkpts`；输出只在 strobe 点上，追加与否不改变评分行。
   - 没有保存行恰在穿越上：默认门限的四个用例用 90 ps 时钟边沿，穿越落在两行正中（离行 5 ps）；`param-override` 的穿越在行后 0.5 ps；两个端点用例与 `rail-droop` 的穿越本来就不在行上（生成器断言）。所以 `clk - vss` 没有一行恰好等于 `vth`，checker 的穿越规则里与门限的精确比较不会决定任何穿越（样板 r2.18 的实数 `==` 注意）。
   - 设计余量：穿越到 tick 的间距与相邻穿越间距这两条台架义务都留了余量。下限按 U15 fix-r5 的假设推（保存样本偏离源不超过 1 mV、时刻偏差不超过 1 fs；`clk - vss` 是两个节点之差，按 2 mV 算）：一个穿越最多移动 2 mV/斜率 + 1 fs，一个相位（两个穿越）最多移动两倍；20 ps 边沿上分别是 0.045 ps 与 0.091 ps。上限按样板的量化规定：承担最短相位覆盖的 `param-endpoints-low`，三个短相位（40.44 ps、41.56 ps、41.56 ps）离 `4*tedge` = 40 ps 不超过一个 2 ps 网格步（2026-10-29 修正 r1，审核 R01-07；此前为 43.6 ps 至 44.4 ps），生成器断言下限与上限；`grid-phase` 的最短相位 220 ps（下界 200 ps）不承担最短相位覆盖，见“2026-10-29 修正 r1”一节。各用例穿越到 tick 至少 55 ps。`vin` 中斜率大于 1 V/ns 的段离任一 tick 至少 50 ps，tick 读到的值不取决于仿真器把 tick 放在时间分辨率内的哪一点。
   - `base`（公开兼终评）：默认参数，0.9 V/0 V 静态轨；90 ps 时钟边沿；2、3、4、7 个 tick 的低相与 2 到 10 个 tick 的高相，穿越在 tick 后 65 ps 到 435 ps；`vin` 在低相中变（输出级须保持）、在高相中变（输出级须跟输入级而非 `vin`）、斜坡跨 tick；两次 3 个 tick 的低相中 `vin` 高出 `vdd` 0.2 V、低于 `vss` 0.3 V。
   - `grid-phase`：默认参数，90 ps 时钟边沿；0、1、2、3 个 tick 的相位，多数穿越离最近的 tick 只有 55 ps 到 75 ps；第一个上升穿越在 1.145 ns。
   - `start-high`：`vinit` 0.3 V，时钟在 t = 0 为高，`vin(0)` 0.7 V，90 ps 时钟边沿。
   - `rails-offset`：`vss` 0.25 V、`vdd` 1.05 V，时钟相对 `vss` 在 0/0.9 V 间切换，90 ps 边沿；3 个 tick 的低相中 `vin` 高出 `vdd` 0.4 V 至 0.45 V、低于 `vss` 0.35 V；`phase` 应显示 1.05 V 与 0.25 V。
   - `rail-droop`：`tedge` 100 ps，网格 20 ps；见第 6 条。
   - `param-override`：`vth` 0.3 V、`tick` 0.8 ns、`alpha_in` 0.2、`alpha_out` 0.8、`tedge` 55 ps、`vinit` 0.25 V；360 ps 的时钟边沿让 0.45 V 门限的穿越移动 60 ps，时钟拐点在 0.5 ps 网格上；0 到 5 个 tick 的低相，`vin` 在 0.05 V 与 0.85 V 之间交替；迟到窗见第 10 条。
   - `param-endpoints-low`：下端点 `tick` 0.25 ns、`tedge` 10 ps（实例行写 `tedge=10p`，与参考解 `from` 范围同写法，修正 r1）、`vth` 0.1 V、`vinit` 0 V，最小轨间电压 0.4 V 且 `vss` 取下端 -0.5 V；20 ps 时钟边沿；三个 40.44 ps 至 41.56 ps 的短相位（`4*tedge` 加不到一个网格步）落在两个 tick 之间；网格 2 ps。
   - `param-endpoints-high`：上端点 `tick` 5 ns、`tedge` 1.25 ns（等于 `tick/4`）、`vth` 0.8 V、`alpha_in` 与 `alpha_out` 为 1、`vinit` 等于最大轨间电压 1.5 V，`vss` 取上端 0.5 V；1 ns 时钟边沿；网格 250 ps。
   用例由 build_cases.py（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/build_cases.py`） 生成（精确有理数，共用库 `dth_bench.py`），生成时从最终网表文本解析回参数并断言：实例行的参数覆盖与用例 `params` 一致；参数、轨范围与斜率、`vin` 范围、时钟起点、穿越间距、穿越与 tick 的间距及余量；穿越两侧的保存行之间没有时钟拐点；最后一次穿越之后到 `stop` 至少两个 tick、没有多余的时钟沿；没有保存行恰在评分起点上；`param-override` 的每个事件都有迟到窗内的行。生成记录见 build-cases-report.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/build-cases-report.json`）。
13. checker（[verify.py](tests/verify.py)）只读保存的波形，不读候选源码或参考解：
   - 从记录的 `clk - vss` 用统一穿越规则求穿越；在每个 tick 用最近一次穿越的方向定相位，按行线性插值读 `u` 与 `s`，以 `vinit` 起递推两级并限幅；`vout` 与 `vss + b` 比较，`phase` 与 `vdd` 或 `vss` 比较；
   - 只在一个 tick 使 `b` 变化超过 0.1 mV（题面写明的门限 δ，LIST 第 4.9 版第 0.5 节第 20 条）时，给 `vout` 开不评分窗；t = 0 那一行总按 `vinit` 单独评分（2026-10-29 修正 r1，审核 R01-01、R01-02）；
   - 台架义务出错时抛出异常（无判决，不记候选失败）：缺信号、非有限值、记录不完整、分辨率、参数越界、`tedge` 大于 `tick/4`、轨越界或变化过快、`vin` 越界、`vinit` 不在轨内、时钟起点离门限不足 50 mV、时钟停在门限上、穿越间距不足 `4*tedge`、相邻两次穿越之间离门限不足 50 mV（按保存行判，2026-10-29 修正 r2）、穿越离 tick 不足 50 ps；
   - 不依赖任何仿真器特有的行。共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 与公开入口和首批逐字节相同，公开 checker 副本与私有副本逐字节相同。
14. 参考解按 LRM 与 Spectre 语义自然地写：`@(timer(0, tick))` 递推、`cross()` 在两个方向维护相位标志、`transition()` 驱动 `vout`，`phase` 写成 `V(vdd, vss)` 乘以相位标志的 `transition()`，轨移动时直接跟随。参考解没有为任何 EVAS 版本改写。按样板 r2.18 的三条注意核对：
   - 零边沿 `transition()`：已核对。参考解的两个 `transition()` 都显式写出延迟 0 与上升、下降时间 `tedge`，校准候选同样显式写出（`alt_two_modules` 的内部节点写 1 ps）；台架只有电压源，没有 `transition()`。评分不依赖仿真器缺省的边沿宽度。
   - 实数 `==`：已核对。参考解没有 `==`、`!=`；相位用 `tracks > 0.5`（只取 0 与 1），t = 0 的时钟电平离 `vth` 至少 50 mV；限幅用 `min`、`max`，在恰好相等时两边结果相同。checker 的穿越规则里与门限的精确比较不会遇到恰在门限上的行（上一条）；`b` 是否改变原先用 `!=` 判断，由轨电压的舍入差就能在 t = 0 开出不评分窗、遮住初态错误（审核 R01-01），修正 r1 改用题面写明的 0.1 mV 门限，t = 0 那一行另行单独评分。
   - 直流工作点（FU-01d 更正了样板 r2.18 的说法）：由 vsource 直接驱动的节点在 `initial_step` 和 t = 0 那一行都是逐位精确的值。参考解只在 `initial_step` 里读 `V(clk, vss)`（外部 vsource），用来定初始相位，时钟离 `vth` 至少 50 mV；`vout` 由 Verilog-A 贡献驱动，t = 0 的直流解可能偏 1e-14 量级，远小于 2 mV。checker 对 t = 0 那一行的台架检查（`vinit` 不超过 t = 0 的轨间电压）留 1e-9 V 的余量，只用来盖住记录的轨间电压在浮点相减时的舍入（例如 0.407 − (−0.493) = 0.8999999999999999 对 `vinit` = 0.9）；`param-endpoints-high` 的 `vinit` 恰等于轨间电压（2.0 − 0.5 在 binary64 下恰为 1.5），t = 0 的 tick 不改变 `b`。
15. 平局（TIE-RULE 定稿，sha256 `a4cf0e73…ffa7`）：
   - 第 1 种（不同来源精确同刻）：可能的同刻只有 `cross` 与 `timer`，由“每个穿越离任一 tick 至少 50 ps”在合法域里排除；生成器用精确有理数断言（各用例最小间距 55 ps 到 111 ps）。`initial_step` 与 t = 0 的 tick 不是两种次序：参考解在同一次求值中先执行 `initial_step`，且 t = 0 的 tick 不改写任何 transition 目标（第 5 条）。
   - 第 2 种（事件恰在斜坡终点改写同一 transition）：`vout` 的目标只在 tick 改变，tick 间距不小于 `4*tedge`；`phase` 的目标只在穿越改变，穿越间距不小于 `4*tedge`；不会发生。
   - 第 3 种（过渡终点碰上不改写它的事件）：例如 `vout` 斜坡终点碰上时钟穿越，不是先后之争。
   - 第 4 种（timer 落在时间比较边界）：参考解没有时间比较。checker 的评分窗边界上没有保存行（生成器断言），参考解在评分起点之前早已到位。
   - 第 5 种（不同来源的两个 timer 只差 1 到 64 ulp，TIE-RULE.md `418d542a…`，2026-10-29 补；修正 r1 核对）：参考解只有一个 timer（tick 网格），其余事件是时钟穿越，离任一 tick 至少 50 ps，不适用。
   所以没有第 (ii) 类平局。
16. 校准候选见 [tests/calibration](tests/calibration/README.md)：38 个错误模型、7 个应接受的候选（含余量对照与原 gold 对照），被拒矩阵另存为 `expected.json`，由合成控制生成。覆盖清单在跑完整的旧版矩阵之前冻结，见 coverage.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/coverage.json`）：每项要区分的行为都列出终评用例、VA 候选与 Python 合成控制。
17. 被打断的过渡：不在参考解的合法域内（第 7 条）。只有把 `phase` 电平锁存在 tick 的写法（`alt_latched_span_phase` 与原 gold）会在轨移动时改写正在进行的 `phase` 过渡；按 LRM 4.5.8 的完成规则仍在 `tedge` 内到达，若后端改目标时从当前值重走满 `tedge`，这类写法在 `rail-droop` 被拒，写进 `expected.json` 的 `conditions`。

### 待用户确认（四项都已定，用户 2026-10-29）

下面四项原为“待用户确认”，用户 2026-10-29 已按推荐定：第 1–3 项（待确认清单第 44–46 项）为决定单第 20 项，第 4 项（清单第 47 项）为决定单第 21 项。推荐、另一读法与理由的原文保留，r01-fix-r2 只改状态。

1. **【已定（用户 2026-10-29，决定单第 20 项）】tick 更新还是连续跟踪。** 推荐保留 tick 更新（第 2 条）：两级各按 tick 以 `alpha` 逼近目标。另一读法：改成连续 RC 跟踪（低相 `da/dt = (u - a)/tau_in`，高相 `db/dt = (a - b)/tau_out`，限幅改为连续），按 B13 另写完整合同；那样更接近真实开关电容保持器，原 gold 不能通过（记忆污染降低），但与 r01-spec-acquisition 的连续有限采集重叠，tick 与相位边沿次序这一 author_work 不再存在。
2. **【已定（用户 2026-10-29，决定单第 20 项）】动态轨的处理。** 推荐：每个 tick 读当时的轨，先更新、后限幅，两级都限（含保持的一级），轨每个 tick 至多变 1 mV（第 6 条）。另一读法 A：只限幅本 tick 更新的那一级，保持的电容电荷不受轨影响（`clamp_updated_stage_only` 在 `rail-droop` 会被判对）。另一读法 B：限幅作用在输入上（先把 `u` 限到轨内再采集），存储值不再限幅（`clamp_input_first`）。另一读法 C：合法域只允许静态轨，删去 `rail-droop` 与慢变化条款。
3. **【已定（用户 2026-10-29，决定单第 20 项）】t = 0 的 tick 计入。** 推荐计入（第 4 条，原 gold 与 v2-spec-071 相同）：第一个 tick 在 t = 0，时钟从低开始时它更新输入级。另一读法：第一个 tick 在 t = `tick`（`no_tick_at_zero`），会在 `base`、`grid-phase`、`rails-offset`、`param-override`、`param-endpoints-low` 被拒。
4. **【已定（用户 2026-10-29，决定单第 21 项）】接受原 gold 原样通过。** 推荐接受：合同按工程含义补写，没有为排除公开 gold 而改写；在 SOURCE 和 sources.json 标明记忆污染风险高。另一读法：改动合同使原 gold 不能直接通过（例如改为连续跟踪，或换掉模块名与端口），代价是偏离来源机制或只增加改写成本。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/checks.json`）：
- 单题包装检查与 `scripts/benchmark_workbench.py --check --package`；
- 官方 Harbor 配置解析；
- checker 合成波形控制（synthetic-controls.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/synthetic-controls.json`））：7 个正确模型在 8 个用例全部通过，39 个 Python 错误模型（38 个与 VA 错误候选一一对应，另有 `early_start_0p3tedge`）都至少在一个用例被拒，13 个证据有效性控制都报错、不判分；锁存轨电压且改目标时重走满 `tedge` 的条件模型只在 `rail-droop` 被拒；修正 r1 用改后的 checker 在改后的用例上重跑，判决不变，另加初态与门限控制，见“2026-10-29 修正 r1”一节；
- 旧版 EVAS 0.8.7 冒烟（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；legacy-evas.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/legacy-evas.json`）、legacy-vs-expected.json（`runs/t3-p1-build-20261029/r01-spec-dual-track-hold/legacy-vs-expected.json`））：参考解在 8 个私有用例与公开用例上全部通过，最大误差 0.0 mV，只用 strobe 网格行复判结论不变；起始模型报 `no_continuous_linear_ir`（只有接口，属预期）。38 个 VA 错误候选与 7 个应接受候选各跑 8 个用例，共 360 个条目：有预期的 254 个（198 个应拒、56 个应接受）中 249 个与被拒矩阵一致，1 个不一致，4 个旧版无判决；未列预期的 106 个中 102 个有判决、4 个无判决（审核 R01-09 更正：原先把 `clamp_output_only` 未列预期的 4 个无判决条目也算进有预期的分母，写成 258）。`alt_two_modules` 在 `start-high` 被拒（旧版在 t = 0 的 tick 读内部节点得 0 V，见 `expected.json` 的条件）；`clamp_output_only` 旧版报 `continuous_body_not_lowered`，8 个用例无判决，另做的探针（在 tick 限幅输出，不进题包）被拒的用例与矩阵相同。原 gold 对照 `original_v4_236_gold` 在 8 个用例全部通过。修正 r1 后的计数见“2026-10-29 修正 r1”一节。引用这些通过之前已核对旧版的零点处理：参考解与全部候选只对外部驱动的时钟用 `cross()`，不涉及检出离开零点。此前三轮台架修订（陡输入段移离 tick、两条台架义务加余量、按样板 r2.18 把穿越移出保存行）作废的旧版运行保留在证据目录 `scratch/superseded-r1` 至 `r3`，记录见 checks.json；
- EVAS 02dee32b 阶段 a 至 c：参考解 8 个私有用例与公开用例中，7 个私有用例与公开用例在阶段 c 报已知诊断 `kernel.step_budget`（`source transition proof budget exhausted: slot 2`，NF-01），按样板不再为它做探针；`param-endpoints-high` 完成阶段 c，checker 通过（最大误差 0.0 mV）；起始模型在阶段 a 报 `module requires an analog block or child instances`，属预期；
- 历史 Spectre 对照（见上）；
- Docker 两个镜像实际构建一次并检查。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量；
- Spectre 上记录（样板第 4a 节）：本题合同内没有待发事件，也没有被打断的过渡（tick 与穿越都至少 `4*tedge` 一个，`transition` 延迟为 0），这一项按合同不适用；仍记录 `timer(0, tick)` 在 t = 0 是否触发、它与 `initial_step` 的先后，`cross` 事件在 50 ps 间距下的定位，以及被打断的 `transition()` 的行为（对应 `alt_latched_span_phase` 与 `original_v4_236_gold` 的条件）、t = 0 时跨实例读内部节点的值（对应 `alt_two_modules` 的条件）；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 上面四个原“待用户确认”选择已定（用户 2026-10-29）：第 1–3 项（待确认清单第 44–46 项）为决定单第 20 项，第 4 项（清单第 47 项）为决定单第 21 项，都按推荐定，r01-fix-r2 改了状态；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## 2026-10-29 修正 r1（r01-fix-r1，审核 R01 r1 的处理）

本节**未仿真**：没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。依据是独立审核 `runs/t3-p1-build-20261029/review-r01-r1/astra-review.json`（sha256 `7793e313…6d108`）与主控 brief `runs/t3-p1-build-20261029/briefs/r01-fix-r1.md`，以及总协调 2026-10-29 的补充：标准线网表约定清单第 4.9 版（sha256 `f05138e7…eeed5`）第 0.5 节第 20 条“checker 的变化门限”、平局判据第 5 种情形（TIE-RULE.md `418d542a…b108`）、FU2b 判读（`5691c10e…`）。逐条处理、命令与退出码见 disposition.md（`runs/t3-p1-build-20261029/r01-fix-r1/disposition.md`）。本题涉及 R01-01、R01-07、R01-09、R01-13、R01-14、R01-16，另按第 20 条把门限写进题面。R01-11（共用入口追加执行路径一行、核对日志接受步数）不在本轮：`tests/v2_runtime.py` 是全部题目逐字节共用的文件，待共用入口一轮（execpath-runtime）统一改。

1. **R01-01 与第 20 条：变化门限 δ 与 t = 0 初态。**
   - 题面观察规则改为：使 `b` 变化**超过 0.1 mV** 的 tick 之后 `1.25*tedge` 内的 `vout` 点不评分，不超过 0.1 mV 的变化不开窗，t = 0 那一点总评分。checker 用同一个 δ = 1e-4 V（`abs(lim_b - b) > DELTA`），t = 0 那一行按 `vinit` 单独评分，不受任何不评分窗影响。公开与私有 checker 逐字节相同。
   - δ 的推导（第 20 条，按第 4.10 版的算法重算）：被比较的 `b` 由保存的 `vin`、`vdd`、`vss` 算出。八份终评网表都写了 options 的 reltol 1e-6、vabstol 1e-8 V 和 tran 的 errpreset=moderate，所以瞬态实际用的 reltol = 1e-6 × moderate 的倍数 1 = 1e-6，vabstol 取 options 的 1e-8 V（errpreset 不改它），不用 Spectre 缺省。合法域里 |vin| ≤ 2.5 V、|vdd| ≤ 2.0 V、|vss| ≤ 0.5 V，一侧的噪声带取两条路径中大的那条：(1e-8 + 1e-6×2.5) + (1e-8 + 1e-6×0.5) = 3.02e-6 V（经 `vdd` 限幅的路径为 2.52e-6 V），两侧相加 6.04e-6 V，下界 10 倍为 60.4 µV。合同允许任意小的合法变化（高相的逐步收敛、轨的慢变化），所以门限必须写进题面；上界取题目要检测的最小变化即 atol（2 mV）的一半，1 mV：不开窗的变化不超过 δ，自然的输出过渡在评分点上的误差不超过 δ，仍远小于 2 mV。取 δ = 0.1 mV，在 [60.4 µV, 1 mV] 之内。
   - 用例里名义变化离 δ 不到两边噪声带（6 µV）的有 `rail-droop` 的 0.0958 mV 与三次 0.1015 mV：开窗与否可能随数值噪声变，但正确输出在这些变化上的过渡误差不超过 0.11 mV，判定不依赖开窗与否。
   - 新控制（合成波形，改前、改后 checker 各判一次）：14 个初态控制（审核的两个复现；`vinit` 等于轨间电压 1.5 V 与 0.4 V 时轨精确、上下 1e-12 V、低 0.9 nV、低 1 µV，`vinit` = 0 时 `vss` 上下 1e-12 V；各配正确与错误的初态输出），5 个错误初态由改前通过变为改后被拒，其余判决不变；`vinit` 高出轨间电压 1 µV 两边都报台架错误。4 组门限控制（`b` 变化 0.05 mV、恰为 0.1 mV、刚超过的 0.101 mV、0.2 mV，各配干净输出、窗内 10 mV 瞬态、窗后 10 mV 误差），0.05 mV 与 0.1 mV 的窗内瞬态由改前通过变为改后被拒，其余不变。
2. **R01-07：最短相位的余量上下限。** `param-endpoints-low` 的三个短相位由 43.6–44.4 ps 改为 40.44 ps、41.56 ps、41.56 ps（三个时钟边沿各挪 2 ps 或 4 ps）。下限：一个穿越最多移动 2 mV/(0.9 V/20 ps) + 1 fs = 0.045 ps，一个相位 0.091 ps；上限：一个 2 ps 网格步。两条都写成生成器断言（build_cases_fix.py（`runs/t3-p1-build-20261029/r01-fix-r1/scripts/c061/build_cases_fix.py`），`--variant orig --check` 复现改前字节）。穿越到 tick 至少 61.8 ps，没有行在穿越上或评分起点上。`grid-phase` 的最短相位 220 ps 是 tick 数与相位覆盖的副产物，不承担最短相位覆盖：按 `tedge` 计的门限（例如“短于 4.2*tedge 的相位不算”）由 `param-endpoints-low` 区分，按绝对时间计的门限只会更早暴露。
3. **R01-14：** 实例行 `tedge=0.01n` 改为 `tedge=10p`（参考解 `from [10p:1.25n]` 的写法），生成器同时按文本与按值断言。
4. **R01-09、R01-13、R01-16：** 计数改为两个维度（见上文待定项与 [校准 README](tests/calibration/README.md)）；直流工作点的说法按 FU-01d 改写（上文建设决定第 14 条）；校准 README 开头写明未仿真，旧版段落带完整标签。
5. **样板 r2.29 的核对。**
   - 零边沿 `transition()`：参考解、全部校准候选（含原 gold）与台架里没有省略或写 0 的 rise/fall，都显式写出（`tedge`、其倍数，`alt_two_modules` 的内部节点 1 ps）。按 stop 分档的 w 与“离缺省边沿开始最近的评分时刻”因此都不适用：

     | 用例 | stop | w | 缺省边沿 | 最近的评分时刻 |
     | --- | --- | --- | --- | --- |
     | `base` | 45 ns | 1 ps | 无 | 不适用 |
     | `grid-phase` | 21 ns | 1 ps | 无 | 不适用 |
     | `start-high` | 17 ns | 1 ps | 无 | 不适用 |
     | `rails-offset` | 21 ns | 1 ps | 无 | 不适用 |
     | `rail-droop` | 330 ns | 1 ns | 无 | 不适用 |
     | `param-override` | 28.3 ns | 1 ps | 无 | 不适用 |
     | `param-endpoints-low` | 14 ns | 1 ps | 无 | 不适用 |
     | `param-endpoints-high` | 140 ns | 1 ns | 无 | 不适用 |
   - 最后一行与 stop：checker 取最后一行，不按“时间等于 stop”找行；完整性检查的容差是 stop 的 1e-6（14 fs 起），不是从实测偏移推出的。七个用例的 stop 恰是一个 tick，这些 tick 都不使 `b` 变化超过 δ（`rail-droop` 为 6.7 nV，其余为 0），所以最后一行落在 stop 前后都按同一个 `b` 评分；最后一次穿越到 stop 至少两个 tick，没有要在 stop 处读的值。已核对，不需要改。
   - 网表第 0.5 节：改动的 `param-endpoints-low` 与其余网表按第 4.9 版的条目扫描（扫描时清单文件已是第 4.10 版 `e99f4ddb…`，第 4.10 版只改第 7、20 条、新增第 21 条，扫描的条目不变）（netlist-scan.json（`runs/t3-p1-build-20261029/r01-fix-r1/netlist-scan.json`），含 `list41_scan.py` 的 `check()`）：没有指数加比例符号，比例符号只有 `n`、`p`，后面不接单位；容差都非零；没有 strobetimes；跨行一律没有（每条语句一行，LF）；用例网表不写 precision 与 `src_allbrkpts`；errpreset=moderate（第 10 条：tran 的 reltol 等于 options 的 1e-6）。第 4 条：超过 20 点的 PWL（`rail-droop` 的 `Vclk` 最多 112 点，其余网表的 `Vclk` 最多 42 点）靠执行路径的 `src_allbrkpts=yes`，平段与斜坡的拐角缺省就是断点；checker 只读 strobe 行，不依赖它。已核对。
   - 平局第 5 种情形：参考解只有一个 timer，不适用（上文第 15 条）。FU2b：没有 `idt`、pulse 源或 `$rdist_normal`，不适用。
6. **checker 中判“变了没有”“是否为零”“是否相等”的地方**（第 20 条，逐处清单见 disposition）：`b` 是否改变用 δ；t = 0 那一行按行号单独处理（精确，不是数值比较）；穿越规则里行值与门限的精确比较（六题统一规则，触碰与停留判定）与统计量 `limited_ticks` 的精确 `!=` 属第 20 条范围、不在 R01 发现范围内，没有改，交主控；扫描 B 已核对（2026-10-29，见“2026-10-29 修正 r2”一节第 4 条）；范围检查里的 1e-9 V、1e-12 等余量是不等式的数值余量，不是相等判断。
7. **判决与证据。** 合成控制：原有 47 个模型（7 个正确、1 个条件、39 个错误）在改后用例上，改前与改后 checker 的判决全部相同，也与建题记录相同；`expected.json` 只改 `checker_failure` 的说明（写明 δ 与 t = 0），候选与条件不变（synthetic-controls.json（`runs/t3-p1-build-20261029/r01-fix-r1/c061/synthetic-controls.json`））。旧版：`param-endpoints-low` 重跑 47 次（参考解通过；有预期的 39 个候选条目 38 个一致、`clamp_output_only` 1 个无判决；探针一致），其余 7 个用例的 378 次运行只用改后 checker 重判，判决无一变化（legacy-regrade.json（`runs/t3-p1-build-20261029/r01-fix-r1/c061/legacy-regrade.json`））。合起来：有预期的 254 个条目 249 个一致、1 个不一致（`alt_two_modules` 在 `start-high`，已知的旧版限制）、4 个无判决；未列预期的 106 个中 102 个有判决、4 个无判决；只用网格行重判计数相同（legacy-vs-expected.json（`runs/t3-p1-build-20261029/r01-fix-r1/c061/legacy-vs-expected.json`））。
8. **主控补充（2026-10-29T05:42Z，`runs/t3-p1-build-20261029/briefs/r01-fix-r1.steer-list410.md`，sha256 `94875695…`）的复核**（未仿真；计算与扫描见 steer410-checks.json（`runs/t3-p1-build-20261029/r01-fix-r1/steer410-checks.json`））。依据：清单第 4.10 版（`e99f4ddb…`）、SL-DEC-20261029-05 的补充（`JUDGMENT-W2-S7S12-G400-L0A.md` 第 5 节，`2b6b7d8e…`）、样板 r2.35（`d090ca15…`）。
   - 第 20 条：δ 的下界已按第 4.10 版的算法重算（上文第 1 条），60.4 µV ≤ 0.1 mV ≤ 1 mV，结论不变。题面原有的“轨每 tick 至多变 1 mV”按同一算法下界为 10×2×[(1e-8 + 1e-6×2.0) + (1e-8 + 1e-6×0.5)] = 50.4 µV，也满足。
   - 第 7 条：checker 取最后一行，不按 time == stop 找；完整性容差是 stop 的 1e-6（本题最小的 stop 14 ns 时为 1.4e-14 s），远大于实测偏移上界 3.0e-17 s，也不是从偏移推出的；没有要在 stop 附近读的值。不变。
   - 第 21 条：本题 checker 与本轮工具都不从 spectre.log 取 `$strobe`、`$display`、`$fwrite` 记录：无。共用运行时只在 Spectre 命令行里写 `+log spectre.log`，并把它留作运行文件。
   - cross 返回根：评分依赖 `clk` 穿越的次数（每次穿越翻转 `phase`，并决定其后的 tick 由哪一级采集）。参考解与全部候选的 `cross()` 只写表达式与方向，time_tol 取 Spectre 缺省 1 s（大于 stop），只看 expr_tol；按最宽读法 expr_tol = 1e-9 + max(options reltol, 瞬态 reltol) × max|expr| = 1e-9 + 1e-6 × max|expr|，八个用例中最大 0.80 µV。按精确的 PWL 源逐例求根：参考解的 `V(clk, vss) − vth` 共 161 个根，相邻两根之间 |expr| 的最大值最小为 0.1 V（`param-endpoints-low`，vth = 0.1 V），是 expr_tol 的 1.2e5 倍；候选用到的另三种表达式（`V(clk, vss) − 0.45`、对地的 `V(clk) − vth`、`vss_at_start` 的 `V(clk) − V(vss)(0) − vth`）最小为 0.37 V、0.2 V、0.1 V。都必须报两次，计数可以评分；没有根落在 PWL 折点上。公开用例与私有 `base` 逐字节相同。
   - **合同上的缺口（停下报主控，没有改）：** 本题合法域只要求 `clk` 相邻两次穿越至少相隔 4·tedge、不触碰后返回，没有要求两次穿越之间离 `vth` 多远。一个越过 `vth` 不到 expr_tol（约 1 µV）就返回的 `clk` 是合法输入，这一对根报一次或两次都合 LRM；只报一次时 `phase` 少翻转一次（或两次翻转落在同一时间点），其后 `phase` 与 tick 由哪一级采集都可能与 checker 的期望不同，checker 也不检查这种输入。现有用例都不受影响（最小 0.1 V）。改法（例如合法域加“两次相邻穿越之间，`V(clk) − V(vss)` 离 `vth` 至少 50 mV”，checker 作台架义务检查）要改合同，交主控定。（总协调 2026-10-29 已定照此补上，见“2026-10-29 修正 r2”一节第 1 条。）
   - 一次性 timer（FU-11b、FU-11c）：参考解只有周期 timer `timer(0, tick)`；47 个候选与探针里只有 `grid_restart_at_edges` 用一次性 timer（`tnext = $abstime + tick`），全部文件里没有拿 `$abstime` 与 timer 自己的设定时刻比较的写法：无。
   - transition 的 td（U15）：参考解与全部候选的 td 都是常数 0，没有运行中改 td 的写法：无。

## 2026-10-29 修正 r2（r01-fix-r2）

本节**未仿真**：没有运行 Spectre、EVAS 或模型；合成控制是 Python 波形，旧版结果只重判、不重跑（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）。依据：r01-fix-r1 交主控的合同缺口（r01-fix-r1 处理记录（`runs/t3-p1-build-20261029/r01-fix-r1/disposition.md`）第 9.3 节）与第 20 条遗留（同一记录第 10 节第 3 条）；总协调 2026-10-29 的决定与转达的标准线条件；用户 2026-10-29 对决定单第 20、21 项的答复；扫描 B 报告（report.md（`runs/t3-spectre-wave2-20261029/scan/round-b/report.md`），sha256 `879b3a39e2e22b4f34e0259a21b32d7f9d20cffbcfdca41cb604960083717fed`）。逐处改动、命令与退出码见 r01-fix-r2 处理记录（`runs/t3-p1-build-20261029/r01-fix-r2/disposition.md`）。

1. **合法域补一句（总协调 2026-10-29 定）。** 题面 Legal inputs 的 `clk` 一条，在“不触碰后返回”一句之后加“Between two successive crossings of `vth`, `V(clk) - V(vss)` moves at least 50 mV away from `vth`.”，该条其余句子不动。理由见上文修正 r1 一节第 8 条：原合法域允许越过 `vth` 不到 expr_tol（约 1 µV）就返回的 `clk`，这一对根报一次或两次都合 LRM 5.10.3.1（SL-DEC-20261029-05 的补充），`phase` 的翻转与 tick 由哪一级采集都可能与 checker 的期望不同。补上以后，合法输入相邻两根之间的 |expr| 都远大于 expr_tol，两次都必须报，计数可以评分。建设决定第 8、13 条同步加了这一条。
2. **checker 的台架检查。** 两份 `verify.py`（`tests/` 与 `environment/starter/testbench/`，逐字节相同，sha256 `1b977497c936d759361ac724e06a63a70495472aba8cfb25b33b7ace3e765c0a`，改前 `c0d2f8cb…5a96`）在“穿越间距不足 `4*tedge`”一条之后加一条：用现有的 `crossings()` 规则从保存行求 `V(clk) - V(vss)` 穿越 `vth` 的时刻；对每一对相邻穿越，取两者之间（不含两端）各保存行上 |`V(clk) - V(vss) - vth`| 的最大值，小于 50 mV − 2 mV = 48 mV 时抛出 ValueError（“clk moves less than 50 mV away from vth between successive crossings”）。按 `v2_runtime.py`，`evaluate` 里抛出的 ValueError 记作 checker_error，reward 为空，不算候选的语义失败，与其余台架检查走同一路径。
   - 余量取 2 mV：样板第 3 节的样本偏离规则是每个保存样本可偏离源 1 mV；`V(clk) - V(vss)` 是两个保存节点之差，按 2 mV 算，与建设决定第 12 条、修正 r1 一节第 2 条推穿越余量时同一口径（brief 举的例子是 1 mV，取 2 mV 更宽）。所以极值落在保存行上的合法台架，`clk`、`vss` 各偏 1 mV 也不会被误报，只有明确不到的才报错。反过来，通过检查的台架，相邻两根之间的真实偏离至少 48 mV − 2 mV = 46 mV。
   - 局限：只读保存行。极值落在两个保存行之间时，保存行会低估偏离，低估多少取决于极值附近的斜率，没有上限：合成控制里一个 6 ps 宽、高出 `vth` 60 mV 的尖峰落在两行正中，行上只看到 10 mV，被报台架错误；同样的尖峰落在行上就通过。所以台架的极值要落在平台上，或落在保存行的时刻上；以后新加或改动网表时，用例生成器要断言这一点。越过又返回都在同一个行间隔内的一对穿越，行上看不到，这是穿越提取本来的局限（穿越间距检查也一样），不是本轮新加的。
   - 现有十份网表（8 个私有用例、公开用例与 `visible_test.scs`）都满足：时钟只在两个电平之间切换，相邻两次穿越之间的极值都在平台上，平台上有保存行。按网表在 strobe 网格上求出保存行，191 对相邻穿越的行上最大偏离与精确求值逐对相同（差不超过 1.4e-16 V，row-vs-exact.json（`runs/t3-p1-build-20261029/r01-fix-r2/c061/row-vs-exact.json`））；最小为 0.1 V（`param-endpoints-low`；`param-endpoints-high` 在 binary64 下为 0.09999999999999987 V）。
3. **标准线的条件与核对。** 标准线同意这一句，条件是 50 mV 要大于每份网表最宽的缺省 expr_tol，即 1e-9 + reltol_eff·max|expr|；reltol_eff 计入 errpreset 的倍数（liberal ×10、moderate ×1、conservative ×0.1），不写 errpreset 按 moderate，options 不写 reltol 按 1e-3。主控已对现行 10 份网表核过（核对说明（`runs/t3-p1-build-20261029/mainverify-c061-exprtol/README.md`），脚本 `check_exprtol.py` sha256 `83038ba752cf5ac693d7723c96b4ca9874226d11554a298d8940c6f545af96b8`，输出 `exprtol-check.json` `fec4de16…64ad1`）：10 份网表都写 reltol 1e-6、errpreset moderate，最宽 expr_tol 最大 0.80 µV，50 mV 至少是它的 6.24e4 倍；去掉 options 行的缺省容差对照（reltol 1e-3）至少 62.5 倍；相邻两根之间离 `vth` 最小 0.1 V。本轮没有改网表。改完后用同一脚本对最终题包再核一次，退出码 0，输出 c061-exprtol-final.json（`runs/t3-p1-build-20261029/r01-fix-r2/c061-exprtol-final.json`）（sha256 `fec4de16227b97e1bf3ef056348dd31f43114e700b42ff7dead8a3afa2064ad1`）与主控的输出逐字节相同。按 checker 的 48 mV 判定门槛，通过检查的台架两根之间的真实偏离至少 46 mV，仍是现行网表最宽 expr_tol 的 5.7e4 倍以上、缺省容差对照的 57 倍以上。合同对 `clk` 的电平没有上限，这条条件管的是我们写的网表：以后新加或改动网表，都要用这个脚本再核。
4. **第 20 条遗留：已核对（扫描 B，2026-10-29）。** r01-fix-r1 交主控的两处：穿越规则 `crossings()` 里行值与门限的精确 `==`；统计量 `limited`（`lim_a != new_a or lim_b != new_b`）的精确 `!=`。扫描 B 都定为“已核对”（报告（`runs/t3-spectre-wave2-20261029/scan/round-b/report.md`）第 4 节末“第 20 条 δ 的核对”，逐项理由见 per-task/r01-spec-dual-track-hold.json（`runs/t3-spectre-wave2-20261029/scan/round-b/per-task/r01-spec-dual-track-hold.json`） 的 add_o 一项，sha256 `810b3cd3…52dd`）：前者作用在 vsource 驱动的 `clk − vss` 上，只决定恰在门限的行与台架错误，不改判定；后者只进 `limited_ticks` 计数，不进判决。上文修正 r1 一节第 6 条的状态同步改了。本轮新加的台架检查拿偏离与 48 mV 作有序比较，不是相等判断。
5. **四个“待用户确认”已定（用户 2026-10-29）。** 第 1–3 项（tick 更新、动态轨的限幅、t = 0 的 tick 计入；待确认清单第 44–46 项）为决定单第 20 项，第 4 项（接受原 v4:236 gold 原样通过；清单第 47 项）为决定单第 21 项，都按推荐定。改了的状态行（理由原文不动）：行为依据里讨论记录的“待补”一条与记忆污染一段，建设决定的引言与第 2、4、6 条，“待用户确认”一节的标题、引言与四项，待办里“用户确认上面四个……”一条。题面、参考解与 checker 早已按推荐写入，不再改。
6. **t = 0 的次序：不构成平局，照旧评分（标准线 2026-10-29 判读，总协调转达）。** 问题由扫描 B 提出（报告（`runs/t3-spectre-wave2-20261029/scan/round-b/report.md`）第 10 节第 2 项，另见第 4 节 (f) 项）：t = 0 时 `initial_step` 与 `timer(0, tick)` 同刻，扫描 B 另按“timer 先于 initial_step”的次序算了一遍。标准线的判读，前提是参考解里 `initial_step` 块保持在 timer 块之前：
   - `initial_step` 在 t = 0 的初始解触发，`timer(0, tick)` 不会早于第一个点；两者落在同一时间点时，按源码顺序执行。
   - 参考解的 `initial_step` 块（`solution/circuit.va` 第 23–27 行）写在 timer 块（第 37 行）之前，所以初态一定先于 t = 0 的 tick 设好。
   - 扫描 B 算的“timer 先于 initial_step”那种次序，对这份源码不合规，不是另一种合法读法。
   - tick 落在 0 还是稍后，只影响这个 tick 读 `u` 的时刻；`u` 是连续的，`b` 在第一个 tick 不变（建设决定第 5 条），所以不影响评分。

   候选把 timer 块写在 `initial_step` 块前面、因而结果不同，是候选自身没有保证合同（t = 0 时两级都等于 `vinit`，t = 0 的 tick 从这个初态更新），不算平局。建设决定第 15 条“不是两种次序”的结论与这一判读一致。题面、checker、参考解都不因此改动。
7. **判决与证据（未仿真）。**
   - 合成控制（synthetic-controls.json（`runs/t3-p1-build-20261029/r01-fix-r2/c061/synthetic-controls.json`），脚本 synthetic_r2.py（`runs/t3-p1-build-20261029/r01-fix-r2/scripts/synthetic_r2.py`））：建题的 47 个 Python 模型（7 个正确、1 个条件、39 个错误）在 8 个私有用例与公开用例上共 423 次，改前与改后 checker 返回的整份判决逐个相同；13 个证据有效性控制改前改后都以同一原因报错。新的台架控制（默认参数、10 ps 网格的小台架）：相邻两次穿越之间只离开 `vth` 40 mV 的 `clk`（向上、向下、`vss` = 0.25 V 三种）报台架错误，60 mV 的通过，而且错误输出照样被拒；47.9 mV 报错、48.1 mV 通过（判定门槛 48 mV）；1 µV 的返回（第 1 条的动机）报错；恰为 50 mV 与 48 mV 两个只作平局诊断，不写预期：十进制的这两个电平在 binary64 下离 `vth` 为 0.04999999999999999 V 与 0.04799999999999999 V，前者通过、后者报错，结果取决于舍入。改前的 checker 对这些台架的正确输出都判通过。
   - 旧版重判（legacy-regrade.json（`runs/t3-p1-build-20261029/r01-fix-r2/c061/legacy-regrade.json`），脚本 regrade_r2.py（`runs/t3-p1-build-20261029/r01-fix-r2/scripts/regrade_r2.py`））：建题时的 378 次运行与修正 r1 重跑 `param-endpoints-low` 的 47 次运行，共 425 次，其中 415 次有波形，保存行与只用网格行各判一次，共 830 条记录。改后 checker 与改前的判决（状态、通过与否、最大误差、检查数）无一不同；改前的重判与运行时记录的判决也全部相同。被替换的旧 `param-endpoints-low` 的 46 次运行按它自己的用例记录另算一组，同样无一变化。
   - 改动范围：题面、两份 `verify.py`、本页、校准 README。用例、参考解、`expected.json`、`mutants.py`、task.toml 和共用文件都没改，候选的接受与拒绝矩阵不变。Spectre 上不需要新作业：网表与参考解没改，新检查只读已有的保存行；按 FU-01d，vsource 驱动的 `clk`、`vss` 在 Spectre 的行上逐位等于 PWL 的值，现有台架的平台不会被误报。
