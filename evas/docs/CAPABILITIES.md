# EVAS 能力与缺口总表

核对日期：2026-09-29。本次 PR12 合入后的运行时基线为 EVAS 0.5.3 / IR v5，
实现提交 `ba3c06390cfaca6c34653fcc2f978d7c793a0958`。实际使用还须核对自己的 checkout。
PR 可能继续推进，本表结论只对应列出的固定检查点，不能作为最新 PR head 的验证结果。
具体契约、实现说明和结果各自维护一份。后续改变状态时同时更新日期与身份。

## 状态约定

- **实现**：未实现 / 分支限定实现 / main 限定支持。未支持的合法 VA 写法不等于语言非法。
- **证据**：独立数学样例、本地开发回归、有限后端对照、已知差异、待补证据可同时存在；不是单一通过分数。
- **交付**：待 review / 已 review / 已合并 / 已发布分别记录；包版本号不能代替发布 tag 和 commit。
- ID 稳定标识能力，与 PR、条件编号和测试数量不同。一个条件可关联多个能力，不能因此重复扩大分母。
  本表的建议后续工作不自动授权新实验、实现、发布或合并。

## 能力矩阵

| ID / 能力 | main 范围 | 分支与交付状态 | 证据状态 | 剩余缺口与说明入口 |
| --- | --- | --- | --- | --- |
| LANG：语法、绑定、IR | 标量、参数、限定表达式及版本化 IR | 已合并；算子分支扩展 IR | 前端与畸形 IR 回归 | 条件/数组/循环及更多函数按实际模型需求扩展；[当前语法](../README.md#实现范围) |
| LIN：线性电压关系 | 稠密求解、参考节点、贡献累加、分解复用 | 已合并 | 构造解及原静态回放 | 病态系统与更广规模边界；[数值说明](NUMERICS.md) |
| NONLINEAR：多项式反馈 | 阻尼 Newton、解析 Jacobian、三项验收 | 已合并 PR6 | 独立高精度参考、缩放/容差及失败回归 | 初猜、延续法、多解及更广函数；[数值说明](NUMERICS.md) |
| SPARSE：稀疏线性代数 | 尚未合入 | PR8 保留实现，待整合/review | 旧基线上的正确性与合成性能检查 | 与当前 main 整合；排序/填充/复用由 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) 跟踪 |
| CROSS：阈值事件 | 连续 PWL/仿射、状态独立 guard；触零/平台/stop 到达 | 已合并 PR7/10 | 数学/开发回归、限定 Spectre 对照 | 非线性轨迹和反馈后的重新定位；[事件说明](EVENTS.md) |
| TIMER：固定定时事件 | 固定 start/period/time_tol/enable，有限日程 | PR12 合入：0.5.3 / IR v5 | 本地回归；普通/同刻有限对照及顺序赋值回放 | 动态参数、enable 与复合事件；同刻问题关联 EVENT-ORDER |
| EVENT-ORDER：同刻与原子提交 | 仿射状态/电压联立、前向认证、integer/real 顺序赋值、整批提交/回退 | PR12 合入；PR13 算子历史待同步 | 旧同刻差异在 0.5.1 修复；0.5.3 新回归与限定回放 | Spectre 21.1 重复赋值异常由 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16) 跟踪；更广同刻语义、反馈 guard 仍缺；[说明](EVENTS.md#timer-与同刻兼容性) |
| TRANSITION：延迟与有限边沿 | 尚未合入 | PR13 待 review，依赖 PR12 | 独立边沿/历史样例及本地回归 | 专属 Spectre 对照、公共同刻语义、动态参数/更广输入；[算子说明](OPERATORS.md#transition) |
| ABSDELAY：历史查询 | 尚未合入 | PR14 待 review，依赖 PR13 | 独立 PWL/大时间减法样例及本地回归 | Spectre 对照、内部节点/可变延迟/跳变；[算子说明](OPERATORS.md#absdelay) |
| SLEW：限速与追赶 | 尚未合入 | PR15 待 review，依赖 PR13 | 独立交点/反向/尺度样例及本地回归 | Spectre 对照、内部节点/动态参数/组合；[算子说明](OPERATORS.md#slew) |
| COMPOSE：实例与组合 | 静态反馈、限定采样状态与实例隔离 | 四能力有独立本地联合检查点，非 main | 8 组联合开发用例通过；非跨后端资格 | 算子前向组合、算子驱动 cross、状态反馈同刻迭代；不能由单项正确推出组合正确 |
| DYNAMICS：积分、导数、滤波、相位 | 新内核尚未实现相关通用算子 | 待建立实现契约 | 原 V6 是需求/旧后端证据 | 初值、复位、离散化、积分误差与长期相位；[V6 要求](../validation/README.md#七组行为要求) |
| QUALIFICATION：独立验收 | 有开发条件与检查器 | 持续补证据；无完整资格结论 | 原 31 条件及部分新内核小规模对照 | 新内核完整矩阵、观察误差界、未见确认集；[协议](../validation/METHOD_QUALIFICATION.md) |
| PERFORMANCE：效率证据 | 有库内局部基准 | PR8 有另外的合成检查点 | 不同提交的局部测量 | 同版本端到端/瞬态/跨后端比较；首次、重复、内存分开报告 |

电流未知量、器件级负载与完整 SPICE 分析不在当前电压域任务的默认范围内；不将它们自动列为必做待办。

## 工作与证据身份

| 入口 | 固定检查点与依赖 | 已有证据及边界 |
| --- | --- | --- |
| [PR8](https://github.com/BucketSran/vaEVAS/pull/8) | [4d20fbc](https://github.com/BucketSran/vaEVAS/commit/4d20fbcf1eca0b9e4883d8a59ccdb80ee4f8c331)，较早静态基线 | 稀疏 LU 已接入该分支；当前 main 仍为稠密。整合后需受影响回归 |
| [PR11](https://github.com/BucketSran/vaEVAS/pull/11) | 协作规则、手册与数学契约来源；原数学检查点 [520ca96](https://github.com/BucketSran/vaEVAS/commit/520ca960229dace283fd7c5cc283b7e0f86f0e06) | 13 组 Fraction 数学核对覆盖四算子；不是 13 个正式条件或后端执行 |
| [PR12](https://github.com/BucketSran/vaEVAS/pull/12) | 0.5.3 修复及当前源码/构建身份见[收据](../../experiments/dvs2-spectre-validation/results/timer-0.5.3.json)；同步 main 文档基线 | 132 Python / 17 Rust；12 配置新 EVAS 回放符合独立候选，复用 Spectre 的 4 个重复写配置保留差异；[历史和本轮说明](../../experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053) |
| [PR13](https://github.com/BucketSran/vaEVAS/pull/13) | [bb01e88](https://github.com/BucketSran/vaEVAS/commit/bb01e88225efb8884cd009ae32ab4e77a6b50d0c)，基于 timer 实现 | 129 Python / 17 Rust 是整分支方法数；新增 15 / 4；未执行专属 Spectre 对照 |
| [PR14](https://github.com/BucketSran/vaEVAS/pull/14) | [a4b4fbe](https://github.com/BucketSran/vaEVAS/commit/a4b4fbe628c798c616ccdbcd82e04f36fcd41bb0)，基于 PR13 | 144 Python / 22 Rust；新增 15 / 5；未执行专属 Spectre 对照 |
| [PR15](https://github.com/BucketSran/vaEVAS/pull/15) | [5f0aba6](https://github.com/BucketSran/vaEVAS/commit/5f0aba6a4312fbcddd261cc3e9de7f63736bef9a)，基于 PR13 | 140 Python / 22 Rust；新增 11 / 5；未执行专属 Spectre 对照 |

四能力联合检查固定在本地提交 `31193c624cfa338316143f446b0ef3c3e1dcd2f5`，
155 Python / 27 Rust、8/8 配置通过，316 个观察时刻、96 个事件；该提交/原始收据尚未公开归档。
联合收据 SHA256 为 `4661c0a64d6a73552855ac0b06f616ce4932fa63ed639e53d29af77ee8ba366f`。
这些数字不能与各分支方法数相加，也不改变原 31 条件分母。仅本地哈希不构成公开数据可用性。

## 后续工作顺序

PR12 的限定 EVENT-ORDER 实现已完成本轮 review；Spectre 版本异常由 Issue16 独立跟踪。
先将 PR13 与该事件基线同步并验证，再逐项 review PR13–15，补上各自缺失的对照；SPARSE 的当前基线整合与后续性能优化分开处理。DYNAMICS 等新能力
先从独立义务、数学答案和边界开始。具体负责人、排期和执行预算放在任务/Issue/PR，避免复制到本表。

每次状态更新需链接相应提交/证据；能力 ID 不随 PR 结束而改变。合并时标记 main 支持的限定范围，
发布时记录实际 tag；未发布不能只凭包内版本号标为发布完成。
