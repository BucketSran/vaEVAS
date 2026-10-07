# SAR转换中止：取消待发布结果
一个四位SAR控制器按比较器反馈逐位试探电压，并在最后判决后延迟发布码。starter包含人工注入的复位取消遗漏，复位落在最后判决到发布之间时可出现旧结果。修复 `sar_controller(clk,start,rst,cmp,d3,d2,d1,d0,trial,busy,valid)`，前四端输入，其余输出，全部electrical。端口cmp高表示固定外围ADC比较器判断vin≥trial；原外围比较器与激励不可修改。
参数vth=0.5 V,tr=50 ps,tvalid=0.8 ns（允许0.4–1.2 ns）。trial范围0至15/16 V，其他输出0/1 V。初态全部低。rst上升清空结果码、trial、busy、valid，取消未完成的转换和待发布结果；rst高时忽略start/clk。
空闲且rst低的start上升清空码和valid，置busy，开始四次判决，首先trial=8/16 V。每个clk上升采样cmp，按MSB到LSB决定是否保留该位，再驱动下一试探码/16。第四判决后trial=最终码/16，仍保持busy；经过tvalid才发布四位码并置valid=1/busy=0。busy时新的start被忽略。空闲结果和valid保持至下次start或复位。
四位量化器使用floor(16*vin)并限幅0..15；输入0.02–0.98 V且距离码边界≥5 mV、在转换期间不变。clk周期4 ns，cmp建立≤100 ps，事件间距≥200 ps，reset可落在判决与发布之间。不得在低时钟或复位后发布旧码。电平容差20 mV，所有边沿80 ps；trial逐位值也独立检查。

提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
