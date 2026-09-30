# EVAS 能力与缺口总表

核对日期：2026-09-30。本基线 EVAS 0.9.0 / IR v9 在 0.7.1 的受限 idt 与稠密/稀疏求解之上，
通过 PR23 交付受限事件体 if/else、cross OR 与输入/状态误差认证。旧 IR v1–v8 须从原始 VA 重新编译，未发布版本 tag。
历史 PR14 被测实现为 `3638024`，PR15 为 `e01fb5b`；这两项的合并收尾只同步文档与实验资产，
运行时代码、测试和独立验证定义保持被测身份。PR14 合并提交为 `0c36d3b`，PR15 的最终合并身份见其 PR。
实现、证据、交付分别记录；包版本号不能代替提交身份，也不代表已创建发布 tag。

## 状态约定

- **实现**：未实现 / 分支限定实现 / main 限定支持。未支持的合法 VA 写法不等于语言非法。
- **证据**：独立数学样例、本地开发回归、有限后端对照、已知差异、待补证据可同时存在；不是单一通过分数。
- **交付**：待 review / 已 review / 已合并 / 已发布分别记录；包版本号不能代替发布 tag 和 commit。
- ID 稳定标识能力，与 PR、条件编号和测试数量不同。一个条件可关联多个能力，不能因此重复扩大分母。
  本表的建议后续工作不自动授权新实验、实现、发布或合并。

## 能力矩阵

