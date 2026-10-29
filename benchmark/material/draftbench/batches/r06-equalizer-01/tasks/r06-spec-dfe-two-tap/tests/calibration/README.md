# 校准候选

Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

每个候选都是完整的单文件。checker 只有一类失败：某个评分点上 `decision`、`fb_metric` 或 `slicer_in_dbg` 与期望值相差超过 2 mV；该输出的期望值改变后 1.25·tr 内的点不评分。失败记录里的 `node`、`change_time` 和 `cause` 指出它属于哪次输出变化；判决事件的 `cause` 写出当时的历史与抽头码，例如 `decision 15 (h1=+0, h2=+0, k1=1, k2=3)` 是复位后的第一次判决，`h2=+0` 的是第二次。输出形状和容差边界由作者证据中的 Python 合成轨迹覆盖。参数端点由两个终评用例 `param-endpoints-low`、`param-endpoints-high` 覆盖；`vss` 的下端 −0.5 V 和 `clk` 的最短阈值脉宽（高、低电平各一次 0.502 ns，即 0.5 ns 下界加 2 ps 设计余量）由终评用例 `min-pulse-vss-low` 覆盖；作者证据中的两个合成端点用例另外核对 checker 在端点上的判定。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、4.5.8 `transition`、5.10.2 `initial_step` 写出。合同要求 `rst` 和抽头码输入的穿越离 `clk` 上升沿至少 0.5 ns，上升沿前后 100 ps 内 `vin` 变化小于 0.25 mV，每次判决的切片输入离 `vcm` 至少 5 mV（九个用例实际至少 7 mV），所以事件定位误差在几 ps 内时判决不变。

