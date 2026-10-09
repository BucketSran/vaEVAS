# 更新记录

本页记录版本变化与[历史执行身份](#检查点身份)。当前支持结论见[四后端支持范围](COMPARISON.md)，
逐项证据见[证据索引](development/capability-evidence.md)。单 PR 的细节以 PR/commit 描述为准，本页只留摘要。

<a id="baseline-20261009"></a>

## 2026-10-09：EVAS 0.14.0 开发基线整理

以已合入的 main `c2ca32ee` 为求解器基线，保留 IR18。本次仅把既有五项 strobe 控制
接入受限 `.scs`，没有改变 Rust 求解器、数学根执行约定或精度预算。
这是有明确支持边界的开发版本，不是完整 Spectre 电压域替代或论文最终验收声明。

- **架构已集成。** #108 集成共同事件验收；#117 将每批候选准备、完整事件簇准备与一次发布分开。
  历史、状态、输出和日程经检查后一起提交，失败不污染已接受状态。
  [责任与保持性证据](../../experiments/backends/event-acceptance/README.md)绑定原重构版本，
  不能推导 Spectre 兼容范围扩大。
- **输入接入。** `.scs` 的 tran 支持 `strobetimes`、`strobeperiod`、`strobedelay`、
  `skipstart`、`skipstop`；常规输出网格保持不变。见[控制合同](reference/strobe.md)
  和[实际参考复用](../../experiments/backends/strobe/README.md#scs-adapter-checkpoint)。
- **已知差异。** C1 精确边界前后态、#79 stop=3 计数、VCO 环回及 M1 参考资格继续保留原 F/I。
  Spec B 的原十二槽严格参考义务由 [#96](https://github.com/BucketSran/vaEVAS/issues/96)
  继续跟踪；架构集成与完整对齐分别验收。
- **保留候选。** #79 的 [e981ebd9](https://github.com/BucketSran/vaEVAS/commit/e981ebd9f0e0967c8f8842c31d1198458c9e19e9)
  是未合入的另一种端点根收缩实现。#118 原 [f3618c49](https://github.com/BucketSran/vaEVAS/commit/f3618c4930b360651080e7e5d2dbdaa2c97abe7c)
  的源驱动局部历史扩展未纳入本次基线，其代码、模型与失败证据留在固定历史，不能因接入部分合并而宣称该扩展通过。
- **后续需求。** 输入、诊断、语言、算子扩展分别在 #63/#64/#65/#66；双向自换向在 #70；
  Spectre 版本调查在 #16；精度控制优化在 #119。未实现范围保留明确拒绝，不随版本整理解除。

下方“候选”“未合并”等措辞描述各自历史检查点。当前源码支持查[四后端支持范围](COMPARISON.md)，
版本身份以固定提交为准；旧实验不重新标记为本次执行。

## 2026-10-07：输入比较初值与迟滞计数候选

- EVAS 0.14.0 / IR18 新增 real 状态由实际 driven/ground 仿射比较决定 0/1 初值。
- 全部初值先于模型、算子、守卫、t=0 事件和首行观察解析，严格/非严格 tie 分别保留。
- 异刻事件块可共享自增/自减计数；同刻选中两个写者仍原子拒绝。
- 旧 IR 必须从 VA 重新编译。原论文卡未改；开发回归不表示 Spectre 对齐或已合并支持。

以下 2026-10-06 检查点描述各 PR 引入的源码行为，合并状态见
[PR74](https://github.com/BucketSran/vaEVAS/pull/74)、
[PR75](https://github.com/BucketSran/vaEVAS/pull/75)、
[PR76](https://github.com/BucketSran/vaEVAS/pull/76)、
[PR78](https://github.com/BucketSran/vaEVAS/pull/78)、
[PR80](https://github.com/BucketSran/vaEVAS/pull/80)、
[PR82](https://github.com/BucketSran/vaEVAS/pull/82)、
[PR83](https://github.com/BucketSran/vaEVAS/pull/83) 和
[PR86](https://github.com/BucketSran/vaEVAS/pull/86)。
各项验证仍绑定各自执行版本，合并不会把旧收据重标为新版本，也不代表发布了 tag。

## 未合并开发切片：纯 real 函数有限分支（#65）

- 支持 `< <= > >=` 谓词的 if/else 与局部顺序赋值；条件使用进入支路前捕获的值。
- 两路均定义才形成汇合值，无 else 保留已有值；所有支路保留结构校验，原精度拒绝边界不变。
- 真实 PA clip 函数、独立限幅/实例/顺序答案和拒绝边界见[函数合同](../validation/ANALOG_CONDITIONS_CONTRACT.md#纯函数的分支候选)。
  不代表完整 PA 模型或更广函数语义支持；[两个有限 Spectre 配对](../../experiments/backends/function-branches/README.md)通过，
  原数字写法造成的两次编译失败保持可见。

## 2026-10-06：事件体静态循环（L3）

- 监测事件体中的静态 genvar 循环沿用现有顺序赋值内核；实例参数、数组和循环预算分别检查。
- 动态控制、历史调用和嵌套事件等边界继续拒绝；零次循环不能隐藏不支持的事件体。
- 不改变 IR17 或包版本，不代表原工程模型已完整支持；开发验收见 LANG 的对应测试。

## 2026-10-06：SCS 静态向量端口

- `.scs` 实例先绑定参数，再按声明方向展开 VA 向量端口并与标量列表配对。
- 三项 Spectre 准入探针和公共 EVAS 入口回归验证降/升序及实例宽度；总线文本语法仍拒绝。
- 此为 #63 的输入切片，包版本与 IR17 均未变。证据与边界见 [契约](../validation/SCS_VECTOR_CONTRACT.md)。

## 2026-10-06：完整运行产物

- 新增显式 `evas.results run`，保存生效请求、完整响应和无展示舍入的 CSV。
- 只有全部必需文件完成与校验后才原子写入完成状态，失败保留版本化诊断。
- 依赖包/内核身份接口，不改变原 JSON API 或数值内核。见[契约](reference/results.md)。

## 2026-10-06：仅编译预检与有限诊断登记（DIAG）

- 新增 `python -m evas lint manifest.json`，不查找或启动内核；成功仅表示编译检查通过。
- 在 manifest/source I/O、参数依赖/覆盖和编译资源预算来源登记稳定分类。
  未登记的诊断保留原 payload，类别为 `unknown`；来源盘点与实际执行检查分别计数。
- 不改变 IR17、数值行为或包版本；接口、已测边界与剩余缺口见[诊断说明](reference/diagnostics.md)。

## 2026-10-06：显式身份查询（PKG-ID）

- Python 与 Rust CLI 可在无 manifest、无 stdin 数据时查询实际包/内核身份。
- 绑定所选二进制哈希与报告的 IR schema；无来源或请求协议元数据时保留未知。
- 不改变 IR17、数值请求协议或包版本，详见[身份接口](reference/identity.md)。

## 2026-10-06：有限单极点 laplace_np（O2）

- 单项常量分子与一个负实极点在倒数系数可精确表示时转换为 `[b0]/[1,-1/p]`，保留 DC 增益。
- 复用原调用点、IR17 与滤波历史/误差机制，不增加 Rust 数值路径；epsilon、复杂/多极点和非精确转换拒绝。
- 独立高精度解析 DC/PWL 答案及实例/调用点回归支持这一有限范围，不代表 #66 全部能力完成。

## 2026-10-06：常量初始化与 cross 共用事件体（L2a）

- 一个无分析限定 `initial_step` 可与 cross 叶子 OR，共享无条件实例常量赋值体。
  初始化通过已有路径安装一次；后续穿越执行同一体，不伪造初始化事件记录。
- timer 混合、重复/分析限定初始化叶、动态初值及条件初始化仍拒绝；
  同刻写者冲突和 t=0 初始化先于 timer 的顺序保持不变。
- 不改变 IR17 或内核协议；有限验收与完整模型缺口见[事件手册](math/events.md#initial-cross)。

## 2026-10-06：两级固定 absdelay

- 从原始 PWL 结点导出整段历史包围，保留移位时间误差、每级调用点和补偿查询。
- 仅接收直接嵌套或同实例单位内部别名；结构依赖检查与最终节点预算继续生效。
- 独立 Fraction 答案、放大/大时间拒绝与真实 Frame 回退检查见[算子手册](math/operators.md#两级固定-absdelay-的移位历史包围)。
  冻结放大对照的 1e-6 预算仍拒绝，未宣称一般组合或新增 Spectre 资格。

## 2026-10-06：无状态比较与逻辑表达式（L1a）

源码行为与验证范围见 [PR85](https://github.com/BucketSran/vaEVAS/pull/85)，不据此宣称合并或发布。

- 以既有 Select IR 表达关系、逻辑和三元运算，保留源码身份与原精度判据。
- 隐藏分支中的非法结构仍拒绝；合法但未选中的条件不触发数值判定。
- 有限输入表、条件边界和实际 Rust 入口回归见[表达式测试](../tests/test_stateless_expressions.py)。
  本切片未执行完整 AND2 应用或新增 Spectre 对照，也不开放事件/历史中的一般逻辑。

## EVAS 0.13.0 / IR17（PR61；未发布 tag）

- 合并前 CI 修复 fuzz 种子的 IR16/17 不一致，并在常规 Rust 回归中检验种子及解析电压答案。
- 审查修复重复 include 的历史身份冲突。每条包含路径进入调用点身份；
  同一源文件多次包含的积分保留独立历史，并覆盖宏、循环和隐式反馈组合。

- 事件修改仿射/多项式 guard 后，候选内重建未来日程；失败保留已接受状态和日程。
- 固定 absdelay/slew 可读取联合仿射内部电压投影，独立误差仍传播。
- 纯 real 函数、有界静态 genvar 循环及一维静态索引变量数组在前端展开为同一关系 IR。
  展开的历史调用分别占用独立算子槽，并保存 genvar 路径，与实例/源码位置组成身份。
- 支持多模块源文件、静态子实例、命名/位置端口及参数覆盖；父子关系统一求解，
  子实例网络、状态及算子调用点使用完整实例路径。
- 预处理对象/函数宏、include 和条件编译；调用/包含位置及展开路径保持可追溯，
  源文件只从调用者提供的库存读取。宏复制的历史调用保持独立身份。
- OR 接受 cross/timer 叶子，记录各类型和原时间证书，同刻事件体执行一次。
- 无事件的 index-one 多项式 DAE 可与 proper 滤波联合运行，包括内部节点/算子输入。
  原电压关系、积分 IC 与滤波 DC 条件联合认证；严格 proper 滤波可用多项式输入。
  共同多项式 ODE 复用此证书处理非线性 DC；事件续算保留物理历史，不重新初始化。
  奇异初值、非线性直接通路和隐式 DAE 的事件/复位/ddt 仍拒绝。
- IR17 新增 `held_timer`；时间、周期、启用参数可由保持状态控制。下一事件采用
  最新参数，重新启用保留绝对相位；日程认证后才预测新的积分/滤波轨迹。
  连续电压参数、历史驱动 guard 的重定位仍拒绝。
- Python 包与 Rust 内核的版本均为 0.13.0。旧 IR1–16 须使用原 VA/manifest
  批量重编译。旧输入/工件身份和历史矩阵不改写；未宣称新的正式资格。

## EVAS 0.12.3 / IR16

- 后续检查点分离 `evas-ir`，保留原公开入口与 JSON16；数值状态和提交仍由统一内核管理。
- 新增可选有界诊断、静态贡献/来源查询及只读 stdio MCP；记录身份、失败和截断，缺证据不推测根因。
- 配对测量后减少稀疏消元重复查找，并仅在数值矩阵逐位一致时跨候选共享 LU。
  当前 RHS、原关系残差和历史认证各自执行；[收据与边界](../../experiments/performance/README.md)不构成通用加速承诺。

- 仿射求解在原关系残差超差时，最多复用 LU 做两次迭代精化；仍按原容差验收。
- 受限方阵在普通 Newton 失败后，可用有次数上限的残差连续化寻找初猜。
  最终解仍须通过原方程、原容差与适用的瞬态认证，不增加未认证输出模式。
- 静态批量支持显式选择 1–64 个线程，保持样本顺序和首个错误下标。
  新增可缩放随机矩阵、批量并行及五类瞬态路径基准。数学与边界见
  [数值手册](math/solving.md)。

## Python 前端与验证护栏（PR48、PR49）

- 前端分离实例编译，补齐参数、算子、输入/响应校验和编译资源上限；超时会回收子进程。
- 增加精确有理数区间性质测试、解析根的随机线性系统、两个有界 fuzz 入口，
  以及有独立答案的 ngspice 子集对照。这些不是原 31 条件的新增资格证据。
- 记录现有积分误差链与电压域架构决策；不引入电流/KCL 或更改 IR16。

## PR35：docs/traceability 重构

- docs/ 重组为 README / UPDATE / PROCESS / CAPABILITIES / math/（四章节迁入）；
  CAPABILITIES 保留支持边界与证据入口，TRACEABILITY 汇集文件级关联。
- 测试文件声明 GUARDS；scripts/traceability.py 校验标签、目标及生成物是否同步，
  不把标签完整当作语义覆盖完整或执行证明。
- 目录迁移后的冻结清单与历史收据恢复原身份；当前导航与固定历史链接分别维护。
- 此前文档重构（examples 三课、validation/smoke 分层、experiments 三分类、
  benchmark/reference 迁入）见对应提交 7d0398d / 6d806a0 / 8de77e9。

## EVAS 0.12.2 / IR16（PR33）

已知事件截止点：共同闭包与截止点各自重跑原 31 条件两档 31/31。
数学细节见 [math/continuous.md](math/continuous.md#known-event-horizons)。

## 更早检查点

PR26–PR32（IR11→IR16 演进）摘要见[检查点身份](#检查点身份)；
完整过程叙述保留在各 PR 与固定历史提交，不在本页展开。

## 检查点身份

以下是历史执行记录，不是当前版本重跑结果。

| 检查点 | 固定执行身份 |
| --- | --- |
| PR61 / 0.13.0 / IR17 | 确认冻结 `5171558c`、首次运行后端 `63afd040`；前一矩阵/确认及整合回归 `152a920d`；一致初值与观察修复 `114d676e`；包含身份审查修复及最终矩阵/确认复跑和回归 `d68d3db4`；见[候选收据](../../experiments/runs/capability-completion/README.md) |
| 诊断与性能 / 0.12.3 / IR16 | 配对基线 `e91cf6ff`、候选 `eb03f94d`；原矩阵运行时 `a388a651`；见[当前收据](../../experiments/performance/README.md) |
| PR50 / 0.12.3 / IR16：前轮矩阵重跑 | 被测 main `a7a42e17`；运行时、内核及新执行见前轮收据 |
| PR33 / IR16：事件截止点 | 运行时 `8618339`，合并点 `b4921ca` |
| PR32 / IR16：混合动态与生命周期 | 运行时 `1b99c33`，合并点 `431f335` |
| PR31 / IR16：非线性积分与联合事件 | 运行时 `d06e7f3`，合并点 `09b4222` |
| PR30 / IR16：连续动态 | 运行时 `ba5ab46`/`071a813`，合并点 `bedf20f` |
| PR29 / IR15：矩阵补齐与精度链 | 运行时 `d451605` |
| PR26 / IR11 及旧 EVAS 0.8.7 | 历史失败不改写为新版本成绩，见 [四后端矩阵](../../experiments/backends/dvs2-four-backend-validation/results/MATRIX.md) |

各检查点的收据由上表链接及[追溯矩阵](development/TRACEABILITY.md)导航，完整历史入口见
[实验目录](../../experiments/README.md)；早期失败（根盒等号、复位误拒绝、
Spectre 不一致等）保留在对应历史段落，修复不删除。
