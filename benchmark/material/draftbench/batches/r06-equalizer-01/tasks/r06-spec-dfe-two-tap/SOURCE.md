# 来源与验收状态

## 行为依据

规划候选身份：`task_id` U17-S1，`unit_id` U17，`case_anchor` C355，来源 `src-ca9546843cba`，`primary_ref` C355，动作 S（spec-modeling），家族 R06（滤波、均衡与 RF），优先级 P0，难度 M，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 U17-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。登记要求：
- reuse：两拍判决历史、反馈校正、`tap_lsb` 与切片输入观测；
- author_work：补抽头码到有符号权重、判决编码、中性初态；校准新旧历史判决能区分的序列，减少固定文件拆分；
- solver_work：实现反馈先于当前判决、历史在判决后更新的接收器，处理复位以及抽头改变后的第一拍；
- acceptance：相同当前输入配不同历史判决，应产生规定的不同校正；检查错误判决传播和复位后历史清除；
- spec_plan：首版固定抽头，不引入自适应和 CDR。

R06 已有的 [r06-filter-01](../../../r06-filter-01/) 批次放滤波题，本题是均衡题，另开 `r06-equalizer-01` 批次（批次目录与 README 由主控写）。`source_group` 取新组名 `v4-354`：已建题包和 SOURCE_GROUPS 中原来都没有以 v4:354 为来源的组。

用户已确认的决定：
- **判决编码与空历史（用户已确认，2026-10-28，选 A）**：决定卡 U17-dfe-history.md（`runs/t3-p0-pilot-20261027/decision-cards/U17-dfe-history.md`）。高、低判决编为 +1、−1；复位后还没有发生过的历史判决贡献 0，头两拍只用已有的有效历史；复位后 `fb_metric` 为 0。共同前提照写：两位抽头码按无符号 0 至 3 表示非负幅度，权重 `tap_lsb * code`；每拍先读当前抽头码和已有历史，算出反馈与切片输入，再判决，最后更新历史；两项 metric 锁存本拍实际用到的值。决定卡的纸面例（`tap_lsb = 20 mV`、k1 = 2、k2 = 1、`vcm = 0.45 V`、`vin = 0.46 V`）原样写进题面，也是公开用例 `base` 的第 9、12 次判决：历史（+1, −1）时反馈 +20 mV、切片输入 0.44 V、判低；历史（−1, +1）时反馈 −20 mV、切片输入 0.48 V、判高。终评能检出两类被排除的读法：把未发生的历史当成低判决（选项 B，原 gold 的做法）的 `empty_history_low` 和 0/1 编码（选项 C）的 `unipolar_history` 在九个用例中都被拒（合成控制；旧版结果见下文“待定项”）。把空历史当成高判决的 `empty_history_high`（v4:854 `neg_005` 的实际改动，u17-fix-r2 加入）同样在九个用例中都被拒。复位后头两拍的期望输出单独核对，见建模选择第 6 条。
- **内部组织自由（用户已确认，见讨论记录）**：固定顶层端口和可观察行为，内部模块、状态和文件组织由求解者决定，不恢复旧题“四个文件、四个公开模块”的要求。记录在本线讨论记录 `local/research/benchmark-submission-20261025/README.md` 第 84、120、131、175 行和「### U17-S1：让历史判决真正影响下一次判决」一节（第 212 行起；不在本工作树，文件 sha256 `562a36df97370ff163d45d81200d104b4a228695982a99e5c037375770c97c19`）。第 177 行的实验设计方向（保持当前输入、改变过去判决）由 `history-pairs` 用例实现。记录里“DFE 借用 2 mV 是 worker 建议的校准起点，主控未采用”一句也已核对：本题的 2 mV 是建题者按首批同类题定的误差预算（第 10 条），不是沿用那条建议，待 Spectre 校准验证。本单没有发现记录与 brief 不一致的已定事项。
- **评分起点（用户已确认，2026-10-28，F01 选 A）**：见建模选择第 9 条。

主来源是仓库内的 [v4:354 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap/public/instruction.md)，sha256 `56b1c7a01224c2e2448ea40b130718e7d905e29d09b41dbe3d445ac4a5e37454`，规划登记为 repository-contained。原题沿用的事实：
- 顶层模块 `dfe_rx_top` 与位置端口 `vin, clk, rst, tap1_1, tap1_0, tap2_1, tap2_0, decision, fb_metric, slicer_in_dbg`，参数 `vdd = 0.9 V`、`vss = 0 V`、`vcm = 0.45 V`、`vth = 0.45 V`、`tap_lsb = 20 mV`、`tr = 200 ps`；
- 每个 `clk` 上升沿只用前两次判决算反馈，切片输入为 `V(vin)` 减去反馈，校正后不低于 `vcm` 判高，判决之后才更新两拍历史；`fb_metric` 报告本次判决用的有符号校正，`slicer_in_dbg` 报告本次判决用的校正后输入；复位清历史、`decision`、`fb_metric` 和 `slicer_in_dbg`。

原 gold（[dfe_rx_top](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap/evaluator/solution/dfe_rx_top.va)、[feedback_filter](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap/evaluator/solution/feedback_filter.va)、[slicer](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap/evaluator/solution/slicer.va)、[decision_latch](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap/evaluator/solution/decision_latch.va)）不能直接作健康参考，与讨论记录的判断一致：
- `feedback_filter.va` 第 26–36 行把抽头码读成 0 至 3，却把低历史端口一律当 −1；`decision_latch.va` 第 26–35 行把初态和复位历史设低。所以非零抽头码下复位后立即有反馈，`fb_metric` 不为 0，与原合同“复位清 `fb_metric`”冲突；`feedback_filter` 也没有复位通路。
- `decision_latch.va` 第 44–46 行立即发布新历史，`fb_metric` 随后变成下一拍要用的反馈；`slicer.va` 的 `slicer_in_dbg` 连续跟随 `vin − V(fb_metric)`，复位期间为 `vss`。所以两个观测口在两次判决之间显示的不是“本拍实际用过的值”。

原 checker 是本机 legacy 仓库的 `runners/checkers/v4/task_354.py`（路径 `legacy/behavioral-veriloga-eval/runners/checkers/v4/task_354.py`，sha256 `71dd2857f72341302277ec2d7037f4a58cab23f11b6d63746f2b5a4ba29c1186`，legacy 提交 `fc1f3b36`，只读）。它的局限：
- 期望反馈按双极性计算，并把复位后的历史记成两次低判决；
- 每个上升沿只在沿前取一行、沿后 1 ns 取一行，反馈与切片输入的容差 50 mV，复位行的容差 80 mV；历史按观察到的判决推进；
- 台架只有抽头码 1/1、一次上电复位（复位期间抽头码为 0），`vcm = vth`，参数从不改写，反馈从不改变任何一次判决。

本题不继承它的判据和成绩。外接盘的历史净化包（路径文本 `证据卷/historical-purification-20261022/improve-packs/dfereceiver2tap/`，只读，不链接）记录了同样的缺口：`DEFECTS.json`（sha256 `cfaeb5adb66753b96903505b818a142b049b2d070e852a57780a3bd83100758b`）的 D1“符号约定与空历史没有写明”因 50 mV 容差被驳回，D2“gold 的 `fb_metric` 没有复位通路”判为 needs_human；`OUTPUT/CHANGES.md`（sha256 `779ff7fd6feb1c94a8b759f0c18156bdb897b2c48e1e6737ad691f3bc113b6d2`）与 `OUTPUT/manifest.json`（sha256 `9e8dc6055902112ac5c52d5e3ea5d5a95597fc6a6a6141968975794ae6428304`）有逐项证据；checker 闭包 `CHECKER_SOURCE/closure.py`（sha256 `ec1d2120a70500a9e6ba50c48feb309dc0cdad6b9e67e8cb4bb417f0d14ffbff`）与 legacy 仓库的 checker 内容一致。本题用决定卡 A 关闭 D1，用合同中的复位清零关闭 D2，把净化包列出的覆盖缺口（码 2/3、抽头与历史的对应、运行中复位、`vcm = vth`、观测口相位）都写成了台架要求。

同源的历史形式，按规划不另计题：
- [v4:1354 修复题](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1354-dfe-receiver-2tap-bugfix/public/instruction.md)的错误包只把切片器改成 `vin + fb`；
- [v4:854 测试台题](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/854-dfe-receiver-2tap-testbench/public/instruction.md)要求测试台检出五个变异：切片极性、反馈符号、忽略第二抽头、错误时钟沿、复位保留历史。

本题校准候选与这五个历史变异的对应，按 [mutation_catalog.json](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/854-dfe-receiver-2tap-testbench/evaluator/mutation_catalog.json)（sha256 `21b06b1d…`）和各变异包相对原 gold 的实际改动核对（u17-fix-r1 更正，u17-fix-r2 补 neg_005）：
- 切片极性 `neg_001_slicer_polarity`：`decision_latch.va` 第 45 行把 `>=` 改成 `<`，对应 `decision_polarity`；
- 反馈符号 `neg_002_feedback_sign`：`slicer.va` 第 22 行把减改成加，对应 `feedback_added`；
- 忽略第二抽头 `neg_003_second_tap_ignored`（故障类 `missing_tap`）：`feedback_filter.va` 第 36 行把第二项 `tap2_code * d2_sign` 换成固定的 `4.0 * d1_sign`，第二抽头的码和第二格历史都不再起作用。对应新增的 `second_tap_ignored`：它直接去掉第二项，不复制那个固定的 4 步权重；
- 错误时钟沿 `neg_004_wrong_clock_edge`：`decision_latch.va` 第 38 行把 +1 改成 −1，对应 `falling_edge_clock`；
- 复位保留历史 `neg_005_reset_preserves_history`（故障类 `missing_reset`）：名称说“保留”，实际改动是 `decision_latch.va`（变异包 sha256 `1037cee6…`）第 27–29、33–35 行在上电（`initial_step`）和 `rst` 上升时把 `current_bit`、`prev1_bit`、`prev2_bit` 三个状态位由 0 改成 1，并不保留原值；第 39–42 行 `rst` 为高时的时钟沿仍把三位清成 0（未改）。按实际改动对应 u17-fix-r2 新增的 `empty_history_high`：`prev1_bit`、`prev2_bit` 是两格历史，置 1 就是“空历史当高判决”，本候选在上电和复位时把 `h1`、`h2` 置 +1。`current_bit` 驱动原 gold 的 `decision` 输出；在原 gold 里输出电平与最近一格历史是同一位，本题合同把两者分开（清零后的 `decision` 显示 `vss`，背后的格是空的），所以本候选让清零后的 `decision` 仍为 `vss`，只改历史；输出被置高这一半没有单独的候选，t = 0 时的同类输出错误是 `initial_decision_high`。`reset_keeps_history`（复位清输出但不清历史）只是同属 `missing_reset` 类的另一种错误，不再作为 neg_005 的对应。

`tap_order_swapped`（tap 1 加权较早的判决）是新增的抽头配对错误，不对应任何历史变异：交换 k1、k2 与去掉第二抽头不同，k1 = k2 ≠ 0 时交换不改变结果，去掉第二抽头会改变。其余候选也都是新的。

