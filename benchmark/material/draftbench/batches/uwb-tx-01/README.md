# uwb-tx-01：IR-UWB 发射机种子链第一批

本批从 [IR-UWB TX 种子链系统资产](../../circuits/ir-uwb-tx/README.md) 切出 8 道题，覆盖五类工程动作里的四类，难度从基础到难。
电路、行为约定和系统级 gold 的验证见功能族 README 和 [SPEC.md](../../circuits/ir-uwb-tx/SPEC.md)；任务记录 [#223](https://github.com/BucketSran/vaEVAS/issues/223)。
本批题目都还没有人工审核，也没有模型实测。

## 题目

| 题目 | 工程动作 | 预期难度 | gold 来源 | 状态 |
| --- | --- | --- | --- | --- |
| [uwb-spec-dppm-fsk-encoder](tasks/uwb-spec-dppm-fsk-encoder/instruction.md) | 按规格建模 · 单模块 | 基础 | `module/dppm_fsk_encoder8.va` | implementation；EVAS 0.8.7 上参考解 1 分，校准见题包 |
| uwb-spec-ro-frequency-cal | 按规格建模 · 单模块 | 中 | `module/ro_frequency_cal.va` | 建设中 |
| uwb-spec-pulse-generator | 按规格建模 · 单模块 | 中 | `module/pulse_generator.va` | 建设中 |
| uwb-spec-branch-scheduler | 按规格建模 · 单模块 | 难 | `module/ro_scheduler8.va` | 建设中 |
| uwb-spec-rf-branch | 按规格建模 · 单模块（动态） | 中 | `module/rf_ro_branch.va` | 建设中 |
| uwb-integrate-seed-tx | 扩展与集成 · 现成部件组装 | 中～难 | `system/tx_seed.va` | 建设中 |
| uwb-repair-scheduler-warm-restart | 诊断与修复 · 多模块系统 | 难 | 种子链 + 调度器故障 | 建设中 |
| uwb-test-pulse-decoder | 电路测试与表征 · 指标提取 | 难 | 新写 VA 仪表 | 建设中 |

难度是出题时的预期，以后按模型实测调整。8 题共用同一电路，同源关系按 `source_group = "uwb-tx-seed"` 登记，统计时不能当成相互独立的能力证据。

## 共同约定

- **后端。** 声明后端是当前 EVAS；它还跑不了这些模型（[#229](https://github.com/BucketSran/vaEVAS/issues/229)，另有会话在补），所以各题 `pending` 含 `runtime`，作者运行暂用 EVAS 0.8.7。EVAS 补齐后要重跑每题的参考解和校准样本。
- **评分代码。** 各题 `environment/starter/testbench/uwbtask.py` 是 [kit/uwbtask.py](kit/uwbtask.py) 的逐字节副本；边沿记录仪和时钟源同理。改 kit 后用同步脚本更新各题副本并重做受影响的校准。
- **期望值。** checker 从 Spec 规则和激励独立算期望，不读参考解波形；每题用一个正确的替代实现和若干典型错误版本校准（`tests/calibration/`）。

## 审核时重点看

- 每题的 Spec 是否足够让人确定什么输出算对，参数和合法范围是否齐全；
- 难度分层是否合理，同源题之间是否有足够区别；
- 时间容差（多为 2 ps）是否合适：它要容纳仿真器的过阈定位误差。
