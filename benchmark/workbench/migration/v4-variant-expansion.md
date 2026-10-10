# 相近变体如何增加电路覆盖

本页分析的23个变体已与原39个代表来源合并，当前62个来源的范围、五类对应和优先级统一见[按电路功能组织的迁移候选清单](v4-migration-priorities.md)。本页保存保留理由、源码事实与checker差异，供实施时查阅；纳入候选不表示已成为正式评分题或参考实现合格。

原[400家族取舍索引](v4-migration-index.tsv)和审核统计保持冻结。这23项在旧索引中仍为`reserve_candidate`，当前纳入身份以统一清单为准；其余备选继续保留，不视为已经被代表题完全覆盖。

## 应该保留哪些差异

电路名称接近，不足以判断题目是否重复。我们需要同时看可观察行为、工程动作和验收方法。例如同样叫采样保持，边沿采样、有限采集、延迟取样、保持衰减和多通道读出，分别需要处理不同的时间关系或状态；它们可以共享电路来源，但不能用同一组瞬时码值检查代替。

建议把差异放在合适的位置，不追求每个方向相同题量。

| 变化 | 建议如何组织 | 判别例子 |
| --- | --- | --- |
| 同一行为合同的数值变化 | 同题公开实例或隐藏工况；可从中选择基础题代表，不按参数个数扩增任务数 | DAC位宽、采样幅度、同一事件规则下的门限与时钟周期。需要核对新参数是否真的改变码制、溢出或协议。 |
| 新状态、时间关系、接口协议或输入输出规律 | 独立候选任务，共享来源关系 | 跟踪时间影响保持值；读地址只改变选出通道；非重叠时钟必须留死区；校准码依被测响应更新。 |
| 同一电路承担不同工程工作 | 可有不同题型，但各自说明交付物与独立验收 | 建立比较器、修复有明确故障的比较器、编写其滞回测量模块。允许只取其中一种。 |
| 新增真实非理想效应 | 有工程依据和可区分checker时另立变体；缺依据时先补资产 | 单元失配影响DAC输出可以考察；给理想码距改名为glitch能量没有增加有效覆盖。 |

基础规则本身可以立题。这里的组织方式旨在避免把同一规律的数十个参数实例误报为数十种电路能力，不按代码长度、文件数或预估难度加权。不同电路类型也不需要全部做成系统题。

## 已纳入候选的功能变体

下表的源码事实来自旧库静态阅读，改编和checker列是设计建议。源码入口均固定在本仓库保存的 v4 r53，来源身份沿用[审核摘要](v4-audit-summary.json)。本次补充阅读不改写上一轮“76家族抽查”的冻结统计。

### 采样、判决与码电平路径

