# 事件、时间推进与历史

适用范围：IR16 的受限事件体条件、cross OR 与多事件写者；当前与历史检查点身份见
[能力总表](CAPABILITIES.md)。能力 ID 为 LANG、CROSS、TIMER、EVENT-ORDER、COMPOSE。

共同重构的第一批审查从[生命周期契约](../validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract)进入：
首次初始化、已知历史续算、实际复位、只读观察及原子提交分别定义。
数学根 tau、实际触发 te 与内部代表时刻 b 也分别记录。
本页已有的同刻联立规则是 EVAS 当前选择；特别是非点 cross 的真根条件约定，
不能被读成 LRM 要求所有事件体在真根处读取。第一批反例/对照不修改当前求解器。

<a id="event-or"></a>

## cross 的事件 OR（0.9.0）

`@(cross(g0,...) or cross(g1,...) ...)` 表示一个事件体的触发集合
`E_B = E_0 ∪ E_1 ∪ ...`。这是事件集合合并；每个调用继续独立监测自己的 guard、方向、
时间容差及表达式容差。依据与首版选择见[独立契约](../validation/EVENT_CONDITIONS_CONTRACT.md#trigger-set)。
首版只接受两个以上的 cross 叶子，拒绝 timer 混合及原始 IR 中的空/单叶/嵌套 OR。

OR 结构由 IR v9 引入，当前 IR16 继续使用 `trigger/body/origin` 事件块，OR trigger 内保存 cross 列表。
`EventModel` 为叶子保存 `(block, leaf)` 身份，写者与赋值路径仍按 block 管理。
日程按叶子定位和认证；只有证明同根且共同代表时间满足每个叶子的容差后，
候选批次才将 block 去重，并调用既有顺序赋值和电压联立求解。
不同块或不同实例仍分别执行。不同根即使相距小于 ttol 也不能合并；无法认证排序时拒绝。
事件预算统计所有叶子的根，去重不能绕过预算。

一个 OR 块产生一条 `kind=or` 记录；`fired_triggers` 保存实际触发的叶子索引、guard 值及
原始根时间包围 `time_bounds`，不会只保留第一个触发源。日程、候选帧和记录都经过验收后
才提交；失败候选丢弃，叶子游标与已接受算子历史均不改变。

### guard 只在相关输入断点上定位

状态独立的仿射 guard 可写成 `g_j(t)=b_j+Σ_k a_jk u_k(t)`。
原实现用所有输入断点的并集划分每个 guard；无关输入在根旁新增断点时，
一个真实根可能落入极短区间，算术包围越过区间边界，从而保守拒绝本可认证的事件。
C1 的第二实例及独立的无关输入断点探针实际复现了这种拒绝。

现在用认证后的系数区间选择输入：**只有系数区间恰为 `[0,0]` 才排除该输入**，
不采用“小于某阈值”的判断。所选输入的原 PWL 断点与 0/stop 的并集，足以保证
每一段上的 g_j 仿射；因此没有遗漏 guard 的斜率变化。全电压网络在全部物理输入断点上的
一致性检查仍保留。区间包含不确定非零系数时保守保留该输入；根误差、表达式误差、
同根证明及不确定次序的拒绝规则不变。

实现入口：`syntax.py`/`frontend.py`/双侧 `ir` 定义一块多叶；`event_accuracy.rs`
认证 guard 系数及相关输入；`pwl.rs`/`schedule.rs` 生成逐叶日程；`transient.rs`
在提交前按块去重并保留全部叶子记录，随后复用 settlement 的条件选择与原关系验收。
独立回归在 `test_event_or.py`；实际已接受帧的失败/重试检查在
`transient_condition_tests.rs`。数学/测试方法数与原 31 条件计数分别记录。

0.9.0 OR 历史检查点的剩余边界包括反馈或非线性 guard、timer OR、多块同状态写入、
全部故障点的系统性注入及完整连续时间误差资格。后续多写者的受限扩展见
[本次交付](#multiple-event-writers)，不改写该历史检查点的范围。

## 连续动态与多项式 guard

IR16 已合并状态独立多项式及受限连续算子驱动 cross；值/导数区间隔离根，
同号端点及末端零点不能跳过内部根。切线、平台、事件修改轨迹或不能证明的次序明确失败。
数学、实现和独立测试见[连续动态章节](CONTINUOUS.md#非线性-guard-的根证明)。
下面仿射根公式与触零约定仍仅用于原 PWL/仿射路径。

## 仿射轨迹上的数学定位

固定状态与固定系数的仿射网络在一段 PWL 输入上给出仿射 guard：
`g(t)=g_a+m(t-t_a)`。若 m≠0，候选根为 `t*=t_a-g_a/m`；还需验证段内位置、方向和误差界。
根公式本身不能决定触零/零平台、初始点或同刻状态读取，这些是下面单独定义的行为。
区间包围针对输入 binary64 数值定义的数学问题，不意味着任意源表达式/后端都无误差。

<a id="backend-cross-tolerances"></a>

### 后端定位方式、容差与波形差异

EVAS 与 Spectre 可以满足同一事件契约，却在容差允许范围内选择不同的触发时刻。
EVAS 在当前受限 PWL/仿射范围内从分段关系求根、包围根误差，再选择并认证可表示的事件时间。
Spectre 的闭源实现不能由波形反推出完整算法；本次 V3 实验确认其实际触发时刻受 cross
容差及时间步设置影响。相同容差数值不保证相同的事件时刻，也不代表两者采用相同的误差控制。

[Verilog-AMS LRM 2.4 §5.10.3.1](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
要求 cross 事件在过零后、同时满足时间与表达式容差。对本例局部线性 guard，斜率绝对值为
`|m|`，可允许的延后为 `min(ttol, expr_tol/|m|)`。V3 中 `ttol=1 ns`、
`expr_tol=200 μV`、`|m|=0.4 V/μs`，因此窗口为 500 ps；Spectre 基础档实际晚 250 ps，
仍位于这个窗口。输出 transition 的斜率为 `0.8 V/50 ns`，此时间偏移对应边沿上的 4 mV
名义波形差值；平台电压及 50 ns 边沿时长相同。

事件日志和六次诊断执行见[实验收据](../../experiments/pr14-pr15-validation/results/event-writers-timing.json)。
只收紧 cross 表达式或时间容差显著减小了偏移；只收紧全局求解容差没有减小本例偏移。
这支持事件定位差异的解释，不证明 Spectre 出错、EVAS 普遍更准确，或其他模型也遵循相同比例。

后端比较应同时报告独立数学答案、允许的事件历史、实际设置与观测波形差值。
容差内的差异可以与双方达标并存；超出独立契约的差异仍须作为失败保留。
不能事后扩大容差、逐点任意平移波形，或用后端相互接近代替正确性判断。

## PWL 与事件的执行契约

这是限定实现范围，不是完整 Verilog-A 事件支持。语言依据见
[LRM 2.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf) 和
[事件语句参考](https://verilogams.org/refman/modules/analog-procedural/timing.html)。

- 声明标量 `integer` / `real` 状态，每个状态必须恰有一次 `@(initial_step)` 常数赋值，
  可以引用有效实例参数；暂不接受依赖电压或其他状态的初始化。初始化常数在绑定时确定，
  Rust 在 t=0 的首次求解前安装一次。初始高电平、初始零值的离开本身不产生 `cross`。
- `@(cross(g[, direction[, ttol[, tol]]]))` 接受空语句、顺序赋值或下述受限 if/else 块。方向为 -1/0/+1，默认 0；
  两项容差必须为正的有限实例常数，默认分别为 1 ps 和 1e-9 表达式单位。不支持 cross enable；cross 的受限 `or` 见下节。
- 事件同刻贡献及赋值表达式仍须对电压和状态联合仿射；更广连续多项式贡献、积分和 guard
  的限定范围见[连续动态](CONTINUOUS.md)。以下仿射事件规则继续适用。
  0.4.4 根据 IR 结构保留变量依赖，不以舍入为零的系数证明某项为常量；变量表达式之间的乘法拒绝，
  即使存在代数抵消也可能保守拒绝。区间转换另行检查，不能静默丢弃乘积项。
  整数状态采用精确 signed 32-bit 范围，仅接受整数常数/整数状态运算，超范围报错，不模拟溢出或隐含取整。
  real 状态可以在事件时采样仿射电压表达式。
- 每个实际候选批次中，每个状态最多由一个 cross 或 timer 事件块写入。
  不同事件块可以在可证明不同批次触发时写同一状态；若同一批次实际选中的两个块写同一状态，
  返回 `event_conflict`，不按声明顺序、源码位置或事件类型决定胜负。
  构建期仍拒绝事件块直接读取另一个事件块也可能写入的状态，避免隐藏的跨块顺序依赖。
  同块语句依次看到自己的更新。
  0.5.3 支持同块对同一 integer 状态重复赋值，和 real 一样逐句更新局部状态。
  每次 integer 赋值都检查精确整数及 signed 32-bit 范围，后续写回合法值不能掩盖中间越界。
  与特定 Spectre 版本的重复赋值差异见下文，不将其作为整体拒绝合法程序的依据。
  事件块不能直接读取其他事件块写入的状态。0.5.1 起，同刻事件从同一份事件前状态出发，
  将更新 `s+=Phi(s-,v+)` 代入原电压方程，联立求解同刻电压；同块赋值顺序保留。
  求解后重放原赋值、检查原电压方程残差与状态一致性，再整批提交。整数状态精确一致，
  real 状态重放使用 `reltol * max(abs(state), abs(replay))`，不借用电压绝对容差。
  0.5.2 另从原 IR 用向外舍入独立重建联立方程，包围事件后的电压和状态；
  电压误差须小于 `vabstol + reltol*abs(v)`，real 状态误差须小于 `reltol*abs(state)`，
  integer 状态须精确。预算取向下界、误差取向上界，不能认证时返回 `event_accuracy`。
  real 状态没有绝对误差下限，接近零或舍入严重的合法问题可能被保守拒绝。
  历史检查点的无条件、无算子路径把事件前状态和采样驱动作为给定点量；含条件路径才携带
  PWL 与跨事件状态包围。IR v15 精度链修复统一在初始化、事件候选及普通观察时刻使用
  原 PWL 输入包围和已接受 `Frame.state_bounds`，不以条件或算子是否存在为精度开关。
  新状态区间随成功批次提交，失败候选不改变它；后续放大必须继续验收这份不确定性。
  无算子的观察仍复用固定电路分解，认证失败前不更新接受帧。冗余关系若只在某个状态点成立，
  而非误差映射状态域的恒等式，可能在初始化就明确拒绝。
  [独立采样/跨事件回归](../tests/test_precision_chain.py)和[review 记录](../../experiments/parallel-gap-integration/REVIEW.md#precision-chain)
  记录该变化。均不覆盖前端常量折叠，也不是通用物理单位误差保证。
  无唯一数值解或不能通过一致性检查时明确拒绝，失败不消费事件。容差不用于合并相邻事件。
- guard 不得直接依赖状态，也不能通过电压方程间接依赖状态。Rust 用方程连通性保守检查，
  排除固定驱动和地；即使某种代数抵消可能消除依赖，也可能明确拒绝，避免依赖浮点阈值漏检反馈。
- 每个驱动用连续 PWL 点列描述，从 t=0 开始、时间严格递增且覆盖 stop；不接受重复时间造成的跳变。
  `output_times` 是 [0,stop] 内严格递增的有限观测时刻，`stop/max_step` 均为正且有限。
  观测时刻会实际求解；若恰逢接受的事件时刻，返回事件后电压。事件不必落在输出网格上。

通过上述限制，固定状态下的方程系数不变，输入每个分段内的节点电压和 guard 都是时间的仿射函数。
guard 的状态独立性允许提前生成事件日程。0.4.3 同时进行普通求解和保守误差界计算：

1. JSON 保留 Python 提交的 binary64 值；以编译后 IR 系数及 PWL 点的这些精确数值定义仿射问题。
2. 区间四则运算向外舍入，覆盖原 IR 的贡献累加、消元、输入插值和 guard 求值。
   电压、驱动和状态的传递系数一次性准备；所有状态系数必须能证明为零。
   主元区间包含零，或冗余约束不能证明为恒等式时，明确拒绝。
3. 从断点 guard 区间包围真实仿射根，得到 `[t_lo,t_hi]`；候选时间取可表示的 `t_hi`。
   0.5.2 在端点 guard 均为精确单点时，用四个 binary64 乘积和的精确符号，
   在有效根包围内对可表示时间作至多 64 次二分；找到精确根才收缩为单点。
   非可表示根和不确定端点仍保留区间；不能先建立有限、严格位于段内的根包围时仍拒绝。
   对斜率区间 `m`，用向外舍入验证 `t_event-t_lo <= ttol`，以及
   `max(abs(m))*(t_event-t_lo) <= tol`。根区间、可表示时间和求值误差都进入验收。
4. 重合事件须有相同 guard、可证明成比例的仿射式/端点，或相同的精确根；
   统一时间后重新检查各自容差，共享事件前快照。不同根的误差区间重叠且无法确认顺序时拒绝，
   不按 `ttol` 合并邻近根。普通求解的 guard 和事件后原支路残差仍须通过检查。

不能确认断点符号、根误差超限、根间顺序不明、时间不可表示等情况返回 `event_resolution`。
误差界可能偏宽，数值上本来可解的电路也可能被保守拒绝；不自动放宽容差，不用表达式容差过滤小信号。
界限针对编译后 IR 所定义的仿射实数问题，不覆盖前端常量折叠误差、任意非线性或微分轨迹。
区间准备另有稠密消元和传递系数存储开销。同刻状态认证只缓存最近一批事件的
符号传递系数；0.8.0 的键还包含选中语句与分支决定。缓存不保存已接受/候选状态，
批次或路径变化时替换，不随事件次数增长。
小规模重复事件测量见下述 0.5.2 证据，不据此声明大型网络性能或仿真器排名。
用于定位的初始化状态冻结试算也必须可解；不能完成时直接报告错误。

0.4.6 中，精确零点归到达段所有：若相邻 guard 值为 `a,0`，且 `a` 非零，
则方向为 `-sign(a)`；按 direction 过滤后执行一次，不依赖下一段是否存在或返回哪一侧。
这包括内部孤立零点、零平台入口及 stop。零到零、零到非零都不触发；初始零平台和
恒零输入也不产生事件。再次经过非零段到零时可以重新触发。只有区间能证明精确为零时才走此规则，
不以 `abs(g)<tol` 代替零点判断。真实段内穿越的定位与容差要求保持不变。
stop 事件经过相同的事件后求解和残差验收，成功提交后才返回终点观测；未请求终点输出时
仍执行该事件并保存事件记录。仿真最多接受 1,000,000 步；不能继续推进可表示时间或超过步数预算时显式失败。
到达规则依据限定 PWL 场景的 Spectre 实测，不称为其内部算法或所有触零情形的 LRM 结论。

运行时持有一份已接受状态及其已组装电路。无条件、无算子的普通时间点复用该电路；
历史算子或条件模型在普通时间点也进行区间认证。
先试算候选时间，若有更早的事件就丢弃该候选；随后在事件时刻准备状态、检查范围、重新解算电压并检查
原支路残差。全部成功后才同时提交时间、状态、电路、事件游标与记录。
失败或丢弃的候选不会消耗事件或增加计数器；请求任何一步失败均不返回部分成功结果。
返回的 `transient` 字段含观测时间/状态、实际接受的事件记录（时间、事件序号、类型、源码、cross 的 guard 值及前后状态）、
接受步数和因更早事件而丢弃的候选数。记录中的前后状态是同一时刻整批事件的快照。

### 固定 timer

支持 `@(timer(start, period, time_tol[, enable]))`；省略 period 时用
`timer(start,,time_tol)`，也可用 period=0 或负值表示单次。此空参数形式来自
[LRM 2.4 §5.10.3.3](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的 `analog_expression_or_null`，不采用两个实参含义不明的重载。
start 必须为非负有限实例常数，period 为有限实例常数，time_tol 必须显式给出且为正。
enable 为有限实例常数，0 禁用，非零启用；禁用不跳过模型的语法、IR 和依赖检查。
动态参数、缺省/零容差、复合事件仍明确拒绝。

周期事件定义为编译后 binary64 数值对应的实数 `t_k=start+k*period`。
内核由固定起点和精确整数 k 生成每个时刻，并用向外舍入界包围乘加误差；
实际候选取 fused multiply-add 的可表示结果，须证明 `abs(s_k-t_k)<=time_tol`。
不会从上次实际事件时间累加周期，也不按容差合并相邻名义事件。
同刻 timer 与 cross 共享事件前状态，并联立求解事件后的电压；整数赋值顺序和批次写者冲突规则与 cross 一致。

t=0 时先安装 initial_step 常量并求初始电压，再原子执行 timer(0)，最后输出初始观测。
名义事件恰为 stop 时照常提交，即使未请求 stop 输出也保留事件记录；名义时刻超出
stop 的事件不调度。这是 EVAS 的确定性边界策略，其他后端仍应按完整允许窗口验收。
计时误差、与 stop 的关系、相邻事件次序不能证明，或周期不能推进可表示时间时，
返回 `event_resolution`，不自动增大容差。相同日程或精确同刻可共同提交；
重叠但不能证明同刻的 timer/cross 区间会保守拒绝，有限误差界不意味着所有可解情况都接受。
PWL 根另有精确零点证书：当端点 guard 和到候选时刻的两侧时间差都已认证为
精确 binary64 数，使用完整二进制乘积比较证明线性插值为零，再将根区间收窄为点。
因此 `19U*(8/19)=8U` 不再因中间除法舍入而拒绝；一个 ULP 的真实邻近事件仍分别调度。
端点带不确定性、不可表示根或不能取得该证书时，保留原区间与拒绝边界，不放宽容差。
当前在运行前生成有界的不可变事件日程，并按需推进已接受事件游标；不是惰性队列。
日程空间随事件数线性增长，最多 1,000,000 条事件，超限返回 `event_budget`；时间推进仍保留独立的 1,000,000 步上限。

后续需要单独扩展：动态 timer、复合事件、状态反馈 guard 的同刻迭代，以及非线性轨迹上的
通用根定位。现有波形算子及积分的限定能力见[算子手册](OPERATORS.md)。

## 同块顺序赋值与同刻联立求解

[Verilog-AMS LRM 2.4](https://accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
§5.3、§5.7 及[过程赋值说明](https://www.verilogams.org/refman/modules/analog-procedural/assignment.html#assignment)
给出块内顺序执行和赋值立即更新变量的依据。同一块内的第二句应看到第一句更新后的值。
例如 `n=n+1; n=n+1;` 对应 `n1=n−+1, n2=n1+1, n+=n2`，因此净增量为 2。
连续三次净增量为 3；临时变量和中间值观测同样遵守语句顺序。

对同刻触发的各块，从同一已接受状态 s− 复制各自局部状态，按顺序构造
`s+=Phi(s−,v+)`，再求 `F(v+,Phi(s−,v+),t)=0`。固定候选算子值后，这条事件代入路径限定为仿射，
可代入后直接解线性方程；integer 更新只含整数状态算术，不引入待求电压或隐含取整。
电压同刻联立规则是本实现的选择，有限定对照支持，不称为所有 Verilog-A 事件的唯一通用语义。
积分/滤波的复位观察闭包及未来历史认证另见[共同生命周期](CONTINUOUS.md#shared-lifecycle-closure)。
若两个同刻触发的事件块都写同一状态，EVAS 在求解前拒绝该候选批次并保持旧帧不变。
这与同一块内重复写不同：同块重复写有明确的语句顺序；跨块重复写没有本实现愿意采用的隐式优先级。

具体有三条独立路径保持局部顺序：`EventModel::event_circuit` 构造代入方程，
`EventModel::apply` 重放原赋值，`Bounds::new` 从原 IR 构造区间认证。每次试算均固定从
s− 开始，因此求解、重放或缓存重试不会再累计一次事件。验收后才原子提交；失败时旧帧不变。
0.5.3 只移除输入绑定时的 integer 重复写禁令，没有改动这三条路径或放宽原精度/范围检查。

<a id="multiple-event-writers"></a>

### 多事件块写同一状态（PR25 已交付）

本检查点在 0.9.0 / IR v9 之后增加候选批次 writer 检查，不改变 IR。
构建期允许不同事件块潜在写同一 state，但仍拒绝事件块读取另一个事件块也可能写入的 state。
每次 `settlement::prepare` 先选择条件路径，再调用 `check_selection_writers(selection)`；
只有实际选中的赋值参与冲突判断。不同批次触发的上升/下降迟滞块可以共同维护同一 `q`。
同一批次中两个不同事件块写同一 state 时返回 `event_conflict`，即使写入值相同，也不按源码顺序仲裁。
失败候选不提交 state、state bounds、算子历史、事件游标或记录。

本检查点新增 `test_event_writers.py` 及一项 Rust 已接受帧回退测试，并用原 31 源中的
`v3-main` 两档冻结输入做局部 worker 回放；两档均生成波形且原 checker 给出
`observations_within_targets`。这些证据不替代完整矩阵重跑，不改写 0.9.0 检查点。

后续固定干净候选 `bfaf8d3` 与同一内核，EVAS 和 Spectre 21.1.0.509.isr12 各新执行两档，
四次均满足原 V3 有限观测判据；见[新对照收据](../../experiments/pr14-pr15-validation/results/event-writers-spectre-v3.json)。
六次 Spectre 单参数/事件日志诊断见[定位收据](../../experiments/pr14-pr15-validation/results/event-writers-timing.json)，
解释见[后端容差](#backend-cross-tolerances)。原 checker 未改，正式资格仍 I，raw 仅本地/thu-sui 保留。
重分析入口为 [event_writer_compare.py](../../experiments/pr14-pr15-validation/event_writer_compare.py) 与
[event_writer_timing.py](../../experiments/pr14-pr15-validation/event_writer_timing.py)；有收据不等于公开完整复现包。

<a id="event-conditions"></a>

## 受限事件体条件（0.8.0 实现切片，0.9.0 延续）

0.12.1 的[共同闭包](CONTINUOUS.md#shared-lifecycle-closure)将复位后观察与未来历史分开，
保留每次事件体的局部赋值顺序及整批提交。非点事件日志的可选 `observation_time_bounds`
报告共同观测区间；`time` 是存储代表时刻，点事件省略区间字段。当前 cross 策略显式选择 te=tau，
没有改成 Spectre 的晚触发条件取值；第一批对照仍是这一兼容差异的证据。

0.12.0 的非点 cross 候选在数学根 tau 上认证赋值和条件，代表时刻 b 另作提交电压验收。
完整根盒保留源/历史误差；若条件差值与实际触发的仿射 guard 有精确的同零集证明，
则使用 guard(tau)=0 判定等号。未触发 OR 叶子、timer、区间系数或单纯舍入相等不能提供这项证明。
因此 `u=3t, cross(u-1)` 内的 `u>1` 在根处为假；这改变了旧候选按 b 处微小延迟选支的行为。
其余条件仍需在可行输入盒内证明同一选择；不能证明时拒绝，点时刻 timer 保持原观察语义。
数学与非线性连续重启见[根盒采样](CONTINUOUS.md#事件修改的联合积分与复位)。
本轮没有新 Spectre 对照，这项数学根观察约定不等于其他仿真器的回调时刻。

单个 `cross` 或固定 `timer` 的事件体可含嵌套 `if/else`、顺序块、空语句及无 else 分支。
仅接受 `< <= > >=`，两侧为实例常数或状态独立的仿射电压表达式；else 归最近未配对 if。
依据是 LRM 2.4 §4.2.5、§5.3、§5.7、§5.8.1。以下数值认证方法是 EVAS 的实现选择，
不是 Spectre 内部算法的陈述。0.8.0 切片当时未执行新的后端对照；0.9.0 对照见[OR 说明](#event-or)。

例如 `@(timer(.5,.5,.001)) if (V(rst)>=.5) held=0; else held=V(vin);` 在每次实际事件时间
读取 rst 并选择复位或采样。所有分支都做静态合法性检查，执行时只判断沿路径实际到达的条件。
`initial_step` 仍为常量初始化；条件不能依赖离散状态、历史算子或经电压网络返回的状态。
结构依赖先检查，再作区间消元；`0*q`、`q-q`、下溢系数均不能作为独立性证明。
内部无状态网络如 `z=2*rst-1/4` 可以作为谓词来源。

0.9.0 的点观察契约令实际代表时间为 e，精确实数 PWL 插值为 u(e)，谓词差为
`d(e)=lhs(v(e))-rhs(v(e))`。从原 binary64 IR 的仿射网络得到输入到 d 的区间传递系数，
结合原 PWL 的 `U(e)`，形成包围 `D=[L,H]`。四种关系按下表认证：

| 关系 | 可证明真 | 可证明假 |
| --- | --- | --- |
| d < 0 | H < 0 | L ≥ 0 |
| d ≤ 0 | H ≤ 0 | L > 0 |
| d > 0 | L > 0 | H ≤ 0 |
| d ≥ 0 | L ≥ 0 | H < 0 |

其他有限区间返回 `event_condition`；非有限值也拒绝。不使用额外 epsilon，精确单点 `[0,0]`
按普通严格/非严格比较处理。`cross` 的定位证书不证明代表时间处 guard 必为零。
0.12.0 的非点 cross 转而证明实际根处的条件；只在有精确同零集证书时使用该根约束，
其余条件使用根盒源包围。不能把普通 timer 或近似相等的表达式强行改成等号。
例如 binary64 的 0.1→0.9 在 t=0.5 的实数插值比 0.5 大 `1/72057594037927936`，
普通浮点插值却可得到 0.5。当前区间不能判定这个边界时会保守拒绝，不冒充精确实数比较器。

选择路径 P 后，逐句更新构成 `q+=Phi_P(q−,v+)`，再解
`F(v+,Phi_P(q−,v+),H(e))=0`。数值代入和重放使用同一路径，并重新验证路径；
区间认证独立从原 IR 的选中语句构造映射。`U(e)` 同时传入状态、电压认证，
不能只保证选支正确，却把 RHS 的已舍入输入重新当作精确量。
含条件的整个程序在事件、初值和普通观察点都保留输入及已接受状态包围；即使没有算子也不丢掉采样误差。
电压使用 `vabstol+reltol*abs(v)`，real 状态只有相对项，integer 必须精确；未通过时返回
`event_accuracy`，含历史算子时为 `waveform_accuracy`。0.12.0 联合连续网络另在根盒上
认证采样并保留根到代表时刻的新流误差，见[共同误差链](CONTINUOUS.md#事件修改的联合积分与复位)。
本轮不把这个范围推广为所有算子的历史采样认证、源到 IR 舍入保证或连续时间资格。

每个 EventModel 持有至多一份证书缓存，键为激活块及选中赋值/分支路径；只缓存系数。
每次试算从已接受帧开始重新判定，只有选中路径实际写过的状态能触发算子目标更新。
候选的状态、包围、电压、算子历史和记录全部通过检查后才随游标一起提交。
新增测试直接检查非零 transition 历史下的失败、成功弃步、修正未来输入重试与新缓存控制的一致性；
这仍不是完整调度器任意故障注入证明。

实现入口：[event_conditions.rs](../rust_core/src/event_conditions.rs) 负责结构、路径和谓词认证；
[settlement_bounds.rs](../rust_core/src/settlement_bounds.rs) 负责选中原 IR 的误差传播。
独立答案与边界控制见 [test_event_conditions.py](../tests/test_event_conditions.py)，
实际帧回退见 [transient_condition_tests.rs](../rust_core/src/transient_condition_tests.rs)。
完整目标契约与剩余组合边界见[验证契约](../validation/EVENT_CONDITIONS_CONTRACT.md)。

0.8.0 切片当时尚未支持 `cross … or cross …`，也未执行原采样复位 8 条件；0.9.0 main 已补齐 OR 并完成两档有限观测验证，见[当前契约检查点](../validation/EVENT_CONDITIONS_CONTRACT.md#current-checkpoint)。
该历史检查点仍不支持状态反馈谓词、通用非线性谓词、多块同状态写入、普通 analog if 和 idt reset。
PR25 在候选批次可证明至多一个实际选中块写同一状态时，受限支持多事件块写同一状态；
见[交付说明](#multiple-event-writers)。`feat/evas-idt-reset` 分支另补状态 reset 的限定形式，
边界见[算子手册](OPERATORS.md#idt)。
区间传播会增加运算和存储，丢失相关性时可能保守拒绝；未测量本轮运行开销，也没有自动细化步长或高精度回退。

## timer 与同刻兼容性

[0.5.0 历史对照](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-fixed-timer-comparison)
曾暴露旧电压采样和同刻根认证拒绝；
[0.5.1 修复](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-timer-repair-051)
采用联立求解并修复可表示根认证，限定的级联、反馈和同刻样例已相容。
[0.5.2 加固](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-timer-hardening-052)
增加前向误差认证，同时曾因 Spectre 对照差异保守禁止同块 integer 重复写。
这些旧结果保留原身份，不能当作当前版本的新执行结果。

随后 18 个独立诊断配置显示 Spectre **21.1.0.509.isr12** 的相邻重复自增异常同时涉及
integer 和 real；缩小步长仍存在，插入中间值观测可使现象消失。最小模型无电压反馈，
预期值由顺序赋值独立确定。0.5.3 据此恢复合法 integer 顺序更新，保持语言语义，
不复制该版本的异常输出。确切内部原因、新版本范围和厂商确认仍未知，见
[Issue #16 的可复现输入及对照](https://github.com/BucketSran/vaEVAS/issues/16)。

[0.5.3 回放](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053)
区分语言语义与具体后端的一致性；未修改旧检查器、阈值或原条件分母。
PR13–15 的后续整合和受影响回归见[能力登记表](CAPABILITIES.md)，旧结果不冒充当前分支执行。
若未来允许 guard 依赖状态或算子，须在变化后重新定位根，不能沿用失效的预计算日程。

## 实现与验证入口

- [events.rs](../rust_core/src/events.rs)：身份、结构依赖、顺序代入和赋值重放。
- [settlement.rs](../rust_core/src/settlement.rs)、[settlement_bounds.rs](../rust_core/src/settlement_bounds.rs)：同刻联立、原关系检查及区间认证。
- [schedule.rs](../rust_core/src/schedule.rs)、[event_accuracy.rs](../rust_core/src/event_accuracy.rs)：固定日程、根和误差界。
- [transient.rs](../rust_core/src/transient.rs)：候选帧、原子提交、丢弃及回退测试。
- [test_settlement.py](../tests/test_settlement.py)、[test_timer.py](../tests/test_timer.py)、[test_event_accuracy.py](../tests/test_event_accuracy.py)：独立开发回归。
- [Spectre 实验](../../experiments/dvs2-spectre-validation/README.md)与[共同历史协议](../validation/METHOD_QUALIFICATION.md)：判据及观察限制。

这些证据不等于完整 DVS 资格、任意非线性事件支持或其他仿真器内部算法的证明。
