# v4 滞回比较器表征来源

服务于 [case-0016](../cases/testing-characterization/comparators/case-0016-hysteresis-characterizer/README.md)，同源组为 `v4-family-111`。原始资料来自 `Arcadia-1/behavioral-veriloga-eval` 的 `7b5616dc52195ec275ec6d21c71d7763613702cd`；本轮读取 vaEVAS `c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9` 保存的 r53 原字节。

## 实读材料与身份

2026-10-10，读取111题面、测量参考、支撑比较器、611激励及六个测量负例，并参考 GLM 首轮静态意见。来源链可追到旧 v3-124，尚未确认更早外部电路来源。

| 材料 | SHA-256 |
| --- | --- |
| [111公开规格](../../reference/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/public/instruction.md) | `8afe53096785b9907043de6711ec812816b82314e07613ef630aab9d8fa6a5b4` |
| [测量参考](../../reference/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/evaluator/solution/hysteresis_trip_characterizer.va) | `998ff6326390c213cd39e814a1c30020781e99cc3d9dcb46a62010d3e329ffe8` |
| [支撑比较器](../../reference/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/evaluator/solution/support/support_hysteretic_comparator.va) | `9277616656260fc4dd4a732636fa3f8d9271405521b97f824624fa38fba7633a` |
| [611固定激励](../../reference/v4/release/benchmarkv4-r53/tasks/611-hysteresis-trip-characterizer-testbench/evaluator/reference_tb.scs) | `f8846901ec90aa294f58928427c22dd8d3c774987d8922b5c44865416a9507e2` |

111旧形态叫 DUT，但交付的本来就是 VA 测量模块。611旧形态叫 Testbench，交付的是 `.scs` 激励网表。新题按实际工程动作归入电路测试与表征，不为旧三形态各建一道题。

## 复核边界

GLM 报告的“未捕获时输出为绝对0V、valid低电平不参考VSS”是误读。参考贡献写作 `V(output, vss) <+ ...`，零值对应输出等于VSS。应补清公开规格，但不能据此宣称代码存在局部地错误。原 GLM 报告保留，复核结论单独记录。

GLM 以 `td + tr/2` 估算输出中点延迟；本轮不把135ps当作已验证的后端行为。正式 checker 依据实际输出中点事件，不能照抄这个估值作真值。

旧负例目录与属性标签有错配，需按[实际源码](../../reference/v4/release/benchmarkv4-r53/tasks/611-hysteresis-trip-characterizer-testbench/evaluator/mutation_bundles/)重建校准矩阵。第六个提前置valid负例存在于目录但未列入原五项 catalog。旧私有 checker 未取得；旧认证不能证明新验收有效。

遵循[原始资料使用约定](../../reference/README.md#使用约定)，只引用内部研究资产，未复制为新题源码，外发资格仍未确认。本轮只有源码分析和设计记录，未编译、仿真或校准。
