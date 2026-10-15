# Acquisition Limited Sample And Hold

## Task Contract

Implement the requested Verilog-A artifact for `Acquisition Limited Sample And Hold`.
- Form: `dut`
- Level: `L1`
- Category: `sampling_analog_memory`
- Target artifact(s): `dut.va`

Implement `dut.va` in Verilog-A.

## Public Verilog-A Interface

Declare module `acquisition_limited_sample_hold(sample, rst, vin, vout, metric)`
with scalar electrical voltage-domain ports.

- `sample`: voltage-coded acquisition-window control.
- `rst`: active-high voltage-coded reset.
- `vin`: analog input voltage.
- `vout`: acquired and held output voltage.
- `metric`: voltage-coded monitor that is high while the model is actively
  acquiring and low while it is holding or reset. Its high level is 0.9 V and
  its low level is 0 V.

## Public Parameter Contract

- `vth`: logic threshold, default `0.45`.
- `vinit`: reset and initial held voltage, default `0.45`.
- `alpha`: acquisition fraction per update, default `0.42`.
- `tick`: acquisition update interval, default `1n`.
- `tr`: output and monitor transition smoothing time, default `200p`.

## Required Behavior

Model finite acquisition bandwidth rather than an ideal instantaneous sampler:

- A high `sample` level opens a tracking/acquisition window.
- While acquiring, `vout` moves toward the current `vin` voltage in discrete
  updates separated by `tick`.
- A falling `sample` crossing freezes the last acquired value.
- High `rst` returns the held output to `vinit` and clears the acquisition
  monitor.
- `metric` is high only while acquisition is active.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`. Do not include explanatory prose outside the source artifact contents.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

全局k*tick离散更新，初态tracking=0；sample上升打开窗口，下降关闭。reset在tick读取并回到vinit，短reset脉冲不属于合法输入。每个rst高区间至少2*tick。
