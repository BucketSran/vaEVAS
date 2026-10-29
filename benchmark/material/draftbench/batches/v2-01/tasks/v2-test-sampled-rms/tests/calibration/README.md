# 校准候选（F01 评分起点）

Spectre 校准待做，本目录的内容都未在 Spectre 上仿真。`mutants.py` 从 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

checker 的失败类别是 `kind=report`：某个评分点（保存点，或区间中点的线性插值）上报告与期望值的差超过 2 mV（`tests/v2_testing.py:58-74` 的 `pieces()`）。事件表是 `clk` 与 `reset` 穿越 0.45 V 的每个上升（`:100-101`、`:118`），不论是否采样，报告不变的事件也算。事件与瞬态起止把运行切成区间；不长于 640 ps 的区间整段不评分；其余区间里，离两端都超过 320 ps 的保存点和区间中点（线性插值）都评分。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_report_delay_340ps` | `rms_out`、`valid` 的 transition 延迟 340 ps（guard + 20 ps），过渡仍为 `tr`（用例 80 ps） | 全部用例 | 事件后 320 ps 起的评分点仍是旧值或仍在过渡中 |
| `inwindow_report_delay_200ps`（正确） | 延迟 200 ps，事件后 280 ps 到值，在 320 ps guard 内 | 无 | 无 |

提前负例只有合成控制：报告在事件前超过 320 ps 就变化，因果模型做不出来。作者证据把参考波形的报告列整体提前 340 ps（`early-report--340ps`，应被拒），另有提前 200 ps 的窗内对照（`inwindow-early-report--200ps`，应通过）；两者都没有对应的 VA 候选。

提前 340 ps、过渡 80 ps 时，只有开区间 (e−340, e−320) ps 里的评分点能同时满足“报告已开始变化”和“仍在评分”。

- 旧三例 `maxstep` 为 40 ps，采样沿都在 20 ps 的整数倍上，开区间 (e−340, e−320) ps 里没有网格行：沿前最近的评分行在沿前 340 ps（平移后的过渡恰从这一行开始，仍取旧值，是该行上的平局）或 360 ps，沿前 320 ps 的行被 guard 排除；唯一的 `reset` 上升沿（58.47 ns）前 230 ps 就是采样沿，所在区间整段不评分。所以提前 340 ps 的合成控制在旧三例都通过，不能证明提前负例被拒；提前 360 ps（guard 加一个 maxstep）的诊断控制被拒。只把网格缩到 20 ps 也不够：20 ps 的网格点最多只落在这个开区间的两端。迟到方向有 100 ps 宽、含两到三条评分行的窗，不受影响。这一点 f01-r2 没有改。
- `terminal-fine-grid-10ps`（f01-r2，复审 F01B-03）用 `strobeperiod=10p`、`strobeoutput=strobeonly` 固定保存网格，另照网表约定清单写 `maxstep=10p`、`errpreset=moderate` 与 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`。`clk` 与 `reset` 的折点和穿越都在 10 ps 网格点上，所以每次改变报告的事件 e 之前，e−330 ps 一行离提前检出窗两端各 10 ps；该行上提前 340 ps 的报告已走过 1/8 的过渡：`valid` 差 112.5 mV，`rms_out` 在五次改变 `rms_out` 的事件上差 23.0–47.0 mV（台阶 184–376 mV），都超过 2 mV。迟到方向有 e+330 到 e+410 ps 共 9 行。这个用例上 `early-report--340ps` 被拒，窗内 ±200 ps 与参考都通过；`late_report_delay_340ps` 进它的 `must_reject`。

开发证据（不是校准结论）：f01-r1 的记录在 `runs/t3-batch2-20261027/f01-r1/`，f01-r2 的记录在 `runs/t3-batch2-20261027/f01-r2/`（合成控制 `synthetic-controls.json`、检出窗统计 `evidence/detection-windows.json`、旧版运行 `legacy-runs.json`）。合成控制未仿真，是旧版参考波形在内存中平移后由本题 checker 判定；旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。
