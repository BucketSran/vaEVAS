# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 353-ffe-transmitter-3tap。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 353。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-353-ffe-transmitter-3tap/instruction.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`，科学来源 `a5c12a1a01a47e40a7f37b611e55836e59db65cf`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。模型 Agentic 与 one-shot 试做在该历史记录中为 pending。当时仅为 Spectre 扩展集候选，未获发布资格。历史来源与旧运行仍保留原版本。EVAS 行为不是本题验收真值。

## Modeling choices

原题面“本轮冻结的数值合同”规定 `reset` 在 `clk` 上升沿读取，三个符号初值 0，`main = main_amp*当前符号`，`pre = tap_step*precode*上一符号`，`post = -tap_step*postcode*上上符号`，`debug = vcm+各贡献`，`vout = clamp(vcm+main+pre+post)`。两次上升沿之间 tap 改变不更新目标。这些数值规则已进入现行 Spec，没有改数。

冻结句写了 `clamp`，没有再写上下界。Spec 用同一段已经声明的输出低电平 `vss` 和满幅 `vdd` 作为这个 clamp 的界限。这是对已有参数角色的对应，不是新的电压数。debug 端口不夹位。

实现保持原约定。Harbor 包装把单文件交付改为 `/app/circuit.va`，把 `environment/public` 放到 `/app/testbench`。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。这是评分出口适配，不改写历史校准结果，也不给尚未执行的尝试补 0。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “After a `tr` transition finishes, every point in the following hold interval is checked.” 改为 “Every saved point is scored, for all four outputs, except points less than `1.15*tr` after t = 0 or after a rising `clk` crossing that changes an output target.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `1.15*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）；本题 `tr` 取自 `tests/v2_spec.py:14`（默认 120 ps）。
  - 余量：到达期限仍是原句 “After the `tr` transition, the outputs hold until the next rising edge.”；在 `tr` 与 `1.15*tr` 之间到达的输出不区分，这是用户已接受的余量。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_transition_1p3tr`；应通过（窗内对照）：`inwindow_transition_1p1tr`。
  - 合成控制（未仿真）：底波形为旧版 first30-r1 的参考波形，在内存中推迟输出列后直接调用本题 checker。`late-shift-0.3tr` 2 个私有用例都被拒；`inwindow-shift-0.1tr` 2 个私有用例都通过；未平移的底波形 2/2 通过。共 6/6 符合预期。
  - 旧版 EVAS 0.8.7：`late_transition_1p3tr` 2 个私有用例都被拒；`inwindow_transition_1p1tr` 2 个私有用例都通过。共 4/4 符合 `expected.json`。参考解抽查 2 例（private/contract-base、public/contract-base）都与 first30-r1 一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

### 2026-10-28 补充（tolerance-r1）：用例网表写明容差与输出设置

D1 冻结前总协调定的第 (ii) 类题目修正：用例网表显式写出容差和输出设置。只改台架的容差和输出设置；激励、合同（`instruction.md`）、checker、参考解、候选、`v2_runtime.py` 与 `adc_linearity.py` 都不动。未仿真。

- 改了哪些行：`environment/public/visible_test.scs`、`environment/starter/testbench/cases.json` 1 例、`environment/starter/testbench/visible_test.scs`、`tests/cases.json` 2 例，共 5 个网表。每个网表只改 options 与 tran 两条语句；激励、include、实例与 save 行逐字节不变。
  - 在 `tran` 语句前新加一行 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`。
  - `tran` 语句末尾补 `errpreset=moderate strobeoutput=strobeonly`；`stop`、`maxstep`、`strobeperiod` 不改。
- 取值与来源：标准线 `D1-TOLERANCES.md`（sha256 `55fa799a…`）与 `D1-TOLERANCES.json`（`fbbbebbb…`）；写法按标准线网表约定清单 `LIST.md` 第 3 版（`6a6b17cd…`）。
  - reltol 1e-6、vabstol 1e-8 V、iabstol 1e-12 A，D1 的 12 题一样。本题 checker 的判据：电压 2 mV；标准线按局部截断误差估计，这组容差下的解算误差应远小于最严的判据；这只是选值的依据，不是已证明的全局误差上界，实际误差、事件时刻和耗时待 Spectre 校准验证（D1 容差复审 TOL-01）。iabstol 取 Spectre 缺省 1e-12，本题 save 的都是电压。
  - `errpreset=moderate` 是 Spectre 的缺省。本题校准网表没写 errpreset，按缺省就是 moderate；现在写明，行为不变（运行环境当时是否另设，见下面“历史身份”一条）。
  - `strobeoutput=strobeonly` 也是 Spectre 的缺省：做 strobe 时只输出 strobe 点。写明以保持校准时的输出行。
  - precision 不写进用例网表，由主控另排一轮放在 Spectre 执行路径里；`src_allbrkpts` 等批次 C。
- 历史身份：10-10 历史作者校准（run `final-a5-cb789-equivalent-20261010T2140Z`）用的 `tests/cases.json`（`ea59ac10…`，在 git `fae1bac2` 中核对）没有写本轮补的设置。当时实际生效的容差未知，可能是 Spectre 缺省，也可能是运行环境的设置。所以改后的结果与历史结果按不同的执行身份对待。本文件前面各段说的网表或公开 `.scs`“未改”“逐字节不变”，只指当时那一轮。
- 旧版 EVAS 0.8.7 开发检查：参考解跑 2 个私有与 1 个公开用例，判决与改前最近一次旧版记录逐项相同（3/3 通过），输出行数与各行数值也相同。旧版日志回显的容差由缺省 reltol=0.001、vabstol=1e-06 变为 1e-06、1e-08。新写的参数没有被拒，也没有警告。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v2-spec-353-ffe-transmitter-3tap/`，D1 的对照作业从那里取原网表。改后 sha256：`environment/public/visible_test.scs` `544792c4…`；`environment/starter/testbench/cases.json` `949f5203…`；`environment/starter/testbench/visible_test.scs` `d1fcfc53…`；`tests/cases.json` `11c5451d…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。`testbench/check.py` 与 `testbench/README.md` 由主控接入，本文件未执行该入口。

端口顺序在 instruction 中写明。原文没有单独的 input/output 清单。方向来自同一题面的采样与 drive 句子。结果 JSON 标明这一点，不从 gold 补端口。

私有 checker 在目标变化后跳过 `1.15*tr`。迁移时（2026-10-27）公开合同是 `tr` 结束后检查保持区间，当时不采用 1.15。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 `1.15*tr` 评分起点，到达期限仍是 `tr`。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`data`、`clk`、`rst`、`pre_1`、`pre_0`、`post_1`、`post_0`，门限 `vth`（缺省 0.45 V，用例不覆盖）。
- 激励核对（未仿真）：题包全部 5 份网表（`tests/cases.json` 2 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 clk，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`data`, `clk`, `rst`, `pre_1`, `pre_0`, `post_1`, and `post_0` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
