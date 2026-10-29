# 校准候选（F01 评分起点）

Spectre 校准待做，本目录的内容都未在 Spectre 上仿真。`mutants.py` 从 三个参考文件 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

checker 只有一种失败：某个评分点上输出与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）。评分起点在 `tests/v2_spec.py:188`：t = 0 之后、以及任一输出目标改变的事件之后 `1.15*tr` 内的点，所有输出都不评分；其后保持区间内每个点都评分。消费者替身用例（`architecture-consumer`）由 `tests/v2_structure.py:19-34` 判定，从 t = 0 起每个保存点都评分。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_integrator_transition_1p3tr` | `integrator_state_cell` 的三个公开输出过渡拉到 `1.3*tr`，在评分起点 `1.15*tr` 之后才到值 | `contract-base`、`contract-stretched-input`、`architecture-component-consumer`、`architecture-producer` | 事件后 `1.15*tr` 起的评分点仍在过渡中 |
| `inwindow_integrator_transition_1p1tr`（正确） | 过渡 `1.1*tr`，到值时刻在期限 `tr` 与评分起点之间，属于用户已接受的余量 | 无 | 无 |

`late_integrator_transition_1p3tr` 在 `architecture-component-producer` 与 `architecture-consumer` 上应被接受：前者用固定的伙伴积分器，提交的积分器不参与；后者的积分器被常数替身取代。每个候选目录都含三个交付文件，只有 `integrator_state_cell.va` 与参考解不同。

开发证据（不是校准结论）在 `runs/t3-harbor30-20261027/f01-r1/`：合成控制（未仿真，旧版参考波形在内存中推迟或提前后由本题 checker 判定）见 `synthetic-controls.json`，旧版 EVAS 0.8.7 运行见 `legacy-runs.json`。旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。
