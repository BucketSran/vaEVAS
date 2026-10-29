# 来源与迁移记录

2026-10-27 第二批迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。修复输入仍是完整错误源码。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-repair-reset-sequencer/checks.json`（不入库）。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-reset-sequencer/instruction.md)，blob `0b1aa5a4d5bc41ad5f843af34a44d6240044c717`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-reset-sequencer/SOURCE.md)，blob `f37af0f42b32a99d886ebcb999ea667382921b21`。身份文件是 [SOURCE.json](SOURCE.json)。

本题按已批准的诊断修复 spec #136 建设。`source_id` 为 `272`，来源组 `v4-family-272`，历史路径 `benchmark/reference/v4/release/benchmarkv4-r53/tasks/1272-reset-release-sequencer-bugfix`，`revision` 为 `instruction-r2`。starter SHA256 `1f7df42b4bae031dd03c5fba26c68efc5849611cf2c171a5e6d1539e6bebc23f`，healthy SHA256 `06fde0f44a8c4f485467ce359e76116db7d214e1c64f1d3589bbda6e940c15ad`。故障来自历史人工注错，原始工程故障形成过程未知。

已保留的合同：仅在 clk 上升沿更新；rst 高或 supply_ok/bias_ok 不高时 stage=0，否则递增并在 final_stage 饱和；stage1、stage2、ready 分别在 stage≥1、≥2、≥final_stage 时为 0.9 V，progress=0.9*stage/final_stage，其余输出 0；初态 stage=0；停钟期间 rst 变化不更新状态；final_stage 只取整数 3..5 且终测覆盖该范围，其他参数为源码默认值（`vth=0.45`、`vhi=0.9`、`tr=60p`）；clk 交点前后 0.2 ns 内输入稳定，与 clk 重合的输入跳变不评分；同拍复位与推进时清零优先、不输出 ready；终测使用不同资格与复位轨迹。

同源关系：首批 30 题与 R01 两题中没有同源题；规划池 C414 为“保留组件或变体”，没有候选。

## 建模选择

`starter_kind` 按已有错误模型处理：`/app/circuit.va` 与历史 `environment/input/dut.va` 逐字节相同。参考解 `solution/circuit.va` 与 `solution/files/dut.va` 逐字节相同。公开自测入口是 `check.py`，公开用例取原私有 `tests/cases.json` 的第一个用例 `public-reproduction`（final_stage=3）；历史 `environment/input/public_test.scs` 不复制到 `/app/testbench`。

现行题面按已执行失败记 0、原因另记来写，并写明缺仿真器不是语义错误。

## 待定项

`grading` 和 `runtime` 待定。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，不证明当前 Harbor 包。SOURCE.json 的 `pending` 与旧 SOURCE“作者仿真校准已完成”不一致，本次不删其中任何一句。

checker 的电压容差 25 mV 与事件邻域 guard 0.12 ns 原合同没有写出。2026-10-28 修正（fix-a-r1，F03）按 checker 现值写入题面 Spec：每个保存点允许 25 mV；t=0 后最初 0.12 ns 不评分；每个 `clk` 上升交点前后 0.12 ns 内不评分，因此输出连同 `tr` 平滑须在 0.12 ns 内到达新电平。checker、原激励与参考解未改。

迁移时终评两例只有 `final_stage=3` 与 `5`，题面“终测覆盖 3–5 整个范围”不成立。2026-10-28 修正（fix-a-r1，F04）新增私有用例 `final-stage-4`（`final_stage=4`；qualification 与 reset 迹线另设：第 4 拍到 4 并在第 5、6 拍保持饱和，rst 跨第 7 拍清零，supply_ok 跨第 11 拍、bias_ok 跨第 16 拍各清零一次，第 15 拍再次到 4；输入跳变离 clk 上升与下降交点各约 0.3 ns），原两例未改。

开发证据（记录见文首本地目录）：阶段结果：EVAS 02dee32b 上参考解 2 个私有用例 a–c 完成且 checker 通过，公开台架 a–c 完成；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化；起始错误模型 3/3 个用例被判失败。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

fix-a-r1 复跑（2026-10-28，记录在本地 `runs/t3-batch2-20261027/fix-a-r1/`，不入库）：旧版 EVAS 0.8.7 上参考解私有 3/3（含 `final-stage-4`）、公开 1/1 通过，只用网格行复判无变化；只在端点正确的错误模型（`final_stage>3` 一律按 5 处理）原两例都通过，在 `final-stage-4` 被拒。理想阶跃探针确认题面所写 25 mV、0.12 ns 即 checker 实际尺度。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。
