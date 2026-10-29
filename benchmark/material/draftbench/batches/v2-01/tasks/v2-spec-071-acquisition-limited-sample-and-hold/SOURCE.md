# 来源与迁移记录

2026-10-28 第二批用户决定后迁移（decisions-r1）。改动：Harbor 包装、英文合同、`contract-stretched-input` 的 sample 延迟（用户批准）、`tests/calibration/` 三件和本页；那一轮没有改 checker、`contract-base` 用例、公开台架和参考解。同日 fix-dec-r1 按审核修正参考解、新增私有用例 `contract-midrun-reset` 并更新校准三件，checker 仍未改，见文末“fix-dec-r1 修正”一节。**未仿真**：没有运行 Spectre，也没有运行模型；EVAS 02dee32b 与旧版 EVAS 0.8.7 的结果只是开发证据，待 Spectre 复跑，记录在本地运行目录 `runs/t3-batch2-20261027/decisions-r1/v2-spec-071-acquisition-limited-sample-and-hold/checks.json`（不入库）。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md)，blob `f478d2b002db08d5efc0297ccab622d3dd7bbd92`，提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/SOURCE.md)，blob `f618c9a5476c572570a6be419e56cc2c3740a53a`。

来源为仓库保存的 v4 071-acquisition-limited-sample-and-hold（[v4 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/071-acquisition-limited-sample-and-hold/public/instruction.md)，规划来源 src-47bebeb94396）。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)。decisions-r1 迁移时的参考解与 v4 solution、v1 `vbr1_l1_acquisition_limited_sample_and_hold` 的 dut 形式 gold、bugfix 形式 `dut_fixed.va` 逐字节相同（sha256 `4482266e8bef4f54761e3b0e547efe28e37460aea448eba731d208f9eba9fa30`）。fix-dec-r1 删去 sample 上升沿上的 `held = vinit` 之后，参考解（sha256 `3f648b6fdbf55b6cee7bdef224311a278d1ea3094eb4726da1c8cd57b7f3b910`）不再与这些历史文件同字节；历史字节保留为校准负例 `prefix_reference_sample_edge_reset`。`contract-base` 激励与 v1 bugfix 台架 [tb_acquisition_limited_sample_hold.scs](../../../../../historyref/v1/tasks/CT03_sampling_and_analog_memory/vbr1_l1_acquisition_limited_sample_and_hold/forms/bugfix/gold/tb_acquisition_limited_sample_hold.scs) 的三个源相同，只是 stop 由 90 ns 缩为 70 ns、步长改为 2 ps。

已保留的合同：模块 `acquisition_limited_sample_hold(sample, rst, vin, vout, metric)`，参数 `vth`、`vinit`、`alpha`、`tick`、`tr` 及默认值；全局 `k*tick` 离散更新，初态不跟踪；sample 上升开窗、下降关窗；reset 在 tick 读取并回到 `vinit`；每个 rst 高区间至少 `2*tick`；`metric` 高电平 0.9 V；电压误差 2 mV；时间分辨率不超过最短过渡的四分之一；初态与边沿明确，控制不停在门限，独立控制边沿至少相隔 `2*tr`。

同源关系：首批 30 题中 v2-spec-024（理想边沿采样）机制不同。R01 的 r01-spec-acquisition 功能相关，但改为连续跟踪、输入相关时间常数和有限时间复位，不是本题迁移，责任不同。规划池 C055-S1 的主来源就是 v4:071，同为规格题，复用 alpha=0.42、tick=1 ns 机制与跟踪/保持接口，按用户决定并入本题、不另建。C055-R1（v1 bugfix 来源 src-9276ce9b6eb2）的独立性检查见本地设计说明 `runs/t3-batch2-20261027/decisions-r1/c055-r1/design-note.md`（不入库）：设计说明的结论是不单独建题，用户 2026-10-29 答复决定单第 3 项，定不建；v1 坏版留作本题校准负例 `v1_bugfix_buggy`。

## 建模选择

Harbor 包装把交付改为 `/app/circuit.va`，把 `environment/public` 放到 `/app/testbench`，`visible_test.scs` 的 include 由 `/work/dut.va` 改为 `/app/circuit.va`。公开用例取私有 `tests/cases.json` 的第一个用例 `contract-base`，即公开台架的同一激励。starter 只留端口，方向按原题面的端口说明：`sample`、`rst`、`vin` 为输入，`vout`、`metric` 为输出；参数默认值写在题面。

