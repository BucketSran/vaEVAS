# R03 电源控制第一批（P0 试点）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-27 用户要求提速后开始建设。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r03-spec-buck-softstart](tasks/r03-spec-buck-softstart/SOURCE.md) | U18-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制通过；EVAS 02dee32b 停在 NF-01；旧版 EVAS 0.8.7 参考解 4/4 通过（旧版开发证据，待 Spectre 复跑）；公开的原 gold 也能通过，记忆污染风险高。2026-10-28 按试点审核修正（fix-r1）：加 `vth-tr-override`、`duty-endpoints` 用例、`1.3*tr` 迟到负例与被拒矩阵；评分起点（F01）用户已确认，增量复审待做 |

没有可用的 Spectre，本批检查不执行电路仿真；EVAS 02dee32b 的阶段结果只作开发证据，待 Spectre 复跑。
