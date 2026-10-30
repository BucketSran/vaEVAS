# 来源与建设记录

2026-10-27 按 P0 试点新建，阶段 implementation，`pending = ["grading", "runtime"]`。本机没有 Spectre，本题未经 Spectre 仿真；EVAS 结果只作开发证据。本页不表示科学校准、模型试做、题目审核或正式录取。

## 行为依据

### 规划候选身份

| 项目 | 值 |
| --- | --- |
| task_id | `U15-S1`（规划候选，规格建模） |
| unit_id / primary_ref | `U15` / `C287` |
| 主来源 | `src-76e425b8eda2`：v4 360 公开题面，SHA256 `61db2c239acb0e170becd05de3770172e40f7590fe700058493d614ff7aec6de` |
| 规划登记 | [register.json](../../../../planning/history-candidates/register.json) 的 U15-S1：P0，结构估计难度 M-H，建设成本 M。作者工作为“解决逐沿锁不同延迟与保持整脉宽的冲突，选定逐脉冲锁码或合法改码域；补 load 同刻、未加载和最小脉宽”。`spec_plan` 建议上升沿锁存整脉冲的延迟、下降沿沿用，后续 load 只影响下一脉冲，公开周期、延迟跨度和最小低电平以保证不重排，复位取消所有待发事件 |
| 验收与回退 | 登记的 `acceptance`：高电平期间改码、有待发沿时复位、背靠背不同码下逐个核对输出脉冲，复位后不得出现幽灵沿。`rollback`：若只剩固定延迟或换参数，不另计独立任务 |
| Grok 意见 | 部分采纳：不采纳“原行为已完全可成题”，高低沿之间改码时两条要求冲突；采纳延迟单元的工程价值（[候选说明](../../../../planning/history-candidates/CANDIDATES.md#u15-s1)） |
| 规划说明 | [规划 README](../../../../planning/history-candidates/README.md) 把 U15 列入 P0 首批；C290（DLL）一段写明上下沿允许不同码、不能照搬 U15 的保持脉宽合同；U22-I1 以 U15 作可复用执行器来源 |

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

本题只计 U15-S1 一项。`v4-family-360` 是新组名，按 v4 家族命名，覆盖 v4 360、1360、860 同一内核；正式组名由Benchmark 维护方登记时确定。

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
   - fix-r5（Benchmark 维护方交办第 2 项）：题面写 “Crossings less than 1 ps apart are at the same instant.”，checker 原先按两次穿越的浮点距离 `g <= SAME` 判同刻。恰为 1 ps 时两者不同，而且 checker 的结论取决于两个穿越时刻的舍入方向。现在按题面取严格小于，用精确有理数比较：load 与 `in_clk` 上升穿越之差加舍入上界 B 仍小于 1 ps，才算同刻；差值在 1 ps 的 B 之内、与等号无法区分的，按等号处理，不算同刻。这样的 load 距上升穿越不足 20 ps，判激励越出合同。比较用 `short()`，所以 fix-r4 对 1 ps 加的精度判定照旧：B 超过 0.1 ps 且差值在 B 之内时报证据精度不足。全部用例（公开与私有）中，没有任何两个事件恰好相隔 1 ps：输入穿越与调度沿两两比较，间隔离 1 ps 最近的一对也差约 1 ps（同时翻转的码位，间隔约为 0）。
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
   - fix-r5（Benchmark 维护方交办第 3 项）：题面验收段在 “A missing simulator, or any other execution or infrastructure failure, is not evidence that the model behavior is wrong.” 之后加一句 “If the saved times are too coarse to decide whether a stimulus separation meets its minimum, the case is not graded.”，对应 checker 现有的证据精度不足（`evidence precision insufficient`，记 checker_error，不判分）。checker 对 1 ps 同刻阈值的精度判定也报这一错误；同刻与否决定 load 能否免去与上升沿相隔 20 ps 这一最小值，也属这句话所说的情形。
9. 最小脉宽和不重排：输入高电平至少 `4*tr`；无复位相隔的相邻已接受脉冲，后一上升输出沿距前一下降输出沿至少 `4*tr`。理由：输出过渡最长 `tr`、检查窗口长 `tr + 2*tau_t`，相邻输出沿需可分；DS1023 也规定最小输入脉宽。数值是作者初值。
   - fix-r5（Benchmark 维护方交办第 1 项，激励留余量）：fix-r4 用旧版波形重判时，`minimum-tr-pulses` 的全部行由评分变为激励越出合同，原因是旧版 EVAS 在第一个 4 ps 脉冲的两个穿越处另存了偏离 PWL 4.5e-7 V 的内部样本。Spectre 也可能这样：参考手册 21.1 第 200 页写明全局选项 `src_allbrkpts` 缺省为 no，PWL 拐点未必都是断点，保存点也可能偏离 PWL。激励是否合法正好取决于等号判到哪一侧，属于影响评分的平局，所以改用例避开。
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
- fix-r5（Benchmark 维护方交办的三项：激励留余量、同刻阈值、题面一句；证据目录 `runs/t3-p0-pilot-20261027/fix-r5/`）：
  - Python 合成轨迹与内存复现（未仿真）：扫描与余量控制见建设决定 9 的 fix-r5 条。同刻阈值新增 3 项控制（2 ps 选通行，完整评分）：load 恰在上升穿越后 1 ps（B 之内）、短一个可分辨量、长一个可分辨量（约 1.8e-25 s，大于 2B）。改前依次为合法并通过、合法并通过、越出合同；改后恰为 1 ps 一项变为越出合同，其余两项不变。fix-r4 的全部控制在新 checker 与新用例上重跑：fix-r4 新增的 137 项、fix-r3 的 666 项与 3600 次、fix-r4 对审核 R4-O01 至 R4-O03 的复现，判定 0 项变化；fix-r2 的合成控制 3803 项记录中判定 0 项变化，另有 30 个细节值随 `minimum-tr-pulses` 的边沿移动 1/8 ps（失败记录的时刻与数值；早 3 ps 的模型与审核 N02 的错误规则，首个失败改落在第一个脉冲），被拒结论不变。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：改了激励的 `minimum-tr-pulses` 重跑 27 个作业（参考解与 26 个校准候选，标签 `p0-fix5`）。全部行由 fix-r4 的激励越出合同变为评分：接受 19、拒绝 7，与 fix-r2 的结论逐项相同；只用网格行 0 项变化（接受 19、拒绝 7）。新波形在穿越处仍有偏离 PWL 4e-7 到 4.5e-7 V 的内部样本，高电平比 `4*tr` 长 1.25e-13 s，在余量之内。未改的用例用 fix-r4 重判过的波形再重判：修正前的 checker 与 fix-r4 的记录逐项相同，新 checker 0 项变化。被拒矩阵对照 `expected.json`：全部行与只用网格行都是 147 次一致、3 次 `conditions` 写明的旧版额外拒绝、6 次未运行（`alt_fifo_queue`），与 fix-r1 相同。起始模型只在未改的公开用例上有作业（空模块，无波形），未重跑。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r5/scripts/docker_check.py`，镜像标签 `vabench-p0-fix5:`），7 项检查通过，环境镜像 `/app` 等于含新公开 `verify.py` 的 starter。未执行电路。

## 2026-10-29 状态：待用户决定（未仿真）

- 决定单第 24 项与第 35 项都在等用户决定：
  - 第 24 项：输入不变、只改 td 时，排着的待发沿保留还是删除。标准审核判读为 JUDGMENT-U15-TRANSITION-TD，Spectre 21.1 删除，LRM 2023 的澄清是保留。
  - 第 35 项：load 与 in_clk 的上升穿越精确同刻。标准审核判为平局判据第 1 种，属第 (ii) 类，推荐把 load 沿提前 1 ps，并删去“同刻 load 先生效”一句。
- 定之前，本题的题面、checker、参考解、用例与校准期望都照现状。Spectre 上相关的 7 个作业标“待定”。
- 本节只记状态，上面各节的原文没有改。

## 2026-10-29 修正 r9（决定单第 24、35 项）

- 状态：上一节“2026-10-29 状态：待用户决定（未仿真）”里的两项已定。用户 10-30（北京时间）说，通过交叉审核即可合入，有问题以后再修；项目协调方据此按推荐定下决定单第 24、35 项，2026-10-29 转达。用户随时可以改。上一节与更早各节的原文都没有改，与本节不一致的地方以本节为准。
- 未仿真：本机没有 Spectre。下文的 Spectre 读数都来自已交回的 P0PC 作业；新改的用例还没有 Spectre 结果，确认作业清单见本节末。
- 本轮记录：`runs/t3-p0-build-20261027/p0-fix-r9/disposition.md`。

### 第 24 项 = A：去掉 6 个“应拒”，用例不动

- 现象：两份传输延迟校准候选 `transport_reset_unchanged`、`historical_per_edge_transport` 的复位都把 `transition()` 的目标写成它已有的低电平，并把 td 改成 0；这时还有按原 td 排着、尚未开始的沿。作者按 LRM 2023 版的澄清认为这些沿保留，候选会出幽灵脉冲或迟到的下降沿，所以登记为应拒。Spectre 21.1 在复位那一刻删掉了全部待发沿，波形与“复位时新建一个零延迟、去往 `vss` 的过渡”一致。
- Spectre 21.1 的 7 个作业（都完整跑完、评分为通过，原期望是拒；预读，尚未正式核收）：

| 候选 × 用例 | 作业包 | 复位时的情形与 Spectre 的结果 |
| --- | --- | --- |
| `transport_reset_unchanged` × contract-base | spectre-P0PC-rec-04-v1（结果包 sha256 51668e9de5337f0e…） | 4380 ps 复位时输出为高，4455 ps 的下降沿待发；Spectre 在 4380 ps 当即拉低，通过 |
| `transport_reset_unchanged` × reset-and-initial | 同上 | 2010 ps 复位时 2106 ps 上升、2166 ps 下降两沿待发；Spectre 没有这个脉冲，通过 |
| `transport_reset_unchanged` × parameter-override | 同上 | 2746.67 ps 复位时输出为高，2823.33 ps 的下降沿待发；Spectre 当即拉低，通过 |
| `transport_reset_unchanged` × minimum-tr-pulses | 同上 | 1960 ps 复位时 2040.875 ps 上升、2045 ps 下降两沿待发；Spectre 没有这个脉冲，通过 |
| `historical_per_edge_transport` × reset-and-initial | 同上 | 与上面 reset-and-initial 相同，通过 |
| `historical_per_edge_transport` × minimum-tr-pulses | 同上 | 与上面 minimum-tr-pulses 相同，通过 |
| `transport_reset_unchanged` × 公开 contract-base | spectre-P0PC-opt-01-v1（结果包 sha256 18363753bc259a37…） | 输入与私有 contract-base 相同，数据逐位相同，通过 |

- 理由：评分不断言基准语言没有规定的行为。
  - LRM 2.4 第 4.5.8 节只写了 td 是传输延迟（“td models transport delay”），以及新排的过渡删掉排在它之后的过渡（“deleting any transitions which would follow a newly scheduled transition”），没有规定输入不变、只改 td 时已排的过渡怎么办。
  - 2023 版第 4.5.8 节的澄清是只在输入改变时新建过渡（“A transition is created when the input expression changes”），所以这里不新建过渡，待发沿保留。这是作者的读法，也是 EVAS 的约定。
  - Spectre 21.1 在这里删掉全部待发沿。标准审核 2026-10-29 的判读（sha256 d968fb4e…）：本项目的语言配置以 2.4 为准，2023 版这一段不在配置里，所以这一情形属语言未规定；Spectre 的做法记为“与 2023 的澄清不一致”，不记为 Spectre 偏差。判读还引了一项已核收的实测：只把 td 改大、输入不变时，Spectre 保留待发沿。
- 改动：
  - `tests/calibration/expected.json`：
    - `transport_reset_unchanged` 去掉 contract-base、reset-and-initial、parameter-override、minimum-tr-pulses 4 个应拒。它已没有别的应拒，不再算错误候选，照探针处理：移出 `candidates`，`mutants.py` 改写到 `probe/`，`conditions` 写明两种读法下各用例的结果和 Spectre 的读数。写法照第二批 online-gain 的 `strict_start_no_margin`（同样移出错误组、在 `conditions` 写两个后端的读数）：两者都是判决随后端而定，而本题也要把两边的读数写下来。C260 的 `probe_step_recursion_25p` 是只对固定台架精确的数值探针，性质不同，没有照它写。
    - `historical_per_edge_transport` 去掉 reset-and-initial、minimum-tr-pulses 2 个应拒。这两例改列“依赖仿真器”，不计入校准，在 `conditions` 写明。它仍是错误候选，应拒用例为 contract-base、long-delay-overlap、parameter-override，靠的是下降沿取下降穿越到达时已装载的码（历史逐沿规则）这一处真错，与只改 td 无关。三例都已在 Spectre 上被拒，与期望一致（私有三例：spectre-P0PC-rec-04-v1，结果包 sha256 51668e9de5337f0e…；公开 contract-base：spectre-P0PC-opt-01-v1，结果包 sha256 18363753bc259a37…；预读）：
      - contract-base：1840 ps 的 load 把码由 50 改为 5。1700 ps 起的脉冲按合同用 170 ps 延迟，2170 ps 下降；候选按新码的 35 ps 在 2035 ps 下降，早 135 ps。Spectre 上第一个失败行在 2.036 ns。
      - long-delay-overlap：1050 ps 的 load 改为码 63。1000 ps 起的脉冲按合同用 340 ps 延迟，1440 ps 下降；候选按 552 ps 在 1652 ps 下降，晚 212 ps。第一个失败行在 1.454 ns。
      - parameter-override：2096.67 ps 的 load 改为码 10。2036.67 ps 起的脉冲按合同用 491 ps 延迟，2527.67 ps 上升；候选在 2160 ps 的下降穿越按 120 ps 安排 2280 ps 的下降，早于待发的上升。按 LRM 2.4 第 4.5.8 节，新排的过渡删掉排在它之后的上升，脉冲没有出现。第一个失败行在 2.534 ns。
      - self-loading-burst 仍应接受，Spectre 上也通过。
    - 公开一侧：题包没有单独的公开期望。P0PC 打包时，因为公开 contract-base 与私有 contract-base 逐字节相同，公开作业套用了 `expected.json` 里私有 contract-base 的同一项。去掉私有一项后，公开作业同样不再有期望，不用另改。
  - `tests/calibration/README.md` 同步；`mutants.py` 生成的 VA 文件逐字节不变，只换了目录。
- 对上文的影响：第 23 行“已待发的沿不会被删除”、建设决定第 12 条“会在复位用例中被拒”，现在只按 2023 版的澄清成立；Spectre 21.1 上这种写法会删掉待发沿（上表）。评分不再依赖这一点。待定项里“记录 Spectre 的 `transition()` 待发过渡行为，据此确认两个传输延迟候选的被拒用例”一条，已由上表回答。

### 第 35 项（按推荐）：保留“load 先生效”的用意，不再评分恰好同刻

- 依据：标准审核把 load 与 `in_clk` 上升穿越恰好同刻判为平局判据第 1 种（两个不同来源的事件恰好同刻）。LRM 5.10.3.1 允许每个事件落在各自穿越之后的时间点上，两种执行次序都合规；本题的评分依赖这个次序，属第 (ii) 类，必须避开。推荐让 load 至少比上升穿越早 1 ps，并删去“同刻 load 先生效”一句。
- 题面：
  - 删去第 20 行 “If a `load` rising crossing occurs at the same instant, the load takes effect first: …” 一句。
  - 第 33 行的合法域改为：对每个 `in_clk` 上升穿越，load 上升穿越至少早 1 ps 或至少晚 20 ps。早 1 ps 及以上的，包括早不到 20 ps 的，在该穿越时已生效：这个脉冲用新码，此前未加载也被接受。晚于上升穿越的，从下一个被接受的上升穿越起生效。恰好同刻与早不到 1 ps 的，不是合法激励。码位与 load 相隔 20 ps 一句不变。
  - 删去第 36 行 “Crossings less than 1 ps apart are at the same instant.”：新合同不再按“同刻”判定。
- checker（`tests/verify.py` 与公开副本，两份逐字节相同）：去掉“同刻视为 load 先生效”的分支，常数 `SAME` 换成 `LEAD` = 1 ps。每个 load 上升穿越对每个 `in_clk` 上升穿越：在前的比较 1 ps，同刻或在后的比较 20 ps，不足就报激励越出合同（checker_error，不判分）。比较仍用精确戳和 `short()`：等号合法，精度判定照旧。
- 用例：恰好同刻的 load 在 4 个私有用例里，共 11 处：contract-base 1 处（3600 ps）、reset-and-initial 1 处（2400 ps）、long-delay-overlap 1 处（3800 ps）、self-loading-burst 8 处（每个脉冲）。公开 contract-base 的 `cases.json` 与 `visible_test.scs` 各 1 处。本轮要求里的“5 个用例”就是这 4 个私有用例加公开副本。parameter-override、minimum-tr-pulses 没有同刻的 load，未改。
  - 提前量：项目协调方 2026-10-29 定，用例不压在合同下界上，提前量大于 1 ps，取 2 ps 与“1 ps 加该用例的一个保存网格步”中较大的一个。这 4 个用例（以及公开副本）的 tran 行都写 `strobeperiod=2p`，Spectre 只输出选通点，保存网格步是 2 ps，所以各取 3 ps。
  - 做法：这 13 处 load 上升沿的两个拐点各提前 3 ps（例如 contract-base 的 `3590p`、`3610p` 改为 `3587p`、`3607p`），穿越由与上升穿越同刻改为早 3 ps。其余字节不变，期望不变。
  - 依据第 (ii) 类的余量规则（样板第 3 节）：激励不压在合同边界上。2 ps 的余量是样本偏差规则（每个保存样本偏 1 mV、时刻偏 1 fs）下两端最多损失约 46 fs 的约 43 倍，不超过一个网格步。
  - 代价：这 13 处 load 上升沿的拐点落在奇数 ps，不再在 2 ps 网格上（建设决定第 13 条原说“PWL 拐点都在 2 ps 网格上”）。不影响观测：穿越在 20 ps 斜坡的中点，两侧最近的保存行都在斜坡内部、离拐点至少 9 ps，线性插值得到的就是精确穿越；穿越也不再恰好落在保存行上。
- 精度核对（未仿真）：
  - 新合法域与 3 ps 提前量下，精确比较确定地落在合法一侧。在 2 ps 选通行上（按 Spectre 的 PWL 求值式取值，两种时刻写法），11 处提前量减去 1 ps 都是 2 ps，与 2 ps 的差不到 1.2e-25 s；舍入上界 B 为 5.5e-26 至 8.3e-25 s，远小于 0.1 ps，不会判成证据精度不足。按样本偏差规则朝缩短提前量的方向偏移后，仍比 1 ps 多 1.954 ps，合法。
  - 合同下界恰为 1 ps 时：精确比较按等号判合法（差值在 B 之内），也不会判成证据不够；但只要样本偏差超过 B（约 1e-25 s）就会翻成越出合同，按样本偏差规则最多缩短约 46 fs。所以用例不压在这里，只在合成控制里测。
- 参考解不改。load 语句写在 `in_clk` 语句之前，原是为同刻规则（建设决定第 14 条）；新合同下两者至少相隔 1 ps，两种语句次序结果相同，现有写法仍满足合同，不改最省事。它只用 `cross()`、`timer()` 和零延迟 `transition()`，与在 spectre-P0PC-must-01-v1（结果包 sha256 56bb45ddcc96029e…，已核收）上跑过的参考解逐字节相同。
- 校准候选 `edge_first`：它与参考解只差 load 与 `in_clk` 两条事件语句的次序，只在两者恰好同刻时结果不同。它原来在 contract-base、reset-and-initial、long-delay-overlap、self-loading-burst 上的应拒全靠同刻的 load；新合同排除了同刻，这些 load 又都提前了 3 ps，没有合法激励能把它与参考解分开。所以它的期望不能不变：改列正确组，6 个用例都应接受，`mutants.py` 改写到 `correct/`。本轮要求没有写到这一处，交 Benchmark 维护方定（也可以改为探针或删去）。它在旧网表上的 P0PC 结果（spectre-P0PC-rec-03-v1，结果包 sha256 0ce565dbd403ca6c…，预读）是这 4 例被拒，与旧期望一致。
- 对上文的影响：建设决定第 5 条（同刻 load 先生效，以及 fix-r5 的 1 ps 同刻阈值）、待用户确认 Q2、用例表里四个用例的“同刻 load”、第 14 条的“实现同刻规则”，都由本项代替；待定项里“确认同刻的 load 与 `in_clk` 穿越在同一时间点按源码次序执行”一条不再需要。fix-r5 那一条说 checker 对 1 ps 同刻阈值也做精度判定，现在这一判定用在 1 ps 的提前量下界上。
- 公开测试台说明 `environment/starter/testbench/README.md` 第 25–26 行仍写 “a load at the same instant as a rising `in_clk` edge”。它不在本轮的改动范围内，留给 Benchmark 维护方改（建议改为 “a load 3 ps before a rising `in_clk` edge”）。

### 总时限

- `task.toml` 的 `[verifier] timeout_sec` 由 600 改为 840（样板第 4c 节，项目协调方已同意）：私有用例 6 个 × 120 s = 720 s，加 max(10 %, 60 s) = 72 s，得 792 s，向上取整到整分钟为 840 s。
- 用例时限 120 s 不变：已交回的 P0PC 作业里，参考解最长 18.8 s（spectre-P0PC-must-01-v1，结果包 sha256 56bb45ddcc96029e…），正确候选最长 28.8 s（`alt_level_state` 在 self-loading-burst，spectre-P0PC-rec-04-v1，结果包 sha256 51668e9de5337f0e…），2 倍取整为 60 s，120 s 已够。改时限只改资源限制，判决与期望不变。

### 确认作业（只列清单，未打包）

- 清单在 `runs/t3-p0-build-20261027/p0-fix-r9/spectre-jobs/`，分两组，打不打、打哪组由项目协调方定。作业网表 = 改后的用例网表 + P0PC 的容差补写 + 执行路径一行；与 P0PC 同名作业的网表只差 V_LOAD 一行。
  - 甲组：改了网表的 4 份用例网表（公开 contract-base 与私有逐字节相同，不另列），参考解各一个，期望通过；按 P0PC 同例实测约 1.0 分钟，上限 9 分钟。
  - 乙组：这 4 个用例上有期望的候选，共 99 个作业，期望拒 50、过 49；约 38 分钟，上限 223 分钟。

### 开发证据（未仿真）

- 合成波形控制：建题时的 33 个行为模型在 6 个用例上，改前（旧 checker 加旧用例）、改后（新 checker 加新用例）各 198 次判决，都符合事先写下的预期；判决有变化的只有 `edge_first` 在 4 个改过的用例上由拒变为通过，未改的 2 个用例判决逐个相同。load 提前量的边界控制 36 项（18 种激励 × 2 种时刻写法）都符合预期：早 1 ps、早 1 ps 多 1 fs、早 3 ps、早 19 ps、早 20 ps 及以上都用新码，此前未加载也被接受，按旧码输出的判失败；恰好同刻、早 0.5 ps、早 1 ps 少 1 fs 报激励越出合同；晚 20 ps 及以上从下一个脉冲起生效，晚 19 ps 报激励越出合同。证据有效性控制 9 项都报 checker 错误。
- 已交回 P0PC 作业的预先重判（改前、改后两版 checker 与 `expected.json`）：196 个 U15 作业，改前的判决与预读评分逐个相同。未改的 2 个用例上 56 个作业，改后判决逐个相同（含判决摘要），其中 3 个原来与期望矛盾的作业现在没有期望。改了的 4 个用例（含公开 contract-base）上 140 个作业跑的是旧网表，不再适用；新 checker 对其中恰好同刻的 load 按设计报激励越出合同。去掉的 6 个应拒和公开那 1 个都在这两类里，等确认作业。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：改了的 4 个用例上，参考解（含公开 contract-base）5 个作业全部通过，26 个 `mutants.py` 输出共 104 个作业；与改前的旧版判决比，只有 `edge_first` 在 4 例由拒变为通过；只用网格行重判结论不变。对照新的 `expected.json`：99 次一致，1 次是 `conditions` 写明的旧版额外拒绝（`historical_per_edge_transport` 在 self-loading-burst），5 次没有期望（探针 4 次，`historical_per_edge_transport` 在 reset-and-initial），4 次未运行（`alt_fifo_queue`，旧版不支持数组状态）。
- 结构：`python3 -B scripts/benchmark_workbench.py --check --package` 通过（implementation 级静态检查），题包里没有 `__pycache__`。改过的用例网表和确认作业网表按网表约定清单第 4.14 版静态扫描（`runs/t3-spectre-wave2-20261029/scan/list41_scan.py` 的 `check()`），0 处。
- Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-build-20261027/p0-fix-r9/scripts/docker_check.py`，照建题时的脚本，镜像标签 `vabench-p0-fix-r9:`），7 项检查通过，环境镜像 `/app` 等于含新公开 `verify.py`、`cases.json`、`visible_test.scs` 的 starter。未执行电路。

## 2026-10-29 修正 r9 补充轮

- 状态：r9 一节里写“交 Benchmark 维护方定”的几件已定：项目协调方 2026-10-29 照 Benchmark 维护方的建议定下。本节落实其中要写进题包的三件。上面各节（含 r9 一节）原文都没有改。未仿真：本机没有 Spectre。
- 本轮记录：`runs/t3-p0-build-20261027/p0-fix-r9/followup/disposition.md`。

### `edge_first` 改列正确组

- 6 个用例都应接受。`tests/calibration/expected.json`、`mutants.py` 与校准 README 保持 r9 写入的字节。
- 理由：新合同把与 `in_clk` 上升穿越恰好同刻的 load 排除在合法激励之外，而 `edge_first` 与参考解只差同一时刻 load 与 `in_clk` 两条事件语句的先后。按标准审核的平局规则（TIE-RULE.md），两个不同来源的事件恰好同刻属第 1 种；评分依赖这种先后的属第 (ii) 类，评分不能依赖它。合法激励里两者至少相隔 1 ps，`edge_first` 的行为与参考解相同。

### 公开测试台说明

- `environment/starter/testbench/README.md` 第 25–26 行的 “a load at the same instant as a rising `in_clk` edge” 改为 “a load 3 ps before a rising `in_clk` edge”，反引号写法照旧，其余字节不变；这句跨两行，第 26 行的字节没有变。
- environment/ 下其他文字（starter 下的说明、`contract.json` 等）没有写同刻 load 的地方；公开 checker 里出现 “same instant” 的两处是新合同下报错与注释的原文，不是对用例的描述。

### 容差行写入

- 写了什么：`tests/cases.json` 的 6 个用例、公开 `environment/starter/testbench/cases.json` 与 `visible_test.scs` 的网表，在 tran 行之前另起一行 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，tran 行末补 ` errpreset=moderate strobeoutput=strobeonly`。其余字节不变。
- 依据：网表约定清单把这几个容差、errpreset 和用了 strobe 时的 strobeoutput 列为“必须”项。写法照 P0PC 打包时补进作业网表的规则：作业 meta 的 `netlist_fill`（规则 fill-insert）在全部 U15 作业里只有这一种，与 p0-fix-r7a、p0-fix-r7b 给其他 8 道 P0 题写入的两行相同。
- 证明（未仿真）：
  - 每个用例网表写入后加执行路径一行（SL-EXEC-PATH-v1），与 P0PC 同例参考解作业的网表比：parameter-override、minimum-tr-pulses 逐字节相同（spectre-P0PC-must-01-v1，结果包 sha256 56bb45ddcc96029e…，已核收），这两例已交回的参考解与候选作业跑的就是现行网表加执行路径一行，缺省容差对照按 P0PC 的规则去掉这两行后也对得上；改过 load 的 4 个用例和公开副本只差 V_LOAD 一行（r9 的 3 ps 提前）。
  - 开工时只有这 2 个用例的网表 sha256 等于 P0PC 作业 meta 记的 `case_netlist_sha256`；另 4 个和公开副本不等，原因就是 r9 改了 V_LOAD。
  - `cases.json` 按原缩进重写，只有 `netlist` 字段变了；公开 `cases.json` 仍等于私有 contract-base 记录照原规则写出的结果；`visible_test.scs` 仍等于公开网表换 include 路径。
  - 网表约定清单第 4.17 版的静态扫描（`runs/t3-spectre-wave2-20261029/scan/list41_scan.py` 的 `check()`）：改后的用例网表与 `visible_test.scs` 0 处违规。
- checker 与题面不受影响：checker 只读保存的波形与用例记录（参数、stop、resolution），不读网表里的 options 行与 tran 行；r9 的 1 ps 精度核对只用 PWL 拐点与 stop，改后重算，结果不变。

### 确认作业清单

- 按本轮最终字节重出，在 `runs/t3-p0-build-20261027/p0-fix-r9/followup/spectre-jobs/`。作业网表 = 用例网表 + 执行路径一行，与 r9 清单里同名作业的网表逐字节相同。
- 甲组 4 个参考解作业，priority must；乙组 99 个候选作业，priority recommended。打包由 Benchmark 维护方做，不在本轮。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 3 处台架义务检查（U15-02、U15-04、U15-05，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `e3580be1fc26a191b3b984f016fc39e9e076a555323227613d918fdeb7f8a1d6`，改前 `c5684cd1…`）与本文件。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **U15-02**（`logic_crossings` 第 119–120 行）：t = 0 那一行离 `vth` 不足 1 nV 报 “starts at vth” → 按定义判，门槛仍是 1 nV。
- **U15-04、U15-05**（`logic_crossings` 第 121–126 行，穿越取自 `crossings` 第 79–86 行）：`in_clk`、`load`、`rst` 与 `code_5`…`code_0` 的穿越方向不按初值交替时报 “stops on vth”（靠它发现碰到与停后返回）→ 停留、碰到按定义判。扫描指出旧判法漏掉“停在 `vth` 上再继续同向”；按定义判，它报停留。`logic_crossings` 删去，穿越改由 `crossings()` 直接取，穿越的定义不动。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`in_clk`、`load`、`rst`、`code_5`…`code_0` 各自对 `vth`。`check_stimulus` 在参数域、缺波形与分辨率检查之后，取穿越与 load 守卫之前（第 9 小节第 4 条）。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 72 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”；离 `vth` 不足 1 nV，报 “starts … closer than …”；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：穿越仍由 `crossings()` 从保存行取（不变）。

### 3. 余量（数值未改）

- 起点：1 nV 不变（题面只要求起点不同于 `vth`）。改前按 t = 0 的保存行判，现在按定义精确判。本题没有最小偏离检查。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`in_clk`、`load`、`rst`、`code_5`…`code_0` 各自对 `vth`）的起点、停留、碰到按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点对地；没有叠放源（本题网表里受查节点各由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 8 份网表（私有 6、公开 `cases.json` 1、`visible_test.scs` 1）共 72 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 72 个（PWL 72 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(x)` 与 `vth`，参考解在 `V(x) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `programmable_delay_cell` 在 `V(rst)`、`V(load)`、`V(in_clk)` 减 `vth` 上求根（`in_clk` 两个方向，码位按电平读），就是受查输入本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，8 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 8 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前靠穿越方向不交替报 “stops on vth”，现在按定义报碰到与停留。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到：instruction.md 第 28 行 “Legal stimuli: every input is continuous, starts at a level different from `vth`, and passes through `vth` without stopping on it.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 41 行 “A missing simulator, or any other execution or infrastructure failure, is not evidence that the model behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：8 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 316 行）。16 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（16/16）。
- B 候选：扫描列出的 26 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（32 组不同的行，共 5349 行）。改前、改后判决逐个相同，新 checker 不报台架错误（26/26）。
- C 变体（在 `contract-base` 上改 `rst` 的定义；每个变体事先写下预期），12/12 符合预期：
  - `rst` 起点按十进制恰在门限上：报 “starts on”
  - `rst` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `rst` 起点离门限 5e-10 V：报 “closer than”
  - `rst` 起点离门限 2e-09 V：不报台架错误（照常判分）
  - `rst` 在 2.185e-09 s 处按十进制停在门限：报 “rests on”
  - `rst` 在 2.185e-09 s 处只在 binary64 下停在门限：报 “rests on”
  - `rst` 在 2.185e-09 s 处按十进制碰到门限：报 “touches”
  - `rst` 在 2.185e-09 s 处只在 binary64 下碰到门限：报 “touches”
  - `rst` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `rst` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `rst` 的源有一个值带单位 `0V`：报 “cannot read”
  - `rst` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P0PC-must-01-v1 14、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 126、spectre-P0PC-rec-04-v1 30、spectre-P0R9-must-01-v1 4、spectre-P0R9-rec-01-v1 99，共 299 个。new 与改前 checker 整份判决 299/299 相同。与原判比 159 相同、140 不同，就是上面那 140 个（第 9 小节）。

### 8. 前面各节的相关句子

- 建模选择第 15 条（第 109 行）“它只读波形”与修正 r9 补充轮“容差行写入”第 4 条（第 271 行）“checker 只读保存的波形与用例记录…，不读网表里的 options 行与 tran 行”：checker 现在也读用例网表的 vsource 定义与 tran 行的 stop（仍不读 options 行），仍不读候选源码或参考解。
- 前面各节没有写 `logic_crossings` 的起点与交替判法，没有别的句子要代替。

### 9. 第 1 次停下与 Benchmark 维护方的更正

1. 重判时本题有 140 个作业与打包时的原判不同（spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20）：原判都是 graded（passed=True 69 个、False 71 个），现在都报 “stimulus outside contract: load rising crossing at the same instant as, or less than 20 ps after, an in_clk rising crossing”（checker_error）。改前的 checker 给出同样的结果，新 checker 与它逐个相同，所以不是本轮改动造成的。本轮按派单停下报 Benchmark 维护方；Benchmark 维护方核实后定：不算本轮的判决变化。
2. 原因：这些作业跑的是修正 r9 之前的网表。r9 把与 `in_clk` 上升穿越同刻的 load 排除在合法激励之外，并把四个用例的 load 提前 3 ps；“2026-10-29 修正 r9”一节“开发证据”第 2 条已写这 140 个作业不再适用。
3. 快照与现行用例网表：私有 6 个用例都不同。V_LOAD 激励不同的只有 `contract-base`、`reset-and-initial`、`long-delay-overlap`、`self-loading-burst` 4 个；`parameter-override`、`minimum-tr-pulses` 只差容差与 tran 两行（修正 r9 补充轮写入的容差）。公开 `contract-base` 也差 V_LOAD。
4. 这 140 个里 103 个已由 P0R9 按新激励重跑（spectre-P0R9-must-01-v1 4、spectre-P0R9-rec-01-v1 99），新 checker 的判决与原判整份相同。其余 37 个没有按新激励重跑：公开副本 28 个、缺省容差参考 4 个、探针 `transport_reset_unchanged` 4 个、`historical_per_edge_transport` × `reset-and-initial` 1 个；后两类是 r9 去掉了期望的作业。这一选择见修正 r9 的记录（`runs/t3-p0-build-20261027/p0-fix-r9/disposition.md` 第 224、226 行，不入库）。
5. 新的定义检查排在 load 守卫之前：evaluate 依次查参数域、缺波形、分辨率、`check_stimulus`，再取穿越、核精度、查 load 守卫。快照里的 7 份 U15 用例网表（私有 6、公开 1）都过了新的定义检查（7/7），所以这 140 个旧网表先过定义检查，再被 r9 的守卫拒。
