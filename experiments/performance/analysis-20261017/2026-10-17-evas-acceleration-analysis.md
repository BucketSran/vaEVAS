# EVAS 加速候选分析与规划（issue #138 恢复探索首轮）

日期：2026-10-17。性质：只读分析，不改动工作区、不 commit、不发布。基准：本地 main `e2c7aac7`（EVAS 0.19.0 / rust_core v0.19.0），工作区干净。issue #138 状态：开放、此前暂停，P14 首切片（PR #141 输入共享）已交付；P03/P05/P14 标注"恢复后优先参考"。

## 结论摘要

- 在当前 main 上重跑 `transient_solver` bench（4097 输出点，五轮）：**nonlinear_idt ≈ 220 ms**（范围 218.6–245.0 ms）是绝对主导案例，idt ≈ 42.6 ms、timer ≈ 24.0 ms、cross ≈ 19.1 ms、pwl ≈ 3.4 ms（pwl 首轮 11.0 ms 为冷启动，弃置）。当前瓶颈画像与 2026-10-11 收据时代基本一致：**候选/回放路径的重复克隆与重建**仍是大头（诊断计数 `history_clone_calls` 当时仍有 24576 次逻辑克隆，输入共享只消掉了输入数组部分）。
- 代码证据集中在三处：(1) `operators.rs` 每个候选 trial 都 `self.base.clone()` 整个 Operators（全部 operator entries + continuous），P14 续片的直接对象；(2) `events.rs`/`settlement_bounds.rs`/`transition_source_plan.rs` 每次事件都全量重建 Spec/投影/消元结构，P05 的对象；(3) `nonlinear.rs`/`implicit_dynamics.rs` 每步每迭代重建稠密 `Vec<Vec<I>>` Jacobian 并 `current.jacobian.clone()`，且注释明确"非线性 Jacobian 不使用 LU 缓存"——这正对 nonlinear_idt 最重案例，属 P03/P11。
- Top3 排序：**P14（历史/候选不可变共享续片）> P05（事件后只重建受影响关系）> P03（固定结构计算复用，先攻非线性 Jacobian/初猜）**，均为 issue 预标注的优先参考项，且都有可切的最小验证切片。
- 清单之外提出 6 个新方向（B 部分），其中"梯度/Jet 记忆化扩展"已有现成基础（`nonlinear_value_memo_tests.rs` 的 `GradientJets` 已按逐位兼容 oracle 验收过），是清单外最便宜的入手点。
- 红线重申：所有方向不改变模型语义、事件和历史要求；认证路径的区间包含性不可削弱；B/C 类不能用名义输出接近替代证书检查。

## 现有测量入口与本轮实测

入口：`experiments/performance/README.md`（static_solver / transient_solver bench + `profile_requests.py` 交替五轮配对协议 + `measure_build.py`）。计时边界为 Python 序列化 → 进程启动 → 内核解析/求解/编码 → Python 解析，**不含 VA 编译、checker 与答案检查**——因此"加速 checker"不影响正式分母（见 B6）。

本轮在 main `e2c7aac7` 实测（`EVAS_BENCH_OUTPUTS=4097 cargo bench --locked --bench transient_solver`，release，五轮，单位 ms）：

| 案例 | 中位 | 范围 |
| --- | ---: | --- |
| pwl | 3.42 | 3.42–5.82（弃首轮 10.98） |
| idt | 42.60 | 42.26–46.00 |
| nonlinear_idt | 222.00 | 218.62–244.98 |
| timer | 24.06 | 23.92–24.62 |
| cross | 19.06 | 19.06–19.18 |

机器噪声无法完全排除，仅供相对排序：nonlinear_idt ≈ 5×idt ≈ 65×pwl。这组数字可直接作为恢复后各切片的"当前基线快照"。

## A 部分：P01–P16 未完成候选的证据化排序

### 排序表

