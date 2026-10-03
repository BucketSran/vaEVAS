# 追溯矩阵（自动生成，勿手编）

由 `scripts/traceability.py` 扫描 `evas/tests/*.py` 的 `GUARDS` 标签生成。
流程与标签语义见 [PROCESS.md](PROCESS.md)。共 40 个测试文件。

## 契约 / 能力 → 守护测试

| 契约/能力 ID | 判据锚点 | 守护测试 |
| --- | --- | --- |
| ANALOG：普通 analog 条件 | [锚点](../validation/ANALOG_CONDITIONS_CONTRACT.md) | [test_affine](../tests/test_affine.py) [test_analog_conditions](../tests/test_analog_conditions.py) [test_contracts](../tests/test_contracts.py) |
| LANG：语言/绑定/IR 契约 | [锚点](../README.md#实现范围) | [test_contracts](../tests/test_contracts.py) |
| LIN：线性电压关系 | [锚点](math/solving.md) | [test_accuracy](../tests/test_accuracy.py) [test_affine](../tests/test_affine.py) |
| NONLINEAR-TRANSIENT：非线性瞬态契约 | [锚点](../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | [test_mixed_dynamics](../tests/test_mixed_dynamics.py) [test_nonlinear](../tests/test_nonlinear.py) [test_nonlinear_transient](../tests/test_nonlinear_transient.py) [test_precision_chain](../tests/test_precision_chain.py) |
| SPARSE：稀疏线性代数 | [锚点](math/solving.md#稀疏分支与性能边界) | [test_sparse](../tests/test_sparse.py) [test_sparse_transient](../tests/test_sparse_transient.py) |
| CROSS：阈值事件 | [锚点](math/events.md) | [test_dynamic_cross](../tests/test_dynamic_cross.py) [test_events](../tests/test_events.py) |
| TIMED-OPERATOR：定时与波形算子契约 | [锚点](../validation/TIMED_OPERATOR_CONTRACTS.md) | [test_absdelay](../tests/test_absdelay.py) [test_absdelay_accuracy](../tests/test_absdelay_accuracy.py) [test_semantic_invariants](../tests/test_semantic_invariants.py) [test_slew](../tests/test_slew.py) [test_slew_accuracy](../tests/test_slew_accuracy.py) [test_timed_composition](../tests/test_timed_composition.py) [test_timer](../tests/test_timer.py) [test_transition](../tests/test_transition.py) [test_transition_accuracy](../tests/test_transition_accuracy.py) |
| EVENT-CONDITIONS：事件条件与采样复位契约 | [锚点](../validation/EVENT_CONDITIONS_CONTRACT.md) | [test_dynamic_cross](../tests/test_dynamic_cross.py) [test_event_accuracy](../tests/test_event_accuracy.py) [test_event_conditions](../tests/test_event_conditions.py) [test_event_or](../tests/test_event_or.py) [test_event_window_sampling](../tests/test_event_window_sampling.py) [test_event_writers](../tests/test_event_writers.py) [test_events](../tests/test_events.py) [test_settlement](../tests/test_settlement.py) |
| DYNAMICS：积分与共同生命周期契约 | [锚点](../validation/DYNAMICS_CONTRACTS.md) | [test_continuous_dynamics](../tests/test_continuous_dynamics.py) [test_dynamic_closure](../tests/test_dynamic_closure.py) [test_dynamic_cross](../tests/test_dynamic_cross.py) [test_event_horizons](../tests/test_event_horizons.py) [test_event_window_sampling](../tests/test_event_window_sampling.py) [test_gap_integration](../tests/test_gap_integration.py) [test_idt](../tests/test_idt.py) [test_idt_accuracy](../tests/test_idt_accuracy.py) [test_implicit_dynamics](../tests/test_implicit_dynamics.py) [test_lifecycle_closure](../tests/test_lifecycle_closure.py) [test_mixed_dynamics](../tests/test_mixed_dynamics.py) [test_phase](../tests/test_phase.py) [test_semantic_invariants](../tests/test_semantic_invariants.py) |
| LAPLACE：滤波契约 | [锚点](../validation/LAPLACE_CONTRACTS.md) | [test_laplace](../tests/test_laplace.py) |
| COMPOSE：实例与组合义务 | [锚点](math/continuous.md) | [test_gap_integration](../tests/test_gap_integration.py) |
| QUALIFICATION：独立验收矩阵 | [锚点](../validation/README.md) | **无守护测试（缺口）** |

### 具体条件 DUT（case:*）

| 条件 | 守护测试 |
| --- | --- |
| case:d2_v7_01 | `test_affine.py` |
| case:n_v1_02 | `test_affine.py` |

### 纯开发回归（DEV:*，无契约对应，诚实标注）

| 主题 | 测试 |
| --- | --- |
| DEV:cross-language-arithmetic | `test_interval.py` |
| DEV:ir-migration | `test_migrate.py` |
| DEV:precision-chain | `test_accuracy.py` `test_precision_chain.py` |
| DEV:sparse-reuse | `test_reuse.py` `test_sparse.py` `test_sparse_transient.py` |

## 缺口报告

当前无契约缺口；QUALIFICATION 按设计无单元测试守护（资格只来自矩阵执行收据）；DEV 主题为开发护栏，不要求契约对应。
收据与执行身份见 [CAPABILITIES](CAPABILITIES.md#检查点身份)与[实验目录](../../experiments/README.md)。
