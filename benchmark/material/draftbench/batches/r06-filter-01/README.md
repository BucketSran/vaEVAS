# R06 滤波第一批（P0 试点）

本批从 PR255 规划池的 P0 候选新建本地 Harbor 题包，不计入原 56 题，也不与首批30题、第二批草稿重复计数；同源关系逐题写在各题 `SOURCE.md`。2026-10-27 用户要求提速后开始建设。状态为 implementation，grading 与 runtime 待完成，正式录取为 0。

| 题目 | 规划候选 | 工程动作 | 状态 |
| --- | --- | --- | --- |
| [r06-spec-ct-lowpass-sampler](tasks/r06-spec-ct-lowpass-sampler/SOURCE.md) | C260-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制通过；参考解在 EVAS 02dee32b（拉普拉斯系数数组写法）和旧版 EVAS 0.8.7（参数作系数）上都未跑通，属两版 EVAS 的局限，参考解未改。2026-10-28 按试点审核修正（fix-r1）：加 `vth-tr-override` 用例、`1.3*tr` 迟到负例与被拒矩阵；评分起点（F01）用户已确认，增量复审待做 |
| [r06-spec-dt-lowpass-sampler](tasks/r06-spec-dt-lowpass-sampler/SOURCE.md) | C264-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 4/4 用例通过；EVAS 02dee32b 在 stage a 拒绝 zi 系数数组 `{...}`。评分起点（F01）用户已确认（2026-10-28）。2026-10-28 按 P0 审核修正（p0-fix-a）：新私有用例 `vth-tr-override`（采样穿越落在网格 0.9 处），补 `1.3*tr` 迟到负例、`1.2*tr` 窗内对照与写死 `vth`/`tr` 的校准候选；控制触到阈值又返回不再算穿越（F02）；旧版 EVAS 上参考解 5/5 用例通过；“触碰算不算事件”列为待用户确认，增量复审待做 |
| [r06-spec-slew-envelope](tasks/r06-spec-slew-envelope/SOURCE.md) | C266-S1 | spec-modeling | implementation，未仿真；结构、Harbor 配置、合成波形控制、Docker 构建通过；旧版 EVAS 0.8.7 上参考解 4/4 用例通过；EVAS 02dee32b 在 stage c 拒绝依赖事件状态的 slew。记忆污染风险高：合同就是原 gold 行为的显式写法，用户已确认（2026-10-28）保持现合同、评测时记为高污染风险题。2026-10-28 按 P0 审核修正（p0-fix-a）：checker 裁掉终点及之后的移位事件，避免倒序断点（F01）；新私有用例 `vth-override` 与写死门限的校准候选；题面“1.25 倍斜坡时长”一句限定为两路都从旧目标出发、斜坡未被打断的完整过渡；控制触到阈值又返回不再算穿越（F02）；旧版 EVAS 上参考解 5/5 用例通过；“触碰算不算事件”列为待用户确认，增量复审待做 |

C264-S1（离散一阶低通）与 C260-S1 构成连续/离散的区别：合同要求按 `tupdate` 网格更新，并用连续同极点实现等错误模型区分，不按语法版本重复计题。C266-S1 与第二批草稿 v3-filter-envelope 的来源和机制都不同，各自保留身份。没有可用的 Spectre，本批检查不执行 Spectre 仿真。旧版 EVAS 0.8.7 的结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；EVAS 02dee32b 的阶段结果也只作开发证据。
