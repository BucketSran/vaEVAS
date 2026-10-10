# v4 DUT 按规格建模迁移筛选

2026-10-10；当前仓库 `c81b8c7c`；历史来源固定为 `7b5616dc52195ec275ec6d21c71d7763613702cd`。建议优先讨论 **v4-024、v4-001、v4-186**，分别覆盖采样记忆、边沿鉴相和 SAR 握手。这里判断材料适合改编，不声称难度、后端执行或 checker 已通过。本轮没有仿真、认证复用或源码搬运。

## 元数据普查

逐目录读取 `task_record.json` 的 form，核验 1200 项中 DUT 为 400，另有 testbench/bugfix 各 400；与 [TASK_INDEX](../../reference/v4/release/benchmarkv4-r53/TASK_INDEX.json) 和 [MANIFEST](../../reference/v4/release/benchmarkv4-r53/MANIFEST.json)一致。按 `public_contract.json.identity.category` 得到 59 个旧标签，完整计数如下。这些是电路标签，不能替代当前五类工程动作。

| 旧 category | DUT 数 | 旧 category | DUT 数 |
| --- | ---: | --- | ---: |
| `data_converter` | 70 | `timing` | 3 |
| `mixed_signal` | 29 | `clocking` | 2 |
| `bias_reference_power_management` | 26 | `data_converter_models` | 2 |
| `clock_timing` | 22 | `filter_integrator_macromodels` | 2 |
| `pll_clock_timing` | 20 | `power_management_systems` | 2 |
| `rf_afe_behavioral_macromodels` | 18 | `sampling_memory` | 2 |
| `calibration_control` | 17 | `serdes_io_systems` | 2 |
| `testbench_utility_modules` | 15 | `timing_primitive` | 2 |
| `baseband_signal_conditioning` | 13 | `baseband_signal_conditioning_systems` | 1 |
| `pll_clock_timing_systems` | 13 | `calibration_dem_control` | 1 |
| `comparator` | 10 | `clock_timing_systems` | 1 |
| `measurement_instrumentation_flows` | 10 | `comparator_decision_circuits` | 1 |
| `sampling_analog_memory` | 10 | `feedback_circuit_systems` | 1 |
| `comparator_decision` | 9 | `feedback_circuits` | 1 |
| `data_converter_systems` | 8 | `filter_amp` | 1 |
| `digital_logic` | 8 | `measurement` | 1 |
| `measurement_control` | 7 | `operational_amplifier_macromodels` | 1 |
| `calibration` | 6 | `oscillator_timing_systems` | 1 |
| `serdes_equalization_systems` | 6 | `power_management_supervisors` | 1 |
| `stimulus_source_generators` | 6 | `precision_amplifiers_and_offset_mitigation` | 1 |
| `analog_primitive` | 5 | `receiver_frontend_systems` | 1 |
| `signal_conditioning_and_measurement` | 5 | `reset_power_control_systems` | 1 |
| `amplifier_macromodels` | 4 | `rf_front_end_mixer_macromodels` | 1 |
| `comparator_decision_systems` | 4 | `rf_mixer_systems` | 1 |
| `measurement_systems` | 4 | `rf_power_macromodels` | 1 |
| `reset_power_control` | 4 | `sampling_readout_systems` | 1 |
| `serdes_io` | 4 | `serdes_datapath_macromodels` | 1 |
| `calibration_control_systems` | 3 | `serdes_timing_systems` | 1 |
| `logic` | 3 | `signal_processing` | 1 |
| `power_control` | 3 | `` |  |

对全部 `evaluator/solution/**/*.va` 去注释后扫描 `module 名(`，实际为 529 个声明：349 题一个，8 题两个，18 题三个，15 题四个，10 题五个。它是源码声明计数，不是 elaboration 结果。不能把全部 400 称为单模块。与机器合同列出的 module 名比较，102、109、111、170、301、302 六题还有未列入 artifact module 清单的辅助定义，需另查 support 边界。400 个 instruction 字节内容均不同；221 题参数描述至少一次使用 `overrides 参数名` 模板。后者提示仍有模板式参数说明，需要逐题确认是否充分，不能据此断定 221 题重复或由机器生成。本轮未逐题审计这 400 份文本。

## 实读八个候选

下表链接为 r53 题目录。每题全文读了 `public/instruction.md`、`public_contract.json`、`evaluator/family_spec.json`、`evaluator/solution/*.va`、`public/visible_test.scs`、`evaluator/checker_profile.json`；另读 score/canonical profile 和 score policy。八题参考各为一个实际 module。

