# benchmarkv4 审核的电路功能汇总

本页回答：除已讨论的六组，旧库还有哪些电路功能值得迁移。当前按方向讨论，不要求用户逐题审核规格和 checker。以下是选题建议，尚未增加正式题目或批准整组移植。

2026-10-10，用户已同意将下列新增方向纳入迁移候选。后续完成剩余 GLM 审核，按电路功能给出优先级、五类工程动作的对应、复用与重建边界，并解释未优先选取的其他资产。方向登记不等于批准具体任务或整体照搬旧包。

最终审核已完成400/400家族，当前取舍见[优先迁移清单](v4-migration-priorities.md)和[全库索引](v4-migration-index.tsv)。本页保留下述21:17的355份报告阶段快照，不与最终统计混合。

## 审核到哪里了

全库为 400 个家族、1200 个旧任务包，每个家族包含 DUT、Testbench、Bugfix。首轮已尝试全部家族，341 个取得结构合格草稿，59 个调用或报告未完成。20:59 启动四路补跑，保留原失败记录，并将单次输出上限提高至 64000 tokens。

本页功能统计冻结于 **2026-10-10 21:17，北京时间**：355 个家族有结构合格草稿，4 个在运行，41 个仍标记失败。其中失败包括尚待补跑的首轮失败项，不是判定题目不可迁移。完成草稿覆盖 88.75% 的家族、1065 个任务包。

21:24 再次读取实时进度：361 个家族已有草稿、4 个补跑中、35 个尚未成功取得报告，tmux 补跑会话仍在运行。下文功能计数继续保留 21:17 的 355 份报告快照，新增六份未混入该统计。

`accepted_draft` 只说明报告通过身份、结构和引用格式检查，不表示电路、参考解或 checker 正确。本轮读取全量报告作结构汇总，按功能阅读摘要和代表候选的改编意见，并抽查了 091 斩波核心、109 反馈测量连接和 344 DAC 输出级。未逐题复核全部 GLM 结论，也未运行新仿真。

实时进度见本地 `runs/v4-audit-20261010-r3/INDEX.md`。本页使用的 `runs/v4-function-summary-20261010/family-snapshot.json` 保存报告内容及 SHA-256，`runs/v4-function-summary-20261010/status-snapshot.json` 和 `runs/v4-function-summary-20261010/function-groups.json` 可复核数量。这些 `runs/` 材料未随仓库发布。原资产身份为历史来源 `7b5616dc52195ec275ec6d21c71d7763613702cd`，本仓库保存版本为 `c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9`。

## 已有报告覆盖什么

下表把旧元数据的类别归并为十个阅读组，每个家族仅计一次。名称用于定位资产，不代表已证实的架构，也不是新的题型分类或最终题量配额。

| 功能阅读组 | 全库家族数 | 已有审核草稿 |
| --- | ---: | ---: |
| 转换器与采样 | 93 | 83 |
| 比较器与判决 | 24 | 22 |
| 时钟与 PLL | 65 | 57 |
| 电源、基准与保护 | 37 | 34 |
| 校准与修调 | 27 | 22 |
| 放大、滤波与基带调理 | 31 | 28 |
| RF 与 I/Q | 22 | 22 |
| SerDes 数据通路与均衡 | 13 | 12 |
| 测量与测试激励 | 43 | 41 |
| 混合信号基础辅助 | 45 | 34 |
| 合计 | 400 | 355 |

既有六组为采样保持、比较器滞回表征、BBPD/PFD、振荡分频与时钟测量、SAR 转换控制、电源资格与复位去抖。下表补充六组尚未充分覆盖的内容。代表编号仅供追溯，表中每行不等于一道题，也不要求每个来源派生全部工程动作。

## 六组之外值得纳入的方向

