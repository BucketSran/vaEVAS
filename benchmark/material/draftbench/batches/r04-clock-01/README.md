# R04 时钟与时间测量第一批（P0 试点）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-27 用户要求提速后开始建设。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r04-spec-delay-pulse-hold](tasks/r04-spec-delay-pulse-hold/SOURCE.md) | U15-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、165 次合成波形控制、Docker 实际构建通过；EVAS 02dee32b 1/6 用例跑完并通过 checker，其余停在 NF-01；旧版 EVAS 0.8.7 参考解 6/6 通过、23 个错误候选按设计被拒（旧版开发证据，待 Spectre 复跑）。2026-10-28 按试点审核修正（fix-r1）：小 `tr` 的边沿窗口合并、周期条件、新私有用例 `minimum-tr-pulses` 与被拒矩阵；按试点 r2 审核再修（fix-r2：重叠边沿窗口按逐行相位判定等），r3 复审只剩激励合法性的等号余量一条；fix-r3 把这一余量改为随时刻的 ULP 增大，0.5 ms 处恰好等号的合法激励不再误判，ns 级判定不变，增量复审待做 |
| [r04-spec-fine-coarse-tdc](tasks/r04-spec-fine-coarse-tdc/SOURCE.md) | U16-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 5/5 用例通过，27 个校准候选与被拒矩阵一致；EVAS 02dee32b 在 stage b 被 source floor 证明预算挡住。评分起点（F01）用户已确认（2026-10-28），`1.3*tr` 迟到负例四例都被拒。2026-10-28 按 P0 审核修正（p0-fix-b）：事件相位改为网格的 0.9，改动的私有用例中结果、清零、溢出三类迟到均可见（F06），公开 `base` 未改，其三项例外见 SOURCE；只有两个参考沿也能定周期（F07），新私有用例 `two-ref-short`；输入触到阈值又返回不再算穿越（F02）；“触碰算不算事件”列为待用户确认，增量复审待做 |

U16-S1 与首批 v2-integrate-case0007-adpll-fine-tdc、第二批 v2-test-time-protocol 的职责差异写在其 SOURCE。没有可用的 Spectre，本批检查不执行电路仿真；EVAS 02dee32b 与旧版 EVAS 0.8.7 的结果都只作开发证据，待 Spectre 复跑。