| 变体与对照 | 旧资产实际提供什么 | 对应五类与新增能力 | 需要重做，以及checker怎样区分 |
| --- | --- | --- | --- |
| 有限采集与保持衰减，相对024理想边沿采样 | [071](../../reference/v4/release/benchmarkv4-r53/tasks/071-acquisition-limited-sample-and-hold/evaluator/solution/acquisition_limited_sample_hold.va)在跟踪期定时更新 `held += alpha*(vin-held)`；[042](../../reference/v4/release/benchmarkv4-r53/tasks/042-sample-and-hold-with-droop-leakage/evaluator/solution/leaky_hold.va)采样后每个全局tick乘decay。 | 按规格构建模型；电路测试与表征。新增采集窗口长度和保持年龄的影响。 | 保留离散宏模型时公开tick相位和初态；若题意要求连续RC建立或泄漏，另建对应模型和依据。改变跟踪宽度与保持间隔，检查实际采样值及衰减；不能只测稳态。042的全局衰减不是从每次采样重新计时。 |
| 孔径延迟、双阶段跟踪，相对单沿直接锁存 | [072](../../reference/v4/release/benchmarkv4-r53/tasks/072-aperture-delay-track-and-hold/evaluator/solution/sample_hold_aperture_ref.va)在时钟沿之后再读取输入；[236](../../reference/v4/release/benchmarkv4-r53/tasks/236-dual-track-sample-hold/evaluator/solution/dual_track_sample_hold.va)由两个相位分别更新输入级和输出级，带轨限制。 | 按规格构建模型；电路测试与表征。区分实际取样时刻与输出晚发布，或增加跨相位内部历史。 | 072需规定再次触发、待执行采样与零延迟；它没有透明跟踪路径，不能照名字称完整track-and-hold。输入在触发后变化可区分“晚取样”和“早取样晚输出”。236需检查两阶段历史隔离、相位顺序及饱和。可先选一种，另一种留作后续。 |
| 普通窗口与滞回窗口，相对单门限/单组滞回 | [047](../../reference/v4/release/benchmarkv4-r53/tasks/047-window-comparator-detector/evaluator/solution/window_comparator_ref.va)检测上下边界，输入与输出使用局部VSS；[314](../../reference/v4/release/benchmarkv4-r53/tasks/314-hysteretic-window-comparator/evaluator/solution/hysteretic_window_comparator.va)在tick读取动态上下门限，进入/退出使用不同边界。 | 按规格构建模型；电路测试与表征。增加双边界、窗口内外历史和可调门限。 | 明确相等、非法窗口、启停与复位；314的旧行为是轮询采样，不能直接解释为异步瞬时比较器。分别从上、下方向进入和退出，同一输入值配不同历史；核对局部参考移动和门限变化。 |
| 分段、温度计与已知失配DAC，相对002二进制差分DAC | [014](../../reference/v4/release/benchmarkv4-r53/tasks/014-segmented-dac/evaluator/solution/segmented_dac.va)组合低位二进制和等权高段；[018](../../reference/v4/release/benchmarkv4-r53/tasks/018-unit-element-thermometer-dac/evaluator/solution/thermometer_dac_15seg.va)按启用单元数求和；[025](../../reference/v4/release/benchmarkv4-r53/tasks/025-dac-mismatch-unit-weighting-model/evaluator/solution/dac_mismatch_unit_weighting_model.va)使用已知非理想位权。 | 按规格构建模型；电路测试与表征。增加码制、单元身份或位权误差的可观测作用。 | 分段边界与等数量不同选通组合可区分位权错误。018等权单元的置换本来等价；考失配或DEM时必须新增有差异的单元并接入输出。025是固定四位权重，不能直接当成随机单位单元阵列。新误差测量需定义端点/最佳拟合等口径。 |
| 亚基数权重，相对普通二进制DAC | [243](../../reference/v4/release/benchmarkv4-r53/tasks/243-subradix-dac10/evaluator/solution/subradix_dac10.va)用1.8倍递增的权重求和，归一化常数单独给定。 | 按规格构建模型；后续可用于冗余转换系统的部件。新增不同权重与码空间关系。 | 可先保留为基础变体。checker按公开权重验收，不能沿用自然二进制递增必单调的假设；还需公开归一化定义。要考冗余SAR纠错，必须另补转换和数字重构，单个加权和不等于完整架构。 |

有限采集、孔径和已知失配不自动成为“从数据建立模型”。只有输入换成有来源、足够覆盖并带留出实验的电路观测，才适合该类；第一试点仍按已同意的真实采样级固定数据包建设。

### 多通道、时钟、反馈与实验协议

