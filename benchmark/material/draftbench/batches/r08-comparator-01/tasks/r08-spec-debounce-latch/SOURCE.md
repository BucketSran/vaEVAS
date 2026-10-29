# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C176-S1，`unit_id` C176，来源 `src-4de7bc3ce78f`，`primary_ref` C176，动作 S（spec-modeling），家族 R08，优先级 P0，结构难度 M，建设成本 L。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 C176-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。登记要求：
- reuse：12 ns 连续资格、输入下降取消、复位取消和定时到期复核；
- author_work：补重新触发及到期/下降/复位同刻规则，保留最小接口，校准过期预约不得误触发；
- difference：待执行事件必须失效，不是普通一位锁存。

主来源是 [v4:005-debounce-latch 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/005-debounce-latch/public/instruction.md)，sha256 `b399f82bb4e4b94f397b1ca02b6cd1b0fd8f3273b38d8aa0e34f0d0f52c46935`，规划登记为 repository-contained。[原 gold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/005-debounce-latch/evaluator/solution/debounce_latch.va) 的 sha256 为 `79afb58d…85334009f1a`，与 v3:005 的 gold、第二批修复题的健康源码逐字节相同。原题沿用的事实：
- 接口 `debounce_latch(sig, rst_n, out)`，参数 `vth = 0.45 V`、`vdd = 0.9 V`、`stable = 12 ns`、`tr = 500 ps`；
- `out` 初值为低；复位释放期间 `sig` 上升启动资格计时；到期时 `sig` 与 `rst_n` 仍为高才置高；
- `sig` 下降或 `rst_n` 为低时清零并取消待发资格。

原题没有写重新触发、同刻、上电时 `sig` 已高、复位释放时 `sig` 已高的处理，也没有验收尺度。v4 的 [评分台架](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/005-debounce-latch/evaluator/score_tb.scs)与公开台架相同，只有一份 140 ns 激励；v4 checker 不公开。本机 `legacy/behavioral-veriloga-eval/runners/simulate_evas.py` 的 `check_v3_debounce_latch` 只在 8 个固定时刻按 0.45 V 判高低。这份激励里没有被取消的资格在原定完成时刻遇到 `sig` 与 `rst_n` 都为高，看不到过期预约；参数从未改写。本题不继承它的判据和成绩。

历史 Spectre 证据：按样板第3a节查了本机 `legacy/behavioral-veriloga-eval/results/`（含 `_local/v3_skeleton_dual_parity_cache/hidden/` 与各 `v3_spectre_audit*` 目录），没有 v3:005 或 v4:005 的 Spectre 运行；v4 记录的认证后端是 `rust_evas2`。参考解的事件语义因此只以 LRM 为据，Spectre 行为列入待办。

