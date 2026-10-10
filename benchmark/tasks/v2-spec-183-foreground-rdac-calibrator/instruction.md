# Foreground RDAC Calibrator

## Task Contract

- Form: `dut`.
- Level: `L1`.
- Category: calibration/trim control.
- Target artifact: `dut.va`.
- Role: foreground 7-bit RDAC calibration controller.
- Output boundary: implement only the requested public Verilog-A DUT artifact.

## Public Verilog-A Interface

Declare the public module exactly as:

```verilog
module foreground_rdac_calibrator(ck, d, vrefp, vrefn, dc0, dc1, dc2, dc3, dc4, dc5, dc6, cvinp, cvinn, en, enb);
```

`ck` is the calibration clock, `d` is the comparator decision, `vrefp/vrefn` are forwarded references, `dc0..dc6` are RDAC code bits, and `en/enb` indicate calibration activity. All ports are electrical.

## Public Parameter Contract

Provide overrideable parameter `vdd = 1.0`. Use `0.5*vdd` as the clock and decision threshold and 0/`vdd` as digital output levels.

## Required Behavior

Initialize calibration active with the MSB trial code set (`dc6 = vdd`, all lower RDAC bits low). On each rising `ck` crossing while calibration is active, sample `d` against the `0.5*vdd` threshold and refine the 7-bit RDAC code from MSB toward LSB. For the current trial bit, keep that bit when `d < 0.5*vdd`; clear that bit when `d >= 0.5*vdd`. In both cases, assert the next lower trial bit as the search advances. After the seven-bit capture phase completes, deassert `en` and assert `enb`. Continuously drive `cvinp` from `vrefp` and `cvinn` from `vrefn`.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete Verilog-A source file named `dut.va`. Do not generate a testbench, checker, waveform postprocessor, companion support module, or explanatory prose outside the requested source artifact.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

完成7次上升决策后保持最终码，后续时钟不再改变；初态code=64,en=vdd,enb=0。
