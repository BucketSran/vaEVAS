# 校准候选（F01 评分起点）

Spectre 校准待做，本目录的内容都未在 Spectre 上仿真。`mutants.py` 从 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

checker 只有一种失败：某个评分点上输出与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）。评分起点在 `tests/v2_spec.py:188`：t = 0 之后、以及任一输出目标改变的事件之后 `1.15*200 ps` 内的点，所有输出都不评分；其后保持区间内每个点都评分。本题评分起点为 230 ps。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_output_delay_250ps` | 全部 13 个输出的延迟改为 250 ps（过渡仍为 10 ps），事件后 260 ps 才到值 | 全部用例 | 事件后 230 ps 起的评分点仍是旧值 |
| `inwindow_output_delay_210ps`（正确） | 延迟 210 ps：220 ps 到值，在期限 200 ps 与评分起点 230 ps 之间，属于用户已接受的余量 | 无 | 无 |

旧版 EVAS 0.8.7 跑不了这两个候选：参考解用状态数组，旧版报 `dynamic_state_array_access`（first30-r1 的参考解同样如此），所以上表的条目都待 Spectre 复跑，不算已验证。作者证据另做了标量状态探针：只把数组拆成标量、把指针下标写改成平铺的 if，再按同样的延迟改法派生迟到与窗内两个探针变体。探针单独记账，不是校准候选。

开发证据（不是校准结论）在 `runs/t3-harbor30-20261027/f01-r1/`：合成控制（未仿真，旧版参考波形在内存中推迟或提前后由本题 checker 判定）见 `synthetic-controls.json`，旧版 EVAS 0.8.7 运行见 `legacy-runs.json`，探针见 `probes/` 与 `probe-runs.json`。旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。
