# Clocked Sample And Hold

## Task Contract

Implement one Verilog-A DUT artifact for a clocked sample-and-hold cell.

- Target artifact: `dut.va`

## Public Verilog-A Interface

Declare module `sample_hold(VDD, VSS, IN, CLK, OUT)` with scalar electrical voltage-domain ports.

- `VDD`, `VSS`: local supply rails.
- `IN`: analog input voltage to be sampled.
- `CLK`: voltage-coded sampling clock.
- `OUT`: held analog output voltage.

## Public Parameter Contract

Provide these overrideable public parameters:

- `vth = 0.45 V`: clock threshold.
- `tedge = 100 ps`: output transition smoothing time.

## Required Behavior

- Sample `IN` on each rising `CLK` crossing of `vth`.
- Hold the sampled voltage on `OUT` between rising clock crossings.
- Do not continuously track `IN` while the clock is between sample events.
- Drive `OUT` with smooth voltage-domain behavior referenced to the local rails.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。
