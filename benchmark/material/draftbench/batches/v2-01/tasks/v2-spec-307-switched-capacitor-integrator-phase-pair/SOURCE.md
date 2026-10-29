# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 307-switched-capacitor-integrator-phase-pair。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 307。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/instruction.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`，科学来源 `a5c12a1a01a47e40a7f37b611e55836e59db65cf`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。

公开合同现为 system-interfaces-v2，固定 helper 接口、职责与替身消费。每题六个条件，包括两个组件条件和两个顶层消费条件。旧的两条件校准与模型结果只覆盖旧身份，均保留，不覆盖或升级其成绩。迁移前 SOURCE 还写新版本的 reference、alternative、语义与架构负例 Spectre 作者校准已完成，新 prompt 模型试做尚未完成。这些句子都绑定旧包身份，不认证本次 `/app` 包。当时仅为 Spectre 扩展集候选，未获发布资格。历史来源与旧运行仍保留原版本。EVAS 行为不是本题验收真值。

## Modeling choices

迁移前系统合同给出 helper 端口顺序、`phi1` 保存实际 `vin`、一次 `phi1` 只供一次 `phi2`、增量 `k_int*(sample_node-vcm)`、`phase_metric` 初值与复位值为 `vcm`，以及 producer `0.62 V` 和 consumer `0.63/0.22/0 V`。正常两相间隔至少 `4*tr`。这些数值规则已进入现行 Spec，没有改数。旧成绩不能作为本版本通过证据，这句留在本文件。六个条件仍是现行验收。

重叠按另一相在交点处高于 `vth` 理解，因为控制门限就是已声明的 `vth`。这不是新门限。

实现组织自由，采样与积分职责和替身消费不能收成只看顶层最终码。Harbor 包装把顶层文件改为 `/app/circuit.va`，两个 helper 保持原文件名并平铺在 `/app`。公开激励进入 `/app/testbench`。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。这是评分出口适配，不改写历史校准结果，也不给尚未执行的尝试补 0。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “After a `tr` transition finishes, every point in the following hold interval is checked.” 改为 “Each public output reaches its new value within `tr` after the event that changes it. Every saved point is scored, for all three public outputs, except points less than `1.15*tr` after t = 0 or after an event that changes the target of any public output: a rising `phi2` crossing, or a clear by `rst` or `enable`. In the consumer-substitute condition, every saved point from t = 0 is scored against the substitute voltages.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `1.15*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）；本题 `tr` 取自 `tests/v2_spec.py:11`（本题用例不给 `tr`，默认 200 ps）。消费者替身用例由 `tests/v2_structure.py:19-34` 判定，每个保存点都评分。
  - 余量：到达期限仍是 `tr`；在 `tr` 与 `1.15*tr` 之间到达的输出不区分，这是用户已接受的余量。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`tests/v2_structure.py` 与其公开副本、`cases.json`、参考解、starter 模型、公开激励和其余共用文件逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡或延迟。应被拒：`late_integrator_transition_1p3tr`；应通过（窗内对照）：`inwindow_integrator_transition_1p1tr`。
  - 合成控制（未仿真）：底波形为旧版 first30-r1 的参考波形，在内存中推迟输出列后直接调用本题 checker。`late-shift-0.3tr` 在 contract-base、contract-stretched-input、architecture-component-producer、architecture-component-consumer、architecture-producer 被拒，在 architecture-consumer 通过；`inwindow-shift-0.1tr` 6 个私有用例都通过；未平移的底波形 6/6 通过。共 18/18 符合预期。
  - 旧版 EVAS 0.8.7：`late_integrator_transition_1p3tr` 在 contract-base、contract-stretched-input、architecture-component-consumer、architecture-producer 被拒，在 architecture-component-producer、architecture-consumer 通过；`inwindow_integrator_transition_1p1tr` 6 个私有用例都通过。共 12/12 符合 `expected.json`。参考解抽查 2 例（private/contract-base、public/contract-base）都与 first30-r1 一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-harbor30-20261027/f01-r1/disposition.md（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）。

### 2026-10-28 补充（tolerance-r1）：用例网表写明容差与输出设置

D1 冻结前总协调定的第 (ii) 类题目修正：用例网表显式写出容差和输出设置。只改台架的容差和输出设置；激励、合同（`instruction.md`）、checker、参考解、候选、`v2_runtime.py` 与 `adc_linearity.py` 都不动。未仿真。

- 改了哪些行：`environment/public/visible_test.scs`、`environment/starter/testbench/cases.json` 1 例、`environment/starter/testbench/visible_test.scs`、`tests/cases.json` 6 例，共 9 个网表。每个网表只改 options 与 tran 两条语句；激励、include、实例与 save 行逐字节不变。
  - 在 `tran` 语句前新加一行 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`。
  - `tran` 语句末尾补 `errpreset=moderate strobeoutput=strobeonly`；`stop`、`maxstep`、`strobeperiod` 不改。
