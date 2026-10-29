# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真。频率公式、阈值和误差保持迁移前题面，不用参考测量器的内部变量代替它们。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-clock-frequency/instruction.md)，blob `25b8310bbc0ab67eec45efe41757c975b0cb1635`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-clock-frequency/SOURCE.md)，blob `63c6c71d4d78f0af141eff917f96244de9b1ce8f`。

来源 `v4-362`。原始参考资产仍在 `benchmark/material/historyref/`。固定 DUT 现为 `/app/testbench/dut/dco.va`，模块 `frequency_word_dco`。公开用例现为 `/app/testbench/cases.json`。候选现为 `/app/circuit.va`。

已保留：阈值 0.45 V；`freq_mhz=1e-6/最近 DCO 周期`；`divider_ratio=最近分频周期/最近 DCO 周期`，任一路新周期都更新；两周期齐才 `valid=1 V`；reset 上升或 enable 下降清历史和报告；禁用或复位时不采边沿；`divide_ratio` 是每多少个 DCO 上升沿翻转一次，完整周期比为 2 倍；`tr=20 ps`，guard 80 ps；频率误差 0.8 MHz，周期比 0.03，逻辑 0.01 V。公开范围：`f_min` 80..130 MHz，`f_step` 2..5 MHz，`divide_ratio` 3..7，并可改频率码、复位和禁用时刻。DUT 源码默认 `vdd=0.9`、`vss=0`、`vth=0.45`、`f_min=80e6`、`f_step=2e6`、`f_max=250e6`、`divide_ratio=4`、`tr=100 ps`。

## 建模选择

候选是仪表，不是 DCO。接口壳只留端口。`tr=20 ps` 由求解者声明。满足测量定义即可。不得驱动观测时钟，也不得用 DUT 参数代替边沿测量。DUT 性能不合格时，正确测量仍可通过。

现行题面写已执行失败记 0、原因另记。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该原义保留，缺 Spectre 不是语义错误。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：原题面只有 “The timing guard is 80 ps.”，没有说明 guard 覆盖事件之前、整段不评分与区间中点；本次保留该句，在其后加一段：“The timing guard applies around these events: every rising crossing of `dco_clk` or `div_clk`, every rising crossing of `reset`, and every falling crossing of `enable`, all through 0.45 V, whether or not the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.”
  - 2026-10-28 主控更正说现行题面已写明这些规则（第 11 行或第 15 行一段）；核对 `HEAD` 与本轮改前副本（`orig/`），那一段是本轮新加的文字，不是迁移时已有的。按更正逐句核对时，把区间规则改写成“事件与瞬态起止划分区间”：先前的写法没有把 t = 0 与瞬态终点当作区间端点，首尾两段的整段跳过和中点规则说得不全。改写后各句与 `pieces()` 和本题事件表一致，之后不再改题面。
  - 对应 checker：`tests/v2_testing.py:58-74` 的 `pieces()`：guard 取用例的 80 ps（`:61`），不长于 `2*guard` 的区间整段跳过（`:64`），其余区间取 `(t+guard, end-guard)` 内的保存点加区间中点（`:66-67`），首尾以 t = 0 与瞬态终点为界；事件表见 `tests/v2_testing.py:181-206`（`:183-186` 取四类穿越，`:205` 每个事件都加一段状态，报告不变也加）。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_report_delay_100ps`；应通过（窗内对照）：`inwindow_report_delay_50ps`。
  - 合成控制（未仿真）：底波形为旧版 first30-r1 的参考波形，在内存中提前或推迟报告列后直接调用本题 checker。`late-report-+100ps` 3 个私有用例都被拒；`inwindow-report-+50ps` 3 个私有用例都通过；`early-report--100ps` 3 个私有用例都被拒；`inwindow-early-report--50ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 15/15 符合预期。
  - 旧版 EVAS 0.8.7：`late_report_delay_100ps` 3 个私有用例都被拒；`inwindow_report_delay_50ps` 3 个私有用例都通过。共 6/6 符合 `expected.json`。参考解抽查 2 例（private/terminal-normal、public/normal）都与 first30-r1 一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

### 2026-10-28 补充（first30-fix-r1）：恰好 160 ps 的区间

`pieces()` 用浮点比较判断区间是否不长于 `2*guard`（`tests/v2_testing.py:64`，`end-t<=2*guard`）。名义上恰好 160 ps 的区间相减后可能长出几个 ulp，于是不整段跳过，区间中点被评分；这与第二批 online-gain 审核 AR08 是同一类问题。checker 不动；题面合法输入域（第 17 行）加一句 “In every case, public and final, no interval is exactly 160 ps long.”。

