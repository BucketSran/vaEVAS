# uwb-tx-01：IR-UWB 发射机种子链第一批

本批从 [IR-UWB TX 种子链系统资产](../../circuits/ir-uwb-tx/README.md) 切出 8 道题，覆盖五类工程动作里的四类，难度从基础到难。
电路、行为约定和系统级 gold 的验证见功能族 README 和 [SPEC.md](../../circuits/ir-uwb-tx/SPEC.md)；任务记录 [#223](https://github.com/BucketSran/vaEVAS/issues/223)。
本批题目都还没有人工审核，也没有模型实测。

## 题目

| 题目 | 工程动作 | 预期难度 | gold 来源 | 校准（EVAS 0.8.7，暂用后端） |
| --- | --- | --- | --- | --- |
| [uwb-spec-dppm-fsk-encoder](tasks/uwb-spec-dppm-fsk-encoder/instruction.md) | 按规格建模 · 单模块 | 基础 | `module/dppm_fsk_encoder8.va` | 参考解、替代实现 1 分；9/9 错误版本 0 分 |
| [uwb-spec-ro-frequency-cal](tasks/uwb-spec-ro-frequency-cal/instruction.md) | 按规格建模 · 单模块 | 中 | `module/ro_frequency_cal.va` | 1 / 1；15/15 |
| [uwb-spec-pulse-generator](tasks/uwb-spec-pulse-generator/instruction.md) | 按规格建模 · 单模块 | 中 | `module/pulse_generator.va` | 1 / 1；12/12 |
| [uwb-spec-rf-branch](tasks/uwb-spec-rf-branch/instruction.md) | 按规格建模 · 单模块（动态） | 中 | `module/rf_ro_branch.va` | 1 / 1；11/11 |
| [uwb-spec-branch-scheduler](tasks/uwb-spec-branch-scheduler/instruction.md) | 按规格建模 · 单模块 | 难 | `module/ro_scheduler8.va` | 1 / 1；12/12 |
| [uwb-integrate-seed-tx](tasks/uwb-integrate-seed-tx/instruction.md) | 扩展与集成 · 现成部件组装 | 中～难 | `system/tx_seed.va` | 1 / 1；12/12 |
| [uwb-repair-scheduler-warm-restart](tasks/uwb-repair-scheduler-warm-restart/instruction.md) | 诊断与修复 · 多模块系统 | 难 | 种子链 + 调度器故障 | 1 / 1；起始工程与 10/10 错误修复 0 分 |
| [uwb-test-pulse-decoder](tasks/uwb-test-pulse-decoder/instruction.md) | 电路测试与表征 · 在线仪表 | 难 | 为本题新写的 VA 仪表 | 1 / 1；13/13 |

8 题都在 implementation 阶段通过静态检查，`pending = ["runtime"]`。每题的错误版本、违反的条款和首个失败项在各自 `results/calibration.json`。
难度是出题时的预期，以后按模型实测调整。8 题共用同一电路，同源关系按 `source_group = "uwb-tx-seed"` 登记，统计时不能当成相互独立的能力证据。

## 共同约定

- **后端。** 声明后端是当前 EVAS；它还跑不了这些模型（[#229](https://github.com/BucketSran/vaEVAS/issues/229)，另有会话在补），所以各题 `pending` 含 `runtime`，作者运行暂用 EVAS 0.8.7。EVAS 补齐后要重跑每题的参考解和校准样本。
- **评分代码。** 各题 `environment/starter/testbench/uwbtask.py` 是 [kit/uwbtask.py](kit/uwbtask.py) 的逐字节副本；边沿记录仪和时钟源同理。改 kit 后用同步脚本更新各题副本并重做受影响的校准。
- **期望值。** checker 从 Spec 规则和激励独立算期望，不读参考解波形；每题用一个正确的替代实现和若干典型错误版本校准（`tests/calibration/`）。

## 暂用后端 EVAS 0.8.7 的限制

建设中发现旧 EVAS 的几处缺陷，各题已避开或记录，换到当前 EVAS（#229）或 Spectre 后要重新确认：

- 同一模块两个实例都用 `idt()` 时，只有一个在积分（uwb-spec-rf-branch 的替代实现因此改用闭式）。
- Verilog-A 层次里整根总线端口按子模块的端口名当全局网络解析，不走父模块映射；`V(y) <+ V(x)` 复制节点的过阈会被边沿记录仪漏掉。修复题改为在测试网表里连接整链；集成题要求总线端口接同名网络，并从保存的波形插值过阈。
- 内存约为 `$strobe` 条数 × 计划步数 × 2.1 KB。校准题因此只跑默认参数的第一个窗口，容差放到 20 ps；完整 44.5 µs 校准由系统资产的 `check_system.py` 覆盖。把边沿记录仪改成单条 `$strobe` 可以省一半内存，待做。

## 审核时重点看

- 每题的 Spec 是否足够让人确定什么输出算对，参数和合法范围是否齐全；难度分层是否合理，同源题之间是否有足够区别。
- 时间容差（多为 2 ps，校准题 20 ps）是否合适：它要容纳仿真器的过阈定位误差。
- 需要你决定的具体问题：
  - 调度器：两个支路都处于空闲 HOLD 时接管哪一个，SPEC 没规定。建模题把这种情形排除；修复题保留 gold 的“先查槽 0”并写成规则（修复题保留原代码结构）。是否改成“接管空闲最久的支路”。
  - 保持规则：T_pre > t_hold 时继续保持（SPEC 4.7），仍待确认。
  - 解码仪表：位置容差 δ/4 会让健康发射机在码 100 时报 11/90 个脉冲出错，是否放宽到约 0.4δ；公开用例里没有 err=1 的脉冲，是否加一个公开合成用例。
  - 集成题：题面写了校准、PG、调度器规则，篇幅较长；“总线端口接同名网络”是迁就旧 EVAS 的规则，EVAS 或 Spectre 能跑后应放宽。
  - 修复题：目录交付不套用单文件固定尾段，改写了三句，措辞待确认。
  - 若干题有错误版本只能在终评检出（例如 RF 支路 11 个里 5 个）；是否把对应场景挪一个进公开用例。
