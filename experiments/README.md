# Experiments

此工作区组织使用 Harbor 运行 benchmark 的实验配置、结果分析和论文图表生成。
配置按需要记录模型与 Agent、任务范围、时间和资源预算、重复次数及相关版本。

可跟踪内容包括配置、分析脚本和经过整理且可追溯的结果摘要。
原始轨迹、波形及临时输出使用仓库根目录下的 `runs/` 或外部运行目录，避免提交到 Git。

当前已完成 [DVS-2 起步卡四后端试点](dvs2-starter-pilot/RESULTS.md)，
其 [协议与执行入口](dvs2-starter-pilot/README.md) 固定了 15 个条件和两档设置。
这批数据是独立仿真器验证的开发证据，尚非正式论文达标率或性能排名。

[共同历史重判](dvs2-history-validation/README.md) 使用新的精确有理数判定程序复用旧事件波形，
单列构造校准、条件性相容/不相容及仍未具备的观察资格，不覆盖 v1 的原执行记录。

[Spectre 扩展实测](dvs2-spectre-validation/README.md) 在 thu-sui 执行当前 31 条件、两档共 62 条配置，
全部成功执行并满足固定的有限观测判据；新增 16 条件已实现，完整观察资格仍为 I。

[四后端补测](dvs2-four-backend-validation/README.md) 已在 thu-sui 完成 130 条新配置，
结合 118 条复用记录，补齐 [31 条件 × 四后端 × 两档矩阵](dvs2-four-backend-validation/results/MATRIX.md)。
基础档/细化档达标数分别为 Spectre 31/31、EVAS 18/8、OpenVAF＋ngspice 16/16、Gnucap 17/16，
各档分母均为 31；编译、执行、数值失败与超时完整保留，正式资格仍为 I。
[后续故障归因](dvs2-four-backend-validation/DIAGNOSIS.md)通过 15 个诊断探针追查机制，
保留原矩阵，尚未开展仿真器修复。

任务失败、仿真器问题和执行环境失败应分别记录；
影响判分的修复需要评估哪些结果必须重跑。
