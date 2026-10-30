# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C105-S1，`unit_id` C105，`case_anchor` C105，来源 `src-40687b8cacee`，`primary_ref` C105，动作 S（spec-modeling），家族 R09，优先级 P0，结构难度 H，建设成本 M。登记见[规划登记](../../../../planning/history-candidates/register.json)中的 C105-S1 条目，来源身份见同目录 [sources.json](../../../../planning/history-candidates/sources.json)，规划说明见[候选说明](../../../../planning/history-candidates/CANDIDATES.md#c105-s1)。登记要求：
- reuse：两级量化、残差观测、两拍发布及 valid 接口；
- author_work：固定粗量化电平与残差闭式、第二级门限、样本缓存及连续/空拍对齐；补必要接口，不用固定五文件代替难度；
- difference：每个有效样本需穿越多阶段并保持归属；
- Grok 意见：完整修订原题仍未唯一规定粗电平与残差量化关系，采纳；两拍延迟已经明确，应沿用。复审评论另记"缺第一级电平是箱沿还是中心，以及第二级门限"。

主来源是 2026-10-22 历史净化修订后的 v4:343 题面，sha256 `c4e324ed877a3c672967b2a6a0a233a6ff05b9be43ae118dc5ef6ce27bb50313`。规划登记标为 local-only，原件在证据卷 `historical-purification-20261022/improve-packs/pipelineadctwostage/OUTPUT/instruction.md`（登记路径 `runs/historical-purification-20261022/improve-packs/pipelineadctwostage/OUTPUT/instruction.md` 在主工作区），不在本工作树。修订只比发布版 [v4:343 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/public/instruction.md)（sha256 `ac7f0ba1…a796e9ed`）多一条：`valid_o` 与完整 4 位码出现在 `valid_i` 采样沿之后的第二个 `clk` 上升沿，`valid_o` 只高一个时钟周期（修订包 D1，CHANGES.md sha256 `5e77f595…`）。原题沿用的事实：
- 顶层端口 `vin, clk, rst, valid_i, code_3, code_2, code_1, code_0, valid_o, residue_dbg`，参数 `vdd = 0.9 V`、`vss = 0 V`、`vref = 0.9 V`、`vth = 0.45 V`、`tr = 200 ps`；
- `valid_i` 在 `clk` 上升沿为高时第一级采样，在 `[vss, vref]` 的四个等分区间上给出 2 位粗码；残差为减去粗量化电平后乘 4；第二级在下一个上升沿把残差量化成低两位；
- 采样沿之后的第二个上升沿发布完整码并置 `valid_o`；`valid_o` 只高一个周期，不完成样本的上升沿之后为低；
- 越界输入钳到码 0 和 15；`residue_dbg` 给出第二级使用的第一级残差；复位清两级、码、`valid_o` 和 `residue_dbg`。

原 gold（[`pipeline_adc_top`](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/evaluator/solution/pipeline_adc_top.va)、[`stage1_quantizer`](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/evaluator/solution/stage1_quantizer.va)、[`residue_amp`](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/evaluator/solution/residue_amp.va)、[`stage2_quantizer`](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/evaluator/solution/stage2_quantizer.va)、[`code_aligner`](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/evaluator/solution/code_aligner.va)）与修订包 GOLD 逐字节相同。它的 `residue_amp` 没有时钟，用实时 `V(vin)` 和第一级当前的粗码连续计算残差，不是"采样输入"的残差；复位期间残差为 `vss`，释放后按粗码 0 和实时输入算出（约 4·vin，钳到 `vref`）；`rst` 上升穿越异步清零，`rst` 为高的时钟沿也清零；`valid_o` 落下后码保持。原 checker 是修订包 `CHECKER_SOURCE/closure.py`（sha256 `31924229…`）中的 `check_v4_343_pipeline_adc_two_stage`：
- 期望码写死为 `min(15, int(16*vin/0.9))`，只在每个上升沿后 650 ps 读一次码和 `valid_o`；
- `residue_dbg` 只在采样沿后 650 ps 读一次，容差 60 mV；
- 复位只要求某一行 `rst` 高且码为 0、`valid_o` 低、残差小于 40 mV；
- 台架只有 6 个孤立样本（`valid_i` 为 3 ns 的脉冲），每个样本前后 30 ns 内 `vin` 不变，一次中途复位，参数从不改写。

修订包 DEFECTS.json（sha256 `c765cc6f…`）列出的覆盖缺口：粗码 2 从未出现；细码只有 0 和 3，`code_1` 恒等于 `code_0`，低两位互换看不到；没有连续采样，所以样本归属和"采样输入"与 gold 实时残差的差别都被掩盖；`valid_i` 门控没有反例；0.225 V 的样本正好落在门限上；复位只有一次，同步/异步、释放后残差、码保持还是清零都没写。本题不继承它的判据和成绩，这些缺口就是本题要补的。

并入的变体（规划 [GROK-REVIEW](../../../../planning/history-candidates/GROK-REVIEW.md) 与 pool-review 的处理）：
- `pipelineadcchain4b`：v4:096 的历史修订题面（`src-44b5d8afdac4`，local-only，证据卷 `historical-purification-20261022/improve-packs/pipelineadcchain4b/OUTPUT/instruction.md`，sha256 `ccc34089bc65944a7865161ba576a6dfc74c210687f335de04c31e3614ad965c`）。规划要求"优先复用本版本的中心/增益公式来收敛 C105 歧义，核对单调性而非盲信原 gold"。本题采用它的残差式 `RES1 = (vrefp + vrefn)/2 + 4*(clipped VIN - bin center)` 和"顶部四分位包含 vrefp"，见建模选择第 2 条。发布版 [v4:096 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/096-pipeline-adc-chain-4b/public/instruction.md)没有写中值偏移，这正是修订包的 D1。
- `pipelineadcchain`：[v1 vbr1_l2_pipeline_adc_chain e2e](../../../../../historyref/v1/tasks/CT01_data_converter_models/vbr1_l2_pipeline_adc_chain/forms/e2e/prompt.md)，单样本两级残差链，规划沿用 v4:096 的归并，不另计。

历史 Spectre 证据：按样板第3a节查了本机 `legacy/behavioral-veriloga-eval/results/`（含 `_local/v3_skeleton_dual_parity_cache/hidden/` 与各 `v3_spectre_audit*` 目录），没有 v4:343、v4:096、v3:105（`105-pipeline-adc-chain-4b`）或其他流水线 ADC 的 Spectre 运行；缓存中唯一的 ADC 项 `025-clocked-adc-quantizer` 是另一道题。v4:343 的 score_policy 记录的认证后端是 `rust_evas2`。参考解的事件语义因此只以 LRM 为据，Spectre 行为列入待办。

