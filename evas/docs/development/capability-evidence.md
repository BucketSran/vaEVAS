# 能力 ID 与证据索引

本页供开发和审查使用，登记测试 `GUARDS` 所用的稳定 ID、契约和历史证据。
面向使用者的支持结论只在[四后端支持范围](../COMPARISON.md)维护，详细接受与拒绝条件由所链接的契约维护。
收据只证明其固定执行版本；下表仅登记 ID 与证据，供追溯工具读取，不维护第二份支持状态或当前 main 通过率。

[原 CDS 三例验收](../../../experiments/backends/support/event-runtime-control/README.md#original-cds)
补充 LIN、TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE、PERFORMANCE 的开发证据。
三条原请求通过原 checker 与实际 Spectre 有限配对；重复工作优化和时间来源修复的执行身份、原失败与限制由收据固定。
有限配对不增加 Q 等级，单次耗时不证明稳定加速。

[同步读出与原时限验证](../../../experiments/backends/support/r01-sync-readout/README.md)
补充 TRANSITION、DYNAMICS、CROSS、COMPOSE、TIMER、EVENT-CONDITIONS 和 EVENT-ORDER。
原物理请求完整执行，保持电压满足原要求；严格阈值引起的整题失败保留。
三张独立乘积卡及普通、中断边沿后的两个滤波消费者均有有限数值和行为证据。
动态系数滤波的原IR准入、历史延续和最终认证失败回退见 `test_live_transition_filter.py`
与 `transient_timer_boundary_tests.rs`；外部取证资格仍不完整，不新增Q资格。

[ANSI 端口声明](../../../experiments/backends/support/ansi-ports/README.md)补充 LANG 的有限证据；
五个正控制共25原生配对点及两个实际拒绝控制保留。原26请求中三项完成并通过冻结旧 checker，23项仍有后续阻塞，不新增Q成绩。

[SCS 时间选择](../../../experiments/backends/support/scs-save-time/README.md)补充 LANG 与 DEV:scs-input 的有限证据；
时间轴、电气同名节点和默认节点保存分别验收，不扩展 Spectre 的完整保存语法或固定 Q 成绩。

[源折点保存修复](../../../experiments/backends/support/scs-source-observation/README.md)补充 DEV:scs-input 的有限开发证据；修复保存插值漏脉冲，不改变原Q成绩。

[Pulse 源误差和保存策略](../../../experiments/backends/support/scs-source-uncertainty/README.md)补充 DEV:scs-input 与 TIMER 的有限开发证据；该历史执行仅支持幅度界。新的[物理源曲线证据](../../../experiments/backends/support/source-shape/README.md)扩展 CROSS、EVENT-ORDER、EVENT-CONDITIONS、TIMED-OPERATOR 与 COMPOSE 的有限组合；347 的已解释兼容差异和未合并状态保留；不改变原Q成绩。[P0逐项收据](../../../experiments/backends/support/source-shape/p0.json)补充同步两例、400五例及#119旧精度反例的当前核销，[固定112家族收据](../../../experiments/backends/support/source-shape/replay112.json)保留完整执行、拒绝与清理分母；[091/320收据](../../../experiments/backends/support/source-shape/diagnosis-091-320.json)补独立完整递推与原件实际参考。分类与后续验收由[统一清单](../COMPARISON.md#replay112)维护，拒绝项继续未支持。
[GAP06有限除法采样](../../../experiments/backends/support/source-shape/gap06.json)补充EVENT-CONDITIONS、TIMED-OPERATOR与COMPOSE：八例独立递推及全部保存量通过，原checker3/8，五例严格根处复位差异及参考观察缺证保留。实际原deck参考8/8通过，有限稳定观察与完整原生波形分别记录；当前112分母及剩余拒绝见[唯一清单](../COMPARISON.md#gap06-sampling)。

[Pulse delay 缺省值](../../../experiments/backends/support/pulse-delay/README.md)补充 DEV:scs-input 的有限开发证据；仅省略 delay 取 0，其他源参数与误差约束保持，原 22 请求仍有后续拒绝。

[隐式 DAE 的动态模型步长](../../../experiments/backends/implicit-step-bounds/README.md)补充 DYNAMICS 的有限开发证据；两条实际参考各33点通过原100nV门槛，不宣称原R01请求新增恢复。

[固定 timer 的隐式 DAE 续算](../../../experiments/backends/implicit-event-restart/README.md)补充 DYNAMICS、TIMER、EVENT-ORDER 和 COMPOSE 的有限开发证据；物理 seed、步长与同控制器回退由独立测试核对，实际参考九点通过原 100 nV 门槛。一般事件窗/约束跳参仍拒绝，不新增 Q 资格。

[初始化节点依赖](../../../experiments/backends/support/initial-node-dependencies/README.md)补充 LANG、LIN 和 COMPOSE 的有限开发证据；三个同源实际 Spectre 对照通过，不宣称原 MUX 任务完成。

IR21 共同基础已随 [#174](https://github.com/BucketSran/vaEVAS/pull/174) 合入 main，补充 LANG、ANALOG、CROSS、TIMER、EVENT-ORDER、EVENT-CONDITIONS、DYNAMICS、COMPOSE 和 DEV:scs-input。
契约见[局部变量与条件支路](../../validation/ANALOG_CONDITIONS_CONTRACT.md)、
[事件条件与输出记录](../math/events.md)、[连续选路与有理流](../math/continuous.md#selected-flow)。
开发回归包括[顺序初始化和整数类型](../../tests/test_r01_runtime_frontend.py)、
[状态谓词](../../tests/test_r01_event_conditions.py)、[事件选路](../../tests/test_r01_event_select.py)、
[连续选路](../../tests/test_r01_runtime_select.py)、[输出记录](../../tests/test_display.py)、
[事件时间](../../tests/test_event_time.py)、[整数循环](../../tests/test_integer_loops.py)、[模型步长](../../tests/test_bound_step.py)和
[SCS 驱动保留](../../tests/test_scs_driven_nodes.py)。既有[语言](../../tests/test_r01_language.py)与
[纯表达式](../../tests/test_stateless_expressions.py)回归继续保留。
基础有限对照见[最终控制](../../../experiments/backends/support/r01-root-windows/final-controls/README.md)。
原始 70 条件没有最终版本的全量验收；本轮增补与原完整任务结果见下段，历史成绩保留。

[事件数组与独立测量](../../../experiments/backends/support/r01-timing-observers/README.md)
补充 LANG、CROSS、TIMER、EVENT-CONDITIONS、EVENT-ORDER、COMPOSE 的有限开发证据。
契约见[参数与下标准入](../reference/frontend-admission.md)及[独立测量](../math/events.md#passive-observer)，
回归见[原树义务](../../tests/test_event_parameter_specialization.py)、
[事件数组](../../tests/test_r01_event_arrays.py)、[测量事务](../../tests/test_passive_events.py)。
这些控制不增加固定 Q 成绩；原完整 timing 请求的后续连续耦合拒绝单列。

[原70请求的同版复验摘要](../../../experiments/backends/support/r01-main70-summary.json)保留固定 `main@efd17ed6`、0.17.0 / IR21 的工程完成、拒绝与原判据身份，完整资产仍是local-only，不能转为当前 main 的总通过率或论文Q成绩。后续具名交付与未完成项见[工程请求与扩展范围](../COMPARISON.md#engineering-status)。[覆盖缺口](../../validation/paper/COVERAGE.md#engineering-gap-audit)将LANG、DYNAMICS、TRANSITION、COMPOSE及事件需求对应到独立卡规划，不单独授予支持结论。

[隔离事件统计](../../../experiments/backends/support/README.md#event-statistics)补充 LANG、EVENT-CONDITIONS、EVENT-ORDER、TIMER：IR22 的状态分母及 sqrt/abs/min/max 纯事件数学只扩展完整 IR 证明隔离的观察实例。三条原 gain 请求及四个手算控制已实际验收，不新增论文 Q 成绩。合同见[事件数学](../math/events.md#event-math)，独立输入见[统计控制](../../validation/event_statistics/README.md)，回归见[test_event_statistics.py](../../tests/test_event_statistics.py)。

[连续状态与原 timing 请求](../../../experiments/backends/support/r01-causal-timing/README.md)
补充 DYNAMICS、TIMER、TRANSITION、CROSS、EVENT-CONDITIONS、EVENT-ORDER 与 COMPOSE。
契约见[连续因果投影](../math/continuous.md)和[事件条件与观察](../math/events.md)。
原 timing-0 完整执行并通过原 checker，实际有限配对、所有历史失败及未完成原生点分别保留；不增加固定 Q 成绩。
开发回归覆盖[因果状态](../../tests/test_n09_causal_state_readout.py)、[辅助节点](../../tests/test_auxiliary_continuous_roots.py)、[条件步长](../../tests/test_conditional_history_mesh.py)、[时间来源](../../tests/test_held_time_provenance.py)、[精确期限](../../tests/test_exact_transition_deadlines.py)、[等价事件分支](../../tests/test_event_branch_agreement.py)、[被动查询相位](../../tests/test_passive_history_phase.py)与[初始期限](../../tests/test_initial_observer_horizon.py)。

[空循环声明与当前 timer 安全修复](../../../experiments/backends/support/retained-safety/README.md)
补充 LANG、TIMER、EVENT-ORDER、COMPOSE 的 main 适配证据。
非法节点改为编译失败；新生成当前 timer 改为明确拒绝，尚不支持同刻闭包。
五个实际 Spectre 探针和开发回归不改变原表 Q 档及历史成绩。

[旧整链 Q 补验与中断边沿积分](../../../experiments/backends/support/README.md#legacy-chain-q)
补充 TIMER、TRANSITION、DYNAMICS、COMPOSE、QUALIFICATION。
旧整链使用 main `7344e4db` 对应内核代码；[新增前馈积分](../math/operators.md#transition-integral)
纳入 0.15.0 / IR19，支持范围与发布前实际构建、执行身份分别保留。
校准见[完整回调历史](../../tests/test_legacy_chain_precision.py)、
[有向数学包围](../../tests/test_legacy_chain_bounds.py)和[独立边沿面积](../../tests/test_transition_integral_precision.py)，
生产回归见[中断与历史保持](../../tests/test_transition_integral.py)。不覆盖 #131。

[本轮导数与严格组合修复](../../../experiments/backends/support/README.md#capability-gaps)
补充 LANG、DYNAMICS、COMPOSE、QUALIFICATION；两张导数卡与八张组合卡保留实际候选源码、内核、原判据和Spectre对照。
回归见[多项式导数](../../tests/test_polynomial_derivatives.py)、[滤波精度](../../tests/test_filter_precision.py)。
实现已随 #167 合入 main `e028f96d`；原收据的候选身份和成绩保留，不转授任意组合支持。

[新版根窗口实测](../../../experiments/backends/support/README.md#root-window-v3)
补充 CROSS、EVENT-ORDER、DYNAMICS、COMPOSE、QUALIFICATION。固定 SH-X-RAMP 与 EC04-v1 的三档运行，
保留完整回调区间，严格时间语义与有限分辨率验收分别报告；这是判据与证据更新，没有修改 EVAS 求解器。
[新版合同与校准](../../validation/paper/precision-root-v3.json)不覆盖 #131 或其他窗口。

[采样积分与局部 strobe 修复](../../../experiments/backends/support/README.md#sampled-integral-fix)
补充 DYNAMICS、CROSS、TIMER、EVENT-ORDER、COMPOSE、QUALIFICATION。
[独立面积与物理阶段回归](../../tests/test_sampled_integral_strobe.py)、
[非自治强制点负控](../../tests/test_bounded_event_closure.py)及实际五卡三档对照保留原预算。
EC04 的原窗口资格与 #131 冻结范围保留；回调证明只补离散事件，不替代连续输出验收。

[累计测试清单](../../validation/paper/COVERAGE.md)登记历史条件与新 44 组的逐项关系，
涵盖 LANG、LIN、NONLINEAR、TIMER、CROSS、EVENT-ORDER、TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE、QUALIFICATION。
五层目录整理没有改变实现、判据或成绩。主表按五层固定用例呈现；打勾只表示本行全部必测用例通过，扩展计划和缺证清单分别保留。
L1–L5 是表格导航 ID，不替换下表开发 ID；旧版本、原预算和失败继续保留。

[Q3 支持修复与横线补证](../../../experiments/backends/support/README.md#q3-closure)
补充 LANG、NONLINEAR、DYNAMICS、COMPOSE、QUALIFICATION 的实现与有限证据。
IR19 增加纯数学函数，恒定 PWL 保留原输入位；契约见[纯数学函数](../math/operators.md#elementary-functions)，
回归见[函数测试](../../tests/test_unary_functions.py)、[恒定输入测试](../../tests/test_constant_input_identity.py)，
独立校准见[校准工具](../../validation/calibrate_elementary.py)。
静态输入与回调证书只解除已证明的义务；新旧成绩、具体工具版本和未完组合均在收据中分开记录。
函数修复属于本轮源码交付；#162 的旧运行不计作当前 main 能力，#131 不动。

[原11格后续取证](../../../experiments/backends/support/README.md#evidence-followup)
补充 CROSS、EVENT-ORDER、DYNAMICS、QUALIFICATION 的有限来源证据。
回调记录、实际输入消费者与最终接受状态按固定卡重新核准；新数值分析与旧I并列保存。
这次不修改EVAS生产源码，不将环回侧别或同刻回调直接认定为EVAS缺陷，也不豁免原验收。

[独立基础卡与历史补证](../../../experiments/backends/support/README.md#primitives-main)
补充 LANG、NONLINEAR、DYNAMICS、QUALIFICATION：十卡、三档、四后端共120个新位置，
另重读168份历史配置。新卡固定 main 检查点 `a64c2ad0`，仅验收有限导出值；
不覆盖后续 main、不补造旧事件回调资格，也不回写原成绩。

Q 档精度集的[失败归因复核](../../../experiments/backends/support/README.md#failure-attribution)
补充 CROSS、TIMER、DYNAMICS、QUALIFICATION 的原因证据。它区分事件编译缺陷、已复现的行为错误、
EVAS 回调缺证与严格配置认证拒绝，不改原验收成绩或扩大能力范围。

同日的[严格滤波修复与阈值边界补测](../../../experiments/backends/support/README.md#evas-precision-recovery)
补充 DYNAMICS、CROSS、QUALIFICATION。修复版四个滤波条件通过原 Q3，56 个根附近查询状态正确；
阈值采样的完整回调资格仍未取得。新代码不能直接复用旧源码身份的配置绑定。

[44 组扩展验证](../COMPARISON-METHODOLOGY.md#precision-breadth)补充 LANG、LIN、NONLINEAR、
TIMER、CROSS、EVENT-ORDER、TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE、QUALIFICATION。
它分别记录数值、行为和取证结果；支持结论仍只在支持总表维护，开发用例不计为独立留出集。

| 能力 ID | 契约或数学入口 | 验证与历史证据 |
| --- | --- | --- |

| LANG | [语法/API](../../README.md#实现范围)、[普通条件契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md)、[局部量旧切片](../../validation/LOCAL_STATE_CONTRACT.md)、[当前顺序初始化](../math/events.md#同块顺序赋值与同刻联立求解)、[编译准入与标准环境](../reference/frontend-admission.md) | [case 开发测试](../../tests/test_case_statements.py)、[局部量/事件状态实际有限配对](../../../experiments/backends/local-state/README.md)、[局部量/事件状态回归](../../tests/test_local_state.py)、[表达式开发测试](../../tests/test_stateless_expressions.py)、[普通边界证书开发回归](../../tests/test_ordinary_boundary_certificates.py)、[EX-01 新 Spectre 有限对照](../../../experiments/backends/input-clamp/boundary-followup.json)、[普通条件历史检查](../../../experiments/archive/pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz)、[函数开发测试](../../tests/test_user_functions.py)、[函数分支测试](../../tests/test_function_branches.py)、[有限函数 Spectre 配对](../../../experiments/backends/function-branches/README.md)、[循环开发测试](../../tests/test_static_loops.py)、[事件体循环测试](../../tests/test_event_body_loops.py)、[向量测试](../../tests/test_vector_ports.py)、[测试台适配](../../tests/test_scs.py)、[SCS 向量连接](../../validation/SCS_VECTOR_CONTRACT.md)、[lint 边界测试](../../tests/test_lint.py)、[诊断盘点](../reference/diagnostics.md)、[来源登记](diagnostic-sources.md)、[源码出口清单](diagnostic-inventory.json)、[消费者诊断回归](../../tests/test_diagnostic_consumers.py)、[时序边界原因回归](../../tests/test_timed_boundary_diagnostics.py)、[来源行为回归](../../tests/test_diagnostic_sources.py)、[初始化循环旧切片](../../validation/INITIAL_STATIC_LOOP_CONTRACT.md)、[初始化循环开发测试](../../tests/test_initial_static_loops.py)、[初始化循环实际有限配对](../../../experiments/backends/initial-static-loop/README.md)、[初值/cross 测试](../../tests/test_initial_cross.py)、[输入比较初值](../../tests/test_input_initialization.py)、[八例实际有限配对](../../../experiments/backends/input-initialization/README.md)、[标准数学常量回归](../../tests/test_standard_constants.py)、[未引用私有节点回归](../../tests/test_unused_internal_nodes.py)、[标准头/私有节点实际有限对照与 exact 缺证](../../../experiments/backends/support/frontend-retained/README.md)、[严格准入回归](../../tests/test_compile_admission.py)、[实际准入与观测跟进](../../../experiments/backends/event-alignment/admission-observation-followup.md)；[case 契约](../../validation/CASE_STATEMENTS_CONTRACT.md)；[前端资源预算](../../README.md#frontend-boundaries) ；[耦合行为源回归](../../tests/test_scs_bsource.py) |
| LIN | [求解](../math/solving.md) | [原矩阵检查点](../../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json) |
| NONLINEAR | [求解与精度链](../math/solving.md#精度链的已修复反例与边界)、[瞬态契约](../../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | [精度链检查点](../../../experiments/runs/parallel-gap-integration/results/precision-chain-checks.json) |
| SPARSE | [稀疏分支](../math/solving.md#稀疏分支与性能边界) | [当前配对测量](../../../experiments/performance/README.md)、[历史 PR8](https://github.com/BucketSran/vaEVAS/pull/8)；[Issue57](https://github.com/BucketSran/vaEVAS/issues/57) |
| CROSS | [事件数学](../math/events.md)、[根证明](../math/continuous.md#非线性-guard-的根证明) | [精确仿射历史相位回归](../../tests/test_exact_affine_history_phase.py)、[无关滤波、实际依赖与双实例回归](../../tests/test_sample_state_precision.py)、[动态根历史检查点](../../../experiments/runs/parallel-gap-integration/results/dynamic-closure-review-checks.json)、[重定位开发测试](../../tests/test_event_relocalization.py)、[历史重定位回归](../../tests/test_history_relocalization.py)、[精确停止端点及邻接查询回归](../../tests/test_dynamic_cross.py)、[事件/积分拆分对照](../../../experiments/backends/dvs2-spectre-validation/README.md#cross-restart-diagnostic)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有界局部根及规定拒绝](../../../experiments/backends/ordered-event-sources/candidate-phase/README.md)，不覆盖一般跳变与自换向、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[#70](https://github.com/BucketSran/vaEVAS/issues/70)；[va07 wrong-speed 本地接入](../../../benchmark/material/historyref/tasks/va07-triangle-repair/SOURCE.md#local-evas)；[PR #79](https://github.com/BucketSran/vaEVAS/pull/79) |
| TIMER | [事件手册](../math/events.md)、[定时契约](../../validation/TIMED_OPERATOR_CONTRACTS.md) | [零时刻最终种子实际有限配对](../../../experiments/backends/support/README.md#initial-transition-seed)、[初始化开发回归](../../tests/test_transition_initialization.py)、[固定排序开发回归](../../tests/test_timer_ordering.py)、[近时钟历史组合](../../tests/test_timer_history_order.py)、[有序物理历史续算](../../tests/test_event_history_continuation.py)、[有界因果闭包](../../tests/test_bounded_event_closure.py)、[新容差对照与保留失败](../../../experiments/backends/transient-accuracy/near-clock-history.md)、[SI-01 新参考](../../../experiments/backends/transient-accuracy/core-followup.json)、[动态开发测试](../../tests/test_dynamic_timer.py)、[固定时钟测试](../../tests/test_timer.py)、[同源对照](../../../experiments/backends/dvs2-spectre-validation/README.md#timer-defaults)、[ZOOM 循环事件](../../../experiments/backends/dvs2-spectre-validation/README.md#zoom-static-events)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有序事件源与物理相位对照](../../../experiments/backends/ordered-event-sources/README.md)，两组各 16 请求满足固定判据，原参考 F/I 保留、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[实际 Spectre 对照](../../../experiments/backends/ordered-event-history/README.md)、[停止边界恢复与实际配对](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#timer-stop) |
| EVENT-ORDER | [生命周期](../math/events.md) | [状态消费者开发回归](../../tests/test_sample_state_precision.py)、[采样/复位新参考](../../../experiments/backends/transient-accuracy/core-followup.json)、[精度链回归](../../tests/test_precision_chain.py)、[历史事件条件对照](../../../experiments/archive/pr14-pr15-validation/results/event-conditions-0.9.0.json)，历史对照不验证本分支新修复、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有序事件源与物理相位对照](../../../experiments/backends/ordered-event-sources/README.md)，两组各 16 请求满足固定判据，原参考 F/I 保留、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[回归](../../tests/test_shared_counter.py)；[Issue16](https://github.com/BucketSran/vaEVAS/issues/16) |
| TRANSITION | [算子](../math/operators.md#transition) | [零时刻最终种子实际有限配对](../../../experiments/backends/support/README.md#initial-transition-seed)、[初始化开发回归](../../tests/test_transition_initialization.py)、[默认 fall 同源控制](../../../experiments/backends/transition-default-fall/README.md)、[独立回归](../../tests/test_transition_defaults.py)、[历史四参数误差对照](../../../experiments/backends/dvs2-spectre-validation/results/transition-0.6.1.json) |
| ABSDELAY | [算子](../math/operators.md#absdelay) | [两级开发测试](../../tests/test_absdelay_cascade.py)、[专项历史对照](../../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../../tests/test_history_projection.py) |
| SLEW | [算子](../math/operators.md#slew) | [专项历史对照](../../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../../tests/test_history_projection.py)、[两级固定前馈](../../../experiments/backends/slew-cascade/README.md) |
| DYNAMICS | [算子](../math/operators.md)、[联合数学](../math/continuous.md)、[限幅候选](../math/operators.md#输入决定的连续限幅候选) | [截止点与矩阵检查点](../../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json)、[DAE/滤波开发测试](../../tests/test_implicit_filters.py)、[精度细化开发回归](../../tests/test_transient_accuracy_control.py)、[组合筛查与保留回归](../../../experiments/backends/transient-accuracy/composition-screen.md)、[实际容差对照](../../../experiments/backends/transient-accuracy/README.md)、[当前精度复核](../../../experiments/backends/transient-accuracy/precision-audit.json)、[参考精度与观测补测](../../../experiments/backends/transient-accuracy/reference-followup.json)、[单极点独立答案](../../tests/test_laplace_np.py)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[限幅开发回归](../../tests/test_input_clamp.py)、[实际有限 Spectre 对照](../../../experiments/backends/input-clamp/README.md)；[API/manifest/SCS strobe](../reference/strobe.md)；[控制回归](../../tests/test_strobe.py)；[冻结模型](../../validation/strobe/README.md) |
| COMPOSE | [联合数学](../math/continuous.md) | [零时刻最终种子实际有限配对](../../../experiments/backends/support/README.md#initial-transition-seed)、[初始化开发回归](../../tests/test_transition_initialization.py)、[旧根撤销、完整中断边沿与非零历史回归](../../tests/test_al4_lifecycle.py)、[两级调用与回退](../../tests/test_absdelay_cascade.py)、[采样与非线性历史回归](../../tests/test_sample_state_precision.py)、[观察与依赖修复检查点](../../../experiments/runs/parallel-gap-integration/results/lifecycle-observation-review-fixes.json)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md) |
| QUALIFICATION | [验证集](../../validation/README.md)、[追溯矩阵](TRACEABILITY.md) | [提交前审查收据](../../../experiments/runs/capability-completion/review-receipt.json)、[一致初值收据](../../../experiments/runs/capability-completion/joint-dc-receipt.json)、[前一候选收据](../../../experiments/runs/capability-completion/receipt.json)、[合并基线收据](../../../experiments/performance/matrix.json) [实际观察接口](../reference/observation-evidence.md)、[观察证据开发回归](../../tests/test_observation_evidence.py)。；[当前候选表](../../../experiments/backends/paper/candidate-table.md) |
| PERFORMANCE | [求解手册](../math/solving.md#稀疏分支与性能边界)、[只读诊断](../reference/diagnostics.md) | [当前库内与进程测量](../../../experiments/performance/README.md)、[只读输入共享实测](../../../experiments/performance/README.md#direct-input-sharing)、[历史计时](../../../experiments/runs/solver-performance.json)、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[长期候选 Issue138](https://github.com/BucketSran/vaEVAS/issues/138)；[Issue58](https://github.com/BucketSran/vaEVAS/issues/58)；[Issue59](https://github.com/BucketSran/vaEVAS/issues/59) |

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

[定向生命周期回归](../../validation/sample_edge_filter/README.md#定向生命周期回归)
补充 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE 的开发测试：非零计数经过复位闭包、候选丢弃及精度拒绝后只提交一次；
旧边沿持续到延迟激活；保持量复位后滤波状态续存。局部预期由手算给出，不扩大支持范围或 Spectre 边界资格。

[REA 四行边界核对](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#rea-four-boundaries)
保存 EVAS 0.15.0 / IR19、`ff5d0fd9` 本地树的历史诊断，不作为当前 IR23 对齐证据。
该记录涉及 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE：原始内存确认 Spectre 在正容差内提前回调，
EVAS 的全部 6,366 行计数符合名义时钟，四行严格差异仍保留；未发现需要修改调度或历史的生产缺口。
该结论限于所测原链路，不授予依赖跳变瞬间先后顺序的新消费者同源码资格。

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

固定外部多项式输入的滤波直接通路补充 DYNAMICS、COMPOSE：
[数学与准入](../math/continuous.md#固定外部多项式输入的直接通路)、
[开发回归](../../tests/test_filter_direct.py)、[实际 Spectre 有限对照](../../../experiments/backends/filter-direct/README.md)。
这仅交付 #66/C4 的前馈切片，内部非线性反馈与事件仍未纳入。

2026-10-11 的[近邻 timer 强制点](../../../experiments/backends/strobe/README.md#near-timer)
补充 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE、QUALIFICATION。
固定／精确保持时钟及连续组合共 12 个 EVAS 配置通过；Spectre 10/12，通过范围按固定顺序选档。
连续组合的两个原预算失败和更广局部历史闭包限制保留，不关闭 #96/#119。

2026-10-11 的[当前 main 复验](../../../experiments/backends/support/README.md#current-main)
补充 TIMER、CROSS、SLEW、DYNAMICS、COMPOSE、QUALIFICATION 的集成证据。
复验沿用原判据，未扩展能力定义；逐配置版本和结果见收据，支持结论仍只在支持总表维护。

2026-10-11 的 [v2 精度扫描](../../../experiments/backends/support/README.md#precision-v2)
补充 TIMER、CROSS、DYNAMICS、COMPOSE、QUALIFICATION 的有限证据。
新检查器按同一数学参考验收 Q1～Q3，保留合法回调窗口的全部不确定区间和初始保持阶段；
160 个运行配置与原 v1 成绩分开保存。缺少时刻或生效设置证据时不授予通过，
未修改 EVAS 生产行为，也未迁移旧 core 或其他组合的判据。

同日的[配置绑定与补证](../../../experiments/backends/support/README.md#precision-bindings)
继续补充 TIMER、CROSS、DYNAMICS、COMPOSE、QUALIFICATION 的验收依据。
新增 16 次外部后端运行，EVAS 复用首轮相同实现及原生记录；Q 档位、实际配置和验收要求已绑定。
数值、行为与证据状态分别保存，EVAS 阈值采样的回调缺证及极严配置拒绝继续保留。
原 v1/v2 判据与成绩未改写，#131 未动。

[有界运行期事件控制](../../../experiments/backends/support/event-runtime-control/README.md)补充 LANG、EVENT-CONDITIONS 和 EVENT-ORDER：三个实际 Spectre 控制按原 100 nV 门槛及精确整数答案验收；4096 迭代、signed32 中间检查、数组边界及晚失败回退见 test_event_runtime_loops.py。原 CDS 整题尚未完成，不新增 Q 成绩。

保持目标中的嵌套 held `Select` 补充 TRANSITION 与 EVENT-CONDITIONS，见[原算式、结构负控与有限参考](../../../experiments/backends/support/held-transition-targets/README.md)。这里只验证保持量目标的分支展开，不表示完整 MUX 模型或历史谓词已经支持。
