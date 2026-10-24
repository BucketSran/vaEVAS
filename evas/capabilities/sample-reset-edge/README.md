# 采样、复位与输出边沿

章节：采样、保持、复位。
状态：已比较。
审核：成绩已转录。

依赖的基本节点：`transition`。组合通过不使这些节点自动合格。

成绩沿用[原支持矩阵](../../docs/COMPARISON.md#支持矩阵)的固定模型和配置，
只适用于各行的容差、停止时间及来源版本，不覆盖所有合法写法。
结果来自不同历史版本，不代表当前 main 或 IR33 的一次全量验收。
逐行范围见[验证覆盖](../../validation/paper/COVERAGE.md)，
执行版本与收据见[来源和补充证据](../../docs/development/COMPARISON.md#table-evidence)。

采样、复位与输出边沿。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：漏事件；EVAS：✓ Q3。

成绩来源：[evas/docs/COMPARISON.md#支持矩阵](../../../evas/docs/COMPARISON.md#支持矩阵)。

当前合同若仍在旧路径，是因为那一路径或字节已被冻结收据引用。本目录不搬那些文件。
