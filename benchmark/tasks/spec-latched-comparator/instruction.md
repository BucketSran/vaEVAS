# 锁存比较器：决策延迟与复位取消
ADC的动态比较器在采样沿锁存输入，经再生延迟产生互补决策。完成模型 `latched_comparator(clk,rst,vinp,vinn,outp,outn,ready)`，全部electrical，后三端输出0/1 V。
参数 `vth=0.5 V, voffset=2 mV, tbase=0.2 ns, tau=0.25 ns, vscale=50 mV, vfloor=1 mV, tr=50 ps`，保持可覆盖。时钟/复位逻辑0/1 V，输入共模0.6 V，差分输入在±60 mV；clk上升/下降及rst上升均按vth穿越。
clk上升时先清空输出，若rst低则锁存 `d=vinp-vinn-voffset`；非零d在 `tbase+tau*ln(1+vscale/(abs(d)+vfloor))` 秒后，正d令outp=1/outn=0，负d相反，ready=1。d=0不产生决策。此合成再生延迟合同描述过驱动增加时决策加快，不是晶体管测量数据。
在同一高相，输入变化不能改变已锁存的符号或完成时间。clk下降或rst上升立即清空三输出并取消尚未完成的决策；低相不得出现旧ready。输出通过tr的有限平滑转换，无额外延迟。
验收逻辑电平误差≤20 mV，50%边沿时间误差≤80 ps，检查所有边沿和完整低/高相稳定段。初态全低。公开和隐藏只改变上述范围内输入、相位长度及复位，算法结构不限。

提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
