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

## 6. 工程请求与扩展范围

下表按各自交付证据记录已核对的范围，历史基线与本次有限修复分别见链接，没有重跑全部 R01 请求。
工程请求采用各自的原判据；通过不自动增加上方的 Q 等级。独立控制通过，也不代表完整工程请求通过。

| 工程范围与证据 | 已交付或仍缺什么 | 对应 issue |
| --- | --- | --- |
| [R01 gain 统计](../../experiments/backends/support/README.md#event-statistics) | 已交付。三条原请求通过原 checker 和实际 Spectre 有限配对；共同 Q 验收未完成。 | [#65](https://github.com/BucketSran/vaEVAS/issues/65)、[#96](https://github.com/BucketSran/vaEVAS/issues/96) |
| [R01 timing 连续状态与测量](../../experiments/backends/support/r01-causal-timing/README.md) | 原 `timing-0` 已在原时限内完成并通过 checker；配对仍采用原边沿窗口和插值，不增加 Q 等级。 | [#66](https://github.com/BucketSran/vaEVAS/issues/66)、[#96](https://github.com/BucketSran/vaEVAS/issues/96) |
| [R01 CDS 双采样](../../experiments/backends/support/event-runtime-control/README.md#original-cds) | 本次修复的三条原请求均在原预算内完成，通过原 checker 与实际 Spectre 有限配对；执行绑定固定 v9，不增加 Q 等级。修复重复计算、根窗口和定时来源传递，保留原 `cds-0` 超时及参考告警。 | [#65](https://github.com/BucketSran/vaEVAS/issues/65)、[#119](https://github.com/BucketSran/vaEVAS/issues/119) |
| [R01 MUX 共享采样](../../experiments/backends/support/held-transition-targets/README.md) | 原三条均被事件条件经电压网络读取状态的检查拒绝，原 checker 未运行。仍缺历史采样与根处条件的认证；初态和部分保持量目标表达式已交付。本轮先修 CDS。 | [#65](https://github.com/BucketSran/vaEVAS/issues/65)、[#66](https://github.com/BucketSran/vaEVAS/issues/66) |
| [R01 同步读出](../../experiments/backends/support/r01-sync-readout/README.md) | 已交付实现能完整执行两条原请求，但原 checker 仍为 0/2，严格阈值下的读出差异保留；未合并候选另行验收。 | [#119](https://github.com/BucketSran/vaEVAS/issues/119)、[#96](https://github.com/BucketSran/vaEVAS/issues/96) |
| [ANSI 端口](../../experiments/backends/support/ansi-ports/README.md) | 接受逐端口方向、可选 electrical/一维范围及正文补 discipline，复用原绑定。原26请求推进到后续阶段，3项完成并通过冻结旧 checker，23项仍拒绝；不新增Q成绩。 | LANG |
| [SCS 时间选择](../../experiments/backends/support/scs-save-time/README.md) | `save time` 不再误报未知节点；保留时间轴、同名电气节点与默认节点保存。原 20 请求移除首阻塞，1 项完成并通过冻结旧 checker，19 项仍有后续拒绝；不新增 Q 成绩。 | LANG、DEV:scs-input |
| [Pulse delay 缺省值](../../experiments/backends/support/pulse-delay/README.md) | 仅缺省 delay 取 0，其他六字段保持显式。原 22 请求移除缺 delay 首阻塞，18 项源不确定性组合、4 项编译/语法拒绝保留，无整题完成；不新增 Q 成绩。 | DEV:scs-input |
| [源误差与动态组合](../../experiments/backends/support/scs-source-uncertainty/README.md) | 非零源误差已能随代数关系和固定 timer 采样传播；与连续算子、cross 或状态 timer 的组合仍明确拒绝。 | [#96](https://github.com/BucketSran/vaEVAS/issues/96)、[#119](https://github.com/BucketSran/vaEVAS/issues/119) |
| [隐式动态与事件](../../experiments/backends/implicit-event-restart/README.md) | 已交付有限动态步长和精确固定 timer 续算；一般事件窗、复位及代数约束跳参仍不在已验收范围。 | [#66](https://github.com/BucketSran/vaEVAS/issues/66) |
| 双向自换向 cross | 原问题尚未完成整体验收，候选中的超时和紧根预算失败继续保留。 | [#70](https://github.com/BucketSran/vaEVAS/issues/70)、[#119](https://github.com/BucketSran/vaEVAS/issues/119) |

<!-- ci:progress:start -->
v4 已有固定版本的 400 家族首阻塞探测，分类及推进顺序见[修复顺序](development/COMPARISON.md#repair-priority)。旧 checker 复核仅供定位，不是正式 benchmark 成绩。
<!-- ci:progress:end -->

原请求、独立控制和共同 Q 结论的更新条件见[每项修复与比较的验收](../validation/paper/COVERAGE.md#每项修复与每行比较一起验收)。

## XSPICE 编译出口

新增独立的 [EVAS→XSPICE 入口](reference/xspice.md)，将受限电压事件模型编译为 ngspice47 模型，与负载和反馈联立求解。首批固定 cross/timer/transition 组合、拒步回退与实例隔离的范围及执行身份见[入口证据](../../experiments/backends/xspice-entry/README.md)。这是另一条执行路径，不改变上方四后端固定Q表，也不把 ngspice+OpenVAF-R 的历史结果改写为此入口的结果。

[P0同源专项](../../experiments/backends/xspice-entry/p0-evidence.json)在同一IR28安装包上复用输入别名，补齐动态阈值、事件采样、输出RC与近零守卫的六例验收6/6。判据和各批分母分别保留；有限微例结果不证明完整原件或一般电流支路支持，尚未发布。

本地后端版本2固定接入 EVAS `c8dc2a7b`、IR28，增加 r53 单路及四路采样、条件计数、纯 timer 时钟、差分参考输出、连续 tanh 和时钟采样链路。其[独立本地证据](../../experiments/backends/xspice-entry/r53-evidence.json)包含回退、实例隔离及导数负控；115与068修复后，固定七例 Spectre 对照7/7通过，原配对超差、收敛失败及重试记录保留；不提升为完整兼容或固定Q资格。

[P1标准整理版时钟](../../experiments/backends/xspice-entry/p1-evidence.json)另建15/15同源ngspice/Spectre对照，覆盖零timer最终种子、1800ns默认32路、2400ns/42路、独立批次及长日程。所有后端使用同一标准整理文件，原始来源和两项适配差异保留；原件原样未验。该分母与P0六例、r53七例、旧十配置分别计账，未发布。
