# EVAS 加速外部调研：同类软件做法与数学原理（issue #138 候选扩展）

日期：2026-10-17。性质：只读调研 + 报告写作，不改动代码、不 commit。基准与内部热点画像取自 `2026-10-17-evas-acceleration-analysis.md`（main `e2c7aac7`：nonlinear_idt ≈ 222 ms 主导；`implicit_dynamics.rs` 每步重建稠密区间 Jacobian；`events.rs`/`settlement_bounds.rs`/`transition_source_plan.rs` 事件全量重建；`operators.rs` 每 trial 全量 clone）。

红线（全篇适用）：不削弱认证区间包含性；不改变模型语义、事件顺序与历史要求；改变浮点次序/包围/收敛路径标 B；改变时间推进与误差分配标 C；B/C 类验收必须用精确有理数或独立高精度答案检查区间包含性，名义输出接近不算证书。

## 结论摘要：最值得进 #138 清单的 5 条

按"数学上为什么省 + 与现有瓶颈对齐 + 风险可控"排序：

1. **E1 仿射算术（AA）作为区间认证的第二种外包络表示**（对应 P04，风险 B）。区间法在 EVAS 的区间 Jacobian、误差传播和历史继承中都会因"相关误差被当独立"而膨胀，直接导致更多步长收缩/分裂。AA 显式追踪误差符号相关，`x - x = 0` 精确为零。EVAS 每步重建的稠密区间 Jacobian 正是相关性丢失的重灾区。与红线兼容的关键：AA 得到的仍是严格外包络，包含性不弱于区间法（通常更紧），可用现有"精确有理数积分验证包含性"的验收管道。
2. **E2 符号 LU 复用扩展到"结构不变的非线性区间 Jacobian"**（对应 P03，风险 A 子集/B）。KLU 论文与 ngspice/Xyce 实践的核心：电路矩阵跨步稀疏模式几乎不变，符号分解（排序+选主元计划）做一次，数值因子化逐步刷新。EVAS `implicit_dynamics.rs` 每步从头重建稠密 `Vec<Vec<I>>` Jacobian 并重解，同一模型跨步/跨候选符号结构不变时，"结构识别 + 复用消元次序（保持浮点顺序不变）"是 A 类子集。
3. **E3 廉价外包络预筛 + 原认证路径兜底（cheap enclosure / 分层认证）**（对应 P04/B5，风险 B 组织上近 A）。validated ODE 文献（Lohner AWA、Corliss 综述）的标准结构：先用粗糙但严格的 a priori 包络筛掉"明显安全"的步，只有包络不够紧时才做昂贵的 Krawczyk/区间 Newton 认证。与红线兼容的形态：预筛只用于"提前拒绝快路径分支/少分裂"，最终接受的证书仍由原路径产出——EVAS 的单未知量中值定理路径已是类似思想的实例，可推广。
4. **E4 事件定位的导数/插值复用**（对应 P05/P06，风险 A/B）。Shampine 事件定位理论：符号变化后用已有步内多项式插值（不是重新积分）定位 t*，guard 的导数信息可把迭代次数从纯二分的 O(log(1/ε)) 降到几次。EVAS `events.rs` 每次事件全量重建 Spec，若 guard 求值与导数已在该步算过（`GradientJets` 基础），定位迭代可复用；只要不改变定位精度判据和事件顺序语义，属 A/B。
5. **E5 批量小矩阵核 + SIMD 区间运算（限非认证路径或证明区间仍包住）**（对应 P16/B2，风险 B）。KLU 之后的 batched BLAS 研究（UTK ICL、LIBXSMM）表明小矩阵批处理是数量级收益来源；Goualard 的 SIMD 区间算法解决了舍入方向混合的难题。EVAS 多候选 trial 的区间求值天然批量化。认证路径改变浮点归约次序，必须走包含性验收，或保持认证原路径（见 B5 分层）。

不推荐近期做：GPU 数值核（P16 条件未变，PrimeSim 的 GPU 收益依赖大规模 PLL，EVAS 当前案例规模证明不了传输成本抵消）；Taylor models 全套（E1 的远期上位替代，实现复杂度高，见层面二讨论）；增量 LU rank-one 更新（归入 P02/P03 的 #57 测量后启动条件，SMW 的适用前提是扰动低秩，电路 Jacobian 跨步变化通常是全矩阵小幅变化，低秩性无证据）。

