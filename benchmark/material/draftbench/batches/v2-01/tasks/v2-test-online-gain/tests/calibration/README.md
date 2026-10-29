# 校准候选

`mutants.py` 由 `solution/circuit.va` 生成具体的 VA 候选：`wrong/` 应被拒，`correct/` 应被接受，都用 `../cases.json` 的固定用例和同一 checker 判定。`probe/` 里是随后端而定的探针，不是校准候选，不登记必拒或必接受（见下文“探针”一节）。它们是作者校准样本，不是终评材料，也不进入解题环境。在任意目录运行 `python3 -B mutants.py <新建或空目录>`。`expected.json` 是同一被拒矩阵的机器可读形式。

checker 只有一类失败（`kind=report`）：某个评分点或评分区间中点的 `gain_out`、`valid` 与期望值相差超过 2 mV（`tests/v2_testing.py:58-74`）。评分起点按 F01（用户 2026-10-28 确认，A 方案）：每个事件前后各 350 ps 内不评分，相距不超过 700 ps 的两事件之间整段不评分，其余保存点和每个评分区间的中点都评分。事件是 `start_time` 起（含 `start_time` 本身）的每个全局采样时刻和每个 `begin_round` 穿过 0.5 V 的上升交点（`tests/v2_testing.py:158-179`）。题面照此写明，checker 不动。

| 候选 | 行为 | 必须拒绝的用例 | 必须接受的用例 | 失败类别 |
| --- | --- | --- | --- | --- |
| `late_report_delay_370ps` | 两个报告在事件后 370 ps（guard+20 ps）才开始变化，570 ps 到达（F01 迟到负例） | `terminal-normal`、`terminal-low-performance-dut` | `terminal-invalid-final-span` | `report`（区间中点处未到） |
| `inwindow_report_delay_100ps`（correct） | 事件后 100 ps 开始、300 ps 到达，晚于 `tedge`=200 ps 但在 350 ps guard 内：checker 接受的余量（F01 窗内对照） | 无 | 三例 | 无 |
| `skip_start_sample` | 丢掉 `start_time` 时刻的样本，首个样本晚一个采样周期 | 同上两例 | `terminal-invalid-final-span` | `report`（`valid` 与 `gain_out` 晚一个周期） |

`terminal-invalid-final-span` 的输入跨度始终不超过 20 mV，两个报告全程是 0 V，没有可延迟的变化，所以迟到和丢首样本的候选在这一例都应通过。

提前负例只做合成波形（acausal，VA 写不出）：报告在事件前 370 ps 开始变化被拒（`F01-early-report--370ps`），在事件前 330 ps 开始、事件前 130 ps 到达被接受（`F01-inwindow-early--330ps`）。后者就是 guard 也覆盖事件之前这一余量，用户已接受。

## 探针 `strict_start_no_margin`

author-r2（总协调 2026-10-29）把它从 wrong 组移为随后端而定的探针，写进 `probe/`，`expected.json` 的 `candidates` 不再列它，只在 `conditions` 留说明。它与 c485de86 的原参考解逐字节相同（`$abstime >= start_time`，不留裕量），20 ns 样本是否计入取决于后端给 20 ns timer 的时间点与 `start_time` 比较的结果：

- 旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）：时间点比 `start_time` 小，丢掉 20 ns 样本，`terminal-normal`、`terminal-low-performance-dut` 与对应的两个公开用例被拒，共 4/6 例被拒。旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- Spectre 21.1（B2PC rec-02，执行身份 `spectre-B2PC-rec-02-v1（结果包 sha256 a629d67a6220fbb5…）`，已核收）：19.9 ns 之后的下一个时间点是 `2.000000000000002e-08` s，比 20 ns 大约 2e-23 s，20 ns 样本计入，私有三例都通过，与参考解相同；公开三例的观察作业（B2PC opt-01，`spectre-B2PC-opt-01-v1（结果包 sha256 3e80d95b2f27000a…）`，已核收）也都通过。

所以它不能当负例：原参考解在 Spectre 上可解。参考解保留用户批准的半周期裕量，两种浮点情形下都计入 20 ns 样本。

## 后端结果

- Spectre（B2PC 预校准，已核收 2026-10-29）：上表 3 个候选在私有三例的判决都与本表一致（rec-02，9/9）；公开三例的观察作业（opt-01，无登记期望）判决与对应私有用例相同。参考解与缺省容差对照在私有三例、公开三例都通过（must-02，`spectre-B2PC-must-02-v1（结果包 sha256 b8b1a0c65f6f4a3e…）`）。author-r2 在这些已核收波形上用现行 checker 与 `expected.json` 重判，判决全部不变，记录在 `runs/t3-batch2-20261027/author-r2/`。
- 旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上，上表 3 个候选在三个私有用例和三个公开用例的判决都与本表一致（18/18；公开用例的必拒/必接受与对应私有用例相同），只用网格行复判没有变化。fix-dec-r1（2026-10-28）把公开三例的 `begin_round` 脉冲整体后移 0.35 ns（上升交点由 104.05 ns 移到 104.4 ns，与终评用例的 97.4 ns 一样距采样点 400 ps 和 600 ps）后，候选在公开三例重跑，判决仍与本表一致；私有用例与候选字节都没有改。这是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
