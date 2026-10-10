# 重武装、锁存与溢出的时间计数仪表

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 tdc_meter(start,stop,clk,rst,code_0,...,code_7,valid,overflow)。门限0.5V，逻辑输出0V与1V，code_0最低位。start上升清旧结果、valid和overflow并重新武装，取消先前区间。武装后每clk上升计数一次；stop上升锁存计数并解除武装、valid=1。未武装stop忽略，结果保持；第256个clk触发饱和值255、overflow=1、valid=1，并解除武装。rst上升异步清所有状态，rst高时不测量。固定场景没有同时间的输入边沿；同时间语义不属本题。输出在事件后40ps内可平滑，之后2mV误差。

## 公开自测与终评范围

clk周期90至130ps，输入start/stop边沿20ps；可变测量起止、重武装、未武装stop及reset时刻。终评包含正常锁存、取消区间和超过256边沿的区间；输入门限交点不重合，至少隔开5ps。计数边界与报告电平固定。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。公开自测实例位于 `/work/public/cases.json`，固定DUT实现位于 `/work/public/dut/`，可据此运行自己的Spectre自测。终评在提交后使用合同范围内不同的参数、事件及故障实例；终评台架和checker不进入解题材料。判定目标与数值容差以本题公开合同为准。
