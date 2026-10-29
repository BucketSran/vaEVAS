# 校准候选

Spectre 校准待做。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 应被拒，`correct/` 应被接受，都用 `../cases.json` 的固定用例和同一 checker 判定。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新建或空目录>`。`expected.json` 是同一被拒矩阵的机器可读形式。

checker 只有一类失败：某个评分点的 `vout` 或 `metric` 与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）。评分起点按 F01（用户 2026-10-28 确认，A 方案）：t = 0 之后、以及任一期望输出改变之后 `1.15*tr` 内的点不评分（`tests/v2_spec.py:188`），题面照此写明，checker 不动。

“三例”指 `contract-base`、`contract-stretched-input` 和 fix-dec-r1 新增的 `contract-midrun-reset`。新用例在保持值不等于 `vinit` 时两次拉高 `rst`：13.5 ns 拉高时窗口开着（14 ns 的 tick 复位并关窗，16.5 ns 释放时 sample 仍高）；27.3 ns 拉高时窗口已关，27.75 ns 的 sample 上升交点在 28 ns 复位 tick 之前（29.6 ns 释放时 sample 仍高）。最后两个窗口分别只含 2 个和 1 个 tick。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `late_transition_1p3tr` | 两个输出的过渡时间为 `1.3*tr`，晚于 `1.15*tr` 评分起点才到达（F01 迟到负例） | 三例 | `metric`/`vout`（评分起点处未到） |
| `inwindow_transition_1p1tr`（correct） | 过渡时间 `1.1*tr`：到达时刻在题面期限 `tr` 与评分起点 `1.15*tr` 之间，这是用户已接受的余量（F01 窗内对照） | 无 | 无 |
| `v1_bugfix_buggy` | 与 v1 bugfix 起始模型 `gold/dut_buggy.va`（src-9276ce9b6eb2，sha256 `082b0724…f918`）逐字节相同：开窗沿上直接复制 `vin`，tick 不更新 | 三例 | `vout`（开窗后立即跳到输入） |
| `ideal_sampler_alpha_one` | 每个 tick 直接取 `vin`（相当于 alpha=1） | 三例 | `vout` |
| `local_tick_grid` | 更新网格从每次开窗沿重新起算，不用全局 `k*tick` | 三例 | `vout` |
| `prefix_reference_sample_edge_reset` | 与 fix-dec-r1 之前的参考解逐字节相同（sha256 `4482266e…fa30`）：`rst` 为高时的 sample 上升沿立即把保持值置为 `vinit` | `contract-midrun-reset`（另两例应通过） | `vout`（27.75 ns 起，早于 28 ns 的复位 tick） |
| `async_reset_on_rst_edge` | `rst` 上升交点立即复位并关窗，不等下一个 tick | `contract-midrun-reset`（另两例应通过） | `vout`（13.5 ns 起） |
| `reopen_on_rst_release` | `rst` 释放时若 sample 为高就重新开窗 | `contract-midrun-reset`（另两例应通过） | `metric`（16.5 ns 起） |
| `reset_keeps_window` | 复位 tick 把保持值置为 `vinit`，但不关窗 | `contract-midrun-reset`（另两例应通过） | `metric`（14.23 ns 起） |
| `alt_timer_before_cross`（correct） | 同一更新律，tick 事件块写在 cross 块之前 | 无 | 无 |

条件：`alt_timer_before_cross` 只在没有 sample 交点恰落在 tick 上时与参考解等价。三例的 sample 与 rst 交点距最近 tick 至少 50 ps（新用例至少 250 ps）。decisions-r1 之前的 80.0 ns 同刻点上，按 LRM 的源码次序它会少一次更新：decisions-r1 作者证据中对 c485de86 激励的重放（旧版参考解波形，80 ns 那次更新去掉）被 checker 拒绝，首个失败在 80.23 ns，偏差约 0.19 V。

旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上，以上 10 个候选在三例的判决都与本表一致（30/30，fix-dec-r1 重跑），只用网格行复判没有变化。新增四个负例的首个失败分别在 27.75、13.5、16.5、14.23 ns。这是旧版开发证据，待 Spectre 复跑。旧版对同刻的 cross 与 timer 不按源码次序：在 c485de86 激励上 `alt_timer_before_cross` 与参考解给出相同波形、都通过，所以旧版不能复现上面的次序问题。

fix-dec-r1（2026-10-28）按 Astra 审核 AR01 与主控决定改参考解：删去 sample 上升事件里的 `held = vinit`，复位只在 tick 生效。生成器随之更新，`v1_bugfix_buggy` 仍与原始坏版逐字节相同，改前参考解保留为 `prefix_reference_sample_edge_reset`。
