# 校准候选

Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。`probe/` 里是一个数值诊断探针，不是校准候选，见下文。这些是作者校准样本，不计入终评，也不进入求解环境。fix-r1 按审核 F12 新建本目录。

在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。

[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本。矩阵按 Verilog-A LRM 2.4 的 `laplace_nd`/`laplace_np`（4.5.11）、`ddt()`、`transition()`、`cross()` 语义和本题 checker 写成，是预期，不是结果；每个条目都待 Spectre 校准。只在某种后端语义或条件下成立的条目写在 `conditions`。

## checker 的失败类别

只有一类：评分点上 `out` 离预期保持值超过 2 mV。失败记录的 `sample_event` 与 `reset_sample` 给出它属于哪一次采样。事件后 `1.25*tr` 内的点不评分，`tr` 内的波形形状由作者证据里的 Python 合成轨迹覆盖。

## 候选与应拒用例

“所有用例”指 `base`、`dc-start`、`tau-override`、`vth-tr-override` 共 4 个。

| 候选 | 行为 | 应拒用例 |
| --- | --- | --- |
| `sample_input_directly` | 采样 `V(vin)` 本身，不经滤波 | 所有用例 |
| `discrete_update_at_clock` | 只在 `clk` 上升沿按 `exp(-dt/tau)` 离散更新滤波值 | 所有用例 |
| `tau_from_cutoff` | 把 `tau` 当成 `1/(2*pi*fc)` 换算，时间常数缩小 `2*pi` 倍 | 所有用例 |
| `fixed_tau_100n` | 忽略 `tau`，固定 100 ns | `tau-override` |
| `zero_initial_state` | 滤波器从 0 起步，不与 `vin(0)` 平衡 | `dc-start`、`vth-tr-override` |
| `reset_restarts_filter` | 复位采样同时把滤波值清零 | 所有用例 |
| `filter_frozen_in_reset` | `rst` 为高期间滤波器停止更新 | 所有用例 |
| `asynchronous_reset` | `rst` 上升穿越时立即清零保持值 | 所有用例 |
| `transparent_output` | `out` 跟随滤波值，不保持 | 所有用例 |
| `one_sample_latency` | 保持值晚一次采样 | 所有用例 |
| `falling_edge_sample` | 在 `clk` 下降穿越采样 | 所有用例 |
| `clamp_at_zero` | 保持值夹在 0 V 以上 | 所有用例 |
| `slow_output` | 输出过渡用 `2*tr` | 所有用例 |
| `late_arrival_1p3tr` | 输出过渡用 `1.3*tr`，晚于评分起点到达（F01） | `vth-tr-override`；其余用例不设预期，见下 |
| `fixed_vth` | 门限固定 0.45 V（F08） | `vth-tr-override` |
| `fixed_tr` | 输出过渡固定 200 ps（F08） | `vth-tr-override` |
| `alt_ddt_node`（正确） | 内部节点 `I(ynode) <+ V(ynode) - V(vin) + ddt(tau*V(ynode))` | 无 |
| `alt_laplace_np`（正确） | 同一传递函数的零极点形式 `laplace_np(V(vin), {1.0}, {-1.0/tau, 0.0})`，即 v3:438 的写法 | 无 |
| `alt_fast_output`（正确） | 采样正确，过渡用 `0.2*tr` | 无 |

`zero_initial_state`、`reset_restarts_filter`、`filter_frozen_in_reset` 建立在下面的标量递推上，旧版 EVAS 能直接运行。四个固定用例的 `vin` 拐点都在 25 ps 格点上，递推在这些用例上是精确的，被拒只来自各自的缺陷；`zero_initial_state` 在 `base`、`tau-override` 上的接受预期依赖这一点，写在 `expected.json` 的 `conditions`。

## 数值诊断探针 `probe_step_recursion_25p`

`probe/probe_step_recursion_25p.va` 只用标量状态，不用 `absdelay`，也不用模拟算子：每 25 ps 按 `vin` 线性的精确一阶响应更新一次，采样时从上一次更新外推，平衡起步。fix-r1 把它登记为正确候选 `alt_step_recursion`；fix-r2 按审核 R2-03 改为只对固定台架有效的数值诊断探针，移出 `correct/` 和 `expected.json` 的候选表，单独记账。源码未变。

它只在 25 ps 格点和采样时刻读 `vin`，两次读数之间按直线处理。合同允许 `vin` 在任意时刻变化，没有带宽或斜率限制，读数之间的变化它看不到。作者证据（fix-r2，合成轨迹与旧版运行结果一致）：`vin` 在每个 25 ps 格点为 0、两格点中间为 1 V 的三角波，探针始终读到 0，10 ns 采样时误差 47.6 mV，三次采样后增大到 197 mV；振幅 0.1 V 时误差仍有 4.8 mV。单个拐点落在格点之间的阶跃只留下约 0.01 mV 的一次性误差。所以 fix-r1 这里写的“拐点不在格点上时，单步误差也远小于 2 mV”只对孤立拐点成立，对锁定在格点上的周期输入不成立。

样板要求 `correct/` 至少有一个旧版 EVAS 能运行的正确替代实现，本题找不到这样的实现（试点 r3 审核 R3-01 后改准的说法）。correct 组里的连续算子版本本身只用标量 real，问题不在状态类型，而在旧版不支持的算子。连续滤波合同要对任意合法的 `vin` 成立：只在事件语句（`timer`、`cross`）里更新的标量状态只在有限个时刻读 `vin`，会漏掉读数之间的变化；在连续语句里逐步更新状态，又依赖仿真器何时、按什么次序求值模拟块（包括被拒的时间步和重复迭代），LRM 不保证。满足合同的写法都要用模拟算子或内部节点（`laplace_nd`、`laplace_np`、`ddt`），旧版 EVAS 0.8.7 都不能降低，所以本题的正确候选都没有旧版结果。

`late_arrival_1p3tr` 的预期只设在 `vth-tr-override`：该用例的 0.8 V 穿越比 25 ps 网格行早 2.5 ps，每个事件后 127.5 ps 有一个评分行，落在 `(1.25*tr, 1.3*tr)` 内，`1.3*tr` 的输出在那里还没到。其余用例的事件在 50 ps 网格上，到达前唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，因此不放进 `must_reject` 也不放进 `must_accept`。评分起点已于 2026-10-28 由用户确认：题面写明实际观察起点，checker 不动。超时 20 % 的输出（`1.2*tr`）在期限与评分起点之间到达，通过全部用例，这是用户已接受的余量；`1.3*tr` 的输出在评分起点之后才到达，是迟到负例。

## 旧版 EVAS 不能运行的候选

旧版 EVAS 0.8.7 不能降低带参数系数的 `laplace_nd`/`laplace_np`，也不能降低 `ddt()` 内部节点，报 `ERROR [rust_lowering]: model:0:ct_lowpass_sampler_Model:continuous_body_not_lowered`。参考解本身也因此不能在旧版上运行。不能运行的候选：

- 用参考解滤波器的 13 个：`sample_input_directly`、`tau_from_cutoff`、`asynchronous_reset`、`transparent_output`、`one_sample_latency`、`falling_edge_sample`、`clamp_at_zero`、`slow_output`、`late_arrival_1p3tr`、`fixed_vth`、`fixed_tr`、`alt_fast_output`、`alt_laplace_np`；
- `alt_ddt_node`。

这些候选的矩阵条目按 LRM 预期保留，待 Spectre 校准。诊断用的探针把 `tau` 换成常数 100n，只在 `tau` = 100 ns 的 `base`、`dc-start`、`vth-tr-override` 上跑；探针不是候选本身的结果。12 个探针的 36 次判定中 34 次与矩阵一致，另 2 次是 `late_arrival_1p3tr` 在不设预期的网格边界用例上（旧版上被拒）；`tau_from_cutoff` 和 `alt_laplace_np` 的常数探针仍不能降低。

能直接运行的 5 个候选（`discrete_update_at_clock`、`fixed_tau_100n`、`zero_initial_state`、`reset_restarts_filter`、`filter_frozen_in_reset`）在 4 个用例上的 20 次判定都与矩阵一致。旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；命令、退出码和逐例结果见 `runs/t3-p0-pilot-20261027/fix-r1/disposition.json`。旧版只给点值，不做可信证明，结果可能不准也不报错。

探针 `probe_step_recursion_25p` 单独记账，同样是旧版开发证据，待 Spectre 复跑：fix-r1 的旧版运行（源码与现在逐字节相同）在 4 个固定用例上都接受它。fix-r2 在临时题包上加了三个越格输入控制，不进本题用例：探针在两个三角波控制上被拒（10 ns 误差 47.6 mV；三次采样为 47.6、129.6、196.7 mV），在孤立阶跃控制上通过；常数系数参考探针三个都通过。命令与结果见 `runs/t3-p0-pilot-20261027/fix-r2/disposition.json`。
