# dac-linearity

实现 `/work/dut.va`。模块 dut(code,observe,clk,rst,dnl,inl,valid)。code为整数电压0至15，observe为只读固定DAC实际模拟输出。clk上升沿采集，码必须从0到15每码一次。初始与rst上升沿清空输出和历史；rst高时不采集。16次后仅当码序完整且末值大于首值，valid=1；其他记录valid=0、dnl=inl=0，不返回旧结果。step=(实际末值-实际首值)/15，DNL是相邻实际电压差除step减1的最大绝对值，INL是实际电压相对端点直线偏离除step的最大绝对值，单位LSB。不做最佳拟合，不假设性能合格。完成后保持直到rst，允许完整、缺码、重复码记录。固定DUT offset在0至0.2V、scale在0.5至0.9V、delta在-0.03至0.03V，均只读。

固定后端 Spectre，候选源码按原字节运行，不作语言子集限制。仅 dut.va 可修改；输入及固定器件只读。测量题各电气报告端口的电压数值就是指标数值，例如0.5LSB用0.5V、20dB用20V，valid用0或1V。初态及事件后允许1ns建立，之后输出绝对误差1mV，频谱dB误差0.03dB、ENOB误差0.006bit。输出可用 transition(...,0,100p,100p)；无需复制参考结构。公开台架见 `/work/public/cases.json`，终评改变合同内输入、端点、样本和控制时刻。测量 DUT 性能差仍可通过，评分只看报告正确。源代码、reference与私有checker不进入公开包。
