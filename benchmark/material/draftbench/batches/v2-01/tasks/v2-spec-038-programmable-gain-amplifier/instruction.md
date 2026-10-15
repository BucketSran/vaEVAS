# Programmable Gain Amplifier

## Task Contract

Implement one Verilog-A DUT artifact for a sampled-gain programmable gain amplifier with clipping indication.

- Target artifact: `dut.va`

## Public Verilog-A Interface

Declare module `programmable_gain_amplifier` with positional ports `clk, rst, gain_sel, vin, out, metric`. All ports are electrical.

- `clk`, `rst`, and `gain_sel` are voltage-coded control inputs.
- `vin` is the analog input around the common-mode level.
- `out` is the gain-scaled and bounded output.
- `metric` indicates output clipping. Its low level is 0 V and its high level is 0.9 V, independent of the output clamp parameters.

## Public Parameter Contract

Provide these overrideable public parameters:

- `vth = 0.45 V`: logic threshold for `clk`, `rst`, and `gain_sel`.
- `vcm = 0.45 V`: input and output common-mode reference.
- `gain_low = 0.8`: sampled gain when `gain_sel` is low.
- `gain_high = 2.4`: sampled gain when `gain_sel` is high.
- `vmin = 0.0 V`: lower output clamp.
- `vmax = 0.9 V`: upper output clamp.
- `tr = 200 ps`: transition smoothing time for `out` and `metric`.

## Required Behavior

- Initialize the sampled gain to unity.
- On each rising `clk` crossing, sample `gain_sel` unless reset is active.
- While `rst` is above `vth`, use unity gain, drive `out` to `vcm`, and drive `metric` low.
- When not reset, select `gain_high` for high `gain_sel` and `gain_low` for low `gain_sel`.
- Drive `out` as `vcm + gain * (V(vin) - vcm)` after clipping to the `vmin` to `vmax` range.
- Drive `metric` high when the unclamped target would exceed either clamp limit, and low otherwise.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

out为连续模拟目标不使用tr滤波；tr只用于clipping metric，公开输出无需模拟输出电阻。rst高期间out=vcm，复位只在clk上升时重置储存gain为1。
