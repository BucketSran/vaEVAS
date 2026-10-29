# 来源与迁移记录

2026-10-28 第二批用户决定后迁移（decisions-r1）。改动：Harbor 包装、英文合同、`contract-base` 首个 `clk` 上升斜坡及同一激励的公开台架（用户批准）、`tests/calibration/` 三件和本页；那一轮没有改 checker、`contract-stretched-input` 用例和参考解。同日 fix-dec-r1 按审核修正参考解的 `settled` 低电平、移开两例的同刻与近同刻控制沿、新增两个私有用例、在题面写明参数范围并更新校准三件，checker 仍未改，见文末“fix-dec-r1 修正”一节；增量复审 dec r2 的三处修正见其后“dec r2 增量复审修正”一节。**未仿真**：没有运行 Spectre，也没有运行模型；EVAS 02dee32b 与旧版 EVAS 0.8.7 的结果只是开发证据，待 Spectre 复跑，记录在本地运行目录 `runs/t3-batch2-20261027/decisions-r1/v2-spec-370-opamp-feedback-settling-monitor/checks.json`（不入库）。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-370-opamp-feedback-settling-monitor/instruction.md)，blob `084ed5e098e4c207a7864b0ff1665e8afd70c225`，提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-370-opamp-feedback-settling-monitor/SOURCE.md)，blob `6c2d25f8191b670cf68572371361f9d7fb6b7a71`。

来源为仓库保存的 v4 370-opamp-feedback-settling-monitor。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 370。

已保留的合同：模块 `opamp_feedback_settling` 与十个端口的位置次序，八个参数及默认值；每 250 ps 轮询控制；`code=4*gain_2+2*gain_1+gain_0`；`target`、`vout_next`、`error` 三个公式与钳位；`error_metric=vcm+error`；误差小于 `settle_tol` 时计数加一、否则清零，计数到 3 时 `settled=vdd`；复位或禁用时 `vout=vcm`、`error_metric=vcm`、`settled=vss` 并清计数；可以有可选辅助模块；电压误差 2 mV；时间分辨率不超过最短过渡的四分之一；初态与边沿明确，控制不停在门限，独立控制边沿至少相隔 `2*tr`，未规定的同刻事件不评分。

同源关系：首批 30 题中 v2-test-gain-settling（case-0018+v4-038+v4-370，测试表征）用 370 的动态放大器作被测对象，动作不同，不重复。R01 两题无同源。规划池 C236 为“保留组件或变体”，没有候选。

## 建模选择

Harbor 包装把交付改为 `/app/circuit.va`，把 `environment/public` 放到 `/app/testbench`，`visible_test.scs` 的 include 由 `/work/dut.va` 改为 `/app/circuit.va`。公开用例取私有 `tests/cases.json` 的第一个用例 `contract-base`（改后的激励），与公开台架是同一激励。原题面没有逐端口的 input/output 词，starter 按角色声明：`vin`、`clk`、`rst`、`enable` 与三个增益位为输入，`vout`、`error_metric`、`settled` 为输出；参数默认值写在题面。

用户已确认（2026-10-28）。总协调约 02:40Z 转达用户答复“全部按推荐”。推荐原文（`runs/t3-batch2-20261027/triage-disposition.json` 的 wait_for_user）：“move the first clk ramp to 9.1-10.1 ns (crossing 9.6 ns, public bench synced) and state 'global k*tick polling (k = 0, 1, ...)' in the Spec, as tasks 047/071/375 already do”。主控 brief：“把首个上升斜坡从 9.0–10.0 ns 改为 9.1–10.1 ns，交点 9.6 ns；公开台架 environment/public/visible_test.scs 同步”；“Spec 写明‘全局 k·tick（k = 0, 1, …）轮询’，与 047、071、375 一致”。

落实的改动：

