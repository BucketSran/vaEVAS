# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真，没有改 reference、checker 或用例字节，也没有把 gold 或 checker 当成新的科学答案。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-integrate-349-multichannel-readout/instruction.md)，blob `00d77dc28c571e82bbf04ace50aceef80f3a9545`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-integrate-349-multichannel-readout/SOURCE.md)，blob `b9f9c3332dbad0cd44eb6479482cf5a8fabcd22c`。

v4 来源任务是 [349 instruction](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/349-multichannel-sample-readout/public/instruction.md)。本题把从零建 DUT 改成复用健康 024 单通道资产，保留四通道同时采样和 0、1、2、3 顺序读出。固定 `sample_hold` 与 #133 的 024 合同相同。移植版本 SHA256 为 `e58e5baa42c0ec8a82b194da6f63370bf8f08dd819821a7d7f7d25d3abe27e69`。#133 作者删除非标准 `default_transition`、保留标准 include 与 `tedge`，这是作者环境准备，不是候选评分职责。

已保留的行为包括：顶层端口顺序；`vdd=0.9`、`vth=0.45`、`tr=100 ps`；固定部件 `OUT` 初值为 `VSS`、上升穿 `vth` 采样、`tedge=100 ps` 单调过渡、停钟保持且无下垂；四实例 `VSS=0`、`VDD=vdd`；输入在采样沿前后至少 1 ns 稳定；采样适配延迟不超过 50 ps；reset 禁止采样、清指针/`out`/sel/`valid` 和四通道帧，清零在 reset 上升后 1 ns 内完成；无 reset 引脚的部件靠把四输入切到 0 并产生一次有效采样；sample 与 read 同高时先读旧帧再采新帧；read 低不推进；sample 不改正在保持的 `out`。电压容差 3 mV，事件完成后 1 ns 测量。架构版本 `sample-hold-causal-v2`：终评可换成同端口诊断部件，采样值改为 0.75 或 0.6 倍 `IN` 相对 `VSS`，集成必须透明传递，清帧输入 0 仍为 0。原来源是理想行为，不是器件测量。

公开材料按相对路径在 `/app/testbench/`：`baseline.va`、`public-default.scs`、`cases.json`。原 `environment/public/dut.va` 只是候选壳，现为 `/app/circuit.va`，不另留一份在 testbench。

## 建模选择

路线是全 Verilog-A 扩展集成。Spectre 是固定执行后端，不是路线名。候选只收集 `/app/circuit.va`。适配、控制与连接模块可以写在该文件内，文件数不因此增加。必须实例化固定 `sample_hold` 四次；这个组件职责保留。满足接口和外部行为即可，不规定内部状态变量或事件算子。

现行分数规则写在题面：已执行的失败尝试记 0，原因另记；缺仿真器、编译失败、超时、缺波形或其他执行/基础设施失败不是语义错误的证据。历史题面没有单独写“工具链故障不计零分”。历史作者记录把环境或编译失败排除在有效语义拒绝之外，见下方旧身份。两句都保留，不把缺 Spectre 写成模型错误。

### 2026-10-28 补充（tolerance-r1）：用例网表写明容差与输出设置

D1 冻结前总协调定的第 (ii) 类题目修正：用例网表显式写出容差和输出设置。只改台架的容差和输出设置；激励、合同（`instruction.md`）、checker、参考解、候选、`v2_runtime.py` 与 `adc_linearity.py` 都不动。未仿真。

