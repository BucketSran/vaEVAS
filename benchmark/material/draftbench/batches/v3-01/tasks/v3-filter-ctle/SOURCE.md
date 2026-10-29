# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真，也没有把 verilogaLib 源码当成答案。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-ctle/instruction.md)，blob `f859f078a838a2b0054680186543ef6e9a91897f`，以及同字节的 [environment/public/contract.md](environment/public/contract.md)。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-ctle/SOURCE.md)，blob `69d79e7a9ee150a197209a86175e5d04e589e4a0`。提交时间 2026-10-15T13:29:47+08:00。

规格 #149 单元 C1，同源组 `verilogalib-ctle`。来源身份、许可和改编见 [路线来源](../../../../../../../experiments/benchmark_next/filter/SOURCES.md)。外部 CTLE 固定为 [Brian Li / verilogaLib ctle.va](https://github.com/ShabbyGayBar/verilogaLib/blob/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09/ctle.va)，该版本 MIT，2025 Brian Li。本轮未复制该源码。候选、公开合同和独立 checker 为本仓库原创重建。

已保留：`H(s)=gain*(1+s/(2π fz))/((1+s/(2π fp1))*(1+s/(2π fp2)))`；直流增益为 gain；`x1'=2π fp1*(u-x1)`，`x2'=2π fp2*(x1-x2)`，`y=gain*(x2+fp2/fz*(x1-x2))`；初态 ±0.1。范围 fz 500–2000 Hz，fp1 2000–8000 Hz，fp2 8000–24000 Hz，gain 0.5–2。迁移前壳的默认值 `fz=1000`、`fp1=4000`、`fp2=12000`、`gain=1`、`x1init=0`、`x2init=0` 写入 Spec。输出电压误差不超过 0.006 V。稳态复数频响误差不超过目标模长的 3%，目标模长不足 1 时绝对上限 0.03。验收 DC、多个频点和零初态以外的恢复。权重 1。允许等价内部实现。

公开 `contract.md` 与 `feedback.scs` 在 `/app/testbench/`。原 `public/dut.va` 是候选壳，现只在 `/app/circuit.va`，不留在 testbench。没有固定 DUT。

## 建模选择

新建连续模型。接口壳只留端口，参数由求解者按 Spec 声明。状态方程是行为合同，不是必须使用的变量名。后端固定 Spectre，不限制合法 Verilog-A 写法。

现行题面写已执行失败记 0、原因另记。历史题面只写自测不能代替终评，没有失败分数句。历史路线写 Spectre 扩展集，未证明 ngspice 复验。缺 Spectre 不是语义错误。

### 2026-10-28 补充（tolerance-r1）：用例网表写明容差与输出设置

D1 冻结前总协调定的第 (ii) 类题目修正：用例网表显式写出容差和输出设置。只改台架的容差和输出设置；激励、合同（`instruction.md`）、checker、参考解、候选、`v2_runtime.py` 与 `adc_linearity.py` 都不动。未仿真。

