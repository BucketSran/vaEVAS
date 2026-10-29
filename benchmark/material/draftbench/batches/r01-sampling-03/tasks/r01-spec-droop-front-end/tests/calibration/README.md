# 校准候选

未仿真：本题尚无 Spectre 运行，Spectre 校准待做。`mutants.py` 从 `solution/circuit.va` 生成具体 VA 候选：`wrong/` 应被拒，`correct/` 应被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不属于终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <空输出目录>`。`expected.json` 是同一张被拒矩阵的机器可读版本。

每个候选都是完整的单文件。checker 只有一类失败：某个评分点上 `vout`、`valid` 或 `coarse` 与期望值相差超过 2 mV；该输出的期望值一次变化超过 0.1 mV（题面写明的门限 δ）时，其后 1.25·trf 内的点不评分，不超过 0.1 mV 的变化不开窗。失败记录里的 `node`、`change_time` 和 `cause` 指出它属于哪个事件：`sample n`、`end of valid pulse n` 或 `droop update at … ns`。没有触发的记录照常评分（输出保持初态）；台架义务不满足时（包括 `clk` 的电平转移长于 200 ps：checker 用离两电平都超过 1 mV 的保存行给出转移长度的下界），checker 报错、不判分。输出形状和容差边界由作者证据中的 Python 合成轨迹覆盖。参数端点由终评用例 `param-endpoints-low`（vth 0.2 V、trf 10 ps、tau 10 ns、dt 0.2 ns、taperture 20 ps、valid_width 0.5 ns）与 `param-endpoints-high`（vth 0.7 V、trf 200 ps、tau 1 us、dt 5 ns、taperture 2 ns、valid_width 10 ns）覆盖；`clk` 的最短合法相位（1.002 ns，1 ns 下界加一个 2 ps 网格步）和离下垂更新最近的采样（50.75 ps）在 `param-endpoints-low`，短于孔径的时钟高电平（采样时 `clk` 已回到低电平）在 `param-override` 与 `interrupt`，t = 0 时 `clk` 已高在 `start-high`，被打断的输出过渡在 `interrupt`。

预期判决按 Verilog-A LRM 2.4 的 5.10.3.1 `cross`、5.10.3.3 `timer`、4.5.8 `transition`、5.10.2 `initial_step` 写出。合同要求 `clk` 穿越与采样时刻离任一下垂更新时刻至少 50 ps（用例实际至少 50.75 ps），采样时刻前后 trf/4 内 `vin` 变化小于 0.25 mV，采样值离 `vth` 至少 5 mV（用例实际至少 20 mV），所以事件定位误差在几 ps 内时判决不变。

列中用例简称：
- 默认三例：`base`、`rails-reference`、`phase-grid`，参数都取缺省（`start-high` 也取缺省参数，单列）；
- 参数四例：`param-override`（vth 0.25 V、trf 100 ps、tau 10 ns、dt 2 ns、taperture 1.5 ns、valid_width 4 ns）、`param-endpoints-low`、`param-endpoints-high`、`interrupt`（trf 200 ps、tau 10 ns、dt 1 ns、taperture 1.5 ns、valid_width 0.5 ns，vth 取缺省）；
- 钳位四例：`base`、`rails-reference`、`param-override`、`param-endpoints-high`，有超出电源轨的采样；
- 全部：八个用例。

| 候选 | 行为 | 必须拒绝的用例 | 失败类别 |
| --- | --- | --- | --- |
| `no_aperture` | 在触发沿立即采样（v4:600 neg_004 的实际改动） | 全部 | 孔径内改变的 `vin` |
| `falling_trigger` | 用 `clk` 下降沿触发 | 全部 | 时序 |
| `need_clk_high` | 采样时刻 `clk` 已低就不采样 | `param-override`、`interrupt` | 时钟高电平短于孔径的采样 |
| `no_clamp` | 不钳位 | 钳位四例 | 钳位样本 |
| `upper_clamp_only` | 只钳到 vdd | `base`、`rails-reference` | 低于 vss 的样本 |
| `lower_clamp_only` | 只钳到 vss | 钳位四例 | 高于 vdd 的样本 |
| `span_fixed_0p9` | 轨间跨度写死 0.9 V（钳位上限与高电平都在 vss 上方 0.9 V） | `base`、`rails-reference`、`param-override` | vdd 改变后的钳位与高电平 |
| `rails_at_t0` | 在 t = 0 锁存电源轨 | `base`、`rails-reference`、`param-override` | vdd 改变后的钳位与高电平 |
| `rails_at_trigger` | 在触发沿读电源轨 | `param-override` | 孔径窗口内 vdd 改变后的那次采样 |
| `ground_threshold` | 时钟与下垂判定门限相对地 | `rails-reference` | 时序（200 ps 边沿上早 33 ps） |
| `decision_from_ground` | `coarse` 比较对地的保持值 | `rails-reference` | `coarse` |
| `droop_toward_ground` | 下垂趋向 0 V 而不是 vss | `rails-reference` | 下垂段 |
| `levels_fixed_0p9` | `valid`、`coarse` 高电平写死 vss 上方 0.9 V | `base`、`rails-reference`、`param-override` | 高电平 |
| `low_level_zero` | `valid`、`coarse` 对地驱动，低电平 0 V | `rails-reference` | 低电平（vss = 0.15 V） |
| `coarse_follows_vout` | 每次下垂更新后重新判 `coarse` | `base`、`rails-reference`、`param-override`、`interrupt` | 下垂穿过 vth 之后的 `coarse` |
| `valid_from_trigger` | `valid` 在触发沿升起 | 全部 | `valid` 时序 |
| `valid_on_droop_grid` | `valid` 在 c_k + valid_width 之后的第一个下垂更新时刻才落（原 v4:100 gold 的写法） | 全部 | `valid` 下降 |
| `no_droop` | 不下垂 | 全部 | 下垂段 |
| `droop_always` | 时钟高电平时也下垂 | 全部 | 高电平期间 |
| `droop_fall_anchored` | 下垂网格从每个时钟下降沿起算 | 全部 | 下垂台阶的时刻 |
| `continuous_droop` | 时钟低电平期间连续指数下垂 | 全部（条件见下） | 下垂台阶之间 |
| `euler_factor` | 每步乘 1 − dt/tau | `param-override`、`interrupt` | 下垂段（dt/tau = 0.2、0.1） |
| `vth_fixed_0p45` | 门限写死 0.45 V | `param-override`、`param-endpoints-low`、`param-endpoints-high` | 时序与 `coarse` |
| `vth_default_0p57` | vth 缺省改为 0.57 V（v4:600 neg_002 去掉输出缩放的部分） | 默认三例 | 时序与 `coarse` |
| `trf_fixed_40p` | 过渡时间写死 40 ps | `param-endpoints-low` | 1.25·trf 时未到达（trf = 10 ps） |
| `trf_floor_20p` | 过渡时间钳到 max(trf, 20 ps)（U17R1-01 的模式） | `param-endpoints-low` | 1.25·trf 时未到达 |
| `tau_fixed_90n` | tau 写死 90 ns | 参数四例 | 下垂段 |
| `dt_fixed_0p5n` | dt 写死 0.5 ns | 参数四例 | 下垂段 |
| `taperture_fixed_200p` | 孔径写死 200 ps | 参数四例 | 采样时刻 |
| `valid_width_fixed_2n` | valid_width 写死 2 ns | 参数四例 | `valid` 下降 |
| `late_arrival_1p3trf` | 过渡时间 1.3·trf，到达晚于评分起点 1.25·trf | 全部 | 评分起点后第一个点 |
| `output_scale_0p42` | `vout`、`valid` 乘 0.42（v4:600 neg_005） | 全部 | 电平 |
| `zero_outputs` | 三个输出都对地为 0 V（v4:600 neg_001） | 全部 | 电平 |
| `initial_vin` | 初值取 vin(0) − vss | 全部 | 首次采样前的 `vout` |
| `trigger_initial_high` | t = 0 时 `clk` 已高就当作一次触发，在 taperture 采样 | `start-high` | 首次真实触发前的三个输出 |
| `droop_after_ramp` | `vout` 的新目标若在上一段斜坡进行中到来，等斜坡结束 1 ps 后才开始新斜坡 | `interrupt` | 下垂更新后 1.26·trf 起的评分行 |
| `original_v4_100_gold` | 原 v4:100 gold，只改模块名 | 全部 | 同 `valid_on_droop_grid` |
| `historical_v4_1100_buggy` | 原 v4:1100 坏版，只改模块名：下降沿触发，`vout`、`valid` 乘 0.42 | 全部 | 时序与电平 |
| `alt_fast_output`（正确） | 过渡时间 0.2·trf | 无 | 无 |
| `alt_delayed_within_trf`（正确） | 延迟 0.2·trf 后用 0.8·trf 过渡，正好在 trf 到达 | 无（条件见下） | 无 |
| `alt_following_levels`（正确） | `valid`、`coarse` 写成 V(vdd, vss) 乘 0/1 的 `transition()` | 无（条件见下） | 无 |
| `alt_counter_grid`（正确） | 用绝对 timer 加计数器实现同一下垂网格 | 无 | 无 |
| `margin_arrival_1p2trf`（用户已接受的余量） | 过渡时间 1.2·trf：晚于期限 trf，早于评分起点 1.25·trf | 无 | 无 |

只在部分用例被拒的候选，在其余用例与参考解相同：`need_clk_high` 只有 `param-override` 与 `interrupt` 有采样时 `clk` 已低的情形；`rails_at_trigger` 只有 `param-override` 在孔径窗口内改 vdd；参照系三项与 `low_level_zero` 只有 `rails-reference` 的 vss 不为 0；`euler_factor` 在缺省参数下每步只差 1.5e-5，只有 dt/tau 为 0.2 的 `param-override` 与 0.1 的 `interrupt` 看得出；`trf_fixed_40p` 在 trf 为 100 ps、200 ps 的用例中比期限更快到达，合同允许；`vth_default_0p57` 只改缺省值，参数用例覆盖了 vth，`start-high` 与 `interrupt` 的判定离门限都远；`trigger_initial_high` 只有 `start-high` 在 t = 0 时 `clk` 已高；`droop_after_ramp` 只有 `interrupt` 有在斜坡进行中到来的新目标。`phase-grid`、`param-endpoints-low`、`start-high`、`interrupt` 没有超出电源轨的采样，所以不拒钳位类候选。

按后端语义成立的条目（`expected.json` 的 `conditions`）：

- 全部条目：假定 `cross()` 事件定位在穿越时刻或稍后，`timer()` 事件在设定时刻或稍后。trf 不小于 40 ps 的用例容得下几 ps；`param-endpoints-low`（trf = 10 ps）要求在 0.5 ps 内。`clk` 穿越与采样时刻离下垂更新至少 50.75 ps（`param-endpoints-low`；缺省参数的用例为 53 ps，`interrupt` 为 55 ps），没有一条预期取决于事件落在更新时刻的哪一侧；没有一行恰在门限穿越上，也没有一行恰在某次变化后 1.25·trf 的评分起点上。
- `continuous_droop`：缺省参数下连续律与离散更新最多差一个台阶（h 的 0.55 %，约 4 mV）；合成控制中默认三例与 `param-endpoints-high` 以 3.7–4.3 mV 拒绝，约为 atol 的两倍，`start-high` 以 2.7 mV 拒绝；`param-override`（tau 10 ns、dt 2 ns）以 145 mV 拒绝，`interrupt`（tau 10 ns、dt 1 ns）以 52 mV 拒绝，`param-endpoints-low` 以 10 mV 拒绝。
- 过渡被打断（按最终事件清单）：只有 `interrupt` 打断正在进行的输出过渡，都在 `vout` 上：采样后 55 ps（0.275·trf）与 95 ps（0.475·trf）的下垂更新同向改写 200 ps 的采样斜坡（0.8 V、0.3 V 两次采样），195 ps（0.975·trf）的一次反向改写（0.9 V 采样）。其余用例中同一输出两次变化至少相隔 1.775·trf（`param-override` 的 `vout`）。按 LRM 4.5.8 的完成规则，延迟为 0、上升下降时间相等的 `transition()` 在打断后 trf 内到达新值，合成控制里“从当前值重走满 trf”的模型同样通过；`droop_after_ramp` 等采样斜坡结束才开始下垂台阶，在前两次更新后的第一批评分行（1.26·trf）上仍在移动，被拒。
- `alt_delayed_within_trf`：用了 0.2·trf 的传输延迟，属于待发过渡。除 `interrupt` 外同一输出两次变化至少相隔 1.775·trf；`interrupt` 中下垂更新最早在采样后 0.275·trf 到来，延迟的采样变化那时已经开始，没有待发变化被新变化覆盖，被打断的斜坡按 LRM 4.5.8 在更新后 trf 内到达。
- `alt_following_levels`：`valid`、`coarse` 写成 `V(vdd, vss)` 乘 0/1 的 `transition()`。合法输入保证 `valid` 或 `coarse` 为高时 vdd 不变，所以与在采样时刻锁存电平的参考解相同。
- `valid_on_droop_grid`：原 v4:100 的写法，在下垂 timer 里比较 `$abstime` 与结束时刻。用例中结束时刻离下垂更新至少 6.75 ps（`param-endpoints-low`），比较不在平局上。
- `margin_arrival_1p2trf`：不是正确模型，它晚于期限 trf 到达。按用户已确认的观察规则（F01，2026-10-28），评分起点前到达的输出不判错，这是已接受的余量。
- `late_arrival_1p3trf`：每个采样时刻和 `valid` 结束都落在网格行之后的固定相位：8 ps 网格行后 5 ps（`base`、`rails-reference`、`phase-grid`、`start-high`），2 ps 网格行后 0.5 ps（`param-override`），2 ps 网格行后 1.25 ps（`param-endpoints-low`），4 ps 网格行后 1 ps（`interrupt`），40 ps 网格行后 24 ps（`param-endpoints-high`），所以其后第一个评分行在 1.275·trf（`param-override` 与 `interrupt` 为 1.255·trf，`param-endpoints-high` 为 1.28·trf）；没有一行恰在评分起点上。除 `interrupt` 中被下垂更新在 1.25·trf 之前改写的采样（列为例外）外，每次采样与 `valid` 变化都有自己在 (1.25·trf, 1.3·trf) 内的评分行，1.3·trf 的到达在这些行上对 104 mV 以上的变化（1.255·trf 处为 58 mV，1.28·trf 处为 130 mV）都超出 2 mV；`valid`、`coarse` 的每次变化都在 0.8 V 以上。下垂更新：`param-override` 与 `interrupt` 中每次更新后的第一个评分行在 1.26·trf，已稳定的下垂台阶在 65 mV 以上时，1.3·trf 的到达在这一行超出 2 mV（`param-override` 11 个台阶，`interrupt` 3 个；合成控制 `droop-late-1p3trf` 只在这两例被拒）；其余用例的更新落在 8 ps 网格行上或行后 4 ps（第一个评分行 1.3·trf 或 1.4·trf），或落在 2 ps、40 ps 网格行上（1.4·trf），列为例外：它们最大的下垂台阶（缺省参数约 5 mV，`param-endpoints-low` 17 mV，`param-endpoints-high` 4.5 mV）在窗口内任何一行都不能让 1.3·trf 的到达超出 2 mV。
- `trigger_initial_high`：t = 0 时 `clk` 高于门限就当作一次触发。只有 `start-high` 在 t = 0 时 `clk` 为高（vin 为 0.7 V，第一次下降穿越在 2.333 ns，第一次触发在 5.109 ns），所以只有它拒绝这个候选。
- `droop_after_ramp`：新目标在 `vout` 斜坡进行中到来时，等斜坡结束后 1 ps 才开始新斜坡；1 ps 让改写离开斜坡终点，不落在平局判据第 2 种情形上。只有 `interrupt` 有这样的新目标，合成控制在 5.252 ns 以 35.8 mV 拒绝；其余用例中它与参考解相同。
- `original_v4_100_gold`、`historical_v4_1100_buggy`：不是为本题写的。`mutants.py` 只在仓库内运行时从 `benchmark/material/historyref` 读取原字节，只把模块名 `sample_hold_droop_ref` 改成本题的 `sample_hold_droop`。原 gold 的 `valid` 在下垂网格上结束，与 `valid_on_droop_grid` 行为相同。

合成控制的对应范围：`expected.json` 的 `author_synthetic_control` 是作者证据中对应的 Python 合成控制；`original_v4_100_gold` 对应 `valid-on-droop-grid`，`droop_after_ramp` 对应 `wait-old-ramp`，`historical_v4_1100_buggy` 没有合成控制。

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：旧版运行结果记在作者证据中，不改变这张表。
