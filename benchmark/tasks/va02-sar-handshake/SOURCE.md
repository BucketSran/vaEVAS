# 来源与改编

原始资产：[veriloga/lab/calibration_control/sar_logic_7bit.va](../../reference/veriloga/lab/calibration_control/sar_logic_7bit.va)。
完整历史来源见 [SOURCES.md](../../reference/veriloga/SOURCES.md)。

保留七位逐次逼近握手及互补 CDAC 控制；明确初始化、整字复位和 10ps 输出边沿。原代码把布尔位与 vdd/2 比较，改编规格明确按布尔值选极性，因此可测试 2.5V。首轮使用预定比较器反馈脉冲，逐边检查握手，尚未验证真实比较器闭环。

原始文件未修改。该题评估明确规格到 Verilog-A 的一次性实现，不评估从模糊需求提出模型的能力。
