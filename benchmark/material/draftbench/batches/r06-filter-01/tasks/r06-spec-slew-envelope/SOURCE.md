# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C266-S1，`unit_id` C266，来源 `src-9196e3f9608a`，`primary_ref` C266，动作 S（spec-modeling），家族 FILTER，优先级 P0，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 C266-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。author_work 要求：改写为状态与斜率合同，核对两个不同目标输出的限速、复位目标变化与连续轨迹；不提供完整 slew 调用骨架。

主来源是 v3:324 `324-slew-limited-envelope` 的 `instruction.md`，sha256 `bb83874e2fb9d40dac2e583dc65f2439727c356af11b7a6addaf801e5a03d1cf`。它在规划登记中标为 local-only，本机副本位于 `legacy/behavioral-veriloga-eval/benchmark-vabench-release-v3/tasks/324-slew-limited-envelope/`。同一文件也在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v3/tasks/324-slew-limited-envelope) 中，本地副本与公开 blob 的 git 对象一致（instruction `c6e1af7f`，gold `b69c2043`）。该仓库没有 LICENSE 文件。

原题沿用的事实如下：
- `clk` 上升穿越 `vth` 时更新包络：`mode` 低为峰值保持 `max(包络, vin)`，`mode` 高为释放到当前 `vin`；
- 包络钳位到 0–0.8 V；`out` 的目标为包络，`metric` 的目标为包络/0.8；
- 两路输出都按上升 8e8 V/s、下降 3e8 V/s 限速，`fall_rate` 是正的幅值；
- 阈值 `vth=0.45 V`；复位把包络清零；
- 原 gold 在 `initial_step` 把包络和两路目标置 0，复位发生在 `rst` 上升穿越处，`rst` 为高时的时钟沿也清零。

原 checker 见本机 `legacy/behavioral-veriloga-eval/runners/simulate_evas.py` 的 `check_v3_324_slew_limited_envelope`。它在原 hidden 台架上每路输出只查 7 个写死的时间点，容差 0.10 V。原两份台架的 `rst` 都只在开头为高；复位解除后 `vin` 一直在 0–0.8 V 内，两个钳位都没有起作用；斜坡中途的目标变化、复位时输出的限速下降、两路输出时长不同，原先都没有被检查。原题审计（同目录 `AUDIT.md`）把它记为 slew 算子兼容行，计数标签 `cadence_boundary_only`。本题不继承它的判据和成绩。

历史数值依据：本机 legacy 结果缓存里有原 gold 在原 hidden 台架上的一次 Spectre 21.1.0.509.isr12 运行（2026-07-09，`+preset=ax`，reltol 1e-3，maxstep 1.9 ns，未设 strobe），记录见 historical-spectre-crosscheck.json（`runs/t3-p0-build-20261027/r06-spec-slew-envelope/historical-spectre-crosscheck.json`）。
- 用本题 checker 的轨迹律复核：Spectre 的每个斜坡都从事件前一个时间点开始，本次最多提前 24.6 ps，偏离名义轨迹最多 19.7 mV；
- 按本题"每个事件可提前或推后 50 ps"的界限，所有行都在界内（超出 0 mV）。

这次运行不属于本题包，只说明 Spectre 下 slew 斜坡的起点行为，也是第 6 条时间容差的依据。

