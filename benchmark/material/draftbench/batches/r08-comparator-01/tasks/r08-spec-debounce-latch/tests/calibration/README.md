# 校准候选

Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

checker 只有一类失败：某个评分点的 `V(out)` 与理想电平相差超过 10 mV。失败记录里的 `level_change`、`change_time` 和 `cause` 指出它属于哪一次理想电平变化（初态、哪次资格的完成、哪次 `sig` 或 `rst_n` 下降）。`tr` 内的输出形状由作者证据中的 Python 合成轨迹覆盖。台架义务不满足时 checker 抛出异常，记 checker_error，不判分；修正 r7a 加了一条：同一输入相邻两次穿越之间离 `vth` 不足 49 mV（合同写 50 mV）。这一条与输入的起点、停留、碰到都按用例网表的激励定义判（2026-10-30 修正 v417），碰到报台架错误。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、5.10.3.2 `above`、5.10.3.3 `timer`、4.5.8 `transition` 写出。参考解依赖 5.10.3.3：起始时刻被改写后只按最新值触发，起始时刻在过去则不触发。下表的"过期预约"指已被取消的资格，它原定的完成时刻到达时 `sig` 与 `rst_n` 都已重新为高；`base` 有 77.02、85.02、132.02 ns 三处，`retrigger-ties` 有 78.02 ns，`short-stable` 有 16.002、17.502、68.002 ns。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `immediate_set_on_rise` | 上升沿当即置高（第二批修复题起始模型的故障） | 全部 | `out` |
| `stale_first_reservation` | 下降不取消预约，新上升沿不重新预约，到期时 `sig` 已重新为高便置高 | `base`、`retrigger-ties`、`short-stable` | `out`（过期预约误触发） |
| `reset_keeps_reservation` | 复位只清输出、不取消预约 | `base`、`short-stable` | `out`（复位后的过期预约） |
| `no_recheck_fall_keeps_reservation` | 下降不取消预约，到期只复核 `rst_n` | `base`、`short-stable`、`threshold-override` | `out` |
| `arms_while_reset` | 复位期间的上升沿也开始资格 | `base`、`retrigger-ties` | `out` |
| `level_sensitive_start` | 复位释放时或 t = 0 时 `sig` 为高也开始资格 | `base`、`retrigger-ties`、`short-stable` | `out` |
| `power_up_above` | 用 `above()` 检测上升，初始化时 `sig` 已高即开始资格 | `retrigger-ties` | `out`（12 ns 起） |
| `accumulated_high_time` | 高电平时间跨毛刺累加 | 全部 | `out`（提前置高） |
| `transport_delay_and` | `out` = armed(t) 且 armed(t − stable)，用 `transition()` 传输延迟 | 全部（条件见下） | `out` |
| `symmetric_debounce` | 下降也要持续 `stable` 才清零 | 全部 | `out` |
| `fall_keeps_output` | 下降只取消资格、不清输出 | 全部 | `out` |
| `output_gated_by_reset` | 复位只屏蔽输出，释放后锁存的高电平回来 | 全部 | `out` |
| `rst_active_high` | 复位极性反了 | 全部 | `out` |
| `hardcoded_stable_12n` | 资格时间写死 12 ns | `short-stable`、`threshold-override` | `out` |
| `hardcoded_vth_045` | 门限写死 0.45 V | `threshold-override` | `out` |
| `hardcoded_vdd_09` | 高电平写死 0.9 V | `short-stable` | `out` |
| `hardcoded_tr_500p` | 过渡时间写死 500 ps | `short-stable` | `out`（1.25·tr 时未到达） |
| `slow_output_1p3tr` | 过渡时间 1.3·tr，到达晚于评分起点 1.25·tr | 全部 | `out`（评分起点后第一个点） |
| `late_by_0p3tr` | 完成时刻晚 0.3·tr | 全部 | `out` |
| `late_by_tr` | 完成时刻晚 tr | 全部 | `out` |
| `early_by_tr` | 完成时刻早 tr | 全部 | `out` |
| `alt_transition_delay`（正确） | 不用定时器：上升变化延迟 `stable`、下降变化零延迟，靠 4.5.8 删除其后的待发过渡 | 无（条件见下） | 无 |
| `alt_event_flags`（正确） | 输入电平由事件维护成标志，取消时把定时器时刻移到过去 | 无 | 无 |
| `alt_fast_output`（正确） | 过渡时间 0.2·tr | 无 | 无 |
| `alt_delayed_within_tr`（正确） | 延迟 0.2·tr 后用 0.8·tr 过渡，正好在 tr 到达 | 无 | 无 |

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- `alt_transition_delay`：接受的前提是零延迟的下降变化删除排在它之后的待发上升变化，且每次变化安排时取当时的 `td`。在评测域之外、完成时刻与下降正好同刻时，旧版 EVAS 仍执行了待发上升，输出出现到达 0.9 V 的毛刺脉冲（作者同刻探针），违反同刻规则；如果终评加入正好同刻的用例，它改列 `wrong`。
- `transport_delay_and`：全部拒绝的前提是 `transition()` 保留所有待发变化，即传输延迟；以新变化替换待发变化的后端可能只在部分用例拒绝它。
- `alt_event_flags`：接受的前提是起始时刻移到过去的定时器不再触发。

旧版 EVAS 0.8.7 上 25 个候选都能运行，判决与上表逐项一致，结果见作者证据；旧版结果不改本表。只有标量状态、不用 `absdelay` 的正确实现：参考解、`alt_event_flags`、`alt_fast_output`、`alt_delayed_within_tr`。

## 修正 r7a（2026-10-29）

- `retrigger-ties` 的平局挪动已按用户决定退回原件。退回后 45.02/45.52 ns 恰在 0.5 ns 下界上，于是把 45.02 ns 的下降提前一个网格步到 44.995 ns，毛刺宽 0.525 ns。
- 其余在合同下界上的 16 处都加了一个网格步的余量。详见 `SOURCE.md` 的“2026-10-29 修正 r7a”一节。上文列出的过期预约时刻都不变。
- 被拒矩阵不变。旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：
  - 参考解与 25 个候选在改后的四个私有用例上重跑，参考解另跑公开 `base`，共 105 次；
  - 判决与 `expected.json` 逐项一致，只用网格行重判的结论相同。
- Spectre 上要在改后的用例上重跑全部候选，作业清单见本轮记录。
