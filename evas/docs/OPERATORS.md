# 有历史的波形算子

能力 ID：TRANSITION、ABSDELAY、SLEW、COMPOSE。本基线 EVAS 0.6.1 / IR v6 集成 PR13–15 的限定 transition、absdelay、slew；源码身份与支持边界分别记录。
实现/证据/审阅状态及固定提交见[能力总表](CAPABILITIES.md)。独立需求、手算样例与 Fraction 核对器
由[定时算子契约](../validation/TIMED_OPERATOR_CONTRACTS.md)维护，不以实现生成的波形替代标准答案。

## 公共执行方法

PR13 引入实例与源码调用点身份，算子历史与用户状态分开保存。设 q 为离散状态、H 为已接受历史，
先求算子值 `z(t;q,H)`，再将它代入限定仿射电压方程 `A v=b(u,q,z)`。
当前范围避免算子值隐式依赖本次待求电压；不因此推广到任意反馈或非线性瞬态。

到期目标、边沿端点及追赶交点属于语义断点，输出网格不定义历史。PR13 同步 PR12 后，
在 te 复制历史并推进到期目标，取得当刻算子输出 z_e。显式正边沿使输出在目标变化处连续，
所以同刻可固定 z_e，求解 `q+=Phi(q-,v+)` 与 `F(v+,q+,z_e,u(te))=0`。
代入消去 q+ 后解仿射系统，再回放原赋值、电压残差和状态/电压前向误差认证。
认证矩阵将 z_e 作为参数，复用系数时每次带入新值及其历史区间，不能缓存某次的输出样本。
随后用 q+ 安装新目标，并核对当刻算子值未变；期限顺序通过后，状态、电压、历史、游标、记录一起提交。
失败/弃步只丢弃候选。0.6.1 将算子历史和已采样状态的误差区间传入同刻认证，
参考对象固定为已编译 binary64 IR、实际接受的源事件时刻及驱动输入样本；
不包含源事件相对理想名义时刻的偏差，也不是连续时间全轨迹的精度证明。
共同事件顺序及未决兼容性见[事件手册](EVENTS.md#timer-与同刻兼容性)。

实现入口：[operators.rs](../rust_core/src/operators.rs)、[transient.rs](../rust_core/src/transient.rs)、
[settlement.rs](../rust_core/src/settlement.rs) 与 [settlement_bounds.rs](../rust_core/src/settlement_bounds.rs)。
IR v6 增加 operators 与调用点引用。结构依赖在数值绑定前检查，零乘数、相消、下溢和跨实例连接
不能隐藏不支持的反馈/guard。当前重绑算子值的路径没有新的矩阵分解复用性能结论。

## transition

首批接受本实例已提交标量状态与常数的仿射输入，固定 `d≥0`、显式 `tr>0,tf>0`。
初值为已初始化输入，不凭空添加从零开始的边沿。未中断变化在实际接受时刻 te 发生，
选择完整上/下沿时间 D，则

`y(t)=y0+(y1-y0)*clip((t-te-d)/D,0,1)`。

线性边沿的 10%–90% 时间是 `0.8D`。中断时保存历史起点 o、旧目标 p 和当前值 yc。
同向继续保留 o，反向使用 p；令新历史起点为 on、新目标为 q，则
`m=(q-on)/D`，从 yc 连续前进，终点为 `tc+(q-yc)/m`。下降过程采用反射规则。
输入未变不重启；目标可证明等于当前值则结束边沿。固定延迟队列保存每次待生效目标，保留短脉冲。

数值方法用向外舍入区间包围斜率、剩余时间和期限，代表时间取期限上界；位移须不超过声明时间的1%。
这是 EVAS 的当前分辨率准入限制，不是规范规定或总波形误差保证。不能证明期限顺序或目标方向时拒绝；
端点求值裁剪在起点与目标之间。若观察点落入延迟生效区间，取旧边沿与已生效候选边沿的包围区间并验收电压预算。期限检查在帧/记录提交前完成。

实现：[transition.rs](../rust_core/src/transition.rs)。
验证：[test_transition.py](../tests/test_transition.py)
包含 TR-EDGE/REVERSE/EXTEND/REPEAT/QUEUE、反射、实例隔离、网格与步长、浮点分辨率及拒绝边界。
Rust 另检查队列/边沿的候选回退；新增同刻电压目标与变化算子值上的缓存回归。
专属 Spectre 有限对照见[执行记录](../../experiments/dvs2-spectre-validation/README.md#pr13-transition-061)，不由有限样例宣称通用兼容。
连续电压输入、嵌套、动态参数、缺省/零边沿和算子反馈尚未支持。

### 历史误差与电压精度

0.6.0 只认证把已舍入算子输出当成精确右端项后的方程。残差为零不能证明历史准确：
源事件发生在 `te=1e12 s`、`d=0.10005 s`、边沿 1 s 时，`te+0.5` 的输出误差约
`1.6973e-4 V`，旧版仍可在 `vabstol=1e-9` 下接受。

0.6.1 同时保存代表值与向外舍入区间：延迟生效时刻 `T=[te]+[d]`、边沿起点 Y、
历史起点 O、目标 Q、斜率 `M=(Q-O)/[D]`。在上升段，实数参考值包在
`max(Y,min(Q,Y+M*([t]-T)))` 的区间扩展内；下降段使用相反方向的裁剪。
中断时用旧波形在 T 上的区间作为新 Y，目标队列与边沿结束后继续保留 Q 的区间。
因此代表时间取上界引入的位移不会在下一段被当成零误差。

同刻系统的区间系数映射再将历史和旧状态区间传到所有电压及新状态，
验收 `sup(|v_hat-V|) <= vabstol + reltol*|v_hat|`，右侧采用保守下界。
这同时计入电压网络的放大/消去效应。采样后的 real 状态保存区间供后续事件使用，
其预算只有相对项；integer 必须精确。不含算子且不含事件体条件的模型仍沿用原条件性事件认证。
初始化电压也验收；失败返回 `waveform_accuracy`，不提交状态、历史或输出记录。
不能证明事件次序/方向或同一舍入目标确实未变时返回 `event_resolution`。

这是一种保守验收：没有自动提高运算精度或放宽阈值，区间相关性丢失可能拒绝实际误差很小的模型。
收紧容差通常不增加输出点或 Newton 次数，而可能使当前算法无法通过认证；区间传播本身增加运算和存储。
保证仅限成功接受的计算点及上述固定参考，不含源代码到 IR 的常量舍入、驱动 PWL 求值误差、
名义事件相位或物理模型误差。0.8.0 分支中，含事件体条件的程序另把直接 PWL 求值包围
传入状态/电压认证；没有算子时也保留历史状态误差，范围见[事件条件说明](EVENTS.md#event-conditions)。
不能用此结果宣称与 Spectre 的 reltol/LTE 控制完全相同。
独立 Fraction 回归见 [test_transition_accuracy.py](../tests/test_transition_accuracy.py)：
大时间延迟、延迟生效区间内采样、网络放大、连续中断、跨事件状态误差及初始仿射系数。

### 中断边沿的手算与实现

以时间单位 U 为例，2U 时目标从 0 改为 1，tr=10U；6U 时当前值为 0.4。
若目标改为 0，旧目标 1 成为新历史起点，tf=20U：斜率为 -1/(20U)，
再走 8U 到达 0，即终点 14U。若目标改为 2，则保留历史起点 0：斜率为 2/(10U)，
同样在 14U 到达 2。不能把剩余边沿一律重设为完整 tr/tf，也不能从旧目标处跳变。

`Transition` 分开保存延迟目标队列、当前实际起点/值、历史起点、目标、斜率及结束期限。
`advance` 处理到期目标，`target` 决定上述中断几何，`value` 仅查询波形；采样不写历史。
Rust 的候选帧克隆历史，所以求解器重试不会产生重复排队；多个调用点和实例各有自己的记录。

### 与其他实现的比较

- **规范**：[LRM 2.4 §4.5.8](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
  给出分段线性、纯延迟与中断语义；[LRM 2023 §4.5.8，图4-7至4-12](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf)
  进一步展开上升/下降及连续中断的起点和斜率公式。本实现选择固定参数、事件保持输入这个子集。
- **Spectre**：闭源内核无法据波形推断内部算法；本轮使用相同 VA 与冻结独立折线答案，
  对照普通边沿、反向/同向中断及下降反射、短脉冲、重复目标和同刻目标。
  具体版本、两档设置及差异写入执行记录，不把波形吻合等同于实现一致。
- **Gnucap**：检查固定提交 `100e7469fa2f758b4de0492ec1374266820cbfcd` 的
  [transition 代码生成](https://github.com/gnucap/gnucap-modelgen-verilog/blob/100e7469fa2f758b4de0492ec1374266820cbfcd/mgvams/mg_filt_transition.cc)
  与[运行设备](https://github.com/gnucap/gnucap-modelgen-verilog/blob/100e7469fa2f758b4de0492ec1374266820cbfcd/mgsim/d_va_absdelay.cc)。
  它生成滤波器设备，`tr_accept` 在输入变化时登记波形历史并请求断点，`tr_advance` 查询历史值；
  最小边沿受 dtmin 约束。EVAS 使用显式正边沿及区间分辨率准入，候选历史随整帧提交。
  这里是源码结构比较，没有执行 Gnucap 对照或评定其数值优劣。
- **ngspice + OpenVAF**：[OpenVAF 支持说明](https://openvaf.semimod.de/docs/details/verilog-a-standard/)
  仍列出一般模拟事件控制缺口；因此本轮 timer 驱动的同一 VA 套件不能据该接口直接称为可比。
  这不等于 ngspice 没有断点、行为源或其他实现路线；没有执行其 transition 测试，也不作性能排名。

## absdelay

固定正延迟 τ 的输出为 `y(t)=u(max(t-τ,0))`，其中 u 是直接驱动连续 PWL 的仿射组合。
初始历史保持 u(0)。τ=0 的恒等行为是显式 EVAS 扩展，不能声称由 LRM 的正延迟要求证明。

实现共享不可变的输入语义段，以平移后的拐点要求求解，在原输入历史上查询 `t-τ`。
查询时间使用补偿减法保留低位，按原始拐点排序并作局部插值，避免大时间减法先舍入而错选位置。
例如 t=2^54+4、τ=3，在从 2^54 到 2^54+4 的 0→1 斜坡上，数学答案为1/4；
先舍入 t-τ 可错误得到0。输出采样网格不能作为历史存储。

实现：[absdelay.rs](../rust_core/src/absdelay.rs)。
验证：[test_absdelay.py](../tests/test_absdelay.py)
覆盖非零初值、零/长延迟、大时间低位、双实例、网格/步长及结构拒绝。
修复后基于 PR13 `9850450`，延迟输出同时返回值和历史区间。源语义拐点并集上的端点 A、B
包括原始 binary64 PWL 插值与编译后仿射系数的运算区间。若补偿查询为 q_hi+q_lo，段为 [s,e]，
则局部比例 `F=([q_hi]-[s]+[q_lo])/([e]-[s])`，历史值包含在 `(1-F)A+FB` 中。
查询扩展用于精确选择源段，不能先把 q_hi+q_lo 合成一个舍入后的绝对时间。
同刻认证把此区间传过电压网络和后续状态采样，超出预算返回 `waveform_accuracy`。

[test_absdelay_accuracy.py](../tests/test_absdelay_accuracy.py) 用 Fraction 独立检验正延迟、
初始仿射运算、其他源增加拐点后的插值、网络增益、同刻采样和跨事件误差保留。
例如 0→1、时长3的输入在延迟1之后的 t=2 为1/3；乘以2^30后的 binary64 误差大于1e-10，
旧版可在零支路残差下接受，修复后1e-10预算拒绝、1e-6预算接受并核对真实误差。
这是成功计算点相对编译后 IR 与原始 binary64 源定义的保守认证；不含源代码常量折叠、
允许的事件时间偏移或连续时间全轨迹资格。区间依赖性可能带来保守拒绝。
不可表示或非有限的移位拐点显式失败。[固定检查点专项](../../experiments/pr14-pr15-validation/RESULTS.md)中，PR14 完整前端与内核、Spectre 各 12/12 满足有限观测目标。
内部节点/状态输入、嵌套、跳变、动态延迟/maxdelay 和反馈尚未支持。

## idt

能力 ID：DYNAMICS。main 的 EVAS 0.7.0 / IR v7 支持首版受限二参数积分；
`feat/evas-idt-reset` 分支在 IR v11 上扩展三参数 reset，交付状态见能力总表。
依据 [Verilog-AMS LRM 2023 §4.5.4，表 4-18](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf)，
显式初值形式满足 `z(t)=ic+∫₀ᵗ u(s)ds`。本版只接受贡献表达式中的
`idt(direct_affine_input, constant_ic)` 与分支限定的
`idt(direct_affine_input, constant_ic, state_reset)`：输入为直接驱动、连续 PWL 的仿射组合，
初值为显式有限实例常量，仿真起点为 0。reset 必须是同实例状态和常数的仿射表达式，
且每次事件后能用状态区间证明为零或非零。若输入单位为 U，积分和初值单位为 U·s；
电压贡献中的比例系数由模型提供。参数绑定后每个展开实例的调用点有独立 operator 索引，
多个调用点即使贡献同一支路也不共享初值或历史。

### 分段解析答案与误差参考

源语义拐点的并集将输入分为仿射段。在 `[t₀,t₁]` 上令 `d=t₁-t₀`、
端点输入为 a、b、`h=t-t₀`，则

`z(t₀+h)=z₀+a·h+(b-a)·h²/(2d)`，
`z(t₁)=z₀+(a+b)·d/2`。

首个 z₀ 为 ic，以完整源段积分递推其后端点。查询使用等价的局部式
`z₀+h·((1-h/(2d))·a+(h/(2d))·b)`，不先计算绝对时间平方或全局多项式截距，
也不先形成可能溢出的斜率。语义断点相邻的大绝对时刻仍保留局部时间差。
这消除了 PWL 输入的积分截断误差，**没有**消除浮点运算误差。

验收参考为编译后 binary64 IR 系数与原始 binary64 PWL 点在实数算术下的上述积分。
三参数形式按 LRM 2.4/2023 §4.5.4 的 reset 语义：reset 非零时输出保持 IC；
reset 归零后，从最后一次 reset 断言时刻重新以 IC 为初值积分。
代表值使用调度器接受的事件代表时间；历史区间另保存事件时间包围区间，并在 release 后把
`∫_release^t u(s)ds` 的 release-time 不确定性传入电压预算。
每个端点输入区间包含原始源插值及仿射运算误差；累计端点积分区间保留所有先前段的
不确定性。局部时间差、比例、积分和累加均用向外舍入区间计算。
输出区间作为现有同刻方程的参数，经电压网络及事件采样的增益传递后验收
`sup(|v_hat-V|) <= vabstol+reltol·|v_hat|`，预算取保守下界。
状态沿用现有 real 相对预算、integer 精确预算。零残差不能代替此历史验收。
非有限积分/区间或无法证明预算时拒绝，不自动放宽容差。
原始十进制源码到 binary64 IR 的常量舍入、名义事件时间偏差、非积分的直接驱动样本误差
和连续时间全轨迹证明不在此证书内；保守区间依赖性可能拒绝真实误差很小的模型。

独立答案先固定如下（有理数输入，用于开发验收，不是新增矩阵条件）：

| 输入 / 初值 | 独立答案 |
| --- | --- |
| u=3，ic=-2 | z=-2+3t |
| u=-2+3t，ic=5 | z=5-2t+3t²/2 |
| u=2-t，ic=-1 | z=-1+2t-t²/2 |
| 点 (0,0),(2,4),(5,-2),(8,-2)，ic=3 | t≤2：3+t²；2≤t≤5：7+4h-h²，h=t-2；t≥5：10-2(t-5) |
| u=t/3，ic=0 | z=t²/6；乘 2³⁰ 后 t=1 的误差须由网络预算检出 |
| T=2⁵⁴，t≤T 时 u=0，其后 (T,0),(T+8,4)，ic=1 | z(T+h)=1+h²/4 |

### 生命周期、组合与拒绝边界

完整 PWL 定义在一次请求中不可变；源段与前缀积分构成不可变解析历史，由候选 Frame
克隆共享。它是输入定义的解析表示，不是提前提交未来求解结果。每次试算从已接受帧取得
该表示，查询当刻值/区间后重解统一方程；全部验收通过才替换帧、游标和记录。
查询任意先后顺序不写历史，放弃候选或失败后重试不产生重复积分，输出点和 max_step
不定义积分段。首版不添加新的可变积分状态或按时间缓存的算子样本。

同一时刻修正源输入须重建该请求的语义输入和积分表示并重新求解；相同时间不是缓存身份。
当前公开 API 接受完整源轨迹，没有运行中局部修改 PWL 的接口。事件可采样积分节点，
同刻多个事件仍按现有联立契约执行，后续状态保留积分误差区间。

拒绝缺省 IC、额外参数、输入侧内部节点或状态、reset 中的电压/算子依赖、无法认证为零/非零的 reset、
积分反馈、嵌套、输入非线性、
算子与变量的乘积、静态 solve 入口和算子驱动的 cross（含跨实例传递、零乘数、相消）。
结构依赖检查先于数值简化。积分输出为分段二次，不能交给现有只接受仿射 PWL 的根定位器。
独立的源驱动 cross 和固定 timer 可与积分贡献共存；它们不修改积分输入或 IC。

IR v7 新增 `kind=idt,input,ic,origin`；reset 分支的 IR v11 在 idt 记录中加入可空 `reset` 表达式。
调用引用仍为 `op=operator,operator=index`。
Python/Rust 版本同步，旧版本先于载荷解码拒绝，须从 VA 重新编译；缺字段、额外字段、
错误类型、无效引用/归属和不支持的依赖不可绕过原始 IR 校验。包版本为 0.7.0；包内版本号不代表已发布 tag。
实现入口：[idt.rs](../rust_core/src/idt.rs)、[operators.rs](../rust_core/src/operators.rs)；
独立有理数和组合回归：[test_idt.py](../tests/test_idt.py)、
[test_idt_accuracy.py](../tests/test_idt_accuracy.py)。Rust 另检验查询无副作用及真实候选失败后完整性。
reset 分支新增同刻 post-reset 重解、transition 组合、事件时间区间和弃候选回归；未执行新的远程后端对照。

原开发检查点 `074cde5` 基于 main `5b090571c7de7c6ec08a05c803479505c5d745ee`：
全量 Python 215 项、Rust 40 项通过，其中新增 20 项 Python、7 项 Rust；
649 个原始 binary64 输入的 Fraction 答案均落入实际 Rust 积分区间，包含累计段、尺度变化和次正规数。
[可执行示例](../examples/idt.json)在 0/1/2/3/4 μs 的名义答案为
0.25/0.40/0.45/0.40/0.25 V，属于两参数直接积分开发例。
reset 分支合入多事件写状态依赖后，对原 `d1-free` 与 `d1-reset` 源码执行 targeted EVAS smoke：
base/fine 两档各 4,001/40,001 个观测点均满足原 checker 的 finite-observation 判据，
`d1-reset` 的共同 witness 为 reset x≈1.50002、release x=2.5，最大电压/flag 误差约
1.2e-16。此检查只覆盖 D1 两个条件的本地 EVAS 执行；原矩阵每档分母仍为 31，
其他 29 条件、远程 Spectre 和完整后端矩阵未在本分支重跑；本次证据为本地命令输出，尚未整理成矩阵收据。

0.7.0 整合 PR18 后重新执行完整 Python 218 项、Rust 42 项及独立数学 9 项，均通过。
新增的[私有积分恢复测试](../rust_core/src/transient_idt_tests.rs)由 `transient.rs` 的 test-only 模块加载，
在非零接受时刻核对多实例/调用点失败、弃步、较早重试和未来输入修正；运行时算法未因这次补测修改。
返回的事件批次记录可核对，`run` 循环持有的完整调度游标/已提交 trace 不在此私有入口内，
其失败后的继续执行仍未验证；当前公开请求也没有在线改源或恢复执行接口。

## laplace_nd

能力 ID：DYNAMICS + LANG。本分支新增受限 `laplace_nd`：只接受
`laplace_nd(u, '{b0}, '{d0,d1})`，其中数组是 Verilog-A 标准的前导撇号常量数组，
系数按升幂顺序解释。`d0,d1` 必须为有限正数，`b0` 为有限常数；输入 `u` 必须是直接驱动
连续 PWL 电压和常数的仿射组合。高阶系数、动态系数、非标准 `{...}` 数组、内部节点/状态输入、
嵌套、反馈及算子驱动 `cross` 均明确拒绝，不能截断额外极点后继续执行。

令 `tau=d1/d0`、`gain=b0/d0`，本版求解：

`tau*y'(t)+y(t)=gain*u(t)`。

初始值取仿真起点的 DC 平衡 `y(0)=gain*u(0)`，不从 0 强行启动。对非零常量输入，
输出从第一点起就是对应 DC 值；这也是组合测试检查的显式契约。
在单个 PWL 段上，若端点输入为 `u0,u1`、段长为 `D`、局部时间为 `h`、段起点输出为 `y0`，
则实现使用

`y=e*y0 + gain*((1-e-q)*u0 + q*u1)`，

其中 `e=exp(-h/tau)`、`q=(h-tau*(1-e))/D`。代表值用 `expm1` 和小量级数避免消减。
验收区间改用 `g=1-exp(-x)`、`b=x-g` 的形式：

`y=y0+(gain*u0-y0)*g+gain*m*tau*b`。

证书路径不把已经算出的 f64 `gain/tau/h/D` 重新定义为精确量：`b0/d0`、`d1/d0`
由原始 binary64 系数做外向区间除法，`h=query-start`、`D=end-start` 由 binary64 时间点做外向区间相减。
对区间 `x=h/tau>=0`，实现先二分到 `r<=1/16`，用 `g(r)` 与 `b(r)` 的交错级数加显式下一项余量包围，
再通过 `g(2r)=g(r)*(2-g(r))`、`b(2r)=2*b(r)+g(r)^2` 恢复；`x>=1024` 时用
`exp(-x)<2^-1022` 的粗尾界。历史由源语义拐点递推，输出采样与 `max_step`
不写历史；候选帧克隆该不可变解析历史，所以失败或弃步不会改变已接受状态。

实现入口：[laplace.rs](../rust_core/src/laplace.rs)、[operators.rs](../rust_core/src/operators.rs)。
独立契约与回归见 [LAPLACE_CONTRACTS.md](../validation/LAPLACE_CONTRACTS.md) 和
[test_laplace.py](../tests/test_laplace.py)。回归用 `Decimal` 重新计算解析答案，覆盖标准数组、
DC 初始化、阶跃/斜坡/拐点、小/普通/大指数权重、小时间尺度、非精确原始系数除法、
长绝对时间差放大、实例隔离、网格/步长不变性、历史误差经电压网络放大后的过严预算拒绝及 raw IR 拒绝。

当前误差区间复用直接 PWL 输入包围，并用原始系数/时间点外向算术和上述级数/倍角权重包围滤波历史，
再传入现有电压验收。这仍只证明成功计算点相对编译后 IR 和 binary64 PWL 源的预算；不能据此宣称连续时间全轨迹资格
或 Spectre LTE 控制等价。

## idtmod 与 sin

分支限定实现新增相位子集：`idtmod(u, ic, modulus, offset)` 与 `sin(x)`，用于 D2 类
电压域相位模型。依据 Verilog-AMS LRM 2.4 的 `idtmod(expr, ic, modulus, offset)`
形式，当前只接受显式有限常量初值、显式正有限 modulus 和有限 offset；省略 modulus 的
无界积分形式不映射到本算子，仍应使用普通 `idt` 或明确拒绝。

`idtmod` 的输入沿用 `idt` 首版边界：直接驱动、连续 PWL 的仿射组合，不接受内部节点、
状态、反馈、嵌套或动态参数。实现先用 [idt](#idt) 的解析积分得到未包裹相位
`z(t)=ic+∫u(s)ds`，再返回

`phase(t)=offset + (z(t)-offset) mod modulus`，

范围为半开区间 `[offset, offset+modulus)`。负频率用 `rem_euclid` 语义处理，因此
`ic=1/8,u=-1/4,modulus=1,offset=0` 在 `t=1` 得到 `7/8`。每个调用点和实例仍有独立历史；
查询、输出网格和失败候选不写历史。

`sin` 在本分支是函数型 operator，不引入通用非线性瞬态方程。接受两类输入：
直接驱动 PWL 仿射表达式，或 `constant + coefficient * earlier_operator`。后一类覆盖
``sin(2*`M_PI*phase)``。`phase` 若来自 `idtmod`，误差界使用 wrapped phase 的保守区间；
不会把 binary64 系数 `2*`M_PI` 当成精确实数周期来抵消整圈误差。其他状态输入、内部节点输入、
operator 前向引用、多个 operator 混合、算子驱动 cross 和 operator 乘 voltage/state 仍拒绝。

wrapped 相位本身是不连续输出。严格区间若横跨 wrap 点，只给出整个 `[offset,offset+modulus]`
保守范围；只有通过 outward interval arithmetic 证明 raw phase 落在同一个 turn 内，才返回窄 wrapped 界。
大不确定度、真实跨越和不可精确表示的巨大 turn 会返回整周期或在 bounds 层触发
`waveform_accuracy`。这会在严格电压预算下拒绝不确定 wrap 边界；这是 soundness 约束，
不是连续时间 wrap 轨迹资格。

前端为 D2 暂时接受普通 analog 中每个 `real` 变量一次无条件赋值作为表达式别名，
例如 ``phase = idtmod(...); V(out)<+sin(2*`M_PI*phase);``。别名不创建状态，也不提供通用顺序
程序语义；条件赋值、重复赋值和依赖选择应由后续 LANG 分支统一接管。`constants.vams`
当前只解析窄集合中的 `` `M_PI``，不会执行 include 文件或引入任意宏系统。

验证入口：[test_phase.py](../tests/test_phase.py) 固定常频、chirp、负频率、直接 `sin`、
Decimal 高精度正弦对照、拒绝边界和 raw IR 畸形字段。分支本地用冻结原矩阵输入重跑
`d2-constant` 与 `d2-chirp` 两档 EVAS worker，并用独立 checker 复核：四个配置均为
`observations_within_targets`；overstrict wrap 边界端到端回归会返回 `waveform_accuracy`。
accumulated/wrapped 最大解析误差不超过 `1.8e-15`，
vout 最大解析误差不超过 `9e-15`。该证据是本地分支证据，formal qualification 仍为 I，
未执行 Spectre 或完整 31 条件矩阵。

## slew

首批输入为直接驱动连续 PWL 的仿射组合，固定正限速 r+ 和负限速 r-，初态 y(0)=u(0)。
在输入斜率 a 恒定的分段上：y<u 时以 r+ 追赶，y>u 时以 r- 追赶，y=u 时选择
`clip(a,r-,r+)`；相交后重新判断跟踪或追赶模式。
对于当前输出斜率 s，候选相交时刻为 `tc=t0+(u0-y0)/(s-a)`，只有分母、方向与段内次序可认证才采用。
这给出分段解析轨迹，无需按输出网格做数值积分。

平台期间落后的输出继续追赶；输入反向后，只要仍处于同侧，输出继续原方向直到真正相交。
实现用区间运算认证模式与交点次序，语义段/断点通过 Arc 共享；不确定或不可表示时失败。
交点仅用于调度时才转换成绝对时间；历史保存输入段起点 t0 与局部偏移 δ。
反向后的输出使用 `y(t)=u0+a*δ+r_new*((t-t0)-δ)`，避免先计算 `t0+δ` 丢失低位，
再用错误的输入值重置斜坡。反例：T=2^54，输入 (T,0)、(T+32,4)、(T+64,-4)，
r+=1/16、r-=-1/8，交点为 T+192/5；T+40 的正确输出2.2，旧版错误得到2.0。
零起点与乘2^-40的时间尺度也纳入同一个独立回归。

输入端点、局部交点、输出起点和最终保持值同时保存区间；查询落入交点区间时取相邻模式的包围。
局部表示改善代表值，区间则包围原始 binary64 PWL 和编译后 IR 的实数解，并传入 PR13 的
同刻电压/状态预算。网络增益、相消和后续采样不能把已有误差清零。
不能证明模式或交点次序时仍拒绝；几何成立但电压预算不足时返回 `waveform_accuracy`。
[test_slew_accuracy.py](../tests/test_slew_accuracy.py) 检查反向追赶误差放大、初值/输入重采样、
同刻电压读取与跨事件误差保留。成功计算点的保守验收不构成整个电路的连续时间误差保证，
也不包含编译前常量舍入或允许的源事件时间偏移；保守区间可能拒绝实际误差较小的输入。

实现：[slew.rs](../rust_core/src/slew.rs)。
验证：[test_slew.py](../tests/test_slew.py)
包括独立 SL-CATCH/REVERSE/PASS、反射、SI/二进制尺度、实例与网格变化。
[联合回归](../tests/test_timed_composition.py)另外检查双实例的三算子与 timer/cross 同刻采样，
独立公式覆盖两种实例顺序、两种网格和两种步长，共8配置；该结果绑定 PR15 被测实现 `e01fb5b`。
[专项对照及步长诊断](../../experiments/pr14-pr15-validation/RESULTS.md)中，EVAS 16/16、Spectre 10/16 达到固定有限观测目标。
Spectre 的反向追赶偏差随步长细化下降；这是波形证据，不是私有算法或 LRM 违规的结论。
内部节点/状态输入、嵌套、动态/缺省限速、跳变和反馈尚未支持。

## 来源与证据限制

语义依据为 [Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
§4.5.7–4.5.9；范围收窄、分辨率门限及上述数据结构属于 EVAS 的选择。公式是对限定输入的推导，
规范、EVAS 约定、后端观察三者有分歧时必须显式保留。共同历史与观察预算见
[验证协议](../validation/METHOD_QUALIFICATION.md)，本地方法数不是正式条件数。
原数学样例已经用于开发；新增修复验证不得称其为未见确认集。