外部依据：
- [Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）：
  - §5.10.3.1 `cross()`：事件在阈值穿越之后、时间容差之内触发，t = 0 不产生事件；
  - §4.5.8 `transition()`：过渡被打断时按规定的起点完成，`td` 是传输延迟；
  - §5.10.3.3 `timer()`；§4.2 `floor()`。
  只引用定义，没有复制文字。
- [Wikipedia: Analog-to-digital converter](https://en.wikipedia.org/wiki/Analog-to-digital_converter)（2026-10-28 访问，页面最后修改 2026-09-19 03:33 UTC）的 pipelined ADC 一段：先做粗转换，用 DAC 求出与输入的差，再细转换，最后合并各级结果。CC BY-SA 4.0，只引用结构，没有复制文字。

外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r09-spec-pipeline-two-stage/sources.json`）。GitHub 代码检索（`pipeline adc`、`residue` 加 `valid`，扩展名 `.va`）只找到 Arcadia-1/behavioral-veriloga-eval 的历史题、本仓库自己的首批候选，以及一个没有 LICENSE 的课程仓库 BenjaminGao99/ECE581_PipelineADCModel（只看了目录名，没有读取或复制代码）。arXiv 检索到的流水线 ADC 论文摘要（例如 2201.08221）是电路实现，没有给出可用的行为合同。没有可复制的宽松许可代码，参考解是作者按新合同自写的。

记忆污染风险：中。原 v4:343 的题面、五个 gold 模块、评分台架以及 843 号测试台题的变异包都在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage) 中，与本仓库副本的 git 对象一致（题面 `8589f3f0`，`residue_amp` `2063f9ef`，`code_aligner` `ff5bb734`）。该仓库没有 LICENSE 文件。新合同改了模块名和交付形式，规定了保持样本的残差、复位后的残差、连续与空拍，并改写参数；原 gold 套上新模块名后在四个用例上都被拒（校准候选 `original_v4_343_gold`，旧版 EVAS 上 `residue_dbg` 与码都错）。参考解的写法（`cross` 采样、`transition` 输出、在同一个时钟事件里从输出端往前更新各级）是这类模型最常见的写法。

同源与职责，均不重复计数：
- 首批30题 [v2-spec-003-pipeline-adc-stage](../../../v2-01/tasks/v2-spec-003-pipeline-adc-stage/instruction.md)（`v4-003`，同属 R09）是单个 1.5 位 MDAC 级：`PHI1` 采样、`PHI2` 判决，三区间、`±VREF/4` 门限、增益 2 残差，没有 valid 标记、流水和对齐。本题是两个 2 位级、增益 4、没有冗余，职责是样本保持、连续样本的归属、两拍发布和空拍对齐，以及异步复位丢弃在途样本。本题的校准候选不是单级题的错误模型：单级题的相位、等号归属和三区间错误在本题不适用，本题的候选都针对多级链路和发布协议。
- 同单元的 P1 候选都不在本单范围，没有建题：
  - C089-S1（v4:003 历史修订）是单级的相位边界与"码和残差来自同一样本"；
  - C102-S1（Pipe15 Data Align，v4:181）是四组码以 0/1/2/4 拍不同延迟在同一时刻发布；
  - C103-S1（Pipe ADC Gain Control Loop，v4:194）是成对激励测量与增益码控制。
  本题只有一种两拍延迟，没有校准环路。
- 规划中的 C114-S1（九相 DFF 对齐）要求与 C105 比较差异，尚未建题。
- 旧41题中的 [integrate-pipeline-adc-alignment](../../../../../historyref/tasks/integrate-pipeline-adc-alignment/instruction.md) 是原创小工程（6 位，3 位粗级在上升沿、3 位细级在随后的下降沿，一拍后以单个电压 `0.01*N` 输出），动作是扩展集成，不在草稿分母内。它也要求连续采样时不混合两次转换，但没有 `valid_i` 门控、空拍、残差观测或参数改写。
- 第二批草稿与原56题：除 v2-spec-003 外，没有以 v4:343、v4:096 或 v1 pipeline chain 为来源的题；v3-01 的 converter 各题是 DAC 权重模型，没有流水。
- R01：采样家族，无同源。
- 本题 `source_group` 取新组名 `v4-343`；SOURCE_GROUPS 中原无此组，也没有 `v4-096` 或 `v4-003` 组（v2-spec-003 的 task.toml 用 `v4-003`）。

## 建模选择

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。第 1、3、4、5 条原标“待用户确认 1–4”，即待确认清单第 31–34 项，已定（用户 2026-10-29，决定单第 6 项），理由原文保留。

1. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 1”，即待确认清单第 31 项】接口：单文件单模块，模块名由 `pipeline_adc_top` 改为 `pipeline_adc_two_stage`，保留原顶层的 10 个端口和顺序，不要求五个文件和五个公开子模块（解题者可以在同一文件内自定义辅助模块），也不另加调试端口。
   - 理由：author_work 要求"补必要接口，不用固定五文件代替难度"。原 checker 只实例化顶层，子模块边界只能靠静态扫描。现有端口已经能观察四项职责：`residue_dbg` 看样本保持，码和 `valid_o` 看第二级门限、发布时刻和样本归属。补上的"必要接口"是参数合法域、输入合法域与时序义务、`residue_dbg` 的保持语义、复位与初态。改名是因为 `pipeline_adc_top` 暗示五模块层次，新名描述行为。
   - 另一种读法是保留五个文件与子模块端口，或者像 v4:096 那样另外引出两级判决位（`S1B1..S2B0`、`RES2`），让每级的时刻都可观察。后者会把内部级划分写进合同。
   - 推荐单模块、不加端口。
2. 粗量化电平与残差闭式（规划已定，不作为待确认项）：粗码 `k` 是 `vss + span/4`、`vss + span/2`、`vss + 3*span/4` 三个门限中不高于 `x` 的个数（等于门限归上一区间，`x = vref` 得 `k = 3`）；箱中心 `c = vss + (k + 1/2)*span/4`；残差 `r = (vss + vref)/2 + 4*(x - c)`；第二级用同样三个门限得细码 `f`；码为 `4*k + f`，等于 `floor(16*(x - vss)/span)` 并限到 15。
   - 这就是 v4:096 修订版的中心/增益式。它与"箱沿式" `vss + 4*(x - vss) - k*span` 恒等，所以复审问的"箱沿还是中心"由显式公式唯一确定；中心式配 `vss` 偏移、箱沿式配中值偏移这两种混合读法是校准候选，都被拒。
   - 单调性按规划核对：build_cases.py（`runs/t3-p0-build-20261027/r09-spec-pipeline-two-stage/build_cases.py`） 对四组 `(vss, vref)`（含两个参数端点）各扫描 16000 点，码不减，残差在 `[vss, vref]` 内，箱内斜率为 4，只在三个粗门限处下降一个量程。
   - 扫描还表明：正好落在码边界上时，两级组合与闭式在浮点下可以差一个码（例如 `vss = 0.2 V`、`vref = 1.0 V` 时的 `x = 0.3 V`）。合法域因此要求样本离码边界至少 3 mV，见第 7 条。
3. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 2”，即待确认清单第 32 项】样本缓存：第一级保持 `x`、`k`、`r`，直到下一个取样的时钟沿或复位；`residue_dbg` 驱动第一级保持的 `r`；第二级在下一个时钟沿按该沿之前保持的残差判决，同一沿采入的新样本不影响这次判决。
   - 依据：原文"for the sampled input"和"the stage-1 residue used by stage 2"；真实流水级先采样保持再放大；这样原 gold 的实时残差错误可以被看到。
   - 用例让 `vin` 在每个采样沿后约 2 ns 就变到下一个值，`stream-irregular` 还在斜坡上采样，所以实时残差、时钟高电平期间跟踪、只保持一个周期都会被拒。
   - 另一种读法是残差只在第二级使用的那个周期有效、之后回到 `vss`，或者像原 gold 那样跟随实时输入。
   - 推荐保持到下一个样本或复位。
4. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 3”，即待确认清单第 33 项】两次结果之间码保持：不发布结果的时钟沿只把 `valid_o` 拉低，码保持上一次的值，复位才清零。依据是原 gold；原题面没有写。另一种读法是 `valid_o` 落下时码也清零。推荐保持；`code_zero_between_results` 是对应的错误模型。
5. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 4”，即待确认清单第 34 项】复位：`rst` 上升穿越立即清零（异步），在途样本全部丢弃且永不发布，码为 0、`valid_o` 低、第一级保持 `x = vss` 因而 `residue_dbg = vss`；`rst` 为高时上升沿不采样、不发布；下降穿越没有作用，之后第一个时钟沿就能采样（没有预热）；t = 0 与清零状态相同。
   - 依据：原 gold 是异步清零加"高电平期间的时钟沿也清零"，两者在本合同下等价。新合同只改了释放后的残差：原 gold 释放后按实时输入算出约 4·vin，本题保持 `vss` 到下一个样本，与第 3 条的缓存语义一致。
   - `reset-recovery` 里 `rst` 在发布沿后 100 ps 上升，正好打断输出过渡（修正 r7a 起为 101.875 ps，即合同下界 100 ps 加 1.875 ps 余量，仍在输出过渡的一半处，见修正 r7a 一节第 2 条）；两个 `rst` 脉冲落在时钟沿之间，同步复位看不到它们。
   - 另一种读法是同步复位（只在 `rst` 为高的时钟沿生效）。
   - 推荐异步。
6. 两拍发布与 valid（沿用修订题面，Grok 已认可）：采样沿 `n` 的样本在沿 `n + 2` 发布；流水线在每个时钟沿推进，不论该沿是否取样；不发布结果的时钟沿 `valid_o` 变低；连续样本在连续的沿发布，`valid_o` 中间不落。延迟按时钟沿计，不按时间计：`stream-irregular` 的沿间隔 4–21 ns（修正 r7a 起 4.05–21 ns），且在一次发布后停钟 60 ns，`valid_o` 在停钟期间保持高。
7. 同刻与合法域（原题没有）：
   - `valid_i`、`rst` 的每次穿越离每个 `clk` 上升穿越至少 100 ps；`clk` 相邻上升穿越至少 4 ns；同一输入相邻穿越至少 100 ps；
   - 每个 `clk` 上升穿越前后 100 ps 内 `vin` 变化小于 0.25 mV，所以事件定位误差几乎不影响样本值，残差（增益 4）误差小于 1 mV；
   - 每个样本离码边界 `vss + j*span/16`（j = 1–15）至少 3 mV；
   - `vin` 在 `vss - 0.2 V` 到 `vref + 0.2 V`，控制输入在 0–0.9 V，t = 0 时离 `vth` 至少 50 mV，`clk` 从低开始；控制输入到达 `vth` 时必定穿过，不触碰后返回（p0-fix-c 按第 38 项的推荐写入，见 p0-fix-c 一节；用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版）；
   - 参数合法域：`vss` −0.5 到 0.5 V，`vref - vss` 0.4 到 2 V，`vdd - vss` 0.5 到 2 V，`vth` 0.2 到 0.7 V，`tr` 10 ps 到 1 ns。
   在此域内没有判决取决于同刻或事件定位。台架实际余量：码边界最近 4.28 mV（`stream-irregular` 斜坡），`vin` 在上升沿附近最大变化 0.18 mV。修正 r7a 挪动之后这两个数不变。
8. 评分起点（F01）——用户已确认（2026-10-28）：F01 选 A。题面写明实际观察起点：每次期望输出变化后 `1.25*tr` 内的点不评分，其余保存点都评分；checker 不改。另加评分起点之后才到达的负例：
   - `clk`、`rst`、`valid_i` 的穿越都对齐在输出网格的相位 `0.9*g`，评分起点后的第一个点在 `1.275*tr`；
   - `slow_output_1p3tr` 在四个用例都被拒：合成控制 17.3 mV（`param-override` 19.2 mV），旧版 EVAS 相同；
   - 输出台阶不小于 104 mV 的事件都能看到 1.3·tr 的迟到：`base` 35/35，`stream-irregular` 59/59，`param-override` 25/25，`reset-recovery` 23/24。唯一的例外是被 100 ps 后的 `rst` 打断的那个发布沿，它没有属于自己的评分点（修正 r7a 起 `rst` 在 101.875 ps，例外不变）；
   - 1.2·tr 到达的合成输出通过全部用例，这是 F01 选 A 的已知性质；
   - 建题时发现：`tr = 100 ps`、网格 25 ps 时，若沿用 `g − 5 ps` 的相位，评分起点后的第一个点正好在 1.3·tr，1.3·tr 负例看不到。相位因此改为 `0.9*g`。
9. 误差上限 2 mV，对所有输出（含 `residue_dbg`）都适用：残差是保持值，正确实现在旧版 EVAS 上误差 0.0 mV；合法域保证样本值误差远小于 0.5 mV。评分波形步长不粗于 `tr/4`。
10. 台架：四个用例，输出网格 `maxstep = strobeperiod = tr/4`，所有 PWL 拐点都在网格上，checker 由行数据读穿越时间和样本值时没有插值误差。
    - `base`（公开兼终评，默认参数，10 ns 时钟，40 个沿）：上电复位覆盖一个 `valid_i` 为高的沿；孤立样本，2、3、5 个连续样本，单个和两个空拍；`valid_i` 在沿前、沿后 0.3 ns 变化；粗门限两侧各 5 mV 的样本、低于 `vss`、高于 `vref` 和正好等于 `vref` 的样本；两沿之间的 `rst` 脉冲丢弃两个在途样本并清掉已发布的码；16 个码全部发布。
    - `stream-irregular`（默认参数，82 个沿）：不规则时钟；`vin` 以 1.8 mV/ns 从 −0.03 V 斜升到 0.95 V，在移动中采样，含 14 个连续样本和混合空拍；之后是阶跃输入、连续与空拍，以及发布后的 60 ns 停钟。
    - `reset-recovery`（默认参数，7 ns 时钟）：上电复位覆盖三个 `valid_i` 为高的沿；释放后第一个沿就采样；发布沿后 100 ps 的复位；覆盖三个沿的复位；一级各有一个在途样本、`valid_o` 低而码保持 3 时的复位脉冲；结果 10 正在显示时的复位脉冲；每次释放后 `residue_dbg` 保持 `vss` 直到下一个样本。
    - `param-override`（`vss = 0.2 V`、`vref = 1.0 V`、`vdd = 1.2 V`、`vth = 0.3 V`、`tr = 100 ps`）：0.2–1.0 V 上的码，低于 `vss` 和高于 `vref` 的输入、比 `vss` 高 30 mV 的输入；只到 0.4 V 的 `clk`、`valid_i` 和 `rst` 脉冲，只对 0.3 V 门限起作用。这是 F08 的教训：改写的参数要能被看出。
    台架由 build_cases.py（`runs/t3-p0-build-20261027/r09-spec-pipeline-two-stage/build_cases.py`） 生成，生成时断言台架义务，并用独立的合同模型核对设计的发布序列。
11. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：
    - 从记录的输入按相邻行线性取穿越时间和样本值，按规则推出每次输出变化；t = 0 的初值必评；
    - 穿越提取用六题统一的规则（p0-fix-c，审核 R2-01；p0-fix-b 先按 F02 改成按两侧符号变化识别）：每个保存点与 `vth` 精确比较，恰在 `vth` 上的点不属于任何一侧；相邻两个不在 `vth` 上的点分处两侧时记一次穿越，中间恰有一个阈值点时穿越时刻就是该点，否则按两点线性插值；到达 `vth` 后返回原侧的孤立触碰不是穿越；连续两点停在 `vth` 上违反"不停在 `vth`"，抛出异常、不判分；记录末尾单个阈值点按到达方向算一次穿越；记录开头的阈值点不生成穿越（起始离 `vth` 不足 50 mV 本来就是台架错误）；
    - 台架义务出错时抛出异常（无判决，不记候选失败）：分辨率、参数超域、输入超域、起始电平离 `vth` 不足 50 mV、`clk` 不从低开始、穿越不交替或间距不足、上升沿间距不足 4 ns、`valid_i`/`rst` 离上升沿不足 100 ps、`vin` 在上升沿附近变化过大、样本离码边界不足 3 mV、同一控制输入相邻两次穿越之间离 `vth` 不足 50 mV（修正 r7a 加，保存行上不足 49 mV 才报）；
    - 证据有效性规则（p0-fix-c 写明，题面不改）：记录里至少要有一个 `clk` 上升穿越，没有时抛出异常、不判分。这不是对候选的行为要求：时钟是理想的外部源，候选改变不了它；没有时钟沿的记录不足以证明时钟电路执行完整，所以归为证据无效，不记候选失败。终评台架都有真实的时钟沿。以后若加入合法的静态或纯复位用例，要在台架里写明允许无时钟沿并评初态，或者用期望输入的身份判定记录是否丢失；
    - 结果另报流水统计（时钟沿、复位中的沿、样本、发布、被复位丢弃、连续样本、空拍、发布的码集合、最小码余量）；
    - 不依赖任何仿真器特有行，旧版 EVAS 只用规则网格行重判时结论不变。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
12. 参考解按 LRM 写，没有为任何 EVAS 版本改写：
    - `rst` 与 `clk` 是两个独立的 `cross` 事件，没有用 `or` 合并后在事件里读复位；`cross` 时间容差取 1 ps；
    - 一个时钟事件里从输出端往前更新：先发布第二级寄存器，再让第二级按保持的残差判决，最后第一级采样；
    - `transition` 零延迟驱动六个输出；只用标量状态，没有数组、`absdelay`、定时器或待发事件。
13. 校准候选见 [tests/calibration](tests/calibration/README.md)：36 个错误模型、4 个正确替代实现（采样沿一次算码再经两级寄存器、三模块层次、快过渡、延迟后在 tr 内到达），被拒矩阵另存为 `expected.json`。原 gold 套壳候选只在仓库内生成。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r09-spec-pipeline-two-stage/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制，含参数端点用例；
- 旧版 EVAS 0.8.7 冒烟，含参考解、起始模型和全部校准候选（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）；
- EVAS 02dee32b 阶段 a–c 及两个探针；
- Docker 两个镜像实际构建一次并检查。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量与评分起点后第一个点的实际位置；
- Spectre 上记录 `cross()` 事件的定位精度（参考解时间容差 1 ps），确认它远小于 100 ps 的间隔和 0.25 mV 的 `vin` 静止要求；
- 样板第4a节的待发事件：参考解没有待发事件（`transition` 延迟为 0，也没有定时器），这一项对参考解不适用。Spectre 运行时仍记录：
  - `transition()` 被打断时的完成方式：`reset-recovery` 45.045 ns 的发布沿后 100 ps 复位（修正 r7a 起 101.875 ps）；
  - 校准候选 `alt_delayed_within_tr` 的传输延迟过渡和 `valid_5ns_pulse` 的定时器改期；
  - `alt_three_module_hierarchy` 中一个模块在时钟事件读另一个模块 `transition()` 输出节点时读到的是事件前的值；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 上面四个原“待用户确认”选择已定（用户 2026-10-29，决定单第 6 项，即待确认清单第 31–34 项）；清单第 38 项已定（用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版），见 p0-fix-c 一节；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## p0-fix-b 修正（2026-10-28）

依据铺开六题独立审核 r1（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）的 F02。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-b 处置记录（`runs/t3-p0-build-20261027/p0-fix-b/disposition.md`）。本题**未仿真**：没有运行 Spectre，旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

- 问题：checker 原先把"到达 `vth` 后返回原侧"的孤立触碰记成一次单向穿越。`clk` 触及 `vth` 而 `valid_i` 为高时，checker 假定一次采样并要求 `residue_dbg` 变化；`rst` 触及时假定清零；正确的输出被误拒。若触碰之后还有真实的上升沿，原 checker 会报"穿越不交替"而不评分。
- 改动：只改公开与私有两份 checker 的穿越提取，规则见建模选择第 11 条，两份逐字节相同。题面、参考解、用例、公开台架和校准件都不变。
- 复核：触碰后返回与恰有阈值行的真实穿越各有正反对照（合成波形），修正前触碰类对照判错或不评分、修正后判对；恰有阈值行的穿越前后都判对；建题时的全部合成控制在新 checker 上重跑，结论不变；参考解在旧版 EVAS 上通过全部私有与公开用例；建题时存档的旧版波形用新 checker 重判，判决全部不变。
- 未改的一处：checker 仍要求记录中至少有一个 `clk` 上升沿，没有时抛出异常、不评分。题面没有写这条台架义务；终评用例都满足，对评分没有影响。审核给出的单次触碰波形里没有真实的时钟沿，所以修正后它落在这条检查上（不评分），而不是被误拒。（p0-fix-c 起作为证据有效性规则写进建模选择第 11 条，题面不改。）
- 终评台架没有恰好触及 `vth` 的输入。（p0-fix-c 更正：这里原写“仿真器的 `cross()` 遇到恰好触及阈值又返回的输入是否触发，本题没有记录”，不准确。归档的 Spectre 21.1.0.509 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 显示，`cross()` 在输入恰好到达阈值时按到达方向触发一次，孤立触碰后返回也触发，离开时不触发。p0-fix-c 已按第 38 项的推荐在题面排除触碰。这份记录用的是显式 PWL 实验，参考解在本题台架上的行为仍待 Spectre 复跑。）

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-01、F02 剩余部分与对 C105 时钟沿规则的意见，以及Benchmark 维护方 2026-10-28 对清单第 38 项的安排。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解、用例、公开台架和校准件都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 终点事件（R2-01）。p0-fix-b 的写法丢掉记录末尾单个恰在 `vth` 上的行，终点处到达的事件就没有不评分窗。在修正前的字节上复现：沿用 p0-fix-b 的“`rst` 触碰”场景，记录截在 30 ns，`rst` 在最后一行从下方恰到 0.45 V；此前码 5、`valid_o` 为高，全部输出在最后一行立即清零，被拒 0.9 V；p0-fix-b 之前的写法接受它。现改为六题统一的穿越规则（第 11 条），这条输出通过，提前 1 ns 清零的输出仍被拒。终点事件照样受间隔约束：`rst` 离 `clk` 上升沿 55 ps 时报台架错误，105 ps 时照常评分。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 【第 38 项，已按推荐写入；用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版】控制输入到达门限时必定穿过。题面合法输入一段在“at t = 0 each of them is at least 50 mV away from `vth`.”之后加一句：“A control input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”“不停在 `vth` 上”和起始 50 mV 原已写明，不重复；checker 不变。另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
3. 时钟沿规则（复审意见第 5 项）：checker 要求记录里至少有一个 `clk` 上升穿越，这条现在作为证据有效性规则写进第 11 条，题面不改。
4. 更正 p0-fix-b 一节最后一条：归档的 Spectre 记录存在，原句“本题没有记录”不准确。
5. 复核：
   - p0-fix-b 的 F02 对照 11 个在新 checker 上判决不变（其中原审核的单次触碰波形仍因没有时钟沿而不判分）；p0-fix-b 的合成控制副本在新 checker 上全部符合预期，与存档相比判决与误差 0 项变化。
   - 建题以来的旧版存档波形用新 checker 重判，判决与误差 0 项变化。本题用例未改，没有新的旧版运行。
   - 平局扫描（精确有理数）：参考解的过渡终点都不在输入穿越上。事件与事件同刻的 41 处都有一方是 `clk` 下降穿越或 `valid_i` 穿越，它们都不是本题的事件（`valid_i` 只在时钟沿读电平），不算平局。

第 38 项的三个前提（Benchmark 维护方 2026-10-28 定的口径，也作复审口径）：
- 内部恰为零：参考解的事件只看外部驱动的 `clk` 与 `rst` 上升穿越，`valid_i` 与 `vin` 只在时钟沿读取；没有被测模块内部恰为零的信号参与事件或判决，无需核对。执行细则（Benchmark 维护方 2026-10-28 转标准审核口径，p0-fix-d 写入，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。本题参考解只对外部驱动的 `clk`、`rst` 用 `cross()`，符合（p0-fix-d 核对）。
- 相等规则写成输出行为：粗码与细码写成输出码的规则（不高于样本的门限个数，即相等归上一区间），合法输入让样本离每个码边界至少 3 mV，不出现相等；输入恰在 `vth` 上由合法输入排除（第 2 条）。
- 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。

## 2026-10-29 修正 r7a

依据：扫描 B（`runs/t3-spectre-wave2-20261029/scan/round-b/report.md`）第 2.3 节（第 (ii) 类：用例里的间隔恰好等于合同下界）、第 4 节补o 与补p、第 7 项 (k)；项目协调方 2026-10-29 的决定（第 (ii) 类定甲，补p 照 C061，P0 各题写入容差，补o 本轮定 δ）；网表约定清单第 4.12 版第 20 条与样板 r2.37 第 3 节；用户 2026-10-29 答复的决定单（第 6 项）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-p0-build-20261027/p0-fix-r7a/disposition.md`（不入库）。参考解、`task.toml`、共用文件与校准候选都没有改。本节的检查都**未仿真**：没有运行 Spectre 或模型；合成控制是 Python 波形；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. **`stream-irregular` 的时钟间隔**（扫描 B 第 2.3 节，第 (ii) 类，甲）。
   - 13 对相邻上升沿恰为 4 ns，每对把后一个时钟脉冲（上升、下降两沿，六个拐点）挪后一个网格步 50 ps。605.295/609.295/613.295 ns 连着两个 4 ns，后两个脉冲分别挪 50、100 ps。
   - 间隔都成了 4.05 ns；下一段相应缩短 50 ps（连着的那一串，最后一段缩短 100 ps），全例最短的上升沿间隔是 4.05 ns。余量下限是两端各 1 mV/斜率 + 1 fs 之和，10 mV/ps 边沿为 0.202 ps；50 ps 是它的 247 倍，且不超过一个网格步。
   - 穿越仍在网格相位 0.9·g。挪动的沿离 `valid_i` 的穿越至少 1.95 ns（全例最近的仍是开头的 1 ns，没变）；`vin` 的拐点离任何上升沿至少 1.855 ns（原为 1.945 ns）。
   - 斜坡段上有 6 个取样的沿跟着挪了，样本最多变 0.09 mV，残差最多变 0.36 mV。码序列不变，码边界余量最小仍是 4.28 mV，`vin` 在上升沿附近最大变化仍是 0.18 mV。
2. **`reset-recovery` 的复位离沿**。
   - 45.145 ns 的 `rst` 上升穿越离 45.045 ns 的发布沿恰为 100 ps。
   - 整网格步不可行：挪到 150 ps 后，一个“等当前过渡走完再走复位过渡”的输出恰在复位后 1.25·`tr` 到达。合同不容这种输出（打断后 `tr` 内要到达），但到达时刻正是评分起点，评分行上看不出。建题的合成模型 `interrupted-transition-queued` 只靠这一例拒绝，挪整网格步后它就通过了。
   - 所以改用样板中段拐点的办法：`rst` 上升沿的中段拐点由 0.5 V 改为 0.48 V，拐点仍在网格上。穿越移到 45.146875 ns，离沿 101.875 ps，余量 1.875 ps，是两端损失下限 0.206 ps 的 9.09 倍。
   - 穿越的网格相位由 0.9·g 变为 0.9375·g，偏移在 ±0.05·`tr` 以内。复位后评分起点之后的第一个点在起点后 3.125 ps，原为 5 ps。1.3·`tr` 迟到负例照样被拒，合成误差 23.8 mV，原为 17.3 mV；排队过渡照样被拒，202.5 mV。
3. **其余用例**：`base`、`param-override` 与公开 `base` 没有恰在界上的间隔，激励不改。
   - 核对（精确有理数，未仿真）：四个私有用例与公开 `base` 恰在界上 0 处；没有精确同刻或相差 64 ulp 以内的事件；复位打断的过渡都在斜坡中途。
   - 合成控制：把近界间隔两端穿越附近的保存行各推 1 mV、1 fs，改后用例 14 对都不报台架错误；改前同样的扰动 14 对都报。
4. **相邻两次穿越之间离门限至少 50 mV**（扫描 B 第 4 节补p，照 C061 的决定）。
   - 题面合法输入一段加一句：“Between two successive crossings of `vth` by one control input, that input moves at least 50 mV away from `vth`.”
   - 两份 checker（逐字节相同）对 `clk`、`rst`、`valid_i` 加台架判定：同一输入相邻两次穿越之间，保存行上 `|V(input) - vth|` 的最大值小于 50 mV 减 1 mV 就 `raise ValueError`，记 checker_error。
     - 只涉及一个保存节点，所以减 1 mV；C061 是两个节点之差，减 2 mV。
     - 只读保存行，台架的极值要落在平台上或保存行上。
   - 现有用例最小偏离 0.1 V（`param-override` 只到 0.4 V 的脉冲对 0.3 V 门限），判决不变。
   - 合成控制（未仿真）：`valid_i`、`rst`、`clk` 的平台离门限 40 mV 时报台架错误，60 mV 时通过。`valid_i` 恰为 50 mV 与 49 mV 两处照 C061 只作平局诊断，不写预期，结果分别是通过与报错（binary64 下离门限 0.04999999999999999 V 与 0.04899999999999999 V，报错门槛 0.049 V）。
5. **`residue_dbg` 的变化门限 δ = 0.1 mV**（扫描 B 补o，第 20 条）。
   - 改前，checker 对期望向量（码、`valid_o`、`residue_dbg`）用精确比较决定是否开不评分窗。`residue_dbg` 的期望值由采样的 `vin` 算出，合同允许任意小的合法变化。
   - 现在：码与 `valid_o` 由整数状态算出，照旧精确比较；期望 `residue_dbg` 变化超过 δ 才算变化，δ 以内的变化不开窗，期望值保持原值。题面与两份 checker 同改。
   - 下界：清单第 20 条的 10×(vabstol + reltol×|v|max)，reltol 取 options 的 1e-6 乘 moderate 的 1，vabstol 1e-8。
     - 本题各网表 |vin| 最大 1.15 V，单量 11.6 µV，两量相加 23.2 µV。
     - 计入第一级增益 4（残差 = 4·x + 常数，|x| 最大 1.0 V），两量相加 80.8 µV。
     - δ 是这三种读法的 8.6、4.3、1.24 倍。
     - 合同允许的最宽参数（|vin| 到 2.7 V，|x| 到 2.5 V）：前两种读法 27.1、54.2 µV，δ 仍够；计入增益的读法 0.2 mV，δ 不够。这一点交Benchmark 维护方定。
   - 上界：合同允许任意小的合法变化，要分辨的最小变化就是 atol 2 mV，上界取一半 1 mV。
   - 缺省容差（reltol 1e-3、vabstol 1e-6）下，单量下界约 11.5 mV，已超过上界，所以 δ 必须配合写入的容差。
   - 合成控制（未仿真）：码不变、只有残差变化的一串样本，在变化后的期限内给 `residue_dbg` 加 10 mV 的偏离。残差变 0.11 mV 时开窗，通过；变 0.09 mV 时不开窗，被拒；0.10 mV 只作平局诊断。没有偏离时，0.09 mV 的变化也照常通过。
   - 现有用例里只改残差的变化最小 20 mV，判决不变。`param-override` 里有一处两个名义相等的残差在 binary64 下差 3.3e-16 V，改前算一次变化，现在不算。
6. **写入容差**（扫描 B 第 7 项 (k)，第 (ii) 类）。
   - 写入的位置与字节照 P0PC 的作业网表：`tran` 之前插 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，`tran` 行末补 `errpreset=moderate strobeoutput=strobeonly`。
   - 没改激励的 `base`、`param-override`、公开 `base` 与 `visible_test.scs`：写入后的网表加执行路径一行，与 P0PC must-01（包 `spectre-P0PC-must-01-v1`，结果包 sha256 `56bb45ddcc96029e2ee7bd556bdd9b26db70f2186f91bff0653353d43b837ad6`）的同例带容差作业逐字节相同；去掉写入的两处后，加执行路径一行，与缺省容差对照作业逐字节相同。所以已核收的这些 P0PC 结果仍然作数，用新 checker 重判即可。
   - 改了激励的两例：同一规则作用在改前网表上，与 P0PC 作业逐字节相同。
7. **expr_tol 核对**：写入容差后最宽 expr_tol 最大 0.601 µV（`param-override`），50 mV 是它的 8.3e4 倍以上；缺省容差对照最大 0.6 mV，83 倍。相邻两根之间的最小偏离 0.1 V，不小于 50 mV。
8. **状态**：建模选择第 1、3、4、5 条（待确认清单第 31–34 项）已定，用户 2026-10-29，决定单第 6 项。只改状态，理由原文保留。
9. **校准**：
   - 被拒矩阵与 `expected.json` 不变。
   - 旧版 EVAS 0.8.7 在改后的 `stream-irregular`、`reset-recovery` 上重跑参考解与 40 个候选，参考解另跑公开 `base`，共 83 次，全部评分。参考解全部通过；候选与 `expected.json` 逐项一致，只用网格行重判的结论相同。
   - 建题的 47 个合成模型在改前、改后用例上的判决都相同，最大误差有 2 处小变化。
10. **Spectre**：改了激励的用例上要重跑 84 个作业（必须 4：参考解与缺省容差对照；建议 80；可选 0），清单在 `runs/t3-p0-build-20261027/p0-fix-r7a/spectre-jobs/`，本轮不打包。

## 2026-10-29 修正 r8

依据：项目协调方 2026-10-29 对修正 r7a 的核收意见（同意 `reset-recovery` 的次网格余量；δ 改为 0.25 mV）；网表约定清单第 4.13 版第 0.5 节第 20 条与样板 r2.37 第 3 节。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-p0-build-20261027/p0-fix-r8/disposition.md`（不入库）。本轮只改题面一句、两份 checker 的一个常数、校准说明与本文件；用例、参考解、`task.toml`、共用文件与校准候选都没有改。本节的检查都**未仿真**：没有运行 Spectre 或模型；合成控制是 Python 波形；重判只读已交回的 Spectre 波形和已存档的旧版波形。修正 r7a 一节原文不改。

1. **`residue_dbg` 的变化门限 δ 由 0.1 mV 改为 0.25 mV**。这是修正 r7a 一节第 5 条末尾留待 Benchmark 维护方定的一点，项目协调方 2026-10-29 定为 0.25 mV。
   - 依据：第 20 条要求 δ 覆盖整个合法域。按合同允许的最宽参数，下界是 0.2008 mV，0.1 mV 只有它的 0.498 倍。
   - 题面评分一段的 “δ = 0.1 mV” 改为 “δ = 0.25 mV”，其余字不动。两份 checker 的 `DELTA` 由 `1e-4` 改为 `.25e-3`，改后逐字节相同。不超过 δ 的变化照旧不开窗，期望值保持原值。
2. **下界的算式**（精确有理数核对）。
   - 合法域：`vss` 在 −0.5 V 到 0.5 V，`vref - vss` 在 0.4 V 到 2 V，所以 `vref` 在 −0.1 V 到 2.5 V。`vin` 在 `vss - 0.2 V` 到 `vref + 0.2 V` 之间，即 −0.7 V 到 2.7 V，|vin| 最大 2.7 V。样本 `x` 限在 `[vss, vref]` 内，即 −0.5 V 到 2.5 V，|x| 最大 2.5 V。
   - 容差：六份网表都写入 reltol 1e-6、vabstol 1e-8 与 `errpreset=moderate`（倍数 1），reltol 取 1e-6。
   - 一个样本的噪声带：vabstol + reltol × |x| = 1e-8 V + 1e-6 × 2.5 V = 2.51 µV。限到 `vss` 或 `vref` 的样本就是参数本身，没有噪声带。
   - 残差 `r = (vss + vref)/2 + 4*(x - c)`，箱中心 `c` 由整数 `k` 与参数精确算出，所以残差的噪声带是 4 × 2.51 µV = 10.04 µV。
   - 比较的两边是新的期望残差和保持的期望残差，都由采样算出，两边相加：10 × (10.04 µV + 10.04 µV) = 0.2008 mV，与项目协调方给的数相同。
   - 上界：合同允许任意小的合法残差变化（`vin` 在一个码区间里自由），要分辨的最小变化取 atol 2 mV，上界是它的一半 1 mV。
   - δ = 0.25 mV 是下界的 1.245 倍，是上界的四分之一。
   - 别的读法也满足：计入增益时用 |vin| 2.7 V 代替 |x| 2.5 V，下界 0.2168 mV，δ 是它的 1.15 倍；不计增益的单量、两量读法分别是 27.1、54.2 µV。只按本题现有网表算（|x| 最大 1.0 V，`param-override`），计入增益的下界是 80.8 µV。
   - 与 atol 的关系：按新样本更新残差的正确实现，与保持的期望值最多差 δ；再加上合同允许的样本误差（上升沿前后 100 ps 内 `vin` 变化小于 0.25 mV，乘增益 4 是 1 mV），共 1.25 mV，仍小于 atol 2 mV。
3. **合成控制**（未仿真，照修正 r7a 第 5 条的做法改到新 δ）：码不变、只改残差的一串样本，在变化后的期限内给 `residue_dbg` 加 10 mV 的偏离。
   - 残差变 1.1δ（0.275 mV）时开窗，通过；变 0.9δ（0.225 mV）时不开窗，偏离被评分，被拒（误差 10.17 mV）。
   - 没有偏离时，0.9δ、1.1δ 的变化都照常通过。
   - 恰为 δ 只作平局诊断，不写期望：checker 在 binary64 下算出的残差变化是 2.500000000000835e-4 V，比 `DELTA`（2.5e-4 的 binary64 值，2.5000000000000001e-4）大，算作变化，结果通过。
   - 改前的 checker 五例都通过：0.225 mV 也超过 0.1 mV，照样开窗。
4. **判决不变**（未仿真）。
   - 现有用例：只改残差的变化最小 20 mV（`base`），各例的期望变化数与改前相同。`param-override` 里两个名义相等的残差在 binary64 下差 3.3e-16 V，改前、改后都不算变化。
   - P0PC 已交回的本题作业 210 个，用改前、改后两版 checker 重判：状态与 passed 都相同，整份判决的 sha256 也相同。作业分属四个包：`spectre-P0PC-must-01-v1` 10 个（参考解与缺省容差对照，已正式核收，结果包 sha256 `56bb45ddcc96029e2ee7bd556bdd9b26db70f2186f91bff0653353d43b837ad6`），`spectre-P0PC-opt-02-v1` 40 个（`2c940a81853402709c2cd1e84bcca25d417634394475017ff8d3b9f17e6ef19f`），`spectre-P0PC-rec-07-v1` 28 个（`883cb1bfd7b2a9396ba6117d957d53886060b394149d448d0cad597b00a41200`），`spectre-P0PC-rec-08-v1` 132 个（`6fdfa597ea1e6f3edb5ab9b7606e0b10d1e542cc6d857eaf79bc026c4e23f879`）；后三包是预读。其中 `stream-irregular`、`reset-recovery` 的波形是修正 r7a 挪动激励之前的，只用来比较两版 checker。
   - 已存档的旧版波形 166 次：修正 r7a 在改后的 `stream-irregular`、`reset-recovery` 上的 83 次，建题时在 `base`、`param-override`（激励没改）上的 83 次；都是参考解与 40 个候选，另有参考解的公开 `base`。用两版 checker 重判，全部行与只用网格行的判决都相同。这些是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
   - 建题的 47 个合成模型、两个参数端点上的 34 项与 14 个证据有效性控制，在两版 checker 上的判决、最大误差与迟到可见性统计都相同。
5. **修正 r7a 第 2 条的余量已定**：项目协调方 2026-10-29 同意 `reset-recovery` 的复位离沿用次网格余量 1.875 ps。这一个 `rst` 穿越的网格相位由 0.9·g 变为 0.9375·g，是为了保住唯一一个检“过渡被打断”的负例：建题的合成模型 `interrupted-transition-queued`（等当前过渡走完再走复位过渡）只靠这一例被拒，挪整网格步后它就通过了。
6. **Spectre**：本轮只改 checker 的门限、题面文字、校准说明与本文件，网表与候选都没变，不需要新的 Spectre 作业。已交回和待交回的本题作业都用新 checker 判。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 1 处台架义务检查（C105-06，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `37c6e48a74ae58810851a7773d63151c2d7ae11c0d0a57df00776a67dd60fe11`，改前 `f0f46bed…`）与本文件，以及第 9 小节的用例时限（`tests/cases.json` 的 `timeout_s` 与 `task.toml` 的 verifier 时限）。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **C105-06**（evaluate 第 175 行调用 `crossings`，第 61–63 行）：`clk`、`rst`、`valid_i` 的保存行上相邻两行恰为 `vth`（停留）报台架错误 → 按定义判；`crossings()` 去掉这一句，穿越的定义不动。
- 随同改（决定第 1 项，起点与最小偏离）：evaluate 第 170–171 行 t = 0 那一行离 `vth` 不足 50 mV × `REL`；第 182–190 行（修正 r7a）两次穿越之间各保存行的最大偏离不足 49 mV。两项都按定义判，门槛不变。
- 碰到：改前只当“不算穿越”，现在报台架错误（决定第 2 项）。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`clk`、`rst`、`valid_i` 各自对 `vth`。`check_stimulus` 放在原来起点检查的位置，在取穿越与判分之前。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 18 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”；离 `vth` 不足 0.04999995 V（`START_MARGIN` × `REL`），报 “starts … closer than …”；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 最小偏离：相邻两次定义穿越之间，各定义点离门限的最大偏离小于 0.049 V（`CROSSING_EXCURSION` − `SAMPLE_SLACK`，50 mV − 1 mV），报 “moves only … away from …”；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：判分用的穿越仍由原来的 `crossings()` 从保存行取，穿越的定义不动，只去掉其中“相邻两行恰在门限上就抛出异常”一句。保存行恰在门限上（例如模块在同一输入、同一门限上求根时写下的根处行）不再引起台架错误。

### 3. 余量（数值未改）

- 最小偏离：`SAMPLE_SLACK` = 1 mV 仍从题面的 50 mV 中扣除，报错门槛 49 mV 不变。它原来的理由是保存样本可偏离源 1 mV、保存行会低估两行之间的极值；按定义判以后这个理由不再适用，现在只是容让：定义上只离开 49 mV 到 50 mV 的激励已在题面合法域之外，但不报台架错误。常量注释照此改写，数值未改。
- 起点：50 mV 乘 `REL`（1 − 1e-6）不变，报错门槛 0.04999995 V；按定义精确比较以后相对余量只是容让，数值未改。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`clk`、`rst`、`valid_i` 各自对 `vth`）的起点、停留、碰到、最小偏离按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点对地；没有叠放源（本题网表里受查节点各由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 6 份网表（私有 4、公开 `cases.json` 1、`visible_test.scs` 1）共 24 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 18 个（PWL 18 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(x)` 与 `vth`，参考解在 `V(x) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `pipeline_adc_two_stage` 在 `cross(V(rst) - vth, +1, 1p)`、`cross(V(clk) - vth, +1, 1p)` 上求根（`valid_i` 按电平读），就是受查输入本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，6 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 6 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前只当“不算穿越”，现在一律报台架错误。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到、最小偏离：instruction.md 第 37 行 “They never rest at `vth`, and at t = 0 each of them is at least 50 mV away from `vth`. A control input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Between two successive crossings of `vth` by one control input, that input moves at least 50 mV away from `vth`.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 41 行 “A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：6 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 612 行）。12 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（12/12）。
- B 候选：扫描列出的 40 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（36 组不同的行，共 11255 行）。改前、改后判决逐个相同，新 checker 不报台架错误（40/40）。
- C 变体（在 `base` 上改 `valid_i` 的定义；每个变体事先写下预期），14/14 符合预期：
  - `valid_i` 起点按十进制恰在门限上：报 “starts on”
  - `valid_i` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `valid_i` 起点离门限 0.0498999 V：报 “closer than”
  - `valid_i` 起点离门限 0.0500999 V：不报台架错误（照常判分）
  - `valid_i` 在 3.9105e-07 s 处按十进制停在门限：报 “rests on”
  - `valid_i` 在 3.9105e-07 s 处只在 binary64 下停在门限：报 “rests on”
  - `valid_i` 在 3.9105e-07 s 处按十进制碰到门限：报 “touches”
  - `valid_i` 在 3.9105e-07 s 处只在 binary64 下碰到门限：报 “touches”
  - `Vclk` 在 5.045e-09 s 与 1.0045e-08 s 两次穿越之间只离门限 0.0489 V：报 “moves only”
  - `Vclk` 在 5.045e-09 s 与 1.0045e-08 s 两次穿越之间只离门限 0.0491 V：不报台架错误（照常判分）
  - `valid_i` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `valid_i` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `valid_i` 的源有一个值带单位 `0V`：报 “cannot read”
  - `valid_i` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-02-v1 40、spectre-P0PC-rec-07-v1 28、spectre-P0PC-rec-08-v1 132、spectre-P0R7-must-01-v1 4、spectre-P0R7-rec-02-v1 80，共 294 个。new 与改前 checker 整份判决 294/294 相同。与原判比 status、passed 与台架错误的有无 294/294 相同；整份判决 sha256 有 42 个不同，都在 P0PC 的 `param-override`（spectre-P0PC-must-01-v1 2、spectre-P0PC-rec-07-v1 7、spectre-P0PC-rec-08-v1 33），来自修正 r7a 写进的变化门限 δ：两个名义相等的残差在 binary64 下差 3.3e-16 V，改前算一次变化，r7a 起不算（抽 spectre-P0PC-must-01-v1 的 2 个核过：`output_changes` 28 → 27，`checks`、`max_error` 随之变，见“2026-10-29 修正 r7a”一节第 5 条末尾）。改前的 checker 已经如此，新 checker 与它整份相同。

### 8. 前面各节的相关句子

- 建模选择第 102、103 行（穿越提取里“连续两点停在 `vth` 上…抛出异常”，台架错误里的“起始电平离 `vth` 不足 50 mV”“同一控制输入相邻两次穿越之间离 `vth` 不足 50 mV（修正 r7a 加，保存行上不足 49 mV 才报）”）：起点、停留、碰到、最小偏离改按定义判，碰到报台架错误；穿越时刻的取法不变。
- 修正 r7a 一节第 4 条第 186–188 行（按保存行判最小偏离、减 1 mV 的理由、“只读保存行”）：自本节起按定义判，余量的用途见第 3 小节。

### 9. 用例时限（第五部分，与 checker 改动分开）

- 依据：样板 `runs/t3-p0-pilot-20261027/TEMPLATE.md` 第 4c 节（现行 r2.38，sha256 `55bc2db0676d5c07a4813b55c22b2568833168639f85ab1fd256ff5d743910da`）；项目协调方 2026-10-30 的决定 COORD-BENCH-DAY5-WAVE2-20261030-01，依据第 5 天第二波交回的正确候选实测用时（Benchmark 维护方的预读记录第 6.1 节）。
- 改了什么：`tests/cases.json` 里 `stream-irregular` 加 `"timeout_s": 240`、`reset-recovery` 加 `"timeout_s": 180`，其余 2 个用例照旧取 `v2_runtime.py` 的缺省 120 s；`task.toml` 的 `[verifier] timeout_sec` 由 600 改为 780。其他字段与网表一个字都没动（逐用例比过）；公开 `environment/starter/testbench/cases.json` 只有 `base`，不改。
- `v2_runtime.py` 按 `case.get("timeout_s", 120)` 读到的时限：`base` 120 s、`stream-irregular` 240 s、`reset-recovery` 180 s、`param-override` 120 s。
- 算术：单用例取正确候选实测最长的 2 倍，向上取整到整分钟：2 × 96.626 = 193.252 → 240 s；2 × 77.012 = 154.024 → 180 s。总时限取私有用例时限之和，加 10 % 或 60 s 中较大的，向上取整到整分钟：120 + 240 + 180 + 120 = 660 s，加 66 s 得 726 s → 780 s；verifier 时限 780 s 不小于用例时限之和。
- 实测用的作业：`r7a-c105-pipeline-alt-three-module-hierarchy-stream-irregular`（96.626 s）、`r7a-c105-pipeline-alt-three-module-hierarchy-reset-recovery`（77.012 s），包 spectre-P0R7-rec-02-v1，结果包 sha256 `0eebc6f9dae79cf7ae063341412fb58f8aaa3b133d2c9dbb7799c6ebc3d91c43`。作业网表去掉执行路径一行后与现行用例网表逐字节相同。
- 结果包已核收：2026-10-30 按 Spectre 定版 v1.16 正式核收（项目协调方 COORD-SPECTRE-DAY5-FORMAL-V116-20261030-01）。核收只是执行身份与证据完整性；时限依据仍是打包快照的这几个作业，不因核收重判。
- 只改资源限制：checker、expected、门限、判决与期望都不因这一项改变，不需要新的 Spectre 作业。单次交回的用时不推出跨机器的保证或提速结论。
- 一个后果：score_returns 的 `case_fields_sha256` 覆盖用例除网表外的全部字段，加了 `timeout_s` 之后，这些用例已交回的作业如果对现行题包评，会记 case_changed：spectre-P0R7-must-01-v1 `stream-irregular` 2、spectre-P0R7-must-01-v1 `reset-recovery` 2、spectre-P0R7-rec-02-v1 `stream-irregular` 40、spectre-P0R7-rec-02-v1 `reset-recovery` 40（共 84 个，本轮之前与题包一致）；spectre-P0PC-must-01-v1 `stream-irregular` 2、spectre-P0PC-must-01-v1 `reset-recovery` 2、spectre-P0PC-rec-07-v1 `stream-irregular` 7、spectre-P0PC-rec-07-v1 `reset-recovery` 7、spectre-P0PC-rec-08-v1 `stream-irregular` 33、spectre-P0PC-rec-08-v1 `reset-recovery` 33（共 84 个，修正 r7a 改激励时已经不一致）。用打包时的快照评（`--task-dir`）不受影响；第 7 小节的重判用的就是快照，不受影响。
