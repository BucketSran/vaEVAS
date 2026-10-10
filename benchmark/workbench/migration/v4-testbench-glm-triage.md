# GLM 首轮意见下的 Testbench 移植候选

2026-10-10。本页按最新讨论复核旧 v4 的测试与表征素材：VA 随电路运行完成测量、检查和报告，本身就有工程价值；不因 Python 能离线得到同样结论而降级。响应驱动的实验同样保留，但不要求每题都有。这里给出移植讨论顺序，尚未批准新题卡或形成可评分任务。

## 审核进度与证据范围

本次记录的运行快照为 **2026-10-10 20:37:00，Asia/Shanghai**。总计400家族、1200任务包，每家族一次 GLM 5.3 调用，包含 DUT、Testbench、Bugfix 三形态。

| 状态 | 家族数 | 含义 |
| --- | ---: | --- |
| `accepted_draft` | 330 | 报告通过结构、身份、引用等校验，内容仍需复核 |
| `failed` | 59 | 本次调用或报告校验失败，不能解释为题目不合格 |
| `running` | 8 | 正在生成审核意见 |
| `pending` | 3 | 尚未派发 |

59次失败分为42次429限流、9次JSON解析失败、7次身份/引用/字段校验失败、1次连接中断。失败原响应保留。全量首轮及失败补审尚未完成；限流补审需要降低请求并发，结构错误需先读原响应，不能简单改标签当成成功。

330份有效草稿中的 Testbench 建议为20个 `prefer`、305个 `revise`、3个 `defer`、2个 `exclude`。这是模型意见分布，不是主代理接受数量或题目质量统计。刚才关于仿真内测量价值的修正用于本次统筹复核，未追溯改写 GLM 已发提示词。

本轮程序化核对了400份 Testbench 题面，全部指定交付 `testbench.scs`。重点阅读20个候选的 GLM 摘要、Testbench 参考评价和高影响发现，再核对13个家族的相关题面、参考源码或负例差异：005、046、060、095、101、111、180、195、249、296、361、362、375。不是全400家族的人工复审。所有结论均为静态分析，没有新增编译、仿真、checker 校准或 Agent 成绩。

