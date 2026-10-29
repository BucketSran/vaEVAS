# 来源与迁移记录

2026-10-28 第二批用户决定后迁移（decisions-r1）。改动：Harbor 包装、英文合同、参考解起点比较的半周期裕量（用户批准）、`tests/calibration/` 三件和本页；那一轮没有改 checker、私有与公开用例和固定放大器。同日 fix-dec-r1 把公开三例的 `begin_round` 脉冲后移 0.35 ns，并在题面写明 700 ps 区间的输入域，checker、私有用例、参考解与固定放大器仍未改，见文末“fix-dec-r1 修正”一节。2026-10-29 author-r2 把校准件 `strict_start_no_margin` 改为随后端而定的探针，参考解、checker、用例与题面都未改，见文末“author-r2 修正”一节。**未仿真**：没有运行 Spectre，也没有运行模型；EVAS 02dee32b 与旧版 EVAS 0.8.7 的结果只是开发证据，待 Spectre 复跑，记录在本地运行目录 `runs/t3-batch2-20261027/decisions-r1/v2-test-online-gain/checks.json`（不入库）。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-online-gain/instruction.md)，blob `75805206f300e66fc95e5d1fe6a16d45b6c9c5d4`，提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-test-online-gain/SOURCE.md)，blob `19150051b99ca5d49e3bc7f26fd38f96391032bf`。

来源 `v4-093+v4-038`。本题保留来源的工程目标，并保留后来加上的固定只读 DUT、独立实际波形 checker 和窗口协议。原始参考资产仍在 `benchmark/material/historyref/`。固定 DUT 现为 `/app/testbench/dut/amplifier.va`，模块 `programmable_gain_amplifier`，与原 `environment/public/dut/amplifier.va` 及各用例内联支持文件逐字节相同。公开用例现为 `/app/testbench/cases.json`（原 `environment/public/cases.json` 原字节）。候选壳现为 `/app/circuit.va`，只留端口与原 starter 的 input/output/inout 角色；参数默认值改写在题面。

已保留的合同：模块 `gain_estimator(VDD,VSS,vinp,vinn,voutp,voutn,gain_out,valid,begin_round)`；不得驱动观测输入；1 ns 全局整倍采样实际输入与输出差分，自 `start_time`=20 ns 起累计极值；输入跨度严格大于 0.02 V 时 `valid` 为供电高、`gain_out=(VDD-VSS)*输出跨度/输入跨度/gain_scale`，`gain_scale`=10；小跨度时 `valid` 低、`gain_out`=0；`begin_round` 穿过 0.5 V 上升清除极值、报告与 `valid`，新轮重新收集；不得把放大器内部增益或 clipping 当作测量结果，不得以独立信号源替代输出；`tedge`=200 ps；误差 2 mV；放大器 `gain_low` 0.2–1.2、`gain_high` 1–2.6，输入共模 0.45 V，正弦幅度 0.001–0.07 V、频率 15–25 MHz；可改变增益切换和 `begin_round` 时刻；计时参数、跨度条件与 `gain_scale` 固定；DUT 不达标时报告正确仍可通过。

同源关系：首批 30 题中 v2-test-gain-settling（case-0018+v4-038+v4-370）同用 v4-038 放大器、同为测试表征，但测量责任不同（正弦在线跨度增益与阶跃静态增益、有限建立），不重复。R01 两题无同源。规划池 C247 为“保留组件或变体”，没有候选；与第二批 v2-spec-038（规格建模）动作不同。

## 建模选择

这是测试表征，不是重建放大器。仪表接口壳只留端口；参数 `sample_period`、`start_time`、`gain_scale`、`min_input_span`、`tedge` 由求解者按 Spec 声明（用例在实例上传入同值，不声明会无法运行）。端口方向取自原 starter：`VDD`、`VSS` 为 inout，`vinp`、`vinn`、`voutp`、`voutn`、`begin_round` 为输入，`gain_out`、`valid` 为输出。题面写明 `VDD` 为 0.9 V、`VSS` 接地，这是全部用例的事实；checker 按用例字段 `vhigh`=0.9 判 `valid` 高电平。

用户已确认（2026-10-28）。总协调约 02:40Z 转达用户答复“全部按推荐”。推荐原文（`runs/t3-batch2-20261027/triage-disposition.json` 的 wait_for_user）：“state the inclusive start-sample rule in the contract (as the checker does) and give the reference a half-period margin”。主控 brief：“合同写明 start_time 时刻的样本计入（与 checker 的 `i*period >= start` 一致）”；“参考解加半个采样周期的裕量，用户已批准改参考解。例如把 `$abstime >= start_time` 改为 `$abstime >= start_time - 0.5*sample_period`，写法自定，在 SOURCE 写明”；“350 ps guard 按下面的 F01 写进合同”。

