# CDR判相脉冲模型
在数据恢复环中，判相器用数据边沿、时钟电平及已重定时数据形成advance/retard请求。实现 `cdr_phase_detector(data,clk,retimed,up,down)`，前三端输入，后两端0/1 V输出，全部electrical。参数 `vth=0.5 V,tr=50 ps`。
每个data上升或下降穿越vth时，clk高且retimed低则up=1/down=0；clk低且retimed高则down=1/up=0；其余组合全低。已发布脉冲保持到下一个clk任意方向穿越；禁止UP/DOWN同时高。retimed在没有data边沿时变化不得独自发脉冲。初态全低。输出有限tr平滑，无额外延迟。
输入边沿之间至少200 ps，电平0/1 V；单个脉冲不小于200 ps。不考查同刻边沿仲裁或完整CDR锁定。评分检查方向、完整脉冲数量/50%边沿时刻与脉宽，电平20 mV、时间80 ps容差。用不同data相位的公开/隐藏条件检查早晚数据与无修正关系，不能按时间重放模板。

提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