列中用例简称：
- 复位七例：`base`、`reset-restart`、`param-override`、`long-tr`、`param-endpoints-low`、`param-endpoints-high`、`min-pulse-vss-low`，有判决之后的复位；
- 参数四例：`param-override`（vdd 1.2 V、vss 0.1 V、vcm 0.35 V、vth 0.7 V、tap_lsb 30 mV、tr 100 ps）、`param-endpoints-low`（vdd 0.5 V、vss 0.1 V、vcm 0.2 V、vth 0.2 V、tap_lsb 5 mV、tr 10 ps）、`param-endpoints-high`（vdd 1.5 V、vss 0.5 V、vcm 0.7 V、vth 0.7 V、tap_lsb 50 mV、tr 1 ns）、`min-pulse-vss-low`（vdd 1.5 V、vss −0.5 V、vcm 0.55 V、vth 0.3 V、tap_lsb 40 mV、tr 40 ps）；
- 全部：九个用例（另两例是 `history-pairs`、`isi-channel`）。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `empty_history_low` | 空历史当作低判决 −1（原 v4:354 gold 的做法，决定卡选项 B） | 全部 | 复位后头两拍的 `fb_metric`、`slicer_in_dbg`，部分 `decision` |
| `empty_history_high` | 空历史当作高判决 +1：上电与复位时两格历史置 +1（v4:854 neg_005 的实际改动） | 全部 | 上电与复位后头两拍的 `fb_metric`、`slicer_in_dbg`，部分 `decision` |
| `unipolar_history` | 低判决贡献 0（0/1 编码，决定卡选项 C） | 全部 | `fb_metric`、`slicer_in_dbg`、`decision` |
| `empty_second_slot_low` | 只把空着的第二格当低判决 | 全部 | 复位后头两拍的 `fb_metric` 等 |
| `feedback_added` | 切片输入为 `vin + fb`（v4:1354 的故障） | 全部 | 三个输出 |
| `tap_order_swapped` | tap 1 加权较早的判决，tap 2 加权最近的判决（抽头配对错误，不是历史变异） | 全部 | 三个输出 |
| `second_tap_ignored` | 反馈只用 tap 1，第二抽头不起作用（v4:854 neg_003 类） | 全部 | `fb_metric` 等 |
| `tap_bits_swapped` | 把 `tap1_0`、`tap2_0` 当高位 | 全部 | `fb_metric` 等 |
| `no_feedback` | 不做反馈，只切 `vin` | 全部 | 三个输出 |
| `input_sign_as_history` | 历史存 `vin` 相对 `vcm` 的符号，不存判决 | 全部 | 反馈改变判决之后的 `fb_metric` 等 |
| `shift_before_feedback` | 先移位再算反馈，tap 2 用到上一拍的判决 | 全部 | 三个输出 |
| `history_one_decision_late` | 多一级寄存，反馈用第 n−2、n−3 次判决 | 全部 | 三个输出 |
| `raw_current_decision_in_feedback` | 反馈用本拍 `vin` 的原始符号代替最近的判决 | 全部 | 三个输出 |
| `decision_on_raw_input` | 判决比较 `vin` 与 `vcm`，不用校正后的输入 | 全部 | `decision` |
| `slicer_compares_with_vth` | 切片门限用 `vth` | `param-override`、`min-pulse-vss-low` | `decision` |
| `decision_polarity` | 切片输入低于 `vcm` 时判高（v4:854 neg_001 类） | 全部 | `decision` |
| `fb_metric_reports_next_feedback` | `fb_metric` 报告移位后下一拍的反馈 | 全部 | `fb_metric` |
| `live_metrics` | 两个观测口跟随实时抽头码、移位后的历史和 `vin`（原 gold 的观测方式，空历史按 0） | 全部 | `fb_metric`、`slicer_in_dbg` |
| `slicer_dbg_follows_vin` | `slicer_in_dbg` 在判决后跟随 `vin − fb` | 全部 | `slicer_in_dbg` |
| `taps_one_decision_old` | 本拍用上一次判决时读到的抽头码 | `base`、`history-pairs`、参数四例 | 抽头改变后第一拍的 `fb_metric` 等 |
| `taps_read_only_at_reset` | 只在 t = 0 和 `rst` 上升时读抽头码 | 除 `isi-channel`、`long-tr` 外的七例 | `fb_metric` 等 |
| `synchronous_reset` | 复位只在 `rst` 为高的时钟沿生效 | 复位七例 | 复位上升到下一个时钟沿之间的三个输出 |
| `reset_keeps_history` | 复位清输出但不清历史 | 复位七例 | 复位后头两拍 |
| `reset_clears_h1_only` | 复位只清最近的一格历史 | 复位七例 | 复位后头两拍 |
| `decisions_during_reset` | `rst` 为高时时钟沿照常判决 | `base`、`reset-restart`、`long-tr`、`param-endpoints-low`、`param-endpoints-high`、`min-pulse-vss-low` | 复位期间的三个输出 |
| `cleared_dbg_at_vss` | 清零时 `slicer_in_dbg` 取 `vss` | 参数四例 | `slicer_in_dbg`（t = 0 起） |
| `first_decision_after_reset_skipped` | 复位后第一个 `rst` 为低的上升沿只用来“重新武装”，不判决 | 复位七例 | 复位后头两拍 |
| `initial_decision_high` | t = 0 时 `decision` 为 `vdd` | 全部 | t = 0 起的 `decision` |
| `falling_edge_clock` | 用 `clk` 下降沿判决 | 全部 | 时序 |
| `clk_deglitch_0p6n` | `clk` 低于 `vth` 不足 0.6 ns 后的上升沿不判决（比合同的 0.5 ns 更严的去毛刺） | `min-pulse-vss-low` | 0.502 ns 低电平之后那一拍起的三个输出 |
| `slow_output_1p3tr` | 过渡时间 1.3·tr，到达晚于评分起点 1.25·tr | 全部 | 评分起点后第一个点（变化 104 mV 及以上的输出变化） |
| `hardcoded_vdd_0p9` | 高电平写死 0.9 V | 参数四例 | `decision` |
| `hardcoded_vss_0` | 低电平和清零电平写死 0 V | 参数四例 | `decision` |
| `hardcoded_vcm_0p45` | 切片门限写死 0.45 V | 参数四例 | `decision` 等 |
| `hardcoded_vth_0p45` | 控制门限写死 0.45 V | 参数四例 | 时序（`param-override`、`param-endpoints-high` 的 180 ps 边沿上早 50 ps，`param-endpoints-low` 的 90 ps 边沿上晚 25 ps，`min-pulse-vss-low` 的 90 ps 边沿上晚 15 ps） |
| `hardcoded_tap_lsb_20m` | 抽头步长写死 20 mV | 参数四例 | `fb_metric` 等 |
| `hardcoded_tr_200p` | 过渡时间写死 200 ps | `param-override`、`param-endpoints-low`、`min-pulse-vss-low` | 1.25·tr 时未到达 |
| `tr_floor_100p` | 过渡时间钳到 max(tr, 100 ps) | `param-endpoints-low`、`min-pulse-vss-low` | 1.25·tr 时未到达（tr = 10 ps、40 ps） |
| `decision_floor_0v` | `decision` 钳到不低于 0 V | `min-pulse-vss-low` | `decision`（低判决与清零时的 −0.5 V） |
| `original_v4_354_gold` | 原 v4:354 四个 gold 模块原样提交（唯一不是为本题写的候选） | 全部 | `fb_metric`、`slicer_in_dbg` |
| `alt_valid_count`（正确） | 判决存成 0/1，另记复位后已有几次判决 | 无 | 无 |
| `alt_modules`（正确） | 反馈求和、切片寄存、顶层三个模块（内部组织自由的例子） | 无（条件见下） | 无 |
| `alt_fast_output`（正确） | 过渡时间 0.2·tr | 无 | 无 |
| `alt_delayed_within_tr`（正确） | 延迟 0.2·tr 后用 0.8·tr 过渡，正好在 tr 到达 | 无 | 无 |
| `margin_arrival_1p2tr`（用户已接受的余量） | 过渡时间 1.2·tr：晚于期限 tr，早于评分起点 1.25·tr | 无 | 无 |

