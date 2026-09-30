# 六路缺口的本地整合审查

**当前入口（2026-10-01）**：[精度链修复与兼容边界](REVIEW.md#precision-chain)，
上一轮[同刻查询与标量认证优化](REVIEW.md#accuracy-optimization)保持历史执行身份，
功能补齐入口为[六个剩余条件的联合补齐与分批 review](REVIEW.md#gap-completion)。
候选使用 IR v15，已同步 main `78e914f`。`ddfd379` 的原 31 条件两档均 31/31，
62 份 CSV 与优化前 `39a4545` 不变；后续精度链检查单独归档。尚未合入 main，证据范围及复用方式见上述记录。

## 以下为 IR14 历史联合检查点

以下内容保留原执行及失败身份，不代表当前候选状态。

本轮从 PR21 合并提交 `508f5b924360a48c66b569a1719157a883d1db9f` 的 main 基线出发。
六路实现只在本地分支，尚未发布新 PR、合并 main 或创建 tag。
本页集中记录各自的数学契约、依赖、交叉审查、联合实验和建议审阅顺序。

下面的联合运行及分支表是 `f94a2c9` 保存的固定检查点，不随后续修复改写。
本轮复审发现的新反例、当前可审阅候选及其身份见 [复审记录](REVIEW.md)；
旧联合测试通过不能替代新 head 的受影响验证。

## 范围与所有权

原 31 条件的 DUT、刺激、两档设置、独立检查器与分母保持不变。本轮处理 main
仍拒绝的 10 个条件所需的受限能力；不声称交付完整 Verilog-A 或连续时间精度认证。

| 本地分支 | 能力与数学契约 | 原条件 | 依赖 |
| --- | --- | --- | --- |
| `feat/evas-analog-conditions` | 顺序局部赋值捕获当时表达式；贡献相加；输入驱动 `Select` 的严格符号判定。[契约](../../evas/validation/ANALOG_CONDITIONS_CONTRACT.md) | v1-main | 共用有序 analog AST 与结构依赖 |
| `feat/evas-multiple-event-writers` | 各时刻先选中事件路径，检查实际写集合，再联立解与整批提交。同批两块写同一状态即拒绝。[事件](../../evas/docs/EVENTS.md) | v3-main | 现有 Frame 与事件求解 |
| `feat/evas-nonlinear-transient` | 无状态、无事件、无历史算子时逐点解 `F(v;fl(PWL(t)))=0`；前一成功点仅作 Newton 初猜。[精度边界](../../evas/validation/NONLINEAR_TRANSIENT_CONTRACT.md) | v7-nonlinear-0.5 / 2.0 | 现有 Newton；不代表完整误差链 |
| `feat/evas-idt-reset` | 复位非零时保持 IC；释放后从认证事件时刻继续积分，历史只在候选提交后生效。[算子](../../evas/docs/OPERATORS.md) | d1-free / reset | 多事件写者、已有 PWL idt |
| `feat/evas-laplace-first-order` | 常量数组、一阶 `b0/(d0+d1*s)`；PWL 输入的解析响应与带余项的指数包络。[算子](../../evas/docs/OPERATORS.md) | v6-standard / c2-main | 标准数组语法、历史认证 |
| `feat/evas-phase-operators` | 显式正 modulus/offset 的 idtmod，受限 sin；原始仿射系数区间与正弦 Taylor 余项。[算子](../../evas/docs/OPERATORS.md) | d2-constant / chirp | PWL idt、顺序局部算子引用 |

各分支只写自己的 worktree。整合者独占共同 IR 版本、整合 Git index、能力表及实验收据。
分支保留自己的开发提交；合并冲突的解决与组合修复另留本地整合提交。

| 分支 | 该联合检查点固定的本地 head |
| --- | --- |
| analog conditions | `134280e24dca1299b24c6a62aa90adf54af0915f` |
| event writers | `44b148cc327219af155bf76995bd3fc810983c4d` |
| nonlinear transient | `7e9380a0783e9fa3972c1164e0ed441040e49162` |
| idt reset | `778a6674923a4ecc0011905d1bd88b5bc666cbc9` |
| first-order laplace | `43896403e5d292aabcd5913c6733161262b84ee8` |
| phase | `37ec5951538ff61875f3b79bdc4af0b67b413404` |

## 联合设计与冲突处理

联合分支为 `test/evas-gap-integration`，包版本仍为 0.9.0，但 IR 统一为 **14**。
版本号不是发布身份；本地源码 commit 与内核 SHA256 必须一并引用。

- 统一一个有序 analog AST 和局部变量 resolver。赋值是表达式快照，贡献继续进入方程组累加。
- 无条件局部算子赋值使用独立调用点身份；重复写同一变量不共享积分历史。
- 删除重复的无状态瞬态入口；事件/动态轨迹和无状态 Newton 入口保留明确分流。
- 所有历史算子共享值、区间、候选 advance 与验收接口；不以一次名义值求解代替历史误差认证。
- 结构依赖必须在 lowering 后继续保留，不能通过相消、乘零或局部别名绕过支持边界。
- 普通 `Select` 与动态算子联立、非线性与事件/动态状态联立仍明确拒绝；算子驱动 cross、反馈积分尚未交付。

组合探针在 [test_gap_integration.py](../../evas/tests/test_gap_integration.py)：
局部快照与加法、一阶滤波、多个写者/复位/transition 同批、相位别名与滤波历史、
独立积分调用点、被相消掩盖的反馈，以及上述拒绝边界。它们是开发探针，不是新增独立条件。

## 交叉审查的反例与处理

| 反例 | 原风险 | 本轮处理 |
| --- | --- | --- |
| `u+1e16 > 1e16`，`u=1` | 名义 f64 两侧相等，分支选错 | 精确 product-sum 符号；结构 scalar multiply 仅在乘积可证明精确时进入该路径，否则区间/拒绝 |
| 局部别名内相消输出依赖 | 直接写拒绝、别名写接受 | 普通 analog 条件也触发结构保留，直接/别名拒绝一致 |
| 非精确释放时间下的积分前缀极值 | 名义零点不足以包络真实极值 | 对重叠 PWL 段的完整区间作保守积分包络 |
| `laplace_nd` 的 libm 一 ulp 或预先舍入的比值 | 未证明包络真实指数、系数与大时间差 | 原系数 outward arithmetic、带下一项余项的级数与倍增，包含时间减法区间 |
| 相位包裹与 binary64 `2π` | 未认证的周期捷径或假定浮点常数为精确周期 | 完整相位区间；sin 消费端分别包络 wrap 两侧后取并集 |
| `1e16*p+p-(1e16-2)*p` | 系数名义相消得 2，真实 IR 系数为 3 | 从原始 sin 输入重算系数区间；预算不足时拒绝 |
| `sin(p+q-q)` 或 `sin(p+0*q)` | 第二调用点的结构依赖被零系数掩盖 | 构造前要求 operator 结构依赖集合恰为单一调用点 |

仍未解决的精度问题单独保留：无状态逐点入口未把源插值误差及完整算术误差经
电路灵敏度传入输出验收。`y=1e16*(u-1)`、源 `(0,1),(3,2)`、`t=1` 的残差可以为零，
但相对精确 PWL 答案偏差为 `2/3 V`，超过请求的 `1e-12 V`。
这不是精度更高的证明，不能把错误答案写成应通过的回归。
详见 [NUMERICS](../../evas/docs/NUMERICS.md#无状态瞬态的输入误差边界)。
[诊断程序](diagnose_input_error.py) 与 [新执行结果](results/input-error.json) 可重查精确有理数答案；
该反例独立于原 31 条件，不以修改原 checker 掩盖。

## 实验身份与边界

冻结源为原 PR14/15 的 31 条件，两档共 62 次本地 EVAS 请求。
INPUT_MANIFEST SHA256：`837787b02fbc503e33108baecb38794d03772fc9e3257e9601c2815b18265421`。
检查器 [check_results.py](../dvs2-spectre-validation/check_results.py) SHA256：
`189f9102244ad2804338a0ac2dc1a030db9dedd6cf1570e273b3622c96454d6b`。

执行复用 [matrix.py evas](../pr14-pr15-validation/matrix.py) 的本地适配器；
[analyze.py](analyze.py) 校验输入、运行源码、波形和清单身份，再调用同一个独立检查器。
本轮不启动 Spectre，不把历史 Spectre 结果记成新执行，也没有修改 checker 阈值。

main 的两档各 21/31 有限观测达标复用 [0.9.0 收据](../pr14-pr15-validation/results/event-conditions-0.9.0.json)，
不是本轮重新执行。联合运行时固定在 `bb42a8fd403a33b92acabadaf1aa160b9a6d84ae`，
内核 SHA256 为 `ef1d75757dbbfa8eb9025103433a051712e245e02a06dc03bebfb23b414456f6`。
此后的整合提交只补实验工具、文档与结果，运行时身份经收据中的源码哈希再次核对。

| 固定版本 / 证据 | 基础档（分母 31） | 细化档（分母 31） |
| --- | --- | --- |
| main 0.9.0，历史证据复用 | 21 观测达标、7 编译拒绝、3 内核拒绝 | 21 观测达标、7 编译拒绝、3 内核拒绝 |
| 本地联合 IR14，62 次新请求 | 30 观测达标、1 内核拒绝 | 30 观测达标、1 内核拒绝 |

[逐条矩阵](results/MATRIX.md) 与 [完整整理收据](results/original31.json) 保留所有配置。
新增的 9 条为 v1、v3、v7 非线性两条、d1 两条、v6、c2、d2-chirp。
唯一拒绝条件 `d2-constant` 的两档均为 `waveform_accuracy`：wrapped 输出包围宽近 1 V，
而预算约为基础档 `1.001e-5 V`、细化档 `1.001e-6 V`。现有 raw-phase 区间跨过 wrap，
不足以证明直接 wrapped 电压落在哪一侧。后续需要改进 wrap 边界认证；不能用 sine
的近连续性给直接 wrapped 电压代证，也不能删除该配置来改变分母。

[联合开发检查](results/checks.json)：322 Python、72 Rust 回归通过，包含 8 项组合探针；
构建、格式、all-targets warnings-as-errors、设计数学、9 项动态数学和冻结资产身份检查通过。
完整 raw 波形、日志、二进制仅本地保存；本页及整理收据随本地 Git 保存，尚未公开发布。
正式资格仍为 **I**：有限输出采样与开发反例不构成连续时间误差证明或未见确认集。

## 建议分批 review 与整合

1. 先审多事件写者，再审依赖它的 idt reset；重点看选中写集合、同刻边界与失败回退。
2. 审统一前端与 analog 条件；重点看贡献/赋值区别、结构依赖、等号与非精确乘积。
3. 审一阶 laplace；重点看标准数组语义、DC 初值、指数余项、时间/系数区间及历史查询无副作用。
4. 审 idtmod/sin；重点看 wrap 两侧、真实系数、拒绝边界；直接 wrapped 电压不能用正弦连续性替代认证。
5. 无状态非线性入口先 review 精度契约；完整输入/算术误差链未解决，暂不建议直接并入 main 宣称总电压精度。

在该检查点的初步审查中，多事件写者、idt reset、analog 条件和一阶 laplace 被列为下一批 review 候选。
这不是合并结论；后续复审的阻塞问题和修复状态以 [复审记录](REVIEW.md) 为准。
phase 的 chirp 与正弦子集有正向证据，但原 constant wrap 缺口仍保留，宜先单独审阅该边界。

实际交付时每次只把已审阅能力及其真实依赖移入一个候选 PR，更新 main 能力表与 IR
版本并重跑受影响组合。临时整合分支只用于发现冲突和固定联合证据，不自动成为一个大 PR。
