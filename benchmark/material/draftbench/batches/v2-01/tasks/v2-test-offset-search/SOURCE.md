# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真，也没有改比较器参考或 C109 vref 一类未决选择；本题公开合同里没有 vref 字段。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-offset-search/instruction.md)，blob `ce0bc3916428d10c05a75e0fe4c599f2c430caaf`，提交时间 2026-10-15T13:29:47+08:00。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-offset-search/SOURCE.md)，blob `122fe49946ba295aed31f5924602cba7931877df`。

来源 `v4-109`。本题保留来源工程目标，并保留后来加上的只读 DUT、独立波形 checker 和窗口协议。原始参考资产仍在 `benchmark/material/historyref/`。固定 DUT 现为 `/app/testbench/dut/comparator.va`。公开用例现为 `/app/testbench/cases.json`。候选壳现为 `/app/circuit.va`，只留端口；参数默认值改写在题面。

已保留：估计初值 0；差分输入等于估计且围绕 0.5 V 对称；1 ns 发首个 request；只在 ready 上升更新；`dcmpp>0.5 V` 则减步长，否则加步长；初始步长 0.064 V，每次减半，共 7 次；响应后立即拉低 request，`gap=1 ns`；最后一次 `valid=1`、`status=1`；超时 10 ns 则 `status=2`、`valid=0`；`status=0` 为运行中；逻辑高 1 V；时序允许 80 ps，电压 1.5 mV；范围 ±0.127 V，区间外为公开未覆盖。DUT offset -0.06..0.06 V，响应延迟 150..700 ps，ready 脉宽 400 ps，可在任意已完成响应后停止。参数默认值 `step_initial=0.064`、`iterations=7`、`gap=1n`、`timeout=10n`、`tr=20p`。比较器源码默认 `offset=0.023`、`td=200p`、`tr=20p`、`drop_after=99`。

## 建模选择

这是测试表征，不是重建比较器。仪表接口壳只留端口，参数由求解者按 Spec 声明。满足外部搜索行为即可。不得驱动观测输入。DUT 不达标时，正确报告仍然可以通过。

