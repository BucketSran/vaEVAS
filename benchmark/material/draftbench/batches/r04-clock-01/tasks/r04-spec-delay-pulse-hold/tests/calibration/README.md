# 校准候选

Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。这些是作者校准样本，不计入终评，也不进入求解环境。

在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。

[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本。矩阵按 Verilog-A LRM 2.4 的 `cross()`、`timer()`、`transition()` 语义和同一时刻事件语句的源码次序写成，是预期，不是结果；每个条目都待 Spectre 校准。只在某种后端语义下成立的条目写在 `conditions`。

## checker 的失败类别

- `hold`：两沿之间 `out_clk` 离预期电平超过 2 mV。`state` 字段给出第一个错误采样点时单元处于 `loaded`、`unloaded` 还是 `reset`。
- `edge`：过渡窗口超出 `vss` 到 `vdd` 的带宽，或回头超过 2 mV。相邻两沿的窗口重叠时（只在 `tr` 小于 4/3 ps 时出现），合成一个窗口：其中的保存点要能由各沿按顺序解释，每个沿单调、只在自己的窗口里移动，转向只能发生在下一沿的窗口开始之后。fix-r1 加入窗口合并，fix-r2 加入逐沿的时刻约束（审核 R2-01）。

过渡形状类错误（过冲、过渡中回头、保持中的毛刺）由作者证据里的 Python 合成轨迹覆盖，没有对应的 VA 候选。4 ps 过渡（`parameter-override`）和 1 ps 过渡（`minimum-tr-pulses`）里的回头小于 2 ps 网格，观察不到。

`minimum-tr-pulses` 里 4 1/8 ps（比 `4*tr` 长 1/8 ps，fix-r5 留的余量）的脉冲两沿窗口重叠，按上面的合并规则检查。两沿都落在相邻保存点之间的脉冲看不到，脉冲是否出现不单独判定；8 ps 的脉冲在高电平留有评分的网格行。所以一直为低的输出在该用例的 4 1/8 ps 脉冲上看不出，靠 8 ps 脉冲和其余用例拒绝。网格上看得见的迟到压窄脉冲被拒，没有对应的 VA 候选，由作者证据里的合成控制覆盖（fix-r2，审核 N01、N02）。

## 候选与应拒用例

用例简称：A `contract-base`，B `reset-and-initial`，C `long-delay-overlap`，D `parameter-override`，E `self-loading-burst`，F `minimum-tr-pulses`。

| 候选 | 行为 | 应拒用例 | 预期失败类别 |
| --- | --- | --- | --- |
| `per_edge_latch` | 下降沿取到达时已装载的码（历史规则） | A、C、D | `hold`，loaded |
| `single_slot` | 只有一个待发槽，下降沿覆盖尚未输出的上升沿 | 所有用例 | `hold`，loaded |
| `rise_clears_pending_fall` | 被接受的上升沿丢掉上一脉冲待发的下降沿 | A、C、D、E | `hold`，loaded |
| `fall_time_from_current_delay` | 下降沿按延迟变量定时，下一个被接受的脉冲会改写它 | A、C、D、E | `hold`，loaded |
| `retime_on_load` | 待发沿按输入穿越时刻加“现在装载的码”重新定时 | 所有用例 | `hold`，loaded |
| `reset_gate_only` | 复位只屏蔽在 `rst` 为高期间到期的沿 | A、B、C | `hold`，unloaded（释放后出现的沿） |
| `reset_no_force_low` | 复位取消待发沿，但不把为高的 `out_clk` 拉低 | A、B、C、D | `hold`，reset |
| `reset_keeps_code` | 复位不卸载码 | A、D | `hold`，unloaded |
| `unloaded_code0` | 未加载时按码 0 延迟脉冲 | A、B、D | `hold`，unloaded |
| `load_during_reset` | `rst` 为高期间的 load 也生效 | B | `hold`，unloaded |
| `edge_first` | `in_clk` 语句写在 load 语句之前，同刻 load 从下一个脉冲才生效 | A、B、C、E | `hold`，loaded |
| `load_on_falling_edge` | 在 `load` 下降穿越时取码 | A、B、C、E | `hold`，loaded |
| `code_at_input_edge` | 延迟取 `in_clk` 上升穿越时的码位 | A | `hold`，loaded |
| `bit_order_reversed` | `code_0` 权重 32，`code_5` 权重 1 | 所有用例 | `hold`，部分用例还有 `edge` |
| `no_delay_min` | 延迟只有 `delay_lsb * code` | 所有用例 | `hold`，部分用例还有 `edge` |
| `fixed_vth` | 输入门限固定 0.45 V | D | `hold` |
| `fixed_levels` | 输出电平固定 0.9 V 和 0 V | D | `hold`、`edge` |
| `fixed_delay_params` | `delay_min`、`delay_lsb` 固定为 20 ps、3 ps | C、D | `hold` |
| `slow_output` | 输出过渡用 `2*tr` | A、B、C、D、E | `hold`；F 中 2 ps 过渡仍在 `tr + tau_t` 内，F 接受它 |
| `fixed_tr` | 输出过渡固定 10 ps | D、F | `hold`，F 中还有 `edge` |
| `centered_transition` | 斜坡以沿时刻为中点（50 % 延迟读法） | A、B、C、E | `hold`，loaded；D（`tr` = 4 ps）提前 2 ps 正好等于 `tau_t`，F 提前 0.5 ps，都接受 |
| `transport_reset_unchanged` | 用 `transition()` 传输延迟和锁存的脉冲延迟；复位把目标置低、延迟为 0，目标已为低时什么也不安排 | LRM：A、B、D、F；旧版 EVAS 还拒 C、E | `hold` |
| `historical_per_edge_transport` | 历史结构：`transition()` 传输延迟加逐沿延迟 | LRM：A、B、C、D、F；旧版 EVAS 还拒 E | `hold` |
| `alt_fifo_queue`（正确） | 已安排沿的队列，用一个定时器指向队首 | 无 | 无 |
| `alt_fast_output`（正确） | 时序正确，过渡用 `0.2*tr` | 无 | 无 |
| `alt_level_state`（正确） | 一个双向 `cross()`，按穿越跟踪输入电平 | 无 | 无 |

`alt_fast_output`、`alt_level_state` 只用标量状态，不用 `absdelay`。

两个传输延迟候选：LRM 4.5.8 保留所有排在新过渡之前的待发过渡；旧版 EVAS 0.8.7 改为用新变化替换待发变化，所以在窄脉冲用例里也拒绝它们。Spectre 的行为尚未记录，见 `expected.json` 的 `conditions`。

## 旧版 EVAS 不能运行的候选

- `alt_fifo_queue`：旧版 EVAS 0.8.7 不支持数组状态（`dynamic_state_array_access`），6 个用例都停在仿真前。矩阵条目按 LRM 预期保留，待 Spectre 校准。

## 旧版开发证据

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：除 `alt_fifo_queue` 外，25 个候选在 6 个用例上的 150 次判定中 147 次与矩阵一致，另 3 次是上面写明的旧版额外拒绝；只用网格行重判结论不变。命令、退出码和逐例结果见 `runs/t3-p0-pilot-20261027/fix-r1/disposition.json`。fix-r2 改 checker 后全部重跑，仿真输出与 fix-r1 逐字节相同，判定无变化，见 `runs/t3-p0-pilot-20261027/fix-r2/disposition.json`。旧版只给点值，不做可信证明，结果可能不准也不报错。