| 变体与对照 | 旧资产实际提供什么 | 对应五类与新增能力 | 需要重做，以及checker怎样区分 |
| --- | --- | --- | --- |
| 四通道保持与顺序读出，相对024单通道 | [349的bank、控制器与driver](../../reference/v4/release/benchmarkv4-r53/tasks/349-multichannel-sample-readout/evaluator/solution/)把同时采样、地址轮换、暂停及结果保持组合起来。 | 按规格构建模型；电路测试与表征。增加通道身份、读出顺序和模拟值与valid的对应。 | 明确同时采样/读出时读新值还是旧值，及观察窗口。旧driver在read高时跟随选中保持节点，不能默认一次读沿后锁存。四路使用不同的时变输入，验收采样后改变输入、暂停恢复、回绕及复位。健康单通道工程之后，可另设计扩展与集成。 |
| 两相非重叠发生器，相对307使用外部两相 | [375](../../reference/v4/release/benchmarkv4-r53/tasks/375-nonoverlap-clock-generator/evaluator/solution/nonoverlap_clock_generator.va)先关闭两相，再由全局tick倒计时发布待激活相位。 | 按规格构建模型；电路测试与表征。增加死区调度、请求覆盖和取消。 | 公开按tick计数还是按输入沿后的精确时间计死区；旧tr声明未用于输出平滑。同刻请求/计时顺序、过短周期及disable中断需定清。由真实两相波形测死区并检查始终不重叠，改变输入沿相对tick的位置，不能只读deadtime_metric。 |
| 正交LO生成，相对364/400使用LO混频 | [396](../../reference/v4/release/benchmarkv4-r53/tasks/396-quadrature-lo-generator-divided-clock/evaluator/solution/quadrature_lo_generator_divided_clock.va)按10、11、01、00轮换，I/Q为输入频率的1/4，相差一个输入周期。 | 按规格构建模型；电路测试与表征。增加正交状态顺序、频率关系和重启。 | 独立测I/Q实际边沿、占空比与相位差；检查不同输入占空比、复位及重新使能。quad_ok是内部次数资格，div_metric是状态编码，均不代替测量。相噪、镜像抑制和失配未由这一理想序列证明。 |
| 持续失调伺服与共模调节，相对109/183有限次搜索 | [369](../../reference/v4/release/benchmarkv4-r53/tasks/369-offset-cancellation-servo/evaluator/solution/)由当前修调量计算残差并调节有符号码；[390](../../reference/v4/release/benchmarkv4-r53/tasks/390-common-mode-feedback-loop/evaluator/solution/)对两路施加相同修正。 | 按规格构建模型；电路测试与表征。新增持续跟踪、双极性编码，或共模校正与差模保持两个维度。 | 不能因没有输出节点回读就判定没有反馈；需检查预测残差和实际执行输出的等价范围。369要补样本对齐和复位语义；390只有单向0..7修调，且metric在输出限幅前计算。验收正负变化、不可达目标、端点以及实际共模/差模，不接受码正确而输出错误。 |
| 静态trim叠加自适应校准，相对PGA或单纯失调抑制 | [306](../../reference/v4/release/benchmarkv4-r53/tasks/306-instrumentation-amplifier-offset-trim/evaluator/solution/)将外部码和内部适应量合成为修正，再实际施加到差分放大核心。 | 按规格构建模型；电路测试与表征。新增配置与自适应状态协作，以及校准和正常放大的工作模式。 | 先规定零输入校准或已知训练条件，避免把真实差分信号当失调消掉；适应状态无界而修正电压有限幅，需定工作区和恢复行为。ready只按次数置位，不能当精度达标。验收禁用保持、外部码变更、正常差分增益和实际残差。 |
| 可调滤波与建立资格，相对038静态增益、307积分 | [334](../../reference/v4/release/benchmarkv4-r53/tasks/334-baseband-anti-alias-filter-macro/evaluator/solution/baseband_antialias_filter_macro.va)用码控制离散一阶更新；[370](../../reference/v4/release/benchmarkv4-r53/tasks/370-opamp-feedback-settling-monitor/evaluator/solution/opamp_feedback_settling.va)使输出逐步接近限幅增益目标，并连续三次合格后置settled。 | 按规格构建模型；电路测试与表征。新增可调记忆、目标变化后的动态轨迹与连续资格。 | 明确轮询/事件合同和时间尺度。334不能凭名称证明采样前抗混叠；370不代表真实运放高阶稳定性。根据实际输出测阶跃和离散频响，检验短暂进入误差带后又离开的资格取消；限幅目标的settled不等于未削顶增益正确。 |
| 可重武装并报告溢出的时间测量，相对060周期性仪表 | [346](../../reference/v4/release/benchmarkv4-r53/tasks/346-tdc-measurement-system/evaluator/solution/)组合武装、边沿计数、stop锁存、溢出自动完成与valid输出。 | 按规格构建模型；电路测试与表征。新增实验控制和满量程异常处理，计数器基础题也有明确工程用途。 | 明确同时start/stop/clock优先级，验证valid与overflow传播后的一致性。用独立边沿表检查0、1、254、255、256个计数、重复start、stop-before-start、完成后保持及复位中断，不能只验一个正常长间隔。 |

### 先补工程条件的系统与测量变体

[302分数分频PLL](../../reference/v4/release/benchmarkv4-r53/tasks/302-fractional-n-divider-accumulator-flow/evaluator/solution/fracn_pll_timer_ref.va)和[361 DLL](../../reference/v4/release/benchmarkv4-r53/tasks/361-dll-delay-line-lock/evaluator/solution/)值得保留。前者调整振荡频率并产生分数计数序列，后者调整输入时钟的延迟，都具有实际模型反馈。它们能补足当前部件题的系统行为，但尚未证明锁定和扰动恢复。302的反馈每次计数达标只翻转一次，完整反馈周期涉及两次计数，不能照搬除以N的公式；分数参数范围也需重新定义。361要明确边沿配对、最大延迟、单个pending请求容量与实际电压阈值下的延迟。先分别验收分频序列或固定码延迟，再验收闭环，适合规格建模或系统表征；建立健康整数N或固定延迟基线后，才适合扩展题。

