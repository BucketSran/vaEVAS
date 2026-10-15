# 响应驱动 LDO line/load 表征

实现 `ldo_experiment`，完整端口和默认参数见starter.va。vout只读。line_cmd与load_cmd是唯一允许驱动的命令，固定适配器将line_cmd变成实际VIN，load_cmd的1V增加10mA电流负载，基线RLOAD=120Ω。原DUT与反馈、1µF/50mΩ输出网络可读。输出不是理想一阶模型。

必须按startup,line_up,line_down,load_up,load_down顺序执行，stage对应0..4，全部结束stage=5,done=1。startup的line_cmd在1µs开始线性上升，在ramp_end=21µs达到1.8V，load_cmd=0。startup后line_up命令1.95V；line_down恢复1.8V；load_up保持1.8V并设load_cmd=1V；load_down恢复load_cmd=0V。每个命令改变后保持至下一阶段，完成后保持1.8V/0V。命令边沿1ns内，报告5ns内。

所有阶段只在全局i*tick采样实际vout，tick=50ns。若实际输出在target=1.2V±band=0.024V连续qualification=20个样本，并完成min_window=8µs，才进入下一阶段。startup最短到ramp_end，仅ramp_end及以后的样本可资格；startup_timeout=70µs。其余阶段timeout=40µs。超时也推进并报告status=2，取得资格报告status=1。不许跳过扰动、提前推进或无限等待。每阶段从命令变更后的下一tick采样，startup从t=0采样。

每阶段独立重置峰值与资格历史。端口名为阶段名加_peak_mv、_offset_mv、_recovery_us、_status。peak_mv是该阶段样本与1.2V的最大绝对偏差乘1000；offset_mv是结束样本减1.2V乘1000；recovery_us是形成最终连续资格的首样本减阶段起点乘1e6，超时未资格为-1。已完成阶段报告保持，未完成阶段报告0。初态done=0,stage=0。比如输出先入带又振铃出带，恢复起点必须重置，不能沿用首次入带。正确测得不合格阶段可以通过，始终报告失败不能通过健康DUT。

终评可在公开范围改变ramp_end=17..25µs，COUT=0.5..2µF、RLOAD=100..150Ω、VREF=0.76..0.8V，其余参数与命令固定，最长运行到240µs。所有输出峰值/偏移误差≤0.3mV，恢复时间≤0.075µs，状态≤0.002V，line/实际VIN≤1mV，load_cmd≤0.002V，适配电流报告≤20µA。


## 输入与修改权限

只提交 `/work/dut.va`。公开目录含实际 ADB OTA5 LDO、固定 SKY130 TT 模型、固定外围网络和公开自测。候选不得驱动观测端或修改环境、DUT、模型。固定零压串联探针观测所有候选只读端电流，任一记录点绝对值不得超过0.1nA。该上限允许数值噪声与极小输入负载，候选不能向DUT提供显著电流。目标恒为规格 1.2 V，不能取末端测量值代替。数值结果由电压报告端承载。输入输出端使用全局0作参考。正常和不合格 DUT 都按同一测量定义验收，正确报告失败也通过。

本题固定 Spectre 后端，属于商业仿真器扩展集。源电路能在 ngspice 运行，但本题候选 VA 与电流环境尚未完成开源后端等价校准。公开 `public.scs` 仅是自测条件，终评在公开范围内改变固定环境。编译或后端失败属于待归因环境结果，不作为语义错版拒绝。

