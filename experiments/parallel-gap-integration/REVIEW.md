# 六路候选的复审记录

<a id="precision-chain"></a>

## 2026-10-01：点输入根误差与无条件采样精度链修复

本轮延续本地 `test/evas-gap-integration`，0.9.0 / IR v15；未发布或合入 main。
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

更严格的认证有两项可见边界：多项式非方阵现在在点输入处也拒绝；仿射冗余关系若只在某个
状态点成立、而非误差映射参数域的恒等式，可能在初始化提前拒绝。原 timer 夹具改为明确断言
这个早期错误，候选残差失败/回滚仍由既有 Rust 回归检查。复位时间误差夹具增加实际源结点，
避免 `1e-20 V` 设置先拒绝普通 PWL 插值，从而继续独立检查它原本的复位时间误差。
后一个测试仍检查严格拒绝、接受帧不变和精确复位重试，没有放宽容差。
较晚的 Newton 失败夹具改用方阵 `F=y³−2y+2u`，保留成功后第 1 个样本失败的断言。

认证仅相对于传输后的原 IR；不恢复前端折叠损失，不证明全局多解选择或一般连续时间误差，
非线性与事件/历史联合求解仍未支持。此前标量根盒和查询复用的性能测量只描述其原检查点。

<a id="accuracy-optimization"></a>

## 2026-10-01：同刻查询复用与标量根盒认证优化

当前本地运行时为 `ddfd3795ee7edd7cb5d3e6ccf2160d5872f334d4`，仍为 0.9.0 / IR v15，
未发布或合入 main。优化建立在下方已完成原 31 条件补齐的联合候选上。

### 改动和 review 重点

1. [operators.rs](../../evas/rust_core/src/operators.rs) 的 `Evaluation` 借用同一历史基线并固定时间。
   同刻候选仍克隆和推进该基线；只复用不会被本次推进改变的算子查询值及区间。
   复位 idt、transition 及其 sin 依赖链重新计算。Runtime 分类为穷尽匹配，新增类型必须明确分类。
   [transient.rs](../../evas/rust_core/src/transient.rs) 保留同刻重解、权限检查、值/区间重放及复位历史一致性检查。
   重点检查复用的生命周期是否严格止于本次时间和历史基线，以及失败候选是否仍能完整丢弃。
