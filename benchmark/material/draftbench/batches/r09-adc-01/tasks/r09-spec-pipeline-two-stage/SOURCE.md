# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C105-S1，`unit_id` C105，`case_anchor` C105，来源 `src-40687b8cacee`，`primary_ref` C105，动作 S（spec-modeling），家族 R09，优先级 P0，结构难度 H，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 C105-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。登记要求：
- reuse：两级量化、残差观测、两拍发布及 valid 接口；
- author_work：固定粗量化电平与残差闭式、第二级门限、样本缓存及连续/空拍对齐；补必要接口，不用固定五文件代替难度；
- difference：每个有效样本需穿越多阶段并保持归属；
- Grok 意见：完整修订原题仍未唯一规定粗电平与残差量化关系，采纳；两拍延迟已经明确，应沿用。复审评论另记"缺第一级电平是箱沿还是中心，以及第二级门限"。

主来源是 2026-10-22 历史净化修订后的 v4:343 题面，sha256 `c4e324ed877a3c672967b2a6a0a233a6ff05b9be43ae118dc5ef6ce27bb50313`。规划登记标为 local-only，原件在外接盘 `证据卷/historical-purification-20261022/improve-packs/pipelineadctwostage/OUTPUT/instruction.md`（登记路径 `runs/historical-purification-20261022/improve-packs/pipelineadctwostage/OUTPUT/instruction.md` 在主工作区），不在本工作树。修订只比发布版 [v4:343 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/public/instruction.md)（sha256 `ac7f0ba1…a796e9ed`）多一条：`valid_o` 与完整 4 位码出现在 `valid_i` 采样沿之后的第二个 `clk` 上升沿，`valid_o` 只高一个时钟周期（修订包 D1，CHANGES.md sha256 `5e77f595…`）。原题沿用的事实：
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

并入的变体（规划 GROK-REVIEW（`benchmark/material/draftbench/planning/history-candidates/GROK-REVIEW.md`） 与 pool-review 的处理）：
- `pipelineadcchain4b`：v4:096 的历史修订题面（`src-44b5d8afdac4`，local-only，外接盘 `证据卷/historical-purification-20261022/improve-packs/pipelineadcchain4b/OUTPUT/instruction.md`，sha256 `ccc34089bc65944a7865161ba576a6dfc74c210687f335de04c31e3614ad965c`）。规划要求"优先复用本版本的中心/增益公式来收敛 C105 歧义，核对单调性而非盲信原 gold"。本题采用它的残差式 `RES1 = (vrefp + vrefn)/2 + 4*(clipped VIN - bin center)` 和"顶部四分位包含 vrefp"，见建模选择第 2 条。发布版 [v4:096 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/096-pipeline-adc-chain-4b/public/instruction.md)没有写中值偏移，这正是修订包的 D1。
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

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。

1. 【待用户确认 1】接口：单文件单模块，模块名由 `pipeline_adc_top` 改为 `pipeline_adc_two_stage`，保留原顶层的 10 个端口和顺序，不要求五个文件和五个公开子模块（解题者可以在同一文件内自定义辅助模块），也不另加调试端口。
   - 理由：author_work 要求"补必要接口，不用固定五文件代替难度"。原 checker 只实例化顶层，子模块边界只能靠静态扫描。现有端口已经能观察四项职责：`residue_dbg` 看样本保持，码和 `valid_o` 看第二级门限、发布时刻和样本归属。补上的"必要接口"是参数合法域、输入合法域与时序义务、`residue_dbg` 的保持语义、复位与初态。改名是因为 `pipeline_adc_top` 暗示五模块层次，新名描述行为。
   - 另一种读法是保留五个文件与子模块端口，或者像 v4:096 那样另外引出两级判决位（`S1B1..S2B0`、`RES2`），让每级的时刻都可观察。后者会把内部级划分写进合同。
   - 推荐单模块、不加端口。
