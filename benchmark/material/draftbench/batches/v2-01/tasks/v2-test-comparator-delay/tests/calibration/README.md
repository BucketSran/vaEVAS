# 校准候选（F01 评分起点）

Spectre 校准待做，本目录的内容都未在 Spectre 上仿真。`mutants.py` 从 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

checker 的失败类别是 `kind=report`：某个评分点（保存点，或区间中点的线性插值）上报告与期望值的差超过该输出的容差（`tests/v2_testing.py:58-74` 的 `pieces()`）。事件表是 `clk`、`outp`、`outn` 的每个上升穿越（0.45 V），以及 t = 0。事件与瞬态起止把运行切成区间；不长于 160 ps 的区间整段不评分；其余区间里，离两端都超过 80 ps 的保存点和区间中点都评分。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_report_delay_100ps` | `delay_ps`、`overdrive_mv`、`polarity`、`valid` 的 transition 延迟 100 ps（guard + 20 ps），过渡仍为 `tr` | 全部用例 | 事件后 80 ps 起的评分点仍是旧值 |
| `inwindow_report_delay_50ps`（正确） | 延迟 50 ps，事件后 70 ps 到值，在 80 ps guard 内 | 无 | 无 |

提前负例只有合成控制：报告在事件前超过 80 ps 就变化，因果模型做不出来。作者证据把参考波形的报告列整体提前 100 ps（`early-report--100ps`，应被拒），另有提前 50 ps 的窗内对照（`inwindow-early-report--50ps`，应通过）；两者都没有对应的 VA 候选。

开发证据（不是校准结论）在 `runs/t3-harbor30-20261027/f01-r1/`：合成控制（未仿真，旧版参考波形在内存中推迟或提前后由本题 checker 判定）见 `synthetic-controls.json`，旧版 EVAS 0.8.7 运行见 `legacy-runs.json`。旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。
