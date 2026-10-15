# 优化采样非均匀阈值flash ADC的仿真实现

将 `/work/public/starter.va` 改成 `/work/dut.va`，保持以下电路行为并降低给定固定负载的实际仿真成本。
只提交dut.va，不写额外结果文件。公开输入包含原始合格基线和visible.scs，可用其自测。

模块 `offset_flash(vin,clock,code)`。255个有序阈值：
vref*(k/256+skew*(k/256)*(1-k/256))，k=1..255，skew在[-0.3,0.3]。
上升clock阈值0.5V时采样，码是输入不小于的阈值个数，归一化为code/255，初码0。
采样间保持，delay=0.2ns、线性rise=0.3ns须保留；sample/hold及边沿电压误差0.3mV。
固定负载100us、100MHz采样、10000次转换；另检查不同vref和正负skew。

性能评分使用Spectre 21.1.0.509.isr12、`+mt=1`、psfascii，网表固定reltol=1e-6、
vabstol=1e-9、iabstol=1e-14、errpreset=conservative。不能改网表、容差、真实工作量、
输出有限边沿或规定分辨率取得成绩。最终满分要求所有功能条件通过，且同一job同机执行
的两侧warmup与五对交替求解每次都通过独立波形判据。性能条件可在其他功能条件之前
执行，但任何功能失败都会使整题失败；失败运行不能进入计时分母。

规定intrinsic tran CPU候选中位数/基线中位数不超过0.97，
且五对中至少4对候选成本低于基线。CPU仅取原生intrinsic tran分项，
编译/许可证/启动/网络单独记录，不参与该CPU指标；steps只能取原生日志，PSF点数不能代替。
未变更基线可通过功能但不能取得性能分。终评同时保留端到端过程计时、原生版本/负载及全部原始波形。

允许重新组织内部实现；所有公开接口/参数、采样/状态/波形合同保持。禁止active日志输出及
仿真终止/控制system tasks，防止伪造native统计或提前退出。标准disciplines.vams/constants.vams可include；
无额外非声明include，宏、系统调用、环境读取和外部文件读取不在提交合同内。参考优化源码不在公开输入中。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
