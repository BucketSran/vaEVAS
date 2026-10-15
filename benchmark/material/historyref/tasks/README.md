# 早期历史题包

本目录保存 41 个早期题包：8 个 `va01` 至 `va08` 资产，以及旧七类首批的 33 个专属目录。
旧首批清单有 35 题，其中复用 `va07`、`va08`，不复制题包或额外计数。
这些题包用于复用材料、恢复旧流程和解释历史成绩，不属于当前 57 个草稿或正式题集。

原 ID、题面、起始工程、参考解、随题 checker 和 `SOURCE.md` 的同源字段继续保留。
移动只更新导航与作者读取路径；封存回执、源码快照、结果 JSON 和哈希不改写。
下表保留原题包路径命名空间；它们曾暂存于 `benchmark/material/draftbench/tasks/`。

## 原始记录

- [六题能力初筛](../../../../experiments/va_screen/README.md)，`va07` 与 `va08` 不加入其成绩分母。
- [旧七类首批说明](../legacy-authoring/first-batch/README.md)与[同源元数据](../legacy-authoring/first-batch/METADATA.md)。其中“正式”等状态指当时批次，不是当前录取结论。
- 五份原清单：[建模与修复](first_batch-model_repair.json)、[辨识](first_batch-identification.json)、[集成](first_batch-integration.json)、[验证与测量](first_batch-verification_measurement.json)、[仿真实现优化](first_batch-optimization.json)。文件保留搬迁前字节。
- [历史执行与证据边界](../../../../experiments/benchmark_first_batch/README.md)。

复用到新批次时先说明新的工程工作与原题关系；不继承旧审核、运行资格或分发许可。

## 文件与同源索引

