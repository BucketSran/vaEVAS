# 来源与建设记录

2026-10-27 按 P0 试点新建，阶段 implementation，`pending = ["grading", "runtime"]`。本机没有 Spectre，本题未经 Spectre 仿真；EVAS 结果只作开发证据。本页不表示科学校准、模型试做、题目审核或正式录取。

## 行为依据

### 规划候选身份

| 项目 | 值 |
| --- | --- |
| task_id | `U15-S1`（规划候选，规格建模） |
| unit_id / primary_ref | `U15` / `C287` |
| 主来源 | `src-76e425b8eda2`：v4 360 公开题面，SHA256 `61db2c239acb0e170becd05de3770172e40f7590fe700058493d614ff7aec6de` |
| 规划登记 | register.json（`benchmark/material/draftbench/planning/history-candidates/register.json`） 的 U15-S1：P0，结构估计难度 M-H，建设成本 M。作者工作为“解决逐沿锁不同延迟与保持整脉宽的冲突，选定逐脉冲锁码或合法改码域；补 load 同刻、未加载和最小脉宽”。`spec_plan` 建议上升沿锁存整脉冲的延迟、下降沿沿用，后续 load 只影响下一脉冲，公开周期、延迟跨度和最小低电平以保证不重排，复位取消所有待发事件 |
| 验收与回退 | 登记的 `acceptance`：高电平期间改码、有待发沿时复位、背靠背不同码下逐个核对输出脉冲，复位后不得出现幽灵沿。`rollback`：若只剩固定延迟或换参数，不另计独立任务 |
| Grok 意见 | 部分采纳：不采纳“原行为已完全可成题”，高低沿之间改码时两条要求冲突；采纳延迟单元的工程价值（候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）） |
| 规划说明 | 规划 README（`benchmark/material/draftbench/planning/history-candidates/README.md`） 把 U15 列入 P0 首批；C290（DLL）一段写明上下沿允许不同码、不能照搬 U15 的保持脉宽合同；U22-I1 以 U15 作可复用执行器来源 |

### 历史原件与改编

[v4 360 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/360-digitally-controlled-delay-cell/public/instruction.md)规定：上升 `load` 锁存 `code_5..code_0`；延迟为 `delay_min + delay_lsb * code`；上下沿用同一延迟、保持输入脉宽；同时要求“每个原始边沿独立锁存延迟，后来的 load 不改已待发的边沿”；复位取消待发沿、清码、拉低输出；另有 `delay_metric` 与 `valid`。高电平期间 load 改码时，下降沿锁新码会改变脉宽，与“保持脉宽”冲突，这正是 Grok 指出的缺口。参数默认值 `vdd = 0.9 V`、`vss = 0 V`、`vth = 0.45 V`、`delay_min = 20 ps`、`delay_lsb = 3 ps`、`tr = 100 ps`。本题沿用 load 锁码、延迟映射、复位取消待发沿和前五个默认值，改为逐脉冲锁码，并补齐同刻、未加载、最小脉宽、待发深度和验收尺度。

[v4 360 gold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/360-digitally-controlled-delay-cell/evaluator/solution/digitally_controlled_delay_cell.va)只作冲突分析：它在每个输入沿把当前码换算成 `transition()` 的延迟参数，复位时把目标置低、延迟置 0。按 LRM 4.5.8，目标已为低时复位不安排新过渡，已待发的沿不会被删除。参考解另写，没有复制。v4 [公开激励](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/360-digitally-controlled-delay-cell/public/visible_test.scs)周期 10 ns，65.02 ns 的 load 紧跟上升沿，延迟都远小于脉宽，看不到待发沿重叠；本题用例重新设计，不沿用其刺激表。

同内核还有 [1360 修复形式](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1360-digitally-controlled-delay-cell-bugfix/public/instruction.md)与 [860 测试台形式](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/860-digitally-controlled-delay-cell-testbench/public/instruction.md)。1360 的坏版与 gold 只差 `valid` 永不置位，本题已删除 `valid`，不复用这一故障。

### 同源关系与职责差异

| 题目或候选 | 来源组 | 职责 | 与本题的关系 |
| --- | --- | --- | --- |
| C301-S1（规划，未建） | v4 362（与首批 `v2-test-clock-frequency` 同族） | 频率字 DCO 调节自产振荡器的后续周期，下一半周期生效 | 规划 `difference`：本题对应外部输入的完整脉冲，改码不能改变已接受脉冲的宽度 |
| C292-S1（规划，未建） | v4 064 | 去毛刺延迟线：先资格确认再延迟，反向沿前取消、拒绝短脉冲 | 本题不过滤短脉冲，合法域内的每个已接受脉冲都原样延迟 |
| C312-S1（规划，未建） | v4 375（与第二批 `v2-spec-375` 同族） | 两相交接与死区 | 机制不同 |
| C298、C317（规划为 U15 变体） | v4 326、323 | 分数延迟 DTC、可编程偏移，只规定上升沿 | 规划已判为 U15 的变体，补完整脉冲合同后不另计；本题不包含它们的 `enable`、`phase_metric` |
| C290-S1（规划，未建） | v4 361 | DLL，上下沿可用不同码 | 规划说明不能把本题保持脉宽合同移植过去 |
| U22-I1、U23-S1（规划，未建） | 各自来源 | 占空比校正闭环、四象限相位插值 | 以 U15 为执行器或参照；以后复用本题 DUT、checker 或用例时应登记共享资产 |
| 首批30 [v2-repair-pfd-reset](../../../v2-01/tasks/v2-repair-pfd-reset/instruction.md) | `v4-family-249` | 两路置位后固定 80 ps 清零，复位取消待发清零 | 都有“复位取消待发事件”，但那里只有一个固定延迟；本题有可装载的码、两方向待发沿和逐脉冲锁码 |
| 首批30 [v2-test-comparator-delay](../../../v2-01/tasks/v2-test-comparator-delay/instruction.md)、[v2-test-clock-frequency](../../../v2-01/tasks/v2-test-clock-frequency/instruction.md) | `v4-170`、`v4-362` | 测量固定 DUT 的延迟或频率 | 测试表征题；本题产生延迟边沿 |
| 首批30 [v2-integrate-case0007-adpll-fine-tdc](../../../v2-01/tasks/v2-integrate-case0007-adpll-fine-tdc/instruction.md)、[v2-spec-001-bang-bang-phase-detector](../../../v2-01/tasks/v2-spec-001-bang-bang-phase-detector/instruction.md)、[v3-calibration-fractional-pll](../../../v3-01/tasks/v3-calibration-fractional-pll/instruction.md) | 各自来源组 | TDC 测时间差、鉴相、分数分频 | 时钟族，机制不同 |
| 第二批草稿 [v2-repair-debounce-latch](../../../v2-01/tasks/v2-repair-debounce-latch/instruction.md) | `v4-family-005` | 单个资格定时器，输入回落或复位取消 | 只有一个待发事件，且取消条件是输入本身；本题的待发沿由输入沿按延迟安排，输入回落不取消 |
| 第二批草稿 [v2-spec-375-nonoverlap-clock-generator](../../../v2-01/tasks/v2-spec-375-nonoverlap-clock-generator/instruction.md)、[v2-test-time-protocol](../../../v2-01/tasks/v2-test-time-protocol/instruction.md)、[v2-test-duty-cycle](../../../v2-01/tasks/v2-test-duty-cycle/instruction.md)、[v2-spec-396-quadrature-lo-generator-divided-clock](../../../v2-01/tasks/v2-spec-396-quadrature-lo-generator-divided-clock/instruction.md) | `v4-375`、`v4-346`、`v4-060`、`v4-396` | 死区交接、TDC 重武装、占空比测量、四分频正交 | 时钟族，机制不同；其余第二批草稿未见可编程延迟或待发沿管理 |
| P0 试点 [r01-spec-aperture-delay](../../../r01-sampling-02/tasks/r01-spec-aperture-delay/instruction.md)（C056-S1） | `v4-family-072` | 触发沿预约一次未来读入，触发间距排除重叠 | 同样“沿后预约未来事件”。那里同时只有一个待发读入、无复位；本题两方向沿可同时待发，并有锁码、复位取消和同刻规则 |
| 原 56 题 | 各自来源组 | 上表已列与时钟、延迟相关的题 | 本次只读这些题面，未复审全部 56 题 |