历史 Spectre 证据：按样板第3a节查了本机 `legacy/behavioral-veriloga-eval/results/_local/v3_skeleton_dual_parity_cache/hidden/`（60 题，没有 DFE），又在同一仓库找到 v4 首批 Spectre 缓存里原 gold 在原 score 台架上的运行：路径文本 `legacy/behavioral-veriloga-eval/benchmark-vabench-release-v4/reports/first_n_spectre/cache/354/score/b5e11e83bd2f9c6a52a4efe925db8e88ca18109a26f21f4cf86340770c279769/`，Spectre 21.1.0.509.isr12，`+preset=ax`，2026-07-11；波形 `tran_spectre.csv` sha256 `9fce13191dc567beb0609353efa8ed2880661be36e083af54004d19fbf79a385`，台架与 release 的 `score_tb.scs` 相同（sha256 `c68fd069…`）。用本题合同在同一组记录输入上复核，记录见 historical-spectre-crosscheck.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/historical-spectre-crosscheck.json`）：
- `decision` 的 5 次跳变都从 `clk` 穿越时刻起按 `tr` 线性过渡，与直线的偏差不超过 56 µV，说明 Spectre 在穿越处取事件点，`transition()` 从事件时刻起动；
- 18 个稳定探测点中，gold 的 `slicer_in_dbg` 在 13 个、`fb_metric` 在 11 个与本题合同不同：12.26 ns 起、第一次判决之前 `fb_metric` 就是 −40 mV（空历史当低判决），每次判决约 0.2–0.4 ns 后两个观测口换成下一拍的值；
- 判决序列与本题合同相同，因为原台架的反馈从不改变判决。
这次运行不属于本题包，只说明 Spectre 的事件与过渡行为，以及原 gold 与新合同的差别。

外部依据：
- [Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）：
  - §4.5.8 `transition()`：输出在过渡时间内线性过渡；过渡被打断时按完成规则继续（新目标落在当前值后方时以原目标为起点，否则保留原起点，按“从起点在过渡时间内走完”的斜率从当前值走向新目标），所以在传输延迟为 0、上升与下降时间相等、目标在两次事件之间不变时，打断后仍在过渡时间内到达（非零延迟、上升下降时间不等、排队的过渡另算，见建模选择第 9 条）；新排的过渡之后的待发过渡被删除；
  - §5.10.2 `initial_step`；§5.10.3.1 `cross()`；
  - 每个方程至少要有一个容差（标准线引用的同一要求）。
- DFE 的反馈形式是通行做法：用已作出的判决（±1）乘抽头权重，从当前输入中减去后再切片。GitHub 检索（`gh search code`、`gh search repos`，2026-10-28）找到的公开 Verilog-A DFE 只有：Arcadia-1/behavioral-veriloga-eval 中 v4:354/1354/854 的各版本副本（即本题历史来源）；j95081456/RS_VA_EQ_Adaptation@434a2a86 的 `dfe.va`（没有 LICENSE，只阅读：它用 `2*V - offset` 把判决映射到 ±1，DFF 历史上电为低，正是决定卡选项 B 的做法）；mirekez/cpphdl@8b13e067 生成的 `OneGDFE.va`、`TenGDFE.va`（Apache-2.0，只看了检索列表，没有读取或复制）。arXiv 检索没有相关结果。参考解和新写的 44 个校准候选（`original_v4_354_gold` 以外的全部候选）是作者按新合同自写的，没有复制外部或历史代码。
- `original_v4_354_gold` 单列：它不是作者写的，而是从仓库内已有的组内历史资产按原字节生成的本地对照。`mutants.py` 只在仓库内运行时读取 historyref 中 v4:354 的四个 gold 文件（`slicer.va` `1a828ec5…`、`feedback_filter.va` `45773bdd…`、`decision_latch.va` `aaa44b9b…`、`dfe_rx_top.va` `fab5139b…`，迁入快照 commit `7b5616dc`），只去掉 include 行，再原样拼接。题包里不存这段文本；在仓库外运行时找不到 historyref，`mutants.py` 不生成这个候选。
- 这四个文件在公开仓库中有逐字节相同的副本，该仓库没有 LICENSE（见下一段）。按 [historyref 的使用约定](../../../../../historyref/README.md)，它们仅供课题组内部研究、不对外分发，并保持原字节。所以这个对照只用于组内校准，不是参考解或其他候选的来源，也不构成任何许可依据。
- 外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/sources.json`）。其中 `github-search-dfe` 条目末句“The reference and every candidate are written by the author from the contract”同样只适用于参考解和新写候选。sources.json 是建题记录，原文件不改，更正记在 u17-fix-r1 处理记录（`runs/t3-p0-build-20261027/u17-fix-r1/disposition.md`）。

记忆污染风险：中高。原 v4:354 的题面和四个 gold 模块都在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap) 中，与本仓库副本的 git 对象一致（题面 `62537895`，`dfe_rx_top` `b31efb19`，`feedback_filter` `1ab0474e`，`decision_latch` `2a07c75d`，`slicer` `ee5057fb`）。该仓库没有 LICENSE 文件。顶层模块名和端口与本题相同，原 gold 四个模块拼成一个文件原样提交可以编译，但会在全部用例中失败（校准候选 `original_v4_354_gold`）；新合同改了空历史、观测口锁存和复位语义，照抄 gold 的结构容易改编过来，所以风险不低。

同源与职责，均不重复计数：
- 首批30题：[v2-spec-353-ffe-transmitter-3tap](../../../v2-01/tasks/v2-spec-353-ffe-transmitter-3tap/instruction.md)（v4-353）是发送端三抽头 FFE：在时钟沿采样给定的输入符号，按当前、前一、前二个输入符号加权输出，未采样的历史为 0。本题的反馈来自接收器自己已经作出的判决，判决又取决于反馈，错误判决会传到后面两次校正；同一个当前输入在不同判决历史下判决不同。区别在非线性的判决反馈因果，不是抽头数。两题的“未有历史贡献 0”约定一致。校准候选不是 FFE 题的错误模型：只有 `input_sign_as_history`（历史存输入符号而不是判决）对应“把 DFE 当成 FFE”这一类错误，其余候选针对判决编码、反馈次序、观测口和复位。
- 规划中不在本单范围、尚未建题的同族候选，只写边界：C358-S1 是同一 FFE 发送端的另一来源形式；C354-S1 是 DFE 误差代理更新（两个自适应权重的递推），本题首版固定抽头、没有自适应；U09-I1 是由接收质量驱动的 CTLE/boost 训练闭环，没有判决反馈。登记的回退条件照旧：若以后 U09 改为包含同一 DFE 的完整实现，要重新合并求解责任。
- 第二批草稿与原56题：没有以 v4:354 为来源的题。R06 本批的 [r06-spec-dt-lowpass-sampler](../../../r06-filter-01/tasks/r06-spec-dt-lowpass-sampler/SOURCE.md) 等是滤波题，没有判决反馈。
- R01：采样孔径类题，不涉及均衡。

## 建模选择

每条决定都附理由。标“待用户确认”的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。

1. 接口：模块名 `dfe_rx_top` 与十个位置端口照原题，全部为 electrical；交付 `/app/circuit.va` 单个文件，可以在文件内定义辅助模块。理由：讨论记录要求固定顶层端口；内部组织自由由用户确认，原题“四个文件、四个公开模块”的要求不恢复。Deliverable 写明不要求特定的模块划分、状态变量、算子或事件组织；starter 只有 include、模块与端口声明和 TODO。`context_level` 取 `single-module`：合同只规定一个公开模块。校准候选 `alt_modules`（反馈求和、切片寄存、顶层三个模块）应被接受，是内部组织自由的例子。
2. 参数与合法域（原题只写 finite）：`vdd` 0.5–1.5 V，`vss` −0.5–0.5 V 且 `vdd − vss` 至少 0.4 V，`vcm` 与 `vth` 0.2–0.7 V，`tap_lsb` 5–50 mV，`tr` 10 ps–1 ns。理由：与 C176、U16、C109 的同类范围一致；`vth` 落在 0/0.9 V 控制电平之间并留出余量；`tap_lsb` 上限使最大反馈 6·`tap_lsb` = 0.3 V 不超过 `vin` 的 ±0.4 V 合法跨度。参考解用 `from` 写出这些范围。`param-override` 用例改写全部六个参数。
   - 终评端点用例（u17-fix-r1 加入，审核 U17R1-01；见第 12 条）：`param-endpoints-low` 取 `vdd` 0.5 V、`vss` 0.1 V、`vcm` 0.2 V、`vth` 0.2 V、`tap_lsb` 5 mV、`tr` 10 ps，除 `vss` 外都在下端，`vss` 0.1 V 与 `vdd` 0.5 V 组成最小摆幅 0.4 V；`param-endpoints-high` 取 `vdd` 1.5 V、`vss` 0.5 V、`vcm` 0.7 V、`vth` 0.7 V、`tap_lsb` 50 mV、`tr` 1 ns，全部在上端。
   - `vss` 下端用例（u17-fix-r2 加入，r1 交主控的 H4；见第 12 条）：`min-pulse-vss-low` 取 `vss` −0.5 V（下端）与 `vdd` 1.5 V，摆幅 2.0 V 是合法的最大摆幅；其余参数取合法域内、已有用例没有组合过的值：`vcm` 0.55 V 高于 `vth` 0.3 V（已有用例 `vcm` 等于 `vth`，或如 `param-override` 低于 `vth`），`tap_lsb` 40 mV，`tr` 40 ps（介于 10 ps 与 100 ps 之间，已有用例没有）。
   - 作者证据中的两个合成端点用例只核对 checker，不交给求解者的 VA：`endpoint-low` 的参数与 `param-endpoints-low` 相同（`vss = 0.1 V` 是最小摆幅组合，不是 `vss` 的下端）；`endpoint-high` 取 `vdd` 1.5 V、`vss` −0.5 V、`vcm` 0.7 V、`vth` 0.7 V、`tap_lsb` 50 mV、`tr` 1 ns。`vss` 的下端 −0.5 V 在终评里由 `min-pulse-vss-low` 覆盖（u17-fix-r2 之前只出现在合成 `endpoint-high` 里）。