- 改了哪些行：`environment/public/public-default.scs`、`environment/starter/testbench/cases.json` 1 例、`environment/starter/testbench/public-default.scs`、`tests/cases.json` 4 例，共 7 个网表。每个网表只改 options 与 tran 两条语句；激励、include、实例与 save 行逐字节不变。
  - 在 `tran` 语句前新加一行 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`。
  - `tran` 语句末尾补 `errpreset=conservative`（只有两份 `public-default.scs` 需要补；用例网表原来就写着 `errpreset=conservative`，不改）；`stop`、`maxstep` 不改。
- 取值与来源：标准线 `D1-TOLERANCES.md`（sha256 `55fa799a…`）与 `D1-TOLERANCES.json`（`fbbbebbb…`）；写法按标准线网表约定清单 `LIST.md` 第 3 版（`6a6b17cd…`）。
  - reltol 1e-6、vabstol 1e-8 V、iabstol 1e-12 A，D1 的 12 题一样。本题 checker 的判据：各信号 3 mV，保持窗 10 mV，分频沿 500 ps；标准线按局部截断误差估计，这组容差下的解算误差应远小于最严的判据；这只是选值的依据，不是已证明的全局误差上界，实际误差、事件时刻和耗时待 Spectre 校准验证（D1 容差复审 TOL-01）。iabstol 取 Spectre 缺省 1e-12，本题 save 的都是电压。
  - errpreset 沿用校准时的 `conservative`：Spectre 在瞬态里再把 reltol 乘 0.1，实际为 1e-7；EVAS 接受 errpreset 但忽略，按 1e-6。比共同要求更严是允许的。公开台架 `public-default.scs` 原来没写 errpreset，这次补成 conservative，与公开用例一致。
  - 本题不用 strobe，不写 strobeoutput。
  - precision 不写进用例网表，由主控另排一轮放在 Spectre 执行路径里；`src_allbrkpts` 等批次 C。
- 历史身份：10-10 历史作者校准（run `final-a5-cb789-equivalent-20261010T2140Z`）用的 `tests/cases.json`（`c8d729d5…`，在 git `fae1bac2` 中核对）只写了 errpreset=conservative，没有本轮补的其余设置。当时实际生效的容差未知，可能是 Spectre 缺省，也可能是运行环境的设置。所以改后的结果与历史结果按不同的执行身份对待。本文件前面各段说的网表或公开 `.scs`“未改”“逐字节不变”，只指当时那一轮。
- 旧版 EVAS 0.8.7 开发检查：参考解跑 4 个私有与 1 个公开用例，判决与改前最近一次旧版记录逐项相同（5/5 通过），输出行数与各行数值也相同。旧版日志回显的容差由缺省 reltol=0.001、vabstol=1e-06 变为 1e-06、1e-08。新写的参数没有被拒，也没有警告。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v2-integrate-349-multichannel-readout/`，D1 的对照作业从那里取原网表。改后 sha256：`environment/public/public-default.scs` `9a2a4aa5…`；`environment/starter/testbench/cases.json` `bd4200a4…`；`environment/starter/testbench/public-default.scs` `2e8c4c96…`；`tests/cases.json` `e1024708…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。当前题包未仿真。旧作者正负校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`，科学来源 `a5c12a1a01a47e40a7f37b611e55836e59db65cf`。该记录不证明本次 Harbor 入口、当前参考字节或开源同题复现。模型试做和完整 spec 验收仍未完成。归属仍是 Spectre 扩展集。

现行执行约定：已执行失败记 0 且原因单独记录；尚未执行的检查没有成绩，不能编造 0。当前打包失败尝试可以由 Harbor 边界记 0，原因另记。本机没有 Spectre 不是语义错误。

未决：不由 gold 里的 50 ps/200 ps 复位时序或 `transition` 写法改写上面的 50 ps 适配上限和 1 ns 测量点。











## 2026-10-29 校准候选（first30-calib-r1）

首批 D1 只给本题参考解；本节补错误变体与正确替代，随 D2 出包。改了 `tests/calibration/`（新建 `mutants.py`、`expected.json`、`README.md`）与本页；参考解、checker（含公开副本）、用例、题面、starter 都没有改。未仿真，待 D2 Spectre 校准。

