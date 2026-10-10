# DCO实际码频与分频观测

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 frequency_meter(dco_clk,div_clk,enable,reset,freq_mhz,divider_ratio,valid)。DUT给定且频率码不会连接到候选；只观测真实时钟。检测阈值0.45V。每路至少两次上升沿才有完整周期。freq_mhz=1e-6/最近DCO周期；divider_ratio=最近分频周期/最近DCO周期，任一路新周期均更新它。两周期都已取得时valid=1V，否则0；reset上升或enable下降清所有历史和报告；被禁用或复位时不采边沿。DUT原divide_ratio表示每多少DCO上升沿翻转一次，完整周期比为2倍，该参数不得替代实际测量。tr20ps，guard80ps；频率误差0.8MHz，周期比0.03，逻辑0.01V。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。运行 `python /tests/verify.py --candidate /work/dut.va --output /logs/verifier --tests /tests` 自测，正式条件和数值容差公开于 public/cases.json。
