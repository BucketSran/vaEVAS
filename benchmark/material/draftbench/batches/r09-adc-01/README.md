# R09 ADC 与转换控制第一批（P0）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-28 在 P0 铺开时开始建设。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r09-spec-pipeline-two-stage](tasks/r09-spec-pipeline-two-stage/SOURCE.md) | C105-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 5/5 通过，40 个校准候选与被拒矩阵一致（原 gold 套壳被拒）；EVAS 02dee32b 停在 stage c 的 `kernel.step_budget`；评分起点（F01）用户已确认，`1.3*tr` 迟到负例四例都被拒；记忆污染风险中。2026-10-28 按 P0 审核修正（p0-fix-b）：输入触到阈值又返回不再算穿越（F02）；“触碰算不算事件”列为待用户确认，增量复审待做 |
| r09-spec-sar-adc-system（`benchmark/material/draftbench/batches/r09-adc-01/tasks/r09-spec-sar-adc-system/SOURCE.md`） | C109-S1 | spec-modeling | implementation，未仿真；四个功能模块加顶层（用户 Q1 选 A），转换参考按用户选的端点定义；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 8/8 通过，41 个校准候选 246 次与被拒矩阵一致；EVAS 02dee32b 停在 stage b 的运行期移位量（#270 第15项）；记忆污染风险高：原 gold 只在 `vss≠0` 的两例被拒。2026-10-28 按 P0 审核修正（p0-fix-b）：顶层加复位恢复间隔 `2*tr`（F03，待用户确认，已按推荐写入），新私有用例 `reset-recovery-long-tr`、`modules-initial` 与只改初态的校准负例（F10），合成控制注明覆盖范围（F09）；输入触到阈值又返回不再算穿越（F02）；旧版 EVAS 上参考解全部用例通过。2026-10-29 修正 e（第 (ii) 类）：Spectre 21.1 探针（预读，2026-10-29 已正式核收）证实原参考解的 `cross()` 锁存比较器在零平台后判错（`vin <= vss` 得码 15），换入按电平判定的修正版；新增零平台私有用例三例；校准件新增错误候选 `comparator_cross_latch`（原比较器）；旧版 EVAS 在零平台三例上放过它，属零点处理掩盖；题面两处按决定单第 13 项写入 A（用户 2026-10-29 已确认）；验证超时改为 1800 s（每例约 60 s）。2026-10-29 修正 r4、r5：采样输出的变化门限 δ = 0.1 mV、DAC 位同刻门限 1 ps 写进题面与 checker；全部用例补齐容差；按决定单第 1 项退回 `reset-recovery-long-tr` 的第 (i) 类平局挪动。修正 b 至 r5 的增量复审待做；按现行身份的 Spectre 预校准待建 |

C105-S1 的职责是两级流水线的样本归属与发布对齐，与首批 v2-spec-003-pipeline-adc-stage（单级判决与残差）不同。同单元的 P1 候选 C089-S1、C102-S1、C103-S1 不在本批。C109-S1 把采样、逐位试位、DAC 反馈与 done 的协同交给求解者，与首批 v2-spec-186（SAR 前端逻辑）、v2-spec-002（反馈 DAC）的单模块职责不同。没有可用的 Spectre，本批检查不执行 Spectre 仿真；EVAS 02dee32b 与旧版 EVAS 0.8.7 的结果都只作开发证据，待 Spectre 复跑。
