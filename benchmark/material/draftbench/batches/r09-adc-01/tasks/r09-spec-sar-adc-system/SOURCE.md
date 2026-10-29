# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C109-S1，`unit_id` C109，`case_anchor` C109，来源 `src-be0280f398f5`，`primary_ref` C109，动作 S（spec-modeling），家族 R09，优先级 P0，结构难度 H，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 C109-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。登记要求：
- reuse：四位 SAR 试位、保持样本、CDAC 公式和 done 输出；
- author_work：补忙时 start、同刻 start/clk/reset 及 `vss` 非零时的转换参考；固定监测口在试位前后的含义；
- difference：真实模块间的转换反馈，不只是生成试位；
- Grok 意见：采纳系统代表；同源测试台题可作配套，独立的协议检查职责另见 U27。

用户已确认的决定：
- **模块交付（用户已确认，2026-10-27，Q1 选 A）**：保留四个功能模块及顶层的公开接口与职责，由求解者实现并连接；模块内部算法自由；作者补齐各模块的独立合同，并验收模块行为和完整链路；文件数量不作为考察目标。记录在本线讨论记录 `local/research/benchmark-submission-20261025/README.md` 的「Q1：C109是否要求可复用模块交付」一节（不在本工作树，文件 sha256 `562a36df97370ff163d45d81200d104b4a228695982a99e5c037375770c97c19`）。本单 brief 没有提到这一项，建题时按该记录执行。
- **转换参考（用户已确认，2026-10-28，选 A）**：`vss` 为转换下端点、`vref` 为上端点，`DAC = vss + (vref - vss) * code / 16`，要求 `vref > vss`；逻辑高电平仍由 `vdd` 定义；各模块与顶层的参数语义按这一定义统一。决定卡见 C109-vref.md（`runs/t3-p0-pilot-20261027/decision-cards/C109-vref.md`），纸面例（`vss = 0.1 V`、`vref = 0.9 V`）：

  | 输入 | A：上端点 | B：跨度 | 旧公开公式 |
  | --- | --- | --- | --- |
  | 试位码 8 的 DAC 电压 | 0.50 V | 0.55 V | 0.45 V |
  | 样本 0.52 V 的最终码 | 8 | 7 | 9（按旧公式逐位推出） |

  终评用例 `vss-override` 第一个转换正是这个例子，期望码 8；模块用例 `modules-override` 另用 `vss = 0.1 V`、`vref = 1.0 V` 检查 DAC 单独的电平。按跨度理解和沿用旧公开公式的候选只在这两例被拒（合成控制与旧版 EVAS 都如此）。
- **评分起点（用户已确认，2026-10-28，F01 选 A）**：见建模选择第 8 条。

主来源是仓库内的 [v4:342 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/public/instruction.md)，sha256 `60b66750f0a9527ee5b595ce1a25299f8a4a6c48197df943f69f0b13cb654053`，规划登记为 repository-contained；外接盘的历史净化包里没有本题的修订。原题沿用的事实：
- 五个模块与端口：`sar_adc_top(vin, clk, rst, start, code_3..code_0, done, sample_dbg, dac_dbg)`、`sample_hold`、`sar_comparator`、`sar_controller`、`binary_weighted_cdac`，各自的参数表，默认值 `vdd = 0.9 V`、`vss = 0 V`、`vref = 0.9 V`、`vth = 0.45 V`、`tr = 200 ps`；
- start 上升沿武装转换，下一个 `clk` 上升沿采样 `vin`；随后每个上升沿从高位到低位判一位；比较器在保持样本不低于 DAC 时保留试位；判完第 0 位后置 `done` 并保持结果，直到复位或下一次武装；码位输出 `vdd`/`vss`；`sample_dbg` 给出本次转换使用的保持样本；复位清转换状态、码、`done`、`sample_dbg` 和 `dac_dbg`。

原 gold（[sar_adc_top](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/evaluator/solution/sar_adc_top.va)、[sample_hold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/evaluator/solution/sample_hold.va)、[sar_comparator](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/evaluator/solution/sar_comparator.va)、[sar_controller](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/evaluator/solution/sar_controller.va)、[binary_weighted_cdac](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b/evaluator/solution/binary_weighted_cdac.va)）：
- DAC 源码是 `vss + vref * code / 16`，与公开公式 `vref * trial_code / 16` 和"`vss` 是下端点"三者在 `vss` 非零时互相冲突，这就是决定卡的问题；
- 比较器和 DAC 连续求值；控制器对每个 start 都重新武装；`rst` 为高的时钟沿也清零；码输出逐位显示已判定的位；start 时试位码清零，done 时试位码等于结果。

原 checker 是本机 legacy 仓库的 `runners/checkers/v4/task_342.py`（路径 `legacy/behavioral-veriloga-eval/runners/checkers/v4/task_342.py`，sha256 `d916217014fdfa115cee3475326a8544b8f99bc494425690cb45cdd10aea3324`，只读）。它的局限：
- 期望试位和码都按写死的 0.9 V 计算（隐含 `vss = 0`）；
- 只在采样沿和四个判决沿后 650 ps 各读一次 `dac_dbg`、码和 `done`，试位容差 45 mV，保持样本容差 35 mV，码电平容差 0.12 V；
- 台架只有三次转换（0.05、0.43、0.86 V，码 0、7、15），10 ns 时钟，只有上电复位，参数从不改写；每次转换期间 `vin` 不变，所以不保持样本、直接比较实时输入的实现也能通过；没有忙时 start、转换中复位、背靠背转换或 `vss` 非零。

本题不继承它的判据和成绩，这些缺口就是本题要补的。同源的历史形式：
- [v4:1342 修复题](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1342-sar-adc-system-4b-bugfix/public/instruction.md)给出比较器极性反转的错误包；
- [v4:842 测试台题](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/842-sar-adc-system-4b-testbench/public/instruction.md)要求测试台检出五个变异：采样恒为零、DAC 分母 15、比较器极性、首次试位错、`done` 恒低。

本题的 46 个校准候选中（p0-fix-e 加了 `comparator_cross_latch`），只有 `dac_divisor_15` 和 `comparator_polarity` 对应这些历史变异，其余是新的。

历史 Spectre 证据：按样板第3a节查了本机 `legacy/behavioral-veriloga-eval/results/`（含 `_local/v3_skeleton_dual_parity_cache/hidden/` 与各 `v3_spectre_audit*` 目录），没有 SAR ADC 的 Spectre 运行；缓存中唯一的 ADC 项 `025-clocked-adc-quantizer` 是 3 位 flash 量化器，另一道题。参考解的事件语义因此只以 LRM 为据，Spectre 行为列入待办。

