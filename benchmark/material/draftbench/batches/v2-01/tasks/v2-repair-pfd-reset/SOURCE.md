# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。修复输入仍是完整错误源码。没有仿真，也没有把参考解里的复位写法写成唯一答案。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-pfd-reset/instruction.md)，blob `c397ed9d54e0c468286a400582045ca6bc1f2d6c`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-pfd-reset/SOURCE.md)，blob `f37af0f42b32a99d886ebcb999ea667382921b21`。身份文件是 [SOURCE.json](SOURCE.json)。

本题按已批准的诊断修复 spec #136 建设。`source_id` 为 `249`，来源组 `v4-family-249`，历史路径 `benchmark/reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix`。starter SHA256 `41023069a21d873c92ddd874ec7600edf1417db35f8a0cda642a0aa046b6415c`，healthy SHA256 `efd3bfdec4fed600b9a0e62bab1b6ff89cc1857356aa7178a00684cf26a5acca`。故障来自历史人工注错，原始工程故障形成过程未知。`revision` 为 `stimulus-r2`。四个单模块来源都保留历史人工注错 starter；本题是其中的单模块 PFD。

已保留的合同：`rstb` 低立即清零并取消挂起复位；有效时 `ref` 上升置 `up`，`fb` 上升置 `down`；两者都高后 80 ps 清零；下降沿不置位；复位期间的边沿不记忆；释放后只采纳新边沿；初态两输出 0；高电平 0.9 V；`tr=10 ps`；逻辑阈值 0.45 V；参数默认值保持源码默认 `vth=0.45`、`vh=0.9`、`reset_delay=80p`；终测覆盖两种不同激励；禁止条件也须满足按时启动要求。可整体重写该模块，但端口和上述默认值不收窄。

历史候选文件名 `dut.va` 现为 `/app/circuit.va`。本题没有 `environment/public/dut/`。历史 `environment/input/public_test.scs` 不是现在的 `/app/testbench` 入口；公开自测入口是 `check.py`。

## 建模选择

`starter_kind` 按已有错误模型处理：交付的是完整错误源码，不是只留端口的新壳。求解者可以整体重写模块。验收只看公开外部时序和电压，不规定内部状态变量。固定后端是 Spectre。

现行题面按已执行失败记 0、原因另记来写，并写明缺仿真器不是语义错误。历史题面原句是“不依靠运行外部程序或隐藏终评材料”，没有把工具链故障写成候选零分或未评分。历史 SOURCE 另写作者仿真校准已完成。SOURCE.json 仍写 `calibration_status: pending` 与 `agent_pilots: pending`。本次不删其中任何一句。

### 2026-10-28 补充（tolerance-r1）：用例网表写明容差与输出设置

D1 冻结前总协调定的第 (ii) 类题目修正：用例网表显式写出容差和输出设置。只改台架的容差和输出设置；激励、合同（`instruction.md`）、checker、参考解、候选、`v2_runtime.py` 与 `adc_linearity.py` 都不动。未仿真。

- 改了哪些行：`environment/input/public_test.scs`、`environment/starter/testbench/cases.json` 1 例、`tests/cases.json` 2 例，共 4 个网表。每个网表只改 options 与 tran 两条语句；激励、include、实例与 save 行逐字节不变。
  - 原有的 `simulatorOptions options reltol=1e-6 vabstol=1e-8` 末尾补 `iabstol=1e-12`；reltol、vabstol 原值就是 1e-6、1e-8，不改。
  - `tran` 语句末尾补 `errpreset=moderate`；`stop`、`maxstep` 不改。
- 取值与来源：标准线 `D1-TOLERANCES.md`（sha256 `55fa799a…`）与 `D1-TOLERANCES.json`（`fbbbebbb…`）；写法按标准线网表约定清单 `LIST.md` 第 3 版（`6a6b17cd…`）。
  - reltol 1e-6、vabstol 1e-8 V、iabstol 1e-12 A，D1 的 12 题一样。本题 checker 的判据：电压 25 mV，预期事件附近 20 ps 不评分；标准线按局部截断误差估计，这组容差下的解算误差应远小于最严的判据；这只是选值的依据，不是已证明的全局误差上界，实际误差、事件时刻和耗时待 Spectre 校准验证（D1 容差复审 TOL-01）。iabstol 取 Spectre 缺省 1e-12，本题 save 的都是电压。
  - `errpreset=moderate` 是 Spectre 的缺省。本题校准网表没写 errpreset，按缺省就是 moderate；现在写明，行为不变（运行环境当时是否另设，见下面“历史身份”一条）。
  - 本题不用 strobe，不写 strobeoutput。
  - precision 不写进用例网表，由主控另排一轮放在 Spectre 执行路径里；`src_allbrkpts` 等批次 C。
- 历史身份：10-10 历史作者校准（run `final-a5-cb789-equivalent-20261010T2140Z`）用的 `tests/cases.json`（`7e3a8aa3…`，在 git `fae1bac2` 中核对）只写了 reltol=1e-6、vabstol=1e-8，没有本轮补的其余设置。当时实际生效的容差未知，可能是 Spectre 缺省，也可能是运行环境的设置。所以改后的结果与历史结果按不同的执行身份对待。本文件前面各段说的网表或公开 `.scs`“未改”“逐字节不变”，只指当时那一轮。
- 旧版 EVAS 0.8.7 开发检查：参考解跑 2 个私有与 1 个公开用例，判决与改前最近一次旧版记录逐项相同（3/3 通过），输出行数与各行数值也相同。旧版日志回显的容差改前改后都是 reltol=1e-06、vabstol=1e-08、iabstol=1e-12。新写的参数没有被拒，也没有警告。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v2-repair-pfd-reset/`，D1 的对照作业从那里取原网表。改后 sha256：`environment/input/public_test.scs` `e3ff4efc…`；`environment/starter/testbench/cases.json` `e4925cf4…`；`tests/cases.json` `fe07616e…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。该记录不证明当前 Harbor 包。公开主集资格尚未建立。模型试做尚未完成。本地 checker 的手工外部波形不证明 Verilog-A 执行。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：SOURCE.json 的 `pending` 与旧 SOURCE“作者仿真校准已完成”不一致。本次不由参考解选择科学答案，也不指出应改的源码行。
