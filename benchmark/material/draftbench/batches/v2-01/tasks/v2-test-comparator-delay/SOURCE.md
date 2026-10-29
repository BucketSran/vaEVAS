# 来源与迁移记录

2026-10-27 迁成首批 Harbor 本地包。用户当天决定首批 30 题优先选不需要 SPICE 网表的纯 Verilog-A 题。本题据此替换 `v2-test-por-sequence`，进入首批 slot 29。POR 题包保留为 SPICE 路线后备，未改。本次只改题面、本页和打包文件。评分数值代码、公开与私有用例、参考解行为和支持 DUT 未改。阶段保持 implementation。没有仿真。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-comparator-delay/instruction.md)，blob `adf74b913939e8a9dbd71df3adafb03d8ea4e343`。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-comparator-delay/SOURCE.md)，blob `c64524f4c3f96af90df9d49421ad305e765fc602`。提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。

来源 `v4-170`。本题保留来源工程目标，并保留后来加上的固定只读 DUT、独立实际波形 checker 和明确窗口协议。原始参考资产仍在 `benchmark/material/historyref/`。固定 DUT 现为 `/app/testbench/dut/support_cmp.va`，模块 `support_overdrive_delay_comparator`。公开用例现为 `/app/testbench/cases.json`。候选壳现为 `/app/circuit.va`，只留端口；参数默认值改写在题面。

已保留：模块 `delay_meter(vdd,vss,clk,vinp,vinn,outp,outn,delay_ps,overdrive_mv,polarity,valid)`，端口顺序不变；供电固定 0.9 V 和 0 V；逻辑检测门限 0.45 V；valid 和 polarity 按 0.9 V 逻辑；首个 clk 上升沿前 delay_ps、overdrive_mv、polarity、valid 均为 0；valid 为 0 时数值报告仍按合同初始化或保持；每次 clk 上升沿重新武装并清 valid；overdrive_mv 为该时刻输入差绝对值乘 1000；武装后 outp 或 outn 的首个上升沿把与 clk 的实际间隔乘 1e12 锁存到 delay_ps，polarity 分别为 0.9 V 或 0 V，valid 为 0.9 V；缺决策不能沿用旧 valid；未武装的边沿忽略；重新武装保留上一数值直到新决策；`tr=20 ps`；guard 80 ps；延迟误差 0.7 ps，过驱动 0.2 mV，逻辑 0.002 V。公开自测与终评范围：差分过驱动绝对值 0.001..0.08 V，输入共模 0.45 V；时钟周期 5..7 ns；每轮输入在 launch 前至少 200 ps 稳定；实际响应不超过 1 ns；DUT 可变传播延迟参数，或在任意后续轮缺少决策；供电与单位不变。另保留：不得驱动观测输入；固定 DUT 只读；测量不达标 DUT 时，报告正确结果仍可通过；固定后端 Spectre，语法遵循该后端的 Verilog-A；源码按原字节运行；终评在提交后使用合同范围内不同的参数、事件及故障实例；终评台架和 checker 不进入解题材料；判定目标与数值容差以公开合同为准。参数默认值 `tr=20p` 来自迁移前 starter。支持比较器源码默认 `td_0=24p`、`tau=5p`、`td_min=25p`、`td_max=140p`、`tr=20p`。

## 建模选择

这是测试表征，不是重建比较器。仪表接口壳只留端口，原 starter 的参数和内部变量不进壳。`tr=20 ps` 由求解者按 Spec 声明。端口方向取自迁移前 starter 的 `input`/`output` 声明：`vdd`、`vss`、`clk`、`vinp`、`vinn`、`outp`、`outn` 为输入，题面照样板写成只读观测输入；其余四个为输出。满足外部测量行为即可。不得驱动观测输入。DUT 不达标时，正确报告仍然可以通过。题面只点名固定 DUT 的模块与文件，不复述其源码默认值，所以题面合同数值与迁移前一致。

