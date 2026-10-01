# EVAS IR15 交付审查

当前运行时、数学与兼容性从本页进入。原始逐轮叙述、失败与测量保留在
[固定历史](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/REVIEW.md)，
收据无损归档见[资产入口](README.md#历史与资产)。没有将历史失败删除或记为成功。

<a id="precision-chain"></a>

## 2026-10-01：点输入根误差与无条件采样精度链修复

本交付检查点的运行时固定于
`d451605bf9991ceea010c68af9cb1143f1b50754`，0.9.0 / IR v15；没有发布 tag。
只修复综合审查确认的两处验收缺口，不扩展算子，也不改变原 31 条件或 checker。

### 数学和实现 review

1. [solver.rs](../../evas/rust_core/src/solver.rs) 不再因为输入区间是点值而跳过根盒。
   `y=u+y²,u=.25` 可得到零名义残差及零 Newton 修正，输出却离精确重根 `.5` 约
   `3.725e-9 V`，超过 `1e-12 V` 预算。现在点输入也用 `sup|F|/inf|J|` 的严格内含证明，
   失败再用 Krawczyk；无法认证则 `waveform_accuracy`。静态 `solve` 的局部 Newton 契约不变。
   同支路多贡献保存在 `original_rhs` 列表，区间残差和导数对所有原树求和；移除单来源限制，
   防止拆分合法贡献改变支持范围。名义 Jacobian 只生成预条件器，不作为精确证明。
2. [transient.rs](../../evas/rust_core/src/transient.rs) 的每次试算都读取已接受 `state_bounds`，
   并使用原 PWL 输入区间；初始化及无算子普通观察也认证。此前无条件、无算子路径会把两者压成点。
   最小采样反例的 `u(1)=1+2^-52/3` 舍入为 1，`1e16*(u(1)-1)` 的真实输出约 `.740149 V`，
   原路径返回 0。本轮不再允许小残差掩盖该误差。
   跨事件反例第一次采样 `u(1)=1+2^-54` 可满足相对预算；第二次乘 `1e16` 后，
   名义输出 0 与独立答案 `1e16*2^-54≈.555112 V` 的差异必须进入验收。
   状态区间与电压、历史一起提交；失败候选不改变接受帧。无算子普通观察保留固定电路分解缓存。

review 应检查原树是否完整、区间舍入方向、同刻重放是否仍从接受历史开始，以及普通观察失败前
是否更新了接受时间或状态。实现没有修改事件日程、Newton 迭代、原容差或资格判据。
数学契约见[数值手册](../../evas/docs/NUMERICS.md#精度链的已修复反例与边界)、
[根盒契约](../../evas/validation/NONLINEAR_TRANSIENT_CONTRACT.md)及[事件说明](../../evas/docs/EVENTS.md)。

### 独立验证与兼容边界

[test_precision_chain.py](../../evas/tests/test_precision_chain.py) 用 100 位 Decimal 二次根与精确
Fraction 采样答案覆盖近重根、普通根、贡献拆分/交换、点输入及 off-knot、宽容差正控制、
恒真条件/零 idt 的语义不变性，以及误差跨事件放大。新的 Rust 回归先接受非点状态包围，
再故意失败两次，检查旧帧不变；宽预算下复用证书缓存的重试必须与新模型一致。
冻结旧内核的 RED 阶段中，6 个 Python 方法出现 9 个失败子项，Rust 回归也失败；失败日志保留。
最终全套 **372 Python、83 Rust** 通过；一项旧性能探针明确 ignored，本轮未运行它或重测性能。
locked build、all-targets Clippy `-D warnings` 与格式检查通过。
[开发检查收据](results/precision-chain-checks.json)绑定源码、二进制、测试与失败日志身份。

原 31 条件两档重新执行均 **31/31 有限观测达标**，全部 **62 份 CSV、原判定和生效设置**
与优化检查点 `ddfd379` 一致，DUT、刺激、阈值、checker 和分母未改。
[矩阵收据](results/precision-chain-matrix.json)保留每个配置和基线比较；本轮没有新 Spectre 执行或重分析。
执行内核 SHA256 为 `0d92e770471638182f05fec53c308c0b34d89935c25bbaf70d47f5c9c33f522f`。
原始输入、源码归档、两版内核、RED/失败/最终检查及矩阵输出保存在 ignored 的
`runs/precision-chain-20260930T202707Z-e1c89a/`，清单绑定 876 文件、172,681,211 字节。
原始材料为 **仅本地保留**；整理收据与源码随本检查点交付，正式资格仍为 **I**。

更严格的认证有以下可见边界：多项式非方阵现在在点输入处也拒绝；仿射冗余关系若只在某个
状态点成立、而非误差映射参数域的恒等式，可能在初始化提前拒绝。原 timer 夹具改为明确断言
这个早期错误，候选残差失败/回滚仍由既有 Rust 回归检查。复位时间误差夹具增加实际源结点，
避免 `1e-20 V` 设置先拒绝普通 PWL 插值，从而继续独立检查它原本的复位时间误差。
后一个测试仍检查严格拒绝、接受帧不变和精确复位重试，没有放宽容差。
较晚的 Newton 失败夹具改用方阵 `F=y³−2y+2u`，保留成功后第 1 个样本失败的断言。

通用 `real` 状态使用相对误差预算；接近零的非点包围可能保守拒绝。
认证仅相对于传输后的原 IR；不恢复前端折叠损失，不证明全局多解选择或一般连续时间误差，
非线性与事件/历史联合求解仍未支持。新增认证有计算开销，本轮未测量其速度影响；
此前标量根盒和查询复用的性能测量只描述其原检查点。

<a id="gap-completion"></a>

## 限定功能补齐

普通 analog 条件、一阶 laplace、idtmod/sin 与无状态多项式瞬态统一到 IR15；
贡献进入方程组，局部赋值捕获调用处表达式，各算子拥有实例/调用点历史。
这些边界已在联合运行时检查，未加入一般非线性历史或事件联立求解。

### 数学与实现入口

| 顺序 | 本轮补齐 | 数学原理与精度处理 | 重点入口 |
| --- | --- | --- | --- |
| 1 | `v6-standard`、`c2-main`：常量数组、一阶 `laplace_nd`、滤波采样级联 | 对 `b0/(d0+d1*s)`，令 `τ=d1/d0`、`g=b0/d0`，解 `τy′+y=gu`。直接 PWL 每段使用解析响应，DC 初值为 `gu(0)`；原始系数、时间差和指数余项的区间进入历史及电压验收 | [数学契约](../../evas/validation/LAPLACE_CONTRACTS.md)、[laplace.rs](../../evas/rust_core/src/laplace.rs)、[独立 Decimal 回归](../../evas/tests/test_laplace.py) |
| 2 | `d2-constant`、`d2-chirp`：内建 constants 宏、`idtmod` 与受限 `sin` | 先累计 `z=ic+∫u dt`，查询 `offset+(z-offset) mod modulus`。原始累计相位独立保存；wrap 边界用精确 product-sum 符号或保守区间。正弦分别包围 wrap 两侧，再取并集，不把浮点 `2*M_PI` 当作数学精确周期 | [算子数学](../../evas/docs/OPERATORS.md#idtmod-与-sin)、[idtmod.rs](../../evas/rust_core/src/idtmod.rs)、[operators.rs](../../evas/rust_core/src/operators.rs)、[Fraction/Decimal 回归](../../evas/tests/test_phase.py) |
| 3 | `v7-nonlinear-0.5`、`v7-nonlinear-2.0`：无历史非线性瞬态 | 每个请求时刻独立解 `F(v,u(t))=0`；前一个成功解只作 Newton 初猜。点值与非点输入均使用所有原 RHS 的区间 Jacobian 与 Krawczyk `K=x−CF(x,U)+(I−CJ(X,U))(X−x)`，标量优先用严格 R/m 证明，否则证明 `K⊂int(X)` 且收缩范数 `<1` 后接受 | [精度契约](../../evas/validation/NONLINEAR_TRANSIENT_CONTRACT.md)、[solver.rs](../../evas/rust_core/src/solver.rs)、[高精度根与反例](../../evas/tests/test_nonlinear_transient.py) |
| 4 | 共同入口与组合修复 | 仿射关系保留原 forward-error map；普通条件先认证原 PWL 谓词。全部历史仍从已接受 Frame 重放，试算失败不提交。reset 后允许依赖它的纯 `sin` 同刻重算，不能跳过重新求解及验收 | [analog.rs](../../evas/rust_core/src/analog.rs)、[reset_dependencies.rs](../../evas/rust_core/src/reset_dependencies.rs)、[组合回归](../../evas/tests/test_gap_integration.py)、[实际 Frame 弃候选/重试](../../evas/rust_core/src/transient_idt_tests.rs) |

整合没有另造一套算子执行器。统一 IR 的同时，扩展原有结构依赖图，让新算子中的
复位反馈仍明确拒绝；不能通过 `sin`、局部别名或相消隐藏反馈环。
同刻重算权限只沿实际改变且已获许可的 reset 算子依赖传播；每次仍从相同已接受历史
重算全部候选值、区间、复位状态与电压方程。新增失败后弃候选/重试回归验证这一点。

无状态入口现由 `Analog` 统一分流：仿射系统用已有电压误差映射，纯多项式用 Newton
及其认证；添加无作用的普通条件不能绕过或额外禁用精度检查。缓存只保存同一分支的
表达式/模型/电路结构，不缓存输入、解或物理历史；输出查询不增加 `accepted_steps`。

历史功能检查点 `39a4545` 的 62 次 EVAS 执行两档均 31/31，362 Python、79 Rust 通过。
相对 analog 基线各 25/31 新增六条，原达标 50 份 CSV 不变；该轮只重新核验既有 Spectre 62 次结果，
各 31/31，没有新远端执行。[31 行摘要](results/gap-completion-matrix.md)和
[完整当轮 review](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/REVIEW.md#gap-completion)保留当时身份；
后续精度链的 372/83 及点输入认证不能追溯宣称为当时已完成。

<a id="accuracy-optimization"></a>

## 查询复用与标量认证

`ddfd379` 在一次试算中复用同一时间、同一接受历史上的不可变查询值和区间。
transition、reset idt 及消费它们的 sin 仍重新计算；失败候选整体丢弃。
标量根证明使用 `R=sup|F(x,U)|`、`m=inf|J(X,U)|>0`，严格认证 `R/m` 小于预算盒半径；
不成立时回退 Krawczyk，不能以名义 Jacobian 或小残差代替证明。

[计时收据](results/accuracy-optimization-profile.json)保存 `4a40f09` 与 `ddfd379` 的同机
release 内核、四个固定工作负载、交替四轮的完整测量；
[完整方法与限制](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/REVIEW.md#accuracy-optimization)保留各阶段数据。
正确性检查为 364 Python、82 Rust，原矩阵两档各 31/31，62 份 CSV 与 `39a4545` 一致。
这些局部测量不含 Python/JSON 端到端成本，也没有覆盖最新 `d451605` 的新增认证开销；
不宣称当前版本或跨后端速度倍数。旧收据的完整内容与哈希见[无损归档](README.md#历史与资产)。
