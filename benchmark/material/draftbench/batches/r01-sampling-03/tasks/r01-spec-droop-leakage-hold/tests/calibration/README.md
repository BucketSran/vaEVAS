# 校准候选

未仿真：本题尚无 Spectre 运行，Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

每个候选都是完整的单文件。checker 只有一类失败：某个评分点上 `vout` 与期望的保持值相差超过 2 mV；保持值的一次变化超过 0.1 mV（题面写明的门限 δ）时，其后 1.25·tr 内的点不评分，不超过 0.1 mV 的变化不开窗。失败记录里的 `change_time` 和 `cause` 指出它属于哪个事件：`capture n`、`rst rising crossing` 或 `leak update at … ns`。台架义务不满足时（包括控制的电平转移长于 200 ps：checker 用离两电平都超过 1 mV 的保存行给出转移长度的下界），checker 报错、不判分。输出形状和容差边界由作者证据中的 Python 合成轨迹覆盖。参数端点由终评用例 `param-endpoints-low`（vth 0.1 V、decay 0.5、leak_period 0.5 ns、tr 10 ps）、`param-endpoints-high`（vth 0.8 V、decay 1、tr 1 ns，tr = leak_period/2）和 `param-override`（leak_period 10 ns 的上端，另有 vth 0.2 V、decay 0.9、tr 100 ps）覆盖。最短合法脉冲与间隔：`phase-grid` 末尾两次捕获之间高、低各 0.525 ns，`param-endpoints-low` 有 0.5008 ns 的 `sample` 高电平、0.5008 ns 的低电平和 0.5008 ns 的 `rst` 脉冲（0.5 ns 下界加一个 0.8 ps 网格步），`base`、`reset-release`、`start-high` 各有 0.525 ns 的清零脉冲。t = 0 时 `sample` 已高的情形由 `start-high` 覆盖。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、5.10.3.3 `timer`、4.5.8 `transition`、5.10.2 `initial_step` 写出。合同要求 `sample` 上升穿越离任一泄漏时刻至少 50 ps（用例实际至少 50.35 ps），`rst` 穿越离 `sample` 上升穿越至少 0.5 ns，上升穿越前后 100 ps 内 `vin` 变化小于 0.25 mV，所以事件定位误差在几 ps 内时判决不变。

