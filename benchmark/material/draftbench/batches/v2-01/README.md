# v2-01：五类首批题包

本批保留原 37 道题包、参考解、独立 checker 和来源关系。目录搬迁不完成格式改造或本版人工审核。
任务 ID、`source_group`、历史设计版本和作者结果保持原身份；来源、同源变体与覆盖缺口见[56 题总览](../../TASKS.md)。

当前阶段：已有实现与历史作者记录，本版完整题目审核待进行。
已确认的是五类选题及功能方向；尚未确认每题当前合同、验收方案与新规范题包。
后续先完成 R01 代表题合同审核，再按共用电路小组推进；本次没有新增模型实验或仿真校准。
原校准与交付范围见[作者记录](../../../../../experiments/benchmark_v2/README.md)，不能由历史参考解通过推断本版题目已经录取。

## 审核清单

下表每行指向实际题包。审核后在该行记录审核版本、结论与去向；仅被录取的题包移动到正式 `benchmark/tasks/`。
目前全部保留在本批，没有录取记录。

| 题包 / 英文或原版题面 | 电路功能 | 工程动作 | 同源组 | 本版审核 / 去向 |
| --- | --- | --- | --- | --- |
| [v2-data-sampling-identification](tasks/v2-data-sampling-identification/instruction.md) | 采样与多通道读出 | 从数据建立模型 | `jku-sampling-stage` | 待审核；原位保留 |
| [v2-integrate-349-multichannel-readout](tasks/v2-integrate-349-multichannel-readout/instruction.md) | 采样与多通道读出 | 扩展与集成 | `v4-349` | 待审核；原位保留 |
| [v2-integrate-case0007-adpll-fine-tdc](tasks/v2-integrate-case0007-adpll-fine-tdc/instruction.md) | PLL 与时钟 | 扩展与集成 | `tiny-tapeout-adpll` | 待审核；原位保留 |
| [v2-repair-debounce-latch](tasks/v2-repair-debounce-latch/instruction.md) | 电源、复位与响应测试 | 诊断与修复 | `v4-family-005` | 待审核；原位保留 |
| [v2-repair-pfd-reset](tasks/v2-repair-pfd-reset/instruction.md) | PLL 与时钟 | 诊断与修复 | `v4-family-249` | 待审核；原位保留 |
| [v2-repair-reset-sequencer](tasks/v2-repair-reset-sequencer/instruction.md) | 电源、复位与响应测试 | 诊断与修复 | `v4-family-272` | 待审核；原位保留 |
| [v2-repair-uvlo-brownout](tasks/v2-repair-uvlo-brownout/instruction.md) | 电源、复位与响应测试 | 诊断与修复 | `v4-family-046` | 待审核；原位保留 |
| [v2-repair-uvlo-reset-chain](tasks/v2-repair-uvlo-reset-chain/instruction.md) | 电源、复位与响应测试 | 诊断与修复 | `original-uvlo-chain-case0009` | 待审核；原位保留 |
| [v2-spec-001-bang-bang-phase-detector](tasks/v2-spec-001-bang-bang-phase-detector/instruction.md) | PLL 与时钟 | 按规格构建模型 | `v4-001` | 待审核；原位保留 |
| [v2-spec-002-capacitive-sar-feedback-dac](tasks/v2-spec-002-capacitive-sar-feedback-dac/instruction.md) | DAC 与转换器指标 | 按规格构建模型 | `v4-002` | 待审核；原位保留 |
| [v2-spec-003-pipeline-adc-stage](tasks/v2-spec-003-pipeline-adc-stage/instruction.md) | ADC 结构与转换控制 | 按规格构建模型 | `v4-003` | 待审核；原位保留 |
| [v2-spec-024-clocked-sample-and-hold](tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) | 采样与多通道读出 | 按规格构建模型 | `v4-024` | 待审核；原位保留 |
| [v2-spec-038-programmable-gain-amplifier](tasks/v2-spec-038-programmable-gain-amplifier/instruction.md) | 放大与模拟信号处理 | 按规格构建模型 | `v4-038` | 待审核；原位保留 |
| [v2-spec-047-window-comparator-detector](tasks/v2-spec-047-window-comparator-detector/instruction.md) | 比较器与门限 | 按规格构建模型 | `v4-047` | 待审核；原位保留 |
| [v2-spec-055-first-order-sigma-delta-modulator](tasks/v2-spec-055-first-order-sigma-delta-modulator/instruction.md) | ADC 结构与转换控制 | 按规格构建模型 | `v4-055` | 待审核；原位保留 |
| [v2-spec-071-acquisition-limited-sample-and-hold](tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md) | 采样与多通道读出 | 按规格构建模型 | `v4-071` | 待审核；原位保留 |
| [v2-spec-082-agc-receiver-leveling-loop](tasks/v2-spec-082-agc-receiver-leveling-loop/instruction.md) | 放大与模拟信号处理 | 按规格构建模型 | `v4-082` | 待审核；原位保留 |
| [v2-spec-091-chopper-stabilized-differential-amplifier](tasks/v2-spec-091-chopper-stabilized-differential-amplifier/instruction.md) | 放大与模拟信号处理 | 按规格构建模型 | `v4-091` | 待审核；原位保留 |
| [v2-spec-183-foreground-rdac-calibrator](tasks/v2-spec-183-foreground-rdac-calibrator/instruction.md) | 模拟校准与伺服 | 按规格构建模型 | `v4-183` | 待审核；原位保留 |
| [v2-spec-186-sarfend-logic-4b](tasks/v2-spec-186-sarfend-logic-4b/instruction.md) | ADC 结构与转换控制 | 按规格构建模型 | `v4-186` | 待审核；原位保留 |
| [v2-spec-307-switched-capacitor-integrator-phase-pair](tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/instruction.md) | 滤波、均衡与 RF | 按规格构建模型 | `v4-307` | 待审核；原位保留 |
| [v2-spec-308-correlated-double-sampler-offset-cancel](tasks/v2-spec-308-correlated-double-sampler-offset-cancel/instruction.md) | 放大与模拟信号处理 | 按规格构建模型 | `v4-308` | 待审核；原位保留 |
| [v2-spec-314-hysteretic-window-comparator](tasks/v2-spec-314-hysteretic-window-comparator/instruction.md) | 比较器与门限 | 按规格构建模型 | `v4-314` | 待审核；原位保留 |
| [v2-spec-353-ffe-transmitter-3tap](tasks/v2-spec-353-ffe-transmitter-3tap/instruction.md) | 滤波、均衡与 RF | 按规格构建模型 | `v4-353` | 待审核；原位保留 |
| [v2-spec-370-opamp-feedback-settling-monitor](tasks/v2-spec-370-opamp-feedback-settling-monitor/instruction.md) | 放大与模拟信号处理 | 按规格构建模型 | `v4-370` | 待审核；原位保留 |
| [v2-spec-375-nonoverlap-clock-generator](tasks/v2-spec-375-nonoverlap-clock-generator/instruction.md) | PLL 与时钟 | 按规格构建模型 | `v4-375` | 待审核；原位保留 |
| [v2-spec-396-quadrature-lo-generator-divided-clock](tasks/v2-spec-396-quadrature-lo-generator-divided-clock/instruction.md) | PLL 与时钟 | 按规格构建模型 | `v4-396` | 待审核；原位保留 |
| [v2-test-clock-frequency](tasks/v2-test-clock-frequency/instruction.md) | PLL 与时钟 | 电路测试与表征 | `v4-362` | 待审核；原位保留 |
| [v2-test-comparator-delay](tasks/v2-test-comparator-delay/instruction.md) | 比较器与门限 | 电路测试与表征 | `v4-170` | 待审核；原位保留 |
| [v2-test-duty-cycle](tasks/v2-test-duty-cycle/instruction.md) | PLL 与时钟 | 电路测试与表征 | `v4-060` | 待审核；原位保留 |
| [v2-test-gain-settling](tasks/v2-test-gain-settling/instruction.md) | 放大与模拟信号处理 | 电路测试与表征 | `case-0018+v4-038+v4-370` | 待审核；原位保留 |
| [v2-test-hysteresis](tasks/v2-test-hysteresis/instruction.md) | 比较器与门限 | 电路测试与表征 | `v4-111` | 待审核；原位保留 |
| [v2-test-offset-search](tasks/v2-test-offset-search/instruction.md) | 比较器与门限 | 电路测试与表征 | `v4-109` | 待审核；原位保留 |
| [v2-test-online-gain](tasks/v2-test-online-gain/instruction.md) | 放大与模拟信号处理 | 电路测试与表征 | `v4-093+v4-038` | 待审核；原位保留 |
| [v2-test-por-sequence](tasks/v2-test-por-sequence/instruction.md) | 电源、复位与响应测试 | 电路测试与表征 | `case-0001-sky130-ajc-por` | 待审核；原位保留 |
| [v2-test-sampled-rms](tasks/v2-test-sampled-rms/instruction.md) | 放大与模拟信号处理 | 电路测试与表征 | `v4-074` | 待审核；原位保留 |
| [v2-test-time-protocol](tasks/v2-test-time-protocol/instruction.md) | PLL 与时钟 | 电路测试与表征 | `v4-346` | 待审核；原位保留 |

原目录为 `benchmark/tasks/<task-id>/`，整理中曾位于 `draftbench/tasks/`。封存记录保留原路径和哈希，作者读取工具通过 `experiments/benchmark_paths.py` 定位当前文件。
