# Quadrature LO Generator from Divided Clock

## Task Contract

Implement a Verilog-A DUT source package for a mixed-signal behavioral circuit block.

- Target artifacts: `dut.va`
- Public top module: `quadrature_lo_generator_divided_clock`
- Required public module: `quadrature_lo_generator_divided_clock`

The submitted source must include the target artifact and public module listed above. The public top module is the module instantiated by the evaluator; optional helper modules may be included only when they are part of the DUT source package, not testbench code.

## Public Verilog-A Interface

Declare top module `quadrature_lo_generator_divided_clock` with positional electrical ports `clk_in, rst, enable, lo_i, lo_q, div_metric, quad_ok`. All top-level ports are electrical.

The top module must expose exactly the public top-level port order above. Optional implementation-local helper modules are allowed, but no helper module is required by the public contract.

## Public Parameter Contract

Provide these overrideable public parameters on the top module and propagate compatible values to helper modules where needed:

- `vdd = 0.9 V`: logic high output level.
- `vss = 0.0 V`: logic low output level.
- `vth = 0.45 V`: threshold for clock, reset, and enable.
- `tr = 200 ps`: output transition smoothing time.

## Required Behavior

- On reset or when disabled, clear `lo_i`, `lo_q`, `div_metric`, and `quad_ok`.
- On successive rising `clk_in` edges while enabled, generate the repeating
  state sequence `(lo_i, lo_q) = 10, 11, 01, 00`. Each state lasts one input
  clock period, so both outputs divide the input clock by four and `lo_q`
  trails `lo_i` by one quarter of the divided-clock period.
- `lo_i` and `lo_q` must have the same divided frequency and a deterministic quadrature phase relationship.
- `div_metric` must expose the state index `k` for the currently driven pair as
  `vss + (vdd - vss) * k / 3`, where the sequence above uses `k = 0..3`.
- Assert `quad_ok` after two complete quadrature output cycles with the expected state sequence.

## 实现与修改边界

按公开接口建立电压域行为模型。实现方法与合法Verilog-A表达方式由求解者选择。不得读取评分材料或重放固定测试答案。只修改交付源码，固定激励及评分程序保持不变。

## Output Contract

Return exactly these complete source artifacts:

- `dut.va`

## 固定评测合同

后端固定为Spectre，运行版本和容器身份随校准记录保存。公开自测是public/visible_test.scs，交付物位于/work/dut.va及声明的其他源码。初态、输入范围和同时刻事件遵循下面补充合同。终评可以改变同一合同内的输入和参数。电压误差不超过2mV，输出过渡结束后的保持区间逐点检查；时间分辨率不超过最短过渡的四分之一。

输入初态及边沿保持明确，控制不恰好停在门限，独立控制边沿互相至少隔开两倍输出过渡时间。模拟输入在采样时连续。电源固定，控制门限采用题面注明的参考轨。未规定的同刻事件不评分。各模块的初态以本题补充合同为准。

## 本轮冻结的数值合同

初态所有输出vss。每次reset/disable异步清相位；释放控制不推进，首次新clk输出10。
