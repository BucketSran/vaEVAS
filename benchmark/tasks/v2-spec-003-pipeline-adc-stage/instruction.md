# Pipeline ADC Stage

## Task Contract

Implement the requested Verilog-A artifact for `Pipeline ADC Stage`.
- Form: `dut`
- Level: `L1`
- Category: `data_converter`
- Target artifact(s): `dut.va`

Implement a clocked 1.5-bit pipeline ADC MDAC stage.

## Public Verilog-A Interface

Declare module `pipeline_stage` with positional ports `VDD, VSS, PHI1, PHI2,
VIN, VREF, VRES, D1, D0`. All ports are electrical. `VRES` is the residue
output and `D1,D0` are the sub-ADC decision outputs.

## Public Parameter Contract

Provide these overrideable public parameters:

- `vth = 0.45 V`: clock decision threshold for `PHI1` and `PHI2`.
- `vdd = 0.9 V`: nominal output high level used for initialization.
- `tedge = 200 ps`: output transition smoothing time.

## Required Behavior

On each rising `PHI1` edge, sample `VIN`. On each rising `PHI2` edge, compare
the sampled input around `V(VDD)/2` against the 1.5-bit thresholds
`+V(VREF)/4` and `-V(VREF)/4`.

- Upper region: drive `D1` high, `D0` low, and subtract a half-reference from
  the gain-two residue.
- Middle region: drive `D1` low, `D0` high, and use the gain-two residue
  without reference subtraction or addition.
- Lower region: drive both decision outputs low and add a half-reference to the
  gain-two residue.

Clamp `VRES` to the supply range and drive all outputs with smooth
voltage-domain transitions.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`. Do not include explanatory prose outside the source artifact contents.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

初始VRES=vdd/2、两个D=0。门限相对对地VDD/2，边界等于±VREF/4归middle。PHI1与PHI2非重叠。

在PHI2上升沿，令 `cm=V(VDD)/2`、`x=此前PHI1采到的VIN-cm`，并读取该时刻的 `ref=V(VREF)`。当 `x>ref/4` 时 `region=1`；当 `x<-ref/4` 时 `region=-1`；其余为 `region=0`。残差目标为 `VRES=clamp(cm+2*x-region*ref/2, V(VSS), V(VDD))`，其中clamp把电压限制在给定上下界。两个决策输出在同一PHI2沿更新，D1仅在region=1时高，D0仅在region=0时高；高低电平分别为V(VDD)与V(VSS)。输出保持到下一PHI2上升沿，过渡时间使用tedge。