[325粗细TDC](../../reference/v4/release/benchmarkv4-r53/tasks/325-fine-coarse-tdc-encoder/evaluator/solution/)比346增加亚周期细分，但原细残差只测stop到最近参考沿的比例，不一定足以恢复任意start到stop的完整间隔。首轮period初值和重启历史存在缺口，应先明确预热与有效性，检查首次短测量和跨边沿stop，再决定粗细拼接合同。

[190 RDAC逐码扫描](../../reference/v4/release/benchmarkv4-r53/tasks/190-linearity-rdac-offset-sweep/evaluator/solution/linearity_rdac_offset_sweep.va)比183单点搜索增加逐码、多轮搜索和参考网格推进，适合作为响应驱动表征控制器。需配实际RDAC与比较器，规定结束条件、每码估计及DNL/INL口径。checker应检查搜索确实响应比较器，再根据实际输出核对曲线；文件名中的linearity不等于已有线性度测量。

## 建设顺序

建设优先级集中在[统一清单](v4-migration-priorities.md#统一功能清单)，本页不另设排期。先补工程的方向有捕获范围、测量历史或被测对象等具体缺口；健康基线和校准条件齐备后可调整次序。基础码制、计数和滤波任务也有保留价值，不必强加系统复杂度。

## 相近来源怎样转成五类题型

规格建模与测试表征可以优先复用以上变体，但不能只换题面标题。建模题验收候选的电路输出；测试题验收候选是否准确测出了被测模型的行为，以及是否正确处理未完成、缺边沿或无效窗口。DUT本身性能不好，不应让测量准确的测试模块被判错。固定激励下随仿真直接出结论的基础任务仍有价值。

修复题需要具体、有可观察后果的故障。允许整体重写后，仍需说明任务是否考察有意义的状态、交互或诊断。可以利用相近变体构造负例，例如把晚取样写成晚输出、把共模伺服符号写反；负例用于校准checker，不自动派生成另一道修复题。

扩展与集成要从健康工程出发。合适的关系包括单通道扩成可寻址多通道、固定抽头DFE加入训练、等权DAC加入有实际输出影响的单元失配与DEM。分别先确认新增能力、保留行为和允许改动。给定架构中缺一个模块而要求补齐，仍归规格建模。现有旧参考尚未建立健康基线时，这些是后续建设方向。

数据建模需要不同的输入资产。先完成真实采样级试点；其他变体可逐步提供实验组织和接口，但不能把已知公式生成的记录改称真实电路数据。后续开放主动表征时，激励选择与查询预算属于额外的任务设置。

## 验收与统计如何避免虚假的多样性

每个拟独立变体应附一个能说明新增要求的反例。例如旧单沿保持模型应在“跟踪时间改变最终值”的场景失败；只算平均分频率的实现应在要求分频序列的场景失败。反例用于检验新增要求是否真正进入checker，正式评分仍来自公开合同的独立判据，不能只依赖某一对参考解和负例。

隐藏工况应覆盖同一公开合同，而不增加未公开的噪声、延迟、饱和或错误恢复要求。新增指标需要先确认输入足以辨识、观测窗口足够，以及数值与事件容差的来源。轮询宏模型与连续模型可以分别有价值，应公开各自的行为目标，不能用电路名称代替差异。

同源任务继续保留来源关系。后续登记卡时记录旧family、共享实现/测试资产及变体新增行为；跨旧family但明显同源或只改参数的任务也要检查关联，不凭旧编号不同就认定独立。分析成绩同时列任务数、来源组和行为覆盖，保留任务级成绩，也观察同源任务是否成组成功或失败。完整仓库任务可以单列；本方案不引入难度、文件数或代码量权重，也暂不改计分公式。

现有后端选择原则继续适用。按每题所需行为建设并校准固定环境，合法VA被后端能力挡住时处理环境问题。只有缩减公开要求才能运行的版本另记简化变体，不将其作为原题开源复现的证明。

本页只完成源码分析与候选组织；没有新增编译、仿真、checker校准或Agent试做。变体的实际难度、彼此区分度和健康参考质量，留在建设与试跑阶段判断。
