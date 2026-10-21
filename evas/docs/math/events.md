# 事件、时间推进与历史

适用范围：IR24 的 `cross`、固定/保持状态 `timer`、受限事件体条件、事件 OR、多事件写者及模型步长请求。
能力 ID 为 LANG、CROSS、TIMER、EVENT-ORDER、EVENT-CONDITIONS、DYNAMICS、COMPOSE；支持与缺口见[四后端支持范围](../COMPARISON.md)。

本页维护定位、顺序赋值和同刻关系。历史的复位、观察及未来传播见
[共同生命周期](continuous.md#shared-lifecycle-closure)。
数学根 tau、实际触发 te 与内部代表时刻 b 是不同对象；cross 事件体按[根后右极限](#cross-right-limit)
`te=tau+` 读取：连续值取 tau 处包围，可认证符号的条件取根后一侧。

<a id="bound-step"></a>

## 模型步长请求 `$bound_step`

普通 analog 体可用 `$bound_step(h)` 请求下一次瞬态推进不超过 h 秒。
例如 `$bound_step(0.125); V(y)<+idt(1,0);` 在 0–1 s 至少推进八步，最终 y=1 V。
同一次模型求值中的多个调用、多个实例和请求参数 `max_step` 共同取最小值。
请求只约束下一次推进；条件不再执行该调用时，其旧值不永久保留。
有效请求在静态求解中忽略。依据是
[Verilog-AMS 2023 LRM §9.17.2](https://accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf)；
下述认证、路径范围与最小步是 EVAS 的实现选择。

编译器按语句顺序记录请求值。例如先 `h=0.125; $bound_step(h); h=1;`，
记录的是 0.125。有限非负常数、已支持的电压表达式、保持状态和已有算子结果别名可作值，
但调用本身不能创建新历史算子。初始化体、事件体和纯函数体内的任务调用仍拒绝。
条件调用沿用普通 analog 条件的输入仿射谓词范围；不可达分支也须通过结构检查。

在已接受时刻 t，设活动请求的认证区间为 `H_j=[L_j,U_j]`，控制器选择
`h=min(max_step,L_1,…,L_n)`，再向下舍入 `t+h`，并服从更早的源拐点和已知事件边界。
取下界保证下一步不超过请求的任何可能值；区间非有限或包含负值则明确拒绝。
布尔激活条件跨越切换边界时，只要调用仍可能激活，就保守应用该请求的认证步长限制。
这可能增加小步，但不改变物理方程或事件分支的判定；请求数值本身不能认证时仍拒绝。
若 h 为零或小于可表示的时间间隔，
采用 `next_up(t)` 作为最小推进时刻；极小请求仍可能触发已有步数预算。
普通查询不提交历史。事件体成功提交后，新保持状态用于下一次步长请求；失败试算不保存请求值。

非线性积分器在每个内部接受段起点认证活动条件和请求值，以请求区间下界限制实际积分段；
动态请求也不能只增加外层控制器计数。内部积分同样应用可能激活的请求；
非法条件、未认证的请求数值、非有限值或负值明确拒绝。
隐式 DAE 仍只接受正的无条件常数请求，其他请求在该路径返回 `unsupported_bound_step`。
已支持的线性解析历史由接受帧上的动态请求限制推进，不改变解析公式。
这不是一般动态模型的完整 `$bound_step` 支持。

Python 的 `instance_compiler.py` 生成 IR22 `step_bounds`，每项保存 `value/active/origin`。
Rust 的 `step_bounds.rs` 验证引用和来源、计算认证上限；`transient.rs` 在接受帧调用它，
`nonlinear_dynamics.rs` 限制实际积分段。旧 IR1–21 须从 VA 重新编译。
[test_bound_step.py](../../tests/test_bound_step.py) 独立检查多调用/实例取最小值、条件释放、
事件后状态、语句顺序、查询不改变终值、非法 IR，以及 `y'=y²,y(0)=1` 的解析答案和实际积分段宽度。
[test_r01_language.py](../../tests/test_r01_language.py) 补语言入口回归。
本轮实际 Spectre 对照与最终代码身份的绑定待完成，开发回归不证明跨模拟器行为对齐。

<a id="state-operator-contribution"></a>

### 条件步长的释放

更小的步长只在原条件成立时生效。例如 `if (t<0.25) $bound_step(h)`，
不能因 h 始终为正，就让它在 0.25 秒之后继续限制积分段。
仅当整个请求值包围都不小于已有 maxstep 时，私有历史计算才可将这一冗余限制化简；
更紧的限制保留原条件和切换点。原模型、事件依赖与接受时检查仍保留。
见[条件步长回归](../../tests/test_conditional_history_mesh.py)。

## 状态与观测算子的有限乘积贡献

本地 IR21 候选接受“只含保持状态的仿射表达式”乘“只含已支持算子观测值的仿射表达式”作为电压贡献，
外层可继续作常数缩放和相加。事件同刻先认证算子样本；联立求解只冻结该样本，
状态仍作为未知量参与事件赋值与电压关系。完整算子包围保留为区间系数，不能只用名义值证明精度。
例如当前 transition 值为 c，`q=0.5*V(y)+u` 与 `V(y)<+q*c` 必须共同求解 q 与 y。

这项有限贡献准入不改变事件赋值 RHS 的联合仿射要求。状态乘内部待解电压、
该事件联立路径中的变量或算子分母仍拒绝。一般定时波形算子与 `idt`、`laplace_nd`、`ddt` 的混合网络
仍可能返回 `unsupported`，不能从一个乘积贡献推导整个混合网络受支持。
开发回归见 [事件选路与算子系数](../../tests/test_r01_event_select.py)；尚无本候选的实际 Spectre 对照。

<a id="event-math"></a>

## 隔离观察事件中的统计数学

IR22 的本地源码候选扩展独立测量实例的统计表达式。物理事件先完成同刻联立求解和历史闭合，
观察事件再读取实际事件时刻 tau 的电压值及区间。实例必须满足[完整 IR 隔离判定](#passive-observer)，
不能拥有电压贡献、历史算子或步长请求，也不能让其他实例消费其状态。
判定扫描所有分支及显式零项，不按模型名、当前参数或数值结果放行。
事件中含 `initial_step` 或固定 start=0 timer 叶子时保留原路径，该 timer 的后续周期也不获得此扩展。
正常完成时的隔离 `final_step` 可读取已接受统计状态，时序仍遵守[事件输出合同](#display-records)。

新增纯数学表达式只含 `sqrt`、`abs`、`min`、`max`，并组合原有加减乘除及整数幂。
它们在事件执行时求值，不创建连续历史。已有可用的仿射求值和常量数学保留；
物理事件的有限采样标量另见[因果算术合同](#causal-transition-composition)；其他一般函数及事件历史调用仍拒绝。

例如，下列片段在可证明 `n>0` 时计算均值及标准差：

```verilog
if (n > 0) begin
    mean = sum / n;
    variance = sumsq / n - mean * mean;
    sigma = sqrt(max(0.0, variance));
    $display("mean=%g sigma=%g", mean, sigma);
end
```

每条赋值读取同块此前写入的状态，条件与 `$display` 也读取其所在语句位置的状态。
新增非仿射赋值、数学函数参数和直接显示复用同一个补偿求值入口；不能让同一表达式因消费者不同而采用不同的舍入顺序。
名义值用于记录数值，区间用于证明定义域、选路及后续消费者的误差，不能只凭名义值为正就接受除法。
内核还检查代表值确实位于原表达式的区间内；补偿求值不能代替这项认证。
区间传播遵守下列规则：

- 除法要求分母整个包围不含零。分母值为零或包围跨零时返回 `event_domain`。
- `sqrt` 要求输入整个包围非负，并用既有平方根认证得到输出包围。源码没有 `max` 时，负输入不能擅自夹零。
- 对 `X=[L,H]`，`abs(X)` 的上界为 `max(abs(L),abs(H))`；含零时下界为零，否则为两端绝对值的较小值。
- 对 `X=[Lx,Hx]` 与 `Y=[Ly,Hy]`，`min(X,Y)=[min(Lx,Ly),min(Hx,Hy)]`，
  `max(X,Y)=[max(Lx,Ly),max(Hx,Hy)]`。因此 `max(0.0,variance)` 的输出下界是零，
  即使 variance 的包围跨零，也不需要猜测一条赋值分支。

真 `if` 与三元表达式仍须证明选路，只求值选中臂的数学域。
例如可证明 `n=0` 时，`n>0 ? sum/n : 0.0` 不执行除法。
编译和 IR 校验仍检查两臂的名字、类型、参数数目、源码身份及结构预算；未选臂不能隐藏非法声明或历史调用。
未知条件沿用原保守拒绝和已有两臂等价规则，根处比较仍须满足原同零集证书要求。
非有限值或包围明确失败，integer 继续要求精确整数，real 统计状态保留全部误差区间。

状态、误差包围、显示记录和未来日程只在整批验收成功后提交。数学域错误或后续日程、输出认证失败，
都保留批次前的已接受状态和记录；普通输出查询不重做统计累计。
前端与内核必须配套使用 IR22，从原 VA 与 manifest 重编译，不能仅修改旧 JSON 的版本号。

实现入口为 [lowering.py](../../src/evas/lowering.py) 的事件数学降低、
[events.rs](../../rust_core/src/events.rs) 的原路径选择及依赖检查、
[event_numeric.rs](../../rust_core/src/event_numeric.rs) 的值和区间运算、
[event_conditions.rs](../../rust_core/src/event_conditions.rs) 的条件认证，以及
[passive_events.rs](../../rust_core/src/passive_events.rs) 的隔离观察候选。
[公开回归入口](../../tests/test_event_statistics.py)维护独立统计答案与定义域边界。
三条原 gain 请求已在冻结候选完整通过原 checker，并完成实际 Spectre 对照；
[四项独立统计控制及原请求收据](../../../experiments/backends/support/README.md#event-statistics)保留输入、配置和有限范围。
这项工程验收不增加 Q 成绩，不证明全时域一致。

<a id="display-records"></a>

## 事件输出记录与时间

受支持事件体中的 `$display` 与 `$strobe` 共用输出记录，按语句顺序求值，只输出实际选中分支。
格式限 `%d`、`%g`、`%.Ng`（N 为 1–32）、`%f`、`%.Nf`（N 为 0–32）及 `%%`。
`%f` 默认保留六位小数，指定精度时保留相应小数位；格式转换数须与数值参数数目相同。结果保存在
`transient.display_records`，每条包含 `time`、`event`、`origin`、`text`。
记录与候选事件共同验收后提交；失败试算、丢弃与重试不重复输出。
Python 响应检查要求 `event` 与 `time` 对应已提交事件，`origin` 属于该请求事件内的 `$display`。
`origin` 是源码位置及实例的标签，用于定位语句；它本身不证明输出数值或事件精度。

无电压贡献的被动模型可在 `initial_step` 中穿插常量初始化与输出；记录先于 `timer(0)`。
带电压贡献的模型可在初始化赋值之间输出常量快照。编译器在每条输出语句的位置读取参数和当时的
初始化环境，捕获有限常量参数；后续赋值不会改写此前快照，物理状态与冷启动历史仍使用最后的初始化值。
例如先输出默认 q=0、赋 q=3 再输出，记录为0和3，而初始transition种子为3。
生成的初始事件只含已有IR的Display，不重新执行初始化赋值。Rust在普通初始化与零timer引导两条路径
独立确认主动模型初始事件只含常量输出，不允许原始IR夹带状态写入或电压读取。

本地候选仅允许常量输出参数及常量分支条件。主动初始化输出读取电压、历史算子、输入选择的状态值，
在初始化循环内输出，或由含子实例的模型输出，均明确拒绝；不扩展一般初始化采样。
被动模型仍须有足够驱动约束，浮动节点不因只输出而合法。
独立回归见[主动初始化输出](../../tests/test_active_initial_output.py)，覆盖赋值前后快照、实例隔离、
零timer的种子更新、拒绝重试、固定小数格式和原始IR拒绝边界。该本地候选尚待独立审查及原件checker验收。

此处任务别名、接受后输出与实数格式依据
[VAMS-2023 LRM §9.4.1、§9.4.3、§9.4.6](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf)。
常量初始化快照及主动模型的有限准入是EVAS实现边界。Python的syntax.py保留初始化源序，
instance_compiler.py::initialize_states捕获快照，display.py与Rust display.rs约束格式；
transient.rs与transient_initialization.rs沿用现有候选记录提交。

与零时刻 transition 种子更新组合时，本地集成候选先执行被动 `initial_step`，再执行固定零 timer，
最后用最终状态构造历史。例如 initial 输出旧 n=0 后赋 n=3，timer 的输出应读到3。
两个阶段的状态与记录都属于候选，所有认证及历史构造通过后才发布。初始输出读取内部电压时，
改变 transition 种子的组合仍明确拒绝，避免把最终电压当成 timer 前的电压；种子不变时沿用普通路径。
混合 initial/timer OR 的变化种子组合也尚未支持。新增[组合回归](../../tests/test_initial_display_transition.py)只证明本地开发行为；
这项 IR21 新组合尚缺独立审查及实际 Spectre 对照，不能复用旧三模型收据宣称整个组合对齐。

受限 `final_step` 在正常完成 stop 时、同刻 timer 提交及终点波形采样之后读取已接受状态。
其中的状态赋值反映在 final 事件的 before/after 快照及后续 `$display` 中；
`transient.states` 最后一行和终点电压仍是 final_step 前的波形，不因最终赋值重新采样。
失败运行不补发最终记录。
`$abstime` 读取内核驱动的合成时间节点，事件采样使用事件时间，不能由外部 PWL 覆盖。

独立回归见 [输出记录](../../tests/test_display.py)和[事件时间](../../tests/test_event_time.py)。
这些开发检查不提供本候选的实际 Spectre 对照。

### 输入辅助的初始化种子不变证明（分支候选）

当旧仿射证明不能确认种子不变时，有限输入辅助证明使用完整零时刻输入盒和初始状态盒，
重放原始顺序赋值。未知条件合并两臂，未知内部电压与历史值保持未知；独立事件块还须通过
读写集合检查。只有每个必需历史种子都与原值精确相等时才选用普通初始化路径。
这份旁证不代替事件执行、整数检查、误差传播或事务回退，也不许可改变种子的混合OR事件。

旧形式与具体初值两次尝试各保留200万额度，输入辅助重放只用第二次剩余部分。
节点、集合、克隆和零时刻源查询在工作前扣费；精确求值器逐节点、逐算术操作扣同一总账，
包括Power的每次乘法。耗尽即拒绝旁证，同一余额重试不能恢复额度。
每表达式的512节点、64深度、4096位、20万精确操作及幂指数不超过32的限制继续生效，普通事件的预算作用域不变。
实现见[初始化旁证](../../rust_core/src/initial_state_invariance.rs)和
[精确状态求值](../../rust_core/src/event_value_proof.rs)，公开消费者见
[初始化种子回归](../../tests/test_initial_seed_invariance.py)。缩放预算正反例验证累计收费，
不代表已证明原件在固定200万额度下曾超限；统一原件验收单独记录。

<a id="event-or"></a>

<a id="cross-的事件-or090"></a>

### 事件证明的复用

同一组选中语句的联合仿射关系可以复用其矩阵，当前输入、状态和算子误差包围仍须逐次验收。
系数依赖当前状态或算子值时不适用；域错误、奇异系统和精度失败不能被当作缓存未命中而忽略。
复用后还要重查原条件选路，不能用上次的状态证书替代本次结果。
见[独立缓存回归](../../tests/test_certificate_cache.py)。

### 源选择证明的共享（分支已验收，未合并）

transition 与 source-selected Slew 可在同一请求内共享不可变的源分区与符号事实。
证书绑定完整Program、原始输入曲线、实际节点映射、保持值绑定和精确RootTime；
不同请求、不同输入误差或不同绑定不能按表达式拼写复用。每个算子调用仍拥有独立历史。
原树所有臂、显式零项及依赖在查缓存前检查，缓存命中不能隐藏除零、状态或内部节点读取。

共享不提高原cuts、符号或work上限。每个Plan物化根列表按长度收费，
缓存保存的根列表副本也额外按长度收费；跨Plan取回副本仍收费。
同一Plan中已审计的完整绑定guard可以避免重复物化，不能因此免掉其他Plan的预算。
配额预留失败保持失败状态，不安装部分证书；控制器晚失败后重试不提交历史。
这项复用不扩大Transition的isolated thirdpoint范围，也不证明整体性能提升。

### 共用精确根的边沿期限

如果同一次已认证的回调使两个 transition 开始变化，它们可能有相同的结束时刻。
例如根为 τ、延迟为 td、边沿长 tr，结束时刻是 τ+td+tr。EVAS 保留这个数学时间依据，
分别加上延迟和边沿长度；相同浮点代表值或相同区间本身不能证明两个期限相等。

只有批内每个事件都证明同一精确根时才传播此依据。原事件包围、代表时刻和电压误差门槛不变，
预览、实际安装及积分/滤波消费者使用同一证据。已经进行的边沿被中断时，剩余时间还取决于
当时的值和斜率，因此不能继续套用完整边沿的期限；未证明的排序仍拒绝。
这项依据只用于算子期限之间的比较，不代表所有状态决定的 timer 或用户事件都能精确排序。
见[精确期限回归](../../tests/test_exact_transition_deadlines.py)。

## cross 的事件 OR

`@(cross(g0,...) or cross(g1,...) ...)` 表示一个事件体的触发集合
`E_B = E_0 ∪ E_1 ∪ ...`。这是事件集合合并；每个调用继续独立监测自己的 guard、方向、
时间容差及表达式容差。依据与首版选择见[独立契约](../../validation/EVENT_CONDITIONS_CONTRACT.md#trigger-set)。
OR 接受 cross/timer 叶子的并集；每个叶子保留自己的时间证书。
原始 IR 中的空/单叶/嵌套 OR 仍拒绝。

IR 使用 `trigger/body/origin` 事件块，OR trigger 内保存叶子列表。
`EventModel` 为叶子保存 `(block, leaf)` 身份，写者与赋值路径仍按 block 管理。
日程按叶子定位和认证；只有证明同根且共同代表时间满足每个叶子的容差后，
候选批次才将 block 去重，并调用既有顺序赋值和电压联立求解。
不同块或不同实例仍分别执行。不同根即使相距小于 ttol 也不能合并；无法认证排序时拒绝。
事件预算统计所有叶子的根，去重不能绕过预算。

一个 OR 块产生一条 `kind=or` 记录；`fired_triggers` 保存实际触发的叶子索引、类型及
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

cross 叶子保留 `guard_value`；timer 叶子不伪造 guard 值，只保留时间证书。
同刻 timer/cross 须有精确同刻证明，计数器只更新一次；周期 timer 与不同 cross 根分别执行。
旧合法 IR16 的布局不变；类型字段是响应扩展，原有 cross guard 字段仍保留。
动态 guard 的范围见下节，多块写同一状态的规则见
[写者检查](#multiple-event-writers)。全部故障点的系统性注入和完整连续时间误差资格仍是验证缺口。

<a id="declaration-initializers"></a>

## 事件状态的声明初值

本分支接受原本已有 cross/timer 写者的标量 `integer`、`real` 声明初值。
例如 `integer n=2;` 给已有事件状态设置初值；声明赋值本身不能创建持久状态角色。
有procedural写者的普通 analog 局部量、数组初值、其他变量依赖、电压采样、时间和算子调用仍拒绝。
无procedural写者的有限常量声明另见下节，只读声明不因此变成参数。
参数在每个实例绑定后，初值必须经既有类型降低证明为有限标量常量；这不开放全部合法常量表达式。

所有显式声明初值先在实例私有临时表验证，再覆盖默认零环境，随后按原源码顺序执行 `initial_step`。
因此声明 `n=2` 后的 `@(initial_step) n=7` 得到7；非法声明初值不能因稍后被覆盖而忽略。
失败不返回部分 Program，下一次编译与其他实例不共享种子；声明赋值不在每次模拟求值时重做。

源类型沿用原初始化合同：`real x=7/2` 的整数除法结果为3，显式 `7/2.0` 为3.5。
整数中间溢出、非整型写入与非有限值仍拒绝，real 目标不删除整数检查。
整数参数除法与有限余数范围现在按[typed 整数算术](#typed-integer-closure)绑定；声明初值仍须满足本节的有限标量常量条件。
元数据只在前端保留，经函数、数组及层次展开传递，最终复用 IR24 的 `State.initial`。

独立初值、后续事件和拒绝控制见[声明初值回归](../../tests/test_declaration_initializers.py)；
完整原件及候选身份见[验收收据](../../../experiments/backends/support/declaration-initializers/evidence.json)。
独立的 `initial_step` 已有[有限点电压采样](#input-initialization)；声明初值语法本身仍不接受电压表达式。

<a id="immutable-declarations"></a>

### 无过程写者的常量声明（分支已验收，未合并）

标量integer或real显式声明初值若通过原有限常量、源类型及signed32中间检查，
且整个原始analog树中没有对它的过程赋值，可作为实例私有的只读局部量使用。
例如 `real start=0.25; @(timer(start)) q=1;` 不创建start状态，也不把start加入可覆盖参数空间。
实例参数绑定后分别计算初值；外部不能以同名instance参数覆盖这个局部声明。

写者检查覆盖initial_step、final_step、普通及运行事件、所有分支和循环，
零次循环或死分支中的写入也会关闭只读资格。已有合法cross/timer状态的声明种子继续走原路径。
所有显式初值即使未使用也必须验证；后续覆盖、未调用函数和死分支不能隐藏非法声明或整数溢出。
变量之间的依赖、自引用、数组声明初值、电压与时间初值不进入这个常量入口。
函数参数及函数局部名称按各自作用域绑定，不能借同名模块声明取得常量资格。
公开隔离、命名空间和raw writer控制见
[test_immutable_declarations.py](../../tests/test_immutable_declarations.py)。

<a id="input-initialization"></a>

## 标量 analog function 的源类型保留候选

函数的返回值、形参和局部变量保留声明的 `integer`／`real` 类型。
传入 integer 形参、赋给 integer 局部量及返回 integer 结果时，分别执行该次赋值的转换；
最近整数的半整数向远离零方向舍入，随后检查 signed32 范围。
整数操作数的除法向零截断，余数与被除数同号；real 形参不会因实参写成整数而变成整数除法。
例如 integer 函数先把实参 `2.5` 复制到 integer 形参 `x`，再计算 `x/2`，结果为 `1`；
real 形参下的 `3/2` 为 `1.5`。未赋值的 integer 返回槽从零开始。

内部展开节点 `function_assign` 保留各次赋值的类型义务与顺序，不是新的线协议节点。
未使用的实参、局部赋值和未选中的分支仍保留检查义务；不能先消去它们再判断整数范围。
事件正文的原树审查验证 `function_assign` 的单子节点、类型与每次整数转换，
随后继续遍历完整子树。real wrapper 在参数常量条件和 source-only compact event assignment
中保留旧资格。整数 wrapper 不借此取得 array、index 或 held target 等额外角色。
新增 metadata 查询和复制仍计入原编译审查 owner；未选分支与隐藏操作不会被常量特化消除。
公开兼容与拒绝控制见 [test_event_function_consumer.py](../../tests/test_event_function_consumer.py)。

动态 real 值不能仅凭函数返回类型取得整数资格，必须通过现有完整输入域证明。
后置 clamp 不替代原中间值检查，也不开放一般电压表达式到整数的转换。
需要实例类型绑定的调用在尚无该绑定的参数默认值、数组维度等入口明确拒绝；
这表示当前实现范围有限，不表示这些源程序不合法。
未调用的定义仍按原有结构规则校验，不能据此声称已验证所有未执行路径的数值域。

语法类型由 [syntax.py](../../src/evas/syntax.py) 保存，
[elaboration.py](../../src/evas/elaboration.py) 保留展开义务，
[lowering.py](../../src/evas/lowering.py) 和
[instance_compiler.py](../../src/evas/instance_compiler.py) 使用原整数算术与绑定检查。
[独立公开合同](../../tests/test_integer_functions.py)覆盖复制顺序、正负舍入、除法类型、
默认返回、溢出、未使用实参及名字绑定。本节描述本地候选；完整原修两轨400、CI与安装仍须绑定最终统一源码，
不能把函数窄检查通过记为原369通过。

## 实际驱动输入的比较与有限点初值

EVAS 接受 `@(initial_step) q=(V(in)>H);`，`q` 可为 real 或 integer。
初始化按源码顺序执行，后续语句读取先前赋值；未显式初始化的持久状态默认零。Verilog-A 比较结果为 0/1。
比较输入可以是外部理想源，也可以由其他实例的零时刻电压贡献唯一确定。
例如另一实例以初态 `s=1` 驱动 `V(ctrl)<+transition(s,0,tr,tr)` 时，
`@(initial_step) q=(V(ctrl)>0.5)` 得到 q=1。不能将尚未求出的内部电压当成零。
这是 EVAS 的能力边界，不表示其他合法 initial_step 写法违反语言标准。

比较关系限 `<`、`<=`、`>`、`>=`。两侧可含已绑定参数与仿射电压运算，
前端只允许 input/inout 端口或 ground。Rust 先认证外部 driven，
再按比较所需节点取得贡献闭包，联合求解仿射电压关系；inout 声明本身不能证明电压已确定。
同支路多贡献相加，非接地支路和可逆的线性电压环也参与联合求解。
解析依赖时，可先用状态已确定的完整支路组认证独立电压，不能只取同支路的一个常量贡献。
例如 `V(aux)<+1`、`s=(V(aux)>0.5)`、`V(ctrl,aux)<+s` 依次确定 aux=1、s=1、ctrl=2，
不因非接地支路把 ctrl/aux 连在一起就误判为初始化环。
这些局部证书只决定解析顺序；提交前会丢弃临时电压值，用全部原贡献重新联合认证所需闭包，
再检查全部原初始谓词。晚到约束冲突或谓词结果变化会使整个候选失败。
驱动贡献中的保持状态必须先有确定初态，transition 的零时刻种子复用原目标初值，
该种子算术须能认证为单点。状态选择目标会先绑定已知初态，再判定其条件，不安装或推进额外历史。
没有定义的端口、奇异或冲突电压关系，以及未认证的历史依赖仍拒绝；
零系数、代数抵消和未走分支不能隐藏依赖。受限条件、逻辑与三元初值可组合实例常数、
先前初始化值及直接驱动输入；integer 每次写入都须证明整型和范围。
real 状态还接受结构仿射的输入电压值，以及由输入谓词选择的仿射值臂。
例如 `@(initial_step) q=0.5*V(in)+0.125;` 只采样零时刻，之后 q 保持该值。
每个候选仍检查所有谓词、值臂和结构依赖。integer 值臂保持常量限制，不隐含采样或取整 real 电压。
初态与电压互相选择的固定点、不能独立认证条件的贡献分支、比较式中的历史调用及分析专属生命周期仍不支持。
状态依赖按需要解析，实例枚举顺序不决定结果；依赖环未证唯一时明确拒绝。
单个联合电压闭包限256个未知量，状态依赖深度限128，总依赖工作限100000步。

令输入仿射谓词为 `d=a(v(0))-b(v(0))`。`>` 在 `d=0` 返回 0，`>=` 返回 1，
不设置 epsilon。单点输入复用 binary64 乘积和的精确符号证明；
非点输入复用向外舍入区间证明。区间横跨分支边界且无法证明时返回
`initialization_precision`，附源码及状态身份，不猜测初值。
比较表达式仍返回精确 0/1。real 采样值从原输入包围向外计算，
只有结果有限且 `lo==hi` 才安装到 `State.initial`。源误差或算术舍入产生非点包围时，
即使名义值可计算也返回 `initialization_precision`；当前没有一般初值区间状态传播。

Python `instance_compiler.py` 独立降低初值并保留结构与来源。IR24 的
`State.initial` 复用 number 或既有表达式对象，包括 `affine`、加法、乘法、幂和 `select`；
Python 类型注解由 `float | Select` 扩为 `float | Expression`，schema 未改变。Rust `initialization.rs::resolve`
从 `Trajectory.value_bounds(0)` 及 `initialization_nodes.rs` 的局部电压证书解析整个候选集，成功后才安装常数。
`EventModel.initial()`、算子构造和守卫调度使用同一组结果；
之后才建立完整接受帧，执行合法 timer(0) 并输出首行。
失败路径没有模型、日程、历史、接受帧或 trace 可提交。
旧 schema 和畸形字段分别由版本/请求校验拒绝。

### 前序局部别名与固定数组槽

普通 analog 赋值可给初值或事件表达式提供别名。编译器只接全段唯一、无条件且在该事件前已执行的写者，
按实例绑定参数并按源码顺序代入。纯实例常量别名可用于原有常量设置；
real 输入仿射别名可用于初值，以及 cross guard 和事件体的当前电压读取。
`a=V(in); @(cross(a-0.5,1)) q=a;` 在物理根处重新读取输入，不能把 a 的初始采样当作运行期常量。
这不开放电压驱动的 timer 设置或 cross 方向、容差。

固定数组下标逐槽处理。`a[0]=V(in); a[1]=2*a[0];` 仅为源码中已经写过的准确槽建立作用域，
不因 a[0] 已写就允许提前读 a[1]。实例参数和既有下标检查负责确定槽，未证明的动态下标不获得此扩展。
分支写者、多次写者、未来写者、状态反馈、输出依赖、时间及历史别名仍拒绝。
cross guard继续只接原有连续仿射别名。事件体另接受纯输入的有限选择表达式，例如先定义
`a=(V(in)>0.25)?V(in):0`，再在timer或cross回调中读取a。每次回调读取当前物理根输入，
初始采样和后续保持值相互独立。受限的源integer选择量可作为依赖，但每个原中间值仍受signed32类型检查。
非线性乘积、状态、时间、历史、内部或输出依赖仍拒绝，零系数及未选臂也须完成原审计。

新事件体别名只接原源码中唯一、无条件、前序的普通标量写者。`frontend.py`保留层次绑定与循环展开前的
原模型引用；`initialization_aliases.py`据此检查全部initial、ordinary及event写者，包括零次循环中的写者。
新路径排除数组槽和循环产生的定义，传递依赖也逐项检查。既有仿射数组与循环能力按原合同保持。
按事件体实际需求绑定的表达式保留原树；累计绑定按wire引用重复计数，仍受原100000项IR和深度上限约束，
有限域256与决策展开4096上限不变。guard、方向、容差及timer设置使用原别名映射，不能借事件体映射扩大准入。

`syntax.py::analog_block` 保留事件前的标量名字和 indexed Assignment 前缀，
`array_elaboration.py::scalarize_arrays` 用既有元素绑定转换为精确槽。
`initialization_aliases.py` 证明初始与运行别名，`instance_compiler.py` 在各自词法作用域使用它们。
独立公开证据见 [test_frontend_closure.py](../../tests/test_frontend_closure.py) 与
[test_initial_sampling_closure.py](../../tests/test_initial_sampling_closure.py)和
[test_event_body_input_aliases.py](../../tests/test_event_body_input_aliases.py)，
覆盖根处采样、实例隔离、源码顺序、原写者资格、旧数组及空循环兼容，以及源误差放大。
[固定候选收据](../../../experiments/backends/support/low-cost-closure/evidence.json)区分局部原件验收与全量身份。
这项表达式替换不改变事件排序、历史归属、接受与回退；历史波5的029、111仍有各自的内核事件定位阻塞，后续波6b的029及wave15精确DC投影下的111已通过原checker，一般联合仿射事件组合仍受限。

[三个节点依赖实际对照](../../../experiments/backends/support/initial-node-dependencies/README.md)
覆盖跨实例 transition 种子、耦合电压和非接地支路，有限原生观察均满足原 1e-9 V 门槛。
这三例不代表 MUX 完整工程请求通过。

[零时刻节点依赖回归](../../tests/test_initial_node_dependencies.py)检查跨实例种子、联合电压关系、
源顺序、实例反序，以及循环、未选分支和显式零依赖的拒绝。这些开发回归不增加既有 Spectre 对照或论文成绩。

[公开行为回归](../../tests/test_input_initialization.py)保留原 EV-HC-02 源码，
独立检查高/低启动、精确 tie、两个实例、后续迟滞计数、t=0 timer、
算子初态和 held timer 守卫；Rust 私有回归检查不确定区间拒绝与重试。
这些是开发控制，未更改论文源卡、阈值或分母。
[八例实际 Spectre 配对](../../../experiments/backends/input-initialization/README.md)
覆盖高低启动、四种关系的精确 tie 与 real/integer 异刻共享计数，均满足预先固定的有限观测预算。
一般仿射组合、同批冲突/回退和 t=0 timer/算子顺序仍未由这八例建立商业后端对齐；
原 HC01/HC02 的严格终点、导出和输入误差资格尚缺，论文状态保持 I。

<a id="initial-cross"></a>

## 常量初始化与 cross 共用体

本地 L2a 候选接受 `@(initial_step or cross(g,...)) n=seed;`，也可先写 cross 叶子。
这是受限的源码展开：恰好一个无分析限定初始化叶，其余叶子均为已有 cross，
body 只能包含无条件赋值；当前开发切片也允许在体内静态展开 genvar 循环。
它与其他初始化体合起来，仍须使每个状态恰好初始化一次，
初值是绑定后的实例常量，可以引用参数，不能引用电压、状态或历史。
标量和已支持的一维静态索引变量数组沿用同一检查。无状态模型的空体 `;`
沿用纯初始化的 no-op，仍保留已有 cross 的监测和记录。

对上述单状态例子，初始化给出 `n(0)=seed`；以后该块的穿越给出 `n(tau+)=seed`。
初始化在每次新仿真首次求解前安装一次，没有 cross/timer 事件记录，也不变成 timer(0)。
同刻 cross OR 叶子仍按块执行一次，保留实际触发叶子；不同块写同一状态仍服从
[写者检查](#multiple-event-writers)。已有 t=0 timer 在初始化安装后执行。
重新运行或不同参数实例不共享状态。

`syntax.py` 的 `monitored_event`/`analog_block` 把常量初始化送入已有 `Model.initial`，
把 cross 叶子及相同 body 留作运行时事件；`instance_compiler.py` 验证绑定后的初始化常量。
常量共享体继续使用已有事件路径；当前 IR18 的输入比较初始化见[下文](#input-initialization)。
这项限定支持不扩展到 timer 混合、多个或分析限定初始化叶、动态初值、
条件初始化、嵌套事件或冲突写者。纯 initial_step 及已有冗余纯初始化 OR 保持原规则。

[独立契约](../../validation/EVENT_CONDITIONS_CONTRACT.md#3-触发集合初始化与观察)与
[test_initial_cross.py](../../tests/test_initial_cross.py) 检查独立答案：参数为 7，
在 t=1 的另一个 cross 块写 2，t=2 的共享块恢复 7，观察点 0、0.5、1.5、2.5 得到
`[7,7,2,7]`；参数 9 得到 `[9,9,2,9]`。还检查数组、重复运行、叶子顺序/去重、
t=0 顺序、同刻冲突与明确拒绝边界。有限开发检查不证明完整 SAR/va04 支持，
也不替代外部仿真器对照或任意动态组合验收。

## 连续动态与多项式 guard

IR16 已合并状态独立多项式及受限连续算子驱动 cross；值/导数区间隔离根，
同号端点及末端零点不能跳过内部根。切线、平台、事件修改轨迹或不能证明的次序明确失败。
数学、实现和独立测试见[连续动态章节](continuous.md#非线性-guard-的根证明)。
下面仿射根公式与触零约定仍仅用于原 PWL/仿射路径。

<a id="voltage-demand-root-refinement"></a>

### 电压验收失败时细化输入根

输入驱动的非线性 `cross` 可以在电压验收失败后自动细化。原根必须已证明存在且唯一、
导数严格同号，并与其他事件区间分离。调度器在输出查询推进前，从已接受帧建立事件候选，
检查事件时刻及首个物理历史截止点。后者用于发现延迟边沿激活时才出现的误差。
检查点不取自 `output_times`；公开触发容差和电压预算保持原值。

例如 `u(t)=t`、`cross(u²−2)` 时采样 `q=u`，宽根区间会使 q 的电压包围太宽。
对无算子的直接仿射采样，恢复器分别计算采样映射和后续读取映射。
这样不会把采样时刻的 `q(tau)` 与读取时刻的 `u(t)` 当作同一个值抵消。
已有状态包围始终进入计算，不会因重新求根而清零。

设失败消费者原电压预算为 B，固定当前代表时刻后仍保留的误差界为 C，
采样电压随时间变化的保守斜率界为 M。若 M>0 且 C<B，恢复器用向外舍入推导
试算目标 `width ≤ (B−C)/M`。C 只在当前代表时刻成立，并非所有候选时刻的统一误差界，
也不是不可消除的误差下限。因此达到目标后必须从原已接受帧重建候选，用原预算重新验收。
若仿射依赖证明失败消费者完全不受当前采样时间影响，则直接保留失败，避免无效求根。
其他无法可信归因的情况沿用完整细化。

提前停止仅用于没有后续事件、没有保持状态重定位、没有输入与采样状态共同馈通到同一
消费者的直接路径。后续事件可能放大旧误差；输入馈通可能让输出接近零，收紧相对预算。
这些情况继续完整收紧，直到有覆盖后续需求的预算证明。下面的单次采样滤波链可以提出全响应需求，其他历史算子沿用原策略。

设原根区间为 W，中点为 m，导数区间 D 不含零。均值定理给出
`tau ∈ W ∩ (m − g(m)/D)`。`dynamic_roots.rs::refine` 使用区间 Newton
收缩及严格符号二分。目标试算失败后最多再做一次完整细化，两次共用 256 次迭代预算。
达到目标、算术下限、区间停滞或工作上限都会停止；停止原因和实际宽度进入只读诊断。
根存在性和唯一性证书保留，不能证明的区间不会变成单点。

`schedule.rs::refine_input_root` 重新核对原触发容差，代表时刻仍取上界。
候选全部从同一已接受帧重建，成功后只安装新日历项，状态和历史由共同事件事务提交。
失败不改变已接受状态。输入驱动根上的查询若落在根区间内，可用原 guard 的严格符号
证明查询位于根前或根后。下游有算子不会使输入 guard 失去这个证明；被选中的历史仍须独立通过认证。
这个只读证明不改变根区间或采样历史。无法证明时继续拒绝。

这是局部恢复，不是全时域预算分配，也不自动重放旧历史。后续电压和历史认证仍会拒绝
未被预检发现的超预算结果。精确 timer、相连事件簇及历史依赖根不扩展支持范围。
[恢复回归](../../tests/test_root_recovery.py)覆盖有效目标、无效细化、第二消费者回退、
近根查询、滤波继承误差、后续放大及未来相对预算；原[组合回归](../../tests/test_sample_edge_filter.py)
和 Rust 事务测试继续覆盖历史保存及失败重试。
[验证记录](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#directed-root-recovery)
区分解析回归、同源码直接采样对照、既有 Spectre 复用和未覆盖的对齐范围。

### 原始输入根的精确点值

只有原始物理 PWL 源、没有动态 guard 历史或保持参数依赖的孤立穿越根，
可以用精确有理数评价 guard 在 binary64 时刻的值。这个包围与原区间计算取交，
只能缩小已证明的根盒；若两者冲突就拒绝。表达式深度、运算数及整数位数均有上限。
目前支持仿射、加和乘，其他结构继续使用原认证路径。

没有滤波误差预算的此类根，可以主动细化到相邻可表示时刻，之后再提交事件和历史。
这使根右侧的合理查询落在已认证的后事件历史中；不能从一个较晚的执行代表向前伪造历史。
已有滤波链仍按原电压预算决定细化程度，数学根、采样包围和最终误差验收分别保留。
该策略不读取查询网格，也不要求复制 Spectre 的浮点跳变侧。

<a id="filter-root-budget"></a>

### 单次采样滤波链按输出预算停止

单次输入根采样后，若信号只经过固定 `transition` 和稳定一阶前馈滤波，
现在可以由所有电压消费者反推目标根宽度。这样不必每次收缩到机器精度下限。
例如 `u(t)=t`，在 `cross(u²−2)` 时采样 `q=u`，再用 0.5 s 的边沿驱动
`1/(1+0.25s)`。根区间宽度 w 同时引起采样幅值误差和边沿时间误差，两项都必须计入。

设采样斜率界为 M，根窗口内的新旧目标差界为 A，较短边沿时间为 R。
边沿的全响应灵敏度界是 `Ledge=M+A/R`。稳定一阶滤波的指数核非负且积分不超过 1，
因此经总增益 G 后可用 `Lfilter=|G|*Ledge`。同一根引起的两项误差相加，不作抵消。
固定延迟只平移响应，不增加这个上界。

采样固定在当前代表时刻时保留的误差为 Cq，旧边沿和滤波的误差为 Ce、Cf。
规划使用 `Cedge=Cq+Ce`、`Cfilter=Cf+|G|*(Cq+Ce)`。Cq 包含旧状态与采样运算误差。
对每个节点，按仿射投影系数的绝对值累加 C 和 L，再取最紧的
`w_target ≤ (vabstol−C)/L`。只用绝对预算，避免未来输出过零时相对预算缩小。
中间边沿节点也参与计算；负增益使用绝对值，不能让误差抵消。
本例 M=1、A≈1.4143、R=0.5，单位增益时严格 1e-10 V 预算给出约 26 ps 的目标。

这个全响应灵敏度是求根提案，不是完整的未来数值误差证书。
当前 C 不包含未来所有卷积和电路求解的舍入；换代表时刻也可能改变 C。
达到目标后，仍从原已接受状态重建候选，执行原事件与首个历史截止点验收。
失败时最多再做一次完整细化，两次共享原 256 次迭代上限；后续每个输出仍按原证书验收。
当局部预检尚未失败、但全响应提案已超预算时，也会提前细化。
因此宽预算下可能多做一次本来不需要的细化，不能据此声称整体加速。

准入限于一个保持状态、两个算子、尚无已记录事件且无后续事件或保持状态重定位，
边沿输入必须是该状态的单位映射。采样须有可证明的仿射输入斜率，不能依赖算子历史；
消费者不能混入直接输入或不确定投影系数。固定的正 rise、fall、tau 和非负 delay 均由实际参数参与计算，
不按测试数值硬编码。多事件、中断边沿、反馈、多级滤波和历史重放不进入新分配路径。
旧的不确定度不会清零，无法达标仍拒绝。

代码由 `transition_filter.rs::single_filter_budget` 提供旧历史信息，
`settlement_bounds.rs` 的子模块 [filter_budget.rs](../../rust_core/src/filter_budget.rs) 计算各消费者需求，
`transient_root_refinement.rs` 选择试算与回退。公开的
[滤波预算回归](../../tests/test_filter_budget.py)检查解析输出、正负增益、近根查询、主动细化与拒绝；
Rust 同控制器重试检查候选失败不污染历史或日历。
[本轮证据](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#filter-budget)
将解析误差、工作次数和实际 Spectre 比较分别记录。

## 仿射轨迹上的数学定位

固定状态与固定系数的仿射网络在一段 PWL 输入上给出仿射 guard：
`g(t)=g_a+m(t-t_a)`。若 m≠0，候选根为 `t*=t_a-g_a/m`；还需验证段内位置、方向和误差界。
根公式本身不能决定触零/零平台、初始点或同刻状态读取，这些是下面单独定义的行为。
区间包围针对输入 binary64 数值定义的数学问题，不意味着任意源表达式/后端都无误差。

### 原始输入的事件时刻证书

直接驱动输入的仿射 guard 可以保留原始数值来源，避免在端点区间计算后丢失可证明的时间次序。
例如 `u` 在 6 µs 内从 0 上升到 3 V，`cross(u-0.7,+1)` 的原 binary64 数学根为
`tau = rational(0.7) * rational(6e-6) / 3`。它比 binary64 查询 `1.4e-6` 晚约
`1.00027e-23 s`，两者舍入到同一个浮点数。区间端点相减不能证明该查询应读前态，
但原输入可以证明。旧候选因此返回 `event_resolution`，而实际 Spectre 完成了同模型。

`exact_source.rs::Curve` 对原始输入和仿射表达式保留有预算的有理数运算。
在旧 PWL 根发现成功后，`root_in` 核对当前段没有内部 knot、精确端值属于原端值区间、
根属于原根包围，才建立 `RootTime`。若端值为 a、b，时间为 t0、t1，则
`tau = t0 - a*(t1-t0)/(b-a)`，所有项来自未舍入的来源证明。
证明只收紧已有根区间；原斜率、方向筛选、时间容差和表达式容差仍须通过。

`pwl.rs::Root` 的 root-root 排序、同根判断、相对 timer 的排序和局部时间包围
共同使用这一不可变证书。局部时间直接计算 `tau-(start+index*period)`，不先把绝对
时刻舍入成浮点数。`schedule.rs` 随后沿用物理阶段查询和原子事件提交，保证输出查询、
采样与下游 transition 使用同一段历史。证书不改变输出误差验收或失败回退。

该证明仅接受本次请求的原始 driven/ground 来源。追加的生成源即使误差为零也不取得
原始输入身份；内部节点、状态、历史算子和非仿射乘积不能用此证明放行。
曲线最多 512 个点，有理数分子/分母最多 4096 bit，表达式与运算预算沿用
`exact_source.rs`。缺少来源、跨 knot、区间不匹配或预算不足时保留原区间路径，
不能证明次序仍拒绝。根发现之前的符号不确定、一般内部轨迹和极端边界并未因此解决。

[开发回归](../../tests/test_initialized_event_composition.py)独立用 `Fraction` 检查查询侧别、
下降根、等价 OR 与采样历史；Rust 检查来源隔离、区间匹配、预算回退和容差不变。
[Spectre 工程对照](../../../experiments/backends/event-alignment/README.md)保留旧 C1 拒绝和
两档实际参考、完整误差分母及窗口内差异。有限观测通过不代表连续时间资格，
也不意味着 EVAS 复制了 Spectre 的内部事件定位算法。

<a id="backend-cross-tolerances"></a>

### 后端定位方式、容差与波形差异

EVAS 与 Spectre 可以满足同一事件契约，却在容差允许范围内选择不同的触发时刻。
EVAS 在当前受限 PWL/仿射范围内从分段关系求根、包围根误差，再选择并认证可表示的事件时间。
Spectre 的闭源实现不能由波形反推出完整算法；固定 V3 实验确认其实际触发时刻受 cross
容差及时间步设置影响。相同容差数值不保证相同的事件时刻，也不代表两者采用相同的误差控制。

[Verilog-AMS LRM 2.4 §5.10.3.1](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
要求 cross 事件在过零后、同时满足时间与表达式容差。对本例局部线性 guard，斜率绝对值为
`|m|`，可允许的延后为 `min(ttol, expr_tol/|m|)`。V3 中 `ttol=1 ns`、
`expr_tol=200 μV`、`|m|=0.4 V/μs`，因此窗口为 500 ps；Spectre 基础档实际晚 250 ps，
仍位于这个窗口。输出 transition 的斜率为 `0.8 V/50 ns`，此时间偏移对应边沿上的 4 mV
名义波形差值；平台电压及 50 ns 边沿时长相同。

事件日志和六次诊断执行见[实验收据](../../../experiments/archive/pr14-pr15-validation/results/event-writers-timing.json)。
只收紧 cross 表达式或时间容差显著减小了偏移；只收紧全局求解容差没有减小本例偏移。
这支持事件定位差异的解释，不证明 Spectre 出错、EVAS 普遍更准确，或其他模型也遵循相同比例。

后端比较应同时报告独立数学答案、允许的事件历史、实际设置与观测波形差值。
容差内的差异可以与双方达标并存；超出独立契约的差异仍须作为失败保留。
不能事后扩大容差、逐点任意平移波形，或用后端相互接近代替正确性判断。

<a id="integer-bitops"></a>

## 有限整数位运算

本分支的有限标量实现接受 `&`、`|`、`^`、单目 `~`、`<<` 和 `>>`。
操作数必须具有源语言的 integer 类型。`1.0`、real 参数和返回 real 的函数不能因数值恰好为整数而参与位运算。
依据是 [VAMS LRM 2.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
§4.2.1、§4.2.9和§4.2.11。标准规定移位补零，右操作数按无符号解释。
32位范围沿用EVAS现有signed32整数契约，不扩展为任意精度整数。

对整数 `n`，先取位模式 `u=n mod 2^32`，再执行逐位逻辑或移位。
左移丢弃超过32位的位，右移以零填充；移位量按32位无符号值解释，至少32位的移位结果为零。
最后将结果最高位解释为符号位。因而 `(-1)>>1=2147483647`，`1<<31=-2147483648`。
左移丢弃位是该运算本身的语义，不能使其子表达式中的普通整数加减乘溢出合法。
算术移位、归约运算、带宽度的数字字面量和隐含real转换不属于本切片。

参数绑定时直接折叠常量。含位运算的纯整数事件表达式若只读整数状态和参数，先证明独立状态域基数的乘积不超过256。
每组状态绑定复用现有typed lowerer，逐个验证全部整数中间运算，随后把整个表达式降低为一次平衡`Select`树。
这保留同一状态多次出现的相关性，避免逐运算嵌套选择的重复展开；不改变不含位运算的表达式。
该机制不接受电压、数组、条件或历史调用。其他上下文继续按每个操作数区间构造有限树，域基数乘积也须不超过256。
两种路径均在分配前检查组合预算，原表达式、选择树和全局IR预算继续适用。
该办法枚举的是已证明的小输入域，不按32位宽穷举位模式。移位量须为实例常量。
未证明值域、过大输入域或运行时移位量返回`unsupported_integer_bitwise`，不取近似值。
`CheckedInteger`内部算术必须在截取成功区间之前已证明signed32安全，否则位运算拒绝。
这样有限树常量化不会丢掉本应失败的中间检查。检查下标也采用相同的未截取范围要求。
非字面量操作数的单值范围通过同臂`Select`保留整个原操作数的读取，包括比较谓词里的数组槽和下标。
表中不同输入得到相同输出时也不删除状态谓词，以保留同刻其他事件块的读写冲突检查。
静态`for`控制、数组声明界限和初始化静态数组循环体直接写位运算仍拒绝；
普通genvar循环体在展开后接受常量移位。

持久状态值域沿用`event_index_domains`的事件闭包、回边、顺序写入及中间状态联合范围。
小输入域的抽象传递取全部输入组合结果的最小和最大值。
此外，非负常量掩码`m`满足`0 <= (n & m) <= m`，这个包围不依赖`n`的初值。
其他无法证明的传递保持未知，不能从某次初始化值推断整个仿真范围。

实现入口是`integer_bits.py`的定宽运算与类型规则、`parameters.py`的常量绑定、
`instance_compiler.py`的有限选择树及`event_index_domains.py`的范围传递。
IR24、Rust整数写入检查、事件求解、误差预算和候选提交与回退均未改变。
独立公共回归见[test_integer_bitops.py](../../tests/test_integer_bitops.py)，包括定宽负数边界、
小型移位寄存器的顺序事件、普通analog掩码、参数默认值及拒绝控制。
[证据说明](../../../experiments/backends/support/integer-bitops/README.md)区分本地验证和实际Spectre对照。

<a id="typed-integer-closure"></a>

## typed 整数除法、余数与有限 real 幂

两个源 integer 操作数的 `/` 向零截断，`%` 满足 `n=d*q+r`，非零余数与被除数同号。
例如 `-9/2=-4`、`-9%2=-1`。任一操作数为 real 时除法保留 real 语义；
`real q=9/2` 得到4，`9.0/2` 得到4.5。参数默认值、范围端点和父实例覆盖均沿用源类型，
覆盖参数仍使用原来的依赖替换规则。零除、signed32 中间溢出和 `INT_MIN/-1` 不因最终余数为零而合法。
未知除数域继续拒绝，不能把 real 值恰好为整数当作源 integer。

`integer_arithmetic.py` 对固定非零除数计算商与余数的有符号范围，
`event_index_domains.py` 沿事件回边和顺序写入联合证明整个生命周期的范围。
模计数器 `n=(n+1)%8` 可由此证明有限域；先检查 n+1，不能让 `%8` 掩盖中间溢出。
`integer_constants.py`、`parameters.py`、`hierarchy.py` 与 `node_elaboration.py` 共享常量类型语义，
实例编译复用既有整数检查。独立正反例见 [test_integer_math_closure.py](../../tests/test_integer_math_closure.py)。

静态展开中的scalar integer和genvar循环下标也保留源integer类型。
`elaboration.py::substitute_value` 只给已通过固定边界及signed32检查的循环下标替换叶保留此类型，
不把数值恰为整数的real常量或变量改为integer。`j=-2..1` 的 `j%16` 因此依次为-2、-1、0、1；
原中间溢出、控制变量写者和4096展开上限继续检查。
[独立编译与公共内核回归](../../tests/test_static_loop_integer_type.py)检查常量IR、执行顺序和拒绝控制；
[分支证据](../../../experiments/backends/support/low-cost-closure/static-loop-type.json)仅认证这个类型修复，
不证明完整原请求的累计预算或后续历史消费者已闭合。

运行期整数指数的有限 `pow` 扩展要求底数为正的常量二进制幂，指数源类型为 integer，
且已证明的整个指数域在 [-32,32] 内。`finite_math.py` 只生成有限且可精确表示的 binary64 常量叶，
例如 `pow(2.0,n)` 和 `1.0/pow(2.0,n)`，结果保持 real 类型。
它复用既有 `Select`，单值域也保留原指数读取，不能掩盖同刻读写冲突。
非整数指数、未知或过大域、非二进制幂底数及不能精确有限表示的原值不获得此扩展。
原有常量幂路径按自身合同保留。

有限域仍受256组合与4096实际展开决策预算、原源码和IR限制约束。
资源审计包含参数死臂中实际生成的选择树，所有原操作数和整数中间检查保留。
这不是一般 real `pow` 近似器，也没有新增opcode、时间证明或接受与回退策略。
实现与原件状态见[紧凑证据](../../../experiments/backends/support/low-cost-closure/README.md)。

### 事件体的原生 typed 加法与常量余数（IR27 本地候选）

旧有限域表示优先。仅当其商分段或整数中间范围表示不足时，事件体可生成独立
`integer_primitive`。第一版只包括源 integer 的 Add 和常量非零 signed32 除数的
Remainder；叶只能是 `integer_literal`、同实例 integer `integer_state` 或同类子树。
real 的整数点值、电压、时间、算子和实时 Floor 结果不能直接成为 typed 叶。
源 Floor 仍须先通过原有输入/单 bin 证书并写入合法 integer 状态。

`integer_primitive.rs` 对每个原节点执行 `i32::checked_add` 或 `checked_rem`。
余数向零截断并与被除数同号，`INT_MIN % -1` 拒绝。点路径与盒路径共享这些操作，
盒路径仅接受单点 signed32 state；不从非点盒选择代表值。原 counter 保留真实递增，
后续取余、clamp 或写回不能挽救前一个节点的溢出。同回调每句读取前序局部写入，
不同回调仍保留原同批次冲突规则。失败退出候选帧，不提交状态、历史、日历或输出。
零时刻 timer 的冷启动依赖审计也识别新节点，但原冷历史 seed 的单点证书保持。
输入点值与原 real 算术形成非点 `vout` 盒时，只有下述裸保持状态 Transition 门可保留该盒构造冷历史；其余组成保留原point要求。

前端的新增 typed 构建逐节点扣原事件审计的100000额度，审计与最终构建复用同一 owner，
不因重试恢复额度。原256域、4096决策、IR100000/depth96与精确证明512/depth64上限保留。
可选有理来源解释继续扣原 `value_with_work` 调用方及 `Budget`，缺证或耗尽返回 unknown。
`event_control.rs` 拒绝贡献、算子目标和事件 trigger 中的新节点；`causal_event.rs` 只为新节点
开放实际驱动输入与保持 state 的路径，原 CheckedInteger/Floor/loop 门不变。

独立公共例见 [test_native_integer_events.py](../../tests/test_native_integer_events.py)，
同引擎失败后两次重试见 `transient_lifecycle_tests.rs` 的
`native_integer_failed_prefix_rolls_back_and_retries_same_controller`。
该切片已进入wave16统一候选，原324通过原checker；同候选的原377依赖事件体输入别名闭包。一般runtime除数、位运算、连续integer输出及内部反馈仍不在此范围。原077完整运行后仍为checker FAIL，首个4.896ns失败由原稀疏网格跨边沿插值造成，原FAIL保留，不由派生查询改判；身份和诊断边界见[低成本闭包收据](../../../experiments/backends/support/low-cost-closure/evidence.json)。

### 事件体运行期余数与二元减法（IR28 本地候选）

IR28 在上述源 typed 事件树中增加二元 `Subtract`，并接受 Remainder 的 typed
运行期除数。叶类型、同 owner 审计、真实原节点 origin 和点 signed32 盒要求不变。
前端仅在明确的 typed 余数表示不足处进入既有 native fallback，不捕获任意编译错误。
旧有限域成功路径优先，旧表中确定的零除或越界行仍静态拒绝；字面量零除与常量中间溢出
也不迁为运行期成功路径。宽域 state 的运行期零除在实际选中的原节点报错。

对已接受的整数点，`a-b` 使用 `i32::checked_sub`，`a%d` 使用既有 `checked_rem`。
减法先于父节点执行，即使父节点乘零、取余、clamp 或后续赋值也不能消除其溢出。
余数满足 `a=d*trunc(a/d)+r`，非零余数与 a 同号，零除及 `INT_MIN%-1` 拒绝。
例如 `-9%8=-1`，`(9-2+0.0)/2.0=3.5`；后者仍先检查源 integer 减法，
再按原 real 规则传播数值误差。动态除数在每次使用处读当前局部 state，不能缓存写前值。
成功余数的保守编译包围为 signed32 模数所允许的 `[-2147483647,2147483647]`，
不据此替代执行时的零除、溢出和点盒检查。

点与盒执行仍共用 `integer_primitive.rs::evaluate`，每个节点、操作数及操作扣同一 work
回调；可选有理来源沿原调用者预算，耗尽保持 unknown 或原拒绝。Python 构建沿既有
事件审计 owner 扣费，不新开 fallback 额度。普通贡献、trigger、算子目标、整数 Divide、
单目负号、Multiply、位运算、Floor 和全局 CheckedInteger 准入均未扩展。
零时刻依赖审计仅复用原 typed 节点验证，冷历史的裸 real StateRef 门不变。

公共独立例见 [test_native_integer28.py](../../tests/test_native_integer28.py)。同一 Controller
在真实除零或减法溢出后两次重试的回滚测试为
`integer28_runtime_failures_roll_back_twice_in_same_controller`。这些开发例不代表
原069/335通过、完整Python通过或安装验收；原件收益上界为两项，已验证新增PASS为零。

### 裸保持状态 Transition 的有界冷初态（本地候选）

固定精确timer0执行之后，原点执行值与 `Prepared.bounds` 是两套证据。
例如binary64字面量的`.2+.1`名义值为`.30000000000000004`，实际原盒可为
`[.3,.3000000000000001]`。它是有限有界初态，不能改成名义值的单点。

本门仅接受整program的历史算子全部为Transition，每个原IR input都是裸、同owner、
kind=real的StateRef，并走普通固定timer的 `independent_schedule` 分支。
一般Select/仿射目标、DC voltage alias、其他算子、history-calendar以及dynamic/relocalized guard
保留原point门。初始化语句、未选臂依赖、writer/整数检查和精确零时刻cursor不变。

若名义状态为\(\hat x\)，原证书为\(X\)，冷历史直接由既有
`Transition::enclosed(\hat x,X,delay,rise,fall)`构造settled初态。
初始level在首个实际更新前始终包于\(X\)，delay/rise不产生伪t0边沿；
不调用`advance_at(0)`伪造初始化转移。有限性、向量长度和名义值落在原盒内均先检查。
`transient.rs`在历史构造前借用Prepared.bounds，`operators.rs`的专用私有入口沿原constructor
与source_context/history_work创建一次历史，旧入口默认point行为不变。

Frame.state_bounds和Operators的初始盒仍一起通过原 `model.certify_observation`。
初始输出的误差放大超过原电压预算必须拒绝，有限初态不是单独的接受条件。
失败前不发布frame、日历消费或输出。后续事件沿原Controller候选事务，失败后重试不能改变
种子盒、历史、proof、records或outputs。观察网格不改变物理初态。

独立公共合同见 [test_transition_bootstrap_bounds.py](../../tests/test_transition_bootstrap_bounds.py)。
其Fraction答案取原binary64字面量，不来自EVAS输出；另有严格高增益拒绝、passive初始display
保留和原nonbare目标拒绝。私有bootstrap测试记录实际state/history盒，同Controller回归在
`transient_lifecycle_tests.rs::bounded_cold_transition_seed_survives_two_failed_same_controller_callbacks`。
这些开发证据不替代原件checker、完整候选CI或安装验收。

<a id="wave6-local-closure"></a>

## 波6b起有限闭包与当前验收身份

以下机制已纳入历史波6b的149文件源码与release核 `5935fd87` 全量：261通过、18失败、121拒绝，296相对波5回退。
最新wave12固定158文件源码、IR25与release核 `83da6b2b521c` 的完整400为292通过、18失败、90拒绝。
原198及有效波10的278份通过全部保留，新增14份，无回退；历史波11的十份Select回退已恢复。开发回归与精确提交CI状态见紧凑收据，机制合同不等于所有相关模型通过。固定身份、历史回退及后续开发边界见[紧凑收据](../../../experiments/backends/support/low-cost-closure/evidence.json)。

held timer 仅在整个period包围非正且整个start包围严格为负时，认定过去单次事件的当前日程为空。
后续状态更新仍会重建该timer日历，可将它改期到未来。负start配正period、跨零start或跨正周期制度的区间保持拒绝。
`add_timer` 不修改trigger或接受状态。公开过去单次、重启及正period拒绝见
[test_timer_closure.py](../../tests/test_timer_closure.py)；该文件的源误差负控止于前置准入，不证明内部跨零区间分支。

已认证输入投影可为普通PWL alias根恢复原source `RootTime`。
`GuardBounds::exact_input_expression` 只返回全部系数为点、无残留状态或算子列的原输入表达式。
`schedule_with_history` 优先使用原guard曲线，投影回退仍须通过 `Curve::root_in` 的分段、端点与已发现根匹配。
相同浮点包围不能代替同根证明；相邻不同有理根仍分开回调。
别名两个transition期限与近根控制见 [test_scs_closure.py](../../tests/test_scs_closure.py)。

零时transition bootstrap候选只要求种子依赖状态为点包围。
无关real状态可以保留有限且包含名义值的非点包围，随后事件采样、历史和电压验收必须继续携带它。
`transient_initialization.rs::prepare_stage` 不把非种子值压成点；非transition算子组合仍保留原全点限制。
公开 `BootstrapNonseedBounds` 和Rust同控制器失败重试分别检查236形状的启动、后续放大拒绝及回退，
不开放非点 `State.initial` 或一般bootstrap历史。该候选局部证据见
[test_initial_sampling_closure.py](../../tests/test_initial_sampling_closure.py)。

160形状的运行期整数除数候选将纯integer根表达式所读的联合StateRef域枚举为既有Select树。
联合域须不超过256，每行复用原strict lower，保留signed32中间检查、真实除法与余数语义和全部状态读取。
单值域也保留同刻读取依赖；零除域、未知或过大域继续拒绝，运行移位量未扩展。
该入口由 `integer_expression_table` 触发，`integer_arithmetic.py` 提供有符号范围；4096决策和原IR预算保持。
[test_integer_math_closure.py](../../tests/test_integer_math_closure.py)覆盖正负除数、除数改变、预算和隐蔽中间错误。
160原件在波6b完整验收通过；069等未闭合的嵌套组合仍保留拒绝。

### 波7有限 floor 合同

`floor(x)` 与 `$floor(x)` 的内建结果保留real类型；结果碰巧为整数不赋予integer位运算身份。
裸调用优先绑定同模块已声明的用户函数，包括其他函数体中的前向引用；`$floor` 始终显式调用内建函数。
合法参数或局部名 `floor` 继续按变量读取。独立兼容控制见 [test_floor_syntax.py](../../tests/test_floor_syntax.py)。

内建仅接受有限常量或在调用之前由原始源码证明的有限裁剪范围，再分解为既有选择树。
联合区间划分不超过256，实际展开仍计4096决策和原IR预算；后置裁剪、testbench输入范围和观察到的数值不能充当前置证明。
每个所选输入误差盒必须落在同一整数bin；跨边界或所选原算术中间值非有限时拒绝。
保留原参数求值、signed32赋值检查、未选臂结构与源依赖检查，不用整数转换隐藏原除法或溢出。
合同正反例见 [test_finite_floor.py](../../tests/test_finite_floor.py)。该机制已纳入波7固定150文件源码与release核 `1d0845b6` 的完整400验收，224通过原checker；050、052仍因source transition证明预算拒绝，预算未放宽。
历史波7共269通过、18失败、113拒绝，不把floor入口可编译视为原件通过。波8纳入以下整数读取与点时间证明；后续Slew、证明缓存及tanh不计入当时272，已进入wave12。

<a id="event-floor-ranges"></a>

### 同一回调前序赋值的floor范围（分支已验收，未合并）

事件中的real局部量若在该次使用之前已由源码赋值及裁剪证明有限范围，
可用该范围构造既有floor选择树。例如先夹 `x` 到 `[0,7]`，再取 `$floor(x)`。
每个回调从未知范围开始，事实按源码顺序传递；条件两臂取hull，
未知循环写入清除事实。同一函数展开DAG在多个位置使用时取所有使用环境的共同安全包围，
不能把某个调用点的窄范围带到另一回调、ordinary analog或初始化阶段。

`$floor`仍返回real：`$floor(9/2.0)/2`为2.0，不能把外层除法变成integer除法。
integer赋值只在独立证明整数值及signed32范围后消费该结果；原整数 `9/2` 仍先得到4。
这项静态范围只用于有限分区，原可执行赋值、全部数值包围、溢出和除数域检查均保留。
整个实际输入区间跨bin时拒绝，不能用名义值代替；原256分区、4096决策及100000 IR预算不变。
公开顺序、跨回调和typed控制见
[test_event_floor_ranges.py](../../tests/test_event_floor_ranges.py)。

<a id="native-event-floor"></a>

### 原生事件floor：实际驱动仿射输入的本地候选

有限范围选择树仍是第一入口，原来成功的IR除schema外保持一致；256分区或其他资源拒绝不转入新路径。
事件中的 `floor(8*V(vin))` 若缺少源码前置范围，可用IR26的单参数 `event_math/function=floor` 表示。
新入口只接受参数及原始输入电压构成的仿射表达式，缩放系数限精确二进幂；非二进缩放/除法不以已舍入系数重建floor切点。
producer审计原操作数，保留零系数、未选臂和原算术检查；
内核按实际driven/ground节点再次审计。State、内部反馈、电压未知量、时间、一般事件数学均未因此开放。

设原参数认证盒为 `[a,b]`，floor盒为 `[floor(a),floor(b)]`。两端不同时在该操作处拒绝，
不能因后续饱和到同一值便抹去原中间不确定性。只有既有精确物理根/输入来源链在原盒内证明唯一值时，
才可收紧floor盒；非零源误差没有这张来源证书，代表时刻与中点不能代替它。负数按向负无穷取整。
例如 `floor(-0.5)=-1`；跨越-1的输入盒包含两个floor值，即使二者后来都夹成0也拒绝。

floor在源码中返回real，`floor(3.0)/2`为1.5，不能直接作integer位运算操作数。
每条原integer赋值仍检查精确整数值与signed32范围，后面的 `if(code>7)code=7` 不补救此前溢出。
点求值、区间、精确有理值证明与状态写入分别保留原表达式顺序；失败候选不提交状态、记录、日历或proof。
所有已有分区、IR、路径证明、精度与执行预算不变。

前端由instance_compiler.py::finite_floor保留旧入口并审计新操作数；Rust event_numeric.rs执行点/盒求值，
event_value_proof.rs复用LocalState、RootTime及有理数预算。settlement.rs把现有证明上下文送给causal_event.rs，
后者只允许已证明实际驱动依赖的floor。该因果证书也用于贡献Select的预览、联立解和重放，未知反馈的原拒绝保留。
同控制器跨bin失败与精确源重试由transient_passive_tests.rs检查，公共合同见
[test_native_event_floor.py](../../tests/test_native_event_floor.py)。这仍是未合并候选，原checker与安装验收归主集成，
不以原件能完成执行宣称通过或提高Q资格。023的同回调局部量除法和027的modulo不在此次范围。

<a id="integer-prefix"></a>

### 普通integer分支的共有前缀（分支已验收，未合并）

普通analog中已声明integer目标的分支合并，可把两臂引用同一IR对象的整数前缀保留一次。
例如两臂分别为 `prefix+2` 与 `prefix-3`，合并为 `prefix+(condition?2:-3)`。
原两臂必须先分别通过整型及signed32检查；原guard、来源、未选臂名字和真实IR预算保留。
该入口只接纯原始整数树，不移动State、历史、事件值或checked包装，也不按结构近似匹配不同对象。
real目标及callback赋值不获得此重排。公开正反例见
[test_integer_prefix.py](../../tests/test_integer_prefix.py)。

<a id="rational-transition-levels"></a>

### 中断边沿的有理保持目标（分支已验收，未合并）

已证明来自原输入标量的保持目标，可沿用其精确有理依据计算中断及反向transition的期限。
两个结束包围相同本身仍不证明同一数学期限；相邻不同期限不能合并。
原目标表达式与held selection决定新边沿，不能把中断点的名义输出充当原目标。
原采样误差、边沿误差及后续内部采样误差继续进入历史和未来放大验收。
没有原标量证明的内部采样保留不确定性；真实source_errors不因有理证书变成零。
这不扩大一般连续目标或非点时间证明。公开中断、反向及放大控制见
[test_transition_rational_levels.py](../../tests/test_transition_rational_levels.py)。

<a id="settled-integer-reads"></a>

### 波8隔离整数输出读取

普通整数编码表达式可使用已经证明的事件入口不变量与整个生命周期范围的交集，不能用入口事实覆盖更强的旧范围。
这只适用于唯一扁平实例、无内部模拟节点、输入／输出实际网不同且输出实际网彼此不同的完整程序。
每个输出必须恰有一条接地电压贡献；普通、声明初值、initial_step、事件、触发器、final_step及显示中的电压读取都只能来自输入。
其他实例或观察者、内部网、反馈、端口别名及非唯一输出贡献均关闭证书，回到旧生命周期准入；不授予一般组合支持。

缩小范围只在全部初始化、事件和final_step降低完成后，对普通表达式读取生效。
例如声明 `q=259` 后，initial_step先取 `(q>>1)&1` 再把q置零，保存的仍为1。
完整事件中的临时过冲不能当作普通输出观察，但其signed32中间错误也不能由随后裁剪消除。
有限整数整式仍逐行检查原类型、每个原算术中间值与除数域，联合组合不超过256、展开决策不超过4096，原IR预算保持。
单值表仍保留原状态读取；real除法仍是real。公开正反例见 [test_settled_integer_reads.py](../../tests/test_settled_integer_reads.py)。

可选全局整数范围证明共享原100000工作量。耗尽时不再搜索，也不授予有限不变量，
编译器退回完整signed32未知范围；原源码、索引、整数类型与运行时检查继续。
因此旁证耗尽本身不挡住能由原路径执行的模型，仍需有限范围证明的表达式也不能借此获准。

<a id="held-time-point-proof"></a>

### 波8 held timer的点时间证明

只有简单held timer的real状态start，且其已接受的前状态包围有限并满足 `lo==hi`，才能补充 `RootTime::point` 初始证明。
已有效的原根证明继续优先，不能用非点包围的名义值或端点伪装精确时间。
对原时间证明作加法时，除字面常数外，也可使用已证明且可由单个binary64精确表示的保持标量偏移。
标量事实在同一回调中按源码赋值顺序更新；每个并列回调从相同已接受前状态独立开始。
未知写入会清除标量事实，电压、历史、非点偏移和 `0*unknown` 均不能获得该证明。

加法仍走原 `RootTime.shifted_fixed`，结果必须细化到原后状态包围；原数值包围、电压误差与事件阶段判据保持。
因此 `.5/3` 等不能精确点表示的偏移继续回退，362仍有非点除法偏移限制；这不扩展一般时间生命周期或非点时间制度。
公开顺序、阶段和未来误差负控见 [test_held_timer_provenance.py](../../tests/test_held_timer_provenance.py)。
两个合同已在波8完整原件验收，194、098及026通过原checker；作者与独立审查收据见[紧凑证据](../../../experiments/backends/support/low-cost-closure/evidence.json)。

#### 本地候选：普通 held timer 的有理偏移

2026-10-21 的最小合同扩展上述普通路径：`LocalState` 从真实点输入证明的
有理偏移无需再压成单个 binary64。例如 `due=$abstime+0.5/f`、`f=3`
保留精确 `1/6`，下一事件为 `binary64(0.1)+1/6`，不能选择包围上端点作为物理时刻。
`event_time_provenance::expression_with_points` 复用原标量证明，
以 `RootTime::affine` 保存有理和，并继续用原后状态包围细化；原数值状态和误差不变。
所有原操作数都须有证明，非点输入、隐藏 `0*unknown`、矛盾后状态包围仍不获证书。
付费 history/forcing 路线仍走未扩展的 `event_history_time`，本合同不解除其偏移限制。

完整普通消费者还需要事件发生位置的输入证明。`apply_with_context_charged`
接收该次回调的 `event_value_proof::Context`，按源码顺序证明输入、限幅结果和下一期限。
它使用已接受的前状态，不能从最终写回状态反推中间读值。并列回调各自从前状态开始；
候选后状态盒只用于检查所得时间证明的包含关系。已有 analytic/history 付费 owner
继续委托原路径，不借这个普通入口获得额外数学能力。

[独立截止点测试](../../tests/test_deadline_origin_contract.py)按
`t_k=binary64(0.1)+k/6` 和线性过渡公式检查相同及不同固定移位、多实例和查询不变性。
[原 held timer 测试](../../tests/test_held_timer_provenance.py)保留赋值顺序和未来放大误差反控；
Rust `held_point_tests` 检查同一 Controller 的失败重试，原 deadline/calendar 控制检查
相同数值包围不代表共同根、相邻真实期限不能跳过。Python 的近邻 duration 波形比较
受其电压容差限制，不单独证明一个 ULP 的期限差。此为未提交候选，无新 Spectre 或完整案例信用。

#### 本地候选：历史谓词中的原电压接口

当消费者读取另一个含 `Select` 的电压贡献时，展开树只用于证明依赖和选择谓词。
`history_admission::Admission::resolve` 从原请求取贡献，递归解析选中分支，
保留值树中的原电压接口。生产者 `V(port)=q/8`、消费者 `V(y)=V(port)+1/2`
仍由两个实例各自的方程求解；不能将生产者的裸 `State(q)` 移进消费者的 owner。
原 IR 的所有 owner、隐藏分支和原请求绑定检查先完成，新增遍历、展开与复制复用同一 Work。
不确定谓词失败不改变原 Program；重试继续耗用原额度。

[公开归属正反控](../../tests/test_history_owner_contract.py)采用不同初值和事件时间的两组实例，
以 `q/8+1/2` 独立计算结果，并检查实例声明顺序、查询不变和非法裸跨实例 State。
Rust `owner_contract_tests` 覆盖错误绑定、同 Admission 失败后重试及实际解析耗尽。
普通仿射读出或直接 Transition 谓词未必触发这条路径，不能用它们通过来替代目标缺陷的红例。
本合同不解决原390后续证明预算前沿，不增加完整390的通过数。

## PWL 与事件的执行契约

这是限定实现范围，不是完整 Verilog-A 事件支持。语言依据见
[LRM 2.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf) 和
[事件语句参考](https://verilogams.org/refman/modules/analog-procedural/timing.html)。

- 声明标量 `integer` / `real` 状态，缺省初值为零。`@(initial_step)` 按源码顺序赋值，
  可以重复写同一状态；每次写入均须合法。常数可以引用有效实例参数；两种状态均接受
  [受限 driven 输入条件初始化](#input-initialization)。
  Rust 在 t=0 的首次求解前安装一次；[共享初始化/cross 体](#initial-cross)仍限常量体。
  初始高电平、初始零值的离开本身不产生 `cross`。
- `@(cross(g[, direction[, ttol[, tol]]]))` 接受空语句、顺序赋值或下述受限 if/else 块。方向为 -1/0/+1，默认 0；
  两项容差必须为正的有限实例常数，默认分别为 1 ps 和 1e-9 表达式单位。不支持 cross enable；cross 的受限 `or` 见[OR 规则](#event-or)。
- 事件同刻贡献及赋值表达式仍须对电压和状态联合仿射；更广连续多项式贡献、积分和 guard
  的限定范围见[连续动态](continuous.md)。以下仿射事件规则继续适用。
  根据 IR 结构保留变量依赖，不以舍入为零的系数证明某项为常量。事件赋值 RHS 的双变量乘积仍拒绝，
  即使存在代数抵消也可能保守拒绝。贡献中的有限状态与算子乘积见下节；区间转换不能静默丢弃乘积项。
  整数状态采用精确 signed 32-bit 范围，仅接受整数常数/整数状态运算，普通整数算术超范围报错，不模拟其溢出或隐含取整；有限位运算按[定宽位模式](#integer-bitops)解释。
  real 状态可以在事件时采样仿射电压表达式。
- 每个实际候选批次中，每个状态最多由一个 cross 或 timer 事件块写入。
  不同事件块可以在可证明不同批次触发时写同一状态；若同一批次实际选中的两个块写同一状态，
  返回 `event_conflict`，不按声明顺序、源码位置或事件类型决定胜负。
  事件块可读取其他未在本批次写入的状态，使用事件前已接受值。若选中的另一个块
  在本批次写入被读取状态，则明确拒绝，不按声明顺序推测读取值；结构相消与下溢不消除依赖。
  读依赖包括赋值、已证明选择的条件与 `$display` 参数；无法定符号但证明两臂等价时，两臂的读取和子条件均计入。参数内部的三目表达式保留两条值臂的结构依赖。
  例如同刻一个块写 `q`，另一个块执行 `$display("%g",q)`，也须拒绝。
  未选中的事件分支不产生显示读冲突。同块语句依次看到自己的更新。
  支持同块对同一 integer 状态重复赋值，和 real 一样逐句更新局部状态。
  每次 integer 赋值都检查精确整数及 signed 32-bit 范围，后续写回合法值不能掩盖中间越界。
  与特定 Spectre 版本的重复赋值差异见下文，不将其作为整体拒绝合法程序的依据。
  同刻事件从同一份事件前状态出发，
  将更新 `s+=Phi(s-,v+)` 代入原电压方程，联立求解同刻电压；同块赋值顺序保留。
  求解后重放原赋值、检查原电压方程残差与状态一致性，再整批提交。整数状态精确一致，
  real 状态重放使用 `reltol * max(abs(state), abs(replay))`，不借用电压绝对容差。
  另从原 IR 用向外舍入独立重建联立方程，包围事件后的电压和状态；
  电压误差须小于 `vabstol + reltol*abs(v)`，integer 状态须精确。
  预算取向下界、误差取向上界，不能认证时返回 `event_accuracy`。
  通用 real 状态没有声明物理单位，不单独套用电压绝对容差或
  `reltol*abs(state)` 门槛；接近零的采样可以由其电压消费者证明满足预算。
  每个 real 状态仍必须有有限的完整误差区间，返回的 `transient.states` 是名义值，
  不附带状态自身的相对误差保证。未立即显现在电压中的误差可以被接受，
  但后续电压、算子历史、cross 阈值和保持状态 timer 参数必须使用保存的区间。
  对依赖状态电压网络的事件条件，现有 `unsupported_condition` 限制继续适用。
  初始化、事件候选及普通观察时刻统一使用原 PWL 输入包围和已接受 `Frame.state_bounds`，
  不以条件或算子是否存在为精度开关。
  新状态区间随成功批次提交，失败候选不改变它；后续放大必须继续验收这份不确定性。
  无算子的观察仍复用固定电路分解，认证失败前不更新接受帧。冗余关系若只在某个状态点成立，
  而非误差映射状态域的恒等式，可能在初始化就明确拒绝。
  [独立采样/跨事件回归](../../tests/test_precision_chain.py)、
  [接近零状态与后续消费者回归](../../tests/test_sample_state_precision.py)和[review 记录](../../../experiments/runs/parallel-gap-integration/REVIEW.md#precision-chain)
  记录该变化。均不覆盖前端常量折叠，也不是通用物理单位误差保证。
  无唯一数值解或不能通过一致性检查时明确拒绝，失败不消费事件。容差不用于合并相邻事件。
- 固定日程的 guard 必须与事件状态独立。事件修改的仿射 guard 使用下述候选日程重建；
  其他状态反馈 guard 仍拒绝。结构依赖不以浮点小系数阈值消除。
- 每个驱动用连续 PWL 点列描述，从 t=0 开始、时间严格递增且覆盖 stop；不接受重复时间造成的跳变。
  `output_times` 是 [0,stop] 内严格递增的有限观测时刻，`stop/max_step` 均为正且有限。
  观测时刻会实际求解；若恰逢接受的事件时刻，返回事件后电压。事件不必落在输出网格上。

外部源可另给逐源的绝对电压误差上界。Python `transient` 的 `source_errors`
按驱动节点命名；原生请求 `transient.pwl_errors_V` 按 `pwl/driven` 顺序排列，长度必须一致，
每项为有限非负电压值，或下述 IR24 的物理曲线描述。省略表示全零，显式 null 或错误长度拒绝。
对于非零误差 `E`，`Trajectory.value_bounds` 在名义 PWL 插值的区间上加 `[-E,E]`，
并清除该源的精确曲线证明。固定 timer 的 real 采样使用此区间；后续状态电压放大继续检查原误差预算。
仅有幅度界的请求拒绝所有算子、cross 和保持状态 timer，避免把单一幅度界当作导数或根时刻证明。零误差源保留原路径。

SCS pulse 的原时间参数是已解析 binary64 的精确有理数。设精确拐点为 `t_k`，保存拐点为 `s_k`，
`D=max(abs(s_k-t_k))`，最大原坡度 `L=abs(val1-val0)/min(rise,fall)`。
在相邻拐点间对时间位移线性插值，位移仍不超过 `D`；原 pulse 是 Lipschitz 连续函数，
所以同一时刻的原波形与保存 PWL 相差不超过 `L*D`。
端点电压本来就是输入 binary64，没有额外端值舍入；误差上界用有理数求积，再向上舍入。
折点合并或边沿不能表示时仍拒绝。源码、构造证明和独立预算回归分别见
[scs_sources.py](../../src/evas/scs_sources.py)、[pwl.rs](../../rust_core/src/pwl.rs) 和
[test_source_uncertainty.py](../../tests/test_source_uncertainty.py)。原曲线的有理数角点和舍入差保留在运行元数据，
不把保存 PWL 当作原 pulse 的精确定义。

<a id="physical-source-shape"></a>

### 已知物理源曲线

IR24 的 `pwl_errors_V` 还接受 `{voltage_error_bound_V, exact_knots}`。每个角点含
十进制整数字符串 `time_numerator`、正的 `time_denominator` 和有限 binary64 `value_V`。
Python 保留 `source_errors` 的数值接口，另以 `source_shapes={节点名: 角点列表}` 提交曲线。
这份描述声明唯一的连续物理 PWL，不表示幅度带内任意扰动。内核仍验证声明的非零投影误差。

令名义曲线为 `n(t)`，物理曲线为 `f(t)`，声明幅度界为 `E`。
两者角点的并集划分时间轴；每段上的 `f-n` 都是仿射函数。
内核用精确有理数验证并集的每个端点满足 `|f-n|<=E`，从而证明整个 `[0,stop]` 的包含关系。
实际电压取 `f(t)`，每次转 binary64 的向外舍入区间继续进入方程、状态与下游电压验收。
已识别物理曲线后，投影带用于验证名义表示与物理输入的关系，不再作为任意噪声重复叠加。
无法给出物理求值时仍保留名义插值和原幅度带的保守路径，不能无界接受。

cross 在物理角点分区上完整枚举根，保留原有到零触发、方向、精确根排序和事件窗验收。
不能在发生位移的名义角点之间直接插值来代替物理分区。已认证根通过现有 `RootTime`、日历与
接受/候选 transition 历史传递；误差仍由各消费阶段检查。查询不改变历史，失败候选不提交状态或队列。

guard若引用内部仿射节点，先复用`GuardBounds`已有的电路投影。仅当每个投影系数都是已认证点值、
且没有未消去的状态或算子列时，才能重建原driven输入上的精确表达式，并进入同一物理曲线及根时刻证明。
例如`z=2u`的`cross(z-1)`与直接`cross(2u-1)`保留同一根和根处采样；反向接地、浮动参考及
可精确消元的仿射反馈也按原方程处理。区间系数不能取中点冒充唯一曲线，生成或裁剪的源仍不能获得原始输入身份。
该有限恢复见[独立回归](../../tests/test_source_shape.py)和[B1实际参考及原请求复验](../../../experiments/backends/support/source-shape/b1.json)。

曲线限 2 至 512 点、严格递增、始于零并覆盖 stop；整数解析长度不超过 1250 字符，
有理运算分子/分母不超过 4096 位，复用现有运算与表达式预算。格式、顺序、覆盖或投影带不足时拒绝。
SCS pulse 仅在该预算内附带原始角点，较大 pulse 保留幅度界和原消费者边界。
本轮允许已支持的 cross、保持状态 timer 与 transition 组合；不开放非零源误差的
idt、ddt、laplace、slew、absdelay。普通幅度带的拒绝边界保持，#131 同刻规则不变。

代码入口为 `scs_sources.voltage_points`、`runtime.transient`、`Curve.shaped/range/crossings`、
`Trajectory` 与 `schedule_with_history`。独立 Fraction 回归见
[test_source_shape.py](../../tests/test_source_shape.py)，涵盖位移角点、舍入放大拒绝、反向接地、
零宽脉冲、实例隔离、反馈、timer 复位及查询网格；内核测试检查全分区范围、到零与资源边界。
实际参考及原请求结果见[物理源曲线证据](../../../experiments/backends/support/source-shape/README.md)。

相异源切点与timer的发现窗口重叠时，限定根窗证书按精确根次序消费完整源模式，
事件体仍按现行`te=tau`合同读取物理根，原窗口保留给历史和事件记录。
旧保持阶段前缀、新目标安装和未来边沿须一起认证；有理内部见证、根处采样、
查询／回滚与残余拒绝边界见[源目标历史合同](operators.md#外部源选择目标与实时电压读出)。
这不是仅凭根序对一般近根组合的准入，也没有更改既有Spectre兼容差异。

<a id="paid-shaped-range"></a>

### 同一请求中的物理曲线区间读取

`Trajectory::history_range([a,b], work)` 对已认证的物理 PWL 保留完整曲线，
按原输入顺序先读取所有左端点，再读取所有右端点，最后组合区间与导数。
值域是两个端点和所有严格内部角点值的 hull。导数包围所有与窗口相交的线段斜率；
窗口为精确角点单点时，保留左右两段，不能只取执行代表时刻的一侧。
有理角点与 binary64 窗口边界通过付费的精确比较确定次序。

词法局部 `StagedRange` 借用 immutable `Curve` 和原请求 `Work`，
三个阶段共用原 `Paid.local` 运算计数。左、右端点各求值一次；付费二分定位可能相交的
线段后，仍按原升序逐一检查相交条件、内部角点和斜率。
原六步插值、向外包围和 hull 顺序保持。该读取不裁剪输入，也不修改完整源、AST、隐藏臂、
角色及父表达式资格审查。其他 `forcing_range` 消费者继续使用其原算法与费用。

reader 仅在原左端点循环实际遇到 shaped 输入时建立。构造、slot、容量增长、结构移动、
搜索和有理运算在执行前向同一 owner 付费。只有 None 或普通 Voltage 误差的旧路线不建 reader，
保持原费用。reader 不进入 Frame 或跨请求缓存；失败不提交候选状态、日历、记录或输出，
已花预算不返还。Work 错误直接传播，不退回名义值。原 128 个 plan、8192 个 cut、
10⁹ 总 Work 和局部有理数限制不变。

实现位于 `pwl.rs` 与 `exact_source/history_paid.rs`。
[有理数生成器](../../tests/helpers/generate_shaped_range_oracle.py)独立生成多角点、
非 binary 时间、精确角点、邻 ULP、subnormal 及斜率溢出控制；
`shaped_range_tests.rs` 另比较旧完整区间的结果位并检验自然预算耗尽。
`transient_history_consumer_tests.rs` 验证实际根窗、非点采样、完整 Frame 两次拒绝重试，
原生 `history_consumer` 与公开 [物理点读取控制](../../tests/test_physical_point_bundle.py)
检查生产消费者。减少重复工作不保证任意原件在固定总预算内完成。

<a id="causal-transition-composition"></a>

### 物理采样算术与 transition 组合

IR24 候选允许事件赋值由本实例的保持状态和实际 driven 电压组成有限非线性标量算术。
例如 `a=0.3*u*u; b=a; if(b-a<0)...` 按语句顺序求值，后续语句读此前赋值。
每次赋值保留原表达式的区间包围；可用的有理数证明只能在原包围内收紧结果，未知证明立即清除。
真实输入幅度不确定性不会变成精确值；下游放大仍须满足电压预算。
电气未知量参与的非线性同刻反馈不在此范围，观察实例专用的数学函数、数组和循环也不能借此准入。
结构扫描覆盖完整原事件体，包括条件和未走分支。


有限实数除法也使用这条事件标量路径。例如先写`span=V(vdd,vss)`，按源码条件设置正下限，
再计算`x=clip01((V(in)-V(vss))/span)`，后续递推必须读取本次更新后的span和x。
计数率`(1.0*hits)/n`在先执行`n=n+1`之后使用新计数；这不是整数截断除法。
对于分母包围`D=[L,H]`，只有`0`不属于D才能使用区间商；名义分母为正不能替代这一认证。
裁剪按可证明的比较选择分支，仅求值选中臂，但两臂仍接受原结构审计。

同刻贡献选择的名义预演也必须读取真实driven电压，不能先把全部节点设零后执行采样除法。
电气未知量在预演中仍是占位值，依赖电压赋值状态的贡献谓词先由原规则拒绝，最终状态与电压由联合解和原区间证书验收。
这一预演不提交状态或历史。`q=(q+x)/2`的有限递推、计数均值、裁剪两侧和正下限有独立有理数测试；
分母区间跨零、误差经保持后放大、未知电压反馈及observer-only数学各有拒绝控制。
八例原请求及实际参考的有限结果见[除法采样收据](../../../experiments/backends/support/source-shape/gap06.json)。
严格根处复位导致的原checker失败及完整波形差异保留在[统一清单](../COMPARISON.md#gap06-sampling)。

事件条件可读取无环电压网络中的已认证 transition 样本。网络先展开到实际输入、保持状态和
冻结的算子样本，再检查依赖；同刻写入经电压网络返回条件的环仍拒绝。冻结样本不改变历史。
连续 transition 也可作为另一 transition 目标谓词的输入，但叶子仍为保持值。
`transition_history_target.rs` 对全部源角点、父历史边界和谓词根分区，按无环依赖顺序建立候选计划；
源或保持状态修改后重建。缓存绑定原程序、轨迹、父历史修订和状态包围，查询不能移动目标切换时刻。
候选共享请求级工作预算，失败不退还已消费的预算；积分或滤波器直接消费这类选择目标仍不支持。

中断边沿只有在原物理分区内证明为同一直线 `v(t)=A+B*t` 时，才保留精确起点和直线证明。
`Curve.affine_on` 检查区间内的全部角点，不能用端点连线替代折线。由直线与目标交点得到的
精确结束时间仅补充原期限包围，不移动名义波形或重置误差。无法证明的中断结束次序仍拒绝。
两个独立的连续边沿结束点可在同一代表步消费，因为它们不产生目标或状态的离散修改；
待激活目标和零延迟开始不使用这条规则。每个原物理波形及查询误差检查仍分别保留。

日历中相连的重叠根簇若至少含一个 transition guard，只有每个根都有独立精确证书、
且每组的共同 binary64 代表时刻严格早于下一真实根时才可排序执行。
真实根之间没有可用代表时刻时仍拒绝；同根分组、原容差与固定前驱保护保持。
这不开放一个浮点时间间隔内的一般微事件执行，也不改变 #131 的同刻读取规则。

实现由前端 `lowering.py`、`instance_compiler.py`、`event_specialization.py`，以及
`settlement.rs`、`causal_event.rs`、`causal_voltage.rs`、`event_value_proof.rs`、
`transition_history_target.rs`、`transition.rs` 与 `schedule.rs` 共同承担。
独立回归见 [采样算术](../../tests/test_causal_event_math.py)、
[数值关联](../../tests/test_event_value_precision.py)、
[连续条件与排序](../../tests/test_transition_event_conditions.py)和
[精确期限](../../tests/test_exact_transition_deadlines.py)。真实控制器的晚期失败、回滚和同实例重试
由 `transient_lifecycle_tests.rs` 与 history-target 工作预算测试覆盖。
实际参考与未通过原 checker 的兼容差异保留在[源曲线证据](../../../experiments/backends/support/source-shape/README.md)。

对于没有外部源误差的请求，通过上述限制，固定状态下的方程系数不变，输入每个分段内的节点电压和 guard 都是时间的仿射函数。
guard 的状态独立性允许提前生成事件日程。内核同时进行普通求解和保守误差界计算：

1. JSON 保留 Python 提交的 binary64 值；以编译后 IR 系数及 PWL 点的这些精确数值定义仿射问题。
2. 区间四则运算向外舍入，覆盖原 IR 的贡献累加、消元、输入插值和 guard 求值。
   电压、驱动和状态的传递系数从原关系准备；固定日程的状态系数必须能证明为零。
   主元区间包含零，或冗余约束不能证明为恒等式时，明确拒绝。
3. 从断点 guard 区间包围真实仿射根，得到 `[t_lo,t_hi]`；候选时间取可表示的 `t_hi`。
   在端点 guard 均为精确单点时，用四个 binary64 乘积和的精确符号，
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
符号传递系数；键还包含选中语句与分支决定。缓存不保存已接受/候选状态，
批次或路径变化时替换，不随事件次数增长。
历史计时见[固定章节](https://github.com/BucketSran/vaEVAS/blob/1527502c9affb77fec12aac03adba5446f0f241e/evas/docs/EVENTS.md#timer-与同刻兼容性)，不据此声明大型网络性能或仿真器排名。
用于定位的初始化状态冻结试算也必须可解；不能完成时直接报告错误。

精确零点归到达段所有：若相邻 guard 值为 `a,0`，且 `a` 非零，
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

支持 `@(timer(start[, period[, time_tol[, enable]]]))`。一个实参表示单次事件，
两个实参表示起点和周期；period=0 或负值也表示单次。period、time_tol 可留空，
例如 `timer(start,,time_tol)`、`timer(start,period,)` 或 `timer(start,,,enable)`。
这些缺省和空参数形式来自
[LRM 2.4 §5.10.3.3](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的 `analog_expression_or_null` / `constant_expression_or_null`；start 和显式 enable 不能留空。
前端把省略的 period 归一化为 0，enable 归一化为 1，time_tol 归一化为 `1e-12 s`，
再生成当前 IR22，不引入另一套计时器。1 ps 是 EVAS 的实现选择，规范没有规定这个数值，
也不代表 Spectre 的缺省值。显式容差须有限且非负；零容差仅接受下述固定精确时钟。
固定日程的 start 必须为非负有限实例常数，period 为有限实例常数。
enable 为有限实例常数，0 禁用，非零启用；禁用不跳过模型的语法、IR 和依赖检查。
保持状态控制的参数见[动态 timer](#held-timer)，混合事件见[事件 OR](#event-or)。

周期事件定义为编译后 binary64 数值对应的实数 `t_k=start+k*period`。
内核由固定起点和精确整数 k 生成每个时刻，并用向外舍入界包围乘加误差；
实际候选取该区间的上界 `s_k`，须证明 `0<=s_k-t_k<=time_tol`。
这满足缺省容差时“在名义时刻或稍后”的要求；显式正容差也沿用相同选择。
此前固定日程使用最近舍入的 fused multiply-add，可能略早；现在某些非精确时刻会向后移动几个 ULP。
选择上界仍必须通过用户预算，过严容差可能被保守拒绝。
区间上界溢出不表示名义事件已越过 stop；只有参数下界的乘加本身溢出才能作该判断，
其余不能包围的时间仍返回 `event_resolution`，不能静默丢弃事件。
不会从上次实际事件时间累加周期，也不按容差合并相邻名义事件。

显式 `time_tol=0` 要求 stop 域内每个启用的名义时刻都能表示成精确 binary64 单点。
例如 `timer(0,0.125,0)` 可包含 0 和 stop=1 的事件；`timer(0.1,0.1,0)` 在 stop=0.3
只包含前两个事件，因为提交浮点参数的精确第三个名义时刻略大于 stop。
若 stop 延至该第三个时刻之后，其非单点证书不能满足零容差，返回 `event_resolution`。
零容差不把时钟舍入成最近浮点数，也不允许较早的非点事件占用这个精确时刻。
保持状态 timer 仍要求正容差；负容差拒绝。
独立正负控制见[零容差 timer](../../tests/test_zero_timer.py)。这是 EVAS 的数值合同，不宣称复现 Spectre 的内部时钟算法。

同刻 timer 与 cross 共享事件前状态，并联立求解事件后的电压；整数赋值顺序和批次写者冲突规则与 cross 一致。

非空 strobe 请求对起点、周期均为精确单值的 timer 使用更窄的包围，包含精确保持参数。`exact_time.rs::Clock::bounds`
用 FMA 提出最近舍入值，再以精确有理数符号比较决定它在 `t_k` 的哪一侧。
可表示的 `t_k` 得到单点；否则得到相邻两个浮点数，并再次验证上下界。
`schedule.rs::add_timer` 取其上界后，继续执行原有顺序、`time_tol`、stop 和提交检查。
这样消除了普通区间乘加的额外膨胀，不会把实际早于事件的 strobe 当作事件后状态。
普通查询通常保留原包围；若有限包围跨过 stop，则先精确比较 `t_k` 与 stop。
确认事件在 stop 之后便结束日程；确认在 stop 内才复用 `Clock::bounds` 收紧包围。
这样可消除区间乘加的额外膨胀，不会把 stop 之后的事件提前纳入。
原时间容差、相邻事件顺序和提交检查继续生效；不确定保持参数与非有限包围的拒绝不变。
独立 Fraction 回归检查 stop 前后相邻浮点数、不可表示的名义时刻及未请求终点输出；
[原采样链实际对照](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#timer-stop)
另验证停止时刻的状态提交及边沿、滤波历史。
近邻事件闭包到达真实强制点时，只有下一事件被证明物理上更晚，才提交已检查的前缀。
提交包含该前缀的状态、历史、事件记录和未来日程；不提前消耗后续事件，也不把因果查询改名为强制点。
[实际对照](../../../experiments/backends/strobe/README.md#near-timer)和同控制器失败/重试回归覆盖此边界。
多个真实事件仍可能需要不同的执行点，
不能因为其最窄包围相同就合并；无法真正停在强制点时仍明确拒绝。
独立有理数属性测试验证包含性与相邻性，[强制点回归](../../tests/test_strobe.py)
验证前后状态、历史续算、加密观察和拒绝保护。

[30 条件 Spectre 回调诊断](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#回调规则的后续实测)
在固定 timer 的显式正容差范围内观察到：实际接受点进入名义时间的容差窗口就可以触发，
包括提前的 strobe 点和数值步进点。EVAS 保持上述精确名义相位规则，不以复制该网格为默认兼容目标。
给定 Spectre 网格的计数回放不等于独立生成相同网格，原严格边界失败继续保留。
[独立误差分解](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#数学精度与回调时移的分开验收)
分别检查名义事件下的数学答案、观察到的事件时移及剩余后端残差。
复制接受网格本身不能证明数学精度。2026-10-10 用户接受本批 18 条阶段差异为
[SEF-TIMER-18](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18)，不再要求修复；
原严格结果继续保留，其他模型/设置仍按[验收分类](../../../docs/contributing/validation.md#classify-differences-before-selecting-a-repair)逐项判断。
当前契约仍保持精确名义相位，未把计数变化行当成新的调度策略。

t=0 时先解析并安装 initial_step 初值，再求初始电压，再原子执行 timer(0)，最后输出初始观测。
名义事件恰为 stop 时照常提交，即使未请求 stop 输出也保留事件记录；名义时刻超出
stop 的事件不调度。这是 EVAS 的确定性边界策略，其他后端仍应按完整允许窗口验收。
计时误差、与 stop 的关系、相邻事件次序不能证明，或周期不能推进可表示时间时，
返回 `event_resolution`，不自动增大容差。相同日程或精确同刻可共同提交。

当前分支对完整重叠簇内全部为纯固定 timer 的情况，另外比较精确名义时间。
将输入 binary64 `start`、`period` 解释为精确二进制有理数，以整数索引 k 定义
`t_k=start+k*period`。比较两事件时计算
`sign(start_a+k_a*period_a-start_b-k_b*period_b)`，完整保留乘积与和的二进制信息，
不比较已舍入的代表时间，也不把区间重叠当作同刻。
索引受事件预算约束，小于 `2^53`，转换为 binary64 整数不会损失精度。
按此顺序分组，精确相等的名义时间使用同一个代表值，该值至少为组内所有名义区间的上界。
严格先后的下一组代表值至少为前组代表值的 `next_up`，从而不会因上界相同而合并两个真实事件。
每个延后的代表值仍须在原 `time_tol` 内，不能超过 stop，也必须严格早于簇外下一事件的下界。
任何检查失败仍返回 `event_resolution`。不能借排序扩大用户容差、移动 stop 或穿过外部事件。
名义区间保持原值，事件采样及后续误差传播继续使用它；选定代表值不证明名义时间变成精确单点。
这项排序只覆盖完整重叠簇全部为固定 timer 的情况；timer/cross 或
固定/保持状态 timer 混合簇继续使用原来的同刻证书和区间拒绝规则。
保持状态或历史日历重建保留未变化的固定 timer 及其前驱证明。若其名义窗口仍在
`after` 之后，沿用一般边界检查；若窗口与 `after` 重叠，仅允许原 pending 前缀中
完整的固定 timer 证明链。首个代表时刻组必须以前次提交时间为前驱，后续每组必须
链接前一组，且同组所有 token 都满足该关系。新生成事件、改变的 held timer 或插入的
cross 不能借用这项例外；它也不改变原 `time_tol`、stop 和混合簇限制。

线性与多项式非线性历史另保存最近事件闭包之后、传播至代表时刻之前的物理状态
`X_i+`，以及包含真实事件时刻的观察窗口 `W_i=[l_i,b_i]`。
它与代表时刻的初始状态分别保存。对已证明先后的下一事件，若其窗口跨回
`b_i` 之前，从 `X_i+` 出发，以 `D=[0,up(b_j-l_i)]` 包围当前模式的全部实际持续时间。
非线性路径使用有限 Picard 管，线性路径在 PWL 折点分片使用原区间指数传播，
每片只传递物理状态并重新包围源和坡度。普通输出和根搜索不能因此查询已丢弃的历史。
缺少物理种子、窗口早于保留范围、不能认证有限管或超出电压预算仍拒绝。
数学证明与代码入口见[事件修改的联合积分与复位](continuous.md#事件修改的联合积分与复位)。

每个非单点固定 timer 批次还以事件后的保持状态和完整历史包围检查 history guard。
`keeps_guard_value`只证明事件瞬间的值连续，不证明事件后微分方程不变。
例如`idt(q)`在q改变时积分值不跳变，但新斜率可能在真实事件到代表时刻之间产生cross；
因此该检查必须先于仅按值连续性跳过的分支。
只有能排除从真实事件到代表时刻之间的零点，才从代表时刻继续定位未来根。
无法排除时返回 `event_resolution`，避免漏掉藏在这段窗口内的 cross；末尾 timer
也执行此检查。跳变 guard 的原闭包限制仍保留。候选状态、未来日程及电压误差全部
通过后才一起提交，失败后可在同一控制器重试。
[固定 timer 排序](../../tests/test_timer_ordering.py)与
[历史组合回归](../../tests/test_timer_history_order.py)检查计数、Fraction 积分面积、
后续根、采样后续算、三个近邻时钟、隐藏根拒绝以及查询网格不变性。
实现入口是 [LinearContinuous::ordered_event_state](../../rust_core/src/continuous_history.rs)、
[GuardTrajectory::event_value](../../rust_core/src/guard_trajectory.rs)及
[Controller::accept_history_events](../../rust_core/src/transient_history_calendar.rs)。
此候选扩展支持可认证的多项式非线性近邻历史与 PWL 折点，不支持混合时钟排序或窗口内的完整事件闭包。
新扩展只有本地独立回归，实际 Spectre 对照资格待验。
有限误差界及精确顺序不意味着所有可解情况都接受。
PWL 根另有精确零点证书：当端点 guard 和到候选时刻的两侧时间差都已认证为
精确 binary64 数，使用完整二进制乘积比较证明线性插值为零，再将根区间收窄为点。
因此 `19U*(8/19)=8U` 不再因中间除法舍入而拒绝；一个 ULP 的真实邻近事件仍分别调度。
端点带不确定性、不可表示根或不能取得该证书时，保留原区间与拒绝边界，不放宽容差。
当前在运行前生成有界的不可变事件日程，并按需推进已接受事件游标；不是惰性队列。
日程空间随事件数线性增长，最多 1,000,000 条事件，超限返回 `event_budget`；时间推进仍保留独立的 1,000,000 步上限。

缺省参数、精确有理数时钟和不能满足默认预算的拒绝由
[固定 timer 回归](../../tests/test_timer.py)检查；[动态回归](../../tests/test_dynamic_timer.py)
检查同一默认策略下的自调度与查询不变性。同源 Spectre 对照见
[缺省参数实验](../../../experiments/backends/dvs2-spectre-validation/README.md#timer-defaults)。
连续电压参数、动态容差和状态反馈 guard 的通用同刻迭代仍需单独扩展。
现有波形算子及积分的限定能力见[算子手册](operators.md)。

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
若零时刻事件把 transition 的最终系数设为 1，随后要求 q=y+1、y=q，则事件方程无解，
EVAS 明确拒绝。实际 Spectre 在该原模型中不收敛并恢复越过断点；退出成功和恒零波形
不作为正确事件答案。收缩反馈及正时间边沿的有限正控与联合解一致，
[七例实际诊断与旧期望](../../../experiments/backends/support/r01-root-windows/README.md#最终初态与反馈系数七例实际诊断) 分开保留。

积分/滤波的复位观察闭包及未来历史认证另见[共同生命周期](continuous.md#shared-lifecycle-closure)。
若两个同刻触发的事件块都写同一状态，EVAS 在求解前拒绝该候选批次并保持旧帧不变。
这与同一块内重复写不同：同块重复写有明确的语句顺序；跨块重复写没有本实现愿意采用的隐式优先级。

具体有三条独立路径保持局部顺序：`EventModel::event_circuit` 构造代入方程，
`EventModel::apply` 重放原赋值，`Bounds::new` 从原 IR 构造区间认证。每次试算均固定从
s− 开始，因此求解、重放或缓存重试不会再累计一次事件。验收后才原子提交；失败时旧帧不变。


<a id="ordinary-event-scratch"></a>

### 回调临时值与普通赋值别名

原源码中的标量 `real` 若已有 cross/timer 写者，也可在回调声明之后由普通 analog 语句重新赋值。
例如回调 `e=V(u)+1; q=e;` 后接 `e=2*V(u); V(y)<+e;`，
回调中的 q 读取该回调刚写入的 e，普通输出读取本次普通求值中的 `2*V(u)`。
编译器保留 e 的事件状态槽，同时用独立的普通局部环境按源码顺序降低贡献；两种读取不能互换。

每个回调、初始化体及普通求值中的 e 读取，都须由该体内先前的无条件写入覆盖；
条件写入须在两臂都完成，跨回调旧读、缺臂写入及普通写前读仍拒绝。
这条窄路径要求原模型不含数组，普通写者均位于全部回调声明之后；
仅有初始化写者的持久状态、触发器或只读算子设置中的读取、循环携带的别名均未扩展。
原始零次循环和未走分支仍参与结构检查，新增递归扫描及容器复制由同一个原100000累计预算先计费。
独立公开回归见 [15项角色与顺序控制](../../tests/test_event_ordinary_scratch.py)，
本次没有新增实际 Spectre 配对或371原件通过结论。

<a id="ordinary-event-prefix"></a>

### 回调位置的普通纯输入前缀（分支已验收，未合并）

没有初始化、事件或循环写者的标量 `real`，可以在回调体中读取其源码前缀。
例如 `a=V(u); @(timer(0.25))q=a; a=2*V(u); V(y)<+a;`，
q 在事件根读取该位置的输入，普通输出仍读取后续的两倍输入。
a 不变成保持状态，也不从上次 analog 求值取值；不同回调位置保留各自的前缀。

前缀只依赖实例参数和实际物理 input/inout；传递定义按原源码顺序解析，
条件合并要求两臂都有合法定义和纯输入谓词。写前读、后置定义、时间、
内部或其他实例输出、算子、数组和循环携带仍拒绝，零系数和未选臂也参与检查。
这张绑定只供回调体使用，不进入 trigger、direction、tolerance 或只读设置。
运行时仍使用当前根的完整输入盒，不能用代表点消除真实采样不确定性。

`initialization_aliases.py` 复用旧需求遍历，只为旧路径不能绑定的新需求留下即时提示；
`ordinary_event_prefix.py` 再对完整原树作付费资格检查，
`instance_compiler.py::aliases_at` 按回调 token 取该位置的表达式。
没有新需求时沿用旧路径，避免为旧 typed-target 程序增加扫描和复制费用。
公开控制见 [test_ordinary_event_prefix.py](../../tests/test_ordinary_event_prefix.py)，
包括独立数值答案、查询加密、隐藏依赖以及原100000预算边界的完整 wire 对照。

<a id="initial-only-ordinary-alias"></a>

### 仅初始化状态的普通全路径别名

原标量 `real` 只有 `initial_step` 写者、没有运行事件读写或触发设置依赖时，
普通 analog 求值可在每次读取之前通过本次全路径赋值建立独立别名。
例如 `@(initial_step) q=7; q=2*V(u); V(y)<+q;` 保留 q 的状态槽和初值7，
普通输出读取当前物理输入的两倍。初始化中的所有语句仍完整降低和检查，
初始化输出保留各自调用位置的快照；后续普通覆盖不能消除非法初值或未选臂的义务。

新增目标写入必须位于全部初始化和运行回调声明之后。
传递普通定义若只依赖参数和实际物理输入，可位于回调之前；这不授予目标状态的前序读取。
前序 StateRef 或夹在普通写入之间的 initial_step 不通过这条新入口取得资格，
以免把声明位置的旧状态替换成最终 Frame 状态。这个顺序门是当前支持域，不是语言合法性判断。
普通别名按原源码顺序更新，条件两臂合并；缺臂只能保留本次求值已经定义的值。
别名 RHS 可使用参数、实际外部 input/inout 电压及原机制合法的本实例持久状态，
包括既有 integer 状态的合法选择。读取仍由原 lowerer 和实际 Frame 的 bounds 处理，
本入口不扩展整数范围、事件写者或 history 资格。时间、算子、output/internal/foreign
电压及未定义局部依赖仍拒绝，零系数和未选臂同样参与审计。
新增目标不接受 integer、数组或普通循环携带，不向 waveform 设置或运行回调提供旧值。
其他实例声明的 output/inout 连接会保守排除该输入节点，即使其贡献最终为零。
这条证明仅接受未索引的标量电气 probe；`V(u[0])` 等 indexed probe 本轮保守拒绝，
不以原向量名查询标量 node id。原有非 A 的向量输入入口不变。
设置依赖沿普通赋值、表达式全部操作数、条件谓词与两臂传播，零系数和未选臂不能消除它。
例如 `e=q; $bound_step(e)` 和 `if(q>0)$bound_step(0.125)` 均拒绝；
直接或传递依赖新增目标的条件也不能激活 bound-step 设置。

`initial_ordinary_alias.py::admit` 在原源码上检查角色与全路径写前读，
`instance_compiler.py` 保留 State 初始化并复用普通顺序 alias 环境，IR32不变。
所有新增遍历、复制与别名事实使用同一个 NativeAudit；激活时保留此前已累计工作，
原100000总限额与失败后不退款合同不变。
公开独立回归见 [test_initial_ordinary_alias.py](../../tests/test_initial_ordinary_alias.py)，
覆盖初值/本次值分离、同回调先后赋值后的状态选择、查询网格不变性、源误差band、
原初始化输出及非法隐藏依赖、自然预算耗尽和两次同owner重试。
设置传递依赖、条件激活及向量 foreign 拒绝的公开编译控制见
[test_initial_ordinary_alias_admission.py](../../tests/test_initial_ordinary_alias_admission.py)。
组合回归还要求 A 与无关 Transition 实例交换编译顺序时，保留逐位置贡献、
原 q 初值槽及真实半沿。独立答案为 `a=t`、`b=1-t` 下的 `y=t(1-t)`、`z=y+1`，
不以另一个排列的输出充当数值 oracle。主线在完整实例编译后统一发射已经降低的贡献，
A 入口不改变该队列、单次发射、失败后禁止重放或原预算合同。
这是局部开发合同，没有新增原件通过或 Spectre 对照成绩。

<a id="ordinary-integer-event-prefix"></a>

### 事件读取的普通 integer Floor 前缀（分支已验收，未合并）

单个普通标量 integer 可由物理输入的 `floor` 赋值及后续常量夹位组成前缀，
并只在其后声明的运行回调体内被读取。编译器把完整原赋值和夹位放在每个读取回调之前，
复用已有 integer 状态、原树 Floor 证明和顺序事件语句。
例如先写 `ratio=floor(V(u)+0.5); if(ratio<1)ratio=1;`，
再在 timer 中执行 `q=q+ratio;`，每次读取的是当前事件根处重新计算的 ratio。

顺序为输入原树求值、Floor、signed32 赋值检查、常量夹位，再执行原回调体。
溢出不能被后置夹位掩盖；原输入盒跨 Floor bin 时仍拒绝，除非原机制给出有效来源证书。
当前切片不接受多个 Floor 前缀、数组、初始读取或写者、事件写者、普通贡献或别名读取，
也不进入 display、触发器或设置。它不扩展一般连续 Floor 或 observer 权限，IR32不变。

公开状态轨迹会包含 ratio 及其工程初值0；原模型的每次读取都由同回调前置赋值支配，
不能读取这个初值。accepted/candidate Frame 仍共同拥有该槽及其 bounds，失败时完整回退。
`ordinary_integer_event_prefix.py` 检查原模型和执行模型的完整角色，
`instance_compiler.py` 将前缀交给原范围分析、原事件审计和执行路径；
全部新扫描、保留和复制都先计入原 NativeAudit。没有候选时恢复原直接事件体路径。

公开正反例见 [test_ordinary_integer_event_prefix.py](../../tests/test_ordinary_integer_event_prefix.py)。
[真实 Controller 控制](../../rust_core/src/transient_ordinary_integer_prefix_tests.rs)
使用当前公开编译器生成的 IR，核对非空 warm 前缀、同一 Controller 两次晚期失败后的合法重试，
以及原共享 Work 自然耗尽后的两次粘性拒绝；完整 Frame 包含无关状态、历史、电路、队列和输出。
该控制覆盖静态日历，不外推到 Held/History 日历。
局部证据见[普通前缀收据](../../../experiments/backends/support/low-cost-closure/ordinary-prefix.json)，
局部身份不叠加计分；最终同源双轨、完整CI及安装见[共同收据](../../../experiments/backends/support/low-cost-closure/ordinary-common-three.json)。没有新增Spectre或共同资格。

<a id="ordinary-current-integer-alias"></a>

### 保留事件状态的普通 integer 当前值别名（分支已验收，未合并）

同一标量 integer 可以保留原 State 和 cross 写者，同时在普通 analog 求值中使用独立的当前值别名。
这条路径要求原源码恰有一个无条件顶层普通赋值，且每个普通读取都位于该赋值之后。
例如 `selector=(V(vsel)>vth)?1:0;` 后声明上升和下降 cross 写入 `selector=1/0`，
再由普通 `if(selector==1)` 选择两路输入时，连续输出读取本轮输入计算的 selector，
原 cross 仍更新其原有 State；两种值的命名空间保持分离。

普通赋值的右侧只接受参数及直接当前 input/inout 物理源，拒绝其他局部量、旧状态、time、history，
以及由其他实例输出驱动的输入。原数组、循环、声明初始化、第二写者和条件写者不进入此切片。
写前读，以及初始化体、事件体、触发器或设置中的同名读取仍拒绝，包含零系数或未选分支中的读取。

原两臂和全部子表达式先接受完整结构审计，再由既有 lowerer、决策操作数检查、`checked_ir`
及 signed32 检查确认整数赋值。普通执行保留原整数验证，不删除原树、移动原赋值或新增状态槽。
`ordinary_integer_current_alias.py` 的新资格工作由原 NativeAudit 的100000累计预算支付；
既有写者遍历没有发现候选时，不启动新扫描或计费。此 integer 切片没有新增 IR 或 Rust 消费者权限。

公开控制见 [test_ordinary_integer_current_alias.py](../../tests/test_ordinary_integer_current_alias.py)：
核对原 cross 方向、`V(vsel)-V(0)-vth` guard、原赋值体，以及两次真实触发的 before/after 和 State 轨迹，
并检查查询点不变性及原树负控。原114的258点 checker 定向通过；4个公开方法、11个既有 integer 前缀方法
及旧 k225/k226 费用边界分别保留证据，不合并为新覆盖数。
最终release原114及同源双轨、完整CI与安装已独审，见[共同收据](../../../experiments/backends/support/low-cost-closure/ordinary-common-three.json)。没有新增Spectre配对或共同资格。

<a id="ordinary-point-lineage"></a>

### 采样输入谓词与普通单点的保持值来源证明（分支已验收，未合并）

采样状态和当前输入共同决定贡献分支时，先从原表达式树审计实际 driven 输入及保持状态的来源。
同 owner 的全部回调、numeric actions、未选分支和零项均参加审计；
`$abstime`、内部电压、贡献目标及经另一回调采入的非法依赖仍拒绝。
原完整区间能够决定分支时，继续使用原区间认证。

只有完整旧回退实际返回 `condition_precision`，才尝试保持值的精确来源证明。
它限于没有事件批次、已触发根或物理 exact_root 的普通单点观察，且时间位于已接受 Frame 与原 stop 之间。
旧路径成功及其它错误原样返回，包括旧路径在共享预算已耗尽时仍能完成的情况。

设保持状态的原完整盒为 \(B_i\)，有效有理来源为 \(p_i\in B_i\)。
新证明在原 binary64 叶子上精确递推 \(L(p,u(t))-R(p,u(t))\) 的符号，
同时绑定实际 accepted Frame 的 proof map、原 Program、driven 身份及已验证源配置。
另一 Frame 即使拥有相同盒，也不能替代当前证明；缺失证明、单点盒或代表点不能制造精确值。
非输入或未知节点采用未知 mask。原状态盒、源盒及后续历史传播保持完整，成功 query 后逐项核对未缩窄。

已有 `exact_knots` 可以证明一条确定物理曲线，其 binary64 PWL 投影仍可带非零包围带。
本路径复用付费的 `forcing_shaped_inputs(work)` 资格门及当前 source box 包含检查；
真实未知 band、缺失精确曲线或新增生成源继续拒绝。
只有 `unsupported_forcing_scope` 转为无新证明；`step_budget` 与其它错误传播。
这项来源证明不扩大一般 source-uncertainty 或非点事件窗口的支持。

所有新增扫描、比较、分配及有理数运算预付到原 request Work。
真实控制覆盖非空 Frame、两次晚拒绝后的合法重试、完整电路／历史／队列／输出回退，
原十亿预算自然耗尽98次 query 后的两次粘性拒绝，以及已耗尽预算上旧回退的零新增费用。
公开 Fraction 控制区分精确来源与代表点的相反符号，并核对加密查询不改物理历史。

原037定向 checker 的45个边沿及5项属性通过；开发核、6项内部方法、独立公开控制及所有失败各保留身份。
最终release原037及同源双轨已独审，原始317、修订320、剩80，见[共同收据](../../../experiments/backends/support/low-cost-closure/ordinary-common-three.json)。没有新增Spectre资格。
源码、配置和限制见[单点来源证据](../../../experiments/backends/support/low-cost-closure/ordinary-point-lineage.json)。

<a id="multiple-event-writers"></a>

<a id="多事件块写同一状态pr25-已交付"></a>

### 多事件块写同一状态

写者检查按实际候选批次执行。
构建期允许不同事件块潜在写同一 state。读取其他块也可能写的状态时，
允许 `q=a*q+b` 的受限自身仿射更新：完整结构状态依赖集恰为赋值目标 `q`，
系数 `a` 非零且有限，常数 `b` 有限，且没有电压或算子依赖。integer 仍需每句通过整型和范围检查。
例如两个异刻事件执行 `q=10*q+1`，初值 0 在第一事件后为 1，第二事件后为 11。
数组的每个元素是独立状态；同块后续赋值读取前句结果，不同批次读取各自事件前的已接受历史。
依赖另一个状态、`q-q`、`0*q` 或系数舍入下溢为零的表达式不会获得此例外。
每次 `settlement::prepare` 先选择条件路径，再调用 `check_selection_writers(selection)`；
只有实际选中的赋值参与冲突判断。不同批次触发的上升/下降迟滞块可以共同维护同一 `q`。
同一批次中两个不同事件块写同一 state 时返回 `event_conflict`，即使写入值相同，也不按源码顺序仲裁。
失败候选不提交 state、state bounds、算子历史、事件游标或记录。

独立冲突与互斥批次回归见 [test_event_writers.py](../../tests/test_event_writers.py)，
共享仿射更新及原常量初值迟滞计数见 [test_shared_counter.py](../../tests/test_shared_counter.py)，
数组的两次非幂等更新、负系数、分数系数和同刻写者保护见
[test_variable_arrays.py](../../tests/test_variable_arrays.py)；
真实帧回退由 Rust 私有测试检查。固定 V3 的 EVAS/Spectre 对照见
[对照收据](../../../experiments/archive/pr14-pr15-validation/results/event-writers-spectre-v3.json)，
定位差异见[诊断收据](../../../experiments/archive/pr14-pr15-validation/results/event-writers-timing.json)及
[后端容差解释](#backend-cross-tolerances)。这些是有限观测证据；raw 只在本地/thu-sui 保留，
不等于公开完整复现包或完整矩阵的新执行。

<a id="event-conditions"></a>

<a id="受限事件体条件080-实现切片090-延续"></a>

## 受限事件体条件

[共同闭包](continuous.md#shared-lifecycle-closure)将复位后观察与未来历史分开，
保留每次事件体的局部赋值顺序及整批提交。非点事件日志的可选 `observation_time_bounds`
报告共同观测区间；`time` 是存储代表时刻，点事件省略区间字段。cross 条件按下节 `te=tau+` 选择。

非点 cross 候选在数学根 tau 上认证赋值和条件，代表时刻 b 另作提交电压验收。
完整根盒保留源/历史误差；若条件差值与实际触发的仿射 guard 有精确的同零集证明，
则按下节的根后一侧判定；没有一侧证书时仍按 guard(tau)=0 判定等号。
未触发 OR 叶子、timer、区间系数或单纯舍入相等不能提供这项证明。
因此 `u=3t, cross(u-1,+1)` 内的 `u>1` 为真；代表时刻 b 的舍入不参与这项判断。

<a id="cross-right-limit"></a>

### cross 事件体的根后右极限

[LRM 2.4 §5.10.3.1](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
规定事件“shall occur after the threshold crossing”，并位于时间/表达式容差盒内。
EVAS 取该窗口的右极限 `te=tau+`：连续量在 tau 连续，仍使用原根盒包围；
只有在 tau 恰为零的条件差值才需要根后一侧，且须有证书：

- 触发叶子：源 PWL 段两端 guard 值严格异号时，`(tau, 段末]` 上 guard 符号为段末符号 s。
  条件差值 d 与 guard 有精确同零集 `d=k*g` 时，d 在 tau+ 的符号为 `sign(k)*s`。
- 其他无状态条件：全批均为 cross 且条件在根盒上被证明恰为 `[0,0]` 时，
  用接受历史在 `[lo, next_up(hi)]` 上的导数包围；严格同号才取该符号。
- 同一条件得到相互矛盾的一侧、导数跨零、平台恰在阈值、源幅度误差带、timer、
  付费历史上下文或含 timer 的混合批次均不提供证书，保留原 `[0,0]` 判定或拒绝。

例如 `u` 上升、`w` 同刻下降过 0.5 时，`cross(u-0.5) or cross(w-0.5)` 内
`u>0.5` 为真、`w>0.5` 为假；`w` 恒为 0.5 时 `w>0.5` 仍为假、`w>=0.5` 为真。
独立答案见 [test_cross_right_limit.py](../../tests/test_cross_right_limit.py)。
入口为 `event_conditions.rs::PostRootSides`、`pwl.rs::Root::post_root_side` 与
`transient.rs::post_root_scope`。这只约束事件体读取；普通贡献式的 Select 是 tau 处的连续时间表达式，
仍按原 `g(tau)=0` 判定，避免代表时刻电压验收与事件体选择不一致。
其余条件先在可行输入盒内证明选择；若有限误差盒无法决定选择，只有两臂行为完全相同时才可继续，规则见下文。其他情况拒绝，点时刻 timer 保持原观察语义。
数学与非线性连续重启见[根盒采样](continuous.md#事件修改的联合积分与复位)。
数学根观察约定不等于其他仿真器的回调时刻。

`cross`（包括受限 OR）或固定 `timer` 的事件体可含嵌套 `if/else`、顺序块、空语句及无 else 分支。
当前开发候选还接受 `&& || ! == !=` 及有限非零真值判断；else 归最近未配对 if。
解析器把复合条件降为有序的 `< <= > >=` 条件树，比较操作数可含实例常数、仿射电压和可认证的保持状态。
`a==b` 按 `a<=b` 且 `a>=b` 判断，`!=` 取反；不会引入等号容差。
`&&` 只在左侧为真时进入右侧，`||` 只在左侧为假时进入右侧。结构检查仍覆盖全部分支。
依据是 LRM 2.4 §4.2.5、§5.3、§5.7、§5.8.1。以下数值认证方法是 EVAS 的实现选择，
不是 Spectre 内部算法的陈述。后端执行身份由实验收据维护。

例如 `@(timer(.5,.5,.001)) if (V(rst)>=.5) held=0; else held=V(vin);` 在每次实际事件时间
读取 rst 并选择复位或采样。所有分支都做静态合法性检查，执行时只判断沿路径实际到达的条件。
`initial_step` 的电压初始化只读实际 driven 输入。事件谓词按源码顺序读取同块先前写入，
同时传播完整误差包围。例如 `q=q+1; if(q>=2) q=0;` 使用递增后的 q。
物理事件的谓词不能依赖待联立求解的电压赋值状态或经电压网络返回的状态；
有限 transition 样本与无环网络的候选扩展见[组合边界](#causal-transition-composition)；
独立测量实例的例外见下节。无法证明分支时拒绝。
结构依赖先检查，再作区间消元；`0*q`、`q-q`、下溢系数均不能作为独立性证明。
内部无状态网络如 `z=2*rst-1/4` 可以作为谓词来源。

点观察契约令实际代表时间为 e，精确实数 PWL 插值为 u(e)，谓词差为
`d(e)=lhs(v(e))-rhs(v(e))`。从原 binary64 IR 的仿射网络得到输入到 d 的区间传递系数，
结合原 PWL 的 `U(e)`，形成包围 `D=[L,H]`。四种关系按下表认证：

| 关系 | 可证明真 | 可证明假 |
| --- | --- | --- |
| d < 0 | H < 0 | L ≥ 0 |
| d ≤ 0 | H ≤ 0 | L > 0 |
| d > 0 | L > 0 | H ≤ 0 |
| d ≥ 0 | L ≥ 0 | H < 0 |

其他有限区间先检查两臂是否等价，不能证明等价时返回 `event_condition`；非有限值直接拒绝。不使用额外 epsilon，精确单点 `[0,0]`
按普通严格/非严格比较处理。`cross` 的定位证书不证明代表时间处 guard 必为零。
非点 cross 证明实际根处的条件；只在有精确同零集证书时使用该根约束，
其余条件使用根盒源包围。不能把普通 timer 或近似相等的表达式强行改成等号。
例如 binary64 的 0.1→0.9 在 t=0.5 的实数插值比 0.5 大 `1/72057594037927936`，
普通浮点插值却可得到 0.5。当前区间不能判定这个边界时会保守拒绝，不冒充精确实数比较器。

区间未能判定时，普通（非 floor、非付费历史）事件体再用精确有理值重算谓词差。
同块先前赋值若没有有理来源，但其认证包围恰为有限单点 `[c,c]`，该单点就是精确 binary64 值 c，
与 `LocalState::new` 对单点输入盒的处理一致；非单点盒不制造精确值。
例如先采样稳定 transition 节点 `s=V(held)=0.73`，再判断 `0.45+(V(vin)-s)<0`（`V(vin)=0.28`）：
区间差为 `[-1.1e-16,1.1e-16]`，精确差为 `2^-54>0`，因此选择假分支。
若保持的是 `0.73/3` 之类的非点盒，同样近乎相等的比较仍返回 `event_condition`。
独立控制见 [test_event_singleton_exact.py](../../tests/test_event_singleton_exact.py)。

无法确定的符号不一定改变结果。例如 `abs(h-ref)<=limit` 的内部正负选择若都能证明检查通过，并执行同样的 `good=1`，EVAS 可继续。它从同一完整误差盒分别检查两臂，要求赋值目标、顺序与原始 RHS 树逐项相同，局部状态包围逐位相同，且两臂均不含打印。空臂可以等价；公式不同但当前算出同一数值不能作为等价证明。两臂的所有读取和子条件均保留在写者检查与缓存键中，防止隐藏另一臂的跨块依赖。一次完整选择最多执行 64 次额外臂证明，超限仍拒绝。此规则不收紧误差盒，不引入 epsilon，也不把未知条件宣布为真或假。
独立控制见 [test_event_branch_agreement.py](../../tests/test_event_branch_agreement.py)。

选择路径 P 后，逐句更新构成 `q+=Phi_P(q−,v+)`，再解
`F(v+,Phi_P(q−,v+),H(e))=0`。数值代入和重放使用同一路径，并重新验证路径；
区间认证独立从原 IR 的选中语句构造映射。`U(e)` 同时传入状态、电压认证，
不能只保证选支正确，却把 RHS 的已舍入输入重新当作精确量。
含条件的整个程序在事件、初值和普通观察点都保留输入及已接受状态包围；即使没有算子也不丢掉采样误差。
电压使用 `vabstol+reltol*abs(v)`，integer 必须精确；real 状态保留有限区间，
不单独施加无单位相对预算，其电压、历史及事件消费者继续认证该区间。未通过时返回
`event_accuracy`，含历史算子时为 `waveform_accuracy`。联合连续网络另在根盒上
认证采样并保留根到代表时刻的新流误差，见[共同误差链](continuous.md#事件修改的联合积分与复位)。
此认证不推广为所有算子的历史采样认证、源到 IR 舍入保证或连续时间资格。

每个 EventModel 持有至多一份证书缓存，键为激活块及选中赋值/分支路径；只缓存系数。
每次试算从已接受帧开始重新判定，只有选中路径实际写过的状态能触发算子目标更新。
候选的状态、包围、电压、算子历史和记录全部通过检查后才随游标一起提交。
私有回退测试直接检查非零 transition 历史下的失败、成功弃步、修正未来输入重试与新缓存控制的一致性；
这仍不是完整调度器任意故障注入证明。

实现入口：[event_conditions.rs](../../rust_core/src/event_conditions.rs) 负责结构、路径和谓词认证；
[settlement_bounds.rs](../../rust_core/src/settlement_bounds.rs) 负责选中原 IR 的误差传播。
独立答案与边界控制见 [test_event_conditions.py](../../tests/test_event_conditions.py)，
实际帧回退见 [transient_condition_tests.rs](../../rust_core/src/transient_condition_tests.rs)。
完整目标契约与剩余组合边界见[验证契约](../../validation/EVENT_CONDITIONS_CONTRACT.md)。

状态反馈谓词、通用非线性谓词及普通 analog 条件与动态算子的组合仍超出本页范围。
受限 idt reset 见[算子手册](operators.md#idt)，当前总体缺口见[四后端支持范围](../COMPARISON.md#支持矩阵)。
区间传播会增加运算和存储，丢失相关性时可能保守拒绝；这条路径没有自动细化步长或高精度回退。

<a id="passive-observer"></a>

### 独立测量实例读取物理输出

没有电压贡献、历史算子或步长请求的实例，可以读取已经确定的物理输出并记录测量。
例如 DUT 在同次 cross 把 q 从 0 改为 1、输出 `V(y)=q`，测量器的
`if(V(y)>0.5) seen=V(y);` 读取更新后的 1。实例资格检查覆盖整份原 IR：
只要其他实例的电路、历史、初值或事件消费它的状态，就不能使用这条路径。
未选分支和显式零项也计入依赖；模块名字和当前数值不能决定资格。

内核先完成物理事件的联立求解和同刻历史闭合，再把实际事件时刻 tau 的节点区间交给测量器。
测量器在同块内按顺序认证条件、更新状态，Display 使用同一条认证路径。
它不能把代表时刻 b 的窄电压证书当作 tau 的采样范围。integer 仍须精确，real 采样和
自己的未来 timer 保留全部区间；分支不确定且无法证明两臂等价时仍拒绝。物理算子的索引保留原全局身份，
无法证明的 operator guard 不获得“根处等于零”的捷径。

测量状态、显示和自己的 timer 与物理候选一起提交。任何后续检查失败都会整批回滚，
普通输出查询不重复执行测量，也不重启无依赖的物理历史。同批跨块读写仍按原规则拒绝。
若一批事件全部属于独立测量实例，它不会建立新物理流。查询已发生回调之后、代表时刻 b 之前的结果时，内核保留更新后的测量状态，但从被动事件序列之前的物理历史向前计算。这样不会在已结束的 transition 上倒读旧边沿。混合或物理批次仍使用原历史闭包；窗口内其他历史根、未来日程、输出误差与失败回退也仍需通过检查。
initial_step 与固定 start=0 的 timer 保留原执行顺序，后者后续周期也不转入测量路径。
独立初始测量不会要求旧方程越过已知物理事件预测到 stop。例如 `z′=q z²`、z(0)=1、q 初值 1，在 timer(.5) 将 q 改为 −1；真实曲线在 .5 前为 1/(1−t)，之后为 1/t。初始 Display 不能迫使 q=1 的旧流算到 t=2，因为旧流在 t=1 发散，而真实请求仍有限。
仅在原 IR 证明初始实例完全隔离、且没有动态或历史 guard 时，初始化先预测到当前日历首个期限。再用候选初态重建 held timer 日历，预测到新的首个期限，完成未来历史与输出认证后一起提交。`due=0` 改为未来值或禁用会改变第二个期限；仍为零的 timer 保留给主循环执行，不把 initial 当成已消费 timer。初始测量体和 Display 只执行一次。其他初始化路径保留原策略。
独立曲线、改期、零 timer 与查询网格检查见 [test_initial_observer_horizon.py](../../tests/test_initial_observer_horizon.py)。
一般电路反馈谓词与非线性电气联立赋值仍未支持；隔离统计数学的有限扩展见[事件数学](#event-math)。

实现见[实例隔离与投影](../../rust_core/src/passive_events.rs)、
[物理事件提交](../../rust_core/src/transient.rs)与[物理采样区间](../../rust_core/src/settlement_bounds.rs)。
[公开回归](../../tests/test_passive_events.py)检查同刻读值、自己的 timer、查询不累加及拒绝边界；
[内核回归](../../rust_core/src/transient_passive_tests.rs)检查 tau 与 b、历史不变和整批回滚。
实际 Spectre 对照只证明[列出的有限控制](../../../experiments/backends/support/r01-timing-observers/README.md)，
没有增加论文表的 Q 成绩，也不代替完整原 timing 请求验收。

## timer 与同刻兼容性

同块程序赋值遵守语句顺序，跨块同刻执行遵守前面的联立与写者冲突规则。
固定 Spectre **21.1.0.509.isr12** 的重复自增诊断曾出现与顺序赋值独立答案不同的输出；
缩小步长仍存在，插入中间值观测可使现象消失。最小模型没有电压反馈。
确切内部原因、新版本范围和厂商确认仍未知，见
[Issue #16 的输入及对照](https://github.com/BucketSran/vaEVAS/issues/16)。
EVAS 保留合法的顺序赋值，不将特定后端的异常输出设为期望值。

历史 timer 修复和回放保留在[固定历史章节](https://github.com/BucketSran/vaEVAS/blob/1527502c9affb77fec12aac03adba5446f0f241e/evas/docs/EVENTS.md#timer-与同刻兼容性)。
旧检查点的成绩不能当作当前版本的新执行。若 guard 依赖会被事件修改的历史，
须在变化后重新定位根，不能沿用失效的预计算日程；当前受限实现见下节。

### 事件修改的仿射 guard 重定位

PR61 支持下述范围，尚未取得新的跨后端资格。范围是联合仿射电压网络，
guard 不依赖历史算子；无关的积分/滤波历史可以共存。guard 可直接或经内部节点依赖离散状态。状态在事件间保持：

```text
A v = B u(t) + C q_k + d
g_j(t) = a_j u(t) + c_j q_k + b_j,  t_k < t <= t_(k+1)
```

`event_accuracy.rs` 从原 IR 用区间消元得到投影，并将已接受的 `q_k` 区间代入常数项。
每段 PWL 仍使用既有仿射根证明及容差验收。事件候选先联立求得 `q_(k+1)`，然后只对
非零状态投影系数涉及的已改变区间，撤销旧的未来根并定位 `(t_event,stop]` 的新根。
未改变的 guard 与固定 timer 保留原证书；计数器自增不会令无关 guard 重新触发。
新旧 guard 在整个事件观察窗口内必须能证明同号。跳过零、落到零、离开零或符号无法
认证时返回 `unsupported_cross`；同刻跳变的事件闭包仍需单独设计。

日程重建、与保留日程的同根/先后判断和全部容差检查，都发生在候选内。
成功后一次提交电压、状态区间、日程、游标与记录；失败没有部分更新。更新日程不能
以 `ttol` 合并不同根，也不能静默删除与已接受边界重叠的未来窗口。

独立例：`u=t`，阈值在 `.25` 从 `.75` 改为 `.5`，唯一 cross 为 `.5`，原 `.75` 根作废。
换成阈值 `2` 则无未来 cross；换成 `.125` 造成跳过零，当前明确拒绝。
新模型/刺激见 [event_relocalization](../../validation/cases/event_relocalization/dut.va)，
有理数答案见 [数学检查](../../validation/check_event_conditions_math.py)，
开发回归见 [test_event_relocalization.py](../../tests/test_event_relocalization.py)。
Rust 的 [Controller 回退检查](../../rust_core/src/transient_lifecycle_tests.rs)故意使新根窗口
与独立根无法确认先后，检查失败后的状态、区间、日程及记录，并在同一实例重试。
这些是开发证据；不改变原 31 条件的分母。事件修改历史、隐式非线性 guard 和跳变闭包不由这项切片证明。

### 事件修改积分轨迹后的根重定位

当前候选支持联合仿射电压网络中，事件改变连续积分状态的输入或保持参数后，
重新计算历史驱动的 `cross`。这不是一般隐式非线性 guard 或同刻跳变闭包。

例如 `z=idt(slope,0)`，`slope` 初值为 1，在 `t=0.25` 改为 2。保持积分状态连续：

```text
z(t) = t,                     0 <= t <= 0.25
z(t) = 0.25 + 2(t - 0.25),     t > 0.25
cross(z - 0.75, +1) 的新根为 t = 0.5，旧预测 t = 0.75 必须作废。
```

对一般受支持的连续状态，事件前后遵守：

```text
x'(t) = f(x(t), u(t), q_k)
x(t_e+) = x(t_e-)                 // 没有复位或跳变时
q_(k+1) = event_body(q_k, v(t_e))
g(t) = guard(x(t), u(t), q_(k+1))  // 用新流重新定位未来根
```

实现由 [history calendar](../../rust_core/src/transient_history_calendar.rs) 管理：

1. 先取得不依赖历史的下一事件，用它限定当前预测区间。
2. 在该区间内，用既有历史包围和导数证明定位历史 guard 的根。
3. 到达事件后，在候选中完成赋值、联立求解及历史重启。保留物理状态和已累积误差。
4. 撤销旧历史根，重建未来历史及根。未改变的独立 guard 和 timer 保留原证书。
5. 日程顺序、历史和电压精度全部通过后，才一起提交状态、日程与记录。

两条复杂事件路径的接受合同由
[Controller 的共同接受模块](../../rust_core/src/transient_event_acceptance.rs)管理。
`accept_relocalized` 和 `accept_history_events` 只选择保持状态或历史策略，
共同模块负责旧流事件候选、策略计划、历史延伸、最终日程与电压认证，以及一次发布。
普通事件路径与生产循环的互斥分派保持原有顺序。

`prepare_changed_batch` 集中单轮候选准备：旧流观察与赋值、策略相关的未来日程和
物理历史、历史延伸与最终认证。首次事件和后续微事件均调用这个入口，返回候选
frame、记录、批次末游标和未来日程。静态策略首次从完整日程截取连通事件簇及
下一截止点；后续微事件消费已经截取的日程，不重新扫描完整日程。
`PreparedEvents::prepare` 只读借用已接受的 Controller 与日程，集中处理微事件预算、
整个事件簇的闭包，以及按物理先后选择阶段的输出查询。全部成功后返回候选状态、
记录、输出和日程更新。`CalendarUpdate` 区分静态日程的游标推进与重定位日程的替换，
后者从游标零开始。`accept_changed_events` 只负责调用准备，再消费候选进行一次发布。
`publish` 不执行可返回错误的计算。单轮成功不提交 Controller；后续轮次或输出查询
失败时，仍保留整个事件簇开始前的状态、历史、日程、游标、记录和已存输出。

保持状态策略先在新 held state 下重排未来 timer/guard，用新日程首项限定延伸区间。
历史策略先重排独立日程并保存已消费根的身份和方向，共同模块延伸候选历史后，
再用该轨迹定位历史根。这个先后关系不能互换。两种计划都进入同一个最终验收点，
检查 operator deadline 和新的首项事件顺序，并用延伸后的历史包围认证存储电压。
任何失败都只丢弃候选；accepted frame、state bounds、history、cursor、records 和旧日程
均保留。验收点之后的状态与日程发布之间没有可返回错误的操作。

近时钟批次还有单独的旧流窗口义务。若批次含固定 timer 且窗口非点，
历史 guard 的事件后管道必须在整个窗口内排除隐藏根，即使 `keeps_guard_value`
成立且保持参数没有直接改变。值连续不能证明流场相同；该检查位于跳过未改变 guard
之前。本次重构保留此检查、阈值与拒绝类别，不扩大支持范围。

同 Controller 检查保留事件求值、未来排序和历史延伸的各项失败/重试案例。
共同接受模块另有最终 deadline 与电压验收的回退检查。前者向候选计划提供与
transition 截止点包围重叠的 timer，检查最终排序拒绝与修正重试。
后者在真实非线性候选闭包后
注入错误的存储电压，再经共同的历史延伸和最终认证，检查失败与修正重试。
它是隔离最后验收点的负控，不宣称该模型自然出现延伸后的事件点包围增宽。
移除最终电压认证会使该检查失败。
历史计划也通过同一末阶段负控。模型 `z=t` 在 `t=0.25` 把阈值从 `0.75` 改为
`0.625`，先延伸候选轨迹，再由 `history_epoch` 定位新根。在候选电压被故意改变时，
最终认证拒绝且已接受状态与旧根保留。修正后在同一 Controller 重试，未来日程只保留
`0.625` 的历史根，并与干净接受的状态、历史包围、日程和记录一致。

若事件改变 guard 的保持阈值，旧值和新值必须在**整个事件时间包围**内证明同号。
连续历史使用旧流在该区间内的状态包围，并代入新保持状态；不能只检查代表时刻。
复位等不连续历史若还带有事件时间不确定性，则明确拒绝，等待单独的同刻闭包设计。

已经执行的根不会仅凭一个固定时间偏移被丢弃。事件须保持 guard 连续，离根区间的
导数须严格同号，还须保留进入该根的方向。**局部单调只能证明至多一个根，不能证明
这个根就是刚执行的根。** 当定位代表时刻略晚于真根，事件换向后可能返回穿越同一阈值。

若当前 guard 包围仍含零，后续导数与进入方向相反，并且 direction 也选择该返回方向，
当前实现无法区分返回穿越与已消费根的不确定性，返回 `unsupported_cross`。
它不能宣称这类双向自换向模型兼容 Spectre。只选择向外穿越的有向 guard 可以排除返回方向；
不改变轨迹的双向计数则保留正常的后续正、负向根。
若 guard 在重启点已严格位于零的一侧，直接继续根搜索；即使返回根距离小于 `ttol`，
也不能用固定消抖窗口删除它。导数含零、形成平台或无法证明离根时返回 `event_resolution`。

这是一项明确的支持边界，不能据此断言所有双向 `cross` 不合法或 Spectre 存在缺陷。
有向振荡器参考写法及容差干预见[兼容性实验](../../../experiments/backends/dvs2-spectre-validation/README.md#oscillator-compatibility)。
后续[拆分诊断](../../../experiments/backends/dvs2-spectre-validation/README.md#cross-restart-diagnostic)
分别隔离了近距离穿越的分辨能力和换向附近的积分误差；原模型尚无稳定的跨后端事件序列。
这些观测不支持用固定消抖或模拟某组设置下的积分平台来补齐兼容性。
接受范围和后续验收由 [Issue #70](https://github.com/BucketSran/vaEVAS/issues/70) 跟踪。

2026-10-10 复核保留原乘积 guard 和双向触发，仅分别探查初始斜率 ±1、±3 及两种查询网格。
八组均拒绝；其中 ±1 的密集网格在根附近先遇到 `event_resolution`，其余六组为自换向
`unsupported_cross`。这是拒绝阶段不同，不是八组事件序列通过；本批没有新增 Spectre 执行。
若第一阈值为 h、正斜率为 s，首次根为 τ=h/s；在 τ+δ 换向后，返回同一阈值的时刻为 τ+2δ。
δ=0 的理想反弹与 δ>0 的返回穿越具有不同事件序列，即使两条电压曲线相差很小。
这解释了为什么必须分别验收波形和计数，不能靠电压容差或统一死区决定正确计数。
它不是 Spectre 内部算法的推断。当前仍需可区分的返回根/历史契约及对应参考验收，
不能将本分析当作接受新的兼容性例外或关闭 #70 的依据。

事件时间包围会进入下一段历史。历史日程的动态根优先定位到显式 `ttol` 和 `etol`
的 1/64，以减少后续历史的不确定度。这个系数只是内部数值余量，不是新的精度承诺。
若已有历史误差使进一步收缩停滞，只能在原公开容差已经满足时接受；否则拒绝。
电压与历史认证仍须独立通过，不能用小方程残差替代它们。

边界保持明确：guard 跳过零或落在不确定零附近、激活复位导致当前 guard 跳变、
`ddt` 等不连续轨迹、未提供可认证轨迹/导数的历史算子，以及隐式非线性网络 guard，
均未由这次改动补齐。预测区间本身也必须可求解；本实现不是在任意失效轨迹前自动寻找救援事件。

[开发测试](../../tests/test_history_relocalization.py)检查提前、推迟、消失、反向积分、
阈值变化、非精确根、独立事件与无关历史共存，以及输出采样不改变事件历史。
[Controller 回退检查](../../rust_core/src/transient_lifecycle_tests.rs)在同一实例中拒绝失败候选后重试。
[Spectre 专项入口](../../../experiments/backends/dvs2-spectre-validation/README.md#history-relocalization)
固定 7 类模型、两档步长及独立数学答案；实际后端执行状态以专项收据为准。
这些案例已用于开发，不是新的独立确认集，也不改变原 31 条件矩阵的历史成绩。

<a id="static-loop-events"></a>

## 静态循环中的事件

实例参数确定后，有限 `genvar` 循环等价于一组独立事件声明。例如
`for(i=0;i<N;i=i+1) @(timer(a+i*d,T)) ...` 展开为 N 个事件；第 i 个事件的
名义日程为 `t(i,k)=a+i*d+k*T`，T>0 时 k 为非负整数。非正周期沿用单次 timer 规则。
嵌套循环对每个下标元组分别代入触发参数和事件体，不在运行时执行循环。

[syntax.py](../../src/evas/syntax.py)保留事件与循环的源码顺序；
[elaboration.py](../../src/evas/elaboration.py)在实例绑定后替换下标；
[node_elaboration.py](../../src/evas/node_elaboration.py)再分离事件与连续贡献，展开静态节点访问。
身份由完整实例名、源码位置和展开路径组成，guard 内的历史调用也各有独立槽。
所有事件继续经过同一日程、候选求解和整批提交路径。同刻写入同一状态仍报告冲突，
不能因循环迭代顺序而先后覆盖。

支持 timer/cross 及其 OR、事件体内原有条件赋值、静态数组和向量下标。
普通模拟条件下的事件需要运行时激活语义，当前拒绝；循环包围初始化事件仍未开放。
当前开发切片接受纯初始化体或初始化/cross 共用体内的静态 genvar 循环：
先按实例常量展开 initial 与 analog 树，再沿既有路径安装唯一初值和监测事件，
两树共享迭代与语句预算。初值、拒绝边界、手算答案及待执行实际配对见
[初始化循环契约](../../validation/INITIAL_STATIC_LOOP_CONTRACT.md)。
事件体内的有限静态循环在同一次回调内顺序展开，后续赋值读到本回调前序赋值的结果。
例如 `@(timer(1)) for(i=0;i<3;i=i+1) n=10*n+i+1` 从 `n=0` 得到 123，
它只产生一个事件块，不会形成三个相互冲突的事件写者。
独立事件块之间的同刻冲突、跨写者依赖和失败回退规则保持不变。
体内仍只允许原有赋值和受支持条件，不能引入贡献、历史调用、嵌套事件或运行时循环。
[事件体循环测试](../../tests/test_event_body_loops.py)覆盖顺序、静态数组、实例参数和拒绝边界。
总迭代和展开语句各限 4096，事件及体内叶子分别占用语句预算。
[开发测试](../../tests/test_static_loops.py)使用手算时刻、计数及积分答案，并检查实例隔离和冲突拒绝。
[ZOOM 对照](../../../experiments/backends/dvs2-spectre-validation/README.md#zoom-static-events)
复用原模型及冻结判据，结果不等于任意事件组合或一般连续时间精度资格。

## 实现与验证入口

- [events.rs](../../rust_core/src/events.rs)：身份、结构依赖、顺序代入和赋值重放。
- [settlement.rs](../../rust_core/src/settlement.rs)、[settlement_bounds.rs](../../rust_core/src/settlement_bounds.rs)：同刻联立、原关系检查及区间认证。
- [schedule.rs](../../rust_core/src/schedule.rs)、[event_accuracy.rs](../../rust_core/src/event_accuracy.rs)：固定日程、根和误差界。
- [transient.rs](../../rust_core/src/transient.rs)：候选帧、原子提交、丢弃及回退测试。
- [test_settlement.py](../../tests/test_settlement.py)、[test_timer.py](../../tests/test_timer.py)、[test_event_accuracy.py](../../tests/test_event_accuracy.py)：独立开发回归。
- [Spectre 实验](../../../experiments/backends/dvs2-spectre-validation/README.md)与[共同历史协议](../../validation/METHOD_QUALIFICATION.md)：判据及观察限制。

这些证据不等于完整 DVS 资格、任意非线性事件支持或其他仿真器内部算法的证明。

### 分段保持状态下的多项式 guard

本分支把同一重定位生命周期用于 `g=P(v(t),q_k)`，例如 `u=t`、
`g=u²−q`、q 在 .25 从 .75 改为 .5，新根应为 `sqrt(.5)`。
`GuardTrajectory` 从原仿射电压网络求节点包围，将已接受状态区间保持在该事件间隔，
以区间多项式和链式法则求 `(G,G')`，复用 `dynamic_roots` 的单调括区认证。
直接状态导数为零；内部节点的状态投影也读取同一份区间。
初始状态不能当作所有未来区间的状态。

只撤销实际依赖已改变状态的 guard；未改变的多项式根保留原证书，避免重触发。
事件观察窗口中的旧/新值须证明同号，日程重建成功后才提交。
非线性表达式的相关性丢失可能令包围偏宽；取消项、极小量和切线不能借浮点相消
伪造根证明，失败返回 event_resolution 或明确的同刻闭包拒绝。
网络贡献仍须联合仿射，guard 须与历史算子独立；这项能力不是隐式非线性网络求解。
开发检查包括平方根答案、内部节点投影、观察网格不变性、原始算术消去拒绝，
以及同一 Controller 内的候选跳变失败/重试。该切片没有新 Spectre 对照。

<a id="held-timer"></a>

### 保持状态控制的动态 timer（IR17 分支候选）

语言依据为 [LRM 2.4 §5.10.3.3](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)：
起始时间、周期和 enable 可以改变，time_tol 是常量；start/period 不能调用模拟滤波函数。
变化后下一事件使用最新参数；重新启用时如同没有禁用，不能把 enable 的变化当作新相位原点。

本切片以每个事件间保持的 `q_k` 求 `a(q_k)`、`p(q_k)`、`e(q_k)` 的区间。
若 p>0，未来发生集合为 `a+k*p` 中严格晚于已接受边界的名义事件；
p≤0 则只考虑未来的一次 a。没有改变参数的叶子继续使用原日程。
若参数变化产生当前时刻的候选，必须证明这个 timer 叶子的同一精确时钟已经消费。
共用 OR 事件体不等于同一叶子；相同浮点代表或重叠窗口也不证明同一时钟。
新出现且未消费的当前 timer 返回 `event_resolution`，不能静默丢弃。
例如在 .5 将另一 timer 的 start 从 .75 改成 .5，需要尚未实现的同刻闭包；
已消费 timer 在本次回调中把 period 从 .5 改成 .25，则保留已消费事实并继续寻找未来事件。
`next=next+.25` 的单次 timer 应依次在 .25、.5、.75、1 发生；
start=0、period 从 .5 改为 .25 后依旧按 0+.25k 定位，不从改写时刻重起周期。

从原 IR 计算参数包围，nominal-time、stop 和已接受边界的比较须可认证。
不确定窗口横跨边界或 stop、启用真假不明、正周期无法证明、时间误差超容差或预算超限均拒绝。
新日程及与保留 cross/timer 的排序/同刻认证在候选中完成；失败不修改旧帧。
同一 Controller 的失败排序及修正重试见 transient_lifecycle_tests。

例如 `due=$abstime+delay` 将时间保存在 real 状态，再由单次 `timer(due)` 触发。EVAS 除完整状态区间外，还可保留已证明的精确时间来源，以判定相邻查询在回调之前还是之后。来源接受整条原始 PWL 的时间恒等关系、已证明的 real 状态复制及逐次固定偏移；不依据变量名字或某一个采样值猜测。

已有时间证明的 real 状态被有限常量覆盖时，可将证明替换为该常量的精确值。`min`、`max` 只有在两侧分别具有时间证明或为显式有限常量时，才按精确顺序保留选中一侧的证明。例如 `due0=1e30; next_due=min(due0,due1)` 可以保留较早的 `due1`，前提是 `due0` 在覆盖前仍有时间证明，且 `due1` 的证明有效。这不为普通初始化数组建立时间证明，也不把未经证明的状态值当成精确时刻。

不支持的改写或未知的选择参数仍会清除证明；证明改变或清除，即使数值区间没变，也重建相关 timer 日程。动态周期和一般时间表达式不获得此例外。该证明不收窄原状态与事件区间，也不改变原电压误差验收；邻近输出点仍须证明位于事件哪一侧。
独立邻点、改写与原曲线控制见 [test_held_time_provenance.py](../../tests/test_held_time_provenance.py)。

`held_timer` 保存参数表达式；原固定 timer 的 IR 字段和定位公式保留。
事件记录仍为 `kind=timer`，OR 内 timer 叶子也不包含虚构 guard 值。
参数须是状态/常量的联合仿射表达式。候选允许联合积分/滤波/复位历史：
先在当前事件完成观察与复位闭包，再认证新日程，最后将候选轨迹推进到新日程的首个截止点。
初始化也先建立日程，再预测轨迹，避免跨过能改变流场的事件。新日程或新轨迹失败都不提交。
例如 y′=q y²、y(0)=1，next 在 .25 从 .75 改为 .5，.5 时令 q=−1：
答案在 .5 前为 1/(1−t)，之后为 1/t；不能沿旧增长流场预测到 stop。
同一 Controller 另检查新日程成功、未来流场失败后的完整回退与修正重试。
连续电压参数、动态 tolerance、一般非线性参数仍需补齐。历史驱动 guard 的受限联合预测见“事件修改积分轨迹后的根重定位”。
独立回归见 [test_dynamic_timer.py](../../tests/test_dynamic_timer.py)。
[新当前 timer 的实际对照](../../../experiments/backends/support/retained-safety/README.md)
确认两个反例的 Spectre 回调与一个改周期正控；它没有证明一般 held timer 组合全部兼容。


## 有界局部因果闭包（候选）

近邻时钟的物理时刻为原始 binary64 参数定义的精确数
`tau = start + index * period`。后续自治线性或多项式网络使用
`delta = t - tau` 建立局部 IVP；种子是最终同刻映射后的物理状态，
不把已传播到代表时刻 `b` 的状态当作新的初值。局部坐标查询先用有界整数
累加器认证精确时间差，再调用既有线性传播或多项式 Taylor/Picard 历程。
它没有先将 `tau + delta` 舍入为绝对时间。源耦合的流、源直通输出和依赖
驱动源的历史 guard 不满足这层自治资格，仍明确拒绝。

根隔离在局部坐标上给出 guard 与导数盒，随后按物理先后顺序插入或重排。
动态根的观察权限保留原不可变历程的共享身份；源仿射根保留原段端点与
分子，时钟保留原参数及有界整数索引。无根身份、过期模式历程或缺少因果
先后证明的观察不能只凭两个时间盒的几何关系获准。相同 guard 的同一根
可以合并 OR 叶；不同物理时刻不会因为绝对时间盒重叠而合并。

候选控制器完成整个相连观察簇：旧物理状态、映射后的新流、最早根、
重新排列的日程、严格递增的 binary64 代表值、扩展覆盖并再次检查 guard。
各微事件使用自己的物理观察证书，同物理时刻的同批事件仍联立。
候选阶段帧保存每批事件的物理证书、映射后保持状态和流。簇内请求输出
以 binary64 查询的精确数值与原时钟、源根或局部根盒比较，选择已经发生
的物理阶段；代表时刻只用于执行记录，不能推迟查询中的状态跳变。
强制点若已经处于所有已消费事件之后、下一事件之前，可以在候选中认证并提交
这段物理前缀，随后保留未来日程。未证明先后的点不能截断事务，仍按原拒绝规则处理。
普通固定/仿射源混合簇和 held 簇也使用这个阶段接口，主循环在物理事件
已经到期时先关闭候选，不等代表时刻再输出。局部流查询按物理 delta/cursor
选择历史，不能按代表时刻分流。查询落在不能证明先后的根/held 参数盒内
明确拒绝。对严格导数证明唯一性的根盒，可在盒内尝试至多 53 个由盒端点
决定的二进制网格点。只有 guard 点区间严格等于零才收紧为点证书，包含零
不够；搜索不读取输出网格。

近时钟种子覆盖整个事务所需的物理阶段。查询等于首执行代表时，只有已经
证明后继事件在物理上不晚于查询、且其代表会越过查询，才为该查询保留
局部种子。窗口重叠本身不够；没有此类后继的普通受迫积分仍走原历史路径。
判定使用当前回调之后仍有效的未来日程：held 参数的改期或禁用先重建，
不能用旧截止点触发局部锚定。History 路径只在尚无局部 epoch 且当前窗口
非点时预刷新独立事件；已有局部历史仍先验证观察证书，再按原顺序重建根。
增加输出点不能改变物理事件序列。输出在提交前独立求解，所有未来截止点
和最终电压误差认证通过后，状态、记录、阶段输出和日程一次发布。
任一步失败完整回退，同一控制器可重试。

固定日历保持原数组和原游标，只复制当前相连簇及一个后继截止点。
复制成本随簇大小而非剩余全部日历增长，此处没有实测速度声明。

候选精确排序还覆盖点证书 held timer 与仿射 PWL 源根。
若严格递增的执行代表值推进到原簇外下一事件的下界，候选先尝试扩展该簇。
只有下一事件的原证书能与簇内每个事件证明物理先后或同根，才纳入并重新排序；
每个代表值仍逐项通过原时间、表达式和 stop 预算。无证书的内部根仍拒绝，
不能只因浮点代表值接近就合并回调。例如输入从 binary64 的 0.1 升至 0.9，
两个源 cross 阈值为 0.5、0.5000000000000001，中间的 `timer(0.5)`
可按三个精确物理时刻执行；增加查询点不改变事件记录。后续 held 改期失败
仍回退整个候选，修正后可用同一控制器重试。
构建期排序与控制器复用同一事务资源上限：首个物理时刻组之后最多 64 个
后续组。同刻叶子共享一组，不按叶子数拒绝；65 个后续组返回 `event_budget`。
扩簇一次纳入下一整个相连包围组件，不因其中多个同刻叶子逐个重排全簇。
此检查在重复扩簇和重排阶段施加上限，不等到扩簇遍历完全部日程才拒绝。
该上限约束后续物理组数及重复扩簇次数，不约束同刻叶子数；70 个同刻叶子仍共享一组。
初簇的全对证书预检与扩展组件的逐项证书预检均可能为叶子数的二次复杂度，
且完整日程仍先收集、全局事件数上限仍为百万。这里不承诺日程构建的总复杂度或耗时上界。
下一事件缺少精确排序证书则返回 `event_resolution`，诊断明确指出证书缺失，
与代表值确实超出原容差或 stop 的拒绝区分。
比较最多八个三项 binary64 乘积的精确和，以固定长度整数累加器取符号；
独立 BigRational 属性检查覆盖其符号与紧时间差。非点 held 参数、无严格
先后证书的重叠根、跳跃 guard 与已有自换向边界仍拒绝。新历史根的局部候选
日程至多 64 个微事件，事务至多首组与 64 个后续组，另保留全局事件预算；这是明确的资源
边界，不把未完成的序列视作成功。原 time_tol、expression_tol、stop 和
电压/状态误差门均未放宽。没有可用代表值的时间容差拒绝使用
`event_resolution`，消息含 `cross_ttol_unrepresentable`；该诊断需要相邻
binary64 与局部根盒的最小延迟证明，其他隔离失败不冒充此结论。

[公共独立回归](../../tests/test_bounded_event_closure.py)覆盖隐藏根的接受与
特定容差拒绝、改变流速的两根链、源根/多时钟、点证书 held 参数和三种
输出网格；Rust 控制器检查后续微事件失败后的整批回退与同控制器重试。
这是分支候选证据。新 Spectre 原配置的窗口外阶段差异及 tight 配置内部
崩溃保留，不能把本地正确答案或参考仿真失败当作完整后端对齐。
The common acceptance refactor has a [six-model, two-setting preservation comparison](../../../experiments/backends/event-acceptance/README.md). Mathematical error, finite waveform pairs, exact-boundary observations and reference qualification are reported separately. These development results do not expand capability support.
有序物理历史的[独立条件和实际对照](../../../experiments/backends/ordered-event-history/README.md)分别报告原始计时容差失败与严格计时诊断。后者不替代原始结果，也不能由同一导出行内的两个计数变化推断精确回调先后。

有界闭包的[冻结模型、实际 Spectre 对照与 EVAS 复测](../../../experiments/backends/ordered-event-sources/README.md)保留原编译失败、崩溃、超差和诊断配置。EVAS 修复没有改变参考源码、设置或检查器，故复用这些参考执行；新增物理相位点使用独立有理数答案，不冒充新的逐点 Spectre 配对。两组各 16 份 EVAS 请求分别有 14 份有限输出通过、2 份规定拒绝通过，旧查询相位失败仍可追溯。精确导出终点、极近回调次序及一般跳变闭包未据此获得资格。

<a id="extension-event-contract"></a>

## C1/C5 扩展的共同事件接口

本节是 [ADR-002](../development/DECISIONS.md#adr-002) 的设计契约。
main `fbf896bb` 与未合并候选 #108 的差别须保留，候选的物理阶段输出及有界微事件事务
不因接口被采用而成为已合并支持或完整 Spectre 对齐。

数学根 tau、实际触发 te、执行代表值 b 是三个不同对象。当前 cross 条件按
[`te=tau+`](#cross-right-limit) 选择；其他触发策略需显式决定。窗口须携带所证明的根/触发身份、方向、来源与误差，
不能仅凭时间盒重叠合并两个事件。每次赋值、条件、电压采样、复位和后续历史共用一次 te。
若 b 晚于 te，必须分别包围 te 前的旧流与 te 后的新流，不能将 b 当作物理采样时刻。
查询属于哪个物理阶段也须证明，无法证明先后时拒绝，不能用代表值选择前态/后态。

C1 改变 q 后只撤销实际受影响的未来 guard 证书，再用保持的物理状态、新流和误差重新定位。
旧根不得继续消费，未改变的根不能重复触发。预测终点首先受已知固定/保持 timer 和源断点限定，
保持 timer 改期/禁用时先重建截止点，不能按过期日程推进未来轨迹。
新日程、窗口排序、截止点、状态/电压与未来历史全部在候选内验收。

C5 的每个 timer 参数先分类为实例常量、分段保持状态或连续量。
现有 fixed/held 的绝对 start 与周期相位规则继续成立；连续电压 timer 和动态容差尚未定义实施，
须由最小模型说明修改参数时如何确定未来发生集合及已到期事件，不能以逐输出点检查替代。
隐式 guard 则依赖 C2 的代数分支证书与导数，普通 ODE guard 通过不能证明该组合。

一般同刻跳变闭包需先定义哪些零跳越会触发、同刻触发集合怎样确定，以及解存在/唯一性的条件。
有界微事件簇限制必须显式报告；预算耗尽是失败，不能发布部分簇作为成功。
在这套新契约获得独立反例和实际对照前，保留跳变、不确定自换向、连续 timer 和隐式 guard 的拒绝。
实现时共用一个接受入口，使 state/history/calendar/cursor/records/phase-output 整批提交；
任何一次局部失败都还原整批接受基线，观察查询不得修改这些对象。
具体独立答案、当前已选组合与后续责任分别见 ADR-002 的 C1/C5 行。


### 常数积分历史的精确相位证书

自主常数流的线性 `idt` 历史可附带精确仿射来源。初始值来自原始单点 IC；斜率和输出映射必须具有单点区间证明，不能含状态反馈、源驱动、reset 或滤波器。已证明为单点的事件推进从旧来源精确计算新种子；一般非点事件窗口继续使用原区间种子，并丢弃此精确来源。侧证明使用现有精确源算术的 512 项、4096 位和 200,000 操作预算；超限或缺证明时回到原区间路径。

guard 的精确仿射根必须落在原隔离盒中。日程保留原盒和根身份，仅把执行观察盒与该有理数根的严格外包络相交，再使用上端代表。原方向、时间/表达式容差、stop 与因果前驱检查继续生效；旧流采样、状态映射和新历史种子共享这一观察盒。根证书用于查询和事件排序，两个有理数根即使共享同一个 binary64 外包络也不能合并。此精化复用原始 PWL 根证书的原则，没有把最近浮点数定义为事件时刻。

原 E3 中 `idt(slope)` 在 timer `.25` 后斜率为 2，根恰为 `.5`，该查询读事件后状态。原 E5 的根为有理数 `1/3`，binary64 查询 `float(1/3)` 严格在根前，下一浮点查询在根后。完整原查询列表、邻接查询和稀疏布局由 [历史相位回归](../../tests/test_exact_affine_history_phase.py) 覆盖；一般多项式历史根仍不能由这一仿射证明决定相位。


### 精确DC供电系数与history guard投影

Transition输出乘原始输入供电差、再由内部节点cross采样时，可在投影矩阵中使用整段物理DC系数。
该切片只接收原始已驱动输入/ground的仿射供电叶子；必须在整个`[0,stop]`零斜率、零误差、有限，
完整乘子的精确有理值可表示为非零binary64。正负值均保留，零ground项本身不非法；
零供电、变化源、正误差（包括有physical shape）、隐藏内部依赖和不可精确表示的差值明确拒绝。
例如binary64的`0.9-0`可用，但`0.9-0.1`的精确差不能先浮点舍入为`0.8`再充当证明。

`dc_projection::DcProjection`仅持有原贡献的受证行视图。原Program、贡献、guard树、Origin、
方向和误差门不变，原始电压关系仍用于数值求解与forward-error验收。投影保留供电幅值和符号，
不把`A*(T-0.5)`约成`T-0.5`，也不在另一个实例guard中生成foreign OperatorRef。
`GuardTrajectory`继续使用原Transition epoch、原搜索窗和`RootTime`；等值盒不是history身份。

资格来自既有贡献依赖解析的乘子标记，旧direct-affine和合法implicit分流不承担新DC审计。
`EventModel`、guard/condition/settlement行与实际Operators初始化共用同一个不可变`ProofContext`及
粘性的`Work`。新增树复制、比较、全域精确请求和成员查找均归该owner；耗尽或证明失败不重建owner。
原依赖和未选臂所有权先审计，不能先用零系数/常量化隐藏非法引用。

独立合同见`test_dc_factor.py`：正负供电、非零参考、跨实例与近邻不同history根、全域变化与误差拒绝，
以及原根误差在后续电压放大后紧预算拒绝、宽预算返回区间包围独立有理真值。
同engine失败重试与共享额度耗尽由`dc_projection`私有测试覆盖。原111已随wave15统一候选通过完整请求与原checker；身份与资源边界见[低成本闭包收据](../../../experiments/backends/support/low-cost-closure/evidence.json)，不据此开放一般联合仿射历史组合。

### IR29 本地候选：typed 逻辑右移、按位与及严格保持目标

IR29 / 0.22.0 在既有 typed 事件树中新增 `ShiftRight` 和 `BitAnd`。`>>` 的计数必须来自
integer 常量，先解释为32位无符号数，计数大于等于32时结果为零，包括源 `-1`。
例如 `-1>>1=2147483647`、`-1>>31=1`、`-1>>32=0`。`&` 对32位补码逐位求与。
每个原 Add/Subtract/Rem 子节点仍先检查 signed32，父 `&0` 或 `>>32` 不抹掉子节点溢出。
旧256有限域及4096决策表示成功时保持旧IR；不新增左移、Or/Xor、单目负号、Divide、
普通连续integer贡献、trigger或一般CheckedInteger/Floor准入。

新增 target 是独立 opt-in 消费者，限普通独立日历、全Transition图中的同owner integer
保持状态纯函数。只接受严格projection/Select，原实数常量系数可用于投影；每个原依赖，
包括未选分支和乘零后的依赖，都须经过结构/owner审计。实际Prepared/Frame盒须为与
名义值一致的有限signed32整数点，real state即使当前为整数点也不满足typed叶要求。
冷启动保留原point gate，不借用077裸real非点seed豁免。详细历史/误差合同见
[严格保持整数目标](operators.md#native-held-bits29)。

编译期 `Compilation.native_audit` 保存同一个累计账本。旧无新typed target的程序继续使用
原每事件100000审计限制。首次新target启用aggregate100000限制时，已经发生的全部计费
也计入，因此这是新组合入口更严格的工程准入。其后每个事件和target、失败fallback、
重试、实际Source AST/typing/IR emission/metadata遍历以及展开wire/copy均沿同owner扣费，
不为每target或重试重开额度。IR100000/depth96及其他原cap仍独立成立。
`Program.to_dict` 对opt-in程序逐个展开引用并计费；同一Program重复调用不会退款。
运行期沿原 `ProofContext` 的同一Work，旧无新target程序不创建新target proof。
跨feature入口可通过 `EventModel::new_with_context` 借用调用方在Stage0前创建的原请求Arc；
组合调用方不得为Floor、typed target或其他新消费者各建一个默认额度。

公共回归在 `test_native_held_bits29.py`、`test_held_integer_targets.py`、
`test_native_audit.py`。同Controller目标失败、实际Prepared/Frame非点拒绝和两事件两目标
自然耗尽后两次重试见 `transient_lifecycle_tests.rs::held29_*`。它们是开发证据，
不代表原061/062/027通过、完整Python/400、安装或发布验收。

保持target的长owner及依赖集合辅助按[amount审计费用](operators.md#native-held-bits29)
在实际操作前预付同一Work。运行期Work100000耗尽回归是缩限单元控制，不代表生产1e9额度自然耗尽；
编译aggregate100000的原额度耗尽证据与此分开。原Frame字段复制和首轮serde转换保持旧边界，
不计作新增target reservation已覆盖的工作。


### IR31 候选：事件中的直接电压到 integer 转换

此分支候选为事件体的 `integer code; code = V(input);` 增加显式
`IntegerRound(value, origin)`。输入必须是原始语法中的单个电压探针，引用实际
外部 driven 输入或 ground。原始 real 复合表达式、非整数 real 常量赋值、
时间表达式、history、普通连续赋值和内部节点不由此入口扩展。

[Verilog-AMS LRM 2.4 §4.2.1.1](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
规定最近整数与半整数远离零。因此 `1.5` 转换为 2，`-1.5` 转换为 -2。
这里通过单调最近整数函数计算整个原始输入盒的两个端点；端点结果必须相等，
且均在 signed32 范围内。转换先于程序随后写出的 clamp。跨整数 bin 或跨溢出
边界的盒显式拒绝，不能用代表值、下游 clamp 或事件输出采样点代替证书。
每个事件的输入盒重新绑定到该请求的实际 PWL 和根窗；plateau 不作为生命周期不变量。

代码复用 `event_floor::Request` 的完整原请求绑定、`Work` 和候选局部状态。
`event_control` 在原始有界 postorder 扫描中验证角色：新节点只能是标量 integer
赋值的 RHS 根；real 目标、外层算术或选择、display、trigger、贡献及 operator 输入均拒绝。
所有原始 children 仍完成结构与资源审计；新增角色查询先向同一 Work 付费，不复制 payload。
`event_control` 将新节点纳入原始树扫描；`causal_event` 验证实际 driven 依赖；
`event_floor::resolve` 对本次原输入盒付费并替换已证明的整数点；
`event_numeric` 拒绝未经该 owner 解析的点/盒消费者。原始 RHS 语法检查及未选臂审计
仍先执行，转换不会消除源程序中的整数溢出或其他域错误。

独立回归为 `tests/test_integer_round.py`，包含精确有理数 oracle 的 45 个 binary64
输入、正负 tie 与邻 ULP、signed32 边界、原值盒、非 binary cross 根窗、后续事件读取、
同刻写者和 clamp/保持目标/Transition 消费者。`transient_integer_round_tests.rs`
将 Floor 与新转换放入同一实际 Controller：两次最终电压拒绝后重试保留 accepted
历史，原 1e9 owner 自然耗尽后两次重试不获得额度。此为本地候选证据，
原142的CLI诊断已完整运行，但原worker/checker和最终共同候选验收尚未完成；
不增加任何完整任务 PASS，也未取得新的 Spectre 对齐证据。

线格式升至 IR31，Python 包与 kernel 候选身份为 0.24.0；IR30 和 IR31 相互拒绝。
旧保存请求应从原 VA 重新编译，不能只改 `schema_version`。


## IR32 private candidate: explicit analytic source values

本节保留最初私有候选的锚点；实现已合入IR32本地共同候选，完整交付仍待验收。
解析源切片只扩展物理输入值，不扩展正弦 guard、物理事件 sqrt 或 source×history。
`DEV:scs-input`、`CROSS`、`TIMER`、`EVENT-ORDER` 的新增证据尚未获得交付验收；
原件400与成熟IR31状态不变。显式 `sinedc/ampl/freq/sinephase` 通过 typed descriptor 传输，
保留原终端、source名称、极性与参数出处。正 finite freq 是本实现支持域；
早期候选拒绝厂商默认、AC phase 与 Meg 后缀；2026-10-21 本地入口扩展见下节，
不能由局部通过推断完整 Spectre 对齐。

物理定义为 `polarity*(sinedc+ampl*sin(2*pi*freq*t+pi*sinephase/180))`。
时间和全部参数先作为区间组合 phase，再调用已有有限 Taylor sin 证书。
point、range与导数均保留区间；非binary PWL根用其真实根窗包围正弦，绝不创建有理正弦证明。
phase与导数移相超出已有有限域时拒绝，不使用PWL拟合或nominal回退。

请求入口创建唯一原 Work，原 limits `[128,8192,1000000000]` 不变。
`AnalyticRequest` 私有能力在完整原program/provider/driven绑定后，只准常量初始化、
直接仿射事件赋值、独立原PWL cross或fixed timer，以及直接held输出。resolve前后必须通过
原binding逐字相等，不能借初始化或Graph reduction改写token。所有guard原始依赖均审核，
包括0系数；sine、internal voltage或隐藏未知分支不取得guard根能力。

`ProofOwner::History/Analytic` 只统一共同数学/拷贝的付费入口，不能授予History准入。
旧直接投影算法与fold顺序不变，History bit镜像回归仍需通过。
候选Frame、calendar、proof maps、空Operators与output存储在同Work下预付；拒绝不发布
物理state、calendar、record或output，已用Work不返还。

代码由 `scs_sources.py`/`scs.py`、`runtime.py`、IR32 `AnalyticSource`、
`analytic_source.rs`、`analytic_request.rs`、`pwl.rs` 与共同event paid调用负责。
公共1/6根采样与1/8 timer使用独立Fraction/Taylor答案；额外query、显式拒绝和原1e9自然耗尽
的完整Frame两retry检查保留于原私有证据；共同候选还运行公开入口联合控制。
完整Python由CI执行，局部结果不能替代交付CI，IR31原有完整400成绩不能移到IR32。

### 本地候选：受限 native SCS 零相位入口

`scs.py` 接受精确拼写 `Meg=10^6`，保持 `M=10^6` 与 `m=10^-3` 的区别；
小数、指数与独立正负号沿同一有限数值检查。`MEG`、`meg`、非法相邻后缀仍不在
本入口范围内；这种受限拒绝不是 Spectre 的语言裁定。

接地、无 delay/阻尼/调制的 transient 正弦仍要求显式 `sinedc`、`ampl` 和正 `freq`。
缺省 `sinephase` 取0度，使用 `spectre-native-transient-zero-phase-v1`，
显式相位保留 `explicit-v1`。Rust 拒绝未知标记和“缺省零”标记携带非零相位。
标记声明规范化合同，不认证输入来源。原 token、位置、参数引用和解析 settings
保存在 `testbench.sine_source_origins`，续行也保留各 token 的原位置。

有限 `phase` 是独立小信号参数，保留在元数据中，不进入上述瞬态正弦公式；
本候选不增加 AC 分析。`phase` 与非零 `sinephase` 同时出现的组合缺对照，统一拒绝，
不按任务或具体相位值特判。已有单独显式非零 `sinephase` 合同保持。
数值执行继续复用 `analytic_source::range`，没有新增采样近似。

语义依据复用 Issue214 的官方文档调查及既有 Spectre21.1 源列证据，归档入口为
`runs/evas-source-shape-20261017/overnight-integer-20261018/remaining80-20261020/scs-semantics-20261020/report.md`。
归档仅支持所检查的有限无延迟源形态，旧093频率与当前原件不同；源列对照也不等于364混频输出通过。
[独立入口测试](../../tests/test_scs_native_source_contract.py)用SI固定数值、原token序列、
四分之一周期解析值及电压包围验证新入口，并保留非法参数和来源反控。
本轮无新 Spectre，未给074、093、364整项增加通过信用。

### 本地候选：固定 timer 采样与 held Transition

`analytic_sampled_consumer::Admission` 为固定 timer 的采样状态和 held Transition
建立单独的原请求能力。事件体支持受限的顺序赋值、条件分支及标量加乘除，
可以先更新极值，再计算差值与比值。除数必须由当前完整误差盒证明不含零；
非点正弦采样保留原误差，不能用名义值建立有理证明。
Transition 目标保持为同实例的受限 held 表达式，目标选择条件限已声明的 integer 状态。
物理 DC 因子仍须通过整个原请求的供电证明。

`Operators::new_until_with_analytic_request` 接收同一私有 token 和原 Work，
核对完整 Program、provider、driven 顺序及上下文身份后创建历史。
所有隐藏分支、零系数依赖和 Origin 都先审计；它不授予一般 History、解析源 cross、
状态驱动 timer 或 EventMath 能力。内部 `$abstime` 的注入同时追加非解析 provider 槽，
保持外部 PWL、解析源及误差数组的位置对应；错误的原槽数和端口仍拒绝。

解析源的当前样本盒与历史保持样本盒分别守真，也可能无法决定严格极值比较。
例如相邻采样点落在正弦谷底两侧时，原 binary64 周期的确切 Clock 与理想十进制周期
可以给出不同的“相等”结论。该候选尚未建立一般的解析样本关联证书；差盒含零时继续拒绝，
不按名义值、输出误差阈值或相同外包盒决定分支。历史样本证明只能随真实赋值更新，
不能由额外查询写入物理状态。上述零相位入口语义不等于严格历史比较已经获得证明。

共同付费路径沿用原请求 Work。`PreparedEvents::prepare` 按实际到达的批次、phase 和
query 收取遍历费用，浅容器扩容在分配和移动前付费；Frame 与 calendar 的深复制仍各自预付。
`RootTime::refine_with_work` 先检验原发现盒包含真实根，再复用已付费 enclosure 并取交集。
通用 enclosure 使用原最近值转换、精确有理比较及相邻浮点端点，最后重新检验两端包含；
数学上的未知结果与付费耗尽错误仍分别返回，不用新额度或较宽的盒换取通过。

[采样合同](../../tests/test_original_source_consumers.py)以四分之一周期和线性边沿计算独立答案，
检查顺序极值与比值、物理供电、输入顺序及非法隐藏依赖。
`transient_analytic_tests` 的非空 Transition 控制检查真实误差传播，
并在原请求额度耗尽后比较同一 Controller 的状态、历史、日历和输出。
这些合同与原093完整 checker 分开记录；原074的物理 cross 与 sqrt 组合、
原364的解析输入和 LO 历史乘积仍有独立的准入及证明缺口。
