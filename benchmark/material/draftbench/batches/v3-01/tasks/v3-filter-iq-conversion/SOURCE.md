# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真。上变频乘积和下变频状态方程保持迁移前合同。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-iq-conversion/instruction.md)，blob `6d9272c1c25813d6674ab71d657ad314757127f2`，以及 [environment/public/contract.md](environment/public/contract.md)。原来源页 blob `5b24e9c8f342816bfd3a8cb7a926335b156779bb`。提交时间 2026-10-15T13:29:47+08:00。

规格 #149 单元 C3a，同源组 `v4-364+400`。来源身份见 [路线来源](../../../../../../../experiments/benchmark_next/filter/SOURCES.md)。v4 364 提供上变频主题，400 提供下变频主题，本题合并。固定来源快照在 reviewed main `81eb66258b59b0a0cd48cd3decaa767be02cdd58` 下的 provenance 目录。候选和 checker 为原创重建，未复制旧源码。

已保留：启用时 `up=gain*(i*lc-q*ls)`；`lc=cos θ`，`ls=sin θ`；`a'=2π fbw*(2*rf*lc-a)`，`b'=2π fbw*(-2*rf*ls-b)`，初态 0；`di=a`，`dq=b`；`en<=0.5` 时三个输出为 0，内部低通继续积分，重新启用后显露该状态。gain 0.5–2，默认 1。fbw 1500–3000 Hz，默认 2000 Hz。LO 10–16 kHz。基带 100–1000 Hz。RF 频偏 ±1500 Hz。无噪声、限幅、镜像抑制指标。误差上限：上变频 0.002 V，下变频 0.008 V，和频幅值 0.015 V。权重 1。

公开 `contract.md` 与 `feedback.scs` 在 `/app/testbench/`。原候选壳只迁到 `/app/circuit.va`。没有固定 DUT。

## 建模选择

新建混频模型。接口壳只留端口。真实 I/Q 必须参与乘积，不能直接合成目标载波。禁用时状态继续积分是行为要求，不是某一种内部变量名。

现行题面写已执行失败记 0、原因另记。历史题面只写自测不能代替终评。缺 Spectre 不是语义错误。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2b：NF-16（NF16-25-1-alt2）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2b/orig/v3-filter-iq-conversion/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `solution/circuit.va` | `a45963a9769e296ec25fab4777bb5509ceda24269d46f147867ecabda5e9a4c2` | `61e5b94f1d237d342e875bda637158f93ea13c8a260094112edb7c2bf751ebd9` |
| `solution/dut.va` | `a45963a9769e296ec25fab4777bb5509ceda24269d46f147867ecabda5e9a4c2` | `61e5b94f1d237d342e875bda637158f93ea13c8a260094112edb7c2bf751ebd9` |

- 本文件删去了改写写进来的一节“改写（#270 NF-16），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v3-filter-iq-conversion/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 3 组（用例、候选）两版判决全部相同（3 组都通过）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 `runs/t3-spectre-batchD-20261028/preread-sui01-d2/PREREAD.md` 第 3 节与同目录 `decision1.json`。
- 退回后的 2 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/25-v3-filter-iq-conversion/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 filter 路线的历史记录。不运行模型实验。Spectre 扩展集，ngspice 复验未证明。未正式录取或发布。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：无新的符号冲突。旧模型的钳位、电源共模和离散 tick 按路线记录不继承，本次不加回。
