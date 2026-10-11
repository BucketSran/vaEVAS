# Switched-capacitor Integrator Phase Pair

## Task Contract

Implement a Verilog-A DUT source package for a multi-module mixed-signal behavioral system.

- Target artifacts: `dut.va`, `sample_phase_cell.va`, `integrator_state_cell.va`
- Public top module: `switched_cap_integrator_phase_pair_top`
- Required public modules: `switched_cap_integrator_phase_pair_top`, `sample_phase_cell`, `integrator_state_cell`

The submitted package may include helper modules, but it must include the target artifacts and public modules listed above. The public top module is the top-level DUT entry point; helper modules must be part of the returned DUT source package, not verification harness code.

## Public Verilog-A Interface

Declare top module `switched_cap_integrator_phase_pair_top` with positional electrical ports `vin, phi1, phi2, rst, enable, vout, phase_metric, valid`. All top-level ports are electrical.

Each required public helper module must be declared in one of the returned source artifacts. The helper interfaces and responsibilities are fixed by the versioned system contract below. The top module must expose exactly the public top-level port order above.

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

## 固定系统连接合同 system-interfaces-v2

本版本固定 helper 的接口角色、职责及可替换性，用独立组件和顶层消费实验验收真实模块协作。实现中的实例名、内部节点名、状态表达式和合法 Verilog-A 写法由你选择。下列 helper 端口全部为 electrical，顺序与角色固定；局部端口变量名可以不同。

`sample_phase_cell(vin,phi1,phi2,rst,enable,sample_node,sample_valid)` 在合法 phi1 保存实际 vin 到 sample_node，sample_valid 按有效性编码到 vdd/vss；重叠 phi2 时不得接受，reset/disable 将 sample_node 清为 vcm、sample_valid 清为 vss。sample_node 的过渡在后续正常 phi2 前完成。公开参数为 vdd、vss、vcm、vth、tr，默认值与顶层一致。

`integrator_state_cell(phi1,phi2,rst,enable,sample_node,sample_valid,vout,phase_metric,valid)` 在合法 phi2 消费实际 sample_node/sample_valid，一次 phi1 只允许一次消费，以 k_int*(sample_node-vcm) 增量积分，驱动三个公开输出；重叠、重复 phi2 及复位行为遵循原合同。公开参数为 vdd、vss、vcm、vth、tr、k_int，默认值与顶层一致。顶层将采样模块的真实输出连接到积分模块输入，并将积分模块的输出连接到公开输出。

producer 替身保持采样有效性、控制及复位合同，但每次有效 phi1 提供 sample_node=0.62 V。积分模块必须消费该值。consumer 替身直接提供 vout=0.63 V、phase_metric=0.22 V、valid=0 V；顶层必须将这些值呈现在对应端口。

顶层必须实例化上述两个 public helper，传递兼容的公开参数，并真实使用其连接值。不得在顶层或另一套私有副本中重做 helper 的职责、同时只保留无关或空的 public helper。每个 public helper 定义放在对应同名 .va 交付文件中；dut.va 定义公开顶层。评分器独立载入这些文件，源码不得 include 另一份交付 .va。标准 constants.vams、disciplines.vams 不受影响。额外私有模块可以使用，但不得绕过 public helper 职责。顶层对 helper 的参数覆盖只使用上列公开参数，保证公开兼容替身可独立替换。

终评共六个条件：两组原行为条件，分别独立测试 producer/consumer 的两个组件条件，以及两个顶层替身条件。组件测试使用固定顶层和已知合规的另一组件。顶层替身测试保留你的真实顶层及另一真实 helper；替身仅改变上述公开边界值，检查消费关系，不能用原始 vin 重算而忽略替身。consumer 替身的数值是直接电压贡献，从仿真初态起就应呈现在公开输出，不按正常电路复位公式重写。producer 的替身输出仍遵循原有控制及复位时序。

此版本升级公开 helper 接口及验收方式。旧版只有顶层波形评分，旧 prompt 和成绩保留为旧版本，不能作为本版本通过证据。