- `tests/cases.json` 的 `contract-base` 与 `environment/public/visible_test.scs`：`Vclk` 的 `wave=[0 0 9n 0 10n 0.9 ...` 改为 `wave=[0 0 9.1n 0 10.1n 0.9 ...`，其余字节不变；派生的 `/app/testbench/cases.json` 与 `/app/testbench/visible_test.scs` 由改后字节生成。首个 `clk` 上升交点由 9.5 ns（第 38 个 tick）移到 9.6 ns，首次更新在 9.75 ns。改后 `contract-base` 与公开台架的全部控制交点（clk、rst、enable、增益位）距最近 tick 都是 100 ps。
- Spec 写明“The model polls its controls on the global time grid `k*tick`, `k = 0, 1, ...`, with `tick` = 250 ps; the first tick is at t = 0”，与 checker 一致（`tests/v2_spec.py:48-50` 自 t = 0 起每 `tick` 一个事件）。轮询的其余规则照 checker 与参考解写明：tick 上读控制电平；`clk` 本 tick 为高而上一 tick 不高才更新（`:126`）；上一 tick 的 `clk` 电平在每个 tick 都更新，包括复位与禁用期间（`:128`，参考解第 25 行），所以复位或禁用期间升起的时钟释放后不补更新；初值即复位值。

F01（评分起点）按用户 2026-10-28 的决定写明：checker 实际的观察起点，checker 不动。新句子：“Each output reaches its new value within `tr` after the tick that changes it. Every saved point is scored, for all three outputs, except points less than `1.15*tr` after t = 0 or after a tick that changes an output target.” 位置 `tests/v2_spec.py:188`，期望值来自 `:123-128`、`:151` 的事件历史，2 mV 判据在 `:205-208`。校准三件加了迟到负例 `late_transition_1p3tr` 与窗内对照 `inwindow_transition_1p1tr`（`tr` 与 `1.15*tr` 之间到达，这是用户已接受的余量）；两例步长 2 ps，评分起点与 `1.3*tr` 之间至少有 14 个保存行。另加两个轮询负例：在 `clk` 实际交点更新、轮询网格移半个 tick，都被拒。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。

## 待定项

`grading` 和 `runtime` 待定。历史作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，绑定旧 `/work` 题包与旧 `contract-base` 激励（9.5 ns 同刻点，历史作者校准记为通过），不认证本次 `/app` 包。模型试做没有做。

改动的效果（旧版开发证据）：改前激励下参考解在 `contract-base` 被拒（9.73 ns，`vout` 期望 0.465 V、实际 0.45 V；checker 在 9.5 ns 的同刻点以交点后电平判 clk 已高，参考解按 `V(clk) > vth` 推迟到 9.75 ns）；把旧版参考解波形的首次更新提前到 9.5 ns 后重放，checker 接受。改后参考解两例都通过。

残留的近同刻点（decisions-r1 记录；fix-dec-r1 已移开，见文末）：`contract-stretched-input` 在 69.003 ns 有一个 `clk` 上升交点，比第 276 个 tick（69.0 ns）晚 3 ps，tick 时 `clk` 比门限低约 0.28 mV。它不是同刻点，checker 与参考解都在 69.25 ns 更新，旧版通过；但用 `cross` 检测、事件时间容差大于 3 ps 的实现可能把交点放到 tick 之前。用户这轮只批准改 `contract-base`，所以没有动它，交主控决定是否同样移开。该例还有 6.273 ns 的 enable 交点距 tick 23 ps、39.483 与 100.983 ns 的 clk 下降交点距 tick 17 ps。

两例的 `clk` 下降与 `enable` 下降同在 82.1 ns（`contract-base`）和 100.983 ns（`contract-stretched-input`），与“独立控制边沿至少相隔 `2*tr`”字面不符；`clk` 下降沿不触发任何动作，判定无歧义，decisions-r1 只记录。两例都在 `clk` 低时释放 `rst` 与 `enable`，“复位或禁用期间跟踪 clk 电平、释放后不补更新”这一规则没有用例区分。这两条都由 fix-dec-r1 处理，见文末。

Spectre 待办：记录轮询 tick 上读到的控制电平与 `transition()` 的待发过渡行为。本题输出只在 tick 变化，同一输出两次变化至少相隔一个更新周期（数 ns），大于 `tr`，用例中没有被打断的过渡。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解私有 2 例、公开 1 例和公开台架都在 stage c 报 `kernel.step_budget`（#270 探针 NF-01），最后提交步约 1.86 ns，在改动的 9.6 ns 交点之前，与分诊一致。旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 通过（分诊时私有 1/2），只用网格行复判没有变化；4 个校准候选在两例的判决都与 `tests/calibration/expected.json` 一致。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

## fix-dec-r1 修正（2026-10-28）

