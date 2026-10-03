# 课题组工程资料：逻辑与寄存

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [and2.va](and2.va)<br>[来源](../../SOURCES.md#lab-logic-and2) | 两输入与门，以电压门限解释逻辑并平滑输出。 | `` and2(out, in1, in2) `` | `` real vh = 1.1 ``；`` real vl = 0 ``；`` real vth = 0.55 ``<br>默认高电平 1.1 V、门限 0.55 V；原注释误写为 Nand。 |
| [and3.va](and3.va)<br>[来源](../../SOURCES.md#lab-logic-and3) | 三输入与门，用于电压域控制逻辑建模。 | `` and3(vin1, vin2,vin3, vout) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 1.4 ``<br>默认使用 5 V 电平与微秒级延迟。 |
| [cyclic_adc_decision_logic.va](cyclic_adc_decision_logic.va)<br>[来源](../../SOURCES.md#lab-logic-cyclic_adc_decision_logic) | 根据两路比较结果和 valid 生成循环 ADC 控制与编码信号。 | `` digital_logic1(vin1, vin2,valid, x, y, z, dm, dl) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 1.4 ``<br>包含 x/y/z 和 dm/dl 多路组合逻辑，需按接口真值关系使用。 |
| [dff_0_to_5v.va](dff_0_to_5v.va)<br>[来源](../../SOURCES.md#lab-logic-dff_0_to_5v) | 上升沿 D 触发器，输出 Q 和互补 Qbar。 | `` d_ff(vin_d, vclk, vout_q, vout_qbar) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans_clk = 2.5 ``<br>默认 0/5 V 逻辑，门限 2.5 V；原文件扩展名为 .vams。 |
| [dff_async_set_reset_jitter.va](dff_async_set_reset_jitter.va)<br>[来源](../../SOURCES.md#lab-logic-dff_async_set_reset_jitter) | 带异步置位/复位、独立传播延迟和随机抖动的 D 触发器。 | `` DFFRSHQ(QP, VSS, VDD, CK, D, RN, SN) `` | `` real tcplh=100p from (0:inf) ``；`` real tcphl=100p from (0:inf) ``；`` real trphl=100p from (0:inf) ``<br>支持 initval；供电和时序参数约束见源码。 |
| [dff_minus5_to_5v.va](dff_minus5_to_5v.va)<br>[来源](../../SOURCES.md#lab-logic-dff_minus5_to_5v) | 上升沿 D 触发器，输出 Q 和互补 Qbar。 | `` d_ff(vin_d, vclk, vout_q, vout_qbar) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = -5 ``；`` real vtrans_clk = 0 ``<br>默认 −5/5 V 逻辑，门限 0 V。 |
| [dff_reset_both_outputs_low.va](dff_reset_both_outputs_low.va)<br>[来源](../../SOURCES.md#lab-logic-dff_reset_both_outputs_low) | 上升沿采样 D 的触发器，带独立复位输入。 | `` dff_rst(vin_d, vclk, rst, vout_q, vout_qbar) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans_clk = 2.5 ``<br>原代码复位时 Q 与 Qbar 都为低，并非标准互补复位行为。 |
| [dff_set_reset_supply_referenced.va](dff_set_reset_supply_referenced.va)<br>[来源](../../SOURCES.md#lab-logic-dff_set_reset_supply_referenced) | 带 SETB/RSTB 和互补输出的上升沿 D 触发器。 | `` L4_DFF_VA(SETB,RSTB,CLK,VDD,GND,D,Q,QB) `` | `` real tr = 10p ``；`` real td = 0 ``<br>门限取电源中点；原代码的置位、复位与时钟事件优先关系需结合用例检查。 |
| [mod6_counter_onehot.va](mod6_counter_onehot.va)<br>[来源](../../SOURCES.md#lab-logic-mod6_counter_onehot) | 模六计数，同时输出三位二进制计数和六路独热选通信号。 | `` V_counter(CLK, DOUT, S) `` | `` vdd = 0.9 ``<br>CLK 下降沿计数，输出电平由 vdd 决定。 |
| [nand2.va](nand2.va)<br>[来源](../../SOURCES.md#lab-logic-nand2) | 两输入与非门，以电压门限解释逻辑并平滑输出。 | `` nand2(out, in1, in2) `` | `` real vh = 1.1 ``；`` real vl = 0 ``；`` real vth = 0.55 ``<br>高低电平、门限、延迟和过渡时间可配置。 |
| [nor2.va](nor2.va)<br>[来源](../../SOURCES.md#lab-logic-nor2) | 两输入或非门，以电压门限解释逻辑并平滑输出。 | `` nor2(out, in1, in2) `` | `` real vh = 1.1 ``；`` real vl = 0 ``；`` real vth = 0.55 ``<br>高低电平、门限、延迟和过渡时间可配置。 |
| [or2.va](or2.va)<br>[来源](../../SOURCES.md#lab-logic-or2) | 两输入或门，以电压门限解释逻辑并平滑输出。 | `` or2(out, in1, in2) `` | `` real vh = 1.1 ``；`` real vl = 0 ``；`` real vth = 0.55 ``<br>高低电平、门限、延迟和过渡时间可配置。 |
| [or3.va](or3.va)<br>[来源](../../SOURCES.md#lab-logic-or3) | 三输入或门，用于电压域控制逻辑建模。 | `` or3(vin1,vin2,vin3, vout) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 1.4 ``<br>默认使用 5 V 电平与微秒级延迟。 |
| [rs_latch_lab_copy.va](rs_latch_lab_copy.va)<br>[来源](../../SOURCES.md#lab-logic-rs_latch_lab_copy) | 置位优先的 RS 锁存模型，输出互补电平。 | `` rs_ff(vin_s, vin_r, vout_q, vout_qbar) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 2.5 ``<br>来自课题组 ahdlLib 副本；置位和复位同时有效时保持置位。 |
| [toggle_ff_lab_copy.va](toggle_ff_lab_copy.va)<br>[来源](../../SOURCES.md#lab-logic-toggle_ff_lab_copy) | 每个输入上升沿翻转状态；可用于二分频和状态控制。 | `` t_ff(vtrig, vout_q, vout_qbar) `` | `` integer initial_state = 0 from [0:1] ``；`` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``<br>支持初始状态及互补电平输出。 |
| [xor2.va](xor2.va)<br>[来源](../../SOURCES.md#lab-logic-xor2) | 两输入异或门，以电压门限解释逻辑并平滑输出。 | `` xor2(out, in1, in2) `` | `` real vh = 1.1 ``；`` real vl = 0 ``；`` real vth = 0.55 ``<br>高低电平、门限、延迟和过渡时间可配置。 |
| [xor3.va](xor3.va)<br>[来源](../../SOURCES.md#lab-logic-xor3) | 三输入异或门，用于奇偶逻辑。 | `` xor3(vin1, vin2,vin3, vout) `` | `` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 1.4 ``<br>默认使用 5 V 电平与微秒级延迟。 |