现行题面按已执行失败记 0、原因另记书写。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该历史原义保留在本页，不解释成缺 Spectre 等于语义错误，也不把现行 0 分解释成行为已被检出。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：原题面只有 “The timing guard is 80 ps.”，没有说明 guard 覆盖事件之前、整段不评分与区间中点；本次保留该句，在其后加一段：“The timing guard applies around these events: every rising crossing of `clk`, `outp`, or `outn` through 0.45 V, whether or not the meter is armed or the report changes there. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.”
  - 2026-10-28 主控更正说现行题面已写明这些规则（第 11 行或第 15 行一段）；核对 `HEAD` 与本轮改前副本（`orig/`），那一段是本轮新加的文字，不是迁移时已有的。按更正逐句核对时，把区间规则改写成“事件与瞬态起止划分区间”：先前的写法没有把 t = 0 与瞬态终点当作区间端点，首尾两段的整段跳过和中点规则说得不全。改写后各句与 `pieces()` 和本题事件表一致，之后不再改题面。
  - 对应 checker：`tests/v2_testing.py:58-74` 的 `pieces()`：guard 取用例的 80 ps（`:61`），不长于 `2*guard` 的区间整段跳过（`:64`），其余区间取 `(t+guard, end-guard)` 内的保存点加区间中点（`:66-67`），首尾以 t = 0 与瞬态终点为界；事件表见 `tests/v2_testing.py:77-96`（`:80-82` 取三类上升穿越，门限取用例的 0.45 V；`:95` 每个事件都加一段状态，未武装的边沿也加）。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_report_delay_100ps`；应通过（窗内对照）：`inwindow_report_delay_50ps`。
  - 合成控制（未仿真）：底波形为旧版 first30-r1 的参考波形，在内存中提前或推迟报告列后直接调用本题 checker。`late-report-+100ps` 3 个私有用例都被拒；`inwindow-report-+50ps` 3 个私有用例都通过；`early-report--100ps` 3 个私有用例都被拒；`inwindow-early-report--50ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 15/15 符合预期。
  - 旧版 EVAS 0.8.7：`late_report_delay_100ps` 3 个私有用例都被拒；`inwindow_report_delay_50ps` 3 个私有用例都通过。共 6/6 符合 `expected.json`。参考解抽查 2 例（private/terminal-normal、public/normal）都与 first30-r1 一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 3 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2a：#270 第4项（R09-1）
- rewrite-r2a：NF-09（NF09-29-1r）
- rewrite-r2b：NF-10（NF10-29-1-alt2）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2a/orig/v2-test-comparator-delay/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `environment/public/cases.json` | `0e439ee4c5808a869b5ea0f9a15d13d4247375c7baa39d4f037ca3929e8242d1` | `ec6d85ee8746909420e1cbf8d86954070a31e7791a69f61fadea2c186ae6968b` |
| `environment/public/dut/support_cmp.va` | `da47200e6f858dfd66574cc0ba2a30636ad8180a4d594baeb9f86c9dfefeb49a` | `8248b3a926f0b351041b3c63b74d4ec4822aafcf6d9f45c224f37e21626bcbf5` |
| `environment/starter/testbench/cases.json` | `0e439ee4c5808a869b5ea0f9a15d13d4247375c7baa39d4f037ca3929e8242d1` | `ec6d85ee8746909420e1cbf8d86954070a31e7791a69f61fadea2c186ae6968b` |
| `environment/starter/testbench/dut/support_cmp.va` | `da47200e6f858dfd66574cc0ba2a30636ad8180a4d594baeb9f86c9dfefeb49a` | `8248b3a926f0b351041b3c63b74d4ec4822aafcf6d9f45c224f37e21626bcbf5` |
| `solution/circuit.va` | `028fa39924d9c1b50f24f0d8911edfe3fe44a965f29eb87365104a9f10db53af` | `775ffd0416ef0a9fa42cb384f34c4379ec6f0972b13c47682713f736438bfaca` |
| `solution/dut.va` | `028fa39924d9c1b50f24f0d8911edfe3fe44a965f29eb87365104a9f10db53af` | `775ffd0416ef0a9fa42cb384f34c4379ec6f0972b13c47682713f736438bfaca` |
| `tests/cases.json` | `b04befc7b379e408c57643a17dd86358bb9dae9ca6523fe72df3130b5820478d` | `366c07f69266aa1e825c8dd8d728c7f6f9e1953d47927004f78f8e1ce2c44134` |

- 本文件删去了改写写进来的两节“改写（#270 第4项 / NF-09），待 Spectre 新旧对照”、“改写（#270 NF-10），待 Spectre 新旧对照”（含其中的状态行与主控在审核后补记的规范依据），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-test-comparator-delay/SOURCE.md`；那两节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 18 组（用例、候选）两版判决全部相同（12 组都通过、6 组都被拒）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 Benchmark 的 D2 预读记录（本地 runs/ 下，未公开）第 3 节与同目录的 decision1.json。
- 退回后的 7 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/29-v2-test-comparator-delay/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- 本题有 rewrite-r2a（第4项 R09-1、NF-09 NF09-29-1r）与 rewrite-r2b（NF-10 NF10-29-1-alt2）两组。代码文件按 revert_notes 从 rewrite-r2a/orig 取（rewrite-r2b/orig 是 r2a 改后的状态）。参考解两文件只含 r2a 的行，第一步退回；固定比较器 2 份与 3 个 `cases.json`（内嵌 9 份）叠着两组的改动，原件早于两组，单退 r2a 做不到逐字节，所以第二步与 r2b 一起退回。
- 删去两节改写记录；“区间边界”一节保留，它的核验已含改写前的字节。

## 区间边界（主控 2026-10-28，随 first30-fix-r1 的附带核验）

