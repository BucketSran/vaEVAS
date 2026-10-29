# 来源与迁移记录

2026-10-27 第二批迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。修复输入仍是完整错误源码。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-repair-uvlo-brownout/checks.json`（不入库）。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-uvlo-brownout/instruction.md)，blob `2240b4070b3974542bdf2167dc4fffc509b7ab48`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-repair-uvlo-brownout/SOURCE.md)，blob `f37af0f42b32a99d886ebcb999ea667382921b21`。身份文件是 [SOURCE.json](SOURCE.json)。

本题按已批准的诊断修复 spec #136 建设。`source_id` 为 `046`，来源组 `v4-family-046`，历史路径 `benchmark/reference/v4/release/benchmarkv4-r53/tasks/1046-uvlo-brownout-detector-bugfix`。starter SHA256 `7c069d95792d498c3aa5093c3283441ac9debc262b16d13840f90f72ac4783d8`，healthy SHA256 `60fa91ebfedf02dc4f98eeb393c6cfce1b22db121159cedae22e3d300ef5d55e`。故障来自历史人工注错，原始工程故障形成过程未知。

已保留的合同：仅在 clk 上升沿更新；rst 高清零；out 低且 vin>0.65 V 置高，out 高且 vin<0.55 V 清零，两阈值之间及等号处保持；out 为 0/0.9 V，metric 对应 0.9/0.1 V；初态 out=0、metric=0.9 V；固定参数为源码默认值（`tr=100p`、`vth=0.45`）；终测覆盖两种不同激励；逻辑阈值 0.45 V；禁止条件也须满足按时启动要求。

同源关系：首批 v2-repair-uvlo-reset-chain（original-uvlo-chain-case0009）同属 UVLO 题材，但来源不同，责任是四模块电源链；本题是单模块时钟采样迟滞，不重复。R01 两题无同源；规划池 C395 为“保留组件或变体”，没有候选。

## 建模选择

`starter_kind` 按已有错误模型处理：`/app/circuit.va` 与历史 `environment/input/dut.va` 逐字节相同。参考解 `solution/circuit.va` 与 `solution/files/dut.va` 逐字节相同。公开自测入口是 `check.py`，公开用例取原私有 `tests/cases.json` 的第一个用例 `public-reproduction`；历史 `environment/input/public_test.scs` 不复制到 `/app/testbench`。

现行题面按已执行失败记 0、原因另记来写，并写明缺仿真器不是语义错误。

## 待定项

`grading` 和 `runtime` 待定。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，不证明当前 Harbor 包。SOURCE.json 的 `pending` 与旧 SOURCE“作者仿真校准已完成”不一致，本次不删其中任何一句。

checker 的电压容差 25 mV 与事件邻域 guard 0.15 ns 原合同没有写出。2026-10-28 修正（fix-a-r1，F03）按 checker 现值写入题面 Spec：每个保存点允许 25 mV；t=0 后最初 0.15 ns 不评分；每个 `clk` 上升交点前后 0.15 ns 内不评分，因此输出连同 `tr` 平滑须在 0.15 ns 内到达新电平。checker、激励与参考解未改。

开发证据（记录见文首本地目录）：阶段结果：EVAS 02dee32b 上参考解 2 个私有用例 a–c 完成且 checker 通过，公开台架 a–c 完成；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化；起始错误模型 3/3 个用例被判失败。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

fix-a-r1 复跑（2026-10-28，记录在本地 `runs/t3-batch2-20261027/fix-a-r1/`，不入库）：旧版 EVAS 0.8.7 上参考解私有 2/2、公开 1/1 仍通过，只用网格行复判无变化；理想阶跃探针确认题面所写 25 mV、0.15 ns 即 checker 实际尺度。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。

## author-r2 修正（2026-10-29）：门限的写法

依据：总协调 2026-10-29 对门限写法选甲（`runs/t3-spectre-wave2-20261029/scan/a-narrowed-exempt/README.md` 的“决定”一节，sha256 `769afc9e…160b`）；样板 `runs/t3-p0-pilot-20261027/TEMPLATE.md` r2.36（sha256 `377f1ecd…d048`）第 2 节“触碰门限”一条下的豁免三条；主控 brief `runs/t3-batch2-20261027/briefs/b2-author-r2.md` 第 5 项。记录在本地运行目录 `runs/t3-batch2-20261027/author-r2/`（不入库）。**未仿真**：本轮没有运行 Spectre、EVAS 或模型。

- 改了什么：题面 Spec 第 11 行在“Between the two thresholds, and at either threshold exactly, the state holds.”之后补两句：“The two thresholds are the binary64 (IEEE double-precision) values of the decimal numbers 0.65 and 0.55. This fixes their values, not their spelling: any way of writing them is acceptable if it gives exactly these values.” 只规定值，不规定语法。用例、checker、参考解与 starter 都不改。
- 为什么：`reentry-boundaries` 的 `vin` 按合同恰停在门限上，题面写明等号时保持，本题按样板的豁免条件不套用 A 收窄版。门限不是题面要求声明的参数（题面只要求保留 `tr`、`vth` 的缺省），所以要补这句话，豁免第 2 条才成立。
- DUT 把门限写成算式、算出的值与 0.65 或 0.55 的 binary64 不同，就算违约；答案仍是确定的，因为 Spectre 的 `<`、`>` 是精确比较（FU-01a，已核收）。差 1 ulp 的例子：`0.7 - 0.05`、`0.85 - 0.2`、`0.35 + 0.3` 都得 0.6499999999999999，比 0.65 小 1 ulp。拿它作置位门限时，`reentry-boundaries` 里 `vin` 恰为 0.65、`out` 为低的 4 拍（`clk` 上升交点 0.9995、1.9995、9.9995、10.9995 ns）都会置位，与合同“恰在门限上保持”相反，因此判不通过。常见写法 `vth + 0.2`、`0.9 - 0.25`、`1.3/2`、`650m` 都得 0.65，不受影响（Python 按 binary64 逐一核对）。
- 豁免三条的逐条核对，引用主控的核对记录 `runs/t3-spectre-wave2-20261029/scan/a-narrowed-exempt/README.md`（脚本 `check_exempt.py` sha256 `bad68c26…daf5d`，结果 `exempt-check.json` sha256 `f227d36c…2da1`）：
  1. 平台是平的 PWL 段，写成与门限相同的十进制数：`reentry-boundaries` 的 `vin` 平台写 `0.65`（0–2.599 ns、9.6–11.599 ns）与 `0.55`（4.6–6.599 ns），参考解字面量 `0.65`、`0.55` 与 checker 的 `.65`、`.55` 同值；没有“数值等于门限但写法不同”或“经非零参考节点才等于门限”的平台。满足。
  2. 题面以数值给出门限，参考解直接写字面量；DUT 一侧原先不满足（门限不是要声明的参数，可以写成算式），本轮补上面那句话后满足。
  3. 轮询时刻在平台内部：6 次轮询（0.65 平台 4 次、0.55 平台 2 次）离平台拐角至少 0.3995 ns，没有落在拐角上。满足。
  - 其余用例（`public-reproduction` 与公开用例）没有门限平台。
- 已核收的 Spectre 结果：B2PC must-01（执行身份 `spectre-B2PC-must-01-v1（结果包 sha256 fffd959be8465585…）`，2026-10-29 已核收）里，参考解在私有两例与公开用例都通过，缺省容差对照也都通过，起始模型三例都被拒，与期望相同；`reentry-boundaries` 的 6 次轮询前后，Spectre 的 `vin` 保存行逐位等于门限（带容差与缺省容差各一份）。
- Spectre 待办：本题不需要新的 Spectre 作业。
