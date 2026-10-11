# 五类模型质量分析

已审真实候选能够支持基础规格建模、合法整体修复、实际测量和响应驱动实验的有限质量结论。数据题已有真实公开数据使用分析，但尚无本次可评价泛化的交付；集成和POR试做已暴露无提交或接口限制，实际功能能力未知；gain-settling Flash已有有限窗口性质判断的真实PASS，375双模型Agentic均已预算耗尽且无候选，功能能力未知。这些观察只支持已测工程行为，不能据此给题型或模型作普遍难度排名。完整分母见[模型试做汇总](model-pilot-results.md)。

本报告对应#133的M3、#134的D4、#135的E3、#136的R4和#137的T4。分析基于实际候选、原始轨迹和Spectre波形，任务与候选身份见[证据摘要](model-quality.json)。原始审核报告、轨迹及波形留在本地；摘要不表示这些归档已经公开下载。

本报告分析41条代表记录，不用代表数量代替37题、两个模型、两种模式的148格分母。当前版本及全部结果见[机器汇总](model-pilot-summary.json)。One-shot分类采用固定结果中的provider.derived_submission_classification，同时保留原提取与评分状态。


## 按规格建模，M3

024 Flash one-shot及Agentic的真实最后候选在三条件下通过，含不规则时钟停止及大跳变。源码用相对VSS的实际时钟交点采样输入、状态保持、transition驱动输出，未见答案表、私有文件读取或EVAS专用语法。它支持“基础采样题可解、确实考查事件/轨参考/保持及过渡”，不证明所有合法输入或另一后端等价。GLM one-shot的 bare bound_step 实际编译失败属于候选语法错误，不能与电路行为FAIL合并。

082 GLM Agentic通过两个实际条件，按真实envelope更新带死区/上下限的增益，输出限幅、reset在公开采样边沿生效。它提供有状态反馈行为的代表，不是按默认输出硬编码。

071新公开合同Flash one-shot两条件实际 completed、rc0、reward0。候选只在timer读取sample并开关tracking/metric；真实sample上升后超过200ps过渡期，5.28/6.432ns仍metric=0。题面已明确采集值的tick更新和窗口的sample边沿控制，此例可归为将异步开窗误写成轮询的功能错误。末句孤立看有范围偏宽的可读性弱点，结合显式边沿不足以将拒绝归因未公开要求。新版同题Flash Agentic最后候选则用sample cross控制窗口/metric、timer仅更新保持值，两实际条件PASS；同一5.28/6.432ns点actual metric=.9，73归档artifact逐项匹配。这个具体实现差异解释两候选为何不同，不证明工具造成模式优势。身份见quality-analysis-071-cross-mode.json。

308 Flash旧候选的实际producer采样、consumer消费reset_node及顶层替换消费已有六台架证据。它们是模块协作及替身干预，不是根据响应改变激励的闭环。最小私有重复signal覆盖更新后，同候选实际5/6，延长窗口中的第二次合法signal被fresh_reset清零拒绝。这是公开允许的重复signal功能差异，旧6/6不可升级为当前通过，亦不能只按模块结构PASS断言全部正确。此次覆盖与clock覆盖均已独立实际校准，原raw保留。

308 Flash Agentic的最后完整冻结候选在当前六个条件全部通过。源码在signal采样后保留have_reset，仅由reset清除；真实重复signal在15.282ns与21.432ns分别将vout更新为.7916667与.831，reset_node仍为.339。这具体解释了它与one-shot首次signal后清除fresh_reset的差异，不证明工具造成模式优势。266个归档artifact与六份PSF已独立核验。原1200秒预算结束、末尾公共网关不可用和一次Python NameError均保留；评分绑定服务端确认并冻结的三文件candidate2034c168…，没有用后来本地文件或未确认动作替换。native API错误帧为0只说明模型服务层，不表示所有工具操作成功。

038 Flash Agentic正常stop结束，模型收到明确shell提交附录并写了本地VA，却没有一次harness-public尝试，也没有冻结candidate；协调者按协议未提交单独分类，score=null。直接evas原生工具未暴露不等于说明过的shell路线不可用；当时远端可用性因未尝试仍未知。未从本地或最终消息提取候选补分。见038-flash-no-submission-review.md/json。

375当前双模型Agentic均在末轮length/16384输出上限停止，无候选、无Spectre、score=null。Flash实际读取公开自测、公开客户端并成功列出材料，读取尚未提交dut.va被正确拒绝；8帧、0API错误，公开路线正常。最后16384全部为reasoning，未写源码或提交，原verifier无冻结候选异常保留。固定one-shot最终表375 GLM实际length32000无提交，Flash provider无响应归因未知，是预算或接口观察，不是非重叠时钟行为错误。M3已有024的有限可解性与具体工程区分，375四格均无候选，因此非重叠时钟功能能力未知，试做已完成而非等待成功解题。19个建模来源的完整分母与失败分类见模型试做汇总。证据见quality-analysis-375-flash-final.md/json。

