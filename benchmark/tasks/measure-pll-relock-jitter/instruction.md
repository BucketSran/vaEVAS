# PLL 重锁时间与周期抖动表征

ref为100ns参考时钟，clk为反馈时钟，1us发生跳频后相位重捕获。初始已锁定，1..2.2us获取阶段，允许相位偏移按周期收敛，公开settle_cycles为3/5/7。重锁定义是在1..2.2us期间首次出现连续4个clk上升沿均距最近ref上升沿≤3ns的序列，以该序列第一沿减1us作为relock_ns，单位ns。不能用第4沿时间或1us前锁定状态。2.2..4.2us稳定段有交替确定性相位抖动0.5/1/1.5ns，围绕2ns共模偏移；其首沿开始20周期窗口。jitter_ns为窗口内相邻20个clk上升沿产生的19个周期的总体标准差sqrt(mean(T²)-mean(T)²)，单位ns，移除均值，非TIE RMS，非峰峰值。4.4us前完成，重锁容差0.3ns，抖动容差0.02ns。终评直接提取原始ref/clk边沿独立计算，数据为behavioral_synthetic。

提交 `/work/dut.va`，module `dut(ref,clk,relock_ns,jitter_ns)`，所有端口均为 electrical。电压数值代表题面规定的单位。仅使用 Verilog-A 标准头文件；不读写文件，不执行外部命令。允许调整内部实现。公开自测见 `/work/public/`，终评分只改变公开列出的参数和故障模式，核验真实激励与原始观测，然后核验结果端口。测量最后一个窗口之后保持结果至仿真结束。
