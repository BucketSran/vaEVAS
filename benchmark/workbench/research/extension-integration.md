# 扩展与集成材料调查

2026-10-08；仓库参考 base `b86845e1ef80498a8eed708a56bed993f7a7f17c`。本专题只收集、读取材料，没有运行任何仿真。GitHub 文件通过官方 API 固定 HEAD 后读取 raw；副本及完整文件树在本机 `runs/benchmark-material-survey-20261008/integration-raw/<owner>/`，`metadata.json` 记录 repo、commit、提交日期。网页快照取得情况见 `integration-raw/web-snapshots.json`。论文日期不能用搜索引擎 crawl 日期代替。

## 选材结论与边界

本轮保留 8 项，重点是 PLL/DPLL 的真实反馈、部件状态与端到端动态，兼顾 SAR 和 CDR。两项提供数字 ADPLL 工程，三项提供 VA 部件或多模块示例，两项提供 SAR VA，另有一篇 DPLL 论文。公开可读不等于允许发布为 benchmark，下面分别记录许可。

现成 VA 的数量比搜索结果标题暗示的少。ADPLL Verilog、SystemVerilog 测试及 Python 传递函数只能作为架构、时序和指标参考，需要明确 VA 电压域适配。没有查到可以直接保留全部部件并称为已验证 Spectre ADPLL 的公开工程。本轮也没有为任何来源复现作者成绩。

已读历史 `runs/extension-integration-research-20261008/heavy.md` 和 `original-and-proposal.md`。可复用的是两种集成形式：现成部件组装，及新增部件接入旧工程并按题面修改旧模块、连接或参数。题面应规定保留的原行为。历史 CVDP 的宽松断言、日志式验收不能原样移植。已有故障顶层应先修为健康基线，否则主要考的是诊断修复。

## 1. Designer's Guide 的 PLL 功能部件库

