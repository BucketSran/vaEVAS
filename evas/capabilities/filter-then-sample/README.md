# 滤波→采样保持

章节：组合、反馈、实例。
状态：已比较。
审核：成绩已转录。

依赖的基本节点：`laplace-nd`、`sample-hold-timer`。组合通过不使这些节点自动合格。

滤波→采样保持。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：采样历史错误；EVAS：✓ Q3。

成绩来源：[evas/docs/COMPARISON.md#支持矩阵](../../../evas/docs/COMPARISON.md#支持矩阵)。

当前合同若仍在旧路径，是因为那一路径或字节已被冻结收据引用。本目录不搬那些文件。
