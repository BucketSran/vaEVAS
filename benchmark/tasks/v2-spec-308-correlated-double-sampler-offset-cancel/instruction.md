# Correlated Double Sampler Offset-cancel Macro

## Task Contract

Implement a Verilog-A DUT source package for a multi-module mixed-signal behavioral system.

- Target artifacts: `dut.va`, `reset_sample_latch.va`, `signal_sample_latch.va`
- Public top module: `correlated_double_sampler_top`
- Required public modules: `correlated_double_sampler_top`, `reset_sample_latch`, `signal_sample_latch`

The submitted package may include helper modules, but it must include the target artifacts and public modules listed above. The public top module is the top-level DUT entry point; helper modules must be part of the returned DUT source package, not verification harness code.

## Public Verilog-A Interface

Declare top module `correlated_double_sampler_top` with positional electrical ports `vin, clk, rst, sample_reset, sample_signal, vout, offset_dbg, valid`. All top-level ports are electrical.

Each required public helper module must be declared in one of the returned source artifacts. The helper interfaces and responsibilities are fixed by the versioned system contract below. The top module must expose exactly the public top-level port order above.

## Public Parameter Contract

Provide these overrideable public parameters on the top module and propagate compatible values to helper modules where needed:

- `vdd = 0.9 V`: logic high and upper output rail.
- `vss = 0.0 V`: logic low and lower output rail.
- `vcm = 0.45 V`: signal common-mode reference.
- `vth = 0.45 V`: threshold for voltage-coded control inputs.
- `tr = 200 ps`: output transition smoothing time.
- `cds_gain = 1.0`: correlated-difference gain.

## Required Behavior

- On reset, clear reset-sample, signal-sample, output, debug metric, and `valid`.
- On a rising `clk` edge with `sample_reset` high, capture `vin` as the reset/reference sample.
- On a later rising `clk` edge with `sample_signal` high, capture `vin` as the signal sample.
- Drive `vout` as `vcm` plus the signal-minus-reset difference scaled by `cds_gain`.
- Expose the reset sample on `offset_dbg` and assert `valid` only after a complete reset/signal pair.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly these complete source artifacts:

- `dut.va`
- `reset_sample_latch.va`
- `signal_sample_latch.va`

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

reset_sample初态与复位值为vcm；vout复位到vcm，offset_dbg复位到vss，valid=vss。sample_signal在新的sample_reset之前不得使valid有效。两采样控制不得同时高；采样对完整后valid保持到reset。

## 固定系统连接合同 system-interfaces-v2

本版本固定 helper 的接口角色、职责及可替换性，用独立组件和顶层消费实验验收真实模块协作。实现中的实例名、内部节点名、状态表达式和合法 Verilog-A 写法由你选择。下列 helper 端口全部为 electrical，顺序与角色固定；局部端口变量名可以不同。

`reset_sample_latch(vin,clk,rst,sample_reset,reset_node)` 在有效 reset 采样边沿保存 vin 到 reset_node；初态及异步复位为 vcm，随后保持到下一次合法采样或复位。公开参数为 vdd、vss、vcm、vth、tr，默认值与顶层一致。

`signal_sample_latch(vin,clk,rst,sample_signal,sample_reset,reset_node,vout,offset_dbg,valid)` 记录完整采样对的状态；在有效 signal 采样边沿使用实际 reset_node 作差，按原合同驱动 vout、offset_dbg、valid。reset_node 在后续 signal 边沿前已经建立。公开参数为 vdd、vss、vcm、vth、tr、cds_gain，默认值与顶层一致。顶层将 reset 模块真实输出连接到 signal 模块输入，并将 signal 模块输出连接到公开输出。

producer 替身保持采样、控制及复位合同，但每次有效 reset 采样提供 reset_node=0.31 V。signal 模块必须消费该值。consumer 替身直接提供 vout=0.61 V、offset_dbg=0.23 V、valid=0.9 V；顶层必须将这些值呈现在对应端口。

顶层必须实例化上述两个 public helper，传递兼容的公开参数，并真实使用其连接值。不得在顶层或另一套私有副本中重做 helper 的职责、同时只保留无关或空的 public helper。每个 public helper 定义放在对应同名 .va 交付文件中；dut.va 定义公开顶层。评分器独立载入这些文件，源码不得 include 另一份交付 .va。标准 constants.vams、disciplines.vams 不受影响。额外私有模块可以使用，但不得绕过 public helper 职责。顶层对 helper 的参数覆盖只使用上列公开参数，保证公开兼容替身可独立替换。

终评共六个条件：两组原行为条件，分别独立测试 producer/consumer 的两个组件条件，以及两个顶层替身条件。组件测试使用固定顶层和已知合规的另一组件。顶层替身测试保留你的真实顶层及另一真实 helper；替身仅改变上述公开边界值，检查消费关系，不能用原始 vin 重算而忽略替身。consumer 替身的数值是直接电压贡献，从仿真初态起就应呈现在公开输出，不按正常电路复位公式重写。producer 的替身输出仍遵循原有控制及复位时序。

此版本升级公开 helper 接口及验收方式。旧版只有顶层波形评分，旧 prompt 和成绩保留为旧版本，不能作为本版本通过证据。