依据：Astra 独立审核 `runs/t3-batch2-20261027/review-dec-r1/astra-review.json`（sha256 `22c74f3e…7154`，不入库）的 AR02–AR07（P2/Spec）与交接项 D370-1；主控决定见修正 brief `runs/t3-batch2-20261027/briefs/fix-dec-r1.md` 第 3–8 项。记录在本地运行目录 `runs/t3-batch2-20261027/fix-dec-r1/`（不入库）。**未仿真**：没有运行 Spectre 或模型。

- 控制沿间距（AR02）：`contract-base` 的 `clk` 最后一次下降由 82.0–82.2 ns 移到 81.5–81.7 ns（交点 81.6 ns），与 82.1 ns 的 `enable` 下降相隔 500 ps；公开台架 `environment/public/visible_test.scs`、派生的 `/app/testbench/visible_test.scs` 与 `/app/testbench/cases.json` 同步。`contract-stretched-input` 的 `clk` 最后一次下降移到 100.35 ns，`enable` 下降移到 100.9 ns，相隔 550 ps。82.1 ns 之后没有上升沿，移动不改变期望波形。
- 近同刻（D370-1）：台架设计目标定为每个控制交点距 250 ps tick 网格至少 50 ps。`contract-stretched-input` 中低于目标的交点都移到距 tick 100 ps：`enable` 上升 6.273 → 6.35 ns（原距 tick 23 ps）、`clk` 下降 39.483 → 39.4 ns（17 ps）、`clk` 下降 51.783 → 51.85 ns（33 ps）、`clk` 上升 56.703 → 56.65 ns（47 ps）、`clk` 上升 69.003 → 69.1 ns（3 ps）、三个增益位 71.463 → 71.4 ns（37 ps），以及上一条的 100.983 ns 两个下降。这些近 tick 的移动都保持“第一次看到新电平的 tick”不变（39.5、52.0、56.75、69.25、6.5、71.5 ns，`enable` 下降仍是 101.0 ns）。上一条为错开 `clk` 与 `enable` 而前移的两个末次 `clk` 下降不同：第一次读到低电平的 tick 在 `contract-base` 由 82.25 ns 变为 81.75 ns（交点 82.1 → 81.6 ns），在 `contract-stretched-input` 由 101.0 ns 变为 100.5 ns（交点 100.983 → 100.35 ns）。按原 checker 事件逻辑算的期望输出历史仍与改前逐项相同：`clk` 下降本身不触发更新，这两个下降之后没有 `clk` 上升，禁用生效的 tick（82.25 ns、101.0 ns）也没有变。改后四例的最小 tick 距离为 100、53、100、100 ps（53 ps 是未动的 19.803 与 81.303 ns 两个慢上升，tick 时离门限约 5 mV），不同控制交点的最小间隔为 500、550、500、500 ps，输出过渡终点与输入交点没有同刻，输入没有触到或停在门限上（精确有理数核对）。增益码的几位同刻切换算一次码变化，与现有用例一致。
- 参考解（AR03）：`vss` 可覆盖，题面与 checker 要求初态和复位、禁用时 `settled = vss`（`tests/v2_spec.py:51`、`:59`、`:125`），参考解原来在 `initial_step` 和复位、禁用分支写 0.0。两处改为 `vss`，`solution/circuit.va` 与 `solution/dut.va` 同改，sha256 `7b4b354f…0bf6` → `aca90998…db8e`，两份仍逐字节相同。
- 参数范围（AR04，用户 2026-10-29 按推荐确认，决定单第 8 项；原标“待用户确认”）：题面合法输入域加一句“Parameter overrides keep `0 < alpha <= 1` and `vss <= vcm <= vdd`, so each update moves the output to a point between its previous value and the clamped target.”，checker 不动。理由：在这个范围内 `vout_next` 是旧值与已钳位 target 的凸组合，外层钳位不起作用，checker 省略外层钳位（`tests/v2_spec.py:127`）与公开公式一致；范围外（如 `alpha` = 1.1）按公开公式正确钳位的输出会被 checker 拒（作者重放 3.982 ns，期望 0.945 V、实际 0.9 V）。另一种合理读法是允许 `alpha > 1`，给 checker 补外层钳位并重新校准公开副本。推荐前者：`alpha` 是“每次更新靠近 target 的比例”，本题选的是单调、无过冲的离散建立模型，`0 < alpha <= 1` 时每次更新落在旧值与已钳位 target 之间；`1 < alpha < 2` 会交替过冲，但对固定 target 仍收敛，所以排除它是模型选择，不是稳定性要求。前者也不改评分代码。改变了科学合同（缩小可覆盖参数的合法域），所以列为待用户确认，先按推荐写入；用户 2026-10-29 按推荐确认（见文末 author-r2 一节）。
- 新增私有用例 `contract-code-clamp-release`（24 ns，默认参数；AR05–AR07）：
  - 码 001、010、100 各在一次更新时生效（2.25、4.25、6.25 ns），之后码 111；忽略位（只读 `gain_0`）和交换位权的实现都在 2.48 ns 被拒。
  - 码 7 时 `vin` 为 0.60 V 和 0.30 V，原始 target 1.125 V 与 −0.225 V 分别钳到 0.9 V 和 0 V（8.25、16.25 ns）；只少上限钳位的实现 8.48 ns 被拒，只少下限钳位的 16.48 ns 被拒。两次钳位后的 `error_metric` 都在 0–0.9 V 内。
  - `clk` 在复位（11.6–13.1 ns）和禁用（17.6–19.1 ns）期间升高，释放时仍为高：13.25 与 19.25 ns 的 tick 不更新，16.25 与 22.25 ns 的真实上升沿恢复更新；复位或禁用期间不记录上一 tick `clk` 的实现分别在 13.25、19.25 ns 被拒。
