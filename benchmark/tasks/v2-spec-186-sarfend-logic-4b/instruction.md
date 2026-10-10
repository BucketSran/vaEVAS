# SAR Front-End Logic 4b

## Task Contract

- Form: `dut`.
- Level: `L2`.
- Category: SAR ADC control logic.
- Target artifact: `dut.va`.
- Role: 4-bit SAR front-end handshake, test override, and DAC-control publisher.
- Output boundary: implement only the requested public Verilog-A DUT artifact.

## Public Verilog-A Interface

Declare the public module exactly as:

```verilog
module sarfend_logic_4b(clks, dcomp, dcompb, test, dtest0, dtest1, dtest2, dtest3, clkc, dp1, dp2, dp3, dp4, dm1, dm2, dm3, dm4, dout0, dout1, dout2, dout3);
```

`clks` is the sample/reset clock, `dcomp/dcompb` are comparator outputs, `test` enables test override bits `dtest0..dtest3`, `clkc` requests comparator activity, `dp1..dp4`/`dm1..dm4` are differential DAC controls, and `dout0..dout3` publish the previous conversion word. All ports are electrical.

## Public Parameter Contract

No overrideable public parameters are required. Use 0.45 V thresholds and 0/1 V voltage-coded controls.

## Required Behavior

On each rising `clks` crossing, publish the previous cycle DAC-P word,
reset the conversion pointer, initialize the DAC controls for a new conversion,
capture the test override word, and clear `clkc`.

- Publish the previous P-side state as `dout3=dp4`, `dout2=dp3`,
  `dout1=dp2`, and `dout0=dp1` before reinitializing the DAC controls.
- Initialize the new conversion to `dp4=dm4=0` and to
  `dp3=dm3=dp2=dm2=dp1=dm1=1`. These equal-valued pairs are intentional
  undecided/trial states; only an accepted decision makes that pair
  complementary.
- On falling `clks`, assert `clkc` to start comparison. While `clks` is low,
  comparator reset/recovery with both comparator outputs low reasserts `clkc`.
- Accept decisions in the order `dp4/dm4`, `dp3/dm3`, `dp2/dm2`, then
  `dp1/dm1`. A `dcomp`-high/`dcompb`-low decision produces P/M=`1/0`;
  `dcomp`-low/`dcompb`-high produces P/M=`0/1`.
- With `test` low, use the live comparator decision. With `test` high, use
  captured `dtest3`, `dtest2`, `dtest1`, then `dtest0` for the four decisions.
- Clear `clkc` when a decision is accepted and stop requesting comparisons
  after four decisions.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly one complete Verilog-A source file named `dut.va`. Do not generate a testbench, checker, waveform postprocessor, companion support module, or explanatory prose outside the requested source artifact.

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 固定SAR工程内补逻辑

除局部公开时序外，system_test.scs将你的控制器与固定4-bit加权trial DAC和比较器连接。只能补控制逻辑，不能改固定系统模块。每次clkc上升，系统按已决定的dp高位构造下一个trial电平并比较vin，经过100ps延迟返回互补比较决定；clkc下降使比较器复位，恢复双低后控制器请求下一判决。必须四次依次协作，下一clks上升发布已保存的整码。固定环境源码公开，测试可改变vin和帧周期。局部测试保留test override与异常第五判决保护。

## 上电初态与首帧

从初始时刻起，dp4=dm4=0V，dp3=dm3=dp2=dm2=dp1=dm1=1V，dout0至dout3和clkc均为0V。转换指针等待MSB的dp4/dm4判决，共四位尚未完成。首个clks上升沿仍按一般发布规则发布上电P字，因此dout3:dout0首次变为0111，再初始化新转换并捕获dtest3至dtest0。clks初始为低；首个clks上升沿之前比较器双低，不提供有效决定，test override的捕获从该上升沿开始。
