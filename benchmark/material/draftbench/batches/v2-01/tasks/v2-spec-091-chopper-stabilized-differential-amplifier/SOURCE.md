# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 091-chopper-stabilized-differential-amplifier。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 091。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-091-chopper-stabilized-differential-amplifier/instruction.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`，科学来源 `a5c12a1a01a47e40a7f37b611e55836e59db65cf`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。

公开合同现为 system-interfaces-v2，固定 helper 接口、职责与替身消费。每题六个条件，包括两个组件条件和两个顶层消费条件。旧的两条件校准与模型结果只覆盖旧身份，均保留，不覆盖或升级其成绩。迁移前 SOURCE 还写新版本的 reference、alternative、语义与架构负例 Spectre 作者校准已完成，新 prompt 模型试做尚未完成。这些句子都绑定旧包身份，不认证本次 `/app` 包。当时仅为 Spectre 扩展集候选，未获发布资格。历史来源与旧运行仍保留原版本。EVAS 行为不是本题验收真值。

## Modeling choices

迁移前系统合同给出 helper 端口顺序、`demod_sample = gain*(vinp-vinn)+polarity*gain*vos_amp`、`baseband_ref = gain*(vinp-vinn)`、`2*tr` 延迟加 `tr` 过渡的通知、最终输出在 chop 交点后 `4*tr` 内完成，以及 producer `0.16 V` 和 consumer `0.22/0.67/0.9/0.14 V`。这些数值规则已进入现行 Spec，没有改数。旧成绩不能作为本版本通过证据，这句留在本文件。六个条件仍是现行验收，不是历史成绩。

`lp_alpha` 称为 update fraction，Spec 写成从旧状态向解调样本走该分数。这是原词的直接读法，没有新系数。差分输出以 `vcm` 为中心，所以两个端口是 `vcm±state/2` 再夹到轨。

实现组织自由，两个 helper 的职责和替身消费不能收成只看顶层最终码。Harbor 包装把顶层文件改为 `/app/circuit.va`，两个 helper 保持原文件名并平铺在 `/app`。公开激励进入 `/app/testbench`。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。这是评分出口适配，不改写历史校准结果，也不给尚未执行的尝试补 0。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “After the allowed transition finishes, every point in the following hold interval is checked.” 改为 “Every saved point is scored, for all four public outputs, except points less than `4.1*tr` after t = 0 or after an event that changes the target of any public output: a `chop_clk` crossing while enabled, not in reset, and not held, or a clear by `rst` or `enable`. In the consumer-substitute condition, every saved point from t = 0 is scored against the substitute voltages.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `4.1*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）；本题 `tr` 取自 `tests/v2_spec.py:15`（默认 100 ps）。消费者替身用例由 `tests/v2_structure.py:19-34` 判定，每个保存点都评分。
  - 余量：到达期限仍是原句 “The public outputs may finish within `4*tr` after the chop crossing.”；在 `4*tr` 与 `4.1*tr` 之间到达的输出不区分，这是用户已接受的余量。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`tests/v2_structure.py` 与其公开副本、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_lp_output_delay_0p8tr`；应通过（窗内对照）：`inwindow_lp_output_delay_0p55tr`。
  - 合成控制（未仿真）：底波形为旧版 first30-r1 的参考波形（`architecture-component-producer` 用展开结构的旧版波形 `diag-091-component-producer`），在内存中推迟输出列后直接调用本题 checker。`late-shift-0.8tr` 在 contract-base、contract-stretched-input、architecture-component-producer、architecture-component-consumer、architecture-producer 被拒，在 architecture-consumer 通过；`inwindow-shift-0.55tr` 6 个私有用例都通过；未平移的底波形 6/6 通过。共 18/18 符合预期。
  - 旧版 EVAS 0.8.7：`late_lp_output_delay_0p8tr` 在 contract-base、contract-stretched-input、architecture-component-producer、architecture-component-consumer、architecture-producer 被拒，在 architecture-consumer 通过；`inwindow_lp_output_delay_0p55tr` 在 architecture-component-producer 被拒，在 contract-base、contract-stretched-input、architecture-component-consumer、architecture-producer、architecture-consumer 通过。共 10/12 符合 `expected.json`；不符的 2 例都在 `architecture-component-producer`：旧版对层次保存列 `IDUT.*` 静默返回 0，两个候选都只在这些列上失败，公开输出没有失败，参考解在 first30-r1 同样如此（#270 第7项），这几例不作候选证据。参考解抽查 2 例（private/contract-base、public/contract-base）都与 first30-r1 一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r1b：#270 第7项（R13-1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r1b/orig/v2-spec-091-chopper-stabilized-differential-amplifier/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `environment/starter/testbench/v2_structure.py` | `48efcd6c4ae8f6c5f673e987682a26958a372f58e83bed4f155c6950975e9226` | `ba882616fde45874186b1ffe1a08b1f3dfbf986a639cc67fdc9d9e6861e0a6d0` |
