# 扩展四通道采样与顺序读出

在提供的健康单通道 `sample_hold` 上完成四通道工程。固定后端为 Spectre。
只修改 `/work/dut.va`。`public/baseline.va` 是固定单通道部件，必须复用四实例，不得复制或另写其采样职责。允许增加适配、控制与连接模块，不要求固定文件数。

提供 `sample_mux_readout_top(ch0,ch1,ch2,ch3,clk,rst,sample,read,out,ch_sel_1,ch_sel_0,valid)`，全为electrical端口。参数vdd=.9、vth=.45、tr=100ps，输出逻辑高vdd，逻辑低0。

固定部件接口 `sample_hold(VDD,VSS,IN,CLK,OUT)`。OUT初值为VSS；CLK相对VSS上升越过vth时保存IN相对VSS，tedge=100ps单调过渡；停钟保持，无下垂。四实例VSS接0，VDD接vdd。输入在采样沿前后至少1ns稳定，允许采样适配延迟不超过50ps。

rst为高时禁止采样。rst上升沿及rst为高的clk上升沿清读指针、out、sel和valid。同时清四通道帧，包含采样适配时钟仍高时的reset；清零在reset上升后1ns内完成。固定保持部件没有reset，集成适配应在reset时将四输入切换为0并产生一次有效采样；恢复正常模式后仍使用同一部件。

每个clk上升沿，sample高时同时采集四通道。read高时按0、1、2、3循环读出，out保存该帧该通道，sel为当前out通道，valid置高。sample与read同时为高时读出上一帧，然后采集新帧。read低时保持out与sel，valid置低且不推进指针。sample只更新帧，不能改变正在保持的out。后续read才读到新帧。

模块交互须实际生效。单通道部件始终保留，不允许用输出常数、测试激励或预计算答案替代部件调用。公开自测可观察输出与内部保持节点，终评从端口波形独立验同时采样、顺序、暂停、刷新、reset和旧保持行为。电压容差3mV，事件完成后1ns测量。

架构验收版本 `sample-hold-causal-v2`。除上述健康部件条件外，终评可将出题方的 `sample_hold` 替换为同端口诊断部件。诊断部件保留OUT初值0、CLK相对VSS上升阈值vth、100ps单调过渡及停钟保持，只将采样值改为0.75或0.6乘IN相对VSS。集成必须透明使用该部件的输出，不能补偿诊断增益或另行采样重建帧。四输入、同时采样、旧帧读出、暂停与reset适配规则不变；清帧采样输入0在诊断部件中仍为0。终评从顶层端口独立核对每通道对应诊断保持值，电压容差仍为3mV。本规则用于验证部件实际参与，不按源码相似度或实例数量评分。
