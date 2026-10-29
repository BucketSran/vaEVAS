# 来源与迁移记录

2026-10-27 第二批迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。修复输入仍是完整错误源码。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-repair-debounce-latch/checks.json`（不入库）。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-debounce-latch/instruction.md)，blob `882a080b812065950ca015e370df82fc569fe997`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-debounce-latch/SOURCE.md)，blob `f37af0f42b32a99d886ebcb999ea667382921b21`。身份文件是 [SOURCE.json](SOURCE.json)。

本题按已批准的诊断修复 spec #136 建设。`source_id` 为 `005`，来源组 `v4-family-005`，历史路径 `benchmark/reference/v4/release/benchmarkv4-r53/tasks/1005-debounce-latch-bugfix`。starter SHA256 `62450f5aaee354ec7d3996a5547c13c8f120655821c7ee3c219fe454c0759874`，healthy SHA256 `79afb58d6a0c2a9719a0fb8f1e69e7e9750d7d9d21bfad6ba8eee85334009f1a`。故障来自历史人工注错，原始工程故障形成过程未知。

已保留的合同：sig 上升沿启动 12 ns 连续高资格；sig 回落或低有效 rst_n 立即取消并清零；复位释放时 sig 已高不启动资格，须等待下一上升沿；初态 out=0；逻辑阈值 0.45 V；固定参数为源码默认值 `vth=0.45`、`vdd=0.9`、`stable=12n`、`tr=500p`；终测覆盖两种不同激励；禁止条件也须满足按时启动要求。可整体重写该模块，但端口和上述默认值不收窄。

同源关系：规划池 C176-S1 的主来源是 v4:005-debounce-latch，动作为按规格建模；本题是诊断修复，两者各自保留身份，不重复计数。首批 30 题与 R01 两题中没有同源题。

## 建模选择

原句“输入上升沿启动12ns连续高资格”译为：上升沿开始 12 ns 资格，sig 在此期间持续为高，资格完成时 out 变高。输出高电平用源码参数 `vdd` 表述，这是已有参数角色的对应，不是新数值。

`starter_kind` 按已有错误模型处理：`/app/circuit.va` 与历史 `environment/input/dut.va` 逐字节相同。参考解 `solution/circuit.va` 与 `solution/files/dut.va` 逐字节相同。历史 `environment/input/public_test.scs` 不复制到 `/app/testbench`；公开自测入口是 `check.py`，公开用例取原私有 `tests/cases.json` 的第一个用例 `public-reproduction`，其余用例只在终评使用。

现行题面按已执行失败记 0、原因另记来写，并写明缺仿真器不是语义错误。历史题面原句是“不依靠运行外部程序或隐藏终评材料”。

## 待定项

`grading` 和 `runtime` 待定。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，不证明当前 Harbor 包。SOURCE.json 仍写 `calibration_status: pending` 与 `agent_pilots: pending`，与旧 SOURCE“作者仿真校准已完成”不一致，本次不删其中任何一句。

checker 的电压容差 25 mV 与事件邻域 guard 0.6 ns 原合同没有写出。2026-10-28 修正（fix-a-r1，F03）按 checker 现值写入题面 Spec：每个保存点允许 25 mV；t=0 后最初 0.6 ns 不评分；`sig` 或 `rst_n` 下降交点、资格完成时刻前后 0.6 ns 内不评分，因此输出连同 `tr` 平滑须在 0.6 ns 内到达新电平。checker、激励与参考解未改。

开发证据（记录见文首本地目录）：阶段结果：EVAS 02dee32b 上参考解 2 个私有用例 a–c 完成且 checker 通过，公开台架 a–c 完成；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化；起始错误模型 3/3 个用例被判失败。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

fix-a-r1 复跑（2026-10-28，记录在本地 `runs/t3-batch2-20261027/fix-a-r1/`，不入库）：旧版 EVAS 0.8.7 上参考解私有 2/2、公开 1/1 仍通过，只用网格行复判无变化；按 checker 构造的理想阶跃探针确认题面所写 25 mV、0.6 ns 起始点与事件邻域即 checker 实际尺度。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。