本地证据入口：`runs/v4-testbench-synthesis-20261010/status-snapshot.json`、`runs/v4-testbench-synthesis-20261010/static-examples.json`、`runs/v4-audit-20261010-r3/INDEX.md`。这些 `runs/` 材料未发布，索引会继续变化，统计以本页冻结快照为准。原始资产身份沿用[迁移主页](README.md#先区分三批材料)。

## 先移植四个有明确测量或验证职责的方向

优先表示先细化规格和建设 checker，不表示原参考可以直接充当正确答案。除现成 VA 仪表外，旧 `.scs` 主要提供固定 DUT、激励线索和故障素材，新候选交付物需改为 VA 测量、检查或激励模块。允许报告数值与违规，但终评独立重算，不接受候选自报 PASS 作为唯一依据。

| 优先来源 | GLM 对旧 TB 的意见 | 拟保留的工程工作 | 首先要补清的事项 |
| --- | --- | --- | --- |
| family111 / v4-611：滞回行程点表征 | revise | 给定只读比较器，写 VA 模块测量上、下翻转输入值及宽度，报告有效性；已有 VA 仪表参考和独立比较器支持文件 | 测量的是输出穿越判定门限时的输入值，不能直接等同于器件静态阈值；重复扫描的更新规则、缺单方向事件和本地地参考 |
| family362 / v4-862：DCO 与分频监测 | prefer | 从实际时钟边沿测频，检查控制字与频率关系、分频计数、停振和重新启动；报告测量与违规 | 换码时的有效测量窗口、首个半周期、复位释放行为；每N个DCO上升沿翻转一次输出意味着稳态完整周期为2N个DCO周期 |
| family249 / v4-749：PFD 脉冲与复位检查 | revise | 检查 ref/fb 先后、UP/DOWN 脉宽、双方到达后的互复位，以及单边挂起时外部复位清除 | 同刻边沿、阈值等号、重复输入沿和待执行复位；与 case-0008 保留同源关系，不重复当独立电路 |
| family046 / v4-546：UVLO 迟滞与掉电恢复 | revise | VA 测试模块检查上门限置位、下门限清除、带内记忆及恢复过程，并直接报告结果 | 原件是时钟采样型 UVLO，不能改讲连续模拟比较器；明确同步/异步复位，加入带内从高、低两种历史进入的场景 |

这四个方向不要求第一版都自适应地产生激励。固定激励加完整 VA 测量/检查已经成立；是否让测试模块主动推进实验，应由该电路的测试需求决定。

### 111 最贴近随电路得到结论的例子

[旧 DUT 题面](../../reference/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/public/instruction.md)明确要求交付电压域测量模块，比较器是只读支持件。因此其 DUT 形态本身已接近新“电路测试与表征”，不必先把 v4-611 的“给测量器写网表”原样迁过来。

[仪表参考](../../reference/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/evaluator/solution/hysteresis_trip_characterizer.va)第23–36行在比较器输出穿越电源中点时捕获输入并更新宽度与 valid；[支持比较器](../../reference/v4/release/benchmarkv4-r53/tasks/111-hysteresis-trip-characterizer/evaluator/solution/support/support_hysteretic_comparator.va)包含 `td` 和输出平滑。由此可推断，有限斜率输入下，观测到的翻转输入值会受到输出延时影响。checker 应按题面定义的观测事件求值，不能直接拿 `vhys` 参数作为任何扫描下的测量真值。

旧输出是电压编码值。改成或补充 `$strobe` 报告可以讨论，但格式变化本身不新增一道题；核心仍是正确取样、历史更新、有效性和异常报告。

### 362 应测边沿，不能直接转述 DUT 的 metric

[参考源码](../../reference/v4/release/benchmarkv4-r53/tasks/362-frequency-word-dco-divider-monitor/evaluator/solution/frequency_word_dco.va)第49–58、78–88行从控制字计算目标频率并生成 `freq_metric`；第70–76行单独更新时钟和分频。测试模块应从 `dco_clk` 与 `div_clk` 边沿独立测量，再核对目标和 metric。只读取 metric 会漏掉分频计数错误，也可能漏掉实际时钟与目标不符。

默认 `divide_ratio=4` 时，分频输出每4个 DCO 上升沿翻转一次，上升到下一上升需要8个 DCO 周期。这由[公开合同](../../reference/v4/release/benchmarkv4-r53/tasks/362-frequency-word-dco-divider-monitor/public/instruction.md)第38行和代码一致推出；不能仅凭参数名称认定是四分频。保存的静态计数例子不是仿真证据。

### 249 与 046 的依据

[PFD 参考](../../reference/v4/release/benchmarkv4-r53/tasks/249-pfd-active-low-reset/evaluator/solution/pfd_active_low_reset.va)第18–44行区分外部复位、单边置位和延迟互复位，可直接形成事件时序检查。已检查的负例包含忽略复位、改变互复位等待、交换边沿作用等，但五负例全部检出的旧声明不代替新校准。

[UVLO 参考](../../reference/v4/release/benchmarkv4-r53/tasks/046-uvlo-brownout-detector/evaluator/solution/uvlo_brownout_detector.va)第16–26行只在时钟上升沿采样，使用0.65V置位、0.55V清除和状态保持。公开文字中的“on reset”应补清时序，避免候选和 checker 对异步清除产生不同理解。该题适合作为电源状态检查基础，不能用来代表完整 PMIC 启动系统。

## 同时保留的基础题

| 来源 | 建议 | 已核实的边界 |
| --- | --- | --- |
| family005 / v4-505：去抖资格计时 | 保留短脉冲、持续有效、途中复位和取消待执行事件的 VA 检查题 | [参考](../../reference/v4/release/benchmarkv4-r53/tasks/005-debounce-latch/evaluator/solution/debounce_latch.va)第8–13行有可追踪事件状态；与 case-0014 同源，短实现不影响基础价值 |
| family060 / v4-560：占空比仪表 | 优先复用原 DUT 测量模块任务，补公开报告接口与边界；不要机械地再出“测量一个测量器”的题 | [参考](../../reference/v4/release/benchmarkv4-r53/tasks/060-duty-cycle-meter-8b/evaluator/solution/duty_cycle_meter_8b.va)第15–17行无“见过第一次上升沿”状态，初始高、先下降后上升时会提前进入有效分支；量化舍入另需核对 |

占空比的初始化问题是本次主代理补查：初始 `rise_t=0`，5ns下降置 `have_fall=1`，10ns的第一次实际上升便会设置 valid，尚未观察到合同所说的两个上升沿完整周期。当前只做代码路径推演，未运行仿真。GLM 的 revise 标签没有充分体现这个具体问题，所以不会把原参考直接作为新题 gold。

## 保留方向，但先修资产或补电路依据

| 来源 | 值得保留的部分 | 暂不作为最先移植的原因 |
| --- | --- | --- |
| family375 / v4-875：两相非重叠时钟 | 两相互斥、死区时长、复位/使能以及短请求检查 | [实现](../../reference/v4/release/benchmarkv4-r53/tasks/375-nonoverlap-clock-generator/evaluator/solution/nonoverlap_clock_generator.va)第59–84行按全局 tick 递减计时并直接输出，`tr` 未使用；死区不是自动等于 `dead_ticks*tick`，需先确定健康 DUT 合同 |
| family296 / v4-796：动态供电电平驱动 | 移动 VDD/VSS 下的门限、电平跟踪和欠压钳位检查 | [实现](../../reference/v4/release/benchmarkv4-r53/tasks/296-dynamic-supply-level-driver/evaluator/solution/dynamic_supply_level_driver.va)第21–32行说明本地轨用途；GLM 提醒原固定激励不能区分某绝对门限负例，本轮未逐点复算该全程等价断言，保留为待核实覆盖缺口 |
| family180 / v4-680：采样保持与下垂 | 保持误差、下垂、使能/复位检查 | [实现](../../reference/v4/release/benchmarkv4-r53/tasks/180-track-hold-with-droop-and-aperture/evaluator/solution/track_hold_aperture.va)第31–45行是离散步进下垂，第56–59行 aperture_metric 是输入与上次保持值之差的比例；不能把它当成已校准孔径误差或真实泄漏模型 |
| family361 / v4-861：DLL 锁定与扰动 | 实际延迟线、判相器、调码和锁定检测形成反馈，可研究系统测试 | [顶层](../../reference/v4/release/benchmarkv4-r53/tasks/361-dll-delay-line-lock/evaluator/solution/dll_top.va)第20–34行存在反馈连接；需先验证健康闭环、输出平滑与采样时序，再设计锁定/失锁实验 |

GLM 对361提出“固定92ns激励无法入锁”的具体算术结论，本次**不直接采纳**。其以140ps输入偏移除以5ps得到目标码28，但[延迟线](../../reference/v4/release/benchmarkv4-r53/tasks/361-dll-delay-line-lock/evaluator/solution/delay_line.va)第93行还含100ps输出平滑，判相器检测的是输出阈值穿越，不能只算待执行事件时间。这个遗漏足以要求重算，尚不能反向宣称电路会正确锁定。原始 GLM 报告保留，不静默更改它的结论。

## 这些旧包不宜直接搬运

- **family095 / v4-595，LDO负载阶跃恢复。** 工程主题保留，但本次对照参考与负例发现，neg_002–005 都叠加了四路输出乘0.42。它们还可能有各自错误，却能被同一种粗幅度检查同时区分，不能把“五个负例”解释为五类独立测试能力。[负例目录](../../reference/v4/release/benchmarkv4-r53/tasks/595-ldo-load-step-recovery-testbench/evaluator/mutation_bundles/)。现有真实 LDO 来源继续沿用 case-0002，旧包仅作方法或故障线索。
- **family101 / v4-601，名称为建立时间测量。** [参考](../../reference/v4/release/benchmarkv4-r53/tasks/101-settling-time-measurement/evaluator/solution/settling_time_measurement_tb.va)只产生一阶离散响应，并在固定时间和幅值条件下置 done，没有测量建立时间数值。neg_002–005 去掉注释后的逻辑相同，均为输出乘0.42。保留真正建立时间测量的需求，不能原样继承这个包的题意与负例质量。
- **family195 / v4-695，无输入时序发生器。** [题面](../../reference/v4/release/benchmarkv4-r53/tasks/695-clock-sample-1600n-sequencer-testbench/public/instruction.md)只有输出端口，却要求自行设计激励。GLM 排除旧“写激励网表”形态有依据；若改成观测脉宽、周期和相位关系的 VA 模块仍可能成立，需补真实 ADC 时序用途，不据此排除所有被动测量题。

此外，本轮未完整复核的其余候选仍是未决，不能从未入短名单推断不值得保留。GLM 对复杂架构、真实故障来源、后端兼容性及 checker 强度的判断继续保留人工复核要求。

## 后续111复核

细读原比较器、测量模块与激励后，已整理 [case-0016讨论稿](../cases/testing-characterization/comparators/case-0016-hysteresis-characterizer/README.md)。它区分静态迟滞与输出翻转时观察到的宽度，保留最近双向捕获，并提出最终报告与独立事件checker。GLM所称的绝对零电平问题是误读，原贡献以VSS为参考；具体更正和源文件身份见[来源卡](../sources/v4-hysteresis-characterizer.md)。此处不回写上面的历史运行快照，也不将草案视为已批准或校准。

## 后续按功能归并

2026-10-10，用户在111示例后明确共同审核只需宏观判断迁移内容及电路功能。后续按[迁移总览](README.md#当前先按电路功能看迁移方向)汇总测量、时钟、电源与控制等内容，不再把逐题细化作为用户必须完成的review流程。111的细节保留为例子，362、249、046等先在总览中说明用途和迁移方向；375与361的技术缺口留待实施核验。

新题统一需要公开测量定义、正常/异常结果的语义和可独立核对的输出；量化容差、报告时机和固定后端待实际校准。禁止重写DUT、检查实验覆盖和防止空结果通过等责任按具体题型设定。不沿用旧五负例配额、旧语言子集或统一 Spectre 验收要求，也不为五类或每个家族凑题。
