# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 375-nonoverlap-clock-generator。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 375。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-375-nonoverlap-clock-generator/instruction.md)（blob `9aa511a1558f67e1f9379c9e6be4fd0a865f533e`），原来源页为 [HEAD c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-375-nonoverlap-clock-generator/SOURCE.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。EVAS 行为不是本题验收真值。

同源关系：首批 v2-spec-307（开关电容积分相位对）职责不同。R01 两题无同源。规划池 C312-S1 的主来源是 v4:375（历史修订），同为按规格建模；它计划补的“死区内反向请求替换还是忽略、tick 对齐及短周期域”本题“全局tick的准确死区与取消”一节已写明，责任实质相同，存在重复计数风险。规划池登记由主控处理，本题保留原身份。

## Modeling choices

原题面英文段与中文专节“全局tick的准确死区与取消”合并写入 Spec：第 dead_ticks 个全局 `k*tick` 事件启用新相位，死区在 `((dead_ticks-1)*tick, dead_ticks*tick]`，边沿不与 tick 同刻，新边沿取消旧请求并重新计数，rst 上升或 enable 下降立即清除（含短于 tick 的脉冲），释放控制不自动请求，`0<tr<=tick/2`，相邻 clk 边沿至少 `dead_ticks*tick+4*tr`，互斥按 `(vdd+vss)/2` 判定并贯穿过渡与保持阶段，默认值满足含等号的范围。没有改数。

端口方向按原题面角色句写入 starter：`clk_in`、`rst`、`enable` 为输入，四个输出为输出。

Harbor 包装把单文件交付改为 `/app/circuit.va`，把 `environment/public` 放到 `/app/testbench`，`visible_test.scs` 的 include 由 `/work/dut.va` 改为 `/app/circuit.va`。公开用例取原私有 `tests/cases.json` 的第一个用例 `contract-base`，`contract-stretched-input` 与 `sub-tick-cancel-and-next-edge-restart` 只在终评使用。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。评分起点后来按决定单第 12 项乙方案改为 115 ps（f01-r2 准备；用户 2026-10-29 选乙，定稿），见文末一节；本节的 230 ps 是改前的说法。

