# 开发回归测试

本目录是**开发回归套件**：改代码时确认没有破坏已知行为。
测试用独立答案检查已声明的语义和边界，但不单独授予验证资格。
[validation/](../validation/) 管理条件矩阵与协议；开发测试方法数
不计入矩阵分母，也不能证明所有合法模型和算子组合都已覆盖。

## 如何运行

从 `evas/` 目录执行（需要先构建 Rust 内核）：

```sh
PYTHONPATH=src python3 -m unittest discover tests          # 全量，约 4 分钟
PYTHONPATH=src:tests python3 -m unittest test_idt -v       # 单个文件
```

## GUARDS 守护标签

每个测试文件声明非空 `GUARDS` 列表，标注契约、能力或直接使用的 DUT 模型。
它是文件级导航，不是逐方法覆盖或执行证明；开发主题可加 `DEV:<主题>`。
从仓库根目录运行 `python3 -B scripts/traceability.py --check`，检查标签、
本地目标和[生成矩阵](../docs/TRACEABILITY.md)是否同步。标签语义与生成命令见
[PROCESS.md](../docs/PROCESS.md)。

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
| [test_frontend_limits.py](test_frontend_limits.py) | 语法/参数/IR 预算、共享表达式展开、真实 Rust 传输 |
| [test_manifest.py](test_manifest.py) | manifest 校验、重复字段、CLI 诊断及批次失败隔离 |
| [test_runtime_contracts.py](test_runtime_contracts.py) | 故障响应注入、超时配置及真实子进程回收 |

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