- 新增私有用例 `contract-vss-offset`（22 ns，`vss` = 0.1 V；AR03）：从非复位状态起步，初态 `settled` = 0.1 V；`settled` 升到 0.9 V 后，9.6–11.1 ns 复位、17.6–19.6 ns 禁用。改前参考解（`settled` 低电平 0 V）0.23 ns 起被拒；只在复位时写 0 V 的实现 9.98 ns 被拒，只在禁用时写 0 V 的 17.98 ns 被拒。
- 两个新用例的控制交点都在 tick 后 100 ps，不同控制相距至少 500 ps，同一控制的相邻沿至少 1 ns。上面的评分点由作者模型在用例激励上、经原 checker 判定得到，旧版 EVAS 上对应候选的首个失败时刻与之相差不到 2 ps。
- 校准三件：新增九个负例（`settled_low_zero` = 改前参考解字节、`reset_settled_zero`、`disable_settled_zero`、`gain_bits_reversed`、`gain_code_from_bit0_only`、`target_no_upper_clamp`、`target_no_lower_clamp`、`prev_clk_frozen_in_reset`、`prev_clk_frozen_in_disable`），矩阵与说明见 `tests/calibration/`。F01 的迟到负例与窗内对照在新用例上都有评分行（步长 2 ps），旧版判决分别为拒绝和通过。
- 台架源参数（2026-10-28 新增台架规则：本单新建或修改的台架行，源参数一律显式写出）：改动与新建的 PWL 源只写 `type` 与 `wave`，未满足，交主控裁决。依赖的 Spectre 缺省（Spectre 21.1.0.509.isr12 `spectre -h vsource` 帮助，本地存档 `runs/evas-pulse-delay-20261017/pulse-help-collected/`，vaEVAS 主工作区，不入库，`vsource-help.log` sha256 `081a82af…93ac`）与同日其他题记录的相同：`dc`、`delay`=0、`edgetype`=linear、`offset`=0、`scale`=1、`stretch`=1，以及点数 ≥ 20 时 `allbrkpts`=no。EVAS 02dee32b 的 PWL 源只接受 `type` 与 `wave`（`evas/src/evas/scs_sources.py:22-30`）。新用例的 DUT 参数除 `vss` 外取模型默认值，这是合同要求的默认值，不是 Spectre 缺省。
- 开发证据：旧版 EVAS 0.8.7 上参考解私有 4/4、公开 1/1 通过，13 个校准候选在四例 52/52 与矩阵一致，只用网格行复判没有变化（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）。EVAS 02dee32b 上参考解四个私有例、公开例和公开台架都在 stage c 报 `kernel.step_budget`（NF-01），最后提交步在 1.68–1.86 ns，早于所有改动和新增的激励特征；起始模型在 stage a 报只有接口、没有 analog 块，属预期。

## dec r2 增量复审修正（2026-10-28）

依据：Astra 增量复审 `runs/t3-batch2-20261027/review-dec-r2/astra-review.json`（sha256 `1d97606c…`，不入库）的 R2-01（P2，Spec）、R2-02（P2，Standards）与 AR04 措辞意见；记录在本地运行目录 `runs/t3-batch2-20261027/f01-r1/`（不入库）。只改 `instruction.md` 与本页；checker、用例、参考解、公开激励与校准三件都没有改。**未仿真**：没有运行 Spectre 或模型，下面的核对都从用例激励按精确有理数算出。

