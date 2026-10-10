# 能力 ID 与证据索引

本页供开发和审查使用，登记测试 `GUARDS` 所用的稳定 ID、契约和历史证据。
面向使用者的支持结论只在[四后端支持范围](../COMPARISON.md)维护，详细接受与拒绝条件由所链接的契约维护。
收据只证明其固定执行版本；下表仅登记 ID 与证据，供追溯工具读取，不维护第二份支持状态或当前 main 通过率。

| 能力 ID | 契约或数学入口 | 验证与历史证据 |
| --- | --- | --- |
| LANG | [语法/API](../../README.md#实现范围)、[普通条件契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md)、[局部量/事件状态](../../validation/LOCAL_STATE_CONTRACT.md)、[编译准入与标准环境](../reference/frontend-admission.md) | [case 开发测试](../../tests/test_case_statements.py)、[局部量/事件状态实际有限配对](../../../experiments/backends/local-state/README.md)、[局部量/事件状态回归](../../tests/test_local_state.py)、[表达式开发测试](../../tests/test_stateless_expressions.py)、[普通边界证书开发回归](../../tests/test_ordinary_boundary_certificates.py)、[EX-01 新 Spectre 有限对照](../../../experiments/backends/input-clamp/boundary-followup.json)、[普通条件历史检查](../../../experiments/archive/pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz)、[函数开发测试](../../tests/test_user_functions.py)、[函数分支测试](../../tests/test_function_branches.py)、[有限函数 Spectre 配对](../../../experiments/backends/function-branches/README.md)、[循环开发测试](../../tests/test_static_loops.py)、[事件体循环测试](../../tests/test_event_body_loops.py)、[向量测试](../../tests/test_vector_ports.py)、[测试台适配](../../tests/test_scs.py)、[SCS 向量连接](../../validation/SCS_VECTOR_CONTRACT.md)、[lint 边界测试](../../tests/test_lint.py)、[诊断盘点](../reference/diagnostics.md)、[来源登记](diagnostic-sources.md)、[源码出口清单](diagnostic-inventory.json)、[消费者诊断回归](../../tests/test_diagnostic_consumers.py)、[时序边界原因回归](../../tests/test_timed_boundary_diagnostics.py)、[来源行为回归](../../tests/test_diagnostic_sources.py)、[初始化循环契约](../../validation/INITIAL_STATIC_LOOP_CONTRACT.md)、[初始化循环开发测试](../../tests/test_initial_static_loops.py)、[初始化循环实际有限配对](../../../experiments/backends/initial-static-loop/README.md)、[初值/cross 测试](../../tests/test_initial_cross.py)、[输入比较初值](../../tests/test_input_initialization.py)、[八例实际有限配对](../../../experiments/backends/input-initialization/README.md)、[严格准入回归](../../tests/test_compile_admission.py)、[实际准入与观测跟进](../../../experiments/backends/event-alignment/admission-observation-followup.md)；[case 契约](../../validation/CASE_STATEMENTS_CONTRACT.md)；[前端资源预算](../../README.md#frontend-boundaries) |
| LIN | [求解](../math/solving.md) | [原矩阵检查点](../../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json) |
| NONLINEAR | [求解与精度链](../math/solving.md#精度链的已修复反例与边界)、[瞬态契约](../../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | [精度链检查点](../../../experiments/runs/parallel-gap-integration/results/precision-chain-checks.json) |
| SPARSE | [稀疏分支](../math/solving.md#稀疏分支与性能边界) | [当前配对测量](../../../experiments/performance/README.md)、[历史 PR8](https://github.com/BucketSran/vaEVAS/pull/8)；[Issue57](https://github.com/BucketSran/vaEVAS/issues/57) |
| CROSS | [事件数学](../math/events.md)、[根证明](../math/continuous.md#非线性-guard-的根证明) | [精确仿射历史相位回归](../../tests/test_exact_affine_history_phase.py)、[无关滤波、实际依赖与双实例回归](../../tests/test_sample_state_precision.py)、[动态根历史检查点](../../../experiments/runs/parallel-gap-integration/results/dynamic-closure-review-checks.json)、[重定位开发测试](../../tests/test_event_relocalization.py)、[历史重定位回归](../../tests/test_history_relocalization.py)、[精确停止端点及邻接查询回归](../../tests/test_dynamic_cross.py)、[事件/积分拆分对照](../../../experiments/backends/dvs2-spectre-validation/README.md#cross-restart-diagnostic)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有界局部根及规定拒绝](../../../experiments/backends/ordered-event-sources/candidate-phase/README.md)，不覆盖一般跳变与自换向、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[#70](https://github.com/BucketSran/vaEVAS/issues/70)；[va07 wrong-speed 本地接入](../../../benchmark/tasks/va07-triangle-repair/SOURCE.md#local-evas)；[PR #79](https://github.com/BucketSran/vaEVAS/pull/79) |
| TIMER | [事件手册](../math/events.md)、[定时契约](../../validation/TIMED_OPERATOR_CONTRACTS.md) | [固定排序开发回归](../../tests/test_timer_ordering.py)、[近时钟历史组合](../../tests/test_timer_history_order.py)、[有序物理历史续算](../../tests/test_event_history_continuation.py)、[有界因果闭包](../../tests/test_bounded_event_closure.py)、[新容差对照与保留失败](../../../experiments/backends/transient-accuracy/near-clock-history.md)、[SI-01 新参考](../../../experiments/backends/transient-accuracy/core-followup.json)、[动态开发测试](../../tests/test_dynamic_timer.py)、[固定时钟测试](../../tests/test_timer.py)、[同源对照](../../../experiments/backends/dvs2-spectre-validation/README.md#timer-defaults)、[ZOOM 循环事件](../../../experiments/backends/dvs2-spectre-validation/README.md#zoom-static-events)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有序事件源与物理相位对照](../../../experiments/backends/ordered-event-sources/README.md)，两组各 16 请求满足固定判据，原参考 F/I 保留、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[实际 Spectre 对照](../../../experiments/backends/ordered-event-history/README.md) |
| EVENT-ORDER | [生命周期](../math/events.md) | [状态消费者开发回归](../../tests/test_sample_state_precision.py)、[采样/复位新参考](../../../experiments/backends/transient-accuracy/core-followup.json)、[精度链回归](../../tests/test_precision_chain.py)、[历史事件条件对照](../../../experiments/archive/pr14-pr15-validation/results/event-conditions-0.9.0.json)，历史对照不验证本分支新修复、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有序事件源与物理相位对照](../../../experiments/backends/ordered-event-sources/README.md)，两组各 16 请求满足固定判据，原参考 F/I 保留、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[回归](../../tests/test_shared_counter.py)；[Issue16](https://github.com/BucketSran/vaEVAS/issues/16) |
| TRANSITION | [算子](../math/operators.md#transition) | [默认 fall 同源控制](../../../experiments/backends/transition-default-fall/README.md)、[独立回归](../../tests/test_transition_defaults.py)、[历史四参数误差对照](../../../experiments/backends/dvs2-spectre-validation/results/transition-0.6.1.json) |
| ABSDELAY | [算子](../math/operators.md#absdelay) | [两级开发测试](../../tests/test_absdelay_cascade.py)、[专项历史对照](../../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../../tests/test_history_projection.py) |
| SLEW | [算子](../math/operators.md#slew) | [专项历史对照](../../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../../tests/test_history_projection.py) |
| DYNAMICS | [算子](../math/operators.md)、[联合数学](../math/continuous.md)、[限幅候选](../math/operators.md#输入决定的连续限幅候选) | [截止点与矩阵检查点](../../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json)、[DAE/滤波开发测试](../../tests/test_implicit_filters.py)、[精度细化开发回归](../../tests/test_transient_accuracy_control.py)、[组合筛查与保留回归](../../../experiments/backends/transient-accuracy/composition-screen.md)、[实际容差对照](../../../experiments/backends/transient-accuracy/README.md)、[当前精度复核](../../../experiments/backends/transient-accuracy/precision-audit.json)、[参考精度与观测补测](../../../experiments/backends/transient-accuracy/reference-followup.json)、[单极点独立答案](../../tests/test_laplace_np.py)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[限幅开发回归](../../tests/test_input_clamp.py)、[实际有限 Spectre 对照](../../../experiments/backends/input-clamp/README.md)；[API/manifest/SCS strobe](../reference/strobe.md)；[控制回归](../../tests/test_strobe.py)；[冻结模型](../../validation/strobe/README.md) |
| COMPOSE | [联合数学](../math/continuous.md) | [旧根撤销、完整中断边沿与非零历史回归](../../tests/test_al4_lifecycle.py)、[两级调用与回退](../../tests/test_absdelay_cascade.py)、[采样与非线性历史回归](../../tests/test_sample_state_precision.py)、[观察与依赖修复检查点](../../../experiments/runs/parallel-gap-integration/results/lifecycle-observation-review-fixes.json)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md) |
| QUALIFICATION | [验证集](../../validation/README.md)、[追溯矩阵](TRACEABILITY.md) | [提交前审查收据](../../../experiments/runs/capability-completion/review-receipt.json)、[一致初值收据](../../../experiments/runs/capability-completion/joint-dc-receipt.json)、[前一候选收据](../../../experiments/runs/capability-completion/receipt.json)、[合并基线收据](../../../experiments/performance/matrix.json) [实际观察接口](../reference/observation-evidence.md)、[观察证据开发回归](../../tests/test_observation_evidence.py)。；[当前候选表](../../../experiments/backends/paper/candidate-table.md) |
| PERFORMANCE | [求解手册](../math/solving.md#稀疏分支与性能边界)、[只读诊断](../reference/diagnostics.md) | [当前库内与进程测量](../../../experiments/performance/README.md)、[只读输入共享的本地证据](../../../experiments/performance/README.md#direct-input-sharing)、[历史计时](../../../experiments/runs/solver-performance.json)、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[长期候选 Issue138](https://github.com/BucketSran/vaEVAS/issues/138)；[Issue58](https://github.com/BucketSran/vaEVAS/issues/58)；[Issue59](https://github.com/BucketSran/vaEVAS/issues/59) |

旧能力表的逐轮叙事保留在 [整理前的固定版本](https://github.com/BucketSran/vaEVAS/blob/dbeff2f22475ace8644470346a2d097dee6de418/evas/docs/CAPABILITIES.md)。
检查点身份见 [版本记录](../UPDATE.md#检查点身份)。旧 #79、#97 的未完成验收统一由 [#96](https://github.com/BucketSran/vaEVAS/issues/96) 跟踪；关闭入口不表示原差异通过。

2026-10-09 的[当前 main 四后端复验](../../../experiments/backends/support/README.md)补充 LANG、LIN、NONLINEAR、CROSS、TIMER、EVENT-ORDER、TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE、QUALIFICATION 的有限证据；原边界失败和资格限制保留。

2026-10-10 的[采样到滤波组合](../../../experiments/backends/sample-edge-filter/README.md)补充 TIMER、CROSS、TRANSITION、DYNAMICS、COMPOSE。
同分支的[输入根自动细化](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#adaptive-root)
补充 CROSS、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE；属于有限范围的误差恢复，不改变 timer 的数学日程。
契约见[独立工程条件](../../validation/sample_edge_filter/README.md)，实现数学见[前馈滤波历史](../math/operators.md#transition-filter)，
回归见[公开链路测试](../../tests/test_sample_edge_filter.py)。[后续根窗口修复](../../../experiments/backends/sample-edge-filter/BOUNDARY.md)
保留事件时间到边沿、滤波的包围；4 个新增同源码 Spectre 实验验证容差影响，严格同刻阶段仍有 18 条差异。
18 条记录已于 2026-10-10 按用户决定接受为 [SEF-TIMER-18](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18)，
工程对照通过与原严格 FAIL 分开保留；运行身份见收据，实现与本次契约同批交付。任意重叠窗口和其他用例的边界资格未获豁免。
另有 [30 条件回调诊断](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#回调规则的后续实测)，
验证显式正容差下的接受点触发规则；只读回放支持差异归因，不证明 EVAS 独立生成了同一网格，也不需要为本批复制该网格。

2026-10-10 增加[按失败原因选择根细化](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#directed-root-recovery)，
补充 CROSS、EVENT-ORDER、COMPOSE 及 DEV:precision-chain 的开发证据。
[恢复测试](../../tests/test_root_recovery.py)检查原预算重验和继承误差保留；
既有路径复用实际 Spectre 数据，新直接非线性采样另完成正向、负向和小幅值三条件的同源码对照。
[12 配置均满足原预算](../../../experiments/backends/sample-edge-filter/direct-sample-receipt.json)，
每个条件均实际触发目标细化。四档只改变 Spectre，有限观测不授予普遍精度或历史重放能力。

2026-10-10 的[采样保持与一阶滤波精度实测](../../../experiments/backends/support/README.md#precision-pilot)
补充 TIMER、CROSS、DYNAMICS、COMPOSE、QUALIFICATION。冻结 8 个条件和四档设置，
保留定时采样的 strobe 拒绝及普通查询补测；不改变 EVAS 生产行为或旧批次验收结论。

后续[固定 timer 强制点修复](../../../experiments/backends/strobe/README.md#timer-fix)
补充 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE、QUALIFICATION。
原 12 配置在对应修复的运行快照中重新通过；以强制点回执验收，不把普通查询提升为接受帧。
旧拒绝及 Spectre 请求/原生时间偏差仍保留，完整原始数据为 local-only。

2026-10-11 的[单次滤波链预算分配](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#filter-budget)
补充 CROSS、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE 与 DEV:precision-chain 的开发验证证据。
[数学与准入](../math/events.md#filter-root-budget)区分全响应灵敏度提案和最终数值认证；
新增测试台观测事件补齐原生点后，单案例按原规则选中 `tol`；旧失败和新未达标档位保留。
具体后端覆盖以该记录为准，不扩展一般多事件或历史重放支持。
