# 有历史的波形算子

适用范围：当前 IR18 的直接输入基础算子路径。能力 ID 为 TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE；
支持与缺口见[四后端支持范围](../COMPARISON.md)。独立需求和手算答案由 validation 的专项契约维护。

积分反馈、联合复位、高阶滤波及内部节点/算子输入的 `ddt` 由[连续动态章节](continuous.md)维护。
本页的直接输入限制不自动推广到联合网络。需要历史的算子按实例与调用点保存历史；
局部变量只接收结果，sin 这类纯函数不新增物理历史。

<a id="operator-map"></a>

## 按算子查找

| 数学章节 | 直接输入实现 | 独立回归 | 联合路径 |
| --- | --- | --- | --- |
| [transition](#transition) | [transition.rs](../../rust_core/src/transition.rs) | [边沿与队列](../../tests/test_transition.py)、[历史精度](../../tests/test_transition_accuracy.py) | 事件目标安装与[共同观察](continuous.md#lifecycle-observation-review-fixes) |
| [absdelay](#absdelay) | [absdelay.rs](../../rust_core/src/absdelay.rs) | [延迟查询](../../tests/test_absdelay.py)、[精度](../../tests/test_absdelay_accuracy.py) | 分支候选支持内部仿射电压投影；非点事件观察明确拒绝 |
| [idt](#idt) | [idt.rs](../../rust_core/src/idt.rs) | [积分与复位](../../tests/test_idt.py)、[精度](../../tests/test_idt_accuracy.py) | [积分反馈](continuous.md#电压关系与积分反馈)、[联合复位](continuous.md#事件修改的联合积分与复位) |
| [laplace_nd](#laplace_nd) | [laplace.rs](../../rust_core/src/laplace.rs) | [一阶低通](../../tests/test_laplace.py) | [完整状态空间](continuous.md#高阶滤波的完整状态空间)、[混合网络](continuous.md#多项式积分与滤波的混合网络) |
| [laplace_np](#laplace_np) | [编译转换](../../src/evas/instance_compiler.py)，复用 laplace_nd | [实极点与独立答案](../../tests/test_laplace_np.py) | 本批验证直接连续 PWL；不扩大联合依赖范围 |
| [idtmod / sin](#idtmod-与-sin) | [idtmod.rs](../../rust_core/src/idtmod.rs)；sin 在 [operators.rs](../../rust_core/src/operators.rs) | [相位与函数](../../tests/test_phase.py) | 受限 sin 可供[动态 guard](continuous.md#非线性-guard-的根证明)使用；idtmod 的非点事件观察明确拒绝 |
| [slew](#slew) | [slew.rs](../../rust_core/src/slew.rs) | [追赶模式](../../tests/test_slew.py)、[精度](../../tests/test_slew_accuracy.py) | 分支候选支持内部仿射电压投影；非点事件观察明确拒绝 |

这些文件维护单项公式。[operators.rs](../../rust_core/src/operators.rs) 统一检查调用点与依赖，
区分只读查询、同刻观察和未来历史。涉及事件的改动还需检查
[settlement](events.md#同块顺序赋值与同刻联立求解)与[共同生命周期](continuous.md#shared-lifecycle-closure)。

## 公共执行方法

下面固定当刻算子输出的推导适用于正边沿 transition 与直接输入的 absdelay/slew。
idt 复位可能改变当刻输出，须按[积分生命周期](#生命周期组合与拒绝边界)重建并认证候选，不能直接套用输出不变假设。
当前同样允许纯函数 `sin` 随其已许可的早期复位输入改变；函数链的许可逐项传播，
随后仍从同一接受历史重放并核对整个算子值/区间及积分复位历史。
`reset_dependencies.rs` 的结构图包含滤波/相位/正弦输入边，未认证的 reset 固定点反馈环保守拒绝；
已经交付的受限复位采样闭包见[共同生命周期](continuous.md#shared-lifecycle-closure)。

临时 `Evaluation` 借用同一个历史基线并固定查询时间。
同刻候选仍克隆该基线并推进历史；无复位 idt、idtmod、laplace、absdelay、slew
和直接输入 sin 的查询值/区间可复用。复位 idt、transition 以及沿依赖链消费它们的 sin
重新求值。每种 Runtime 必须显式分类，新增算子时编译器要求补充该分类。
这里复用的是该次试算内的查询结果，不跨时间或历史基线缓存；失败候选仍整体丢弃。
原来的同刻权限、第二次求解、历史/值/区间重放一致性检查均保留，不能用复用跳过验收。
`operators.rs` 的独立回归核对复位后正弦、transition 后正弦，以及弃候选后从原基线重试。

算子使用实例与源码调用点身份，历史与用户状态分开保存。设 q 为离散状态、H 为已接受历史，
先求算子值 `z(t;q,H)`，再将它代入限定仿射电压方程 `A v=b(u,q,z)`。
本页直接输入的独立算子路径与连续联合网络分别维护；后者的电压反馈、导数和非线性积分范围见
[连续动态](continuous.md)，不能把其中一条路径的限制推广到所有调用。

到期目标、边沿端点及追赶交点属于语义断点，输出网格不定义历史。
在 te 复制历史并推进到期目标，取得当刻算子输出 z_e。显式正边沿使输出在目标变化处连续，
所以同刻可固定 z_e，求解 `q+=Phi(q-,v+)` 与 `F(v+,q+,z_e,u(te))=0`。
代入消去 q+ 后解仿射系统，再回放原赋值、电压残差和状态/电压前向误差认证。
认证矩阵将 z_e 作为参数，复用系数时每次带入新值及其历史区间，不能缓存某次的输出样本。
随后用 q+ 安装新目标，并核对当刻算子值未变；期限顺序通过后，状态、电压、历史、游标、记录一起提交。
失败/弃步只丢弃候选。算子历史和已采样状态的误差区间传入同刻认证，
参考对象固定为已编译 binary64 IR、实际接受的源事件时刻及驱动输入样本；
不包含源事件相对理想名义时刻的偏差，也不是连续时间全轨迹的精度证明。
共同事件顺序及未决兼容性见[事件手册](events.md#timer-与同刻兼容性)。

实现入口：[operators.rs](../../rust_core/src/operators.rs)、[transient.rs](../../rust_core/src/transient.rs)、
[settlement.rs](../../rust_core/src/settlement.rs) 与 [settlement_bounds.rs](../../rust_core/src/settlement_bounds.rs)。
IR 保存 operators 与调用点引用。结构依赖在数值绑定前检查，零乘数、相消、下溢和跨实例连接
不能隐藏不支持的反馈/guard。当前重绑算子值的路径没有新的矩阵分解复用性能结论。

## transition

接受本实例已提交标量状态与常数的仿射输入；支持三参数 `transition(x,d,tr)` 和四参数 `transition(x,d,tr,tf)`。
延迟和边沿为有限实例常数，`d≥0`、`tr>0,tf>0`。仅省略 fall 且显式 rise 为正时，
按 Verilog-AMS LRM 2.4 §4.5.8 将 `tf=tr`，编译到同一 Transition IR；保留原源位置、实例和调用点。
这不引入零边沿或完全省略边沿的默认最小时间。
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

实现：[transition.rs](../../rust_core/src/transition.rs)。
验证：[test_transition.py](../../tests/test_transition.py)
包含 TR-EDGE/REVERSE/EXTEND/REPEAT/QUEUE、反射、实例隔离、网格与步长、浮点分辨率及拒绝边界。
Rust 另检查队列/边沿的候选回退；新增同刻电压目标与变化算子值上的缓存回归。
专属 Spectre 有限对照见[执行记录](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/dvs2-spectre-validation/README.md#pr13-transition-061)，不由有限样例宣称通用兼容。
三参数独立上/下沿、中断与实例隔离回归见 [test_transition_defaults.py](../../tests/test_transition_defaults.py)。
新增默认 fall 的[同源有限控制](../../../experiments/backends/transition-default-fall/README.md)核对了完整边沿、中断和两个实例。
显式 timer 容差 `1e-12` 控制的实际原生波形满足 `1e-8 V` 预算；原 `1e-18` 参考未产生目标变化而保留失败。
所需观察点缺失、原始状态逐点差以及 callback 窗口/计数证据不足仍保留；不据此宣称一般 timer 或后端全对齐。
连续电压输入、嵌套、动态参数、缺省 rise/零边沿和算子反馈尚未支持。

### 历史误差与电压精度

把已舍入算子输出当成精确右端项，只能认证方程求解。残差为零不能证明历史准确：
源事件发生在 `te=1e12 s`、`d=0.10005 s`、边沿 1 s 时，`te+0.5` 的输出误差约
`1.6973e-4 V`，旧版仍可在 `vabstol=1e-9` 下接受。

当前同时保存代表值与向外舍入区间：延迟生效时刻 `T=[te]+[d]`、边沿起点 Y、
历史起点 O、目标 Q、斜率 `M=(Q-O)/[D]`。在上升段，实数参考值包在
`max(Y,min(Q,Y+M*([t]-T)))` 的区间扩展内；下降段使用相反方向的裁剪。
中断时用旧波形在 T 上的区间作为新 Y，目标队列与边沿结束后继续保留 Q 的区间。
因此代表时间取上界引入的位移不会在下一段被当成零误差。

同刻系统的区间系数映射再将历史和旧状态区间传到所有电压及新状态，
验收 `sup(|v_hat-V|) <= vabstol + reltol*|v_hat|`，右侧采用保守下界。
这同时计入电压网络的放大/消去效应。采样后的 real 状态保存区间供后续事件使用，
其预算只有相对项；integer 必须精确。无算子事件模型另由[事件输入/状态认证](events.md#pwl-与事件的执行契约)验收。
初始化电压也验收；失败返回 `waveform_accuracy`，不提交状态、历史或输出记录。
不能证明事件次序/方向或同一舍入目标确实未变时返回 `event_resolution`。

这是一种保守验收：没有自动提高运算精度或放宽阈值，区间相关性丢失可能拒绝实际误差很小的模型。
收紧容差通常不增加输出点或 Newton 次数，而可能使当前算法无法通过认证；区间传播本身增加运算和存储。
上述历史证书仅针对成功接受的计算点及固定参考，不包含源代码到 IR 的常量舍入、
驱动 PWL 求值误差、名义事件相位或物理模型误差。事件路径另把直接 PWL 求值包围
传入状态/电压认证；没有算子时也保留历史状态误差，范围见[事件条件说明](events.md#event-conditions)。
不能用此结果宣称与 Spectre 的 reltol/LTE 控制完全相同。
独立 Fraction 回归见 [test_transition_accuracy.py](../../tests/test_transition_accuracy.py)：
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
- **Spectre**：闭源内核无法据波形推断内部算法；固定专项实验使用相同 VA 与冻结独立折线答案，
  对照普通边沿、反向/同向中断及下降反射、短脉冲、重复目标和同刻目标。
  具体版本、两档设置及差异写入执行记录，不把波形吻合等同于实现一致。
- **Gnucap**：检查固定提交 `100e7469fa2f758b4de0492ec1374266820cbfcd` 的
  [transition 代码生成](https://github.com/gnucap/gnucap-modelgen-verilog/blob/100e7469fa2f758b4de0492ec1374266820cbfcd/mgvams/mg_filt_transition.cc)
  与[运行设备](https://github.com/gnucap/gnucap-modelgen-verilog/blob/100e7469fa2f758b4de0492ec1374266820cbfcd/mgsim/d_va_absdelay.cc)。
  它生成滤波器设备，`tr_accept` 在输入变化时登记波形历史并请求断点，`tr_advance` 查询历史值；
  最小边沿受 dtmin 约束。EVAS 使用显式正边沿及区间分辨率准入，候选历史随整帧提交。
  这里是源码结构比较，没有执行 Gnucap 对照或评定其数值优劣。
- **ngspice + OpenVAF**：历史专项未执行该组合的 timer 驱动 transition 套件，不能称为已完成同模型对照。
  [OpenVAF 支持说明](https://openvaf.semimod.de/docs/details/verilog-a-standard/)是未固定版本的接口导航，
  不能据该网页推断所有工具版本的能力。
  这不等于 ngspice 没有断点、行为源或其他实现路线；没有执行其 transition 测试，也不作性能排名。

## absdelay

固定正延迟 τ 的输出为 `y(t)=u(max(t-τ,0))`，其中 u 是直接驱动连续 PWL 的仿射组合。
初始历史保持 u(0)。τ=0 的恒等行为是显式 EVAS 扩展，不能声称由 LRM 的正延迟要求证明。
τ 须为有限实例常数；τ 大于 stop 时仍保持初值。

实现共享不可变的输入语义段，以平移后的拐点要求求解，在原输入历史上查询 `t-τ`。
查询时间使用补偿减法保留低位，按原始拐点排序并作局部插值，避免大时间减法先舍入而错选位置。
例如 t=2^54+4、τ=3，在从 2^54 到 2^54+4 的 0→1 斜坡上，数学答案为1/4；
先舍入 t-τ 可错误得到0。输出采样网格不能作为历史存储。

实现：[absdelay.rs](../../rust_core/src/absdelay.rs)。
验证：[test_absdelay.py](../../tests/test_absdelay.py)
覆盖非零初值、零/长延迟、大时间低位、双实例、网格/步长及结构拒绝。
延迟输出同时返回值和历史区间。源语义拐点并集上的端点 A、B
包括原始 binary64 PWL 插值与编译后仿射系数的运算区间。若补偿查询为 q_hi+q_lo，段为 [s,e]，
则局部比例 `F=([q_hi]-[s]+[q_lo])/([e]-[s])`，历史值包含在 `(1-F)A+FB` 中。
查询扩展用于精确选择源段，不能先把 q_hi+q_lo 合成一个舍入后的绝对时间。
同刻认证把此区间传过电压网络和后续状态采样，超出预算返回 `waveform_accuracy`。

[test_absdelay_accuracy.py](../../tests/test_absdelay_accuracy.py) 用 Fraction 独立检验正延迟、
初始仿射运算、其他源增加拐点后的插值、网络增益、同刻采样和跨事件误差保留。
例如 0→1、时长3的输入在延迟1之后的 t=2 为1/3；乘以2^30后的 binary64 误差大于1e-10，
旧版可在零支路残差下接受，修复后1e-10预算拒绝、1e-6预算接受并核对真实误差。
这是成功计算点相对编译后 IR 与原始 binary64 源定义的保守认证；不含源代码常量折叠、
允许的事件时间偏移或连续时间全轨迹资格。区间依赖性可能带来保守拒绝。
不可表示或非有限的移位拐点显式失败。EVAS/Spectre 的固定专项结果与身份见
[执行记录](../../../experiments/archive/pr14-pr15-validation/RESULTS.md)，有限观测达标不证明通用兼容。
本实现允许下述内部仿射电压投影及受限两级固定 delay。状态输入、其他嵌套、跳变、
动态延迟/maxdelay 和经过历史状态的反馈尚未支持；代数电压反馈可在投影前统一求解。

### 两级固定 absdelay 的移位历史包围

分支开发域限于 `absdelay(absdelay(x,d1),d2)`，或同实例、可认证单位增益/零偏置
内部电压别名；第一级 x 为上述外部连续 PWL 投影。两个调用点保留各自身份与参数，
不合并为一个算子。物理答案为 `x(max(t-d1-d2,0))`，这里两个 binary64 参数作为
实数相加；`RN(d1+d2)` 不能替代它。第三层、一般 history 组合、状态/事件输入、
动态参数、absdelay 与 slew 混合嵌套、跨实例内部 history 和经过 history 的反馈继续拒绝。

原输入 knots 为 t_i、真实端点 a_i∈A_i。取认证 Lipschitz 上界
`L >= max magnitude((A_(i+1)-A_i)/(t_(i+1)-t_i))`。
一级真实移位时刻为 s_i=t_i+d1，导出的浮点 knot 为 h_i=RN(t_i+d1)。
用向外区间算术计算 `epsilon_i >= |s_i-h_i|`，并导出原代表值 a_i 与
`B_i=A_i+[-E_i,E_i]`，`E_i >= L*epsilon_i`。d1>0 时显式保留 0→d1 初值 hold。
拒绝非有限界、溢出或塌缩 knots；末端 hold 使用 B_N。

任意名义段内 t=(1-θ)h_i+θh_(i+1)，取 τ=(1-θ)s_i+θs_(i+1)。
真实一级 f 在 τ 处等于原端点的凸插值，且
`|f(t)-f(τ)| <= L|t-τ| <= (1-θ)E_i+θE_(i+1)`。
所以 `(1-θ)B_i+θB_(i+1)` 对**整段每个时间**包围 f(t)，即使真实角点落在名义段内。
这个 tube 不宣称真实曲线是名义 knot 的某个固定顶点选择，不可转用于导数或 guard。
二级查询继续用补偿的 `max(t-d2,0)` 和区间插值，因此上述包围也覆盖二级物理值。

`AbsDelay::shifted_tube` 只给第二级导出这个包围；`operators::history_parent/build_delay`
在原始结构依赖检查之后，通过已有原 IR `node_map` 证明单位别名，并受限递归构造两级，
支持贡献顺序变化。普通 `projected_points` 和其他 history 准入保持原拒绝规则。
两级 slew 使用下方独立的分段历史构造，不复用 absdelay 的移位包围。
值区间经既有 settlement 认证传播至各电压节点，包含外部增益、插值、网络与值舍入误差。
每级 immutable Arc 随真实 Frame clone/discard/retry 保留，观察网格不生成历史。

[test_absdelay_cascade.py](../../tests/test_absdelay_cascade.py) 的独立 Fraction 答案覆盖
初值、两级边界、非二进制参数、直接/内部编码、实例、query refinement 与放大拒绝；
[Rust lifecycle 检查](../../rust_core/src/transient_lifecycle_tests.rs) 运行同 Frame 的失败、
丢弃与较早重试。大时间 A=2^54、d1=d2=3 时，名义角点即使采样真实值也可得到
7/16，而物理答案是1/2；新 tube 保留差异，tight budget 下明确拒绝。
G=2^30、d1=.1、d2=.2、x=t/3 的冻结 1e-10 和 1e-6 预算均拒绝，后者区间过宽，
不能宣称宽预算对照成功。局部检查不新增 Spectre 资格或完整 C3 支持；独立审查尚待完成。

### absdelay 与 slew 的内部电压投影

直接输入保留原路径；内部输入先对原仿射电压关系作区间投影：
`A v = B u + d`，从而 `x = c v + e = c A^(-1) B u + c A^(-1) d + e`。
`operators.rs::projected_points` 使用 `event_accuracy.rs` 与事件共用的原 IR 投影，
不另写节点赋值执行器。结构检查跟随被读取节点的电压关系，拒绝任何离散状态或
历史算子依赖，包括 `0*V(z)`、抵消和下溢形式中的历史反馈。

输入必须是已认证的连续 PWL。每个物理输入断点都保留输入区间及有限代表值；区间
继续进入既有 `AbsDelay::enclosed` / `Slew::enclosed`，输出验收仍考虑误差放大。
查询不改写历史，输出网格不生成输入历史。奇异或无法认证的投影明确拒绝。

独立例 `z=u+.5z` 给出 `z=2u`。令 `u=min(t,2)`，固定延迟 1 的输出为
`2 min(max(t-1,0),2)`；限速 `+1/-2` 的输出为 `min(t,4)`。
[共同模型](../../validation/cases/projected_history/dut.va)与
[开发回归](../../tests/test_history_projection.py)固定这些答案，并检查直接/内部编码、
新增输出点、历史反馈拒绝及小残差不能掩盖投影误差。新样例属于开发集，不改变原
31 条件，也没有新 Spectre 资格结论。

## idt

能力 ID：DYNAMICS。本节说明二参数解析积分与受限三参数 reset；支持状态见能力表。
依据 [Verilog-AMS LRM 2023 §4.5.4，表 4-18](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf)，
显式初值形式满足 `z(t)=ic+∫₀ᵗ u(s)ds`。本节直接 PWL 解析路径只接受贡献表达式中的
`idt(direct_affine_input, constant_ic)` 与受限的
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
reset 归零后，从 reset 保持解除/释放时刻重新以 IC 为初值积分。
代表值按 `IC + (prefix(t) - prefix(release))` 求值，先取前缀差，避免提前相加两份大 IC 产生不必要的溢出；区间采用同样分组。前缀差仍可能有消减和区间依赖性，必须由误差预算验收。
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
不定义积分段。二参数解析路径不添加新的可变积分状态或按时间缓存的算子样本。

同一时刻修正源输入须重建该请求的语义输入和积分表示并重新求解；相同时间不是缓存身份。
当前公开 API 接受完整源轨迹，没有运行中局部修改 PWL 的接口。事件可采样积分节点，
同刻多个事件仍按现有联立契约执行，后续状态保留积分误差区间。

上述是直接 PWL 解析路径的生命周期。内部电压、积分反馈、嵌套、事件保持输入、联合复位、
多项式积分输入和状态独立算子 cross 由[连续网络](continuous.md)处理。
缺省 IC、额外参数、静态 solve、reset 中的电压/算子依赖和未认证 reset 仍拒绝。
结构依赖先于数值相消检查；事件修改历史的 guard 需要重定位，当前尚未接入。

没有获得共同闭包认证的“积分器 → 电压网络 → 事件状态赋值 → 该积分器复位”固定点环仍拒绝。
受限的实际复位后采样的准入与拒绝见[共同闭包](continuous.md#shared-lifecycle-closure)，
不能沿用首版的结构限制将所有复位/采样组合统称不支持。
例如事件后 `q=y`、IC=0、未复位积分值为 1 时无自洽解；`q=1-y` 则有两组自洽解。
数值试算稳定不能证明解存在或唯一。`reset_dependencies.rs` 复用组装后的未知节点连通组，
构建节点、状态和算子之间的结构依赖；覆盖局部状态、内部节点、实例连接及其他算子的中转。
固定驱动和地不会被未知电压反向影响。检查采用全部潜在路径的并集，不用时间互斥、
条件互斥、零乘数或相消消除依赖，因此可能保守拒绝数学上可解的反馈写法。
没有形成复位环的普通积分采样及单向算子采样继续支持；这不是完整 VA 的合法性判定。

同刻二次求解从同一份已接受历史重建候选，不能继承第一次试算的复位/释放操作。
最终重放须保持复位模式、释放代表时刻及其包围区间一致，并核对算子值和区间。
值未改变而历史区间改变时也重新验收电压和事件状态；无法认证则整批拒绝。
精确释放时刻的积分区间为零长度，输出及其包围均为 IC；不确定释放仍保留时间误差。
失败、丢弃或重试不修改已接受状态及历史。


IR 的 idt 记录保存 `kind=idt,input,ic,origin` 及可空 `reset` 表达式。
调用引用为 `op=operator,operator=index`。Python/Rust 同时校验版本、字段、类型、归属和依赖；
旧 IR 须从原始 VA 重新编译，不能只修改版本号，见[迁移规则](../../README.md#ir-v8-migration)。

实现入口与独立回归见上方对应表。Rust 另检查查询无副作用、调用点隔离及候选失败后的历史完整性；
[transient_idt_tests.rs](../../rust_core/src/transient_idt_tests.rs) 在非零接受时刻检查失败、弃步、较早重试和未来输入修正。
该私有入口不覆盖生产控制器的全部游标与 trace；控制器回退另见[共同生命周期](continuous.md#shared-lifecycle-closure)。
[可执行示例](../../validation/smoke/idt.json)的名义输出为 0.25/0.40/0.45/0.40/0.25 V，属于二参数直接积分。

直接积分与复位的旧测试数量、D1 有限观测 witness 和完整矩阵执行分别保留在
[固定历史章节](https://github.com/BucketSran/vaEVAS/blob/1527502c9affb77fec12aac03adba5446f0f241e/evas/docs/OPERATORS.md#idt)、
[D1 收据](../../../experiments/archive/pr14-pr15-validation/results/idt-reset-review.json)及
[复位合并验证](../../../experiments/archive/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)。
这些结果绑定原检查点，不证明精确事件时刻或连续时间全轨迹精度。

## laplace_nd

能力 ID：DYNAMICS + LANG。本节的直接输入解析路径接受
`laplace_nd(u, '{b0}, '{d0,d1})`，其中数组是 Verilog-A 标准的前导撇号常量数组，
系数按升幂顺序解释。`d0,d1` 必须为有限正数，`b0` 为有限常数；输入 `u` 必须是直接驱动
连续 PWL 电压和常数的仿射组合。此路径拒绝动态系数、非标准 `{...}` 数组和超出该解析形式的依赖，不能截断额外极点后继续执行。
单个 `transition` 的前馈输入另见[下节](#transition-filter)。高阶系数、其他内部节点、反馈与动态 cross 的联合范围见[连续动态](continuous.md#行为与边界)。

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

实现入口：[laplace.rs](../../rust_core/src/laplace.rs)、[operators.rs](../../rust_core/src/operators.rs)。
独立契约与回归见 [LAPLACE_CONTRACTS.md](../../validation/LAPLACE_CONTRACTS.md) 和
[test_laplace.py](../../tests/test_laplace.py)。回归用 `Decimal` 重新计算解析答案，覆盖标准数组、
DC 初始化、阶跃/斜坡/拐点、小/普通/大指数权重、小时间尺度、非精确原始系数除法、
长绝对时间差放大、实例隔离、网格/步长不变性、历史误差经电压网络放大后的过严预算拒绝及 raw IR 拒绝。

当前误差区间复用直接 PWL 输入包围，并用原始系数/时间点外向算术和上述级数/倍角权重包围滤波历史，
再传入现有电压验收。这仍只证明成功计算点相对编译后 IR 和 binary64 PWL 源的预算；不能据此宣称连续时间全轨迹资格
或 Spectre LTE 控制等价。

<a id="transition-filter"></a>

### 采样边沿进入一阶滤波

`transition_filter.rs` 接受同实例单个 `transition` 输出及其常数仿射变换，
再进入上述一阶 `laplace_nd`。例如先以事件更新 `q`，再执行：

```verilog
V(edge) <+ transition(q, delay, rise, fall);
V(filtered) <+ laplace_nd(V(edge), '{1}, '{1, tau});
```

投影前先检查结构依赖。额外的直接输入、离散状态、第二个历史算子、跨实例依赖和反馈均不进入此路径，
即使额外依赖乘以零也保留拒绝。过滤后的电压用于 `cross` 或继续进入联合连续网络尚未支持。
这条扩展不改变一阶系数条件，也不把任意级联或高阶网络纳入支持范围。

边沿的每个稳定分段有 `u(h)=u0+m*h`。沿用上一节的 `g,b` 区间权重，计算
`y(h)=y0*(1-g)+gain*u0*g+gain*m*tau*b`，初态仍取 DC 平衡。
传播在延迟激活和边沿结束处分段。时间舍入造成的激活或结束区间内，以输入值包围和正指数核积分，
不把区间两端连成一条假斜坡。状态和目标的不确定度继续传入电压验收，过严预算仍返回 `waveform_accuracy`。

事件到来时，滤波器先保存旧边沿，再在私有候选上试装新目标。
采样、复位和中断边沿不重置滤波状态。只有目标变化或物理边沿截止点能提交滤波历史；
增加输出查询只产生私有预测。已提交帧保留旧滤波和旧边沿快照，供跨越提交点的观察使用。
同刻候选比较完整过去历史，失败候选由外层事务丢弃，不能污染下一次试算。

`transition::advance_at` 接收物理事件窗口 `W=[a,c]` 和执行代表时刻 `b>=c`。
固定延迟激活使用 `W+delay`，边沿起止界继续保留这个区间，不能将 `b` 当作精确的实际发生时刻。
窗口宽度无法满足延迟分辨率、或新旧激活次序无法证明时，仍明确拒绝。

零延迟边沿可能已在 `a` 到 `b` 之间影响滤波器。只沿旧边沿积分到 `b` 会漏掉这段面积。
`ActivationPrefix` 保存旧历史的 `Y(a)`，并用旧、新边沿在 `[a,b]` 的值域并集，经仿射投影得到 `U`。
对窗内任意 `t`，正指数核给出
`Y(t) ⊆ (1-g)*Y(a) + gain*g*U`，其中 `g=1-exp(-(t-a)/tau)`。
`bounds` 与 `range` 在窗内使用这个包围，窗前读取旧快照，窗后从包围终值继续传播。
固定 timer 的精确关系可能证明窗内查询的事件阶段，因此不能只修复 `Y(b)` 而让过去查询仍返回旧积分。
这个窗口也参与历史相等性和候选回退；其下界早于已提交滤波历史时保守拒绝，尚未实现任意重叠窗口的有序传播。

宽事件容差不保证严格输出精度。宽根窗口经过边沿和滤波放大后，若超过 `vabstol/reltol` 预算，
请求返回 `waveform_accuracy`。本分支新增[受限自动根细化](events.md#voltage-demand-root-refinement)：
输入驱动的孤立非线性根可在候选电压验收失败后细化，再重新验收。
[单次采样链](events.md#filter-root-budget)另将采样与边沿时间的灵敏度传到滤波输出，
由最紧消费者提出提前停止目标；一般历史仍沿用原策略。
未覆盖的历史根、复杂事件簇及后续预算失败仍明确拒绝；用户也可收紧 `cross` 容差后重新申请。
这些包围相对于 EVAS 物理事件契约成立，不等于复现 Spectre 的数值回调时刻。
实际 `$abstime` 探针已显示 Spectre 个别 timer 回调随下游动态和 strobe 设置变化；
精确跳变侧验收仍失败，见[边界诊断](../../../experiments/backends/sample-edge-filter/BOUNDARY.md)。

实现见 [transition_filter.rs](../../rust_core/src/transition_filter.rs)，生命周期入口在
[operators.rs](../../rust_core/src/operators.rs)。[公开回归](../../tests/test_sample_edge_filter.py)检查 DC、
中断、复位、实例隔离、贡献顺序、查询不变性和拒绝边界；Rust 测试另查不确定激活包围及失败候选回退。
实际容差对照和保持节点边界差值见[实验报告](../../../experiments/backends/sample-edge-filter/README.md)。

## laplace_np

能力 ID：LANG + DYNAMICS。本批接受
`laplace_np(u, '{b0}, '{p,0})`：一个有限、实例常量的分子系数 `b0`，
一个有限负实极点 `p`，虚部为零，省略 epsilon，且 `-1/p` 可精确表示为有限正 binary64。
系数须使用标准常量数组；零、正、复数或多个极点、动态系数、多项分子、
非精确倒数及显式 epsilon 均明确拒绝。有限 `b0` 可为零或负数，
但零分子不会取消对极点、转换精度或输入依赖的检查。

依据 [Verilog-AMS LRM 2.4 §4.5.11.3](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf#page=92)，
单个实极点的传递关系是 `H(s)=b0/(1-s/p)`。编译器保持分子不变，
转换为升幂分母 `[1,-1/p]`。不能改为 `[−p,1]`，否则 DC 增益会从 `b0`
变成 `b0/(-p)`。例如 `p=-4` 时应求解 `y+y'/4=b0*u`，
DC 初值为 `b0*u(0)`；对从零开始的斜坡 `u=t`，独立答案为
`y=b0*(t-(1-exp(-4*t))/4)`。
LRM §4.5.11 的 epsilon 用于绝对容差，当前没有该参数的映射；
即使提供常量 epsilon 也拒绝，不能悄悄忽略它。

精确性以编译后的原始 binary64 实例常量为参照，不把十进制源码或先前常量折叠
重新解释为精确实数。先计算候选 `c=-1/p`，再用原始浮点值的整数比检查
`Fraction(c) == -1/Fraction(p)`；候选必须有限且为正。
只检查浮点乘积 `c*p==-1` 不够：`p=-3` 与舍入的 `c=1/3` 可满足该乘积检查，
有理数仍不相等，必须拒绝。因此通过域内的 `[1,c]` 与原极点关系严格相同，
不会向现有滤波误差链引入遗漏的系数转换误差。

[syntax.py](../../src/evas/syntax.py)识别算子；
[instance_compiler.py](../../src/evas/instance_compiler.py)验证并转换常量，
保留原输入表达式、实例、源码位置及展开身份，向共同列表追加既有 `LaplaceNd`。
没有新增 IR 或运行时历史类型。DC/PWL 初始化、不可变接受历史、候选回退、
系数与时间区间及电压误差验收均由上节的既有路径维护。
转换不扩大输入或下游依赖权限；例如滤波输出再供给 `absdelay` 的未认证历史依赖仍拒绝。
本批不声称一般极点形式、其他 #66 算子、联合网络的新组合或连续时间全轨迹资格。

独立回归 [test_laplace_np.py](../../tests/test_laplace_np.py)通过公开 `compile_sources`/`transient`
入口，在 `p=-4`、查询 `0,0.125,0.25,0.5,1 s`、`reltol=0`、`vabstol=1e-8` 下，
以 90 位 Decimal 计算原极点解析答案并检查 `1e-6 V` 外部预算。
覆盖单位输入 DC、斜坡、分子 2、实例与多调用点隔离、查询网格不变性、
无效域及下游历史拒绝；等价 `laplace_nd` 结果只作为转换的辅助证据。

## 输入决定的连续限幅候选

当前分支增加 `f=affine(inputs); if(f<lo) f=lo; else if(f>hi) f=hi` 的
连续限幅能力。验证组合包括 `clamp → idtmod → sin` 和独立的 `clamp → idt`。lowering 识别贡献 RHS、`IdtMod` 和无 reset 的 `Idt` input 中的
连续 clamp，因此也支持原 VCO 的 freq 贡献输出。`Sin` input 本身包含原始 Select
不在受理范围，会被既有仿射检查拒绝。也接受上下限检查顺序相反及包含等号的连续写法。
`lo<hi` 必须为有限常量；仿射式只依赖直接驱动端口和 ground。此切片没有显式事件或
持久状态。限幅基式和历史算子输入不接受内部电压反馈；一般不连续 select、状态/算子谓词、
带 reset 的积分或其他历史算子混合仍拒绝。限幅输出外的既有线性电压方程能力不变，
例如 `V(y)<+clip(V(u))+0.5*V(y)` 是可解的 `V(y)=2*clip(V(u))`，不表示限幅基式依赖 y。
并列 `Idt` 也必须只依赖原始/派生驱动源；结构上相消的内部电压和算子依赖不能绕过检查。
这允许用独立积分输出诊断累积相位，但该输出不是 `idtmod` 的内部状态。
既有无状态条件求值能力不受此切片限制。

数学参考是 `g(t)=min(hi,max(lo,f(t)))`。原输入 PWL 的每个语义段上，f 为仿射，
g 只在 f=lo、f=hi 改变斜率。分段构建发生在读出之前，不根据观测网格选择分支。
积分保持 `ic+∫g(t)dt`，常规路径按原有闭式梯形公式查询；查询不提交历史。

[input_clamp.rs](../../rust_core/src/input_clamp.rs)校验原表达式索引、来源和全部依赖后，
把识别出的连续 clamp 降低到内部受包围 PWL 驱动节点。它不改变序列化 IR/schema，
不新增用户输入/输出。响应保留原节点次序，删除内部节点的电压列。失败 lowering
不改变原 program/source；内部源为不可变定义，试算继续使用既有克隆/提交路径。

误差证书包含两项。原仿射端点与代表值的全段偏差界为 E；clip 的 1-Lipschitz 性质
使输入偏差不会放大。每个阈值根由外向 interval 包围，代表根位移为 δ，原段斜率上界为 M。
将原根映射到代表根的分段线性时间映射，最大位移不超过各根位移最大值，因此
`|g真实参考-g派生PWL| ≤ E+M·maxδ`。实现采用更保守的段内位移界之和，
跨不重叠原段取最大，再加 E。根间区间无法认证顺序或根无法认证在段内部时明确拒绝。
该界覆盖全时刻，不仅根端点；不能把浮点代表根称为精确根。

[pwl.rs](../../rust_core/src/pwl.rs)每次派生源求值保留上述一致误差带；
[operators.rs](../../rust_core/src/operators.rs)的 direct_points 消费源包围，
[Idt::enclosed](../../rust_core/src/idt.rs)按有包围的端点积分，继而传播到
[idtmod](../../rust_core/src/idtmod.rs)、sin 和原电压证书。没有通过删掉误差带或放宽
phase 电压预算解决包裹边界问题；确实无法证明的包裹侧仍按既有合同拒绝。

本分支的补充证书保留原 compiled-binary64 IR 算术，而不是把已舍入的派生端点当作
原源。[exact_source.rs](../../rust_core/src/exact_source.rs)把原 PWL 时间/值和 IR 常量
转为精确有理数；按各原源断点的并集，在原表达式上精确求值，再用有理阈值根切分
`min(hi,max(lo,f))`。以编译后 binary64 IR 的常量与结构作为精确实数参考。模块重新检查每个乘积
至少一侧为常数，拒绝以端点线性插值代表二次函数。来源元数据仅存于内部 Trajectory，
不改变公开 IR，也不证明 decimal Verilog-A 源与已折叠 binary64 IR 等价。
`add_enclosed_source` 的 error 是调用者承诺的全段误差上界。error=0 才能按所给 PWL 建立
精确来源；限幅 lowering 随即用原表达式来源覆盖，包括覆盖为 None。中间候选不对外可见，
有理构造超限时不能保留代表 PWL 的来源作为替代。

`IdtMod` 的常规 raw enclosure 跨 turn 时，请求原输入证书。直接源 PWL 与连续限幅输入使用同一判据，
不依赖表达式是否含 clamp。所有结构依赖和来源有效性仍逐项检查，不能用零乘或相消隐藏未知来源。
未跨 turn 的常规计算不变；这不是把所有积分计算替换为有理数运算。
以有理梯形面积计算 `r=ic+∫g`，以 `k=floor((r-offset)/modulus)` 得到
`p=r-k·modulus`。精确相等返回 offset；负相位和非零 offset 使用同一公式。
返回 nominal 与由相邻 binary64 值构成的外向包围来自同一个 p，均重新与有理参考比较。
若舍入 nominal 落到排除的上端点，则取其前一个浮点数并保留外向界；最后再次确认
nominal 属于半开区间。包围可以包含上端点。原有 sine 多区间处理继续保留。

资源上限为每条原/合成曲线 512 点、表达式 512 个节点及 64 层、每次构建/查询
200,000 次有理结果检查、每个检查结果的分子/分母至多 4096 bits；turn 绝对值至多
2^52。去重前临时断点列表至多 512² 点。原 binary64 分数至多 1075 bits，每步输入
来自已检查结果；加减/乘除至多若干次交叉乘积，因此单步临时位长也有固定上界，
不是先构造任意大的有理数再截断。超限或转换无法包围时撤回该证书并继续原保守路径，
严格电压预算下仍可返回 `waveform_accuracy`。有真实非点源误差的输入没有精确来源，
即使与已认证 clamp 相加也不会获得该证书。证书无缓存写入，克隆、乱序查询和丢弃试算
不改变已接受历史。直接 PWL 的可证明边界现在可受理；真实不确定来源、资源超限和无法满足
最终电压预算的边界继续拒绝。旧拒绝用例保留原请求与预算，回归改为检查独立有理答案；
另保留超过 binary64 表示精度的电压预算拒绝控制。

独立证据为[原 VCO 源与解析面积回归](../../tests/test_input_clamp.py)：原 CO-VCO-01
源未改，显式初相位 0.125，限幅拐点 1.2/3.2/4.8/6.8 us，答案来自独立分段面积及
`sin(2πp)`。Rust 单测另用精确有理数检查非二进制根两侧全段包含、积分消费源误差、
非法原索引/来源拒绝及 lowering 失败不修改输入。新增 public Rust 路径回归以独立
Fraction oracle 使用独立算术实现同一分段积分公式，检查原四中心、非二进制限幅根两侧/相等、负相位/offset、多源不齐断点
和观测网格不变。直接 chirp 的精确回绕与两侧、增加独立 `idt` 前后的公共输出和解析面积
也通过公开编译/内核路径检查；Rust 控制检查真实不确定性与资源耗尽保留两侧、half-open 舍入
及 clone/query 不写历史。双实例边界另用手算面积 `3/4-(3/8)/(b+1/4)`，分别改变初值及输入末端，检查来源隔离。
[实际 Spectre 精简证据](../../../experiments/backends/input-clamp/README.md)记录
40,836 个普通同刻行及四次包裹左右括定的有限开发对齐。另一个包含四个中心的 batch
在首次误差认证拒绝处退出，四行均未配对。后续[逐点诊断](../../../experiments/backends/input-clamp/boundary-diagnostics.json)
在修复前原配置、收紧及仅诊断的放宽容差下分别执行，四个原模型中心均因普通 phase 的误差界拒绝；
左右邻点完成，不同源码的常零 phase 贡献控制也完成，但不能替代原模型验收。
本分支新证书在独立 compiled-IR 数学回归中通过四中心，第三中心保留接近 1 的
ordinary phase；修复后全部40,840个原 Spectre 保存时刻已配对，第三中心普通相位差约1cycle，圆周相位差约1e-8cycle，分歧未被掩盖。详见[修复后证据](../../../experiments/backends/input-clamp/certificate-evidence.json)。严格 stop
覆盖缺口仍保留，正式导出及输入误差资格尚缺，paper 状态为 I。开发对齐不构成
完整能力支持、全连续轨迹证明或 formal P；分支本地回归也不是已合入支持。

## idtmod 与 sin

受限相位子集包括 `idtmod(u, ic, modulus, offset)` 与 `sin(x)`，用于 D2 类
电压域相位模型。依据 Verilog-AMS LRM 2.4 的 `idtmod(expr, ic, modulus, offset)`
形式，当前只接受显式有限常量初值、显式正有限 modulus 和有限 offset；省略 modulus 的
无界积分形式不映射到本算子，仍应使用普通 `idt` 或明确拒绝。

`idtmod` 的输入为直接驱动、连续 PWL 的仿射组合，不接受内部节点、
状态、反馈、嵌套或动态参数。实现先用 [idt](#idt) 的解析积分得到未包裹相位
`z(t)=ic+∫u(s)ds`，再返回

`phase(t)=offset + (z(t)-offset) mod modulus`，

范围为半开区间 `[offset, offset+modulus)`。负频率用 `rem_euclid` 语义处理，因此
`ic=1/8,u=-1/4,modulus=1,offset=0` 在 `t=1` 得到 `7/8`。每个调用点和实例仍有独立历史；
查询、输出网格和失败候选不写历史。

`sin` 在本页路径中是函数型 operator，不引入通用非线性瞬态方程。接受两类输入：
直接驱动 PWL 仿射表达式，或 `constant + coefficient * earlier_operator`。后一类覆盖
``sin(2*`M_PI*phase)``。运行值可使用已绑定的代表系数，但精度证书重新从原始输入表达式做
outward affine arithmetic，保留常量和系数折叠、相消及 binary64 运算造成的区间误差；若代表值可能
偏离该区间内的实数参考且无法满足电压预算，则返回 `waveform_accuracy`。`phase` 若来自 `idtmod`，
误差界使用 wrapped phase 的保守区间；不会把 binary64 系数 `2*`M_PI` 当成精确实数周期来抵消整圈误差。
其他状态输入、内部节点输入、operator 前向引用、多个 operator 混合、算子驱动 cross 和
operator 乘 voltage/state 仍拒绝。

wrapped 相位本身是不连续输出。严格区间若横跨 wrap 点，默认只能给出整个 `[offset,offset+modulus]`
保守范围；只有通过 outward interval arithmetic 证明 raw phase 落在同一个 turn 内，才返回窄 wrapped 界。
对常量输入段、精确点输入/前缀积分和可用 exact binary64 product/sum 判定的请求，若 raw phase 区间
只跨相邻 turn，内核会比较精确实数 `raw-(offset+k·modulus)` 的符号：小于零取左侧，
大于零取右侧，等于零取 half-open wrap 的 offset 点。因此 D2 这类 binary64 采样点在 wrap 邻域
可证明时能通过；非精确系数、非点输入误差、过多乘积项或巨大 turn 仍保守保留两侧并可能拒绝。
当 `sin` 消费同一个 `idtmod` 输出时，可以保留 wrap 两侧的两个相位区间，分别做正弦区间证明再取并集；
这只用于该函数证书，不改变 wrapped 电压输出的整周期保守界，也不把 binary64 的 `2π` 当作精确周期。
大不确定度、真实跨越和不可精确表示的巨大 turn 会返回整周期或在 bounds 层触发
`waveform_accuracy`。这会在严格电压预算下拒绝不确定 wrap 边界；这是 soundness 约束，
不是连续时间 wrap 轨迹资格。

局部变量由统一的顺序 analog lowering 转换。
无事件/初始化的普通 local real 可重复无条件赋值，每条赋值捕获当时表达式；每个动态调用仍有独立身份。
例如 ``phase = idtmod(...); V(out)<+sin(2*`M_PI*phase);`` 不创建持久状态。
条件动态调用仍拒绝；普通条件与动态算子联立也尚未支持。`constants.vams`
当前只解析窄集合中的 `` `M_PI``，不会执行 include 文件或引入任意宏系统。

验证入口：[test_phase.py](../../tests/test_phase.py) 使用固定常频、chirp、负频率和 Decimal 高精度正弦答案，
检查仿射重复引用、隐藏依赖、相消误差、wrap 两侧包围、exact wrap 及 raw IR 畸形字段。
无法证明 wrap 边界时应返回 `waveform_accuracy`，不能用代表值选择一侧。
专项执行及早期矩阵成绩保留在[固定历史章节](https://github.com/BucketSran/vaEVAS/blob/1527502c9affb77fec12aac03adba5446f0f241e/evas/docs/OPERATORS.md#idtmod-与-sin)；
当前联合矩阵的执行身份见[实验入口](../../../experiments/runs/parallel-gap-integration/README.md#当前证据)。

## slew

输入为直接驱动连续 PWL 的仿射组合，固定正限速 r+ 和负限速 r-，初态 y(0)=u(0)。
三参数须显式提供，`rise>0`、`fall<0` 为有限实例常数，限速单位为输入单位/秒。
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
局部表示改善代表值，区间则包围原始 binary64 PWL 和编译后 IR 的实数解，并传入共同的
同刻电压/状态预算。网络增益、相消和后续采样不能把已有误差清零。
不能证明模式或交点次序时仍拒绝；几何成立但电压预算不足时返回 `waveform_accuracy`。
[test_slew_accuracy.py](../../tests/test_slew_accuracy.py) 检查反向追赶误差放大、初值/输入重采样、
同刻电压读取与跨事件误差保留。成功计算点的保守验收不构成整个电路的连续时间误差保证，
也不包含编译前常量舍入或允许的源事件时间偏移；保守区间可能拒绝实际误差较小的输入。

实现：[slew.rs](../../rust_core/src/slew.rs)。
验证：[test_slew.py](../../tests/test_slew.py)
包括独立 SL-CATCH/REVERSE/PASS、反射、SI/二进制尺度、实例与网格变化。
[联合回归](../../tests/test_timed_composition.py)另外检查双实例的三算子与 timer/cross 同刻采样，
独立公式覆盖实例顺序、输出网格和步长变化。
固定版本的专项结果见[对照及步长诊断](../../../experiments/archive/pr14-pr15-validation/RESULTS.md)。
Spectre 的反向追赶偏差随步长细化下降；这是波形证据，不是私有算法或 LRM 违规的结论。
本实现允许上述内部仿射电压投影和下述两级固定前馈。状态输入、更深嵌套、动态/缺省限速、跳变和
经过历史状态的反馈尚未支持。

### 两级固定 slew 的完整分段历史

支持 `slew(slew(x,r1,f1),r2,f2)`，或同实例的单位增益、零偏置电压别名。
两层限速均为固定常数，第一级输入为上述连续 PWL 仿射投影。
结构检查先于数值消元；乘零或相消不能隐藏状态、反馈、其他算子或跨实例历史依赖。
第三层、混合算子和非单位别名仍拒绝。原有单层 slew 的计算路径保留。

第二层必须看到第一层真正改变斜率的位置。实现把名义输入端点、两层追赶交点及其值
保存为精确有理数，只在返回电压或向调度器提供断点时转换为 binary64。
例如反向刺激 `(0,0),(2,4),(4,-4),(24,-4)`，两级限速分别为 ±0.5 和 ±0.25：
第一级在 `8/3` 秒转向，第二级在 `32/9` 秒转向。
如果只把输出查询点传给第二层，它可能漏掉这两个交点，结果便随查询密度改变。

名义曲线不等于忽略输入误差。设投影端点的认证区间为 `A_i`，代表值为 `a_i`，取
`E = max_i max(|a_i-lo(A_i)|, |hi(A_i)-a_i|)`。
连续 PWL 插值使真实输入与名义输入在整段内相差不超过 E。
固定限速算子保持输入的大小次序，并满足 `S(x+c)=S(x)+c`，初值也随输入首值平移。
因此 `x-E ≤ x_true ≤ x+E` 推出 `S(x)-E ≤ S(x_true) ≤ S(x)+E`；同一个 E 可以继续传过第二级。
查询区间包围精确名义值加减 E，再由现有电压验收检查外部增益和浮点求解误差。
E 过宽时仍拒绝，不把代表值直接当作无误差状态。

这是固定、连续输入和固定限速下的推导，不能用于动态限速、跳变输入或反馈。
两级构造最多接收 512 个源拐点，复用精确源算术的 4096 位及 200,000 次运算预算；
超限返回 `waveform_accuracy`。历史由不可变 Arc 保存，查询和失败试算不改写它。
本次不增加 slew 的 cross 守卫，也不增加非点事件窗口内的采样能力。

实现位于 [slew_cascade.rs](../../rust_core/src/slew_cascade.rs)，
准入及电压误差传递位于 [operators.rs](../../rust_core/src/operators.rs)。
[独立回归](../../tests/test_slew_cascade.py)检查两层公式、反向邻点、非零初态、实例顺序、
时间尺度、查询密度和误差放大；同 Controller 的失败重试由
[transient.rs](../../rust_core/src/transient.rs)检查。
[实际 Spectre 对照](../../../experiments/backends/slew-cascade/README.md)单列本批模型、设置和结果，
不扩展历史表的分母，也不完成 #66 的 C4 滤波直接通路。

## 来源与证据限制

语义依据为 [Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
§4.5.7–4.5.9；范围收窄、分辨率门限及上述数据结构属于 EVAS 的选择。公式是对限定输入的推导，
规范、EVAS 约定、后端观察三者有分歧时必须显式保留。共同历史与观察预算见
[验证协议](../../validation/METHOD_QUALIFICATION.md)，本地方法数不是正式条件数。
原数学样例已经用于开发；新增修复验证不得称其为未见确认集。

<a id="extension-operator-contract"></a>

## C3 与新算子的共同接口

本节是 [ADR-002](../development/DECISIONS.md#adr-002) 的设计契约，保持现有每个算子的限定准入。
历史算子的身份由实例、源码位置和展开身份确定，不能改为接收变量的名字；
纯函数不产生物理历史，但必须继承输入的误差依赖。

C3 固定前馈先定义输入历史的 value/bounds、语义断点与可证明的下一截止点，
再定义新算子的初始化、查询和候选变化。输出网格不定义历史。
上游时间误差经移位/追赶变成输出包围，不能把上游代表样本当作精确 PWL 再建下游历史。
未变化调用点沿用接受态；失败/弃步丢弃下游候选，不保留已推进的上游。
两级固定 absdelay 的交付不授权一般 slew/深层延迟/滤波组合，初次 slew 切片的独立预期见 ADR-002/C3。

动态参数须另外定义参数改变时的历史作用范围、队列和模式变化。例如延迟改变后究竟查询
旧输入轨迹的哪个时刻，限速改变后哪个模式从当前物理状态开始，均不能用参数绑定成功来回答。
历史反馈须证明联合存在/唯一性和时间因果性，无法证明则明确拒绝。
这些接口可以扩展现有 Runtime；不先创建无消费者的通用历史框架。

<a id="operator-breadth-backlog"></a>

## #66 算子目录的分批验收与未交付范围

责任入口是 [#66](https://github.com/BucketSran/vaEVAS/issues/66)。
对比版本仍固定为 [Arcadia EVAS v0.8.7](https://github.com/Arcadia-1/EVAS/tree/v0.8.7)，
名称/行为 helper 的声明不能作为本库误差认证证据。
本轮优先验收 #96/#108 的既有连续状态和事件组合，没有以新函数数量代替行为对齐。
尚未从已选模型识别新算子阻塞时，不批量启动目录。以下是未交付任务的验收入口，
不是已支持清单，也不构成已建立独立实现 PR 的声明。

| 批次 | 首次实施前固定的输入/独立预期与接口 | 当前交付与剩余责任 |
| --- | --- | --- |
| 数学函数 exp/ln/log/cos/floor/ceil、limexp | 实数定义域、溢出、导数、区间包围及不连续点逐项定义；floor(-.25)=-1、ceil(-.25)=0 等边界必须独立检查。limexp 的试算限幅与最终 exp 解分开验收，不能把限幅结果当正确根 | 现有受限 sin 不完成此批；其余仍归 #66/math，待实际模型选择有限切片 |
| 连续 laplace_np/zd/zp | 固定系数原传递关系、复根的共轭/实系数约束、阶数、原 DC 初值及转换误差；验收原关系而非仅转换后的 IR | #80 只交付单负实极点 np 且倒数精确可表示；多极点/复根/其他形式/epsilon 仍归 #66/continuous，非线性直接通路依赖 #62/C4 |
| 离散 zi_nd/np/zd/zp | 冻结采样时钟、延迟、初值和递推式，以独立离散序列验收调用点隔离与失败回退；时钟驱动共同候选与提交 | 全批仍归 #66/discrete；不能用连续滤波或外部预计算波形替代 |
| 随机/噪声 | 定义种子与调用点状态、拒绝试算后的序列恢复、统计/PSD 语义；行为随机 helper 与随机瞬态过程分别验收 | 全批仍归 #66/noise；瞬态静默置零不算支持，PSD 查询也不完成随机过程认证 |
| 表/文件任务 | 固定文件身份、插值/外推和错误规则；外部副作用只能在接受后发生，失败/重试不得重复写入 | 全批仍归 #66/table-file；需定义事务提交与外部副作用失败结果，不能在试算中直接写文件 |
| analysis/ac_stim、AC/noise sweep、$bound_step | 明确适用分析、请求接口及真实效果；行为 sweep、小信号线性化和误差认证分开 | 全批仍归 #66/analysis；$bound_step 的求步约束不能以输出采样间距冒充 |

后续每批由 #66 登记具体实际模型和关联实现 PR/子项，再把该批责任移交。
本轮尚无这些新实施入口，#66 仍未满足全部关闭条件。
若实际需求需要未认证模式，先完成 ADR-002 所规定的单独决定，默认路径不得静默降级。
每个新算子同时交付数学章节、状态生命周期、正/负边界、依赖误差和调用组合验收；
实际 Spectre 对照限该模型/配置，不能由有限配对扩大目录范围。
