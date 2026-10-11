# 四后端支持范围与精度评测

本表说明四个后端在规定精度下能完成哪些电压域任务，也是论文取表入口。
**当前已为 8 个采样保持与一阶滤波条件建立 Q1/Q2/Q3 配置绑定。首轮 160 次运行保留，本轮另补 16 次配置与回调取证。**
通过只覆盖具名条件、观察点和误差预算，不代表完整语言支持或全时域误差证明。

阅读顺序：[精度控制](#accuracy-controls) → [表格构建与标记](#table-design) →
[验收误差](#acceptance-budgets) → [实际配置](#measured-settings) → [测评结果](#支持矩阵)。
详细依据见[配套评测标准](COMPARISON-METHODOLOGY.md)。
新的[Q1～Q3 精度档位](COMPARISON-METHODOLOGY.md#precision-tiers-proposal)已实现并实测。
[最新结果](#precision-binding-results)将数值达标与证据完整性分开列出；首轮 v2 和历史 v1 成绩分别保留。

<a id="accuracy-controls"></a>

## 1. 四个后端如何控制精度

| 后端 | 控制方式 | 怎样理解 |
| --- | --- | --- |
| Spectre | 求解容差、积分方法与误差控制、最大步长 | 决定每一步如何求解、何时缩步；精度预设可能覆盖请求值 |
| ngspice + OpenVAF-R | ngspice 的容差、瞬态积分与步长控制 | OpenVAF-R 编译模型，ngspice 负责数值求解 |
| Gnucap + modelgen-verilog | Gnucap 的容差、积分与步长控制，时间分辨率 `dtmin` | modelgen-verilog 编译模型，Gnucap 负责数值求解 |
| EVAS | `vabstol`、`reltol`、`max_step`，以及受支持路径的误差传播检查 | 作用取决于求解路径；解析传播也存在有限精度误差，收紧设置可能改变是否接受结果 |

模型中的 `timer` 时间容差和 `cross` 时间、表达式容差另行约束事件定位。
`strobe` 规定求解或观察时刻，本身不保证电压误差达标。
**内部设置是控制手段，外部测试误差才是验收标准。** 相同参数值不表示同等输出精度。

<a id="table-design"></a>

## 2. 表格怎样构建，标记是什么意思

基础特性检查一种语言写法或算子；工程组合检查采样保持、边沿、滤波等共同工作时的行为。
每行先固定必测条件，覆盖该行适用的初态、信号幅度、事件前后、持续运行或多实例情形。
具体范围写在行名和[条件说明](COMPARISON-METHODOLOGY.md#test-conditions)中，不把一次成功推广到所有写法。

单个用例通过记为 **✓**；确认失败直接写原因，如“编译失败”“漏事件”“输出超差”。
尚不能下结论时，写清缺少什么，例如“边界未验收”；尚未细分的保留“待验证”。
没有运行的写“未测”。这些待完成项不等于失败。

一行有多个用例时，用 **通过数／计划测试数** 表示，例如 `2/3`。
这里的 3 是事先约定要测的用例数，2 是已经确认通过的数量。
若剩下 1 项未测，就写 `2/3，另 1 项未测`；总数仍是 3，也不能把未测说成失败。
失败原因、待验证或未测的数量在附注中说明，配置尝试次数不计入用例数。

<a id="acceptance-budgets"></a>

## 3. 如何统一验收标准

**同一个测试用例，四个后端使用相同的模型、输入、行为要求和允许误差。**
各后端可以采用不同的容差、步长和积分方法，但都要达到同一验收要求。
验收同时检查电压误差、事件时间、次数与顺序，关键边界也要检查。

不同类型的用例可以有不同误差预算，但必须在测试前确定，不能根据运行结果放宽。
具体数值、预算依据和边界判定见[评测标准](COMPARISON-METHODOLOGY.md#numerical-acceptance)。
尚未按共同标准完成验收的历史结果在下文单独列出，不与新测试合并计算通过率。

<a id="measured-settings"></a>

## 4. 测试实际采用了哪些配置

本批 EVAS 为 main **`826fefb1`** 的独立 release 构建，包版本 **0.14.0 / IR18**，未修改模拟器。
Spectre 为 **21.1.0.509.isr12**，ngspice 为 **46**，Gnucap 为 **snapshot 2026.07.29**。
编译器、内核和容器以[收据](../../experiments/backends/support/20261011-precision-binding.json)及[配置绑定表](../validation/paper/precision-bindings-v1.json)的哈希固定。

选择“条件＋后端＋Q 档”即可在运行前确定下表配置及对应验收要求。
相同配置可以满足多个 Q 档；空缺组合返回具体原因，不自动降档。

| 后端与已校准条件 | Q1 配置 | Q2 配置 | Q3 配置 |
| --- | --- | --- | --- |
| Spectre：四个采样保持条件 | base，含回调日志 | 同左 | 同左 |
| Spectre：斜坡、非零初态、idt 滤波 | base | tol | deep_bound |
| Spectre：小信号滤波 | base | base | tol |
| EVAS：三个定时采样、四个滤波条件 | base | base | base |
| ngspice：斜坡、非零初态、idt 滤波 | tol | step | deep |
| ngspice：小信号滤波 | base | tol | step |
| Gnucap：三个定时采样条件 | base | base | base |
| Gnucap：斜坡、idt 滤波 | tol | step | deep_bound |
| Gnucap：小信号滤波 | base | step | step |

这些配置的实际容差如下。三组值依次对应 **base/step、tol/both、deep/deep_bound**。

| 后端 | 实际相对容差，三组 | 实际电压绝对容差，三组 | 实际电流绝对容差，三组 | 积分方法 |
| --- | --- | --- | --- | --- |
| Spectre | 10⁻⁶ / 10⁻⁹ / 10⁻¹¹ | 1 nV / 1 pV / 10 fV | 100 fA / 1 fA / 10 aA | `traponly` |
| ngspice | 10⁻⁵ / 10⁻⁸ / 10⁻¹⁰ | 1 nV / 1 pV / 10 fV | 100 fA / 1 fA / 10 aA | `trap` |
| Gnucap | 10⁻⁵ / 10⁻⁸ / 10⁻¹⁰ | 1 nV / 1 pV / 10 fV | 100 fA / 1 fA / 10 aA | `trap` |
| EVAS | 10⁻⁵ / 10⁻⁸ / 10⁻¹⁰ | 1 nV / 1 pV / 10 fV | 不适用 | 按模型选择路径 |

base/tol 的最大步长为 **31.25 ns**，step/both 为 **3.90625 ns**；
ngspice deep 为 **0.48828125 ns**，新增 deep_bound 为 **0.4 ns**。
Spectre 的实际 reltol 是请求值的 1/10，这是 `conservative` 预设的作用。
ngspice 固定 `trtol=7`、`chgtol=10 fC`、`itl4=10`；Gnucap 固定 `trtol=7`、`dtmin=10⁻¹⁶ s`、`dtratio=10⁹`。
各配置沿用同一 Q3 观察计划；有效设置和观察证据都须验收。

Spectre 和 EVAS 的所选步长有运行回执；ngspice、Gnucap 则补有与安装身份一致的参数传递证明。
二者分别记录，不把写入网表当成读回。旧 deep 的回显不足、时间量化及 EVAS 拒绝记录仍保留。
更多设置、证据方式和复用范围见[评测标准](COMPARISON-METHODOLOGY.md#precision-bindings)。

## 5. 测评结果

数字表示通过数与计划测试数，附注说明未通过的原因或尚未完成的测试。
历史表沿用原验收范围，不代表新的统一精度验收已经完成。

<a id="支持矩阵"></a>
<a id="新精度测试"></a>

<a id="precision-binding-results"></a>

### 当前：Q 档位与配置已绑定

下表按每个条件已确认的最高档报告。**Q3 通过也满足 Q1、Q2，且必须在同一次运行中满足行为和证据要求。**
1 V 条件的 Q3 电压门槛为 **101 nV**，1 mV 条件为 **1.1 nV**；事件与关键边界没有排除。

| 必测条件 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS `826fefb1` |
| --- | --- | --- | --- | --- |
| 定时采样：斜坡、小信号、32 次采样 | Q3 ✓，3/3 | 工作点失败 | Q3 ✓，3/3 | Q3 ✓，3/3 |
| 阈值采样：8 次穿越与保持 | Q3 ✓ | 工作点失败 | 漏事件，仅 3 次 | 数值达标，回调边界待证 |
| 一阶滤波：斜坡、非零 DC 初态、小信号 | Q3 ✓，3/3 | Q3 ✓，3/3 | Q3 2/3；非零初态错误 | Q3 ✓，3/3 |
| 等价 idt 一阶反馈 | Q3 ✓ | Q3 ✓ | Q3 ✓ | Q3 ✓ |

数值结果与证据状态分开看，才能决定接下来是修求解器还是补观察：

| 后端 | Q3 数值结果 | 证据与行为检查 | 取得完整配置资格 |
| --- | --- | --- | --- |
| Spectre | 8/8 达标 | 八项均有完整通过依据 | 8/8 |
| EVAS | 8/8 达标 | 阈值采样的实际回调边界仍缺证，其余七项完整 | 7/8 |
| ngspice + OpenVAF-R | 四个滤波达标；四个采样保持无波形 | 滤波设置与边界证据已补齐；采样保持工作点失败 | 4/8 |
| Gnucap + modelgen-verilog | 六项达标；非零初态超差；漏事件一项不做数值合格判断 | 六项完整通过；另两项已有失败依据 | 6/8 |

Spectre 首轮的“Q3 尚未确认”已由本轮补测和取证补齐，不能再解释成它达不到 Q3。
EVAS 的剩余一项是回调取证问题，不据此认定电压计算错误，也不直接授予通过。
三个 EVAS 滤波条件在极严 deep 设置下的认证拒绝仍保留；可复用的基础配置通过不抵消这些拒绝。
本批仍是开发条件的有限观察，不是独立论文最终评价集或全时域误差证明。
[本轮实测与复验入口](../../experiments/backends/support/README.md#precision-bindings)。

<a id="precision-v2-results"></a>

### 首轮 v2：原 160 次扫描成绩

本节保留补证前的结论，不代表上方最新配置资格。Q1、Q2、Q3 的电压门槛依次为 **100 nV + 10 ppm × A**、**10 nV + 1 ppm × A**、
**1 nV + 0.1 ppm × A**，A 是预先固定的 1 V 或 1 mV 刻度。
所有档位检查相同的事件、初态和关键边界。下表写出已确认的最高档；Q3 通过同时满足 Q1、Q2。

| 必测条件 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS `826fefb1` |
| --- | --- | --- | --- | --- |
| 定时采样：斜坡、小信号、32 次采样 | 回调边界待证 | 工作点失败 | Q3 ✓，3/3 | Q3 ✓，3/3 |
| 阈值采样：8 次穿越与保持 | 回调边界待证 | 工作点失败 | 漏事件，五档均仅 3 次 | 回调边界待证 |
| 一阶滤波：斜坡、非零 DC 初态、小信号 | Q2 ✓，3/3；Q3 仅小信号确认 | 步长生效待证 | Q2 2/3；非零初态错误；Q3 仅小信号确认 | Q3 ✓，3/3 |
| 等价 `idt` 一阶反馈 | Q2 ✓；Q3 配置回显待证 | 步长生效待证 | Q2 ✓；Q3 步长量化有差别 | Q3 ✓ |

**“回调边界待证”不是电压超差。** 这些运行的采样误差已小于 Q3 门槛，但观察得到的回调区间跨越合法窗口端点，
还不能确认整个区间内的时刻都合法。四后端使用同一规则：不裁掉区间外侧，也不把第一条新计数记录直接当作回调时刻。

滤波也需分清数值与证据。Spectre 的 deep 波形已达到 Q3，尚缺更准确的步长生效证据；
ngspice 四个滤波条件都有 Q2 数值达标的配置，但步长资格尚未补齐，两个 deep 条件还缺输入折点一侧的观察。
Gnucap 的非零初态始终为 0 V，预期为 0.25 V，属于真实输出错误。

EVAS 七个条件在基础档就满足 Q3，另一个阈值采样条件缺边界证据。
但三个大信号滤波条件在 deep 下被内部精度认证拒绝，原始失败保留；基础档成功不表示任何更严配置都可用。
全部配置、误差变化及下一步见[本轮实测记录](../../experiments/backends/support/README.md#precision-v2)。
本批是开发条件的有限观察，不是独立论文最终评价集，也不宣称全面 Spectre 对齐。

### 历史 v1：基础连续动态

这 4 个条件采用 **10 nV + 1 ppm × 固定参考幅度** 的电压误差目标，属于原 8 条件精度集。
EVAS 在 2026-10-11 复验中四档均通过。其他后端采用原批次的首个达标配置。

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

### 历史 v1 与后续组合：沿用原验收

每行按各自的固定条件计数，预算不同，不相加计算总通过率。
前两行是原 8 条件精度集中的另外 4 条，已完成四后端共同标准下的实测。
其余为独立开发对照，仍缺两个开源后端的同条件验收，不属于完整四后端精度比较。
EVAS 列均来自 2026-10-11 复验，Spectre 列保留原来的达标设置与超差记录。

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

### 基础特性与其他组合：尚未完成新标准的统一验收

以下仍使用 **2026-10-09 至 10-10 的原批次证据**，没有在 2026-10-11 复验中全部重跑，不能当成 `fc7e57fd` 的新成绩。
核心运行时为 `5d357251`，采样滤波组合为 `ad6f3577`；后续专项版本见行内证据。
本节的 ✓ 仅指原报告注明的测试范围，不代表新的统一精度验收已经完成。
原检查跳过关键边界的项目标为“边界未验收”，不能据窗外结果给整项打勾。
当前代码已包含对应实现，但是否满足更广的工程条件，需要另行验收。

| 特性／测试范围 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS 原批次 |
| --- | --- | --- | --- | --- |
| **基础语言与电压关系** | | | | |
| 线性、参考节点、贡献累加 | ✓ | ✓ | ✓ | ✓ |
| 三次多项式反馈 | ✓ | ✓ | ✓ | ✓ |
| 宏、参数 | ✓ | ✓ | 参考节点异常 | ✓ |
| 静态层次 | ✓ | 编译失败 | ✓ | ✓ |
| 条件、函数、顺序赋值 | 边界未验收 | 边界未验收 | 边界未验收 | 边界未验收 |
| 静态循环与数组事件 | 边界未验收 | 编译失败 | 编译失败 | 边界未验收 |
| 静态电压向量 | ✓ | ✓ | 编译失败 | ✓ |
| **单项算子与原事件组合** | | | | |
| `initial_step` 与事件状态 | 待验证 | 组合事件失败 | 待验证 | ✓ |
| `cross` 阈值事件 | 待验证 | 事件条件丢失 | 待验证 | 边界未验收 |
| `timer` 采样／定时事件 | 待验证 | 事件条件丢失 | 待验证 | ✓；原采样差异保留 |
| `transition` 与事件组合 | 待验证 | 组合事件失败 | 待验证 | ✓；原边沿时移保留 |
| `absdelay` 固定延迟 | ✓ | 编译器崩溃 | ✓ | ✓ |
| `slew` 固定速率 | ✓；细步长 | 编译失败 | ✓ | ✓ |
| `idt` 连续积分 | 待验证 | 待验证 | 待验证 | ✓ |
| `idtmod` 相位环回 | 待验证 | 待验证 | 编译失败 | 环回边界未验收 |
| `laplace_nd` 单极点，旧短时常数条件 | ✓ | ✓ | 输出超差 | ✓ |
| `laplace_np` 单极点，旧短时常数条件 | ✓ | 编译失败 | 输出超差 | ✓ |
| `ddt` 分段线性输入：仅线性段内 | ✓ | ✓ | 输出超差 | ✓ |
| **专项工程组合** | | | | |
| 非线性 `cross` 直接采样：正向、负向、小幅值 | 3/3 | 未测 | 未测 | 3/3；按预算细化 |
| 非线性积分与事件后续算 | 2/2；需收紧容差 | 未测 | 未测 | 2/2 |
| 采样→保持→边沿→一阶滤波，原 4 类组合 | 4/4 | 未测 | 未测 | 4/4；接受限定边界差异 |

条件／函数和循环／数组事件的旧检查跳过阈值或事件附近的一段时间，只验证其余观察点。
这两行的“边界未验收”表示缺少完整验收，不能据此判定后端不支持，也不能认定整项通过。
`cross`、`idtmod` 的旧报告同样仍缺边界验收证据。
`ddt` 行只报告线性段内求导，拐点附近尚未验收。边界如何补验见[评测标准](COMPARISON-METHODOLOGY.md#table-verdicts)。
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

### EVAS 还缺什么

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

### 证据与论文使用

- [v2 精度扫描](../../experiments/backends/support/README.md#precision-v2)：新 checker、160 个运行配置与未完成资格。
- [当前 main 复验](../../experiments/backends/support/README.md#current-main)：本轮执行范围、构建身份、保留的原始参考及限制。
- [评测标准](COMPARISON-METHODOLOGY.md)：预算推导、精度设置、原生时刻与事件窗口的验收规则。
- [初版比较表](../../experiments/backends/comparison/TABLE.md)：原 V1–V7 开发集与 CMP8，仅作历史基线。
- [验证设计](../validation/paper/README.md)与[维护契约](development/COMPARISON.md)：后续用例和复验规则。

当前材料用于开发与支持范围说明，**尚不是冻结的独立论文评价集**。部分原始日志和波形仅在本地保存，
公开收据中的哈希不等于公开可下载的数据。论文定稿时需冻结用例、工具、判据和证据版本。
