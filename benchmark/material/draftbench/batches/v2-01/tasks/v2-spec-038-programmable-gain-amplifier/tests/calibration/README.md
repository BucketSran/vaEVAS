# 校准候选（F01 评分起点）

Spectre 校准待做，本目录的内容都未在 Spectre 上仿真。`mutants.py` 从 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

checker 只有一种失败：某个评分点上输出与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）；另外，`metric` 在其不评分区内低于 −2 mV 或高于 0.902 V 记 `metric_overshoot`（`:202-203`）。本题不适用 `tests/v2_spec.py:188`：`out` 从 t = 0 起每个保存点都评分（`:196`）；`metric` 在其目标每次改变后 `1.15*tr` 内不评分（`:197-201`）。`metric` 目标改变的时刻（`:154-181`）是：`rst` 低时未钳位目标 `vcm + gain*(V(vin) - vcm)`（`V(vin)` 在保存点间线性插值）穿越 `vmin` 或 `vmax` 的时刻，以及改变它的 `rst` 穿越与 `clk` 上升穿越；初始目标为高时 t = 0 也算。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_metric_transition_1p3tr` | `metric` 的过渡由 `tr` 拉到 `1.3*tr`，在目标改变后的评分起点 `1.15*tr` 之后才到值 | 全部用例 | 目标改变后 `1.15*tr` 起的 `metric` 评分点仍在过渡中 |
| `inwindow_metric_transition_1p1tr`（正确） | 过渡 `1.1*tr`，到值时刻在期限 `tr` 与评分起点之间，属于用户已接受的余量 | 无 | 无 |

`out` 是连续输出，两个候选都不改它。

开发证据（不是校准结论）在 `runs/t3-batch2-20261027/f01-r1/`：合成控制（未仿真，旧版参考波形在内存中推迟或提前后由本题 checker 判定）见 `synthetic-controls.json`，旧版 EVAS 0.8.7 运行见 `legacy-runs.json`。旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。
