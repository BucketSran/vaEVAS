# Op-amp Feedback Settling Monitor

## Task Contract

Implement a Verilog-A DUT source package for a mixed-signal behavioral circuit block.

- Target artifacts: `dut.va`
- Public top module: `opamp_feedback_settling`
- Required public module: `opamp_feedback_settling`

The submitted source must include the target artifact and public module listed above. Optional helper modules may be included only when they are part of the DUT source package.

## Public Verilog-A Interface

Declare top module `opamp_feedback_settling` with positional electrical ports `vin, clk, rst, enable, gain_2, gain_1, gain_0, vout, error_metric, settled`. All top-level ports are electrical.

The top module must expose exactly the public top-level port order above. Optional implementation-local helper modules are allowed, but no helper module is required by the public contract.

## Public Parameter Contract

Provide these overrideable public parameters on the top module and propagate compatible values to helper modules where needed:

- `vdd = 0.9 V`: upper output clamp.
- `vss = 0.0 V`: lower output clamp.
- `vcm = 0.45 V`: common-mode reference.
- `vth = 0.45 V`: threshold for clock and control inputs.
- `gain_lsb = 0.5`: closed-loop gain increment per gain-code step.
- `alpha = 0.3`: sampled settling factor.
- `settle_tol = 40e-3 V`: error tolerance for settled flag.
- `tr = 200 ps`: output transition smoothing time.

## Required Behavior

- On reset or when `enable` is low, drive `vout` and the zero-error encoding on `error_metric` to `vcm`, and clear `settled`.
- Decode `gain_2..gain_0` into a closed-loop target gain of at least unity.
- Update `vout` once per rising `clk` edge toward the target closed-loop output using `alpha`.
- Clamp `vout` to the range `vss` through `vdd`.
- `error_metric` must expose the target-minus-output error as a `vcm`-centered voltage code.
- Assert `settled` after three consecutive updates where the absolute error is below `settle_tol`.
- The output must move in the direction of the target after an input step unless already clamped.

Poll controls every `tick = 250 ps`. Decode
`code=4*gain_2+2*gain_1+gain_0` and, on each enabled rising edge, compute

`target = clamp(vcm + (1+gain_lsb*code)*(vin-vcm), vss, vdd)`

`vout_next = clamp(vout + alpha*(target-vout), vss, vdd)`

`error = target-vout_next`.

Drive `vout=vout_next` and encode the signed error on the public electrical
metric as `error_metric=vcm+error`; `vcm` therefore represents zero error.
Increment the settle counter when `abs(error)<settle_tol`, otherwise clear it,
and assert `settled=vdd` at count three. Reset or disable drives `vout=vcm`,
`error_metric=vcm`, and `settled=vss`, and clears the counter.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly these complete source artifacts:

- `dut.va`

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。
