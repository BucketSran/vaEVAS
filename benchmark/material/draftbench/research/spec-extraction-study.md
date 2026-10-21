# 从 checker 与参考实现提取 Spec：30 题静态对照

2026-10-21，研究如何把来源材料转成可独立实现、可验收的公开规格，并纳入现有 benchmark
建设流程。研究覆盖 15 道 AnalogBench 和 15 道 CVDP Heavy v1.1.0，每题分别使用独立的重建
会话和对照会话。没有运行电路、RTL、编译器、容器、模型解题或候选优化。

两组证据不对称。AnalogBench 有 checker 和参考网表；Heavy 官方公开版本不含参考补丁正文，
本组只能使用 checker 与待修改 baseline。下文不把这 30 题统称为完整 checker/gold 配对，
也不比较两组“恢复率”。本次改进的是作者流程，没有证明生成规格已更准确或任务更有区分度。

## 可采用的建设方法

从材料提取规格可以自动生成候选条款和证据索引，但完整需求还需要工程依据与作者选择。
建议按以下顺序建设，执行要求已写入[现有英文流程](../docs/agent-workflow.md#extract-and-review-a-behavior-agreement)。

1. 固定来源版本，识别原要求、公开引用文档、gold、故障 baseline、台架、checker、配置和历史记录。
   先追踪真正生效的源码与检查入口，再解释代码。递归收齐公开规范依赖，记录不可得的部分。
2. 提取每项独立行为的输入与历史、可观察输出、参考、条件、误差及来源。
   区分直接依据、推断、作者主动选择和未知；复用 `SOURCE.md` 的现有分节。
3. 分开模型适用范围、任务要求满足的域、具体验证用例和数值测量预算。
   同时区分电路性能指标、模型误差界和测量不确定性。
4. 查找会影响正确性的分歧。用同一合法输入和历史下的两种读法，说明为何无法确定某个输出是否合格。
   容差内差异、明确允许的随机性和实现自由可以合法，无需限定唯一输出。保留来源冲突并裁决。
5. 从行为约定写公开 `Spec`，从工程边界写 `Deliverable`。
   度量定义可以放在公开引用材料中，私有测试不能补充隐藏的正确性规则。
6. 用独立审查核对公开合同、预期推导与验收覆盖。旧资产可采用本次的代码盲重建再对照方法；
   新题直接依据工程材料和声明的选择审查。静态审查后，仍按原阶段门槛开展获准的校准。

这是既有建设流程的细化，不新增强制 JSON、中间状态、逐题双会话审批或独立工作流文件。
研究用 JSON 方便审计，不作为日常题包的新格式。R01 的未定数值及边界不因本研究自动采纳。

## 来源、选样与证据身份

AnalogBench 使用 [Arcadia-1/analog-design-bench 的固定提交](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25)。
从其 50 个题包中，在重建结果产生前选取 15 题，覆盖放大、采样、选择、时序、转换、电源、振荡和偏置。
这些题的 `solution/circuit.spi` 均存在。本次读取参考实现及静态检查代码，不继承历史通过记录为本次验证。
外部 `/opt/analog-arena/check_circuit.py`、PDK 与基础镜像内容未在本地源码快照中检查。
部分任务有 starter 内的网表指南，部分只引用镜像内指南，不能一概说指南缺失。

CVDP 使用 [nvidia/cvdp-benchmark-dataset 固定版本](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/tree/5b807d945f6a99aa645f7e43a64a2115e281b4bf)。
公开 Heavy 的 no_commercial 75 题及 commercial 25 题均保留 patch 路径而无非空补丁内容。
[官方 runner README](https://github.com/NVlabs/cvdp_benchmark/blob/8e894cf74414ab1eaea1e2b4e80a02f123df07b6/README.md#L11)
也说明公开发布排除了参考解。所选 15 题来自 no_commercial，按不同工程仓库覆盖接口与工作范围，
没有根据 checker 质量或重建好坏筛题。这不是对全部 Heavy 的随机抽样。

Heavy 的 [sanitized context bundles](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_public/README.md)
是任务起始上下文，不能当作 gold。15 个 bundle 的 LFS SHA256 已核对，并恢复到各题指定 context commit；
这些提交没有父历史，不能从中恢复修复前后版本。CH05 的 checker 内嵌 RTL 参考仍保留这一身份，
不等于官方 gold 补丁已公开。没有借用其他题的上下文或自行解题补作参考解。

| 原始文件 | SHA256 |
| --- | --- |
| Heavy no_commercial JSONL | `809916fa3248a4b2597b2a2ac364d3450d24936cad0e25bbe1bf0f1243ad1ea7` |
| Heavy commercial JSONL | `a4f6e9e9a0928aa8d78fe513476d4541173fc6d3760d5dd6683265b3aa98aacf` |

## 独立会话如何工作

每题 A 会话只拿 checker、可用参考代码、代码台架和配置。Heavy 额外提供代码 baseline，并明确它可能有错。
A 不能读实际题面、独立规格文档、其他题、来源缓存或网络，输出英文重建 Spec、逐项来源主张和访问记录。
重建文件冻结并保存哈希后，另一个全新 B 会话读取它、真实题面、题面引用的公开材料和相关制品。
B 输出中文对照、逐项差异来源和访问记录，不修改 A。

对照包括恢复正确、材料支持但提取遗漏、测试被外推成全域、实现被误当要求、无法恢复的意图、
规格与制品冲突、测量定义缺口、公开上下文缺口和原规格歧义。类别用于组织发现，没有统一的
“原子需求”计数单位，因此不计算匹配百分比。原题是对照对象，也需要接受一致性检查。

代码注释保留，可能含规范性文字。这里的独立性指会话上下文与允许读取路径分离，不是去除所有
语义线索，也没有证明模型从未在预训练中见过材料。会话共享文件系统，访问记录是工具记录与自述，
没有实施操作系统级隔离。因此本研究支持定性方法总结，不支持严格盲测效果或因果改进结论。

初始 Heavy 打包脚本误将隐藏配置过滤。发现后，CH01–CH10 初稿进入 `intake-v1` 归档，
向原 A 会话补入公开 `.env`，在不提供真实题面的情况下复核，再重新冻结。CH01 已有的 B 报告也保留初版并复核。
随后完整性核查补回 CH06 的 `.env_core2axi`，补读前 A/B 保存在 `intake-v2`。
其余两份被排除的 `.gitignore` 仅含 `__pycache__`，不作规范依据。上述都是研究取材问题，
不能归咎原数据。初稿、修订与取材纠正均保留，未用 B 见到的真实要求反向改写 A。

## 15 道 AnalogBench 的逐题收获

每个编号对应一对独立会话。下表是便于定位的定性结论，具体主张和源行号保存在本机逐题报告。

| 编号与固定题包 | 对规格书写有影响的观察 |
| --- | --- |
| [AB01 五管 OTA](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ota-5t-gain40-pm60-noise50uv-pvt) | 电气门槛可恢复，五管设计目标与“不按内部器件数匹配”的政策不能由 gold 唯一推出；first crossing 还需明确方向 |
| [AB02 cascode OTA 修复](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-telescopic-cascode-ota-pvt-fix) | 27 点覆盖、固定偏置与明确排除项要分别记录；末窗均值的取绝对值顺序和权重需定义 |
| [AB03 三阶段 ring amplifier](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ring-amp-3stage-gain8-400uw) | 本题确有架构要求，不能因未见拓扑断言就取消；功耗窗口、最后入带和独立记录的历史需核对 |
| [AB04 bottom-plate sampler](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-bottom-plate-sampler-pvt) | 保持区间最大偏差与两时刻之差不同；SFDR 目标及其工程理由不能变成 ENOB 要求 |
| [AB05 bootstrap sampler](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-bootstrap-sampler-fft) | “每个跟踪窗”与 32 个稳态检查点不同；公共与终评正弦相位、读值时刻影响语义 |
| [AB06 8:1 MUX](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-analog-input-mux-8to1-pvt) | 带宽需要基线频率与下降交点定义；公开压力点诊断与终评不能只凭指标同名视为等价 |
| [AB07 二分频器](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-transistor-divide-by-2) | 复位释放相位、门槛交叉序号和观察窗口需明确；DUT 禁用器件政策不适用于台架元件 |
| [AB08 3-bit flash ADC](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-flash-adc-3bit-pvt) | 有限代表工况、理想输入驱动和距码阈值裕量属于合同条件；flash 名称不自动要求某种内部拓扑 |
| [AB09 异步 SAR ADC](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-sar-adc-4bit-async) | 采集、启动转换与判读时刻应写成时序关系；允许改变 tone bin、码序和 decoy 的范围不能只靠一条台架推定 |
| [AB10 5-bit DAC](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-cmos-switched-resistor-dac-5bit-pvt) | major-carry 建立和峰值偏差需要时间基准；输出阻抗门槛的工程依据不能由代码中的常量反造 |
| [AB11 2:1 SC converter](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-switched-capacitor-2to1-converter-pvt) | 内部相位生成与电容归属是工程职责；startup、保持、Rout 符号及功率有效性要分别定义 |
| [AB12 LDO](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ldo-ota5-robust-pvt-mc) | 外部板级网络与 DUT 边界影响合法实现；历史结果的 100 µVrms 不能覆盖当前正文和 checker 的 150 µVrms |
| [AB13 current-starved VCO](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-current-starved-ring-vco-pvt) | 名义条件失败如何影响后续评分，与测量无效是不同分支；duty、平均功率与 pushing 需公式和窗口 |
| [AB14 ICC/IPTAT 电流镜](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-programmable-icc-iptat-current-mirror-pvt) | 完整区间与 41 点扫描、扰动条件下跨码要求与仅标称检查的量词需分开 |
| [AB15 bandgap](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-high-psrr-bandgap-reference-pvt) | 连续温漂目标不能缩成 1 °C 网格；启动基准来源与初态不能被“同一指标”概括 |

## 15 道 CVDP Heavy 的逐题收获

以下链接定位固定 JSONL 中的题目记录。完整上下文来自该记录指定的公开 bundle，均为 baseline。

| 编号与原始 ID | 对规格书写有影响的观察 |
| --- | --- |
| [CH01 axis_0001](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L15) | 发现可疑代码不等于获知完整修复授权；原题对常量赋值的分支定位与 baseline 不符 |
| [CH02 async-fifo_0003](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L43) | 读数据源的单个断言不能恢复完整 FIFO、指针、边界与 CDC 意图；参数适用范围还需公开依据 |
| [CH03 edma_0008](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L52) | 线上出现包值不等于接受事务；安全谓词、停机、恢复和新模块职责无法从有限样本唯一恢复 |
| [CH04 enso_0003](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L23) | 短 prompt 引用的 bench 提供核心合同；只修改指定模块和显式寄存器名称仍是作者要求 |
| [CH05 i2c_0007](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L50) | checker 内嵌参考的无效读行为不能自动升格为要求；默认值、结构及 full 判据仍需规范核对 |
| [CH06 pulpino_0004](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L69) | 统一双端口和零起始 RAM 是修改目标，旧集成不能约束新目标；接口不一致未必是 checker 缺陷 |
| [CH07 rvx_0002](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L42) | 应先看配置实际加载的八个 RTL；旁置 top、日志与刺激不能代替生效工程或功能断言 |
| [CH08 verilog_pcie_0004](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L54) | 被引用规格补足复位和参数域；有限宽计数回绕与每个事件最终可见的承诺需要容量边界 |
| [CH09 verilog_ethernet_0029](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L21) | 头字段、排他路由、复位及背压要求宽于检查器观察；整帧输出和目的映射仍有歧义 |
| [CH10 usb_cdc_0037](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L2) | 全面修复不能缩成复位输出检查；README 中 PHY 采样例外需要与泛称顺序逻辑门控对齐 |
| [CH11 ddr4_controller_0005](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L4) | new_seed 仍有效时的输出缺陷不能被撤销后才读值的检查覆盖；“所有工作条件”也需要可操作的边界 |
| [CH12 wifi_ldpc_codec_0002](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L5) | 保持值不变不能替代正向采样要求；计数有变化也弱于恰好 +1 |
| [CH13 fabulous_fabric_0006](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L59) | 末态完成不能代表未提前完成、一字一拍和异步复位；DESYNC 编码及 SPI 模式存在冲突 |
| [CH14 fpu_wrappers_0005](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L8) | 公开规格补充结构要求；nan_sign 的角色与 checker 用途有语义缺口，打印结果不能建立完整算术合同 |
| [CH15 schoolMIPS_0012](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl#L3) | ROM 正确及寄存器期望值的叙述与编码有冲突；完整分频周期与低电平计数必须分别定义 |

## 哪些写法最容易改变题意

### 先保留需求量词，再说明测量近似

AB04 的题面要求保持期间变化不超过 5 mV，bench 实际比较 7.8 ns 与 11.5 ns 两个值。
AB14 同时要求完整 compliance 区间的偏差和至少 41 点扫描；代码的有限点并不证明点间行为。
正确处理是保留区间义务，另记当前测量方法及充分性缺口；不能把两个端点之差直接改称最大保持误差。
见 [AB04 规范](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-bottom-plate-sampler-pvt/instruction.md#L24)、
[保持 bench](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-bottom-plate-sampler-pvt/tests/benches/tb_hold.spi#L19)
和 [AB14 规范](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-programmable-icc-iptat-current-mirror-pvt/instruction.md#L60)。

写作者应明确 `max |error(t)|`、`|error(t_sample)|`、`|mean(error)|` 或 `mean(|error|)` 中采用哪一种，
写出参考值和窗口。数字问题也一样：测试看到信号可解析或读到一个包值，不等于完整事务成功。
CH03 的包值采样不等待 valid；不能从该观察推出安全策略允许这笔事务。

### 不从 gold 选择推导实现政策

AB01 的五管设计目标与资格评分政策并不相同，AB03 则明确要求三阶段架构。
对 VA 任务，不能统一规定“只看外部波形”或统一规定“必须沿用参考结构”。应先确定本题考察的工程责任，
再声明强制架构、保留职责和允许变化。未观察内部节点也不能取消公开的架构义务。
见 [AB01 政策](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ota-5t-gain40-pm60-noise50uv-pvt/instruction.md)
和 [AB03 开头](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ring-amp-3stage-gain8-400uw/instruction.md#L1)。

CH06 说明另一个方向：扩展任务要改变旧工程。baseline 接口只能说明起点，不能自动成为必须保留的终点。
看见 checker 期待的新信号而旧接口没有时，要先读修改要求；这本身不足以判 checker 错误。

### 把数值目标、定义和预算分别写清

AB04 能从代码恢复 80 dB SFDR，却不能唯一推出选择该目标的工程理由，尤其不能把其动机改写成
13-bit ENOB 硬指标。AB12 当前正文与 checker 是 150 µVrms，历史摘要另写 100 µVrms，历史记录不应
改写当前门槛。另有任务的功耗平均窗、启动参考或最后入带搜索与自然语言简称不完全一致。
这些需要指标定义和版本核对，不应靠调容差消除。

对本项目，输入斜率乘以时间定位误差只是一项幅值误差预算。它既不决定工程需要的输出精度，
也不证明求解器能在该预算内完成。未知精度可以在设计阶段保留具名 TBD，说明依据与备选方案，
后续获准校准才形成可达性证据。相关职责见[设计参考](../docs/design-reference.md#从工程依据提取规格)。

### 检查完整公开上下文，不按 prompt 长度评价规格

CH04 的 bench、CH08 的 `docs/spec_pulse_merge.md`、CH03 的旧 DMA 文档以及 CH10 的 README
会改变读者可知的合同。把这些排除在 A 包中是研究设计，不能据此指控原题遗漏。
反过来，一个 `/opt` 路径或镜像标签也不能证明研究者已核对了指南、合法性规则或 PDK。
应区分故意隐藏、取材漏件、源快照不含及尚未检查运行环境四种情况。

公开依赖完整也不保证自洽。CH08 的事件不丢失承诺需要容量或流量条件；CH01 的错误分支定位
与代码不同。发现这类问题时，生成器应返回两侧证据和具体待裁决规则，不能自动挑一侧写得更肯定。

## 如何复用独立提取与对照

以下是作者会话提示的最小内容，实例化时补路径、版本和写入边界。生产流程中复用已有记录，
无需每题照搬本研究全部输出。不能把作者提示附到 solver instruction。

```text
Stage A: Read only the supplied checker, available reference code, code benches
and public build configuration. Do not read the actual prompt or standalone spec.
Distinguish a faulty baseline, a candidate gold and a checker-embedded oracle.
Reconstruct an English engineering Spec and Deliverable. Trace each obligation
to source lines, state its conditions/history/reference, and separate tested
examples from the required domain. Keep implementation policy and absent intent
unresolved unless supported. Record files read, omissions and apparent spec text
in comments. Do not simulate, solve or browse other sources. Freeze the output.
```

```text
Stage B: In a different fresh session, compare the frozen reconstruction with
the actual prompt and all referenced public specifications, then inspect relevant
artifacts. Do not edit A. Identify faithful recovery, extraction omissions,
unsupported generalization, unrecoverable intent, measurement gaps, conflicting
sources and missing public context. Cite both sides and separate static facts
from runtime hypotheses. Do not assume the original spec or gold is infallible.
Return concrete writing lessons; do not score prose similarity or match rates.
```

自动化适合负责来源清单、哈希、配置依赖、候选条款、来源行号和结构检查。
含义提取后仍须复核量词、时序参考和失败分支。需要作者决定的是工程用途、欠确定的正确行为、
抽象与实现限制，以及没有来源的精度尺度。常规缺文件、链接、提取遗漏和格式问题由 agent 修复；
不把它们全部转成人工问卷。校准阶段再用正确替代实现和定向错误检查误拒与漏检，继续遵守执行授权。

## 本机证据与研究限制

完整本机记录位于 `runs/benchmark-review-principles-20261016/spec-extraction-study-20261021/`。
每题的 `A-output/`、`B-output/` 保存文档、来源 JSON 与访问记录；`input-manifest.json` 和
`A-freeze.json`、`B-freeze.json` 保存输入及冻结输出身份。来源下载、原始题面与源码留在 ignored
运行区，不随本笔记再分发。维护的正文保留固定原始来源和可独立阅读的结论。

`scope.json` 记录 4 小时上限与禁止实验边界，`decisions.tsv` 是本轮唯一决策流水，
`sessions.json` 记录逐题会话，`study-audit.json` 记录文件、JSON、哈希和引用范围检查。
这些检查不能证明条款语义正确、会话强隔离、参考实现可行或 checker 运行有效。

本轮没有校准任何电气/RTL 指标，没有重现发布者结果，没有评估模型通过率，也没有证明所有
静态风险均可触发。样本有意覆盖不同机制，不能推断整个数据集的问题比例。
方法已纳入[建设流程](../docs/agent-workflow.md)，对人的解释在[设计参考](../docs/design-reference.md#从工程依据提取规格)，
公开规格的内容职责继续由[题包约定](../docs/task-package.md#行为说明的详细程度与草稿边界)维护。
