# 校准候选（F01 评分起点）

Spectre 校准待做，本目录的内容都未在 Spectre 上仿真。`mutants.py` 从 三个参考文件 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

checker 只有一种失败：某个评分点上输出与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）。评分起点在 `tests/v2_spec.py:188`：t = 0 之后、以及任一输出目标改变的事件之后 `4.1*tr` 内的点，所有输出都不评分；其后保持区间内每个点都评分。消费者替身用例（`architecture-consumer`）由 `tests/v2_structure.py:19-34` 判定，从 t = 0 起每个保存点都评分。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_lp_output_delay_0p8tr` | `synchronous_lp_state` 的四个输出延迟 `0.8*tr`：有效斩波沿后 `4.3*tr` 才到值（参考解为 `3.5*tr`：通知在 `2*tr` 后开始、`2.5*tr` 处穿越，低通再过渡 `tr`） | `contract-base`、`contract-stretched-input`、`architecture-component-consumer`、`architecture-producer` | 公开输出在 `4.1*tr` 处仍在过渡中 |
| `inwindow_lp_output_delay_0p55tr`（正确） | 延迟 `0.55*tr`：`4.05*tr` 到值，在期限 `4*tr` 与评分起点 `4.1*tr` 之间，属于用户已接受的余量 | 无 | 无 |

`late_lp_output_delay_0p8tr` 在 `architecture-component-producer` 与 `architecture-consumer` 上应被接受：前者用固定的伙伴低通，提交的低通不参与；后者的低通被常数替身取代，公开输出不随事件变化。每个候选目录都含三个交付文件，只有 `synchronous_lp_state.va` 与参考解不同。

旧版 EVAS 0.8.7 对 `architecture-component-producer` 的层次保存列 `IDUT.*` 静默返回 0（first30-r1 的参考解同样失败，#270 第7项），这一用例在旧版上的失败不是候选的证据。合成控制改用展开结构的旧版波形（`runs/t3-legacy-evas-20261027/diag-091-component-producer/`）。

开发证据（不是校准结论）在 `runs/t3-harbor30-20261027/f01-r1/`：合成控制（未仿真，旧版参考波形在内存中推迟或提前后由本题 checker 判定）见 `synthetic-controls.json`，旧版 EVAS 0.8.7 运行见 `legacy-runs.json`。旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。
