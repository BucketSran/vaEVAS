# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 047-window-comparator-detector。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 047。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-047-window-comparator-detector/instruction.md)（blob `d69209f82e23786604b2854c2c6e363560035446`），原来源页为 [HEAD c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-047-window-comparator-detector/SOURCE.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。原题面另写“实际校准pending”，两种记录并存，本次不删。EVAS 行为不是本题验收真值。

同源关系：首批 v2-spec-314 迟滞窗比较器（v4-314）与本题功能相近；原题面写明本题考察确定轮询语义，314 考察异步迟滞历史，责任不同。R01 两题无同源；规划池 C182 为“保留组件或变体”，没有候选。

## Modeling choices

原题面是单段中文合同，现行 Spec 逐句译出：端口 electrical，参数 `vlow=.3V`、`vhigh=.6V`、`tedge=200ps`、`tick=500ps`，VDD 与 VSS 固定且 VDD>VSS，初态由 vin 相对 VSS 决定，全局 `k*tick` 轮询，严格位于 `(vlow,vhigh)` 时输出 VDD，否则 VSS，tedge 平滑，两次 tick 之间保持，覆盖非零 VSS、精确边界值与短于 tick 的窗口，2 mV 误差，未定义同刻事件不检查。没有改数。原句“此题考察确定轮询语义，314考察异步迟滞历史”是题目设计说明，移到本页，不写进求解者题面。

原题面没有逐端口的 input/output 词。starter 按角色声明：`VDD`、`VSS` 为 inout 供电端（同首批 003 的写法），`vin` 为输入，`out` 为输出。

Harbor 包装把单文件交付改为 `/app/circuit.va`，把 `environment/public` 放到 `/app/testbench`，`visible_test.scs` 的 include 由 `/work/dut.va` 改为 `/app/circuit.va`。公开用例取原私有 `tests/cases.json` 的第一个用例 `contract-base`。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “Voltage error is at most 2 mV. Final evaluation covers different stimuli inside this public contract.” 改为 “Voltage error is at most 2 mV. `out` reaches its new level within `tedge` after the tick that changes its target. Every saved point is scored, except points less than `1.15*tedge` after t = 0 or after a tick `k*tick` at which the polled decision changes the target of `out`. A crossing of a window edge between ticks starts no unscored interval. Final evaluation covers different stimuli inside this public contract.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `1.15*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）。本题只有 tick 事件改变目标：`:48-50` 每 `tick` 加一个事件，`:78` 在 tick 上按 `V(vin, VSS)` 判窗；`:46-47` 的 `vin` 穿越 `vlow`/`vhigh` 也进事件表，但不改变目标，所以不起不评分区；`tr` 取 `tedge` 的默认 200 ps（`:11`，用例不给参数）。
  - 余量：到达期限仍是 `tedge`；在 `tedge` 与 `1.15*tedge` 之间到达的不区分，这是用户已接受的余量。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡时间。应被拒：`late_transition_1p3tedge`；应通过（窗内对照）：`inwindow_transition_1p1tedge`。
  - 合成控制（未仿真）：底波形为 fix-a-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中推迟输出列后直接调用本题 checker。`late-shift-60ps` 5 个私有用例都被拒；`inwindow-shift-20ps` 5 个私有用例都通过；未平移的底波形 5/5 通过。共 15/15 符合预期。
  - 旧版 EVAS 0.8.7：`late_transition_1p3tedge` 5 个私有用例都被拒；`inwindow_transition_1p1tedge` 5 个私有用例都通过。有预期的 10 例中 10 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/contract-base、public/contract-base）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。**未仿真**：没有运行 Spectre。EVAS 02dee32b 与旧版 EVAS 0.8.7 的阶段结果只是开发证据（待 Spectre 复跑），记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-spec-047-window-comparator-detector/checks.json`（不入库）。阶段结果：EVAS 02dee32b 在 stage c 报 `kernel.step_budget`（#270 探针 NF-01），约 0.57 ns 处，私有 2 个用例与公开台架相同；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

私有 checker 在目标变化后跳过 `1.15*tedge` 再逐点检查 2 mV。迁移时（2026-10-27）原题面只写“每次目标变化用 tedge 平滑”与 2 mV，没有写跳过窗长度，当时不加入题面。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 tick 后的 `1.15*tedge` 评分起点，到达期限仍是 `tedge`。