| 候选与原资产 | 已有事实、沿用与删改建议 | 公开输入、交付与独立验收建议 | 同行需要确认 |
| --- | --- | --- | --- |
| [024 clocked sample and hold](../../reference/v4/release/benchmarkv4-r53/tasks/024-clocked-sample-and-hold)，`sample_hold.va` | 上升沿保存 `V(IN,VSS)`，间隔保持；可沿用接口、vth/tedge 和非零 VSS 公开 deck。新文本明确初态为 VSS、时钟门限相对 VSS；VDD 未参与参考计算。 | 给端口/参数表、局部轨定义、示例 deck，交付同名 VA。checker 从输入 crossing 插值得采样值，逐区间检验保持、错边沿及高相透明。 | 这是理想边沿采样保持，名称不应暗示跟踪窗；是否要求限幅、动态电源轨及输出负载。 |
| [001 BBPD](../../reference/v4/release/benchmarkv4-r53/tasks/001-bang-bang-phase-detector)，`bbpd_ref.va` | 数据双边沿按 clk/retimed 四种关系决定 UP/DOWN，下一时钟双边沿清除。沿用真值表、互斥与脉冲语义。 | 给真值表、边沿表、四参数和公开 PWL 例子；交付一个 VA。checker 按输入事件独立重建脉冲区间，检验方向、清除与电平，变换事件间距。 | 与常见 BBPD 拓扑的关系；阈值相等、数据和时钟同时过门限的优先级。 |
| [186 SAR front-end](../../reference/v4/release/benchmarkv4-r53/tasks/186-sarfend-logic-4b)，`sarfend_logic_4b.va` | 四次比较依次更新 dp4 至 dp1；clks 上升沿先发布旧字再初始化。未决 P/M 的 0/0、1/1 是文本明确的状态，不能强制全程互补。参考采样 dtest，但 live 读取 test。 | 给上一字映射、状态/握手表、test 捕获时刻与合法比较器脉冲；交付一个 VA。checker 使用独立状态表验全部字与试探状态，并检查四次后停止请求；改变 test/dtest 与复位位置。 | 两比较器输出同高、毛刺/重叠如何处理；test 是否也应在 clks 捕获；首字与中断转换如何定义。 |
| [017 strongarm latch](../../reference/v4/release/benchmarkv4-r53/tasks/017-strongarm-style-latch-comparator)，`cmp_strongarm.va` | 题面本地轨门限，参考却用绝对 VDD/CLK，输出也对地，VSS 被忽略；公开 deck 的 VSS=0 掩盖差异。保留锁存/下降沿复位/offset，先重写电源语义。 | 公开采样决策表和轨定义；交付一个 VA。独立 crossing/sign checker，增加非零 VSS、高相输入反转及 offset。LP/LM 是否公开另定。 | 同行确认双低预充及零差分双低抽象；不把理想事件模型称为再生速度或亚稳态模型。 |
| [071 acquisition-limited S/H](../../reference/v4/release/benchmarkv4-r53/tasks/071-acquisition-limited-sample-and-hold)，`acquisition_limited_sample_hold.va` | alpha/tick 离散逼近；参考仅 timer 或 sample 上升时识别 reset，初始 sample 高也不开窗。已有复位/开窗文本不够精确。 | 给更新周期相位、初态及复位优先表；交付一个 VA。独立递推与窗外保持检查，特别测 tick 之间 reset 和初始高电平。删除 metric 需另定公开状态观测。 | alpha 与物理带宽的关系；若要求真实建立动态，应由同行选连续模型合同。 |
| [191 6-bit SAR DAS](../../reference/v4/release/benchmarkv4-r53/tasks/191-sar-das-logic-6b)，`sar_das_logic_6b.va` | 双时钟清零/预置；首决策 index7 对已预置 d6/db6 仅置高，不能区分该对的首决策。参数机器合同单位空、范围只写 finite。 | 给六步开关表、脉冲和合法时序，补时间单位/合法范围；独立状态表验 bit retention 与 co/cob。交付一个 VA。 | 该首决策是否真是 DAS 工程意图、转换完成后多余时钟如何处理；暂不优先。 |
| [192 self-timed SAR](../../reference/v4/release/benchmarkv4-r53/tasks/192-sar-logic-4b-self-timed)，`sar_logic_4b_self_timed.va` | 四决策与动态 timer 握手；reference 在 reset 才刷新轨值，末步后保持 step1，额外脉冲仍可改写 LSB。 | 给合法一热比较器脉冲、终止和挂起延迟处理，交付一个 VA；独立事件队列检查延迟、位序、复位中断和完成后静止。 | 异步 reset 应否取消全部请求；原文本没有足够的非法/同时事件合同。 |
| [375 nonoverlap clock](../../reference/v4/release/benchmarkv4-r53/tasks/375-nonoverlap-clock-generator)，`nonoverlap_clock_generator.va` | 参考全局 timer 递减 dead_ticks；等待时间依请求相位变化，且声明 tr 却直接赋电压，与题面平滑要求不符。 | 保留 phi1/phi2、复位/使能工程行为；删改 deadtime_metric/valid 要明确。公开死区区间和短脉冲规则，独立测两相不重叠及死区，交付一个 VA。 | 同行决定严格持续时间或离散计数、短请求取消/覆盖，以及 disable 后重新启用语义。 |