核验（未仿真）：对 3 个私有与 3 个公开用例，各取网表与支撑文件都和现行用例相同的旧版参考波形，在内存中记录 checker 交给 `pieces()` 的状态表。没有区间落在 160 ps ± 1 fs 内。离 160 ps 最近的都在 `terminal-different-frequency-map`：不长于 160 ps 的最长区间 102.617 ps（189.897–190.0 ns），长于 160 ps 的最短区间 287.694 ps（162.162–162.45 ns）。其余用例里不长于 160 ps 的区间都是 `dco_clk` 与 `div_clk` 同时上升的零长区间，长于 160 ps 的最短区间为 500 ps 至 2000 ps。脚本与结果：`runs/t3-harbor30-20261027/first30-fix-r1/scripts/measure_intervals.py`、`measure/intervals.json`。波形是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

### 2026-10-28 补充（tolerance-r1）：用例网表写明容差与输出设置

D1 冻结前总协调定的第 (ii) 类题目修正：用例网表显式写出容差和输出设置。只改台架的容差和输出设置；激励、合同（`instruction.md`）、checker、参考解、候选、`v2_runtime.py` 与 `adc_linearity.py` 都不动。未仿真。

- 改了哪些行：`environment/public/cases.json` 3 例、`environment/starter/testbench/cases.json` 3 例、`tests/cases.json` 3 例，共 9 个网表。每个网表只改 options 与 tran 两条语句；激励、include、实例与 save 行逐字节不变。
  - 在 `tran` 语句前新加一行 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`。
  - `tran` 语句末尾补 `errpreset=moderate`；`stop`、`maxstep` 不改。
- 取值与来源：标准线 `D1-TOLERANCES.md`（sha256 `55fa799a…`）与 `D1-TOLERANCES.json`（`fbbbebbb…`）；写法按标准线网表约定清单 `LIST.md` 第 3 版（`6a6b17cd…`）。
  - reltol 1e-6、vabstol 1e-8 V、iabstol 1e-12 A，D1 的 12 题一样。本题 checker 的判据：电压 10 mV，guard 80 ps，频率 0.8 MHz，分频比 0.03；标准线按局部截断误差估计，这组容差下的解算误差应远小于最严的判据；这只是选值的依据，不是已证明的全局误差上界，实际误差、事件时刻和耗时待 Spectre 校准验证（D1 容差复审 TOL-01）。本题输出 freq_mhz 以 MHz 为单位，取值远大于 1.5 V，标准线“信号在 1.5 V 以内”的前提不适用；按 reltol 1e-6 计，其局部误差容限约为 1e-6 乘以该值，仍远小于 0.8 MHz 的判据（推导）。iabstol 取 Spectre 缺省 1e-12，本题 save 的都是电压。
  - `errpreset=moderate` 是 Spectre 的缺省。本题校准网表没写 errpreset，按缺省就是 moderate；现在写明，行为不变（运行环境当时是否另设，见下面“历史身份”一条）。
  - 本题不用 strobe，不写 strobeoutput。
  - precision 不写进用例网表，由主控另排一轮放在 Spectre 执行路径里；`src_allbrkpts` 等批次 C。
- 历史身份：10-10 历史作者校准（run `final-a5-cb789-equivalent-20261010T2140Z`）用的 `tests/cases.json`（`59581f81…`，在 git `c3771e59` 中核对，当时路径 `benchmark/tasks/v2-test-clock-frequency/tests/cases.json`）没有写本轮补的设置。当时实际生效的容差未知，可能是 Spectre 缺省，也可能是运行环境的设置。所以改后的结果与历史结果按不同的执行身份对待。本文件前面各段说的网表或公开 `.scs`“未改”“逐字节不变”，只指当时那一轮。
- 旧版 EVAS 0.8.7 开发检查：参考解跑 3 个私有与 3 个公开用例，判决与改前最近一次旧版记录逐项相同（6/6 通过），输出行数与各行数值也相同。旧版日志回显的容差由缺省 reltol=0.001、vabstol=1e-06 变为 1e-06、1e-08。新写的参数没有被拒，也没有警告。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v2-test-clock-frequency/`，D1 的对照作业从那里取原网表。改后 sha256：`environment/public/cases.json` `2f75b953…`；`environment/starter/testbench/cases.json` `2f75b953…`；`tests/cases.json` `bd800326…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。不证明当前 Harbor 包。模型试跑尚未完成。开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：无新的公式冲突。DUT 源码默认 `f_max=250e6` 不在公开扫描句子里；公开扫描只写了 `f_min`、`f_step` 和 `divide_ratio`。本次不把 `f_max` 扩成新的公开扫描范围。
