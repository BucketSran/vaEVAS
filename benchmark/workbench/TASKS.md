# 两批 56 道题总览

本页汇总 v2 的 37 道题和下一批的 19 道题，供按工程动作与电路功能做宏观 review。每个任务只计一次，权重均为 1；参数场景、作者错版和共享来源不另增题量。五类不要求数量相等，也不因多文件或系统规模加权。

这里的“已建设”指已有题目资产、参考解、独立 checker 及对应作者校准记录，不表示已冻结公开发布，也不表示所有后端均可复现。下一批没有模型实验，本页不讨论模型通过率或推断难度。精确接口、数值、可修改范围和当前验收合同以各任务的 `instruction.md` 为准。

## 五类工程动作

| 工程动作 | 前批 | 新增 | 合计 | 典型输入 → 交付 | 独立 checker 的判断对象 |
| --- | ---: | ---: | ---: | --- | --- |
| 按规格构建模型 | 19 | 8 | **27** | 接口、行为/动态规格，必要时给定模块职责 → 单模块或指定模块组成的 VA 模型 | 实际波形对照状态、事件、解析式或独立数值解；系统题另验组件职责及真实连接 |
| 从数据建立模型 | 1 | 1 | **2** | 真实电路的固定表征数据、输入和工况说明 → 可接受新输入、保留动态历史的 VA 模型 | 完整保留实验上的自由运行误差；不把正确输出反馈给候选模型 |
| 扩展与集成 | 2 | 4 | **6** | 可运行健康基线、固定工程及新增需求 → 扩展模块、连接或控制功能 | 原能力兼容、新能力及实际闭环作用，避免只生成正确监控数字 |
| 诊断与修复 | 5 | 0 | **5** | 有缺陷的 VA 源码、规格和固定测试环境 → 修复后的指定源码，允许整体重写 | 故障被消除，同时正常行为、复位、取消与跨模块依赖仍正确 |
| 电路测试与表征 | 10 | 6 | **16** | 可读 DUT/观测、接口、指标与实验合同 → 在线仪表、激励与测量模块或响应驱动测试台 | 从实际输入、DUT 响应和事件独立重算指标，并检查实验流程与无效状态 |
| **总计** | **37** | **19** | **56** | | |

测试与表征保留三种有价值的形式：伴随仿真直接出指标；施加规定激励并测量；根据真实响应决定下一步激励。不是每道题都需要自适应流程。例如 DAC 线性度题读取固定扫描，而 LDO line/load 题需要等待真实响应后推进阶段。正确测出 DUT 不达标也可以通过，不能把“DUT 合格”误当成“测量模块合格”。

## 按电路功能看覆盖与合同

下表按主要电路功能归组，每道题只进入一组，便于核对数量。跨组的工程关联在后面的同源关系表中保留。“新增”只指相对前批 37 题，不表示这些想法或原始资产从未出现在历史 benchmark 中。

| 电路功能 | 规格 | 数据 | 扩展 | 修复 | 测试 | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 采样与多通道读出 | 2 | 1 | 1 | 0 | 0 | 4 |
| ADC 结构与转换控制 | 3 | 0 | 0 | 0 | 0 | 3 |
| DAC 与转换器指标 | 5 | 0 | 0 | 0 | 2 | 7 |
| 放大与模拟信号处理 | 5 | 0 | 0 | 0 | 3 | 8 |
| 连续 OTA 动态 | 1 | 1 | 0 | 0 | 1 | 3 |
| 比较器与门限 | 2 | 0 | 0 | 0 | 3 | 5 |
| PLL 与时钟 | 3 | 0 | 2 | 1 | 3 | 9 |
| 滤波、均衡与 RF | 5 | 0 | 1 | 0 | 1 | 7 |
| 模拟校准与伺服 | 1 | 0 | 2 | 0 | 0 | 3 |
| 电源、复位与响应测试 | 0 | 0 | 0 | 4 | 3 | 7 |
| **合计** | **27** | **2** | **6** | **5** | **16** | **56** |

