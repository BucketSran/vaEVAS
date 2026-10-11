# 实际放大器静态增益和有限建立

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 gain_settling_meter(vin,static_out,dynamic_out,launch,gain,gain_valid,settling_ns,settled,status)。固定台分别实例化静态038和动态370，二者并联观测相同输入，不是级联；只读端口没有内部settled标志。首个launch上升沿前，gain、gain_valid、settling_ns、settled、status均为0；有效标志为0时，数值报告仍须按本合同初始化或保持。launch上升捕获输入和静态输出基线，清报告，随后每250ps采样动态输出80次，观察窗口20ns；输入在第一个采样前改变后保持，第二轮重新捕获全部状态。跨度边界按1pV数值比较容差验收（abs(span)≤0.02V+1pV为无效），正常与慢DUT激励均离开该边界。窗口末输入与基线跨度无效时status=2、其余报告0；否则gain=实际静态输出变化/实际输入变化、gain_valid=1。最终static_out定义观测目标。所有81个动态样本包括基线中，最后一个误差大于2mV的样本之后第一个样本定义settling_ns；完全无超差为0。末8个样本都在2mV内才settled=1、status=1并报告建立时间，否则settled=0、status=3、settling_ns=0，仍报告实际静态gain。收集中status=0。只证明公开有限观察窗口，不能宣称无限时间稳定；不达标动态也可被正确仪表测量并通过。tr20ps、guard80ps，gain误差0.02，建立时间0.03ns，其余3mV。

## 公开自测与终评范围

静态放大器增益固定2.5，动态alpha为0.01至0.35；vin基线与阶跃值在0.42至0.49V。每轮launch后200至240ps内完成输入阶跃，随后保持至窗口末；可有有效跨度、无效跨度或窗口内未建立DUT。各轮相隔至少25ns；固定80次采样和末8样本条件不变。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。公开自测实例位于 `/work/public/cases.json`，固定DUT实现位于 `/work/public/dut/`，可据此运行自己的Spectre自测。终评在提交后使用合同范围内不同的参数、事件及故障实例；终评台架和checker不进入解题材料。判定目标与数值容差以本题公开合同为准。
