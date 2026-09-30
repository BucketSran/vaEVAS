# EVAS 能力与缺口总表

核对日期：2026-10-01。当前 main 使用 EVAS 0.9.0 / IR v11，未发布版本 tag。
旧 IR v1–v10 须从原始 VA 重新编译。实现、证据与交付分别记录；
包版本号不能代替被测提交身份。数学与实现见[手册](README.md)，运行记录见[证据索引](../../experiments/README.md#checkpoint-evidence)。

候选 `feat/evas-analog-conditions` 已同步该 main，序列化格式为 IR v12，待本轮 review。
它的局部条件与 PWL 误差认证见[开发契约](../validation/ANALOG_CONDITIONS_CONTRACT.md)；分支检查不改变下表 main 范围或原矩阵成绩。
候选 `9c5d6c5` 的 306 Python / 64 Rust 与原 31×2 新本地矩阵见[验收修复记录](../../experiments/pr14-pr15-validation/RESULTS.md#analog-conditions-acceptance-review)：
两档各 25/31，原达标 48 份 CSV 哈希一致；未合并，原始材料仅本地保留。
后续[新 Spectre 对照与缺口专项](../../experiments/pr14-pr15-validation/RESULTS.md#analog-gap-spectre-comparison)
复用该 EVAS 执行、对 Spectre 新跑原 31×2，两档各 31/31；三个旧候选各新跑受影响两条件两档，
各 4/4。候选基线/IR 尚未统一，不能相加为整合版本 31/31；六个有理数边界探针另列。
此前 `3fd58da` 的 v1-main 专项作为[历史检查点](../../experiments/pr14-pr15-validation/RESULTS.md#analog-conditions-review)保留。

## 状态约定

- **实现**：未实现 / 分支限定实现 / main 限定支持。未支持的合法 VA 写法不等于语言非法。
- **证据**：独立数学样例、本地开发回归、有限后端对照、已知差异、待补证据可同时存在；不是单一通过分数。
- **交付**：待 review / 已 review / 已合并 / 已发布分别记录；包版本号不能代替发布 tag 和 commit。
- ID 稳定标识能力，与 PR、条件编号和测试数量不同。一个条件可关联多个能力，不能因此重复扩大分母。
  本表的建议后续工作不自动授权新实验、实现、发布或合并。

## 能力矩阵

表中的旧版本和 IR 编号标识首次交付或被测历史检查点，当前序列化格式统一为 IR v11。

| ID / 能力 | main 范围 | 交付来源 / 检查点 | 证据状态 | 剩余缺口与说明入口 |
| --- | --- | --- | --- | --- |
| LANG：语法、绑定、IR | 标量、参数、限定表达式、受限事件 if/else 与 cross OR、版本化 IR | PR23 交付事件条件/OR；main 使用 IR v11；普通 analog 条件为待 review 的 IR v12 分支 | 独立条件与畸形 IR 回归见[事件说明](EVENTS.md#event-conditions)；候选的限幅、PWL 阈值、误差放大、统一验收和两端谓词限制见[契约](../validation/ANALOG_CONDITIONS_CONTRACT.md)及[31×2 记录](../../experiments/pr14-pr15-validation/RESULTS.md#analog-conditions-acceptance-review) | 分支仍限无事件/动态算子的输入驱动仿射/限定分段仿射谓词；隐式反馈/数组/循环及更多函数待补；[当前语法](../README.md#实现范围) |
| LIN：线性电压关系 | 稠密/稀疏求解、参考节点、贡献累加、分解复用 | PR8 集成分流，交付见该 PR | 构造解及 0.7.1 新静态回放；候选无状态 PWL 统一验收见[修复记录](../../experiments/pr14-pr15-validation/RESULTS.md#analog-conditions-acceptance-review) | 病态系统与更广规模边界；[数值说明](NUMERICS.md) |
| NONLINEAR：多项式反馈 | 静态 `solve` 的阻尼 Newton、解析 Jacobian、三项验收 | 已合并 PR6 | 独立高精度参考、缩放/容差及失败回归 | 非线性瞬态、初猜、延续法、多解及更广函数；[数值说明](NUMERICS.md) |
| SPARSE：稀疏线性代数 | n≥32、nnz≤0.1mn 时采用稀疏 LU；适用于静态、Newton 及限定事件/历史算子的电压解 | [PR8](https://github.com/BucketSran/vaEVAS/pull/8) 于 0.7.1 / IR v7 交付 | 该检查点的整合回归、构造解/原残差、稀疏事件/算子和 idt 检查；性能数据限旧检查点 | 历史区间认证仍稠密；排序/填充/复用由 [Issue9](https://github.com/BucketSran/vaEVAS/issues/9) 跟踪；[数值说明](NUMERICS.md#稀疏分支与性能边界) |
| CROSS：阈值事件 | 连续 PWL/仿射、状态独立 guard；触零/平台/stop 到达及 cross OR | 已合并 PR7/10；PR23 审阅交付 OR、逐叶证书与同块去重 | 数学/开发回归、历史限定 Spectre 对照；0.9.0 原 31 矩阵见[收据](../../experiments/pr14-pr15-validation/RESULTS.md#event-conditions-090) | 非线性轨迹和反馈后的重新定位；[事件说明](EVENTS.md) |
| TIMER：固定定时事件 | 固定 start/period/time_tol/enable，有限日程 | PR12 合入：0.5.3 / IR v5 | 本地回归；普通/同刻有限对照及顺序赋值回放 | 动态参数、enable 与复合事件；同刻问题关联 EVENT-ORDER |
| EVENT-ORDER：同刻与原子提交 | 仿射状态/电压联立、前向认证、integer/real 顺序赋值、认证条件路径、批次内单写者、整批提交/回退 | PR12/13 已合入；PR14 延续历史误差传播；PR23 审阅交付路径缓存、输入与旧状态包围及 OR 同块去重；[PR25](https://github.com/BucketSran/vaEVAS/pull/25) 经审阅交付多 writer 受限支持 | PR12/13 历史证据保留；新增条件失败/弃步/修正未来输入重试；迟滞、实际 Selection 冲突、结构跨块读取拒绝及新 V3 EVAS/Spectre 两档对照，正式资格 I | Spectre 21.1 重复赋值异常见 [Issue16](https://github.com/BucketSran/vaEVAS/issues/16)；反馈 guard 仍缺；同批多块写同一状态仍 `event_conflict`，跨块 state 读取仍拒绝；[说明](EVENTS.md#timer-与同刻兼容性) |
| TRANSITION：延迟与有限边沿 | 固定延迟、显式正边沿、状态仿射输入 | PR13 已合入；0.6.1 / IR v6 | 6 项 Fraction 精度回归；共同观察网格下 EVAS/Spectre 各 16/16 | 完整观察资格、区间保守性、更广同刻语义/动态参数/输入；[算子说明](OPERATORS.md#transition) |
| ABSDELAY：历史查询 | 固定非负延迟、直接连续 PWL 的仿射输入，历史误差传播 | PR14 已合入；被测 `3638024`，收尾不改运行时代码 | 独立 PWL/大时间减法、同刻/跨事件回归；[专项](../../experiments/pr14-pr15-validation/RESULTS.md) EVAS/Spectre 各 12/12 | 内部节点/状态输入、可变延迟、跳变、嵌套及反馈；[算子说明](OPERATORS.md#absdelay) |
| SLEW：限速与追赶 | 固定正/负限速、直接连续 PWL 的仿射输入 | 随 PR15 交付；被测 `e01fb5b`，依赖 PR14 已合入 | 局部交点/历史误差回归；[专项](../../experiments/pr14-pr15-validation/RESULTS.md) EVAS 16/16、Spectre 10/16，步长诊断保留 | 内部节点/动态参数/组合；[算子说明](OPERATORS.md#slew) |
| COMPOSE：实例与组合 | 静态反馈、限定事件采样与实例隔离 | 随 PR15 集成组合回归；另补独立语义不变性回归 | PR15 8 配置独立 Fraction 检查通过；新增 3 项贡献排列、重命名与观测不变性回归见[覆盖映射](../validation/DYNAMICS_CONTRACTS.md)；旧联合检查点保留 | 算子前向组合、算子驱动 cross、状态反馈同刻迭代；单项正确不能推出组合正确 |
| DYNAMICS：积分、导数、滤波、相位 | 显式常量初值、直接连续 PWL 仿射输入的二参数 idt，及受限状态 reset 的三参数 idt；导数/滤波/相位未交付 main | [PR19](https://github.com/BucketSran/vaEVAS/pull/19) 交付二参数；[PR26](https://github.com/BucketSran/vaEVAS/pull/26) 交付 reset，IR v11；被测运行时 `edb004d` | [独立契约与恢复检查](../validation/DYNAMICS_CONTRACTS.md)；hold/release、transition 组合、同引擎弃候选与事件时间区间回归；两档各 24/31，相比 PR25 main `6df7f48` 各 22/31，原达标 44 份 CSV 逐字节一致，见[完整审查对照](../../experiments/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)；[数学与实现](OPERATORS.md#idt) | 仍限定无结构复位反馈环的状态 reset、直接 PWL 输入；积分输入反馈、嵌套、积分驱动 cross、连续时间资格及完整调度器失败恢复待补；已重跑原 31×2 本地矩阵，未新增后端对照 |
| QUALIFICATION：独立验收 | 开发条件与检查器，无完整资格结论 | 原 31 条件瞬态矩阵两档执行；PR20 交付独立 checker 校准 | [PR23 历史收据](../../experiments/pr14-pr15-validation/RESULTS.md#event-conditions-090)：两档各 21/31；[已合并 PR26 运行时对照](../../experiments/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)：`edb004d` 各 24/31，PR25 基线 `6df7f48` 各 22/31；历史与其他后端失败保留；[S1 审阅补充](../validation/NEXT_CASE_CARDS.md#s1-review)及 E1/E2/C1 校准 | 观察误差界、未见确认集；S1 新顺序条件未执行后端，不增加原矩阵成绩；正式资格仍 I；[协议](../validation/METHOD_QUALIFICATION.md) |
| PERFORMANCE：效率证据 | 有库内局部基准和稠密/稀疏分流 | PR8 合成检查点保留；当前版本未重新计时 | 不同旧提交的局部测量；18.5% 退化未稳定复现，见[边界](NUMERICS.md#稀疏分支与性能边界) | 同版本端到端/瞬态/跨后端比较；首次、重复、内存分开报告 |

电流未知量、器件级负载与完整 SPICE 分析不在当前电压域任务的默认范围内；不将它们自动列为必做待办。

## 工作与证据身份

- 最新已合并实现：PR26，被测运行时 `edb004dbb4b05ebd91c1f1f3bb7f261fd1d19b8f`；
  [审查对照与收据](../../experiments/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)保留基线、逐配置结果及检查身份。
- 各轮执行与重判沿[实验索引](../../experiments/README.md#checkpoint-evidence)进入原协议和结果，历史数据不充当当前源码的新执行。
- 早期 PR 的完整身份表与四能力本地联合检查记录见[固定历史版本](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/docs/CAPABILITIES.md#工作与证据身份)。
  其中仅本地保存的提交、日志和波形不构成公开数据可用性；各轮检查数量不能相加为条件通过数。

## 本地整合与交付边界

当前联合候选 `test/evas-gap-integration` 已同步 main `78e914f` 和 analog 验收修复，
整合一阶滤波、相位与无状态非线性瞬态，格式统一为 **IR v15**。保留主分支的复位反馈
拒绝和候选历史重放，并补充 `sin` 消费复位积分器时的同刻重算。尚未创建新 PR 或合入 main。
本轮范围、数学入口、联合检查与原矩阵证据见[当前复审记录](../../experiments/parallel-gap-integration/REVIEW.md#gap-completion)。
此前 IR14、单项分支及旧 main 的收据保持历史身份，不能代替本轮联合验证，也不改写上表的 main 交付范围。

## 后续工作顺序

后续工作从当前 0.9.0 / IR v11 main 开始；每项使用一个可独立 review 的 PR，实际依赖才堆叠。
受限事件体条件与 cross OR 已完成原 8 条件两档有限观测验证；多事件写者及受限 idt 复位也已完成审阅与矩阵检查；下表仅保留剩余范围。
条件数是受影响范围，不是新增达标承诺；
完整拒绝诊断见[原矩阵](../../experiments/pr14-pr15-validation/RESULTS.md)。

| 优先顺序 / 能力 | 下一项范围与数学依据 | 对应原条件 | 验收重点 |
| --- | --- | --- | --- |
| 1 / LANG | 普通 analog 局部顺序赋值、比较及 if/else；先限定输入驱动的分段仿射关系 | v1-main（1） | 独立限幅公式、等号边界、阈值定位、语句顺序；暂不扩展隐式分支反馈 |
| 2 / NONLINEAR | 无动态状态和事件耦合的非线性瞬态入口：在请求时刻解 F(v,u(t))=0，复用 Newton | v7-nonlinear 两条（2） | 独立单调三次方程根、前一点初猜、容差/失败；不声称已支持非线性 cross |
| 3 / DYNAMICS + LANG | 标准常量数组与一阶 laplace_nd；先实现 τ y′+y=u 的独立状态演化，再测试采样级联 | v6-standard、c2-main（2） | 指数/斜坡解析解、初值、长时间稳定性及级联；不能只通过数组解析就记支持 |
| 4 / DYNAMICS + LANG | constants 宏、idtmod 和 sin；累计相位与取模相位分开保存 | d2-constant/chirp（2） | 相位积分、环绕边界、长期累计误差、频率变化；依赖 idt |

已有待整合实现及新专项证据见[缺口对照](../../experiments/pr14-pr15-validation/RESULTS.md#analog-gap-spectre-comparison)：
非线性候选 `227c77c`、滤波 `4389640`、相位 `11f49d2` 均在受影响原条件两档各 4/4。
它们基于旧 main `508f5b9`，使用 IR v9/v12/v13；应先同步当前 main、统一共享 IR/瞬态入口并
保留事件/复位修复，再对联合检查点验收。这条证据不更新上表 main 交付范围。

SPARSE 的共享矩阵与瞬态调用路径已在 PR8 整合验证；后续按 Issue9 优化排序、填充和分解复用。
瞬态试算、固定矩阵复用、分段求值及按需事件日程另登记为
[Issue24](https://github.com/BucketSran/vaEVAS/issues/24)，当前延后；优先完成上述声明范围的功能、精度链与独立验证。
固定同一支持范围与误差目标，分开测构建/编译、首次求解、
重复求解、瞬态与内存；没有相应测量前不报速度倍数。性能路线不改变上述功能覆盖分母。

每项先固定数学契约、独立答案和接受/拒绝边界，再实现并跑专项与受影响原条件。
积累到功能检查点后重跑完整矩阵；扩大覆盖后另冻结未参与开发的确认集。
具体负责人、执行预算和新任务范围放在后续任务/Issue/PR，不由本表自动授权。

每次状态更新需链接相应提交/证据；能力 ID 不随 PR 结束而改变。合并时标记 main 支持的限定范围，
发布时记录实际 tag；未发布不能只凭包内版本号标为发布完成。
