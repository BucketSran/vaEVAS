# 校准候选

Spectre 校准尚未进行。`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 里的候选应被拒，`correct/` 里的应被接受，判定都用同一个 checker 和 `../cases.json` 的固定用例。这些是作者校准样本，不计入终评，也不进入求解环境。fix-r1 按审核 F12 新建本目录。

在任意目录运行 `python3 -B mutants.py <输出目录>`，每次写到一个空目录。

[expected.json](expected.json) 是同一张被拒矩阵的机器可读版本。矩阵按 Verilog-A LRM 2.4 的 `cross()`、`transition()` 语义和本题 checker 写成，是预期，不是结果；每个条目都待 Spectre 校准。只在某种条件下成立的条目写在 `conditions`。

## checker 的失败类别

只有一类：评分点上 `pwm`、`duty_metric`、`soft_ref`、`pgood` 之一离上一采样事件后的预期状态超过 2 mV。失败记录的 `node` 给出输出，`sample_event` 与 `event_kind`（`initial`、`clear`、`update`）给出它属于哪一拍。事件后 `1.25*tr` 内的点不评分，`tr` 内的波形形状由作者证据里的 Python 合成轨迹覆盖。

## 候选与应拒用例

“所有用例”指 `base`、`vref-step-down`、`vss-offset`、`vth-tr-override`、`duty-endpoints` 共 5 个。

| 候选 | 行为 | 应拒用例 | 出错的输出（旧版运行所见） |
| --- | --- | --- | --- |
| `duty_up_new_soft` | `duty_up` 用本拍更新后的软参考 | 所有用例 | `duty_metric` |
| `duty_up_vs_vref` | `duty_up` 比较 `vfb` 与 `vref` | 所有用例 | `duty_metric`、`pwm` |
| `soft_overshoot` | 软参考按 `soft_step` 步进，不在 `vref` 处钳住 | 所有用例 | `soft_ref`，由此还有 `duty_metric`、`pwm` |
| `soft_jumps_down` | `vref` 低于软参考时直接跳到 `vref` | `vref-step-down` | `soft_ref` |
| `duty_step_25m` | duty 步长 0.025 | 所有用例 | `duty_metric`、`pwm` |
| `clamp_before_update` | 先夹位再步进，结果不再夹位 | 所有用例 | `duty_metric`、`pwm` |
| `duty_clear_to_min` | 上电与清零把 duty 置为 `duty_min` | 除 `duty-endpoints`（`duty_min` 为 0）外的所有用例 | `duty_metric` |
| `duty_metric_cleared_to_vss` | duty 为 0 时 `duty_metric` 输出 `vss` | `vss-offset` | `duty_metric` |
| `pwm_old_carrier` | 用载波加 1 之前的计数比较 | 所有用例 | `pwm` |
| `pwm_old_duty` | 用本拍更新前的 duty 比较 | `base`、`vref-step-down` | `pwm` |
| `pwm_less_or_equal` | `carrier <= 20*duty`，每个周期多一个高电平 | 所有用例 | `pwm` |
| `pwm_duty_latched_per_cycle` | 只在载波回到 0 时取 duty | `base`、`vref-step-down`、`vth-tr-override`、`duty-endpoints` | `pwm` |
| `carrier_kept_across_clear` | 清零不复位载波 | `base`、`vref-step-down`、`vss-offset`、`duty-endpoints` | `pwm` |
| `pgood_count_kept_across_clear` | 清零不复位 pgood 计数 | `vss-offset`、`vth-tr-override` | `pgood` |
| `enable_ignored` | `enable` 为低不清零 | 所有用例 | 四个输出 |
| `asynchronous_clear` | `rst` 上升或 `enable` 下降时立即清零 | 所有用例 | 四个输出 |
| `pgood_sticky` | 失去资格时计数不归零 | `base`、`vref-step-down`、`vss-offset` | `pgood` |
| `pgood_after_2` | 连续 2 拍即置 pgood | 除 `duty-endpoints` 外的所有用例 | `pgood` |
| `pgood_after_4` | 连续 4 拍才置 pgood | 除 `duty-endpoints` 外的所有用例 | `pgood` |
| `pgood_from_soft_done` | 软参考走到 `vref` 就算合格 | 所有用例 | `pgood` |
| `pgood_vfb_vs_soft` | 资格窗口以软参考为中心 | `vss-offset`、`vth-tr-override` | `pgood` |
| `falling_edge_sample` | 在 `clk` 下降穿越采样 | 所有用例 | 四个输出 |
| `one_edge_latency` | 输出显示上一拍的状态 | 所有用例 | 四个输出 |
| `late_arrival_1p3tr` | 四个输出都用 `1.3*tr` 过渡，晚于评分起点到达（F02） | `vth-tr-override`；其余用例不设预期，见下 | 四个输出 |
| `fixed_vth` | 门限固定 0.45 V（F08） | `vth-tr-override` | 四个输出（早 70 ps 移动） |
| `fixed_tr` | 过渡固定 200 ps（F08） | `vth-tr-override` | 四个输出（评分起点仍在过渡） |
| `endpoint_limits` | duty 始终限在 [0.05, 0.95]，不管 `duty_min`、`duty_max`（F07，审核 R07） | `duty-endpoints` | `duty_metric`、`pwm` |
| `min_on_time_at_wrap` | 载波回到 0 时 pwm 总为高，duty 0 时每周期多一个脉冲（F07） | `duty-endpoints` | `pwm` |
| `forced_off_state` | 载波为 19 时 pwm 总为低，duty 1 时每周期少一个脉冲（F07） | `duty-endpoints` | `pwm` |
| `alt_integer_duty`（正确） | duty 存成 0.05 的整数倍计数，`duty_metric` 输出 `0.05*n` | 无 | 无 |
| `alt_fast_output`（正确） | 状态正确，过渡用 `0.2*tr` | 无 | 无 |

两个正确候选都只用标量状态，不用 `absdelay`。原 5 文件 gold 所在的公开仓库没有 LICENSE，按复用边界只读参考，不作为候选放进本目录。

`late_arrival_1p3tr` 的预期只设在 `vth-tr-override`：该用例的 0.8 V 穿越比 25 ps 网格行早 2.5 ps，每个事件后 127.5 ps 有一个评分行，落在 `(1.25*tr, 1.3*tr)` 内，`1.3*tr` 的输出在那里还没到。其余用例的事件在 50 ps 网格上，到达前唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，因此不放进 `must_reject` 也不放进 `must_accept`。

评分起点已于 2026-10-28 由用户确认：题面写明实际观察起点，checker 不动。超时 20 % 的输出（`1.2*tr`）在期限与评分起点之间到达，通过全部用例，这是用户已接受的余量；`1.3*tr` 的输出在评分起点之后才到达，是迟到负例。

## 旧版 EVAS 不能运行的候选

无。旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：31 个候选在 5 个用例上的 155 次判定中，151 次与矩阵一致，另 4 次是上面不设预期的 `late_arrival_1p3tr` 网格边界用例（旧版上都被拒）；只用网格行重判结论不变。命令、退出码和逐例结果见 `runs/t3-p0-pilot-20261027/fix-r1/disposition.json`。旧版只给点值，不做可信证明，结果可能不准也不报错。
