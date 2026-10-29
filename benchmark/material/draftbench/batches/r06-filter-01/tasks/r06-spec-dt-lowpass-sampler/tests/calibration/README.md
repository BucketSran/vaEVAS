# 校准候选

Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。这些是作者校准样本，不计入终评，也不进入求解环境。在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本。

## checker 的失败类别

只有一类：评分点上 `out` 离预期保持值超过 2 mV。失败记录的 `sample_event` 与 `update_index` 给出它属于哪一次采样、哪一次滤波更新。采样事件后 `1.25*tr` 内的点不评分；`tr` 内的输出形状由作者证据里的 Python 合成轨迹覆盖。

## 语义依据

被拒预期按 Verilog-A LRM 2.4 的 4.5.11 与 4.5.12 写成，是预期，不是结果，每个条目都待 Spectre 校准。LRM 原文没有写定三处算子细节，待在 Spectre 上记录：zi 滤波器的起步状态（同一 `H(z)` 的 `zi_np` 在历史 Spectre 21.1 运行中从 DC 工作点起步）、`t0` 参数的作用、zi 过渡时间。旧版 EVAS 0.8.7 的 `zi_nd` 从零历史起步，忽略 `t0` 和 zi 过渡时间，也不能降低带参数系数的 `laplace_nd` 和两项分子的 zi。这些旧版结果记在作者证据里，不改变本表。

## 候选与应拒用例

“所有用例”指 `base`、`dc-start`、`tupdate-override`、`vth-tr-override` 共 4 个。

| 候选 | 行为 | 应拒用例 | 预期失败 |
| --- | --- | --- | --- |
| `continuous_same_pole` | 同极点的连续滤波器：`laplace_nd`，`tau = tupdate/ln(4/3)` | 所有用例 | `out` |
| `continuous_euler_tau` | 连续滤波器，`tau = 4*tupdate` | 所有用例 | `out` |
| `update_on_clock` | 递推在每次 `clk` 上升穿越时运行，不按内部网格 | 所有用例 | `out` |
| `one_period_delay` | 分子 `{0, 0.25}`：`y_k` 用 `x_(k-1)` | 所有用例 | `out` |
| `half_period_phase` | 更新时刻在 `(k + 1/2)*tupdate`（`t0 = tupdate/2`） | 所有用例 | `out` |
| `interpolated_between_updates` | zi 过渡时间取 `tupdate`：两次更新之间按斜坡变化 | 所有用例 | `out` |
| `swapped_coefficients` | `H(z) = 0.75/(1 - 0.25*z^-1)` | 所有用例 | `out` |
| `fixed_tupdate_100n` | 忽略 `tupdate`，固定 100 ns | `tupdate-override` | `out` |
| `zero_initial_state` | `y_(-1) = 0`，不取 t = 0 的 `V(vin)` | `dc-start`、`tupdate-override`、`vth-tr-override` | `out`（最初几次采样） |
| `reset_clears_filter` | 复位采样同时清掉滤波值 | 所有用例 | `out`（复位解除后） |
| `filter_frozen_in_reset` | `rst` 为高时跳过更新 | 所有用例 | `out`（复位解除后） |
| `asynchronous_reset` | `rst` 上升穿越时立即清保持值 | 所有用例 | `out` |
| `sample_input_directly` | 保持 `V(vin)` 本身，不经滤波 | 所有用例 | `out` |
| `transparent_output` | 两次采样之间 `out` 跟随滤波值 | 所有用例 | `out` |
| `falling_edge_sample` | 在 `clk` 下降穿越采样 | 所有用例 | `out` |
| `clamp_at_zero` | 保持值夹在 0 V 以上 | `base`、`tupdate-override`、`vth-tr-override` | `out`（负保持值） |
| `slow_output` | 输出过渡用 `2*tr` | 所有用例 | `out`（`1.25*tr` 时未到） |
| `late_arrival_1p3tr` | 输出过渡用 `1.3*tr`，在评分起点之后才到达 | `vth-tr-override`；其余用例不设预期，见下 | `out`（事件后 127.5 ps 的评分行） |
| `fixed_vth` | 门限固定 0.45 V（`clk` 穿越与 `rst` 读取都用它） | `vth-tr-override` | `out`（事件前的评分行） |
| `fixed_tr` | 输出过渡固定 200 ps | `vth-tr-override` | `out`（事件后 127.5 ps 的评分行） |
| `alt_timer_recursion`（正确） | 在 `@(timer(0, tupdate))` 上做标量递推，平衡起步，不用 zi 算子 | 无 | 无 |
| `alt_zi_nd`（正确） | 同一 `H(z)` 的分子分母形式 | 无，前提是 `zi_nd` 从 DC 工作点起步 | 无 |
| `alt_fast_output`（正确） | 采样正确，过渡用 `0.2*tr` | 无 | 无 |
| `margin_arrival_1p2tr`（用户已接受的余量） | 过渡用 `1.2*tr`：晚于期限 `tr`，早于评分起点 `1.25*tr` | 无 | 无 |

