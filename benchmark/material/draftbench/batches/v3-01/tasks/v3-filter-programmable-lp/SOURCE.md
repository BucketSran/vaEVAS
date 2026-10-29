# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。没有仿真。码 0 必须保留基线行为，复位过渡区仍没有另给时间宽度。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-programmable-lp/instruction.md)，blob `ad6e69c1da661656d000ca3a5ce1f856d249fa96`，以及 [environment/public/contract.md](environment/public/contract.md)。原来源页 blob `1f75411853d2cb7e2ed134a2ca79947f29f238be`。提交时间 2026-10-15T13:29:47+08:00。

规格 #149 单元 C2，同源组 `v4-334`。来源见 [路线来源](../../../../../../../experiments/benchmark_next/filter/SOURCES.md)。v4 334 提供可调带宽与历史主题。本题使用原创连续低通基线、公开码频映射、换码连续性和复位，不复用旧离散递推。固定快照在 reviewed main `81eb66258b59b0a0cd48cd3decaa767be02cdd58`。未复制旧实现。

已保留：`base` 800–1200 Hz，默认 1000；`initval` ±0.1，默认 0，兼作初态和复位电压；`code` 电压 0–3；`c=clip(round(code),0,3)`；`fc=base*2^c`；`y'=2π fc*(u-y)`，`y(0)=initval`；跨舍入阈值立即改速率且 `y` 连续，不清历史；`reset>0.5` 时 `y=initval`，释放后从此积分；码 0 保留基线行为；输出误差上限 0.008 V，复位切换的模拟过渡区除外。权重 1。固定基线默认 `base=1000`、`initval=0`。

`fixed_lp.va` 在 `/app/testbench/fixed_lp.va`，不在 `dut/` 子目录。`contract.md` 与 `feedback.scs` 在 testbench 根。原候选壳只在 `/app/circuit.va`。

## 建模选择

这是对固定健康低通的扩展。基线可读不可改。候选可选用等价实现，不强制沿用 `idt` 形式。接口壳只留端口。码变化不得清空历史；复位才回到 `initval`。

现行题面写已执行失败记 0、原因另记。历史题面只写自测不能代替终评。缺 Spectre 不是语义错误。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2b：#270 第13项续（R27-1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2b/orig/v3-filter-programmable-lp/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `solution/circuit.va` | `7cf0587b4c0703e57e7b0dbc8f7a08e0ae6e6d64f9d93225c0eed07f6fac0891` | `d4ecdc6a449ea8aa78ba45355686f4e58a26a817c3a7093a4209b5be44c7b95c` |
| `solution/dut.va` | `7cf0587b4c0703e57e7b0dbc8f7a08e0ae6e6d64f9d93225c0eed07f6fac0891` | `d4ecdc6a449ea8aa78ba45355686f4e58a26a817c3a7093a4209b5be44c7b95c` |

- 本文件删去了改写写进来的一节“改写（#270 第13项续），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v3-filter-programmable-lp/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 3 组（用例、候选）两版判决全部相同（3 组都通过）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 `runs/t3-spectre-batchD-20261028/preread-sui01-d2/PREREAD.md` 第 3 节与同目录 `decision1.json`。
- 退回后的 2 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/27-v3-filter-programmable-lp/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- rewrite-r2a 的第6项续（R25-1）已于 2026-10-28 按审核退回（`runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/revert-r2a.json`），NF-14 在 rewrite-r2a 内撤回；本轮只退 rewrite-r2b 的 R27-1，原件取自 rewrite-r2b/orig（与改写前的整包原件相同）。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 filter 路线的历史记录。不运行模型实验。Spectre 扩展集，开源复验未证明。未正式录取或发布。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：合同排除“复位切换的模拟过渡区”，但没有给出该区的时间宽度。本次不补一个数，也不用参考解或 checker 的采样点代替它。旧离散 tick 不继承。