3. 历史与编码（决定卡 A）：两格历史 `h1`（最近一次）、`h2`（再前一次），高 +1、低 −1、空 0；t = 0 和每次复位后两格都空。题面明说“清零后的 `decision` 输出不是一次判决：它显示 `vss`，但背后的格是空的，贡献 0”，以免求解者把输出电平当成历史。
4. 抽头码：`k1 = 2*b(tap1_1) + b(tap1_0)`，`k2 = 2*b(tap2_1) + b(tap2_0)`，`tap1_1`、`tap2_1` 是高位；tap 1 加权 `h1`，tap 2 加权 `h2`。理由：原 gold 的码读法与对应关系；原题没有写明对应关系（净化包列为缺口）。码 1/2 不对称，用来检出高低位颠倒（`tap_bits_swapped`）；k1 ≠ k2 且 h1 ≠ h2 时检出抽头次序颠倒（`tap_order_swapped`）；k2 ≠ 0 且第二格有判决时检出忽略第二抽头（`second_tap_ignored`）。
5. 逐拍次序与抽头读取时刻（决定卡共同前提）：判决事件是 `rst` 为低时 `clk` 上升穿越 `vth`；在穿越时刻读 `k1`、`k2` 和 `V(vin)`，算 `fb_n = tap_lsb*(k1*h1 + k2*h2)`、`s_n = V(vin) − fb_n`，`s_n >= vcm` 判高，三个输出改为本次的判决电平、`fb_n`、`s_n`，最后 `h2` 取旧 `h1`、`h1` 取本次判决。题面写成编号步骤，并写明反馈从不使用正在作出的判决。两次判决之间 `vin` 或抽头码的变化不改变任何输出，下次判决时才读取；所以“抽头改变后的第一拍”用新码和旧历史。各用例在每个时钟间隔中间改 `vin`，抽头码在间隔中间改，能分别检出“观测口跟随 `vin`”（`slicer_dbg_follows_vin`）、“观测口跟随实时抽头码与移位后的历史”（`live_metrics`，原 gold 的观测方式）和“用上一次判决时读到的抽头码”（`taps_one_decision_old`）。
6. 复位后的头两拍：第一次判决没有反馈，第二次只有 tap 1；题面用一句话写明。用例 `base`、`reset-restart`、`param-override`、`long-tr` 中每次复位后的头两拍都用非零抽头码，`history-pairs`、`isi-channel` 检查上电后的头两拍，两个端点用例上电后和复位后的头两拍也都用非零抽头码，`min-pulse-vss-low` 上电后和两次复位后的头两拍同样如此；合成控制的 `first_two_after_reset` 一节对每个这样的判决列出期望的三个输出，以及哪些错误模型在该拍给出不同值（空历史当低、0/1 编码、只把第二格当低、复位不清历史、只清第一格、复位后第一拍不判决、只在复位时读抽头码），见 synthetic-controls.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/synthetic-controls.json`）、u17-fix-r1 的 synthetic-controls.json（`runs/t3-p0-build-20261027/u17-fix-r1/synthetic-controls.json`） 与 u17-fix-r2 的 synthetic-controls.json（`runs/t3-p0-build-20261027/u17-fix-r2/synthetic-controls.json`）。40 个这样的判决（原六例 26 个，两个端点用例 8 个，`min-pulse-vss-low` 6 个）里，每一个至少被两个错误模型区分；u17-fix-r2 另列的“空历史当高”在其中 39 个给出不同值（`first_two_after_reset_r2_models`）。
7. 【待用户确认 1】复位的作用方式：`rst` 上升穿越 `vth` 时立即清空历史、把 `decision` 置 `vss`、两个观测口置 0 V，不等时钟沿；`rst` 为高时的时钟沿不判决（复位优先）；`rst` 下降穿越本身不改变任何输出；t = 0 时处于同样的清零状态。
   - 依据：原合同“On reset, clear …”；原 gold 的 `decision_latch` 在 `rst` 上升时清零、`slicer` 在复位期间按电平清 `slicer_in_dbg`；原 checker 检查复位期间的行。
   - 另一种读法是同步复位：只在 `rst` 为高的时钟沿清零（首批 FFE 题的写法）。按它写的实现在 `rst` 上升到下一个时钟沿之间仍显示旧值，在有判决后复位的七个用例中被拒（`synchronous_reset`）。
   - 推荐异步清零。
8. 【待用户确认 2】清零时 `slicer_in_dbg` 的取值：0 V。
   - 依据：决定卡定 `fb_metric` 复位为 0；原合同对两个观测口都写“clear”；它们是测量值，不是逻辑电平。`decision` 是逻辑输出，清零为 `vss`。
   - 另一种读法是 `vss`（原 gold 复位期间写 `vss`），或复位期间跟随 `vin`。`param-override`（`vss = 0.1 V`）、两个端点用例（`vss` 为 0.1 V、0.5 V）和 `min-pulse-vss-low`（`vss = −0.5 V`）中三者不同；按 `vss` 写的 `cleared_dbg_at_vss` 只在这四例被拒。
   - 推荐 0 V。若改为 `vss`，只需改题面一句、checker 的清零值和这四例的期望。
9. 输出时序与评分起点：每次改变某个输出期望值的事件之后，该输出在 `tr` 内到达新值并保持到下一次变化；下一次变化在到达之前出现时同样适用；`tr` 内的波形不作规定。
   - 评分起点与到达期限（F01，用户已确认，2026-10-28）：题面写明 checker 实际的观察起点，“除该输出期望值变化后 `1.25*tr` 内的点外，所有保存点都评分”，checker 不动。期限 `tr` 与评分起点之间到达不区分，这是题面写明的余量。新题按输出开不评分窗（C109 的写法）：只在某个输出的期望值真正变化时给它开窗。（p0u17-fix-r5 起为期望值变化超过 δ = 0.1 mV 之后，题面写明，见“2026-10-29 修正 r5”一节第 1 条。）
   - 迟到负例：九个用例都把改变输出的事件（`clk` 上升穿越、`rst` 穿越）放在输出网格的固定相位上：原六例在网格步长的 0.9 处（`reset-restart` 网格 100 ps、`param-override` 25 ps、其余 50 ps），`param-endpoints-low` 在 2.5 ps 网格的 0.92 处，`param-endpoints-high` 在 50 ps 网格的 0.5 处，`min-pulse-vss-low` 在 10 ps 网格的 0.9 处。于是每个事件后 1.275·`tr`（`long-tr` 为 1.255·`tr`，`param-endpoints-low` 为 1.27·`tr`）处有一个评分行，落在 (1.25·`tr`, 1.3·`tr`) 内，判定不取决于舍入。1.3·`tr` 到达的合成控制在九个用例都被拒：逐次统计全部输出变化，变化不小于 104 mV 的都被这个评分行看到，`decision` 的 162 次变化中除 `long-tr` 被复位改写的 1 次外都属此类；`long-tr` 共有 5 次变化被 0.6 ns 后的复位改写、没有自己的评分行，列为例外。VA 候选 `slow_output_1p3tr` 预期在九例都被拒。
   - 窗内对照：`margin_arrival_1p2tr`（1.2·`tr` 到达）应在全部用例通过，这是用户已接受的余量，不是正确模型。`param-endpoints-low` 的 `tr` 只有 10 ps，这一对照比评分行早 0.7 ps 到达，参考解早 2.7 ps，所以该例的期望要求 `cross()` 事件落在穿越后 0.7 ps 内；`min-pulse-vss-low`（`tr = 40 ps`）里这一对照早 3 ps、参考解早 11 ps，要求在 3 ps 内。按 Cadence Verilog-A Language Reference（产品版本 21.1）“Cross Event”一节第 129 页，`cross` 事件出现在穿越之后，并落在 time_tol 与 expr_tol 限定的范围内；time_tol 缺省为 1 s，实际不起作用；expr_tol 缺省为 1e-9 加 reltol 乘信号最大值。即使按 Spectre 缺省的 reltol 1e-3 计，在该例 90 ps 的时钟边沿上也不到 0.1 ps；本台架写的 reltol 是 1e-6。实际定位待 Spectre 记录。
   - 过渡被打断：按 LRM 2.4 §4.5.8 的完成规则（只按章节转述：打断后，新目标落在当前值后方时以原目标为斜率起点，否则保留原起点；输出从当前值按“从起点在过渡时间内走完”的斜率走向新目标），被打断的 `transition()` 在打断后 `tr` 内到达新值，所以合同不必排除打断，`rst` 的间隔也不必恢复为 2·`tr`。这条结论有前提：传输延迟为 0、上升与下降时间都是 `tr`、目标在两次事件之间保持不变。本题参考解满足这些前提，两电平的 `decision` 与多电平的 `fb_metric`、`slicer_in_dbg` 都成立；非零 `td`、上升下降时间不等、排队的过渡都要另算（审核 r1 的打断意见，u17-fix-r1 补写）。`long-tr`（`tr = 1 ns`）里两次复位在判决后 0.6 ns 上升：`decision` 与两个观测口从过渡中途转回清零值，`slicer_in_dbg` 有一次沿原方向继续越过原目标。按完成规则逐个输出算出的实际终点是 7.245、7.245、7.5587 ns（6.645 ns 的复位）和 25.3783、25.5593 ns（24.645 ns 的复位，两个观测口），与审核 r1 的推导相同，记录在 u17-fix-r1 的 build-endpoint-report.json（`runs/t3-p0-build-20261027/u17-fix-r1/build-endpoint-report.json`）。合成控制中按 LRM 完成规则和“从当前值重新走满 `tr`”两种写法都通过；“等当前过渡走完才开始新过渡”的模型只在该例被拒。两个端点用例和 `min-pulse-vss-low` 没有打断。
10. 误差预算：三个输出在每个评分点的误差都不超过 2 mV；时间上只有 `tr` 期限与 1.25·`tr` 评分起点，不另设时间容差。理由：与首批 v2 规格题、C264、C109 的 2 mV 一致；反馈值是 `tap_lsb` 的整数倍（至少 5 mV），切片输入离 `vcm` 至少 5 mV，判决电平相差至少 0.4 V，最小的错误模型差异也有 10 mV（合成控制中最小的被拒误差是 `tap_bits_swapped` 在 `param-endpoints-low` 的 10 mV，该例 `tap_lsb` = 5 mV；原六例中最小的是同一模型在 `reset-restart` 的 20 mV，其余多在 40 mV 以上；`min-pulse-vss-low` 上最小的是 `slow_output_1p3tr` 的 38.5 mV）。±1.9 mV 偏移的合成波形在九个用例都通过，±2.1 mV 都被拒。这是建题者定的预算，待 Spectre 校准验证。
11. 合法输入（原题没有）：
    - `clk`、`rst` 和抽头码输入在 0 V 与 0.9 V 之间切换，每次过渡不超过 200 ps；不停在 `vth` 上，到达 `vth` 时必定穿过，不触碰后返回，t = 0 时离 `vth` 至少 50 mV；`clk` 从低电平开始；
    - 同一输入相邻两次穿越至少相隔 0.5 ns，相邻 `clk` 上升穿越至少相隔 2 ns；
    - 每次 `rst` 穿越、每次抽头码输入穿越离任何 `clk` 上升穿越至少 0.5 ns，所以不同来源的事件不会同刻；
    - `vin` 连续，离 `vcm` 不超过 0.4 V；每个 `clk` 上升穿越前后 100 ps 内 `vin` 变化小于 0.25 mV；
    - 每次判决的切片输入离 `vcm` 至少 5 mV，所以没有判决由平局决定（题面仍写出 `>=` 规则）。
    理由：这些条件使期望值只由合同决定，不依赖事件定位误差、浮点相等或同刻次序；控制电平条件与 C264、C109 一致；`vin` 静止窗与切片余量沿用 C109 的写法（采样前后 100 ps、3 mV 余量），本题取 5 mV，九个用例实际至少 7 mV。checker 对这些条件逐条核对，违反时抛出异常、不判分（台架义务，不算候选失败）。
12. 台架：九个用例。前六个由 build_cases.py（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/build_cases.py`） 生成，生成时用独立写的合同模型断言上面的台架义务、切片余量和平局扫描，结果在 build-cases-report.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/build-cases-report.json`）。两个参数端点用例（u17-fix-r1 加入）由 build_endpoint_cases.py（`runs/t3-p0-build-20261027/u17-fix-r1/build_endpoint_cases.py`） 生成：它沿用 build_cases.py 的用例类和断言，另外用精确有理数从最终网表重新解析每个控制输入的门限穿越，核对间距、离时钟沿的距离、`clk` 的高低电平时长和最后一拍之后没有多余的上升沿，并按实际完成时刻做平局扫描，结果在 build-endpoint-report.json（`runs/t3-p0-build-20261027/u17-fix-r1/build-endpoint-report.json`）。`min-pulse-vss-low`（u17-fix-r2 加入）由 build_margin_case.py（`runs/t3-p0-build-20261027/u17-fix-r2/build_margin_case.py`） 生成，用同一套网表核对与平局扫描（build_endpoint_cases.py 的字节副本），再用 scan_minimums.py（`runs/t3-p0-build-20261027/u17-fix-r2/scan_minimums.py`） 精确列出合同每个时间下界上的间隔，断言下文的余量，结果在 build-margin-report.json（`runs/t3-p0-build-20261027/u17-fix-r2/build-margin-report.json`）。u17-fix-r3 把 `reset-restart`、`isi-channel`、`param-endpoints-low` 三例里恰在下界上的间隔挪开，三例由 build_r3_cases.py（`runs/t3-p0-build-20261027/u17-fix-r3/build_r3_cases.py`） 重新生成，见“2026-10-29 修正 r3”一节。
    - `base`（公开兼终评，默认参数，5 ns 时钟，113 ns）：上电即抽头码 3/3，头两拍空历史；反馈相消；两次反馈使判决与原始输入相反；抽头码在两次判决之间改为 2/1，然后是决定卡的纸面例；一次在两个时钟沿之间上升、跨过两个时钟沿的复位，复位期间抽头码改为 1/3，其后的头两拍。
    - `history-pairs`（4 ns 时钟，298 ns）：六组抽头码（1/2、2/1、3/0、0/3、3/2、1/3）各配四种历史，每组先用两次远离 `vcm` 的判决设好历史，再用 `vcm ± 5 mV` 的同一输入探测，同一输入和抽头码在不同历史下得到不同判决（24 对）；与原始输入相反的探测判决进入下一次校正；每次换码后的第一拍用新码和旧历史。
    - `reset-restart`（`tr = 400 ps`，100 ps 网格与 200 ps 控制边沿，5 ns 时钟）：t = 0 时 `rst` 为高、抽头码 3/2，两个时钟沿落在复位中；两个时钟沿之间 0.502 ns 宽的复位脉冲（u17-fix-r3 之前恰为 0.5 ns，加了 2 ps 设计余量）；跨两个时钟沿、期间改码为 2/3 的复位；第二次上升时输出已清零的两次连续复位；一直保持到结束的复位，其间还有两个时钟沿。每次重启后都有头两拍。
    - `param-override`（`vdd = 1.2 V`、`vss = 0.1 V`、`vcm = 0.35 V`、`vth = 0.7 V`、`tap_lsb = 30 mV`、`tr = 100 ps`，25 ps 网格）：`clk` 与 `rst` 边沿 180 ps，0.45 V 门限会早 50 ps 动作；`clk` 高于 `vth` 只有 0.58 ns；切片输入落在 `vcm` 与 0.45 V 之间、`vcm` 与 `vth` 之间的判决；清零值 0 V 与 `vss` 不同；负的切片输入；期间改码的复位。
    - `isi-channel`（2.05 ns 时钟，即最短合法周期 2 ns 加一个 50 ps 网格步的设计余量，u17-fix-r3 之前恰为 2 ns；抽头码 2/1；124.5 ns）：`vin = vcm + 50 mV·x(n) + 40 mV·x(n−1) + 20 mV·x(n−2)`，`x` 是固定种子的伪随机符号序列（包括 t = 0 之前的两个符号，所以头两拍的码间干扰没有被抵消），抽头与信道的两个后游标匹配；三次 85–95 mV 的反向扰动造成错误判决，错误判决的反馈传到后面的判决。这是本题的工程场景：DFE 抵消后游标码间干扰，也带来错误传播。
    - `long-tr`（`tr = 1 ns`，即最长合法过渡，50 ps 网格，3 ns 时钟，抽头码 2/1）：第 9 条的两次打断；一次反馈改变判决后的依赖判决；保持到结束、其间有一个时钟沿的复位。
    - `param-endpoints-low`（`vdd = 0.5 V`、`vss = 0.1 V`、`vcm = 0.2 V`、`vth = 0.2 V`、`tap_lsb = 5 mV`、`tr = 10 ps`，2.5 ps 网格即 `tr/4`，2.0025 ns 时钟即最短合法周期 2 ns 加一个 2.5 ps 网格步的设计余量（u17-fix-r3 之前恰为 2 ns），90 ps 控制边沿，26.5325 ns，10 614 个网格行）：除 `vss` 外的参数都在下端，`vss` 与 `vdd` 组成最小摆幅 0.4 V。事件在网格步长的 0.92 处，评分行在事件后 1.27·`tr`。上电即抽头码 1/2；5–20 mV 的反馈使 5 次判决与原始输入相反，同一输入在不同历史下判决不同（2 对）；两次判决之间换码为 3/1，换码后第一拍用新码和旧历史；一次在两个时钟沿之间上升、跨过一个时钟沿的复位，复位期间换码为 2/3，其后的头两拍。最小切片余量 8 mV。按 `max(tr, 100 ps)` 钳住过渡时间的实现在此例被拒（审核 U17R1-01 的反例）。
    - `param-endpoints-high`（`vdd = 1.5 V`、`vss = 0.5 V`、`vcm = 0.7 V`、`vth = 0.7 V`、`tap_lsb = 50 mV`、`tr = 1 ns`，50 ps 网格，3 ns 时钟，180 ps 控制边沿，37.55 ns）：全部参数在上端。事件在网格步长的 0.5 处，评分行在事件后 1.275·`tr`。上电即抽头码 2/1；最多 200 mV 的反馈使 6 次判决与原始输入相反，同一输入在不同历史下判决不同（2 对）；两次判决之间换码为 1/3，换码后第一拍的判决与按旧码判的不同；一次在两个时钟沿之间上升、跨过一个时钟沿的复位，复位期间换码为 3/2，其后的头两拍。复位在判决 1.5 ns 后上升，两个端点用例都没有打断。
    - `min-pulse-vss-low`（`vdd = 1.5 V`、`vss = −0.5 V`、`vcm = 0.55 V`、`vth = 0.3 V`、`tap_lsb = 40 mV`、`tr = 40 ps`，10 ps 网格即 `tr/4`，29 ns，2 901 个网格行；u17-fix-r2 加入，覆盖 r1 交主控的 H4 两处端点）：
      - 覆盖的边界：`vss` 的下端 −0.5 V（与 `vdd` 1.5 V 组成合法的最大摆幅 2.0 V）；`clk` 的最短阈值脉宽，按最终网表的阈值穿越算，高电平一次（3.509 → 4.011 ns）、低电平一次（7.517 → 8.019 ns），都是 0.502 ns。同一用例还有一次 0.502 ns 的 `rst` 脉冲（23.719 → 24.221 ns）和一对相隔 2.010 ns 的 `clk` 上升穿越（3.509 → 5.519 ns）。原八例中最近的是 `param-override` 的 0.58 ns 高电平和 `param-endpoints-low` 的 0.86 ns 低电平（u17-fix-r3 后为 0.8625 ns）；u17-fix-r2 时 `reset-restart` 的 0.5 ns 复位脉冲与 `isi-channel`、`param-endpoints-low` 的 2 ns 周期恰在下界上（scan-minimums-package.json（`runs/t3-p0-build-20261027/u17-fix-r2/scan-minimums-package.json`）），u17-fix-r3 已把它们挪开（见“2026-10-29 修正 r3”一节）。
      - 设计余量：恰为下界的间隔按 U15 fix-r5 的裁定算平局（合法与否取决于保存样本与时刻的偏差），所以 0.5 ns 的三处各加 2 ps，2 ns 的一处加 10 ps，用精确有理数断言。下限：一个间隔的两端各由相邻两行线性插值得到，每端最多移动 Δv/s + Δt（s 是穿越处的斜率，本例控制边沿都是 90 ps 走 0.9 V，s = 10 mV/ps），checker 自带的相对余量只有 1e-6（0.5 ns 上 0.5 fs）。2 ps 的余量每端能吸收 1 ps，即 10 mV 的样本偏差（时刻无偏差时）或 1 ps 的时刻偏差；按 U15 fix-r5 对 Spectre 样本的假设（偏离 PWL 不超过 1 mV、时刻偏差不超过 1 fs），两端合计至多 0.202 ps，是余量的 10 %；旧版偏差 4.5e-7 V 对应 9e-5 ps。上限：2 ps 是 0.5 ns 的 0.4 %、网格步长的五分之一，远小于原用例中次近的 80 ps（高电平）与 360 ps（低电平；u17-fix-r3 后 362.5 ps），仍在测“最短脉宽附近”。2 ns 周期的两端都是改变输出的判决沿，要守 F01 的网格相位（两端都在 0.9·g），所以余量取一个网格步长 10 ps（2 ns 的 0.5 %）；按同一假设损失 0.202 ps，是余量的 2 %。
      - 合成控制核对了这两个方向：把每处余量反向缩到下界以下（0.498 ns、1.990 ns）时 checker 报台架违例、不判分；把 0.5 ns 三处两端穿越两侧的保存行向缩短方向偏 4.5e-7 V、1 mV、1 mV 加 1 fs、5 mV、9 mV 仍合法，偏 11 mV 越界；2 ns 一处的前端同时是短高电平的起点，只移后端，偏到 80 mV（约 8 ps）仍合法；同一处恰为 0.5 ns 或 2 ns 时，不加偏差合法、偏 1 mV 即越界，这就是平局（u17-fix-r2 的 synthetic-controls.json 的 `evidence_controls_new_case` 与 `margin_controls`）。
      - 网格与评分行：改变输出的事件（`clk` 上升穿越、`rst` 上升穿越）都在 10 ps 网格的 0.9 处，事件后 1.275·`tr`（51 ps）处有评分行，严格落在 (1.25·`tr`, 1.3·`tr`) 内；1.3·`tr` 到达在这一行上差 1/52 的步长，`decision` 的每次变化（2.0 V）都差 38.5 mV。窗内对照与参考解分别早 3 ps、11 ps 到达。
      - 激励：时钟用 PWL，以便同一用例里分别给出短高电平和短低电平；`clk`、`rst`、抽头码的边沿都是 90 ps，拐点不在网格上，但离每个 `clk`、`rst` 穿越至少 30 ps，穿越两侧的网格行都落在同一段斜坡上，所以插值是精确的，也不取决于 Spectre 是否把拐点设为时间点（`src_allbrkpts` 待定）；没有穿越落在网格行上；`vin` 的拐点在网格上，离 `clk` 上升穿越至少 0.9 ns。
      - 内容：上电即抽头码 3/1；40–120 mV 的反馈使 6 次判决与原始输入相反，同一输入在不同历史下判决不同（2 对）；两次判决之间换码为 1/2，换码后第一拍的判决与按旧码判的不同；一次在判决后 1 ns 上升、跨过一个时钟沿的复位，复位期间换码为 2/3，其后的头两拍；0.502 ns 的复位脉冲（判决后 0.7 ns 上升）及其后的头两拍。5 次判决的切片输入在 `vth` 与 `vcm` 之间，4 次在 0.45 V 与 `vcm` 之间。最小切片余量 20 mV。没有打断。
      - 被拒情况：u17-fix-r1 已有的 37 个错误 VA 候选在此例都应被拒，包括在原八例中只被一例拒绝的 `tr_floor_100p`（原为 `param-endpoints-low`；本例 `tr` 40 ps）和 `slicer_compares_with_vth`（原为 `param-override`；本例 `vcm ≠ vth`）；合成控制里只有不对应 VA 候选的 `interrupt-waits-for-ramp-end` 通过，因为本例没有打断。u17-fix-r2 新加的 `decision_floor_0v`（`decision` 钳到不低于 0 V）与 `clk_deglitch_0p6n`（低电平不足 0.6 ns 后的上升沿不判决）只在此例被拒，说明这两处端点确实进了终评。
    - 网表按标准线的网表约定清单第 3 版（`runs/standard-line-20261028/netlist-conventions/LIST.md`，sha256 `6a6b17cddf813a8e7c7c4be3d47fed3bac5ab63b23fa207e0f49ff9a0f7713af`，只读）写：每个网表有 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，`tran` 写 `stop`、`maxstep`、`strobeperiod`、`errpreset=moderate`、`strobeoutput=strobeonly`；时钟在前八例是 pulse 源，写全 `val0`、`val1`、`period`、`width`、`rise`、`fall`，平移时写 `delay`，在 `min-pulse-vss-low` 是 PWL；其余是从 t = 0 起、覆盖 `stop` 的 PWL；`save` 列出 checker 读的十个信号；“不必”一档的参数一律不写；`precision` 与 `src_allbrkpts` 不写进用例网表。容差取值以标准线给 D1 定的为起点（`D1-TOLERANCES.md`，sha256 `7dc99b4b…`）：信号在 1.5 V 以内时每个节点的允许误差约 1.5e-6 V，比 2 mV 判据小三个数量级；这是选值依据，不是误差保证，实际误差待 Spectre 校准验证。
    - checker 不依赖仿真器把输出行放在哪里：评分行就是 strobe 网格；穿越时刻按相邻行线性插值，每个事件边沿在穿越两侧的网格行之间都是同一段直线（边沿长度至少 1.8 个网格步，`isi-channel` 等 100 ps 边沿对 50 ps 网格；端点用例为 90 ps 边沿对 2.5 ps 网格、180 ps 边沿对 50 ps 网格；`min-pulse-vss-low` 为 90 ps 边沿对 10 ps 网格），插值是精确的；前八例 `vin` 与抽头码的 PWL 拐点都在网格上、离时钟沿至少 0.5 ns，`min-pulse-vss-low` 见上文。
13. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：从记录的输入按上面的规则递推期望值，按输出比较。
    - 台架义务出错时抛出异常（无判决，不记候选失败）：参数超域、分辨率、控制电平与起始余量、穿越交替与间距、`rst` 与抽头码离时钟沿的距离、时钟沿处 `rst` 与抽头码离 `vth` 不足 0.1 V（在过渡中）、`vin` 超域或在时钟沿附近移动、切片输入离 `vcm` 不足 5 mV、没有判决事件；
    - 穿越提取用六题统一的 `crossings()`（函数文本与 C264、C109 相同）：恰在阈值上的行不属于任何一侧，触碰不算穿越，停在阈值上报错；
    - 返回的 `stats` 列出判决数、复位后头两拍数、与原始输入相反的判决数、“同一输入不同历史”的判决对数、换码后第一拍数、用到的码与历史组合、最小切片余量；
    - 不依赖任何仿真器特有行。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同；公开 checker 副本与私有副本逐字节相同。
14. 参考解（[circuit.va](solution/circuit.va)）按 LRM 与 Spectre 语义自然地写：`@(initial_step)` 和 `@(cross(V(rst) - vth, +1))` 设清零状态；`@(cross(V(clk) - vth, +1))` 中先判断 `V(rst)` 电平，再读抽头码、算反馈和切片输入、判决、移位；整数历史 +1/−1/0；三个输出都用延迟为 0 的 `transition()`。复位与采样拆成两个独立事件（样板第3a节）。参考解没有为任何 EVAS 版本改写。
    - 内部信号恰为零（第 38 项前提 1，r2.14）：`cross()` 只用在外部驱动的 `clk` 与 `rst` 上；空历史是整数 0，只参与算术；反馈恰为 0 时也只作为 `transition()` 的目标，没有任何事件检测它“离开零点”。
    - 旧版零点处理（r2.16）：已核对，不涉及。参考解和全部校准候选都只在外部驱动的 `clk`、`rst` 上用 `cross()`，这两个输入按合法域从不停在门限上、t = 0 时离门限至少 50 mV、到达门限必定穿过；没有在可能恰为零或恰在门限上的信号上检出“离开”的写法，旧版的通过不会被这种处理掩盖。
15. 平局扫描（标准线定稿判据 `TIE-RULE.md`，现行 sha256 `a4cf0e73dfc91af72416bb42d273b9b578f6caa2dc6fa098153751dfd280ffa7`，含 2026-10-28 补的第 4 种情形），在生成时用精确有理数核对，结果在 build-cases-report.json 的 `ties`；两个端点用例和 `long-tr` 的实际终点扫描在 u17-fix-r1 的 build-endpoint-report.json，`min-pulse-vss-low` 的在 u17-fix-r2 的 build-margin-report.json。建题时的扫描只查事件时刻加 `tr` 的名义终点；u17-fix-r1 按完成规则算出每个输出的实际完成时刻，再查所有控制输入的穿越（`clk` 与 `rst` 的上升和下降、抽头码）：
    - 第 1 种（不同来源的事件精确同刻）：没有，合法域要求 `rst` 穿越离时钟沿至少 0.5 ns；
    - 第 2 种（事件恰在某个过渡结束时改写它的目标）：没有；改变输出的相邻事件最近相隔 0.6·`tr`（`long-tr`）；`param-endpoints-high` 至少 1.5·`tr`，`param-endpoints-low` 至少 100·`tr`，`min-pulse-vss-low` 至少 17.5·`tr`（0.7 ns），原五例至少 2.5·`tr`；
    - 第 3 种（过渡终点碰上不改写它的事件）：名义终点筛查在 `long-tr` 找到两处：7.645 ns 的 `rst` 下降穿越和同一时刻的 `clk` 下降穿越，恰在 6.645 ns 复位所启动的清零过渡按完整 `tr` 计的终点；25.645 ns 的 `clk` 下降穿越，恰在 24.645 ns 复位所启动的清零过渡的名义终点。这只是名义终点筛查的结果，不是实际终点碰撞的精确结论：按完成规则，三路清零实际在 7.245、7.245、7.5587 ns 已结束，第二次在 25.3783、25.5593 ns 结束，所有实际终点上都没有任何输入穿越。这些下降穿越都不是参考解的事件，也不改写任何过渡目标，不构成先后之争，定为第 3 类，按自然写法保留，不挪输入。两个端点用例和 `min-pulse-vss-low` 没有打断，实际终点就是事件加 `tr`，其上没有任何输入穿越；
    - 第 4 种（timer 落在时间比较的边界上）：不适用，参考解没有 timer 事件，也没有时间比较。
16. 校准候选见 [tests/calibration](tests/calibration/README.md)：40 个错误模型（u17-fix-r1 加了 `second_tap_ignored` 与 `tr_floor_100p`，u17-fix-r2 加了 `empty_history_high`、`decision_floor_0v` 与 `clk_deglitch_0p6n`）、4 个正确替代实现（`alt_valid_count`、`alt_modules`、`alt_fast_output`、`alt_delayed_within_tr`）和 1 个余量对照 `margin_arrival_1p2tr`，被拒矩阵另存为 `expected.json`。其中 `original_v4_354_gold` 是唯一不是作者写的候选（见“外部依据”），由 `mutants.py` 在仓库内从 historyref 按原字节读取生成，题包里不存 gold 文本；它在九个用例中都应被拒，说明照搬原 gold 拿不到分。`tr_floor_100p` 把过渡时间钳到 `max(tr, 100 ps)`，在 `tr` 不小于 100 ps 的七个用例中与参考解相同，只在 `param-endpoints-low` 与 `min-pulse-vss-low` 被拒；`second_tap_ignored` 在九个用例中都应被拒。u17-fix-r2 的三个：
    - `empty_history_high`：上电与复位时两格历史置 +1，即 v4:854 `neg_005` 的实际改动（见“行为依据”中的对应关系），九个用例都应被拒；
    - `decision_floor_0v`：`decision` 写成 `transition(max(level, 0.0), …)`，在 `vss` 不小于 0 的八个用例中与参考解相同，只在 `min-pulse-vss-low`（`vss = −0.5 V`）被拒；
    - `clk_deglitch_0p6n`：记下最近一次 `clk` 下降穿越的时刻，上升穿越离它不足 0.6 ns 时不判决，是比合同 0.5 ns 更严的去毛刺；原八例每个上升穿越之前 `clk` 都至少低 0.86 ns，与参考解相同，只在 `min-pulse-vss-low`（一次 0.502 ns 低电平）被拒。
    最短的高电平、2 ns 周期与 0.5 ns 复位脉冲没有另加 VA 候选：要靠高电平长短来确认判决的写法，得等下降沿才能输出，在全部用例的时序上就先失败；2 ns 周期与 0.5 ns 复位脉冲在原八例中贴近下界出现（`isi-channel` 2.05 ns、`param-endpoints-low` 2.0025 ns 的周期；`reset-restart` 0.502 ns 的复位脉冲；u17-fix-r3 之前恰在下界上），对它们敏感的写法在那里被拒。这三处由合成控制核对 checker 的台架判定（第 17 条）。
17. 合成波形控制（synthetic_controls.py（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/synthetic_controls.py`），结果 synthetic-controls.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/synthetic-controls.json`））：48 个模型（8 个应通过、40 个应失败）在六个用例上的判定全部符合预期；两个合成端点用例上的 15 个模型也都符合预期：`endpoint-low` 与 `param-endpoints-low` 参数相同（`vss = 0.1 V` 是与 `vdd` 0.5 V 组成的最小摆幅，不是 `vss` 的下端；`tr = 10 ps`、2.5 ps 网格、2 ns 时钟、0.5 ns 复位脉冲），`endpoint-high` 取 `vdd` 1.5 V、`vss` −0.5 V、`vcm` 0.7 V、`vth` 0.7 V、`tap_lsb` 50 mV、`tr` 1 ns；17 个证据有效性控制（缺信号、非有限值、截断、网格过粗、`rst` 或抽头码离时钟沿太近、时钟沿处 `vin` 移动、切片余量 3 mV、`vin` 超域、`clk` 起始为高、`rst` 起始离门限 20 mV、`rst` 停在门限上、时钟间隔 1.5 ns、参数超域）都抛出异常、不判分。
    - u17-fix-r1 用同一脚本的副本重跑（synthetic_controls.py（`runs/t3-p0-build-20261027/u17-fix-r1/synthetic_controls.py`），结果 synthetic-controls.json（`runs/t3-p0-build-20261027/u17-fix-r1/synthetic-controls.json`）），加了两个终评端点用例和两个模型 `tr-floor-100p`、`second-tap-ignored`。50 个模型（8 个应通过、42 个应失败）在八个用例上的判定全部符合预期。原六例上的全部判定、两个合成端点用例的 15 个模型、17 个证据控制、迟到统计和头两拍核对，都与建题记录逐项相同。
    - `tr-floor-100p` 在原六例和 `param-endpoints-high` 通过（误差 0 mV），只在 `param-endpoints-low` 被拒（349.2 mV）；在合成 `endpoint-low` 上复现审核 r1 的结论：最大误差 348.8 mV，首个失败点 1.015 ns，`decision` 期望 0.5 V、实际 0.1512 V。`second-tap-ignored` 在八个用例都被拒。
    - u17-fix-r2 再用副本重跑（synthetic_controls.py（`runs/t3-p0-build-20261027/u17-fix-r2/synthetic_controls.py`），结果 synthetic-controls.json（`runs/t3-p0-build-20261027/u17-fix-r2/synthetic-controls.json`）），加了 `min-pulse-vss-low` 和三个模型 `empty-history-high`、`decision-floor-0V`、`clk-deglitch-0.6ns`。53 个模型（8 个应通过、45 个应失败）在九个用例上的判定全部符合预期；原八例上的全部判定、两个合成端点用例的 15 个模型、17 个证据控制、迟到统计、覆盖统计和头两拍核对，都与 u17-fix-r1 的记录逐项相同。在新用例上：参考行为通过；1.3·`tr` 迟到负例被拒（38.5 mV），1.2·`tr` 窗内对照通过；r1 已有的模型除 `interrupt-waits-for-ramp-end`（本例没有打断）外都被拒；`empty-history-high` 在九例都被拒，`decision-floor-0V` 与 `clk-deglitch-0.6ns` 只在本例被拒。另加 4 个只针对本例的证据控制（0.498 ns 高电平、0.498 ns 低电平、1.990 ns 周期、0.498 ns 复位脉冲，都报台架违例）和 U15 fix-r5 式的余量控制（第 12 条）。三个新模型在两个合成端点用例上的判定也符合预期（`decision-floor-0V` 只在 `vss = −0.5 V` 的 `endpoint-high` 被拒）。
    - u17-fix-r3 再用副本重跑（synthetic_controls.py（`runs/t3-p0-build-20261027/u17-fix-r3/synthetic_controls.py`），结果 synthetic-controls.json（`runs/t3-p0-build-20261027/u17-fix-r3/synthetic-controls.json`）），换上挪开下界的三例：53 个模型在九个用例上的判定全部符合预期；三例上的判决、失败区间数、最大误差、覆盖统计、迟到统计与头两拍核对都与 u17-fix-r2 相同，其余六例与其余控制逐项相同；另加三例的余量控制（见“2026-10-29 修正 r3”一节）。
    - 这些是合成控制，未仿真。

## 2026-10-29 修正 r3（u17-fix-r3，第 (ii) 类）

主控对 u17-fix-r2 交主控 H2 的裁定：原八例中有三例的间隔恰在合同下界上。按 U15 fix-r5 的裁定，这属于平局：台架合法与否取决于保存样本与时刻的偏差；按 1 mV 的样本偏差假设，这三例在 Spectre 上会被判台架违例、不评分。本轮按第 (ii) 类把这些间隔挪开下界、留出余量。只改了这三例的激励（`tests/cases.json` 中的三条记录），用例名、用途、参数覆盖、判决序列与评分意图都不变；其余六例逐字节不变；题面、参考解、checker、starter、公开用例与校准三件都没改。处理记录在 u17-fix-r3 的 disposition.md（`runs/t3-p0-build-20261027/u17-fix-r3/disposition.md`）。**未仿真。**

### 改了什么

时刻都按最终网表的阈值穿越算。

- `reset-restart`：0.5 ns 复位脉冲的下降穿越 37.09 → 37.092 ns（PWL 拐点 36.99、37.19 → 36.992、37.192 ns），高电平 0.5 → 0.502 ns。上升穿越 36.59 ns 改变输出，仍在 100 ps 网格的 0.9 处；下降穿越不改变任何输出，没有网格相位约束。其余激励与 stop（122.1 ns）不变。随之变短的只有其后的低电平（24.5 → 24.498 ns，离下界仍有 23.998 ns）。
- `isi-channel`：时钟周期 2 → 2.05 ns（pulse 源只改 `period`）。
  - 第 k 个上升穿越 2.045 + 2k → 2.045 + 2.05k ns（k = 0…59），末拍 120.045 → 122.995 ns；三次扰动所在的第 14、31、47 拍为 30.045 → 30.745、64.045 → 65.595、96.045 → 98.395 ns。
  - 每个 `vin` 拐点与它所在区间开头的上升穿越保持原来的距离：区间 k 的 `vin` 变化仍在该上升穿越后 0.955–1.055 ns，仍在下降穿越前 45 ps 走完，离下一个上升穿越 0.995 ns（原为 0.945 ns）。
  - 60 次判决的 `vin`、抽头码、历史、反馈、切片输入与判决与原例逐项相同；stop 121.55 → 124.5 ns（顺延 59 × 50 ps），网格行 2 432 → 2 491。
- `param-endpoints-low`：时钟周期 2 → 2.0025 ns（pulse 源只改 `period`）。
  - 第 k 个上升穿越 1.0023 + 2k → 1.0023 + 2.0025k ns（k = 0…12），末拍 25.0023 → 25.0323 ns。
  - `vin`、抽头码与 `rst` 的每个拐点与它前面的上升穿越保持原来的距离：复位上升 18.0023 → 18.0223 ns、下降 20.0023 → 20.0248 ns（仍在第 8 拍后 1 ns 上升、跨过第 9 拍）；换码斜坡 14.3–14.4 → 14.315–14.415 ns、18.3–18.4 → 18.32–18.42 ns。
  - 13 个时钟沿（12 次判决、1 次在复位中）的内容与原例逐项相同；stop 26.5025 → 26.5325 ns，网格行 10 602 → 10 614。
  - 实例行的 `tap_lsb=5m` 改写为 `5e-3`，与参考解 `from [5e-3:50e-3]` 的端点写法相同（样板 r2.22，见下文第 2 项核对第 5 条）；值不变。

### 余量与依据

下限按 U15 fix-r5 的样本偏差规则，推导与 u17-fix-r2 的 `min-pulse-vss-low` 相同，但按各例自己的网格、`tr` 与控制边沿重算：checker 用相邻两行线性插值求每个穿越，两行各偏 Δv、Δt 时一端至多移 Δv/s + Δt（s 是穿越处的斜率），一个间隔两端合计至多缩短 2(Δv/s + Δt)；checker 自带的相对余量只有 1e-6（0.5 ns 上 0.5 fs，2 ns 上 2 fs）。上限按样板 r2.21：最短脉宽、最短间隔离合同下界不超过一个网格步。

| 用例 | 间隔 | 余量 | 网格、`tr`、控制边沿 | 1 mV、1 fs 时两端合计损失 | 每端可吸收（时刻无偏差时） | 上限 |
| --- | --- | --- | --- | --- | --- | --- |
| `reset-restart` | `rst` 高电平 0.5 ns | 2 ps | 100 ps、400 ps、200 ps（4.5 mV/ps） | 0.446 ps（余量的 22 %） | 4.5 mV | 一个网格步 100 ps |
| `isi-channel` | 相邻 `clk` 上升穿越 2 ns | 50 ps | 50 ps、200 ps、100 ps（9 mV/ps） | 0.224 ps（0.45 %） | 225 mV | 一个网格步 50 ps |
| `param-endpoints-low` | 相邻 `clk` 上升穿越 2 ns | 2.5 ps | 2.5 ps、10 ps、90 ps（10 mV/ps） | 0.202 ps（8 %） | 12.5 mV | 一个网格步 2.5 ps |

- 0.5 ns 一类照 u17-fix-r2 留 2 ps。本例 `rst` 边沿 200 ps，斜率不到 `min-pulse-vss-low`（10 mV/ps）的一半，所以每端只能吸收 4.5 mV（r2 的例子为 10 mV），在 1 mV、1 fs 的假设下用掉余量的 22 %。下降穿越没有相位约束，余量也可以取得更大（上限 100 ps），本轮按 brief 取 2 ps。
- 2 ns 一类的两端都是改变输出的判决沿，要守 F01 的网格相位：事件后的首个评分行要严格落在 (1.25·`tr`, 1.3·`tr`) 内，`isi-channel` 的首个评分行在 1.275·`tr`，事件只能整体移 −5 至 +5 ps；`param-endpoints-low` 在 1.27·`tr`，只能移 −0.3 至 +0.2 ps。59 对、12 对周期首尾相接，不是整网格步的余量会逐拍累积，所以余量取一个网格步：`isi-channel` 50 ps（2 ns 的 2.5 %），`param-endpoints-low` 2.5 ps（0.125 %），都恰为样板允许的上限。
- 旧版内部行的偏差 4.5e-7 V（U15 fix-r5 实测）在三例上对应至多 2e-4 ps。

### 核对（精确有理数，未仿真）

由 build_r3_cases.py（`runs/t3-p0-build-20261027/u17-fix-r3/build_r3_cases.py`） 生成并断言，结果在 build-r3-report.json（`runs/t3-p0-build-20261027/u17-fix-r3/build-r3-report.json`）：

- 先用建题与 u17-fix-r1 生成器的字节副本逐字节重建三条旧记录，再生成新记录。新网表按网表约定清单第 3 版写，容差、`errpreset`、`maxstep`、`strobeperiod`、`strobeoutput` 与原例相同，PWL 从 0 起并覆盖 stop，pulse 写全参数，不写 `precision`、`src_allbrkpts`。
- 从最终网表独立重解析（u17-fix-r1 的 `netlist_check`）：台架义务全部满足；判决与生成器的合同模型一致；最后一拍之后、stop 之前没有多余的上升穿越；每次输出变化后的首个评分行严格落在 (1.25·`tr`, 1.3·`tr`) 内（`reset-restart`、`isi-channel` 在 1.275·`tr`，`param-endpoints-low` 在 1.27·`tr`），评分起点与迟到时刻之间都有评分行。
- 改变输出的事件仍在网格的 0.9 处（`param-endpoints-low` 为 0.92 处）；每个控制输入穿越两侧的网格行在同一段斜坡上，没有穿越落在网格行上，也没有网格行恰在评分起点上；用例 `params` 与实例行覆盖相同。
- 平局按 TIE-RULE.md 的四类（含第 4 种），按每个输出的实际完成时刻扫描：三例都没有；三例都没有打断。PWL 折点情形（平局规则 v2.1）：九个用例 `clk`、`rst` 与抽头码的全部折点都在 0 V 或 0.9 V，参考解与候选的 `cross()` 门限（0.2、0.3、0.45、0.7 V）都严格在两者之间，没有根落在折点上。
- 下界重扫：用 u17-fix-r2 的 scan_minimums.py（`runs/t3-p0-build-20261027/u17-fix-r3/scan_minimums.py`）（副本只改了目录）重扫九例，恰在下界上的间隔由 72 处变为 0 处（scan-minimums-package.json（`runs/t3-p0-build-20261027/u17-fix-r3/scan-minimums-package.json`））。三例各类间隔的最小值都没有更靠近下界；唯一变短的单个间隔是上面 `reset-restart` 的那一段低电平。

合成控制（synthetic_controls.py（`runs/t3-p0-build-20261027/u17-fix-r3/synthetic_controls.py`），结果 synthetic-controls.json（`runs/t3-p0-build-20261027/u17-fix-r3/synthetic-controls.json`））：

- 三例上参考行为通过；1.3·`tr` 迟到负例被拒（17.3、17.3、9.2 mV），1.2·`tr` 窗内对照通过。
- u17-fix-r2 的 53 个模型在三例上的判决、失败区间数与最大误差，以及覆盖统计、迟到统计与头两拍核对，都与 u17-fix-r2 相同；`expected.json` 的 45 个候选按各自的合成控制在三例上 135 项都与预期一致。其余六例与不涉及这三例的全部控制，与 u17-fix-r2 逐项相同。
- 余量控制：把三处余量反向扣掉（0.498 ns、1.95 ns、1.9975 ns）时 checker 报台架违例、不判分；u17-fix-r2 的网表恰在下界上，不加偏差合法、保存行偏 1 mV 即越界，复现了平局；新网表上，`reset-restart` 偏 4 mV 合法、5 mV 越界，`param-endpoints-low` 偏 12 mV 合法、13 mV 越界，`isi-channel` 偏 40 mV 加 2 ps 仍合法，与上表的吸收量一致。

旧版 EVAS 0.8.7（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑；记录在 u17-fix-r3 的 legacy-evas.json（`runs/t3-p0-build-20261027/u17-fix-r3/legacy-evas.json`））：参考解与 45 个校准候选在三例上 138 次运行，全部行与只用网格行的判决都与 `expected.json` 一致（138/138）；判决与最大误差都与本轮之前在旧网表上的运行相同；没有层次列全零、时间行去重或网格行改判。按 r2.16 核对零点掩盖：参考解与候选只在外部驱动的 `clk`、`rst` 上用 `cross()`，这两个输入从不停在门限上、t = 0 时离门限至少 50 mV、到达门限必定穿过，这些通过没有被旧版的零点处理掩盖。

`expected.json`、`README.md` 与 `mutants.py` 没有变化：三例的期望不变（合成控制 135/135，旧版 138/138）；README 中涉及这三例的说法仍成立，例如 `clk_deglitch_0p6n` 所依据的“原八例每个上升穿越之前 `clk` 至少低 0.86 ns”，现在的最小值是 `param-endpoints-low` 的 0.8625 ns。README 的表与数字由 check_readme.py（`runs/t3-p0-build-20261027/u17-fix-r3/check_readme.py`） 的副本重新核对。

### 样板 r2.18–r2.21 新条目的核对

核对脚本只读题包，结果在 item2-checks.json（`runs/t3-p0-build-20261027/u17-fix-r3/item2-checks.json`）。

1. 零边沿 `transition()`：参考解三个输出都是 `transition(x, 0.0, tr, tr)`，上升、下降时间显式为 `tr`（合法域 10 ps–1 ns，不为 0）。45 个校准候选的 `transition()` 都显式写了上升、下降时间（`tr`、0.2·`tr`、0.8·`tr`、1.2·`tr`、1.3·`tr`、200 ps、max(`tr`, 100 ps)），没有 0 或省略。台架的 pulse 源都写了 `rise`、`fall`。已核对，不依赖。
2. 实数 `==`：参考解没有实数 `==`、`!=`；它的实数比较 `V(rst) <= vth`、`V(tap…) > vth`、`slicer >= vcm` 都由合法域留出余量：时钟沿处 `rst` 与抽头码离 `vth` 至少 0.1 V（checker 核对），切片输入离 `vcm` 至少 5 mV（九例实际至少 7 mV）。候选里的 `==`、`!=` 都比较整数。checker 的 `crossings()` 用精确的 `==` 判断“某行恰在门限上”（verify.py 第 58、59、68 行）：本题台架没有穿越落在网格行上（生成器断言），即使仿真器的某行恰好等于门限，求得的穿越时刻也与插值的相同，判定不依赖它。checker 的另一处见第 6 条。
3. `initial_step` 与直流工作点：参考解的 `@(initial_step)` 只设常量与参数（`h1 = h2 = 0`、`fb = slicer = 0`、`level = vss`），不读节点，直流工作点 1.5e-12 量级的偏差不进入任何期望值；t = 0 的评分行期望 `vss`、0 V、0 V，参考解输出的就是这些目标值，1.5e-12 量级的偏差远小于 2 mV。两个错误候选在 `initial_step` 里读节点（`first_decision_after_reset_skipped` 读 `V(rst)`，`taps_read_only_at_reset` 读四个抽头码），都与 `vth` 比较，t = 0 时这些输入离 `vth` 至少 50 mV（checker 核对），不受影响。
4. `cross()` 的根恰在 PWL 折点上而事件里按电平比较：没有根落在折点上（见上文核对的平局一条）。另外，`clk` 事件里的电平比较读的是 `rst`、抽头码与 `vin`，它们在穿越时刻离门限至少 0.1 V，或在穿越前后 100 ps 内静止，穿越点读值与穿越后读值相同；`rst` 事件里没有电平比较。不依赖。
5. 实例行的参数端点写法：九个用例里值等于参考解 `from` 端点的实例覆盖共 15 处，写法不同的 4 处：
   - 本轮改动范围内的 `param-endpoints-low` `tap_lsb=5m`（范围写 `5e-3`），已改为 `5e-3`；
   - 本轮改动范围外的 `long-tr` `tr=1000p`（范围写 `1n`）、`param-endpoints-high` `tap_lsb=50m`（`50e-3`）与 `tr=1000p`（`1n`）。按 brief 其余六例逐字节不动，交主控。（p0u17-fix-r4 已改为与范围相同的写法，见“2026-10-29 修正 r4”一节第 1 条。）
   这四对按单次舍入、按当前 EVAS 的两次舍入（#289）都得到与端点相同的 binary64，不会触发 `parameter_range`；Spectre 的解析待 FU-01(c) 实测。
6. checker 判断“期望值是否改变”：`distinct()`（verify.py 第 172 行）用实数 `!=`，只有期望值真正改变的项才给该输出开 1.25·`tr` 的不评分窗。
   - `decision`（`vdd`、`vss`）与 `fb_metric`（`tap_lsb` 乘整数）的期望是精确值，同一名义值得到同一 binary64。
   - `slicer_in_dbg` 的期望是从保存行插值得到的 `vin` 减反馈。名义上相等的相邻期望（`history-pairs` 4 处、`isi-channel` 11 处）在 `vin` 样本有偏差时会被当成变化，多开不评分窗，只会放松评分。
   - 合成探针（checker-ne-probe.json（`runs/t3-p0-build-20261027/u17-fix-r3/checker-ne-probe.json`））让 `vin` 保存行带 1e-12 V 量级的偏差：这 15 处都多开了窗，53 个模型在九例上的判决都不变。失败区间数有 35 个模型与用例的组合变化：34 个在多开窗的两例，来自多开的窗；1 个是 `hardcoded-vth-0.45` 在 `param-endpoints-low` 的一个区间，那里切片输入恰好变化 2 mV，该模型在评分行的误差恰等于 2 mV 容差，1e-12 V 的偏差让它从失败变为通过，该模型在此例另有 32 个失败区间。
   - 参考解不依赖它。按 brief 本轮不改 checker，交主控（样板建议改用明确门限，例如 1 nV）。（p0u17-fix-r4：审核 R4-02 要求改为推导出的门限；按 brief 的上下限推导没有空当，停下交主控，checker 未改，见“2026-10-29 修正 r4”一节第 2 条。）（p0u17-fix-r5 已按清单第 4.9 版第 20 条处理：题面写明 δ = 0.1 mV，checker 只对 `slicer_in_dbg` 用同一个 δ，见“2026-10-29 修正 r5”一节第 1 条。）

结论：参考解与台架不依赖以上任何一条，没有需要停下的第 (ii) 类问题；第 5 条范围外的三处写法和第 6 条的 `!=` 交主控。

## 2026-10-29 修正 r4（p0u17-fix-r4，第 (ii) 类）

依据：P0 两题增量合审 r4（astra-review.json（`runs/t3-p0-build-20261027/review-p0u17-r4/astra-review.json`），sha256 `a15a8704…`）的 R4-05、R4-02 与审核者对 u17-fix-r3 交主控 H2、H3、H4 的意见，主控的 p0u17-fix-r4 brief，样板 r2.26，网表约定清单第 4.2 版（`71ddb16a…`），平局判据 TIE-RULE.md（`a4cf0e73…`）。改动文件改前、改后的 sha256，脚本、命令、退出码与结果见 p0u17-fix-r4 处置记录（`runs/t3-p0-build-20261027/p0u17-fix-r4/disposition.md`）。**未仿真**：本机没有 Spectre，本轮没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。题面、参考解、两份 checker、starter、`task.toml`、公开用例与校准三件都没有改；`tests/cases.json` 只改了两行。

1. 参数端点的字面写法（审核 R4-05，即 r3 交主控的 H2）。
   - `long-tr` 实例行 `tr=1000p` → `tr=1n`；`param-endpoints-high` 实例行 `tap_lsb=50m` → `tap_lsb=50e-3`、`tr=1000p` → `tr=1n`，与参考解 `from [5e-3:50e-3]`、`from [10p:1n]` 的端点写法相同。用例 `params`、激励、判决与评分都不变。
   - 生成器同步（u17_literal_cases.py（`runs/t3-p0-build-20261027/p0u17-fix-r4/scripts/u17_literal_cases.py`））：用建题的 `long_tr()` 与 u17-fix-r1 的 `endpoints_high()`（字节副本）先逐字节重建两条旧记录，再经 u17-fix-r3 的 `SpelledCase`（端点覆盖按 `from` 范围的原文写）生成新记录，与题包的新字节逐字节相同；只有两条 `XDUT` 行不同。
   - 解析核对：按倍率精确解析后，九个用例里值等于范围端点的 15 处实例覆盖全部与范围同写法（改前不同的就是上面三处）；这三对在单次舍入（Spectre，FU-01b；EVAS 修好 #289 后）和当前 EVAS 的两次舍入下，都与端点是同一个 binary64。
   - 合成核对：u17-fix-r3 的 53 个模型在两例上，改前改后的判决、失败区间、最大误差与首个失败逐项相同，迟到可见性与覆盖统计也相同（控制按用例 `params` 生成，与实例行写法无关）。
   - 旧版 EVAS 0.8.7：参考解与 45 个候选在两例的新字节上 92 次运行，全部行与只用网格行的判决都与 `expected.json` 一致（92/92），参考解误差 0；判决与此前在旧写法上的运行（建题 41 次、u17-fix-r1 45 次、u17-fix-r2 6 次）逐项相同。此前的旧版运行保留旧写法的身份，不说明它们验证过新字节。
2. checker 的“无变化”判定（审核 R4-02，即 r3 交主控的 H3）：**停下交主控，本轮没有改 checker**，两份副本仍逐字节相同。（p0u17-fix-r5 已按清单第 4.9 版第 20 条处理，见“2026-10-29 修正 r5”一节第 1 条。）
   - `distinct()`（`tests/verify.py` 第 172 行）同时用于 `decision`（`vdd`/`vss`）、`fb_metric`（`tap_lsb` 乘整数）与 `slicer_in_dbg`（`vin` 减反馈）。前两个名义相等时 binary64 相同，精确比较是对的；要门限的只有 `slicer_in_dbg`。
   - 门限的下限按 brief 是样本偏差（每个样本 1 mV、1 fs）在期望值上造成的最大差：两个名义相同的切片输入可差 2 mV；上限是合同里最小的合法名义变化：合同对相邻两次判决的切片输入之差没有下限，上限为 0；现台架 `param-endpoints-low` 里就有 2 mV 的合法名义变化。上下限之间没有空当，按 brief 停下。
   - 题面怎么写开窗（逐字核对）：第 47 行“Every saved point is scored, except points less than `1.25*tr` after an event that changes that output's expected value.”，期望值“are calculated with the rules above from the recorded inputs”；第 37 行规定每次改变期望值的事件后输出在 `tr` 内到达新值，“The waveform inside that `tr` interval is not specified.”。题面对任何改变期望值的事件都承诺不评分窗，没有最小幅度；合同里存在任意小的合法变化，任何正的门限都会少开题面承诺的窗，成为隐藏的评分规则（主控转述的 R01-02 同类问题）。按主控 2026-10-29 的补充，停下报主控，不改题面。`decision`（变化至少 `vdd − vss` ≥ 0.4 V）与 `fb_metric`（至少 `tap_lsb` ≥ 5 mV）的最小合法变化是正的，门限在那里有空当，但精确比较已经对，不需要门限。
   - 最小合法变化控制（r402_min_change.py（`runs/t3-p0-build-20261027/p0u17-fix-r4/scripts/r402_min_change.py`））：`history-pairs` 44.045 ns 的判决与前一次切片输入相同，让 `vin` 在这次判决前后 0.5 ns 内加 δ（合法），切片输入变化 δ，输出在 `tr` 内到达新值，另一份在期限内多一个 10 mV 的偏移（题面允许）。现行 checker 对 δ = 0.5 nV、0.5 µV、1.5 mV、5 mV 都开窗、都通过；门限 1 nV、1 µV、3 mV 的变体在 δ 小于门限时不开窗，拒绝期限内带偏移的合法输出。
   - 证据（scratch 里的变体 checker，不进题包）：现行 checker 放过三个定向尖峰控制（`slicer_in_dbg` 在事件后 5 ps 的一行加 10 mV：`isi-channel` 8.2 ns 只靠 binary64 算术；`history-pairs` 44.05 ns、`isi-channel` 6.15 ns 加审核者用的 k·1e-12 V 偏差）；门限 1 nV、1 µV 的变体都拒绝它们，正确波形在同样偏差下通过，53 个模型的被拒集合不变，k·1e-12 V 偏差多开的 15 个窗变为 0。门限 3 mV 的变体（大到能吸收 1 mV 偏差）则在 `param-endpoints-low` 误判合同波形与另外几个正确的替代模型：它把那次 2 mV 的名义变化当成不变。名义相等的相邻切片输入：`history-pairs` 4 处、`reset-restart` 1 处、`isi-channel` 15 处（其中 4 处在样本无偏差时 binary64 也不同）。可选做法与利弊在处置记录里，由主控定。
3. H4（`reset-restart` 的 2 ps）已核对：保留。`rst` 边沿 0.9 V/200 ps = 4.5 mV/ps，每端 1 mV、1 fs 时间隔至多缩短 2·(1 mV ÷ 4.5 mV/ps + 1 fs) = 0.4464 ps，是 2 ps 余量的 22 %；时刻无偏差时每端可吸收 4.5 mV；上限是一个网格步 100 ps。与审核者的推导（约 0.446 ps）相同。
4. 下界重扫（u17_bounds.py（`runs/t3-p0-build-20261027/p0u17-fix-r4/scripts/u17_bounds.py`），按 1 mV、1 fs 的损失，并带 u17-fix-r3 的 `scan_minimums.py`）：九例改前、改后都没有离下界不到损失的间隔，恰在下界上的为 0；改前改后结果逐项相同，修正 r3 的结论（72 处 → 0 处）不因本轮改动而变。各类间隔余量对损失的最小倍数：`reset-restart` 的 `rst` 高电平 4.5 倍，`min-pulse-vss-low` 的最短脉宽 9.9 倍，`param-endpoints-low` 的时钟周期 12.4 倍。电压界：切片输入离 `vcm` 至少 7 mV（下界 5 mV，多出的 2 mV 大于 1 mV 的损失）；`vin` 静止判定（0.25 mV）在各样本互不相关的 1 mV 偏差下会误报，与 C109 同一类，交主控；逻辑电平的 1 mV 容差恰等于模型上限。（p0u17-fix-r5：两项都由主控与总协调定为保留，见“2026-10-29 修正 r5”一节第 2 条。）平局：本轮只改实例行写法，不移动任何事件；TIE-RULE.md 在本轮期间补的第 5 种（不同来源的两个事件只差 1 到 64 ulp，现行 sha256 `1fb0682f…`）对本题没有新增，合同让 `rst` 与抽头码离时钟沿至少 0.5 ns，修正 r3 按实际完成时刻的扫描也没有平局。
5. 样板 r2.26 新条目在改动处的核对（主控 `list41_scan.py` 的 `check(text)`，清单第 4.2 版第 0.5 节）：两份改动的网表与其余九份都没有命中：跨行一律行尾反斜杠、LF 换行（本题网表都是单行语句，没有 CR）；没有同时写 `strobetimes` 与 `strobeperiod`；容差不为 0；没有“指数加比例符号”的数（`50e-3` 是指数写法、不带比例符号）。checker：完整性检查取最后一行、带容差（`tests/verify.py` 第 232 行），没有按“时间等于 stop”找行；评分逐行进行，不依赖输出行落在哪个时刻。合成核对：`long-tr` 的合同波形最后一行提前 6 ulp 仍通过，按两倍细的网格保存也通过。
6. 校准件不变：`expected.json`、`README.md`、`mutants.py` 都没有改（45 个候选与 u17-fix-r3 的输出逐字节相同；README 第 11 行写的是参数值，不涉及写法）。

## 2026-10-29 修正 r5（p0u17-fix-r5，第 (ii) 类）

依据：主控的 p0u17-fix-r5 brief（`runs/t3-p0-build-20261027/briefs/p0u17-fix-r5.md`，sha256 `364bfcb7…`）与 05:42Z 的补充（同目录 `p0u17-fix-r5.steer-list410.md`，`94875695…`）；总协调 2026-10-29 的决定（两题照网表约定清单第 0.5 节第 20 条做，δ 取 0.1 mV）；网表约定清单第 4.9 版（`f05138e7…`）与第 4.10 版（`e99f4ddb…`）；样板 r2.33（`f70e0850…`），本轮期间升到 r2.35（`d090ca15…`）；平局判据 TIE-RULE.md（`418d542a…`）；SL-DEC-20261029-05（`JUDGMENT-W2-S7S12-G400-L0A.md` 第 5 节，brief 给的 `10378745…`，补充后 `2b6b7d8e…`）；`JUDGMENT-FU2b.md`（`5691c10e…`）第 3、7 节。改动文件改前、改后的 sha256，脚本、命令、退出码与结果见 p0u17-fix-r5 处置记录（`runs/t3-p0-build-20261027/p0u17-fix-r5/disposition.md`）。**未仿真**：本机没有 Spectre，本轮没有运行 Spectre 或模型；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。本轮只改了题面一句、两份 checker 与本文件；参考解、starter、`task.toml`、用例与校准三件都没有改。

1. `slicer_in_dbg` 的变化门限 δ = 0.1 mV（审核 R4-02，即 r3 交主控的 H3；清单第 0.5 节第 20 条）。
   - 题面第 47 行，原文：“Every saved point is scored, except points less than `1.25*tr` after an event that changes that output's expected value. At each scored point …”；新文：“Every saved point is scored, except points less than `1.25*tr` after an event that changes that output's expected value by more than δ = 0.1 mV. A change of δ or less, such as a slicer input within δ of the previous one, does not count as a change here or in the output timing rule above: it opens no such interval, the expected value keeps its previous value, and the output is scored against that value as at any other point. At each scored point …”。这一行其余文字和题面其余部分不变；“here or in the output timing rule above”让第 37 行的输出时序规则按同一个 δ 读。
   - checker（`tests/verify.py`，公开副本逐字节相同）：新增 `DELTA = 1e-4`（第 39 行）；`distinct()` 加可选参数 `delta`（第 172–180 行），给了 `delta` 时按 `abs(a - b) > delta` 判变化，不给时照旧用 `!=`；只有 `slicer_in_dbg` 传 `DELTA`（第 266 行）；模块文档串同步写明。变化不超过 δ 时不保留该项，期望值保持原值，与题面新句一致。
   - 逐处：`decision`（`vdd`/`vss`）与 `fb_metric`（`tap_lsb` 乘整数）由参数与整数状态精确算出，名义相等时 binary64 逐位相同，名义不同至少差 0.4 V 与 `tap_lsb`（≥ 5 mV），远大于 δ，照旧精确比较，开出的窗与“变化超过 δ”逐个相同；`slicer_in_dbg` 是插值得到的 `vin` 减反馈，用 δ。`coverage()` 里“同一输入”用的 1 mV（第 212 行）只是统计，不评分。`crossings()` 的 `r[node] == level`（第 62 行）是穿越规则的定义，不在此列（见第 4 条）。
   - δ 的推导（清单第 4.10 版第 20 条的取法）：
     - 本题台架都写 `reltol=1e-6`、`vabstol=1e-8`、`errpreset=moderate`（倍数 1），瞬态 reltol 为 1e-6。反馈精确，切片输入的噪声就是 `vin` 的噪声，噪声带 n = vabstol + reltol×|vin|max。
     - 下界 10×(n + n)：台架最大 |vin| 为 0.8 V（`param-endpoints-high`），下界 10×2×(1e-8 + 1e-6×0.8) V = 16.2 µV；按合同 |vin| ≤ `vcm` + 0.4 V ≤ 1.1 V，下界 22.2 µV。
     - 上界：现台架切片输入最小的非零名义变化 2 mV（`param-endpoints-low`），上界 1 mV。
     - δ = 0.1 mV 是合同下界的 4.5 倍，是上界的 1/10。不写容差时按 Spectre 缺省（1e-3、1e-6 V）下界为 22.0 mV，超过上界；本题全部用例都已写容差。
     - 评分容差：每例 atol 2 mV，不小于 δ 加两个噪声带。
   - 对照（未仿真，Python 合成波形，u17_controls_r5.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/u17_controls_r5.py`））：`history-pairs` 44.045 ns 的判决与前一次切片输入相同（0.31 V）；让 `vin` 在这一沿前后 0.5 ns 内加 d（仍满足 100 ps 内静止），切片输入变化 d，`slicer_in_dbg` 在 `tr` 内到达新值并保持到下一次判决；另一份在期限内多一个 10 mV 的偏移。

     | 合法变化 d | binary64 差 | 开窗 | 正确波形 | 期限内 +10 mV |
     | --- | --- | --- | --- | --- |
     | 0.05 mV | 4.999999999999449e-05 | 否 | 通过（误差 0.05 mV） | 被拒（10.04 mV） |
     | 0.1 mV（恰为 δ） | 9.999999999998899e-05 | 否 | 通过（0.1 mV） | 被拒（10.08 mV） |
     | 0.11 mV | 1.0999999999999899e-04 | 是 | 通过 | 通过 |
     | 1 mV | 1.0000000000000009e-03 | 是 | 通过 | 通过 |

     改前的 checker 对四种 d 都开窗、都通过。d 恰为 δ 时，`vin − fb` 的 binary64 差比 δ 小 1 ulp 量级，checker 不开窗，与题面“δ or less”一致；若舍入落在 δ 之上，只会多开一个窗、放松评分。
   - 审核者的三个尖峰（修正 r4 第 3.3 节：`isi-channel` 8.2 ns 只靠 binary64 算术；`history-pairs` 44.05 ns 与 `isi-channel` 6.15 ns 加 k·1e-12 V 偏差）：新 checker 都拒绝（10 mV），改前都放过；正确波形在同样偏差下通过。k·1e-12 V 偏差多开的窗由 15 个变为 0，53 个模型的判决都不变。
   - 正确实现加 1 mV、1 fs 的样本偏差：九例的合同波形，`vin` 以外的每个保存值各偏至多 1 mV（伪随机），每行时刻偏 1 fs（首末两行不偏），`vin`（vsource 直接驱动、读值逐位精确）只偏至多 1e-12 V：九例都通过，最大误差 1.0 mV。
