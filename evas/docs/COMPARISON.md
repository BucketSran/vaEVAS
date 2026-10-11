# 四后端支持范围

**最新 EVAS 已支持定时采样的 strobe、近邻定时事件、采样到一阶滤波、两级固定 `slew`，以及外部多项式输入的滤波。**
复杂事件反馈、一般历史组合及部分精确边界仍未完成。

本表是项目唯一的支持总表，也是论文取表入口。更新日期：**2026-10-11**。
当前 EVAS 代码基线为已合入的 [main `fc7e57fd`](https://github.com/BucketSran/vaEVAS/commit/fc7e57fd3b92e76b15f5c3dc8c2359d25c6b1313)。
**0.14.0 是尚未递增的包版本，IR18 是编译结果的格式版本；两者不能区分近期修复。** 本表用提交号标明代码身份。

本轮用该版本重新执行下列精度与组合检查，见[当前版本复验](../../experiments/backends/support/README.md#current-main)。
其他三后端复用原模型、刺激、设置与判据下的实际运行，未在本轮重跑。
Spectre 为 **21.1.0.509.isr12**；两个开源方案以证据中的编译器哈希和容器身份为准，结论不泛指所有版本。

## 怎样判断通过

- **p/N**：N 个固定条件中有 p 个通过。每个后端可以按既定规则选择达标设置；失败档位仍保留。
- **✓**：通过该行限定范围的旧批次检查。**运行成功**：完成仿真，但尚未完成行为验收。**未测**：没有该组合的实测结论。
- 通过只覆盖所列写法、观察点和预算，不表示完整语言支持、全时域误差证明或与 Spectre 逐点相同。

精度目标来自外部工程判据，不能直接用内部 `reltol` 代替。
下表按用例列出预算；时间窗口、事件顺序和边界另行检查，不能删除关键边界来取得通过。
具体依据、四后端配置及选择规则见[评测标准](COMPARISON-METHODOLOGY.md)。

<a id="支持矩阵"></a>
<a id="新精度测试"></a>

## 基础连续动态：最新版本复验

这 4 个条件采用 **10 nV + 1 ppm × 固定参考幅度** 的电压误差目标，属于原 8 条件精度集。
EVAS 四档均重新通过。其他后端采用原批次的首个达标配置。

| 必测范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS `fc7e57fd` |
| --- | --- | --- | --- | --- |
| 一阶 `laplace_nd`：斜坡、非零 DC 初态、小信号 | 3/3 | 3/3 | 2/3；非零初态错误 | **3/3** |
| `idt` 一阶反馈：分段线性输入 | 1/1 | 1/1 | 1/1 | **1/1** |

Gnucap 的非零初态应为 0.25 V，四档均从 0 V 开始，属于输出错误。
这些线性条件不能证明所有非线性积分路径都有相同精度。
[原四后端证据](../../experiments/backends/support/README.md#precision-pilot)保留全部 128 配置与后续补测。

<a id="strobe-与连续历史组合"></a>
<a id="两级固定-slew-组合"></a>
<a id="非线性输入的滤波直接通路"></a>

## 工程组合：最新版本复验

每行按各自的固定条件计数，预算不同，不相加计算总通过率。
前两行是原 8 条件精度集中的另外 4 条；其余为独立开发对照。
EVAS 列均来自本轮重跑，Spectre 列保留原来的达标设置与超差记录。

| 必测范围 | 电压预算 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS `fc7e57fd` |
| --- | --- | --- | --- | --- | --- |
| 定时采样保持：斜坡、小信号、32 次采样 | 10 nV + 1 ppm × 固定幅度 | 3/3 | 0/3；工作点失败 | 3/3 | **3/3；strobe** |
| 阈值采样保持：8 次穿越与读值 | 10 nV + 1 ppm × 固定幅度 | 1/1 | 0/1；工作点失败 | 1/1；仅基础档 | **1/1；strobe** |
| 采样→保持→边沿→滤波：正常、中断、双实例 | 100 µV | 3/3 | 未测 | 未测 | **3/3；strobe** |
| 采样→积分：原 100 ps 定时容差 | 100 µV | 0/1；115.49 µV 超差 | 未测 | 未测 | **1/1；strobe** |
| 近邻 timer：固定、精确保持周期 | 1 µV | 2/2 | 未测 | 未测 | **2/2；strobe** |
| 近邻 timer→边沿→滤波，另路积分 | 1 µV | 1/1；需收紧容差 | 未测 | 未测 | **1/1；strobe** |
| 两级固定 `slew`：斜坡、平台、反向追赶 | 1 µV | 3/3；反向需局部细步长 | 未测 | 未测 | **3/3** |
| 平方输入的滤波直接通路：斜坡、非零初态反向、非整数系数 | 1 µV | 3/3；反向需收紧设置 | 未测 | 未测 | **3/3** |

前三类定时问题的含义需要分清：

- **EVAS 已修复的拒绝**：原固定 timer 的 12 次 strobe 拒绝及新增近邻 timer 的 12 个配置，修复后均通过。原失败保留。
- **Spectre 参考超差**：采样→积分原条件仍失败。只把模型中的定时容差收紧到 10 ps、1 ps 后，误差分别降至 11.61 µV、1.18 µV；不能据原差值判 EVAS 积分错误。
- **Gnucap 的设置敏感性**：阈值采样基础档记录 8 次事件，后三档仅 4、7、3 次。基础档通过不表示收紧设置后更可靠。

各组合的原始设置、失败档位和实际 Spectre 对照分别见
[固定 timer](../../experiments/backends/strobe/README.md#timer-fix)、
[近邻 timer](../../experiments/backends/strobe/README.md#near-timer)、
[两级 slew](../../experiments/backends/slew-cascade/README.md)、
[滤波直接通路](../../experiments/backends/filter-direct/README.md)。
两级 slew 不含动态限速、第三层、反馈或 cross 消费者；滤波直接通路只含外部源的多项式输入。

## 基础特性与其他组合：保留原批次结论

以下仍使用 **2026-10-09 至 10-10 的原批次证据**，没有在本轮全部重跑，不能当成 `fc7e57fd` 的新成绩。
核心运行时为 `5d357251`，采样滤波组合为 `ad6f3577`；后续专项版本见行内证据。
当前代码已包含对应实现，但是否满足更广的工程条件，需要另行验收。

| 特性／测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS 原批次 |
| --- | --- | --- | --- | --- |
| **基础语言与电压关系** | | | | |
| 线性、参考节点、贡献累加 | ✓ | ✓ | ✓ | ✓ |
| 三次多项式反馈 | ✓ | ✓ | ✓ | ✓ |
| 宏、参数 | ✓ | ✓ | 参考节点异常 | ✓ |
| 静态层次 | ✓ | 编译失败 | ✓ | ✓ |
| 条件、函数、顺序赋值 | ✓ 阈值窗外 | ✓ 阈值窗外 | ✓ 阈值窗外 | ✓ 阈值窗外 |
| 静态循环与数组事件 | ✓ 事件窗外 | 编译失败 | 编译失败 | ✓ 事件窗外 |
| 静态电压向量 | ✓ | ✓ | 编译失败 | ✓ |
| **单项算子与原事件组合** | | | | |
| `initial_step` 与事件状态 | 运行成功 | 组合事件失败 | 运行成功 | ✓ |
| `cross` 阈值事件 | 运行成功 | 事件条件丢失 | 运行成功 | ✓；精确边界待核 |
| `timer` 采样／定时事件 | 运行成功 | 事件条件丢失 | 运行成功 | ✓；原采样差异保留 |
| `transition` 与事件组合 | 运行成功 | 组合事件失败 | 运行成功 | ✓；原边沿时移保留 |
| `absdelay` 固定延迟 | ✓ | 编译器崩溃 | ✓ | ✓ |
| `slew` 固定速率 | 细步长通过 | 编译失败 | ✓ | ✓ |
| `idt` 连续积分 | 运行成功 | 运行成功 | 运行成功 | ✓ |
| `idtmod` 相位环回 | 运行成功 | 运行成功 | 编译失败 | ✓；精确环回边界待核 |
| `laplace_nd` 单极点，旧短时常数条件 | ✓ | ✓ | 输出超差 | ✓ |
| `laplace_np` 单极点，旧短时常数条件 | ✓ | 编译失败 | 输出超差 | ✓ |
| `ddt` 分段线性输入 | ✓ 段内 | ✓ 段内 | 输出超差 | ✓ 段内 |
| **专项工程组合** | | | | |
| 非线性 `cross` 直接采样：正向、负向、小幅值 | 3/3 | 未测 | 未测 | 3/3；按预算细化 |
| 非线性积分与事件后续算 | 2/2；需收紧容差 | 未测 | 未测 | 2/2 |
| 采样→保持→边沿→一阶滤波，原 4 类组合 | 4/4 | 未测 | 未测 | 4/4；接受限定边界差异 |

“阈值窗外”“事件窗外”“段内”只说明旧检查的范围，不是语言不支持，也不满足新增测试必须检查关键边界的要求。
“组合事件失败”包含事件 OR 编译失败或事件状态错误，不能单独归因于 `initial_step`、`transition`。

[原逐项报告](../../experiments/backends/support/README.md)保留模型与判据。
所测 OpenVAF-R 编译产物丢失 timer/cross 事件条件，设置对照未修复最小反例；见[失败定位](../../experiments/backends/support/README.md#ngspice-events)。
Gnucap 旧专项补齐时间分辨率后为 9 通过、3 输出超差、1 输入异常，另有原 2 项编译失败。

后续专项证据分别为[非线性 cross 直接采样](../../experiments/backends/sample-edge-filter/BOUNDARY.md#新直接采样路径的同源码对照)、
[非线性积分与续算](../../experiments/backends/transient-accuracy/README.md#integration-20261010)、
[原四类采样滤波](../../experiments/backends/sample-edge-filter/README.md)。
非线性积分两例按原 1 mV 预算验收；8 配置中工程对照 5/8 通过，参考超差和严格时刻失败仍保留。
原四类采样滤波的 **SEF-TIMER-18** 是已接受的 18 条跳变侧差异，不再要求清零；
[接受范围](../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18)不包括 C1、#79、VCO、Spec B 或新模型。

## EVAS 还缺什么

| 范围 | 已完成 | 仍未完成 |
| --- | --- | --- |
| 定时事件与 strobe | 固定时钟、精确保持时钟、近邻事件及上述连续消费者 | 不确定保持参数、连续局部历史和一般事件簇 |
| 采样与下游消费者 | 直接采样、单次滤波预算反推、停止时刻采样 | 采样→保持→边沿→滤波→cross 的近根查询；[#131](https://github.com/BucketSran/vaEVAS/pull/131) 仍为 draft，未计入 main |
| 算子组合 | 两级固定 slew、外部多项式滤波直接通路 | 动态参数、更深级联、内部非线性反馈及事件修改历史后的普遍闭包；[#66](https://github.com/BucketSran/vaEVAS/issues/66) |
| 复杂事件反馈 | 已有有限组合 | 双向自换向 cross；[#70](https://github.com/BucketSran/vaEVAS/issues/70) |
| 精确边界与参考资格 | 原严格失败和已接受差异分别保留 | C1、#79 stop=3、VCO 普通相位节点环回、Spec B 的剩余参考资格；[#96](https://github.com/BucketSran/vaEVAS/issues/96) |
| 语言、网表与精度控制 | 有限控制流、DC/PWL/pulse、五项 strobe 控制 | 更广语言与源类型、非精确脉冲时刻、通用精度预算和拒绝原因细分；[#65](https://github.com/BucketSran/vaEVAS/issues/65)、[#63](https://github.com/BucketSran/vaEVAS/issues/63)、[#119](https://github.com/BucketSran/vaEVAS/issues/119) |

[停止时刻修复](../../experiments/backends/sample-edge-filter/BOUNDARY.md#timer-stop)在原 100 nV 预算内通过；
[单次滤波预算反推](../../experiments/backends/sample-edge-filter/BOUNDARY.md#filter-budget)只覆盖具名案例，均不扩大上表分母。
[#64](https://github.com/BucketSran/vaEVAS/issues/64) 的诊断接口交付已完成关闭；诊断能力不计作电路数值通过。

表中既有真实能力限制，也有尚未完成的参考或观察验收。不能把后者全部称为 EVAS 数值错误。
EVAS 仍是电压域行为模拟器，不求解晶体管、电流／电荷方程、真实负载及完整 SPICE 网表。本表不作速度排名。

## 证据与论文使用

- [当前 main 复验](../../experiments/backends/support/README.md#current-main)：本轮执行范围、构建身份、保留的原始参考及限制。
- [评测标准](COMPARISON-METHODOLOGY.md)：预算推导、精度设置、原生时刻与事件窗口的验收规则。
- [初版比较表](../../experiments/backends/comparison/TABLE.md)：原 V1–V7 开发集与 CMP8，仅作历史基线。
- [验证设计](../validation/paper/README.md)与[维护契约](development/COMPARISON.md)：后续用例和复验规则。

当前材料用于开发与支持范围说明，**尚不是冻结的独立论文评价集**。部分原始日志和波形仅在本地保存，
公开收据中的哈希不等于公开可下载的数据。论文定稿时需冻结用例、工具、判据和证据版本。