落实的改动：

- 合同：“Samples are taken at the global times `k*sample_period`, `k = 0, 1, ...`, that are at or after `start_time`. The sample at `start_time` itself counts, so with the defaults the first sample is at 20 ns.” 与 checker 一致（`tests/v2_testing.py:161`，`i*period>=start`）。
- 参考解：`solution/circuit.va` 第 43–44 行（`solution/dut.va` 同改，两份逐字节相同）由 `if ($abstime >= start_time) begin` 改为 `if ($abstime >= start_time - 0.5*sample_period) begin`，上一行加注释“Half a sample period of margin: the sample at start_time itself counts.”。19 ns 的 timer 仍被排除，20 ns 的 timer 无论浮点值略小还是相等都计入。改前字节（sha256 `f67567f9…ae26`）保留为 `strict_start_no_margin`：decisions-r1 起作校准负例，author-r2 起改为随后端而定的探针（见文末）。

F01（评分起点）按用户 2026-10-28 的决定写明：checker 实际的观察起点，checker 不动。新句子：“The timing guard is 350 ps, and the voltage error limit is 2 mV. The timing guard applies around these events: every sample instant `k*sample_period` at or after `start_time`, whether or not the report changes there, and every rising crossing of `begin_round` through 0.5 V. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 700 ps is not scored. In every longer interval, each output is scored at every saved point more than 350 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.” 位置 `tests/v2_testing.py:58-74`（`pieces()`：`end-t<=2*guard` 跳过，`(t+guard, end-guard)` 内的保存点与中点评分），事件表 `:161-162`（采样时刻与 `begin_round` 上升交点），guard 来自用例字段 `guard`=3.5e-10。原题面只写“事件后 350 ps 允许平滑”，没有写事件之前的 350 ps 与 700 ps 整段不评分。校准三件加了迟到负例 `late_report_delay_370ps`（事件后 guard+20 ps 才开始变化）与窗内对照 `inwindow_report_delay_100ps`（300 ps 到达）；提前负例是合成波形（事件前 370 ps 开始变化被拒；事件前 330 ps 开始被接受，这是 guard 覆盖事件之前、用户已接受的余量）。区间中点总是评分，事件后 350–570 ps 内至少还有 2 个保存行（`maxstep` 100 ps）。

decisions-r1 把题面写的 `begin_round` 与采样时刻的最小间隔改为只对终评用例声明（fix-dec-r1 已恢复为公开与终评共同的承诺，见文末）：“In the final-evaluation cases, every rising `begin_round` crossing is at least 200 ps away from every global sample instant.” 原题面把这句放在“公开自测与终评范围”下，但公开三例的交点在 104.05 ns，距 104 ns 采样点只有 50 ps（见待定项）。私有三例的交点在 97.4 ns，距采样点 400 ps。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。历史原句“工具链故障单独诊断，不作为候选零分”保留在本页，不解释成缺 Spectre 等于语义错误。

## 待定项

`grading` 和 `runtime` 待定。历史作者校准只作为 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md) 的记录，Run ID `final-a5-cb789-equivalent-20261010T2140Z`，绑定旧 `/work` 题包与改前参考解，不认证本次 `/app` 包。测试表征索引见 [testing README](../../../../../../../experiments/benchmark_v2/testing_characterization/README.md)。模型试做没有做。固定 Spectre，开源同题等价尚未验证。

疑点（decisions-r1 记录；fix-dec-r1 按主控决定后移公开脉冲，见文末）：公开三例的 `begin_round` 上升交点在 104.05 ns，距 104 ns 采样点 50 ps，小于原题面写的 200 ps。两者相距不足 700 ps，checker 整段不评分，判定无歧义；但公开用例在原合同的公开自测范围之外。本轮没有批准改公开激励，所以只把题面的 200 ps 改为终评用例的声明并记录。可选做法：把公开 `Vbegin` 斜坡后移约 0.35 ns（交点 104.4 ns），或在题面写明公开用例的这一例外。

参考解起点：Spectre 上 20 ns 的 timer 时刻是否小于 `start_time` 取决于浮点值；加裕量后两种情况参考解都计入 20 ns 样本，与 checker 一致。不加裕量的写法（改前参考解）在旧版上丢掉 20 ns 样本，`valid` 晚一个采样周期，私有 `terminal-normal`、`terminal-low-performance-dut` 与对应公开用例被拒。

