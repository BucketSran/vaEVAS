# Chopper-Stabilized Differential Amplifier

## Task Contract

Implement a three-module L2 behavioral model of a chopper-stabilized differential amplifier. The circuit must compose input chopping and offset-bearing gain with a separate synchronous event-driven low-pass stage. This is a complete signal-flow model, not a bare sign chopper, sampled auto-zero store, or trim servo.

Target artifacts: `dut.va`, `chopper_gain_core.va`, and `synchronous_lp_state.va`.

## Public Verilog-A Interface

Declare this positional electrical interface exactly:

```verilog
module chopper_stabilized_differential_amplifier(
    vinp, vinn, chop_clk, rst, enable, hold,
    voutp, voutn, settled, offset_residual
);
```

`vinp`, `vinn`, `chop_clk`, `rst`, `enable`, and `hold` are inputs. `voutp`, `voutn`, `settled`, and `offset_residual` are outputs.

Also declare helper modules `chopper_gain_core` and `synchronous_lp_state`. The top module must instantiate both helpers and connect them through electrical internal demodulated-sample and event-strobe nodes.

## Public Parameter Contract

- `vdd = 0.9 V`, `vss = 0.0 V`, and `vcm = 0.45 V` define the output rails and common mode.
- `vth = 0.45 V` is the control threshold.
- `gain = 3.0` is the differential baseband gain.
- `vos_amp = 20 mV` is the internal offset added after input chopping and before amplification.
- `lp_alpha = 0.25` is the low-pass update fraction, with `0 < lp_alpha <= 1`.
- `settle_tol = 20 mV` and integer `settle_cycles = 3` define convergence qualification.
- `tr = 100 ps` is output transition smoothing time.

## Required Behavior

At every rising and falling `chop_clk` threshold crossing while enabled, not reset, and not held:

1. Multiply `vinp-vinn` by the current chopper polarity.
2. Add `vos_amp` inside the amplifier and apply `gain`.
3. Synchronously demodulate by the same polarity. The desired differential input therefore returns to baseband with gain, while amplifier offset alternates polarity.
4. Update the retained low-pass state by `lp_alpha` toward that demodulated sample.

Drive `voutp-voutn` from the retained low-pass state, centered on `vcm` and limited to the `vss`/`vdd` rails. Drive `offset_residual` to the retained state minus `gain*(vinp-vinn)` sampled at the most recent active update. Assert `settled` after `settle_cycles` consecutive active updates whose absolute residual is at most `settle_tol`.

Active-high `rst` or low `enable` asynchronously clears the retained differential state, residual, convergence count, and `settled`; the differential outputs return to zero around `vcm`. While `hold` is high, preserve all retained state and outputs exactly. Resume event-driven filtering on later chopper edges after hold is released.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly these complete source files and no other artifact:

- `dut.va`
- `chopper_gain_core.va`
- `synchronous_lp_state.va`

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

内部core先建立理想demod_sample和baseband_ref，再经2*tr延迟加tr过渡的event_strobe通知LP；最终输出允许在输入chop交点后4*tr内完成。内部职责及传递必须保留。
