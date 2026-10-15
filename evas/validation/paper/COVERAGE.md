# 累计测试清单与新旧对应

本清单登记本版主表的固定用例、五层扩展计划、历史对应和待补证据。
[支持对比表](../../docs/COMPARISON.md)只呈现结果；本页登记用例关系，不另判成绩。
新 44 组及相应 EVAS 修复来自已合入的 [#162](https://github.com/BucketSran/vaEVAS/pull/162)。
其模型、checker 和收据链接固定执行版本，旧成绩不自动代表后续 main。
本轮新增 IR19 数学函数与恒定输入修复，执行身份和固定范围见[本轮证据](../../../experiments/backends/support/README.md#q3-closure)。
采样积分与局部 strobe 的五卡复测另见[新修复收据](../../../experiments/backends/support/README.md#sampled-integral-fix)，不覆盖旧运行。

本次盘点覆盖历史对比表引用的 31 条件、core-v1 的 12 条件、15 个专项、8 个精度条件，
以及采样滤波、strobe、近邻 timer、两级 slew、滤波直通、直接采样、非线性续算和七模型确认集。
另补登记原卡中的 `s1-default-reordered` 未运行条件。开发单元测试与校准控制不计作对比条件。
这里覆盖所列历史批次，不声称已穷尽全库调试探针；发现遗漏时追加登记，不改旧批次分母。

**没有一项旧条件被本次盘点宣布退役。** 下表的“相关项”只表示共同特性，不表示完整覆盖。
即使数学形式相似，模型、幅度、初态、时长、消费者、边界或判据不同，也保留原用例和成绩。
对完整替代的确认，需要逐项核对这些条件及旧例能检出的错误；目前没有这样的替代证明。

## 如何累积结果

- 每个结果保留用例、判据、配置和执行版本。新模型或新判据另立记录，不能覆盖原成绩。
- 同一用例复测时并列保存旧结果与新结果，主表注明所引用版本；旧版本通过不自动代表最新版本。
- 同组全部必测变体在某个 Q 档完整通过，才可报告该档精度。更严配置失败也保留，不抹去已验证配置。
- 不把不同批次、不同预算或配置次数相加成一个总通过率。重复复验和别名也不增加独立用例数。

例如，旧 `SH-T-SMALL` 是 1 mV 小信号；新批次全部采用 1 V 参考刻度。
新批次 Q3 通过不能替代旧小信号 Q3 的 1.1 nV 要求。

<a id="layer-directory"></a>

## 五层能力目录与扩展计划

目录按验收问题分层，不按 F、EC 前缀或实现难度排序。每行的 ID 和相对顺序保持稳定。
新能力追加所属层末尾；同一能力的新用例追加该行明细。扩展必测范围时记录新范围版本，
旧用例、判据和成绩继续按原身份查询，不能把旧通过自动套到扩展范围。
L1–L5 是本文的表格导航 ID，不替代开发回归的 LANG、TIMER 等能力 ID。

下表是扩展目标，尚未完成的目标不计入本版主表验收。
本版实际必测集合单独列在[固定范围](#summary-scopes)；下表的“已有资料”只表示相关模型已登记。
旧条件先标主归属，也可在其他行作为辅助证据；交叉引用不增加用例数。
六个数学函数各自成行。高层组合通过不自动授予低层算子的完整支持资格。
测试中可以使用辅助算子，但必须单独核验其输入或事件，区分被测行为与辅助行为。

<a id="layer-1"></a>

### 第1层：语言与静态电压关系

| 能力 | 扩展目标 | 已有资料 | 待补测试或验收 |
| --- | --- | --- | --- |
| <a id="l1-01"></a>L1-01 宏与 include | 对象宏、函数宏、条件编译、重复包含保护 | [`F01`](#f01)、[`LANG-preprocess`](#old-lang-preprocess)、[`language`](#old-language) | include 保护、条件编译的独立验收 |
| <a id="l1-02"></a>L1-02 参数 | 默认值、实例覆盖、参数依赖、合法范围端点 | [`F01`](#f01)、[`F09`](#f09)、[`s1-default`](#old-s1-default)、[`s1-override`](#old-s1-override)、[`LANG-preprocess`](#old-lang-preprocess)、[`LANG-hierarchy`](#old-lang-hierarchy)、[`SI-01`](#old-si-01) | 参数依赖与范围端点 |
| <a id="l1-03"></a>L1-03 条件与逻辑表达式 | 各分支；阈值下、相等、上；逻辑与三元选择；动态重求值 | [`F03`](#f03)、[`F05`](#f05)、[`v1-main`](#old-v1-main)、[`EX-01`](#old-ex-01)、[`LANG-functions`](#old-lang-functions) | 精确输入取证；动态与 DC 边界的共同验收 |
| <a id="l1-04"></a>L1-04 case 分支 | 各分支、首次匹配、default；动态重求值 | [`F04`](#f04) | 动态 case 用例 |
| <a id="l1-05"></a>L1-05 顺序赋值 | 前句结果、重复赋值、分支内重写判断变量、贡献值快照 | [`F02`](#f02)、[`F05`](#f05)、[`EX-01`](#old-ex-01)、[`LANG-functions`](#old-lang-functions) | 原动态模型与新边界卡按同一版复验 |
| <a id="l1-06"></a>L1-06 用户函数 | 参数、局部量、分支、嵌套调用、调用间隔离 | [`F05`](#f05)、[`LANG-functions`](#old-lang-functions)、[`language`](#old-language) | 嵌套调用与调用间隔离 |
| <a id="l1-07"></a>L1-07 静态循环 | 零次、一次、多次、参数化次数、顺序累加 | [`F06`](#f06)、[`LANG-array-events`](#old-lang-array-events)、[`language`](#old-language) | 零次、一次与参数化次数 |
| <a id="l1-08"></a>L1-08 变量数组：静态下标 | 首尾元素、静态下标、声明方向、独立读写 | [`F06`](#f06)、[`LANG-array-events`](#old-lang-array-events)、[`language`](#old-language) | 相反声明方向；持久事件状态另见 L3-11 |
| <a id="l1-09"></a>L1-09 电气向量 | 各位独立驱动与读取、升降序声明、模块间位连接 | [`F08`](#f08)、[`LANG-vector`](#old-lang-vector) | 升序声明与模块间位连接 |
| <a id="l1-10"></a>L1-10 模块层次 | 命名与位置连接、参数传递、内部节点隔离、声明交换 | [`F09`](#f09)、[`LANG-hierarchy`](#old-lang-hierarchy)、[`v7-linear-main`](#old-v7-linear-main)、[`v7-linear-swapped`](#old-v7-linear-swapped)、[`v7-linear-a-half`](#old-v7-linear-a-half)、[`language`](#old-language) | 不同连接写法与独立输入对照 |
| <a id="l1-11"></a>L1-11 sin | 零点、极值、正负输入、不同周期 | [`P-sin`](#p-sin) | 本批有限范围及各档结果已另立身份；其余合法参数和变体仍待扩展 |
| <a id="l1-12"></a>L1-12 cos | 零点、极值、正负输入、不同周期 | [`P-cos`](#p-cos) | 本批有限范围及各档结果已另立身份；其余合法参数和变体仍待扩展 |
| <a id="l1-13"></a>L1-13 exp | 零输入、正负输入、预先限定的有限动态范围 | [`P-exp`](#p-exp) | 本批有限范围及各档结果已另立身份；其余合法参数和变体仍待扩展 |
| <a id="l1-14"></a>L1-14 ln | 正输入、1 附近、接近零的合法范围 | [`P-ln`](#p-ln) | 本批有限范围及各档结果已另立身份；其余合法参数和变体仍待扩展 |
| <a id="l1-15"></a>L1-15 sqrt | 零、正输入、近零与尺度变化 | [`P-sqrt`](#p-sqrt) | 本批有限范围及各档结果已另立身份；其余合法参数和变体仍待扩展 |
| <a id="l1-16"></a>L1-16 pow | 合法底数与指数组合、零与负底数的适用条件 | [`P-pow`](#p-pow)、[`P-pow-half`](#p-pow-half) | 本批有限范围及各档结果已另立身份；其余合法参数和变体仍待扩展 |
| <a id="l1-17"></a>L1-17 电压访问与贡献 | 单端、差分、非零参考、贡献累加；单独改变输入、参考和供电 | [`F10`](#f10)、[`v2-main`](#old-v2-main)、[`v2-reference-zero`](#old-v2-reference-zero)、[`v2-supply-fixed`](#old-v2-supply-fixed)、[`v2-input-common-mode`](#old-v2-input-common-mode)、[`VR-01`](#old-vr-01)、[`VR-add`](#old-vr-add)、[`s1-default`](#old-s1-default)、[`s1-override`](#old-s1-override)、[`s1-default-reordered`](#old-s1-default-reordered) | 原供电对照按新规则复验；贡献重排补充条件尚未运行 |
| <a id="l1-18"></a>L1-18 静态电压反馈 | 有限唯一解的线性与非线性关系；正、负、零输入；核验输出解 | [`F11`](#f11)、[`F12`](#f12)、[`v7-linear-main`](#old-v7-linear-main)、[`v7-nonlinear-0.5`](#old-v7-nonlinear-0.5)、[`v7-nonlinear-2.0`](#old-v7-nonlinear-2.0)、[`NL-cubic`](#old-nl-cubic)、[`language`](#old-language) | 旧参数条件与新卡的同版复验；不外推到任意非线性关系 |
| <a id="l1-19"></a>L1-19 有界运行时循环 | 回调执行时决定次数；零次、一次、多次；顺序累加与最终循环变量 | [工程暴露的缺口](#engineering-gap-audit) | 冻结独立循环卡；不能用静态展开成绩替代 |

<a id="layer-2"></a>

### 第2层：单个动态算子与基本事件

| 能力 | 扩展目标 | 已有资料 | 待补测试或验收 |
| --- | --- | --- | --- |
| <a id="l2-01"></a>L2-01 initial_step | 常量及输入决定初态；输入低、高、等阈值；初始化一次 | [`F07`](#f07)、[`EC01`](#ec01)、[`e2-low`](#old-e2-low)、[`e2-clock-high`](#old-e2-clock-high)、[`e2-reset-high`](#old-e2-reset-high)、[`EV-HC-02`](#old-ev-hc-02) | 初始等阈值、只执行一次及输入决定初态的统一验收 |
| <a id="l2-02"></a>L2-02 输入驱动的 cross | 上升、下降、双向；穿越与不穿越；首次及重复事件；次数与读值 | [`F07`](#f07)、[`EC04`](#ec04)、[`e1-aligned`](#old-e1-aligned)、[`e1-shifted`](#old-e1-shifted)、[`e1-slow`](#old-e1-slow)、[`SH-X-RAMP`](#old-sh-x-ramp)、[`DS:positive`](#old-ds-positive)、[`DS:negative`](#old-ds-negative)、[`DS:small`](#old-ds-small) | 不穿越与双向独立卡；回调区间取证 |
| <a id="l2-03"></a>L2-03 固定 timer | 单次、周期、首次、末次、长期计数、允许时间范围 | [`F19`](#f19)、[`EC03`](#ec03)、[`TM-01`](#old-tm-01)、[`SI-01`](#old-si-01)、[`SH-T-RAMP`](#old-sh-t-ramp)、[`SH-T-SMALL`](#old-sh-t-small)、[`SH-T-LONG`](#old-sh-t-long) | 各类末次边界的规则与取证；保留原 32 次采样 |
| <a id="l2-04"></a>L2-04 动态 timer | 修改下次时刻、周期变化、关闭恢复、旧日程取消 | [`EC21`](#ec21)、[`calendar`](#old-calendar) | 现卡只提前一次 next，且语义假设待核实；其他变体待设计 |
| <a id="l2-05"></a>L2-05 事件 OR | 单来源、异刻、同刻；事件体次数、状态更新 | [`EC01`](#ec01)、[`EC22`](#ec22)、[`CO-SH-01`](#old-co-sh-01)、[`roots`](#old-roots) | 同刻合并与计数合同未决；异刻证据另存 |
| <a id="l2-06"></a>L2-06 transition | 初态、延迟、非对称沿、重复目标、中断、短脉冲队列 | [`F19`](#f19)、[`EC02`](#ec02)、[`TM-01`](#old-tm-01)、[`v5-main`](#old-v5-main) | 重复目标、同向中断与延迟队列；输入日程须独立核验 |
| <a id="l2-07"></a>L2-07 固定 absdelay | 非零初始历史、正延迟、延迟超过 stop、拐点平移 | [`F17`](#f17)、[`AD-ramp`](#old-ad-ramp)、[`AD-after-stop`](#old-ad-after-stop) | 旧 after-stop 条件的同版与新精度验收 |
| <a id="l2-08"></a>L2-08 固定 slew | 正负限速、未触限跟踪、平台追赶、反向与相交边界 | [`F18`](#f18)、[`SL-catch`](#old-sl-catch)、[`SL-reverse`](#old-sl-reverse)、[`SL-tracking`](#old-sl-tracking) | 保留旧未触限条件；统一精度与边界复验 |
| <a id="l2-09"></a>L2-09 idt | 非零初值、常量及变输入、正负面积、折点、复位与释放 | [`P-idt`](#p-idt)、[`F13`](#f13)、[`EC06`](#ec06)、[`d1-free`](#old-d1-free)、[`d1-reset`](#old-d1-reset)、[`CP-01`](#old-cp-01) | 原复位持续区间与释放按新规则复验；新卡的 Spectre Q3 终点资料待核 |
| <a id="l2-10"></a>L2-10 idtmod | 初相、模数、偏置、正负频率、变频、多次环回及两侧读值 | [`F20`](#f20)、[`EC17`](#ec17)、[`EC18`](#ec18)、[`d2-constant`](#old-d2-constant)、[`d2-chirp`](#old-d2-chirp)、[`CP-02`](#old-cp-02) | 不同模数、长期累计及原始相位环回取证 |
| <a id="l2-11"></a>L2-11 ddt | 常量、正负斜坡、光滑曲线、启动与折点单侧值 | [`P-ddt`](#p-ddt)、[`P-ddt-input`](#p-ddt-input)、[`F14`](#f14)、[`DDT-pwl`](#old-ddt-pwl) | 常量及负斜率独立卡；旧折点的阶段与单侧观察；新光滑卡的配置及拒绝诊断 |
| <a id="l2-12"></a>L2-12 一阶 laplace_nd | DC 增益、时间常数、非零启动；阶跃、斜坡、正弦幅相 | [`F15`](#f15)、[`v6-standard`](#old-v6-standard)、[`LP-nd`](#old-lp-nd)、[`LP-RAMP`](#old-lp-ramp)、[`LP-NONZERO`](#old-lp-nonzero)、[`LP-SMALL`](#old-lp-small) | 阶跃与正弦幅相；保留旧小信号和短时间常数 |
| <a id="l2-13"></a>L2-13 一阶 laplace_np | 一阶响应、极点表达、独立参数换算；阶跃、斜坡、正弦幅相 | [`F16`](#f16)、[`LP-np`](#old-lp-np) | 一般参数与正弦幅相；现新卡只核验指定二进制参数 |
| <a id="l2-14"></a>L2-14 高阶连续滤波 | 至少二阶实极点及共轭极点；启动、幅相、全部历史状态 | [`EC11`](#ec11) | 共轭极点、正弦幅相；现卡仅二阶重复实极点 |
| <a id="l2-15"></a>L2-15 $bound_step | 固定、条件及状态相关上限；不活跃请求；阶段切换 | [工程暴露的缺口](#engineering-gap-audit) | 波形精度与步长契约分别取证；数值正确不能单独证明上限生效 |

<a id="layer-3"></a>

### 第3层：简单组合

| 能力 | 扩展目标 | 已有资料 | 待补测试或验收 |
| --- | --- | --- | --- |
| <a id="l3-01"></a>L3-01 采样保持 | 定时及穿越时钟；初态、采样值、保持、次数；变化输入附近采样 | [`EV-SH-01`](#old-ev-sh-01)、[`SH-T-RAMP`](#old-sh-t-ramp)、[`SH-X-RAMP`](#old-sh-x-ramp)、[`SH-T-SMALL`](#old-sh-t-small)、[`SH-T-LONG`](#old-sh-t-long)、[`DS:positive`](#old-ds-positive)、[`DS:negative`](#old-ds-negative)、[`DS:small`](#old-ds-small) | 阈值采样完整回调资格；不同尺度与时长保留 |
| <a id="l3-02"></a>L3-02 采样、复位与输出边沿 | 复位抑制、释放恢复、边沿启动与中断；显式优先级 | [`EC01`](#ec01)、[`v4-c0`](#old-v4-c0)、[`v4-c1`](#old-v4-c1)、[`e2-low`](#old-e2-low)、[`e2-clock-high`](#old-e2-clock-high)、[`e2-reset-high`](#old-e2-reset-high)、[`CO-SH-01`](#old-co-sh-01) | 初始化变体及回调区间；同刻复杂交互另列 L5-05 |
| <a id="l3-03"></a>L3-03 迟滞比较器与边沿 | 高低输入启动、上下阈值、区间内保持、快速反向 | [`EC02`](#ec02)、[`v3-main`](#old-v3-main)、[`EV-HC-01`](#old-ev-hc-01)、[`EV-HC-02`](#old-ev-hc-02)、[`CO-HC-01`](#old-co-hc-01) | 原高输入启动与新短脉冲的共同验收 |
| <a id="l3-04"></a>L3-04 采样保持后积分 | 非零初态、分段面积、末次回调、误差向积分传播；线性及非线性输入 | [`EC03`](#ec03)、[`EC04`](#ec04)、[`STROBE-TIMER-IDT`](#old-strobe-timer-idt) | EC03 的 stop 附加要求单独解释；EC04 非线性根回调取证 |
| <a id="l3-05"></a>L3-05 积分级联与复位 | 上游复位、保持、释放；下游保留已有面积 | [`EC07`](#ec07)、[`d1-reset`](#old-d1-reset) | 当前卡完整验收；多轮复位及不同释放时序 |
| <a id="l3-06"></a>L3-06 非线性输入与滤波直通项 | 非零初态、输入反向、直通与历史项、内部输入折点 | [`EC12`](#ec12)、[`FD:ramp`](#old-fd-ramp)、[`FD:reverse`](#old-fd-reverse)、[`FD:nondyadic`](#old-fd-nondyadic) | 保留旧非整数系数；按共同预算补验 |
| <a id="l3-07"></a>L3-07 滤波与微分组合 | 滤波后内部导数、输入导数进入直通项、DC 与瞬态阶段、折点 | [`EC11`](#ec11)、[`EC16`](#ec16) | 阶段证据、光滑输入及共轭极点组合 |
| <a id="l3-08"></a>L3-08 延迟级联 | 各级历史、拐点平移、独立并行延迟、短脉冲 | [`EC14`](#ec14)、[`projected`](#old-projected) | 短脉冲、更深级联；原 projected 另有 slew 消费者 |
| <a id="l3-09"></a>L3-09 限速及延迟限速级联 | 各级历史、平台追赶、反向、短脉冲、延迟后限速 | [`EC15`](#ec15)、[`SC:ramp`](#old-sc-ramp)、[`SC:catch`](#old-sc-catch)、[`SC:reverse`](#old-sc-reverse)、[`projected`](#old-projected) | 独立延迟后限速卡、短脉冲及更深级联 |
| <a id="l3-10"></a>L3-10 中断边沿后积分 | 边沿中断、反向、下游面积与已有历史 | [`EC05`](#ec05) | EC05-Q-v2 已另定共同回调历史与独立面积判据；原探针及成绩保留，见[本轮证据](../../../experiments/backends/support/README.md#legacy-chain-q)。 |
| <a id="l3-11"></a>L3-11 数组的事件状态更新 | 初始化、异刻更新、非幂等计数、各元素状态保留 | [`F07`](#f07)、[`LANG-array-events`](#old-lang-array-events) | 不同元素与来源的隔离变体；同刻交互另列 L5-05 |
| <a id="l3-12"></a>L3-12 动态电压与边沿相乘 | 斜坡或连续保持电压乘 transition；起止边界、中断、实例隔离 | [工程暴露的缺口](#engineering-gap-audit) | 独立乘积卡与滤波消费者；不能借单算子成绩 |
| <a id="l3-13"></a>L3-13 事件数学与最终统计 | 状态相关除法、平方根、增益与 RMS；无样本和无效分母分支 | [工程暴露的缺口](#engineering-gap-audit) | 冻结统计量及单位；错误分支不能靠删样本通过 |
| <a id="l3-14"></a>L3-14 跨事件数组索引 | 计数、pending、取消、复位与实际读写的关系；边界元素 | [工程暴露的缺口](#engineering-gap-audit) | 独立合法索引与拒绝控制；不能直接把推断裁成数组范围 |

<a id="layer-4"></a>

### 第4层：完整工程信号链

| 能力 | 扩展目标 | 已有资料 | 待补测试或验收 |
| --- | --- | --- | --- |
| <a id="l4-01"></a>L4-01 采样→保持→边沿→滤波 | 正常采样、复位、中断、实例隔离；各级历史；普通查询与 strobe | [`SEF-TIMER`](#old-sef-timer)、[`SEF-RESET`](#old-sef-reset)、[`SEF-INTERRUPT`](#old-sef-interrupt)、[`SEF-ISOLATION`](#old-sef-isolation)、[`ST:SEF-TIMER`](#old-st-sef-timer)、[`ST:SEF-INTERRUPT`](#old-st-sef-interrupt)、[`ST:SEF-ISOLATION`](#old-st-sef-isolation) | 原 18 条已接受差异范围不扩大；四后端统一精度与同版复验 |
| <a id="l4-02"></a>L4-02 滤波→采样保持 | 读取实际滤波状态；快速变化及折点附近采样；后续保持 | [`c2-main`](#old-c2-main) | 已有旧模型，待新精度与关键边界复验 |
| <a id="l4-03"></a>L4-03 电压求解→延迟→采样 | 电压求解、延迟启动历史、周期读值、快变和折点附近采样 | [`EC13`](#ec13)、[`projected`](#old-projected) | 保留 stop 附加要求；补快变及折点附近采样 |
| <a id="l4-04"></a>L4-04 VCO 与相位消费者 | 变频、限频、门控、长期相位；正弦与相位触发 cross | [`F20`](#f20)、[`EC17`](#ec17)、[`EC18`](#ec18)、[`d2-constant`](#old-d2-constant)、[`d2-chirp`](#old-d2-chirp)、[`CP-01`](#old-cp-01)、[`CP-02`](#old-cp-02)、[`CO-VCO-01`](#old-co-vco-01) | 门控、长期相位、相位 cross；保留原限频模型 |
| <a id="l4-05"></a>L4-05 量化器与 ADC 码流 | 码转换阈值、端码、饱和、采样更新与逐次读取 | 本清单暂无独立对比卡 | 尚未冻结仿真器对比卡，不能借 AI benchmark 成绩 |

<a id="layer-5"></a>

### 第5层：复杂交互

| 能力 | 扩展目标 | 已有资料 | 待补测试或验收 |
| --- | --- | --- | --- |
| <a id="l5-01"></a>L5-01 多通道与实例隔离 | 不同输入、参数、初态、时钟；单路改变、复位、声明交换 | [`EC06`](#ec06)、[`EC19`](#ec19)、[`c1-main`](#old-c1-main)、[`c1-swapped`](#old-c1-swapped)、[`c1-no-reset-a`](#old-c1-no-reset-a)、[`SI-01`](#old-si-01)、[`histories`](#old-histories)、[`reset_filter`](#old-reset_filter)、[`SEF-ISOLATION`](#old-sef-isolation) | 相位实例、积分实例和采样实例分别验收；原独立滤波历史保留 |
| <a id="l5-02"></a>L5-02 连续动态联合反馈 | 积分、滤波共同状态；非线性反馈；实际轨迹与独立答案 | [`EC09`](#ec09)、[`NA:nonlinear`](#old-na-nonlinear)、[`LP-IDT`](#old-lp-idt) | 多初态、参数变化；保留原放大输出误差要求 |
| <a id="l5-03"></a>L5-03 事件改变连续动态 | 改变积分速度、系数、阈值或日程；保留历史、重预测未来事件 | [`EC08`](#ec08)、[`EC10`](#ec10)、[`EC21`](#ec21)、[`NA:event-continuation`](#old-na-event-continuation)、[`calendar`](#old-calendar)、[`roots`](#old-roots)、[`reset_filter`](#old-reset_filter) | 多轮切换及取消旧根；EC21 的 timer 假设不作为已确认语言结论 |
| <a id="l5-04"></a>L5-04 近邻事件与下游历史 | 近而不同的时刻、先后次序、计数、采样、积分、边沿与滤波 | [`EC20`](#ec20)、[`NT:fixed`](#old-nt-fixed)、[`NT:held`](#old-nt-held)、[`NT:chain`](#old-nt-chain) | 新 EC20 不替代旧整链；补统一精度与完整顺序取证 |
| <a id="l5-05"></a>L5-05 同刻事件 | 显式优先级、回调次数、状态更新、下游历史 | [`EC22`](#ec22)、[`roots`](#old-roots) | EC22 的同刻 OR 合同未定；异刻 roots 不能代替同刻验收 |
| <a id="l5-06"></a>L5-06 内部状态触发反馈事件 | 积分或滤波触发 cross；事件反过来改变动态；重复事件顺序 | [`EC23`](#ec23) | 自换向探针先确认模型、参考及事件历史；不修改 #131 |
| <a id="l5-07"></a>L5-07 隐式连续关系与复位 | 初始解、分支延续、复位与释放、无关状态保留；追加只读事件和系数切换变体 | [`EC24`](#ec24)、[`implicit`](#old-implicit) | 旧无复位模型继续保留；新复位探针待合同与参考资格 |

<a id="engineering-gap-audit"></a>

## 工程暴露的覆盖缺口与共同交付

当前主表能说明固定用例通过，不能说明所有同名语言特性或工程组合都通过。数组固定范围只含静态下标；函数卡检查电压表达式；单独 transition 的通过也不包含动态电压乘边沿。这些范围与新工程需求之间有明确空缺。

R01 原70请求在固定 main `efd17ed6` 的复验中，23条通过原 checker，47条明确拒绝。它们采用原任务预算，不是本表的新Q成绩；完整原资产与运行资料尚为本地保留材料，[复验摘要与逐项身份](../../../experiments/backends/support/r01-main70-summary.json)保存计数、原请求ID、输入与判据哈希及其可用范围；它不提供完整raw的公共复现。这组工程反馈用于提出需求，不能直接充当独立论文评价集。

| 原工程障碍 | 原请求数 | 五层目录归属 | 必须补出的独立测试 |
| --- | ---: | --- | --- |
| 联合仿射准入限制 | 23 | [L3-12](#l3-12)，并在第4层验证读出整链 | 已知斜坡乘边沿、连续积分电压乘边沿、下游滤波；同步和MUX是原任务回归 |
| 动态步长限制 | 12 | [L2-15](#l2-15)，第5层补阶段切换 | 固定及变化上限；reset、采集、注入三阶段；更紧上限与不活跃请求 |
| 隐式动态不能与事件组合 | 3 | [L5-07](#l5-07)追加变体 | 独立初态、只读观测事件、系数切换、复位与释放；检查无关历史 |
| 有界运行时循环 | 3 | [L1-19](#l1-19) | 当刻n决定0、1、多个迭代；顺序累加；第二次事件改n，最终状态与记录核对 |
| final_step统计除法 | 3 | [L3-13](#l3-13) | 固定已知样本的增益、失调及RMS；样本不足、零分母分支；事件算术与日志 |
| MUX数组下界证明 | 3 | [L3-14](#l3-14) | 初态零、有效采集后才写、提前取消、复位、首尾元素与独立实例 |

这47条按该次复验的首个障碍归类，不代表47个独立漏洞，也不承诺修一条规则就恢复全部关联请求。源码中有电压乘transition的读出形式，但尚未逐条运行定位版内核确认每个拒绝的首个乘法表达式。

<a id="event-statistics-development"></a>

IR22 统计修复已让原 `gain-0`、`gain-1`、`gain-2` 完整通过原 checker和实际 Spectre有限配对，
原120秒预算、VA及历史失败保持。这三条分别保留新结果，没有将上面旧23/70改成当前main的新总数。
[四项独立控制](../event_statistics/README.md)补出L3-13的固定样本拟合、停止边界、语句顺序和无样本分支；
定义域拒绝、非法IR、隔离门禁、失败回退及查询不变由开发回归另查。
这仍是有限开发证据，统计量的共同Q单位、四后端配置和精度扫描尚未完成，不能把L3-13加入主表为Q通过。

九条已完成请求另有输入配对失败，已从原生值与原PWL复算为保存网格漏折点后的插值差异。它们不加入上述47条，原共同配对成绩仍为14/23。后续观察集必须包括输入折点、关键事件及两侧；没有折点或插值误差界时，不能把直线插值当成真实轨迹。这个观察要求适用于各层，不另算一个语言能力。

### 每项修复与每行比较一起验收

一项共同交付包含原工程回归和独立比较卡，分别保留判据：

1. 原请求保留VA、刺激、精度、超时与原checker，说明完整执行是否增加。修复旧报错后出现新报错，仍是未完成。
2. 独立卡先固定数学或语义答案，再校准正确与错误输出。增加参数、初态和等价写法，避免只适配原失败源码；含初始化、关键边界、消费者及失败回退。
3. 四后端使用同一张独立卡与共同Q要求，各自选择已校准配置，记录实际生效参数。统计量需声明单位或电压编码，不能直接把电压门槛套到时间和计数。
4. 完成一档全部必测项和取证后，才在主表追加支持结论。工程原2mV判据通过不转为Q3；缺配置、回调或原生观察时保留缺证，不能只看数字。

原工程资产是回归，不是未经开发使用的留出集。新卡可以源于这些需求，但数学答案不能来自EVAS输出；论文确认集应另留未用于修复的参数或模型，并固定版本。旧行继续按原范围报告；新增能力行按层次追加，原顺序、行ID、模型和成绩不变。

### 首批共同目标

先处理L3-12。原请求ID为`r01-integrate-sync/core-boundary`和`r01-integrate-sync/c0`，可在[逐项摘要](../../../experiments/backends/support/r01-main70-summary.json)核对。core-boundary使用非物理core检查连接与读出责任；c0使用原采样保持core，是完整原电路目标。前者不能替代后者通过，两份原请求均不改。独立卡同时包含时变输入、保持状态和滤波消费者，以区分单算子成功与组合成功。乘积准入解除后可能还需要动态步长或历史能力，不能提前声明整题完成。

本批[同步读出实测](../../../experiments/backends/support/r01-sync-readout/README.md)使两份请求完整执行，物理c0在原120秒内完成9001行；原checker仍因严格阈值状态差异失败。三张独立乘积卡完成有限数值核对，普通/中断边沿的两个滤波消费者尚未完成。关键边界与外部取证资格未齐，不授予L3-12新Q成绩，原47条失败分母和旧结果保持。

随后处理L2-15及其连续动态消费者。步长上限是否遵守需实际接受网格或可核对的求解控制证据；没有该证据不能由准确波形推断。符号或解析传播的路径也要明确控制契约，不虚构不存在的数值积分网格。

运行时循环、最终统计、跨事件索引作为各自的小包，使用同一共同交付规则；实际完成范围按本页各项证据记录，规划不等于通过。#131不修改；原已接受边界差异不因扩表被重新列为缺陷。

<a id="shared-variants"></a>

## 后续测试的跨层变体

这些要求指导后续扩展；本版已经采用的变体以固定用例为准，不自动把计划加入本版分母。
它们附在适用能力行下，不单独增加层次，也不机械排列所有参数组合。
每张新卡在运行前写明采用哪些变体、各自能检出什么错误；不适用的注明理由。

| 变体 | 适用范围与验收目的 | 保留的已有例子 |
| --- | --- | --- |
| 小信号与幅度变化 | 采样、积分、滤波、非线性求解，检查绝对误差与状态误差传播 | SH-T-SMALL、LP-SMALL、DS:small |
| 长时间与重复事件 | timer、采样、idt、idtmod，检查计数、漂移和历史累积 | SH-T-LONG 的 32 次采样 |
| 初态与输入变化 | 所有有状态算子，区分输入决定初态、非零初态和中途变化 | LP-NONZERO、e2、EV-HC-02 |
| 边界与观察方式 | 事件及连续历史组合，核验边界两侧、普通查询、strobe 和查询加密 | SEF/ST、NT、确认集两张查询网格 |
| 顺序与隔离 | 贡献、数组、层次、多个状态，分别检查绝对答案和单路变化 | F09/F10、原 c1、EC06、EC19 |

查询加密用于检查已规定观察上的一致性，不宣称全时域证明。关键边界不直接排除。
同一条合法事件历史必须解释状态、采样值及全部下游输出；精度档位和后端配置沿用
[评测标准](../../docs/COMPARISON-METHODOLOGY.md#precision-tiers-proposal)，本次不改变数值门槛。

<a id="duplicates"></a>

## 重复执行与不同条件怎样区分

| 关系 | 登记方式 |
| --- | --- |
| 同一 SEF 模型增加 strobe | 仍是同一电路，追加观察方式与执行记录；强制点义务不能删除 |
| 确认集七模型使用稀疏、加密两张网格 | 七模型、十四次执行，不写成十四类行为 |
| 原八条件的 v1、v2、配置绑定、修复复验 | 保留不同判据、配置和工具身份，不按运行次数扩大行为数量 |
| F09/F10 重排；EC06 v2 重排 | 同组必测变体；EC06 同时交换实例和贡献，不能单独归因某一种顺序 |
| EC11/EC12 v2 | 输入斜坡新增内部折点，初值不变；是行为变体，不是单纯重新运行 |
| ND 与 NP 写法 | 数学响应可相同，但语言接口不同，各自保留能力行 |
| 小信号、长序列、不同复位或不同下游消费者 | 不同条件，不能按相同算子名合并；SEF 与 EC01、NT:chain 与 EC20 均不等价 |
| s1-default-reordered | 原 31 之外的新增编码条件，已设计但未运行，不回填原分母 |

<a id="exploratory-cases"></a>

## 判据尚未确定的探针

EC05-v1、EC22、EC23、EC24 的原探针继续保留模型、执行结果、失败和原评测位置。
EC05 另立 EC05-Q-v2，以独立中断折线面积验收，原探针成绩不变。EC22–EC24 的完整参考仍未确认。
EC21 虽有原档位通过记录，timer 重新读取 next 的语义仍依赖未核实假设，也不据此授予新版通用支持。
它们进入新版正式验收前，先固定合法模型、数学或语义答案、事件规则及校准。
只有这类材料的能力不列入本版支持主表，保留在本节计划中，不把它解释成四个后端均不支持。
尚未定稿的 ID 为 L2-04、L5-05、L5-06、L5-07；L3-10 的新版范围另列下文。L4-05 ADC 暂无独立对比卡，也只列计划。

这不改变历史 breadth 的 44 组、71 变体、852 个评测位置，也不重算原 P/F/I 或移除失败。
后端失败本身不是转为探针的理由；这里沿用原卡已经记录的参考限制。
同刻事件和隐式复位能力仍留在五层规划，不因待定而删除。

<a id="summary-scopes"></a>

## 本版主表的固定必测范围

本版范围记为 **comparison-scope-v1（2026-10-12）**。每行以下表列出的全部用例与变体为准，
未来扩展不计入这一版，也不使本版通过重新变成“部分”。同一行四后端使用同一集合。
这次固定范围是对已有资产的整理，不是新的论文留出集，也不是重新计算原成绩。

基础行优先使用已有独立卡；工程行按模型、消费者或事件方式分开。
例如三次幂与半次幂、定时采样与阈值采样、原近邻整链与新增相邻浮点用例分别呈现。
这种拆分保留每种写法的结果，不挑出成功变体来缩小原组要求。

表内 F/EC 组一律包含固定收据登记的**全部 mandatory_variants**。
P 卡包含本卡的全部有限观察、起止点和输入折点；V 卡包含完整绑定要求。
所有原模型、初态、事件窗口、预算、checker、配置和失败保持原身份。
只检查窗外的历史结果不能授予本版打勾；未定稿探针继续保留原执行槽位。

同一能力的不同用例可以采用不同的原协议，因此不能把它们拼成统一通过率。
✓ Q2 只表示全部必测用例已取得 Q2 完整资格；Q3 的拒绝、超差或缺证照常保留。
旧预算不换算成 Q 档。主表没有展示的历史成绩也不被替代，下文仍逐项登记。

| 来源代号 | 固定来源及工具身份 |
| --- | --- |
| B | [新44组固定版本](#breadth-44)。EVAS 候选 `519d5e28`；F/EC 源码和收据固定于 `814da00d`，未合入实现不算 main 支持。 |
| P | [独立基础卡](#finite-primitives)。EVAS main 检查点 `a64c2ad0`；原120位置和六项 sin 校准分开保存。 |
| V | [八条件配置绑定](precision-bindings-v1.json)。EVAS `826fefb1`；精度依据为各条件原三档完整绑定资格。 |
| ST | [原定时 strobe 对照](../../../experiments/backends/strobe/README.md#timer-fix)。固定原模型，采用整合及 main 复验身份，不改原100 ps条件。 |
| SEF | [原采样滤波及 main 复验](../../../experiments/backends/sample-edge-filter/README.md)。四模型按 PR #123 集成收据，ST 三观察另按 `fc7e57fd` 复验；并列范围，不是一次同版全量执行。 |
| NT | [原近邻 timer 及 main 复验](../../../experiments/backends/strobe/README.md#near-timer)。原三模型收据与 `fc7e57fd` 复验；使用各自原预算。 |
| OLD | [原31条件](#legacy-31)。保留 c2-main 原成绩；2026-10-13 的 Q 补验另立身份，不转授其他原31条件。 |
| Q-CHAIN | [旧整链 Q 补验](../../../experiments/backends/support/README.md#legacy-chain-q)。EVAS 生产代码对应 main `7344e4db`；新强制观察、只读回调与分析来源分别记录。 |
| Q-AREA | [EC05-Q-v2](../../../experiments/backends/support/README.md#legacy-chain-q)。保留 EC05-v1 源码，新建独立面积验收；EVAS 实现纳入 0.15.0，执行仍绑定发布前候选；原两种开源方案尚无新版 Q 结果。 |

两类导数和八张组合卡另用 `e2d8cbf8` 构建进行实际复验，实现已随 #167 合入 main `e028f96d`。
[原收据](../../../experiments/backends/support/20261013-capability-gaps.json)保留执行时的候选身份。
[新版根窗口批次](../../../experiments/backends/support/README.md#root-window-v3)复测 SH-X-RAMP 与 EC04-v1，
共18个配置：EVAS原模型6个、Spectre原模型6个、Spectre只读回调模型6个。它们是已有用例的重复执行，
不增加独立用例数或更换必测范围。新旧判据和成绩分开保存；其他行不算 main 同版全量验收。

**2026-10-13 补充范围 v1.1** 另立旧整链 Q 验收和 EC05-Q-v2。旧整链仍为
STROBE-TIMER-IDT、SEF四电路及三观察、c2-main、NT三模型，共12个条件。
模型、初态、原事件范围、旧 checker 和成绩不变。新 Q 观察保留旧请求并添加关键边界强制点，
不宣称原普通查询执行已经复现。旧 checker 在新波形上的重审也与历史运行分开。
EC05-Q-v2 保留原 EC05-v1 源码，单独增加参考、回调取证和边界观察。
这是新验收身份，不回写原44组852个位置。来源、实际配置和逐档结果见
[本轮证据](../../../experiments/backends/support/README.md#legacy-chain-q)。

主表结果按下列范围引用，版本和收据随来源保留。不同版本的结果不能解释为同一最新版的整体支持。
函数卡中写作 π 的输入，实际使用冻结源码里的 binary64 近似值；参考答案按这些实际操作数计算。

### 第1层的固定用例

| 主表行 | 全部必测用例 | 本版范围与限制 |
| --- | --- | --- |
| <a id="scope-l1-01"></a>[L1-01](#l1-01) 宏与 include（含实例） | B：[`F01`](#f01) | F01-base：对象宏、函数宏、include 与实例参数；层次实例是本卡依赖，不据层次失败认定宏不支持。 |
| <a id="scope-l1-02"></a>[L1-02](#l1-02) 参数 | B：[`F01`](#f01)、[`F09`](#f09) | 默认与覆盖参数；F09-base、F09-reordered 均必测，检查两级参数传递与交换声明。 |
| <a id="scope-l1-03"></a>[L1-03](#l1-03) 条件与逻辑表达式 | B：[`F03`](#f03)、[`F05`](#f05) | F03 的12个 DC 边界输入，加 F05 全部函数分支变体；输入邻点不能合并。 |
| <a id="scope-l1-04"></a>[L1-04](#l1-04) case 分支 | B：[`F04`](#f04) | F04-dc-0 至 F04-dc-4：首次匹配、其他分支及 default；动态 case 另列计划。 |
| <a id="scope-l1-05"></a>[L1-05](#l1-05) 顺序赋值 | B：[`F02`](#f02)、[`F05`](#f05) | 顺序局部量与贡献快照；函数分支内赋值，F02/F05 全部变体。 |
| <a id="scope-l1-06"></a>[L1-06](#l1-06) 用户函数 | B：[`F05`](#f05) | F05 的动态输入及三个 DC 输入，验证参数、局部量和分支；未包含嵌套调用。 |
| <a id="scope-l1-07"></a>[L1-07](#l1-07) 静态循环 | B：[`F06`](#f06) | F06-base 的固定循环次数、顺序累加和所有数组输出；零次与一次循环另列计划。 |
| <a id="scope-l1-08"></a>[L1-08](#l1-08) 变量数组：静态下标 | B：[`F06`](#f06) | F06-base 中全部声明元素与静态下标；与循环行共用执行，不重复计数。 |
| <a id="scope-l1-09"></a>[L1-09](#l1-09) 电气向量 | B：[`F08`](#f08) | F08-base 的全部向量位，分别驱动并读取；不外推到相反声明方向。 |
| <a id="scope-l1-10"></a>[L1-10](#l1-10) 模块层次 | B：[`F09`](#f09) | F09 两个必测变体：原声明与重排声明，所有内部节点和输出一起验收。 |
| <a id="scope-l1-11"></a>[L1-11](#l1-11) sin | P：[`P-sin`](#p-sin) | 输入折点为 −4π、−π/2、0、π/2、4π；全部原生观察与折点验收，追加原 Q3 配置校准。 |
| <a id="scope-l1-12"></a>[L1-12](#l1-12) cos | P：[`P-cos`](#p-cos) | 输入折点为 −4π、−π、0、π、4π；包含折点及段内观察。 |
| <a id="scope-l1-13"></a>[L1-13](#l1-13) exp | P：[`P-exp`](#p-exp) | 输入折点为 −4、−1、0、1、4；限定有限动态范围。 |
| <a id="scope-l1-14"></a>[L1-14](#l1-14) ln | P：[`P-ln`](#p-ln) | 输入折点为 10⁻⁶、0.25、1、2、8，均为正值。 |
| <a id="scope-l1-15"></a>[L1-15](#l1-15) sqrt | P：[`P-sqrt`](#p-sqrt) | 输入折点为 0、10⁻¹²、10⁻⁶、0.25、4；近零输入与输出误差共同核验。 |
| <a id="scope-l1-16-cube"></a>[L1-16](#l1-16) pow：三次幂 | P：[`P-pow`](#p-pow) | 指数固定为3，底数折点为 −2、−1、0、1、2。 |
| <a id="scope-l1-16-half"></a>[L1-16](#l1-16) pow：半次幂 | P：[`P-pow-half`](#p-pow-half) | 指数固定为0.5，底数折点为 0、10⁻¹²、10⁻⁶、0.25、4；不与三次幂合并报通过。 |
| <a id="scope-l1-17"></a>[L1-17](#l1-17) 电压访问与贡献 | B：[`F10`](#f10) | F10-base、F10-reordered、F10-common-mode：非零参考、差分访问、贡献重排与共模变化。 |
| <a id="scope-l1-18"></a>[L1-18](#l1-18) 静态电压反馈 | B：[`F11`](#f11)、[`F12`](#f12) | 唯一仿射解与单调三次解，F11/F12 的全部已冻结输入变体；不外推到任意非线性关系。 |

### 第2层的固定用例

| 主表行 | 全部必测用例 | 本版范围与限制 |
| --- | --- | --- |
| <a id="scope-l2-01"></a>[L2-01](#l2-01) initial_step：事件状态初始化 | B：[`F07`](#f07)、[`EC01`](#ec01) | F07/EC01 的固定初态及后续事件状态；整卡验收，不能仅截取初始输出。 |
| <a id="scope-l2-02"></a>[L2-02](#l2-02) cross：斜坡穿越 | V：[`SH-X-RAMP`](#old-sh-x-ramp) | SH-X-RAMP 全部8次穿越、回调区间、采样值、保持阶段；与 L3-01 阈值行共用用例。 |
| <a id="scope-l2-03"></a>[L2-03](#l2-03) 固定 timer | V：[`SH-T-RAMP`](#old-sh-t-ramp)、[`SH-T-SMALL`](#old-sh-t-small)、[`SH-T-LONG`](#old-sh-t-long) | 1 V 斜坡、1 mV 斜坡各8次，常量32次；初态、回调、读值与保持全部必测。 |
| <a id="scope-l2-05"></a>[L2-05](#l2-05) 事件 OR：采样与复位 | B：[`EC01`](#ec01) | EC01-v1 的异刻采样与复位、显式优先级及完整输出；同刻 OR 的 EC22 不在本版范围。 |
| <a id="scope-l2-06"></a>[L2-06](#l2-06) transition：定时非对称沿 | B：[`F19`](#f19) | F19 全部固定变体：启动、正延迟、非对称完整沿及周期；中断边沿另有组合卡。 |
| <a id="scope-l2-07"></a>[L2-07](#l2-07) 固定 absdelay | B：[`F17`](#f17) | F17 全部启动历史与固定延迟变体，核验初始值和折点平移。 |
| <a id="scope-l2-08"></a>[L2-08](#l2-08) 固定 slew | B：[`F18`](#f18) | F18-base：非对称限速、反向追赶与所有边界观察。 |
| <a id="scope-l2-09"></a>[L2-09](#l2-09) idt：非零初值与正负面积 | P：[`P-idt`](#p-idt) | 初值0.125，输入折点0、1、−1、0，全部有限观察含起止点；本卡不含复位。 |
| <a id="scope-l2-10"></a>[L2-10](#l2-10) idtmod：原始相位与环回 | B：[`F20`](#f20)、[`EC18`](#ec18) | F20 的相位和正弦，加 EC18 的负频率与非零偏置；原始相位环回两侧不能省略。 |
| <a id="scope-l2-11-time"></a>[L2-11](#l2-11) ddt：二次时间表达式 | P：[`P-ddt`](#p-ddt) | ddt(($abstime/T)²)×T，独立答案2t/T；包含启动、段内和终点。 |
| <a id="scope-l2-11-input"></a>[L2-11](#l2-11) ddt：电压斜坡平方 | P：[`P-ddt-input`](#p-ddt-input) | ddt(V(u)²)×T，斜坡延续到 stop 之后；独立答案2t/T。 |
| <a id="scope-l2-12"></a>[L2-12](#l2-12) 一阶 laplace_nd | V：[`LP-RAMP`](#old-lp-ramp)、[`LP-NONZERO`](#old-lp-nonzero)、[`LP-SMALL`](#old-lp-small) | 斜坡、0.25 V 非零 DC 初态、1 mV 小信号；每个条件的全部观察及折点两侧。 |
| <a id="scope-l2-13"></a>[L2-13](#l2-13) 一阶 laplace_np | B：[`F16`](#f16) | F16 的指定二进制参数与等价一阶响应；不包含任意极点参数。 |
| <a id="scope-l2-14"></a>[L2-14](#l2-14) 二阶滤波（内部微分） | B：[`EC11`](#ec11) | EC11-v1/v2：重复实极点，含内部导数，v2 的内部输入折点也必测。 |

### 第3层的固定用例

| 主表行 | 全部必测用例 | 本版范围与限制 |
| --- | --- | --- |
| <a id="scope-l3-01-timer"></a>[L3-01](#l3-01) 采样保持：定时 | V：[`SH-T-RAMP`](#old-sh-t-ramp)、[`SH-T-SMALL`](#old-sh-t-small)、[`SH-T-LONG`](#old-sh-t-long) | 同固定 timer 行的三卡；额外明确采样值及每段保持，全部三卡一起通过才打勾。 |
| <a id="scope-l3-01-cross"></a>[L3-01](#l3-01) 采样保持：阈值 | V：[`SH-X-RAMP`](#old-sh-x-ramp) | 完整8次穿越及其读值、保持；不借定时采样通过授予资格。 |
| <a id="scope-l3-02"></a>[L3-02](#l3-02) 采样、复位与输出边沿 | B：[`EC01`](#ec01) | EC01-v1 的固定时序、复位优先级和完整边沿输出。 |
| <a id="scope-l3-03"></a>[L3-03](#l3-03) 迟滞比较器与边沿 | B：[`EC02`](#ec02) | EC02-v1：迟滞阈值、非对称边沿与短脉冲反转，全部输出必测。 |
| <a id="scope-l3-04-timer"></a>[L3-04](#l3-04) 定时采样→积分：原模型 | ST：[`STROBE-TIMER-IDT`](#old-strobe-timer-idt) | 原 TT=100 ps、100 µV 判据与历史成绩保留；Q补验保留原请求，增加有限边界强制点，不借10 ps/1 ps诊断替代本卡。 |
| <a id="scope-l3-04-ordered"></a>[L3-04](#l3-04) 采样→积分：停止边界与非线性 | B：[`EC03`](#ec03)、[`EC04`](#ec04) | EC03 stop 的末次回调和 EC04 的非线性输入全部验收；不截掉停止时刻。 |
| <a id="scope-l3-05"></a>[L3-05](#l3-05) 积分级联与复位 | B：[`EC07`](#ec07) | EC07-v1：上游复位、保持与释放，下游保留已有面积。 |
| <a id="scope-l3-06"></a>[L3-06](#l3-06) 非线性输入与滤波直通项 | B：[`EC12`](#ec12) | EC12-v1/v2 全部变体：非零 DC 初态、多项式输入，v2 内部折点。 |
| <a id="scope-l3-07"></a>[L3-07](#l3-07) 滤波与微分：DC 直通项 | B：[`EC16`](#ec16) | EC16-v1 的 DC 导数与瞬态直通输出；不以二阶滤波 EC11 的通过代替。 |
| <a id="scope-l3-08"></a>[L3-08](#l3-08) 两个固定延迟的历史 | B：[`EC14`](#ec14) | EC14-v1 的全部两路延迟与输出，独立并行历史。 |
| <a id="scope-l3-09"></a>[L3-09](#l3-09) 两级 slew 与反向追赶 | B：[`EC15`](#ec15) | EC15-v1 的两级非对称 slew 与全部反向边界观察；不含任意深度级联。 |
| <a id="scope-l3-10"></a>[L3-10](#l3-10) 中断边沿后积分 | Q-AREA：[`EC05`](#ec05) / EC05-Q-v2 | 原上升与反向沿、0.1 V 非零积分初值；完整两次回调、边沿起止点两侧与全部输出。保留旧探针成绩；新 Q 结论分别属于 EVAS 原源和 Spectre 只读源。 |
| <a id="scope-l3-11"></a>[L3-11](#l3-11) 数组的事件状态更新 | B：[`F07`](#f07) | F07-base 的持久数组、非幂等更新、重复事件和全部元素；与初始化行共用执行。 |

### 第4层的固定用例

| 主表行 | 全部必测用例 | 本版范围与限制 |
| --- | --- | --- |
| <a id="scope-l4-01"></a>[L4-01](#l4-01) 采样→保持→边沿→滤波 | SEF：[`SEF-TIMER`](#old-sef-timer)、[`SEF-RESET`](#old-sef-reset)、[`SEF-INTERRUPT`](#old-sef-interrupt)、[`SEF-ISOLATION`](#old-sef-isolation)、[`ST:SEF-TIMER`](#old-st-sef-timer)、[`ST:SEF-INTERRUPT`](#old-st-sef-interrupt)、[`ST:SEF-ISOLATION`](#old-st-sef-isolation) | 原四种电路与三种观察；Q补验保留旧观察并添加强制点。保留 SEF-TIMER-18 的已接受范围和全部严格失败，不将其扩大。 |
| <a id="scope-l4-02"></a>[L4-02](#l4-02) 滤波→采样保持 | OLD：[`c2-main`](#old-c2-main) | 原 c2-main 同源模型；旧600 µV与1 mV判据保留，新Q验收检查滤波值、实际采样、完整保持及关键边界。 |
| <a id="scope-l4-03"></a>[L4-03](#l4-03) 电压求解→延迟→采样 | B：[`EC13`](#ec13) | EC13-v1 的代数电压解、延迟历史及全部4次 timer 回调，包含 stop 要求。 |
| <a id="scope-l4-04"></a>[L4-04](#l4-04) VCO：扫频与原始相位 | B：[`F20`](#f20)、[`EC17`](#ec17)、[`EC18`](#ec18) | 固定频率、正向扫频、负频率及非零偏置；原始相位和正弦均须验收。 |

### 第5层的固定用例

| 主表行 | 全部必测用例 | 本版范围与限制 |
| --- | --- | --- |
| <a id="scope-l5-01-integral"></a>[L5-01](#l5-01) 实例隔离：双积分器复位 | B：[`EC06`](#ec06) | EC06-v1/v2 的两个初值、单路复位及实例/贡献重排，所有变体必测。 |
| <a id="scope-l5-01-phase"></a>[L5-01](#l5-01) 实例隔离：双相位历史 | B：[`EC19`](#ec19) | EC19-v1 的不同频率与初值，分别检查相位及正弦历史。 |
| <a id="scope-l5-02"></a>[L5-02](#l5-02) 非线性积分与滤波联合反馈 | B：[`EC09`](#ec09) | EC09-v1 的联合反馈轨迹与全部输出；原 LP-IDT、NA 放大模型另存历史。 |
| <a id="scope-l5-03-linear"></a>[L5-03](#l5-03) 事件改变动态：线性反馈 | B：[`EC08`](#ec08) | EC08-v1：事件改变保持输入，线性反馈保留其他状态；旧Q3超时保留；新候选三档通过。 |
| <a id="scope-l5-03-riccati"></a>[L5-03](#l5-03) 事件改变动态：Riccati 滤波 | B：[`EC10`](#ec10) | EC10-v1：事件激活 Riccati 滤波，不重新进行 DC 初始化。 |
| <a id="scope-l5-04-chain"></a>[L5-04](#l5-04) 近邻定时事件：原整链 | NT：[`NT:fixed`](#old-nt-fixed)、[`NT:held`](#old-nt-held)、[`NT:chain`](#old-nt-chain) | 原三模型全部计数、采样和连续输出；采用各模型原事件容差和接地参考。旧1 µV判据保留，Q补验另立身份。 |
| <a id="scope-l5-04-adjacent"></a>[L5-04](#l5-04) 近邻定时事件：相邻浮点采样积分 | B：[`EC20`](#ec20) | EC20-v1 的相邻 binary64 时刻、采样值与积分面积；不同于原 NT 整链。 |

### 怎样查回旧结论

主表的测试范围现在写到具体用例，不再用整个扩展目标作分母。
比如 `P-idt` 的三档记录与 F13、EC06 的记录各自保留；P-idt 通过不消除 F13 的缺证，也不证明积分复位。
二阶滤波的 EC11 与 DC 导数直通的 EC16 分开，前者通过不授予后者资格。

旧 LANG-preprocess、LANG-vector、LP-np 等 1 mV 成绩仍在[原专项记录](../../../experiments/backends/support/README.md#专项-15-条件)，
并非被新表的空格或失败改判。原 DS 的 2.01 µV/12 nV、SC/FD 的 1 µV、NA 的双输出预算也仍见[历史工程组合](#历史工程组合逐项对应)。
这些范围不会因为新增 F/EC 卡而退役，也不能用于补齐另一张卡的失败。

历史44组仍为71变体、852位置；新基础卡仍为120位置，sin另有6次配置校准。
本页不重算这些分母或通过数。未来增加必测用例时另记 scope-v2，并同时保留本版与扩展版结论。

## 先找到各批的原始成绩

| 测试批次 | 条件定义 | 保留的成绩与版本依据 |
| --- | --- | --- |
| 原 31 条件 | [起步卡](../CASE_CARDS.md)、[补充卡](../NEXT_CASE_CARDS.md) | [四后端原矩阵](../../../experiments/backends/dvs2-four-backend-validation/results/MATRIX.md)、[后续 EVAS 复验](../README.md#latest-evas-checkpoint) |
| core-v1，12 条件 | [冻结卡](core-v1.json) | [逐项记录](../../../experiments/backends/support/README.md#核心-12-条件)；EVAS `5d357251`，端点诊断另存 |
| 专项，15 条件 | [v2 源码与条件](../support/cases-v2.json)，[旧 v1](../support/cases-v1.json) | [原成绩及补测](../../../experiments/backends/support/README.md#专项-15-条件)；EVAS 原执行 `6ee1ebaa` |
| 采样与滤波，8 条件 | [v1 条件](precision-v1.json)、[v2 判据](precision-v2.json) | [v1](../../../experiments/backends/support/README.md#precision-pilot)、[v2](../../../experiments/backends/support/README.md#precision-v2)、[配置补证](../../../experiments/backends/support/README.md#precision-bindings)；v2 EVAS `826fefb1` |
| 既有组合复验 | 下方各专项定义 | [21 条件复验](../../../experiments/backends/support/README.md#current-main)；EVAS `fc7e57fd`，含上述 8 条件，不增加条件数 |
| 严格滤波修复 | 仍用原 8 条件中的 4 个滤波模型 | [deep 补测](../../../experiments/backends/support/README.md#evas-precision-recovery)；基线 `7c9e6aba`，不回填旧绑定表 |
| 新 44 组，71 变体 | [基础](https://github.com/BucketSran/vaEVAS/blob/814da00daf2f0bea1555fffe923f5b6abd78b6bf/evas/validation/paper/precision_breadth_foundation.py)、[组合](https://github.com/BucketSran/vaEVAS/blob/814da00daf2f0bea1555fffe923f5b6abd78b6bf/evas/validation/paper/precision_breadth_composition.py) | [逐档成绩](../../../experiments/backends/support/README.md#breadth-tier-results)、[收据](https://github.com/BucketSran/vaEVAS/blob/814da00daf2f0bea1555fffe923f5b6abd78b6bf/experiments/backends/support/20261012-breadth.json)；EVAS `519d5e28` |
| 旧整链 Q 补验，12 条件 | 旧 SEF/ST、STROBE-TIMER-IDT、c2-main、NT；新 Q 观察与只读源分开 | [逐档补验](../../../experiments/backends/support/README.md#legacy-chain-q)，108次；EVAS内核对应 main `7344e4db`，36次完整通过；不增加旧条件数。 |
| 中断边沿积分新版，1 条件 | EC05-v1 源码；EC05-Q-v2 面积与边界判据 | [实际对照](../../../experiments/backends/support/README.md#legacy-chain-q)，9次；EVAS本分支和Spectre只读源三档通过，原Spectre源未取得新Q资格；原852位置不改。 |

上述 EVAS 版本不构成一次同版本全量复验。各后端实际工具身份和设置随原收据保留。
历史通过只表示对应判据的有限观察通过；没有完成 Q 档验收的，不能仅按电压阈值换算成 Q1/Q2/Q3。

<a id="legacy-31"></a>

## 原 31 条件逐项对应

本表 ID 与[原矩阵](../../../experiments/backends/dvs2-four-backend-validation/results/matrix.json)一致。
`v6-standard` 是旧 `v6-main` 的标准数组语法版本，原始源码和失败保留，不算两项。

| 原条件 | 主归属 | 检查内容 | 新 44 组中的相关项 | 仍须保留的旧范围 |
| --- | --- | --- | --- | --- |
| <a id="old-v1-main"></a>`v1-main` | [L1-03](#l1-03) | 静态增益、失调、限幅 | F03、F05 | 原分段输入和增益组合 |
| <a id="old-v2-main"></a>`v2-main` | [L1-17](#l1-17) | 差分、参考与供电变化 | F10 | 供电依赖与原差分刺激 |
| <a id="old-v2-reference-zero"></a>`v2-reference-zero` | [L1-17](#l1-17) | 参考置零的单因素对照 | F10 | 与 v2-main 的成对关系 |
| <a id="old-v2-supply-fixed"></a>`v2-supply-fixed` | [L1-17](#l1-17) | 供电固定的单因素对照 | 无直接对应 | 供电敏感性对照 |
| <a id="old-v2-input-common-mode"></a>`v2-input-common-mode` | [L1-17](#l1-17) | 共模变化 | F10 | 原供电、差分和共模组合 |
| <a id="old-v3-main"></a>`v3-main` | [L3-03](#l3-03) | 迟滞比较器 | EC02 | 原阈值、刺激和启动条件 |
| <a id="old-v4-c0"></a>`v4-c0` | [L3-02](#l3-02) | 采样、复位与边沿 | EC01 | 原时钟相位 c0 |
| <a id="old-v4-c1"></a>`v4-c1` | [L3-02](#l3-02) | 采样、复位与边沿 | EC01 | 原时钟相位 c1 |
| <a id="old-v5-main"></a>`v5-main` | [L2-06](#l2-06) | 非对称定时脉冲 | F19 | 原延迟、周期和边沿参数 |
| <a id="old-v6-standard"></a>`v6-standard` | [L2-12](#l2-12) | 一阶低通 | F15 | 原时间常数与输入 |
| <a id="old-v7-linear-main"></a>`v7-linear-main` | [L1-10](#l1-10) | 线性双实例 | F09、F11 | 原实例输入和增益 |
| <a id="old-v7-linear-swapped"></a>`v7-linear-swapped` | [L1-10](#l1-10) | 交换实例声明顺序 | F09 | 原双实例绝对答案和成对关系 |
| <a id="old-v7-linear-a-half"></a>`v7-linear-a-half` | [L1-10](#l1-10) | 只改变 A 输入 | F09 | B 不受影响的单因素对照 |
| <a id="old-v7-nonlinear-0.5"></a>`v7-nonlinear-0.5` | [L1-18](#l1-18) | 三次唯一解反馈 | F12 | 原系数 0.5 |
| <a id="old-v7-nonlinear-2.0"></a>`v7-nonlinear-2.0` | [L1-18](#l1-18) | 三次唯一解反馈 | F12 | 原系数 2.0 |
| <a id="old-e1-aligned"></a>`e1-aligned` | [L2-02](#l2-02) | 穿越事件累计 | F07、EC04 | 原根与网格对齐 |
| <a id="old-e1-shifted"></a>`e1-shifted` | [L2-02](#l2-02) | 穿越事件累计 | F07、EC04 | 原偏移根与重复计数 |
| <a id="old-e1-slow"></a>`e1-slow` | [L2-02](#l2-02) | 慢斜率穿越 | F07、EC04 | 原斜率和表达式容差关系 |
| <a id="old-e2-low"></a>`e2-low` | [L2-01](#l2-01) | 低时钟、低复位启动 | EC01 | 原初始化与释放时序 |
| <a id="old-e2-clock-high"></a>`e2-clock-high` | [L2-01](#l2-01) | 高时钟启动不误采样 | EC01 | 初始高时钟条件 |
| <a id="old-e2-reset-high"></a>`e2-reset-high` | [L2-01](#l2-01) | 高复位启动及恢复 | EC01 | 初始高复位条件 |
| <a id="old-c1-main"></a>`c1-main` | [L5-01](#l5-01) | 双采样实例及单路复位 | EC01、EC06、EC19 | 原采样器实例隔离组合 |
| <a id="old-c1-swapped"></a>`c1-swapped` | [L5-01](#l5-01) | 交换采样实例声明 | F09、EC01 | 原有状态实例声明交换 |
| <a id="old-c1-no-reset-a"></a>`c1-no-reset-a` | [L5-01](#l5-01) | 取消 A 的复位 | EC01、EC06 | 对 B 的不变性和 A 的独立答案 |
| <a id="old-c2-main"></a>`c2-main` | [L4-02](#l4-02) | 先滤波，再采样与边沿 | 无完整对应 | 滤波状态在采样时刻的读取 |
| <a id="old-d1-free"></a>`d1-free` | [L2-09](#l2-09) | 非零初值与正负积分 | F13 | 原正负面积刺激 |
| <a id="old-d1-reset"></a>`d1-reset` | [L2-09](#l2-09) | 积分复位保持与释放 | EC06、EC07 | 原复位持续区间及释放 |
| <a id="old-d2-constant"></a>`d2-constant` | [L2-10](#l2-10) | 固定频率环回与正弦 | F20 | 原初相、频率和圈数 |
| <a id="old-d2-chirp"></a>`d2-chirp` | [L4-04](#l4-04) | 变频环回与正弦 | EC17 | 原频率轨迹和观察 |
| <a id="old-s1-default"></a>`s1-default` | [L1-17](#l1-17) | 贡献累加、参数默认 | F01、F10 | 原默认值与独立输入 |
| <a id="old-s1-override"></a>`s1-override` | [L1-17](#l1-17) | 贡献累加、参数覆盖 | F01、F10 | 与默认条件的成对关系 |

<a id="supplemental-conditions"></a>

## 原批次之外的补充条件

| 原条件 | 主归属 | 来源与用途 | 当前记录 |
| --- | --- | --- | --- |
| <a id="old-s1-default-reordered"></a>`s1-default-reordered` | [L1-17](#l1-17) | [原卡](../NEXT_CASE_CARDS.md#s1-review)；只改变默认模型的三条贡献顺序，两种编码须分别符合绝对答案 | 已有模型与校准，未运行；保留 T/I，不加入原 31 分母 |

<a id="core-12"></a>

## core-v1 的 12 条件逐项对应

[原卡](core-v1.json)与[原成绩](../../../experiments/backends/support/README.md#核心-12-条件)继续保留。
原 EVAS 的 12 项计分通过，不包含另列未决的精确端点诊断；不能改写为新 Q 档完整通过。

| 原条件 | 主归属 | 检查内容 | 新 44 组中的相关项 | 仍须保留的旧范围 |
| --- | --- | --- | --- | --- |
| <a id="old-vr-01"></a>`VR-01` | [L1-17](#l1-17) | 差分访问与非零参考 | F10 | 原三个独立输入 |
| <a id="old-ex-01"></a>`EX-01` | [L1-05](#l1-05) | 顺序赋值与限频 | F02、F03、F05 | 原限幅频率输出 |
| <a id="old-ev-sh-01"></a>`EV-SH-01` | [L3-01](#l3-01) | 周期采样保持 | EC03 | 原纯保持输出及原周期 |
| <a id="old-ev-hc-01"></a>`EV-HC-01` | [L3-03](#l3-03) | 上下阈值与迟滞 | EC02 | 原双阈值状态轨迹 |
| <a id="old-ev-hc-02"></a>`EV-HC-02` | [L3-03](#l3-03) | 输入决定启动高状态 | EC02 | 原高输入初始化 |
| <a id="old-tm-01"></a>`TM-01` | [L2-06](#l2-06) | 正延迟与完整非对称沿 | F19 | 原 pulse 日程及完整沿 |
| <a id="old-cp-01"></a>`CP-01` | [L2-09](#l2-09) | 非零初相与变频积分 | F13、EC17 | 原积分初值和频率轨迹 |
| <a id="old-cp-02"></a>`CP-02` | [L2-10](#l2-10) | 多周期模相位与正弦 | F20 | 原环回次数和未决端点 |
| <a id="old-si-01"></a>`SI-01` | [L5-01](#l5-01) | 双实例定时递推 | F01、F09、EC19 | 独立周期与采样状态 |
| <a id="old-co-sh-01"></a>`CO-SH-01` | [L3-02](#l3-02) | 采样、复位抑制与边沿 | EC01 | 原复位释放时序 |
| <a id="old-co-hc-01"></a>`CO-HC-01` | [L3-03](#l3-03) | 迟滞与完整边沿 | EC02 | 原阈值和沿参数 |
| <a id="old-co-vco-01"></a>`CO-VCO-01` | [L4-04](#l4-04) | 限幅频率驱动 VCO | EC17 | 限频组合和未决环回端点 |

<a id="support-15"></a>

## 15 个语言与算子专项逐项对应

[旧判据](../support/README.md)的 1 mV 门槛和排除窗不改。
函数、数组事件和 ddt 拐点不能因旧窗外达标就取得完整边界资格。

| 原条件 | 主归属 | 检查内容 | 新 44 组中的相关项 | 仍须保留的旧范围 |
| --- | --- | --- | --- | --- |
| <a id="old-ad-ramp"></a>`AD-ramp` | [L2-07](#l2-07) | 固定延迟斜坡 | F17 | 原短时间尺度与参数 |
| <a id="old-ad-after-stop"></a>`AD-after-stop` | [L2-07](#l2-07) | 延迟超过仿真终点 | 无直接对应 | 全程读取初始历史 |
| <a id="old-sl-catch"></a>`SL-catch` | [L2-08](#l2-08) | 限速平台追赶 | F18 | 原平台与交点 |
| <a id="old-sl-reverse"></a>`SL-reverse` | [L2-08](#l2-08) | 限速反向追赶 | F18 | 原反向刺激和细步长对照 |
| <a id="old-sl-tracking"></a>`SL-tracking` | [L2-08](#l2-08) | 未触限速的跟踪 | 无独立对应 | 全程不触限条件 |
| <a id="old-lp-nd"></a>`LP-nd` | [L2-12](#l2-12) | 短时间常数一阶 ND | F15 | 原短时间常数 |
| <a id="old-lp-np"></a>`LP-np` | [L2-13](#l2-13) | 短时间常数一阶 NP | F16 | 原极点及 ND 对应 |
| <a id="old-ddt-pwl"></a>`DDT-pwl` | [L2-11](#l2-11) | PWL 线性段内求导 | F14 | 原段内成绩；旧拐点未验收 |
| <a id="old-nl-cubic"></a>`NL-cubic` | [L1-18](#l1-18) | 单调三次反馈 | F12 | 原系数和刺激 |
| <a id="old-vr-add"></a>`VR-add` | [L1-17](#l1-17) | 参考与贡献累加 | F10 | 原参考节点和输入 |
| <a id="old-lang-preprocess"></a>`LANG-preprocess` | [L1-01](#l1-01) | 宏与参数 | F01 | 原无层次宏模型及异常输入 |
| <a id="old-lang-hierarchy"></a>`LANG-hierarchy` | [L1-10](#l1-10) | 静态层次 | F09 | 原层次、连接和参数 |
| <a id="old-lang-functions"></a>`LANG-functions` | [L1-06](#l1-06) | 条件、函数与顺序赋值 | F02、F03、F05 | 原动态输入；旧阈值窗未验收 |
| <a id="old-lang-array-events"></a>`LANG-array-events` | [L3-11](#l3-11) | 循环、数组与事件 | F06、F07 | 原事件和状态；旧事件窗未验收 |
| <a id="old-lang-vector"></a>`LANG-vector` | [L1-09](#l1-09) | 静态电气向量 | F08 | 原各位激励和连接 |

<a id="precision-8"></a>

## 原八条件精度集逐项对应

v1、v2 扫描、配置绑定和 deep 修复是这些条件的不同验收或执行记录，不是新的行为条件。
本节完整保留 [8 个模型](precision-v1.json)，新 44 组没有替代它们。

| 原条件 | 主归属 | 检查内容 | 新 44 组中的相关项 | 仍须保留的旧范围 |
| --- | --- | --- | --- | --- |
| <a id="old-sh-t-ramp"></a>`SH-T-RAMP` | [L3-01](#l3-01) | 定时采样斜坡，8 次 | EC03 | 原纯采样保持、8 次时序 |
| <a id="old-sh-x-ramp"></a>`SH-X-RAMP` | [L3-01](#l3-01) | 阈值采样，8 次 | EC01、EC04 | 原穿越时钟、8 次回调资格 |
| <a id="old-sh-t-small"></a>`SH-T-SMALL` | [L3-01](#l3-01) | 1 mV 定时采样 | 无同尺度对应 | 小信号；Q3 总预算 1.1 nV |
| <a id="old-sh-t-long"></a>`SH-T-LONG` | [L3-01](#l3-01) | 连续 32 次定时采样 | 无同长度对应 | 32 次计数、读值及保持 |
| <a id="old-lp-ramp"></a>`LP-RAMP` | [L2-12](#l2-12) | 一阶滤波斜坡 | F15 | 原参数、输入和观察 |
| <a id="old-lp-nonzero"></a>`LP-NONZERO` | [L2-12](#l2-12) | 非零 DC 初态滤波 | F15 | 原 0.25 V 初值条件 |
| <a id="old-lp-small"></a>`LP-SMALL` | [L2-12](#l2-12) | 1 mV 一阶滤波 | 无同尺度对应 | 小信号；Q3 总预算 1.1 nV |
| <a id="old-lp-idt"></a>`LP-IDT` | [L5-02](#l5-02) | idt 写法的一阶反馈 | EC08 | 原无事件连续反馈模型 |

<a id="compositions"></a>

## 历史工程组合逐项对应

名称加前缀用于区分不同目录内的 `ramp`、`reverse` 等 ID，不改原用例名。
来源：采样滤波 [SEF](../sample_edge_filter/contract.py)、强制点 [ST](../strobe/timer_composition.py)、
近邻时钟 [NT](../strobe/near_timer.py)、两级限速 [SC](../slew_cascade/compare.py)、
滤波直通 [FD](../filter_direct/compare.py)、直接采样 [DS](../../../experiments/backends/sample-edge-filter/direct_sample.py)、
非线性续算 [NA](../../../experiments/backends/transient-accuracy/README.md#integration-20261010)。

实际结果和执行身份分别见 [SEF](../../../experiments/backends/sample-edge-filter/README.md)、
[ST](../../../experiments/backends/strobe/README.md#timer-fix)、[NT](../../../experiments/backends/strobe/README.md#near-timer)、
[SC](../../../experiments/backends/slew-cascade/README.md)、[FD](../../../experiments/backends/filter-direct/README.md)、
[DS](../../../experiments/backends/sample-edge-filter/direct-sample-receipt.json)。
ST、NT、SC、FD 的 EVAS 后续复验为 `fc7e57fd`；SEF 按 PR #123 集成收据，
DS 按 `0623475c` 集成收据，NA 按 `4cf15adc` 集成收据保留，均不冒充新 44 组的执行版本。

SEF 和 ST 的电压预算为 100 µV，NT、SC、FD 为 1 µV。
DS 正、负条件的固定参考幅度为 2 V，小信号为 2 mV，按原 `10 nV + 1 ppm × A` 分别得到 2.01 µV 和 12 nV。
NA 的状态输出预算为 0.1 µV，放大输出为 1 mV；所有这些预算都沿用原判据。

ST 的三个 SEF 模型复用原合同，新增的是 strobe 执行要求，不能再算三项独立电路。
SEF-TIMER-18 只豁免[已列出的 18 条跳变侧差异](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18)，不扩展到新模型。

| 原条件 | 主归属 | 检查内容 | 新 44 组中的相关项 | 仍须保留的旧范围 |
| --- | --- | --- | --- | --- |
| <a id="old-sef-timer"></a>`SEF-TIMER` | [L4-01](#l4-01) | 采样→保持→边沿→滤波 | F19、EC01 | 完整四级链及原观察 |
| <a id="old-sef-reset"></a>`SEF-RESET` | [L4-01](#l4-01) | cross 时钟采样与复位的滤波链 | EC01 | 原触发方式和完整滤波历史 |
| <a id="old-sef-interrupt"></a>`SEF-INTERRUPT` | [L4-01](#l4-01) | 中断边沿后继续滤波 | EC02、EC05 | 边沿中断与下游滤波组合 |
| <a id="old-sef-isolation"></a>`SEF-ISOLATION` | [L4-01](#l4-01) | 双实例采样滤波 | EC06、EC19 | 各实例四级历史隔离 |
| <a id="old-st-sef-timer"></a>`ST:SEF-TIMER` | [L4-01](#l4-01) | 正常链的 strobe | F19、EC01 | 原强制点请求与回执 |
| <a id="old-st-sef-interrupt"></a>`ST:SEF-INTERRUPT` | [L4-01](#l4-01) | 中断链的 strobe | EC02、EC05 | 原强制点和滤波消费者 |
| <a id="old-st-sef-isolation"></a>`ST:SEF-ISOLATION` | [L4-01](#l4-01) | 双实例链的 strobe | EC06、EC19 | 原双链强制点 |
| <a id="old-strobe-timer-idt"></a>`STROBE-TIMER-IDT` | [L3-04](#l3-04) | 采样保持后积分 | EC03 | 原 100 ps timer 与 100 µV 预算 |
| <a id="old-nt-fixed"></a>`NT:fixed` | [L5-04](#l5-04) | 0.3 与 0.1+0.2 邻近时钟 | EC20 | 原固定周期和观察点 |
| <a id="old-nt-held"></a>`NT:held` | [L5-04](#l5-04) | 精确保持周期的邻近时钟 | EC20、EC21 | 保持周期变量；非提前 next |
| <a id="old-nt-chain"></a>`NT:chain` | [L5-04](#l5-04) | 近邻时钟→边沿→滤波，另路积分 | EC20 | 完整下游链，不能由采样积分替代 |
| <a id="old-sc-ramp"></a>`SC:ramp` | [L3-09](#l3-09) | 两级 slew 斜坡 | EC15 | 原对称速率与斜坡 |
| <a id="old-sc-catch"></a>`SC:catch` | [L3-09](#l3-09) | 两级 slew 平台追赶 | EC15 | 原平台及两个追赶点 |
| <a id="old-sc-reverse"></a>`SC:reverse` | [L3-09](#l3-09) | 两级 slew 反向追赶 | EC15 | 原反向轨迹、局部细步长证据 |
| <a id="old-fd-ramp"></a>`FD:ramp` | [L3-06](#l3-06) | 平方输入的滤波直接项 | EC12 | 原秒级模型和参数 |
| <a id="old-fd-reverse"></a>`FD:reverse` | [L3-06](#l3-06) | 非零初态、反向输入 | EC12 | 原 PWL 历史 |
| <a id="old-fd-nondyadic"></a>`FD:nondyadic` | [L3-06](#l3-06) | 非整数系数直接项 | EC12 | 原 d1=3 的系数与输入 |
| <a id="old-ds-positive"></a>`DS:positive` | [L3-01](#l3-01) | 非线性根的正向直接采样 | EC04 | 仅直接保持的原模型及预算 |
| <a id="old-ds-negative"></a>`DS:negative` | [L3-01](#l3-01) | 非线性根的负值直接采样 | EC04 | 原负输出尺度 |
| <a id="old-ds-small"></a>`DS:small` | [L3-01](#l3-01) | 非线性根的小幅值直接采样 | 无同尺度对应 | 原 0.001 倍幅度 |
| <a id="old-na-nonlinear"></a>`NA:nonlinear` | [L5-02](#l5-02) | 连续非线性积分及放大输出 | EC09 | 原有理轨迹、10000 倍放大输出 |
| <a id="old-na-event-continuation"></a>`NA:event-continuation` | [L5-03](#l5-03) | 事件改变非线性积分速度 | EC10、EC21 | 原事件、严格锚点与补充连续观测规则 |

<a id="confirmation"></a>

## 七模型确认集

[原合同与数学答案](../confirmation/README.md)固定 10 nV 电压目标，每例有稀疏、加密两张查询网格。
它不是 Q3 扫描，也不是四后端对照。原 EVAS [14 次复验](../README.md#latest-evas-checkpoint)保留原身份。

| 原条件 | 主归属 | 检查内容 | 新 44 组中的相关项 | 仍须保留的旧范围 |
| --- | --- | --- | --- | --- |
| <a id="old-language"></a>`language` | [L1-06](#l1-06) | 宏、函数、循环、数组、层次和反馈 | F01、F05、F06、F09、F11 | 整条语言组合，不以各项单测代替 |
| <a id="old-histories"></a>`histories` | [L5-01](#l5-01) | 层次中两个积分初值的隔离 | EC06 | 原层次和增益 |
| <a id="old-calendar"></a>`calendar` | [L5-03](#l5-03) | 提前 next 后非线性积分反向 | EC21 | 原秒级轨迹与双查询网格 |
| <a id="old-projected"></a>`projected` | [L4-03](#l4-03) | 隐式代数投影驱动延迟及 slew | EC13、EC15 | 延迟、slew 和代数关系的完整组合 |
| <a id="old-roots"></a>`roots` | [L5-03](#l5-03) | 改阈值后重定位根与 timer OR | EC04、EC22 | 原未来根撤销及异刻 OR |
| <a id="old-implicit"></a>`implicit` | [L5-07](#l5-07) | 唯一分支隐式连续关系 | EC24 | 原无复位轨迹，不同于复位探针 |
| <a id="old-reset_filter"></a>`reset_filter` | [L5-01](#l5-01) | 积分复位但独立滤波历史保留 | EC06、EC08 | 原积分和滤波共同状态及双网格 |

<a id="breadth-44"></a>

## 新 44 组逐项对应

下列变体名直接来自当前条件生成器，共 71 个，不能只测组内一个变体就判整组通过。
每组链接的旧例只是相关来源，旧例仍按上文单独维护。
新批次的独立参考、预算和模型已固定；本次只整理映射，没有重新执行或修改 checker。主归属用于导航，辅助覆盖可交叉引用，但同一条件不重复计数。

| 新组及必测变体 | 主归属 | 相关历史用例 | 本组新增或改变的检查 |
| --- | --- | --- | --- |
| <a id="f01"></a>**F01**：`F01-base` | [L1-01](#l1-01) | LANG-preprocess；s1-default/override；SI-01 | 函数宏和实例参数组合；不代替原无层次模型 |
| <a id="f02"></a>**F02**：`F02-base` | [L1-05](#l1-05) | EX-01；LANG-functions | 贡献发生时的顺序局部值快照 |
| <a id="f03"></a>**F03**：`F03-dc-0`, `F03-dc-1`, `F03-dc-2`, `F03-dc-3`, `F03-dc-4`, `F03-dc-5`, `F03-dc-6`, `F03-dc-7`, `F03-dc-8`, `F03-dc-9`, `F03-dc-10`, `F03-dc-11` | [L1-03](#l1-03) | v1-main；EX-01；LANG-functions | 比较、逻辑、三目在阈值及相邻浮点数的 DC 表 |
| <a id="f04"></a>**F04**：`F04-dc-0`, `F04-dc-1`, `F04-dc-2`, `F04-dc-3`, `F04-dc-4` | [L1-04](#l1-04) | 无同名历史比较条件 | case 首次匹配与 default 的五种 DC 输入 |
| <a id="f05"></a>**F05**：`F05-base`, `F05-dc-0`, `F05-dc-1`, `F05-dc-2` | [L1-06](#l1-06) | LANG-functions；确认集 language | 函数分支、局部量和三种 DC 输入 |
| <a id="f06"></a>**F06**：`F06-base` | [L1-07](#l1-07) | LANG-array-events；确认集 language | 独立静态循环与局部数组 |
| <a id="f07"></a>**F07**：`F07-base` | [L3-11](#l3-11) | LANG-array-events；e1-aligned/shifted/slow | 非幂等数组事件更新，timer 与 cross 分开取证 |
| <a id="f08"></a>**F08**：`F08-base` | [L1-09](#l1-09) | LANG-vector | 当前静态电气向量写法 |
| <a id="f09"></a>**F09**：`F09-base`, `F09-reordered` | [L1-10](#l1-10) | LANG-hierarchy；v7-linear-swapped；确认集 language | 两级层次与声明交换 |
| <a id="f10"></a>**F10**：`F10-base`, `F10-common-mode`, `F10-reordered` | [L1-17](#l1-17) | VR-01；VR-add；v2-main；s1-default/override | 参考、贡献顺序、共模变体；不含原供电对照 |
| <a id="f11"></a>**F11**：`F11-base` | [L1-18](#l1-18) | v7-linear-main；确认集 language | 独立唯一仿射隐式关系 |
| <a id="f12"></a>**F12**：`F12-base`, `F12-dc-0`, `F12-dc-1`, `F12-dc-2` | [L1-18](#l1-18) | NL-cubic；v7-nonlinear-0.5/2.0 | 当前三次关系及正、负、零 DC 输入 |
| <a id="f13"></a>**F13**：`F13-base` | [L2-09](#l2-09) | CP-01；d1-free | 当前非零初值的积分轨迹 |
| <a id="f14"></a>**F14**：`F14-base` | [L2-11](#l2-11) | DDT-pwl | PWL 导数单侧值，启动和折点不再由旧排除窗代替 |
| <a id="f15"></a>**F15**：`F15-base` | [L2-12](#l2-12) | LP-nd；LP-RAMP/NONZERO；v6-standard | 二进制参数、非零 DC；没有旧小信号和短时间常数条件 |
| <a id="f16"></a>**F16**：`F16-base` | [L2-13](#l2-13) | LP-np | 与 F15 对应的极点表示 |
| <a id="f17"></a>**F17**：`F17-base` | [L2-07](#l2-07) | AD-ramp | 当前延迟启动历史；不覆盖 AD-after-stop |
| <a id="f18"></a>**F18**：`F18-base` | [L2-08](#l2-08) | SL-catch/reverse/tracking | 当前非对称限速与反向追赶 |
| <a id="f19"></a>**F19**：`F19-base` | [L2-06](#l2-06) | TM-01；v5-main | 当前 timer 日程与完整非对称沿 |
| <a id="f20"></a>**F20**：`F20-base` | [L2-10](#l2-10) | CP-02；d2-constant | 原始模相位与正弦分别验收环回边界 |
| <a id="ec01"></a>**EC01**：`EC01-v1` | [L3-02](#l3-02) | CO-SH-01；v4-c0/c1；e2-low/clock-high/reset-high | 当前采样、复位和 transition；没有下游滤波 |
| <a id="ec02"></a>**EC02**：`EC02-v1` | [L3-03](#l3-03) | CO-HC-01；EV-HC-01/02；v3-main | 迟滞后边沿的快速反向和短脉冲 |
| <a id="ec03"></a>**EC03**：`EC03-v1` | [L3-04](#l3-04) | STROBE-TIMER-IDT；SH-T-RAMP | 非零积分初值；另规定 stop 时已看到最后回调 |
| <a id="ec04"></a>**EC04**：`EC04-v1` | [L3-04](#l3-04) | DS:positive/negative/small；e1-aligned/shifted/slow | 非线性根采样后再驱动非线性积分 |
| <a id="ec05"></a>**EC05**：`EC05-v1` | [L3-10](#l3-10) | SEF-INTERRUPT；ST:SEF-INTERRUPT | 原支持探针保留；EC05-Q-v2另验收中断后积分面积、非零初值和边界两侧。 |
| <a id="ec06"></a>**EC06**：`EC06-v1`, `EC06-v2` | [L5-01](#l5-01) | d1-reset；确认集 histories/reset_filter | 双积分器仅复位一路、独立初值和编码变体 |
| <a id="ec07"></a>**EC07**：`EC07-v1` | [L3-05](#l3-05) | d1-reset | 上游复位后下游积分保留已有面积 |
| <a id="ec08"></a>**EC08**：`EC08-v1` | [L5-03](#l5-03) | LP-IDT；确认集 reset_filter | 保持输入驱动反馈并保留另路状态 |
| <a id="ec09"></a>**EC09**：`EC09-v1` | [L5-02](#l5-02) | NA:nonlinear | 非线性积分与滤波器的联合反馈 |
| <a id="ec10"></a>**EC10**：`EC10-v1` | [L5-03](#l5-03) | NA:event-continuation | 事件激活 Riccati 滤波，保持原历史 |
| <a id="ec11"></a>**EC11**：`EC11-v1`, `EC11-v2` | [L3-07](#l3-07) | v6-standard；LP-nd | 内部导数和二阶滤波，v2 增加输入斜坡内部折点，保持初值 |
| <a id="ec12"></a>**EC12**：`EC12-v1`, `EC12-v2` | [L3-06](#l3-06) | FD:ramp/reverse/nondyadic | 当前多项式直通滤波，v2 增加输入斜坡内部折点，保持初值 |
| <a id="ec13"></a>**EC13**：`EC13-v1` | [L4-03](#l4-03) | 确认集 projected | 代数投影、延迟和定时采样；另有 stop 回调要求 |
| <a id="ec14"></a>**EC14**：`EC14-v1` | [L3-08](#l3-08) | AD-ramp；确认集 projected | 两级延迟级联及另路独立延迟 |
| <a id="ec15"></a>**EC15**：`EC15-v1` | [L3-09](#l3-09) | SC:ramp/catch/reverse；确认集 projected | 非对称两级 slew；不替换旧对称速率三刺激 |
| <a id="ec16"></a>**EC16**：`EC16-v1` | [L3-07](#l3-07) | DDT-pwl；LP-nd | DC 导数阶段进入滤波直通项 |
| <a id="ec17"></a>**EC17**：`EC17-v1` | [L4-04](#l4-04) | d2-chirp；CP-01；CO-VCO-01 | 当前正向扫频；不覆盖原限频和门控 |
| <a id="ec18"></a>**EC18**：`EC18-v1` | [L2-10](#l2-10) | CP-02；d2-constant | 负频率和非零模偏移 |
| <a id="ec19"></a>**EC19**：`EC19-v1` | [L5-01](#l5-01) | SI-01；c1-main；确认集 histories | 不同频率和初值的相位实例隔离；不是原采样器 |
| <a id="ec20"></a>**EC20**：`EC20-v1` | [L5-04](#l5-04) | NT:fixed/held/chain | 相邻浮点时钟→采样积分；没有原边沿和滤波 |
| <a id="ec21"></a>**EC21**：`EC21-v1` | [L5-03](#l5-03) | 确认集 calendar；NA:event-continuation | 提前 next 的当前非线性传播，动态 timer 假设另存 |
| <a id="ec22"></a>**EC22**：`EC22-v1` | [L5-05](#l5-05) | CO-SH-01；确认集 roots | 同刻复位和时钟的语义探针，不能替代异刻事件 |
| <a id="ec23"></a>**EC23**：`EC23-v1` | [L5-06](#l5-06) | 旧 #70/#79 自换向诊断 | 双向自换向支持探针；不修改旧诊断或 #131 |
| <a id="ec24"></a>**EC24**：`EC24-v1` | [L5-07](#l5-07) | 确认集 implicit/reset_filter | 带复位隐式 DAE 支持探针 |

<a id="finite-primitives"></a>

## 新增独立基础卡逐项对应

本轮新增十张卡，每张在四后端执行 Q1/Q2/Q3，共120个位置。
EVAS 为固定 main 检查点 `a64c2ad0`；旧31条件、专项、原八条件和新增44组继续保留。
以下每张卡是新增子范围，不能替代旧尺度、复位、消费者或语言变体。
结果和实际配置见[本轮运行记录](../../../experiments/backends/support/README.md#primitives-main)。

| 新卡 | 能力行 | 必测内容 | 与已有测试的关系 |
| --- | --- | --- | --- |
| <a id="p-sin"></a>P-sin | [L1-11](#l1-11) | 零、正负极值、跨周期输入；范围 ±4π | 独立函数卡，组合中的 sin 继续保留 |
| <a id="p-cos"></a>P-cos | [L1-12](#l1-12) | 零、正负极值、跨周期输入；范围 ±4π | 独立函数卡 |
| <a id="p-exp"></a>P-exp | [L1-13](#l1-13) | 输入 −4、−1、0、1、4 及观察到的中间值 | 独立函数卡，不授予无界范围 |
| <a id="p-ln"></a>P-ln | [L1-14](#l1-14) | 正输入 10⁻⁶、0.25、1、2、8 | 独立函数卡；更接近零及非法域另列 |
| <a id="p-sqrt"></a>P-sqrt | [L1-15](#l1-15) | 零、10⁻¹²、10⁻⁶、0.25、4 | 独立函数卡，核对近零输入偏差 |
| <a id="p-pow"></a>P-pow | [L1-16](#l1-16) | −2 至2、固定三次幂 | 不代替所有合法指数 |
| <a id="p-pow-half"></a>P-pow-half | [L1-16](#l1-16) | 非负输入、固定半次幂 | 与三次幂分开验收 |
| <a id="p-idt"></a>P-idt | [L2-09](#l2-09) | 0.125 非零初值、PWL 正负面积与折点 | 补独立积分；不代替旧复位与释放 |
| <a id="p-ddt"></a>P-ddt | [L2-11](#l2-11) | 二次时间表达式的导数 | 单列 `$abstime` 准入依赖 |
| <a id="p-ddt-input"></a>P-ddt-input | [L2-11](#l2-11) | 电压斜坡平方的导数；终止前保持斜率 | 隔离 ddt 算子与时间表达式准入 |

本批检查原生导出的有限观察点，要求起点、终点和全部输入折点的记录。
保留实际时刻，按固定 checker 判断；略超 `stop` 的末点也仍记证据不足，没有直接放宽判据。
函数用有理级数或高精度 Decimal 包络作答案，积分用 PWL 的精确面积，微分用闭式导数。
整数幂、微分和积分都有独立手算锚点；近零输入、超差、缺观察及来源被改动均有故障校准。
没有整段波形误差证明，也没有自动扩展为组合支持。

### 新证据明确了哪些缺口

| 问题 | 本批依据 | 下一步 |
| --- | --- | --- |
| EVAS 缺少 `cos/exp/ln/sqrt`、半次幂及 `$abstime` 准入 | 合法模块名下稳定编译拒绝；其他后端编译成功 | 补前端、求值与误差传播，再沿原卡复验；不能只放宽语法 |
| EVAS 拒绝 `ddt(V(u)*V(u))` | 三档均要求瞬态表达式联合仿射；Spectre Q2 与 Gnucap Q2 有合格有限结果 | 扩展光滑非线性输入的微分路径，保留启动及段内验收 |
| EVAS `sin` 原Q3配置过紧，已另批校准 | 同卡将内部绝对容差改为100 fV后，实际65点通过原101 nV验收 | [六项对照](../../../experiments/backends/support/README.md#sin-q3-calibration)与原失败分别保留；本例不列为内核缺陷 |
| ngspice 的 `ln/sqrt` 初始工作点失败 | OSDI 编译成功，日志出现 NaN，未生成波形 | 核对初始猜测、定义域和 OSDI 求解路径；尚不能定为函数缺陷 |
| 微分精度与终点证据未闭合 | ngspice 两张微分卡三档超差；Gnucap Q3 超差；Spectre 微分有两项超差、三项终点缺证，积分Q3另有一项终点缺证 | 独立诊断启动、步长和观测，不由三档失败推断后端不可达到目标 |

本批新增卡采用另一套固定有限观察协议。它们的通过不自动清除旧 44 组的来源、回调或关键边界缺证。

<a id="pending-audit"></a>

### 旧表42格“待核”分别缺什么

已逐项核对重组前旧表的22行、42个后端单元格，对应新44组中的237个不同执行位置；
另有“滤波→采样保持”的四后端旧记录，尚未按新精度档复验。
[核对收据](../../../experiments/backends/support/20261012-pending-audit.json)保存每项原成绩、缺证原因和来源身份。
这次核对不重算历史分数，也没有把补读配置当作输入或事件证据。
`case`另核对了四后端各五个Q3旧输出：导出的输入值和分支结果都符合预期。
缺口是输入的精确消费与导出身份资料，尚不能将“打印值相同”当作该证明，也不能据此说四后端都不支持 `case`。

| 旧表核对标签 | 单元格数 | 还需要核验什么 |
| --- | ---: | --- |
| 输入与导出待证 | 2 | 比较阈值两侧的实际输入；开源后端的原生导出路径 |
| 输入待证 | 4 | `case` 接收到的实际常量是否与规定值逐位相同 |
| 导出待证 | 9 | 原生观察来源和实际运行控制，不能只根据打印的数字判通过 |
| 回调待证 | 13 | 完整回调区间是否落在语言允许范围；同一事件历史能否解释后续输出 |
| 终点与导出待证 | 2 | 补齐起止观察，核对实际导出路径 |
| 环回待证 | 4 | 原始相位在环回两侧的答案与误差；不能用正弦通过代替 |
| 配置待证 | 4 | Spectre 的实际步长和停止时刻；数值通过不能补造生效设置 |
| 未按新精度复验 | 4 | 旧滤波采样模型在新Q档下的同版对照 |

这些缺证不能直接归为EVAS缺陷。原收据中的数值超差、执行失败和不同变体仍逐项保留，
新主表用“—”表示尚无完整验收结论，本节保留重组前的细分标签和数量，便于追查资料。
`sin` Q3的[单独校准](../../../experiments/backends/support/README.md#sin-q3-calibration)已完成；下一批补基础特性的实际输入与导出证据；
事件、原始环回及高层组合继续各自验收，不挪用基础函数的通过记录。

<a id="remaining-coverage"></a>

## 还缺哪些测试和验收

“有相关模型”与“完整覆盖规划”分开看。下表对照[已同意的完整规划](README.md#next-engineering-suite)，
不是根据某后端能否通过缩减需求。

| 范围 | 已有材料 | 尚缺的工作 |
| --- | --- | --- |
| 小信号、长采样 | SH-T-SMALL、LP-SMALL、SH-T-LONG 已测 | 在目标集成版本复验；不由 1 V 的新短测试代替 |
| 采样、边沿与滤波整链 | SEF、ST、NT:chain 已测 | 保留整链回归；新 44 组不能替代这些消费者 |
| 滤波后采样 | 原 c2-main 已测，已补 main 的 Q1/Q2/Q3 强制观察验收 | 更广输入与滤波参数另定新版；不由本卡外推全部滤波后采样 |
| 供电和参考的单因素关系 | 原 v2 四条件已测 | 新统一精度流程中的供电依赖和对应观察 |
| 宏、参数、循环和数组的边界 | 旧语言模型及 F01–F09 部分覆盖 | include 保护、参数范围、零次/一次/参数化循环、声明方向等规划条件 |
| 独立数学函数 | 组合里用到 sin、exp、pow | 已补十张固定独立卡及六项sin校准；更大范围与参数变体另立新版，组合使用不等于独立覆盖 |
| 初始化及事件调度 | 原 e2、EV-HC-02、EC01/21/22 部分覆盖 | 逐项补齐初始阈值、周期修改、关闭恢复、旧日程取消及同刻规则 |
| VCO 与消费者 | d2、CO-VCO-01、F20、EC17–19 | 门控、长期相位、读取相位的 cross；已有环回处取证也须完成 |
| 连续动态 | 原滤波集、EC09–12/16 | 正弦幅相、共轭极点、光滑曲线导数及更广历史组合 |
| 延迟与限速 | AD、SL、SC、EC13–15 | 延迟后限速、短脉冲和更深级联按原规划形成独立卡 |
| ADC 码流 | 规划有此行 | 固定端码、阈值、饱和及读取时序的仿真器用例，不能借 benchmark 成绩补此行 |

更早的 above、last_crossing、动态索引、运行时循环及其他滤波形式继续按原规划延期，不记为已测。
本清单只说明已盘点材料能支持哪些主张，不是对整个仓库“没有其他测试”的断言。

<a id="pending-evidence"></a>

## 原11格的取证核对

上一轮11格已有运行，但缺少实际回调、输入消费者或最终接受状态的证明。
这次逐格核对并补跑，**补齐来源不等于通过验收**。新分析与旧成绩并列保存；
旧判据、窗口、预算、请求列表和失败没有回写。
执行身份、配置、误差与校准见[后续补证](../../../experiments/backends/support/README.md#evidence-followup)。
前两格共用一个阈值采样用例，不能算成两个独立实验。

| 主表行与后端 | 必测用例 | 已查清的情况 | 仍未完成的要求 |
| --- | --- | --- | --- |
| [L2-02](#scope-l2-02) cross，EVAS | SH-X-RAMP | 五份原配置共40个完整根区间都包含按实际PWL端点计算的真根；旧内缩窗口排除了全部真根。 | 新版 root-window-v3 三档已通过；旧不通过仍保留。严格无提前的证明未决，有限分辨率验收已完成。 |
| [L3-01](#scope-l3-01-cross) 阈值采样，EVAS | SH-X-RAMP | 与上一格共用8次回调；问题是旧窗与真根冲突。 | 与上一格共用同一次新版验收，取得 Q3；不算第二个独立实验。#131不动。 |
| [L2-10](#scope-l2-10) 原始环回相位，Spectre | F20、EC18 | 原生波形、公开相位变量、实际参数与接受阶段已关联。EC18新有限数值通过；F20仍有环回侧别差异。 | F20两个相邻请求合并到同一原生行，且精确环回边界未验收。 |
| [L2-10](#scope-l2-10) 原始环回相位，ngspice | F20、EC18 | 实际求解状态、相位消费者与全部原生输出已关联。F20等值stop字串复跑后终点位值正确。 | 环回处精确坐标与旧时间区间参考仍不能取得同一资格；新旧分析分开。 |
| [L4-04](#scope-l4-04) VCO，Spectre | F20、EC17、EC18 | 三张必测卡的实际参数、原相位与输出均已核对。EC17动态频率赋值的舍入也保留。 | F20和EC17的精确环回边界未验收，F20另有观测点合并。 |
| [L5-01](#scope-l5-01-phase) 双相位历史，Spectre | EC19 | 两个实例各自的参数、原相位与全部10169个原生观察已关联；观测开关不改变科学波形。 | 一个精确环回点返回近1，数学半开参考为0；旧区间判据仍为I。 |
| [L3-07](#scope-l3-07) 滤波与微分，Spectre | EC16 | PWL输入、DC与瞬态阶段、原滤波参数和10168个原生观察已核对。 | 启动点输出误差下界109.6 nV，超Q3的101 nV。容差再缩100倍的补测提前终止，不能授予通过。 |
| [L3-07](#scope-l3-07) 滤波与微分，ngspice | EC16 | 实际输入导数、原编译状态、接受路径和8621个原生观察已关联；新有限分析最大误差上界2.18 nV，通过Q3。 | 本卡来源和有限数值要求已闭合；不转授其他模型，也不回写旧I。 |
| [L3-07](#scope-l3-07) 滤波与微分，Gnucap | EC16 | 原微分与滤波消费者、PWL实际斜率及8198个原生观察已关联。 | 已测配置的输出误差至少674 µV，超过原Q1/Q2/Q3；DC边界的参考包围也仍未通过。 |
| [L5-04](#scope-l5-04-adjacent) 相邻浮点事件，Spectre | EC20 | 原回调仅新增保存时刻的局部量；观测开关前后34689行科学数据逐位相同。两个回调保存为同一double时刻。 | 严格物理先后未满足；16266个原请求中还有1项无对应原生行。 |
| [L5-04](#scope-l5-04-adjacent) 相邻浮点事件，Gnucap | EC20 | 原两通道处于同一实际接受时刻，已有记录可核查。 | 同样未取得原要求的严格物理先后。 |

“环回边界未验收”不表示连续积分相差近1 V。例如相位应从接近1环回到0，
极小的积分或频率舍入差会让两个结果分别落在跳变两侧。
新分析保留普通标量差，不改用环形距离；旧判据在时间区间跨越跳变时仍记I。
这些新用例没有借用此前SEF-TIMER-18的已接受差异，也不要求EVAS复制另一个后端的舍入侧。

这里的“新有限分析”只验收固定模型的全部原生观察、原要求的观察覆盖及来源。
例如ngspice的EC16在DC时刻为0，瞬态右侧按原解析响应验收；
没有降低101 nV门槛或删去初态、启动点。它不证明全时域，也不代表三档配置都已重新执行。
Spectre的as单位识别使用另立身份且经校准的关联方法，原不识别as的失败仍保留。
更严Spectre配置的提前停止与部分波形也完整保留，不计作完整精度结果。

Gnucap的固定延迟、限速、非线性反馈、定时边沿和电压求解后采样，已补齐原生输出、
实际接受时刻和舍入误差，有限用例通过Q3，不再列为缺证。
事件OR的实际状态只有3次更新，原要求5次，已归为漏事件。

实际失败另有确定原因：Spectre 的积分复位输出超差；ngspice 的部分组合编译或初始化失败；
Gnucap 的停止边界漏事件、采样到滤波的输出或历史错误。主表直接写这些原因。
其中的“超差”只说明已测配置未达标，不证明所有可选配置均无法达到目标。

上述 EVAS 执行缺口已在[采样积分修复批次](../../../experiments/backends/support/README.md#sampled-integral-fix)实际复验：
EC03/EC07/EC10/EC20 各三档完整通过，EC04 各三档完成执行但根区间未满足原触发窗。
EC04 的完整区间包含旧 nominal 的下邻；不裁剪区间、不将数值正确诊断改记为原卡通过。
这次没有扩展各行必测范围，也没有替换原44组或历史成绩；新增源码和内核身份另立收据。
EC04 的真根 `sqrt(2)×T` 小于旧窗口向上舍入的起点，故包含真根的完整区间无法落入旧窗。
两类冲突的依据见[评测标准](../../docs/COMPARISON-METHODOLOGY.md#root-window-conflict)。
上述是原判据的历史结论。后续另立 root-window-v3 并完成校准和实际对照：EVAS两卡三档6个配置通过，
Spectre只读回调模型5个通过、SH-X Q2有5项strobe在原16ULP窗口内找不到原生对应，仍为证据不足。
Spectre原模型6个配置没有回调日志，继续保留证据不足；只读模型成绩不转授原模型。
三格主表更新只引用新版合格Q3，原判据和历史成绩不变。完整依据见[新版收据](../../../experiments/backends/support/20261013-root-window-v3.json)。

两张 `ddt` 卡及 EC08/EC12 的 Q3 执行限制已由[本轮修复与复验](../../../experiments/backends/support/README.md#capability-gaps)处理。
原编译失败、拒绝和超时与新三档结果并列保存，不回写历史。
c2-main 保留原 600 µV / 1 mV 工程成绩；[旧整链Q补验](../../../experiments/backends/support/README.md#legacy-chain-q)
另取得EVAS原源与Spectre只读源三档完整资格，不回写旧记录。

本轮旧整链的待补资料是Spectre近邻三模型的关键边界双侧观察及stop打印格式校准，三档共9次。
其原1 µV成绩仍保留，EVAS同组已通过三档。旧整链的36个原Spectre源、EC05的3个原Spectre源
没有回调日志，资格不从只读源转移。中断积分的另外两个开源后端还没有EC05-Q-v2验收，
旧EC05-v1的执行失败或证据不足继续留在原44组收据中。

探索用的动态 timer、内部反馈事件和隐式复位仍在[扩展计划](#exploratory-cases)，
参考或验收尚未定稿，不纳入本版固定支持行。