- 候选：错误 9 个（`read_pause_advance`、`valid_sticky`、`reset_output_stale`、`reset_clock_high_bank_stale`、`channel0_only`、`read_after_capture`、`continuous_mux_output`、`architecture_bypass`、`original_v4_349_gold`），正确 1 个（`alt_one_hot_token`）；原 gold 套壳 `original_v4_349_gold`（wrong）。
- 被拒矩阵摘要：
  - `read_pause_advance`：全部私有用例与公开用例应被拒；类别：暂停时仍推进读指针。
  - `valid_sticky`：应在 `sample-read-reset`、`architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 与公开 `sample-read-reset` 被拒，其余应通过；类别：read 低时不清 valid。
  - `reset_output_stale`：应在 `sample-read-reset`、`architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 与公开 `sample-read-reset` 被拒，其余应通过；类别：复位不清 out。
  - `reset_clock_high_bank_stale`：应在 `reset-during-sample-high` 被拒，其余应通过；类别：漏掉复位适配（适配时钟已高时复位不清帧）。
  - `channel0_only`：应在 `sample-read-reset`、`architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 与公开 `sample-read-reset` 被拒，其余应通过；类别：连线错（四个部件都采通道 0）。
  - `read_after_capture`：应在 `sample-read-reset`、`architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 与公开 `sample-read-reset` 被拒，其余应通过；类别：状态更新顺序错（先采新帧再读）。
  - `continuous_mux_output`：应在 `sample-read-reset`、`architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 与公开 `sample-read-reset` 被拒，其余应通过；类别：out 连续跟随所选保持节点（sample 改变正在保持的 out）。
  - `architecture_bypass`：应在 `architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 被拒，其余应通过；类别：架构旁路（帧存在变量里，部件不参与）。
  - `original_v4_349_gold`：应在 `sample-read-reset`、`architecture-gain-0.75-sample-read-reset`、`architecture-gain-0.6-sample-read-reset` 与公开 `sample-read-reset` 被拒，其余应通过；类别：原 gold 套壳（v4:349 四文件合一）。
  - `alt_one_hot_token`：全部私有与公开用例应通过；类别：正确替代（独热读令牌）。
- 覆盖缺口（交主控，本轮不加用例）：
  - “rst 为高时的 clk 上升沿清零”从未出现：两例的 rst 高电平段（0–2、101.1–103、16.02–18 ns）都不含 clk 上升沿，把这一分支当普通沿处理的实现能通过全部用例。 建议：加一个 rst 跨过一个 clk 上升沿的用例，该沿 read 与 sample 都为高，使按普通沿处理会读出非零值或采下新帧。
  - 参数覆盖从未出现：vdd、vth、tr 都用缺省值，把 vdd 写死成 0.9 V 的 sel/valid 电平能通过。 建议：加一个 vdd=1.0 V、vth=0.5 V 的用例。
- F01：不是 F01 的情形，但方向相反：检查点在 clk 或 rst 穿越后 0.95–0.99 ns（边沿完成后 0.90–0.98 ns），早于题面“事件完成后 1 ns 测量”；题面又允许清零在 rst 上升后 1 ns 内完成。合法但较慢的清零（例如 0.97 ns 完成）会在 102 ns 的检查点被判错。SOURCE 已把“1 ns 测量点”列为未决。本轮不改题面与 checker，也不加依赖这段余量的候选；全部候选的被拒都来自远离这段余量的检查点，误差在几十 mV 以上。交主控。
- 样板 r2.18–r2.24 各条已逐条核对，结果写在 [校准 README](tests/calibration/README.md) 的同名一节；需要交主控的：349 检查点早于题面“事件完成后 1 ns”与“rst 上升后 1 ns 内清零”（0.90–0.98 ns），合法的慢清零会被误判；SOURCE 已列未决，本轮未改，候选不依赖这段余量；349 “rst 为高时的 clk 上升沿清零”没有用例覆盖（见覆盖缺口）。
- 记忆污染：原 v4:349 gold（四文件合一）自带采样器、不用固定部件，输出驱动在 read 高时连续读保持节点，只在 reset-during-sample-high 上通过、其余三个私有用例与公开用例都被拒：记忆污染低。
- 旧版 EVAS 0.8.7 开发检查（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）：参考解与 10 个候选在 5 个用例上都能运行。除 `architecture_bypass` 外，全部行判决与矩阵逐项一致；`architecture_bypass` 的 5 个运行在全部行上都是 evidence_error（旧版 13 位时间打印造成 13 个重复时间行，`non-increasing waveform times`），只用网格行与去重诊断的判决都与矩阵一致（健康部件两例通过、诊断部件两例被拒、公开例通过）。只用网格行复判没有改变其余运行的判决。
- D1 交回的执行身份：私有包 `spectre-D1-private-v2（结果包 sha256 7ec4fbda83b6db84…）`（118 个作业），公开包 `spectre-D1-public-v2（结果包 sha256 87f515d69aa668a9…）`（29 个作业）。Spectre 线 2026-10-29 正式核收（suite v1.8 加 r8 两项未结 P1 的一次性核对，证据 clean）。核收报告是 `Spectre 线核收报告（私有）`（sha256 `66844d7b…`）与同目录的 `结果包（私有）`（`0701a701…`）；登记文件是 `runs/spectre-returns-20261028/accepted/REGISTER.json`（主控转达时 sha256 `3764e9af…`，之后又追加了别的批次，D1 两条不变）。合成控制读的是 `runs/t3-spectre-batchD-20261028/returns-preread-…/` 下解开的同一结果包，两个 tar.gz 的 sha256 与登记相同。
- 合成控制（未仿真）：D1 Spectre 21.1 交回（2026-10-29 已正式核收，执行身份见上）的参考解波形在内存中改写后由本题 checker 判定，判据控制与候选模型全部与预期一致，见 README。
- D2 估计：50 个作业，一般每个约 25.5 s，串行约 21 分钟，PSF 约 51.5 MB。
- 待办：D2 Spectre 校准（参考解应过，`wrong/` 按矩阵被拒，`correct/` 按矩阵通过）。
- 记录：first30-calib-r1 交付（`runs/t3-harbor30-20261027/first30-calib-r1/disposition.md`）。

