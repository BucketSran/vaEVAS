# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。五个错误工程文件都仍可改，没有把交付收成单个文件，也没有仿真。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-uvlo-reset-chain/instruction.md)，blob `48faa228c37c170258fcd021fa32e4b41a09a3ea`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-uvlo-reset-chain/SOURCE.md)，blob `f37af0f42b32a99d886ebcb999ea667382921b21`。身份文件是 [SOURCE.json](SOURCE.json)。

本题按已批准的诊断修复 spec #136 建设。`source_id` 为 `case-0009`，来源组 `original-uvlo-chain-case0009`，`provenance` 为仓库原创行为电源控制链。`revision` 为 `author-va-r2`。因果模块是 UVLO hysteresis、continuous qualification reset release、enable gate、clocked stateful downstream。故障来源记录为 artificial engineering-motivated stale qualification deadline。这不是晶体管 POR。

已保留的合同：上穿 0.65 V 产生 `pgood`，下穿 0.55 V 撤销，迟滞区保持；`pgood` 连续高 10 ns 后 `resetb` 释放；失效立即断言并取消旧计时，再次有效必须重计完整 10 ns；`enable` 为两者同时有效；`activity` 初值 0，有效时每个 `clk` 上升沿加 0.1 V，否则清零，保护撤销也清零；正常供电必须出现下游递增。逻辑高 0.9 V，逻辑阈值 0.45 V。传播与平滑在 0.15 ns 内完成，10 ns 资格允许 0.15 ns 传播容差。公开调参窗口：上阈值 0.64..0.66 V，下阈值 0.54..0.56 V，release delay 9.9..10.1 ns。源码默认值 `high=0.65`、`low=0.55`、`delay=10n`、`tr=10p` 保留。禁止条件也须满足按时启动要求。

可编辑文件是 `/app/circuit.va`（原 `dut.va` 顶层连接）以及原文件名 `/app/uvlo.va`、`/app/release.va`、`/app/enable.va`、`/app/downstream.va`。没有固定 `public/dut` 目录。历史 `environment/input/public_test.scs` 不是现在的 testbench 入口。

## 建模选择

这是多文件已有模型，不是只留端口的新壳。五个文件都收集。允许改指定模块、连接和设计参数，也允许在这些文件内整体重建。四个模块职责必须还在。验收只看公开外部时序和电压。

现行题面写已执行失败记 0、原因另记，缺 Spectre 不是语义错误。历史题面没有把工具链故障写成零分。旧 SOURCE 写作者仿真校准已完成，SOURCE.json 仍写 `calibration_status: pending` 与 `agent_pilots: pending`。本题按五文件规则说明采集每个已声明文件的当前内容；不使用仅适用单文件的固定尾段。Deliverable、artifacts和安装清单保持同一五文件集合。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 2 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r1b：NF-02（NF02-28-1）
- rewrite-r1b：NF-13（NF13-28-1-alt1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r1b/orig/v2-repair-uvlo-reset-chain/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `environment/input/enable.va` | `2e2ae744b28cb2d63ca4cbe14df7c83d987942ce20cb2ce7c825bf931939cac4` | `6b01e99a70c76df919158e06305f05b6bdb45f6e54e67cd69bf2b737329b0aea` |
| `environment/starter/enable.va` | `2e2ae744b28cb2d63ca4cbe14df7c83d987942ce20cb2ce7c825bf931939cac4` | `6b01e99a70c76df919158e06305f05b6bdb45f6e54e67cd69bf2b737329b0aea` |
| `solution/enable.va` | `2e2ae744b28cb2d63ca4cbe14df7c83d987942ce20cb2ce7c825bf931939cac4` | `6b01e99a70c76df919158e06305f05b6bdb45f6e54e67cd69bf2b737329b0aea` |
| `solution/files/enable.va` | `2e2ae744b28cb2d63ca4cbe14df7c83d987942ce20cb2ce7c825bf931939cac4` | `6b01e99a70c76df919158e06305f05b6bdb45f6e54e67cd69bf2b737329b0aea` |

- 本文件删去了改写写进来的一节“改写（#270 NF-02 / NF-13），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-repair-uvlo-reset-chain/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 6 组（用例、候选）两版判决全部相同（3 组都通过、3 组都被拒）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 `runs/t3-spectre-batchD-20261028/preread-sui01-d2/PREREAD.md` 第 3 节与同目录 `decision1.json`。
- 退回后的 4 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/28-v2-repair-uvlo-reset-chain/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- `enable.va` 的四份副本（参考解 2 份、候选可见的起始模型 `environment/starter/enable.va` 与 `environment/input/enable.va`）回到原写法；`release.va` 未动。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。它不证明当前 Harbor 包。公开主集资格尚未建立。手工外部波形不证明 Verilog-A 执行。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：SOURCE.json 的 pending 与旧 SOURCE 的“校准已完成”不一致。本次不指出应修改的源码行，也不用参考解里的 `deadline=-1` 写法代替公开取消规则。
