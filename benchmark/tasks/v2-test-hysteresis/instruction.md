# 比较器双向滞回表征

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 `hysteresis_meter(vin, cmp_out, begin_round, up, down, width, valid)`。输入均为只读观测，输出以伏报告输入捕获值，逻辑高低为1V与0V。`tr=20ps` 为输出边沿参数。比较器输出穿过0.5V上升/下降时，分别捕获实际 `vin` 到 up/down；同一轮两方向都捕获后，width=up-down，valid=1。begin_round穿过0.5V上升时清零全部报告与方向历史。新轮缺少任一方向必须保持valid=0；没有begin事件时初始轮从t=0开始。每方向的后续边沿刷新对应值。比较器延迟已包含在实际捕获点中，不能按DUT参数直接报告理想门限。输出在事件后100ps内可过渡，之后绝对误差不得超过2mV。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。运行 `python /tests/verify.py --candidate /work/dut.va --output /logs/verifier --tests /tests` 自测，正式条件和数值容差公开于 public/cases.json。
