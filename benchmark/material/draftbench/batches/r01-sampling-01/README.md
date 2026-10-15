# R01 采样第一批：代表题合同审核

本批目前只有 `r01-spec-acquisition` 一个合同草稿，不计入两批 56 题。
已确认的 R01 方向、共用电路机制和同源区别仍在[R01 功能族](../../circuits/r01-sampling/README.md)；
旧 20 道题包的恢复记录见[整合说明](../../DISCUSSION.md#整合与归档结果)，没有把旧格式题包批量恢复为当前草稿。

## 当前审核

- 工程动作：按规格构建模型；电路功能：连续跟踪的有限采集与保持。
- 已有材料：[英文题面](tasks/r01-spec-acquisition/instruction.md)、[接口与 TODO](tasks/r01-spec-acquisition/environment/starter/circuit.va)、[公开台架](tasks/r01-spec-acquisition/environment/starter/testbench/tb.scs)。
- 来源与区别：[SOURCE](tasks/r01-spec-acquisition/SOURCE.md)记录与旧 071 的关联；共用 `r01-basic` 核心，新增连续跟踪、输入相关时间常数和有限复位。
- 中文导读与未决合同：[basic 说明](../../circuits/r01-sampling/module/basic/README.md#有限采集建模题合同审核)。
- 当前版本：2026-10-14 恢复的合同草稿；本版人工审核待进行，尚无录取去向。
- 下一项工作：继续核对工程价值、关键行为与合同。合同和验收方案确认后，再接入完整环境、参考解、checker 与作者校准。

这份草稿尚不能作为完整 Harbor 题运行。本次只调整存放位置，不补做题目实现或模型实验。
每次合同修改在 SOURCE 与本清单记录版本和结论；录取时移入正式题集并保留链接。
