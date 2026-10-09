# 诊断与修复材料调查

调查日期 2026-10-08。仓库基线 `b86845e1ef80498a8eed708a56bed993f7a7f17c`；原始核查文件位于本机 `runs/benchmark-material-survey-20261008/repair-raw/`。本专题没有运行仿真、校准或修改任务。本报告是候选材料筛选，不能作为正式收题、评分或支持声明。

范围遵循当前已定五类任务中的诊断与修复。候选交付物是电压域 VA；关注电路功能、状态、事件、复位、接口和规定性能。独立 checker 定义正确性，Spectre 作最终验收。本报告不纳入仿真加速、收敛或异常耗时。允许修复单模块整体重写；系统题先做多 VA 模块，再考虑 VA 接真实器件网表。指定模块、连接、设计参数可以修改，验收条件固定。

## 本地材料身份与分发边界

下列前三项来自旧 v4 r53 单模块 bugfix 包，已逐项读取规格、starter、reference、checker profile、评分网表、derivation manifest 与 mutation catalog。[资料入口](../reference/README.md)记载其迁入来源为 Arcadia-1/behavioral-veriloga-eval，固定快照 `7b5616dc52195ec275ec6d21c71d7763613702cd`。该目录仅供内部研究，不是本项目当前 Harbor 正式发布集。没有查到可据以外发整套派生任务的授权；三个模型是否另受第三方来源权利约束仍需逐项追溯。本次没有复制 Cadence 安装库代码或发往外部。

v4 `checker_profile.json` 明示 `access=private_checker_backend`、`checker_source_public=false`。本地材料提供 checker 名称、信号合同、认证记录和网表，但本次未定位三个对应的实际 checker 实现，因此只能评估合同和建议新独立 checker，不能声称旧 checker 已审计。三个 r53 `task_record.json` 都将公开 visible deck 与 trusted replay 绑定为相同字节，改题需要新建固定验收版本，不能将旧公开刺激直接当成隐藏泛化测试。[示例 task record](../reference/v4/release/benchmarkv4-r53/tasks/1042-sample-and-hold-with-droop-leakage-bugfix/task_record.json)。

### 1. v4-1042：采样保持与周期下垂

资产目录 [1042-sample-and-hold-with-droop-leakage-bugfix](../reference/v4/release/benchmarkv4-r53/tasks/1042-sample-and-hold-with-droop-leakage-bugfix/public/instruction.md)。精确起始路径为该任务 `public/buggy_bundle/leaky_hold.va`，参考为 `evaluator/solution/leaky_hold.va`，评分刺激为 `evaluator/score_tb.scs`，checker profile 为 `evaluator/checker_profile.json`。来源故障清单为 [042 mutation catalog](../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/042-sample-and-hold-with-droop-leakage/evaluator/mutation_catalog.json)，派生 manifest 的 bugfix seed 是 `neg_001`。

事实：接口 `leaky_hold(sample,rst,vin,vout)`。sample 上升交点采集当前 vin；每 leak_period 将 held 乘 decay；reset 在采样或泄漏更新事件时清零；transition 平滑输出。starter 将采样更新写成 held=0，且 decay 默认 0.900，与合同/参考的 0.985 不同。它是人工 mutation 派生的具体故障素材，本次未找到真实用户工程 bug 记录。旧 [certification](../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/042-sample-and-hold-with-droop-leakage/evaluator/certification.json) 标明 `rust_evas2_only`，记录 EVAS2 0.8.3、五个负例 killed；这不是当前 Spectre 终验。

工程用途是离散采样保持和读出链路的泄漏估计，非真实开关电路下垂表征。它的乘性 droop 合同可用明确递推式验收：从外部 sample 交点取得 vin，以已规定的 timer 网格计算泄漏次数，独立算 held。避开或显式定义 sample 与泄漏完全同时的优先级。检查不同 leak_period、decay、正负输入、初态、复位脉冲及 sample 之间 vin 改变仍保持的条件，不使用 reference 波形作答案。

