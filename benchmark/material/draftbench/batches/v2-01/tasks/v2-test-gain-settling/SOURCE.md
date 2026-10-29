# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真，也没有用公开网表里的实例覆盖值改写题面已写的 2.5 增益合同。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-gain-settling/instruction.md)，blob `8402411258ed26a67978b5c8fa373fcf9893eba8`。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-gain-settling/SOURCE.md)，blob `c98a163388d83ff1c14f96e571db7ed4c9316441`。提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。来源组 `case-0018+v4-038+v4-370`。原始参考资产仍在 `benchmark/material/historyref/`。

已保留的测量合同：首个 launch 前报告为 0；launch 上升捕获输入和静态输出基线并清报告；其后每 250 ps 采样动态输出 80 次，窗口 20 ns；第二轮重新捕获；`abs(span)<=0.02 V+1 pV` 无效；无效时 `status=2` 且其余报告 0；否则 `gain=实际静态输出变化/实际输入变化` 且 `gain_valid=1`；81 个动态样本含基线，最后一个大于 2 mV 的样本之后的第一个样本是 `settling_ns`，完全无超差为 0；末 8 个样本都在 2 mV 内才 `settled=1`、`status=1`，否则 `settled=0`、`status=3`、`settling_ns=0`，仍报告实际静态 gain；收集中 `status=0`。`tr=20 ps`，guard 80 ps，gain 误差 0.02，建立时间 0.03 ns，其余 3 mV。静态增益合同固定 2.5。动态 alpha 0.01..0.35。vin 基线与阶跃 0.42..0.49 V。每轮 launch 后 200..240 ps 内完成输入阶跃。各轮至少相隔 25 ns。

仪表参数默认值来自迁移前 starter：`sample_period=250p`、`min_input_span=0.02`、`settle_tol=0.002`、`tr=20p`、`samples=80`、`tail_samples=8`。固定文件在 `/app/testbench/dut/static_amp.va` 与 `dynamic_amp.va`。公开用例在 `/app/testbench/cases.json`。

## 建模选择

两个放大器并联观察同一输入，不是级联。候选只测量，不读内部 settled 标志，也不读 DUT 参数。接口壳只留端口。不达标动态响应可以被正确仪表测量并通过。只证明公开有限窗口。

现行题面写已执行失败记 0、原因另记。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该原义保留。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：原题面只有 “The timing guard is 80 ps.”，没有说明 guard 覆盖事件之前、整段不评分与区间中点；本次保留该句，在其后加一段：“The timing guard applies around these events: every rising crossing of `launch` through 0.5 V, and the end of each window, 80 sample periods of 250 ps (20 ns) after its `launch` crossing. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.”
  - 2026-10-28 主控更正说现行题面已写明这些规则（第 11 行或第 15 行一段）；核对 `HEAD` 与本轮改前副本（`orig/`），那一段是本轮新加的文字，不是迁移时已有的。按更正逐句核对时，把区间规则改写成“事件与瞬态起止划分区间”：先前的写法没有把 t = 0 与瞬态终点当作区间端点，首尾两段的整段跳过和中点规则说得不全。改写后各句与 `pieces()` 和本题事件表一致，之后不再改题面。
  - 对应 checker：`tests/v2_testing.py:58-74` 的 `pieces()`：guard 取用例的 80 ps（`:61`），不长于 `2*guard` 的区间整段跳过（`:64`），其余区间取 `(t+guard, end-guard)` 内的保存点加区间中点（`:66-67`），首尾以 t = 0 与瞬态终点为界；事件表见 `tests/v2_testing.py:299-332`（`:303` 的 `launch` 穿越用 `Wave.edges` 默认门限 0.5 V（`:20`），`:307` 窗口终点，`:312`、`:327` 两类状态）。
  - `launch` 的 0.5 V 门限原题面没有写，参考解也用 0.5 V；本次写进事件表，与 checker 一致。brief 提到本题“还有其他用 guard 的地方”，逐行核对 `settling()`（`tests/v2_testing.py:299-332`）只有 `pieces()` 用 guard，没有别的 guard 用法；样本时刻按 `launch` 穿越加 `j*250 ps` 精确插值，不带容差。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_report_delay_100ps`；应通过（窗内对照）：`inwindow_report_delay_50ps`。
  - 合成控制（未仿真）：底波形为标量状态探针的旧版波形，在内存中提前或推迟报告列后直接调用本题 checker。`late-report-+100ps` 3 个私有用例都被拒；`inwindow-report-+50ps` 3 个私有用例都通过；`early-report--100ps` 3 个私有用例都被拒；`inwindow-early-report--50ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 15/15 符合预期。
  - 旧版 EVAS 0.8.7：参考解与由它派生的两个候选在旧版上都跑不了：参考解用状态数组，旧版在降级阶段报 `dynamic_state_array_access`。实跑确认：候选 6/6 例、参考解抽查 2 例都是 simulation_failed，参考解结论与 first30-r1 一致。所以 `expected.json` 的条目待 Spectre 复跑，不算已验证。另做的标量状态探针（只把数组拆成标量、下标写改成平铺的 if，单独记账，不是校准候选）在全部 6 个私有与公开用例通过；按同样延迟改法派生的探针变体 `late_report_delay_100ps` 3/3 被拒，`inwindow_report_delay_50ps` 3/3 通过。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

