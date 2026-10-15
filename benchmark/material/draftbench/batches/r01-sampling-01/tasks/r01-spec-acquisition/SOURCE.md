# 来源与合同审核状态

本题来自 [R01 basic 电路资产](../../../../circuits/r01-sampling/module/basic/README.md)，
属于按规格构建模型，与 R01 core 及使用 core 的组合系统同族。
与[旧 071](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md)功能相关，
但将固定 tick 更新改为连续跟踪，并增加输入相关时间常数和有限时间复位；不是旧题的格式迁移。

有限建立和前拍残余是采样级的工程动机。具体时间常数、输入曲率与复位方程是本项目定义的行为合同，
未由真实晶体管采样级拟合，也不继承真实 SKY130 数据建模题的校准结论。
机制资料仍由 [R01 功能族](../../../../circuits/r01-sampling/README.md)维护。

2026-10-14，本目录只恢复一份供人工审核的合同草稿：英文题面、最小接口、公开台架和交付路径。
中文导读及验收方案在 [basic 说明](../../../../circuits/r01-sampling/module/basic/README.md#有限采集建模题合同审核)。
实验范围和 2 mV 判据是本版待审方案，尚未完成新版本数值校准。
Docker 环境、公开指标分析、参考解、独立终评和结果摘要留到合同确认后接入；当前不能作为完整 Harbor 题运行。
本题不加入现有 56 题，也没有模型实验或人工设计认可记录。

公开台架复用本地恢复快照 `benchmark-consolidation-20261014/r01-drafts/working-tree.tar`
中 `benchmark/tasks/r01-spec-acquisition/environment/public/public.scs` 的激励与数值设置，
仅将 include 路径改为 `../circuit.va`、模块名改为 `track_hold`。
原文件 SHA-256：`344ad3f97563d6f6787b1a239783fb63370ca8e9bcce8234b99f8ba8c39e5ce2`。
归档位置与恢复方法见[整合与归档结果](../../../../DISCUSSION.md#整合与归档结果)。
旧参考解、checker 及旧格式运行证据仍留在恢复快照；它们没有被复制到求解者材料，也不作为本版验收证据。