- 取值与来源：标准线 `D1-TOLERANCES.md`（sha256 `55fa799a…`）与 `D1-TOLERANCES.json`（`fbbbebbb…`）；写法按标准线网表约定清单 `LIST.md` 第 3 版（`6a6b17cd…`）。
  - reltol 1e-6、vabstol 1e-8 V、iabstol 1e-12 A，D1 的 12 题一样。本题 checker 的判据：电压 2 mV；标准线按局部截断误差估计，这组容差下的解算误差应远小于最严的判据；这只是选值的依据，不是已证明的全局误差上界，实际误差、事件时刻和耗时待 Spectre 校准验证（D1 容差复审 TOL-01）。iabstol 取 Spectre 缺省 1e-12，本题 save 的都是电压。
  - `errpreset=moderate` 是 Spectre 的缺省。本题校准网表没写 errpreset，按缺省就是 moderate；现在写明，行为不变（运行环境当时是否另设，见下面“历史身份”一条）。
  - `strobeoutput=strobeonly` 也是 Spectre 的缺省：做 strobe 时只输出 strobe 点。写明以保持校准时的输出行。
  - precision 不写进用例网表，由主控另排一轮放在 Spectre 执行路径里；`src_allbrkpts` 等批次 C。
- 历史身份：10-10 历史作者校准（run `final-a5-cb789-equivalent-20261010T2140Z`）用的 `tests/cases.json`（`eb26fe8b…`，在 git `fae1bac2` 中核对）没有写本轮补的设置。当时实际生效的容差未知，可能是 Spectre 缺省，也可能是运行环境的设置。所以改后的结果与历史结果按不同的执行身份对待。本文件前面各段说的网表或公开 `.scs`“未改”“逐字节不变”，只指当时那一轮。
- 旧版 EVAS 0.8.7 开发检查：参考解跑 6 个私有与 1 个公开用例，判决与改前最近一次旧版记录逐项相同（7/7 通过），输出行数与各行数值也相同。旧版日志回显的容差由缺省 reltol=0.001、vabstol=1e-06 变为 1e-06、1e-08。新写的参数没有被拒，也没有警告。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 改前原文件逐字节存于 `runs/t3-spectre-batchD-20261028/tolerance-r1/orig/v2-spec-307-switched-capacitor-integrator-phase-pair/`，D1 的对照作业从那里取原网表。改后 sha256：`environment/public/visible_test.scs` `e397c2af…`；`environment/starter/testbench/cases.json` `470e9da3…`；`environment/starter/testbench/visible_test.scs` `e6e87b29…`；`tests/cases.json` `d2614dbd…`。
- 证据目录：runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md（`runs/t3-spectre-batchD-20261028/tolerance-r1/disposition.md`）。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。`testbench/check.py` 与 `testbench/README.md` 由主控接入，本文件未执行该入口。

顶层端口顺序在 instruction 中写明，但顶层那一句本身没有 input/output 两个词。方向来自后文“采样输出接到积分输入，积分驱动三个公开输出”。结果 JSON 按该段填写，并记下顶层首句没有方向词。不从 gold 补端口。

`phase_metric` 的初值写了。`vout` 和 `valid` 的初值写在复位或禁用时。若上电时已经使能且未复位，公开合同没有另一句上电积分值。私有 checker 在 t=0 把 `vout` 放在 `vcm`、`valid` 放在 `vss`。本次不把这个未复位上电状态补成新要求。

