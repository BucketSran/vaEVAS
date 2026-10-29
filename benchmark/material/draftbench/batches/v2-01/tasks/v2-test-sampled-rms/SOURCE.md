# 来源与迁移记录

2026-10-27 第二批 B 组迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。评分数值代码、公开与私有用例、参考解行为都没有改。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration-b/v2-test-sampled-rms/checks.json`（不入库）。迁移后的审核修正（2026-10-28，fix-b-r1）见“待定项”末段。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-sampled-rms/instruction.md)，blob `92cc4c0e719a17ea9139a6ee995eaf2a0e8410b4`，提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-sampled-rms/SOURCE.md)，blob `a48ef0a29c46816363ec19d95f60af3b6ddba3cf`。

来源 `v4-074`。本题保留来源工程目标，并保留后来加上的独立实际波形 checker 和窗口协议。原始参考资产仍在 `benchmark/material/historyref/`。公开用例现为 `/app/testbench/cases.json`（原 `environment/public/cases.json` 原字节）。候选壳现为 `/app/circuit.va`，只留端口与原 starter 的 input/output 角色；参数默认值改写在题面。

已保留：模块 `sampled_true_rms_to_dc(vinp,vinn,clk,reset,enable,rms_out,valid)`；`vth=0.45 V`、`vhigh=0.9 V`、`tr=100 ps`（原 starter 声明 `from (0:inf)`）；每个 enable 高且 reset 低的 clk 上升沿采样实际差分输入；恰好四个样本形成不重叠窗口，输出 `sqrt(mean(x*x))`；禁用采样边沿不丢弃部分窗口但清 valid；每个完成窗口 valid 高一个采样间隔，下一 clk 上升清 valid；reset 上升异步清累计、报告和 valid，reset 高时采样也清零；rms_out 保持到下一完整窗口；误差 2 mV，事件后 320 ps 允许输出过渡。公开与终评范围：两路输入各在 0..0.9 V，直流或正弦（幅度 0..0.35 V、频率 10..35 MHz）；时钟周期 4..6 ns；reset 与 enable 时刻可变并跨越部分窗口；控制门限交点与采样沿至少隔开 200 ps；四样本窗口、阈值与报告单位固定。

同源关系：首批 30 题与 R01 两题无同源。规划池 C203-S1 的主来源即 v4:074，复用“四个有效样本的 RMS、禁用暂停和异步复位清窗”，与本题交付行为实质相同（本题是测试表征，C203-S1 标按规格建模），存在重复计数风险。规划池登记由主控处理，本题保留原身份。

## 建模选择

这是测试表征。原题面套用了测量题模板句“固定 DUT 源码位于 `/work/public/dut/`，只读”和“固定DUT实现位于 `/work/public/dut/`”，但本题包内没有 `dut/` 目录，被测输入、时钟、复位与使能都是各台架网表里的独立源。按 B 组迁移要求删改这两句：题面改写为“被测输入与控制信号是每个台架网表中的独立源，没有固定 DUT 模型文件”，公开用例句不再指向 `dut/`。“测量不达标 DUT 时，报告正确结果仍可通过”保留为“仪表是评分对象，被测信号偏离其目标时正确报告仍通过”。这是使题面与包内实际一致的文字更正，不改判据。

原 starter 的参数 `vth=0.45`、`vhigh=0.9`、`tr=100p from (0:inf)` 写入 Spec，内部变量不进壳。原题面没有点名 `vhigh` 的用途；本题唯一的逻辑输出是 valid，参考解与 checker 都把 0.9 V 用作 valid 高电平，Spec 写作“valid 的高电平”。公开与私有台架都以 `tr=80p` 实例化仪表，Spec 照实写出，候选因此须保留可覆盖的 `tr` 参数。端口方向取自原 starter：五个输入、两个输出。

现行题面按已执行失败记 0、原因另记书写。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该历史原义保留在本页，不解释成缺 Spectre 等于语义错误，也不把现行 0 分解释成行为已被检出。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。后续修正见文末“复审 F01B-03 修正（f01-r2）”一节：新增 10 ps 网格私有用例，提前负例在该例上被拒。

- 题面：原题面只有 “The error limit is 2 mV, and outputs may transition within 320 ps after an event.”，没有说明 guard 也覆盖事件之前、整段不评分与区间中点；本次保留该句，在其后加一段：“This 320 ps timing guard applies around these events: every rising crossing of `clk` or `reset` through 0.45 V, whether or not a sample is taken or the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 640 ps is not scored. In every longer interval, each output is scored at every saved point more than 320 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.”
  - 对应 checker：`tests/v2_testing.py:58-74` 的 `pieces()`：guard 取用例的 320 ps（`:61`），不长于 `2*guard` 的区间整段跳过（`:64`），其余区间取 `(t+guard, end-guard)` 内的保存点加区间中点（`:66-67`），首尾以 t = 0 与瞬态终点为界；事件表见 `rms()`（`:98-119`）：`:100-101` 取 `reset` 与 `clk` 穿越 0.45 V 的上升，`:118` 每个事件都加一段状态，不采样或报告不变也加。除 `pieces()` 外没有别的 guard 用法。
  - 合法输入域加一句：“In every case, public and final, no interval is exactly 640 ps long.”。`end-t<=2*guard` 是浮点比较，名义上恰好 640 ps 的区间相减后可能长出几个 ulp，于是不被跳过、区间中点被评分，与第二批 online-gain 审核 AR08 同类；checker 不动。核验（未仿真）：对全部私有与公开用例，取网表与支撑文件都和现行用例相同的旧版参考波形，在内存中记录 checker 实际划出的区间。没有区间落在 640 ps ± 1 fs 内。不长于 640 ps 的最长区间 230.000 ps（private/terminal-normal-reset-disable，58.24–58.47 ns）；长于 640 ps 的最短区间 1540.000 ps（public/normal-reset-disable，0.0–1.54 ns）。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改报告延迟。应被拒：`late_report_delay_340ps`；应通过（窗内对照）：`inwindow_report_delay_200ps`。
  - 合成控制（未仿真）：底波形为 fix-b-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中提前或推迟报告列后直接调用本题 checker。`late-report-+340ps` 3 个私有用例都被拒；`inwindow-report-+200ps` 3 个私有用例都通过；`early-report--340ps` 3 个私有用例都通过；`inwindow-early-report--200ps` 3 个私有用例都通过；`diagnostic-early-report--360ps` 3 个私有用例都被拒；未平移的底波形 3/3 通过。共 15/18 符合预期；不符的是 `early-report--340ps`（应被拒而通过，原因见下一条）。
  - 提前方向只有 20 ps 的检出窗：`maxstep` 40 ps 的网格上，每个采样沿前最后一个评分行恰在沿前 340 ps，提前 340 ps 的平移在该行仍是旧值（平移后的过渡恰从这一行开始），所以 `early-report--340ps` 通过；提前 360 ps 的诊断控制被拒。迟到方向的窗有 100 ps、含两条网格行，`late-report-+340ps` 被拒。现有用例做不到提前 340 ps 的检出，交主控，本轮不加用例。
  - 旧版 EVAS 0.8.7：`late_report_delay_340ps` 3 个私有用例都被拒；`inwindow_report_delay_200ps` 3 个私有用例都通过。有预期的 6 例中 6 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/terminal-normal-reset-disable、public/normal-reset-disable）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。旧作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。测试表征索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。这些记录不证明当前 Harbor 包。原 SOURCE 写“新增固定只读 DUT”，本题实际没有固定 DUT 文件，该句是家族模板措辞，本次不删原句。模型试跑尚未完成。固定 Spectre，开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解正弦输入的私有 2 个、公开 2 个用例在 stage c 报 `kernel.unsupported_analytic_source_consumer`（sampled Transition profile requires independent fixed Timer leaves and constant initialization，#270 与 NF 清单未列），dc-input 私有与公开 2 个用例在 stage c 报 NF-11（observer mathematics and control nodes require an isolated observer event），均无提交步；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 3/3、公开 3/3 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；部分 checker 依赖旧版特有输出行，旧版通过不代表 Spectre 或新版 EVAS 通过。这些结果待 Spectre 复跑，不是校准或录取依据。

2026-10-28 审核修正（fix-b-r1，B06）：题面补写“从 t=0 到第一个完整窗口，rms_out 与 valid 为 0 V”。依据是现有 checker 与参考解：checker 初态为 `rms_out=0、valid=0`，第一个完整窗口前的采样沿只清 valid、不改 rms_out；参考解 `initial_step` 清零。数值、用例、checker 与参考解都未改。验证（**未仿真**，没有运行 Spectre）：报告初值为 0.45 V 的 VA 错例在修正前后的三个私有用例都被拒，0.36 ns 起 rms_out 应为 0 V；说明这是已在执行的判据，此前只缺合同文字。这是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，记录在 `runs/t3-batch2-20261027/fix-b-r1/`（不入库）。

迁移时（2026-10-27）未发现题面数值与固定 checker 冲突：checker 的事件邻域为 320 ps（用例 `guard=3.2e-10`），与题面一致，但题面没有写 guard 也覆盖事件之前，也没有写整段跳过与区间中点。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明事件表与区间规则。

## 复审 F01B-03 修正（f01-r2，2026-10-28）

依据增量复审 `runs/t3-batch2-20261027/review-f01-r5/astra-review.json`（A 部分暂不通过）。**未仿真**：没有运行 Spectre。旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；合成控制是已存旧版参考波形在内存中变换后由本题 checker 判定，也未仿真。记录在本地 `runs/t3-batch2-20261027/f01-r2/`（不入库），其中 `disposition.md` 列出命令、退出码与改前改后哈希。

- 问题：提前 340 ps、原过渡 80 ps 时，只有开区间 (e−340, e−320) ps 里的评分点能同时满足“报告已开始变化”和“仍在评分”。旧三例的采样沿都在 20 ps 的整数倍上，40 ps 或 20 ps 的网格点最多只落在这个区间的两端：e−340 ps 仍是旧值，e−320 ps 被 guard 排除；唯一的 `reset` 上升沿（58.47 ns）前 230 ps 就是采样沿，所在区间整段不评分。所以只把网格缩到 20 ps 仍看不出来。
- 新私有用例 `terminal-fine-grid-10ps`，激励与旧例同形：`clk` 为 pulse（`delay=1.6n period=5.3n width=2.4n rise=80p fall=80p`），`reset`、`enable` 为 200 ps 边沿的 PWL，两路正弦输入（`vinp` 为 `sinedc=0.42 ampl=0.3 freq=25Meg`，`vinn` 为 `sinedc=0.47 ampl=0.2 freq=16Meg`），实例 `tr=80p`。
  - 网表照网表约定清单第 3 版写：`simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`；`tran tran stop=110n maxstep=10p strobeperiod=10p errpreset=moderate strobeoutput=strobeonly`；save 列出 checker 读的全部信号；正弦源写 `sinedc`，不写 `dc` 与 `delay`；PWL 从 t = 0 起、覆盖 stop。保存网格由 strobe 固定，precision 不写进用例网表。
  - 网格相位：`clk` 上升穿越在 1.64 + 5.3k ns，`reset` 上升穿越在 57.07 ns，都是 10 ps 的整数倍。每次改变报告的事件 e 之前，e−330 ps 一行在提前检出窗内，离两端各 10 ps，不靠浮点舍入；迟到方向 e+330 到 e+410 ps 共 9 行。
  - e−330 ps 处，提前 340 ps 的报告已走过 1/8 的过渡：`valid` 在八次报告改变上都差 112.5 mV；`rms_out` 在五次改变 `rms_out` 的事件上差 23.0、23.6、46.6、47.0、30.9 mV（台阶 184、189、373、376、247 mV）。两个输出各自都超过 2 mV。
  - 合法域：时钟周期 5.3 ns；两路输入在 0.12–0.72 V 与 0.27–0.67 V，振幅 0.30、0.20 V，频率 25、16 MHz；控制门限穿越离采样沿至少 1.43 ns；事件最短间隔 1.64 ns，没有不长于或恰为 640 ps 的区间；`reset` 在 57.07 ns 清除一个刚完成、`valid` 仍为高的窗口，清零也有可见变化；`enable` 低电平跨越部分窗口。
- 合成控制（未仿真；全部行与只用网格行各一遍）：新用例上提前 −340 ps 与迟到 +340 ps 都被拒，窗内 ±200 ps 与参考都通过；提前 −320 ps 作为边界诊断通过。旧三例上提前 −340 ps 仍都通过，“未覆盖”的说明保留。
- 旧版 EVAS 0.8.7：新用例上参考解与 `inwindow_report_delay_200ps` 通过，`late_report_delay_340ps` 被拒，只用网格行复判判决不变，与 `expected.json` 一致。引用这些通过之前核对了零点处理：参考解只在 `clk`、`reset` 的上升穿越上读输入，控制信号停在 0 或 0.9 V，不在门限上停留或折返，旧版的通过不受这一处理掩盖。
- 平局（TIE-RULE 现行版 `a4cf0e73…`，含第 4 种情形）：`clk` 与 `reset` 两个来源的事件最近相隔 2.43 ns；参考与全部候选、合成控制的斜坡终点离其他事件至少 2 ns，没有被改写目标的斜坡；参考解没有 timer。无第 (ii) 类平局。
- Spectre 待办：新用例的参考与候选校准；核对 Spectre 在 10 ps strobe 网格上的保存点。
