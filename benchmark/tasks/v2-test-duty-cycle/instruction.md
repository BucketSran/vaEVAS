# 实际时钟占空比测量

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 duty_cycle_meter_8b(clk_in,valid,duty0,...,duty7)，duty0为最低位。阈值vth=0.45V、报告高vdd=0.9V、tr=20ps。必须见到上升、下降、下一上升三个事件才报告完整周期；初态高电平的下降不能独自构成完整周期。码值为四舍五入的255乘实际高电平时间除实际周期，饱和0到255。valid初始0，首个完整周期后为0.9V并保持；新完整周期更新码，其他时间保持旧结果。guard100ps，逻辑电平误差2mV。边沿时间的数值验收不确定度为1fs；由三个实际边沿的±1fs区间求占空比上下界，仅在该区间跨越半LSB量化门限时容许相邻两个完整8位码。示例数学码42.5可接受42或43，不能逐位混选，也不接受41或44。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。运行 `python /tests/verify.py --candidate /work/dut.va --output /logs/verifier --tests /tests` 自测，正式条件和数值容差公开于 public/cases.json。
