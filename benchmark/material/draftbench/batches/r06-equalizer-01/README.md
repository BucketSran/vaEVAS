# R06 均衡第一批（P0）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系写在题目的 `SOURCE.md`。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| r06-spec-dfe-two-tap（`benchmark/material/draftbench/batches/r06-equalizer-01/tasks/r06-spec-dfe-two-tap/SOURCE.md`） | U17-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 10/10 用例通过（9 个私有加公开 `base`）；EVAS 02dee32b 在 stage c 报已知的 NF-01（transition 证明预算），截短用例可跑通。判决编码与空历史（决定卡选 A）、内部组织自由用户已确认；复位方式与清零后 `slicer_in_dbg` 的取值列为待用户确认（已按推荐写入）。独立审核 r1 的 4 条发现已由修正 r1、r2 处理：r1 新增两个参数端点用例与两个错误候选，改正来源声明与历史错误对应；r2 新增 vss 下端与最短 clk 脉宽端点用例 `min-pulse-vss-low`，以及 `empty_history_high` 等三个错误候选。原八例中有三例的间隔恰在合同下界上，按 U15 修正 r5 的裁定属平局，r3 已挪开（复位高电平 0.502 ns，两例时钟周期各加一个网格步），九例重扫后恰在下界上的间隔为 0。2026-10-29 修正 r4、r5：采样量 `slicer_in_dbg` 的变化门限 δ = 0.1 mV 写进题面与 checker。r1 至 r5 的增量复审待做；现行身份还没有 Spectre 结果 |

U17-S1 与首批30题里的 FFE（slot 22，v2-spec-353）机制不同：本题考历史判决经反馈影响下一次判决，`history-pairs` 用例在当前输入不变时改变过去判决。没有可用的 Spectre，本批检查不执行 Spectre 仿真。旧版 EVAS 0.8.7 的结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；EVAS 02dee32b 的阶段结果也只作开发证据。
