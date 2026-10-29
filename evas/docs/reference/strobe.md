# 强制求解时刻

当前实现通过 Python `transient`、JSON manifest 和受限 `.scs` 入口提供 strobe 控制。
它与 `output_times` 分开：后者请求输出，前者要求计算在指定时刻落点。
`.scs` 的 `tran` 接受下表五项控制，使用相同展开规则；`stop` 和 `maxstep` 仍须显式指定。
`.scs` 还接受显式 `strobeoutput=all/strobeonly` 保存策略，见下文。别名和显式零周期仍拒绝。
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
显式表与周期表取并集，最多 1,000,000 点（`evas.limits.MAX_OUTPUT_POINTS`，内核同值，见[请求级资源上限](proof-work-limit.md)）；舍入后周期点重合时明确拒绝。
窗口和偏移只能与周期一起使用，显式时间表不受周期窗口裁剪。
若窗口内没有周期点且显式表为空，展开结果为空，按普通请求执行，不生成
`strobe_evidence`。只有非空强制表要求完整回执；空表不是执行了强制求解。

无状态电路在强制点求解工作点。事件控制器将强制点纳入推进日程；
线性传播和非线性 Taylor/隐式历史在强制点分段。
源的 PWL 折点保持独立，强制点不会变成新的源插值定义。
这可能改变数值分段与误差包围，因此带 strobe 的请求须单独验证。
它不改变数学根处更新的事件契约，也不能保证另一后端选择相同事件相位。

固定参数 `timer` 与 strobe 同用时，调度器先收紧名义时刻的数值包围。
例如第三次 1 µs 周期事件，原区间运算会把执行点推到 `3.0000000000000005e-6 s`，
跨过请求的 3 µs。现在用精确比较找到包含名义时刻的最窄浮点区间，
再完成事件提交和强制求解。若请求点确实早于事件，则仍返回事件前状态。
这项修复没有放宽 `time_tol`，也没有把普通查询的结果改标为强制求解。
未开启 strobe 的请求保留原调度路径；保持状态决定的 timer 参数不采用该细化。

局部时间锚定的事件现在可以接受 strobe，但必须证明该点处于已经完成的物理阶段：
之前的事件都已发生，下一事件还没有发生，积分历史和节点电压也通过原预算。
控制器先提交这段前缀，把后续事件留在日程中；来源为 `accepted_controller_frame`。
例如两个周期时钟在 6 µs 附近先后发生，夹在中间的强制点仍可读取正确的计数和积分。

如果只能通过原子事件簇的 `certified_causal_frame` 查询取得结果，仍返回
`unsupported_strobe`。未能证明先后的根盒、非自治局部流等原拒绝边界也保留。
强制点不会因有一个可查询数值就被改标为正式接受帧。

`strobe_evidence` 使用版本 1，包含 `times`、`sample_origins` 和 `voltages_V`。
节点次序与常规结果一致。前端核对强制点完整性与来源，不能把缺失字段当成功。
当前来源为 `stateless_working_point`、`accepted_controller_frame` 或
`implicit_history_evaluation`；历史类来源的落点由积分分段规则及内核回归共同验证。
该字段不提供 Spectre 回调次序证明，也不扩大已有连续时间误差证据。
strobe 请求是 IR18 引入的可选扩展，当前编译格式为 IR19；旧内核拒绝未知请求字段，新前端拒绝缺失回执。

验证入口为 [公共控制测试](../../tests/test_strobe.py)、
[独立模型与冻结预算](../../validation/strobe/README.md)、
[采样积分与局部前缀回归](../../tests/test_sampled_integral_strobe.py)。
原 C1、#79 和 VCO 的严格边界缺口继续保留，不因新增控制或提示转为通过。

`.scs` 示例：`tran tran stop=1 maxstep=0.5 strobeperiod=0.25 strobedelay=0.125`。
常规观察网格仍为 `[0,0.5,1]`，四个强制点单独保存在 `strobe_evidence`；
它们不改写源 PWL。`load_scs` 在编译前检查时间表类型、范围和资源上限，
`simulate_scs` 将原控制交给已有 API。适配元数据同时记录控制参数和展开时间表。
[入口测试](../../tests/test_scs.py)与[接入配对说明](../../../experiments/backends/strobe/README.md#scs-adapter-checkpoint)
覆盖该入口；沿用既有实际 Spectre 观测，原缺失时间与设置资格 I 保留。

## 显式保存策略

`strobeoutput` 只选择 `simulate_scs` 响应中的 `saved` 行；完整 `solutions`、
`transient` 状态与事件、`strobe_evidence` 和观察证书保持相同。
`all` 保存常规观察行和强制行的并集。`strobeonly` 保存强制行和终止时刻；
若使用周期窗口，还保存窗口外的常规行。窗口包含两端，终止时刻始终保留。
没有 strobe 控制或只有空的显式表时，两种策略都保存常规观察行。
周期表为空的 `strobeonly` 组合尚未核对参考行为，明确拒绝。

例如 `stop=1 maxstep=.25 strobetimes=[.125 .625] strobeoutput=strobeonly`
保存 `[.125,.625,1]`，终止时刻无需另列为强制点。
改为 `strobeperiod=.25 strobedelay=.125 skipstart=.2 skipstop=.8` 后，
强制点为 `[.325,.575]`；常规网格位于窗口外的 `0` 和 `1` 也被保存。
原始源折点仍定义源波形，`strobeonly` 可按请求移除窗口内的源折点保存行。

未指定 `strobeoutput` 时，EVAS 保留原保存合同：`saved` 仅含常规观察行，强制点另存。
这与 Spectre 的默认 `strobeonly` 不同；需要保存策略的测试台须显式给出选项。
本次同源码实际 Spectre 21.1.0.509.isr12 对照核对了显式表、周期窗口及无 strobe 的两种策略，
没有要求两个后端采用相同常规时间步。
[固定模型与判据](../../validation/strobe/output-policy/case.json)、
[独立检查器](../../validation/strobe/output_policy.py)及
[拒绝校准](../../validation/strobe/test_output_policy.py)保留精确时刻、窗口外行和终止行义务。
Spectre 默认策略见 [Cadence strobe 说明](https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-tech-tips-using-the-spectre-strobe-feature)。
