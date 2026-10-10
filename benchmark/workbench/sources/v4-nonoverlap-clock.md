# v4 两相非重叠时钟来源

服务[case-0017](../cases/spec-modeling/pll/case-0017-nonoverlap-clock/README.md)，同源组`v4-family-375`。上游来源为`Arcadia-1/behavioral-veriloga-eval`的`7b5616dc52195ec275ec6d21c71d7763613702cd`；实读本仓库`c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9`保存的r53字节。

2026-10-11读取发生器参考与原score_tb网表，承接[变体源码分析](../migration/v4-variant-expansion.md)。本次没有重审全部旧三形态或负例。固定版本、文件链接和哈希见下表。

| 实读材料 | SHA-256 |
| --- | --- |
| [发生器参考VA](../../reference/v4/release/benchmarkv4-r53/tasks/375-nonoverlap-clock-generator/evaluator/solution/nonoverlap_clock_generator.va) | `987fce5a593b448297f6b09059ce2ca44305a93df9418d86507dfa76b3353cad` |
| [原固定激励](../../reference/v4/release/benchmarkv4-r53/tasks/375-nonoverlap-clock-generator/evaluator/score_tb.scs) | `231763dd22d0485942a8d9cfdedf00e5328cc96b5819feaffdf5f155d98277d4` |

旧接口含输入时钟、复位、使能、两相输出、等待标志与valid。每个输入边沿覆盖待执行相位，并重装tick计数。复位或禁用使输出立即门控为低，内部挂起状态在后续输入边沿或tick才清除；短暂控制脉冲可能只门控输出而未被状态更新采到。新规格需明确是否保留这一行为。

死区受输入沿与全局tick相位影响。`deadtime_metric`仅表示正在等待，不是数值时间；`tr`未用于输出贡献。代码存在不证明事件重合规则、当前仿真器兼容性或checker正确。

资料沿用[原始资料约定](../../reference/README.md#使用约定)，目前限内部研究，外发资格未确认。本轮只建立引用，不复制为正式任务。未编译、仿真或实际校准。
