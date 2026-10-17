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
| <a id="gap-04"></a>GAP04 精确物理源驱动 cross、保持 timer、transition | **部分完成，未合并**：IR24 有界物理 PWL、完整根分区、有限 transition 组合与采样证明；#208 最终原23例完整执行，原 checker 22/23。见[固定证据](../../experiments/backends/support/source-shape/README.md)。 | P1 先固定待验收版本，再按消费者扩展原请求复验。集成是否进行另按授权；347 转 GAP09，不强造23/23。 | 物理曲线位于原误差带内，根、采样、历史、查询及失败回滚保持；原精度和预算不变。 | [#96](https://github.com/BucketSran/vaEVAS/issues/96)、[#119](https://github.com/BucketSran/vaEVAS/issues/119) |
| <a id="gap-05"></a>GAP05 源误差进入积分、微分、滤波、slew、delay | **部分完成／待复验**：普通幅度带可用于代数与固定 timer；IR24 的有限扩展不开放非零源误差的 idt、ddt、laplace、slew、absdelay。原400中的67个源组合家族未在IR24重放。 | P1 先区分唯一物理曲线和仅幅度带，按消费者试跑；P2 再逐个补导数、根与历史误差传播。依赖 GAP04，不直接删除原拒绝。 | 独立误差包围必须覆盖实际物理量；放大、拐点、历史累计、复位及失败重试均受原预算约束。 | #96、#66、#119 |
| <a id="gap-06"></a>GAP06 事件算术、变量除法与统计数学 | **部分完成**：隔离统计数学已使原 gain 三条通过 checker 和实际有限配对；IR24 另有有限源／保持状态算术。见[统计证据](../../experiments/backends/support/README.md#event-statistics)。 | P1 复验原变量除法与非仿射分支家族，逐例区分隔离观察者和物理反馈；位运算、初始化表达式等独立语言缺口分批处理。依赖类型、定义域与 GAP09 的事件读取合同。 | 顺序赋值、整型中间值、除零与数学域、未选分支结构、状态误差及下游放大正确；不能借观察者准入放行反馈。 | #65、#119 |
| <a id="gap-07"></a>GAP07 运行期循环、数组与跨事件索引 | **部分完成**：隔离观察事件循环及数组已合入；原 CDS 三条在固定v9通过原 checker 和实际有限配对。MUX 仅有索引、初态及保持目标子能力。见[CDS证据](../../experiments/backends/support/event-runtime-control/README.md#original-cds)。 | P1 维护 CDS 与有界语言回归；更广物理／混合事件循环按独立合同选择。MUX/F30 保持暂停，不能因 GAP04 已增强而自动恢复。 | 循环次数、退出变量、下标关系、取消／复位、整数溢出与整批回滚均正确；原 MUX 需独立完整验收。 | #65；物理历史由 #66/#96 协作。 |
| <a id="gap-08"></a>GAP08 连续历史、动态电压乘边沿及下游滤波 | **部分完成**：timing-0 原预算与 checker 通过；有限动态系数乘单 transition 及普通／中断后滤波已交付。同步两条完整执行，但原 checker 0/2。见[同步证据](../../experiments/backends/support/r01-sync-readout/README.md)。 | P1 先核销原请求与旧精度反例；P2 扩展状态系数、多父历史及反馈。同步严格阈值差异转 GAP09；依赖物理历史保持与完整采样误差。 | 非零旧历史、实际中断值、调用点与实例身份保留；额外查询不改变轨迹，晚失败可在同控制器重试。 | #66、#119、#96 |
| <a id="gap-09"></a>GAP09 cross 根处条件、近邻排序与查询不变性 | **语义差异／待复验**：347 的精确根与 Spectre 晚回调差异已证实并按用户决定保留；同步0/2有同类敏感写法。400旧失败107、157、164、168、185尚未逐项归因。#119旧查询移动回调和高增益反例尚需当前版核销。 | **P0** 分别冻结数学读取侧、实际回调及 checker 观察要求。近邻根只有独立证明与可用代表时刻才执行。347 的决定不泛化为其他模型豁免。 | 每个原反例独立区分真实缺陷、语义差异和观察缺证；高增益、两侧查询、同根／异根及原时间预算均验收。 | #119、#96；自换向另归 GAP12/#70。 |
| <a id="gap-10"></a>GAP10 动态 $bound_step 与隐式积分控制 | **部分完成／原请求待复验**：已选 DAE 动态步长有两模型各33个实际参考点；不能据此宣称原12条工程阻塞全部恢复。见[步长证据](../../experiments/backends/implicit-step-bounds/README.md)。 | P1 先用固定集成核复验原工程请求，按活动条件与消费者分组。事件版本依赖 GAP11；无事件路径可独立验收。 | 实际接受推进遵守活动上限，非活动请求不误限制；非法值、切阶段、查询不变及回退有证据。 | #66、#119 |
| <a id="gap-11"></a>GAP11 DAE 事件重启、复位、ddt 与隐式 guard | **部分完成**：精确固定 timer 改 forcing／步长后的一致续算已交付；一般 cross、保持 timer、非精确窗口、reset/ddt 与代数约束跳参仍缺。见[续算证据](../../experiments/backends/implicit-event-restart/README.md)。 | P2 按一致重启→指定状态复位→ddt 跳变／脉冲边界→隐式 guard 推进，依赖 GAP10 和事件事务；每步分别验收。 | 重解一致代数根并保留无关物理状态；奇异、多根、初态不一致、约束跳参与晚失败分别有正反例。 | #96 的 C2/C5、#66 的已选切片。 |
| <a id="gap-12"></a>GAP12 双向自换向 cross | **部分完成，未结案**：已有独立返回根分析及实际 Spectre 诊断，尚无完整原模型接受／拒绝验收。 | P2 依赖 GAP09 的根身份与顺序、GAP08 的历史重启；先支持可分辨返回根，再明确不可分辨边界，不加统一死区。 | 原乘积 guard、两个方向、精确／非精确根、timer/PWL控制、查询不变和同控制器重试齐全。 | [#70](https://github.com/BucketSran/vaEVAS/issues/70) |
| <a id="gap-13"></a>GAP13 深层 delay/slew、非线性滤波直接通路与联合反馈 | **部分完成**：有限固定前馈已有交付；可变参数、多历史及更广反馈不由单算子或单边沿卡授予支持。 | P2 固定前馈历史→参数变化／深层组合→联合反馈与初始化；依赖 GAP08，涉及代数一致性时依赖 GAP11。 | 检查原关系和前向误差，历史所有权、拐点追赶、参数切换及反馈根唯一性，不只验证变换公式。 | #66 的 C3/C4 |
| <a id="gap-14"></a>GAP14 分析事件与更广语言结构 | **部分完成**：已选 initial_step、final_step 及有限控制流已有合同；above、last_crossing 和未选结构仍逐项开放。 | P2 依赖 GAP06/GAP07 的类型与执行义务，按真实模型分批定义生命周期与历史归属；不把 final_step 统计通过当作全部分析事件完成。 | 初始化、结束、重复叶、混合事件与历史读取有独立语义答案；保留资源、失败回退和实例隔离。 | #65 |
| <a id="gap-15"></a>GAP15 原请求总账与四后端共同资格 | **待复验／待补证**：已有具名有限交付；当前版完整R01、400及新增能力共同Q仍未闭合。 | P3 对每个已完成切片固定独立卡、单位、判据及配置并校准；稳定版本再做原请求总账。依赖相应 GAP04–GAP14 切片，不等待所有扩展。 | 原生观察、完整回调、配置生效、失败与未运行槽保留；开发样例不冒充独立确认集，有限配对不转授Q。 | #96、#119 |
| <a id="gap-16"></a>GAP16 Spectre 版本异常范围 | **外部待证**：EVAS 顺序赋值修复已交付；外部重复赋值异常的跨版本范围未知。 | 独立外部线，取得另一合法可用版本或厂商反馈后复核；不阻塞当前电压域修复。 | 同一未插桩模型、单因素设置及版本身份；同版本重复运行不算版本范围证据。 | [#16](https://github.com/BucketSran/vaEVAS/issues/16) |
| <a id="gap-17"></a>GAP17 ngspice/Xyce 宿主联合求解 | **独立工程线**：独立EVAS证据不授予宿主模式资格；连续VA开关试点也不等于事件托管已验收。 | 分别由原宿主任务推进，依赖真实宿主节点读取、贡献装配、接受／拒步回调与实例状态接口。 | Newton重复求值只提交一次，真实拒步重试保留事件及历史；默认LTE、transition、负载和观察网格各自验证。 | [#176](https://github.com/BucketSran/vaEVAS/issues/176)、[#181](https://github.com/BucketSran/vaEVAS/issues/181)；试点[#200](https://github.com/BucketSran/vaEVAS/issues/200)。 |
| <a id="gap-18"></a>GAP18 性能与无损复用 | **独立候选线**：P03/P05等保留候选及各自CI，不计作本轮正确性缺口关闭。 | 按原所有者、范围和授权处理候选；先固定功能和精度，再做有原因的性能测量，不自动恢复暂停工作。 | 工作量与设置相同，结果或认证包围保持，端到端重复测量成立；单次耗时不证明加速。 | [#138](https://github.com/BucketSran/vaEVAS/issues/138) |
| <a id="gap-19"></a>GAP19 离散滤波、随机／噪声、表／文件与分析辅助 | **未选扩展，义务保留**：#66 原目录中的 zi 类离散滤波、随机／噪声、表／文件任务及 AC/noise/analysis 辅助没有由本轮有限数学和连续滤波交付覆盖。 | P2 按真实模型分别选切片，先定义采样时钟、随机复现、外部文件身份及分析生命周期；依赖相应类型、历史和分析合同。未选条目继续由#66负责，不以标签移交代替接收。 | 每类有独立答案或不变量、初始化与失败边界、参数和实例隔离；随机行为固定种子与统计判据，不能直接套用确定性电压门槛。 | #66；分析事件边界另见GAP14/#65。 |
| <a id="gap-20"></a>GAP20 旧 default_transition 与调用兼容 | **待复验／语义待核**：400旧基线有10个 default_transition 首阻塞家族；旧CLI和非地参考源也有范围差异，没有随三项入口修复完成。 | P1 先核对固定旧版源码、标准含义与当前公共接口，再决定保留兼容还是明确拒绝。依赖GAP01/GAP02；这10个历史家族不计入下述112个复验集合。 | 原样与适配派生分别保留；不把旧专用宏当标准，也不通过改VA或隐藏默认值取得原题通过。 | #65的语言边界；整体原请求分类由#96维护。 |
| <a id="gap-21"></a>GAP21 其余数学函数与连续滤波表示 | **部分完成／未选范围待核销**：已有 exp、ln、cos 等函数和有限 laplace_np 转换不重复立项；#66 原目录中 limexp 等其余数学语义及更广 laplace_np/zd/zp、复根形式仍须逐项裁决。 | P2 按真实模型选择函数或滤波形式，先核现有实现与独立证据，再决定补实现或具名移交。涉及直接通路与反馈时依赖GAP13。 | 函数定义域、溢出、不连续点、导数和误差界明确；limexp的迭代限制与最终函数分开，滤波转换保持系数、复根约束、阶数与初态。 | #66；未交付范围在本项保留到正式接收。 |

### 三条来源的去重与复验范围

| 来源 | 固定结果 | 当前必须保留的未知 |
| --- | --- | --- |
| R01原70请求 | `efd17ed6` 上23条原checker通过、47条拒绝。后续gain、CDS、timing及动态切片各自有固定证据，不能直接相加。 | 最终版本70条未全量复验；旧47是首阻塞分组，不是当前剩余漏洞数。九条旧输入配对失败另有观察插值归因，原14/23共同输入输出成绩不改写。 |
| 400家族基线 | `8c3ef9ee` 上51输入失败、166前端失败、108内核拒绝、75完成；其中旧checker70通过、5不一致。 | 旧checker尚未完整绑定r53正式认证链；不是当前版本的总通过率。原始完整400探测保留为local-only，不能声称公开完整重放。 |
| 三入口修复 | save time 20、ANSI 26、pulse delay 22，共68个不同家族。分阶段26个家族曾通过旧checker。 | 26来自不同版本，其中001、047、089、269仅有较早通过；早期ANSI/Pulse清理失败收据保留，不据后续进程快照改成清理成功。 |
| #208最终复验 | 23个是上述68的子集，同一最终核全部执行、22个旧checker通过、23个清理确认。347两处差异另列GAP09。 | 另外45个入口家族未在IR24重放，其中4个较早通过、41个上次失败。41个旧失败不等于当前核仍失败。 |
| 下一批受影响复验 | 原400中首阻塞为源组合的67个，与上述68个不相交。67加剩余45，去重为112个。 | 112是待执行清单，不是112个独立缺陷。先按cross/timer/transition及其他动态消费者试跑，再扩至各组；不自动启动完整远端矩阵。 |

41个最后已知失败包括事件变量除法8、非仿射谓词8、语法13、其他编译3、暂态组合3、初始化事件3、
整数算术1、事件分辨率1和资源预算1。这些只说明旧检查点的下一阻塞，复验后才更新当前分类。

<details>
<summary>112个待复验家族的固定ID</summary>

原67个源组合家族：002、004、006、008、010、040、043、044、051、055、065、071、084、091、100、103、104、106、109、117、178、184、191、198、199、200、204、205、206、207、208、209、210、213、214、284、293、294、306、308、309、310、311、312、320、321、322、327、331、341、342、345、352、353、356、357、361、363、367、375、376、379、382、394、395、397、399。

尚未在IR24重放的45个入口家族：001、012、017、026、036、047、048、049、056、057、058、072、076、077、078、079、081、088、089、097、098、261、262、263、264、265、266、267、268、269、271、274、275、276、277、278、279、280、299、300、301、302、348、349、355。

</details>

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

后续执行顺序是先核销GAP09的具体反例与语义，再复验112个受影响家族并按消费者选择GAP05/GAP06等有限切片。
DAE按GAP10→GAP11推进，历史反馈按GAP08→GAP13推进，自换向由GAP09/GAP08→GAP12承接。
每个已完成切片分别进入GAP15验收。GAP16–GAP18保留独立负责人和外部依赖，不并入当前源码修复队列。

<!-- ci:progress:start -->
v4 已有固定版本的 400 家族首阻塞探测，分类及推进顺序见[修复顺序](development/COMPARISON.md#repair-priority)。旧 checker 复核仅供定位，不是正式 benchmark 成绩。
<!-- ci:progress:end -->

原请求、独立控制和共同 Q 结论的更新条件见[每项修复与比较的验收](../validation/paper/COVERAGE.md#每项修复与每行比较一起验收)。
