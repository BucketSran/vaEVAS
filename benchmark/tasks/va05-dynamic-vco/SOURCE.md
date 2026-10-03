# 来源与改编

原始资产：[veriloga/cadence/clock_pll/dig_vco__icadvm201.va](../../reference/veriloga/cadence/clock_pll/dig_vco__icadvm201.va)。
完整历史来源见 [SOURCES.md](../../reference/veriloga/SOURCES.md)。

显式规定初始输出为高，补全原例未赋值的 vout_val；保留频率积分与事件翻转。独立判据对分段线性频率积分并求半周期交点，不从参考波形抽取。

原始文件未修改。该题评估明确规格到 Verilog-A 的一次性实现，不评估从模糊需求提出模型的能力。
