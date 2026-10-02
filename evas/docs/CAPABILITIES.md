# EVAS 能力与缺口总表

核对日期：2026-10-02。当前源码为 **EVAS 0.12.2 / IR v16**，已由
[PR33](https://github.com/BucketSran/vaEVAS/pull/33) 合并到 main `b4921ca`，未发布 tag。
[已知事件截止点](CONTINUOUS.md#known-event-horizons)被测运行时为 `8618339`；
[当前证据](../../experiments/parallel-gap-integration/README.md#当前证据)保存执行、审查与集成身份。
旧收据保留执行时的提交/分支状态，不由合并或清理改写。
旧 IR 1–15 需要从原始 VA/manifest 重新编译；[批量入口](../README.md#ir-v8-migration)
不会重写历史 IR 或收据。Python 与 Rust 必须使用同一 IR 版本。

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
| NONLINEAR：多项式反馈 | 静态阻尼 Newton/解析 Jacobian；无状态、无事件、无历史的多项式瞬态；点值和非点输入均作根盒证明 | [瞬态契约](../validation/NONLINEAR_TRANSIENT_CONTRACT.md)、[根证明与精度链](NUMERICS.md#精度链的已修复反例与边界)、[独立根回归](../tests/test_precision_chain.py) | 瞬态认证限方阵；静态 solve 仍局部收敛；多解全局选择、更广函数尚缺；受限 index-one 多项式 DAE 与积分联合延续见 DYNAMICS |
| SPARSE：稀疏线性代数 | n≥32、nnz≤0.1mn 时采用稀疏 LU，电压解与 Newton 共用 | [PR8](https://github.com/BucketSran/vaEVAS/pull/8)、[数值与性能边界](NUMERICS.md#稀疏分支与性能边界) | 历史/根区间认证仍稠密；排序、填充、符号复用见 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) |
| CROSS：阈值事件 | 原 PWL/仿射 guard；新增状态独立多项式、连续线性/多项式积分、滤波/受限 sin guard；逐叶认证与同块去重 | [事件数学](EVENTS.md)、[新根证明](CONTINUOUS.md#非线性-guard-的根证明)、[解析根回归](../tests/test_dynamic_cross.py) | 状态或事件修改轨迹、隐式非线性电压轨迹、切线/平台认证、更新后重定位、cross/timer 混合 OR 尚缺 |
| TIMER：固定定时事件 | 固定 start/period/time_tol/enable，有限日程 | [定时与同刻](EVENTS.md#固定-timer)、历史 PR12 | 动态参数与 enable 尚缺 |
| EVENT-ORDER：同刻与提交 | 仿射状态/电压联立、程序顺序赋值、认证条件路径、实际单写者、整批提交/回退；PWL/状态误差跨事件保留 | [生命周期与拒绝](EVENTS.md)、[采样误差回归](../tests/test_precision_chain.py)、[修复 review](../../experiments/parallel-gap-integration/REVIEW.md#precision-chain) | 同批两块写同一状态为 event_conflict；跨块 state 读取拒绝；通用 real 状态相对预算在零附近可能保守；Spectre 重复赋值差异见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16) |
| TRANSITION：延迟与边沿 | 固定延迟、显式正边沿、状态仿射输入；历史误差参与验收 | [算子说明](OPERATORS.md#transition)、历史 PR13 独立 Fraction 与 16/16 配置对照 | 动态参数、零/省略边沿、完整观察资格及更广组合尚缺 |
| ABSDELAY：历史查询 | 固定非负延迟、直接连续 PWL 仿射输入 | [算子说明](OPERATORS.md#absdelay)、历史 PR14 独立答案与 12/12 专项 | 内部节点/状态、可变延迟、跳变、嵌套和反馈尚缺 |
| SLEW：限速与追赶 | 固定正/负限速、直接连续 PWL 仿射输入 | [算子说明](OPERATORS.md#slew)、历史 PR15 专项：EVAS 16/16，Spectre 10/16，步长诊断保留 | 内部节点、动态参数、更广组合尚缺；旧测量不替代当前版本执行 |
| DYNAMICS：积分/滤波/相位 | 原直接 PWL idt/reset、idtmod/sin；新增仿射/多项式积分反馈、事件保持输入与联合 reset、共同复位后采样闭包、独立已知 timer/仿射源 cross 截止点的非线性传播、上端点代表时刻的根盒采样/稳定条件与触发根等号认证、积分与 proper 滤波混合及已知历史上的事件后多项式滤波反馈、无事件 index-one 多项式隐式 DAE、1–8 阶完整滤波、受限内部/算子输入 ddt | [基础算子](OPERATORS.md)、[联合数学与数值](CONTINUOUS.md)、[截止点回归](../tests/test_event_horizons.py)、[闭式与组合回归](../tests/test_dynamic_closure.py) | 隐式 DAE 与事件/复位/滤波/ddt 组合；首次启动的非线性滤波 DC、非线性直接通路、通用函数/ddt 混合、时间盒内部代表时刻、复位固定点环、直接项/导数暴露的事件反馈联合认证、跳变/高指标导数、缺省 IC、动态参数；动态 guard 网络仍要求整段预测；其他算子的非精确历史采样未纳入本轮认证；不确定条件或超预算采样仍拒绝 |
| COMPOSE：实例与组合 | 平面实例隔离、限定采样/复位；积分/滤波闭包经过算子和电压关系，支持受限多项式混合和隐式 DAE，保留贡献求和；DC 与瞬态输入导数在整个网络内分别一致求值；事件重启复用物理历史，仅实际复位积分写入 IC；共同闭包后再按已知事件截止点安装非线性未来历史 | [联合数学](CONTINUOUS.md)、[初始化组合义务](CONTINUOUS.md#初始化组合的独立行为义务)、[基础组合回归](../tests/test_gap_integration.py)、[依赖图](../rust_core/src/reset_dependencies.rs) | 结构依赖不能由相消/零系数绕过；ddt 直接通路不进入连续 cross；非线性混合只含积分和 proper 滤波；非严格 proper 直接项事件反馈环保守拒绝；首次启动的非线性滤波 DC、非线性直接通路、隐式 DAE 与事件/其他算子组合及事件后 guard 重定位仍缺 |
| QUALIFICATION：独立验收 | 共同闭包和已知事件截止点各自重跑原 31 条件，两档各 31/31；追加修复统一根盒观察与导数瞬时依赖，证据按快照区分，矩阵分母不变 | [本地截止点检查](../../experiments/parallel-gap-integration/results/event-horizon-checks.json)、[观察与依赖修复](../../experiments/parallel-gap-integration/results/lifecycle-observation-review-fixes.json)、[共同闭包检查](../../experiments/parallel-gap-integration/results/lifecycle-closure-checks.json)、[独立审查修复](../../experiments/parallel-gap-integration/results/certified-mixed-review-fixes.json)、[修复前检查](../../experiments/parallel-gap-integration/results/certified-mixed-dynamics-checks.json)、[修复前矩阵](../../experiments/parallel-gap-integration/results/certified-mixed-dynamics-matrix.json)、 [最终审查检查](../../experiments/parallel-gap-integration/results/dynamic-closure-review-checks.json)、[事件窗口检查](../../experiments/parallel-gap-integration/results/nonlinear-event-window-checks.json)、[首轮检查](../../experiments/parallel-gap-integration/results/dynamic-closure-checks.json)、[PR30 初始化收据](../../experiments/parallel-gap-integration/results/continuous-initialization-review.json)、[首轮 IR16 检查](../../experiments/parallel-gap-integration/results/continuous-dynamics-checks.json)、[历史 IR15 证据](../validation/README.md#ir15-checkpoint) | 正式 DVS 资格 I；原矩阵已参与开发，未见确认集、物理观察误差界与一般连续时间资格尚缺 |
| PERFORMANCE：效率证据 | 稀疏分流、同刻不可变查询复用、标量 R/m 根证明；固定工作负载历史计时 | [优化检查点](../../experiments/parallel-gap-integration/REVIEW.md#accuracy-optimization)、[计时收据](../../experiments/parallel-gap-integration/results/accuracy-optimization-profile.json) | 当前运行时未重测性能，无当前端到端/跨后端速度声明；更广复用与日程见 [Issue24](https://github.com/BucketSran/vaEVAS/issues/24) |

## 工作与证据身份

当前结果集中维护在[实验入口](../../experiments/parallel-gap-integration/README.md#当前证据)。
下表只做身份导航；开发检查方法数、原矩阵、Spectre 执行与性能测量分别计数。

| 检查点 | 固定执行身份与历史入口 |
| --- | --- |
| PR33 / IR16：已知事件截止点 | 运行时 `8618339`，审查头 `18063c9`，main 合并点 `b4921ca`；[检查与审查收据](../../experiments/parallel-gap-integration/results/event-horizon-checks.json) |
| PR32 / IR16：混合动态与共同生命周期 | 被测运行时 `1b99c33`，main 合并点 `431f335`；[三项开发](../../experiments/parallel-gap-integration/README.md#certified-mixed-dynamics)、[第一批对照](../../experiments/parallel-gap-integration/README.md#shared-lifecycle-review)、[共同闭包](../../experiments/parallel-gap-integration/README.md#lifecycle-closure-review)、[追加观察/依赖修复](../../experiments/parallel-gap-integration/README.md#lifecycle-observation-review-fixes) |
| PR31 / IR16：非线性积分与联合事件 | 最终审查运行时 `d06e7f3`，main 合并点 `09b4222`；[首轮及根盒修复](../../experiments/parallel-gap-integration/README.md#dynamic-closure) |
| PR30 / IR16：连续动态与旧 IR 重编译 | 首轮运行时 `ba5ab46`，初始化修复 `071a813`，main 合并点 `bedf20f`；[执行与初始化修复](../../experiments/parallel-gap-integration/README.md#continuous-dynamics) |
| PR29 / IR15：原矩阵补齐及精度链 | 精度链运行时 `d451605`；[历史执行](../../experiments/parallel-gap-integration/README.md#ir15-precision-chain)，更早功能/计时见[无损历史资产](../../experiments/parallel-gap-integration/README.md#历史与资产) |
| PR26 / IR11 及旧 EVAS 0.8.7 | [PR26 原对照](../../experiments/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)、[旧四后端矩阵](../../experiments/dvs2-four-backend-validation/results/MATRIX.md)；历史失败不改写为新版本成绩 |

原矩阵已经参与开发诊断，正式 DVS 资格仍 I。完整 raw 和内核为仅本地保留；公开整理收据
不等于公开全部原始资产。PR32 的早期根盒等号失败、复位采样误拒绝、有限时间爆炸探针超时
和 Spectre 不一致都保留在对应历史段落中；后续修复不删除这些结果。
合并后的分支可按保留规则清理，固定提交/PR 仍能追溯迭代；原始材料须另行归档。

## 后续工作

原 31 条件在这个有限范围内已经补齐；下面是更广语言/组合能力和证据缺口。
它们不阻塞本受限检查点交付，也不应被读作完整电压域 VA 已完成。

| 方向 | 下一步需先固定的设计与独立验收 |
| --- | --- |
| 联合动态求解 | 已补 index-one 多项式 DAE、积分/proper 滤波混合、根盒采样和稳定条件；剩余 DAE 的事件/复位/其他算子组合、首次启动的非线性滤波 DC、非线性直接通路、时间盒内部代表时刻及动态 guard 日程的分段传播/重新定位 |
| 事件扩展 | 已补状态独立多项式/连续算子 guard；剩余事件后轨迹重定位、切线、隐式非线性电压 guard、动态 timer/混合 OR |
| 语言和算子 | 已补受限内部/算子输入 ddt 和 1–8 阶滤波；剩余跳变/高指标导数、通用函数/过程控制/数组及更广初值/参数语义 |
| 精度/资格 | 通用状态预算、前端折叠误差、一般连续时间误差、独立观察资格与未见确认集，保留拒绝及错误对照 |
| 性能 | 按 Issue9/24 在同范围/误差目标下测准备、首次、重复、瞬态与内存；不要拿旧局部计时代替最新整体速度 |

每项先固定数学契约和接受/拒绝边界，再做独立答案、不变性和失败后完整性检查。
实际范围、依赖、负责人和预算写在对应 Issue/PR；合并或发布只根据真实动作更新状态。

按[共同生命周期契约](../validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract)分批审查。
第一批交付独立数学、输入冻结及初始化/续算/事件采样/复位对照；
第二批已补受限共同复位观察闭包、生产事件提交/回退及 te=tau 的显式时间绑定，集成记录见 PR32。
之后才补非线性初始化、DAE 与事件/复位组合、改变轨迹后的根重定位；晚触发策略与更广历史认证另行验收。
资格确认与性能测量分别推进，原 31 条开发回归继续保留。