外部依据：
- [Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）：
  - §5.10.3.1 `cross()`：事件在阈值穿越之后、时间容差之内触发，t = 0 不产生事件；
  - §4.5.8 `transition()`：过渡被打断时的完成规则，`td` 为传输延迟，同一事件启动的过渡在该时刻还没有移动；
  - §5.10.3.3 `timer()`。
  只引用定义，没有复制文字。
- 本线讨论记录中对 [Arcadia-1/analog-design-bench@972f7cd7](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25) 四位 SAR 题的分析（采样后改变输入、公开预期算法与观察规则）。本题采纳"采样后改变输入"这一实验设计；建题时没有读取其代码，也没有复制。该仓库的许可证字段为 NOASSERTION。

外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r09-spec-sar-adc-system/sources.json`）。GitHub 代码检索（`sar_controller`，扩展名 `.va`）只找到 Arcadia-1/behavioral-veriloga-eval 中 v4:342、1342、842 的各版本副本。没有可复制的宽松许可代码，参考解是作者按新合同自写的。

记忆污染风险：高。原 v4:342 的题面和五个 gold 模块都在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b) 中，与本仓库副本的 git 对象一致（题面 `7c818a65`，`sar_controller` `22b97c75`，`binary_weighted_cdac` `cb3982f3`）。该仓库没有 LICENSE 文件。
- 用户确认保留模块接口（Q1），所以 gold 的模块名、端口和参数表与本题完全相同；
- 推荐的忙时 start 规则（重新武装）也与 gold 一致；
- 原 gold 原样提交只在 `vss` 非零的两例被拒（校准候选 `original_v4_342_gold`，见下）。
- 用户选的端点定义（Q2 选 A）是现在唯一能区分原 gold 的科学条件。

参考解是作者按新合同自写的，结构（`cross` 事件、`transition` 输出、四个模块连成顶层）是这类模型最常见的写法。

同源与职责，均不重复计数：
- 首批30题：
  - [v2-spec-186-sarfend-logic-4b](../../../v2-01/tasks/v2-spec-186-sarfend-logic-4b/instruction.md)（`v4-186`）只让求解者在固定的 DAC 与比较器工程里补 SAR 前端控制器（双相、测试字覆盖、上一轮结果发布）；
  - [v2-spec-002-capacitive-sar-feedback-dac](../../../v2-01/tasks/v2-spec-002-capacitive-sar-feedback-dac/instruction.md)（`v4-002`）只建差分反馈 DAC。
  - 本题要求求解者自己建立采样、试位 DAC、比较与控制的整条因果链，且输入在一次转换中继续变化，再加上四个模块各自的独立行为。
  - 本题的校准候选不是这两题的错误模型。
- 规划中的同族候选都没有建题：
  - C111-S1（SAR Front-End Logic 4b，即 v4:186 的历史修订，P2）是测试/正常两路径的前端控制；
  - U27-T1（SAR 转换协议与内部观测一致性验证，P1，测试动作）负责检出协议违约，v4:842 测试台题的方向归它；
  - C100-S1（比较器双边沿握手 SAR，P1）与 C112-S1（自定时 SAR，P1）是控制协议变体。
- 本批 [r09-spec-pipeline-two-stage](../r09-spec-pipeline-two-stage/SOURCE.md)（C105-S1）是两级流水线 ADC，架构与职责不同，无同源关系。
- 第二批草稿与原56题：除上述两题外，没有以 v4:342 为来源的题；v3-01 的 converter 各题是 DAC 权重模型，没有转换控制。
- R01：采样家族，无同源。
- 本题 `source_group` 取新组名 `v4-342`；SOURCE_GROUPS 中原无此组。`context_level` 取 `multi-module-system`，与首批多模块题一致；交付仍是单个 `/app/circuit.va`，五个模块写在同一文件中。

## 建模选择

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。（第 3、4、5、14 条原标“待用户确认”，用户 2026-10-29 已按推荐定，c109-fix-r6 改了各条的状态，理由原文不动。）

1. 模块交付（用户已确认 Q1）：保留五个模块名、端口顺序和参数表，交付合在一个文件。
   - 每个模块写出独立合同：DAC 只由位输入决定电平，比较器只看两输入之差的符号，采样保持只在 `sample_en` 为高且不在复位中的时钟沿采样，控制器的逐位规则按 `cmp_i` 判定；
   - 终评另有两个模块用例，把四个模块分别单独实例化、各给激励，与顶层用例一起验收；
   - 比较器保留原参数表里的 `vth`，题面写明它在该模块中不起作用。
   - 理由：Q1 要求"作者补齐各模块独立合同，再验收模块行为和完整链路，不能只检查模块名或文件数"；文件数量不作为考察目标，所以沿用样板的单文件交付。
2. 转换参考（用户已确认 Q2）：`DAC(c) = vss + (vref - vss)*c/16`，各模块统一。最终码等于 `floor(16*(x - vss)/span)` 限到 0–15。
   - 低于 `vss` 的样本得 0，高于 `vref` 的得 15；`sample_dbg` 显示原始样本，不限幅。
   - build_cases.py（`runs/t3-p0-build-20261027/r09-spec-sar-adc-system/build_cases.py`） 用独立合同模型逐个核对每次转换的码。
3. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 1”，即待确认清单第 35 项】忙时 start：任何 start 请求都重新武装，进行中的转换被放弃且永不发布。
   - 依据：原文"A rising start request arms a new conversion"没有忙时例外；原 gold 如此；本线讨论记录的建议也是"忙时start建议重新武装"。
   - 用例在武装后、采样沿后以及判完一位、两位、三位时各放了一次重新武装（`busy-reset`），`base` 与模块用例也各有一次。
   - 另一种读法是转换中忽略 start（MCU 内置 ADC 的常见约定）。这种候选（`busy_start_ignored`）在含忙时 start 的四个用例被拒。
   - 推荐重新武装。
4. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 2”，即待确认清单第 36 项】同刻与复位规则写在题面公开：
   - 复位优先：与 `rst` 任一穿越同刻的时钟沿或 start 无效；`rst` 上升立即清零（异步），下降无作用；
   - 与时钟沿同刻的 start 算在该沿之后，采样等到严格的下一个沿；
   - 终评保持这些事件分开，题面同样公开写明：控制输入的穿越离 `clk` 上升沿至少 100 ps；顶层用例中 start 离 `clk` 上升沿至少 `2*tr`，因为 start 经控制器的 `sample_en` 传到采样保持，`sample_en` 要在采样沿前越过 `vth`；start 与 `rst` 的穿越至少相隔 100 ps；顶层用例中 `rst` 放行的时钟沿离此前的 `rst` 上升穿越至少 `2*tr`（2026-10-28 p0-fix-b 增加，见第 14 条）；c109-fix-r6 起，顶层用例中 `rst` 的上升穿越离此前的 `clk` 上升穿越至少 `tr`（见“2026-10-29 修正 r6”一节第 1 条）；
   - 两侧边界都测：控制器用例中 start 在时钟沿前、后 100 ps；顶层用例中 start 在时钟沿前、后 `2*tr`。（p0u17-fix-r4 起离下界都留了设计余量：控制器用例为沿前 150 ps、125 ps，沿后 105 ps、102.5 ps；顶层用例为 `2*tr` 加 50 ps 或 5 ps。见“2026-10-29 修正 r4”一节第 1 条。）
   - 依据：讨论记录要求"start与clk同刻是否让采样等到严格下一沿，也须公开决定，不能通过私自排除同刻输入解决"；这里规则与排除都公开。
   - 另一种读法是终评加入正好同刻的用例。这依赖同一时间点上跨模块事件的执行次序，Spectre 上尚无记录；参考解按源码次序把时钟事件放在 start 事件之前，与公开规则一致。
   - 推荐现在不评正好同刻，Spectre 记录事件次序后再定。
5. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 3”，即待确认清单第 37 项】监测口与输出在试位前后的含义：
   - `dac_dbg = DAC(T)`：复位和每次 start 后为 `vss`，采样沿后为 `DAC(8)`，每个判决沿后为下一个试位，判完第 0 位后为 `DAC(最终码)`，保持到下一次 start 或复位；
   - `sample_dbg` 在采样沿变为原始样本，跨过 start 保持到下一个采样沿，复位时为 `vss`；
   - 码输出逐位显示已判定的位 `R`，start 与复位时清零；`done` 从完成沿保持到下一次 start 或复位；
   - 时序：码、`done`、`sample_dbg` 的期限为 `tr`；`dac_dbg` 的期限为 `2*tr`，因为变化先经控制器的试位输出、再经 DAC 两个模块，各自在 `tr` 内。
   - 依据：原 gold 的行为和原 checker 的检查点一致；原 checker 在每个转换沿读取 `dac_dbg`，期望值同上。
   - 另一种读法是码输出只在 done 时更新、start 时 `dac_dbg` 保持上次结果、或 `sample_dbg` 在 start 时清零。对应候选（`code_only_at_done`、`dac_keeps_final_at_start`、`sample_cleared_at_start` 的合成控制）都被拒。
   - 推荐沿用 gold 一致的定义。
6. 复位期间的 start 不被记住（`start_latched_in_reset` 是错误模型）；`rst` 为高时时钟沿不采样，采样保持在 `rst` 上升时立即清为 `vss`。理由：复位优先，原 gold 如此。
7. 合法域（原题没有）：
   - `vin` 在 `vss - 0.2 V` 到 `vref + 0.2 V`；控制输入在 0–0.9 V，t = 0 时离 `vth` 至少 50 mV，`clk` 从低开始；台架驱动的逻辑输入到达 `vth` 时必定穿过，不触碰后返回（p0-fix-c 按第 38 项的推荐写入，见 p0-fix-c 一节；用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版）；
   - 同一输入相邻穿越至少 100 ps；`clk` 相邻上升沿至少 4 ns（`tr` 最大 1 ns 时，DAC 与比较器在 3·tr 内稳定）；
   - 采样沿前后 100 ps 内 `vin` 变化小于 0.25 mV；
   - 顶层用例中，`rst` 为低的时钟沿离此前每次 `rst` 上升穿越至少 `2*tr`（p0-fix-b，第 14 条）；c109-fix-r6 起另有：每次 `rst` 上升穿越离此前的 `clk` 上升穿越至少 `tr`，只约束上升穿越（见“2026-10-29 修正 r6”一节第 1 条）；
   - 顶层用例的每个样本离 `DAC(1..15)` 至少 3 mV。台架实际余量最小 4 mV（`sweep` 每个 DAC 电平两侧各 4 mV）；
   - 比较器单测中两输入之差 t = 0 时离 0 至少 5 mV，过零至少相隔 1 ns，到达 0 时必定穿过（后一条是 p0-fix-c 按第 38 项写入的）；DAC 单测中同时变化的位同刻穿越（p0u17-fix-r5 起写成穿越相差不超过 1 ps 算同时，见“2026-10-29 修正 r5”一节第 2 条；c109-fix-r6 起为 5 ps，见“2026-10-29 修正 r6”一节第 2 条）；
   - 顶层内部的比较差值（采样保持输出减 DAC 输出）不受这些约束：它由被测模块产生，t = 0 和复位后两侧的目标值都是 `vss`，差值按代数为 0 并停在 0，是合法状态（p0-fix-c，审核 R2-04，见 p0-fix-c 一节第 3 条；求解出的两个节点是否逐位相等没有证明，见 p0-fix-d 一节第 3 条）。合法域不排除零平台后的第一个样本等于或低于 `vss`，这时差值从零平台直接走向负侧（p0-fix-d，审核 R3-01，见 p0-fix-d 一节第 2 条）。p0-fix-e 加了三个终评用例：`zero-plateau-vss`、`zero-plateau-from-below` 测零平台后走向负侧，`zero-plateau-from-above` 测从正侧回到零平台后走向正侧（见 p0-fix-e 一节）；
   - 参数合法域：`vss` −0.5 到 0.5 V，`vref - vss` 0.4 到 2 V，`vdd - vss` 0.5 到 2 V，`vth` 0.2 到 0.7 V 且离 `vss`、`vdd` 各至少 0.1 V，`tr` 10 ps 到 1 ns。
   - 传递特性扫描：build_cases.py 对五组 `(vss, vref)`（含两个参数端点）各取 20001 点，逐位判决的结果单调，处处等于 `floor(16*(x - vss)/span)` 限到 0–15，正好落在 DAC 电平上的点也一致。
   - 3 mV 余量不是为浮点，而是让比较器在相等时的取值和事件定位都不影响判决：严格大于的比较器只在平局处与合同不同，终评因此没有平局。
8. 评分起点（F01）——用户已确认（2026-10-28）：F01 选 A。题面写明实际观察起点，checker 不改：每个输出在其期望值变化后 1.25 倍期限内不评分，即 `1.25*tr`，顶层 `dac_dbg` 为 `2.5*tr`。（p0u17-fix-r5 起为期望值变化超过 δ = 0.1 mV 之后，见“2026-10-29 修正 r5”一节第 1 条。）
   - 所有事件穿越（`clk`、`rst`、`start`、`sample_en`、`cmp_i`、DAC 位输入、比较器输入差的过零）都对齐在输出网格的相位 `0.9*g`。期限为 `tr` 的输出（码、`done`、`sample_dbg` 和各模块输出），评分起点后的第一个点在事件后 `1.275*tr`，即 1.275 倍期限。顶层 `dac_dbg` 的期限是 `2*tr`、不评分窗是 `2.5*tr`，同一相位下第一个点在事件后 `2.525*tr`，即 1.2625 倍期限。p0-fix-b 按审核 F12 改正了这一句：原文把两类输出都写成 1.275 倍期限。
   - 迟到负例 `slow_output_1p3tr` 在八个用例都被拒：合成控制 17–24 mV，旧版 EVAS 17–32 mV（两个新用例都是 17.3 mV）。p0-fix-e 的零平台三例也都被拒：合成控制 17.3–19.5 mV，旧版 EVAS 都是 17.3 mV。p0-fix-e 按换入后的比较器重新生成候选后，旧版只用网格行时前八例为 17.3–23.1 mV；全部行在 `base`、`sweep`、`reset-recovery-long-tr` 上有恰在评分起点的旧版事件行，最大到 46.2 mV，判决不变。
   - 按输出变化逐个统计：台阶不小于可见门槛（码等为 104 mV，`dac_dbg` 为 69 mV）的变化全部被 1.3 倍迟到负例命中，各用例 95/95、171/171、360/360、71/71、96/96、167/167，新用例 `reset-recovery-long-tr` 46/46、`modules-initial` 19/19，零平台三例 4/4、11/11、19/19（p0-fix-e，没有被下一次变化覆盖的变化）。另有少数变化在评分起点前就被同一输出的下一次变化覆盖，没有自己的评分点：
     - `dac_dbg` 在完成沿后或采样沿前 `2*tr` 处遇到 start（`base` 2 次，`sweep` 14 次）。`dac_dbg` 的不评分窗是 `2.5*tr`，比顶层 start 的最小间隔 `2*tr` 长；
     - 控制器用例中时钟沿前 100 ps 的 start（`ct_t3`、`ct_en`，两个模块用例各 2 次）。p0u17-fix-r4 后这次 start 在沿前 150 ps（`modules-default`）与 125 ps（`modules-override`），仍是这 4 次没有自己的评分点；`modules-override` 中它的不评分窗恰在下一次变化处结束，两者之间没有保存行，checker 的评分与挪动前相同。
   - 窗内对照：1.2 倍期限到达的合成输出和 VA 候选 `margin_arrival_1p2tr`（以及 `dac_dbg` 在 2.4·tr 到达）都通过。它们晚于期限、早于评分起点，这是用户已接受的余量。
9. 误差上限 2 mV，对所有输出；正确实现在旧版 EVAS 上误差 0.0 mV。评分波形步长不粗于 `tr/4`。
10. 台架：十一个用例，输出网格 `maxstep = strobeperiod = tr/4`，所有 PWL 拐点都在网格上。`reset-recovery-long-tr`、`modules-initial` 是 p0-fix-b 加的，最后三个零平台用例是 p0-fix-e 加的。p0u17-fix-r4 给前八例里恰在合同下界上的间隔加了设计余量（`base`、`modules-default`、`sweep`、`modules-override`、`reset-recovery-long-tr`），下面描述里的 `2*tr`、100 ps、4 ns 与“正好在下限”是原设计，现值见“2026-10-29 修正 r4”一节第 1 条的表。
    - `base`（公开兼终评，默认参数，8 ns 时钟）：
      - 上电复位里有一个 start 请求和一个时钟沿；
      - 采样 0.60 V 后立即把 `vin` 改为 0.20 V（码 10，讨论记录的纸面例）；完成后 `2*tr` 的 start（码 8，中点上方 5 mV）；判完两位后的忙时 start（第一次永不完成，第二次得 13）；
      - 低于 `vss` 与高于 `vref` 的输入（0 与 15），`sample_dbg` 显示原始样本；
      - start 保持高电平跨过完成沿；判完两位后的复位脉冲及其中的 start；`DAC(10)` 上方 5 mV 的样本；时钟沿后与沿前 `2*tr` 的 start。
    - `modules-default`（公开兼终评，默认参数）：
      - DAC 走遍 16 个码，含多位同时变化；
      - 比较器的 DAC 输入以大幅与 2–10 mV 的差越过样本；
      - 采样保持的 `sample_en` 在沿前、沿后 0.3 ns 变化，慢斜坡输入，复位跨过时钟沿和落在两沿之间，超出范围的输入；
      - 控制器的判决序列 1010、1111、0000，时钟沿前、后 100 ps 的 start，忙时重新武装，判完一位后的复位及其中的 start，完成后保持中的复位，start 保持高电平。
    - `sweep`（默认参数，不规则时钟 4–9 ns）：34 次背靠背转换，样本在每个 `DAC(1..15)` 两侧各 4 mV，外加 0.02、0.88、−0.1、0.95 V；每个采样沿后 1 ns `vin` 偏离 0.3 V；16 个码全部出现。
    - `busy-reset`（默认参数，7 ns 时钟，无上电复位）：在武装后、采样沿后、判完一到三位时重新武装；采样沿后、判完三位后、完成保持中、武装中的复位；覆盖时钟沿的复位及其中的 start；释放后 0.4 ns 的 start。
    - `vss-override`（`vss = 0.1 V`、`vref = 0.9 V`、`vdd = 1.2 V`、`vth = 0.3 V`、`tr = 100 ps`）：决定卡纸面例 0.52 V 得 8；比 `vss` 高 30 mV 的样本；低于 `vss`、高于 `vref` 的样本；只到 0.4 V 的 start、`clk` 和 `rst` 脉冲，只对 0.3 V 门限起作用。
    - `modules-override`：模块用例改为 `vss = 0.1 V`、`vref = 1.0 V`、`vdd = 1.2 V`、`vth = 0.3 V`、`tr = 100 ps`。DAC 位、`sample_en`、start、`cmp_i`、`rst` 各有一个只到 0.4 V 的脉冲。`vref` 不取 0.9 V，是为了让写死 0.9 V 的候选被看出。
    - `reset-recovery-long-tr`（顶层，`tr = 1 ns`，6 ns 时钟，审核 F03）：
      - 0.60 V 的转换（码 10）；
      - start 请求后 750 ps 宽的复位，上升穿越正好在下一个时钟沿前 `2*tr`（复位恢复间隔的下限），该沿处 `vin` 为 0.75 V：控制器已空闲，该沿不采样，`sample_dbg` 保持 `vss`；这次 start 请求在复位前 1.25 ns（p0-fix-c 挪早 250 ps，原为正好 `tr`，见 p0-fix-c 一节第 5 条；2026-10-29 已按用户决定退回，现又正好在复位前 `tr`，见“2026-10-29 修正 r5”一节第 0 条）；
      - 0.30 V 的转换（码 5）；判完一位后在时钟沿前 `2*tr` 复位而放弃的转换；
      - start 请求后、时钟沿前 250 ps 上升并覆盖该沿的复位，该沿处 `sample_en` 仍为高（`rst` 为高，不采样）；
      - 0.85 V 的转换（码 15），以及 `done` 为高时在时钟沿前 `2*tr` 的复位。
    - `modules-initial`（只有 DAC 与比较器，默认参数，审核 F10）：DAC 位输入从码 11 起步（`bit_3`、`bit_1`、`bit_0` 为高），之后经过 9、6、15、0、11、4、13，含多位同时变化；比较器两输入之差从 −0.15 V 起步（t = 0 时 `cmp_o` 为低），之后双向过零五次。
    - 零平台三例（顶层，默认参数，8 ns 时钟，p0-fix-e，审核 R3-01）：
      - `zero-plateau-vss`：空闲时的复位脉冲，start 后一次 `x = vss` 的转换（码 0），完成后还有一个空闲时钟沿。顶层内部比较器两输入从 t = 0 起都是 `vss`，差值为 0，采样沿后直接走向负侧；`sample_dbg` 一直是 `vss`；
      - `zero-plateau-from-below`：0.60 V 的转换判完一位后被复位放弃，差值从负侧回到 0；随后一次 `x = vss` 的转换（码 0），差值再从零平台走向负侧；
      - `zero-plateau-from-above`：0.60 V 的转换（码 10）完成后 start，再在武装中、下一个时钟沿前 3 ns 复位，差值从正侧回到 0；随后再一次 0.60 V 的转换（码 10），差值从零平台走向正侧且 `x >= DAC(8)`。
    前八例由 build_cases.py 生成，生成时断言台架义务，并用独立的合同模型核对每次转换的结果。零平台三例取自 Spectre 小探针 `spectre-P0probe-C109-v1` 的网表，只删去 save 语句里的三个内部名，其余逐字节不变，网表按标准线网表约定清单 v3 的“必须”一档写了容差、`errpreset` 与 `strobeoutput`（p0-fix-e 的 build_zero_plateau_cases.py（`runs/t3-p0-build-20261027/p0-fix-e/scripts/build_zero_plateau_cases.py`））。
11. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：
    - 顶层用例按公开规则从记录的输入推出每次转换、每个输出的变化；模块用例分别推出四个模块的期望；t = 0 的初值必评；
    - 台架义务出错时抛出异常（无判决，不记候选失败）；
    - 只在输出期望值真正改变时开不评分窗；建题时的可见性统计发现最初版本对未变化的码位也开了窗，已改正（p0u17-fix-r5 起采样保持值，即顶层 `sample_dbg` 与模块 `sh_o`、`sh_dbg`，按变化超过 δ = 0.1 mV 判，题面写明；其余期望值由整数状态与参数精确算出，仍精确比较，见“2026-10-29 修正 r5”一节第 1 条）；
    - 穿越提取用六题统一的规则（p0-fix-c，审核 R2-01；p0-fix-b 先按 F02 改成按两侧符号变化识别）：每个保存点与阈值精确比较，恰在阈值上的点不属于任何一侧；相邻两个不在阈值上的点分处两侧时记一次穿越，中间恰有一个阈值点时穿越时刻就是该点，否则按两点线性插值；到达阈值后返回原侧的孤立触碰不是穿越；连续两点停在阈值上违反"不停在 `vth`"（比较器单测为"差值不停在 0"），抛出异常、不判分；记录末尾单个阈值点按到达方向算一次穿越；记录开头的阈值点不生成穿越（起始余量不足本来就是台架错误）；
    - 这条规则只用于外部驱动的台架节点：逻辑输入和比较器单测的两输入之差。顶层内部的比较差值由被测模块产生，checker 不提取它的穿越，也不因它停在 0 报台架错误；顶层期望按记录的输入和理想 DAC 规则（`x >= DAC(T)` 时保留该位）计算，内部比较的对错只通过码、`done`、`sample_dbg`、`dac_dbg` 判分（p0-fix-c，审核 R2-04）；
    - 顶层用例另查复位恢复间隔：`rst` 为低的时钟沿离此前的 `rst` 上升穿越不足 `2*tr` 时抛出异常（p0-fix-b，第 14 条）；c109-fix-r6 起另查：`rst` 上升穿越离此前的 `clk` 上升穿越不足 `tr` 时抛出异常；DAC 单测的同刻门限为 5 ps，相邻都不超过 5 ps、首尾超过 5 ps 的一串位穿越也抛出异常（见“2026-10-29 修正 r6”一节第 1–3 条）；
    - 结果另报统计：转换数、完成、被 start 或复位放弃、码集合、最小码余量等；
    - 不依赖任何仿真器特有行，旧版 EVAS 只用规则网格行重判时结论不变。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
12. 参考解按 LRM 写，没有为任何 EVAS 版本改写：
    - 五个模块；DAC 位输入、`clk`、`rst`、`start` 都用带 1 ps 时间容差的 `cross` 事件，比较器输入差的 `cross` 只放时间点；
    - 比较器按电平判定：`cmp_o` 在每个时间点取 `V(sample_i) >= V(dac_i)`。这是 p0-fix-e 换入的修正版（第 (ii) 类）：换入前的比较器在顶层内部差值的零平台上靠 `cross()` 记状态，按归档 Spectre 的到达规则，差值离开零点不触发事件，合法输入会判错（例如零平台后第一次转换 `vin = vss`，得码 15，合同为 0），Spectre 小探针预读证实了这一点，见 p0-fix-d 一节第 2 条与 p0-fix-e 一节；
    - 控制器中复位、时钟、start 三个事件分开，时钟事件写在 start 事件之前；
    - `transition` 零延迟驱动全部输出；只用标量状态，没有数组、`absdelay`、定时器或待发事件。
13. 校准候选见 [tests/calibration](tests/calibration/README.md)：40 个错误模型、6 个应被接受的候选，其中 `margin_arrival_1p2tr` 是用户已接受的余量，不是正确模型。被拒矩阵另存为 `expected.json`。p0-fix-b 新增 `cdac_initial_bits_zero`、`comparator_initial_high`（只改 `initial_step` 赋值）、`sample_en_cleared_at_next_edge` 与正确候选 `alt_fast_sample_en`。p0-fix-c 修正了 `cdac_bit_order_reversed` 的合成控制（审核 R2-03），它现在在八个用例上都模拟 VA 候选，被拒矩阵去掉了该条目的 `author_synthetic_control_cases`。p0-fix-e 随参考解换入新增错误候选 `comparator_cross_latch`（换入前的比较器），改写 `comparator_polarity`（电平判定取反）、`comparator_initial_high`（保留锁存写法、初值置 1）、`alt_gold_style_continuous`（比较器不放 `cross()` 时间点），其余候选只随比较器文本变化。
14. 【已定（用户 2026-10-29，决定单第 5 项）；原标“待用户确认 4”，即待确认清单第 39 项】顶层复位恢复间隔（2026-10-28 p0-fix-b，审核 F03）：顶层用例中，`rst` 为低的时钟沿离此前每次 `rst` 上升穿越至少 `2*tr`。
   - 问题：原合法域只要求 `rst` 穿越离时钟沿 100 ps。控制器在 `rst` 上升时把 `sample_en` 拉低，期限是 `tr`；`tr` 长、复位短时，下一个时钟沿处 `sample_en` 仍高于 `vth`，采样保持再取一次样，违反顶层"复位后空闲、时钟沿无效"。参考解自身的模块组合就会这样：审核的推导场景（`tr = 1 ns`，复位 3.75–3.875 ns，时钟沿 4 ns）在旧版 EVAS 上复现，`sample_dbg` 变为 0.6 V，修正前的 checker 判失败（误差 600 mV）。
   - 推荐并已写入：公开补上复位恢复间隔。理由：
     - 题面已经按模块链推出顶层的 start 间隔 `2*tr` 和 `dac_dbg` 期限 `2*tr`，复位经同一条 `sample_en` 链路传到采样保持，`2*tr` 与 start 的规则对称；
     - 加上后，满足各自期限的四个模块按题面连接，自然满足顶层合同，符合用户已确认的 Q1（模块内部算法自由，验收模块行为和完整链路）；
     - 各模块单测的合法域不变，参考解不改。
   - 另一种读法：保留原合法域，要求参考解（和求解者）让 `sample_en` 在复位后的首个时钟沿前已低于 `vth`，例如 `sample_en` 的过渡远快于 `tr`。这样题面不变，但只按模块期限实现、按题面连接的模型会在长 `tr`、短复位的顶层用例中失败，等于对模块内部时序加了题面没写的要求。校准候选 `alt_fast_sample_en` 就是这种实现，两种读法下都正确。
   - 终评与校准：新用例 `reset-recovery-long-tr` 在间隔下限处测三次复位（p0u17-fix-r4 后为下限加 9.375 ps）；`sample_en_cleared_at_next_edge`（复位不拉低 `sample_en`、等下一个时钟沿才清）只在这一例被拒；修正后的 checker 对间隔不足的顶层台架抛出异常。
   - 若用户选另一种读法：删去题面这一条和 checker 的检查，把参考解控制器的 `sample_en` 改为快过渡，`reset-recovery-long-tr` 的三次复位挪到时钟沿前一格（250 ps），并把原参考解列为错误候选。（用户 2026-10-29 已按推荐定，这一改法不再适用。）

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r09-spec-sar-adc-system/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制，含参数端点用例；
- 旧版 EVAS 0.8.7 冒烟，含参考解、起始模型和全部校准候选（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）；
- EVAS 02dee32b 阶段 a–c 及两个探针；
- Docker 两个镜像实际构建一次并检查。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量与评分起点后第一个点的实际位置；
- Spectre 上记录跨模块的同刻读取：采样沿上控制器拉低 `sample_en` 时，采样保持在同一事件读到的是否仍为高电平；判决沿上控制器读取的比较器输出是否为上一沿后稳定的值；
- Spectre 上记录 `cross()` 事件的定位精度（参考解时间容差 1 ps），确认它远小于 100 ps 的间隔和 0.25 mV 的 `vin` 静止要求；
- Spectre 上记录 `reset-recovery-long-tr` 中三次 `2*tr` 复位后首个时钟沿处 `sample_en` 的电平，确认参考解在复位恢复间隔下限处不再采样（p0u17-fix-r4 后三次复位在时钟沿前 `2*tr` 加 9.375 ps）；p0u17-fix-r5 起 start 脉冲 B 已退回原位，38.225 ns 处它启动的控制器过渡恰在复位上升穿越上结束，这处第 (i) 类平局一并记录（见“2026-10-29 修正 r5”一节第 0 条）；
- Spectre 上复跑顶层内部比较差值恰为 0 的三种情形（p0-fix-c，审核 R2-04；推导见 p0-fix-c 一节第 3 条）：参考解从零出发（五个顶层用例的 t = 0）；复位回零后再离开（`base` 319.345–340.045 ns，`busy-reset` 153.845–171.045、195.845–213.045、258.845–325.045 ns，`vss-override` 173.704–189.0225 ns，`reset-recovery-long-tr` 93.725–130.225 ns、159.725 ns 到记录结束）；同侧返回（`reset-recovery-long-tr` 39.225–52.225 ns，正→0→正）。记录参考解比较器 `cross()` 在这些零点的事件、平台期间的 `cmp_o`，以及其后第一个判决沿的读数。（p0-fix-e 更新：换入前比较器的零点事件已由探针预读实测；换入后的参考解按电平判定，判决不依赖零点事件，这一项随下面的 D2 校准记录平台前后 `cmp` 的翻转即可。）
- Spectre 上记录 `modules-override` 两处第 (i) 类平局（52.0225 ns、92.1225 ns）的事件（p0-fix-c 一节第 6 条；p0-fix-d 按定稿平局判据复核仍为第 (i) 类）。p0u17-fix-r4 为合法域平局把沿前的 start 挪早 25 ps、把沿后 start 之前的空闲时钟沿挪早 2.5 ps 后，52.0225 ns 的这一处不再存在；92.1225 ns 采样保持的过渡终点碰上另一实例 start（第 3 种情形）仍在，这一项只剩它；
- C109 小探针 `spectre-P0probe-C109-v1`（p0-fix-d，审核 R3-01；本线自用，不进题包）：**已预读**（Spectre 21.1，结果包 `结果包（私有）`，sha256 `2c4e79eb…`；suite v1.5 的 verify_return 核对为 identity-verified，18 个作业 completed，证据 clean）。正式核收待 Spectre 线核对脚本的 r5 审核通过（2026-10-29 已正式核收，执行身份 `spectre-P0probe-C109-v1（结果包 sha256 2c4e79eb7fa60d24…）`，见“2026-10-29 修正 r4”一节的现状）。结论与记录路径见 p0-fix-e 一节第 1 条；网表、用例与清单在 spectre-probe（`runs/t3-p0-build-20261027/p0-fix-d/spectre-probe/README.md`）；
- 换入后的参考解（`solution/circuit.va`，sha256 `917b96e9…`）与新用例（零平台三例）在 D2 按新身份校准：参考解在十一个私有用例与两个公开用例上通过 checker；46 个校准候选按新的 `expected.json` 比对，其中 `comparator_cross_latch`、`comparator_initial_high` 在零平台三例上被拒取决于到达规则（探针预读已证实）。记录每例的 Spectre 用时（探针每例约 60 s，其中 Verilog-A 编译约 57 s）；
- 样板第4a节的待发事件：参考解没有待发事件（`transition` 延迟为 0，也没有定时器），这一项对参考解不适用。Spectre 运行时仍记录：
  - `transition()` 被打断时的完成方式：控制器用例中 start 在时钟沿前 100 ps，`sample_en` 的上升过渡被采样沿打断（p0u17-fix-r4 后 `modules-default` 为沿前 150 ps，`tr = 200 ps` 时仍被打断；`modules-override` 为沿前 125 ps，长于 `tr = 100 ps`，不再被打断）；
  - 校准候选 `alt_delayed_within_tr` 的传输延迟过渡；
  - `alt_gold_style_continuous` 连续求值的比较器与 DAC 在输入穿越后的翻转时刻；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 上面四个原"待用户确认"选择已定（用户 2026-10-29）：第 3、4、5 条（待确认清单第 35–37 项）为决定单第 6 项，第 14 条（p0-fix-b 新增，清单第 39 项）为决定单第 5 项，都按推荐定，c109-fix-r6 改了状态。清单第 38 项（决定单第 4 项，p0-fix-c 已按推荐写入题面，见 p0-fix-c 一节）和清单第 41 项（决定单第 13 项，p0-fix-e 已按推荐 A 写入题面，见 p0-fix-e 一节第 3 条）用户 2026-10-29 已确认：第 38 项为 A 收窄版，第 41 项为 A，题面不再改；
- p0u17-fix-r5 改了 `reset-recovery-long-tr`（start 脉冲 B 退回）与 `busy-reset`、`vss-override`、`modules-initial`（补容差行）四份网表，checker 改了采样保持值的变化门限 δ 与 DAC 位同刻的 `SAME`：这四例的参考解与校准候选在 P0 预校准包里按新字节重跑；其余七例与两个公开用例的网表没有变，已有结果用新 checker 重判即可（见“2026-10-29 修正 r5”一节第 7 条）；
- c109-fix-r6 的 checker 只加了台架义务的检查（复位离时钟沿 `tr`、DAC 同刻 5 ps、DAC 位穿越串），现有用例的判决不变；另有不进 `cases.json` 的附加台架 `reset-tr-after-edge`（复位恰在时钟沿后 `tr`），参考解在 P0 预校准包里跑一次，应在改后的 checker 上通过（见“2026-10-29 修正 r6”一节第 1、6 条）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## p0-fix-b 修正（2026-10-28）

依据铺开六题独立审核 r1（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）。本节只记改了什么、为什么改；每个改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-b 处置记录（`runs/t3-p0-build-20261027/p0-fix-b/disposition.md`）。本题**未仿真**：没有运行 Spectre，旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

- F02（穿越提取）：checker 原先把"到达阈值后返回原侧"的孤立触碰记成一次单向穿越，比较器差值触零、DAC 位或时钟触及 `vth` 都会凭空产生事件，合同正确的波形被误拒。现按两侧实际符号变化识别，规则见建模选择第 11 条。公开与私有 checker 同时改，逐字节相同。外部驱动的终评台架输入没有恰好触及阈值的；顶层内部的比较差值在 t = 0 与复位后恰为 0，是被测模块的合法状态（p0-fix-c 更正：原句没有区分外部输入与内部信号，见 p0-fix-c 一节第 3 条）。旧版存档波形用新 checker 重判，判决全部不变。
- F03（复位恢复）：见建模选择第 14 条，已定（用户 2026-10-29，决定单第 5 项；原记“待用户确认”）。题面合法域加一条，checker 加对应检查，新用例 `reset-recovery-long-tr`，新校准候选 `sample_en_cleared_at_next_edge`、`alt_fast_sample_en`。参考解没有改。
- F09（合成控制对应关系）：`expected.json` 为只在模块分支模拟 VA 行为的三个合成控制加了 `author_synthetic_control_cases` 字段；`sh_samples_at_sample_en_rise` 改用按其立即更新、反馈和独立模块行为写的合成控制 `sh-samples-at-sample-en-rise`，被拒集合与 VA 矩阵一致。VA 矩阵和旧版观测没有删减。
- F10（输入相关初态）：新用例 `modules-initial` 从码 11 和负比较差起步，保留 t = 0 的评分；新错误候选 `cdac_initial_bits_zero`、`comparator_initial_high` 只改 `initial_step` 赋值，只在这一例被拒。
- F12（记录）：建模选择第 8 条分别写明普通输出 1.275 倍期限、顶层 `dac_dbg` 1.2625 倍期限。
- 原有六个用例、公开用例与公开台架逐字节不变；参考解、起始文件、共用运行文件不变。

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-01、R2-03、R2-04 的题包部分与 F02、F09 的剩余部分，主控 2026-10-28 对清单第 38 项的安排，以及 p0-fix-c 的精确有理数平局扫描。R2-04 的决定卡部分由主控改。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解与公开用例、公开台架都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 终点事件（R2-01）。p0-fix-b 的写法丢掉记录末尾单个恰在阈值上的行，终点处到达的事件就没有不评分窗。在修正前的字节上复现：独立 DAC 从码 0 起步，`cb_3` 在最后一行（10 ns）从下方恰到 0.45 V，`cdac_o`、`cdac_dbg` 在这一行立即到 0.45 V，被拒 0.45 V；p0-fix-b 之前的写法接受它。现改为六题统一的穿越规则（第 11 条），这条输出通过，提前 1 ns 改变的输出仍被拒。终点事件照样受间隔约束：与另一位的穿越相隔 55 ps（既不同刻也不足 100 ps）时报台架错误，105 ps 时照常评分。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 【第 38 项，已按推荐写入；用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版】外部驱动的逻辑输入与比较器单测的输入差，到达门限时必定穿过。题面合法输入第一条在“at t = 0 each is at least 50 mV away from `vth`.”之后加一句：“Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”；比较器单测一条加“always crosses 0 when it reaches 0 (it never touches 0 and returns to the same sign)”。“不停在门限上”和起始余量原已写明，不重复；比较器输入差的起始余量仍是原有的 5 mV，没有改成 50 mV。checker 不变。这句不约束顶层内部的比较差值，见第 3 条。另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
3. 顶层内部的比较差值（R2-04）。
   - 顶层的比较器比较采样保持的输出与 DAC 输出。这个差值由被测模块产生，不是台架输入。t = 0 和每次复位后，采样保持为 `vss`，DAC 的试位码为 0、输出也是 `vss`，差值按代数为 0 并停在 0，直到下一个采样沿（节点上是否逐位为 0 没有证明，p0-fix-d 一节第 3 条）。这是合法状态，不报台架错误。
   - 相等时的行为由题面规定：比较器在 `V(sample_i) >= V(dac_i)` 时输出 1，顶层在 `x >= DAC(T)` 时保留该位，所以差值为 0 时比较结果为 1；差值离开 0 以后，为正时是 1、为负时是 0，只由当时的符号决定，与它是不是从 0 出发无关。
   - checker 的边界（第 11 条）：顶层期望按记录的输入和理想 DAC 规则计算，判决沿上的差值就是 `x - DAC(T)`，合法域保证它离 0 至少 3 mV；checker 不提取内部差值的穿越，也不因它停在 0 而不评分。内部比较的对错只通过可观察输出判分。
   - 推导（未仿真，c109-internal-zero.json（`runs/t3-p0-build-20261027/p0-fix-c/evidence/c109-internal-zero.json`））：按参考解的事件链（控制器试位与 `sample_en` 在 `tr` 内线性过渡，DAC 位在试位过 `vth` 时翻转，DAC 与采样保持输出在 `tr` 内线性过渡）精确重建五个顶层用例的内部差值。零平台在 `base` 0–28.045 ns、319.345–340.045 ns，`sweep` 0–3.045 ns，`busy-reset` 0–3.045 ns 与三次复位后，`vss-override` 0–3.0225 ns、173.704–189.0225 ns，`reset-recovery-long-tr` 0–4.225 ns、39.225–52.225 ns、93.725–130.225 ns、159.725 ns 到记录结束，与审核从旧版波形量出的平台一致。只有 `reset-recovery-long-tr` 39.225–52.225 ns 是从正侧到 0 再回正侧；其余复位平台都从负侧进入，向正侧离开（`reset-recovery-long-tr` 最后一段延续到记录结束）；t = 0 的平台都向正侧离开。按两种读法处理精确零（只在符号改变时记事件；归档 Spectre 记录的“到达 0 时按到达方向记一次，离开不记”），参考解比较器在全部判决沿上的状态都与合同一致。差别只在平台期间的内部状态：例如 39.225–52.225 ns 按归档读法为 0，合同为 1；这一段没有判决，不评分。这是推导，不是 Spectre 结论；旧版 EVAS 全部通过也不代表跨后端一致。（p0-fix-d 补：这只覆盖现有五个顶层用例，它们的零平台都向正侧离开或延续到记录结束；零平台后样本等于或低于 `vss`、差值直接走向负侧的合法情形没有覆盖，按到达规则参考解会判错，见 p0-fix-d 一节第 2 条。）
   - 已列入 Spectre 待复跑（见待办）：参考解从零出发、复位回零后再离开、同侧返回。
   - p0-fix-b 一节 F02 一条原写“终评台架没有恰好触及阈值的输入”，没有区分外部输入与内部信号，已更正。p0-fix-b 处置记录中“仿真器的 `cross()` 遇到这种输入是否触发，本线没有记录”一句在原记录里，p0-fix-c 不改原记录，这里更正：归档的 Spectre 21.1.0.509 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 存在，但只覆盖显式 PWL 的零点，不覆盖本题内部 `transition()` 反馈形成的零点。
4. 反序 DAC 的合成控制（R2-03，F09 收尾）。p0-fix-b 的合成控制 `cdac-bit-order-reversed` 初态按正常位序读码、更新按反序记位，`modules-initial` 从 t = 0 起就与 VA 候选不同：码 11（`bit_3`、`bit_1`、`bit_0` 为高）读成 0.61875 V，VA 为 0.73125 V；4.3 ns 第一次码变后合成为 0.61875 V，VA 与合同都是 0.50625 V。它在顶层用例也没有模拟这个候选。
   - 改法：p0-fix-c 的合成控制让位状态照输入记录，只在 DAC 电平公式里反转权重，初态与每次更新一致，顶层与模块分支相同（脚本（`runs/t3-p0-build-20261027/p0-fix-c/scripts/r09-spec-sar-adc-system/synthetic_controls.py`））。它在八个用例都被拒，与 VA 矩阵一致。
   - 新的分析记录 r2-03-cdac-reversed.json（`runs/t3-p0-build-20261027/p0-fix-c/evidence/r2-03-cdac-reversed.json`）：与旧版存档的 VA 波形（八个用例，另加 p0-fix-c 在挪动后的 `reset-recovery-long-tr` 上的新运行）逐行比较稳定评分行，修正后的控制最大差 2.2e-16 V（浮点舍入），p0-fix-b 的控制最大差 1.1 V。t = 0 与第一次码变后的值都与 VA 相同。
   - 所以 `expected.json` 去掉了该条目的 `author_synthetic_control_cases`，校准说明同步改写；VA 被拒矩阵和旧版原始证据都没有改。`sh_ignores_sample_en`、`sh_samples_in_reset` 的部分覆盖声明不变。
5. `reset-recovery-long-tr` 的平局（p0-fix-c 精确有理数扫描）。武装中复位的那次 start 请求（B）在复位上升穿越前正好 `tr` = 1 ns：控制器由它启动的过渡（`sample_en` 上升、试位与码清零）正好在 38.225 ns 的复位上升穿越上结束，两者精确值只差 −22·2⁻⁸³ s；由此 DAC 的过渡终点又与内部 `sample_en` 的穿越同刻。用例要测的是复位恰在下一个时钟沿前 `2*tr`；start 离复位多远不是边界。
   - 定类（主控 2026-10-28 定稿的口径）：两处都是第 (i) 类，迁就 EVAS，不是题目缺陷。checker 的期望只由记录的 `clk`、`rst`、`start` 穿越和 `vin` 算出（`tests/verify.py` 第 252–254 行取穿越，第 286–295 行由 `run_sar` 和理想 DAC 算期望）；38.225 ns 的复位改变 `sample_dbg` 的期望，但只取决于复位的穿越时刻，与它和控制器过渡终点谁先谁后无关。平局时刻落在码位 3、1 与 `done`（37.225 ns 起，到 38.475 ns）、`dac_dbg`（37.225 ns 起，到 39.725 ns）和 `sample_dbg`（38.225 ns 起，到 39.475 ns）的不评分窗内；38.725 ns 的内部同刻只涉及 `dac_dbg`，也在它的窗内。两种次序下参考解的波形相同。合成核对（tie-classification.json（`runs/t3-p0-build-20261027/p0-fix-c/evidence/tie-classification.json`））：在原用例上，合同波形通过；相关输出从平局时刻到窗口结束加 0.25 V 仍通过；窗口结束后加 0.25 V 被拒。
   - p0-fix-d 按标准线定稿的平局判据（TIE-RULE）重新定类，结论仍是第 (i) 类，依据改为逐点核对两种次序：38.225 ns 的复位改写的是 `sample_en` 刚结束的上升斜坡的目标，方向相反，LRM 4.5.8 的中断规则下两种次序的波形相同；试位、码和 `done` 的目标不变，是过渡终点碰上不改写它的事件。上面按“平局时刻落在不评分窗里”的合成核对只看了期望变化的输出（审核 R3-02），由 p0-fix-d 一节第 1 条代替。
   - **第 (i) 类，待用户确认是否退回。** 退回时只恢复 start 脉冲 B 的六个角点时刻（上升穿越 36.975 → 37.225 ns，下降穿越 37.725 → 37.975 ns），保留之后加的全部用例与改动（p0-fix-e 的零平台三例，p0u17-fix-r4 的设计余量）。不要拿 `runs/t3-p0-build-20261027/p0-fix-c/orig/r09-spec-sar-adc-system/tests/cases.json` 整份覆盖：那份只有八例，会删掉零平台三例，也会撤掉 p0u17-fix-r4 的余量。退回脚本、对现行字节应用后的 sha256 与核对见“2026-10-29 修正 r4”一节第 3 条（p0u17-fix-r4 按审核 R4-03 改写本句；原句要求整份退回）。题面推荐 A 的 `instruction.md` 单文件退回是另一回事，见 p0-fix-e 一节第 3 条。2026-10-29 已按用户决定退回（决定单第 1 项），见“2026-10-29 修正 r5”一节第 0 条。
   - 改法：start 脉冲 B 整体提前一个 250 ps 网格步，上升穿越 36.975 ns、下降穿越 37.725 ns，网格相位不变。只挪上升沿会让过渡终点落在原来的下降穿越上，所以下降一起挪。复位、时钟和其余输入不变。生成脚本是 p0-fix-c 的 build_cases.py 副本，断言全部台架义务并用独立合同模型核对结果。
   - 核对：三次复位仍正好在时钟沿前 `2*tr`；转换结果仍为 10、5、15；迟到可见性仍为 46/46，1.3·tr 负例在 36.975 ns 这次变化上超出 17.3 mV，1.2·tr 窗内对照通过。（p0u17-fix-r4 后三次复位在时钟沿前 `2*tr` 加 9.375 ps，其余核对结果不变，见该节。）
6. `modules-override` 的两处平局来自刻意测的边界，没有挪（p0u17-fix-r4 已按合法域平局的裁定挪开，见“2026-10-29 修正 r4”一节第 1 条）。控制器单测的 start 在时钟沿前、后正好 100 ps（合同下限），而本例 `tr = 100 ps`：
   - 52.0225 ns：51.9225 ns 的 start 请求启动的控制器输出过渡，正好在 52.0225 ns 的 `ct_clk`（同一时刻还有 `sh_clk`）上升穿越上结束，精确差 −69/8·2⁻⁸³ s；
   - 92.1225 ns：采样保持在 92.0225 ns 的时钟沿采样，它的输出过渡正好在 92.1225 ns 的 `ct_start` 上升穿越上结束，精确差 443/8·2⁻⁸³ s，这是两个独立实例之间的同刻。
   按主控 2026-10-28 定稿的口径，两处都是第 (i) 类：每个实例的期望只由它自己的输入算出，平局时刻落在相关输出的不评分窗内（控制器各输出 51.9225 ns 起到 52.0475 ns，时钟沿使 `ct_en`、`ct_t3` 另开 52.0225 ns 起的窗；采样保持 92.0225 ns 起到 92.1475 ns，start 使控制器各输出另开 92.1225 ns 起的窗），合成核对同第 5 条。按口径不挪，也不用停下；这两个时间点列为 Spectre 记录项（见待办）。p0-fix-d 按定稿判据复核：52.0225 ns 的时钟沿改写 `ct_en`、`ct_t3` 刚结束的斜坡的目标，方向相反，两种次序波形相同；92.1225 ns 是采样保持的过渡终点碰上另一实例的 start，不是先后之争；仍是第 (i) 类，不挪（p0-fix-d 一节第 1 条）。
   事件与事件同刻的另做了扫描（event-pairs.json（`runs/t3-p0-build-20261027/p0-fix-c/evidence/event-pairs.json`），PWL 拐点不算事件）：同一模块内两个事件同刻的没有；其余是一方不是事件（如 `clk` 下降、`sample_en` 或 `ct_cmp` 的电平读取）、两个独立实例的事件同刻、合同要求同刻的 DAC 位，以及顶层内部同刻翻转的试位位（DAC 处理后的电平与次序无关，checker 按输入事件算 `dac_dbg`），都不是第 (ii) 类。
7. 复核：
   - p0-fix-b 的 F02 对照 13 个在新 checker 上判决不变。
   - p0-fix-b 的合成控制副本：只换 checker 时与存档相比判决与误差 0 项变化；换上新用例后只有 `sample-cleared-at-start` 在 `reset-recovery-long-tr` 的误差由 465 mV 变为 600 mV（仍被拒）。p0-fix-c 的合成控制全部符合预期；与 p0-fix-b 存档相比，只有 `cdac-bit-order-reversed` 在五个顶层用例由通过变为被拒（第 4 条）。
   - 旧版 EVAS：参考解在全部私有与公开用例上通过（10/10，误差 0）；45 个校准候选在 `reset-recovery-long-tr` 上与被拒矩阵逐项一致（25 拒、20 接受）。
   - 建题以来的旧版存档波形（含 p0-fix-b 的 F03 探针）用新 checker 重判，判决与误差 0 项变化。
8. 第 38 项的三个前提（主控 2026-10-28 定的口径，也作复审口径）：
   - 内部恰为零（p0-fix-d 按审核 R3-04 改写，原文删去了由旧版平台和有理数重建推出的 LRM 保证）：
     - 代数：码为 0 时 DAC 的目标值 `vss + (vref - vss)*0/16.0`（`solution/circuit.va` 第 34 行）乘以整数 0 得精确的 0，加到 `vss` 上仍是 `vss`，与采样保持在 `initial_step` 和 `rst` 上升时赋的 `held = vss`（第 74–75 行；p0-fix-e 换入后为第 75–76 行）精确相等。这一点成立。
     - 节点：比较器读的是两个经 `transition()`、由求解器解出的 electrical 节点。它们的差在任何 LRM 允许的求值方式下是否都逐位为 0，没有证明：LRM 按容差判收敛，不保证两个目标值相同的贡献在节点上读出逐位相等；p0-fix-c 的精确有理数模型在过渡结束时直接取目标值，是把待证的性质当作了前提。**未满足，待 Spectre 核对**：小探针保存 `XDUT.held` 与 `XDUT.dac`，打包时加的 `precision="%.17g"` 能看出两者是否逐位相等。（p0-fix-e 补：Spectre 21.1 探针预读中，六个用例、两份参考解的全部平台行上 `XDUT.held − XDUT.dac` 逐位为 0，两列逐位相同；层次名照写取到。这是预读，正式核收待 Spectre 线 r5。）
     - 第 38 项前提 1 对本题的状态（p0-fix-e 更新）：Spectre 21.1 上平台差值逐位为 0（上一条），但 p0-fix-e 换入的修正版按电平判定，不再依赖这一点，符合执行细则。原写“**不成立（现有写法），改法待探针结果**”，说的是换入前的比较器：即使节点恰为零，`cross()` 型比较器在零平台上向负侧离开时，按到达规则也不触发，合法输入会判错（p0-fix-d 一节第 2 条），探针预读证实了判错。
     - 执行细则（主控 2026-10-28 转标准线口径，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。换入前的比较器（原件第 53–58 行）不符合；p0-fix-e 已换入按电平判定的修正版（现第 55–59 行），符合。
     - 判决沿上的差值是 `x - DAC(T)`（`T` 至少为 1），合法域让它离 0 至少 3 mV；按电平判定的比较器在判决沿读到的就是这个差值的符号，与平台上差值是否逐位为 0 无关。
   - 相等规则写成输出行为：题面已按输出写明：比较器在 `V(sample_i) >= V(dac_i)` 时 `cmp_o` 为 1，相等时也是 1，t = 0 时同样按这条规则（`instruction.md` 第 23 行）；采样保持在 t = 0 和复位时为 `vss`（第 25 行）；控制器在 t = 0 和复位时空闲、`T = 0`、`R = 0`、`sample_en` 与 `done` 为低（第 30 行）；顶层在 `x >= DAC(T)` 时保留该位（第 38 行），`dac_dbg` 在复位和每次 start 之后为 `vss`（第 40 行）。换入前（p0-fix-e 之前）参考解的比较器在顶层内部恰为零的差值上用 `cross()`（原件第 54–56 行），依赖的是到达规则：到达 0 时按到达方向记一次事件，离开 0 不记，t = 0 的零由 `initial_step` 取 `>=`。这是 EVAS 自定的约定，与归档的 Spectre 记录一致。p0-fix-c 原写“可以接受”，p0-fix-d 按审核 R3-01 撤回：按这条规则，差值从零平台直接走向负侧时比较器不更新，合法输入会判错（例如零平台后第一次转换 `vin = vss`，得 15，合同为 0），见 p0-fix-d 一节第 2 条。也按这条规则，`reset-recovery-long-tr` 39.225–52.225 ns 从正侧到达 0 时比较器内部为 0（题面规则在相等时为 1）；这段没有判决，`cmp_o` 在顶层不被评分，第 3 条的推导表明全部判决沿与合同一致。p0-fix-e 换入按电平判定的比较器后，这些情形都按相等规则处理（相等时为 1），不再依赖到达规则；题面比较器一条的“事件”也按决定单第 13 项的推荐 A 改写（p0-fix-e 一节第 3 条）。
   - 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。

## p0-fix-d 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r3（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r3/astra-review.json`））的 R3-01 至 R3-04，主控 2026-10-28 的派发与补充：标准线定稿的平局判据（`runs/standard-line-20261028/rules/TIE-RULE.md`，sha256 `a4cf0e73…`，含第 4 种情形）、比较器的改法、本线的 Spectre 小探针。复现脚本、命令与结果，以及改动文件改前、改后的 sha256，见 p0-fix-d 处置记录（`runs/t3-p0-build-20261027/p0-fix-d/disposition.md`）。本轮只改了本文件：参考解、题面、用例、checker 和校准件都没有改。**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 平局（审核 R3-02、R3-03），按定稿判据重扫、定类。
   - 扫描：精确有理数模型按参考解的完整事件链重建：控制器 → 试位位 → DAC 位事件 → DAC 斜坡，采样保持，内部差值到 0、过 0、离开 0，比较器事件 → `cmp` 斜坡 → 控制器在时钟沿读 `cmp`。`transition()` 被打断时按 LRM 4.5.8 的中断规则。网表数值按 binary64 读入，两种算法各扫一遍，此后精确运算。比较器按三种语义各扫一遍：甲，归档 Spectre 的到达规则；乙，只在变号时记事件；修正版的电平判定。修正 c 之前与现行的用例字节都扫。模型在八个用例上与旧版存档的参考解波形逐行相差不超过 2.5e-10 V。
   - 修正 c 记录的 C109 平局 46 项全部重现；新增的都与内部比较器有关，或是不同实例之间的事件对。
   - 定类，逐个列出种类、是否改写同一个 transition、两种次序下评分输出是否不同：
     - `reset-recovery-long-tr` 38.225 ns（修正 c 之前的字节）：复位改写 `sample_en` 刚结束的上升斜坡的目标，方向相反，中断规则以旧终点为起点，两种次序的波形相同；试位、码和 `done` 的目标不变，是过渡终点碰上不改写它的事件。第 (i) 类，已挪，**待用户确认是否退回**（原件在 p0-fix-c/orig/；退回只恢复 start 脉冲 B，办法见 p0-fix-c 一节第 5 条；2026-10-29 已按用户决定退回，见“2026-10-29 修正 r5”一节第 0 条）。同用例 38.725 ns 的 DAC 终点对内部 `sample_en` 穿越不涉及事件，不是平局。
     - 约 40.225 ns（审核 R3-03 补扫；修正 c 前后都有，只在语义甲下出现）：39.225 ns 差值从正侧到达 0，语义甲触发一次 −1，`cmp` 的斜坡在 40.225 ns 结束，与 `clk` 上升穿越的精确差为 −5·2⁻⁸¹ s（binary64 下为相邻数）。时钟沿不改写 `cmp` 的目标，而且控制器在 38.225 ns 复位后空闲，这个沿不读 `cmp`。过渡终点碰上不改写它的事件，第 (i) 类，不挪。
     - `modules-override` 52.0225 ns：`ct_clk` 采样沿改写 `ct_en`、`ct_t3` 刚结束的斜坡的目标，方向相反，两种次序的波形相同；其余输出的目标不变；同刻的 `sh_clk` 属另一实例。92.1225 ns：采样保持的过渡终点碰上另一实例的 start，不是先后之争。都是第 (i) 类，不挪。（p0u17-fix-r4 为合法域平局挪开下界后，52.0225 ns 这一对不再存在，92.1225 ns 仍在，见该节。）
     - 新增的零平台到达（语义甲与电平判定：`base` 319.345 ns，`busy-reset` 153.845、195.845、258.845 ns，`vss-override` 173.704 ns，`reset-recovery-long-tr` 39.225、93.725、159.725 ns）：DAC 或采样保持的斜坡结束时差值恰好到 0，比较器事件由此触发，是过渡终点碰上不改写它的事件，第 (i) 类。
     - 新增的变号事件（语义乙：`base` 340.045 ns，`busy-reset` 171.045、213.045、325.045 ns，`vss-override` 189.0225 ns，`reset-recovery-long-tr` 130.225 ns）：采样沿启动斜坡、差值离开 0 的同一刻记事件，按因果在时钟事件之后；控制器在该沿读到的 `cmp` 两种次序相同，第 (i) 类。
     - 模块用例中不同实例的事件精确同刻（`modules-default` 38 处，`modules-override` 22 处）：把同刻事件按相反的实例次序重算，全部输出差 0，第 (i) 类。
     - `modules-override` 同时翻转、方向相反的 DAC 位，穿越时刻相差 4.6e-27 s 到 3.4e-17 s（11 组，来自 6 位小数的中间电平），落在 `cross()` 的时间容差内：按同一次发生合并处理，或晚的先处理，`cdac_o` 只在不评分窗内最多差 0.143 V，评分时刻差 0，第 (i) 类。
     - 没有事件读值恰在门限上的情形。本题参考解没有 `timer()`，也不读 `$abstime`，第 4 种情形不适用。
   - 结论（p0u17-fix-r4 按审核 R4-01 收窄）：在上面逐项核过的事件次序项里（两个事件精确同刻、事件恰在斜坡终点改写同一 transition、斜坡终点碰上不改写它的事件、timer 落在时间比较边界），C109 没有第 (ii) 类平局，本轮不挪任何输入，也不退回已挪的。这个结论只覆盖事件次序；合同下界上的合法性平局（输入间隔恰在下界上，台架合不合法取决于保存样本与时刻的偏差）不在其内，处理记录见“2026-10-29 修正 r4”一节第 1 条。p0-fix-c 一节第 5、6 条原来的定类依据由本条代替。

2. 零平台直接向负侧离开（审核 R3-01）。
   - 合法域：`vin` 可在 `vss - 0.2 V` 到 `vref + 0.2 V`，`vin = vss` 和低于 `vss` 都合法；最终码 0 合法；3 mV 余量只对 `DAC(1..15)`，样本等于 `DAC(0) = vss` 不受限。
   - 零平台只在保持值为 `vss`、试位码为 0 时出现：t = 0；复位后；样本恰为 `vss` 的转换被 start 打断后；码为 0、样本恰为 `vss` 的转换完成后。平台只在下一个采样沿结束，样本 `x <= vss` 时差值直接走向负侧。
   - 精确推导，17 个合法场景，合成控制都经 checker 判过：
     - t = 0 的平台、`x <= vss`：现有参考解在语义甲、乙下都得码 15，合同为 0；
     - 从负侧进入的平台（判决中复位、start 打断、码 0 完成），`x <= vss`：语义甲下得 15，语义乙正确；
     - 从正侧进入的平台（start 之后、采样沿之前复位，与本题 38.225 ns 的结构相同），`x >= DAC(8)`：语义甲下得 0（0.6 V 应得 10），语义乙正确；
     - 修正版在 17 个场景、两种语义下都给出合同码；现有用例没有这些情形，所以现有参考解在全部现有用例上通过。
   - 结论：按归档 Spectre 的到达规则，现有参考解对合法输入判错，这是参考解在评分后端上的问题，不是 EVAS 的问题。Spectre 在这一结构上的实际事件语义和两个节点是否逐位相等，由小探针实测（p0-fix-e 补：已预读，现有参考解按语义甲判错，平台上两节点逐位相等，见 p0-fix-e 一节第 1 条）。旧版 EVAS 0.8.7 上两种参考解在全部探针用例上都得合同码，层次化保存的内部节点读回全 0，不能代替 Spectre。
   - 修正版（ref-fixed/circuit.va（`runs/t3-p0-build-20261027/p0-fix-d/spectre-probe/ref-fixed/circuit.va`），与 `solution/` 同名同结构；p0-fix-d 时没有换入，p0-fix-e 已逐字节换入）：只改比较器，`cmp_o` 在每个时间点按电平 `V(sample_i) >= V(dac_i)` 给出，`cross()` 只在过零处放时间点；控制器、模块接口、题面和 checker 不变。理由：合同的模块划分里比较器就是“`V(sample_i) >= V(dac_i)` 时为 1”，控制器按读到的 `cmp` 定位；按电平判定后，每个判决沿读到的就是该沿差值的符号（合法域保证离 0 至少 3 mV），与差值是否从零出发、平台上是否逐位为 0、仿真器的零点语义都无关。合成控制：修正版在全部现有用例上的评分输出与现有参考解逐点相同；旧版 EVAS 上它通过全部私有与公开用例。
   - 题面：改为电平判定不要求改合同。比较器一条写“事件是差值穿过 0”，又规定输出只在本模块列出的事件处变化；顶层内部差值离开零平台时，电平规则要 `cmp_o` 变化，而这不是穿越。建议的新文字与另一种读法列为待用户确认项，见 p0-fix-d 处置记录，由主控转总协调；本轮不改题面。（p0-fix-e：已按推荐 A 写入题面，见 p0-fix-e 一节第 3 条；用户 2026-10-29 已确认。）
   - 校准：换入修正版时，`mutants.py` 里依赖比较器原文的三个候选要改写（`comparator_polarity`、`comparator_initial_high`、`alt_gold_style_continuous`），其余 42 个候选文字只随比较器变化；p0-fix-d 的副本生成后，四个比较器候选在旧版 EVAS 上对八个私有用例的判决与 `expected.json` 逐项一致。现有比较器可作新的错误候选 `comparator_cross_latch`，它在现有用例上都通过，要靠新加的零平台用例（如探针的 `vin = vss`）拒绝，且被拒取决于后端的零点语义，`expected.json` 需加条件说明。
   - 实测确认现有参考解判错时，主控另派一轮把修正版换进题包（第 (ii) 类题目修正），同步 `mutants.py`、`expected.json`，并加零平台用例；现有参考解若没错，修正版不采用。（这一轮就是 p0-fix-e，见 p0-fix-e 一节；上一条的校准改动也在其中。）

3. 内部恰为零（审核 R3-04）：见 p0-fix-c 一节第 8 条第一项的改写。代数上码 0 的目标值与 `vss` 精确相等；求解出的两个节点在任何 LRM 允许的求值方式下是否逐位为 0 没有证明，未满足，待 Spectre 核对。第 38 项前提 1 对本题的状态：不成立（现有写法），改法待探针结果。（p0-fix-e 更新：探针预读中两节点逐位相等；换入的修正版按电平判定，不再依赖这一点，见 p0-fix-c 一节第 8 条。）

4. Spectre 小探针 `spectre-P0probe-C109-v1`（本线自用，不进题包）：六个用例，现有参考解与修正版各跑一遍。
   - 必做三例：`vin = vss`、`vss + 10 mV`（对照）、`vss - 10 mV`，都是复位后启动一次转换。
   - 补充三例：从负侧回到零平台后 `vin = vss`（区分语义甲、乙），从正侧回到零平台后 0.6 V，以及 `vss = 0.1 V` 的 `vin = vss`（看非零 `vss` 下两个节点是否逐位相等）。
   - 网表按标准线网表约定清单的“必须”一档写容差、`errpreset`、`maxstep` 与 `strobeoutput`，`precision` 一行打包时再加；内部节点按 Spectre 的层次路径写 `XDUT.held`、`XDUT.dac`、`XDUT.cmp`。
   - 每例在两种语义下的预期码和比较器输出时间线见探针目录的 `predictions.json`。

## 主控补记（2026-10-28）

本节由主控按总协调 2026-10-28 的要求写入，只改本文件。**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 旧版 EVAS 的通过不能当证据。现有参考解在旧版 EVAS 0.8.7 上通过全部用例（私有 8/8，连同公开 10/10，误差 0），在探针六例上也都得合同码。但旧版处理内部差值离开零平台的方式与归档 Spectre 的到达规则不同，效果相当于电平判定，正好掩盖了比较器 `cross()` 在零点上的问题：探针 `c109-probe-vss` 上旧版得 0，按到达规则应得 15（p0-fix-d 一节第 2 条）。所以本文件各处引用的旧版通过结果，只说明参考解在旧版上能运行、checker 能判分，不说明它在 Spectre 上正确；参考解对不对，以 Spectre 探针与 Spectre 校准为准。修正版按电平判定，不依赖零点语义，但它的旧版结果同样只是开发证据。
2. 探针网表已由 Spectre 线核对（2026-10-28），按现状打包，不改。层次化保存名 `XDUT.held`、`XDUT.dac`、`XDUT.cmp` 的写法与 Verilog-A Reference 21.1 第 313–314 页一致（转述：内部节点用“实例名.节点名”）。结构化 Verilog-A 父模块内部的网能否取到，目前还没有 Spectre 记录，由批次 C 的对应项实测。取不到时，平台上两节点是否逐位相等先用顶层 `sample_dbg - dac_dbg` 判，并注明是代用量：`sample_dbg` 与 `held`、`dac_dbg` 与 `dac` 分别由参数相同的两个 `transition()` 驱动（`solution/circuit.va` 第 80–81 行、第 35–36 行）。

## 2026-10-29 修正（p0-fix-e，第 (ii) 类）

依据是 Spectre 小探针的预读与主控 2026-10-29 的派发。改动文件改前、改后的 sha256，复现脚本、命令、退出码与结果见 p0-fix-e 处置记录（`runs/t3-p0-build-20261027/p0-fix-e/disposition.md`）。**未仿真**：本机没有 Spectre，本轮没有运行 Spectre 或模型；探针结果是 Spectre 21.1 预读（正式核收待 r5）；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 依据：探针 `spectre-P0probe-C109-v1` 的 Spectre 21.1 预读，**预读，正式核收待 Spectre 线 r5**。
   - 结果包 `结果包（私有）`，sha256 `2c4e79eb7fa60d245128a653bdcb757461e84f8c0f1ba366a29be3825b833665`。suite v1.5 的 verify_return 核对：identity-verified，18 个作业 completed，证据 clean。记录在 returns-preread-…（本地记录，未公开）：`verify-v1.5.json`，`score/score.json` 与 score.md（本地记录，未公开）。
   - 换入前的参考解：`vss`、`minus10mV`、`reset-from-below-vss`、`vss0p1-vss` 得码 15（合同 0），`reset-from-above-0p6` 第二次转换得 0（合同 10），checker 都判失败；`plus10mV` 得 0、通过。六例与语义甲（归档 Spectre 的到达规则）逐例一致，`XDUT.cmp` 的时间线也一致。
   - 修正版：六例都得合同码，checker 通过。
   - 平台上 `XDUT.held − XDUT.dac` 每行恰为 0；层次名照写取到；保底作业与主体作业的顶层波形逐行相同；没有 AHDL 定义域警告。
   - 总协调的安排：确认判错，就按第 (ii) 类换入修正版，核收后再定稿。
2. 换了什么、为什么。
   - 参考解：`solution/circuit.va` 换成修正版，与 ref-fixed/circuit.va（`runs/t3-p0-build-20261027/p0-fix-d/spectre-probe/ref-fixed/circuit.va`） 逐字节相同（sha256 `917b96e972fdf5e600d3f5190668ee30f6a34c247776ec52ca58f58d6508eb04`），`solve.sh` 不变。只改比较器：`@(cross(V(sample_i) - V(dac_i), 0, 1p));` 只放时间点，`high = V(sample_i) >= V(dac_i);` 每个时间点求一次，输出照旧。理由见 p0-fix-d 一节第 2 条：合同里的比较器就是“`V(sample_i) >= V(dac_i)` 时为 1”，按电平判定后，每个判决沿读到的就是该沿差值的符号，与差值是否从零出发、仿真器的零点语义都无关。
   - 行号：比较器上方的注释由一行变为三行、比较器本身少一行，所以比较器之后的行号加 1。前文各节引用的行号凡未注明的，指换入前的字节（原件在 `runs/t3-p0-build-20261027/p0-fix-e/orig/`）；例如主控补记第 2 条的第 80–81 行现为第 81–82 行，第 35–36 行不变。
   - 校准候选：`tests/calibration/mutants.py` 照 p0-fix-d 的副本改写依赖比较器原文的三个候选（`comparator_polarity` 改为电平取反；`comparator_initial_high` 保留锁存写法、初值置 1；`alt_gold_style_continuous` 去掉比较器一段后同原来），新增错误候选 `comparator_cross_latch`，即换入前的比较器。生成的 46 个候选与 p0-fix-d 副本的输出逐字节相同。
   - 用例：`tests/cases.json` 末尾追加三个零平台私有用例，前八例逐字节不动：

     | 用例 | 探针用例 | 零平台情形 | 对应的 Spectre 作业与预读结果 |
     | --- | --- | --- | --- |
     | `zero-plateau-vss` | `c109-probe-vss` | t = 0 起的平台，之后 `x = vss`，差值走向负侧 | 修正版：主体作业 `ref-fixed-c109-probe-vss` 与保底作业 `top-only-fixed-c109-probe-vss` 都得码 0、checker 通过；保底作业的网表就是本用例网表加 precision 一行，逐字节核对相同。换入前的参考解两作业都得 15、失败 |
     | `zero-plateau-from-below` | `c109-probe-reset-from-below-vss` | 复位使差值从负侧回到 0，之后 `x = vss`，差值走向负侧 | 修正版 `ref-fixed-c109-probe-reset-from-below-vss` 得 0、通过；换入前的参考解得 15、失败 |
     | `zero-plateau-from-above` | `c109-probe-reset-from-above-0p6` | 武装中复位使差值从正侧回到 0，之后 `x = 0.60 V`，差值走向正侧 | 修正版 `ref-fixed-c109-probe-reset-from-above-0p6` 两次都得 10、通过；换入前的参考解第二次得 0、失败 |

     - 网表从探针用例取，save 语句只删去 `XDUT.held`、`XDUT.dac`、`XDUT.cmp` 三个名字，其余逐字节不变：题目只规定四个模块与顶层的公开接口，顶层内部的网名不是合同，终评网表不能保存它们。后两例在探针里只有带三个内部名的主体作业，网表只差 save 一行；三个必做用例的主体与保底作业顶层波形逐行相同。
     - 用例沿用题包的字段，探针专用字段（`timeout_s`、`probe_*` 等）不带入，单例超时按 `tests/v2_runtime.py` 的缺省 120 s。
     - 没有加 `plus10mV`、`minus10mV`、`vss0p1-vss`：在六个探针用例上跑全部合成控制与精确模型，这三例拒绝的候选都已被现有十一例拒绝（`minus10mV`、`vss0p1-vss` 对两个锁存候选的判决与 `zero-plateau-vss` 相同，另外只多拒已在别处被拒的 `sample_clamped_at_vss`、写死参数与端点读法；`plus10mV` 是对照，不拒任何锁存候选）。每例在 Spectre 上约 60 s，其中 Verilog-A 编译约 57 s（探针实测）。非零 `vss` 下两节点是否逐位相等，探针预读已经回答。
   - `expected.json` 与校准说明：新用例并入被拒矩阵。`comparator_cross_latch` 在零平台三例应拒，`conditions` 写明它被拒取决于仿真器在离开零平台时不触发 `cross()`（到达规则），Spectre 21.1 探针预读已证实；旧版 EVAS 0.8.7 上它通过，是被旧版零点处理掩盖（样板 r2.16 第 4 节第 4 条）。`comparator_initial_high` 保留锁存写法，在零平台三例按同一条件被拒；`sample_en_cleared_at_next_edge` 也在 `zero-plateau-from-above` 被拒。其余候选在新用例上的预期逐项写在校准说明的表里。`comparator_reads_live_vin` 改用忠实的合成控制 `comparator-reads-live-vin`：原控制让 `sample_dbg` 跟随 `vin`，在两个复位零平台例上会多拒。
3. 【用户 2026-10-29 已确认（选 A），决定单第 13 项，即待确认清单第 41 项】题面按推荐 A 写入两处：
   - 比较器一条，原文：“An event is a crossing of `V(sample_i) - V(dac_i)` through 0.”；现为：“An event is any change of whether `V(sample_i) >= V(dac_i)`: a crossing of the difference `V(sample_i) - V(dac_i)` through 0, the difference reaching 0 from below, or the difference leaving 0 toward negative values. In tests of the comparator only crossings occur.”。与决定单的文字相比，只在第一个“the difference”后补了差值的写法，含义不变。
   - 顶层一条的第一个要点（定义 `x` 的那一条）末尾加一句：“Inside the top module both comparator inputs are `vss` at t = 0 and after a reset, so their difference is 0 there and `cmp_o` is 1; at the next sample edge the difference leaves 0, toward negative values when `x <= vss`.”。放在这里是因为 `x` 在这一条定义，行号也不变。
   - 理由：原文“事件是差值穿过 0”与全局的“输出只在本模块列出的事件处变化”合起来，离开零平台就不算事件，而顶层的电平规则要求 `cmp_o` 此时变化，题面字面有矛盾。新文字与按电平判定的参考解一致，现有的 `cross()` 锁存写法明确不合规；模块单测的台架只有过零，判分不变。
   - 另两种读法：B 维持现状，靠顶层“`x >= DAC(T)` 时保留该位”判分，题面字面有矛盾，按“事件即过零”写出 `cross()` 锁存比较器的求解者会在新用例上失败；C 缩合法域，要求零平台后第一个样本高于 `vss` 至少 3 mV，放弃复位后第一次转换“低于 `vss` 得 0”的覆盖，不推荐。
   - 退回办法：用户若选 B，`instruction.md` 逐字节退回到本轮改前（原件 `runs/t3-p0-build-20261027/p0-fix-e/orig/r09-spec-sar-adc-system/instruction.md`，sha256 `0ff86ae504be4db37dea2035277ee0b7c917b020537402d5acf5a835a75b9aaa`），参考解仍用修正版。公开 starter 里没有同样的句子，没有改。（用户 2026-10-29 选 A，这一退回办法不再适用。）
4. 第 38 项前提 1 对本题的状态：Spectre 21.1 上平台差值逐位为 0（探针预读），但修正版按电平判定，不再依赖这一点，符合执行细则。p0-fix-c 一节第 8 条已同步。
5. 开发检查（命令、退出码与结果见处置记录）：
   - 精确模型（p0-fix-d 的 `c109_model.py`）：修正版在前八例与两个公开用例上的评分输出与换入前的参考解在语义甲、乙下逐点相同，差 0，与 p0-fix-d 的结论逐项相同；在零平台三例通过。换入前的参考解在语义甲下三例都失败，语义乙下只有 `zero-plateau-vss` 失败。
   - 与 Spectre 预读波形对照（同一激励的作业，逐行比较评分输出）：修正版的模型波形在评分行上与 Spectre 差 0，全部行最大差 2.45e-7 V（不评分窗内的斜坡采样）；checker 用新用例的记录在 Spectre 波形上判修正版通过（误差 0）、判换入前的参考解失败（0.9 V），后者与语义甲的模型一致。
   - 合成控制：全部现有合成控制在前八例与 p0-fix-c 的存档逐项相同；新用例上 1.3·tr 迟到负例被拒、1.2·tr 窗内对照通过，可见台阶的输出变化全部命中（4/4、11/11、19/19），每次变化后的第一个评分点在 1.275 倍期限（`dac_dbg` 1.2625 倍），严格落在评分起点与迟到时刻之间。
   - 台架：从最终网表精确核对合法域与台架义务、用例 `params` 与网表实例覆盖一致（都为空）、网表约定（清单 v3 的“必须”一档，precision 不写）；`zero-plateau-vss` 完成后有一个空闲时钟沿（`done_one_clock` 靠它被拒），其余两例最后一拍就是完成沿，最后一拍到 stop 都是 3.955 ns，每个输出的最后一次变化之后都有评分行。
   - 平局（TIE-RULE，含第 4 种）：零平台三例在两种 binary64 读法、三种比较器语义下都没有第 (ii) 类，不挪任何输入；参考解没有 `timer()`，也不读 `$abstime`。
   - 旧版 EVAS 0.8.7（旧版开发证据，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑；`legacy_case.py`，标签 p0-fix-e）：参考解在十一个私有用例和两个公开用例上都通过，全部行与只用网格行都是 13/13；起始模型在两个公开用例上不能仿真（模块没有 analog 块），照实记录。46 个候选在十三个用例上共 598 次运行，与 `expected.json` 对照，全部行与只用网格行各 592 项一致、6 项不一致。不一致的 6 项全是 `comparator_cross_latch` 与 `comparator_initial_high` 在零平台三例上旧版通过，是旧版零点处理的掩盖（样板 r2.16 第 4 节第 4 条），不是矩阵或 checker 的问题；Spectre 预读已证实换入前的比较器在同样的激励上判错。没有只因旧版特有输出行而改变的判决。修正版的旧版通过不受这种掩盖影响，因为它按电平判定，但仍只是开发证据。
   - 结构与 Docker：`python3 -B scripts/benchmark_workbench.py --check --package <题包>` 退出码 0（implementation static checks passed）；两个镜像各实际构建一次（标签 p0-fix-e），七项检查全部通过，验证镜像里装入的参考解 sha256 为 `917b96e9…`。
6. 运行时间（交主控）：探针每例在 Spectre 上约 60 s，其中 Verilog-A 编译约 57 s（每个用例在新的工作目录里重新编译）。按此估计，十一个私有用例约 11 分钟，超过 `task.toml` 的 `[verifier] timeout_sec = 600`；原八例约 8 分钟。运行时仍在 `pending`，本轮不改 `task.toml`。

## 主控补记（2026-10-29，验证超时）
- 探针在 Spectre 21.1 上实测（预读，正式核收待 Spectre 线 r6）：18 个作业中位 60.6 s、最长 69.1 s，其中 Verilog-A 编译约 57 s，每个用例在新的工作目录里重新编译。
- 十一个私有用例因此约 11–13 分钟，超过原来的验证超时 600 s。主控把 `task.toml` 的 `[verifier] timeout_sec` 从 600 改为 1800。只改运行时限，合同、用例与评分都不变。
- 单例超时仍是 `tests/v2_runtime.py` 的缺省 120 s，是每例实测用时的 1.7 倍以上。
- 让用例共用编译结果要改共用评分运行时，不在本题处理。
- 改前原件在 runs/t3-p0-build-20261027/mainverify-p0-fix-e/orig/。

## 2026-10-29 修正 r4（p0u17-fix-r4，第 (ii) 类）

依据：P0 两题增量合审 r4（astra-review.json（`runs/t3-p0-build-20261027/review-p0u17-r4/astra-review.json`），sha256 `a15a8704…`）的 R4-01、R4-02、R4-03，主控的 p0u17-fix-r4 brief，U15 fix-r5 的样本偏差裁定，样板 r2.26，网表约定清单第 4.2 版（`71ddb16a…`），平局判据 TIE-RULE.md（`a4cf0e73…`，另加平局规则 v2.1 的折点根与 pulse 角点）。改动文件改前、改后的 sha256，脚本、命令、退出码与结果见 p0u17-fix-r4 处置记录（`runs/t3-p0-build-20261027/p0u17-fix-r4/disposition.md`）。**未仿真**：本机没有 Spectre，本轮没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。题面、参考解、starter、`task.toml`、两份 checker 与 `mutants.py` 都没有改。

现状：Spectre 小探针 `spectre-P0probe-C109-v1` 的交回结果已于 2026-10-29 由 Spectre 线正式核收（suite v1.8，加 r8 两项未结 P1 的一次性核对；执行身份 `spectre-P0probe-C109-v1（结果包 sha256 2c4e79eb7fa60d24…）`，18 个作业，证据 clean；登记文件 `current/runs/spectre-returns-20261028/accepted/REGISTER.json`，sha256 `3764e9af088c11ff8379fcd9c9c4f37a5721eea732ca391351d6c09b8f82a4a0`）。预读用的是同一个结果包、同一执行身份，以前各节所说的预读结论由此定稿，那些段落的原文不改。

1. 合同下界上的合法性平局（审核 R4-01）。
   - 时序下界（`instruction.md` 第 47–49、53 行）：同一输入相邻穿越至少 100 ps；`clk` 相邻上升沿至少 4 ns；`rst`、`sample_en`、`cmp_i` 的穿越离 `clk` 上升沿至少 100 ps；start 的穿越离 `rst` 的穿越至少 100 ps；start 上升离 `clk` 上升至少 100 ps，顶层至少 `2*tr`；顶层复位恢复至少 `2*tr`；DAC 位或同刻穿越、或至少相隔 100 ps；比较器单测的差值相邻过零至少 1 ns。checker 遇到违例报台架错误，自带的余量只有相对 1e-6。
   - 损失：按 U15 fix-r5，保存样本偏 1 mV、时刻偏 1 fs 时，一个穿越至多移 1 mV/|s| + 1 fs（s 为穿越处的斜率），一个间隔两端合计至多缩短 2·(1 mV/|s| + 1 fs)。本题控制边沿在穿越处：`tr = 200 ps` 为 10 mV/ps，损失 0.202 ps；`tr = 100 ps`、`vth = 0.3 V` 为 13.3 mV/ps，损失约 0.15 ps；`tr = 1 ns` 为 2 mV/ps，损失 1.002 ps。
   - 重扫（精确有理数，c109_bounds.py（`runs/t3-p0-build-20261027/p0u17-fix-r4/scripts/c109_bounds.py`））：改前私有用例有 77 处间隔恰在下界上（余量都是 0）：`base` 3（start 离时钟沿 `2*tr`），`modules-default` 2（控制器 start 离时钟沿 100 ps），`sweep` 67（34 个恰为 4 ns 的时钟周期，33 次完成沿后恰 `2*tr` 的 start），`modules-override` 2（start 离时钟沿 100 ps），`reset-recovery-long-tr` 3（复位恢复恰 `2*tr`）；公开的 `base`、`modules-default` 与同名私有用例相同。`busy-reset`、`vss-override`、`modules-initial` 与零平台三例没有；零平台三例各类间隔离下界至少 900 ps，网表逐字节不动，探针核收结果对应的仍是现网表。
   - 挪法：间隔两端都改变输出期望（F01 相位锁定）时，挪一端整一个网格步，事件仍在网格的 0.9 处；一端是不改变任何输出的空闲时钟沿时，只挪这一端，办法是改它两段斜坡中间角点的电压，角点时刻不动、仍在网格上：从 0 V 起的上升斜坡在 g·`vth`/m 处穿越（m 为中间角点），m = `vth`·5/4 时提前 0.1·g，m = `vth`·16/15 时推迟 0.0375·g。用例名、用途、参数覆盖与评分意图不变；用途文字只改了已经不准的数字（`base`、`modules-default`、`sweep`、`reset-recovery-long-tr`）。

     | 用例 | 间隔（下界） | 处数 | 挪法 | 改后 | 余量 | 损失 | 余量/损失 | 每端可吸收 |
     | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
     | `base` | 完成沿 E8 → start B（`2*tr`） | 1 | start B 上升推迟一个网格步，60.445 → 60.495 ns | 450 ps | 50 ps | 0.202 ps | 248 | 250 mV |
     | `base` | 空闲沿 E48 → start H（`2*tr`） | 1 | E48 中间角点 0.5 → 0.5625 V，380.045 → 380.04 ns | 405 ps | 5 ps | 0.191 ps | 26 | 26.5 mV |
     | `base` | start I → 采样沿 E55（`2*tr`） | 1 | start I 上升提前一个网格步，435.645 → 435.595 ns | 450 ps | 50 ps | 0.202 ps | 248 | 250 mV |
     | `modules-default` | `ct_start` → 采样沿 q7（100 ps） | 1 | 提前一个网格步，51.945 → 51.895 ns | 150 ps | 50 ps | 0.202 ps | 248 | 250 mV |
     | `modules-default` | 空闲沿 q12 → `ct_start`（100 ps） | 1 | q12 中间角点 0.5 → 0.5625 V，92.045 → 92.04 ns | 105 ps | 5 ps | 0.191 ps | 26 | 26.5 mV |
     | `sweep` | 时钟周期（4 ns） | 34 | 后一个判决沿推迟一个网格步 | 4.05 ns | 50 ps | 0.202 ps | 248 | 250 mV |
     | `sweep` | 完成沿 → start（`2*tr`） | 33 | start 上升推迟一个网格步 | 450 ps | 50 ps | 0.202 ps | 248 | 250 mV |
     | `modules-override` | `ct_start` → 采样沿 q7（100 ps） | 1 | 提前一个网格步，51.9225 → 51.8975 ns | 125 ps | 25 ps | 0.152 ps | 164 | 167 mV |
     | `modules-override` | 空闲沿 q12 → `ct_start`（100 ps） | 1 | q12 中间角点 0.333333 → 0.375 V，92.0225 → 92.02 ns | 102.5 ps | 2.5 ps | 0.144 ps | 17 | 17.6 mV |
     | `reset-recovery-long-tr` | `rst` 上升 → 空闲沿（`2*tr`） | 3 | 空闲沿 E7、E16、E27 中间角点 0.5 → 0.48 V，各推迟 9.375 ps | 2.009375 ns | 9.375 ps | 1.023 ps | 9.2 | 9.18 mV |

     “每端可吸收”是时刻无偏差时每端样本能偏多少仍合法；精确值与逐处时刻见 r401-table.json（`runs/t3-p0-build-20261027/p0u17-fix-r4/evidence/r401-table.json`）。余量都不超过一个网格步。被挪的沿使相邻的另一个间隔变短，都离下界很远：`sweep` 被挪判决沿之后的周期 6.5 → 6.45 ns、8 → 7.95 ns，start 高电平 1 → 0.95 ns；挪早的空闲沿之前的周期短 5 ps 或 2.5 ps；`reset-recovery-long-tr` 被挪空闲沿之后的周期短 9.375 ps。
   - `modules-override` 两处（原来刻意测下界，`tr = 100 ps`）：沿前的 start 离下界 25 ps，是相位锁定时能取的最小余量（一个网格步）；沿后的 start 离下界 2.5 ps，只挪了它前面那个空闲时钟沿。仍考“靠近下界”：沿前的 start 在前一个沿之后、离采样沿只有 1.25·`tr`，控制器要把这个沿当采样沿；沿后的 start 离刚过去的沿 102.5 ps，控制器要等下一个沿才采样。挪后 52.0225 ns 处 start 启动的过渡恰在时钟沿上结束的第 (i) 类平局不再存在（过渡在沿前 25 ps 走完）。沿前这次 start 的不评分窗恰在采样沿处结束，两者之间没有保存行，`ct_en`、`ct_t3` 的这两次变化仍没有自己的评分点，与挪动前相同。`modules-default` 的同一结构为沿前 150 ps（0.75·`tr`，`sample_en` 的上升在沿处仍未走完）、沿后 105 ps。
   - 台架写法：改动的八份网表（五个私有用例、两个公开用例与 `visible_test.scs`）按清单第 4.2 版补了“必须”一档，容差与已有用例（零平台三例）相同：`simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，`tran` 上加 `errpreset=moderate`、`strobeoutput=strobeonly`；不写 `precision`、`src_allbrkpts`。其余六例逐字节不动。
   - 核对（未仿真；脚本与结果见处置记录）：
     - 改后 77 处的余量都大于损失，最小是 `reset-recovery-long-tr` 的 9.2 倍；所有角点仍在网格上，没有角点恰在门限上，没有穿越落在网格行上；
     - 相位锁定的事件仍在网格 0.9 处，首个评分行仍在 1.275·`tr`（`dac_dbg` 1.2625 倍期限），评分起点与迟到时刻之间都有评分行；迟到可见性逐例不变：`base` 95/95、`modules-default` 171/171、`sweep` 360/360、`modules-override` 167/167、`reset-recovery-long-tr` 46/46；没有自己评分点的变化与挪动前是同一批（`base` 2、`modules-default` 2、`sweep` 14、`modules-override` 2 次）；
     - 转换结果与统计与挪动前相同；58 个合成控制的被拒集合与预期相同、前后不变（判决变化 0 项）；证据有效性控制 15/15；精确模型下参考解十一例都通过；
     - 平局：五个被挪用例在两种 binary64 读法、三种比较器语义下都没有第 (ii) 类；`modules-override` 52.0225 ns 的第 2、3 种情形消失，92.1225 ns 的第 3 种情形仍在；第 4 种不适用（参考解没有 `timer()`、`$abstime`）；没有根落在 PWL 折点上，本题不用 pulse 源。TIE-RULE.md 在本轮期间补了第 5 种（不同来源的两个事件只差 1 到 64 ulp，现行 sha256 `1fb0682f…`）：扫描把 10 zs 内的事件对都按两种次序求解过，本题时刻下 64 ulp 不超过 1.4e-20 s，10 zs 到 1 ps 之间最近的一对也相差 170 万 ulp 以上，第 5 种没有新增；
     - 旧版 EVAS 0.8.7：参考解与 46 个候选在五个私有用例、两个公开用例上 329 次运行，加起始模型 2 次（照旧 simulation_failed），全部行与只用网格行的判决都与 `expected.json` 一致，与 p0-fix-e 在挪动前字节上的运行逐项相同（331/331）；参考解最大误差 1.8e-12 V；1.3·`tr` 迟到负例只用网格行时被拒 17.3–23.1 mV，1.2·`tr` 窗内对照都通过；没有层次列全零、时间行去重或网格行改判。按样板第 4 节第 4 条核对零点掩盖：参考解按电平判定，不受影响；两个锁存候选在这五例按 `expected.json` 应被接受，它们的旧版通过不作 Spectre 证据。
   - 1 mV、1 fs 的样本偏差模型下，下面三类合法性判定无法靠台架余量解决，本轮不改，交主控：DAC 位“同刻”（checker 取 1 fs，三个模块用例共 38 组同时变化的位在模型下可差 0.2 ps，会报台架错误）；`vin` 静止（0.25 mV，平的 `vin` 在各样本互不相关的 1 mV 偏差下可测得 2 mV 的变化）；恰等于模型上限、没有余裕的两处电压界（逻辑输入电平的 1 mV 容差，`sweep` 的 4 mV 码余量对 3 mV 下界）。（p0u17-fix-r5：DAC 位同刻改为写进题面的 1 ps；`vin` 静止与余裕为 0 的电压界由主控与总协调定为保留。见“2026-10-29 修正 r5”一节第 2、4 条。）
2. checker 的“无变化”判定（审核 R4-02）：**停下交主控，本轮没有改 checker**，两份副本仍逐字节相同。（p0u17-fix-r5 已按清单第 4.9 版第 20 条处理：题面写明 δ = 0.1 mV，checker 用同一个 δ，见“2026-10-29 修正 r5”一节第 1 条。）
   - 用实数 `!=` 判“期望值是否改变”的地方：`tests/verify.py` 第 153 行（`run_sar` 的 `put`）、第 233 行（`distinct`）、第 369 行（`sample_hold` 分支）。`T`、`R`、`en`、`done` 与码是整数，`distinct` 只比较由整数码选出的 `vdd`/`vss` 电平，名义相等时 binary64 也相同，精确比较是对的（这些输出的最小合法变化是正的：DAC 码步 `(vref − vss)/16` ≥ 25 mV，逻辑电平 `vdd − vss` ≥ 0.5 V，门限在那里有空当，但不需要）；要门限的只有采样保持值（顶层 `sample_dbg`，模块 `sh_o`、`sh_dbg`）。
   - 门限的下限按 brief 是样本偏差在期望值上造成的最大差：两个名义相同的采样值每个偏 1 mV，可差 2 mV。上限是合同里最小的合法名义变化：合同对相邻两次采样值之差、对复位前样本离 `vss` 的距离都没有下限，任意小的名义变化都合法，上限为 0。上下限之间没有空当，按 brief 停下。
   - 题面怎么写开窗（逐字核对）：第 55 行“Every saved point is scored, except points less than 1.25 times an output's deadline after an event that changes that output's expected value.”，期望值“are calculated with the rules above from the recorded inputs”；第 19 行规定每次改变期望值的事件后输出在期限内到达新值，“The waveform inside the deadline is not specified.”。题面对任何改变期望值的事件都承诺不评分窗，没有最小幅度。合同里又存在任意小的合法变化，所以任何正的门限都会少开题面承诺的窗，成为隐藏的评分规则（主控转述的 R01-02 同类问题）。按主控 2026-10-29 的补充，这一情况停下报主控，不改题面。
   - 最小合法变化控制（r402_min_change.py（`runs/t3-p0-build-20261027/p0u17-fix-r4/scripts/r402_min_change.py`））：`zero-plateau-vss` 中让采样值比 `vss` 高 δ（`vin` 各行加 δ，合法），输出在 `tr` 内到达 `vss` + δ，另一份在期限内多一个 10 mV 的偏移（题面允许）。现行 checker 对 δ = 0.5 nV、0.5 µV、1.5 mV、5 mV 都开窗、都通过；门限 1 nV、1 µV、3 mV 的变体在 δ 小于门限时不开窗，拒绝期限内带偏移的合法输出。
   - 证据（scratch 里的变体 checker，不进题包）：现行 checker 放过审核者的定向尖峰控制（`zero-plateau-vss`，`vin` 各行加 1e-12 V，12.05 ns 一行的 `sample_dbg` 加 10 mV）；门限 1 nV、1 µV、3 mV 的三个变体都拒绝它，正确波形在同样偏差下通过；三个变体在 58 个合成控制、精确模型与已核收 Spectre 结果包的重判上判决都不变（修正版四个作业通过，换入前参考解四个作业失败）。现台架里采样保持值最小的非零名义变化是 18.04 mV（`modules-override`）。可选做法与利弊在处置记录里，由主控定。
3. 平局退回说明（审核 R4-03）：p0-fix-c 一节第 5 条已改写为只退回 start 脉冲 B。退回脚本 revert_start_b.py（`runs/t3-p0-build-20261027/p0u17-fix-r4/scripts/revert_start_b.py`），不应用。对现行最终字节（`tests/cases.json` sha256 `6e28af0801c0344cdbdee3b3a5e8ee080cdb398f25a4fad3879a2f2e5fad4e6d`）应用后得到的 `tests/cases.json` sha256 为 `c52a5942cd2fdf7f617a95b76859a7ef3f84439bfbb006b2df042c36ae7a58d2`。核对：只有 `reset-recovery-long-tr` 中 `Vstart` 一行的六个时刻不同，这一行与 p0-fix-c 原件逐字节相同；其余十例，以及该例的其余字段（本轮的余量、清单补行、用途），都与现行字节相同；全部下界仍有余量；F01 迟到可见性 46/46，合成控制与精确模型都符合预期；平局扫描重新出现 38.225 ns 的第 2、3 种情形，仍为第 (i) 类，没有第 (ii) 类。题面推荐 A 的 `instruction.md` 单文件退回是另一回事（p0-fix-e 一节第 3 条，备份 sha256 `0ff86ae5…` 已核过），两者互不影响。2026-10-29 已按用户决定退回（决定单第 1 项），见“2026-10-29 修正 r5”一节第 0 条。
4. 样板 r2.26 新条目在改动处的核对（主控 `list41_scan.py` 的 `check(text)`，按清单第 4.2 版第 0.5 节）：改动的八份网表与其余六份都没有命中：跨行一律行尾反斜杠、LF 换行（本题网表都是单行语句，没有 CR）；没有同时写 `strobetimes` 与 `strobeperiod`（只用 `strobeperiod`）；容差不为 0；没有“指数加比例符号”的数。checker：完整性检查取最后一行、带容差（`tests/verify.py` 第 414 行，`abs(ts[-1] - case['stop']) > max(1e-15, case['stop'] * 1e-6)`），没有按“时间等于 stop”找行；评分逐行进行，穿越按相邻行插值，不依赖输出行落在哪个时刻。合成核对：`reset-recovery-long-tr` 的合同波形最后一行提前 6 ulp 仍通过，按两倍细的网格保存也通过。
5. 校准件：`mutants.py` 不变（46 个候选与 p0-fix-e 的输出逐字节相同）；`expected.json` 的被拒矩阵不变，`conditions` 里 `sample_en_cleared_at_next_edge`、`reset_recovery` 两条把“恰为 `2*tr`”改为“`2*tr` 加 9.375 ps 的设计余量”；校准 README 同步改两句。

## 2026-10-29 修正 r5（p0u17-fix-r5，第 (ii) 类）

依据：主控的 p0u17-fix-r5 brief（`runs/t3-p0-build-20261027/briefs/p0u17-fix-r5.md`，sha256 `364bfcb7…`）与 05:42Z 的补充（同目录 `p0u17-fix-r5.steer-list410.md`，`94875695…`）；用户 2026-10-29 对决定单的答复（第 1 项退回原件，第 4 项触碰门限按 A 收窄版，第 13 项比较器事件按 A）；总协调同日的决定（两题照网表约定清单第 0.5 节第 20 条做，δ 取 0.1 mV，DAC 位同刻取有界值 1 ps，C109 全部用例补容差）；网表约定清单第 4.9 版（`f05138e7…`）与第 4.10 版（`e99f4ddb…`）；样板 r2.33（`f70e0850…`），本轮期间升到 r2.35（`d090ca15…`）；平局判据 TIE-RULE.md（`418d542a…`）；SL-DEC-20261029-05（`JUDGMENT-W2-S7S12-G400-L0A.md` 第 5 节，brief 给的 `10378745…`，补充后 `2b6b7d8e…`）；`JUDGMENT-FU2b.md`（`5691c10e…`）第 3、7 节。改动文件改前、改后的 sha256，脚本、命令、退出码与结果见 p0u17-fix-r5 处置记录（`runs/t3-p0-build-20261027/p0u17-fix-r5/disposition.md`）。**未仿真**：本机没有 Spectre，本轮没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；C109 探针结果 2026-10-29 已正式核收（执行身份 `spectre-P0probe-C109-v1（结果包 sha256 2c4e79eb7fa60d24…）`）。参考解、starter 的 `circuit.va`、`task.toml` 与 `mutants.py` 都没有改。

0. 退回第 (i) 类平局挪动（决定单第 1 项，用户 2026-10-29 按推荐定“退回原件”）。
   - 对象：`reset-recovery-long-tr` 中 start 脉冲 B 的六个角点时刻（`Vstart` 一行）。p0-fix-c 为避开 38.225 ns 的平局把它提前了 250 ps，按平局判据属第 (i) 类。退回后上升穿越 37.225 ns、下降穿越 37.975 ns（退回前为 36.975、37.725 ns）。
   - 做法：用修正 r4 备好的退回脚本（字节副本 revert_start_b.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/revert_start_b.py`），sha256 `1ca4ea3d…`，与修正 r4 的原件相同）。输入为现行 `tests/cases.json`（`6e28af08…`），输出 `c52a5942cd2fdf7f617a95b76859a7ef3f84439bfbb006b2df042c36ae7a58d2`，都与预期相同。只有该例 `Vstart` 一行的六个时刻不同，这一行与 p0-fix-c 原件逐字节相同；该例的其余字段（修正 r4 的空闲沿余量、清单补行、用途）与其余十例都不变。写入题包用本轮带 `--check` 的 `c109_cases_r5.py`，反向编辑复现改前字节。退回记录在 revert.json（`runs/t3-p0-build-20261027/p0u17-fix-r5/revert/revert.json`），供主控转总协调，由 EVAS 更新 #270、#276 的公开说明。
   - 核对（未仿真，照修正 r4 第 3 条的三项）：
     - 下界重扫：时序间隔离下界不到损失的 0 处，恰在下界上的 0 处；
     - F01：迟到可见性 46/46，首个评分行仍在 1.275·`tr`（`dac_dbg` 1.2625 倍期限），没有自己评分点的变化 0 次；58 个合成控制被拒集合与预期相同，判决变化 0；
     - 平局：38.225 ns 的第 2 种情形（复位上升改写 `sample_en` 刚结束的上升斜坡的目标，方向相反）与第 3 种情形（试位、码、`done` 的过渡终点碰上复位）重新出现；两种 binary64 读法、三种比较器语义下第 (ii) 类都是 0，按反序重算的评分输出差 0，10 zs 到 1 ps 之间没有事件对。
   - 公开用例：公开 `cases.json` 与 `visible_test.scs` 里没有这一例，没有可退回的。
   - 第 3 条（补容差）在退回后的字节上做，不碰这一例。这一例的网表变了，参考解与校准候选要在预校准包里按新字节重跑。
   - 旧版 EVAS 0.8.7（brief 没要求，加跑）：参考解与 46 个候选在这一例 47 次，全部行与只用网格行的判决都与 `expected.json` 一致。
1. 采样输出的变化门限 δ = 0.1 mV（审核 R4-02；清单第 0.5 节第 20 条）。
   - 题面第 55 行，原文：“Every saved point is scored, except points less than 1.25 times an output's deadline after an event that changes that output's expected value. That is `1.25*tr`, and `2.5*tr` for `dac_dbg` of the top module. At each scored point …”；新文：“Every saved point is scored, except points less than 1.25 times an output's deadline after an event that changes that output's expected value by more than δ = 0.1 mV. That is `1.25*tr`, and `2.5*tr` for `dac_dbg` of the top module. A change of δ or less, such as a new sample within δ of the held one, does not count as a change here or in the output timing rule above: it opens no such interval, the expected value keeps its previous value, and the output is scored against that value as at any other point. At each scored point …”。这一行其余文字和题面其余部分不变。“here or in the output timing rule above”让第 19 行的输出时序规则按同一个 δ 读，不必改那一行。
   - checker（`tests/verify.py`，公开副本逐字节相同）：新增 `DELTA = 1e-4`（第 37 行）；`run_sar.put` 对 `held` 用 `abs(v - state[k]) > DELTA`，`T`、`R`、`en`、`done` 仍用 `!=`（第 156–157 行）；`sample_hold` 分支改为 `abs(held - ch[-1][1]) > DELTA`（第 373 行）；模块文档串同步写明。变化不超过 δ 时不追加变化项，期望值保持原值，与题面新句一致。
   - 修正 r4 第 3.1 节列的位置，逐处：`run_sar.put` 的 `held`（采样值）用 δ，`T`、`R`、`en`、`done`（整数）精确；`distinct`（第 237 行，由整数码选出的 `vdd`/`vss` 电平）精确；DAC 码（第 333 行，整数码）精确；`sample_hold` 分支（采样值）用 δ。比较器单测的期望在每次过零交替为 `vdd`/`vss`，没有判等。精确比较的这些输出，名义相等时 binary64 逐位相同，名义不同时至少差一个 DAC 码步 `(vref − vss)/16`（≥ 25 mV）或逻辑摆幅（≥ 0.5 V），远大于 δ，所以精确比较开出的窗与题面的“变化超过 δ”逐个相同。`crossings()` 的 `r[node] == level`（第 70、71、80 行）是穿越规则里“某行恰在门限上”的定义，只用于台架输入，不判期望值是否改变，不在此列（见第 8 条）。
   - δ 的推导（清单第 4.10 版第 20 条的取法：reltol 取瞬态实际值，即 options 的值乘 errpreset 的倍数；vabstol 取 options 的值）：
     - 本题台架都写 `reltol=1e-6`、`vabstol=1e-8`、`errpreset=moderate`（倍数 1），瞬态 reltol 为 1e-6。一个采样值的噪声带 n = vabstol + reltol×|v|max，|v|max 取采样源节点（顶层 `vin`、模块 `sh_vin`）PWL 的最大绝对值。
     - 下界 10×(n + n)（两个采样值相比，两边相加）：台架最大 |v| 为 1.05 V（`base`、`modules-default`、`modules-override`），下界 10×2×(1e-8 + 1e-6×1.05) V = 21.2 µV；按合同取 |v|max = vref + 0.2 V ≤ 2.7 V，下界 54.2 µV。
     - 上界：要检测的最小变化的一半。现台架采样保持值最小的非零名义变化是 18.04 mV（`modules-override`），上界 9.02 mV。
     - δ = 0.1 mV 在两者之间：是合同下界的 1.85 倍，是上界的 1/90。
     - 不写容差时按 Spectre 缺省（reltol 1e-3、vabstol 1e-6 V）：`busy-reset`（|v|max 0.82 V）的下界为 16.4 mV，`vss-override`（0.95 V）为 19.0 mV，都超过上界 9.02 mV，两条矛盾。所以第 3 条先给这三例补容差。
     - 评分容差：每例 atol 2 mV，不小于 δ 加两个噪声带（至多 0.105 mV）。不超过 δ 的合法变化使期望值保持原值，正确输出与它至多差 δ 加数值噪声，不会被误拒。
   - 对照（未仿真，Python 合成波形，c109_controls_r5.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/c109_controls_r5.py`））。顶层是 `zero-plateau-vss`：`vin` 各行加 d，12.045 ns 采样沿的样本比所保持的 `vss` 高 d，`sample_dbg` 在 `tr` 内到达 `vss + d`。模块是 `modules-default`：把 `sh_vin` 最后一段平台从 0.5 V 改为 1.05 V + d，92.045 ns 的样本比所保持的 1.05 V 高 d，`sh_o` 在 `tr` 内到达新值。另一份在期限内（事件后 0.9·`tr` 内）多一个 10 mV 的偏移。“开窗”按 checker 评分点数比 d = 0 时少来判。

     | 合法变化 d | binary64 差（顶层 / 模块） | 开窗 | 正确波形 | 期限内 +10 mV |
     | --- | --- | --- | --- | --- |
     | 0.05 mV | 5e-05 / 5.0000000000105516e-05 | 否 | 通过（误差 0.05 mV） | 被拒（10.04 mV） |
     | 0.1 mV（恰为 δ） | 1e-4（恰等于 δ）/ 9.999999999998899e-05 | 否 | 通过（0.1 mV） | 被拒（10.08 mV） |
     | 0.11 mV | 1.1e-4 / 1.100000000000545e-4 | 是 | 通过 | 通过 |
     | 1 mV | 1e-3 / 9.999999999998899e-4 | 是 | 通过 | 通过 |

     改前的 checker 对四种 d 都开窗，八份都通过。按新题面，变化不超过 δ 时期限内的偏移不合法，被拒是对的；刚超过 δ 的 0.11 mV 照样开窗。
   - 审核者的尖峰（修正 r4 第 3.3 节：`vin` 各行加 1e-12 V，12.05 ns 一行的 `sample_dbg` 加 10 mV）：新 checker 拒绝（10 mV），改前放过；正确波形加同样的 1e-12 V 偏差、或 `vin` 整体加 1 mV，都通过（r402_c109.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/r402_c109.py`） 的字节副本，只把已核收结果包的读取路径指到修正 r4 的副本）。
   - 正确实现加 1 mV、1 fs 的样本偏差：十一例的合同波形，`vin`、`sh_vin`、`cmp_s`、`cmp_d` 以外的每个保存值各偏至多 1 mV（伪随机），每行时刻偏 1 fs（首末两行不偏）；这四个由 vsource 直接驱动、读值逐位精确的节点只偏至多 1e-12 V（见第 4 条）。新 checker 十一例都通过，最大误差 1.0 mV；改前的 checker 在三个模块用例报 DAC 同刻的台架错误。
2. DAC 位同刻的门限 1 ps。
   - 题面第 50 行，原文：“Bit inputs of the DAC that change together cross `vth` at the same instant. Other crossings of bit inputs are at least 100 ps apart.”；新文：“Bit inputs of the DAC that change together cross `vth` within 1 ps of one another, and these crossings count as simultaneous. Other crossings of bit inputs are at least 100 ps apart.”。
   - checker：`SAME = 1e-15` 改为 `1e-12`（第 36 行），台架判定（第 321 行，相邻两次穿越相差大于 1 ps 又不足 100 ps 时报台架错误）与并组（第 328 行，一组里最早的穿越起 1 ps 内的穿越并成一次）照旧用它。合法输入的一组两两相差不超过 1 ps，都在最早一次之后 1 ps 内，所以并组与题面一致。
   - 推导：
     - 下界（第 20 条用在时刻上）：一个穿越时刻的噪声 = n/|s|，n = vabstol + reltol×0.9 V = 9.1e-7 V（位输入在 0 V 与 0.9 V 之间），s 是穿越处的斜率；默认参数的位边沿 10 mV/ps，两位相加再乘 10，得 10×2×9.1e-7 V ÷ 10 mV/ps = 1.82 fs（`modules-override` 的边沿 13.3、26.7 mV/ps，为 1.37 fs）。1 ps 是它的 549 倍。改前的 1 fs 比这个下界还小。若 `modules-initial` 不补容差，按缺省 1e-3、1e-6 V 算得 1.8 ps，1 ps 就在下界以下，这也是第 3 条要补的原因。
     - 1 mV、1 fs 的样本偏差模型下，两位穿越至多差 0.202 ps（`modules-override` 0.152 ps），1 ps 是它的 4.95 倍：模型的偏差也算同时。（c109-fix-r6 更正：`modules-override` 按一组里最差的一对算为 0.302 ps，见“2026-10-29 修正 r6”一节第 2 条。）
     - 上界：要区分的最小间隔 100 ps 的一半，50 ps；1 ps 是它的 1/50。现台架不同时变化的位至少相隔 3 ns。
   - 重扫：修正 r4 的 `c109_bounds.py`（字节副本，只把其中的 `SAME` 改为 1 ps，c109_bounds_r5.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/c109_bounds_r5.py`））：十一份私有与两份公开网表 0 条不足，修正 r4 第 2.7 节的 38 组（含公开副本共 54 条）不再报；时序间隔 0 处不足。
   - 对照：`modules-initial` 8.045 ns 处四位同时变化，把 `cb_2` 的穿越挪 −0.5、+0.202、+0.5 ps：都按同时处理，正确波形通过；挪 +2 ps：报台架错误 “DAC bit crossings neither simultaneous nor 100 ps apart”，不判分。改前的 checker 对这四个都报台架错误。
3. C109 全部用例补容差。
   - `busy-reset`、`vss-override`、`modules-initial` 照其余八例补清单第 4.9 版“必须”一档：`tran` 之前插 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`；`tran` 在 `stop` 后加 `errpreset=moderate`、末尾加 `strobeoutput=strobeonly`。这三例其余字节不动，不写 `precision`、`src_allbrkpts`。写入用 `c109_cases_r5.py`（`--check` 先由改前字节重算，再核对反向编辑复现改前字节）。`tests/cases.json` 最终为 `0010163c…`。
   - 公开 `cases.json` 与 `visible_test.scs` 已有这几行（修正 r4 补），没有缺口，没有改。
   - 旧版 EVAS 0.8.7：参考解与 46 个候选在三例 141 次，全部行与只用网格行的判决都与 `expected.json` 一致；保存行与 p0-fix-e 在改前网表上的存档逐行相同（旧版接受这些容差但不使用）。
   - 三例的网表变了，参考解与校准候选要在 Spectre 上重跑，预校准包包含它们。
4. 同步。
   - 校准件：`tests/calibration/README.md` 与 `expected.json` 里 `comparator_cross_latch` 一条的探针状态，由“预读，正式核收待 Spectre 线 r5”改为“2026-10-29 已正式核收”，写明执行身份。被拒矩阵与候选不变。
   - 第 38、41 项：建模选择第 7 条、待办、p0-fix-c 一节第 2 条、p0-fix-d 一节第 2 条与 p0-fix-e 一节第 3 条的“待用户确认”改为“用户 2026-10-29 已确认”（第 38 项 A 收窄版，第 41 项 A）。题面早已按推荐写入，不再改。
   - 修正 r4 第 12 节其余几项，主控与总协调定为保留：
     - `vin` 静止判定（采样沿前后 100 ps 内变化小于 0.25 mV）：vsource 直接驱动的节点读值逐位精确（FU-01d），1 mV 模型不适用，判定不改；
     - 余裕为 0 的电压界（逻辑输入 0–0.9 V 的 1 mV 容差，`sweep` 的 4 mV 码余量对 3 mV 下界）：1 mV 模型只是推余量用的保守模型，第 20 条的数值噪声下界（约 20 µV）远小于 1 mV，不改；
     - 相位锁定的间隔用整网格步（`modules-default` 沿前 start 150 ps、`modules-override` 125 ps）：不改；
     - 修正 r4 目录下的 `legacy/`（旧版原始结果约 1.6 GB）不动。本轮的旧版原始结果（346 MB）放在证据卷 `证据卷/benchmark-p0u17-fix-r5-20261029/`。
5. 样板 r2.33（本轮期间升到 r2.35）新条目在本轮改动处的核对（未仿真；静态扫描与精确有理数）：
   - 清单第 0.5 节：协调方 `runs/t3-spectre-wave2-20261029/scan/list41_scan.py`（`92d7cea1…`，按第 4.7 版规则，只作模块载入、不运行 `main()`）的 `check(text)` 逐份核对本题 14 份网表（本轮改了 `busy-reset`、`vss-override`、`reset-recovery-long-tr`、`modules-initial` 四份）：0 命中。
   - 清单第 4.10 版第 7 条（最后一行的偏移不超过 3.0e-17 s）：checker 的完整性检查取最后一行，容差为 max(1e-15 s, 1e-6×stop)，本题最小 40 fs，盖得住；不按 time == stop 找行。第 21 条：本轮的 checker 与工具都不从日志取 `$strobe`、`$display`、`$fwrite` 记录，无。
   - 平局第 5 种：本轮改动的四例重扫（修正 r4 的 `c109_tie_r4.py`，现行 TIE-RULE）：10 zs 内的事件对都按两种次序求解（本题时刻下 64 ulp 不超过 4.2e-22 s）；10 zs 到 1 ps 之间只有 `modules-initial` 的 3 对：20.045 ns 比较器单测的过零（6 位小数的中间电平）比三位 DAC 输入晚 0.45 fs，两个实例互不相连，期望与次序无关；第 (ii) 类 0。
   - cross 返回根（SL-DEC-20261029-05 及 2b6b7d8e 的补充，return_roots_r5.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/return_roots_r5.py`））：参考解的 `cross()` 都写了 time_tol = 1 ps。由台架驱动的表达式（顶层 `rst`、`clk`、`start`，模块的 `cb_k`、`sh_rst`、`sh_clk`、`ct_rst`、`ct_clk`、`ct_start`，比较器单测的差值）在全部用例中，相邻两根至少相隔约 500 ps（最小 499.99997 ps，`modules-override` 的 `ct_start`），两根之间 |expr| 的最大值至少 3 mV（比较器单测的差值；逻辑输入至少 100 mV，`vss-override` 只到 0.4 V 的脉冲对 0.3 V 门限）；expr_tol 按最宽的读法（reltol 取 options 与瞬态值中较大的 1e-6，信号最大值取全程 |expr| 的最大值）至多 0.65 µV。每一对都必须报两次，计数可以评分，没有落在框内的。顶层内部的 DAC 位输入是控制器的试位输出：八个顶层用例里没有一次试位斜坡在中途被改写（trial_retarget_scan.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/trial_retarget_scan.py`）），两次穿越之间位都走到轨，同样必须报两次。顶层比较器的 `cross()` 只放时间点，输出按电平给出，计数不评分。
   - idt：参考解与 46 个候选都没有 `idt`。pulse：本题台架只用 PWL，没有 pulse 源。
   - 整数操作数的 abs、min、max：主控粗扫 `intminmax-scan.json`（`95975f2d…`）在本题没有命中；参考解不用 abs、min、max。
   - 主控 05:42Z 补充的两条：一次性 `timer()`：参考解与全部候选都没有 `timer()`，也不读 `$abstime`；`transition()` 的 td：参考解为 0，候选的 td 都是常数（0 或 0.2·`tr`），没有输入不变、只改 td 的写法。
6. 判决有变化的候选与控制。
   - VA 校准候选（旧版开发证据）：本轮 188 次运行与 `expected.json` 0 项不一致。存档的 611 次旧版波形用新 checker 重判（各按运行时的用例字节；423 次在现网表上，188 次在本轮改前的四例上），与记录的判决 0 项变化（全部行与只用网格行），新旧 checker 的判决逐项相同；与 `expected.json` 不一致的 6 项，仍是 p0-fix-e 起记录的零点掩盖（`comparator_cross_latch`、`comparator_initial_high` 在零平台三例的旧版通过）。
   - 合成控制：58 个模型 × 11 例的被拒集合与预期相同，新旧 checker 都如此；端点模型、F01 迟到可见性、证据有效性控制 15/15、精确模型（参考解十一例都通过；锁存候选在语义甲下零平台三例被拒，语义乙下只有 `zero-plateau-vss`），新旧 checker 逐项相同。
   - 判决改变的只有本轮加的对照，与设计一致：变化不超过 δ 而期限内有 10 mV 偏移的波形（改前通过，现在被拒）；审核者的尖峰（改前放过，现在被拒）；DAC 位相差 0.202–0.5 ps 与样本偏差控制（改前报台架错误，现在判分并通过）。
   - 已核收的探针结果包用新 checker 重判：修正版 4 个作业通过，换入前的 4 个作业失败，与改前相同。
7. Spectre 预校准：网表变了的 `reset-recovery-long-tr`、`busy-reset`、`vss-override`、`modules-initial` 四例，参考解与 46 个候选（188 个作业）必须重跑。checker 改了 `sample_dbg`、`sh_o`、`sh_dbg` 的变化判定与 DAC 同刻，其余七例与两个公开用例的评分也受影响；现有的 Spectre 结果只有零平台三例的探针（已用新 checker 重判），所以全部十一例与两个公开用例都应在包里，参考解 13 个作业、候选在十一个私有用例上 506 个作业。包的范围由主控定。
8. 交主控（本轮不改）：
   - 合法域允许 `rst` 在时钟沿后 100 ps 上升，`tr` 大于 100 ps 时，复位可以在控制器的试位斜坡中途改写目标。若改写恰在某位斜坡到达 `vth` 的一刻，这一位只触到 `vth` 又返回：按合同 DAC 的码不变，而参考解的 DAC 用 `cross()` 锁存位值，按到达规则会在到达时置位、离开时不复位。这是第 38 项前提 1 同类的内部恰在门限上的情形，只在时刻精确重合时出现。现有八个顶层用例里没有中途改写，评分不受影响；终评若改激励，有可能碰到。是否收窄合法域（例如复位离此前的时钟沿至少 `tr`）或改 DAC 写法，由主控定。（总协调 2026-10-29 定收窄合法域，c109-fix-r6 已做，见“2026-10-29 修正 r6”一节第 1 条。）
   - δ 的语义：本题与 U17 在变化不超过 δ 时让期望值保持原值（brief 要求只改“无变化”判定）；R01 三题的 checker 在这种变化时更新期望值、只是不开窗。两种写法各自与题面一致，但不统一；要统一须改变化列表与评分函数的结构。
   - `crossings()` 判“某行恰在门限上”仍用精确比较。本题台架输入的网格行离门限至少 0.22 mV（比较器单测的差值），用 0.1 mV 的带宽也得到同样的穿越。是否按第 20 条改写，由主控定。
   - 1 ps 对 1 mV 模型的倍数是 4.95，不是 10。若主控要求按 1 mV 模型取 10 倍，下界为 2.02 ps，可改取例如 5 ps（上界 50 ps），2 ps 的对照相应改为例如 10 ps。（总协调 2026-10-29 定 5 ps，c109-fix-r6 已改，见“2026-10-29 修正 r6”一节第 2 条。）
   - 并组以一组里最早的穿越为准。相邻两次都不超过 1 ps、首尾超过 1 ps 的一串穿越（题面不合法）不会报台架错误，会被并成两组。这在改前（1 fs）就存在，现台架没有这种情形。（总协调 2026-10-29 定改为台架错误，c109-fix-r6 已加检查，见“2026-10-29 修正 r6”一节第 3 条。）

## 2026-10-29 修正 r6（c109-fix-r6，第 (ii) 类与台架义务）

依据：主控的 c109-fix-r6 brief，三项由总协调 2026-10-29 按主控意见定（合法域收窄、DAC 位同刻门限 5 ps、DAC 并组的台架检查）；主控同日的补充（已定项的状态行）；第 1 项另据决定单第 4 项的 A 收窄版与平局规则的同一原则（避开只在时刻精确重合时才出现的内部触碰）；网表约定清单第 4.10 版（`e99f4ddb…`）第 0.5 节第 20 条；样板 r2.37（`f180bd09…`）第 2、3 节；平局判据 TIE-RULE.md（`418d542a…`）。改动文件改前、改后的 sha256，脚本、命令、退出码与结果见 c109-fix-r6 处置记录（`runs/t3-p0-build-20261027/c109-fix-r6/disposition.md`）。**未仿真**：本机没有 Spectre，本轮没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；C109 探针结果 2026-10-29 已正式核收（执行身份 `spectre-P0probe-C109-v1（结果包 sha256 2c4e79eb7fa60d24…）`）。参考解、starter 的 `circuit.va`、`task.toml`、`cases.json` 与公开副本、公开 `.scs`、`mutants.py` 都没有改。

0. 已定项的状态（主控补充）。
   - 总协调给出的对应：待确认清单第 35–37 项（建模选择第 3、4、5 条：忙时 start、同刻与复位规则、监测口与输出的含义）属决定单第 6 项；第 39 项（第 14 条：顶层复位恢复间隔 `2*tr`）属决定单第 5 项。用户 2026-10-29 都按推荐定。
   - 改了的状态行（理由原文不动）：建模选择的引言加一句；第 3、4、5、14 条的“待用户确认 1–4”改为“已定（用户 2026-10-29，决定单第 N 项）”，并注明原标与清单编号；第 14 条“若用户选另一种读法”一句末尾注明这一改法不再适用；待办里“用户确认上面四个……”一条；p0-fix-b 一节的 F03 一条。校准 README 两处与 `expected.json` 的 `conditions.reset_recovery` 也写着第 39 项待确认，同步改为已定（第 4 条）。第 38、41 项上一轮已改，不动。逐处的原文与新文见处置记录。
1. 合法域收窄：顶层用例中 `rst` 的上升穿越离此前的 `clk` 上升穿越至少 `tr`。
   - 起因：修正 r5 一节第 8 条第 1 点。原合法域只要求 `rst` 的穿越离 `clk` 上升穿越至少 100 ps；`tr` 大于 100 ps 时，复位可以在控制器的试位斜坡中途改写目标。改写若恰在某位到达 `vth` 的一刻，这一位只触到 `vth` 又返回：按合同 DAC 的码不变，参考解 DAC 的 `cross()` 锁存按到达规则却会在到达时置位、离开时不复位，`dac_dbg` 出错。
   - 依据：决定单第 4 项的 A 收窄版与平局规则的同一原则。只在时刻精确重合时才出现的内部触碰，由合法域避开，不靠模拟器的事件语义；参考解的 DAC 不改。
   - 题面：`instruction.md` 在复位恢复一条之后新加一条（第 50 行）：“When the top module is tested, every rising crossing of `rst` is at least `tr` after the preceding rising `clk` crossing. A reset therefore changes the controller's outputs, including the trial code that drives the DAC, only after they have reached the levels set at that clock edge.”
   - 只约束上升穿越。`rst` 的下降穿越不改变任何状态（题面第 30 行），触碰只来自复位改写试位目标。若约束全部穿越，现有用例 `reset-recovery-long-tr` 就不合法：118.725 ns 的下降穿越离此前 118.225 ns 的 `clk` 上升穿越只有 500 ps（0.5·`tr`；这次复位覆盖该沿，沿上 `rst` 为高，该沿本来就不起作用）。brief 不许改用例，按 brief 的允许只约束上升穿越，已报主控。
   - 为什么这一条就够：顶层的试位码 `T` 只在时钟沿、start 请求和 `rst` 上升三种事件改变。时钟沿与其后的 start 至少相隔 `2*tr`，相邻时钟沿至少 4 ns，`rst` 上升之后被放行的时钟沿至少 `2*tr`，start 与 `rst` 上升都把 `T` 设为 0、彼此不改写目标；新加的一条补上“时钟沿之后的 `rst` 上升”。于是试位斜坡不会在走完之前被改写；恰为 `tr` 时改写落在斜坡终点（平局规则第 2 种情形），这时位在轨上。
   - checker（`tests/verify.py` 第 271–276 行，公开副本逐字节相同）：对每次 `rst` 上升穿越找此前最近的 `clk` 上升穿越，相差不足 `tr` 时报台架错误 “a rising rst crossing within tr after the preceding rising clk crossing”。写法与其他合法输入检查相同（`ValueError`，相对余量 `REL`）。
   - 现有用例：精确有理数重扫，十一个私有与两个公开用例 0 处触发，最小为 4·`tr`（`reset-recovery-long-tr`，38.225 ns 离 34.225 ns）；按 1 mV、1 fs 模型也都有余量。
   - 对照（未仿真）：
     - 附加台架 `reset-tr-after-edge`，不进 `cases.json`：网表（`runs/t3-p0-build-20261027/c109-fix-r6/bench/reset-tr-after-edge.scs`）（sha256 `4f818f18…`）与用例记录（`runs/t3-p0-build-20261027/c109-fix-r6/bench/reset-tr-after-edge.case.json`）（`ddc904f8…`）。`tr = 1 ns`、6 ns 时钟，五次 `rst` 上升都恰在此前的时钟沿后 `tr`（精确有理数）：首次转换的采样沿（0.60 V）、保留位的判决沿（0.60 V）、不保留位的判决沿（0.30 V）、完成沿（0.65 V，码 11）、保持 0.85 V 时重新武装的采样沿（0.30 V）。其余合法界的余量都至少是损失的 648 倍。
     - 平局核对（TIE-RULE，精确有理数，两种 binary64 读法 × 三种比较器语义）：五次复位共 13 次第 2 种情形（复位恰在斜坡终点改写该斜坡的目标）。11 次方向相反（试位、码、`done`、DAC 输出、采样保持），按 LRM 4.5.8 的中断规则以旧终点为起点，两种读法的波形逐位相同。2 次方向相同：41.725 ns 的 DAC 输出由 `DAC(8)` 降到 `DAC(4)` 后再降到 `vss`，95.225 ns 的保持值由 0.85 V 降到 0.30 V 后再降到 `vss`；两种读法相差至多 0.1125 V 与 0.194 V，都在 `dac_dbg`、`sample_dbg` 的不评分窗内。参考解（电平比较器）第 (ii) 类 0，复位时刻四个试位位都在轨上（0 或 0.9 V）。属第 (i) 类，按自然写法保留。
     - 合成控制：附加台架的合同波形与精确参考解在新 checker 上通过（误差 0），输出各加至多 1 mV 的偏差也通过。五次复位都提前一个网格步（0.75·`tr`）或两个网格步（0.5·`tr`；这时其中四次复位处，参考解正在走的试位位在复位时恰在 `vth`（精确有理数下），正是收窄要排除的触碰）时，新 checker 报上面的台架错误；改前的 checker 对这三份都判通过。
     - 旧版 EVAS 0.8.7（旧版开发证据，待 Spectre 复跑）：参考解跑附加台架一次（标签 c109-fix6），全部行与只用网格行都通过，最大误差 0。参考解的比较器按电平判定，DAC 的位输入在这一台架里只有穿越、没有停在 `vth`，这次通过不受零点掩盖影响。
   - Spectre：附加台架作预校准包的附加作业，参考解跑一次，应在改后的 checker 上通过（第 6 条）。
2. DAC 位同刻门限由 1 ps 改为 5 ps。
   - 题面第 51 行（原第 50 行），原文：“Bit inputs of the DAC that change together cross `vth` within 1 ps of one another, and these crossings count as simultaneous. Other crossings of bit inputs are at least 100 ps apart.”；新文只把 1 ps 改为 5 ps。
   - checker：`SAME = 5e-12`（第 36 行）；台架判定（第 327–328 行）与并组（第 335 行）的比较改用 `SAME / REL`，即沿用 checker 其他界都带的相对余量 1e-6。理由：恰为 5 ps 的对照，checker 由保存行插值算出的间距是 5 ps + 7.07e-25 s，比 binary64 的 `5e-12` 大；不带余量就会把它报成台架错误，与题面“within 5 ps”相反。
   - 推导（清单第 4.10 版第 20 条与样板的观测模型，精确有理数）：
     - 下界（第 20 条用在时刻上）：一次穿越时刻的噪声带为 (vabstol + reltol×|v|max)/|s|。台架写 reltol 1e-6、errpreset moderate（倍数 1）、vabstol 1e-8，位输入在 0–0.9 V，噪声带的电压部分为 9.1e-7 V。两次穿越相比，取一组里斜率最小的两位相加再乘 10：默认参数（位边沿 10 mV/ps）为 1.82 fs，`modules-override` 为 2.73 fs（4.44 与 13.3 mV/ps 的两位）。5 ps 约是它的 2747 倍与 1832 倍。
     - 1 mV、1 fs 模型：两位穿越至多差 Σ (1 mV/|s| + 1 fs)，默认参数 0.202 ps，`modules-override` 0.302 ps；10 倍为 2.02 ps 与 3.02 ps，5 ps 不小于它们（2.48 倍与 1.66 倍）。
     - 上界：要区分的最小间隔 100 ps 的一半，50 ps。现台架不同组的位穿越至少相隔 3 ns。
     - 更正：修正 r5 取一组里时间上最早与最晚的两位，`modules-override` 得 0.152 ps 与 1.37 fs。35.0225 ns 那一组里 `cb_1` 由只到 0.4 V 的平台下降（4.44 mV/ps），最差的一对是它与上升的位，为 0.302 ps 与 2.73 fs。按这个数，原来的 1 ps 只是模型的 3.3 倍。
     - 适用范围：位边沿不慢于 4.02 mV/ps 时，5 ps 不小于模型的 10 倍；不慢于 3.64 µV/ps 时，不小于第 20 条的下界。现台架最慢的位边沿是 4.44 mV/ps。
   - 对照（`modules-initial` 8.045 ns 四位同时变化的一组，移动 `cb_2` 的穿越）：−0.5、+0.202、+0.5、+2、+5 ps 都按同时处理，正确波形通过；+10 ps 报台架错误 “DAC bit crossings neither simultaneous nor 100 ps apart”。改前（1 ps）+2、+5、+10 ps 都报台架错误。修正 r5 的 2 ps 对照按 brief 改为 10 ps。
   - 重扫：十一份私有与两份公开网表，DAC 同刻组按 5 ps 判 0 条不足，时序间隔 0 处不足。
3. DAC 并组的台架检查。
   - checker（第 340–342 行）：并组仍从一组里最早的穿越算起；一组结束后，下一次穿越若离这一组的最后一次不超过 `SAME`，即一串相邻都不超过 5 ps、首尾超过 5 ps 的位穿越，报台架错误 “DAC bit crossings that change together spread over more than 5 ps”。以前这样的一串会被悄悄并成两组。
   - 题面不改：“within 5 ps of one another”说的是两两之间，其余穿越又至少相隔 100 ps，这样的一串本来就不合法，checker 现在照题面查出来。
   - 对照：同一组里把 `cb_2`、`cb_1` 挪 +3、+6 ps 或 +5、+10 ps（相邻 3 或 5 ps，首尾 6 或 10 ps）时，新 checker 报这条台架错误；去掉这条检查的变体（只在 scratch）判分并通过，即悄悄并成两组。
   - 现有用例 0 处触发，三个模块用例的位穿越串与组逐一相同。
4. 同步。
   - 校准件：`mutants.py`、被拒矩阵与候选都不变。`tests/calibration/README.md` 第 7、86 行与 `expected.json` 的 `conditions.reset_recovery` 把第 39 项的“待用户确认”（“pending user confirmation”）改为已定（用户 2026-10-29，决定单第 5 项），与第 0 条一致。第 1–3 项不改变任何候选的判决，校准件不需要别的改动。
   - 建模选择第 4、7、11 条与待办补了指向本节的说明；修正 r5 一节第 2 条的推导与第 8 条中三点各补一句，原文不动。
5. 判决有变化的候选与控制（未仿真）。
   - VA 校准候选（旧版开发证据）：存档的 1128 次旧版波形（611 次在现网表上，517 次在较早的用例字节上，含修正 r5 的 188 次）用新 checker 重判，与记录的判决 0 项变化（全部行与只用网格行），与改前 checker 的重判逐项相同；与 `expected.json` 不一致的 6 项仍是 p0-fix-e 起记录的零点掩盖（`comparator_cross_latch`、`comparator_initial_high` 在零平台三例的旧版通过）。
   - 合成控制与精确模型：58 个合成模型在十一例上的被拒集合、精确参考解、审核者的尖峰、δ 的对照、1 mV 与 1 fs 的偏差控制、端点模型、F01 迟到可见性、证据有效性控制 15/15，新旧 checker 逐项相同。
   - 已核收探针结果包用新 checker 重判：修正版 4 个作业通过，换入前 4 个作业失败，与改前相同。
   - 按设计改判的只有对照：修正 r5 的 +2 ps 对照由台架错误变为按同时处理并通过；本轮新加的 +5 ps 对照通过、+10 ps 报台架错误；附加台架复位提前到 0.75·`tr`、0.5·`tr` 的两份由通过变为台架错误；两串位穿越的台架错误由 “neither simultaneous …” 变为 “spread over more than 5 ps”。
6. Spectre 预校准：在修正 r5 一节第 7 条的范围（参考解 13 个作业，候选在十一个私有用例上 506 个作业）之外，加附加台架的一个参考解作业，共 520 个。本轮 checker 只加台架义务检查，现有用例的结果按新 checker 重判即可。每个作业约 60 s，大部分是 Verilog-A 编译；附加台架有 417 个 strobe 行。包的范围由主控定。
7. 交主控（本轮按下面的读法做了，主控可改）：
   - 第 1 项只约束上升穿越（理由见第 1 条）。
   - 第 2 项的比较带 `REL` 余量，不只是改常量（理由见第 2 条）。
   - 校准 README 与 `expected.json` 的第 39 项状态随 SOURCE 一起改（第 4 条）；主控若只要改 SOURCE，这两个文件退回修正 r5 的字节即可，判决不受影响。
   - 附加台架是恰在边界上的对照，余量为 0，靠 checker 的相对余量吸收舍入（`tr = 1 ns` 时 1 fs）。清单第 0.5 节第 7 条在扫描 A 的 290 个作业里测到最后一行时刻偏差至多 3.0e-17 s；保存行偏这个量级时，这一台架的穿越移动不到 1e-17 s，远小于 1 fs。Spectre 上若这一作业报复位间隔的台架错误，先查保存行的时刻。