## 规格与来源边界

旧 instruction 给人读的目标，machine contract 给接口/属性，visible deck 给一个可见场景；三者没有足够规则解决上述冲突。新题应以重新写定的公开规格为规范，机器合同由它生成，示例 deck 只说明用法。删掉旧语言子集限制，以电压域行为和交付范围定题；正确 VA 受后端限制属于环境缺陷。满足独立验收条件的 ngspice 可独立评分。

八题的 visible deck 与 trusted replay 逐字相同，checker profile 实存，但只是私有 checker ID/信号声明。旧 runner 依赖 `runners/checkers/v4/registry.py`、`task_XXX.py` 与 `runners/simulate_evas.py`，本轮未在当前迁入目录及对应仓库路径找到这些实现，尚未完成旧 checker 的定位和复用，不能声称已有可运行独立 checker。依据见 [validate_v4_checker_batch.py](../../reference/v4/scripts/validate_v4_checker_batch.py) 与 [feedback_oracle.py](../../reference/v4/runners/feedback_oracle.py)。后续须重建独立判据，不能把参考波形作为唯一答案。

来源追溯到各题的 `benchmark/reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/<同名目录>/evaluator/task_record.json`。001/017/024 分别指旧 slug 001/018/026；v1 的 [001 SOURCE_TASK](../../reference/v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_bang_bang_phase_detector/forms/dut/SOURCE_TASK.md)、[017 SOURCE_TASK](../../reference/v1/tasks/CT02_comparator_and_decision_circuits/vbr1_l1_strongarm_style_latch_comparator/forms/dut/SOURCE_TASK.md)、[024 SOURCE_TASK](../../reference/v1/tasks/CT03_sampling_and_analog_memory/vbr1_l1_clocked_sample_and_hold/forms/dut/SOURCE_TASK.md)只提供旧题路径，001 是 `tasks/spec-to-va/voltage/pll-clock/bbpd`，017 是 `tasks/spec-to-va/voltage/comparator/vbm1_strongarm_comparator_behavior_dut`，024 是 `sample_hold_smoke` E2E 提升的 DUT；没有据这些记录认定对应真实晶体管电路。071 指旧 slug071；375 指934，source_task_id为空，尚无原工程线索。

186/191/192 对应 v3 导入222/229/230。[SOURCES.md](../../reference/veriloga/SOURCES.md#尚待定位的历史来源)分别列 `guoxue25/SARFEND_LOGIC_FT_4B.va`、`zhangz/SAR_logic_DAS_va.va`、`zhangz/L3_logic_4b.va` 为未定位原始资料。r53 参考可读，原始工程源码仍未知。现有 [va02 来源](../../tasks/va02-sar-handshake/SOURCE.md)明确是 [lab 七位 SAR](../../reference/veriloga/lab/calibration_control/sar_logic_7bit.va)、v3 导入243；与186不能确认共源，只能登记相近行为。实读了 va02 题面/参考和 lab 四位 SAR 源码；后者对应234，也不能仅凭四位握手认定是192原材料。

另抽查 [310 bootstrap metric](../../reference/v4/release/benchmarkv4-r53/tasks/310-bootstrapped-sampler-charge-metric)题面与参考，`boot_metric=clip(2*abs(vhold-vcm))`，droop 按固定 tick 加减，题面未公开该 tick。这是指标算术包装，尚无自举开关的物理合同，不推荐按标题直接迁入工程建模题。没有据这一个例子给全部400分类。本轮实读范围为上述八题加310抽查、三个 v1 SOURCE_TASK、provenance记录、来源索引和 va02/lab 对照；所有原始资产保持只读。公开解题包建议只放新规格、接口/参数表、示例连接/激励、运行说明；参考源码和终评checker保留内部，不复制进新case。
