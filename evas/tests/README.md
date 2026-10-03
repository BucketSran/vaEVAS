# 开发回归测试

本目录是**开发回归套件**：改代码时确认没有破坏已知行为。
它回答"这次改动有没有引入回归"，不回答"EVAS 语义是否正确"——
后者由上级 [validation/](../validation/) 的固定条件矩阵与协议回答。
套件中每个文件都声明自己不是验证矩阵的追加条件
（如 `test_idt.py` 的 "development cases, not additional conditions in the
original matrix"）；通过 506 个测试不等于获得 506 项验证。

## 如何运行

从 `evas/` 目录执行（需要先构建 Rust 内核）：

```sh
PYTHONPATH=src python3 -m unittest discover tests          # 全量，约 4 分钟
PYTHONPATH=src python3 -m unittest tests.test_idt -v       # 单个文件
```

## GUARDS 守护标签

每个测试文件顶部声明 `GUARDS = [...]`，标注它守护的契约/能力/条件 ID
（纯开发回归用 `DEV:<主题>` 诚实标注）。标签由
`scripts/traceability.py` 扫描生成 [docs/TRACEABILITY.md](../docs/TRACEABILITY.md)；
`python3 scripts/traceability.py --check` 拒绝无标签文件。流程规则见
[docs/PROCESS.md](../docs/PROCESS.md)。

## 期望值的独立性约定

所有期望值独立于被测实现固定：精确分数（`Fraction`）梯形积分、
`Decimal` 代数参考、闭式解或代入推导的手算答案；不使用内核自身的
历史、采样网格或输出作为 oracle。新增测试必须延续该约定并在
docstring 中说明答案来源，不得以"EVAS 当前输出"为期望值。

## 文件分组

### 按特性的功能回归

| 文件 | 覆盖 |
| --- | --- |
| [test_affine.py](test_affine.py) | 公开编译/求解入口的行为契约 |
| [test_contracts.py](test_contracts.py) | 参数绑定与版本化分支身份契约 |
| [test_analog_conditions.py](test_analog_conditions.py) | 普通模拟赋值与 if/else |
| [test_idt.py](test_idt.py) | 首个受限积分（精确分数 oracle） |
| [test_absdelay.py](test_absdelay.py) / [test_timer.py](test_timer.py) / [test_transition.py](test_transition.py) / [test_slew.py](test_slew.py) | 延迟 / 定时 / 边沿 / 转换速率 |
| [test_laplace.py](test_laplace.py) / [test_phase.py](test_phase.py) | 一阶滤波 / idtmod-sin 相位 |
| [test_nonlinear.py](test_nonlinear.py) / [test_nonlinear_transient.py](test_nonlinear_transient.py) | 多项式静态与瞬态 |
| [test_migrate.py](test_migrate.py) | IR16 迁移与批量重编译 |

### 精度与准确性

`*_accuracy.py` 系列（[absdelay](test_absdelay_accuracy.py)、
[event](test_event_accuracy.py)、[idt](test_idt_accuracy.py)、
[slew](test_slew_accuracy.py)、[transition](test_transition_accuracy.py)、
[test_accuracy.py](test_accuracy.py)）与
[test_precision_chain.py](test_precision_chain.py)：
用独立代数/Decimal/分数参考检查电压与事件时刻误差；
阈值描述这些具体问题，不是全局误差界。

### 组合与不变量

| 文件 | 覆盖 |
| --- | --- |
| [test_settlement.py](test_settlement.py) | 同刻联立事件方程与拒绝控制 |
| [test_events.py](test_events.py) / [test_dynamic_cross.py](test_dynamic_cross.py) / [test_event_or.py](test_event_or.py) / [test_event_writers.py](test_event_writers.py) | cross / 动态根 / OR / 写者冲突 |
| [test_event_conditions.py](test_event_conditions.py) | 独立事件体答案 |
| [test_event_horizons.py](test_event_horizons.py) / [test_event_window_sampling.py](test_event_window_sampling.py) | 已知事件截止点 / 根盒采样认证 |
| [test_continuous_dynamics.py](test_continuous_dynamics.py) / [test_mixed_dynamics.py](test_mixed_dynamics.py) / [test_implicit_dynamics.py](test_implicit_dynamics.py) | 连续动力学 / 混合算子 / index-one DAE |
| [test_dynamic_closure.py](test_dynamic_closure.py) / [test_lifecycle_closure.py](test_lifecycle_closure.py) / [test_gap_integration.py](test_gap_integration.py) | 动态组合 / 复位后闭包 / 跨特性组合 |
| [test_timed_composition.py](test_timed_composition.py) / [test_semantic_invariants.py](test_semantic_invariants.py) | 定时组合 / 蜕变历史探针 |
| [test_sparse.py](test_sparse.py) / [test_sparse_transient.py](test_sparse_transient.py) / [test_reuse.py](test_reuse.py) | 稀疏规模 / 重复求解 |
| [test_interval.py](test_interval.py) | Rust 事件算术 vs Python 精确分数 |

### 独立脚本（非 unittest）

| 脚本 | 用途 |
| --- | --- |
| [run_static_regression.py](run_static_regression.py) | 重放 31 条件的静态点；被拒条件如实记录 |
| [benchmark_events.py](benchmark_events.py) | 发布内核的事件规模性能检查，非仿真器排名 |

## 准入约定

- 新文件命名 `test_<特性>.py`，docstring 声明期望值来源；
- 修改不得把被测实现的输出固化为期望值；
- 需要正式验证资格的条件进入 [validation/](../validation/)，不在本目录扩充。
