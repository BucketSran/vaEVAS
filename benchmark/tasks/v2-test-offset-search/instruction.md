# 响应驱动比较器失调搜索

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 offset_search(dcmpp,ready,vinp,vinn,request,offset_est,valid,status)。初态估计0，差分输入=估计值且围绕0.5V对称。1ns启动首个request高脉冲，比较器在收到request后给出dcmpp决策和ready上升。候选只能在ready上升时更新：dcmpp>0.5V则减当前步长，否则加步长；初始步长0.064V，每次减半，共7次。响应后立即拉低request，gap=1ns后发下个request。最后一次响应后valid=1、status=1，停止刺激并保持结果。任何request超过timeout=10ns仍没有ready时status=2、valid=0，停止并保持未完成估计。status=0表示运行中。阈值及逻辑高为0.5V与1V，tr20ps；时序允许80ps，电压1.5mV。不允许按固定预期响应表推进；范围为±0.127V，区间外DUT属于公开未覆盖条件。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。运行 `python /tests/verify.py --candidate /work/dut.va --output /logs/verifier --tests /tests` 自测，正式条件和数值容差公开于 public/cases.json。
