# EVAS 能力与缺口总表

核对日期：2026-10-03。当前源码为 **EVAS 0.12.2 / IR v16**，已由
[PR33](https://github.com/BucketSran/vaEVAS/pull/33) 合并到 main `b4921ca`，未发布 tag。
逐条件的守护测试与证明收据索引见[追溯矩阵](TRACEABILITY.md)（脚本自动生成，勿手编）；
执行身份与历史检查点见[实验入口](../../experiments/runs/parallel-gap-integration/README.md#当前证据)。

## 状态约定

- 下表只描述当前源码的限定支持；合法 VA 超出范围时明确拒绝，不因此成为非法语言。
- 实现、有限验证、合并和发布分别记录。合并身份以 Git/PR 为准，没有 tag 不宣称发布。
- 能力 ID 稳定，不等于 PR 号、条件数或测试方法数；单项正确不证明任意组合正确。
- 建议后续工作不自动授权新实现或实验。电流未知量、器件负载及完整 SPICE 不属于默认任务。

## 能力矩阵

每行一句话范围 + 一句话缺口；数学细节在 [math/](math/README.md) 对应章节展开。

| ID / 能力 | 限定支持（摘要） | 数学入口 | 剩余边界（摘要） |
| --- | --- | --- | --- |
| LANG | 标量/参数、有限常量数组、局部顺序赋值与输入 if/else、事件条件与 cross OR | [语法/API](../README.md#实现范围)、[普通条件契约](../validation/ANALOG_CONDITIONS_CONTRACT.md) | 条件瞬态限分段仿射；循环、通用数组、用户函数、预处理和层次尚缺 |
| LIN | 贡献累加、参考节点、稠密/稀疏求解与分解复用 | [求解](math/solving.md) | 病态系统与区间保守性 |
| NONLINEAR | 静态阻尼 Newton；无状态多项式瞬态根盒证明 | [求解与精度链](math/solving.md#精度链的已修复反例与边界)、[瞬态契约](../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | 瞬态认证限方阵；多解全局选择、更广函数尚缺 |
| SPARSE | n≥32 且 nnz≤0.1mn 时稀疏 LU | [稀疏分支](math/solving.md#稀疏分支与性能边界) | 认证仍稠密；排序/复用见 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) |
| CROSS | PWL/仿射/状态独立多项式/连续积分/滤波/受限 sin guard，逐叶认证 | [事件数学](math/events.md)、[根证明](math/continuous.md#非线性-guard-的根证明) | 事件修改轨迹、隐式非线性 guard、切线认证、更新后重定位尚缺 |
| TIMER | 固定 start/period/time_tol/enable，有限日程 | [定时](math/events.md#固定-timer) | 动态参数与 enable 尚缺 |
| EVENT-ORDER | 同刻联立、程序顺序赋值、单写者、整批提交/回退 | [生命周期](math/events.md) | 同批双写拒绝；预算保守；Spectre 差异见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16) |
| TRANSITION | 固定延迟、显式正边沿，历史误差参与验收 | [算子](math/operators.md#transition) | 动态参数、零/省略边沿及更广组合尚缺 |
| ABSDELAY | 固定非负延迟、直接连续 PWL 仿射输入 | [算子](math/operators.md#absdelay) | 内部节点、可变延迟、跳变、嵌套和反馈尚缺 |
| SLEW | 固定正/负限速、直接连续 PWL 仿射输入 | [算子](math/operators.md#slew) | 内部节点、动态参数、更广组合尚缺 |
| DYNAMICS | idt/idtmod/sin、积分反馈、联合 reset、1–8 阶滤波、受限 ddt、index-one 多项式 DAE | [算子](math/operators.md)、[联合数学](math/continuous.md) | DAE 与事件/复位/滤波/ddt 组合、非线性滤波 DC、通用函数混合等尚缺 |
| COMPOSE | 平面实例隔离、积分/滤波闭包、DC 与瞬态导数一致求值、事件重启复用物理历史 | [联合数学](math/continuous.md) | 结构依赖不可绕过；非线性混合限积分+proper 滤波 |
| QUALIFICATION | 原矩阵两档各 31/31（IR16 检查点） | [验证集](../validation/README.md)、[追溯矩阵](TRACEABILITY.md) | 正式 DVS 资格 I；未见确认集与一般连续时间资格尚缺 |
| PERFORMANCE | 稀疏分流、查询复用、标量根证明；固定工作负载历史计时 | [优化检查点](../../experiments/runs/parallel-gap-integration/REVIEW.md#accuracy-optimization) | 当前运行时未重测；见 [Issue24](https://github.com/BucketSran/vaEVAS/issues/24) |

## 检查点身份

| 检查点 | 固定执行身份 |
| --- | --- |
| PR33 / IR16：事件截止点 | 运行时 `8618339`，合并点 `b4921ca` |
| PR32 / IR16：混合动态与生命周期 | 运行时 `1b99c33`，合并点 `431f335` |
| PR31 / IR16：非线性积分与联合事件 | 运行时 `d06e7f3`，合并点 `09b4222` |
| PR30 / IR16：连续动态 | 运行时 `ba5ab46`/`071a813`，合并点 `bedf20f` |
| PR29 / IR15：矩阵补齐与精度链 | 运行时 `d451605` |
| PR26 / IR11 及旧 EVAS 0.8.7 | 历史失败不改写为新版本成绩，见 [四后端矩阵](../../experiments/backends/dvs2-four-backend-validation/results/MATRIX.md) |

各检查点的收据与审查材料入口由[追溯矩阵](TRACEABILITY.md)与
[实验目录](../../experiments/README.md)导航；早期失败（根盒等号、复位误拒绝、
Spectre 不一致等）保留在对应历史段落，修复不删除。

## 后续工作

原 31 条件在本范围内已补齐；更广能力缺口（联合动态求解组合、事件扩展、
语言算子、精度资格、性能测量）按[共同生命周期契约](../validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract)
分批推进。每项先固定数学契约和接受/拒绝边界，再做独立答案、不变性和失败后
完整性检查。实际范围、依赖、负责人和预算写在对应 Issue/PR。