2. 修正 r4 第 12 节在本题的几项，主控与总协调定为保留：
   - `vin` 静止判定（判决沿前后 100 ps 内变化小于 0.25 mV）：vsource 直接驱动的节点读值逐位精确（FU-01d），1 mV 模型不适用，判定不改；
   - 余裕为 0 的电压界（控制输入 0–0.9 V 的 1 mV 容差）：1 mV 模型只是推余量用的保守模型，第 20 条的数值噪声下界（约 20 µV）远小于 1 mV，不改；
   - 相位锁定的间隔用整网格步（修正 r3 的 `isi-channel` 50 ps、`param-endpoints-low` 2.5 ps）：不改；
   - 修正 r4 目录下的 `legacy/` 不动。
3. 样板 r2.33（本轮期间升到 r2.35）新条目的核对（未仿真；静态扫描与精确有理数）。本轮没有改本题的网表，下面是对现行字节的复核：
   - 清单第 0.5 节：协调方 `list41_scan.py`（`92d7cea1…`，按第 4.7 版规则，只作模块载入、不运行 `main()`）的 `check(text)` 对 11 份网表 0 命中。第 4.10 版第 7 条：完整性检查取最后一行，容差 max(1e-15 s, 1e-6×stop)，本题最小 26.5 fs，盖得住 3.0e-17 s 的偏移；不按 time == stop 找行。第 21 条：本轮的 checker 与工具都不从日志取 `$strobe`、`$display`、`$fwrite` 记录，无。
   - 平局第 5 种：本轮不移动任何事件；合法域让 `rst` 与抽头码离时钟沿至少 0.5 ns，修正 r3 按实际完成时刻的扫描没有平局，第 5 种没有新增。
   - cross 返回根（SL-DEC-20261029-05 及 2b6b7d8e 的补充，return_roots_r5.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/return_roots_r5.py`））：参考解只在 `clk`、`rst` 上用 `cross(…, +1)`，没写 time_tol（缺省 1 s），只看 expr_tol。expr_tol 按最宽的读法至多 0.70 µV；九例中两信号相邻两根至少相隔 502 ps，两根之间 |expr| 的最大值至少 200 mV。每一对都必须报两次，判决的次数可以评分，没有落在框内的。
   - idt：参考解与 45 个候选都没有 `idt`。pulse：10 个 pulse 源（前八例、公开 `base` 与 `visible_test.scs` 的时钟）都写了 `rise`、`fall`。
   - 整数操作数的 abs、min、max：主控粗扫 `intminmax-scan.json`（`95975f2d…`）在本题没有命中；参考解不用 abs、min、max。
   - 主控 05:42Z 补充的两条：一次性 `timer()`：参考解与全部候选都没有 `timer()`；候选 `clk_deglitch_0p6n` 在 `cross()` 事件里读 `$abstime` 与上一次下降沿比较，不是 timer，离 0.6 ns 的比较边界至少 98 ps（`min-pulse-vss-low` 的 0.502 ns 低电平）。`transition()` 的 td：参考解为 0，候选的 td 都是常数（0 或 0.2·`tr`），没有输入不变、只改 td 的写法。
4. 更正：修正 r3 一节“样板 r2.18–r2.21 新条目的核对”第 2 条说“本题台架没有穿越落在网格行上（生成器断言）”。这对 `clk`、`rst` 成立，对抽头码不成立：`base` 与 `history-pairs` 的抽头码边沿是 100 ps、拐点在 50 ps 网格上，斜坡中点 0.45 V 恰是 `vth`，落在网格行上（onlevel_rows.py（`runs/t3-p0-build-20261027/p0u17-fix-r5/scripts/onlevel_rows.py`））。`crossings()` 按规则把这一行当作穿越时刻；Spectre 若在这一行差 1 ulp，求得的穿越时刻也只差 1e-25 s 量级。抽头码只在离它至少 0.5 ns 的时钟沿上按电平读取，评分不受影响。原文不改。
5. 判决有变化的候选与控制：
   - VA 校准候选（旧版开发证据）：存档的 416 次旧版波形用新 checker 重判（各按运行时的用例字节），与记录的判决 0 项变化（全部行与只用网格行），与 `expected.json` 0 项不一致（407 项有预期）。
   - 合成控制：53 个模型 × 9 例的被拒集合与预期相同，新旧 checker 都如此；端点模型、证据控制 17/17、`min-pulse-vss-low` 的控制 5/5、余量控制 28/28、修正 r3 的余量控制 26/26、迟到可见性，新旧 checker 逐项相同。
   - 判决改变的只有本轮加的对照，与设计一致：变化不超过 δ 而期限内有 10 mV 偏移的波形、审核者的三个尖峰，改前通过，现在被拒。
6. Spectre 预校准：网表没有变；checker 改了 `slicer_in_dbg` 的变化判定，九个私有用例与公开 `base` 的评分都受影响。本题还没有当前参考解与台架的 Spectre 结果，参考解 10 个作业、45 个候选在九个私有用例上 405 个作业都应在包里，范围由主控定。
7. 交主控：
   - δ 的语义与 C109 相同（变化不超过 δ 时期望值保持原值），与 R01 三题（期望值更新、只是不开窗）不同；两种写法各自与题面一致，统一要改评分结构。
   - `crossings()` 判“某行恰在门限上”仍用精确比较；上面第 4 条的抽头码行恰在门限上，用 0.1 mV 的带宽也得到同一个穿越时刻。是否按第 20 条改写，由主控定。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

建题时做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/checks.json`）：
- 包装检查与单题静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制（上面第 17 条）；
- 旧版 EVAS 0.8.7 冒烟（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑），记录在 legacy-evas.json（`runs/t3-p0-build-20261027/r06-spec-dfe-two-tap/legacy-evas.json`）：
  - 参考解在 6 个私有用例和公开 `base` 上都通过 checker，最大误差 0.0 mV；旧版多输出的过渡四分点行去掉后只用网格行重判，判决不变；
  - 起始模型只声明接口，旧版在降阶时报 `no_continuous_linear_ir`；
  - 40 个校准候选在 6 个用例上的 240 次运行与 `expected.json` 全部一致：35 个错误模型在必须拒绝的用例全被拒，在其余用例通过；5 个正确替代与余量对照全部通过（误差 0.0 mV）。被拒误差最小的是 `slow_output_1p3tr`（17.3 mV，`param-override` 21.2 mV）、`tap_bits_swapped` 在 `reset-restart` 与 `taps_one_decision_old` 在 `base`（20 mV）；
  - 没有 `hierarchical_columns_all_zero` 或时间行去重诊断；按 r2.16 核对，这些通过没有被旧版的零点处理掩盖（第 14 条）；
