# 从表征数据建立动态 Verilog-A 模型：材料调研

调研日期为 2026-10-08。仓库讨论基点为 `b86845e1ef80498a8eed708a56bed993f7a7f17c`。本报告服务于已采用的五类 VA benchmark 中“从数据建立模型”一类。首题仍为真实采样级电路；候选交付为可独立运行的电压域 Verilog-A，最终在 Spectre 中验收。这里没有新增评分任务，没有运行 Spectre、源电路仿真、辨识训练或 checker 校准。

沿用已定顺序：先固定表征数据包，后续阶段才让 Agent 主动调用原电路补做表征。真实来源、动态行为和使用指标是核心。静态曲线拟合、纯问答、仿真加速和收敛调试不纳入本类。原始取回文件位于本机 `runs/benchmark-material-survey-20261008/data-raw/`，不随研究笔记发布。

## 当前建议

首题可继续使用 JKU/Manuel Moser 的 SKY130 transmission gate 与固定 hold C。真实 MOS 开关和现成瞬态台架已实际取得，许可明确。它有机会把输入相关采集、沿附近 pedestal 和状态延续放在一个小电路中，但本次没有证明这些效应已经大于数值噪声，不能预先承诺都能评分。

方法上采用独立实验留出和无真实输出反馈的自由运行。公开数据必须足够区分瞬时采样、有限建立时间及不同历史下的响应。隐藏测试不应负责揭示公开数据根本无法辨识的效应。Silverbox、Wiener–Hammerstein 与 SUBNET 提供数据和方法参考；它们不能替换真实采样级首题，也不证明现有源电路已经可用 Spectre 生成真值。

本次新增核实了三点：官方 dataloader 的实际 LICENSE 是 BSD-3-Clause；2009 WH 原报告与当前 dataloader 的初始化/评分窗口不同；若照搬 CT-subnet 作者 notebook，会把部分 validation 记录保留在 test 中。这些都说明必须检查代码和版本，不能只照抄论文概述。

## 9 组一手材料

所有链接的核查日期均为 2026-10-08。GitHub 原始文件已按固定 revision 下载到本机研究输出目录的 `data-raw/`，正文中的“已取得”只表示文件取得与阅读，不表示运行成功。网页和数据未固定发布版本的情况单独标出。

### 1. SKY130 SAR ADC 的 transmission gate 与采样台架

