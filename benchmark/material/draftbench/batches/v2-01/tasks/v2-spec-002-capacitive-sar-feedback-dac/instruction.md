# Capacitive SAR Feedback DAC

## Task Contract

Implement the requested Verilog-A artifact for `Capacitive Weighted SAR Feedback DAC`.
- Form: `dut`
- Level: `L1`
- Category: `data_converter`
- Target artifact(s): `dut.va`

Implement a clocked capacitive feedback DAC for a SAR ADC.

## Public Verilog-A Interface

Declare module `cdac_cal` with positional ports `VDD, VSS, CLK, D9, D8, D7,
D6, D5, D4, D3, D2, D1, D0, CAL0, CAL1, VDAC_P, VDAC_N`. All ports are
electrical. `VDD` and `VSS` are supply/reference nodes; `VDAC_P` and `VDAC_N`
are complementary differential outputs.

## Public Parameter Contract

Provide these overrideable public parameters:

- `vcm = 0.45 V`: output common-mode voltage.
- `swing = 0.6 V`: differential output swing scale.
- `tt = 20 ps`: output transition smoothing time.

Use a 0.45 V logic threshold for the sampled clock, DAC control bits, and
calibration bits.

## Required Behavior

On each rising `CLK` edge, sample `D9..D0`, `CAL0`, and `CAL1`. Interpret
`D9..D0` as an unsigned 10-bit binary word with `D9` as the most significant
bit and `D0` as the least significant bit. Interpret the calibration pins as a
small unsigned code where `CAL0` contributes one unit and `CAL1` contributes
two units.

Model the redundant calibration contribution as an additive offset of 32 main
DAC codes per calibration unit. Higher effective code should raise `VDAC_P`
relative to `VDAC_N`; lower effective code should lower it. Drive complementary
outputs around `vcm`, with the output differential proportional to the centered
effective code over the full 10-bit main-code range.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`. Do not include explanatory prose outside the source artifact contents.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

初始双输出对VSS为vcm；差分=swing*((code+32*cal)/1023-.5)，两个对VSS输出为vcm±差分/2，不夹位。