| 方向 | 对应电路功能 | 代表旧资产 | 建议迁移内容 |
| --- | --- | --- | --- |
| DAC、流水线与 ΣΔ 转换 | DAC 电平码转换；粗量化后的残差放大与后级量化；积分器、量化器、反馈 DAC 和抽取 | [002 CDAC](../../reference/v4/release/benchmarkv4-r53/tasks/002-capacitive-sar-feedback-dac/)、[003 流水线级](../../reference/v4/release/benchmarkv4-r53/tasks/003-pipeline-adc-stage/)、[343 两级流水线](../../reference/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage/)、[350 ΣΔ 环路](../../reference/v4/release/benchmarkv4-r53/tasks/350-sigma-delta-mini-loop/) | 单模块建模、工程内补残差级或反馈模块、转换流程测试。保留实际信号路径，系统性能需另行校准。 |
| 放大器与精密前端 | 可编程增益、自动增益调节、斩波失调抑制、相关双采样消除公共偏置 | [038 PGA](../../reference/v4/release/benchmarkv4-r53/tasks/038-programmable-gain-amplifier/)、[082 AGC](../../reference/v4/release/benchmarkv4-r53/tasks/082-agc-receiver-leveling-loop/)、[091 斩波放大器](../../reference/v4/release/benchmarkv4-r53/tasks/091-chopper-stabilized-differential-amplifier/)、[308 CDS](../../reference/v4/release/benchmarkv4-r53/tasks/308-correlated-double-sampler-offset-cancel/) | 增益和饱和建模、前端补模块、失调抑制与增益恢复测量。现有斩波模型含常量失调，不据此宣称已有 1/f 噪声测试。 |
| 开关电容滤波与链路均衡 | 两相采样与积分；利用历史符号作加权补偿或判决反馈 | [307 SC 积分器](../../reference/v4/release/benchmarkv4-r53/tasks/307-switched-capacitor-integrator-phase-pair/)、[353 FFE](../../reference/v4/release/benchmarkv4-r53/tasks/353-ffe-transmitter-3tap/)、[331 DFE](../../reference/v4/release/benchmarkv4-r53/tasks/331-dfe-error-proxy-loop/) | 两相积分建模、系数或历史状态修复、扩展均衡能力及响应测试。DFE 旧包的误差代理量不能直接当成真实误码率。 |
| 校准、修调与元件轮换 | 根据比较结果逐步搜索失调或修调码；改变 DAC 单元的使用顺序 | [109 失调环路](../../reference/v4/release/benchmarkv4-r53/tasks/109-comparator-offset-calibration-loop/)、[183 RDAC 校准](../../reference/v4/release/benchmarkv4-r53/tasks/183-foreground-rdac-calibrator/)、[344 DEM](../../reference/v4/release/benchmarkv4-r53/tasks/344-segmented-dac-dem-system/) | 校准控制建模、闭环集成、响应驱动测试。344 可取单元轮换控制，失配抑制性能需要补上受选中单元影响的模拟输出。 |
| RF、I/Q 与包络 | 正交支路混频、LO 极性控制、包络跟踪及不同的上升/恢复速度 | [364 I/Q 上变频](../../reference/v4/release/benchmarkv4-r53/tasks/364-iq-upconversion-mixer-chain/)、[400 下变频](../../reference/v4/release/benchmarkv4-r53/tasks/400-downconversion-mixer-lo-polarity/)、[336 包络检测](../../reference/v4/release/benchmarkv4-r53/tasks/336-rf-envelope-detector-attack-release/) | 混频器或 LO 部件建模、I/Q 连接修复、包络动态表征。先考已建模的频率转换与状态行为，RF 噪声等性能另找依据。 |
| SerDes 数据通路 | PAM4 映射和四电平输出、多门限判决、串并转换与字对齐 | [355 PAM4 发送](../../reference/v4/release/benchmarkv4-r53/tasks/355-pam4-tx-driver/)、[394 PAM4 判决](../../reference/v4/release/benchmarkv4-r53/tasks/394-pam4-slicer-gray-decoder/)、[392 串化](../../reference/v4/release/benchmarkv4-r53/tasks/392-serializer-mux-timing-macro/)、[393 解串](../../reference/v4/release/benchmarkv4-r53/tasks/393-deserializer-demux-alignment-macro/) | 电平与时序建模、工程补模块、数据对齐测试。旧模型缺少完整信道时，不直接出眼图或误码性能题。 |
| 通用测量与响应驱动实验 | 随仿真计算增益、RMS；根据电路当前判决调整下一次激励 | [093 增益估计](../../reference/v4/release/benchmarkv4-r53/tasks/093-gain-estimator/)、[074 RMS](../../reference/v4/release/benchmarkv4-r53/tasks/074-sampled-true-rms-to-dc-converter/)、[109 失调搜索](../../reference/v4/release/benchmarkv4-r53/tasks/109-comparator-offset-calibration-loop/) | 优先改成直接交付 VA 测量或测试模块的任务。RMS 旧包使用短离散窗口，重新出题时按应用定义测量范围；109 可用于闭环实验题。 |
| 电源控制与保护扩展 | 软启动参考生成、PWM 占空比调节、过温时降低控制量 | [341 软启动](../../reference/v4/release/benchmarkv4-r53/tasks/341-buck-soft-start-ramp-controller/)、[372 Buck 控制器](../../reference/v4/release/benchmarkv4-r53/tasks/372-buck-converter-controller-macro/)、[340 热折返](../../reference/v4/release/benchmarkv4-r53/tasks/340-thermal-foldback-power-limiter/) | 补充电源控制建模、状态修复和保护序列测试。372 原工程反馈由预设波形提供，迁移范围先限控制器，不能视为完整 Buck 稳压系统。 |

## 如何取舍

建议优先补齐放大与精密前端、SC 滤波与链路均衡、校准与响应驱动实验。这几组能扩大电路覆盖，也便于解释 VA 模块如何参与实际信号处理和在线实验。DAC、流水线与 ΣΔ 则能把已有 ADC 方向从 SAR 控制扩展到其他转换结构。RF/IQ 和 PAM4 进入候选池，后续请相应领域同行一起判断行为抽象。电源控制作为原电源组的扩展，不另设任务类别。

109 的源码和网表已静态确认：测量模块读取比较器判决，调整差分激励并减小搜索步长，支持比较器将激励变成下一次判决。这可用于设计响应驱动的测试任务。对仅由 PWL 提供判决的旧校准包，先记录为控制器素材，补齐实际被测模块后再称为闭环实验。091 静态确认了调制、失调注入和同步解调路径；344 输出级只读取粗细码，不读取轮换后的单元选择，因此旧包不足以证明 DEM 的模拟性能收益。

一些简单门逻辑、编码器、计数器和状态控制可以作为基础题或工程配套模块。暂不按数量批量迁入，以免大量相近题盖过真正不同的电路功能。题名包含 CTLE、自举、失配整形或稳压环路，也不自动获得相应架构身份，应保留实际成立的部分或另找资产重建。

五类工程动作保持不变。旧 DUT 中本来就在执行测量的 VA 模块，也可以成为“电路测试与表征”的来源。最终按 Agent 的实际工作分类，不沿用旧包标签。数据建模仍优先建设真实采样级数据，旧行为模型生成的数据不冒充真实电路数据。

本页只做宏观筛选；具体规格、严格 checker、后端校准和模型试做由后续出题阶段完成。GLM 的 `prefer`、`revise` 等标签保留为建议，不用作正式接纳数量。
