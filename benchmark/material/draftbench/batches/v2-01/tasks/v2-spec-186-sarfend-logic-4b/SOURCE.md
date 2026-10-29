# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 186-sarfend-logic-4b。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 186。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-186-sarfend-logic-4b/instruction.md)。公开材料仍是 [visible_test.scs](environment/public/visible_test.scs)、[system_test.scs](environment/public/system_test.scs) 和 [sar_support.va](environment/public/sar_support.va)。`sar_fixed_frontend` 是固定公开系统模块，不是本题交付，也不从 gold 拆接口。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`，科学来源 `a5c12a1a01a47e40a7f37b611e55836e59db65cf`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。模型 Agentic 与 one-shot 试做在该历史记录中为 pending。当时仅为 Spectre 扩展集候选，未获发布资格。历史来源与旧运行仍保留原版本。EVAS 行为不是本题验收真值。

## Modeling choices

原题面“上电初态与首帧”和系统连接段给出 0 V / 1 V、0.45 V 门限、200 ps 控制器完成界限、比较器 100 ps 延迟、首帧 `dout3:dout0 = 0111`，以及四次判决后停止。这些数值规则已进入现行 Spec，没有改数。

控制器实现保持自由，但发布顺序、试验对、test 捕获和四次协作不能收成只看最终码。Harbor 包装把控制器交付改为 `/app/circuit.va`。固定公开文件进入 `/app/testbench`，文件名不变。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。这是评分出口适配，不改写历史校准结果，也不给尚未执行的尝试补 0。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “After an output transition finishes, every point in the following hold interval is checked.” 改为 “Every saved point is scored, for all thirteen outputs, except points less than 230 ps (`1.15*200 ps`) after t = 0 or after a `clks`, `dcomp`, or `dcompb` crossing that changes an output target.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `1.15*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）；本题 `tr` 取自 `tests/v2_spec.py:11`（本题用例不给 `tr`，默认 200 ps）。
  - 余量：完成期限仍是原句 “Every digital output change of this controller completes within 200 ps of the triggering control or comparator event.”；在 200 ps 与 230 ps 之间完成的输出不区分，这是用户已接受的余量。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_output_delay_250ps`；应通过（窗内对照）：`inwindow_output_delay_210ps`。
  - 合成控制（未仿真）：底波形为标量状态探针的旧版波形，在内存中推迟输出列后直接调用本题 checker。`late-shift-230ps` 3 个私有用例都被拒；`inwindow-shift-180ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 9/9 符合预期。
  - 旧版 EVAS 0.8.7：参考解与由它派生的两个候选在旧版上都跑不了：参考解用状态数组，旧版在降级阶段报 `dynamic_state_array_access`。实跑确认：候选 6/6 例、参考解抽查 2 例都是 simulation_failed，参考解结论与 first30-r1 一致。所以 `expected.json` 的条目待 Spectre 复跑，不算已验证。另做的标量状态探针（只把数组拆成标量、下标写改成平铺的 if，单独记账，不是校准候选）在全部 4 个私有与公开用例通过；按同样延迟改法派生的探针变体 `late_output_delay_250ps` 3/3 被拒，`inwindow_output_delay_210ps` 3/3 通过。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 3 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r1b：#270 第15项（R15-1）
- rewrite-r1b：NF-03（NF03-06-1）
- rewrite-r1b：NF-23（NF23-06-1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r1b/orig/v2-spec-186-sarfend-logic-4b/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `environment/public/sar_support.va` | `d0e968c32974d674d556ecf4d61cc9d703bd3f8ff1a6a4eeb2694a1e7bbf02ff` | `f2270a504d358140dad30d0b86b33543d1de33799b39e48ff11ae7f34219ceed` |
| `environment/starter/testbench/sar_support.va` | `d0e968c32974d674d556ecf4d61cc9d703bd3f8ff1a6a4eeb2694a1e7bbf02ff` | `f2270a504d358140dad30d0b86b33543d1de33799b39e48ff11ae7f34219ceed` |
| `solution/circuit.va` | `f1355a12b3648d10c01d870f175506c71369dc884b41a3bc70b5890a096dd3d2` | `983b21c79bc6ca24f5ffacd3ef9d6e61726eb96a8a4d4758f241df3c05941161` |
| `solution/dut.va` | `f1355a12b3648d10c01d870f175506c71369dc884b41a3bc70b5890a096dd3d2` | `983b21c79bc6ca24f5ffacd3ef9d6e61726eb96a8a4d4758f241df3c05941161` |
| `tests/calibration/README.md` | `a8c35ecb66c51836e30b3f9037e7ff3e40c3daebe04f7a5d9a4d0009f83905ff` | `f3d016c5f46642696884fb40b7c7de2ff3002122023b96e73e16fcc3af9cdf0e` |
| `tests/cases.json` | `2d94e9e13ff99324229799861183b749bbcbf1426d3564a8dff3429e1c9c9dd6` | `8e3f3b9c7f12560539a76d974f7aec408e94867ff02e757571b737286673fcae` |

- 本文件删去了改写写进来的一节“改写（#270 第15项 / NF-03 / NF-23），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-spec-186-sarfend-logic-4b/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 12 组（用例、候选）两版判决全部相同（8 组都通过、4 组都被拒）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 Benchmark 的 D2 预读记录（本地 runs/ 下，未公开）第 3 节与同目录的 decision1.json。
- 退回后的 6 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/06-v2-spec-186-sarfend-logic-4b/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- 固定支持模块 `sar_fixed_frontend`（公开 2 份与 `tests/cases.json` 中 `fixed-sar-collaboration` 内嵌的 1 份）回到原写法，对所有候选生效。
- `tests/calibration/README.md` 删去 rewrite-r1b 加的改写复核一段（classification 的 revert_notes 第 3 条：随该行退回），按 rewrite-r1b/orig 逐字节恢复。`mutants.py`、`expected.json` 本来就没有因改写而改。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。`testbench/check.py` 与 `testbench/README.md` 由主控接入，本文件未执行该入口。旧 `system_test.scs` 的 include 仍指向 `/work`。主控搬迁公开文件时要改这些路径。本 worker 不改该 scs。

接口句把 `dcomp`/`dcompb` 称为 comparator outputs。这是比较器的输出，不是 `sarfend_logic_4b` 的输出端口。行为要求本模块消费这对决定。starter 方向按 input 记录，并在结果 JSON 保留这个用词冲突。

公开句同时写“`clks` 下降沿拉高 `clkc`”和“`clks` 为低且比较器双低时重发 `clkc`”。私有 checker 把二者并成：`clks` 为低时，互补对当作判决，双低才把 `clkc` 拉高。下降沿若比较器仍互补，两边读法不同。本次不裁决，Spec 保留两句原文。

上电到第一次 `clks` 上升之前，原文说双低不提供有效决定，且 `clkc` 初值为 0。私有 checker 在此区间若发生事件且指针仍为 4，可能把 `clkc` 拉高。本次不采用该 checker 行为。

比较器双高没有公开效果。局部测试写了异常第五次判决保护，行为规则只是四次接受后停止请求。没有另给第五次的方程。

私有 checker 在目标变化后跳过约 `1.15*200 ps`。迁移时（2026-10-27）公开合同是控制器输出过渡结束后检查保持区间，当时不采用 1.15。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 230 ps 评分起点，200 ps 完成期限不变。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`clks`、`dcomp`、`dcompb`、`test`、`dtest0`–`dtest3`，门限是题面写定的 0.45 V。`dcomp`、`dcompb` 在 5 份网表里由电压源直接驱动；在 3 份系统台架（私有 `fixed-sar-collaboration`、两份 `system_test.scs`）里由固定模块 `sar_fixed_frontend` 驱动，见“激励核对”。固定模块读的 `vin` 不由控制器比较，不在此列。
- 激励核对（未仿真）：题包全部 8 份网表（`tests/cases.json` 3 份、公开 `cases.json` 1 份、`environment/public/system_test.scs`、`environment/public/visible_test.scs`、`environment/starter/testbench/system_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/system_test.scs` 的 clks，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。系统台架的 `dcomp`、`dcompb` 不是电压源驱动，精确扫描不覆盖，另按源码与已核收波形核对：固定模块 `sar_fixed_frontend` 输出 `transition(p, 100p, 10p, 10p)`，`p` 只取 0 或 1，所以只停在 0 V 或 1 V；按握手，控制器在比较器输出过 0.45 V、判定被接受后才清 `clkc`，比较器复位还要再晚 100 ps 才开始，所以对守握手的控制器，每次跳变都先走完。已正式核收的 D2 参考解作业 `06-spec186-sarfend-ref-fixed-sar-collaboration` 与 `-deftol`（D2-private-a，REGISTER `a565a298…`；台架激励、`dut.va`、`sar_support.va` 与现包逐字节相同）的波形里，`dcomp`、`dcompb` 恰为 0.45 V 的行共 0 行，转折点离 0.45 V 最近 0.45 V（都在 0 V 或 1 V）。核对见 check-186-system-pair.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/check-186-system-pair.json`）（`990b56c5…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`clks`, `dcomp`, `dcompb`, `test`, and `dtest0` through `dtest3` never rest at the 0.45 V threshold. Each of them that reaches the threshold always crosses it; it never touches the threshold and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。门限照本题原写法写成“the 0.45 V threshold”。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
