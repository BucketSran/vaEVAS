# 按规格构建模型：原始材料调研

核查日期：2026-10-08。仓库基线：`b86845e1ef80498a8eed708a56bed993f7a7f17c`。本报告只收集材料，未编译或运行模型，未启动 Spectre、EVAS、训练或电路仿真，也未验证原作者的性能结果。原始取回文件位于本机 `runs/benchmark-material-survey-20261008/spec-raw/`，不随研究笔记发布。本报告不构成可发布 benchmark。

本类包含按给定规格创建单模块、补齐固定工程的关键模块，以及在职责、接口和交互已固定时建立完整系统。建议题目提供电路行为合同，要求提交 VA 电压域模型，并用实际 Spectre 波形终验。下文“已读”是来源直接证据，“建议/推断”是任务改造想法，“缺口”是尚未解决的适配或复现条件。公开源码均不能直接当正确答案。

## 1. anlit75/ADPLL：固定分工的 ADPLL 工程

- 标题、作者、年份：All Digital Phase-Locked Loop；owner `anlit75`，许可证署名 Ting-An Cheng；当前核查版本为 2026 年。
- 精确身份：commit `57376b014d06dd0832eb8f17906d681f09c9a097`；本地 `spec-raw/anlit75_ADPLL-commit.json` 和 `-tree.json` 保存 GitHub API 身份与文件树。
- 已读：[README](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/README.md) 的架构与规格段；[DCO.v](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/DCO.v) 的端口、周期 case 表与末尾翻转；[CONTROLLER.v](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/CONTROLLER.v) 的职责注释和控制过程；[FILTER.v](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/FILTER.v) 全文。
- 实际资产：Verilog 行为 DCO、PFD、控制器、滤波器、分频器、顶层与测试文件，以及 HSPICE DCO/PFD 网表。控制器描述方向反转后步长减半；DCO 以多位码选择周期后按半周期翻转。来源具有系统各模块分工，适合学习闭环建模。[文件树](https://api.github.com/repos/anlit75/ADPLL/git/trees/57376b014d06dd0832eb8f17906d681f09c9a097?recursive=1)
- 许可证：已读 [MIT LICENSE](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/LICENSE)，要求保留版权和许可声明。
- 建议工程动作：给定 PFD、控制器、分频职责与明确码频映射，要求编写电压端口 DCO 或整个 ADPLL 的 VA 模型。独立 checker 从输出过零时间计算周期、跟踪参考阶跃后的频差与相差，而非只检查作者的 lock 信号。
- 缺口：源工程以 Verilog/HSPICE 实现；需重新规定模拟电压阈值、复位、换码时的相位连续性。当前 DCO 接收 RESET，但所读振荡过程没有复位分支；周期表含部分非标准温度计码。不能照搬作为规范。没有在本调研运行其测试，README 的锁定/抖动指标未复现。[DCO.v](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/DCO.v)

## 2. Lauwers 等：开关电容低通滤波器的分层规格

- 标题、作者、年份：High-level design case of a switched-capacitor low-pass filter using Verilog-A；Erik Lauwers、Koen Lampaert、Paolo Miliozzi、Georges Gielen；BMAS 2000。[作者论文 PDF](https://bmas.designers-guide.org/2000/papers/bmas00-lauwers.pdf)
- 已读位置：第 1–2 页的系统拓扑和 §3 的运放参数；第 3–4 页的压摆、饱和恢复与开关非理想；第 5 页 §4 表 1。论文提供一阶全差分 SC 滤波器、Miller 运放/开关宏模型设计说明、连接图、局部 VA 语句和结果表；此次没有发现完整可下载工程或完整 VA 文件。
- 已读证据：模型从 GBW、增益、压摆率、相位裕量、偏置与负载等参数构建；开关考虑馈通、信号相关导通及通道电阻。论文解释输出阻抗与周边开关之间的作用，适合从系统规格反推子模块合同。[§3](https://bmas.designers-guide.org/2000/papers/bmas00-lauwers.pdf)
- 许可证：未查明论文代码的独立许可；公开阅读不等于可复制/分发。
- 建议工程动作：提供已固定的两相 SC 采样与电容比，要求补齐有限增益、单/双极点、压摆及输出限幅的运放模型。checker 独立计算小信号增益、稳态极点、阶跃压摆斜率、采样后残差；系统侧检查滤波极点和输入幅度依赖。
- 缺口：原模型包含电流、负载与开关物理作用，电压域实现必须限定负载合同，不能声称复现全部电路行为。原文讨论的收敛和耗时只作为历史背景，不改造成任务。未复现作者曲线。[§3–4](https://bmas.designers-guide.org/2000/papers/bmas00-lauwers.pdf)

## 3. Sobot 等：固定反馈脉冲形状的 CT ΔΣ 系统

- 标题、作者、年份：Behavioral modeling of continuous time ΔΣ modulators；Robert Sobot、Shawn Stapleton、Marek Syrzycki；BMAS 2003。[原论文 PDF](https://bmas.designers-guide.org/2003/papers/bmas03-sobot.pdf)
- 已读位置：第 1 页总体环路；第 2 页 §II A–D；第 3 页 §II E–G 和 §III；第 4 页图 6、8、9。实际资产是架构图、局部 VA 代码、CT 传递函数、NRZ/RZ/HZ 反馈脉冲设计及谱图，没有核查到完整发布工程。
- 已读证据：电压积分器和通用滤波器使用 laplace_nd；量化器由比较器/DFF 构成；DAC 输出使用 transition；加法器和增益块使用 absdelay。论文用一阶低通与四阶带通闭环讨论反馈延迟和时钟抖动。[§II–III](https://bmas.designers-guide.org/2003/papers/bmas03-sobot.pdf)
- 许可证：未查明代码片段的独立许可。
- 建议工程动作：限定一阶 CT 架构、采样时刻、反馈符号、NRZ/RZ 占空比及环路延迟，要求补齐积分器、采样量化器与反馈 DAC。checker 依据每段恒定输入的积分面积和每周期脉冲面积建立独立状态递推，检查比特流和内部状态；谱指标作为补充验收。
- 缺口：论文未覆盖所有 z 域到 s 域映射推导。若设四阶任务，应另给可核验系数与初值；不能仅以视觉接近原图判断正确。本次未运行模型、未复现 SNR 或抖动结论。[§II B、§III](https://bmas.designers-guide.org/2003/papers/bmas03-sobot.pdf)

## 4. Spiazzi、Buso、Tagliavia：flyback 宏模型的状态与接口

- 标题、作者、年份：Verilog-A behavioral modeling of power converters；Giorgio Spiazzi、Simone Buso、Donato Tagliavia；作者机构文件位于 2001/Cobep 目录，PDF 页码 743–748，年份按该目录标记 2001。[Padova 作者机构 PDF](https://www.dei.unipd.it/~pel/Articoli/2001/Cobep/Cobep01_1.pdf)
- 已读位置：§II 的控制器图 2–3；§III 的模型状态说明；最后一页 Appendix A 完整 `FLYBACK(inp, inn, outp, outn, B, G)` 源码。PDF 已下载并用 pdftotext 阅读，保存在 `spec-raw/flyback.pdf` 和 `flyback.txt`。
- 实际资产：电路和控制框图、磁化电流积分的状态方程、CCM/DCM 转换说明、完整 VA 附录及仿真波形。输出电容在宏模型外部；模型通过门极电压和基极电流阈值确定开关态，DCM 时电流钳至零并复位积分。[§III、Appendix A](https://www.dei.unipd.it/~pel/Articoli/2001/Cobep/Cobep01_1.pdf)
- 许可证：未查明独立源码许可。
- 建议工程动作：从同一状态职责学习“电压编码磁化电流”的建模题，固定磁化电感、匝比、驱动波形与输出电压输入。checker 分段解析积分，检查电流斜率、零电流平台和再启动。
- 缺口：源代码使用 I(B) 与电流贡献，原样不属于 VA 电压域；如果屏蔽端口电流，要明确这是受限状态模型，不是可接任意负载的电源。原文的仿真提速目的不纳入题目。未复现原作者系统结果。[Appendix A](https://www.dei.unipd.it/~pel/Articoli/2001/Cobep/Cobep01_1.pdf)

## 5. Ken Kundert / Designer's Guide：振荡相位和电源边界的短模型

- 标题、作者、年份：Voltage controlled oscillators，Ken Kundert，源文件版本 2，2019-04-02；Current limiting voltage regulator，文件未写作者或年份，发布者为 Designer's Guide。
- 已读精确文件：[vco.va](https://designers-guide.org/verilog-ams/functional-blocks/vco/vco.va) 的 `vco0` 及 `vco1` 起始段；[regulator.va](https://designers-guide.org/verilog-ams/functional-blocks/regulator/regulator.va) 全文。网页无 commit，需未来复现时固定下载哈希。
- 实际资产：VCO 模型及 [VCO 测试文件](https://designers-guide.org/verilog-ams/functional-blocks/vco/vco.scs) 的网站链接；限流稳压器与 [测试链接](https://designers-guide.org/verilog-ams/functional-blocks/regulator/regulator.scs)。测试仅从目录链接识别，此次未读取或执行。`vco0` 对频率限幅，再积分成相位；regulator 在电压驱动与电流驱动间切换。[模型目录](https://designers-guide.org/verilog-ams/index.html)
- 许可边界：目录 Terms & Conditions 仅允许满足条件的个人/课堂复制；其他发布、服务器张贴及分发要求作者预先书面许可，不能直接打包进公开任务。[条款](https://designers-guide.org/verilog-ams/index.html)
- 建议工程动作：用频率范围、控制增益和换频时相位连续的文字规格，独立编写 VCO/DCO。checker 积分输入频率，并测过零时刻与相位误差。稳压器只作为电流/电压接口边界的学习材料。
- 缺口：VCO 的 idtmod 支持需单独确认；regulator 有端口电流与拓扑切换，不能原样用于电压域。未检查作者测试或运行模型。

## 6. AnalogHub / A. Sidun：VCO、低通和非交叠时钟

- 标题、作者、年份：`analoghub-ie/software` 的 Verilog-A 示例；文件署名 A. Sidun；具体创建年份未核查，最新核查 commit 日期为 2026-03-29。
- 固定身份：`33a495131027283f22c51ca423f1aed0aa1ae98e`；已保存 API commit 与 tree。已读 [vco1.va](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/vco1.va)、[LPF.va](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/LPF.va)、[nonoverlap_clk_2ph.va](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/nonoverlap_clk_2ph.va) 全文。
- 实际资产：电压 VCO、laplace_nd 一/二阶滤波器、cross/transition 两相时钟。时钟代码在连续输入上升沿间交替两相，属于分频输出，不是对每个输入半周期直接生成同频两相。[时钟文件](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/nonoverlap_clk_2ph.va)
- 许可证：核查固定文件树没有 LICENSE/COPYING 类文件，文件头只有作者/来源；分发许可未查明，不能从 public 推断允许复用。[文件树](https://api.github.com/repos/analoghub-ie/software/git/trees/33a495131027283f22c51ca423f1aed0aa1ae98e?recursive=1)
- 建议工程动作：固定两相时钟频率、死区及启动协议，要求按规格构建，checker 测输出边沿、占空比和任一时刻双相是否同时高。滤波器可按解析频响与阶跃响应验收。
- 缺口：LPF 一阶分支确有重复同一 V(out) 贡献，按贡献相加语义推断其增益不符合通常单位直流增益的 LPF；二阶两个相同实极点也不使该参数天然等于 -3dB 点。以上为静态推断，未仿真验证。VCO 负频率边界没有限制。[LPF.va](https://github.com/analoghub-ie/software/blob/33a495131027283f22c51ca423f1aed0aa1ae98e/Verilog-A/LPF.va)

## 7. Brian Li / verilogaLib：CTLE 和 PFD 电压模块

- 标题、作者、年份：Library of Verilog-A models；owner `ShabbyGayBar`，MIT 署名 Brian Li，版权 2025；核查 commit 为 `a6cdb37055a811ee47d435ebfd4d0f4a0d298a09`，日期 2026-10-08。
- 已读：[ctle.va](https://github.com/ShabbyGayBar/verilogaLib/blob/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09/ctle.va) 全文；固定 [文件树](https://api.github.com/repos/ShabbyGayBar/verilogaLib/git/trees/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09?recursive=1) 确认有 CTLE、PFD、理想 ADC/DAC、编码器、DFF、电压控制电阻。PFD 只确认文件存在，未读取实现，不对其行为作判断。
- 实际资产：CTLE 以零点和两个极点参数调用 laplace_zp 并驱动电压输出。文件注释说明 Hz 转 rad/s。[ctle.va](https://github.com/ShabbyGayBar/verilogaLib/blob/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09/ctle.va)
- 许可证：已读 [MIT LICENSE](https://github.com/ShabbyGayBar/verilogaLib/blob/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09/LICENSE)，复用需保留声明。
- 建议工程动作：给定单位直流增益、零极点、峰值增益上限和初始状态的 CTLE 模型题；checker 独立计算复数频响，再用多正弦幅相和阶跃瞬态核对，可加入限幅作为明确的非理想规格。
- 缺口：当前文件使用 `gain` 而未见声明，源码不能直接作为答案；laplace_zp 的增益归一化也应重新定义。搜索缓存列出的动态放大器/比较器在当前树中不存在，不能引用它们为现有可用资产。未编译或模拟。[固定 ctle.va](https://github.com/ShabbyGayBar/verilogaLib/blob/a6cdb37055a811ee47d435ebfd4d0f4a0d298a09/ctle.va)

## 最值得先学习的三项

1. **SC 滤波器论文**。先读 §3 中从运放规格到状态、输出阻抗及饱和恢复的解释，再读 §4 的系统指标。这能帮助把“指定非理想”写成可测行为，而不是只列参数名。电压域版本应主动缩小负载合同。[原论文](https://bmas.designers-guide.org/2000/papers/bmas00-lauwers.pdf)
2. **ADPLL 工程**。先读控制器职责、DCO 周期表及 FILTER 的事件/计数关系。学习的是系统接口和反馈职责；原源码还需校核，锁定不能仅听取内部标志。[固定控制器](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/CONTROLLER.v)
3. **CT ΔΣ 论文**。先读 §II 的采样、积分、延迟和反馈脉冲，再读图 4 和图 6。它适合训练“按固定架构建立动态系统”，其中脉冲面积与时序也是规格的一部分。[原论文](https://bmas.designers-guide.org/2003/papers/bmas03-sobot.pdf)

## 三个任务想法，均为建议

| 建议任务 | 提供给求解者的规格和工程 | 求解动作 | 独立验收与终验 | 尚需解决 |
| --- | --- | --- | --- | --- |
| 规格 DCO 补入固定 ADPLL | 提供已校验 PFD/控制器/分频器及明确码频函数、启动、复位、换码相位协议 | 从空壳编写 DCO，满足频率范围与连续相位；不要求照搬原表 | 对恒码、随机换码的解析相位积分验收；闭环参考阶跃测实际频差和周期序列；实际 Spectre 终验 | 固定合法码、极限状态、lock 条件；不能把数据拟合藏在本类中 |
| 指定非理想的 SC 运放模块 | 固定滤波拓扑/时钟/电容比，给增益、主极点、压摆率、限幅及恢复时间合同 | 工程内补齐运放 VA；保留模块职责和连接 | 独立连续状态模型检查斜率和恢复，再核对采样递推及滤波极点；实际 Spectre 终验 | 若不支持真实电流负载，改成明确单向电压合同；电容和开关行为需先有独立参考 |
| 固定一阶 CT ΔΣ 系统建模 | 提供积分器增益、比较阈值、时钟、NRZ/RZ 反馈幅度/面积、传播延迟和初态 | 创建积分器、量化/DFF、反馈 DAC 和求和器；不得换架构 | 对分段输入/反馈精确积分，检查状态和比特流；固定谱分析作为补充；实际 Spectre 终验 | 规定事件同时发生的优先级、过零容差、输出量化以及延迟历史 |

这些题目的分类取决于主要缺失内容。如果只是已有实现接线，属于“扩展与集成”；如果起点已有错误实现并要求找错，属于“诊断与修复”；若给出数据要求拟合码频曲线，属于“从数据建立模型”。上述建议只把关键行为规格作为输入，主要产物是新模型。

## 核查限度与原始材料

- 所有来源核查日期统一为 2026-10-08。GitHub 来源固定 commit；网页/PDF 尚无版本哈希合同。
- `spec-raw/` 留有三仓库 commit/tree JSON、实际成功下载的文件和 flyback PDF/提取文本。部分原始下载返回 403 或长时间无响应，但网页工具已实际读取所引用的对应代码或 PDF 段落；本地未缓存不代表未读。VCO/regulator 测试文件未读。
- flyback 的浏览抓取曾超时，后通过作者机构 URL 成功下载并阅读 Appendix A。SC 与 CT ΔΣ PDF 由网页工具读取；没有重新分发其正文。
- 未查到明确、质量足够且适配电压域的独立 bandgap/LDO 或 TDC 完整原工程。本报告没有以论坛建议或搜索摘要补足这一空缺。稳压器和 flyback 作为边界材料，优先落地仍是 DCO/PLL、滤波器与 CT ΔΣ。
- 此次只有材料核查，没有“模型通过”“与 Spectre 对齐”或“可直接发布”的结论。论文结果是作者报告；checker、任务切分和适配动作是本报告建议。
