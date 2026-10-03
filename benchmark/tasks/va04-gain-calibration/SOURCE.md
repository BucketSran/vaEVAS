# 来源与改编

原始资产：[veriloga/lab/calibration_control/pipeline_adc_gain_calibration_nested_view.va](../../reference/veriloga/lab/calibration_control/pipeline_adc_gain_calibration_nested_view.va)。
完整历史来源见 [SOURCES.md](../../reference/veriloga/SOURCES.md)。

保留两相码采样、64 LSB 目标差、增益步进和饱和机制。原始 tt 未被使用，改编明确用 tt 控制全部输出边沿；没有声称任意实际 ADC 植物模型下都收敛。

原始文件未修改。该题评估明确规格到 Verilog-A 的一次性实现，不评估从模糊需求提出模型的能力。
