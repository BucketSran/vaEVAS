# v3-01：五条扩充路线题包

本批保留原 19 道题包、参考解、独立 checker 和来源关系。目录搬迁不完成格式改造或本版人工审核。
任务 ID、`source_group`、历史设计版本和作者结果保持原身份；来源、同源变体与覆盖缺口见[56 题总览](../../TASKS.md)。

当前阶段：已有实现与历史作者记录，本版完整题目审核待进行。
已确认的是五类选题及功能方向；尚未确认每题当前合同、验收方案与新规范题包。
后续先完成 R01 代表题合同审核，再按共用电路小组推进；本次没有新增模型实验或仿真校准。
原校准与交付范围见[作者记录](../../../../../experiments/benchmark_next/README.md)，不能由历史参考解通过推断本版题目已经录取。

## 审核清单

下表每行指向实际题包。审核后在该行记录审核版本、结论与去向；仅被录取的题包移动到正式 `benchmark/tasks/`。
目前全部保留在本批，没有录取记录。

| 题包 / 英文或原版题面 | 电路功能 | 工程动作 | 同源组 | 本版审核 / 去向 |
| --- | --- | --- | --- | --- |
| [v3-calibration-common-mode-servo](tasks/v3-calibration-common-mode-servo/instruction.md) | 模拟校准与伺服 | 扩展与集成 | `calibration-frontends-306-369-390` | 待审核；原位保留 |
| [v3-calibration-continuous-offset](tasks/v3-calibration-continuous-offset/instruction.md) | 模拟校准与伺服 | 扩展与集成 | `calibration-frontends-306-369-390` | 待审核；原位保留 |
| [v3-calibration-fractional-pll](tasks/v3-calibration-fractional-pll/instruction.md) | PLL 与时钟 | 扩展与集成 | `fractional-pll-302` | 待审核；原位保留 |
| [v3-converter-adc-spectrum](tasks/v3-converter-adc-spectrum/instruction.md) | DAC 与转换器指标 | 电路测试与表征 | `first-batch-measure-adc-spectrum` | 待审核；原位保留 |
| [v3-converter-dac-linearity](tasks/v3-converter-dac-linearity/instruction.md) | DAC 与转换器指标 | 电路测试与表征 | `repository-owned-dac-scan` | 待审核；原位保留 |
| [v3-converter-nonideal](tasks/v3-converter-nonideal/instruction.md) | DAC 与转换器指标 | 按规格构建模型 | `v4-025` | 待审核；原位保留 |
| [v3-converter-segmented](tasks/v3-converter-segmented/instruction.md) | DAC 与转换器指标 | 按规格构建模型 | `v4-014` | 待审核；原位保留 |
| [v3-converter-subradix](tasks/v3-converter-subradix/instruction.md) | DAC 与转换器指标 | 按规格构建模型 | `v4-243` | 待审核；原位保留 |
| [v3-converter-thermometer](tasks/v3-converter-thermometer/instruction.md) | DAC 与转换器指标 | 按规格构建模型 | `v4-018` | 待审核；原位保留 |
| [v3-filter-ctle](tasks/v3-filter-ctle/instruction.md) | 滤波、均衡与 RF | 按规格构建模型 | `verilogalib-ctle` | 待审核；原位保留 |
| [v3-filter-envelope](tasks/v3-filter-envelope/instruction.md) | 滤波、均衡与 RF | 按规格构建模型 | `v4-336` | 待审核；原位保留 |
| [v3-filter-iq-conversion](tasks/v3-filter-iq-conversion/instruction.md) | 滤波、均衡与 RF | 按规格构建模型 | `v4-364+400` | 待审核；原位保留 |
| [v3-filter-programmable-lp](tasks/v3-filter-programmable-lp/instruction.md) | 滤波、均衡与 RF | 扩展与集成 | `v4-334` | 待审核；原位保留 |
| [v3-filter-sweep-measurement](tasks/v3-filter-sweep-measurement/instruction.md) | 滤波、均衡与 RF | 电路测试与表征 | `original-filter-measurement` | 待审核；原位保留 |
| [v3-ldo-response-experiment](tasks/v3-ldo-response-experiment/instruction.md) | 电源、复位与响应测试 | 电路测试与表征 | `adb-ldo-ota5` | 待审核；原位保留 |
| [v3-ldo-startup-measurement](tasks/v3-ldo-startup-measurement/instruction.md) | 电源、复位与响应测试 | 电路测试与表征 | `adb-ldo-ota5` | 待审核；原位保留 |
| [v3-ota-continuous](tasks/v3-ota-continuous/instruction.md) | 连续 OTA 动态 | 按规格构建模型 | `jku-ota-dynamics` | 待审核；原位保留 |
| [v3-ota-data-model](tasks/v3-ota-data-model/instruction.md) | 连续 OTA 动态 | 从数据建立模型 | `jku-ota-dynamics` | 待审核；原位保留 |
| [v3-ota-step-measurement](tasks/v3-ota-step-measurement/instruction.md) | 连续 OTA 动态 | 电路测试与表征 | `jku-ota-dynamics` | 待审核；原位保留 |

原目录为 `benchmark/tasks/<task-id>/`，整理中曾位于 `draftbench/tasks/`。封存记录保留原路径和哈希，作者读取工具通过 `experiments/benchmark_paths.py` 定位当前文件。
