# 比较器传播延迟与过驱动测量

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 delay_meter(vdd,vss,clk,vinp,vinn,outp,outn,delay_ps,overdrive_mv,polarity,valid)。供电固定0.9V和0V，逻辑检测门限0.45V；报告valid和polarity也按0.9V逻辑。每次clk上升沿重新武装并清valid，overdrive_mv为该时刻输入差绝对值乘1000。武装后outp或outn的首个上升沿锁存与clk的实际间隔乘1e12到delay_ps，polarity分别为0.9V或0V，valid为0.9V。缺决策不能沿用旧valid；未武装的边沿忽略，重新武装保留上一数值直到新决策。tr=20ps；guard80ps，延迟误差0.7ps、过驱动0.2mV、逻辑0.002V。

## 公开自测与终评范围

差分过驱动绝对值为0.001至0.08V，输入共模0.45V；时钟周期5至7ns，每轮输入在launch前至少200ps稳定，实际响应不超过1ns。DUT可变传播延迟参数，或在任意后续轮缺少决策；供电与单位保持不变。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。公开自测实例位于 `/work/public/cases.json`，固定DUT实现位于 `/work/public/dut/`，可据此运行自己的Spectre自测。终评在提交后使用合同范围内不同的参数、事件及故障实例；终评台架和checker不进入解题材料。判定目标与数值容差以本题公开合同为准。