| ID / 能力 | main 范围 | 分支与交付状态 | 证据状态 | 剩余缺口与说明入口 |
| --- | --- | --- | --- | --- |
| LANG：语法、绑定、IR | 标量、参数、限定表达式、受限事件 if/else 与 cross OR、版本化 IR | PR23 审阅交付：0.9.0 / IR v9；旧 IR 须重编译 | 独立条件与畸形 IR 回归见[事件说明](EVENTS.md#event-conditions) | 普通 analog 条件/数组/循环及更多函数按实际模型需求扩展；[当前语法](../README.md#实现范围) |
| LIN：线性电压关系 | 稠密/稀疏求解、参考节点、贡献累加、分解复用 | PR8 集成分流，交付见该 PR | 构造解及 0.7.1 新静态回放 | 病态系统与更广规模边界；[数值说明](NUMERICS.md) |
| NONLINEAR：多项式反馈 | 阻尼 Newton、解析 Jacobian、三项验收 | 已合并 PR6 | 独立高精度参考、缩放/容差及失败回归 | 初猜、延续法、多解及更广函数；[数值说明](NUMERICS.md) |
| SPARSE：稀疏线性代数 | n≥32、nnz≤0.1mn 时采用稀疏 LU；适用于静态、Newton 及限定事件/历史算子的电压解 | 0.7.1 / IR v7；[PR8](https://github.com/BucketSran/vaEVAS/pull/8) 交付，未发布 tag | 当前整合回归、构造解/原残差、稀疏事件/算子和 idt 检查；性能数据限旧检查点 | 历史区间认证仍稠密；排序/填充/复用由 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) 跟踪；[数值说明](NUMERICS.md#稀疏分支与性能边界) |
| CROSS：阈值事件 | 连续 PWL/仿射、状态独立 guard；触零/平台/stop 到达及 cross OR | 已合并 PR7/10；PR23 审阅交付 OR、逐叶证书与同块去重 | 数学/开发回归、历史限定 Spectre 对照；0.9.0 原 31 矩阵见[收据](../../experiments/pr14-pr15-validation/RESULTS.md#event-conditions-090) | 非线性轨迹和反馈后的重新定位；[事件说明](EVENTS.md) |
| TIMER：固定定时事件 | 固定 start/period/time_tol/enable，有限日程 | PR12 合入：0.5.3 / IR v5 | 本地回归；普通/同刻有限对照及顺序赋值回放 | 动态参数、enable 与复合事件；同刻问题关联 EVENT-ORDER |
| EVENT-ORDER：同刻与原子提交 | 仿射状态/电压联立、前向认证、integer/real 顺序赋值、认证条件路径、整批提交/回退 | PR12/13 已合入；PR14 延续历史误差传播；PR23 审阅交付路径缓存、输入与旧状态包围及 OR 同块去重 | PR12/13 历史证据保留；新增条件失败/弃步/修正未来输入重试 | Spectre 21.1 重复赋值异常见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16)；多事件块写同一状态、反馈 guard 仍缺；[说明](EVENTS.md#timer-与同刻兼容性) |
| TRANSITION：延迟与有限边沿 | 固定延迟、显式正边沿、状态仿射输入 | PR13 已合入；0.6.1 / IR v6 | 6 项 Fraction 精度回归；共同观察网格下 EVAS/Spectre 各 16/16 | 完整观察资格、区间保守性、更广同刻语义/动态参数/输入；[算子说明](OPERATORS.md#transition) |
| ABSDELAY：历史查询 | 固定非负延迟、直接连续 PWL 的仿射输入，历史误差传播 | PR14 已合入；被测 `3638024`，收尾不改运行时代码 | 独立 PWL/大时间减法、同刻/跨事件回归；[专项](../../experiments/pr14-pr15-validation/RESULTS.md) EVAS/Spectre 各 12/12 | 内部节点/状态输入、可变延迟、跳变、嵌套及反馈；[算子说明](OPERATORS.md#absdelay) |
| SLEW：限速与追赶 | 固定正/负限速、直接连续 PWL 的仿射输入 | 随 PR15 交付；被测 `e01fb5b`，依赖 PR14 已合入 | 局部交点/历史误差回归；[专项](../../experiments/pr14-pr15-validation/RESULTS.md) EVAS 16/16、Spectre 10/16，步长诊断保留 | 内部节点/动态参数/组合；[算子说明](OPERATORS.md#slew) |
| COMPOSE：实例与组合 | 静态反馈、限定事件采样与实例隔离 | 随 PR15 集成组合回归；另补独立语义不变性回归 | PR15 8 配置独立 Fraction 检查通过；新增 3 项贡献排列、重命名与观测不变性回归见[覆盖映射](../validation/DYNAMICS_CONTRACTS.md)；旧联合检查点保留 | 算子前向组合、算子驱动 cross、状态反馈同刻迭代；单项正确不能推出组合正确 |
| DYNAMICS：积分、导数、滤波、相位 | main：显式常量初值、直接连续 PWL 仿射输入的 idt；分支：显式 modulus/offset 的 idtmod 与受限 sin 相位输出 | main 为 0.7.0 / IR v7；PR19 交付 idt。phase 分支待 review，临时 IR v13，未发布 tag | idt 证据见[独立契约与恢复检查](../validation/DYNAMICS_CONTRACTS.md)与[数学实现](OPERATORS.md#idt)；phase 分支 `test_phase.py` 与冻结 D2 两条件两档本地 checker 通过，见[算子说明](OPERATORS.md#idtmod-与-sin) | idt 复位、反馈、嵌套、积分驱动 cross、连续时间资格及完整调度器失败恢复仍缺；phase 分支不支持省略 modulus、动态参数、operator/state/内部节点复杂组合 |
| QUALIFICATION：独立验收 | 开发条件与检查器，无完整资格结论 | 0.9.0 原 31 条件瞬态矩阵两档执行；PR20 交付独立 checker 校准 | [0.9.0 收据](../../experiments/pr14-pr15-validation/RESULTS.md#event-conditions-090)：EVAS 两档各 21/31，其余 10 明确拒绝；历史与其他后端失败保留；[S1 审阅补充](../validation/NEXT_CASE_CARDS.md#s1-review)及 E1/E2/C1 校准 | 观察误差界、未见确认集；S1 新顺序条件未执行后端，不增加原矩阵成绩；正式资格仍 I；[协议](../validation/METHOD_QUALIFICATION.md) |
| PERFORMANCE：效率证据 | 有库内局部基准和稠密/稀疏分流 | PR8 合成检查点保留，0.7.1 未重新计时 | 不同旧提交的局部测量；18.5% 退化未稳定复现，见[边界](NUMERICS.md#稀疏分支与性能边界) | 同版本端到端/瞬态/跨后端比较；首次、重复、内存分开报告 |

电流未知量、器件级负载与完整 SPICE 分析不在当前电压域任务的默认范围内；不将它们自动列为必做待办。

## 工作与证据身份

| 入口 | 固定检查点与依赖 | 已有证据及边界 |
| --- | --- | --- |
| [PR23](https://github.com/BucketSran/vaEVAS/pull/23) | 0.9.0 / IR v9，生产源码 `14d0b24`；审阅通过，交付 main；合并前同步 PR20 main `ee50b5d`，收尾只改测试/文档，生产源码身份不变 | 260 Python / 56 Rust 本轮审阅重跑通过；原 31 条件两档各 21 有限观测达标、10 明确拒绝，正式资格 I；修正 OR 专项 EVAS 16/16、Spectre 15/16；近邻根粗档差异保留，两个单参数诊断双方均 2/2；[收据](../../experiments/pr14-pr15-validation/RESULTS.md#event-conditions-090)，矩阵与 Spectre 证据复用，raw local-only |
| [PR20](https://github.com/BucketSran/vaEVAS/pull/20) | 独立 S1 与 E1/E2/C1 checker 校准；已合并 `ee50b5d`，未修改 EVAS 实现或原 31 条件身份 | 66 项 checker 校准本轮审阅重跑通过；新增贡献顺序条件尚未执行后端，不能增加矩阵通过数；[S1 审阅卡](../validation/NEXT_CASE_CARDS.md#s1-review) |
| [PR17](https://github.com/BucketSran/vaEVAS/pull/17) | 2026-09-29 旧 EVAS `v0.8.7` / `6cb6fa7` 审查档案；原报告提交 `0b7576a`，审阅通过并交付历史资产，运行时不变 | 47 条诊断观测（含错误输出与拒绝），不是通过数；本轮核对 11 个资产哈希、16 次完整模型请求身份与 11 组解析误差；[报告与证据边界](../../experiments/legacy-evas-migration/README.md)。受限 idt 已另由 PR19 交付，其他候选以当前能力表为准；完整日志和二进制 local-only |
| [0.8.0 历史检查点](../validation/EVENT_CONDITIONS_CONTRACT.md#conditions-080-checkpoint) | 事件条件提交 `a1b0163` / IR v8，基于 main `a0c8043`；现作为 PR23 的前一实现切片保留 | 250 Python / 55 Rust、14 条件数学 / 9 动态数学；当时静态 22 配置、484,022 点通过。此切片当时 OR 未接入，也未新跑 Spectre、原瞬态矩阵或计时；不能替代 0.9.0 证据 |
| [PR8](https://github.com/BucketSran/vaEVAS/pull/8) | 0.7.1 / IR v7，被测 `f44b730`，基于 PR19 main `2e3196f`；算法来源 `4d20fbc`，最终收尾只改文档 | 230 Python / 52 Rust / 9 纯数学；静态 22 配置、484,022 点通过，20 条明确拒绝；稀疏 idt 1,240 个电压检查；未新跑 Spectre、瞬态原矩阵或计时，原始日志仅本地保留 |
| [PR11](https://github.com/BucketSran/vaEVAS/pull/11) | 协作规则、手册与数学契约来源；原数学检查点 [520ca96](https://github.com/BucketSran/vaEVAS/commit/520ca960229dace283fd7c5cc283b7e0f86f0e06) | 13 组 Fraction 数学核对覆盖四算子；不是 13 个正式条件或后端执行 |
| [PR12](https://github.com/BucketSran/vaEVAS/pull/12) | 0.5.3 修复及当前源码/构建身份见[收据](../../experiments/dvs2-spectre-validation/results/timer-0.5.3.json)；同步 main 文档基线 | 132 Python / 17 Rust；12 配置新 EVAS 回放符合独立候选，复用 Spectre 的 4 个重复写配置保留差异；[历史和本轮说明](../../experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053) |
| [PR13](https://github.com/BucketSran/vaEVAS/pull/13) | 0.6.1 / IR v6，实现 `9850450`；基于 main `e6f04c4`，源码/内核身份见[收据](../../experiments/dvs2-spectre-validation/results/transition-0.6.1.json) | 155 Python / 23 Rust / 48 checker；共同观察网格下两后端各 16/16；[说明及旧证据](../../experiments/dvs2-spectre-validation/README.md#pr13-transition-061) |
| [PR14](https://github.com/BucketSran/vaEVAS/pull/14) | 被测 `3638024`；收尾同步 main 文档，运行时代码不变 | 176 Python / 28 Rust；[专项证据](../../experiments/pr14-pr15-validation/RESULTS.md)中独立 PR14 全栈与 Spectre 各 12/12；原始材料未公开归档 |
| [PR15](https://github.com/BucketSran/vaEVAS/pull/15) | 被测 `e01fb5b`，基于 PR14 `3638024`；共享验证发布于 `ec3acaa` | 195 Python / 33 Rust，8 组合配置；[专项和原矩阵](../../experiments/pr14-pr15-validation/RESULTS.md)记录成功、明确拒绝与 Spectre 步长差异 |
| [PR19](https://github.com/BucketSran/vaEVAS/pull/19) | 0.7.0 / IR v7，被测 `d33b1da`，基于 PR18 `1dc0bed`；最终登记补交只改本表 | 218 Python / 42 Rust、9 纯数学；649 积分区间核对；非零历史失败/弃步/重试。未新执行 Spectre 或原矩阵，范围见[契约](../validation/DYNAMICS_CONTRACTS.md) |

四能力联合检查固定在本地提交 `31193c624cfa338316143f446b0ef3c3e1dcd2f5`，
155 Python / 27 Rust、8/8 配置通过，316 个观察时刻、96 个事件；该提交/原始收据尚未公开归档。
联合收据 SHA256 为 `4661c0a64d6a73552855ac0b06f616ce4932fa63ed639e53d29af77ee8ba366f`。
这些数字不能与各分支方法数相加，也不改变原 31 条件分母。仅本地哈希不构成公开数据可用性。

## 后续工作顺序

后续工作从当前 0.9.0 / IR v9 main 开始；每项使用一个可独立 review 的 PR，实际依赖才堆叠。
受限事件体条件与 cross OR 已完成原 8 条件两档有限观测验证；下表仅保留剩余范围。
条件数是受影响范围，不是新增达标承诺；
完整拒绝诊断见[原矩阵](../../experiments/pr14-pr15-validation/RESULTS.md)。

| 优先顺序 / 能力 | 下一项范围与数学依据 | 对应原条件 | 验收重点 |
| --- | --- | --- | --- |
| 1 / LANG | 普通 analog 局部顺序赋值、比较及 if/else；先限定输入驱动的分段仿射关系 | v1-main（1） | 独立限幅公式、等号边界、阈值定位、语句顺序；暂不扩展隐式分支反馈 |
| 2 / EVENT-ORDER | 多事件块写同一状态；先支持可证明无冲突的更新，同刻冲突另立契约 | v3-main（1），亦为复位积分依赖 | 上/下阈值迟滞、保持区间、同时写冲突及失败回退；不能只删除当前拒绝检查 |
| 3 / NONLINEAR | 无动态状态和事件耦合的非线性瞬态入口：在请求时刻解 F(v,u(t))=0，复用 Newton | v7-nonlinear 两条（2） | 独立单调三次方程根、前一点初猜、容差/失败；不声称已支持非线性 cross |
| 4 / DYNAMICS | 在现有显式初值/PWL idt 上补复位；重新定义复位前后历史及原子提交 | d1-free/reset（2） | 非零初值、复位保持/释放、区间积分误差、撤销重试；依赖多事件状态更新 |
| 5 / DYNAMICS + LANG | 标准常量数组与一阶 laplace_nd；先实现 τ y′+y=u 的独立状态演化，再测试采样级联 | v6-standard、c2-main（2） | 指数/斜坡解析解、初值、长时间稳定性及级联；不能只通过数组解析就记支持 |
| 6 / DYNAMICS + LANG | constants 宏、idtmod 和 sin；累计相位与取模相位分开保存 | d2-constant/chirp（2） | 相位积分、环绕边界、长期累计误差、频率变化；依赖 idt |

SPARSE 的共享矩阵与瞬态调用路径已在 PR8 整合验证；后续按 Issue9 优化排序、填充和分解复用。
固定同一支持范围与误差目标，分开测构建/编译、首次求解、
重复求解、瞬态与内存；没有相应测量前不报速度倍数。性能路线不改变上述功能覆盖分母。

每项先固定数学契约、独立答案和接受/拒绝边界，再实现并跑专项与受影响原条件。
积累到功能检查点后重跑完整矩阵；扩大覆盖后另冻结未参与开发的确认集。
具体负责人、执行预算和新任务范围放在后续任务/Issue/PR，不由本表自动授权。

每次状态更新需链接相应提交/证据；能力 ID 不随 PR 结束而改变。合并时标记 main 支持的限定范围，
发布时记录实际 tag；未发布不能只凭包内版本号标为发布完成。
