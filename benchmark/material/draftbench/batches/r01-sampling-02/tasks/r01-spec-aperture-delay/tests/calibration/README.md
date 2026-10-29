# 校准候选

Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。这些是作者校准样本，不计入终评，也不进入求解环境。

在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。

[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本。矩阵按 Verilog-A LRM 2.4 的 `cross()`、`above()`、`timer()`、`transition()` 语义写成，是预期，不是结果；每个条目都待 Spectre 校准。只在某种后端语义下成立的条目写在 `conditions`。

## checker 的失败类别

- `initial_hold`、`hold`：保持区间里有 `vout` 采样点离接受带的每个值都超过 2 mV。初值的保持区间总包含时刻 0。
- `transition_bound`：过渡窗口里有采样点超出“正在离开的值与新接受带”所张区间 2 mV 以上。
- `transition_not_monotone`：`c_k + tau_t` 之后回头超过 2 mV。
- `transition_direction`：捕获时刻附近的输出整体在新接受带一侧之外，输出却朝反方向单调移动。fix-r1 加入。

过渡形状类错误（过冲、过渡中回头、保持中的毛刺、被打断后朝反方向移动）另由作者证据里的 Python 合成轨迹覆盖，没有对应的 VA 候选。

## 候选与应拒用例

“所有用例”指 `contract-base`、`rails-and-supplies`、`parameter-override`、`short-aperture-burst`、`initial-high-clock`、`interrupted-transitions`、`early-first-capture` 共 7 个。

| 候选 | 行为 | 应拒用例 | 预期失败类别 |
| --- | --- | --- | --- |
| `edge_read_delayed_output` | 在触发沿读入 `vin`，只把输出推迟 `taperture` | 所有用例 | `hold` |
| `edge_sample_immediate` | 在触发沿读入并立即更新 | 所有用例 | `hold`、`initial_hold`（在 `c_k` 之前就移动） |
| `read_late_by_tedge` | 在 `c_k + tedge` 才读入 | 所有用例 | `hold`（`c_k + tedge + tau_t` 时还没到） |
| `fixed_aperture` | 忽略 `taperture`，固定 200 ps | `parameter-override`、`short-aperture-burst`、`interrupted-transitions`、`early-first-capture` | `hold` |
| `fixed_threshold` | 忽略 `vth`，固定 0.45 V | `parameter-override` | `hold` |
| `fixed_tedge` | 忽略 `tedge`，固定 50 ps | `short-aperture-burst`、`early-first-capture` | `hold`（还没到） |
| `slow_output` | 过渡用 `2*tedge` | 所有用例 | `hold`（还没到） |
| `init_zero` | 初始保持值为 0 V | 所有用例 | `initial_hold` |
| `clamp_rails` | 把保持值夹在电源之间 | `rails-and-supplies` | `initial_hold`、`hold` |
| `vss_referenced` | 保持 `vin - VSS` 并相对 `VSS` 输出 | `rails-and-supplies` | `hold`（随 `VSS` 移动） |
| `both_edges` | 下降穿越也触发 | 所有用例 | `hold` |
| `above_trigger` | 用 `above()`，0 时刻 `clk` 为高也触发 | `initial-high-clock` | `initial_hold` |
| `requires_clk_high` | `c_k` 时 `clk` 为低就跳过读入 | `contract-base`、`parameter-override`、`short-aperture-burst`、`interrupted-transitions` | `hold` |
| `periodic_timer` | 首次读入后每隔 `taperture` 重读 `vin` | 所有用例 | `hold` |
| `lockout` | 距上次接受的触发不足 `3*taperture` 的触发被忽略 | `contract-base`、`parameter-override`、`short-aperture-burst`、`interrupted-transitions` | `hold` |
| `continuous_track` | `vout` 跟随 `vin` | 所有用例 | `initial_hold`、`hold` |
| `drop_while_moving` | 输出还在过渡时到来的读入被丢弃（F04） | `interrupted-transitions` | `hold`（停在被丢弃前的值）、`transition_direction`（被丢弃的读入要求转向，输出仍朝旧值走） |
| `finish_then_turn` | 先走完正在进行的过渡，再走向期间读到的最新值（F03 的排队读法） | `interrupted-transitions` | `hold`、`transition_not_monotone` |
| `init_mid_supply` | 初始保持值取 `(V(VDD)+V(VSS))/2`，不取 `vin(0)`（F05） | 除 `short-aperture-burst`（其 `vin(0)` 正好 0.45 V）外的所有用例 | `initial_hold`；在 `early-first-capture` 只有时刻 0 的采样能发现它 |
| `alt_delayed_clock`（正确） | 用 `absdelay()` 把 `clk` 延迟 `taperture`，在延迟后的上升穿越读入 | 无 | 无 |
| `alt_fast_output`（正确） | 读入正确，过渡用 `0.2*tedge` | 无 | 无 |

`alt_fast_output` 只用标量状态，不用 `absdelay`。

新增用例的作用：

- `interrupted-transitions`：`taperture` 60 ps、`tedge` 200 ps、捕获间隔 120 ps，包含输出尚未到达时再次捕获以及连续两次打断（按 LRM 补全斜率，实际打断发生在 680、1680、1800 ps 的捕获），含先升后降；每组最后一次捕获之后有可观测的保持段。被打断的过渡按 LRM 4.5.8 的补全斜率规则运行，合成控制里的 `lrm_completion_slope` 通过。
- `early-first-capture`：首个触发在 1 ps、读入在 4 ps，早于 `tau_t`，初值只能由时刻 0 的采样判定。修正前的 checker 在这里放过 `init_mid_supply`。

## 旧版 EVAS 不能运行的候选

- `alt_delayed_clock`：旧版 EVAS 0.8.7 不支持 `absdelay()`，7 个用例都停在仿真前。矩阵条目按 LRM 预期保留，待 Spectre 校准。

## 旧版开发证据

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：除 `alt_delayed_clock` 外，20 个候选在 7 个用例上的 140 次判定都与矩阵一致，只用网格行重判结论不变。命令、退出码和逐例结果见 `runs/t3-p0-pilot-20261027/fix-r1/disposition.json`。旧版只给点值，不做可信证明，结果可能不准也不报错。