本题只计 U15-S1 一项。`v4-family-360` 是新组名，按 v4 家族命名，覆盖 v4 360、1360、860 同一内核；正式组名由主控登记时确定。

### 外部来源与许可

| 来源 | 版本 | 许可 | 用途 |
| --- | --- | --- | --- |
| [Verilog-AMS LRM](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（Accellera） | 2.4.0，2014-05-30；2026-10-27 取得的 PDF SHA256 `621b2a1a3751e7685600f180fe8f362766fe13e952023ded3d7ae48314337c03` | 标准文本，版权所有 | 按 4.5.8 `transition()`（td 是传输延迟，新安排的过渡只删除排在它之后的待发过渡）、5.10.3.3 `timer()`（起始时刻在未来才触发，按最新起始值重排）、5.10.3.1 `cross()`（事件在穿越之后、容差之内触发）写参考解和校准候选。未复制文字 |
| [DS1023 数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/DS1023.pdf)（Dallas/Maxim，今 ADI） | 页脚日期码 070505；PDF SHA256 `8de9c6821786551a6e04dbebe8ad5b893e5917525d8347edd1540006a0709c8d` | 厂商版权文档 | 只引用工程事实：延迟等于固有“step zero”延迟加编程步数；LE 锁存编程值；改码后需建立时间才能准确延迟；规定最小输入脉宽与最小周期；输出延迟可远大于输入脉宽，并可超过一个周期。未复制文字、图或数值 |
| [Arcadia-1/behavioral-veriloga-eval](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd) | 提交 `7b5616dc52195ec275ec6d21c71d7763613702cd` | 公开仓库，未见 LICENSE | 公开含 v4 360 合同、gold 及 1360、860 形式；本仓库 historyref 是其迁入快照。未复制代码 |
| [Infineon/adsbenchmark](https://github.com/Infineon/adsbenchmark/blob/d1f5c9be021970e8c1fda5a2c5eea3987cb9667c/PHY/src/checker/va_common_stimuli/veriloga/states/5_delay_line.va) | 提交 `d1f5c9be021970e8c1fda5a2c5eea3987cb9667c` | MIT | 只引用工程做法：延迟线测试分别测上升沿和下降沿。未复制代码 |
| [OmarSiwy/VAMS-Conformance-Suite](https://github.com/OmarSiwy/VAMS-Conformance-Suite/blob/3900a2457b854d9f16d091095d10586ea3a3a414/tests/verilog-a/ch04_expressions/transition_transport_delay.va) | 提交 `3900a2457b854d9f16d091095d10586ea3a3a414` | 未见 LICENSE | 检索所得，只作线索，指向 LRM 4.5.8 的传输延迟句；随后核对 LRM 原文。未使用其内容 |

GitHub 代码检索、arXiv API 检索和 onsemi 数据手册尝试的结果见证据目录 `runs/t3-p0-pilot-20261027/r04-spec-delay-pulse-hold/sources.json`；arXiv 没有相关条目。

记忆污染风险：历史合同与 gold 在上述 Arcadia-1 公开仓库可检索。本题改用逐脉冲锁码，模块名、接口、合法域、验收和用例都已改变；照搬公开 gold 结构的校准候选 `historical_per_edge_transport` 在本题用例中被拒，见下文开发证据。评测时仍应考虑模型可能见过原题。

## 建模选择

### 建设决定

1. 模块名改为 `programmable_delay_cell`，取规划标题“可编程延迟单元”。理由：行为合同已实质改变，按题包约定用电路功能名，也避免沿用原名引导回忆旧合同。
2. 端口保留 `in_clk, load, rst, code_5..code_0` 的顺序与 `out_clk`，删除 `delay_metric` 与 `valid`。理由：两者不属于待发事件与保持脉宽的职责，保留就要另定它们在逐脉冲锁码下的语义（报当前码还是在途码、何时置位）。列为待确认 Q6。码位仍用六个标量端口、MSB 在前，与首批 353 的 `pre_1, pre_0` 写法一致。
3. 参数：`vth`、`vdd`、`vss`、`delay_min`、`delay_lsb` 沿用历史默认值。`tr` 改为输出过渡时间上限，默认 10 ps。理由：历史 100 ps 比 20 ps 最小延迟和 40 ps 级脉冲还长，无法分清 3 ps 码阶与相邻边沿。合法域：`vss < vdd`，`delay_min > 0`（零延迟会让定时事件落在当前时刻），`delay_lsb ≥ 0`，`tr > 0`。
4. 逐脉冲锁码：已接受的上升沿锁存整脉冲的延迟，下降沿沿用；之后的 load，包括脉冲为高或其输出沿待发时的 load，只影响下一个被接受的上升沿。理由：规划 `spec_plan` 的推荐；它不限制 load 时刻，并满足“改码不改已接受脉冲宽度”。另一读法是保留逐沿锁码、把 load 限于低电平且无待发沿的合法改码域，列为待确认 Q1。
5. load 与上升沿同刻：load 先生效，该脉冲用新码；即使此前未加载也被接受。理由：“沿时已装载的码”含同刻 load；在 Verilog-A 里由事件语句的源码次序决定，规则明确、可测。另一读法（沿先、新码从下一脉冲起）列为待确认 Q2。观测上两次穿越相差不足 1 ps 记为同刻，其余 load 与上升沿至少相隔 20 ps。
   - fix-r5（主控交办第 2 项）：题面写 “Crossings less than 1 ps apart are at the same instant.”，checker 原先按两次穿越的浮点距离 `g <= SAME` 判同刻。恰为 1 ps 时两者不同，而且 checker 的结论取决于两个穿越时刻的舍入方向。现在按题面取严格小于，用精确有理数比较：load 与 `in_clk` 上升穿越之差加舍入上界 B 仍小于 1 ps，才算同刻；差值在 1 ps 的 B 之内、与等号无法区分的，按等号处理，不算同刻。这样的 load 距上升穿越不足 20 ps，判激励越出合同。比较用 `short()`，所以 fix-r4 对 1 ps 加的精度判定照旧：B 超过 0.1 ps 且差值在 B 之内时报证据精度不足。全部用例（公开与私有）中，没有任何两个事件恰好相隔 1 ps：输入穿越与调度沿两两比较，间隔离 1 ps 最近的一对也差约 1 ps（同时翻转的码位，间隔约为 0）。
6. 未加载：上电和每次复位后直到下一次 load，上升沿不被接受，`out_clk` 保持 `vss`。理由：与历史 gold 的 `loaded` 门控一致，且“清码”后不应凭空产生延迟。另一读法（按码 0 输出 `delay_min` 延迟）列为待确认 Q3。
7. 输出沿时刻：`out_clk` 在 `t_e` 前不离开原电平，之后单调变化，`t_e + tr` 前到达新电平，允许更快。理由：沿用 C056 的 `tedge` 写法，用到达时间和单调性约束，不强制某个语言函数。按这一读法，延迟从输入 `vth` 穿越算到输出开始变化；用满 `tr` 时，中点穿越再晚 `tr/2`。另一读法（50 % 中点在 `t_e`）列为待确认 Q4。
8. 待发深度：同方向的输入沿不在同方向输出沿待发期间或其后 20 ps 内到达，因此任何时刻最多一个上升沿、一个下降沿待发。等价地说，对每个未被复位取消的已接受脉冲（延迟 `d`），下一个 `in_clk` 上升穿越距本脉冲上升穿越至少 `d + 20 ps`，下一个下降穿越距本脉冲下降穿越也至少 `d + 20 ps`；两个间隔都要满足。理由：规划要求公开周期与延迟跨度；DS1023 一类器件允许延迟超过一个周期，本题把队列深度留在两项，难点放在锁码、取消和交错。允许多个脉冲同时在途的读法列为待确认 Q5。
   - fix-r1（F09）：原文写“周期长于 `delay_min + 63*delay_lsb + 20 ps` 即满足”，这个充分条件不成立。脉宽逐个变化时，上升沿间隔足够大，下降沿间隔仍可能不足：码 63、输入脉冲 400–1300 ps 与 1400–1500 ps 的上升周期为 1000 ps，下降沿只隔 200 ps，第二个下降穿越到来时上一下降输出沿还待发到 1509 ps（审核 R09）。题面和本条已改为上面的两个间隔。checker 本来就按两个方向分别检查，未改。间隔恰好等于 `d + 20 ps` 合法。
   - fix-r2（审核 R2-02）：checker 原先的比较没有舍入余量，恰好等于 `d + 20 ps` 的合法激励可能被浮点舍入判为越出合同（审核 N03：码 63，两个同方向间隔都是 229 ps，`rise_out + 20 ps` 比 630 ps 多 1e-25 s）。现在激励合法性检查里的每个最小间隔都按等号合法处理：同方向的 `d + 20 ps`、load 与 `in_clk` 上升穿越的 20 ps、码位与 load 的 20 ps、`rst` 的 `max(20 ps, 4*tr)`。比较时留间隔值 1e-9 的相对余量，20 ps 时为 2e-20 s。ns 量级时刻的舍入误差约 1e-24 s，余量只吸收舍入，不改变 20 ps 等间隔：差 2 fs 的激励照旧判为越出合同。
   - fix-r3（试点 r3 审核，R2-02 仍开放）：fix-r2 的余量只与间隔值成比例，恒为 2e-20 s，只够 ns 量级的时刻。时刻的浮点舍入随时刻增大，题面又没有运行时长上限：0.5 ms 处一个 ULP（双精度最低位单位）是 1.08e-19 s，同方向间隔恰好 `d + 20 ps` 的激励仍被判越出合同（审核 R3-O01：两个方向的观测间隔都比 20 ps 短 8.0e-20 s，即 0.74 个 ULP）。现在激励合法性检查里的全部最小间隔共用一个比较：同方向 `d + 20 ps`、load 与 `in_clk` 上升穿越 20 ps、码位与 load 20 ps、`rst` 与 `in_clk` 穿越、load 上升穿越和调度沿的 `max(20 ps, 4*tr)`、`in_clk` 高电平 `4*tr`、相邻输出沿 `4*tr`。间隔短于最小值减去余量，才判为越出合同；余量取相减的两个时刻中较晚者的 8 个 ULP，最小值的 1e-9 更大时取后者。观测穿越时刻和由它加延迟算出的调度时刻，各与精确值差一两个 ULP；在默认参数和本轮控制所用的激励、保存行上（ns 到 1 s 的 13 个量级），等号激励的观测间隔与最小值之差在 −1.9 到 +1.7 个 ULP 之间。ns 量级仍是 1e-9 的相对余量，判定与 fix-r2 相同；8 ULP 一项在 0.5 ms 处为 8.7e-19 s，运行时刻小于 1 s 时不超过 0.9 fs，而 1e-9 一项随最小值增大，默认参数的 20 ps、40 ps 为 2e-20、4e-20 s，合法的 tr = 1 µs 时 4*tr 一项为 4 fs，0.5 ms 附近的余量即为 4 fs（试点 r4 审核 R4-02 更正：原写“0.5 ms 处余量为 8.7e-19 s，运行时刻小于 1 s 时不超过 0.9 fs”，漏了 1e-9 一项；本条的余量已由下面 fix-r4 一条取代）。20 ps、`max(20 ps, 4*tr)` 与 `4*tr` 的取值都不变。代价：短于余量的差别与舍入无法区分，按等号处理（0.5 ms 处短 4 个 ULP 的激励判为合法）；短出两倍余量的激励判为越出合同。题面各条原本就写 at least，没有运行时长的限制，未改。
   - fix-r4（试点 r4 审核 R4-01、R4-02）：fix-r3 的 8 ULP 余量随绝对时刻无界增长，1024 s 处为 1.82 ps，10 类间隔各短 1 ps 的激励都判为合法并评分（审核 R4-O01、R4-O02），放宽了 ps 级合同。现在 checker 用精确有理数在保存行之间插值求穿越时刻，间隔与最小值也按精确值比较，checker 自身不再引入舍入；余量只取推导出的舍入上界，不再有 8 ULP 或 1e-9 的经验项。推导的前提：保存的时刻与电压、`vth`、各参数以及 20 ps、1 ps 两个常数都是双精度数，各自代表与之相差不超过半个 ULP 的值；激励时刻以同一单位（ps）写出，单位本身的舍入是所有时刻共用的相对误差，不超过 2^-53。一个间隔的余量 B 是以下各项之和：
     - 时刻项：两端各取所在输入边沿终点（穿越后输入不再朝同一方向变化的第一个保存样本）的半个 ULP；插值所用的两个样本和它们所在的激励拐点都不晚于这里。1 ns 处每端 1.0e-25 s，0.5 ms 处 5.4e-20 s，1 s 处 1.1e-16 s。
     - 电压项：每端 (t1 − t0)·η，η = (½ULP(vth) + max(½ULP(a), ½ULP(b))) / (|b − a| − ½ULP(a) − ½ULP(b))，a、b 是穿越两侧的保存电压。2 ps 网格上，2 ps 斜坡约 2e-28 s，120 ps 斜坡约 7e-27 s；只有行距很大的稀疏保存行才显著（行距 0.5 ms 时 6e-20 s）。
     - 参数项：调度沿加 ½ULP(delay_min) + code·½ULP(delay_lsb)；最小值 20 ps 加 ½ULP(20 ps)，4*tr 加 4·½ULP(tr)，max(20 ps, 4*tr) 取两者半个 ULP 中的较大者。默认参数下这几项不超过 1.4e-26 s；它们随参数增大（半个 ULP 不超过参数值的 1.1e-16 倍），例如 tr = 1 µs 时 4·½ULP(tr) = 4.2e-22 s，delay_min = 1 µs 时 1.1e-22 s。
     - 单位项：两端所依输入穿越之差的 2^-53 倍，20 ps 为 2.2e-27 s，229 ps 为 2.5e-26 s。

     判定：设 e 为间隔减最小值。e + B < 0 判越出合同；e ≥ B 合法；其余情况与等号在舍入范围内无法区分，B 不超过 0.1 ps 时按等号判合法，超过 0.1 ps 时报证据精度不足（checker_error，不判分）。1 ps 同刻阈值也按这一精度判定：load 与 `in_clk` 上升穿越之差落在 1 ps 的 B 之内、且 B 超过 0.1 ps 时，报证据精度不足。界限取 0.1 ps 的理由：要让设计上短 1 ps 的激励（1 ps 是合同写明的最小时间量，即同刻阈值）在最不利的舍入下仍判越界，需要 B < 0.5 ps；按等号接受的设计短缺最多为 2B，取 B ≤ 0.1 ps，使它不超过 0.2 ps，也与 checker 已有的网格容差（2 ps 的 5 %，即 0.1 ps）一致。0.1 ps 是本轮的取值，改 `PRECISION` 一个常数即可。双精度下，默认参数时两条边沿都终于 512 s（2^9 s）之后，等号附近的间隔报证据精度不足（B = 1.14e-13 s）；一端在 512 s 前、一端在后为 8.5e-14 s，都在 256–512 s 为 5.7e-14 s，仍按等号判合法。1024 s 处 B = 2.27e-13 s，短 1 ps 判越出合同，长 1 ps 合法，等号报证据精度不足。从 2048 s 起，2 ps 网格的行距（1.82 与 2.27 ps）已超出 2.1 ps 的分辨率检查。题面未改，没有加运行时长上限；证据精度不足与其他基础设施失败一样不判分，题面已有的说明可以覆盖。

     代价与适用范围：B 不超过 0.1 ps 时，短于 B 的差别按等号处理（1 ns 处约 2e-25 s，0.5 ms 处约 1.1e-19 s）；fix-r3 的 8 ULP 余量下判为合法的“短 4 个 ULP”激励，现在判越出合同。推导只覆盖双精度表示，不覆盖仿真器自身的数值误差，也不覆盖只写 13 位有效数字的时刻。旧版 EVAS 0.8.7 在 `minimum-tr-pulses` 第一个 4 ps 脉冲的 301 ps、305 ps 处另存了两个内部样本，电压比 PWL 高或低 4.5e-7 V，观测高电平比 4*tr 短 1.17e-25 s，超出该处 5.3e-26 s 的 B，这些全部行因此重判为激励越出合同；只用 2 ps 网格行时不受影响。fix-r5 给这些恰为最小值的脉冲加了设计余量，见第 9 条。
   - fix-r5（主控交办第 3 项）：题面验收段在 “A missing simulator, or any other execution or infrastructure failure, is not evidence that the model behavior is wrong.” 之后加一句 “If the saved times are too coarse to decide whether a stimulus separation meets its minimum, the case is not graded.”，对应 checker 现有的证据精度不足（`evidence precision insufficient`，记 checker_error，不判分）。checker 对 1 ps 同刻阈值的精度判定也报这一错误；同刻与否决定 load 能否免去与上升沿相隔 20 ps 这一最小值，也属这句话所说的情形。
9. 最小脉宽和不重排：输入高电平至少 `4*tr`；无复位相隔的相邻已接受脉冲，后一上升输出沿距前一下降输出沿至少 `4*tr`。理由：输出过渡最长 `tr`、检查窗口长 `tr + 2*tau_t`，相邻输出沿需可分；DS1023 也规定最小输入脉宽。数值是作者初值。
   - fix-r5（主控交办第 1 项，激励留余量）：fix-r4 用旧版波形重判时，`minimum-tr-pulses` 的全部行由评分变为激励越出合同，原因是旧版 EVAS 在第一个 4 ps 脉冲的两个穿越处另存了偏离 PWL 4.5e-7 V 的内部样本。Spectre 也可能这样：参考手册 21.1 第 200 页写明全局选项 `src_allbrkpts` 缺省为 no，PWL 拐点未必都是断点，保存点也可能偏离 PWL。激励是否合法正好取决于等号判到哪一侧，属于影响评分的平局，所以改用例避开。
     - 扫描：在 2 ps 选通行上记录 checker 的 8 处、10 类最小间隔比较（公开与私有共 7 个用例，两种时刻写法）。差值在 B 之内的只有 9 处，都在 `minimum-tr-pulses`：5 个 4 ps 脉冲的 `in_clk` 高电平恰为 `4*tr`；其中未被复位取消的 4 个，输出上升沿到下降沿也恰为 `4*tr`。其余比较离最小值最近的是 `reset-and-initial` 的 41 ps 输出低电平，比最小值多 1 ps。同刻阈值见第 5 条。
     - 做法：这 5 个脉冲各加 1/8 ps 设计余量，拐点全部留在 2 ps 网格上。脉冲的一条边沿在斜坡外 2 ps 处多一个 0.1 V 的拐点，使穿越落在 0.1 V 到 0.9 V 的 2 ps 段上：上升沿前加“脚”，穿越提前 1 ps − 2 ps × 0.35/0.8 = 1/8 ps；下降沿后加“尾”，穿越推迟 2 ps × 0.45/0.8 − 1 ps = 1/8 ps。输出上升沿落在两行之间（奇数 ps）的脉冲加脚（301、1901 ps 处的脉冲），落在网格行上的加尾（901、1501、1561 ps 处的脉冲）。这样每个保存行在保持区间、边沿窗口和合并窗口里的角色都与改前相同；全加脚或全加尾都会让某个保持行离开保持区间。改后高电平与输出脉宽都是 4 1/8 ps，`in_clk` 由 34 个点变为 39 个点，其余输入和其余 5 个用例逐字节不变。
     - 余量推导：一个间隔的观测误差来自两端穿越各自的保存样本偏差 Δv 与保存时刻偏差 Δt，至多为 (Δv/0.4 V/ps + Δt) + (Δv/0.45 V/ps + Δt)。1/8 ps 可承受每个样本约 26 mV（Δt = 0），或每端 62.5 fs（Δv = 0）。下限：这 9 处的 B 不超过 4.2e-25 s，余量约为它的 3e11 倍；旧版的偏差是每个穿越约 1e-18 s（4.5e-7 V），余量约为它的 1.2e5 倍。对 Spectre 的假设：全部拐点都在 2 ps 选通点上，Spectre 在每个选通点强制取时间点，保存的是计算值而不是插值（参考手册 21.1 第 456 页），`strobeoutput` 缺省只输出选通点（第 443 页），所以不论 `src_allbrkpts` 怎么定，余量只依赖选通网格；再假定每个保存的输入样本偏离 PWL 不超过 1 mV、保存时刻偏差不超过 1 fs（比理想电压源应有的舍入级误差宽松得多，也是旧版偏差的 2000 倍以上），这时高电平至多短约 6.7 fs。上限：1/8 ps 小于合同的 1 ps 时间量；4 1/8 ps 仍小于 `tr + 2*tau_t` = 5 ps，两沿窗口照旧重叠，用例仍测最小脉宽附近的行为。
     - 结果（未仿真；旧版开发证据见下文）：改后扫描 0 处在 B 之内，原 9 处的差值都是 1/8 ps。合成波形在每个穿越处另加一个偏离的保存行：照搬旧版参考波形第一个脉冲的偏差，或使两端都缩短高电平的 4.5e-7 V、1 mV、1 mV 加 1 fs、20 mV、25 mV，新激励都合法，30 mV 时越出合同；旧激励在这些偏差下都越出合同。校准候选的被拒矩阵不变。
10. 复位：`rst` 高为复位。上升穿越时取消全部待发沿、结束所有已接受脉冲（其后的下降输入沿不再安排）、输出为高时当即拉低、卸载码；复位期间不接受上升沿、忽略 load；0 时刻已高的 `in_clk`、`load`、`rst` 不算穿越。理由：登记要求复位取消待发事件、不得出现复位后的幽灵沿；复位期间的 load 被忽略与历史 gold 一致，是复位优先的常规写法。`rst` 穿越与输入穿越、调度沿时刻（含被取消的）至少相隔 `max(20 ps, 4*tr)`，避免“沿先到还是复位先到”的数值歧义。
11. 验收尺度：`epsilon_v = 2 mV` 沿用首批；时序容差 `tau_t = 2 ps`，观察网格 2 ps。LRM 5.10.3 规定 `cross()`、`timer()` 事件在真实时刻当时或之后触发，提前方向只需覆盖网格插值，滞后方向另有 `tr` 的余量。早沿按 2 ps 检出，晚沿要超过 `tr + tau_t` 才检出。设计用例中，沿时刻类错误至少差 20 ps；过渡类错误（`2*tr`、固定 10 ps）在窗口端点留下远超 2 mV 的电压误差；居中过渡提前 `tr/2`，在 `tr = 10 ps` 的用例中检出。数值待 Spectre 校准。
   - 相邻沿的检查窗口（fix-r1，F06；fix-r2，R2-01）：每个沿的窗口是 `[t_e - tau_t, t_e + tr + tau_t]`，合法的相邻沿间隔至少 `4*tr`。`tr` 小于 4/3 ps 时窗口会重叠，原 checker 把上一沿的过渡算进下一沿的窗口，误拒正确的最短脉冲（审核 R06：`tr` = 0.5 ps、2 ps 脉冲）。fix-r1 把重叠的窗口合成一个，只按各沿的先后数转向，不再约束每次移动发生的时刻：迟到又压窄的脉冲（审核 N01：期望沿 120/124 ps，输出 125–127 ps）和 `minimum-tr-pulses` 里同类的错误输出（审核 N02）都能通过。fix-r2 改为逐个保存点追踪它可能处于哪一个沿：各沿按顺序、各自单调，只在自己的窗口里移动；窗口结束时或之后的保存点要求该沿已完成，窗口开始时或之前的保存点要求该沿未开始；转向只能发生在下一沿的窗口开始之后。合并区间的两端仍由保持检查负责，所以窗口不重叠时与原检查完全相同，前 5 个用例的判定不变。合同、`tr` 与最小脉宽都未加下限。仍有的代价：两沿都落在相邻两个保存点之间的窄脉冲看不到；宽度小于 `tr + 2*tau_t` 的脉冲两沿之间没有保持区间，一直为低的输出在这类脉冲上看不出，要靠更宽的脉冲和其余用例拒绝。
12. 不设语法限制：验收只看外部行为，checker 不检查写法；用 `transition()` 传输延迟、定时器或队列都可以。传输延迟写法若复位时目标不变，就删不掉待发沿，会在复位用例中被拒；这是行为错误，不是写法限制。
13. 用例共 6 个，公开 1 个；最后一个是 fix-r1 新增的私有用例，fix-r5 只改了它的 `in_clk`，公开用例与台架未变。全部输入为 0 V 到 0.9 V 的 PWL，PWL 拐点都在 2 ps 网格上：

| 用例 | 参数 | 主要区分 |
| --- | --- | --- |
| `contract-base`（公开） | 默认 | 首次 load 前的脉冲被丢弃；load 为高期间码位变化（区分沿锁存与电平、下降沿锁存）；高电平期间 load 保持脉宽；60 ps 脉冲配 209 ps 延迟，两沿同时待发，其间 load 不改时；下一上升输入沿时上一脉冲的下降沿仍待发；load 与上升沿同刻；输出高时复位且其下降沿待发；复位后未重新 load 的脉冲被丢弃；复位期间释放前待发的上升沿，其时刻落在释放之后 |
| `reset-and-initial` | 默认 | 0 时刻 `rst`、`in_clk`、`load` 都已为高；复位期间的脉冲与 load 被忽略，释放后仍未加载；窄脉冲输入已回落、两输出沿都待发时复位（传输延迟写法的目标不变）；未加载时 load 与上升沿同刻；209 ps 到 20 ps 改码后 41 ps 的输出低电平；输出高时复位，本脉冲下降沿与下一脉冲上升沿同时待发 |
| `long-delay-overlap` | `delay_min = 300 ps`、`delay_lsb = 4 ps` | 300–552 ps 延迟，多次在下一上升沿到来时上一下降沿仍待发，并伴随改码；两沿待发时 load；复位时本脉冲下降沿和下一脉冲上升沿待发，后者时刻在释放之后；未加载时同刻 load |
| `parameter-override` | `vth = 0.3`、`vdd = 1.2`、`vss = 0.2`、`delay_min = 50 ps`、`delay_lsb = 7 ps`、`tr = 4 ps` | 120 ps 输入斜坡使固定 0.45 V 门限错 20 ps；输出电平；4 ps 过渡上限；单比特码 1 与 32 暴露位序；37 ps 脉冲配 274 ps 延迟；491 ps 到 120 ps 改码时上一下降沿待发；复位强制拉到 0.2 V |
| `self-loading-burst` | 默认 | `load` 与 `in_clk` 波形相同，每个脉冲用它自己上升沿时的码；首个脉冲只因同刻 load 才被接受；8 个背靠背不同码脉冲，其中一处下降沿在下一上升沿时仍待发 |
| `minimum-tr-pulses` | `tr = 1 ps` | 输入沿 2 ps 斜坡；5 个 4 1/8 ps（`4*tr` 加 1/8 ps 设计余量，fix-r5）脉冲，两沿窗口重叠，检验合并窗口不误拒，也拒绝网格上看得见的迟到压窄输出（fix-r2，审核 N02）；3 个 8 ps 脉冲，高电平有评分行；延迟 20、35、209、23、140 ps，输出沿在网格上与不在网格上；两沿都待发时 load 不改时；两个短脉冲相隔 60 ps；复位取消两沿都待发的脉冲，重新 load 后的脉冲被接受（F06） |

14. 参考解 [solution/circuit.va](solution/circuit.va)：上升穿越锁存脉冲延迟并预约上升沿，下降穿越用同一延迟预约下降沿，两个 `timer()` 各管一个方向，复位清除待发标志并拉低，`transition()` 零延迟输出；load 语句写在 `in_clk` 语句之前，实现同刻规则。未用历史 gold 的变量名或结构。
15. 包装按首批30题的 Harbor 形式。`environment/Dockerfile`、两份 `.dockerignore`、`tests/Dockerfile`、`tests/test.sh`、`solution/solve.sh`、`harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、公开 `check.py` 与首批逐字节相同。题目判定写在 [tests/verify.py](tests/verify.py)，由 `v2_runtime.main` 调用，公开副本相同；它只读波形，不读候选源码或参考解。
16. [tests/calibration/](tests/calibration/README.md)：`mutants.py` 由参考解生成 23 个错误候选和 3 个正确替代实现，README 列出每个候选应在哪个用例被拒及失败类别。fix-r1 补了机器可读的被拒矩阵 [expected.json](tests/calibration/expected.json)（格式照 C264-S1，条目都是待 Spectre 校准的预期），README 改为中文。

### 待用户确认

| 编号 | 选择 | 推荐（已写入题面） | 另一读法 |
| --- | --- | --- | --- |
| Q1 | 逐沿锁码与保持脉宽的冲突 | 逐脉冲锁码：上升沿锁存，下降沿沿用，load 时刻不受限 | 保留逐沿锁码，合法改码域限于输入为低且无待发沿；保持脉宽由合法域保证 |
| Q2 | load 与上升沿同刻 | load 先生效，该脉冲用新码，未加载时也被接受 | 沿先：该脉冲用旧码（未加载则不接受），新码从下一脉冲起 |
| Q3 | 未加载时的脉冲 | 不接受，`out_clk` 保持低 | 按码 0 处理，以 `delay_min` 延迟输出 |
| Q4 | 输出沿时刻的参考点 | 过渡在 `t_e` 开始，`tr` 是到达上限，允许更快 | 50 % 中点在 `t_e`，过渡居中 |
| Q5 | 待发深度 | 每个方向最多一个待发沿（上升到上升、下降到下降的输入间隔都至少为该脉冲延迟加 20 ps） | 允许多个脉冲同时在途，求解者需维护队列；需另定最大在途数 |
| Q6 | 历史 `delay_metric`、`valid` 输出 | 删除 | 保留，并补定逐脉冲锁码下报哪一个码、何时置位与复位 |

## 待定项

未仿真：本机没有 Spectre，参考解、checker 和用例都没有 Spectre 运行证据。`results/reference.json` 与 `results/calibration.json` 尚未生成。

待办：

- Spectre 校准：参考解跑全部私有与公开用例；`tests/calibration` 的候选逐个过同一 checker，结果与 `expected.json` 比对；记录 `minimum-tr-pulses` 中 1 ps 过渡在 2 ps 网格上的输出行；确认 `tau_t` 能覆盖 `cross`、`timer` 的事件定位与 `strobeperiod` 网格；确认同刻的 load 与 `in_clk` 穿越在同一时间点按源码次序执行；记录 Spectre 的 `transition()` 待发过渡行为，据此确认两个传输延迟候选的被拒用例。
- Spectre 校准时核对激励的观测精度：fix-r4 的合法性余量假定保存的输入样本与时刻都在双精度半个 ULP 之内（2 ps 选通网格上，PWL 拐点就是保存行）。fix-r5 已给 `minimum-tr-pulses` 中原先恰为 4*tr 的脉冲加了 1/8 ps 设计余量（第 9 条），它按每个保存样本偏离 PWL 不超过 1 mV、保存时刻偏差不超过 1 fs 设计，可承受约 26 mV 或 62.5 fs。校准时记录各用例 `in_clk` 等输入的保存样本与 PWL 的最大偏差，确认在假设之内。
- 作者校准：按上述结果写结果文件，复核 2 mV、2 ps、`4*tr` 与 20 ps 间隔是否需要调整。
- 难度：结构估计 M-H，未实测。

开发证据（证据目录 `runs/t3-p0-pilot-20261027/r04-spec-delay-pulse-hold/`，待 Spectre 复跑，不作校准、录取或 EVAS 能力验收）：

- 结构与配置：单题包装检查、`benchmark_workbench.py --check`（本题为 implementation 级）、用例生成可复现，以及固定版本 Harbor `TaskConfig` 解析，全部通过。
- Docker：环境镜像与评分镜像各构建一次，7 项检查通过：评分镜像 `/app` 为空，缺交付物判 0 分，环境镜像 `/app` 等于 starter 且不含 `/tests`、`/solution`，参考解安装逐字节一致，缺后端时公开自测退出码 2，独立评分记 `infrastructure_error` 并给 Harbor 0 分。未执行电路。
- Python 合成轨迹：33 个行为模型（3 个正确、30 个错误）× 5 用例共 165 次判决，全部符合事先写下的预期；另 7 项证据有效性控制都判为 checker 错误而非候选失败。
- EVAS `02dee32b`：参考解 6 个用例都过 a、b 阶段。`self-loading-burst` 跑完 c 阶段并通过 checker；其余 5 个在 c 阶段停于 `source transition proof budget exhausted: slot 2, …`（#270 NF-01），最后提交步约在 2.8–3.45 ns；同一网表在不同作业里的预算计数略有差异，最后提交步相同。起始模型在 a 阶段被拒：`module requires an analog block or child instances`。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解 6 个用例全部通过；起始模型因空模块被拒（`ERROR [rust_lowering]: model:0:programmable_delay_cell_Model:no_continuous_linear_ir`）。23 个错误候选的被拒用例与 [calibration README](tests/calibration/README.md) 的预期逐项一致，其余用例通过；其中两个传输延迟候选还在窄脉冲用例中被拒，因为旧版 `transition()` 以新变化替换待发变化，与 LRM 4.5.8 不同。`alt_fast_output`、`alt_level_state` 全部通过。参考解与全部候选只用规则网格行重判，结论都不变。`alt_fifo_queue` 因旧版不支持 `dynamic_state_array_access` 未能运行，属于旧版局限。旧版只给点值，不做可信证明，结果可能不准也不报错；部分 checker 依赖旧版特有的输出行，旧版通过不代表 Spectre 或新版 EVAS 通过。
- fix-r1（审核 `review-pilot-r1` 的 F06、F09、F12、F14；证据目录 `runs/t3-p0-pilot-20261027/fix-r1/`）：
  - Python 合成轨迹（未仿真）：建题时的 33 个模型在 6 个用例上共 198 次判决，全部符合事先写下的预期，前 5 个用例的判定与建题时相同；审核复现 R06 的正确最短脉冲和晚 2 ps 的同形脉冲在修正前被拒、修正后通过，双脉冲、1.2 V 过冲和晚 20 ps 的脉冲修正前后都被拒；F09 边界控制中两个方向间隔 `d + 21 ps` 合法、`d + 19 ps` 判为激励越出合同，R09 的激励仍判为越出合同；建题时的 7 项证据有效性控制仍都判为 checker 错误。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解 6 个私有用例和公开用例全部通过，只用网格行重判结论不变，前 5 个用例的结论与建题时相同。26 个校准候选中，除 `alt_fifo_queue`（旧版不支持数组状态）外的 150 次判定有 147 次与 `expected.json` 一致，另 3 次是 `conditions` 写明的传输延迟候选的旧版额外拒绝。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r1/scripts/docker_check.py`，照 C264-S1 的脚本，镜像标签 `vabench-p0-fix:`），7 项检查通过：评分镜像 `/app` 为空，缺交付物判 0 分，环境镜像 `/app` 等于 starter（含改过的公开 `verify.py`）且不含 `/tests`、`/solution`，参考解安装逐字节一致，缺后端时公开自测退出码 2，独立评分记 `infrastructure_error` 并给 Harbor 0 分。未执行电路。
- fix-r2（审核 `review-pilot-r2` 的 R2-01、R2-02；证据目录 `runs/t3-p0-pilot-20261027/fix-r2/`）：
  - Python 合成轨迹（未仿真）：建题时的 33 个模型在 6 个用例上的 198 次判决与 fix-r1 相同，全部符合事先写下的预期；R06 的 6 个形状判定不变。审核 N01 的迟到压窄脉冲（125–127 ps）由修正前通过变为被拒，同一设置下的正确输出、两沿各晚 2 ps 或各早 2 ps 的输出仍通过；N02 的错误规则在 `minimum-tr-pulses` 上由通过变为被拒，其余 5 个用例不受影响。“迟到压窄”扫描的 1440 个输出中，764 个在网格上看得见违规，全部被拒，修正前的 checker 接受其中 586 个；其余 676 个，修正前后接受的数目相同。随机生成的 3999 个各沿都在自己容差窗口内单调移动的输出（2031 个两沿窗口重叠）全部通过。激励边界：同方向 `d + 20 ps`、load 与上升穿越 20 ps、码位与 load 20 ps、`rst` 的 40 ps，等号都判为合法，修正前在 50 种整体平移中有 19 到 50 种判为越出合同；少 1 ps 越出合同，多 1 ps 合法；同方向间隔少 2 fs 越出合同，多 2 fs 合法。建题时的 7 项证据有效性控制仍都判为 checker 错误。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解、起始模型和 26 个校准候选的 164 个作业全部重跑，其中 157 对 `tran.csv` 与 fix-r1 逐字节相同，另 7 个作业两边都没有产生波形（试点 r3 审核 R3-02 更正，原写“每个 `tran.csv` 都相同”），判定（全部行与只用网格行）0 项变化；与 `expected.json` 的比对仍是 147 次一致、3 次 `conditions` 写明的旧版额外拒绝、6 次未运行。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r2/scripts/docker_check.py`，镜像标签 `vabench-p0-fix2:`），7 项检查通过，环境镜像 `/app` 等于含新公开 `verify.py` 的 starter。未执行电路。
- fix-r3（审核 `review-pilot-r3` 的 R2-02；证据目录 `runs/t3-p0-pilot-20261027/fix-r3/`）：
  - Python 合成轨迹与内存复现（未仿真）：审核 R3-O01 的两个 0.5 ms 激励（只取 PWL 拐点行）由修正前判越出合同变为合法。把这两段激励连同 load 整体平移到 0.5 ms，在 1.4 ns 活动窗口内取 2 ps 网格行完整评分，修正前上升方向判越出合同，修正后两个方向都合法并通过。同方向 `d + 20 ps` 两个方向在 ns 级和 0.5 ms 各取等号、少一个可分辨量 q、多一个 q（q 取余量的两倍：ns 级 4e-20 s，0.5 ms 处 1.7e-18 s）以及 ±2 fs：等号和多出的激励合法并通过，少的都判越出合同。10 类最小间隔在 ns 级和 0.5 ms 各取等号与 ±1 ps，能经 `delay_min` 或 `tr` 调节的 8 类另取 ±q 与 ±2 fs，124 项全部符合；10 类在 ns 到 1 s 的 13 个量级上只取拐点行，取等号、±q 与短 4 个 ULP，520 项全部符合。等号激励在 0.5 ms 平移 50 种（两种时刻写法）、在 13 个量级各平移 20 种，3600 次完整评分全部合法并通过；修正前的 checker 在 0.5 ms 的 1000 次中有 509 次判越出合同。ns 级的控制修正前后判定全部相同。fix-r2 的合成控制在新 checker 上重跑，3831 项记录中控制判定 0 项变化，只有 checker 哈希与“修正前”参照列不同（参照 checker 由 fix-r1 版换成 fix-r2 版）。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：没有重跑仿真。fix-r2 保存的 157 个作业的 311 份波形（全部行 157 份、只用网格行 154 份）经同一适配器重判：修正前的 checker 与 fix-r2 的记录逐项相同，新 checker 的判定 0 项变化；另 7 个作业没有波形（起始模型空模块、`alt_fifo_queue` 数组状态）。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r3/scripts/docker_check.py`，镜像标签 `vabench-p0-fix3:`），7 项检查通过，环境镜像 `/app` 等于含新公开 `verify.py` 的 starter。未执行电路。
- fix-r4（审核 `review-pilot-r4` 的 R4-01、R4-02；证据目录 `runs/t3-p0-pilot-20261027/fix-r4/`）：
  - Python 合成轨迹与内存复现（未仿真）：审核 R4-O01（1024 s 处保存行恰在穿越上、相距 18.645 ps 的 load 与码位）由修正前的合法变为越出合同；R4-O02 的 10 类各短 1 ps 由合法并通过变为越出合同，原因与类别一致；R4-O03（tr = 1 µs，0.5 ms 处高电平短 2 fs）由合法变为越出合同。fix-r3 的全部控制在新 checker 上重跑（A 20 项、C 124 项、D 520 项、B 2 项与 E 3600 次）：只有 D 的 130 项“短 4 个 ULP”由合法变为越出合同，其余判定不变；fix-r2 的合成控制重跑，3803 项记录中判定 0 项变化。新增 137 项控制全部符合事先写下的预期：1024 s 处 10 类各取等号、短 1 ps、长 1 ps（两种时刻写法），依次报证据精度不足、越出合同、合法并通过；保存行恰在穿越上的等号（ns、0.5 ms、1024 s），等号及其舍入范围内合法，短一个可分辨量、1 ps 或 1 fs 越出合同，1024 s 处落在余量内的报证据精度不足；512 s 两侧各 10 类，B 为 0.057、0.085 ps 时等号合法并通过，0.114 ps 时报证据精度不足；tr = 1 µs 时等号合法、短 2 fs 越出合同；1024 s 处落在 1 ps 同刻阈值余量内的 load 报证据精度不足。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：没有重跑仿真。fix-r3 重判过的 311 份波形再重判：修正前的 checker 与 fix-r3 的记录逐项相同；新 checker 有 26 项变化，都是 `minimum-tr-pulses` 的全部行（参考解、23 个错误候选与 2 个正确替代实现），由评分变为激励越出合同，原因见建设决定 8 的 fix-r4 条；只用网格行的 154 份不变。全部行现为接受 54、拒绝 77、激励越出合同 26。另 7 个作业没有波形（起始模型空模块、`alt_fifo_queue` 数组状态）。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r4/scripts/docker_check.py`，镜像标签 `vabench-p0-fix4:`），7 项检查通过，环境镜像 `/app` 等于含新公开 `verify.py` 的 starter。未执行电路。
- fix-r5（主控交办的三项：激励留余量、同刻阈值、题面一句；证据目录 `runs/t3-p0-pilot-20261027/fix-r5/`）：
  - Python 合成轨迹与内存复现（未仿真）：扫描与余量控制见建设决定 9 的 fix-r5 条。同刻阈值新增 3 项控制（2 ps 选通行，完整评分）：load 恰在上升穿越后 1 ps（B 之内）、短一个可分辨量、长一个可分辨量（约 1.8e-25 s，大于 2B）。改前依次为合法并通过、合法并通过、越出合同；改后恰为 1 ps 一项变为越出合同，其余两项不变。fix-r4 的全部控制在新 checker 与新用例上重跑：fix-r4 新增的 137 项、fix-r3 的 666 项与 3600 次、fix-r4 对审核 R4-O01 至 R4-O03 的复现，判定 0 项变化；fix-r2 的合成控制 3803 项记录中判定 0 项变化，另有 30 个细节值随 `minimum-tr-pulses` 的边沿移动 1/8 ps（失败记录的时刻与数值；早 3 ps 的模型与审核 N02 的错误规则，首个失败改落在第一个脉冲），被拒结论不变。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：改了激励的 `minimum-tr-pulses` 重跑 27 个作业（参考解与 26 个校准候选，标签 `p0-fix5`）。全部行由 fix-r4 的激励越出合同变为评分：接受 19、拒绝 7，与 fix-r2 的结论逐项相同；只用网格行 0 项变化（接受 19、拒绝 7）。新波形在穿越处仍有偏离 PWL 4e-7 到 4.5e-7 V 的内部样本，高电平比 `4*tr` 长 1.25e-13 s，在余量之内。未改的用例用 fix-r4 重判过的波形再重判：修正前的 checker 与 fix-r4 的记录逐项相同，新 checker 0 项变化。被拒矩阵对照 `expected.json`：全部行与只用网格行都是 147 次一致、3 次 `conditions` 写明的旧版额外拒绝、6 次未运行（`alt_fifo_queue`），与 fix-r1 相同。起始模型只在未改的公开用例上有作业（空模块，无波形），未重跑。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r5/scripts/docker_check.py`，镜像标签 `vabench-p0-fix5:`），7 项检查通过，环境镜像 `/app` 等于含新公开 `verify.py` 的 starter。未执行电路。

## 2026-10-29 状态：待用户决定（未仿真）

- 决定单第 24 项与第 35 项都在等用户决定：
  - 第 24 项：输入不变、只改 td 时，排着的待发沿保留还是删除。标准线判读为 JUDGMENT-U15-TRANSITION-TD，Spectre 21.1 删除，LRM 2023 的澄清是保留。
  - 第 35 项：load 与 in_clk 的上升穿越精确同刻。标准线判为平局判据第 1 种，属第 (ii) 类，推荐把 load 沿提前 1 ps，并删去“同刻 load 先生效”一句。
- 定之前，本题的题面、checker、参考解、用例与校准期望都照现状。Spectre 上相关的 7 个作业标“待定”。
- 本节只记状态，上面各节的原文没有改。
