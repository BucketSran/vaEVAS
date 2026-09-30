# 六路缺口的本地整合审查

本轮从 PR21 合并提交 `508f5b924360a48c66b569a1719157a883d1db9f` 的 main 基线出发。
六路实现只在本地分支，尚未发布新 PR、合并 main 或创建 tag。
本页集中记录各自的数学契约、依赖、交叉审查、联合实验和建议审阅顺序。

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

仍未解决的精度问题单独保留：无状态逐点入口未把源插值误差及完整算术误差经
电路灵敏度传入输出验收。`y=1e16*(u-1)`、源 `(0,1),(3,2)`、`t=1` 的残差可以为零，
但相对精确 PWL 答案偏差为 `2/3 V`，超过请求的 `1e-12 V`。
这不是精度更高的证明，不能把错误答案写成应通过的回归。
详见 [NUMERICS](../../evas/docs/NUMERICS.md#无状态瞬态的输入误差边界)。

## 实验身份与边界

冻结源为原 PR14/15 的 31 条件，两档共 62 次本地 EVAS 请求。
INPUT_MANIFEST SHA256：`837787b02fbc503e33108baecb38794d03772fc9e3257e9601c2815b18265421`。
检查器 [check_results.py](../dvs2-spectre-validation/check_results.py) SHA256：
`189f9102244ad2804338a0ac2dc1a030db9dedd6cf1570e273b3622c96454d6b`。

执行复用 [matrix.py evas](../pr14-pr15-validation/matrix.py) 的本地适配器；
[analyze.py](analyze.py) 校验输入、运行源码、波形和清单身份，再调用同一个独立检查器。
本轮不启动 Spectre，不把历史 Spectre 结果记成新执行，也没有修改 checker 阈值。

main 的两档各 21/31 有限观测达标复用 [0.9.0 收据](../pr14-pr15-validation/results/event-conditions-0.9.0.json)，
不是本轮重新执行。六路最终联合结果与检查身份将在本目录结果收据中记录。
完整 raw 波形、日志、二进制仅本地保存；本页及整理收据随本地 Git 保存，尚未公开发布。
正式资格仍为 **I**：有限输出采样与开发反例不构成连续时间误差证明或未见确认集。

## 建议分批 review 与整合

1. 先审多事件写者，再审依赖它的 idt reset；重点看选中写集合、同刻边界与失败回退。
2. 审统一前端与 analog 条件；重点看贡献/赋值区别、结构依赖、等号与非精确乘积。
3. 审一阶 laplace；重点看标准数组语义、DC 初值、指数余项、时间/系数区间及历史查询无副作用。
4. 审 idtmod/sin；重点看 wrap 两侧、真实系数、拒绝边界；直接 wrapped 电压不能用正弦连续性替代认证。
5. 无状态非线性入口先 review 精度契约；完整输入/算术误差链未解决，暂不建议直接并入 main 宣称总电压精度。

实际交付时每次只把已审阅能力及其真实依赖移入一个候选 PR，更新 main 能力表与 IR
版本并重跑受影响组合。临时整合分支只用于发现冲突和固定联合证据，不自动成为一个大 PR。
