# 强制求解时刻

当前开发候选在 Python `transient` 和 JSON manifest 中增加 strobe 控制。
它与 `output_times` 分开：后者请求输出，前者要求计算在指定时刻落点。
`.scs` 导入器暂不接受这些选项；Spectre 的 `strobeoutput` 保存策略和别名也尚未实现。
这是一项有限控制能力，不代表已复制 Spectre 的内部积分或浮点运算顺序。

```python
result = transient(program, sources, [0, 1], stop=1, max_step=0.5,
                   strobetimes=[0.2, 0.7], kernel=kernel)
```

例中的常规输出仍只有 `[0, 1]`。`result['strobe_evidence']` 另存
强制点 `[0.2, 0.7]`、对应节点电压及计算来源。无需诊断开关也会返回。
manifest 将同名选项放在 `transient` 内。原有请求不新增强制点。

| 选项 | 约束与含义 |
| --- | --- |
| `strobetimes` | 严格递增、有限、位于 `[0,stop]` 的时间列表 |
| `strobeperiod` | 正周期，未提供则不开启周期表；当前拒绝显式零值 |
| `strobedelay` | 相对窗口起点的偏移，默认 0，必须小于周期 |
| `skipstart` / `skipstop` | 周期窗口，默认 0 / stop；须满足 `0 <= start <= end <= stop` |

周期表满足 `t_k = skipstart + strobedelay + k*strobeperiod <= skipstop`。
EVAS 对输入 binary64 值作精确有理数运算，再将每个时刻舍入一次。
这是 EVAS 明示的生成规则，Spectre 私有运算次序仍未知。
显式表与周期表取并集，最多 100,000 点；舍入后周期点重合时明确拒绝。
窗口和偏移只能与周期一起使用，显式时间表不受周期窗口裁剪。

无状态电路在强制点求解工作点。事件控制器将强制点纳入推进日程；
线性传播和非线性 Taylor/隐式历史在强制点分段。
源的 PWL 折点保持独立，强制点不会变成新的源插值定义。
这可能改变数值分段与误差包围，因此带 strobe 的请求须单独验证。
它不改变数学根处更新的事件契约，也不能保证另一后端选择相同事件相位。

当前遇到局部时间锚定的因果事件闭包，或强制点只能通过原子事件簇的
`certified_causal_frame` 查询取得时，返回 `unsupported_strobe`。
这类查询尚不能证明已在该点完成所请求的强制推进。
普通查询仍按原契约处理，不因本功能扩大拒绝范围。

`strobe_evidence` 使用版本 1，包含 `times`、`sample_origins` 和 `voltages_V`。
节点次序与常规结果一致。前端核对强制点完整性与来源，不能把缺失字段当成功。
当前来源为 `stateless_working_point`、`accepted_controller_frame` 或
`implicit_history_evaluation`；历史类来源的落点由积分分段规则及内核回归共同验证。
该字段不提供 Spectre 回调次序证明，也不扩大已有连续时间误差证据。
请求协议保持 IR18 的可选扩展；旧内核拒绝未知请求字段，新前端拒绝缺失回执。

验证入口为 [公共控制测试](../tests/test_strobe.py)、
[独立模型与冻结预算](../validation/strobe/README.md)。
原 C1、#79 和 VCO 的严格边界缺口继续保留，不因新增控制或提示转为通过。