2. 粗量化电平与残差闭式（规划已定，不作为待确认项）：粗码 `k` 是 `vss + span/4`、`vss + span/2`、`vss + 3*span/4` 三个门限中不高于 `x` 的个数（等于门限归上一区间，`x = vref` 得 `k = 3`）；箱中心 `c = vss + (k + 1/2)*span/4`；残差 `r = (vss + vref)/2 + 4*(x - c)`；第二级用同样三个门限得细码 `f`；码为 `4*k + f`，等于 `floor(16*(x - vss)/span)` 并限到 15。
   - 这就是 v4:096 修订版的中心/增益式。它与"箱沿式" `vss + 4*(x - vss) - k*span` 恒等，所以复审问的"箱沿还是中心"由显式公式唯一确定；中心式配 `vss` 偏移、箱沿式配中值偏移这两种混合读法是校准候选，都被拒。
   - 单调性按规划核对：build_cases.py（`runs/t3-p0-build-20261027/r09-spec-pipeline-two-stage/build_cases.py`） 对四组 `(vss, vref)`（含两个参数端点）各扫描 16000 点，码不减，残差在 `[vss, vref]` 内，箱内斜率为 4，只在三个粗门限处下降一个量程。
   - 扫描还表明：正好落在码边界上时，两级组合与闭式在浮点下可以差一个码（例如 `vss = 0.2 V`、`vref = 1.0 V` 时的 `x = 0.3 V`）。合法域因此要求样本离码边界至少 3 mV，见第 7 条。
3. 【待用户确认 2】样本缓存：第一级保持 `x`、`k`、`r`，直到下一个取样的时钟沿或复位；`residue_dbg` 驱动第一级保持的 `r`；第二级在下一个时钟沿按该沿之前保持的残差判决，同一沿采入的新样本不影响这次判决。
   - 依据：原文"for the sampled input"和"the stage-1 residue used by stage 2"；真实流水级先采样保持再放大；这样原 gold 的实时残差错误可以被看到。
   - 用例让 `vin` 在每个采样沿后约 2 ns 就变到下一个值，`stream-irregular` 还在斜坡上采样，所以实时残差、时钟高电平期间跟踪、只保持一个周期都会被拒。
   - 另一种读法是残差只在第二级使用的那个周期有效、之后回到 `vss`，或者像原 gold 那样跟随实时输入。
   - 推荐保持到下一个样本或复位。
4. 【待用户确认 3】两次结果之间码保持：不发布结果的时钟沿只把 `valid_o` 拉低，码保持上一次的值，复位才清零。依据是原 gold；原题面没有写。另一种读法是 `valid_o` 落下时码也清零。推荐保持；`code_zero_between_results` 是对应的错误模型。
5. 【待用户确认 4】复位：`rst` 上升穿越立即清零（异步），在途样本全部丢弃且永不发布，码为 0、`valid_o` 低、第一级保持 `x = vss` 因而 `residue_dbg = vss`；`rst` 为高时上升沿不采样、不发布；下降穿越没有作用，之后第一个时钟沿就能采样（没有预热）；t = 0 与清零状态相同。
   - 依据：原 gold 是异步清零加"高电平期间的时钟沿也清零"，两者在本合同下等价。新合同只改了释放后的残差：原 gold 释放后按实时输入算出约 4·vin，本题保持 `vss` 到下一个样本，与第 3 条的缓存语义一致。
   - `reset-recovery` 里 `rst` 在发布沿后 100 ps 上升，正好打断输出过渡；两个 `rst` 脉冲落在时钟沿之间，同步复位看不到它们。
   - 另一种读法是同步复位（只在 `rst` 为高的时钟沿生效）。
   - 推荐异步。