| 电路功能（前批 + 新增） | 已覆盖内容及本批增量 | 输入材料 → 交付要求 | checker 思路 |
| --- | --- | --- | --- |
| **采样与多通道读出（4 + 0）** | 理想边沿采样、有限采集、真实采样级动态辨识、四通道读出 | 采样规格，或真实电路固定数据包，或健康采样模块与读出框架 → VA 采样模型/多通道工程 | 采样时刻与保持历史；真实电路保留实验上的动态误差；同时采集和顺序读出，并验证复用模块的实际作用 |
| **ADC 结构与转换控制（3 + 0）** | 流水级、一级 ΣΔ、工程内补 SAR 前端逻辑 | 残差/状态规格、接口，或固定 DAC/比较器工程 → 转换级或控制模块 | 量化与残差递推、积分历史、逐位判决和握手；按题面固定工程边界验收 |
| **DAC 与转换器指标（1 + 6）** | 原 SAR 电容反馈 DAC；新增分段、温度计、指定非理想、sub-radix DAC，以及 DAC DNL/INL 和 ADC 相干频谱指标 | 明确权重与采样保持规格，或固定 DAC 扫描/ADC 码流 → DAC 模型或 VA 指标仪表 | 独立权重公式与保持检查；从实际 16 级扫描重算端点 DNL/INL；独立谱功率重算 SNDR/SFDR/DC/ENOB，检查无效窗口和 reset |
| **放大与模拟信号处理（8 + 0）** | PGA、AGC、斩波放大、CDS、离散建立模型，以及增益、建立与四样本 RMS 仪表 | 详细状态/采样合同、指定多模块接口，或固定可读 DUT → VA 模型/仪表 | 输出增益、限幅、历史和资格计时；多模块题独立测组件及替换后的真实消费；仪表从实际波形重算 |
| **连续 OTA 动态（0 + 3）** | 新增连续大/小信号状态、真实晶体管 OTA 数据建模、双向阶跃测量 | 连续方程与初态；或固定工况真实数据；或固定行为 OTA 与阶跃协议 → 模型或激励测量模块 | 解析分段压摆与指数建立；真实保留实验误差；实际激励及响应上的增益、采样压摆率、有限窗口建立和超时/饱和报告 |
| **比较器与门限（5 + 0）** | 窗口检测、滞回窗口、翻转电压/表观滞回、过驱动延迟、自适应失调搜索 | 门限/历史合同，或可读比较器、观测和扫描/搜索接口 → 判决模型或测量/搜索模块 | 状态相关门限；实际上下行翻转与延迟；ready/超时、搜索码与完整性，不只检查最终常量 |
| **PLL 与时钟（8 + 1）** | Alexander BBPD、非重叠时钟、正交分频、PFD 修复、频率/占空比/时间协议测量、fine TDC 集成；新增分数 PLL | 采样与事件规格、缺陷 PFD、健康 ADPLL/整数环路与固定 DCO、固定时钟 DUT → 模型、修复、集成控制或仪表 | 历史样本对齐、边沿/死区/取消；实际 DCO 到反馈的因果关系、锁定资格与扰动恢复；分数题验 N/N+1 分频和整数兼容 |
| **滤波、均衡与 RF（2 + 5）** | 原三抽头 FFE、两相 SC 积分；新增 CTLE、可编程连续低通、I/Q 变频、动态包络和扫频测量 | 传递函数/状态与初态、健康低通基线、固定 DUT 和扫频协议 → VA 模型、扩展或激励测量模块 | 独立 ODE/复数频响、换码时状态连续性、混频极性和边带、包络能量历史；从实际扫频输入输出重算增益/相位 |
| **模拟校准与伺服（1 + 2）** | 原前台 RDAC 逐次逼近；新增持续失调校准、共模伺服 | 判决/搜索规格，或健康模拟前端、可用执行器及校准窗口 → 控制器/扩展环路 | 原控制顺序；真实输出残差及慢漂移跟踪；执行器限幅恢复；共模被调节时差模信号仍保留 |
| **电源、复位与响应测试（5 + 2）** | 去抖、复位序列、UVLO 及多模块链修复、真实 POR 测试台；新增真实 LDO 启动和响应驱动 line/load 实验 | 缺陷模块/连接，或真实电路与依赖、固定激励/命令适配器 → 修复源码、只读仪表或完整 VA 测试台 | 故障与正常序列、资格计时和取消；真实电源轨/复位行为；LDO 启动、过冲、有限窗口建立；按实际响应推进阶段并核对命令、指标和超时 |