建议作为容易但有工程意义的基础题，或作为多通道采样读出系统中的一个可改模块。整体重写风险高：公开规格已经足够重新写出短模型，而且 starter 的采样置零十分明显。若目标是诊断能力，提供多个模块、局部已知正确行为及“新采样正确但长保持出错”的故障现象更合适。不能用代码改动行数限制替代工程任务。reset 是否应真正异步清零与当前合同不同，若改题须先更新公开合同，不能隐藏新增要求。

### 2. v4-1249：PFD 的外部低有效复位

资产 [1249 instruction](../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/public/instruction.md)。精确起始文件为任务 `public/buggy_bundle/pfd_active_low_reset.va`，参考为 `evaluator/solution/pfd_active_low_reset.va`，刺激为 `evaluator/score_tb.scs`；来源 [249 mutation catalog](../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/249-pfd-active-low-reset/evaluator/mutation_catalog.json) 与 [derivation manifest](../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/249-pfd-active-low-reset/evaluator/derivation_manifest.json)。

事实：ref/fb 上升沿分别置 UP/DOWN，两边均到达后延迟 reset_delay 清零；rstb 低需立即清掉任意单边挂起状态、抑制新边沿并取消挂起互复位。starter 完全不使用 rstb，且缺少公开参数 tr，仅硬写 10p。参考加入 reset 的下降 crossing、边沿使能判断和低电平清零。故障类型为人工注入，可映射 PLL 启动、停钟及复位恢复场景。

来源存在未决项：derivation manifest 宣称 bugfix seed `neg_005_metric_scale_low`，catalog 将它解释为输出增益错误；字节比对确认当前 r53 starter 对应 catalog 的 `neg_002_ignore_reset`，哈希见本专题末尾。不能根据标签声称起始程序就是输出缩放 mutation，也不能将任何历史认证自动绑定到当前 starter。已确认字节身份与标签不一致；改题前仍需解释这项来源差异。

独立 checker 应从 ref/fb/rstb 的阈值交点执行一个简单事件队列，输出预期 UP/DOWN 边沿集合和高脉冲宽度；覆盖只有单边到达时复位、两边已到达但 timer 未截止时复位、低复位时有时钟、释放后先 fb 再 ref、reset_delay/tr/vh 覆盖。需要冻结同时事件规则。最终用 Spectre 观察公开端口，不能读取 up_state/trst 或接受候选自报事件时间。

建议优先提升为多 VA 的 PFD+电压控制环节+VCO/分频器小系统，故障只许改 PFD 或指定连接，验收保持鉴相方向、复位恢复和重锁顺序。这保留诊断关联性。单文件完整规格下整体重写很容易退化为规格建模。真实器件比较器或复位路径可作为第二阶段，只验收 VA 电压接口及闭环行为，器件求解交给 Spectre。

### 3. v4-1281：电源有效条件与异步复位事件计数

资产 [1281 instruction](../reference/v4/release/benchmarkv4-r53/tasks/1281-async-reset-event-counter-bugfix/public/instruction.md)。精确文件为该任务 `public/buggy_bundle/async_reset_event_counter.va`、`evaluator/solution/async_reset_event_counter.va`、`evaluator/score_tb.scs`、`evaluator/checker_profile.json`；来源为 [281 mutation catalog](../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/281-async-reset-event-counter/evaluator/mutation_catalog.json) 与同目录 derivation manifest。

事实：本地供电 span=V(vdd,vss)，输入相对 vss 归一化。clk 或 rst 上升触发更新；rst 高或 en/span 无效时清零；有效时满足两路输入阈值便计数，最多4，flag 在3以上有效。starter 算出 valid_v 后忽略它，既不在 invalid 时清零，又用常数1替代计数使能。它确有非 ADC 的状态/电源接口故障素材，但合同带14端口，其中 in2/in3/ctrl0/ctrl1没有影响主要计数逻辑，工程架构仍偏通用 helper。仅加“电路”名称不足以形成真实监控任务。

