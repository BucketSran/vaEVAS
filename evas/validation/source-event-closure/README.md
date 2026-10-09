# 源驱动局部事件闭包

模型、刺激、请求精度和验收预算在实际 Spectre 执行前冻结于 [contract.json](contract.json)。
[模型](dut.va)包含两个极近 timer、输入驱动的积分、一次历史 cross 改变积分流和另一条积分历史。
正极性斜坡与负极性折线各配两档参考精度，共四个配置。

独立答案是原 binary64 PWL 的有理数分段梯形积分：令 tau 为精确 `.1+.2`，
A 为 tau 后的输入面积，则 z 在 A≤.002 时为 polarity*A，之后为 polarity*(2*A-.002)；
w 为从零开始的输入面积加 max(0,t-tau)。这避免用 EVAS 自身输出来定义答案。
模拟电压预算固定 1µV，离散计数在预先规定事件的 2ns 窗口外要求一致。
窗口内所有差异保留；缺失的精确 binary64 请求时刻记 I，不插值补齐。

检查器、负控制与实际结果见 [对照入口](../../../experiments/backends/source-event-closure/README.md)。
该模型是开发集，不能作为未见独立论文评价集，也不替换原 C1/#79/VCO/M1。
