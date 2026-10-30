# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C264-S1，`unit_id` C264，来源 `src-bad8f422df0a`，`primary_ref` C264，动作 S（spec-modeling），家族 FILTER，优先级 P0，建设成本 M。登记见[规划登记](../../../../planning/history-candidates/register.json)中的 C264-S1 条目，来源身份见同目录 [sources.json](../../../../planning/history-candidates/sources.json)，规划说明见[候选说明](../../../../planning/history-candidates/CANDIDATES.md#c264-s1)。author_work 要求：整理成可独立理解的离散传递合同，核对初态、采样相位、插值及双采样同刻关系，不猜测等价递推。

主来源是 v3:441 `441-zi-nd-discrete-filter` 的 `instruction.md`，sha256 `27a566f6efe77dadfacb595a7f2440b0ec6443a9f4eaaa6c9f6d620a301e802c`。它在规划登记中标为 local-only，本机副本位于 `legacy/behavioral-veriloga-eval/benchmark-vabench-release-v3/tasks/441-zi-nd-discrete-filter/`。同一文件也在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v3/tasks/441-zi-nd-discrete-filter) 中，本地副本与公开 blob 的 git 对象一致（instruction `23e16b34`，gold `4a23ed28`）。该仓库没有 LICENSE 文件。

原题沿用的事实如下：
- 离散一阶低通，原文指定 `zi_nd(V(vin), {0.25}, {1.0, -0.75}, 100n)`，即 `H(z)=0.25/(1-0.75 z^-1)`，DC 增益 1，内部每 100 ns 更新；
- 算子在连续上下文中计算，每个 `clk` 上升沿把当时的滤波值复制到输出；
- 采样时若 `rst` 高于 `vth`，只清采样输出，滤波器不受影响；
- 阈值 `vth=0.45 V`，输出过渡 `tr=200 ps`；
- 原 starter 在 `initial_step` 把采样状态置 0。

同一单元的其他历史形式，按规划不另计题：
- v3:442 `442-zi-np-discrete-filter` 用 `zi_np(V(vin), {0.25}, {0.75, 0.0}, 100n)` 写同一个 `H(z)`，只差算子形式（清单条目 `zinpdiscretefilter`，同指 C264）；
- v3:494 `494-continuous-zi-nd-filter` 是另一组系数的 zi_nd 语法登台题，原题自述缺少动态精度合同，规划只保留为系数变体素材。

原 checker 见本机 `legacy/behavioral-veriloga-eval/runners/simulate_evas.py` 的 `check_v3_441_zi_nd_discrete_filter`（经 `_v3_zi_expected_at`）。它只在前三个时钟沿后 8 ns 各取一个点，按 max(12 mV, 2%) 判定。它对两种算子假设了不同的初态：zi_nd 从 0 起、跳过 t=0 的更新，zi_np 从 `vin(0)` 起。原 441 两份台架的 `vin(0)` 都是 0，`rst` 都恒为 0，所以初态、"复位不清滤波"和两套时间基准的关系原先都没有被检查。本题不继承它的判据和成绩。

历史数值依据：本机 legacy 结果缓存里有原 gold 在原 hidden 台架上的两次 Spectre 21.1.0.509.isr12 运行（2026-07-09，`+preset=ax`，reltol 1e-3，maxstep 10 ns），记录见 historical-spectre-crosscheck.json（`runs/t3-p0-build-20261027/r06-spec-dt-lowpass-sampler/historical-spectre-crosscheck.json`）。用本题 checker 的更新公式逐沿复核：
- v3:441（zi_nd，`vin(0)=0`）：三个采样值 0、0.30625、0.2546875 V 与公式一致，误差小于 1e-13 mV。这确认了更新时刻为 t=0 起每 100 ns、新输入在本更新时刻生效、更新之间保持；在 99.45 ns（更新前 0.55 ns）的采样得到更新前的值。
- v3:442（zi_np，`vin(0)=0.65 V`）：第一个采样为 0.65 V，即从 DC 工作点（平衡态）起步；零初态模型应为 0.1625 V。

这两次运行不属于本题包，只说明 Spectre 下 zi 算子的相位、递推与起始状态，也说明 `{...}` 数组写法在该版 Spectre 上可用。

