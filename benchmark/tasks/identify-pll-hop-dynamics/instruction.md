# 从PLL跳频轨迹辨识闭环动态

这个原创PLL行为对象有相位反馈与积分校正，用于频率合成器跳频后的重捕获预测。
你要从固定loop的完整跳频实验辨识电压可观察行为，预测频率超调、建立和输出相位。
不要求从闭环数据唯一恢复charge pump、VCO或loop filter的器件参数。

交付 `/work/dut.va`，模块 `identified_pll`，electrical端口 `(cmd,out,tune)`。
cmd是已解码的频率设定电压，1 V表示1 MHz；起点cmd=0.8 V，
参考与输出相位都为0 cycles。参考相位是cmd*1 MHz的时间积分。
out是单位幅度sinusoidal时钟电压；tune是固定监测器，将瞬时输出频率以1 V/MHz编码。
它不是对物理VCO控制端或负载的建模。候选只实现电压行为。

public CSV包括cmd、out、tune以及通过连续相位跟踪计算的reference减output相位差。
单位为s、V、cycles。该相位差是表征观察，不是要求你提交的内部状态。
数据身份为本项目 `behavioral_synthetic`，没有silicon测量、ADIsimPLL输出或器件电路表征。
四次实验来自同一个固定相位反馈系统。可自主选择辨识算法。

允许cmd在0.65至1.2 V之间跳变，第一次跳变8至20 us，
后续跳变至少间隔20 us，观察时间不超过200 us。模型须保留尚未建立时再次跳变的状态。
不要求PVT、RF功率、phase noise、随机抖动、输入电流或负载耦合。

终评在完整隐藏实验检查tune逐窗误差不超过0.3 mV，
out的相位一致波形误差不超过8 mV；最终跳变100 us后tune必须保持在目标0.3 mV频率带内。
测试输入边沿1 ps，最大观测步10 ns。既不能仅查lock flag，也不能只拟合最终频率。
公开网表可自测，最终只提交dut.va，不读终评、不写文件、不执行系统命令。
