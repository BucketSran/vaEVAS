# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真。低幅度槽按合同自己的 `第k槽` 编号保留为 k=2，不另选一槽。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-sweep-measurement/instruction.md)，blob `34d4dccc70e57e9102aeb7f7cb680dbed0454be3`，以及 [environment/public/contract.md](environment/public/contract.md)。原来源页 blob `4b20a8e33d56dad9c4d554aa80b26c005122720f`。提交时间 2026-10-15T13:29:47+08:00。

规格 #149 单元 C4，同源组 `original-filter-measurement`。来源见 [路线来源](../../../../../../../experiments/benchmark_next/filter/SOURCES.md)。这是新建连续滤波测量工程：只读低通 DUT、真实扫频和同步积分。候选和 checker 为原创重建。

已保留：四频点；`f0=1000`、`f1=4000`、`f2=16000`、`f3=8000` Hz，范围 500–20000 Hz；`slot` 默认 0.02 s；`settle` 默认 0.004 s，合法 0.001–0.005 s；`window` 默认 0.008 s，合法 0.001–0.009 s；`settle+window<slot`；`amplitude` 默认 0.12 V，合法 0.05–0.2 V；第 k 槽从 `k*slot` 起；合同写“第2槽”为 0.0001 V。合同同时定义“第k槽从 k*slot 起”，因此第2槽是 k=2，对应 `f2`。同步积分 `C=2/window*∫v(t)*exp(-j2π fk*(t-槽起点)) dt`；gain 为模比，phase 为包裹到 `[-π,π]` 的辐角。窗末更新并保持到下一窗末。有效条件 `|Cin|>=0.01 V`、`window*fk>=6`、`settle>=0.003 s`。固定 DUT 截止 600–4000 Hz、增益 0.5–2。源码默认 `fc=1500`、`g=1`。误差：幅值 0.035，包裹相位 0.035 rad，激励 0.002 V。权重 1。

`healthy.va` 在 `/app/testbench/healthy.va`，不在 `dut/` 子目录。`contract.md` 与 `feedback.scs` 在 testbench 根。原仪表壳只在 `/app/circuit.va`。

## 建模选择

候选是扫频仪表。固定低通只读。必须驱动四个频点并从实际波形测量。不能读 DUT 参数或用公式代替积分。接口壳只留端口。低幅度窗口报告 `valid=0` 是合同的一部分。

现行题面写已执行失败记 0、原因另记。历史题面只写自测不能代替终评。缺 Spectre 不是语义错误。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2b：#270 第13项续（R28-1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2b/orig/v3-filter-sweep-measurement/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `solution/circuit.va` | `6988d7d4254b68978243b91a04d177fd55b2e651182ca3363b4138e6b1af4338` | `3a774882ca3eab7d15d8fb44d43d19044d8f383596e0afe71cabd16b46235212` |
| `solution/dut.va` | `6988d7d4254b68978243b91a04d177fd55b2e651182ca3363b4138e6b1af4338` | `3a774882ca3eab7d15d8fb44d43d19044d8f383596e0afe71cabd16b46235212` |

- 本文件删去了改写写进来的一节“改写（#270 第13项续），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v3-filter-sweep-measurement/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。14 题共 156 组（用例、候选）两版判决相同。本题两版带容差（reltol 1e-6、vabstol 1e-8、iabstol 1e-12）的参考解作业都写满单文件上限被截断，4 组两版都判不了，正在补跑；缺省容差的原件对照 4/4 通过。见 `runs/t3-spectre-batchD-20261028/preread-sui01-d2/PREREAD.md` 第 3 节与同目录 `decision1.json`。
- 退回后的 2 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/26-v3-filter-sweep-measurement/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 filter 路线的历史记录。不运行模型实验。Spectre 扩展集，开源复验未证明。未正式录取或发布。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：若把“第2槽”读成从 1 数起的第二槽，会落到 k=1 而不是 k=2。合同自己写了“第k槽从 k*slot 起”，与 k=2 一致，所以题面采用 k=2。这不是用 checker 改科学；`cases.json` 里 0.0001 也在 amplitudes 的下标 2，只作为同一编号的旁证，不单独定案。

## 2026-10-29 修正 r5：积分窗末端放宽 δ（first30-fix-r5，第 (ii) 类）

总协调 2026-10-29 批准的第 (ii) 类修正（first30-fix-r5 第 1 项）。只改参考解里的一处比较边界；题面（`instruction.md`）、公开与私有 checker、用例与公开文件都没有改。本题没有 `tests/calibration/` 候选，不用补。未仿真。

- 改了什么：`solution/circuit.va` 与 `solution/dut.va` 第 16 行。
  - 原：`active=(tloc>=settle && tloc<=settle+window);`
  - 新：`active=(tloc>=settle && tloc<=settle+window+1e-6*window);`
  - 两个文件改后仍逐字节相同，sha256 `3a774882ca3eab7d15d8fb44d43d19044d8f383596e0afe71cabd16b46235212` → `506438b13f01b249c635fed65c2b51f1b8a2d8c36596ec5f2b6361c413ac1eff`。
  - 改后与 D2 快照 `runs/t3-spectre-batchD-20261028/d2/snapshot/original-delta/26-v3-filter-sweep-measurement/solution/` 的同名文件逐字节相同。快照记录 `runs/t3-spectre-batchD-20261028/d2/snapshot/SNAPSHOT.json`（sha256 `1b49b778cab62b347f84e0c5add7d99c524bda5c6faa81d703d447ce39e48b80`）的 `delta` 一段写的就是这一处：old `tloc<=settle+window)`、new `tloc<=settle+window+1e-6*window)`，original-delta 的改前、改后哈希与上面相同；它的计划一句（转述）是“timer 不动，窗末端放宽到 settle+window+δ，δ = 1e-6·window（缺省 8 ns），合同不变；可选加一句：窗末报告读的是整个窗口的积分”。