迁移时终评两例 VSS 都为 0，tick 上没有恰在 0.3/0.6 V 的样本，窗口内持续时间都长于一个 tick，题面所述覆盖范围不成立。2026-10-28 修正（fix-a-r1，F06）新增三个私有用例：`nonzero-vss`（VSS=0.2 V、VDD=1.0 V，含忽略 VSS 就会判反的输入与初态）、`exact-boundary-samples`（VSS=0，vin 在多个 tick 上处于恰为 0.3 或 0.6 V 的平坦段，含初态）、`sub-tick-windows`（两个 tick 之间整段穿窗两次、只含一个 tick 的短窗、两个 tick 之间短暂出窗）。公开用例与 checker 未改。旧版 EVAS 0.8.7 上参考解私有 5/5、公开 1/1 通过，只用网格行复判无变化；忽略 VSS、端点算作窗口内、两次 tick 之间的短暂入窗也在下个 tick 判入窗三种错误模型在原两例都通过，分别被 `nonzero-vss`、`exact-boundary-samples`、`sub-tick-windows` 拒绝；异步窗口比较（不轮询）的错误模型在原两例与三个新用例都被拒。精确边界依赖仿真器在 PWL 平坦段与 0 V 电源上给出逐位精确的 0.3/0.6 V；旧版 EVAS 如此，Spectre 待复跑确认。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。

## 2026-10-29 触碰门限豁免（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。样板同节的豁免：合同有意让输入恰停在门限上、题面写明等于门限时算哪一边的，三条同时满足就不套用。本题题面写明 `V(vin, VSS)` 严格位于 `(vlow, vhigh)` 内才输出 `VDD`，覆盖范围含 “exact boundary values”，等于门限算窗外。总协调 2026-10-29 定（标准线确认）：三条都满足，照现状，不套用 A 收窄版。本轮题面不加句子。
- 三条逐条核对：主控记录 a-narrowed-exempt/README.md（`runs/t3-spectre-wave2-20261029/scan/a-narrowed-exempt/README.md`）（sha256 `769afc9eb766f85e0d84c33431e0c8da47b16fa6cc7008eb9d5b672beb8e160b`），脚本 check_exempt.py（`runs/t3-spectre-wave2-20261029/scan/a-narrowed-exempt/check_exempt.py`）（`bad68c26…`）→ exempt-check.json（`runs/t3-spectre-wave2-20261029/scan/a-narrowed-exempt/exempt-check.json`）（sha256 `f227d36cc3e684748f0867d09d25725b3ef658776882d9e96b49735c2eb02da1`）；本轮在现包上复核，结论相同。
  1. 平台是平的 PWL 段，写成与门限相同的十进制数：满足。只有私有用例 `exact-boundary-samples` 有门限平台，共 4 段：0–0.7 ns 与 3.8–4.7 ns 写 `0.3`，1.8–2.7 ns 与 4.8–5.7 ns 写 `0.6`，逐段与门限的十进制写法相同，与参考解参数缺省 `vlow=0.3`、`vhigh=0.6` 和 checker 的 `.3`、`.6` 同值；`VSS` 写 dc `0`。没有经非零参考节点才等于门限的平台（`nonzero-vss` 的各平台与 `VSS` 之差离门限至少 10 mV）。
  2. 题面以数值给出门限，参考解与 DUT 都把这个数直接写成参数：满足。题面写 `vlow` = 0.3 V、`vhigh` = 0.6 V，并要求声明为可覆盖参数；参考解 `parameter real vlow=0.3,vhigh=0.6`；校准候选只改输出过渡时间。
  3. 轮询时刻落在平台内部，不在拐角上：满足。平台内 7 次轮询（0.5、2.0、2.5、4.0、4.5、5.0、5.5 ns），离拐角最近 0.2 ns；t = 0 的判定落在 PWL 第一个折点上（1 次），按标准线 2026-10-29 的确认不算拐角。B2PC must-01（2026-10-29T00:32Z 正式核收）两份参考解作业在这 8 次轮询前后的 `vin` 行都逐位等于门限。
- 本轮复核（未仿真）：touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`）在现包全部 8 份网表（`tests/cases.json` 5 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）上按有理数精确求值 `V(vin, VSS)` 对 `vlow`、`vhigh`：停在门限上 4 处，都是上述平台（`tests/cases.json#exact-boundary-samples`）；t = 0 恰在门限上 1 处，是同一用例的起点；触碰后返回 0 处；stop 时恰在门限上 0 处（touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`），`a9c256da…`）。主控记录只查了两份 `cases.json`，本轮补查了两份 `visible_test.scs`（都与 `contract-base` 相同，没有门限平台）。
- 不改：题面、checker、用例、网表、参考解、校准三件、`task.toml` 都逐字节不变，只改本页。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
