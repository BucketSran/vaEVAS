# R08 比较器与门限第一批（P0）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-28 在 P0 铺开时开始建设。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r08-spec-debounce-latch](tasks/r08-spec-debounce-latch/SOURCE.md) | C176-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 5/5 用例通过，25 个校准候选与被拒矩阵一致；EVAS 02dee32b 停在 NF-01（#275）；原 gold 能通过新合同，记忆污染风险高。评分起点（F01）用户已确认（2026-10-28），`1.3*tr` 迟到负例四例都被拒。2026-10-28 按 P0 审核修正（p0-fix-b）：输入触到阈值又返回不再算穿越（F02），旧版 EVAS 上参考解仍全部通过；“触碰算不算事件”列为待用户确认，增量复审待做 |

C176-S1 与第二批草稿 v2-repair-debounce-latch 同源（v4:005），后者是诊断修复题，本题按规格建模，各自保留身份，不重复计数。没有可用的 Spectre，本批检查不执行 Spectre 仿真；EVAS 02dee32b 与旧版 EVAS 0.8.7 的结果都只作开发证据，待 Spectre 复跑。
