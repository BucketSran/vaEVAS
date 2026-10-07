# 异步 UART 接收器采样日历候选

原创8N1接收行为模型，用于模拟系统内稀疏状态消息：固定115200baud、100ms内10帧，
每帧实际接收8数据位并验证stop，另有一段短假start。baseline采用16倍波特率全局
轮询，每轮真实读取rx/reset；reference在下降start边沿后调度半bit资格校验及各bit
中心，不在空闲期轮询。真实位数、wire消息、nominal波特率及漂移保持不变，没有人为
放大级数、spin、死代码或修改外部网表maxstep。

16倍采样是实际UART架构采用的正常模式，见 [Microchip USART配置](https://developerhelp.microchip.com/xwiki/bin/view/products/mcu-mpu/8-bit-avr/peripherals/usart/8-bit-avr-usart-mega-configuration/)。
该来源仅支持采样架构的工程用途；本模型是独立编写的公开简化中心采样合同，不复制
厂商实现，不宣称具备其多数表决、FIFO或全部抗噪能力。输入合同包含±2%发送时钟漂移、
持续0.2/0.3bit的短假start、坏stop及reset中断，不含恰落采样中心的额外毛刺。

输出busy从被接受的start到stop中心（或假start半bit取消）；valid在正确stop时
置位，到下一start/reset清除；error在错误stop时置位，到下一start/reset清除。
data完成正确帧才更新、按255归一化，错误stop保持旧码；shift公开实际LSB-first
移入进度并在start/reset清零。输出有限线性边沿10ns。reset取消在途帧并清所有状态。
不能预知最终消息、跳过真实位采样或丢掉输出边沿。

oracle从公开rx/reset的PWL独立求阈值边沿，逐中心读取wire并构造八位序列及stop判据，
没有从模型或reference输出定义正确性。事件容差0.08bit大于16x检测量化(最大0.0625bit)，
稳定电压误差4uV；相对观测输出中点检查25/75% finite transition。全部稳定点逐点
核验，避开公开0.09bit事件邻域。3case覆盖稀疏吞吐、framing/reset恢复、57600baud和
两次假start。八倍采样是负例候选，须actual证明违反公开时刻合同，不能假定必拒。

本候选尚无actual Spectre、未声明收益、不计正式题。纯fixture已核验主case10good帧/
80数据采样/1false start，resetcase2good+1framing/26采样/1取消，57600case2good/
16采样/2false start；这些不是VA执行证据。

请协调者先通过已有harness运行baseline/reference的全部3条件，probe为
`probes/optimize-uart-calendar`。通过后用native accepted步骤及intrinsicCPU/elapsed
定位oversampling轮询成本，负控短case及不同baud也保留。若没有可重复成本信号，退回
候选，不降低合同。选题鉴定后再交替5对，保存源码/判据/Spectre版本/真实工作数/
失败数/负载/编译与许可证/独立process计时，遵循REPEAT_REQUEST。
