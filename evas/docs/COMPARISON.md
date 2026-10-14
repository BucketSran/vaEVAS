# 四后端支持对比

**这张表比较固定用例中的支持和精度。** 每个行名链接到[本版必测范围](../validation/paper/COVERAGE.md#summary-scopes)。
同一行对四个后端使用相同用例和验收要求；后端可以使用不同配置达到要求。

<a id="table-design"></a>

- **✓ Q3**：本行全部必测用例完整通过 Q3。只通过 Q2 就写 **✓ Q2**；更严档位的失败仍保留。
- **具体原因**：已测配置失败，或某项原验收要求尚未满足。边界、回调和观测限制不等于整个算子不支持。

精度标记是验收上限，不是实测最大误差。1 V 刻度的 Q1、Q2、Q3 分别为 **10.1 µV、1.01 µV、101 nV**；
1 mV 小信号 Q3 为 **1.1 nV**。时间、状态和关键边界也须通过，详见[评测标准](COMPARISON-METHODOLOGY.md)。
只检查窗外、只有正确数字或只有运行成功，都不能打勾。

[#167](https://github.com/BucketSran/vaEVAS/pull/167) 已合入 main，补齐两类 `ddt`、采样后积分和局部 strobe。
本轮用独立新版 checker 重新验收旧窗口冲突的两个模型，三格取得 **✓ Q3**。
时间判断采用原有限导出分辨率，严格“没有提前触发”仍单列为未决；详见[新版结果](../../experiments/backends/support/README.md#root-window-v3)。

四条旧整链已在 main `7344e4db` 取得 EVAS 三档36次完整验收，全部达到 Q3。
本轮定时积分、采样边沿链、滤波后采样和中断边沿积分的 Spectre Q3，属于单独加入只读回调记录的源码；
原源码缺回调取证，未取得新 Q 资格。近邻整链保留原1 µV成绩，新 Q 尚缺边界观察及配置格式校准。
EVAS 0.15.0 / IR19 纳入中断边沿积分实现；该行 Q3 来自发布前候选的实际运行。
原预算和历史成绩继续保留，实际对照见[本轮记录](../../experiments/backends/support/README.md#legacy-chain-q)。

0.17.0 / IR21 开发代码增加顺序初始化与默认零状态、可证明整型的局部运算、
受限状态谓词、事件输出记录、合成时间驱动、有理连续流、受限 exp forcing 及保持物理状态的条件选路，
并将动态 [`$bound_step`](math/events.md#bound-step) 传入已支持的非线性内部积分段。
最终候选已取得[七项基础和三项初态的实际有限对照](../../experiments/backends/support/r01-root-windows/final-controls/README.md)，
它们使用独立控制预算，不属于下表固定 Q 用例。原16条复跑仍为12条完成，原70没有形成最终版本的完整验收，
因此不改下表历史成绩。一般数学函数与非线性电压代数耦合及更广组合仍有缺口。

固定零时刻 timer 的 transition 初态修正已取得[三模型实际有限配对](../../experiments/backends/support/README.md#initial-transition-seed)。
该修复使用原 `1e-8 V` 预算；第四反馈模型仅作诊断，不新增本表 Q 成绩，也不覆盖一般历史反馈。

[空循环声明与当前 timer 修复](../../experiments/backends/support/retained-safety/README.md)只消除错误接受。
新生成当前 timer 仍需同刻闭包，本轮没有改动下面各行的历史精度结论。

结果来自不同版本，**不是当前 main 的一次全量验收**。
五个数学函数的修复见[更新记录](../../experiments/backends/support/README.md#q3-closure)，
原11格的补证见[后续核对](../../experiments/backends/support/README.md#evidence-followup)，
旧表保存在[更新前的固定版本](https://github.com/BucketSran/vaEVAS/blob/8f7d911fe42f0692774ba388846d5dbf50f1bc34/evas/docs/COMPARISON.md)。
两类导数及八张组合卡的实际构建源为 `e2d8cbf8`，实现已随 #167 合入 `e028f96d`。
新版窗口的18次运行复用经逐文件核对的同一内核；其他行保留各自固定身份。
五个数学函数使用 IR19 构建，源码与内核身份由收据固定；事件和相位部分复用
[已合入的 #162](https://github.com/BucketSran/vaEVAS/pull/162) 的早期候选 `519d5e28` 的实际运行，其他身份见
[范围与来源](../validation/paper/COVERAGE.md#summary-scopes)。通过限于所列模型、观察、配置和执行版本，不外推到所有合法写法或全时域。

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
| [变量数组](../validation/paper/COVERAGE.md#scope-l1-08) | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
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

未定稿的动态 timer、ADC、同刻事件、内部反馈事件与隐式复位，列在[扩展计划](../validation/paper/COVERAGE.md#exploratory-cases)，不作为当前支持结论。
[配套清单](../validation/paper/COVERAGE.md#pending-evidence)说明原11格的核对结果与仍未完成的验收；[累计清单](../validation/paper/COVERAGE.md#先找到各批的原始成绩)保留全部历史用例、失败和原成绩。