外部规范：[Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）。
- §5.10.3.1：`cross()` 在时间离开 0 之后才产生事件；§5.10.3.2：`above()` 在初始化时也会触发；
- §5.10.3.3：`timer()` 的起始时刻在求值中改变时，下一个事件按最新值安排；周期不为正时只在起始时刻位于未来时触发一次；
- §4.5.8：`transition()` 的 `td` 是传输延迟，可以有任意多个待发过渡，新安排的过渡删除排在它之后的待发过渡；过渡被打断时按规定的起点与斜率完成。

本题只引用这些定义，没有复制 LRM 文字。外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r08-spec-debounce-latch/sources.json`）。GitHub 代码检索（`debounce`、`deglitch`、`glitch filter` 等）只找到 Arcadia-1/behavioral-veriloga-eval 中的历史题，没有其他实现，也没有可复制的宽松许可代码。

记忆污染风险：高。原 v3:005、v4:005（r45–r53）的题面、gold 和台架都在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/005-debounce-latch) 中，与本仓库副本的 git 对象一致（题面 `57a5b8bb`，gold `bc41d96c`）。该仓库没有 LICENSE 文件。本题保留了最小接口，原 gold 原样提交即满足新合同；参考解是作者按新合同自写的，没有复制公开代码，但与原 gold 同为 `cross` + `timer` + `transition` 结构，这是这类模型最常见的写法。见待用户确认 1。

同源与职责，均不重复计数：
- 第二批草稿 [v2-repair-debounce-latch](../../../v2-01/tasks/v2-repair-debounce-latch/instruction.md)（`v4-family-005`）与本题同源（v4:005），分诊已核实两者各自保留身份：
  - 那里是诊断修复，给出完整错误源码（上升沿当即置高），验收为 25 mV、事件邻域 0.6 ns、两份固定激励；
  - 本题从只有接口的 starter 按规格建模，要求自己组织资格、取消、重新触发与同刻规则，终评改写 `vth`、`vdd`、`stable`、`tr`；
  - 本题校准候选中只有 `immediate_set_on_rise` 对应修复题的起始故障，另有 20 个错误模型和 4 个正确替代实现。
  - 本题沿用那里已明文写出的"复位释放时 `sig` 已高不启动资格"。
- 首批30题：
  - [v2-repair-pfd-reset](../../../v2-01/tasks/v2-repair-pfd-reset/instruction.md)（`v4-family-249`）也有"复位取消待发事件"和"释放后只接受新沿"，但待发的是置位后固定 80 ps 的清零，没有资格窗口；
  - [v2-repair-uvlo-reset-chain](../../../v2-01/tasks/v2-repair-uvlo-reset-chain/instruction.md) 的 `chain_release` 要求供电有效连续一段时间后才释放复位，是四模块链中的一环，按电平而非沿资格；
  - [v2-spec-314-hysteretic-window-comparator](../../../v2-01/tasks/v2-spec-314-hysteretic-window-comparator/instruction.md) 等比较器题没有资格计时。
- 第二批其余草稿和原56题：除修复题外没有以 v4:005 或 v3:005 为来源的题。
- R01：采样家族，无同源。
- P0 试点 [r04-spec-delay-pulse-hold](../../../r04-clock-01/tasks/r04-spec-delay-pulse-hold/instruction.md)（U15-S1）管理两方向可同时待发的延迟沿，由复位取消；本题只有一个资格待发，取消条件是输入本身，难点在过期预约和完成时刻附近的竞争。
- 规划中的 C292-S1（带去毛刺窗口的边沿延迟线，P1）尚未建题，规划要求先复用本题和 U15 的事件规则经验。

## 建模选择

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。

1. 接口与参数保留原题：模块 `debounce_latch`，端口 `sig, rst_n, out`，参数 `vth`、`vdd`、`stable`、`tr` 及默认值。新增合法范围：`vth` 0.2–0.7 V，`vdd` 0.5–1.5 V，`stable` 2 ns–1 us，`tr` 10 ps–1 ns。理由：author_work 要求保留最小接口；没有增加调试输出，待发状态只能通过 `out` 间接观察。
2. 合同写成理想电平规则：上升穿越且 `rst_n` 为高时开始资格，`t_r + stable` 完成置 `vdd`，`sig` 或 `rst_n` 的下降穿越取消并清零。完成要求整个闭区间内两路都保持为高，与原题"到期复核"一致。Deliverable 写明不要求特定算子、状态变量或事件组织。
3. 【待用户确认 1】只有复位释放期间的 `sig` 上升穿越启动资格。t = 0 时 `sig` 已高、复位释放时 `sig` 已高，都不启动，要等下一次上升穿越；`rst_n` 上升本身不改变任何状态。
   - 依据：原题"sig rises through vth while reset is released"；第二批修复题已明文写出释放时已高不启动；首批 v2-repair-pfd-reset 也是"释放后只接受新沿"；LRM 的 `cross()` 在 t = 0 不触发。
   - 另一种读法是电平型资格（计数器式去抖常见）：`sig` 与 `rst_n` 同时为高就开始计时，复位释放或上电时已高也算。这种读法下原 gold 会失败，可降低记忆污染，但改变了原题语义，并与同源修复题矛盾。
   - `retrigger-ties` 用例里 `sig` 与 `rst_n` 从 t = 0 起为高 20 ns，`base`、`retrigger-ties`、`short-stable` 各有释放时 `sig` 已高且之后保持超过 `stable` 的段落，电平型读法在这三例被拒（合成控制 `level-sensitive-start`）。
   - 推荐沿型。
4. 重新触发与过期预约：每次合格的上升穿越从自身时刻重新计时；被取消的资格永不完成，原定完成时刻到达时即使两路都已重新为高也不改变输出。用例刻意安排了 7 个这样的时刻（`base` 77.02/85.02/132.02 ns，`retrigger-ties` 78.02 ns，`short-stable` 16.002/17.502/68.002 ns），对应 author_work 的"校准过期预约不得误触发"。保留第一次预约不重排（`stale_first_reservation`）、复位不取消（`reset_keeps_reservation`）、下降不取消且不复核 `sig`、复位期间也开始资格、高电平时间跨毛刺累加、`transition()` 传输延迟的两点判断，都是错误模型。
5. 【待用户确认 2】同刻：完成时刻与 `sig` 或 `rst_n` 的下降穿越正好同刻时取消优先，不置高（author_work 的到期/下降/复位同刻）。合法激励域把这类正好同刻排除在终评之外：任何下降穿越离任何 `t_r + stable` 至少 0.3 ns；`sig` 上升穿越离任何 `rst_n` 穿越至少 0.5 ns，因此上升与复位穿越同刻的结果不作规定。
   - 终评用例在边界两侧各放一处：下降早于完成 0.3 ns（不出现脉冲）、晚于完成 0.3 ns（输出上升途中被打断）；`sig` 上升早于或晚于复位释放 0.5 ns。
   - 旧版 EVAS 同刻探针（不入题包，见探针记录（`runs/t3-p0-build-20261027/r08-spec-debounce-latch/scratch/tie-probe/tie-probe-summary.json`））：完成与下降或复位下降正好同刻时，参考解与 `alt_event_flags` 保持 0 V，`alt_transition_delay` 仍执行了待发上升，输出出现一个到达 0.9 V 的毛刺脉冲后回到 0 V；`sig` 上升与复位释放正好同刻时三者都开始了资格。这说明上升与复位同刻没有自然统一的结果，所以合同不规定。
   - 另一种读法是终评加入正好同刻的完成/取消用例，这会拒绝 `alt_transition_delay` 一类写法；但 Spectre 中 `timer` 与 `cross` 事件的相对定位尚未记录，参考解在同刻处的毛刺幅度也未知。
   - 推荐现在不评正好同刻，Spectre 校准记录事件次序后再定。
6. 输出：`out` 驱动理想电平，每次电平变化后 `tr` 内到达新电平并保持；下一次变化先于到达时同样适用；`tr` 内波形不作规定。smoothstep、0.2·tr 快过渡、延迟 0.2·tr 再用 0.8·tr 过渡的合成控制都通过。
7. 用户已确认（2026-10-28，经总协调答复“全部按推荐”，F01 选题面写明实际观察起点）：评分起点与到达期限照样板第3b节沿用试点写法，电平变化后 `1.25*tr` 内不评分，题面照实写明，checker 不动。
   - 另加在评分起点之后才到达的负例 `slow_output_1p3tr`（过渡 1.3·tr）。所有用例的输出变化时刻都对齐网格相位，评分起点后的第一个点在起点之后 5 ps（`base`、`retrigger-ties`）、3 ps（`short-stable`）或 10 ps（`threshold-override`）。该负例在四个用例都被拒，合成控制误差 27.7 mV（`short-stable` 18.5 mV），旧版 EVAS 同样被拒。
   - 1.2·tr 到达的合成输出通过全部用例。按用户确认，期限 `tr` 与评分起点 `1.25*tr` 之间到达不区分，这是题面写明的余量。
8. 【待用户确认 3】误差上限 10 mV（同源修复题为 25 mV）。
   - 理由：`out` 是理想电压驱动，正确实现在旧版 EVAS 上误差 0.0 mV；25 mV 下 1.3·tr 负例在评分起点后 5 ps 的误差只有 27.7 mV，余量太小。
   - 另一种读法是与修复题一致取 25 mV，但需要把网格相位压到 1–2 ps 才能稳定拒绝 1.3·tr 负例。
   - 推荐 10 mV。
9. 【待用户确认 4】输入可以停在 0 V 与 0.9 V 之间的任意电平（离 `vth` 至少 50 mV 起步，不停在 `vth`），斜坡长短不限。
   - 理由：改写 `vth` 要能被看出，F08 指出过写死门限与正确实现不可区分。`threshold-override`（`vth = 0.3 V`）让 `rst_n` 停在 0.38 V、`sig` 有 0.38 V 平台和一次掉到 0.38 V 的下陷，写死 0.45 V 的模型在该例必败；1.5 ns 斜坡使 0.3 V 与 0.45 V 的穿越差 0.25 ns。
   - 另一种读法是输入只取 0/0.9 V 逻辑电平、边沿不长于 200 ps，此时只能靠斜坡检出门限，上升方向会被 1.25·tr 的不评分区遮住。
   - 推荐允许中间电平。
10. 台架：四个用例，输出网格 `maxstep = strobeperiod`，每个输入转换是一段穿越时刻为设计值的线性斜坡，checker 读取穿越时间无插值误差。
    - `base`（公开兼终评，默认参数，25 ps 网格）：上电复位中途 `sig` 上升、释放时 `sig` 已高；普通资格与下降清零；毛刺串，其中两处过期预约；输出为高时复位；资格中途 2 ns 复位脉冲；完成前后 0.3 ns 的下降。
    - `retrigger-ties`（默认参数）：t = 0 起两路为高；输出为高时 0.525 ns 低毛刺（p0-fix-c 由 0.5 ns 改为 0.525 ns，见 p0-fix-c 一节）；8 ns 高、1 ns 低的毛刺串（累加模型会提前 8 ns 置高）；复位下降在完成前后 0.3 ns；`sig` 上升在复位释放前后 0.5 ns。
    - `short-stable`（`stable = 4 ns`、`tr = 100 ps`、`vdd = 1.2 V`，10 ps 网格）：写死 12 ns 会迟 8 ns；毛刺串；完成后 0.3 ns 下降，其间 0.17 ns 的高电平受评分；1 ns 复位脉冲使一次资格作废。
    - `threshold-override`（`vth = 0.3 V`、`stable = 30 ns`、`tr = 1 ns`，50 ps 网格）：见第9条；完成前后 0.3 ns 的下降配 1 ns 输出过渡；从 0.38 V 电平复位。
    台架由 build_cases.py（`runs/t3-p0-build-20261027/r08-spec-debounce-latch/build_cases.py`） 生成，生成时断言全部台架义务，并独立算出理想电平。
11. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：
    - 从记录的 `sig`、`rst_n` 按相邻行线性取穿越时间，按规则算出理想电平；
    - 穿越提取用六题统一的规则（p0-fix-c，审核 R2-01；p0-fix-b 先按 F02 改成按两侧符号变化识别）：每个保存点与 `vth` 精确比较，恰在 `vth` 上的点不属于任何一侧；相邻两个不在 `vth` 上的点分处两侧时记一次穿越，中间恰有一个阈值点时穿越时刻就是该点，否则按两点线性插值；到达 `vth` 后返回原侧的孤立触碰不是穿越；连续两点停在 `vth` 上违反"不停在 `vth`"，抛出异常、不判分；记录末尾单个阈值点按到达方向算一次穿越；记录开头的阈值点不生成穿越（起始离 `vth` 不足 50 mV 本来就是台架错误）；
    - t = 0 的初值不在任何不评分区内，必评；
    - 台架义务出错时抛出异常（无判决，不记候选失败）：分辨率、参数超域、输入超出 0–0.9 V、起始电平离 `vth` 不足 50 mV、穿越不交替、同一输入相邻穿越不足 0.5 ns、上升离复位穿越不足 0.5 ns、下降离完成时刻不足 0.3 ns；
    - 不依赖任何仿真器特有行，旧版 EVAS 只用规则网格行重判时结论不变；
    - 结果另报被取消且原定完成时刻两路都为高的资格个数，作为过期预约覆盖的记录。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
12. 参考解按 LRM 写：三个 `cross` 事件与一个 `timer(t_done)`，取消事件写在完成事件之前，同一求值中取消优先；`running` 标志使已取消资格的定时器时刻无效；新的上升沿改写 `t_done`，按 §5.10.3.3 重排定时器；`transition` 零延迟驱动输出。没有为任何 EVAS 版本改写。
13. 校准候选见 [tests/calibration](tests/calibration/README.md)：21 个错误模型、4 个正确替代实现，被拒矩阵另存为 `expected.json`；只在某种后端语义下成立的三条写进 `conditions`。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r08-spec-debounce-latch/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制；
- 旧版 EVAS 0.8.7 冒烟，含参考解、起始模型、全部校准候选和同刻探针（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）；
- EVAS 02dee32b 阶段 a–c 及两个探针；
- Docker 两个镜像实际构建一次并检查。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量与评分起点后第一个点的实际位置；
- Spectre 待发事件（样板第4a节）：本题有待发事件，即资格定时器的预约，以及校准候选中 `transition()` 的延迟变化。需要记录：
  - `transition()` 的待发过渡行为：零延迟下降是否删除其后的待发上升，对应 `alt_transition_delay`；是否保留全部待发变化，对应 `transport_delay_and`。旧版 EVAS 用新变化替换待发变化，与 LRM 4.5.8 不同。
  - 同刻事件的执行次序：同一时间点上 `cross` 与 `timer` 事件是否按源码次序执行；
  - `timer` 起始时刻改写后旧时刻不触发、移到过去后不触发：过期预约不得误触发；
  - 完成时刻与下降正好同刻时参考解的输出毛刺，作为待用户确认 2 的依据；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 用户确认上面四个"待用户确认"选择（F01 已于 2026-10-28 确认）和清单第 38 项（p0-fix-c 已按推荐写入题面，见 p0-fix-c 一节）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## p0-fix-b 修正（2026-10-28）

依据铺开六题独立审核 r1（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）的 F02。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-b 处置记录（`runs/t3-p0-build-20261027/p0-fix-b/disposition.md`）。本题**未仿真**：没有运行 Spectre，旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

- 问题：checker 原先把"到达 `vth` 后返回原侧"的孤立触碰记成一次单向穿越，又没有返回事件。`sig` 从下方触及 `vth` 会凭空开始一次资格并在 `stable` 后要求置高，`sig` 或 `rst_n` 从上方触及会凭空取消资格，合同正确的波形被误拒。题面把穿越定义为输入越过 `vth` 的时刻，触碰不是穿越。
- 改动：只改公开与私有两份 checker 的穿越提取，规则见建模选择第 11 条，两份逐字节相同。题面、参考解、用例、公开台架和校准件都不变。
- 复核：触碰后返回与恰有阈值行的真实穿越各有正反对照（合成波形），修正前触碰类对照判错、修正后判对，恰有阈值行的穿越前后都判对；建题时的全部合成控制在新 checker 上重跑，结论不变；参考解在旧版 EVAS 上通过全部私有与公开用例；建题时存档的旧版波形用新 checker 重判，判决全部不变。
- 终评台架没有恰好触及 `vth` 的输入。（p0-fix-c 更正：这里原写“仿真器的 `cross()` 遇到恰好触及阈值又返回的输入是否触发，本题没有记录”，不准确。归档的 Spectre 21.1.0.509 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 显示，`cross()` 在输入恰好到达阈值时按到达方向触发一次，孤立触碰后返回也触发，离开时不触发。p0-fix-c 已按第 38 项的推荐在题面排除触碰。这份记录用的是显式 PWL 实验，参考解在本题台架上的行为仍待 Spectre 复跑。）

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-01 与 F02 剩余部分、主控 2026-10-28 对清单第 38 项的安排，以及 EVAS 线用精确有理数发现的 `retrigger-ties` 平局。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解、公开用例与公开台架、校准件都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 终点事件（R2-01）。p0-fix-b 的写法丢掉记录末尾单个恰在 `vth` 上的行，终点处到达的事件就没有不评分窗。题面允许输出在事件时刻立即改变，所以正确输出会被判错。在修正前的字节上复现：`sig` 在 1.045 ns 上升、`stable` 2 ns，`out` 在 3.045 ns 后为高；`rst_n` 在最后一行（10 ns）从上方恰到 0.45 V，`out` 在这一行立即清零，被拒 0.9 V；p0-fix-b 之前的写法接受它。现改为六题统一的穿越规则（第 11 条）：末尾单个阈值点按到达方向算一次穿越，这条输出通过；提前 1 ns 清零的输出仍被拒。终点事件照样受相邻穿越间隔约束：离前一次 `sig` 穿越 0.455 ns 时报台架错误，正好 0.5 ns 时照常评分。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 【待用户确认第 38 项，已按推荐写入】输入到达门限时必定穿过。题面合法输入一段在“at t = 0 each is at least 50 mV away from `vth`.”之后加一句：“An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”“不停在 `vth` 上”和起始 50 mV 原已写明，不重复；checker 不变。另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
3. `retrigger-ties` 的平局（EVAS 线发现）。这个用例在 45.02 ns 用 `sig` 下降清零高电平输出，45.52 ns 再上升，要测的是输出为高时的短低毛刺。毛刺宽 0.5 ns，恰好等于默认 `tr` 500 ps：参考解输出的下降斜坡在 fl(45.02n)+fl(0.5n) 结束，`sig` 在 45.52 ns 穿过 `vth`，两者精确值只差 11·2⁻⁸³ s，落在同一个 binary64 时刻。
   - 定类（主控 2026-10-28 定稿的口径，总协调已确认）：第 (i) 类，迁就 EVAS，不是题目缺陷。checker 的期望只由记录的 `sig`、`rst_n` 穿越算出（`tests/verify.py` 第 117 行取穿越，第 58–89 行的 `ideal_changes` 只用这些穿越），45.52 ns 这次上升开始一次资格、不改变理想电平；平局时刻落在 45.02 ns 变化后的不评分窗内（到 45.645 ns）。两种次序下参考解的波形相同。合成核对（tie-classification.json（`runs/t3-p0-build-20261027/p0-fix-c/evidence/tie-classification.json`），与主控的 `main-c176-tie-check` 一致）：合同波形通过；`out` 从 45.52 ns 到窗口结束加 0.25 V 仍通过；窗口结束后加 0.25 V 被拒。
   - **第 (i) 类，待用户确认是否退回；原件在 p0-fix-c/orig/。** 退回时用原 `tests/cases.json`（`runs/t3-p0-build-20261027/p0-fix-c/orig/r08-spec-debounce-latch/tests/cases.json`），本条的其余核对不受影响。
   - 改法：这次上升挪后一个 25 ps 网格步到 45.545 ns，网格相位不变，毛刺宽 0.525 ns；只改 `Vsig` 的两个拐点（45.47n→45.495n，45.57n→45.595n）和 purpose 文字，题面和 checker 不动。生成脚本是 p0-fix-c 的 build_cases.py 副本，断言全部台架义务。
   - 核对：这次上升开始的资格在 57.545 ns 完成（原 57.52 ns），最近的下降穿越在 65.02 ns，离完成时刻远大于 0.3 ns；离 `rst_n` 穿越远大于 0.5 ns；其他穿越离任何完成时刻都至少 0.3 ns；过期预约仍是 78.02 ns。评分起点后的第一个点仍在 1.25·tr 之后 5 ps，1.3·tr 迟到负例在 57.545 ns 这次变化上超出 27.7 mV，1.2·tr 窗内对照通过。
   - 0.5 ns 最小间隔的边界仍有覆盖：`base` 的 73.77/74.27 ns 与 `short-stable` 的 13.002/13.502、15.002/15.502 ns 都是同一输入相隔正好 0.5 ns 的两次穿越。`base` 73.77 ns 那次下降不改变理想电平，不起过渡，所以没有平局。
   - 精确有理数扫描六题全部用例的结果见处置记录：本题只有这一处，挪开后没有平局；事件与事件同刻的没有。

第 38 项的三个前提（主控 2026-10-28 定的口径，也作复审口径）：
- 内部恰为零：参考解的事件只看外部驱动的 `sig`（上升、下降）、`rst_n` 下降和自己的 `timer`，`rst_n` 只在 `sig` 上升时读电平；没有被测模块内部恰为零的信号参与事件或判决，无需核对。执行细则（主控 2026-10-28 转标准线口径，p0-fix-d 写入，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。本题参考解只对外部驱动的 `sig`、`rst_n` 用 `cross()`，`timer()` 的事件体只读 `sig`、`rst_n` 的电平，符合（p0-fix-d 核对）。
- 相等规则写成输出行为：题面没有内部相等规则；完成时刻与下降同刻、上升与复位同刻由合法输入排除（第 5 条）。
- 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。
4. 复核：
   - p0-fix-b 的 F02 对照 11 个在新 checker 上判决不变；p0-fix-b 的合成控制副本在新用例上全部符合预期，与存档相比判决与误差 0 项变化。
   - 旧版 EVAS：参考解在全部私有与公开用例上通过（5/5，误差 0）；25 个校准候选在 `retrigger-ties` 上与被拒矩阵逐项一致（15 拒、10 接受），被拒矩阵不变。
   - 建题以来的旧版存档波形用新 checker 重判，判决与误差 0 项变化。