| 名次 | 候选 | 风险 | 一句话理由 |
| --- | --- | --- | --- |
| 1 | **P14 不可变历史共享续片** | A | 24576 次逻辑克隆计数仍在；`operators.rs:1212` 每次 trial 全量 clone；上一切片已验证方法学与收益（173→3.4 ms span） |
| 2 | **P05 只重建受事件影响的关系** | A | `events.rs` Spec/rebind、`settlement_bounds.rs` 消元投影、`transition_source_plan.rs` 每次事件全量重建；timer/cross 案例事件密集 |
| 3 | **P03 固定结构计算复用（非线性路径优先）** | A/B | nonlinear_idt 是最重案例；`implicit_dynamics.rs` 每步重建稠密区间 Jacobian，`nonlinear.rs` Newton 每迭代 clone Jacobian，LU 缓存明确不覆盖非线性 |
| 4 | P11 初猜复用 | B | 依赖 P03 先给出迭代/重试瓶颈证据，暂作 P03 的附属观测 |
| 5 | P04 认证复用/分块 | A/B | 单独切片，须包含性 + 拒绝边界；先等 P14/P05 释放的画像 |
| 6+ | P06/P07/P08/P09/P15/P16/P01/P02/P12/P13 | — | 启动条件未满足（真实负载证明、耦合模型合同、传输成本证明等），维持暂缓 |

### 1) P14：候选/回放历史与 Operators 不可变部分共享（风险 A）

- **依据**：`operators.rs` 中 `Evaluation::observed_after_with_time_proofs` 与候选推进路径每次执行 `self.base.clone()`（诊断 span `history.clone`、计数器 `history_clone_calls` / `history_clone_operator_slots`）。PR #141 只把 `DirectInput` 点列/区间改共享数组，逻辑克隆 24576 次原样保留；`continuous` 已是 `Arc` 但 `restarted_with_time_proofs` 每次重建新 `Continuous`。`Runtime::Transition` 的 source plan、证书缓存（`events_certificate_cache_tests.rs` 表明已部分存在）等不可变部分仍随 clone 复制。
- **切片**：延续 direct-input-sharing 方法学——目标案例 `EVAS_BENCH_CASE=pwl_idt, EVAS_BENCH_OUTPUTS=8193`（上切片已建立 408→281 ms 的敏感分母）+ 本轮 nonlinear_idt-4097。实现限定为"entries 内不可变字段 Arc 化 / 写时复制"，不改任何数值运算顺序。
- **验收**：A 类。五轮交替端到端计时（中位/范围/峰值 RSS）+ 每例新旧内核完整 JSON 响应**逐字节一致**（含事件与误差区间）+ 诊断计数（clone 次数应降、求解/认证次数不变）+ 三角波精确有理数积分包含性 + 校准反例拒绝"区间漏答案"。

### 2) P05：事件后只重建受影响的关系与预测（风险 A）

- **依据**：`events.rs` 的 `Spec::build`/`rebind`/`same_context` 路径与 `settlement_bounds.rs` 的 `substitute`/`from_rows` 每次事件选择后从头重建绑定与消元投影（该文件刚合入的优化只做了"重复 state 检查扫描一次 live 参数"，说明重建路径仍是全量）；`transition_source_plan.rs` 每次 `build`/`for_program` 重新做表达式绑定与 forms 展开。timer-4097（24 ms，33+ 事件）与 cross-4097（19 ms）事件密度高，重建占比可先用诊断 span 量化再动手。
- **切片**：先加只读诊断（不改语义）：按事件记录 Spec rebuild / plan rebuild / 消元投影构造次数与耗时；确认占比后再实施"依赖未变则复用"（`matches_operator_bindings`、`same_certificate`、`proven_equal` 等等价判据已在代码里，可作复用钥匙）。
- **验收**：A 类。依赖完整性是前提：复用钥匙必须覆盖实际依赖（缓存身份 = 操作符绑定 + 选择 + 时间证词）；逐字节一致 + 事件次数/顺序/边界不变 + 查询网格不变 + 独立答案与拒绝案例保持。计时用 timer-4097 / cross-4097 交替五轮。

### 3) P03：固定矩阵/符号结构与不可变计算复用，首选非线性 Jacobian（A/B 混合，切片取 A 子集）

