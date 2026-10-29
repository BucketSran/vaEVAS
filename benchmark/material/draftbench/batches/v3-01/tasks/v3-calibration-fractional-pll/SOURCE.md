# 来源与迁移记录

2026-10-27 只迁题面和本页。阶段保持 implementation。`/app/circuit.va` 保留原完整整数 PLL，作为 existing-model 待扩展。没有仿真，也没有把参考解的控制系数写成合同。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-calibration-fractional-pll/instruction.md)，blob `571b2ebaa0c2dbb670792276909e4a0e671ae355`。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-calibration-fractional-pll/SOURCE.md)，blob `f71a85e22fded58f0f4179883b5956554f8ba809`。提交时间 2026-10-15T13:29:47+08:00。

本题对应批准规格 [#150](https://github.com/BucketSran/vaEVAS/issues/150)，设计单元 D1。固定基线 main `81eb66258b59b0a0cd48cd3decaa767be02cdd58`。来源 v4 302 只提供工程主题和接口比较依据，来自 `benchmark/material/historyref/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/` 的固定快照。题面、控制器、健康行为环境和独立判据是新编写资产，没有复制受限来源实现。上游 v4 许可未知，来源记录不授予再分发权。

D1 采用上升沿 N/N+1 平均比率，替代 302 旧的 toggle 计数符号。已有 v2 fine-TDC 仍是原独立任务，没有改名。D2/D3 不在本题。路线记录见 [calibration README](../../../../../../../experiments/benchmark_next/calibration/README.md)。激励和环境都是行为合成，不是硅片数据或晶体管模型。

已保留的数值：灵敏度 8..12 MHz/V，标称 10 MHz/V；150 µs 加入绝对值不超过 2 MHz 的频偏，175 µs 撤除；参考 10 MHz；`n` 为 3 或 4；`frac` 为 0、0.25、0.5、0.75；模式改变 2 ns 内生效并清余数、部分计数和资格；相邻 fb 上升沿之间恰好 N 或 N+1 个实际 DCO 上升沿，`frac=0` 只能 N；窗口平均与 `N+frac` 误差不超过 0.04；DCO/参考频比误差不超过 0.06；fb/参考不超过 0.015；锁定窗相位平均统计的阈值为 0.2 周期，平均与绝对值的顺序已于2026-10-27由用户选定（见决定卡末段），展开峰峰不超过 0.35 周期；模式改变或 reset 后 2 ns 内撤销 lock，模式改变后首 1 µs 保持低，15 µs 内重新获得资格；reset 高期间 fb 和 lock 为低，检查为 2 ns 加 200 ps；15 µs 期限允许 2.2 ns；期限后的窗口检查频率、相位和 95% 资格覆盖；每段驻留 25 µs。逻辑高 0.9 V，阈值 0.45 V。权重 1。健康 DCO 默认 `sensitivity=10e6`、`frequency_step=0`、`step_start=150u`、`step_end=175u`。

`healthy.va` 在 `/app/testbench/healthy.va`。`public-default.scs`、`acceptance-windows.json`、`interface.json` 在 testbench 根。原 `public/dut.va` 是待扩展的完整代码，现只在 `/app/circuit.va`，不另复制到 testbench。

## 建模选择

existing-model：求解者在完整整数实现上扩展分数分频，同时保留 `frac=0` 的整数行为。可以改控制算法、辅助模块和连接。不要求唯一累加器或 DSM 比特序列。必须由真实反馈误差调谐 DCO。`dco` 是候选输入，候选输出只有 `tune`、`fb`、`lock`。

现行题面写已执行失败记 0、原因另记。历史题面原句是“编译、超时或后端证据不完整保留未评分状态，不当作语义失败”。该原义保留。现行 0 分不表示语义错误，缺 Spectre 也不是语义错误。

## 2026-10-29 退回第 (i) 类改写（决定单第 1 项）

用户 2026-10-29 对决定单第 1 项按推荐定“退回原件”：参考解与台架以 Spectre 可解为准，第 (i) 类改写（只为迁就 EVAS 的写法改写）退回原件。清单与做法照 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/classification-20261028.json` 的 rows、revisions 与 revert_notes。本题退回 1 行，由 first30-fix-r4 第 0 项执行（2026-10-29，未仿真）：

- rewrite-r2b：#270 第5项续（R24-1-alt2）、NF-20（NF20-20-1）

退回的文件从 `runs/t3-harbor30-20261027/issue270-resolution/rewrite-r2b/orig/v3-calibration-fractional-pll/` 逐字节复制回来。复制前核对现行文件等于该轮 `packages-after.sha256` 的值（改写交付时的状态），复制后等于该轮 `orig.sha256` 的值：

| 文件 | 改前 sha256（改写版） | 改后 sha256（原件） |
| --- | --- | --- |
| `environment/public/dut.va` | `c8f4821f37fc16ccdf8eddaccbc5b9beb47b38a6f0f701902da96951c4086626` | `c567764776f0891c42202f2d83c6bc91fad1a2e81cb9c477e5c4e1f21a44217f` |
| `environment/starter/circuit.va` | `c8f4821f37fc16ccdf8eddaccbc5b9beb47b38a6f0f701902da96951c4086626` | `c567764776f0891c42202f2d83c6bc91fad1a2e81cb9c477e5c4e1f21a44217f` |
| `solution/circuit.va` | `c2b73f25c04b2f9a3ce0fa69204248a145790416e21804cbd5c4526f50eb95a9` | `6632ecd8f08d6a4c0176c0875e13be53835f0c959d54fec21b51769a1589cb6e` |
| `solution/dut.va` | `c2b73f25c04b2f9a3ce0fa69204248a145790416e21804cbd5c4526f50eb95a9` | `6632ecd8f08d6a4c0176c0875e13be53835f0c959d54fec21b51769a1589cb6e` |

- 本文件删去了改写写进来的一节“改写（#270 第8项、第5项续 / NF-20），待 Spectre 新旧对照”（含其中的状态行），改前全文存 `runs/t3-harbor30-20261027/first30-fix-r4/orig/v3-calibration-fractional-pll/SOURCE.md`；那一节之外的文字未改。
- 依据：批次 D2 在 Spectre 21.1 上对照原件作业与改写版作业（D2 四包，2026-10-29 已正式核收；执行身份 `spectre-D2-must-public-v1（结果包 sha256 f0bbe69eb210f9ca…）`、`spectre-D2-must-private-a-v1（结果包 sha256 86f7892ab6d1302f…）`、`spectre-D2-must-private-b-v1（结果包 sha256 ed546a857219b69f…）`、`spectre-D2-must-alt-v1（结果包 sha256 e369364972507acf…）`）。本题 3 组（用例、候选）两版判决全部相同（3 组都通过）；14 题共 156 组两版判决相同。原件参考解在 Spectre 上可解。见 Benchmark 的 D2 预读记录（本地 runs/ 下，未公开）第 3 节与同目录的 decision1.json。
- 退回后的 4 个文件与 D2 快照原件 `runs/t3-spectre-batchD-20261028/d2/snapshot/original/20-v3-calibration-fractional-pll/` 逐字节相同，D2 的原件作业跑的就是这份。本轮没有为退回跑旧版 EVAS。
- 这些写法回到 EVAS 一侧；#270、#276 的公开说明由主控转总协调，交 EVAS 线更新。
- 删去的一节还含第8项（R16-1，pulse→PWL）的历史记录。那一行已于 2026-10-28 撤回（总协调定 S2 选 (c)，`runs/t3-harbor30-20261027/issue270-resolution/rewrite-main/revert-s2-pwl.json`），几个台架文件早已是原件，本轮未动。
- 候选可见的起始模型（`environment/public/dut.va`、`environment/starter/circuit.va`，即 `/app/circuit.va`）随参考解一起回到原写法（`$rtoi` 与 `fb` 上的 cross）。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只指路线记录中的历史身份：r9 为 [author-calibration-r9.json](../../../../../../../experiments/benchmark_next/calibration/author-calibration-r9.json)，其后 r10 保持 15 µs 合同并完成 20 个新 PLL 条件；最终叙述为 44 个条件中 14 个正确实现条件通过、15 种语义错版的 30 个条件被拒绝。r9 不能替代 r10。没有模型试做。Docker 不带商业工具。尚无同题开源后端复验资格。未正式录取或发布。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

未决：`/app/testbench/interface.json` 的 `hidden_changes` 写 “published bias/common-mode envelope and slope, actuator, DCO sensitivity and frequency-disturbance ranges”。题面没有公布 bias、共模包络或斜率范围。该句看起来混入了 D2/D3 的共享措辞。本次不把共模或 bias 加进 D1 合同，也不用 checker 里的 `cm_target` 定答案。

独立Astra B-R1-02确认平均相位口径未决：旧题面“平均相位绝对值”、旧作者README“平均绝对相位”与旧checker的 `abs(mean(phi))` 不完全一致。新英文曾明确写 `mean(abs(phi))`，本轮已撤回该未经选择的明确化，并在Spec具名TBD，保留0.2周期阈值与0.35周期峰峰值，但不选择平均与绝对值顺序。正负相位算术例可区分两式，不证明完整PLL可达。当前数值checker保留旧字节，不能把它的判定当作该科学条件已选定。只有合同确定并完成对应校准后才可授予评分资格。2026-10-27用户已选定口径，见决定卡末段；校准仍待完成。

### 评分合同决定卡

2026-10-27补充；同日用户确认采用下述持续平均偏差建议，落实见本卡末段。复用B-R1-02的纸面例：7个`+0.30`与3个`-0.04`周期的相位，峰峰值0.34满足既有0.35限值；`abs(mean(phi))=0.198`通过0.2限值，`mean(abs(phi))=0.222`不通过。这里只证明两种定义会改变评分，不证明该序列能通过完整PLL的分频、因果与恢复条件。

建议把两项职责分开：用`abs(mean(phi_unwrapped))<=0.2`限制持续平均相位偏差，用既有`max(phi_unwrapped)-min(phi_unwrapped)<=0.35`限制波动。理由是本题允许分数分频的正常边沿摆动，考察闭环跟踪和资格恢复，没有承诺逐边沿贴合参考。若希望限制每个边沿离参考的平均距离，则选择`mean(abs(phi_unwrapped))<=0.2`；它是不同且更强的要求，不能当作等义翻译。

公式选择时还须一并写清相位序列：建议首个样本取相对最近参考沿的有符号相位，后续按连续分支展开，两个统计都用该序列。否则原始最近沿相位`[+0.49,-0.49]`会平均成0，而连续序列`[0.49,0.51]`的平均为0.5、峰峰仅0.02，半周期偏置可能被正负抵消。这项定义是本卡建议；旧checker已经这样展开，不构成用户已选的证明。

用户只需决定相位指标要衡量“持续平均偏差”还是“逐沿平均距离”，相应公式和展开约定一起确认。Spec、公共acceptance说明、公开与私有`v2_next_calibration.py`须使用同一定义；保留0.2、0.35及既有频率、15µs恢复要求。采用建议时现checker公式可保留，选择另一式则需改变统计行与错版期望。无论选哪一式，均不能直接继承历史校准资格，也不因现有gold结果选择标准。

#### 决定与落实

2026-10-27用户确认：相位以参考周期计，单位不是度。每个评估窗内，首个反馈上升沿取相对最近参考上升沿的有符号相位，此后每个沿先按各自最近参考沿取值，再整周期平移到与前一值相差不超过0.5周期，得到连续序列`phi`。持续平均偏差`abs(mean(phi))`不超过0.2周期；同一序列的峰峰值`max(phi)-min(phi)`不超过0.35周期。这不是`mean(abs(phi))`。频率比、15µs恢复与资格覆盖等原有责任不变。

现行Spec已写明上述定义，并删除了两式并列的TBD。公私[v2_next_calibration.py](tests/v2_next_calibration.py)（SHA256 `7efea5c0bbd65a0f644bd702d6e4b0540f867768a102ce3748a8489ee2c32f96`）原本就按这种展开计算这两项统计，这次没有改动；公开`acceptance-windows.json`只含窗口时刻，不含统计公式，也未改动。

合成控制复用本卡的纸面例：7个`+0.30`与3个`-0.04`的序列`abs(mean)`为0.198，判为通过；若按被否决的`mean(abs)`计为0.222。原始最近沿为`+0.49`、`-0.49`交替的序列展开后平均0.50，判为拒绝。结果在`runs/t3-harbor30-20261027/grading-adoption/`。这只检查统计公式，不证明完整PLL能满足分频、因果与恢复条件；作者校准与后端运行仍待完成。
