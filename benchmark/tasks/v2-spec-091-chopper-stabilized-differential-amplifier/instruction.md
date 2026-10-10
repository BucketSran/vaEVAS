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

## 固定系统连接合同 system-interfaces-v2

本版本固定 helper 的接口角色、职责及可替换性，用独立组件和顶层消费实验验收真实模块协作。实现中的实例名、内部节点名、状态表达式和合法 Verilog-A 写法由你选择。下列 helper 端口全部为 electrical，顺序与角色固定；局部端口变量名可以不同。

`chopper_gain_core(vinp,vinn,chop_clk,rst,enable,hold,demod_sample,baseband_ref,event_strobe)` 负责两种 chop 边沿的斩波、带 offset 的增益及同步解调。demod_sample 为 gain*(vinp-vinn)+polarity*gain*vos_amp，baseband_ref 为 gain*(vinp-vinn)；reset/disable 清零样本与通知，hold 禁止更新。样本在通知开始前建立，event_strobe 每次有效样本翻转，延迟 2*tr 后以 tr 过渡通知。公开参数为 vdd、vss、vth、gain、vos_amp、tr，默认值与顶层一致。

`synchronous_lp_state(demod_sample,baseband_ref,event_strobe,rst,enable,hold,voutp,voutn,settled,offset_residual)` 消费 core 的两个样本及两方向通知 crossing，以公开 lp_alpha 递推低通；残差为低通状态减实际 baseband_ref，settled 按公开次数累计。它驱动四个公开输出并按原合同复位。公开参数为 vdd、vss、vcm、vth、gain、lp_alpha、settle_tol、settle_cycles、tr，默认值与顶层一致。顶层将实际 core 输出连接到 LP 输入，并将实际 LP 输出连接到公开输出。

producer 替身保持控制及通知合同，但每次有效采样提供 demod_sample=baseband_ref=0.16 V。LP 必须消费这些值。consumer 替身直接提供 voutp=0.22 V、voutn=0.67 V、settled=0.9 V、offset_residual=0.14 V；顶层必须将这些值呈现在对应端口。

顶层必须实例化上述两个 public helper，传递兼容的公开参数，并真实使用其连接值。不得在顶层或另一套私有副本中重做 helper 的职责、同时只保留无关或空的 public helper。每个 public helper 定义放在对应同名 .va 交付文件中；dut.va 定义公开顶层。评分器独立载入这些文件，源码不得 include 另一份交付 .va。标准 constants.vams、disciplines.vams 不受影响。额外私有模块可以使用，但不得绕过 public helper 职责。顶层对 helper 的参数覆盖只使用上列公开参数，保证公开兼容替身可独立替换。

终评共六个条件：两组原行为条件，分别独立测试 producer/consumer 的两个组件条件，以及两个顶层替身条件。组件测试使用固定顶层和已知合规的另一组件。顶层替身测试保留你的真实顶层及另一真实 helper；替身仅改变上述公开边界值，检查消费关系，不能用原始 vin 重算而忽略替身。consumer 替身的数值是直接电压贡献，从仿真初态起就应呈现在公开输出，不按正常电路复位公式重写。producer 的替身输出仍遵循原有控制及复位时序。

此版本升级公开 helper 接口及验收方式。旧版只有顶层波形评分，旧 prompt 和成绩保留为旧版本，不能作为本版本通过证据。
