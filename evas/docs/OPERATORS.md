# 有历史的波形算子

能力 ID：TRANSITION、ABSDELAY、SLEW、COMPOSE。本文解释开发检查点；当前 main 0.4.6 尚未支持这三个算子。
实现/证据/审阅状态及固定提交见[能力总表](CAPABILITIES.md)。独立需求、手算样例与 Fraction 核对器
由[定时算子契约](../validation/TIMED_OPERATOR_CONTRACTS.md)维护，不以实现生成的波形替代标准答案。

## 公共执行方法

PR13 引入实例与源码调用点身份，算子历史与用户状态分开保存。设 q 为离散状态、H 为已接受历史，
先求算子值 `z(t;q,H)`，再将它代入限定仿射电压方程 `A v=b(u,q,z)`。
当前范围避免算子值隐式依赖本次待求电压；不因此推广到任意反馈或非线性瞬态。

到期目标、边沿端点及追赶交点属于语义断点，输出网格不定义历史。时间推进复制候选历史，
求事件前电压、准备状态、更新目标、重解并验收，最后一起提交；失败/弃步不消耗队列。
共同事件顺序及未决兼容性见[事件手册](EVENTS.md#timer-与同刻兼容性)。

共享代码检查点：[operators.rs](https://github.com/BucketSran/vaEVAS/blob/bb01e88225efb8884cd009ae32ab4e77a6b50d0c/evas/rust_core/src/operators.rs)、
[transient.rs](https://github.com/BucketSran/vaEVAS/blob/bb01e88225efb8884cd009ae32ab4e77a6b50d0c/evas/rust_core/src/transient.rs)。
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
端点求值裁剪在起点与目标之间。期限检查在帧/记录提交前完成。

实现：[transition.rs](https://github.com/BucketSran/vaEVAS/blob/bb01e88225efb8884cd009ae32ab4e77a6b50d0c/evas/rust_core/src/transition.rs)。
验证：[test_transition.py](https://github.com/BucketSran/vaEVAS/blob/bb01e88225efb8884cd009ae32ab4e77a6b50d0c/evas/tests/test_transition.py)
包含 TR-EDGE/REVERSE/EXTEND/REPEAT/QUEUE、反射、实例隔离、网格与步长、浮点分辨率及拒绝边界。
Rust 另检查队列/边沿的候选回退。尚未完成专属 Spectre 对照，下降反射及同刻边界不能仅凭数学样例宣称兼容。
连续电压输入、嵌套、动态参数、缺省/零边沿和算子反馈尚未支持。

## absdelay

固定正延迟 τ 的输出为 `y(t)=u(max(t-τ,0))`，其中 u 是直接驱动连续 PWL 的仿射组合。
初始历史保持 u(0)。τ=0 的恒等行为是显式 EVAS 扩展，不能声称由 LRM 的正延迟要求证明。

实现共享不可变的输入语义段，以平移后的拐点要求求解，在原输入历史上查询 `t-τ`。
查询时间使用补偿减法保留低位，按原始拐点排序并作局部插值，避免大时间减法先舍入而错选位置。
例如 t=2^54+4、τ=3，在从 2^54 到 2^54+4 的 0→1 斜坡上，数学答案为1/4；
先舍入 t-τ 可错误得到0。输出采样网格不能作为历史存储。

实现：[absdelay.rs](https://github.com/BucketSran/vaEVAS/blob/a4b4fbe628c798c616ccdbcd82e04f36fcd41bb0/evas/rust_core/src/absdelay.rs)。
验证：[test_absdelay.py](https://github.com/BucketSran/vaEVAS/blob/a4b4fbe628c798c616ccdbcd82e04f36fcd41bb0/evas/tests/test_absdelay.py)
覆盖非零初值、零/长延迟、大时间低位、双实例、网格/步长及结构拒绝。
不可表示或非有限的移位拐点显式失败；尚未完成 Spectre 对照或通用历史误差界。
内部节点/状态输入、嵌套、跳变、动态延迟/maxdelay 和反馈尚未支持。

## slew

首批输入为直接驱动连续 PWL 的仿射组合，固定正限速 r+ 和负限速 r-，初态 y(0)=u(0)。
在输入斜率 a 恒定的分段上：y<u 时以 r+ 追赶，y>u 时以 r- 追赶，y=u 时选择
`clip(a,r-,r+)`；相交后重新判断跟踪或追赶模式。
对于当前输出斜率 s，候选相交时刻为 `tc=t0+(u0-y0)/(s-a)`，只有分母、方向与段内次序可认证才采用。
这给出分段解析轨迹，无需按输出网格做数值积分。

平台期间落后的输出继续追赶；输入反向后，只要仍处于同侧，输出继续原方向直到真正相交。
实现用区间运算认证模式与交点次序，语义段/断点通过 Arc 共享；不确定或不可表示时失败。
这些几何判定不构成整个电路的连续时间前向误差保证。

实现：[slew.rs](https://github.com/BucketSran/vaEVAS/blob/5f0aba6a4312fbcddd261cc3e9de7f63736bef9a/evas/rust_core/src/slew.rs)。
验证：[test_slew.py](https://github.com/BucketSran/vaEVAS/blob/5f0aba6a4312fbcddd261cc3e9de7f63736bef9a/evas/tests/test_slew.py)
包括独立 SL-CATCH/REVERSE/PASS、反射、SI/二进制尺度、实例与网格变化。
尚未完成 Spectre 对照；内部节点/状态输入、嵌套、动态/缺省限速、跳变和反馈尚未支持。

## 来源与证据限制

语义依据为 [Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
§4.5.7–4.5.9；范围收窄、分辨率门限及上述数据结构属于 EVAS 的选择。公式是对限定输入的推导，
规范、EVAS 约定、后端观察三者有分歧时必须显式保留。共同历史与观察预算见
[验证协议](../validation/METHOD_QUALIFICATION.md)，本地方法数不是正式条件数。
原数学样例已经用于开发；新增修复验证不得称其为未见确认集。