- 改了哪些行：`environment/public/feedback.scs`、`environment/starter/testbench/cases.json` 1 例、`environment/starter/testbench/feedback.scs`、`public/feedback.scs`、`tests/cases.json` 2 例，共 6 个网表。每个网表只改 options 与 tran 两条语句；激励、include、实例与 save 行逐字节不变。
  - 在 `tran` 语句前新加一行 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`。
  - `tran` 语句原来就写着 `errpreset=conservative`，不改；`stop`、`maxstep` 不改。
- 取值与来源：标准线 `D1-TOLERANCES.md`（sha256 `55fa799a…`）与 `D1-TOLERANCES.json`（`fbbbebbb…`）；写法按标准线网表约定清单 `LIST.md` 第 3 版（`6a6b17cd…`）。
  - reltol 1e-6、vabstol 1e-8 V、iabstol 1e-12 A，D1 的 12 题一样。本题 checker 的判据：y 对 checker 自行积分的 ODE 6 mV，复增益 3%·max(1, |H|)；标准线按局部截断误差估计，这组容差下的解算误差应远小于最严的判据；这只是选值的依据，不是已证明的全局误差上界，实际误差、事件时刻和耗时待 Spectre 校准验证（D1 容差复审 TOL-01）。iabstol 取 Spectre 缺省 1e-12，本题 save 的都是电压。
  - errpreset 沿用校准时的 `conservative`：Spectre 在瞬态里再把 reltol 乘 0.1，实际为 1e-7；EVAS 接受 errpreset 但忽略，按 1e-6。比共同要求更严是允许的。本题 12 ms、conservative，D1 运行时请记录运行时间。
  - 本题不用 strobe，不写 strobeoutput。
  - precision 不写进用例网表，由主控另排一轮放在 Spectre 执行路径里；`src_allbrkpts` 等批次 C。
- 历史身份：历史作者校准（filter 路线 `experiments/benchmark_next/filter/calibration.json`，2026-10-11 提交）登记的生成脚本 `build.py`（`d0a90b24…`）写出的网表，以及校准提交前 git 中的 `tests/cases.json`（`8c865727…`，`e1a147cf`），都只写了 `errpreset=conservative`，没有 reltol、vabstol、iabstol。当时实际生效的容差未知，可能是 Spectre 缺省，也可能是运行环境的设置。所以改后的结果与历史结果按不同的执行身份对待。本文件前面各段说的网表或公开 `.scs`“未改”“逐字节不变”，只指当时那一轮。
- 另记一条，本轮不处理：激励里 4 个 sine 源没写 sinedc。`LIST.md` 把 sinedc 列为“必须”，而且 sinephase 为 90 与 101.459° 这种情形正等批次 C 的 C05d/C05e。本轮按要求不改激励，已在记录里交主控。
- 旧版 EVAS 0.8.7 开发检查：参考解跑 2 个私有与 1 个公开用例，改前改后都在旧版的 rust_lowering 阶段失败，没有评分，首个诊断相同（`ERROR [rust_lowering]: source:u:missing_waveform_metadata`）。这是旧版的能力所限，与本轮改动无关。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v3-filter-ctle/`，D1 的对照作业从那里取原网表。改后 sha256：`environment/public/feedback.scs` `f675d825…`；`environment/starter/testbench/cases.json` `97f3d133…`；`environment/starter/testbench/feedback.scs` `418d63bf…`；`public/feedback.scs` `f675d825…`；`tests/cases.json` `7117f7e8…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 filter 路线记录中的历史身份，本次不运行模型实验。未正式录取或发布。开源复验资格未证明。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：无新的传递函数冲突。外部 verilogaLib 未声明 gain 的缺口仍只记在路线来源，不改本题已给出的 gain 范围和默认值 1。











## 2026-10-29 校准候选（first30-calib-r1）

首批 D1 只给本题参考解；本节补错误变体与正确替代，随 D2 出包。改了 `tests/calibration/`（新建 `mutants.py`、`expected.json`、`README.md`）与本页；参考解、checker（含公开副本）、用例、题面、starter 都没有改。未仿真，待 D2 Spectre 校准。

- 候选：错误 4 个（`hz_as_radians`、`zero_initval`、`corner_frequencies_hardcoded`、`zero_normalized_to_first_pole`），正确 1 个（`alt_difference_state`）；没有原 gold 套壳。
- 被拒矩阵摘要：
  - `hz_as_radians`：全部私有用例与公开用例应被拒；类别：单位错（Hz 当 rad/s，漏 2π）。
  - `zero_initval`：应在 `ctle-1` 被拒，其余应通过；类别：初态不读覆盖值（x1init、x2init 写死为 0）。
  - `corner_frequencies_hardcoded`：应在 `ctle-1` 被拒，其余应通过；类别：参数写死不读覆盖值（fz、fp1、fp2 固定为缺省）。
  - `zero_normalized_to_first_pole`：全部私有用例与公开用例应被拒；类别：零点归一化错（fp1/fz 代替 fp2/fz）。
  - `alt_difference_state`：全部私有与公开用例应通过；类别：正确替代（差分状态 d = x1 - x2）。
- 覆盖缺口（交主控，本轮不加用例）：
  - 参数只在 ctle-1 覆盖一次，合法域端点（fz 500/2000、fp1 2000/8000、fp2 8000/24000、gain 0.5/2、初态 ±0.1）都没有用例。 建议：加一个取端点的用例，例如 fz 2000、fp1 2000、fp2 24000、gain 0.5、x1init 0.1、x2init -0.1。
- F01：连续输出，逐点比较加稳态频响，没有事件后的评分起点。不适用。
- 样板 r2.18–r2.24 各条已逐条核对，结果写在 [校准 README](tests/calibration/README.md) 的同名一节；需要交主控的：无。
- 记忆污染：本题是 benchmark_next 新建题（规格 #149，同源组 verilogalib-ctle），不是 v4 迁移题；historyref 里的 v4 CTLE 题（329 自适应环、352 时钟化均衡器宏）端口与合同都不同，不作套壳候选。
- 旧版 EVAS 0.8.7 开发检查（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）：参考解与 5 个候选在旧版都报 `ERROR [rust_lowering]: source:u:missing_waveform_metadata`（sine 源），没有判决；预期依据合成控制（候选输出由 checker 自己的 RK4 积分器按候选系数推出），待 Spectre 核实。
- D1 交回的执行身份：私有包 `spectre-D1-private-v2（结果包 sha256 7ec4fbda83b6db84…）`（118 个作业），公开包 `spectre-D1-public-v2（结果包 sha256 87f515d69aa668a9…）`（29 个作业）。Spectre 线 2026-10-29 正式核收（suite v1.8 加 r8 两项未结 P1 的一次性核对，证据 clean）。核收报告是 `Spectre 线核收报告（私有）`（sha256 `66844d7b…`）与同目录的 `结果包（私有）`（`0701a701…`）；登记文件是 `runs/spectre-returns-20261028/accepted/REGISTER.json`（主控转达时 sha256 `3764e9af…`，之后又追加了别的批次，D1 两条不变）。合成控制读的是 `runs/t3-spectre-batchD-20261028/returns-preread-…/` 下解开的同一结果包，两个 tar.gz 的 sha256 与登记相同。
- 合成控制（未仿真）：D1 Spectre 21.1 交回（2026-10-29 已正式核收，执行身份见上）的参考解波形在内存中改写后由本题 checker 判定，判据控制与候选模型全部与预期一致，见 README。
- D2 估计：15 个作业，一般每个约 11.5 s，串行约 3 分钟，PSF 约 35.2 MB。
- 待办：D2 Spectre 校准（参考解应过，`wrong/` 按矩阵被拒，`correct/` 按矩阵通过）。
- 记录：first30-calib-r1 交付（`runs/t3-harbor30-20261027/first30-calib-r1/disposition.md`）。

## 2026-10-29 修正 r4（first30-fix-r4，第 (ii) 类）

总协调派的 first30-fix-r4 第 3 项：补 first30-calib-r1 交主控的合法域端点缺口。只加用例，现有两例、候选、checker、参考解与题面都不改。未仿真，待 Spectre 复跑。

- 改了什么：`tests/cases.json` 加 `ctle-endpoints`：参数 fz 2000、fp1 2000、fp2 24000、gain 0.5、x1init 0.1、x2init -0.1，实例行写 `fz=2000 fp1=2000 fp2=24000 gain=0.5 x1init=0.1 x2init=-0.1`；u = `Vdc dc=0.04` 加 500 Hz、2/8/16 kHz 四个 `sinedc=0 ampl=0.035` 的 sine 源；容差与 tran 同现有用例（`reltol=1e-6 vabstol=1e-8 iabstol=1e-12`；`stop=0.012 maxstep=1e-06 errpreset=conservative`）。`tests/calibration/expected.json` 与 `README.md` 同步（见 README 末节）。
- 为什么：参数只在 ctle-1 覆盖一次，合法域端点都没有用例。新用例取 fz 上端、fp1 下端、fp2 上端、gain 下端、初态两端。fz = fp1 时 H(s) 里零点与第一极点相消，但初态合同里 x1 仍按 fp1 从 x1init 恢复，时域响应不是单极点滤波。
- 合法域写法核对：题面写“Their legal ranges are 500–2000, 2000–8000, and 8000–24000. `gain` is 0.5–2.”与“each lies in ±0.1”，没有写明是否含端点；按惯常读法含端点。参考解 `parameter real fz=1000, …` 不声明 `from`，端点合法。用例的端点写法与题面相同（2000、24000、0.5、0.1、-0.1）。要不要在题面写明“含端点”，交主控（本轮不改题面）。
- 余量依据：checker 的判据是逐行 6 mV 与稳态各频点 0.03·max(1,|H|)；新用例没有事件、没有门限，不涉及网格余量。各错误候选的误差由合成控制给出（见 README）。
- 第 5 项核对（样板 r2.29–r2.35，LIST 第 4.10 版）：
  - 没有 transition、cross、timer，零边沿、td、回零根、一次性 timer 都不适用。
  - idt：参考解与候选的 `idt(…, x1init/x2init)` 只有初值，没有 assert 复位，“idt 复位不只在 t = 0”不适用。
  - 最后一行与 stop：checker 用全部行积分、用 stop/2 之后的行求相量，不要求最后一行恰为 stop。
  - 网表第 0.5 节：新网表用 `list41_scan.py`（92d7cea1…）扫描无命中；sine 源写明 sinedc、ampl、freq（LIST 的“必须”项）；errpreset=conservative；数字写法没有指数加比例。
  - 第 20 条：checker 只有 6 mV 与 3% 的误差判据，没有判“变了没有、是否为零、是否相等”的门限。无。
  - 第 21 条：checker 不读日志记录。无。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：参考解与 5 个候选在新用例上都报 `missing_waveform_metadata`（sine 源），没有判决；期望依据合成控制，待 Spectre 核实。
- Spectre 补跑：7 个作业，PSF 约 15.9 MB，单个最大约 2.49 MB，串行约 1 分钟；清单 `runs/t3-harbor30-20261027/first30-fix-r4/spectre-jobs/`。
- 改前原文件逐字节存于 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v3-filter-ctle/`。改前 → 改后 sha256：`tests/cases.json` `7117f7e8…` → `d8e268c6…`；`tests/calibration/expected.json` `c1fafa94…` → `f64d0c9f…`；`tests/calibration/README.md` `28c8acb9…` → `577015f1…`；本页改后的 sha256 记在交付记录里。
- 记录：first30-fix-r4 交付（`runs/t3-harbor30-20261027/first30-fix-r4/disposition.md`）。
