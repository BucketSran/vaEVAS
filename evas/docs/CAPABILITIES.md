# EVAS 能力与缺口总表

核对日期：2026-09-30。本基线 EVAS 0.7.0 / IR v7 在 PR12–15 的定时事件与历史算子之上增加受限 idt。
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
| LANG：语法、绑定、IR | 标量、参数、限定表达式及版本化 IR | 限定算子及显式初值 idt 使用 IR v7 | 前端与畸形 IR 回归 | 条件/数组/循环及更多函数按实际模型需求扩展；[当前语法](../README.md#实现范围) |
| LIN：线性电压关系 | 稠密求解、参考节点、贡献累加、分解复用 | 已合并 | 构造解及原静态回放 | 病态系统与更广规模边界；[数值说明](NUMERICS.md) |
| NONLINEAR：多项式反馈 | 阻尼 Newton、解析 Jacobian、三项验收 | 已合并 PR6 | 独立高精度参考、缩放/容差及失败回归 | 初猜、延续法、多解及更广函数；[数值说明](NUMERICS.md) |
| SPARSE：稀疏线性代数 | 尚未合入 | PR8 保留实现，待整合/review | 旧基线上的正确性与合成性能检查 | 与当前 main 整合；排序/填充/复用由 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) 跟踪 |
| CROSS：阈值事件 | 连续 PWL/仿射、状态独立 guard；触零/平台/stop 到达 | 已合并 PR7/10 | 数学/开发回归、限定 Spectre 对照 | 非线性轨迹和反馈后的重新定位；[事件说明](EVENTS.md) |
| TIMER：固定定时事件 | 固定 start/period/time_tol/enable，有限日程 | PR12 合入：0.5.3 / IR v5 | 本地回归；普通/同刻有限对照及顺序赋值回放 | 动态参数、enable 与复合事件；同刻问题关联 EVENT-ORDER |
| EVENT-ORDER：同刻与原子提交 | 仿射状态/电压联立、前向认证、integer/real 顺序赋值、整批提交/回退 | PR12/13 已合入；PR14 延续历史误差传播 | PR12 顺序赋值与 PR13 电压目标/算子值回归 | Spectre 21.1 重复赋值异常见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16)；多事件块写同一状态、反馈 guard 仍缺；[说明](EVENTS.md#timer-与同刻兼容性) |
| TRANSITION：延迟与有限边沿 | 固定延迟、显式正边沿、状态仿射输入 | PR13 已合入；0.6.1 / IR v6 | 6 项 Fraction 精度回归；共同观察网格下 EVAS/Spectre 各 16/16 | 完整观察资格、区间保守性、更广同刻语义/动态参数/输入；[算子说明](OPERATORS.md#transition) |
| ABSDELAY：历史查询 | 固定非负延迟、直接连续 PWL 的仿射输入，历史误差传播 | PR14 已合入；被测 `3638024`，收尾不改运行时代码 | 独立 PWL/大时间减法、同刻/跨事件回归；[专项](../../experiments/pr14-pr15-validation/RESULTS.md) EVAS/Spectre 各 12/12 | 内部节点/状态输入、可变延迟、跳变、嵌套及反馈；[算子说明](OPERATORS.md#absdelay) |
| SLEW：限速与追赶 | 固定正/负限速、直接连续 PWL 的仿射输入 | 随 PR15 交付；被测 `e01fb5b`，依赖 PR14 已合入 | 局部交点/历史误差回归；[专项](../../experiments/pr14-pr15-validation/RESULTS.md) EVAS 16/16、Spectre 10/16，步长诊断保留 | 内部节点/动态参数/组合；[算子说明](OPERATORS.md#slew) |
| COMPOSE：实例与组合 | 静态反馈、限定事件采样与实例隔离 | 随 PR15 集成组合回归；另补独立语义不变性回归 | PR15 8 配置独立 Fraction 检查通过；新增 3 项贡献排列、重命名与观测不变性回归见[覆盖映射](../validation/DYNAMICS_CONTRACTS.md)；旧联合检查点保留 | 算子前向组合、算子驱动 cross、状态反馈同刻迭代；单项正确不能推出组合正确 |
| DYNAMICS：积分、导数、滤波、相位 | 显式常量初值、直接连续 PWL 仿射输入的 idt；导数/滤波/相位未实现 | 0.7.0 / IR v7 受限实现；本次合并交付，未发布 tag | [独立契约与恢复检查](../validation/DYNAMICS_CONTRACTS.md)、有理数区间核对及实际 idt 回归；[数学与实现](OPERATORS.md#idt) | 复位、反馈、嵌套、积分驱动 cross、连续时间资格及完整调度器失败恢复；原 D1 仍拒绝 |
| QUALIFICATION：独立验收 | 开发条件与检查器，无完整资格结论 | 原 31 条件在 PR15 被测实现重跑；0.7.0 未重跑矩阵 | [248 单元新执行](../../experiments/pr14-pr15-validation/RESULTS.md)：EVAS 两档各 13/31，其余 18 拒绝；其他后端失败保留 | 观察误差界、未见确认集；[协议](../validation/METHOD_QUALIFICATION.md) |
| PERFORMANCE：效率证据 | 有库内局部基准 | PR8 有另外的合成检查点 | 不同提交的局部测量 | 同版本端到端/瞬态/跨后端比较；首次、重复、内存分开报告 |

电流未知量、器件级负载与完整 SPICE 分析不在当前电压域任务的默认范围内；不将它们自动列为必做待办。

## 工作与证据身份

| 入口 | 固定检查点与依赖 | 已有证据及边界 |
| --- | --- | --- |
| [PR8](https://github.com/BucketSran/vaEVAS/pull/8) | [4d20fbc](https://github.com/BucketSran/vaEVAS/commit/4d20fbcf1eca0b9e4883d8a59ccdb80ee4f8c331)，较早静态基线 | 稀疏 LU 已接入该分支；当前 main 仍为稠密。整合后需受影响回归 |
| [PR11](https://github.com/BucketSran/vaEVAS/pull/11) | 协作规则、手册与数学契约来源；原数学检查点 [520ca96](https://github.com/BucketSran/vaEVAS/commit/520ca960229dace283fd7c5cc283b7e0f86f0e06) | 13 组 Fraction 数学核对覆盖四算子；不是 13 个正式条件或后端执行 |
| [PR12](https://github.com/BucketSran/vaEVAS/pull/12) | 0.5.3 修复及当前源码/构建身份见[收据](../../experiments/dvs2-spectre-validation/results/timer-0.5.3.json)；同步 main 文档基线 | 132 Python / 17 Rust；12 配置新 EVAS 回放符合独立候选，复用 Spectre 的 4 个重复写配置保留差异；[历史和本轮说明](../../experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053) |
| [PR13](https://github.com/BucketSran/vaEVAS/pull/13) | 0.6.1 / IR v6，实现 `9850450`；基于 main `e6f04c4`，源码/内核身份见[收据](../../experiments/dvs2-spectre-validation/results/transition-0.6.1.json) | 155 Python / 23 Rust / 48 checker；共同观察网格下两后端各 16/16；[说明及旧证据](../../experiments/dvs2-spectre-validation/README.md#pr13-transition-061) |
| [PR14](https://github.com/BucketSran/vaEVAS/pull/14) | 被测 `3638024`；收尾同步 main 文档，运行时代码不变 | 176 Python / 28 Rust；[专项证据](../../experiments/pr14-pr15-validation/RESULTS.md)中独立 PR14 全栈与 Spectre 各 12/12；原始材料未公开归档 |
| [PR15](https://github.com/BucketSran/vaEVAS/pull/15) | 被测 `e01fb5b`，基于 PR14 `3638024`；共享验证发布于 `ec3acaa` | 195 Python / 33 Rust，8 组合配置；[专项和原矩阵](../../experiments/pr14-pr15-validation/RESULTS.md)记录成功、明确拒绝与 Spectre 步长差异 |

四能力联合检查固定在本地提交 `31193c624cfa338316143f446b0ef3c3e1dcd2f5`，
155 Python / 27 Rust、8/8 配置通过，316 个观察时刻、96 个事件；该提交/原始收据尚未公开归档。
联合收据 SHA256 为 `4661c0a64d6a73552855ac0b06f616ce4932fa63ed639e53d29af77ee8ba366f`。
这些数字不能与各分支方法数相加，也不改变原 31 条件分母。仅本地哈希不构成公开数据可用性。

## 后续工作顺序

后续工作从已合入 PR14/15 的 main 开始；每项使用一个可独立 review 的 PR，实际依赖才堆叠。
以下列出剩余范围；受限的无复位 idt 已有实现，其余按实际提交和证据判断。条件数是受影响范围，不是新增达标承诺；
完整拒绝诊断见[原矩阵](../../experiments/pr14-pr15-validation/RESULTS.md)。

| 优先顺序 / 能力 | 下一项范围与数学依据 | 对应原条件 | 验收重点 |
| --- | --- | --- | --- |
| 1 / LANG | 普通 analog 局部顺序赋值、比较及 if/else；先限定输入驱动的分段仿射关系 | v1-main（1） | 独立限幅公式、等号边界、阈值定位、语句顺序；暂不扩展隐式分支反馈 |
| 2 / LANG + EVENT-ORDER | 事件体条件赋值、cross 的 or 组合；同刻触发集合去重与明确的复位优先分支 | v4 两条、e2 三条、c1 三条（8） | 时钟/复位单独与同刻、初始高电平、实例隔离；共同事件时间定义和状态提交 |
| 3 / EVENT-ORDER | 多事件块写同一状态；先支持可证明无冲突的更新，同刻冲突另立契约 | v3-main（1），亦为复位积分依赖 | 上/下阈值迟滞、保持区间、同时写冲突及失败回退；不能只删除当前拒绝检查 |
| 4 / NONLINEAR | 无动态状态和事件耦合的非线性瞬态入口：在请求时刻解 F(v,u(t))=0，复用 Newton | v7-nonlinear 两条（2） | 独立单调三次方程根、前一点初猜、容差/失败；不声称已支持非线性 cross |
| 5 / DYNAMICS | 在现有显式初值/PWL idt 上补复位；重新定义复位前后历史及原子提交 | d1-free/reset（2） | 非零初值、复位保持/释放、区间积分误差、撤销重试；依赖多事件状态更新 |
| 6 / DYNAMICS + LANG | 标准常量数组与一阶 laplace_nd；先实现 τ y′+y=u 的独立状态演化，再测试采样级联 | v6-standard、c2-main（2） | 指数/斜坡解析解、初值、长时间稳定性及级联；不能只通过数组解析就记支持 |
| 7 / DYNAMICS + LANG | constants 宏、idtmod 和 sin；累计相位与取模相位分开保存 | d2-constant/chirp（2） | 相位积分、环绕边界、长期累计误差、频率变化；依赖 idt |

SPARSE 是独立性能路线：先将 PR8 的稀疏 LU 同步当前 main，验证共享矩阵与瞬态调用路径，
再按 Issue9 优化排序、填充和分解复用。固定同一支持范围与误差目标，分开测构建/编译、首次求解、
重复求解、瞬态与内存；没有相应测量前不报速度倍数。性能路线不改变上述功能覆盖分母。

每项先固定数学契约、独立答案和接受/拒绝边界，再实现并跑专项与受影响原条件。
积累到功能检查点后重跑完整矩阵；扩大覆盖后另冻结未参与开发的确认集。
具体负责人、执行预算和新任务范围放在后续任务/Issue/PR，不由本表自动授权。

每次状态更新需链接相应提交/证据；能力 ID 不随 PR 结束而改变。合并时标记 main 支持的限定范围，
发布时记录实际 tag；未发布不能只凭包内版本号标为发布完成。