证据沿用 quality-analysis-working.md、quality-analysis-agentic-incremental.md、model-quality-071-flash-contract-attribution.md、clock-and-author-overlays-final-review.md；源码/条件SHA见对应JSON及candidate-identities。旧十一题公开修正前的尝试只作探索，不纳入新版难度结论。

## 从真实数据建模，D4

GLM Agentic实际加载全部32训练+2自测记录，核对CSV输入/时钟与公开PWL，使用2.44pF及观测导数拟合F(vin,vhold)，建立自有状态的数值积分并按采集RMS、保持最大误差和采样误差分段自评。所审程序使用真值作拟合与误差比较，未见逐时真值反馈成预测输出、时间对齐或靠长平静区稀释采集误差。公开自测也参与部分拟合/调参，属于许可公共材料，不能因此将它的自评当独立泛化证据。

真实原生1200.159439s预算内有57次assistant、61个本地工具、一次公共目录读取、0API错误帧、0Spectre。末尾仍在重写并调试Python pipeline，缺少load_all导入后无完成返回；没有VA交付或submission，verifier/score均null。完整轨迹和逐文件核验支持“材料正确到达并被使用、预算内策略未完成”，不支持“材料传递失败”或“电路拟合FAIL”。原raw的通用infra分类保留，另以固定的预算裁定记录解释，不覆盖历史。

本范围未发现私有heldout/checker进入消息或分析代码。该判断限于已审轨迹，不是训练污染证明或新隔离验收。两个模式canonical题面/34CSV/JSON/default的SHA对齐只证明同源字节，不证明文件表示与单请求序列化具有相同上下文开销或实际使用。Flash Agentic也在原生1200.138407s耗尽，无候选。它实际读取公开34实验，拟合真实输出导数得到物理/多项式电导表面，并检查瞬态及外推风险；没有VA生成、提交或全波形/留出验收。31个本地bash、28次assistant、0API错误，公共模拟在缺少dut.va时被正确拒绝，实际Spectre为0。固定one-shot两模型实际length32000，派生分类output_budget_exhausted_no_submission，原提取格式失败状态保留。D4四格都有终态但无可评分候选，真实留出泛化能力未知；试做完成不要求必须解题成功。

证据见 quality-analysis-data-agentic-incremental.md/json及quality-analysis-data-flash-agentic-incremental.md/json，含实际prompt、public文件、raw、receipt及trial result身份。

## 扩展与集成，E3

截至固定snapshot，349及ADPLL两题的GLM/Flash Agentic都在末轮length16384停止，没有提交候选、没有执行终评、score=null。已独立读取四份真实raw/summary，核对封存SHA和最后usage；大部分末轮输出计入reasoning。349模型读了公开baseline及材料，ADPLL Flash读了健康组件/题意；初始分析识别了实际复用组件的要求，但没有可运行交付，不能评价新增通道/细调实现、旧行为兼容或部件因果作用。此处不能用作者参考PASS充当模型能力，也不能把未提交算成集成功能FAIL。

当前两题Agentic均无有效候选，E3应如实报告预算/提交障碍和功能能力未知，不能虚构因果分析。本次两个模式均无可评分的集成候选，因此没有模型DCO/反馈/细调关闭兼容或349采样组件作用的因果证据。公开诊断/结构符合只是入口，不自动证明数据流的作用。固定one-shot两题GLM均actual length32000无提交，Flash均provider无响应归因未知，均无可评分候选；两个模式的真实功能能力均未知。E3可据此形成预算和交付边界的有限结论，不需要永远等待成功候选或再试；完整八格来源归类见模型试做汇总。

## 诊断与修复，R4

五个既有one-shot代表的合法完整重写在10条实际条件下通过。debounce保留连续资格、取消及重新武装；PFD按真实两个边沿和延迟reset维护状态；reset-sequencer保留资格/时钟计数及停止保持；UVLO保留公开滞回与恢复；五VA电源链保留UVLO→释放→使能→真实下游activity因果连接及保护清除。已读代码未见固定测试时间答案或删下游伪造ready。

这支持合法整体重写仍能实现真实功能，评分没有按参考代码形状或改动行数判错。单模块可通过基础状态重建解决，应保留基础覆盖定位，不通过禁重写人为加难。多VA链有实际协作义务，不能仅因文件多就称难。单个候选/两条件不能证明全部输入或总体区分度；五题20格及两模式失败类型由机器汇总与这些代表关联，不给未读的新Agentic候选额外源码能力结论。

