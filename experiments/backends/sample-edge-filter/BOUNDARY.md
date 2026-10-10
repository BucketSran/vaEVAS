# 边界诊断与根窗口修复

**当前结论：本批工程对照通过，18 条瞬时阶段差异已接受为已知差异。严格逐点诊断仍为 FAIL。**
实测工作使用 `codex/sample-edge-filter` 中基于 `ad6f3577` 的源码。实现、验收标准和此报告同批交付；下列历史收据保留各次运行当时的未提交身份。
实现曾修复事件时间误差进入边沿、滤波时被丢弃的问题；没有复制 Spectre 的数值回调落点。

<a id="accepted-timer-18"></a>

## SEF-TIMER-18 的接受决定

2026-10-10，用户明确要求把这 18 条记录为可接受的已知差异，并从 EVAS 修复目标中移出。
[接受记录](accepted-differences.json)保存全部 18 条原记录、身份、原判定和重新调查条件。
相关任务由 [#96](https://github.com/BucketSran/vaEVAS/issues/96) 维护，
通用分类由[验收标准](../../../docs/contributing/validation.md#classify-differences-before-selecting-a-repair)维护。

| 范围 | 决定 |
| --- | --- |
| 四类模型 × base/tight/fine，12 对运行、52,200 个共同时间点 | 原工程预算不变，工程对照通过 |
| TIMER 3 条、INTERRUPT 9 条、ISOLATION 6 条，RESET 0 条 | Spectre 在该观察点领先一个事件；保留严格 FAIL，不要求清零 |
| Spectre 21.1.0.509.isr12；EVAS 候选身份 | 以 [adaptive-root 收据](adaptive-root-receipt.json)的源码清单和内核哈希为准；该收据记录实测时的未提交身份 |
| 原始模型、设置、checker、F/I 和大波形 | 全部保留；原始材料仍 local-only，不宣称新执行或公开完整复现 |

这些 timer 显式使用 `time_tol=1 ps`。[LRM 2.4 §5.10.3.3](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
允许在该容差范围内安排事件点。名义时刻与窗口内另一求解点可以产生不同的瞬时跳变侧，
不能仅凭这种差异判为 EVAS 缺陷，也不将所有观察统称为 Spectre 舍入错误。
本批最终次数、工程事件时窗、采样值和全部记录上的边沿/滤波预算均通过；独立分析中 EVAS 符合名义日程。
这组有限观测没有证明任意电路或全轨迹精度。

不为清除这 18 条而加统一 epsilon、改写正确 timer 排序、移动输出查询或复制 Spectre 接受网格。
普通查询不改变历史、误差包围真实、试算失败不污染状态等原要求继续有效。
只有出现新的语义错误、非法触发时刻、漏/重复/错序事件、错误历史、误差包围失败或下游超预算，才重新调查相应问题。
模型、设置、消费者或后端版本改变后复验受影响范围，不自动继承本记录。
C1、原 #79、VCO、Spec B、零容差 timer 探针，以及本批初态/stop 失败探针均不在此次接受范围内。

以下是接受决定之前的逐轮诊断。文中的“完整对齐失败”“待实现兼容策略”等保留当时结论；
其“必须清零才完成”的作用已由上面的决定替代，严格诊断的数值结果没有改写。
[首次收据](receipt.json)、[边界收据](boundary-receipt.json)和后续收据仍是原执行/分析快照。

## 为什么仍有跳变侧差异

对 `SEF-INTERRUPT/tight` 增加两种只读观察：在 timer 回调中记录 `$abstime`，并将这个值保存到输出节点。
新增 Spectre 原模型复跑与首次结果的全部 6,366 行逐位相同；加观察后的原节点、时刻也逐位相同。
因此，本例的仪表没有改变被观察结果。

第四次 timer 的名义时刻是输入 binary64 `1e-6` 的四倍，即 `3.9999999999999998e-6 s`。
实际观察如下，全部使用 Spectre 21.1.0.509.isr12、17 位输出：

| 模型／设置 | 回调内 `$abstime`（s） | 原生波形首次输出计数 4 的时刻（s） |
| --- | ---: | ---: |
| 完整链路，保留 strobetimes | 3.9999999999999990e-6 | 3.9999999999999990e-6 |
| 移除 transition/filter，保留 strobetimes | 3.9999999999999998e-6 | 3.9999999999999998e-6 |
| 同一最小模型，移除 strobetimes | 3.9999999999999990e-6 | 3.9999999999999990e-6 |

完整链路的回调本身早一个 ULP，约 `8.47e-22 s`。所以 1.15 V 的保持差异来自这一个时刻两端处在不同跳变侧，
不是整段波形偏差 1.15 V，也不是仅有文本导出错位。
EVAS 的固定 timer 使用精确二进制有理数判断物理相位，在这个左邻点仍输出事件前计数。

**已证实的是回调时刻依赖所测下游动态和 strobe 设置；尚未确定的是 Spectre 内部步长、舍入和事件调度的具体算法。**
这些数据不足以推导“每次都提前一个 ULP”的兼容规则。本次未改变精确 timer 排序、同刻分组或查询不改变历史的约定。
不同设置之间是否存在同一时刻的不可兼容计数，还需更广的专门实验；不能从本组推断必然冲突或必然可逐点复现。

## 本次真正修复的漏洞

1. `cross` 得到 `[a,c]` 的事件时间包围，但原 `transition` 只收到执行代表 `b`。
   这相当于把尚不确定的时刻当成精确值。新入口把完整窗口传入延迟激活和边沿起止计算。
2. 零延迟时，真实事件可能在 `b` 之前已经改变输入。只沿旧输入积分到 `b` 会漏掉面积。
   新实现保存这一段的滤波包围，窗内查询和以后回查都使用它，并将其纳入历史身份和失败回退。

独立反例的根是 `sqrt(2)`。原内核在 `vabstol=1e-10 V` 下接受了约 `1.06e-4 V` 的滤波误差。
另一个内核反例中，事件窗口 `[1,1.001]`、边沿 0.5 s、滤波时间常数 0.25 s，
执行时刻本应包住约 `3.99 µV` 的前缀积分，旧实现却返回 `[0,0]`。两个失败都在改动前实际复现。
公式与拒绝范围见[算子手册](../../../evas/docs/math/operators.md#transition-filter)。

## 新的实际 Spectre 对照

四个同源码实验固定 `u(t)=t`、`cross(u²-2)`、0→1 边沿、0.5 s 边沿时间和 0.25 s 滤波时间常数。
改变延迟为 0／0.125 s，以及 `cross` 的 time/expr tolerance 为 `1e-3`／`1e-12`。
Spectre 请求 `reltol=1e-9`、`vabstol=1e-11 V`、`traponly`、`maxstep=1/256 s`；
实际 transient `reltol=1e-10`，其余控制由原生日志读回，不把请求值当作实际值。
观察点预先固定为 0、1、1.75、2.5、3 s，均直接使用原生记录；这组检查连续输出，不代替上面的精确事件阶段检查。

| 延迟 | Spectre 宽事件容差：滤波误差 | Spectre 窄事件容差：滤波误差 | EVAS 窄事件容差：滤波误差 |
| --- | ---: | ---: | ---: |
| 0 | 261.98 µV | 80.38 nV | 0.101 pV |
| 0.125 s | 201.92 µV | 80.15 nV | 0.216 pV |

误差均为五个观察点相对独立解析解的最大值，不是全轨迹证明。
EVAS 在宽根窗口配 `1e-10 V` 要求时，两例均正确拒绝；收紧根窗口后均接受并达到该预算。
宽根窗口配 `1e-3 V` 时也均在预算内，但不意味着与另一套数值回调实现逐点相同。
这修复了“错误接受高精度请求”，尚未实现依据下游电压预算自动细化事件根。

## 原组合复测与剩余工作

- 原四类模型的稀疏、密集及三套 Spectre 原生网格，共 20 个 EVAS 请求仍通过原工程判据。
  共同查询的完整解、事件记录逐位相同；全行滤波差保持为基础档 6.84 µV、紧档 0.103 µV。
- 严格计数检查依旧为 **18 条失败**，没有删除事件窗里的记录。表格已改为“部分通过”，整体任务不计完成。
- Rust：223 通过、1 个已有忽略项。Python 主回归 136 通过；补充选择 30 通过，与主回归有重叠，不相加充当独立测试总数。
  另外执行精度链、timed composition、dynamic closure 和 mixed dynamics，58 项通过。
  增补检查包含正负投影、负增益、中断旧边沿、窗口内及过去查询、近邻固定 timer、宽预算拒绝及窄根精度。
- 独立数值审查与证据审查均无待处理发现，原始报告及哈希保留在收据所指本地材料中；这不是完整对齐的合并批准。
- 新事件窗口下界早于已提交滤波历史时仍保守拒绝；任意重叠窗口、滤波反馈和高阶消费者不在新增支持范围。

后续精确边界工作需要独立的“允许回调时刻及可观察阶段”契约，明确物理根、数值回调和输出请求之间的关系。
先用同源码的设置扰动实验确定可以稳定复现的规则，再决定是否增加数值回调策略；不能把这次误差包围修复当作该策略已经实现。

## 回调规则的后续实测

新增 30 次 Spectre 21.1.0.509.isr12 执行，分为 21 个探索条件和 9 个在运行前写下预测的留出条件。
这组实验只诊断固定 timer。**EVAS 内核没有因此改动，原 18 条严格阶段差异仍失败。**
输入、工具、分析身份及全部条件见[回调收据](callback-rules-receipt.json)。

在本组正显式容差、互不重叠的 timer 窗口内，下面的条件规则重现了观测：

> 已知仿真实际接受的时间点序列，下一事件的名义时刻为 `start + k*period`。
> 第一个进入 `[名义时刻 − timetol, 名义时刻 + timetol]` 的接受点执行该事件。

[独立回放](callback_policy.py)只读取时间序列和 VA 参数来预测次数，再与原生计数列比较。
它没有从计数列提取触发点来构造答案。17 个正容差探索条件共 12,462 行、129 次回调，
9 个留出条件共 5,069 行、28 次回调，计数均匹配。
原 TIMER、INTERRUPT、ISOLATION 三类模型的三档历史运行也全部匹配，共 12 条实例轨迹、53,633 个实例观察、57 次回调。
该回放解释了原 18 条计数差异，但它使用 **Spectre 自己的接受网格**，不能计作 EVAS 已经独立复现这些结果。
RESET 的 cross 轨迹不属于这个 timer 规则的验收分母。
回放把输入 binary64 参数转成精确有理数，计算 `start + k*period`。
这些容差窗口还不足以区分 Spectre 内部采用精确目标、逐次浮点相加或其他调度算法。
留出预测按执行记录在运行前保存，尚未发布为不可变的预注册记录。

关键留出实验使用一次性 timer，名义时刻为 4 µs：

| 改变的条件 | 实际回调 | 结论 |
| --- | --- | --- |
| 无额外强制点，容差 1 ps | 4 µs | 基准 |
| 在事件前 0.5 ps 插入 strobe，容差 1 ps | 4 µs − 0.5 ps | 容差内的先到接受点触发 |
| 保留这个 strobe，容差改为 0.01 ps | 4 µs | 该点已在允许窗口外 |
| strobe 提前 1.5 ps，容差 1 ps | 4 µs | 窗外点不触发 |
| strobe 推后 0.5 ps，容差 1 ps | 4 µs | 4 µs 已有更早的接受点，后到 strobe 不改变回调 |

另一个 10 ns 容差留出条件在事件前 7.7734375 ns 的自然接受点触发，早于我们插入的前 5 ns strobe。
因此“回调只会吸附到 strobe”也不成立。
仅把 `maxstep` 减半或改为三分之一，偏移可到 284 ULP，约 `2.59e-19 s`。
这两例全部 16 次回调均逐位等于前一原生时间加 `maxstep`，支持接受步的浮点推进参与偏移的解释。
这不证明所有 timer 都以这种方式累计时间。
原宽步长例的最后一位具体如何产生，仍不能从这组数据反推出 Spectre 私有算法。

其他假设的结果与限制如下：

- 直流输入、移除下游动态后仍出现偏移。PWL 拐点不是必要条件。
- `transres=1e-24 s` 保留了本例偏移，`transres=0` 被 Spectre 拒绝。不能用它解释全部 timer 差异。
- 二进制精确周期控制在本组回调落点准确，但不证明任意网格下都准确。
- 三个显式 `timetol=0` 条件实际只有 7 次回调，缺少约 3 µs 的一次。日志与原生计数一致，原因未闭合。
  它们留在 21 条件总账中，不纳入正容差规则，也不把漏事件复制成 EVAS 语义。
- 首批 02→03 控制同时改变了未使用的 clk/rst 直流值。原输入保留，H00 补做只改变 u 的控制，结果与 03 相同。
- 单 strobe 运行的原生输出可能没有 t=0，末点也可能略越过 stop。这里只核验完整 timer 窗口，
  不授予初态或全轨迹精度资格。原始首末时间、失败执行和零容差结果全部保留。

这为下一步实现划清了边界：名义日程、容差内实际执行点、普通输出查询必须分别表示。
strobe 是求解日程的一部分；普通查询不能为了匹配一次比较而改变事件历史。
实际回调改变采样值后，保持状态、边沿和滤波必须从同一回调状态继续。
这些是待实现的兼容策略要求，不能用本次只读回放替代。
精确逐位复现仍需要复现产生接受点的规则。当前尚未实现该规则，也不保证可从公开资料恢复其所有细节。

后续不以复制完整接受网格作为默认修复目标。它可以帮助诊断某一版本的数值行为，
但即使网格相同，积分、算术和事件状态求值仍可能不同，也不等于得到了数学精确解。
下面先把数学精度和后端兼容性分开检查，原严格失败继续保留。

本轮分析修正保留在本地决策记录中。探针解析最初未处理日志进度字符，后经原生数据交叉核对修复。
独立审查补齐了固定分母、失败退出、连续序号、冻结输入和 raw/rows 身份校验。
留出结果首次 tar 传输被 macOS 消费 AppleDouble 元数据，原副本保留为不完整；
从同一远端目录用 zip 重传至 `callback-rules/transfer-v2/holdout-results` 后完整校验。
不是删除清单键绕过核验。原始资料仍为 local-only。

## 数学精度与回调时移的分开验收

本轮没有修改 EVAS 内核，也没有新启动仿真。复用原来的 12 对实际运行，
共 52,200 个共同原生时刻；双实例展开后是 15 条轨迹、66,221 个实例观察。
95 个 Python/Rust 运行时源文件与归档执行快照相同，工具与结果通过原收据校验。
分析器、检查结果和限制见[误差分解收据](error-decomposition-receipt.json)。

独立参考从冻结的 PWL 刺激重新计算采样值，再计算边沿多边形和一阶滤波解析卷积。
输入 binary64 值按精确有理数处理，卷积使用 60 位 Decimal 求值。
它不读取 Spectre 的保持、边沿或滤波电压来生成答案。

每个同一物理时刻使用四个值：实际 Spectre 输出 S、实际 EVAS 输出 E、
按名义事件时刻计算的参考 R0，以及按首个原生计数变化行时刻计算的参考 Rs。
逐点保留带符号关系 `S − E = (S − Rs) + (Rs − R0) − (E − R0)`，不把不同发生时刻的最大值相减。

| 检查项 | 本批结果 | 能说明什么 |
| --- | --- | --- |
| EVAS 相对名义参考的滤波偏差 | 最大 4.03×10⁻¹⁵ V | 在这些观察点上没有发现新的数学精度错误 |
| Spectre 相对观察时刻参考的滤波残差 | 基础档 6.837 µV，紧档 0.1030 µV，更细步长档 0.1026 µV | 收紧容差减小本批主要滤波残差；不是纯积分误差测量 |
| 单独替换事件时刻造成的滤波变化 | 最大 0.109 nV | 本批主要滤波残差无法仅由事件时移解释 |
| 保持节点的全行差异 | 最大 1.15 V；按观察时刻重算后，Spectre 保持残差最大 1.48×10⁻¹⁶ V | 大差异发生在跳变两侧，不代表整段电压误差 |
| 严格事件阶段 | EVAS 与名义参考无差异；Spectre 有 18 条提前一个事件的记录 | 原 EVAS/Spectre 严格验收仍失败，不能由上面结果豁免 |
| EVAS 报告的电压包围 | 所检查保持、边沿、滤波点均包含名义参考 | 有限点交叉检查，不能升级成全轨迹误差证明 |

Rs 的时刻是**首次观察到计数变化的原生行**，不是对隐藏回调时刻的完整取证。
因此 `S − Rs` 还包含输入求值、算术和算子实现差异。RESET 条件的边沿残差约 0.125 nV，
也说明不能将剩余差值全归给积分器。独立审查另用 85 位分段 ODE 递推复核 3,787 个参考点，
与卷积实现的最大差约 3.68×10⁻⁵⁹ V；这验证求值方法，不是对 Spectre 私有算法的证明。

后续改动须分别给出名义数学误差、允许事件时移造成的电路变化、固定 Spectre 版本的实际差异。
若新增数值回调策略，必须独立规定名义事件、实际执行点及普通查询的关系，
并验证采样、边沿、滤波、过去查询和失败回退都沿用同一事件历史。
本轮没有据此改变精确 timer 契约、放宽原判据或解除原 18 条失败。

```sh
python3 -B experiments/backends/sample-edge-filter/error_decomposition.py runs/sample-edge-filter-20261010/spectre runs/sample-edge-filter-20261010/boundary/evas runs/new-error-decomposition.json
python3 -B -m unittest discover -s experiments/backends/sample-edge-filter -p 'test_error_decomposition.py' -v
```

分解命令成功只表示诊断完成，输出中的 `original_strict_verdict` 仍为 FAIL。
新输出不得覆盖旧记录；归档缺失、身份变化或配置分析失败会返回非零。

## 复验与材料

```sh
python3 -B experiments/backends/sample-edge-filter/boundary_replay.py runs/sample-edge-filter-20261010/spectre runs/sample-edge-filter-20261010/boundary/evas
python3 -B experiments/backends/sample-edge-filter/callback_probe.py freeze ORIGINAL_CASE_DIR NEW_PROBE_INPUTS
python3 -B experiments/backends/sample-edge-filter/callback_probe.py roots NEW_ROOT_INPUTS
python3 -B experiments/backends/sample-edge-filter/callback_probe.py run FROZEN_INPUTS NEW_RESULTS --profile EXISTING_PROFILE
python3 -B experiments/backends/sample-edge-filter/root_compare.py SPECTRE_ROOT_RESULTS NEW_EVAS_RESULTS KERNEL
```

第一条命令当前应返回退出码 1。新运行必须使用新输出目录。
原始材料保留于 `runs/sample-edge-filter-20261010/boundary/`，当前为 local-only。
本次实际启动 Spectre 10 次：8 次完整诊断，另 2 次在仿真后因探针解析依赖／设置记录缺失中断，失败目录保留。
`BUILD.json`、`SOURCE_MANIFEST.json`、`snapshot/` 与保存的内核绑定新候选；`results-v3/` 保存回调探针，
`root-spectre/` 保存同源码精度对照，`root-evas-checked/` 保存正反验收，`strict-final.json` 保存全部 18 条差异。

回调诊断使用 `callback_rules.py freeze ORIGINAL_MINIMAL_DIR NEW_INPUTS` 冻结输入，
然后复用 `callback_probe.py run NEW_INPUTS NEW_RESULTS --profile PROFILE`。
本次首批生成器的冻结版本保留在 `callback-rules/package/`，当前生成器已修正直流单因素控制。
对已有证据重新分析，无需重跑 Spectre：

```sh
python3 -B experiments/backends/sample-edge-filter/callback_rules.py analyze COMPLETE_RESULTS NEW_ANALYSIS.json --inputs FROZEN_INPUTS
python3 -B experiments/backends/sample-edge-filter/callback_policy.py COMPLETE_RESULTS NEW_POLICY.json --kind probes
python3 -B experiments/backends/sample-edge-filter/callback_policy.py runs/sample-edge-filter-20261010/spectre NEW_CHAIN_POLICY.json --kind chain
python3 -B -m unittest discover -s experiments/backends/sample-edge-filter -p 'test_callback*.py' -v
```

首批 21 条件有上述 4 条失败或不适用项，因此两个分析命令都应返回非零。
留出条件使用完整重传目录，两个命令均通过。原 `boundary_replay.py` 仍返回 18 条失败。

<a id="adaptive-root"></a>

## 电压请求驱动的输入根细化

本增量让宽 `cross` 容差下的部分高精度请求自动恢复，未改变事件的数学观察约定。
前一候选已经修复根窗口丢失，但 `cross(u²−2,+1,1e-3,1e-3)` 接边沿和一阶滤波时，
`vabstol=1e-10 V` 仍被拒绝。此次先复现该拒绝，再加入发布前预检。
预检检查事件及首个历史截止点；若电压验收失败，在原根区间内继续求解并重试一次。
原公开容差、模型、刺激和输出误差检查不变，方法和限制见[事件手册](../../../evas/docs/math/events.md#voltage-demand-root-refinement)。

使用新内核执行原四个根诊断模型，各申请两档 EVAS 电压预算，共八个请求。
Spectre 侧复用前轮四次实际仿真，原源码、设置、原生数据清单经旧收据哈希核验；本增量没有新增远端运行。
下表是原五个固定时刻的滤波数学偏差，不是连续时间上界。

| 模型 | EVAS 原状态，1e-10 V 请求 | EVAS 本候选最大数学偏差 | 原 Spectre 最大数学偏差 |
| --- | --- | ---: | ---: |
| 宽 cross 容差，零延迟 | 拒绝 | 2.78×10⁻¹⁶ V | 2.62×10⁻⁴ V |
| 宽 cross 容差，0.125 s 延迟 | 拒绝 | 6.67×10⁻¹⁶ V | 2.02×10⁻⁴ V |
| 紧 cross 容差，零延迟 | 通过 | 1.01×10⁻¹³ V | 8.04×10⁻⁸ V |
| 紧 cross 容差，0.125 s 延迟 | 通过 | 2.16×10⁻¹³ V | 8.02×10⁻⁸ V |

EVAS 精度足够时不强制细化，因此此处宽容差加高精度请求的结果可以比原本的紧容差更接近解析答案。
这不能解读为 Spectre 应满足 EVAS 的同名预算，也不证明 EVAS 普遍更准确。
实际 Spectre 版本、有效设置与原失败见[旧收据](boundary-receipt.json)，不会重写。
`root_compare.py --policy retained-window` 保留旧拒绝要求；`--policy adaptive-root` 明确采用本轮恢复要求。
两者均保留原五个观测点和误差预算。

```sh
python3 -B experiments/backends/sample-edge-filter/root_compare.py runs/sample-edge-filter-20261010/boundary/root-spectre runs/new-adaptive-root evas/rust_core/target/debug/evas-kernel --policy adaptive-root
```

本候选只自动处理相互分离、无状态/历史依赖的非线性根。精确 timer 不变；相连事件簇、
历史根和全时域误差预算分配尚未覆盖。首个截止点之后仍可能因历史包围过宽而拒绝，
预检不是全波形合格证。低于当前算术误差下限的请求继续失败。
新内核的 20 个工程请求均通过原工程判据，52,200 行严格检查仍保留完全相同的 18 条阶段差异。
[本轮收据](adaptive-root-receipt.json)记录新构建、复用来源、独立复核和全部失败历史。
原始材料在 `runs/sample-edge-filter-20261010/adaptive-root/`，为 local-only。
