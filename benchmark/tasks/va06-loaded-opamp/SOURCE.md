# 来源与改编

原始资产：[veriloga/cadence/analog/opamp.va](../../reference/veriloga/cadence/analog/opamp.va)。
完整历史来源见 [SOURCES.md](../../reference/veriloga/SOURCES.md)。

原例电路方程不改；头文件名称标准化。规格明确电流方向、软限幅和外部负载，不要求此非功率守恒宏模型具备电源电流真实性。三组独立 RK4 数值解作电压判据，解析输入支路电流作额外判据。

原始文件未修改。该题评估明确规格到 Verilog-A 的一次性实现，不评估从模糊需求提出模型的能力。