用户已确认（2026-10-28）。总协调约 02:40Z 转达用户答复“全部按推荐”。推荐原文（`runs/t3-batch2-20261027/triage-disposition.json` 的 wait_for_user）：“shift that case's sample delay off the tick grid (+0.25 ns, crossing 80.25 ns); contract and checker unchanged”；“C055-S1 (same source v4:071, same S) is not built separately; its planned contract strengthening becomes later work on this task”。主控 brief 的落实要求：“把该用例 Vsample 的 delay 加 0.25 ns，交点移到 80.25 ns；合同与 checker 不变”；“它计划补的合同内容（每次获取的更新式、首个 tick、sample/rst/tick 同刻规则、删除实现骨架）中，checker 已经确定的，在英文合同里照 checker 写明；需要改 checker 的，记为后续待办”；疑点 2“照实写进 SOURCE，交主控，不加触发它的用例”。

落实的改动：

- `tests/cases.json` 的 `contract-stretched-input`：`Vsample` 的 `delay=6.15n` 改为 `delay=6.4n`，其余字节不变。sample 上升交点由 6.2、30.8、55.4、80.0 ns 移到 6.45、31.05、55.65、80.25 ns，下降交点由 12.45、37.05、61.65 ns 移到 12.7、37.3、61.9 ns，rst 交点仍在 2.5215 ns。所有交点都不在 1 ns 网格上，距最近 tick 至少 50 ps（31.05 ns）。`contract-base` 与公开台架的交点也至少相距 50 ps，所以公开台架不用改。
- 开窗次数不变（4 次），第二个窗口内的 tick 由 31–37 ns 的 7 个变为 32–37 ns 的 6 个，第四个窗口不再在 80 ns 立即更新。
- C055-S1 计划补的四项，都是 checker 已经确定的，照 checker 写进英文合同：每次获取 `v + alpha*(V(vin) - v)`，`vin` 取 tick 时刻值（`tests/v2_spec.py:76`）；首个 tick 在 t = 0，网格为全局 `k*tick`（`:48-50`）；sample 交点与 tick 同刻时先处理交点（事件按时刻与名称排序，`:51`），rst 取该时刻之后的电平（1e-16 s 前瞻，`:68`）；没有实现骨架，starter 只有接口。原题面“未规定的同刻事件不评分”与 checker 实际对同刻点评分相矛盾，这句改为同刻规则，并写明用例中交点距 tick 至少 50 ps。

F01（评分起点）按用户 2026-10-28 的决定写明：checker 实际的观察起点，checker 不动。新句子：“Each output reaches its new value within `tr` after the instant that changes it. Every saved point is scored, for both outputs, except points less than `1.15*tr` after t = 0 or after an instant that changes the expected value of either output: a tick that updates or resets the held value, or a `sample` crossing that opens or closes the window.” 位置 `tests/v2_spec.py:188`（`t<start+tr*1.15` 跳过），期望值来自 `:151`、`:183` 的事件历史，2 mV 判据在 `:205-208`。校准三件加了迟到负例 `late_transition_1p3tr` 与窗内对照 `inwindow_transition_1p1tr`（`tr` 与 `1.15*tr` 之间到达，这是用户已接受的余量）；两例步长 2 ps，评分起点与 `1.3*tr` 之间至少有 14 个保存行。

题面的“Helper modules may be defined in the same file”是单文件交付的说明，不是新行为。题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。

## 待定项

`grading` 和 `runtime` 待定。历史作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，绑定旧 `/work` 题包与旧 stretched 激励，不认证本次 `/app` 包。模型试做没有做。

疑点 2（decisions-r1 记录；已由 fix-dec-r1 按主控决定处理，见文末）：参考解在 `rst` 为高时遇到 sample 上升沿，立即把保持值置为 `vinit`；合同与 checker 只在 tick 读取 reset，期望值要到下一个 tick 才回到 `vinit`。两者只在这种情形下不同：`rst` 在两个 tick 之间升高、保持值不等于 `vinit`、sample 在下一个 tick 之前上升，偏差最长不到一个 tick。合成控制中，在 20.5 ns 拉高 rst、20.9 ns sample 上升的场景，按参考解行为构造的波形被 checker 拒绝（20.905 ns，`vout` 期望 0.5435 V、实际 0.5411 V）。两个用例的 `rst` 只在 t = 0 起为高，运行中不再拉高，所以这一分歧和“rst 只在 tick 生效”（异步复位的错误模型）都没有用例区分。按用户决定本轮不加用例。可选做法：改参考解，使 sample 沿只决定是否开窗；或者加运行中复位的私有用例并决定该时刻的规则。