## 2026-10-29 修正 r4（first30-fix-r4，第 (ii) 类）

按 F01 用户决定执行（2026-10-28 决定单第 6 项，选 A：题面写明 checker 实际的观察时刻，checker 不改）。另补 first30-calib-r1 交主控的两个覆盖缺口（first30-fix-r4 第 1、3 项）。未仿真，待 Spectre 复跑。

- 改了什么：
  - 题面只改两句：原“Clearing finishes within 1 ns after the reset rising edge.”，新“Clearing finishes within 0.9 ns after the clearing edge crosses `vth`.”；原“The voltage tolerance is 3 mV, measured 1 ns after the event completes.”，新“The voltage tolerance is 3 mV, measured 0.95 ns to 1 ns after the rising `clk` or `rst` edge that causes the event crosses `vth`.”。上文“待定项”里“1 ns 测量点”一条由此落定。
  - `tests/cases.json` 加 `param-vdd-vth-sample-read-reset`（sample-read-reset 的时序，实例写 `vdd=1.0 vth=0.5`，控制信号 0 到 1.0 V，四帧输入都不同）与 `reset-high-across-clock-edge`（rst 在 41.05–47.05 ns 为高，跨过 45.01 ns 的 clk 上升沿，该沿 read 与 sample 都为高）；检查点在引起事件的沿穿越 vth 后 0.95 ns（rst，100 ps 斜坡）或 0.99 ns（clk，20 ps 边沿），与现有用例同一规则；容差与 tran 同现有用例（`reltol=1e-6 vabstol=1e-8 iabstol=1e-12`；`errpreset=conservative`）。现有四例逐字节不变。
  - `tests/calibration/mutants.py` 加三个候选：`rst_high_clk_as_normal_edge`（只错在 rst 为高时的 clk 沿）、`late_clear_after_check`（F01 迟到负例，清零在 1.04 ns 完成）、`inwindow_clear_before_check`（窗内对照，0.92 ns 完成）；`expected.json` 与 `README.md` 同步（见 README 末节）。
  - checker（含公开副本）、参考解、公开用例与现有候选都没有改。
