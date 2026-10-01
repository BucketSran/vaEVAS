# EVAS 能力与缺口总表

核对日期：2026-10-01。此工作树为 **EVAS 0.10.0 / IR v16 开发分支**，尚未合并或发布。
已合并基线为 [PR29](https://github.com/BucketSran/vaEVAS/pull/29)，其运行时
`d451605bf9991ceea010c68af9cb1143f1b50754` 的 IR15 收据保持原身份。
旧 IR 1–15 需要从原始 VA/manifest 重新编译；[批量入口](../README.md#ir-v8-migration)
不会重写历史 IR 或收据。Python 与 Rust 必须使用同一 IR 版本。
开发范围和独立验证见[连续动态](CONTINUOUS.md)；已合并实验身份从
[当前证据](../../experiments/parallel-gap-integration/README.md#当前证据)进入。

## 状态约定

- 下表只描述当前源码的限定支持；合法 VA 超出范围时明确拒绝，不因此成为非法语言。
- 实现、有限验证、合并和发布分别记录。合并身份以 Git/PR 为准，没有 tag 不宣称发布。
- 能力 ID 稳定，不等于 PR 号、条件数或测试方法数；单项正确不证明任意组合正确。
- 建议后续工作不自动授权新实现或实验。电流未知量、器件负载及完整 SPICE 不属于默认任务。

## 能力矩阵

| ID / 能力 | 当前限定支持 | 数学、实现与证据入口 | 剩余边界 |
| --- | --- | --- | --- |
| LANG：语法、绑定、IR | 标量/参数、有限常量数组、`M_PI`；普通 analog 局部顺序 `real` 赋值及输入驱动 if/else；事件条件与 cross OR；IR16 及 manifest 批量重编译 | [语法/API](../README.md#实现范围)、[普通条件契约](../validation/ANALOG_CONDITIONS_CONTRACT.md)、[frontend.py](../src/evas/frontend.py) | 条件瞬态限分段仿射；普通条件与事件/历史组合、循环、通用数组、用户函数、通用预处理和层次尚缺 |
| LIN：线性电压关系 | 贡献累加、参考节点、稠密/稀疏求解和固定电路分解复用；原 IR 仿射映射认证瞬态输出 | [数值说明](NUMERICS.md)、[assembly.rs](../rust_core/src/assembly.rs)、[solver.rs](../rust_core/src/solver.rs) | 病态系统和区间保守性；冗余约束须在误差参数域上成立 |
| NONLINEAR：多项式反馈 | 静态阻尼 Newton/解析 Jacobian；无状态、无事件、无历史的多项式瞬态；点值和非点输入均作根盒证明 | [瞬态契约](../validation/NONLINEAR_TRANSIENT_CONTRACT.md)、[根证明与精度链](NUMERICS.md#精度链的已修复反例与边界)、[独立根回归](../tests/test_precision_chain.py) | 瞬态认证限方阵；静态 solve 仍局部收敛；多解选择、非线性事件/历史联立和更广函数尚缺 |
| SPARSE：稀疏线性代数 | n≥32、nnz≤0.1mn 时采用稀疏 LU，电压解与 Newton 共用 | [PR8](https://github.com/BucketSran/vaEVAS/pull/8)、[数值与性能边界](NUMERICS.md#稀疏分支与性能边界) | 历史/根区间认证仍稠密；排序、填充、符号复用见 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) |
| CROSS：阈值事件 | 原 PWL/仿射 guard；开发新增状态独立多项式、连续积分/滤波/受限 sin guard；逐叶认证与同块去重 | [事件数学](EVENTS.md)、[新根证明](CONTINUOUS.md#非线性-guard-的根证明)、[解析根回归](../tests/test_dynamic_cross.py) | 状态或事件修改轨迹、隐式非线性电压轨迹、切线/平台认证、更新后重定位、cross/timer 混合 OR 尚缺 |
| TIMER：固定定时事件 | 固定 start/period/time_tol/enable，有限日程 | [定时与同刻](EVENTS.md#固定-timer)、历史 PR12 | 动态参数与 enable 尚缺 |
| EVENT-ORDER：同刻与提交 | 仿射状态/电压联立、程序顺序赋值、认证条件路径、实际单写者、整批提交/回退；PWL/状态误差跨事件保留 | [生命周期与拒绝](EVENTS.md)、[采样误差回归](../tests/test_precision_chain.py)、[修复 review](../../experiments/parallel-gap-integration/REVIEW.md#precision-chain) | 同批两块写同一状态为 event_conflict；跨块 state 读取拒绝；通用 real 状态相对预算在零附近可能保守；Spectre 重复赋值差异见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16) |
| TRANSITION：延迟与边沿 | 固定延迟、显式正边沿、状态仿射输入；历史误差参与验收 | [算子说明](OPERATORS.md#transition)、历史 PR13 独立 Fraction 与 16/16 配置对照 | 动态参数、零/省略边沿、完整观察资格及更广组合尚缺 |
| ABSDELAY：历史查询 | 固定非负延迟、直接连续 PWL 仿射输入 | [算子说明](OPERATORS.md#absdelay)、历史 PR14 独立答案与 12/12 专项 | 内部节点/状态、可变延迟、跳变、嵌套和反馈尚缺 |
| SLEW：限速与追赶 | 固定正/负限速、直接连续 PWL 仿射输入 | [算子说明](OPERATORS.md#slew)、历史 PR15 专项：EVAS 16/16，Spectre 10/16，步长诊断保留 | 内部节点、动态参数、更广组合尚缺；旧测量不替代当前版本执行 |
| DYNAMICS：积分/滤波/相位 | 原直接 PWL idt/reset、idtmod/sin；开发新增仿射积分电压反馈/线性嵌套、1–8 阶 proper laplace_nd 完整分子、直接 PWL ddt | [基础算子](OPERATORS.md)、[联合数学与数值](CONTINUOUS.md)、[独立闭式回归](../tests/test_continuous_dynamics.py) | 非线性或事件状态动态反馈、联合 reset、内部/算子 ddt、缺省 IC、动态参数、长时间范围和数值预算尚缺 |
| COMPOSE：实例与组合 | 平面实例隔离、限定采样/复位；开发新增线性积分/滤波闭包经过算子和电压关系，保留贡献求和 | [联合数学](CONTINUOUS.md)、[基础组合回归](../tests/test_gap_integration.py)、[依赖图](../rust_core/src/reset_dependencies.rs) | 结构依赖不能由相消/零系数绕过；事件驱动联合网络、非线性动态组合待契约 |
| QUALIFICATION：独立验收 | 原 31 条件两档各 31/31 有限观测；独立数学答案、语义不变性和失败恢复回归 | [最新矩阵](../validation/README.md#latest-evas-checkpoint)、[372 Python / 83 Rust 收据](../../experiments/parallel-gap-integration/results/precision-chain-checks.json) | 正式 DVS 资格 I；原矩阵已参与开发，未见确认集、物理观察误差界与一般连续时间资格尚缺 |
| PERFORMANCE：效率证据 | 稀疏分流、同刻不可变查询复用、标量 R/m 根证明；固定工作负载历史计时 | [优化检查点](../../experiments/parallel-gap-integration/REVIEW.md#accuracy-optimization)、[计时收据](../../experiments/parallel-gap-integration/results/accuracy-optimization-profile.json) | 最新精度链未重测性能，无当前端到端/跨后端速度声明；更广复用与日程见 [Issue24](https://github.com/BucketSran/vaEVAS/issues/24) |

## 工作与证据身份

已合并基线运行时 `d451605` 的 **62 次新本地执行**均达标，CSV、判定和生效设置与 `ddfd379` 一致；
372 Python、83 Rust、locked build、Clippy 和格式检查通过，一项旧性能探针 ignored。
原 DUT、刺激、容差、检查器和分母未改；最新修复没有新 Spectre 执行或性能测量。
完整原始输入、波形、日志与二进制为 **仅本地保留**；公开整理收据不等于公开完整 raw。

历史 PR26 / IR11 的两档各 24/31 仍绑定 `edb004d`，不改写成新版本成绩。
旧联合 IR14、单项分支、功能补齐 `39a4545` 和优化 `ddfd379` 均保持原身份，见
[历史入口与无损收据归档](../../experiments/parallel-gap-integration/README.md#历史与资产)。
更早的交付表保留在[固定历史](https://github.com/BucketSran/vaEVAS/blob/78e914ff97d4902365b76d5c3c87be57c39c83e9/evas/docs/CAPABILITIES.md)。

## 后续工作

原 31 条件在这个有限范围内已经补齐；下面是更广语言/组合能力和证据缺口。
它们不阻塞本受限检查点交付，也不应被读作完整电压域 VA 已完成。

| 方向 | 下一步需先固定的设计与独立验收 |
| --- | --- |
| 联合动态求解 | 本分支已补仿射积分电压反馈和线性滤波联合传播；下一步是事件修改历史、reset 与非线性 DAE，另定义联合误差及重试 |
| 事件扩展 | 本分支已补状态独立多项式/连续算子 guard；剩余事件后轨迹重定位、切线、隐式非线性电压 guard、动态 timer/混合 OR |
| 语言和算子 | 本分支已补直接 PWL ddt 和 1–8 阶滤波；剩余通用导数/函数、过程控制、数组及更广初值/参数语义 |
| 精度/资格 | 通用状态预算、前端折叠误差、一般连续时间误差、独立观察资格与未见确认集，保留拒绝及错误对照 |
| 性能 | 按 Issue9/24 在同范围/误差目标下测准备、首次、重复、瞬态与内存；不要拿旧局部计时代替最新整体速度 |

每项先固定数学契约和接受/拒绝边界，再做独立答案、不变性和失败后完整性检查。
实际范围、依赖、负责人和预算写在对应 Issue/PR；合并或发布只根据真实动作更新状态。
