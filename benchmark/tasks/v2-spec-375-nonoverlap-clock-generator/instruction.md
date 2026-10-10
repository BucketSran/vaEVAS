# Non-overlapping Clock Generator

## Task Contract

Implement one Verilog-A DUT artifact for `Non-overlapping Clock Generator`.

- Target artifact: `dut.va`
- Public top module: `nonoverlap_clock_generator`
- Task level: `L1`
- Circuit category: `clock_timing`

## Public Verilog-A Interface

Declare module `nonoverlap_clock_generator` with positional electrical ports `clk_in, rst, enable, phi1, phi2, deadtime_metric, valid`. All ports are electrical.

`clk_in`, `rst`, and `enable` are voltage-coded controls. `phi1` and `phi2` are generated non-overlapping phase outputs. `deadtime_metric` marks the enforced both-low handoff interval, and `valid` marks that at least one active phase handoff has completed.

## Public Parameter Contract

Provide these overrideable public parameters:

- `vdd = 0.9 V`: logic-high output level
- `vss = 0.0 V`: logic-low output level
- `vth = 0.45 V`: logic threshold for input controls
- `dead_ticks = 5`: number of internal timer ticks held both-low after a phase request
- `tick = 200 ps`: internal discrete update interval for dead-time scheduling
- `tr = 100 ps`: output transition smoothing time

## Required Behavior

- Reset or a low `enable` clears both phases, `deadtime_metric`, and `valid`.
- A rising `clk_in` request eventually enables `phi1`; a falling `clk_in` request eventually enables `phi2`.
- During each handoff, both `phi1` and `phi2` remain low for the configured dead-time interval.
- `phi1` and `phi2` must never be high at the same time.
- `deadtime_metric` is high only while a pending phase request is in the enforced both-low interval.
- `valid` becomes high after the first enabled handoff completes and remains high until reset or disable.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 全局tick的准确死区与取消

边沿在t请求相位后，未来第dead_ticks个全局k*tick事件才启用新相位，死区在((dead_ticks-1)*tick,dead_ticks*tick]。边沿不与tick同时发生。每次新边沿取消旧请求，重新计数。rst上升或enable下降立即清除active、pending、counter、valid，包括短于tick的控制脉冲。释放控制不自动请求，等下次clk边沿再启动。输出用tr过渡，tr<tick/2。相邻clk边沿至少dead_ticks*tick+4*tr。