2. [solver.rs](../../evas/rust_core/src/solver.rs) 的 `scalar_root_box` 在单未知量、非点输入时先做中值定理证明。
   令 `R=sup|F(x,U)|`、`m=inf|∂F/∂v|>0`，向外舍入的 `R/m` 必须严格小于到预算盒两端的
   向内舍入距离。此时对每个固定输入，连续性和单调性证明盒内存在唯一根。
   证明失败回到原 Krawczyk；原 RHS、区间导数、残差门及电压预算均保留。
   重点检查舍入方向、导数跨零/很小、端点等号和反馈误差放大，不能只看名义残差。
   完整推导见[精度契约](../../evas/validation/NONLINEAR_TRANSIENT_CONTRACT.md#scalar-monotonicity-certificate)。

没有更换 Newton、时间步策略或容差。点输入仍是原区间残差及名义 Newton 验收，
没有额外根盒证明；多未知量仍走原 Krawczyk。本轮未实现稀疏区间消元或长相位重表示。

### 性能实验

基线 `4a40f09` 只在 `39a4545` 的实现上增加 cfg(test) 计时探针，生产行为相同。
它从已提交源码归档重新编译，得到与最初探针二进制相同的 SHA256；初期试跑仍单独保留。
候选和基线均使用 locked release 构建，在同一 Apple M5 / macOS 主机交替执行四轮
AB、BA、AB、BA；每个进程先完整预热，每个模型各计时五次，共每版本每模型 20 次。
请求克隆、输入解析、JSON 序列化和进程启动在计时外；完整内核计时包含本次模型准备、
求解、认证与响应构造。专项查询计时只描述查询成本，不作为完整仿真耗时。

所有模型固定 `vabstol=reltol=1e-8`。三次方程有 1,026 个输出点，PWL 从
`(0,.125)` 到 `(3,.875)`，末点 t=3，其余为 `i/1024`；系数分别为 .5 和 2。
两条组合模型有 1,025 个 `i/1024` 输出点，PWL 从 `(0,.25)` 到 `(1,.5)`；
一阶滤波与相位函数并行输出，复位模型另在 .25/.5 时切换 reset，并输出 reset-idt 的正弦。
完整模型、请求哈希、方法、每个阶段的中位数和最小/最大值见[性能收据](results/accuracy-optimization-profile.json)。

| 完整内核模型 | 基线中位数 ms | 优化后 ms | 中位耗时下降 |
| --- | ---: | ---: | ---: |
| 三次方程，系数 .5 | 5.461 | 4.997 | 8.5% |
| 三次方程，系数 2 | 5.454 | 4.942 | 9.4% |
| 滤波与相位 | 29.627 | 16.139 | 45.5% |
| 复位积分、滤波与相位 | 42.788 | 27.068 | 36.7% |

三次方程的认证阶段中位耗时约从 2.91 ms 降至 2.39 ms；名义 Newton 路径未改变。
组合模型减少的是同刻重复查询，单次不可变历史区间查询方法保持原实现。
全部 160 份完整响应与各模型的基线响应一致。共享主机没有锁核/锁频；复位组合有一次
候选耗时 49.36 ms，完整波动范围保留。上述仅为固定局部工作负载的描述性结果，
不承诺每次都加速，也不是 Python/JSON 端到端或对 Spectre 的速度比较。

显式计时入口是 [performance_probes.rs](../../evas/rust_core/src/performance_probes.rs) 中
ignored 的 `profile_accuracy_components`；[profile.py](profile.py) 校验冻结输入和二进制身份、
交替运行并检查完整响应一致性。取得收据绑定的本地请求及二进制后，用新输出目录运行：

```sh
python3 -B experiments/parallel-gap-integration/profile.py \
  --baseline "$baseline_probe" --candidate "$candidate_probe" \
  --inputs "$frozen_profile_inputs" --root "$new_profile_run" --rounds 4
```

### 正确性、身份和限制

[原矩阵新执行收据](results/accuracy-optimization-matrix.json)：原 31 条件两档均 **31/31 有限观测达标**，
全部 **62 份 CSV 与 `39a4545` 逐字节一致**，判定和生效设置也一致。
原 DUT、刺激、阈值、checker 和分母均未改。本轮没有新 Spectre 执行或重分析；
下方 Spectre 对照保留历史归属。

[开发检查收据](results/accuracy-optimization-checks.json)：**364 Python、82 Rust** 测试通过，
另有一项计时探针在常规 Rust 测试中明确 ignored，已在专项计时中显式执行。
locked build、all-targets Clippy `-D warnings` 和格式检查通过。
新增独立验证包括高精度三次根的正/负导数方向、反馈放大拒绝、严格盒端点与溢出拒绝，
以及不可变查询、复位/transition 正弦重算和丢弃候选后的重试。
首轮新增 Rust 夹具误用了 IR 枚举名 `idtmod`，修正为 `idt_mod` 后全套通过；原失败日志保留。

原始请求、release 探针、debug 内核、全部计时、失败与矩阵日志、源码归档和原始清单位于
ignored 的 `runs/accuracy-optimization-20260930T175927Z-b2a5e8/`，可用性为 **仅本地保留**。
整理收据与源码在本地 Git；未将该目录发布为公开复现包。
正式资格仍为 **I**，没有新增连续时间精度资格或未见确认集结论。

<a id="gap-completion"></a>

## 2026-10-01：剩余六条件补齐与联合验收

当前候选为本地 `test/evas-gap-integration`，运行时固定于
`39a4545c34fb22b1bd69731ca6b8bd8852b0e9dd`，包版本仍为 0.9.0，格式统一为 **IR v15**。
已同步当前 main `78e914ff97d4902365b76d5c3c87be57c39c83e9`、analog 验收修复以及
滤波 `4389640`、相位 `11f49d2`、非线性 `227c77c` 候选。未发布、未合入 main。
旧 IR 必须从原始 VA 重新编译；不得修改归档 JSON 的版本号冒充迁移。

原 31 条件的基础档与细化档均 **31/31 有限观测达标**。相对 analog 基线 `9c5d6c5`
的各 25/31，新增的是以下六条；原达标 50 份 CSV 逐字节一致，无退化。
相对已合并 PR26 检查点的各 24/31，还包括已经在 analog 候选补齐的 `v1-main`。

### 分批 review 的数学与实现入口

| 顺序 | 本轮补齐 | 数学原理与精度处理 | 重点入口 |
| --- | --- | --- | --- |
| 1 | `v6-standard`、`c2-main`：常量数组、一阶 `laplace_nd`、滤波采样级联 | 对 `b0/(d0+d1*s)`，令 `τ=d1/d0`、`g=b0/d0`，解 `τy′+y=gu`。直接 PWL 每段使用解析响应，DC 初值为 `gu(0)`；原始系数、时间差和指数余项的区间进入历史及电压验收 | [数学契约](../../evas/validation/LAPLACE_CONTRACTS.md)、[laplace.rs](../../evas/rust_core/src/laplace.rs)、[独立 Decimal 回归](../../evas/tests/test_laplace.py) |
| 2 | `d2-constant`、`d2-chirp`：内建 constants 宏、`idtmod` 与受限 `sin` | 先累计 `z=ic+∫u dt`，查询 `offset+(z-offset) mod modulus`。原始累计相位独立保存；wrap 边界用精确 product-sum 符号或保守区间。正弦分别包围 wrap 两侧，再取并集，不把浮点 `2*M_PI` 当作数学精确周期 | [算子数学](../../evas/docs/OPERATORS.md#idtmod-与-sin)、[idtmod.rs](../../evas/rust_core/src/idtmod.rs)、[operators.rs](../../evas/rust_core/src/operators.rs)、[Fraction/Decimal 回归](../../evas/tests/test_phase.py) |
| 3 | `v7-nonlinear-0.5`、`v7-nonlinear-2.0`：无历史非线性瞬态 | 每个请求时刻独立解 `F(v,u(t))=0`；前一个成功解只作 Newton 初猜。非点输入包围使用原 RHS 的区间 Jacobian 与 Krawczyk `K=x−CF(x,U)+(I−CJ(X,U))(X−x)`，证明 `K⊂int(X)` 且收缩范数 `<1` 后接受 | [精度契约](../../evas/validation/NONLINEAR_TRANSIENT_CONTRACT.md)、[solver.rs](../../evas/rust_core/src/solver.rs)、[高精度根与反例](../../evas/tests/test_nonlinear_transient.py) |
| 4 | 共同入口与组合修复 | 仿射关系保留原 forward-error map；普通条件先认证原 PWL 谓词。全部历史仍从已接受 Frame 重放，试算失败不提交。reset 后允许依赖它的纯 `sin` 同刻重算，不能跳过重新求解及验收 | [analog.rs](../../evas/rust_core/src/analog.rs)、[reset_dependencies.rs](../../evas/rust_core/src/reset_dependencies.rs)、[组合回归](../../evas/tests/test_gap_integration.py)、[实际 Frame 弃候选/重试](../../evas/rust_core/src/transient_idt_tests.rs) |

整合没有另造一套算子执行器。统一 IR 的同时，扩展原有结构依赖图，让新算子中的
复位反馈仍明确拒绝；不能通过 `sin`、局部别名或相消隐藏反馈环。
同刻重算权限只沿实际改变且已获许可的 reset 算子依赖传播；每次仍从相同已接受历史
重算全部候选值、区间、复位状态与电压方程。新增失败后弃候选/重试回归验证这一点。

无状态入口现由 `Analog` 统一分流：仿射系统用已有电压误差映射，纯多项式用 Newton
及其认证；添加无作用的普通条件不能绕过或额外禁用精度检查。缓存只保存同一分支的
表达式/模型/电路结构，不缓存输入、解或物理历史；输出查询不增加 `accepted_steps`。

### 新执行、复用与验收结果

[完整 31 行矩阵](results/gap-completion-matrix.md)、[逐配置收据](results/gap-completion-current.json)
和[开发检查收据](results/gap-completion-checks.json)分别记录行为条件、设置与检查方法。
原 DUT、刺激、两档目标、检查器与分母未改。

| 证据 | 基础档 | 细化档 | 使用方式 |
| --- | ---: | ---: | --- |
| analog 候选 `9c5d6c5` | 25/31 | 25/31 | 复用原收据作兼容基线 |
| 联合候选 `39a4545` | **31/31** | **31/31** | 本轮 62 次新 EVAS 执行 |
| Spectre 21.1.0.509.isr12 | 31/31 | 31/31 | 复用上一轮 62 次执行，核对输入/工具/设置/清单并重新判定全部导出波形 |

首次联合矩阵在 `493c292` 已两档各 31/31；之后补入实际 reset→sin 回退测试、
Clippy 等价改写与无状态步数语义修复，并在最终 `39a4545` **重新执行完整矩阵**。
首次 Clippy 失败日志及开发期失败记录保留，不能把早期通过当成最终源码通过。

最终检查：**362 Python、79 Rust** 回归通过；locked build、all-targets Clippy `-D warnings`
与格式检查通过。独立设计数学、9 项动态数学及冻结资产身份检查也通过。
另有静态回放 12 条件×两档、24 配置共 **528,024 静态点**通过；其余 19 条动态条件
由该独立静态入口明确跳过，不是额外的瞬态矩阵失败或新增条件。

执行内核 SHA256 为
`d59822b07aad389df40559297a328639b484ba2e3512ada0009a7576078ca167`。
原 checker SHA256 为
`189f9102244ad2804338a0ac2dc1a030db9dedd6cf1570e273b3622c96454d6b`。
收据绑定原输入清单、实际运行源码、内核、波形、请求与生效设置，
[analyze.py](analyze.py)验证这些身份后调用原独立 checker；没有放宽阈值。

### 支持边界与复现

这次补齐的是原矩阵剩余条件所需的受限能力。高阶/动态系数滤波、积分输入反馈、
动态算子驱动 cross、非线性与事件/历史的联合求解、任意函数/宏/数组仍未交付。
普通 analog 条件的非线性分支叶仍拒绝；本轮非线性瞬态不含普通条件或动态状态。
非点输入的多项式包围限定方形单来源分支系统；点输入目前使用原区间残差及名义
Newton 验收，没有额外 root-box 前向误差证明。病态或一般多解系统不能由本轮成绩保证。

正式 DVS 资格仍 **I**；有限观测、代码内认证和开发反例不等于全时域误差资格。
原 31 条件已用于开发，后续应另冻未见确认集。本轮未测速度，也未新启动 Spectre。

源码、数学契约、分析程序和整理结果在本地 Git 检查点；大波形、二进制、测试日志、
失败记录及实际运行源码归档保存在 ignored 的
`runs/gap-completion-20260930T165211Z-3154da/`，可用性为 **仅本地保留**。
完整原始文件清单及哈希由开发检查收据链接；未上传，不称为公开复现数据包。

取得收据绑定的原始目录后，可运行以下重分析（变量指向原始归档，输出使用新路径）：

```sh
python3 -B experiments/parallel-gap-integration/analyze.py \
  --source "$spectre_inputs" --run "$matrix_run" --identity "$runtime_identity" \
  --output "$new_analysis" --spectre "$spectre_exports" \
  --baseline experiments/pr14-pr15-validation/results/analog-conditions-acceptance-review.json \
  --spectre-receipt experiments/pr14-pr15-validation/results/analog-gap-spectre-comparison.json
```

新执行时用 `experiments/pr14-pr15-validation/matrix.py evas --source INPUTS --root NEW_RUN --kernel KERNEL`；
前端/运行时需切到收据固定源码并重新从 VA 编译 IR，使用新的目录与运行身份。
分批审阅完成前，main 的已合并范围及历史成绩保持不变。

## 以下为保留的历史复审

以下段落保留各轮当时的基线、候选、失败与结论；当前联合状态以本节为准。

主分支比较基线：`508f5b924360a48c66b569a1719157a883d1db9f`。
本页记录 2026-09-30 的实际复审；候选仍在本地，未发布新 PR、合并 main 或发布 tag。
原联合检查点及其 30/31 结果保留在 [README](README.md)，不将新专项结果改写为新联合成绩。

## 首批候选：多事件写者

分支 `feat/evas-multiple-event-writers`，head `bfaf8d3b2696a362f6209259ba520356485552fb`，生产代码固定于
`144d8b0d90f4812fa4924597bcb0c1fa1337f20e`；后两次提交只整理收据路径与主分支/候选能力登记。
比较 `508f5b9..bfaf8d3`。IR 仍为 9，无新增运行时依赖。

原先两个事件块只要可能写同一状态就被静态拒绝，导致正常的上下阈值迟滞也不能运行。
现在先认证候选批次的条件路径，再检查实际写集合。对状态 q 与批次 B：

```text
W(q,B) = { event block | its selected path actually assigns q }
accept the writer check iff |W(q,B)| <= 1 for every q
```

不同批次分别写 q 合法；同一块的顺序赋值仍属于一个写者。同批两个块写 q 则整批
`event_conflict`，即使写入值相同。没有按源码顺序决定跨块优先级。OR 的同块去重沿用已有实现。
此检查发生在候选求解和正式历史提交之前；已接受 Frame 作为试算起点，失败不会消费事件或修改历史。

跨块读取仍明确拒绝。复审发现 `q-q`、`0*q`、下溢系数可绕过非零系数检查，
`144d8b0` 已改用保留的结构依赖；前端与 raw IR 均有回归，同块顺序更新仍保留。

### Review 入口与范围

- [events.rs](../../evas/rust_core/src/events.rs)：潜在写者集合、结构读取拒绝、实际 Selection 写者检查。
- [settlement.rs](../../evas/rust_core/src/settlement.rs)：认证路径后、求解前的检查位置。
- [test_event_writers.py](../../evas/tests/test_event_writers.py)：迟滞、保持、实例排列、选中路径、相同值冲突与结构读取反例。
- [transient_condition_tests.rs](../../evas/rust_core/src/transient_condition_tests.rs)：实际 Frame 失败回退及 raw IR 拒绝。

阅读单项差异时切到 `feat/evas-multiple-event-writers` 的固定 head；下方临时联合版本
已同步这一轮修复，但包含其他未批准能力，不能作为这项 PR 的完整差异。单项最终差异涉及 9 个文件；生产逻辑仅
`events.rs` 与 `settlement.rs`，合计新增 27 行、删除 9 行，其余为测试、契约和紧凑收据。

### 验证与结论

子线程报告：86 项相关 Python、58 项 Rust、构建及格式检查通过。
主线程在固定生产 head 上另重跑 7 项 writer Python 与 1 项实际 Frame rollback Rust，均通过；
核对内核、checker、worker、两档 DUT/condition/settings/waveform 哈希，与新 V3 收据全部一致。

原 V3 的冻结输入、两档设置和独立 checker 未改；两档均 `observations_within_targets`，
分别 4,001 / 40,001 个观测点，最大观测电压误差约 `2.04e-14 / 2.12e-14 V`。
收据位于候选分支 `experiments/pr14-pr15-validation/results/event-writers-v3-branch.json`。
运行真实发生在旧 head 加未提交修复上，运行后修复提交为 `144d8b0`；收据保留当时的 dirty 身份，
不冒充 clean commit 执行。这份分支专项当时未新执行 Spectre；后续新对照见下节。
raw 与冻结输入仍 local-only，正式资格 I；未作性能测量。

结论：该受限写者策略、调用位置与失败完整性没有新的阻塞发现，可先交用户 review。
最终交付仍需用户审阅和实际目标 main 的依赖同步；本结论不授权合并。

### 后续补充：V3 与 Spectre 的新执行对照

`event-writers-spectre-20260930-01` 固定同一候选 `bfaf8d3`，干净工作树，内核 SHA256
`b3cf1d076325dea136ac806823f9f78d434f174b9199fd9d6a1ed8710cedcd83`。
原 V3 DUT、condition、两档 settings、Spectre 网表逐字节复制自原冻结输入；原 checker 未改。
本轮 EVAS 与 thu-sui 的 Spectre **21.1.0.509.isr12** 各新执行两次，共四次，未复用旧波形。
沿用原 Spectre runner，只将案例数、输出数断言与预算元数据缩减为 1 条件 / 2 次；
单线程、单 CPU，90 s/次、30 s license 等待上限。实际 stop、step、maxstep、method 与
reltol/vabstol/iabstol 均已从 Spectre 日志核对，全部匹配原请求。

| 档位 | EVAS / Spectre 点数 | 独立验收 | 平台误差 | 两波形最大插值差值 |
| --- | ---: | --- | ---: | ---: |
| 基础 | 4,001 / 4,006 | 两者均 observations_within_targets | 两者 0 V | 4.0000 mV |
| 细化 | 40,001 / 40,006 | 两者均 observations_within_targets | 两者 0 V | 0.65250 mV |

原独立答案中，两次迟滞更新的名义时刻为 1.375 / 3.375 μs；输出从 0.1 V 到 0.9 V，
边沿时长 50 ns。基础档从 Spectre 的输出 50% crossing 推算起点约晚 0.25 ns；
细化档约晚 0.03140 / 0.04078 ns。这些是输出边沿估计，不是直接读取内部事件时刻。
边沿斜率为 `0.8 V / 50 ns`，故 0.25 ns 位移对应约 4 mV 名义波形差值。
原合同允许事件起点晚至 0.5 ns，原 checker 用所有导出点检验是否存在共同允许事件历史；
不能把原电压目标理解为每个点都必须贴合名义零时间偏差波形。两者的共同历史检查均为 P，
正式观察资格仍为 I，未证明未观测时刻的误差。

结论限定为正常 V3 迟滞：平台与事件历史相容，边沿存在可解释且细化后减小的数值差异；
不能声称逐点一致、Spectre 出错、EVAS 普遍更准确或同刻多写语义已对齐。
本轮未新增同刻跨块实际写冲突的 Spectre 诊断、完整 31 矩阵或速度测量。

新收据见 [V3 对照](../pr14-pr15-validation/results/event-writers-spectre-v3.json)，
重分析入口为 [event_writer_compare.py](../pr14-pr15-validation/event_writer_compare.py)。
8 项原 checker 校准检查另通过。原始波形、远端清单、运行器快照及候选源码归档仅本地/thu-sui 保留，
不称为可公开下载的复现包。

<a id="v3-cross-timing"></a>

### V3 差异定位：cross 容差与时间步

`event-writers-timing-20260930-01` 在相同 thu-sui 环境及 Spectre **21.1.0.509.isr12**
上新执行六次：基础/细化档各一个事件日志配置，另有四个基础档控制配置。
每次仍为单线程、单 CPU、90 s 执行及 30 s license 等待预算。先冻结输入和配置计划，
保留原 DUT 与原收据；诊断配置单独计数，不是原 31 矩阵的新单元，也没有新执行 EVAS。

日志配置只在两个事件体中增加 `$strobe`，打印 `$abstime` 与更新后的 q。
其两档导出波形的时间、输入、输出均与上一节对应 Spectre 基线逐值完全一致，
日志时刻也与输出 50% 推算的起点一致，因此本例差异不只是导出或插值造成的假象：

| 档位 | 上升事件日志 / μs | 下降事件日志 / μs | 相对名义零点的延后 / ps |
| --- | ---: | ---: | ---: |
| 基础 | 1.37525 | 3.37525 | 250 / 250 |
| 细化 | 1.3750313958334245 | 3.3750407812471904 | 31.39583 / 40.78125 |

日志确认 q 按 0→1→0 更新。下表控制实验的时间来自输出边沿估计；并未增加事件日志。
`solver-tolerances-only` 同时收紧 reltol/vabstol/iabstol，属于一组全局精度控制，
不能称为单一标量参数实验。其余控制各只改变列出的设置。

| 配置 | 相对基础档的改变 | 上升 / 下降延后 / ps | 最大名义输出误差 / mV |
| --- | --- | ---: | ---: |
| 原基础档，加事件日志 | 日志无观测扰动 | 250 / 250 | 4.000 |
| maxstep-only | maxstep：1 ns→0.1 ns，step 仍 1 ns | 约 0 / 100 | 1.600 |
| cross-vtol-only | cross expr_tol：200 μV→2 μV | 2.5 / 2.5 | 0.040 |
| cross-ttol-only | cross ttol：1 ns→1 ps | 0.5 / 0.5 | 0.008 |
| solver-tolerances-only | reltol/vabstol/iabstol 分别收紧 1000 倍 | 250 / 250 | 4.000 |

六个配置的平台误差均为 0 V，边沿时长估计均为 50 ns（舍入误差以内）。
独立名义根为 1.375 / 3.375 μs。输入斜率绝对值为 `4e5 V/s`，
原事件窗口为 `min(1 ns, 2e-4 V / (4e5 V/s))=500 ps`。
基础档晚 250 ps 触发时，guard 已越过零点 100 μV，仍在原窗口内。
输出边沿斜率为 `1.6e7 V/s`，故 `250 ps × 1.6e7 V/s=4 mV`；
各控制配置实测最大名义误差也与边沿位移乘以此斜率相符。

这些对照支持以下原因链：cross 的实际触发时间不同，transition 随之整体移位，
而其平台与边沿形状保持一致。收紧 cross 容差有效，全局求解容差收紧无此效果；
maxstep 控制的两个边沿不同，说明不能把偏移解释为固定步长比例，或认为只改步长就必然落在零点。
EVAS 当前 PWL/仿射求根及认证方式见[事件手册](../../evas/docs/EVENTS.md#backend-cross-tolerances)。
不由这些观测推断 Spectre 内部完整定位算法，也不把差异归因于新增写者仲裁。

原 checker 未改，六组导出观测均满足**原 V3 合同**；收紧 cross 的控制并未另获其更严格
容差下的正式资格。原合同的允许窗口来自
[LRM 2.4 §5.10.3.1](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
容差内的波形差异不自动构成后端错误；有限观测与内部事件日志也不证明完整连续时间正确性。
正式资格仍 I；未进行性能测量、同刻写冲突诊断或全矩阵重跑。

整理收据为 [event-writers-timing.json](../pr14-pr15-validation/results/event-writers-timing.json)，
重分析入口为 [event_writer_timing.py](../pr14-pr15-validation/event_writer_timing.py)。
原始输入、波形、日志、运行器快照及远端归档仍仅本地/thu-sui 保留。

## 继续处理的精度问题

### idt reset

复审在 `778a667` 确认：`1e16*q+q-1e16*q` 本应等于 q，却被合并系数舍入成零。
q 初值 1、t=2 归零、输入恒 1、IC=.25，原实现接受 `[.25,1.25,2.25,3.25]`，
正确应为 `[.25,.25,.25,1.25]`。`26164ce` 已保留原 reset 树并认证未合并 product-sum，
`7ecf652` 同步真正依赖的 event writer `144d8b0`。

但 `7ecf652` 仍有嵌套乘积反例：

```text
reset = (0.1*q)*0.1 - 0.010000000000000002*q
```

对 q=1，原 binary64 常数的精确实数解释为非零：
`Fraction(.1)^2-Fraction(.010000000000000002) = -1080863910568919/1298074214633706907132624082305024`。
主线程重现了同样的错误输出，原因是系数乘法先舍入、随后把舍入系数当作精确值认证。
`466d63c3269aaa0dfbf8580e776cdc0541062ceb` 已补每次系数乘积的 exact 资格检查，
常数合并也要求可证明精确；否则从原树作区间回退，跨零明确拒绝。
主线程重跑 source/raw IR 的两类相消与嵌套乘积共 4 项回归，均通过。
子线程另报告 274 项 Python、61 项 Rust，以及 D1 free/reset 两档四次专项均观测达标。
原 `1e16*q+q-1e16*q` 可正确运行，嵌套非精确系数的反例会保守拒绝。
该有界实现可以作为多事件写者后的第二项 review 候选；不同于支持任意 reset 代数化简。

### 无状态瞬态的反馈放大

`0063f82` 补了 exact-PWL 输入区间下的支路残差检查，能拒绝原 `y=1e16*(u-1)` 反例，
但残差不等于输出误差。主线程在该 head 又重现：

```text
y = a*y + (u-1), a=0.99999999999999
u: (0,1), (3,nextafter(1,+infinity)); observe t=1
vabstol=1e-12, reltol=0
```

精确有理数答案为
`(Fraction(nextafter(1,+inf))-1)/3/(1-Fraction(a)) = 1/135 V`，
内核却接受 y=0。输入残差很小，但 `(1-a)^-1` 将其放大约 `1e14` 倍。
`4a903d4` 的固定 Jacobian 灵敏度检查已拒绝这个反馈反例，但固定点导数不能独自给出
非线性根移动的严格上界，普通浮点逆与误差累加也不自动成为可靠包络。
名义 Newton 收敛、原关系区间残差和一阶灵敏度不能单独代替根误差的证明。

最终候选固定于 `227c77cbc29f35584ea7a7fe7fa686ebb65543d3`：非点输入使用 square Krawczyk
预算盒，浮点逆只作预条件器，要求区间映射严格内含盒且收缩。复审提出的 `X-x` 减法、
范数累加已采用外扩区间运算；残差与 Jacobian 从保存的 `Equation.original_rhs` 求值。
没有放宽重复 affine terms 的原 invalid-IR 规则；相消反例使用合法原始 Add 树，另保留非法重复项拒绝回归。

主线程在最终候选的实际内核上重跑上面的 `1/135 V` 反馈反例，结果为 `waveform_accuracy` 拒绝。
子线程报告 41 项相关 Python 通过；外扩与原树修复后另有 57 项 Rust，以及 V7 两条件两档共四次正向回放。
最终恢复 IR 校验的提交另重跑合法 Add 树与重复项拒绝测试。

此项可以进入单独 review，不能宣称总电压精度已补齐：非点输入证书仅限无事件/历史/状态、
方阵、单 origin 的既有多项式路径；点输入仍只有原关系区间残差验收，不提供根包络或前向误差证明。
它尚未合入下方临时组合版本，专项证据不能替代组合后的检查。

## 更新后的临时组合检查

联合运行时固定于 `fc106879e40e993fa5fe41fd07151f8f96a8d358` / IR14，
内核 SHA256 `77e740300eb43992d5978f5e7c6dbab5217efa3d9282c18de9c77a981f941581`。
合入 event writer `87491e8`、reset `466d63c`、phase `11f49d2`，未合入上述非线性精度修复。
解决共享接口时保留相位 helper，给 reset 判定的 `Select` 明确拒绝；raw phase 边界证书
遇到带 reset 的 idt 必须退出，不能无视其释放历史。

58 项相关 Python（含 8 项跨能力组合）、75 项 Rust、构建及 all-targets warnings-as-errors
检查通过。详细范围及 Clippy 工具链组件缺失记录于 [checks](results/review-checks.json)；
本轮没有把它写成 Clippy 通过，也没有重复完整 Python suite。

原 V3、D1 free/reset、D2 constant/chirp 五条件、两档共 10 次新本地请求、220,010 个导出观测点均
`observations_within_targets`，仍复用原 INPUT_MANIFEST 与独立 checker。
新 [专项收据](results/review-affected.json) 独立保存实际执行 commit、干净状态、内核和源码哈希、
输入/设置/波形身份；raw local-only。这不是全矩阵 31/31 或连续时间精度的证明。

## 其他候选与顺序

- analog 条件：固定 `134280e`，已有独立 Fraction 分支/顺序/结构依赖与原 V1 两档正向证据。
- 一阶 laplace：固定 `4389640`，已有带余项的指数界、原系数/时间区间与原 C2/V6 四次正向证据。
- phase：`11f49d2`，新增原相位 wrap 侧的精确符号证书；专项 D2 constant/chirp 两档均观测达标。
  near-wrap 测试已改为从原 binary64 常数作 Fraction 积分/modulo，half-ulp 错侧代表值仍保守拒绝。
  这不是联合 31/31 的新证据。

先 review 多事件写者；idt 以 `466d63c` 的修复与实际父依赖接续。analog 条件、一阶滤波和相位
分别保留独立范围，交付时统一共享 IR/前端接口并补受影响组合验证，不把临时联合分支直接当成一个大 PR。