| 题包 | 所属历史批次 | 同源组 | 原路径 |
| --- | --- | --- | --- |
| [identify-adc-driver-settling](identify-adc-driver-settling/SOURCE.md) | 旧七类首批 | `original-identified_driver-identification` | `benchmark/tasks/identify-adc-driver-settling/` |
| [identify-comparator-overdrive](identify-comparator-overdrive/SOURCE.md) | 旧七类首批 | `original-identified_comparator-identification` | `benchmark/tasks/identify-comparator-overdrive/` |
| [identify-pll-hop-dynamics](identify-pll-hop-dynamics/SOURCE.md) | 旧七类首批 | `original-identified_pll-identification` | `benchmark/tasks/identify-pll-hop-dynamics/` |
| [identify-sc-clocked-filter](identify-sc-clocked-filter/SOURCE.md) | 旧七类首批 | `original-identified_sc-identification` | `benchmark/tasks/identify-sc-clocked-filter/` |
| [identify-sh-acquisition](identify-sh-acquisition/SOURCE.md) | 旧七类首批 | `original-sh-identification` | `benchmark/tasks/identify-sh-acquisition/` |
| [integrate-agc-attack-release](integrate-agc-attack-release/SOURCE.md) | 旧七类首批 | `original-receiver-agc` | `benchmark/tasks/integrate-agc-attack-release/` |
| [integrate-iq-baseband-calibration](integrate-iq-baseband-calibration/SOURCE.md) | 旧七类首批 | `original-iq-baseband` | `benchmark/tasks/integrate-iq-baseband-calibration/` |
| [integrate-pipeline-adc-alignment](integrate-pipeline-adc-alignment/SOURCE.md) | 旧七类首批 | `original-pipeline-adc` | `benchmark/tasks/integrate-pipeline-adc-alignment/` |
| [integrate-pll-hop-reacquisition](integrate-pll-hop-reacquisition/SOURCE.md) | 旧七类首批 | `original-hopping-pll` | `benchmark/tasks/integrate-pll-hop-reacquisition/` |
| [integrate-tdc-measurement-chain](integrate-tdc-measurement-chain/SOURCE.md) | 旧七类首批 | `original-tdc-chain` | `benchmark/tasks/integrate-tdc-measurement-chain/` |
| [measure-adc-spectrum](measure-adc-spectrum/SOURCE.md) | 旧七类首批 | `first-batch-measure-adc-spectrum` | `benchmark/tasks/measure-adc-spectrum/` |
| [measure-comparator-delay-hysteresis](measure-comparator-delay-hysteresis/SOURCE.md) | 旧七类首批 | `first-batch-measure-comparator-delay-hysteresis` | `benchmark/tasks/measure-comparator-delay-hysteresis/` |
| [measure-pll-relock-jitter](measure-pll-relock-jitter/SOURCE.md) | 旧七类首批 | `first-batch-measure-pll-relock-jitter` | `benchmark/tasks/measure-pll-relock-jitter/` |
| [measure-sh-acquisition-droop](measure-sh-acquisition-droop/SOURCE.md) | 旧七类首批 | `original-periodic-sh-observation` | `benchmark/tasks/measure-sh-acquisition-droop/` |
| [optimize-flash-thresholds](optimize-flash-thresholds/SOURCE.md) | 旧七类首批 | `original-flash-thresholds-optimization` | `benchmark/tasks/optimize-flash-thresholds/` |
| [optimize-power-monitor](optimize-power-monitor/SOURCE.md) | 旧七类首批 | `original-power-monitor-optimization` | `benchmark/tasks/optimize-power-monitor/` |
| [optimize-sar-calendar](optimize-sar-calendar/SOURCE.md) | 旧七类首批 | `original-sensor-sar-calendar` | `benchmark/tasks/optimize-sar-calendar/` |
| [optimize-uart-calendar](optimize-uart-calendar/SOURCE.md) | 旧七类首批 | `original-uart-sampling-calendar` | `benchmark/tasks/optimize-uart-calendar/` |
| [optimize-vco-step](optimize-vco-step/SOURCE.md) | 旧七类首批 | `original-vco-boundstep-optimization` | `benchmark/tasks/optimize-vco-step/` |
| [repair-sar-abort](repair-sar-abort/SOURCE.md) | 旧七类首批 | `sar-controller-original` | `benchmark/tasks/repair-sar-abort/` |
| [repair-sigma-delta-phase](repair-sigma-delta-phase/SOURCE.md) | 旧七类首批 | `sigma-delta-original` | `benchmark/tasks/repair-sigma-delta-phase/` |
| [repair-uvlo-recovery](repair-uvlo-recovery/SOURCE.md) | 旧七类首批 | `uvlo-monitor-original` | `benchmark/tasks/repair-uvlo-recovery/` |
| [repair-zoom-sequencer](repair-zoom-sequencer/SOURCE.md) | 旧七类首批 | `zoom-timing-original` | `benchmark/tasks/repair-zoom-sequencer/` |
| [spec-cdr-phase-detector](spec-cdr-phase-detector/SOURCE.md) | 旧七类首批 | `cdr-phase-original` | `benchmark/tasks/spec-cdr-phase-detector/` |
| [spec-latched-comparator](spec-latched-comparator/SOURCE.md) | 旧七类首批 | `latched-comparator-original` | `benchmark/tasks/spec-latched-comparator/` |
| [spec-sample-hold-acquisition](spec-sample-hold-acquisition/SOURCE.md) | 旧七类首批 | `sample-hold-original` | `benchmark/tasks/spec-sample-hold-acquisition/` |
| [spec-sigma-delta](spec-sigma-delta/SOURCE.md) | 旧七类首批 | `sigma-delta-original` | `benchmark/tasks/spec-sigma-delta/` |
| [spec-uvlo-deglitch](spec-uvlo-deglitch/SOURCE.md) | 旧七类首批 | `uvlo-monitor-original` | `benchmark/tasks/spec-uvlo-deglitch/` |
| [va01-and2](va01-and2/SOURCE.md) | 早期 VA | `lab` | `benchmark/tasks/va01-and2/` |
| [va02-sar-handshake](va02-sar-handshake/SOURCE.md) | 早期 VA | `lab` | `benchmark/tasks/va02-sar-handshake/` |
| [va03-zoom-timing](va03-zoom-timing/SOURCE.md) | 早期 VA | `lab` | `benchmark/tasks/va03-zoom-timing/` |
| [va04-gain-calibration](va04-gain-calibration/SOURCE.md) | 早期 VA | `lab` | `benchmark/tasks/va04-gain-calibration/` |
| [va05-dynamic-vco](va05-dynamic-vco/SOURCE.md) | 早期 VA | `cadence` | `benchmark/tasks/va05-dynamic-vco/` |
| [va06-loaded-opamp](va06-loaded-opamp/SOURCE.md) | 早期 VA | `cadence` | `benchmark/tasks/va06-loaded-opamp/` |
| [va07-triangle-repair](va07-triangle-repair/SOURCE.md) | 早期 VA | `repository-triangle-oscillator` | `benchmark/tasks/va07-triangle-repair/` |
| [va08-adc-linearity](va08-adc-linearity/SOURCE.md) | 早期 VA | `repository-owned-original-adc-linearity` | `benchmark/tasks/va08-adc-linearity/` |
| [verify-comparator-overdrive](verify-comparator-overdrive/SOURCE.md) | 旧七类首批 | `first-batch-verify-comparator-overdrive` | `benchmark/tasks/verify-comparator-overdrive/` |
| [verify-nonoverlap-stimulus](verify-nonoverlap-stimulus/SOURCE.md) | 旧七类首批 | `first-batch-verify-nonoverlap-stimulus` | `benchmark/tasks/verify-nonoverlap-stimulus/` |
| [verify-pll-lock-checker](verify-pll-lock-checker/SOURCE.md) | 旧七类首批 | `first-batch-verify-pll-lock-checker` | `benchmark/tasks/verify-pll-lock-checker/` |
| [verify-sar-flow](verify-sar-flow/SOURCE.md) | 旧七类首批 | `first-batch-verify-sar-flow` | `benchmark/tasks/verify-sar-flow/` |
| [verify-sh-settling-checker](verify-sh-settling-checker/SOURCE.md) | 旧七类首批 | `original-periodic-sh-observation` | `benchmark/tasks/verify-sh-settling-checker/` |
