# 校准候选（F01 评分起点）

`mutants.py` 从 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 必须被拒，`correct/` 必须被同一 checker 在 `../cases.json` 的固定用例上接受。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新的空目录>`，输出目录必须是新的或空的。`expected.json` 是同一张被拒矩阵的机器可读版本。

这组候选只针对 F01：评分起点与到达期限。2026-10-28 用户确认选 A：题面写明 checker 实际的观察起点，checker 不动。每个候选只改输出的过渡时间或延迟，其他行为与参考解相同。

决定单第 12 项：用户 2026-10-29 选乙，定稿。本目录是 f01-r2 按乙准备的：全部用例的 `params` 写 `tr=1e-10`，即实例的缺省 `tr`，checker 的评分起点由 230 ps 变为 115 ps。为选甲准备的退回办法不再执行。

checker 只有一种失败：某个评分点上输出与期望值相差超过 2 mV（`tests/v2_spec.py:205-208`）；另外任一行 `phi1`、`phi2` 同时高于 `(vdd+vss)/2` 记 `phase_overlap`（`:184-187`，每个保存点都查，不评分区内也查）。评分起点在 `tests/v2_spec.py:188`：t = 0 之后、以及改变任一输出目标的事件（使能且不在复位时任一方向的 `clk_in` 穿越；其后第 `dead_ticks` 个 tick，所请求相位在此启用；`rst` 上升或 `enable` 下降清零）之后 `1.15*tr` 内不评分。`tr` 取用例 `params` 的 `tr`（`:11`），现为 100 ps，所以评分起点是 115 ps。

| 候选 | 行为 | 必须拒绝的用例 | 预期失败 |
| --- | --- | --- | --- |
| `late_transition_2p6tr` | 四个输出的过渡由 `tr` 拉到 `2.6*tr`（260 ps） | 全部用例 | 事件后 115 ps 起的评分点仍在过渡中 |
| `late_transition_1p3tr` | 过渡 `1.3*tr`（130 ps），比评分起点晚 15 ps 到值 | 全部用例 | 事件后 115–130 ps 的评分点仍在过渡中（2 ps 网格上约 7 行） |
| `inwindow_transition_1p1tr`（正确） | 过渡 `1.1*tr`（110 ps），到值时刻在期限 `tr` 与评分起点 115 ps 之间，属于用户已接受的余量 | 无 | 无 |

本题已接受的余量是 15 ps（期限 100 ps 到评分起点 115 ps），与其他题的 `0.15*tr` 相同。窗内对照离评分起点只有 5 ps，`expected.json` 的 `conditions` 写明它假定后端的事件与过渡时刻偏差小于 5 ps。两相同时延长，互斥检查不受影响。

f01-r1 的正确候选 `inwindow_transition_2p2tr`（220 ps 到值）在 115 ps 起点下会被拒，已从本目录移除，由 `inwindow_transition_1p1tr` 取代。改前、改后各候选的判决对照见 `runs/t3-batch2-20261027/f01-r2/disposition.md`。

开发证据（不是校准结论）：f01-r1 的记录在 `runs/t3-batch2-20261027/f01-r1/`，f01-r2 的记录在 `runs/t3-batch2-20261027/f01-r2/`（合成控制 `synthetic-controls.json`、改前改后重判 `evidence/375-before-after.json`、旧版运行 `legacy-runs.json`）。合成控制未仿真，是旧版参考波形在内存中推迟后由本题 checker 判定；旧版结果只是开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑，不改变上表。

Spectre（B2PC 预校准，已核收 2026-10-29）：参考解在三个私有用例与公开用例都通过（must-01，执行身份 `spectre-B2PC-must-01-v1（结果包 sha256 fffd959be8465585…）`）；上表 3 个候选在三个私有用例的判决与本表一致（rec-02，`spectre-B2PC-rec-02-v1（结果包 sha256 a629d67a6220fbb5…）`），在公开用例上也同样判（opt-01，`spectre-B2PC-opt-01-v1（结果包 sha256 3e80d95b2f27000a…）`）。已移除的 220 ps 候选在乙边四个用例都被拒，在甲边都通过（opt-01 与 rec-02）。两边的完整表见 `SOURCE.md` 的“author-r2 定稿”一节。
