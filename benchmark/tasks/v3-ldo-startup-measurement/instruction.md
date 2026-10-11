# LDO 启动在线测量

为固定晶体管 LDO 编写只读观测模块 `ldo_startup_meter(vin,vout,t90_us,overshoot_mv,settle_us,reached,settled,status,done)`。参数 `tick=50ns,ramp_start=1us,ramp_end=21us,window=70us,target=1.2,tail=20`，隐藏条件可改 ramp_end 至17..25us、window至60..80us、VIN高值至1.0..1.8V、固定RLOAD至60..240Ω、COUT至0.5..2µF。tick、target、tail固定。

每个全局 i*tick 从t=0至window采样实际vout。t90是最早一个样本满足输出≥0.9*target且后续所有样本也满足的时刻，减ramp_start，单位µs。不存在则t90_us=-1,reached=0；存在则reached=1。overshoot_mv=max(0,全部样本最大值-target)*1000。建立是ramp_end后最早一个样本在target±2%且其余样本始终在带内，并至少有末20个连续样本的时刻。settle_us是该时刻减ramp_end，单位µs。不存在则settle_us=-1,settled=0。ramp_end与window为tick整数倍。

任何样本出[-0.1,2.2]V则status=4；否则未达90%为2，否则未建立为3，否则为1。数值与有效位仍按各自定义输出。done在window采样后变1。全部报告端在此之前为0，此后保持至仿真结束。边沿可在5ns内过渡。终评报告误差t90/settle≤0.075µs，过冲≤0.3mV，逻辑与status≤0.002V。原来源的记录采样定义沿用；这里明确增加末20样本资格，防止末尾单点入带误报。

## 输入与修改权限

只提交 `/work/dut.va`。公开目录含实际 ADB OTA5 LDO、固定 SKY130 TT 模型、固定外围网络和公开自测。候选不得驱动观测端或修改环境、DUT、模型。固定零压串联探针观测所有候选只读端电流，任一记录点绝对值不得超过0.1nA。该上限允许数值噪声与极小输入负载，候选不能向DUT提供显著电流。目标恒为规格 1.2 V，不能取末端测量值代替。数值结果由电压报告端承载。输入输出端使用全局0作参考。正常和不合格 DUT 都按同一测量定义验收，正确报告失败也通过。

本题固定 Spectre 后端，属于商业仿真器扩展集。源电路能在 ngspice 运行，但本题候选 VA 与电流环境尚未完成开源后端等价校准。公开 `public.scs` 仅是自测条件，终评在公开范围内改变固定环境。编译或后端失败属于待归因环境结果，不作为语义错版拒绝。

