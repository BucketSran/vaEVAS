# R01 采样第二批（P0 试点）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-27 用户要求提速后开始建设。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r01-spec-aperture-delay](tasks/r01-spec-aperture-delay/SOURCE.md) | C056-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、145 次合成波形控制通过；EVAS 02dee32b 1/6 用例跑完并通过 checker，其余停在 NF-01；旧版 EVAS 0.8.7 参考解 6/6 通过（旧版开发证据，待 Spectre 复跑）。2026-10-28 按试点审核修正（fix-r1）：打断方向与覆盖、初值区间，新增私有用例 `interrupted-transitions`、`early-first-capture` 与被拒矩阵，增量复审待做。2026-10-30 修正 v417：起点、停留、碰到、最小偏离改按用例网表的 vsource 定义判（网表约定清单第 4.21 版第 20 条做法甲），碰到一律报台架错误；门限与余量数值未改，两份 checker 逐字节相同。合成控制通过；已交回的 184 个 Spectre 作业用打包快照重判，新 checker 与改前的判决逐个相同。未仿真。 |
| r01-repair-aperture-delay | C056-R1 | diagnosis-repair | 未建：建题子任务判定与 S1 职责实质重复（合同相同、交付是 S1 子集、两种坏版已作 S1 校准负例），停在设计说明；用户已确认（2026-10-28）不建，C056 只计一题 |

没有可用的 Spectre，本批检查不执行电路仿真；EVAS 02dee32b 的阶段结果只作开发证据，待 Spectre 复跑。