`hardcoded_tr_200p` 在 `reset-restart`（`tr = 400 ps`）、`long-tr` 和 `param-endpoints-high`（`tr = 1 ns`）中不被拒：200 ps 的过渡早于期限到达，合同允许。`tr_floor_100p` 在 `tr` 不小于 100 ps 的七个用例中与参考解相同，只在 `param-endpoints-low`（`tr = 10 ps`）与 `min-pulse-vss-low`（`tr = 40 ps`）被拒。`decision_floor_0v` 在 `vss` 不小于 0 的八个用例中与参考解相同，只在 `min-pulse-vss-low`（`vss = −0.5 V`）被拒。`clk_deglitch_0p6n` 在原八例中与参考解相同，因为这些用例每个 `clk` 上升穿越之前都至少低 0.86 ns；它只在 `min-pulse-vss-low` 被拒，该例有一次 0.502 ns 的低电平。`taps_one_decision_old` 在 `reset-restart` 中不被拒：该例只在复位期间改抽头码，复位后的第一次判决没有反馈；`isi-channel` 和 `long-tr` 的抽头码固定。`slicer_compares_with_vth` 只在 `param-override` 与 `min-pulse-vss-low` 被拒：其余用例的 `vcm` 与 `vth` 相等。

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- 全部条目：假定 `cross()` 事件定位在穿越时刻或稍后。`tr` 不小于 100 ps 的用例容得下几 ps；`min-pulse-vss-low`（`tr = 40 ps`）要求在 3 ps 内：该例的评分行在事件后 1.275·`tr`，`margin_arrival_1p2tr` 比它早 3 ps 到达，参考解早 11 ps；`param-endpoints-low`（`tr = 10 ps`）要求在 0.7 ps 内：该例的评分行在事件后 1.27·`tr`，`margin_arrival_1p2tr` 比它早 0.7 ps 到达，参考解早 2.7 ps。
- `alt_modules`：切片寄存模块在时钟事件读取反馈节点，反馈节点由另一个模块从历史节点连续算出；历史节点是 `transition()` 输出，目标只在同一事件改变，所以按 LRM 4.5.8 该时刻读到的是事件之前的历史。反馈求和模块没有事件，不涉及跨实例的事件次序。Spectre 上要记录。
- `alt_delayed_within_tr`：用了 0.2·tr 的传输延迟（至多 0.2 ns），属于待发过渡。合法输入中改变输出的事件至少相隔 0.5 ns，每个延迟变化在下一个变化排上之前已经开始，不会有待发过渡被删除（LRM 4.5.8）。
- 过渡被打断（`interrupted_transitions`）：`long-tr`（`tr = 1 ns`）里两次复位在判决后 0.6 ns 上升，输出仍在过渡中就被改写目标。按 LRM 4.5.8 的完成规则，被打断的 `transition()` 在打断后 tr 内到达新值，前提是延迟为 0、上升与下降时间都是 tr、目标在两次事件之间不变；非零延迟、上升下降时间不等或排队的过渡要另算。所以满足这些前提的候选在这一例和别的用例一样判；合成控制里“等当前过渡走完再开始新过渡”的模型只在这一例被拒。两个端点用例和 `min-pulse-vss-low` 没有打断。
- `margin_arrival_1p2tr`：不是正确模型，它晚于期限 tr 到达。按用户已确认的观察规则（F01 选 A，2026-10-28），评分起点前到达的输出不判错，这是已接受的余量。
- `original_v4_354_gold`：顶层模块名与端口和本题相同，原样使用；它把空历史当低判决，两个观测口随实时输入和移位后的历史变化，`fb_metric` 没有复位通路。它不是作者写的：`mutants.py` 只在仓库内运行时从 `benchmark/material/historyref` 按原字节读取四个文件，去掉 include 行后拼接。
- `empty_history_high`：对应 v4:854 `neg_005_reset_preserves_history` 的实际改动。该变异包的 `decision_latch.va` 第 27–29、33–35 行在上电和 `rst` 上升时把 `current_bit`、`prev1_bit`、`prev2_bit` 三个状态位由 0 改成 1。后两位是两格历史，置 1 即本候选的“空历史当高判决”；`current_bit` 驱动原 gold 的 `decision` 输出，本候选让清零后的 `decision` 仍为 `vss`（t = 0 时 `decision` 为 `vdd` 的错误另见 `initial_decision_high`）。九个用例上电或复位后的第一次判决都有非零抽头码，都应拒绝。
- `second_tap_ignored`：反馈只用 tap 1，对应 v4:854 `neg_003_second_tap_ignored` 的故障类（`missing_tap`）。历史变异把第二项换成固定的 4·d1，本候选直接去掉第二项；九个用例都有 k2 非零且第二格有判决的拍。
- `slow_output_1p3tr`：九个用例都把改变输出的事件放在输出网格的固定相位上，使事件后 (1.25·tr, 1.3·tr) 内有一个评分行：`base`、`history-pairs`、`reset-restart`、`param-override`、`isi-channel`、`param-endpoints-high`、`min-pulse-vss-low` 在 1.275·tr，`long-tr` 在 1.255·tr，`param-endpoints-low` 在 1.27·tr。1.3·tr 的到达在这一行上对不小于 104 mV 的变化都超出 2 mV。`decision` 的 162 次变化中，161 次属此类并被看到；`long-tr` 有 5 次输出变化（其中 1 次是 `decision`）被 0.6 ns 后的复位改写，没有自己的评分行。迟到负例在九个用例都被拒。

合成控制的对应范围：`expected.json` 的 `author_synthetic_control` 是作者证据中对应的 Python 合成控制。`live_metrics` 对应 `live-metrics`，`original_v4_354_gold` 对应 `live-gold-observation`（空历史按低判决、无 `fb_metric` 复位、复位期间 `slicer_in_dbg` 为 `vss`），`second_tap_ignored` 对应 `second-tap-ignored`，`tr_floor_100p` 对应 `tr-floor-100p`，`empty_history_high` 对应 `empty-history-high`，`decision_floor_0v` 对应 `decision-floor-0V`，`clk_deglitch_0p6n` 对应 `clk-deglitch-0.6ns`。

参考解没有待发事件：它的 `transition()` 延迟为 0，也没有定时器。上面的待发事件只属于校准候选 `alt_delayed_within_tr`，与参考解分别判断。

旧版 EVAS 0.8.7 上的运行结果记在作者证据中，不改变这张表。
