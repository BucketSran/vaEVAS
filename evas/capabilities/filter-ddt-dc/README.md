# 滤波与微分：DC 直通项

历史视图身份：`historical-comparison-import-f210ebd5`。
原输入：`evas/docs/COMPARISON.md`。
原判据范围：Historical transcription; not qualification for current main。
这些成绩留在该历史身份下。当前要求分母只计登记中的当前要求。
当前逐要求四后端事实见 [support.md](../generated/support.md) 与 [support-facts.json](../generated/support-facts.json)。

章节：连续动态与相位。
状态：已比较。
审核：成绩已转录。

依赖的基本节点：`laplace-nd`、`ddt-input`。组合通过不使这些节点自动合格。

成绩沿用[原支持矩阵](../../docs/COMPARISON.md#支持矩阵)的固定模型和配置，
只适用于各行的容差、停止时间及来源版本，不覆盖所有合法写法。
结果来自不同历史版本，不代表当前 main 或 IR33 的一次全量验收。
逐行范围见[验证覆盖](../../validation/paper/COVERAGE.md)，
执行版本与收据见[来源和补充证据](../../docs/development/COMPARISON.md#table-evidence)。

滤波与微分：DC 直通项。Spectre：Q3 启动误差超限；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。

成绩来源：[evas/docs/COMPARISON.md#支持矩阵](../../../evas/docs/COMPARISON.md#支持矩阵)。

当前合同若仍在旧路径，是因为那一路径或字节已被冻结收据引用。本目录不搬那些文件。
