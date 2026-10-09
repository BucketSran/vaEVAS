# 对齐 pipeline ADC 的级间数据

工程用两相时钟把6位ADC分成3位粗转换和3位残差转换。粗级在上升沿采样，细级在随后的下降沿处理同一次采样的残差。原始顶层直接组合粗码和细码，会在连续采样时混合两次转换。请扩展顶层寄存器与valid路径，保持两级接口和量化规则。

提交 `dut.va`、`rtl/coarse.va`、`rtl/fine.va`，顶层 `pipeline_adc(vin,clk,reset,result,valid)`。输入vin为0至1 V，clk和reset以0.5 V交越；时钟周期3至6 ns，占空比50%，模拟输入在上升沿前后0.2 ns保持稳定。上升沿采样N=`min(63,max(0,floor(64*vin)))`，结果电压为0.01*N V。第一次有效上升沿只填充流水线，valid=0，result=0。以后每个上升沿输出上一次上升沿采样的N，valid=1，结果保持到下一输出事件。时钟停止时结果及valid保持。

reset上升立即清除输出与valid，reset高电平的时钟不填充流水线；reset解除后的第一次上升沿仍只填充，第二次才输出新样本。复位不能让旧细码泄漏。结果误差0.002 V，valid误差0.01 V，事件后0.15 ns建立。不要用公开输入轨迹硬编码答案。内部coarse/residue/fine可重写实现，但不得改变合同的采样相位、输入范围和延迟。

公开工程在 `/work/public/`，请在 `/work/` 建立提交工程，入口为 `/work/dut.va`。可修改的提交文件清单见公开 `SUBMISSION.json`。同目录运行 `python3 public/smoke.py --candidate /work/dut.va` 可检查公开波形。终评输入均在上述合同范围内，不能访问隐藏测试或用时间表输出答案。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`、`rtl/coarse.va`、`rtl/fine.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
