# 四后端支持对比

比较范围固定为每个行名所链接的模型与配置，四个后端使用相同用例和验收要求。
结果来自不同版本，**不代表当前 main 的一次全量验收，也不覆盖所有合法写法**。
前五节列固定 Q 用例；[第六节](#engineering-status)列工程请求的交付与缺口，两者分别验收。

<a id="table-design"></a>

**✓ Qn** 表示本行全部必测用例的数值、时间、状态和关键边界均通过该档；其他格写出失败原因或未完成的验收。
Q 是验收上限：1 V 刻度的 Q1 / Q2 / Q3 为 10.1 µV / 1.01 µV / 101 nV，1 mV 刻度的 Q3 为 1.1 nV。
判据见[评测标准](COMPARISON-METHODOLOGY.md)，执行版本与表外能力见[来源和补充证据](development/COMPARISON.md#table-evidence)。

<a id="支持矩阵"></a><a id="precision-binding-results"></a><a id="新精度测试"></a><a id="precision-breadth-results"></a>

## 1. 语言与静态电压关系

| 能力与测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [宏与 include（含实例）](../validation/paper/COVERAGE.md#scope-l1-01) | ✓ Q3 | 层次语法编译失败 | ✓ Q3 | ✓ Q3 |
| [参数](../validation/paper/COVERAGE.md#scope-l1-02) | ✓ Q3 | 层次语法编译失败 | ✓ Q3 | ✓ Q3 |
| [条件与逻辑表达式](../validation/paper/COVERAGE.md#scope-l1-03) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [case 分支](../validation/paper/COVERAGE.md#scope-l1-04) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [顺序赋值](../validation/paper/COVERAGE.md#scope-l1-05) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [用户函数](../validation/paper/COVERAGE.md#scope-l1-06) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [静态循环](../validation/paper/COVERAGE.md#scope-l1-07) | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
| [变量数组：静态下标](../validation/paper/COVERAGE.md#scope-l1-08) | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
| [电气向量](../validation/paper/COVERAGE.md#scope-l1-09) | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
| [模块层次](../validation/paper/COVERAGE.md#scope-l1-10) | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [sin](../validation/paper/COVERAGE.md#scope-l1-11) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [cos](../validation/paper/COVERAGE.md#scope-l1-12) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [exp](../validation/paper/COVERAGE.md#scope-l1-13) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [ln](../validation/paper/COVERAGE.md#scope-l1-14) | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [sqrt](../validation/paper/COVERAGE.md#scope-l1-15) | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [pow：三次幂](../validation/paper/COVERAGE.md#scope-l1-16-cube) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [pow：半次幂](../validation/paper/COVERAGE.md#scope-l1-16-half) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [电压访问与贡献](../validation/paper/COVERAGE.md#scope-l1-17) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [静态电压反馈](../validation/paper/COVERAGE.md#scope-l1-18) | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |

## 2. 单个动态算子与基本事件

| 能力与测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [initial_step：事件状态初始化](../validation/paper/COVERAGE.md#scope-l2-01) | ✓ Q3 | 编译或初始化失败 | 编译失败 | ✓ Q3 |
| [cross：斜坡穿越](../validation/paper/COVERAGE.md#scope-l2-02) | ✓ Q3 | 初始化失败 | 漏事件 | ✓ Q3 |
| [固定 timer](../validation/paper/COVERAGE.md#scope-l2-03) | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [事件 OR：采样与复位](../validation/paper/COVERAGE.md#scope-l2-05) | ✓ Q3 | 编译失败 | 漏事件 | ✓ Q3 |
| [transition：定时非对称沿](../validation/paper/COVERAGE.md#scope-l2-06) | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [固定 absdelay](../validation/paper/COVERAGE.md#scope-l2-07) | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [固定 slew](../validation/paper/COVERAGE.md#scope-l2-08) | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [idt：非零初值与正负面积](../validation/paper/COVERAGE.md#scope-l2-09) | ✓ Q2 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [idtmod：原始相位与环回](../validation/paper/COVERAGE.md#scope-l2-10) | 环回边界未验收 | 环回边界未验收 | 编译失败 | ✓ Q3 |
| [ddt：二次时间表达式](../validation/paper/COVERAGE.md#scope-l2-11-time) | Q1 误差超限 | 误差超限 | ✓ Q2 | ✓ Q3 |
| [ddt：电压斜坡平方](../validation/paper/COVERAGE.md#scope-l2-11-input) | ✓ Q2 | 误差超限 | ✓ Q2 | ✓ Q3 |
| [一阶 laplace_nd](../validation/paper/COVERAGE.md#scope-l2-12) | ✓ Q3 | ✓ Q3 | 非零初态错误 | ✓ Q3 |
| [一阶 laplace_np](../validation/paper/COVERAGE.md#scope-l2-13) | ✓ Q3 | 编译失败 | 误差超限 | ✓ Q3 |
| [二阶滤波（内部微分）](../validation/paper/COVERAGE.md#scope-l2-14) | ✓ Q3 | Q1 误差超限 | 误差超限 | ✓ Q3 |

## 3. 简单组合

| 能力与测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [采样保持：定时](../validation/paper/COVERAGE.md#scope-l3-01-timer) | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [采样保持：阈值](../validation/paper/COVERAGE.md#scope-l3-01-cross) | ✓ Q3 | 初始化失败 | 漏事件 | ✓ Q3 |
| [采样、复位与输出边沿](../validation/paper/COVERAGE.md#scope-l3-02) | ✓ Q3 | 编译失败 | 漏事件 | ✓ Q3 |
| [迟滞比较器与边沿](../validation/paper/COVERAGE.md#scope-l3-03) | ✓ Q3 | 初始化失败 | 误差超限 | ✓ Q3 |
| [定时采样→积分：原模型](../validation/paper/COVERAGE.md#scope-l3-04-timer) | ✓ Q3 | 初始化失败 | 漏定时事件 | ✓ Q3 |
| [采样→积分：停止边界与非线性](../validation/paper/COVERAGE.md#scope-l3-04-ordered) | ✓ Q3 | 初始化失败 | 停止边界未达标 | ✓ Q3 |
| [积分级联与复位](../validation/paper/COVERAGE.md#scope-l3-05) | 复位误差超限 | 初始化失败 | 误差超限 | ✓ Q3 |
| [非线性输入与滤波直通项](../validation/paper/COVERAGE.md#scope-l3-06) | Q2 误差超限 | Q1/Q2 误差超限 | 误差超限 | ✓ Q3 |
| [滤波与微分：DC 直通项](../validation/paper/COVERAGE.md#scope-l3-07) | Q3 启动误差超限 | ✓ Q3 | 误差超限 | ✓ Q3 |
| [两个固定延迟的历史](../validation/paper/COVERAGE.md#scope-l3-08) | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [两级 slew 与反向追赶](../validation/paper/COVERAGE.md#scope-l3-09) | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [中断边沿→积分](../validation/paper/COVERAGE.md#scope-l3-10) | ✓ Q3 | 新版验收未跑 | 新版验收未跑 | ✓ Q3 |
| [数组的事件状态更新](../validation/paper/COVERAGE.md#scope-l3-11) | ✓ Q3 | 初始化失败 | 编译失败 | ✓ Q3 |

## 4. 完整工程信号链

| 能力与测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [采样→保持→边沿→滤波](../validation/paper/COVERAGE.md#scope-l4-01) | ✓ Q3 | 编译失败 | 事件与输出错误 | ✓ Q3 |
| [滤波→采样保持](../validation/paper/COVERAGE.md#scope-l4-02) | ✓ Q3 | 编译失败 | 采样历史错误 | ✓ Q3 |
| [电压求解→延迟→采样](../validation/paper/COVERAGE.md#scope-l4-03) | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [VCO：扫频与原始相位](../validation/paper/COVERAGE.md#scope-l4-04) | 环回边界未验收 | 扫频误差超限 | 编译失败 | ✓ Q3 |

## 5. 复杂交互

| 能力与测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [实例隔离：双积分器复位](../validation/paper/COVERAGE.md#scope-l5-01-integral) | 复位误差超限 | 编译失败 | 误差超限 | ✓ Q3 |
| [实例隔离：双相位历史](../validation/paper/COVERAGE.md#scope-l5-01-phase) | 环回边界未验收 | 编译失败 | 编译失败 | ✓ Q3 |
| [非线性积分与滤波联合反馈](../validation/paper/COVERAGE.md#scope-l5-02) | ✓ Q3 | 误差超限 | ✓ Q3 | ✓ Q3 |
| [事件改变动态：线性反馈](../validation/paper/COVERAGE.md#scope-l5-03-linear) | ✓ Q3 | 初始化失败 | Q1 误差超限 | ✓ Q3 |
| [事件改变动态：Riccati 滤波](../validation/paper/COVERAGE.md#scope-l5-03-riccati) | ✓ Q3 | 初始化失败 | 误差超限 | ✓ Q3 |
| [近邻定时事件：原整链](../validation/paper/COVERAGE.md#scope-l5-04-chain) | ✓ 1 µV | 初始化失败 | ✓ 1µV | ✓ Q3 |
| [近邻定时事件：相邻浮点采样积分](../validation/paper/COVERAGE.md#scope-l5-04-adjacent) | 回调同刻 | 初始化失败 | 回调同刻 | ✓ Q3 |

表外需求和待验收项见[覆盖缺口](../validation/paper/COVERAGE.md#engineering-gap-audit)；原失败与旧成绩见[历史批次索引](../validation/paper/COVERAGE.md#先找到各批的原始成绩)。

<a id="engineering-status"></a>

## 6. 统一功能缺口与推进路线

本节是 R01、400 家族和现有 issue 的唯一功能状态与排期入口。Issue 保留原规格、讨论和执行历史，
只链接本节对应功能，不再分别维护一套当前缺口、优先级或路线。具体数学和接受边界仍由各功能合同负责。
更新功能条目时，同时补固定源码、原请求结果及合并状态；测试数量不代替原请求验收。

### 状态、版本与合并边界

- **已解决**：条目限定范围已通过实际验收，并已合入 main。范围之外的合法写法不自动获得支持。
- **部分完成**：已有实现或有限验收，但更广消费者、原请求或集成仍未完成。
- **待复验**：只有较早版本结果，或只有微例证据。未在选定最终版本运行，不能列为当前已解决或当前仍失败。
- **语义差异**：已经区分数学合同、实际后端回调和原 checker。保留原判定，单例决定不推广到其他模型。
- **暂停／范围外／外部待证**：需要单独范围决定、其他项目交付或外部证据，不因排期自动恢复。

2026-10-17 核对：输入修复 [#203](https://github.com/BucketSran/vaEVAS/pull/203)、
[#204](https://github.com/BucketSran/vaEVAS/pull/204)、[#206](https://github.com/BucketSran/vaEVAS/pull/206)
已合入 `main@49f24f0b`。[#208](https://github.com/BucketSran/vaEVAS/pull/208) 的行为验收固定于
`82284d97`，仍为未合并草稿。其 1860 项 Python、403 项 Rust 及全部已选择的 CI 项通过，
不表示 IR24 已进入 main，也不重标其他版本的实验。后续纯文档提交不改变该行为验收身份。

优先级按可观察结果排列：P0 核对已有错误输出和未决语义；P1 复验共享前置及修复有实际反例的有限功能；
P2 在前置成立后扩展复杂组合；P3 对已完成切片补共同资格与整体验收。各切片可独立完成验收，
不要求等所有 P2 功能完成才开展对应的 P3 取证。此路线不授权新的仿真、合并、解冻或宿主实现。

### 按具体功能推进

共同验收要求见[本节验收条件](#gap-acceptance)。表中验收列补充各功能必须区分的行为。

| 功能 | 当前状态与已解决范围 | 下一步范围、优先级与依赖 | 必须取得的验收结果 | 责任入口 |
| --- | --- | --- | --- | --- |
| <a id="gap-01"></a>GAP01 SCS 保存与源折点 | **已解决**：`save time`、同名电气节点、默认节点保存及已选源折点保存；#203 与此前 #183/#184 已合入。见[保存证据](../../experiments/backends/support/scs-save-time/README.md)。 | 维护回归；新增源形式与 options 另按真实模型选择，不把受限入口扩大为完整 Spectre 网表支持。 | 时间轴、节点列、折点、普通保存与 strobe 保存各自正确；未知设置仍明确处理。 | [#63](https://github.com/BucketSran/vaEVAS/issues/63) 已按受限范围关闭；新核心消费者由 GAP04/GAP05 承接。 |
| <a id="gap-02"></a>GAP02 ANSI 端口与实例绑定 | **已解决**：逐端口显式方向、electrical、一维范围及正文补 discipline，#204 已合入。见[端口证据](../../experiments/backends/support/ansi-ports/README.md)。 | P1 仅处理实际剩余语法；共享名字列表、更广结构不从本条继承支持。依赖原端口绑定与资源检查。 | ANSI 与 non-ANSI 等价，保留位序、参数范围、跨实例隔离和明确拒绝。 | [#65](https://github.com/BucketSran/vaEVAS/issues/65) |
| <a id="gap-03"></a>GAP03 Pulse 参数默认值 | **已解决**：仅缺省 delay 取 0，#206 已合入。见[源参数证据](../../experiments/backends/support/pulse-delay/README.md)。 | 维护回归；其他默认参数先核参考语义，不由 delay 规则类推。 | 缺省与显式零的物理输入等价；其他缺参、非法边沿及时间分辨率仍检查。 | #63 的输入维护；动态范围转 GAP04/GAP05。 |
| <a id="gap-04"></a>GAP04 精确物理源驱动 cross、保持 timer、transition | **部分完成，未合并**：IR24 有界物理 PWL、完整根分区、有限 transition 组合与采样证明；原23例checker仍22/23。审核发现B1的内部仿射guard投影遗漏已有限修复，见[B1收据](../../experiments/backends/support/source-shape/b1.json)和[固定证据](../../experiments/backends/support/source-shape/README.md)。 | P1 按112复验的实际拒绝选择有限消费者修复。非点值投影仍拒绝；集成是否进行另按授权，347转GAP09，不强造23/23。 | 物理曲线位于原误差带内，根、采样、历史、查询及失败回滚保持；原精度和预算不变。 | [#96](https://github.com/BucketSran/vaEVAS/issues/96)、[#119](https://github.com/BucketSran/vaEVAS/issues/119) |
| <a id="gap-05"></a>GAP05 源误差进入积分、微分、滤波、slew、delay | **部分完成，原67家族已复验**：普通幅度带可用于代数与固定timer；IR24仍不开放仅非零源误差的idt、ddt、laplace、slew、absdelay。原67与剩余45均已在同一release核执行，见[112结果](#replay112)。 | P1 按实际拒绝区分唯一物理曲线与仅幅度带，再选择消费者切片；P2 逐项补导数、根与历史误差传播。依赖GAP04，不能直接删除原拒绝。 | 独立误差包围必须覆盖实际物理量；放大、拐点、历史累计、复位及失败重试均受原预算约束。 | #96、#66、#119 |
| <a id="gap-06"></a>GAP06 事件算术、变量除法与统计数学 | **有限除法切片完成，未合并**：八例事件内实数除法／裁剪采样均通过独立递推，原checker为3通过、5不一致；实际Spectre原件8/8通过，严格根处复位差异及观察缺证保留，见[逐例验收](#gap06-sampling)。隔离gain统计数学另有[既有证据](../../experiments/backends/support/README.md#event-statistics)。 | P1 按剩余47拒绝选择下一切片；普通模拟非线性谓词8例及GAP05两例未纳入本次。位运算、初始化表达式等独立语言缺口分批处理。依赖类型、定义域与 GAP09 的事件读取合同。 | 顺序赋值、整型中间值、除零与数学域、未选分支结构、状态误差及下游放大正确；不能借观察者准入放行反馈。 | #65、#119 |
| <a id="gap-07"></a>GAP07 运行期循环、数组与跨事件索引 | **部分完成**：隔离观察事件循环及数组已合入；原 CDS 三条在固定v9通过原 checker 和实际有限配对。MUX 仅有索引、初态及保持目标子能力。见[CDS证据](../../experiments/backends/support/event-runtime-control/README.md#original-cds)。 | P1 维护 CDS 与有界语言回归；更广物理／混合事件循环按独立合同选择。MUX/F30 保持暂停，不能因 GAP04 已增强而自动恢复。 | 循环次数、退出变量、下标关系、取消／复位、整数溢出与整批回滚均正确；原 MUX 需独立完整验收。 | #65；物理历史由 #66/#96 协作。 |
| <a id="gap-08"></a>GAP08 连续历史、动态电压乘边沿及下游滤波 | **部分完成**：timing-0 原预算与 checker 通过；有限动态系数乘单 transition 及普通／中断后滤波已交付。同步两条完整执行，但原 checker 0/2。见[同步证据](../../experiments/backends/support/r01-sync-readout/README.md)。 | P1 处理P0核销后仍拒绝的原精度请求；P2 扩展状态系数、多父历史及反馈。同步严格阈值差异转 GAP09；依赖物理历史保持与完整采样误差。 | 非零旧历史、实际中断值、调用点与实例身份保留；额外查询不改变轨迹，晚失败可在同控制器重试。 | #66、#119、#96 |
| <a id="gap-09"></a>GAP09 cross 根处条件、近邻排序与查询不变性 | **P0及091/320已逐项归因，兼容差异与未支持项保留**：同步两例、400五例及091/320分别有原checker及独立根处赋值证据；091/320另补原件实际Spectre与回调对照，见[逐例结果](#diagnosis-091-320)。#119查询对仍拒绝，积分切换及相邻切点仍保守拒绝。GAP06另有五例严格根处复位差异，见[八例增量](#gap06-sampling)；347既定差异不变。 | P1 恢复可认证的近邻因果根、查询相位及宽根窗条件，再处理相邻浮点mode；分别保留原请求、失败与预算。不能把拒绝记成查询不变性修复，也不将347决定推广为模型豁免。 | 近邻根须证明身份、顺序与可用代表；成功请求须验证采样、未来历史、两侧查询和失败回退。原checker、精度与时间预算不变。 | #119、#96；自换向另归 GAP12/#70。 |
| <a id="gap-10"></a>GAP10 动态 $bound_step 与隐式积分控制 | **部分完成／原请求待复验**：已选 DAE 动态步长有两模型各33个实际参考点；不能据此宣称原12条工程阻塞全部恢复。见[步长证据](../../experiments/backends/implicit-step-bounds/README.md)。 | P1 先用固定集成核复验原工程请求，按活动条件与消费者分组。事件版本依赖 GAP11；无事件路径可独立验收。 | 实际接受推进遵守活动上限，非活动请求不误限制；非法值、切阶段、查询不变及回退有证据。 | #66、#119 |
| <a id="gap-11"></a>GAP11 DAE 事件重启、复位、ddt 与隐式 guard | **部分完成**：精确固定 timer 改 forcing／步长后的一致续算已交付；一般 cross、保持 timer、非精确窗口、reset/ddt 与代数约束跳参仍缺。见[续算证据](../../experiments/backends/implicit-event-restart/README.md)。 | P2 按一致重启→指定状态复位→ddt 跳变／脉冲边界→隐式 guard 推进，依赖 GAP10 和事件事务；每步分别验收。 | 重解一致代数根并保留无关物理状态；奇异、多根、初态不一致、约束跳参与晚失败分别有正反例。 | #96 的 C2/C5、#66 的已选切片。 |
| <a id="gap-12"></a>GAP12 双向自换向 cross | **部分完成，未结案**：已有独立返回根分析及实际 Spectre 诊断，尚无完整原模型接受／拒绝验收。 | P2 依赖 GAP09 的根身份与顺序、GAP08 的历史重启；先支持可分辨返回根，再明确不可分辨边界，不加统一死区。 | 原乘积 guard、两个方向、精确／非精确根、timer/PWL控制、查询不变和同控制器重试齐全。 | [#70](https://github.com/BucketSran/vaEVAS/issues/70) |
| <a id="gap-13"></a>GAP13 深层 delay/slew、非线性滤波直接通路与联合反馈 | **部分完成**：有限固定前馈已有交付；可变参数、多历史及更广反馈不由单算子或单边沿卡授予支持。 | P2 固定前馈历史→参数变化／深层组合→联合反馈与初始化；依赖 GAP08，涉及代数一致性时依赖 GAP11。 | 检查原关系和前向误差，历史所有权、拐点追赶、参数切换及反馈根唯一性，不只验证变换公式。 | #66 的 C3/C4 |
| <a id="gap-14"></a>GAP14 分析事件与更广语言结构 | **部分完成**：已选 initial_step、final_step 及有限控制流已有合同；above、last_crossing 和未选结构仍逐项开放。 | P2 依赖 GAP06/GAP07 的类型与执行义务，按真实模型分批定义生命周期与历史归属；不把 final_step 统计通过当作全部分析事件完成。 | 初始化、结束、重复叶、混合事件与历史读取有独立语义答案；保留资源、失败回退和实例隔离。 | #65 |
| <a id="gap-15"></a>GAP15 原请求总账与四后端共同资格 | **固定候选已复验，仍待共同资格**：`553eb83b` 的400原模型和71变体三档213位置已完整执行，见[本轮结果](#evaluation-400-71)。完整R01及四后端共同Q仍未闭合。 | P3 按已保留的拒绝、合同差异与缺证补齐验收；新修复另用执行身份，不能覆盖本批失败。依赖相应 GAP04–GAP14 切片。 | 原生观察、完整回调、配置生效、失败与未运行槽保留；开发样例不冒充独立确认集，有限配对不转授Q。 | #96、#119 |
| <a id="gap-16"></a>GAP16 Spectre 版本异常范围 | **外部待证**：EVAS 顺序赋值修复已交付；外部重复赋值异常的跨版本范围未知。 | 独立外部线，取得另一合法可用版本或厂商反馈后复核；不阻塞当前电压域修复。 | 同一未插桩模型、单因素设置及版本身份；同版本重复运行不算版本范围证据。 | [#16](https://github.com/BucketSran/vaEVAS/issues/16) |
| <a id="gap-17"></a>GAP17 ngspice/Xyce 宿主联合求解 | **独立工程线**：独立EVAS证据不授予宿主模式资格；连续VA开关试点也不等于事件托管已验收。 | 分别由原宿主任务推进，依赖真实宿主节点读取、贡献装配、接受／拒步回调与实例状态接口。 | Newton重复求值只提交一次，真实拒步重试保留事件及历史；默认LTE、transition、负载和观察网格各自验证。 | [#176](https://github.com/BucketSran/vaEVAS/issues/176)、[#181](https://github.com/BucketSran/vaEVAS/issues/181)；试点[#200](https://github.com/BucketSran/vaEVAS/issues/200)。 |
| <a id="gap-18"></a>GAP18 性能与无损复用 | **独立候选线**：P03/P05等保留候选及各自CI，不计作本轮正确性缺口关闭。 | 按原所有者、范围和授权处理候选；先固定功能和精度，再做有原因的性能测量，不自动恢复暂停工作。 | 工作量与设置相同，结果或认证包围保持，端到端重复测量成立；单次耗时不证明加速。 | [#138](https://github.com/BucketSran/vaEVAS/issues/138) |
| <a id="gap-19"></a>GAP19 离散滤波、随机／噪声、表／文件与分析辅助 | **未选扩展，义务保留**：#66 原目录中的 zi 类离散滤波、随机／噪声、表／文件任务及 AC/noise/analysis 辅助没有由本轮有限数学和连续滤波交付覆盖。 | P2 按真实模型分别选切片，先定义采样时钟、随机复现、外部文件身份及分析生命周期；依赖相应类型、历史和分析合同。未选条目继续由#66负责，不以标签移交代替接收。 | 每类有独立答案或不变量、初始化与失败边界、参数和实例隔离；随机行为固定种子与统计判据，不能直接套用确定性电压门槛。 | #66；分析事件边界另见GAP14/#65。 |
| <a id="gap-20"></a>GAP20 旧 default_transition 与调用兼容 | **待复验／语义待核**：400旧基线有10个 default_transition 首阻塞家族；旧CLI和非地参考源也有范围差异，没有随三项入口修复完成。 | P1 先核对固定旧版源码、标准含义与当前公共接口，再决定保留兼容还是明确拒绝。依赖GAP01/GAP02；这10个历史家族不计入下述112个复验集合。 | 原样与适配派生分别保留；不把旧专用宏当标准，也不通过改VA或隐藏默认值取得原题通过。 | #65的语言边界；整体原请求分类由#96维护。 |
| <a id="gap-21"></a>GAP21 其余数学函数与连续滤波表示 | **部分完成／未选范围待核销**：已有 exp、ln、cos 等函数和有限 laplace_np 转换不重复立项；#66 原目录中 limexp 等其余数学语义及更广 laplace_np/zd/zp、复根形式仍须逐项裁决。 | P2 按真实模型选择函数或滤波形式，先核现有实现与独立证据，再决定补实现或具名移交。涉及直接通路与反馈时依赖GAP13。 | 函数定义域、溢出、不连续点、导数和误差界明确；limexp的迭代限制与最终函数分开，滤波转换保持系数、复根约束、阶数与初态。 | #66；未交付范围在本项保留到正式接收。 |

<a id="p0-originals"></a>

### P0原反例逐项结果

2026-10-17在同一行为源码`82284d97`上核销；文档父提交为`c2e45d8f`，未合并。
原冻结debug核的同步c0两次达到120秒限制，失败保留；同源码独立release构建在原预算内完成两例，
c0约53.2秒、core-boundary约7.9秒，各9031行，原checker仍0/2。构建配置不同，不能据此声称算法加速或覆盖debug失败。
[逐项数学、原判据与构建收据](../../experiments/backends/support/source-shape/p0.json)保存独立分类，原始输出为local-only。

| 原请求 | 当前判定与具体依据 | 尚需满足的验收 |
| --- | --- | --- |
| 同步`r01-integrate-sync/c0` | release完整执行；原checker FAIL。10次DUT事件的精确PWL根处`frame_valid/acquired`赋值相符；严格`track>vth`在开窗根处为假。 | 工程兼容差异保留。实际Spectre同源观察回调读正guard，原checker通过；不宣称两后端严格一致。 |
| 同步`core-boundary` | release完整执行；原checker FAIL。独立核对10次DUT事件，四路held最大误差约`1.11e-16 V`，valid/dout仍不同。 | 同源实际参考按原身份复用，保留整题失败与参考资格边界。 |
| 400/107 | 3次事件的独立位权解码与根处输出相符；触发位的严格`>`为假，原checker FAIL。 | 保留原双极DAC的兼容差异；未新增该例实际Spectre执行。 |
| 400/157 | 3次事件的独立折叠码与`out_value`相符；根处严格阈值选路与原checker不同。 | 原checker FAIL保留，不用其他DAC的结果代替。 |
| 400/164 | 2次事件、7位加权和独立核对通过；同根触发的输入等于阈值，严格`>`不置位。 | 原checker FAIL保留，不能改成根后输入解码。 |
| 400/168 | 8次事件的独立offset及trim和相符，根处触发位不加权。 | 原checker FAIL保留，其他未触发输入各自按精确PWL判断。 |
| 400/185 | 7次事件的独立移位、复位及SDI插入相符；根处`sck_level=0`使scko三项失败。 | 原checker FAIL及其193项检查保留；不能将移位已执行误报为整个SPI请求通过。 |
| #119原查询对 | 原IR22按版本拒绝；原VA重编译IR24后，稀疏请求`unsupported_cross`，密查询`event_resolution`。两数学根相差约`2.4168e-17 s`，最近binary64相同。 | **未支持**。须证明因果根顺序及查询相位，成功执行两请求后才可验查询不变性。旧2.7881 ps移动及F25/F26身份保留，不记作已修复。 |
| #119高增益采样 | 原`q=1e6*u`、平方积分请求通过；终点相对独立`sqrt(2)`答案误差约`6.44e-4 V`，在原`2e7 V + 1e-10相对`预算内。额外查询事件完全相同。 | 此有限原例已恢复；原`1e-6 V`绝对负控明确`waveform_accuracy`，不得推广为任意高增益支持。 |
| #119线性积分切换 | 原宽窗条件`u>1.414214`返回`event_condition`，不发布波形。 | **合理拒绝，恢复未完成**。细化根盒后须独立验证`tau+3(t-tau)`及原预算，不能采用旧post-root后继作现行合同。 |
| #119非线性积分切换 | 同一原条件返回`event_condition`。 | **合理拒绝，恢复未完成**。须独立验证`1/(1+tau+3(t-tau))`及旧历史保持。 |
| #119相邻切点线性两种谓词 | 原直谓词与嵌套谓词均`condition_precision`，没有可表示的mode内部点。 | **未支持**。精确面积为1，须有覆盖整个开区间的证明后才能接受。 |
| #119相邻切点非线性两种谓词 | 两请求均`condition_precision`，保留原预算和拒绝。 | **未支持**。精确面积为`pi/4`，不能冻结为端点值或套用线性开侧证明。 |

上述分类分别依赖原程序与数学合同，不来自347的单例决定。相关69项回归在debug与release分别通过；
七个机制请求在release的完整响应与原debug证据相同，复用已执行实际Spectre及独立答案，不新增远端执行或Q成绩。

### 三条来源的去重与复验范围

| 来源 | 固定结果 | 当前必须保留的未知 |
| --- | --- | --- |
| R01原70请求 | `efd17ed6` 上23条原checker通过、47条拒绝。后续gain、CDS、timing及动态切片各自有固定证据，不能直接相加。 | 最终版本70条未全量复验；旧47是首阻塞分组，不是当前剩余漏洞数。九条旧输入配对失败另有观察插值归因，原14/23共同输入输出成绩不改写。 |
| 400家族基线 | `8c3ef9ee` 上51输入失败、166前端失败、108内核拒绝、75完成；其中旧checker70通过、5不一致。 | 旧checker尚未完整绑定r53正式认证链；不是当前版本的总通过率。原始完整400探测保留为local-only，不能声称公开完整重放。 |
| 三入口修复 | save time 20、ANSI 26、pulse delay 22，共68个不同家族。分阶段26个家族曾通过旧checker。 | 26来自不同版本，其中001、047、089、269仅有较早通过；早期ANSI/Pulse清理失败收据保留，不据后续进程快照改成清理成功。 |
| #208原23复验 | 23个是上述68的子集；debug及同源码release均完整执行、22个旧checker通过、23个清理确认，完整响应相同。347两处差异另列GAP09。 | 另外45个入口家族已纳入下述112复验；其旧4通过/41失败仅保留为历史，不能代替当前结果。 |
| 本轮受影响复验 | 原400中首阻塞为源组合的67个，与上述68个不相交。67加剩余45，去重为112个；全部按原输入、checker、精度和预算执行。 | 112是固定分母，不是112个缺陷或通过承诺。初验55通过、2不一致、55拒绝；[GAP06增量](#gap06-sampling)后为58通过、7不一致、47拒绝。没有启动完整远端矩阵。 |

旧41个失败包括事件变量除法8、非仿射谓词8、语法13、其他编译3、暂态组合3、初始化事件3、
整数算术1、事件分辨率1和资源预算1；这是历史首阻塞分组。当前逐例诊断在[112收据](../../experiments/backends/support/source-shape/replay112.json)，不将旧分组改写为当前剩余缺陷数。

<a id="replay112"></a>

### 固定112家族复验结果

最新GAP06候选为58个旧checker通过、7个观察不一致、47个拒绝，全部112例清理确认，见[八例增量](#gap06-sampling)。下表保留初验身份及原判定。

同一行为源码`82284d97`及P0冻结release核执行全部112个原请求。57例完成仿真，其中55例通过旧checker，
091、320两例观察不一致；另55例拒绝。零超时、零未运行、112例guardian清理确认。
原checker尚未完整绑定r53正式认证链，此处不是400家族新通过率或正式Q成绩。

| 原VA消费者分组 | 固定家族 | 旧checker通过 | 观察不一致 | 输入或前端拒绝 | 内核未支持 | 认证拒绝 | 编译资源上限 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cross与transition | 89 | 52 | 2 | 21 | 5 | 8 | 1 |
| cross的其他消费者 | 2 | 1 | 0 | 1 | 0 | 0 | 0 |
| timer与transition | 5 | 1 | 0 | 2 | 1 | 1 | 0 |
| 仅transition | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| 连续历史算子 | 4 | 0 | 0 | 1 | 3 | 0 | 0 |
| 其他 | 11 | 1 | 0 | 10 | 0 | 0 | 0 |
| 合计 | 112 | 55 | 2 | 36 | 9 | 9 | 1 |

分组依据是原VA的算子调用名称，仅用于试跑和执行顺序，不证明组合准入。
[每例原判定、完整失败分母与身份](../../experiments/backends/support/source-shape/replay112.json)保留输入、核、checker、normalization与guardian哈希；完整输出仍为local-only。
输入或前端拒绝也可能是当前语言能力限制，不能统称原模型非法；无波形的请求不计作已观察到数值错误。

091、320已按下述原程序、完整事件状态和独立数学逐例归因；两例原失败均保留。
认证拒绝的原电压/相位预算不放宽；语言、初始化、仅幅度带历史和资源边界分别由原GAP承接。

<a id="diagnosis-091-320"></a>

### 091、320逐例归因

两例沿用上述冻结源和核，原checker、normalization、精度及120/150秒预算未改。
独立Fraction递推核对全部160次事件提交、4641行共47414个保存量，均在原电压预算内；
最大事件状态误差分别约`7.18e-15 V`、`1.10e-16 V`。该有限原请求中未发现独立EVAS缺陷。
[数学、原判据及实际参考收据](../../experiments/backends/support/source-shape/diagnosis-091-320.json)保留各例身份和观察资格。

| 原请求 | 语义差异的具体传播 | 实际参考与观察缺证 |
| --- | --- | --- |
| 091斩波差分放大器 | 首个有效上升根4.025 ns处`chop_clk=0.45 V`，VA严格`>`为假，polarity取−1，sample为0.06 V；下游延迟strobe使baseband成为0.015 V，voutp为0.4575 V、residual为−0.105 V。原checker按边沿方向取+1，期望0.4725 V、−0.075 V；首次在4.480 ns报错。全部125次事件及3637行符合原根处递推。 | 原deck实际Spectre通过原checker；观察副本在4.025012500027778 ns记录guard约`+0.0002250005 V`、polarity=+1。68次chop、55次LP回调递推相符；两个控制清零块及initial未逐条插桩，不能声称完整回调资格。 |
| 320码相关DAC缓冲器 | 8.05 ns的code2上升根，触发位等于阈值而不置位，target保持0；随后三次根依次为0.24、0.72、0.78 V。62.05 ns重使能根处`enable<=vth`仍成立，target清零并保持。原checker用根后时钟保存行的完整码字期望target，进而产生metric及边沿更新差异。全部35次事件及1004行符合原根处递推。 | 原deck实际Spectre通过原checker，仍保留允许范围内3项target误差；回调读正guard，置入新位，重使能后target为0.9 V。含初始DAC在内36条回调递推相符。 |

实际参考共4次：两个原件和两个仅加回调日志的独立观察副本；逐值比较各副本与原件的全部原生保存行完全相同。
所有执行按原deck设置和既有90秒、4 GiB、32 MiB、单线程、30秒license等待上限完成并确认清理。
091实际reltol=1e-4、vabstol=1e-6 V、gear2only；320实际reltol=1e-3、vabstol=1e-6 V、traponly。
两者均保持原maxstep。旧设置读取器不识别`1 uV`，其4项分析失败保留；本地另从原日志逐行读出单位，未重跑或改设置。
原默认格式PSF没有完整逐点误差证书，不以checker通过、日志位数或回调对照授予共同Q。
两例因此归为有限语义兼容差异，原失败和剩余观察缺证分别保留，未改VA或EVAS行为；347的`te=tau`不变。

另按审核转交处理的B1是独立实现缺陷：`z=2u`的内部guard附等价shape后原本被拒绝。
修复复用已认证点值投影，不改变上述两例的根处语义。新release核重新执行固定112家族，
全部状态、原checker完整note及拒绝诊断不变，57份完整响应相同；55通过、2失败、55拒绝及112清理分母保持。
原23家族也按原预算全部复验，23份完整响应均相同；七项机制请求复验后复用原实际参考。
B1另有一项新增实际Spectre，285个共享原生时刻与独立线性答案相符；原生误差与共同Q资格仍未闭合，
见[B1完整有限收据](../../experiments/backends/support/source-shape/b1.json)。这些修复及证据继续留在草稿#208，未合并。


<a id="gap06-sampling"></a>

### GAP06有限事件除法与裁剪采样

本切片固定261、262、263、264、267、271、275、276，原VA、checker、normalization、精度及120秒内核／150秒worker预算不变。
前端现在单独降低物理事件标量除法与选择，不借隔离观察数学准入；同刻贡献选择预演使用实际驱动值，避免把正分母当作零。
完整原树依赖、分母区间含零拒绝、状态误差与下游电压认证保持。[固定收据](../../experiments/backends/support/source-shape/gap06.json)和[完整输入](../../experiments/backends/support/source-shape/gap06-inputs.json)保留身份与限制。

| 原家族 | EVAS原checker | 独立原程序核对与实际参考 |
| --- | --- | --- |
| 261、262、263、264、267 | 0/5通过，原失败保留 | 9.025 ns异步复位数学根处`rst=vth`，原`rst>vth`为假，事件仍执行有效采样。9.145 ns原checker要求清零，261/262/263/267的metric相差0.39 V，264的flag相差0.9 V。实际Spectre原件均通过checker；根后读取能解释差异，但本八例未插桩回调，具体回调侧别与误差仍缺证。 |
| 271、275、276 | 3/3通过 | 计数率与归一化递推符合原程序。275/276也有根处复位后的参考差异，原checker允许的观察与完整波形一致性是不同要求，不能据3/3宣称全时域对齐。 |

八例124次完整事件状态、172706个原保存量均符合独立Fraction源／根／递推／线性边沿答案，debug与release完整响应相同。
八个原deck新增实际Spectre执行均成功、checker为8/8；固定73个稳定观察按预定10 µV门槛符合独立采样答案。
所有原生波形中的边沿与复位差异另列完整分母，未平移时间轴或删除原checker窗口。
默认PSF／回调误差和共同Q未认证；旧读取器对单位及同名`time`列的分析错误保留，本地按TRACE列定义重读，没有重跑或修改精度。

同一候选重跑全部112家族，八例由拒绝变为3通过、5不一致，其余104例判定及57份成功响应保持。
原23家族的完整响应也相同，仍22/23通过，347两处失败和`te=tau`决定不变；135例均清理确认。
普通连续除法、未隔离非线性电反馈和普通模拟非线性谓词不由本切片扩展，47拒绝继续按原GAP处理。PR208保持未合并草稿，F30/#131冻结。

<details>
<summary>本轮112个家族的固定ID</summary>

原67个源组合家族：002、004、006、008、010、040、043、044、051、055、065、071、084、091、100、103、104、106、109、117、178、184、191、198、199、200、204、205、206、207、208、209、210、213、214、284、293、294、306、308、309、310、311、312、320、321、322、327、331、341、342、345、352、353、356、357、361、363、367、375、376、379、382、394、395、397、399。

本轮补验的45个入口家族：001、012、017、026、036、047、048、049、056、057、058、072、076、077、078、079、081、088、089、097、098、261、262、263、264、265、266、267、268、269、271、274、275、276、277、278、279、280、299、300、301、302、348、349、355。

</details>

<a id="evaluation-400-71"></a>

### 固定候选400原模型与71变体三档复验

本轮 DUT 固定为 PR208 的 `553eb83bbaaa10e867abcc7b0d1e4cf26c75adb5`，没有中途修改源码、checker、normalization、精度、采样网格或预算。
[逐例收据](../../experiments/backends/support/source-shape/evaluation-400-71.json)分列两套分母、原始判定、独立判据、拒绝诊断、缺证及来源身份。
400原模型沿用已验收的macOS release核 `ce8ad6db`；213位置使用同一源码在Linux重新构建并于批前冻结的核 `0c7d22a2`。两套核不能当作同一二进制或同一工具链。
完整模型快照、波形、响应和执行日志为local-only，公开收据不构成完整原件下载。

400个原v4 r53 gold模型与trusted replay台架全部执行并确认guardian清理，保持每例120秒内核、150秒worker预算。196例完成，原checker为181通过、15不一致，另204例拒绝；没有超时或未运行。
204个拒绝分为162个输入或前端障碍、24个认证拒绝、16个明确支持限制，以及101、314两个尚未定位原因的源历史推进拒绝。前端拒绝不证明原模型非法，认证拒绝也不证明输出数值错误。
旧checker未完整绑定r53正式认证链，181不是新版正式benchmark成绩，也不是盲测通过率。旧版本的全部失败及51个输入障碍原件保留。

| 原checker不一致家族 | 本轮已有证据与保留限制 |
| --- | --- |
| 107、157、164、168 | 独立Fraction求根及全部事件赋值符合原VA的严格阈值比较。旧checker按后续稳定输入重新解码，与根处更新后保持的状态不同。没有新增实际Spectre回调观察。 |
| 185 | 六次时钟根均为0.45 V，原 `sck_level = V(scki) > 0.45` 为假；旧checker在上升沿后要求scko为0.9 V。证据限于该状态与输出。 |
| 260、261、262、263、264、267 | 严格根处复位条件与旧checker清零预期不同。260新增17次事件及23562个保存量的独立递推核对；其余复用完整响应相同的GAP06证据。回调侧别与全原生观察的缺证保持。 |
| 091、320 | 完整响应与既有独立递推、实际参考取证时相同；根处严格条件与后侧回调差异沿用[原归因](#diagnosis-091-320)。不扩大原观察资格。 |
| 347 | 原两处不一致和 `te=tau` 决定保持，完整响应未变，仍按GAP09处理。 |
| 075 | 135.5 ns至136 ns两个保存点横跨完整500 ps transition，输出差约0.4975 V。旧平滑判据只检查相邻样本差不超过0.40 V；361次timer峰值递推相符，但没有边沿内部点，不能据此证明跳变或全时域平滑。 |

上述14个回调或合同差异及1个观察缺证均保留原checker FAIL，没有改成通过。它们尚未提供实现输出错误的证据，也不替204个拒绝消除未知原因。

71个独立变体属于44组，基础132位置与组合81位置全部按原Q1=base、Q2=both、Q3=deep执行。原Linux执行器的90秒阶段、4 GiB地址空间、32 MiB单文件、256 MiB条件目录和单线程控制保持。
12个独立pilot先核对接线、设置读回、导出、清单与清理，再执行完整213位置。207位置取得波形，EC23与EC24各三档拒绝；全部213清理确认，无超时或未运行。

| 原目标档位 | 独立判据通过 | 证据不足 | 执行拒绝 | 44组中全部必需变体通过的组数 |
| --- | ---: | ---: | ---: | ---: |
| Q1 | 39 | 30 | 2 | 27 |
| Q2 | 39 | 30 | 2 | 27 |
| Q3 | 37 | 32 | 2 | 25 |
| 合计位置 | 115 | 92 | 6 | 各档分别计组，不合并为132个独立组 |

92个缺证保留原原因，包括精确输入导出、完整合法回调窗、DC与瞬态相位、跨通道回调次序、参考未定义及时间或导出不确定度。EC05、EC22仍是支持探针，不因取得波形而授予资格。
EC23三档拒绝来自动态cross符号认证，EC24三档明确拒绝事件参数改变隐式代数约束后的分支重选。没有用拒绝结果计算波形误差；本批没有已被原独立判据判为 `numerical_error` 或 `behavior_error` 的位置，未知项仍未知。

Linux新构建另通过401项内核及2项IR测试，1项忽略；首次离线缺少锁定依赖的未启动尝试保留。原1869项Python与同源码macOS验收沿用，不宣称重新执行。
本批未新增Spectre或四后端852位置矩阵，也未执行完整R01的70条件。结果只适用于这个未合并候选与原开发合同，不授予四后端共同Q或完整工程支持。F30/#131冻结，PR208继续草稿、不合并。

### 已关闭项与保留边界

[#62](https://github.com/BucketSran/vaEVAS/issues/62)关闭设计和实施责任移交，不表示C1–C5全部实现；
[#63](https://github.com/BucketSran/vaEVAS/issues/63)关闭受限输入适配，其核心消费者由GAP04/GAP05承接。
[#64](https://github.com/BucketSran/vaEVAS/issues/64)的诊断与外部消费、
[#67](https://github.com/BucketSran/vaEVAS/issues/67)的配套构建／身份／产物已完成各自验收。
[#68](https://github.com/BucketSran/vaEVAS/issues/68)以不纳入计划关闭，电流、KCL、R/C不因此获得实现。
F30与[PR #131](https://github.com/BucketSran/vaEVAS/pull/131)保持冻结，规划条目和共享能力进展不构成解冻授权。

<a id="gap-acceptance"></a>

### 各功能的验收与更新条件

1. 固定原VA、刺激、初态、checker、normalization、容差及每例预算，分别记录编译、完整执行和原判据结果。
2. 先写独立数学或语义答案，并保留正例、真正不确定负例、等价写法、查询不变及同控制器失败回退。
3. 对受影响行为取得实际Spectre证据，或明确固定身份且适用的复用依据；请求设置与实际生效值分别记录。
4. 只改有证据的最小共同机制。修掉首阻塞后回到完整原请求，新的失败仍算未完成，保留原分母。
5. 每个切片在同一待验收源码／内核上完成相关回归、独立审查及CI；合并和发布状态另列。微例、单次速度和有限配对不替代整题或共同Q。
6. 当前功能状态、优先级、依赖和下一步只更新本节。Issue只保留对应条目链接、关闭范围及原规格历史；证据包保留原执行身份，不随路线改写。

P0逐项核销、固定112家族复验及091/320逐例归因已完成，仍未支持的原义务保持。
GAP06有限除法八例已独立验收；后续按剩余47拒绝选择GAP05/GAP06等有限切片；每项仍需独立行为答案与原预算验收。
DAE按GAP10→GAP11推进，历史反馈按GAP08→GAP13推进，自换向由GAP09/GAP08→GAP12承接。
每个已完成切片分别进入GAP15验收。GAP16–GAP18保留独立负责人和外部依赖，不并入当前源码修复队列。

<!-- ci:progress:start -->
v4 已有固定版本的 400 家族首阻塞探测，分类及推进顺序见[修复顺序](development/COMPARISON.md#repair-priority)。旧 checker 复核仅供定位，不是正式 benchmark 成绩。
<!-- ci:progress:end -->

原请求、独立控制和共同 Q 结论的更新条件见[每项修复与比较的验收](../validation/paper/COVERAGE.md#每项修复与每行比较一起验收)。
