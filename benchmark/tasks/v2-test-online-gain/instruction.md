# 实际放大器在线增益仪表

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 gain_estimator(VDD,VSS,vinp,vinn,voutp,voutn,gain_out,valid,begin_round)。每sample_period=1ns的全局整倍时刻采样实际输入和输出差分，从start_time=20ns起累计极值。输入跨度严格大于min_input_span=0.02V时valid为供电高，gain_out=(VDD-VSS)*输出跨度/输入跨度/gain_scale，gain_scale=10。小跨度保持valid低、gain_out=0。begin_round穿过0.5V上升清极值、报告和valid，新轮重新收集。不得读取放大器内部增益或clipping作为测量结果，不得把输出替换成独立信号源。tedge=200ps；事件后350ps允许平滑，误差2mV。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。运行 `python /tests/verify.py --candidate /work/dut.va --output /logs/verifier --tests /tests` 自测，正式条件和数值容差公开于 public/cases.json。
