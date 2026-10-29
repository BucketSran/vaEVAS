# 来源与迁移记录

2026-10-27 第二批 B 组迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。评分数值代码、公开与私有用例、参考解行为都没有改。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration-b/v2-test-time-protocol/checks.json`（不入库）。迁移后的审核修正（2026-10-28，fix-b-r1）见“待定项”末段。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-time-protocol/instruction.md)，blob `5c613b4b05de2c15a485b822254a01e1e2068345`，提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-time-protocol/SOURCE.md)，blob `b4559c02cbfb8a3e986dddc8edf1312b3218b58f`。

来源 `v4-346`。本题保留来源工程目标，并保留后来加上的独立实际波形 checker 和窗口协议。原始参考资产仍在 `benchmark/material/historyref/`。公开用例现为 `/app/testbench/cases.json`（原 `environment/public/cases.json` 原字节）。候选壳现为 `/app/circuit.va`，只留端口与原 starter 的 input/output 角色；参数默认值改写在题面。

已保留：模块 `tdc_meter(start,stop,clk,rst,code_0,...,code_7,valid,overflow)`，code_0 为最低位；门限 0.5 V，逻辑输出 0 V 与 1 V；start 上升清旧结果、valid 和 overflow 并重新武装，取消先前区间；武装后每个 clk 上升计数一次；stop 上升锁存计数并解除武装、`valid=1`；未武装 stop 忽略，结果保持；第 256 个 clk 触发饱和值 255、`overflow=1`、`valid=1` 并解除武装；rst 上升异步清所有状态，rst 高时不测量；固定场景没有同时间的输入边沿，同时间语义不属本题；事件后 40 ps 内可平滑，之后 2 mV 误差。code 是结果寄存器输出：start 后至 stop 或溢出之前 code 全为 0、`valid=0`、`overflow=0`，内部累加计数不直接驱动 code；结果发布后 code、valid、overflow 保持到下一次 start 或 rst；初态同 rst 清零后的状态，尚未武装。公开与终评范围：clk 周期 90..130 ps，start/stop 输入边沿 20 ps；测量起止、重武装、未武装 stop 及 reset 时刻可变；终评包含正常锁存、取消区间和超过 256 边沿的区间；输入门限交点不重合，至少隔开 5 ps；计数边界与报告电平固定。

同源关系：首批 30 题与 R01 两题无同源。规划池 C328-S1 的主来源即 v4:346，其计划补的“溢出在 stop 前结束测量、新 start 重启”本题已写明，责任实质相同，存在重复计数风险。规划池登记由主控处理，本题保留原身份。

## 建模选择

这是测试表征。原题面套用了测量题模板句“固定 DUT 源码位于 `/work/public/dut/`，只读”和“固定DUT实现位于 `/work/public/dut/`”，但本题包内没有 `dut/` 目录，start、stop、clk、rst 都是各台架网表里的独立源。按 B 组迁移要求删改这两句：题面改写为“被测事件是每个台架网表中的独立源，没有固定 DUT 模型文件”，公开用例句不再指向 `dut/`。“测量不达标 DUT 时，报告正确结果仍可通过”保留为“仪表是评分对象，被测区间偏离其目标时正确报告仍通过”。这是使题面与包内实际一致的文字更正，不改判据。

原题面没有写参数；原 starter 声明 `tr=20p`，照首批 v2-test-comparator-delay 的做法写入 Spec（“Declare real parameter `tr=20 ps`”），内部变量不进壳。台架不覆盖该参数。端口方向取自原 starter：四个输入、十个输出。

现行题面按已执行失败记 0、原因另记书写。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该历史原义保留在本页，不解释成缺 Spectre 等于语义错误，也不把现行 0 分解释成行为已被检出。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。

- 题面：原题面只有 “Outputs may be smoothed within 40 ps after an event. After that, the error limit is 2 mV.”，没有说明 guard 也覆盖事件之前、整段不评分与区间中点；本次保留该句，在其后加一段：“This 40 ps timing guard applies around these events: every rising crossing of `rst`, `start`, `stop`, or `clk` through 0.5 V, whether or not the meter is armed or the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 80 ps is not scored. In every longer interval, each output is scored at every saved point more than 40 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.”
  - 对应 checker：`tests/v2_testing.py:58-74` 的 `pieces()`：guard 取用例的 40 ps（`:61`），不长于 `2*guard` 的区间整段跳过（`:64`），其余区间取 `(t+guard, end-guard)` 内的保存点加区间中点（`:66-67`），首尾以 t = 0 与瞬态终点为界；事件表见 `tdc()`（`:262-297`）：`:266-267` 取 `rst`、`start`、`stop`、`clk` 穿越用例门限 0.5 V（`:263`）的上升，`:296` 每个事件都加一段状态，未武装或报告不变也加。除 `pieces()` 外没有别的 guard 用法。
  - 合法输入域加一句：“In every case, public and final, no interval is exactly 80 ps long.”。`end-t<=2*guard` 是浮点比较，名义上恰好 80 ps 的区间相减后可能长出几个 ulp，于是不被跳过、区间中点被评分，与第二批 online-gain 审核 AR08 同类；checker 不动。核验（未仿真）：对全部私有与公开用例，取网表与支撑文件都和现行用例相同的旧版参考波形，在内存中记录 checker 实际划出的区间。没有区间落在 80 ps ± 1 fs 内。不长于 80 ps 的最长区间 77.500 ps（private/terminal-extra-stop，33.3025–33.38 ns）；长于 80 ps 的最短区间 82.500 ps（private/terminal-rearm-stop-overflow，0.0–0.0825 ns）。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改报告延迟。应被拒：`late_report_delay_60ps`；应通过（窗内对照）：`inwindow_report_delay_10ps`。
  - 合成控制（未仿真）：底波形为 fix-b-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中提前或推迟报告列后直接调用本题 checker。`late-report-+60ps` 4 个私有用例都被拒；`inwindow-report-+10ps` 4 个私有用例都通过；`early-report--60ps` 4 个私有用例都被拒；`inwindow-early-report--10ps` 4 个私有用例都通过；未平移的底波形 4/4 通过。共 20/20 符合预期。
  - 旧版 EVAS 0.8.7：`late_report_delay_60ps` 4 个私有用例都被拒；`inwindow_report_delay_10ps` 4 个私有用例都通过。有预期的 8 例中 8 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/terminal-rearm-stop-overflow、public/rearm-stop-overflow）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。旧作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。测试表征索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。这些记录不证明当前 Harbor 包。原 SOURCE 写“新增固定只读 DUT”，本题实际没有固定 DUT 文件，该句是家族模板措辞，本次不删原句。模型试跑尚未完成。固定 Spectre，开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解私有 3 个、公开 3 个用例都在 stage b 报 NF-06（dut.va: event integer domains failed the post-fixpoint verification），未进入仿真；`planning/simulation-routes/routes.json` 记的 pulse 幅度界缺口（#8，有条件）被遮蔽未走到。旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 3/3、公开 3/3 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；部分 checker 依赖旧版特有输出行，旧版通过不代表 Spectre 或新版 EVAS 通过。这些结果待 Spectre 复跑，不是校准或录取依据。

2026-10-28 审核修正（fix-b-r1，B03）：迁移时三个私有用例都没有测量中途的再次 start，也没有未武装的 stop。`terminal-extra-stop` 的末次 stop 在 33.38 ns，此时第三次测量才数到 245 个沿，溢出要到 34.5125 ns，所以它仍是普通锁存。新增私有用例 `terminal-rearm-unarmed-stop`，clk 周期 92 ps，stop 38 ns：rst 在 0.45 ns 释放；1.005 ns 的 stop 发生在初态，未武装；2.015 ns start 之后在 4.500 ns 再次 start，即武装中重武装；6.480 ns 的 stop 锁存 21 个沿；9.010 ns 再给一次未武装 stop，此时结果已发布、时钟仍在跑；10.990 ns start 后在 34.4705 ns 溢出；36.010 ns 再给一次未武装 stop。各输入门限交点之间、与任一 clk 交点之间至少隔开 19.5 ps，合同要求 5 ps。公开用例未变，checker 与参考解都未改。

验证（**未仿真**，没有运行 Spectre）：旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 4/4、公开 3/3 通过，只用网格行复判无变化。三个 VA 错例在原三个私有用例都通过，在新用例都被拒：武装中忽略 start 的版本在 6.548 ns 报 48 而不是 21；未武装也锁存的版本在初态 stop 之后 1.12 ns 起 valid=1；stop 后计数器继续、后续 stop 重新锁存的版本在 9.124 ns 改写结果。这些是旧版开发证据，待 Spectre 复跑，记录在 `runs/t3-batch2-20261027/fix-b-r1/`（不入库）。

未决：未发现题面数值与固定 checker 冲突。checker 把同一时刻的事件按 rst、start、stop、clk 排序；题面写明同时间语义不属本题，固定用例输入交点至少隔开 5 ps。