列中用例简称：
- 漏电六例：`base`、`phase-grid`、`reset-release`、`param-override`、`param-endpoints-low`、`start-high`（decay < 1）；`param-endpoints-high` 的 decay = 1，不漏电；
- 复位六例：`base`、`reset-release`、`param-override`、`param-endpoints-low`、`param-endpoints-high`、`start-high`，都有清除非零保持值的 `rst` 上升；`phase-grid` 没有复位；
- 参数三例：`param-override`、`param-endpoints-low`、`param-endpoints-high`；
- 全部：七个用例。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `leak_from_capture` | 泄漏网格在每次捕获时重新起算，第一次泄漏在捕获后一个周期 | 漏电六例 | 捕获后第一次泄漏前后的保持段 |
| `leak_grid_half_phase` | 泄漏时刻为 (k + 1/2)·leak_period | 漏电六例 | 各泄漏段 |
| `continuous_leak` | 捕获值连续衰减 decay^((t − t_c)/leak_period)，不分步 | 漏电六例 | 泄漏时刻之间的保持段 |
| `no_leak` | 理想保持，不泄漏 | 漏电六例 | 第一次泄漏之后 |
| `leak_only_sample_low` | `sample` 为高时跳过泄漏 | 漏电六例 | `sample` 高电平期间的泄漏 |
| `negative_not_leaked` | 负的保持值不泄漏 | 漏电六例 | 负捕获之后 |
| `capture_includes_leak` | 捕获时存 decay·vin | 漏电六例 | 捕获后的保持段 |
| `decay_fixed_0p985` | decay 写死 0.985 | 参数三例 | 泄漏段（decay = 1 时也错） |
| `period_fixed_1n` | leak_period 写死 1 ns | `param-override`、`param-endpoints-low` | 泄漏段 |
| `tr_fixed_500p` | 过渡时间写死 500 ps | `param-override`、`param-endpoints-low` | 1.25·tr 时未到达 |
| `tr_floor_100p` | 过渡时间钳到 max(tr, 100 ps)（U17R1-01 的模式） | `param-endpoints-low` | 1.25·tr 时未到达（tr = 10 ps） |
| `vth_fixed_0p45` | 门限写死 0.45 V | 参数三例 | 时序（`param-override` 的 180 ps 边沿上晚 50 ps，`param-endpoints-low` 的 90 ps 边沿上晚 35 ps，`param-endpoints-high` 的 180 ps 边沿上早 70 ps） |
| `sync_reset_events` | 复位只在泄漏时刻和 `sample` 上升时读取（原 v4:042 gold 的复位） | 复位六例 | `rst` 上升到下一泄漏时刻之间；不含事件的短复位脉冲完全无效 |
| `capture_in_reset` | `rst` 为高时照常捕获 | `base`、`reset-release` | 复位期间的捕获 |
| `capture_on_release` | `rst` 下降时若 `sample` 为高就捕获 | `base`、`reset-release` | 释放之后 |
| `reset_ignored` | 没有复位 | 复位六例 | 复位之后 |
| `falling_edge_capture` | 在 `sample` 下降沿捕获 | 全部 | 捕获时刻与值 |
| `track_while_high` | `sample` 为高时 `vout` 跟随 `vin`，下降沿保持 | 漏电六例 | `sample` 高电平期间 |
| `sample_deglitch_0p6n` | 低电平不足 0.6 ns 后的上升沿不捕获（比合同的 0.5 ns 更严） | `phase-grid`、`param-endpoints-low` | 0.525 ns、0.5008 ns 低电平之后那次捕获 |
| `initial_vin` | 初值取 vin(0)，且不理会 t = 0 时的复位电平 | 除 `phase-grid` 外的六例 | t = 0 起 |
| `capture_initial_high` | t = 0 时 `sample` 已高（`rst` 为低）就当作一次捕获，初值取 vin(0) | `start-high` | t = 0 到第一次真实上升穿越之间 |
| `late_arrival_1p3tr` | 过渡时间 1.3·tr，到达晚于评分起点 1.25·tr | 全部 | 评分起点后第一个点（300 mV 以上的捕获与清零） |
| `original_v4_042_gold` | 原 v4:042 gold 原样提交（模块名、端口与本题相同） | 复位六例 | 同 `sync_reset_events` |
| `historical_v4_1042_buggy` | 原 v4:1042 坏版原样提交：捕获存 0 V，decay 缺省 0.9 | 全部 | 捕获之后 |
| `alt_fast_output`（正确） | 过渡时间 0.2·tr | 无 | 无 |
| `alt_counter_grid`（正确） | 用绝对 timer 加更新计数实现同一泄漏网格，不用周期 timer | 无 | 无 |
| `alt_delayed_within_tr`（正确） | 延迟 0.2·tr 后用 0.8·tr 过渡，正好在 tr 到达 | 无（条件见下） | 无 |
| `margin_arrival_1p2tr`（用户已接受的余量） | 过渡时间 1.2·tr：晚于期限 tr，早于评分起点 1.25·tr | 无 | 无 |