外部规范：[Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）。
- §4.5.9 定义 slew()：快于限值的变化按限值变化，慢于限值的变化原样通过；`max_neg_slew_rate` 应小于 0；DC 分析中直接输出目标值；
- §4.5.8 定义 transition() 及其中断规则（只用于错误模型的预期）；
- §4.5.15 规定模拟算子不得放在事件或条件语句中。

本题只引用这些定义，没有复制 LRM 文字或代码。外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r06-spec-slew-envelope/sources.json`）。

同源与职责，均不重复计数：
- 第二批草稿：[v3-filter-envelope](../../../v3-01/tasks/v3-filter-envelope/instruction.md)（v4-336）是 I/Q 能量状态的连续包络，状态方程 `e' = 2π*bandwidth*(P - e)`，复位把状态置为 `initval`，没有时钟采样、峰值保持/释放或限速输出。两题来源与机制都不同（第二批分诊已核实），各自计题。
- R06 本批：[r06-spec-ct-lowpass-sampler](../r06-spec-ct-lowpass-sampler/SOURCE.md)（C260-S1）与 [r06-spec-dt-lowpass-sampler](../r06-spec-dt-lowpass-sampler/SOURCE.md)（C264-S1）是线性滤波加采样保持；本题是非线性的事件包络加限速输出，与之互补。
- 首批30题：
  - [v3-ota-continuous](../../../v3-01/tasks/v3-ota-continuous/instruction.md) 是 OTA 宏模型，小信号指数建立，大信号进入不对称压摆区。它的输入是连续信号，没有事件更新的包络状态；
  - [v2-spec-082-agc-receiver-leveling-loop](../../../v2-01/tasks/v2-spec-082-agc-receiver-leveling-loop/instruction.md) 用 `abs` 观测包络并按时钟步进增益，输出不限速；
  - [v3-filter-programmable-lp](../../../v3-01/tasks/v3-filter-programmable-lp/instruction.md) 与 [v3-filter-ctle](../../../v3-01/tasks/v3-filter-ctle/instruction.md) 是线性连续滤波。
- 原56题：除上述各题外，没有其他题以 v3:324 为来源。本题 `source_group` 取新组名 `v3-324`，SOURCE_GROUPS 中原无此组。
- R01：采样保持各题都采样输入本身，不含包络或限速。
- 规划中的相关单元都不另建题：
  - C245-S1（两级运放压摆宏模型，P1）是按拍限步，与连续限速不同，本题的 `step_per_sample` 错误模型就是这种写法；
  - C242（复位清目标、输出继续限速）、C239（不对称上升下降）、C240、C241 等 v3:321–325 的 slew 语法题在规划中保留为组件，本题的复位与不对称斜率行为覆盖其职责，不另计；
  - C262（攻击/释放步长包络）与 C210/C234（峰值保持）也保留为组件或变体。

## 建模选择

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。

1. 模块名由 `slew_limited_envelope` 改为 `slew_envelope_tracker`。理由：原名与公开 gold 相同，改名后原 gold 不能直接原样提交；新名同样描述电路功能。
2. 合同写成状态与斜率两层（author_work）：
   - 包络是只在复位和采样事件改变的分段常数；
   - 两路目标分别是包络和包络/0.8；
   - 每路输出从 0 V 出发，低于目标时以 `rise_rate` 上升，高于目标时以 `fall_rate` 下降，到达后停住，从不跳变，目标在斜坡中途改变时从当前值转向；
   - 说明两路斜坡时长的关系：两路都停在各自目标上、`env` 改变且斜坡没有被后续事件打断时，`metric` 的斜坡是 `out` 的 1.25 倍；一般情形下每路按自身到目标的剩余距离除以斜率计算，中途转向后两路时长不必保持这个比例（p0-fix-a 按审核 F08 改；原句无条件写 1.25 倍，与“从各自当前值转向”矛盾，`rate-override` 的 92 ns 复位就是两路同为 0.3 V、同时到 0 V）。
   原文要求"用 `slew(target, rise_rate, -fall_rate)` 驱动输出，不用 transition"，属于实现指定，已删去；Deliverable 写明不要求特定算子、状态变量或事件组织；starter 只有 include、模块与端口声明和 TODO，没有 slew 调用骨架。校准候选 `alt_explicit_ramp` 不用 slew() 也满足合同。
3. 【待用户确认 1】复位为异步：`rst` 上升穿越处立即清零包络，`rst` 为高时的采样沿保持包络为 0，`rst` 下降不产生事件。
   - 依据：原 gold 的行为；原文"On reset, clear the envelope to zero"本身没有说明是否等时钟沿。
   - `base` 在两次采样之间放了 195–200 ns 的短复位脉冲，只在采样沿清零的同步读法在三个用例中都失败（合成控制 750–1000 mV）。
   - 另一种读法是同步复位。推荐异步。
   - 附带发现：原 gold 用 `cross(clk) or cross(rst)` 合并事件，再在事件里读 `V(rst) > vth`；在 `rst` 自身的上升穿越点 `V(rst)` 正好约等于 `vth`，复位分支不一定执行。新参考解把清零写成独立事件。
4. 复位时目标变为 0，两路输出以 `fall_rate` 下降，不强制归零。理由：这是 author_work 所说的"复位目标变化"，也是原 gold 的 slew 行为；规划中 C242 的"复位清目标、输出继续限速"正是这一职责。复位瞬间输出归零的写法（`reset_jumps_outputs`）在三个用例中都失败。
5. 终评 `rate-override` 用例取 `rise_rate=1.5e8`、`fall_rate=6e8`（下降快于上升），两个速率的合法范围都定为 1e8–4e9 V/s。理由：速率在原题中已是公开参数；改参数可以发现写死 8e8/3e8 的实现（只在该用例失败，805 mV）；慢上升使 5 ns 间隔的采样落在上升斜坡中途，可以区分"包络状态"与"实际输出"两层（`peak_on_output` 只在该用例失败，62.5 mV）。
6. 【待用户确认 2】时间容差：每个复位或采样事件可以提前或推后至多 50 ps 生效，各事件独立；保存点落在这些轨迹在该时刻所取范围的 2 mV 以内即通过。
   - 理由：Spectre 的 slew 在事件前一个时间点开始斜坡（历史运行提前 24.6 ps，偏离名义 19.7 mV），旧版 EVAS 提前一个 50 ps 行（偏离 40 mV）；
   - 斜坡中途转向时两个事件的提前量可能不同，单点时间窗盖不住，所以按事件计；
   - 该动力学保序，checker 用"目标最早上升/最晚下降"和"最晚上升/最早下降"两条响应求界，计算是精确的；
   - 50 ps 等于台架最大步长；`events-80ps-early/late` 合成控制失败（18–24 mV），`events-mixed-45ps` 通过。
   - 另一种读法是逐点时间窗，或像 C260 那样跳过事件后的点。推荐按事件计。
7. 接口保留原题的 6 个端口和 `vth`、`rise_rate`、`fall_rate` 三个参数。`mode` 和 `metric` 在本题都有行为：`mode` 选择保持或释放，`metric` 是第二个目标。原 starter 里未使用的 `vhi`、`tr` 不在 gold 中，已删去。钳位 0–0.8 V 与 `metric` 的 0.8 缩放沿用原题，不设参数。
8. 采样细节：`V(vin)`、`mode`、`rst` 都在穿越时刻读取；`mode` 与 `rst` 的跨阈值离任何上升沿至少 1 ns，避免同刻读法。峰值保持与释放之后都做钳位，`vin` 合法域取 -0.5 V 到 1.2 V，使上下两个钳位都可达。
9. 初态：包络为 0 V，两路输出从 0 V 出发（原 gold 的 `initial_step` 与 slew 的 DC 行为）。`reset-and-start` 在 t=0 时 `rst` 低、`mode` 高、`vin=0.6 V`，输出必须保持 0 V 到第一个采样；从 `vin(0)` 初始化包络的写法失败（750 mV）。
10. 合法域（原题没有）：
    - 控制电平 0/0.9 V，边沿不长于 200 ps，`vth` 在两电平之间，`clk` 从低开始，`mode` 与 `rst` 可高可低开始；控制到达 `vth` 时必定穿过，不触碰后返回，不停在 `vth` 上，t = 0 时离 `vth` 至少 50 mV（后两条是 p0-fix-c 按待用户确认第 38 项的推荐写入的，见 p0-fix-c 一节）；
    - 相邻上升沿至少 5 ns，`clk` 高低各至少 2 ns；
    - 速率范围 1e8–4e9 V/s。
11. 台架：四个用例，50 ps 输出网格，`maxstep=50p strobeperiod=50p`，所有 PWL 拐点落在网格上，`vin` 在每个采样沿前后 0.5 ns 内不变。前三个用例的控制边沿是以给定时刻为中心的 100 ps 边沿；`vth-override` 的控制边沿都是从给定时刻开始的 200 ps 边沿。
    - `base`（公开兼终评）：默认速率；开头复位且 `vin` 高于钳位；保持、对较低输入的保持、向下释放、峰值上升、释放到负输入（钳到 0）、向上释放、超过 0.8 V 的峰值（钳到 0.8）、两次采样之间的异步清零、采样后 1 ns 的清零使 `metric` 在斜坡中途转向、`rst` 为高时的采样、复位后的保持与释放。
    - `rate-override`：慢上升快下降；`vin(0)=0.4 V` 且 `rst` 低；上升斜坡中途的保持采样（`vin` 在输出与目标之间）、使 `metric` 中途转向的释放、上升 2 ns 时的清零。
    - `reset-and-start`：t=0 时 `mode` 高、`rst` 低；首次上升中的清零；`rst` 为高时的三次采样且 `vin`、`mode` 都在变；释放、对较低和相等输入的保持；`vin` 合法上下限处的峰值与释放；目标已为 0 时的短复位；释放后 1 ns 的清零。
    - `vth-override`（p0-fix-a，审核 F05）：`vth` 0.8 V，`rise_rate` 4e9 V/s（合法上限），`fall_rate` 1e9 V/s；200 ps 边沿让 0.45 V 门限把每个上升穿越提前 77.8 ps，超出事件容差 27.8 ps（上升偏 111 mV，下降偏 27.8 mV）；`vin(0)=0.5 V`；峰值保持、对较低输入的保持、向下释放、两次采样之间的异步清零、`rst` 为高时的采样、超过 0.8 V 的峰值、释放到负输入、向上释放；最后一次清零在终点前 22.2 ps。
    前三个用例由 build_cases.py（`runs/t3-p0-build-20261027/r06-spec-slew-envelope/build_cases.py`） 生成，`vth-override` 由 c266_cases.py（`runs/t3-p0-build-20261027/p0-fix-a/scripts/c266_cases.py`） 追加，两者都在生成时断言上述台架义务。
12. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：
    - 从记录的 `rst`、`clk` 穿越和穿越时刻的 `vin`、`mode` 重建包络事件，按第 2 条算出两路名义轨迹与第 6 条的上下界，逐个保存点比较；
    - 轨迹只积分到仿真终点（p0-fix-a，审核 F01）：事件推后 50 ps 后落在终点之后时，不再影响任何保存点，也不再生成倒序断点；
    - 穿越提取用六题统一的规则（p0-fix-c，审核 R2-01、R2-02；p0-fix-a 先按 F02 改成按两侧符号变化识别）：每个保存点与阈值精确比较，恰在阈值上的点不属于任何一侧；相邻两个不在阈值上的点分处两侧时记一次穿越，中间恰有一个阈值点时时刻取该点，否则在两点间线性插值；孤立的阈值点两侧同侧，即触碰后返回，不算穿越；连续两点恰在阈值上表示控制停在 `vth`，抛出异常、不判分，平台后跨到另一侧、回到原侧或记录在平台上结束都一样；记录末尾单个阈值点按到达方向算一次穿越，使终点处的事件仍有提前 50 ps 的容差；记录开头的阈值点不生成穿越；
    - 台架义务出错时抛出异常（无判决，不记候选失败），包括分辨率、`vin` 超域、速率超域、时钟间距、`mode`/`rst` 与采样沿间距，以及控制在 t = 0 离 `vth` 不足 50 mV、控制停在 `vth` 上（这两项是 p0-fix-c 加的）；
    - 不依赖任何仿真器特有行。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
13. 参考解按 LRM 与 Spectre 语义写：包络在 `initial_step`、`rst` 上升穿越事件和 `clk` 上升穿越事件中更新；`V(out) <+ slew(env, rise_rate, -fall_rate)`、`V(metric) <+ slew(env / 0.8, rise_rate, -fall_rate)` 在连续上下文中计算。参考解没有为任何 EVAS 版本改写。
14. 用户已确认（2026-10-28，经总协调答复“全部按推荐”）：记忆污染，保持现合同，标为高污染风险题。原 gold 自 2026-07 起在公开 GitHub 上。本题合同就是把原 gold 的行为写成显式合同，所以原 gold 改掉模块名后，除了第 3 条所说的合并事件读 `V(rst)` 的不确定性，行为与本合同一致，污染风险高于 C260/C264。
    - 采用推荐：保持现合同（沿用原题事实），评测时把它记为高污染风险题，批次 README 与登记记录同样标明；
    - 未采用的另一种做法是加一个钳位上限参数（如 `vmax`，`metric = env/vmax`）并在终评中改它，迫使改写，但这超出 reuse 列出的事实。
    参考解是作者按新合同自写的，没有复制公开代码；它的结构（cross 事件更新包络、slew 驱动输出）是这类模型最常见的写法。
15. 校准候选见 [tests/calibration](tests/calibration/README.md)：20 个错误模型、3 个正确替代实现（含只用标量状态和 `$abstime`、不用 slew() 与 `absdelay` 的 `alt_explicit_ramp`），被拒矩阵另存为 `expected.json`。`fixed_vth` 是 p0-fix-a 加的。

## p0-fix-a 修正（2026-10-28）

依据是 P0 铺开题的独立审核 astra-review.json（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）（F01、F02、F05、F08、F11）。修正记录、命令与结果见 p0-fix-a/disposition.json（`runs/t3-p0-build-20261027/p0-fix-a/disposition.json`）。参考解没有改，公开用例与公开台架也没有改。公开 checker 副本与私有副本一起改，仍逐字节相同。

1. 终点处的事件容差（F01）。原 `response` 会处理推后 50 ps 后落在终点之后的事件，再追加更早的终点，生成倒序断点；完全符合合同的名义斜坡因此被误拒。是否误拒取决于二分查找落在倒序点的哪一侧，所以有的用例碰巧不受影响。在修正前的字节上复现审核的 `terminal-reset` 例：终点前 10 ps 的复位，正确输出被拒 9 mV。合成对照覆盖末次峰值保持采样、释放、复位分别在终点前 0、10、50 ps 的情形；修正前在 0 ps 和 10 ps 误拒了 33 条应通过的轨迹。改为只积分到终点（第 12 条）。修正后，容差内的轨迹都通过；提前 80 ps 的错误轨迹仍被拒；跳变和反向轨迹在 10、50 ps 时被拒，在 0 ps 时事件后没有保存点，看不出。题面没有限制末次事件离终点多远，本修正也不加这个限制。
2. 穿越提取（F02）。原写法把“到达阈值后返回原侧”的触碰算成一次穿越。在修正前的字节上复现：`rst` 从下方触到 `vth` 再返回，checker 虚构一次清零，正确输出被拒；`clk` 的触碰虚构一次采样；`mode` 在采样前 0.5 ns 从上方触到 `vth`，checker 报台架越界，不给判决。改为按阈值两侧的实际符号变化识别（规则见第 12 条）。真正经过阈值行的穿越与原写法结果相同（各用例的控制边沿都恰有阈值行）；在终点到达阈值也与原写法一样算穿越。保留这条约定，是因为严格规则会让终点处的事件失去提前 50 ps 的容差：合成诊断中，提前 40 ps 启动的正确轨迹被误拒 12–32 mV。
3. 门限覆盖（F05）。原三个用例都不覆写 `vth`，写死 0.45 V 的实现能通过全部固定用例。新私有用例 `vth-override`（第 11 条）用 200 ps 边沿和大斜率，使错误门限的提前量超出 ±50 ps 容差；校准候选加 `fixed_vth`。`mode` 与 `rst` 在每个采样时刻都处在 0 V 或 0.9 V，用错门限读取它们看不出来；`fixed_vth` 靠 `clk` 和 `rst` 的穿越时刻暴露，`rst` 的两次清零单独也能暴露它。
4. 两路斜坡时长（F08）：题面把 1.25 倍限定为两路都从停在目标上开始、斜坡未被打断的完整过渡，并写明一般情形按各自剩余距离和斜率计算；第 2 条同步。独立限速的主合同不变。
5. 校准说明（F11）：`tests/calibration/README.md` 改为中文，候选名、命令、诊断与引用保留原文。
6. 【待用户确认 3】精确触碰的语义（p0-fix-a 发现，交主控）。归档的 Spectre 21.1.0.509 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 显示：输入恰好到达阈值时，`cross()` 触发一次“到达”事件，到达后返回原侧也触发，离开时不触发，到达终点时也触发。这正是原 checker 的提取规则。F02 修正后的 checker 不把触碰算作穿越，与题面“穿过 `vth`”一致；但参考解用 `cross()`，在 Spectre 上遇到 `clk` 或 `rst` 的精确触碰会采样或清零，新 checker 会判它错。
   - 本题控制是 0/0.9 V 逻辑信号，精确触碰不算一次切换，所以判断它不在合法域内。在全部合法台架上，两种规则的判定相同；固定用例没有触碰，旧版波形重判 0 项变化。终点处到达阈值算穿越的约定与 Spectre 一致。
   - 旧版 EVAS 0.8.7 的 C264 触碰探针没有触发，与 Spectre 不同；本题的探针那一行不是精确的阈值值，没有测到触碰（f02-touch-semantics.json（`runs/t3-p0-build-20261027/p0-fix-a/evidence/f02-touch-semantics.json`））。
   - 推荐：在题面写明控制到达 `vth` 时必定穿过它，不会触到后返回原侧。这只是把现有输入域写明，不改 checker 和参考解。
   - 另一种读法：按 Spectre 的到达语义把触碰也算作事件，那样应撤回 F02 修正。
   - 本单没有改题面，由主控与另一子任务的同类修正统一决定。

本节的检查都**未仿真**；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-02、R2-01 的复查项与 F02 剩余部分，以及主控 2026-10-28 对清单第 38 项的安排。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解、用例、公开台架和校准件都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 阈值平台（R2-02）。p0-fix-a 的写法把连续两行以上停在阈值上的平台当作可评分输入，而题面已写明控制不停在 `vth` 上。在修正前的字节上复现：`rst` 在 10.000 ns、10.050 ns 两行恰为 0.45 V，平台后跨到另一侧、回到原侧、记录在平台上结束，三种都得到判决（都通过）。现改为六题统一的穿越规则（第 12 条），三种都抛出异常、不判分，记录开头的两行平台也一样。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 终点容差（R2-01 要求的复查）。记录末尾单个阈值点仍按到达方向算一次穿越，所以终点处的复位或采样仍可提前 50 ps 生效。p0-fix-a 的 81 个终点对照（末次峰值保持、释放、复位分别在终点前 0、10、50 ps，容差内外的轨迹）在新 checker 上全部符合预期，判决与存档相同。末次事件离前一次上升沿不足 5 ns 时照样报台架错误。
3. 【待用户确认第 38 项，已按推荐写入】控制到达门限时必定穿过。题面合法输入一段在“Controls never rest at `vth`.”之后加两句：“A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. At t = 0 each control is at least 50 mV away from `vth`.”checker 加对应的台架检查：`clk`、`mode` 或 `rst` 在 t = 0 离 `vth` 不足 50 mV 时抛出异常。
   - 这两句只约束外部驱动的控制输入。p0-fix-a 一节第 6 条的【待用户确认 3】就是这一项。
   - t = 0 的 50 mV 余量是缩域，不是对原合同的无损澄清：原合法域只要求 `vth` 严格位于 0 V 与 0.9 V 之间。新加的是输入初态与 `vth` 的联合约束，不是把参数一律收窄：控制都从 0 V 起步时，要求 `vth` ≥ 0.05 V（可到 0.9 V 以下）；有控制从高轨起步时，另要求 `vth` ≤ 0.85 V；要让任意高低初态都合法，公共范围才是 0.05–0.85 V。本题 `clk` 从低起步，前一条总适用；`mode`、`rst` 可以从高轨起步，此时适用后一条（p0-fix-d 按 P0 r3 复审 R3-05 更正，与待选清单第 40 项一致）。四个用例的 `vth` 是 0.45 V 和 0.8 V，都满足，判分不变。用户若不要这一缩域，只需删去第二句和 checker 的起始检查。
   - 另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
4. 复核：
   - 行模式表在六题 checker 上相同；本题与修正前只差在平台，现在报错。
   - p0-fix-a 的合成控制与 F01–F11 复现脚本复制到 p0-fix-c 后在新 checker 上重跑，判决与误差与存档逐项相同；建题时的证据有效性控制仍全部报错、不判分。
   - 建题以来的旧版存档波形（含 p0-fix-a 的运行与触碰探针）用新 checker 重判，判决与误差 0 项变化。本题用例未改，没有新的旧版运行。
   - 平局扫描（精确有理数）：参考解 `slew()` 斜坡到达目标的时刻都不在输入穿越上。事件与事件同刻的三处（`rate-override` 72 ns、92 ns，`reset-and-start` 94 ns）都有一方是 `clk` 下降穿越，不是本题的事件，不算平局。

第 38 项的三个前提（主控 2026-10-28 定的口径，也作复审口径）：
- 内部恰为零：参考解的事件只看外部驱动的 `clk` 与 `rst` 上升穿越，`mode` 只在采样事件读电平；没有被测模块内部恰为零的信号参与事件或判决，无需核对。执行细则（主控 2026-10-28 转标准线口径，p0-fix-d 写入，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。本题参考解只对外部驱动的 `clk`、`rst` 用 `cross()`，符合（p0-fix-d 核对）。
- 相等规则写成输出行为：题面没有内部相等规则；峰值保持取较大值时相等无歧义；控制恰在 `vth` 上由合法输入排除（第 3 条）。
- 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r06-spec-slew-envelope/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制；
- 旧版 EVAS 0.8.7 冒烟，含参考解、起始模型、全部校准候选和诊断探针（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）；
- EVAS 02dee32b 阶段 a–c；
- Docker 两个镜像实际构建一次并检查。

p0-fix-a 的检查（findings 复现、合成控制、旧版运行与重判、结构检查、Docker）另记在 checks.json 的 `p0_fix_a` 一节；EVAS 02dee32b 没有对新用例重跑。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录每个事件处 slew 斜坡的起点偏移（预期不超过一个时间步）；
- 本题合同内没有待发事件：没有传输延迟，控制跨阈值离采样沿至少 1 ns，斜坡中途转向属于合同。Spectre 运行时仍按样板记录 `transition()` 的待发与中断行为（对应 `no_slew`、`fixed_duration_transition` 两个候选）和同刻事件的执行次序；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 用户确认上面三个“待用户确认”选择（第 3 个在 p0-fix-a 一节，即清单第 38 项；p0-fix-c 已按推荐写入题面，t = 0 的 50 mV 余量是缩域，见 p0-fix-c 一节；第 14 条已于 2026-10-28 确认）；
- 记录 `results/reference.json` 与 `results/calibration.json`。
