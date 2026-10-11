# 3-tap FFE Transmitter

## Task Contract

Implement one Verilog-A DUT artifact for `3-tap FFE Transmitter`.

- Target artifact: `dut.va`
- Public top module: `ffe_tx_3tap`
- Task level: `L1`
- Circuit category: `serdes_equalization_systems`

## Public Verilog-A Interface

Declare module `ffe_tx_3tap` with positional electrical ports `data, clk, rst, pre_1, pre_0, post_1, post_0, vout, main_dbg, pre_dbg, post_dbg`. All ports are electrical.

`data` is sampled as a binary NRZ symbol on rising `clk` edges. `pre_1:pre_0` and `post_1:post_0` are unsigned two-bit tap-control codes.

## Public Parameter Contract

Provide these overrideable public parameters:

- `vdd = 0.9 V`: output full-scale level
- `vss = 0.0 V`: output low level
- `vcm = 0.45 V`: common-mode level
- `vth = 0.45 V`: logic threshold
- `main_amp = 0.18 V`: main cursor amplitude around common mode
- `tap_step = 0.04 V`: tap contribution per code step
- `tr = 120 ps`: output transition smoothing time

## Required Behavior

- Reset clears symbol history and drives all outputs to common mode.
- On each rising `clk`, sample `data` as +1 for high and -1 for low.
- Drive `main_dbg`, `pre_dbg`, and `post_dbg` as voltage-coded per-tap contributions around common mode.
- `vout` is the clipped sum of the current main contribution, previous-symbol pre contribution, and older-symbol post contribution.
- Higher tap-control codes must increase the corresponding contribution magnitude.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete source artifact named `dut.va`.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

reset在clk上升读取，三个符号初值0。main=main_amp*当前符号，pre=tap_step*precode*上一符号，post=-tap_step*postcode*上上符号。debug=vcm+各贡献，vout=clamp(vcm+main+pre+post)。

每次非reset的clk上升沿同时采样data、pre_1:pre_0和post_1:post_0。tap码按vth判高低，分别解码为0至3，并与该沿更新后的符号历史一起计算贡献。两次clk上升沿之间，tap输入改变不更新输出目标；输出在tr过渡后保持。clk上升沿采到reset有效时，将历史及所有输出目标清到上述初态。
