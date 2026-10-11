# thermometer

实现 `/work/dut.va`。模块 dut(seg0,seg1,seg2,seg3,seg4,seg5,seg6,seg7,seg8,seg9,seg10,seg11,seg12,seg13,seg14,clk,rst,aout)；lo=0V、hi=1V、tr=100ps 可覆盖，lo在0至0.2V、hi在0.8至1.1V、tr在50至300ps。控制引脚严格大于0.45V为1，阈值相等为0；clk以0.5V上升沿采样，只在该沿更新，其他时刻保持，rst未使用且固定0。初态aout=lo。每个输入权重按端口顺序为 [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]；aout=lo+(hi-lo)乘以活动权重和除以全活动权重和。任意独立单元模式均合法，包括温度计气泡；亚基数自然二进制码可以非单调，不要求修正。输出必须形成真实模拟电压。

固定后端 Spectre，候选源码按原字节运行，不作语言子集限制。仅 dut.va 可修改；输入及固定器件只读。测量题各电气报告端口的电压数值就是指标数值，例如0.5LSB用0.5V、20dB用20V，valid用0或1V。初态及事件后允许1ns建立，之后输出绝对误差1mV，频谱dB误差0.03dB、ENOB误差0.006bit。输出可用 transition(...,0,100p,100p)；无需复制参考结构。公开台架见 `/work/public/cases.json`，终评改变合同内输入、端点、样本和控制时刻。测量 DUT 性能差仍可通过，评分只看报告正确。源代码、reference与私有checker不进入公开包。