现行题面按已执行失败记 0、原因另记书写。历史题面原句是“工具链故障单独诊断，不作为候选零分”。该历史原义保留在本页，不解释成缺 Spectre 等于语义错误，也不把现行 0 分解释成行为已被检出。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照，测量题另加提前负例。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：原题面只有 “The timing allowance is 80 ps and the voltage tolerance is 1.5 mV.”，没有说明 guard 覆盖事件之前、整段不评分与区间中点；本次保留该句，在其后加一段：“The first rising `request` crossing of 0.5 V must lie within 80 ps of 1.01 ns, where an edge that starts at 1 ns with the default 20 ps transition crosses. A response is the first rising `ready` crossing of 0.5 V after a rising `request` crossing and before the next one. Each later rising `request` crossing must lie within 80 ps of the preceding response plus `gap`. The timeout is counted from the rising `request` crossing. All six outputs, including `request`, `vinp`, and `vinn`, are scored as reports. The timing allowance also applies around these events: every rising `request` crossing, every response, and every timeout instant. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.”
  - 2026-10-28 主控更正说现行题面已写明这些规则（第 11 行或第 15 行一段）；核对 `HEAD` 与本轮改前副本（`orig/`），那一段是本轮新加的文字，不是迁移时已有的。按更正逐句核对时，把区间规则改写成“事件与瞬态起止划分区间”：先前的写法没有把 t = 0 与瞬态终点当作区间端点，首尾两段的整段跳过和中点规则说得不全。改写后各句与 `pieces()` 和本题事件表一致，之后不再改题面。
  - 对应 checker：`tests/v2_testing.py:58-74` 的 `pieces()`：guard 取用例的 80 ps（`:61`），不长于 `2*guard` 的区间整段跳过（`:64`），其余区间取 `(t+guard, end-guard)` 内的保存点加区间中点（`:66-67`），首尾以 t = 0 与瞬态终点为界；事件表见 `tests/v2_testing.py:208-260`（`:209-210` 的 `request`、`ready` 穿越用默认门限 0.5 V，`:226` 请求、`:234` 超时、`:248` 响应三类状态，`:229` 超时从请求穿越算起）；请求时刻的另两处 guard：`:216` 首个请求离 `first_request`（用例 1.01 ns）超过 80 ps 记 `initial_request`，`:252` 后续请求离响应加 `gap` 超过 80 ps 记 `request_not_response_driven`。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_testing.py` 与公开副本 `environment/starter/testbench/v2_testing.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改报告延迟、`request` 延迟或请求时刻。应被拒：`late_report_delay_100ps`、`late_request_delay_100ps`、`early_request_100ps`；应通过（窗内对照）：`inwindow_report_delay_50ps`、`inwindow_request_delay_50ps`、`inwindow_early_request_50ps`。
  - 合成控制（未仿真）：底波形为旧版 first30-r1 的参考波形，在内存中提前或推迟报告列，另单独平移 `request` 列后直接调用本题 checker。`late-report-+100ps` 3 个私有用例都被拒；`inwindow-report-+50ps` 3 个私有用例都通过；`early-report--100ps` 3 个私有用例都被拒；`inwindow-early-report--50ps` 3 个私有用例都通过；`late-request-+100ps` 3 个私有用例都被拒；`inwindow-request-+50ps` 3 个私有用例都通过；`early-request--100ps` 3 个私有用例都被拒；`inwindow-early-request--50ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 27/27 符合预期。
  - 旧版 EVAS 0.8.7：`early_request_100ps` 3 个私有用例都被拒；`late_report_delay_100ps` 3 个私有用例都被拒；`late_request_delay_100ps` 3 个私有用例都被拒；`inwindow_early_request_50ps` 3 个私有用例都通过；`inwindow_report_delay_50ps` 3 个私有用例都通过；`inwindow_request_delay_50ps` 3 个私有用例都通过。共 18/18 符合 `expected.json`。参考解抽查 2 例（private/terminal-normal-positive、public/normal-positive）都与 first30-r1 一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

### 2026-10-28 补充（first30-fix-r1）：恰好 160 ps 的区间

`pieces()` 用浮点比较判断区间是否不长于 `2*guard`（`tests/v2_testing.py:64`，`end-t<=2*guard`）。名义上恰好 160 ps 的区间相减后可能长出几个 ulp，于是不整段跳过，区间中点被评分；这与第二批 online-gain 审核 AR08 是同一类问题。checker 不动；题面合法输入域（第 17 行）加一句 “In every case, public and final, no interval is exactly 160 ps long.”。

核验（未仿真）：对 3 个私有与 3 个公开用例，各取网表与支撑文件都和现行用例（NF-12a 之后）相同的旧版参考波形，在内存中记录 checker 交给 `pieces()` 的状态表。没有区间落在 160 ps ± 1 fs 内，也没有不长于 160 ps 的区间；最短区间是请求穿越到响应：公开 `normal-positive`、`response-timeout` 为 210 ps（1.01–1.22 ns），私有用例为 360 ps 或 460 ps，公开 `normal-negative` 为 610 ps。脚本与结果：`runs/t3-harbor30-20261027/first30-fix-r1/scripts/measure_intervals.py`、`measure/intervals.json`。波形是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2a：NF-12a（私有用例 `terminal-normal-negative` 的 offset −0.036 → −0.0361；revisions[0] 由第 (ii) 类改归第 (i) 类）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2a/orig/v2-test-offset-search/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `tests/cases.json` | `7d62fedd35e8527017610e86f4557c5094436175305ff0fdce6b5aa06bc12d02` | `98dde635b7a8f74b852f0f3e3b45a6b0dfb5d1f50b0851d55b27850f897d1a90` |

- 本文件删去了改写写进来的一节“用例改动（NF-12a），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-test-offset-search/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 42 组（用例、候选）两版判决全部相同（24 组都通过、18 组都被拒）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 Benchmark 的 D2 预读记录（本地 runs/ 下，未公开）第 3 节与同目录的 decision1.json。
- 退回后的 1 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/16-v2-test-offset-search/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- 上面 first30-fix-r1 一节的区间核验用的是 NF-12a 之后的用例。退回只把 `terminal-normal-negative` 的 offset 由 −0.0361 改回 −0.036；请求与响应的时刻由用例的 first_request、gap 与比较器 td 决定，与 offset 无关，所以那一节的区间表不受影响（推断，本轮未重测）。
- 退回后这一例第 6 次比较在十进制下恰为平局（`runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2a/slot16-tie.json`）。checker 按记录的 `dcmpp` 重放搜索，判决不依赖平局落在哪一侧，这是 revisions[0] 把它改归第 (i) 类的依据；D2 上这一例两版判决也相同。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的历史记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，audit SHA256 `011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。测试表征索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。这些记录不证明当前 Harbor 包。模型试跑尚未完成。固定 Spectre，开源同题等价尚未验证。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：无新的科学冲突需要用 checker 裁定。C109 vref 不在本题合同内，本次不动。