- 题面：评分段原句 “After a `tr` transition finishes, every point in the following hold interval is checked.” 改为 “Each output reaches its new value within `tr` after the event that changes it. Every saved point is scored, for all four outputs, except points less than 230 ps after t = 0 or after an event that changes an output target: a `clk_in` crossing in either direction while enabled and not in reset, the `dead_ticks`-th tick after it, at which the requested phase starts, or a clear by a rising `rst` or a falling `enable`. The mutual-exclusion check applies at every saved point, including the unscored ones.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `1.15*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）。目标改变的事件见 `:99-104`（使能且不在复位时的 `clk_in` 穿越、第 `dead_ticks` 个 tick、清零）；互斥检查 `:184-187` 在跳过之前、每个保存点都做。本题 `tr` 取 checker 默认 200 ps（`:11` 的默认链，用例不给参数），所以评分起点是 230 ps；题面 `tr` 默认 100 ps，checker 不读 DUT 的 `tr`。
  - 余量：到达期限仍是 `tr`（默认 100 ps）；在 `tr` 与 230 ps 之间到达的不区分，这是用户已接受的余量。本题余量（默认 130 ps）比按 `1.15*tr` 算的大，因为 checker 的 200 ps 与题面的 `tr` 不同，已交主控。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡时间。应被拒：`late_transition_2p6tr`；应通过（窗内对照）：`inwindow_transition_2p2tr`。
  - 合成控制（未仿真）：底波形为 fix-a-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中推迟输出列后直接调用本题 checker。`late-shift-160ps` 3 个私有用例都被拒；`inwindow-shift-120ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 9/9 符合预期。
  - 旧版 EVAS 0.8.7：`late_transition_2p6tr` 3 个私有用例都被拒；`inwindow_transition_2p2tr` 3 个私有用例都通过。有预期的 6 例中 6 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/contract-base、public/contract-base）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。**未仿真**：没有运行 Spectre。EVAS 02dee32b 与旧版 EVAS 0.8.7 的阶段结果只是开发证据（待 Spectre 复跑），记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-spec-375-nonoverlap-clock-generator/checks.json`（不入库）。阶段结果：EVAS 02dee32b 在 stage c 报 `kernel.unsupported_history_input`（同 308 的消息），没有提交步，私有 3 个用例与公开台架相同；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 3/3、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

迁移时 `sub-tick-cancel-and-next-edge-restart` 用例中 clk 上升与 enable 下降、上升分别相距约 125 ps、165 ps，小于通用条款“独立控制边沿至少 2*tr=200 ps”，题面也没有说明短脉冲与 clk 的间距是否豁免。2026-10-28 修正（fix-a-r1，F05）把这个 40 ps 的 enable 低脉冲移到约 9.855–9.895 ns：距 clk 上升 325/365 ps，仍在两个 tick（9.8、10.0 ns）之间、短于一个 tick，仍在第 dead_ticks 个 tick 之前取消待定请求。题面照 checker 现有处理写明：同一 `rst` 或 `enable` 清除脉冲的两沿彼此不算独立边沿，脉冲可窄于 `2*tr`、短于一个 tick（checker 在前沿清除，后沿只是释放）；脉冲各沿与 `clk_in` 边沿仍至少 `2*tr`。checker 与参考解未改。

私有 checker 在目标变化后跳过 `1.15*tr`（`tr` 取 checker 默认 200 ps，即 230 ps）。迁移时（2026-10-27）公开合同是 `tr` 结束后检查保持区间，当时不采用 1.15。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 230 ps 评分起点与互斥检查逐点进行，到达期限仍是 `tr`。（f01-r2 起用例 `params` 写 `tr=1e-10`，评分起点为 115 ps；用户 2026-10-29 选乙，见文末。）

fix-a-r1 复跑（2026-10-28，记录在本地 `runs/t3-batch2-20261027/fix-a-r1/`，不入库）：旧版 EVAS 0.8.7 上参考解私有 3/3、公开 1/1 通过，只用网格行复判无变化；只在 tick 与 clk 边沿处理清除（无异步清除）的错误模型在改后的短脉冲用例被拒。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。

## 决定单第 12 项：评分起点按乙（f01-r2 准备，用户 2026-10-29 选乙）

**用户 2026-10-29 选乙（决定单第 12 项），定稿。** 总协调推荐乙；复审认为现状不算判分缺陷，交用户二选一。乙收紧验收范围：到达时刻在 115 ps 之后、230 ps 之前的输出原来通过，现在被拒，不是单纯的记录修正。本节末的退回办法是为用户选甲准备的，现在不再执行。

依据增量复审 `runs/t3-batch2-20261027/review-f01-r5/astra-review.json` 对主控打算的意见（`coordinator_opinions.task_375`）与决定单第 12 项。**未仿真**：没有运行 Spectre。旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑；合成控制是已存旧版参考波形在内存中变换后由本题 checker 判定，也未仿真。记录在本地 `runs/t3-batch2-20261027/f01-r2/`（不入库），其中 `disposition.md` 列出命令、退出码与改前改后哈希。

- 依据：checker 不读题面的 `tr`。用例不带 `params` 时，`tests/v2_spec.py:11` 的缺省链给 `tr` = 200 ps，评分起点 `1.15*tr` = 230 ps；题面 `tr` 缺省是 100 ps。130 ps 的余量不是有意定的，别的题是 `0.15*tr`。
- 改动：
  - 私有 3 例与公开 1 例（`tests/cases.json`、`environment/starter/testbench/cases.json`）的 `params` 由 `{}` 改为 `{"tr": 1e-10}`；激励、网表与 `resolution` 都不动。四个用例的实例都用缺省 `tr`（100 ps），`params` 与实例一致。
  - 题面第 28 行 “less than 230 ps after” 改为 “less than 115 ps after”。题面其他地方与 `environment/starter/testbench/README.md` 都没有写 230 ps 或 200 ps 缺省链（逐处核对）。
  - checker 代码不动。
  - 校准件：`late_transition_2p6tr`（260 ps 到值）保留；新加迟到负例 `late_transition_1p3tr`（130 ps）；正确候选由 `inwindow_transition_2p2tr`（220 ps，新起点下会被拒）换成 `inwindow_transition_1p1tr`（110 ps）。窗内对照离评分起点 5 ps，`expected.json` 的 `conditions` 写明它假定后端的事件与过渡时刻偏差小于 5 ps。
- 时间步检查照实核对，无出入：`tests/v2_spec.py:27` 用 `case.get('resolution', tr/4)*1.05`；四个用例都显式写 `resolution=2e-12`，上限 2.1 ps，与 `params` 无关；网表 `maxstep=2p strobeperiod=2p`。题面“时间步不粗于最短输出过渡的四分之一”在 `tr` = 100 ps 时是 25 ps，2 ps 网格满足。
- 规则：用例 `params` 的 `tr` 必须等于实例的有效 `tr`。题面的 115 ps 对应缺省 `tr`；以后若有用例覆盖实例的 `tr`，题面这一句要改写为 `1.15*tr`。
- 验证（未仿真）：
  - 合成控制（全部行与只用网格行各一遍）：旧版参考波形推迟后，110 ps 到值在改前改后都通过；130 ps 与 220 ps 改前通过、改后被拒；260 ps 改前改后都被拒；参考解改前改后都通过。私有 3 例与公开 1 例共 80 项，全部符合预期。
  - 旧版 EVAS 0.8.7：参考解与 `inwindow_transition_1p1tr` 在四个用例都通过，`late_transition_1p3tr`、`late_transition_2p6tr` 与已移除的 `inwindow_transition_2p2tr` 在四个用例都被拒；同一批波形按改前的 `params` 重判，`late_transition_1p3tr` 与 `inwindow_transition_2p2tr` 都通过，其余不变。全部行与只用网格行判决相同。旧版开发证据，待 Spectre 复跑。引用这些通过之前核对了零点处理：参考解的 `cross()` 读 0 与 0.9 V 之间的控制信号，不在门限上停留或折返，旧版的通过不受这一处理掩盖。
  - 互斥检查照常逐点进行，全部候选都没有 `phase_overlap`。
  - 平局（TIE-RULE 现行版 `a4cf0e73…`，含第 4 种情形）：激励未改，不同来源事件最近 5 ps（stretched 例 `clk_in` 与 tick）；各候选斜坡终点离同一输出的下一次目标改变至少 65 ps，没有被改写目标的斜坡；timer 体没有时间比较。无第 (ii) 类平局。
- 退回办法（为用户选甲准备，用户 2026-10-29 选乙，不再执行，只留作记录）：把 `runs/t3-batch2-20261027/f01-r2/orig/v2-spec-375-nonoverlap-clock-generator/` 下的 7 个原件逐字节拷回题包同名位置（`SOURCE.md`、`instruction.md`、`tests/cases.json`、`environment/starter/testbench/cases.json` 与 `tests/calibration/` 三件），按 `runs/t3-batch2-20261027/f01-r2/orig.sha256` 核对。脚本 `runs/t3-batch2-20261027/f01-r2/scripts/rollback_375.py` 先核对题包现状等于本轮改后的哈希，再拷回并核对；author-r2 改了本页与校准件，题包现状已不等于 f01-r2 改后的哈希，按脚本代码，它只会报告不符、不拷回（author-r2 没有运行它）。
- Spectre 待办：按 115 ps 起点做参考与候选校准。（author-r2：已由 B2PC 预校准做完，已核收，见下一节。）

## author-r2 定稿（2026-10-29）

依据：决定单第 12 项，用户 2026-10-29 选乙（`runs/t3-p0-pilot-20261027/pending-user-choices.md` 末尾“第二批”一节）；主控 brief `runs/t3-batch2-20261027/briefs/b2-author-r2.md` 第 3 项；B2PC 预校准的核收结果（Benchmark 的预读记录（本地 runs/ 下，未公开） 第 2 节第 3 条、第 4.1 节）。记录在本地运行目录 `runs/t3-batch2-20261027/author-r2/`（不入库）。**未仿真**：本轮没有运行 Spectre、EVAS 或模型。

- 改了什么：本页与 `tests/calibration/README.md` 去掉“待用户确认”，写明用户选乙；`tests/calibration/expected.json` 的 `semantics` 改为“用户 2026-10-29 选乙”，`conditions` 补 Spectre 读数。用例、checker、参考解、题面与 `mutants.py` 都不改。`rollback_375.py` 不再执行。
- Spectre 读数（都已核收）：甲边是 f01-r2 之前的字节（用例 `params` 为空，评分起点 230 ps），乙边是题包现行字节（`params` 为 `{"tr": 1e-10}`，评分起点 115 ps）；两边网表与参考解逐字节相同，只差用例 `params`。每格是“通过数 / 用例数”，用例为私有 3 例加公开 1 例。

  | 候选 | 甲 | 乙 |
  | --- | --- | --- |
  | 参考解 | 4/4 通过 | 4/4 通过（缺省容差对照也 4/4 通过） |
  | 110 ps（`inwindow_transition_1p1tr`） | 4/4 通过 | 4/4 通过 |
  | 130 ps（`late_transition_1p3tr`） | 4/4 通过 | 0/4，被拒 |
  | 220 ps（`inwindow_transition_2p2tr`） | 4/4 通过 | 0/4，被拒 |
  | 260 ps（`late_transition_2p6tr`） | 0/4，被拒 | 0/4，被拒 |

  - 参考解在 must-01（执行身份 `spectre-B2PC-must-01-v1（结果包 sha256 fffd959be8465585…）`）；乙边私有用例上的 260、130、110 ps 与甲边私有用例上的 260、220 ps 在 rec-02（`spectre-B2PC-rec-02-v1（结果包 sha256 a629d67a6220fbb5…）`）；两边的公开用例、甲边借来的 130、110 ps 与乙边的 220 ps 分界项在 opt-01（`spectre-B2PC-opt-01-v1（结果包 sha256 3e80d95b2f27000a…）`）。
  - 乙边：参考解 4 个用例都通过；110 ps 通过，130 ps、260 ps 被拒；opt-01 的 220 ps 在乙边被拒、在甲边通过。两边判决不同的只有 130 ps 与 220 ps：乙的分界在 110–130 ps 之间，甲的在 220–260 ps 之间。全部判决与 `expected.json`、f01-r2 的旧版开发证据相同。
  - 窗内对照 110 ps 离评分起点 5 ps，`conditions` 写的前提（后端的事件与过渡时刻偏差小于 5 ps）在这些作业上成立：私有三例与公开用例都通过。
- Spectre 待办：本题不需要新的 Spectre 作业。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`clk_in`、`rst`、`enable`，门限 `vth`（缺省 0.45 V，用例不覆盖）。
- 激励核对（未仿真）：题包全部 6 份网表（`tests/cases.json` 3 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 clk_in，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`clk_in`, `rst`, and `enable` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
