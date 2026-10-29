# 真实采样级数据建模：Harbor迁移

## 行为依据

本题保留[原公开合同](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-data-sampling-identification/instruction.md)和[原来源与历史校准记录](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-data-sampling-identification/SOURCE.md)的身份。来源为Manuel Moser / JKU的SKY130采样级晶体管瞬态，原电路892272208df28b6c7620101e129a9d8dd95ebab7，PDK f62031a1be9aefe902d6d54cddd6f59b57627436，来源许可Apache-2.0。真值由ngspice 47生成，候选VA由Spectre执行，两者分开。

32条训练、2条公开自测和4条完整留出实验，以及采集RMS、采样误差和保持误差合同均沿用原件。源码转录、源数值检查、公开拟合与历史isolated-r4校准见原SOURCE的各项固定记录；历史失败和规范化身份差异仍属于原记录，不改写为当前Harbor包通过。

## 建模选择

本次把求解者交付统一到/app/circuit.va，保留sampling_model接口及全部模型自由度。公开数据保持原字节，2条selftest作为公开诊断，4条heldout真值保持私有。评分继续从实际候选轨迹与固定源观察独立计算，不用gold输出作真值，不重新拟合或改变误差界。

旧内部文件名dut.va可由交付适配器在独立临时目录映射，映射须保持候选字节不变。已执行失败的Harbor分数出口按现行项目政策记0并单独保存原因；原历史reward或执行状态不变。

### 2026-10-28 补充（tolerance-r1）：公开台架 public-default.scs 与公开用例对齐

本题不在 D1。总协调定的同一轮题目修正里，只把公开台架 `public-default.scs` 的写法对齐到本题公开用例现有的写法，不引入新取值。用例网表（`tests/cases.json` 与公开 `cases.json`）、激励、合同、checker、参考解都不动。未仿真。

- 改了哪些行：`environment/public/public-default.scs` 与 `environment/starter/testbench/public-default.scs` 两份，在 `tran` 语句前新加 `options options reltol=1e-6 vabstol=1e-8 iabstol=1e-14`。其余行逐字节不变。
- 依据：公开用例 `selftest-0`、`selftest-1` 都在 `tran` 前写着这同一行，私有 `tests/cases.json` 的 6 个用例也一样。
- 仍未对齐、本轮不改的：`public-default.scs` 的 `maxstep` 仍是 50p（公开用例为 10p）；`tran` 没写 errpreset，公开用例也没写。按本轮“maxstep 不改、不引入新取值”的要求都不动，已在记录里交主控。本题的容差取值由总协调以后再定。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v2-data-sampling-identification/`。改后 sha256：`environment/public/public-default.scs` `22406078…`；`environment/starter/testbench/public-default.scs` `d59f4896…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2b：#270 第10项（R22-1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2b/orig/v2-data-sampling-identification/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `solution/circuit.va` | `02421341d1fa3e4c7feef15f8a6ab422484a18d84fa02c9b399d755afe0ef85d` | `61cd42da4a0a83e60b67e7d481388d8ad2ce4feadaa683ade461f127cda8b94f` |
| `solution/dut.va` | `02421341d1fa3e4c7feef15f8a6ab422484a18d84fa02c9b399d755afe0ef85d` | `61cd42da4a0a83e60b67e7d481388d8ad2ce4feadaa683ade461f127cda8b94f` |

- 本文件删去了改写写进来的一节“改写（#270 第10项），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v2-data-sampling-identification/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 8 组（用例、候选）两版判决全部相同（8 组都通过）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 Benchmark 的 D2 预读记录（本地 runs/ 下，未公开）第 3 节与同目录的 decision1.json。
- 退回后的 2 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/02-v2-data-sampling-identification/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。

## 待定项

本次完整/app题包尚未完成Spectre参考、替代正确实现和错误对照的当前校准；公共/私有执行、交付收集及独立Harbor verifier仍需实际验证。Docker可用但本机未发现Spectre，不能用缺后端的0分声称模型被语义检出。本阶段为implementation，grading/runtime继续待定；未正式录取、模型实测或发布。