Spectre 待办：记录 `timer` 在 `start_time` 处的触发时刻与 `transition()` 的待发过渡行为。本题两个报告只在采样时刻或 `begin_round` 交点变化；按旧版参考解波形重算 checker 的期望历史，各例相邻两次期望变化至少相隔 1 ns，大于 `tedge`，用例中没有被打断的过渡。

`start_time` 处的读数（author-r2 补记，已核收）：B2PC 预校准的 must-02（执行身份 `spectre-B2PC-must-02-v1（结果包 sha256 b8b1a0c65f6f4a3e…）`）、rec-02（`spectre-B2PC-rec-02-v1（结果包 sha256 a629d67a6220fbb5…）`）、opt-01（`spectre-B2PC-opt-01-v1（结果包 sha256 3e80d95b2f27000a…）`）三包里本题的 18 个参考解与 `strict_start_no_margin` 作业，PSF 在 19.9 ns 之后的下一个时间点都是 `2.000000000000002e-08` s，比 20 ns（`2e-08`）大约 2e-23 s，20 ns 的样本被计入。`strict_start_no_margin` 与 c485de86 的原参考解逐字节相同，在私有三例、公开三例都通过，所以原参考解在 Spectre 上是可解的；旧版 EVAS 0.8.7 上它丢掉 20 ns 样本、4/6 例被拒，只是旧版的时刻比 `start_time` 小。用户批准的半周期裕量照旧保留：加裕量后，两种浮点情形下参考解都计入 20 ns 样本。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解私有 3 例、公开 3 例都在 stage b 被拒，首个诊断是固定 `amplifier.va:39:9`“ordinary analog if predicates must be affine or input-selected piecewise-affine; nonlinear products and powers are unsupported”（NF-22 同类，固定支持模型，影响所有候选），与分诊一致；参考解改动不在这一步之前。旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 3/3、公开 3/3 通过（分诊时 2/6），只用网格行复判没有变化；4 个校准候选在私有与公开 6 例的判决都与 `tests/calibration/expected.json` 一致。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

## fix-dec-r1 修正（2026-10-28）

依据：Astra 独立审核 `runs/t3-batch2-20261027/review-dec-r1/astra-review.json`（sha256 `22c74f3e…7154`，不入库）的 AR08（P2/Spec）与交接项 DOG-1；主控决定见修正 brief `runs/t3-batch2-20261027/briefs/fix-dec-r1.md` 第 9、10 项。记录在本地运行目录 `runs/t3-batch2-20261027/fix-dec-r1/`（不入库）。**未仿真**：没有运行 Spectre 或模型。

- 700 ps 边界（AR08，主控决定 checker 不动）：`pieces()` 用 `end-t<=2*guard` 判定整段不评分（`tests/v2_testing.py:64`）。名义上恰好 700 ps 的区间在 binary64 下可能算成略大于 700 ps（如 `21*1e-9 - 20.3e-9` = 7.00000000000003e-10 s），于是区间中点被评分，“不长于 700 ps 的区间整段不评分”不能稳定兑现。作者重放：`begin_round` 交点在 20.3 ns、只在 20.4–20.9 ns 加 0.3 V 的波形在 20.65 ns 被拒，不加的对照通过。题面合法输入域的那句改为：“In every case, public and final, every rising `begin_round` crossing is at least 200 ps away from every global sample instant, and no interval is exactly 700 ps long.” 按精确有理数核对全部六例（私有三例与改后的公开三例）：没有恰好 700 ps 的区间，最接近的区间是 600 ps（`begin_round` 交点到下一采样点），其次 400 ps（上一采样点到交点）与 1000 ps（相邻采样点），与 700 ps 至少差 100 ps。
- 同一 `pieces()` 的其他题：首批 4 道测量题与第二批其余测量题用的是同一个 `pieces()`，同类边界由各自的修正轮核验；本轮只查本题。
- 公开脉冲（DOG-1，主控决定）：公开三例 `Vbegin` 的整个脉冲后移 0.35 ns，`wave=[0 0 104n 0 104.1n 1 105n 1 105.1n 0 240n 0]` 改为 `wave=[0 0 104.35n 0 104.45n 1 105.35n 1 105.45n 0 240n 0]`，上升交点由 104.05 ns 移到 104.4 ns，距 104 ns 与 105 ns 采样点 400 ps 和 600 ps，与私有三例的 97.4 ns 相同；脉宽不变。`environment/public/cases.json` 与 `/app/testbench/cases.json` 两份副本同步，仍逐字节相同。题面的 200 ps 恢复为公开与终评共同的承诺（见上一条的原句）。改后公开三例按旧版参考解波形重算的期望历史中，相邻两次期望变化仍至少相隔 1 ns。
- 台架源参数（2026-10-28 新增台架规则：本单新建或修改的台架行，源参数一律显式写出）：改动的 `Vbegin` 行只写 `type` 与 `wave`，未满足，交主控裁决。依赖的 Spectre 缺省（Spectre 21.1.0.509.isr12 `spectre -h vsource` 帮助，本地存档 `runs/evas-pulse-delay-20261017/pulse-help-collected/`，vaEVAS 主工作区，不入库，`vsource-help.log` sha256 `081a82af…93ac`）与同日其他题记录的相同：`dc`、`delay`=0、`edgetype`=linear、`offset`=0、`scale`=1、`stretch`=1（本行 6 点，`allbrkpts` 缺省为 yes）。EVAS 02dee32b 的 PWL 源只接受 `type` 与 `wave`（`evas/src/evas/scs_sources.py:22-30`）。没改到的行不动。
- 开发证据：旧版 EVAS 0.8.7 上参考解私有 3/3、公开 3/3 通过；4 个校准候选在改后的公开三例 12/12 与矩阵一致，只用网格行复判没有变化（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）。EVAS 02dee32b 上公开三例的参考解仍在 stage b 停在固定 `amplifier.va:39:9`（NF-22 同类，与私有例相同），起始模型在 stage a 报只有接口、没有 analog 块，属预期。