外部规范：[Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）。
- §4.5.12 定义 zi 滤波器：周期 T 采样，"单位传递函数时等同于每 T 采样一次、没有延迟的采样保持"；首次跳变默认在 t=0；τ=0 时输出突变，且不得直接赋给支路；τ 省略时取 `default_transition`，未定义时由仿真器决定；
- 表 4-20 规定 zi 的系数、T 与 t0 是常量表达式，参数属于常量表达式；
- §4.5.15 规定模拟算子不得放在事件或条件语句中，且在 t=0 前没有状态历史。

LRM 没有写 zi 滤波器在 DC 工作点和瞬态起点的取值，各实现也不一致：gnucap-modelgen-verilog 在瞬态开始时把寄存器清零；verilog-a-sim 的 DC 取 `H(1)` 乘输入，但瞬态 t=0 的采样取冷启动种子；旧版 EVAS 0.8.7 的 zi_nd 从零历史起步，zi_np 从平衡态起步。所以本题把初态写成显式合同。本题只引用这些定义与实现事实，没有复制 LRM 文字或任何代码。外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r06-spec-dt-lowpass-sampler/sources.json`）。

同源与职责，均不重复计数：
- R06 本批：[r06-spec-ct-lowpass-sampler](../r06-spec-ct-lowpass-sampler/SOURCE.md)（C260-S1）是连续一阶低通加同样的外部采样与复位规则。两题构成连续与离散的区别，不是同一模型的两种写法：
  - 本题的滤波值只在内部网格上变化，网格之间保持，网格之间的输入变化不被看到；
  - 同极点的连续滤波器（`tau=tupdate/ln(4/3)`）在本题三个用例中都失败（合成控制 134–399 mV，旧版 EVAS 常数系数探针 134–399 mV）；
  - C260 本身的滤波律（tau=100 ns）在本题全部失败。
- 首批30题：
  - [v3-filter-programmable-lp](../../../v3-01/tasks/v3-filter-programmable-lp/instruction.md)（v4-334）是连续一阶低通，复位清滤波状态，没有采样；
  - [v2-spec-024-clocked-sample-and-hold](../../../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) 在时钟沿采输入本身；
  - [v2-spec-055-first-order-sigma-delta-modulator](../../../v2-01/tasks/v2-spec-055-first-order-sigma-delta-modulator/instruction.md) 与 [v2-spec-307-switched-capacitor-integrator-phase-pair](../../../v2-01/tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/instruction.md) 的离散状态都在外部时钟或相位沿上更新。本题的离散更新由模型自己的网格驱动，外部时钟只读取，这正是要区分的错误模型（`update_on_clock`）。
- 第二批草稿：
  - [v2-spec-071-acquisition-limited-sample-and-hold](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md) 也按内部 tick 做一阶逼近，但更新只在采集窗内进行，由窗口门控，输出就是采集值；本题的网格从 t=0 起固定，不受 `clk`/`rst` 门控，由独立的外部采样器观察；
  - [v3-filter-envelope](../../../v3-01/tasks/v3-filter-envelope/instruction.md)（v4-336）是连续包络，没有离散网格和外部采样。
- 原56题：除上述各题外，没有其他题以 v3:441/442 为来源。本题 `source_group` 取新组名 `v3-441`（含 v3:442），SOURCE_GROUPS 中原无此组。
- R01：[r01-sampling-01](../../../r01-sampling-01/README.md) 与 r01-sampling-02 的孔径延迟都采样输入本身，属于 R01 家族。
- 规划中的同家族候选都尚未建题：
  - C250-S1：500 ps 离散一阶低通，单一定时输出，没有外部采样；
  - C265-S1：离散高通加外部采样（P1），与本题共享两套时间基准的结构，但真值不同；
  - C261-S1：连续高通加采样。

## 建模选择

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。原标"待用户确认 1–4"的第 3–6 条（待确认清单第 16–19 项）已定（用户 2026-10-29，决定单第 6 项），都按推荐，2026-10-29 修正 r7b 只改了状态。

1. 模块名由 `zi_nd_discrete_filter` 改为 `dt_lowpass_sampler`。理由：author_work 要把指定的算子调用改成行为合同，旧名直接点出算子；与 C260 的 `ct_lowpass_sampler` 对应。
2. 合同直接写差分方程与时间网格：更新时刻 `t_k = k*tupdate`（从 t=0 起，与 `clk`/`rst` 无关），`x_k` 是 `t_k` 时刻的 `V(vin)`，`y_k = 0.25*x_k + 0.75*y_(k-1)`，新输入在本更新时刻生效，更新之间保持。Deliverable 写明不要求特定算子、状态变量或事件组织；starter 只有 include、模块与端口声明和 TODO。理由：author_work 要求"可独立理解"、"不猜测等价递推"。原文只给 zi_nd 调用，解题者要自己推出采样时刻、是否有一拍延迟和保持方式；现在这些都写成可观察的合同。
3. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 1”，即待确认清单第 16 项】初态：`y_(-1) = V(vin)(0)`，即滤波器在 t=0 与输入平衡，与 DC 工作点一致。`dc-start`（`vin(0)=0.6 V`、首个采样在 6 ns）和 `tupdate-override`（`vin(0)=-0.3 V`）检验这一点。
   - 依据：历史 Spectre 21.1 的 zi_np 运行从平衡态起步；C260 也取平衡初态，两题一致。
   - 另一种读法是零初态（gnucap、旧版 EVAS 的 zi_nd、原 checker 的 zi_nd 分支），在这两个用例中失败（合成控制 450/225 mV）。
   - 推荐平衡初态并保留这两个用例。
4. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 2”，即待确认清单第 17 项】把更新周期暴露为参数 `tupdate`，默认 100 ns，合法范围 20 ns 到 1 us；终评 `tupdate-override` 用例取 130 ns。系数保持原题的 0.25 与 0.75，不设参数。
   - 理由：两套时间基准是本题的核心，具名的内部周期是这类合同的自然形式；终评改参数可以发现写死 100 ns 的实现（合成控制和旧版 EVAS 都只在该用例失败，325 mV）。
   - 另一种读法是照原题固定 100 ns、不设参数，或连系数也设成参数。推荐只设 `tupdate`。
5. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 3”，即待确认清单第 18 项】删去原接口中的 `mode` 端口、`vhi` 参数和 `metric` 输出，接口改为 `(vin, clk, rst, out)`。理由：原文说明 `mode` 只为旧 harness 兼容、`vhi` 不缩放输出；`metric` 与 `out` 恒等。与 C260 的处理相同。推荐删去。
6. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 4”，即待确认清单第 19 项】两套时间基准同刻（author_work 的"双采样同刻关系"）：合法域要求每个 `clk` 上升穿越离任何更新时刻至少 0.5 ns；在此域内，采样取穿越之前最近一次更新的值。
   - `dc-start` 有 6 个采样落在更新前或后 0.6 ns，原 441 台架的采样也在更新前 0.55 ns，历史 Spectre 给出更新前的值；
   - 理由：正好同刻时，结果取决于仿真器对同刻事件和 zi 输出突变点的排序，合同若规定"先更新后采样"，评的是事件次序而不是滤波器；
   - 另一种读法是在合同中规定同刻规则并加同刻用例。推荐排除同刻。
7. 插值：`y` 在两次更新之间保持 `y_k`，不插值，也不跟随 `vin`；`x_k` 是瞬时值，不是区间平均。`base` 中 422–458 ns 的 36 ns 负脉冲完全落在两次更新之间，正确模型看不到它。插值（zi 过渡时间取 `tupdate`）和区间平均模型都失败（合成控制最小 156 mV）。
8. 采样语义沿用原文：上升沿过 `vth` 为采样事件；采样时 `rst` 高则采样值为 0 V，否则为当时的 `y`；两次采样之间采样值不变；第一次采样前为 0 V（原 starter 的初值）。`rst` 只在采样事件被读取，滤波器在复位期间照常更新。复位清滤波、复位冻结滤波和异步清零都是错误模型。
9. 输出：采样后 `tr` 内到达新值，`tr` 内的波形不作规定（smoothstep 形状的合成控制通过）；采样事件后 `1.25*tr` 内的点不评分，其余所有保存点都评分；误差上限 2 mV；评分波形步长不粗于 `tr/4`。
   - 评分起点与到达期限（F01）：用户已确认（2026-10-28，经项目协调方答复“全部按推荐”，F01 选题面写明实际观察起点），题面已写明“Every saved point is scored except points less than `1.25*tr` after a sample event.”，checker 不动。期限 `tr` 与评分起点之间到达不区分，这是题面写明的余量。
   - 迟到负例（p0-fix-a 补齐）：原三个用例的采样穿越都在 50 ps 网格上（如 `base` 在 12.0 ns），`1.3*tr` 之前唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，被拒矩阵对这三个用例不设预期。私有用例 `vth-tr-override` 的采样穿越在网格的 0.9 处，每个事件后 127.5 ps 有评分行，落在 `(1.25*tr, 1.3*tr)` 内。迟到负例 `late_arrival_1p3tr` 在该用例被拒：13 次保持值变化中 9 次超过可见门槛 104 mV，其余 4 次列为例外。窗内对照 `margin_arrival_1p2tr`（`1.2*tr`）在全部用例通过，这是用户已接受的余量。这些是合成控制与旧版开发证据，待 Spectre 复跑。
   - 2 mV 与首批同类规格及 C260 一致；
   - 正确实现在旧版 EVAS 上的误差为 0.0 mV，历史 Spectre 复核误差小于 1e-13 mV；
   - 合成错误模型中最小的误差是"更新后 2 ns 才读 vin"（4.1 mV；`dc-start` 87.5 mV），其余都大于 90 mV，例外是只在对应用例才区分的写死 `tupdate`、零初态和夹位。
   原 checker 只取 3 个点、按 12 mV/2% 判定，过宽，不沿用。
10. 合法域（原题没有）：
    - `vin` 连续，范围 -1 V 到 +1 V；`base` 中保持值会转为负值，可检验无夹位；
    - 控制电平 0/0.9 V，边沿不长于 200 ps，`vth` 在两电平之间；控制到达 `vth` 时必定穿过，不触碰后返回，不停在 `vth` 上，t = 0 时离 `vth` 至少 50 mV（后两条是 p0-fix-c 按第 38 项的推荐写入的，见 p0-fix-c 一节；第 38 项用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版；其中 t = 0 的 50 mV 一条已定（用户 2026-10-29，决定单第 11 项），即待选清单第 40 项）；
    - 相邻上升沿至少 5 ns，高低电平各至少 2 ns，`rst` 跨阈值离任何采样事件至少 1 ns，上升沿离任何更新时刻至少 0.5 ns；
    - `tr` 范围 10 ps 到 1 ns。
11. 台架：四个用例。前三个用 50 ps 输出网格（`maxstep=50p strobeperiod=50p`），`vth-tr-override` 用 25 ps（`tr/4`）。所有 PWL 拐点和所有更新时刻都落在各自的网格上，checker 从行数据读取 `x_k` 时没有插值误差；`vth-tr-override` 的 `clk` 是脉冲源，拐点不在网格上，但每个穿越两侧的网格行都在同一段线性边沿上。
    - `base`（公开兼终评）：30 ns 规则时钟，每次更新之间 3–4 个采样；两次更新之间的阶跃与负脉冲；穿过更新时刻的斜坡；保持值转负；跨 4 个采样的复位期间 `vin` 阶跃；不跨沿的短 `rst` 脉冲。
    - `dc-start`：平衡初态；不规则时钟，含一个更新区间内的连续采样、跨两次更新的 229 ns 间隔，以及更新前后 0.6 ns 的采样；400 ns 更新后 1.5 ns 的输入阶跃；跨 2 个采样的复位、单采样复位脉冲、结尾复位保持。
    - `tupdate-override`：`tupdate=130 ns`；45 ns 时钟；`vin(0)=-0.3 V`；跨 6 个采样的复位期间满幅阶跃；穿过两次更新的慢斜坡。
    - `vth-tr-override`（p0-fix-a，审核 F04）：`vth` 0.8 V、`tr` 100 ps；`clk` 周期 30 ns、边沿 180 ps，0.8 V 穿越在 12.0225 + 30k ns，比下一个网格行早 2.5 ps，0.45 V 门限会提前 70 ps 采样；`vin(0)=0.5 V`；负保持值；跨一次更新的两次采样复位、单采样复位脉冲、不含采样的短 `rst` 脉冲、结尾复位保持。
    前三个用例由 build_cases.py（`runs/t3-p0-build-20261027/r06-spec-dt-lowpass-sampler/build_cases.py`） 生成，`vth-tr-override` 由 c264_cases.py（`runs/t3-p0-build-20261027/p0-fix-a/scripts/c264_cases.py`） 追加，两者都在生成时断言上述台架义务。
12. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：
    - 按记录的 `vin`（相邻行间线性）在每个更新时刻取 `x_k`，用平衡初态递推出 `y_k`，在记录的上升沿时刻取最近一次更新的值；
    - 台架义务出错时抛出异常（无判决，不记候选失败），包括分辨率、`vin` 超域、参数超域、时钟间距、上升沿与更新时刻间距、`rst` 与采样沿间距，以及控制在 t = 0 离 `vth` 不足 50 mV、控制停在 `vth` 上（这两项是 p0-fix-c 加的）；
    - 穿越提取用六题统一的规则（p0-fix-c，审核 R2-01、R2-02；p0-fix-a 先按 F02 改成按两侧符号变化识别）：每个保存点与阈值精确比较，恰在阈值上的点不属于任何一侧；相邻两个不在阈值上的点分处两侧时记一次穿越，中间恰有一个阈值点时时刻取该点，否则在两点间线性插值；孤立的阈值点两侧同侧，即触碰后返回，不算穿越；连续两点恰在阈值上表示控制停在 `vth`，抛出异常、不判分，平台后跨到另一侧、回到原侧或记录在平台上结束都一样；记录末尾单个阈值点按到达方向算一次穿越；记录开头的阈值点不生成穿越；
    - 不依赖任何仿真器特有行。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
13. 参考解按 LRM 与 Spectre 语义写：`zi_np(V(vin), {0.25}, {0.75, 0.0}, tupdate, 0.0)` 在连续上下文中计算，过渡时间显式取 0 使更新之间严格保持（只赋给变量，不直接赋给支路），cross 事件只读取它的值，`transition` 驱动输出。参考解没有为任何 EVAS 版本改写。
    - 选 zi_np 而不是主来源的 zi_nd：两者是同一 `H(z)`，但只有 zi_np 有 Spectre 平衡起步的历史证据；旧版 EVAS 0.8.7 的 zi_nd 从零历史起步，最初写成 zi_nd 的参考解在 `dc-start`、`tupdate-override` 上失败（450/225 mV），改成 zi_np 后三个用例都通过。zi_nd 写法保留为校准候选 `alt_zi_nd`，它在 Spectre 上的起步状态待记录。
    - 这些都是开发证据，不改合同。
14. 参考解是作者按新合同自写的，没有复制公开代码。但它的结构（zi 算子、cross 采样、transition 输出）与公开仓库中原 v3:441/442 gold 相同，这是这类模型最常见的写法。原 gold 自 2026-07 起在公开 GitHub 上，评测时应考虑记忆污染。新合同改了模块名、接口、`tupdate` 参数和初态规则，原 gold 原样提交不能通过，但核心写法容易改编。
15. 校准候选见 [tests/calibration](tests/calibration/README.md)：20 个错误模型、3 个正确替代实现（含只用标量状态和 timer、不用 zi 与 `absdelay` 的 `alt_timer_recursion`）和 1 个余量对照 `margin_arrival_1p2tr`，被拒矩阵另存为 `expected.json`。其中 `late_arrival_1p3tr`、`fixed_vth`、`fixed_tr` 和余量对照是 p0-fix-a 加的。

## p0-fix-a 修正（2026-10-28）

依据是 P0 铺开题的独立审核 astra-review.json（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）（F02、F04、F11）。修正记录、命令与结果见 p0-fix-a/disposition.json（`runs/t3-p0-build-20261027/p0-fix-a/disposition.json`）。题面和参考解没有改，公开用例与公开台架也没有改。公开 checker 副本与私有副本一起改，仍逐字节相同。

1. 穿越提取（F02）。原写法 `a < level <= b or a > level >= b` 把“到达阈值后返回原侧”的触碰算成一次穿越，而且没有返回事件。在修正前的字节上复现：`clk` 从下方触到 `vth` 再返回，checker 虚构一次采样，正确输出被拒；`rst` 在采样后 0.5 ns 触到 `vth`，checker 报台架越界，不给判决。改为按阈值两侧的实际符号变化识别（规则见第 12 条）。真正经过阈值行的穿越与原写法结果相同，在终点到达阈值也与原写法一样算穿越；变化只在触碰。建题时的全部合成控制与旧版波形重判，判定都不变。题面把事件定义为穿过 `vth` 的穿越，不必改。
2. `vth`、`tr` 覆盖与迟到负例（F04 和第 9 条待补项）。原三个用例只覆写 `tupdate`，写死 0.45 V 门限或 200 ps 过渡的实现能通过全部固定用例。新私有用例 `vth-tr-override`（第 11 条）加 `vth` 0.8 V 和 `tr` 100 ps；180 ps 边沿让 0.45 V 门限提前 70 ps 采样，事件前的评分行能看出来；采样穿越在网格的 0.9 处，`1.3*tr` 的迟到有评分行可见。校准候选加 `late_arrival_1p3tr`、`fixed_vth`、`fixed_tr` 和余量对照 `margin_arrival_1p2tr`，进被拒矩阵。`rst` 在每个采样时刻都在 0 V 或 0.9 V，用错门限读取不改变结果，所以 `fixed_vth` 只靠 `clk` 穿越时刻暴露。
3. 校准说明（F11）：`tests/calibration/README.md` 改为中文，候选名、命令、诊断与引用保留原文。
4. 【已定（用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版）；原标“待用户确认 5”，即待确认清单第 38 项】精确触碰的语义（p0-fix-a 发现，交Benchmark 维护方）。归档的 Spectre 21.1.0.509 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 显示：输入恰好到达阈值时，`cross()` 触发一次“到达”事件，到达后返回原侧也触发，离开时不触发。这正是原 checker 的提取规则。F02 修正后的 checker 不把触碰算作穿越，与题面“穿过 `vth`”一致；但参考解用 `cross()`，在 Spectre 上遇到精确触碰会采样，新 checker 会判它错。
   - 本题控制是 0/0.9 V 逻辑信号，精确触碰不算一次切换，所以判断它不在合法域内。在全部合法台架上，两种规则的判定相同；固定用例没有触碰，旧版波形重判 0 项变化。
   - 旧版 EVAS 0.8.7 在触碰探针上没有触发（f02-touch-semantics.json（`runs/t3-p0-build-20261027/p0-fix-a/evidence/f02-touch-semantics.json`）），与 Spectre 不同，不能用来定论。
   - 推荐：在题面写明控制到达 `vth` 时必定穿过它，不会触到后返回原侧。这只是把现有输入域写明，不改 checker 和参考解。
   - 另一种读法：按 Spectre 的到达语义把触碰也算作事件，那样应撤回 F02 修正。
   - 本单没有改题面，由Benchmark 维护方与另一子任务的同类修正统一决定。

本节的检查都**未仿真**；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-02 与 F02 剩余部分，以及Benchmark 维护方 2026-10-28 对清单第 38 项的安排。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解、用例、公开台架和校准件都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 阈值平台（R2-02）。p0-fix-a 的写法把连续两行以上停在阈值上的平台当作可评分输入，而题面已写明控制不停在 `vth` 上。在修正前的字节上复现：`rst` 在 10.000 ns、10.050 ns 两行恰为 0.45 V，平台后跨到另一侧、回到原侧、记录在平台上结束，三种都得到判决（都通过）。现改为六题统一的穿越规则（第 12 条），三种都抛出异常、不判分，记录开头的两行平台也一样。记录末尾单个阈值点仍按到达方向算一次穿越；触碰和恰有一个阈值点的穿越，判定与修正前相同。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 【第 38 项，已按推荐写入；用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版】控制到达门限时必定穿过。题面合法输入一段在“Controls never rest at `vth`.”之后加两句：“A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. At t = 0 each control is at least 50 mV away from `vth`.”checker 加对应的台架检查：`clk` 或 `rst` 在 t = 0 离 `vth` 不足 50 mV 时抛出异常。
   - 这两句只约束外部驱动的控制输入。p0-fix-a 一节第 4 条（原标“待用户确认 5”）就是这一项。
   - t = 0 的 50 mV 余量是缩域，不是对原合同的无损澄清：原合法域只要求 `vth` 严格位于 0 V 与 0.9 V 之间。新加的是输入初态与 `vth` 的联合约束，不是把参数一律收窄：控制都从 0 V 起步时，要求 `vth` ≥ 0.05 V（可到 0.9 V 以下）；有控制从高轨起步时，另要求 `vth` ≤ 0.85 V；要让任意高低初态都合法，公共范围才是 0.05–0.85 V。本题 `clk` 从低起步，前一条总适用；`rst` 可以从高轨起步，此时适用后一条（p0-fix-d 按 P0 r3 复审 R3-05 更正，与待选清单第 40 项一致）。四个用例的 `vth` 是 0.45 V 和 0.8 V，都满足，判分不变。用户若不要这一缩域，只需删去第二句和 checker 的起始检查。已定（用户 2026-10-29，决定单第 11 项，即待选清单第 40 项）：保留这一缩域，按推荐。
   - 另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
3. 复核：
   - 行模式表在六题 checker 上相同；本题与修正前只差在平台，现在报错。
   - p0-fix-a 的合成控制与 F01–F11 复现脚本复制到 p0-fix-c 后在新 checker 上重跑，判决与误差与存档逐项相同；建题时的证据有效性控制仍全部报错、不判分。
   - 建题以来的旧版存档波形（含 p0-fix-a 的运行与触碰探针）用新 checker 重判，判决与误差 0 项变化。本题用例未改，没有新的旧版运行。
   - 平局扫描（精确有理数）：参考解的过渡终点都不在输入穿越上。`dc-start` 205 ns 处 `vin` 的一个拐点与 `clk` 的下降穿越同刻；按Benchmark 维护方 2026-10-28 的口径，PWL 拐点不是事件，`clk` 下降穿越也不是本题的事件，不算平局，未改。事件与事件同刻的只有 `base` 657 ns 处 `clk` 下降与 `rst` 下降，两者都不是事件。

第 38 项的三个前提（Benchmark 维护方 2026-10-28 定的口径，也作复审口径）：
- 内部恰为零：参考解的事件只看外部驱动的 `clk`（`cross(V(clk) - vth, +1)`），`rst` 只在采样事件读电平，`zi_np` 的更新由内部时间网格驱动；没有被测模块内部恰为零的信号参与事件或判决，无需核对。执行细则（Benchmark 维护方 2026-10-28 转标准审核口径，p0-fix-d 写入，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。本题参考解只对外部驱动的 `clk` 用 `cross()`，符合（p0-fix-d 核对）。
- 相等规则写成输出行为：题面没有内部相等规则；控制恰在 `vth` 上由合法输入排除（第 2 条）。
- 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r06-spec-dt-lowpass-sampler/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制；
- 旧版 EVAS 0.8.7 冒烟，含参考解、起始模型、全部校准候选和诊断探针（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）；
- EVAS 02dee32b 阶段 a–c；
- Docker 两个镜像实际构建一次并检查。

p0-fix-a 的检查（findings 复现、合成控制、旧版运行与重判、结构检查、Docker）另记在 checks.json 的 `p0_fix_a` 一节；EVAS 02dee32b 没有对新用例重跑。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量；
- Spectre 上记录 zi 算子细节：zi_np 与 zi_nd 的起步状态是否都等于 `H(1)*V(vin)`、`t0` 参数和 zi 过渡时间的效果（对应 `alt_zi_nd`、`half_period_phase`、`interpolated_between_updates`）；
- 本题合同内没有待发事件：相邻采样至少 5 ns，输出过渡最多 1 ns，上升沿离更新时刻至少 0.5 ns。Spectre 运行时仍记录 `transition()` 的待发过渡行为，以及更新前后 0.6 ns 的采样与 zi 更新的执行次序；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 上面五个"待用户确认"选择中，建模选择第 3–6 条的四个（待确认清单第 16–19 项）已定（用户 2026-10-29，决定单第 6 项），p0-fix-c 一节 t = 0 的 50 mV 余量（待选清单第 40 项）已定（用户 2026-10-29，决定单第 11 项），都按推荐，修正 r7b 改了状态；
- 第 5 个"待用户确认"选择（在 p0-fix-a 一节，即清单第 38 项）已定（用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版）；p0-fix-c 已按推荐写入题面，见 p0-fix-c 一节，题面不再改；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## 2026-10-29 修正 r7b（p0-fix-r7b）

依据：扫描 B 报告第 4 节 (k) 项与第 10 节（项目协调方 2026-10-29 批准本轮，本题只做容差写入）；用户 2026-10-29 答复的决定单。改前改后的 sha256、脚本、命令与退出码见本轮记录 runs/t3-p0-build-20261027/p0-fix-r7b/disposition.md（不入库）。本节**未仿真**：没有运行 Spectre、EVAS 或旧版 EVAS。

1. 容差写入（第 (ii) 类；标准审核 2026-10-29 给的值）。6 份网表（4 个私有用例、公开 `cases.json`、`visible_test.scs`）都在 tran 行之前另起一行写 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，tran 行末补 `errpreset=moderate strobeoutput=strobeonly`，其余字节不变。5 个用例网表写入后再加执行路径一行，与预校准包 P0PC-must-01（包 spectre-P0PC-must-01-v1，结果包 sha256 `56bb45ddcc96029e2ee7bd556bdd9b26db70f2186f91bff0653353d43b837ad6`，已核收）的同例参考解作业网表逐字节相同；`visible_test.scs` 与公开用例只差 include 路径。所以已核收的结果仍然作数，激励没有变，不需要新的 Spectre 作业。题面、checker、参考解、校准件都没有改。
2. 决定单状态：建模选择第 3–6 条（原标“待用户确认 1–4”，待确认清单第 16–19 项）改为已定（用户 2026-10-29，决定单第 6 项）；p0-fix-c 一节 t = 0 的 50 mV 起始余量（待选清单第 40 项）改为已定（用户 2026-10-29，决定单第 11 项），保留这一缩域。理由原文不动；合法域一条与待办同步。Benchmark 维护方随后照 C109 的写法，把第 38 项（决定单第 4 项）的状态行同步为已定，只改状态行。
3. 写入容差后，相邻两次 `clk`、`rst` 穿越之间离 `vth` 的最小偏离仍是 0.1 V（`vth-tr-override`），远大于最宽的缺省 expr_tol（写入容差后最大 0.801 µV，缺省容差对照 0.800 mV），只作记录。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 1 处台架义务检查（C264-04，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `308b824e568bc8f637e02ec35dba9b070d555d8255d591e6e776b24d738d2587`，改前 `e400cd4e…`）与本文件。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **C264-04**（evaluate 第 94、102 行调用 `crossings`，第 38–40 行）：`clk`、`rst` 的保存行上相邻两行恰为 `vth`（停留）报台架错误 → 按定义判；`crossings()` 去掉这一句，穿越的定义不动。
- 随同改（决定第 1 项，起点）：evaluate 第 86–87 行 t = 0 那一行离 `vth` 不足 50 mV × (1 − 1e-6) 报错 → 按定义判，门槛不变。
- 碰到：改前只当“不算穿越”，现在报台架错误（决定第 2 项）。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`clk`、`rst` 各自对 `vth`。`check_stimulus` 放在原来起点检查的位置，在取穿越与判分之前。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 7 个、pulse 5 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”；离 `vth` 不足 0.04999995 V（`START_MARGIN` × (1 − 1e-6)），报 “starts … closer than …”；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：判分用的穿越仍由原来的 `crossings()` 从保存行取，穿越的定义不动，只去掉其中“相邻两行恰在门限上就抛出异常”一句。保存行恰在门限上（例如模块在同一输入、同一门限上求根时写下的根处行）不再引起台架错误。

### 3. 余量（数值未改）

- 起点：50 mV 乘 (1 − 1e-6) 不变，报错门槛 0.04999995 V；按定义精确比较以后相对余量只是容让，数值未改。本题没有最小偏离检查。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`clk`、`rst` 各自对 `vth`）的起点、停留、碰到按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点对地；没有叠放源（本题网表里受查节点各由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 6 份网表（私有 4、公开 `cases.json` 1、`visible_test.scs` 1）共 18 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 12 个（PWL 7 个、pulse 5 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(x)` 与 `vth`，参考解在 `V(x) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `dt_lowpass_sampler` 只在 `cross(V(clk) - vth, +1)` 上求根（`rst` 按电平读），就是受查输入本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，6 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 6 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前只当“不算穿越”，现在一律报台架错误。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到：instruction.md 第 25 行 “Controls never rest at `vth`. A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. At t = 0 each control is at least 50 mV away from `vth`.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 29 行 “A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：6 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 434 行）。12 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（12/12）。
- B 候选：扫描列出的 24 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（24 组不同的行，共 4957 行）。改前、改后判决逐个相同，新 checker 不报台架错误（24/24）。
- C 变体（在 `base` 上改 `rst` 的定义；每个变体事先写下预期），12/12 符合预期：
  - `rst` 起点按十进制恰在门限上：报 “starts on”
  - `rst` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `rst` 起点离门限 0.0498999 V：报 “closer than”
  - `rst` 起点离门限 0.0500999 V：不报台架错误（照常判分）
  - `rst` 在 2.70475e-07 s 处按十进制停在门限：报 “rests on”
  - `rst` 在 2.70475e-07 s 处只在 binary64 下停在门限：报 “rests on”
  - `rst` 在 2.70475e-07 s 处按十进制碰到门限：报 “touches”
  - `rst` 在 2.70475e-07 s 处只在 binary64 下碰到门限：报 “touches”
  - `rst` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `rst` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `rst` 的源有一个值带单位 `0V`：报 “cannot read”
  - `rst` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-02-v1 27、spectre-P0PC-rec-05-v1 40、spectre-P0PC-rec-06-v1 53，共 130 个。new 与改前 checker 整份判决 130/130 相同。与原判比 status、passed 与台架错误的有无 130/130 相同，整份判决 sha256 也相同。

### 8. 前面各节的相关句子

- 建模选择第 94、95 行（台架错误里的“控制在 t = 0 离 `vth` 不足 50 mV、控制停在 `vth` 上”，穿越提取里“连续两点恰在阈值上表示控制停在 `vth`，抛出异常”）：起点、停留、碰到改按定义判，碰到报台架错误；穿越时刻的取法不变。