`pieces()` 用浮点比较判断区间是否不长于 `2*guard`（`tests/v2_testing.py:64`）。名义上恰好 160 ps 的区间相减后可能长出几个 ulp，于是不整段跳过，区间中点被评分；这与第二批 online-gain 审核 AR08 是同一类问题。first30-fix-r1 核验本题全部用例（含改写前的字节）没有恰好 160 ps 的区间，最近的见 runs/t3-harbor30-20261027/first30-fix-r1/disposition.json。checker 不动；题面合法输入域（第 15 行）加一句 “In every case, public and final, no interval is exactly 160 ps long.”，与其余三道测量题相同。这句只改 instruction.md，不涉及在审的改写文件。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。测试表征索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。这些记录不证明当前 Harbor 包。历史来源与旧运行仍保留原版本。当前 Harbor 包的模型试跑尚未完成。目录存在不表示发布资格。固定 Spectre，开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

原文以下几处没有写死。题面照原义直译，本次不裁决：

- `launch` 一词原文未定义，题面保留原词。公开支持比较器在 clk 上升沿采样输入（`environment/public/dut/support_cmp.va:29`）。固定 checker 把 clk 上升沿记为 launch 事件（`tests/v2_testing.py:80`）。
- “重新武装保留上一数值直到新决策”没有逐项点名“上一数值”。同段已写 clk 上升沿清 valid，并按该时刻更新 overdrive_mv。固定 checker 在 clk 上升沿只改 overdrive_mv 与 valid，delay_ps 与 polarity 保持到新决策（`tests/v2_testing.py:88-93`）。
- “实际响应不超过1ns”没有写明起止点。

边沿测量电平已由原题面确定：clk、outp、outn 的上升沿按逻辑检测门限 0.45 V 判定，“与clk的实际间隔”取这两次穿越之差。固定 checker 按用例 `threshold=0.45` 取上升穿越（`tests/v2_testing.py:78-82`），六个原用例均为 0.45。

未决：未发现题面数值与固定 checker 冲突。公开 `dut/support_cmp.va` 是正常比较器。公开 `missing-final-decision` 用例内联的同名支持文件另加 `$abstime < 24n` 门控。这是来源已有的缺决策故障实例，checker 按用例记录写入支持文件。本次不动。

## 2026-10-29 核对：固定比较器在 clk 下降沿把 out_delay 改回 0（first30-fix-r5 第 3 项，M9）

- 写法：固定比较器 `support_cmp.va`（`environment/public/dut/`、`environment/starter/testbench/dut/` 两份文件，与三份 `cases.json` 里内嵌的 9 份副本）第 53 行在 clk 下降沿把 `out_delay` 改回 0。对输出本来就是 0 的那一路，这是“输入不变、只把 td 改成 0”。
  - 这与 U15 同类：Spectre 21.1 在 U15 上删掉了全部待发沿（预读）；LRM 2023 第 4.5.8 节的澄清是保留；2.4 没有规定（标准线判读（本地记录），sha256 `d968fb4ee720f7ac55e89567b1abd770e2a18fc113b0783eb3e5ee2d85e0dd1e`）。
- 核对（精确有理数重放比较器的事件逻辑，`runs/t3-harbor30-20261027/first30-fix-r5/scripts/slot29_pending.py` → `runs/t3-harbor30-20261027/first30-fix-r5/slot29/pending-check.json`）：
  - 6 个用例（私有 3、公开 3；starter 的 `cases.json` 与公开的相同）共有 64 次“值不变、td 改变”的写入，其中把 td 改成 0 的 32 次。
  - 每一次都没有按非零延迟排着、还没开始的过渡，也没有正在进行的过渡。保留、删除两种读法下，outp、outn 逐沿相同。
  - 原因是结构上的：非零延迟的过渡只在 clk 上升沿出现，把被选中的那一路从 0 改成 1；随后的下降沿把这一路从 1 改回 0，这是真正的输入变化，两种读法都会删掉排在它后面的沿；没被选中的那一路从来没有排着的沿。各用例的延迟沿在 clk 下降前至少 2.225 ns 就已走完。
  - 校准候选（`inwindow_report_delay_50ps`、`late_report_delay_100ps`）与参考解的 `transition()` 延迟都是常量，没有运行中改 td 的写法。
- Spectre 21.1（D2，2026-10-29 已正式核收；四包 D2-must-public、private-a、private-b、alt 的执行身份记在私有记录 first30-fix-r5 的 slot29/SOURCE-draft.md）：
  - 参考解、缺省容差对照与两个校准候选，原件与改写版比较器，共 42 个作业。每个作业的输入与 run.json 记的哈希相同，比较器副本与对应版本相同。
  - outp、outn 的 0.45 V 穿越与预测（沿起点加 tr/2）逐沿相同，最大偏差 0.015 ps（缺省容差作业；带容差的作业 1.5e-5 ps）。
  - 在这些用例上两种读法给出同一波形，Spectre 的结果与之一致，分不出 Spectre 取哪一种；改写版（timer 加零延迟 transition，没有 td 变化）的波形也相同。
- 结论：评分不依赖待发沿的去留，记“已核对”；不属决定单第 24 项。
