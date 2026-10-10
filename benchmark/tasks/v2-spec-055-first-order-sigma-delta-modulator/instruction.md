# First Order Sigma Delta Modulator

## Task Contract

Implement the DUT Verilog-A source file `dut.va`.
This is an L1 data-converter task: a clocked first-order sigma-delta modulator
with a one-bit voltage-coded output stream.

## Public Verilog-A Interface

```verilog
Declare module `first_order_sigma_delta_modulator` with the positional ports listed below.
```

All ports are electrical. `vin` is the normalized analog input, `vclk` is the
modulator clock, and `bitout` is the voltage-coded one-bit output stream.

## Public Parameter Contract

- `vth_clk = 0.45 V`: clock threshold.
- `vh = 0.9 V`: output logic-high level.
- `vref = 1.0 V`: normalized feedback reference.
- `tr = 20p`: output transition smoothing time.

## Required Behavior

Maintain a first-order accumulator. On each rising crossing of `vclk`, update
the accumulator with the current normalized input minus the previous one-bit
feedback value. Publish the next output bit high when the updated accumulator
is nonnegative and low otherwise. The output stream should therefore have a
higher pulse density for larger `vin` values while keeping the accumulator
bounded by the feedback action.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return only `dut.va` implementing the public
module. The file must compile under the simulator-compatible Verilog-A and must not
require additional modules, include files, or example harness changes.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

初态acc=0、bit=0。每上升沿acc+=vin/vref-旧bit，newbit=(acc>=0)。vin范围[0,vref]。