- EVAS 02dee32b 阶段 a–c：参考解在全部 7 次运行（6 个私有用例与公开 `base`）都停在阶段 c，首个诊断是已知的 `kernel.step_budget`（`source transition proof budget exhausted: slot 2`，NF-01）；起始模型在阶段 a 报 `module requires an analog block or child instances`。两个探针（scratch 中的副本，题包未改）：把 `base` 截到 12.5 ns（两次判决）时阶段 c 完成，checker 通过、误差 0.0 mV，说明失败来自运行长度的预算；三模块的 `alt_modules` 在阶段 b 报新诊断 `unsupported_event_context`（`ordinary integer alias requires an executable capture`，第 14 行：反馈求和模块在连续语句里给整数变量赋值），交主控转 EVAS。后续（u17-fix-r1 补记）：EVAS 线只做编译核对后确认，这条诊断属 EVAS 回退，由 [#243](https://github.com/BucketSran/vaEVAS/pull/243) 带来：#243 之前的 2a790344 能编译，之后的 d6b7543f 报错，把 k1–s2 改成 real 后两个版本都能编译。这条记在回退总 issue [#287](https://github.com/BucketSran/vaEVAS/issues/287) 的评论里。候选写法合法，不改。这些都是开发证据，不是 EVAS 能力验收或校准；
- Docker 两个镜像实际构建一次并检查。

u17-fix-r1（2026-10-29，处理独立审核 r1 的四条发现与打断意见）另做了下列检查，命令、退出码与结果见 disposition.json（`runs/t3-p0-build-20261027/u17-fix-r1/disposition.json`），仍未仿真：
- 两个端点用例的构造核对（第 12 条）与合成控制（第 17 条）；
- 旧版 EVAS 0.8.7（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑），记录在 u17-fix-r1 的 legacy-evas.json（`runs/t3-p0-build-20261027/u17-fix-r1/legacy-evas.json`）：
  - 参考解在两个端点用例上通过 checker，最大误差 0.0 mV；
  - 42 个校准候选在两个端点用例上的 84 次运行、两个新候选在原六例上的 12 次运行，全部行与只用网格行的判决都与 `expected.json` 一致（98 次中 98 次）。被拒误差最小的是 `slow_output_1p3tr` 在 `param-endpoints-low` 的 9.2 mV 和 `tap_bits_swapped` 在同一例的 10 mV；`tr_floor_100p` 在原六例和 `param-endpoints-high` 通过（误差 0.0 mV），在 `param-endpoints-low` 被拒（349.2 mV）；`second_tap_ignored` 在八个用例都被拒；
  - 没有 `hierarchical_columns_all_zero` 或时间行去重诊断；按 r2.16 核对，新用例也只在外部驱动的 `clk`、`rst` 上用 `cross()`，这些通过没有被旧版的零点处理掩盖；
- 包装检查、单题静态检查，Docker 两个镜像重新构建一次并检查。

u17-fix-r2（2026-10-29，主控交办的 H4 与 H6：加 `min-pulse-vss-low`，补“空历史当高判决”的候选）另做了下列检查，命令、退出码与结果见 disposition.json（`runs/t3-p0-build-20261027/u17-fix-r2/disposition.json`），仍未仿真：
- 新用例的构造核对与余量断言（第 12 条），原八例时间下界的精确扫描；
- 合成控制（第 17 条），原八例逐项与 u17-fix-r1 相同；
- 旧版 EVAS 0.8.7（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑），记录在 u17-fix-r2 的 legacy-evas.json（`runs/t3-p0-build-20261027/u17-fix-r2/legacy-evas.json`）：
  - 参考解在 `min-pulse-vss-low` 上通过 checker，最大误差 0.0 mV；
  - 45 个校准候选在新用例上的 45 次运行、三个新候选在原八例上的 24 次运行，全部行与只用网格行的判决都与 `expected.json` 一致（70 次中 70 次，含参考解）。新用例上被拒误差最小的是 `slow_output_1p3tr` 的 38.5 mV；`empty_history_high` 在九例都被拒（最小 25 mV，`param-endpoints-low`）；`decision_floor_0v` 与 `clk_deglitch_0p6n` 在原八例都通过（误差 0.0 mV），只在新用例被拒（500 mV、2000 mV）；
  - 没有 `hierarchical_columns_all_zero` 或时间行去重诊断，网格行重判没有改变判决；按 r2.16 核对，新用例和新候选也只在外部驱动的 `clk`、`rst` 上用 `cross()`（`clk_deglitch_0p6n` 另用 `clk` 的下降穿越），这两个输入从不停在门限上，这些通过没有被旧版的零点处理掩盖；
- 包装检查、单题静态检查，Docker 两个镜像重新构建一次并检查。

u17-fix-r3（2026-10-29，第 (ii) 类：把 `reset-restart`、`isi-channel`、`param-endpoints-low` 恰在合同下界上的间隔挪开）另做了下列检查，命令、退出码与结果见 disposition.json（`runs/t3-p0-build-20261027/u17-fix-r3/disposition.json`），仍未仿真：
- 三例的构造核对、余量断言与九例的下界重扫（“2026-10-29 修正 r3”一节）；
- 合成控制，其余六例逐项与 u17-fix-r2 相同；
- 旧版 EVAS 0.8.7（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）：参考解与 45 个候选在三例上 138 次运行，全部行与只用网格行都与 `expected.json` 一致；
- 样板 r2.18–r2.21 新条目的核对；
- 包装检查、单题静态检查，Docker 两个镜像重新构建一次并检查。

p0u17-fix-r4（2026-10-29，第 (ii) 类：两例实例行的端点写法；审核 R4-02 的门限停下交主控）另做了下列检查，命令、退出码与结果见 disposition.json（`runs/t3-p0-build-20261027/p0u17-fix-r4/disposition.json`），仍未仿真：
- 两例的生成器重建、解析核对与合成核对，九例按 1 mV、1 fs 损失的下界重扫（“2026-10-29 修正 r4”一节）；
- 旧版 EVAS 0.8.7（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）：参考解与 45 个候选在两例的新字节上 92 次运行，全部行与只用网格行都与 `expected.json` 一致；
- R4-02 的门限推导，以及 scratch 里变体 checker 的尖峰控制与全矩阵重判（不进题包）；
- 样板 r2.26 新条目在改动处的核对；
- 单题静态检查，Docker 两个镜像重新构建一次并检查。

p0u17-fix-r5（2026-10-29，第 (ii) 类：`slicer_in_dbg` 的变化门限 δ = 0.1 mV 写进题面与 checker）另做了下列检查，命令、退出码与结果见 disposition.json（`runs/t3-p0-build-20261027/p0u17-fix-r5/disposition.json`），仍未仿真：
- δ 的上下界推导与评分容差核对，最小合法变化与审核者尖峰的对照，样本偏差控制（“2026-10-29 修正 r5”一节第 1 条）；
- 53 个模型 × 9 例、端点、证据与余量控制，在新旧 checker 上逐项比较；
- 旧版 EVAS 0.8.7 的存档波形用新 checker 重判（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）：416 次，与记录的判决 0 项变化；
- 下界重扫（不变），样板 r2.33/r2.35 新条目的核对，cross 返回根；
- 单题静态检查，Docker 两个镜像重新构建一次并检查。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量；p0u17-fix-r5 改了 checker 的 `slicer_in_dbg` 变化判定，预校准包按新 checker 判分（见“2026-10-29 修正 r5”一节第 6 条）；
- Spectre 上记录 `transition()` 的打断行为（`long-tr` 的两次复位在过渡中途改写目标，LRM §4.5.8 完成规则）和待发过渡（只出现在校准候选 `alt_delayed_within_tr` 的 0.2·`tr` 延迟中；参考解的延迟为 0）；参考解没有同刻事件（合法域把 `rst` 与时钟沿分开至少 0.5 ns），同刻事件的执行次序不适用；
- Spectre 上记录 `cross()` 的事件定位，以及 `alt_modules` 在时钟事件读另一个模块节点时读到的值（预期为事件之前的值）；`param-endpoints-low`（`tr = 10 ps`）的期望要求事件落在穿越后 0.7 ps 内，`min-pulse-vss-low`（`tr = 40 ps`）要求在 3 ps 内，校准时记录这两例的实际定位与余量；
- Spectre 上记录 `min-pulse-vss-low` 各控制输入保存样本与 PWL 的最大偏差和保存时刻的偏差，确认在余量所依据的假设（1 mV、1 fs）之内；u17-fix-r3 挪开下界的三处同样记录，其中 `reset-restart` 的 0.502 ns `rst` 高电平每端只能吸收 4.5 mV；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部 45 个候选，按 `expected.json` 比对；
- 用户确认上面两个“待用户确认”选择（第 7 条异步复位、第 8 条清零后 `slicer_in_dbg` 为 0 V）；
- 记录 `results/reference.json` 与 `results/calibration.json`。
