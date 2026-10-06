# EVAS 能力与缺口总表

核对日期：2026-10-06。本源码为 **EVAS 0.13.0 / IR v17**，未发布 tag。
上一合并检查点的实现与审查见 [PR61](https://github.com/BucketSran/vaEVAS/pull/61)。
改动摘要见[更新记录](UPDATE.md)，合并身份以 Git/PR 为准。
测试文件声明的契约/能力关联见[追溯矩阵](TRACEABILITY.md)（自动生成）；
矩阵同时展示下表的证据入口，收据各自绑定历史执行，不能自动证明当前代码。
此前矩阵执行与审查见[补齐候选收据](../../experiments/runs/capability-completion/README.md)；
前端支持边界见 [#63](https://github.com/BucketSran/vaEVAS/issues/63)、[#64](https://github.com/BucketSran/vaEVAS/issues/64)、[#65](https://github.com/BucketSran/vaEVAS/issues/65)：参数约束、静态 electrical 向量、冗余初始化 OR、具名诊断与受限 `.scs` 输入；开发测试不替代上述矩阵收据。
DIAG 检查点增加[仅编译预检和有限来源诊断](diagnostics.md)，不构成数值或完整诊断覆盖声明。
L2a 检查点支持[常量初始化与 cross 共用体](math/events.md#initial-cross)，不代表完整 SAR 模型支持。
历史检查点见[原实验入口](../../experiments/runs/parallel-gap-integration/README.md#当前证据)。

## 状态约定

- 下表只描述当前源码的限定支持；合法 VA 超出范围时明确拒绝，不因此成为非法语言。
- 实现、有限验证、合并和发布分别记录。表内源码支持不等于已合并或已发布；合并身份见[更新记录中的对应 PR](UPDATE.md)，没有 tag 不宣称发布。
- 能力 ID 稳定，不等于 PR 号、条件数或测试方法数；单项正确不证明任意组合正确。
- 建议后续工作不自动授权新实现或实验。电流未知量、器件负载及完整 SPICE 不属于默认任务。

## 能力矩阵

每行保留支持摘要、关键边界和一个证据入口；完整条件与拒绝边界以
[math/](math/README.md) 及对应 validation 契约为准。证据列保存历史身份，
不声称覆盖该能力的所有组合；性能结果也不自动适用于当前版本。

| ID / 能力 | 限定支持（摘要） | 数学入口 | 剩余边界（摘要） | 证据入口 |
| --- | --- | --- | --- | --- |
| LANG | 标量/参数、有限常量数组、局部顺序赋值与输入 if/else、事件条件与 cross OR；支持纯 real 函数内联（当前开发切片增加有限 if/else 顺序赋值）、静态 genvar 循环（独立历史槽、监测事件及事件体顺序赋值）、一维静态索引变量数组、静态模块层次、对象/函数宏和 include/条件编译，以及 cross/timer 混合 OR；当前分支另有无状态比较、逻辑与三元表达式候选；新增精确 integer 参数/范围、静态 electrical 向量、冗余初始化 OR 和受限 `.scs` 输入（静态向量端口接标量列表）；当前源码支持仅编译 lint 与输入/参数/资源来源诊断；E1 切片补充已审计的展开预算、节点/模块/连接来源与部分内核 kind 分类；有限单负实极点 `laplace_np` 精确转换；当前源码支持一个无分析限定初始化叶与 cross 共用常量赋值体 | [语法/API](../README.md#实现范围)、[普通条件契约](../validation/ANALOG_CONDITIONS_CONTRACT.md) | 受[前端资源预算](../README.md#frontend-boundaries)限制；条件瞬态限分段仿射；普通条件与事件/历史组合、循环内初始化、事件体贡献/历史调用/嵌套事件、运行时循环、动态索引/多维/参数数组、更广函数、宏拼接/字符串化、其他编译指令、generate 与实例数组尚缺；整数隐式转换、独立分析初始化、`$discontinuity` 和更广 `.scs` 语义仍缺；lint 不验证数值请求/动态支持，源码出口清单已维护，实际触发与细分类仍有限，外部诊断消费者仍缺；混合初始化的 timer/重复或分析限定叶、动态初值和条件初始化仍拒绝 | [表达式开发测试](../tests/test_stateless_expressions.py)、[普通条件历史检查](../../experiments/archive/pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz)、[函数开发测试](../tests/test_user_functions.py)、[函数分支测试](../tests/test_function_branches.py)、[有限函数 Spectre 配对](../../experiments/backends/function-branches/README.md)、[循环开发测试](../tests/test_static_loops.py)、[事件体循环测试](../tests/test_event_body_loops.py)、[向量测试](../tests/test_vector_ports.py)、[测试台适配](../tests/test_scs.py)、[SCS 向量连接](../validation/SCS_VECTOR_CONTRACT.md)、[lint 边界测试](../tests/test_lint.py)、[诊断盘点](diagnostics.md)、[来源登记](diagnostic-sources.md)、[源码出口清单](diagnostic-inventory.json)、[消费者诊断回归](../tests/test_diagnostic_consumers.py)、[来源行为回归](../tests/test_diagnostic_sources.py)、[初值/cross 测试](../tests/test_initial_cross.py) |
| LIN | 贡献累加、参考节点、稠密/稀疏求解、分解复用与残差失败后的有限精化 | [求解](math/solving.md) | 病态系统与区间保守性；冗余约束须在误差参数域成立 | [原矩阵检查点](../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json) |
| NONLINEAR | 静态阻尼 Newton 与受限连续化重试；无状态多项式瞬态根盒证明 | [求解与精度链](math/solving.md#精度链的已修复反例与边界)、[瞬态契约](../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | 瞬态认证限方阵；静态 solve 只保证局部收敛；多解全局选择、更广函数尚缺 | [精度链检查点](../../experiments/runs/parallel-gap-integration/results/precision-chain-checks.json) |
| SPARSE | n≥32 且 nnz≤0.1mn 时稀疏 LU；减少消元重复查找 | [稀疏分支](math/solving.md#稀疏分支与性能边界) | 认证仍稠密；填充/存储后续 [Issue57](https://github.com/BucketSran/vaEVAS/issues/57) | [当前配对测量](../../experiments/performance/README.md)、[历史 PR8](https://github.com/BucketSran/vaEVAS/pull/8) |
| CROSS | PWL/仿射/状态独立多项式/连续积分/滤波/受限 sin guard，逐叶认证；支持事件修改仿射/多项式阈值及内部节点后的未来根重定位 | [事件数学](math/events.md)、[根证明](math/continuous.md#非线性-guard-的根证明) | 候选已补受限连续积分轨迹的事件重定位；不确定根窗口内的双向自换向明确拒绝（[#70](https://github.com/BucketSran/vaEVAS/issues/70)）；同刻跳变闭包、隐式非线性 guard、切线/平台认证尚缺；[va07 wrong-speed 本地接入](../../benchmark/tasks/va07-triangle-repair/SOURCE.md#local-evas)在原 stop=3 s 出现端点数值拒绝，真实负控验收未完成 | [动态根历史检查点](../../experiments/runs/parallel-gap-integration/results/dynamic-closure-review-checks.json)、[重定位开发测试](../tests/test_event_relocalization.py)、[历史重定位回归](../tests/test_history_relocalization.py)、[事件/积分拆分对照](../../experiments/backends/dvs2-spectre-validation/README.md#cross-restart-diagnostic) |
| TIMER | 固定单次/周期日程；IR17 支持保持状态控制的 start/period/enable，按新日程截止点推进历史；候选支持缺省 period/time_tol/enable，默认容差 1 ps，选择不早于名义时刻的代表值 | [事件手册](math/events.md)、[定时契约](../validation/TIMED_OPERATOR_CONTRACTS.md) | 连续电压参数、动态/显式零容差仍缺；候选历史日程限可认证连续轨迹，不确定边界拒绝；普通模拟条件下的事件激活仍缺 | [动态开发测试](../tests/test_dynamic_timer.py)、[固定时钟测试](../tests/test_timer.py)、[同源对照](../../experiments/backends/dvs2-spectre-validation/README.md#timer-defaults)、[ZOOM 循环事件](../../experiments/backends/dvs2-spectre-validation/README.md#zoom-static-events) |
| EVENT-ORDER | 同刻联立、程序顺序赋值、单写者、整批提交/回退 | [生命周期](math/events.md) | 同批双写及跨块 state 读取拒绝；real 相对预算在零附近保守；Spectre 差异见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16) | [事件条件历史对照](../../experiments/archive/pr14-pr15-validation/results/event-conditions-0.9.0.json) |
| TRANSITION | 固定延迟、显式正边沿、状态仿射输入，历史误差参与验收 | [算子](math/operators.md#transition) | 动态参数、零/省略边沿及更广组合尚缺 | [历史误差修复对照](../../experiments/backends/dvs2-spectre-validation/results/transition-0.6.1.json) |
| ABSDELAY | 固定非负延迟、直接连续 PWL 仿射输入；支持内部仿射电压投影；当前源码支持两级固定延迟及同实例单位内部别名 | [算子](math/operators.md#absdelay) | 可变延迟、状态/跳变、第三层/一般历史组合和历史反馈尚缺；大增益时整段包围可能保守拒绝 | [两级开发测试](../tests/test_absdelay_cascade.py)、[专项历史对照](../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../tests/test_history_projection.py) |
| SLEW | 固定正/负限速、直接连续 PWL 仿射输入；支持内部仿射电压投影 | [算子](math/operators.md#slew) | 动态参数、状态/嵌套和历史反馈尚缺 | [专项历史对照](../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../tests/test_history_projection.py) |
| DYNAMICS | idt/idtmod/sin、积分反馈、联合 reset、1–8 阶滤波、可精确转换的单负实极点 laplace_np、受限 ddt、index-one 多项式 DAE；支持 DAE 与 proper 滤波联合状态、内部/算子输入及可认证的非线性滤波 DC；当前分支候选增加无事件 input-only 连续 clamp 的贡献输出及 clamp→idtmod→sin 闭式分段 | [算子](math/operators.md)、[联合数学](math/continuous.md)、[限幅候选](math/operators.md#输入决定的连续限幅候选) | DAE 与事件/复位/ddt、非线性直接通路、通用函数混合等尚缺；DC 证书仅确定局部根；laplace_np 不支持多项分子/复杂或多个极点/epsilon/非精确倒数；clamp 切片仅有限常量上下限、直接驱动仿射输入，无显式事件/状态/内部反馈/其他历史算子；实际有限对照保留四个未配对中心、严格 stop 和观察资格缺口 | [截止点与矩阵检查点](../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json)、[DAE/滤波开发测试](../tests/test_implicit_filters.py)、[单极点独立答案](../tests/test_laplace_np.py)、[限幅开发回归](../tests/test_input_clamp.py)、[实际有限 Spectre 对照](../../experiments/backends/input-clamp/README.md) |
| COMPOSE | 实例隔离（含静态层次）、积分/滤波闭包、DC 与瞬态导数一致求值、事件重启复用物理历史；当前源码支持受限两级固定 absdelay | [联合数学](math/continuous.md) | 结构依赖不可绕过；非线性混合限积分+proper 滤波 | [两级调用与回退](../tests/test_absdelay_cascade.py)、[观察与依赖修复检查点](../../experiments/runs/parallel-gap-integration/results/lifecycle-observation-review-fixes.json) |
| QUALIFICATION | 原矩阵两档各 31/31（合并基线 0.12.3 / IR16）；0.13.0 / IR17 检查点重跑仍各 31/31；七个预先冻结确认案例首次及复跑各 14/14 | [验证集](../validation/README.md)、[追溯矩阵](TRACEABILITY.md) | 正式 DVS 资格 I；原矩阵已用于开发；七案例确认限该冻结批次，不覆盖后加 DAE/滤波或一般组合；独立观察误差与一般连续时间资格仍缺 | [提交前审查收据](../../experiments/runs/capability-completion/review-receipt.json)、[一致初值收据](../../experiments/runs/capability-completion/joint-dc-receipt.json)、[前一候选收据](../../experiments/runs/capability-completion/receipt.json)、[合并基线收据](../../experiments/performance/matrix.json) |
| PERFORMANCE | 稀疏分流、查询复用、标量根证明、独立静态并行；逐位相同的仿射矩阵跨候选复用 LU | [求解手册](math/solving.md#稀疏分支与性能边界)、[只读诊断](diagnostics.md) | 完整请求成本已测；历史/guard 优化见 [Issue58](https://github.com/BucketSran/vaEVAS/issues/58)，长输出协议见 [Issue59](https://github.com/BucketSran/vaEVAS/issues/59)；无 Spectre 同配置加速结论 | [当前库内与进程测量](../../experiments/performance/README.md)、[历史计时](../../experiments/runs/solver-performance.json) |

## 检查点身份

| 检查点 | 固定执行身份 |
| --- | --- |
| PR61 / 0.13.0 / IR17 | 确认冻结 `5171558c`、首次运行后端 `63afd040`；前一矩阵/确认及整合回归 `152a920d`；一致初值与观察修复 `114d676e`；包含身份审查修复及最终矩阵/确认复跑和回归 `d68d3db4`；见[候选收据](../../experiments/runs/capability-completion/README.md) |
| 诊断与性能 / 0.12.3 / IR16 | 配对基线 `e91cf6ff`、候选 `eb03f94d`；原矩阵运行时 `a388a651`；见[当前收据](../../experiments/performance/README.md) |
| PR50 / 0.12.3 / IR16：前轮矩阵重跑 | 被测 main `a7a42e17`；运行时、内核及新执行见前轮收据 |
| PR33 / IR16：事件截止点 | 运行时 `8618339`，合并点 `b4921ca` |
| PR32 / IR16：混合动态与生命周期 | 运行时 `1b99c33`，合并点 `431f335` |
| PR31 / IR16：非线性积分与联合事件 | 运行时 `d06e7f3`，合并点 `09b4222` |
| PR30 / IR16：连续动态 | 运行时 `ba5ab46`/`071a813`，合并点 `bedf20f` |
| PR29 / IR15：矩阵补齐与精度链 | 运行时 `d451605` |
| PR26 / IR11 及旧 EVAS 0.8.7 | 历史失败不改写为新版本成绩，见 [四后端矩阵](../../experiments/backends/dvs2-four-backend-validation/results/MATRIX.md) |

各检查点的收据由上表证据列及[追溯矩阵](TRACEABILITY.md)导航，完整历史入口见
[实验目录](../../experiments/README.md)；早期失败（根盒等号、复位误拒绝、
Spectre 不一致等）保留在对应历史段落，修复不删除。

## 后续工作

原 31 条件在本范围内已补齐；更广能力缺口（联合动态求解组合、事件扩展、
语言算子、精度资格、性能测量）按[共同生命周期契约](../validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract)
分批推进。每项先固定数学契约和接受/拒绝边界，再做独立答案、不变性和失败后
完整性检查。实际范围、依赖、负责人和预算写在对应 Issue/PR。