## 层面一：同类软件的做法（一手材料）

### Cadence Spectre / APS / Spectre X（商业）

- 经典 Spectre 单线程；多线程属于 APS/Spectre X（`++aps +mt=N`），Spectre X 分布式扩展到多机，Spectre FX 宣称 32 核最高 3×。用户实测收益高度依赖规模（大版图后仿收益高，小电路仅 ~25%）。
  - 来源：[Cadence 论坛 thread](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/41116/spectre-tran-simulation-and-multithreading)、[Spectre X 分布式博客](https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-tech-tips-increase-performance-and-capacity-using-spectre-x-distributed-simulation)。
- 对 EVAS 的启示：多线程是 P12/P16 的方向，但商业工具的证据表明**小规模收益有限甚至负**——与 issue #138 的"测调度成本"启动条件一致，不构成提前启动理由。
- ALPS 两份官方 PDF 已在 issue #138 附链接（智能矩阵求解、并行、步长控制、内存管理、断点续仿），此处不重复；ALPS 佐证的是 E2/E4 类"减少重复符号工作"，而非数值捷径。

### Synopsys PrimeSim / HSPICE（商业）

- 公开材料：PrimeSim SPICE 的 GPU 加速博客宣称 PLL 仿真最高 28×；HSPICE 多线程瞬态的 "similarity" 类特性只在授权手册/发布说明中公开，公开渠道无细节。
  - 来源：[PrimeSim SPICE GPU 博客](https://www.synopsys.com/blogs/chip-design/accelerating-accuracy-primesim-spice-gpu.html)、[PrimeSim HSPICE 产品页](https://www.synopsys.com/implementation-and-signoff/ams-simulation/primesim-hspice.html)、[HSPICE User Guide（公开旧版 PDF）](https://cseweb.ucsd.edu/classes/wi10/cse241a/assign/hspice_sa.pdf)。
- 启示：GPU 路线的公开收益全部来自**大规模、长时间、器件求值主导**的负载；EVAS 当前瓶颈是 200 ms 级认证密集请求，画像不匹配。

### Xyce（开源，Sandia）

- 从头为大规模并行（MPI）设计：器件求值与矩阵组装分布化、稀疏解算器（Trilinos）并行。用户指南与参考指南为一手材料。
  - 来源：[Xyce Users' Guide 7.6 PDF](https://xyce.sandia.gov/files/xyce/Xyce_Users_Guide_7.6.pdf)、[Xyce GitHub](https://github.com/Xyce/Xyce)。
- 启示：Xyce 的收益同样以数千节点以上电路为前提；对 EVAS 更可借鉴的是它**器件求值与求解器解耦的分层结构**——对应 P05"事件后只重建受影响关系"的模块边界设计。

### ngspice / OpenVAF（开源）

- OpenVAF：基于 LLVM 的 Verilog-A AOT 编译器，编译产物（.osdi）运行时加载，速度"与内置 C 模型相当、有时更快"。核心技术是编译期公共子表达式消除、死代码消除、强度削减和算子向量化（`ddx` 导数走 LLVM 自动微分式生成）。
  - 来源：[ngspice OSDI 页](https://ngspice.sourceforge.io/osdi.html)、[OpenVAF performance](https://openvaf.semimod.de/docs/details/performance)、[OpenVAF GitHub](https://github.com/OpenVAF/OpenVAF-Original)。
- ngspice 的 KLU 后端跨步复用稀疏矩阵的符号结构与选主元次序（refactorization 只做数值更新）。
- 启示：**编译期对模型表达式做 CSE + 预计算导数**正是 EVAS 内部分析 B3（`expression.rs` DAG 预编译、`direct_derivative.rs` 雏形）的外部佐证；ngspice KLU refactorization 是 E2 的直接先例。

### 数值库

- **KLU**（Davis & Natarajan, ACM TOMS 2010, Algorithm 907）：专为电路矩阵设计——Gilbert-Peierls 左看 LU + COLAMD/AMD 排序 + BTF 块三角置换；关键洞见是电路矩阵的稀疏模式跨 Newton 迭代/跨时间步几乎不变，符号分析与排序只需做一次。来源：[ACM 论文 PDF](https://dl.acm.org/doi/pdf/10.1145/1824801.1824814)、[KLU User Guide](https://users.encs.concordia.ca/~krzyzak/R%20Code-Communications%20in%20Statistics%20and%20Simulation%202014/Zubeh%C3%B6r/SuiteSparse/KLU/Doc/KLU_UserGuide.pdf)。
- **Batched BLAS / 小矩阵核**：UTK ICL 的 batched 小矩阵分解、LIBXSMM 运行时代码生成的小 GEMM。来源：[Batched BLAS 报告](https://icl.utk.edu/files/publications/2016/icl-utk-909-2016.pdf)、[LIBXSMM](https://dl.acm.org/doi/10.5555/3014904.3015017)。对 EVAS：多候选 trial / 多 RHS 的稠密小区间运算可批处理（E5）。

## 层面二：数学原理方向

### M1 仿射算术（Affine Arithmetic）——对应 P04，风险 B

数学依据：经典区间算术把每个量表示为 `[lo, hi]`，同一变量两次出现的误差被视为独立（dependency problem）：`(x+1)-x` 区间宽度是 2 而非 0。AA 把量表示为 `x0 + Σ xi·εi + rk`（εi ∈ [-1,1] 的独立符号噪声），相关误差共享同一 εi，相减时精确抵消。Stolfi 等原始论文与后续验证 ODE 工作表明：对逐步误差累积问题，AA 的界随步长线性收紧，而区间法的宽度按指数膨胀（wrapping effect），这直接决定可用步长与分裂次数。
- 为什么对 EVAS 省：`implicit_dynamics.rs` 的区间 Jacobian、`continuous.md` 的误差传播链、历史继承误差都在做大量"区间×区间"运算，相关性丢失造成的过度保守是**认证拒绝/缩步**的直接来源。更紧的包络 = 更少的重试、更大的可用步长、更少的候选分裂。
- 红线/验收：AA 仍是严格外包络（每步做一次区间化得到经典区间即可），包含性不弱化；但所有舍入处理改道，属 B 类——必须用精确有理数/独立高精度答案验证包含性与拒绝边界，覆盖放大、相消、非点输入、继承历史与应拒绝案例。
- 来源：[Stolfi 等 AA 论文](https://tema.sbmac.org.br/tema/article/download/352/291)、[Nedialkov：IA/AA/Taylor 对比（验证 ODE）](https://scholarworks.utep.edu/cgi/viewcontent.cgi?referer=&httpsredir=1&article=1276&context=cs_techrep)、[CMU 用 AA 做浮点误差界](https://users.ece.cmu.edu/~rutenbar/pdf/rutenbar-intervalicassp03.pdf)。

### M2 Taylor models（远期上位替代）——对应 P04，风险 B/C

数学依据：把解表示为"多项式 + 区间余项"，多项式系数追踪各阶相关性，余项吸收高阶与舍入误差。Berz/Makino（COSY）与 Neher 的结论：在依赖问题丰富、长时积分场景下 Taylor models 显著优于纯区间法。代价是数据结构与算子实现复杂（乘法后要"garbage collection"截断高阶项）。
- 对 EVAS：`continuous.md` 的联合状态方程误差传播理论上最受益，但这是对认证内核的整个重写，短期只作为 E1 之后的路线图项。
- 来源：[Neher：Taylor Model ODE 积分](http://www.cs.toronto.edu/pub/reports/na/Taylor_Models_ODES_2006.pdf)、[VSPODE（Lin & Stadtherr）](https://academicweb.nd.edu/~markst/lin-stadtherr-vspode-apnum.pdf)。

### M3 Krawczyk vs 区间 Newton 代价 + cheap enclosure 预筛——对应 P04/B5，风险 B

数学依据：Krawczyk 算子 `K = x - CF(x) + (I - CJ(X))(X - x)` 只需算一次区间矩阵乘（C 固定），不必像区间 Newton 那样每迭代解区间线性系统——这正是 EVAS `solving.md` 已选 Krawczyk 的原因，方向正确。可再进一步的两步：
1. **预条件 C 的复用**：J 变化小时 C 的去偏差作用近似保持，复用 C 省掉一次区间矩阵求逆/分解（浮点 C 只是预条件器，不影响包含性证明的结构，但会改变 K 的数值 → B 类，须重验内含判据的成功率不下降为拒绝）。
2. **cheap enclosure 两层筛**：Lohner AWA 与 Corliss 综述的标准做法——先算粗糙 a priori 包络，若已能证明目标（预算盒内含/步长可行）则跳过精认证。EVAS 的单未知量中值定理路径（`solving.md`）已是实例。推广方向：粗包络由上一步误差区间外推（保持向外舍入），只有粗筛失败才做全量 Krawczyk 重放。**红线兼容形态**：粗筛结果本身也是严格区间，最终接受仍以原证书路径产出或被证明包含——绝不能变成"认证也走快路径"。
- 来源：[Corliss：Where Is Validated ODE Solving Going?](https://www.researchgate.net/profile/George-Corliss/publication/2304159_Where_Is_Validated_ODE_Solving_Going/links/02e7e515363ff58c4000000/Where_Is_Validated_ODE_Solving_Going.pdf)。

### M4 结构重分析：LU 增量更新与符号复用——对应 P02/P03，A 子集/B

数学依据：
- **符号复用（推荐）**：稀疏 LU 的代价分符号（排序、fill-in 结构、选主元计划）与数值（因子化）两部分。若矩阵稀疏模式不变，符号部分可完整复用（KLU 的核心假设，电路矩阵满足）。EVAS 现有 `Arc<OnceLock<LU>>` 只覆盖"系数逐位相同的固定矩阵"；扩展到"符号结构不变、数值刷新"的非线性区间 Jacobian，且**保持消元次序与浮点顺序不变**，是 A 类子集（内部分析已列为 P03 首选）。
- **SMW/rank-one 更新（暂不推荐）**：`A' = A + UVᵀ` 时 `(A+UVᵀ)⁻¹ = A⁻¹ - A⁻¹U(I+VᵀA⁻¹U)⁻¹VᵀA⁻¹`。适用前提是扰动低秩。电路 Jacobian 跨步变化通常全矩阵小幅漂移，低秩性无证据；且数值稳定性有条件（[SMW 稳定性分析](https://arxiv.org/html/2504.04554v1)、[Higham 解读](https://nhigham.com/2020/09/29/what-is-the-sherman_morrison_woodbury_formula)）。保持 issue 现有归类：归入 P02/P03 的测量后启动条件，不单独立项。
- 来源：[KLU 论文](https://dl.acm.org/doi/pdf/10.1145/1824801.1824814)、[Hager：Updating the Inverse of a Matrix](https://people.clas.ufl.edu/hager/files/update-1.pdf)。

### M5 事件定位数学——对应 P05/P06，风险 A/B

数学依据：Shampine 事件定位框架：检测 g(t,y) 符号变化后，用**已算好的步内连续表示**（插值多项式）求根，而不是重新积分；若 g 沿解的导数 dg/dt 可得（EVAS 的 `GradientJets` 已提供 guard 导数），Newton/Brent 混合迭代次数远少于纯二分。validated 事件定位（astrodynamics 的 Taylor 方法事件检测）进一步给出区间判据下的严格定位。
- 对 EVAS：`events.rs` 每次事件全量重建 Spec/rebind；guard 求值与导数若能跨"检测→定位→同刻联立"复用（记忆化键含变量值/顺序身份，沿用 `nonlinear_value_memo_tests.rs` 的逐位兼容 oracle），属 A 类；若改变定位迭代起点/收敛路径使定位出的 t* 数值变化，则 B 类（事件边界数值变化但语义顺序不变须单独论证）。
- 来源：[Shampine 等：Event location for ODEs](https://www.researchgate.net/publication/222531143_Event_location_for_ordinary_differential_equations)、[MATLAB odezero 文档](https://www.mathworks.com/help/matlab/math/ode-event-location.html)、[astrodynamics Taylor 事件检测（2022）](https://www.researchgate.net/publication/360098471)。

### M6 编译期技术：CSE + 强度削减 + 区间 SIMD——对应 B2/B3/B7，风险 A/B

数学依据/工程证据：
- OpenVAF 证明 Verilog-A 级模型的编译期 CSE/死代码消除/导数预生成可达到手写 C 模型同级性能。EVAS 对应物是 `expression.rs` DAG 的编译期化与 `direct_derivative.rs` 扩展（内部 B3）；表达式重写会改变浮点结果（B 类），须逐步对照有限差分/原路径区间并保留奇异/非有限回退。
- SIMD 区间运算：Goualard（2008）给出正确的 SSE 区间四则算法（难点是上下界需相反舍入方向，用符号翻转技巧解决）；VILIB（2024）提供可自动向量化的 C++ 区间库。EVAS 的多候选区间求值批量批处理化（batched evaluate，同一表达式多组区间输入）与 `settlement_bounds::dot/prepared_dot` 的批量 dot 是直接对象。**认证路径改变浮点归约次序 → B 类，须包含性验收，或仅用于非认证快路径（分层，见 M3）**。
- 来源：[Goualard：Fast and Correct SIMD Algorithms for Interval Arithmetic](https://hal.science/hal-00288456/document)、[IEEE 1788 合规测试比较](https://arxiv.org/html/2205.11837v1)、[VILIB](https://www.researchgate.net/publication/414829012_VILIB_High_Performance_C_Library_for_Auto-Vectorizing_Interval_Arithmetic)、[OpenVAF performance](https://openvaf.semimod.de/docs/details/performance)。

## 统一的风险/验收/对应模块表

| ID | 候选 | 对应 #138 | EVAS 模块 | 风险 | 验收要点 |
| --- | --- | --- | --- | --- | --- |
| E1 | 仿射算术外包络（认证表示升级） | P04 | `implicit_dynamics.rs`（区间 Jacobian）、continuous 误差传播、历史误差区间 | B | 精确有理数/高精度独立答案验证包含性；覆盖放大、相消、非点输入、继承历史、应拒绝案例；名义波形接近不算数 |
| E2 | 符号结构复用扩展到非线性区间 Jacobian | P03 | `implicit_dynamics.rs`、`nonlinear.rs`、`linear.rs` LU 缓存 | A 子集（保持消元次序与浮点顺序）；重排序则 B | A 子集逐字节一致（含误差区间与事件）；非零模式恒定性先用只读诊断证明；触及消元次序改走包含性验收 |
| E3 | cheap enclosure 两层筛（粗严格包络预筛 + 原认证兜底） | P04/B5 | Krawczyk 重放路径、中值定理单未知量路径推广 | B（组织上近 A） | 最终证书必须由原路径产出或被证明包含；拒绝边界不得前移（原来能证的仍要能证，可允许更多拒绝单独报告）；端到端计预筛成本 |
| E4 | guard 导数/插值复用的事件定位 | P05/P06 | `events.rs`、`transition_source_plan.rs`、`GradientJets` | A（复用不改变计算）/ B（改变定位数值路径） | 复用键覆盖实际依赖（变量值/顺序身份）；事件次数、顺序、边界逐字节一致（A）；B 类须独立定位精度对照与事件语义顺序不变论证 |
| E5 | 批量小区间核 + SIMD（分层） | P16/B2 | `settlement_bounds::dot/prepared_dot/substitute`、多候选 trial 求值、多 RHS 回代 | B | 改变归约次序 → 包含性验收；或 SIMD 只进非认证快路径、认证保持原路径；报告调度/搬运开销，短请求负收益须如实记录 |
| M2' | Taylor models（路线图项，暂缓） | P04 远期 | continuous 误差传播整体 | B/C | 仅作 E1 后续路线登记，不启动 |
| M4' | SMW/rank-one LU 更新（暂缓） | P02/P03 | `linear.rs`/`nonlinear.rs` | B | 低秩性无证据，留在 #57 测量后启动条件内 |
| M6a | 表达式编译期 CSE/预生成导数 | B3 | `expression.rs`、`direct_derivative.rs` | B | 逐步对照原路径区间 + 有限差分；奇异/非有限回退原路径 |
| M6b | 模型特征分派特化内核 | B7 | `linear.rs` 分流、`analog.rs` 入口 | A | 分派判据确定性并记录于响应身份；每条特化内核与通用内核逐位对照 |

## 方法与边界说明

- 外部材料全部来自公开一手来源（官方手册/论文/源码库），链接随文；商业工具的多线程/GPU 内部算法细节（late-mode、similarity）无公开一手文档，相关条目只引用公开可达的论坛/博客/数据表，不臆测内部机制。
- 本报告未修改任何生产代码；bench 数字引自 2026-10-17 内部分析的单机五轮快照，仅作瓶颈画像锚点。
- 各候选立项时仍按 issue #138 验收规则执行：固定分母、交替五轮、按风险类别选逐位/包含性判据、Spectre 对照按项目规则复核。