| `tests/calibration/README.md` | `1a7f80e9b03f6bf7d0417cb91730adc4f92517fccce722166356ffbfdbd952a3` | `facd05738d084ace6d79ec7e0d5bf1a5e2225a3cbd0a623aa5e55a41d439c3a0` |
| `tests/cases.json` | `c639d02d4c264dfe1f18b9b65e62654750f33279b11fe1ddcc81bc4d95311458` | `3fc69dfe61153f3bc7422c9cdb5316e3760133738c9ae5aff14c8ddc649b331c` |
| `tests/v2_structure.py` | `48efcd6c4ae8f6c5f673e987682a26958a372f58e83bed4f155c6950975e9226` | `ba882616fde45874186b1ffe1a08b1f3dfbf986a639cc67fdc9d9e6861e0a6d0` |

- 本文件删去了改写写进来的一节“改写（#270 第7项），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-spec-091-chopper-stabilized-differential-amplifier/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 21 组（用例、候选）两版判决全部相同（16 组都通过、5 组都被拒）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 Benchmark 的 D2 预读记录（本地 runs/ 下，未公开）第 3 节与同目录的 decision1.json。
- 退回后的 4 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/10-v2-spec-091-chopper-stabilized-differential-amplifier/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- 私有用例 `architecture-component-producer` 回到层次保存写法（`IDUT.*`），checker `tests/v2_structure.py` 与公开副本回到原键名；退回后两份 checker 仍逐字节相同。
- `tests/calibration/README.md` 删去 rewrite-r1b 改写的旧版层次列一段（classification 的 revert_notes 第 3 条：随该行退回），按 rewrite-r1b/orig 逐字节恢复。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。`testbench/check.py` 与 `testbench/README.md` 由主控接入，本文件未执行该入口。

顶层和两个 helper 的端口顺序、电气类型和输入输出角色都写在迁移前 instruction 中。局部端口名可以不同。这不是接口缺口。

chop 极性在上升沿和下降沿哪一个为 +1，公开公式没有写死。私有 checker 用上升沿 +1、下降沿 -1。本次不把这个符号补进 Spec。`event_strobe` 在第一次翻转前的电平也没有公开初值。

已使能且未复位的上电保留状态没有单独句子。复位或禁用才把差分状态清到 0。私有 checker 在清零事件之前把低通状态放在 `vcm`。本次不采用。

私有 checker 跳过 `4.1*tr` 后才评分。迁移时（2026-10-27）公开允许窗口是 `4*tr`，当时不采用 4.1。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面保留 `4*tr` 到达期限，另写明 `4.1*tr` 评分起点。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`chop_clk`、`rst`、`enable`、`hold`，门限 `vth`（缺省 0.45 V，用例不覆盖）。`vinp`、`vinn` 是模拟输入；`demod_sample`、`baseband_ref`、`event_strobe` 是模块之间的信号，在全部网表里都由模块产生（被测核心、固定伙伴或替身），电压源只驱动 `vinp`、`vinn` 与四个控制；都不在此列。
- 激励核对（未仿真）：题包全部 9 份网表（`tests/cases.json` 6 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 chop_clk，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`chop_clk`, `rst`, `enable`, and `hold` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