后续待办（C055-S1 的计划补强中需要改用例或 checker 的部分）：运行中复位的用例（见疑点 2）；窗口只含一到两个 tick 的短窗用例（规划写“按跟踪窗长度校准误差”，decisions-r1 时两例窗长 5 与 6 个 tick）。checker 本身不需要改。fix-dec-r1 新增的 `contract-midrun-reset` 已含两段运行中复位，以及只含 2 个和 1 个 tick 的两个窗口，这两项都已覆盖。

同刻次序：旧版 EVAS 0.8.7 对同一时刻的 cross 与 timer 不按源码次序处理。在 c485de86 的 80 ns 同刻激励上，tick 块写在 cross 块之前的合法实现（`alt_timer_before_cross`）与参考解得到同一波形、都通过，旧版因此不能复现分诊所说的“少一次更新”。按 LRM，同一时刻的事件按源码次序执行；对旧版参考解波形去掉 80 ns 那次更新后重放，checker 拒绝（80.23 ns 起偏差约 0.19 V）。改后的激励不再有同刻点，这一差异不影响判定。Spectre 待办：记录同一时刻的 `cross` 与 `timer` 的执行次序，以及 `transition()` 的待发过渡行为。同一输出的两次变化至少相隔 1 ns（`vout` 只在 tick 变化，`metric` 只在 sample 交点或复位 tick 变化），大于 `tr`，用例中没有被打断的过渡。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解私有 2 例、公开 1 例和公开台架都在 stage c 报 `kernel.step_budget`（#270 探针 NF-01），最后提交步约 4.25 ns，在改动的 sample 沿之前，与分诊一致。旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 通过（分诊时 2/2，不变），只用网格行复判没有变化；6 个校准候选在两例的判决都与 `tests/calibration/expected.json` 一致。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

## fix-dec-r1 修正（2026-10-28）

依据：Astra 独立审核 `runs/t3-batch2-20261027/review-dec-r1/astra-review.json`（sha256 `22c74f3e…7154`，不入库）的 AR01（P2/Spec）、AR10（P2/Standards）与交接项 D071-1；主控决定见修正 brief `runs/t3-batch2-20261027/briefs/fix-dec-r1.md` 第 1、2 项。记录在本地运行目录 `runs/t3-batch2-20261027/fix-dec-r1/`（不入库）。**未仿真**：没有运行 Spectre 或模型。

- 参考解（AR01、D071-1，主控决定）：`rst` 为高时的 sample 上升沿原来立即把保持值置为 `vinit`，合同与 checker 只在 tick 复位（题面“The held value changes only at ticks”“`rst` acts only at ticks”；`tests/v2_spec.py:73-76`），两者在 `rst` 于两 tick 之间升高、保持值不等于 `vinit`、sample 在下一 tick 前上升时不同。按合同删去 sample 上升事件里的 `held = vinit`，该事件只决定窗口是否打开，复位留给 tick。`solution/circuit.va` 与 `solution/dut.va` 同改，sha256 `4482266e…fa30` → `3f648b6f…b910`，两份仍逐字节相同。题面与 checker 不改。
- 新增私有用例 `contract-midrun-reset`（41 ns，步长 2 ps，参数取默认）：
  - 13.5 ns 拉高 `rst` 时窗口开着、保持值约 0.797 V；14 ns 的 tick 复位并关窗；16.5 ns 释放时 sample 仍高，窗口不应重开。
  - 第二个窗口把保持值带到约 0.216 V 后，27.3 ns 拉高 `rst`；27.75 ns 的 sample 上升交点在 28 ns 复位 tick 之前，此时 `rst` 为高，窗口不开、保持值不变；29.6 ns 释放时 sample 仍高。
  - 之后两个窗口分别只含 2 个和 1 个 tick，确认下一次 sample 上升才恢复获取。
  - 三个 `rst` 高区间为 2.5、3.0、2.3 ns（≥ `2*tick`）。按精确有理数核对：sample 与 `rst` 交点距最近 tick 至少 250 ps，不同控制的交点相距至少 450 ps；输出过渡终点与任何输入交点都不同刻；输入没有触到或停在门限上。
  - 能区分的评分点（作者模型在本用例激励上、由原 checker 判定；旧版 EVAS 的首个失败时刻与之相差不到 2 ps）：异步复位 13.5 ns 起被拒；sample 沿提前复位（改前参考解）27.75 ns 起被拒；释放后错误重开窗 16.5 ns 起被拒；复位不关窗 14.23 ns 起被拒。前两例没有运行中复位，这四种错误在前两例都通过。