这次新增主要补上了连续动态、RF 信号处理、真实 LDO 和持续反馈校准。前批已经有多模块系统题；新增 19 题主要仍是单模块和固定被控电路内的工程动作，不能据此声称完整系统/仓库任务已充分覆盖。

## 同源、变体与跨题关联

“共享资产”“同一合同的行为变体”和“功能接近”需要分开记录。题目可独立计分，后续统计同时保留这些关系；不能把同一解法家族直接当作多个独立电路架构。下表补充设计卡的 [同源索引](SOURCE_GROUPS.md)，前批精确关系见 [task-source-map.json](../../experiments/benchmark_v2/task-source-map.json)。

| 关联组 | 关系与新增行为 | 分析边界 |
| --- | --- | --- |
| 024 采样 → 349 多通道 | 健康 024 模块被四通道工程明确复用；增加并行采集、读出顺序与保持 | 071 有限采集属于相近功能；真实采样级数据题另有晶体管来源，不宣称共用原始电路 |
| 038 / 093 / 370 放大与测量 | PGA、在线增益、离散建立模型和增益/建立仪表共享部分 DUT 资产 | 建模与测量是不同动作，但其电路与公式相关性应保留 |
| 斩波 / CDS / SC 积分 | 多模块职责和独立替换验收方法相似；各自体现解调、双采样作差、两相积分 | 共用验收方法不等于共用电路源码；不能只保留空 helper 后在顶层重算 |
| 三道 OTA | 共同研究连续动态、拟合和表征；规格模型与阶跃测量采用行为电路，数据题来自真实 JKU OTA | 元数据的 OTA 路线组不意味着三题都来自同一晶体管 DUT；数据真值不由规格模型生成 |
| 两道 LDO | 共用 Analog Design Bench OTA5 LDO 与器件环境；从固定启动观测扩展到响应驱动的 line/load 实验 | 共享 DUT，新增的是实验控制责任；不重复声称两个独立 LDO 架构 |
| 四道新 DAC | 分段、温度计、非理想权重、sub-radix 均以时钟锁存的加权和为基础；覆盖编码冗余、稀疏/气泡输入、失配及非二进制进位 | 原始来源分别为 v4 014/018/025/243，属于相近合同变体，不能直接标成相同原始源码；静态测量另验真实扫描 |
| ADC 频谱 | 移植历史 `measure-adc-spectrum` 路线，现为 VA 在线指标题 | 相对这 37 题是新增，相对全部历史资产不是新来源；历史 va08 ADC 线性度题不另加入本页 56 题 |
| fine TDC / 分数 PLL / BBPD / PFD | 都涉及相位与闭环时序；新增 fine 路径与 N/N+1 分频的工程要求不同 | 功能相关，不能据名称推定共享同一完整 ADPLL 工程或同一原始电路 |
| 失调校准 / 共模伺服 / RDAC | 新两题使用同一行为前端家族，分别保持有用差模信号并调节失调/共模；旧 RDAC 是前台判决搜索 | 306/369 合并服务持续失调一题，不按两个来源重复计数；还不是晶体管级全工况校准 |
| 滤波与 RF 五题 | 相互关联的连续状态、变频与测量方法；低通、I/Q、包络分别吸收 v4 334、364/400、336 等素材 | 364/400 合成 I/Q 一题；CTLE 另参考开源 Verilog-A 材料。旧离散实现未直接充当连续动态真值 |
| 电源修复 / POR / LDO | 相同电源功能领域，工程动作横跨修复和测试 | VA UVLO 链、真实 Ajacci POR、真实 ADB LDO 是不同来源；不能合称同一电源系统的完整覆盖 |

## 剩余覆盖缺口与后续 review

下列是本批边界和供后续讨论的方向，不是自动批准的新 spec，也不要求现在逐题冻结数值。