- R2-01：题面合法输入域第 32 行在“Independent control edges are at least `2*tr` apart.”之后加一句：“The three gain bits form one code bus: the bits that change in one code change may cross `vth` at the same instant, and that change counts as one control event, so distinct code changes are at least `2*tr` apart from each other and from every `clk`, `rst`, or `enable` crossing.”。现行四例与这条约定一致：同刻多位切换出现在 `contract-base` 58.1 ns（三位同升）、`contract-stretched-input` 71.4 ns（三位同升）与 `contract-code-clamp-release` 3.6、5.6、7.6 ns（两位一升一降）；把三位当一个总线，码变化与其他码变化或 `clk`、`rst`、`enable` 交点的最小间隔是 2000、2300、500 ps，`contract-vss-offset` 没有码变化，都不小于 `2*tr` = 400 ps。checker 每个 tick 读完整码（`tests/v2_spec.py:127`），不动。
- R2-02：上一节“近同刻（D370-1）”一条原写“每次移动都保持‘第一次看到新电平的 tick’不变”，对末次 `clk` 下降不成立，已照实改写；输出历史不变的结论不变，理由改为“下降不触发更新、其后没有上升、禁用 tick 不变”。核对：把改前（`fix-dec-r1/orig/`）与现行用例的输入按 PWL 精确合成为每 2 ps 加全部折点与 tick 的输入行，交给原 checker，两例的期望输出历史逐项相同。
- AR04：上一节参数范围一条的理由改写为“本题选的是单调、无过冲的离散建立模型；`1 < alpha < 2` 会交替过冲但仍收敛”，不再说大于 1 不是稳定模型。合同取值范围 `0 < alpha <= 1` 不动；当时仍待用户确认（决定单第 8 项），用户 2026-10-29 按推荐确认。
- 本节核对的脚本与结果：`runs/t3-batch2-20261027/f01-r1/scripts/verify_370.py`、`evidence/370-dec-r2-check.json`。

## author-r2 定稿（2026-10-29）

依据：决定单第 8 项（审核 AR04），用户 2026-10-29 按推荐确认（`runs/t3-p0-pilot-20261027/pending-user-choices.md` 末尾“第二批”一节）；主控 brief `runs/t3-batch2-20261027/briefs/b2-author-r2.md` 第 4 项。记录在本地运行目录 `runs/t3-batch2-20261027/author-r2/`（不入库）。**未仿真**：本轮没有运行 Spectre、EVAS 或模型。

- 改了什么：只改本页，把参数范围一条的“待用户确认”改为用户已按推荐确认。合法域 `0 < alpha <= 1`、`vss <= vcm <= vdd` 已在题面第 32 行（“Parameter overrides keep `0 < alpha <= 1` and `vss <= vcm <= vdd`, so each update moves the output to a point between its previous value and the clamped target.”），checker 省略外层钳位与这一合法域一致，都不改。用例、参考解与校准件也不改。
- 已核收的 Spectre 结果（B2PC 预校准，作参考，不因本轮改动而变）：参考解与缺省容差对照 10 个作业都通过（must-01，执行身份 `spectre-B2PC-must-01-v1（结果包 sha256 fffd959be8465585…）`）；校准候选有登记期望的 65 个作业都与期望一致（rec-01 32 个，`spectre-B2PC-rec-01-v1（结果包 sha256 984027e2c18a8b03…）`；rec-02 20 个，`spectre-B2PC-rec-02-v1（结果包 sha256 a629d67a6220fbb5…）`；opt-01 13 个，`spectre-B2PC-opt-01-v1（结果包 sha256 3e80d95b2f27000a…）`）。
- Spectre 待办：本题不需要新的 Spectre 作业。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`clk`、`rst`、`enable`、`gain_2`、`gain_1`、`gain_0`，门限 `vth`（缺省 0.45 V；用例 `contract-vss-offset` 只覆盖 `vss`，不覆盖 `vth`）。控制在 tick 上被轮询，这一句照样适用。`vin` 是模拟输入，不在此列。
- 激励核对（未仿真）：题包全部 7 份网表（`tests/cases.json` 4 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 clk，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`clk`, `rst`, `enable`, `gain_2`, `gain_1`, and `gain_0` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