- 校准三件随参考解更新：`v1_bugfix_buggy` 仍与原始坏版逐字节相同（sha256 `082b0724…f918`，生成器断言）；新增 `prefix_reference_sample_edge_reset`（= 改前参考解字节）、`async_reset_on_rst_edge`、`reopen_on_rst_release`、`reset_keeps_window`，矩阵见 `tests/calibration/`。F01 的迟到负例与窗内对照在新用例上也有评分行（步长 2 ps，`1.15*tr` 与 `1.3*tr` 之间至少 14 行），旧版判决分别为拒绝和通过。
- 作者合成控制（AR10，Standards）：decisions-r1 的 071 合成场景（`decisions-r1/scripts/synthetic_dec.py:176`）把开头 `rst` 高区间做成 1.5 ns，不满足每段至少 `2*tick` 的输入合同，却标为 pass-contract。fix-dec-r1 的重跑把这段延长到 2.5 ns，属于输入域修正，原记录 `decisions-r1/synthetic-controls.json`（sha256 `bc06c757…8578`）保留不改；10 项控制的判决与原记录相同。
- 历史 gold 的记忆污染：v4 solution、v1 dut 形式 gold 和 `dut_fixed.va` 都带这条 sample 沿复位，与 `prefix_reference_sample_edge_reset` 同字节，所以照抄公开历史 gold 的提交会在 `contract-midrun-reset` 上被拒。C055-R1 设计说明（`runs/t3-batch2-20261027/decisions-r1/c055-r1/design-note.md` 第 21 行）把 `dut_fixed.va` 写成与 071 参考解逐字节相同，那是 decisions-r1 时点的事实，需由主控补时间限定，本轮不改 decisions-r1 的记录。
- 台架源参数（2026-10-28 新增台架规则：本单新建或修改的台架行，源参数一律显式写出）：新用例的三个 PWL 源只写 `type` 与 `wave`，未满足，交主控裁决。依赖的 Spectre 缺省（Spectre 21.1.0.509.isr12 `spectre -h vsource` 帮助，本地存档 `runs/evas-pulse-delay-20261017/pulse-help-collected/`，vaEVAS 主工作区，不入库，`vsource-help.log` sha256 `081a82af…93ac`）与同日其他题记录的相同：`dc`、通用波形参数 `delay`=0 与 `edgetype`=linear、PWL 的 `offset`=0、`scale`=1、`stretch`=1，以及点数 ≥ 20 时 `allbrkpts`=no（本例 sample 源 22 点）。EVAS 02dee32b 的 PWL 源只接受 `type` 与 `wave`（`evas/src/evas/scs_sources.py:22-30`），显式写出会在 stage a 被拒，同日 v3-converter-adc-spectrum 等题已有探针记录。
- 开发证据：旧版 EVAS 0.8.7 上参考解私有 3/3、公开 1/1 通过，10 个校准候选在三例 30/30 与矩阵一致，只用网格行复判没有变化（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）。EVAS 02dee32b 上参考解三个私有例、公开例和公开台架都在 stage c 报 `kernel.step_budget`（NF-01），最后提交步在 4.25–4.44 ns，早于新用例的第一次运行中复位；起始模型在 stage a 报只有接口、没有 analog 块，属预期。
- Spectre 待办不变：记录同一时刻的 `cross` 与 `timer` 的执行次序，以及 `transition()` 的待发过渡行为；新用例中同一输出的两次变化至少相隔 1 ns，没有被打断的过渡。

## author-r2 记录（2026-10-29）

依据：决定单第 3 项，用户 2026-10-29 定 C055-R1 不建；主控 brief `runs/t3-batch2-20261027/briefs/b2-author-r2.md` 第 7 项。记录在本地运行目录 `runs/t3-batch2-20261027/author-r2/`（不入库）。**未仿真**：本轮没有运行 Spectre、EVAS 或模型。

- 只改本页：上文“同源关系”一段把设计说明的“不建”结论改为用户 2026-10-29 已定不建。题面、用例、checker、参考解与校准件都不改。
- W2-25 rec-03 为 C055-R1 的 v1 坏版本打包了一个作业（`W225--C055-R1--buggy`，`runs/t3-spectre-wave2-20261029/w225/disposition-rec03.md`），用的是 v1 原台架与 v1 的 checker；它的结果只作记录，不当建题依据，也不代替本题校准负例 `v1_bugfix_buggy` 的判定。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`sample`、`rst`，门限 `vth`（缺省 0.45 V，用例不覆盖）。`vin` 是模拟输入，只在 tick 上被读，不在此列。
- 激励核对（未仿真）：题包全部 6 份网表（`tests/cases.json` 3 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 sample，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`sample` and `rst` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