| 维度 | 当前边界 | 后续需要判断或补齐的内容 |
| --- | --- | --- |
| 基础变体的区分度 | 四种 DAC 及若干事件/计量题有接近的解法 | 是否保留全部基础题、按家族报告，或把更多建设投入到新增动态行为；先按工程价值判断，不凭文件数估难度 |
| 真实数据建模 | 只有采样级和 OTA 两类，均为固定数据包与有限工况 | 跨负载/偏置/PVT 的覆盖，以及允许主动表征的题型；不能把当前保留实验等同于任意工况泛化 |
| 真实电源流程 | POR 覆盖上电、欠压、恢复；LDO 覆盖启动和 line/load | EN、power-good、休眠/唤醒、掉电次序等尚未完整建设；需要有对应节点与真实电路依据 |
| RF / PLL 非理想效应 | 主要是确定性行为，I/Q 是理想变频；PLL 有实际 DCO 反馈及扰动恢复 | 相位噪声、杂散、镜像/非线性、噪声底等仍欠缺，需先确定电路资产与可独立验证的合同 |
| 转换器动态与统计 | DAC 重点为静态权重与保持，ADC 频谱为短相干码流 | DEM/动态失配、完整 RDAC 扫描、非相干频谱及统计稳定性仍未纳入；历史候选 344/190 的准备材料不算已建题 |
| 系统工程覆盖 | 已有多模块 VA 和固定被控电路任务，完整仓库任务仍少 | 补齐模块职责、连接、跨模块故障和新增功能的工程跨度；保留组件替换/因果检查，避免只凭外部接口把系统写成单公式 |
| 开源复现与运行交付 | 本页两批任务的现有评分证据以 Spectre 为准；真实源电路可运行 ngspice 不等于候选 VA 任务已适配 | 逐题评估固定开源后端或经校准的 VA 替代环境，保留原要求；简化变体另记。新 19 题作者校准不等于完整 Harbor Agent Trial |

## 56 题定位索引

以下只用于定位题面与来源，不逐题重新定义规格。类别简称：**规格、数据、扩展、修复、测试**。`v2` 是前批 37 题，`v3` 是新增 19 题；版本前缀不是难度等级。

<!-- task-inventory:begin -->