6. 两拍发布与 valid（沿用修订题面，Grok 已认可）：采样沿 `n` 的样本在沿 `n + 2` 发布；流水线在每个时钟沿推进，不论该沿是否取样；不发布结果的时钟沿 `valid_o` 变低；连续样本在连续的沿发布，`valid_o` 中间不落。延迟按时钟沿计，不按时间计：`stream-irregular` 的沿间隔 4–21 ns，且在一次发布后停钟 60 ns，`valid_o` 在停钟期间保持高。
7. 同刻与合法域（原题没有）：
   - `valid_i`、`rst` 的每次穿越离每个 `clk` 上升穿越至少 100 ps；`clk` 相邻上升穿越至少 4 ns；同一输入相邻穿越至少 100 ps；
   - 每个 `clk` 上升穿越前后 100 ps 内 `vin` 变化小于 0.25 mV，所以事件定位误差几乎不影响样本值，残差（增益 4）误差小于 1 mV；
   - 每个样本离码边界 `vss + j*span/16`（j = 1–15）至少 3 mV；
   - `vin` 在 `vss - 0.2 V` 到 `vref + 0.2 V`，控制输入在 0–0.9 V，t = 0 时离 `vth` 至少 50 mV，`clk` 从低开始；控制输入到达 `vth` 时必定穿过，不触碰后返回（p0-fix-c 按待用户确认第 38 项的推荐写入，见 p0-fix-c 一节）；
   - 参数合法域：`vss` −0.5 到 0.5 V，`vref - vss` 0.4 到 2 V，`vdd - vss` 0.5 到 2 V，`vth` 0.2 到 0.7 V，`tr` 10 ps 到 1 ns。
   在此域内没有判决取决于同刻或事件定位。台架实际余量：码边界最近 4.28 mV（`stream-irregular` 斜坡），`vin` 在上升沿附近最大变化 0.18 mV。
8. 评分起点（F01）——用户已确认（2026-10-28）：F01 选 A。题面写明实际观察起点：每次期望输出变化后 `1.25*tr` 内的点不评分，其余保存点都评分；checker 不改。另加评分起点之后才到达的负例：
   - `clk`、`rst`、`valid_i` 的穿越都对齐在输出网格的相位 `0.9*g`，评分起点后的第一个点在 `1.275*tr`；
   - `slow_output_1p3tr` 在四个用例都被拒：合成控制 17.3 mV（`param-override` 19.2 mV），旧版 EVAS 相同；
   - 输出台阶不小于 104 mV 的事件都能看到 1.3·tr 的迟到：`base` 35/35，`stream-irregular` 59/59，`param-override` 25/25，`reset-recovery` 23/24。唯一的例外是被 100 ps 后的 `rst` 打断的那个发布沿，它没有属于自己的评分点；
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
    - 台架义务出错时抛出异常（无判决，不记候选失败）：分辨率、参数超域、输入超域、起始电平离 `vth` 不足 50 mV、`clk` 不从低开始、穿越不交替或间距不足、上升沿间距不足 4 ns、`valid_i`/`rst` 离上升沿不足 100 ps、`vin` 在上升沿附近变化过大、样本离码边界不足 3 mV；
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
  - `transition()` 被打断时的完成方式：`reset-recovery` 45.045 ns 的发布沿后 100 ps 复位；
  - 校准候选 `alt_delayed_within_tr` 的传输延迟过渡和 `valid_5ns_pulse` 的定时器改期；
  - `alt_three_module_hierarchy` 中一个模块在时钟事件读另一个模块 `transition()` 输出节点时读到的是事件前的值；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 用户确认上面四个"待用户确认"选择和清单第 38 项（p0-fix-c 已按推荐写入题面，见 p0-fix-c 一节）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## p0-fix-b 修正（2026-10-28）

依据铺开六题独立审核 r1（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）的 F02。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-b 处置记录（`runs/t3-p0-build-20261027/p0-fix-b/disposition.md`）。本题**未仿真**：没有运行 Spectre，旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

