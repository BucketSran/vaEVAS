# 电源监控：UVLO毛刺拒绝与棕断恢复
电源启动时短暂越过阈值不能提前解除系统复位；棕断后恢复也必须重新资格确认。实现 `uvlo_monitor(vin,rst,pgood,fault)`，全部electrical，pgood/fault为互补0/1 V。参数upper=0.65 V,lower=0.55 V,tgood=2 ns,tbad=1 ns,vth=0.5 V,tr=50 ps，保持可覆盖。
初态pgood=0。rst高立即清零pgood、fault=1并取消全部计时。rst低时，vin连续严格高于upper达tgood，才置pgood=1；任何返回≤upper都取消尚未完成的启动计时，不能累积多个短脉冲。pgood=1后，vin连续严格低于lower达tbad才清零；任何回到≥lower都取消尚未完成的棕断计时。lower至upper之间保持当前pgood。rst释放时若vin已高于upper，重新从释放时刻计满tgood。fault=1-pgood；输出通过tr平滑，无额外延迟。
vin范围0.4–0.85 V、tgood1–4 ns,tbad0.5–2 ns，输入线性边沿≥40 ps，所有计时相对实际阈值交点；不测试计时截止与输入交点完全重合。验收完整pgood/fault边沿、短脉冲拒绝、滞回保持、复位重启，电平20 mV、时间100 ps容差。模型只表达电压监控行为，不含电源电流或稳压环。

提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