| 电路功能 | 批次 / 类别 | 任务与有效题面 | 来源说明 |
| --- | --- | --- | --- |
| 采样与多通道读出 | v2 / 规格 | [边沿采样保持](../tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) | [SOURCE](../tasks/v2-spec-024-clocked-sample-and-hold/SOURCE.md) |
| 采样与多通道读出 | v2 / 规格 | [有限采集采样保持](../tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md) | [SOURCE](../tasks/v2-spec-071-acquisition-limited-sample-and-hold/SOURCE.md) |
| 采样与多通道读出 | v2 / 数据 | [真实采样级动态辨识](../tasks/v2-data-sampling-identification/instruction.md) | [SOURCE](../tasks/v2-data-sampling-identification/SOURCE.md) |
| 采样与多通道读出 | v2 / 扩展 | [四通道采集与读出](../tasks/v2-integrate-349-multichannel-readout/instruction.md) | [SOURCE](../tasks/v2-integrate-349-multichannel-readout/SOURCE.md) |
| ADC 结构与转换控制 | v2 / 规格 | [流水 ADC 级](../tasks/v2-spec-003-pipeline-adc-stage/instruction.md) | [SOURCE](../tasks/v2-spec-003-pipeline-adc-stage/SOURCE.md) |
| ADC 结构与转换控制 | v2 / 规格 | [一级 ΣΔ 调制器](../tasks/v2-spec-055-first-order-sigma-delta-modulator/instruction.md) | [SOURCE](../tasks/v2-spec-055-first-order-sigma-delta-modulator/SOURCE.md) |
| ADC 结构与转换控制 | v2 / 规格 | [SAR 前端逻辑补齐](../tasks/v2-spec-186-sarfend-logic-4b/instruction.md) | [SOURCE](../tasks/v2-spec-186-sarfend-logic-4b/SOURCE.md) |
| DAC 与转换器指标 | v2 / 规格 | [SAR 电容反馈 DAC](../tasks/v2-spec-002-capacitive-sar-feedback-dac/instruction.md) | [SOURCE](../tasks/v2-spec-002-capacitive-sar-feedback-dac/SOURCE.md) |
| DAC 与转换器指标 | v3 / 规格 | [分段 DAC](../tasks/v3-converter-segmented/instruction.md) | [SOURCE](../tasks/v3-converter-segmented/SOURCE.md) |
| DAC 与转换器指标 | v3 / 规格 | [温度计 DAC](../tasks/v3-converter-thermometer/instruction.md) | [SOURCE](../tasks/v3-converter-thermometer/SOURCE.md) |
| DAC 与转换器指标 | v3 / 规格 | [指定非理想权重 DAC](../tasks/v3-converter-nonideal/instruction.md) | [SOURCE](../tasks/v3-converter-nonideal/SOURCE.md) |
| DAC 与转换器指标 | v3 / 规格 | [Sub-radix DAC](../tasks/v3-converter-subradix/instruction.md) | [SOURCE](../tasks/v3-converter-subradix/SOURCE.md) |
| DAC 与转换器指标 | v3 / 测试 | [DAC 静态线性度测量](../tasks/v3-converter-dac-linearity/instruction.md) | [SOURCE](../tasks/v3-converter-dac-linearity/SOURCE.md) |
| DAC 与转换器指标 | v3 / 测试 | [ADC 相干频谱指标](../tasks/v3-converter-adc-spectrum/instruction.md) | [SOURCE](../tasks/v3-converter-adc-spectrum/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 规格 | [可编程增益放大器](../tasks/v2-spec-038-programmable-gain-amplifier/instruction.md) | [SOURCE](../tasks/v2-spec-038-programmable-gain-amplifier/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 规格 | [AGC 电平调节环路](../tasks/v2-spec-082-agc-receiver-leveling-loop/instruction.md) | [SOURCE](../tasks/v2-spec-082-agc-receiver-leveling-loop/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 规格 | [多模块斩波放大器](../tasks/v2-spec-091-chopper-stabilized-differential-amplifier/instruction.md) | [SOURCE](../tasks/v2-spec-091-chopper-stabilized-differential-amplifier/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 规格 | [多模块相关双采样](../tasks/v2-spec-308-correlated-double-sampler-offset-cancel/instruction.md) | [SOURCE](../tasks/v2-spec-308-correlated-double-sampler-offset-cancel/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 规格 | [离散反馈建立模型](../tasks/v2-spec-370-opamp-feedback-settling-monitor/instruction.md) | [SOURCE](../tasks/v2-spec-370-opamp-feedback-settling-monitor/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 测试 | [在线增益仪表](../tasks/v2-test-online-gain/instruction.md) | [SOURCE](../tasks/v2-test-online-gain/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 测试 | [增益与有限窗口建立测量](../tasks/v2-test-gain-settling/instruction.md) | [SOURCE](../tasks/v2-test-gain-settling/SOURCE.md) |
| 放大与模拟信号处理 | v2 / 测试 | [四样本在线 RMS](../tasks/v2-test-sampled-rms/instruction.md) | [SOURCE](../tasks/v2-test-sampled-rms/SOURCE.md) |
| 连续 OTA 动态 | v3 / 规格 | [连续 OTA 规格建模](../tasks/v3-ota-continuous/instruction.md) | [SOURCE](../tasks/v3-ota-continuous/SOURCE.md) |
| 连续 OTA 动态 | v3 / 数据 | [真实 OTA 数据建模](../tasks/v3-ota-data-model/instruction.md) | [SOURCE](../tasks/v3-ota-data-model/SOURCE.md) |
| 连续 OTA 动态 | v3 / 测试 | [OTA 阶跃激励与测量](../tasks/v3-ota-step-measurement/instruction.md) | [SOURCE](../tasks/v3-ota-step-measurement/SOURCE.md) |
| 比较器与门限 | v2 / 规格 | [窗口比较器](../tasks/v2-spec-047-window-comparator-detector/instruction.md) | [SOURCE](../tasks/v2-spec-047-window-comparator-detector/SOURCE.md) |
| 比较器与门限 | v2 / 规格 | [滞回窗口比较器](../tasks/v2-spec-314-hysteretic-window-comparator/instruction.md) | [SOURCE](../tasks/v2-spec-314-hysteretic-window-comparator/SOURCE.md) |
| 比较器与门限 | v2 / 测试 | [翻转电压与表观滞回](../tasks/v2-test-hysteresis/instruction.md) | [SOURCE](../tasks/v2-test-hysteresis/SOURCE.md) |
| 比较器与门限 | v2 / 测试 | [比较器过驱动延迟](../tasks/v2-test-comparator-delay/instruction.md) | [SOURCE](../tasks/v2-test-comparator-delay/SOURCE.md) |
| 比较器与门限 | v2 / 测试 | [自适应失调搜索](../tasks/v2-test-offset-search/instruction.md) | [SOURCE](../tasks/v2-test-offset-search/SOURCE.md) |
| PLL 与时钟 | v2 / 规格 | [Alexander BBPD 内部采样](../tasks/v2-spec-001-bang-bang-phase-detector/instruction.md) | [SOURCE](../tasks/v2-spec-001-bang-bang-phase-detector/SOURCE.md) |
| PLL 与时钟 | v2 / 规格 | [两相非重叠时钟](../tasks/v2-spec-375-nonoverlap-clock-generator/instruction.md) | [SOURCE](../tasks/v2-spec-375-nonoverlap-clock-generator/SOURCE.md) |
| PLL 与时钟 | v2 / 规格 | [正交分频时钟](../tasks/v2-spec-396-quadrature-lo-generator-divided-clock/instruction.md) | [SOURCE](../tasks/v2-spec-396-quadrature-lo-generator-divided-clock/SOURCE.md) |
| PLL 与时钟 | v2 / 扩展 | [ADPLL fine TDC 集成](../tasks/v2-integrate-case0007-adpll-fine-tdc/instruction.md) | [SOURCE](../tasks/v2-integrate-case0007-adpll-fine-tdc/SOURCE.md) |
| PLL 与时钟 | v2 / 修复 | [PFD 复位与事件取消修复](../tasks/v2-repair-pfd-reset/instruction.md) | [SOURCE](../tasks/v2-repair-pfd-reset/SOURCE.md) |
| PLL 与时钟 | v2 / 测试 | [时钟与 DCO 频率测量](../tasks/v2-test-clock-frequency/instruction.md) | [SOURCE](../tasks/v2-test-clock-frequency/SOURCE.md) |
| PLL 与时钟 | v2 / 测试 | [完整周期占空比测量](../tasks/v2-test-duty-cycle/instruction.md) | [SOURCE](../tasks/v2-test-duty-cycle/SOURCE.md) |
| PLL 与时钟 | v2 / 测试 | [时间编码与重装协议测量](../tasks/v2-test-time-protocol/instruction.md) | [SOURCE](../tasks/v2-test-time-protocol/SOURCE.md) |
| PLL 与时钟 | v3 / 扩展 | [分数 PLL 扩展](../tasks/v3-calibration-fractional-pll/instruction.md) | [SOURCE](../tasks/v3-calibration-fractional-pll/SOURCE.md) |
| 滤波、均衡与 RF | v2 / 规格 | [三抽头 FFE](../tasks/v2-spec-353-ffe-transmitter-3tap/instruction.md) | [SOURCE](../tasks/v2-spec-353-ffe-transmitter-3tap/SOURCE.md) |
| 滤波、均衡与 RF | v2 / 规格 | [多模块两相 SC 积分](../tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/instruction.md) | [SOURCE](../tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/SOURCE.md) |
| 滤波、均衡与 RF | v3 / 规格 | [连续 CTLE](../tasks/v3-filter-ctle/instruction.md) | [SOURCE](../tasks/v3-filter-ctle/SOURCE.md) |
| 滤波、均衡与 RF | v3 / 扩展 | [可编程连续低通扩展](../tasks/v3-filter-programmable-lp/instruction.md) | [SOURCE](../tasks/v3-filter-programmable-lp/SOURCE.md) |
| 滤波、均衡与 RF | v3 / 规格 | [I/Q 变频](../tasks/v3-filter-iq-conversion/instruction.md) | [SOURCE](../tasks/v3-filter-iq-conversion/SOURCE.md) |
| 滤波、均衡与 RF | v3 / 规格 | [动态包络](../tasks/v3-filter-envelope/instruction.md) | [SOURCE](../tasks/v3-filter-envelope/SOURCE.md) |
| 滤波、均衡与 RF | v3 / 测试 | [扫频激励与复数频响测量](../tasks/v3-filter-sweep-measurement/instruction.md) | [SOURCE](../tasks/v3-filter-sweep-measurement/SOURCE.md) |
| 模拟校准与伺服 | v2 / 规格 | [前台 RDAC 校准](../tasks/v2-spec-183-foreground-rdac-calibrator/instruction.md) | [SOURCE](../tasks/v2-spec-183-foreground-rdac-calibrator/SOURCE.md) |
| 模拟校准与伺服 | v3 / 扩展 | [持续失调校准](../tasks/v3-calibration-continuous-offset/instruction.md) | [SOURCE](../tasks/v3-calibration-continuous-offset/SOURCE.md) |
| 模拟校准与伺服 | v3 / 扩展 | [共模伺服](../tasks/v3-calibration-common-mode-servo/instruction.md) | [SOURCE](../tasks/v3-calibration-common-mode-servo/SOURCE.md) |
| 电源、复位与响应测试 | v2 / 修复 | [去抖资格修复](../tasks/v2-repair-debounce-latch/instruction.md) | [SOURCE](../tasks/v2-repair-debounce-latch/SOURCE.md) |
| 电源、复位与响应测试 | v2 / 修复 | [复位释放序列修复](../tasks/v2-repair-reset-sequencer/instruction.md) | [SOURCE](../tasks/v2-repair-reset-sequencer/SOURCE.md) |
| 电源、复位与响应测试 | v2 / 修复 | [UVLO 欠压恢复修复](../tasks/v2-repair-uvlo-brownout/instruction.md) | [SOURCE](../tasks/v2-repair-uvlo-brownout/SOURCE.md) |
| 电源、复位与响应测试 | v2 / 修复 | [多模块 UVLO 复位链修复](../tasks/v2-repair-uvlo-reset-chain/instruction.md) | [SOURCE](../tasks/v2-repair-uvlo-reset-chain/SOURCE.md) |
| 电源、复位与响应测试 | v2 / 测试 | [真实 POR 响应测试台](../tasks/v2-test-por-sequence/instruction.md) | [SOURCE](../tasks/v2-test-por-sequence/SOURCE.md) |
| 电源、复位与响应测试 | v3 / 测试 | [真实 LDO 启动测量](../tasks/v3-ldo-startup-measurement/instruction.md) | [SOURCE](../tasks/v3-ldo-startup-measurement/SOURCE.md) |
| 电源、复位与响应测试 | v3 / 测试 | [真实 LDO 响应驱动 line/load 实验](../tasks/v3-ldo-response-experiment/instruction.md) | [SOURCE](../tasks/v3-ldo-response-experiment/SOURCE.md) |

<!-- task-inventory:end -->

## 交付与证据入口

| 批次/路线 | 数量 | 实现与作者校准入口 | 交付 PR |
| --- | ---: | --- | --- |
| 前批五类 | 37 | [v2 总入口](../../experiments/benchmark_v2/README.md)、[交付映射](../../experiments/benchmark_v2/spec-delivery.md)、[当前补充校准](../../experiments/benchmark_v2/author-calibration-private-overlays.md) | [#145](https://github.com/BucketSran/vaEVAS/pull/145) |
| OTA | 3 | [任务与校准](../../experiments/benchmark_next/ota/README.md) | [#154](https://github.com/BucketSran/vaEVAS/pull/154) |
| LDO | 2 | [任务与校准](../../experiments/benchmark_next/ldo/README.md) | [#155](https://github.com/BucketSran/vaEVAS/pull/155) |
| 滤波与 RF | 5 | [任务与校准](../../experiments/benchmark_next/filter/README.md) | [#152](https://github.com/BucketSran/vaEVAS/pull/152) |
| PLL 与模拟校准 | 3 | [任务与校准](../../experiments/benchmark_next/calibration/README.md) | [#156](https://github.com/BucketSran/vaEVAS/pull/156) |
| DAC / ADC | 6 | [任务与校准](../../experiments/benchmark_next/converter/README.md) | [#153](https://github.com/BucketSran/vaEVAS/pull/153) |

两批实现合并不自动改写早期 18 张设计卡的 review 状态，也不把 62 个迁移来源候选全都视为已实施。历史卡、来源和讨论保留在[工作区](README.md)；后续由用户重新组织 review。本页只提供统一事实入口，不新增审批队列。

维护时同步检查：定位索引的 task ID 与前批 `task-source-map.json`、下一批五条路线的实际任务一一对应；按 `task.toml` 的 `engineering_action` 核对分类；功能组和类别总数都应回到 56。新增批次时一起更新计数、关系与缺口，不从历史题卡数量反推任务数。这里不复制有效题面，也不覆盖各任务的 `SOURCE.md`、参考解或 checker。
