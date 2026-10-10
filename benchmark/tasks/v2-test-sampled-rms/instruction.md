# 四样本在线真有效值仪表

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 sampled_true_rms_to_dc(vinp,vinn,clk,reset,enable,rms_out,valid)。vth=0.45V、vhigh=0.9V、tr=100ps。每个enable为高且reset为低的clk上升沿采样实际差分输入；恰好四个样本形成不重叠窗口，输出sqrt(mean(x*x))。禁用采样边沿不丢弃部分窗口，但清valid。每个完成窗口valid高一个采样间隔；下一clk上升清零valid。reset上升异步清累计、报告和valid；reset高时采样也清零。rms_out保持到下一完整窗口。误差2mV，事件后320ps允许输出过渡。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。运行 `python /tests/verify.py --candidate /work/dut.va --output /logs/verifier --tests /tests` 自测，正式条件和数值容差公开于 public/cases.json。
