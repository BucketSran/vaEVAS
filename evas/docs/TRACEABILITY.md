# 追溯矩阵（自动生成，勿手编）

由 `scripts/traceability.py` 读取测试 `GUARDS`、能力表及 DUT 目录生成。
流程与标签语义见 [PROCESS.md](PROCESS.md)。共 62 个测试文件。
标签是人工审查的文件级关联，不证明完整覆盖、测试通过或先红后绿。
证据链接沿用能力表中的检查点，不自动认证当前代码；实现入口见数学章节的代码地图。

## 契约 / 能力 → 守护测试

| 契约/能力 ID | 契约或数学入口 | 已声明的守护测试 | 证据入口 |
| --- | --- | --- | --- |
| LANG | [契约/数学](../README.md#实现范围) | [test_affine](../tests/test_affine.py) [test_contracts](../tests/test_contracts.py) [test_dynamic_timer](../tests/test_dynamic_timer.py) [test_frontend_diagnostics](../tests/test_frontend_diagnostics.py) [test_frontend_limits](../tests/test_frontend_limits.py) [test_hierarchy](../tests/test_hierarchy.py) [test_initial_events](../tests/test_initial_events.py) [test_loop_histories](../tests/test_loop_histories.py) [test_manifest](../tests/test_manifest.py) [test_parameter_constraints](../tests/test_parameter_constraints.py) [test_preprocessor](../tests/test_preprocessor.py) [test_query](../tests/test_query.py) [test_runtime_contracts](../tests/test_runtime_contracts.py) [test_scs](../tests/test_scs.py) [test_static_loops](../tests/test_static_loops.py) [test_user_functions](../tests/test_user_functions.py) [test_variable_arrays](../tests/test_variable_arrays.py) [test_vector_ports](../tests/test_vector_ports.py) | [普通条件历史检查](../../experiments/archive/pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz)、[函数开发测试](../tests/test_user_functions.py)、[循环开发测试](../tests/test_static_loops.py)、[向量测试](../tests/test_vector_ports.py)、[测试台适配](../tests/test_scs.py) |
| LIN | [契约/数学](math/solving.md) | [test_accuracy](../tests/test_accuracy.py) [test_affine](../tests/test_affine.py) [test_contracts](../tests/test_contracts.py) [test_parallel](../tests/test_parallel.py) [test_refinement](../tests/test_refinement.py) [test_reuse](../tests/test_reuse.py) [test_static_loops](../tests/test_static_loops.py) [test_user_functions](../tests/test_user_functions.py) | [原矩阵检查点](../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json) |
| NONLINEAR | [求解与精度链](math/solving.md#精度链的已修复反例与边界)、[瞬态契约](../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | [test_nonlinear](../tests/test_nonlinear.py) [test_nonlinear_transient](../tests/test_nonlinear_transient.py) [test_parallel](../tests/test_parallel.py) | [精度链检查点](../../experiments/runs/parallel-gap-integration/results/precision-chain-checks.json) |
| SPARSE | [契约/数学](math/solving.md#稀疏分支与性能边界) | [test_refinement](../tests/test_refinement.py) [test_reuse](../tests/test_reuse.py) [test_sparse](../tests/test_sparse.py) [test_sparse_transient](../tests/test_sparse_transient.py) | [当前配对测量](../../experiments/performance/README.md)、[历史 PR8](https://github.com/BucketSran/vaEVAS/pull/8) |
| CROSS | [契约/数学](math/events.md) | [test_dynamic_cross](../tests/test_dynamic_cross.py) [test_event_accuracy](../tests/test_event_accuracy.py) [test_event_relocalization](../tests/test_event_relocalization.py) [test_events](../tests/test_events.py) [test_user_functions](../tests/test_user_functions.py) | [动态根历史检查点](../../experiments/runs/parallel-gap-integration/results/dynamic-closure-review-checks.json)、[重定位开发测试](../tests/test_event_relocalization.py) |
| TIMER | [事件手册](math/events.md)、[定时契约](../validation/TIMED_OPERATOR_CONTRACTS.md) | [test_dynamic_timer](../tests/test_dynamic_timer.py) [test_event_relocalization](../tests/test_event_relocalization.py) [test_frontend_diagnostics](../tests/test_frontend_diagnostics.py) [test_timer](../tests/test_timer.py) | [动态开发测试](../tests/test_dynamic_timer.py)、[固定时钟测试](../tests/test_timer.py) |
| EVENT-ORDER | [生命周期](math/events.md) | [test_diagnostics](../tests/test_diagnostics.py) [test_dynamic_timer](../tests/test_dynamic_timer.py) [test_event_conditions](../tests/test_event_conditions.py) [test_event_or](../tests/test_event_or.py) [test_event_relocalization](../tests/test_event_relocalization.py) [test_event_writers](../tests/test_event_writers.py) [test_initial_events](../tests/test_initial_events.py) [test_settlement](../tests/test_settlement.py) [test_variable_arrays](../tests/test_variable_arrays.py) | [事件条件历史对照](../../experiments/archive/pr14-pr15-validation/results/event-conditions-0.9.0.json) |
| TRANSITION | [算子](math/operators.md#transition) | [test_semantic_invariants](../tests/test_semantic_invariants.py) [test_transition](../tests/test_transition.py) [test_transition_accuracy](../tests/test_transition_accuracy.py) | [历史误差修复对照](../../experiments/backends/dvs2-spectre-validation/results/transition-0.6.1.json) |
| ABSDELAY | [算子](math/operators.md#absdelay) | [test_absdelay](../tests/test_absdelay.py) [test_absdelay_accuracy](../tests/test_absdelay_accuracy.py) [test_history_projection](../tests/test_history_projection.py) | [专项历史对照](../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../tests/test_history_projection.py) |
| SLEW | [算子](math/operators.md#slew) | [test_history_projection](../tests/test_history_projection.py) [test_slew](../tests/test_slew.py) [test_slew_accuracy](../tests/test_slew_accuracy.py) | [专项历史对照](../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../tests/test_history_projection.py) |
| DYNAMICS | [契约/数学](../validation/DYNAMICS_CONTRACTS.md) | [test_continuous_dynamics](../tests/test_continuous_dynamics.py) [test_dynamic_closure](../tests/test_dynamic_closure.py) [test_dynamic_cross](../tests/test_dynamic_cross.py) [test_event_horizons](../tests/test_event_horizons.py) [test_event_window_sampling](../tests/test_event_window_sampling.py) [test_frontend_diagnostics](../tests/test_frontend_diagnostics.py) [test_gap_integration](../tests/test_gap_integration.py) [test_hierarchy](../tests/test_hierarchy.py) [test_idt](../tests/test_idt.py) [test_idt_accuracy](../tests/test_idt_accuracy.py) [test_implicit_dynamics](../tests/test_implicit_dynamics.py) [test_implicit_filters](../tests/test_implicit_filters.py) [test_laplace](../tests/test_laplace.py) [test_lifecycle_closure](../tests/test_lifecycle_closure.py) [test_loop_histories](../tests/test_loop_histories.py) [test_mixed_dynamics](../tests/test_mixed_dynamics.py) [test_phase](../tests/test_phase.py) [test_preprocessor](../tests/test_preprocessor.py) | [截止点与矩阵检查点](../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json)、[DAE/滤波开发测试](../tests/test_implicit_filters.py) |
| COMPOSE | [契约/数学](math/continuous.md) | [test_affine](../tests/test_affine.py) [test_diagnostics](../tests/test_diagnostics.py) [test_frontend_limits](../tests/test_frontend_limits.py) [test_gap_integration](../tests/test_gap_integration.py) [test_hierarchy](../tests/test_hierarchy.py) [test_history_projection](../tests/test_history_projection.py) [test_implicit_filters](../tests/test_implicit_filters.py) [test_loop_histories](../tests/test_loop_histories.py) [test_mixed_dynamics](../tests/test_mixed_dynamics.py) [test_preprocessor](../tests/test_preprocessor.py) [test_query](../tests/test_query.py) [test_semantic_invariants](../tests/test_semantic_invariants.py) [test_static_loops](../tests/test_static_loops.py) [test_user_functions](../tests/test_user_functions.py) [test_variable_arrays](../tests/test_variable_arrays.py) | [观察与依赖修复检查点](../../experiments/runs/parallel-gap-integration/results/lifecycle-observation-review-fixes.json) |
| QUALIFICATION | [契约/数学](../validation/README.md) | 以执行证据为准 | [提交前审查收据](../../experiments/runs/capability-completion/review-receipt.json)、[一致初值收据](../../experiments/runs/capability-completion/joint-dc-receipt.json)、[前一候选收据](../../experiments/runs/capability-completion/receipt.json)、[合并基线收据](../../experiments/performance/matrix.json) |
| PERFORMANCE | [求解手册](math/solving.md#稀疏分支与性能边界)、[只读诊断](diagnostics.md) | [test_diagnostics](../tests/test_diagnostics.py) [test_parallel](../tests/test_parallel.py) | [当前库内与进程测量](../../experiments/performance/README.md)、[历史计时](../../experiments/runs/solver-performance.json) |
| ANALOG | [契约](../validation/ANALOG_CONDITIONS_CONTRACT.md) | [test_analog_conditions](../tests/test_analog_conditions.py) | 按所属能力查阅；此行不绑定执行 |
| NONLINEAR-TRANSIENT | [契约](../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | [test_nonlinear_transient](../tests/test_nonlinear_transient.py) [test_precision_chain](../tests/test_precision_chain.py) | 按所属能力查阅；此行不绑定执行 |
| TIMED-OPERATOR | [契约](../validation/TIMED_OPERATOR_CONTRACTS.md) | [test_absdelay](../tests/test_absdelay.py) [test_absdelay_accuracy](../tests/test_absdelay_accuracy.py) [test_history_projection](../tests/test_history_projection.py) [test_semantic_invariants](../tests/test_semantic_invariants.py) [test_slew](../tests/test_slew.py) [test_slew_accuracy](../tests/test_slew_accuracy.py) [test_timed_composition](../tests/test_timed_composition.py) [test_timer](../tests/test_timer.py) [test_transition](../tests/test_transition.py) [test_transition_accuracy](../tests/test_transition_accuracy.py) | 按所属能力查阅；此行不绑定执行 |
| EVENT-CONDITIONS | [契约](../validation/EVENT_CONDITIONS_CONTRACT.md) | [test_dynamic_cross](../tests/test_dynamic_cross.py) [test_event_conditions](../tests/test_event_conditions.py) [test_event_or](../tests/test_event_or.py) [test_event_relocalization](../tests/test_event_relocalization.py) [test_event_window_sampling](../tests/test_event_window_sampling.py) [test_event_writers](../tests/test_event_writers.py) [test_events](../tests/test_events.py) [test_settlement](../tests/test_settlement.py) | 按所属能力查阅；此行不绑定执行 |
| LAPLACE | [契约](../validation/LAPLACE_CONTRACTS.md) | [test_implicit_filters](../tests/test_implicit_filters.py) [test_laplace](../tests/test_laplace.py) [test_mixed_dynamics](../tests/test_mixed_dynamics.py) | 按所属能力查阅；此行不绑定执行 |

### 直接使用的 DUT 模型（case:*）

列出当前 DUT 目录；模型 ID 不等于运行条件 ID，未声明关联也不代表未被矩阵执行。

| 模型 | 已声明的守护测试 |
| --- | --- |
| [case:d2_v1_01](../validation/cases/d2_v1_01/dut.va) | 未声明关联 |
| [case:d2_v2_01](../validation/cases/d2_v2_01/dut.va) | 未声明关联 |
| [case:d2_v3_01](../validation/cases/d2_v3_01/dut.va) | 未声明关联 |
| [case:d2_v4_01](../validation/cases/d2_v4_01/dut.va) | 未声明关联 |
| [case:d2_v5_01](../validation/cases/d2_v5_01/dut.va) | 未声明关联 |
| [case:d2_v6_01](../validation/cases/d2_v6_01/dut.va) | 未声明关联 |
| [case:d2_v6_01_standard](../validation/cases/d2_v6_01_standard/dut.va) | 未声明关联 |
| [case:d2_v7_01](../validation/cases/d2_v7_01/dut.va) | [test_affine](../tests/test_affine.py) |
| [case:d2_v7_02](../validation/cases/d2_v7_02/dut.va) | 未声明关联 |
| [case:event_relocalization](../validation/cases/event_relocalization/dut.va) | [test_event_relocalization](../tests/test_event_relocalization.py) |
| [case:hierarchy](../validation/cases/hierarchy/dut.va) | [test_hierarchy](../tests/test_hierarchy.py) |
| [case:n_v1_02](../validation/cases/n_v1_02/dut.va) | [test_affine](../tests/test_affine.py) |
| [case:n_v1_02_reordered](../validation/cases/n_v1_02_reordered/dut.va) | 未声明关联 |
| [case:n_v3_02](../validation/cases/n_v3_02/dut.va) | 未声明关联 |
| [case:n_v4_02](../validation/cases/n_v4_02/dut.va) | 未声明关联 |
| [case:n_v6_02](../validation/cases/n_v6_02/dut.va) | 未声明关联 |
| [case:n_v6_03](../validation/cases/n_v6_03/dut.va) | 未声明关联 |
| [case:preprocessor](../validation/cases/preprocessor/dut.va) | [test_preprocessor](../tests/test_preprocessor.py) |
| [case:projected_history](../validation/cases/projected_history/dut.va) | [test_history_projection](../tests/test_history_projection.py) |
| [case:pure_function](../validation/cases/pure_function/dut.va) | [test_user_functions](../tests/test_user_functions.py) |
| [case:static_loop](../validation/cases/static_loop/dut.va) | [test_static_loops](../tests/test_static_loops.py) |
| [case:variable_array](../validation/cases/variable_array/dut.va) | [test_variable_arrays](../tests/test_variable_arrays.py) |

### 开发主题（DEV:*，可与契约标签并存）

| 主题 | 测试 |
| --- | --- |
| DEV:cross-language-arithmetic | [test_interval](../tests/test_interval.py) |
| DEV:ir-migration | [test_migrate](../tests/test_migrate.py) |
| DEV:manifest-input | [test_manifest](../tests/test_manifest.py) |
| DEV:precision-chain | [test_accuracy](../tests/test_accuracy.py) [test_precision_chain](../tests/test_precision_chain.py) |
| DEV:runtime-protocol | [test_runtime_contracts](../tests/test_runtime_contracts.py) |
| DEV:scs-input | [test_scs](../tests/test_scs.py) |
| DEV:sparse-reuse | [test_reuse](../tests/test_reuse.py) [test_sparse](../tests/test_sparse.py) [test_sparse_transient](../tests/test_sparse_transient.py) |

## 关联缺口

登记的能力/契约已有文件级关联（QUALIFICATION、PERFORMANCE 以执行证据为准）。
本表不枚举所有语义组合或逐条测试方法，不能据此声称没有测试或实现缺口。
收据与执行身份见 [CAPABILITIES](CAPABILITIES.md#检查点身份)与[实验目录](../../experiments/README.md)。