- **依据**：`nonlinear_idt` 是当前最重案例（222 ms，≈5× idt）。`implicit_dynamics.rs:88/208` 每个 restart/step 重建稠密 `Vec<Vec<I>>` 区间 Jacobian 并重新 `solve`；`nonlinear.rs` Newton 迭代内 `current.jacobian.clone()` 且每迭代完整重评估；性能 README 明确"非线性 Jacobian 不使用这个（LU）缓存"。结构常量 Jacobian 的复用（同一模型跨步/跨候选符号结构不变、仅数值刷新）是 A 类子集；若涉及重排消元次序则滑入 B。
- **切片**：nonlinear_idt-4097 单案例。第一步只做"结构识别 + 复用判定"诊断（每步 Jacobian 非零模式是否恒定）；第二步复用结构、保持求解次序与浮点顺序不变。
- **验收**：A 子集逐字节一致；一旦触及区间消元顺序（B），改用精确有理数/独立高精度答案检查区间包含性，覆盖放大、相消、继承历史与应拒绝案例；注意 issue 规则"计数减少不自动称为提速"，端到端交替五轮。P11（初猜复用）在同一切片的诊断里顺带记录迭代次数分布，满足其"必须有迭代/重试瓶颈证据"的启动条件，但不实施。

## B 部分：清单之外的新加速方向

| # | 方向 | 风险 | 验收注意 |
| --- | --- | --- | --- |
| B1 | 梯度/Jet 子表达式记忆化扩展（跨步、跨候选） | A/B | 已有 `GradientJets`（`nonlinear_value_memo_tests.rs`）按"旧算法逐位兼容 oracle"验收的先例——扩展复用域时保留该 oracle；键必须含变量值/顺序身份（现有测试 `does_not_reuse_changed_variables_or_order`）；非有限 Jet 不得入缓存 |
| B2 | 数值核批处理/SIMD 化（`settlement_bounds::dot/prepared_dot/substitute`、稀疏消元 fill-in 更新、多 RHS 三角回代批处理） | B | 改变浮点归约次序，逐位一致不可用；须用区间包含性 + 独立有理数答案；SIMD 只可用于非认证路径或证明区间仍包住（认证仍可用原路径——见 B5 分层） |
| B3 | 解析/自动微分预解析 Jacobian 与符号复用（`expression.rs` DAG 预编译，`direct_derivative.rs` 已有雏形；跨步复用符号导数仅代数值） | B | 导数表达式重写改变浮点结果；每模型首步生成、逐步对照有限差分/原路径区间；拒绝案例（奇异、非有限）走原路径回退 |
| B4 | rayon 单次仿真内独立任务并行：多候选 trial 并行评估、多 RHS 共享 LU 的回代并行、事件谓词独立扫描 | A/B | trial 之间无共享可变状态时可归 A（每 trial 独立 clone base，天然隔离）；任何跨 trial 归约（择优、求和）改变次序则 B；须报告调度开销，短请求可能负收益——issue P12 的"测调度成本"条件适用 |
| B5 | 认证/非认证路径精度分层：非认证快路径（重排、SIMD、fused ops）+ 认证保持原保守区间路径，最终仍以原证书验收 | B（组织上近 A） | 红线：认证区间包含性不可削弱——分层不能变成"认证也走快路径"；快路径只影响内部候选筛选，最终接受判定与误差区间必须由原路径产出或被证明包含 |
| B6 | 检查器与验收工具链周转加速（Python 校准套件、`profile_requests.py` 配对协议并行化） | A（不计正式分母） | 正式分母边界不含 checker，任何此处收益不得计入端到端提速声明；只用于缩短开发/CI 反馈环，报告需单独列 |
| B7 | 编译期特化/模型特征分派（小规模模型 const-N 内核、`linear.rs` dense/sparse 之外按 nnz/带宽第三档分派；JIT 式"模型特征→专用内核"） | A | 分派判据须确定性且记录于响应身份；每条特化内核独立通过与通用内核的逐位（A 类）对照；不得改变选档边界上的拒绝行为 |

不推荐现在做的：事件调度前瞻/预测性断点排序（C 类，直接改时间推进与误差分配，issue 的 C 类验收最重且无真实失败重试开销证据）；GPU/批量数值核（P16 条件未变，传输成本无证据）；增量 LU/结构化矩阵更新——归入 P02/P03 的启动条件（#57 测量后启动），不单独立项。

## 方法与边界说明

- 本报告全部为静态分析 + 一次只读 bench 实测（上文表），未修改任何文件；工作区在分析前后均为干净状态。
- bench 数字来自单机五轮，未做机器负载隔离，只用于案例间相对排序，不作为任何候选的收益承诺。
- 各切片正式立项时仍须按 issue #138 验收规则执行：固定分母、交替五轮、按风险类别选逐位/包含性判据、Spectre 对照按项目规则复核（可复用冻结参考但须重建执行新 EVAS）。