- 标题/owner/年份：`SKY130_SAR-ADC1`，Manuel Moser / JKU，原理图版权 2022，GitHub owner 为 efabless。
- 固定版本：[892272208df28b6c7620101e129a9d8dd95ebab7](https://github.com/efabless/SKY130_SAR-ADC1/tree/892272208df28b6c7620101e129a9d8dd95ebab7)。核心路径为 [adc_gate_switch.sch](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_switch.sch)、[adc_gate_tb_transient.sch](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_tb_transient.sch)。本机副本在 `runs/benchmark-material-survey-20261008/data-raw/sampler/`。
- 事实：开关使用 SKY130 pfet/nfet，主开关 W=7.6、L=0.22，dummy W=3.8、L=0.22。台架有互补控制 inverter、2.44 pF hold C，tt、1.8 V、25°C，`.tran 10p 65n`。源文件有 1 ps 边沿和 `RELTOL=.1`。已取得 README、LICENSE、两份原理图及比较器 SPICE 网表；未取得该采样台架的独立原始输出数据。
- 许可：[Apache-2.0](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/LICENSE)，原理图也带 notice。源 PDK 的实际依赖文件版本与许可仍需单独固定。
- 借鉴建议：输入包记录 `vin(t)`、外部控制、实际输入重构方式及 `vhold(t)`，允许用显式状态描述跟踪阶段与保持阶段。若 inverter 包含在隐藏原电路中，应明确模型接收外部单控制还是接收两路已生成控制；否则沿延迟的归属会不清楚。
- 隐藏实验/负例建议：在同一瞬时 `vin`、同一 clock 电平下，改变前一拍保持值和本拍跟踪时长；留出新输入阶跃序列、不同输入/clock 相位以及连续多拍。负例为瞬时采样、固定 RC、每拍清零、记忆训练波形、错误有效沿。
- 适配缺口/未知：松容差和极快边沿需先做源表征的数值对照。dummy 可能降低开关注入；droop 未证明可观察。原理图不是直接可运行的 Spectre netlist。本题固定 hold C 与其他外部条件，不要求候选端口电流或可变负载耦合。

### 2. JKU improved OTA 闭环缓冲器

- 标题/owner/年份：`Analog (Integrated) Circuit Design`，Harald Pretl 与 JKU 合作者，README 版权 2024–2026；瞬态台架版权 2024–2025。
- 固定版本：[5635f2f5bb52968ed6c5d6896b2243d023af7edc](https://github.com/iic-jku/analog-circuit-design/tree/5635f2f5bb52968ed6c5d6896b2243d023af7edc)。已取得 [ota-improved.sch](https://github.com/iic-jku/analog-circuit-design/blob/5635f2f5bb52968ed6c5d6896b2243d023af7edc/xschem/ota-improved.sch)、[ota-improved_tb-tran.sch](https://github.com/iic-jku/analog-circuit-design/blob/5635f2f5bb52968ed6c5d6896b2243d023af7edc/xschem/ota-improved_tb-tran.sch)、[CACE YAML](https://github.com/iic-jku/analog-circuit-design/blob/5635f2f5bb52968ed6c5d6896b2243d023af7edc/cace/voltage-buffer-ota-improved.yaml)，副本在 `data-raw/ota/`。
- 事实：课程用 xschem/ngspice，当前工艺是 IHP SG13CMOS5L。台架供电 1.5 V，固定 50 fF，输入 0.8 V，通过 enable 启动，量测 99% 输出阈值。CACE 指明 ihp-sg13cmos5l 与 IIC-OSIC-TOOLS 2026.08+，含 settling 对输入、供电、温度、corner 的设置。这里只检查配置，没有取得/重算完整波形。
- 许可：[Apache-2.0](https://github.com/iic-jku/analog-circuit-design/blob/5635f2f5bb52968ed6c5d6896b2243d023af7edc/LICENSE)，不自动涵盖所有 PDK 依赖。
- 借鉴建议：作为非 ADC 的后续真实连续动态候选，提供输入电压、enable、输出电压的整段记录，用小/大阶跃与启动记录辨识有限带宽及非线性 slew。既有台架主要支撑启动，不能据此声称已提供完整输入阶跃数据。
- 隐藏实验/负例建议：留出幅度与方向组合、停止/重启、饱和后回到工作区的整段实验。错误解包括静态跟随、一阶固定时间常数、以测得稳态值作 oracle、只拟合 enable 启动。
- 适配缺口/未知：IHP PSP/OSDI 与 Spectre 的移植未验证；slew、振铃、饱和恢复需新表征确认。它是固定条件的 OTA voltage buffer，不能称为现成完整 ADC driver。

### 3. Silverbox 实测动态基准与原技术报告

- 标题/owner/年份：Wigren、Johan Schoukens，`Three free data sets for development and benchmarking in nonlinear system identification`，ECC 2013；原技术说明标题为 `Data for benchmarking in nonlinear system identification`，2013-006。
- 原始入口：[官方 Silverbox 页面](https://www.nonlinearbenchmark.org/benchmarks/silverbox)、[原说明 PDF](https://drive.google.com/file/d/1EgQGYn1r949VChEhUTRkOe5xToxiFszE/view)、[SilverboxFiles.zip](https://drive.google.com/file/d/17iS-6oBUUgrmiAcrZoG9S5sOaljZnDSy/view)。本次成功下载 PDF 375,681 bytes、ZIP 5,793,999 bytes；解包包含 `SNLS80mV.{mat,csv}`、`Schroeder80mV.{mat,csv}` 和两份 README。副本在 `data-raw/silverbox-*`，发布链接没有固定数据 revision，另保留 SHA-256 清单。
- 事实：真实电子电路实现 Duffing 类反馈动态，V1 为输入电压，V2 为实测输出。原说明记录生成与采集同步、采样频率约 610.35 Hz、带限 Gaussian arrow 激励与随机相位 odd multisine。附加 README 说明 Schroeder multisine，并指出去输出均值只是近似，因为系统自身也可能产生 DC。
- 许可/可取得性：已取得完整数据包并检查文件清单，未发现独立数据 LICENSE。免费下载的表述不能代替再分发许可；论文许可也不能自动授权数据。
- 借鉴建议：作为动态辨识方法/误差分析参考。保留连续记录、输入分布与同步信息，区分普通激励与外推子集；不能机械地对每条输出减均值，否则可能删去真实非线性偏置。
- 隐藏实验/负例建议：用新的 multisine 相位或可控幅值包络检出静态拟合、单一固定线性动态及输出反馈校正。这里公开数据已经固定，不能仅靠重命名这些记录得到保密隐藏实验，也不能主动调用未提供的真实装置。
- 适配缺口/未知：没有本次已核实的可运行 transistor netlist，不能作为采样级源。把离散采样点交给连续 VA 前，还需固定输入重构与采集滤波语义。此处没有做参数辨识或误差计算。

### 4. 官方 nonlinear_benchmarks dataloader 与提交模板

- 标题/owner/年份：`nonlinear_benchmarks`，Maarten Schoukens 仓库，代码版权 Gerben Beintema 2023–2024，当前检查版本于 2026-10-08 用 `git ls-remote` 固定为 [f9fb3883086870a27b31917ccde1f78c95d53cb2](https://github.com/MaartenSchoukens/nonlinear_benchmarks/tree/f9fb3883086870a27b31917ccde1f78c95d53cb2)。不能把检索日期当作 commit 日期。
- 路径与可取得性：已取得 [benchmarks.py](https://github.com/MaartenSchoukens/nonlinear_benchmarks/blob/f9fb3883086870a27b31917ccde1f78c95d53cb2/nonlinear_benchmarks/benchmarks.py)、[utilities.py](https://github.com/MaartenSchoukens/nonlinear_benchmarks/blob/f9fb3883086870a27b31917ccde1f78c95d53cb2/nonlinear_benchmarks/utilities.py)、[silverbox.py 提交模板](https://github.com/MaartenSchoukens/nonlinear_benchmarks/blob/f9fb3883086870a27b31917ccde1f78c95d53cb2/submission_examples/silverbox.py)、WH 模板与 README，副本在 `data-raw/loader/`。
- 事实：数据接口带 sampling_time 和 state_initialization_window_length。WH 取完整记录 `[5200:184000]` 后按前 100000 与剩余段切分；Silverbox multisine 按连续 75/25 切分。它们不是全部按独立新实验分组。两者当前模板允许仅用输入和测试输出首 50 点初始化，之后计算自由运行误差。Silverbox 三类分开报告，no-extrapolation 是 full arrow 的子集。
- 许可：[实际 LICENSE 为 BSD-3-Clause](https://github.com/MaartenSchoukens/nonlinear_benchmarks/blob/f9fb3883086870a27b31917ccde1f78c95d53cb2/LICENSE)，不是照搬某些 PyPI 元信息中的 MIT。代码许可不等于它下载的数据许可。
- 借鉴建议：本项目数据包显式带记录 ID、时间单位、输入通道、初始化区间、评分区间和可重建激励。首题优先源电路与 VA 共享可见前置历史，避免提供真实输出作初态估计；若以后允许前缀估计，长度和可使用方式需固定。
- 隐藏实验/负例建议：输出前缀只能初始化，不能重新训练参数；评分期输出不可反馈。通过同输入而不同前史、整段长运行和新独立记录，检出定期重置/teacher forcing。逐点随机切分负例不能成为正式协议。
- 适配缺口/未知：50 点没有跨电路的通用意义。不同规则下所得数字不得混报；当前工具不是 Spectre 的候选 VA checker，本次未执行其加载/评分函数。

### 5. Wiener–Hammerstein SYSID09 原始辨识合同

- 标题/owner/年份：`Wiener-Hammerstein benchmark`，Johan Schoukens、Johan Suykens、Lennart Ljung，2009 SYSID。
- 精确材料：[KTH 原始四页报告](https://people.kth.se/~hjalmars/ifac_tc11_benchmarks/2009_wienerhammerstein/IFAC-SYSID09-Schoukens-Benchmark.pdf)、[官方入口](https://www.nonlinearbenchmark.org/benchmarks/wiener-hammerstein)。论文由子 agent 实际读取；核查记录在 `data-raw/dynamic-primary.md`。报告无代码固定 revision；数据下载入口与下载器见第 4 项，本次未取得完整 WH MAT 数据。
- 事实：真实电子装置包含两个动态滤波块与中间二极管静态非线性。原协议从同一记录划出估计段 1–100000 与测试段 100001–188000；均值、标准差与 RMS 评分用 101001–188000，略去测试前 1000 点。仅用输入生成模拟输出，测试不能参与估计/选模。它没有把幅值/频段外推纳入原合同。
- 许可/可取得性：PDF 可读；独立数据再分发许可本次未核实。可读电路描述不等于已有可执行 Spectre 源网表。
- 借鉴建议：真值来源、激励生成、采集和评分协议应一起发布。记录段切分是原事实；本项目更严格的独立实验留出是设计建议，应明确区别。该原协议的 1000 点与第 4 项的 50 点不能互换。
- 隐藏实验/负例建议：以同频带而不同随机实现的输入验证动态结构，逐段检查偏差与频域残差。静态非线性拟合、只用一段 LTI 动态、测试集选模都需要检出。
- 适配缺口/未知：采样级还需要 clock、跟踪/保持阶段和事件时间指标；这篇连续电路基准不能单独规定这些。

### 6. 非线性系统辨识路线图

- 标题/owner/年份：`Nonlinear system identification: A user-oriented roadmap`，Johan Schoukens、Lennart Ljung，2019；[作者 arXiv v1](https://arxiv.org/html/1902.00683v1)。论文由子 agent 实际阅读，其核查记录在 `data-raw/dynamic-primary.md`。版本固定为 v1，后续发表版差异未逐项核对。
- 事实：讨论激励的频率/幅值覆盖、重复周期与不同相位实现、独立 validation，以及 prediction error 和 simulation error 的区别。一步预测借真实输出更新时，可以表现很好却在不反馈真实输出的模拟中失败。
- 许可/可取得性：作者全文可读，arXiv 为 perpetual non-exclusive license；不能当成数据集许可。它不是一个新的数据集或代码包。
- 借鉴建议：采样级宽带输入还需 clock 专项实验。分别改变输入幅值、变化率、跟踪时长、保持时长，避免所有量同时变化而无法定位状态效应。辨识结果只需满足用途，不必恢复唯一真实内部参数。
- 隐藏实验/负例建议：运行完整独立记录，包含同一输入值但不同历史、连续多拍及重启。负例为只优化一步预测、依赖测试输出修正状态、在新激励下漂移。
- 适配缺口/未知：路线图不给本题 VA 实现、误差门槛或 Spectre 设置。隐状态阶数与允许误差仍由实际数据和用途决定。

### 7. 2026 非线性辨识统一平台论文

- 标题/owner/年份：`Benchmarking for nonlinear system identification: Submission platform and baseline results`，Maarten Schoukens、Max Champneys、Gerben Izaak Beintema、Timothy James Rogers，Data-Centric Engineering 7, e40，2026-09-15；[发表页](https://www.cambridge.org/core/journals/data-centric-engineering/article/benchmarking-for-nonlinear-system-identification-submission-platform-and-baseline-results/BD06B2C87096B4A700EE173A298A0FEC)，[DOI 10.1017/dce.2026.10067](https://doi.org/10.1017/dce.2026.10067)，[发表版存档 PDF](https://eprints.whiterose.ac.uk/id/eprint/245745/1/benchmarking-for-nonlinear-system-identification-submission-platform-and-baseline-results.pdf)。子 agent 实际核查发表页与作者机构存档 PDF，详细来源在 `data-raw/dynamic-primary.md`。
- 事实：§3.2 统一输入输出表示与初态窗口；模型可以使用固定前缀 `u_ini,y_ini` 初始化，后续评分不用真实输出反馈。统一 RMSE 的协议与基线有助于避免各自选择有利切分。平台同时指出固定离线数据无法直接测试输入设计或主动学习，因为参与者不能调用真实系统。
- 许可/可取得性：发表版为 CC BY 4.0；基线代码/数据入口由作者网站与官方 dataloader 提供，本次没有运行其 baseline。
- 借鉴建议：固定数据阶段和主动表征阶段需要分别定义。前者所有参与者得到相同输入，后者才衡量 Agent 在调用预算内选实验的能力。不要把两种结果放在同一评分名下而隐藏不同的信息权限。
- 隐藏实验/负例建议：冻结测试访问权限与版本，禁止按隐藏误差调参。用过短初态段强迫模型失败、用过长初态段排除启动行为，均是待校准的协议负例。
- 适配缺口/未知：本题需电路用途指标，并显式检查采样事件，不能只因借用 RMSE 就称为完整电路模型验收。固定数据对主动表征研究的限制仍在。

### 8. 带过程噪声的 Wiener–Hammerstein 真实电路数据

- 标题/owner/年份：`Wiener-Hammerstein benchmark with process noise`，Maarten Schoukens、Jean-Philippe Noël；相关论文 `Three Benchmarks Addressing Open Challenges in Nonlinear System Identification`，IFAC 2017。[官方页面](https://www.nonlinearbenchmark.org/benchmarks/wiener-hammerstein-process-noise)，数据 [DOI 10.4121/12952124](https://doi.org/10.4121/12952124)。无本次固定数据 revision。
- 事实：主要过程噪声进入静态非线性之前，输入/输出测量通道还有较小噪声。官方说明 ZIP 包括信号生成指南、估计/测试/历史测量数据、装置照片和示意电路，CSV/MAT 可用；同时警告实际电路参数/运放可能与示意图不同。网站声明此基准尚未接入官方 dataloader 评分。
- 可取得性/许可：本次实际读到官方说明，但 DOI 访问返回 403，metadata 请求未成功，未下载 ZIP；不声称已检查其完整数据或许可证。数据许可未知。
- 借鉴建议：用于确定性题容差研究，提醒不能把所有误差当作独立输出白噪声。先看重复记录的输入条件、同步和噪声位置，再决定比较均值波形还是统计特征。
- 隐藏实验/负例建议：重复同激励的独立记录，检查模型是否学到可重复动态而非单次噪声；按幅值分组残差，检出把非线性内部噪声统一按输出噪声扣除的方案。
- 适配缺口/未知：首题优先确定性晶体管表征，不能直接用逐点单轨迹阈值扩展为随机噪声生成题。过程噪声资料适合阅读与容差设计，暂不推荐作第一个任务源。

### 9. CT-subnet 连续时间状态模型及作者代码

- 标题/owner/年份：`Continuous-time identification of dynamic state-space models by deep subspace encoding`，Gerben I. Beintema、Maarten Schoukens、Roland Tóth，ICLR 2023，预印本首次发布 2022。[作者预印本](https://arxiv.org/abs/2204.09405)、[作者机构发表版 PDF](https://pure.tue.nl/ws/portalfiles/portal/315058416/3099_continuous_time_identification.pdf)。作者代码固定为 [CT-subnet@fc4df7a2d630fce459c12cf558634a885a5e1c41](https://github.com/GerbenBeintema/CT-subnet/tree/fc4df7a2d630fce459c12cf558634a885a5e1c41)。
- 事实/可取得性：论文描述连续时间导数模型、子段自由运行损失、encoder 估初态与导数归一化。已实际取得 arXiv PDF 3,220,098 bytes、README、`encoder-CT-train.ipynb`、`encoder-CT-analysis.ipynb`，在 `data-raw/ct-subnet*`。作者 README 要求 deepSI 3.13，给出外部 426 MB 估计模型下载链接，本次未取得模型/运行环境，未训练。OpenReview PDF 被访问验证拦截，最终成功取得作者预印本。
- 许可：该固定仓库首页未展示许可证，根 LICENSE 请求为 404。只可确认为公开可读代码，重分发许可未核实；deepSI 的许可不能自动覆盖 notebook。
- 代码复核事实：CCT 的 `val, test = test[:len(test)//2], test` 使 validation 仍包含在 test 中；CED 先取每条记录 `[300:]` 作 test，再取其前 100 点作 val。analysis notebook 相同切分；另有根据 test NRMS 选择 `ibest` 的分析段。这些是所检查代码的事实，不推断作者其他结果都使用这些路径。论文另明确 EMPS 的 validation/test 是不重叠的，不能把前两项代码观察推广到全部实验。
- 借鉴建议：连续时间状态表示比固定采样差分方程更接近 VA 的时间语义，可作参考解方法阅读。论文 §3 明确要对样点间输入作附加假设，常用 ZOH；不能只给采样点而假定连续激励唯一。训练时可使用子段/encoder，最终仍需在完整隐藏输入下独立运行。不能直接照搬其研究 notebook 当严格独立的 task checker。
- 隐藏实验/负例建议：固定初态后改变可见输入时间安排，完整自由运行，观察长程误差；用子段重复初始化的解作负例。检查模型是否只是把训练采样率写死。谱系与数值条件的分析可以帮助作者选模型，但隐藏测试不得参与这种选择。
- 适配缺口/未知：论文实验对象包括非电子装置；没有 clocked sampler VA 转换。神经导数转成 Verilog-A、模型规模、Spectre 兼容性与稳定性都未验证，不能以论文结果承诺本题可行。

## 表征数据包与验收研究建议

以下均为本项目建议，未实施。静态 I/O 表可以辅助观察偏置或幅值边界，但本题训练输入必须保留状态、时间和 clock。

| 数据包内容 | 首题应给出的具体内容 | 需要防止的歧义 |
| --- | --- | --- |
| 接口合同 | 输入/输出、clock 极性和阈值、reset/启动语义、固定供电温度、固定 hold C 与适用范围 | 把瞬时采样的理想接口当作源电路行为 |
| 记录与时间 | `record_id,t,vin,clock,vhold`，单位、原始时间戳、评分窗口 | 随机打散时间点导致相邻状态泄漏 |
| 激励重构 | PWL/发生器定义，边沿斜率、时钟相位、源阻抗固定约定 | 把离散样点误认为连续输入唯一含义 |
| 初态 | 完整可见前置激励与每条记录是否独立启动 | 不同隐状态混在同一瞬时 I/O 条件中 |
| 来源身份 | circuit/PDK/仿真器固定版本、netlist hash、保存配置 | 用参考 VA 合成数据冒充真实电路表征 |
| 误差基础 | 源仿真数值配置对照；实测则重复记录和同步误差 | 未校准容差或用候选失败反向修改判据 |

首题训练实验至少要分别改变跟踪时长、输入电平/阶跃方向和前拍状态。是否加入保持下垂、开关注入或 clock feedthrough，取决于实际数据能否稳定观察。建议先用两类合理模型做可辨识性对照：瞬时采样加 pedestal 与有限建立状态模型。如果两类都能符合公开数据却在目标用途分开，应补公开实验；不能把不充分的数据当成更困难的隐藏测试。

隐藏实验按完整独立记录生成。先比较适用范围内的新序列与相位，再单列公开声明的外推范围。不能暗中改变 corner、温度或 hold C。每条记录的前置历史固定，评分阶段没有真实输出反馈。首拍/启动本身是目标时，必须另设相应窗口，不能全部放进不计分的初始化段。

建议的 checker 顺序为编译与完整运行检查、固定网格的电压误差、逐阶段工程指标和长连续记录。电压误差用预设绝对尺度；沿左右侧及局部窗固定，禁止按候选时间漂移重新对齐。采集结束误差、建立时间、规定沿后 pedestal、保持结束电压应独立给阈值，平静段不能稀释关键沿的错误。若参考 droop 不高于数值不确定性，不把它硬塞进指标。失败、未完成段、发散、NaN 保留在分母与失败清单中。

Spectre 终验运行候选 `.va`，真值来自固定原电路表征。若原电路只在 ngspice/Xyce 生成数据，这阶段只能声称跨仿真器的数据拟合；要求源 transistor 与 Spectre 行为对齐时，还需实际源移植/比对，当前未完成。不能用某参考 VA 与候选 VA 相互一致替代源电路证据。

主动表征是后续阶段建议。它需要冻结可调用原电路、可选实验范围、调用/输出预算和返回记录格式，并将每次实验记录留存。隐藏最终输入保持独立。在此之前，本次公开固定数据包仍是共同起点。主动选择实验的成绩不能归入“只给同一离线数据”的成绩。

## 三项推荐阅读

1. [采样开关与瞬态台架固定源码](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_tb_transient.sch)。先看实际可观察节点、inverter 和松容差设置，决定首题数据生成合同。
2. [Schoukens–Ljung 路线图 v1](https://arxiv.org/html/1902.00683v1)。重点阅读实验设计、simulation/prediction error 和独立 validation，检查公开数据是否支持要求的状态行为。
3. [官方 Silverbox 提交模板固定源码](https://github.com/MaartenSchoukens/nonlinear_benchmarks/blob/f9fb3883086870a27b31917ccde1f78c95d53cb2/submission_examples/silverbox.py)。对照 `benchmarks.py`，把初态可用输出、后续自由运行和子集关系落实到可检查的协议。

## 具体任务研究候选

| 候选，均为建议 | 输入与交付 | 隐藏实验与主要负例 | 尚需证据 |
| --- | --- | --- | --- |
| A，优先推进已定首题：从固定数据建立 transmission-gate 采样级 VA | 固定工艺/供电/温度/C 的真实表征包；交付独立 `.va`，映射 vin/clock 到 vhold | 新跟踪时长、不同前拍保持值、新 clock/input 相位、连续多拍；瞬时采样/固定 RC/每拍清零应分开 | 源仿真数值稳定性、公开输入可辨识性、至少两种正确实现与负例的 Spectre checker 校准；不能预先规定必有 droop |
| B，后续阶段：采样级主动补表征 | 在 A 的基础上给受预算限制的原电路调用接口；Agent 自选实验后交付 VA | 隐藏新独立记录；只重复低频正弦、把调用得到的输出逐点回放应失败 | 调用范围、预算、重复性与轨迹记录协议；必须与固定离线数据阶段分别报告 |
| C，非 ADC 备用后续题：真实 OTA buffer 启动与输入相关建立 | 固定 enable/bias/load；公开启动、小/大阶跃及恢复记录；交付连续时间电压 VA | 新方向/幅度组合、重启与饱和恢复；静态跟随/一阶固定 tau/只拟合启动应分开 | 新源表征与 Spectre 路径、稳定可见的非线性动态；不替换 A |

Silverbox/WH 更适合当方法、切分与负例设计材料。若另立数据驱动动态题，必须先核实再分发许可与连续输入语义。它们当前不具备采样级原电路可调用接口，故不作为本次首题替代。

## 检查与限制

本次读取既有 `runs/data-model-research-20261008/{checker-research,circuit-sources}.md`，检查 `git status -sb`，实际浏览一手网页/PDF，下载并查看固定版本源码、Silverbox PDF/ZIP 和 notebook。下载失败包括部分 DOI/metadata、OpenReview 验证和 GitHub API 限流，后两者分别改用作者材料与 `git ls-remote`，未宣称失败入口已成功。

没有运行电路、训练、评分、Spectre 或性能测量。文件 SHA-256 清单在 `data-raw/sha256.tsv`，论文复核详见 `data-raw/dynamic-primary.md`。文件的下载 hash 固定本次取得的字节，不等于提供了第三方材料的再分发授权。