另一来源差异：derivation seed 为 `neg_003_wrong_scale`，字节比对确认当前 starter 对应 ignore_enable，哈希见本专题末尾。与1249相同，旧故障标签不能直接使用，差异原因仍待追溯。没有真实工程 bug issue/commit 证据，归类人工注入。

checker 建议只根据外部边沿、span、输入归一化和饱和递推计算 out/flag/metric，覆盖本地地电位移动、合法 span 两边边界、en 关闭后下一更新清零、停钟期间 rst 上升异步清零、连续触发和中断后重计。不要隐式新增“en变化立即清零”，因为旧合同只规定 clk/rst 更新。需要明确零幅度供电的处理和未用端口意义。

建议暂列备选，先将它具体化为上电资格链或采样有效次数监控，与 UVLO/复位释放顺序连接。单模块整体重写退化风险高，且冗余端口会浪费阅读预算而不增加工程挑战。

## 本地真实故障与原创语义故障对照

### 4. 三角波振荡器的双向 cross 反复换向

[来源](../tasks/va07-triangle-repair/SOURCE.md)、[题面](../tasks/va07-triangle-repair/instruction.md)、[独立 checker](../checkers/triangle_oscillator.py)。固定仓库来源链接为 [base 上的 SOURCE](https://github.com/BucketSran/vaEVAS/blob/b86845e1ef80498a8eed708a56bed993f7a7f17c/benchmark/tasks/va07-triangle-repair/SOURCE.md)。仓库记录 BC-0001 和真实积分历史重定位开发故障：cross 的方向0在边界事件中翻转自身积分斜率，返回穿越又翻转，产生额外换向。这是电路事件表达错误，不是收敛/加速题。

资产是仓库自有原创任务，不包含第三方模型源码；具体公开分发仍按仓库许可证和审批处理。参考用上限+1、下限-1的有向 crossing。checker 用外部正速度 ctl 的分段积分与三角波折返解析答案，不依赖参考波形，验收波形、换向时间和次数。允许重写且重写不必退化：输入连续变速、方向、初态和上下限变化要求模型保持积分历史；可比较另一种等价算法。但完整规格仍允许重新建模，应记录为“真实开发故障上的修复”，不可夸大为大型工程诊断。

SOURCE 记录已有历史 Spectre 校准，且区分本地 EVAS 查询网格未决和真实负例执行失败。本次没有复核那些运行，不能用 EVAS 的动态 cross 拒绝现象作为候选 VA 本身的正确性判据。它最适合直接研读独立判据与真实行为故障如何分离。

### 5. UVLO 资格计时取消遗漏

[题面](../tasks/repair-uvlo-recovery/instruction.md)、[来源](../tasks/repair-uvlo-recovery/SOURCE.md)、[起始代码](../tasks/repair-uvlo-recovery/environment/public/starter.va)、[参考解](../tasks/repair-uvlo-recovery/solution/dut.va)、[checker 的 uvlo_targets](https://github.com/BucketSran/vaEVAS/blob/b86845e1ef80498a8eed708a56bed993f7a7f17c/benchmark/checkers/first_batch_model_repair.py#L121)、[故障生成位置](https://github.com/BucketSran/vaEVAS/blob/b86845e1ef80498a8eed708a56bed993f7a7f17c/experiments/benchmark_first_batch/model_repair/build.py#L244)。

这是仓库原创电压 UVLO 合同，SOURCE 明确人工注错，未复制旧 v4/Cadence 源，也不声称实测或晶体管级真实性。故障删除 vin 回落时取消 up_at，并删掉 timer 发布时的 vin 再检查，允许旧资格事件错误发布 power-good。工程用途具体：启动短毛刺不能解除系统复位，棕断恢复需重新资格。独立 checker 从 PWL 阈值交点和复位时刻建立带 token 的队列，取消 token 使旧 deadline 失效；该算法与 VA 的实数 timer 实现不同。

适合接 UVLO+reset-release+enable-gate 多 VA 小系统，提供“短毛刺后某个下游模块错误启动”公开现象，允许指定模块或连接修复，保持完整 pgood/fault 和恢复时间合同。下一步可接真实比较器产生的电压输出；禁止把 VA 的输出电流/阻抗要求偷偷加入范围。单模块规格已详细，完全重写会接近建模题，但小系统通过故障定位和保持未改行为仍有诊断价值。

现有 SOURCE 仅声明本地构造与行级 checker 测试；需要另查实际 Spectre/Harbor/Agentic 收据。本次不声称它已经完成终验。许可边界与仓库原创资产相同。

## 公开第一方代码与修订

以下三项由 research 子调查核对第一方 commit、patch、源码和许可。完整阅读记录保存在本机 `runs/benchmark-material-survey-20261008/repair-raw/public-behavior.md`。DFF/PFD 来自同一个 verilogaLib 来源组，不能按两个独立工程来源解释成绩覆盖。第三项超出电压域，仅作真实修复方法对照。

### 6. verilogaLib DFF：异步控制与确定启动状态

[异步控制真实提交 `7a32dca34a49380d211423b5128798d5c6dd10a0`](https://github.com/ShabbyGayBar/verilogaLib/commit/7a32dca34a49380d211423b5128798d5c6dd10a0) 删除旧 `dff_rsn.va` 并加入 [dff_sr.va](https://github.com/ShabbyGayBar/verilogaLib/blob/7a32dca34a49380d211423b5128798d5c6dd10a0/dff_sr.va)。[初始化增量提交 `5c32ac1a8a1b27482271ad54066a886381fd5628`](https://github.com/ShabbyGayBar/verilogaLib/commit/5c32ac1a8a1b27482271ad54066a886381fd5628) 的父版本是 `63a571f7d650dd4816eef3ac69825cf3e9d9b757`，同路径旧/新文件可固定比较。[MIT LICENSE](https://github.com/ShabbyGayBar/verilogaLib/blob/5c32ac1a8a1b27482271ad54066a886381fd5628/LICENSE) 允许复制改编，需保留 Brian Li 2025 版权与许可文本。

事实：新合同规定低有效 rst/set 双有效时 Q、Qbar 同为高；旧实现总用 x 与反相输出，静态上不能表达该双高规则。新增 initial_q 和 initial_step 处理启动时已有异步控制。提交标题是 feat/refactor，没有找到 bug issue、失败波形或完整回归，不能标为上游确认真实缺陷。若用新契约改旧代码成修复题，应标来源驱动人工改题；初始化参数属于真实新增接口，更接近扩展任务，不能声称旧版违反旧合同。

工程用途推断为混合信号采样、分频及顺序控制。建议独立 checker 按外部时钟和控制事件建状态机，验证只在时钟上升采样、异步覆盖、双有效、初始控制有效、解除顺序以及输出延迟。双有效解除后的存储规则必须公开，不能偷用 reference 实现定义。整体重写允许，但需检出组合门、普通互补DFF和无存储实现；若题面给出全状态表，单文件仍易退化为规格建模。更适合作多 VA 复位释放或分频系统中的指定修复模块。

未知：7a32dca 的旧父SHA尚未取得，旧文件可由固定 patch 读取但收题仍需补身份；`discipline.h/constants.h` 与目标环境的头文件映射未验证。无 Spectre/EVAS 仿真，未证实控制解除竞争语义。

### 7. verilogaLib PFD：内部复位与外部输出电平分离

[真实重构提交 `63a571f7d650dd4816eef3ac69825cf3e9d9b757`](https://github.com/ShabbyGayBar/verilogaLib/commit/63a571f7d650dd4816eef3ac69825cf3e9d9b757)、[固定 pfd.va](https://github.com/ShabbyGayBar/verilogaLib/blob/63a571f7d650dd4816eef3ac69825cf3e9d9b757/pfd.va)、[新旧 patch](https://github.com/ShabbyGayBar/verilogaLib/commit/63a571f7d650dd4816eef3ac69825cf3e9d9b757.patch)、[同修订 MIT LICENSE](https://github.com/ShabbyGayBar/verilogaLib/blob/63a571f7d650dd4816eef3ac69825cf3e9d9b757/LICENSE)。

事实：旧内部 reset 振幅乘外部 vlogic_high，再以输入阈值 vtrans 检测。新实现将内部 reset 归一化到0/1并固定0.5 crossing，同时改 fb 为 lo，增加 vlogic_low 和初始化。真实行为改动存在，但未找到上游 bug issue或失败波形。静态推断的反例是输入时钟足以过 vtrans，而输出高电平低于 vtrans，旧内部 reset 可能无法过阈值，状态锁住。必须实际复现才能作为已确认故障。

用途为 PLL 鉴相鉴频，未核对具体系统部署。改题应剥离端口改名和新增输出低电平，公开原端口与内部复位独立要求，固定旧 starter 父版本。独立 checker 从两个输入边沿的事件队列得到 UP/DOWN 脉冲，改变输出轨但保持输入能触发、测试先后边沿、频率失配、单路停钟和多周期复位。需冻结短周期/同时边沿的接受范围。整体重写成 XOR 或只比最后时间戳会丢失频率鉴别与持续状态，完整事件序列能检出；若只有平均相位评分则会放过。

未运行反例、Spectre 或其他模拟器；旧父完整SHA尚缺；无现成独立 checker 经过本次审计。许可可用，但接入、包含文件和时序边界都待验证。

### 8. fairchild 波导损耗：真实行为修复的范围外对照

[真实修复 commit `3a307175e6fc931bce231e33e1fbcef73abd3766`](https://github.com/hughmor/fairchild/commit/3a307175e6fc931bce231e33e1fbcef73abd3766) 明确记录损耗换算中的二倍关系重复计算。固定修订同时保留 [旧 waveguide.va](https://github.com/hughmor/fairchild/blob/3a307175e6fc931bce231e33e1fbcef73abd3766/legacy/va-models/photonic/waveguide.va) 与 [新 va_waveguide.va](https://github.com/hughmor/fairchild/blob/3a307175e6fc931bce231e33e1fbcef73abd3766/examples/verilog_a/models/va_waveguide.va)。[check.py](https://github.com/hughmor/fairchild/blob/3a307175e6fc931bce231e33e1fbcef73abd3766/examples/verilog_a/check.py) 和 [wg_compare.sp](https://github.com/hughmor/fairchild/blob/3a307175e6fc931bce231e33e1fbcef73abd3766/examples/verilog_a/wg_compare.sp) 为上游验证入口，未运行、未确认 checker 独立性。[README](https://github.com/hughmor/fairchild/blob/3a307175e6fc931bce231e33e1fbcef73abd3766/README.md) 声明MIT，但该修订未找到完整 LICENSE 文书，复制前仍需补版权许可证据。

上游记录1 mm、3 dB/cm 的旧功率比约0.966051，修正值约0.933254。解析独立答案是 `Pout/Pin=10^(-alpha_dB_cm*L_cm/10)`；可验收长度/损耗变化、零损耗、相位旋转保范与串接功率相乘，不能用同库 native 模型作唯一答案，因为它曾有同类错误。重写成实数衰减丢失复数相位，只验证单点又会放过硬编码。

它使用 optical_field/optical_lambda 自定义 discipline 和 OF/OWL 访问器，明确超出当前电压域，排除直接收题，不推断电压域改写可行。该commit内其它收敛/移植修改不属于本调查。它提供“真实行为修复记录+物理公式+旧新资产”的研究方法参照；本次未仿真、未跑独立重算、未核对 Spectre 接入。

## 从材料到可收题仍缺什么

1. 固定公开行为与故障来源。旧 v4 的“scored=true”和 mutation killed 是历史包内部状态；本仓库资料 README 明确它们不参与当前评分。249/281 的 starter 与 seed 标签差异应先追溯，不能复制错误 provenance。
2. 固定修改边界。允许单模块重写，系统题可指定模块、连接和设计参数可改。checker 和终验参数独立固定。只有题面公开的保持行为进入隐藏验收，不额外要求原 reference 的内部算法。
3. 独立 checker 使用输入交点、解析递推和公开端口。除正常输入外，检查复位插入、timer 取消、停钟、合法参数变化和输入参考地移动。需要真正能检出相关故障的负例，不能只靠零输出 stub。
4. 实际 Spectre 终验需绑定 source hash、网表、参数、初态、Spectre版本、容差和完整波形。对参考、等价实现、针对性负例和模型提交做判分校准。EVAS 实测是另一个复现证据，不替代 Spectre。
5. 分发逐项确认。旧 v4 本地持有不代表有对外发布许可；Cadence 只描述索引元信息，未知许可源码不复制进题面/参考解/checker。新原创实现应清楚记录需求参考和未复制代码边界。

本专题只执行文件读取、结构检查和 SHA256 记录，未编译、未运行 Spectre/EVAS/Harbor，未调用模型解题，未重判历史波形。额外字节检查确认1249 starter 的 SHA256 为 `41023069a21d873c92ddd874ec7600edf1417db35f8a0cda642a0aa046b6415c`，对应 catalog 的 ignore_reset；1281 starter 为 `b50490447ef19eb1a62cfebbc126c9f5033524077e2c013fc112518eb45a872e`，对应 ignore_enable。两者均不等于各自 manifest 声称的 seed 文件，本机核对记录为 `runs/benchmark-material-survey-20261008/repair-raw/seed-identity-check.json`。这证明字节身份不一致；为什么发生以及哪些发布/认证记录受影响仍未知。所读 v4 文件身份清单保存在同一本机目录的 `local-asset-identities.json`。

## 先读哪些，先试哪类任务

优先读三份材料：

- [三角波修复 SOURCE 和独立 checker](../tasks/va07-triangle-repair/SOURCE.md)。它给出真实故障、独立设计目标、仿真器差异和校准边界的完整分离范例。
- [v4-1249 PFD 合同及 starter](../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/public/instruction.md)。重点读单边挂起复位和 pending mutual reset；同时核对来源标签差异，避免沿用不一致的 provenance。
- [UVLO 独立 token 事件队列](https://github.com/BucketSran/vaEVAS/blob/b86845e1ef80498a8eed708a56bed993f7a7f17c/benchmark/checkers/first_batch_model_repair.py#L121)。它展示如何用外部刺激和独立数据结构验收取消计时，适合扩展到多模块复位系统。

优先任务方向按以下顺序推进：

1. 多 VA 的 UVLO、复位释放序列和使能门系统。用短毛刺、棕断、复位释放时电源已高的公开失败现象要求定位。允许指定模块或连接修复，固定 power-good 资格时长及下游启动/复位顺序。故障源明确标人工注入，后续真实电路反馈再单列记录。
2. 多 VA 的 PFD 与时钟反馈小系统。复位落在单边状态或待清零 timer 期间，恢复后检查鉴相方向、脉冲宽度和重锁。明确可以改的 PFD/连接/参数；保留未出错的时钟模块与接口合同。公开 DFF/PFD 代码可作接口和架构阅读，实际修复素材优先 v4 的具体 reset 错误。
3. 采样保持阵列与读出 mux 系统。让采样、保持泄漏、通道选择和复位错误在端口上产生具体电压误差，要求修复指定采样或读出模块并保持其他通道行为。1042 可作基础种子，但当前“采样恒零”的错误不足以证明挑战性；应以多通道状态交互和规定保持误差为核心。

三项方向均先有多 VA 系统的独立验收，再决定是否接真实器件网表。器件级阶段应保留实际比较器/开关/控制电路的用途与证据，不能将纯行为合成波形称为实测或晶体管级真实性能。本次推荐只决定下一步材料与改题顺序，不表示任务已完成校准或正式接纳。
