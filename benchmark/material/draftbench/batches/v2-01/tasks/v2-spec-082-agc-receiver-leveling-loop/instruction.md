# AGC Receiver Leveling Loop

## Task Contract

Implement the requested Verilog-A artifact for `AGC Receiver Leveling Loop`.
- Form: `dut`
- Level: `L2`
- Category: `rf_afe_behavioral_macromodels`
- Target artifact(s): `dut.va`

Implement a voltage-domain automatic-gain-control receiver leveling loop.

## Public Verilog-A Interface

Declare module `agc_receiver_leveling_loop` with positional ports `clk, rst,
vin, out, metric, gain_mon, rssi_mon`. All ports are electrical.

`clk` is the gain-control update clock, `rst` is an active-high voltage-coded
reset, `vin` is the receiver input envelope centered around common mode, `out`
is the leveled receiver output, `gain_mon` exposes the bounded gain-control
state, `rssi_mon` exposes the observed output envelope, and `metric` indicates
near-target settling.

## Public Parameter Contract

Provide these overrideable public parameters:

- `tr = 100p`: transition time used for smoothed voltage contributions.
- `vth = 0.45 V`: threshold for voltage-coded logic decisions.
- `target_amp = 0.18 V`: desired output-envelope amplitude around common mode.
- `deadband = 0.025 V`: tolerance band around the target amplitude before gain
  correction is needed.

## Required Behavior

On reset, initialize the gain state to `2.2`, return `out` to the 0.45 V
common-mode level, drive `rssi_mon` and `metric` to 0 V, and drive `gain_mon`
from the public gain-monitor scaling below. After reset releases, update the
sampled loop on rising `clk` crossings through `vth`.

For each non-reset update, compute the leveled output from the current gain as
`out = 0.45 + gain * (vin - 0.45)` and clamp `out` to `[0.02 V, 0.88 V]`.
The observed output envelope is `abs(out - 0.45)`. Drive `rssi_mon` as
`0.9 * envelope / 0.43`, clamped to `[0 V, 0.9 V]`. If the envelope is greater
than `target_amp + deadband`, reduce the gain by `0.18`; if the envelope is
less than `target_amp - deadband`, increase the gain by `0.10`; otherwise keep
the gain unchanged. Clamp the gain state to `[0.45, 3.0]`.

Drive `gain_mon` as `0.9 * (gain - 0.45) / (3.0 - 0.45)` after the gain
update. Drive `metric` as `0.9 - 4.0 * abs(envelope - target_amp)`, clamped to
`[0 V, 0.9 V]`. Small input envelopes should be amplified, overload windows
should reduce the gain monitor, and the output should settle toward
`target_amp` around common mode while remaining bounded.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`. Do not include explanatory prose outside the source artifact contents.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

reset在clk上升读取。初始out=.45、metric=rssi=0、gain=2.2，gain_mon=.9*(2.2-.45)/2.55。
