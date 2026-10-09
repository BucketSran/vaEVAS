# SAR 转换完整验证流程

SAR ADC 前端验证需要同时检查采样值、转换握手和复位中止。器件将 vin 的 0..1 V 转为 4-bit unsigned code 电压。start 上升沿在空闲时接收请求；器件每 10 ns 检查端口，接收后 4..6 个 tick 发出宽 10 ns 的 done，code=floor(16*vin) 限幅 0..15。忙时请求忽略。rst 低立即在下一 tick 中止并清零，不允许旧 done。

实现完整激励与自动判定。运行 1.2 us，每 200 ns 一次转换。第 k 个周期 vin=(2*(k mod 6)+1.25)/16 V，主 start 在周期内 31..42 ns，忙时 start 在 51..62 ns。初始 rst 在 0..21 ns 为低，第 k=2 周期在 65..76 ns 拉低中止。边沿过渡不超过 0.2 ns。其余 rst=1、start=0。独立终评检查刺激覆盖和每个实际请求/输出。verdict 初值 0，发现错误锁存 1；正确器件最终应为 0。需拒绝一码偏移、忙时重新接收、复位后旧结果三类器件。判定允许 code 0.1 V 误差，done 必须在请求后 35..75 ns；监测至结束。器件故障模式终评可注入，候选不能知道其参数。

提交 `/work/dut.va`，module `dut(vin,start,rst,code,done,verdict)`，所有端口均为 electrical。电压数值代表题面规定的单位。仅使用 Verilog-A 标准头文件；不读写文件，不执行外部命令。允许调整内部实现。公开自测见 `/work/public/`，终评分只改变公开列出的参数和故障模式，核验真实激励与原始观测，然后核验结果端口。测量最后一个窗口之后保持结果至仿真结束。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
