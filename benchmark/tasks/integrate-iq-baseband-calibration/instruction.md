# 集成 I/Q 基带幅相校准

接收机基带的I/Q两路存在增益、正交相位串扰和DC偏移。已有系数寄存器与采样限幅模块，原始顶层尚未把校准算子接入。请实现并集成2x2逆校准，保持bypass和输出采样行为。

提交 `dut.va` 与 `rtl/coeff.va`、`rtl/inverse.va`、`rtl/sample.va`。顶层 `iq_calibration(ri,rq,a,b,c,d,oi,oq,apply,clk,bypass,reset,out_i,out_q,clipped)`。输入ri/rq单位V，校准描述前向失配 `ri=a*I+b*Q+oi`、`rq=c*I+d*Q+oq`。a,d为0.6至1.4，b,c为-0.4至0.4，oi/oq为-0.2至0.2 V，所有提交系数组合满足det=`a*d-b*c >=0.2`。apply以0.5 V上升交越锁存6个系数，未apply的端口变化不得改变校准。reset上升使系数恢复单位矩阵、偏移为0，清零输出和clipped；reset高时禁止apply和clk采样。

每个clk上升沿采样校准后的两路，公式 `I=(d*(ri-oi)-b*(rq-oq))/det`、`Q=(-c*(ri-oi)+a*(rq-oq))/det`。bypass高则直接采样ri/rq。无论何种路径，分别限幅到[-1,+1] V，任一路限幅前绝对值大于1时clipped=1，否则0。输出和clipped在两次采样之间保持，bypass或ri/rq变化不能提前改变已采样结果。clk周期4至6 ns，apply距clk至少0.4 ns，数据距clk至少0.2 ns。输出事件后0.15 ns内建立，电压误差0.003 V，标志误差0.01 V。工程只要求电压域，不要求模拟输出阻抗。

公开工程在 `/work/public/`，请在 `/work/` 建立提交工程，入口为 `/work/dut.va`。可修改的提交文件清单见公开 `SUBMISSION.json`。同目录运行 `python3 public/smoke.py --candidate /work/dut.va` 可检查公开波形。终评输入均在上述合同范围内，不能访问隐藏测试或用时间表输出答案。

<!-- generated submission policy -->

## 源码与文件合同

终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 `disciplines.vams`、`constants.vams`、`dut.va`、`rtl/coeff.va`、`rtl/inverse.va`、`rtl/sample.va`。不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。

候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。本题不允许打开文件。无法编译、超时或不能产生完整规定波形的提交计零分。

<!-- end generated submission policy -->