- 问题：checker 原先把"到达 `vth` 后返回原侧"的孤立触碰记成一次单向穿越。`clk` 触及 `vth` 而 `valid_i` 为高时，checker 假定一次采样并要求 `residue_dbg` 变化；`rst` 触及时假定清零；正确的输出被误拒。若触碰之后还有真实的上升沿，原 checker 会报"穿越不交替"而不评分。
- 改动：只改公开与私有两份 checker 的穿越提取，规则见建模选择第 11 条，两份逐字节相同。题面、参考解、用例、公开台架和校准件都不变。
- 复核：触碰后返回与恰有阈值行的真实穿越各有正反对照（合成波形），修正前触碰类对照判错或不评分、修正后判对；恰有阈值行的穿越前后都判对；建题时的全部合成控制在新 checker 上重跑，结论不变；参考解在旧版 EVAS 上通过全部私有与公开用例；建题时存档的旧版波形用新 checker 重判，判决全部不变。
- 未改的一处：checker 仍要求记录中至少有一个 `clk` 上升沿，没有时抛出异常、不评分。题面没有写这条台架义务；终评用例都满足，对评分没有影响。审核给出的单次触碰波形里没有真实的时钟沿，所以修正后它落在这条检查上（不评分），而不是被误拒。（p0-fix-c 起作为证据有效性规则写进建模选择第 11 条，题面不改。）
- 终评台架没有恰好触及 `vth` 的输入。（p0-fix-c 更正：这里原写“仿真器的 `cross()` 遇到恰好触及阈值又返回的输入是否触发，本题没有记录”，不准确。归档的 Spectre 21.1.0.509 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 显示，`cross()` 在输入恰好到达阈值时按到达方向触发一次，孤立触碰后返回也触发，离开时不触发。p0-fix-c 已按第 38 项的推荐在题面排除触碰。这份记录用的是显式 PWL 实验，参考解在本题台架上的行为仍待 Spectre 复跑。）

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-01、F02 剩余部分与对 C105 时钟沿规则的意见，以及主控 2026-10-28 对清单第 38 项的安排。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解、用例、公开台架和校准件都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 终点事件（R2-01）。p0-fix-b 的写法丢掉记录末尾单个恰在 `vth` 上的行，终点处到达的事件就没有不评分窗。在修正前的字节上复现：沿用 p0-fix-b 的“`rst` 触碰”场景，记录截在 30 ns，`rst` 在最后一行从下方恰到 0.45 V；此前码 5、`valid_o` 为高，全部输出在最后一行立即清零，被拒 0.9 V；p0-fix-b 之前的写法接受它。现改为六题统一的穿越规则（第 11 条），这条输出通过，提前 1 ns 清零的输出仍被拒。终点事件照样受间隔约束：`rst` 离 `clk` 上升沿 55 ps 时报台架错误，105 ps 时照常评分。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 【待用户确认第 38 项，已按推荐写入】控制输入到达门限时必定穿过。题面合法输入一段在“at t = 0 each of them is at least 50 mV away from `vth`.”之后加一句：“A control input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”“不停在 `vth` 上”和起始 50 mV 原已写明，不重复；checker 不变。另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
3. 时钟沿规则（复审意见第 5 项）：checker 要求记录里至少有一个 `clk` 上升穿越，这条现在作为证据有效性规则写进第 11 条，题面不改。
4. 更正 p0-fix-b 一节最后一条：归档的 Spectre 记录存在，原句“本题没有记录”不准确。
5. 复核：
   - p0-fix-b 的 F02 对照 11 个在新 checker 上判决不变（其中原审核的单次触碰波形仍因没有时钟沿而不判分）；p0-fix-b 的合成控制副本在新 checker 上全部符合预期，与存档相比判决与误差 0 项变化。
   - 建题以来的旧版存档波形用新 checker 重判，判决与误差 0 项变化。本题用例未改，没有新的旧版运行。
   - 平局扫描（精确有理数）：参考解的过渡终点都不在输入穿越上。事件与事件同刻的 41 处都有一方是 `clk` 下降穿越或 `valid_i` 穿越，它们都不是本题的事件（`valid_i` 只在时钟沿读电平），不算平局。

第 38 项的三个前提（主控 2026-10-28 定的口径，也作复审口径）：
- 内部恰为零：参考解的事件只看外部驱动的 `clk` 与 `rst` 上升穿越，`valid_i` 与 `vin` 只在时钟沿读取；没有被测模块内部恰为零的信号参与事件或判决，无需核对。执行细则（主控 2026-10-28 转标准线口径，p0-fix-d 写入，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。本题参考解只对外部驱动的 `clk`、`rst` 用 `cross()`，符合（p0-fix-d 核对）。
- 相等规则写成输出行为：粗码与细码写成输出码的规则（不高于样本的门限个数，即相等归上一区间），合法输入让样本离每个码边界至少 3 mV，不出现相等；输入恰在 `vth` 上由合法输入排除（第 2 条）。
- 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。