漏电类候选在 `param-endpoints-high`（decay = 1）都与参考解相同，所以不被拒；`period_fixed_1n` 也因 decay = 1 而在该例不可见。`tr_fixed_500p` 在 `param-endpoints-high`（tr = 1 ns）比期限更快到达，合同允许。`tr_floor_100p` 在 tr 不小于 100 ps 的六个用例中与参考解相同，只在 `param-endpoints-low` 被拒。`capture_in_reset`、`capture_on_release` 只在有“复位期间的 `sample` 上升”或“`sample` 为高时释放复位”的 `base`、`reset-release` 被拒。`initial_vin` 在 `phase-grid` 不被拒：该例 vin(0) = 0。`capture_initial_high` 只在 t = 0 时 `sample` 已高的 `start-high` 被拒，其余六例 t = 0 时 `sample` 为低，它与参考解相同。`sample_deglitch_0p6n` 只在有短低电平的两例被拒，其余用例每次捕获前至少低 1.5 ns。

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- 全部条目：假定 `cross()` 事件定位在穿越时刻或稍后，`timer(0, leak_period)` 事件在 k·leak_period。泄漏时刻是输出网格行，每个 `sample` 上升穿越离泄漏时刻至少 50.35 ps（`param-endpoints-low`；`base`、`phase-grid` 为 52.5 ps），所以没有一条预期取决于捕获落在泄漏时刻的哪一侧；没有保存行恰在评分起点（某次变化后 1.25·tr）上。tr 不小于 100 ps 的用例容得下几 ps 的事件定位误差；`param-endpoints-low`（tr = 10 ps）要求在 0.5 ps 内：评分行在事件后 1.275·tr，`margin_arrival_1p2tr` 比它早 0.75 ps 到达。
- 过渡被打断：`base`（7 次）、`phase-grid`（11 次）、`reset-release`（6 次）、`param-override`（1 次）、`start-high`（2 次）有捕获后 52.5 ps（`param-override` 为 57.5 ps）就到泄漏时刻、清零落在泄漏斜坡中（泄漏时刻后 22.5–222.5 ps）、泄漏落在捕获斜坡中的情形。按 LRM 4.5.8 的完成规则，延迟为 0、上升与下降时间都是 tr、目标在事件之间不变的 `transition()` 在打断后 tr 内到达新值，所以这些用例不必排除打断；合成控制里“从当前值重走满 tr”的模型同样通过。
- `alt_delayed_within_tr`：用了 0.2·tr 的传输延迟，属于待发过渡。`base`、`phase-grid`（tr = 500 ps，延迟 100 ps）的捕获后 52.5 ps 到泄漏时刻，捕获的变化尚在待发，泄漏的变化随后排上。不论后端按 LRM 4.5.8 排队，还是用新变化替换待发变化，泄漏的目标已经含有捕获值，都在泄漏时刻后 tr 内到达。其余用例里，每次延迟的变化都在下一个事件之前开始。
- `margin_arrival_1p2tr`：不是正确模型，它晚于期限 tr 到达。按用户已确认的观察规则（F01，2026-10-28），评分起点前到达的输出不判错，这是已接受的余量。
- `late_arrival_1p3tr`：捕获和清零在 `base`、`phase-grid`、`reset-release`、`start-high` 落在 10 ps 网格行后 2.5 ps 或 7.5 ps，第一个评分行在事件后 1.255·tr 或 1.265·tr；`param-override` 落在 2 ps 网格行后 0.5 ps（1.255·tr），`param-endpoints-low` 落在 0.8 ps 网格行后 0.05 ps（1.275·tr），`param-endpoints-high` 落在 20 ps 网格行后 18 ps（1.262·tr）。没有保存行恰在评分起点上。每个用例至少有三次 300 mV 以上、有自己评分行的捕获或清零，1.3·tr 的到达在这些行上都超出 2 mV；被下一次泄漏在 1.25·tr 之前改写的捕获列为例外。泄漏时刻是网格行：`param-override` 中每次泄漏后的第一个评分行在 1.26·tr，`param-endpoints-low` 在 1.28·tr，已稳定的泄漏台阶在 65 mV（h 的 10 %）或 130 mV（h 的 50 %）以上时，1.3·tr 的到达在这一行超出 2 mV（`param-override` 3 个台阶，`param-endpoints-low` 11 个；合成控制 `leak-late-1p3tr` 只在这两例被拒）；缺省参数的四例在泄漏后 1.26·tr 也有评分行，但最大的泄漏台阶（h 的 1.5 %，14 mV）在窗口内任何一行都不能让 1.3·tr 的到达超出 2 mV，`param-endpoints-high` 没有泄漏变化（decay = 1）。
- `capture_initial_high`：t = 0 时 `sample` 高于 `vth`（`rst` 为低）就取 vin(0) 作为保持值。只有 `start-high` 在 t = 0 时 `sample` 为高（vin 为 0.6 V，第一次上升穿越在 5.3225 ns），所以只有它拒绝这个候选。
- `continuous_leak`、`track_while_high`：用了不经 `transition()` 的直接贡献，前者含 `$abstime`。
- `original_v4_042_gold`、`historical_v4_1042_buggy`：不是为本题写的。`mutants.py` 只在仓库内运行时从 `benchmark/material/historyref` 按原字节读取。原 gold 的模块名、端口与本题相同，原样可用；它的复位是事件同步的，与 `sync_reset_events` 行为相同。v4:542 的五个历史负例与 1042 坏版实际改动相同（捕获存 0 V、decay 缺省 0.9），只差注释，不另列。

合成控制的对应范围：`expected.json` 的 `author_synthetic_control` 是作者证据中对应的 Python 合成控制；`original_v4_042_gold` 对应 `sync-reset-events`，`historical_v4_1042_buggy` 没有合成控制。

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：旧版跑不了两个候选，`tr_floor_100p`（`transition()` 的时间参数里用 `max()`）和 `track_while_high`（`tracking*V(vin) + (1 − tracking)*smooth` 的混合贡献），都报 `ERROR [rust_lowering]: … timer_static_linear_specialized_path_preferred`。这是旧版的局限，不是候选的错误。`tr_floor_100p` 另有旧版能跑的探针 `tr_floor_100p_param`（把 `max(tr, 100p)` 放进参数），单独记账，不在本目录；`track_while_high` 没有旧版能跑的探针，待 Spectre 验证。旧版运行结果记在作者证据中，不改变这张表。