**事实与读取。** Ken Kundert；PFD/CP `Version 1e, 3 August 2010`，VCO `Version 2, 2 April 2019`；分频器署名 Ken Kundert、Hua Li，`Version 1d, 16 June 2024`。官方[目录及使用条款](https://designers-guide.org/verilog-ams/index.html)，实际读取 [pfd_cp.va](https://designers-guide.org/verilog-ams/functional-blocks/pfd_cp/pfd_cp.va) 行 21–54、63–105，[freq-divider.va](https://designers-guide.org/verilog-ams/functional-blocks/freq-divider/freq-divider.va) 行 18–40、51–80，[vco.va](https://designers-guide.org/verilog-ams/functional-blocks/vco/vco.va) 行 18–84、92–134。已在 web 工具成功阅读；直接下载收到 403，因此没有假称 raw 文件已落盘。PFD 测试链接 `.scs` 也未读到。

**资产与原工程动作。** 都是真实 VA 部件，PFD 边沿改变三态状态，charge pump 输出电流；divider 计输入边沿，VCO 把控制电压转为频率并积分相位。提供有/无 jitter 的成对实现和测试入口，适合学习新增非理想行为如何保留无 jitter 模式。条款准许个人/课堂非商业复制；重新发布、放服务器或其他分发需作者书面许可。不能视为宽松开源资产。

**改题建议。** 依文档独立实现电压输出的 PFD、环路滤波器、VCO、divider，然后组装闭环或接入可配置 divider。明确 CP 电流形式需要电压域等效模型，不能直接把这个 CP 当纯电压域部件。

**独立 checker 与复用。** checker 从参考、输出、反馈节点的跨阈值时间求频率比、相差、锁定时间和重锁定，另做开环 PFD 极性与 divider 比率核查。隐藏改变 VCO 增益及初相位，确保输出依赖真实回路。复用约束需要固定部件散列、连接检查，并由注入扰动的动态检查证明反馈路径发挥作用。

**坑与未知。** `ratio>=2`，奇数分频 duty 不等于恰好 50%；CP 电流符号取决于端口电流方向。同步 jitter 与 VCO 累积 jitter 不可混称。未检验初始化、同刻双边沿、Spectre/EVAS 兼容性或闭环参数。

## 2. SIMetrix 的三模块 VA PLL 教学

**事实与读取。** SIMetrix Technologies / SIMPLIS 官方 [Phase-locked Loop](https://www.simplistechnologies.com/documentation/simetrix/verilog_a_reference/topics/writingverilog_acode_phaselockedloop.htm)，未标原始年份，2026-10-08 读取。实际读取网页行 1590–1687 的完整代码；HTML 已存 `integration-raw/simetrix-pll.html`，SHA256 在 manifest。

**资产与原工程动作。** 顶层实例化 multiplier phase detector、RC 一阶 filter、`idtmod` VCO，各自传参。它展示如何把三个已有 VA 模块接成子系统。顶层 `phase_detect_in` 是外露检测输入，调用工程须把本地振荡信号接回此端；顶层没有自行连接该反馈。官方页脚 All Rights Reserved，没找到代码分发许可。可学习，不能直接认定可发布代码包。

**改题建议。** 给定独立编写且已验证的三个等效 VA 部件，要求补系统连接及新增 N 分频反馈；允许改顶层、divider 和规定参数，保留 N=1 原行为。带外露回路输入的原示例不能当已经闭合的基线。

**独立 checker 与复用。** 先用滤波器阶跃时间常数和 VCO 开环 f(V) 定标，再比较完整回路的稳态比率、捕获、参考频率阶跃。改变外部 feedback 的相位并测响应，避免只产生输入频率倍数的伪系统。固定滤波器和 VCO 部件，允许明示适配。

**坑与未知。** 乘法鉴相是模拟 PLL，不是 PFD/TDC ADPLL；锁点可能有相偏，不能要求所有 PLL 相差为零。原页面出现 `'M_PI` 等写法，移植必须核对宏语法。没有 divider 或测试网表的完整 Spectre 复现。

## 3. Ting-An Cheng 的 ADPLL 课程工程

**事实与读取。** Ting-An Cheng / `anlit75`，2026，MIT。[固定仓库](https://github.com/anlit75/ADPLL/tree/57376b014d06dd0832eb8f17906d681f09c9a097)。实查 `05_ADPLL/ADPLL.v`、`CONTROLLER.v`、`FILTER.v`、`DCO.v`、`TEST.v`、`DCO.sp`、`PFD.sp` 和 LICENSE；全部在 raw 目录。原工程用 Verilog 行为模型与 SPICE 晶体管文件设计 PFD、controller/filter、DCO、divider。

**资产与原工程动作。** 是多模块数字/混合信号架构材料，不是 VA。Controller 依据方向调 DCO code，方向变化减小步长；FILTER 在锁定后计同方向事件。README 报告行为/AMS 仿真及频率、jitter，但本轮未独立验证。

**实际问题。** [ADPLL.v 行 75–82](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/ADPLL.v#L75) 的 divider 输入是 `REF_CLK`，不来自 `OUT_CLK`。`freq_lock` 依步长是否为 1；TEST 扫周期和 M，但没有读出频率正确性断言。FILTER 的组合块自增/自保持和 controller default 数字写法还有静态可疑处。这里只报告源码事实及风险，不声称已经编译失败。

**改题建议。** 先独立建立正确、可复现的 VA 基线，再设计从粗搜索接入 fine TDC/PI 跟踪，或接入可编程 divider。不能把修错反馈线直接叫扩展集成。MIT 可用于仓库代码，工艺相关 SPICE 依赖与第三方资产仍需另核查。

**独立 checker 与复用。** 不以 LOCK 为最终 oracle；从 OUT_CLK/FB 测比率及相位。随机初码、参考阶跃、divider 切换，比较 coarse-only 模式保留行为和 fine 模式相差范围。固定 DCO 模块与端口，隐藏改变 DCO 表/增益以证明新模块确实影响回路。原 TEST 不宜直接作为评分器。

## 4. Tiny Tapeout 的量化 DCO 加 PI 回路

**事实与读取。** Govardhana Kondapaturi / `SriKondapaturi`，2026，Apache-2.0。[固定仓库](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/tree/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2)。实查 `src/project.v`、`src/dco.v`、`test/test.py`、README、LICENSE。作者称 Tiny Tapeout SKY26c tapeout；本轮未查硬件测量，不能写成已测硅片性能。

**资产与原工程动作。** Verilog 回路用 DCO 域 Gray counter，经参考域同步后在 16 周期窗口统计振荡次数，再由饱和 PI 产生 10 位调谐字。锁检测累计四窗口误差，再连续八组确认。DCO 仿真仅用高四位，16 个频率档；硬件是标准单元 ring 和 tap mux。属于粗频率计数反馈，不是高分辨率边沿 TDC；没有证据证明绝对相位锁定。

**原验收与坑。** [test.py](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/test/test.py) RTL 验 N=4 再 N=3，频率容差 2 MHz；门级分支只检 oscillation。DCO 行为频率约 16.7–46 MHz，与 UI 接受 N=1..63 不是同一可达范围。锁定后的 retune 可能读到尚未清除的旧锁旗。锁检测用组误差的绝对值，不是组内绝对误差均值，正负可能抵消。

**改题建议。** 用其离散环路契约独立编写电压域 VA 部件，已有 count/coarse loop 上接 fine TDC 或 reset/retune 资格判定部件。题目明确控制更新延迟、饱和及可达 N，不把 RTL 数字模型称现成 VA。

**独立 checker 与复用。** 单独检查窗口计数与跨界 modulo，再从输出边沿验证频率、相位、锁旗真实性及 retune 撤销旧锁。保留原 coarse 模式；新增模块使用内部误差与 DCO 控制连接，输出黑盒结果不能替代。Apache 许可比前两项易复用，但需要保留 notices，并重新确认模拟环振与数字 delay 的适配。

## 5. DVCon 的 PFD/TDC/DLF/DSM 多阶段 DPLL

**事实与读取。** Biju Viswanathan、Rajagopal P.C、Ramya Nair S. R、Joseph J Vettickatt、Jobin Cyriac；Network Systems and Technologies。官方 [An Effective Design and Verification Methodology for Digital PLL](https://dvcon-proceedings.org/wp-content/uploads/an-effective-design-and-verification-methodology-for-digital-pll.pdf)。PDF 本文没有确认出版年份，检索日期不代表出版年。web 成功读取 8 页文本，重点 P1–P4 图1–4及 P5–P7；直接下载 403，未保存 PDF。未找到公开源码或宽松许可。

**资产与原工程动作。** 论文架构由 PFD、双向 TDC、controller、digital loop filter、DSM、DCO、12 位 divider 组成。coarse/fine 搜索先关闭 DSM，后进入 fractional 搜索，再用 TDC 做 phase tracking。滤波器对已有八个码加两个新码去掉最大最小值，生成基准码。论文采用数字模型和最终 co-simulation；不是完整公开 VA 工程。

**改题建议。** 作为 TDC/PFD/DSM 的接口与模式切换材料。在预制 VA integer/coarse PLL 中新增 fractional DSM 或 fine TDC，题面给出允许修改 controller/filter 的范围，指定关闭新增模式时保留原整数锁定行为。不纳入其加速仿真目标。

**独立 checker 与复用。** 使用独立离散状态模型检模式顺序、DSM 平均码和饱和，再在 Spectre 从波形验平均倍频、频率阶跃和锁后相差。需要同时检查内部控制码与外部边沿，不能仅 DSM 均值正确。事实中的 19/10/9 位接口可作例子，不等于本题规格已确定。

**坑与未知。** 摘要的频率范围和正文表格不完全一致；文中 DCO 码增大使频率降低，不能默认正 Kvco。没有开源作者测试器、原 PDK 或可复现 signoff 数据。性能容差和新 VA 基线都需独立建立。

## 6. Virginia Tech 的 split-CDAC SAR 工程

**事实与读取。** Victor Velasquez Fonseca / `vonfel`，ECE5404，Spring 2026。[固定仓库](https://github.com/vonfel/Split-CDAC-Asynchronous-SAR-ADC/tree/9ab0f9786b69ca9ac2fd1fac0bb37cec27552a96)。实查 `cadence/veriloga/sar_logic_async.vams`、`comparator.vams`、`rtl/sar_fsm.sv`、`sar_fsm_tb.sv`、`python/split_cdac_model.py`、README。文件树只有 schematic/结果图片，没有完整顶层电路网表；本轮未读取图片，因此未核对真实电容连接。未发现 LICENSE。

**资产与原工程动作。** 控制器虽扩展名 vams，实际是 electrical/analog VA；时钟上升采样、下降试 MSB，然后每个 T_bit 读 COMP 并推进位码。公开 comparator 是增益加 rail clamp 的静态模型。数字 FSM 和 Python CDAC 是辅助材料。

**源码与描述差异。** README 称 comparator-valid self-timed，实际 VA 控制器按固定 timer，没有 valid 端。比较器没有锁存恢复或有限判决延迟。Python 直接计算 V(code)，不是端到端 SAR 仿真；所谓 endpoint INL 没在计算式中作端点拟合。SV testbench 的末尾通过/失败打印不能当严格评分。

**改题建议。** 给定已正确工作的 fixed-T_bit 电压域 SAR，接入有有限 settling 的 DAC 与带 VALID 的 comparator，修改 SAR 为握手推进，保留采样相位及原固定时序模式。样本同时覆盖新增部件与允许修改旧控制器。原代码发布许可未知，宜独立实现。

**独立 checker 与复用。** 输入在 hold 后跳变，检查本次码仍对应旧样本；独立重建每个试码和比较结果，检查 valid 到达前不推进；扫两种 DAC settling 和 comparator latency。最终量化误差按选定 DAC 的实际阈值计算，不能一概用理想 1 LSB。固定 S/H、DAC 契约，黑盒扰动证明真的取反馈，不接受直接 floor(Vin/LSB) 输出。未知项包括动态 timer 修改的 Spectre行为、split-CDAC 电荷守恒、真实拓扑及 ADC 全码性能。

## 7. IIT Dharwad 的 9-bit SAR 与 DAC VA

**事实与读取。** Veenadhar / `Veenadhar-10`，2026 commit，README 未标课程年份。[固定仓库](https://github.com/Veenadhar-10/9bit-SAR-ADC-Cadence/tree/0f0a39dfc06e2a68da28303156e7565fcedbb059)。实查 `verilog_A/sar_logic.va` 和 `dac_9_bits.va`；不是 README 写的 `verilogA` 目录。文件树有 schematic PNG 和 slides，但没有公开整机网表或 checker。未发现 LICENSE。

**资产与原工程动作。** VA controller 按 start 和 clk 边沿逐位试码，经 comparator 决策输出 DAC 位，DAC 用权重解码输出 VREF*code/512。作者称用 SCL180 与 Spectre 集成 S/H、StrongARM、CDAC，相关模拟电路只有图片，本轮未核对图片与源代码。

**关键坑。** [sar_logic.va 行60–69](https://github.com/Veenadhar-10/9bit-SAR-ADC-Cadence/blob/0f0a39dfc06e2a68da28303156e7565fcedbb059/verilog_A/sar_logic.va#L60) 用 code 范围判断 d7..d1，没有按位掩码；例如 code=384 时 d8=1、d7=0，输出不是384。初始化 bit=8 即允许未 start 的时钟作决策。缺少忙状态/重复 start 规则，不能直接当健康集成基线。

**改题建议。** 作为小型系统接口教材，或交给诊断修复类；若要扩展集成，先独立重建健康 VA 基线，再加入双输入选择/S/H 或输出缓存，允许改 controller 与连接，保留原单输入转换。独立 checker 从已保持输入、DAC 阈值和九次比较求码，并验证 start/EOC/旧码保留；复用 DAC 且改变 VREF 可测真实连接。无授权、无独立 oracle、无动态仿真证据，优先级低于来源6。

## 8. YiDingg 的 SerDes VA 与 CDR 检测器作者笔记

**事实与读取。** YiDingg，首篇标2026-02-04，CDR 笔记含2026-02仿真记录。[固定仓库](https://github.com/YiDingg/YiDingg/tree/38a2f2b0f1861a27229f6f9a18036c76758e59a4)，实查 `AnalogIC/Verilog-A Modeling for Commonly Used Modules of SerDes and Wireline.md` 的 MUX2/SRL/VCO 完整代码，及 `Overview and Verification of CDR Phase and Frequency Detectors.md` 的 Hogge/Alexander、辅助 FD 和相差/频差曲线描述；本轮未读外链图片。

**资产与原工程动作。** 前文实际给出逻辑/MUX/latch 和 VCO VA，作者改过输出边沿形状及 jitter 更新机制，并记录跨模块名称解析问题。PLL/DLL 标题为空，不能当完整 PLL 资产。CDR 文描述作者用 VA 验检测器及双向频率捕获，没有找到完整 CDR 源和 testbench。仓库 LICENSE 是 Apache-2.0；文中借用 Designer's Guide代码和第三方论文图，不能把仓库许可扩大覆盖这些资产。

**改题建议。** 用独立编写的 VCO、采样器和 Alexander PD 作为旧 CDR，接辅助 frequency detector 和 acquisition/tracking 控制，允许修改 loop filter 与模式开关。保留近锁定旧 phase tracking，新增频差捕获。这里的 VA 部件较零散，完整电路与状态契约需要出题人补齐。

**独立 checker 与复用。** 使用固定及隐藏 PRBS，分别从正负频差启动，检测采样相位、长跑 bit error、cycle slip 和模式切换；只看 recovered clock 平均频率不能证明 CDR。改变数据转移密度及 VCO 初相位，证明 PD/FD 都参与反馈。无转移片段按规格 holdover，不能要求 PD 在任意数据上都捕获。作者对 PD/FD 的曲线是学习参考，不能代替 Spectre终验。

## 优先学习的三个来源

1. **来源4 Tiny Tapeout**。许可清楚、完整闭环和测试可读，可学习窗口误差、饱和 PI、量化 DCO、锁资格及原测试限制。把“counter detector”与“fine TDC”区别讲清楚。
2. **来源1 Designer's Guide**。VA 部件接口、边沿事件及 jitter 分类清楚，适合搭建电压域等效模型；作为学习材料，分发必须另处理许可。
3. **来源5 DVCon DPLL**。最适合学习从 coarse acquisition 到 fractional/fine tracking 的模块交互；公开架构可用，代码及实现证据需要独立补齐。

来源6是优先 ADC 补充，可学习 sample/trial/compare 交互，但 valid/timer差异和拓扑资产缺失要保留在笔记里。来源3、7的明显缺陷说明“漂亮 README + 结果图”不足以认定系统基线正确。

## 三个候选任务建议，尚未建题

| 候选 | 给定健康起点与实际工程动作 | 允许修改与必须保留 | 独立验收 |
| --- | --- | --- | --- |
| integer PLL 接入 fine TDC tracking | 给定VA DCO、counter/PFD coarse loop、divider；增加正负误差 TDC 与 fine PI，接 controller 模式切换 | 允许改 controller/filter/顶层，保留 coarse-only 的频率比及复位行为；DCO和divider不能重写 | 重构每窗口计数/每次TDC码，再查相位和频率、锁旗撤销、重锁；不同DCO增益/量化；Spectre终验 |
| PLL 接入 fractional DSM 和可配置反馈 | 已验证 integer loop；新增 DSM 把 fractional control 分配到邻码或N/N+1反馈，题面明确一种架构 | 允许改 divider或DCO适配、filter/controller连接；fraction=0保留整数模式；明确reset/配置生效点 | 平均比率、分频序列/DSM均值、相位/period分布、阶跃及旧模式；隐藏改初相位/增益证明反馈；Spectre终验 |
| fixed-T_bit SAR 接入 valid握手比较器 | 给定VA S/H、DAC、原SAR；接有限响应比较器并改变推进逻辑 | 允许改SAR、控制连线及指定时序参数；保留fixed模式、采样时刻/码约定；S/H/DAC需复用 | 持有期间输入跳变、每位试码、valid前不得推进、转换完成有界、连续转换；不同settling/latency；Spectre终验 |

三题均不追求模拟器速度、优化代码或收敛技巧。公开与隐藏 checker 的事件约定、可达范围、量化阈值、测量窗口及 tolerances 必须先定，再定性能门槛。仅有拓扑静态检查不够；固定部件、可观测内部节点及隐藏动态扰动需要一起证明真实复用。题目不得要求保持本轮识别出的错误行为，正确基线与修复历史应分开。

## 本轮检查及未完成项

- 读五个 GitHub 仓库的固定 commit 和相关源码/测试，检查 license；读两个作者/官方教学源和一篇论文。raw目录保留实际成功取得的源，不保留不存在或下载失败的文件。
- 未运行 Python参考模型、RTL、VA、Spectre或EVAS；没有通过率、锁定性能或兼容性结论。没有下载PDK、未读取schematic图片、未核对作者硅片结果。
- 谈到性能值时均限于源代码阈值/作者报告或改题建议；benchmark最终容差仍未知。第一题健康基线与VA TDC实现、第二题fractional架构选择、第三题CDAC电压等效模型需后续确定。