私有 checker 使用通用的 `1.15*tr` 跳过。公开输出过渡是 `tr`，内部采样节点要在正常 `phi2` 前完成，两相间隔至少 `4*tr`。迁移时（2026-10-27）不把 1.15 写成新容差。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 `1.15*tr` 评分起点，到达期限仍是 `tr`。

独立Astra A-r1保留的科学未决：原题面要求积分state累加并夹位vout，没有明确越轨时是否把夹位结果反馈到递推状态。现题“clamp the result”也不足以区分。越轨后反向增量会使状态夹位与仅输出夹位产生不同解除饱和结果。旧checker实现状态夹位不构成选定它的独立科学依据；当轮不据此冻结anti-windup条件。2026-10-27用户已选定状态夹位，见决定卡末段。该差异只作纸面推导，未运行VA。审查与算术例在本轮runs/t3-harbor30-20261027/astra-review-a-r1.json及其307-saturation-interpretations.json。

### 评分合同决定卡

2026-10-27补充；同日用户确认采用下述状态夹位建议，落实见本卡末段。原合同已定的是复位回到`vcm`、每个有效相对只消费一次样本、增量`k_int*(sample_node-vcm)`及输出不越电源轨。它没有明确内部积分状态是否也夹位，不能把现有checker选择当成原出处已经裁决。

复用A-r1的最小纸面例：先复位至0.45V，随后6个合法相对都采样0.9V，最后一个采样0V；取`k_int=0.2`、电源轨0和0.9V。第6对后两种输出都为0.9V。第7对的负增量到来时，状态夹位得到0.81V，仅夹位输出仍为0.9V。差90mV，超过既有2mV误差限。例子先复位，避免把另一个未定的上电状态混入本次选择；没有VA运行。

建议采用状态夹位：`q_next=clamp(q+k_int*(sample_node-vcm),vss,vdd)`，`vout=q_next`。这把任务限定为有界电压状态的两相积分器；饱和后的反向样本立即作用于可观察状态，不新增隐藏的过饱和记忆责任。这是设计建议，不是唯一物理模型。另一选择是`q_next=q+increment`，只令`vout=clamp(q_next,...)`，并把解除饱和前的累计记忆明确写成责任。

用户需选择上述两种行为之一。采用建议后，Spec须明确递推式并消除“clamp the result”的歧义，现有checker与参考中的状态夹位路径可保留，但仍需对这个反例及组件/顶层消费条件校准。若选仅夹位输出，则积分helper参考、公私checker的307递推和相应错版期望都受影响。两种选择都保持三个模块职责、替身消费、原电压和时序阈值；不修改旧运行记录。

#### 决定与落实

2026-10-27用户确认状态夹位：每个合法相对令`q_next=clamp(q+k_int*(sample_node-vcm),vss,vdd)`，`vout`输出该状态；不保留超出电源轨的累计量，饱和后的反向样本当拍就让`vout`离开电源轨。现行Spec已写明递推式，并把复位写成积分状态回到`vcm`，与原合同“复位回到`vcm`”一致。

该选择不代决未复位、已使能时的上电积分状态，上文Open items里的这一项保留。

参考解[integrator_state_cell.va](solution/integrator_state_cell.va)与公私checker（[tests/v2_spec.py](tests/v2_spec.py)与公开副本，SHA256 `6c3187d1c824a18de7264e8d98e7cdd4eafa0d78b91e73ba00fbd625b020d2ac`）原本就按状态夹位递推，这次没有改动。合成控制复用上面的七相对例：状态夹位轨迹第7对后为0.81V，判为通过；仅夹位输出的轨迹停在0.90V，判为拒绝。结果在`runs/t3-harbor30-20261027/grading-adoption/`。这是Python判据检查，没有运行VA，组件与顶层替身条件的Spectre校准仍待完成。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`phi1`、`phi2`、`rst`、`enable`，门限 `vth`（缺省 0.45 V，用例不覆盖）。`vin` 是模拟输入；`sample_node`、`sample_valid` 是模块之间的信号，在全部网表里都由模块产生，电压源只驱动 `vin` 与四个控制；都不在此列。
- 激励核对（未仿真）：题包全部 9 份网表（`tests/cases.json` 6 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 enable，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`phi1`, `phi2`, `rst`, and `enable` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
