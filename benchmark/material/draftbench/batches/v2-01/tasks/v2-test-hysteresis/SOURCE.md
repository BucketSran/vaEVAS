# 来源与迁移记录

2026-10-27 第二批 B 组迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。评分数值代码、公开与私有用例、参考解行为和固定比较器都没有改。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration-b/v2-test-hysteresis/checks.json`（不入库）。迁移后的审核修正（2026-10-28，fix-b-r1）见“待定项”末段。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-hysteresis/instruction.md)，blob `bf213e99fd2f1012fbc6a4aac9d5a3dfdcd23e41`，提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-hysteresis/SOURCE.md)，blob `9b6fac50f84c0f3df778e1e57e0e7139a585239e`。

来源 `v4-111`。本题保留来源工程目标，并保留后来加上的固定只读 DUT、独立实际波形 checker 和窗口协议。原始参考资产仍在 `benchmark/material/historyref/`。固定 DUT 现为 `/app/testbench/dut/support_cmp.va`，模块 `support_hysteretic_comparator`，与原 `environment/public/dut/support_cmp.va` 及各用例内联支持文件逐字节相同。公开用例现为 `/app/testbench/cases.json`（原 `environment/public/cases.json` 原字节）。候选壳现为 `/app/circuit.va`，只留端口与原 starter 的 input/output 角色；参数默认值改写在题面。

已保留：模块 `hysteresis_meter(vin,cmp_out,begin_round,up,down,width,valid)`；输入为只读观测，输出以伏报告输入捕获值，逻辑高低 1 V 与 0 V；`tr=20 ps` 为输出边沿参数；cmp_out 穿过 0.5 V 上升/下降时分别把实际 vin 捕获到 up/down；同一轮两方向都捕获后 `width=up-down`、`valid=1`；begin_round 穿过 0.5 V 上升清零全部报告与方向历史；新轮缺任一方向保持 `valid=0`；没有 begin 事件时初始轮从 t=0 开始；每方向后续边沿刷新对应值；比较器延迟包含在实际捕获点中，不能按 DUT 参数报告理想门限；事件后 100 ps 内可过渡，之后绝对误差不超过 2 mV。公开与终评范围：vin 0.35..0.65 V；比较器 offset -0.02..0.02 V，vhys 0.04..0.13 V，td 100..500 ps；可改变输入斜坡、轮起点及完整/缺方向轮；初态 cmp_out 低，轮起点不与比较器边沿重合。固定比较器源码默认 `offset=0`、`vhys=50m`、`td=120p`、`tr=30p`，题面只点名模块与文件，不复述源码默认值。

同源关系：首批 30 题中 v2-test-offset-search（v4-109）与 v2-test-comparator-delay（v4-170）来源和测量量不同；R01 两题无同源。规划池 U07-T1 同为 v4:111 来源、同为测试表征，但其责任是“分离本征迟滞与动态延迟”；本题要求延迟包含在捕获值中，责任不同，不重复计数。

## 建模选择

这是测试表征，不是重建比较器。仪表接口壳只留端口，原 starter 的参数和内部变量不进壳；`tr=20 ps` 由求解者按 Spec 声明。端口方向取自原 starter：`vin`、`cmp_out`、`begin_round` 为输入，`up`、`down`、`width`、`valid` 为输出。满足外部测量行为即可，不得驱动观测输入。DUT 不达标时，正确报告仍然可以通过。

现行题面按已执行失败记 0、原因另记书写。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该历史原义保留在本页，不解释成缺 Spectre 等于语义错误，也不把现行 0 分解释成行为已被检出。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。

- 题面：原题面只有 “Outputs may transition within 100 ps after an event. After that, the absolute error must not exceed 2 mV.”，没有说明 guard 也覆盖事件之前、整段不评分与只评保存行；本次保留该句，在其后加一段：“This 100 ps timing guard applies around these events: every rising crossing of `begin_round` through 0.5 V, and every rising or falling crossing of `cmp_out` through 0.5 V, whether or not the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. In every interval, each output is scored at every saved point more than 100 ps from both ends of the interval, and at no other point, so an interval no longer than 200 ps is not scored.”
  - 对应 checker：`tests/v2_testing.py` 的 `hysteresis()`（`:29-55`）：事件为 `begin_round` 穿越 0.5 V 的每个上升与 `cmp_out` 穿越 0.5 V 的每个上升、下降（`:30-32`，`Wave.edges` 默认门限 0.5 V，`:20`），与 t = 0 的起点一起排成点表（`:38`），报告不变的事件也算；每段只评 `t+guard < 行时刻 < end-guard` 的保存行（`:51`），guard 取用例的 100 ps（`:36`），不评区间中点，也不插值；不长于 `2*guard` 的区间因此没有评分点。本题不经 `pieces()`；除此之外没有别的 guard 用法。
  - 合法输入域加一句：“In every case, public and final, no interval is exactly 200 ps long.”。`end-t<=2*guard` 是浮点比较，名义上恰好 200 ps 的区间相减后可能长出几个 ulp，于是不被跳过，恰在中间的保存行可能被评分，与第二批 online-gain 审核 AR08 同类；checker 不动。核验（未仿真）：对全部私有与公开用例，取网表与支撑文件都和现行用例相同的旧版参考波形，在内存中记录 checker 实际划出的区间。没有区间落在 200 ps ± 1 fs 内。没有不长于 200 ps 的区间；长于 200 ps 的最短区间 1958.636 ps（public/bad-dut-wide，19.051364–21.01 ns）。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改报告延迟。应被拒：`late_report_delay_120ps`；应通过（窗内对照）：`inwindow_report_delay_50ps`。
  - 合成控制（未仿真）：底波形为 fix-b-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中提前或推迟报告列后直接调用本题 checker。`late-report-+120ps` 4 个私有用例都被拒；`inwindow-report-+50ps` 4 个私有用例都通过；`early-report--120ps` 4 个私有用例都被拒；`inwindow-early-report--50ps` 4 个私有用例都通过；未平移的底波形 4/4 通过。共 20/20 符合预期。
  - 旧版 EVAS 0.8.7：`late_report_delay_120ps` 4 个私有用例都被拒；`inwindow_report_delay_50ps` 4 个私有用例都通过。有预期的 8 例中 8 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/terminal-normal、public/normal）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。旧作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。测试表征索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。这些记录不证明当前 Harbor 包。模型试跑尚未完成。固定 Spectre，开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解私有 3 个、公开 3 个用例都在 stage c 报 `kernel.invalid_ir`（unbound real value requires its procedure frame），t=0 前、没有提交步；#270 与 NF 清单未列此消息，未定位在参考解还是固定 `support_cmp.va`；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 3/3、公开 3/3 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；部分 checker 依赖旧版特有输出行，旧版通过不代表 Spectre 或新版 EVAS 通过。这些结果待 Spectre 复跑，不是校准或录取依据。

2026-10-28 审核修正（fix-b-r1）。B04：迁移时三个私有用例每轮每个方向最多一次比较器边沿，“同方向后续边沿刷新”没有终评覆盖；只锁存首次边沿的错误仪表在三例都通过。新增私有用例 `terminal-same-round-refresh`，比较器 offset 0.011 V、vhys 0.07 V、td 400 ps，stop 90 ns。首轮先以 0.01 V/ns 慢上越、0.1 V/ns 快下越，再以 0.1 V/ns 快上越、0.01 V/ns 慢下越。47.01 ns 的 begin_round 开始第二轮，依次以 0.05 V/ns 上越、0.1 V/ns 下越、0.005 V/ns 慢上越。同方向两次捕获的 vin 在首轮相差约 37 mV（上、下各一次），在第二轮相差约 19 mV（上越），都远大于 2 mV。用例在合同范围内：vin 0.40–0.62 V，cmp_out 初态低，begin_round 交点与最近的比较器边沿相隔约 6 ns。公开用例未变。

B06：题面补写初值规则。每轮开始时，包括 t=0 起的初始轮，up、down、width、valid 都是 0 V；本轮尚未捕获的方向报告 0 V；两个方向都捕获前 width 为 0 V。依据是现有 checker 与参考解：checker 的初态与 begin_round 清零后的状态都是 `up=down=width=valid=0`，width 只在两个方向都已捕获时更新；参考解 `initial_step` 与 begin_round 都清零，w 只在 su、sd 都为 1 时更新。数值没有改。

checker 与参考解都未改。验证（**未仿真**，没有运行 Spectre）：旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 4/4、公开 3/3 通过，只用网格行复判无变化。只锁存首次边沿的 VA 错例在原三个私有用例都通过，在新用例被拒：23.98 ns 处 up 应为 0.5875 V，实际 0.5502 V。报告初值为 0.5 V 的错例在全部私有用例被拒。这些是旧版开发证据，待 Spectre 复跑，记录在 `runs/t3-batch2-20261027/fix-b-r1/`（不入库）。

迁移时（2026-10-27）未发现题面数值与固定 checker 冲突：checker 的事件邻域与题面“100 ps 内可过渡”同为 100 ps（用例 `guard=1e-10`），但题面没有写 guard 也覆盖事件之前，也没有写区间规则。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明事件表、事件前后各 100 ps 不评分与只评保存行。
