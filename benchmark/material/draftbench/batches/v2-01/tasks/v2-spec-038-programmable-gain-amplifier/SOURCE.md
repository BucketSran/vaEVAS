# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 038-programmable-gain-amplifier。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 038。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-038-programmable-gain-amplifier/instruction.md)（blob `e365849dcfa943b067af8cd64bb601b7b9eb4bc5`），原来源页为 [HEAD c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-038-programmable-gain-amplifier/SOURCE.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。模型 Agentic 与 one-shot 试做在该历史记录中为 pending。EVAS 行为不是本题验收真值。

同源关系：首批 30 题中 v2-test-gain-settling（`case-0018+v4-038+v4-370`）与第二批 v2-test-online-gain（`v4-093+v4-038`）共用 v4-038 放大器来源，二者都是测量题；本题是按规格建模，动作不同，各自保留身份，不重复计数。R01 两题无同源；规划池 C211 为“保留组件或变体”，没有候选。

## Modeling choices

原题面参数表写 `tr` 用于 `out` 和 `metric`，同一题面“本轮冻结的数值合同”写 out 为连续模拟目标、不使用 tr 滤波，tr 只用于 clipping metric。checker（038 分支对 out 不设跳过窗）与参考解（`V(out) <+ bounded` 不经 transition）都按冻结段。现行 Spec 按冻结段写参数说明，没有改数。

冻结段“复位只在 clk 上升时重置储存 gain 为 1”与“rst 高期间 out=vcm”写入 Spec。端口方向按原题面的角色句写入 starter：`clk`、`rst`、`gain_sel`、`vin` 为输入，`out`、`metric` 为输出。

Harbor 包装把单文件交付改为 `/app/circuit.va`，把 `environment/public` 放到 `/app/testbench`，其中 `visible_test.scs` 的 include 由 `/work/dut.va` 改为 `/app/circuit.va`。公开用例取原私有 `tests/cases.json` 的第一个用例 `contract-base`，其余用例只在终评使用。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “`out` is checked at every point. After a `tr` transition of `metric` finishes, every point in the following hold interval is checked.” 改为 “`out` is scored at every saved point, from t = 0. `metric` reaches its new level within `tr` after its target changes. That target changes where the unclamped target `vcm + gain * (V(vin) - vcm)`, with `V(vin)` interpolated linearly between saved points, crosses `vmin` or `vmax` while `rst` is low, and at each `rst` crossing or rising `clk` crossing that changes it. `metric` is scored at every saved point except points less than `1.15*tr` after a change of its target, including t = 0 when its initial target is high. At those unscored points `metric` must still stay within 2 mV of the range from 0 V to 0.9 V.”
  - 对应 checker：本题不适用 `tests/v2_spec.py:188`（`sid!='038'`）：`out` 从 t = 0 起每个保存点都评分（`:196` 期望值，`:205-208` 判据）；`metric` 的目标改变时刻由 `:154-181` 算出（`rst` 低时未钳位目标在保存点间线性插值后穿越 `vmin`/`vmax` 的时刻 `:174-180`，`rst` 穿越与 `clk` 上升穿越中改变它的 `:168-173`，初始目标为高时的 t = 0 `:167`），其后 `1.15*tr` 内不评分 `metric`（`:197-201`），那段时间里 `metric` 越出 −2 mV 至 0.902 V 记 `metric_overshoot`（`:202-203`）；`tr` 取默认 200 ps（`:11`，用例不给参数）。
  - 余量：`metric` 的到达期限仍是 `tr`；在 `tr` 与 `1.15*tr` 之间到达的不区分，这是用户已接受的余量。`out` 没有不评分区。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡时间。应被拒：`late_metric_transition_1p3tr`；应通过（窗内对照）：`inwindow_metric_transition_1p1tr`。
  - 合成控制（未仿真）：底波形为 fix-a-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中推迟 `metric` 列后直接调用本题 checker。`late-shift-60ps` 2 个私有用例都被拒；`inwindow-shift-20ps` 2 个私有用例都通过；未平移的底波形 2/2 通过。共 6/6 符合预期。
  - 旧版 EVAS 0.8.7：`late_metric_transition_1p3tr` 2 个私有用例都被拒；`inwindow_metric_transition_1p1tr` 2 个私有用例都通过。有预期的 4 例中 4 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/contract-base、public/contract-base）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。**未仿真**：没有运行 Spectre。EVAS 02dee32b 与旧版 EVAS 0.8.7 的阶段结果只是开发证据（待 Spectre 复跑），记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-spec-038-programmable-gain-amplifier/checks.json`（不入库）。阶段结果：EVAS 02dee32b 在 stage b 拒绝参考解 `dut.va:39:9` 的普通 if（含非线性乘积，与 #270 探针 NF-22 同类），私有 2 个用例与公开台架相同；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

迁移时 contract-base 首个 clk 上升（约 2.04 ns）与 rst 下降（约 2.25 ns）相距约 210 ps，contract-stretched-input 相应为约 267.5 ps，都小于合同“独立控制边沿至少 2*tr=400 ps”。2026-10-28 修正（fix-a-r1，F05）把 rst 释放移到约 2.65 ns 与约 3.2595 ns（stretched 仍按 1.23 倍同比），间距变为 610 ps 与 759.5 ps，首个 clk 上升仍在 rst 高期间；公开 `cases.json` 与两份 `visible_test.scs` 同步。checker 与参考解未改。

私有 checker 对 `metric` 在目标变化后跳过 `1.15*tr`，并检查该窗内不越出 0..0.9 V。迁移时（2026-10-27）公开合同是 `tr` 结束后检查保持区间，当时不采用 1.15。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 `metric` 的 `1.15*tr` 评分起点、目标改变的时刻与窗内范围，`out` 从 t = 0 起逐点评分。

fix-a-r1 复跑（2026-10-28，记录在本地 `runs/t3-batch2-20261027/fix-a-r1/`，不入库）：改后两例与公开用例上，旧版 EVAS 0.8.7 参考解私有 2/2、公开 1/1 通过，只用网格行复判无变化；rst 高时仍采样 `gain_sel` 的错误模型在改后两例与公开用例都被拒，说明首拍复位仍受测。1.15 窗口属待用户决定的 F01，本轮未动。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`clk`、`rst`、`gain_sel`，门限 `vth`（缺省 0.45 V，用例不覆盖）。`vin` 是模拟输入；削波判定比的是被测模块内部算出的未削波目标 `vcm + gain * (V(vin) - vcm)`，题面写明“超过”才置高（等于不算），不在此列。
- 激励核对（未仿真）：题包全部 5 份网表（`tests/cases.json` 2 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 clk，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。另作参考（不在本条范围内）：`vin` 对三种增益（1、0.8、2.4）下的等效削波电平 `vcm + (vmin - vcm)/g`、`vcm + (vmax - vcm)/g`，停留、触碰、t = 0 或 stop 恰在电平上共 0 处，局部极值最近 0.06 V，平段最近 0.0575 V。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`clk`, `rst`, and `gain_sel` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