- 为什么（标准线的平局判定）：
  - 测量用的 `@(timer(settle+window,slot))` 恰好落在积分窗 `tloc<=settle+window` 的末端。LRM 5.10.3.3 允许事件的时间点在设定时刻，或稍后一点。
  - 落在稍后时 `!active` 已为真，四个 `idt(…,0,!active)` 处在复位、返回 0，`den` 为 0，本应有效的窗报 `valid = 0`，gain、phase 也跟着报 0。
  - 这是平局判据第 4 种情形（`runs/standard-line-20261028/rules/TIE-RULE.md`，sha256 `418d542a3035848fb6a0f124d8a70dba1a53e9b483fec88ccb2c327be230b108`）：被评分的 valid、gain、phase 在两种落点下判定不同，属第 (ii) 类，题目必须避开。
  - 标准线的复核表 `runs/standard-line-20261028/answers/slot26-tie/slot26_window_end_tie.json`（sha256 `bb639078d3a0ff37259f8f592fbd8fe90816273858d0dfdb83582aa7d13bc9c5`）：sweep-0 的 k = 3（f3 = 8 kHz，被评分的有效窗）按精确事件时刻就近舍入，就已落在窗末之后 1.04e-17 s；三个用例里每个有效窗，事件时刻再晚 1 个 binary64 步都得 valid = 0。
  - 改法是标准线定的改法 2：timer 不动，窗末端放宽 δ = 1e-6·window（缺省 window 8 ms 时 8 ns，sweep-1 的 1.3 ms 时 1.3 ns）。样板 r2.37 第 3 节平局条以本题为例。
- **原参考解在 Spectre 上通过，不能说明题目原来是对的。** 不加 δ 的原件在 D2 的缺省容差对照（已核收）与 D2R（预读）上都通过（见下一条），靠的是 Spectre 的事件时刻算法碰巧落在设定时刻上或略早。按标准线的复核，只有略早于精确时刻的时刻算法（例如先把 k·period 舍入再加起点，sweep-0 的 k = 3 早 6.9e-18 s）才给 valid = 1；换一个同样合乎 LRM 的后端或时刻算法，就会判错。
- 依据（Spectre 21.1）：
  - D2R（预读，尚未正式核收；执行身份 `spectre-D2R-must-v1（结果包 sha256 8191421cd53eeae1…）`）：加 δ 与不加 δ 的参考解 8 对作业（原件、改写版各 4 例：私有 sweep-0、sweep-1、sweep-2 与公开 sweep-0），都通过，判决相同（`runs/t3-spectre-batchD-20261028/d2s26/returns/decision/decision-d2r.json`，主控预读页 `runs/t3-spectre-wave2-20261029/returns-preread-…/d2r-f30c-w225/PREREAD.md` 第 1 节）。其中原件加 δ 的 4 个作业 `26-filter-sweep-delta-ref-*-f128` 跑的 `dut.va` 就是改后这份；网表是本题用例网表加 D2 写入的容差行（reltol 1e-6、vabstol 1e-8、iabstol 1e-12）与执行路径一行（first30-fix-r5 逐个作业核对）。
  - D2（2026-10-29 已正式核收；执行身份 `spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）：缺省容差的原件加 δ 4 个作业 `26-filter-sweep-delta-ref-deftol-*` 都通过，与不加 δ 的缺省容差原件判决相同；它们的网表就是本题用例网表加执行路径一行，`dut.va` 也是改后这份。
  - 所以改后的参考解在 Spectre 上已经跑过，预计不用为这一处重跑。
- 窗末报告读的是整个窗口的积分（只写在本页，题面不改）：
  - δ 只让积分器在测量 timer 读数之后才复位。timer 在 settle+window 或稍后几个 binary64 步触发，读 `V(ai)`、`V(bi)`、`V(ao)`、`V(bo)`，读到的是从窗口起点积到读数时刻的积分，与题面的 `[slot start + settle, slot start + settle + window]` 只差这几个步长。
  - 读数之后到 settle+window+δ，积分器还在积，但没有人读；`!active` 一为真就复位，下一窗从 0 起积。
  - δ 最大 9 ns（window 9 ms 时）；合法的 settle+window 最大 14 ms，离槽边界（slot 20 ms）至少 6 ms，δ 不会让窗口跨进下一槽。
  - 理由：报告的量与合同相同，题面已写在窗末更新报告、积分区间就是窗口本身，所以题面不用改；这一句写给读 SOURCE 的人，免得再回头核对“放宽窗末端是否改了积分区间”。
- 旧版 EVAS 与 EVAS：本轮都没有运行（只改一处比较边界，判据以 Spectre 为准）。
- 改前原文件逐字节存于 `runs/t3-harbor30-20261027/first30-fix-r5/orig/v3-filter-sweep-measurement/`；本页改后的 sha256 记在交付记录里。
- 记录：first30-fix-r5 交付（`runs/t3-harbor30-20261027/first30-fix-r5/disposition.md`）。
