# 开关电容两相非重叠时钟实验

为采样与传递两级开关电容链产生两相时钟。提交模块参数 period=100 ns、dead=5 ns，隐藏条件 period=100/120/160 ns，dead=3/5/9 ns。每周期 phase1 高窗 [dead,period/2)，phase2 高窗 [period/2+dead,period)。高电平 1 V，低电平 0 V，稳定电平允许0.01 V误差，边沿过渡 0.1 ns，允许每个 0.5V 边沿相对窗口边界最多 0.3 ns 偏差。运行12周期，要求两相均完整活动，并且每次交换有规定死区。下游电压域采样级在 phase1 上升采集 vin，在 phase2 上升传递为 z；终评同时检查下游采样值误差不超过2mV，禁止把两相并接。此题只要求完成刺激环节。

提交 `/work/dut.va`，module `dut(p1,p2)`，所有端口均为 electrical。电压数值代表题面规定的单位。仅使用 Verilog-A 标准头文件；不读写文件，不执行外部命令。允许调整内部实现。公开自测见 `/work/public/`，终评分只改变公开列出的参数和故障模式，核验真实激励与原始观测，然后核验结果端口。测量最后一个窗口之后保持结果至仿真结束。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
