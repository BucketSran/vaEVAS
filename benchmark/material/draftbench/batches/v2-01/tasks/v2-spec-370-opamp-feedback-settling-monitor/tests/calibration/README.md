# 校准候选

Spectre 校准待做。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 应被拒，`correct/` 应被接受，都用 `../cases.json` 的固定用例和同一 checker 判定。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新建或空目录>`。`expected.json` 是同一被拒矩阵的机器可读形式。

checker 只有一类失败：某个评分点的 `vout`、`error_metric` 或 `settled` 与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）。评分起点按 F01（用户 2026-10-28 确认，A 方案）：t = 0 之后、以及改变任一期望输出的 tick 之后 `1.15*tr` 内的点不评分（`tests/v2_spec.py:188`），题面照此写明，checker 不动。

用例共四个。fix-dec-r1 新增两个私有用例：

- `contract-code-clamp-release`（默认参数）：增益码依次为 001、010、100、111，各有一次更新生效；码 7 时 `vin` 为 0.60 V 和 0.30 V，原始 target 为 1.125 V 和 −0.225 V，分别被钳到 `vdd` 和 `vss`；`rst` 在 13.1 ns、`enable` 在 19.1 ns 释放时 `clk` 都已为高，释放时的 tick 不更新，下一次真实上升沿（16.25、22.25 ns）恢复更新。
- `contract-vss-offset`（`vss` = 0.1 V）：从非复位状态起步，看到初态的 `settled = vss`；`settled` 升到 `vdd` 后，9.6–11.1 ns 复位、17.6–19.6 ns 禁用，两段的低电平都应为 0.1 V。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `late_transition_1p3tr` | 三个输出的过渡时间为 `1.3*tr`，晚于 `1.15*tr` 评分起点才到达（F01 迟到负例） | 四例 | 评分起点处未到 |
| `inwindow_transition_1p1tr`（correct） | 过渡时间 `1.1*tr`：到达时刻在题面期限 `tr` 与评分起点 `1.15*tr` 之间，这是用户已接受的余量（F01 窗内对照） | 无 | 无 |
| `edge_triggered_update` | 同一更新律，但在 `clk` 实际上升交点更新，不等下一个全局 tick | 四例 | `error_metric`（比期望早约 150 ps 变化） |
| `half_tick_phase` | 轮询网格移到 `(k+1/2)*tick`，不是全局 `k*tick` | 四例 | `error_metric`/`vout` |
| `settled_low_zero` | 与 fix-dec-r1 之前的参考解逐字节相同（sha256 `7b4b354f…0bf6`）：初态和复位、禁用时 `settled` 为 0 V 而非 `vss` | `contract-vss-offset` | `settled`（0.23 ns 起，初态） |
| `reset_settled_zero` | 只在复位时把 `settled` 置为 0 V | `contract-vss-offset` | `settled`（9.98 ns 起，复位段） |
| `disable_settled_zero` | 只在禁用时把 `settled` 置为 0 V | `contract-vss-offset` | `settled`（17.98 ns 起，禁用段） |
| `gain_bits_reversed` | 位权交换：`gain_0` 计 4、`gain_2` 计 1 | `contract-code-clamp-release` | `vout`（2.48 ns 起，码 001） |
| `gain_code_from_bit0_only` | 只读 `gain_0`，为 1 时码取 7，忽略另两位 | `contract-code-clamp-release` | `vout`（2.48 ns 起） |
| `target_no_upper_clamp` | target 只钳下限，不钳 `vdd` | `contract-code-clamp-release` | `vout`（8.48 ns 起） |
| `target_no_lower_clamp` | target 只钳上限，不钳 `vss` | `contract-code-clamp-release` | `vout`（16.48 ns 起） |
| `prev_clk_frozen_in_reset` | 复位期间的 tick 不记录上一 tick 的 `clk` | `contract-code-clamp-release` | `error_metric`（13.25 ns，释放时补了一次更新） |
| `prev_clk_frozen_in_disable` | 禁用期间的 tick 不记录上一 tick 的 `clk` | `contract-code-clamp-release` | `error_metric`（19.25 ns，同上） |

后九个负例在各自“必须拒绝”以外的三例上应通过（`expected.json` 的 `must_accept`）：那些用例只有码 000/111、target 不越界、释放时 `clk` 为低、`vss` = 0。

旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上，以上 13 个候选在四例的判决都与本表一致（52/52，fix-dec-r1 重跑），只用网格行复判没有变化。表中的首个失败时刻取自这些旧版结果。这是旧版开发证据，待 Spectre 复跑。

2026-10-28 decisions-r1 把 `contract-base` 首个 `clk` 上升斜坡由 9–10 ns 改为 9.1–10.1 ns（交点 9.6 ns），公开台架同步。改前交点恰在 9.5 ns 的 tick 上：checker 以交点后的电平判 clk 已高、在 9.5 ns 更新，参考解在 9.75 ns 更新；作者证据中对改前旧版波形的重放：把首次更新提前到 9.5 ns 后被 checker 接受，原波形被拒（9.73 ns，`vout` 期望 0.465 V、实际 0.45 V）。fix-dec-r1 再把 `contract-base` 的 `clk` 下降移到 81.6 ns，与 82.1 ns 的 `enable` 下降相隔 500 ps；`contract-stretched-input` 的各控制交点距 tick 都不少于 50 ps，`clk` 与 `enable` 的下降相隔 550 ps。这些移动都不改变哪个 tick 第一次看到新电平，期望波形不变。

参考解的 `settled` 低电平在 fix-dec-r1 改为 `vss`（初态与复位、禁用分支）。
