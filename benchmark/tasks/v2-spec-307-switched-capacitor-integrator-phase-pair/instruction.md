# Switched-capacitor Integrator Phase Pair

## Task Contract

Implement a Verilog-A DUT source package for a multi-module mixed-signal behavioral system.

- Target artifacts: `dut.va`, `sample_phase_cell.va`, `integrator_state_cell.va`
- Public top module: `switched_cap_integrator_phase_pair_top`
- Required public modules: `switched_cap_integrator_phase_pair_top`, `sample_phase_cell`, `integrator_state_cell`

The submitted package may include helper modules, but it must include the target artifacts and public modules listed above. The public top module is the top-level DUT entry point; helper modules must be part of the returned DUT source package, not verification harness code.

## Public Verilog-A Interface

Declare top module `switched_cap_integrator_phase_pair_top` with positional electrical ports `vin, phi1, phi2, rst, enable, vout, phase_metric, valid`. All top-level ports are electrical.

Each required public helper module must be declared in one of the returned source artifacts. The helper modules may use implementation-local ports chosen by the solver, but the top module must expose exactly the public top-level port order above.

## Public Parameter Contract

Provide these overrideable public parameters on the top module and propagate compatible values to helper modules where needed:

- `vdd = 0.9 V`: logic high and upper output rail.
- `vss = 0.0 V`: logic low and lower output rail.
- `vcm = 0.45 V`: signal common-mode reference.
- `vth = 0.45 V`: threshold for voltage-coded control inputs.
- `tr = 200 ps`: output transition smoothing time.
- `k_int = 0.2`: integration increment per phase pair.

## Required Behavior

- On reset or when disabled, clear the integration state, drive `vout` to `vcm`, and clear `valid`.
- On a rising `phi1` crossing, sample the input deviation from `vcm` into the sampling state.
- On the following rising `phi2` crossing, add `k_int` times the sampled deviation to the integrator state.
- Reject overlapping `phi1` and `phi2` updates by holding the previous state and lowering `valid` for that cycle.
- Expose the most recent accepted phase pair on `phase_metric` and clamp `vout` to the rails.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly these complete source artifacts:

- `dut.va`
- `sample_phase_cell.va`
- `integrator_state_cell.va`

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

phase_metric初态与复位值为vcm，接受时编码最近phi1的采样值夹到电源轨。一次phi1只能供一次phi2积分，缺少新phi1的重复phi2必须拒绝。reset/disable异步清空采样有效性与积分。内部sample节点过渡必须在phi2之前完成，正常两相间隔至少4*tr。