## 门限、过渡时间与迟到负例（p0-fix-a）

私有用例 `vth-tr-override` 按审核 F04 加入：`vth` 0.8 V，`tr` 100 ps，25 ps 网格，`clk` 边沿 180 ps，`tupdate` 用默认的 100 ns。每个采样穿越都比下一个网格行早 2.5 ps（在网格的 0.9 处），所以每个事件后 127.5 ps 有一个评分行，落在 `(1.25*tr, 1.3*tr)` 内。0.45 V 门限会提前 70 ps 采样，事件前 22.5 ps 和 47.5 ps 的评分行都落在这段提前量里。

- `late_arrival_1p3tr`：只在 `vth-tr-override` 设预期。30 次采样中保持值变化 13 次；其中 9 次变化超过 104 mV，`1.3*tr` 的输出在 127.5 ps 处偏差超过 2 mV；其余 4 次（25–90 mV）看不出，列为例外。`base`、`dc-start`、`tupdate-override` 的采样都在 50 ps 网格上，`1.3*tr` 之前唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，所以这三个用例既不放进 `must_reject`，也不放进 `must_accept`。
- `fixed_vth`：只能靠 `clk` 的穿越时刻暴露，13 次变化都看得出。`rst` 在每个采样时刻都处在 0 V 或 0.9 V，用错门限读取它不会改变采样结果。
- `fixed_tr`：200 ps 的过渡在 127.5 ps 处只走了 64 %，13 次变化都看得出。
- `margin_arrival_1p2tr` 不是正确模型，它晚于期限 `tr` 到达。按用户已确认的观察规则（F01，2026-10-28），评分起点之前到达的输出不判错，这是已接受的余量，所以它放在 `correct/`，4 个用例都应通过。

## 旧版 EVAS 不能运行或结果不同的候选

旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。旧版只给点值，不做可信证明，结果可能不准也不报错。

- 不能降低，没有旧版判定：`continuous_same_pole`、`continuous_euler_tau`（带参数系数的 `laplace_nd`）、`one_period_delay`（两项分子的 zi），报 `ERROR [rust_lowering]: model:0:dt_lowpass_sampler_Model:continuous_body_not_lowered`。作者证据里用常数系数或标量 timer 写的探针在全部 4 个用例上都被拒。
- 旧版结果与矩阵不同，原因是旧版语义：`half_period_phase`（旧版忽略 `t0`）、`interpolated_between_updates`（旧版忽略 zi 过渡时间）在旧版上通过，对应的标量 timer 探针在 4 个用例上都被拒；`alt_zi_nd` 在旧版上从零历史起步，在 `dc-start`、`tupdate-override`、`vth-tr-override` 上被拒。
- p0-fix-a 新增的 4 个候选在旧版上都与矩阵一致：`late_arrival_1p3tr` 在 `vth-tr-override` 上被拒（9.6 mV），在三个不设预期的网格边界用例上也被拒；`fixed_vth`、`fixed_tr` 只在 `vth-tr-override` 上被拒；`margin_arrival_1p2tr` 在 4 个用例上都通过。其余候选在 `vth-tr-override` 上的旧版判定也与矩阵一致。

命令、退出码和逐例结果见 `runs/t3-p0-build-20261027/r06-spec-dt-lowpass-sampler/checks.json` 与 `runs/t3-p0-build-20261027/p0-fix-a/disposition.json`。