证据见 quality-analysis-working.md、quality-analysis-evidence.json和candidate-identities。这些公开合同及私有条件未被后续十一题合同/308/clock覆盖改动取代。

## 测量与表征，T4

已审online-gain从实际输入/输出差分跨度计算增益，sampled-rms在实际采样沿累积平方，不从DUT参数或理想输入公式偷取指标；各三条件真实通过。clock-frequency GLM Agentic保留两路真实上升沿历史并按实际周期计算。覆盖修正后原one-shot Flash及Agentic GLM均实际3/3；额外13.8截断诊断在新第三例被拒绝，支持评价真实周期比。未把额外诊断加入179登记作者分母。

offset-search Flash只在实际ready响应到来时依据dcmpp更新搜索并发下一请求，缺响应时撤销等待、报告超时。三实际条件通过，支持响应驱动实验及完成/超时区分。它没有驱动观测端，也不是按固定答案输出成功。

这两层证据不能代替性质判断。gain-settling GLM Agentic已读取公开静态/动态VA和cases；一次terminated由原生内部重试成功恢复，末有效响应length16384但没有候选、Spectre或性质测量交付，固定typed分类为原生传输成功恢复后输出预算耗尽，无新增attempt，原1错误保留；功能能力未知。Flash已在原1200s预算耗尽后对最后完整冻结候选完成三条件PASS，one-shot GLM实际length32000无提交、Flash provider无响应归因未知；POR两模型Agentic已实际读取cases、网表及观测/数字组件，末轮length16384无候选、无Spectre、score=null，one-shot两模型都被provider context limit拒绝。POR试做可以形成上下文/预算障碍的有限结论，但完整上电、欠压、恢复及自动性质判断能力未知，不需要为了形成分析而强求成功解题。必须分别报告测量数值错误、性质误报/漏报、实验未执行或未完成，不能把搜索PASS扩写为T4全部完成。旧time-protocol公开码保持语义修正前FAIL仍是探索；新版终态才用于最终分析。Flash候选从真实static/input变化计算增益，采81个dynamic点并按窗口末static目标作最后超差/尾8判断。独立PSF计算正常两轮7.25/7.75ns,status1；慢DUT末样本仍超差,status3、settling_ns0但gain有效2.5；无效跨度.007/-.003则status2其余0，均与实际报告一致。支持有限窗口性质区分；未见读内部settled、驱动观测端或答案硬编码。原公共API误用和末尾未确认去debug写入保留，评分绑定先前完整冻结debug候选。10题40格的完整分母见机器汇总，不把有限窗口推广成无限稳定。证据见quality-analysis-gain-flash.md/evidence.json及只读PSF probe。

## 发布时的分母与结论边界

| 实际状态 | 可以说明 | 不能说明 |
| --- | --- | --- |
| 已graded的功能PASS/FAIL | 指定case、候选、版本的实际合同符合性；源码/raw能支持具体原因 | 未测输入全正确、整体难度或跨后端等价 |
| 无效VA/编译失败 | 候选无法在固定后端执行，保留日志及身份 | 已测电气功能FAIL |
| 截断/格式不完整 | 未取得完整可评分交付，保留原响应 | 补写后的假想电路错误 |
| 正常stop但仅本地源码、未协议提交 | 已交付shell路线仍未尝试，无冻结candidate、null；保留环境可用性不可知 | 从本地/最终消息补造评分候选或归因电气FAIL |
| 原生output length/16384 | 实际输出预算停止且无提交，score=null | 集成功能失败或客观题目过难 |
| 原生1200s预算耗尽 | 原资源内策略未完成，无提交保留 | 额外时间必能成功或材料缺失 |
| API无响应/环境失败/未知 | 真实attempt及失败层/未知状态 | 自动归因模型功能、删除分母或选历史最好答案 |
| 在途/未启动 | 尚待最终证据 | 任何成功、失败或完成声明 |

原生默认输出上限16384与one-shot32000不同，旧5格stock联网安装与fresh69格verified-offline执行历史亦不同。必须公开这些边界，不能把模式差异直接归因工具增强或模型能力。材料字节对齐不能消除它们。所有旧失败、预算、环境和未知继续保留，十一题公开修正前尝试仅作为探索。

作者当前179变体/584条件位置的实际校准是任务判据证据，不是148格模型完成。308当前覆盖和clock当前覆盖替换了旧私有条件位置，严格复用及新增实际身份已独立审；不能把a5历史1104次尝试升级成新模型运行。

所有必要代表均有终态和相应分析。无提交时的能力未知是本次结论的限制；试做完成不要求模型成功解题。五份spec的建设、校准、参考入口和模型试做义务由[交付验收](../spec-delivery.md)统一对应。