### 2026-10-28 补充（first30-fix-r1）：恰好 160 ps 的区间

`pieces()` 用浮点比较判断区间是否不长于 `2*guard`（`tests/v2_testing.py:64`，`end-t<=2*guard`）。名义上恰好 160 ps 的区间相减后可能长出几个 ulp，于是不整段跳过，区间中点被评分；这与第二批 online-gain 审核 AR08 是同一类问题。checker 不动；题面合法输入域（第 19 行）加一句 “In every case, public and final, no interval is exactly 160 ps long.”。

核验（未仿真）：对 3 个私有与 3 个公开用例，各取网表与支撑文件都和现行用例（rewrite-r2a 之后）相同的旧版波形，在内存中记录 checker 交给 `pieces()` 的状态表。参考解在旧版上跑不了，波形取 rewrite-r2a 的标量状态探针运行；事件只由 `launch` 激励与窗口终点决定，与被测报告无关。没有区间落在 160 ps ± 1 fs 内，也没有不长于 160 ps 的区间；最短区间是 t = 0 到第一次 `launch` 穿越：私有 3010 ps、公开 2010 ps。脚本与结果：`runs/t3-harbor30-20261027/first30-fix-r1/scripts/measure_intervals.py`、`measure/intervals.json`。波形是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 2 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2a：NF-03、NF-06（NF06-30-1、NF03-30-1）
- rewrite-r2a：NF-22（NF22-30-1-alt1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2a/orig/v2-test-gain-settling/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `environment/public/cases.json` | `57660f4e7594b1d6bf89c8a7dc920ad9c8bf0524ee0eb6a047274bb6322774fe` | `5ee54d2a1e71d8ddfd03474e09172c39bae055bcc86f4b6d27ed52dad247bd31` |
| `environment/public/dut/static_amp.va` | `c7a056eefc8912d06952ec428fffbe6f21c3d63fc48ee014a1da30d1b2a0358f` | `19f89f91658be46809f3cee8fa247a0ab17bf3585816420481ad91542a810055` |
| `environment/starter/testbench/cases.json` | `57660f4e7594b1d6bf89c8a7dc920ad9c8bf0524ee0eb6a047274bb6322774fe` | `5ee54d2a1e71d8ddfd03474e09172c39bae055bcc86f4b6d27ed52dad247bd31` |
| `environment/starter/testbench/dut/static_amp.va` | `c7a056eefc8912d06952ec428fffbe6f21c3d63fc48ee014a1da30d1b2a0358f` | `19f89f91658be46809f3cee8fa247a0ab17bf3585816420481ad91542a810055` |
| `solution/circuit.va` | `ab68e82bebca413f64c05262fcf4fa56fcb9877ef381ac305b5e2db92afa6c55` | `cd0d49a2f1a0eed923eff8deb9ea5058c09d92107496a4692d247534a1e00552` |
| `solution/dut.va` | `ab68e82bebca413f64c05262fcf4fa56fcb9877ef381ac305b5e2db92afa6c55` | `cd0d49a2f1a0eed923eff8deb9ea5058c09d92107496a4692d247534a1e00552` |
| `tests/cases.json` | `49d76c1847fa27621a6b8a929af76acc527215bbc06aa815b7d7500035117020` | `4c628bbbf6c14021cbef66d11015fee400ba8c77c41007d25a7dad534f362845` |

- 本文件删去了改写写进来的一节“改写（#270 NF-03 / NF-06 / NF-22），待 Spectre 新旧对照”（含其中的状态行与主控在审核后补记的规范依据），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-test-gain-settling/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 18 组（用例、候选）两版判决全部相同（12 组都通过、6 组都被拒）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 `runs/t3-spectre-batchD-20261028/preread-sui01-d2/PREREAD.md` 第 3 节与同目录 `decision1.json`。
- 退回后的 7 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/30-v2-test-gain-settling/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- 固定放大器 `programmable_gain_amplifier`（`static_amp.va` 的 2 份文件与 3 个 `cases.json` 内嵌的 9 份）回到原写法，对所有候选生效。
- 上面 first30-fix-r1 一节的核验用的是 rewrite-r2a 之后的用例与标量状态探针波形。区间事件只由 `launch` 激励与窗口终点决定，固定放大器的谓词写法在合同域内取值相同（rewrite-r2a 的推导），所以那一节的结论不受影响（推断，本轮未重测）。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。不证明当前 Harbor 包。模型试跑尚未完成。开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

实例参数核对：静态源码默认 `gain_low=0.8`、`gain_high=2.4`，而题面写静态增益固定 2.5，公开 `cases.json` 网表把该实例设成 `gain_low=2.5 gain_high=2.5`。动态源码默认 `alpha=0.3`、`tick=250 ps`、`tr=200 ps`，公开网表另出现 `alpha=0.3` 或 `0.01`，以及 `tick=50p tr=100p`。题面公开范围只写 alpha、vin 和阶跃时刻，没有把 `tick`/`tr` 列成可扫描合同。本次不把网表覆盖值升格成新的科学范围，也不改 2.5 这句已定条件。

主控核对：三个公开case均显式实例化 `gain_low=2.5 gain_high=2.5`，与静态增益合同一致；库默认0.8/2.4不构成该实例的合同冲突。动态实例的tick/tr也为公开台架中明确的覆盖值，不由此推导新扫描范围。独立运行与checker校准仍待定。