## author-r2 修正（2026-10-29）

依据：总协调 2026-10-29 的决定（主控 brief `runs/t3-batch2-20261027/briefs/b2-author-r2.md` 第 1 项）与已核收的 B2PC 预校准结果（`runs/t3-spectre-wave2-20261029/returns-preread-…/b2pc/PREREAD.md` 第 2 节第 2 条）。记录在本地运行目录 `runs/t3-batch2-20261027/author-r2/`（不入库）。**未仿真**：本轮没有运行 Spectre、EVAS 或模型，下面的 Spectre 读数都来自已核收的交回波形。

- 改了什么：校准件 `strict_start_no_margin` 由 wrong 组改为随后端而定的探针，做法照 C260 的 `probe_step_recursion_25p`。`tests/calibration/mutants.py` 的 `candidates()` 另返回 `probe`，主程序把它写到 `probe/`；字节不变，仍与 c485de86 的原参考解逐字节相同（生成器断言 sha256 `f67567f9…ae26`）。`expected.json` 的 `candidates` 不再列它，也不登记必拒、必接受；`conditions` 留一条说明，照实写两个后端的读数。校准 `README.md` 同步。参考解、checker、私有与公开用例、题面都没有改。
- 为什么：它的判定取决于后端给 20 ns timer 的时间点与 `start_time` 的比较。旧版 EVAS 0.8.7 上时间点比 `start_time` 小，它丢掉 20 ns 样本，4/6 例被拒（旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑）；Spectre 21.1 上时间点比 20 ns 大约 2e-23 s，它在私有三例（B2PC rec-02，执行身份 `spectre-B2PC-rec-02-v1（结果包 sha256 a629d67a6220fbb5…）`，已核收）与公开三例（B2PC opt-01，`spectre-B2PC-opt-01-v1（结果包 sha256 3e80d95b2f27000a…）`，已核收，观察作业）都通过，与参考解相同。原先登记的必拒两例因此在 Spectre 上判为 contradicts；这不是参考解缺陷，原参考解在 Spectre 上可解。读数见上文“待定项”里的 `start_time` 一段。
- 重判（未仿真）：用现行 checker 与改后的 `expected.json`，在已核收的 B2PC 波形上重判本题全部 36 个作业（must-02 参考解与缺省容差对照 12 个，执行身份 `spectre-B2PC-must-02-v1（结果包 sha256 b8b1a0c65f6f4a3e…）`；rec-02 候选与探针 12 个；opt-01 公开观察作业 12 个）。判决与核收时的评分逐项相同；原来与期望相反的两项（探针在 `terminal-normal`、`terminal-low-performance-dut`）改为无登记期望，其余候选作业都与期望一致。每个 PSF 的 sha256 都与其 run.json、核收的 score.json 相同。
- 合成控制：checker 与用例都没改，decisions-r1 与 fix-dec-r1 的合成控制结论不变；探针原先对应的合成控制 `fail-skip-start` 仍由 `skip_start_sample` 对应。
- Spectre 待办：本题不需要新的 Spectre 作业。
