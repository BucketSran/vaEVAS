# 连续 OTA 双向阶跃测量

实现 `stimulus_meter(vin,enable,launch,vout,gain,slew_metric,settle,valid,status,direction)`。vout是只读观测，其余是候选驱动。DUT源码 `/work/public/dut.va` 可读，仅通过波形测量，不能拿内部参数或预计表冒充实际结果。

输入初始0.75 V；enable初始0，在10 ns升1.5 V。200、400、600、800、1000、1200 ns依次驱动vin为0.8、0.7、1.2、0.3、1.6、0.75 V，边沿10 ps。每个阶跃同时升launch=1并清valid/status=0。每轮在阶跃后1至180 ns按1 ns采样vout。阶跃前的vin与vout为基准。尾20点均值F作为有限窗口稳态估计；gain=(F-基准输出)/(新输入-基准输入)，单位V/V；slew为相邻采样点及基准至首点的最大绝对输出差，单位V/ns。direction为输入正负方向，+1或-1。

建立判据是相对F的3 mV带内，lastbad为最后越带样本编号1至180，无越带为0。lastbad<=160才表示连续末20样本建立，settle=lastbad+1 ns；否则settle=180 ns。完成后status依次优先4表示输入跨度<20 mV、3表示F<=0.105或>=1.395 V限幅、1表示建立、2表示窗口未建立。valid仅status=1时为1。测量慢或限幅DUT时，报告对应状态也可通过。完成后launch=0，报告保持至下一轮；新一轮不得沿用旧valid。

DUT隐藏条件仅改变tau=17至300 ns、正slew=0.001至0.012 V/ns、负slew=0.0006至0.006 V/ns、gain=0.96至0.99；其余合同相同。独立checker从实际激励与波形计算指标，gain误差<=0.003，slew_metric<=0.001 V/ns，settle<=2 ns，状态和方向误差<=0.01 V。

交付 `/work/dut.va`；只修改此文件。固定后端 Spectre，候选原字节执行，后端编译或执行故障须诊断，不能自动计为语义零分。公开自测 `/work/public/cases.json` 和只读外围可用，终评只改变公开范围内的完整实验条件。权重 1。