- 为什么：checker 冻结的检查点在穿越后 0.95–0.99 ns，早于题面的“事件完成后 1 ns”，而题面允许清零在 1 ns 内完成，合法的慢清零会被误判（first30-calib-r1 F01 一栏）。用户 2026-10-28 选 A：题面写明实际的观察时刻，期限放在观察点之前。
- 余量依据：期限 0.9 ns 比最早的检查点 0.95 ns 早 50 ps；参考解在 rst 穿越后约 0.16 ns 清完，离期限约 0.74 ns。迟到负例在 1.04 ns 完成，期限与到达之间有 0.95 ns 的检查点，按 out 的 100 ps 过渡，检查点上仍差 0.08–0.33 V（合成控制）；窗内对照在 0.92 ns 完成，0.95 ns 时已到值。冻结检查时刻是十进制写法的 binary64 值，相对“0.95 ns、0.99 ns”只差约 1e-15 ns，题面按“0.95 ns 到 1 ns”写，checker 实际观察点全部在这段里（`runs/t3-harbor30-20261027/first30-fix-r4/slot03/build-write.json` 的 `observation_offsets_ns`）。新用例的控制斜坡离 clk 沿至少 1.91 ns，输入在采样沿前后稳定 2.99 ns，rst 后的两个 timer 离 clk 沿至少 3.76 ns。
- 第 5 项核对（样板 r2.29–r2.35，LIST 第 4.10 版）：
  - 零边沿 transition：参考解 `transition(gate*vdd,0,10p)` 与 `transition(x,0,tr)` 省略 fall，按 LRM 等于 rise，不是零边沿；固定部件写明 rise、fall；td 都是 0。
  - 最后一行与 stop：最后检查点 166 ns、保持窗到 173 ns（stop 175 ns）；`reset-high-across-clock-edge` 最后检查点 96 ns、保持窗到 74 ns（stop 105 ns）；checker 按固定时刻插值，不找 time == stop。
  - 网表第 0.5 节：两例用 `list41_scan.py`（92d7cea1…）扫描无命中；clk 为 pulse，写明 val0、val1、period、rise、fall、width；errpreset=conservative（第 10 条）；PWL 拐角都在平段与斜坡之间（第 4 条）；数字写法没有指数加比例（第 13 条）。
  - TIE-RULE 第 5 类：rst 后的两个 timer（+50 ps、+200 ps）与新候选的清零 timer 离最近的 clk 事件都在 2.8 ns 以上；没有 64 ulp 内的事件。
  - cross 回零根：参考解与候选的 `cross()` 都在 clk、rst 上，都没写 time_tol、expr_tol；max|expr| 为 0.45 V（vth 0.45 V 的用例）或 0.5 V（参数用例），缺省 expr_tol 约 4.5e-7–5.0e-7 V（严容差 reltol 1e-6；conservative 的瞬态值 1e-7，取两者中大的）与 4.5e-4–5.0e-4 V（默认容差对照）；控制信号满摆，上升、下降穿越之间 |expr| 至少到 0.45 V，两根总是分开；评分不依赖回零根计数。
  - pulse rise/fall：clk 写明 20p。idt：没有。touch：控制信号在 0 或满摆的平台上，不需要。
  - 第 20 条：checker 只在冻结时刻与保持窗里按 3 mV 比较，期望值由用例数据给出，没有判“变了没有、是否为零、是否相等”的门限；`times[j]==t` 只是取样方式（正好有行就取该行，否则插值）。无。
  - 第 21 条：checker 不读日志记录。无。一次性 timer：参考解 `@(timer(reset_clock_at))`、`@(timer(reset_release_at))` 与新候选的 `@(timer(clear_at))` 体内都不比较 $abstime。无。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：43 个运行，全部行 42 个出判决、只用网格行 43 个出判决，都与矩阵一致，见 README 末节。
- Spectre 补跑：30 个作业，PSF 约 25.1 MB，单个最大约 1.05 MB，串行约 13 分钟；建议附加 15 个作业，PSF 约 15.7 MB，单个最大约 1.05 MB，串行约 6 分钟；清单 `runs/t3-harbor30-20261027/first30-fix-r4/spectre-jobs/`。
- 改前原文件逐字节存于 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-integrate-349-multichannel-readout/`。改前 → 改后 sha256：`instruction.md` `63192665…` → `75f72fe0…`；`tests/cases.json` `e1024708…` → `3ecbd484…`；`tests/calibration/mutants.py` `b2e53b72…` → `b9dfcb44…`；`tests/calibration/expected.json` `a9680807…` → `f20aef5b…`；`tests/calibration/README.md` `e728cb5b…` → `650bf862…`；本页改后的 sha256 记在交付记录里。
- 记录：first30-fix-r4 交付（`runs/t3-harbor30-20261027/first30-fix-r4/disposition.md`）。
